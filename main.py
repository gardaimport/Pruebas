import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# Configuración
st.set_page_config(page_title="Control Trazabilidad Lotes", layout="wide")

# =========================
# CARGA MAESTRO CLIENTES
# =========================
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

st.title("🎯 Sistema de Trazabilidad: Encargos vs Ventas")

# =========================
# SUBIDA ARCHIVOS
# =========================
st.sidebar.header("📂 Subir archivos")
f_encargos = st.sidebar.file_uploader("1. Encargos", type=['xlsx'])
f_cal = st.sidebar.file_uploader("2. Relación CAL", type=['xlsx'])
f_movs = st.sidebar.file_uploader("3. Movimientos", type=['xlsx'])

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
    # VENTAS
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

    ventas['Cantidad'] = ventas['Cantidad'].abs()

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

    # 🔴 EVITAR DUPLICADOS
    df_final = df_final.drop_duplicates()

    # =========================
    # VISUALIZACIÓN POR LOTES
    # =========================
    st.subheader("📦 Trazabilidad visual por Lote")

    for lote, df_lote in df_final.groupby('Nº lote'):

        if pd.isna(lote):
            continue

        ventas_lote = ventas[ventas['Nº lote'] == lote]

        # ✅ CORRECCIÓN: suma real del encargo
        total_enc = df_lote['Cant_Encargada'].sum()

        total_vendido = ventas_lote['Cantidad'].fillna(0).sum()
        pendiente = total_enc - total_vendido

        # Estado
        if total_vendido == 0:
            estado = "🔴 SIN VENDER"
        elif pendiente > 0:
            estado = "🟡 VENTA PARCIAL"
        elif pendiente == 0:
            estado = "🟢 COMPLETO"
        else:
            estado = "⚠️ SOBREVENTA"

        # ✅ AÑADIR CADUCIDAD
        caducidad = df_lote['Fecha caducidad'].dropna().iloc[0] if not df_lote['Fecha caducidad'].dropna().empty else "Sin fecha"

        titulo = f"📦 LOTE: {lote} | Cad: {caducidad} | {df_lote['Descripción'].iloc[0]} | {estado}"

        with st.expander(titulo):

            # RESUMEN
            st.markdown(f"""
            **Entradas:** {total_enc}  
            **Vendido:** {total_vendido}  
            **Pendiente:** {pendiente}  
            """)

            # =====================
            # ENCARGO INICIAL
            # =====================
            st.markdown("### 📥 Encargo inicial")

            for vendedor, df_enc_v in df_lote.groupby('Vendedor_Encargo'):
                st.markdown(
                    f"- 👤 Comercial {vendedor} encargó **{df_enc_v['Cant_Encargada'].sum()} uds**"
                )

            # =====================
            # VENTAS
            # =====================
            if ventas_lote.empty:
                st.markdown("### 🛑 Sin ventas registradas")
            else:
                st.markdown("### 💰 Ventas realizadas")

                for vendedor, df_vend in ventas_lote.groupby('Vendedor_Que_Vendió'):

                    st.markdown("---")
                    st.markdown(f"👤 **Comercial:** {vendedor}")

                    for _, row in df_vend.iterrows():
                        st.markdown(
                            f"- {row['Alias_Cliente_Venta']} → **{row['Cantidad']} uds** ({row['Fecha_Venta']})"
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
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Sube los archivos para comenzar.")
