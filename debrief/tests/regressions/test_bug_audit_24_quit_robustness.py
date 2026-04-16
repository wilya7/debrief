# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-24.

BUG-AUDIT-24 hardens ``/debrief:quit`` with:
1. Defensive cycle-state check (belt-and-suspenders warning).
2. Summary output to stderr.
3. Transient artifact cleanup (.debrief/task_prompt.md, gate_data.json).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import pytest

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

_TS = "2026-04-16T12:00:00Z"


def _write_state_files(
    root: Path,
    *,
    phase: str = "production",
    sub_phase: str = "production/red_green",
    red_green_iteration: int = 0,
    slides: Optional[list[dict[str, Any]]] = None,
    style_locked: bool = True,
    presentations: Optional[list[dict[str, Any]]] = None,
) -> None:
    deck = {
        "project_name": "test",
        "created_at": _TS,
        "archetype": "lab_meeting",
        "style_locked": style_locked,
        "closing_slide": None,
        "slides": slides or [],
        "presentations": presentations or [],
    }
    (root / "deck_state.json").write_text(json.dumps(deck), encoding="utf-8")

    debrief = {
        "phase": phase,
        "sub_phase": sub_phase,
        "active_agent": "consultant",
        "archetype": "lab_meeting",
        "current_group_id": None,
        "current_slide_slug": None,
        "pending_gate": None,
        "last_gate_response": None,
        "red_green_iteration": red_green_iteration,
        "red_green_started_at": None,
        "group_slide_index": 0,
        "group_slide_count": 1,
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
        "session_started_at": _TS,
        "state_hash": "abc123",
    }
    (root / "debrief_state.json").write_text(
        json.dumps(debrief), encoding="utf-8"
    )


def _slide_dict(slug: str, **kw: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "slug": slug, "title": f"Title of {slug}", "status": "approved",
        "backup": False, "content_summary": "Summary",
        "visual_approach": "Diagram", "design_choices": "Minimal",
        "forks_not_taken": None, "user_recommendations": None,
        "qa_passed": True, "accepted_violations": [],
        "last_modified": _TS, "group_id": "g1",
        "user_assets": [], "has_math": False,
    }
    defaults.update(kw)
    return defaults


class TestQuitSummaryOutput:
    """BUG-AUDIT-24: quit must print a summary to stderr."""

    def test_summary_includes_phase_and_archetype(
        self, tmp_path: Path, capsys: pytest.CaptureFixture,
    ) -> None:
        _write_state_files(tmp_path, phase="production")
        utility_skills.skill_quit(tmp_path)
        msg = capsys.readouterr().err.lower()
        assert "production" in msg
        assert "lab_meeting" in msg

    def test_summary_includes_approved_slide_count(
        self, tmp_path: Path, capsys: pytest.CaptureFixture,
    ) -> None:
        _write_state_files(
            tmp_path,
            slides=[
                _slide_dict("s1"),
                _slide_dict("s2"),
                _slide_dict("s3", status="draft"),
                _slide_dict("s4", backup=True),
            ],
        )
        utility_skills.skill_quit(tmp_path)
        msg = capsys.readouterr().err
        assert "approved slides: 2" in msg

    def test_summary_includes_resume_instruction(
        self, tmp_path: Path, capsys: pytest.CaptureFixture,
    ) -> None:
        _write_state_files(tmp_path)
        utility_skills.skill_quit(tmp_path)
        msg = capsys.readouterr().err.lower()
        assert "resume" in msg or "debrief" in msg


class TestQuitTransientArtifactCleanup:
    """BUG-AUDIT-24: quit must clean task_prompt.md and gate_data.json."""

    def test_task_prompt_md_deleted(self, tmp_path: Path) -> None:
        _write_state_files(tmp_path)
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir(parents=True, exist_ok=True)
        (debrief_dir / "task_prompt.md").write_text("stale prompt")

        utility_skills.skill_quit(tmp_path)

        assert not (debrief_dir / "task_prompt.md").exists()

    def test_gate_data_json_deleted(self, tmp_path: Path) -> None:
        _write_state_files(tmp_path)
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir(parents=True, exist_ok=True)
        (debrief_dir / "gate_data.json").write_text("{}")

        utility_skills.skill_quit(tmp_path)

        assert not (debrief_dir / "gate_data.json").exists()

    def test_non_transient_files_preserved(self, tmp_path: Path) -> None:
        _write_state_files(tmp_path)
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir(parents=True, exist_ok=True)
        (debrief_dir / "briefs").mkdir()
        (debrief_dir / "briefs" / "g1.md").write_text("group brief")

        utility_skills.skill_quit(tmp_path)

        assert (debrief_dir / "briefs" / "g1.md").is_file()


class TestQuitDefensiveCycleCheck:
    """BUG-AUDIT-24: belt-and-suspenders warning on mid-cycle quit."""

    def test_no_cycle_warning_when_not_in_cycle(
        self, tmp_path: Path, capsys: pytest.CaptureFixture,
    ) -> None:
        _write_state_files(
            tmp_path, sub_phase="production/slide_review",
            red_green_iteration=0,
        )
        utility_skills.skill_quit(tmp_path)
        msg = capsys.readouterr().err
        assert "active red-green cycle" not in msg

    def test_warning_when_mid_red_green_cycle(
        self, tmp_path: Path, capsys: pytest.CaptureFixture,
    ) -> None:
        _write_state_files(
            tmp_path, sub_phase="production/red_green",
            red_green_iteration=3,
        )
        utility_skills.skill_quit(tmp_path)
        msg = capsys.readouterr().err
        assert "WARNING" in msg
        assert "red-green" in msg.lower() or "red_green" in msg

    def test_warning_does_not_block_quit(
        self, tmp_path: Path,
    ) -> None:
        _write_state_files(
            tmp_path, sub_phase="production/red_green",
            red_green_iteration=2,
        )
        # Should complete without raising, despite the warning
        utility_skills.skill_quit(tmp_path)
        # State files should still be flushed
        assert (tmp_path / "deck_state.json").is_file()
        assert (tmp_path / "debrief_state.json").is_file()
