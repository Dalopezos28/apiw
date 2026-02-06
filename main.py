import os
import json
import gspread
import httpx
from datetime import datetime
from fastapi import FastAPI, Request, Response, Query
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google.oauth2.service_account import Credentials

app = FastAPI()

# --- CONFIGURACIÓN ---
TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
DESTINATARIO = os.getenv("DESTINATARIO")
SHEET_ID = "1nmqZoDmBJZPBMaSS0vOuz7dYNlfe-jZBV5rPQ67ms9g"

def obtener_ultimo_registro_incapacidad():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key(SHEET_ID).worksheet("BD Incapacidades")
        registros = sheet.get_all_values()
        
        if len(registros) <= 1:
            return "No hay registros disponibles en la base de datos."

        ultima_fila = registros[-1]
        hoy = datetime.now()

        nombre = ultima_fila[0] if ultima_fila[0] else "Sin Nombre"
        fecha_fin_str = ultima_fila[10] # Columna K
        
        if not fecha_fin_str:
            return f"El último registro ({nombre}) no tiene fecha de fin."
        
        fecha_fin = datetime.strptime(fecha_fin_str, "%d/%m/%Y")
        diferencia = (fecha_fin - hoy).days + 1
        
        if diferencia >= 0:
            return f"• {nombre}: faltan {diferencia} días de incapacidad."
        else:
            return f"• {nombre}: incapacidad vencida hace {abs(diferencia)} días."
                
    except Exception as e:
        return f"Error conectando con Google Sheets: {e}"

async def enviar_reporte_whatsapp(usar_hello_world=False):
    reporte = obtener_ultimo_registro_incapacidad()
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    lista_destinatarios = [n.strip() for n in DESTINATARIO.split(",")]
    
    nombre_plantilla = "hello_world" if usar_hello_world else "reporte_incapacidad_diario"
    idioma = "en_US" if usar_hello_world else "es"

    async with httpx.AsyncClient() as client:
        for numero in lista_destinatarios:
            data = {
                "messaging_product": "whatsapp",
                "to": numero,
                "type": "template",
                "template": {
                    "name": nombre_plantilla,
                    "language": { "code": idioma }
                }
            }

            if not usar_hello_world:
                data["template"]["components"] = [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": reporte}]
                }]
            
            try:
                res = await client.post(url, headers=headers, json=data)
                print(f"Ejecución Programada - Envío a {numero}: {res.status_code}")
            except Exception as e:
                print(f"Error en envío programado a {numero}: {e}")

# --- PROGRAMADOR (AsyncIOScheduler) ---
scheduler = AsyncIOScheduler()

# Tarea 1: Prueba de hoy a las 8:00 PM (Hora Colombia)
scheduler.add_job(enviar_reporte_whatsapp, 'cron', hour=20, minute=0, timezone='America/Bogota')

# Tarea 2: Reporte oficial diario a las 9:00 AM (Hora Colombia)
scheduler.add_job(enviar_reporte_whatsapp, 'cron', hour=9, minute=0, timezone='America/Bogota')

scheduler.start()

# --- RUTAS ---

@app.get("/")
def home():
    return {"status": "Bot Corporación CHVS Activo", "horas_programadas": ["08:00 PM", "09:00 AM"]}

@app.get("/test-ahora")
async def disparar_prueba_manual():
    await enviar_reporte_whatsapp(usar_hello_world=False)
    return {"status": "Prueba manual ejecutada"}

@app.get("/webhook")
async def validar_webhook(token: str = Query(alias="hub.verify_token"), challenge: str = Query(alias="hub.challenge")):
    if token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Error", status_code=403)

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    try:
        data = await request.json()
        return Response(content="EVENT_RECEIVED", status_code=200)
    except Exception as e:
        return Response(content="ERROR", status_code=400)