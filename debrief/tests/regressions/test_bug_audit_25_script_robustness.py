# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-25.

BUG-AUDIT-25 applies filesystem-derived versioning and an
approved-slide precondition to ``/debrief:script``, consistent
with the handout (BUG-AUDIT-21) and export (BUG-AUDIT-23) fixes.
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


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_11" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402

_TS = "2026-04-16T12:00:00Z"
_FOLDER = "2026_04_16_test_deck"


def _slide_dict(slug: str, **kw: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "slug": slug, "title": f"Title of {slug}", "status": "approved",
        "backup": False, "content_summary": f"Summary for {slug}",
        "visual_approach": "Diagram", "design_choices": "Minimal",
        "forks_not_taken": None, "user_recommendations": None,
        "qa_passed": True, "accepted_violations": [],
        "last_modified": _TS, "group_id": "g1",
        "user_assets": [], "has_math": False,
    }
    defaults.update(kw)
    return defaults


def _setup_script_project(
    root: Path,
    *,
    slides: Optional[list[dict[str, Any]]] = None,
) -> None:
    state = {
        "project_name": "test",
        "created_at": _TS,
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": slides if slides is not None else [_slide_dict("intro")],
        "presentations": [{
            "folder": _FOLDER,
            "created_at": _TS,
            "slide_manifest": [],
            "export_count": 0,
            "script_count": 0,
            "handout_count": 0,
            "separator_position": None,
            "separator_content": None,
        }],
    }
    (root / "deck_state.json").write_text(json.dumps(state), encoding="utf-8")


class TestScriptVersionDerivedFromFilesystem:
    """BUG-AUDIT-25: version is filesystem-derived, no state mutation."""

    def test_first_script_is_v001(self, tmp_path: Path) -> None:
        _setup_script_project(tmp_path)
        utility_skills.main_script_generator(tmp_path)
        expected = tmp_path / "output" / _FOLDER / "script_v001.md"
        assert expected.is_file()

    def test_preexisting_v002_yields_v003(self, tmp_path: Path) -> None:
        _setup_script_project(tmp_path)
        out_dir = tmp_path / "output" / _FOLDER
        out_dir.mkdir(parents=True)
        (out_dir / "script_v002.md").write_text("old script")

        utility_skills.main_script_generator(tmp_path)
        assert (out_dir / "script_v003.md").is_file()

    def test_deck_state_not_mutated(self, tmp_path: Path) -> None:
        _setup_script_project(tmp_path)
        before = (tmp_path / "deck_state.json").read_bytes()

        utility_skills.main_script_generator(tmp_path)

        after = (tmp_path / "deck_state.json").read_bytes()
        assert before == after


class TestScriptApprovedSlidePrecondition:
    """BUG-AUDIT-25: exit 2 if no approved non-backup slides."""

    def test_no_approved_slides_exits_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture,
    ) -> None:
        _setup_script_project(
            tmp_path,
            slides=[_slide_dict("draft_1", status="draft")],
        )
        with pytest.raises(SystemExit) as exc_info:
            utility_skills.main_script_generator(tmp_path)
        assert exc_info.value.code == 2
        msg = capsys.readouterr().err.lower()
        assert "approved" in msg

    def test_only_backup_approved_exits_2(
        self, tmp_path: Path,
    ) -> None:
        _setup_script_project(
            tmp_path,
            slides=[_slide_dict("backup_1", backup=True)],
        )
        with pytest.raises(SystemExit) as exc_info:
            utility_skills.main_script_generator(tmp_path)
        assert exc_info.value.code == 2

    def test_backup_slides_appear_under_backup_section(
        self, tmp_path: Path,
    ) -> None:
        """BUG-AUDIT-65 / REQ-SCRIPT-BACKUP-1 / BC-11.6b: script now
        INCLUDES approved backup slides, under a '## Backup Slides'
        section heading. Prior to BUG-AUDIT-65 this test asserted
        exclusion — that behavior was wrong per the Round 5 UX review
        (presenters need Q&A notes)."""
        _setup_script_project(
            tmp_path,
            slides=[
                _slide_dict("live_1"),
                _slide_dict("backup_old", backup=True),
            ],
        )
        utility_skills.main_script_generator(tmp_path)
        script = (tmp_path / "output" / _FOLDER / "script_v001.md").read_text()
        assert "live_1" in script
        # BUG-AUDIT-65: backup slide now INCLUDED, under its own section.
        assert "backup_old" in script
        assert "## Backup Slides" in script
        # Backup slide appears AFTER the main slide block.
        assert script.index("backup_old") > script.index("live_1")
