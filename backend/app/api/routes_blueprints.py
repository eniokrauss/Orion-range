from fastapi import APIRouter, HTTPException

from app.schemas.blueprint import LabBlueprint
from app.services.blueprint_validator import BlueprintError, validate_blueprint

router = APIRouter(prefix="/blueprints", tags=["blueprints"])


@router.post("/validate")
def validate_blueprint_route(blueprint: LabBlueprint):
    try:
        validate_blueprint(blueprint)
    except BlueprintError as exc:
        message = str(exc)
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BLUEPRINT_VALIDATION_ERROR",
                "message": message,
                "legacy_detail": message,
            },
        ) from exc

    nodes_count = len(blueprint.nodes)
    networks_count = len(blueprint.networks)

    return {
        "valid": True,
        "name": blueprint.name,
        "version": blueprint.version,
        "nodes": nodes_count,
        "networks": networks_count,
        "summary": {
            "nodes": nodes_count,
            "networks": networks_count,
        },
    }
