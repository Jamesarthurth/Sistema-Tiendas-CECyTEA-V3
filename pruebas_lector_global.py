"""Pruebas automáticas del lector GLOBAL V3.

No utiliza un GLOBAL real. Construye datos mínimos en memoria para evitar subir
información administrativa sensible al repositorio.
"""

from __future__ import annotations

import pandas as pd

from lector_global import normalizar_global, separar_movimientos_por_catalogo


def construir_global_prueba() -> pd.DataFrame:
    """Imita las columnas importantes del GLOBAL, incluyendo TOTAL que debe ignorarse."""
    return pd.DataFrame(
        [
            {
                "  Fecha": "2026-02-10",
                "NÚMERO": "REC-001",
                "Matrícula": "CJM9900001",
                "Nombre(s)": "CECYTEA TIENDA ESCOLAR",
                "CUOTA RECUPERACION\nCJM": 1500.0,
                "CUOTA RECUPERACION\nAST": 0.0,
                "OTROS INGRESOS (ENERGIA ELEC)": 300.0,
                "TOTAL": 99999.0,
            },
            {
                "  Fecha": "2026-02-12",
                "NÚMERO": "REC-002",
                "Matrícula": "AST9900002",
                "Nombre(s)": "CECYT ASIENTOS TIENDA ESCOLAR",
                "CUOTA RECUPERACION\nCJM": 0.0,
                "CUOTA RECUPERACION\nAST": 1840.0,
                "OTROS INGRESOS (ENERGIA ELEC)": 346.0,
                "TOTAL": 99999.0,
            },
            {
                # No contiene TIEND: debe excluirse aunque tenga importes.
                "  Fecha": "2026-02-15",
                "NÚMERO": "ALUMNO-001",
                "Matrícula": "CJM0000001",
                "Nombre(s)": "ALUMNO DE PRUEBA",
                "CUOTA RECUPERACION\nCJM": 8000.0,
                "CUOTA RECUPERACION\nAST": 5000.0,
                "OTROS INGRESOS (ENERGIA ELEC)": 900.0,
                "TOTAL": 99999.0,
            },
            {
                # Clave existente en el GLOBAL, pero no activa en el catálogo de esta prueba.
                "  Fecha": "2026-02-20",
                "NÚMERO": "REC-003",
                "Matrícula": "XYZ9900003",
                "Nombre(s)": "TIENDA ESCOLAR XYZ",
                "CUOTA RECUPERACION\nCJM": 500.0,
                "CUOTA RECUPERACION\nAST": 0.0,
                "OTROS INGRESOS (ENERGIA ELEC)": 0.0,
                "TOTAL": 99999.0,
            },
        ]
    )


def prueba_lectura_y_separacion_de_conceptos() -> None:
    movimientos = normalizar_global(construir_global_prueba())

    # Solo tres filas de tienda con pagos. El alumno queda fuera.
    assert len(movimientos) == 3

    cjm = movimientos.loc[movimientos["CLAVE_PLANTEL"] == "CJM"].iloc[0]
    assert cjm["MATRICULA"] == "CJM9900001"
    assert cjm["REFERENCIA_GLOBAL"] == "REC-001"
    assert round(float(cjm["PAGO_CUOTA"]), 2) == 1500.00
    assert round(float(cjm["PAGO_EE"]), 2) == 300.00

    ast = movimientos.loc[movimientos["CLAVE_PLANTEL"] == "AST"].iloc[0]
    assert round(float(ast["PAGO_CUOTA"]), 2) == 1840.00
    assert round(float(ast["PAGO_EE"]), 2) == 346.00

    # TOTAL es 99,999 en la fuente, pero nunca participa en los pagos normalizados.
    assert float(cjm["PAGO_CUOTA"]) != 99999.0
    assert float(cjm["PAGO_EE"]) != 99999.0

    print("OK · Prueba 3A: GLOBAL filtra tiendas, obtiene clave por Matrícula y separa Cuota/EE.")


def prueba_claves_no_reconocidas_no_se_descartan() -> None:
    movimientos = normalizar_global(construir_global_prueba())
    validos, no_reconocidos = separar_movimientos_por_catalogo(movimientos, {"CJM", "AST"})

    assert set(validos["CLAVE_PLANTEL"]) == {"CJM", "AST"}
    assert len(no_reconocidos) == 1
    assert no_reconocidos.iloc[0]["CLAVE_PLANTEL"] == "XYZ"

    print("OK · Prueba 3B: una clave fuera del catálogo se reporta y no se pierde silenciosamente.")


def main() -> None:
    prueba_lectura_y_separacion_de_conceptos()
    prueba_claves_no_reconocidas_no_se_descartan()
    print("\nPRUEBAS SUPERADAS: el lector GLOBAL entrega movimientos limpios y auditables.\n")


if __name__ == "__main__":
    main()
