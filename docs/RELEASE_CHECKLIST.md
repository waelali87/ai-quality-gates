# Release Checklist — v0.1.0

## Source and packaging

- [x] Canonical repository tree contains no build/cache artifacts.
- [x] `python -m compileall -q src` passes.
- [x] Wheel builds without runtime dependencies.
- [x] Built wheel is installed into a clean environment and `aqg --version` passes.
- [x] Sample strict validation and release-check run from the installed wheel.
- [x] No credentials, private keys, tokens, or private email addresses are present in the accepted release source.
- [x] Internal `MANIFEST.sha256` covers the release tree.
- [x] Release workflow generates `SHA256SUMS` for uploaded release artifacts.

## Security / filesystem

- [x] `.quality-gates` symlink fails.
- [x] `gates/` symlink fails.
- [x] `policy.toml` symlink fails.
- [x] symlinked gate file fails.
- [x] Governed paths cannot resolve outside project root.
- [x] Evidence traversal outside root fails.

## Lifecycle / freshness

- [x] Full unit/lifecycle/adversarial suite passes.
- [x] `aqg verify` requires Analyze through Re-test plus complete PASS evidence mapping.
- [x] Material CLI mutation after Verify invalidates Verify.
- [x] Manual material mutation after Verify makes Verification-Fingerprint stale.
- [x] Approval requires a fresh Verify.
- [x] Material mutation after approval invalidates/stales approval.
- [x] CLOSED record mutation makes Closure-Fingerprint stale, including review-not-required gates.
- [x] DEFER → RESUME → START before execution is valid.
- [x] DEFER requires a concrete Problem.
- [x] WAIVE requires concrete Problem + AC + Evidence Required.

## Parser / machine contract

- [x] Wrong-section AC/EVID/stage spoofing fails.
- [x] Duplicate metadata and duplicate sections fail.
- [x] H2 headings inside fenced code do not count as schema sections.
- [x] Nonblank preamble before Metadata fails.
- [x] Newline/control characters in titles fail.
- [x] Evidence refs with spaces follow documented grammar.
- [x] JSON failure/success shapes include Schema Version 1 and stable command-specific keys.

## Governance / scheduling

- [x] `aqg validate --strict examples/sample-project` passes.
- [x] `aqg release-check examples/sample-project` passes.
- [x] Critical DRAFT/OPEN fails release-check.
- [x] Critical WAIVED fails release-check under default policy.
- [x] Critical/High cannot disable review under default policy.
- [x] Critical READY outranks Low IN_PROGRESS in `aqg next`.
- [x] `aqg next` refuses invalid projects.

## CI

- [x] Python 3.11 green on accepted RC2 baseline.
- [x] Python 3.12 green on accepted RC2 baseline.
- [x] Python 3.13 green on accepted RC2 baseline.
- [x] CI smoke-tests the built wheel, not only editable install.
- [x] Consumer workflow pins `v0.1.0` or an immutable commit SHA, not `main`.
- [ ] Final promotion commit matrix green — automatically required before release publication.

## Documentation

- [x] README distinguishes record integrity, governance compliance, and release readiness.
- [x] Verification, approval, and closure freshness are documented.
- [x] Governed-path and untrusted-agent-content boundaries are explicit.
- [x] Single-writer limitation is explicit.
- [x] Roadmap lists only future work.
- [x] Final v0.1.0 release notes are included.

## GitHub

- [x] Full source tree is pushed.
- [ ] Actions are green on the final promotion commit.
- [ ] Tag `v0.1.0` points to the final verified commit.
- [ ] GitHub Release contains source ZIP, wheel, and `SHA256SUMS`.

The final four unchecked items are publication-time controls. The release workflow is fail-closed: it runs only after the final CI workflow completes successfully on `main`, then creates `v0.1.0` from that exact verified commit and uploads the release artifacts.
