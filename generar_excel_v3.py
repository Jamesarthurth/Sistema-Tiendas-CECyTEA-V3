"""Comando de consola para generar el Excel final del Sistema CECyTEA V3.

Ejemplo:
python generar_excel_v3.py --global "GLOBAL 2026.xlsx" --machote datos/Machote_Tarifas_CECYTEA_V3.xlsx --salida Reporte_V3.xlsx
"""

from __future__ import annotations

import argparse
from pathlib import Path

from exportador_excel_v3 import exportar_excel_v3
from procesador_v3 import procesar_archivos


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el reporte Excel del Sistema de Tiendas CECyTEA V3.")
    parser.add_argument("--global", dest="archivo_global", required=True, help="Ruta del archivo GLOBAL .xlsx")
    parser.add_argument("--machote", dest="archivo_machote", required=True, help="Ruta del machote V3 .xlsx")
    parser.add_argument("--salida", default="Reporte_Tiendas_CECYTEA_V3.xlsx", help="Nombre o ruta del Excel final")
    parser.add_argument("--hoja-global", default="2024", help="Nombre de la hoja de movimientos en GLOBAL")
    parser.add_argument("--fila-encabezado", type=int, default=1, help="Fila de encabezados de GLOBAL, contando desde cero")
    argumentos = parser.parse_args()

    resultado = procesar_archivos(
        archivo_machote=Path(argumentos.archivo_machote),
        archivo_global=Path(argumentos.archivo_global),
        hoja_global=argumentos.hoja_global,
        fila_encabezado_global=argumentos.fila_encabezado,
    )
    salida = exportar_excel_v3(resultado, Path(argumentos.salida))
    print(f"Reporte creado correctamente: {salida}")


if __name__ == "__main__":
    main()
