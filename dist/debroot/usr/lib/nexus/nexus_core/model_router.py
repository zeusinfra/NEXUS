from __future__ import annotations

import re
from dataclasses import asdict, dataclass


CRITICAL_TERMS = {
    "sudo",
    "/etc",
    "systemctl",
    "bootloader",
    "mkfs",
    "dd ",
    "wipefs",
    "parted",
}
COMPLEX_TERMS = {
    "arquitetura",
    "architecture",
    "refator",
    "multi-arquivo",
    "security",
    "segurança",
    "debugging profundo",
    "package",
    ".deb",
    "debian",
    "systemd",
}
DANGEROUS_PATTERNS = [
    re.compile(r"\brm\s+-rf\s+/(?:\s|$)"),
    re.compile(r"\bchmod\s+-R\s+777\s+/"),
    re.compile(r"\bchown\s+-R\b.*\s+/"),
]


@dataclass(frozen=True)
class RoutingDecision:
    task: str
    complexity: str
    route: str
    model_role: str
    risk: str
    reviewer_required: bool
    approval_required: bool
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class ModelRouter:
    def classify(self, task: str) -> RoutingDecision:
        text = (task or "").strip()
        lowered = text.lower()

        if any(pattern.search(lowered) for pattern in DANGEROUS_PATTERNS):
            return self._decision(
                text, "critical", "cloud", "critical", "blocked destructive pattern"
            )

        if any(term in lowered for term in CRITICAL_TERMS):
            return self._decision(
                text,
                "critical",
                "cloud",
                "critical",
                "sudo/system/systemd/destructive context",
            )

        if any(term in lowered for term in COMPLEX_TERMS) or len(text) > 900:
            return self._decision(
                text,
                "complex",
                "cloud",
                "high",
                "complex architecture/security/package task",
            )

        if len(text) < 220 and not any(
            token in lowered for token in ("alterar", "executar", "install", "delete")
        ):
            return self._decision(text, "simple", "local", "low", "short low-risk task")

        return self._decision(
            text, "normal", "local", "medium", "default hybrid routing"
        )

    def _decision(
        self, task: str, complexity: str, route: str, risk: str, reason: str
    ) -> RoutingDecision:
        critical = complexity == "critical"
        return RoutingDecision(
            task=task,
            complexity=complexity,
            route=route,
            model_role="strategic" if route == "cloud" else "reflexive",
            risk=risk,
            reviewer_required=complexity in {"complex", "critical"},
            approval_required=critical,
            reason=reason,
        )
