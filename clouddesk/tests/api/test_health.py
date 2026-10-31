"""Health routes, against `docs/API_CONTRACT.md` §3."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.core.health import (
    REQUIRED_COMPONENTS,
    ComponentHealth,
    is_ready,
    register_readiness_check,
    run_readiness_checks,
)


def check_returning(status: str, detail: str | None = None):
    async def _check() -> ComponentHealth:
        return ComponentHealth(status, detail)  # type: ignore[arg-type]

    return _check


class TestHealth:
    def test_returns_the_contract_shape(self, client: TestClient) -> None:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "version": __version__,
            "environment": "development",
        }

    def test_is_unprefixed(self, client: TestClient) -> None:
        """Probes call /health, not /api/v1/health."""
        assert client.get("/api/v1/health").status_code == 404


class TestLiveness:
    def test_returns_alive(self, client: TestClient) -> None:
        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_performs_no_io(self, client: TestClient) -> None:
        """The contract says no I/O. Prove it: a registered check must not run.

        A liveness probe that touches a dependency restarts the container when
        that dependency blips, turning one outage into two.
        """
        called = False

        async def _tripwire() -> ComponentHealth:
            nonlocal called
            called = True
            return ComponentHealth("ok")

        register_readiness_check("database", _tripwire)

        assert client.get("/health/live").status_code == 200
        assert called is False, "/health/live must not run readiness checks"

    def test_survives_a_broken_dependency(self, client: TestClient) -> None:
        """Liveness stays 200 even when a dependency is down — that is the point."""
        register_readiness_check("database", check_returning("unavailable", "down"))

        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503


class TestReadiness:
    def test_reports_every_required_component(self, client: TestClient) -> None:
        body = client.get("/health/ready").json()

        assert set(REQUIRED_COMPONENTS) <= set(body["checks"])

    def test_unwired_components_are_not_configured_not_ok(self, client: TestClient) -> None:
        """Nothing is wired yet, and the endpoint must not pretend otherwise."""
        body = client.get("/health/ready").json()

        for component in REQUIRED_COMPONENTS:
            assert body["checks"][component]["status"] == "not_configured"

    def test_ready_while_nothing_is_wired(self, client: TestClient) -> None:
        response = client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_ok_component_is_reported_ok(self, client: TestClient) -> None:
        register_readiness_check("database", check_returning("ok"))

        body = client.get("/health/ready").json()

        assert body["checks"]["database"] == {"status": "ok"}
        assert body["status"] == "ready"

    def test_detail_is_included_when_present(self, client: TestClient) -> None:
        register_readiness_check("redis", check_returning("degraded", "slow"))

        body = client.get("/health/ready").json()

        assert body["checks"]["redis"] == {"status": "degraded", "detail": "slow"}

    def test_unavailable_component_returns_503(self, client: TestClient) -> None:
        register_readiness_check("database", check_returning("unavailable", "refused"))

        response = client.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    def test_degraded_does_not_take_the_service_out_of_rotation(self, client: TestClient) -> None:
        register_readiness_check("redis", check_returning("degraded", "slow"))

        assert client.get("/health/ready").status_code == 200

    def test_extra_components_are_reported(self, client: TestClient) -> None:
        register_readiness_check("qdrant_cloud", check_returning("ok"))

        body = client.get("/health/ready").json()

        assert body["checks"]["qdrant_cloud"]["status"] == "ok"


class TestReadinessIsolation:
    """A probe is called by something that kills the container. It must not misbehave."""

    async def test_a_raising_check_becomes_unavailable(self) -> None:
        async def _explodes() -> ComponentHealth:
            raise ConnectionRefusedError("nope")

        register_readiness_check("database", _explodes)

        results = await run_readiness_checks()

        assert results["database"].status == "unavailable"
        assert results["database"].detail == "ConnectionRefusedError"

    async def test_a_raising_check_does_not_reach_the_client(self, client: TestClient) -> None:
        async def _explodes() -> ComponentHealth:
            raise RuntimeError("boom")

        register_readiness_check("llm", _explodes)

        response = client.get("/health/ready")

        assert response.status_code == 503  # not a 500
        assert response.json()["checks"]["llm"]["status"] == "unavailable"

    async def test_a_hanging_check_times_out(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.core.health.READINESS_TIMEOUT_SECONDS", 0.01)

        async def _hangs() -> ComponentHealth:
            await asyncio.sleep(10)
            return ComponentHealth("ok")

        register_readiness_check("redis", _hangs)

        results = await run_readiness_checks()

        assert results["redis"].status == "unavailable"
        assert "timed out" in (results["redis"].detail or "")

    async def test_one_broken_check_does_not_hide_the_others(self) -> None:
        async def _explodes() -> ComponentHealth:
            raise RuntimeError("boom")

        register_readiness_check("database", _explodes)
        register_readiness_check("redis", check_returning("ok"))

        results = await run_readiness_checks()

        assert results["database"].status == "unavailable"
        assert results["redis"].status == "ok"


class TestIsReady:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [("ok", True), ("degraded", True), ("not_configured", True), ("unavailable", False)],
    )
    def test_only_unavailable_blocks_readiness(self, status: str, expected: bool) -> None:
        results = {"database": ComponentHealth(status)}  # type: ignore[arg-type]
        assert is_ready(results) is expected

    def test_empty_results_are_ready(self) -> None:
        assert is_ready({}) is True
