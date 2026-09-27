import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliLifecycleTests(unittest.TestCase):
    def run_cli(self, *args: str, expect=0):
        result = subprocess.run(
            [sys.executable, "-m", "ai_quality_gates.cli", *args],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, expect, msg=f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        return result

    def test_end_to_end_controlled_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Protect data integrity", "--severity", "critical", "--path", str(root))
            gate = root / ".quality-gates" / "gates" / "GATE-001.md"
            text = gate.read_text(encoding="utf-8")
            text = text.replace(
                "Describe the defect, risk, gap, or requirement this gate resolves.",
                "Duplicate writes can corrupt a financial posting.",
            )
            text = text.replace(
                "Describe an objective, testable outcome.",
                "A duplicate submission creates exactly one posting.",
            )
            text = text.replace(
                "Describe the objective evidence required.",
                "An idempotency regression test passes.",
            )
            gate.write_text(text, encoding="utf-8")

            self.run_cli("start", "GATE-001", "--note", "Readiness criteria defined", "--path", str(root))
            for stage_note in [
                "Root cause isolated",
                "Implementation and rollback plan prepared",
                "Idempotency protection implemented",
                "Regression test executed",
                "Independent code review completed",
                "No additional defect required a fix",
                "Regression suite rerun after review",
            ]:
                self.run_cli("advance", "GATE-001", "--note", stage_note, "--path", str(root))

            evidence = root / "artifacts" / "idempotency.txt"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text("PASS\n", encoding="utf-8")
            self.run_cli(
                "add-evidence",
                "GATE-001",
                "EVID-001",
                "--ref",
                "file:artifacts/idempotency.txt",
                "--result",
                "PASS",
                "--note",
                "Regression test passed",
                "--path",
                str(root),
            )
            self.run_cli(
                "satisfy",
                "GATE-001",
                "AC-001",
                "--evidence",
                "EVID-001",
                "--note",
                "The regression test proves one posting per duplicate submission",
                "--path",
                str(root),
            )
            self.run_cli(
                "verify",
                "GATE-001",
                "--note",
                "Evidence mapped to acceptance criteria and final material state verified",
                "--path",
                str(root),
            )
            self.run_cli(
                "approve",
                "GATE-001",
                "--reviewer",
                "QA Reviewer",
                "--note",
                "Final verified state accepted",
                "--path",
                str(root),
            )
            self.run_cli(
                "close",
                "GATE-001",
                "--confirm-no-regression",
                "--note",
                "All closure invariants satisfied",
                "--path",
                str(root),
            )
            result = self.run_cli("validate", "--strict", str(root))
            self.assertIn("Validation passed", result.stdout)

    def test_close_refuses_incomplete_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Incomplete gate", "--review-required", "no", "--path", str(root))
            gate = root / ".quality-gates" / "gates" / "GATE-001.md"
            text = gate.read_text(encoding="utf-8")
            text = text.replace("Describe the defect, risk, gap, or requirement this gate resolves.", "Concrete problem.")
            text = text.replace("Describe an objective, testable outcome.", "Concrete outcome is true.")
            text = text.replace("Describe the objective evidence required.", "Concrete test evidence exists.")
            gate.write_text(text, encoding="utf-8")
            self.run_cli("start", "GATE-001", "--note", "Ready", "--path", str(root))
            result = self.run_cli(
                "close",
                "GATE-001",
                "--confirm-no-regression",
                "--note",
                "Premature close attempt",
                "--path",
                str(root),
                expect=1,
            )
            self.assertIn("Analyze through Verify must be complete", result.stdout)

    def test_json_status_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_cli("init", str(root))
            self.run_cli("new", "Machine readable", "--path", str(root))
            result = self.run_cli("status", str(root), "--json")
            import json
            payload = json.loads(result.stdout)
            self.assertEqual(payload["gates"][0]["gate"], "GATE-001")
            self.assertIn(payload["gates"][0]["state"], {"DRAFT", "READY"})


if __name__ == "__main__":
    unittest.main()
