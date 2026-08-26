import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import dotenv 
from dotenv import load_dotenv, find_dotenv
import unicodedata
import os
import re
import difflib
from datetime import datetime

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

hoja = client.open_by_key(os.getenv("CONSOLIDADO"))
consolidado_fcs = hoja.worksheet("CONSOLIDADO").get_all_values()
empleo = hoja.worksheet("REPORTE_KUEPA_EMPLEO").get_all_values()

def limpiar_celdas_dataframe(df):
    columnas_texto = df.select_dtypes(include=['object', 'string']).columns
    for col in columnas_texto:
        df[col] = df[col].str.replace(r'[\n\r\t\xa0]+', ' ', regex=True)
        df[col] = df[col].str.replace(r'\s{2,}', ' ', regex=True)
        df[col] = df[col].str.strip()
    return df

consolidado_fcs = pd.DataFrame(consolidado_fcs[6:], columns=consolidado_fcs[5])
consolidado_fcs = consolidado_fcs.loc[:, consolidado_fcs.columns.str.strip() != '']
consolidado_fcs = consolidado_fcs.loc[:, ~consolidado_fcs.columns.duplicated(keep='first')]
consolidado_fcs = limpiar_celdas_dataframe(consolidado_fcs)
consolidado_fcs = consolidado_fcs[consolidado_fcs['REPORTE'].str.strip().str.lower() == "finalizado"]

df_empleo = pd.DataFrame(empleo[1:], columns=empleo[0])
df_empleo = df_empleo.loc[:, ~df_empleo.columns.duplicated(keep='first')]
df_empleo = limpiar_celdas_dataframe(df_empleo)

def limpiar_texto(x):
    if pd.isna(x) or str(x).strip() == "":
        return ""
    texto = str(x).upper().strip()
    texto = ''.join(c for c in unicodedata.normalize('NFKD', texto) if unicodedata.category(c) != 'Mn')
    return texto

def normalizar_direccion(dir_str):
    if not dir_str:
        return ""
    d = str(dir_str).upper()
    d = re.sub(r'[^\w\s]', ' ', d)
    d = d.replace('BIS', ' BIS ')
    for word in ['SUR', 'NORTE', 'ESTE', 'OESTE', 'ORIENTE', 'OCCIDENTE']:
        d = d.replace(word, ' ')
    d = re.sub(r'([A-Z])(\d)', r'\1 \2', d)
    d = re.sub(r'(\d)([A-Z])', r'\1 \2', d)
    d = re.sub(r'\b0+(\d+)\b', r'\1', d)
    d = re.sub(r'\b(CARERA|CARERRA|CAR)\b', 'CARRERA', d)
    d = re.sub(r'\b(CALL)\b', 'CALLE', d)
    d = re.sub(r'\b(TRASVERSAL)\b', 'TRANSVERSAL', d)
    d = re.sub(r'\b(APTO|AP|TORRE|TO|INT|INTERIOR|BLOQUE|BLQ|PISO|PI|MZ|MANZANA|LOTE|CASA|CS|ALT)\s*\d*[A-Z]*\b', ' ', d)
    d = re.sub(r'\b(AV|AVDA|AVENIDA)\s*(CRA|CR|KR|KRA|CARRERA|K)\b', 'K', d)
    d = re.sub(r'\b(AV|AVDA|AVENIDA)\s*(CLL|CL|KLL|CALLE|C)\b', 'C', d)
    d = re.sub(r'\bAK\b', 'K', d)
    d = re.sub(r'\bAC\b', 'C', d)
    d = re.sub(r'\b(CLL|CL|KLL|CALLE)\b', 'C', d) 
    d = re.sub(r'\b(CRA|CR|KR|KRA|CARRERA)\b', 'K', d) 
    d = re.sub(r'\b(TV|TRV|TRANSVERSAL)\b', 'T', d)
    d = re.sub(r'\b(DG|DIAG|DIAGONAL)\b', 'D', d)
    d = re.sub(r'\b(AV|AVDA|AVENIDA)\b', 'A', d)
    d = re.sub(r'\b(NO|NRO|NUMERO)\b', ' ', d)
    d = re.sub(r'\bN\b(?=\s*\d)', ' ', d)
    d = re.sub(r'\s+', '', d)
    
    return d

