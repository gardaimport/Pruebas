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
# FUNCIÓN LIMPIAR COLUMNAS
# =====================================================
def limpiar_columnas(df):
    df.columns = df.columns.astype(str).str.strip()
    return df

# =====================================================
# CARGA MAESTRO CLIENTES
# =====================================================
@st.cache_data
def cargar_maestro():
    archivo = "Clientes.xlsx"

    if os.path.exists(archivo):
        try:
            df = pd.read_excel(
                archivo,
                engine="openpyxl",
                dtype=str
            )
            return limpiar_columnas(df)
        except:
            return pd.DataFrame()

    return pd.DataFrame()


df_clientes = cargar_maestro()

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
# SECCIÓN 1
# =====================================================
if seccion == "📦 Trazabilidad por Lotes":

    st.title("📦 Sistema de Trazabilidad por Lotes")

    st.sidebar.header("📂 Subir archivos")

    f_encargos = st.sidebar.file_uploader(
        "1. Encargos registrados",
        type=["xlsx"],
        key="s1a"
    )

    f_cal = st.sidebar.file_uploader(
        "2. Archivo ENCARGOS/CAL",
        type=["xlsx"],
        key="s1b"
    )

    f_movs = st.sidebar.file_uploader(
        "3. Archivo movimiento producto",
        type=["xlsx"],
        key="s1c"
    )

    if f_encargos and f_cal and f_movs:

        df_enc = limpiar_columnas(pd.read_excel(f_encargos, dtype=str))
        df_cal = limpiar_columnas(pd.read_excel(f_cal, dtype=str))
        df_mov = limpiar_columnas(pd.read_excel(f_movs, dtype=str))

        df_enc["Cantidad"] = pd.to_numeric(
            df_enc["Cantidad"],
            errors="coerce"
        ).fillna(0)

        df_mov["Cantidad"] = pd.to_numeric(
            df_mov["Cantidad"],
            errors="coerce"
        ).fillna(0)

        for col in ["Fecha registro", "Fecha caducidad"]:
            if col in df_mov.columns:
                df_mov[col] = pd.to_datetime(
                    df_mov[col],
                    errors="coerce"
                ).dt.strftime("%d/%m/%Y")

        ventas = df_mov[
            df_mov["Tipo movimiento"] == "Venta"
        ].copy()

        ventas["Cant_Venta"] = ventas["Cantidad"].apply(
            lambda x: abs(x) if x < 0 else 0
        )

        ventas["Cant_Devolucion"] = ventas["Cantidad"].apply(
            lambda x: x if x > 0 else 0
        )

        paso1 = pd.merge(
            df_enc,
            df_cal[
                ["Nº", "Nº de albarán"]
            ],
            left_on="Nº Pedido compra",
            right_on="Nº",
            how="left"
        )

        entradas = df_mov[
            df_mov["Tipo movimiento"] == "Compra"
        ][
            [
                "Nº documento",
                "Nº lote",
                "Fecha registro",
                "Fecha caducidad"
            ]
        ].drop_duplicates()

        final = pd.merge(
            paso1,
            entradas,
            left_on="Nº de albarán",
            right_on="Nº documento",
            how="left"
        )

        st.subheader("📋 Resultado")

        for lote, bloque in final.groupby("Nº lote"):

            if pd.isna(lote):
                continue

            st.write(f"### 📦 Lote {lote}")
            st.dataframe(
                bloque,
                use_container_width=True,
                hide_index=True
            )

