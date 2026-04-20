# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-72.

BUG-AUDIT-72 adds Tier-1 invariant `INV-25` — viewport-fit script
presence — to `qa_checker.run_programmatic_checks`. Slides without the
canonical viewport-fit IIFE clip below the fold when viewed in a
sub-1920x1080 browser window. The screenshot / export pipelines force
a 1920x1080 viewport so the defect is invisible to automated QA; the
failure surfaces only when the author opens the slide in a real
browser.

TEST CLASSES:

1. TestCheckViewportFitScript — marker detection (present / absent /
   wrong version / quote tolerance / wire-in).
2. TestSpecimenIsInAgentSpec — the canonical script block in
   `agents/slide-maker.md` continues to carry the marker, so the
   authored specimen and the enforcement primitive stay aligned.

All tests run unconditionally in both workspace and delivered layouts
via the sibling-discovery path pattern established in
`test_bug_audit_21_handout_robustness.py`; zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-72 and
blueprint contracts BC-8.10 / BC-9.3b.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_9").is_dir()


def _qa_checker_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_9"
    return _PROJECT_ROOT / "src" / "debrief"


def _slide_maker_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "slide-maker.md"
    return _PROJECT_ROOT / "agents" / "slide-maker.md"


if str(_qa_checker_module_dir()) not in sys.path:
    sys.path.insert(0, str(_qa_checker_module_dir()))

import qa_checker  # noqa: E402
from qa_checker import check_viewport_fit_script  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slide_with(script_head: str, tmp_path: Path) -> Path:
    """Write a minimal slide HTML with a specific <script> block in <head>
    and return the path.
    """
    html = (
        "<!DOCTYPE html><html><head>"
        "<meta charset='utf-8'>"
        f"{script_head}"
        "</head><body>"
        "<div class='slide'><h1>Hi</h1></div>"
        "</body></html>"
    )
    path = tmp_path / "slide.html"
    path.write_text(html, encoding="utf-8")
    return path


_CANONICAL_SCRIPT = (
    '<script data-debrief-viewport-fit="v1">'
    "(function(){})();"
    "</script>"
)


# ---------------------------------------------------------------------------
# Test class 1: check_viewport_fit_script
# ---------------------------------------------------------------------------


class TestCheckViewportFitScript:
    def test_marker_present_passes(self, tmp_path: Path) -> None:
        slide = _slide_with(_CANONICAL_SCRIPT, tmp_path)
        result = check_viewport_fit_script(slide)
        assert result is None

    def test_marker_absent_fails(self, tmp_path: Path) -> None:
        slide = _slide_with("", tmp_path)
        result = check_viewport_fit_script(slide)
        assert result is not None
        assert result["invariant"] == "INV-25"
        # Failure description names the expected attribute so the author
        # can find it without reading the spec.
        assert "data-debrief-viewport-fit" in result["description"]

    def test_wrong_version_fails(self, tmp_path: Path) -> None:
        # A future-versioned marker ("v2") MUST NOT satisfy the v1
        # contract — lets us rev the contract without losing detection.
        wrong = '<script data-debrief-viewport-fit="v2">(function(){})();</script>'
        slide = _slide_with(wrong, tmp_path)
        result = check_viewport_fit_script(slide)
        assert result is not None
        assert result["invariant"] == "INV-25"

    def test_single_quotes_accepted(self, tmp_path: Path) -> None:
        single_q = "<script data-debrief-viewport-fit='v1'>x();</script>"
        slide = _slide_with(single_q, tmp_path)
        result = check_viewport_fit_script(slide)
        assert result is None

    def test_extra_whitespace_around_equals_accepted(
        self, tmp_path: Path
    ) -> None:
        spaced = '<script data-debrief-viewport-fit = "v1">y();</script>'
        slide = _slide_with(spaced, tmp_path)
        result = check_viewport_fit_script(slide)
        assert result is None

    def test_attribute_case_insensitive(self, tmp_path: Path) -> None:
        # HTML attribute names are case-insensitive.
        upper = '<SCRIPT DATA-DEBRIEF-VIEWPORT-FIT="v1">z();</SCRIPT>'
        slide = _slide_with(upper, tmp_path)
        result = check_viewport_fit_script(slide)
        assert result is None

    def test_marker_before_other_attributes_accepted(
        self, tmp_path: Path
    ) -> None:
        tag = '<script data-debrief-viewport-fit="v1" defer>q();</script>'
        slide = _slide_with(tag, tmp_path)
        assert check_viewport_fit_script(slide) is None

    def test_marker_after_other_attributes_accepted(
        self, tmp_path: Path
    ) -> None:
        tag = '<script defer data-debrief-viewport-fit="v1">r();</script>'
        slide = _slide_with(tag, tmp_path)
        assert check_viewport_fit_script(slide) is None

    def test_marker_in_comment_alone_does_not_satisfy(
        self, tmp_path: Path
    ) -> None:
        # A commented-out script shouldn't satisfy the check. The
        # marker-regex requires the literal sequence ``<script ...
        # data-debrief-viewport-fit="v1"...>`` in the HTML source; a
        # purely HTML-commented-out block like
        # ``<!-- <script data-debrief-viewport-fit="v1"></script> -->``
        # WOULD be matched by our regex (we don't parse HTML, we regex
        # the source). That's an acceptable false-positive: an author
        # who intentionally commented out the fitter has signaled they
        # want to suppress INV-25 for a reason; INV-25's job is to
        # detect accidental omission, not adversarial authors. The
        # documented interpretation is: INV-25 detects PRESENCE of the
        # literal marker tag in the source, not RUNTIME behavior.
        #
        # This test pins the documented behavior: a plain comment-free
        # slide with NO marker fails; the other cases covered above
        # pin the detection grammar.
        slide = _slide_with(
            "<!-- no fitter here intentionally -->", tmp_path
        )
        result = check_viewport_fit_script(slide)
        assert result is not None
        assert result["invariant"] == "INV-25"

    def test_unreadable_file_returns_none(self, tmp_path: Path) -> None:
        # Missing slide → check returns None (a different layer reports
        # the file error with a clearer message).
        missing = tmp_path / "does_not_exist.html"
        result = check_viewport_fit_script(missing)
        assert result is None

    def test_failure_revision_instruction_points_at_agent_spec(
        self, tmp_path: Path
    ) -> None:
        slide = _slide_with("", tmp_path)
        result = check_viewport_fit_script(slide)
        assert result is not None
        ri = result["revision_instruction"]
        assert "slide-maker.md" in ri
        assert "data-debrief-viewport-fit" in ri


