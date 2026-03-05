from collections import Counter
from datetime import datetime

from app.services.blueprint_repository import blueprint_repository
from app.services.job_repository import job_repository
from app.services.scenario_repository import scenario_repository


def _iso(dt: datetime | None) -> str:
    if not dt:
        return datetime.utcnow().isoformat()
    return dt.isoformat()


def get_ops_overview() -> dict:
    blueprints = blueprint_repository.list()
    jobs = job_repository.list()
    runs = scenario_repository.list()

    job_status = Counter(job.status for job in jobs)
    run_status = Counter(run.status for run in runs)

    active_jobs = job_status.get("running", 0) + job_status.get("pending", 0)
    active_scenarios = run_status.get("running", 0) + run_status.get("pending", 0)

    telemetry = {
        "packets_per_sec": 700 + (active_jobs * 27) + (active_scenarios * 33),
        "throughput_gbps": round(1.2 + (active_jobs * 0.08) + (active_scenarios * 0.11), 2),
        "connections": 110 + (len(blueprints) * 4) + (active_jobs * 2),
    }

    events: list[dict] = []

    for run in runs[:5]:
        events.append(
            {
                "timestamp": _iso(run.updated_at),
                "level": "error" if run.status == "failed" else "info",
                "source": "scenario",
                "message": f"{run.scenario_name} -> {run.status}",
            }
        )

    for job in jobs[:5]:
        events.append(
            {
                "timestamp": _iso(job.updated_at),
                "level": "error" if job.status == "failed" else "info",
                "source": "job",
                "message": f"{job.action} ({job.id[:8]}) -> {job.status}",
            }
        )

    for bp in blueprints[:3]:
        events.append(
            {
                "timestamp": _iso(bp.created_at),
                "level": "ok",
                "source": "blueprint",
                "message": f"Blueprint created: {bp.name}",
            }
        )

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
            "alerts_per_min": job_status.get("failed", 0) + run_status.get("failed", 0),
            "anomalies": active_scenarios + job_status.get("failed", 0),
        },
        "telemetry": telemetry,
        "recent_events": events,
    }
