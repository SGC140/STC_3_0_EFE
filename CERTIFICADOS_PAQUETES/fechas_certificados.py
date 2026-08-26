import pandas as pd
import os
import re
import time
import pydrive2
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import PyPDF2
from dotenv import load_dotenv, find_dotenv 

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
json_credentials = os.path.join(ruta_boveda, "credentials_module.json")
json_client = os.path.join(ruta_boveda, "client_secrets.json")

credentials_drive = json_credentials

def loggin_drive():
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile(credentials_drive)
    if gauth.access_token_expired:
        gauth.Refresh() 
        gauth.SaveCredentialsFile(credentials_drive)
    else:
        gauth.Authorize()  
    return GoogleDrive(gauth)
   
drive = loggin_drive()


scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]
Credenciales = ServiceAccountCredentials.from_json_keyfile_name(json_plexus, scope)
client = gspread.authorize(Credenciales) 

load_dotenv(override=True)
documento = os.getenv("consolidado_formacion")
sheets = client.open_by_key(documento)
hoja = sheets.worksheet('CERTIFICADOS')
datos = hoja.get_all_values()
df = pd.DataFrame(datos[1:], columns=datos[0])
df = df[df['DOCUMENTO'] != ""]

nombre_temporal = 'temp_certificado.pdf'
total_filas = len(df)

patron_blindado = r"entre\s*el\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*y\s*el\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})"

print(f"Iniciando procesamiento de {total_filas} registros...")

for index, fila in df.iterrows():
    cedula = fila.get('DOCUMENTO', '')
    link = fila.get('Merged Doc URL - CERTIFICADOS', '')
    fecha_existente = fila.get('FECHA FINALIZACIÓN', '')

    if str(fecha_existente).strip() != "":
        print(f"[{index + 1}/{total_filas}] Cédula {cedula}: Ya tiene fecha registrada. Saltando...")
        continue

    if not cedula or not link or str(link).strip() == "":
        print(f"[{index + 1}/{total_filas}] Registro sin cédula o link válido. Saltando...")
        continue

    match_id = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
    if not match_id:
        print(f"[{index + 1}/{total_filas}] Cédula {cedula}: Link de Drive inválido.")
        continue
        
    file_id = match_id.group(1)
    fecha_fin_nueva = None

    print(f"[{index + 1}/{total_filas}] Descargando PDF para cédula {cedula}...")

    max_intentos = 3
    for intento in range(max_intentos):
        try:
            time.sleep(1) 
            
            archivo = drive.CreateFile({'id': file_id})
            archivo.GetContentFile(nombre_temporal)

            texto_pdf = ""
            with open(nombre_temporal, 'rb') as f:
                lector = PyPDF2.PdfReader(f)
                for pagina in lector.pages:
                    ext = pagina.extract_text()
                    if ext:
                        texto_pdf += ext + " "

            texto_pdf = re.sub(r'\s+', ' ', texto_pdf).strip()

            match_fecha = re.search(patron_blindado, texto_pdf, re.IGNORECASE)
            if match_fecha:
                fecha_fin_nueva = match_fecha.group(2)
                print(f"   -> Fecha encontrada con éxito: {fecha_fin_nueva}")
            else:
                print(f"   -> Advertencia: No se halló el patrón de fecha.")

                print(f"   -> PyPDF2 leyó esto: '{texto_pdf[:300]}'...")
            
            break 
                
        except Exception as e:
            print(f"   -> Intento {intento + 1} fallido: {e}")
            time.sleep(2)
            
        finally:

            if os.path.exists(nombre_temporal):
                try:
                    os.remove(nombre_temporal)
                except PermissionError:
                    pass
            

    if fecha_fin_nueva:
        try:
            celda_match = hoja.find(str(cedula))
            if celda_match:
                row = celda_match.row

                _ = hoja.update(range_name=f'N{row}', values=[[fecha_fin_nueva]])
                print(f"   -> ¡Éxito! Celda N{row} actualizada en Google Sheets.")
                
        except gspread.exceptions.CellNotFound:
            print(f"   -> ⚠ La cédula {cedula} no se encontró en la hoja de Sheets.")
        except Exception as e:
            print(f"   -> Error al actualizar Sheets: {e}")

print("\n¡Proceso de extracción y actualización finalizado con éxito!")