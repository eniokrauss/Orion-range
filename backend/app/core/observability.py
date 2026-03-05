"""
In-process metrics registry for Prometheus scraping.

Tracks:
  HTTP counters   — requests, duration, by status, by path (existing)
  Job counters    — jobs completed by action+status, duration histogram
  Step counters   — steps completed by action+step_key+status
  Reset latency   — histogram of reset operation duration

All operations are thread-safe.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock


class InMemoryMetrics:

    def __init__(self) -> None:
        self._lock = Lock()

        # ── HTTP ──────────────────────────────────────────────────────────────
        self._request_count = 0
        self._request_duration_ms_total = 0.0
        self._by_status: dict[str, int] = defaultdict(int)
        self._by_path: dict[str, int] = defaultdict(int)

        # ── Jobs ──────────────────────────────────────────────────────────────
        # key: (action, status)  → count
        self._job_completions: dict[tuple[str, str], int] = defaultdict(int)
        # key: action → list of duration_seconds floats (for histogram)
        self._job_duration_seconds: dict[str, list[float]] = defaultdict(list)

        # ── Steps ─────────────────────────────────────────────────────────────
        # key: (action, step_key, status) → count
        self._step_completions: dict[tuple[str, str, str], int] = defaultdict(int)

        # ── Reset latency ─────────────────────────────────────────────────────
        self._reset_durations: list[float] = []

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def observe_request(self, *, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._request_count += 1
            self._request_duration_ms_total += duration_ms
            self._by_status[str(status_code)] += 1
            self._by_path[path] += 1

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def observe_job_completed(self, *, action: str, status: str, duration_seconds: float) -> None:
        """Call when a job reaches a terminal state (succeeded or failed)."""
        with self._lock:
            self._job_completions[(action, status)] += 1
            self._job_duration_seconds[action].append(duration_seconds)
            if action == "reset" and status == "succeeded":
                self._reset_durations.append(duration_seconds)

    def observe_step_completed(self, *, action: str, step_key: str, status: str) -> None:
        """Call when a job step reaches a terminal state."""
        with self._lock:
            self._step_completions[(action, step_key, status)] += 1

    # ── Histogram helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _histogram_lines(
        metric_name: str,
        help_text: str,
        label_name: str,
        data: dict[str, list[float]],
        buckets: list[float],
    ) -> list[str]:
        lines = [
            f"# HELP {metric_name} {help_text}",
            f"# TYPE {metric_name} histogram",
        ]
        for label_value, durations in sorted(data.items()):
            count = len(durations)
            total = sum(durations)
            for b in buckets:
                bucket_count = sum(1 for d in durations if d <= b)
                b_str = "+Inf" if b == float("inf") else str(b)
                lines.append(
                    f'{metric_name}_bucket{{{label_name}="{label_value}",le="{b_str}"}} {bucket_count}'
                )
            lines.append(f'{metric_name}_sum{{{label_name}="{label_value}"}} {total:.6f}')
            lines.append(f'{metric_name}_count{{{label_name}="{label_value}"}} {count}')
        return lines

    # ── Prometheus render ─────────────────────────────────────────────────────

    def render_prometheus(self) -> str:
        _JOB_BUCKETS = [1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0, float("inf")]
        _RESET_BUCKETS = [5.0, 15.0, 30.0, 60.0, 120.0, 180.0, float("inf")]

        with self._lock:
            lines: list[str] = []

            # ── HTTP ──────────────────────────────────────────────────────────
            lines += [
                "# HELP orion_http_requests_total Total HTTP requests.",
                "# TYPE orion_http_requests_total counter",
                f"orion_http_requests_total {self._request_count}",
                "# HELP orion_http_request_duration_ms_sum Sum of HTTP request durations in ms.",
                "# TYPE orion_http_request_duration_ms_sum counter",
                f"orion_http_request_duration_ms_sum {self._request_duration_ms_total:.3f}",
                "# HELP orion_http_requests_by_status_total Total HTTP requests by status.",
                "# TYPE orion_http_requests_by_status_total counter",
            ]
            for status_code, count in sorted(self._by_status.items()):
                lines.append(f'orion_http_requests_by_status_total{{status="{status_code}"}} {count}')

            lines += [
                "# HELP orion_http_requests_by_path_total Total HTTP requests by route path.",
                "# TYPE orion_http_requests_by_path_total counter",
            ]
            for path, count in sorted(self._by_path.items()):
                escaped = path.replace('"', r'\"')
                lines.append(f'orion_http_requests_by_path_total{{path="{escaped}"}} {count}')

            # ── Jobs: completion counter ───────────────────────────────────────
            lines += [
                "# HELP orion_jobs_total Total jobs by action and terminal status.",
                "# TYPE orion_jobs_total counter",
            ]
            for (action, status), count in sorted(self._job_completions.items()):
                lines.append(f'orion_jobs_total{{action="{action}",status="{status}"}} {count}')

            # ── Jobs: duration histogram ───────────────────────────────────────
            lines += self._histogram_lines(
                "orion_job_duration_seconds",
                "Job execution duration in seconds by action.",
                "action",
                dict(self._job_duration_seconds),
                _JOB_BUCKETS,
            )

            # ── Steps: completion counter ──────────────────────────────────────
            lines += [
                "# HELP orion_job_steps_total Total job steps by action, step_key and status.",
                "# TYPE orion_job_steps_total counter",
            ]
            for (action, step_key, status), count in sorted(self._step_completions.items()):
                lines.append(
                    f'orion_job_steps_total{{action="{action}",step="{step_key}",status="{status}"}} {count}'
                )

            # ── Reset latency histogram ────────────────────────────────────────
            if self._reset_durations:
                lines += self._histogram_lines(
                    "orion_reset_duration_seconds",
                    "Successful reset (rollback-to-baseline) duration in seconds.",
                    "action",
                    {"reset": list(self._reset_durations)},
                    _RESET_BUCKETS,
                )

        return "\n".join(lines) + "\n"


metrics_registry = InMemoryMetrics()
