import os
import requests
from dotenv import load_dotenv # Necesitarás: pip install python-dotenv

load_dotenv() # Carga el archivo .env donde guardes tu TOKEN localmente

TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

def enviar_mensaje_prueba(destinatario):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Esta es la estructura de la plantilla "hello_world" de Meta
    data = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "template",
        "template": {
            "name": "hello_world",
            "language": {
                "code": "en_US"
            }
        }
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()

# Reemplaza con tu número personal (incluye código de país, ej: 57310...)
mi_numero = "573175003012" 
resultado = enviar_mensaje_prueba(mi_numero)
print(resultado)