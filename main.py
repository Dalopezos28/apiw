import os
import json
import gspread
import httpx
from datetime import datetime
from fastapi import FastAPI, Request, Response, Query
from apscheduler.schedulers.background import BackgroundScheduler
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
        
        # Accedemos específicamente a la pestaña "BD Incapacidades"
        sheet = client.open_by_key(SHEET_ID).worksheet("BD Incapacidades")
        
        # Obtenemos todos los registros para encontrar el último
        registros = sheet.get_all_values()
        
        if len(registros) <= 1:
            return "No hay registros disponibles en la base de datos."

        # Tomamos la última fila
        ultima_fila = registros[-1]
        hoy = datetime.now()

        try:
            nombre = ultima_fila[0] if ultima_fila[0] else "Sin Nombre"
            fecha_fin_str = ultima_fila[10] # Columna K
            
            if not fecha_fin_str:
                return f"El último registro ({nombre}) no tiene fecha de fin."
            
            fecha_fin = datetime.strptime(fecha_fin_str, "%d/%m/%Y")
            diferencia = (fecha_fin - hoy).days + 1
            
            if diferencia >= 0:
                return f"• {nombre}: faltan {diferencia} días."
            else:
                return f"• {nombre}: incapacidad vencida hace {abs(diferencia)} días."
                
        except Exception as e:
            return f"Error procesando los datos de la última fila: {e}"
    
    except Exception as e:
        return f"Error conectando con la pestaña BD Incapacidades: {e}"

async def enviar_reporte_whatsapp():
    reporte = obtener_ultimo_registro_incapacidad()
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Usando la plantilla sencilla que definimos
    data = {
        "messaging_product": "whatsapp",
        "to": DESTINATARIO,
        "type": "template",
        "template": {
            "name": "reporte_incapacidad_diario",
            "language": { "code": "es" },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        { "type": "text", "text": reporte }
                    ]
                }
            ]
        }
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(url, headers=headers, json=data)
        print(f"Envío de reporte (Último registro): {res.status_code}")

# --- PROGRAMADOR ---
scheduler = BackgroundScheduler()
scheduler.add_job(enviar_reporte_whatsapp, 'cron', hour=9, minute=0, timezone='America/Bogota')
scheduler.start()

# --- RUTAS ---
@app.get("/webhook")
async def validar_webhook(token: str = Query(alias="hub.verify_token"), challenge: str = Query(alias="hub.challenge")):
    if token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Error", status_code=403)

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    return {"status": "recibido"}

@app.get("/")
def home():
    return {"status": "Bot CHVS Online", "pestaña": "BD Incapacidades"}