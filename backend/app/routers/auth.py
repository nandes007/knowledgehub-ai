from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.deps import CurrentUserDep, SessionDep
from app.models.company import Company
from app.models.department import Department
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(payload: RegisterRequest, session: SessionDep) -> RegisterResponse:
    existing_company = session.exec(
        select(Company).where(Company.name == payload.company_name)
    ).first()
    if existing_company is not None:
        raise HTTPException(status_code=409, detail="Company name already taken")

    existing_user = session.exec(select(User).where(User.email == payload.email)).first()
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    company = Company(
        name=payload.company_name,
        status="active",
    )
    session.add(company)
    session.flush()

    user = User(
        company_id=company.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role="admin",
        approval_status="pending",
    )
    session.add(user)
    session.commit()

    return RegisterResponse(message="Registration pending approval")


@router.get("/me", response_model=MeResponse)
def me(current_user: CurrentUserDep, session: SessionDep) -> MeResponse:
    company_name = None
    if current_user.company_id:
        company = session.get(Company, current_user.company_id)
        if company:
            company_name = company.name

    department_name = None
    if current_user.department_id:
        dept = session.get(Department, current_user.department_id)
        if dept:
            department_name = dept.name

    return MeResponse(
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
        approval_status=current_user.approval_status,
        company_id=current_user.company_id,
        company_name=company_name,
        department_id=current_user.department_id,
        department_name=department_name,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.approval_status == "pending":
        raise HTTPException(status_code=403, detail="Your account is pending approval")
    if user.approval_status == "rejected":
        raise HTTPException(status_code=403, detail="Your registration has been rejected")

    if user.company_id:
        company = session.get(Company, user.company_id)
        if company and company.status == "suspended":
            raise HTTPException(status_code=403, detail="Your company has been suspended")

    return TokenResponse(access_token=create_access_token(user.id))
