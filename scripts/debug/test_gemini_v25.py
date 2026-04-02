import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Testing gemini-2.5-flash...")
try:
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents="Hola, responde con 'OK' si recibes esto."
    )
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
