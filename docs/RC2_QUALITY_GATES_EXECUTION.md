# RC2 Quality Gates Execution Report

Date: 2026-09-27

This report converts the final RC1 review recommendations into sequential execution gates. Each gate followed: **Analyze → Prepare → Execute → Test → Review → Fix → Re-test → Verify → Close Gate**. A gate was not treated as closed until its targeted tests passed.

## GATE-R1 — Governed Path Containment — CRITICAL — CLOSED

- **Problem:** symlinked AQG workspace/gate/policy paths could redirect reads/writes outside the project root.
- **Execute:** added governed-path containment and symlink rejection for `.quality-gates`, `gates/`, `policy.toml`, and gate entries; mutation lookup also fails closed.
- **Tests:** workspace symlink, gates-directory symlink, policy symlink, gate-file symlink.
- **Verify:** all targeted security tests PASS.

## GATE-R2 — Verification Freshness — CRITICAL — CLOSED

- **Problem:** evidence/mappings could change after Verify while approval/closure still succeeded.
- **Execute:** introduced controlled `aqg verify`, `Verified-On`, `Verification-Fingerprint`, fresh-verification preconditions, and automatic verification invalidation on material CLI mutations.
- **Tests:** change evidence after Verify resets Verify; manual material edit after Verify causes stale-fingerprint failure; approval without fresh Verify fails.
- **Verify:** targeted lifecycle/adversarial tests PASS.

## GATE-R3 — Lifecycle Temporal Model — HIGH — CLOSED

- **Problem:** DEFER/RESUME before execution caused later `Started-On` chronology errors.
- **Execute:** separated lifecycle events from execution events for Started-On chronology while preserving global monotonic Work Log ordering.
- **Tests:** DEFER → RESUME → START before execution.
- **Verify:** PASS.

## GATE-R4 — Exception Readiness — HIGH — CLOSED

- **Problem:** undefined placeholder gates could be waived/deferred as governance exceptions.
- **Execute:** DEFER requires concrete Problem; WAIVE requires concrete Problem + Acceptance Criteria + Evidence Required; release policy remains a separate control for blocking severities.
- **Tests:** undefined waiver rejected; authorized scoped blocking waiver policy test remains PASS.
- **Verify:** PASS.

## GATE-R5 — Closure Freshness — HIGH — CLOSED

- **Problem:** review-not-required CLOSED gates could be materially edited after closure without detection.
- **Execute:** added `Closed-On` and SHA-256 `Closure-Fingerprint` to every closed gate.
- **Tests:** post-close manual edit to no-review gate causes stale-closure failure.
- **Verify:** PASS.

## GATE-R6 — Test the Artifact We Ship — HIGH — CLOSED LOCALLY / EXTERNAL MATRIX PENDING

- **Problem:** CI built a wheel but smoke-tested the editable install.
- **Execute:** CI now uninstalls editable AQG, installs `dist/*.whl`, then runs CLI/sample strict validation/release-check from the wheel on Python 3.11/3.12/3.13.
- **Local test:** wheel build and clean-wheel install are executed in the release acceptance sequence.
- **External dependency:** GitHub Actions matrix can only be verified after full source push.

## GATE-R7 — Fence-aware Markdown Scanner — MEDIUM — CLOSED

- **Problem:** H2 headings inside fenced examples could be interpreted as schema sections.
- **Execute:** section scanner ignores backtick/tilde fenced code blocks.
- **Test:** fenced `## Metadata` inside Problem no longer creates a duplicate section.
- **Verify:** PASS.

## GATE-R8 — Evidence Reference Grammar v1 — MEDIUM — CLOSED

- **Problem:** evidence refs could not contain spaces.
- **Execute:** parser now reads `ref=` up to the canonical ` | result=` delimiter.
- **Tests:** `file:artifacts/proof file.txt` and `manual:QA Reviewer approval note` parse/validate.
- **Verify:** PASS.

## GATE-R9 — Stable JSON Contract — MEDIUM — CLOSED

- **Problem:** `release-check --json` failure returned `valid:false` rather than `release_ready:false`.
- **Execute:** JSON outputs carry `schema_version: 1`; validation consistently uses `valid`, release-check consistently uses `release_ready`.
- **Tests:** success/failure machine-contract checks.
- **Verify:** PASS.

## GATE-R10 — Severity-first Scheduling — MEDIUM — CLOSED

- **Problem:** a Low IN_PROGRESS gate could outrank a Critical READY gate.
- **Execute:** scheduling order is severity first, then state (`IN_PROGRESS` before `READY` within a severity), then Gate ID.
- **Test:** Critical READY outranks Low IN_PROGRESS.
- **Verify:** PASS.

## GATE-R11 — Preserve File Permissions — MEDIUM — CLOSED

- **Problem:** atomic replacement could change an existing file from 0644 to 0600.
- **Execute:** atomic writes preserve the original POSIX mode before `os.replace`.
- **Test:** mutation preserves 0644 on POSIX.
- **Verify:** PASS.

## GATE-R12 — AI Threat Boundary + Preamble/Title Guard — MEDIUM — CLOSED

- **Problem:** agent-facing trust boundary did not explicitly classify repository/evidence content as untrusted data; ungoverned preamble/title control characters were accepted.
- **Execute:** added untrusted-content rules to agent/security/trust documentation; rejected nonblank preamble before Metadata and control/newline characters in gate titles.
- **Tests:** newline title rejected without file creation; nonblank preamble fails validation.
- **Verify:** PASS.

## GATE-R13 — Release Engineering / Maintainability — LOW/MEDIUM — CLOSED LOCALLY

- **Problem:** test helpers were coupled, validation repeatedly reparsed gates, archive conventions were weak, and release evidence needed refresh.
- **Execute:** extracted shared test helpers; validation reuses parsed gate summaries; sample project regenerated through the controlled lifecycle; docs/schema/checklists updated; versioned RC2 archive + internal manifest/external archive checksum are generated at packaging time.
- **Performance verification:** local strict validation benchmark: ~0.085 s / 50 gates, ~0.189 s / 100 gates, ~0.529 s / 200 gates on the audit environment.
- **Verify:** compile/sample/package checks PASS; external GitHub CI remains the final publication dependency.

## Sequential gate status

| Gate | Severity | Status |
|---|---|---|
| GATE-R1 | Critical | CLOSED |
| GATE-R2 | Critical | CLOSED |
| GATE-R3 | High | CLOSED |
| GATE-R4 | High | CLOSED |
| GATE-R5 | High | CLOSED |
| GATE-R6 | High | CLOSED LOCALLY — GitHub matrix pending |
| GATE-R7 | Medium | CLOSED |
| GATE-R8 | Medium | CLOSED |
| GATE-R9 | Medium | CLOSED |
| GATE-R10 | Medium | CLOSED |
| GATE-R11 | Medium | CLOSED |
| GATE-R12 | Medium | CLOSED |
| GATE-R13 | Low/Medium | CLOSED LOCALLY — GitHub publication check pending |

## Release decision

All code/documentation recommendations from the RC1 review have been implemented locally. The only remaining non-local acceptance gate is the GitHub Actions matrix on Python 3.11/3.12/3.13 after pushing the complete RC2 source tree. Do not create the final `v0.1.0` tag until that matrix is green.
