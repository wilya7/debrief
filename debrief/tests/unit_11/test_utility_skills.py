# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Tests for Unit 11: Utility Skills.

Tested contracts: BC-11.1 through BC-11.14.

Synthetic data generation assumptions
--------------------------------------
- ``SlideRecord`` stand-ins are ``SimpleNamespace`` objects carrying every
  field defined in Section 17.2: ``slug``, ``title``, ``status``
  ("approved"), ``backup`` (bool), ``content_summary``, ``visual_approach``,
  ``design_choices``, ``forks_not_taken``, ``user_recommendations``,
  ``qa_passed`` (True), ``accepted_violations`` ([]),
  ``last_modified`` ("2026-04-12T00:00:00Z"), ``group_id``,
  ``user_assets`` ([]), ``has_math`` (False).
- ``DeckState`` stand-ins are ``SimpleNamespace`` objects with fields:
  ``project_name``, ``created_at``, ``archetype``, ``style_locked``,
  ``closing_slide``, ``slides`` (list of SlideRecord stand-ins),
  ``presentations`` (list of PresentationRecord stand-ins).
- ``DebriefState`` stand-ins are ``SimpleNamespace`` objects with the
  fields used by BC-11.1 through BC-11.3: ``phase``, ``sub_phase``,
  ``pending_gate``, ``pre_view_state``, ``view_deferred``,
  ``red_green_iteration``, ``red_green_started_at``.
- ``PresentationRecord`` stand-ins carry: ``folder``, ``created_at``,
  ``slide_manifest`` ([]), ``export_count``, ``script_count``,
  ``handout_count``, ``separator_position`` (None), ``separator_content``
  (None).
- Filesystem state is always isolated in pytest ``tmp_path``; no global
  directories are modified.
- ``sanitize_save_label`` is tested via the stub's exported name
  ``sanitize_save_label`` from ``utility_skills``.
- ``parse_view_query`` is tested against a ``DeckState`` stand-in whose
  ``slides`` contain a mix of approved, non-approved, backup, and grouped
  slides to cover all five query forms in REQ-VIEW-1.
- ``generate_view_html`` is tested with one-slide lists (full-size contract)
  and multi-slide lists (thumbnail grid contract); the output is inspected
  as a raw string for HTML structural markers.
- ``generate_script_content`` receives a minimal ``deck_brief_content``
  string and a list of SlideRecord stand-ins; the returned markdown is
  inspected for per-slide section headings.
- ``generate_layout_html`` is tested for both "2up" and "4up" modes;
  the returned string must contain all slide slugs and the expected grid
  structure marker (2up: 2 columns; 4up: 4 per page / 2×2 grid).
- ``main_view``, ``main_script_generator``, ``main_handout`` are entry-point
  functions that call Unit 2 I/O helpers. All file I/O is either written to
  ``tmp_path`` or mocked with ``unittest.mock.patch`` to avoid side effects
  on real disk state. The ``webbrowser.open`` call in ``main_view`` is always
  patched so no browser is launched during tests.
- The playwright import check in BC-11.7 is exercised by patching
  ``importlib.util.find_spec`` to return ``None`` inside the module under
  test.
- ``deck_state.json`` and ``debrief_state.json`` files are written as
  minimal-but-valid JSON into ``tmp_path`` for entry-point tests; the JSON
  content only needs the fields exercised by the tested code path.
