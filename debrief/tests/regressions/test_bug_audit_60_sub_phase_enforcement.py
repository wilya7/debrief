# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-60 Cluster 1 (sub_phase state management).

Smoke test Round 3 surfaced three bugs in sub_phase handling:

- BUG-ST-a-2 (HIGH): consultant.md §"Valid sub_phase Values" drifted from
  SUB_PHASE_VALUES / spec §14.17 + blueprint BC-2.15. Secondary: write path
  did not validate sub_phase, so invalid values persisted to disk and
  crashed the next read with StateCorruptError.
- BUG-ST-a-3 (HIGH): smoke test prompt used `finalization/complete` and
  `complete/done` (both invalid) — symptom of a-2. Addressed by fixing the
  prompt, not by code; not covered here.
- BUG-ST-a-5 (LOW): cli_update_state set fields blindly; phase not derived
  from sub_phase prefix, so `sub_phase=production/...` with implicit
  `phase=discovery` left the state mis-gated for /debrief:view.

This file covers the contract changes (REQ-STATE-ENUM-1/2/3; BC-2.15,
BC-2.15a, BC-2.15b):

1. write_debrief_state rejects invalid sub_phase (file unchanged).
2. cli_update_state derives phase from sub_phase prefix.
3. cli_update_state exits 1 on inconsistent explicit phase/sub_phase.
4. consultant.md's §"Valid sub_phase Values" ≡ SUB_PHASE_VALUES.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_2").is_dir()


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import debrief_state  # noqa: E402


def _consultant_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    return _PROJECT_ROOT / "agents" / "consultant.md"


def _make_state(**overrides) -> debrief_state.DebriefState:
    """Build a DebriefState with sensible defaults for testing writes."""
    base = {
        "phase": "discovery",
        "sub_phase": "discovery/greeting",
        "active_agent": "consultant",
        "archetype": "conference_talk",
        "current_group_id": None,
        "current_slide_slug": None,
        "pending_gate": None,
        "last_gate_response": None,
        "red_green_started_at": None,
        "group_slide_index": 0,
        "group_slide_count": 0,
        "backup_mode": False,
        "completed_groups": [],
        "pre_view_state": None,
        "view_deferred": False,
        "closing_slide_pending": False,
        "group_revise_slug": None,
        "style_import_mode": None,
        "reference_provided": False,
        "reference_modality": None,
        "papers_provided": False,
        "selected_figures": None,
        "session_started_at": "2026-04-18T00:00:00+00:00",
        "state_hash": "",
    }
    base.update(overrides)
    return debrief_state.DebriefState(**base)


def _init_project(project_root: Path) -> None:
    """Initialize a minimal project dir with a valid debrief_state.json."""
    (project_root / ".debrief").mkdir(parents=True, exist_ok=True)
    debrief_state.write_debrief_state(project_root, _make_state())


# ---------------------------------------------------------------------------
# 1. write_debrief_state validates sub_phase before writing
# ---------------------------------------------------------------------------


def test_write_rejects_invalid_sub_phase(tmp_path):
    """BUG-AUDIT-60 / REQ-STATE-ENUM-2 / BC-2.15:
    write_debrief_state must call validate_debrief_state before atomic_write_json.
    Invalid sub_phase must raise StateCorruptError; on-disk file must be unchanged.
    """
    _init_project(tmp_path)
    dest = tmp_path / "debrief_state.json"
    before = dest.read_text(encoding="utf-8")

    bad_state = _make_state(sub_phase="production/backup_decision")  # not in SUB_PHASE_VALUES

    with pytest.raises(debrief_state.StateCorruptError, match="sub_phase"):
        debrief_state.write_debrief_state(tmp_path, bad_state)

    after = dest.read_text(encoding="utf-8")
    assert after == before, (
        "write_debrief_state must NOT have modified the file on validation failure"
    )


def test_write_rejects_other_known_bogus_values(tmp_path):
    """Spot-check the specific bogus values from the pre-fix consultant.md
    (BUG-ST-a-2). All must be rejected by write validation."""
    _init_project(tmp_path)
    bogus_values = [
        "discovery/reference_import",
        "production/brief_dispatch",
        "production/slide_authoring",
        "production/backup_decision",
        "production/closing_slide",
        "finalization/export_ordering",
        "finalization/complete",
        "complete/done",
        "complete/idle",
    ]
    for bad in bogus_values:
        with pytest.raises(debrief_state.StateCorruptError):
            debrief_state.write_debrief_state(tmp_path, _make_state(sub_phase=bad))


def test_write_accepts_all_canonical_values(tmp_path):
    """Every value in SUB_PHASE_VALUES must write successfully."""
    _init_project(tmp_path)
    for value in debrief_state.SUB_PHASE_VALUES:
        derived_phase = value.split("/", 1)[0] if "/" in value else value
        debrief_state.write_debrief_state(
            tmp_path, _make_state(sub_phase=value, phase=derived_phase)
        )


# ---------------------------------------------------------------------------
# 2. cli_update_state derives phase from sub_phase prefix
# ---------------------------------------------------------------------------


