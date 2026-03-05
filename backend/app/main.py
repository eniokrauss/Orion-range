"""
Orion Range Core — FastAPI application entry point.

HTTP middleware responsibilities:
  1. Attach / generate x-request-id for every request.
  2. Push request_id + org_id into the log context so every log line
     emitted during that request automatically carries those fields.
  3. Record Prometheus metrics.

Startup:
  - Create all DB tables via SQLAlchemy metadata.
  - Start the periodic GC background thread (if GC_INTERVAL_SECONDS > 0).
"""

from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, Request

from app.api.routes_auth import router as auth_router
from app.api.routes_blueprints import router as blueprints_router
from app.api.routes_health import router as health_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_mitre import router as mitre_router
from app.api.routes_ops import router as ops_router
from app.api.routes_scenarios import router as scenarios_router
from app.api.routes_version import router as version_router
from app.core.auth import require_api_key
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.observability import metrics_registry
from app.db.base import Base
from app.db.session import engine
from app.models.baseline import BaselineRecord        # noqa: F401
from app.models.blueprint import BlueprintRecord      # noqa: F401
from app.models.job import JobRecord                  # noqa: F401
from app.models.job_step import JobStepRecord         # noqa: F401
from app.models.revoked_token import RevokedTokenRecord # noqa: F401
from app.models.scenario_run import ScenarioRunRecord # noqa: F401
from app.models.user_token_state import UserTokenStateRecord # noqa: F401
from app.models.user import UserRecord                # noqa: F401

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ───────────────────────────────────────────────────────────────
    Base.metadata.create_all(bind=engine)

    from app.services.gc import start_periodic_gc
    start_periodic_gc(settings.gc_interval_seconds)

    yield
    # ── shutdown ──────────────────────────────────────────────────────────────
    from app.services.gc import stop_periodic_gc
    stop_periodic_gc()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    lifespan=lifespan,
)


@asynccontextmanager
async def _async_log_context(**fields):
    from app.core.log_context import log_context as _lc
    with _lc(**fields):
        yield


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    start = perf_counter()

    org_id: str | None = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from app.core.security import decode_token
            payload = decode_token(auth_header[7:], expected_type="access")
            org_id = payload.org_id
        except Exception:
            pass

    ctx_fields: dict = {"request_id": request_id}
    if org_id:
        ctx_fields["org_id"] = org_id

    async with _async_log_context(**ctx_fields):
        response = await call_next(request)

    duration_ms = (perf_counter() - start) * 1000
    metrics_registry.observe_request(
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    response.headers["x-request-id"] = request_id
    return response


# Public routes
app.include_router(health_router,   tags=["health"])
app.include_router(version_router,  tags=["meta"])
app.include_router(metrics_router,  tags=["meta"])
app.include_router(auth_router,     tags=["auth"])

# Protected routes
app.include_router(blueprints_router, tags=["blueprints"], dependencies=[Depends(require_api_key)])
app.include_router(jobs_router,       tags=["jobs"],       dependencies=[Depends(require_api_key)])
app.include_router(scenarios_router,  tags=["scenarios"],  dependencies=[Depends(require_api_key)])
app.include_router(mitre_router,      tags=["mitre"],      dependencies=[Depends(require_api_key)])
app.include_router(ops_router,        tags=["ops"],        dependencies=[Depends(require_api_key)])
