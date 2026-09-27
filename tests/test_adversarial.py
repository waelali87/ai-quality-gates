import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ai_quality_gates.cli import _invalidate_approval_if_needed
from ai_quality_gates.core import (
    STAGES,
    append_section_line,
    approval_fingerprint,
    gates_dir,
    policy_path,
    parse_gate,
    release_check,
    render_gate,
    replace_metadata,
    replace_section,
    set_id_checkbox,
    set_named_checkbox,
    validate_project,
)
from helpers import ready_text, start_text, complete_stage, fully_closed_text


class AdversarialCoreTests(unittest.TestCase):
    def test_release_check_blocks_critical_draft_while_strict_structure_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root); gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(ready_text(severity="critical"), encoding="utf-8")
            self.assertEqual(validate_project(root, strict=True), [])
            self.assertTrue(any("release blocked" in e for e in release_check(root)))

    def test_release_check_allows_medium_draft_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root); gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(ready_text(severity="medium"), encoding="utf-8")
            self.assertEqual(release_check(root), [])

    def test_release_check_blocks_critical_waiver_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root); gd.mkdir(parents=True)
            text = ready_text(severity="critical")
            text = replace_metadata(text, "Status", "WAIVED")
            text = replace_metadata(text, "Exception-Reason", "Temporary business exception")
            text = replace_metadata(text, "Exception-By", "Release Manager")
            text = replace_metadata(text, "Exception-On", "2026-09-27T12:00:00Z")
            text = append_section_line(text, "Work Log", "- 2026-09-27T12:00:00Z | EXCEPTION | WAIVED by Release Manager: Temporary business exception")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            self.assertEqual(validate_project(root, strict=True), [])
            self.assertTrue(any("WAIVED" in e for e in release_check(root)))


    def test_policy_can_explicitly_allow_waived_blocking_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root); gd.mkdir(parents=True)
            (root / ".quality-gates" / "policy.toml").write_text(
                '[release]\nblocking_severities=["critical","high"]\nallow_waived_blocking=true\nallow_deferred_blocking=false\n\n[review]\nrequired_severities=["critical","high"]\n',
                encoding="utf-8",
            )
            text = ready_text(severity="critical")
            text = replace_metadata(text, "Status", "WAIVED")
            text = replace_metadata(text, "Exception-Reason", "Authorized release exception")
            text = replace_metadata(text, "Exception-By", "Release Manager")
            text = replace_metadata(text, "Exception-On", "2026-09-27T12:00:00Z")
            text = append_section_line(text, "Work Log", "- 2026-09-27T12:00:00Z | EXCEPTION | WAIVED by Release Manager: Authorized release exception")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            self.assertEqual(release_check(root), [])

    def test_acceptance_criterion_in_wrong_section_does_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = render_gate("GATE-001", "Wrong section", "medium")
            text = replace_section(text, "Problem", "Concrete problem.\n- [ ] AC-001 | Wrongly placed criterion")
            text = replace_section(text, "Acceptance Criteria", "No structured criterion here.")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertTrue(any("Acceptance Criteria" in e for e in errors))

    def test_evidence_requirement_in_wrong_section_does_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = render_gate("GATE-001", "Wrong evidence section", "medium")
            text = replace_section(text, "Problem", "Concrete problem.\n- [ ] EVID-001 | type=test | Wrongly placed evidence")
            text = replace_section(text, "Evidence Required", "No structured evidence here.")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertTrue(any("Evidence Required" in e for e in errors))

    def test_stage_checkbox_outside_execution_cycle_does_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = render_gate("GATE-001", "Wrong stage", "medium")
            text = replace_section(text, "Problem", "Concrete problem.\n- [x] Analyze")
            body = replace_section(text, "Execution Cycle", "\n".join(f"- [ ] {s}" for s in STAGES[1:]))
            (gd / "GATE-001.md").write_text(body, encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertTrue(any("exactly the 9 canonical stages" in e for e in errors))

    def test_duplicate_required_section_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = render_gate("GATE-001", "Duplicate section", "medium")
            text += "\n## Acceptance Criteria\n- [ ] AC-002 | Another criterion.\n"
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            self.assertTrue(any("duplicate heading" in e for e in validate_project(root, strict=True)))

    def test_required_sections_out_of_order_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = render_gate("GATE-001", "Order", "medium")
            problem = "## Problem\nDescribe the defect, risk, gap, or requirement this gate resolves.\n\n"
            acceptance = "## Acceptance Criteria\n- [ ] AC-001 | Describe an objective, testable outcome.\n\n"
            text = text.replace(problem + acceptance, acceptance + problem)
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            self.assertTrue(any("canonical order" in e for e in validate_project(root, strict=True)))

    def test_unknown_metadata_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = render_gate("GATE-001", "Unknown metadata", "medium")
            text = text.replace("- Status: DRAFT", "- Status: DRAFT\n- Hidden-Override: YES")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            self.assertTrue(any("unexpected metadata 'Hidden-Override'" in e for e in validate_project(root, strict=True)))

    def test_duplicate_metadata_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = render_gate("GATE-001", "Duplicate metadata", "medium")
            text = text.replace("- Status: DRAFT", "- Status: DRAFT\n- Status: CLOSED")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            self.assertTrue(any("duplicate metadata 'Status'" in e for e in validate_project(root, strict=True)))

    def test_noncanonical_numeric_identity_is_rejected_and_collides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(render_gate("GATE-001", "Canonical", "medium"), encoding="utf-8")
            text = render_gate("GATE-001", "Alias", "medium").replace("# GATE-001", "# GATE-1", 1)
            (gd / "GATE-1.md").write_text(text, encoding="utf-8")
            errors = validate_project(root, strict=True)
            self.assertTrue(any("duplicate logical gate ID GATE-001" in e for e in errors))
            self.assertTrue(any("not canonical" in e for e in errors))

    def test_misnamed_markdown_file_in_gates_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(render_gate("GATE-001", "Valid", "medium"), encoding="utf-8")
            (gd / "gate-002.md").write_text("broken", encoding="utf-8")
            self.assertTrue(any("unexpected Markdown file" in e for e in validate_project(root, strict=True)))

    def test_open_gate_cannot_have_close_gate_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = start_text(ready_text(severity="medium"))
            for i, stage in enumerate(STAGES):
                text = complete_stage(text, stage, i)
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            errors = validate_project(root)
            self.assertTrue(any("OPEN gate cannot have Close Gate completed" in e for e in errors))

    def test_stage_history_cannot_precede_started_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = start_text(ready_text(), "2026-09-27T12:10:00Z")
            text = complete_stage(text, "Analyze", 0)
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            self.assertTrue(any("precedes Started-On" in e for e in validate_project(root)))

    def test_policy_requires_review_for_critical_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = ready_text(severity="critical")
            text = replace_metadata(text, "Review-Required", "NO")
            text = replace_metadata(text, "Approval", "NOT_REQUIRED")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            self.assertTrue(any("policy requires independent review" in e for e in validate_project(root, strict=True)))

    def test_cli_mutation_helper_invalidates_existing_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = start_text(ready_text(severity="medium"))
            for i, stage in enumerate(STAGES[:-1]):
                text = complete_stage(text, stage, i)
            text = replace_metadata(text, "Reviewer", "QA")
            text = replace_metadata(text, "Approval", "APPROVED")
            text = replace_metadata(text, "Approved-On", "2026-09-27T12:08:00Z")
            text = replace_metadata(text, "Approval-Fingerprint", approval_fingerprint(text))
            text = append_section_line(text, "Work Log", "- 2026-09-27T12:08:00Z | APPROVAL | QA approved final verified state")
            mutated = _invalidate_approval_if_needed(text, "2026-09-27T12:09:00Z", "Evidence changed")
            path = gd / "GATE-001.md"; path.write_text(mutated, encoding="utf-8")
            gate = parse_gate(path)
            self.assertEqual(gate.approval, "PENDING")
            self.assertEqual(gate.reviewer, "Unassigned")
            self.assertEqual(gate.approval_fingerprint, "None")
            self.assertIn("APPROVAL_INVALIDATED", mutated)

    def test_manual_change_after_approval_makes_approval_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            evidence = root / "artifacts" / "proof.txt"; evidence.parent.mkdir(); evidence.write_text("PASS\n")
            text = start_text(ready_text(severity="medium"))
            for i, stage in enumerate(STAGES[:-1]):
                text = complete_stage(text, stage, i)
            text = replace_section(text, "Evidence Collected", "- EVID-001 | type=test | ref=file:artifacts/proof.txt | result=PASS | note=Proof passed")
            text = set_id_checkbox(text, "EVID-001", True)
            text = set_id_checkbox(text, "AC-001", True)
            text = replace_section(text, "Verification", "- AC-001 -> EVID-001 | Evidence proves criterion")
            fp = approval_fingerprint(text)
            text = replace_metadata(text, "Reviewer", "Reviewer")
            text = replace_metadata(text, "Approval", "APPROVED")
            text = replace_metadata(text, "Approved-On", "2026-09-27T12:08:00Z")
            text = replace_metadata(text, "Approval-Fingerprint", fp)
            text = append_section_line(text, "Work Log", "- 2026-09-27T12:08:00Z | APPROVAL | Reviewer approved final verified state")
            text = replace_section(text, "Problem", "Materially changed problem after approval.")
            (gd / "GATE-001.md").write_text(text, encoding="utf-8")
            self.assertTrue(any("approval is stale" in e for e in validate_project(root, strict=True)))


class AdversarialCliTests(unittest.TestCase):
    def run_cli(self, *args: str, expect=0):
        result = subprocess.run([sys.executable, "-m", "ai_quality_gates.cli", *args], text=True, capture_output=True)
        self.assertEqual(result.returncode, expect, msg=f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        return result

    def test_next_refuses_invalid_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Valid", "--path", str(root))
            (root / ".quality-gates" / "gates" / "GATE-002.md").write_text("broken", encoding="utf-8")
            result = self.run_cli("next", str(root), expect=1)
            self.assertIn("Cannot schedule work", result.stdout)

    def test_new_rejects_duplicate_dependencies_without_writing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Parent", "--path", str(root))
            self.run_cli(
                "new", "Child", "--depends-on", "GATE-001", "--depends-on", "GATE-001", "--path", str(root), expect=1
            )
            self.assertFalse((root / ".quality-gates" / "gates" / "GATE-002.md").exists())

    def test_new_rejects_review_bypass_for_critical_by_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            result = self.run_cli("new", "Critical", "--severity", "critical", "--review-required", "no", "--path", str(root), expect=1)
            self.assertIn("policy requires independent review", result.stdout)

    def test_approve_is_refused_before_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Needs review", "--path", str(root))
            gate = root / ".quality-gates" / "gates" / "GATE-001.md"
            text = gate.read_text()
            text = text.replace("Describe the defect, risk, gap, or requirement this gate resolves.", "Concrete problem.")
            text = text.replace("Describe an objective, testable outcome.", "Concrete outcome.")
            text = text.replace("Describe the objective evidence required.", "Concrete evidence.")
            gate.write_text(text)
            self.run_cli("start", "GATE-001", "--note", "Ready", "--path", str(root))
            result = self.run_cli("approve", "GATE-001", "--reviewer", "QA", "--note", "Too early", "--path", str(root), expect=1)
            self.assertIn("Analyze through Verify", result.stdout)

    def test_release_check_cli_blocks_critical_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Release blocker", "--severity", "critical", "--path", str(root))
            result = self.run_cli("release-check", str(root), expect=1)
            self.assertIn("Release check failed", result.stdout)


if __name__ == "__main__":
    unittest.main()

class GovernedPathSecurityTests(unittest.TestCase):
    def test_gates_directory_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            qdir = root / ".quality-gates"
            qdir.mkdir()
            (qdir / "gates").symlink_to(Path(outside), target_is_directory=True)
            errors = validate_project(root, strict=True)
            self.assertTrue(any("must not be a symbolic link" in e for e in errors))

    def test_symlinked_gate_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            target = Path(outside) / "GATE-001.md"
            target.write_text(ready_text(), encoding="utf-8")
            (gd / "GATE-001.md").symlink_to(target)
            errors = validate_project(root, strict=True)
            self.assertTrue(any("gate entries must not be symbolic links" in e for e in errors))

    def test_policy_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            gd = gates_dir(root)
            gd.mkdir(parents=True)
            (gd / "GATE-001.md").write_text(ready_text(), encoding="utf-8")
            target = Path(outside) / "policy.toml"
            target.write_text('[release]\nblocking_severities=["critical"]\n', encoding="utf-8")
            policy_path(root).symlink_to(target)
            errors = validate_project(root, strict=True)
            self.assertTrue(any("policy file must not be a symbolic link" in e for e in errors))

class VerificationFreshnessTests(unittest.TestCase):
    def run_cli(self, *args: str, expect=0):
        result = subprocess.run([sys.executable, "-m", "ai_quality_gates.cli", *args], text=True, capture_output=True)
        self.assertEqual(result.returncode, expect, msg=f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        return result

    def _prepare_to_retest(self, root: Path):
        self.run_cli("init", str(root))
        self.run_cli("new", "Verify freshness", "--severity", "high", "--path", str(root))
        gate = root / ".quality-gates" / "gates" / "GATE-001.md"
        text = gate.read_text()
        text = text.replace("Describe the defect, risk, gap, or requirement this gate resolves.", "Concrete defect is reproducible.")
        text = text.replace("Describe an objective, testable outcome.", "Concrete defect is no longer reproducible.")
        text = text.replace("Describe the objective evidence required.", "Regression evidence passes.")
        gate.write_text(text)
        self.run_cli("start", "GATE-001", "--note", "Ready", "--path", str(root))
        for note in ["analyzed", "prepared", "executed", "tested", "reviewed", "fixed", "retested"]:
            self.run_cli("advance", "GATE-001", "--note", note, "--path", str(root))
        evidence = root / "artifacts" / "proof file.txt"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("PASS\n")
        self.run_cli("add-evidence", "GATE-001", "EVID-001", "--ref", "file:artifacts/proof file.txt", "--result", "PASS", "--note", "proof passed", "--path", str(root))
        self.run_cli("satisfy", "GATE-001", "AC-001", "--evidence", "EVID-001", "--note", "proof maps to criterion", "--path", str(root))
        return gate

    def test_material_cli_change_after_verify_invalidates_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gate = self._prepare_to_retest(root)
            self.run_cli("verify", "GATE-001", "--note", "final state verified", "--path", str(root))
            self.run_cli("add-evidence", "GATE-001", "EVID-001", "--ref", "file:artifacts/proof file.txt", "--result", "PASS", "--note", "proof changed", "--path", str(root))
            text = gate.read_text()
            self.assertIn("- [ ] Verify", text)
            self.assertIn("- Verified-On: None", text)
            result = self.run_cli("approve", "GATE-001", "--reviewer", "QA", "--note", "should fail", "--path", str(root), expect=1)
            self.assertTrue("fresh verification" in result.stdout.lower() or "analyze through verify" in result.stdout.lower())

    def test_manual_change_after_verify_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gate = self._prepare_to_retest(root)
            self.run_cli("verify", "GATE-001", "--note", "verified", "--path", str(root))
            text = gate.read_text().replace("Concrete defect is reproducible.", "Materially changed defect after Verify.")
            gate.write_text(text)
            errors = validate_project(root, strict=True)
            self.assertTrue(any("verification is stale" in e for e in errors))

    def test_defer_resume_before_start_remains_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Lifecycle", "--review-required", "no", "--path", str(root))
            gate = root / ".quality-gates" / "gates" / "GATE-001.md"
            text = gate.read_text().replace("Describe the defect, risk, gap, or requirement this gate resolves.", "Concrete scoped problem.")
            gate.write_text(text)
            self.run_cli("defer", "GATE-001", "--reason", "External dependency", "--by", "Owner", "--path", str(root))
            self.run_cli("resume", "GATE-001", "--note", "Dependency resolved", "--path", str(root))
            # define remaining readiness after resume
            text = gate.read_text().replace("Describe an objective, testable outcome.", "Concrete result.").replace("Describe the objective evidence required.", "Concrete evidence.")
            gate.write_text(text)
            self.run_cli("start", "GATE-001", "--note", "Ready now", "--path", str(root))
            self.assertEqual(validate_project(root, strict=True), [])

    def test_waive_requires_defined_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Undefined waiver", "--severity", "medium", "--path", str(root))
            result = self.run_cli("waive", "GATE-001", "--reason", "Not doing", "--by", "Owner", "--path", str(root), expect=1)
            self.assertIn("concrete Problem", result.stdout)

    def test_closed_no_review_gate_detects_manual_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gd = gates_dir(root); gd.mkdir(parents=True)
            text = fully_closed_text(root, review_required=False)
            path = gd / "GATE-001.md"
            path.write_text(text)
            self.assertEqual(validate_project(root, strict=True), [])
            path.write_text(text.replace("A concrete defect exists", "Materially edited closed defect exists"))
            self.assertTrue(any("closure is stale" in e for e in validate_project(root, strict=True)))

class Rc2AdditionalHardeningTests(unittest.TestCase):
    def run_cli(self, *args: str, expect=0):
        result = subprocess.run([sys.executable, "-m", "ai_quality_gates.cli", *args], text=True, capture_output=True)
        self.assertEqual(result.returncode, expect, msg=f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        return result

    def test_workspace_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            (root / ".quality-gates").symlink_to(Path(outside), target_is_directory=True)
            self.assertTrue(any("workspace must not be a symbolic link" in e for e in validate_project(root, strict=True)))

    def test_fenced_h2_does_not_count_as_schema_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = ready_text()
            text = replace_section(text, "Problem", "Concrete issue.\n\n```text\n## Metadata\n- fake: yes\n```")
            (gd / "GATE-001.md").write_text(text)
            self.assertEqual(validate_project(root, strict=True), [])

    def test_evidence_file_ref_with_spaces_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            proof = root / "artifacts" / "proof file.txt"; proof.parent.mkdir(); proof.write_text("PASS")
            text = ready_text(severity="medium")
            text = replace_section(text, "Evidence Collected", "- EVID-001 | type=test | ref=file:artifacts/proof file.txt | result=PASS | note=Proof passed")
            (gd / "GATE-001.md").write_text(text)
            self.assertEqual(validate_project(root, strict=True), [])

    def test_release_check_json_failure_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Blocker", "--severity", "critical", "--path", str(root))
            result = self.run_cli("release-check", str(root), "--json", expect=1)
            import json
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertIs(payload["release_ready"], False)
            self.assertIn("errors", payload)
            self.assertNotIn("valid", payload)

    def test_validate_json_failure_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli("validate", "--strict", str(Path(tmp)), "--json", expect=1)
            import json
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 1)
            self.assertIs(payload["valid"], False)

    def test_critical_ready_outranks_low_in_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Low WIP", "--severity", "low", "--review-required", "no", "--path", str(root))
            p1 = root / ".quality-gates/gates/GATE-001.md"
            p1.write_text(p1.read_text().replace("Describe the defect, risk, gap, or requirement this gate resolves.", "Low issue.").replace("Describe an objective, testable outcome.", "Low outcome.").replace("Describe the objective evidence required.", "Low evidence."))
            self.run_cli("start", "GATE-001", "--note", "low work", "--path", str(root))
            self.run_cli("new", "Critical ready", "--severity", "critical", "--path", str(root))
            p2 = root / ".quality-gates/gates/GATE-002.md"
            p2.write_text(p2.read_text().replace("Describe the defect, risk, gap, or requirement this gate resolves.", "Critical issue.").replace("Describe an objective, testable outcome.", "Critical outcome.").replace("Describe the objective evidence required.", "Critical evidence."))
            result = self.run_cli("next", str(root))
            self.assertTrue(result.stdout.startswith("GATE-002"), result.stdout)

    @unittest.skipIf(sys.platform.startswith("win"), "POSIX mode semantics")
    def test_atomic_mutation_preserves_file_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Mode", "--review-required", "no", "--path", str(root))
            gate = root / ".quality-gates/gates/GATE-001.md"
            gate.chmod(0o644)
            text = gate.read_text().replace("Describe the defect, risk, gap, or requirement this gate resolves.", "Concrete problem.").replace("Describe an objective, testable outcome.", "Concrete outcome.").replace("Describe the objective evidence required.", "Concrete evidence.")
            gate.write_text(text); gate.chmod(0o644)
            self.run_cli("start", "GATE-001", "--note", "start", "--path", str(root))
            self.assertEqual(gate.stat().st_mode & 0o777, 0o644)

    def test_title_newline_is_rejected_without_creating_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "bad\ntitle", "--path", str(root), expect=1)
            self.assertFalse((root / ".quality-gates/gates/GATE-001.md").exists())

    def test_nonblank_preamble_before_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = ready_text().replace("\n\n## Metadata", "\nUNSTRUCTURED PREAMBLE\n\n## Metadata", 1)
            (gd / "GATE-001.md").write_text(text)
            self.assertTrue(any("nonblank preamble" in e for e in validate_project(root, strict=True)))

class EvidenceGrammarTests(unittest.TestCase):
    def test_manual_approval_ref_with_spaces_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); gd = gates_dir(root); gd.mkdir(parents=True)
            text = render_gate("GATE-001", "Manual ref", "medium")
            text = replace_section(text, "Problem", "Concrete problem.")
            text = replace_section(text, "Acceptance Criteria", "- [ ] AC-001 | Concrete outcome.")
            text = replace_section(text, "Evidence Required", "- [ ] EVID-001 | type=approval | Human approval evidence is required.")
            text = replace_section(text, "Evidence Collected", "- EVID-001 | type=approval | ref=manual:QA Reviewer approval note | result=PASS | note=Reviewer accepted scope")
            (gd / "GATE-001.md").write_text(text)
            self.assertEqual(validate_project(root, strict=True), [])
