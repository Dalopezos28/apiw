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

def obtener_datos_incapacidad():
    try:
        # Carga credenciales desde la variable de entorno para mayor seguridad
        creds_json = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        client = gspread.authorize(creds)
        
        # Abrir el libro y la primera hoja
        sheet = client.open_by_key(SHEET_ID).sheet1
        registros = sheet.get_all_values()
        
        mensajes = []
        hoy = datetime.now()

        # Procesar filas (saltando cabecera)
        for fila in registros[1:]:
            try:
                # Columnas J (índice 9) y K (índice 10) -> dd/mm/yyyy
                nombre = fila[0] if fila[0] else "Sin Nombre"
                fecha_fin_str = fila[10]
                
                if not fecha_fin_str:
                    continue
                
                fecha_fin = datetime.strptime(fecha_fin_str, "%d/%m/%Y")
                # Calculamos la diferencia
                diferencia = (fecha_fin - hoy).days + 1
                
                if diferencia >= 0:
                    mensajes.append(f"• {nombre}: faltan {diferencia} días.")
                else:
                    mensajes.append(f"• {nombre}: incapacidad vencida.")
            except Exception as e:
                print(f"Error procesando fila de {fila[0] if fila else 'desconocido'}: {e}")
                
        return "\n".join(mensajes) if mensajes else "No hay registros de incapacidad vigentes."
    
    except Exception as e:
        return f"Error conectando con Google Sheets: {e}"

async def enviar_reporte_whatsapp():
    reporte = obtener_datos_incapacidad()
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Mensaje de texto plano (Requiere que el número sea real o el destinatario esté verificado)
    data = {
        "messaging_product": "whatsapp",
        "to": DESTINATARIO,
        "type": "text",
        "text": {
            "body": f"📋 *REPORTE DIARIO CHVS*\n\nConteo de días restantes de incapacidad:\n\n{reporte}"
        }
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(url, headers=headers, json=data)
        print(f"Envío de reporte: {res.status_code} - {res.text}")

# --- PROGRAMADOR (SCHEDULER) ---
scheduler = BackgroundScheduler()
# Se ejecuta a las 9:00 AM hora de Colombia
scheduler.add_job(enviar_reporte_whatsapp, 'cron', hour=9, minute=0, timezone='America/Bogota')
scheduler.start()

# --- RUTAS DEL WEBHOOK ---
@app.get("/webhook")
async def validar_webhook(
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge")
):
    if token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Error de token", status_code=403)

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    data = await request.json()
    # Aquí puedes añadir lógica para responder mensajes entrantes
    print(f"Evento recibido en Webhook: {data}")
    return {"status": "recibido"}

@app.get("/")
def home():
    return {"status": "Bot Corporación CHVS Activo", "sistema": "Monitoreo de Incapacidades"}