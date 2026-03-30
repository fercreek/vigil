import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TELEGRAM_TOKEN")

print("--- Buscador de Chat ID ---")
print(f"Buscando el bot: @tradercreekbot")
print("Por favor, envía un mensaje desde tu Telegram al bot ahora mismo.")
print("Esperando 15 segundos...")

for i in range(15, 0, -1):
    print(f"{i}...", end=" ", flush=True)
    time.sleep(1)

print("\n\nRevisando actualizaciones...")

url = f"https://api.telegram.org/bot{token}/getUpdates"
r = requests.get(url)
data = r.json()

if data.get("ok") and data.get("result"):
    for update in data["result"]:
        if "message" in update:
            chat = update["message"]["chat"]
            print(f"¡Encontrado!")
            print(f"Nombre: {chat.get('first_name')} {chat.get('last_name', '')}")
            print(f"CHAT_ID: {chat['id']}")
            print("---")
else:
    print("No se encontraron mensajes. Asegúrate de:")
    print("1. Buscar @tradercreekbot en Telegram.")
    print("2. Presionar 'Iniciar' (Start) o enviar un mensaje.")
    print("3. Correr este script de nuevo.")
