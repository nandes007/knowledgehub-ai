import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import models  # noqa: F401 - registers tables on SQLModel.metadata
from app.config import settings
from app.logging_config import configure_logging
from app.rate_limit import limiter
from app.deps import get_company_context
from app.routers import (
    auth,
    chat,
    companies,
    conversations,
    departments,
    documents,
    instance,
    invites,
    members,
    stats,
)

_access_logger = logging.getLogger("app.access")

COMPANY_PREFIX = "/companies/{slug}"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    yield


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title="KnowledgeHub AI", lifespan=lifespan)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        _access_logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # Account-level: a signed-in user, no company needed.
    app.include_router(auth.router)
    app.include_router(companies.account_router)
    app.include_router(invites.account_router)

    # Platform: instance admins only.
    app.include_router(instance.router)

    # Everything inside a company. The membership check sits on the router, so a
    # route added here is tenant-scoped before it does anything else.
    for module in (companies, members, invites, departments, documents, chat, conversations, stats):
        app.include_router(
            module.router, prefix=COMPANY_PREFIX, dependencies=[Depends(get_company_context)]
        )

    return app


app = create_app()
