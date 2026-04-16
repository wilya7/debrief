# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-32: remaining inline preconditions.

Tests view's project precondition + no-match message, and save's
confirmation output per REQ-SAVE-3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_11" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402

_TS = "2026-04-16T12:00:00Z"


def _write_state(root: Path, **kw: Any) -> None:
    deck = {
        "project_name": "test", "created_at": _TS,
        "archetype": "lab_meeting", "style_locked": True,
        "closing_slide": None, "slides": [], "presentations": [],
    }
    (root / "deck_state.json").write_text(json.dumps(deck))
    debrief = {
        "phase": kw.get("phase", "production"),
        "sub_phase": kw.get("sub_phase", "production/slide_review"),
        "active_agent": "consultant", "archetype": "lab_meeting",
        "current_group_id": None, "current_slide_slug": None,
        "pending_gate": None, "last_gate_response": None,
        "red_green_iteration": 0, "red_green_started_at": None,
        "group_slide_index": 0, "group_slide_count": 1,
        "backup_mode": False, "completed_groups": [],
        "pre_view_state": None, "view_deferred": False,
        "closing_slide_pending": False, "group_revise_slug": None,
        "style_import_mode": None, "reference_provided": False,
        "reference_modality": None, "papers_provided": False,
        "selected_figures": None, "session_started_at": _TS,
        "state_hash": "abc123",
    }
    (root / "debrief_state.json").write_text(json.dumps(debrief))


class TestViewProjectPrecondition:
    def test_missing_deck_state_exits_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture,
    ) -> None:
        with pytest.raises(SystemExit) as exc_info:
            utility_skills.main_view("all", tmp_path)
        assert exc_info.value.code == 2
        msg = capsys.readouterr().err.lower()
        assert "deck_state.json" in msg or "no project" in msg


class TestViewNoMatchMessage:
    def test_no_match_prints_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture,
    ) -> None:
        _write_state(tmp_path)
        with patch("webbrowser.open"):
            with pytest.raises(SystemExit) as exc_info:
                utility_skills.main_view("nonexistent_slug", tmp_path)
        assert exc_info.value.code == 1
        msg = capsys.readouterr().err.lower()
        assert "no slides match" in msg


class TestSaveConfirmationOutput:
    def test_save_prints_confirmation(
        self, tmp_path: Path, capsys: pytest.CaptureFixture,
    ) -> None:
        _write_state(tmp_path)
        (tmp_path / "ledger.jsonl").write_text("")
        utility_skills.skill_save("my_snap", tmp_path)
        msg = capsys.readouterr().err
        assert "snapshot saved" in msg.lower()
        assert "my_snap" in msg
        assert "deck_state.json" in msg

    def test_save_empty_project_warns(
        self, tmp_path: Path, capsys: pytest.CaptureFixture,
    ) -> None:
        utility_skills.skill_save("empty_snap", tmp_path)
        msg = capsys.readouterr().err
        assert "empty" in msg.lower() or "no state" in msg.lower()
