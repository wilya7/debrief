# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression test for BUG-AUDIT-36: export creates PresentationRecord on first run."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_10").is_dir()


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_10" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

from export import main_export  # noqa: E402

_TS = "2026-04-16T12:00:00Z"


def _setup_project_no_presentations(root: Path) -> None:
    slides = [
        {"slug": "intro", "title": "Intro", "status": "approved",
         "backup": False, "content_summary": "S", "visual_approach": "D",
         "design_choices": "M", "forks_not_taken": None,
         "user_recommendations": None, "qa_passed": True,
         "accepted_violations": [], "last_modified": _TS,
         "group_id": "g1", "user_assets": [], "has_math": False},
    ]
    state = {
        "project_name": "test_project",
        "created_at": _TS,
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": slides,
        "presentations": [],  # EMPTY — first export
    }
    (root / "deck_state.json").write_text(json.dumps(state), encoding="utf-8")

    style_config = {
        "colors": {"primary": "#000", "background": "#fff", "text": "#111",
                    "accent": "#06c", "secondary_bg": "#f5f5f5", "border": "#ccc"},
        "typography": {"heading_font": "sans-serif", "body_font": "sans-serif",
                        "base_size": "16px", "heading_weight": "700",
                        "body_weight": "400", "line_height": "1.5"},
        "spacing": {"slide_padding": "40px", "element_gap": "20px",
                     "section_gap": "32px"},
        "layout": {"slide_width": 1920, "slide_height": 1080,
                    "max_content_width": "1600px", "grid_columns": 12},
        "data_viz": {"chart_font": "sans-serif", "axis_color": "#333",
                      "grid_color": "#eee"},
        "constraints": {}, "provenance": {},
    }
    (root / "style_config.json").write_text(json.dumps(style_config), encoding="utf-8")

    (root / "slides").mkdir()
    (root / "slides" / "intro.html").write_text("<html><body>Intro</body></html>")
    (root / "assets").mkdir()
    (root / "assets" / "style.css").write_text("body{}")


class TestExportFirstRunCreatesPresentationRecord:

    def test_first_export_creates_record_and_succeeds(
        self, tmp_path: Path,
    ) -> None:
        _setup_project_no_presentations(tmp_path)

        mock_fitz_doc = MagicMock()
        mock_fitz_doc.__enter__ = MagicMock(return_value=mock_fitz_doc)
        mock_fitz_doc.__exit__ = MagicMock(return_value=False)
        mock_merged = MagicMock()
        mock_merged.save.side_effect = lambda path: Path(path).write_bytes(
            b"%PDF-1.4 mock"
        )
        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = lambda **kw: (
            mock_fitz_doc if "stream" in kw else mock_merged
        )

        mock_page = MagicMock()
        mock_page.pdf.return_value = b"%PDF-1.4 page"
        mock_page.goto = MagicMock()
        mock_page.close = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.new_page.return_value = mock_page
        mock_ctx.close = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_ctx
        mock_browser.close = MagicMock()
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_sync_ctx = MagicMock()
        mock_sync_ctx.__enter__ = MagicMock(return_value=mock_pw)
        mock_sync_ctx.__exit__ = MagicMock(return_value=False)

        with (
            patch("subprocess.run", return_value=MagicMock(returncode=0, stderr="")),
            patch("importlib.util.find_spec", return_value=MagicMock()),
            patch.dict("sys.modules", {
                "playwright": MagicMock(),
                "playwright.sync_api": MagicMock(
                    sync_playwright=MagicMock(return_value=mock_sync_ctx)
                ),
                "fitz": mock_fitz,
            }),
        ):
            main_export(tmp_path)

        # Verify presentation record was created
        state = json.loads((tmp_path / "deck_state.json").read_text())
        assert len(state["presentations"]) == 1
        assert state["presentations"][0]["folder"].startswith("20")

    def test_first_export_folder_contains_project_name(
        self, tmp_path: Path,
    ) -> None:
        """Verify the auto-created folder name includes project_name."""
        _setup_project_no_presentations(tmp_path)

        mock_fitz_doc = MagicMock()
        mock_fitz_doc.__enter__ = MagicMock(return_value=mock_fitz_doc)
        mock_fitz_doc.__exit__ = MagicMock(return_value=False)
        mock_merged = MagicMock()
        mock_merged.save.side_effect = lambda path: Path(path).write_bytes(
            b"%PDF-1.4 mock"
        )
        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = lambda **kw: (
            mock_fitz_doc if "stream" in kw else mock_merged
        )

        mock_page = MagicMock()
        mock_page.pdf.return_value = b"%PDF-1.4 page"
        mock_page.goto = MagicMock()
        mock_page.close = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.new_page.return_value = mock_page
        mock_ctx.close = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_ctx
        mock_browser.close = MagicMock()
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_sync_ctx = MagicMock()
        mock_sync_ctx.__enter__ = MagicMock(return_value=mock_pw)
        mock_sync_ctx.__exit__ = MagicMock(return_value=False)

        with (
            patch("subprocess.run", return_value=MagicMock(returncode=0, stderr="")),
            patch("importlib.util.find_spec", return_value=MagicMock()),
            patch.dict("sys.modules", {
                "playwright": MagicMock(),
                "playwright.sync_api": MagicMock(
                    sync_playwright=MagicMock(return_value=mock_sync_ctx)
                ),
                "fitz": mock_fitz,
            }),
        ):
            main_export(tmp_path)

        state = json.loads((tmp_path / "deck_state.json").read_text())
        assert "test_project" in state["presentations"][0]["folder"]
