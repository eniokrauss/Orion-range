from fastapi import Depends, FastAPI

from app.api.routes_blueprints import router as blueprints_router
from app.api.routes_health import router as health_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_mitre import router as mitre_router
from app.api.routes_ops import router as ops_router
from app.api.routes_scenarios import router as scenarios_router
from app.api.routes_version import router as version_router
from app.core.auth import require_api_key
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.session import engine
from app.models.baseline import BaselineRecord  # noqa: F401
from app.models.blueprint import BlueprintRecord  # noqa: F401
from app.models.job import JobRecord  # noqa: F401
from app.models.scenario_run import ScenarioRunRecord  # noqa: F401

setup_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
)


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(health_router, tags=["health"])
app.include_router(version_router, tags=["meta"])
app.include_router(blueprints_router, tags=["blueprints"], dependencies=[Depends(require_api_key)])
app.include_router(jobs_router, tags=["jobs"], dependencies=[Depends(require_api_key)])
app.include_router(scenarios_router, tags=["scenarios"], dependencies=[Depends(require_api_key)])
app.include_router(mitre_router, tags=["mitre"], dependencies=[Depends(require_api_key)])
app.include_router(ops_router, tags=["ops"], dependencies=[Depends(require_api_key)])
