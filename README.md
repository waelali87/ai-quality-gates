# AI Quality Gates Framework

**AI Quality Gates (AQG)** is a deterministic, evidence-based governance framework and zero-runtime-dependency Python CLI for AI-assisted software development and other complex execution work.

It turns findings, recommendations, risks, defects, and missing requirements into dependency-aware quality gates, then prevents a gate from being treated as complete until its execution history, evidence, verification mappings, review requirements, and closure invariants are internally consistent.

> **Core principle:** a confident statement is not evidence, and a checked box is not proof by itself.

## Why AQG exists

Long AI-assisted tasks fail in predictable ways: recommendations disappear, work jumps directly to “done,” dependencies are ignored, fixes are not re-tested, evidence is vague, and an agent can claim completion without a durable audit trail.

AQG makes the execution contract explicit:

```text
Findings / Risks / Requirements
            ↓
Deduplicate and prioritize
            ↓
Map hard dependencies
            ↓
Create DRAFT gates
            ↓
Define objective criteria + evidence
            ↓
Start only when READY
            ↓
Analyze → Prepare → Execute → Test → Review → Fix → Re-test → Verify
            ↓
Independent approval when required
            ↓
Close only after strict validation
```

## What is enforced

AQG validates more than final checkboxes:

- canonical gate identity: filename and internal Gate ID must agree;
- schema versioning;
- unique Gate IDs and AC/EVID identifiers;
- dependency existence and cycle detection;
- dependency-aware execution (`READY`, `BLOCKED`, `IN_PROGRESS`);
- sequential stage completion: checked stages must form a contiguous prefix;
- stage-history and work-log entries must match completed stages in order;
- non-placeholder problem, acceptance criteria, and evidence requirements before execution;
- structured evidence references and optional strict local-file existence checks;
- acceptance criteria mapped to collected PASS evidence;
- independent approval when `Review-Required: YES`;
- auditable `DEFERRED` and `WAIVED` exceptions that are **not** equivalent to closure;
- controlled final closure through `aqg close`;
- fail-closed validation for malformed or contradictory gate records.

## Trust model — what AQG proves and what it does not

AQG proves **process-state consistency** within the gate records. It can verify that required metadata exists, dependencies are respected, stages were recorded sequentially, evidence references are structurally valid, local evidence files exist in strict mode, criteria are mapped to PASS evidence, and closure invariants are satisfied.

AQG **does not independently prove that the underlying software, analysis, screenshot, external URL, test implementation, human review, or business decision is truthful or correct**. A malicious or careless user can fabricate artifacts. AQG therefore complements—not replaces—domain expertise, secure CI, test quality, code review, security review, audit procedures, and human accountability.

## Installation

Requires Python 3.11+.

```bash
python -m pip install -e .
```

The runtime package uses only the Python standard library.

## Quick start

```bash
aqg init

aqg new "Prevent duplicate payment posting" --severity critical
```

Edit `.quality-gates/gates/GATE-001.md` and replace the DRAFT placeholders with real content. Then:

```bash
aqg status
aqg start GATE-001 --note "Problem, criteria, and evidence plan reviewed"
```

Advance one stage at a time:

```bash
aqg advance GATE-001 --note "Root cause confirmed"
aqg advance GATE-001 --note "Implementation and rollback plan prepared"
# ... continue through Review / Fix / Re-test ...
```

Record objective evidence. `file:` references are verified to exist under the project root when strict validation or controlled evidence entry is used:

```bash
aqg add-evidence GATE-001 EVID-001 \
  --ref file:artifacts/regression-test.txt \
  --result PASS \
  --note "Idempotency regression suite passed"
```

Map acceptance criteria to evidence:

```bash
aqg satisfy GATE-001 AC-001 \
  --evidence EVID-001 \
  --note "The regression suite proves duplicate submissions create one posting"
```

Record independent approval after the Review stage when required:

```bash
aqg approve GATE-001 \
  --reviewer "QA Reviewer" \
  --note "Reviewed implementation, tests, and regression risk"
```

Complete Verify, then close only through the controlled command:

```bash
aqg close GATE-001 \
  --confirm-no-regression \
  --note "All closure invariants satisfied"
```

