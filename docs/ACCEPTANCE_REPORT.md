# Acceptance Report — v0.1.0 RC2

Date: 2026-09-27

## Local verified results

- Test inventory: **67 test cases** after RC2 hardening.
- All test cases have passed in local module/class/targeted runs on Python 3.13.5.
- A single monolithic `unittest discover` invocation exceeds the interactive execution window in this audit environment because CLI lifecycle tests spawn many Python subprocesses; GitHub CI remains the authoritative uninterrupted full-discovery run.
- Python compile check: PASS.
- Sample project strict validation: PASS.
- Sample project release-policy check: PASS.
- Governed symlink/path escape controls: PASS.
- Verification/approval/closure freshness controls: PASS.
- Exception-readiness controls: PASS.
- Fence-aware schema parsing: PASS.
- Evidence refs with spaces: PASS.
- Stable JSON contract tests: PASS.
- Severity-first scheduler test: PASS.
- POSIX file-mode preservation test: PASS.
- Title/preamble guards: PASS.
- Local strict-validation benchmark: ~0.085s/50 gates, ~0.189s/100, ~0.529s/200 in this environment.

## Package acceptance

Verified locally on Python 3.13.5:

1. `python -m compileall -q src` — **PASS**
2. `python -m pip wheel . --no-deps --no-build-isolation -w dist` — **PASS**
3. clean venv install of the built wheel with `--no-index --no-deps` — **PASS**
4. installed-wheel `aqg --version` → `aqg 0.1.0rc2` — **PASS**
5. installed-wheel `aqg validate --strict examples/sample-project` — **PASS**
6. installed-wheel `aqg release-check examples/sample-project` — **PASS**
7. secret/private-key/token pattern scan — **PASS** (no matches)
8. email-like-string scan — **PASS** (no matches)
9. internal `MANIFEST.sha256` — **PASS** (43 source-file entries verified after cleanup); external `SHA256SUMS` is generated for the final RC2 archive.

## External CI still required

The repository CI is configured for Python 3.11, 3.12, and 3.13 and now tests the built wheel. The final public `v0.1.0` tag remains blocked until the complete source tree is pushed and all three GitHub Actions matrix jobs are green.

## Decision

**RC2 local engineering gates, package-install gates, and internal manifest verification: PASS. GitHub CI is the remaining external publication gate.**

**Final public v0.1.0 tag: HOLD until GitHub Actions is green on the complete source commit.**
