"""Lector y normalizador del archivo GLOBAL para el Sistema de Tiendas Escolares CECyTEA V3.

Este módulo no calcula adeudos. Su única responsabilidad es convertir GLOBAL en una
lista confiable de movimientos de tiendas con esta estructura:

ID_MOVIMIENTO | FECHA | CLAVE_PLANTEL | PAGO_CUOTA | PAGO_EE | ...

Reglas:
- Considera registros cuyo Nombre(s) contenga "TIEND".
- Incluye la excepción de PABELLON DE ARTEAGA, que corresponde a una tienda aunque
  su nombre no contiene la palabra "TIENDA".
- Excluye movimientos con fecha anterior al 01/01/2026.
- Obtiene CLAVE_PLANTEL de los primeros tres caracteres de Matrícula.
- Suma exclusivamente las columnas cuyo encabezado contiene "CUOTA RECUPERACION".
- Lee EE únicamente de "OTROS INGRESOS (ENERGIA ELEC)".
- Nunca usa TOTAL ni otros conceptos de ingreso.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


HOJA_GLOBAL_POR_DEFECTO = "2024"
FILA_ENCABEZADO_POR_DEFECTO = 1

# Regla institucional: los reportes V3 nunca aplican movimientos anteriores a 2026.
# El filtro usa FECHA, no SEMESTRE, porque FECHA identifica el año real del movimiento.
ANIO_MINIMO_GLOBAL = 2026

# Casos conocidos que sí corresponden a una tienda, aunque el texto no incluya TIEND.
EXCEPCIONES_TIENDA_POR_NOMBRE = ("PABELLON DE ARTEAGA",)


def _normalizar_texto(valor: Any) -> str:
    """Normaliza texto de encabezados y valores para comparaciones seguras."""
    if pd.isna(valor):
        return ""
    return " ".join(str(valor).strip().upper().replace("\n", " ").split())


def _resolver_columna(columnas: list[Any], nombre_esperado: str) -> Any:
    """Ubica una columna comparando encabezados sin depender de espacios o saltos."""
    objetivo = _normalizar_texto(nombre_esperado)
    coincidencias = [col for col in columnas if _normalizar_texto(col) == objetivo]
    if len(coincidencias) != 1:
        raise ValueError(
            f"No se encontró una sola columna para '{nombre_esperado}'. "
            f"Coincidencias: {coincidencias}"
        )
    return coincidencias[0]


def _a_importe(serie: pd.Series, nombre: str) -> pd.Series:
    """Convierte importes a número y evita que valores no numéricos pasen desapercibidos."""
    convertido = pd.to_numeric(serie, errors="coerce")
    invalidos = serie.notna() & convertido.isna()
    if invalidos.any():
        ejemplos = serie.loc[invalidos].head(5).tolist()
        raise ValueError(f"La columna '{nombre}' contiene importes no válidos: {ejemplos}")
    return convertido.fillna(0.0).astype(float)


def leer_global(
    archivo: str | Path,
    hoja: str = HOJA_GLOBAL_POR_DEFECTO,
    fila_encabezado: int = FILA_ENCABEZADO_POR_DEFECTO,
    anio_minimo: int = ANIO_MINIMO_GLOBAL,
) -> pd.DataFrame:
    """Lee un GLOBAL de Excel y devuelve exclusivamente sus movimientos de tienda normalizados."""
    archivo = Path(archivo)
    if not archivo.exists():
        raise FileNotFoundError(f"No se encontró el archivo GLOBAL: {archivo}")

    global_df = pd.read_excel(archivo, sheet_name=hoja, header=fila_encabezado)
    return normalizar_global(global_df, anio_minimo=anio_minimo)


def normalizar_global(
    global_df: pd.DataFrame,
    anio_minimo: int = ANIO_MINIMO_GLOBAL,
) -> pd.DataFrame:
    """Convierte un DataFrame GLOBAL en movimientos de tienda estandarizados.

    Se expone por separado para permitir pruebas sin subir ni publicar un GLOBAL real.

    Parámetros
    ----------
    anio_minimo:
        Año mínimo aceptado según la fecha del movimiento. Por defecto es 2026.
        Los registros anteriores se excluyen antes de validar Matrícula o importes,
        para que el histórico no afecte ni bloquee el reporte actual.
    """
    columnas_salida = [
        "ID_MOVIMIENTO", "FECHA", "CLAVE_PLANTEL", "MATRICULA",
        "NOMBRE_ORIGINAL", "REFERENCIA_GLOBAL", "PAGO_CUOTA", "PAGO_EE",
    ]

    if global_df.empty:
        return pd.DataFrame(columns=columnas_salida)

    if not isinstance(anio_minimo, int) or anio_minimo < 2000:
        raise ValueError("anio_minimo debe ser un año válido, por ejemplo 2026.")

    columnas = list(global_df.columns)
    columna_fecha = _resolver_columna(columnas, "Fecha")
    columna_matricula = _resolver_columna(columnas, "Matrícula")
    columna_nombre = _resolver_columna(columnas, "Nombre(s)")
    columna_ee = _resolver_columna(columnas, "OTROS INGRESOS (ENERGIA ELEC)")

    # NÚMERO sirve como referencia humana; no se usa para calcular pagos ni como llave única.
    try:
        columna_referencia = _resolver_columna(columnas, "NÚMERO")
    except ValueError:
        columna_referencia = None

    columnas_cuota = [
        columna
        for columna in columnas
        if "CUOTA RECUPERACION" in _normalizar_texto(columna)
    ]
    if not columnas_cuota:
        raise ValueError("GLOBAL no contiene columnas de CUOTA RECUPERACION.")

    base = global_df.copy()
    nombres = base[columna_nombre].fillna("").astype(str)
    nombres_normalizados = nombres.map(_normalizar_texto)

    es_tienda = nombres_normalizados.str.contains("TIEND", regex=False, na=False)
    es_excepcion = pd.Series(False, index=base.index)
    for excepcion in EXCEPCIONES_TIENDA_POR_NOMBRE:
        es_excepcion = es_excepcion | nombres_normalizados.str.contains(
            excepcion,
            regex=False,
            na=False,
        )

    tiendas = base.loc[es_tienda | es_excepcion].copy()

    if tiendas.empty:
        return pd.DataFrame(columns=columnas_salida)

    tiendas["FECHA"] = pd.to_datetime(tiendas[columna_fecha], errors="coerce")
    if tiendas["FECHA"].isna().any():
        filas = tiendas.index[tiendas["FECHA"].isna()].tolist()[:5]
        raise ValueError(f"Hay movimientos de tienda sin FECHA válida. Filas de GLOBAL: {filas}")

    # El GLOBAL contiene histórico desde 2025. Se excluye antes de continuar con
    # Matrícula e importes para que los movimientos anteriores nunca se apliquen
    # al periodo administrado por la V3.
    tiendas = tiendas.loc[tiendas["FECHA"].dt.year >= anio_minimo].copy()
    if tiendas.empty:
        return pd.DataFrame(columns=columnas_salida)

    tiendas["MATRICULA"] = tiendas[columna_matricula].fillna("").astype(str).str.strip().str.upper()
    tiendas["CLAVE_PLANTEL"] = tiendas["MATRICULA"].str[:3]
    claves_invalidas = ~tiendas["CLAVE_PLANTEL"].str.fullmatch(r"[A-Z0-9]{3}", na=False)
    if claves_invalidas.any():
        ejemplos = tiendas.loc[claves_invalidas, ["MATRICULA", columna_nombre]].head(5).to_dict("records")
        raise ValueError(f"Hay movimientos de tienda sin una CLAVE_PLANTEL válida en Matrícula: {ejemplos}")

    importes_cuota = pd.DataFrame(
        {str(columna): _a_importe(tiendas[columna], str(columna)) for columna in columnas_cuota},
        index=tiendas.index,
    )
    tiendas["PAGO_CUOTA"] = importes_cuota.sum(axis=1)
    tiendas["PAGO_EE"] = _a_importe(tiendas[columna_ee], str(columna_ee))

    if (tiendas[["PAGO_CUOTA", "PAGO_EE"]] < 0).any().any():
        raise ValueError("GLOBAL contiene pagos negativos en movimientos de tienda.")

    tiendas["NOMBRE_ORIGINAL"] = tiendas[columna_nombre].fillna("").astype(str).str.strip()
    tiendas["REFERENCIA_GLOBAL"] = (
        tiendas[columna_referencia].astype("string").fillna("").astype(str).str.strip()
        if columna_referencia is not None
        else ""
    )
    tiendas["ID_MOVIMIENTO"] = [f"GLOBAL-{indice}" for indice in tiendas.index]

    # Los renglones de tienda sin pago de cuota ni EE no afectan el motor.
    movimientos = tiendas[(tiendas["PAGO_CUOTA"] > 0) | (tiendas["PAGO_EE"] > 0)].copy()

    salida = movimientos[columnas_salida].sort_values(["FECHA", "ID_MOVIMIENTO"]).reset_index(drop=True)
    return salida


def separar_movimientos_por_catalogo(
    movimientos: pd.DataFrame,
    claves_activas: set[str] | list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa los movimientos reconocidos de las claves que no están activas en el catálogo.

    Los no reconocidos no se descartan en silencio: se devuelven para revisión.
    """
    claves = {str(clave).strip().upper() for clave in claves_activas}
    validos = movimientos[movimientos["CLAVE_PLANTEL"].isin(claves)].copy()
    no_reconocidos = movimientos[~movimientos["CLAVE_PLANTEL"].isin(claves)].copy()
    return validos.reset_index(drop=True), no_reconocidos.reset_index(drop=True)