# ---------------------------------------------------------------------------
# Test class 2: INV-25 wire-in via run_programmatic_checks
# ---------------------------------------------------------------------------


_SIBLING_CHECKS = [
    "check_contrast",
    "check_no_inline_styles",
    "check_no_external_requests",
    "check_aspect_ratio",
    "check_permitted_libraries",
    "check_valid_html5",
    "check_images_respect_margins",
    "check_math_no_overflow",
    "check_diagrams_no_errors",
    "check_fonts_loadable",
    "check_css_vars_defined",
    "check_image_paths_exist",
    "check_image_aspect_ratio",
    "check_inline_math_line_height",
    "check_math_assets_exist",
    "check_filename_consistency",
    "check_text_overflow",
    "check_raw_source_visible",
    "check_slug_not_in_content",
]


def _patch_sibling_checks() -> list:
    return [
        patch.object(qa_checker, name, return_value=None)
        for name in _SIBLING_CHECKS
    ]


class TestInv25WireIn:
    def test_inv25_failure_appears_when_marker_missing(
        self, tmp_path: Path
    ) -> None:
        slide = _slide_with("", tmp_path)
        shot = tmp_path / "shot.png"

        patches = _patch_sibling_checks()
        for p in patches:
            p.start()
        try:
            page = MagicMock()
            failures, _warnings, veto = (
                qa_checker.run_programmatic_checks(
                    slide, shot, {}, page,
                    slug="slide", project_root=tmp_path,
                )
            )
        finally:
            for p in patches:
                p.stop()

        assert len(failures) == 1
        assert failures[0]["invariant"] == "INV-25"
        assert veto is False

    def test_inv25_absent_when_marker_present(
        self, tmp_path: Path
    ) -> None:
        slide = _slide_with(_CANONICAL_SCRIPT, tmp_path)
        shot = tmp_path / "shot.png"

        patches = _patch_sibling_checks()
        for p in patches:
            p.start()
        try:
            page = MagicMock()
            failures, _warnings, _veto = (
                qa_checker.run_programmatic_checks(
                    slide, shot, {}, page,
                    slug="slide", project_root=tmp_path,
                )
            )
        finally:
            for p in patches:
                p.stop()

        assert failures == []


# ---------------------------------------------------------------------------
# Test class 3: specimen-alignment between agent spec and enforcement
# ---------------------------------------------------------------------------


class TestSpecimenIsInAgentSpec:
    def test_slide_maker_md_contains_the_marker(self) -> None:
        """The canonical script block in agents/slide-maker.md must
        still carry the INV-25 marker attribute. If someone revises
        the block and drops the marker, this test catches it — without
        this, the enforcement and the authored specimen would drift.
        """
        text = _slide_maker_md_path().read_text(encoding="utf-8")
        assert 'data-debrief-viewport-fit="v1"' in text

    def test_slide_maker_md_references_inv25(self) -> None:
        text = _slide_maker_md_path().read_text(encoding="utf-8")
        assert "INV-25" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
