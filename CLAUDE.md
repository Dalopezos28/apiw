# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Descripción

Servicio FastAPI desplegado en Railway que actúa como middleware entre la WhatsApp Business API de Meta y tres sistemas internos:

1. **Incapacidades** — Lee Google Sheets y envía reportes diarios por WhatsApp (scheduler interno)
2. **Compras/boletín** — Recibe llamadas HTTP desde `boletin_semanal` y envía notificación con plantilla WhatsApp
3. **Calidad** — Webhook que recibe mensajes entrantes de WhatsApp, detecta cédulas y llama al ERP para generar certificados

## Entorno

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Variables de entorno requeridas (todas en `main.py`):

| Variable | Uso |
|---|---|
| `WHATSAPP_TOKEN` | Bearer token de WhatsApp Business API |
| `PHONE_NUMBER_ID` | ID del número de teléfono en Meta |
| `VERIFY_TOKEN` | Token para validar el webhook de Meta |
| `DESTINATARIO` | Número(s) destino para reportes de incapacidades (separados por coma) |
| `GOOGLE_CREDS_JSON` | Service account JSON para leer Google Sheets |
| `COMPRAS_API_KEY` | Clave para autenticar llamadas desde `boletin_semanal` |
| `COMPRAS_DESTINATARIO` | Número(s) destino para notificaciones de compras (separados por coma) |
| `ERP_URL` | URL base del ERP de calidad |
| `ERP_API_KEY` | Clave para el ERP de calidad |

## Arquitectura

Todo el código vive en un único archivo `main.py`. Los tres dominios conviven en el mismo proceso:

### 1. Incapacidades (scheduler)
`AsyncIOScheduler` (APScheduler) ejecuta `enviar_reporte_whatsapp` a las 9:00 AM y 8:00 PM (hora Colombia). La función lee la última fila de la hoja `"BD Incapacidades"` del Google Sheet `SHEET_ID` (hardcodeado), calcula días restantes de la columna K y envía la plantilla `reporte_incapacidad_diario` o `hello_world`.

### 2. Compras/boletín — endpoints HTTP

- `POST /compras/notify` — Envía texto libre. Autenticado con header `x-compras-secret`.
- `POST /compras/notify-template` — Envía la plantilla `cavasa_boletin_mensual` (header: `mes`; body: `pdfs`, `registros`, `reemplazos`; botón URL: `file/d/{file_id}/view`). Autenticado con header `x-compras-secret`.
- `GET /compras/notify-template/test` — Envía la plantilla con datos de prueba.

La autenticación compara el header `x-compras-secret` con `COMPRAS_API_KEY`.

### 3. Calidad — webhook WhatsApp

- `GET /webhook` — Validación de Meta (devuelve `hub.challenge` si `hub.verify_token` coincide con `VERIFY_TOKEN`).
- `POST /webhook` — Recibe mensajes entrantes. Si el texto del mensaje es una cédula colombiana (6-12 dígitos), llama a `procesar_solicitud_certificado` como tarea async. Esta función hace `POST {ERP_URL}/calidad/api/whatsapp/generar/` con `{"cedula": cedula}` y responde al remitente con el link del certificado o un mensaje de error.

## Despliegue

Heroku/Railway usando `Procfile`:
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```
Runtime: Python 3.11.

## Plantillas WhatsApp requeridas en Meta

- `hello_world` (en_US) — plantilla de prueba estándar de Meta
- `reporte_incapacidad_diario` (es) — 1 parámetro de body: texto del reporte
- `cavasa_boletin_mensual` (es_CO) — header: `{{mes}}`; body: `{{pdfs}}`, `{{registros}}`, `{{reemplazos}}`; botón URL dinámico con sufijo `file/d/{file_id}/view`
