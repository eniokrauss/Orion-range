from fastapi import APIRouter, HTTPException

from app.schemas.scenario import ScenarioStartRequest
from app.services.scenario_repository import ScenarioRunNotFoundError, scenario_repository
from app.services.scenario_runner import start_scenario, stop_scenario

router = APIRouter(prefix="/scenarios")


@router.post("/runs")
def start_scenario_run(payload: ScenarioStartRequest):
    run = scenario_repository.create(scenario_name=payload.scenario_name, timeline=[])
    start_scenario(run.id, payload.steps)
    return {
        "id": run.id,
        "scenario_name": run.scenario_name,
        "status": run.status,
        "timeline": run.timeline,
    }


@router.get("/runs")
def list_scenario_runs():
    runs = scenario_repository.list()
    return [
        {
            "id": run.id,
            "scenario_name": run.scenario_name,
            "status": run.status,
            "timeline": run.timeline,
        }
        for run in runs
    ]


@router.get("/runs/{run_id}")
def get_scenario_run(run_id: str):
    try:
        run = scenario_repository.get(run_id)
    except ScenarioRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "id": run.id,
        "scenario_name": run.scenario_name,
        "status": run.status,
        "timeline": run.timeline,
    }


@router.post("/runs/{run_id}/stop")
def stop_scenario_run(run_id: str):
    try:
        scenario_repository.get(run_id)
    except ScenarioRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    stop_scenario(run_id)
    return {"id": run_id, "status": "stopping"}
