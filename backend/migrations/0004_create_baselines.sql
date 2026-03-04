CREATE TABLE IF NOT EXISTS baselines (
    blueprint_id VARCHAR(36) PRIMARY KEY,
    snapshot_ref VARCHAR(120) NOT NULL,
    reset_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
