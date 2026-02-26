from fastapi import FastAPI
from app.api.routes_health import router as health_router
from app.api.routes_version import router as version_router

app = FastAPI(
    title="Orion Range Core",
    version="0.1.0",
    description="Open-source Cyber Range Orchestrator (Core)",
)

app.include_router(health_router, tags=["health"])
app.include_router(version_router, tags=["meta"])
