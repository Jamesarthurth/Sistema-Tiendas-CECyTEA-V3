"""Pruebas del Paso 5: reportes derivados del Detalle de Cobranza.

Se prueba que los reportes no hagan cálculos alternos: usan la salida del
procesador como fuente única de verdad.
"""

from __future__ import annotations

import pandas as pd

from lector_global import normalizar_global
from motor_v3 import ConfiguracionPeriodo, MachoteV3
from procesador_v3 import procesar_periodo
from reportes_v3 import generar_reportes


def crear_machote_prueba() -> MachoteV3:
    planteles = pd.DataFrame(
        [
            {"CLAVE_PLANTEL": "CJM", "NOMBRE_PLANTEL": "CECyTEA Jesús María", "ESTATUS_TIENDA": "ACTIVA"},
            {"CLAVE_PLANTEL": "AST", "NOMBRE_PLANTEL": "CECyTEA Asientos", "ESTATUS_TIENDA": "ACTIVA"},
        ]
    )
    tarifas = pd.DataFrame(
        [
            {"CLAVE_PLANTEL": "CJM", "NOMBRE_PLANTEL": "CECyTEA Jesús María", "MES": "2026-02-01", "CUOTA": 1000.0, "EE": 100.0},
            {"CLAVE_PLANTEL": "CJM", "NOMBRE_PLANTEL": "CECyTEA Jesús María", "MES": "2026-03-01", "CUOTA": 1000.0, "EE": 100.0},
            {"CLAVE_PLANTEL": "AST", "NOMBRE_PLANTEL": "CECyTEA Asientos", "MES": "2026-02-01", "CUOTA": 500.0, "EE": 50.0},
        ]
    )
    tarifas["MES"] = pd.to_datetime(tarifas["MES"])
    saldos = pd.DataFrame(
        [
            {"CLAVE_PLANTEL": "CJM", "NOMBRE_PLANTEL": "CECyTEA Jesús María", "SALDO_FAVOR_CUOTA": 0.0, "SALDO_FAVOR_EE": 0.0},
            {"CLAVE_PLANTEL": "AST", "NOMBRE_PLANTEL": "CECyTEA Asientos", "SALDO_FAVOR_CUOTA": 0.0, "SALDO_FAVOR_EE": 0.0},
        ]
    )
    return MachoteV3(
        planteles=planteles,
        tarifas=tarifas,
        saldos_iniciales=saldos,
        configuracion=ConfiguracionPeriodo(
            "2026-1-PRUEBA", "2026-02-01", "2026-03-31", "Febrero-Marzo 2026"
        ),
    )


def crear_global_prueba() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "  Fecha": "2026-02-10",
                "NÚMERO": "REC-001",
                "Matrícula": "CJM9900001",
                "Nombre(s)": "CECYTEA TIENDA ESCOLAR",
                "CUOTA RECUPERACION": 600.0,
                "OTROS INGRESOS (ENERGIA ELEC)": 60.0,
                "TOTAL": 99999.0,
            },
            {
                "  Fecha": "2026-03-05",
                "NÚMERO": "REC-002",
                "Matrícula": "CJM9900001",
                "Nombre(s)": "CECYTEA TIENDA ESCOLAR",
                "CUOTA RECUPERACION": 900.0,
                "OTROS INGRESOS (ENERGIA ELEC)": 90.0,
                "TOTAL": 99999.0,
            },
        ]
    )


def main() -> None:
    movimientos = normalizar_global(crear_global_prueba())
    procesado = procesar_periodo(crear_machote_prueba(), movimientos)
    reportes = generar_reportes(procesado)

    ejecutivo = reportes["reporte_ejecutivo"]
    adeudos = reportes["adeudos"]
    detalle = reportes["detalle_cobranza"]

    # El Detalle de Cobranza se preserva como fuente de verdad: 3 meses/plantel x 2 conceptos.
    assert len(detalle) == 6
    assert set(detalle.columns) == {
        "CLAVE_PLANTEL", "NOMBRE_PLANTEL", "MES", "CONCEPTO", "ESPERADO",
        "PAGADO", "PENDIENTE", "ESTADO", "FECHA_ULTIMO_ABONO",
    }

    # El Ejecutivo muestra una fila por plantel y concepto, con texto de estado por mes.
    assert len(ejecutivo) == 4
    cjm_cuota = ejecutivo[(ejecutivo["CLAVE_PLANTEL"] == "CJM") & (ejecutivo["CONCEPTO"] == "CUOTA")].iloc[0]
    assert "PAGADO" in cjm_cuota["Feb 2026"]
    assert "PARCIAL" in cjm_cuota["Mar 2026"]
    assert "Debe: $500.00" in cjm_cuota["Mar 2026"]
    assert round(float(cjm_cuota["TOTAL_PENDIENTE"]), 2) == 500.00

    # Adeudos conserva importes del procesador y describe los meses/conceptos exactos.
    cjm_adeudo = adeudos[adeudos["CLAVE_PLANTEL"] == "CJM"].iloc[0]
    assert round(float(cjm_adeudo["ADEUDO_CUOTA"]), 2) == 500.00
    assert round(float(cjm_adeudo["ADEUDO_EE"]), 2) == 50.00
    assert round(float(cjm_adeudo["ADEUDO_TOTAL"]), 2) == 550.00
    assert cjm_adeudo["MESES_CON_ADEUDO"] == "Mar 2026"
    assert "DETALLE_ADEUDO" not in adeudos.columns

    # AST no pagó; debe aparecer como adeudo completo y no como saldo a favor.
    ast_adeudo = adeudos[adeudos["CLAVE_PLANTEL"] == "AST"].iloc[0]
    assert round(float(ast_adeudo["ADEUDO_TOTAL"]), 2) == 550.00
    assert ast_adeudo["MESES_CON_ADEUDO"] == "Feb 2026"
    assert ast_adeudo["ESTADO_GENERAL"] == "CON ADEUDO"

    # La suma de adeudo publicada debe coincidir con la salida del motor, sin cálculos divergentes.
    assert round(float(adeudos["ADEUDO_TOTAL"].sum()), 2) == round(float(procesado["resumen_planteles"]["ADEUDO_TOTAL"].sum()), 2)

    print("OK · Prueba 5: Reporte Ejecutivo se deriva del Detalle de Cobranza.")
    print("OK · Prueba 5: Adeudos identifica meses y conceptos pendientes exactos.")
    print("OK · Prueba 5: Los importes publicados coinciden con la salida del motor.")
    print("\nPRUEBAS DE REPORTES SUPERADAS.\n")


if __name__ == "__main__":
    main()
