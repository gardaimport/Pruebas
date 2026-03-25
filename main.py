import streamlit as st
import pandas as pd
import io
from datetime import datetime

# Configuración de página
st.set_page_config(page_title="Control Trazabilidad Lotes", layout="wide")

# 1. CARGA DEL MAESTRO EXCEL (Fijo en el servidor/GitHub)
@st.cache_data
def cargar_maestro():
    # Leemos el Excel asegurando que los códigos sean tratados como texto
    try:
        df = pd.read_excel("Clientes.xlsx", dtype={'Nº': str, 'Cód. vendedor': str})
        return df
    except Exception as e:
        st.error(f"Error al cargar Clientes.xlsx: {e}")
        return pd.DataFrame(columns=['Nº', 'Alias', 'Cód. vendedor'])

df_clientes = cargar_maestro()

st.title("🎯 Sistema de Trazabilidad: Encargos vs Ventas")
st.markdown("Cruce de datos para control de stock colgado y lotes.")

# --- BARRA LATERAL: SUBIDA DE ARCHIVOS DIARIOS ---
st.sidebar.header("📂 Subir archivos de consulta")
f_encargos = st.sidebar.file_uploader("1. Encargos registrados", type=['xlsx'])
f_cal = st.sidebar.file_uploader("2. Archivo ENCARGOS/CAL", type=['xlsx'])
f_movs = st.sidebar.file_uploader("3. Archivo movimiento producto", type=['xlsx'])

if f_encargos and f_cal and f_movs:
    # Lectura de los archivos subidos
    # Usamos dtype=str en columnas clave para no perder ceros a la izquierda
    df_enc = pd.read_excel(f_encargos, dtype={'Cód. vendedor': str, 'Nº Pedido compra': str})
    df_cal = pd.read_excel(f_cal, dtype={'Nº': str, 'Nº de albarán': str})
    df_mov = pd.read_excel(f_movs, dtype={'Nº documento': str, 'Nº lote': str, 'Cód. procedencia mov.': str, 'Nº producto': str})
    
    # Conversión de cantidades a números
    df_enc['Cantidad'] = pd.to_numeric(df_enc['Cantidad'], errors='coerce').fillna(0)
    df_mov['Cantidad'] = pd.to_numeric(df_mov['Cantidad'], errors='coerce').fillna(0)

    # --- LÓGICA DE PROCESAMIENTO ---

    # A. VENTAS DETALLADAS CON NOMBRE DE CLIENTE Y VENDEDOR (Usando Maestro)
    ventas_detalle = df_mov[df_mov['Tipo movimiento'] == 'Venta'].copy()
    ventas_detalle = pd.merge(
        ventas_detalle, 
        df_clientes[['Nº', 'Alias', 'Cód. vendedor']], 
        left_on='Cód. procedencia mov.', 
        right_on='Nº', 
        how='left'
    )
    
    # Resumen de ventas por Lote + Nº Cliente + Alias
    resumen_ventas_lote = ventas_detalle.groupby(['Nº lote', 'Cód. vendedor', 'Nº', 'Alias']).agg({
        'Cantidad': lambda x: abs(x.sum())
    }).reset_index().rename(columns={
        'Nº': 'Nº_Cliente_Venta',
        'Alias': 'Alias_Cliente_Venta',
        'Cantidad': 'Cant_Vendida',
        'Cód. vendedor': 'Vendedor_Que_Vendió'
    })

    # B. TRAZABILIDAD DESDE EL ENCARGO
    # 1. Encargo -> CAL (Entrada)
    paso1 = pd.merge(
        df_enc[['Cód. vendedor', 'Nº Pedido compra', 'Descripción', 'Cantidad', 'Alias']], 
        df_cal[['Nº', 'Nº de albarán']], 
        left_on='Nº Pedido compra', 
        right_on='Nº', 
        how='left'
    ).rename(columns={'Cantidad': 'Cant_Encargada', 'Alias': 'Nombre_Encargo', 'Nº de albarán': 'CAL_Entrada', 'Cód. vendedor': 'Vendedor_Encargo'})

    # 2. CAL -> Lote (Buscamos la entrada física del lote en movimientos)
    entradas_lotes = df_mov[df_mov['Tipo movimiento'] == 'Compra'][['Nº documento', 'Nº lote', 'Fecha caducidad']].drop_duplicates()
    paso2 = pd.merge(paso1, entradas_lotes, left_on='CAL_Entrada', right_on='Nº documento', how='left')

    # 3. Unión Final con Ventas Reales (Quién compró cada lote)
    df_final = pd.merge(
        paso2,
        resumen_ventas_lote,
        on='Nº lote',
        how='left'
    ).fillna({
        'Cant_Vendida': 0, 
        'Nº_Cliente_Venta': '---', 
        'Alias_Cliente_Venta': 'SIN VENTA',
        'Vendedor_Que_Vendió': '---'
    })

    # C. CÁLCULO DE BALANCE (Encargado vs Vendido)
    df_final['Diferencia'] = df_final['Cant_Encargada'] - df_final['Cant_Vendida']

    # --- INTERFAZ ---
    st.subheader("📋 Vista de Trazabilidad")
    
    # Filtro por vendedor del encargo
    vend_filtro = st.selectbox("Filtrar por Vendedor del Encargo", ["Todos"] + list(df_final['Vendedor_Encargo'].unique()))
    if vend_filtro != "Todos":
        df_final = df_final[df_final['Vendedor_Encargo'] == vend_filtro]

    st.dataframe(df_final, use_container_width=True, hide_index=True)

    # --- EXCEL DESCARGABLE ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Trazabilidad_Total')
    
    st.download_button(
        label="📥 Descargar Reporte Completo (Excel)",
        data=output.getvalue(),
        file_name=f"Trazabilidad_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👋 Sube los 3 archivos Excel en la barra lateral para generar el informe.")
    st.image("https://img.icons8.com/clouds/200/000000/data-configuration.png", width=100)