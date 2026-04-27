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
# TRAZABILIDAD LOTES
# =====================================================
if seccion == "📦 Trazabilidad lotes":

    st.title("📦 Sistema de Trazabilidad por Lotes")

    st.sidebar.header("Subir archivos")

    f_encargos = st.sidebar.file_uploader(
        "1. Encargos",
        type=["xlsx"],
        key="enc1"
    )

    f_cal = st.sidebar.file_uploader(
        "2. Relación CAL",
        type=["xlsx"],
        key="cal1"
    )

    f_movs = st.sidebar.file_uploader(
        "3. Movimientos",
        type=["xlsx"],
        key="mov1"
    )

    if f_encargos and f_cal and f_movs:

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
                "Nº lote": str,
                "Cód. procedencia mov.": str
            }
        )

        # LIMPIEZA
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

        # =====================================
        # VENTAS
        # negativo = venta
        # positivo = devolución
        # =====================================
        ventas = df_mov[
            df_mov["Tipo movimiento"] == "Venta"
        ].copy()

        ventas = pd.merge(
            ventas,
            df_clientes[
                ["Nº", "Alias", "Cód. vendedor"]
            ],
            left_on="Cód. procedencia mov.",
            right_on="Nº",
            how="left"
        )

        ventas = ventas.rename(columns={
            "Alias": "Alias_Cliente_Venta",
            "Nº": "Nº_Cliente_Venta",
            "Cód. vendedor": "Vendedor_Que_Vendió",
            "Fecha registro": "Fecha_Venta"
        })

        ventas["Cant_Venta"] = ventas["Cantidad"].apply(
            lambda x: abs(x) if x < 0 else 0
        )

        ventas["Cant_Devolucion"] = ventas["Cantidad"].apply(
            lambda x: x if x > 0 else 0
        )

        # =====================================
        # ENCARGOS -> CAL
        # =====================================
        paso1 = pd.merge(
            df_enc[
                [
                    "Cód. vendedor",
                    "Nº Pedido compra",
                    "Descripción",
                    "Cantidad",
                    "Alias"
                ]
            ],
            df_cal[
                [
                    "Nº",
                    "Nº de albarán"
                ]
            ],
            left_on="Nº Pedido compra",
            right_on="Nº",
            how="left"
        ).rename(columns={
            "Cantidad": "Cant_Encargada",
            "Alias": "Nombre_Encargo",
            "Nº de albarán": "CAL_Entrada",
            "Cód. vendedor": "Vendedor_Encargo"
        })

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

        df_final = pd.merge(
            paso1,
            entradas,
            left_on="CAL_Entrada",
            right_on="Nº documento",
            how="left"
        ).drop_duplicates()

        # =====================================
        # VISUAL LOTES
        # =====================================
        st.subheader("📦 Resultado por lotes")

        for lote, df_lote in df_final.groupby("Nº lote"):

            if pd.isna(lote):
                continue

            ventas_lote = ventas[
                ventas["Nº lote"] == lote
            ]

            total_enc = df_lote["Cant_Encargada"].sum()

            total_vendido = ventas_lote["Cant_Venta"].sum()
            total_devuelto = ventas_lote["Cant_Devolucion"].sum()

            neto_vendido = total_vendido - total_devuelto

            pendiente = total_enc - neto_vendido

            if neto_vendido == 0:
                estado = "🔴 SIN VENDER"
            elif pendiente > 0:
                estado = "🟡 PARCIAL"
            elif pendiente == 0:
                estado = "🟢 COMPLETO"
            else:
                estado = "⚠️ SOBREVENTA"

            cad = "Sin fecha"

            if not df_lote["Fecha caducidad"].dropna().empty:
                cad = df_lote["Fecha caducidad"].dropna().iloc[0]

            titulo = f"📦 LOTE {lote} | Cad: {cad} | {estado}"

            with st.expander(titulo):

                st.markdown(f"""
                **Entradas:** {total_enc}  
                **Ventas:** {total_vendido}  
                **Devoluciones:** {total_devuelto}  
                **Neto vendido:** {neto_vendido}  
                **Pendiente:** {pendiente}
                """)

                st.markdown("### 📥 Encargos")

                for vendedor, bloque in df_lote.groupby("Vendedor_Encargo"):
                    cantidad = bloque["Cant_Encargada"].sum()

                    st.markdown(
                        f"- Comercial **{vendedor}** pidió **{cantidad} uds**"
                    )

                st.markdown("### 💰 Movimientos")

                if ventas_lote.empty:
                    st.write("Sin movimientos.")
                else:
                    for vendedor, bloque in ventas_lote.groupby("Vendedor_Que_Vendió"):

                        st.markdown(f"**Comercial {vendedor}**")

                        for _, row in bloque.iterrows():

                            if row["Cantidad"] < 0:
                                txt = f"🔴 Venta {abs(row['Cantidad'])} uds"
                            else:
                                txt = f"🟢 Devolución {row['Cantidad']} uds"

                            st.write(
                                f"- {row['Alias_Cliente_Venta']} | {txt} | {row['Fecha_Venta']}"
                            )

