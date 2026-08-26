import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import dotenv 
from dotenv import load_dotenv, find_dotenv
import unicodedata
import os
import re

load_dotenv(find_dotenv(), override=True)

try:
    ruta_base = os.path.dirname(os.path.abspath(__file__))
except NameError:
    ruta_base = os.getcwd()

if "CONFIG_SEGURIDAD" in os.listdir(ruta_base):
    ruta_global = ruta_base
else:
    ruta_global = os.path.dirname(ruta_base)
    
ruta_boveda = os.path.join(ruta_global, "CONFIG_SEGURIDAD")
json_plexus = os.path.join(ruta_boveda, "applied-plexus-476714-n0-d7c1f0400cc6.json")

scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

Credenciales = ServiceAccountCredentials.from_json_keyfile_name(json_plexus, scope)
client = gspread.authorize(Credenciales) 
load_dotenv(override=True)

# 2. Descarga de datos
hoja = client.open_by_key(os.getenv("CONSOLIDADO"))
entrega_1 = hoja.worksheet("ENTREGA 1").get_all_values()

# Guardamos la hoja de KUEPA en una variable para sobrescribirla después
hoja_kuepa = hoja.worksheet("REPORTE KUEPA_EMPLEO")
empleo = hoja_kuepa.get_all_values()

def limpiar_celdas_dataframe(df):
    columnas_texto = df.select_dtypes(include=['object', 'string']).columns
    for col in columnas_texto:
        df[col] = df[col].str.replace(r'[\n\r\t\xa0]+', ' ', regex=True)
        df[col] = df[col].str.replace(r'\s{2,}', ' ', regex=True)
        df[col] = df[col].str.strip()
    return df

def limpiar_texto(x):
    if pd.isna(x) or str(x).strip() == "":
        return ""
    texto = str(x).upper().strip()
    texto = ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn')
    return texto

# 3. Preparación de DataFrames
df_entrega_1 = pd.DataFrame(entrega_1[1:], columns=entrega_1[0])
df_entrega_1 = df_entrega_1.loc[:, df_entrega_1.columns.str.strip() != '']
df_entrega_1 = df_entrega_1.loc[:, ~df_entrega_1.columns.duplicated(keep='first')]
df_entrega_1 = limpiar_celdas_dataframe(df_entrega_1)

# BASE MAESTRA DE KUEPA (Conservará todos los registros intactos para luego sobrescribirse)
df_empleo_completo = pd.DataFrame(empleo[1:], columns=empleo[0])
df_empleo_completo = df_empleo_completo.loc[:, ~df_empleo_completo.columns.duplicated(keep='first')]
df_empleo_completo = limpiar_celdas_dataframe(df_empleo_completo)
df_empleo_completo['doc_number_clean'] = df_empleo_completo['doc_number'].str.strip()

# Creamos una copia filtrada sin duplicados EXCLUSIVAMENTE para hacer la comparación 1 a 1
df_empleo_cruce = df_empleo_completo.drop_duplicates(subset=['doc_number_clean'], keep='last').copy()

df_entrega_1['documento_clean'] = df_entrega_1['NÚMERO DE DOCUMENTO'].str.strip()

# Cruce de bases
df_cruce = pd.merge(
    df_entrega_1, 
    df_empleo_cruce, 
    left_on='documento_clean', 
    right_on='doc_number_clean', 
    how='left', 
    suffixes=('_fcs', '_empleo')
)

discrepancias = []
correcciones_kuepa = [] 

