"""Stateless JWT access token utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from roadmap.config.settings import settings
from roadmap.domain.exceptions import AuthenticationError


class TokenExpiredError(AuthenticationError):
    """Raised when access token has expired."""


class InvalidTokenError(AuthenticationError):
    """Raised when access token signature, algorithm, or payload is invalid."""


def create_access_token(
    user_id: str,
    expires_delta: timedelta | None = None,
    secret: str | None = None,
    algorithm: str | None = None,
) -> str:
    """Create a signed bearer JWT access token containing only minimal identity claims."""
    now = datetime.now(UTC)
    expire_minutes = settings.auth_access_token_expire_minutes
    expire_duration = expires_delta if expires_delta is not None else timedelta(minutes=expire_minutes)
    expire_at = now + expire_duration

    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire_at.timestamp()),
    }

    signing_secret = secret or settings.auth_secret
    signing_algo = algorithm or settings.auth_algorithm

    return jwt.encode(payload, signing_secret, algorithm=signing_algo)


def decode_access_token(
    token: str,
    secret: str | None = None,
    algorithm: str | None = None,
) -> dict[str, Any]:
    """
    Decode and validate a bearer JWT access token.

    Enforces:
    - Signature verification
    - Configured algorithm allowlist (rejects arbitrary/none algorithms)
    - Expiration (exp)
    - Not-before (nbf)
    - Required subject (sub)
    """
    signing_secret = secret or settings.auth_secret
    expected_algo = algorithm or settings.auth_algorithm

    try:
        payload = jwt.decode(
            token,
            signing_secret,
            algorithms=[expected_algo],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Invalid token.") from exc

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str) or not sub.strip():
        raise InvalidTokenError("Token payload missing valid subject.")

    return payload
