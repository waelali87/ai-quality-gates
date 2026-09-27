# Acceptance Report — v0.1.0

Date: 2026-09-28

## Engineering acceptance

- Test inventory: **67 test cases** after RC2 hardening.
- Python compile check: **PASS**.
- Sample project strict validation: **PASS**.
- Sample project release-policy check: **PASS**.
- Governed symlink/path-escape controls: **PASS**.
- Verification / approval / closure freshness controls: **PASS**.
- Exception-readiness controls: **PASS**.
- Fence-aware schema parsing: **PASS**.
- Evidence refs with spaces: **PASS**.
- Stable JSON contract tests: **PASS**.
- Severity-first scheduler test: **PASS**.
- POSIX file-mode preservation test: **PASS**.
- Title/preamble guards: **PASS**.

## Package acceptance

The accepted package flow verifies:

1. `python -m compileall -q src`
2. clean wheel build from the source tree
3. replacement of the editable installation with the built wheel
4. installed-wheel `aqg --version`
5. installed-wheel `aqg validate --strict examples/sample-project`
6. installed-wheel `aqg release-check examples/sample-project`
7. source manifest integrity
8. release-asset SHA-256 checksums

## External CI verification

GitHub Actions run `36352179562` on the published RC2 baseline completed successfully across Python 3.11, 3.12, and 3.13. All matrix jobs passed full test discovery, compile check, clean wheel build, installed-wheel CLI smoke test, sample strict validation, and sample release-policy check.

The final `v0.1.0` promotion commit is required to pass the same CI matrix before the automated release workflow publishes the tag and release assets.

## Decision

**RC2 engineering acceptance: PASS.**

**v0.1.0 promotion: APPROVED, conditional only on the same final-commit GitHub Actions matrix completing green. The repository release workflow publishes the final tag and assets only after that condition is met.**
