# 🚀 Guía de Despliegue: Scalp Bot en Replit (24/7 Cloud)

Esta guía te ayudará a mover tu bot V1.6.3 a la nube de **Replit** para que funcione sin interrupciones y con el Dashboard web de consulta siempre activo.

---

## 🏗️ Paso 1: Subir archivos a Replit

1.  Crea un nuevo **Repl** (Python).
2.  Sube todos los archivos del proyecto (puedes arrastrar y soltar), especialmente:
    *   `main.py`, `scalp_alert_bot.py`, `app.py`, `gemini_analyzer.py`, `indicators.py`, `tracker.py`.
    *   `requirements.txt`.
    *   Carpeta `templates/` y `static/`.
    *   **NO** subas el archivo `.env`. Usaremos la herramienta interna de Replit.

## 🔒 Paso 2: Configurar Secretos (Secrets)

En Replit, las variables de entorno se guardan en el panel **Secrets** (icono de candado 🔒).
Añade estas claves una a una:

| Clave | Valor |
| :--- | :--- |
| `TELEGRAM_TOKEN` | Tu Token de Telegram |
| `TELEGRAM_CHAT_ID` | Tu ID de Chat |
| `GEMINI_API_KEY` | Tu API Key de Google GenAI |
| `CHECK_INTERVAL` | `35` |

## ⚡ Paso 3: Lanzar el Sistema

1.  Haz clic en el botón **Run** (botón azul gigante).
2.  Replit instalará automáticamente las dependencias de `requirements.txt`.
3.  Verás que se abre una ventana a la derecha con el **Dashboard Web**.
4.  En la terminal verás el mensaje: `🚀 --- INICIANDO SISTEMA HÍBRIDO (V1.6.3 REPLIT READY) ---`.

## ☕ Paso 4: Mantenerlo Despierto (UptimeRobot)

Para que el Plan Gratuito de Replit no se duerma tras unos minutos:
1.  Copia la **URL de tu web** que aparece sobre el Dashboard en Replit (ej: `https://tu-repl-nombre.usuario.repl.co`).
2.  Ve a [UptimeRobot.com](https://uptimerobot.com/) (Gratis).
3.  Crea un **HTTP Monitor** que apunte a esa URL cada 5 minutos.
4.  ¡Listo! Esto mantendrá tu bot activo las 24 horas del día.

---

> [!TIP]
> **Base de Datos**: El archivo `trades.db` vivirá dentro de Replit. Si reinicias el Repl, los datos persisten. Si quieres hacer una copia de seguridad, puedes descargar el archivo `trades.db` periódicamente desde el panel lateral de Replit.

> [!CAUTION]
> **Privacidad**: Si el Dashboard es público, cualquiera con la URL podrá ver tus trades. Si necesitas una contraseña, avísame y la implementaremos en `app.py`.

¡Tu bot ya es un sistema de trading en la nube! 📈🤖☁️
