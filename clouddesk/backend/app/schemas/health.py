"""Health endpoint payloads. See `docs/API_CONTRACT.md` §3."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """`GET /health`."""

    status: str = "ok"
    version: str
    environment: str


class LivenessResponse(BaseModel):
    """`GET /health/live`. Deliberately holds nothing that needs looking up."""

    status: str = "alive"


class ReadinessResponse(BaseModel):
    """`GET /health/ready`.

    `checks` maps component name to `{"status": ..., "detail": ...}`, where
    detail is present only when there is something to say.
    """

    status: str
    checks: dict[str, dict[str, str]] = Field(default_factory=dict)
