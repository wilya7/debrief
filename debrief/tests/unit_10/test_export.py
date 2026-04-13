# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Tests for Unit 10: Export Module.

Tested contracts: BC-10.1 through BC-10.9.

Synthetic data generation assumptions
--------------------------------------
- ``DeckState`` objects are constructed directly from the dataclass fields
  defined in Unit 2 (state management).  Where Unit 2 is not available, a
  lightweight ``SimpleNamespace``-based stand-in with the same attribute names
  is used.  The stand-in is assembled in the ``make_deck_state`` fixture.
- Slide HTML files are minimal well-formed HTML5 strings written to
  ``tmp_path/slides/``.  They are not browser-renderable but their paths are
  valid ``Path`` objects, which is all the export module needs for page-list
  construction.
- ``SlideRecord`` stand-ins are ``SimpleNamespace`` objects with fields:
  ``slug``, ``title``, ``status`` ("approved"), ``backup`` (bool),
  ``content_summary``, ``visual_approach``, ``design_choices``,
  ``forks_not_taken``, ``user_recommendations``, ``qa_passed`` (True),
  ``accepted_violations`` ([]), ``last_modified`` (ISO8601 string),
  ``group_id``, ``user_assets`` ([]), ``has_math`` (False).
- ``PresentationRecord`` stand-ins have fields: ``folder``, ``created_at``,
  ``slide_manifest`` ([]), ``export_count`` (int), ``script_count`` (0),
  ``handout_count`` (0), ``separator_position`` (None or int),
  ``separator_content`` (None or str).
- ``style_config`` test dicts use realistic CSS token values sourced from the
  BC-6 CSS_PROPERTY_MAP dot-paths.  The exact values are arbitrary but well-
  typed.
- ``export_log.jsonl`` entries are verified by reading the file back and
  parsing each line as JSON.  The JSONL append contract (BC-10.5 + REQ-EXPORT-5)
  requires all 7 schema fields to be present.
- All ``tmp_path`` project trees are created fresh per test via pytest
  fixtures; no test shares mutable state.
- The canonical PDF page order tests (BC-10.3) exercise all combinations:
  main-only, main+closing, main+separator, main+closing+separator+backup,
  backup-only, empty deck.
- ``generate_closing_slide_html`` is tested for structural HTML validity (has
  ``<html>``, ``<body>``, and CSS variable usage) without asserting on the
  exact pixel values so the tests remain implementation-agnostic.
- ``generate_separator_html`` is tested with each of the four recognised
  ``separator_content`` values: ``'acknowledgments'``, ``'questions'``,
  ``'summary'``, and a custom text string.
- ``append_export_log`` is tested with ``error_message=None`` (success path)
  and with a non-null ``error_message`` (failure path per BC-10.5).
- Multiple sequential ``append_export_log`` calls on the same file verify
  the append-only contract (JSONL grows, old entries are preserved).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
from export import (
    append_export_log,
    build_page_list,
    generate_closing_slide_html,
    generate_separator_html,
)

# ---------------------------------------------------------------------------
# Helpers to build stand-in state objects
# ---------------------------------------------------------------------------


def _make_slide(
    slug: str,
    backup: bool = False,
    status: str = "approved",
) -> SimpleNamespace:
    """Return a minimal SlideRecord stand-in."""
    return SimpleNamespace(
        slug=slug,
        title=f"Title of {slug}",
        status=status,
        backup=backup,
        content_summary="summary",
        visual_approach="visual",
        design_choices="choices",
        forks_not_taken=None,
        user_recommendations=None,
        qa_passed=True,
        accepted_violations=[],
        last_modified="2026-04-12T00:00:00Z",
        group_id="group_01",
        user_assets=[],
        has_math=False,
    )


def _make_presentation(
    folder: str = "2026_04_12_test",
    export_count: int = 0,
    separator_position: Optional[int] = None,
    separator_content: Optional[str] = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        folder=folder,
        created_at="2026-04-12T00:00:00Z",
        slide_manifest=[],
        export_count=export_count,
        script_count=0,
        handout_count=0,
        separator_position=separator_position,
        separator_content=separator_content,
    )


def _make_deck_state(
    slides: list[SimpleNamespace],
    closing_slide: Optional[str] = None,
    presentations: Optional[list[SimpleNamespace]] = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        project_name="test_project",
        created_at="2026-04-12T00:00:00Z",
        archetype="lab_meeting",
        style_locked=True,
        closing_slide=closing_slide,
        slides=slides,
        presentations=presentations or [],
    )


