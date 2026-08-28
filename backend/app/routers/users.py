import uuid

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.deps import AdminDep, SessionDep
from app.models.department import Department
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.auth import hash_password

router = APIRouter(prefix="/users", tags=["users"])


def _user_to_read(user: User, session: SessionDep) -> UserRead:
    department_name = None
    if user.department_id:
        dept = session.get(Department, user.department_id)
        if dept:
            department_name = dept.name
    return UserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        approval_status=user.approval_status,
        company_id=user.company_id,
        department_id=user.department_id,
        department_name=department_name,
        created_at=user.created_at,
    )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_user: AdminDep,
    session: SessionDep,
) -> UserRead:
    if current_user.company_id is None and current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin must belong to a company",
        )

    if current_user.role == "admin" and payload.role != "member":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company admins can only create employee users",
        )

    dept = session.get(Department, payload.department_id)
    if dept is None or (current_user.company_id and dept.company_id != current_user.company_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    company_id = current_user.company_id if current_user.company_id else dept.company_id

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        approval_status="approved",
        company_id=company_id,
        department_id=payload.department_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return _user_to_read(user, session)


@router.get("", response_model=list[UserRead])
def list_users(
    current_user: AdminDep,
    session: SessionDep,
) -> list[UserRead]:
    if current_user.company_id is None and current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin must belong to a company",
        )

    statement = select(User)
    if current_user.company_id is not None:
        statement = statement.where(User.company_id == current_user.company_id)
    statement = statement.order_by(User.created_at.desc())

    users = session.exec(statement).all()
    return [_user_to_read(u, session) for u in users]


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    current_user: AdminDep,
    session: SessionDep,
) -> UserRead:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if current_user.role == "admin":
        if current_user.company_id is None or user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if user.role != "member":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admins can only manage employee users",
            )
        if payload.role is not None and payload.role != "member":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admins cannot assign admin role",
            )

    if payload.department_id is not None:
        dept = session.get(Department, payload.department_id)
        if dept is None or (user.company_id is not None and dept.company_id != user.company_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found",
            )
        user.department_id = payload.department_id

    if payload.display_name is not None:
        user.display_name = payload.display_name

    if payload.role is not None:
        user.role = payload.role

    session.add(user)
    session.commit()
    session.refresh(user)

    return _user_to_read(user, session)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    current_user: AdminDep,
    session: SessionDep,
) -> None:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete own account",
        )

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if current_user.role == "admin":
        if current_user.company_id is None or user.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if user.role != "member":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company admins can only delete employee users",
            )

    session.delete(user)
    session.commit()
