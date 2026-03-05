from threading import Event, Lock, Thread
from time import sleep

from app.schemas.scenario import ScenarioStep
from app.services.mitre_plugins.registry import (
    MitreTechniqueNotFoundError,
    mitre_plugin_registry,
)
from app.services.scenario_repository import scenario_repository

_stops: dict[str, Event] = {}
_stops_lock = Lock()


def _ensure_stop_event(run_id: str) -> Event:
    with _stops_lock:
        return _stops.setdefault(run_id, Event())


def _clear_stop_event(run_id: str) -> None:
    with _stops_lock:
        _stops.pop(run_id, None)


def _run(run_id: str, steps: list[ScenarioStep]) -> None:
    stop_event = _ensure_stop_event(run_id)
    timeline: list[dict] = []

    try:
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
    finally:
        _clear_stop_event(run_id)


def start_scenario(run_id: str, steps: list[ScenarioStep]) -> None:
    stop_event = _ensure_stop_event(run_id)
    stop_event.clear()

    worker = Thread(target=_run, args=(run_id, steps), daemon=True)
    worker.start()


def stop_scenario(run_id: str) -> None:
    stop_event = _ensure_stop_event(run_id)
    stop_event.set()
