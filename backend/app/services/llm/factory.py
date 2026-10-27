from collections.abc import Callable
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.providers import AzureOpenAIProvider, ClaudeProvider, MockProvider, OpenAIProvider

# Factory registry: adding a vendor (Gemini, Bedrock, ...) is one class + one line here.
PROVIDERS: dict[str, Callable[[Settings], LLMProvider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "azure_openai": AzureOpenAIProvider,
    "mock": lambda _s: MockProvider(),
}

REQUIRED_KEYS = {
    "claude": "anthropic_api_key",
    "openai": "openai_api_key",
    "azure_openai": "azure_openai_api_key",
}


def build_provider(name: str, s: Settings) -> LLMProvider | None:
    """Return the provider, or None when it isn't configured (so it's skipped, not crashed on)."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown LLM provider '{name}'. Options: {', '.join(PROVIDERS)}")
    key_attr = REQUIRED_KEYS.get(name)
    if key_attr and not getattr(s, key_attr):
        return None
    return PROVIDERS[name](s)


def build_chain(s: Settings) -> list[LLMProvider]:
    names = [s.llm_provider, *[n.strip() for n in s.llm_fallback_providers.split(",") if n.strip()]]
    chain: list[LLMProvider] = []
    for name in dict.fromkeys(names):  # dedupe, keep order
        provider = build_provider(name, s)
        if provider:
            chain.append(provider)
    return chain or [MockProvider()]


@lru_cache
def get_gateway():
    from app.core.cache import get_cache
    from app.services.llm.gateway import LLMGateway

    s = get_settings()
    return LLMGateway(build_chain(s), get_cache(), s)
