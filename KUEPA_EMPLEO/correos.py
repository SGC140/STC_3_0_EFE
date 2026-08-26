import pandas as pd
import os
from dotenv import load_dotenv, find_dotenv
import pydrive2
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pdfkit
import requests
import base64

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

print(json_plexus)

# --- CONFIGURACIÓN DE WKHTMLTOPDF ---
ruta_wkhtmltopdf = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
try:
    config_pdfkit = pdfkit.configuration(wkhtmltopdf=ruta_wkhtmltopdf)
except Exception as e:
    print(f"Error cargando wkhtmltopdf: {e}")
    exit()

load_dotenv(override=True)
credentials_drive = json_credentials
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

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

Credenciales = ServiceAccountCredentials.from_json_keyfile_name(json_plexus, scope)
client = gspread.authorize(Credenciales) 

remitente = "sociostalentocapital3.0@kuepa.edu.co"
folder = "1eEa6dbqdzeg-gf_xDdk3Ef2MXyyd15Cs"
db = "1-mkew1k_3HJXRxMN7LYuHVIouxTbQny7vtLnUNGLVEU"

documento_sheet = client.open_by_key(db)
hoja_ws = documento_sheet.worksheet("Hoja 1")
datos = hoja_ws.get_all_values()

df = pd.DataFrame(datos[1:], columns=datos[0])

try:
    col_link = df.columns.get_loc("Link Correo") + 1
except KeyError:
    print("Error: No se encontró la columna 'Link Correo'.")
    exit()

# --- MAGIA BASE64 PARA LAS IMÁGENES ---
# Esto descarga las imágenes 1 vez y las vuelve código para que el PDF no falle jamás
def url_a_base64(url):
    try:
        respuesta = requests.get(url)
        respuesta.raise_for_status()
        b64 = base64.b64encode(respuesta.content).decode('utf-8')
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        print(f"Error descargando {url}: {e}")
        return ""

print("Descargando imágenes y convirtiendo a Base64...")
img_logo = url_a_base64("https://storage.googleapis.com/ket-bucket/bucket/U099Y5NS0Q4/Prueba/dad60c3e292a759087b0b4426927f08f.png")
img_mano = url_a_base64("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f44b.png")
img_chulo = url_a_base64("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/2705.png")
# --------------------------------------

print(f"Iniciando procesamiento de {len(df)} registros...")

opciones_pdf = {
    "encoding": "UTF-8",
    "quiet": "",
    "margin-top": "0mm",
    "margin-bottom": "0mm",
    "margin-right": "0mm",
    "margin-left": "0mm",
    "page-width": "210mm",
    "page-height": "400mm",
    "disable-smart-shrinking": "",
    "enable-local-file-access": "" 
}

