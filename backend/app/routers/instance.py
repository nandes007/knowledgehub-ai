import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import delete, select, update

from app.deps import InstanceAdminDep, SessionDep
from app.models.company import Company
from app.models.document import Document
from app.models.invite import Invite
from app.models.membership import Membership
from app.models.user import User
from app.routers.stats import usage_stats
from app.schemas.instance import InstanceCompanyRead, InstanceUserCompany, InstanceUserRead
from app.services.companies import delete_company, delete_conversations
from ingestion.index import VectorStore, get_vector_store
from ingestion.pipeline import delete_files

# Platform administration. Nothing here reads a company's documents or chats.
router = APIRouter(prefix="/instance", tags=["instance"])


def _user_to_read(user: User, session: SessionDep) -> InstanceUserRead:
    rows = session.exec(
        select(Company, Membership)
        .join(Membership, Membership.company_id == Company.id)
        .where(Membership.user_id == user.id)
        .order_by(Company.name)
    ).all()
    return InstanceUserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_instance_admin=user.is_instance_admin,
        approval_status=user.approval_status,
        companies=[InstanceUserCompany(name=c.name, slug=c.slug, role=m.role) for c, m in rows],
        created_at=user.created_at,
    )


def _user_or_404(session: SessionDep, user_id: uuid.UUID) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users", response_model=list[InstanceUserRead])
def list_users(
    session: SessionDep,
    current_user: InstanceAdminDep,
    approval_status: str | None = Query(default=None),
) -> list[InstanceUserRead]:
    statement = select(User)
    if approval_status is not None:
        statement = statement.where(User.approval_status == approval_status)
    users = session.exec(statement.order_by(User.created_at.desc())).all()
    return [_user_to_read(u, session) for u in users]


def _set_approval(session: SessionDep, user_id: uuid.UUID, approval_status: str) -> InstanceUserRead:
    user = _user_or_404(session, user_id)
    user.approval_status = approval_status
    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_to_read(user, session)


@router.patch("/users/{user_id}/approve", response_model=InstanceUserRead)
def approve_user(user_id: uuid.UUID, session: SessionDep, current_user: InstanceAdminDep) -> InstanceUserRead:
    return _set_approval(session, user_id, "approved")


@router.patch("/users/{user_id}/reject", response_model=InstanceUserRead)
def reject_user(user_id: uuid.UUID, session: SessionDep, current_user: InstanceAdminDep) -> InstanceUserRead:
    if user_id == current_user.id:
        raise HTTPException(status_code=403, detail="Cannot reject own account")
    return _set_approval(session, user_id, "rejected")


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: uuid.UUID, session: SessionDep, current_user: InstanceAdminDep) -> None:
    if user_id == current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete own account")
    user = _user_or_404(session, user_id)

    memberships = list(session.exec(select(Membership).where(Membership.user_id == user_id)))
    if any(m.role == "owner" for m in memberships):
        raise HTTPException(
            status_code=409,
            detail="This user owns a company. Delete the company or have them transfer ownership first.",
        )

    files: list[str] = []
    for membership in memberships:
        # Same as removing a member: their chats go, their uploads stay with the
        # company, credited to its owner.
        files += delete_conversations(session, membership.company_id, user_id)
        owner_id = session.exec(
            select(Membership.user_id).where(
                Membership.company_id == membership.company_id, Membership.role == "owner"
            )
        ).one()
        session.exec(
            update(Document)
            .where(Document.company_id == membership.company_id, Document.uploaded_by == user_id)
            .values(uploaded_by=owner_id)
        )
        session.delete(membership)
    session.exec(delete(Invite).where(Invite.invited_by == user_id))
    session.delete(user)
    session.commit()
    delete_files(files)


def _company_to_read(company: Company, member_count: int) -> InstanceCompanyRead:
    return InstanceCompanyRead(**company.model_dump(), member_count=member_count)


def _company_or_404(session: SessionDep, company_id: uuid.UUID) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


def _member_count(session: SessionDep, company_id: uuid.UUID) -> int:
    return session.exec(
        select(func.count()).select_from(Membership).where(Membership.company_id == company_id)
    ).one()


@router.get("/companies", response_model=list[InstanceCompanyRead])
def list_companies(session: SessionDep, current_user: InstanceAdminDep) -> list[InstanceCompanyRead]:
    companies = session.exec(select(Company).order_by(Company.created_at.desc())).all()
    return [_company_to_read(c, _member_count(session, c.id)) for c in companies]


def _set_status(session: SessionDep, company_id: uuid.UUID, status: str) -> InstanceCompanyRead:
    company = _company_or_404(session, company_id)
    company.status = status
    company.updated_at = datetime.now(timezone.utc)
    session.add(company)
    session.commit()
    session.refresh(company)
    return _company_to_read(company, _member_count(session, company.id))


@router.patch("/companies/{company_id}/suspend", response_model=InstanceCompanyRead)
def suspend_company(
    company_id: uuid.UUID, session: SessionDep, current_user: InstanceAdminDep
) -> InstanceCompanyRead:
    return _set_status(session, company_id, "suspended")


@router.patch("/companies/{company_id}/activate", response_model=InstanceCompanyRead)
def activate_company(
    company_id: uuid.UUID, session: SessionDep, current_user: InstanceAdminDep
) -> InstanceCompanyRead:
    return _set_status(session, company_id, "active")


@router.delete("/companies/{company_id}", status_code=204)
def remove_company(
    company_id: uuid.UUID,
    session: SessionDep,
    current_user: InstanceAdminDep,
    vector_store: VectorStore = Depends(get_vector_store),
) -> None:
    delete_company(session, _company_or_404(session, company_id), vector_store)


@router.get("/stats")
def instance_stats(session: SessionDep, current_user: InstanceAdminDep) -> dict:
    return usage_stats(session)
