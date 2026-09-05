"""Shared utilities — UUID / ID generation."""

from __future__ import annotations

import uuid


def new_id() -> str:
    """Generate a new UUID4 as a string."""
    return str(uuid.uuid4())


def is_valid_id(value: str) -> bool:
    """Return True if *value* is a valid UUID4 string."""
    try:
        uuid.UUID(value, version=4)
        return True
    except ValueError:
        return False
