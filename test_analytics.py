"""Seeds synthetic traces, then checks analytics, alerts and OTel payloads.

Run against a scratch database, since it inserts rows:
    DATABASE_URL=postgresql://.../helix_test python test_analytics.py
"""
import uuid
import psycopg2.extras

import tracer
import alerts
import analytics
from otel_export import build_payload
from pricing import cost_usd

tracer.create_tables()
alerts.create_tables()

conn = tracer.get_db()
cur = conn.cursor()

def seed(n, minutes_ago, latency, tokens, status="success", feature="chat"):
    for _ in range(n):
        cur.execute("""
            INSERT INTO traces (id, model, prompt, response, latency_ms, prompt_tokens,
                                completion_tokens, total_tokens, status, tags, created_at)
            VALUES (%s, 'llama3.2', 'seed prompt', 'seed', %s, %s, %s, %s, %s, %s,
                    NOW() - %s * INTERVAL '1 minute')
        """, (str(uuid.uuid4()), latency, tokens, tokens, tokens * 2, status,
              psycopg2.extras.Json({"feature": feature}), minutes_ago))

seed(20, 30, latency=400, tokens=100)                     # quiet baseline
seed(10, 1, latency=5000, tokens=5000, feature="agent")   # runaway loop
seed(5, 1, latency=5000, tokens=0, status="error", feature="agent")
conn.commit()
cur.close()
conn.close()

s = analytics.summary(24)
assert s["calls"] == 35 and s["errors"] == 5, s
expected = cost_usd("llama3.2", 20 * 100 + 10 * 5000, 20 * 100 + 10 * 5000)
assert abs(s["cost_usd"] - expected) < 1e-6, (s["cost_usd"], expected)
assert analytics.by_model(24)[0]["model"] == "llama3.2"
assert sum(p["calls"] for p in analytics.timeseries(24)) == 35
assert analytics.by_tag("feature", 24)[0]["value"] == "agent"
assert len(analytics.recent(10)) == 10

kinds = {a["kind"] for a in alerts.check_alerts()}
assert {"cost_spike", "latency_spike", "error_rate"} <= kinds, kinds
assert alerts.check_alerts() == [], "cooldown should suppress repeats"

span = build_payload([{
    "trace_id": str(uuid.uuid4()), "model": "llama3.2", "latency_ms": 250.0, "prompt_tokens": 10,
    "completion_tokens": 20, "status": "success", "tags": {"env": "dev"}, "end_time": 1_700_000_000.0,
}])["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
assert len(span["traceId"]) == 32 and len(span["spanId"]) == 16
assert int(span["endTimeUnixNano"]) - int(span["startTimeUnixNano"]) == 250_000_000

print("analytics, alerts and OTel export OK")
