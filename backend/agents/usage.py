"""What each build costs: tokens per model, priced in US dollars.

A UsageMeter is attached to every model of one build. LangChain calls it
after each model reply, with the reply's token counts.

PRICES are US dollars per million tokens. Anthropic rates are from public
price trackers (Nov 2026); cache reads are priced at Anthropic's usual 10% of
input. Models not listed still have their tokens counted, with no cost.
"""

import threading

from langchain_core.callbacks import BaseCallbackHandler

PRICES = {
    # model: (input, cache write, cache read, output)
    "claude-sonnet-5-5": (2.00, 2.50, 0.20, 10.00),
    "claude-haiku-5-5": (0.10, 0.125, 0.01, 0.50),
    "claude-opus-5-5": (4.00, 5.00, 0.40, 20.00),
}

FIELDS = ("calls", "input_tokens", "cache_write_tokens", "cache_read_tokens", "output_tokens")


def _price(model: str) -> tuple | None:
    # Replies may name a dated version, such as claude-sonnet-5-5-20260915.
    for name, price in PRICES.items():
        if model == name or model.startswith(f"{name}-"):
            return price
    return None


def cost_usd(model: str, counts: dict) -> float | None:
    price = _price(model)
    if price is None:
        return None
    rate_in, rate_write, rate_read, rate_out = price
    return (
        counts["input_tokens"] * rate_in
        + counts["cache_write_tokens"] * rate_write
        + counts["cache_read_tokens"] * rate_read
        + counts["output_tokens"] * rate_out
    ) / 1_000_000


class UsageMeter(BaseCallbackHandler):
    """Adds up the tokens of every model reply in one build."""

    def __init__(self):
        self._lock = threading.Lock()
        self._models: dict[str, dict] = {}

    def on_llm_end(self, response, **kwargs) -> None:
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                usage = getattr(message, "usage_metadata", None)
                if not usage:
                    continue
                meta = message.response_metadata or {}
                model = meta.get("model_name") or meta.get("model") or "unknown"
                details = usage.get("input_token_details") or {}
                read = details.get("cache_read") or 0
                write = details.get("cache_creation") or 0
                self.add(
                    model,
                    # input_tokens includes cached tokens; count each kind once
                    input_tokens=max(0, usage.get("input_tokens", 0) - read - write),
                    cache_write_tokens=write,
                    cache_read_tokens=read,
                    output_tokens=usage.get("output_tokens", 0),
                )

    def add(self, model: str, **counts) -> None:
        with self._lock:
            total = self._models.setdefault(model, dict.fromkeys(FIELDS, 0))
            total["calls"] += 1
            for field, value in counts.items():
                total[field] += value

    def summary(self) -> dict:
        with self._lock:
            models = {name: dict(counts) for name, counts in self._models.items()}
        costs = {name: cost_usd(name, counts) for name, counts in models.items()}
        for name, cost in costs.items():
            models[name]["cost_usd"] = None if cost is None else round(cost, 4)
        known = [c for c in costs.values() if c is not None]
        return {
            "models": models,
            **{field: sum(m[field] for m in models.values()) for field in FIELDS},
            # None when no model is priced; partial when only some are
            "cost_usd": round(sum(known), 4) if known else None,
            "complete": len(known) == len(costs),
        }
