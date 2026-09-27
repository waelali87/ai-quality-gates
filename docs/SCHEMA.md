# Gate Schema v1

Every gate is a Markdown document with `Schema-Version: 1` and exactly one occurrence of each required section, in canonical order:

1. Metadata
2. Problem
3. Acceptance Criteria
4. Evidence Required
5. Evidence Collected
6. Execution Cycle
7. Stage History
8. Work Log
9. Verification
10. Closure

Schema-critical data is section-aware and headings inside fenced code blocks are ignored. Nonblank content between the H1 gate title and `## Metadata` is invalid. An `AC-*` line outside Acceptance Criteria, an `EVID-*` line outside its evidence section, or a stage checkbox outside Execution Cycle does not count.

## Canonical identity

- Gate: `GATE-<number>` rendered with at least three digits (`GATE-001`, `GATE-1000`).
- Acceptance criterion: `AC-<number>`.
- Evidence requirement: `EVID-<number>`.

`GATE-1`, `GATE-01`, and `GATE-001` resolve to the same numeric identity, so only canonical `GATE-001` is accepted. Duplicate numeric identities are invalid. Every Markdown file inside `.quality-gates/gates/` must be a canonical gate record.

## Governed paths

`.quality-gates`, `gates/`, `policy.toml`, and gate records must not be symbolic links and must resolve inside the project root.

## Required metadata

- Schema-Version
- Severity
- Dependencies
- Status
- Current-Stage
- Started-On
- Verified-On
- Verification-Fingerprint
- Review-Required
- Reviewer
- Approval
- Approved-On
- Approval-Fingerprint
- Closed-On
- Closure-Fingerprint
- Exception-Reason
- Exception-By
- Exception-On

Each governed metadata key appears exactly once.

## Execution cycle

Execution Cycle contains exactly these nine rows, in order:

`Analyze → Prepare → Execute → Test → Review → Fix → Re-test → Verify → Close Gate`

`aqg advance` completes Analyze through Re-test. `aqg verify` is the controlled Verify transition. `aqg close` is the controlled Close Gate transition.

Checked stages form one contiguous prefix. `OPEN` cannot include completed `Close Gate`; `CLOSED` requires all nine stages.

## Verification freshness

`aqg verify` is allowed only after Analyze through Re-test are complete and required PASS evidence is mapped to all acceptance criteria. It records:

- `Verified-On`
- `Verification-Fingerprint`

The fingerprint binds the material state being verified: title, severity, dependencies, problem, criteria, evidence requirements/collection, verification mappings, execution state through Re-test, and related stage/work-log state. Material changes after Verify make verification stale. Controlled CLI mutations invalidate Verify explicitly.

## Approval freshness

For review-required gates, approval is accepted only after a fresh Verify. AQG stores `Approved-On` and `Approval-Fingerprint` over the final verified state including the verification fingerprint. Material changes after approval make approval stale or explicitly invalidate it.

## Closure freshness

All CLOSED gates, including gates where independent review is not required, store:

- `Closed-On`
- `Closure-Fingerprint`

The closure fingerprint binds the closed gate record except for the self-referential fingerprint value itself. Material edits to a closed gate therefore fail strict validation.

## Evidence references

Collected evidence uses `ref=<scheme:value>`. The parser allows spaces inside reference values and reads the value up to the canonical ` | result=` delimiter. Supported schemes are `file:`, `url:`, `commit:`, and approval-only `manual:`.

## Exception readiness

- `DEFERRED` requires a concrete Problem plus exception reason/owner/time.
- `WAIVED` requires a concrete Problem, Acceptance Criteria, Evidence Required, plus exception reason/owner/time.
- Release policy separately decides whether a blocking-severity DEFERRED/WAIVED gate may release.

## Migration policy

Schema v1 is the only supported schema in v0.1. A future breaking format change must increment Schema-Version, document changed invariants, provide a deterministic migration path, preserve original records until verification, and fail closed on unknown schema versions.
