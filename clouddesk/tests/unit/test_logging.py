"""JSON logging: one parseable object per line, always carrying the correlation ids."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import pytest
from app.core.logging import (
    JsonFormatter,
    bind_request_id,
    bind_workflow_id,
    clear_context,
    get_request_id,
    get_workflow_id,
    setup_logging,
    workflow_context,
)


@pytest.fixture(autouse=True)
def _isolate_logging():
    """Give every test a clean root logger and empty correlation ids."""
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    clear_context()
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)
    clear_context()


def emit(capsys: pytest.CaptureFixture[str], **kwargs: Any) -> dict[str, Any]:
    """Log one record through the real handler and return the parsed JSON."""
    setup_logging(level="DEBUG")
    logging.getLogger("clouddesk.test").info("hello", **kwargs)
    line = capsys.readouterr().out.strip()
    return json.loads(line)


class TestFormat:
    def test_output_is_one_json_object(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(level="DEBUG")
        logging.getLogger("clouddesk.test").info("hello")

        out = capsys.readouterr().out
        assert out.count("\n") == 1, "a record must not span lines"
        json.loads(out)  # must not raise

    def test_carries_the_expected_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        record = emit(capsys)

        assert record["message"] == "hello"
        assert record["level"] == "INFO"
        assert record["logger"] == "clouddesk.test"
        assert record["timestamp"].endswith("+00:00"), "timestamps are UTC"

    def test_request_and_workflow_ids_are_always_present(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        record = emit(capsys)

        # Present but null, so a log pipeline can rely on the key existing.
        assert record["request_id"] is None
        assert record["workflow_id"] is None

    def test_percent_style_arguments_are_rendered(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(level="DEBUG")
        logging.getLogger("clouddesk.test").info("ticket %s took %d ms", "CD-1002", 42)

        record = json.loads(capsys.readouterr().out)
        assert record["message"] == "ticket CD-1002 took 42 ms"

    def test_extra_fields_are_included(self, capsys: pytest.CaptureFixture[str]) -> None:
        record = emit(capsys, extra={"ticket_id": "CD-1002", "node": "risk_check"})

        assert record["ticket_id"] == "CD-1002"
        assert record["node"] == "risk_check"

    def test_unserialisable_extra_does_not_break_the_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        record = emit(capsys, extra={"obj": object()})
        assert "obj" in record  # coerced by default=str rather than raising

    def test_exceptions_are_captured(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(level="DEBUG")
        try:
            raise ValueError("boom")
        except ValueError:
            logging.getLogger("clouddesk.test").exception("failed")

        record = json.loads(capsys.readouterr().out)
        assert record["level"] == "ERROR"
        assert "ValueError: boom" in record["exception"]

    def test_formatter_is_usable_standalone(self) -> None:
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="x",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="standalone",
            args=(),
            exc_info=None,
        )
        assert json.loads(formatter.format(record))["message"] == "standalone"


class TestCorrelationIds:
    def test_bound_ids_appear_on_the_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        bind_request_id("req-1")
        bind_workflow_id("wf-1")

        record = emit(capsys)

        assert record["request_id"] == "req-1"
        assert record["workflow_id"] == "wf-1"

    def test_bind_request_id_generates_one_when_absent(self) -> None:
        generated = bind_request_id()

        assert generated
        assert get_request_id() == generated

    def test_bind_request_id_returns_what_it_set(self) -> None:
        assert bind_request_id("req-explicit") == "req-explicit"
        assert get_request_id() == "req-explicit"

    def test_workflow_context_restores_the_previous_value(self) -> None:
        bind_workflow_id("outer")

        with workflow_context("inner"):
            assert get_workflow_id() == "inner"

        assert get_workflow_id() == "outer"

    def test_workflow_context_restores_after_an_exception(self) -> None:
        bind_workflow_id("outer")

        with pytest.raises(RuntimeError), workflow_context("inner"):
            raise RuntimeError("boom")

        assert get_workflow_id() == "outer"

    def test_clear_context_resets_both(self) -> None:
        bind_request_id("req-1")
        bind_workflow_id("wf-1")

        clear_context()

        assert get_request_id() is None
        assert get_workflow_id() is None

    async def test_ids_do_not_leak_between_concurrent_tasks(self) -> None:
        """The reason these are ContextVars: two runs must not see each other's id."""
        seen: dict[str, str | None] = {}

        async def run(workflow_id: str) -> None:
            bind_workflow_id(workflow_id)
            await asyncio.sleep(0)  # force interleaving
            seen[workflow_id] = get_workflow_id()

        await asyncio.gather(
            asyncio.create_task(run("wf-a")),
            asyncio.create_task(run("wf-b")),
        )

        assert seen == {"wf-a": "wf-a", "wf-b": "wf-b"}


class TestSetup:
    def test_is_idempotent(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(level="DEBUG")
        setup_logging(level="DEBUG")
        setup_logging(level="DEBUG")

        logging.getLogger("clouddesk.test").info("once")

        lines = capsys.readouterr().out.strip().splitlines()
        assert len(lines) == 1, "repeated setup must not duplicate handlers"

    def test_replaces_a_pre_existing_handler(self, capsys: pytest.CaptureFixture[str]) -> None:
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())

        setup_logging(level="DEBUG")
        logging.getLogger("clouddesk.test").info("once")

        lines = capsys.readouterr().out.strip().splitlines()
        assert len(lines) == 1
        json.loads(lines[0])

    def test_level_is_applied(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(level="WARNING")
        logging.getLogger("clouddesk.test").info("suppressed")
        logging.getLogger("clouddesk.test").warning("kept")

        lines = capsys.readouterr().out.strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["message"] == "kept"

    def test_repeat_setup_updates_the_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        setup_logging(level="WARNING")
        setup_logging(level="DEBUG")

        logging.getLogger("clouddesk.test").debug("now visible")
        assert json.loads(capsys.readouterr().out)["message"] == "now visible"

    def test_level_defaults_to_settings(self, capsys: pytest.CaptureFixture[str]) -> None:
        from app.core.config import get_settings

        get_settings.cache_clear()
        setup_logging()  # no explicit level
        logging.getLogger("clouddesk.test").debug("demo mode is debug")

        assert capsys.readouterr().out.strip(), "DEMO_MODE defaults to DEBUG"
        get_settings.cache_clear()

    def test_uvicorn_loggers_are_routed_through_the_formatter(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        uvicorn = logging.getLogger("uvicorn.error")
        uvicorn.addHandler(logging.StreamHandler())

        setup_logging(level="DEBUG")
        uvicorn.info("started")

        lines = capsys.readouterr().out.strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["logger"] == "uvicorn.error"
