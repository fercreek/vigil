import logging
import os
import json
from datetime import datetime

# Directorio de logs persistente
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

APP_LOG_FILE = os.path.join(LOGS_DIR, "app.log")
AI_LOG_FILE = os.path.join(LOGS_DIR, "ai_decisions.jsonl")

# Configurar el Logger Estándar de la Aplicación
logger = logging.getLogger("ScalpBot")
logger.setLevel(logging.INFO)

# Evitar duplicados si se recarga el módulo
if not logger.handlers:
    # Escribir en archivo app.log
    fh = logging.FileHandler(APP_LOG_FILE)
    fh.setLevel(logging.INFO)
    
    # Escribir en la terminal también
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Formato ejecutivo
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)

def log_ai_decision(persona: str, prompt: str, raw_response: str, metadata: dict = None):
    """Guarda en JSONL (JSON Lines) el pensamiento estructurado de la Inteligencia Artificial."""
    timestamp = datetime.now().isoformat()
    
    record = {
        "timestamp": timestamp,
        "persona": persona,
        "prompt": prompt,
        "raw_response": raw_response,
        "metadata": metadata or {}
    }
    
    # Con JSONL simplemente anexamos la línea sin romper la sintaxis JSON
    try:
        with open(AI_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"No se pudo guardar el pensamiento del bot: {e}")