for indice, fila in df.iterrows():
    documento = str(fila.get("Id de documento", ""))
    correo = fila.get("Email*", "")
    link = fila.get("Link Correo", "")

    if str(link).strip() != "":
        continue

    if not documento or not correo:
        continue
        
    temp_html = f"temp_{documento}.html"
    temp_pdf = f"temp_{documento}.pdf"

    fecha_actual = "Viernes, 10 de Julio de 2026"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <body style="margin: 0; padding: 20px; background-color: #ffffff; font-family: Arial, sans-serif;-webkit-font-smoothing: antialiased;">
        <div style="max-width: 600px; margin: 0 auto; color: #222;">
            
            <h2 style="font-weight: normal; margin-bottom: 20px; font-size: 22px;">Jóvenes con Oportunidades - Ruta de Empleo</h2>
            <div style="border-bottom: 1px solid #ddd; padding-bottom: 15px; margin-bottom: 25px;">
                <p style="margin: 2px 0; font-size: 14px;"><strong>Socios Talento Capital 3.0</strong> &lt;{remitente}&gt;</p>
                <p style="margin: 2px 0; color: #555; font-size: 13px;">Para: {correo}</p>
                <p style="margin: 2px 0; color: #555; font-size: 13px; text-align: right;">{fecha_actual}</p>
            </div>
            
            <table width="600" border="0" cellspacing="0" cellpadding="0" style="border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                <tr><td height="6" bgcolor="#D32F2F" style="font-size: 0; line-height: 0;">&nbsp;</td></tr>
                <tr>
                    <td bgcolor="#E65100" style="padding: 35px 40px; text-align: left;">
                        <h1 style="color: #ffffff; font-size: 24px; margin: 0; font-weight: bold; letter-spacing: 0.5px;">Jóvenes con Oportunidades</h1>
                        <p style="color: #FFCCBC; font-size: 13px; margin: 5px 0 0 0; text-transform: uppercase; letter-spacing: 1px; font-weight: bold;">Ruta de Empleo y Empleabilidad</p>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 40px 40px 30px 40px; background-color: #ffffff;">
                        <p style="font-size: 16px; color: #333333; line-height: 1.5; margin-top: 0; margin-bottom: 20px;">
                            Hola, <img src="{img_mano}" width="18" height="18" style="vertical-align: middle; margin-bottom: 3px;">
                        </p>
                        <p style="font-size: 15px; color: #4a4a4a; line-height: 1.6; margin-bottom: 20px;">Recibe un cordial saludo del equipo <strong>Socios Talento Capital 3.0</strong>.</p>
                        <p style="font-size: 15px; color: #4a4a4a; line-height: 1.6; margin-bottom: 20px;">A través de la ruta de empleo de la <strong>Secretaría Distrital de Desarrollo Económico</strong>, queremos acompañarte en tu participación en los componentes 2 y 3 del programa <strong>Jóvenes con Oportunidades</strong>, correspondientes a la formación en cursos cortos y a la empleabilidad, respectivamente.</p>
                        <p style="font-size: 15px; color: #4a4a4a; line-height: 1.6; margin-bottom: 30px;">Este proceso busca acompañarte de manera cercana en el ajuste de tu perfil laboral, la revisión de documentos y la identificación de posibles oportunidades de empleo de acuerdo con tu experiencia, intereses y disponibilidad.</p>
                        
                        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #FFF3E0; border-left: 4px solid #E65100; border-radius: 4px; margin-bottom: 30px;">
                            <tr>
                                <td style="padding: 25px 25px;">
                                    <h2 style="font-size: 15px; color: #D32F2F; margin-top: 0; margin-bottom: 15px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">Dentro de tu ruta recibirás acompañamiento en:</h2>
                                    <table width="100%" border="0" cellspacing="0" cellpadding="0">
                                        <tr><td valign="top" style="padding-bottom: 12px; font-size: 14.5px; color: #333333; line-height: 1.5;"><img src="{img_chulo}" width="16" height="16" style="vertical-align: middle; margin-right: 5px;"> Registro y actualización de hoja de vida.</td></tr>
                                        <tr><td valign="top" style="padding-bottom: 12px; font-size: 14.5px; color: #333333; line-height: 1.5;"><img src="{img_chulo}" width="16" height="16" style="vertical-align: middle; margin-right: 5px;"> <strong>Verificación documental:</strong> entrega y validación de documentos requeridos.</td></tr>
                                        <tr><td valign="top" style="padding-bottom: 12px; font-size: 14.5px; color: #333333; line-height: 1.5;"><img src="{img_chulo}" width="16" height="16" style="vertical-align: middle; margin-right: 5px;"> Orientación laboral.</td></tr>
                                        <tr><td valign="top" style="padding-bottom: 12px; font-size: 14.5px; color: #333333; line-height: 1.5;"><img src="{img_chulo}" width="16" height="16" style="vertical-align: middle; margin-right: 5px;"> Formación o fortalecimiento de habilidades, si aplica.</td></tr>
                                        <tr><td valign="top" style="padding-bottom: 12px; font-size: 14.5px; color: #333333; line-height: 1.5;"><img src="{img_chulo}" width="16" height="16" style="vertical-align: middle; margin-right: 5px;"> Remisión y preselección a vacantes, cuando tu perfil se ajuste a las oportunidades disponibles.</td></tr>
                                        <tr><td valign="top" style="font-size: 14.5px; color: #333333; line-height: 1.5;"><img src="{img_chulo}" width="16" height="16" style="vertical-align: middle; margin-right: 5px;"> Seguimiento con empresarios frente a las oportunidades gestionadas.</td></tr>
                                    </table>
                                </td>
                            </tr>
                        </table>

                        <p style="font-size: 15px; color: #4a4a4a; line-height: 1.6; margin-bottom: 20px;">También realizaremos una valoración de riesgo al desempleo, que nos permitirá caracterizar mejor tu situación y orientar el acompañamiento de acuerdo con tus necesidades. Esta valoración no define la asignación del paquete; se utiliza para orientar mejor la remisión y el acompañamiento.</p>
                        <p style="font-size: 15px; color: #4a4a4a; line-height: 1.6; margin-bottom: 20px;">Es importante tener presente que esta ruta busca aumentar tus posibilidades de acceso al empleo, fortalecer tu perfil y promover tu participación en oportunidades laborales. Sin embargo, la participación en el proceso no garantiza una contratación inmediata, una vacante fija o un empleo asegurado.</p>
                        <p style="font-size: 15px; color: #4a4a4a; line-height: 1.6; margin-bottom: 30px;">Te invitamos a confirmar tu participación respondiendo este correo con la frase: <strong>“Sí, confirmo mi participación en la ruta”</strong>.</p>
                        <p style="font-size: 15px; color: #4a4a4a; line-height: 1.6; margin-bottom: 5px;">Cordialmente,</p>
                        <p style="font-size: 15px; color: #333333; font-weight: bold; line-height: 1.6; margin-top: 0; margin-bottom: 0;">Equipo Socios Talento Capital 3.0</p>
                    </td>
                </tr>
                
                <tr>
                    <td style="background-color: #ffffff; padding: 30px 40px; border-top: 2px solid #f0f0f0;">
                        <table width="100%" border="0" cellspacing="0" cellpadding="0">
                            <tr>
                                <td width="150" align="left" valign="middle">
                                    <img src="{img_logo}" alt="kuepa EduTech" width="130" style="display: block; border: none; outline: none; text-decoration: none;">
                                </td>
                                <td width="20">&nbsp;</td>
                                <td align="left" valign="middle" style="font-family: Arial, sans-serif; font-size: 13px; color: #595959; line-height: 1.8;">
                                    T: +57 (601) 9180110<br>
                                    Cll 85 No. 19b-02. Bogotá DC, Colombia<br>
                                    <a href="http://www.kuepa.com" style="color: #595959; text-decoration: none;">www.kuepa.com</a> 
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </div>
    </body>
    </html>
    """
    
    link_pdf_drive = None
    print(f"\n--- Procesando Documento: {documento} ---")

    try:
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html_content)

        pdfkit.from_file(temp_html, temp_pdf, configuration=config_pdfkit, options=opciones_pdf)

        archivo_drive = drive.CreateFile({
            'title': f'Correo_{documento}.pdf', 
            'parents': [{'id': folder}]
        })
        archivo_drive.SetContentFile(temp_pdf)
        archivo_drive.Upload()
        
        link_pdf_drive = archivo_drive['alternateLink'] 
        print(f"  -> Éxito: PDF subido a Drive.")

    except Exception as e:
        print(f"  -> ❌ ERROR: {e}")
        
    finally:
        for archivo in [temp_html, temp_pdf]:
            if os.path.exists(archivo):
                try:
                    os.remove(archivo)
                except:
                    pass

    if link_pdf_drive:
        try:
            celda_match = hoja_ws.find(documento)
            if celda_match:
                hoja_ws.update_cell(celda_match.row, col_link, link_pdf_drive)
                print(f"  -> ✅ Sheet actualizado.")
        except Exception as e:
            print(f"  -> ❌ Error al escribir en Sheets: {e}")

print("\n¡Proceso finalizado!")