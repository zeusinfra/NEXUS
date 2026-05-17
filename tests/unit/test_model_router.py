from nexus_core.model_router import ModelRouter


def test_short_low_risk_task_routes_to_local():
    decision = ModelRouter().classify("resuma estes logs")

    assert decision.complexity == "simple"
    assert decision.route == "local"
    assert decision.reviewer_required is False
    assert decision.approval_required is False


def test_architecture_task_routes_to_cloud():
    decision = ModelRouter().classify(
        "planejar arquitetura multi-arquivo para pacote .deb"
    )

    assert decision.complexity == "complex"
    assert decision.route == "cloud"
    assert decision.reviewer_required is True


def test_sudo_task_requires_cloud_and_approval():
    decision = ModelRouter().classify("sudo systemctl restart nexus")

    assert decision.complexity == "critical"
    assert decision.route == "cloud"
    assert decision.approval_required is True


def test_blocked_destructive_pattern_is_critical():
    decision = ModelRouter().classify("rm -rf /")

    assert decision.complexity == "critical"
    assert decision.risk == "critical"
    assert decision.approval_required is True
    assert "blocked" in decision.reason
