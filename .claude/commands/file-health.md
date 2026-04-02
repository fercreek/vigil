# /file-health — Revisar salud y tamaño de archivos

Ejecuta una revisión del estado de los archivos Python del proyecto.

Para cada archivo `.py` en el directorio raíz:
1. Muestra el número de líneas
2. Marca con ⚠️ los que superen 600 líneas
3. Marca con 🔴 los que superen 900 líneas
4. Para los archivos marcados, sugiere qué sección extraer según las reglas de CLAUDE.md

Después verifica:
- Que `scalp_alert_bot.py` < 1300 líneas
- Que no haya funciones duplicadas o código muerto (funciones UNUSED, bloques `if False`)
- Que `telegram_commands.py` existe y tiene el dispatcher de comandos Telegram

Finaliza con un resumen de acciones recomendadas.
