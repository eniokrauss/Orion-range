"""
Security utilities — password hashing and JWT token lifecycle.

Password hashing uses PBKDF2-HMAC-SHA256 via the stdlib `hashlib`
module so there are zero new dependencies for the core auth flow.

JWT tokens are signed with HS256 using a secret from settings.
The payload carries: sub (user_id), org_id, roles, type (access|refresh).

Access tokens:  short-lived (default 30 min).
Refresh tokens: longer-lived (default 7 days), used only to mint new
                access tokens — never accepted on domain endpoints.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── constants ─────────────────────────────────────────────────────────────────

_ACCESS_TTL_SECONDS  = 30 * 60        # 30 minutes
_REFRESH_TTL_SECONDS = 7 * 24 * 3600  # 7 days
_PBKDF2_ITERATIONS   = 260_000        # OWASP 2023 recommendation
_PBKDF2_ALGO         = "sha256"


# ── exceptions ────────────────────────────────────────────────────────────────

class TokenError(Exception):
    """Raised when a JWT is invalid, expired or has wrong type."""


# ── dataclass ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TokenPayload:
    sub: str          # user_id
    org_id: str
    roles: set[str]
    token_type: str   # "access" or "refresh"
    exp: int          # unix timestamp
    jti: str
    token_version: int


# ── password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash of *password* as a storable string."""
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGO,
        password.encode(),
        salt.encode(),
        _PBKDF2_ITERATIONS,
    )
    return f"pbkdf2:{_PBKDF2_ITERATIONS}:{salt}:{dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Return True if *password* matches *stored_hash*."""
    try:
        _, iterations_str, salt, dk_hex = stored_hash.split(":")
        iterations = int(iterations_str)
    except (ValueError, AttributeError):
        return False

    dk = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGO,
        password.encode(),
        salt.encode(),
        iterations,
    )
    return hmac.compare_digest(dk.hex(), dk_hex)


# ── minimal JWT (HS256, stdlib only) ─────────────────────────────────────────

def _b64_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return urlsafe_b64decode(s + "=" * (padding % 4))


def _split_csv(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]


def _jwt_signing_secret() -> bytes:
    secret = settings.jwt_secret.strip()
    if not secret:
        raise TokenError("JWT_SECRET is not configured. Set it in your .env file.")
    return secret.encode()


def _jwt_verification_secrets() -> list[bytes]:
    primary = settings.jwt_secret.strip()
    if not primary:
        raise TokenError("JWT_SECRET is not configured. Set it in your .env file.")

    all_secrets = [primary, *_split_csv(settings.jwt_secret_fallbacks)]
    deduped = list(dict.fromkeys(all_secrets))
    return [secret.encode() for secret in deduped]


def _sign(header_b64: str, payload_b64: str, secret: bytes) -> str:
    msg = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(secret, msg, hashlib.sha256).digest()
    return _b64_encode(sig)


def _create_token(
    user_id: str,
    org_id: str,
    roles: set[str],
    token_type: str,
    ttl: int,
    token_version: int = 0,
) -> str:
    issued_at = int(time.time())
    header = _b64_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    claims: dict = {
        "sub": user_id,
        "org_id": org_id,
        "roles": sorted(roles),
        "type": token_type,
        "iat": issued_at,
        "exp": issued_at + ttl,
        "jti": uuid4().hex,
        "tv": token_version,
    }
    if settings.jwt_issuer:
        claims["iss"] = settings.jwt_issuer
    if settings.jwt_audience:
        claims["aud"] = settings.jwt_audience

    payload = _b64_encode(json.dumps(claims).encode())
    sig = _sign(header, payload, _jwt_signing_secret())
    return f"{header}.{payload}.{sig}"


def create_access_token(
    user_id: str,
    org_id: str,
    roles: set[str],
    token_version: int = 0,
) -> str:
    return _create_token(user_id, org_id, roles, "access", _ACCESS_TTL_SECONDS, token_version=token_version)


def create_refresh_token(
    user_id: str,
    org_id: str,
    roles: set[str],
    token_version: int = 0,
) -> str:
    return _create_token(user_id, org_id, roles, "refresh", _REFRESH_TTL_SECONDS, token_version=token_version)


def decode_token(token: str, *, expected_type: str = "access") -> TokenPayload:
    """
    Decode and validate a JWT. Raises TokenError on any failure.

    Validates: structure, signature, expiry, token type.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise TokenError("Malformed token: expected 3 parts.")

        header_b64, payload_b64, sig_b64 = parts
        valid_signature = any(
            hmac.compare_digest(_sign(header_b64, payload_b64, secret), sig_b64)
            for secret in _jwt_verification_secrets()
        )
        if not valid_signature:
            raise TokenError("Invalid token signature.")

        data = json.loads(_b64_decode(payload_b64))
    except (json.JSONDecodeError, Exception) as exc:
        raise TokenError(f"Could not decode token: {exc}") from exc

    now = int(time.time())
    skew = settings.jwt_clock_skew_seconds

    try:
        exp = int(data.get("exp", 0))
    except (TypeError, ValueError) as exc:
        raise TokenError("Invalid exp claim.") from exc
    if exp < now - skew:
        raise TokenError("Token has expired.")

    iat = data.get("iat")
    if iat is not None:
        try:
            iat_int = int(iat)
        except (TypeError, ValueError) as exc:
            raise TokenError("Invalid iat claim.") from exc
        if iat_int > now + skew:
            raise TokenError("Token issued-at is in the future.")

    if data.get("type") != expected_type:
        raise TokenError(
            f"Wrong token type: expected '{expected_type}', got '{data.get('type')}'."
        )

    if settings.jwt_issuer and data.get("iss") != settings.jwt_issuer:
        raise TokenError("Invalid token issuer.")

    if settings.jwt_audience:
        aud = data.get("aud")
        if isinstance(aud, list):
            if settings.jwt_audience not in aud:
                raise TokenError("Invalid token audience.")
        elif aud != settings.jwt_audience:
            raise TokenError("Invalid token audience.")

    try:
        return TokenPayload(
            sub=data["sub"],
            org_id=data.get("org_id", "default"),
            roles=set(data.get("roles", [])),
            token_type=data["type"],
            exp=exp,
            jti=data["jti"],
            token_version=int(data.get("tv", 0)),
        )
    except KeyError as exc:
        raise TokenError(f"Token missing required claim: {exc}") from exc
