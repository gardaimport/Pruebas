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
# CARGA MAESTRO CLIENTES
# =====================================================
@st.cache_data
def cargar_maestro():
    archivo = "Clientes.xlsx"

    if os.path.exists(archivo):
        try:
            return pd.read_excel(
                archivo,
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
        "📦 Trazabilidad por Lotes",
        "📥 Entradas por Comercial"
    ]
)

# =====================================================
# SECCIÓN 1
# TRAZABILIDAD LOTES
# =====================================================
if seccion == "📦 Trazabilidad por Lotes":

    st.title("📦 Sistema de Trazabilidad por Lotes")

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
                "Nº lote": str,
                "Cód. procedencia mov.": str,
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

        for col in ["Fecha registro", "Fecha caducidad"]:
            if col in df_mov.columns:
                df_mov[col] = pd.to_datetime(
                    df_mov[col],
                    errors="coerce"
                ).dt.strftime("%d/%m/%Y")

        # =================================================
        # VENTAS
        # =================================================
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

        # =================================================
        # ENCARGOS -> CAL
        # =================================================
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

        # =================================================
        # VISUAL
        # =================================================
        st.subheader("📋 Resultado por lotes")

        for lote, df_lote in df_final.groupby("Nº lote"):

            if pd.isna(lote):
                continue

            ventas_lote = ventas[
                ventas["Nº lote"] == lote
            ]

            total_enc = df_lote["Cant_Encargada"].sum()

            total_vendido = ventas_lote["Cant_Venta"].sum()
            total_devuelto = ventas_lote["Cant_Devolucion"].sum()

            neto = total_vendido - total_devuelto
            pendiente = total_enc - neto

            if neto == 0:
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

            with st.expander(
                f"📦 LOTE {lote} | Cad: {cad} | {estado}"
            ):

                st.markdown(f"""
                **Entradas:** {total_enc}  
                **Ventas:** {total_vendido}  
                **Devoluciones:** {total_devuelto}  
                **Neto vendido:** {neto}  
                **Pendiente:** {pendiente}
                """)

                st.markdown("### 📥 Encargos")

                for vendedor, bloque in df_lote.groupby("Vendedor_Encargo"):
                    cantidad = bloque["Cant_Encargada"].sum()
                    st.write(
                        f"Comercial {vendedor}: {cantidad} uds"
                    )

                st.markdown("### 💰 Movimientos")

                if ventas_lote.empty:
                    st.write("Sin movimientos.")
                else:
                    for _, row in ventas_lote.iterrows():

                        if row["Cantidad"] < 0:
                            mov = f"Venta {abs(row['Cantidad'])}"
                        else:
                            mov = f"Devolución {row['Cantidad']}"

                        st.write(
                            f"{row['Alias_Cliente_Venta']} | {mov} | {row['Fecha_Venta']}"
                        )

        # =================================================
        # DESCARGA
        # =================================================
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df_final.to_excel(
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
# SECCIÓN 2
# ENTRADAS POR COMERCIAL
# =====================================================
elif seccion == "📥 Entradas por Comercial":

    st.title("📥 Reparto de Entradas por Comercial")

    st.sidebar.header("📂 Subir archivos")

    f_enc = st.sidebar.file_uploader(
        "1. Encargos registrados",
        type=["xlsx"],
        key="sec2_a"
    )

    f_ped = st.sidebar.file_uploader(
        "2. Pedidos Compra",
        type=["xlsx"],
        key="sec2_b"
    )

    f_mov = st.sidebar.file_uploader(
        "3. Movs. Productos",
        type=["xlsx"],
        key="sec2_c"
    )

    if f_enc and f_ped and f_mov:

        # =================================================
        # CARGA
        # =================================================
        df_enc = pd.read_excel(
            f_enc,
            dtype={
                "Nº producto": str,
                "Cód. vendedor": str,
                "Nº Pedido compra": str
            }
        )

        df_ped = pd.read_excel(
            f_ped,
            dtype={
                "Nº": str,
                "Nº de albarán": str
            }
        )

        df_mov = pd.read_excel(
            f_mov,
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

        # =================================================
        # ENCARGOS + PEDIDOS
        # =================================================
        paso1 = pd.merge(
            df_enc,
            df_ped[
                [
                    "Nº",
                    "Nº de albarán"
                ]
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
        # RESULTADO
        # =================================================
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

        # =================================================
        # VISUAL
        # =================================================
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

        # =================================================
        # TABLA COMPLETA
        # =================================================
        st.subheader("📄 Tabla completa")

        st.dataframe(
            resultado,
            use_container_width=True,
            hide_index=True
        )

        # =================================================
        # DESCARGA
        # =================================================
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
