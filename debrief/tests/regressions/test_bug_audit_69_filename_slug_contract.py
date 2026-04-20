# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-69.

BUG-AUDIT-69 adds Tier-1 invariant `INV-24` — filename/slug
consistency — to `qa_checker.run_programmatic_checks`. The invariant
enforces two sub-rules (BC-9.3a):

  * Rule A (always active): ``slide_path.stem == screenshot_path.stem``.
  * Rule B (state-aware): when ``deck_state.json`` is readable AND its
    ``slides`` array is non-empty, ``slide_path.stem`` MUST equal
    ``SlideRecord.slug`` for some recorded slide. Skipped silently
    when state is absent or empty (legitimate first-author case).

The enforcement catches the two concrete failures that motivated the
bug: (1) slide-maker writing ``slides/NN_<slug>.html`` with the
numeric prefix, (2) screenshots inheriting that prefix and then
drifting from the slide filename after a rename pass.

TEST CLASSES:

1. TestFilenameRuleA — stem match/mismatch, both paths always.
2. TestFilenameRuleB — deck_state awareness and skip semantics.
3. TestFailureSchema — failure-entry grammar and revision_instruction.
4. TestWireIntoProgrammaticChecks — the check is actually run as part
   of ``run_programmatic_checks`` and appears in the returned failures.

All tests run unconditionally in both workspace and delivered layouts
via the sibling-discovery path pattern established in
`test_bug_audit_21_handout_robustness.py`; zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-69 and
blueprint contract BC-9.3a.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution, mirroring BUG-AUDIT-21's pattern.
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


def _debrief_state_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_2"
    return _PROJECT_ROOT / "src" / "debrief"


for _dir in (_debrief_state_module_dir(), _qa_checker_module_dir()):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import qa_checker  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal deck_state.json helper — only the fields INV-24 reads.
# ---------------------------------------------------------------------------


