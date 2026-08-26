from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import Response
from playwright.sync_api import sync_playwright

app = FastAPI()

class DatosHTML(BaseModel):
    html: str
    width: Optional[str] = "A4" 
    height: Optional[str] = "A4"

@app.post("/crear-pdf")
def crear_pdf(datos: DatosHTML):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()      
        page.set_content(datos.html)
        pdf_bytes = page.pdf(
            width=datos.width, 
            height=datos.height,
            print_background=True 
        )
        browser.close()
        
    return Response(content=pdf_bytes, media_type="application/pdf")