-- Migration 0010: per-user JWT token version state for global session revocation.
CREATE TABLE IF NOT EXISTS user_token_states (
    user_id        VARCHAR(36) PRIMARY KEY,
    token_version  INTEGER     NOT NULL DEFAULT 0,
    updated_at     TIMESTAMP   NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_user_token_states_updated_at ON user_token_states (updated_at);