def _write_deck_state_with_slugs(
    project_root: Path, slugs: list[str]
) -> None:
    slides = [
        {
            "slug": s,
            "title": f"Title of {s}",
            "status": "approved",
            "backup": False,
            "content_summary": None,
            "visual_approach": None,
            "design_choices": None,
            "forks_not_taken": None,
            "user_recommendations": None,
            "qa_passed": True,
            "accepted_violations": [],
            "last_modified": "",
            "group_id": None,
            "user_assets": [],
            "has_math": False,
        }
        for s in slugs
    ]
    data = {
        "project_name": "bug_audit_69_test",
        "created_at": "",
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": slides,
        "presentations": [],
    }
    (project_root / "deck_state.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Test class 1: Rule A — slide/screenshot stem consistency (always-on)
# ---------------------------------------------------------------------------


class TestFilenameRuleA:
    def test_matching_stems_pass(self, tmp_path: Path) -> None:
        slide = tmp_path / "slides" / "intro.html"
        shot = tmp_path / "output" / "screenshots" / "intro.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is None

    def test_mismatched_stems_fail(self, tmp_path: Path) -> None:
        slide = tmp_path / "slides" / "01_intro.html"
        shot = tmp_path / "output" / "screenshots" / "intro.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is not None
        assert result["invariant"] == "INV-24"

    def test_rule_a_runs_even_when_deck_state_missing(
        self, tmp_path: Path
    ) -> None:
        # No deck_state.json anywhere — Rule B is skipped, but Rule A
        # must still fire on stem mismatch.
        slide = tmp_path / "slides" / "first.html"
        shot = tmp_path / "output" / "screenshots" / "second.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is not None
        assert result["invariant"] == "INV-24"

    def test_rule_a_reports_both_stems(self, tmp_path: Path) -> None:
        slide = tmp_path / "slides" / "alpha.html"
        shot = tmp_path / "output" / "screenshots" / "beta.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is not None
        assert "'alpha'" in result["description"]
        assert "'beta'" in result["description"]


# ---------------------------------------------------------------------------
# Test class 2: Rule B — deck_state.json awareness + skip semantics
# ---------------------------------------------------------------------------


class TestFilenameRuleB:
    def test_slug_in_state_passes(self, tmp_path: Path) -> None:
        _write_deck_state_with_slugs(tmp_path, ["intro", "body", "closing"])
        slide = tmp_path / "slides" / "intro.html"
        shot = tmp_path / "output" / "screenshots" / "intro.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is None

    def test_nn_prefix_not_in_state_fails(self, tmp_path: Path) -> None:
        # The canonical regression case: slide-maker wrote
        # "01_intro.html" and screenshot "01_intro.png". Rule A passes
        # (stems match). Rule B fails because "01_intro" is not in
        # {intro, body, closing}.
        _write_deck_state_with_slugs(tmp_path, ["intro", "body", "closing"])
        slide = tmp_path / "slides" / "01_intro.html"
        shot = tmp_path / "output" / "screenshots" / "01_intro.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is not None
        assert result["invariant"] == "INV-24"
        # Description previews at least one known slug.
        assert "intro" in result["description"]

    def test_missing_state_skips_rule_b(self, tmp_path: Path) -> None:
        # Rule A passes (matching stems), no deck_state.json → Rule B
        # is skipped, overall result is None (pass).
        slide = tmp_path / "slides" / "foo.html"
        shot = tmp_path / "output" / "screenshots" / "foo.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is None

    def test_empty_slides_list_skips_rule_b(
        self, tmp_path: Path
    ) -> None:
        _write_deck_state_with_slugs(tmp_path, [])
        slide = tmp_path / "slides" / "foo.html"
        shot = tmp_path / "output" / "screenshots" / "foo.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is None

    def test_malformed_state_file_skips_rule_b(
        self, tmp_path: Path
    ) -> None:
        # Best-effort parse: malformed deck_state.json must not raise.
        (tmp_path / "deck_state.json").write_text(
            "this is not json", encoding="utf-8"
        )
        slide = tmp_path / "slides" / "foo.html"
        shot = tmp_path / "output" / "screenshots" / "foo.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is None

    def test_state_without_slides_field_skips_rule_b(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "deck_state.json").write_text(
            json.dumps({"project_name": "x"}), encoding="utf-8"
        )
        slide = tmp_path / "slides" / "foo.html"
        shot = tmp_path / "output" / "screenshots" / "foo.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is None

    def test_state_with_only_empty_slug_entries_skips_rule_b(
        self, tmp_path: Path
    ) -> None:
        # Slides array exists but every entry has an empty/missing slug.
        data = {
            "project_name": "x",
            "slides": [{"slug": ""}, {"title": "no-slug"}],
            "presentations": [],
        }
        (tmp_path / "deck_state.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        slide = tmp_path / "slides" / "foo.html"
        shot = tmp_path / "output" / "screenshots" / "foo.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# Test class 3: Failure schema + revision_instruction grammar
# ---------------------------------------------------------------------------


class TestFailureSchema:
    def test_rule_a_failure_schema(self, tmp_path: Path) -> None:
        slide = tmp_path / "slides" / "a.html"
        shot = tmp_path / "output" / "screenshots" / "b.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is not None
        assert set(result.keys()) >= {
            "invariant",
            "description",
            "revision_instruction",
        }
        assert result["invariant"] == "INV-24"
        # Revision instruction names the canonical paths.
        assert "slides/<slug>.html" in result["revision_instruction"]
        assert (
            "output/screenshots/<slug>.png"
            in result["revision_instruction"]
        )

    def test_rule_b_failure_schema(self, tmp_path: Path) -> None:
        _write_deck_state_with_slugs(tmp_path, ["intro"])
        slide = tmp_path / "slides" / "01_intro.html"
        shot = tmp_path / "output" / "screenshots" / "01_intro.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is not None
        assert result["invariant"] == "INV-24"
        assert "slides/<slug>.html" in result["revision_instruction"]

    def test_failure_is_not_veto_flagged(self, tmp_path: Path) -> None:
        # The QAFailure dict itself carries no veto field — veto is
        # signaled by run_programmatic_checks setting the third tuple
        # element. INV-24 must NOT be VETO-flagged at the boundary.
        slide = tmp_path / "slides" / "a.html"
        shot = tmp_path / "output" / "screenshots" / "b.png"
        result = qa_checker.check_filename_consistency(slide, shot, tmp_path)
        assert result is not None
        assert "veto" not in result


# ---------------------------------------------------------------------------
# Test class 4: wire-in via run_programmatic_checks
# ---------------------------------------------------------------------------


def _write_trivial_valid_slide(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "<!DOCTYPE html><html><head><title>t</title></head>"
        "<body><div class='slide'>hi</div></body></html>",
        encoding="utf-8",
    )


# Every sibling check in run_programmatic_checks that INV-24 tests
# must not depend on. We patch each to return None so INV-24 is the
# only failure source we're measuring.
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
    # INV-25 / BUG-AUDIT-72: added to the checks_run list after
    # BUG-AUDIT-69. Patch it out here so this test measures INV-24 in
    # isolation.
    "check_viewport_fit_script",
    "check_text_overflow",
    "check_raw_source_visible",
    "check_slug_not_in_content",
]


def _patch_sibling_checks() -> list:
    """Return a list of patch() context managers that stub every
    sibling check to None so INV-24 is the only observable signal."""
    return [
        patch.object(qa_checker, name, return_value=None)
        for name in _SIBLING_CHECKS
    ]


class TestWireIntoProgrammaticChecks:
    def test_inv24_failure_appears_in_programmatic_checks_output(
        self, tmp_path: Path
    ) -> None:
        slide = tmp_path / "slides" / "01_intro.html"
        _write_trivial_valid_slide(slide)
        shot = tmp_path / "output" / "screenshots" / "01_intro.png"
        _write_deck_state_with_slugs(tmp_path, ["intro"])

        patches = _patch_sibling_checks()
        for p in patches:
            p.start()
        try:
            page = MagicMock()
            failures, warnings, veto = qa_checker.run_programmatic_checks(
                slide, shot, {}, page, slug="01_intro", project_root=tmp_path
            )
        finally:
            for p in patches:
                p.stop()

        assert failures, "expected INV-24 failure, got none"
        assert len(failures) == 1
        assert failures[0]["invariant"] == "INV-24"
        assert veto is False, "INV-24 must NOT flip the veto bit"

    def test_matching_canonical_filenames_produce_no_inv24(
        self, tmp_path: Path
    ) -> None:
        slide = tmp_path / "slides" / "intro.html"
        _write_trivial_valid_slide(slide)
        shot = tmp_path / "output" / "screenshots" / "intro.png"
        _write_deck_state_with_slugs(tmp_path, ["intro"])

        patches = _patch_sibling_checks()
        for p in patches:
            p.start()
        try:
            page = MagicMock()
            failures, _warnings, _veto = qa_checker.run_programmatic_checks(
                slide, shot, {}, page, slug="intro", project_root=tmp_path
            )
        finally:
            for p in patches:
                p.stop()

        assert failures == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
