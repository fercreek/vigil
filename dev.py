import os
import time
import subprocess
import sys
import signal

# --- CONFIGURACIÓN ---
WATCH_EXTENSIONS = ('.py', '.env')
IGNORE_DIRS = ('.git', '__pycache__', 'venv', 'data', 'memory', 'docs')
COMMAND = [sys.executable, "main.py"]

def get_file_stats():
    """Escanea el directorio y retorna un diccionario {archivo: mtime}."""
    stats = {}
    for root, dirs, files in os.walk('.'):
        # Ignorar carpetas pesadas o irrelevantes
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            if file.endswith(WATCH_EXTENSIONS):
                full_path = os.path.join(root, file)
                try:
                    stats[full_path] = os.path.getmtime(full_path)
                except OSError:
                    pass
    return stats

def kill_process(process):
    """Mata el proceso y sus descendientes de forma segura."""
    if process:
        print(f"\n🔄 CAMBIO DETECTADO. Reiniciando Sistema...")
        try:
            # En Unix mandamos SIGTERM a todo el grupo de proceso
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except:
            process.terminate()
        process.wait()

def main():
    print("🚀 --- MONITOR DE DESARROLLO ZENITH ACTIVADO ---")
    print(f"👀 Vigilando cambios en: {', '.join(WATCH_EXTENSIONS)}")
    print("💡 Usa CTRL+C para detener el monitor y el bot.\n")

    current_process = None
    last_stats = get_file_stats()

    # Primera ejecución
    try:
        current_process = subprocess.Popen(COMMAND, preexec_fn=os.setsid)
        
        while True:
            time.sleep(1.5) # Polling cada 1.5s (bajo consumo)
            new_stats = get_file_stats()
            
            # Comparar estados
            reloaded = False
            for path, mtime in new_stats.items():
                if path not in last_stats or mtime > last_stats[path]:
                    reloaded = True
                    break
            
            if reloaded:
                kill_process(current_process)
                current_process = subprocess.Popen(COMMAND, preexec_fn=os.setsid)
                last_stats = new_stats
                
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo Monitor y Bot...")
        if current_process:
            os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
        sys.exit(0)

if __name__ == "__main__":
    main()
