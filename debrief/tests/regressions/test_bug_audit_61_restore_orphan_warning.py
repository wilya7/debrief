# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-61 — restore orphan-output warning.

BUG-ST-round4-a-1 (MEDIUM): `/debrief:restore` preserves `output/<date>/`
folders per BC-11.12 but leaves the user with orphan PDFs/scripts/handouts
that aren't referenced by the restored deck_state.presentations. Pre-fix
no warning was emitted — users could be weeks later wondering why their
PDFs don't match their state.

BUG-AUDIT-61 / REQ-RESTORE-WARN-1 / BC-11.12a: after the BC-11.11 step 6
confirmation print, `skill_restore` enumerates `output/<YYYY_MM_DD_*>/`
folders, diffs against `presentations[].folder` in the restored state,
and for each orphan prints a warning + appends a `restore_orphan_warning`
ledger entry. Files are NOT deleted — scope of BC-11.12 is preserved.

Coverage:

1. Orphan folder on disk, no reference in restored state → warning
   printed to stderr + ledger entry appended.
2. Orphan folder exists but IS referenced in restored state → no warning
   (not an orphan).
3. No orphans → no warning, no ledger entry for this event type.
4. Orphan files are NOT deleted after restore (BC-11.12 scope preserved).
5. Non-dated subdirectories under output/ (e.g., `snapshots/`,
   `handouts/`, `screenshots/`) are ignored by the audit — only
   `YYYY_MM_DD_*` folders are candidates.
6. When the restored state is unreadable, the audit degrades gracefully
   (still emits warnings for observable dated folders; does not crash).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_11" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_3" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_7" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_10" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402
import debrief_state  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_slide(slug: str) -> debrief_state.SlideRecord:
    return debrief_state.SlideRecord(
        slug=slug,
        title=slug,
        status="approved",
        backup=False,
        content_summary=None,
        visual_approach=None,
        design_choices=None,
        forks_not_taken=None,
        user_recommendations=None,
        qa_passed=True,
        accepted_violations=[],
        last_modified="2026-04-18T00:00:00+00:00",
        group_id=None,
        user_assets=[],
        has_math=False,
    )


def _make_presentation(folder: str) -> debrief_state.PresentationRecord:
    return debrief_state.PresentationRecord(
        folder=folder,
        created_at="2026-04-18",
        slide_manifest=[],
        export_count=0,
        script_count=0,
        handout_count=0,
        separator_position=None,
        separator_content=None,
    )


def _setup_restored_project(
    root: Path,
    *,
    dated_folders: list[str],
    presentation_folders: list[str],
) -> Path:
    """Create a project with:
    - deck_state.json referencing `presentation_folders` in its
      presentations[] list,
    - `output/<folder>/` subdirs on disk for every `dated_folders` entry,
      each containing a dummy deck_v001.pdf.
    Returns the ledger.jsonl path.
    """
    (root / ".debrief").mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(parents=True, exist_ok=True)

    # Create dated folders on disk
    for name in dated_folders:
        folder = root / "output" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "deck_v001.pdf").write_bytes(b"%PDF-1.4\n%EOF\n")

    # Write restored deck_state.json
    deck = debrief_state.DeckState(
        project_name="demo",
        created_at="2026-04-18T00:00:00+00:00",
        archetype="conference_talk",
        style_locked=True,
        closing_slide=None,
        slides=[_make_slide("hook")],
        presentations=[_make_presentation(f) for f in presentation_folders],
    )
    debrief_state.write_deck_state(root, deck)

    ledger_path = root / "ledger.jsonl"
    ledger_path.write_text("", encoding="utf-8")
    return ledger_path


def _read_ledger_events(ledger_path: Path, event: str) -> list[dict]:
    """Return every JSON line in the ledger whose top-level `event` == event."""
    if not ledger_path.is_file():
        return []
    out = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get("event") == event:
            out.append(entry)
    return out


# ---------------------------------------------------------------------------
# 1. Orphan folder → warning + ledger entry
# ---------------------------------------------------------------------------


def test_orphan_folder_emits_warning_and_ledger_entry(tmp_path, capsys):
    """REQ-RESTORE-WARN-1 / BC-11.12a: an output/<date>/ folder on disk
    that isn't in the restored presentations list must trigger one
    stderr warning and one ledger entry."""
    ledger = _setup_restored_project(
        tmp_path,
        dated_folders=["2026_04_18_project"],
        presentation_folders=[],  # restored state has no presentations
    )

    utility_skills._emit_orphan_output_warnings(tmp_path, ledger)

    captured = capsys.readouterr()
    assert "orphan" in captured.err.lower()
    assert "2026_04_18_project" in captured.err
    assert "1 file" in captured.err or "1 files" in captured.err

    entries = _read_ledger_events(ledger, "restore_orphan_warning")
    assert len(entries) == 1
    assert entries[0]["orphan_folder"] == "output/2026_04_18_project"
    assert entries[0]["file_count"] == 1
    assert "timestamp" in entries[0]


# ---------------------------------------------------------------------------
# 2. Referenced folder is NOT an orphan → no warning
# ---------------------------------------------------------------------------


def test_referenced_folder_is_not_orphan(tmp_path, capsys):
    ledger = _setup_restored_project(
        tmp_path,
        dated_folders=["2026_04_18_project"],
        presentation_folders=["2026_04_18_project"],
    )

    utility_skills._emit_orphan_output_warnings(tmp_path, ledger)

    captured = capsys.readouterr()
    assert captured.err == ""
    entries = _read_ledger_events(ledger, "restore_orphan_warning")
    assert entries == []


