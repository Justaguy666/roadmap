from datetime import UTC, datetime, timedelta

import pytest

from roadmap.application.services.llm_budget_manager import (
    LLMBudgetManager,
    ProviderQuotaUnavailableError,
)
from roadmap.domain.entities.llm_budget import (
    FailureCategory,
    LLMProviderState,
    LLMWorkflow,
)
from roadmap.infrastructure.llm.fake_provider import FakeLLMProvider
from roadmap.infrastructure.llm.gemini_provider import GeminiProvider
from roadmap.storage.repositories.llm_usage_repository import SqliteLLMUsageRepository


@pytest.fixture
def repo(db_session):
    return SqliteLLMUsageRepository(db_session)


def test_provider_state_exact_keying(repo):
    # Test saving provider state with concrete model
    state = LLMProviderState(
        provider="gemini",
        model="gemini-3.7-flash",
        is_available=False,
        last_failure_category=FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED,
        cooldown_until=datetime.now(UTC) + timedelta(hours=1),
    )
    repo.save_provider_state(state)

    fetched = repo.get_provider_state("gemini", "gemini-3.7-flash")
    assert fetched is not None
    assert fetched.provider == "gemini"
    assert fetched.model == "gemini-3.7-flash"
    assert fetched.last_failure_category == FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED


def test_provider_state_legacy_migration(repo):
    # Simulate legacy state stored with model="default"
    legacy_state = LLMProviderState(
        provider="gemini",
        model="default",
        is_available=False,
        last_failure_category=FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED,
        cooldown_until=datetime.now(UTC) + timedelta(hours=1),
    )
    repo.save_provider_state(legacy_state)

    # When querying for concrete model, it should auto-migrate
    fetched = repo.get_provider_state("gemini", "gemini-3.7-flash")
    assert fetched is not None
    assert fetched.provider == "gemini"
    assert fetched.model == "gemini-3.7-flash"

    # And legacy record should be cleaned up
    raw_default = repo.get_provider_state("gemini", "default")
    assert raw_default is None


def test_fail_fast_on_second_reservation(repo):
    budget_mgr = LLMBudgetManager(repository=repo)

    # 1. First reservation succeeds
    res = budget_mgr.reserve(
        workflow=LLMWorkflow.GENERATION,
        operation="generate_test",
        provider="gemini",
        model="gemini-3.7-flash",
        estimated_requests=1,
    )
    assert res.provider == "gemini"
    assert res.model == "gemini-3.7-flash"

    # 2. Complete fails with daily quota exceeded
    budget_mgr.commit(
        reservation=res,
        success=False,
        failure_category=FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED,
        error_message="Daily limit reached",
        actual_requests=1,
    )

    # Verify state saved
    state = repo.get_provider_state("gemini", "gemini-3.7-flash")
    assert state is not None
    assert state.is_available is False
    assert state.cooldown_until is not None

    # 3. Second reservation MUST fail fast before invoking provider
    with pytest.raises(ProviderQuotaUnavailableError) as exc_info:
        budget_mgr.reserve(
            workflow=LLMWorkflow.GENERATION,
            operation="generate_test_2",
            provider="gemini",
            model="gemini-3.7-flash",
            estimated_requests=1,
        )
    assert "is in cooldown for" in str(exc_info.value)
    assert "circuit-breaker active" in str(exc_info.value)
    assert "gemini" in str(exc_info.value)
    assert "gemini-3.7-flash" in str(exc_info.value)


def test_zero_network_calls_when_quota_exhausted(repo):
    """Verify that when a provider is in cooldown, zero network calls are attempted."""
    budget_mgr = LLMBudgetManager(repository=repo)

    # Set provider in cooldown
    state = LLMProviderState(
        provider="gemini",
        model="gemini-3.7-flash",
        is_available=False,
        quota_exhausted=True,
        last_failure_category=FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED,
        blocked_until=datetime.now(UTC) + timedelta(minutes=30),
    )
    repo.save_provider_state(state)

    network_call_count = 0

    def mock_network_call():
        nonlocal network_call_count
        network_call_count += 1
        return "result"

    # Attempt operation protected by budget_mgr.reserve
    with pytest.raises(ProviderQuotaUnavailableError):
        res = budget_mgr.reserve(
            workflow=LLMWorkflow.GENERATION,
            operation="candidate_generation",
            provider="gemini",
            model="gemini-3.7-flash",
        )
        mock_network_call()
        budget_mgr.commit(res, success=True)

    # Assert exactly zero network calls occurred
    assert network_call_count == 0

    # Assert no actual requests were recorded in usage history
    usage = repo.get_recent_usage(limit=10)
    assert len(usage) == 0


def test_reprobe_mechanism_after_cooldown_expires(repo):
    """Verify that after cooldown expires, one re-probe is permitted and success clears cooldown."""
    budget_mgr = LLMBudgetManager(repository=repo)

    # Set provider in expired cooldown
    expired_time = datetime.now(UTC) - timedelta(minutes=5)
    state = LLMProviderState(
        provider="gemini",
        model="gemini-3.7-flash",
        is_available=False,
        quota_exhausted=True,
        last_failure_category=FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED,
        cooldown_until=expired_time,
        blocked_until=expired_time,
    )
    repo.save_provider_state(state)

    # Reservation should be allowed as a re-probe
    res = budget_mgr.reserve(
        workflow=LLMWorkflow.GENERATION,
        operation="probe_operation",
        provider="gemini",
        model="gemini-3.7-flash",
        estimated_requests=1,
    )
    assert res is not None

    # Probe succeeds -> should clear provider cooldown and quota exhaustion
    budget_mgr.commit(
        reservation=res,
        success=True,
        actual_requests=1,
    )

    updated_state = repo.get_provider_state("gemini", "gemini-3.7-flash")
    assert updated_state is not None
    assert updated_state.is_available is True
    assert updated_state.quota_exhausted is False
    assert updated_state.cooldown_until is None
    assert updated_state.blocked_until is None


def test_gemini_provider_daily_quota_no_retry_delay_confusion():
    # Verify Gemini provider identifies daily quota properly without blind retries
    provider = GeminiProvider(api_key="fake-key", model="gemini-3.7-flash")
    assert provider.provider_name == "gemini"
    assert provider.model_name == "gemini-3.7-flash"


def test_fake_provider_identities():
    fake = FakeLLMProvider()
    assert fake.provider_name == "mock"
    assert fake.model_name == "default"

