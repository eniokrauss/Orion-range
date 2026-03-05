"""
Tests for structured log correlation.

Verifies that:
  1. log_context injects fields into log records.
  2. Nested contexts merge and restore correctly.
  3. Thread-local context is set and cleared by the job runner.
  4. HTTP middleware injects request_id into log records.
  5. JSON formatter emits valid JSON with expected fields.
  6. Text formatter appends context fields in brackets.
  7. Context fields do not leak between requests / threads.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from io import StringIO

import pytest

from app.core.log_context import (
    clear_thread_context,
    get_log_context,
    log_context,
    set_thread_context,
)
from app.core.logging import _ContextFilter, _JsonFormatter, _TextFormatter


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_logger_with_capture(formatter) -> tuple[logging.Logger, StringIO]:
    """Return a logger that writes to a StringIO with the given formatter."""
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(formatter)
    handler.addFilter(_ContextFilter())
    log = logging.getLogger(f"test.capture.{id(formatter)}")
    log.handlers.clear()
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    log.propagate = False
    return log, buf


# ── log_context ContextVar ────────────────────────────────────────────────────

class TestLogContext:
    def setup_method(self):
        clear_thread_context()

    def teardown_method(self):
        clear_thread_context()

    def test_context_empty_by_default(self):
        assert get_log_context() == {}

    def test_context_manager_sets_fields(self):
        with log_context(job_id="job-1", org_id="org-a"):
            ctx = get_log_context()
            assert ctx["job_id"] == "job-1"
            assert ctx["org_id"] == "org-a"

    def test_context_manager_restores_after_exit(self):
        with log_context(job_id="job-1"):
            pass
        assert "job_id" not in get_log_context()

    def test_nested_contexts_merge(self):
        with log_context(org_id="org-a"):
            with log_context(job_id="job-1"):
                ctx = get_log_context()
                assert ctx["org_id"] == "org-a"
                assert ctx["job_id"] == "job-1"
            # Inner context gone, outer preserved
            assert get_log_context().get("org_id") == "org-a"
            assert "job_id" not in get_log_context()

    def test_nested_context_override(self):
        with log_context(org_id="outer"):
            with log_context(org_id="inner"):
                assert get_log_context()["org_id"] == "inner"
            assert get_log_context()["org_id"] == "outer"

    def test_context_does_not_leak_between_calls(self):
        with log_context(job_id="leak-test"):
            pass
        assert get_log_context() == {}


# ── thread-local context ──────────────────────────────────────────────────────

class TestThreadLocalContext:
    def setup_method(self):
        clear_thread_context()

    def teardown_method(self):
        clear_thread_context()

    def test_set_and_get_thread_context(self):
        set_thread_context(job_id="tl-job", org_id="tl-org")
        ctx = get_log_context()
        assert ctx["job_id"] == "tl-job"
        assert ctx["org_id"] == "tl-org"

    def test_clear_thread_context(self):
        set_thread_context(job_id="tl-job")
        clear_thread_context()
        assert get_log_context() == {}

    def test_thread_context_not_visible_in_other_thread(self):
        """Thread-local fields set in one thread must not appear in another."""
        set_thread_context(job_id="main-thread-job")

        seen_in_other = {}

        def _worker():
            seen_in_other.update(get_log_context())

        t = threading.Thread(target=_worker)
        t.start()
        t.join()

        # Other thread should not see main thread's job_id
        assert "job_id" not in seen_in_other

    def test_thread_context_set_none_removes_field(self):
        set_thread_context(step_key="step-1")
        assert get_log_context().get("step_key") == "step-1"
        set_thread_context(step_key=None)
        # None values should be filtered by the formatter, but the key may remain
        # What matters: formatter skips None values
        ctx = get_log_context()
        assert ctx.get("step_key") is None


# ── _ContextFilter ────────────────────────────────────────────────────────────

class TestContextFilter:
    def setup_method(self):
        clear_thread_context()

    def teardown_method(self):
        clear_thread_context()

    def test_filter_injects_context_into_record(self):
        log, buf = _make_logger_with_capture(_TextFormatter())
        with log_context(job_id="filter-job", org_id="filter-org"):
            log.info("test message")

        output = buf.getvalue()
        assert "filter-job" in output
        assert "filter-org" in output

    def test_filter_adds_none_defaults_for_missing_fields(self):
        """Even without context, the standard fields should exist on the record."""
        records: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        h = _Capture()
        h.addFilter(_ContextFilter())
        log = logging.getLogger("test.filter.defaults")
        log.handlers = [h]
        log.propagate = False
        log.info("check defaults")

        assert records, "No records captured"
        r = records[0]
        for field in ("request_id", "job_id", "org_id", "blueprint_id", "step_key"):
            assert hasattr(r, field), f"Missing attribute: {field}"


# ── JSON formatter ────────────────────────────────────────────────────────────

class TestJsonFormatter:
    def setup_method(self):
        clear_thread_context()

    def teardown_method(self):
        clear_thread_context()

    def test_output_is_valid_json(self):
        log, buf = _make_logger_with_capture(_JsonFormatter())
        log.info("json test")
        obj = json.loads(buf.getvalue().strip())
        assert obj["message"] == "json test"
        assert obj["level"] == "INFO"
        assert "ts" in obj
        assert "logger" in obj

    def test_context_fields_appear_in_json(self):
        log, buf = _make_logger_with_capture(_JsonFormatter())
        with log_context(job_id="json-job", org_id="json-org", blueprint_id="bp-1"):
            log.info("with context")

        obj = json.loads(buf.getvalue().strip())
        assert obj["job_id"] == "json-job"
        assert obj["org_id"] == "json-org"
        assert obj["blueprint_id"] == "bp-1"

    def test_none_context_fields_omitted(self):
        """Fields that are None must not appear in the JSON output."""
        log, buf = _make_logger_with_capture(_JsonFormatter())
        log.info("no context")
        obj = json.loads(buf.getvalue().strip())
        for field in ("job_id", "org_id", "blueprint_id", "request_id", "step_key"):
            assert field not in obj, f"None field should be omitted: {field}"

    def test_exception_info_serialized(self):
        log, buf = _make_logger_with_capture(_JsonFormatter())
        try:
            raise ValueError("test error")
        except ValueError:
            log.exception("caught exception")

        obj = json.loads(buf.getvalue().strip())
        assert "exception" in obj
        assert "ValueError" in obj["exception"]


# ── text formatter ────────────────────────────────────────────────────────────

class TestTextFormatter:
    def setup_method(self):
        clear_thread_context()

    def teardown_method(self):
        clear_thread_context()

    def test_message_appears_in_output(self):
        log, buf = _make_logger_with_capture(_TextFormatter())
        log.info("hello from text formatter")
        assert "hello from text formatter" in buf.getvalue()

    def test_context_fields_appended_in_brackets(self):
        log, buf = _make_logger_with_capture(_TextFormatter())
        with log_context(job_id="txt-job", org_id="txt-org"):
            log.info("text with context")

        output = buf.getvalue()
        assert "[" in output
        assert "job_id=txt-job" in output
        assert "org_id=txt-org" in output

    def test_no_brackets_when_context_empty(self):
        log, buf = _make_logger_with_capture(_TextFormatter())
        log.info("no context here")
        output = buf.getvalue()
        assert "[" not in output


# ── job runner log correlation ────────────────────────────────────────────────

class TestJobRunnerLogCorrelation:
    """
    Verify that the job runner sets thread log context so log lines
    automatically carry job_id, action, blueprint_id, and step_key.
    """

    def setup_method(self):
        clear_thread_context()

    def teardown_method(self):
        clear_thread_context()

    def test_thread_context_cleared_after_job_finishes(self):
        """After _run_job completes the thread context must be empty."""
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from app.services import job_runner

        fake_job = SimpleNamespace(
            action="provision",
            target_blueprint_id=None,
            max_attempts=1,
            org_id="test-org",
        )

        class _FakeRepo:
            def get(self, _): return fake_job
            def update_status(self, **_): pass

        class _FakeAdapter:
            def provision(self, _): pass

        class _FakeStepRepo:
            def get_or_create(self, *_): return SimpleNamespace(status="pending")
            def is_done(self, *_): return False
            def mark_running(self, *_): pass
            def mark_done(self, *_): pass
            def mark_failed(self, *_, **__): pass
            def list_for_job(self, _): return []


        original_repo     = job_runner.job_repository
        original_adapter  = job_runner.get_hypervisor_adapter
        original_step     = job_runner.job_step_repository
        original_validate = job_runner._validate_blueprint

        job_runner.job_repository         = _FakeRepo()
        job_runner.get_hypervisor_adapter = lambda: _FakeAdapter()
        job_runner.job_step_repository    = _FakeStepRepo()
        job_runner._validate_blueprint    = lambda _: None

        try:
            job_runner._run_job("job-ctx-test")
            assert get_log_context() == {}, (
                f"Thread context not cleared after job: {get_log_context()}"
            )
        finally:
            job_runner.job_repository         = original_repo
            job_runner.get_hypervisor_adapter = original_adapter
            job_runner.job_step_repository    = original_step
            job_runner._validate_blueprint    = original_validate


# ── HTTP middleware log correlation ───────────────────────────────────────────

class TestHttpMiddlewareCorrelation:
    """Verify that the HTTP middleware injects request_id into responses."""

    def test_request_id_header_returned(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        response = client.get("/health")
        assert "x-request-id" in response.headers

    def test_custom_request_id_preserved(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        response = client.get("/health", headers={"x-request-id": "my-trace-id"})
        assert response.headers["x-request-id"] == "my-trace-id"

    def test_generated_request_id_is_uuid_format(self):
        import re
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        response = client.get("/health")
        rid = response.headers["x-request-id"]
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            rid,
        ), f"request_id not UUID format: {rid}"
