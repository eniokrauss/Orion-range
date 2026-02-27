from fastapi import APIRouter, HTTPException

from app.schemas.blueprint import LabBlueprint
codex/verify-the-structure-kqxjtv
from app.services.blueprint_store import BlueprintNotFoundError, blueprint_store
main
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
codex/verify-the-structure-kqxjtv


@router.post("")
def create_blueprint(blueprint: LabBlueprint):
    try:
        validate_blueprint(blueprint)
    except BlueprintError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stored = blueprint_store.create(blueprint)
    return {
        "id": stored.blueprint_id,
        "name": stored.blueprint.name,
        "version": stored.blueprint.version,
        "nodes": len(stored.blueprint.nodes),
        "networks": len(stored.blueprint.networks),
    }


@router.get("")
def list_blueprints():
    items = blueprint_store.list()
    return [
        {
            "id": item.blueprint_id,
            "name": item.blueprint.name,
            "version": item.blueprint.version,
            "nodes": len(item.blueprint.nodes),
            "networks": len(item.blueprint.networks),
        }
        for item in items
    ]


@router.get("/{blueprint_id}")
def get_blueprint(blueprint_id: str):
    try:
        item = blueprint_store.get(blueprint_id)
    except BlueprintNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "id": item.blueprint_id,
        "blueprint": item.blueprint.model_dump(),
    }


@router.delete("/{blueprint_id}", status_code=204)
def delete_blueprint(blueprint_id: str):
    try:
        blueprint_store.delete(blueprint_id)
    except BlueprintNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None
main
