from collections import defaultdict
from threading import Lock


class InMemoryMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._request_count = 0
        self._request_duration_ms_total = 0.0
        self._by_status: dict[str, int] = defaultdict(int)
        self._by_path: dict[str, int] = defaultdict(int)

    def observe_request(self, *, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._request_count += 1
            self._request_duration_ms_total += duration_ms
            self._by_status[str(status_code)] += 1
            self._by_path[path] += 1

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP orion_http_requests_total Total HTTP requests.",
                "# TYPE orion_http_requests_total counter",
                f"orion_http_requests_total {self._request_count}",
                "# HELP orion_http_request_duration_ms_sum Sum of HTTP request durations in milliseconds.",
                "# TYPE orion_http_request_duration_ms_sum counter",
                f"orion_http_request_duration_ms_sum {self._request_duration_ms_total:.3f}",
                "# HELP orion_http_requests_by_status_total Total HTTP requests by response status code.",
                "# TYPE orion_http_requests_by_status_total counter",
            ]

            for status_code, count in sorted(self._by_status.items()):
                lines.append(f'orion_http_requests_by_status_total{{status="{status_code}"}} {count}')

            lines.extend(
                [
                    "# HELP orion_http_requests_by_path_total Total HTTP requests by route path.",
                    "# TYPE orion_http_requests_by_path_total counter",
                ]
            )

            for path, count in sorted(self._by_path.items()):
                escaped_path = path.replace('"', r'\"')
                lines.append(f'orion_http_requests_by_path_total{{path="{escaped_path}"}} {count}')

            return "\n".join(lines) + "\n"


metrics_registry = InMemoryMetrics()
