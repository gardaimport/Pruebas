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
    st.info("Mantén aquí tu sección 1 actual funcional.")

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

        # =================================================
        # CARGA
        # =================================================
        df_enc = limpiar_columnas(pd.read_excel(f_enc, dtype=str))
        df_ped = limpiar_columnas(pd.read_excel(f_ped, dtype=str))
        df_mov = limpiar_columnas(pd.read_excel(f_mov, dtype=str))

        # =================================================
        # NUMÉRICOS
        # =================================================
        df_enc["Cantidad"] = pd.to_numeric(
            df_enc["Cantidad"],
            errors="coerce"
        ).fillna(0)

        df_mov["Cantidad"] = pd.to_numeric(
            df_mov["Cantidad"],
            errors="coerce"
        ).fillna(0)

        # =================================================
        # SOLO ENTRADAS POSITIVAS
        # =================================================
        df_mov = df_mov[
            df_mov["Cantidad"] > 0
        ].copy()

        # =================================================
        # FECHA SIMPLE
        # =================================================
        if "Fecha caducidad" in df_mov.columns:
            df_mov["Fecha caducidad"] = pd.to_datetime(
                df_mov["Fecha caducidad"],
                errors="coerce"
            ).dt.strftime("%d/%m/%Y")

        # =================================================
        # ENCARGOS + PEDIDOS
        # =================================================
        paso1 = pd.merge(
            df_enc,
            df_ped[
                ["Nº", "Nº de albarán"]
            ],
            left_on="Nº Pedido compra",
            right_on="Nº",
            how="left"
        )

        # =================================================
        # + MOVIMIENTOS
        # =================================================
        final = pd.merge(
            paso1,
            df_mov,
            left_on=["Nº de albarán", "Nº producto"],
            right_on=["Nº documento", "Nº producto"],
            how="inner",
            suffixes=("_enc", "_mov")
        )

        # =================================================
        # RESULTADO BASE
        # =================================================
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

        resultado = resultado.sort_values(
            by=["Referencia", "Comercial"]
        )

        # =================================================
        # VISUAL
        # =================================================
        st.subheader("📋 Resultado")

        for ref, bloque in resultado.groupby("Referencia"):

            descripcion = bloque["Descripción"].iloc[0]

            total_enc = bloque["Cantidad Encargada"].sum()
            total_rec = bloque["Cantidad Recibida"].iloc[0]

            with st.expander(
                f"📦 {ref} - {descripcion} | Encargado: {total_enc} | Recibido: {total_rec}"
            ):

                if total_rec < total_enc:

                    st.warning(
                        "Se ha recibido menos cantidad de la solicitada."
                    )

                    mostrar = bloque[
                        [
                            "Comercial",
                            "Cantidad Encargada"
                        ]
                    ]

                else:

                    mostrar = bloque[
                        [
                            "Comercial",
                            "Cantidad Encargada"
                        ]
                    ].copy()

                    mostrar["Asignado"] = mostrar[
                        "Cantidad Encargada"
                    ]

                st.dataframe(
                    mostrar,
                    use_container_width=True,
                    hide_index=True
                )

        # =================================================
        # PREPARAR EXCEL FINAL
        # =================================================
        filas_excel = []

        for ref, bloque in resultado.groupby("Referencia"):

            total_enc = bloque["Cantidad Encargada"].sum()
            total_rec = bloque["Cantidad Recibida"].iloc[0]

            if total_rec < total_enc:
                estado = f"RECIBIDO MENOS ({total_rec} de {total_enc})"
            elif total_rec == total_enc:
                estado = "COMPLETO"
            else:
                estado = f"RECIBIDO DE MÁS ({total_rec} de {total_enc})"

            temp = bloque.copy()

            temp["Total Encargado"] = total_enc
            temp["Total Recibido"] = total_rec
            temp["Estado"] = estado

            filas_excel.append(temp)

        excel_final = pd.concat(
            filas_excel,
            ignore_index=True
        )

        # =================================================
        # DESCARGA
        # =================================================
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            excel_final.to_excel(
                writer,
                index=False,
                sheet_name="Entradas"
            )

        st.download_button(
            "📥 Descargar Excel",
            data=output.getvalue(),
            file_name=f"Entradas_Comercial_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.info("Sube los 3 archivos para comenzar.")
