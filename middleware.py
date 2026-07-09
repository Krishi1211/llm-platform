import time
import requests
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_db():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def create_table():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS llm_logs (
            id SERIAL PRIMARY KEY,
            model TEXT,
            prompt TEXT,
            response TEXT,
            latency_ms FLOAT,
            prompt_tokens INT,
            completion_tokens INT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def log_call(model, prompt, response, latency_ms, prompt_tokens, completion_tokens):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO llm_logs 
        (model, prompt, response, latency_ms, prompt_tokens, completion_tokens)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (model, prompt, response, latency_ms, prompt_tokens, completion_tokens))
    conn.commit()
    cur.close()
    conn.close()

def call_llm(prompt, model="llama3.2"):
    start = time.time()
    
    res = requests.post("http://localhost:11434/api/generate", json={
        "model": model,
        "prompt": prompt,
        "stream": False
    })
    
    latency_ms = (time.time() - start) * 1000
    data = res.json()
    response_text = data.get("response", "")
    prompt_tokens = data.get("prompt_eval_count", 0)
    completion_tokens = data.get("eval_count", 0)

    log_call(model, prompt, response_text, latency_ms, prompt_tokens, completion_tokens)
    
    return {
        "response": response_text,
        "latency_ms": round(latency_ms, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens
    }

if __name__ == "__main__":
    create_table()
    
    # test 3 calls
    prompts = ["what is 2+2?", "name a planet", "what is python?"]
    for p in prompts:
        result = call_llm(p)
        print(f"\nPrompt: {p}")
        print(f"Response: {result['response'][:80]}")
        print(f"Latency: {result['latency_ms']}ms")
        print(f"Tokens: {result['prompt_tokens']} in / {result['completion_tokens']} out")