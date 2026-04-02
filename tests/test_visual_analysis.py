import os
import sys

# Añadir el path actual para importación de core
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

import gemini_analyzer
from datetime import datetime

def test_visual_context():
    print("\n--- 👁️ TEST DE ANÁLISIS MULTIMODAL V14.2 ---")
    
    # 1. Verificar si existe el gráfico de ETH 4h subido por el usuario
    symbol = "ETH"
    img_path = gemini_analyzer._find_recent_chart(symbol)
    
    if img_path:
        print(f"✅ Gráfico detectado en: {img_path}")
        print(f"📅 Fecha de modificación: {datetime.fromtimestamp(os.path.getmtime(img_path))}")
        
        # 2. Solicitar análisis al Agente Éxodo (Scalper)
        print("\n⚡ [EXODO] Analizando gráfico y mercado actual...")
        prompt = "Analiza el gráfico adjunto de ETH. ¿Qué niveles de soporte y resistencia ves? ¿Coincide con un escenario de SHORT o LONG?"
        
        try:
            # En el test, llamamos directamente a la función de chat con la imagen
            response, _ = gemini_analyzer._chat_with_persona("SCALPER", prompt, image_path=img_path)
            
            if response:
                print("\n🤖 --- REPORTE VISUAL ---")
                print(response)
                print("\n✨ ÉXITO: El sistema ha integrado la imagen como fuente de datos.")
            else:
                print("❌ Fallo en la respuesta de la IA.")
        except Exception as e:
            print(f"❌ Error durante el análisis: {e}")
            
    else:
        print(f"⚠️ No se encontró el gráfico para {symbol}. Intenta subirlo vía Telegram con /add_chart {symbol} 4h.")

    print("\n🏁 --- FIN DEL TEST VISUAL ---")

if __name__ == "__main__":
    test_visual_context()
