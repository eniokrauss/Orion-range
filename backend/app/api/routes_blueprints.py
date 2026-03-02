from fastapi import APIRouter, HTTPException

from app.schemas.blueprint import LabBlueprint
from app.services.blueprint_repository import BlueprintNotFoundError, blueprint_repository
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


@router.post("")
def create_blueprint(blueprint: LabBlueprint):
    try:
        validate_blueprint(blueprint)
    except BlueprintError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stored = blueprint_repository.create(blueprint)
    payload = stored.payload
    return {
        "id": stored.id,
        "name": stored.name,
        "version": stored.version,
        "nodes": len(payload.get("nodes", [])),
        "networks": len(payload.get("networks", [])),
    }


@router.get("")
def list_blueprints():
    items = blueprint_repository.list()
    return [
        {
            "id": item.id,
            "name": item.name,
            "version": item.version,
            "nodes": len(item.payload.get("nodes", [])),
            "networks": len(item.payload.get("networks", [])),
        }
        for item in items
    ]


@router.get("/{blueprint_id}")
def get_blueprint(blueprint_id: str):
    try:
        item = blueprint_repository.get(blueprint_id)
    except BlueprintNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "id": item.id,
        "blueprint": item.payload,
    }


@router.delete("/{blueprint_id}", status_code=204)
def delete_blueprint(blueprint_id: str):
    try:
        blueprint_repository.delete(blueprint_id)
    except BlueprintNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None
