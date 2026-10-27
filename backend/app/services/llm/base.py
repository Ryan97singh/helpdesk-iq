"""Provider-agnostic contracts for the LLM gateway (Strategy pattern).

Every provider (Claude, OpenAI, Azure OpenAI, Mock) implements `LLMProvider`, so the rest of the
app never imports a vendor SDK. Swapping or adding a vendor is a new class + one factory entry.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

Tier = Literal["chat", "fast"]  # model routing: strong model for answers, cheap model for classification

# USD per 1M tokens (input, output). Used for per-request cost accounting and dashboards.
PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5-5": (4.00, 20.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "mock-chat": (0.0, 0.0),
    "mock-fast": (0.0, 0.0),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price, out_price = PRICING.get(model, (0.0, 0.0))
    return round((input_tokens * in_price + output_tokens * out_price) / 1_000_000, 6)


@dataclass
class LLMRequest:
    system: str
    messages: list[dict]                 # [{"role": "user"|"assistant", "content": str}]
    tier: Tier = "chat"
    max_tokens: int = 1024
    json_schema: dict | None = None      # structured output; provider guarantees valid JSON


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    extra: dict = field(default_factory=dict)


class ProviderError(Exception):
    def __init__(self, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def model_for(self, tier: Tier) -> str: ...

    @abstractmethod
    def complete(self, req: LLMRequest) -> LLMResult: ...

    @abstractmethod
    def stream(self, req: LLMRequest) -> Iterator[str | LLMResult]:
        """Yield text deltas, then exactly one final LLMResult carrying usage."""
