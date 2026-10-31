"""Health and probe routes.

Unprefixed on purpose: container and orchestrator probes call `/health/live`
and `/health/ready` directly, and should not break when the API version prefix
changes (`docs/API_CONTRACT.md` §3).

The three routes answer three different questions:

* `/health`      — what is this, and which environment? For humans.
* `/health/live` — is the process alive? **No I/O.** A liveness probe that
  touches the database restarts the container when the database blips, which
  turns one outage into two.
* `/health/ready`— can it serve traffic? This one may do I/O, and returns 503
  when a component it depends on is down.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app import __version__
from app.core.config import get_settings
from app.core.health import is_ready, run_readiness_checks
from app.schemas.health import HealthResponse, LivenessResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.environment,
    )


@router.get("/health/live", response_model=LivenessResponse)
async def live() -> LivenessResponse:
    """Liveness. Performs no I/O by design — do not add any."""
    return LivenessResponse(status="alive")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def ready(response: Response) -> ReadinessResponse:
    results = await run_readiness_checks()

    if not is_ready(results):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if is_ready(results) else "not_ready",
        checks={name: health.as_dict() for name, health in results.items()},
    )
