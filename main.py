import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime

# Configuración de página
st.set_page_config(page_title="Control Trazabilidad Lotes", layout="wide")

# 1. CARGA DEL MAESTRO EXCEL (Fijo en GitHub)
@st.cache_data
def cargar_maestro():
    ruta_archivo = "Clientes.xlsx"
    if os.path.exists(ruta_archivo):
        try:
            df = pd.read_excel(ruta_archivo, engine='openpyxl', dtype={'Nº': str, 'Cód. vendedor': str})
            return df
        except Exception as e:
            st.error(f"Error al abrir Clientes.xlsx: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

df_clientes = cargar_maestro()

st.title("🎯 Sistema de Trazabilidad: Encargos vs Ventas")

# --- BARRA LATERAL: SUBIDA DE ARCHIVOS ---
st.sidebar.header("📂 Subir archivos de consulta")
f_encargos = st.sidebar.file_uploader("1. Encargos registrados", type=['xlsx'])
f_cal = st.sidebar.file_uploader("2. Archivo ENCARGOS/CAL", type=['xlsx'])
f_movs = st.sidebar.file_uploader("3. Archivo movimiento producto", type=['xlsx'])

if f_encargos and f_cal and f_movs:
    df_enc = pd.read_excel(f_encargos, dtype={'Cód. vendedor': str, 'Nº Pedido compra': str})
    df_cal = pd.read_excel(f_cal, dtype={'Nº': str, 'Nº de albarán': str})
    df_mov = pd.read_excel(f_movs, dtype={'Nº documento': str, 'Nº lote': str, 'Cód. procedencia mov.': str, 'Nº producto': str})
    
    # Conversión de cantidades
    df_enc['Cantidad'] = pd.to_numeric(df_enc['Cantidad'], errors='coerce').fillna(0)
    df_mov['Cantidad'] = pd.to_numeric(df_mov['Cantidad'], errors='coerce').fillna(0)

    # --- TRATAMIENTO DE FECHAS ---
    # Convertimos a datetime y luego a formato texto simple DD/MM/YYYY
    for col in ['Fecha registro', 'Fecha caducidad']:
        if col in df_mov.columns:
            df_mov[col] = pd.to_datetime(df_mov[col], errors='coerce').dt.strftime('%d/%m/%Y')

    # --- LÓGICA DE PROCESAMIENTO ---

    # A. VENTAS DETALLADAS
    ventas_detalle = df_mov[df_mov['Tipo movimiento'] == 'Venta'].copy()
    ventas_detalle = pd.merge(
        ventas_detalle, 
        df_clientes[['Nº', 'Alias', 'Cód. vendedor']], 
        left_on='Cód. procedencia mov.', 
        right_on='Nº', 
        how='left'
    )
    
    resumen_ventas_lote = ventas_detalle.groupby(['Nº lote', 'Cód. vendedor', 'Nº', 'Alias', 'Fecha registro']).agg({
        'Cantidad': lambda x: abs(x.sum())
    }).reset_index().rename(columns={
        'Nº': 'Nº_Cliente_Venta',
        'Alias': 'Alias_Cliente_Venta',
        'Cantidad': 'Cant_Vendida',
        'Cód. vendedor': 'Vendedor_Que_Vendió',
        'Fecha registro': 'Fecha_Venta'
    })

    # B. TRAZABILIDAD DESDE EL ENCARGO
    paso1 = pd.merge(
        df_enc[['Cód. vendedor', 'Nº Pedido compra', 'Descripción', 'Cantidad', 'Alias']], 
        df_cal[['Nº', 'Nº de albarán']], 
        left_on='Nº Pedido compra', 
        right_on='Nº', 
        how='left'
    ).rename(columns={'Cantidad': 'Cant_Encargada', 'Alias': 'Nombre_Encargo', 'Nº de albarán': 'CAL_Entrada', 'Cód. vendedor': 'Vendedor_Encargo'})

    # Traemos Fecha registro de la ENTRADA (Compra)
    entradas_lotes = df_mov[df_mov['Tipo movimiento'] == 'Compra'][['Nº documento', 'Nº lote', 'Fecha caducidad', 'Fecha registro']].drop_duplicates()
    
    paso2 = pd.merge(paso1, entradas_lotes, left_on='CAL_Entrada', right_on='Nº documento', how='left')

    # C. UNIÓN FINAL
    df_final = pd.merge(
        paso2,
        resumen_ventas_lote,
        on='Nº lote',
        how='left'
    ).fillna({
        'Cant_Vendida': 0, 
        'Nº_Cliente_Venta': '---', 
        'Alias_Cliente_Venta': 'SIN VENTA',
        'Vendedor_Que_Vendió': '---',
        'Fecha_Venta': '---'
    })

    # D. REORGANIZACIÓN DE COLUMNAS PARA EL REPORTE
    reporte_excel = df_final[[
        'Vendedor_Encargo', 'Nombre_Encargo', 'Descripción', 'Nº Pedido compra', 
        'CAL_Entrada', 'Fecha registro', 'Nº lote', 'Fecha caducidad', 
        'Cant_Encargada', 'Nº_Cliente_Venta', 'Alias_Cliente_Venta', 
        'Vendedor_Que_Vendió', 'Fecha_Venta', 'Cant_Vendida'
    ]].rename(columns={'Fecha registro': 'Fecha_Entrada_Almacén'})

    # --- INTERFAZ ---
    st.subheader("📋 Trazabilidad de Lotes y Fechas")
    st.dataframe(reporte_excel, use_container_width=True, hide_index=True)

    # Excel Descargable
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        reporte_excel.to_excel(writer, index=False, sheet_name='Trazabilidad')
    
    st.download_button(
        label="📥 Descargar Excel con Fechas Simples",
        data=output.getvalue(),
        file_name=f"Trazabilidad_Fechas_{datetime.now().strftime('%d-%m')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Sube los archivos para procesar la trazabilidad.")
