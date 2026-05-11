"""
ZEUS Cognitive Core — Privacy Guard.

Manages data classification, user consent, and export filtering.
Ensures no sensitive data (tokens, .env, private habits) is exported
to external services without explicit permission.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import IntEnum
from typing import Any

from zeus_core.cognitive.cognitive_db import get_connection
from zeus_core.observability import get_logger, log_event

logger = get_logger("zeus.security.privacy")

# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------


class PrivacyLevel(IntEnum):
    PUBLIC = 0
    LOCAL_SENSITIVE = 1
    HIGHLY_SENSITIVE = 2
    SECRET = 3


@dataclass
class ValidationResult:
    allowed: bool
    action: str  # 'allowed' | 'blocked' | 'sanitized'
    level: PrivacyLevel
    reason: str | None = None
    sanitized_content: str | None = None


# ------------------------------------------------------------------
# Regex Patterns for Sensitive Data
# ------------------------------------------------------------------

SECRET_PATTERNS = {
    "openai_key": r"sk-[a-zA-Z0-9]{48}",
    "generic_key": r"(?i)(api[_-]?key|secret|password|token)['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9]{16,})['\"]?",
    "env_file": r"(?m)^[A-Z_]+=[^\n]+$",
    "auth_header": r"(?i)Authorization:\s*(Bearer|Basic)\s+[a-zA-Z0-9\._\-+/=]+",
}

SENSITIVE_PATHS = [
    r"\.ssh/",
    r"\.env",
    r"\.aws/",
    r"config/.*secret",
    r"zeus_events\.db",
]

# ------------------------------------------------------------------
# Privacy Guard Logic
# ------------------------------------------------------------------

try:
    from zeus_security import PrivacyEngineRust

    RUST_SECURITY_AVAILABLE = True
except ImportError:
    RUST_SECURITY_AVAILABLE = False


class PrivacyGuard:
    """The central engine for privacy protection."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path
        # Global privacy mode: 'balanced' | 'strict' | 'local_only'
        self.mode = os.getenv("ZEUS_PRIVACY_MODE", "balanced").lower()
        self.session_masked_count = 0

        if RUST_SECURITY_AVAILABLE:
            self.rust_engine = PrivacyEngineRust()
            logger.info("🦀 ZEUS: Privacy Guard operando com motor Rust otimizado.")
        else:
            self.rust_engine = None
            logger.warning("🐍 ZEUS: Privacy Guard operando em modo Python (fallback).")

    def classify_content(self, content: str) -> PrivacyLevel:
        """Analyze content and return its highest privacy level."""
        if not content:
            return PrivacyLevel.PUBLIC

        if self.rust_engine:
            level_int = self.rust_engine.classify(content)
            return PrivacyLevel(level_int)

        # Check for SECRET patterns
        for name, pattern in SECRET_PATTERNS.items():
            if re.search(pattern, content):
                return PrivacyLevel.SECRET

        # Check for HIGHLY_SENSITIVE patterns (paths, user habits mentioned)
        for path in SENSITIVE_PATHS:
            if re.search(path, content):
                return PrivacyLevel.HIGHLY_SENSITIVE

        if "habits" in content.lower() or "workflow" in content.lower():
            if "detected" in content.lower() or "observed" in content.lower():
                return PrivacyLevel.HIGHLY_SENSITIVE

        # Check for LOCAL_SENSITIVE (generic chat/notes)
        if len(content) > 10:
            return PrivacyLevel.LOCAL_SENSITIVE

        return PrivacyLevel.PUBLIC

    def validate_export(self, content: str, destination: str) -> ValidationResult:
        """
        Validate if content can be exported to a specific destination.
        Returns ValidationResult with 'allowed', 'action', and 'sanitized_content'.
        """
        level = self.classify_content(content)
        dest_type = self._get_destination_type(destination)

        # 1. SECRET level is NEVER allowed raw to external
        if level == PrivacyLevel.SECRET:
            if dest_type == "local":
                return ValidationResult(True, "allowed", level)

            # Attempt to sanitize
            sanitized = self.sanitize(content)
            self._audit(
                "export_attempt",
                destination,
                "sanitized",
                level,
                "Masked SECRET patterns",
            )
            return ValidationResult(
                True, "sanitized", level, "Secrets masked", sanitized
            )

        # 2. HIGHLY_SENSITIVE requires explicit consent for external
        if level == PrivacyLevel.HIGHLY_SENSITIVE:
            if dest_type == "local":
                return ValidationResult(True, "allowed", level)

            if self.check_consent(f"export_{destination}"):
                return ValidationResult(True, "allowed", level)

            self._audit(
                "export_attempt",
                destination,
                "blocked",
                level,
                "Requires explicit consent",
            )
            return ValidationResult(
                False,
                "blocked",
                level,
                "Consente requerido para dados altamente sensíveis",
            )

        # 3. LOCAL_SENSITIVE allows balanced export, blocks in local_only
        if level == PrivacyLevel.LOCAL_SENSITIVE:
            if self.mode == "local_only" and dest_type != "local":
                return ValidationResult(
                    False, "blocked", level, "Modo local_only ativo"
                )

            return ValidationResult(True, "allowed", level)

        return ValidationResult(True, "allowed", PrivacyLevel.PUBLIC)

    def sanitize(self, content: str) -> str:
        """Mask sensitive patterns in the content."""
        if self.rust_engine:
            sanitized, count = self.rust_engine.sanitize(content)
            if count > 0:
                self.session_masked_count += count
            return sanitized

        sanitized = content
        for name, pattern in SECRET_PATTERNS.items():
            new_content, count = re.subn(pattern, f"[MASKED_{name.upper()}]", sanitized)
            if count > 0:
                self.session_masked_count += count
                sanitized = new_content
        return sanitized

    def _get_destination_type(self, destination: str) -> str:
        if destination in {"openai", "gemini", "anthropic", "cloud_llm"}:
            return "cloud"
        if destination in {"notion", "linear", "external_api"}:
            return "external_service"
        return "local"

    def sanitize_perception(self, perception: dict) -> dict:
        """
        Recursively mask all secrets in a perception dictionary.
        This is the 'Cognitive Shield' — secrets never reach the LLM's 'mind'.
        """
        return self._mask_recursive(perception)

    def _mask_recursive(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._mask_recursive(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._mask_recursive(i) for i in data]
        elif isinstance(data, str):
            return self.sanitize(data)
        return data

    # ------------------------------------------------------------------
    # Consent Management
    # ------------------------------------------------------------------

    def check_consent(self, resource: str) -> bool:
        """Check if there is a valid active consent for the resource."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with get_connection(self.db_path) as conn:
                row = conn.execute(
                    "SELECT allowed FROM privacy_consents "
                    "WHERE resource = ? AND allowed = 1 AND (expires_at IS NULL OR expires_at > ?)",
                    (resource, now),
                ).fetchone()
            return bool(row and row["allowed"])
        except Exception:
            return False

    def grant_consent(
        self, resource: str, scope: str = "session", duration_min: int = 30
    ) -> str:
        """Grant a new consent."""
        cid = uuid.uuid4().hex[:12]
        expires = None
        if scope == "session":
            expires = (
                datetime.now(timezone.utc) + timedelta(minutes=duration_min)
            ).isoformat()
        elif scope == "once":
            expires = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()

        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO privacy_consents (id, resource, scope, allowed, expires_at, created_at) "
                "VALUES (?, ?, ?, 1, ?, ?)",
                (cid, resource, scope, expires, datetime.now(timezone.utc).isoformat()),
            )
        self._audit(
            "consent_granted",
            resource,
            "allowed",
            PrivacyLevel.PUBLIC,
            f"Scope: {scope}",
        )
        return cid

    def revoke_consent(self, resource: str) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE privacy_consents SET allowed = 0 WHERE resource = ?",
                (resource,),
            )
        self._audit("consent_revoked", resource, "revoked", PrivacyLevel.PUBLIC)

    # ------------------------------------------------------------------
    # Auditing
    # ------------------------------------------------------------------

    def _audit(
        self,
        etype: str,
        resource: str,
        action: str,
        level: PrivacyLevel,
        reason: str | None = None,
    ) -> None:
        aid = uuid.uuid4().hex[:12]
        try:
            with get_connection(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO privacy_audit_log (id, event_type, resource, destination, action, reason, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        aid,
                        etype,
                        resource,
                        "n/a",
                        action,
                        reason,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        except Exception:
            pass
        log_event(
            logger,
            20 if action == "allowed" else 30,
            "privacy_audit",
            id=aid,
            event=etype,
            resource=resource,
            action=action,
            privacy_level=level.name,
        )

    def get_audit_logs(self, limit: int = 50) -> list[dict]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM privacy_audit_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
