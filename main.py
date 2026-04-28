import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# =====================================================
# CONFIGURACIÓN
# =====================================================
st.set_page_config(
    page_title="Sistema de Trazabilidad",
    layout="wide"
)

# =====================================================
# FUNCIONES
# =====================================================
def limpiar_columnas(df):
    df.columns = df.columns.astype(str).str.strip()
    return df

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
# =====================================================
# SECCIÓN 1 ORIGINAL RESTAURADA
# =====================================================
# =====================================================
if seccion == "📦 Trazabilidad por Lotes":

    st.title("📦 Sistema de Trazabilidad por Lotes")

    # -------------------------------------------------
    # SUBIDA ARCHIVOS (COMO ORIGINAL)
    # -------------------------------------------------
    st.sidebar.header("📂 Subir archivos")

    f_encargos = st.sidebar.file_uploader(
        "1. Encargos registrados",
        type=["xlsx"],
        key="file1"
    )

    f_cal = st.sidebar.file_uploader(
        "2. Archivo ENCARGOS/CAL",
        type=["xlsx"],
        key="file2"
    )

    f_movs = st.sidebar.file_uploader(
        "3. Archivo movimiento producto",
        type=["xlsx"],
        key="file3"
    )

    # -------------------------------------------------
    # SI HAY ARCHIVOS
    # -------------------------------------------------
    if f_encargos is not None and f_cal is not None and f_movs is not None:

        df_enc = limpiar_columnas(
            pd.read_excel(f_encargos, dtype=str)
        )

        df_cal = limpiar_columnas(
            pd.read_excel(f_cal, dtype=str)
        )

        df_mov = limpiar_columnas(
            pd.read_excel(f_movs, dtype=str)
        )

        # =============================================
        # NUMÉRICOS
        # =============================================
        df_enc["Cantidad"] = pd.to_numeric(
            df_enc["Cantidad"],
            errors="coerce"
        ).fillna(0)

        df_mov["Cantidad"] = pd.to_numeric(
            df_mov["Cantidad"],
            errors="coerce"
        ).fillna(0)

        # =============================================
        # FECHAS
        # =============================================
        for col in ["Fecha registro", "Fecha caducidad"]:
            if col in df_mov.columns:
                df_mov[col] = pd.to_datetime(
                    df_mov[col],
                    errors="coerce"
                ).dt.strftime("%d/%m/%Y")

        # =============================================
        # VENTAS
        # =============================================
        ventas = df_mov[
            df_mov["Tipo movimiento"] == "Venta"
        ].copy()

        ventas["Cant_Venta"] = ventas["Cantidad"].apply(
            lambda x: abs(x) if x < 0 else 0
        )

        ventas["Cant_Devolucion"] = ventas["Cantidad"].apply(
            lambda x: x if x > 0 else 0
        )

        # =============================================
        # ENCARGOS + ALBARÁN
        # =============================================
        paso1 = pd.merge(
            df_enc,
            df_cal[
                ["Nº", "Nº de albarán"]
            ],
            left_on="Nº Pedido compra",
            right_on="Nº",
            how="left"
        )

        # =============================================
        # ENTRADAS
        # =============================================
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

        # =============================================
        # VISUAL
        # =============================================
        st.subheader("📋 Resultado por lotes")

        for lote, bloque in final.groupby("Nº lote"):

            if pd.isna(lote):
                continue

            total_enc = bloque["Cantidad"].sum()

            ventas_lote = ventas[
                ventas["Nº lote"] == lote
            ]

            total_vendido = ventas_lote["Cant_Venta"].sum()
            total_dev = ventas_lote["Cant_Devolucion"].sum()

            neto = total_vendido - total_dev
            pendiente = total_enc - neto

            cad = "Sin fecha"

            if not bloque["Fecha caducidad"].dropna().empty:
                cad = bloque["Fecha caducidad"].dropna().iloc[0]

            with st.expander(
                f"📦 Lote {lote} | Cad: {cad}"
            ):

                st.markdown(f"""
                **Entrado:** {total_enc}  
                **Vendido:** {total_vendido}  
                **Devuelto:** {total_dev}  
                **Pendiente:** {pendiente}
                """)

                st.markdown("### 📥 Encargado por comerciales")

                resumen = bloque.groupby(
                    "Cód. vendedor"
                )["Cantidad"].sum().reset_index()

                resumen.columns = [
                    "Comercial",
                    "Cantidad"
                ]

                st.dataframe(
                    resumen,
                    use_container_width=True,
                    hide_index=True
                )

        # =============================================
        # DESCARGA
        # =============================================
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            final.to_excel(
                writer,
                index=False,
                sheet_name="Trazabilidad"
            )

        st.download_button(
            "📥 Descargar Excel",
            data=output.getvalue(),
            file_name=f"Trazabilidad_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.info("Sube los 3 archivos para comenzar.")

# =====================================================
# =====================================================
# SECCIÓN 2
# =====================================================
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

        df_enc = limpiar_columnas(pd.read_excel(f_enc, dtype=str))
        df_ped = limpiar_columnas(pd.read_excel(f_ped, dtype=str))
        df_mov = limpiar_columnas(pd.read_excel(f_mov, dtype=str))

        df_enc["Cantidad"] = pd.to_numeric(
            df_enc["Cantidad"],
            errors="coerce"
        ).fillna(0)

        df_mov["Cantidad"] = pd.to_numeric(
            df_mov["Cantidad"],
            errors="coerce"
        ).fillna(0)

        df_mov = df_mov[
            df_mov["Cantidad"] > 0
        ].copy()

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

        resultado.columns = [
            "Referencia",
            "Descripción",
            "Cantidad Encargada",
            "Cantidad Recibida",
            "Comercial",
            "Fecha caducidad"
        ]

        st.subheader("📋 Resultado")

        for ref, bloque in resultado.groupby("Referencia"):

            desc = bloque["Descripción"].iloc[0]
            total_enc = bloque["Cantidad Encargada"].sum()
            total_rec = bloque["Cantidad Recibida"].iloc[0]

            with st.expander(
                f"📦 {ref} - {desc} | Encargado: {total_enc} | Recibido: {total_rec}"
            ):

                if total_rec < total_enc:
                    st.warning(
                        "Recibido menos cantidad que la encargada."
                    )

                mostrar = bloque[
                    [
                        "Comercial",
                        "Cantidad Encargada"
                    ]
                ]

                st.dataframe(
                    mostrar,
                    use_container_width=True,
                    hide_index=True
                )

    else:
        st.info("Sube los 3 archivos para comenzar.")
