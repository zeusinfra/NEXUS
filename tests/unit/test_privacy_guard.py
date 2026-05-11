"""Tests for the Privacy Guard."""

import pytest
from zeus_core.cognitive.cognitive_db import init_cognitive_tables
from zeus_core.security.privacy_guard import PrivacyGuard, PrivacyLevel


@pytest.fixture
def guard(tmp_path):
    db = str(tmp_path / "test_privacy.db")
    init_cognitive_tables(db)
    return PrivacyGuard(db_path=db)


class TestPrivacyGuard:
    def test_classification_public(self, guard):
        assert guard.classify_content("Hello") == PrivacyLevel.PUBLIC

    def test_classification_sensitive(self, guard):
        assert (
            guard.classify_content("My long note about systems")
            == PrivacyLevel.LOCAL_SENSITIVE
        )

    def test_classification_highly_sensitive(self, guard):
        assert (
            guard.classify_content("Detected user habits for the day")
            == PrivacyLevel.HIGHLY_SENSITIVE
        )
        assert (
            guard.classify_content("Path: /home/zeus/.ssh/id_rsa")
            == PrivacyLevel.HIGHLY_SENSITIVE
        )

    def test_classification_secret(self, guard):
        # OpenAI Key
        assert (
            guard.classify_content(
                "Key: sk-abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234"
            )
            == PrivacyLevel.SECRET
        )
        # Generic Secret
        assert (
            guard.classify_content("API_KEY='supersecretpassword'")
            == PrivacyLevel.SECRET
        )

    def test_sanitize(self, guard):
        content = "My key is sk-abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234"
        sanitized = guard.sanitize(content)
        assert "sk-" not in sanitized
        assert "[MASKED_OPENAI_KEY]" in sanitized

    def test_validate_export_local(self, guard):
        # Local exports always allowed (for now)
        res = guard.validate_export("My habits", "local")
        assert res.allowed is True
        assert res.action == "allowed"

    def test_validate_export_secret_cloud(self, guard):
        # Secrets should be sanitized for cloud
        content = "Key: sk-abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234"
        res = guard.validate_export(content, "openai")
        assert res.allowed is True
        assert res.action == "sanitized"
        assert "[MASKED_OPENAI_KEY]" in res.sanitized_content

    def test_validate_export_sensitive_no_consent(self, guard):
        # Highly sensitive blocked if no consent
        content = "Detailed user workflows observed"
        res = guard.validate_export(content, "notion")
        assert res.allowed is False
        assert res.action == "blocked"

    def test_consent_flow(self, guard):
        resource = "export_notion"
        assert guard.check_consent(resource) is False

        guard.grant_consent(resource, scope="session")
        assert guard.check_consent(resource) is True

        # Validate export now allowed
        res = guard.validate_export("User workflows", "notion")
        assert res.allowed is True

        guard.revoke_consent(resource)
        assert guard.check_consent(resource) is False

    def test_audit_logs(self, guard):
        guard.validate_export(
            "Secret sk-abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234", "gemini"
        )
        logs = guard.get_audit_logs()
        assert len(logs) >= 1
        assert logs[0]["action"] == "sanitized"
