import uuid

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.deps import AdminDep, SessionDep
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentRead

router = APIRouter(prefix="/departments", tags=["departments"])


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    current_user: AdminDep,
    session: SessionDep,
) -> Department:
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin must belong to a company",
        )

    dept_name = payload.name.strip()
    if not dept_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Department name cannot be empty",
        )

    existing = session.exec(
        select(Department).where(
            Department.company_id == current_user.company_id,
            Department.name == dept_name,
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department with this name already exists",
        )

    department = Department(
        name=dept_name,
        company_id=current_user.company_id,
    )
    session.add(department)
    session.commit()
    session.refresh(department)

    return department


@router.get("", response_model=list[DepartmentRead])
def list_departments(
    current_user: AdminDep,
    session: SessionDep,
) -> list[Department]:
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin must belong to a company",
        )

    statement = (
        select(Department)
        .where(Department.company_id == current_user.company_id)
        .order_by(Department.name.asc())
    )
    departments = session.exec(statement).all()
    return list(departments)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: uuid.UUID,
    current_user: AdminDep,
    session: SessionDep,
) -> None:
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin must belong to a company",
        )

    department = session.get(Department, department_id)
    if department is None or department.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    session.delete(department)
    session.commit()
