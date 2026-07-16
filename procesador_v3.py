"""Integración del Sistema de Tiendas Escolares CECyTEA V3.

Une el lector GLOBAL con el motor FIFO y genera la fuente única de verdad:
Detalle de Cobranza, Trazabilidad y Resumen por plantel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from lector_global import leer_global, separar_movimientos_por_catalogo
from motor_v3 import ConfiguracionPeriodo, MachoteV3, cargar_machote, procesar_plantel

COLUMNAS_DETALLE = [
    "CLAVE_PLANTEL", "NOMBRE_PLANTEL", "MES", "CONCEPTO", "ESPERADO",
    "PAGADO", "PENDIENTE", "ESTADO", "FECHA_ULTIMO_ABONO",
]
COLUMNAS_TRAZABILIDAD = [
    "CLAVE_PLANTEL", "NOMBRE_PLANTEL", "MES", "CONCEPTO", "ORIGEN",
    "ID_MOVIMIENTO", "FECHA_MOVIMIENTO", "MONTO_APLICADO",
]
COLUMNAS_RESUMEN = [
    "CLAVE_PLANTEL", "NOMBRE_PLANTEL", "ADEUDO_CUOTA", "ADEUDO_EE",
    "ADEUDO_TOTAL", "SALDO_FAVOR_CUOTA", "SALDO_FAVOR_EE",
    "SALDO_FAVOR_TOTAL", "MESES_CON_ADEUDO", "ESTADO_GENERAL",
]


def _estado_general(adeudo_total: float, saldo_favor_total: float) -> str:
    if adeudo_total > 0.005:
        return "CON ADEUDO"
    if saldo_favor_total > 0.005:
        return "SALDO A FAVOR"
    return "AL CORRIENTE"


def _meses_con_adeudo(detalle_plantel: pd.DataFrame) -> str:
    con_saldo = detalle_plantel[detalle_plantel["PENDIENTE"] > 0.005].copy()
    if con_saldo.empty:
        return ""
    meses = sorted(pd.to_datetime(con_saldo["MES"]).dt.to_period("M").unique())
    return ", ".join(str(mes) for mes in meses)


def _configuracion_del_machote(machote: MachoteV3) -> ConfiguracionPeriodo:
    """Obtiene configuración aun si el objeto viene de una prueba antigua."""
    configuracion = getattr(machote, "configuracion", None)
    if isinstance(configuracion, ConfiguracionPeriodo):
        return configuracion
    configuracion = ConfiguracionPeriodo.desde_tarifas(machote.tarifas)
    try:
        machote.configuracion = configuracion
    except Exception:
        pass
    return configuracion


def filtrar_movimientos_por_periodo(
    movimientos: pd.DataFrame,
    configuracion: ConfiguracionPeriodo,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa movimientos dentro y fuera del rango configurado."""
    if movimientos is None or movimientos.empty:
        columnas = list(movimientos.columns) if isinstance(movimientos, pd.DataFrame) else []
        vacio = pd.DataFrame(columns=columnas)
        return vacio.copy(), vacio.copy()

    if "FECHA" not in movimientos.columns:
        raise ValueError("Los movimientos normalizados deben incluir la columna FECHA.")

    copia = movimientos.copy()
    copia["FECHA"] = pd.to_datetime(copia["FECHA"], errors="coerce")
    if copia["FECHA"].isna().any():
        ejemplos = copia.loc[copia["FECHA"].isna()].head(5).to_dict("records")
        raise ValueError(f"Hay movimientos con FECHA inválida: {ejemplos}")

    fechas = copia["FECHA"].dt.normalize()
    dentro = fechas.between(
        configuracion.fecha_inicio_pagos,
        configuracion.fecha_fin_pagos,
        inclusive="both",
    )
    return copia.loc[dentro].copy(), copia.loc[~dentro].copy()


