"""Request correlation ids (N3).

`X-Request-ID` must come back on every response, including the ones the
application never builds itself — 404s, validation errors and 500s.
"""

from __future__ import annotations

import json
import logging
import uuid

import pytest

# Imported at module level, not inside a test: with `from __future__ import
# annotations` every annotation is a string, and FastAPI resolves them against
# module globals. A function-local import leaves `Request` unresolvable, and
# FastAPI silently falls back to treating the parameter as a query field.
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.logging import setup_logging
from app.middleware.request_id import (
    MAX_REQUEST_ID_LENGTH,
    REQUEST_ID_HEADER,
    sanitize_request_id,
)

HEADER = REQUEST_ID_HEADER


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


class TestHeaderIsAlwaysPresent:
    def test_on_a_successful_response(self, client: TestClient) -> None:
        assert client.get("/health").headers.get(HEADER)

    def test_on_a_404(self, client: TestClient) -> None:
        """The router builds this response, not our code."""
        response = client.get("/nope")

        assert response.status_code == 404
        assert response.headers.get(HEADER)

    def test_on_a_405(self, client: TestClient) -> None:
        response = client.post("/health")

        assert response.status_code == 405
        assert response.headers.get(HEADER)

    def test_on_a_500(self, app: FastAPI, tolerant_client: TestClient) -> None:
        """The hardest case, and the one that matters most when debugging.

        Starlette builds this response after the handler raises. A
        BaseHTTPMiddleware implementation would drop the header here.
        """

        @app.get("/boom")
        async def boom() -> None:
            raise RuntimeError("boom")

        response = tolerant_client.get("/boom")

        assert response.status_code == 500
        assert response.headers.get(HEADER)

    def test_a_500_matches_the_error_contract(
        self, app: FastAPI, tolerant_client: TestClient
    ) -> None:
        """CLAUDE.md §10: every error body is `{"detail": string}`.

        Starlette's default 500 is text/plain, so this only holds because of the
        registered exception handler.
        """

        @app.get("/boom-shape")
        async def boom_shape() -> None:
            raise RuntimeError("internal detail that must not leak")

        response = tolerant_client.get("/boom-shape")

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal Server Error"}
        assert "internal detail" not in response.text

    def test_the_500_id_matches_the_one_sent(
        self, app: FastAPI, tolerant_client: TestClient
    ) -> None:
        @app.get("/boom-id")
        async def boom_id() -> None:
            raise RuntimeError("boom")

        response = tolerant_client.get("/boom-id", headers={HEADER: "trace-500"})

        assert response.headers[HEADER] == "trace-500"


class TestEchoAndGenerate:
    def test_a_valid_incoming_id_is_echoed(self, client: TestClient) -> None:
        response = client.get("/health", headers={HEADER: "trace-abc-123"})

        assert response.headers[HEADER] == "trace-abc-123"

    def test_one_is_generated_when_absent(self, client: TestClient) -> None:
        value = client.get("/health").headers[HEADER]

        assert is_uuid(value)

    def test_each_request_gets_its_own(self, client: TestClient) -> None:
        first = client.get("/health").headers[HEADER]
        second = client.get("/health").headers[HEADER]

        assert first != second

    def test_the_header_name_is_case_insensitive(self, client: TestClient) -> None:
        response = client.get("/health", headers={"x-request-id": "lower-case-id"})

        assert response.headers[HEADER] == "lower-case-id"

    def test_it_is_exposed_to_the_browser(self, client: TestClient) -> None:
        """Without expose_headers the frontend can never read it."""
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})

        exposed = response.headers.get("access-control-expose-headers", "")
        assert HEADER.lower() in exposed.lower()


class TestUntrustedInput:
    """The incoming header is attacker-controlled and ends up in every log line."""

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("crlf injection", "abc\r\nX-Injected: evil"),
            ("newline", "abc\ndef"),
            ("null byte", "abc\x00def"),
            ("ansi escape", "abc\x1b[31mred"),
            ("spaces", "has spaces"),
            ("too long", "a" * (MAX_REQUEST_ID_LENGTH + 1)),
            ("empty", ""),
        ],
    )
    def test_a_dangerous_id_is_replaced_not_echoed(
        self, client: TestClient, name: str, value: str
    ) -> None:
        try:
            response = client.get("/health", headers={HEADER: value})
        except Exception:
            # httpx refuses to send some of these, which is also a pass:
            # the value never reaches the server.
            return

        returned = response.headers[HEADER]
        assert returned != value
        assert is_uuid(returned), f"{name} should fall back to a generated id"

    @pytest.mark.parametrize(
        "value",
        [
            "0194fdc2-fa2f-4cc0-81d3-ff12045b73c8",  # uuid
            "01ARZ3NDEKTSV4RRFFQ69G5FAV",  # ulid
            "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",  # w3c trace
            "req_abc.123-XYZ",
            "a" * MAX_REQUEST_ID_LENGTH,  # exactly at the limit
        ],
    )
    def test_realistic_ids_are_accepted(self, client: TestClient, value: str) -> None:
        assert client.get("/health", headers={HEADER: value}).headers[HEADER] == value


class TestSanitize:
    """Unit-level, so the rule is pinned independently of HTTP."""

    @pytest.mark.parametrize("value", ["abc", "a-b_c.d:e", "A1"])
    def test_accepts_valid(self, value: str) -> None:
        assert sanitize_request_id(value) == value

    @pytest.mark.parametrize(
        "value", [None, "", "   ", "a b", "a\nb", "a" * (MAX_REQUEST_ID_LENGTH + 1), "é"]
    )
    def test_rejects_invalid(self, value: str | None) -> None:
        assert sanitize_request_id(value) is None

    def test_trims_surrounding_whitespace(self) -> None:
        assert sanitize_request_id("  abc  ") == "abc"


class TestLoggingIntegration:
    """The whole point of the id: correlating a response with its log lines."""

    def test_the_id_appears_in_logs_for_that_request(
        self, app: FastAPI, client: TestClient, capsys: pytest.CaptureFixture[str]
    ) -> None:
        @app.get("/logs-something")
        async def logs_something() -> dict[str, str]:
            logging.getLogger("clouddesk.test").warning("inside the handler")
            return {"ok": "yes"}

        # The `client` fixture runs before `capsys` activates, so the handler
        # installed during lifespan is bound to the pre-capture stdout. Rebind
        # it now that capture is live — setup_logging rebuilds rather than
        # returning early, which is exactly what makes this possible.
        setup_logging(level="DEBUG")
        capsys.readouterr()  # drop startup noise

        response = client.get("/logs-something", headers={HEADER: "correlate-me"})

        lines = [
            json.loads(line)
            for line in capsys.readouterr().out.strip().splitlines()
            if line.startswith("{")
        ]
        handler_lines = [ln for ln in lines if ln["message"] == "inside the handler"]

        assert handler_lines, "the handler's log line should have been captured"
        assert handler_lines[0]["request_id"] == "correlate-me"
        assert response.headers[HEADER] == "correlate-me"

    def test_the_handler_can_read_it_from_request_state(
        self, app: FastAPI, client: TestClient
    ) -> None:
        @app.get("/echo-state")
        async def echo_state(request: Request) -> dict[str, str]:
            return {"request_id": request.state.request_id}

        response = client.get("/echo-state", headers={HEADER: "from-state"})

        assert response.json() == {"request_id": "from-state"}
        assert response.headers[HEADER] == "from-state"
