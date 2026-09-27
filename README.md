# AI Quality Gates Framework

**AI Quality Gates (AQG)** is a deterministic, evidence-based governance framework and zero-runtime-dependency Python CLI for AI-assisted software development and other complex execution work.

It converts findings, risks, defects, and requirements into dependency-aware gates, then separates three questions that are often confused:

1. **Record integrity** — is the gate data structurally and logically consistent?
2. **Governance compliance** — does the record satisfy policy such as mandatory review?
3. **Release readiness** — are all release-blocking gates acceptably resolved?

> **Core principle:** a confident statement is not evidence, and a structurally valid record is not automatically release-ready.

## Why AQG exists

Long AI-assisted tasks fail in predictable ways: recommendations disappear, work jumps directly to “done,” dependencies are ignored, fixes are not re-tested, reviewers approve stale states, evidence is vague, and CI can turn green while critical work remains unresolved.

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
Independent approval of the final verified state when required
            ↓
Close Gate
            ↓
Strict record validation
            ↓
Release-policy check
```

## What is enforced

AQG validates more than final checkboxes:

- canonical gate identity (`GATE-001`, `GATE-1000`, ...);
- exactly one occurrence of each required section and governed metadata key;
- section-aware parsing — AC, evidence, stages, and closure data only count in their canonical sections;
- unique Gate, AC, and EVID identities;
- dependency existence, canonical IDs, and cycle detection;
- dependency-aware execution (`READY`, `BLOCKED`, `IN_PROGRESS`);
- exactly nine execution stages in canonical order;
- sequential stage completion with timestamped Stage History and Work Log entries;
- temporal integrity: started time, stage events, approval, and closure cannot move backward;
- non-placeholder problem, acceptance criteria, and evidence requirements before execution;
- structured evidence references and strict local-file existence checks;
- acceptance criteria mapped to collected PASS evidence;
- policy-driven mandatory independent review for configured severities;
- approval only after **Verify**, plus a SHA-256 fingerprint of the reviewed state;
- automatic/manual detection of stale approval when reviewed content changes;
- auditable `DEFERRED` and `WAIVED` exceptions that are not equivalent to closure;
- controlled final closure through `aqg close`;
- separate `aqg release-check` enforcement for release-blocking severities;
- fail-closed validation for malformed, duplicated, hidden, or contradictory gate records.

## Trust model

AQG proves **recorded process-state consistency**. It can verify structure, dependency state, stage order, evidence references, local evidence-file existence, AC-to-evidence mappings, approval freshness, policy constraints, and release-blocking status.

AQG **does not prove that the underlying code, test implementation, screenshot, URL, human reviewer, or business assertion is truthful or correct**. A malicious or careless actor can fabricate artifacts. AQG complements—not replaces—domain expertise, secure CI, code review, security review, access controls, and human accountability.

The audit trail is **Git-auditable, not tamper-proof**.

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

`aqg init` creates:

```text
.quality-gates/
├── README.md
├── policy.toml
└── gates/
```

Edit the generated gate and replace the Problem, `AC-*`, and `EVID-*` placeholders. Then:

```bash
aqg status
aqg next
aqg start GATE-001 --note "Problem, criteria, and evidence plan reviewed"
```

Advance one stage at a time:

```bash
aqg advance GATE-001 --note "Root cause confirmed"
aqg advance GATE-001 --note "Implementation and rollback plan prepared"
# continue through Re-test
```

Record objective evidence and map acceptance criteria:

```bash
aqg add-evidence GATE-001 EVID-001 \
  --ref file:artifacts/regression-test.txt \
  --result PASS \
  --note "Idempotency regression suite passed"

aqg satisfy GATE-001 AC-001 \
  --evidence EVID-001 \
  --note "The regression suite proves duplicate submissions create one posting"
```

Complete **Verify** first:

```bash
aqg verify GATE-001 --note "Evidence mapped to acceptance criteria and final material state verified"
```

`aqg verify` records `Verified-On` plus a SHA-256 `Verification-Fingerprint`. Any material mutation after Verify invalidates that verification; manual material edits are detected as stale.

Then record independent approval of that final verified state when required:

```bash
aqg approve GATE-001 \
  --reviewer "QA Reviewer" \
  --note "Final verified state reviewed and accepted"
```

Any material content change after approval makes the approval stale. CLI mutations invalidate it explicitly; manual changes are detected by the approval fingerprint.

Close only through the controlled command:

```bash
aqg close GATE-001 \
  --confirm-no-regression \
  --note "All closure invariants satisfied"
