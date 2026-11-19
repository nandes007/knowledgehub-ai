import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from sqlmodel import select

from app.deps import AdminDep, CurrentUserDep, SessionDep
from app.models.company import Company
from app.models.department import Department
from app.models.invite import Invite
from app.models.membership import Membership
from app.models.user import User
from app.schemas.company import InviteAccepted, InviteCreate, InviteCreated, InvitePreview, InviteRead
from app.services import invites

# Mounted under /companies/{slug}.
router = APIRouter(tags=["invites"])
# Account-level: the invitee is not a member yet.
account_router = APIRouter(prefix="/invites", tags=["invites"])


def _read(invite: Invite) -> dict:
    return invite.model_dump(include={"id", "email", "role", "department_id", "expires_at", "created_at"})


@router.post("/invites", response_model=InviteCreated, status_code=status.HTTP_201_CREATED)
def create_invite(payload: InviteCreate, ctx: AdminDep, session: SessionDep) -> InviteCreated:
    email = payload.email.strip().lower()
    if payload.role not in ("admin", "member"):
        raise HTTPException(status_code=422, detail="Role must be admin or member")
    if payload.role == "admin" and ctx.role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can invite admins")

    if payload.department_id is not None:
        department = session.get(Department, payload.department_id)
        if department is None or department.company_id != ctx.company.id:
            raise HTTPException(status_code=404, detail="Department not found")

    already_member = session.exec(
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.company_id == ctx.company.id, func.lower(User.email) == email)
    ).first()
    if already_member is not None:
        raise HTTPException(status_code=409, detail="This person is already a member")

    # A new invite replaces an unaccepted one, so only the latest link works.
    for stale in session.exec(
        select(Invite).where(
            Invite.company_id == ctx.company.id, Invite.email == email, Invite.accepted_at.is_(None)
        )
    ):
        session.delete(stale)

    token, token_hash = invites.new_token()
    invite = Invite(
        company_id=ctx.company.id,
        email=email,
        role=payload.role,
        department_id=payload.department_id,
        invited_by=ctx.user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + invites.INVITE_TTL,
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return InviteCreated(**_read(invite), token=token)


@router.get("/invites", response_model=list[InviteRead])
def list_invites(ctx: AdminDep, session: SessionDep) -> list[dict]:
    rows = session.exec(
        select(Invite).where(Invite.company_id == ctx.company.id).order_by(Invite.created_at.desc())
    )
    return [_read(invite) for invite in rows if invites.is_pending(invite)]


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invite(invite_id: uuid.UUID, ctx: AdminDep, session: SessionDep) -> None:
    invite = session.get(Invite, invite_id)
    if invite is None or invite.company_id != ctx.company.id or invite.accepted_at is not None:
        raise HTTPException(status_code=404, detail="Invite not found")
    session.delete(invite)
    session.commit()


def _pending_or_404(session: SessionDep, token: str) -> Invite:
    invite = invites.find_pending(session, token)
    if invite is None:
        raise HTTPException(status_code=404, detail="This invite link is invalid or has expired")
    return invite


@account_router.get("/{token}", response_model=InvitePreview)
def preview_invite(token: str, session: SessionDep) -> InvitePreview:
    """Public: lets the invite page say which company and email before signing in."""
    invite = _pending_or_404(session, token)
    company = session.get(Company, invite.company_id)
    return InvitePreview(company_name=company.name, email=invite.email, role=invite.role)


@account_router.post("/{token}/accept", response_model=InviteAccepted)
def accept_invite(token: str, current_user: CurrentUserDep, session: SessionDep) -> InviteAccepted:
    invite = _pending_or_404(session, token)
    if not invites.is_for(invite, current_user.email):
        raise HTTPException(status_code=403, detail="This invite was sent to a different email address")

    company = session.get(Company, invite.company_id)
    existing = session.exec(
        select(Membership).where(
            Membership.company_id == invite.company_id, Membership.user_id == current_user.id
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"You are already a member of {company.name}")

    invites.accept(session, invite, current_user)
    session.commit()
    return InviteAccepted(company_slug=company.slug)
