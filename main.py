from fastapi import FastAPI, Request, Response, Query
import httpx
import os

app = FastAPI()

# Estas variables las configuraremos en el panel de Railway
TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

@app.get("/")
def home():
    return {"status": "Bot Online", "project": "CHVS_WhatsApp_System"}

# Paso obligatorio para que Meta valide tu servidor
@app.get("/webhook")
async def validar_webhook(
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge")
):
    if token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Error de token", status_code=403)

# Aquí es donde llegarán los mensajes de los usuarios
@app.post("/webhook")
async def recibir_mensaje(request: Request):
    data = await request.json()
    
    try:
        # Extraemos el mensaje (ajustado a la estructura JSON de Meta)
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [{}])[0]
        
        if messages:
            telefono_cliente = messages.get("from")
            texto_recibido = messages.get("text", {}).get("body")
            
            print(f"Mensaje de {telefono_cliente}: {texto_recibido}")
            
            # Aquí podrías conectar tu lógica de Ciencia de Datos o Base de Datos
            # Por ahora, solo imprimimos en consola
            
    except Exception as e:
        print(f"Error procesando JSON: {e}")
        
    return {"status": "success"}