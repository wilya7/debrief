# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-37: 7 veto rules (REQ-QA-2).

Tests the 3 programmatic veto checks added to qa_checker.py:
VETO-01 (text overflow), VETO-04 (raw source visible),
VETO-06 (slug in content).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_9").is_dir()


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_9" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

from qa_checker import (  # noqa: E402
    check_raw_source_visible,
    check_slug_not_in_content,
    check_text_overflow,
)


def _mock_page(inner_text: str = "", overflow_element: str = None) -> MagicMock:
    page = MagicMock()
    page.inner_text.return_value = inner_text

    if overflow_element:
        page.evaluate.return_value = overflow_element
    else:
        page.evaluate.return_value = None

    return page


class TestVeto01TextOverflow:

    def test_no_overflow_returns_none(self) -> None:
        page = _mock_page(overflow_element=None)
        assert check_text_overflow(page) is None

    def test_overflow_detected_returns_veto(self) -> None:
        page = _mock_page(overflow_element="DIV.content-area")
        result = check_text_overflow(page)
        assert result is not None
        assert result["invariant"] == "VETO-01"


class TestVeto04RawSourceVisible:

    def test_clean_text_returns_none(self) -> None:
        page = _mock_page(inner_text="This is a normal slide about methodology")
        assert check_raw_source_visible(page) is None

    def test_html_tags_in_text_returns_veto(self) -> None:
        page = _mock_page(inner_text="Results: <div class='chart'>data</div>")
        result = check_raw_source_visible(page)
        assert result is not None
        assert result["invariant"] == "VETO-04"

    def test_latex_in_text_returns_veto(self) -> None:
        page = _mock_page(inner_text="The equation is \\begin{equation} x=1")
        result = check_raw_source_visible(page)
        assert result is not None
        assert result["invariant"] == "VETO-04"

    def test_css_in_text_returns_veto(self) -> None:
        page = _mock_page(inner_text='The box has style="color:red" applied')
        result = check_raw_source_visible(page)
        assert result is not None
        assert result["invariant"] == "VETO-04"


class TestVeto06SlugInContent:

    def test_no_slug_in_text_returns_none(self) -> None:
        page = _mock_page(inner_text="Introduction to our research methods")
        assert check_slug_not_in_content(page, "intro_methods_01") is None

    def test_slug_in_text_returns_veto(self) -> None:
        page = _mock_page(inner_text="Slide: intro_methods_01 - Introduction")
        result = check_slug_not_in_content(page, "intro_methods_01")
        assert result is not None
        assert result["invariant"] == "VETO-06"

    def test_empty_slug_returns_none(self) -> None:
        page = _mock_page(inner_text="anything")
        assert check_slug_not_in_content(page, "") is None


class TestRunProgrammaticChecksVetoFlag:
    """Verify that run_programmatic_checks returns veto=True when any
    veto check fires, and veto=False otherwise.
    """

    def test_veto_false_when_no_violations(self, tmp_path: Path) -> None:
        from qa_checker import run_programmatic_checks

        slide = tmp_path / "test.html"
        slide.write_text("<html><body><h1>Title</h1></body></html>")
        screenshot = tmp_path / "test.png"

        page = MagicMock()
        page.evaluate.return_value = None
        page.inner_text.return_value = "Title"

        _, _, veto = run_programmatic_checks(
            slide, screenshot, {"layout": {}}, page, slug="intro"
        )
        assert veto is False

    def test_veto_true_when_slug_in_content(self, tmp_path: Path) -> None:
        from qa_checker import run_programmatic_checks

        slide = tmp_path / "test.html"
        slide.write_text("<html><body><h1>intro</h1></body></html>")
        screenshot = tmp_path / "test.png"

        page = MagicMock()
        page.evaluate.return_value = None
        page.inner_text.return_value = "intro"

        _, _, veto = run_programmatic_checks(
            slide, screenshot, {"layout": {}}, page, slug="intro"
        )
        assert veto is True
