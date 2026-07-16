"""Aplicación Streamlit del Sistema de Tiendas Escolares CECyTEA V3.

La app no contiene reglas de negocio: usa el motor V3 validado.
El usuario carga un GLOBAL y un Machote V3; los archivos se procesan sólo
para generar el reporte de la sesión y no se escriben al repositorio.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pandas as pd
import streamlit as st

from exportador_excel_v3 import exportar_excel_v3
from lector_global import leer_global
from motor_v3 import cargar_machote
from procesador_v3 import procesar_periodo
from reportes_v3 import generar_reportes


NOMBRE_APP = "Sistema de Control de Tiendas Escolares"
VERSION_APP = "V3.1.2"
BASE_DIR = Path(__file__).resolve().parent
MACHOTE_OFICIAL = BASE_DIR / "datos" / "Machote_Tarifas_CECYTEA_V3.xlsx"
LOGO = BASE_DIR / "logo_cecytea.png"


st.set_page_config(
    page_title=NOMBRE_APP,
    page_icon="📊",
    layout="wide",
)


def _dinero(valor: Any) -> str:
    """Da formato administrativo a un importe."""
    return f"${float(valor or 0):,.2f}"


def _leer_bytes(archivo_subido) -> bytes:
    """Obtiene los bytes completos de un archivo de Streamlit."""
    archivo_subido.seek(0)
    return archivo_subido.getvalue()


def _guardar_archivo_temporal(directorio: Path, nombre: str, contenido: bytes) -> Path:
    """Guarda un archivo sólo durante la ejecución actual."""
    ruta = directorio / nombre
    ruta.write_bytes(contenido)
    return ruta


def _validar_archivo_excel(archivo_subido, etiqueta: str) -> None:
    """Valida extensión y tamaño antes de iniciar el motor."""
    if archivo_subido is None:
        raise ValueError(f"Falta cargar el archivo {etiqueta}.")
    if not archivo_subido.name.lower().endswith(".xlsx"):
        raise ValueError(f"El archivo {etiqueta} debe estar en formato .xlsx.")
    if len(_leer_bytes(archivo_subido)) == 0:
        raise ValueError(f"El archivo {etiqueta} está vacío.")


def procesar_archivos_subidos(archivo_global, archivo_machote) -> dict[str, Any]:
    """Ejecuta el flujo V3 con archivos cargados por el usuario.

    No usa caché para evitar retener datos sensibles de GLOBAL. Los archivos se
    guardan en un directorio temporal que se elimina al terminar el proceso.
    """
    _validar_archivo_excel(archivo_global, "GLOBAL")
    _validar_archivo_excel(archivo_machote, "Machote V3")

    with TemporaryDirectory(prefix="cecytea_v3_") as temporal:
        carpeta = Path(temporal)
        ruta_global = _guardar_archivo_temporal(
            carpeta,
            "GLOBAL.xlsx",
            _leer_bytes(archivo_global),
        )
        ruta_machote = _guardar_archivo_temporal(
            carpeta,
            "Machote_Tarifas_CECYTEA_V3.xlsx",
            _leer_bytes(archivo_machote),
        )
        ruta_reporte = carpeta / "Reporte_Tiendas_CECYTEA_V3.xlsx"

        # Validación del machote y lectura segura de GLOBAL.
        machote = cargar_machote(ruta_machote)
        movimientos = leer_global(ruta_global, hoja="2024", fila_encabezado=1)
        resultado = procesar_periodo(machote, movimientos)

        # Compatibilidad defensiva entre versiones: la configuración puede venir
        # del procesador o directamente del objeto MachoteV3.
        configuracion_resultado = (
            resultado.get("configuracion_periodo")
            or resultado.get("configuracion")
        )
        if not isinstance(configuracion_resultado, dict):
            configuracion_obj = getattr(machote, "configuracion", None)
            if configuracion_obj is None:
                raise ValueError(
                    "No fue posible obtener la configuración del periodo. "
                    "Verifica que el machote tenga la hoja CONFIGURACION y que "
                    "motor_v3.py y procesador_v3.py sean de la misma versión."
                )
            configuracion_resultado = {
                "PERIODO": configuracion_obj.periodo,
                "FECHA_INICIO_PAGOS": configuracion_obj.fecha_inicio_pagos,
                "FECHA_FIN_PAGOS": configuracion_obj.fecha_fin_pagos,
                "DESCRIPCION": configuracion_obj.descripcion,
            }
            resultado["configuracion_periodo"] = configuracion_resultado

        if "movimientos_fuera_periodo" not in resultado:
            resultado["movimientos_fuera_periodo"] = pd.DataFrame(
                columns=movimientos.columns
            )

        reportes = generar_reportes(resultado)
        exportar_excel_v3(resultado, ruta_reporte)

        return {
            "reporte_excel": ruta_reporte.read_bytes(),
            "resultado": resultado,
            "reportes": reportes,
            "planteles_activos": machote.planteles.copy(),
            "tarifas": machote.tarifas.copy(),
            "movimientos_leidos": movimientos.copy(),
            "configuracion": configuracion_resultado,
        }


def _aplicar_estilos() -> None:
    st.markdown(
        """
        <style>
        :root {
            --cecytea-indigo: #2B247C;
            --cecytea-lime: #CBE300;
            --cecytea-bg: #F7F8FC;
        }
        .main .block-container {
            max-width: 1200px;
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }
        .hero {
            background: linear-gradient(135deg, #ffffff 0%, #F0F1FC 100%);
            border: 1px solid #DDDFF5;
            border-radius: 18px;
            padding: 1.6rem 1.8rem;
            margin-bottom: 1rem;
            box-shadow: 0 5px 16px rgba(43,36,124,.08);
        }
        .hero h1 {
            color: #2B247C;
            font-size: 2rem;
            margin: 0 0 .35rem 0;
        }
        .hero p { color: #4B4B63; margin: 0; }
        .section-label {
            border-left: 6px solid #CBE300;
            color: #2B247C;
            font-weight: 800;
            font-size: 1.25rem;
            padding-left: .65rem;
            margin: 1.45rem 0 .65rem 0;
        }
        .small-card {
            background: #FFFFFF;
            border: 1px solid #E5E7F5;
            border-radius: 12px;
            padding: 1rem 1.1rem;
            min-height: 120px;
        }
        div.stButton > button, div.stDownloadButton > button {
            background-color: #2B247C;
            color: #FFFFFF;
            border: 0;
            border-radius: 9px;
            font-weight: 700;
        }
        div.stButton > button:hover, div.stDownloadButton > button:hover {
            background-color: #1F1A63;
            color: #FFFFFF;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _mostrar_encabezado() -> None:
    if LOGO.exists():
        col_logo, col_texto = st.columns([1, 5])
        with col_logo:
            st.image(str(LOGO), use_container_width=True)
        with col_texto:
            st.markdown(
                f"""
                <div class="hero">
                    <h1>{NOMBRE_APP}</h1>
                    <p>Genera reportes de pagos, adeudos y trazabilidad con reglas FIFO, pagos parciales y saldos a favor.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f"""
            <div class="hero">
                <h1>📊 {NOMBRE_APP}</h1>
                <p>Genera reportes de pagos, adeudos y trazabilidad con reglas FIFO, pagos parciales y saldos a favor.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _mostrar_resultados(datos: dict[str, Any]) -> None:
    resultado = datos["resultado"]
    reportes = datos["reportes"]
    adeudos = reportes["adeudos"].copy()
    tarifas = datos["tarifas"].copy()
    no_reconocidos = resultado["movimientos_no_reconocidos"].copy()
    fuera_periodo = resultado.get("movimientos_fuera_periodo", pd.DataFrame()).copy()
    configuracion = datos["configuracion"]
    periodo = str(configuracion.get("PERIODO", ""))
    fecha_inicio = pd.Timestamp(configuracion["FECHA_INICIO_PAGOS"])
    fecha_fin = pd.Timestamp(configuracion["FECHA_FIN_PAGOS"])
    descripcion = str(configuracion.get("DESCRIPCION", periodo))

    st.info(
        f"**Periodo detectado:** {periodo} · "
        f"**Rango de pagos:** {fecha_inicio.strftime('%d/%m/%Y')} "
        f"al {fecha_fin.strftime('%d/%m/%Y')} · "
        f"**Descripción:** {descripcion}"
    )

    total_planteles = len(adeudos)
    con_adeudo = int((adeudos["ADEUDO_TOTAL"] > 0.005).sum())
    al_corriente = int((adeudos["ESTADO_GENERAL"] == "AL CORRIENTE").sum())
    saldo_favor = float(adeudos["SALDO_FAVOR_TOTAL"].sum())
    adeudo_total = float(adeudos["ADEUDO_TOTAL"].sum())
    meses = sorted(pd.to_datetime(tarifas["MES"]).dt.strftime("%b-%Y").unique().tolist())

    st.markdown('<div class="section-label">Resultado del procesamiento</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Planteles activos", total_planteles)
    c2.metric("Al corriente", al_corriente)
    c3.metric("Con adeudo", con_adeudo)
    c4.metric("Adeudo total", _dinero(adeudo_total))

    dentro_periodo = len(resultado["movimientos_reconocidos"]) + len(no_reconocidos)
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Saldo a favor total", _dinero(saldo_favor))
    c6.metric("Movimientos leídos", len(datos["movimientos_leidos"]))
    c7.metric("Dentro del periodo", dentro_periodo)
    c8.metric("Fuera del periodo", len(fuera_periodo))

    st.caption(f"Meses tarifados ({len(meses)}): {', '.join(meses)}")

    if fuera_periodo.empty:
        st.success("Todos los movimientos leídos pertenecen al rango configurado.")
    else:
        st.warning(
            f"Se excluyeron {len(fuera_periodo)} movimiento(s) por estar fuera del periodo {periodo}. "
            "Quedaron disponibles en la hoja 'Fuera de Periodo' del reporte."
        )
        with st.expander("Ver movimientos fuera del periodo"):
            st.dataframe(fuera_periodo, use_container_width=True, hide_index=True)

    if no_reconocidos.empty:
        st.success("No se encontraron movimientos con claves fuera del catálogo activo.")
    else:
        st.warning(
            f"Hay {len(no_reconocidos)} movimiento(s) con una clave que no pertenece a un plantel ACTIVO. "
            "No se descartaron: quedaron en la hoja 'Movimientos por Revisar'."
        )
        with st.expander("Ver movimientos por revisar"):
            st.dataframe(no_reconocidos, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-label">Vista previa de adeudos</div>', unsafe_allow_html=True)
    vista = adeudos.copy()
    columnas_monetarias = [
        "ADEUDO_CUOTA", "ADEUDO_EE", "ADEUDO_TOTAL",
        "SALDO_FAVOR_CUOTA", "SALDO_FAVOR_EE", "SALDO_FAVOR_TOTAL",
    ]
    formato = {col: _dinero for col in columnas_monetarias if col in vista.columns}
    st.dataframe(
        vista.style.format(formato),
        use_container_width=True,
        hide_index=True,
        height=420,
    )

    with st.expander("Ver Detalle de Cobranza"):
        detalle = reportes["detalle_cobranza"].copy()
        st.dataframe(
            detalle.style.format({"ESPERADO": _dinero, "PAGADO": _dinero, "PENDIENTE": _dinero}),
            use_container_width=True,
            hide_index=True,
            height=420,
        )

    st.markdown('<div class="section-label">Descargar reporte</div>', unsafe_allow_html=True)
    st.download_button(
        label="📥 Descargar reporte Excel V3",
        data=datos["reporte_excel"],
        file_name="Reporte_Tiendas_CECYTEA_V3.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=False,
    )


def main() -> None:
    _aplicar_estilos()

    # Evita mostrar resultados conservados de una versión anterior de la app.
    if st.session_state.get("_version_app_v3") != VERSION_APP:
        st.session_state.pop("resultado_v3", None)
        st.session_state["_version_app_v3"] = VERSION_APP

    with st.sidebar:
        if LOGO.exists():
            st.image(str(LOGO), use_container_width=True)
        st.markdown("### Configuración")
        st.write(f"**Versión:** {VERSION_APP}")
        st.write("**Método:** FIFO por concepto")
        st.caption("Cuota y EE siempre se procesan por separado.")
        st.divider()
        st.markdown("#### Machote oficial")
        if MACHOTE_OFICIAL.exists():
            st.download_button(
                label="📥 Descargar machote V3",
                data=MACHOTE_OFICIAL.read_bytes(),
                file_name="Machote_Tarifas_CECYTEA_V3.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.error("No se encontró el machote oficial dentro de la carpeta datos.")

    _mostrar_encabezado()

    st.markdown('<div class="section-label">Cómo usar el sistema</div>', unsafe_allow_html=True)
    a, b, c = st.columns(3)
    with a:
        st.markdown("<div class='small-card'><b>1. Descarga y actualiza el machote</b><br><br>Captura configuración del periodo, planteles, estatus, meses, cuotas, EE y saldos iniciales.</div>", unsafe_allow_html=True)
    with b:
        st.markdown("<div class='small-card'><b>2. Sube GLOBAL y el machote</b><br><br>GLOBAL se lee por la clave de los primeros tres caracteres de Matrícula.</div>", unsafe_allow_html=True)
    with c:
        st.markdown("<div class='small-card'><b>3. Genera el reporte</b><br><br>El archivo final incluirá Ejecutivo, Adeudos, Detalle y Trazabilidad.</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-label">Cargar archivos</div>', unsafe_allow_html=True)
    col_global, col_machote = st.columns(2)
    with col_global:
        archivo_global = st.file_uploader(
            "Archivo GLOBAL (.xlsx)",
            type=["xlsx"],
            key="archivo_global",
            help="Debe contener la hoja '2024' y los encabezados de GLOBAL.",
        )
    with col_machote:
        archivo_machote = st.file_uploader(
            "Machote V3 actualizado (.xlsx)",
            type=["xlsx"],
            key="archivo_machote",
            help="Usa el machote descargado en esta página. El sistema detecta el periodo desde CONFIGURACION y los meses desde TARIFAS.",
        )

    st.info(
        "Los archivos cargados se usan únicamente para generar el reporte de esta sesión. "
        "No se guardan en GitHub ni sustituyen el machote oficial."
    )

    generar = st.button("🚀 Generar reporte V3", type="primary", disabled=not (archivo_global and archivo_machote))
    if generar:
        try:
            with st.spinner("Validando archivos y aplicando pagos por FIFO..."):
                datos = procesar_archivos_subidos(archivo_global, archivo_machote)
            st.session_state["resultado_v3"] = datos
            st.success("Reporte generado correctamente.")
        except Exception as error:
            st.session_state.pop("resultado_v3", None)
            st.error(f"No fue posible generar el reporte: {error}")
            with st.expander("Ayuda para corregir el archivo"):
                st.markdown(
                    """
                    Revisa que:
                    - GLOBAL tenga la hoja `2024`.
                    - El machote tenga las hojas `CONFIGURACION`, `PLANTELES`, `TARIFAS` y `SALDOS_INICIALES`.
                    - Todo plantel con estatus `ACTIVA` tenga clave y tarifas.
                    - Cuota, EE y saldos sean importes numéricos no negativos.
                    - No existan dos filas de tarifas para la misma clave y el mismo mes.
                    """
                )

    if "resultado_v3" in st.session_state:
        _mostrar_resultados(st.session_state["resultado_v3"])
    else:
        st.caption("Carga ambos archivos y presiona “Generar reporte V3” para comenzar.")

    st.markdown(
        f"<p style='text-align:center; color:#616161; margin-top:2rem;'>CECyTEA · {NOMBRE_APP} · {VERSION_APP}</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
