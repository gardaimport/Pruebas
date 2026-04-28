import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# =====================================================
# CONFIGURACIÓN
# =====================================================
st.set_page_config(page_title="Control Trazabilidad Lotes", layout="wide")

# =====================================================
# MAESTRO CLIENTES
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
# SECCIÓN 1 (ORIGINAL RESTAURADA)
# =====================================================
# =====================================================
if seccion == "📦 Trazabilidad por Lotes":

    st.title("🎯 Sistema de Trazabilidad: Encargos vs Ventas")

    st.sidebar.header("📂 Subir archivos")

    f_encargos = st.sidebar.file_uploader("1. Encargos", type=['xlsx'], key="s1_1")
    f_cal = st.sidebar.file_uploader("2. Relación CAL", type=['xlsx'], key="s1_2")
    f_movs = st.sidebar.file_uploader("3. Movimientos", type=['xlsx'], key="s1_3")

    if f_encargos and f_cal and f_movs:

        df_enc = pd.read_excel(f_encargos, dtype={'Cód. vendedor': str, 'Nº Pedido compra': str})
        df_cal = pd.read_excel(f_cal, dtype={'Nº': str, 'Nº de albarán': str})
        df_mov = pd.read_excel(f_movs, dtype={'Nº documento': str, 'Nº lote': str, 'Cód. procedencia mov.': str})

        df_enc['Cantidad'] = pd.to_numeric(df_enc['Cantidad'], errors='coerce').fillna(0)
        df_mov['Cantidad'] = pd.to_numeric(df_mov['Cantidad'], errors='coerce').fillna(0)

        for col in ['Fecha registro', 'Fecha caducidad']:
            if col in df_mov.columns:
                df_mov[col] = pd.to_datetime(df_mov[col], errors='coerce').dt.strftime('%d/%m/%Y')

        # VENTAS
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

        ventas['Cant_Venta'] = ventas['Cantidad'].apply(lambda x: abs(x) if x < 0 else 0)
        ventas['Cant_Devolucion'] = ventas['Cantidad'].apply(lambda x: x if x > 0 else 0)

        # ENCARGOS
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
        ).drop_duplicates()

        st.subheader("📦 Trazabilidad por Lotes")

        for lote, df_lote in df_final.groupby('Nº lote'):

            if pd.isna(lote):
                continue

            ventas_lote = ventas[ventas['Nº lote'] == lote]

            total_enc = df_lote['Cant_Encargada'].sum()
            total_vendido = ventas_lote['Cant_Venta'].sum()
            total_devuelto = ventas_lote['Cant_Devolucion'].sum()

            neto = total_vendido - total_devuelto
            pendiente = total_enc - neto

            estado = "🔴 SIN VENDER" if neto == 0 else "🟡 PARCIAL" if pendiente > 0 else "🟢 COMPLETO"

            cad = df_lote['Fecha caducidad'].dropna().iloc[0] if not df_lote['Fecha caducidad'].dropna().empty else "Sin fecha"

            with st.expander(f"📦 LOTE {lote} | {estado}"):

                st.write(f"Entradas: {total_enc}")
                st.write(f"Ventas: {total_vendido}")
                st.write(f"Devoluciones: {total_devuelto}")
                st.write(f"Pendiente: {pendiente}")

# =====================================================
# =====================================================
# SECCIÓN 2 (REPARTO POR COMERCIAL MEJORADO)
# =====================================================
# =====================================================
elif seccion == "📥 Entradas por Comercial":

    st.title("📥 Entradas por Comercial")

    st.sidebar.header("📂 Subir archivos")

    f_enc = st.sidebar.file_uploader("1. Encargos", type=["xlsx"], key="s2_1")
    f_ped = st.sidebar.file_uploader("2. Pedidos Compra", type=["xlsx"], key="s2_2")
    f_mov = st.sidebar.file_uploader("3. Movimientos", type=["xlsx"], key="s2_3")

    if f_enc and f_ped and f_mov:

        df_enc = pd.read_excel(f_enc, dtype=str)
        df_ped = pd.read_excel(f_ped, dtype=str)
        df_mov = pd.read_excel(f_mov, dtype=str)

        df_enc["Cantidad"] = pd.to_numeric(df_enc["Cantidad"], errors="coerce").fillna(0)
        df_mov["Cantidad"] = pd.to_numeric(df_mov["Cantidad"], errors="coerce").fillna(0)

        df_mov = df_mov[df_mov["Cantidad"] > 0].copy()

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
            how="inner"
        )

        resultado = final.rename(columns={
            "Cantidad_x": "Cantidad Encargada",
            "Cantidad_y": "Cantidad Recibida",
            "Cód. vendedor": "Comercial"
        })

        st.subheader("📋 Entradas por Comercial")

        for ref, bloque in resultado.groupby("Nº producto"):

            total_enc = bloque["Cantidad Encargada"].sum()
            total_rec = bloque["Cantidad Recibida"].sum()

            estado = "⚠️ MENOS RECIBIDO" if total_rec < total_enc else "✔ COMPLETO"

            with st.expander(f"📦 {ref} | Enc: {total_enc} | Rec: {total_rec} | {estado}"):

                st.dataframe(
                    bloque[["Comercial", "Cantidad Encargada"]],
                    use_container_width=True,
                    hide_index=True
                )

        # EXCEL
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            resultado.to_excel(writer, index=False, sheet_name="Reparto")

        st.download_button(
            "📥 Descargar Excel",
            data=output.getvalue(),
            file_name=f"reparto_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.info("Sube los 3 archivos para comenzar.")
