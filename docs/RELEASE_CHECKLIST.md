# Release Checklist

## Source and packaging

- [ ] Canonical repository tree contains no build/cache artifacts.
- [ ] `python -m compileall -q src` passes.
- [ ] Wheel builds without runtime dependencies.
- [ ] Built wheel is installed into a clean environment and `aqg --version` passes.
- [ ] Sample strict validation and release-check run from the installed wheel.
- [ ] No credentials, private keys, tokens, or private email addresses are present.
- [ ] Internal `MANIFEST.sha256` covers the release tree.
- [ ] External `SHA256SUMS` covers the archive artifact.

## Security / filesystem

- [ ] `.quality-gates` symlink fails.
- [ ] `gates/` symlink fails.
- [ ] `policy.toml` symlink fails.
- [ ] symlinked gate file fails.
- [ ] Governed paths cannot resolve outside project root.
- [ ] Evidence traversal outside root fails.

## Lifecycle / freshness

- [ ] Full unit/lifecycle/adversarial suite passes.
- [ ] `aqg verify` requires Analyze through Re-test plus complete PASS evidence mapping.
- [ ] Material CLI mutation after Verify invalidates Verify.
- [ ] Manual material mutation after Verify makes Verification-Fingerprint stale.
- [ ] Approval requires a fresh Verify.
- [ ] Material mutation after approval invalidates/stales approval.
- [ ] CLOSED record mutation makes Closure-Fingerprint stale, including review-not-required gates.
- [ ] DEFER → RESUME → START before execution is valid.
- [ ] DEFER requires a concrete Problem.
- [ ] WAIVE requires concrete Problem + AC + Evidence Required.

## Parser / machine contract

- [ ] Wrong-section AC/EVID/stage spoofing fails.
- [ ] Duplicate metadata and duplicate sections fail.
- [ ] H2 headings inside fenced code do not count as schema sections.
- [ ] Nonblank preamble before Metadata fails.
- [ ] Newline/control characters in titles fail.
- [ ] Evidence refs with spaces follow documented grammar.
- [ ] JSON failure/success shapes include Schema Version 1 and stable command-specific keys.

## Governance / scheduling

- [ ] `aqg validate --strict examples/sample-project` passes.
- [ ] `aqg release-check examples/sample-project` passes.
- [ ] Critical DRAFT/OPEN fails release-check.
- [ ] Critical WAIVED fails release-check under default policy.
- [ ] Critical/High cannot disable review under default policy.
- [ ] Critical READY outranks Low IN_PROGRESS in `aqg next`.
- [ ] `aqg next` refuses invalid projects.

## CI

- [ ] Python 3.11 green.
- [ ] Python 3.12 green.
- [ ] Python 3.13 green.
- [ ] CI smoke-tests the built wheel, not only editable install.
- [ ] Consumer workflow pins `v0.1.0` or an immutable commit SHA, not `main`.

## Documentation

- [ ] README distinguishes record integrity, governance compliance, and release readiness.
- [ ] Verification, approval, and closure freshness are documented.
- [ ] Governed-path and untrusted-agent-content boundaries are explicit.
- [ ] Single-writer limitation is explicit.
- [ ] Roadmap lists only future work.

## GitHub

- [ ] Full source tree is pushed.
- [ ] Actions are green on the release commit.
- [ ] Tag `v0.1.0` points to the verified commit only after every preceding item passes.
