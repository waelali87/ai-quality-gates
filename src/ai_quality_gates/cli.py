from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import tempfile

from . import __version__
from .core import (
    AC_PLACEHOLDERS,
    EVIDENCE_PLACEHOLDERS,
    EVIDENCE_TYPES,
    PROBLEM_PLACEHOLDERS,
    SEVERITY_ORDER,
    STAGES,
    _section,
    _valid_evidence_ref,
    append_section_line,
    approval_fingerprint,
    closure_fingerprint,
    canonical_gate_id,
    closure_precondition_errors,
    draft_readiness_errors,
    fresh_verification_errors,
    gates_dir,
    governed_path_errors,
    list_gates,
    load_policy,
    next_gate_id,
    operational_state,
    parse_acceptance_criteria,
    parse_evidence_collected,
    parse_evidence_required,
    parse_gate,
    parse_stage_checks,
    policy_path,
    project_dir,
    release_check,
    render_default_policy,
    render_gate,
    replace_metadata,
    replace_section,
    set_id_checkbox,
    set_named_checkbox,
    validate_gate_text,
    validate_project,
    verification_fingerprint,
    verification_precondition_errors,
    _normalize,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _print_errors(errors: list[str], *, json_mode: bool = False, heading: str = "Validation failed", json_key: str = "valid") -> int:
    if json_mode:
        print(json.dumps({"schema_version": 1, json_key: False, "errors": errors}, indent=2))
    else:
        print(f"{heading}:")
        for error in errors:
            print(f"- {error}")
    return 1


def _gate_map(root: Path):
    return {gate.gate_id: gate for gate in list_gates(root)}


def _get_gate(root: Path, gate_id: str):
    path_errors = governed_path_errors(root)
    if path_errors:
        raise ValueError(path_errors[0])
    try:
        requested = canonical_gate_id(gate_id)
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    gate = _gate_map(root).get(requested)
    if gate is None:
        raise ValueError(f"unknown gate '{requested}'")
    return gate


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original_mode = None
    if path.exists() and not path.is_symlink():
        original_mode = path.stat().st_mode & 0o7777
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if original_mode is not None:
            os.chmod(tmp_name, original_mode)
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def _write_with_rollback(path: Path, new_text: str, root: Path, *, strict: bool = False) -> list[str]:
    old_text = path.read_text(encoding="utf-8")
    _atomic_write(path, new_text)
    errors = validate_project(root, strict=strict)
    if errors:
        _atomic_write(path, old_text)
    return errors


def _invalidate_approval_if_needed(text: str, timestamp: str, reason: str) -> str:
    # Read through parse-compatible metadata values without exposing another public API.
    metadata_body = _section(text, "Metadata") or ""
    if not re.search(r"^- Approval:\s*APPROVED\s*$", metadata_body, re.MULTILINE | re.IGNORECASE):
        return text
    text = replace_metadata(text, "Reviewer", "Unassigned")
    text = replace_metadata(text, "Approval", "PENDING")
    text = replace_metadata(text, "Approved-On", "None")
    text = replace_metadata(text, "Approval-Fingerprint", "None")
    text = append_section_line(text, "Work Log", f"- {timestamp} | APPROVAL_INVALIDATED | {reason}")
    return text


def _invalidate_verification_if_needed(text: str, timestamp: str, reason: str) -> str:
    checks = parse_stage_checks(text)
    metadata = _section(text, "Metadata") or ""
    verified = bool(checks and checks[STAGES.index("Verify")]) or not re.search(
        r"^- Verification-Fingerprint:\s*None\s*$", metadata, re.MULTILINE | re.IGNORECASE
    )
    text = _invalidate_approval_if_needed(text, timestamp, reason)
    if not verified:
        return text
    text = set_named_checkbox(text, "Verify", False)
    text = set_named_checkbox(text, "Close Gate", False)
    history = _section(text, "Stage History") or ""
    hlines = [line for line in history.splitlines() if not re.search(r"\| (Verify|Close Gate) \| completed$", line)]
    text = replace_section(text, "Stage History", "\n".join(hlines) if hlines else "- None yet.")
    work = _section(text, "Work Log") or ""
    wlines = [line for line in work.splitlines() if not re.search(r"\| (Verify|Close Gate) \|", line)]
    text = replace_section(text, "Work Log", "\n".join(wlines) if wlines else "- None yet.")
    text = replace_metadata(text, "Current-Stage", "Verify")
    text = replace_metadata(text, "Verified-On", "None")
    text = replace_metadata(text, "Verification-Fingerprint", "None")
    text = append_section_line(text, "Work Log", f"- {timestamp} | VERIFICATION_INVALIDATED | {reason}")
    return text


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    path_errors = governed_path_errors(root)
    if path_errors:
        return _print_errors(path_errors, heading="Cannot initialize an unsafe AQG workspace")
    qdir = project_dir(root)
    gd = gates_dir(root)
    gd.mkdir(parents=True, exist_ok=True)
    workspace_readme = qdir / "README.md"
    if not workspace_readme.exists():
        _atomic_write(
            workspace_readme,
            "# AI Quality Gates Workspace\n\n"
            "Gate records live in `gates/`; policy lives in `policy.toml`.\n\n"
            "Recommended flow: `aqg new` → edit DRAFT → `aqg start` → `aqg advance` → "
            "`aqg add-evidence` / `aqg satisfy` → `aqg verify` → `aqg approve` → `aqg close`.\n\n"
            "Use `aqg validate --strict` for record integrity and `aqg release-check` for release readiness.\n\n"
            "AQG v0.1 uses a single-writer model: do not run concurrent AQG mutations against the same workspace.\n",
        )
    ppath = policy_path(root)
    if not ppath.exists():
        _atomic_write(ppath, render_default_policy())
    print(f"Initialized AI Quality Gates in {qdir}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    gd = gates_dir(root)
    gd.mkdir(parents=True, exist_ok=True)

    project_errors = validate_project(root, strict=False)
    if project_errors:
        return _print_errors(project_errors, heading="Cannot create a gate while the workspace is invalid")

    try:
        deps = [canonical_gate_id(dep) for dep in (args.depends_on or [])]
    except Exception as exc:
        return _print_errors([str(exc)])
    if len(set(deps)) != len(deps):
        return _print_errors(["duplicate dependencies are not allowed"])

    known = _gate_map(root)
    unknown = [dep for dep in deps if dep not in known]
    if unknown:
        return _print_errors([f"unknown dependency '{dep}'" for dep in unknown])

    try:
        policy = load_policy(root)
    except Exception as exc:
        return _print_errors([str(exc)])
    severity = args.severity.lower()
    if args.review_required == "no" and severity in policy.review_required_severities:
        return _print_errors([
            f"policy requires independent review for {severity} severity; change policy.toml explicitly to allow otherwise"
        ])

    gate_id = next_gate_id(root)
    try:
        text = render_gate(gate_id, args.title, severity, deps)
    except Exception as exc:
        return _print_errors([str(exc)])
    if args.review_required == "no":
        text = replace_metadata(text, "Review-Required", "NO")
        text = replace_metadata(text, "Approval", "NOT_REQUIRED")

    path = gd / f"{gate_id}.md"
    candidate_known = set(known) | {gate_id}
    candidate_errors = validate_gate_text(text, path, candidate_known, root, strict=False, policy=policy)
    if candidate_errors:
        return _print_errors(candidate_errors, heading="Prospective gate failed validation")

    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        return _print_errors([f"{path} already exists; another writer may have created the same gate ID"])

    print(f"Created {path}")
    print(f"Status: DRAFT. Replace placeholders, then run `aqg start {gate_id}`.")
    return 0


def _status_rows(root: Path) -> list[dict[str, str]]:
    gates = list_gates(root)
    gate_by_id = {g.gate_id: g for g in gates}
    rows = []
    for gate in gates:
        state = operational_state(root, gate, gate_by_id)
        blockers = [dep for dep in gate.dependencies if dep not in gate_by_id or not gate_by_id[dep].closed]
        rows.append(
            {
                "gate": gate.gate_id,
                "severity": gate.severity.upper(),
                "state": state,
                "stage": gate.current_stage,
                "blocked_by": ",".join(blockers) if blockers else "-",
                "title": gate.title,
            }
        )
    state_order = {"IN_PROGRESS": 0, "READY": 1, "BLOCKED": 2, "DRAFT": 3, "DEFERRED": 4, "WAIVED": 5, "CLOSED": 6}
    return sorted(rows, key=lambda r: (SEVERITY_ORDER[r["severity"].lower()], state_order.get(r["state"], 99), r["gate"]))


def cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    errors = validate_project(root, strict=False)
    rows = _status_rows(root)
    if args.json:
        print(json.dumps({"schema_version": 1, "gates": rows, "errors": errors}, indent=2))
        return 1 if errors else 0
    if not rows:
        print("No gates found. Run `aqg init` and `aqg new \"Your gate\"`.")
        return 1 if errors else 0
    print(f"{'GATE':<11} {'SEVERITY':<9} {'STATE':<12} {'STAGE':<12} {'BLOCKED BY':<16} TITLE")
    print("-" * 108)
    for row in rows:
        print(f"{row['gate']:<11} {row['severity']:<9} {row['state']:<12} {row['stage']:<12} {row['blocked_by']:<16} {row['title']}")
    if errors:
        print("\nStructural warnings/errors:")
        for error in errors:
            print(f"- {error}")
        return 1
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    errors = validate_project(root, strict=True)
    if errors:
        return _print_errors(errors, json_mode=args.json, heading="Cannot schedule work from an invalid workspace")
    rows = _status_rows(root)
    candidates = [row for row in rows if row["state"] in {"IN_PROGRESS", "READY"}]
    if not candidates:
        payload = {"next": None, "message": "No executable gate. Resolve blockers or prepare a DRAFT gate."}
        if args.json:
            print(json.dumps({"schema_version": 1, **payload}, indent=2))
        else:
            print(payload["message"])
        return 0
    choice = candidates[0]
    if args.json:
        print(json.dumps({"schema_version": 1, "next": choice}, indent=2))
    else:
        print(f"{choice['gate']} [{choice['severity']}] {choice['state']} — {choice['title']}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    errors = validate_project(root, strict=args.strict)
    if errors:
        return _print_errors(errors, json_mode=args.json)
    if args.json:
        print(json.dumps({"schema_version": 1, "valid": True, "strict": args.strict, "errors": []}, indent=2))
    else:
        mode = "strict " if args.strict else ""
        print(f"Validation passed: {mode}record structure, identity, sequencing, evidence references, policy, and closure invariants are consistent.")
    return 0


def cmd_release_check(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    errors = release_check(root)
    if errors:
        return _print_errors(errors, json_mode=args.json, heading="Release check failed", json_key="release_ready")
    if args.json:
        print(json.dumps({"schema_version": 1, "release_ready": True, "errors": []}, indent=2))
    else:
        print("Release check passed: all release-blocking gates satisfy policy.")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    try:
        gate = _get_gate(root, args.gate_id)
    except ValueError as exc:
        return _print_errors([str(exc)])
    if gate.status != "DRAFT":
        return _print_errors([f"{gate.gate_id}: only DRAFT gates can be started (current status: {gate.status})"])
    errors = draft_readiness_errors(root, gate.gate_id)
    if errors:
        return _print_errors(errors)

    timestamp = _now()
    text = gate.path.read_text(encoding="utf-8")
    text = replace_metadata(text, "Status", "OPEN")
    text = replace_metadata(text, "Started-On", timestamp)
    text = append_section_line(text, "Work Log", f"- {timestamp} | START | {args.note}")
    errors = _write_with_rollback(gate.path, text, root)
    if errors:
        return _print_errors(errors)
    print(f"Started {gate.gate_id}. Current stage: Analyze")
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    try:
        gate = _get_gate(root, args.gate_id)
    except ValueError as exc:
        return _print_errors([str(exc)])
    if gate.status != "OPEN":
        return _print_errors([f"{gate.gate_id}: only OPEN gates can advance (current status: {gate.status})"])

    project_errors = validate_project(root, strict=False)
    if project_errors:
        return _print_errors(project_errors)

    text = gate.path.read_text(encoding="utf-8")
    checks = parse_stage_checks(text)
    try:
        index = checks.index(False)
    except ValueError:
        return _print_errors([f"{gate.gate_id}: all stages are already complete"])
    stage = STAGES[index]
    if stage == "Verify":
        return _print_errors([f"{gate.gate_id}: use `aqg verify {gate.gate_id} --note ...` to attest the final material state"])
    if stage == "Close Gate":
        return _print_errors([f"{gate.gate_id}: use `aqg close {gate.gate_id} --confirm-no-regression` for the final stage"])

    timestamp = _now()
    text = set_named_checkbox(text, stage, True)
    text = append_section_line(text, "Stage History", f"- {timestamp} | {stage} | completed")
    text = append_section_line(text, "Work Log", f"- {timestamp} | {stage} | {args.note}")
    text = replace_metadata(text, "Current-Stage", STAGES[index + 1])
    errors = _write_with_rollback(gate.path, text, root)
    if errors:
        return _print_errors(errors)
    print(f"Completed {stage} for {gate.gate_id}. Next stage: {STAGES[index + 1]}")
    return 0


def cmd_add_evidence(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    try:
        gate = _get_gate(root, args.gate_id)
    except ValueError as exc:
        return _print_errors([str(exc)])
    if gate.status in {"CLOSED", "DEFERRED", "WAIVED"}:
        return _print_errors([f"{gate.gate_id}: evidence cannot be changed while status is {gate.status}"])

    text = gate.path.read_text(encoding="utf-8")
    required = {item_id: evidence_type for item_id, _, evidence_type, _ in parse_evidence_required(text)}
    if args.evidence_id not in required:
        return _print_errors([f"{gate.gate_id}: unknown evidence requirement '{args.evidence_id}'"])
    evidence_type = required[args.evidence_id]
    if args.type and args.type != evidence_type:
        return _print_errors([f"{gate.gate_id}: {args.evidence_id} requires type={evidence_type}, not type={args.type}"])
    ref_error = _valid_evidence_ref(root, evidence_type, args.ref, strict=True)
    if ref_error:
        return _print_errors([f"{gate.gate_id}: {args.evidence_id} {ref_error}"])

    timestamp = _now()
    text = _invalidate_verification_if_needed(text, timestamp, f"Evidence {args.evidence_id} changed after verification")
    body = _section(text, "Evidence Collected") or ""
    body_lines = [line for line in body.splitlines() if not line.startswith(f"- {args.evidence_id} |")]
    body_lines = [line for line in body_lines if line.strip().lower() not in {"- none yet.", "none yet."}]
    body_lines.append(f"- {args.evidence_id} | type={evidence_type} | ref={args.ref} | result={args.result} | note={args.note}")
    text = replace_section(text, "Evidence Collected", "\n".join(body_lines))
    if args.result == "PASS":
        text = set_id_checkbox(text, args.evidence_id, True)
    else:
        text = set_id_checkbox(text, args.evidence_id, False)
    errors = _write_with_rollback(gate.path, text, root, strict=True)
    if errors:
        return _print_errors(errors)
    print(f"Recorded {args.evidence_id} for {gate.gate_id}: {args.result}")
    return 0


def cmd_satisfy(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    try:
        gate = _get_gate(root, args.gate_id)
    except ValueError as exc:
        return _print_errors([str(exc)])
    if gate.status in {"CLOSED", "DEFERRED", "WAIVED"}:
        return _print_errors([f"{gate.gate_id}: criteria cannot be changed while status is {gate.status}"])

    text = gate.path.read_text(encoding="utf-8")
    criteria = {item_id for item_id, _, _ in parse_acceptance_criteria(text)}
    if args.criterion_id not in criteria:
        return _print_errors([f"{gate.gate_id}: unknown acceptance criterion '{args.criterion_id}'"])
    collected = {record.evidence_id: record for record in parse_evidence_collected(text)}
    missing = [item for item in args.evidence if item not in collected]
    if missing:
        return _print_errors([f"{gate.gate_id}: missing collected evidence '{item}'" for item in missing])
    not_pass = [item for item in args.evidence if collected[item].result != "PASS"]
    if not_pass:
        return _print_errors([f"{gate.gate_id}: evidence '{item}' is not PASS" for item in not_pass])

    timestamp = _now()
    text = _invalidate_verification_if_needed(text, timestamp, f"Verification mapping {args.criterion_id} changed after verification")
    text = set_id_checkbox(text, args.criterion_id, True)
    body = _section(text, "Verification") or ""
    lines = [line for line in body.splitlines() if not line.startswith(f"- {args.criterion_id} ->")]
    lines = [line for line in lines if line.strip().lower() not in {"- none yet.", "none yet."}]
    lines.append(f"- {args.criterion_id} -> {', '.join(args.evidence)} | {args.note}")
    text = replace_section(text, "Verification", "\n".join(lines))
    errors = _write_with_rollback(gate.path, text, root)
    if errors:
        return _print_errors(errors)
    print(f"Satisfied {args.criterion_id} for {gate.gate_id}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    try:
        gate = _get_gate(root, args.gate_id)
    except ValueError as exc:
        return _print_errors([str(exc)])
    errors = verification_precondition_errors(root, gate.gate_id, strict=True)
    if errors:
        return _print_errors(errors, heading="Verify preconditions failed")
    timestamp = _now()
    text = gate.path.read_text(encoding="utf-8")
    fingerprint = verification_fingerprint(text)
    text = set_named_checkbox(text, "Verify", True)
    text = append_section_line(text, "Stage History", f"- {timestamp} | Verify | completed")
    text = append_section_line(text, "Work Log", f"- {timestamp} | Verify | {args.note}")
    text = replace_metadata(text, "Current-Stage", "Close Gate")
    text = replace_metadata(text, "Verified-On", timestamp)
    text = replace_metadata(text, "Verification-Fingerprint", fingerprint)
    errors = _write_with_rollback(gate.path, text, root, strict=True)
    if errors:
        return _print_errors(errors)
    print(f"Verified final material state of {gate.gate_id}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    try:
        gate = _get_gate(root, args.gate_id)
    except ValueError as exc:
        return _print_errors([str(exc)])
    if not gate.review_required:
        print(f"{gate.gate_id}: independent review is not required by this gate/policy.")
        return 0
    if gate.status != "OPEN":
        return _print_errors([f"{gate.gate_id}: only OPEN gates can be approved"])

    errors = fresh_verification_errors(root, gate.gate_id, strict=True)
    if errors:
        return _print_errors(errors, heading="Approval preconditions failed")

    timestamp = _now()
    text = gate.path.read_text(encoding="utf-8")
    fingerprint = approval_fingerprint(text)
    text = replace_metadata(text, "Reviewer", args.reviewer)
    text = replace_metadata(text, "Approval", "APPROVED")
    text = replace_metadata(text, "Approved-On", timestamp)
    text = replace_metadata(text, "Approval-Fingerprint", fingerprint)
    text = append_section_line(text, "Work Log", f"- {timestamp} | APPROVAL | Approved by {args.reviewer}: {args.note}")
    errors = _write_with_rollback(gate.path, text, root, strict=True)
    if errors:
        return _print_errors(errors)
    print(f"Approved final verified state of {gate.gate_id} by {args.reviewer}")
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    if not args.confirm_no_regression:
        return _print_errors(["closure requires --confirm-no-regression"])
    try:
        gate_id = canonical_gate_id(args.gate_id)
    except Exception as exc:
        return _print_errors([str(exc)])
    errors = closure_precondition_errors(root, gate_id, strict=True)
    if errors:
        return _print_errors(errors)
    gate = _get_gate(root, gate_id)
    timestamp = _now()
    text = gate.path.read_text(encoding="utf-8")
    text = set_named_checkbox(text, "Close Gate", True)
    text = append_section_line(text, "Stage History", f"- {timestamp} | Close Gate | completed")
    text = append_section_line(text, "Work Log", f"- {timestamp} | Close Gate | {args.note}")
    text = replace_metadata(text, "Current-Stage", "COMPLETE")
    for label in (
        "All acceptance criteria satisfied",
        "Required evidence attached or referenced",
        "Dependencies closed",
        "No known Critical/High regression introduced",
        "Gate formally closed",
    ):
        text = set_named_checkbox(text, label, True)
    text = replace_metadata(text, "Status", "CLOSED")
    text = replace_metadata(text, "Closed-On", timestamp)
    text = replace_metadata(text, "Closure-Fingerprint", "None")
    text = replace_metadata(text, "Closure-Fingerprint", closure_fingerprint(text))
    errors = _write_with_rollback(gate.path, text, root, strict=True)
    if errors:
        return _print_errors(errors)
    print(f"Closed {gate.gate_id}. Strict record validation passed.")
    return 0


def _exception_transition(args: argparse.Namespace, status: str) -> int:
    root = Path(args.path).resolve()
    try:
        gate = _get_gate(root, args.gate_id)
    except ValueError as exc:
        return _print_errors([str(exc)])
    if gate.status == "CLOSED":
        return _print_errors([f"{gate.gate_id}: CLOSED gates cannot be {status.lower()}"])
    timestamp = _now()
    text = gate.path.read_text(encoding="utf-8")
    problem = _section(text, "Problem") or ""
    if not problem or _normalize(problem) in PROBLEM_PLACEHOLDERS:
        return _print_errors([f"{gate.gate_id}: {status} requires a concrete Problem statement before exception"])
    if status == "WAIVED":
        acs = parse_acceptance_criteria(text)
        reqs = parse_evidence_required(text)
        if not acs or any(_normalize(desc) in AC_PLACEHOLDERS for _, _, desc in acs):
            return _print_errors([f"{gate.gate_id}: WAIVED requires concrete Acceptance Criteria before exception"])
        if not reqs or any(_normalize(desc) in EVIDENCE_PLACEHOLDERS for _, _, _, desc in reqs):
            return _print_errors([f"{gate.gate_id}: WAIVED requires concrete Evidence Required before exception"])
    text = _invalidate_verification_if_needed(text, timestamp, f"Gate moved to {status}")
    text = replace_metadata(text, "Status", status)
    text = replace_metadata(text, "Exception-Reason", args.reason)
    text = replace_metadata(text, "Exception-By", args.by)
    text = replace_metadata(text, "Exception-On", timestamp)
    text = append_section_line(text, "Work Log", f"- {timestamp} | EXCEPTION | {status} by {args.by}: {args.reason}")
    errors = _write_with_rollback(gate.path, text, root)
    if errors:
        return _print_errors(errors)
    print(f"{status.title()} {gate.gate_id}")
    return 0


def cmd_defer(args: argparse.Namespace) -> int:
    return _exception_transition(args, "DEFERRED")


def cmd_waive(args: argparse.Namespace) -> int:
    return _exception_transition(args, "WAIVED")


def cmd_resume(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    try:
        gate = _get_gate(root, args.gate_id)
    except ValueError as exc:
        return _print_errors([str(exc)])
    if gate.status not in {"DEFERRED", "WAIVED"}:
        return _print_errors([f"{gate.gate_id}: only DEFERRED or WAIVED gates can be resumed"])
    status = "DRAFT" if gate.started_on.strip().lower() == "none" else "OPEN"
    timestamp = _now()
    text = gate.path.read_text(encoding="utf-8")
    text = replace_metadata(text, "Status", status)
    text = replace_metadata(text, "Exception-Reason", "None")
    text = replace_metadata(text, "Exception-By", "None")
    text = replace_metadata(text, "Exception-On", "None")
    text = append_section_line(text, "Work Log", f"- {timestamp} | RESUME | {args.note}")
    errors = _write_with_rollback(gate.path, text, root)
    if errors:
        return _print_errors(errors)
    print(f"Resumed {gate.gate_id} as {status}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aqg", description="AI Quality Gates Framework CLI")
    parser.add_argument("--version", action="version", version=f"aqg {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize a quality-gates workspace and default policy")
    p_init.add_argument("path", nargs="?", default=".")
    p_init.set_defaults(func=cmd_init)

    p_new = sub.add_parser("new", help="Create a new validated DRAFT gate")
    p_new.add_argument("title")
    p_new.add_argument("--severity", choices=["critical", "high", "medium", "low"], default="medium")
    p_new.add_argument("--depends-on", action="append", default=[])
    p_new.add_argument("--review-required", choices=["yes", "no"], default="yes")
    p_new.add_argument("--path", default=".")
    p_new.set_defaults(func=cmd_new)

    p_status = sub.add_parser("status", help="Show lifecycle and dependency-aware gate status")
    p_status.add_argument("path", nargs="?", default=".")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    p_next = sub.add_parser("next", help="Show the next executable gate; refuses invalid workspaces")
    p_next.add_argument("path", nargs="?", default=".")
    p_next.add_argument("--json", action="store_true")
    p_next.set_defaults(func=cmd_next)

    p_validate = sub.add_parser("validate", help="Validate record structure and governance invariants")
    p_validate.add_argument("path", nargs="?", default=".")
    p_validate.add_argument("--strict", action="store_true", help="Require workspace/gates and verify local evidence files")
    p_validate.add_argument("--json", action="store_true")
    p_validate.set_defaults(func=cmd_validate)

    p_release = sub.add_parser("release-check", help="Enforce release policy after strict record validation")
    p_release.add_argument("path", nargs="?", default=".")
    p_release.add_argument("--json", action="store_true")
    p_release.set_defaults(func=cmd_release_check)

    p_start = sub.add_parser("start", help="Start a READY DRAFT gate")
    p_start.add_argument("gate_id")
    p_start.add_argument("--note", required=True, help="Reason/context for starting the gate")
    p_start.add_argument("--path", default=".")
    p_start.set_defaults(func=cmd_start)

    p_advance = sub.add_parser("advance", help="Complete the current stage and move to the next stage")
    p_advance.add_argument("gate_id")
    p_advance.add_argument("--note", required=True, help="Material work/result for the completed stage")
    p_advance.add_argument("--path", default=".")
    p_advance.set_defaults(func=cmd_advance)

    p_evidence = sub.add_parser("add-evidence", help="Record objective evidence against an EVID-* requirement")
    p_evidence.add_argument("gate_id")
    p_evidence.add_argument("evidence_id")
    p_evidence.add_argument("--type", choices=sorted(EVIDENCE_TYPES))
    p_evidence.add_argument("--ref", required=True, help="file:path, url:https://..., commit:sha, or manual:name for approvals")
    p_evidence.add_argument("--result", choices=["PASS", "FAIL", "N/A"], default="PASS")
    p_evidence.add_argument("--note", required=True)
    p_evidence.add_argument("--path", default=".")
    p_evidence.set_defaults(func=cmd_add_evidence)

    p_satisfy = sub.add_parser("satisfy", help="Mark an AC-* criterion satisfied and map it to PASS evidence")
    p_satisfy.add_argument("gate_id")
    p_satisfy.add_argument("criterion_id")
    p_satisfy.add_argument("--evidence", action="append", required=True)
    p_satisfy.add_argument("--note", required=True)
    p_satisfy.add_argument("--path", default=".")
    p_satisfy.set_defaults(func=cmd_satisfy)

    p_verify = sub.add_parser("verify", help="Verify the final material state after Re-test and evidence mapping")
    p_verify.add_argument("gate_id")
    p_verify.add_argument("--note", required=True)
    p_verify.add_argument("--path", default=".")
    p_verify.set_defaults(func=cmd_verify)

    p_approve = sub.add_parser("approve", help="Approve the final verified state; only valid after Verify")
    p_approve.add_argument("gate_id")
    p_approve.add_argument("--reviewer", required=True)
    p_approve.add_argument("--note", required=True)
    p_approve.add_argument("--path", default=".")
    p_approve.set_defaults(func=cmd_approve)

    p_close = sub.add_parser("close", help="Formally close a fully verified and approved gate")
    p_close.add_argument("gate_id")
    p_close.add_argument("--confirm-no-regression", action="store_true")
    p_close.add_argument("--note", required=True)
    p_close.add_argument("--path", default=".")
    p_close.set_defaults(func=cmd_close)

    for name, handler, help_text in [
        ("defer", cmd_defer, "Defer a gate with an auditable exception"),
        ("waive", cmd_waive, "Waive a gate without treating it as verified closure"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("gate_id")
        p.add_argument("--reason", required=True)
        p.add_argument("--by", required=True, dest="by")
        p.add_argument("--path", default=".")
        p.set_defaults(func=handler)

    p_resume = sub.add_parser("resume", help="Resume a DEFERRED or WAIVED gate")
    p_resume.add_argument("gate_id")
    p_resume.add_argument("--note", required=True)
    p_resume.add_argument("--path", default=".")
    p_resume.set_defaults(func=cmd_resume)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
