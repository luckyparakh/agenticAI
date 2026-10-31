"""Readiness checks.

`/health/ready` reports on the four components CLAUDE.md §10 names: database,
redis, vector store and LLM provider. None of them exist yet, so this module is
a **registry** rather than a set of checks: each component registers its own
check when its phase lands, and until then it reports `not_configured`.

That is deliberate. Reporting `ok` for a database that has not been written
would be a lie told by a health endpoint, which is the worst place to tell one.

Registering a check (from the component's own module, at import or startup):

    register_readiness_check("database", _ping_database)

Two guarantees this module makes, both because a readiness probe is called by an
orchestrator that will kill the container if it misbehaves:

* A check that raises is reported as `unavailable`, never propagated.
* A check that hangs is cut off at `READINESS_TIMEOUT_SECONDS`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

ReadinessStatus = Literal["ok", "degraded", "unavailable", "not_configured"]

# A probe that hangs is worse than one that fails: the orchestrator waits.
READINESS_TIMEOUT_SECONDS = 2.0

# Reported on every call even when nothing has registered them (CLAUDE.md §10).
REQUIRED_COMPONENTS: tuple[str, ...] = ("database", "redis", "vector_store", "llm")


@dataclass(frozen=True)
class ComponentHealth:
    """One component's answer to "can you serve traffic?"."""

    status: ReadinessStatus
    detail: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = {"status": self.status}
        if self.detail:
            payload["detail"] = self.detail
        return payload


CheckFn = Callable[[], Awaitable[ComponentHealth]]

_checks: dict[str, CheckFn] = {}


def register_readiness_check(name: str, check: CheckFn) -> None:
    """Register (or replace) the check for one component."""
    _checks[name] = check


def unregister_readiness_check(name: str) -> None:
    _checks.pop(name, None)


def clear_readiness_checks() -> None:
    """Drop every registered check. For tests."""
    _checks.clear()


def registered_check_names() -> tuple[str, ...]:
    return tuple(_checks)


async def _run_one(name: str, check: CheckFn) -> ComponentHealth:
    try:
        return await asyncio.wait_for(check(), timeout=READINESS_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning("readiness check timed out", extra={"component": name})
        return ComponentHealth("unavailable", f"timed out after {READINESS_TIMEOUT_SECONDS:g}s")
    except Exception as exc:  # noqa: BLE001 - a probe must never raise
        logger.warning(
            "readiness check failed",
            extra={"component": name, "error": type(exc).__name__},
        )
        return ComponentHealth("unavailable", type(exc).__name__)


async def run_readiness_checks() -> dict[str, ComponentHealth]:
    """Run every check concurrently and return one entry per component."""
    names = list(REQUIRED_COMPONENTS)
    names += [name for name in _checks if name not in REQUIRED_COMPONENTS]

    registered = [name for name in names if name in _checks]
    results = await asyncio.gather(*(_run_one(name, _checks[name]) for name in registered))
    by_name = dict(zip(registered, results, strict=True))

    return {
        name: by_name.get(name, ComponentHealth("not_configured", "not wired up yet"))
        for name in names
    }


def is_ready(results: dict[str, ComponentHealth]) -> bool:
    """Ready unless something that exists is broken.

    `not_configured` does not block readiness — the component is not part of the
    application yet, so the app can serve what it does have. `degraded` does not
    block either: a slow cache should not take the service out of rotation.
    """
    return not any(health.status == "unavailable" for health in results.values())
