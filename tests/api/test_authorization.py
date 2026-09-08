"""
Tests: Cross-user authorization matrix and discovery protection (MVP-7.3).

Verifies:
1. Strict resource ownership across all 6 resource families:
   - Profiles: GET /profiles/{id}
   - Roadmaps: GET /profiles/{id}/roadmaps, /latest, /{version}
   - Progress: GET/POST /profiles/{id}/progress
   - Feedback: POST /profiles/{id}/feedback
   - Adaptations: POST /profiles/{id}/adaptations/prepare
   - Knowledge: GET /profiles/{id}/knowledge/search
2. Discovery protection: 404 RESOURCE_NOT_FOUND indistinguishable from missing resource.
3. Unauthenticated requests rejected with 401 across all protected routes.
4. Client parameter tampering: user_id cannot be supplied/injected by client.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from roadmap.api.schemas.common import ErrorCode
from roadmap.security.tokens import create_access_token


@pytest.fixture
def multi_user_setup(unauthed_client: TestClient, user_factory):
    """Set up User A and User B each with their own profile and access headers."""
    user_a, headers_a = user_factory(email="user_a@roadmap.ai")
    user_b, headers_b = user_factory(email="user_b@roadmap.ai")

    body_a = {
        "name": "User Alpha",
        "target_goal": "Master Distributed Systems",
        "current_level": "familiar",
    }
    resp_a = unauthed_client.post("/api/v1/profiles", json=body_a, headers=headers_a)
    assert resp_a.status_code == 201
    profile_a_id = resp_a.json()["id"]

    body_b = {
        "name": "User Beta",
        "target_goal": "Master Machine Learning",
        "current_level": "proficient",
    }
    resp_b = unauthed_client.post("/api/v1/profiles", json=body_b, headers=headers_b)
    assert resp_b.status_code == 201
    profile_b_id = resp_b.json()["id"]

    return {
        "user_a": user_a,
        "headers_a": headers_a,
        "profile_a_id": profile_a_id,
        "user_b": user_b,
        "headers_b": headers_b,
        "profile_b_id": profile_b_id,
    }


# ===========================================================================
# 1. Cross-User Authorization Matrix: All 6 Resource Families
# ===========================================================================

def test_cross_user_profile_access_denied(unauthed_client: TestClient, multi_user_setup) -> None:
    """User A cannot access User B's profile; User B cannot access User A's profile."""
    headers_a = multi_user_setup["headers_a"]
    profile_b_id = multi_user_setup["profile_b_id"]
    headers_b = multi_user_setup["headers_b"]
    profile_a_id = multi_user_setup["profile_a_id"]

    # User A -> Profile B
    resp_a = unauthed_client.get(f"/api/v1/profiles/{profile_b_id}", headers=headers_a)
    assert resp_a.status_code == 404
    assert resp_a.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND

    # User B -> Profile A
    resp_b = unauthed_client.get(f"/api/v1/profiles/{profile_a_id}", headers=headers_b)
    assert resp_b.status_code == 404
    assert resp_b.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND

    # User A -> Profile A (allowed)
    resp_owner = unauthed_client.get(f"/api/v1/profiles/{profile_a_id}", headers=headers_a)
    assert resp_owner.status_code == 200
    assert resp_owner.json()["id"] == profile_a_id


def test_cross_user_roadmaps_access_denied(unauthed_client: TestClient, multi_user_setup) -> None:
    """User A cannot list or read User B's roadmaps."""
    headers_a = multi_user_setup["headers_a"]
    profile_b_id = multi_user_setup["profile_b_id"]

    # List roadmaps
    resp_list = unauthed_client.get(f"/api/v1/profiles/{profile_b_id}/roadmaps", headers=headers_a)
    assert resp_list.status_code == 404
    assert resp_list.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND

    # Latest roadmap
    resp_latest = unauthed_client.get(f"/api/v1/profiles/{profile_b_id}/roadmaps/latest", headers=headers_a)
    assert resp_latest.status_code == 404
    assert resp_latest.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND

    # Versioned roadmap
    resp_v1 = unauthed_client.get(f"/api/v1/profiles/{profile_b_id}/roadmaps/1", headers=headers_a)
    assert resp_v1.status_code == 404
    assert resp_v1.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND


def test_cross_user_progress_access_denied(unauthed_client: TestClient, multi_user_setup) -> None:
    """User A cannot list or record progress on User B's profile."""
    headers_a = multi_user_setup["headers_a"]
    profile_b_id = multi_user_setup["profile_b_id"]

    # List progress
    resp_list = unauthed_client.get(f"/api/v1/profiles/{profile_b_id}/progress", headers=headers_a)
    assert resp_list.status_code == 404
    assert resp_list.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND

    # Record progress
    body = {"skill_name": "Python", "completion_percentage": 50.0}
    resp_post = unauthed_client.post(
        f"/api/v1/profiles/{profile_b_id}/progress",
        json=body,
        headers=headers_a,
    )
    assert resp_post.status_code == 404
    assert resp_post.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND


