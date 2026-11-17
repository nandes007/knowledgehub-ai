import uuid

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.deps import AdminDep, SessionDep
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentRead

# Mounted under /companies/{slug}.
router = APIRouter(prefix="/departments", tags=["departments"])


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    ctx: AdminDep,
    session: SessionDep,
) -> Department:
    dept_name = payload.name.strip()
    if not dept_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Department name cannot be empty",
        )

    existing = session.exec(
        select(Department).where(
            Department.company_id == ctx.company.id,
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
        company_id=ctx.company.id,
    )
    session.add(department)
    session.commit()
    session.refresh(department)

    return department


@router.get("", response_model=list[DepartmentRead])
def list_departments(
    ctx: AdminDep,
    session: SessionDep,
) -> list[Department]:
    statement = (
        select(Department)
        .where(Department.company_id == ctx.company.id)
        .order_by(Department.name.asc())
    )
    departments = session.exec(statement).all()
    return list(departments)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: uuid.UUID,
    ctx: AdminDep,
    session: SessionDep,
) -> None:
    department = session.get(Department, department_id)
    if department is None or department.company_id != ctx.company.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    session.delete(department)
    session.commit()
