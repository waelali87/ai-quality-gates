from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import hashlib
import json
import re
import tomllib
from urllib.parse import urlparse

SCHEMA_VERSION = "1"
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
STAGES = (
    "Analyze",
    "Prepare",
    "Execute",
    "Test",
    "Review",
    "Fix",
    "Re-test",
    "Verify",
    "Close Gate",
)
STATUSES = {"DRAFT", "OPEN", "CLOSED", "DEFERRED", "WAIVED"}
EVIDENCE_TYPES = {"test", "diff", "log", "screenshot", "report", "approval", "metric", "other"}
GATE_FILE_RE = re.compile(r"^GATE-(\d+)\.md$")
GATE_ID_RE = re.compile(r"^GATE-(\d+)$")
SECTION_RE = re.compile(r"^## ([^\n]+?)\s*$", re.MULTILINE)
METADATA_LINE_RE = re.compile(r"^- ([A-Za-z][A-Za-z0-9-]*):\s*(.*?)\s*$")
AC_LINE_RE = re.compile(r"^- \[([ xX])\] (AC-\d+) \| (.+)$")
EVID_REQ_LINE_RE = re.compile(r"^- \[([ xX])\] (EVID-\d+) \| type=([A-Za-z0-9_-]+) \| (.+)$")
EVID_COLLECT_LINE_RE = re.compile(
    r"^- (EVID-\d+) \| type=([A-Za-z0-9_-]+) \| ref=(.*?) \| result=(PASS|FAIL|N/A) \| note=(.+)$",
    re.IGNORECASE,
)
VERIFY_LINE_RE = re.compile(r"^- (AC-\d+) -> ((?:EVID-\d+)(?:,\s*EVID-\d+)*) \| (.+)$")
CHECKBOX_LINE_RE = re.compile(r"^- \[([ xX])\] (.+?)\s*$")
HISTORY_LINE_RE = re.compile(r"^- ([^|]+?) \| (.+?) \| completed$")
WORKLOG_LINE_RE = re.compile(r"^- ([^|]+?) \| (.+?) \| (.+)$")

REQUIRED_SECTIONS = (
    "Metadata",
    "Problem",
    "Acceptance Criteria",
    "Evidence Required",
    "Evidence Collected",
    "Execution Cycle",
    "Stage History",
    "Work Log",
    "Verification",
    "Closure",
)
METADATA_KEYS = (
    "Schema-Version",
    "Severity",
    "Dependencies",
    "Status",
    "Current-Stage",
    "Started-On",
    "Verified-On",
    "Verification-Fingerprint",
    "Review-Required",
    "Reviewer",
    "Approval",
    "Approved-On",
    "Approval-Fingerprint",
    "Closed-On",
    "Closure-Fingerprint",
    "Exception-Reason",
    "Exception-By",
    "Exception-On",
)
CLOSURE_CHECKS = (
    "All acceptance criteria satisfied",
    "Required evidence attached or referenced",
    "Dependencies closed",
    "No known Critical/High regression introduced",
    "Gate formally closed",
)

PROBLEM_PLACEHOLDERS = {
    "describe the defect, risk, gap, or requirement this gate resolves.",
    "state the defect, risk, missing requirement, or control gap.",
}
AC_PLACEHOLDERS = {
    "criterion 1 is objectively verifiable.",
    "criterion is objective and testable.",
    "describe an objective, testable outcome.",
}
EVIDENCE_PLACEHOLDERS = {
    "add links, test output, screenshots, diffs, logs, or other objective evidence.",
    "identify the evidence that proves closure.",
    "describe the objective evidence required.",
}
VERIFICATION_PLACEHOLDERS = {
    "state why the acceptance criteria are satisfied and identify the evidence.",
    "explain how the evidence proves each acceptance criterion.",
}
NONE_LINES = {"- none yet.", "none yet."}


class GateParseError(ValueError):
    """A gate document is structurally unreadable or ambiguous."""


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    evidence_type: str
    ref: str
    result: str
    note: str


@dataclass(frozen=True)
class Policy:
    blocking_severities: tuple[str, ...] = ("critical", "high")
    review_required_severities: tuple[str, ...] = ("critical", "high")
    allow_waived_blocking: bool = False
    allow_deferred_blocking: bool = False


@dataclass(frozen=True)
class GateSummary:
    gate_id: str
    title: str
    severity: str
    status: str
    current_stage: str
    path: Path
    dependencies: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION
    started_on: str = "None"
    verified_on: str = "None"
    verification_fingerprint: str = "None"
    review_required: bool = True
    reviewer: str = "Unassigned"
    approval: str = "PENDING"
    approved_on: str = "None"
    approval_fingerprint: str = "None"
    closed_on: str = "None"
    closure_fingerprint: str = "None"
    exception_reason: str = "None"
    exception_by: str = "None"
    exception_on: str = "None"

    @property
    def closed(self) -> bool:
        return self.status == "CLOSED"


# ---------- paths / policy ----------


def project_dir(root: Path) -> Path:
    return root / ".quality-gates"


def gates_dir(root: Path) -> Path:
    return project_dir(root) / "gates"


def policy_path(root: Path) -> Path:
    return project_dir(root) / "policy.toml"




def _path_within(root: Path, path: Path) -> bool:
    root_resolved = root.resolve()
    try:
        path.resolve(strict=False).relative_to(root_resolved)
        return True
    except (OSError, ValueError):
        return False


def governed_path_errors(root: Path) -> list[str]:
    """Fail closed when AQG-governed paths escape the project or use symlinks."""
    root = root.resolve()
    errors: list[str] = []
    qdir = project_dir(root)
    gd = gates_dir(root)
    ppath = policy_path(root)

    for label, path in (("workspace", qdir), ("gates directory", gd), ("policy file", ppath)):
        if path.is_symlink():
            errors.append(f"{path}: governed {label} must not be a symbolic link")
            continue
        if (path.exists() or path.is_symlink()) and not _path_within(root, path):
            errors.append(f"{path}: governed {label} escapes the project root")

    if gd.exists() and not gd.is_symlink() and gd.is_dir():
        try:
            entries = list(gd.iterdir())
        except OSError as exc:
            errors.append(f"{gd}: cannot inspect gates directory: {exc}")
            return errors
        for path in entries:
            if path.is_symlink():
                errors.append(f"{path}: governed gate entries must not be symbolic links")
            elif not _path_within(root, path):
                errors.append(f"{path}: governed gate entry escapes the project root")
    return _dedupe(errors) if '_dedupe' in globals() else list(dict.fromkeys(errors))


def render_default_policy() -> str:
    return (
        "# AI Quality Gates policy\n"
        "# v0.1 assumes one AQG writer at a time.\n\n"
        "[release]\n"
        'blocking_severities = ["critical", "high"]\n'
        "allow_waived_blocking = false\n"
        "allow_deferred_blocking = false\n\n"
        "[review]\n"
        'required_severities = ["critical", "high"]\n'
    )