# =====================================================
# SECCIÓN 2
# =====================================================
elif seccion == "📥 Entradas por Comercial":

    st.title("📥 Entradas por Comercial")

    st.sidebar.header("📂 Subir archivos")

    f_enc = st.sidebar.file_uploader(
        "1. Encargos registrados",
        type=["xlsx"],
        key="s2a"
    )

    f_ped = st.sidebar.file_uploader(
        "2. Pedidos Compra",
        type=["xlsx"],
        key="s2b"
    )

    f_mov = st.sidebar.file_uploader(
        "3. Movs. Productos",
        type=["xlsx"],
        key="s2c"
    )

    if f_enc and f_ped and f_mov:

        # =============================================
        # CARGA
        # =============================================
        df_enc = limpiar_columnas(pd.read_excel(f_enc, dtype=str))
        df_ped = limpiar_columnas(pd.read_excel(f_ped, dtype=str))
        df_mov = limpiar_columnas(pd.read_excel(f_mov, dtype=str))

        # =============================================
        # VALIDACIÓN COLUMNAS
        # =============================================
        necesarias1 = [
            "Nº producto",
            "Descripción",
            "Cantidad",
            "Cód. vendedor",
            "Nº Pedido compra"
        ]

        for c in necesarias1:
            if c not in df_enc.columns:
                st.error(f"Falta columna en archivo 1: {c}")
                st.write(df_enc.columns.tolist())
                st.stop()

        necesarias2 = [
            "Nº",
            "Nº de albarán"
        ]

        for c in necesarias2:
            if c not in df_ped.columns:
                st.error(f"Falta columna en archivo 2: {c}")
                st.write(df_ped.columns.tolist())
                st.stop()

        necesarias3 = [
            "Nº documento",
            "Nº producto",
            "Descripción",
            "Cantidad"
        ]

        for c in necesarias3:
            if c not in df_mov.columns:
                st.error(f"Falta columna en archivo 3: {c}")
                st.write(df_mov.columns.tolist())
                st.stop()

        # =============================================
        # LIMPIEZA NUMÉRICA
        # =============================================
        df_enc["Cantidad"] = pd.to_numeric(
            df_enc["Cantidad"],
            errors="coerce"
        ).fillna(0)

        df_mov["Cantidad"] = pd.to_numeric(
            df_mov["Cantidad"],
            errors="coerce"
        ).fillna(0)

        # Solo entradas positivas
        df_mov = df_mov[
            df_mov["Cantidad"] > 0
        ].copy()

        # Fecha simple
        if "Fecha caducidad" in df_mov.columns:
            df_mov["Fecha caducidad"] = pd.to_datetime(
                df_mov["Fecha caducidad"],
                errors="coerce"
            ).dt.strftime("%d/%m/%Y")

        # =============================================
        # UNIÓN 1
        # =============================================
        paso1 = pd.merge(
            df_enc,
            df_ped[
                ["Nº", "Nº de albarán"]
            ],
            left_on="Nº Pedido compra",
            right_on="Nº",
            how="left"
        )

        # =============================================
        # UNIÓN 2
        # =============================================
        final = pd.merge(
            paso1,
            df_mov,
            left_on=["Nº de albarán", "Nº producto"],
            right_on=["Nº documento", "Nº producto"],
            how="inner",
            suffixes=("_enc", "_mov")
        )

        # =============================================
        # RESULTADO
        # =============================================
        resultado = final[
            [
                "Nº producto",
                "Descripción_enc",
                "Fecha caducidad",
                "Cantidad_enc",
                "Cód. vendedor",
                "Nº Pedido compra",
                "Nº de albarán"
            ]
        ].copy()

        resultado = resultado.rename(columns={
            "Nº producto": "Referencia",
            "Descripción_enc": "Descripción",
            "Cantidad_enc": "Cantidad Comercial",
            "Cód. vendedor": "Comercial",
            "Nº Pedido compra": "Pedido Compra",
            "Nº de albarán": "Albarán Entrada"
        })

        resultado = resultado.sort_values(
            by=["Referencia", "Pedido Compra", "Comercial"]
        )

        # =============================================
        # VISUAL
        # =============================================
        st.subheader("📋 Resultado")

        for ref, bloque in resultado.groupby("Referencia"):

            desc = bloque["Descripción"].iloc[0]

            with st.expander(
                f"📦 {ref} - {desc}"
            ):

                st.dataframe(
                    bloque,
                    use_container_width=True,
                    hide_index=True
                )

                total = bloque["Cantidad Comercial"].sum()

                st.success(
                    f"Total asignado: {total}"
                )

        # =============================================
        # DESCARGA
        # =============================================
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            resultado.to_excel(
                writer,
                index=False,
                sheet_name="Reparto"
            )

        st.download_button(
            "📥 Descargar Excel",
            data=output.getvalue(),
            file_name=f"Reparto_Entradas_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.info("Sube los 3 archivos para comenzar.")
