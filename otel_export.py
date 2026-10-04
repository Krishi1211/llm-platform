import os
import argparse
import requests
from dotenv import load_dotenv

from pricing import cost_usd

load_dotenv()

# OTLP/HTTP endpoint of a collector, e.g. http://localhost:4318. Export is off when unset.
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "helix")


def _attr(key, value):
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}


def trace_to_span(trace):
    """Maps one trace row to an OTLP span using the GenAI semantic conventions.

    trace needs: trace_id (uuid str), model, latency_ms, prompt_tokens,
    completion_tokens, status, end_time (epoch seconds); optional error_message, tags.
    """
    hex_id = trace["trace_id"].replace("-", "")
    end_ns = int(trace["end_time"] * 1e9)
    start_ns = end_ns - int(trace["latency_ms"] * 1e6)
    attributes = [
        _attr("gen_ai.operation.name", "generate"),
        _attr("gen_ai.system", "ollama"),
        _attr("gen_ai.request.model", trace["model"]),
        _attr("gen_ai.usage.input_tokens", int(trace["prompt_tokens"] or 0)),
        _attr("gen_ai.usage.output_tokens", int(trace["completion_tokens"] or 0)),
        _attr("helix.cost_usd", cost_usd(trace["model"], trace["prompt_tokens"], trace["completion_tokens"])),
    ]
    for key, value in (trace.get("tags") or {}).items():
        attributes.append(_attr(f"helix.tag.{key}", value))

    is_error = trace["status"] == "error"
    status = {"code": 2, "message": trace.get("error_message") or ""} if is_error else {"code": 1}
    return {
        "traceId": hex_id,
        "spanId": hex_id[:16],
        "name": f"generate {trace['model']}",
        "kind": 3,  # CLIENT
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "attributes": attributes,
        "status": status,
    }


def build_payload(traces):
    return {
        "resourceSpans": [{
            "resource": {"attributes": [_attr("service.name", SERVICE_NAME)]},
            "scopeSpans": [{
                "scope": {"name": "helix.tracer"},
                "spans": [trace_to_span(t) for t in traces],
            }],
        }]
    }


def export_traces(traces, endpoint=None):
    """POSTs traces to the collector. Returns True on success, False if disabled or failed."""
    endpoint = endpoint or OTLP_ENDPOINT
    if not endpoint or not traces:
        return False
    try:
        res = requests.post(f"{endpoint.rstrip('/')}/v1/traces", json=build_payload(traces), timeout=5)
        return res.status_code < 300
    except Exception as e:
        print(f"OTel export failed: {e}")
        return False


def backfill(hours):
    from tracer import get_db
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, model, latency_ms, prompt_tokens, completion_tokens, status, error_message, tags,
               EXTRACT(EPOCH FROM created_at)
        FROM traces WHERE created_at >= NOW() - %s * INTERVAL '1 hour' ORDER BY created_at
    """, (hours,))
    traces = [{
        "trace_id": str(i), "model": model, "latency_ms": lat or 0, "prompt_tokens": pt,
        "completion_tokens": ct, "status": status, "error_message": err, "tags": tags,
        "end_time": float(epoch) + (lat or 0) / 1000.0,
    } for i, model, lat, pt, ct, status, err, tags, epoch in cur.fetchall()]
    cur.close()
    conn.close()
    ok = export_traces(traces)
    print(f"Exported {len(traces)} traces" if ok else f"Export failed or disabled ({len(traces)} traces found)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-export stored traces to an OTLP collector")
    parser.add_argument("--hours", type=int, default=24)
    backfill(parser.parse_args().hours)
