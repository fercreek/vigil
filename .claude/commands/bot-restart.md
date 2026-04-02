# /bot-restart — Reiniciar el bot de forma limpia

Pasos para reiniciar el bot de trading:

1. Verificar la sintaxis de todos los archivos modificados:
   ```
   python -m py_compile scalp_alert_bot.py
   python -m py_compile telegram_commands.py
   python -m py_compile gemini_analyzer.py
   ```

2. Matar procesos viejos (buscar PIDs de `main.py` y `scalp_alert_bot.py` directos):
   ```
   pkill -f "python.*main.py"
   pkill -f "python.*scalp_alert_bot.py"
   ```

3. Esperar 2 segundos y arrancar:
   ```
   source venv/bin/activate
   nohup python main.py > bot.log 2>&1 &
   ```

4. Esperar 5 segundos y verificar logs:
   ```
   tail -15 bot.log
   ```

5. Confirmar que aparezca:
   - `[AI Router] Claude Haiku disponible`
   - Flask running en puerto 8080
   - Sin errores de importación

6. Probar con `check_user_queries` directo si hay dudas.
