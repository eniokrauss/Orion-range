-- Migration 0007: add org_id to all domain tables.
-- Uses ALTER TABLE ... ADD COLUMN IF NOT EXISTS for idempotency.
-- Default value 'default' preserves all existing rows.

ALTER TABLE blueprints
    ADD COLUMN IF NOT EXISTS org_id VARCHAR(36) NOT NULL DEFAULT 'default';

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS org_id VARCHAR(36) NOT NULL DEFAULT 'default';

ALTER TABLE baselines
    ADD COLUMN IF NOT EXISTS org_id VARCHAR(36) NOT NULL DEFAULT 'default';

ALTER TABLE scenario_runs
    ADD COLUMN IF NOT EXISTS org_id VARCHAR(36) NOT NULL DEFAULT 'default';

-- Indexes for tenant-scoped queries (the most common access pattern).
CREATE INDEX IF NOT EXISTS ix_blueprints_org_id    ON blueprints    (org_id);
CREATE INDEX IF NOT EXISTS ix_jobs_org_id           ON jobs          (org_id);
CREATE INDEX IF NOT EXISTS ix_baselines_org_id      ON baselines     (org_id);
CREATE INDEX IF NOT EXISTS ix_scenario_runs_org_id  ON scenario_runs (org_id);
