import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import dotenv 
from dotenv import load_dotenv, find_dotenv
import unicodedata
import os
import re

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

# 1. Autenticación
scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

Credenciales = ServiceAccountCredentials.from_json_keyfile_name(json_plexus, scope)
client = gspread.authorize(Credenciales) 
load_dotenv(find_dotenv(), override=True)

# 2. Descarga de datos
hoja = client.open_by_key(os.getenv("CONSOLIDADO"))
entrega_1 = hoja.worksheet("ENTREGA 1").get_all_values()
empleo = hoja.worksheet("REPORTE KUEPA_EMPLEO").get_all_values()

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

df_empleo = pd.DataFrame(empleo[1:], columns=empleo[0])
df_empleo = df_empleo.loc[:, ~df_empleo.columns.duplicated(keep='first')]
df_empleo = limpiar_celdas_dataframe(df_empleo)

df_empleo['doc_number_clean'] = df_empleo['doc_number'].str.strip()
df_entrega_1['documento_clean'] = df_entrega_1['NÚMERO DE DOCUMENTO'].str.strip()

# Eliminamos duplicados en KUEPA para mantener la relación 1 a 1
df_empleo = df_empleo.drop_duplicates(subset=['doc_number_clean'], keep='last')

# Cruce de bases
df_cruce = pd.merge(
    df_entrega_1, 
    df_empleo, 
    left_on='documento_clean', 
    right_on='doc_number_clean', 
    how='left', 
    suffixes=('_fcs', '_empleo')
)

discrepancias = []

# 4. Motor de Validación Exclusivo para Empleabilidad
for index, row in df_cruce.iterrows():
    doc_id = row['documento_clean']
    
    # Extracción simple del orientador para asignar la corrección
    orientador = row.get('ORIENTADOR/A', row.get('ORIENTADORA ', 'NO REGISTRADO'))
    if pd.isna(orientador) or str(orientador).strip() == "":
        orientador = 'NO REGISTRADO'
    
    # Validamos si no cruzó
    if pd.isna(row['doc_number_clean']):
        discrepancias.append({
            'Documento': doc_id,
            'Orientador/a': str(orientador).strip(),
            'Dato a usar (KUEPA)': 'FALTA EN KUEPA (No cruzó)',
            'Dato original (FCS)': 'PRESENTE EN FCS'
        })
        continue 
    
    # Limpiamos los datos de empleabilidad de Kuepa
    kuepa_job_id = limpiar_texto(row['job_offer_id'])
    kuepa_job_name = limpiar_texto(row['job_offer_name'])
    kuepa_company = limpiar_texto(row['company_name'])
    kuepa_nit = limpiar_texto(row['nit'])
    kuepa_sector = limpiar_texto(row['sector_name'])
    
    match_encontrado = False
    opciones_fcs_registradas = []
    
    # Comparamos contra las 3 opciones de FCS
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

        # Si hay algo registrado en esta opción, lo guardamos para el reporte por si falla el match
        if fcs_job_id or fcs_company:
            opciones_fcs_registradas.append(f"[Opción {num_vacante}: Vacante {fcs_job_id} - {fcs_job_name} en {fcs_company} (NIT: {fcs_nit})]")

        # Verificación estricta del match
        if (kuepa_job_id == fcs_job_id and 
            kuepa_job_name == fcs_job_name and 
            kuepa_company == fcs_company and 
            kuepa_nit == fcs_nit and 
            kuepa_sector == fcs_sector):
            
            match_encontrado = True
            break 
            
    # Si ninguna de las 3 opciones hizo match perfecto, registramos la discrepancia
    if not match_encontrado:
        # Si ambas plataformas están vacías en empleabilidad, lo ignoramos
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

df_reporte = pd.DataFrame(discrepancias)

nombre_hojaq = os.getenv('DISCREPANCIAS')
nombre_hoja = client.open_by_key(nombre_hojaq)
data = nombre_hoja.worksheet("REPORTE EMPLEABILIDAD")
_ = data.clear()

if not df_reporte.empty:
    datos_a_subir = [df_reporte.columns.values.tolist()] + df_reporte.values.tolist()
    _ = data.update(range_name='A1', values=datos_a_subir)
    print(f"¡Sincronización exitosa! Se actualizaron {len(df_reporte)} registros de empleabilidad en la pestaña 'REPORTE EMPLEABILIDAD'.")
else:
    _ = data.update(range_name='A1', values=[['Documento', 'Orientador/a', 'Dato a usar (KUEPA)', 'Dato original (FCS)']])
    print("¡Sincronización exitosa! Cero discrepancias de empleabilidad encontradas.")