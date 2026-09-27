from pathlib import Path

from ai_quality_gates.core import (
    STAGES, append_section_line, approval_fingerprint, closure_fingerprint,
    render_gate, replace_metadata, replace_section, set_id_checkbox,
    set_named_checkbox, verification_fingerprint,
)

def ready_text(gate_id="GATE-001", title="Example", severity="high", dependencies=None):
    text = render_gate(gate_id, title, severity, dependencies or [])
    text = replace_section(text, "Problem", "A concrete defect exists and must be resolved.")
    text = replace_section(text, "Acceptance Criteria", "- [ ] AC-001 | The concrete defect is no longer reproducible.")
    text = replace_section(
        text,
        "Evidence Required",
        "- [ ] EVID-001 | type=test | A reproducible regression test passes.",
    )
    return text


def start_text(text: str, timestamp="2026-09-27T12:00:00Z") -> str:
    text = replace_metadata(text, "Status", "OPEN")
    text = replace_metadata(text, "Started-On", timestamp)
    text = append_section_line(text, "Work Log", f"- {timestamp} | START | Gate execution started after readiness review")
    return text


def complete_stage(text: str, stage: str, index: int) -> str:
    timestamp = f"2026-09-27T12:{index:02d}:00Z"
    text = set_named_checkbox(text, stage, True)
    text = append_section_line(text, "Stage History", f"- {timestamp} | {stage} | completed")
    text = append_section_line(text, "Work Log", f"- {timestamp} | {stage} | Completed {stage} with recorded objective work")
    next_stage = STAGES[index + 1] if index + 1 < len(STAGES) else "COMPLETE"
    text = replace_metadata(text, "Current-Stage", next_stage)
    return text


def fully_closed_text(root: Path, gate_id="GATE-001", dependencies=None, review_required=True, severity=None):
    evidence = root / "artifacts" / "test-results.txt"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("PASS\n", encoding="utf-8")

    text = ready_text(gate_id, severity=severity or ("high" if review_required else "medium"), dependencies=dependencies)
    if not review_required:
        text = replace_metadata(text, "Review-Required", "NO")
        text = replace_metadata(text, "Approval", "NOT_REQUIRED")
    text = start_text(text)
    for index, stage in enumerate(STAGES[:-1]):
        text = complete_stage(text, stage, index)
    text = replace_section(
        text,
        "Evidence Collected",
        "- EVID-001 | type=test | ref=file:artifacts/test-results.txt | result=PASS | note=Regression test passed",
    )
    text = set_id_checkbox(text, "EVID-001", True)
    text = set_id_checkbox(text, "AC-001", True)
    text = replace_section(
        text,
        "Verification",
        "- AC-001 -> EVID-001 | Passing regression evidence proves the criterion.",
    )
    text = replace_metadata(text, "Verified-On", "2026-09-27T12:07:00Z")
    text = replace_metadata(text, "Verification-Fingerprint", verification_fingerprint(text))
    if review_required:
        approved_on = "2026-09-27T12:08:00Z"
        fingerprint = approval_fingerprint(text)
        text = replace_metadata(text, "Reviewer", "Independent Reviewer")
        text = replace_metadata(text, "Approval", "APPROVED")
        text = replace_metadata(text, "Approved-On", approved_on)
        text = replace_metadata(text, "Approval-Fingerprint", fingerprint)
        text = append_section_line(
            text,
            "Work Log",
            f"- {approved_on} | APPROVAL | Independent review approved the final verified state",
        )
    text = complete_stage(text, "Close Gate", 8)
    for label in [
        "All acceptance criteria satisfied",
        "Required evidence attached or referenced",
        "Dependencies closed",
        "No known Critical/High regression introduced",
        "Gate formally closed",
    ]:
        text = set_named_checkbox(text, label, True)
    text = replace_metadata(text, "Status", "CLOSED")
    text = replace_metadata(text, "Closed-On", "2026-09-27T12:08:00Z")
    text = replace_metadata(text, "Closure-Fingerprint", closure_fingerprint(text))
    return text

