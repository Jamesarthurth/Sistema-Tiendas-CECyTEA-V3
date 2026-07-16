"""Pruebas automáticas del motor V3.

Incluye:
1. Pagos parciales y segundo abono.
2. Pago anticipado que cubre meses futuros y deja saldo a favor.
"""

from pathlib import Path

import pandas as pd

from motor_v3 import cargar_machote, procesar_plantel

BASE_DIR = Path(__file__).resolve().parent
ARCHIVO_MACHOTE = BASE_DIR / "datos" / "Machote_Tarifas_CECYTEA_V3.xlsx"
CLAVE_PRUEBA = "CJM"


def dinero(valor: float) -> str:
    return f"${valor:,.2f}"


def obtener_fila(estado: pd.DataFrame, mes: str, concepto: str) -> pd.Series:
    """Obtiene una fila mensual/concepto y falla si no existe."""
    filtro = (estado["MES"] == pd.Timestamp(mes)) & (estado["CONCEPTO"] == concepto)
    filas = estado.loc[filtro]
    assert len(filas) == 1, f"No se encontró una sola fila para {mes} / {concepto}."
    return filas.iloc[0]


def prueba_pagos_parciales(machote) -> None:
    """Un segundo abono completa febrero y continúa hacia marzo."""
    pagos_prueba = pd.DataFrame(
        [
            {
                "ID_MOVIMIENTO": "PRUEBA-001",
                "FECHA": "2026-02-10",
                "PAGO_CUOTA": 1500.00,
                "PAGO_EE": 300.00,
            },
            {
                "ID_MOVIMIENTO": "PRUEBA-002",
                "FECHA": "2026-03-15",
                "PAGO_CUOTA": 1800.00,
                "PAGO_EE": 250.00,
            },
        ]
    )

    resultado = procesar_plantel(machote, CLAVE_PRUEBA, pagos_prueba)
    estado = resultado["estado_mensual"]

    febrero_cuota = obtener_fila(estado, "2026-02-01", "CUOTA")
    marzo_cuota = obtener_fila(estado, "2026-03-01", "CUOTA")
    febrero_ee = obtener_fila(estado, "2026-02-01", "EE")
    marzo_ee = obtener_fila(estado, "2026-03-01", "EE")

    assert febrero_cuota["ESTADO"] == "PAGADO"
    assert febrero_ee["ESTADO"] == "PAGADO"
    assert round(float(marzo_cuota["PAGADO"]), 2) == 657.00
    assert round(float(marzo_cuota["PENDIENTE"]), 2) == 4628.00
    assert marzo_cuota["ESTADO"] == "PARCIAL"
    assert round(float(marzo_ee["PAGADO"]), 2) == 52.00
    assert round(float(marzo_ee["PENDIENTE"]), 2) == 945.00
    assert marzo_ee["ESTADO"] == "PARCIAL"
    assert round(float(resultado["resumen"]["SALDO_FAVOR_CUOTA"]), 2) == 0.00
    assert round(float(resultado["resumen"]["SALDO_FAVOR_EE"]), 2) == 0.00

    print("OK · Prueba 1: pagos parciales y segundo abono.")


def prueba_pago_anticipado_y_saldo_a_favor(machote) -> None:
    """Un pago de mayo puede cubrir hasta junio y dejar saldo a favor."""
    pagos_prueba = pd.DataFrame(
        [
            {
                "ID_MOVIMIENTO": "PRUEBA-003",
                "FECHA": "2026-05-20",
                "PAGO_CUOTA": 22000.00,
                "PAGO_EE": 4200.00,
            }
        ]
    )

    resultado = procesar_plantel(machote, CLAVE_PRUEBA, pagos_prueba)
    estado = resultado["estado_mensual"]

    # Todos los meses disponibles, incluso junio, deben quedar cubiertos.
    cuota = estado[estado["CONCEPTO"] == "CUOTA"]
    ee = estado[estado["CONCEPTO"] == "EE"]
    assert (cuota["ESTADO"] == "PAGADO").all()
    assert (ee["ESTADO"] == "PAGADO").all()
    assert round(float(cuota["PENDIENTE"].sum()), 2) == 0.00
    assert round(float(ee["PENDIENTE"].sum()), 2) == 0.00

    # El sobrante no se pierde ni se mezcla: se conserva por concepto.
    assert round(float(resultado["resumen"]["SALDO_FAVOR_CUOTA"]), 2) == 859.00
    assert round(float(resultado["resumen"]["SALDO_FAVOR_EE"]), 2) == 213.00

    junio_cuota = obtener_fila(estado, "2026-06-01", "CUOTA")
    junio_ee = obtener_fila(estado, "2026-06-01", "EE")
    assert round(float(junio_cuota["PAGADO"]), 2) == 5285.00
    assert round(float(junio_ee["PAGADO"]), 2) == 997.00

    print("OK · Prueba 2: pago anticipado y saldo a favor.")
    print(f"   Saldo a favor de Cuota: {dinero(resultado['resumen']['SALDO_FAVOR_CUOTA'])}")
    print(f"   Saldo a favor de EE: {dinero(resultado['resumen']['SALDO_FAVOR_EE'])}")


def main() -> None:
    machote = cargar_machote(ARCHIVO_MACHOTE)
    assert machote.periodo == "2026-1"
    assert machote.fecha_inicio_pagos == pd.Timestamp("2026-02-01")
    assert machote.fecha_fin_pagos == pd.Timestamp("2026-06-30")
    print("OK · Configuración del periodo leída desde el machote.")

    prueba_pagos_parciales(machote)
    prueba_pago_anticipado_y_saldo_a_favor(machote)

    print("\nPRUEBAS SUPERADAS: el motor conserva pagos parciales, anticipa meses futuros y guarda saldos a favor.\n")


if __name__ == "__main__":
    main()
