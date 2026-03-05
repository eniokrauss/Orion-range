"""
Auth routes — login, token refresh, user management.

POST /auth/login          — email + password → access + refresh tokens
POST /auth/refresh        — refresh token → new access token (one-time refresh token)
POST /auth/logout         — revoke provided access/refresh tokens
POST /auth/logout-all     — revoke all JWT sessions for current user
GET  /auth/sessions       — show current user session state
POST /auth/users/{id}/revoke-sessions — revoke all sessions for a user
GET  /auth/users/{id}/sessions        — show session state for a user (admin)
GET  /auth/me             — current user info (requires valid access token)
POST /auth/users          — create user (range_admin only)
GET  /auth/users          — list users in org (range_admin only)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser, RequireRole, require_api_key, require_roles
from app.core.errors import ErrorCode, http_error
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
)
from app.services.user_repository import (
    UserEmailConflictError,
    UserNotFoundError,
    user_repository,
)
from app.services.token_revocation_repository import token_revocation_repository
from app.services.user_token_state_repository import user_token_state_repository

router = APIRouter(prefix="/auth")


def _user_response(record) -> dict:
    return {
        "id": record.id,
        "email": record.email,
        "org_id": record.org_id,
        "roles": record.roles,
        "is_active": record.is_active,
        "created_at": record.created_at.isoformat(),
    }


def _decode_any_token(token: str):
    try:
        return decode_token(token, expected_type="access")
    except TokenError:
        return decode_token(token, expected_type="refresh")


def _sessions_payload(
    user_id: str,
    *,
    limit: int,
    offset: int,
    token_type: str | None = None,
    reason: str | None = None,
) -> dict:
    token_revocation_repository.prune_expired()
    token_version = user_token_state_repository.get_token_version(user_id)
    total = token_revocation_repository.count_for_subject(
        user_id,
        token_type=token_type,
        reason=reason,
    )
    revoked = token_revocation_repository.list_for_subject(
        user_id,
        limit=limit,
        offset=offset,
        token_type=token_type,
        reason=reason,
    )
    return {
        "user_id": user_id,
        "token_version": token_version,
        "total_revoked_tokens": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "token_type": token_type,
            "reason": reason,
        },
        "revoked_tokens": [
            {
                "jti": row.jti,
                "token_type": row.token_type,
                "reason": row.reason,
                "revoked_at": row.revoked_at.isoformat(),
                "expires_at": row.expires_at.isoformat(),
            }
            for row in revoked
        ],
    }


# ── public endpoints ──────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    """Authenticate with email and password. Returns access + refresh tokens."""
    try:
        user = user_repository.get_by_email(payload.email)
    except UserNotFoundError:
        # Don't reveal whether the email exists
        raise http_error(status_code=401, code=ErrorCode.UNAUTHORIZED,
                         message="Invalid email or password.")

    if not user.is_active:
        raise http_error(status_code=401, code=ErrorCode.UNAUTHORIZED,
                         message="Account is disabled.")

    if not verify_password(payload.password, user.hashed_password):
        raise http_error(status_code=401, code=ErrorCode.UNAUTHORIZED,
                         message="Invalid email or password.")

    roles = user.role_set()
    token_version = user_token_state_repository.get_token_version(user.id)
    return {
        "access_token":  create_access_token(user.id, user.org_id, roles, token_version=token_version),
        "refresh_token": create_refresh_token(user.id, user.org_id, roles, token_version=token_version),
        "token_type":    "bearer",
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest):
    """Exchange a refresh token for a new access token."""
    try:
        token_data = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise http_error(status_code=401, code=ErrorCode.UNAUTHORIZED, message=str(exc)) from exc

    if not token_revocation_repository.revoke(
        jti=token_data.jti,
        token_type=token_data.token_type,
        exp_unix=token_data.exp,
        subject_id=token_data.sub,
        org_id=token_data.org_id,
        reason="refresh-rotated",
    ):
        raise http_error(
            status_code=401,
            code=ErrorCode.UNAUTHORIZED,
            message="Refresh token has already been used or revoked.",
        )

    # Re-fetch user to catch deactivation since token was issued
    try:
        user = user_repository.get_by_id(token_data.sub)
    except UserNotFoundError:
        raise http_error(status_code=401, code=ErrorCode.UNAUTHORIZED,
                         message="User no longer exists.")

    if not user.is_active:
        raise http_error(status_code=401, code=ErrorCode.UNAUTHORIZED,
                         message="Account is disabled.")

    current_version = user_token_state_repository.get_token_version(user.id)
    if token_data.token_version != current_version:
        raise http_error(
            status_code=401,
            code=ErrorCode.UNAUTHORIZED,
            message="Refresh token session is no longer valid.",
        )

    roles = user.role_set()
    token_revocation_repository.prune_expired()
    return {
        "access_token":  create_access_token(user.id, user.org_id, roles, token_version=current_version),
        "refresh_token": create_refresh_token(user.id, user.org_id, roles, token_version=current_version),
        "token_type":    "bearer",
    }


@router.post("/logout")
def logout(payload: LogoutRequest):
    """Revoke provided access/refresh tokens (idempotent)."""
    provided_tokens = [t for t in (payload.access_token, payload.refresh_token) if t]
    if not provided_tokens:
        raise http_error(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Provide at least one token (access_token or refresh_token).",
        )

    revoked_count = 0
    for token in provided_tokens:
        try:
            token_data = _decode_any_token(token)
        except TokenError as exc:
            raise http_error(status_code=401, code=ErrorCode.UNAUTHORIZED, message=str(exc)) from exc

        inserted = token_revocation_repository.revoke(
            jti=token_data.jti,
            token_type=token_data.token_type,
            exp_unix=token_data.exp,
            subject_id=token_data.sub,
            org_id=token_data.org_id,
            reason="logout",
        )
        if inserted:
            revoked_count += 1

    token_revocation_repository.prune_expired()
    return {"revoked": revoked_count}


@router.post("/logout-all")
def logout_all(current_user: CurrentUser | None = Depends(require_api_key)):
    """Invalidate all JWT sessions for the authenticated user."""
    if current_user is None:
        raise http_error(
            status_code=401,
            code=ErrorCode.UNAUTHORIZED,
            message="Authentication required.",
        )

    if current_user.user_id == "api-key-user":
        raise http_error(
            status_code=403,
            code=ErrorCode.FORBIDDEN,
            message="logout-all requires JWT user authentication.",
        )

    new_version = user_token_state_repository.bump_token_version(current_user.user_id)
    token_revocation_repository.prune_expired()
    return {"user_id": current_user.user_id, "token_version": new_version}


@router.get("/sessions")
def list_my_sessions(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    token_type: str | None = Query(default=None),
    reason: str | None = Query(default=None),
    current_user: CurrentUser | None = Depends(require_api_key),
):
    """Return current JWT session state for authenticated user."""
    if current_user is None:
        raise http_error(
            status_code=401,
            code=ErrorCode.UNAUTHORIZED,
            message="Authentication required.",
        )

    if current_user.user_id == "api-key-user":
        raise http_error(
            status_code=403,
            code=ErrorCode.FORBIDDEN,
            message="JWT user authentication required.",
        )

    return _sessions_payload(
        current_user.user_id,
        limit=limit,
        offset=offset,
        token_type=token_type,
        reason=reason,
    )


@router.post("/users/{user_id}/revoke-sessions", dependencies=[Depends(require_roles(["range_admin"]))])
def revoke_user_sessions(user_id: str):
    """Invalidate all JWT sessions for a specific user by bumping token version."""
    try:
        user_repository.get_by_id(user_id)
    except UserNotFoundError as exc:
        raise http_error(status_code=404, code=ErrorCode.NOT_FOUND, message=str(exc)) from exc

    new_version = user_token_state_repository.bump_token_version(user_id)
    token_revocation_repository.prune_expired()
    return {"user_id": user_id, "token_version": new_version}


@router.get("/users/{user_id}/sessions", dependencies=[Depends(require_roles(["range_admin"]))])
def list_user_sessions(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    token_type: str | None = Query(default=None),
    reason: str | None = Query(default=None),
):
    try:
        user_repository.get_by_id(user_id)
    except UserNotFoundError as exc:
        raise http_error(status_code=404, code=ErrorCode.NOT_FOUND, message=str(exc)) from exc

    return _sessions_payload(
        user_id,
        limit=limit,
        offset=offset,
        token_type=token_type,
        reason=reason,
    )


# ── authenticated endpoints ───────────────────────────────────────────────────

@router.get("/me")
def me(current_user: CurrentUser | None = Depends(require_api_key)):
    """Return info about the currently authenticated user."""
    if current_user is None:
        return {"mode": "open", "message": "No authentication configured."}

    if current_user.user_id == "api-key-user":
        return {
            "user_id": "api-key-user",
            "org_id": current_user.org_id,
            "roles": sorted(current_user.roles),
            "auth_method": "api_key",
        }

    try:
        user = user_repository.get_by_id(current_user.user_id)
    except UserNotFoundError:
        raise http_error(status_code=401, code=ErrorCode.UNAUTHORIZED,
                         message="User not found.")

    return {
        **_user_response(user),
        "auth_method": "jwt",
    }


# ── admin-only user management ────────────────────────────────────────────────

@router.post("/users", dependencies=[Depends(require_roles(["range_admin"]))])
def create_user(payload: UserCreateRequest):
    """Create a new user account. Requires range_admin role."""
    try:
        user = user_repository.create(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            roles=payload.roles,
            org_id=payload.org_id,
        )
    except UserEmailConflictError as exc:
        raise http_error(status_code=409, code=ErrorCode.CONFLICT, message=str(exc)) from exc

    return _user_response(user)


@router.get("/users", dependencies=[Depends(require_roles(["range_admin"]))])
def list_users(org_id: str | None = None):
    """List users, optionally filtered by org. Requires range_admin role."""
    users = user_repository.list(org_id=org_id)
    return [_user_response(u) for u in users]
