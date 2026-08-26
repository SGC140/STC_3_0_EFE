import os
import ast
import sys
import subprocess

carpeta_maestra = os.getcwd()
librerias = set()
modulos_nativos = sys.stdlib_module_names

mapeo_nombres_pip = {
    "dotenv": "python-dotenv",
    "PIL": "Pillow"
}

for raiz, carpetas, archivos in os.walk(carpeta_maestra):
    carpetas[:] = [c for c in carpetas if c not in ["venv", "config_seguridad", ".git", ".vscode", "__pycache__"]]
    
    for archivo in archivos:
        if archivo.endswith(".py"):
            ruta_archivo = os.path.join(raiz, archivo)
            with open(ruta_archivo, "r", encoding="utf-8") as f:
                try:
                    arbol = ast.parse(f.read(), filename=archivo)
                    for nodo in ast.walk(arbol):
                        base = None
                        if isinstance(nodo, ast.Import):
                            for alias in nodo.names:
                                base = alias.name.split(".")[0]
                                if base and base not in modulos_nativos and base != "_ast":
                                    librerias.add(base)
                        elif isinstance(nodo, ast.ImportFrom):
                            if nodo.module:
                                base = nodo.module.split(".")[0]
                                if base and base not in modulos_nativos:
                                    librerias.add(base)
                except SyntaxError:
                    pass

librerias_finales = set()
for lib in librerias:
    librerias_finales.add(mapeo_nombres_pip.get(lib, lib))

ruta_req = os.path.join(carpeta_maestra, "requirements.txt")
with open(ruta_req, "w", encoding="utf-8") as f:
    for lib in sorted(librerias_finales):
        f.write(lib + "\n")

ruta_python_venv = os.path.join(carpeta_maestra, "venv", "Scripts", "python.exe")

if os.path.exists(ruta_req) and os.path.exists(ruta_python_venv):
    subprocess.run([ruta_python_venv, "-m", "pip", "install", "-r", ruta_req], cwd=carpeta_maestra)