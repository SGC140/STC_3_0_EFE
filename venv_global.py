import os
import shutil
import subprocess

carpeta_maestra = os.getcwd()
ruta_venv_global = os.path.join(carpeta_maestra, "venv")
ruta_req_global = os.path.join(carpeta_maestra, "requirements.txt")
dependencias = set()

for carpeta in os.listdir(carpeta_maestra):
    ruta_carpeta = os.path.join(carpeta_maestra, carpeta)
    
    if os.path.isdir(ruta_carpeta) and carpeta not in ["venv", "config_seguridad", ".git", ".vscode"]:
        ruta_venv_local = os.path.join(ruta_carpeta, "venv")
        ruta_req_local = os.path.join(ruta_carpeta, "requirements.txt")
        
        if os.path.exists(ruta_venv_local):
            shutil.rmtree(ruta_venv_local)
            
        if os.path.exists(ruta_req_local):
            with open(ruta_req_local, "r", encoding="utf-8") as f:
                for linea in f:
                    if linea.strip():
                        dependencias.add(linea.strip())
            os.remove(ruta_req_local)

if dependencias:
    with open(ruta_req_global, "w", encoding="utf-8") as f:
        for dep in sorted(dependencias):
            f.write(dep + "\n")

if os.path.exists(ruta_venv_global):
    shutil.rmtree(ruta_venv_global)

subprocess.run(["python", "-m", "venv", "venv"], cwd=carpeta_maestra)

ruta_python_venv = os.path.join(carpeta_maestra, "venv", "Scripts", "python.exe")

if os.path.exists(ruta_req_global):
    subprocess.run([ruta_python_venv, "-m", "pip", "install", "-r", ruta_req_global], cwd=carpeta_maestra)