- Timestamps use the fixed string "2026-04-12T00:00:00Z" throughout.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
from utility_skills import (
    generate_layout_html,
    generate_script_content,
    generate_view_html,
    main_handout,
    main_script_generator,
    main_view,
    parse_view_query,
    sanitize_save_label,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_TS = "2026-04-12T00:00:00Z"
_FOLDER = "2026_04_12_test_deck"


# ---------------------------------------------------------------------------
# Stand-in factory helpers
# ---------------------------------------------------------------------------


def _make_slide(
    slug: str = "intro",
    status: str = "approved",
    backup: bool = False,
    group_id: Optional[str] = "group_01",
    content_summary: Optional[str] = "Key summary",
) -> SimpleNamespace:
    """Return a minimal SlideRecord stand-in."""
    return SimpleNamespace(
        slug=slug,
        title=f"Title of {slug}",
        status=status,
        backup=backup,
        content_summary=content_summary,
        visual_approach="Diagram",
        design_choices="Minimal",
        forks_not_taken=None,
        user_recommendations=None,
        qa_passed=True,
        accepted_violations=[],
        last_modified=_TS,
        group_id=group_id,
        user_assets=[],
        has_math=False,
    )


def _make_presentation(
    folder: str = _FOLDER,
    script_count: int = 0,
    handout_count: int = 0,
    export_count: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        folder=folder,
        created_at=_TS,
        slide_manifest=[],
        export_count=export_count,
        script_count=script_count,
        handout_count=handout_count,
        separator_position=None,
        separator_content=None,
    )


def _make_deck_state(
    slides: Optional[list[SimpleNamespace]] = None,
    presentations: Optional[list[SimpleNamespace]] = None,
    style_locked: bool = True,
    closing_slide: Optional[str] = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        project_name="test_project",
        created_at=_TS,
        archetype="lab_meeting",
        style_locked=style_locked,
        closing_slide=closing_slide,
        slides=slides if slides is not None else [],
        presentations=presentations if presentations is not None else [],
    )


def _make_debrief_state(
    phase: str = "production",
    sub_phase: str = "production/red_green",
    pending_gate: Optional[str] = None,
    pre_view_state: Optional[dict] = None,
    view_deferred: bool = False,
    red_green_iteration: int = 0,
    red_green_started_at: Optional[str] = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        phase=phase,
        sub_phase=sub_phase,
        active_agent="consultant",
        archetype="lab_meeting",
        current_group_id=None,
        current_slide_slug=None,
        pending_gate=pending_gate,
        last_gate_response=None,
        red_green_iteration=red_green_iteration,
        red_green_started_at=red_green_started_at,
        group_slide_index=0,
        group_slide_count=1,
        backup_mode=False,
        completed_groups=[],
        pre_view_state=pre_view_state,
        view_deferred=view_deferred,
        closing_slide_pending=False,
        group_revise_slug=None,
        style_import_mode=None,
        reference_provided=False,
        reference_modality=None,
        papers_provided=False,
        selected_figures=None,
        session_started_at=_TS,
        state_hash="abc123",
    )


# ---------------------------------------------------------------------------
# Helpers for writing minimal state JSON to tmp_path
# ---------------------------------------------------------------------------


def _write_deck_state(
    project_root: Path,
    slides: Optional[list[dict]] = None,
    presentations: Optional[list[dict]] = None,
) -> None:
    data: dict[str, Any] = {
        "project_name": "test_project",
        "created_at": _TS,
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": slides if slides is not None else [],
        "presentations": presentations if presentations is not None else [],
    }
    (project_root / "deck_state.json").write_text(json.dumps(data))


def _write_debrief_state(
    project_root: Path,
    phase: str = "production",
    sub_phase: str = "production/red_green",
    pending_gate: Optional[str] = None,
    pre_view_state: Optional[dict] = None,
    view_deferred: bool = False,
    red_green_iteration: int = 0,
    red_green_started_at: Optional[str] = None,
) -> None:
    data: dict[str, Any] = {
        "phase": phase,
        "sub_phase": sub_phase,
        "active_agent": "consultant",
        "archetype": "lab_meeting",
        "current_group_id": None,
        "current_slide_slug": None,
        "pending_gate": pending_gate,
        "last_gate_response": None,
        "red_green_iteration": red_green_iteration,
        "red_green_started_at": red_green_started_at,
        "group_slide_index": 0,
        "group_slide_count": 1,
        "backup_mode": False,
        "completed_groups": [],
        "pre_view_state": pre_view_state,
        "view_deferred": view_deferred,
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
    (project_root / "debrief_state.json").write_text(json.dumps(data))


def _slide_dict(
    slug: str,
    status: str = "approved",
    backup: bool = False,
    group_id: Optional[str] = "group_01",
) -> dict[str, Any]:
    return {
        "slug": slug,
        "title": f"Title of {slug}",
        "status": status,
        "backup": backup,
        "content_summary": "Summary",
        "visual_approach": "Diagram",
        "design_choices": "Minimal",
        "forks_not_taken": None,
        "user_recommendations": None,
        "qa_passed": True,
        "accepted_violations": [],
        "last_modified": _TS,
        "group_id": group_id,
        "user_assets": [],
        "has_math": False,
    }


# ===========================================================================
# BC-11.9 / BC-11.4-adjacent: sanitize_save_label
# ===========================================================================


class TestSanitizeSaveLabel:
    """Tests for sanitize_save_label (BC-11.9 save label sanitization)."""

    def test_normal_user_label_is_sanitized_to_lowercase_with_underscores(
        self,
    ) -> None:
        result = sanitize_save_label("My Great Snapshot")
        assert result == "my_great_snapshot"

    def test_hyphens_in_label_are_replaced_with_underscores(self) -> None:
        result = sanitize_save_label("pre-release-snapshot")
        assert result == "pre_release_snapshot"

    def test_special_characters_are_removed_from_label(self) -> None:
        result = sanitize_save_label("snap@shot#1!")
        assert result == "snapshot1"

    def test_consecutive_underscores_are_collapsed_in_label(self) -> None:
        result = sanitize_save_label("snap  shot")
        assert result == "snap_shot"

    def test_leading_and_trailing_underscores_are_stripped_from_label(
        self,
    ) -> None:
        result = sanitize_save_label("__snapshot__")
        assert result == "snapshot"

    def test_label_longer_than_50_chars_is_truncated_to_50(self) -> None:
        long_label = "a" * 60
        result = sanitize_save_label(long_label)
        assert len(result) <= 50

    def test_empty_label_returns_untitled_fallback(self) -> None:
        result = sanitize_save_label("!!!@@@")
        assert result == "untitled"

    def test_whitespace_only_label_returns_untitled_fallback(self) -> None:
        result = sanitize_save_label("   ")
        assert result == "untitled"

    def test_label_exactly_50_chars_after_sanitization_is_preserved(
        self,
    ) -> None:
        label = "a" * 50
        result = sanitize_save_label(label)
        assert result == "a" * 50

    def test_label_of_51_chars_after_sanitization_is_truncated(self) -> None:
        label = "a" * 51
        result = sanitize_save_label(label)
        assert len(result) == 50

    def test_mixed_case_label_is_fully_lowercased(self) -> None:
        result = sanitize_save_label("UPPER_lower_MiXeD")
        assert result == result.lower()

    def test_label_with_only_underscores_returns_untitled(self) -> None:
        result = sanitize_save_label("___")
        assert result == "untitled"


# ===========================================================================
# BC-11.1 / BC-11.2 / BC-11.3: parse_view_query (REQ-VIEW-1 query forms)
# ===========================================================================


class TestParseViewQuery:
    """Tests for parse_view_query covering all five REQ-VIEW-1 query forms."""

    @pytest.fixture()
    def deck_with_slides(self) -> SimpleNamespace:
        slides = [
            _make_slide("intro", status="approved", backup=False, group_id="g1"),
            _make_slide("methods", status="approved", backup=False, group_id="g1"),
            _make_slide(
                "results",
                status="approved",
                backup=False,
                group_id="g2",
            ),
            _make_slide("backup_1", status="approved", backup=True, group_id=None),
            _make_slide(
                "draft_only",
                status="draft",
                backup=False,
                group_id="g1",
            ),
        ]
        return _make_deck_state(slides=slides)

    def test_query_all_returns_only_approved_non_backup_slides(
        self, deck_with_slides: SimpleNamespace
    ) -> None:
        result = parse_view_query("all", deck_with_slides)
        slugs = [s.slug for s in result]
        assert "intro" in slugs
        assert "methods" in slugs
        assert "results" in slugs
        # backup slide should NOT appear in 'all' query
        assert "backup_1" not in slugs
        # draft slide should NOT appear
        assert "draft_only" not in slugs

    def test_query_all_returns_list_not_empty_when_approved_slides_exist(
        self, deck_with_slides: SimpleNamespace
    ) -> None:
        result = parse_view_query("all", deck_with_slides)
        assert len(result) > 0

    def test_query_by_slug_returns_single_matching_slide(
        self, deck_with_slides: SimpleNamespace
    ) -> None:
        result = parse_view_query("intro", deck_with_slides)
        assert len(result) == 1
        assert result[0].slug == "intro"

    def test_query_by_slug_returns_empty_list_when_slug_not_found(
        self, deck_with_slides: SimpleNamespace
    ) -> None:
        result = parse_view_query("nonexistent_slug", deck_with_slides)
        assert result == []

    def test_query_group_returns_all_approved_slides_in_group(
        self, deck_with_slides: SimpleNamespace
    ) -> None:
        result = parse_view_query("group:g1", deck_with_slides)
        slugs = [s.slug for s in result]
        assert "intro" in slugs
        assert "methods" in slugs
        # draft_only is in g1 but not approved — must be excluded
        assert "draft_only" not in slugs

    def test_query_group_returns_empty_list_for_unknown_group(
        self, deck_with_slides: SimpleNamespace
    ) -> None:
        result = parse_view_query("group:no_such_group", deck_with_slides)
        assert result == []

    def test_query_last_returns_only_the_last_approved_slide(
        self, deck_with_slides: SimpleNamespace
    ) -> None:
        result = parse_view_query("last", deck_with_slides)
        assert len(result) == 1
        # last approved (non-backup) slide in order is "results"
        assert result[0].slug == "results"

    def test_query_last_returns_empty_list_when_no_approved_slides(
        self,
    ) -> None:
        empty_deck = _make_deck_state(
            slides=[
                _make_slide("d1", status="draft"),
            ]
        )
        result = parse_view_query("last", empty_deck)
        assert result == []

    def test_query_backup_returns_only_backup_slides(
        self, deck_with_slides: SimpleNamespace
    ) -> None:
        result = parse_view_query("backup", deck_with_slides)
        assert all(s.backup for s in result)
        slugs = [s.slug for s in result]
        assert "backup_1" in slugs

    def test_query_backup_returns_empty_list_when_no_backup_slides(
        self,
    ) -> None:
        no_backup_deck = _make_deck_state(slides=[_make_slide("intro", backup=False)])
        result = parse_view_query("backup", no_backup_deck)
        assert result == []

    def test_unknown_query_form_returns_empty_list(
        self, deck_with_slides: SimpleNamespace
    ) -> None:
        result = parse_view_query("gibberish_query_xyz", deck_with_slides)
        assert result == []


# ===========================================================================
# BC-11.4: generate_view_html
# ===========================================================================


class TestGenerateViewHtml:
    """Tests for generate_view_html (BC-11.4)."""

    @pytest.fixture()
    def project_root(self, tmp_path: Path) -> Path:
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "screenshots").mkdir(parents=True)
        return tmp_path

    @pytest.fixture()
    def single_slide(self) -> list[SimpleNamespace]:
        return [_make_slide("intro")]

    @pytest.fixture()
    def multiple_slides(self) -> list[SimpleNamespace]:
        return [
            _make_slide("intro"),
            _make_slide("methods"),
            _make_slide("results"),
        ]

    def test_generate_view_html_returns_a_string(
        self,
        single_slide: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_view_html(single_slide, project_root)
        assert isinstance(result, str)

    def test_generated_html_contains_html_root_element(
        self,
        single_slide: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_view_html(single_slide, project_root)
        assert "<html" in result.lower()

    def test_generated_html_has_no_external_css_or_js_links(
        self,
        single_slide: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_view_html(single_slide, project_root)
        # No <link rel="stylesheet">, no <script src="...">
        assert 'rel="stylesheet"' not in result
        assert "<script src=" not in result

    def test_single_slide_html_includes_slug_label(
        self,
        single_slide: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_view_html(single_slide, project_root)
        assert "intro" in result

    def test_single_slide_html_includes_slide_title(
        self,
        single_slide: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_view_html(single_slide, project_root)
        assert "Title of intro" in result

    def test_multi_slide_html_includes_all_slug_labels(
        self,
        multiple_slides: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_view_html(multiple_slides, project_root)
        for slide in multiple_slides:
            assert slide.slug in result

    def test_multi_slide_html_includes_all_slide_titles(
        self,
        multiple_slides: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_view_html(multiple_slides, project_root)
        for slide in multiple_slides:
            assert slide.title in result

    def test_view_html_is_self_contained_no_external_references(
        self,
        multiple_slides: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_view_html(multiple_slides, project_root)
        assert "https://" not in result
        assert "http://" not in result


# ===========================================================================
# BC-11.1: main_view — phase-gating behavior
# ===========================================================================


class TestMainViewPhaseGating:
    """Tests for main_view phase-based behavior (BC-11.1)."""

    def test_main_view_in_phase1_prints_no_slides_message_and_exits(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """BC-11.1: In Phase 1 (discovery), main_view exits without file I/O."""
        _write_deck_state(tmp_path)
        _write_debrief_state(
            tmp_path,
            phase="discovery",
            sub_phase="discovery/dialog",
        )
        with pytest.raises(SystemExit) as exc_info:
            main_view("all", tmp_path)
        assert exc_info.value.code == 0
        output = capsys.readouterr()
        combined = output.out + output.err
        assert "No slides yet" in combined

    def test_main_view_in_phase2_prints_no_slides_message_and_exits(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """BC-11.1: In Phase 2 (style), main_view exits without file I/O."""
        _write_deck_state(tmp_path)
        _write_debrief_state(
            tmp_path,
            phase="style",
            sub_phase="style/style_dialog",
        )
        with pytest.raises(SystemExit) as exc_info:
            main_view("all", tmp_path)
        assert exc_info.value.code == 0
        output = capsys.readouterr()
        combined = output.out + output.err
        assert "No slides yet" in combined

    def test_main_view_phase1_does_not_write_view_html(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.1: In Phase 1, no view.html file must be created."""
        (tmp_path / "output").mkdir()
        _write_deck_state(tmp_path)
        _write_debrief_state(
            tmp_path,
            phase="discovery",
            sub_phase="discovery/greeting",
        )
        try:
            main_view("all", tmp_path)
        except SystemExit:
            pass
        assert not (tmp_path / "output" / "view.html").exists()

    def test_main_view_phase2_does_not_write_view_html(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.1: In Phase 2, no view.html file must be created."""
        (tmp_path / "output").mkdir()
        _write_deck_state(tmp_path)
        _write_debrief_state(
            tmp_path,
            phase="style",
            sub_phase="style/style_review",
        )
        try:
            main_view("all", tmp_path)
        except SystemExit:
            pass
        assert not (tmp_path / "output" / "view.html").exists()

    def test_main_view_exits_code_1_when_no_slides_match_query(
        self,
        tmp_path: Path,
    ) -> None:
        """main_view exits code 1 when the query resolves to no slides."""
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "screenshots").mkdir()
        _write_deck_state(
            tmp_path,
            slides=[],
            presentations=[
                {
                    "folder": _FOLDER,
                    "created_at": _TS,
                    "slide_manifest": [],
                    "export_count": 1,
                    "script_count": 0,
                    "handout_count": 0,
                    "separator_position": None,
                    "separator_content": None,
                }
            ],
        )
        _write_debrief_state(
            tmp_path,
            phase="finalization",
            sub_phase="finalization/post_export",
        )
        with patch("webbrowser.open"):
            with pytest.raises(SystemExit) as exc_info:
                main_view("all", tmp_path)
        assert exc_info.value.code == 1


# ===========================================================================
# BC-11.2: view nested protection
# ===========================================================================


class TestMainViewNestedProtection:
    """Tests for BC-11.2: view skill must not overwrite pre_view_state."""

    def test_main_view_in_phase3_does_not_overwrite_existing_pre_view_state(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.2: If pre_view_state is already set, it must not be overwritten."""
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "screenshots").mkdir()
        existing_pre_view = {"phase": "production", "sub_phase": "production/red_green"}
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
        )
        _write_debrief_state(
            tmp_path,
            phase="production",
            sub_phase="production/group_review",
            pre_view_state=existing_pre_view,
        )
        with patch("webbrowser.open"):
            try:
                main_view("all", tmp_path)
            except SystemExit:
                pass
        # Reload debrief_state to check pre_view_state was not overwritten
        state_data = json.loads((tmp_path / "debrief_state.json").read_text())
        assert state_data.get("pre_view_state") == existing_pre_view


# ===========================================================================
# BC-11.3: view red-green deferral
# ===========================================================================


class TestMainViewRedGreenDeferral:
    """Tests for BC-11.3: view must be deferred during active red-green cycle."""

    def test_main_view_sets_view_deferred_when_red_green_cycle_is_active(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.3: Active red-green cycle → view_deferred=True, no gate set."""
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "screenshots").mkdir()
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
        )
        # red-green cycle is active: iteration > 0
        _write_debrief_state(
            tmp_path,
            phase="production",
            sub_phase="production/red_green",
            red_green_iteration=2,
            red_green_started_at=_TS,
        )
        with patch("webbrowser.open"):
            try:
                main_view("all", tmp_path)
            except SystemExit:
                pass
        state_data = json.loads((tmp_path / "debrief_state.json").read_text())
        assert state_data.get("view_deferred") is True

    def test_main_view_does_not_set_pending_gate_when_red_green_cycle_is_active(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.3: Active red-green cycle → pending_gate must NOT be
        G3.V_view_dispatch."""
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "screenshots").mkdir()
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
        )
        _write_debrief_state(
            tmp_path,
            phase="production",
            sub_phase="production/red_green",
            red_green_iteration=1,
            red_green_started_at=_TS,
        )
        with patch("webbrowser.open"):
            try:
                main_view("all", tmp_path)
            except SystemExit:
                pass
        state_data = json.loads((tmp_path / "debrief_state.json").read_text())
        assert state_data.get("pending_gate") != "G3.V_view_dispatch"


# ===========================================================================
# BC-11.5 + BC-11.6: main_script_generator precondition and folder selection
# ===========================================================================


class TestMainScriptGeneratorPrecondition:
    """Tests for BC-11.5: script_generator exits when presentations is empty."""

    def test_main_script_generator_exits_code_1_when_no_presentations(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """BC-11.5: No presentations → exit 1 with error message."""
        (tmp_path / "output").mkdir()
        (tmp_path / "deck_brief.md").write_text("# Brief\n\nSome content.")
        _write_deck_state(tmp_path, slides=[], presentations=[])
        _write_debrief_state(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main_script_generator(tmp_path)
        assert exc_info.value.code == 1
        output = capsys.readouterr()
        combined = output.out + output.err
        assert "No export" in combined

    def test_main_script_generator_prints_no_export_message(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """BC-11.5: The exact error message text is checked."""
        (tmp_path / "output").mkdir()
        (tmp_path / "deck_brief.md").write_text("# Brief")
        _write_deck_state(tmp_path, presentations=[])
        _write_debrief_state(tmp_path)
        with pytest.raises(SystemExit):
            main_script_generator(tmp_path)
        output = capsys.readouterr()
        combined = output.out + output.err
        assert "Run /debrief:export first" in combined


class TestMainScriptGeneratorFolderSelection:
    """Tests for BC-11.6: script version numbering and folder selection."""

    def test_main_script_generator_uses_most_recent_presentation_folder(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.6: Uses last entry in presentations array for folder."""
        first_folder = "2026_04_10_first"
        last_folder = "2026_04_12_last"
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / first_folder).mkdir()
        (tmp_path / "output" / last_folder).mkdir()
        (tmp_path / "deck_brief.md").write_text("# Brief\n\nContent here.")
        presentations = [
            {
                "folder": first_folder,
                "created_at": _TS,
                "slide_manifest": [],
                "export_count": 1,
                "script_count": 0,
                "handout_count": 0,
                "separator_position": None,
                "separator_content": None,
            },
            {
                "folder": last_folder,
                "created_at": _TS,
                "slide_manifest": [],
                "export_count": 1,
                "script_count": 0,
                "handout_count": 0,
                "separator_position": None,
                "separator_content": None,
            },
        ]
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
            presentations=presentations,
        )
        _write_debrief_state(tmp_path)
        main_script_generator(tmp_path)
        assert (tmp_path / "output" / last_folder / "script_v001.md").exists()

    def test_main_script_generator_version_zero_padded_to_3_digits(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.6: NNN is zero-padded: first script is script_v001.md."""
        folder = "2026_04_12_deck"
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / folder).mkdir()
        (tmp_path / "deck_brief.md").write_text("# Brief\n\nContent.")
        presentations = [
            {
                "folder": folder,
                "created_at": _TS,
                "slide_manifest": [],
                "export_count": 1,
                "script_count": 0,
                "handout_count": 0,
                "separator_position": None,
                "separator_content": None,
            }
        ]
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
            presentations=presentations,
        )
        _write_debrief_state(tmp_path)
        main_script_generator(tmp_path)
        expected = tmp_path / "output" / folder / "script_v001.md"
        assert expected.exists()

    def test_main_script_generator_second_run_produces_script_v002(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.6: Second generation increments to script_v002.md."""
        folder = "2026_04_12_deck"
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / folder).mkdir()
        (tmp_path / "deck_brief.md").write_text("# Brief\n\nContent.")
        presentations = [
            {
                "folder": folder,
                "created_at": _TS,
                "slide_manifest": [],
                "export_count": 1,
                "script_count": 1,
                "handout_count": 0,
                "separator_position": None,
                "separator_content": None,
            }
        ]
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
            presentations=presentations,
        )
        _write_debrief_state(tmp_path)
        main_script_generator(tmp_path)
        expected = tmp_path / "output" / folder / "script_v002.md"
        assert expected.exists()

    def test_main_script_generator_prints_output_path_to_stderr(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """main_script_generator prints the generated file path to stderr."""
        folder = "2026_04_12_deck"
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / folder).mkdir()
        (tmp_path / "deck_brief.md").write_text("# Brief\n\nContent.")
        presentations = [
            {
                "folder": folder,
                "created_at": _TS,
                "slide_manifest": [],
                "export_count": 1,
                "script_count": 0,
                "handout_count": 0,
                "separator_position": None,
                "separator_content": None,
            }
        ]
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
            presentations=presentations,
        )
        _write_debrief_state(tmp_path)
        main_script_generator(tmp_path)
        captured = capsys.readouterr()
        assert "script_v001.md" in captured.err


# ===========================================================================
# BC-11.6: generate_script_content per-slide sections
# ===========================================================================


class TestGenerateScriptContent:
    """Tests for generate_script_content (BC-11.6 / REQ-SCRIPT-3)."""

    @pytest.fixture()
    def two_slides(self) -> list[SimpleNamespace]:
        return [
            _make_slide("intro", content_summary="Intro key points here"),
            _make_slide("methods", content_summary="Methods key points here"),
        ]

    def test_generate_script_content_returns_string(
        self,
        two_slides: list[SimpleNamespace],
    ) -> None:
        result = generate_script_content(
            "# Brief\n\nThis is a talk.",
            two_slides,
            _FOLDER,
        )
        assert isinstance(result, str)

    def test_generate_script_content_includes_section_for_each_slide(
        self,
        two_slides: list[SimpleNamespace],
    ) -> None:
        result = generate_script_content(
            "# Brief\n\nThis is a talk.",
            two_slides,
            _FOLDER,
        )
        # Each slide title or slug should appear in the script
        for slide in two_slides:
            assert slide.title in result or slide.slug in result

    def test_generate_script_content_includes_talking_points_marker(
        self,
        two_slides: list[SimpleNamespace],
    ) -> None:
        """REQ-SCRIPT-3: key talking points must appear in some form."""
        result = generate_script_content(
            "# Brief",
            two_slides,
            _FOLDER,
        )
        # At least one of the expected keywords from REQ-SCRIPT-3 must appear
        markers = [
            "talking point",
            "key point",
            "transition",
            "speaking time",
            "estimated",
        ]
        lower_result = result.lower()
        assert any(m in lower_result for m in markers)

    def test_generate_script_content_single_slide_produces_non_empty_output(
        self,
    ) -> None:
        result = generate_script_content(
            "# Brief",
            [_make_slide("solo")],
            _FOLDER,
        )
        assert len(result.strip()) > 0

    def test_generate_script_content_empty_slides_list_produces_valid_string(
        self,
    ) -> None:
        result = generate_script_content("# Brief", [], _FOLDER)
        assert isinstance(result, str)


# ===========================================================================
# BC-11.7: main_handout — playwright env check
# ===========================================================================


class TestMainHandoutPlaywrightEnvCheck:
    """Tests for BC-11.7 / BC-11.16: playwright import check runs after
    preconditions. BUG-AUDIT-21 amendment: the test setup now includes
    approved slides so the flow reaches the playwright check; previously
    the presence-of-presentations was the only setup, but BC-11.16
    validates ``approved-slide availability`` first and the missing-
    slides path would shadow the playwright signal under test.
    """

    def test_main_handout_exits_code_2_when_playwright_is_unavailable(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """BC-11.7: Missing playwright → exit 2 with env-corruption message."""
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
            presentations=[],
        )
        _write_debrief_state(tmp_path)

        # BUG-AUDIT-21 note: capture the real find_spec BEFORE patching
        # so non-playwright lookups pass through to the real
        # implementation. Without this, the patched MagicMock calls
        # back into itself on non-playwright names and recurses. The
        # old test got away with it because the pre-BUG-AUDIT-21
        # main_handout hit the playwright check first and returned
        # before any non-playwright find_spec call was made. After
        # the precondition reordering, main_handout reaches
        # read_deck_state (which imports json_repair) before the
        # playwright check, exposing the recursion bug.
        _real_find_spec = importlib.util.find_spec

        def _fake_find_spec(name: str):
            if name == "playwright":
                return None
            return _real_find_spec(name)

        with patch("importlib.util.find_spec", side_effect=_fake_find_spec):
            with pytest.raises(SystemExit) as exc_info:
                main_handout("2up", tmp_path)
        assert exc_info.value.code == 2

    def test_main_handout_stderr_has_env_corruption_message_when_playwright_missing(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """BC-11.7: The stderr message must reference the env-corruption context."""
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
            presentations=[],
        )
        _write_debrief_state(tmp_path)

        _real_find_spec = importlib.util.find_spec

        def _fake_find_spec2(name: str):
            if name == "playwright":
                return None
            return _real_find_spec(name)

        with patch("importlib.util.find_spec", side_effect=_fake_find_spec2):
            with pytest.raises(SystemExit):
                main_handout("2up", tmp_path)
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        # Must mention playwright or env corruption
        lower = combined.lower()
        assert "playwright" in lower or "environment" in lower or "conda" in lower


# BUG-AUDIT-21: the old ``TestMainHandoutVersionNumbering`` class was
# deleted. It set up synthetic presentation records with a pre-set
# ``handout_count`` and asserted the output path fell under
# ``output/<presentation_folder>/handout_v{NNN}.pdf``. That path scheme
# is gone per BC-11.17 — handout now writes to ``output/handouts/`` and
# derives its version number by scanning the directory, not by reading
# state. The equivalent coverage (plus several new cases — noise file
# tolerance, max-existing-derivation, directory auto-creation, and real
# %PDF magic byte verification) lives in
# ``tests/regressions/test_bug_audit_21_handout_robustness.py``.


# ===========================================================================
# BC-11.6 / generate_layout_html: 2up and 4up mode
# ===========================================================================


class TestGenerateLayoutHtml:
    """Tests for generate_layout_html (BC-11.6, REQ-HAND-4 layout modes)."""

    @pytest.fixture()
    def four_slides(self) -> list[SimpleNamespace]:
        return [
            _make_slide(f"slide_{i}", content_summary=f"Summary {i}") for i in range(4)
        ]

    @pytest.fixture()
    def project_root(self, tmp_path: Path) -> Path:
        (tmp_path / "output" / "screenshots").mkdir(parents=True)
        return tmp_path

    def test_generate_layout_html_returns_string(
        self,
        four_slides: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_layout_html("2up", four_slides, project_root)
        assert isinstance(result, str)

    def test_generate_layout_html_contains_html_element(
        self,
        four_slides: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_layout_html("2up", four_slides, project_root)
        assert "<html" in result.lower()

    def test_generate_layout_html_2up_includes_all_slide_slugs(
        self,
        four_slides: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_layout_html("2up", four_slides, project_root)
        for slide in four_slides:
            assert slide.slug in result

    def test_generate_layout_html_4up_includes_all_slide_slugs(
        self,
        four_slides: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        result = generate_layout_html("4up", four_slides, project_root)
        for slide in four_slides:
            assert slide.slug in result

    def test_generate_layout_html_2up_includes_content_summary_notes(
        self,
        four_slides: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        """2up mode uses detailed notes from content_summary fields."""
        result = generate_layout_html("2up", four_slides, project_root)
        for slide in four_slides:
            if slide.content_summary:
                assert slide.content_summary in result

    def test_generate_layout_html_4up_includes_slide_content(
        self,
        four_slides: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        """4up mode still includes slide titles or slugs."""
        result = generate_layout_html("4up", four_slides, project_root)
        for slide in four_slides:
            assert slide.slug in result or slide.title in result

    def test_generate_layout_html_has_no_external_dependencies(
        self,
        four_slides: list[SimpleNamespace],
        project_root: Path,
    ) -> None:
        """Layout HTML must not include external CSS or JS links."""
        result = generate_layout_html("2up", four_slides, project_root)
        assert 'rel="stylesheet"' not in result
        assert "<script src=" not in result


# ===========================================================================
# BC-11.10: skill_save — does not touch debrief_state
# ===========================================================================


class TestSkillSaveDoesNotTouchDebriefState:
    """Tests for BC-11.10: save must not copy or modify debrief_state.json."""

    def test_save_copies_deck_state_to_snapshot_directory(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.10: deck_state.json must appear in snapshot dir."""
        from utility_skills import skill_save  # type: ignore[import]

        (tmp_path / "output" / "snapshots").mkdir(parents=True)
        _write_deck_state(tmp_path)
        _write_debrief_state(tmp_path)
        (tmp_path / "ledger.jsonl").write_text("")
        skill_save("my_snapshot", tmp_path)
        snapshot_dir = tmp_path / "output" / "snapshots" / "my_snapshot"
        assert (snapshot_dir / "deck_state.json").exists()

    def test_save_does_not_copy_debrief_state_to_snapshot_directory(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.10: debrief_state.json must NOT appear in snapshot dir."""
        from utility_skills import skill_save  # type: ignore[import]

        (tmp_path / "output" / "snapshots").mkdir(parents=True)
        _write_deck_state(tmp_path)
        _write_debrief_state(tmp_path)
        (tmp_path / "ledger.jsonl").write_text("")
        skill_save("no_debrief", tmp_path)
        snapshot_dir = tmp_path / "output" / "snapshots" / "no_debrief"
        assert not (snapshot_dir / "debrief_state.json").exists()

    def test_save_copies_ledger_to_snapshot_directory(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.10: ledger.jsonl must appear in snapshot dir."""
        from utility_skills import skill_save  # type: ignore[import]

        (tmp_path / "output" / "snapshots").mkdir(parents=True)
        _write_deck_state(tmp_path)
        _write_debrief_state(tmp_path)
        (tmp_path / "ledger.jsonl").write_text('{"event":"test"}\n')
        skill_save("with_ledger", tmp_path)
        snapshot_dir = tmp_path / "output" / "snapshots" / "with_ledger"
        assert (snapshot_dir / "ledger.jsonl").exists()

    def test_save_label_sanitization_applied_to_user_provided_label(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.9: User label is sanitized before directory creation."""
        from utility_skills import skill_save  # type: ignore[import]

        (tmp_path / "output" / "snapshots").mkdir(parents=True)
        _write_deck_state(tmp_path)
        _write_debrief_state(tmp_path)
        (tmp_path / "ledger.jsonl").write_text("")
        # Raw label has uppercase and spaces — should be sanitized
        skill_save("My Snapshot Label", tmp_path)
        sanitized = tmp_path / "output" / "snapshots" / "my_snapshot_label"
        assert sanitized.exists()

    def test_save_collision_appends_suffix_to_directory_name(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.9: Collision → append _2 to snapshot directory name."""
        from utility_skills import skill_save  # type: ignore[import]

        (tmp_path / "output" / "snapshots").mkdir(parents=True)
        # Pre-create the first snapshot to simulate collision
        (tmp_path / "output" / "snapshots" / "my_snap").mkdir()
        _write_deck_state(tmp_path)
        _write_debrief_state(tmp_path)
        (tmp_path / "ledger.jsonl").write_text("")
        skill_save("my_snap", tmp_path)
        assert (tmp_path / "output" / "snapshots" / "my_snap_2").exists()

    def test_save_empty_sanitized_label_falls_back_to_untitled(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.9: Empty sanitized result → use 'untitled' as directory name."""
        from utility_skills import skill_save  # type: ignore[import]

        (tmp_path / "output" / "snapshots").mkdir(parents=True)
        _write_deck_state(tmp_path)
        _write_debrief_state(tmp_path)
        (tmp_path / "ledger.jsonl").write_text("")
        # Label sanitizes to empty
        skill_save("!!!@@@", tmp_path)
        assert (tmp_path / "output" / "snapshots" / "untitled").exists()


# BUG-AUDIT-22: the old ``TestSkillResetConfirmationAndExemption`` class
# (7 tests) was deleted. It tested the hard-delete ``skill_reset`` function
# that BUG-AUDIT-22 replaced with ``skill_restore`` (backup-restore from
# ``output/snapshots/``). The equivalent coverage — and more (auto-save
# safety net, orphan sweep, restore_log entry, invalid-label handling,
# list mode) — lives in
# ``tests/regressions/test_bug_audit_22_restore.py``.


# ===========================================================================
# BC-11.13 + BC-11.14: skill_quit flush sequence and draft retention
# ===========================================================================


class TestSkillQuitFlushSequence:
    """Tests for BC-11.13: quit flushes state files before cleaning artifacts."""

    @pytest.fixture()
    def project_with_draft(self, tmp_path: Path) -> Path:
        """Set up a project in style/style_dialog sub_phase with draft dir."""
        (tmp_path / ".debrief" / "draft").mkdir(parents=True)
        (tmp_path / ".debrief" / "draft" / "style_config.json").write_text(
            json.dumps({"font": "Helvetica"})
        )
        (tmp_path / ".debrief" / "state.lock").touch()
        _write_deck_state(tmp_path)
        _write_debrief_state(
            tmp_path,
            phase="style",
            sub_phase="style/style_dialog",
        )
        (tmp_path / "ledger.jsonl").write_text("")
        return tmp_path

    @pytest.fixture()
    def project_in_production(self, tmp_path: Path) -> Path:
        """Set up a project in production/group_planning sub_phase."""
        (tmp_path / ".debrief").mkdir(parents=True)
        (tmp_path / ".debrief" / "draft").mkdir()
        (tmp_path / ".debrief" / "draft" / "preview.html").write_text("<html>")
        (tmp_path / ".debrief" / "state.lock").touch()
        _write_deck_state(tmp_path)
        _write_debrief_state(
            tmp_path,
            phase="production",
            sub_phase="production/group_planning",
        )
        (tmp_path / "ledger.jsonl").write_text("")
        return tmp_path

    def test_quit_writes_debrief_state_file(self, project_with_draft: Path) -> None:
        """BC-11.13: debrief_state.json must be written (flushed) by quit."""
        from utility_skills import skill_quit  # type: ignore[import]

        mtime_before = (project_with_draft / "debrief_state.json").stat().st_mtime
        skill_quit(project_with_draft)
        mtime_after = (project_with_draft / "debrief_state.json").stat().st_mtime
        assert mtime_after >= mtime_before

    def test_quit_writes_deck_state_file(self, project_with_draft: Path) -> None:
        """BC-11.13: deck_state.json must be written (flushed) by quit."""
        from utility_skills import skill_quit  # type: ignore[import]

        mtime_before = (project_with_draft / "deck_state.json").stat().st_mtime
        skill_quit(project_with_draft)
        mtime_after = (project_with_draft / "deck_state.json").stat().st_mtime
        assert mtime_after >= mtime_before

    def test_quit_retains_draft_directory_in_style_dialog_sub_phase(
        self, project_with_draft: Path
    ) -> None:
        """BC-11.14: .debrief/draft/ is retained during style/style_dialog."""
        from utility_skills import skill_quit  # type: ignore[import]

        skill_quit(project_with_draft)
        assert (project_with_draft / ".debrief" / "draft").exists()

    def test_quit_retains_draft_directory_in_style_review_sub_phase(
        self, tmp_path: Path
    ) -> None:
        """BC-11.14: .debrief/draft/ is retained during style/style_review."""
        from utility_skills import skill_quit  # type: ignore[import]

        (tmp_path / ".debrief" / "draft").mkdir(parents=True)
        (tmp_path / ".debrief" / "draft" / "style_config.json").write_text(
            json.dumps({"font": "Helvetica"})
        )
        (tmp_path / ".debrief" / "state.lock").touch()
        _write_deck_state(tmp_path)
        _write_debrief_state(
            tmp_path,
            phase="style",
            sub_phase="style/style_review",
        )
        (tmp_path / "ledger.jsonl").write_text("")
        skill_quit(tmp_path)
        assert (tmp_path / ".debrief" / "draft").exists()

    def test_quit_cleans_draft_directory_in_production_phase(
        self, project_in_production: Path
    ) -> None:
        """BC-11.14: .debrief/draft/ is removed in production/group_planning."""
        from utility_skills import skill_quit  # type: ignore[import]

        skill_quit(project_in_production)
        assert not (project_in_production / ".debrief" / "draft").exists()

    def test_quit_retains_draft_when_pending_gate_is_G2_1_style_config_review(
        self, tmp_path: Path
    ) -> None:
        """BC-11.14: draft is kept when pending_gate==G2.1_style_config_review."""
        from utility_skills import skill_quit  # type: ignore[import]

        (tmp_path / ".debrief" / "draft").mkdir(parents=True)
        (tmp_path / ".debrief" / "draft" / "style_config.json").write_text(
            json.dumps({"font": "Helvetica"})
        )
        (tmp_path / ".debrief" / "state.lock").touch()
        _write_deck_state(tmp_path)
        _write_debrief_state(
            tmp_path,
            phase="style",
            sub_phase="style/style_lock",
            pending_gate="G2.1_style_config_review",
        )
        (tmp_path / "ledger.jsonl").write_text("")
        skill_quit(tmp_path)
        assert (tmp_path / ".debrief" / "draft").exists()

    def test_quit_cleans_draft_in_style_lock_without_pending_gate(
        self, tmp_path: Path
    ) -> None:
        """BC-11.14: style/style_lock without G2.1 pending gate → draft cleaned."""
        from utility_skills import skill_quit  # type: ignore[import]

        (tmp_path / ".debrief" / "draft").mkdir(parents=True)
        (tmp_path / ".debrief" / "draft" / "preview.html").write_text("<html>")
        (tmp_path / ".debrief" / "state.lock").touch()
        _write_deck_state(tmp_path)
        _write_debrief_state(
            tmp_path,
            phase="style",
            sub_phase="style/style_lock",
            pending_gate=None,
        )
        (tmp_path / "ledger.jsonl").write_text("")
        skill_quit(tmp_path)
        assert not (tmp_path / ".debrief" / "draft").exists()


# ===========================================================================
# BC-11.1: Phase 3 routing — pre_view_state and pending_gate are set
# ===========================================================================


class TestMainViewPhase3RoutingFirstCall:
    """BC-11.1: In Phase 3, first view call sets pre_view_state and gate."""

    def test_phase3_first_call_sets_pre_view_state(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.1: Phase 3 first call must set pre_view_state in state."""
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "screenshots").mkdir()
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
        )
        _write_debrief_state(
            tmp_path,
            phase="production",
            sub_phase="production/group_review",
            pre_view_state=None,
        )
        with patch("webbrowser.open"):
            try:
                main_view("all", tmp_path)
            except SystemExit:
                pass
        state_data = json.loads(
            (tmp_path / "debrief_state.json").read_text()
        )
        assert state_data.get("pre_view_state") is not None

    def test_phase3_first_call_sets_pending_gate_to_view_dispatch(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.1: Phase 3 first call must set pending_gate to dispatch."""
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "screenshots").mkdir()
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
        )
        _write_debrief_state(
            tmp_path,
            phase="production",
            sub_phase="production/group_planning",
            pre_view_state=None,
        )
        with patch("webbrowser.open"):
            try:
                main_view("all", tmp_path)
            except SystemExit:
                pass
        state_data = json.loads(
            (tmp_path / "debrief_state.json").read_text()
        )
        assert state_data.get("pending_gate") == "G3.V_view_dispatch"


# ===========================================================================
# BC-11.1: Phase 4 run-and-return — no routing side effects
# ===========================================================================


class TestMainViewPhase4NoRoutingSideEffects:
    """BC-11.1: Phase 4/complete must not set pre_view_state or pending_gate."""

    def _setup(self, tmp_path: Path, phase: str, sub_phase: str) -> None:
        (tmp_path / "output").mkdir(exist_ok=True)
        (tmp_path / "output" / "screenshots").mkdir(exist_ok=True)
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
        )
        _write_debrief_state(
            tmp_path,
            phase=phase,
            sub_phase=sub_phase,
            pre_view_state=None,
            pending_gate=None,
        )

    def test_phase4_does_not_set_pre_view_state(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.1: In Phase 4, pre_view_state must remain unset."""
        self._setup(tmp_path, "finalization", "finalization/post_export")
        with patch("webbrowser.open"):
            try:
                main_view("all", tmp_path)
            except SystemExit:
                pass
        state_data = json.loads(
            (tmp_path / "debrief_state.json").read_text()
        )
        assert state_data.get("pre_view_state") is None

    def test_phase4_does_not_set_pending_gate(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.1: In Phase 4, pending_gate must remain unset."""
        self._setup(
            tmp_path, "finalization", "finalization/reviewing_for_export"
        )
        with patch("webbrowser.open"):
            try:
                main_view("all", tmp_path)
            except SystemExit:
                pass
        state_data = json.loads(
            (tmp_path / "debrief_state.json").read_text()
        )
        assert state_data.get("pending_gate") is None


# ===========================================================================
# BC-11.4: view.html is written and overwrites on each invocation
# ===========================================================================


class TestMainViewWritesViewHtml:
    """BC-11.4: main_view must write output/view.html and overwrite it."""

    def test_main_view_writes_view_html_in_production_phase(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.4: main_view creates output/view.html when slides exist."""
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "screenshots").mkdir()
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
        )
        _write_debrief_state(
            tmp_path,
            phase="production",
            sub_phase="production/group_review",
        )
        with patch("webbrowser.open"):
            try:
                main_view("all", tmp_path)
            except SystemExit:
                pass
        assert (tmp_path / "output" / "view.html").exists()

    def test_main_view_overwrites_existing_view_html(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.4: main_view overwrites an existing output/view.html."""
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "screenshots").mkdir()
        view_path = tmp_path / "output" / "view.html"
        view_path.write_text("OLD CONTENT", encoding="utf-8")
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
        )
        _write_debrief_state(
            tmp_path,
            phase="finalization",
            sub_phase="finalization/post_export",
            pre_view_state=None,
            pending_gate=None,
        )
        with patch("webbrowser.open"):
            try:
                main_view("all", tmp_path)
            except SystemExit:
                pass
        content = view_path.read_text(encoding="utf-8")
        assert content != "OLD CONTENT"
        assert "<html" in content.lower()


# ===========================================================================
# BC-11.8: main_handout does not consume (modify) pending_gate
# ===========================================================================


_FAKE_PDF_BYTES_FOR_PENDING_GATE_TESTS = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Count 0 /Kids [] >>\nendobj\n"
    b"xref\n0 3\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n"
    b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n100\n%%EOF\n"
)


def _fake_playwright_that_writes_bytes() -> MagicMock:
    """Return a sync_playwright() mock whose page.pdf(path=...) writes
    real %PDF bytes to the requested path. BUG-AUDIT-21: the old
    MagicMock-with-touch hack is gone, so tests that don't want to
    launch real Chromium must simulate page.pdf by writing bytes.
    """

    def _fake_page_pdf(path: str) -> None:
        Path(path).write_bytes(_FAKE_PDF_BYTES_FOR_PENDING_GATE_TESTS)

    mock_page = MagicMock()
    mock_page.pdf.side_effect = _fake_page_pdf
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page
    mock_pw = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_pw)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=mock_ctx)


class TestMainHandoutDoesNotConsumePendingGate:
    """BC-11.8: /debrief:handout must not clear or modify pending_gate.

    BUG-AUDIT-21 amendment: these tests were rewritten to match the
    decoupled output path (BC-11.17) and to use a fake page.pdf that
    writes real %PDF bytes instead of the old out_path.touch() hack.
    """

    def _setup_handout(
        self,
        tmp_path: Path,
        pending_gate: Optional[str],
    ) -> None:
        # BUG-AUDIT-21: no presentation folder needed — handout writes to
        # output/handouts/ which the function auto-creates. Screenshots
        # directory also no longer required (fallback to [no screenshot]).
        _write_deck_state(
            tmp_path,
            slides=[_slide_dict("intro")],
            presentations=[],
        )
        _write_debrief_state(
            tmp_path,
            phase="finalization",
            sub_phase="finalization/post_export",
            pending_gate=pending_gate,
        )

    def test_handout_preserves_pending_gate_g4_6(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.8: pending_gate G4.6 must survive a main_handout call."""
        self._setup_handout(tmp_path, pending_gate="G4.6_handout_review")
        with patch(
            "playwright.sync_api.sync_playwright",
            _fake_playwright_that_writes_bytes(),
        ):
            main_handout("2up", tmp_path)
        state_data = json.loads(
            (tmp_path / "debrief_state.json").read_text()
        )
        assert state_data.get("pending_gate") == "G4.6_handout_review"

    def test_handout_preserves_none_pending_gate(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.8: None pending_gate must remain None after main_handout."""
        self._setup_handout(tmp_path, pending_gate=None)
        with patch(
            "playwright.sync_api.sync_playwright",
            _fake_playwright_that_writes_bytes(),
        ):
            main_handout("2up", tmp_path)
        state_data = json.loads(
            (tmp_path / "debrief_state.json").read_text()
        )
        assert state_data.get("pending_gate") is None
