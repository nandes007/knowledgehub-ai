from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import select

from app.config import settings
from app.deps import CurrentUserDep, MemberDep, OwnerDep, SessionDep
from app.models.company import Company
from app.models.membership import Membership
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate
from app.services.companies import delete_company, unique_slug
from ingestion.index import VectorStore, get_vector_store

# Account-level: creating a company needs no membership yet.
account_router = APIRouter(tags=["companies"])
# Mounted under /companies/{slug}.
router = APIRouter(tags=["companies"])


def _read(company: Company, role: str) -> CompanyRead:
    return CompanyRead(id=company.id, name=company.name, slug=company.slug, status=company.status, role=role)


def _clean_name(session: SessionDep, name: str, *, exclude: Company | None = None) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Company name cannot be empty")
    existing = session.exec(select(Company).where(Company.name == name)).first()
    if existing is not None and existing != exclude:
        raise HTTPException(status_code=409, detail="Company name already taken")
    return name


@account_router.post("/companies", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, current_user: CurrentUserDep, session: SessionDep) -> CompanyRead:
    name = _clean_name(session, payload.name)

    if settings.max_companies_per_user:
        owned = session.exec(
            select(func.count())
            .select_from(Membership)
            .where(Membership.user_id == current_user.id, Membership.role == "owner")
        ).one()
        if owned >= settings.max_companies_per_user:
            raise HTTPException(
                status_code=403,
                detail=f"Company limit reached: you can own at most {settings.max_companies_per_user} "
                "on this instance.",
            )

    company = Company(name=name, slug=unique_slug(session, name), status="active")
    session.add(company)
    session.flush()
    session.add(Membership(user_id=current_user.id, company_id=company.id, role="owner"))
    session.commit()
    session.refresh(company)
    return _read(company, "owner")


@router.get("", response_model=CompanyRead)
def get_company(ctx: MemberDep) -> CompanyRead:
    return _read(ctx.company, ctx.role)


@router.patch("", response_model=CompanyRead)
def rename_company(payload: CompanyUpdate, ctx: OwnerDep, session: SessionDep) -> CompanyRead:
    # The slug stays: links to the company keep working after a rename.
    ctx.company.name = _clean_name(session, payload.name, exclude=ctx.company)
    ctx.company.updated_at = datetime.now(timezone.utc)
    session.add(ctx.company)
    session.commit()
    session.refresh(ctx.company)
    return _read(ctx.company, ctx.role)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def remove_company(
    ctx: OwnerDep,
    session: SessionDep,
    vector_store: VectorStore = Depends(get_vector_store),
) -> None:
    delete_company(session, ctx.company, vector_store)
