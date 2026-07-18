from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401 - registers tables on SQLModel.metadata
from app.db import create_db_and_tables
from app.routers.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    create_db_and_tables()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="KnowledgeHub AI", lifespan=lifespan)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(chat_router)

    return app


app = create_app()
