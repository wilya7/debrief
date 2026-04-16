# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-22.

BUG-AUDIT-22 replaced the hard-delete ``/debrief:reset`` with a
backup-restore ``/debrief:restore``. These tests exercise:

1. List mode — prints available snapshots, returns without side effects.
2. Restore from snapshot — overwrites deck_state.json, optionally
   ledger.jsonl, sweeps orphan slides, writes restore_log entry.
3. Preservation of non-state files — CLAUDE.md, debrief_state.json,
   style_config.json, etc. are never touched by restore.
4. Invalid label handling — exits code 2 with descriptive message.
5. Auto-save safety net — pre_restore_<ts> snapshot created before
   overwrite; contains the pre-restore deck_state.json.

All tests run in both workspace and delivered layouts via sibling
discovery; zero skips.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


def _utility_skills_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_11"
    return _PROJECT_ROOT / "src" / "debrief"


def _debrief_state_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_2"
    return _PROJECT_ROOT / "src" / "debrief"


for _dir in (_debrief_state_module_dir(), _utility_skills_module_dir()):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture helpers.
# ---------------------------------------------------------------------------

_TS = "2026-04-16T12:00:00Z"


def _deck_state_dict(
    slides: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    return {
        "project_name": "bug_audit_22_test",
        "created_at": _TS,
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": slides if slides is not None else [],
        "presentations": [],
    }


def _slide_dict(slug: str, **kw: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "slug": slug,
        "title": f"Title of {slug}",
        "status": "approved",
        "backup": False,
        "content_summary": f"Summary for {slug}",
        "visual_approach": "Diagram",
        "design_choices": "Minimal",
        "forks_not_taken": None,
        "user_recommendations": None,
        "qa_passed": True,
        "accepted_violations": [],
        "last_modified": _TS,
        "group_id": "group_01",
        "user_assets": [],
        "has_math": False,
    }
    defaults.update(kw)
    return defaults


def _setup_project_with_snapshot(
    root: Path,
    *,
    current_slides: list[str],
    snapshot_label: str,
    snapshot_slides: list[str],
    extra_slide_html: Optional[list[str]] = None,
) -> None:
    """Build a synthetic project with a snapshot for restore testing.

    - Writes deck_state.json with `current_slides` slugs.
    - Creates slides/<slug>.html for each current slug + any extras.
    - Creates output/snapshots/<label>/deck_state.json with `snapshot_slides`.
    """
    current_state = _deck_state_dict(
        slides=[_slide_dict(s) for s in current_slides]
    )
    (root / "deck_state.json").write_text(
        json.dumps(current_state), encoding="utf-8"
    )

    slides_dir = root / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    for slug in current_slides:
        (slides_dir / f"{slug}.html").write_text(
            f"<html>{slug}</html>", encoding="utf-8"
        )
    for slug in (extra_slide_html or []):
        (slides_dir / f"{slug}.html").write_text(
            f"<html>{slug}</html>", encoding="utf-8"
        )

    snap_state = _deck_state_dict(
        slides=[_slide_dict(s) for s in snapshot_slides]
    )
    snap_dir = root / "output" / "snapshots" / snapshot_label
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / "deck_state.json").write_text(
        json.dumps(snap_state), encoding="utf-8"
    )


# ===========================================================================
# TestRestoreListMode
# ===========================================================================


