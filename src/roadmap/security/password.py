"""Password hashing and validation utilities."""

from __future__ import annotations

import bcrypt

from roadmap.domain.exceptions import ValidationError

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def validate_password_strength(password: str) -> None:
    """Validate password length and basic sanity."""
    if not password or len(password.strip()) == 0:
        raise ValidationError("password", "Password cannot be empty or whitespace only.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            "password",
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.",
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValidationError(
            "password",
            f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters.",
        )


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with salt."""
    validate_password_strength(password)
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash in constant time."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False
