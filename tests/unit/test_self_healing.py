from nexus_core.cognitive.self_healing import HealingProposal, SelfHealingEngine


def test_self_healing_blocks_shell_control_commands():
    engine = SelfHealingEngine()
    proposal = HealingProposal(
        issue="test",
        rationale="ensure shell chaining is blocked",
        commands=["echo ok && echo unsafe"],
        risk="low",
    )

    assert engine.apply_fix(proposal) is False


def test_self_healing_runs_policy_allowed_low_risk_command():
    engine = SelfHealingEngine()
    proposal = HealingProposal(
        issue="test",
        rationale="allow simple read-only command",
        commands=["echo ok"],
        risk="low",
    )

    assert engine.apply_fix(proposal) is True
