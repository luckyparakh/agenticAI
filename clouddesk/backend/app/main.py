"""FastAPI application factory and startup.

Run it with `uvicorn app.main:app --reload` from `backend/`, or `make backend`
once the Makefile lands (P1-4).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health
from app.core.config import Settings, get_settings
from app.core.logging import get_logger, get_request_id, setup_logging
from app.middleware import REQUEST_ID_HEADER, RequestIdMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown.

    Later phases add `create_tables()` and `bootstrap_demo_data()` here
    (CLAUDE.md §10).
    """
    settings = get_settings()
    setup_logging()

    logger.info(
        "clouddesk starting",
        extra={
            "version": __version__,
            "environment": settings.environment,
            "demo_mode": settings.demo_mode,
            "llm_provider": settings.llm_provider,
            "vector_store": settings.vector_store,
        },
    )

    yield

    logger.info("clouddesk stopped")


def _add_middleware(app: FastAPI, settings: Settings) -> None:
    """Install middleware in the order CLAUDE.md §9 requires.

    The request-order chain is:

        CORS → RequestId → RateLimit → Audit → route

    Starlette wraps each `add_middleware` call *around* what is already there,
    so **the last one added is the outermost**. The calls below therefore run in
    reverse of the chain above. Adding a new middleware in the wrong position is
    silent — nothing errors, you just get a different order — so add new ones
    with this comment in view.

    RateLimit (P3-3) and Audit (P3-4) slot in between, added *before* the two
    here.
    """
    app.add_middleware(RequestIdMiddleware)

    origins = settings.cors_origin_list
    # A browser rejects `Access-Control-Allow-Origin: *` together with
    # credentials, so a wildcard origin list has to drop credentials.
    wildcard = "*" in origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=not wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
        # Without this the browser can read the response but not the header,
        # so the id never reaches the frontend's error reports (N3).
        expose_headers=[REQUEST_ID_HEADER],
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Turn an unhandled exception into the contract's error shape.

    This exists because of where Starlette puts `ServerErrorMiddleware`: it is
    the outermost layer, *outside* every user middleware, so the 500 it builds
    by itself never passes through `RequestIdMiddleware`'s `send` wrapper. Left
    alone it returns `text/plain` with no `X-Request-ID` — breaking both the
    `{"detail": ...}` shape (CLAUDE.md §10) and N3, on the one response where a
    correlation id is worth the most.

    Registering a handler for `Exception` hands it to `ServerErrorMiddleware`,
    which calls this to build the response and then re-raises so the server
    still logs the traceback. The id is read from the ContextVar rather than the
    request, because it is still set: the middleware chain runs in one task, so
    the value survives back up the stack.

    The client is told nothing about the exception. Internal detail goes to the
    log, where the request id ties it back to this response.
    """
    logger.exception(
        "unhandled exception",
        extra={"path": request.url.path, "method": request.method},
    )

    request_id = get_request_id()
    headers = {REQUEST_ID_HEADER: request_id} if request_id else None

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
        headers=headers,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. A factory so tests can build isolated instances."""
    settings = settings or get_settings()

    app = FastAPI(
        title="CloudDesk Support API",
        version=__version__,
        description="Autonomous Customer Support & Resolution Platform",
        lifespan=lifespan,
    )

    _add_middleware(app, settings)

    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Unprefixed: probes call these directly (docs/API_CONTRACT.md §3).
    app.include_router(health.router)

    # Routers under /api/v1 are added from Phase 4 onward.

    return app


app = create_app()
