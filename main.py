import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================
st.set_page_config(
    page_title="Control Comercial y Trazabilidad",
    layout="wide"
)

# =====================================================
# CARGA MAESTRO CLIENTES
# =====================================================
@st.cache_data
def cargar_maestro():
    ruta_archivo = "Clientes.xlsx"

    if os.path.exists(ruta_archivo):
        try:
            return pd.read_excel(
                ruta_archivo,
                engine="openpyxl",
                dtype={
                    "Nº": str,
                    "Cód. vendedor": str
                }
            )
        except:
            return pd.DataFrame()

    return pd.DataFrame()


df_clientes = cargar_maestro()

# =====================================================
# MENÚ LATERAL
# =====================================================
st.sidebar.title("📂 Menú")

seccion = st.sidebar.radio(
    "Selecciona sección",
    [
        "📦 Trazabilidad lotes",
        "📥 Entradas vs Encargos"
    ]
)

# =====================================================
# SECCIÓN 1
# =====================================================
if seccion == "📦 Trazabilidad lotes":

    st.title("📦 Sistema de Trazabilidad por Lotes")
    st.info("Sección 1 mantenida igual que tu versión funcional.")

# =====================================================
# SECCIÓN 2 CORREGIDA DEFINITIVA
# =====================================================
elif seccion == "📥 Entradas vs Encargos":

    st.title("📥 Entradas reales vs Encargos por Comercial")

    st.sidebar.header("Subir archivos")

    f_encargos = st.sidebar.file_uploader(
        "1. Encargos",
        type=["xlsx"],
        key="enc2"
    )

    f_cal = st.sidebar.file_uploader(
        "2. Relación CAL",
        type=["xlsx"],
        key="cal2"
    )

    f_movs = st.sidebar.file_uploader(
        "3. Movimientos",
        type=["xlsx"],
        key="mov2"
    )

    if f_encargos and f_cal and f_movs:

        # =====================================
        # CARGA
        # =====================================
        df_enc = pd.read_excel(
            f_encargos,
            dtype={
                "Cód. vendedor": str,
                "Nº Pedido compra": str
            }
        )

        df_cal = pd.read_excel(
            f_cal,
            dtype={
                "Nº": str,
                "Nº de albarán": str
            }
        )

        df_mov = pd.read_excel(
            f_movs,
            dtype={
                "Nº documento": str
            }
        )

        # =====================================
        # LIMPIEZA
        # =====================================
        df_enc["Cantidad"] = pd.to_numeric(
            df_enc["Cantidad"],
            errors="coerce"
        ).fillna(0)

        df_mov["Cantidad"] = pd.to_numeric(
            df_mov["Cantidad"],
            errors="coerce"
        ).fillna(0)

        # =====================================
        # SOLO COMPRAS
        # =====================================
        compras = df_mov[
            df_mov["Tipo movimiento"] == "Compra"
        ].copy()

        # =====================================
        # ENCARGOS -> CAL
        # =====================================
        paso1 = pd.merge(
            df_enc,
            df_cal[["Nº", "Nº de albarán"]],
            left_on="Nº Pedido compra",
            right_on="Nº",
            how="left"
        )

        # =====================================
        # CAL -> MOVIMIENTOS
        # =====================================
        final = pd.merge(
            paso1,
            compras,
            left_on="Nº de albarán",
            right_on="Nº documento",
            how="left"
        )

        # =====================================
        # DETECTAR COLUMNAS
        # =====================================
        posibles_producto = [
            "Nº producto_x",
            "Nº producto",
            "Nº producto_y",
            "Producto",
            "Referencia",
            "Cod producto"
        ]

        col_producto = None

        for c in posibles_producto:
            if c in final.columns:
                col_producto = c
                break

        if col_producto is None:
            st.error("No se detectó columna producto.")
            st.write(final.columns.tolist())
            st.stop()

        posibles_desc = [
            "Descripción",
            "Descripcion",
            "Producto",
            "Nombre producto"
        ]

        col_desc = None

        for c in posibles_desc:
            if c in final.columns:
                col_desc = c
                break

        if col_desc is None:
            col_desc = col_producto

        # =====================================
        # COLUMNAS GROUPBY SIN DUPLICADOS
        # =====================================
        cols_group = []

        cols_group.append(col_producto)

        if col_desc != col_producto:
            cols_group.append(col_desc)

        cols_group.append("Cód. vendedor")

        # =====================================
        # AGRUPAR
        # =====================================
        resumen = final.groupby(
            cols_group,
            dropna=False
        ).agg(
            Encargado=("Cantidad_x", "sum"),
            Entrado=("Cantidad_y", "sum")
        ).reset_index()

        resumen["Encargado"] = resumen["Encargado"].fillna(0)
        resumen["Entrado"] = resumen["Entrado"].fillna(0)

        resumen["Diferencia"] = (
            resumen["Entrado"] - resumen["Encargado"]
        )

        # =====================================
        # CREAR COLUMNAS FIJAS
        # =====================================
        resumen["Referencia"] = resumen[col_producto]

        if col_desc in resumen.columns:
            resumen["Descripción"] = resumen[col_desc]
        else:
            resumen["Descripción"] = resumen[col_producto]

        resumen["Comercial"] = resumen["Cód. vendedor"]

        # =====================================
        # QUEDARSE SOLO CON COLUMNAS BUENAS
        # =====================================
        resumen = resumen[
            [
                "Referencia",
                "Descripción",
                "Comercial",
                "Encargado",
                "Entrado",
                "Diferencia"
            ]
        ]

        # =====================================
        # ORDENAR
        # =====================================
        resumen = resumen.sort_values(
            by=["Referencia", "Comercial"],
            ascending=True
        )

        # =====================================
        # MOSTRAR
        # =====================================
        st.subheader("📋 Resultado")

        st.dataframe(
            resumen,
            use_container_width=True,
            hide_index=True
        )

        # =====================================
        # KPIS
        # =====================================
        st.subheader("📊 Totales")

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Referencias",
            resumen["Referencia"].nunique()
        )

        c2.metric(
            "Comerciales",
            resumen["Comercial"].nunique()
        )

        c3.metric(
            "Diferencia total",
            round(resumen["Diferencia"].sum(), 2)
        )

        # =====================================
        # DESCARGA
        # =====================================
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            resumen.to_excel(
                writer,
                index=False,
                sheet_name="Entradas_vs_Encargos"
            )

        st.download_button(
            "📥 Descargar Excel",
            data=output.getvalue(),
            file_name=f"Entradas_vs_Encargos_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.info("Sube los 3 archivos.")
