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
documento_orientacion = os.getenv("documento_orientacion")

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(credenciales, scopes=scopes)
client_sheets = gspread.authorize(creds)

orientaciones = client_sheets.open_by_key(documento_orientacion)
hojas_orientaciones = orientaciones.worksheets()
hojas_descartadas = ['JCO', 'Perfil Ocupacional', 'Base remision', 'Coreecion FSC', 'registro ', 'orientacion', 
                    'Intermediacion', 'perfiles ', 'Mitigacion', 'remision ', ' LISTA DATOS', 'CONTROL DE FALTANTES', 'REPORTE FCS - SIS']
consolidado_orientaciones = []
total_hojas = []
for hoja in hojas_orientaciones:
    if 'GESTIÓN' not in hoja.title and 'ATENCIONES' not in hoja.title and 'CITACIÓN' not in hoja.title and 'CONSOLIDADO' not in hoja.title and 'FORMACIÓN' not in hoja.title:
        if hoja.title not in hojas_descartadas:     
            datos = hoja.get_all_values()
            df = pd.DataFrame(datos[6:], columns=datos[5])
            df.columns = df.columns.astype(str).str.strip().str.upper()
            if 'NÚMERO DE DOCUMENTO' in df.columns:
                df = df[df['NÚMERO DE DOCUMENTO'] != ""]
                df['ORIENTADOR/A'] = hoja.title
                total_hojas.append(df)


df_consolidado = pd.concat(total_hojas, ignore_index=True)
df_consolidado = df_consolidado.fillna("")
df_consolidado.to_csv("CSV.csv")
datos_update = df_consolidado.values.tolist()

hoja_destino = orientaciones.worksheet('CONSOLIDADO')

_ = hoja_destino.batch_clear(["A7:ZZ"])
_ = hoja_destino.update(values=datos_update, range_name='A7')

print("PROCESO FINALIZADO")

