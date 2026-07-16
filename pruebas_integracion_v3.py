"""Pruebas de integración V3.

Comprueba que el lector GLOBAL y el motor FIFO trabajen juntos.
No usa información real: construye un GLOBAL de prueba y un machote en memoria.
"""

from __future__ import annotations

import pandas as pd

from lector_global import normalizar_global
from motor_v3 import ConfiguracionPeriodo, MachoteV3
from procesador_v3 import procesar_periodo


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
    configuracion = ConfiguracionPeriodo(
        periodo="2026-1-PRUEBA",
        fecha_inicio_pagos="2026-02-01",
        fecha_fin_pagos="2026-03-31",
        descripcion="Febrero-Marzo 2026",
    )
    return MachoteV3(
        planteles=planteles,
        tarifas=tarifas,
        saldos_iniciales=saldos,
        configuracion=configuracion,
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
            {
                # Movimiento válido por clave, pero fuera del periodo configurado.
                "  Fecha": "2026-04-01",
                "NÚMERO": "REC-FUERA",
                "Matrícula": "CJM9900001",
                "Nombre(s)": "CECYTEA TIENDA ESCOLAR",
                "CUOTA RECUPERACION": 5000.0,
                "OTROS INGRESOS (ENERGIA ELEC)": 500.0,
                "TOTAL": 99999.0,
            },
            {
                # Debe conservarse para revisión, no desaparecer.
                "  Fecha": "2026-03-06",
                "NÚMERO": "REC-003",
                "Matrícula": "XYZ9900001",
                "Nombre(s)": "TIENDA ESCOLAR SIN CATALOGO",
                "CUOTA RECUPERACION": 999.0,
                "OTROS INGRESOS (ENERGIA ELEC)": 9.0,
                "TOTAL": 99999.0,
            },
        ]
    )



def prueba_semestre_futuro() -> None:
    """El motor acepta meses y fechas de un semestre futuro sin cambiar código."""
    planteles = pd.DataFrame([
        {"CLAVE_PLANTEL": "CJM", "NOMBRE_PLANTEL": "CECyTEA Jesús María", "ESTATUS_TIENDA": "ACTIVA"}
    ])
    tarifas = pd.DataFrame([
        {"CLAVE_PLANTEL": "CJM", "NOMBRE_PLANTEL": "CECyTEA Jesús María", "MES": "2027-08-01", "CUOTA": 1000.0, "EE": 100.0},
        {"CLAVE_PLANTEL": "CJM", "NOMBRE_PLANTEL": "CECyTEA Jesús María", "MES": "2027-09-01", "CUOTA": 1000.0, "EE": 100.0},
    ])
    tarifas["MES"] = pd.to_datetime(tarifas["MES"])
    saldos = pd.DataFrame([
        {"CLAVE_PLANTEL": "CJM", "NOMBRE_PLANTEL": "CECyTEA Jesús María", "SALDO_FAVOR_CUOTA": 0.0, "SALDO_FAVOR_EE": 0.0}
    ])
    machote = MachoteV3(
        planteles=planteles,
        tarifas=tarifas,
        saldos_iniciales=saldos,
        configuracion=ConfiguracionPeriodo(
            "2027-2", "2027-08-01", "2027-12-31", "Agosto-Diciembre 2027"
        ),
    )
    global_futuro = pd.DataFrame([
        {
            "  Fecha": "2027-07-31", "NÚMERO": "ANTES", "Matrícula": "CJM9900001",
            "Nombre(s)": "CECYTEA TIENDA ESCOLAR", "CUOTA RECUPERACION": 9999.0,
            "OTROS INGRESOS (ENERGIA ELEC)": 999.0,
        },
        {
            "  Fecha": "2027-08-15", "NÚMERO": "DENTRO", "Matrícula": "CJM9900001",
            "Nombre(s)": "CECYTEA TIENDA ESCOLAR", "CUOTA RECUPERACION": 1500.0,
            "OTROS INGRESOS (ENERGIA ELEC)": 150.0,
        },
    ])
    resultado = procesar_periodo(machote, normalizar_global(global_futuro))
    detalle = resultado["detalle_cobranza"]
    agosto = detalle[(detalle["MES"] == pd.Timestamp("2027-08-01")) & (detalle["CONCEPTO"] == "CUOTA")].iloc[0]
    septiembre = detalle[(detalle["MES"] == pd.Timestamp("2027-09-01")) & (detalle["CONCEPTO"] == "CUOTA")].iloc[0]
    assert agosto["ESTADO"] == "PAGADO"
    assert round(float(septiembre["PAGADO"]), 2) == 500.00
    assert len(resultado["movimientos_fuera_periodo"]) == 1
    assert resultado["configuracion_periodo"]["PERIODO"] == "2027-2"
    print("OK · Semestre futuro 2027-2: meses nuevos y filtro temporal funcionan sin cambiar código.")