def test_cross_user_feedback_access_denied(unauthed_client: TestClient, multi_user_setup) -> None:
    """User A cannot submit feedback for User B's profile."""
    headers_a = multi_user_setup["headers_a"]
    profile_b_id = multi_user_setup["profile_b_id"]

    body = {
        "skill_name": "Python",
        "difficulty": 3,
        "confidence": 3,
        "satisfaction": 3,
    }
    resp = unauthed_client.post(
        f"/api/v1/profiles/{profile_b_id}/feedback",
        json=body,
        headers=headers_a,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND


def test_cross_user_adaptation_access_denied(unauthed_client: TestClient, multi_user_setup) -> None:
    """User A cannot trigger adaptation proposals on User B's profile."""
    headers_a = multi_user_setup["headers_a"]
    profile_b_id = multi_user_setup["profile_b_id"]

    resp = unauthed_client.post(
        f"/api/v1/profiles/{profile_b_id}/adaptations/prepare",
        headers=headers_a,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND


def test_cross_user_knowledge_access_denied(unauthed_client: TestClient, multi_user_setup) -> None:
    """User A cannot run knowledge searches under User B's profile."""
    headers_a = multi_user_setup["headers_a"]
    profile_b_id = multi_user_setup["profile_b_id"]

    resp = unauthed_client.get(
        f"/api/v1/profiles/{profile_b_id}/knowledge/search",
        params={"query": "algorithms"},
        headers=headers_a,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND


# ===========================================================================
# 2. Ownership Binding & Parameter Tampering
# ===========================================================================

def test_client_cannot_supply_user_id_on_profile_creation(
    unauthed_client: TestClient,
    user_factory,
) -> None:
    """
    Even if the client sends a 'user_id' in the JSON body, the server must
    bind the profile strictly to the authenticated user from the token.
    """
    user_attacker, headers_attacker = user_factory(email="attacker@roadmap.ai")
    user_victim, _ = user_factory(email="victim@roadmap.ai")

    # Attacker attempts to forge profile for victim
    tampered_body = {
        "name": "Tampered Profile",
        "target_goal": "Tampered Target Goal",
        "user_id": user_victim.id,  # Attempted forgery
    }
    resp = unauthed_client.post("/api/v1/profiles", json=tampered_body, headers=headers_attacker)
    assert resp.status_code == 201
    profile_id = resp.json()["id"]

    # Profile must be accessible by attacker (the true owner)
    resp_attacker = unauthed_client.get(f"/api/v1/profiles/{profile_id}", headers=headers_attacker)
    assert resp_attacker.status_code == 200

    # Profile must NOT be accessible by victim
    token_victim = create_access_token(user_id=user_victim.id)
    headers_victim = {"Authorization": f"Bearer {token_victim}"}
    resp_victim = unauthed_client.get(f"/api/v1/profiles/{profile_id}", headers=headers_victim)
    assert resp_victim.status_code == 404
    assert resp_victim.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND


def test_user_cannot_create_multiple_profiles(
    unauthed_client: TestClient,
    user_factory,
) -> None:
    """A user can only have one active profile (409 Conflict on second creation)."""
    user, headers = user_factory(email="single@roadmap.ai")
    body = {
        "name": "First Profile",
        "target_goal": "First Goal Here",
    }
    resp1 = unauthed_client.post("/api/v1/profiles", json=body, headers=headers)
    assert resp1.status_code == 201

    body2 = {
        "name": "Second Profile",
        "target_goal": "Second Goal Here",
    }
    resp2 = unauthed_client.post("/api/v1/profiles", json=body2, headers=headers)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == ErrorCode.PROFILE_ALREADY_EXISTS


# ===========================================================================
# 3. Discovery Protection: Indistinguishability
# ===========================================================================

def test_discovery_protection_is_indistinguishable(
    unauthed_client: TestClient,
    multi_user_setup,
) -> None:
    """
    Querying a nonexistent profile ID versus an existing profile ID of another user
    must return the exact same HTTP status (404) and error code (RESOURCE_NOT_FOUND).
    """
    headers_a = multi_user_setup["headers_a"]
    profile_b_id = multi_user_setup["profile_b_id"]
    nonexistent_id = "completely-random-id-that-never-existed-000"

    resp_other_user = unauthed_client.get(f"/api/v1/profiles/{profile_b_id}", headers=headers_a)
    resp_nonexistent = unauthed_client.get(f"/api/v1/profiles/{nonexistent_id}", headers=headers_a)

    assert resp_other_user.status_code == resp_nonexistent.status_code == 404
    assert resp_other_user.json() == resp_nonexistent.json()
    assert resp_other_user.json()["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND


# ===========================================================================
# 4. Unauthenticated Access Protection
# ===========================================================================

@pytest.mark.parametrize(
    "method,path,json_body",
    [
        ("GET", "/api/v1/profiles/any-id", None),
        ("POST", "/api/v1/profiles", {"name": "Anon", "target_goal": "Goal here"}),
        ("GET", "/api/v1/profiles/any-id/roadmaps", None),
        ("GET", "/api/v1/profiles/any-id/roadmaps/latest", None),
        ("GET", "/api/v1/profiles/any-id/roadmaps/1", None),
        ("GET", "/api/v1/profiles/any-id/progress", None),
        ("POST", "/api/v1/profiles/any-id/progress", {"skill_name": "P", "completion_percentage": 10.0}),
        ("POST", "/api/v1/profiles/any-id/feedback", {"skill_name": "P", "difficulty": 1, "confidence": 1, "satisfaction": 1}),
        ("POST", "/api/v1/profiles/any-id/adaptations/prepare", None),
        ("GET", "/api/v1/profiles/any-id/knowledge/search?query=test", None),
    ],
)
def test_all_protected_endpoints_require_authentication(
    unauthed_client: TestClient,
    method: str,
    path: str,
    json_body: dict | None,
) -> None:
    """Every protected endpoint returns 401 AUTHENTICATION_REQUIRED when called with no credentials."""
    if method == "GET":
        resp = unauthed_client.get(path)
    elif method == "POST":
        resp = unauthed_client.post(path, json=json_body)
    else:
        pytest.fail(f"Unsupported method {method}")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.AUTHENTICATION_REQUIRED
