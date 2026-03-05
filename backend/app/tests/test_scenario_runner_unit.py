from app.schemas.scenario import ScenarioStep
from app.services import scenario_runner


class _FakeRepository:
    def __init__(self) -> None:
        self.updates: list[tuple[str, str, list[dict]]] = []

    def update(self, run_id: str, status: str, timeline: list[dict]):
        self.updates.append((run_id, status, list(timeline)))


class _FakeRegistry:
    def resolve_action(self, action: str):
        return action, None


def test_run_cleans_stop_event_after_completion(monkeypatch):
    fake_repository = _FakeRepository()

    monkeypatch.setattr(scenario_runner, "scenario_repository", fake_repository)
    monkeypatch.setattr(scenario_runner, "mitre_plugin_registry", _FakeRegistry())

    run_id = "run-cleanup"
    steps = [ScenarioStep(name="step-1", action="inject", delay_ms=0)]

    scenario_runner._run(run_id, steps)

    assert all(status != "failed" for _, status, _ in fake_repository.updates)
    assert fake_repository.updates[-1][1] == "completed"
    assert run_id not in scenario_runner._stops


def test_run_stops_when_stop_flag_is_set_and_cleans_map(monkeypatch):
    fake_repository = _FakeRepository()

    monkeypatch.setattr(scenario_runner, "scenario_repository", fake_repository)
    monkeypatch.setattr(scenario_runner, "mitre_plugin_registry", _FakeRegistry())

    run_id = "run-stopped"
    stop_event = scenario_runner._ensure_stop_event(run_id)
    stop_event.set()

    steps = [ScenarioStep(name="step-1", action="inject", delay_ms=0)]
    scenario_runner._run(run_id, steps)

    assert fake_repository.updates[-1][1] == "stopped"
    assert run_id not in scenario_runner._stops