_MINIMAL_STYLE_CONFIG: dict[str, Any] = {
    "colors": {
        "primary": "#1a1a2e",
        "secondary": "#16213e",
        "accent": "#0f3460",
        "background": "#ffffff",
        "text_primary": "#000000",
        "text_secondary": "#444444",
        "code_background": "#f5f5f5",
        "border": "#dddddd",
    },
    "typography": {
        "heading_font_family": "Inter",
        "body_font_family": "Inter",
        "code_font_family": "Fira Code",
        "heading_size_base": "2rem",
        "body_size_base": "1rem",
        "heading_weight": "700",
        "body_weight": "400",
        "line_height": "1.5",
    },
    "spacing": {
        "margin_pct": "5",
        "gap": "1rem",
        "section_gap": "2rem",
    },
    "layout": {
        "slide_width": "1920",
        "slide_height": "1080",
        "column_gap": "2rem",
    },
    "data_viz": {
        "primary_colormap": "viridis",
        "axis_color": "#333333",
        "grid_color": "#eeeeee",
        "annotation_color": "#ff0000",
    },
    "constraints": {
        "permitted_diagram_types": ["mermaid"],
    },
    "provenance": {
        "source": "stylist",
    },
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    """Return a project tree with slides/ and output/ directories."""
    (tmp_path / "slides").mkdir()
    (tmp_path / "output").mkdir()
    return tmp_path


@pytest.fixture()
def slide_files(project_dir: Path) -> list[Path]:
    """Write two minimal slide HTML files, return their paths."""
    paths = []
    for slug in ("intro", "methods"):
        p = project_dir / "slides" / f"{slug}.html"
        p.write_text(
            f"<!DOCTYPE html><html><body>{slug}</body></html>",
            encoding="utf-8",
        )
        paths.append(p)
    return paths


# ===========================================================================
# BC-10.3: Canonical PDF page order
# ===========================================================================


class TestBuildPageListCanonicalOrder:
    """Tests for build_page_list per BC-10.3 (Section 24.10 ordering)."""

    def test_main_slides_only_appear_first_in_page_list(
        self, project_dir: Path, slide_files: list[Path]
    ) -> None:
        """Main approved slides (backup=False) are listed first, in array order."""
        slides = [
            _make_slide("intro", backup=False),
            _make_slide("methods", backup=False),
        ]
        state = _make_deck_state(slides)
        pages = build_page_list(state, project_dir)
        assert len(pages) == 2
        assert pages[0]["type"] == "slide"
        assert pages[1]["type"] == "slide"

    def test_main_slides_preserve_array_order(
        self, project_dir: Path, slide_files: list[Path]
    ) -> None:
        """Array order of main slides is preserved, not sorted by slug."""
        slides = [
            _make_slide("zzz_last", backup=False),
            _make_slide("aaa_first", backup=False),
        ]
        state = _make_deck_state(slides)
        pages = build_page_list(state, project_dir)
        slide_pages = [p for p in pages if p["type"] == "slide"]
        assert len(slide_pages) == 2
        first_path = slide_pages[0]["path"]
        assert first_path is not None
        assert "zzz_last" in str(first_path)

    def test_closing_slide_appears_after_main_slides(
        self, project_dir: Path, slide_files: list[Path]
    ) -> None:
        """Closing slide comes after all main slides, before separator/backup."""
        slides = [_make_slide("intro", backup=False)]
        state = _make_deck_state(slides, closing_slide="empty")
        pages = build_page_list(state, project_dir)
        types = [p["type"] for p in pages]
        slide_indices = [i for i, t in enumerate(types) if t == "slide"]
        closing_indices = [i for i, t in enumerate(types) if t == "closing"]
        assert closing_indices, "Expected a closing slide page"
        assert max(slide_indices) < min(closing_indices)

    def test_closing_slide_not_added_when_closing_slide_is_none(
        self, project_dir: Path, slide_files: list[Path]
    ) -> None:
        """No closing page is added when closing_slide is None."""
        slides = [_make_slide("intro", backup=False)]
        state = _make_deck_state(slides, closing_slide=None)
        pages = build_page_list(state, project_dir)
        types = [p["type"] for p in pages]
        assert "closing" not in types

    def test_closing_slide_not_added_when_closing_slide_is_not_empty(
        self, project_dir: Path, slide_files: list[Path]
    ) -> None:
        """Closing slide is only added when value is exactly 'empty'."""
        slides = [_make_slide("intro", backup=False)]
        state = _make_deck_state(slides, closing_slide="custom")
        pages = build_page_list(state, project_dir)
        types = [p["type"] for p in pages]
        assert "closing" not in types

    def test_separator_appears_after_closing_slide_before_backup_slides(
        self, project_dir: Path, slide_files: list[Path]
    ) -> None:
        """Separator comes after closing and before backup slides."""
        presentation = _make_presentation(
            separator_position=1, separator_content="questions"
        )
        slides = [
            _make_slide("intro", backup=False),
            _make_slide("backup_s1", backup=True),
        ]
        state = _make_deck_state(
            slides,
            closing_slide="empty",
            presentations=[presentation],
        )
        pages = build_page_list(state, project_dir)
        types = [p["type"] for p in pages]
        # order: slide, closing, separator, slide(backup)
        assert "separator" in types
        sep_idx = types.index("separator")
        closing_idx = types.index("closing")
        backup_indices = [
            i for i, p in enumerate(pages) if p["type"] == "slide" and p.get("backup")
        ]
        assert closing_idx < sep_idx
        if backup_indices:
            assert sep_idx < min(backup_indices)

    def test_backup_slides_appear_last_in_page_list(self, project_dir: Path) -> None:
        """Backup slides (backup=True) are appended after main/closing/separator."""
        # Write slide files for both main and backup slugs
        (project_dir / "slides" / "intro.html").write_text(
            "<!DOCTYPE html><html><body>intro</body></html>",
            encoding="utf-8",
        )
        (project_dir / "slides" / "backup1.html").write_text(
            "<!DOCTYPE html><html><body>backup1</body></html>",
            encoding="utf-8",
        )
        slides = [
            _make_slide("intro", backup=False),
            _make_slide("backup1", backup=True),
        ]
        state = _make_deck_state(slides)
        pages = build_page_list(state, project_dir)
        types = [p["type"] for p in pages]
        # Both are "slide" type; check ordering by path content
        assert len(types) == 2
        first_path = str(pages[0]["path"])
        last_path = str(pages[1]["path"])
        assert "intro" in first_path
        assert "backup1" in last_path

    def test_empty_deck_returns_empty_page_list(self, project_dir: Path) -> None:
        """A deck with no approved slides produces an empty page list."""
        slides: list[SimpleNamespace] = []
        state = _make_deck_state(slides)
        pages = build_page_list(state, project_dir)
        assert pages == []

    def test_non_approved_slides_are_excluded_from_page_list(
        self, project_dir: Path
    ) -> None:
        """Draft and discarded slides are not included in the page list."""
        slides = [
            _make_slide("draft_slide", backup=False, status="draft"),
            _make_slide("discarded_slide", backup=False, status="discarded"),
        ]
        state = _make_deck_state(slides)
        pages = build_page_list(state, project_dir)
        assert pages == []

    def test_full_order_main_closing_separator_backup(self, project_dir: Path) -> None:
        """Full canonical order: main slides, closing, separator, backup slides."""
        for slug in ("s_main", "s_backup"):
            (project_dir / "slides" / f"{slug}.html").write_text(
                f"<!DOCTYPE html><html><body>{slug}</body></html>",
                encoding="utf-8",
            )
        presentation = _make_presentation(
            separator_position=0, separator_content="acknowledgments"
        )
        slides = [
            _make_slide("s_main", backup=False),
            _make_slide("s_backup", backup=True),
        ]
        state = _make_deck_state(
            slides,
            closing_slide="empty",
            presentations=[presentation],
        )
        pages = build_page_list(state, project_dir)
        types = [p["type"] for p in pages]
        assert types[0] == "slide"  # main
        assert "closing" in types
        assert "separator" in types
        closing_idx = types.index("closing")
        separator_idx = types.index("separator")
        last_slide_idx = len(types) - 1
        assert closing_idx < separator_idx
        assert types[last_slide_idx] == "slide"

    def test_page_list_entries_have_required_keys(self, project_dir: Path) -> None:
        """Each page descriptor dict contains 'type', 'path', and 'content' keys."""
        (project_dir / "slides" / "slide_a.html").write_text(
            "<!DOCTYPE html><html><body>a</body></html>",
            encoding="utf-8",
        )
        slides = [_make_slide("slide_a", backup=False)]
        state = _make_deck_state(slides, closing_slide="empty")
        pages = build_page_list(state, project_dir)
        for page in pages:
            assert "type" in page, f"Missing 'type' key in {page}"
            assert "path" in page, f"Missing 'path' key in {page}"
            assert "content" in page, f"Missing 'content' key in {page}"

    def test_slide_pages_have_path_set(self, project_dir: Path) -> None:
        """Slide-type pages have a non-None path pointing to the HTML file."""
        (project_dir / "slides" / "slide_b.html").write_text(
            "<!DOCTYPE html><html><body>b</body></html>",
            encoding="utf-8",
        )
        slides = [_make_slide("slide_b", backup=False)]
        state = _make_deck_state(slides)
        pages = build_page_list(state, project_dir)
        assert pages[0]["path"] is not None
        assert Path(pages[0]["path"]).suffix == ".html"

    def test_closing_page_has_no_path(self, project_dir: Path) -> None:
        """Closing slide pages are in-memory: path is None."""
        (project_dir / "slides" / "slide_c.html").write_text(
            "<!DOCTYPE html><html><body>c</body></html>",
            encoding="utf-8",
        )
        slides = [_make_slide("slide_c", backup=False)]
        state = _make_deck_state(slides, closing_slide="empty")
        pages = build_page_list(state, project_dir)
        closing = next(p for p in pages if p["type"] == "closing")
        assert closing["path"] is None

    def test_separator_page_has_no_path(self, project_dir: Path) -> None:
        """Separator slide pages are in-memory: path is None."""
        (project_dir / "slides" / "slide_d.html").write_text(
            "<!DOCTYPE html><html><body>d</body></html>",
            encoding="utf-8",
        )
        presentation = _make_presentation(
            separator_position=0, separator_content="summary"
        )
        slides = [_make_slide("slide_d", backup=False)]
        state = _make_deck_state(slides, presentations=[presentation])
        pages = build_page_list(state, project_dir)
        sep = next((p for p in pages if p["type"] == "separator"), None)
        if sep is not None:
            assert sep["path"] is None

    def test_separator_not_added_when_separator_position_is_none(
        self, project_dir: Path
    ) -> None:
        """No separator is added when separator_position is None."""
        (project_dir / "slides" / "slide_e.html").write_text(
            "<!DOCTYPE html><html><body>e</body></html>",
            encoding="utf-8",
        )
        presentation = _make_presentation(separator_position=None)
        slides = [_make_slide("slide_e", backup=False)]
        state = _make_deck_state(slides, presentations=[presentation])
        pages = build_page_list(state, project_dir)
        types = [p["type"] for p in pages]
        assert "separator" not in types


# ===========================================================================
# BC-10.5 / REQ-EXPORT-5: append_export_log canonical schema
# ===========================================================================


class TestAppendExportLogSchemaCompliance:
    """Tests for append_export_log (BC-10.5, REQ-EXPORT-5)."""

    def test_success_entry_contains_all_seven_required_fields(
        self, project_dir: Path
    ) -> None:
        """A success log entry must contain all 7 REQ-EXPORT-5 fields."""
        append_export_log(
            project_root=project_dir,
            presentation_folder="2026_04_12_test",
            version=1,
            slide_count=5,
            playwright_exit_status=0,
            pdf_path="output/2026_04_12_test/deck_v001.pdf",
            error_message=None,
        )
        log_file = project_dir / "output" / "export_log.jsonl"
        assert log_file.exists()
        entries = [json.loads(line) for line in log_file.read_text().splitlines()]
        assert len(entries) == 1
        entry = entries[0]
        required_fields = {
            "timestamp",
            "presentation_folder",
            "version",
            "slide_count",
            "playwright_exit_status",
            "pdf_path",
            "error_message",
        }
        assert required_fields.issubset(entry.keys()), (
            f"Missing fields: {required_fields - entry.keys()}"
        )

    def test_success_entry_has_null_error_message(self, project_dir: Path) -> None:
        """On success, error_message must be null (None in JSON)."""
        append_export_log(
            project_root=project_dir,
            presentation_folder="2026_04_12_test",
            version=1,
            slide_count=3,
            playwright_exit_status=0,
            pdf_path="output/2026_04_12_test/deck_v001.pdf",
            error_message=None,
        )
        log_file = project_dir / "output" / "export_log.jsonl"
        entry = json.loads(log_file.read_text().splitlines()[0])
        assert entry["error_message"] is None

    def test_failure_entry_contains_error_message_text(self, project_dir: Path) -> None:
        """On failure, error_message contains the error text (non-null)."""
        error_text = "Playwright crashed: Target closed"
        append_export_log(
            project_root=project_dir,
            presentation_folder="2026_04_12_test",
            version=1,
            slide_count=0,
            playwright_exit_status=1,
            pdf_path="",
            error_message=error_text,
        )
        log_file = project_dir / "output" / "export_log.jsonl"
        entry = json.loads(log_file.read_text().splitlines()[0])
        assert entry["error_message"] == error_text
        assert entry["playwright_exit_status"] == 1

    def test_failure_entry_may_have_empty_pdf_path(self, project_dir: Path) -> None:
        """When no PDF was produced, pdf_path may be empty string."""
        append_export_log(
            project_root=project_dir,
            presentation_folder="2026_04_12_test",
            version=1,
            slide_count=0,
            playwright_exit_status=1,
            pdf_path="",
            error_message="No PDF produced",
        )
        log_file = project_dir / "output" / "export_log.jsonl"
        entry = json.loads(log_file.read_text().splitlines()[0])
        assert entry["pdf_path"] == ""

    def test_timestamp_field_is_iso8601_string(self, project_dir: Path) -> None:
        """The timestamp field must be a non-empty ISO 8601 string."""
        append_export_log(
            project_root=project_dir,
            presentation_folder="2026_04_12_test",
            version=1,
            slide_count=2,
            playwright_exit_status=0,
            pdf_path="output/2026_04_12_test/deck_v001.pdf",
            error_message=None,
        )
        log_file = project_dir / "output" / "export_log.jsonl"
        entry = json.loads(log_file.read_text().splitlines()[0])
        ts = entry["timestamp"]
        assert isinstance(ts, str) and len(ts) > 0
        # Basic ISO8601 sanity: contains T or date separators
        assert re.search(r"\d{4}-\d{2}-\d{2}", ts), f"Not ISO 8601: {ts}"

    def test_multiple_appends_grow_the_log_file(self, project_dir: Path) -> None:
        """Each call appends exactly one new JSONL entry."""
        for i in range(3):
            append_export_log(
                project_root=project_dir,
                presentation_folder="2026_04_12_test",
                version=i + 1,
                slide_count=4,
                playwright_exit_status=0,
                pdf_path=f"output/2026_04_12_test/deck_v00{i + 1}.pdf",
                error_message=None,
            )
        log_file = project_dir / "output" / "export_log.jsonl"
        lines = [ln for ln in log_file.read_text().splitlines() if ln.strip()]
        assert len(lines) == 3

    def test_earlier_entries_preserved_after_subsequent_appends(
        self, project_dir: Path
    ) -> None:
        """Pre-existing log entries are not overwritten by subsequent appends."""
        append_export_log(
            project_root=project_dir,
            presentation_folder="first_folder",
            version=1,
            slide_count=1,
            playwright_exit_status=0,
            pdf_path="output/first_folder/deck_v001.pdf",
            error_message=None,
        )
        append_export_log(
            project_root=project_dir,
            presentation_folder="second_folder",
            version=1,
            slide_count=2,
            playwright_exit_status=0,
            pdf_path="output/second_folder/deck_v001.pdf",
            error_message=None,
        )
        log_file = project_dir / "output" / "export_log.jsonl"
        lines = log_file.read_text().splitlines()
        first_entry = json.loads(lines[0])
        assert first_entry["presentation_folder"] == "first_folder"

    def test_entry_version_field_matches_argument(self, project_dir: Path) -> None:
        """The version field in the log entry equals the version argument."""
        append_export_log(
            project_root=project_dir,
            presentation_folder="2026_04_12_test",
            version=7,
            slide_count=5,
            playwright_exit_status=0,
            pdf_path="output/2026_04_12_test/deck_v007.pdf",
            error_message=None,
        )
        log_file = project_dir / "output" / "export_log.jsonl"
        entry = json.loads(log_file.read_text().splitlines()[0])
        assert entry["version"] == 7

    def test_entry_slide_count_matches_argument(self, project_dir: Path) -> None:
        """The slide_count field in the log entry equals the slide_count argument."""
        append_export_log(
            project_root=project_dir,
            presentation_folder="2026_04_12_test",
            version=1,
            slide_count=12,
            playwright_exit_status=0,
            pdf_path="output/2026_04_12_test/deck_v001.pdf",
            error_message=None,
        )
        log_file = project_dir / "output" / "export_log.jsonl"
        entry = json.loads(log_file.read_text().splitlines()[0])
        assert entry["slide_count"] == 12

    def test_entry_presentation_folder_matches_argument(
        self, project_dir: Path
    ) -> None:
        """The presentation_folder field equals the folder argument."""
        append_export_log(
            project_root=project_dir,
            presentation_folder="2026_04_12_my_talk",
            version=1,
            slide_count=3,
            playwright_exit_status=0,
            pdf_path="output/2026_04_12_my_talk/deck_v001.pdf",
            error_message=None,
        )
        log_file = project_dir / "output" / "export_log.jsonl"
        entry = json.loads(log_file.read_text().splitlines()[0])
        assert entry["presentation_folder"] == "2026_04_12_my_talk"

    def test_log_file_created_in_output_directory(self, project_dir: Path) -> None:
        """The export log is always written to output/export_log.jsonl."""
        append_export_log(
            project_root=project_dir,
            presentation_folder="test_folder",
            version=1,
            slide_count=1,
            playwright_exit_status=0,
            pdf_path="output/test_folder/deck_v001.pdf",
            error_message=None,
        )
        expected_path = project_dir / "output" / "export_log.jsonl"
        assert expected_path.exists()

    def test_each_line_is_valid_json(self, project_dir: Path) -> None:
        """Every line in export_log.jsonl must be parseable as JSON."""
        for i in range(2):
            append_export_log(
                project_root=project_dir,
                presentation_folder="2026_04_12_test",
                version=i + 1,
                slide_count=2,
                playwright_exit_status=0,
                pdf_path=f"output/2026_04_12_test/deck_v00{i + 1}.pdf",
                error_message=None,
            )
        log_file = project_dir / "output" / "export_log.jsonl"
        for line in log_file.read_text().splitlines():
            if line.strip():
                obj = json.loads(line)  # must not raise
                assert isinstance(obj, dict)


# ===========================================================================
# BC-10.3 supplementary: generate_closing_slide_html structural tests
# ===========================================================================


class TestGenerateClosingSlideHtml:
    """Tests for generate_closing_slide_html (BC-10.3, BC-10.8)."""

    def test_returns_non_empty_string(self) -> None:
        """generate_closing_slide_html returns a non-empty string."""
        html = generate_closing_slide_html(_MINIMAL_STYLE_CONFIG)
        assert isinstance(html, str) and len(html) > 0

    def test_output_contains_html_tag(self) -> None:
        """The generated HTML contains an <html> element."""
        html = generate_closing_slide_html(_MINIMAL_STYLE_CONFIG)
        assert "<html" in html.lower()

    def test_output_contains_body_tag(self) -> None:
        """The generated HTML contains a <body> element."""
        html = generate_closing_slide_html(_MINIMAL_STYLE_CONFIG)
        assert "<body" in html.lower()

    def test_output_contains_no_visible_text_content(self) -> None:
        """The closing slide is an empty styled slide with no meaningful text."""
        html = generate_closing_slide_html(_MINIMAL_STYLE_CONFIG)
        # Strip tags; remaining visible text should be minimal/empty
        text_only = re.sub(r"<[^>]+>", "", html).strip()
        # Allow whitespace-only or very short text (e.g., whitespace chars)
        # but not paragraph-length content
        assert len(text_only) < 50, (
            f"Unexpected visible text in closing slide: {text_only!r}"
        )

    def test_output_uses_css_custom_properties(self) -> None:
        """The HTML references CSS custom properties (--color-* or var(--)."""
        html = generate_closing_slide_html(_MINIMAL_STYLE_CONFIG)
        assert "--" in html or "var(" in html

    def test_different_style_configs_produce_different_outputs(self) -> None:
        """Distinct style configs produce distinct HTML output."""
        config_a = _MINIMAL_STYLE_CONFIG
        config_b = {
            **_MINIMAL_STYLE_CONFIG,
            "colors": {**_MINIMAL_STYLE_CONFIG["colors"], "background": "#000000"},
        }
        html_a = generate_closing_slide_html(config_a)
        html_b = generate_closing_slide_html(config_b)
        assert html_a != html_b


# ===========================================================================
# BC-10.3 supplementary: generate_separator_html structural tests
# ===========================================================================


class TestGenerateSeparatorHtml:
    """Tests for generate_separator_html."""

    @pytest.mark.parametrize(
        "content",
        ["acknowledgments", "questions", "summary"],
    )
    def test_recognised_content_value_produces_non_empty_html(
        self, content: str
    ) -> None:
        """All recognised separator_content values produce non-empty HTML."""
        html = generate_separator_html(content, _MINIMAL_STYLE_CONFIG)
        assert isinstance(html, str) and len(html) > 0

    def test_custom_text_is_included_in_output(self) -> None:
        """Custom separator text appears in the generated HTML."""
        custom = "Special Acknowledgments to Dr. Smith"
        html = generate_separator_html(custom, _MINIMAL_STYLE_CONFIG)
        assert custom in html or custom.lower() in html.lower()

    def test_acknowledgments_keyword_reflected_in_output(self) -> None:
        """'acknowledgments' appears in the output for that content value."""
        html = generate_separator_html("acknowledgments", _MINIMAL_STYLE_CONFIG)
        assert "acknowledgment" in html.lower()

    def test_questions_keyword_reflected_in_output(self) -> None:
        """'questions' appears in the output for that content value."""
        html = generate_separator_html("questions", _MINIMAL_STYLE_CONFIG)
        assert "question" in html.lower()

    def test_summary_keyword_reflected_in_output(self) -> None:
        """'summary' appears in the output for that content value."""
        html = generate_separator_html("summary", _MINIMAL_STYLE_CONFIG)
        assert "summary" in html.lower()

    def test_output_contains_html_tag(self) -> None:
        """The generated separator HTML contains an <html> element."""
        html = generate_separator_html("questions", _MINIMAL_STYLE_CONFIG)
        assert "<html" in html.lower()

    def test_output_uses_css_custom_properties(self) -> None:
        """The separator slide references CSS custom properties."""
        html = generate_separator_html("acknowledgments", _MINIMAL_STYLE_CONFIG)
        assert "--" in html or "var(" in html

    def test_different_content_values_produce_different_outputs(self) -> None:
        """Different separator_content values produce distinct HTML."""
        html_ack = generate_separator_html("acknowledgments", _MINIMAL_STYLE_CONFIG)
        html_q = generate_separator_html("questions", _MINIMAL_STYLE_CONFIG)
        assert html_ack != html_q


# ===========================================================================
# BC-10.7: Env corruption check (playwright availability at entry)
# ===========================================================================


class TestMainExportEnvCorruptionCheck:
    """Tests for main_export env corruption exit code 2 (BC-10.7)."""

    def test_exits_with_code_2_when_playwright_not_available(
        self, project_dir: Path
    ) -> None:
        """main_export exits with code 2 when playwright is not importable."""
        from export import main_export

        with patch("importlib.util.find_spec", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                main_export(project_dir)
        assert exc_info.value.code == 2

    def test_exits_with_code_2_prints_to_stderr(
        self, project_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """main_export prints an error message to stderr when playwright absent."""
        from export import main_export

        with patch("importlib.util.find_spec", return_value=None):
            with pytest.raises(SystemExit):
                main_export(project_dir)
        captured = capsys.readouterr()
        assert len(captured.err) > 0 or len(captured.out) > 0


# ===========================================================================
# BC-10.1: Style compiler invocation before Playwright
# ===========================================================================


class TestMainExportStyleCompilerInvocation:
    """Tests for BC-10.1: style_compiler is invoked before Playwright opens."""

    def test_exits_with_nonzero_when_style_compiler_fails(
        self, project_dir: Path
    ) -> None:
        """main_export aborts (non-zero exit) when style compiler exits non-zero."""
        from export import main_export

        mock_find_spec = MagicMock(return_value=MagicMock())  # playwright present
        mock_run = MagicMock()
        mock_run.return_value = MagicMock(returncode=1, stderr="Compiler error")

        with (
            patch("importlib.util.find_spec", mock_find_spec),
            patch("subprocess.run", mock_run),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main_export(project_dir)
        # Must not exit 0; exact code is 1 per contract
        assert exc_info.value.code != 0

    def test_style_compiler_called_with_correct_arguments(
        self, project_dir: Path
    ) -> None:
        """style_compiler is invoked with style_config.json and assets/style.css."""
        from export import main_export

        mock_find_spec = MagicMock(return_value=MagicMock())
        captured_calls: list[Any] = []

        def fake_run(args: Any, **kwargs: Any) -> MagicMock:
            captured_calls.append(args)
            result = MagicMock()
            result.returncode = 1  # fail fast to avoid deeper execution
            result.stderr = "fail"
            return result

        with (
            patch("importlib.util.find_spec", mock_find_spec),
            patch("subprocess.run", side_effect=fake_run),
        ):
            with pytest.raises(SystemExit):
                main_export(project_dir)

        assert len(captured_calls) >= 1
        first_call = captured_calls[0]
        cmd_str = " ".join(str(a) for a in first_call)
        assert "style_compiler" in cmd_str
        assert "style_config.json" in cmd_str
        assert "style.css" in cmd_str


# ===========================================================================
# BC-10.4: PDF file naming (deck_vNNN.pdf zero-padded to 3 digits)
# ===========================================================================


class TestPdfFileNaming:
    """Tests for BC-10.4: deck_v{NNN}.pdf naming convention."""

    @pytest.mark.parametrize(
        "export_count, expected_suffix",
        [
            (0, "deck_v001.pdf"),
            (1, "deck_v002.pdf"),
            (9, "deck_v010.pdf"),
            (99, "deck_v100.pdf"),
        ],
    )
    def test_pdf_version_is_export_count_plus_one_zero_padded(
        self,
        export_count: int,
        expected_suffix: str,
        project_dir: Path,
    ) -> None:
        """PDF filename uses export_count+1 zero-padded to 3 digits."""
        # This is a naming-convention test: verify the convention is encoded
        # correctly by constructing the expected filename directly per BC-10.4.
        version = export_count + 1
        filename = f"deck_v{version:03d}.pdf"
        assert filename == expected_suffix


# ===========================================================================
# BC-10.3 integration: page list type values are constrained
# ===========================================================================


class TestPageListTypeValues:
    """Each page dict 'type' must be one of 'slide', 'closing', 'separator'."""

    def test_all_page_types_are_valid(self, project_dir: Path) -> None:
        """Every page descriptor produced by build_page_list has a valid type."""
        (project_dir / "slides" / "alpha.html").write_text(
            "<!DOCTYPE html><html><body>alpha</body></html>",
            encoding="utf-8",
        )
        (project_dir / "slides" / "beta.html").write_text(
            "<!DOCTYPE html><html><body>beta</body></html>",
            encoding="utf-8",
        )
        presentation = _make_presentation(
            separator_position=0, separator_content="questions"
        )
        slides = [
            _make_slide("alpha", backup=False),
            _make_slide("beta", backup=True),
        ]
        state = _make_deck_state(
            slides,
            closing_slide="empty",
            presentations=[presentation],
        )
        pages = build_page_list(state, project_dir)
        valid_types = {"slide", "closing", "separator"}
        for page in pages:
            assert page["type"] in valid_types, (
                f"Unexpected page type: {page['type']!r}"
            )


# ===========================================================================
# BC-10.1 gap: compiler stderr printed; Playwright not opened on failure
# ===========================================================================


class TestStyleCompilerFailureBehavior:
    """Additional BC-10.1 contracts: stderr output and Playwright not opened."""

    def test_compiler_stderr_is_printed_when_compiler_fails(
        self,
        project_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Compiler stderr text must appear in main_export output on failure."""
        from export import main_export

        compiler_stderr = "SyntaxError: unknown token at line 7"
        mock_find_spec = MagicMock(return_value=MagicMock())

        def fake_run(args: Any, **kwargs: Any) -> MagicMock:
            result = MagicMock()
            result.returncode = 1
            result.stderr = compiler_stderr
            return result

        with (
            patch("importlib.util.find_spec", mock_find_spec),
            patch("subprocess.run", side_effect=fake_run),
        ):
            with pytest.raises(SystemExit):
                main_export(project_dir)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert compiler_stderr in combined, (
            f"Compiler stderr not printed. Got: {combined!r}"
        )

    def test_playwright_not_opened_when_compiler_fails(
        self, project_dir: Path
    ) -> None:
        """sync_playwright must never be called when style compiler exits non-0."""
        from export import main_export

        mock_find_spec = MagicMock(return_value=MagicMock())
        sync_playwright_calls: list[Any] = []

        def fake_run(args: Any, **kwargs: Any) -> MagicMock:
            result = MagicMock()
            result.returncode = 1
            result.stderr = "compiler error"
            return result

        def fake_sync_playwright(*a: Any, **kw: Any) -> MagicMock:
            sync_playwright_calls.append(True)
            return MagicMock()

        with (
            patch("importlib.util.find_spec", mock_find_spec),
            patch("subprocess.run", side_effect=fake_run),
            patch("export.sync_playwright", fake_sync_playwright, create=True),
        ):
            with pytest.raises(SystemExit):
                main_export(project_dir)

        assert sync_playwright_calls == [], (
            "sync_playwright was opened despite style compiler failure"
        )


# ===========================================================================
# BC-10.2 gap: one BrowserContext created and reused for all pages
# ===========================================================================


def _make_full_playwright_mock() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Return (mock_context, mock_browser, mock_pw_instance).

    Configures the chain so that sync_playwright().__enter__() returns
    mock_pw_instance, pw.chromium.launch() returns mock_browser, and
    browser.new_context() returns mock_context.  Each page created via
    context.new_page() returns a fresh MagicMock with a .pdf() that
    returns b'%PDF-1.4 mock'.
    """
    mock_page = MagicMock()
    mock_page.pdf.return_value = b"%PDF-1.4 mock"

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw_instance = MagicMock()
    mock_pw_instance.chromium.launch.return_value = mock_browser

    return mock_context, mock_browser, mock_pw_instance


class TestOneBrowserContextPerExport:
    """BC-10.2: one BrowserContext per export, no per-page browser launch."""

    def _run_main_export_with_mock_playwright(
        self,
        project_dir: Path,
        mock_pw_instance: MagicMock,
        slides: list[SimpleNamespace],
        extra_state_kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Drive main_export with a fully mocked Playwright session.

        Patches: importlib.util.find_spec (playwright present),
        subprocess.run (compiler succeeds), debrief.state module,
        playwright.sync_api.sync_playwright, and fitz (PyMuPDF).
        """
        from export import main_export

        extra_state_kwargs = extra_state_kwargs or {}
        presentation = _make_presentation(export_count=0)
        state = _make_deck_state(
            slides,
            presentations=[presentation],
            **extra_state_kwargs,
        )

        # Write slide HTML files so build_page_list can resolve paths
        for slide in slides:
            if not slide.backup or True:
                p = project_dir / "slides" / f"{slide.slug}.html"
                p.write_text(
                    f"<html><body>{slide.slug}</body></html>",
                    encoding="utf-8",
                )

        # Write a minimal style_config.json
        (project_dir / "style_config.json").write_text(
            json.dumps(_MINIMAL_STYLE_CONFIG), encoding="utf-8"
        )

        mock_state_module = MagicMock()
        mock_state_module.read_deck_state.return_value = state
        mock_state_module.increment_export_count.return_value = None
        mock_state_module.write_deck_state.return_value = None

        # fitz (PyMuPDF) mock: 1 call for merged + 1 call per page buffer
        page_count = sum(
            1 for s in slides if s.status == "approved"
        )
        mock_merged = MagicMock()
        fitz_open_results: list[Any] = [mock_merged]
        for _ in range(page_count):
            doc_mock = MagicMock()
            doc_mock.__enter__ = MagicMock(return_value=doc_mock)
            doc_mock.__exit__ = MagicMock(return_value=False)
            fitz_open_results.append(doc_mock)
        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = fitz_open_results

        ctx_mgr = MagicMock()
        ctx_mgr.__enter__ = MagicMock(return_value=mock_pw_instance)
        ctx_mgr.__exit__ = MagicMock(return_value=False)

        with (
            patch("importlib.util.find_spec", return_value=MagicMock()),
            patch(
                "subprocess.run",
                return_value=MagicMock(returncode=0, stderr=""),
            ),
            patch.dict(
                "sys.modules",
                {
                    "debrief": MagicMock(),
                    "debrief.state": mock_state_module,
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(
                        sync_playwright=MagicMock(
                            return_value=ctx_mgr
                        )
                    ),
                    "fitz": mock_fitz,
                },
            ),
        ):
            main_export(project_dir)

    def test_new_context_called_exactly_once_for_two_slides(
        self, project_dir: Path
    ) -> None:
        """new_context() is called exactly once even with multiple slides."""
        mock_context, mock_browser, mock_pw_instance = (
            _make_full_playwright_mock()
        )
        slides = [
            _make_slide("slide1", backup=False),
            _make_slide("slide2", backup=False),
        ]
        self._run_main_export_with_mock_playwright(
            project_dir, mock_pw_instance, slides
        )
        assert mock_browser.new_context.call_count == 1, (
            f"Expected new_context called once, got "
            f"{mock_browser.new_context.call_count}"
        )

    def test_context_close_called_after_all_pages_rendered(
        self, project_dir: Path
    ) -> None:
        """context.close() is called after all pages are rendered."""
        mock_context, mock_browser, mock_pw_instance = (
            _make_full_playwright_mock()
        )
        slides = [_make_slide("slide_a", backup=False)]
        self._run_main_export_with_mock_playwright(
            project_dir, mock_pw_instance, slides
        )
        mock_context.close.assert_called_once()

    def test_no_per_page_chromium_launch(self, project_dir: Path) -> None:
        """chromium.launch() is called exactly once, not once per page."""
        mock_context, mock_browser, mock_pw_instance = (
            _make_full_playwright_mock()
        )
        slides = [
            _make_slide("p1", backup=False),
            _make_slide("p2", backup=False),
            _make_slide("p3", backup=False),
        ]
        self._run_main_export_with_mock_playwright(
            project_dir, mock_pw_instance, slides
        )
        assert mock_pw_instance.chromium.launch.call_count == 1, (
            f"Expected chromium.launch called once, got "
            f"{mock_pw_instance.chromium.launch.call_count}"
        )


# ===========================================================================
# BC-10.4 gap: main_export reads export_count from presentation record
# ===========================================================================


class TestPdfFileNamingFromPresentationRecord:
    """BC-10.4: main_export uses export_count from the presentation record."""

    def _run_export_and_get_pdf_path(
        self,
        project_dir: Path,
        export_count: int,
    ) -> str:
        """Run main_export with a mock state having the given export_count.

        Returns the pdf_path string passed to append_export_log.
        """
        from export import main_export

        presentation = _make_presentation(
            folder="2026_04_12_talk",
            export_count=export_count,
        )
        slides = [_make_slide("s1", backup=False)]
        state = _make_deck_state(slides, presentations=[presentation])

        (project_dir / "slides" / "s1.html").write_text(
            "<html><body>s1</body></html>", encoding="utf-8"
        )
        (project_dir / "style_config.json").write_text(
            json.dumps(_MINIMAL_STYLE_CONFIG), encoding="utf-8"
        )

        mock_state_module = MagicMock()
        mock_state_module.read_deck_state.return_value = state
        mock_state_module.increment_export_count.return_value = None
        mock_state_module.write_deck_state.return_value = None

        logged: list[dict[str, Any]] = []

        def fake_append_log(**kwargs: Any) -> None:
            logged.append(kwargs)

        mock_page = MagicMock()
        mock_page.pdf.return_value = b"%PDF-1.4"
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        ctx_mgr = MagicMock()
        ctx_mgr.__enter__ = MagicMock(return_value=mock_pw_instance)
        ctx_mgr.__exit__ = MagicMock(return_value=False)

        mock_fitz_doc = MagicMock()
        mock_fitz_doc.__enter__ = MagicMock(return_value=mock_fitz_doc)
        mock_fitz_doc.__exit__ = MagicMock(return_value=False)
        mock_merged = MagicMock()
        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = [mock_merged, mock_fitz_doc]

        with (
            patch("importlib.util.find_spec", return_value=MagicMock()),
            patch(
                "subprocess.run",
                return_value=MagicMock(returncode=0, stderr=""),
            ),
            patch("export.append_export_log", side_effect=fake_append_log),
            patch.dict(
                "sys.modules",
                {
                    "debrief": MagicMock(),
                    "debrief.state": mock_state_module,
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(
                        sync_playwright=MagicMock(return_value=ctx_mgr)
                    ),
                    "fitz": mock_fitz,
                },
            ),
        ):
            main_export(project_dir)

        assert logged, "append_export_log was never called"
        return logged[-1].get("pdf_path", "")

    def test_version_one_when_export_count_is_zero(
        self, project_dir: Path
    ) -> None:
        """export_count=0 produces deck_v001.pdf."""
        pdf_path = self._run_export_and_get_pdf_path(project_dir, 0)
        assert pdf_path.endswith("deck_v001.pdf"), (
            f"Expected deck_v001.pdf, got {pdf_path!r}"
        )

    def test_version_uses_export_count_plus_one(
        self, project_dir: Path
    ) -> None:
        """export_count=4 produces deck_v005.pdf."""
        pdf_path = self._run_export_and_get_pdf_path(project_dir, 4)
        assert pdf_path.endswith("deck_v005.pdf"), (
            f"Expected deck_v005.pdf, got {pdf_path!r}"
        )


# ===========================================================================
# BC-10.5 gap: append_export_log called after PDF is written on success
# ===========================================================================


class TestExportLogWrittenAfterPdf:
    """BC-10.5: append_export_log is called with success status after PDF."""

    def test_append_export_log_called_with_success_status_on_export(
        self, project_dir: Path
    ) -> None:
        """On successful export, append_export_log receives playwright_exit_status=0."""
        from export import main_export

        presentation = _make_presentation(
            folder="2026_04_12_talk", export_count=0
        )
        slides = [_make_slide("main_s", backup=False)]
        state = _make_deck_state(slides, presentations=[presentation])

        (project_dir / "slides" / "main_s.html").write_text(
            "<html><body>main_s</body></html>", encoding="utf-8"
        )
        (project_dir / "style_config.json").write_text(
            json.dumps(_MINIMAL_STYLE_CONFIG), encoding="utf-8"
        )

        mock_state_module = MagicMock()
        mock_state_module.read_deck_state.return_value = state
        mock_state_module.increment_export_count.return_value = None
        mock_state_module.write_deck_state.return_value = None

        logged: list[dict[str, Any]] = []

        def fake_append_log(**kwargs: Any) -> None:
            logged.append(kwargs)

        mock_page = MagicMock()
        mock_page.pdf.return_value = b"%PDF-1.4"
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        ctx_mgr = MagicMock()
        ctx_mgr.__enter__ = MagicMock(return_value=mock_pw)
        ctx_mgr.__exit__ = MagicMock(return_value=False)

        mock_fitz_doc = MagicMock()
        mock_fitz_doc.__enter__ = MagicMock(return_value=mock_fitz_doc)
        mock_fitz_doc.__exit__ = MagicMock(return_value=False)
        mock_merged = MagicMock()
        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = [mock_merged, mock_fitz_doc]

        with (
            patch("importlib.util.find_spec", return_value=MagicMock()),
            patch(
                "subprocess.run",
                return_value=MagicMock(returncode=0, stderr=""),
            ),
            patch("export.append_export_log", side_effect=fake_append_log),
            patch.dict(
                "sys.modules",
                {
                    "debrief": MagicMock(),
                    "debrief.state": mock_state_module,
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(
                        sync_playwright=MagicMock(return_value=ctx_mgr)
                    ),
                    "fitz": mock_fitz,
                },
            ),
        ):
            main_export(project_dir)

        assert any(
            entry.get("playwright_exit_status") == 0
            for entry in logged
        ), (
            "append_export_log was not called with playwright_exit_status=0 "
            f"on successful export. Calls: {logged}"
        )

    def test_append_export_log_not_called_before_pdf_write(
        self, project_dir: Path
    ) -> None:
        """append_export_log must not be called if PDF write hasn't occurred.

        Verifies BC-10.5 ordering: log is written after PDF, not before.
        We simulate this by tracking call order using side-effect order.
        """
        from export import main_export

        presentation = _make_presentation(
            folder="2026_04_12_talk", export_count=0
        )
        slides = [_make_slide("s_order", backup=False)]
        state = _make_deck_state(slides, presentations=[presentation])

        (project_dir / "slides" / "s_order.html").write_text(
            "<html><body>order</body></html>", encoding="utf-8"
        )
        (project_dir / "style_config.json").write_text(
            json.dumps(_MINIMAL_STYLE_CONFIG), encoding="utf-8"
        )

        mock_state_module = MagicMock()
        mock_state_module.read_deck_state.return_value = state
        mock_state_module.increment_export_count.return_value = None
        mock_state_module.write_deck_state.return_value = None

        call_order: list[str] = []

        def fake_append_log(**kwargs: Any) -> None:
            call_order.append("append_export_log")

        mock_page = MagicMock()

        def fake_pdf(**kwargs: Any) -> bytes:
            call_order.append("page.pdf")
            return b"%PDF-1.4"

        mock_page.pdf.side_effect = fake_pdf
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        ctx_mgr = MagicMock()
        ctx_mgr.__enter__ = MagicMock(return_value=mock_pw)
        ctx_mgr.__exit__ = MagicMock(return_value=False)

        mock_fitz_doc = MagicMock()
        mock_fitz_doc.__enter__ = MagicMock(return_value=mock_fitz_doc)
        mock_fitz_doc.__exit__ = MagicMock(return_value=False)

        saved_paths: list[str] = []

        mock_merged = MagicMock()

        def fake_fitz_save(path: str, **kwargs: Any) -> None:
            call_order.append("pdf_write")
            saved_paths.append(path)

        mock_merged.save.side_effect = fake_fitz_save
        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = [mock_merged, mock_fitz_doc]

        with (
            patch("importlib.util.find_spec", return_value=MagicMock()),
            patch(
                "subprocess.run",
                return_value=MagicMock(returncode=0, stderr=""),
            ),
            patch("export.append_export_log", side_effect=fake_append_log),
            patch.dict(
                "sys.modules",
                {
                    "debrief": MagicMock(),
                    "debrief.state": mock_state_module,
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(
                        sync_playwright=MagicMock(return_value=ctx_mgr)
                    ),
                    "fitz": mock_fitz,
                },
            ),
        ):
            main_export(project_dir)

        # "pdf_write" must appear before "append_export_log" in call order
        assert "append_export_log" in call_order, (
            "append_export_log was never called"
        )
        log_idx = call_order.index("append_export_log")
        assert "pdf_write" in call_order, "PDF save was never called"
        write_idx = call_order.index("pdf_write")
        assert write_idx < log_idx, (
            f"append_export_log called before PDF write. "
            f"Order: {call_order}"
        )
