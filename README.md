# Helix - LLM Observability Platforms

> every LLM call → logged → observed

When an LLM app goes wrong in production, you're blind — no logs, no cost breakdown, 
no way to know which prompt version broke things. Helix sits between your app and the 
model, capturing every call's latency, token usage, and cost into Postgres, versioning 
your prompts with diffs, and alerting you before a runaway loop drains your budget. 
Think a self-hosted LangSmith.

## Features
- [x] Ollama + Postgres connection verified
- [x] LLM call logging middleware
- [x] Structured trace storage schema
- [x] Prompt versioning + diff view
- [x] Cost analytics dashboard
- [x] Alerting on cost/latency spikes
- [x] OpenTelemetry trace export

## Stack
`Python` `Ollama` `PostgreSQL` `Next.js` `OpenTelemetry`

## Run locally
```bash
# start ollama
ollama serve

# in a new terminal
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# verify setup
python test_setup.py
```

## Env vars
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/llmplatform
```

## Cost analytics dashboard
```bash
python dashboard.py            # http://localhost:8080
```
Shows spend, calls, tokens, p95 latency and error rate, cost and latency over
time, a per-model breakdown, recent traces and alerts. The JSON behind it is at
`/api/summary`, `/api/models`, `/api/timeseries`, `/api/tags?tag=feature`,
`/api/recent` and `/api/alerts` (all take `?hours=`).

Prices live in `pricing.py` as USD per 1,000 tokens. Local Ollama models are
priced at a hosted-equivalent rate so spend is visible; override with
`MODEL_PRICES='{"llama3.2": {"prompt": 0, "completion": 0}}'`.

## Alerts
```bash
python alerts.py               # checks every 60s; --once for a single check
```
Compares the last 5 minutes with the hour before it and fires on a cost or p95
latency spike (3x the usual rate), on hard limits, and on a high error rate.
Alerts are stored in the `alerts` table, shown on the dashboard, and posted to
`ALERT_WEBHOOK_URL` if set. Thresholds are env vars at the top of `alerts.py`.

## OpenTelemetry export
```
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```
With this set, every trace is also sent to the collector as an OTLP/HTTP span
using the GenAI semantic conventions (`gen_ai.request.model`,
`gen_ai.usage.input_tokens`, ...). `python otel_export.py --hours 24` re-exports
stored traces.

## Tests
```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/helix_test python test_analytics.py
```
Seeds synthetic traces, so point it at a scratch database.
