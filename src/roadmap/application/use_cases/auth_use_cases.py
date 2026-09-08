"""Application use cases for user authentication and registration."""

from __future__ import annotations

import re
from dataclasses import dataclass

from roadmap.application.ports.repositories import UserRepository
from roadmap.domain.entities.user import User
from roadmap.domain.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    ValidationError,
)
from roadmap.security.password import hash_password, validate_password_strength, verify_password
from roadmap.shared.ids import new_id
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    """Canonicalize email by stripping leading/trailing whitespace and lowercasing."""
    if not email or not email.strip():
        raise ValidationError("email", "Email address cannot be empty.")
    normalized = email.strip().lower()
    if not _EMAIL_REGEX.match(normalized):
        raise ValidationError("email", f"Invalid email address format: {email!r}")
    return normalized


@dataclass
class RegisterUserRequest:
    email: str
    password: str


class RegisterUserUseCase:
    """Register a new user account with hashed credentials."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def execute(self, request: RegisterUserRequest) -> User:
        canonical_email = normalize_email(request.email)
        validate_password_strength(request.password)

        existing = self._user_repo.get_by_email(canonical_email)
        if existing is not None:
            raise UserAlreadyExistsError(f"A user with email '{canonical_email}' is already registered.")

        pw_hash = hash_password(request.password)
        user = User(
            id=new_id(),
            email=canonical_email,
            password_hash=pw_hash,
            status="active",
        )
        self._user_repo.save(user)
        logger.info("User registered", user_id=user.id)
        return user


@dataclass
class AuthenticateUserRequest:
    email: str
    password: str


class AuthenticateUserUseCase:
    """Authenticate user credentials in constant-time and return user identity."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def execute(self, request: AuthenticateUserRequest) -> User:
        # Canonicalize email; if malformed, still do dummy check to protect timing
        try:
            canonical_email = normalize_email(request.email)
        except ValidationError:
            canonical_email = ""

        user = self._user_repo.get_by_email(canonical_email) if canonical_email else None

        # Dummy password check to prevent timing attacks when user does not exist
        dummy_hash = "$2b$12$e898492049182390182390e898492049182390182390e89849204"
        valid = False
        if user is not None:
            valid = verify_password(request.password, user.password_hash)
        else:
            verify_password(request.password, dummy_hash)

        if not valid or user is None:
            # Generic response: never disclose whether email exists
            raise InvalidCredentialsError("Invalid email or password.")

        if not user.is_active:
            raise InvalidCredentialsError("User account is inactive or disabled.")

        logger.info("User authenticated", user_id=user.id)
        return user