```

Finally run both checks:

```bash
aqg validate --strict
aqg release-check
```

`validate --strict` answers **“are the records valid?”**. `release-check` answers **“may this project release under policy?”**.

## Policy

The default `.quality-gates/policy.toml` is:

```toml
[release]
blocking_severities = ["critical", "high"]
allow_waived_blocking = false
allow_deferred_blocking = false

[review]
required_severities = ["critical", "high"]
```

A Critical or High gate therefore cannot disable review through `--review-required no` unless the repository owner explicitly changes policy. A valid Critical/High DRAFT, OPEN, DEFERRED, or WAIVED gate still blocks `release-check` under the default policy.

## Formal and operational states

Formal statuses:

- `DRAFT` — definition/preparation;
- `OPEN` — execution started;
- `CLOSED` — verified closure;
- `DEFERRED` — explicitly postponed;
- `WAIVED` — explicitly waived, but not verified closure.

Operational states shown by `aqg status`:

- `DRAFT` — not ready;
- `READY` — DRAFT is complete and prerequisites are closed;
- `BLOCKED` — dependency not closed;
- `IN_PROGRESS` — OPEN;
- `CLOSED`, `DEFERRED`, `WAIVED`.

`aqg next` refuses to schedule work from an invalid workspace.

## Evidence contract

Required evidence:

```markdown
- [ ] EVID-001 | type=test | A reproducible regression test passes.
```

Collected evidence:

```markdown
- EVID-001 | type=test | ref=file:artifacts/test-results.txt | result=PASS | note=Regression suite passed
```

Supported references:

- `file:relative/path` — strict mode requires the file to exist and rejects path escape;
- `url:https://...` — absolute HTTP(S) URL;
- `commit:<7-40 hex SHA>` — Git commit reference;
- `manual:<description>` — only for `type=approval` evidence.

Acceptance mapping:

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
aqg release-check [path] [--json]
aqg start GATE-001 --note "..."
aqg advance GATE-001 --note "..."
aqg verify GATE-001 --note "..."
aqg add-evidence GATE-001 EVID-001 --ref ... --result PASS --note "..."
aqg satisfy GATE-001 AC-001 --evidence EVID-001 --note "..."
aqg approve GATE-001 --reviewer "..." --note "..."
aqg close GATE-001 --confirm-no-regression --note "..."
aqg defer GATE-001 --reason "..." --by "..."
aqg waive GATE-001 --reason "..." --by "..."
aqg resume GATE-001 --note "..."
```

## Machine-readable JSON contract

JSON outputs include `schema_version: 1`. `validate --json` always uses `valid`, while `release-check --json` always uses `release_ready`; both include `errors`. This shape is stable for Schema Version 1.

## Governed-path safety

AQG rejects symlinked `.quality-gates`, `gates/`, `policy.toml`, and gate records. Governed paths must resolve inside the project root.

## CI

The repository CI is configured for Python 3.11, 3.12, and 3.13. Consumer CI should run both:

```bash
aqg validate --strict
aqg release-check
```

See [`examples/consumer-workflow.yml`](examples/consumer-workflow.yml). The example pins AQG to `v0.1.0`; high-assurance consumers can pin an exact commit SHA.

## AI-agent usage

Start with [`prompts/UNIVERSAL_AGENT_PROMPT.md`](prompts/UNIVERSAL_AGENT_PROMPT.md). Integration notes are included for ChatGPT/Codex, Claude Code, Cursor, and OpenCode.

The `.quality-gates/` directory is durable execution state. Agents should use AQG lifecycle commands rather than manually changing governed fields.

## Concurrency model

**v0.1 is single-writer.** Do not run concurrent AQG mutation commands against the same workspace. Writes are atomic where AQG replaces existing records, and new gate creation uses exclusive creation, but cross-process multi-writer locking is intentionally deferred.

## Repository layout

```text
.
├── src/ai_quality_gates/
├── templates/
├── prompts/
├── docs/
├── examples/
├── tests/
└── .github/
```

## Security

Never commit secrets, tokens, passwords, personal data, production credentials, or confidential records into `.quality-gates/`. Prefer sanitized evidence. See [`SECURITY.md`](SECURITY.md).

## Maturity

`0.1.0rc2` is the release candidate for the initial public `v0.1.0` alpha. It is intentionally CLI-first, Markdown-based, single-writer, and dependency-light.

## License

MIT License. See [`LICENSE`](LICENSE).

## Author

Created by **Wael Elgendy** as an open framework for disciplined AI-assisted execution and quality assurance.
