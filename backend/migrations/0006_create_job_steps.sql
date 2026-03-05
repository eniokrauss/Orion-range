-- Migration 0006: job_steps table for checkpoint-based job recovery.
-- Each row represents one atomic step within a job's execution plan.
-- Steps with status='done' are skipped on retry — enabling idempotent recovery.
CREATE TABLE IF NOT EXISTS job_steps (
    id          VARCHAR(36)  PRIMARY KEY,
    job_id      VARCHAR(36)  NOT NULL,
    step_key    VARCHAR(100) NOT NULL,
    status      VARCHAR(20)  NOT NULL DEFAULT 'pending',
    error       TEXT,
    started_at  TIMESTAMP,
    finished_at TIMESTAMP,
    created_at  TIMESTAMP    NOT NULL,
    CONSTRAINT uq_job_step UNIQUE (job_id, step_key)
);

CREATE INDEX IF NOT EXISTS ix_job_steps_job_id ON job_steps (job_id);
