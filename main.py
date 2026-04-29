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
    ruta_archivo = "Clientes.xlsx"
    if os.path.exists(ruta_archivo):
        try:
            return pd.read_excel(
                ruta_archivo,
                engine='openpyxl',
                dtype={'Nº': str, 'Cód. vendedor': str}
            )
        except Exception as e:
            st.error(f"Error al abrir Clientes.xlsx: {e}")
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
# SECCIÓN 1: CÓDIGO ORIGINAL INTEGRADO
# =====================================================
if seccion == "📦 Trazabilidad por Lotes":

    st.title("🎯 Sistema de Trazabilidad: Encargos vs Ventas")

    st.sidebar.header("📂 Subir archivos")
    f_encargos = st.sidebar.file_uploader("1. Encargos", type=['xlsx'], key="s1a")
    f_cal = st.sidebar.file_uploader("2. Relación CAL", type=['xlsx'], key="s1b")
    f_movs = st.sidebar.file_uploader("3. Movimientos", type=['xlsx'], key="s1c")

    if f_encargos and f_cal and f_movs:

        df_enc = pd.read_excel(f_encargos, dtype={'Cód. vendedor': str, 'Nº Pedido compra': str})
        df_cal = pd.read_excel(f_cal, dtype={'Nº': str, 'Nº de albarán': str})
        df_mov = pd.read_excel(f_movs, dtype={
            'Nº documento': str,
            'Nº lote': str,
            'Cód. procedencia mov.': str
        })

        # =========================
        # LIMPIEZA
        # =========================
        df_enc['Cantidad'] = pd.to_numeric(df_enc['Cantidad'], errors='coerce').fillna(0)
        df_mov['Cantidad'] = pd.to_numeric(df_mov['Cantidad'], errors='coerce').fillna(0)

        for col in ['Fecha registro', 'Fecha caducidad']:
            if col in df_mov.columns:
                df_mov[col] = pd.to_datetime(df_mov[col], errors='coerce').dt.strftime('%d/%m/%Y')

        # =========================
        # VENTAS (CORREGIDO)
        # =========================
        ventas = df_mov[df_mov['Tipo movimiento'] == 'Venta'].copy()

        ventas = pd.merge(
            ventas,
            df_clientes[['Nº', 'Alias', 'Cód. vendedor']],
            left_on='Cód. procedencia mov.',
            right_on='Nº',
            how='left'
        )

        ventas = ventas.rename(columns={
            'Alias': 'Alias_Cliente_Venta',
            'Nº': 'Nº_Cliente_Venta',
            'Cód. vendedor': 'Vendedor_Que_Vendió',
            'Fecha registro': 'Fecha_Venta'
        })

        # 🔥 CLAVE: separar ventas y devoluciones
        ventas['Cant_Venta'] = ventas['Cantidad'].apply(lambda x: abs(x) if x < 0 else 0)
        ventas['Cant_Devolucion'] = ventas['Cantidad'].apply(lambda x: x if x > 0 else 0)

        # =========================
        # ENCARGOS → LOTES
        # =========================
        paso1 = pd.merge(
            df_enc[['Cód. vendedor', 'Nº Pedido compra', 'Descripción', 'Cantidad', 'Alias']],
            df_cal[['Nº', 'Nº de albarán']],
            left_on='Nº Pedido compra',
            right_on='Nº',
            how='left'
        ).rename(columns={
            'Cantidad': 'Cant_Encargada',
            'Alias': 'Nombre_Encargo',
            'Nº de albarán': 'CAL_Entrada',
            'Cód. vendedor': 'Vendedor_Encargo'
        })

        entradas = df_mov[df_mov['Tipo movimiento'] == 'Compra'][[
            'Nº documento', 'Nº lote', 'Fecha registro', 'Fecha caducidad'
        ]].drop_duplicates()

        df_final = pd.merge(
            paso1,
            entradas,
            left_on='CAL_Entrada',
            right_on='Nº documento',
            how='left'
        )

        df_final = df_final.drop_duplicates()

        # =========================
        # VISUALIZACIÓN POR LOTES
        # =========================
        st.subheader("📦 Trazabilidad visual por Lote")

        for lote, df_lote in df_final.groupby('Nº lote'):

            if pd.isna(lote):
                continue

            ventas_lote = ventas[ventas['Nº lote'] == lote]
            total_enc = df_lote['Cant_Encargada'].sum()
            total_vendido = ventas_lote['Cant_Venta'].sum()
            total_devuelto = ventas_lote['Cant_Devolucion'].sum()
            neto_vendido = total_vendido - total_devuelto
            pendiente = total_enc - neto_vendido

            # Estado
            if neto_vendido == 0:
                estado = "🔴 SIN VENDER"
            elif pendiente > 0:
                estado = "🟡 VENTA PARCIAL"
            elif pendiente == 0:
                estado = "🟢 COMPLETO"
            else:
                estado = "⚠️ SOBREVENTA"

            caducidad = df_lote['Fecha caducidad'].dropna().iloc[0] if not df_lote['Fecha caducidad'].dropna().empty else "Sin fecha"

            titulo = f"📦 LOTE: {lote} | Cad: {caducidad} | {df_lote['Descripción'].iloc[0]} | {estado}"

            with st.expander(titulo):

                # RESUMEN
                st.markdown(f"""
                **Entradas:** {total_enc}  
                **Ventas:** {total_vendido}  
                **Devoluciones:** {total_devuelto}  
                **Neto vendido:** {neto_vendido}  
                **Pendiente:** {pendiente}  
                """)

                # ENCARGO
                st.markdown("### 📥 Encargo inicial")
                for vendedor, df_enc_v in df_lote.groupby('Vendedor_Encargo'):
                    st.markdown(
                        f"- 👤 Comercial {vendedor} encargó **{df_enc_v['Cant_Encargada'].sum()} uds**"
                    )

                # VENTAS
                if ventas_lote.empty:
                    st.markdown("### 🛑 Sin movimientos")
                else:
                    st.markdown("### 💰 Movimientos (ventas y devoluciones)")

                    for vendedor, df_vend in ventas_lote.groupby('Vendedor_Que_Vendió'):

                        st.markdown("---")
                        st.markdown(f"👤 **Comercial:** {vendedor}")

                        for _, row in df_vend.iterrows():

                            if row['Cantidad'] < 0:
                                texto = f"🔴 Venta: {abs(row['Cantidad'])} uds"
                            else:
                                texto = f"🟢 Devolución: {row['Cantidad']} uds"

                            st.markdown(
                                f"- {row['Alias_Cliente_Venta']} → {texto} ({row['Fecha_Venta']})"
                            )

        # =========================
        # DESCARGA EXCEL
        # =========================
        st.subheader("📥 Descargar datos en Excel")

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, index=False, sheet_name='Base')

        st.download_button(
            label="Descargar Excel base",
            data=output.getvalue(),
            file_name=f"Trazabilidad_{datetime.now().strftime('%d-%m')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_descarga_s1"
        )

    else:
        st.info("Sube los archivos para comenzar.")

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

        # CARGA
        df_enc = limpiar_columnas(pd.read_excel(f_enc, dtype=str))
        df_ped = limpiar_columnas(pd.read_excel(f_ped, dtype=str))
        df_mov = limpiar_columnas(pd.read_excel(f_mov, dtype=str))

        # NUMÉRICOS
        df_enc["Cantidad"] = pd.to_numeric(df_enc["Cantidad"], errors="coerce").fillna(0)
        df_mov["Cantidad"] = pd.to_numeric(df_mov["Cantidad"], errors="coerce").fillna(0)

        # SOLO ENTRADAS POSITIVAS
        df_mov = df_mov[df_mov["Cantidad"] > 0].copy()

        # FECHA SIMPLE
        if "Fecha caducidad" in df_mov.columns:
            df_mov["Fecha caducidad"] = pd.to_datetime(
                df_mov["Fecha caducidad"],
                errors="coerce"
            ).dt.strftime("%d/%m/%Y")

        # ENCARGOS + PEDIDOS
        paso1 = pd.merge(
            df_enc,
            df_ped[["Nº", "Nº de albarán"]],
            left_on="Nº Pedido compra",
            right_on="Nº",
            how="left"
        )

        # + MOVIMIENTOS
        final = pd.merge(
            paso1,
            df_mov,
            left_on=["Nº de albarán", "Nº producto"],
            right_on=["Nº documento", "Nº producto"],
            how="inner",
            suffixes=("_enc", "_mov")
        )

        # RESULTADO BASE
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

        resultado = resultado.sort_values(by=["Referencia", "Comercial"])

        # VISUAL
        st.subheader("📋 Resultado")

        for ref, bloque in resultado.groupby("Referencia"):
            descripcion = bloque["Descripción"].iloc[0]
            total_enc = bloque["Cantidad Encargada"].sum()
            total_rec = bloque["Cantidad Recibida"].iloc[0]

            if total_rec < total_enc:
                estado_header = "🔴 RECIBIDO PARCIAL"
            elif total_rec == total_enc:
                estado_header = "🟢 RECIBIDO COMPLETO"
            else:
                estado_header = "⚠️ RECIBIDO DE MÁS"

            with st.expander(f"📦 {ref} - {descripcion} | {estado_header} | Encargado: {total_enc} | Recibido: {total_rec}"):
                if total_rec < total_enc:
                    st.warning("Se ha recibido menos cantidad de la solicitada.")
                    mostrar = bloque[["Comercial", "Cantidad Encargada"]]
                else:
                    mostrar = bloque[["Comercial", "Cantidad Encargada"]].copy()
                    mostrar["Asignado"] = mostrar["Cantidad Encargada"]

                st.dataframe(mostrar, use_container_width=True, hide_index=True)

        # PREPARAR EXCEL FINAL
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

        excel_final = pd.concat(filas_excel, ignore_index=True)

        # DESCARGA
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            excel_final.to_excel(writer, index=False, sheet_name="Entradas")

        st.download_button(
            "📥 Descargar Excel",
            data=output.getvalue(),
            file_name=f"Entradas_Comercial_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_descarga_s2"
        )

    else:
        st.info("Sube los 3 archivos para comenzar.")
