import os
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

# test ollama
response = requests.post("http://localhost:11434/api/generate", json={
    "model": "llama3.2",
    "prompt": "say hi",
    "stream": False
})
print("Ollama:", response.json()["response"])

# test postgres
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
print("Postgres: connected")
conn.close()