def extraer_orientadora_observacion(obs, fallback_prof):
    obs_limpio = limpiar_texto(obs)
    partes = re.split(r'ORIENTADOR(?:A|O|/A|\(A\))?\s*:', obs_limpio)
    if len(partes) > 1:
        ext = partes[-1]
        ext = re.split(r'\bCURSO\b', ext)[0]
        ext = ext.replace('.', '').strip()
        return ext.replace('DIANA VALBUENA', 'CAROLINA VALBUENA')
    
    fall = limpiar_texto(fallback_prof)
    return fall.replace('DIANA VALBUENA', 'CAROLINA VALBUENA')

def normalizar_barrera(b):
    if not b: return ""
    b = str(b).upper().strip()
    b = b.replace('PERTENECE AL PROGRAMA JCO', '')
    b = b.replace('(JCO)', '')
    b = b.replace('JCO', '')
    
    b = re.sub(r'[^\w\s]', ' ', b)
    b = re.sub(r'\s+', ' ', b).strip()
    
    if b.startswith('NO APLICA ES'):
        b = 'NO APLICA'
        
    if b in ['NO APLICA', 'NO APLIA', 'NA', 'NINGUNA', 'N A']:
        return 'NO APLICA'
    return b

def limpiar_nit(nit):
    if not nit: return ""
    return re.split(r'[-_\s]', str(nit))[0].strip()

def calcular_similitud(texto1, texto2):
    if not texto1 and not texto2: return 1.0
    if not texto1 or not texto2: return 0.0
    t1 = re.sub(r'[\W_]+', '', texto1)
    t2 = re.sub(r'[\W_]+', '', texto2)
    return difflib.SequenceMatcher(None, t1, t2).ratio()

mapa_documentos = {
    'CEDULA DE CIUDADANIA': 'CC', 'C.C': 'CC',
    'TARJETA DE IDENTIDAD': 'TI', 'T.I': 'TI',
    'CEDULA DE EXTRANJERIA': 'CE', 'C.E': 'CE',
    'PERMISO POR PROTECCION TEMPORAL': 'PPT',
    'DOCUMENTO NACIONAL DE IDENTIDAD': 'DNI',
    'PASAPORTE': 'PA'
}

consolidado_fcs['APELLIDOS_COMPLETOS'] = (
    consolidado_fcs['APELLIDOS \n(APELLIDOS 1 Y 2)'].astype(str).str.strip() + " " + 
    consolidado_fcs['APELLIDO 2'].astype(str).str.strip()
).str.strip().str.replace(r'\s+', ' ', regex=True)

df_empleo['doc_number_clean'] = df_empleo['doc_number'].str.strip()
consolidado_fcs['documento_clean'] = consolidado_fcs['NÚMERO DE DOCUMENTO'].str.strip()

df_empleo = df_empleo.drop_duplicates()

