"""LLM gateway: the single entry point the app uses to talk to any model.

Cross-cutting concerns live here once instead of in every feature:
  * response cache (identical prompt -> zero-cost answer)
  * model routing by tier (cheap model for triage, strong model for chat)
  * retries with exponential backoff on retryable errors (429 / 5xx / network)
  * provider fallback chain (e.g. Claude -> Azure OpenAI -> Mock)
  * token / cost / latency accounting (DB row + Prometheus metrics)
"""

import hashlib
import json
import logging
import random
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.cache import Cache
from app.core.config import Settings
from app.core.logging import log_event
from app.core.metrics import LLM_CACHE, LLM_COST, LLM_LATENCY, LLM_REQUESTS, LLM_TOKENS
from app.services.llm.base import LLMProvider, LLMRequest, LLMResult, ProviderError, estimate_cost
from app.services.llm.providers import MockProvider

logger = logging.getLogger("llm.gateway")


@dataclass
class CallRecord:
    task: str
    user_id: int | None
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    cache_hit: bool
    fallback_used: bool
    success: bool


def db_recorder(rec: CallRecord) -> None:
    from app.db import SessionLocal
    from app.models import LLMUsage

    with SessionLocal() as db:
        db.add(LLMUsage(**rec.__dict__))
        db.commit()


def db_spend_today() -> float:
    from sqlalchemy import func, select

    from app.db import SessionLocal
    from app.models import LLMUsage

    midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        return float(db.scalar(select(func.coalesce(func.sum(LLMUsage.cost_usd), 0.0))
                               .where(LLMUsage.created_at >= midnight)) or 0.0)


class AllProvidersFailed(Exception):
    pass


