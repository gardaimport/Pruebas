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
    ruta = "Clientes.xlsx"

    if os.path.exists(ruta):
        try:
            return pd.read_excel(
                ruta,
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
# MENÚ
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
# (la dejamos simple para no tocar tu parte funcional)
# =====================================================
if seccion == "📦 Trazabilidad lotes":

    st.title("📦 Sistema de Trazabilidad por Lotes")
    st.info("Mantén aquí tu sección 1 funcional actual.")

# =====================================================
# SECCIÓN 2 CORREGIDA REAL
# PRODUCTOS DESGLOSADOS POR COMERCIAL
# =====================================================
elif seccion == "📥 Entradas vs Encargos":

    st.title("📥 Productos entrados desglosados por Comercial")

    st.sidebar.header("Subir archivos")

    f_encargos = st.sidebar.file_uploader(
        "1. Encargos",
        type=["xlsx"],
        key="enc2"
    )

    f_cal = st.sidebar.file_uploader(
        "2. Archivo CAL",
        type=["xlsx"],
        key="cal2"
    )

    f_movs = st.sidebar.file_uploader(
        "3. Movimientos",
        type=["xlsx"],
        key="mov2"
    )

    if f_encargos and f_cal and f_movs:

        # =================================================
        # CARGA
        # =================================================
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
                "Nº documento": str,
                "Nº producto": str
            }
        )

        # =================================================
        # LIMPIEZA
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
        # SOLO ENTRADAS
        # =================================================
        compras = df_mov[
            df_mov["Tipo movimiento"] == "Compra"
        ].copy()

        # =================================================
        # ENCARGOS -> CAL
        # =================================================
        paso1 = pd.merge(
            df_enc,
            df_cal[
                ["Nº", "Nº de albarán"]
            ],
            left_on="Nº Pedido compra",
            right_on="Nº",
            how="left"
        )

        # =================================================
        # CAL -> MOVIMIENTOS
        # =================================================
        final = pd.merge(
            paso1,
            compras,
            left_on="Nº de albarán",
            right_on="Nº documento",
            how="left"
        )

        # =================================================
        # DESCRIPCIÓN BUENA
        # Preferimos la del archivo encargos
        # =================================================
        col_desc = "Descripción"

        if col_desc not in final.columns:
            final["Descripción"] = ""

        # =================================================
        # REFERENCIA
        # =================================================
        col_ref = None

        for c in [
            "Nº producto_x",
            "Nº producto",
            "Nº producto_y",
            "Referencia"
        ]:
            if c in final.columns:
                col_ref = c
                break

        if col_ref is None:
            st.error("No se encontró referencia producto.")
            st.write(final.columns.tolist())
            st.stop()

        # =================================================
        # RESUMEN REAL
        # UN PRODUCTO DESGLOSADO POR COMERCIAL
        # =================================================
        resumen = final.groupby(
            [
                col_ref,
                "Descripción",
                "Cód. vendedor"
            ],
            dropna=False
        ).agg(
            Cantidad_Encargada=("Cantidad_x", "sum"),
            Cantidad_Entrada=("Cantidad_y", "sum")
        ).reset_index()

        resumen["Cantidad_Entrada"] = resumen[
            "Cantidad_Entrada"
        ].fillna(0)

        resumen["Diferencia"] = (
            resumen["Cantidad_Entrada"] -
            resumen["Cantidad_Encargada"]
        )

        resumen = resumen.rename(columns={
            col_ref: "Referencia",
            "Cód. vendedor": "Comercial"
        })

        # =================================================
        # ORDEN
        # =================================================
        resumen = resumen[
            [
                "Referencia",
                "Descripción",
                "Comercial",
                "Cantidad_Encargada",
                "Cantidad_Entrada",
                "Diferencia"
            ]
        ]

        resumen = resumen.sort_values(
            by=["Referencia", "Comercial"]
        )

        # =================================================
        # VISUAL
        # =================================================
        st.subheader("📋 Resultado")

        for ref, bloque in resumen.groupby("Referencia"):

            desc = bloque["Descripción"].iloc[0]

            with st.expander(
                f"📦 {ref} - {desc}"
            ):

                st.dataframe(
                    bloque.drop(
                        columns=["Referencia", "Descripción"]
                    ),
                    use_container_width=True,
                    hide_index=True
                )

        # =================================================
        # TABLA COMPLETA
        # =================================================
        st.subheader("📄 Tabla completa")

        st.dataframe(
            resumen,
            use_container_width=True,
            hide_index=True
        )

        # =================================================
        # DESCARGA
        # =================================================
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            resumen.to_excel(
                writer,
                index=False,
                sheet_name="Resumen"
            )

        st.download_button(
            "📥 Descargar Excel",
            data=output.getvalue(),
            file_name=f"Productos_por_Comercial_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.info("Sube los 3 archivos.")
