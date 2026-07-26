from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import func
from sqlmodel import select

from app.deps import CurrentUserDep, SessionDep
from app.models.document import Document
from app.models.message import Message

router = APIRouter()

_STATS_WINDOW_DAYS = 30

# ponytail: one blended $/1k-token rate rather than a per-model, per-direction
# price table. Good enough for a ballpark "what did yesterday cost"; swap in
# real per-model prompt/completion pricing if the estimate needs to be exact.
_PRICE_PER_1K_TOKENS_USD = 0.0003


@router.get("/stats")
def get_stats(session: SessionDep, current_user: CurrentUserDep) -> dict:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    since = datetime.now(timezone.utc) - timedelta(days=_STATS_WINDOW_DAYS)
    day_column = func.date(Message.created_at)
    rows = session.exec(
        select(day_column, func.count())
        .where(Message.created_at >= since)
        .group_by(day_column)
        .order_by(day_column)
    ).all()

    document_count = session.exec(select(func.count()).select_from(Document)).one()
    total_tokens = session.exec(
        select(func.coalesce(func.sum(Message.token_count), 0)).where(Message.role == "assistant")
    ).one()

    return {
        "messages_per_day": [{"date": str(day), "count": count} for day, count in rows],
        "document_count": document_count,
        "estimated_cost_usd": round((total_tokens / 1000) * _PRICE_PER_1K_TOKENS_USD, 4),
    }
