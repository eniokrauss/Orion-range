from hmac import compare_digest

from fastapi import Header

from app.core.config import settings
from app.core.errors import ErrorCode, http_error


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    configured_key = settings.api_key
    if not configured_key:
        return

    if x_api_key and compare_digest(x_api_key, configured_key):
        return

    raise http_error(
        status_code=401,
        code=ErrorCode.UNAUTHORIZED,
        message="Invalid or missing API key.",
    )
