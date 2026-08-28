from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from app.deps import SessionDep, SuperAdminDep
from app.models.company import Company
from app.models.user import User
from app.schemas.superadmin import SuperadminCompanyRead, SuperadminUserRead

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


def _user_to_read(user: User, session: SessionDep) -> SuperadminUserRead:
    company_name = None
    if user.company_id:
        company = session.get(Company, user.company_id)
        if company:
            company_name = company.name
    return SuperadminUserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        approval_status=user.approval_status,
        company_id=user.company_id,
        company_name=company_name,
        department_id=user.department_id,
        created_at=user.created_at,
    )


@router.get("/users", response_model=list[SuperadminUserRead])
def list_users(
    session: SessionDep,
    current_user: SuperAdminDep,
    approval_status: str | None = Query(default=None),
) -> list[SuperadminUserRead]:
    statement = select(User)
    if approval_status is not None:
        statement = statement.where(User.approval_status == approval_status)
    statement = statement.order_by(User.created_at.desc())

    users = session.exec(statement).all()
    return [_user_to_read(u, session) for u in users]


@router.patch("/users/{user_id}/approve", response_model=SuperadminUserRead)
def approve_user(
    user_id: uuid.UUID,
    session: SessionDep,
    current_user: SuperAdminDep,
) -> SuperadminUserRead:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.approval_status = "approved"
    session.add(user)
    session.commit()
    session.refresh(user)

    return _user_to_read(user, session)


@router.patch("/users/{user_id}/reject", response_model=SuperadminUserRead)
def reject_user(
    user_id: uuid.UUID,
    session: SessionDep,
    current_user: SuperAdminDep,
) -> SuperadminUserRead:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.approval_status = "rejected"
    session.add(user)
    session.commit()
    session.refresh(user)

    return _user_to_read(user, session)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: uuid.UUID,
    session: SessionDep,
    current_user: SuperAdminDep,
) -> None:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete own account",
        )
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(user)
    session.commit()


@router.get("/companies", response_model=list[SuperadminCompanyRead])
def list_companies(
    session: SessionDep,
    current_user: SuperAdminDep,
) -> list[Company]:
    statement = select(Company).order_by(Company.created_at.desc())
    return list(session.exec(statement).all())


@router.patch("/companies/{company_id}/suspend", response_model=SuperadminCompanyRead)
def suspend_company(
    company_id: uuid.UUID,
    session: SessionDep,
    current_user: SuperAdminDep,
) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    company.status = "suspended"
    company.updated_at = datetime.now(timezone.utc)
    session.add(company)
    session.commit()
    session.refresh(company)

    return company


@router.patch("/companies/{company_id}/activate", response_model=SuperadminCompanyRead)
def activate_company(
    company_id: uuid.UUID,
    session: SessionDep,
    current_user: SuperAdminDep,
) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    company.status = "active"
    company.updated_at = datetime.now(timezone.utc)
    session.add(company)
    session.commit()
    session.refresh(company)

    return company
