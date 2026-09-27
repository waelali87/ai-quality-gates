# Roadmap

## v0.1 — Initial public alpha

Implemented:

- section-aware Schema-Version 1 Markdown parser;
- canonical Gate IDs and duplicate numeric-identity detection;
- DRAFT / OPEN / CLOSED / DEFERRED / WAIVED lifecycle;
- READY / BLOCKED / IN_PROGRESS derived states;
- dependency validation and cycle detection;
- sequential nine-stage enforcement with temporal integrity;
- AC/EVID evidence contracts and verification mappings;
- strict local evidence-file validation and path containment;
- governed-path symlink rejection and project-root containment;
- controlled Verify with verification fingerprint freshness checks;
- final-state independent review with approval fingerprint freshness checks;
- closure fingerprints for post-close mutation detection;
- repository policy for mandatory review and release-blocking severities;
- separate strict record validation and `release-check`;
- controlled `start`, `advance`, evidence, approval, closure, exception, and resume commands;
- `status`, `next`, and JSON output;
- atomic record replacement plus explicit single-writer model;
- Python 3.11–3.13 CI configuration.

## v0.2

- migration command for future schema versions;
- configurable evidence-policy profiles beyond the current release/review policy;
- SARIF / richer machine-readable validation output;
- dependency graph export (DOT / Mermaid);
- import converter from audit/review findings;
- optional signed evidence manifests.

## v0.3

- pluggable domain-specific validators;
- additional agent-runtime adapters;
- multi-reviewer / quorum policies;
- optional cross-process locking and multi-agent worktree guidance.

## v1.0 target

- stable schema and CLI compatibility guarantees;
- documented extension interface;
- backward-compatible migrations;
- production-grade release/security policy and provenance options.
