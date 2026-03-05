from types import SimpleNamespace

from app.services import job_runner


class _FakeJobRepository:
    def __init__(self, job):
        self.job = job
        self.updates: list[dict] = []

    def get(self, job_id: str):
        return self.job

    def update_status(self, **kwargs):
        self.updates.append(kwargs)


class _FakeAdapter:
    def provision(self, _target_blueprint_id):
        return None

    def snapshot(self, _target_blueprint_id):
        return None

    def reset(self, _target_blueprint_id):
        return None


def test_run_job_cleans_running_registry(monkeypatch):
    fake_job = SimpleNamespace(action="provision", target_blueprint_id=None, max_attempts=1)
    fake_repository = _FakeJobRepository(fake_job)

    monkeypatch.setattr(job_runner, "job_repository", fake_repository)
    monkeypatch.setattr(job_runner, "get_hypervisor_adapter", lambda: _FakeAdapter())

    job_id = "job-cleanup"
    job_runner._run_job(job_id)

    assert fake_repository.updates[-1]["status"] == "succeeded"
    assert job_id not in job_runner._running_jobs


def test_run_job_ignores_duplicate_execution(monkeypatch):
    fake_job = SimpleNamespace(action="provision", target_blueprint_id=None, max_attempts=1)
    fake_repository = _FakeJobRepository(fake_job)

    monkeypatch.setattr(job_runner, "job_repository", fake_repository)
    monkeypatch.setattr(job_runner, "get_hypervisor_adapter", lambda: _FakeAdapter())

    job_id = "job-duplicate"
    job_runner._running_jobs.add(job_id)
    try:
        job_runner._run_job(job_id)
    finally:
        job_runner._running_jobs.discard(job_id)

    assert fake_repository.updates == []