def _run_update_cli(project_root: Path, assignments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "debrief_state" if _is_workspace_layout() else "debrief.debrief_state",
            "update",
            "--project-root",
            str(project_root),
            "--set",
            *assignments,
        ],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "")),
    )


def test_cli_update_derives_phase_from_sub_phase(tmp_path):
    """BUG-AUDIT-60 / REQ-STATE-ENUM-3 / BC-2.15a:
    When only sub_phase is passed, phase must be derived from its prefix.
    """
    _init_project(tmp_path)
    # Use the in-process entry point rather than subprocess to avoid sys.path fuss
    debrief_state.cli_update_state(tmp_path, ["sub_phase=production/slide_review"])
    state = debrief_state.read_debrief_state(tmp_path)
    assert state.sub_phase == "production/slide_review"
    assert state.phase == "production", (
        f"phase should be derived from sub_phase prefix; got {state.phase!r}"
    )


def test_cli_update_derives_phase_for_bare_complete(tmp_path):
    """The `complete` value has no `/` — derived phase is the whole value."""
    _init_project(tmp_path)
    # Need to be in finalization/post_export or similar so that jumping to
    # complete doesn't fail some cross-field invariant. Just go direct.
    debrief_state.cli_update_state(tmp_path, ["sub_phase=complete"])
    state = debrief_state.read_debrief_state(tmp_path)
    assert state.sub_phase == "complete"
    assert state.phase == "complete"


def test_cli_update_accepts_consistent_explicit_pair(tmp_path):
    _init_project(tmp_path)
    debrief_state.cli_update_state(
        tmp_path, ["phase=production", "sub_phase=production/red_green"]
    )
    state = debrief_state.read_debrief_state(tmp_path)
    assert state.phase == "production"
    assert state.sub_phase == "production/red_green"


def test_cli_update_rejects_inconsistent_explicit_pair(tmp_path, capsys):
    """BC-2.15a: phase/sub_phase mismatch must exit 1 with a descriptive error."""
    _init_project(tmp_path)
    before = (tmp_path / "debrief_state.json").read_text(encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        debrief_state.cli_update_state(
            tmp_path,
            ["phase=discovery", "sub_phase=production/red_green"],
        )
    assert excinfo.value.code == 1

    captured = capsys.readouterr()
    assert "inconsistent" in captured.err.lower() or "phase" in captured.err.lower()

    after = (tmp_path / "debrief_state.json").read_text(encoding="utf-8")
    assert after == before, "state file must be unchanged on rejected update"


# ---------------------------------------------------------------------------
# 3. consultant.md's §"Valid sub_phase Values" list ≡ SUB_PHASE_VALUES
# ---------------------------------------------------------------------------


_SUB_PHASE_SECTION_HEADER = re.compile(r"^##\s+Valid\s+sub_phase\s+Values", re.MULTILINE)
_BACKTICK_TOKEN = re.compile(r"`([a-z_/]+)`")


def _parse_consultant_sub_phase_list(md_text: str) -> set[str]:
    """Extract the set of sub_phase values listed in consultant.md's
    §"Valid sub_phase Values" section. Reads the comma-delimited backticked
    list that follows the header until the next `## ` heading.
    """
    m = _SUB_PHASE_SECTION_HEADER.search(md_text)
    assert m, "consultant.md is missing §'Valid sub_phase Values' section"
    tail = md_text[m.end():]
    # Stop at the next level-2 heading
    next_header = re.search(r"\n##\s", tail)
    section = tail[: next_header.start()] if next_header else tail
    tokens = _BACKTICK_TOKEN.findall(section)
    # Only keep tokens that look like sub_phase values: either
    # `<phase>/<subphase>` with alpha on both sides of the slash, or the
    # single canonical bare value `complete`. Exclude stray backticked
    # tokens from surrounding prose (e.g., `/`, variable names).
    sub_phase_shape = re.compile(r"^[a-z_]+/[a-z_]+$")
    return {
        tok for tok in tokens
        if sub_phase_shape.match(tok) or tok == "complete"
    }


def test_consultant_md_sub_phase_list_equals_code_constant():
    """BUG-AUDIT-60 / REQ-STATE-ENUM-1 / BC-2.15b:
    consultant.md's documented enumeration must set-equal SUB_PHASE_VALUES.
    Drift is a CRITICAL regression.
    """
    md_path = _consultant_md_path()
    assert md_path.is_file(), f"consultant.md not found at {md_path}"

    documented = _parse_consultant_sub_phase_list(md_path.read_text(encoding="utf-8"))
    canonical = set(debrief_state.SUB_PHASE_VALUES)

    missing_from_doc = canonical - documented
    extra_in_doc = documented - canonical

    assert not missing_from_doc, (
        f"consultant.md is missing canonical sub_phase values: "
        f"{sorted(missing_from_doc)}"
    )
    assert not extra_in_doc, (
        f"consultant.md lists sub_phase values not in SUB_PHASE_VALUES: "
        f"{sorted(extra_in_doc)}"
    )
