import tempfile
import unittest
from pathlib import Path

from ai_quality_gates.core import (
    STAGES,
    append_section_line,
    approval_fingerprint,
    closure_fingerprint,
    gates_dir,
    next_gate_id,
    operational_state,
    parse_gate,
    render_gate,
    replace_metadata,
    replace_section,
    set_id_checkbox,
    set_named_checkbox,
    verification_fingerprint,
    validate_project,
)


from helpers import ready_text, start_text, complete_stage, fully_closed_text


class QualityGatesTests(unittest.TestCase):
    def test_next_gate_id_supports_more_than_999(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gates_dir(root).mkdir(parents=True)
            (gates_dir(root) / "GATE-999.md").write_text("x", encoding="utf-8")
            self.assertEqual(next_gate_id(root), "GATE-1000")

    def test_draft_template_is_structurally_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(render_gate("GATE-001", "Draft", "medium"), encoding="utf-8")
            self.assertEqual(validate_project(root, strict=True), [])

    def test_strict_missing_workspace_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            errors = validate_project(Path(tmp), strict=True)
            self.assertTrue(any("workspace not found" in error for error in errors))

    def test_malformed_gate_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text("broken", encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertTrue(any("invalid gate title" in error for error in errors))

    def test_header_id_must_match_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(render_gate("GATE-002", "Mismatch", "high"), encoding="utf-8")
            errors = validate_project(root)
            self.assertTrue(any("does not match filename" in error for error in errors))

    def test_duplicate_logical_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(render_gate("GATE-001", "One", "high"), encoding="utf-8")
            (gd / "GATE-0001.md").write_text(render_gate("GATE-001", "Duplicate", "medium"), encoding="utf-8")
            errors = validate_project(root)
            self.assertTrue(any("duplicate logical gate ID" in error for error in errors))

    def test_unknown_dependency_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(render_gate("GATE-001", "One", "high", ["GATE-999"]), encoding="utf-8")
            errors = validate_project(root)
            self.assertTrue(any("unknown dependency 'GATE-999'" in error for error in errors))

    def test_dependency_cycle_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(render_gate("GATE-001", "First", "high", ["GATE-002"]), encoding="utf-8")
            (gd / "GATE-002.md").write_text(render_gate("GATE-002", "Second", "high", ["GATE-001"]), encoding="utf-8")
            errors = validate_project(root)
            self.assertTrue(any("dependency cycle detected" in error for error in errors))

    def test_out_of_sequence_stage_check_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            text = ready_text()
            text = start_text(text)
            text = set_named_checkbox(text, "Execute", True)
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root)
            self.assertTrue(any("out of sequence" in error for error in errors))

    def test_stage_history_required_for_checked_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            text = ready_text()
            text = start_text(text)
            text = set_named_checkbox(text, "Analyze", True)
            text = replace_metadata(text, "Current-Stage", "Prepare")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root)
            self.assertTrue(any("stage history does not match" in error for error in errors))

    def test_open_gate_cannot_start_over_open_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(ready_text("GATE-001"), encoding="utf-8")
            child = start_text(ready_text("GATE-002", dependencies=["GATE-001"]))
            (gd / "GATE-002.md").write_text(child, encoding="utf-8")
            errors = validate_project(root)
            self.assertTrue(any("open while dependency GATE-001 is not closed" in error for error in errors))

    def test_closed_gate_with_placeholder_acceptance_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            text = fully_closed_text(root)
            text = replace_section(text, "Acceptance Criteria", "- [x] AC-001 | Describe an objective, testable outcome.")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertTrue(any("placeholder acceptance criterion" in error or "AC-001 is still a placeholder" in error for error in errors))

    def test_closed_gate_with_placeholder_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            text = fully_closed_text(root)
            text = replace_section(text, "Evidence Required", "- [x] EVID-001 | type=test | Describe the objective evidence required.")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertTrue(any("placeholder evidence" in error or "EVID-001 is still a placeholder" in error for error in errors))

    def test_strict_validation_checks_local_evidence_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            text = fully_closed_text(root)
            (root / "artifacts" / "test-results.txt").unlink()
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertTrue(any("file evidence does not exist" in error for error in errors))

    def test_evidence_cannot_escape_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            text = fully_closed_text(root)
            text = text.replace("ref=file:artifacts/test-results.txt", "ref=file:../outside.txt")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertTrue(any("escapes the project root" in error for error in errors))

    def test_closed_gate_requires_verification_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            text = fully_closed_text(root)
            text = replace_section(text, "Verification", "- None yet.")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertTrue(any("lacks verification mapping" in error for error in errors))

    def test_waiver_requires_auditable_exception_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            text = ready_text()
            text = replace_metadata(text, "Status", "WAIVED")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root)
            self.assertTrue(any("requires Exception-Reason" in error for error in errors))
            self.assertTrue(any("requires Exception-By" in error for error in errors))

    def test_operational_state_distinguishes_ready_and_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(ready_text("GATE-001"), encoding="utf-8")
            (gd / "GATE-002.md").write_text(ready_text("GATE-002", dependencies=["GATE-001"]), encoding="utf-8")
            gates = {gate.gate_id: gate for gate in [parse_gate(gd / "GATE-001.md"), parse_gate(gd / "GATE-002.md")]}
            self.assertEqual(operational_state(root, gates["GATE-001"], gates), "READY")
            self.assertEqual(operational_state(root, gates["GATE-002"], gates), "BLOCKED")

    def test_closed_gate_requires_independent_approval_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            text = fully_closed_text(root)
            text = replace_metadata(text, "Reviewer", "Unassigned")
            text = replace_metadata(text, "Approval", "PENDING")
            text = replace_metadata(text, "Approved-On", "None")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertTrue(any("requires independent approval" in error for error in errors))

    def test_fully_closed_gate_with_real_evidence_passes_strict_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(fully_closed_text(root), encoding="utf-8")
            self.assertEqual(validate_project(root, strict=True), [])

    def test_strict_workspace_with_no_gates_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gates_dir(root).mkdir(parents=True)
            errors = validate_project(root, strict=True)
            self.assertTrue(any("no gate records found" in error for error in errors))

    def test_invalid_naive_timestamp_fails_without_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            text = ready_text()
            text = start_text(text, "2026-09-27T12:00:00")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root)
            self.assertTrue(any("valid Started-On timestamp" in error for error in errors))

    def test_failed_evidence_can_be_recorded_while_gate_is_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            evidence = root / "artifacts" / "failed.txt"
            evidence.parent.mkdir(parents=True)
            evidence.write_text("FAIL\n", encoding="utf-8")
            text = start_text(ready_text())
            text = replace_section(
                text,
                "Evidence Collected",
                "- EVID-001 | type=test | ref=file:artifacts/failed.txt | result=FAIL | note=Regression still reproduces",
            )
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertFalse(any("result is FAIL" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
