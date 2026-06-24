"""Motor de cálculo V3 para el Sistema de Tiendas Escolares CECyTEA.

Este archivo no depende de Streamlit. Su única función es leer el machote V3 y
aplicar pagos de Cuota y EE por separado mediante FIFO.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

CONCEPTOS = ("CUOTA", "EE")
ESTATUS_ACTIVOS = {"ACTIVA", "ACTIVO"}
TOLERANCIA = 0.005


@dataclass
class MachoteV3:
    """Datos normalizados del machote de tarifas V3."""

    planteles: pd.DataFrame
    tarifas: pd.DataFrame
    saldos_iniciales: pd.DataFrame


def _normalizar_columna(valor: Any) -> str:
    """Convierte encabezados a un formato uniforme y seguro para comparar."""
    if pd.isna(valor):
        return ""
    return str(valor).strip().upper().replace("\n", " ")


def _leer_hoja_con_encabezado(
    archivo: str | Path,
    hoja: str,
    columnas_requeridas: Iterable[str],
) -> pd.DataFrame:
    """Busca automáticamente la fila de encabezados dentro de una hoja del machote."""
    vista = pd.read_excel(archivo, sheet_name=hoja, header=None)
    requeridas = {_normalizar_columna(col) for col in columnas_requeridas}

    fila_encabezado: int | None = None
    for indice, fila in vista.iterrows():
        encontrados = {_normalizar_columna(valor) for valor in fila.tolist()}
        if requeridas.issubset(encontrados):
            fila_encabezado = int(indice)
            break

    if fila_encabezado is None:
        raise ValueError(
            f"No se encontraron los encabezados {sorted(requeridas)} en la hoja '{hoja}'."
        )

    datos = pd.read_excel(archivo, sheet_name=hoja, header=fila_encabezado)
    datos.columns = [_normalizar_columna(col) for col in datos.columns]
    datos = datos.dropna(how="all").copy()
    return datos


def _a_numero(serie: pd.Series, nombre: str) -> pd.Series:
    """Convierte una serie a importe numérico y reporta valores no válidos."""
    convertido = pd.to_numeric(serie, errors="coerce")
    invalidos = serie.notna() & convertido.isna()
    if invalidos.any():
        ejemplos = serie.loc[invalidos].head(5).tolist()
        raise ValueError(f"La columna '{nombre}' contiene montos no válidos: {ejemplos}")
    return convertido.fillna(0.0).astype(float)


def cargar_machote(archivo: str | Path) -> MachoteV3:
    """Lee, valida y normaliza el machote V3.

    Reglas principales:
    - Solo los planteles con ESTATUS_TIENDA = ACTIVA participan en cálculos.
    - Tarifas se capturan en una fila por plantel y por mes.
    - Cuota, EE y saldos a favor nunca se mezclan.
    """
    archivo = Path(archivo)
    if not archivo.exists():
        raise FileNotFoundError(f"No se encontró el machote: {archivo}")

    planteles = _leer_hoja_con_encabezado(
        archivo,
        "PLANTELES",
        ["CLAVE_PLANTEL", "NOMBRE_PLANTEL"],
    )

    if "ESTATUS_TIENDA" not in planteles.columns:
        # Compatibilidad con un machote temprano que aún usaba ACTIVO.
        if "ACTIVO" in planteles.columns:
            planteles["ESTATUS_TIENDA"] = planteles["ACTIVO"].map(
                lambda valor: "ACTIVA" if _normalizar_columna(valor) in {"SI", "ACTIVO", "ACTIVA"} else "SIN TIENDA"
            )
        else:
            raise ValueError("La hoja PLANTELES debe incluir la columna ESTATUS_TIENDA.")

    planteles["CLAVE_PLANTEL"] = planteles["CLAVE_PLANTEL"].fillna("").astype(str).str.strip().str.upper()
    planteles["NOMBRE_PLANTEL"] = planteles["NOMBRE_PLANTEL"].fillna("").astype(str).str.strip()
    planteles["ESTATUS_TIENDA"] = planteles["ESTATUS_TIENDA"].map(_normalizar_columna)

    # Un plantel sin tienda puede no tener clave; uno activo sí debe tenerla.
    activos_sin_clave = planteles[
        planteles["ESTATUS_TIENDA"].isin(ESTATUS_ACTIVOS)
        & (planteles["CLAVE_PLANTEL"] == "")
    ]
    if not activos_sin_clave.empty:
        nombres = activos_sin_clave["NOMBRE_PLANTEL"].tolist()
        raise ValueError(f"Hay planteles ACTIVOS sin CLAVE_PLANTEL: {nombres}")

    activos = planteles[planteles["ESTATUS_TIENDA"].isin(ESTATUS_ACTIVOS)].copy()
    if activos.empty:
        raise ValueError("No hay planteles con estatus ACTIVA en el machote.")

    duplicadas = activos["CLAVE_PLANTEL"].duplicated(keep=False)
    if duplicadas.any():
        claves = activos.loc[duplicadas, "CLAVE_PLANTEL"].tolist()
        raise ValueError(f"Hay claves de plantel duplicadas entre planteles activos: {claves}")

    tarifas = _leer_hoja_con_encabezado(
        archivo,
        "TARIFAS",
        ["CLAVE_PLANTEL", "MES", "CUOTA", "EE"],
    )
    tarifas["CLAVE_PLANTEL"] = tarifas["CLAVE_PLANTEL"].fillna("").astype(str).str.strip().str.upper()
    tarifas["MES"] = pd.to_datetime(tarifas["MES"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    tarifas["CUOTA"] = _a_numero(tarifas["CUOTA"], "CUOTA")
    tarifas["EE"] = _a_numero(tarifas["EE"], "EE")

    tarifas = tarifas[tarifas["CLAVE_PLANTEL"] != ""].copy()
    if tarifas["MES"].isna().any():
        ejemplos = tarifas.loc[tarifas["MES"].isna(), "CLAVE_PLANTEL"].head(5).tolist()
        raise ValueError(f"Hay tarifas sin MES válido. Claves involucradas: {ejemplos}")
    if (tarifas[["CUOTA", "EE"]] < 0).any().any():
        raise ValueError("Las tarifas no pueden tener montos negativos.")

    tarifas = tarifas.merge(
        activos[["CLAVE_PLANTEL", "NOMBRE_PLANTEL", "ESTATUS_TIENDA"]],
        on="CLAVE_PLANTEL",
        how="inner",
        suffixes=("", "_CATALOGO"),
    )
    tarifas["NOMBRE_PLANTEL"] = tarifas["NOMBRE_PLANTEL_CATALOGO"].fillna(tarifas.get("NOMBRE_PLANTEL", ""))
    columnas_eliminar = [col for col in ["NOMBRE_PLANTEL_CATALOGO"] if col in tarifas.columns]
    tarifas = tarifas.drop(columns=columnas_eliminar)

    if tarifas.empty:
        raise ValueError("No se encontraron tarifas para los planteles ACTIVOS.")

    duplicadas_tarifa = tarifas.duplicated(subset=["CLAVE_PLANTEL", "MES"], keep=False)
    if duplicadas_tarifa.any():
        ejemplos = tarifas.loc[duplicadas_tarifa, ["CLAVE_PLANTEL", "MES"]].head(10).to_dict("records")
        raise ValueError(f"Hay tarifas duplicadas para el mismo plantel y mes: {ejemplos}")

    claves_con_tarifa = set(tarifas["CLAVE_PLANTEL"])
    activos_sin_tarifa = activos.loc[~activos["CLAVE_PLANTEL"].isin(claves_con_tarifa), "NOMBRE_PLANTEL"].tolist()
    if activos_sin_tarifa:
        raise ValueError(f"Hay planteles ACTIVOS sin tarifas capturadas: {activos_sin_tarifa}")

    try:
        saldos = _leer_hoja_con_encabezado(
            archivo,
            "SALDOS_INICIALES",
            ["CLAVE_PLANTEL", "SALDO_FAVOR_CUOTA", "SALDO_FAVOR_EE"],
        )
    except ValueError:
        # No bloquea pruebas iniciales si en el futuro se crea un machote sin la hoja.
        saldos = pd.DataFrame(columns=["CLAVE_PLANTEL", "SALDO_FAVOR_CUOTA", "SALDO_FAVOR_EE"])

    saldos["CLAVE_PLANTEL"] = saldos["CLAVE_PLANTEL"].fillna("").astype(str).str.strip().str.upper()
    saldos = saldos[saldos["CLAVE_PLANTEL"] != ""].copy()
    for columna in ["SALDO_FAVOR_CUOTA", "SALDO_FAVOR_EE"]:
        if columna not in saldos.columns:
            saldos[columna] = 0.0
        saldos[columna] = _a_numero(saldos[columna], columna)

    if (saldos[["SALDO_FAVOR_CUOTA", "SALDO_FAVOR_EE"]] < 0).any().any():
        raise ValueError("Los saldos a favor no pueden ser negativos.")

    if saldos["CLAVE_PLANTEL"].duplicated().any():
        claves = saldos.loc[saldos["CLAVE_PLANTEL"].duplicated(keep=False), "CLAVE_PLANTEL"].tolist()
        raise ValueError(f"Hay saldos iniciales repetidos para estas claves: {claves}")

    saldos = activos[["CLAVE_PLANTEL", "NOMBRE_PLANTEL"]].merge(
        saldos[["CLAVE_PLANTEL", "SALDO_FAVOR_CUOTA", "SALDO_FAVOR_EE"]],
        on="CLAVE_PLANTEL",
        how="left",
    )
    saldos[["SALDO_FAVOR_CUOTA", "SALDO_FAVOR_EE"]] = saldos[["SALDO_FAVOR_CUOTA", "SALDO_FAVOR_EE"]].fillna(0.0)

    tarifas = tarifas[["CLAVE_PLANTEL", "NOMBRE_PLANTEL", "MES", "CUOTA", "EE"]].sort_values(
        ["CLAVE_PLANTEL", "MES"]
    ).reset_index(drop=True)
    activos = activos[["CLAVE_PLANTEL", "NOMBRE_PLANTEL", "ESTATUS_TIENDA"]].sort_values("CLAVE_PLANTEL").reset_index(drop=True)

    return MachoteV3(planteles=activos, tarifas=tarifas, saldos_iniciales=saldos)


def _normalizar_pagos(pagos: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    """Acepta pagos de prueba o pagos que luego vendrán de GLOBAL."""
    pagos_df = pd.DataFrame(pagos).copy()
    if pagos_df.empty:
        return pd.DataFrame(columns=["ID_MOVIMIENTO", "FECHA", "PAGO_CUOTA", "PAGO_EE"])

    requeridas = {"FECHA", "PAGO_CUOTA", "PAGO_EE"}
    columnas = {_normalizar_columna(col): col for col in pagos_df.columns}
    faltantes = requeridas.difference(columnas)
    if faltantes:
        raise ValueError(f"Los pagos deben tener estas columnas: {sorted(requeridas)}. Faltan: {sorted(faltantes)}")

    pagos_df = pagos_df.rename(columns={original: normalizada for normalizada, original in columnas.items()})
    if "ID_MOVIMIENTO" not in pagos_df.columns:
        pagos_df["ID_MOVIMIENTO"] = [f"MOV-{indice:04d}" for indice in range(1, len(pagos_df) + 1)]

    pagos_df["FECHA"] = pd.to_datetime(pagos_df["FECHA"], errors="coerce")
    if pagos_df["FECHA"].isna().any():
        raise ValueError("Hay pagos sin FECHA válida.")

    pagos_df["PAGO_CUOTA"] = _a_numero(pagos_df["PAGO_CUOTA"], "PAGO_CUOTA")
    pagos_df["PAGO_EE"] = _a_numero(pagos_df["PAGO_EE"], "PAGO_EE")

    if (pagos_df[["PAGO_CUOTA", "PAGO_EE"]] < 0).any().any():
        raise ValueError("No se permiten pagos negativos.")

    return pagos_df[["ID_MOVIMIENTO", "FECHA", "PAGO_CUOTA", "PAGO_EE"]].sort_values(
        ["FECHA", "ID_MOVIMIENTO"]
    ).reset_index(drop=True)


def _estado(esperado: float, pagado: float) -> str:
    if esperado <= TOLERANCIA:
        return "SIN CUOTA"
    pendiente = max(esperado - pagado, 0.0)
    if pendiente <= TOLERANCIA:
        return "PAGADO"
    if pagado > TOLERANCIA:
        return "PARCIAL"
    return "PENDIENTE"


def aplicar_fifo_por_concepto(
    tarifas_plantel: pd.DataFrame,
    pagos: pd.DataFrame | list[dict[str, Any]],
    concepto: str,
    saldo_inicial: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """Aplica saldo inicial y pagos a un concepto mediante FIFO.

    Regresa:
    1. Estado por mes.
    2. Trazabilidad de cada monto aplicado.
    3. Saldo a favor final para ese concepto.
    """
    concepto = _normalizar_columna(concepto)
    if concepto not in CONCEPTOS:
        raise ValueError(f"Concepto no válido: {concepto}. Usa CUOTA o EE.")

    if tarifas_plantel.empty:
        raise ValueError("No hay tarifas para procesar.")

    clave = str(tarifas_plantel.iloc[0]["CLAVE_PLANTEL"])
    nombre = str(tarifas_plantel.iloc[0]["NOMBRE_PLANTEL"])
    columna_pago = f"PAGO_{concepto}"

    estado = tarifas_plantel[["CLAVE_PLANTEL", "NOMBRE_PLANTEL", "MES", concepto]].copy()
    estado = estado.rename(columns={concepto: "ESPERADO"})
    estado["ESPERADO"] = estado["ESPERADO"].astype(float)
    estado["PAGADO"] = 0.0
    estado["PENDIENTE"] = estado["ESPERADO"]
    estado["FECHA_ULTIMO_ABONO"] = pd.NaT
    estado = estado.sort_values("MES").reset_index(drop=True)

    trazas: list[dict[str, Any]] = []

    def aplicar_monto(monto: float, fecha: pd.Timestamp | pd.NaT, origen: str, id_movimiento: str) -> float:
        restante = float(monto)
        for indice in estado.index:
            pendiente = float(estado.at[indice, "PENDIENTE"])
            if restante <= TOLERANCIA:
                break
            if pendiente <= TOLERANCIA:
                continue

            aplicado = min(restante, pendiente)
            estado.at[indice, "PAGADO"] = float(estado.at[indice, "PAGADO"]) + aplicado
            estado.at[indice, "PENDIENTE"] = max(pendiente - aplicado, 0.0)
            if pd.notna(fecha):
                estado.at[indice, "FECHA_ULTIMO_ABONO"] = fecha

            trazas.append(
                {
                    "CLAVE_PLANTEL": clave,
                    "NOMBRE_PLANTEL": nombre,
                    "MES": estado.at[indice, "MES"],
                    "CONCEPTO": concepto,
                    "ORIGEN": origen,
                    "ID_MOVIMIENTO": id_movimiento,
                    "FECHA_MOVIMIENTO": fecha,
                    "MONTO_APLICADO": aplicado,
                }
            )
            restante -= aplicado
        return max(restante, 0.0)

    saldo_inicial = float(saldo_inicial or 0.0)
    if saldo_inicial < -TOLERANCIA:
        raise ValueError("El saldo inicial no puede ser negativo.")
    saldo_a_favor = aplicar_monto(saldo_inicial, pd.NaT, "SALDO_INICIAL", "SALDO-INICIAL")

    pagos_df = _normalizar_pagos(pagos)
    for _, pago in pagos_df.iterrows():
        monto = float(pago[columna_pago])
        if monto <= TOLERANCIA:
            continue
        saldo_a_favor += aplicar_monto(
            monto=monto,
            fecha=pago["FECHA"],
            origen="PAGO",
            id_movimiento=str(pago["ID_MOVIMIENTO"]),
        )

    estado["PENDIENTE"] = estado["PENDIENTE"].clip(lower=0.0)
    estado["ESTADO"] = estado.apply(lambda fila: _estado(float(fila["ESPERADO"]), float(fila["PAGADO"])), axis=1)
    estado.insert(3, "CONCEPTO", concepto)
    estado = estado[
        [
            "CLAVE_PLANTEL",
            "NOMBRE_PLANTEL",
            "MES",
            "CONCEPTO",
            "ESPERADO",
            "PAGADO",
            "PENDIENTE",
            "ESTADO",
            "FECHA_ULTIMO_ABONO",
        ]
    ]

    trazabilidad = pd.DataFrame(
        trazas,
        columns=[
            "CLAVE_PLANTEL",
            "NOMBRE_PLANTEL",
            "MES",
            "CONCEPTO",
            "ORIGEN",
            "ID_MOVIMIENTO",
            "FECHA_MOVIMIENTO",
            "MONTO_APLICADO",
        ],
    )

    return estado, trazabilidad, float(saldo_a_favor)


def procesar_plantel(
    machote: MachoteV3,
    clave_plantel: str,
    pagos: pd.DataFrame | list[dict[str, Any]],
) -> dict[str, Any]:
    """Procesa un plantel completo: cuota y EE por separado."""
    clave = str(clave_plantel).strip().upper()
    plantel = machote.planteles[machote.planteles["CLAVE_PLANTEL"] == clave]
    if plantel.empty:
        raise ValueError(f"La clave '{clave}' no corresponde a un plantel ACTIVO del machote.")

    tarifas_plantel = machote.tarifas[machote.tarifas["CLAVE_PLANTEL"] == clave].copy()
    if tarifas_plantel.empty:
        raise ValueError(f"El plantel {clave} no tiene tarifas capturadas.")

    saldo = machote.saldos_iniciales[machote.saldos_iniciales["CLAVE_PLANTEL"] == clave]
    saldo_cuota = float(saldo.iloc[0]["SALDO_FAVOR_CUOTA"]) if not saldo.empty else 0.0
    saldo_ee = float(saldo.iloc[0]["SALDO_FAVOR_EE"]) if not saldo.empty else 0.0

    estado_cuota, traza_cuota, saldo_final_cuota = aplicar_fifo_por_concepto(
        tarifas_plantel=tarifas_plantel,
        pagos=pagos,
        concepto="CUOTA",
        saldo_inicial=saldo_cuota,
    )
    estado_ee, traza_ee, saldo_final_ee = aplicar_fifo_por_concepto(
        tarifas_plantel=tarifas_plantel,
        pagos=pagos,
        concepto="EE",
        saldo_inicial=saldo_ee,
    )

    estado = pd.concat([estado_cuota, estado_ee], ignore_index=True).sort_values(
        ["MES", "CONCEPTO"]
    ).reset_index(drop=True)
    trazabilidad = pd.concat([traza_cuota, traza_ee], ignore_index=True)

    resumen = {
        "CLAVE_PLANTEL": clave,
        "NOMBRE_PLANTEL": plantel.iloc[0]["NOMBRE_PLANTEL"],
        "ADEUDO_CUOTA": float(estado_cuota["PENDIENTE"].sum()),
        "ADEUDO_EE": float(estado_ee["PENDIENTE"].sum()),
        "ADEUDO_TOTAL": float(estado_cuota["PENDIENTE"].sum() + estado_ee["PENDIENTE"].sum()),
        "SALDO_FAVOR_CUOTA": saldo_final_cuota,
        "SALDO_FAVOR_EE": saldo_final_ee,
    }

    return {
        "estado_mensual": estado,
        "trazabilidad": trazabilidad,
        "resumen": resumen,
    }
