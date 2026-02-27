from fastapi import APIRouter, HTTPException

from app.schemas.blueprint import LabBlueprint
from app.services.blueprint_validator import BlueprintError, validate_blueprint

router = APIRouter(prefix="/blueprints")


@router.post("/validate")
def validate_blueprint_route(blueprint: LabBlueprint):
    try:
        validate_blueprint(blueprint)
    except BlueprintError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "valid": True,
        "name": blueprint.name,
        "version": blueprint.version,
        "nodes": len(blueprint.nodes),
        "networks": len(blueprint.networks),
    }
