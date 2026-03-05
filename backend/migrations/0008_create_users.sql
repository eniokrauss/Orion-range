-- Migration 0008: users table for JWT-based auth and RBAC.
CREATE TABLE IF NOT EXISTS users (
    id              VARCHAR(36)  PRIMARY KEY,
    org_id          VARCHAR(36)  NOT NULL DEFAULT 'default',
    email           VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    roles           VARCHAR(200) NOT NULL DEFAULT 'student',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP    NOT NULL,
    updated_at      TIMESTAMP    NOT NULL,
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS ix_users_org_id ON users (org_id);
CREATE INDEX IF NOT EXISTS ix_users_email  ON users (email);
