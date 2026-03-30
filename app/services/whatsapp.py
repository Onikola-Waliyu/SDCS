import os
import httpx
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

async def send_whatsapp_message(to: str, text: str):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(WHATSAPP_URL, json=payload, headers=headers)
        if response.status_code >= 400:
            print(f">>> WHATSAPP API ERROR: {response.text}")
        return response.json()
