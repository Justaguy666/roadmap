"""Integration tests verifying workflow budget limits and batch clamping."""


import pytest

from roadmap.application.ports.llm_provider import ApplicationBudgetExceededError
from roadmap.application.services.llm_budget_manager import LLMBudgetManager
from roadmap.domain.value_objects.enums import LLMWorkflow
from tests.unit.test_llm_budget_manager import InMemoryLLMUsageRepository


def test_research_batch_budget_clamping_logic() -> None:
    repo = InMemoryLLMUsageRepository()
    # Research budget: 3 calls max
    # Suppose 1 call was used for query planning
    mgr = LLMBudgetManager(repository=repo, daily_budget=10, workflow_budgets={LLMWorkflow.RESEARCH: 3})

    # Plan query
    r_plan = mgr.reserve(LLMWorkflow.RESEARCH, operation="query_planning", estimated_requests=1)
    mgr.commit(r_plan, success=True, actual_requests=1)

    # Remaining research budget: 3 - 1 = 2
    status = mgr.get_quota_status()
    remaining = status.workflow_budgets[LLMWorkflow.RESEARCH].remaining
    assert remaining == 2

    # If we have 10 candidate extraction batches, we should only take up to remaining budget (2 batches)
    candidate_batches = [f"batch_{i}" for i in range(10)]
    clamped_batches = candidate_batches[:remaining]
    assert len(clamped_batches) == 2

    # Reserve and run those 2
    for _b in clamped_batches:
        res = mgr.reserve(LLMWorkflow.RESEARCH, operation="batch_extract", estimated_requests=1)
        mgr.commit(res, success=True, actual_requests=1)

    # Now research budget is fully consumed
    assert mgr.get_quota_status().workflow_budgets[LLMWorkflow.RESEARCH].remaining == 0

    # Any additional reservation raises ApplicationBudgetExceededError
    with pytest.raises(ApplicationBudgetExceededError):
        mgr.reserve(LLMWorkflow.RESEARCH, operation="batch_extract", estimated_requests=1)


def test_generation_fast_fails_when_budget_exhausted() -> None:
    repo = InMemoryLLMUsageRepository()
    mgr = LLMBudgetManager(repository=repo, daily_budget=10, workflow_budgets={LLMWorkflow.GENERATION: 1})

    # 1 call used
    r1 = mgr.reserve(LLMWorkflow.GENERATION, operation="generate_candidate", estimated_requests=1)
    mgr.commit(r1, success=True, actual_requests=1)

    # Next generation attempt immediately fails deterministically without calling LLM provider
    with pytest.raises(ApplicationBudgetExceededError) as exc:
        mgr.reserve(LLMWorkflow.GENERATION, operation="generate_candidate", estimated_requests=1)

    assert exc.value.workflow == "generation"
    assert exc.value.allocated == 1
    assert exc.value.used == 1
