# Changelog

All notable changes to this project will be documented here.

## [0.1.0rc2] - 2026-09-27

### Added

- Release candidate 2 for the initial public alpha of AI Quality Gates.
- Section-aware Schema-Version 1 Markdown gate format.
- Canonical Gate ID / filename validation and numeric duplicate detection.
- DRAFT, OPEN, CLOSED, DEFERRED, and WAIVED formal statuses.
- READY, BLOCKED, and IN_PROGRESS derived states.
- Hard dependency validation and cycle detection.
- Controlled lifecycle commands: `start`, `advance`, `close`, `defer`, `waive`, `resume`.
- Structured AC-* criteria, EVID-* requirements, evidence collection, and verification mappings.
- Evidence references using `file:`, `url:`, `commit:`, and approval-only `manual:` schemes.
- Strict local evidence-file validation and project-root containment.
- Final-state `approve` command available only after Verify.
- SHA-256 Approval-Fingerprint to detect stale approvals after material changes.
- Repository `policy.toml` with mandatory Critical/High review and release-blocking defaults.
- `release-check` command separate from structural validation.
- `next` refuses invalid workspaces.
- JSON output for `status`, `validate`, and `release-check`.
- GitHub Actions Python 3.11–3.13 test matrix configuration.
- Trust model, release checklist, sample lifecycle, consumer CI example, and security guidance.

- Controlled `verify` command with `Verified-On` and `Verification-Fingerprint`.
- `Closed-On` and `Closure-Fingerprint` for all closed gates.
- Governed-path symlink rejection for workspace, policy, gate directory, and gate files.
- Stable JSON Schema Version 1 output keys.
- Severity-first `next` scheduling.
- Evidence refs may contain spaces.

### Reliability hardening

- Duplicate sections and metadata keys fail closed.
- Misnamed Markdown files inside `gates/` are not silently ignored.
- Wrong-section AC/EVID/stage patterns do not satisfy schema requirements.
- OPEN gates cannot complete Close Gate; CLOSED gates require the full cycle.
- Stage/work-log timestamps cannot precede Started-On.
- Malformed records fail validation instead of crashing project validation.
- Closed placeholder gates are rejected.
- Skip-to-done / non-sequential stages are rejected.
- Missing workspaces/gates fail strict mode.
- New-gate dependency errors are rejected before the file is created.
- Existing-record mutations use atomic replacement; v0.1 explicitly remains single-writer.