# =====================================================
# SECCIÓN 2
# ENTRADAS VS ENCARGOS (CORREGIDA)
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

        # LIMPIEZA
        df_enc["Cantidad"] = pd.to_numeric(
            df_enc["Cantidad"],
            errors="coerce"
        ).fillna(0)

        df_mov["Cantidad"] = pd.to_numeric(
            df_mov["Cantidad"],
            errors="coerce"
        ).fillna(0)

        # SOLO COMPRAS
        compras = df_mov[
            df_mov["Tipo movimiento"] == "Compra"
        ].copy()

        # ENCARGOS -> CAL
        paso1 = pd.merge(
            df_enc,
            df_cal[
                [
                    "Nº",
                    "Nº de albarán"
                ]
            ],
            left_on="Nº Pedido compra",
            right_on="Nº",
            how="left"
        )

        # CAL -> MOVIMIENTOS
        final = pd.merge(
            paso1,
            compras,
            left_on="Nº de albarán",
            right_on="Nº documento",
            how="left"
        )

        # =====================================
        # DETECTAR COLUMNA PRODUCTO
        # =====================================
        posibles_producto = [
            "Nº producto_x",
            "Nº producto",
            "Nº producto_y",
            "Producto",
            "Referencia",
            "Cod producto",
            "Código producto"
        ]

        col_producto = None

        for col in posibles_producto:
            if col in final.columns:
                col_producto = col
                break

        if col_producto is None:
            st.error("No se encontró columna producto")
            st.write(final.columns.tolist())
            st.stop()

        # =====================================
        # DETECTAR DESCRIPCIÓN
        # =====================================
        posibles_desc = [
            "Descripción",
            "Descripcion",
            "Producto",
            "Nombre producto"
        ]

        col_desc = None

        for col in posibles_desc:
            if col in final.columns:
                col_desc = col
                break

        if col_desc is None:
            col_desc = col_producto

        # =====================================
        # GROUPBY SIN DUPLICADOS
        # =====================================
        cols_group = [col_producto]

        if col_desc != col_producto:
            cols_group.append(col_desc)

        cols_group.append("Cód. vendedor")

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

        if col_desc not in resumen.columns:
            resumen["Descripción"] = resumen[col_producto]

        resumen = resumen.rename(columns={
            col_producto: "Referencia",
            col_desc: "Descripción",
            "Cód. vendedor": "Comercial"
        })

        resumen = resumen.sort_values(
            by=["Referencia", "Comercial"]
        )

        # =====================================
        # VISUAL
        # =====================================
        st.subheader("📋 Resultado")

        st.dataframe(
            resumen,
            use_container_width=True,
            hide_index=True
        )

        # =====================================
        # TOTALES
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
        # DESCARGA EXCEL
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
            file_name="Entradas_vs_Encargos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.info("Sube los 3 archivos.")
