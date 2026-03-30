# 🧠 Integración de IA: Gemini 2.5 Flash

El corazón analítico del bot reside en su capacidad para procesar datos de mercado no lineales y "razonar" sobre la confluencia técnica. Esto se logra a través de una integración profunda con **Google Gemini 2.5 Flash**.

## 👥 Personas y Especializaciones

El sistema utiliza tres perfiles distintos de IA para proporcionar visiones complementarias:

| Persona | Emojis | Enfoque | Filosofía |
| :--- | :--- | :--- | :--- |
| **CONSERVADOR** | 🔵 🏛️ | Largo Plazo / Sólido | Bajista si USDT.D > 8.05%. Busca soportes institucionales. |
| **SCALPER** | ⚡ 💀 | Micropatrones / Rápido | Aprovecha volatilidad de la hora. Alta tolerancia al riesgo. |
| **EXPERT_ADVISOR**| 🧠 🔍 | Consultoría Manual | Proporciona análisis Elliott y psicología de trading. |

## 💾 Memoria Persistente (Daily Memory)

A diferencia de un chat simple, `gemini_analyzer.py` implementa un sistema de **historial diario persistente**:
1.  **Directorio `memory/`**: Cada día se genera un archivo JSON por persona (ej. `CONSERVADOR_2026-03-29.json`).
2.  **Contexto Acumulado**: El bot registra alertas pasadas y resultados de trades en este archivo.
3.  **Hilos de Chat**: Al consultar a la IA, se "recuerda" lo ocurrido durante las últimas 24 horas, permitiendo que la IA detecte cambios en el sentimiento del mercado.

## 🤝 Consenso Híbrido (Validation Logic)

Cuando el algoritmo técnico detecta una señal, el proceso es el siguiente:
1.  **Score Técnico**: Se calcula un score de 0 a 5.
2.  **Challenge a la IA**: Se envía un prompt estructurado a Gemini con el contexto actual.
3.  **Filtro JSON**: El bot exige una respuesta en formato JSON: `{"decision": "CONFIRM" | "REJECT", "reason": "..."}`.
4.  **Ejecución**: Solo si hay `CONFIRM`, se lanza la alerta como `🔹💎🔹 CONSENSO IA`.

## 🛠️ SDK y Configuración
- **Model**: `gemini-2.5-flash` y `gemini-flash-latest` (para pulsos rápidos).
- **System Instructions**: Cada persona tiene su propia "System Instruction" que define su sesgo y reglas operativas.
- **Safety**: Todas las respuestas son sanitizadas por `safe_html` para evitar errores de parseo en Telegram.

> [!IMPORTANT]
> El bot está configurado para **rechazar** automáticamente señales que vayan en contra de la tendencia mayor (EMA 200), incluso si la IA da su aprobación inicial, añadiendo una capa extra de seguridad algorítmica.
