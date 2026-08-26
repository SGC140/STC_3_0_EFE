import pandas as pd
import os
import re
import time
from dotenv import load_dotenv, find_dotenv
import pydrive2
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import PyPDF2
import glob
from PIL import Image

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

documento = os.getenv("consolidado_formacion")
sheets = client.open_by_key(documento)
hoja = sheets.worksheet('CERTIFICADOS')

datos = hoja.get_all_values()
df = pd.DataFrame(datos[1:], columns=datos[0])
df = df[df['DOCUMENTO'] != ""]
df_pantallazos = df[df['PANTALLAZO'] == ""]
print(df_pantallazos)

cedulas_pendientes = df_pantallazos['DOCUMENTO'].astype(str).tolist()

carpeta_pantallazos = os.getenv("carpeta_pantallazos")
query_drive = f"'{carpeta_pantallazos}' in parents and trashed=false"
pantallazos = drive.ListFile({'q': query_drive}).GetList()

for archivo in pantallazos:
    nombre_archivo = archivo['title']
    user = str(nombre_archivo).split("_")[0]
    
    if user not in cedulas_pendientes:
        continue
        
    link = f"https://drive.google.com/file/d/{archivo['id']}/view"
    
    try:
        celda_match = hoja.find(user)
        if celda_match:
            row = celda_match.row
            _ = hoja.update(range_name=f'O{row}', values=[[link]])
            print(f"Exito. Celda O{row} actualizada para el pantallazo del documento {user}.")
            
    except gspread.exceptions.CellNotFound:
        print(f"El documento {user} no se encontro en la hoja de Sheets.")
    except Exception as e:
        print(f"Error al actualizar el documento {user}: {e}")
    
    time.sleep(1.5)

print("Actualizaciones de Pantallazos finalizadas")

datos = hoja.get_all_values()
df = pd.DataFrame(datos[1:], columns=datos[0])
df = df[df['DOCUMENTO'] != ""]
df_paquetes = df[df['PANTALLAZO'] != ""]
df_paquetes = df_paquetes[df_paquetes["PAQUETE - FORMACIÓN"] == ""] 
df_paquetes = df_paquetes[df_paquetes["ESTADO"] == "CERTIFICADO"]

carpeta_paquetes = os.getenv("carpeta_paquetes")

for indice, fila in df_paquetes.iterrows():
    usuario = fila['DOCUMENTO']
    certificado_url = fila["Merged Doc URL - CERTIFICADOS"]
    pantallazo_url = fila["PANTALLAZO"]
    match_cert = re.search(r'/d/([a-zA-Z0-9_-]+)/view', certificado_url)
    match_pant = re.search(r'/d/([a-zA-Z0-9_-]+)/view', pantallazo_url)
    if not match_cert or not match_pant:
        print(f"Error extrayendo IDs de las URLs para el documento {usuario}.")
        continue
    id_cert = match_cert.group(1)
    id_pant = match_pant.group(1)

    try:
        archivo_cert = drive.CreateFile({'id': id_cert})
        archivo_cert.GetContentFile('temp_cert.pdf')
        archivo_pant = drive.CreateFile({'id': id_pant})
        archivo_pant.GetContentFile('temp_pant.img')
        imagen = Image.open('temp_pant.img')
        if imagen.mode != 'RGB':
            imagen = imagen.convert('RGB')
        imagen.save('temp_pant.pdf')
        merger = PyPDF2.PdfMerger()
        merger.append('temp_cert.pdf')
        merger.append('temp_pant.pdf')
        nombre_final = f"{usuario}_CONSOLIDADO.pdf"
        merger.write(nombre_final)
        merger.close()

        nuevo_archivo = drive.CreateFile({
            'title': nombre_final, 
            'parents': [{'id': carpeta_paquetes}]
        })
        nuevo_archivo.SetContentFile(nombre_final)
        nuevo_archivo.Upload()      
        link_consolidado = f"https://drive.google.com/file/d/{nuevo_archivo['id']}/view"
        celda_match = hoja.find(str(usuario))
        if celda_match:
            row = celda_match.row
            _ = hoja.update(range_name=f'P{row}', values=[[link_consolidado]])
            print(f"Exito. Celda P{row} actualizada para el paquete del documento {usuario}.")

    except gspread.exceptions.CellNotFound:
        print(f"El documento {usuario} no se encontro en la hoja de Sheets.")
    except Exception as e:
        print(f"Error al procesar el paquete para {usuario}: {e}")
    finally:
            archivos_temporales = ['temp_cert.pdf', 'temp_pant.img', 'temp_pant.pdf', f"{usuario}_CONSOLIDADO.pdf"]
            for f_temp in archivos_temporales:
                if os.path.exists(f_temp):
                    try:
                        os.remove(f_temp)
                    except Exception:
                        continue

    time.sleep(1.5)

temporales = glob.glob("*_CONSOLIDADO.pdf")
for temporal in temporales:
    os.remove(temporal)


