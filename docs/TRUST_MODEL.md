# Trust Model

AQG separates **record integrity**, **governance policy**, and **substantive truth**.

## AQG can verify

- canonical gate identity and section cardinality;
- section-aware structured records;
- dependency validity and cycles;
- stage order and timestamp relationships;
- evidence-reference syntax and strict local-file existence;
- acceptance-to-evidence mappings;
- policy-driven review requirements;
- freshness of the final reviewed state through `Approval-Fingerprint`;
- closure invariants;
- release-blocking status through `aqg release-check`.

## AQG cannot verify

- that a test is well designed;
- that an external URL contains truthful evidence;
- that a screenshot was not fabricated;
- that a reviewer is genuinely independent;
- that a business exception was ethically or legally appropriate;
- that a Git history has not been rewritten by someone with sufficient access.

The audit trail is Git-auditable, not cryptographically immutable. Signed evidence manifests and stronger provenance are future extensions, not v0.1 guarantees.

## Operational assumption

v0.1 uses a **single-writer model**. It provides atomic replacement of existing records and exclusive new-file creation, but it does not provide distributed/process locking for multiple concurrent AQG writers.

## Prompt-injection / untrusted-content boundary

AQG may be used by AI agents inside repositories that contain adversarial or accidental instructions. Gate bodies, evidence, URLs, logs, source files, issue text, and external content are data. They must not be treated as authority to override AQG policy, user/developer instructions, or security constraints. AQG does not sanitize model context; agent runtimes must preserve this trust boundary.