def _policy_severity_list(value: object, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise GateParseError(f"policy '{key}' must be an array of severity strings")
    normalized = tuple(item.lower() for item in value)
    unknown = [item for item in normalized if item not in SEVERITY_ORDER]
    if unknown:
        raise GateParseError(f"policy '{key}' contains unknown severities: {', '.join(unknown)}")
    if len(set(normalized)) != len(normalized):
        raise GateParseError(f"policy '{key}' contains duplicate severities")
    return normalized


def load_policy(root: Path) -> Policy:
    path = policy_path(root)
    if not path.exists():
        return Policy()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise GateParseError(f"{path}: invalid policy.toml: {exc}") from exc
    release = data.get("release", {})
    review = data.get("review", {})
    if not isinstance(release, dict) or not isinstance(review, dict):
        raise GateParseError(f"{path}: [release] and [review] must be TOML tables")
    blocking = _policy_severity_list(
        release.get("blocking_severities", ["critical", "high"]),
        "release.blocking_severities",
    )
    required = _policy_severity_list(
        review.get("required_severities", ["critical", "high"]),
        "review.required_severities",
    )
    allow_waived = release.get("allow_waived_blocking", False)
    allow_deferred = release.get("allow_deferred_blocking", False)
    if not isinstance(allow_waived, bool) or not isinstance(allow_deferred, bool):
        raise GateParseError(f"{path}: release exception policy values must be booleans")
    return Policy(blocking, required, allow_waived, allow_deferred)


# ---------- parsing primitives ----------


@dataclass(frozen=True)
class _HeadingMatch:
    title: str
    start_pos: int
    end_pos: int

    def group(self, index: int) -> str:
        if index != 1:
            raise IndexError(index)
        return self.title

    def start(self) -> int:
        return self.start_pos

    def end(self) -> int:
        return self.end_pos


def _section_matches(text: str) -> list[_HeadingMatch]:
    """Return H2 headings outside fenced code blocks."""
    matches: list[_HeadingMatch] = []
    offset = 0
    fence_char: str | None = None
    fence_len = 0
    for line in text.splitlines(keepends=True):
        raw = line.rstrip("\r\n")
        fence = re.match(r"^\s*(`{3,}|~{3,})", raw)
        if fence:
            marker = fence.group(1)
            if fence_char is None:
                fence_char, fence_len = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_len:
                fence_char, fence_len = None, 0
            offset += len(line)
            continue
        if fence_char is None:
            heading = re.fullmatch(r"## ([^\n]+?)\s*", raw)
            if heading:
                matches.append(_HeadingMatch(heading.group(1).strip(), offset, offset + len(raw)))
        offset += len(line)
    return matches


def _validate_title_value(title: str) -> None:
    if not title or not title.strip():
        raise GateParseError("gate title must not be empty")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
        raise GateParseError("gate title must not contain newlines or control characters")

def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _is_none(value: str) -> bool:
    return value.strip().lower() in {"", "none", "n/a", "null", "unassigned"}


def canonical_gate_id(value: str) -> str:
    match = GATE_ID_RE.fullmatch(value.strip())
    if not match:
        raise GateParseError(f"invalid gate ID '{value}'")
    number = int(match.group(1))
    if number < 1:
        raise GateParseError("gate number must be >= 1")
    return f"GATE-{number:03d}"


def _section_occurrences(text: str, heading: str) -> list[str]:
    matches = _section_matches(text)
    bodies: list[str] = []
    for index, match in enumerate(matches):
        if match.group(1).strip() != heading:
            continue
        start = match.end()
        if start < len(text) and text[start:start + 1] == "\n":
            start += 1
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        bodies.append(text[start:end].strip())
    return bodies


def _section(text: str, heading: str) -> str | None:
    bodies = _section_occurrences(text, heading)
    return bodies[0] if len(bodies) == 1 else None


def _section_required(text: str, heading: str) -> str:
    bodies = _section_occurrences(text, heading)
    if not bodies:
        raise GateParseError(f"missing heading '## {heading}'")
    if len(bodies) > 1:
        raise GateParseError(f"duplicate heading '## {heading}'")
    return bodies[0]


def _metadata_map(text: str) -> dict[str, str]:
    body = _section_required(text, "Metadata")
    values: dict[str, str] = {}
    for line in body.splitlines():
        if not line.strip():
            continue
        match = METADATA_LINE_RE.fullmatch(line.strip())
        if not match:
            raise GateParseError(f"invalid Metadata line: {line.strip()}")
        key, value = match.group(1), match.group(2).strip()
        if key in values:
            raise GateParseError(f"duplicate metadata '{key}'")
        values[key] = value
    return values


def _metadata_value(text: str, key: str, *, required: bool = True) -> str | None:
    values = _metadata_map(text)
    if key in values:
        return values[key]
    if required:
        raise GateParseError(f"missing metadata '{key}'")
    return None


def _replace_exact_section(text: str, heading: str, body: str) -> str:
    matches = _section_matches(text)
    indexes = [i for i, m in enumerate(matches) if m.group(1).strip() == heading]
    if not indexes:
        raise GateParseError(f"missing heading '## {heading}'")
    if len(indexes) > 1:
        raise GateParseError(f"duplicate heading '## {heading}'")
    i = indexes[0]
    match = matches[i]
    start = match.end()
    if start < len(text) and text[start:start + 1] == "\n":
        start += 1
    end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
    replacement = body.rstrip() + "\n\n"
    return text[:start] + replacement + text[end:]


def replace_section(text: str, heading: str, body: str) -> str:
    return _replace_exact_section(text, heading, body)


def replace_metadata(text: str, key: str, value: str) -> str:
    body = _section_required(text, "Metadata")
    lines = body.splitlines()
    indexes = [i for i, line in enumerate(lines) if METADATA_LINE_RE.fullmatch(line.strip()) and METADATA_LINE_RE.fullmatch(line.strip()).group(1) == key]
    if not indexes:
        raise GateParseError(f"missing metadata '{key}'")
    if len(indexes) > 1:
        raise GateParseError(f"duplicate metadata '{key}'")
    lines[indexes[0]] = f"- {key}: {value}"
    return replace_section(text, "Metadata", "\n".join(lines))


def append_section_line(text: str, heading: str, line: str) -> str:
    body = _section_required(text, heading)
    if _normalize(body) in NONE_LINES:
        new_body = line
    else:
        new_body = body.rstrip() + "\n" + line
    return replace_section(text, heading, new_body)


def set_named_checkbox(text: str, label: str, checked: bool = True) -> str:
    if label in STAGES:
        heading = "Execution Cycle"
    elif label in CLOSURE_CHECKS:
        heading = "Closure"
    else:
        raise GateParseError(f"unknown governed checkbox '{label}'")
    body = _section_required(text, heading)
    pattern = re.compile(rf"^- \[[ xX]\] {re.escape(label)}\s*$", re.MULTILINE)
    matches = list(pattern.finditer(body))
    if not matches:
        raise GateParseError(f"missing checkbox '{label}' in {heading}")
    if len(matches) > 1:
        raise GateParseError(f"duplicate checkbox '{label}' in {heading}")
    mark = "x" if checked else " "
    body = pattern.sub(f"- [{mark}] {label}", body, count=1)
    return replace_section(text, heading, body)


def set_id_checkbox(text: str, item_id: str, checked: bool = True) -> str:
    if item_id.startswith("AC-"):
        heading = "Acceptance Criteria"
    elif item_id.startswith("EVID-"):
        heading = "Evidence Required"
    else:
        raise GateParseError(f"unsupported checkbox item '{item_id}'")
    body = _section_required(text, heading)
    pattern = re.compile(rf"^- \[[ xX]\] ({re.escape(item_id)} \| .+)$", re.MULTILINE)
    matches = list(pattern.finditer(body))
    if not matches:
        raise GateParseError(f"missing checkbox item '{item_id}' in {heading}")
    if len(matches) > 1:
        raise GateParseError(f"duplicate checkbox item '{item_id}' in {heading}")
    mark = "x" if checked else " "
    body = pattern.sub(rf"- [{mark}] \1", body, count=1)
    return replace_section(text, heading, body)


# ---------- rendering / summaries ----------


def render_gate(gate_id: str, title: str, severity: str, dependencies: list[str] | None = None) -> str:
    _validate_title_value(title)
    canonical = canonical_gate_id(gate_id)
    dependencies = dependencies or []
    deps = ", ".join(dependencies) if dependencies else "None"
    lines = [
        f"# {canonical} — {title}",
        "",
        "## Metadata",
        f"- Schema-Version: {SCHEMA_VERSION}",
        f"- Severity: {severity}",
        f"- Dependencies: {deps}",
        "- Status: DRAFT",
        "- Current-Stage: Analyze",
        "- Started-On: None",
        "- Verified-On: None",
        "- Verification-Fingerprint: None",
        "- Review-Required: YES",
        "- Reviewer: Unassigned",
        "- Approval: PENDING",
        "- Approved-On: None",
        "- Approval-Fingerprint: None",
        "- Closed-On: None",
        "- Closure-Fingerprint: None",
        "- Exception-Reason: None",
        "- Exception-By: None",
        "- Exception-On: None",
        "",
        "## Problem",
        "Describe the defect, risk, gap, or requirement this gate resolves.",
        "",
        "## Acceptance Criteria",
        "- [ ] AC-001 | Describe an objective, testable outcome.",
        "",
        "## Evidence Required",
        "- [ ] EVID-001 | type=test | Describe the objective evidence required.",
        "",
        "## Evidence Collected",
        "- None yet.",
        "",
        "## Execution Cycle",
    ]
    lines.extend(f"- [ ] {stage}" for stage in STAGES)
    lines.extend(
        [
            "",
            "## Stage History",
            "- None yet.",
            "",
            "## Work Log",
            "- None yet.",
            "",
            "## Verification",
            "- None yet.",
            "",
            "## Closure",
        ]
    )
    lines.extend(f"- [ ] {label}" for label in CLOSURE_CHECKS)
    lines.append("")
    return "\n".join(lines)


def next_gate_id(root: Path) -> str:
    gd = gates_dir(root)
    numbers: list[int] = []
    if gd.exists():
        for p in gd.iterdir():
            match = GATE_FILE_RE.fullmatch(p.name)
            if match:
                number = int(match.group(1))
                if number >= 1:
                    numbers.append(number)
    number = max(numbers, default=0) + 1
    return f"GATE-{number:03d}"


def parse_gate(path: Path) -> GateSummary:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise GateParseError(f"{path}: cannot read gate: {exc}") from exc
    first = text.splitlines()[0] if text else ""
    match = re.fullmatch(r"# (GATE-\d+) — (.+)", first)
    if not match:
        raise GateParseError(f"{path}: invalid gate title; expected '# GATE-NNN — Title'")
    raw_gate_id, title = match.group(1), match.group(2).strip()
    try:
        canonical_gate_id(raw_gate_id)
        metadata = _metadata_map(text)
        missing = [key for key in METADATA_KEYS if key not in metadata]
        if missing:
            raise GateParseError(f"missing metadata '{missing[0]}'")
        schema_version = metadata["Schema-Version"]
        severity = metadata["Severity"].lower()
        deps_raw = metadata["Dependencies"]
        status = metadata["Status"].upper()
        current_stage = metadata["Current-Stage"]
        started_on = metadata["Started-On"]
        verified_on = metadata["Verified-On"]
        verification_fingerprint_value = metadata["Verification-Fingerprint"]
        review_required_raw = metadata["Review-Required"].upper()
        reviewer = metadata["Reviewer"]
        approval = metadata["Approval"].upper()
        approved_on = metadata["Approved-On"]
        approval_fingerprint_value = metadata["Approval-Fingerprint"]
        closed_on = metadata["Closed-On"]
        closure_fingerprint_value = metadata["Closure-Fingerprint"]
        exception_reason = metadata["Exception-Reason"]
        exception_by = metadata["Exception-By"]
        exception_on = metadata["Exception-On"]
    except GateParseError as exc:
        raise GateParseError(f"{path}: {exc}") from exc

    if severity not in SEVERITY_ORDER:
        raise GateParseError(f"{path}: invalid severity '{severity}'")
    if status not in STATUSES:
        raise GateParseError(f"{path}: invalid status '{status}'")
    if review_required_raw not in {"YES", "NO"}:
        raise GateParseError(f"{path}: Review-Required must be YES or NO")

    deps: tuple[str, ...] = ()
    if deps_raw.strip().lower() != "none":
        deps = tuple(dep.strip() for dep in deps_raw.split(",") if dep.strip())

    return GateSummary(
        gate_id=raw_gate_id,
        title=title,
        severity=severity,
        status=status,
        current_stage=current_stage,
        path=path,
        dependencies=deps,
        schema_version=schema_version,
        started_on=started_on,
        verified_on=verified_on,
        verification_fingerprint=verification_fingerprint_value,
        review_required=review_required_raw == "YES",
        reviewer=reviewer,
        approval=approval,
        approved_on=approved_on,
        approval_fingerprint=approval_fingerprint_value,
        closed_on=closed_on,
        closure_fingerprint=closure_fingerprint_value,
        exception_reason=exception_reason,
        exception_by=exception_by,
        exception_on=exception_on,
    )


def gate_paths(root: Path) -> list[Path]:
    gd = gates_dir(root)
    if not gd.exists():
        return []
    return sorted([p for p in gd.iterdir() if p.is_file() and GATE_FILE_RE.fullmatch(p.name)], key=lambda p: p.name)


def list_gates(root: Path) -> list[GateSummary]:
    gates: list[GateSummary] = []
    for path in gate_paths(root):
        try:
            gates.append(parse_gate(path))
        except GateParseError:
            continue
    return gates


# ---------- section-aware record parsers ----------


def _section_lines(text: str, heading: str) -> list[str]:
    body = _section(text, heading)
    if body is None or _normalize(body) in NONE_LINES:
        return []
    return [line.strip() for line in body.splitlines() if line.strip()]


def parse_acceptance_criteria(text: str) -> list[tuple[str, bool, str]]:
    rows: list[tuple[str, bool, str]] = []
    for line in _section_lines(text, "Acceptance Criteria"):
        match = AC_LINE_RE.fullmatch(line)
        if match:
            rows.append((match.group(2), match.group(1).lower() == "x", match.group(3).strip()))
    return rows


def parse_evidence_required(text: str) -> list[tuple[str, bool, str, str]]:
    rows: list[tuple[str, bool, str, str]] = []
    for line in _section_lines(text, "Evidence Required"):
        match = EVID_REQ_LINE_RE.fullmatch(line)
        if match:
            rows.append((match.group(2), match.group(1).lower() == "x", match.group(3).lower(), match.group(4).strip()))
    return rows


def parse_evidence_collected(text: str) -> list[EvidenceRecord]:
    rows: list[EvidenceRecord] = []
    for line in _section_lines(text, "Evidence Collected"):
        match = EVID_COLLECT_LINE_RE.fullmatch(line)
        if match:
            rows.append(EvidenceRecord(match.group(1), match.group(2).lower(), match.group(3), match.group(4).upper(), match.group(5).strip()))
    return rows


def parse_verification(text: str) -> list[tuple[str, tuple[str, ...], str]]:
    mappings: list[tuple[str, tuple[str, ...], str]] = []
    for line in _section_lines(text, "Verification"):
        match = VERIFY_LINE_RE.fullmatch(line)
        if match:
            mappings.append((match.group(1), tuple(e.strip() for e in match.group(2).split(",")), match.group(3).strip()))
    return mappings


def parse_execution_cycle(text: str) -> list[tuple[str, bool]]:
    rows: list[tuple[str, bool]] = []
    for line in _section_lines(text, "Execution Cycle"):
        match = CHECKBOX_LINE_RE.fullmatch(line)
        if match:
            rows.append((match.group(2).strip(), match.group(1).lower() == "x"))
    return rows


def parse_stage_checks(text: str) -> list[bool]:
    by_label = {label: checked for label, checked in parse_execution_cycle(text)}
    return [by_label.get(stage, False) for stage in STAGES]


def parse_stage_history(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in _section_lines(text, "Stage History"):
        match = HISTORY_LINE_RE.fullmatch(line)
        if match:
            rows.append((match.group(1).strip(), match.group(2).strip()))
    return rows


def parse_work_log(text: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for line in _section_lines(text, "Work Log"):
        match = WORKLOG_LINE_RE.fullmatch(line)
        if match:
            rows.append((match.group(1).strip(), match.group(2).strip(), match.group(3).strip()))
    return rows


def parse_closure_checks(text: str) -> list[tuple[str, bool]]:
    rows: list[tuple[str, bool]] = []
    for line in _section_lines(text, "Closure"):
        match = CHECKBOX_LINE_RE.fullmatch(line)
        if match:
            rows.append((match.group(2).strip(), match.group(1).lower() == "x"))
    return rows


# ---------- evidence / time / fingerprints ----------


def _parse_iso(value: str) -> datetime | None:
    if _is_none(value):
        return None
    candidate = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _valid_evidence_ref(root: Path, evidence_type: str, ref: str, strict: bool) -> str | None:
    if ":" not in ref:
        return "evidence ref must use an explicit scheme: file:, url:, commit:, or manual:"
    scheme, value = ref.split(":", 1)
    scheme = scheme.lower()
    value = value.strip()
    if not value:
        return "evidence ref has an empty value"
    if scheme == "file":
        candidate = Path(value)
        if candidate.is_absolute():
            return "file evidence must use a project-relative path"
        resolved = (root / candidate).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            return "file evidence escapes the project root"
        if strict and not resolved.is_file():
            return f"file evidence does not exist: {value}"
        return None
    if scheme == "url":
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "url evidence must be an absolute http(s) URL"
        return None
    if scheme == "commit":
        if not re.fullmatch(r"[0-9a-fA-F]{7,40}", value):
            return "commit evidence must be a 7-40 character hexadecimal SHA"
        return None
    if scheme == "manual":
        if evidence_type != "approval":
            return "manual evidence is only allowed for type=approval"
        return None
    return f"unsupported evidence ref scheme '{scheme}'"


def approval_fingerprint(text: str) -> str:
    """Hash the final reviewed state while excluding approval/closure bookkeeping."""
    metadata = _metadata_map(text)
    execution = [(stage, checked) for stage, checked in parse_execution_cycle(text) if stage != "Close Gate"]
    history = [(ts, stage) for ts, stage in parse_stage_history(text) if stage != "Close Gate"]
    worklog = [(ts, stage, note) for ts, stage, note in parse_work_log(text) if stage in STAGES[:-1]]
    payload = {
        "title": text.splitlines()[0] if text else "",
        "severity": metadata.get("Severity"),
        "dependencies": metadata.get("Dependencies"),
        "started_on": metadata.get("Started-On"),
        "review_required": metadata.get("Review-Required"),
        "verified_on": metadata.get("Verified-On"),
        "verification_fingerprint": metadata.get("Verification-Fingerprint"),
        "problem": _section_required(text, "Problem"),
        "acceptance": _section_required(text, "Acceptance Criteria"),
        "evidence_required": _section_required(text, "Evidence Required"),
        "evidence_collected": _section_required(text, "Evidence Collected"),
        "execution": execution,
        "history": history,
        "worklog": worklog,
        "verification": _section_required(text, "Verification"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verification_fingerprint(text: str) -> str:
    """Hash the material state that Verify attests to, excluding Verify/approval/closure bookkeeping."""
    metadata = _metadata_map(text)
    execution = [(stage, checked) for stage, checked in parse_execution_cycle(text) if stage not in {"Verify", "Close Gate"}]
    history = [(ts, stage) for ts, stage in parse_stage_history(text) if stage not in {"Verify", "Close Gate"}]
    worklog = [(ts, stage, note) for ts, stage, note in parse_work_log(text) if stage in STAGES[:7]]
    payload = {
        "title": text.splitlines()[0] if text else "",
        "severity": metadata.get("Severity"),
        "dependencies": metadata.get("Dependencies"),
        "started_on": metadata.get("Started-On"),
        "review_required": metadata.get("Review-Required"),
        "problem": _section_required(text, "Problem"),
        "acceptance": _section_required(text, "Acceptance Criteria"),
        "evidence_required": _section_required(text, "Evidence Required"),
        "evidence_collected": _section_required(text, "Evidence Collected"),
        "execution": execution,
        "history": history,
        "worklog": worklog,
        "verification": _section_required(text, "Verification"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def closure_fingerprint(text: str) -> str:
    """Hash a CLOSED gate while excluding only the self-referential Closure-Fingerprint value."""
    normalized = replace_metadata(text, "Closure-Fingerprint", "None")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _prefix_length(checks: list[bool]) -> int:
    length = 0
    for checked in checks:
        if not checked:
            break
        length += 1
    return length


# ---------- readiness / operational state ----------


def _draft_readiness_errors(gate: GateSummary, text: str, gate_by_id: dict[str, GateSummary]) -> list[str]:
    errors: list[str] = []
    problem = _section(text, "Problem")
    if not problem or _normalize(problem) in PROBLEM_PLACEHOLDERS:
        errors.append(f"{gate.gate_id}: problem statement is still a placeholder")
    acs = parse_acceptance_criteria(text)
    if not acs:
        errors.append(f"{gate.gate_id}: at least one acceptance criterion is required")
    for ac_id, _, desc in acs:
        if _normalize(desc) in AC_PLACEHOLDERS:
            errors.append(f"{gate.gate_id}: {ac_id} is still a placeholder")
    required = parse_evidence_required(text)
    if not required:
        errors.append(f"{gate.gate_id}: at least one evidence requirement is required")
    for evid_id, _, evidence_type, desc in required:
        if evidence_type not in EVIDENCE_TYPES:
            errors.append(f"{gate.gate_id}: {evid_id} has unsupported evidence type '{evidence_type}'")
        if _normalize(desc) in EVIDENCE_PLACEHOLDERS:
            errors.append(f"{gate.gate_id}: {evid_id} is still a placeholder")
    for dep in gate.dependencies:
        dep_gate = gate_by_id.get(dep)
        if dep_gate is None:
            errors.append(f"{gate.gate_id}: unknown dependency '{dep}'")
        elif not dep_gate.closed:
            errors.append(f"{gate.gate_id}: blocked by dependency {dep} ({dep_gate.status})")
    return errors


def draft_readiness_errors(root: Path, gate_id: str) -> list[str]:
    errors = validate_project(root, strict=False)
    if errors:
        return errors
    gates = list_gates(root)
    gate_by_id = {g.gate_id: g for g in gates}
    gate = gate_by_id.get(gate_id)
    if gate is None:
        return [f"unknown gate '{gate_id}'"]
    text = gate.path.read_text(encoding="utf-8")
    return _draft_readiness_errors(gate, text, gate_by_id)


def operational_state(root: Path, gate: GateSummary, gate_by_id: dict[str, GateSummary] | None = None) -> str:
    gate_by_id = gate_by_id or {g.gate_id: g for g in list_gates(root)}
    if gate.status in {"CLOSED", "DEFERRED", "WAIVED"}:
        return gate.status
    blockers = [dep for dep in gate.dependencies if dep not in gate_by_id or not gate_by_id[dep].closed]
    if blockers:
        return "BLOCKED"
    if gate.status == "OPEN":
        return "IN_PROGRESS"
    try:
        text = gate.path.read_text(encoding="utf-8")
    except OSError:
        return "DRAFT"
    readiness = _draft_readiness_errors(gate, text, gate_by_id)
    return "READY" if not readiness else "DRAFT"


# ---------- structural validation ----------


def _validate_section_cardinality(text: str, gate_label: str) -> list[str]:
    errors: list[str] = []
    all_headings = [match.group(1).strip() for match in _section_matches(text)]
    for heading in REQUIRED_SECTIONS:
        count = all_headings.count(heading)
        if count == 0:
            errors.append(f"{gate_label}: missing heading '## {heading}'")
        elif count > 1:
            errors.append(f"{gate_label}: duplicate heading '## {heading}'")
    unknown = sorted({heading for heading in all_headings if heading not in REQUIRED_SECTIONS})
    for heading in unknown:
        errors.append(f"{gate_label}: unexpected heading '## {heading}'")
    if not unknown and all(all_headings.count(heading) == 1 for heading in REQUIRED_SECTIONS):
        if all_headings != list(REQUIRED_SECTIONS):
            errors.append(f"{gate_label}: required sections must appear exactly once in canonical order")
    return errors


def _validate_structured_section_lines(text: str, gate_id: str) -> list[str]:
    errors: list[str] = []
    validators = {
        "Acceptance Criteria": AC_LINE_RE,
        "Evidence Required": EVID_REQ_LINE_RE,
        "Evidence Collected": EVID_COLLECT_LINE_RE,
        "Verification": VERIFY_LINE_RE,
        "Stage History": HISTORY_LINE_RE,
        "Work Log": WORKLOG_LINE_RE,
    }
    for heading, pattern in validators.items():
        body = _section(text, heading)
        if body is None:
            continue
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        if len(lines) == 1 and _normalize(lines[0]) in NONE_LINES:
            continue
        for line in lines:
            if not pattern.fullmatch(line):
                errors.append(f"{gate_id}: invalid line in {heading}: {line}")
    return errors


def _validate_execution_section(text: str, gate_id: str) -> tuple[list[str], list[bool]]:
    errors: list[str] = []
    body = _section(text, "Execution Cycle")
    if body is None:
        return errors, [False] * len(STAGES)
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    parsed: list[tuple[str, bool]] = []
    for line in lines:
        match = CHECKBOX_LINE_RE.fullmatch(line)
        if not match:
            errors.append(f"{gate_id}: invalid line in Execution Cycle: {line}")
            continue
        parsed.append((match.group(2).strip(), match.group(1).lower() == "x"))
    labels = [label for label, _ in parsed]
    if labels != list(STAGES):
        errors.append(f"{gate_id}: Execution Cycle must contain exactly the 9 canonical stages in order")
    checks = [False] * len(STAGES)
    if labels == list(STAGES):
        checks = [checked for _, checked in parsed]
    return errors, checks


def _validate_closure_section(text: str, gate_id: str) -> tuple[list[str], dict[str, bool]]:
    errors: list[str] = []
    body = _section(text, "Closure")
    if body is None:
        return errors, {label: False for label in CLOSURE_CHECKS}
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    parsed: list[tuple[str, bool]] = []
    for line in lines:
        match = CHECKBOX_LINE_RE.fullmatch(line)
        if not match:
            errors.append(f"{gate_id}: invalid line in Closure: {line}")
            continue
        parsed.append((match.group(2).strip(), match.group(1).lower() == "x"))
    labels = [label for label, _ in parsed]
    if labels != list(CLOSURE_CHECKS):
        errors.append(f"{gate_id}: Closure must contain exactly the canonical closure checks in order")
    marks = {label: checked for label, checked in parsed}
    return errors, {label: marks.get(label, False) for label in CLOSURE_CHECKS}


def validate_gate_text(
    text: str,
    path: Path,
    known_ids: set[str],
    root: Path,
    *,
    strict: bool = False,
    policy: Policy | None = None,
    gate_by_id: dict[str, GateSummary] | None = None,
) -> list[str]:
    errors: list[str] = []
    first = text.splitlines()[0] if text else ""
    title_match = re.fullmatch(r"# (GATE-\d+) — (.+)", first)
    gate_label = title_match.group(1) if title_match else path.name
    if title_match:
        try:
            _validate_title_value(title_match.group(2))
        except GateParseError as exc:
            errors.append(f"{gate_label}: {exc}")
        headings = _section_matches(text)
        metadata_head = next((m for m in headings if m.group(1).strip() == "Metadata"), None)
        if metadata_head:
            first_line_end = text.find("\n")
            first_line_end = len(text) if first_line_end < 0 else first_line_end + 1
            if text[first_line_end:metadata_head.start()].strip():
                errors.append(f"{gate_label}: nonblank preamble before Metadata is not allowed")
    errors.extend(_validate_section_cardinality(text, gate_label))
    if errors:
        # Keep validating line-level issues where possible, but parse_gate may be ambiguous.
        pass
    try:
        # parse through a small in-memory-compatible helper by interpreting metadata directly.
        if not title_match:
            raise GateParseError(f"{path}: invalid gate title; expected '# GATE-NNN — Title'")
        raw_gate_id = title_match.group(1)
        canonical_header = canonical_gate_id(raw_gate_id)
        metadata = _metadata_map(text)
        missing = [key for key in METADATA_KEYS if key not in metadata]
        if missing:
            raise GateParseError(f"{path}: missing metadata '{missing[0]}'")
        unknown_metadata = [key for key in metadata if key not in METADATA_KEYS]
        if unknown_metadata:
            raise GateParseError(f"{path}: unexpected metadata '{unknown_metadata[0]}'")
        severity = metadata["Severity"].lower()
        status = metadata["Status"].upper()
        if severity not in SEVERITY_ORDER:
            raise GateParseError(f"{path}: invalid severity '{severity}'")
        if status not in STATUSES:
            raise GateParseError(f"{path}: invalid status '{status}'")
        review_raw = metadata["Review-Required"].upper()
        if review_raw not in {"YES", "NO"}:
            raise GateParseError(f"{path}: Review-Required must be YES or NO")
        deps_raw = metadata["Dependencies"]
        deps = tuple(dep.strip() for dep in deps_raw.split(",") if dep.strip()) if deps_raw.lower() != "none" else ()
        gate = GateSummary(
            gate_id=raw_gate_id,
            title=title_match.group(2).strip(),
            severity=severity,
            status=status,
            current_stage=metadata["Current-Stage"],
            path=path,
            dependencies=deps,
            schema_version=metadata["Schema-Version"],
            started_on=metadata["Started-On"],
            verified_on=metadata["Verified-On"],
            verification_fingerprint=metadata["Verification-Fingerprint"],
            review_required=review_raw == "YES",
            reviewer=metadata["Reviewer"],
            approval=metadata["Approval"].upper(),
            approved_on=metadata["Approved-On"],
            approval_fingerprint=metadata["Approval-Fingerprint"],
            closed_on=metadata["Closed-On"],
            closure_fingerprint=metadata["Closure-Fingerprint"],
            exception_reason=metadata["Exception-Reason"],
            exception_by=metadata["Exception-By"],
            exception_on=metadata["Exception-On"],
        )
    except GateParseError as exc:
        errors.append(str(exc))
        return _dedupe(errors)

    file_match = GATE_FILE_RE.fullmatch(path.name)
    if not file_match:
        errors.append(f"{path}: invalid gate filename; expected GATE-<number>.md")
    else:
        canonical_file = f"GATE-{int(file_match.group(1)):03d}" if int(file_match.group(1)) >= 1 else "INVALID"
        if raw_gate_id != canonical_header:
            errors.append(f"{raw_gate_id}: header ID is not canonical; expected {canonical_header}")
        if path.stem != canonical_file:
            errors.append(f"{path}: gate filename is not canonical; expected {canonical_file}.md")
        if int(file_match.group(1)) >= 1 and int(file_match.group(1)) != int(raw_gate_id.split("-", 1)[1]):
            errors.append(f"{raw_gate_id}: header ID does not match filename {path.name}")

    if gate.schema_version != SCHEMA_VERSION:
        errors.append(f"{gate.gate_id}: unsupported Schema-Version '{gate.schema_version}' (expected {SCHEMA_VERSION})")

    policy = policy or Policy()
    if gate.severity in policy.review_required_severities and not gate.review_required:
        errors.append(f"{gate.gate_id}: policy requires independent review for {gate.severity} severity")

    if len(set(gate.dependencies)) != len(gate.dependencies):
        errors.append(f"{gate.gate_id}: duplicate dependencies are not allowed")
    for dep in gate.dependencies:
        try:
            canonical_dep = canonical_gate_id(dep)
        except GateParseError:
            errors.append(f"{gate.gate_id}: invalid dependency ID '{dep}'")
            continue
        if dep != canonical_dep:
            errors.append(f"{gate.gate_id}: dependency ID '{dep}' is not canonical; expected {canonical_dep}")
        if canonical_dep not in known_ids:
            errors.append(f"{gate.gate_id}: unknown dependency '{dep}'")
        if canonical_dep == canonical_header:
            errors.append(f"{gate.gate_id}: gate cannot depend on itself")

    errors.extend(_validate_structured_section_lines(text, gate.gate_id))
    execution_errors, checks = _validate_execution_section(text, gate.gate_id)
    errors.extend(execution_errors)
    closure_errors, closure_marks = _validate_closure_section(text, gate.gate_id)
    errors.extend(closure_errors)

    acs = parse_acceptance_criteria(text)
    if not acs:
        errors.append(f"{gate.gate_id}: Acceptance Criteria must contain at least one AC-* checkbox")
    ac_ids = [item[0] for item in acs]
    if len(set(ac_ids)) != len(ac_ids):
        errors.append(f"{gate.gate_id}: duplicate acceptance criterion IDs")

    required_evidence = parse_evidence_required(text)
    if not required_evidence:
        errors.append(f"{gate.gate_id}: Evidence Required must contain at least one EVID-* checkbox")
    req_ids = [item[0] for item in required_evidence]
    if len(set(req_ids)) != len(req_ids):
        errors.append(f"{gate.gate_id}: duplicate evidence requirement IDs")
    for evid_id, _, evidence_type, _ in required_evidence:
        if evidence_type not in EVIDENCE_TYPES:
            errors.append(f"{gate.gate_id}: {evid_id} has unsupported evidence type '{evidence_type}'")

    gate_by_id = gate_by_id or {g.gate_id: g for g in list_gates(root)}
    if gate.status in {"OPEN", "CLOSED"}:
        errors.extend(err for err in _draft_readiness_errors(gate, text, gate_by_id) if "blocked by dependency" not in err)

    prefix_len = _prefix_length(checks)
    if any(checks[prefix_len:]):
        errors.append(f"{gate.gate_id}: execution stages are checked out of sequence")
    expected_current = STAGES[prefix_len] if prefix_len < len(STAGES) else "COMPLETE"
    if gate.current_stage != expected_current:
        errors.append(f"{gate.gate_id}: Current-Stage is '{gate.current_stage}' but expected '{expected_current}'")

    started_dt = _parse_iso(gate.started_on)
    if gate.status == "DRAFT":
        if started_dt is not None:
            errors.append(f"{gate.gate_id}: DRAFT gate must have Started-On: None")
        if prefix_len:
            errors.append(f"{gate.gate_id}: DRAFT gate cannot have completed execution stages")
    elif gate.status in {"OPEN", "CLOSED"}:
        if started_dt is None:
            errors.append(f"{gate.gate_id}: {gate.status} gate requires a valid Started-On timestamp")
    elif gate.status in {"DEFERRED", "WAIVED"} and prefix_len and started_dt is None:
        errors.append(f"{gate.gate_id}: started {gate.status} gate requires a valid Started-On timestamp")

    # OPEN must not have the final Close Gate stage completed.
    if gate.status == "OPEN" and checks and checks[-1]:
        errors.append(f"{gate.gate_id}: OPEN gate cannot have Close Gate completed")
    if gate.status == "CLOSED" and (len(checks) != len(STAGES) or not all(checks)):
        errors.append(f"{gate.gate_id}: CLOSED gate requires all execution stages including Close Gate")
    if gate.status in {"DRAFT", "OPEN", "DEFERRED", "WAIVED"} and closure_marks.get("Gate formally closed", False):
        errors.append(f"{gate.gate_id}: non-closed gate cannot be marked formally closed")

    history = parse_stage_history(text)
    raw_history_lines = _section_lines(text, "Stage History")
    if raw_history_lines and len(history) != len(raw_history_lines):
        errors.append(f"{gate.gate_id}: Stage History contains malformed entries")
    history_stages = [stage for _, stage in history]
    expected_history = list(STAGES[:prefix_len])
    if history_stages != expected_history:
        errors.append(f"{gate.gate_id}: stage history does not match the sequential completed-stage prefix")
    history_times: list[datetime] = []
    history_by_stage: dict[str, datetime] = {}
    for timestamp, stage in history:
        dt = _parse_iso(timestamp)
        if dt is None:
            errors.append(f"{gate.gate_id}: invalid stage-history timestamp '{timestamp}' for {stage}")
        else:
            history_times.append(dt)
            history_by_stage[stage] = dt
    if any(a > b for a, b in zip(history_times, history_times[1:])):
        errors.append(f"{gate.gate_id}: stage-history timestamps are not monotonic")
    if started_dt is not None and any(dt < started_dt for dt in history_times):
        errors.append(f"{gate.gate_id}: stage-history timestamp precedes Started-On")

    worklog = parse_work_log(text)
    raw_worklog_lines = _section_lines(text, "Work Log")
    if raw_worklog_lines and len(worklog) != len(raw_worklog_lines):
        errors.append(f"{gate.gate_id}: Work Log contains malformed entries")
    worklog_times: list[datetime] = []
    for timestamp, stage, note in worklog:
        dt = _parse_iso(timestamp)
        if dt is None:
            errors.append(f"{gate.gate_id}: invalid work-log timestamp '{timestamp}'")
        else:
            worklog_times.append(dt)
        if not note or _normalize(note) in {"note", "todo", "placeholder"}:
            errors.append(f"{gate.gate_id}: work-log entry for {stage} has no meaningful note")
    if any(a > b for a, b in zip(worklog_times, worklog_times[1:])):
        errors.append(f"{gate.gate_id}: work-log timestamps are not monotonic")
    execution_log_times = [
        dt for ts, stage, _ in worklog
        if stage == "START" or stage in STAGES or stage == "APPROVAL"
        if (dt := _parse_iso(ts)) is not None
    ]
    if started_dt is not None and any(dt < started_dt for dt in execution_log_times):
        errors.append(f"{gate.gate_id}: execution work-log timestamp precedes Started-On")

    stage_worklog = [(ts, stage) for ts, stage, _ in worklog if stage in STAGES]
    if [stage for _, stage in stage_worklog] != expected_history:
        errors.append(f"{gate.gate_id}: work log does not contain one ordered entry per completed stage")
    for (hist_ts, hist_stage), (log_ts, log_stage) in zip(history, stage_worklog):
        if hist_stage == log_stage and hist_ts != log_ts:
            errors.append(f"{gate.gate_id}: {hist_stage} Stage History and Work Log timestamps must match")

    start_entries = [(ts, note) for ts, stage, note in worklog if stage == "START"]
    if started_dt is not None:
        if len(start_entries) != 1:
            errors.append(f"{gate.gate_id}: started gate requires exactly one START work-log entry")
        elif _parse_iso(start_entries[0][0]) != started_dt:
            errors.append(f"{gate.gate_id}: START work-log timestamp must equal Started-On")
    elif start_entries:
        errors.append(f"{gate.gate_id}: unstarted gate cannot contain a START work-log entry")

    verify_checked = checks[STAGES.index("Verify")] if len(checks) == len(STAGES) else False
    verified_dt = _parse_iso(gate.verified_on)
    if verify_checked:
        if verified_dt is None:
            errors.append(f"{gate.gate_id}: completed Verify requires a valid Verified-On timestamp")
        verify_history_dt = history_by_stage.get("Verify")
        if verified_dt and verify_history_dt and verified_dt != verify_history_dt:
            errors.append(f"{gate.gate_id}: Verified-On must equal Verify Stage History timestamp")
        if _is_none(gate.verification_fingerprint):
            errors.append(f"{gate.gate_id}: completed Verify requires Verification-Fingerprint")
        else:
            try:
                expected_vfp = verification_fingerprint(text)
                if gate.verification_fingerprint != expected_vfp:
                    errors.append(f"{gate.gate_id}: verification is stale because material content changed after Verify")
            except GateParseError as exc:
                errors.append(f"{gate.gate_id}: cannot verify Verification-Fingerprint: {exc}")
    else:
        if not _is_none(gate.verified_on) or not _is_none(gate.verification_fingerprint):
            errors.append(f"{gate.gate_id}: unverified gate requires Verified-On/Verification-Fingerprint to be None")

    approval_entries = [(ts, note) for ts, stage, note in worklog if stage == "APPROVAL"]
    invalidation_entries = [(ts, note) for ts, stage, note in worklog if stage == "APPROVAL_INVALIDATED"]
    approval_times = [dt for ts, _ in approval_entries if (dt := _parse_iso(ts)) is not None]
    invalidation_times = [dt for ts, _ in invalidation_entries if (dt := _parse_iso(ts)) is not None]
    latest_approval = max(approval_times) if approval_times else None
    latest_invalidation = max(invalidation_times) if invalidation_times else None
    if gate.review_required:
        if gate.approval not in {"PENDING", "APPROVED"}:
            errors.append(f"{gate.gate_id}: review-required gate must use Approval PENDING or APPROVED")
        if gate.approval == "APPROVED":
            approved_dt = _parse_iso(gate.approved_on)
            if _is_none(gate.reviewer):
                errors.append(f"{gate.gate_id}: approved gate requires a Reviewer")
            if approved_dt is None:
                errors.append(f"{gate.gate_id}: approved gate requires a valid Approved-On timestamp")
            if not verify_checked:
                errors.append(f"{gate.gate_id}: approval is only valid after Verify is complete")
            elif _is_none(gate.verification_fingerprint):
                errors.append(f"{gate.gate_id}: approval requires a fresh Verification-Fingerprint")
            else:
                try:
                    if gate.verification_fingerprint != verification_fingerprint(text):
                        errors.append(f"{gate.gate_id}: approval requires fresh verification of the current material state")
                except GateParseError as exc:
                    errors.append(f"{gate.gate_id}: cannot validate verification before approval: {exc}")
            verify_dt = history_by_stage.get("Verify")
            if approved_dt and verify_dt and approved_dt < verify_dt:
                errors.append(f"{gate.gate_id}: Approved-On precedes Verify completion")
            if latest_approval is None:
                errors.append(f"{gate.gate_id}: approved gate requires an APPROVAL work-log entry")
            elif approved_dt and latest_approval != approved_dt:
                errors.append(f"{gate.gate_id}: latest APPROVAL work-log timestamp must equal Approved-On")
            if latest_invalidation and latest_approval and latest_invalidation >= latest_approval:
                errors.append(f"{gate.gate_id}: approval was invalidated after the latest approval")
            if _is_none(gate.approval_fingerprint):
                errors.append(f"{gate.gate_id}: approved gate requires Approval-Fingerprint")
            else:
                try:
                    expected_fp = approval_fingerprint(text)
                    if gate.approval_fingerprint != expected_fp:
                        errors.append(f"{gate.gate_id}: approval is stale because reviewed content changed after approval")
                except GateParseError as exc:
                    errors.append(f"{gate.gate_id}: cannot verify Approval-Fingerprint: {exc}")
        else:
            if not _is_none(gate.reviewer) or not _is_none(gate.approved_on) or not _is_none(gate.approval_fingerprint):
                errors.append(f"{gate.gate_id}: pending approval requires Reviewer/Approved-On/Approval-Fingerprint to be empty")
            if latest_approval and (latest_invalidation is None or latest_invalidation < latest_approval):
                errors.append(f"{gate.gate_id}: pending approval must record invalidation after the latest prior approval")
    else:
        if gate.approval != "NOT_REQUIRED":
            errors.append(f"{gate.gate_id}: Review-Required NO requires Approval: NOT_REQUIRED")
        if not _is_none(gate.reviewer) or not _is_none(gate.approved_on) or not _is_none(gate.approval_fingerprint):
            errors.append(f"{gate.gate_id}: review-not-required gate must not contain reviewer approval metadata")
        if approval_entries:
            errors.append(f"{gate.gate_id}: review-not-required gate cannot contain APPROVAL work-log entries")

    if gate.status in {"DEFERRED", "WAIVED"}:
        if _is_none(gate.exception_reason):
            errors.append(f"{gate.gate_id}: {gate.status} gate requires Exception-Reason")
        if _is_none(gate.exception_by):
            errors.append(f"{gate.gate_id}: {gate.status} gate requires Exception-By")
        exception_dt = _parse_iso(gate.exception_on)
        if exception_dt is None:
            errors.append(f"{gate.gate_id}: {gate.status} gate requires a valid Exception-On timestamp")
        problem = _section(text, "Problem")
        if not problem or _normalize(problem) in PROBLEM_PLACEHOLDERS:
            errors.append(f"{gate.gate_id}: {gate.status} requires a concrete Problem statement before exception")
        if gate.status == "WAIVED":
            if not acs or any(_normalize(desc) in AC_PLACEHOLDERS for _, _, desc in acs):
                errors.append(f"{gate.gate_id}: WAIVED requires concrete Acceptance Criteria before exception")
            if not required_evidence or any(_normalize(desc) in EVIDENCE_PLACEHOLDERS for _, _, _, desc in required_evidence):
                errors.append(f"{gate.gate_id}: WAIVED requires concrete Evidence Required before exception")
    else:
        if not _is_none(gate.exception_reason) or not _is_none(gate.exception_by) or not _is_none(gate.exception_on):
            errors.append(f"{gate.gate_id}: exception metadata must be None unless status is DEFERRED or WAIVED")

    collected = parse_evidence_collected(text)
    collected_ids = [item.evidence_id for item in collected]
    if len(set(collected_ids)) != len(collected_ids):
        errors.append(f"{gate.gate_id}: duplicate collected evidence IDs")
    req_by_id = {evid_id: (checked, evidence_type, desc) for evid_id, checked, evidence_type, desc in required_evidence}
    for record in collected:
        if record.evidence_id not in req_by_id:
            errors.append(f"{gate.gate_id}: collected evidence {record.evidence_id} has no matching requirement")
            continue
        req_type = req_by_id[record.evidence_id][1]
        if record.evidence_type != req_type:
            errors.append(f"{gate.gate_id}: {record.evidence_id} collected type '{record.evidence_type}' does not match required type '{req_type}'")
        ref_error = _valid_evidence_ref(root, record.evidence_type, record.ref, strict)
        if ref_error:
            errors.append(f"{gate.gate_id}: {record.evidence_id} {ref_error}")
        if record.result == "FAIL" and gate.status == "CLOSED":
            errors.append(f"{gate.gate_id}: {record.evidence_id} result is FAIL")
        if record.result == "N/A" and record.evidence_type != "approval":
            errors.append(f"{gate.gate_id}: {record.evidence_id} result N/A cannot satisfy non-approval evidence")
        if not record.note or _normalize(record.note) in {"note", "todo", "placeholder"}:
            errors.append(f"{gate.gate_id}: {record.evidence_id} requires a meaningful note")

    mappings = parse_verification(text)
    mapping_by_ac: dict[str, tuple[tuple[str, ...], str]] = {}
    for ac_id, evid_ids, note in mappings:
        if ac_id in mapping_by_ac:
            errors.append(f"{gate.gate_id}: duplicate verification mapping for {ac_id}")
        mapping_by_ac[ac_id] = (evid_ids, note)
        if ac_id not in ac_ids:
            errors.append(f"{gate.gate_id}: verification references unknown criterion {ac_id}")
        for evid_id in evid_ids:
            if evid_id not in collected_ids:
                errors.append(f"{gate.gate_id}: verification references missing collected evidence {evid_id}")
        if not note or _normalize(note) in VERIFICATION_PLACEHOLDERS:
            errors.append(f"{gate.gate_id}: verification mapping for {ac_id} has no meaningful explanation")

    if gate.status == "CLOSED":
        for ac_id, checked, desc in acs:
            if not checked:
                errors.append(f"{gate.gate_id}: closed gate has unchecked acceptance criterion {ac_id}")
            if _normalize(desc) in AC_PLACEHOLDERS:
                errors.append(f"{gate.gate_id}: closed gate contains placeholder acceptance criterion {ac_id}")
            if ac_id not in mapping_by_ac:
                errors.append(f"{gate.gate_id}: closed gate lacks verification mapping for {ac_id}")
        for evid_id, checked, _, desc in required_evidence:
            if not checked:
                errors.append(f"{gate.gate_id}: closed gate has unchecked evidence requirement {evid_id}")
            if _normalize(desc) in EVIDENCE_PLACEHOLDERS:
                errors.append(f"{gate.gate_id}: closed gate contains placeholder evidence requirement {evid_id}")
            if evid_id not in collected_ids:
                errors.append(f"{gate.gate_id}: closed gate lacks collected evidence {evid_id}")
        if gate.review_required and gate.approval != "APPROVED":
            errors.append(f"{gate.gate_id}: closed gate requires independent approval")
        for label, checked in closure_marks.items():
            if not checked:
                errors.append(f"{gate.gate_id}: closure check incomplete: {label}")
        close_dt = history_by_stage.get("Close Gate")
        approved_dt = _parse_iso(gate.approved_on)
        if gate.review_required and close_dt and approved_dt and close_dt < approved_dt:
            errors.append(f"{gate.gate_id}: Close Gate completion precedes independent approval")
        closed_dt = _parse_iso(gate.closed_on)
        if closed_dt is None:
            errors.append(f"{gate.gate_id}: CLOSED gate requires a valid Closed-On timestamp")
        elif close_dt and closed_dt != close_dt:
            errors.append(f"{gate.gate_id}: Closed-On must equal Close Gate Stage History timestamp")
        if _is_none(gate.closure_fingerprint):
            errors.append(f"{gate.gate_id}: CLOSED gate requires Closure-Fingerprint")
        else:
            try:
                if gate.closure_fingerprint != closure_fingerprint(text):
                    errors.append(f"{gate.gate_id}: closure is stale because closed content changed after closure")
            except GateParseError as exc:
                errors.append(f"{gate.gate_id}: cannot verify Closure-Fingerprint: {exc}")
    else:
        if not _is_none(gate.closed_on) or not _is_none(gate.closure_fingerprint):
            errors.append(f"{gate.gate_id}: non-closed gate requires Closed-On/Closure-Fingerprint to be None")
        # All closure boxes except regression may remain unchecked until formal closure.
        if any(closure_marks.values()):
            errors.append(f"{gate.gate_id}: non-closed gate cannot have Closure checkboxes selected")

    return _dedupe(errors)


def validate_gate(path: Path, known_ids: set[str], root: Path, *, strict: bool = False, policy: Policy | None = None, gate_by_id: dict[str, GateSummary] | None = None) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{path}: cannot read gate: {exc}"]
    return validate_gate_text(text, path, known_ids, root, strict=strict, policy=policy, gate_by_id=gate_by_id)


def _dedupe(errors: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for error in errors:
        if error not in seen:
            result.append(error)
            seen.add(error)
    return result


def validate_project(root: Path, *, strict: bool = False) -> list[str]:
    root = root.resolve()
    qdir = project_dir(root)
    gd = gates_dir(root)
    errors: list[str] = []

    path_errors = governed_path_errors(root)
    if path_errors:
        return path_errors

    if not qdir.exists():
        return [f"quality-gates workspace not found: {qdir}"] if strict else []
    if not gd.exists():
        return [f"gates directory not found: {gd}"] if strict else []

    try:
        policy = load_policy(root)
    except GateParseError as exc:
        errors.append(str(exc))
        policy = Policy()

    unexpected_md = sorted(p for p in gd.iterdir() if p.is_file() and p.suffix.lower() == ".md" and not GATE_FILE_RE.fullmatch(p.name))
    for path in unexpected_md:
        errors.append(f"{path}: unexpected Markdown file in gates directory; expected canonical GATE-<number>.md")

    paths = gate_paths(root)
    if not paths:
        if strict:
            errors.append(f"no gate records found in {gd}")
        return _dedupe(errors)

    parsed: list[GateSummary] = []
    numeric_counts: dict[int, int] = {}
    canonical_ids: set[str] = set()
    for path in paths:
        file_match = GATE_FILE_RE.fullmatch(path.name)
        if file_match:
            number = int(file_match.group(1))
            if number >= 1:
                numeric_counts[number] = numeric_counts.get(number, 0) + 1
                canonical_ids.add(f"GATE-{number:03d}")
        try:
            gate = parse_gate(path)
            parsed.append(gate)
            number = int(gate.gate_id.split("-", 1)[1])
            numeric_counts[number] = max(numeric_counts.get(number, 0), 1)
            canonical_ids.add(f"GATE-{number:03d}")
        except GateParseError as exc:
            errors.append(str(exc))

    # Detect multiple filenames / headers resolving to the same numeric identity.
    path_numbers: dict[int, list[str]] = {}
    for path in paths:
        match = GATE_FILE_RE.fullmatch(path.name)
        if match and int(match.group(1)) >= 1:
            path_numbers.setdefault(int(match.group(1)), []).append(path.name)
    for number, names in path_numbers.items():
        if len(names) > 1:
            errors.append(f"duplicate logical gate ID GATE-{number:03d} appears in: {', '.join(sorted(names))}")

    parsed_by_id = {g.gate_id: g for g in parsed}
    for path in paths:
        errors.extend(validate_gate(path, canonical_ids, root, strict=strict, policy=policy, gate_by_id=parsed_by_id))

    # Only canonical, uniquely named, parseable gates participate in dependency graph checks.
    gate_by_id: dict[str, GateSummary] = {}
    for gate in parsed:
        try:
            canonical = canonical_gate_id(gate.gate_id)
        except GateParseError:
            continue
        if gate.gate_id == canonical and gate.path.name == f"{canonical}.md" and len(path_numbers.get(int(canonical.split("-")[1]), [])) == 1:
            gate_by_id[canonical] = gate

    visiting: list[str] = []
    visited: set[str] = set()
    reported_cycles: set[tuple[str, ...]] = set()

    def visit(gate_id: str) -> None:
        if gate_id in visiting:
            start = visiting.index(gate_id)
            cycle = tuple(visiting[start:] + [gate_id])
            if cycle not in reported_cycles:
                errors.append(f"dependency cycle detected: {' -> '.join(cycle)}")
                reported_cycles.add(cycle)
            return
        if gate_id in visited or gate_id not in gate_by_id:
            return
        visiting.append(gate_id)
        for dep in gate_by_id[gate_id].dependencies:
            if dep in gate_by_id:
                visit(dep)
        visiting.pop()
        visited.add(gate_id)

    for gate_id in gate_by_id:
        visit(gate_id)

    for gate in gate_by_id.values():
        if gate.status in {"OPEN", "CLOSED"}:
            for dep in gate.dependencies:
                dep_gate = gate_by_id.get(dep)
                if dep_gate and not dep_gate.closed:
                    errors.append(f"{gate.gate_id}: {gate.status.lower()} while dependency {dep} is not closed")

    return _dedupe(errors)


# ---------- closure / release policy ----------


def verification_precondition_errors(root: Path, gate_id: str, *, strict: bool = True) -> list[str]:
    """Preconditions for recording Verify: Analyze through Re-test complete, evidence complete."""
    project_errors = validate_project(root, strict=False)
    if project_errors:
        return project_errors
    gates = list_gates(root)
    gate_by_id = {g.gate_id: g for g in gates}
    gate = gate_by_id.get(gate_id)
    if gate is None:
        return [f"unknown gate '{gate_id}'"]
    if gate.status != "OPEN":
        return [f"{gate_id}: only OPEN gates can be verified"]
    text = gate.path.read_text(encoding="utf-8")
    errors: list[str] = []
    checks = parse_stage_checks(text)
    if checks[:7] != [True] * 7 or any(checks[7:]):
        errors.append(f"{gate_id}: Analyze through Re-test must be complete while Verify and Close Gate remain pending")

    acs = parse_acceptance_criteria(text)
    collected = parse_evidence_collected(text)
    mappings = {ac_id: evids for ac_id, evids, _ in parse_verification(text)}
    collected_ids = {record.evidence_id for record in collected if record.result == "PASS"}
    for ac_id, checked, desc in acs:
        if not checked:
            errors.append(f"{gate_id}: acceptance criterion {ac_id} is not satisfied")
        if _normalize(desc) in AC_PLACEHOLDERS:
            errors.append(f"{gate_id}: acceptance criterion {ac_id} is a placeholder")
        if ac_id not in mappings:
            errors.append(f"{gate_id}: acceptance criterion {ac_id} lacks verification evidence")
        elif not set(mappings[ac_id]).issubset(collected_ids):
            errors.append(f"{gate_id}: acceptance criterion {ac_id} references evidence that is not PASS")

    for evid_id, checked, evidence_type, desc in parse_evidence_required(text):
        if not checked:
            errors.append(f"{gate_id}: evidence requirement {evid_id} is not satisfied")
        if _normalize(desc) in EVIDENCE_PLACEHOLDERS:
            errors.append(f"{gate_id}: evidence requirement {evid_id} is a placeholder")
        record = next((item for item in collected if item.evidence_id == evid_id), None)
        if record is None:
            errors.append(f"{gate_id}: missing collected evidence {evid_id}")
        else:
            ref_error = _valid_evidence_ref(root.resolve(), evidence_type, record.ref, strict)
            if ref_error:
                errors.append(f"{gate_id}: {evid_id} {ref_error}")
            if record.result != "PASS":
                errors.append(f"{gate_id}: {evid_id} must have result=PASS")

    for dep in gate.dependencies:
        dep_gate = gate_by_id.get(dep)
        if dep_gate is None or not dep_gate.closed:
            errors.append(f"{gate_id}: dependency {dep} is not closed")
    return _dedupe(errors)


def fresh_verification_errors(root: Path, gate_id: str, *, strict: bool = True) -> list[str]:
    errors = validate_project(root, strict=strict)
    if errors:
        return errors
    gate = {g.gate_id: g for g in list_gates(root)}.get(gate_id)
    if gate is None:
        return [f"unknown gate '{gate_id}'"]
    if gate.status != "OPEN":
        return [f"{gate_id}: only OPEN gates can be approved/closed"]
    text = gate.path.read_text(encoding="utf-8")
    checks = parse_stage_checks(text)
    if checks[:8] != [True] * 8 or checks[8]:
        return [f"{gate_id}: Analyze through Verify must be complete and Close Gate must remain pending"]
    if _is_none(gate.verified_on) or _is_none(gate.verification_fingerprint):
        return [f"{gate_id}: a fresh verification record is required"]
    if gate.verification_fingerprint != verification_fingerprint(text):
        return [f"{gate_id}: verification is stale because material content changed after Verify"]
    return []


def closure_precondition_errors(root: Path, gate_id: str, *, strict: bool = True) -> list[str]:
    errors = fresh_verification_errors(root, gate_id, strict=strict)
    if errors:
        return errors
    gate = {g.gate_id: g for g in list_gates(root)}.get(gate_id)
    if gate is None:
        return [f"unknown gate '{gate_id}'"]
    if gate.review_required:
        if gate.approval != "APPROVED":
            errors.append(f"{gate_id}: independent review approval is required")
        else:
            text = gate.path.read_text(encoding="utf-8")
            expected = approval_fingerprint(text)
            if gate.approval_fingerprint != expected:
                errors.append(f"{gate_id}: approval is stale because reviewed content changed after approval")
    return _dedupe(errors)


def release_check(root: Path) -> list[str]:
    root = root.resolve()
    errors = validate_project(root, strict=True)
    if errors:
        return errors
    try:
        policy = load_policy(root)
    except GateParseError as exc:
        return [str(exc)]
    gates = list_gates(root)
    blockers: list[str] = []
    for gate in gates:
        if gate.severity not in policy.blocking_severities:
            continue
        if gate.status == "CLOSED":
            continue
        if gate.status == "WAIVED" and policy.allow_waived_blocking:
            continue
        if gate.status == "DEFERRED" and policy.allow_deferred_blocking:
            continue
        blockers.append(f"{gate.gate_id}: release blocked by {gate.severity.upper()} gate in status {gate.status}")
    return blockers
