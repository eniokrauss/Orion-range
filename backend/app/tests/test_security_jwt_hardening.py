from __future__ import annotations

import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode

import pytest

from app.core.config import settings
from app.core.security import TokenError, create_access_token, decode_token


def _b64(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    return urlsafe_b64decode(data + "=" * (padding % 4))


def _build_token(secret: str, claims: dict) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps(claims).encode())
    sig = hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64(sig)}"


def _claims(**overrides) -> dict:
    now = int(time.time())
    base = {
        "sub": "user-1",
        "org_id": "default",
        "roles": ["range_admin"],
        "type": "access",
        "iat": now,
        "exp": now + 300,
        "jti": "token-1",
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def jwt_settings():
    original_secret = settings.jwt_secret
    original_fallbacks = settings.jwt_secret_fallbacks
    original_issuer = settings.jwt_issuer
    original_audience = settings.jwt_audience
    original_clock_skew = settings.jwt_clock_skew_seconds

    settings.jwt_secret = "primary-secret"
    settings.jwt_secret_fallbacks = ""
    settings.jwt_issuer = ""
    settings.jwt_audience = ""
    settings.jwt_clock_skew_seconds = 30

    yield

    settings.jwt_secret = original_secret
    settings.jwt_secret_fallbacks = original_fallbacks
    settings.jwt_issuer = original_issuer
    settings.jwt_audience = original_audience
    settings.jwt_clock_skew_seconds = original_clock_skew


def test_decode_accepts_fallback_secret():
    settings.jwt_secret = "new-secret"
    settings.jwt_secret_fallbacks = "old-secret"
    token = _build_token("old-secret", _claims())

    decoded = decode_token(token, expected_type="access")

    assert decoded.sub == "user-1"


def test_decode_rejects_wrong_issuer_when_configured():
    settings.jwt_issuer = "orion-core"
    token = _build_token("primary-secret", _claims(iss="other-issuer"))

    with pytest.raises(TokenError, match="issuer"):
        decode_token(token, expected_type="access")


def test_decode_rejects_wrong_audience_when_configured():
    settings.jwt_audience = "orion-api"
    token = _build_token("primary-secret", _claims(aud="other-aud"))

    with pytest.raises(TokenError, match="audience"):
        decode_token(token, expected_type="access")


def test_create_token_includes_configured_issuer_and_audience():
    settings.jwt_issuer = "orion-core"
    settings.jwt_audience = "orion-api"

    token = create_access_token("user-1", "default", {"range_admin"})
    payload_b64 = token.split(".")[1]
    payload = json.loads(_b64_decode(payload_b64))

    assert payload["iss"] == "orion-core"
    assert payload["aud"] == "orion-api"
    decode_token(token, expected_type="access")


def test_decode_rejects_token_with_future_iat_beyond_clock_skew():
    settings.jwt_clock_skew_seconds = 0
    token = _build_token("primary-secret", _claims(iat=int(time.time()) + 120))

    with pytest.raises(TokenError, match="future"):
        decode_token(token, expected_type="access")