class TestRestoreListMode:
    """BC-11.11: list mode prints available snapshots."""

    def test_list_with_snapshots_prints_labels(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        snap_base = tmp_path / "output" / "snapshots"
        for lbl in ("alpha", "beta", "gamma"):
            d = snap_base / lbl
            d.mkdir(parents=True)
            (d / "deck_state.json").write_text("{}")
        # gamma_invalid has no deck_state.json — should be excluded
        (snap_base / "gamma_invalid").mkdir()

        utility_skills.skill_restore(None, tmp_path)

        out = capsys.readouterr().err
        assert "alpha" in out
        assert "beta" in out
        assert "gamma" in out
        assert "gamma_invalid" not in out

    def test_list_with_no_snapshots_prints_guidance(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        utility_skills.skill_restore(None, tmp_path)
        out = capsys.readouterr().err
        assert "no snapshots" in out.lower() or "/debrief:save" in out

    def test_list_with_ledger_in_snapshot_shows_contents(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        d = tmp_path / "output" / "snapshots" / "with_ledger"
        d.mkdir(parents=True)
        (d / "deck_state.json").write_text("{}")
        (d / "ledger.jsonl").write_text("")

        utility_skills.skill_restore(None, tmp_path)

        out = capsys.readouterr().err
        assert "ledger.jsonl" in out


# ===========================================================================
# TestRestoreFromSnapshot
# ===========================================================================


class TestRestoreFromSnapshot:
    """BC-11.11: restore mode overwrites state and sweeps orphans."""

    def test_deck_state_overwritten_from_snapshot(
        self,
        tmp_path: Path,
    ) -> None:
        _setup_project_with_snapshot(
            tmp_path,
            current_slides=["intro", "methods"],
            snapshot_label="v1",
            snapshot_slides=["intro"],
        )

        utility_skills.skill_restore("v1", tmp_path)

        restored = json.loads(
            (tmp_path / "deck_state.json").read_text(encoding="utf-8")
        )
        slugs = [s["slug"] for s in restored["slides"]]
        assert slugs == ["intro"]

    def test_orphan_slides_swept_after_restore(
        self,
        tmp_path: Path,
    ) -> None:
        _setup_project_with_snapshot(
            tmp_path,
            current_slides=["intro", "methods", "results"],
            snapshot_label="v1",
            snapshot_slides=["intro"],
        )

        utility_skills.skill_restore("v1", tmp_path)

        slides_dir = tmp_path / "slides"
        remaining = sorted(p.stem for p in slides_dir.glob("*.html"))
        assert remaining == ["intro"], (
            f"Expected only 'intro' after restore; got {remaining}"
        )

    def test_restore_log_entry_written_to_ledger(
        self,
        tmp_path: Path,
    ) -> None:
        _setup_project_with_snapshot(
            tmp_path,
            current_slides=["intro"],
            snapshot_label="v1",
            snapshot_slides=["intro"],
        )
        (tmp_path / "ledger.jsonl").write_text("", encoding="utf-8")

        utility_skills.skill_restore("v1", tmp_path)

        ledger = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
        lines = [l for l in ledger.strip().splitlines() if l.strip()]
        assert len(lines) >= 1
        entry = json.loads(lines[-1])
        assert entry["event"] == "restore"
        assert entry["restored_from"] == "v1"
        assert "auto_saved_as" in entry
        assert "swept_slugs" in entry

    def test_ledger_restored_from_snapshot_when_present(
        self,
        tmp_path: Path,
    ) -> None:
        _setup_project_with_snapshot(
            tmp_path,
            current_slides=["intro"],
            snapshot_label="v1",
            snapshot_slides=["intro"],
        )
        (tmp_path / "ledger.jsonl").write_text(
            '{"event":"old"}\n', encoding="utf-8"
        )
        snap_ledger = (
            tmp_path / "output" / "snapshots" / "v1" / "ledger.jsonl"
        )
        snap_ledger.write_text(
            '{"event":"snapshot_entry"}\n', encoding="utf-8"
        )

        utility_skills.skill_restore("v1", tmp_path)

        ledger = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
        assert "snapshot_entry" in ledger
        assert "restore" in ledger  # restore_log entry appended after


# ===========================================================================
# TestRestorePreservesNonStateFiles
# ===========================================================================


class TestRestorePreservesNonStateFiles:
    """BC-11.12: restore only touches deck_state, ledger, and orphan slides."""

    def test_claude_md_untouched(self, tmp_path: Path) -> None:
        _setup_project_with_snapshot(
            tmp_path,
            current_slides=["intro"],
            snapshot_label="v1",
            snapshot_slides=["intro"],
        )
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Original CLAUDE.md\n", encoding="utf-8")

        utility_skills.skill_restore("v1", tmp_path)

        assert claude_md.read_text(encoding="utf-8") == "# Original CLAUDE.md\n"

    def test_debrief_state_json_untouched(self, tmp_path: Path) -> None:
        _setup_project_with_snapshot(
            tmp_path,
            current_slides=["intro"],
            snapshot_label="v1",
            snapshot_slides=["intro"],
        )
        ds = tmp_path / "debrief_state.json"
        ds.write_text('{"phase":"production"}', encoding="utf-8")

        utility_skills.skill_restore("v1", tmp_path)

        assert json.loads(ds.read_text())["phase"] == "production"

    def test_style_config_untouched(self, tmp_path: Path) -> None:
        _setup_project_with_snapshot(
            tmp_path,
            current_slides=["intro"],
            snapshot_label="v1",
            snapshot_slides=["intro"],
        )
        sc = tmp_path / "style_config.json"
        sc.write_text('{"colors":{"primary":"#000"}}', encoding="utf-8")

        utility_skills.skill_restore("v1", tmp_path)

        assert json.loads(sc.read_text())["colors"]["primary"] == "#000"

    def test_dot_debrief_directory_untouched(self, tmp_path: Path) -> None:
        _setup_project_with_snapshot(
            tmp_path,
            current_slides=["intro"],
            snapshot_label="v1",
            snapshot_slides=["intro"],
        )
        draft = tmp_path / ".debrief" / "draft"
        draft.mkdir(parents=True)
        (draft / "wip.json").write_text("{}", encoding="utf-8")

        utility_skills.skill_restore("v1", tmp_path)

        assert (draft / "wip.json").is_file()

    def test_assets_directory_untouched(self, tmp_path: Path) -> None:
        _setup_project_with_snapshot(
            tmp_path,
            current_slides=["intro"],
            snapshot_label="v1",
            snapshot_slides=["intro"],
        )
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "style.css").write_text("body{}", encoding="utf-8")

        utility_skills.skill_restore("v1", tmp_path)

        assert (assets / "style.css").is_file()


# ===========================================================================
# TestRestoreInvalidLabel
# ===========================================================================


class TestRestoreInvalidLabel:
    """BC-11.11: invalid label → exit 2 with descriptive message."""

    def test_nonexistent_label_exits_2(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        _setup_project_with_snapshot(
            tmp_path,
            current_slides=["intro"],
            snapshot_label="real_snapshot",
            snapshot_slides=["intro"],
        )

        with pytest.raises(SystemExit) as exc_info:
            utility_skills.skill_restore("nonexistent", tmp_path)
        assert exc_info.value.code == 2

        msg = capsys.readouterr().err.lower()
        assert "nonexistent" in msg
        assert "real_snapshot" in msg  # lists available

    def test_label_pointing_to_directory_without_deck_state(
        self,
        tmp_path: Path,
    ) -> None:
        d = tmp_path / "output" / "snapshots" / "empty_snap"
        d.mkdir(parents=True)
        # No deck_state.json inside — invalid snapshot

        (tmp_path / "deck_state.json").write_text(
            json.dumps(_deck_state_dict()), encoding="utf-8"
        )

        with pytest.raises(SystemExit) as exc_info:
            utility_skills.skill_restore("empty_snap", tmp_path)
        assert exc_info.value.code == 2


# ===========================================================================
# TestRestoreAutoSaveSafetyNet
# ===========================================================================


class TestRestoreAutoSaveSafetyNet:
    """BC-11.11 step 2: auto-save current state before overwrite."""

    def test_auto_save_snapshot_created_before_overwrite(
        self,
        tmp_path: Path,
    ) -> None:
        _setup_project_with_snapshot(
            tmp_path,
            current_slides=["intro", "methods"],
            snapshot_label="v1",
            snapshot_slides=["intro"],
        )

        utility_skills.skill_restore("v1", tmp_path)

        # Find auto-save snapshot
        snaps = tmp_path / "output" / "snapshots"
        auto_saves = [
            d.name for d in snaps.iterdir()
            if d.is_dir() and d.name.startswith("pre_restore_")
        ]
        assert len(auto_saves) == 1, (
            f"Expected exactly one auto-save snapshot; found {auto_saves}"
        )

    def test_auto_save_contains_pre_restore_deck_state(
        self,
        tmp_path: Path,
    ) -> None:
        current_state = _deck_state_dict(
            slides=[_slide_dict("intro"), _slide_dict("methods")]
        )
        (tmp_path / "deck_state.json").write_text(
            json.dumps(current_state), encoding="utf-8"
        )
        (tmp_path / "slides").mkdir()

        snap_state = _deck_state_dict(slides=[_slide_dict("intro")])
        snap_dir = tmp_path / "output" / "snapshots" / "v1"
        snap_dir.mkdir(parents=True)
        (snap_dir / "deck_state.json").write_text(
            json.dumps(snap_state), encoding="utf-8"
        )

        utility_skills.skill_restore("v1", tmp_path)

        snaps = tmp_path / "output" / "snapshots"
        auto_save_dir = next(
            d for d in snaps.iterdir()
            if d.name.startswith("pre_restore_")
        )
        auto_saved = json.loads(
            (auto_save_dir / "deck_state.json").read_text(encoding="utf-8")
        )
        auto_slugs = [s["slug"] for s in auto_saved["slides"]]
        assert auto_slugs == ["intro", "methods"], (
            f"Auto-save should contain pre-restore state with both "
            f"slides; got {auto_slugs}"
        )
