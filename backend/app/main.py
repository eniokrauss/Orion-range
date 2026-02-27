from fastapi import FastAPI

from app.api.routes_blueprints import router as blueprints_router
from app.api.routes_health import router as health_router
from app.api.routes_version import router as version_router
from app.core.config import settings
from app.core.logging import setup_logging
codex/verify-the-structure-m8z187
from app.db.base import Base
from app.db.session import engine
from app.models.blueprint import BlueprintRecord  # noqa: F401
main

setup_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
)

codex/verify-the-structure-m8z187

@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


main
app.include_router(health_router, tags=["health"])
app.include_router(version_router, tags=["meta"])
app.include_router(blueprints_router, tags=["blueprints"])
