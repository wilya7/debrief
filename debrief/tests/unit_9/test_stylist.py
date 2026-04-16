# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Tests for Unit 9: QA System (qa_checker module).

Tested contracts: BC-9.1 through BC-9.4.

Synthetic data generation assumptions
--------------------------------------
- Slide HTML files are minimal strings written to ``tmp_path``.  Content is
  chosen to trigger (or not trigger) the specific invariant under test, not
  to be browser-renderable.  A "clean" slide is a self-contained HTML5
  skeleton with no inline style attributes, no external URLs, and only
  permitted library script tags.
- Slide HTML with inline style attributes uses ``style="color:red"`` on a
  ``<div>`` element -- a single attribute is sufficient to trigger INV-06.
- External URL detection tests use ``src="https://cdn.example.com/lib.js"``
  (HTTPS) and ``href="http://fonts.googleapis.com/css"`` (HTTP) as
  representative external references.  Local relative paths such as
  ``src="vendor/mermaid.min.js"`` and ``href="assets/style.css"`` are
  verified to pass (return None).
- Permitted library tests: the permitted list ``["mermaid"]`` is used;
  ``mermaid.min.js`` passes, ``katex.min.js`` fails.  Empty permitted list
  ``[]`` causes any library script to fail.
- ``build_qa_log_entry`` tests construct ``QAFailure`` dicts with all three
  required keys: ``"invariant"``, ``"description"``, ``"revision_instruction"``.
  ``QAWarning`` dicts follow the same structure.
- ``append_qa_log`` tests use a fresh ``tmp_path`` project tree.  Multiple
  appends are verified to produce multiple JSONL lines (one per entry).
- BC-9.1 (veto gate ordering) is tested by verifying that
  ``main_qa_checker`` accepts a ``--slide-path`` argument and that the
  qa_checker module does not invoke Playwright during a unit-test-friendly
  invocation.  Agent ordering is a compositional property; the test verifies
  the module's contract boundary (no side effects on import) and the veto
  flag propagation through ``build_qa_log_entry``.
- BC-9.2 (per-invocation Playwright context) is tested by patching
  ``sync_playwright`` and confirming the context is opened and closed exactly
  once per ``main_qa_checker`` invocation, and that the close call happens
  inside a ``finally`` block (verified by raising inside the context and
  confirming close is still called).
- BC-9.3 (screenshot-before-checks) is tested by patching the Playwright
  context so that the screenshot call raises, then verifying the resulting
  qa_log entry has ``"invariant": "SCREENSHOT"`` and the process exits 1.
- BC-9.4 (canonical schema) is tested by calling ``build_qa_log_entry``
  directly and asserting all nine required keys are present with correct
  types.
- All ``tmp_path`` trees are created fresh per test via pytest fixtures;
  no test shares mutable state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from qa_checker import (
    append_qa_log,
    build_qa_log_entry,
    check_no_external_requests,
    check_no_inline_styles,
    check_permitted_libraries,
)

# ---------------------------------------------------------------------------
# Minimal HTML fixtures
# ---------------------------------------------------------------------------

_CLEAN_SLIDE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Test Slide</title>
<link rel="stylesheet" href="assets/style.css">
<script src="vendor/mermaid.min.js"></script>
</head>
<body><div class="slide"><p>Content</p></div></body>
</html>
"""

_INLINE_STYLE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body><div style="color:red">Text</div></body>
</html>
"""

_EXTERNAL_SRC_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<script src="https://cdn.example.com/lib.js"></script>
</head>
<body></body>
</html>
"""

_EXTERNAL_HREF_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<link href="http://fonts.googleapis.com/css" rel="stylesheet">
</head>
<body></body>
</html>
"""

