"""
Tests for JWT auth, RBAC and user management endpoints.

All tests run with JWT_SECRET set and no API_KEY, ensuring the
JWT path is exercised end-to-end. The existing test_auth.py covers
the legacy API key path and is left unchanged.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.db.base import Base
from app.db.session import engine
from app.main import app
from app.services.token_revocation_repository import token_revocation_repository
from app.services.user_token_state_repository import user_token_state_repository
from app.services.user_repository import user_repository

client = TestClient(app)

_TEST_SECRET = "test-secret-key-not-for-production"
_ADMIN_EMAIL = "admin@orion.local"
_ADMIN_PASS  = "AdminPass123!"
_STUDENT_EMAIL = "student@orion.local"
_STUDENT_PASS  = "StudentPass123!"


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_jwt_env():
    """Configure JWT secret and clear users before each test."""
    original_secret  = settings.jwt_secret
    original_api_key = settings.api_key
    original_fallbacks = settings.jwt_secret_fallbacks
    original_issuer = settings.jwt_issuer
    original_audience = settings.jwt_audience
    original_clock_skew = settings.jwt_clock_skew_seconds
    settings.jwt_secret = _TEST_SECRET
    settings.api_key    = ""  # disable legacy API key for JWT tests
    settings.jwt_secret_fallbacks = ""
    settings.jwt_issuer = ""
    settings.jwt_audience = ""
    settings.jwt_clock_skew_seconds = 30
    Base.metadata.create_all(bind=engine)
    user_repository.clear_all()
    token_revocation_repository.clear_all()
    user_token_state_repository.clear_all()
    yield
    settings.jwt_secret = original_secret
    settings.api_key    = original_api_key
    settings.jwt_secret_fallbacks = original_fallbacks
    settings.jwt_issuer = original_issuer
    settings.jwt_audience = original_audience
    settings.jwt_clock_skew_seconds = original_clock_skew
    user_repository.clear_all()
    token_revocation_repository.clear_all()
    user_token_state_repository.clear_all()


def _create_admin() -> dict:
    """Create an admin user directly in the DB and return login tokens."""
    user_repository.create(
        email=_ADMIN_EMAIL,
        hashed_password=hash_password(_ADMIN_PASS),
        roles="range_admin",
        org_id="default",
    )
    resp = client.post("/auth/login", json={"email": _ADMIN_EMAIL, "password": _ADMIN_PASS})
    assert resp.status_code == 200
    return resp.json()


def _create_student() -> dict:
    """Create a student user and return login tokens."""
    user_repository.create(
        email=_STUDENT_EMAIL,
        hashed_password=hash_password(_STUDENT_PASS),
        roles="student",
        org_id="default",
    )
    resp = client.post("/auth/login", json={"email": _STUDENT_EMAIL, "password": _STUDENT_PASS})
    assert resp.status_code == 200
    return resp.json()


def _auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ── password hashing ──────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self):
        h = hash_password("MySecretPass!")
        assert verify_password("MySecretPass!", h)

    def test_wrong_password_fails(self):
        h = hash_password("correct-password")
        assert not verify_password("wrong-password", h)

    def test_two_hashes_of_same_password_differ(self):
        """Each hash uses a random salt — two calls must not produce the same output."""
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2
        assert verify_password("same-password", h1)
        assert verify_password("same-password", h2)

    def test_empty_stored_hash_fails_gracefully(self):
        assert not verify_password("anything", "")


# ── login ─────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_returns_tokens(self):
        tokens = _create_admin()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self):
        user_repository.create(
            email="user@orion.local",
            hashed_password=hash_password("correct"),
            roles="student",
            org_id="default",
        )
        resp = client.post("/auth/login", json={"email": "user@orion.local", "password": "wrong"})
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_login_unknown_email_returns_401(self):
        resp = client.post("/auth/login", json={"email": "nobody@orion.local", "password": "pass"})
        assert resp.status_code == 401

    def test_login_disabled_account_returns_401(self):
        user = user_repository.create(
            email="disabled@orion.local",
            hashed_password=hash_password("pass"),
            roles="student",
            org_id="default",
        )
        user_repository.set_active(user.id, active=False)
        resp = client.post("/auth/login", json={"email": "disabled@orion.local", "password": "pass"})
        assert resp.status_code == 401


# ── token refresh ─────────────────────────────────────────────────────────────

class TestRefresh:
    def test_refresh_returns_new_access_token(self):
        tokens = _create_admin()
        resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert resp.status_code == 200
        new_tokens = resp.json()
        assert "access_token" in new_tokens
        # New access token must differ from the original (new iat)
        assert new_tokens["access_token"] != tokens["access_token"]

    def test_refresh_with_access_token_fails(self):
        """Access tokens must not be accepted at the refresh endpoint."""
        tokens = _create_admin()
        resp = client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
        assert resp.status_code == 401

    def test_refresh_with_garbage_fails(self):
        resp = client.post("/auth/refresh", json={"refresh_token": "not.a.token"})
        assert resp.status_code == 401

    def test_refresh_token_cannot_be_reused(self):
        tokens = _create_admin()

        first = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert first.status_code == 200

        replay = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert replay.status_code == 401
        assert replay.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_rotated_refresh_token_remains_valid(self):
        tokens = _create_admin()
        first = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert first.status_code == 200

        rotated = first.json()["refresh_token"]
        second = client.post("/auth/refresh", json={"refresh_token": rotated})
        assert second.status_code == 200


class TestLogout:
    def test_logout_requires_at_least_one_token(self):
        resp = client.post("/auth/logout", json={})
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"

    def test_logout_with_invalid_token_returns_401(self):
        resp = client.post("/auth/logout", json={"access_token": "invalid.token.here"})
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_logout_revokes_access_token(self):
        tokens = _create_admin()

        logout_resp = client.post("/auth/logout", json={"access_token": tokens["access_token"]})
        assert logout_resp.status_code == 200
        assert logout_resp.json()["revoked"] == 1

        me_resp = client.get("/auth/me", headers=_auth_header(tokens))
        assert me_resp.status_code == 401
        assert me_resp.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_logout_revokes_refresh_token(self):
        tokens = _create_admin()

        logout_resp = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
        assert logout_resp.status_code == 200
        assert logout_resp.json()["revoked"] == 1

        refresh_resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert refresh_resp.status_code == 401
        assert refresh_resp.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_logout_is_idempotent_for_same_token(self):
        tokens = _create_admin()
        first = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
        second = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})

        assert first.status_code == 200
        assert first.json()["revoked"] == 1
        assert second.status_code == 200
        assert second.json()["revoked"] == 0

    def test_logout_all_invalidates_current_access_and_refresh(self):
        tokens = _create_admin()

        logout_all = client.post("/auth/logout-all", headers=_auth_header(tokens))
        assert logout_all.status_code == 200

        me_after = client.get("/auth/me", headers=_auth_header(tokens))
        assert me_after.status_code == 401
        assert me_after.json()["detail"]["code"] == "UNAUTHORIZED"

        refresh_after = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert refresh_after.status_code == 401
        assert refresh_after.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_logout_all_without_auth_returns_401(self):
        resp = client.post("/auth/logout-all")
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_logout_all_with_api_key_auth_returns_403(self):
        original_secret = settings.jwt_secret
        original_key = settings.api_key
        settings.jwt_secret = ""
        settings.api_key = "test-key"
        try:
            resp = client.post("/auth/logout-all", headers={"x-api-key": "test-key"})
            assert resp.status_code == 403
            assert resp.json()["detail"]["code"] == "FORBIDDEN"
        finally:
            settings.jwt_secret = original_secret
            settings.api_key = original_key


class TestSessions:
    def _seed_revocations_for_admin(self):
        base_tokens = _create_admin()
        first_refresh = client.post("/auth/refresh", json={"refresh_token": base_tokens["refresh_token"]})
        assert first_refresh.status_code == 200
        rotated = first_refresh.json()

        revoke_access = client.post("/auth/logout", json={"access_token": base_tokens["access_token"]})
        assert revoke_access.status_code == 200

        revoke_rotated_refresh = client.post("/auth/logout", json={"refresh_token": rotated["refresh_token"]})
        assert revoke_rotated_refresh.status_code == 200

        return rotated

    def test_list_my_sessions_requires_auth(self):
        resp = client.get("/auth/sessions")
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_list_my_sessions_with_api_key_auth_returns_403(self):
        original_secret = settings.jwt_secret
        original_key = settings.api_key
        settings.jwt_secret = ""
        settings.api_key = "test-key"
        try:
            resp = client.get("/auth/sessions", headers={"x-api-key": "test-key"})
            assert resp.status_code == 403
            assert resp.json()["detail"]["code"] == "FORBIDDEN"
        finally:
            settings.jwt_secret = original_secret
            settings.api_key = original_key

    def test_list_my_sessions_returns_token_version_and_revoked_tokens(self):
        tokens = self._seed_revocations_for_admin()
        resp = client.get("/auth/sessions", headers=_auth_header(tokens))
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"]
        assert isinstance(body["token_version"], int)
        assert isinstance(body["total_revoked_tokens"], int)
        assert body["limit"] == 20
        assert body["offset"] == 0
        assert isinstance(body["filters"], dict)
        assert isinstance(body["revoked_tokens"], list)
        assert body["total_revoked_tokens"] >= 3
        assert any(t["token_type"] == "refresh" for t in body["revoked_tokens"])

    def test_list_my_sessions_supports_pagination(self):
        tokens = self._seed_revocations_for_admin()

        page = client.get("/auth/sessions", params={"limit": 2, "offset": 1}, headers=_auth_header(tokens))
        assert page.status_code == 200
        body = page.json()
        assert body["limit"] == 2
        assert body["offset"] == 1
        assert body["total_revoked_tokens"] >= 3
        assert len(body["revoked_tokens"]) <= 2

    def test_list_my_sessions_supports_filters(self):
        tokens = self._seed_revocations_for_admin()

        refresh_only = client.get(
            "/auth/sessions",
            params={"token_type": "refresh"},
            headers=_auth_header(tokens),
        )
        assert refresh_only.status_code == 200
        refresh_body = refresh_only.json()
        assert refresh_body["filters"]["token_type"] == "refresh"
        assert all(item["token_type"] == "refresh" for item in refresh_body["revoked_tokens"])

        logout_only = client.get(
            "/auth/sessions",
            params={"reason": "logout"},
            headers=_auth_header(tokens),
        )
        assert logout_only.status_code == 200
        logout_body = logout_only.json()
        assert logout_body["filters"]["reason"] == "logout"
        assert all(item["reason"] == "logout" for item in logout_body["revoked_tokens"])

    def test_admin_can_list_other_user_sessions(self):
        admin_tokens = _create_admin()
        user = user_repository.create(
            email="session-user@orion.local",
            hashed_password=hash_password("SessionPass123!"),
            roles="student",
            org_id="default",
        )
        user_tokens = client.post(
            "/auth/login",
            json={"email": "session-user@orion.local", "password": "SessionPass123!"},
        )
        assert user_tokens.status_code == 200
        user_tokens_body = user_tokens.json()
        client.post("/auth/logout", json={"refresh_token": user_tokens_body["refresh_token"]})

        resp = client.get(f"/auth/users/{user.id}/sessions", headers=_auth_header(admin_tokens))
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == user.id
        assert "total_revoked_tokens" in body
        assert isinstance(body["revoked_tokens"], list)
        assert len(body["revoked_tokens"]) >= 1

    def test_admin_can_filter_other_user_sessions(self):
        admin_tokens = _create_admin()
        user = user_repository.create(
            email="session-filter@orion.local",
            hashed_password=hash_password("SessionPass123!"),
            roles="student",
            org_id="default",
        )
        login = client.post("/auth/login", json={"email": "session-filter@orion.local", "password": "SessionPass123!"})
        assert login.status_code == 200
        issued = login.json()
        rotated = client.post("/auth/refresh", json={"refresh_token": issued["refresh_token"]})
        assert rotated.status_code == 200
        client.post("/auth/logout", json={"refresh_token": rotated.json()["refresh_token"]})

        resp = client.get(
            f"/auth/users/{user.id}/sessions",
            params={"reason": "refresh-rotated", "token_type": "refresh"},
            headers=_auth_header(admin_tokens),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["filters"]["reason"] == "refresh-rotated"
        assert body["filters"]["token_type"] == "refresh"
        assert all(item["reason"] == "refresh-rotated" for item in body["revoked_tokens"])

    def test_student_cannot_list_other_user_sessions(self):
        student_tokens = _create_student()
        resp = client.get("/auth/users/any-user/sessions", headers=_auth_header(student_tokens))
        assert resp.status_code == 403

    def test_admin_list_other_user_sessions_returns_404_for_missing_user(self):
        admin_tokens = _create_admin()
        resp = client.get("/auth/users/missing-user/sessions", headers=_auth_header(admin_tokens))
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "NOT_FOUND"


# ── /auth/me ──────────────────────────────────────────────────────────────────

class TestMe:
    def test_me_with_valid_token(self):
        tokens = _create_admin()
        resp = client.get("/auth/me", headers=_auth_header(tokens))
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == _ADMIN_EMAIL
        assert body["auth_method"] == "jwt"

    def test_me_with_no_auth_returns_401(self):
        resp = client.get("/auth/me")
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_me_with_invalid_token_returns_401(self):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401


# ── RBAC ─────────────────────────────────────────────────────────────────────

class TestRBAC:
    def test_admin_can_create_user(self):
        admin_tokens = _create_admin()
        resp = client.post(
            "/auth/users",
            headers=_auth_header(admin_tokens),
            json={"email": "new@orion.local", "password": "NewPass123!", "roles": "student"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "new@orion.local"

    def test_student_cannot_create_user(self):
        student_tokens = _create_student()
        resp = client.post(
            "/auth/users",
            headers=_auth_header(student_tokens),
            json={"email": "other@orion.local", "password": "Pass123!", "roles": "student"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "FORBIDDEN"

    def test_admin_can_list_users(self):
        admin_tokens = _create_admin()
        resp = client.get("/auth/users", headers=_auth_header(admin_tokens))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_student_cannot_list_users(self):
        student_tokens = _create_student()
        resp = client.get("/auth/users", headers=_auth_header(student_tokens))
        assert resp.status_code == 403

    def test_duplicate_email_returns_409(self):
        admin_tokens = _create_admin()
        payload = {"email": "dup@orion.local", "password": "Pass123!", "roles": "student"}
        r1 = client.post("/auth/users", headers=_auth_header(admin_tokens), json=payload)
        assert r1.status_code == 200
        r2 = client.post("/auth/users", headers=_auth_header(admin_tokens), json=payload)
        assert r2.status_code == 409
        assert r2.json()["detail"]["code"] == "CONFLICT"

    def test_admin_can_revoke_user_sessions(self):
        admin_tokens = _create_admin()
        user = user_repository.create(
            email="target@orion.local",
            hashed_password=hash_password("TargetPass123!"),
            roles="student",
            org_id="default",
        )
        resp = client.post(
            f"/auth/users/{user.id}/revoke-sessions",
            headers=_auth_header(admin_tokens),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == user.id
        assert body["token_version"] == 1

    def test_student_cannot_revoke_user_sessions(self):
        student_tokens = _create_student()
        resp = client.post(
            "/auth/users/any-user/revoke-sessions",
            headers=_auth_header(student_tokens),
        )
        assert resp.status_code == 403


# ── full auth flow ────────────────────────────────────────────────────────────

class TestFullAuthFlow:
    def test_protected_blueprint_route_requires_auth_when_jwt_configured(self):
        """With JWT configured, protected routes must reject missing credentials."""
        resp = client.post(
            "/blueprints/validate",
            json={
                "name": "test-lab",
                "schema_version": "1.0",
                "networks": [{"name": "net1"}],
                "nodes": [{"name": "node1", "networks": ["net1"]}],
            },
        )
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "UNAUTHORIZED"

    def test_valid_jwt_accesses_protected_route(self):
        tokens = _create_admin()
        resp = client.post(
            "/blueprints/validate",
            headers=_auth_header(tokens),
            json={
                "name": "jwt-lab",
                "schema_version": "1.0",
                "networks": [{"name": "net1"}],
                "nodes": [{"name": "node1", "networks": ["net1"]}],
            },
        )
        assert resp.status_code == 200

    def test_expired_token_rejected(self):
        """Manually forge a token with exp in the past."""
        import hashlib, hmac, json, time
        from base64 import urlsafe_b64encode

        def b64(data):
            return urlsafe_b64encode(data).rstrip(b"=").decode()

        header  = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload = b64(json.dumps({
            "sub": "user-1", "org_id": "default", "roles": ["range_admin"],
            "type": "access", "iat": 1000, "exp": 1001,  # way in the past
        }).encode())
        sig_bytes = hmac.new(_TEST_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        sig = b64(sig_bytes)
        expired_token = f"{header}.{payload}.{sig}"

        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"]["message"].lower()

    def test_revoke_sessions_invalidates_existing_access_and_refresh(self):
        tokens = _create_admin()

        me_before = client.get("/auth/me", headers=_auth_header(tokens))
        assert me_before.status_code == 200
        user_id = me_before.json()["id"]

        revoke = client.post(
            f"/auth/users/{user_id}/revoke-sessions",
            headers=_auth_header(tokens),
        )
        assert revoke.status_code == 200

        me_after = client.get("/auth/me", headers=_auth_header(tokens))
        assert me_after.status_code == 401
        assert me_after.json()["detail"]["code"] == "UNAUTHORIZED"

        refresh_after = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert refresh_after.status_code == 401
        assert refresh_after.json()["detail"]["code"] == "UNAUTHORIZED"
