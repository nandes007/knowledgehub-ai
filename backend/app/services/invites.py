import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.invite import Invite
from app.models.membership import Membership
from app.models.user import User

INVITE_TTL = timedelta(days=7)


def new_token() -> tuple[str, str]:
    """(token for the link, hash to store)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    # SQLite hands timestamps back without a timezone.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def is_pending(invite: Invite) -> bool:
    return invite.accepted_at is None and _aware(invite.expires_at) > datetime.now(timezone.utc)


def find_pending(session: Session, token: str) -> Invite | None:
    invite = session.exec(select(Invite).where(Invite.token_hash == hash_token(token))).first()
    return invite if invite is not None and is_pending(invite) else None


def is_for(invite: Invite, email: str) -> bool:
    return invite.email == email.strip().lower()


def accept(session: Session, invite: Invite, user: User) -> Membership:
    """Single use: the caller has checked the invite is pending and for this user."""
    membership = Membership(
        user_id=user.id,
        company_id=invite.company_id,
        role=invite.role,
        department_id=invite.department_id,
    )
    invite.accepted_at = datetime.now(timezone.utc)
    session.add(membership)
    session.add(invite)
    return membership
