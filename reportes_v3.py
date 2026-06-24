"""Reportes del Sistema de Tiendas Escolares CECyTEA V3.

Este módulo no calcula pagos. Solo transforma la salida de ``procesador_v3.py``
en vistas administrativas consistentes. La fuente única de verdad sigue siendo
el Detalle de Cobranza generado por el motor FIFO.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

TOLERANCIA = 0.005

COLUMNAS_DETALLE = [
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

COLUMNAS_RESUMEN = [
    "CLAVE_PLANTEL",
    "NOMBRE_PLANTEL",
    "ADEUDO_CUOTA",
    "ADEUDO_EE",
    "ADEUDO_TOTAL",
    "SALDO_FAVOR_CUOTA",
    "SALDO_FAVOR_EE",
    "SALDO_FAVOR_TOTAL",
    "MESES_CON_ADEUDO",
    "ESTADO_GENERAL",
]

MESES_ES = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}


def _validar_columnas(df: pd.DataFrame, requeridas: list[str], nombre: str) -> None:
    faltantes = [col for col in requeridas if col not in df.columns]
    if faltantes:
        raise ValueError(f"{nombre} no contiene las columnas requeridas: {faltantes}")


def _dinero(valor: Any) -> str:
    return f"${float(valor or 0):,.2f}"


def _etiqueta_mes(valor: Any) -> str:
    fecha = pd.to_datetime(valor)
    return f"{MESES_ES[fecha.month]} {fecha.year}"


def _normalizar_detalle(detalle_cobranza: pd.DataFrame) -> pd.DataFrame:
    """Valida y ordena el detalle sin cambiar los cálculos del motor."""
    _validar_columnas(detalle_cobranza, COLUMNAS_DETALLE, "Detalle de Cobranza")
    detalle = detalle_cobranza[COLUMNAS_DETALLE].copy()
    detalle["MES"] = pd.to_datetime(detalle["MES"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    if detalle["MES"].isna().any():
        raise ValueError("Detalle de Cobranza contiene meses inválidos.")

    for columna in ["ESPERADO", "PAGADO", "PENDIENTE"]:
        detalle[columna] = pd.to_numeric(detalle[columna], errors="coerce")
        if detalle[columna].isna().any():
            raise ValueError(f"Detalle de Cobranza contiene importes inválidos en {columna}.")

    detalle["CONCEPTO"] = detalle["CONCEPTO"].astype(str).str.strip().str.upper()
    conceptos_invalidos = sorted(set(detalle["CONCEPTO"]) - {"CUOTA", "EE"})
    if conceptos_invalidos:
        raise ValueError(f"Detalle de Cobranza contiene conceptos no válidos: {conceptos_invalidos}")

    return detalle.sort_values(["CLAVE_PLANTEL", "MES", "CONCEPTO"]).reset_index(drop=True)


def _celda_ejecutiva(fila: pd.Series) -> str:
    """Texto legible para una celda mensual del Reporte Ejecutivo."""
    estado = str(fila["ESTADO"]).upper()
    esperado = float(fila["ESPERADO"])
    pagado = float(fila["PAGADO"])
    pendiente = float(fila["PENDIENTE"])

    if estado == "SIN CUOTA":
        return "SIN CUOTA"
    if estado == "PAGADO":
        return f"PAGADO\n{_dinero(pagado)}"
    if estado == "PARCIAL":
        return f"PARCIAL\nPagado: {_dinero(pagado)}\nDebe: {_dinero(pendiente)}"
    return f"PENDIENTE\nDebe: {_dinero(esperado)}"


def crear_reporte_ejecutivo(detalle_cobranza: pd.DataFrame) -> pd.DataFrame:
    """Crea una vista amplia, una fila por plantel y concepto.

    Cada columna mensual se deriva directamente de una fila del Detalle de
    Cobranza. No se recalcula ningún pago ni adeudo en esta función.
    """
    detalle = _normalizar_detalle(detalle_cobranza)
    meses = sorted(detalle["MES"].drop_duplicates().tolist())
    etiquetas = [_etiqueta_mes(mes) for mes in meses]

    filas: list[dict[str, Any]] = []
    grupos = detalle.groupby(["CLAVE_PLANTEL", "NOMBRE_PLANTEL", "CONCEPTO"], sort=True)
    for (clave, nombre, concepto), grupo in grupos:
        fila: dict[str, Any] = {
            "CLAVE_PLANTEL": clave,
            "NOMBRE_PLANTEL": nombre,
            "CONCEPTO": concepto,
            "TOTAL_ESPERADO": float(grupo["ESPERADO"].sum()),
            "TOTAL_PAGADO": float(grupo["PAGADO"].sum()),
            "TOTAL_PENDIENTE": float(grupo["PENDIENTE"].sum()),
        }
        for mes, etiqueta in zip(meses, etiquetas, strict=True):
            coincidencia = grupo[grupo["MES"] == mes]
            fila[etiqueta] = "SIN CUOTA" if coincidencia.empty else _celda_ejecutiva(coincidencia.iloc[0])
        filas.append(fila)

    columnas = [
        "CLAVE_PLANTEL",
        "NOMBRE_PLANTEL",
        "CONCEPTO",
        *etiquetas,
        "TOTAL_ESPERADO",
        "TOTAL_PAGADO",
        "TOTAL_PENDIENTE",
    ]
    ejecutivo = pd.DataFrame(filas, columns=columnas)
    return ejecutivo.sort_values(["CLAVE_PLANTEL", "CONCEPTO"]).reset_index(drop=True)


def _detalle_de_adeudo(detalle_plantel: pd.DataFrame) -> tuple[str, str]:
    """Convierte saldos pendientes en texto administrativo por mes."""
    pendientes = detalle_plantel[detalle_plantel["PENDIENTE"] > TOLERANCIA].copy()
    if pendientes.empty:
        return "", ""

    meses_texto: list[str] = []
    desglose: list[str] = []
    for mes, grupo_mes in pendientes.groupby("MES", sort=True):
        etiqueta = _etiqueta_mes(mes)
        meses_texto.append(etiqueta)
        partes = []
        for concepto in ("CUOTA", "EE"):
            fila = grupo_mes[grupo_mes["CONCEPTO"] == concepto]
            if not fila.empty and float(fila.iloc[0]["PENDIENTE"]) > TOLERANCIA:
                etiqueta_concepto = "Cuota" if concepto == "CUOTA" else "EE"
                partes.append(f"{etiqueta_concepto}: {_dinero(fila.iloc[0]['PENDIENTE'])}")
        desglose.append(f"{etiqueta} — {' | '.join(partes)}")

    return ", ".join(meses_texto), " ; ".join(desglose)


def crear_reporte_adeudos(
    detalle_cobranza: pd.DataFrame,
    resumen_planteles: pd.DataFrame,
) -> pd.DataFrame:
    """Resume adeudos y saldos a favor sin recalcular pagos.

    Los importes numéricos se conservan desde ``resumen_planteles`` producido
    por el motor. El detalle solo se usa para describir exactamente qué meses
    y conceptos siguen pendientes.
    """
    detalle = _normalizar_detalle(detalle_cobranza)
    _validar_columnas(resumen_planteles, COLUMNAS_RESUMEN, "Resumen de planteles")
    resumen = resumen_planteles[COLUMNAS_RESUMEN].copy()

    for columna in [
        "ADEUDO_CUOTA",
        "ADEUDO_EE",
        "ADEUDO_TOTAL",
        "SALDO_FAVOR_CUOTA",
        "SALDO_FAVOR_EE",
        "SALDO_FAVOR_TOTAL",
    ]:
        resumen[columna] = pd.to_numeric(resumen[columna], errors="coerce")
        if resumen[columna].isna().any():
            raise ValueError(f"Resumen de planteles contiene importes inválidos en {columna}.")

    descripciones: list[dict[str, str]] = []
    for clave, grupo in detalle.groupby("CLAVE_PLANTEL", sort=False):
        meses, detalle_texto = _detalle_de_adeudo(grupo)
        descripciones.append(
            {
                "CLAVE_PLANTEL": clave,
                "MESES_CON_ADEUDO_REPORTE": meses,
                "DETALLE_ADEUDO": detalle_texto,
            }
        )

    resultado = resumen.merge(pd.DataFrame(descripciones), on="CLAVE_PLANTEL", how="left")
    resultado["MESES_CON_ADEUDO_REPORTE"] = resultado["MESES_CON_ADEUDO_REPORTE"].fillna("")
    resultado["DETALLE_ADEUDO"] = resultado["DETALLE_ADEUDO"].fillna("")

    columnas = [
        "CLAVE_PLANTEL",
        "NOMBRE_PLANTEL",
        "ADEUDO_CUOTA",
        "ADEUDO_EE",
        "ADEUDO_TOTAL",
        "MESES_CON_ADEUDO_REPORTE",
        "DETALLE_ADEUDO",
        "SALDO_FAVOR_CUOTA",
        "SALDO_FAVOR_EE",
        "SALDO_FAVOR_TOTAL",
        "ESTADO_GENERAL",
    ]
    resultado = resultado[columnas].rename(columns={"MESES_CON_ADEUDO_REPORTE": "MESES_CON_ADEUDO"})
    return resultado.sort_values(["ADEUDO_TOTAL", "CLAVE_PLANTEL"], ascending=[False, True]).reset_index(drop=True)


def crear_detalle_cobranza(detalle_cobranza: pd.DataFrame) -> pd.DataFrame:
    """Devuelve el detalle técnico, ya validado y ordenado, para reportarlo."""
    return _normalizar_detalle(detalle_cobranza)


def generar_reportes(resultado_procesamiento: Mapping[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Crea las tres vistas administrativas requeridas por la V3.

    Parámetro:
        resultado_procesamiento: salida de ``procesador_v3.procesar_periodo``.
    """
    requeridos = {"detalle_cobranza", "resumen_planteles"}
    faltantes = requeridos.difference(resultado_procesamiento)
    if faltantes:
        raise ValueError(f"Faltan resultados de procesamiento para crear reportes: {sorted(faltantes)}")

    detalle = crear_detalle_cobranza(resultado_procesamiento["detalle_cobranza"])
    ejecutivo = crear_reporte_ejecutivo(detalle)
    adeudos = crear_reporte_adeudos(detalle, resultado_procesamiento["resumen_planteles"])

    return {
        "reporte_ejecutivo": ejecutivo,
        "adeudos": adeudos,
        "detalle_cobranza": detalle,
    }
