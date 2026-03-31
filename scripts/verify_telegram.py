import os
import requests
from dotenv import load_dotenv

def test_telegram():
    load_dotenv()
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ Error: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no encontrados.")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🛡️ <b>VERIFICACIÓN DEL SISTEMA</b>\nEl Scalp Alert Bot está listo para operar. Conexión a Telegram: ✅ OK",
        "parse_mode": "HTML"
    }
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        res = r.json()
        if res.get("ok"):
            print("✅ Mensaje de prueba enviado exitosamente.")
        else:
            print(f"❌ Error en Telegram: {res.get('description')}")
    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")

if __name__ == "__main__":
    test_telegram()