class LLMGateway:
    def __init__(
        self,
        providers: list[LLMProvider],
        cache: Cache,
        settings: Settings,
        recorder: Callable[[CallRecord], None] = db_recorder,
        sleep: Callable[[float], None] = time.sleep,
        spend_today: Callable[[], float] = db_spend_today,
    ) -> None:
        self.providers = providers
        self.cache = cache
        self.s = settings
        self.record = recorder
        self._sleep = sleep
        self._spend_today = spend_today
        self._spend_checked = (0.0, 0.0)  # (monotonic time, spend) - avoid a DB query on every call

    def budget_exceeded(self) -> bool:
        """Hard daily spend cap: protects a public demo (or a runaway loop) from an unbounded bill."""
        budget = self.s.llm_daily_budget_usd
        if budget <= 0:
            return False
        checked_at, spend = self._spend_checked
        if time.monotonic() - checked_at > 30:
            spend = self._spend_today()
            self._spend_checked = (time.monotonic(), spend)
        return spend >= budget

    def _chain(self) -> tuple[list[LLMProvider], bool]:
        """Providers to try, and whether we're degraded (budget exhausted -> offline mock only)."""
        if self.budget_exceeded():
            logger.warning("daily LLM budget exhausted; serving offline mock")
            mocks = [p for p in self.providers if p.name == "mock"]
            return mocks or [MockProvider()], True
        return self.providers, False

    @property
    def primary(self) -> LLMProvider:
        return self.providers[0]

    def _cache_key(self, req: LLMRequest, scope: str | None) -> str:
        """Exact-match key over the full request, or over a caller-supplied `scope` (e.g. normalised
        question + retrieved chunk ids) so FAQ answers are reused across users and conversations."""
        p = self.primary
        body = scope if scope is not None else [req.system, req.messages, req.json_schema, req.max_tokens]
        raw = json.dumps([p.name, p.model_for(req.tier), body], sort_keys=True)
        return "llm:" + hashlib.sha256(raw.encode()).hexdigest()

    def _finish(self, task: str, user_id: int | None, result: LLMResult, started: float,
                cache_hit: bool, fallback_used: bool) -> CallRecord:
        latency_ms = int((time.perf_counter() - started) * 1000)
        cost = 0.0 if cache_hit else estimate_cost(result.model, result.input_tokens, result.output_tokens)
        rec = CallRecord(task, user_id, result.provider, result.model,
                         0 if cache_hit else result.input_tokens, 0 if cache_hit else result.output_tokens,
                         cost, latency_ms, cache_hit, fallback_used, True)
        LLM_REQUESTS.labels(rec.provider, rec.model, task, "cache_hit" if cache_hit else "ok").inc()
        LLM_LATENCY.labels(rec.provider, task).observe(latency_ms / 1000)
        if not cache_hit:
            LLM_TOKENS.labels(rec.provider, rec.model, "input").inc(rec.input_tokens)
            LLM_TOKENS.labels(rec.provider, rec.model, "output").inc(rec.output_tokens)
            LLM_COST.labels(rec.provider, rec.model).inc(cost)
        log_event(logger, "llm_call", **rec.__dict__)
        self.record(rec)
        return rec

    def _failed(self, task: str, user_id: int | None, provider: LLMProvider, req: LLMRequest, err: Exception) -> None:
        LLM_REQUESTS.labels(provider.name, provider.model_for(req.tier), task, "error").inc()
        logger.warning("llm provider failed", extra={"extra_fields": {"provider": provider.name, "error": str(err)}})

    def _with_retries(self, fn: Callable[[], LLMResult]) -> LLMResult:
        attempt = 0
        while True:
            try:
                return fn()
            except ProviderError as err:
                if not err.retryable or attempt >= self.s.llm_max_retries:
                    raise
                # Exponential backoff with jitter: 0.5s, 1s, 2s ... (+0-250ms) to avoid thundering herds.
                self._sleep(0.5 * 2**attempt + random.uniform(0, 0.25))  # noqa: S311 (jitter, not crypto)
                attempt += 1

    def complete(self, req: LLMRequest, task: str, user_id: int | None = None,
                 use_cache: bool = True, cache_scope: str | None = None) -> tuple[LLMResult, CallRecord]:
        started = time.perf_counter()
        key = self._cache_key(req, cache_scope)
        if use_cache and (cached := self.cache.get(key)):
            LLM_CACHE.labels("hit").inc()
            result = LLMResult(**json.loads(cached))
            return result, self._finish(task, user_id, result, started, cache_hit=True, fallback_used=False)
        LLM_CACHE.labels("miss").inc()

        errors = []
        chain, degraded = self._chain()
        for i, provider in enumerate(chain):
            try:
                result = self._with_retries(lambda p=provider: p.complete(req))
            except ProviderError as err:
                self._failed(task, user_id, provider, req, err)
                errors.append(str(err))
                continue
            fallback = i > 0 or degraded
            if use_cache and not fallback:  # never cache a degraded answer under the primary's key
                self.cache.set(key, json.dumps(result.__dict__), self.s.llm_cache_ttl_seconds)
            return result, self._finish(task, user_id, result, started, cache_hit=False, fallback_used=fallback)
        raise AllProvidersFailed("; ".join(errors))

    def stream(self, req: LLMRequest, task: str, user_id: int | None = None,
               use_cache: bool = True, cache_scope: str | None = None) -> Iterator[str | CallRecord]:
        """Yield text deltas, then the CallRecord. Falls back only if a provider fails before its
        first token: once text has reached the user we can't silently switch models mid-answer."""
        started = time.perf_counter()
        key = self._cache_key(req, cache_scope)
        if use_cache and (cached := self.cache.get(key)):
            LLM_CACHE.labels("hit").inc()
            result = LLMResult(**json.loads(cached))
            yield result.text
            yield self._finish(task, user_id, result, started, cache_hit=True, fallback_used=False)
            return
        LLM_CACHE.labels("miss").inc()

        errors = []
        chain, degraded = self._chain()
        for i, provider in enumerate(chain):
            emitted = False
            try:
                for item in provider.stream(req):
                    if isinstance(item, LLMResult):
                        fallback = i > 0 or degraded
                        if use_cache and not fallback:
                            self.cache.set(key, json.dumps(item.__dict__), self.s.llm_cache_ttl_seconds)
                        yield self._finish(task, user_id, item, started, cache_hit=False, fallback_used=fallback)
                        return
                    emitted = True
                    yield item
            except ProviderError as err:
                self._failed(task, user_id, provider, req, err)
                if emitted:
                    raise
                errors.append(str(err))
        raise AllProvidersFailed("; ".join(errors))
