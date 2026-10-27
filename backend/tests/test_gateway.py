import pytest

from app.core.cache import InMemoryCache
from app.core.config import Settings
from app.services.llm.base import LLMProvider, LLMRequest, LLMResult, ProviderError, estimate_cost
from app.services.llm.factory import build_chain
from app.services.llm.gateway import AllProvidersFailed, CallRecord, LLMGateway
from app.services.llm.providers import MockProvider


class ScriptedProvider(LLMProvider):
    """Fails with the scripted errors first, then succeeds."""

    def __init__(self, name: str, errors: list[ProviderError] | None = None, model: str = "claude-sonnet-5-5"):
        self.name, self.errors, self.model, self.calls = name, list(errors or []), model, 0

    def model_for(self, tier):
        return self.model

    def complete(self, req):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return LLMResult(f"answer from {self.name}", self.name, self.model, 1000, 200)

    def stream(self, req):
        result = self.complete(req)
        yield from ["answer ", "from ", self.name]
        yield result


def gateway(*providers, records=None, budget=0.0, spent=0.0):
    s = Settings(llm_max_retries=2, llm_cache_ttl_seconds=60, llm_daily_budget_usd=budget)
    return LLMGateway(list(providers), InMemoryCache(), s,
                      recorder=(records.append if records is not None else lambda r: None), sleep=lambda _: None,
                      spend_today=lambda: spent)


REQ = LLMRequest(system="sys", messages=[{"role": "user", "content": "hello"}])


def test_cost_estimate_uses_per_model_pricing():
    assert estimate_cost("claude-sonnet-5-5", 1_000_000, 1_000_000) == 12.0
    assert estimate_cost("claude-haiku-5-5", 1000, 200) == pytest.approx(0.0002)
    assert estimate_cost("unknown-model", 1000, 1000) == 0.0


def test_retries_retryable_errors_then_succeeds():
    p = ScriptedProvider("claude", [ProviderError("429", True), ProviderError("503", True)])
    records = []
    result, rec = gateway(p, records=records).complete(REQ, task="chat")
    assert p.calls == 3 and result.provider == "claude"
    assert rec.cost_usd == estimate_cost("claude-sonnet-5-5", 1000, 200)
    assert records == [rec] and not rec.fallback_used


def test_falls_back_on_non_retryable_error_without_retrying():
    primary = ScriptedProvider("claude", [ProviderError("400 bad request", False)])
    backup = ScriptedProvider("azure_openai", model="gpt-4o")
    result, rec = gateway(primary, backup).complete(REQ, task="chat")
    assert primary.calls == 1
    assert result.provider == "azure_openai" and rec.fallback_used


def test_falls_back_after_retries_exhausted():
    primary = ScriptedProvider("claude", [ProviderError("503", True)] * 3)
    result, _ = gateway(primary, MockProvider()).complete(REQ, task="chat")
    assert primary.calls == 3 and result.provider == "mock"


def test_all_providers_failing_raises():
    with pytest.raises(AllProvidersFailed):
        gateway(ScriptedProvider("claude", [ProviderError("401", False)])).complete(REQ, task="chat")


def test_cache_hit_is_free_and_skips_provider():
    p = ScriptedProvider("claude")
    gw = gateway(p)
    gw.complete(REQ, task="chat")
    result, rec = gw.complete(REQ, task="chat")
    assert p.calls == 1
    assert rec.cache_hit and rec.cost_usd == 0 and result.text == "answer from claude"


def test_fallback_answers_are_not_cached():
    primary = ScriptedProvider("claude", [ProviderError("400", False)])
    gw = gateway(primary, ScriptedProvider("mock", model="mock-chat"))
    gw.complete(REQ, task="chat")
    _, rec = gw.complete(REQ, task="chat")
    assert not rec.cache_hit and primary.calls == 2  # primary tried again once healthy


def test_stream_falls_back_before_first_token():
    primary = ScriptedProvider("claude", [ProviderError("503", False)])
    items = list(gateway(primary, MockProvider()).stream(REQ, task="chat"))
    assert isinstance(items[-1], CallRecord) and items[-1].fallback_used
    assert "".join(i for i in items if isinstance(i, str))


def test_build_chain_skips_unconfigured_providers():
    chain = build_chain(Settings(llm_provider="claude", llm_fallback_providers="openai,mock", anthropic_api_key=None))
    assert [p.name for p in chain] == ["mock"]


def test_mock_provider_structured_triage_output():
    import json

    req = LLMRequest(system="", messages=[{"role": "user", "content": "VPN down, cannot work, urgent"}],
                     tier="fast", json_schema={"type": "object"})
    data = json.loads(MockProvider().complete(req).text)
    assert data["category"] == "Access" and data["priority"] == "urgent"


def test_daily_budget_exhausted_serves_mock_and_skips_paid_provider():
    paid = ScriptedProvider("claude")
    gw = gateway(paid, budget=1.0, spent=1.02)
    result, rec = gw.complete(REQ, task="chat")
    assert paid.calls == 0 and result.provider == "mock" and rec.fallback_used
    # degraded answers are not cached: once the budget resets, the real model answers again
    gw._spend_today, gw._spend_checked = (lambda: 0.0), (0.0, 0.0)
    result, _ = gw.complete(REQ, task="chat")
    assert result.provider == "claude" and paid.calls == 1


def test_budget_under_limit_uses_primary():
    paid = ScriptedProvider("claude")
    items = list(gateway(paid, budget=1.0, spent=0.4).stream(REQ, task="chat"))
    assert items[-1].provider == "claude" and not items[-1].fallback_used


def test_hosted_postgres_urls_get_sqlalchemy_driver():
    assert Settings(database_url="postgres://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"
    assert Settings(database_url="postgresql://u:p@h/db?sslmode=require").database_url.startswith("postgresql+psycopg://")
    assert Settings(database_url="sqlite:///x.db").database_url == "sqlite:///x.db"
