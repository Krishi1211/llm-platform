import os
import time
import argparse
import requests
import psycopg2.extras
from dotenv import load_dotenv

from tracer import get_db
from pricing import cost_usd

load_dotenv()

WINDOW_MINUTES = int(os.getenv("ALERT_WINDOW_MINUTES", "5"))
BASELINE_MINUTES = int(os.getenv("ALERT_BASELINE_MINUTES", "60"))
SPIKE_FACTOR = float(os.getenv("ALERT_SPIKE_FACTOR", "3"))
COST_LIMIT = float(os.getenv("ALERT_COST_PER_WINDOW_USD", "1.0"))
LATENCY_LIMIT = float(os.getenv("ALERT_P95_LATENCY_MS", "30000"))
ERROR_RATE_LIMIT = float(os.getenv("ALERT_ERROR_RATE", "0.2"))
MIN_CALLS = int(os.getenv("ALERT_MIN_CALLS", "5"))
COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "15"))
WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL")


def create_tables():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            kind TEXT NOT NULL,
            message TEXT NOT NULL,
            value FLOAT,
            threshold FLOAT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def _window_stats(cur, start_minutes, end_minutes):
    """Stats for traces between start_minutes and end_minutes ago."""
    cur.execute("""
        SELECT model, COUNT(*), COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0),
               COUNT(*) FILTER (WHERE status = 'error')
        FROM traces
        WHERE created_at >= NOW() - %s * INTERVAL '1 minute'
          AND created_at <  NOW() - %s * INTERVAL '1 minute'
        GROUP BY model
    """, (start_minutes, end_minutes))
    calls = errors = 0
    cost = 0.0
    for model, n, pt, ct, err in cur.fetchall():
        calls += n
        errors += err
        cost += cost_usd(model, pt, ct)
    cur.execute("""
        SELECT COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms), 0)
        FROM traces
        WHERE created_at >= NOW() - %s * INTERVAL '1 minute'
          AND created_at <  NOW() - %s * INTERVAL '1 minute'
    """, (start_minutes, end_minutes))
    return {"calls": calls, "errors": errors, "cost": cost, "p95": cur.fetchone()[0]}


def evaluate(current, baseline):
    """Pure rule check. baseline covers BASELINE_MINUTES, current covers WINDOW_MINUTES."""
    found = []
    if current["calls"] < MIN_CALLS:
        return found
    scale = WINDOW_MINUTES / BASELINE_MINUTES
    baseline_cost = baseline["cost"] * scale

    if current["cost"] > COST_LIMIT:
        found.append(("cost_limit", current["cost"], COST_LIMIT,
                      f"Spend of ${current['cost']:.4f} in the last {WINDOW_MINUTES} min is over the ${COST_LIMIT:.2f} limit"))
    elif baseline["calls"] >= MIN_CALLS and current["cost"] > SPIKE_FACTOR * baseline_cost > 0:
        found.append(("cost_spike", current["cost"], SPIKE_FACTOR * baseline_cost,
                      f"Spend of ${current['cost']:.4f} in the last {WINDOW_MINUTES} min is {current['cost'] / baseline_cost:.1f}x the usual rate"))

    if current["p95"] > LATENCY_LIMIT:
        found.append(("latency_limit", current["p95"], LATENCY_LIMIT,
                      f"p95 latency of {current['p95']:.0f} ms is over the {LATENCY_LIMIT:.0f} ms limit"))
    elif baseline["calls"] >= MIN_CALLS and current["p95"] > SPIKE_FACTOR * baseline["p95"] > 0:
        found.append(("latency_spike", current["p95"], SPIKE_FACTOR * baseline["p95"],
                      f"p95 latency of {current['p95']:.0f} ms is {current['p95'] / baseline['p95']:.1f}x the usual {baseline['p95']:.0f} ms"))

    error_rate = current["errors"] / current["calls"]
    if error_rate > ERROR_RATE_LIMIT:
        found.append(("error_rate", error_rate, ERROR_RATE_LIMIT,
                      f"{error_rate:.0%} of calls failed in the last {WINDOW_MINUTES} min"))
    return found


def check_alerts():
    """Evaluates the rules, stores new alerts and returns them."""
    conn = get_db()
    cur = conn.cursor()
    current = _window_stats(cur, WINDOW_MINUTES, 0)
    baseline = _window_stats(cur, WINDOW_MINUTES + BASELINE_MINUTES, WINDOW_MINUTES)

    fired = []
    for kind, value, threshold, message in evaluate(current, baseline):
        cur.execute("""
            SELECT 1 FROM alerts
            WHERE kind = %s AND created_at >= NOW() - %s * INTERVAL '1 minute' LIMIT 1
        """, (kind, COOLDOWN_MINUTES))
        if cur.fetchone():
            continue
        cur.execute("""
            INSERT INTO alerts (kind, message, value, threshold) VALUES (%s, %s, %s, %s)
        """, (kind, message, value, threshold))
        fired.append({"kind": kind, "message": message, "value": value, "threshold": threshold})
    conn.commit()
    cur.close()
    conn.close()

    for alert in fired:
        print(f"[ALERT] {alert['kind']}: {alert['message']}")
        if WEBHOOK_URL:
            try:
                requests.post(WEBHOOK_URL, json={"text": f"Helix alert: {alert['message']}", **alert}, timeout=5)
            except Exception as e:
                print(f"webhook failed: {e}")
    return fired


def recent_alerts(limit=20):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT kind, message, value, threshold, created_at FROM alerts ORDER BY created_at DESC LIMIT %s", (limit,))
    rows = [{**row, "created_at": row["created_at"].isoformat()} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Watch traces and alert on cost, latency and error spikes")
    parser.add_argument("--interval", type=int, default=60, help="seconds between checks")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    create_tables()
    while True:
        check_alerts()
        if args.once:
            break
        time.sleep(args.interval)
