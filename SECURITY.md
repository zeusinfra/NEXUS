# Security Policy

NEXUS is local-first software that can observe desktop context and broker
system actions. Security issues are treated seriously, especially when they
involve privileged execution, local files, secrets, network exposure, or
external integrations.

## Supported Versions

| Version | Supported |
| --- | --- |
| `main` | Yes |
| Latest tagged release | Yes |
| Older pre-1.0 snapshots | No |

Because the project is still evolving, security fixes are expected to land on
`main` first. Users should update to the latest commit or latest release when a
security fix is announced.

## Reporting a Vulnerability

Do not report vulnerabilities through public GitHub issues.

Preferred reporting path:

1. Open a private GitHub security advisory for `zeusinfra/NEXUS`.
2. Include enough detail for maintainers to reproduce and assess the issue.
3. Wait for maintainer acknowledgement before public disclosure.

If private advisories are unavailable, contact the repository maintainers
privately through GitHub.

## What to Include

Please include:

- Affected commit, branch, or release.
- Impact summary.
- Reproduction steps or proof of concept.
- Logs, screenshots, or traces with secrets removed.
- Whether the issue requires local access, LAN access, or remote access.
- Any suggested mitigation or patch.

Never send real credentials, private keys, personal vault contents, production
tokens, or sensitive user data in a report.

## Security Scope

High-priority areas include:

- Organizational runtime proposal, approval, execution, verification, and
  memory records.
- Iced GUI or TUI controls that approve or execute commands.
- RootDaemon and privileged command execution.
- Command policy classification, allowlists, blocklists, and approval gates.
- Authentication, LAN access, CORS, trusted host checks, and token handling.
- Filesystem access, path validation, backup/restore, and vault sync.
- Secret handling in `.env`, CI, logs, and test fixtures.
- Obsidian, Notion, Linear, browser, voice, and external API integrations.
- Dependency, CodeQL, Gitleaks, and Trivy findings.

Out-of-scope examples:

- Issues requiring already-compromised root access with no additional impact.
- Denial of service from intentionally exhausting local disk, RAM, or CPU.
- Social engineering that does not exploit project code or configuration.
- Reports against unsupported historical snapshots.

## Response Expectations

Maintainers aim to:

- Acknowledge valid reports within 48 hours.
- Triage severity and affected versions.
- Coordinate a fix or mitigation plan.
- Credit reporters when requested and appropriate.
- Publish disclosure notes after a patch or mitigation is available.

Timelines may vary based on severity, exploitability, and maintainer
availability.

## Hardening Expectations

Contributors should preserve these defaults:

- Local-first operation unless a user explicitly enables external services.
- No committed secrets or real personal data.
- Isolated test runtime paths.
- Explicit review for privileged execution changes.
- Auditability for high-risk actions.
- Conservative defaults for network exposure and integration sync.
- No command may be reported as successful without concrete evidence such as an
  exit code, runtime event, verification record, service status, or file check.
- Approval must not imply execution. Interfaces should keep these actions
  separate and visible.
- Destructive commands must require explicit operator approval and should prefer
  dry-run, backup, or rollback guidance where possible.
- Daemon and systemd helpers should default to planning/reporting unless a
  write or execute flag is explicitly supplied.

See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request expectations around
security-sensitive changes.
