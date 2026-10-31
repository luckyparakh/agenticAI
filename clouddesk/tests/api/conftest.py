"""Fixtures for the HTTP tests.

Scoped to `tests/api/` on purpose: the project-wide harness (env isolation,
auth headers, a temp database) is P1-3 and will live in `tests/conftest.py`.
Anything here that is still useful then should be hoisted, not duplicated.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.health import clear_readiness_checks
from app.main import create_app


@pytest.fixture(autouse=True)
def _clean_readiness_registry() -> Iterator[None]:
    """The check registry is process-wide; no test may leak one into the next."""
    clear_readiness_checks()
    yield
    clear_readiness_checks()


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # `with` runs lifespan, so startup logging is exercised too.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def tolerant_client(app: FastAPI) -> Iterator[TestClient]:
    """A client that returns the 500 instead of re-raising the exception.

    Needed to assert on what the server actually sends when a handler blows up.
    """
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
