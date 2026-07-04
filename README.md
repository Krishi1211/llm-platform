# Helix - LLM Observability Platform

> every LLM call → logged → observed

When an LLM app goes wrong in production, you're blind — no logs, no cost breakdown, 
no way to know which prompt version broke things. Helix sits between your app and the 
model, capturing every call's latency, token usage, and cost into Postgres, versioning 
your prompts with diffs, and alerting you before a runaway loop drains your budget. 
Think a self-hosted LangSmith.

## Features
- [x] Ollama + Postgres connection verified
- [ ] LLM call logging middleware
- [ ] Structured trace storage schema
- [ ] Prompt versioning + diff view
- [ ] Cost analytics dashboard
- [ ] Alerting on cost/latency spikes
- [ ] OpenTelemetry trace export

## Stack
`Python` `Ollama` `PostgreSQL` `Next.js` `OpenTelemetry`

## Run locally
```bash
# start ollama
ollama serve

# in a new terminal
python3 -m venv venv && source venv/bin/activate
pip install requests psycopg2-binary python-dotenv

# verify setup
python test_setup.py
```

## Env vars
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/llmplatform
```