"""
log_context — thread-local structured logging context.

Sets named fields that are automatically injected into every log record
emitted while the context is active. Works correctly in both threaded
and async code because it uses threading.local (synchronous workers)
combined with a ContextVar fallback for async usage.

Usage:
    with log_context(job_id="abc", org_id="default"):
        logger.info("starting step")   # record includes job_id, org_id

    # or as a plain push/pop (job runner, non-context-manager usage):
    token = push_log_context(job_id="abc")
    ...
    pop_log_context(token)
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator

# ContextVar holds a *snapshot* dict for the current async task / thread.
# Each push creates a new dict (copy-on-write) so nested contexts don't
# pollute parent contexts.
_ctx_var: ContextVar[dict[str, Any]] = ContextVar("orion_log_ctx", default={})

# Thread-local shadow for synchronous background threads (job runner).
_thread_local = threading.local()


def _current() -> dict[str, Any]:
    """Return the active log context dict (merges thread-local + ContextVar)."""
    tl = getattr(_thread_local, "ctx", {})
    cv = _ctx_var.get()
    if tl:
        return {**cv, **tl}
    return cv


def get_log_context() -> dict[str, Any]:
    """Return a copy of the current log context fields."""
    return dict(_current())


@contextmanager
def log_context(**fields: Any) -> Generator[None, None, None]:
    """
    Context manager that merges *fields* into the log context for the
    duration of the block, then restores the previous context.
    """
    previous = _ctx_var.get()
    token = _ctx_var.set({**previous, **fields})
    try:
        yield
    finally:
        _ctx_var.reset(token)


def set_thread_context(**fields: Any) -> None:
    """
    Imperatively set log context fields on the current thread.
    Used by the job runner which spawns daemon threads.
    Call clear_thread_context() when the thread's work is done.
    """
    existing = getattr(_thread_local, "ctx", {})
    _thread_local.ctx = {**existing, **fields}


def clear_thread_context() -> None:
    """Clear all thread-local log context fields."""
    _thread_local.ctx = {}
