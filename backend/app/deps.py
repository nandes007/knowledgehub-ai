from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from jose import JWTError
from sqlmodel import Session, select

from app.db import get_session
from app.models.company import Company
from app.models.membership import Membership
from app.models.user import User
from app.services.auth import decode_access_token

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(session: SessionDep, authorization: str | None = Header(default=None)) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if authorization is None or not authorization.startswith("Bearer "):
        raise unauthorized

    try:
        user_id = decode_access_token(authorization.removeprefix("Bearer "))
    except JWTError as exc:
        raise unauthorized from exc

    user = session.get(User, user_id)
    if user is None:
        raise unauthorized

    if user.approval_status == "pending":
        raise HTTPException(status_code=403, detail="Your account is pending approval")
    if user.approval_status == "rejected":
        raise HTTPException(status_code=403, detail="Your registration has been rejected")
    if user.approval_status != "approved":
        raise HTTPException(status_code=403, detail="Account not approved")

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_instance_admin(current_user: CurrentUserDep) -> User:
    if not current_user.is_instance_admin:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


InstanceAdminDep = Annotated[User, Depends(require_instance_admin)]


@dataclass
class CompanyContext:
    """The caller inside one company. Company-scoped routes get their company from
    here and nowhere else, so none of them can skip the membership check."""

    user: User
    company: Company
    membership: Membership

    @property
    def role(self) -> str:
        return self.membership.role


def get_company_context(slug: str, current_user: CurrentUserDep, session: SessionDep) -> CompanyContext:
    row = session.exec(
        select(Company, Membership)
        .join(Membership, Membership.company_id == Company.id)
        .where(Company.slug == slug, Membership.user_id == current_user.id)
    ).first()
    # Unknown slug and "not a member" look the same, so slugs cannot be probed.
    # Instance admins get no pass: without a membership they are not in the company.
    if row is None:
        raise HTTPException(status_code=404, detail="Company not found")
    company, membership = row
    if company.status != "active":
        raise HTTPException(status_code=403, detail="This company has been suspended")
    return CompanyContext(user=current_user, company=company, membership=membership)


def require_company_role(minimum: str) -> Callable[[CompanyContext], CompanyContext]:
    def _checker(ctx: Annotated[CompanyContext, Depends(get_company_context)]) -> CompanyContext:
        if not ctx.membership.at_least(minimum):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return ctx

    return _checker


MemberDep = Annotated[CompanyContext, Depends(get_company_context)]
AdminDep = Annotated[CompanyContext, Depends(require_company_role("admin"))]
OwnerDep = Annotated[CompanyContext, Depends(require_company_role("owner"))]
