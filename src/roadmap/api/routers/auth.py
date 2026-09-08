"""Authentication endpoints: POST /register, POST /login, GET /me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from roadmap.api.dependencies import (
    get_authenticate_user_use_case,
    get_current_user,
    get_register_user_use_case,
)
from roadmap.api.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from roadmap.api.schemas.common import ErrorCode
from roadmap.application.use_cases.auth_use_cases import (
    AuthenticateUserRequest,
    AuthenticateUserUseCase,
    RegisterUserRequest,
    RegisterUserUseCase,
)
from roadmap.domain.entities.user import User
from roadmap.domain.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    ValidationError,
)
from roadmap.security.tokens import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user account with email and password.",
    responses={
        201: {"description": "User created successfully"},
        400: {"description": "Validation error or weak password"},
        409: {"description": "Email already registered"},
    },
)
def register(
    body: UserRegisterRequest,
    use_case: RegisterUserUseCase = Depends(get_register_user_use_case),
) -> UserResponse:
    """Register a new user account."""
    try:
        user = use_case.execute(RegisterUserRequest(email=body.email, password=body.password))
        return UserResponse(
            id=user.id,
            email=user.email,
            status=user.status,
            created_at=user.created_at,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": ErrorCode.EMAIL_ALREADY_REGISTERED, "message": str(exc)}},
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": ErrorCode.BAD_REQUEST, "message": str(exc)}},
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and obtain access token",
    description="Authenticates user credentials and returns a signed bearer JWT access token.",
    responses={
        200: {"description": "Authentication successful"},
        401: {"description": "Invalid credentials"},
    },
)
def login(
    body: UserLoginRequest,
    use_case: AuthenticateUserUseCase = Depends(get_authenticate_user_use_case),
) -> TokenResponse:
    """Authenticate credentials and generate JWT access token."""
    try:
        user = use_case.execute(AuthenticateUserRequest(email=body.email, password=body.password))
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": ErrorCode.INVALID_CREDENTIALS, "message": str(exc)}},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    access_token = create_access_token(user_id=user.id)
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user identity",
    description="Returns the identity of the currently authenticated user.",
    responses={
        200: {"description": "Current user identity"},
        401: {"description": "Authentication required or invalid token"},
    },
)
def me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the authenticated user's account details."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        status=current_user.status,
        created_at=current_user.created_at,
    )
