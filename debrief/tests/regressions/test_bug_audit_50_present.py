# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-50: /debrief:present command."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent

for _dir in (
    _PROJECT_ROOT / "src" / ("unit_11" if (_PROJECT_ROOT / "src" / "unit_11").is_dir() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if (_PROJECT_ROOT / "src" / "unit_2").is_dir() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402

_TS = "2026-04-17T12:00:00Z"


def _setup_present_project(root: Path, slugs: list[str], builds: dict = None) -> None:
    state = {
        "project_name": "test",
        "created_at": _TS,
        "archetype": "conference_talk",
        "style_locked": True,
        "closing_slide": None,
        "slides": [
            {"slug": s, "title": f"Title {s}", "status": "approved",
             "backup": False, "content_summary": "S",
             "visual_approach": "D", "design_choices": "M",
             "forks_not_taken": None, "user_recommendations": None,
             "qa_passed": True, "accepted_violations": [],
             "last_modified": _TS, "group_id": "g1",
             "user_assets": [], "has_math": False}
            for s in slugs
        ],
        "presentations": [],
    }
    (root / "deck_state.json").write_text(json.dumps(state))

    slides_dir = root / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    for s in slugs:
        (slides_dir / f"{s}.html").write_text(
            f"<html><body><div class='slide'><h1>{s}</h1></div></body></html>"
        )

    if builds:
        for slug, count in builds.items():
            for i in range(1, count + 1):
                (slides_dir / f"{slug}_build_{i}.html").write_text(
                    f"<html><body><div class='slide'><h1>{slug} build {i}</h1></div></body></html>"
                )


class TestPresentGeneratesHtml:

    def test_creates_presentation_html(self, tmp_path: Path) -> None:
        _setup_present_project(tmp_path, ["intro", "methods"])
        with patch("webbrowser.open"):
            utility_skills.main_present(tmp_path)
        assert (tmp_path / "output" / "presentation.html").is_file()

    def test_html_contains_all_slides(self, tmp_path: Path) -> None:
        _setup_present_project(tmp_path, ["intro", "methods", "results"])
        with patch("webbrowser.open"):
            utility_skills.main_present(tmp_path)
        html = (tmp_path / "output" / "presentation.html").read_text()
        assert "intro" in html
        assert "methods" in html
        assert "results" in html

    def test_html_has_keyboard_navigation(self, tmp_path: Path) -> None:
        _setup_present_project(tmp_path, ["intro"])
        with patch("webbrowser.open"):
            utility_skills.main_present(tmp_path)
        html = (tmp_path / "output" / "presentation.html").read_text()
        assert "ArrowRight" in html
        assert "ArrowLeft" in html
        assert "fullscreen" in html.lower()

    def test_html_has_slide_counter(self, tmp_path: Path) -> None:
        _setup_present_project(tmp_path, ["intro", "methods"])
        with patch("webbrowser.open"):
            utility_skills.main_present(tmp_path)
        html = (tmp_path / "output" / "presentation.html").read_text()
        assert "slide-counter" in html


class TestPresentProgressiveDisclosure:

    def test_builds_included_before_final(self, tmp_path: Path) -> None:
        _setup_present_project(
            tmp_path, ["results"],
            builds={"results": 2},
        )
        with patch("webbrowser.open"):
            utility_skills.main_present(tmp_path)
        html = (tmp_path / "output" / "presentation.html").read_text()
        # Should contain build 1, build 2, and final
        assert "results build 1" in html
        assert "results build 2" in html
        assert "3 / 3" in html or 'data-index="2"' in html


class TestPresentPreconditions:

    def test_no_project_exits_2(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc_info:
            utility_skills.main_present(tmp_path)
        assert exc_info.value.code == 2

    def test_no_approved_slides_exits_2(self, tmp_path: Path) -> None:
        state = {
            "project_name": "test", "created_at": _TS,
            "archetype": "conference_talk", "style_locked": True,
            "closing_slide": None, "slides": [], "presentations": [],
        }
        (tmp_path / "deck_state.json").write_text(json.dumps(state))
        with pytest.raises(SystemExit) as exc_info:
            utility_skills.main_present(tmp_path)
        assert exc_info.value.code == 2
