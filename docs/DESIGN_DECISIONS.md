# Design Decisions

## Markdown remains the human-readable gate record

Records must remain readable, diffable, portable, and agent-friendly. AQG therefore keeps Markdown as storage while imposing deterministic structure.

## Parse sections before patterns

The parser treats headings as schema boundaries. AC, evidence, execution stages, verification mappings, and closure checks only count inside their canonical sections. This prevents a regex elsewhere in the document from spoofing governed state.

## Validation and release readiness are separate

`aqg validate --strict` proves record and governance consistency. It intentionally does not decide whether unresolved work is acceptable for release. `aqg release-check` applies repository policy to release-blocking severities.

## Policy is repository-owned

`.quality-gates/policy.toml` controls release-blocking severities, release exception behavior, and severities requiring independent review. Agents cannot silently bypass Critical/High review under the default policy.

## Approval is of the final verified state

Independent approval occurs after Verify, not after Review. AQG stores an approval fingerprint over material reviewed content. Changes after approval invalidate or stale the approval, preventing pre-fix approvals from authorizing a later state.

## Exceptions are not closure

DEFERRED and WAIVED keep explicit reason, owner, and timestamp. They do not satisfy CLOSED dependencies, and default release policy still blocks Critical/High exceptions.

## Zero runtime dependencies

The CLI uses only the Python standard library to reduce installation friction and supply-chain surface.

## v0.1 is single-writer

AQG uses atomic replacement for mutations and exclusive creation for new gates, but it does not claim safe multi-writer concurrency. Cross-process locking is deferred until there is evidence that the additional complexity is justified.
