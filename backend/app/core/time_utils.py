from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """
    Return a naive datetime that represents UTC now.

    We keep it naive to preserve existing DB/API behavior while avoiding
    deprecated datetime.utcnow().
    """
    return datetime.now(UTC).replace(tzinfo=None)
