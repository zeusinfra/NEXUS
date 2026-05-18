## Description
<!-- Describe your changes in detail -->

## Related Issues
<!-- Link to the issue this PR resolves, e.g., "Fixes #123" -->

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Security patch

## Verification
- [ ] Tests pass locally (`pytest tests/` and `cargo check`)
- [ ] Lints pass (`cargo fmt --check`, `cargo clippy`)
- [ ] Autonomous safety guardrails verified (if modifying RootDaemon or Policies)
- [ ] Execution evidence, verification records and replay are covered (if modifying runtime execution)
- [ ] Resource budgets are respected (if modifying autonomous execution, planning, or command loops)
- [ ] UI changes keep technical complexity out of the primary conversational flow
