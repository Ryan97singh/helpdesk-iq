from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram("http_request_duration_seconds", "HTTP latency", ["method", "route"])

LLM_REQUESTS = Counter("llm_requests_total", "LLM gateway calls", ["provider", "model", "task", "outcome"])
LLM_TOKENS = Counter("llm_tokens_total", "LLM tokens", ["provider", "model", "direction"])
LLM_COST = Counter("llm_cost_usd_total", "Estimated LLM spend in USD", ["provider", "model"])
LLM_LATENCY = Histogram(
    "llm_latency_seconds", "LLM call latency", ["provider", "task"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 32),
)
LLM_CACHE = Counter("llm_cache_total", "LLM response cache lookups", ["result"])

EVENTS = Counter("events_processed_total", "Events processed by workers", ["type", "outcome"])
