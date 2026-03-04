from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/version")
def version():
    return {
        "name": "orion-range-core",
        "version": settings.app_version,
        "environment": settings.orion_env,
    }
