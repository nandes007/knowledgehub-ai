from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from jose import JWTError
from sqlmodel import Session

from app.db import get_session
from app.models.company import Company
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

    if user.company_id:
        company = session.get(Company, user.company_id)
        if company and company.status == "suspended":
            raise HTTPException(status_code=403, detail="Your company has been suspended")
        if company and company.status != "active":
            raise HTTPException(status_code=403, detail="Company is not active")

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_role(*allowed_roles: str) -> Callable[[User], User]:
    def _role_checker(current_user: CurrentUserDep) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions",
            )
        return current_user

    return _role_checker


SuperAdminDep = Annotated[User, Depends(require_role("superadmin"))]
AdminDep = Annotated[User, Depends(require_role("superadmin", "admin"))]
