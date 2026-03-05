"""
Auth dependencies for FastAPI routes.

Two authentication strategies coexist for backward compatibility:

1. JWT Bearer token  — new, preferred. Used by /auth/login flow.
2. API key header    — legacy, kept for existing integrations.
   When API_KEY is set in settings, all protected routes also accept
   x-api-key. When both are empty/unconfigured, routes are open
   (dev mode).

RBAC dependency factories:
  require_roles(["range_admin"])  — factory that returns a FastAPI dep
  RequireRole.admin               — shorthand for range_admin
  RequireRole.instructor          — shorthand for instructor
  RequireRole.student             — shorthand for student (any auth)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from hmac import compare_digest

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.errors import ErrorCode, http_error
from app.core.security import TokenError, TokenPayload, decode_token
from app.services.token_revocation_repository import token_revocation_repository
from app.services.user_token_state_repository import user_token_state_repository

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


# ── current-user dataclass surfaced to route handlers ────────────────────────

@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    org_id: str
    roles: set[str]

    def has_role(self, *roles: str) -> bool:
        return bool(self.roles & set(roles))


# ── core auth resolution ──────────────────────────────────────────────────────

def _resolve_current_user(
    credentials: HTTPAuthorizationCredentials | None,
    x_api_key: str | None,
) -> CurrentUser | None:
    """
    Try JWT first, fall back to API key.
    Returns None when neither is configured (open/dev mode).
    """

    configured_jwt = bool(settings.jwt_secret)
    configured_key = bool(settings.api_key)

    # ── JWT path ──────────────────────────────────────────────────────────────
    if credentials is not None:
        try:
            payload: TokenPayload = decode_token(credentials.credentials, expected_type="access")
            if token_revocation_repository.is_revoked(payload.jti):
                raise http_error(
                    status_code=401,
                    code=ErrorCode.UNAUTHORIZED,
                    message="Token has been revoked.",
                )
            current_version = user_token_state_repository.get_token_version(payload.sub)
            if payload.token_version != current_version:
                raise http_error(
                    status_code=401,
                    code=ErrorCode.UNAUTHORIZED,
                    message="Token session is no longer valid.",
                )
            return CurrentUser(
                user_id=payload.sub,
                org_id=payload.org_id,
                roles=payload.roles,
            )
        except TokenError as exc:
            logger.debug("JWT validation failed: %s", exc)
            raise http_error(
                status_code=401,
                code=ErrorCode.UNAUTHORIZED,
                message=str(exc),
            ) from exc

    # ── API key path (legacy) ─────────────────────────────────────────────────
    if x_api_key is not None:
        if configured_key and compare_digest(x_api_key, settings.api_key):
            return CurrentUser(
                user_id="api-key-user",
                org_id="default",
                roles={"range_admin"},  # API key grants full access
            )
        raise http_error(
            status_code=401,
            code=ErrorCode.UNAUTHORIZED,
            message="Invalid API key.",
        )

    if configured_jwt or configured_key:
        raise http_error(
            status_code=401,
            code=ErrorCode.UNAUTHORIZED,
            message="Missing authentication credentials.",
        )

    # ── open mode (neither configured) ───────────────────────────────────────
    return None


# ── backward-compat dependency (used in main.py include_router) ──────────────

def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_api_key: str | None = Header(default=None),
) -> CurrentUser | None:
    """
    Drop-in replacement for the old require_api_key.
    Accepts JWT Bearer or x-api-key header. Returns None in open mode.
    Existing tests that set settings.api_key still work unchanged.
    """
    return _resolve_current_user(credentials, x_api_key)


# ── RBAC dependency factory ───────────────────────────────────────────────────

def require_roles(required: list[str]):
    """
    Return a FastAPI dependency that enforces role membership.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_roles(["range_admin"]))])

    In open mode (no JWT secret, no API key) the check is skipped so
    that local dev and the existing test suite continue to work.
    """
    def _dep(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
        x_api_key: str | None = Header(default=None),
    ) -> CurrentUser | None:
        user = _resolve_current_user(credentials, x_api_key)
        if user is None:
            # open/dev mode — skip RBAC
            return None

        if not user.has_role(*required):
            raise http_error(
                status_code=403,
                code=ErrorCode.FORBIDDEN,
                message=f"Required role(s): {required}. Your roles: {sorted(user.roles)}.",
            )
        return user

    return _dep


class RequireRole:
    """Shorthand dependency instances for common role checks."""
    admin      = Depends(require_roles(["range_admin"]))
    instructor = Depends(require_roles(["range_admin", "instructor"]))
    student    = Depends(require_roles(["range_admin", "instructor", "student"]))