df_empleo['fecha_nac_clean'] = pd.to_datetime(df_empleo['birthdate'], errors='coerce').dt.strftime('%Y-%m-%d')
consolidado_fcs['fecha_nac_clean'] = pd.to_datetime(consolidado_fcs['FECHA DE NACIMIENTO \n( DD/MM/AA)'], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')

df_empleo['orientadora_extraida'] = df_empleo.apply(lambda row: extraer_orientadora_observacion(row['observation'], row['professional']), axis=1)

columnas_a_comparar = [
    ('doc_type', 'TIPO DE DOCUMENTO', 'Tipo de Documento'),
    ('first_name', 'NOMBRES \n(NOMBRE 1 Y 2)', 'Nombres'),
    ('last_name', 'APELLIDOS_COMPLETOS', 'Apellidos'),
    ('phone', 'TELÉFONO DE CONTACTO ', 'Teléfono'),
    ('address_street', 'DIRECCIÓN DE RESIDENCIA', 'Dirección'),
    ('email', 'CORREO ELECTRÓNICO ', 'Correo'),
    ('orientadora_extraida', 'ORIENTADORA ', 'Orientadora'),
    ('reason', 'PRINCIPAL BARRERA IDENTIFICADA', 'Barrera Identificada'),
    ('observation', 'CONCEPTO DE ORIENTACIÓN (DESCRIPCIÓN IGUAL AL REGISTRADO EN LA PLATAFORMA AUTORIZADA SPE)', 'Concepto Orientación')
]

discrepancias = []

for index, row_fcs in consolidado_fcs.iterrows():
    doc_id = row_fcs['documento_clean']
    
    orientador = row_fcs.get('ORIENTADOR/A', row_fcs.get('ORIENTADORA ', 'NO REGISTRADO'))
    if pd.isna(orientador) or str(orientador).strip() == "":
        orientador = 'NO REGISTRADO'
    
    kuepa_matches = df_empleo[df_empleo['doc_number_clean'] == doc_id]
    
    if kuepa_matches.empty:
        discrepancias.append({
            'Documento': doc_id, 'Orientador/a': str(orientador).strip(),
            'Dato a usar (KUEPA)': 'FALTA EN KUEPA (No cruzó)', 'Dato original (FCS)': 'PRESENTE EN FCS'
        })
        continue 
    
    errores_kuepa = [] 
    errores_fcs = []
    
    row_empleo_gen = kuepa_matches.iloc[-1]
    
    if str(row_empleo_gen['fecha_nac_clean']) != str(row_fcs['fecha_nac_clean']):
        errores_kuepa.append(f"Fecha Nacimiento: {row_empleo_gen['fecha_nac_clean']}")
        errores_fcs.append(f"Fecha Nacimiento: {row_fcs['fecha_nac_clean']}")

    for col_empleo, col_fcs, nombre_campo in columnas_a_comparar:
        valor_empleo = limpiar_texto(row_empleo_gen[col_empleo])
        valor_fcs = limpiar_texto(row_fcs[col_fcs])
        
        if nombre_campo == 'Tipo de Documento':
            valor_fcs = mapa_documentos.get(valor_fcs, valor_fcs)
            valor_empleo = mapa_documentos.get(valor_empleo, valor_empleo)
            
        if nombre_campo == 'Barrera Identificada':
            norm_empleo = normalizar_barrera(valor_empleo)
            norm_fcs = normalizar_barrera(valor_fcs)
            if norm_empleo == norm_fcs:
                continue
            if norm_empleo == "" and norm_fcs == "NO APLICA":
                continue 
                
        if nombre_campo == 'Concepto Orientación':
            puro_empleo = re.sub(r'[\W_]+', '', valor_empleo)
            puro_fcs = re.sub(r'[\W_]+', '', valor_fcs)
            similitud = difflib.SequenceMatcher(None, puro_empleo, puro_fcs).ratio()
            if similitud >= 0.95: 
                continue 

        if nombre_campo == 'Dirección':
            if normalizar_direccion(valor_empleo) == normalizar_direccion(valor_fcs):
                continue 
                
        if nombre_campo == 'Orientadora':
            valor_empleo = valor_empleo.replace("DIANA VALBUENA", "CAROLINA VALBUENA")
            valor_fcs = valor_fcs.replace("DIANA VALBUENA", "CAROLINA VALBUENA")
            if valor_empleo == valor_fcs:
                continue
        
        if valor_empleo != valor_fcs:
            val_kuepa = valor_empleo if valor_empleo != "" else "VACÍO EN KUEPA"
            val_fcs = valor_fcs if valor_fcs != "" else "VACÍO EN FCS"
            errores_kuepa.append(f"{nombre_campo}: {val_kuepa}")
            errores_fcs.append(f"{nombre_campo}: {val_fcs}")

    fcs_slots = []
    for i in ["", ".1", ".2"]:
        num = 1 if i == "" else (2 if i == ".1" else 3)
        fcs_nit_col = f'NIT CON DÍGITO DE VERIFICACIÓN\nUsar Guión ( - ) para el DV{i}'
        if fcs_nit_col not in row_fcs:
             fcs_nit_col = f'NIT (CON DÍGITO DE VERIFICACIÓN){i}'
        
        id_val = limpiar_texto(row_fcs.get(f'CÓDIGO DE VACANTE No {num}', ''))
        cargo_val = limpiar_texto(row_fcs.get(f'NOMBRE DEL CARGO{i}', ''))
        empresa_val = limpiar_texto(row_fcs.get(f'NOMBRE DE LA EMPRESA{i}', ''))
        
        if id_val or cargo_val or empresa_val:
            fcs_slots.append({
                'slot_num': num,
                'id': id_val,
                'cargo': cargo_val,
                'empresa': empresa_val,
                'nit': limpiar_texto(row_fcs.get(fcs_nit_col, '')),
                'sector': limpiar_texto(row_fcs.get(f'SECTOR AL QUE PERTENECE LA EMPRESA{i}', ''))
            })

    matched_fcs_slots = set()
    vacantes_unicas = kuepa_matches.drop_duplicates(subset=['job_offer_id', 'company_name'])

    for _, job_row in vacantes_unicas.iterrows():
        k_id = limpiar_texto(job_row['job_offer_id'])
        k_cargo = limpiar_texto(job_row['job_offer_name'])
        k_empresa = limpiar_texto(job_row['company_name'])
        k_nit = limpiar_texto(job_row['nit'])
        k_sector = limpiar_texto(job_row['sector_name'])
        
        if not k_id and not k_empresa:
            continue
            
        best_slot = None
        
        for slot in fcs_slots:
            if slot['slot_num'] in matched_fcs_slots: continue
            if k_id and slot['id'] == k_id:
                best_slot = slot
                break
        
        if not best_slot:
            for slot in fcs_slots:
                if slot['slot_num'] in matched_fcs_slots: continue
                if k_empresa and slot['empresa'] == k_empresa:
                    best_slot = slot
                    break
                    
        if not best_slot:
            for slot in fcs_slots:
                if slot['slot_num'] in matched_fcs_slots: continue
                if k_cargo and slot['cargo'] and (k_cargo in slot['cargo']):
                    best_slot = slot
                    break
        
        if best_slot:
            matched_fcs_slots.add(best_slot['slot_num'])
            prefix = f"[Vacante {best_slot['slot_num']}] "
            
            if k_id != best_slot['id']:
                errores_kuepa.append(f"{prefix}ID Vacante: {k_id if k_id else 'VACÍO'}")
                errores_fcs.append(f"{prefix}ID Vacante: {best_slot['id'] if best_slot['id'] else 'VACÍO'}")
            
            if k_cargo and (k_cargo not in best_slot['cargo']):
                errores_kuepa.append(f"{prefix}Cargo: {k_cargo}")
                errores_fcs.append(f"{prefix}Cargo: {best_slot['cargo'] if best_slot['cargo'] else 'VACÍO'}")
            
            if k_empresa != best_slot['empresa']:
                errores_kuepa.append(f"{prefix}Empresa: {k_empresa if k_empresa else 'VACÍO'}")
                errores_fcs.append(f"{prefix}Empresa: {best_slot['empresa'] if best_slot['empresa'] else 'VACÍO'}")
            
            if k_nit != best_slot['nit']:
                errores_kuepa.append(f"{prefix}NIT: {k_nit if k_nit else 'VACÍO'}")
                errores_fcs.append(f"{prefix}NIT: {best_slot['nit'] if best_slot['nit'] else 'VACÍO'}")
            
            if k_sector != best_slot['sector']:
                errores_kuepa.append(f"{prefix}Sector: {k_sector if k_sector else 'VACÍO'}")
                errores_fcs.append(f"{prefix}Sector: {best_slot['sector'] if best_slot['sector'] else 'VACÍO'}")
                
        else:
            val_k_desc = f"ID:{k_id} | Cargo:{k_cargo} | Emp:{k_empresa} | NIT:{k_nit} | Sec:{k_sector}"
            errores_kuepa.append(f"Falta reportar vacante de KUEPA en FCS: {val_k_desc}")
            errores_fcs.append("Vacante NO REPORTADA en las 3 opciones de FCS")

    if errores_kuepa:
        discrepancias.append({
            'Documento': doc_id,
            'Orientador/a': str(orientador).strip(),
            'Dato a usar (KUEPA)': ' | '.join(errores_kuepa),
            'Dato original (FCS)': ' | '.join(errores_fcs)
        })

df_reporte = pd.DataFrame(discrepancias)

nombre_hoja = os.getenv('CONSOLIDADO')
hoja_reporte = client.open_by_key(nombre_hoja)
data = hoja_reporte.worksheet("SUBSANACIONES_KUEPA_EMPLEO")


data.batch_clear(['A2:Z'])

if not df_reporte.empty:
    datos_a_subir = df_reporte.values.tolist()
    _ = data.update(range_name='A2', values=datos_a_subir)
    print(f"¡Sincronización exitosa! Se actualizaron {len(df_reporte)} registros en la pestaña '{data.title}'.")
else:
    print("¡Sincronización exitosa! Cero discrepancias encontradas.")

fecha_hoy = datetime.today()

print(f"Reporte de subsanaciones generado. Última Actualización {fecha_hoy}")