def main() -> None:
    movimientos = normalizar_global(crear_global_prueba())
    resultado = procesar_periodo(crear_machote_prueba(), movimientos)

    detalle = resultado["detalle_cobranza"]
    resumen = resultado["resumen_planteles"]
    no_reconocidos = resultado["movimientos_no_reconocidos"]
    trazabilidad = resultado["trazabilidad"]
    fuera_periodo = resultado["movimientos_fuera_periodo"]

    # 2 meses de CJM x 2 conceptos + 1 mes de AST x 2 conceptos.
    assert len(detalle) == 6

    # CJM: pagos totales Cuota=1500 y EE=150; FIFO debe liquidar febrero y dejar marzo parcial.
    cjm_feb_cuota = detalle[(detalle["CLAVE_PLANTEL"] == "CJM") & (detalle["MES"] == pd.Timestamp("2026-02-01")) & (detalle["CONCEPTO"] == "CUOTA")].iloc[0]
    cjm_mar_cuota = detalle[(detalle["CLAVE_PLANTEL"] == "CJM") & (detalle["MES"] == pd.Timestamp("2026-03-01")) & (detalle["CONCEPTO"] == "CUOTA")].iloc[0]
    cjm_mar_ee = detalle[(detalle["CLAVE_PLANTEL"] == "CJM") & (detalle["MES"] == pd.Timestamp("2026-03-01")) & (detalle["CONCEPTO"] == "EE")].iloc[0]

    assert cjm_feb_cuota["ESTADO"] == "PAGADO"
    assert round(float(cjm_mar_cuota["PAGADO"]), 2) == 500.00
    assert round(float(cjm_mar_cuota["PENDIENTE"]), 2) == 500.00
    assert cjm_mar_cuota["ESTADO"] == "PARCIAL"
    assert round(float(cjm_mar_ee["PAGADO"]), 2) == 50.00
    assert round(float(cjm_mar_ee["PENDIENTE"]), 2) == 50.00

    # AST no recibió pagos y por eso aparece con su adeudo completo.
    ast = resumen[resumen["CLAVE_PLANTEL"] == "AST"].iloc[0]
    assert round(float(ast["ADEUDO_CUOTA"]), 2) == 500.00
    assert round(float(ast["ADEUDO_EE"]), 2) == 50.00
    assert ast["ESTADO_GENERAL"] == "CON ADEUDO"

    # CJM debe resumir los adeudos reales, no usar TOTAL de GLOBAL.
    cjm = resumen[resumen["CLAVE_PLANTEL"] == "CJM"].iloc[0]
    assert round(float(cjm["ADEUDO_CUOTA"]), 2) == 500.00
    assert round(float(cjm["ADEUDO_EE"]), 2) == 50.00
    assert round(float(cjm["ADEUDO_TOTAL"]), 2) == 550.00
    assert cjm["MESES_CON_ADEUDO"] == "2026-03"

    # El pago de abril se excluye y no altera el saldo del periodo febrero-marzo.
    assert len(fuera_periodo) == 1
    assert fuera_periodo.iloc[0]["REFERENCIA_GLOBAL"] == "REC-FUERA"

    # La clave desconocida se conserva en revisión y no altera CJM ni AST.
    assert len(no_reconocidos) == 1
    assert no_reconocidos.iloc[0]["CLAVE_PLANTEL"] == "XYZ"

    # La trazabilidad permite explicar a qué mes se aplicó cada parte de un pago.
    assert len(trazabilidad) == 6
    assert set(trazabilidad["CONCEPTO"]) == {"CUOTA", "EE"}

    print("OK · Prueba 4: GLOBAL + motor FIFO generan un detalle de cobranza único y auditable.")
    print("OK · Pago parcial: CJM queda con marzo parcial.")
    print("OK · Plantel sin pagos: AST conserva adeudo completo.")
    print("OK · Clave no reconocida: XYZ queda en revisión, no se pierde.")
    print("OK · Movimiento de abril: queda fuera del periodo y no afecta adeudos.")
    prueba_semestre_futuro()
    print("\nPRUEBA DE INTEGRACIÓN SUPERADA.\n")


if __name__ == "__main__":
    main()
