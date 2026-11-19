import uuid

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.deps import AdminDep, CompanyContext, MemberDep, OwnerDep, SessionDep
from app.models.department import Department
from app.models.membership import Membership
from app.models.user import User
from app.schemas.company import MemberRead, MemberUpdate, OwnershipTransfer
from app.services.companies import delete_conversations
from ingestion.pipeline import delete_files

router = APIRouter(tags=["members"])


def _read(session: SessionDep, membership: Membership, user: User) -> MemberRead:
    department = session.get(Department, membership.department_id) if membership.department_id else None
    return MemberRead(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        department_id=membership.department_id,
        department_name=department.name if department else None,
        joined_at=membership.created_at,
    )


def _membership_of(session: SessionDep, ctx: CompanyContext, user_id: uuid.UUID) -> Membership:
    membership = session.exec(
        select(Membership).where(Membership.company_id == ctx.company.id, Membership.user_id == user_id)
    ).first()
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return membership


def _require_can_manage(ctx: CompanyContext, target: Membership) -> None:
    """The owner manages everyone; an admin manages members only."""
    if ctx.role != "owner" and target.role != "member":
        raise HTTPException(status_code=403, detail="Only the owner can manage admins")


@router.get("/members", response_model=list[MemberRead])
def list_members(ctx: AdminDep, session: SessionDep) -> list[MemberRead]:
    rows = session.exec(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.company_id == ctx.company.id)
        .order_by(Membership.created_at)
    ).all()
    return [_read(session, membership, user) for membership, user in rows]


@router.patch("/members/{user_id}", response_model=MemberRead)
def update_member(user_id: uuid.UUID, payload: MemberUpdate, ctx: AdminDep, session: SessionDep) -> MemberRead:
    target = _membership_of(session, ctx, user_id)
    is_self = user_id == ctx.user.id
    if not is_self:
        _require_can_manage(ctx, target)

    if payload.role is not None and payload.role != target.role:
        if is_self:
            raise HTTPException(status_code=403, detail="You cannot change your own role")
        if payload.role == "owner":
            raise HTTPException(status_code=400, detail="Ownership changes by transfer only")
        if payload.role not in ("admin", "member"):
            raise HTTPException(status_code=422, detail="Role must be admin or member")
        if ctx.role != "owner":
            raise HTTPException(status_code=403, detail="Only the owner can change roles")
        target.role = payload.role

    if "department_id" in payload.model_fields_set:
        if payload.department_id is not None:
            department = session.get(Department, payload.department_id)
            if department is None or department.company_id != ctx.company.id:
                raise HTTPException(status_code=404, detail="Department not found")
        target.department_id = payload.department_id

    session.add(target)
    session.commit()
    session.refresh(target)
    return _read(session, target, session.get(User, user_id))


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(user_id: uuid.UUID, ctx: MemberDep, session: SessionDep) -> None:
    """Remove someone, or leave (your own id). Their uploads stay; their chats here go."""
    if user_id == ctx.user.id:
        target = ctx.membership
    else:
        if not ctx.membership.at_least("admin"):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        target = _membership_of(session, ctx, user_id)
        _require_can_manage(ctx, target)

    if target.role == "owner":
        # Only reachable as the owner leaving: nobody else can manage the owner.
        raise HTTPException(status_code=409, detail="Transfer ownership before leaving the company")

    files = delete_conversations(session, ctx.company.id, user_id)
    session.delete(target)
    session.commit()
    delete_files(files)


@router.post("/transfer-ownership", response_model=MemberRead)
def transfer_ownership(payload: OwnershipTransfer, ctx: OwnerDep, session: SessionDep) -> MemberRead:
    if payload.user_id == ctx.user.id:
        raise HTTPException(status_code=400, detail="You already own this company")
    target = _membership_of(session, ctx, payload.user_id)

    # Step down first: the company may never hold two owners, even mid-transaction.
    ctx.membership.role = "admin"
    session.add(ctx.membership)
    session.flush()
    target.role = "owner"
    session.add(target)
    session.commit()
    session.refresh(target)
    return _read(session, target, session.get(User, payload.user_id))
