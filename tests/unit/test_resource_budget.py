from __future__ import annotations

from nexus_core.organization.resource_budget import (
    ExecutionBudget,
    ResourceBudgetGovernor,
)


def test_resource_budget_caps_timeout_and_blocks_concurrency():
    governor = ResourceBudgetGovernor(
        ExecutionBudget(
            concurrent_task_limit=1,
            timeout_max_s=10,
            token_budget=100,
            cpu_soft_limit_percent=100,
            ram_soft_limit_percent=100,
        )
    )

    allowed = governor.assess(active_executions=0, requested_timeout_s=30)
    blocked = governor.assess(active_executions=1, requested_timeout_s=5)

    assert allowed["allowed"] is True
    assert allowed["effective_timeout_s"] == 10
    assert blocked["allowed"] is False
    assert "concurrent task limit" in blocked["reasons"][0]
