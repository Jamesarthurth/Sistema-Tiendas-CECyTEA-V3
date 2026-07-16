# Historial de cambios

## V3.1.0
- Lee la hoja `CONFIGURACION` del machote.
- Filtra pagos por fecha inicial y final del periodo.
- Conserva movimientos excluidos en `Fuera de Periodo`.
- Muestra periodo y rango en Streamlit.
- Agrega periodo y movimientos excluidos al Resumen del Excel.
- Mantiene sin cambios el motor FIFO, pagos parciales y saldos a favor.

## V3.1.1
- Corrige compatibilidad de `MachoteV3` con las pruebas existentes.
- Evita el error `MachoteV3 object has no attribute configuracion`.
- Lee y valida la hoja `CONFIGURACION`.
- Filtra pagos por fecha inicial y final del periodo.
- Exporta movimientos fuera del periodo en una hoja independiente.
- Prueba automáticamente semestres futuros sin cambios de código.
- Limpia resultados de sesión creados por versiones anteriores de Streamlit.
