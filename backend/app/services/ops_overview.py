"""
Ops overview — aggregates real runtime data from DB repositories.

No simulated or hardcoded telemetry values. Every number comes from
the database so the frontend reflects actual system state.
"""

from collections import Counter
from datetime import datetime

from app.core.time_utils import utcnow
from app.services.blueprint_repository import blueprint_repository
from app.services.job_repository import job_repository
from app.services.job_step_repository import job_step_repository
from app.services.scenario_repository import scenario_repository


def _iso(dt: datetime | None) -> str:
    if not dt:
        return utcnow().isoformat()
    return dt.isoformat()


def get_ops_overview() -> dict:
    blueprints = blueprint_repository.list()
    jobs = job_repository.list()
    runs = scenario_repository.list()

    job_status = Counter(job.status for job in jobs)
    run_status = Counter(run.status for run in runs)

    active_jobs = job_status.get("running", 0) + job_status.get("pending", 0)
    active_scenarios = run_status.get("running", 0) + run_status.get("pending", 0)
    failed_jobs = job_status.get("failed", 0)
    failed_scenarios = run_status.get("failed", 0)

    # Step-level stats derived from real DB data
    running_job_ids = [j.id for j in jobs if j.status == "running"]
    active_steps = 0
    for job_id in running_job_ids:
        steps = job_step_repository.list_for_job(job_id)
        active_steps += sum(1 for s in steps if s.status == "running")

    events: list[dict] = []

    for run in runs[:5]:
        events.append({
            "timestamp": _iso(run.updated_at),
            "level": "error" if run.status == "failed" else "info",
            "source": "scenario",
            "message": f"{run.scenario_name} -> {run.status}",
        })

    for job in jobs[:5]:
        events.append({
            "timestamp": _iso(job.updated_at),
            "level": "error" if job.status == "failed" else ("warn" if job.attempts > 1 else "info"),
            "source": "job",
            "message": f"{job.action} ({job.id[:8]}) -> {job.status}"
                       + (f" [attempt {job.attempts}/{job.max_attempts}]" if job.attempts > 1 else ""),
        })

    for bp in blueprints[:3]:
        events.append({
            "timestamp": _iso(bp.created_at),
            "level": "ok",
            "source": "blueprint",
            "message": f"Blueprint registered: {bp.name} v{bp.version}",
        })

    events = sorted(events, key=lambda item: item["timestamp"], reverse=True)[:12]

    return {
        "summary": {
            "blueprints_total": len(blueprints),
            "jobs_total": len(jobs),
            "jobs_by_status": dict(job_status),
            "scenarios_total": len(runs),
            "scenarios_by_status": dict(run_status),
            "active_jobs": active_jobs,
            "active_scenarios": active_scenarios,
            "active_steps": active_steps,
            "failed_jobs": failed_jobs,
            "failed_scenarios": failed_scenarios,
            "alerts_active": failed_jobs + failed_scenarios,
        },
        "recent_events": events,
    }
