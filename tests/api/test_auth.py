"""Tests: Authentication endpoints (/auth/register, /auth/login, /auth/me)."""

from __future__ import annotations

from datetime import timedelta

import jwt
from fastapi.testclient import TestClient

from roadmap.api.schemas.common import ErrorCode
from roadmap.security.tokens import create_access_token


def test_register_success(unauthed_client: TestClient) -> None:
    resp = unauthed_client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@roadmap.ai", "password": "StrongPassword123!"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@roadmap.ai"
    assert data["status"] == "active"
    assert "id" in data
    assert "created_at" in data
    # Guarantee password/hash is never exposed
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_email_conflict(unauthed_client: TestClient) -> None:
    unauthed_client.post(
        "/api/v1/auth/register",
        json={"email": "dup@roadmap.ai", "password": "StrongPassword123!"},
    )
    resp = unauthed_client.post(
        "/api/v1/auth/register",
        json={"email": "dup@roadmap.ai", "password": "StrongPassword123!"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == ErrorCode.EMAIL_ALREADY_REGISTERED


def test_register_duplicate_email_case_insensitive(unauthed_client: TestClient) -> None:
    unauthed_client.post(
        "/api/v1/auth/register",
        json={"email": "case.user@roadmap.ai", "password": "StrongPassword123!"},
    )
    resp = unauthed_client.post(
        "/api/v1/auth/register",
        json={"email": "CASE.USER@ROADMAP.AI", "password": "StrongPassword123!"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == ErrorCode.EMAIL_ALREADY_REGISTERED


def test_register_weak_password_rejected(unauthed_client: TestClient) -> None:
    resp = unauthed_client.post(
        "/api/v1/auth/register",
        json={"email": "weak@roadmap.ai", "password": "short"},
    )
    assert resp.status_code in (400, 422)


def test_login_success(unauthed_client: TestClient) -> None:
    unauthed_client.post(
        "/api/v1/auth/register",
        json={"email": "loginuser@roadmap.ai", "password": "StrongPassword123!"},
    )
    resp = unauthed_client.post(
        "/api/v1/auth/login",
        json={"email": "loginuser@roadmap.ai", "password": "StrongPassword123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


def test_login_case_insensitive_email(unauthed_client: TestClient) -> None:
    unauthed_client.post(
        "/api/v1/auth/register",
        json={"email": "mixed@roadmap.ai", "password": "StrongPassword123!"},
    )
    resp = unauthed_client.post(
        "/api/v1/auth/login",
        json={"email": "MIXED@ROADMAP.AI", "password": "StrongPassword123!"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_invalid_password(unauthed_client: TestClient) -> None:
    unauthed_client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@roadmap.ai", "password": "StrongPassword123!"},
    )
    resp = unauthed_client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@roadmap.ai", "password": "IncorrectPassword999!"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.INVALID_CREDENTIALS


def test_login_nonexistent_user(unauthed_client: TestClient) -> None:
    resp = unauthed_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@roadmap.ai", "password": "AnyPassword123!"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.INVALID_CREDENTIALS


def test_me_authenticated(unauthed_client: TestClient) -> None:
    reg = unauthed_client.post(
        "/api/v1/auth/register",
        json={"email": "me@roadmap.ai", "password": "StrongPassword123!"},
    )
    user_id = reg.json()["id"]

    login = unauthed_client.post(
        "/api/v1/auth/login",
        json={"email": "me@roadmap.ai", "password": "StrongPassword123!"},
    )
    token = login.json()["access_token"]

    resp = unauthed_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == user_id
    assert data["email"] == "me@roadmap.ai"
    assert data["status"] == "active"


def test_me_unauthenticated_rejected(unauthed_client: TestClient) -> None:
    resp = unauthed_client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.AUTHENTICATION_REQUIRED


def test_me_expired_token_rejected(unauthed_client: TestClient, user_factory) -> None:
    user, _ = user_factory(email="expired@roadmap.ai")
    # Token expired 1 hour ago
    expired_token = create_access_token(user_id=user.id, expires_delta=timedelta(hours=-1))
    resp = unauthed_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.TOKEN_EXPIRED


def test_me_invalid_token_rejected(unauthed_client: TestClient) -> None:
    resp = unauthed_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.INVALID_TOKEN


def test_me_algorithm_tampering_rejected(unauthed_client: TestClient, user_factory) -> None:
    user, _ = user_factory(email="tamper@roadmap.ai")
    # Generate token with "none" algorithm
    tampered_token = jwt.encode({"sub": user.id, "iat": 1000, "exp": 9999999999}, "", algorithm="none")
    resp = unauthed_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.INVALID_TOKEN


def test_inactive_user_cannot_login(unauthed_client: TestClient, user_factory) -> None:
    user, _ = user_factory(email="inactive@roadmap.ai", status="suspended")
    resp = unauthed_client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@roadmap.ai", "password": "SecurePassword123!"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.INVALID_CREDENTIALS


def test_inactive_user_token_rejected_at_me(unauthed_client: TestClient, user_factory) -> None:
    user, headers = user_factory(email="suspended@roadmap.ai", status="suspended")
    resp = unauthed_client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.INVALID_TOKEN
