from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app import models  # noqa: F401 - registers tables on SQLModel.metadata
from app.config import settings
from app.db import create_db_and_tables, engine
from app.routers.chat import router as chat_router
from app.routers.conversations import router as conversations_router
from app.routers.documents import router as documents_router
from app.seed import ensure_seed_user


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    create_db_and_tables()
    with Session(engine) as session:
        ensure_seed_user(session)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="KnowledgeHub AI", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(chat_router)
    app.include_router(conversations_router)
    app.include_router(documents_router)

    return app


app = create_app()
