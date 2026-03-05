CREATE TABLE IF NOT EXISTS scenario_runs (
    id VARCHAR(36) PRIMARY KEY,
    scenario_name VARCHAR(120) NOT NULL,
    status VARCHAR(20) NOT NULL,
    timeline JSON NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