# ---------------------------------------------------------------------------
# 3. No dated folders → no warning, no entry
# ---------------------------------------------------------------------------


def test_no_dated_folders_means_silence(tmp_path, capsys):
    ledger = _setup_restored_project(
        tmp_path,
        dated_folders=[],
        presentation_folders=[],
    )

    utility_skills._emit_orphan_output_warnings(tmp_path, ledger)

    captured = capsys.readouterr()
    assert captured.err == ""
    assert _read_ledger_events(ledger, "restore_orphan_warning") == []


# ---------------------------------------------------------------------------
# 4. Orphan files are NOT deleted (BC-11.12 scope preserved)
# ---------------------------------------------------------------------------


def test_orphan_files_are_not_deleted(tmp_path):
    """BC-11.12: restore MUST NOT delete output/. The orphan-warning
    addition (BC-11.12a) preserves that scope — it only emits warnings."""
    ledger = _setup_restored_project(
        tmp_path,
        dated_folders=["2026_04_18_project"],
        presentation_folders=[],
    )
    pdf = tmp_path / "output" / "2026_04_18_project" / "deck_v001.pdf"

    utility_skills._emit_orphan_output_warnings(tmp_path, ledger)

    assert pdf.is_file(), (
        "orphan PDF must NOT be deleted by the warning audit "
        "(BC-11.12 scope preservation)."
    )


# ---------------------------------------------------------------------------
# 5. Non-dated output/ subdirectories are ignored
# ---------------------------------------------------------------------------


def test_non_dated_subdirs_are_ignored(tmp_path, capsys):
    """output/snapshots, output/handouts, output/screenshots are not
    dated-folder candidates and must be silently skipped."""
    ledger = _setup_restored_project(
        tmp_path,
        dated_folders=[],
        presentation_folders=[],
    )
    for name in ("snapshots", "handouts", "screenshots"):
        d = tmp_path / "output" / name
        d.mkdir(exist_ok=True)
        (d / "x.pdf").write_bytes(b"PDF")

    utility_skills._emit_orphan_output_warnings(tmp_path, ledger)

    captured = capsys.readouterr()
    assert captured.err == ""
    assert _read_ledger_events(ledger, "restore_orphan_warning") == []


# ---------------------------------------------------------------------------
# 6. Multiple orphans — each gets its own warning + ledger line
# ---------------------------------------------------------------------------


def test_multiple_orphans_each_logged(tmp_path, capsys):
    ledger = _setup_restored_project(
        tmp_path,
        dated_folders=["2026_04_18_a", "2026_04_18_b", "2026_04_18_c"],
        presentation_folders=["2026_04_18_b"],   # b is referenced; a and c are orphans
    )

    utility_skills._emit_orphan_output_warnings(tmp_path, ledger)

    captured = capsys.readouterr()
    err = captured.err
    assert "2026_04_18_a" in err
    assert "2026_04_18_c" in err
    assert "2026_04_18_b" not in err   # referenced, not an orphan

    entries = _read_ledger_events(ledger, "restore_orphan_warning")
    orphan_names = {e["orphan_folder"].rsplit("/", 1)[-1] for e in entries}
    assert orphan_names == {"2026_04_18_a", "2026_04_18_c"}


# ---------------------------------------------------------------------------
# 7. Integration: skill_restore actually calls the audit
# ---------------------------------------------------------------------------


def test_skill_restore_invokes_orphan_audit(tmp_path, capsys):
    """End-to-end: a snapshot exists whose presentations[] is empty, but
    the project has a dated output folder on disk. After skill_restore
    the orphan warning must appear."""
    _setup_restored_project(
        tmp_path,
        dated_folders=["2026_04_18_project"],
        presentation_folders=["2026_04_18_project"],  # pre-restore state
    )

    # Write a minimal debrief_state.json to satisfy skill_save's reads
    db_state = debrief_state.DebriefState(
        phase="production",
        sub_phase="finalization/post_export",
        active_agent="consultant",
        archetype="conference_talk",
        current_group_id=None,
        current_slide_slug=None,
        pending_gate=None,
        last_gate_response=None,
        red_green_started_at=None,
        group_slide_index=0,
        group_slide_count=0,
        backup_mode=False,
        completed_groups=[],
        pre_view_state=None,
        view_deferred=False,
        closing_slide_pending=False,
        group_revise_slug=None,
        style_import_mode=None,
        reference_provided=False,
        reference_modality=None,
        papers_provided=False,
        selected_figures=None,
        session_started_at="2026-04-18T00:00:00+00:00",
        state_hash="",
    )
    debrief_state.write_debrief_state(tmp_path, db_state)

    # Create a snapshot with NO presentations — this is what the restore
    # will rewrite deck_state.json to. Dated folder on disk will be orphaned.
    snap_dir = tmp_path / "output" / "snapshots" / "old_state"
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_deck = debrief_state.DeckState(
        project_name="demo",
        created_at="2026-04-18T00:00:00+00:00",
        archetype="conference_talk",
        style_locked=True,
        closing_slide=None,
        slides=[_make_slide("hook")],
        presentations=[],  # empty — so dated folder will be an orphan
    )
    debrief_state.write_deck_state(snap_dir, snap_deck)

    utility_skills.skill_restore("old_state", tmp_path)

    captured = capsys.readouterr()
    assert "orphan" in captured.err.lower()
    assert "2026_04_18_project" in captured.err

    entries = _read_ledger_events(
        tmp_path / "ledger.jsonl", "restore_orphan_warning"
    )
    assert len(entries) >= 1
