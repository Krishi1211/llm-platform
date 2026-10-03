from tracer import get_db
from pricing import cost_usd

BUCKETS = {"hour": "hour", "day": "day"}


def _query(sql, params=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def by_model(hours=24):
    rows = _query("""
        SELECT model,
               COUNT(*),
               COALESCE(SUM(prompt_tokens), 0),
               COALESCE(SUM(completion_tokens), 0),
               COALESCE(AVG(latency_ms), 0),
               COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms), 0),
               COUNT(*) FILTER (WHERE status = 'error')
        FROM traces
        WHERE created_at >= NOW() - %s * INTERVAL '1 hour'
        GROUP BY model
        ORDER BY COUNT(*) DESC
    """, (hours,))
    return [{
        "model": model,
        "calls": calls,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "cost_usd": round(cost_usd(model, pt, ct), 6),
        "avg_latency_ms": round(avg, 2),
        "p95_latency_ms": round(p95, 2),
        "errors": errors,
    } for model, calls, pt, ct, avg, p95, errors in rows]


def summary(hours=24):
    models = by_model(hours)
    calls = sum(m["calls"] for m in models)
    errors = sum(m["errors"] for m in models)
    p95 = _query("""
        SELECT COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms), 0),
               COALESCE(AVG(latency_ms), 0)
        FROM traces WHERE created_at >= NOW() - %s * INTERVAL '1 hour'
    """, (hours,))[0]
    return {
        "hours": hours,
        "calls": calls,
        "errors": errors,
        "error_rate": round(errors / calls, 4) if calls else 0.0,
        "prompt_tokens": sum(m["prompt_tokens"] for m in models),
        "completion_tokens": sum(m["completion_tokens"] for m in models),
        "cost_usd": round(sum(m["cost_usd"] for m in models), 6),
        "p95_latency_ms": round(p95[0], 2),
        "avg_latency_ms": round(p95[1], 2),
    }


def timeseries(hours=24, bucket="hour"):
    rows = _query(f"""
        SELECT DATE_TRUNC('{BUCKETS[bucket]}', created_at) AS bucket,
               model,
               COUNT(*),
               COALESCE(SUM(prompt_tokens), 0),
               COALESCE(SUM(completion_tokens), 0),
               COALESCE(AVG(latency_ms), 0)
        FROM traces
        WHERE created_at >= NOW() - %s * INTERVAL '1 hour'
        GROUP BY bucket, model
        ORDER BY bucket
    """, (hours,))
    points = {}
    for ts, model, calls, pt, ct, avg in rows:
        p = points.setdefault(ts, {"bucket": ts.isoformat(), "calls": 0, "cost_usd": 0.0, "_lat": 0.0})
        p["calls"] += calls
        p["cost_usd"] += cost_usd(model, pt, ct)
        p["_lat"] += avg * calls
    out = []
    for p in points.values():
        p["avg_latency_ms"] = round(p.pop("_lat") / p["calls"], 2)
        p["cost_usd"] = round(p["cost_usd"], 6)
        out.append(p)
    return out


def by_tag(tag, hours=24):
    rows = _query("""
        SELECT COALESCE(tags->>%s, '(none)'), model, COUNT(*),
               COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0)
        FROM traces
        WHERE created_at >= NOW() - %s * INTERVAL '1 hour'
        GROUP BY 1, model
    """, (tag, hours))
    out = {}
    for value, model, calls, pt, ct in rows:
        o = out.setdefault(value, {"value": value, "calls": 0, "cost_usd": 0.0})
        o["calls"] += calls
        o["cost_usd"] = round(o["cost_usd"] + cost_usd(model, pt, ct), 6)
    return sorted(out.values(), key=lambda o: -o["cost_usd"])


def recent(limit=25):
    rows = _query("""
        SELECT id, model, LEFT(prompt, 120), latency_ms, prompt_tokens, completion_tokens,
               status, tags, created_at
        FROM traces ORDER BY created_at DESC LIMIT %s
    """, (limit,))
    return [{
        "id": str(i), "model": model, "prompt": prompt, "latency_ms": round(lat or 0, 2),
        "total_tokens": (pt or 0) + (ct or 0), "cost_usd": round(cost_usd(model, pt, ct), 6),
        "status": status, "tags": tags, "created_at": created.isoformat(),
    } for i, model, prompt, lat, pt, ct, status, tags, created in rows]
