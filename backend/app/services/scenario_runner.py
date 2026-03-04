from threading import Event, Thread
from time import sleep

from app.schemas.scenario import ScenarioStep
from app.services.mitre_plugins.registry import (
    MitreTechniqueNotFoundError,
    mitre_plugin_registry,
)
from app.services.scenario_repository import scenario_repository

_stops: dict[str, Event] = {}


def _run(run_id: str, steps: list[ScenarioStep]) -> None:
    stop_event = _stops.setdefault(run_id, Event())
    timeline: list[dict] = []
    scenario_repository.update(run_id, status="running", timeline=timeline)

    for step in steps:
        if stop_event.is_set():
            scenario_repository.update(run_id, status="stopped", timeline=timeline)
            return

        if step.delay_ms:
            sleep(step.delay_ms / 1000)

        try:
            resolved_action, technique = mitre_plugin_registry.resolve_action(step.action)
        except MitreTechniqueNotFoundError as exc:
            timeline.append(
                {
                    "step": step.name,
                    "action": step.action,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            scenario_repository.update(run_id, status="failed", timeline=timeline)
            return

        event = {"step": step.name, "action": resolved_action, "status": "done"}
        if technique:
            event["mitre"] = {
                "technique_id": technique.technique_id,
                "name": technique.name,
            }

        timeline.append(event)
        scenario_repository.update(run_id, status="running", timeline=timeline)

    scenario_repository.update(run_id, status="completed", timeline=timeline)


def start_scenario(run_id: str, steps: list[ScenarioStep]) -> None:
    worker = Thread(target=_run, args=(run_id, steps), daemon=True)
    worker.start()


def stop_scenario(run_id: str) -> None:
    stop_event = _stops.setdefault(run_id, Event())
    stop_event.set()
