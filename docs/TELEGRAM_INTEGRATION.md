# 📱 Interfaz de Usuario: Telegram Integration

El bot no es solo un emisor pasivo de alertas; es un **Asistente de Trading Interactivo**. La integración se realiza mediante la **Telegram Bot API** con un sistema de polling optimizado para Replit.

## 🚀 Comandos Interactivos

| Comando | Acción | Descripción |
| :--- | :--- | :--- |
| `/status` | 📊 Reporte | Muestra precios actuales, RSI y sentimiento macro de ETH, BTC y TAO. |
| `/analyze [SYM]` | 🧠 Agente Experto | Activa el `EXPERT_ADVISOR` de Gemini para un análisis profundo del símbolo. |
| `Status de Mercado` | 📊 Botón Contextual | Atajo visual para el comando `/status`. |

## 🛡️ Sistema de Alertas (Visual Design)

El bot utiliza HTML para proporcionar una experiencia "Premium":
- **Cabeceras Dinámicas**: `🛡️ [V1-TECH]` vs `🤖 [V2-AI-GEMINI]`.
- **Badge de Conconvicción**: 💎 DIAMANTE, 🔥 ALTA CONVICCIÓN, ⚡ ESTÁNDAR.
- **Micro-datos**: Incluye Dominancia USDT/BTC, precio del Oro y contexto Elliott.

## ⚠️ Robustez: El Escudo HTML (`safe_html`)

Uno de los mayores retos resueltos es el formateo de respuestas de IA para Telegram:
1.  **Escape de Símbolos**: Telegram falla si encuentra `<` o `>` que no son etiquetas válidas (ej. `RSI < 30`).
2.  **Mapeo de Etiquetas**: La IA genera Markdown o HTML variado. `safe_html` convierte:
    -   `<ul>` / `<li>` → Viñetas de emojis (•).
    -   `<h1...h4>` → Texto en negrita (`<b>`).
    -   `---` → Separadores visuales (`──────────────`).
3.  **Preservación de Código**: Mantiene etiquetas permitidas (`<b>`, `<i>`, `<code>`) escapando el contenido matemático.

## 🧵 Gestión de Hilos y Respuestas
- **Reply IDs**: Cuando el bot monitorea una posición abierta, utiliza `reply_to_message_id` para que las actualizaciones de TP/SL aparezcan anidadas a la señal original.
- **Teclado Persistente**: Utiliza `ReplyKeyboardMarkup` para que el menú de comandos esté siempre a mano del usuario.

> [!CAUTION]
> El bot tiene una validación de `TELEGRAM_CHAT_ID` en `check_user_queries`. Cualquier intento de comando desde un chat no autorizado será ignorado para proteger la seguridad operativa.
