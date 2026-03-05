from fastapi import APIRouter

from app.services.mitre_plugins.registry import mitre_plugin_registry

router = APIRouter(prefix="/mitre")


@router.get("/techniques")
def list_techniques():
    return {"items": mitre_plugin_registry.list_techniques()}
