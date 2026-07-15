import psycopg2
import psycopg2.extras
import os
import difflib
from dotenv import load_dotenv

load_dotenv()

def get_db():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def create_tables():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prompt_versions (
            id SERIAL PRIMARY KEY,
            prompt_name TEXT NOT NULL,
            version INT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(prompt_name, version)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("Tables ready.")

def save_prompt(name, content):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(MAX(version), 0) FROM prompt_versions WHERE prompt_name = %s
    """, (name,))
    latest_version = cur.fetchone()[0]
    new_version = latest_version + 1
    cur.execute("""
        INSERT INTO prompt_versions (prompt_name, version, content)
        VALUES (%s, %s, %s)
    """, (name, new_version, content))
    conn.commit()
    cur.close()
    conn.close()
    print(f"Saved {name} v{new_version}")
    return new_version

def get_prompt(name, version=None):
    conn = get_db()
    cur = conn.cursor()
    if version:
        cur.execute("""
            SELECT content, version FROM prompt_versions
            WHERE prompt_name = %s AND version = %s
        """, (name, version))
    else:
        cur.execute("""
            SELECT content, version FROM prompt_versions
            WHERE prompt_name = %s ORDER BY version DESC LIMIT 1
        """, (name,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {"content": row[0], "version": row[1]} if row else None

def list_versions(name):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT version, created_at FROM prompt_versions
        WHERE prompt_name = %s ORDER BY version
    """, (name,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"version": r[0], "created_at": str(r[1])} for r in rows]

def diff_versions(name, v1, v2):
    p1 = get_prompt(name, v1)
    p2 = get_prompt(name, v2)
    if not p1 or not p2:
        return "one or both versions not found"
    diff = difflib.unified_diff(
        p1["content"].splitlines(keepends=True),
        p2["content"].splitlines(keepends=True),
        fromfile=f"{name} v{v1}",
        tofile=f"{name} v{v2}"
    )
    return "".join(diff)