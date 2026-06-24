"""Prueba inicial del motor V3.

Este archivo usa CJM (Jesús María) y reproduce el escenario de pagos parciales
que debe resolver la nueva versión del sistema.
"""

from pathlib import Path

import pandas as pd

from motor_v3 import cargar_machote, procesar_plantel

BASE_DIR = Path(__file__).resolve().parent
ARCHIVO_MACHOTE = BASE_DIR / "datos" / "Machote_Tarifas_CECYTEA_V3.xlsx"
CLAVE_PRUEBA = "CJM"


def dinero(valor: float) -> str:
    return f"${valor:,.2f}"


def main() -> None:
    machote = cargar_machote(ARCHIVO_MACHOTE)

    # Caso 2 + Caso 3: pago parcial y segundo abono.
    # Tarifas reales de CJM en febrero: Cuota $2,643.00 y EE $498.00.
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
    estado = resultado["estado_mensual"].copy()

    febrero_cuota = estado[(estado["MES"] == pd.Timestamp("2026-02-01")) & (estado["CONCEPTO"] == "CUOTA")].iloc[0]
    marzo_cuota = estado[(estado["MES"] == pd.Timestamp("2026-03-01")) & (estado["CONCEPTO"] == "CUOTA")].iloc[0]
    febrero_ee = estado[(estado["MES"] == pd.Timestamp("2026-02-01")) & (estado["CONCEPTO"] == "EE")].iloc[0]
    marzo_ee = estado[(estado["MES"] == pd.Timestamp("2026-03-01")) & (estado["CONCEPTO"] == "EE")].iloc[0]

    # Validaciones del comportamiento FIFO esperado.
    assert febrero_cuota["ESTADO"] == "PAGADO"
    assert febrero_ee["ESTADO"] == "PAGADO"
    assert round(float(marzo_cuota["PAGADO"]), 2) == 657.00
    assert round(float(marzo_cuota["PENDIENTE"]), 2) == 4628.00
    assert marzo_cuota["ESTADO"] == "PARCIAL"
    assert round(float(marzo_ee["PAGADO"]), 2) == 52.00
    assert round(float(marzo_ee["PENDIENTE"]), 2) == 945.00
    assert marzo_ee["ESTADO"] == "PARCIAL"

    print("\nPRUEBA SUPERADA: pagos parciales aplicados correctamente por FIFO.\n")
    print("ESTADO MENSUAL")
    vista = estado.copy()
    vista["MES"] = vista["MES"].dt.strftime("%b-%Y")
    for columna in ["ESPERADO", "PAGADO", "PENDIENTE"]:
        vista[columna] = vista[columna].map(dinero)
    print(vista.to_string(index=False))

    print("\nTRAZABILIDAD DE PAGOS")
    traza = resultado["trazabilidad"].copy()
    if not traza.empty:
        traza["MES"] = traza["MES"].dt.strftime("%b-%Y")
        traza["FECHA_MOVIMIENTO"] = traza["FECHA_MOVIMIENTO"].dt.strftime("%d/%m/%Y")
        traza["MONTO_APLICADO"] = traza["MONTO_APLICADO"].map(dinero)
    print(traza.to_string(index=False))

    print("\nRESUMEN")
    for campo, valor in resultado["resumen"].items():
        if campo.startswith("ADEUDO") or campo.startswith("SALDO"):
            print(f"{campo}: {dinero(float(valor))}")
        else:
            print(f"{campo}: {valor}")


if __name__ == "__main__":
    main()
