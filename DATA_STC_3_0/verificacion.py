import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv, find_dotenv
import os

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

credenciales = json_plexus
documento_verificacion = os.getenv("documento_verificacion")

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(credenciales, scopes=scopes)
client_sheets = gspread.authorize(creds)

verificaciones = client_sheets.open_by_key(documento_verificacion)
hojas_verificacion = verificaciones.worksheets()
consolidado = [] 
for hoja in hojas_verificacion:
    nombre_hoja, id_hoja = hoja.title, hoja.id
    if 'Leads' not in nombre_hoja and 'General' not in nombre_hoja:
        datos = hoja.get_all_values()
        df = pd.DataFrame(datos[2:], columns=datos[1])
        df = df.dropna(subset='Número Documento')
        df = df[df['Número Documento'] != ""]
        df['Verificador'] = nombre_hoja
        if not df.empty:
            consolidado.append(df)

df_final = pd.concat(consolidado, ignore_index=True)
print(df_final)