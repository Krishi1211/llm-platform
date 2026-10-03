import json
import os

# USD per 1,000 tokens. Local Ollama models cost nothing to call, so by default
# they are priced at a hosted-equivalent rate to make spend visible. Override
# with MODEL_PRICES='{"llama3.2": {"prompt": 0, "completion": 0}}'.
DEFAULT_PRICE = {"prompt": 0.0005, "completion": 0.0015}

PRICES = {
    "llama3.2": {"prompt": 0.0002, "completion": 0.0002},
}
PRICES.update(json.loads(os.getenv("MODEL_PRICES", "{}")))


def cost_usd(model, prompt_tokens, completion_tokens):
    price = PRICES.get(model, DEFAULT_PRICE)
    return ((prompt_tokens or 0) * price["prompt"] + (completion_tokens or 0) * price["completion"]) / 1000.0
