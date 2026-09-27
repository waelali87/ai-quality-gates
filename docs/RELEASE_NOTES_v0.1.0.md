# AI Quality Gates v0.1.0

`v0.1.0` is the first public alpha release of **AI Quality Gates (AQG)**: a deterministic, evidence-based governance framework and Python CLI for turning findings, risks, defects, and requirements into dependency-aware quality gates.

## What ships in v0.1.0

- Structured quality-gate records with canonical IDs, severities, dependencies, acceptance criteria, evidence requirements, and lifecycle state.
- Enforced execution cycle: Analyze → Prepare → Execute → Test → Review → Fix → Re-test → Verify → Close Gate.
- Dependency-aware READY / BLOCKED / IN_PROGRESS scheduling.
- Controlled `verify`, approval, and closure fingerprints to detect stale reviewed states.
- Release-policy checks separated from structural validation.
- Symlink/path-escape protection for governed paths and strict local-evidence containment.
- Stable Schema Version 1 JSON outputs for automation.
- Adversarial parser and lifecycle hardening, including duplicate-section rejection, wrong-section spoofing rejection, fenced-heading handling, and malformed-record fail-closed behavior.
- AI-agent integration prompts for ChatGPT/Codex, Claude Code, Cursor, and OpenCode.
- Examples, policy templates, trust model, security guidance, release checklist, and consumer CI sample.

## Verification

The release candidate baseline passed the full GitHub Actions matrix on Python 3.11, 3.12, and 3.13. The CI flow executes the full unit/lifecycle/adversarial suite, compiles the package, builds a clean wheel, installs that wheel, verifies the CLI version, and runs strict validation plus release-policy checks against the sample project.

## Scope and maturity

This is an **alpha** release. AQG v0.1 is deliberately CLI-first, Markdown-based, single-writer, and zero-runtime-dependency. Its audit trail is Git-auditable, not tamper-proof, and it does not replace domain review, secure CI, or human accountability.

## Integrity

Release assets include a source ZIP, a Python wheel, and `SHA256SUMS` covering those uploaded artifacts.
