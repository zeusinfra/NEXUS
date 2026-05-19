# Security Policy — Zeus Protocol

## 🛡️ Commitment to Security

At Zeus Protocol, the security of the NEXUS system and the privacy of our users' operational data are our highest priorities. As a local-first cognitive operating layer, NEXUS is designed with security boundaries at its core, separating proposal, approval, and execution of system actions.

The current runtime security invariant is evidence-first autonomy: an action is
not considered complete unless the system has persisted execution evidence,
verification state and replayable history.

## 🔓 Reporting a Vulnerability

We value the work of security researchers and the community in helping us maintain a secure ecosystem. If you discover a security vulnerability within NEXUS or any Zeus Protocol infrastructure, we request that you report it to us responsibly.

**Please do not open a public issue for security-related findings.**

### Reporting Process

1.  **WhatsApp**: Send a detailed report to +55 (12) 98247-4095.
2.  **Encryption**: If sensitive information is included, please use our PGP key (available upon request or via our website).
3.  **Details**: Include a description of the vulnerability, steps to reproduce, and potential impact.

### Our Response Timeline

*   **Acknowledgment**: You will receive an acknowledgment of your report within 24–48 hours.
*   **Assessment**: Our security team will conduct a thorough assessment and keep you informed of the progress.
*   **Resolution**: We aim to provide a resolution or mitigation strategy as quickly as possible, typically within 7–14 business days depending on the complexity.

## 🚀 Supported Versions

Zeus Protocol actively supports and provides security updates for the following versions of NEXUS:

| Version | Supported |
| :--- | :--- |
| 1.x (Current) | ✅ Yes |
| < 1.0 | ❌ No (Please upgrade to the latest Enterprise release) |

## ⚖️ Responsible Disclosure Policy

Zeus Protocol follows the principles of responsible disclosure. We ask that researchers:
*   Give us reasonable time to investigate and mitigate the issue before making any information public.
*   Avoid privacy violations, destruction of data, and interruption or degradation of our services.
*   Do not engage in "extortion" or demand payment in exchange for reporting vulnerabilities.

## 🎓 Security Research Guidelines

Research performed on local NEXUS instances should not impact other users or Zeus Protocol's hosted infrastructure (zeusprotocol.cloud). We encourage security audits of our command ledger, approval queue, structured execution plans, action replay, self-healing diagnostics, resource governor and sandbox runtime.

Areas of special interest:

*   bypassing approval before command execution;
*   marking work complete without stdout/stderr, exit code or verification;
*   losing or corrupting replay history;
*   hiding failed commands from incidents;
*   exceeding configured CPU, RAM, timeout or concurrency budgets.

---
Copyright © 2026 Zeus Protocol. All rights reserved.