def procesar_periodo(
    machote: MachoteV3,
    movimientos_global: pd.DataFrame,
) -> dict[str, Any]:
    """Procesa planteles activos y excluye pagos fuera del periodo."""
    configuracion = _configuracion_del_machote(machote)
    movimientos_periodo, movimientos_fuera_periodo = filtrar_movimientos_por_periodo(
        movimientos_global, configuracion
    )

    claves_activas = set(machote.planteles["CLAVE_PLANTEL"].astype(str).str.upper())
    movimientos_reconocidos, movimientos_no_reconocidos = separar_movimientos_por_catalogo(
        movimientos_periodo, claves_activas
    )

    detalles: list[pd.DataFrame] = []
    trazas: list[pd.DataFrame] = []
    filas_resumen: list[dict[str, Any]] = []

    for _, plantel in machote.planteles.sort_values("CLAVE_PLANTEL").iterrows():
        clave = str(plantel["CLAVE_PLANTEL"]).strip().upper()
        pagos_plantel = movimientos_reconocidos[
            movimientos_reconocidos["CLAVE_PLANTEL"].astype(str).str.upper() == clave
        ].copy()

        resultado = procesar_plantel(machote, clave, pagos_plantel)
        detalle_plantel = resultado["estado_mensual"].copy()
        traza_plantel = resultado["trazabilidad"].copy()
        resumen_motor = resultado["resumen"]

        detalles.append(detalle_plantel)
        if not traza_plantel.empty:
            trazas.append(traza_plantel)

        saldo_favor_total = float(
            resumen_motor["SALDO_FAVOR_CUOTA"] + resumen_motor["SALDO_FAVOR_EE"]
        )
        adeudo_total = float(resumen_motor["ADEUDO_TOTAL"])
        filas_resumen.append({
            "CLAVE_PLANTEL": clave,
            "NOMBRE_PLANTEL": resumen_motor["NOMBRE_PLANTEL"],
            "ADEUDO_CUOTA": float(resumen_motor["ADEUDO_CUOTA"]),
            "ADEUDO_EE": float(resumen_motor["ADEUDO_EE"]),
            "ADEUDO_TOTAL": adeudo_total,
            "SALDO_FAVOR_CUOTA": float(resumen_motor["SALDO_FAVOR_CUOTA"]),
            "SALDO_FAVOR_EE": float(resumen_motor["SALDO_FAVOR_EE"]),
            "SALDO_FAVOR_TOTAL": saldo_favor_total,
            "MESES_CON_ADEUDO": _meses_con_adeudo(detalle_plantel),
            "ESTADO_GENERAL": _estado_general(adeudo_total, saldo_favor_total),
        })

    detalle = (
        pd.concat(detalles, ignore_index=True)
        if detalles else pd.DataFrame(columns=COLUMNAS_DETALLE)
    )
    detalle = detalle[COLUMNAS_DETALLE].sort_values(
        ["CLAVE_PLANTEL", "MES", "CONCEPTO"]
    ).reset_index(drop=True)

    trazabilidad = (
        pd.concat(trazas, ignore_index=True)
        if trazas else pd.DataFrame(columns=COLUMNAS_TRAZABILIDAD)
    )
    trazabilidad = trazabilidad[COLUMNAS_TRAZABILIDAD].sort_values(
        ["CLAVE_PLANTEL", "FECHA_MOVIMIENTO", "ID_MOVIMIENTO", "CONCEPTO", "MES"]
    ).reset_index(drop=True)

    resumen = pd.DataFrame(filas_resumen, columns=COLUMNAS_RESUMEN)
    resumen = resumen.sort_values(
        ["ADEUDO_TOTAL", "CLAVE_PLANTEL"], ascending=[False, True]
    ).reset_index(drop=True)

    configuracion_dict = {
        "PERIODO": configuracion.periodo,
        "FECHA_INICIO_PAGOS": configuracion.fecha_inicio_pagos,
        "FECHA_FIN_PAGOS": configuracion.fecha_fin_pagos,
        "DESCRIPCION": configuracion.descripcion,
    }

    return {
        "detalle_cobranza": detalle,
        "trazabilidad": trazabilidad,
        "resumen_planteles": resumen,
        "movimientos_reconocidos": movimientos_reconocidos.reset_index(drop=True),
        "movimientos_no_reconocidos": movimientos_no_reconocidos.reset_index(drop=True),
        "movimientos_fuera_periodo": movimientos_fuera_periodo.reset_index(drop=True),
        "configuracion_periodo": configuracion_dict,
        # Alias de compatibilidad para evitar errores si una interfaz previa usa
        # el nombre corto "configuracion".
        "configuracion": configuracion_dict,
    }


def procesar_archivos(
    archivo_machote: str | Path,
    archivo_global: str | Path,
    hoja_global: str = "2024",
    fila_encabezado_global: int = 1,
) -> dict[str, Any]:
    machote = cargar_machote(archivo_machote)
    movimientos = leer_global(
        archivo_global,
        hoja=hoja_global,
        fila_encabezado=fila_encabezado_global,
    )
    return procesar_periodo(machote, movimientos)
