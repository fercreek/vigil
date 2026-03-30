import os
import requests
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def debug_polling():
    print(f"📡 Debugging Telegram Bot Polling...")
    print(f"🔑 Token: {TELEGRAM_TOKEN[:5]}...{TELEGRAM_TOKEN[-5:]}")
    print(f"🛡️ Chat ID Autorizado: {TELEGRAM_CHAT_ID}")
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"limit": 10}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if not data.get("ok"):
            print(f"❌ Error API: {data}")
            return
            
        updates = data.get("result", [])
        print(f"✅ Se encontraron {len(updates)} actualizaciones recientes.\n")
        
        for u in updates:
            mid = u["update_id"]
            m = u.get("message", {})
            text = m.get("text", "N/A")
            cid = str(m.get("chat", {}).get("id", "N/A"))
            uname = m.get("from", {}).get("username", "N/A")
            
            print(f"🆔 Update: {mid}")
            print(f"👤 Remitente: @{uname} (Chat ID: {cid})")
            print(f"📝 Texto: {text}")
            if cid == str(TELEGRAM_CHAT_ID):
                print("🌟 ¡ESTE ID COINCIDE CON TU .ENV! ✅")
            else:
                print("❌ ESTE ID NO COINCIDE. El bot está ignorando este mensaje.")
            print("-" * 30)
            
    except Exception as e:
        print(f"❌ Error fatal: {e}")

if __name__ == "__main__":
    debug_polling()
