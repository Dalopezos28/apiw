import os
import json
import gspread
import httpx
from datetime import datetime
from fastapi import FastAPI, Request, Response, Query, Header, HTTPException
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google.oauth2.service_account import Credentials

app = FastAPI()

# --- CONFIGURACIÓN ---
TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
DESTINATARIO = os.getenv("DESTINATARIO")
SHEET_ID = "1nmqZoDmBJZPBMaSS0vOuz7dYNlfe-jZBV5rPQ67ms9g"

# Integración ERP Calidad — certificados por WhatsApp
ERP_URL = os.getenv("ERP_URL", "").rstrip("/")     # ej: https://erp-chvs.up.railway.app
ERP_API_KEY = os.getenv("ERP_API_KEY", "")         # igual a CALIDAD_WA_API_KEY en el ERP

# --- COMPRAS / BOLETÍN SEMANAL ---
COMPRAS_API_KEY = os.getenv("COMPRAS_API_KEY", "")  # API key para autenticar llamadas desde COMPRAS
COMPRAS_DESTINATARIO = os.getenv("COMPRAS_DESTINATARIO", "")  # Número(s) destino, separados por coma


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

# --- CERTIFICADOS CALIDAD (integración ERP) ---

def _es_cedula(texto: str) -> bool:
    """Retorna True si el texto parece una cédula colombiana (6-12 dígitos)."""
    t = texto.strip()
    return t.isdigit() and 6 <= len(t) <= 12


async def enviar_mensaje_texto(numero: str, mensaje: str):
    """Envía un mensaje de texto libre por WhatsApp (sin plantilla)."""
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": mensaje},
    }
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(url, headers=headers, json=data)
            print(f"Respuesta certificado a {numero}: {res.status_code} | {res.text}")
        except Exception as e:
            print(f"Error enviando respuesta a {numero}: {e}")


async def procesar_solicitud_certificado(numero: str, cedula: str):
    """Llama al ERP para generar el certificado y responde al usuario por WhatsApp."""
    if not ERP_URL or not ERP_API_KEY:
        await enviar_mensaje_texto(
            numero,
            "⚠️ El servicio de certificados no está configurado. Contacta al administrador."
        )
        return

    endpoint = f"{ERP_URL}/calidad/api/whatsapp/generar/"
    headers = {
        "Content-Type": "application/json",
        "X-CALIDAD-API-KEY": ERP_API_KEY,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.post(endpoint, headers=headers, json={"cedula": cedula})
        except Exception as e:
            print(f"Error llamando al ERP para cédula {cedula}: {e}")
            await enviar_mensaje_texto(
                numero,
                "❌ No se pudo conectar con el sistema. Intenta más tarde."
            )
            return

    if res.status_code == 200:
        datos = res.json()
        nombre = datos.get("nombre", "")
        numero_cert = datos.get("numero", "")
        url_cert = datos.get("url_certificado", "")
        mensaje = (
            f"✅ ¡Hola {nombre}!\n\n"
            f"Tu certificado *{numero_cert}* está listo.\n\n"
            f"📄 Descárgalo aquí:\n{url_cert}"
        )
    elif res.status_code == 404:
        mensaje = (
            f"❌ No encontré ningún empleado con la cédula *{cedula}*.\n"
            "Verifica el número e intenta de nuevo."
        )
    else:
        mensaje = (
            "⚠️ Ocurrió un error generando el certificado. "
            "Contacta al área de calidad."
        )

    await enviar_mensaje_texto(numero, mensaje)


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

# --- COMPRAS: envío de notificaciones ---

class ComprasNotifyRequest(BaseModel):
    message: str


class ComprasTemplateRequest(BaseModel):
    mes: str        # ej: "Marzo 2026"
    pdfs: str       # ej: "4"
    registros: str  # ej: "312"
    reemplazos: str # ej: "87"
    file_id: str    # Drive file ID para el botón


async def _send_whatsapp_template(
    destinatarios: list[str],
    mes: str,
    pdfs: str,
    registros: str,
    reemplazos: str,
    file_id: str,
) -> list[dict]:
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    resultados = []
    async with httpx.AsyncClient() as client:
        for numero in destinatarios:
            data = {
                "messaging_product": "whatsapp",
                "to": numero,
                "type": "template",
                "template": {
                    "name": "cavasa_boletin_mensual",
                    "language": {"code": "es"},
                    "components": [
                        {
                            "type": "header",
                            "parameters": [{"type": "text", "text": mes}],
                        },
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": pdfs},
                                {"type": "text", "text": registros},
                                {"type": "text", "text": reemplazos},
                            ],
                        },
                        {
                            "type": "button",
                            "sub_type": "url",
                            "index": "0",
                            "parameters": [{"type": "text", "text": f"{file_id}/view"}],
                        },
                    ],
                },
            }
            try:
                res = await client.post(url, headers=headers, json=data, timeout=30)
                resultados.append({"numero": numero, "status": res.status_code, "response": res.text})
                print(f"COMPRAS template → {numero}: {res.status_code} | {res.text}")
            except Exception as e:
                resultados.append({"numero": numero, "error": str(e)})
                print(f"COMPRAS template error → {numero}: {e}")
    return resultados


