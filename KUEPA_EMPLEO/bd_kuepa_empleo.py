from dotenv import load_dotenv, find_dotenv
import pandas as pd
import os
from datetime import datetime
import pydrive2
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import gspread
from oauth2client.service_account import ServiceAccountCredentials

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

scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

Credenciales = ServiceAccountCredentials.from_json_keyfile_name(json_plexus, scope)
client = gspread.authorize(Credenciales)    
drive = loggin_drive()
carpeta_kuepa_empleo = os.getenv("CARPETA_KUEPA_EMPLEO")
query_drive = f"'{carpeta_kuepa_empleo}' in parents and trashed=false"
archivos = drive.ListFile({'q': query_drive}).GetList()

metadata_total = []
for archivo in archivos:
    nombre_archivo = archivo['title']
    id_archivo = archivo['id']
    hora_archivo = archivo['createdDate']
    hora_actualizacion = archivo['modifiedDate']
    metadata = {"Nombre": nombre_archivo, "ID": id_archivo,  "Hora": hora_archivo,  "Hora_Actualización": hora_actualizacion}
    metadata_total.append(metadata)

metadata_df = pd.DataFrame(metadata_total)
metadata_df['Categoría'] = metadata_df['Nombre'].str.extract(r'(PROFILE|OFERTAS|LOCALIDADES)')
metadata_df['Hora'] = pd.to_datetime(metadata_df['Hora'])
metadata_df = metadata_df.sort_values(by='Hora', ascending=False).copy()
metadata_df = metadata_df.drop_duplicates(subset=['Categoría'], keep='first')

for indice, fila in metadata_df.iterrows():
    id = fila['ID']
    documento = fila['Categoría'] 
    if 'LOCALIDADES' in documento:
        localidades = fila['ID']
    elif 'OFERTAS' in documento:
        ofertas = fila['ID']
    elif 'PROFILE' in documento:
        profile = fila['ID']

data_localidades = client.open_by_key(localidades).worksheet("Hoja 1").get_all_values()
data_ofertas = client.open_by_key(ofertas).worksheet("Hoja 1").get_all_values()
data_kuepa_empleo = client.open_by_key(profile).worksheet("Hoja 1").get_all_values()

df = pd.DataFrame(data_kuepa_empleo[1:], columns=data_kuepa_empleo[0])
df_ofertas = pd.DataFrame(data_ofertas[1:], columns=data_ofertas[0])
df_ofertas = df_ofertas.drop_duplicates(subset='job_offer_id', keep='last')
df_localidades = pd.DataFrame(data_localidades[1:], columns=data_localidades[0])

df = df[df['curriculum_id'] != ""]
df = df[df["curriculum_id"].notna()]
df = df[df["curriculum_id"].notnull()]
df = df[df['id_curriculum'] != ""]
df = df[df["id_curriculum"].notna()]
df = df[df["id_curriculum"].notnull()]

df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
df = df.dropna(subset=['created_at'])

df['doc_number'] = df['doc_number'].astype(str).str.strip()
df_localidades['PROFILE_DOC_NUMBER'] = df_localidades['PROFILE_DOC_NUMBER'].astype(str).str.strip()

df = pd.merge(
    left = df, right= df_ofertas,
    how = 'left',
    left_on = 'profile_id', right_on='profile_id')
df = pd.merge(
    left=df, right=df_localidades,
    how = 'left',
    left_on='doc_number', right_on='PROFILE_DOC_NUMBER' 
)

df['created_at_x'] = pd.to_datetime(df['created_at_x'], errors='coerce')
excepciones = [
    'profile_id', 'occupational_interest', 'job_offer_id', 'job_offer_name', 
    'company_id', 'company_name', 'nit', 'sector_name', 'professional', 'created_at_x'
]
cols_a_actualizar = [columna for columna in df.columns if columna not in excepciones]
df_reciente = df.sort_values(by='created_at_x', ascending=False)
df_reciente = df_reciente.drop_duplicates(subset=['profile_id'], keep='first')
df_reciente = df_reciente[['profile_id'] + cols_a_actualizar]
df = df.drop(columns=cols_a_actualizar)
df = pd.merge(df, df_reciente, on='profile_id', how='left')

df = df[df['created_at_x'].dt.year >= 2026]

columnas_finales = ['doc_type','doc_number','first_name','last_name','birthdate','sex','phone','mobile_phone',
                    'address_street','location_in_bogota_answer_label','neighborhood','email','id_curriculum','curriculum_id','date',
                    'offerer','professional','reason','observation','remission_concept','created_at_x','occupational_interest',
                    'profile_id','job_offer_id','job_offer_name','company_id','company_name','nit','sector_name']

df.columns = df.columns.str.lower().str.strip()

df = df[columnas_finales]
df = df.rename(columns={'location_in_bogota_answer_label': 'localidad',
                        'created_at_x': 'created_at',
                        'profile_id_x': 'profile_id'})
df['Marc colocacion'] = None
df['curriculum_id'] = '100%'

df = df.sort_values(by='doc_number')

fecha_hoy = datetime.today()
fecha_formateada = fecha_hoy.strftime('%Y%m%d')

df = df.astype(str)
df = df.fillna("")
data_update = [df.columns.values.tolist()] + df.values.tolist()

_ = client.open_by_key(os.getenv("CONSOLIDADO")).worksheet("REPORTE_KUEPA_EMPLEO").clear()
_ = client.open_by_key(os.getenv("CONSOLIDADO")).worksheet("REPORTE_KUEPA_EMPLEO").update(range_name="A1", values=data_update)

print(f"Reporte de Kuepa empleo generado. Última Actualización {fecha_hoy}")
