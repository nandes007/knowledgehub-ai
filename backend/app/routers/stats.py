import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func
from sqlmodel import Session, select

from app.deps import AdminDep, SessionDep
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.message import Message
from app.models.user import User

# Mounted under /companies/{slug}.
router = APIRouter()

_STATS_WINDOW_DAYS = 30

# ponytail: one blended $/1k-token rate rather than a per-model, per-direction
# price table. Good enough for a ballpark "what did yesterday cost"; swap in
# real per-model prompt/completion pricing if the estimate needs to be exact.
_PRICE_PER_1K_TOKENS_USD = 0.0003


def usage_stats(session: Session, company_id: uuid.UUID | None = None) -> dict:
    """Usage for one company, or for the whole instance when company_id is None."""
    since = datetime.now(timezone.utc) - timedelta(days=_STATS_WINDOW_DAYS)
    day_column = func.date(Message.created_at)

    def messages(statement):
        if company_id is None:
            return statement
        return statement.join(Conversation, Message.conversation_id == Conversation.id).where(
            Conversation.company_id == company_id
        )

    def documents(statement):
        return statement if company_id is None else statement.where(Document.company_id == company_id)

    rows = session.exec(
        messages(select(day_column, func.count()))
        .where(Message.created_at >= since)
        .group_by(day_column)
        .order_by(day_column)
    ).all()
    document_count = session.exec(documents(select(func.count()).select_from(Document))).one()
    total_tokens = session.exec(
        messages(select(func.coalesce(func.sum(Message.token_count), 0))).where(Message.role == "assistant")
    ).one()
    documents_per_user = session.exec(
        documents(select(User.email, func.count(Document.id)).join(Document, Document.uploaded_by == User.id))
        .group_by(User.email)
        .order_by(func.count(Document.id).desc(), User.email)
    ).all()
    tokens_per_day = session.exec(
        messages(select(day_column, func.coalesce(func.sum(Message.token_count), 0)))
        .where(Message.created_at >= since, Message.role == "assistant")
        .group_by(day_column)
        .order_by(day_column)
    ).all()

    return {
        "messages_per_day": [{"date": str(day), "count": count} for day, count in rows],
        "document_count": document_count,
        "estimated_cost_usd": _cost_usd(total_tokens),
        "documents_per_user": [{"email": email, "count": count} for email, count in documents_per_user],
        "cost_per_day": [{"date": str(day), "cost_usd": _cost_usd(tokens)} for day, tokens in tokens_per_day],
    }


@router.get("/stats")
def get_stats(session: SessionDep, ctx: AdminDep) -> dict:
    return usage_stats(session, ctx.company.id)


def _cost_usd(tokens: int) -> float:
    return round((tokens / 1000) * _PRICE_PER_1K_TOKENS_USD, 4)
