# Quickstart

## 1. Install

```bash
git clone https://github.com/waelali87/ai-quality-gates.git
cd ai-quality-gates
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
```

## 2. Initialize

```bash
cd /path/to/target-project
aqg init
```

This creates `.quality-gates/policy.toml` with Critical/High release blocking and mandatory review by default.

## 3. Create and define a gate

```bash
aqg new "Protect secrets from logs" --severity critical
```

Replace the generated Problem, `AC-*`, and `EVID-*` placeholders.

## 4. Check readiness and start

```bash
aqg status
aqg next
aqg start GATE-001 --note "Scope, criteria, and evidence plan reviewed"
```

## 5. Execute sequentially

Use `aqg advance` for Analyze through Re-test. Record “no fix required” when that is the real result; do not invent a change.

## 6. Record evidence and acceptance mappings

```bash
aqg add-evidence GATE-001 EVID-001 \
  --ref file:artifacts/redaction-test.txt \
  --result PASS \
  --note "Sensitive-token leakage regression test passed"

aqg satisfy GATE-001 AC-001 \
  --evidence EVID-001 \
  --note "The regression test proves tokens are redacted"
```

## 7. Complete Verify, then approve

```bash
aqg advance GATE-001 --note "Acceptance criteria mapped to PASS evidence"
aqg approve GATE-001 \
  --reviewer "QA Reviewer" \
  --note "Final verified state reviewed and accepted"
```

Approval before Verify is rejected. A material change after approval invalidates or stales the approval.

## 8. Close

```bash
aqg close GATE-001 \
  --confirm-no-regression \
  --note "All closure invariants satisfied"
```

## 9. Validate vs release-check

```bash
aqg validate --strict   # record integrity + governance invariants
aqg release-check       # release-blocking policy
```

A structurally valid Critical DRAFT gate can pass `validate --strict` but must fail `release-check` under the default policy.

## 10. Machine-readable output

```bash
aqg status --json
aqg validate --strict --json
aqg release-check --json
```

## Concurrency note

v0.1 assumes a single AQG writer per workspace. Do not run concurrent mutation commands against the same `.quality-gates/` directory.