@app.post("/compras/notify")
async def compras_notify(
    body: ComprasNotifyRequest,
    x_compras_secret: str = Header(default=""),
):
    if not COMPRAS_API_KEY or x_compras_secret != COMPRAS_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not COMPRAS_DESTINATARIO:
        raise HTTPException(status_code=500, detail="COMPRAS_DESTINATARIO not configured")

    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    destinatarios = [n.strip() for n in COMPRAS_DESTINATARIO.split(",") if n.strip()]
    resultados = []

    async with httpx.AsyncClient() as client:
        for numero in destinatarios:
            data = {
                "messaging_product": "whatsapp",
                "to": numero,
                "type": "text",
                "text": {"preview_url": False, "body": body.message},
            }
            try:
                res = await client.post(url, headers=headers, json=data, timeout=30)
                resultados.append({"numero": numero, "status": res.status_code})
                print(f"COMPRAS notify → {numero}: {res.status_code}")
            except Exception as e:
                resultados.append({"numero": numero, "error": str(e)})
                print(f"COMPRAS notify error → {numero}: {e}")

    return {"enviados": resultados}


@app.post("/compras/notify-template")
async def compras_notify_template(
    body: ComprasTemplateRequest,
    x_compras_secret: str = Header(default=""),
):
    if not COMPRAS_API_KEY or x_compras_secret != COMPRAS_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not COMPRAS_DESTINATARIO:
        raise HTTPException(status_code=500, detail="COMPRAS_DESTINATARIO not configured")

    destinatarios = [n.strip() for n in COMPRAS_DESTINATARIO.split(",") if n.strip()]
    resultados = await _send_whatsapp_template(
        destinatarios, body.mes, body.pdfs, body.registros, body.reemplazos, body.file_id
    )
    return {"enviados": resultados}


@app.get("/compras/notify-template/test")
async def compras_notify_template_test(
    x_compras_secret: str = Header(default=""),
):
    """Envía la plantilla con datos de prueba para verificar que funciona."""
    if not COMPRAS_API_KEY or x_compras_secret != COMPRAS_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not COMPRAS_DESTINATARIO:
        raise HTTPException(status_code=500, detail="COMPRAS_DESTINATARIO not configured")

    destinatarios = [n.strip() for n in COMPRAS_DESTINATARIO.split(",") if n.strip()]
    resultados = await _send_whatsapp_template(
        destinatarios,
        mes="Marzo 2026",
        pdfs="4",
        registros="312",
        reemplazos="87",
        file_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",  # placeholder Drive ID
    )
    return {"test": True, "enviados": resultados}


@app.get("/webhook")
async def validar_webhook(token: str = Query(alias="hub.verify_token"), challenge: str = Query(alias="hub.challenge")):
    if token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Error", status_code=403)

@app.post("/webhook")
async def recibir_mensaje(request: Request):
    try:
        data = await request.json()
        print(f"WEBHOOK payload: {json.dumps(data)}")

        # Extraer mensajes entrantes del payload de WhatsApp
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                mensajes = value.get("messages", [])
                print(f"WEBHOOK mensajes encontrados: {len(mensajes)}")
                for msg in mensajes:
                    tipo = msg.get("type")
                    texto = msg.get("text", {}).get("body", "").strip()
                    numero_remitente = msg.get("from", "")
                    print(f"WEBHOOK msg tipo={tipo} from={numero_remitente} texto={repr(texto)}")
                    if tipo == "text" and _es_cedula(texto):
                        import asyncio
                        asyncio.create_task(
                            procesar_solicitud_certificado(numero_remitente, texto)
                        )

        return Response(content="EVENT_RECEIVED", status_code=200)
    except Exception as e:
        print(f"Error procesando webhook: {e}")
        return Response(content="ERROR", status_code=400)