# 4. Motor de Validación Exclusivo para Empleabilidad
for index, row in df_cruce.iterrows():
    doc_id = row['documento_clean']
    
    orientador = row.get('ORIENTADOR/A', row.get('ORIENTADORA ', 'NO REGISTRADO'))
    if pd.isna(orientador) or str(orientador).strip() == "":
        orientador = 'NO REGISTRADO'
    
    if pd.isna(row['doc_number_clean']):
        discrepancias.append({
            'Documento': doc_id,
            'Orientador/a': str(orientador).strip(),
            'Dato a usar (KUEPA)': 'FALTA EN KUEPA (No cruzó)',
            'Dato original (FCS)': 'PRESENTE EN FCS'
        })
        continue 
    
    kuepa_job_id = limpiar_texto(row['job_offer_id'])
    kuepa_job_name = limpiar_texto(row['job_offer_name'])
    kuepa_company = limpiar_texto(row['company_name'])
    kuepa_nit = limpiar_texto(row['nit'])
    kuepa_sector = limpiar_texto(row['sector_name'])
    
    match_encontrado = False
    opciones_fcs_registradas = []
    
    for i in ["", ".1", ".2"]:
        num_vacante = 1 if i == "" else (2 if i == ".1" else 3)
        
        fcs_job_id = limpiar_texto(row.get(f'CÓDIGO DE VACANTE No {num_vacante}', ''))
        fcs_job_name = limpiar_texto(row.get(f'NOMBRE DEL CARGO{i}', ''))
        fcs_company = limpiar_texto(row.get(f'NOMBRE DE LA EMPRESA{i}', ''))
        
        fcs_nit_col = f'NIT CON DÍGITO DE VERIFICACIÓN\nUsar Guión ( - ) para el DV{i}'
        if fcs_nit_col not in row:
             fcs_nit_col = f'NIT (CON DÍGITO DE VERIFICACIÓN){i}'
        fcs_nit = limpiar_texto(row.get(fcs_nit_col, ''))
        
        fcs_sector = limpiar_texto(row.get(f'SECTOR AL QUE PERTENECE LA EMPRESA{i}', ''))

        if fcs_job_id or fcs_company:
            opciones_fcs_registradas.append(f"[Opción {num_vacante}: Vacante {fcs_job_id} - {fcs_job_name} en {fcs_company} (NIT: {fcs_nit})]")

        if (kuepa_job_id == fcs_job_id and 
            kuepa_job_name == fcs_job_name and 
            kuepa_company == fcs_company and 
            kuepa_nit == fcs_nit and 
            kuepa_sector == fcs_sector):
            
            match_encontrado = True
            break 
            
    if not match_encontrado:
        if not kuepa_job_id and not kuepa_company and not opciones_fcs_registradas:
            continue
            
        val_kuepa = f"Vacante {kuepa_job_id} - {kuepa_job_name} en {kuepa_company} (NIT: {kuepa_nit} - Sector: {kuepa_sector})" if (kuepa_job_id or kuepa_company) else "SIN VACANTE REGISTRADA EN KUEPA"
        val_fcs = " | ".join(opciones_fcs_registradas) if opciones_fcs_registradas else "SIN VACANTE REGISTRADA EN FCS"
        
        discrepancias.append({
            'Documento': doc_id,
            'Orientador/a': str(orientador).strip(),
            'Dato a usar (KUEPA)': val_kuepa,
            'Dato original (FCS)': val_fcs
        })
        
        # Guardamos la corrección usando los nombres crudos de FCS (Opción 1)
        fcs_nit_col_principal = 'NIT CON DÍGITO DE VERIFICACIÓN\nUsar Guión ( - ) para el DV'
        if fcs_nit_col_principal not in row:
             fcs_nit_col_principal = 'NIT (CON DÍGITO DE VERIFICACIÓN)'
             
        correcciones_kuepa.append({
            'doc_number': doc_id,
            'job_offer_id': str(row.get('CÓDIGO DE VACANTE No 1', '')).strip(),
            'job_offer_name': str(row.get('NOMBRE DEL CARGO', '')).strip(),
            'company_name': str(row.get('NOMBRE DE LA EMPRESA', '')).strip(),
            'nit': str(row.get(fcs_nit_col_principal, '')).strip(),
            'sector_name': str(row.get('SECTOR AL QUE PERTENECE LA EMPRESA', '')).strip()
        })

# 5. INYECCIÓN DE CORRECCIONES A LA BASE MAESTRA
if correcciones_kuepa:
    df_actualizacion = pd.DataFrame(correcciones_kuepa)
    # Convertimos las correcciones en un diccionario para inyectarlas hiper-rápido por número de cédula
    diccionario_actualizaciones = df_actualizacion.set_index('doc_number').to_dict('index')
    
    columnas_kuepa = ['job_offer_id', 'job_offer_name', 'company_name', 'nit', 'sector_name']
    
    # Recorremos la base completa. Si la cédula tiene un error, sobrescribimos los datos de empleabilidad
    for idx, row in df_empleo_completo.iterrows():
        cedula = row['doc_number_clean']
        if cedula in diccionario_actualizaciones:
            for col in columnas_kuepa:
                if col in df_empleo_completo.columns:
                    df_empleo_completo.at[idx, col] = diccionario_actualizaciones[cedula][col]

# Quitamos la columna virtual 'doc_number_clean' para que la base quede exactamente igual que el original
if 'doc_number_clean' in df_empleo_completo.columns:
    df_empleo_completo.drop(columns=['doc_number_clean'], inplace=True)

# 6. Sincronización final con Google Sheets
nombre_hojaq = os.getenv('DISCREPANCIAS')
hoja_discrepancias = client.open_by_key(nombre_hojaq)

# --- Sincronizar Reporte Empleabilidad ---
data_reporte = hoja_discrepancias.worksheet("REPORTE EMPLEABILIDAD")
data_reporte.clear()
df_reporte = pd.DataFrame(discrepancias)

if not df_reporte.empty:
    datos_a_subir_reporte = [df_reporte.columns.values.tolist()] + df_reporte.values.tolist()
    data_reporte.update(range_name='A1', values=datos_a_subir_reporte)
    print(f"¡Auditoría lista! Se reportaron {len(df_reporte)} discrepancias de empleabilidad.")
else:
    data_reporte.update(range_name='A1', values=[['Documento', 'Orientador/a', 'Dato a usar (KUEPA)', 'Dato original (FCS)']])
    print("¡Auditoría lista! Cero discrepancias de empleabilidad encontradas.")

# --- SOBRESCRIBIR LA BASE MAESTRA DE KUEPA ---
if correcciones_kuepa:
    hoja_kuepa.clear()
    datos_kuepa = [df_empleo_completo.columns.values.tolist()] + df_empleo_completo.values.tolist()
    hoja_kuepa.update(range_name='A1', values=datos_kuepa)
    print(f"¡MAGIA HECHA! La hoja 'REPORTE KUEPA_EMPLEO' fue sobrescrita corrigiendo a {len(correcciones_kuepa)} usuarios. Tienes el dato final listo.")
else:
    print("La hoja 'REPORTE KUEPA_EMPLEO' está impecable, no fue necesario sobrescribirla.")