from tracer import create_tables, Tracer

create_tables()

tracer = Tracer(model="llama3.2", tags={"env": "dev", "feature": "week2"})

prompts = [
    "what is a binary search tree?",
    "explain docker in one sentence",
    "what is a write ahead log?"
]

for p in prompts:
    result = tracer.run(p)
    print(f"\nTrace ID: {result['trace_id']}")
    print(f"Latency: {result['latency_ms']}ms")
    print(f"Tokens: {result['total_tokens']} total")
    print(f"Status: {result['status']}")