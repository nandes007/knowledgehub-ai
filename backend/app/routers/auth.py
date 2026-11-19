from fastapi import APIRouter, HTTPException
from sqlalchemy import func
from sqlmodel import select

from app.config import settings
from app.deps import CurrentUserDep, SessionDep
from app.models.company import Company
from app.models.department import Department
from app.models.membership import Membership
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    MyCompany,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services import invites
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(payload: RegisterRequest, session: SessionDep) -> RegisterResponse:
    """Creates an account only. A company comes afterwards: create one, or join by invite."""
    invite = None
    if payload.invite_token:
        invite = invites.find_pending(session, payload.invite_token)
        if invite is None:
            raise HTTPException(status_code=404, detail="This invite link is invalid or has expired")
        if not invites.is_for(invite, payload.email):
            raise HTTPException(status_code=403, detail="This invite was sent to a different email address")
    elif settings.signup_mode == "closed":
        raise HTTPException(status_code=403, detail="Signup is closed. Ask a company admin for an invite link.")

    if session.exec(select(User).where(func.lower(User.email) == payload.email.strip().lower())).first() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    # An invite vouches for the account, so it skips approval.
    pending = invite is None and settings.signup_mode == "approval"
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        approval_status="pending" if pending else "approved",
    )
    session.add(user)
    session.flush()

    company_slug = None
    if invite is not None:
        invites.accept(session, invite, user)
        company_slug = session.get(Company, invite.company_id).slug
    session.commit()

    return RegisterResponse(
        message="Registration pending approval" if pending else "Account created",
        approval_status=user.approval_status,
        company_slug=company_slug,
    )


@router.get("/me", response_model=MeResponse)
def me(current_user: CurrentUserDep, session: SessionDep) -> MeResponse:
    rows = session.exec(
        select(Company, Membership, Department)
        .join(Membership, Membership.company_id == Company.id)
        .join(Department, Department.id == Membership.department_id, isouter=True)
        .where(Membership.user_id == current_user.id)
        .order_by(Company.name)
    ).all()
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        is_instance_admin=current_user.is_instance_admin,
        approval_status=current_user.approval_status,
        companies=[
            MyCompany(
                id=company.id,
                name=company.name,
                slug=company.slug,
                status=company.status,
                role=membership.role,
                department_id=membership.department_id,
                department_name=department.name if department else None,
            )
            for company, membership, department in rows
        ],
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    user = session.exec(select(User).where(func.lower(User.email) == payload.email.strip().lower())).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.approval_status == "pending":
        raise HTTPException(status_code=403, detail="Your account is pending approval")
    if user.approval_status == "rejected":
        raise HTTPException(status_code=403, detail="Your registration has been rejected")

    return TokenResponse(access_token=create_access_token(user.id))
