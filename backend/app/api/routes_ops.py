from fastapi import APIRouter

from app.services.ops_overview import get_ops_overview

router = APIRouter(prefix="/ops")


@router.get("/overview")
def ops_overview():
    return get_ops_overview()