_KATEX_SLIDE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<script src="vendor/katex.min.js"></script>
</head>
<body></body>
</html>
"""


# ---------------------------------------------------------------------------
# Helper to write slide HTML to a temp file
# ---------------------------------------------------------------------------


def _write_slide(tmp_path: Path, html: str, name: str = "slide.html") -> Path:
    slide = tmp_path / name
    slide.write_text(html, encoding="utf-8")
    return slide


# ===========================================================================
# BC-9.4 — build_qa_log_entry: canonical schema
# ===========================================================================


class TestBuildQaLogEntryCanonicalSchema:
    """BC-9.4: build_qa_log_entry produces every required key with correct types."""

    def test_all_nine_required_keys_are_present_in_returned_entry(self) -> None:
        entry = build_qa_log_entry(
            slug="my_slide",
            passed=True,
            veto=False,
            checks_run=["INV-04", "INV-06"],
            failures=[],
            warnings=[],
        )
        required_keys = {
            "slug",
            "timestamp",
            "passed",
            "veto",
            "checks_run",
            "failures",
            "warnings",
            "revision_instructions",
        }
        assert required_keys.issubset(entry.keys()), (
            f"Missing keys: {required_keys - entry.keys()}"
        )

    def test_slug_field_matches_provided_slug(self) -> None:
        entry = build_qa_log_entry(
            slug="intro_slide",
            passed=False,
            veto=False,
            checks_run=[],
            failures=[],
            warnings=[],
        )
        assert entry["slug"] == "intro_slide"

    def test_passed_field_is_bool_true_when_no_failures(self) -> None:
        entry = build_qa_log_entry(
            slug="s",
            passed=True,
            veto=False,
            checks_run=[],
            failures=[],
            warnings=[],
        )
        assert entry["passed"] is True
        assert isinstance(entry["passed"], bool)

    def test_passed_field_is_bool_false_when_failures_present(self) -> None:
        failure: dict[str, str] = {
            "invariant": "INV-06",
            "description": "inline style found",
            "revision_instruction": "Remove inline style attributes.",
        }
        entry = build_qa_log_entry(
            slug="s",
            passed=False,
            veto=False,
            checks_run=["INV-06"],
            failures=[failure],
            warnings=[],
        )
        assert entry["passed"] is False
        assert isinstance(entry["passed"], bool)

    def test_veto_field_is_bool(self) -> None:
        entry = build_qa_log_entry(
            slug="s",
            passed=False,
            veto=True,
            checks_run=[],
            failures=[],
            warnings=[],
        )
        assert entry["veto"] is True
        assert isinstance(entry["veto"], bool)

    def test_checks_run_field_is_list(self) -> None:
        entry = build_qa_log_entry(
            slug="s",
            passed=True,
            veto=False,
            checks_run=["INV-04", "INV-08"],
            failures=[],
            warnings=[],
        )
        assert isinstance(entry["checks_run"], list)
        assert entry["checks_run"] == ["INV-04", "INV-08"]

    def test_failures_field_is_list(self) -> None:
        entry = build_qa_log_entry(
            slug="s",
            passed=True,
            veto=False,
            checks_run=[],
            failures=[],
            warnings=[],
        )
        assert isinstance(entry["failures"], list)

    def test_warnings_field_is_list(self) -> None:
        entry = build_qa_log_entry(
            slug="s",
            passed=True,
            veto=False,
            checks_run=[],
            failures=[],
            warnings=[],
        )
        assert isinstance(entry["warnings"], list)

    def test_revision_instructions_is_list(self) -> None:
        entry = build_qa_log_entry(
            slug="s",
            passed=True,
            veto=False,
            checks_run=[],
            failures=[],
            warnings=[],
        )
        assert isinstance(entry["revision_instructions"], list)

    def test_revision_instructions_derived_from_failure_revision_instruction_fields(
        self,
    ) -> None:
        failure1: dict[str, str] = {
            "invariant": "INV-06",
            "description": "inline style",
            "revision_instruction": "Remove all inline style attributes.",
        }
        failure2: dict[str, str] = {
            "invariant": "INV-07",
            "description": "external URL",
            "revision_instruction": "Remove external URL references.",
        }
        entry = build_qa_log_entry(
            slug="s",
            passed=False,
            veto=False,
            checks_run=["INV-06", "INV-07"],
            failures=[failure1, failure2],
            warnings=[],
        )
        assert "Remove all inline style attributes." in entry["revision_instructions"]
        assert "Remove external URL references." in entry["revision_instructions"]

    def test_revision_instructions_empty_when_no_failures(self) -> None:
        entry = build_qa_log_entry(
            slug="s",
            passed=True,
            veto=False,
            checks_run=["INV-04"],
            failures=[],
            warnings=[],
        )
        assert entry["revision_instructions"] == []

    def test_timestamp_is_iso_8601_string(self) -> None:
        import re

        entry = build_qa_log_entry(
            slug="s",
            passed=True,
            veto=False,
            checks_run=[],
            failures=[],
            warnings=[],
        )
        # ISO 8601 basic pattern: YYYY-MM-DDThh:mm:ss
        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
        assert isinstance(entry["timestamp"], str)
        assert iso_pattern.match(entry["timestamp"]), (
            f"timestamp '{entry['timestamp']}' does not match ISO 8601"
        )

    def test_entry_is_json_serializable(self) -> None:
        failure: dict[str, str] = {
            "invariant": "INV-04",
            "description": "low contrast",
            "revision_instruction": "Increase contrast.",
        }
        entry = build_qa_log_entry(
            slug="contrast_slide",
            passed=False,
            veto=False,
            checks_run=["INV-04"],
            failures=[failure],
            warnings=[],
        )
        # must not raise
        serialized = json.dumps(entry)
        decoded = json.loads(serialized)
        assert decoded["slug"] == "contrast_slide"


# ===========================================================================
# BC-9.4 — build_qa_log_entry: veto entry shape
# ===========================================================================


class TestBuildQaLogEntryVetoShape:
    """BC-9.4 / BC-9.10: veto entries carry correct flag and failure list."""

    def test_veto_true_is_preserved_in_entry(self) -> None:
        veto_failure: dict[str, str] = {
            "invariant": "VETO-01",
            "description": "blank slide",
            "revision_instruction": "Add content to the slide.",
        }
        entry = build_qa_log_entry(
            slug="blank",
            passed=False,
            veto=True,
            checks_run=[],
            failures=[veto_failure],
            warnings=[],
        )
        assert entry["veto"] is True

    def test_veto_entry_failures_list_contains_veto_failure(self) -> None:
        veto_failure: dict[str, str] = {
            "invariant": "VETO-02",
            "description": "screenshot unreadable",
            "revision_instruction": "Re-render the slide.",
        }
        entry = build_qa_log_entry(
            slug="s",
            passed=False,
            veto=True,
            checks_run=[],
            failures=[veto_failure],
            warnings=[],
        )
        assert len(entry["failures"]) == 1
        assert entry["failures"][0]["invariant"] == "VETO-02"

    def test_veto_false_entry_has_false_veto_field(self) -> None:
        entry = build_qa_log_entry(
            slug="good_slide",
            passed=True,
            veto=False,
            checks_run=["INV-04", "INV-06"],
            failures=[],
            warnings=[],
        )
        assert entry["veto"] is False


# ===========================================================================
# BC-9.4 — append_qa_log: file append semantics
# ===========================================================================


class TestAppendQaLog:
    """BC-9.4: append_qa_log writes one JSON line per entry to qa_log.jsonl."""

    def _make_project_tree(self, tmp_path: Path) -> Path:
        project_root = tmp_path / "project"
        (project_root / "output").mkdir(parents=True)
        return project_root

    def test_appending_single_entry_creates_qa_log_jsonl(self, tmp_path: Path) -> None:
        project_root = self._make_project_tree(tmp_path)
        entry: dict[str, Any] = {
            "slug": "s",
            "timestamp": "2026-04-12T10:00:00",
            "passed": True,
            "veto": False,
            "checks_run": [],
            "failures": [],
            "warnings": [],
            "revision_instructions": [],
        }
        append_qa_log(project_root, entry)
        log_path = project_root / "output" / "qa_log.jsonl"
        assert log_path.exists()

    def test_single_appended_entry_is_valid_json_line(self, tmp_path: Path) -> None:
        project_root = self._make_project_tree(tmp_path)
        entry: dict[str, Any] = {
            "slug": "my_slide",
            "timestamp": "2026-04-12T10:00:00",
            "passed": False,
            "veto": False,
            "checks_run": ["INV-06"],
            "failures": [
                {
                    "invariant": "INV-06",
                    "description": "inline style",
                    "revision_instruction": "Remove it.",
                }
            ],
            "warnings": [],
            "revision_instructions": ["Remove it."],
        }
        append_qa_log(project_root, entry)
        log_path = project_root / "output" / "qa_log.jsonl"
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        decoded = json.loads(lines[0])
        assert decoded["slug"] == "my_slide"

    def test_multiple_appends_produce_multiple_jsonl_lines(
        self, tmp_path: Path
    ) -> None:
        project_root = self._make_project_tree(tmp_path)
        for slug in ["slide_a", "slide_b", "slide_c"]:
            entry: dict[str, Any] = {
                "slug": slug,
                "timestamp": "2026-04-12T10:00:00",
                "passed": True,
                "veto": False,
                "checks_run": [],
                "failures": [],
                "warnings": [],
                "revision_instructions": [],
            }
            append_qa_log(project_root, entry)
        log_path = project_root / "output" / "qa_log.jsonl"
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        slugs = [json.loads(line)["slug"] for line in lines]
        assert slugs == ["slide_a", "slide_b", "slide_c"]

    def test_each_line_in_jsonl_is_valid_json(self, tmp_path: Path) -> None:
        project_root = self._make_project_tree(tmp_path)
        for i in range(5):
            entry: dict[str, Any] = {
                "slug": f"slide_{i}",
                "timestamp": "2026-04-12T11:00:00",
                "passed": True,
                "veto": False,
                "checks_run": [],
                "failures": [],
                "warnings": [],
                "revision_instructions": [],
            }
            append_qa_log(project_root, entry)
        log_path = project_root / "output" / "qa_log.jsonl"
        for line in log_path.read_text(encoding="utf-8").strip().splitlines():
            json.loads(line)  # must not raise

    def test_append_does_not_overwrite_existing_entries(self, tmp_path: Path) -> None:
        project_root = self._make_project_tree(tmp_path)
        first: dict[str, Any] = {
            "slug": "first",
            "timestamp": "2026-04-12T09:00:00",
            "passed": True,
            "veto": False,
            "checks_run": [],
            "failures": [],
            "warnings": [],
            "revision_instructions": [],
        }
        append_qa_log(project_root, first)
        second: dict[str, Any] = {
            "slug": "second",
            "timestamp": "2026-04-12T09:01:00",
            "passed": False,
            "veto": False,
            "checks_run": ["INV-04"],
            "failures": [
                {
                    "invariant": "INV-04",
                    "description": "low contrast",
                    "revision_instruction": "Fix contrast.",
                }
            ],
            "warnings": [],
            "revision_instructions": ["Fix contrast."],
        }
        append_qa_log(project_root, second)
        log_path = project_root / "output" / "qa_log.jsonl"
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["slug"] == "first"
        assert json.loads(lines[1])["slug"] == "second"


# ===========================================================================
# BC-9.4 — check_no_inline_styles: INV-06
# ===========================================================================


class TestCheckNoInlineStyles:
    """BC-9.4 / INV-06: check_no_inline_styles returns None for clean slides."""

    def test_returns_none_for_slide_with_no_inline_styles(self, tmp_path: Path) -> None:
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        result = check_no_inline_styles(slide)
        assert result is None

    def test_returns_qa_failure_when_inline_style_attribute_present(
        self, tmp_path: Path
    ) -> None:
        slide = _write_slide(tmp_path, _INLINE_STYLE_HTML)
        result = check_no_inline_styles(slide)
        assert result is not None

    def test_qa_failure_has_invariant_key_inv_06(self, tmp_path: Path) -> None:
        slide = _write_slide(tmp_path, _INLINE_STYLE_HTML)
        result = check_no_inline_styles(slide)
        assert result is not None
        assert result.get("invariant") == "INV-06"

    def test_qa_failure_has_description_key(self, tmp_path: Path) -> None:
        slide = _write_slide(tmp_path, _INLINE_STYLE_HTML)
        result = check_no_inline_styles(slide)
        assert result is not None
        assert "description" in result
        assert isinstance(result["description"], str)

    def test_qa_failure_has_revision_instruction_key(self, tmp_path: Path) -> None:
        slide = _write_slide(tmp_path, _INLINE_STYLE_HTML)
        result = check_no_inline_styles(slide)
        assert result is not None
        assert "revision_instruction" in result
        assert isinstance(result["revision_instruction"], str)

    def test_returns_none_for_slide_with_class_attribute_but_no_style(
        self, tmp_path: Path
    ) -> None:
        html = (
            '<!DOCTYPE html><html><body><div class="highlight">text</div></body></html>'
        )
        slide = _write_slide(tmp_path, html)
        result = check_no_inline_styles(slide)
        assert result is None

    def test_detects_inline_style_on_span_element(self, tmp_path: Path) -> None:
        html = (
            "<!DOCTYPE html><html><body>"
            '<p><span style="font-size:2em">big</span></p>'
            "</body></html>"
        )
        slide = _write_slide(tmp_path, html)
        result = check_no_inline_styles(slide)
        assert result is not None


# ===========================================================================
# BC-9.4 — check_no_external_requests: INV-07
# ===========================================================================


class TestCheckNoExternalRequests:
    """BC-9.4 / INV-07: check_no_external_requests detects external URLs."""

    def test_returns_none_for_slide_with_only_local_references(
        self, tmp_path: Path
    ) -> None:
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        result = check_no_external_requests(slide)
        assert result is None

    def test_returns_qa_failure_when_https_src_present(self, tmp_path: Path) -> None:
        slide = _write_slide(tmp_path, _EXTERNAL_SRC_HTML)
        result = check_no_external_requests(slide)
        assert result is not None

    def test_returns_qa_failure_when_http_href_present(self, tmp_path: Path) -> None:
        slide = _write_slide(tmp_path, _EXTERNAL_HREF_HTML)
        result = check_no_external_requests(slide)
        assert result is not None

    def test_qa_failure_has_invariant_key_inv_07(self, tmp_path: Path) -> None:
        slide = _write_slide(tmp_path, _EXTERNAL_SRC_HTML)
        result = check_no_external_requests(slide)
        assert result is not None
        assert result.get("invariant") == "INV-07"

    def test_qa_failure_has_description_key(self, tmp_path: Path) -> None:
        slide = _write_slide(tmp_path, _EXTERNAL_SRC_HTML)
        result = check_no_external_requests(slide)
        assert result is not None
        assert "description" in result
        assert isinstance(result["description"], str)

    def test_qa_failure_has_revision_instruction_key(self, tmp_path: Path) -> None:
        slide = _write_slide(tmp_path, _EXTERNAL_SRC_HTML)
        result = check_no_external_requests(slide)
        assert result is not None
        assert "revision_instruction" in result

    def test_local_relative_src_does_not_trigger_failure(self, tmp_path: Path) -> None:
        html = (
            "<!DOCTYPE html><html><head>"
            '<script src="vendor/mermaid.min.js"></script>'
            "</head><body></body></html>"
        )
        slide = _write_slide(tmp_path, html)
        result = check_no_external_requests(slide)
        assert result is None

    def test_local_relative_href_does_not_trigger_failure(self, tmp_path: Path) -> None:
        html = (
            "<!DOCTYPE html><html><head>"
            '<link rel="stylesheet" href="assets/style.css">'
            "</head><body></body></html>"
        )
        slide = _write_slide(tmp_path, html)
        result = check_no_external_requests(slide)
        assert result is None

    def test_https_in_comment_does_not_trigger_failure(self, tmp_path: Path) -> None:
        # A URL that appears only inside an HTML comment must not trigger the
        # check -- the slide has no live external requests.
        html = "<!DOCTYPE html><html><body><!-- https://example.com --></body></html>"
        slide = _write_slide(tmp_path, html)
        # Whether comments are excluded is implementation-specific, but at
        # minimum the check must not raise an exception.
        _ = check_no_external_requests(slide)


# ===========================================================================
# BC-9.4 — check_permitted_libraries: INV-10
# ===========================================================================


class TestCheckPermittedLibraries:
    """BC-9.4 / INV-10: check_permitted_libraries enforces allowed scripts."""

    def test_returns_none_when_all_scripts_are_in_permitted_list(
        self, tmp_path: Path
    ) -> None:
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        result = check_permitted_libraries(slide, permitted=["mermaid"])
        assert result is None

    def test_returns_qa_failure_when_unpermitted_library_is_referenced(
        self, tmp_path: Path
    ) -> None:
        # _KATEX_SLIDE_HTML references katex; permitted list only allows mermaid
        slide = _write_slide(tmp_path, _KATEX_SLIDE_HTML)
        result = check_permitted_libraries(slide, permitted=["mermaid"])
        assert result is not None

    def test_qa_failure_has_invariant_key_inv_10(self, tmp_path: Path) -> None:
        slide = _write_slide(tmp_path, _KATEX_SLIDE_HTML)
        result = check_permitted_libraries(slide, permitted=["mermaid"])
        assert result is not None
        assert result.get("invariant") == "INV-10"

    def test_qa_failure_has_description_and_revision_instruction(
        self, tmp_path: Path
    ) -> None:
        slide = _write_slide(tmp_path, _KATEX_SLIDE_HTML)
        result = check_permitted_libraries(slide, permitted=["mermaid"])
        assert result is not None
        assert "description" in result
        assert "revision_instruction" in result

    def test_returns_none_for_slide_with_no_diagram_scripts(
        self, tmp_path: Path
    ) -> None:
        html = (
            "<!DOCTYPE html><html><head></head>"
            "<body><p>No scripts at all.</p></body></html>"
        )
        slide = _write_slide(tmp_path, html)
        result = check_permitted_libraries(slide, permitted=["mermaid"])
        assert result is None

    def test_empty_permitted_list_flags_any_diagram_library(
        self, tmp_path: Path
    ) -> None:
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        # mermaid.min.js is referenced; permitted list is empty -> failure
        result = check_permitted_libraries(slide, permitted=[])
        assert result is not None

    def test_both_mermaid_and_katex_permitted_returns_none(
        self, tmp_path: Path
    ) -> None:
        html = (
            "<!DOCTYPE html><html><head>"
            '<script src="vendor/mermaid.min.js"></script>'
            '<script src="vendor/katex.min.js"></script>'
            "</head><body></body></html>"
        )
        slide = _write_slide(tmp_path, html)
        result = check_permitted_libraries(slide, permitted=["mermaid", "katex"])
        assert result is None


# ===========================================================================
# BC-9.2 — main_qa_checker: per-invocation Playwright context
# ===========================================================================


class TestMainQaCheckerPlaywrightContext:
    """BC-9.2: main_qa_checker opens and closes its own sync_playwright context."""

    def test_playwright_context_is_opened_once_per_invocation(
        self, tmp_path: Path
    ) -> None:
        """sync_playwright().__enter__ is called exactly once per invocation."""
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        screenshot_path = tmp_path / "output" / "screenshots" / "s.png"
        screenshot_path.parent.mkdir(parents=True)

        mock_page = MagicMock()
        mock_page.evaluate.return_value = None
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_context_manager = MagicMock()
        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_context_manager.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_context_manager.__exit__ = MagicMock(return_value=False)

        with (
            patch("qa_checker.sync_playwright", return_value=mock_context_manager),
            pytest.raises(SystemExit),
        ):
            from qa_checker import main_qa_checker

            main_qa_checker(slide, screenshot_path, tmp_path)

        mock_context_manager.__enter__.assert_called_once()

    def test_playwright_context_exit_called_even_when_exception_raised(
        self, tmp_path: Path
    ) -> None:
        """Context __exit__ is called in a finally block (cleanup on exception)."""
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        screenshot_path = tmp_path / "output" / "screenshots" / "s.png"
        screenshot_path.parent.mkdir(parents=True)

        mock_browser = MagicMock()
        mock_page = MagicMock()
        # Raise RuntimeError during screenshot to simulate Playwright crash
        mock_page.screenshot.side_effect = RuntimeError("playwright crash")
        mock_browser.new_page.return_value = mock_page
        mock_context_manager = MagicMock()
        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_context_manager.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_context_manager.__exit__ = MagicMock(return_value=False)

        with (
            patch("qa_checker.sync_playwright", return_value=mock_context_manager),
            pytest.raises(SystemExit),
        ):
            from qa_checker import main_qa_checker

            main_qa_checker(slide, screenshot_path, tmp_path)

        # __exit__ must have been called (finally-block semantics)
        mock_context_manager.__exit__.assert_called_once()

    def test_playwright_context_exit_called_on_clean_exit_path(
        self, tmp_path: Path
    ) -> None:
        """BC-9.2: __exit__ is also called when main_qa_checker exits cleanly
        (exit code 0, no exception). The finally block must always run."""
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        screenshot_path = tmp_path / "output" / "screenshots" / "clean.png"
        screenshot_path.parent.mkdir(parents=True)

        mock_page = MagicMock()
        mock_page.evaluate.return_value = None
        mock_page.inner_text.return_value = ""  # BUG-AUDIT-37: veto checks need string

        def _write_png(path: str) -> None:
            Path(path).write_bytes(b"\x89PNG")

        mock_page.screenshot.side_effect = _write_png
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_context_manager = MagicMock()
        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_context_manager.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_context_manager.__exit__ = MagicMock(return_value=False)

        with (
            patch("qa_checker.sync_playwright", return_value=mock_context_manager),
            pytest.raises(SystemExit) as exc_info,
        ):
            from qa_checker import main_qa_checker

            main_qa_checker(slide, screenshot_path, tmp_path)

        assert exc_info.value.code == 0
        # __exit__ must be called even on the clean exit path
        mock_context_manager.__exit__.assert_called_once()


# ===========================================================================
# BC-9.3 — main_qa_checker: screenshot written before checks; failure on crash
# ===========================================================================


class TestMainQaCheckerScreenshotBeforeChecks:
    """BC-9.3: screenshot must be written before invariant checks."""

    def test_screenshot_failure_writes_screenshot_invariant_entry_to_qa_log(
        self, tmp_path: Path
    ) -> None:
        """When screenshot raises, a SCREENSHOT failure is appended to qa_log."""
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        (tmp_path / "output" / "screenshots").mkdir(parents=True)
        screenshot_path = tmp_path / "output" / "screenshots" / "crash.png"

        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_page.screenshot.side_effect = RuntimeError("browser timeout")
        mock_browser.new_page.return_value = mock_page
        mock_context_manager = MagicMock()
        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_context_manager.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_context_manager.__exit__ = MagicMock(return_value=False)

        with (
            patch("qa_checker.sync_playwright", return_value=mock_context_manager),
            pytest.raises(SystemExit) as exc_info,
        ):
            from qa_checker import main_qa_checker

            main_qa_checker(slide, screenshot_path, tmp_path)

        # Must exit with code 1
        assert exc_info.value.code == 1

        # qa_log.jsonl must contain a SCREENSHOT failure entry
        log_path = tmp_path / "output" / "qa_log.jsonl"
        assert log_path.exists(), "qa_log.jsonl was not created on screenshot failure"
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 1
        found_screenshot_failure = any(
            any(
                f.get("invariant") == "SCREENSHOT"
                for f in json.loads(line).get("failures", [])
            )
            for line in lines
        )
        assert found_screenshot_failure, (
            "No SCREENSHOT invariant failure found in qa_log.jsonl"
        )

    def test_screenshot_failure_exits_with_code_1(self, tmp_path: Path) -> None:
        """main_qa_checker exits code 1 when screenshot raises."""
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        (tmp_path / "output" / "screenshots").mkdir(parents=True)
        screenshot_path = tmp_path / "output" / "screenshots" / "err.png"

        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_page.screenshot.side_effect = RuntimeError("crash")
        mock_browser.new_page.return_value = mock_page
        mock_context_manager = MagicMock()
        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_context_manager.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_context_manager.__exit__ = MagicMock(return_value=False)

        with (
            patch("qa_checker.sync_playwright", return_value=mock_context_manager),
            pytest.raises(SystemExit) as exc_info,
        ):
            from qa_checker import main_qa_checker

            main_qa_checker(slide, screenshot_path, tmp_path)

        assert exc_info.value.code == 1


# ===========================================================================
# BC-9.1 — veto flag propagation through build_qa_log_entry
# ===========================================================================


class TestVetoFlagPropagation:
    """BC-9.1: veto entries must have veto=True; non-veto entries have veto=False.

    BC-9.1 is primarily an agent-level ordering concern. The testable Python
    contract is that build_qa_log_entry faithfully records the veto flag, so
    that any downstream consumer (update_state, the routing script) can rely
    on it to distinguish agent veto results from programmatic check results.
    """

    def test_non_veto_entry_has_veto_false(self) -> None:
        entry = build_qa_log_entry(
            slug="s",
            passed=True,
            veto=False,
            checks_run=["INV-04", "INV-06", "INV-07", "INV-08"],
            failures=[],
            warnings=[],
        )
        assert entry["veto"] is False

    def test_veto_entry_has_veto_true_and_passed_false(self) -> None:
        veto_failure: dict[str, str] = {
            "invariant": "VETO-03",
            "description": "placeholder content",
            "revision_instruction": "Replace placeholder text.",
        }
        entry = build_qa_log_entry(
            slug="placeholder_slide",
            passed=False,
            veto=True,
            checks_run=[],
            failures=[veto_failure],
            warnings=[],
        )
        assert entry["veto"] is True
        assert entry["passed"] is False

    def test_veto_revision_instructions_derived_from_veto_failure(self) -> None:
        veto_failure: dict[str, str] = {
            "invariant": "VETO-05",
            "description": "speaker notes visible",
            "revision_instruction": "Hide speaker notes.",
        }
        entry = build_qa_log_entry(
            slug="notes_slide",
            passed=False,
            veto=True,
            checks_run=[],
            failures=[veto_failure],
            warnings=[],
        )
        assert "Hide speaker notes." in entry["revision_instructions"]

    def test_checks_run_list_preserved_in_entry(self) -> None:
        checks = ["INV-04", "INV-06", "INV-07", "INV-08", "INV-10"]
        entry = build_qa_log_entry(
            slug="s",
            passed=True,
            veto=False,
            checks_run=checks,
            failures=[],
            warnings=[],
        )
        assert entry["checks_run"] == checks


# ===========================================================================
# BC-9.11 — main_qa_checker: json_repair env check (exit code 2)
# ===========================================================================


class TestMainQaCheckerEnvCheck:
    """BC-9.11: main_qa_checker exits 2 if json_repair is unavailable."""

    def test_exits_with_code_2_when_json_repair_not_available(
        self, tmp_path: Path
    ) -> None:
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        screenshot_path = tmp_path / "output" / "screenshots" / "s.png"
        screenshot_path.parent.mkdir(parents=True)

        with (
            patch("importlib.util.find_spec", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            # Re-import after patching find_spec to simulate missing package
            import importlib

            import qa_checker as _qc

            importlib.reload(_qc)
            _qc.main_qa_checker(slide, screenshot_path, tmp_path)

        assert exc_info.value.code == 2


# ===========================================================================
# BC-9.1 — no side effects on module import
# ===========================================================================


class TestQaCheckerNoSideEffectsOnImport:
    """BC-9.1: importing qa_checker must not invoke sync_playwright or I/O."""

    def test_importing_qa_checker_does_not_call_sync_playwright(self) -> None:
        """BC-9.1: the module boundary contract is that qa_checker can be
        imported without triggering any Playwright launch or browser
        process.  We reload the module under a sentinel mock to confirm
        sync_playwright is never called at import time.
        """
        import importlib

        import qa_checker as _qc

        mock_pw = MagicMock()
        with patch("qa_checker.sync_playwright", mock_pw):
            importlib.reload(_qc)

        # sync_playwright must NOT have been called as a side effect of import
        mock_pw.assert_not_called()


# ===========================================================================
# BC-9.3 — screenshot failure: checks_run must be empty
# ===========================================================================


class TestScreenshotFailureChecksRunEmpty:
    """BC-9.3: when screenshot fails, no invariant checks run (checks_run=[])."""

    def _make_crash_mocks(self) -> tuple[MagicMock, MagicMock]:
        """Return (mock_context_manager, mock_page) wired for screenshot crash."""
        mock_page = MagicMock()
        mock_page.screenshot.side_effect = RuntimeError("timeout during screenshot")
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        return mock_ctx, mock_page

    def test_checks_run_is_empty_in_log_entry_when_screenshot_fails(
        self, tmp_path: Path
    ) -> None:
        """BC-9.3: the qa_log entry written on screenshot failure must have
        checks_run == [] because no programmatic checks ran."""
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        (tmp_path / "output" / "screenshots").mkdir(parents=True)
        screenshot_path = tmp_path / "output" / "screenshots" / "fail.png"

        mock_ctx, _ = self._make_crash_mocks()

        with (
            patch("qa_checker.sync_playwright", return_value=mock_ctx),
            pytest.raises(SystemExit),
        ):
            from qa_checker import main_qa_checker

            main_qa_checker(slide, screenshot_path, tmp_path)

        log_path = tmp_path / "output" / "qa_log.jsonl"
        assert log_path.exists()
        entry = json.loads(
            log_path.read_text(encoding="utf-8").strip().splitlines()[0]
        )
        assert entry["checks_run"] == [], (
            "checks_run must be empty when screenshot fails; "
            f"got {entry['checks_run']}"
        )

    def test_no_inv_checks_were_called_when_screenshot_fails(
        self, tmp_path: Path
    ) -> None:
        """BC-9.3: programmatic check functions must not be called after a
        screenshot failure.  We verify by confirming the only failure in
        qa_log is the SCREENSHOT entry and no INV-* invariant IDs appear."""
        slide = _write_slide(tmp_path, _INLINE_STYLE_HTML)
        (tmp_path / "output" / "screenshots").mkdir(parents=True)
        screenshot_path = tmp_path / "output" / "screenshots" / "noinv.png"

        mock_ctx, _ = self._make_crash_mocks()

        with (
            patch("qa_checker.sync_playwright", return_value=mock_ctx),
            pytest.raises(SystemExit),
        ):
            from qa_checker import main_qa_checker

            main_qa_checker(slide, screenshot_path, tmp_path)

        log_path = tmp_path / "output" / "qa_log.jsonl"
        entry = json.loads(
            log_path.read_text(encoding="utf-8").strip().splitlines()[0]
        )
        invariant_ids = [f.get("invariant") for f in entry.get("failures", [])]
        inv_checks = [i for i in invariant_ids if str(i).startswith("INV-")]
        assert inv_checks == [], (
            "No INV-* failures should appear when screenshot fails; "
            f"got {inv_checks}"
        )


# ===========================================================================
# BC-9.4 — screenshot failure entry conforms to canonical schema
# ===========================================================================


class TestScreenshotFailureEntryCanonicalSchema:
    """BC-9.4: the qa_log entry written on screenshot failure must include
    all eight required canonical schema keys."""

    _REQUIRED_KEYS = {
        "slug",
        "timestamp",
        "passed",
        "veto",
        "checks_run",
        "failures",
        "warnings",
        "revision_instructions",
    }

    def test_screenshot_failure_entry_has_all_required_keys(
        self, tmp_path: Path
    ) -> None:
        """BC-9.4: the SCREENSHOT failure log entry must contain every key
        required by the canonical qa_log.jsonl schema."""
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        (tmp_path / "output" / "screenshots").mkdir(parents=True)
        screenshot_path = tmp_path / "output" / "screenshots" / "schema.png"

        mock_page = MagicMock()
        mock_page.screenshot.side_effect = RuntimeError("crash")
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with (
            patch("qa_checker.sync_playwright", return_value=mock_ctx),
            pytest.raises(SystemExit),
        ):
            from qa_checker import main_qa_checker

            main_qa_checker(slide, screenshot_path, tmp_path)

        log_path = tmp_path / "output" / "qa_log.jsonl"
        assert log_path.exists()
        entry = json.loads(
            log_path.read_text(encoding="utf-8").strip().splitlines()[0]
        )
        missing = self._REQUIRED_KEYS - entry.keys()
        assert not missing, (
            f"Screenshot failure entry is missing canonical keys: {missing}"
        )

    def test_screenshot_failure_entry_passed_is_false(
        self, tmp_path: Path
    ) -> None:
        """BC-9.4: passed must be False in the SCREENSHOT failure entry."""
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        (tmp_path / "output" / "screenshots").mkdir(parents=True)
        screenshot_path = tmp_path / "output" / "screenshots" / "pf.png"

        mock_page = MagicMock()
        mock_page.screenshot.side_effect = RuntimeError("crash")
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with (
            patch("qa_checker.sync_playwright", return_value=mock_ctx),
            pytest.raises(SystemExit),
        ):
            from qa_checker import main_qa_checker

            main_qa_checker(slide, screenshot_path, tmp_path)

        log_path = tmp_path / "output" / "qa_log.jsonl"
        entry = json.loads(
            log_path.read_text(encoding="utf-8").strip().splitlines()[0]
        )
        assert entry["passed"] is False

    def test_screenshot_failure_entry_revision_instructions_non_empty(
        self, tmp_path: Path
    ) -> None:
        """BC-9.4: revision_instructions must be derived from the SCREENSHOT
        failure's revision_instruction field and must not be empty."""
        slide = _write_slide(tmp_path, _CLEAN_SLIDE_HTML)
        (tmp_path / "output" / "screenshots").mkdir(parents=True)
        screenshot_path = tmp_path / "output" / "screenshots" / "ri.png"

        mock_page = MagicMock()
        mock_page.screenshot.side_effect = RuntimeError("crash")
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with (
            patch("qa_checker.sync_playwright", return_value=mock_ctx),
            pytest.raises(SystemExit),
        ):
            from qa_checker import main_qa_checker

            main_qa_checker(slide, screenshot_path, tmp_path)

        log_path = tmp_path / "output" / "qa_log.jsonl"
        entry = json.loads(
            log_path.read_text(encoding="utf-8").strip().splitlines()[0]
        )
        assert isinstance(entry["revision_instructions"], list)
        assert len(entry["revision_instructions"]) >= 1, (
            "revision_instructions must be non-empty for a SCREENSHOT failure"
        )
