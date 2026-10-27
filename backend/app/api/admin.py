from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, cast, func, select

from app.core.config import get_settings
from app.core.security import DbSession, require_roles
from app.models import Document, LLMUsage, Role, Ticket, User
from app.services.llm.factory import get_gateway
from app.services.llm.gateway import db_spend_today

router = APIRouter(prefix="/api/admin", tags=["admin"])
Admin = Annotated[User, Depends(require_roles(Role.admin))]


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    values = sorted(values)
    return values[min(len(values) - 1, int(round(pct * (len(values) - 1))))]


@router.get("/stats")
def stats(_: Admin, db: DbSession, days: Annotated[int, Query(ge=1, le=90)] = 7):
    since = datetime.now(UTC) - timedelta(days=days)
    in_window = LLMUsage.created_at >= since

    totals = db.execute(
        select(
            func.count(LLMUsage.id),
            func.coalesce(func.sum(LLMUsage.input_tokens), 0),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0),
            func.coalesce(func.sum(LLMUsage.cost_usd), 0.0),
            func.coalesce(func.sum(cast(LLMUsage.cache_hit, Integer)), 0),
            func.coalesce(func.sum(cast(LLMUsage.fallback_used, Integer)), 0),
        ).where(in_window)
    ).one()
    calls, tokens_in, tokens_out, cost, cache_hits, fallbacks = totals

    # Percentiles in Python keep this portable across SQLite/PostgreSQL; bounded to recent rows.
    latencies = db.scalars(
        select(LLMUsage.latency_ms).where(in_window, LLMUsage.cache_hit.is_(False))
        .order_by(LLMUsage.created_at.desc()).limit(5000)
    ).all()

    by_model = [
        {"provider": p, "model": m, "task": t, "calls": c, "cost_usd": round(float(cs), 6), "avg_latency_ms": int(lat or 0)}
        for p, m, t, c, cs, lat in db.execute(
            select(LLMUsage.provider, LLMUsage.model, LLMUsage.task, func.count(), func.sum(LLMUsage.cost_usd),
                   func.avg(LLMUsage.latency_ms))
            .where(in_window).group_by(LLMUsage.provider, LLMUsage.model, LLMUsage.task)
        ).all()
    ]
    day = func.date(LLMUsage.created_at)
    daily = [
        {"day": str(d), "calls": c, "cost_usd": round(float(cs), 6)}
        for d, c, cs in db.execute(
            select(day, func.count(), func.sum(LLMUsage.cost_usd)).where(in_window).group_by(day).order_by(day)
        ).all()
    ]
    tickets_by_category = dict(db.execute(
        select(func.coalesce(Ticket.category, "Untriaged"), func.count()).group_by(Ticket.category)).all())
    tickets_by_status = {s.value: n for s, n in db.execute(select(Ticket.status, func.count()).group_by(Ticket.status)).all()}

    return {
        "window_days": days,
        "llm": {
            "calls": calls,
            "input_tokens": int(tokens_in),
            "output_tokens": int(tokens_out),
            "cost_usd": round(float(cost), 6),
            "cache_hit_rate": round(cache_hits / calls, 3) if calls else 0.0,
            "fallback_count": int(fallbacks),
            "p50_latency_ms": _percentile(latencies, 0.50),
            "p95_latency_ms": _percentile(latencies, 0.95),
            "by_model": by_model,
            "daily": daily,
        },
        "tickets": {"by_category": tickets_by_category, "by_status": tickets_by_status},
        "documents": db.scalar(select(func.count(Document.id))),
        "users": db.scalar(select(func.count(User.id))),
        "gateway": {
            "providers": [p.name for p in get_gateway().providers],
            "configured_primary": get_settings().llm_provider,
            "daily_budget_usd": get_settings().llm_daily_budget_usd,
            "spent_today_usd": round(db_spend_today(), 6),
        },
    }
