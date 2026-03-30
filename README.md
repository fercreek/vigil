# Zenith Trading Suite 🤖🏛️ (V2.1.0 Dual Engine)

Esta es una suite de trading algorítmico de élite diseñada para operar en **Binance** con máxima estabilidad. El sistema combina análisis técnico institucional con el razonamiento avanzado de **Gemini AI** para ofrecer una ventaja competitiva en el mercado.

## ✨ ¿Qué hace esta versión? (Zenith V2.1.0)

El sistema ha evolucionado a una arquitectura de **Motor Dual** que cubre todo el espectro del mercado:

### 1. ⚡ Scalp Alert Engine (15m)
- **Estrategia**: Captura de rebotes rápidos y micro-tendencias.
- **Indicadores**: RSI, Bandas de Bollinger, EMA 200 y ATR dinámico.
- **Filtro AI**: Validación instantánea por los agentes *Conservador* y *Scalper*.

### 2. 🏛️ Zenith Swing Engine (H4)
- **Estrategia**: Seguimiento de tendencia institucional de alta probabilidad.
- **Indicadores**: Nube de Ichimoku (Kumo Breakout) y Order Blocks (SMC).
- **AI Bias**: El agente *Institutional Strategist* define la dirección semanal para filtrar ruidos.

### 3. 📱 Interfaz Contextual (Telegram)
- **Botones Dinámicos**: El menú de Telegram se adapta en tiempo real. Si abres una operación manual, los botones de LONG/SHORT desaparecen y son reemplazados por un botón de **Cierre con PnL**.
- **Seguridad**: Bloqueo automático de entradas duplicadas para proteger tu capital.

### 4. 🛠️ Modo Hot Reload (Dev Mode)
- **Agilidad**: Usa `python3 dev.py` para que el sistema se reinicie automáticamente al detectar cualquier cambio en el código. ¡Cero tiempos muertos!

---

## 🚀 Cómo correr la Suite

### A. Modo Producción (Estable)
Lanza todo el sistema (Dashboard + Scalp + Swing) con un solo comando:
```bash
python3 main.py
```

### B. Modo Desarrollo (Hot Reload)
Usa el monitor inteligente para que los cambios se apliquen al instante:
```bash
python3 dev.py
```

---

## ☁️ Despliegue en la Nube (Replit Ready)
1. Configura tus **Secrets** (`TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`).
2. El orquestador `main.py` está optimizado para mantener la web viva 24/7.
3. El sistema incluye un **Escudo de Estabilidad (V2.1)** que sanitiza todos los datos nulos, garantizando que el bot no se detenga por fallos de red externos.

---
¡El sistema Zenith es ahora una solución completa de nivel profesional para el trading algorítmico! 📈🏛️🚀
