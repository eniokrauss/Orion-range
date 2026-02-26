from fastapi import APIRouter

router = APIRouter()

@router.get("/version")
def version():
    return {"name": "orion-range-core", "version": "0.1.0"}
