import requests

# Configuración de tus credenciales (Cópialas de tu panel de Meta)
TOKEN = "EAAUANJTEhCQBQktzGnxlKznORV1oyr3386iMFR9UjHXYA3zrh3FN9beLXLPfZB36j1qTPaw5CUWbyQxCmZAFSuvMU427xXSmyr5VB4k3jZBWi1vnueL2UXiTBrLhV5ZAnqsxW2Mkin7HXejV0dZAYjDvZCO9JOoxhwscjAa3BWm8rq36XjSSEOStx9iWleXWwwZCqyGf5owezpKVoQ7qcKkThLMMyVTuNcRWxKOaWj5on4nANMDi1h2D2EoPwOBAr1ZBRFCuitFBgSoGluMMDJMZBnAZDZD"
PHONE_NUMBER_ID = "990436387484180"  # Tomado de tu captura

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