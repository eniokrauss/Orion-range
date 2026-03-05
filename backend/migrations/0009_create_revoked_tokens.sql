-- Migration 0009: revoked token registry for refresh-token rotation/revocation.
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti         VARCHAR(64)  PRIMARY KEY,
    token_type  VARCHAR(20)  NOT NULL,
    subject_id  VARCHAR(36),
    org_id      VARCHAR(36),
    reason      VARCHAR(120),
    expires_at  TIMESTAMP    NOT NULL,
    revoked_at  TIMESTAMP    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_revoked_tokens_token_type ON revoked_tokens (token_type);
CREATE INDEX IF NOT EXISTS ix_revoked_tokens_subject_id ON revoked_tokens (subject_id);
CREATE INDEX IF NOT EXISTS ix_revoked_tokens_org_id     ON revoked_tokens (org_id);
CREATE INDEX IF NOT EXISTS ix_revoked_tokens_expires_at ON revoked_tokens (expires_at);
