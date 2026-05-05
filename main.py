import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# =====================================================
# CONFIGURACIÓN GENERAL
# =====================================================
st.set_page_config(
    page_title="Sistema de Trazabilidad",
    layout="wide"
)

# =====================================================
# LIMPIAR COLUMNAS
# =====================================================
def limpiar_columnas(df):
    df.columns = df.columns.astype(str).str.strip()
    return df

# =====================================================
# CARGA MAESTRO CLIENTES
# =====================================================
@st.cache_data
def cargar_maestro_clientes():
    ruta_archivo = "Clientes.xlsx"
    if os.path.exists(ruta_archivo):
        try:
            return pd.read_excel(
                ruta_archivo,
                engine='openpyxl',
                dtype={'Nº': str, 'Cód. vendedor': str}
            )
        except:
            return pd.DataFrame()
    return pd.DataFrame()

# =====================================================
# CARGA MAESTRO VENDEDORES
# =====================================================
@st.cache_data
def cargar_vendedores():
    archivo = "Vendedores.xlsx"
    if os.path.exists(archivo):
        try:
            df = pd.read_excel(archivo, dtype=str)
            df = limpiar_columnas(df)
            return df.rename(columns={
                "Código": "Cód. vendedor",
                "Nombre": "Nombre Comercial"
            })
        except:
            return pd.DataFrame()
    return pd.DataFrame()

df_clientes = cargar_maestro_clientes()
df_vendedores = cargar_vendedores()

# =====================================================
# MENÚ
# =====================================================
st.sidebar.title("📂 Menú")

seccion = st.sidebar.radio(
    "Selecciona sección",
    [
        "📦 Trazabilidad por Lotes",
        "📥 Entradas por Comercial"
    ]
)

# =====================================================
# SECCIÓN 1 (SIN CAMBIOS)
# =====================================================
if seccion == "📦 Trazabilidad por Lotes":
    st.title("🎯 Sistema de Trazabilidad: Encargos vs Ventas")
    st.info("Sección 1 intacta.")

# =====================================================
# SECCIÓN 2
# =====================================================
elif seccion == "📥 Entradas por Comercial":

    st.title("📥 Entradas por Comercial")

    st.sidebar.header("📂 Subir archivos")

    f_enc = st.sidebar.file_uploader("1. Encargos registrados", type=["xlsx"], key="s2a")
    f_ped = st.sidebar.file_uploader("2. Pedidos Compra", type=["xlsx"], key="s2b")
    f_mov = st.sidebar.file_uploader("3. Movs. Productos", type=["xlsx"], key="s2c")

    if f_enc and f_ped and f_mov:

        df_enc = limpiar_columnas(pd.read_excel(f_enc, dtype=str))
        df_ped = limpiar_columnas(pd.read_excel(f_ped, dtype=str))
        df_mov = limpiar_columnas(pd.read_excel(f_mov, dtype=str))

        df_enc["Cantidad"] = pd.to_numeric(df_enc["Cantidad"], errors="coerce").fillna(0)
        df_mov["Cantidad"] = pd.to_numeric(df_mov["Cantidad"], errors="coerce").fillna(0)

        df_mov = df_mov[df_mov["Cantidad"] > 0].copy()

        if "Fecha caducidad" in df_mov.columns:
            df_mov["Fecha caducidad"] = pd.to_datetime(
                df_mov["Fecha caducidad"],
                errors="coerce"
            ).dt.strftime("%d/%m/%Y")

        paso1 = pd.merge(
            df_enc,
            df_ped[["Nº", "Nº de albarán"]],
            left_on="Nº Pedido compra",
            right_on="Nº",
            how="left"
        )

        final = pd.merge(
            paso1,
            df_mov,
            left_on=["Nº de albarán", "Nº producto"],
            right_on=["Nº documento", "Nº producto"],
            how="inner",
            suffixes=("_enc", "_mov")
        )

        resultado = final[
            [
                "Nº producto",
                "Descripción_enc",
                "Cantidad_enc",
                "Cantidad_mov",
                "Cód. vendedor",
                "Fecha caducidad"
            ]
        ].copy()

        resultado = resultado.rename(columns={
            "Nº producto": "Referencia",
            "Descripción_enc": "Descripción",
            "Cantidad_enc": "Cantidad Encargada",
            "Cantidad_mov": "Cantidad Recibida",
            "Cód. vendedor": "Comercial"
        })

        # =====================================================
        # 🔥 AÑADIR NOMBRE DEL COMERCIAL
        # =====================================================
        if not df_vendedores.empty:

            resultado = pd.merge(
                resultado,
                df_vendedores,
                left_on="Comercial",
                right_on="Cód. vendedor",
                how="left"
            )

            resultado["Comercial"] = resultado["Nombre Comercial"].fillna(resultado["Comercial"])

            resultado = resultado.drop(columns=["Nombre Comercial", "Cód. vendedor"])

        resultado = resultado.sort_values(by=["Referencia", "Comercial"])

        # =====================================================
        # VISUAL
        # =====================================================
        st.subheader("📋 Resultado")

        for ref, bloque in resultado.groupby("Referencia"):

            descripcion = bloque["Descripción"].iloc[0]

            total_enc = bloque["Cantidad Encargada"].sum()
            total_rec = bloque["Cantidad Recibida"].sum()

            if total_rec < total_enc:
                estado_header = "🔴 RECIBIDO PARCIAL"
            elif total_rec == total_enc:
                estado_header = "🟢 RECIBIDO COMPLETO"
            else:
                estado_header = "⚠️ RECIBIDO DE MÁS"

            with st.expander(
                f"📦 {ref} - {descripcion} | {estado_header} | Encargado: {total_enc} | Recibido: {total_rec}"
            ):

                if total_rec < total_enc:
                    st.warning("Se ha recibido menos cantidad de la solicitada.")

                mostrar = bloque[["Comercial", "Cantidad Encargada"]].copy()

                st.dataframe(
                    mostrar,
                    use_container_width=True,
                    hide_index=True
                )

        # =====================================================
        # EXCEL
        # =====================================================
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            resultado.to_excel(writer, index=False, sheet_name="Entradas")

        st.download_button(
            "📥 Descargar Excel",
            data=output.getvalue(),
            file_name=f"Entradas_Comercial_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.info("Sube los 3 archivos para comenzar.")
