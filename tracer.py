import time
import uuid
import requests
import psycopg2
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

def get_db():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def create_tables():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS traces (
            id UUID PRIMARY KEY,
            model TEXT NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT,
            latency_ms FLOAT,
            prompt_tokens INT,
            completion_tokens INT,
            total_tokens INT,
            status TEXT DEFAULT 'success',
            error_message TEXT,
            tags JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Tables created.")

class Tracer:
    def __init__(self, model="llama3.2", tags=None):
        self.model = model
        self.tags = tags or {}

    def run(self, prompt):
        trace_id = str(uuid.uuid4())
        start = time.time()
        status = "success"
        error_message = None
        response_text = ""
        prompt_tokens = 0
        completion_tokens = 0

        try:
            res = requests.post("http://localhost:11434/api/generate", json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }, timeout=60)

            data = res.json()
            response_text = data.get("response", "")
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)

        except Exception as e:
            status = "error"
            error_message = str(e)

        latency_ms = (time.time() - start) * 1000
        total_tokens = prompt_tokens + completion_tokens

        # save trace
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO traces (
                id, model, prompt, response, latency_ms,
                prompt_tokens, completion_tokens, total_tokens,
                status, error_message, tags
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            trace_id, self.model, prompt, response_text, latency_ms,
            prompt_tokens, completion_tokens, total_tokens,
            status, error_message, psycopg2.extras.Json(self.tags)
        ))
        conn.commit()
        cur.close()
        conn.close()

        return {
            "trace_id": trace_id,
            "response": response_text,
            "latency_ms": round(latency_ms, 2),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "status": status
        }