Finally:

```bash
aqg validate --strict
```

## Lifecycle states

AQG stores formal statuses and derives operational states.

Formal statuses:

- `DRAFT` — gate definition is being prepared;
- `OPEN` — execution has started;
- `CLOSED` — verified closure;
- `DEFERRED` — explicitly postponed with reason/owner/date;
- `WAIVED` — explicitly waived with reason/owner/date; **not** verified closure.

Operational states shown by `aqg status`:

- `DRAFT` — not yet ready;
- `READY` — DRAFT is complete and prerequisites are closed;
- `BLOCKED` — at least one dependency is not closed;
- `IN_PROGRESS` — OPEN and executing;
- `CLOSED`, `DEFERRED`, `WAIVED`.

Use `aqg next` to select the highest-priority executable gate while respecting dependencies.

## Evidence contract

Required evidence is declared with stable IDs:

```markdown
- [ ] EVID-001 | type=test | A reproducible regression test passes.
```

Collected evidence uses a structured record:

```markdown
- EVID-001 | type=test | ref=file:artifacts/test-results.txt | result=PASS | note=Regression suite passed
```

Supported reference schemes:

- `file:relative/path` — project-relative artifact; strict mode requires it to exist and forbids path escape;
- `url:https://...` — absolute HTTP(S) URL;
- `commit:<7-40 hex SHA>` — Git commit reference;
- `manual:<description>` — permitted only for `type=approval`.

Acceptance criteria must be explicitly mapped to collected PASS evidence:

```markdown
- AC-001 -> EVID-001 | Regression evidence proves idempotent posting.
```

## CLI

```text
aqg init [path]
aqg new "Title" [--severity ...] [--depends-on GATE-001] [--review-required yes|no]
aqg status [path] [--json]
aqg next [path] [--json]
aqg validate [path] [--strict] [--json]
aqg start GATE-001 --note "..."
aqg advance GATE-001 --note "..."
aqg add-evidence GATE-001 EVID-001 --ref ... --result PASS --note "..."
aqg satisfy GATE-001 AC-001 --evidence EVID-001 --note "..."
aqg approve GATE-001 --reviewer "..." --note "..."
aqg close GATE-001 --confirm-no-regression --note "..."
aqg defer GATE-001 --reason "..." --by "..."
aqg waive GATE-001 --reason "..." --by "..."
aqg resume GATE-001 --note "..."
```

## CI

The repository tests Python 3.11, 3.12, and 3.13. For a consumer project, copy [`examples/consumer-workflow.yml`](examples/consumer-workflow.yml) into `.github/workflows/quality-gates.yml` and adapt installation as needed.

The enforcement command is:

```bash
aqg validate --strict
```

## Use with AI coding agents

Start with [`prompts/UNIVERSAL_AGENT_PROMPT.md`](prompts/UNIVERSAL_AGENT_PROMPT.md). Integration notes are included for ChatGPT/Codex, Claude Code, Cursor, and OpenCode.

The `.quality-gates/` directory is the durable source of truth. The agent should use AQG commands for lifecycle transitions instead of manually marking a gate complete.

## Repository layout

```text
.
├── src/ai_quality_gates/     # CLI and validation logic
├── templates/                # Gate and findings templates
├── prompts/                  # Agent operating prompts
├── docs/                     # Specification, trust model, design decisions
├── examples/                 # Lifecycle examples and consumer CI
├── tests/                    # Unit + end-to-end tests
└── .github/                  # CI and contribution templates
```

## Security and sensitive evidence

Never commit secrets, tokens, passwords, personal data, production credentials, or confidential records into `.quality-gates/`. Prefer sanitized or redacted evidence artifacts. See [`SECURITY.md`](SECURITY.md).

## Maturity

`v0.1.0` is the initial public alpha. Its scope is intentionally narrow: deterministic Markdown gate records, dependency-aware lifecycle control, evidence contracts, strict validation, and a small standard-library CLI.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT License. See [`LICENSE`](LICENSE).

## Author

Created by **Wael Elgendy** as an open framework for disciplined AI-assisted execution and quality assurance.
