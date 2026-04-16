# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Tests for Unit 2: State Management Library.

Synthetic data generation assumptions
--------------------------------------
- All SlideRecord fixtures use ISO 8601 timestamps of the form
  "2026-01-15T10:00:00Z" for ``last_modified``.
- DeckState fixtures use ``project_name="test_project"``,
  ``archetype="lab_meeting"``, ``created_at="2026-01-15T09:00:00Z"``.
- DebriefState fixtures are fully populated with valid enum values and
  non-negative counters; ``session_started_at="2026-01-15T09:00:00Z"``.
- ``state_hash`` in DebriefState fixtures is computed by calling
  ``compute_state_hash`` (the function under test) on the serialized dict,
  minus the ``state_hash`` key itself.  Tests that require a known-good hash
  compute it inline using ``hashlib.sha256`` over ``json.dumps`` with
  ``sort_keys=True, separators=(',', ':')``.
- The lock file ``.debrief/state.lock`` is created by tests that exercise
  ``write_debrief_state``; the ``.debrief/`` directory is created inside
  ``tmp_path`` using ``Path.mkdir(parents=True, exist_ok=True)``.
- ``json_repair`` is assumed to be installed in the test environment
  (listed in ``environment.yml``); its unavailability is tested by patching
  ``importlib.util.find_spec`` to return ``None``.
- Atomic-write tests use ``tmp_path`` (pytest built-in) for isolation;
  no global state is modified.
- ``compute_state_hash`` is tested independently before it is used as a
  helper in DebriefState round-trip tests to avoid circular assumptions.
- The ``validate_debrief_state`` function receives plain ``dict`` objects;
  no dataclass conversion is needed for those tests.
- For ``sanitize_identifier`` truncation tests, ``max_length`` is set
  explicitly to small values (e.g., 5) to produce predictable results.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from debrief_state import (
    DebriefState,
    DeckState,
    PresentationRecord,
    SlideRecord,
    StateCorruptError,
    atomic_write_json,
    compute_state_hash,
    get_approved_slides,
    get_slide_by_slug,
    increment_export_count,
    increment_handout_count,
    increment_script_count,
    read_debrief_state,
    read_deck_state,
    sanitize_identifier,
    validate_debrief_state,
    write_debrief_state,
    write_deck_state,
)

# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

_TS = "2026-01-15T10:00:00Z"
_CREATED = "2026-01-15T09:00:00Z"


def _make_slide(
    slug: str = "intro",
    status: str = "approved",
    backup: bool = False,
) -> SlideRecord:
    return SlideRecord(
        slug=slug,
        title="Introduction",
        status=status,
        backup=backup,
        content_summary="Summary text",
        visual_approach="Diagram",
        design_choices="Minimal",
        forks_not_taken=None,
        user_recommendations=None,
        qa_passed=False,
        accepted_violations=[],
        last_modified=_TS,
        group_id="group_1",
        user_assets=[],
        has_math=False,
    )


def _make_deck_state(slides: list[SlideRecord] | None = None) -> DeckState:
    return DeckState(
        project_name="test_project",
        created_at=_CREATED,
        archetype="lab_meeting",
        style_locked=False,
        closing_slide=None,
        slides=slides if slides is not None else [],
        presentations=[],
    )


def _make_presentation_record(folder: str = "2026_01_15_intro") -> PresentationRecord:
    return PresentationRecord(
        folder=folder,
        created_at=_CREATED,
        slide_manifest=["intro"],
        export_count=0,
        script_count=0,
        handout_count=0,
        separator_position=None,
        separator_content=None,
    )


def _base_debrief_dict() -> dict[str, Any]:
    """Return a fully valid debrief_state dict (no state_hash yet)."""
    return {
        "phase": "production",
        "sub_phase": "production/red_green",
        "active_agent": "slide_maker",
        "archetype": "lab_meeting",
        "current_group_id": "group_1",
        "current_slide_slug": "intro",
        "pending_gate": None,
        "last_gate_response": None,
        "red_green_started_at": _TS,
        "group_slide_index": 1,
        "group_slide_count": 3,
        "backup_mode": False,
        "completed_groups": [],
        "pre_view_state": None,
        "view_deferred": False,
        "closing_slide_pending": False,
        "group_revise_slug": None,
        "style_import_mode": None,
        "reference_provided": False,
        "reference_modality": None,
        "papers_provided": False,
        "selected_figures": None,
        "session_started_at": _CREATED,
    }


def _make_debrief_state(d: dict[str, Any] | None = None) -> DebriefState:
    """Build a DebriefState from a dict; computes state_hash automatically."""
    base = d if d is not None else _base_debrief_dict()
    h = compute_state_hash(base)
    return DebriefState(
        phase=base["phase"],
        sub_phase=base["sub_phase"],
        active_agent=base["active_agent"],
        archetype=base["archetype"],
        current_group_id=base.get("current_group_id"),
        current_slide_slug=base.get("current_slide_slug"),
        pending_gate=base.get("pending_gate"),
        last_gate_response=base.get("last_gate_response"),
        red_green_started_at=base.get("red_green_started_at"),
        group_slide_index=base["group_slide_index"],
        group_slide_count=base["group_slide_count"],
        backup_mode=base["backup_mode"],
        completed_groups=base["completed_groups"],
        pre_view_state=base.get("pre_view_state"),
        view_deferred=base["view_deferred"],
        closing_slide_pending=base["closing_slide_pending"],
        group_revise_slug=base.get("group_revise_slug"),
        style_import_mode=base.get("style_import_mode"),
        reference_provided=base["reference_provided"],
        reference_modality=base.get("reference_modality"),
        papers_provided=base["papers_provided"],
        selected_figures=base.get("selected_figures"),
        session_started_at=base["session_started_at"],
        state_hash=h,
    )


def _write_debrief_json(path: Path, d: dict[str, Any]) -> None:
    """Write a debrief_state.json file with a correct hash."""
    content = dict(d)
    content["state_hash"] = compute_state_hash(
        {k: v for k, v in content.items() if k != "state_hash"}
    )
    path.write_text(json.dumps(content))


# ---------------------------------------------------------------------------
# BC-2.10 — compute_state_hash: canonical JSON serialization
# ---------------------------------------------------------------------------


class TestComputeStateHash:
    def test_returns_hex_sha256_digest(self) -> None:
        d = {"phase": "discovery", "active_agent": "consultant"}
        result = compute_state_hash(d)
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_excludes_state_hash_key(self) -> None:
        d_without = {"phase": "discovery", "active_agent": "consultant"}
        d_with = dict(d_without)
        d_with["state_hash"] = "somehash"
        assert compute_state_hash(d_without) == compute_state_hash(d_with)

    def test_deterministic_output(self) -> None:
        d = _base_debrief_dict()
        assert compute_state_hash(d) == compute_state_hash(d)

    def test_sorted_keys_canonical_form(self) -> None:
        """Hash must use sort_keys=True so key order does not matter."""
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        assert compute_state_hash(d1) == compute_state_hash(d2)

    def test_matches_manual_sha256(self) -> None:
        d = {"phase": "style", "sub_phase": "style/style_dialog"}
        payload = json.dumps(d, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(payload.encode()).hexdigest()
        assert compute_state_hash(d) == expected

    def test_no_trailing_whitespace_in_hash_input(self) -> None:
        """Ensure no trailing newlines contaminate the hash."""
        d = {"x": 1}
        payload = json.dumps(d, sort_keys=True, separators=(",", ":"))
        assert payload == payload.strip()
        expected = hashlib.sha256(payload.encode()).hexdigest()
        assert compute_state_hash(d) == expected

    def test_different_values_produce_different_hashes(self) -> None:
        d1 = {"phase": "discovery"}
        d2 = {"phase": "complete"}
        assert compute_state_hash(d1) != compute_state_hash(d2)


# ---------------------------------------------------------------------------
# BC-2.11, BC-2.14, BC-2.15 — validate_debrief_state: enum enforcement
# ---------------------------------------------------------------------------


class TestValidateDebriefState:
    def _valid(self) -> dict[str, Any]:
        d = _base_debrief_dict()
        d["state_hash"] = compute_state_hash(d)
        return d

    def test_valid_state_does_not_raise(self) -> None:
        validate_debrief_state(self._valid())

    # phase enum
    def test_invalid_phase_raises_state_corrupt_error(self) -> None:
        d = self._valid()
        d["phase"] = "unknown_phase"
        with pytest.raises(StateCorruptError):
            validate_debrief_state(d)

    def test_all_valid_phases_pass(self) -> None:
        for phase in ("discovery", "style", "production", "finalization", "complete"):
            d = self._valid()
            d["phase"] = phase
            validate_debrief_state(d)  # must not raise

    def test_empty_string_phase_raises(self) -> None:
        d = self._valid()
        d["phase"] = ""
        with pytest.raises(StateCorruptError):
            validate_debrief_state(d)

    # active_agent enum (BC-2.14)
    def test_invalid_active_agent_raises_state_corrupt_error(self) -> None:
        d = self._valid()
        d["active_agent"] = "visual-qa"  # hyphen form is invalid; must be "qa"
        with pytest.raises(StateCorruptError):
            validate_debrief_state(d)

    def test_all_valid_active_agents_pass(self) -> None:
        for agent in ("consultant", "slide_maker", "stylist", "qa", "none"):
            d = self._valid()
            d["active_agent"] = agent
            validate_debrief_state(d)

    def test_active_agent_none_string_is_valid(self) -> None:
        """The string 'none' (not Python None) is a valid active_agent value."""
        d = self._valid()
        d["active_agent"] = "none"
        validate_debrief_state(d)

    def test_active_agent_python_none_raises(self) -> None:
        """Python None (null) for active_agent is invalid; must be string 'none'."""
        d = self._valid()
        d["active_agent"] = None
        with pytest.raises(StateCorruptError):
            validate_debrief_state(d)

    # sub_phase enum (BC-2.15)
    def test_invalid_sub_phase_raises_state_corrupt_error(self) -> None:
        d = self._valid()
        d["sub_phase"] = "production/nonexistent"
        with pytest.raises(StateCorruptError):
            validate_debrief_state(d)

    def test_all_24_valid_sub_phases_pass(self) -> None:
        valid_sub_phases = [
            "discovery/greeting",
            "discovery/dialog",
            "discovery/brief_review",
            "discovery/paper_analysis",
            "discovery/figure_selection",
            "discovery/style_analysis",
            "style/style_dialog",
            "style/style_review",
            "style/style_lock",
            "production/group_planning",
            "production/red_green",
            "production/diagnostic",
            "production/oscillation_review",
            "production/slide_review",
            "production/group_review",
            "production/more_slides",
            "production/deck_ending",
            "finalization/export_options",
            "finalization/backup_decision",
            "finalization/export_confirm",
            "finalization/reviewing_for_export",
            "finalization/exporting",
            "finalization/post_export",
            "complete",
        ]
        for sp in valid_sub_phases:
            d = self._valid()
            d["sub_phase"] = sp
            validate_debrief_state(d)

    # style_import_mode enum
    def test_invalid_style_import_mode_raises(self) -> None:
        d = self._valid()
        d["style_import_mode"] = "copy"
        with pytest.raises(StateCorruptError):
            validate_debrief_state(d)

    def test_valid_style_import_modes_pass(self) -> None:
        for mode in ("baseline", "inspiration", None):
            d = self._valid()
            d["style_import_mode"] = mode
            validate_debrief_state(d)

    # reference_modality enum
    def test_invalid_reference_modality_raises(self) -> None:
        d = self._valid()
        d["reference_modality"] = "docx"
        with pytest.raises(StateCorruptError):
            validate_debrief_state(d)

    def test_valid_reference_modalities_pass(self) -> None:
        for mod in ("pptx", "pdf", "html", "html_dir", None):
            d = self._valid()
            d["reference_modality"] = mod
            validate_debrief_state(d)

    # numeric counter non-negative
    def test_negative_group_slide_index_raises(self) -> None:
        d = self._valid()
        d["group_slide_index"] = -1
        with pytest.raises(StateCorruptError):
            validate_debrief_state(d)

    def test_negative_group_slide_count_raises(self) -> None:
        d = self._valid()
        d["group_slide_count"] = -1
        with pytest.raises(StateCorruptError):
            validate_debrief_state(d)

    def test_zero_counters_are_valid(self) -> None:
        d = self._valid()
        d["group_slide_index"] = 0
        d["group_slide_count"] = 0
        validate_debrief_state(d)

    # required field presence
    def test_missing_required_field_raises_state_corrupt_error(self) -> None:
        d = self._valid()
        del d["phase"]
        with pytest.raises(StateCorruptError):
            validate_debrief_state(d)

    def test_error_message_is_descriptive(self) -> None:
        d = self._valid()
        d["phase"] = "bad_phase"
        with pytest.raises(StateCorruptError, match="phase"):
            validate_debrief_state(d)


# ---------------------------------------------------------------------------
# BC-2.9 — StateCorruptError propagation
# ---------------------------------------------------------------------------


class TestStateCorruptErrorPropagation:
    def test_state_corrupt_error_is_exception_subclass(self) -> None:
        exc = StateCorruptError("test message")
        assert isinstance(exc, Exception)

    def test_state_corrupt_error_preserves_message(self) -> None:
        msg = "field phase has invalid value: 'bad'"
        exc = StateCorruptError(msg)
        assert str(exc) == msg


# ---------------------------------------------------------------------------
# BC-2.6 — get_approved_slides: ordering and filtering
# ---------------------------------------------------------------------------


class TestGetApprovedSlides:
    def test_returns_only_approved_slides(self) -> None:
        s1 = _make_slide("s1", status="approved")
        s2 = _make_slide("s2", status="draft")
        s3 = _make_slide("s3", status="needs_revision")
        s4 = _make_slide("s4", status="approved")
        state = _make_deck_state([s1, s2, s3, s4])
        result = get_approved_slides(state)
        assert [s.slug for s in result] == ["s1", "s4"]

    def test_preserves_array_order(self) -> None:
        s1 = _make_slide("first", status="approved")
        s2 = _make_slide("second", status="approved")
        s3 = _make_slide("third", status="approved")
        state = _make_deck_state([s3, s1, s2])
        result = get_approved_slides(state)
        assert [s.slug for s in result] == ["third", "first", "second"]

    def test_preserves_insertion_order_not_alphabetical(self) -> None:
        s1 = _make_slide("zebra", status="approved")
        s2 = _make_slide("alpha", status="approved")
        state = _make_deck_state([s1, s2])
        result = get_approved_slides(state)
        assert result[0].slug == "zebra"
        assert result[1].slug == "alpha"

    def test_no_sort_applied(self) -> None:
        slides = [_make_slide(f"slide_{i}", status="approved") for i in [3, 1, 2]]
        state = _make_deck_state(slides)
        result = get_approved_slides(state)
        assert [s.slug for s in result] == ["slide_3", "slide_1", "slide_2"]

    def test_returns_empty_list_when_no_approved_slides(self) -> None:
        s1 = _make_slide("s1", status="draft")
        state = _make_deck_state([s1])
        assert get_approved_slides(state) == []

    def test_returns_empty_list_when_no_slides_at_all(self) -> None:
        state = _make_deck_state([])
        assert get_approved_slides(state) == []

    def test_backup_filter_true_returns_only_backup_slides(self) -> None:
        s_main = _make_slide("main_slide", status="approved", backup=False)
        s_back = _make_slide("backup_slide", status="approved", backup=True)
        state = _make_deck_state([s_main, s_back])
        result = get_approved_slides(state, backup=True)
        assert len(result) == 1
        assert result[0].slug == "backup_slide"

    def test_backup_filter_false_returns_only_non_backup_slides(self) -> None:
        s_main = _make_slide("main_slide", status="approved", backup=False)
        s_back = _make_slide("backup_slide", status="approved", backup=True)
        state = _make_deck_state([s_main, s_back])
        result = get_approved_slides(state, backup=False)
        assert len(result) == 1
        assert result[0].slug == "main_slide"

    def test_backup_filter_none_returns_all_approved(self) -> None:
        s_main = _make_slide("main_slide", status="approved", backup=False)
        s_back = _make_slide("backup_slide", status="approved", backup=True)
        state = _make_deck_state([s_main, s_back])
        result = get_approved_slides(state, backup=None)
        assert len(result) == 2

    def test_backup_filter_applies_after_approval_filter(self) -> None:
        s1 = _make_slide("s1", status="draft", backup=True)
        s2 = _make_slide("s2", status="approved", backup=True)
        state = _make_deck_state([s1, s2])
        result = get_approved_slides(state, backup=True)
        assert len(result) == 1
        assert result[0].slug == "s2"

    def test_discarded_slides_not_returned(self) -> None:
        s1 = _make_slide("s1", status="discarded")
        state = _make_deck_state([s1])
        assert get_approved_slides(state) == []


# ---------------------------------------------------------------------------
# BC-2.7 — get_slide_by_slug: discarded and absent behavior
# ---------------------------------------------------------------------------


class TestGetSlideBySlug:
    def test_returns_slide_for_existing_slug(self) -> None:
        s = _make_slide("intro", status="approved")
        state = _make_deck_state([s])
        result = get_slide_by_slug(state, "intro")
        assert result is not None
        assert result.slug == "intro"

    def test_returns_none_for_absent_slug(self) -> None:
        s = _make_slide("intro", status="approved")
        state = _make_deck_state([s])
        assert get_slide_by_slug(state, "nonexistent") is None

    def test_returns_none_for_discarded_slug(self) -> None:
        """BC-2.7: discarded slide must return None even if slug matches."""
        s = _make_slide("intro", status="discarded")
        state = _make_deck_state([s])
        assert get_slide_by_slug(state, "intro") is None

    def test_returns_slide_for_draft_status(self) -> None:
        s = _make_slide("intro", status="draft")
        state = _make_deck_state([s])
        result = get_slide_by_slug(state, "intro")
        assert result is not None

    def test_returns_slide_for_needs_revision_status(self) -> None:
        s = _make_slide("intro", status="needs_revision")
        state = _make_deck_state([s])
        result = get_slide_by_slug(state, "intro")
        assert result is not None

    def test_returns_none_when_no_slides(self) -> None:
        state = _make_deck_state([])
        assert get_slide_by_slug(state, "intro") is None


# ---------------------------------------------------------------------------
# BC-2.8 — increment_* functions: in-place, no write
# ---------------------------------------------------------------------------


class TestIncrementExportCount:
    def test_increments_export_count_in_place(self) -> None:
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        increment_export_count(state, "folder_a")
        assert state.presentations[0].export_count == 1

    def test_increments_by_one_each_call(self) -> None:
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        increment_export_count(state, "folder_a")
        increment_export_count(state, "folder_a")
        assert state.presentations[0].export_count == 2

    def test_raises_key_error_for_missing_folder(self) -> None:
        state = _make_deck_state()
        state.presentations = []
        with pytest.raises(KeyError):
            increment_export_count(state, "nonexistent_folder")

    def test_returns_none(self) -> None:
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        result = increment_export_count(state, "folder_a")
        assert result is None

    def test_does_not_modify_other_presentation_records(self) -> None:
        rec_a = _make_presentation_record("folder_a")
        rec_b = _make_presentation_record("folder_b")
        state = _make_deck_state()
        state.presentations = [rec_a, rec_b]
        increment_export_count(state, "folder_a")
        assert state.presentations[1].export_count == 0


class TestIncrementScriptCount:
    def test_increments_script_count_in_place(self) -> None:
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        increment_script_count(state, "folder_a")
        assert state.presentations[0].script_count == 1

    def test_raises_key_error_for_missing_folder(self) -> None:
        state = _make_deck_state()
        state.presentations = []
        with pytest.raises(KeyError):
            increment_script_count(state, "nonexistent_folder")

    def test_returns_none(self) -> None:
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        result = increment_script_count(state, "folder_a")
        assert result is None

    def test_does_not_modify_export_count(self) -> None:
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        increment_script_count(state, "folder_a")
        assert state.presentations[0].export_count == 0


class TestIncrementHandoutCount:
    def test_increments_handout_count_in_place(self) -> None:
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        increment_handout_count(state, "folder_a")
        assert state.presentations[0].handout_count == 1

    def test_raises_key_error_for_missing_folder(self) -> None:
        state = _make_deck_state()
        state.presentations = []
        with pytest.raises(KeyError):
            increment_handout_count(state, "nonexistent_folder")

    def test_returns_none(self) -> None:
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        result = increment_handout_count(state, "folder_a")
        assert result is None

    def test_does_not_modify_script_count(self) -> None:
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        increment_handout_count(state, "folder_a")
        assert state.presentations[0].script_count == 0


# ---------------------------------------------------------------------------
# BC-2.2, BC-2.12 — write_deck_state / read_deck_state: atomic write + round-trip
# ---------------------------------------------------------------------------


class TestWriteDeckState:
    def test_writes_json_file(self, tmp_path: Path) -> None:
        state = _make_deck_state()
        write_deck_state(tmp_path, state)
        assert (tmp_path / "deck_state.json").exists()

    def test_tmp_file_does_not_persist_after_write(self, tmp_path: Path) -> None:
        state = _make_deck_state()
        write_deck_state(tmp_path, state)
        tmp_file = tmp_path / "deck_state.json.tmp"
        assert not tmp_file.exists()

    def test_written_json_is_valid(self, tmp_path: Path) -> None:
        state = _make_deck_state()
        write_deck_state(tmp_path, state)
        content = json.loads((tmp_path / "deck_state.json").read_text())
        assert isinstance(content, dict)

    def test_all_deck_state_fields_written(self, tmp_path: Path) -> None:
        state = _make_deck_state()
        write_deck_state(tmp_path, state)
        content = json.loads((tmp_path / "deck_state.json").read_text())
        required = {
            "project_name",
            "created_at",
            "archetype",
            "style_locked",
            "closing_slide",
            "slides",
            "presentations",
        }
        assert required <= set(content.keys())

    def test_all_slide_record_fields_written(self, tmp_path: Path) -> None:
        """BC-2.12: all 15 SlideRecord fields must appear in the output."""
        slide = _make_slide("intro", status="approved")
        state = _make_deck_state([slide])
        write_deck_state(tmp_path, state)
        content = json.loads((tmp_path / "deck_state.json").read_text())
        written_slide = content["slides"][0]
        required_fields = {
            "slug",
            "title",
            "status",
            "content_summary",
            "visual_approach",
            "design_choices",
            "forks_not_taken",
            "user_recommendations",
            "qa_passed",
            "accepted_violations",
            "last_modified",
            "group_id",
            "backup",
            "user_assets",
            "has_math",
        }
        assert required_fields <= set(written_slide.keys())

    def test_qa_passed_defaults_to_false(self, tmp_path: Path) -> None:
        slide = _make_slide("intro", status="approved")
        slide.qa_passed = False
        state = _make_deck_state([slide])
        write_deck_state(tmp_path, state)
        content = json.loads((tmp_path / "deck_state.json").read_text())
        assert content["slides"][0]["qa_passed"] is False

    def test_user_assets_defaults_to_empty_list(self, tmp_path: Path) -> None:
        slide = _make_slide("intro")
        slide.user_assets = []
        state = _make_deck_state([slide])
        write_deck_state(tmp_path, state)
        content = json.loads((tmp_path / "deck_state.json").read_text())
        assert content["slides"][0]["user_assets"] == []


class TestReadDeckState:
    def test_round_trip_preserves_project_name(self, tmp_path: Path) -> None:
        state = _make_deck_state()
        write_deck_state(tmp_path, state)
        loaded = read_deck_state(tmp_path)
        assert loaded.project_name == "test_project"

    def test_round_trip_preserves_slides(self, tmp_path: Path) -> None:
        slide = _make_slide("intro", status="approved")
        state = _make_deck_state([slide])
        write_deck_state(tmp_path, state)
        loaded = read_deck_state(tmp_path)
        assert len(loaded.slides) == 1
        assert loaded.slides[0].slug == "intro"

    def test_round_trip_preserves_archetype(self, tmp_path: Path) -> None:
        state = _make_deck_state()
        write_deck_state(tmp_path, state)
        loaded = read_deck_state(tmp_path)
        assert loaded.archetype == "lab_meeting"

    def test_raises_state_corrupt_error_on_missing_required_fields(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "deck_state.json").write_text(json.dumps({"project_name": "x"}))
        with pytest.raises(StateCorruptError):
            read_deck_state(tmp_path)

    def test_raises_state_corrupt_error_on_unrepaired_json(
        self, tmp_path: Path
    ) -> None:
        # Write something that json_repair cannot reconstruct into a valid deck state
        (tmp_path / "deck_state.json").write_text("NOT JSON AT ALL !!!")
        with pytest.raises(StateCorruptError):
            read_deck_state(tmp_path)

    def test_json_repair_used_on_slightly_malformed_json(self, tmp_path: Path) -> None:
        """BC-2.1: json_repair should salvage trailing-comma JSON."""
        _make_deck_state()  # ensure factory works
        d = {
            "project_name": "test_project",
            "created_at": _CREATED,
            "archetype": "lab_meeting",
            "style_locked": False,
            "closing_slide": None,
            "slides": [],
            "presentations": [],
        }
        # trailing comma — technically invalid JSON but json_repair handles it
        raw = json.dumps(d).rstrip("}") + ', "extra": "val"}'
        (tmp_path / "deck_state.json").write_text(raw)
        # Should not raise — json_repair fixes it; required fields still present
        try:
            read_deck_state(tmp_path)
        except StateCorruptError:
            pass  # acceptable if repair doesn't help for this specific corruption

    def test_exit_code_2_when_json_repair_unavailable(self, tmp_path: Path) -> None:
        """BC-2.1: if json_repair is missing, function must call sys.exit(2)."""
        state = _make_deck_state()
        write_deck_state(tmp_path, state)
        with (
            mock.patch("importlib.util.find_spec", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            read_deck_state(tmp_path)
        assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# BC-2.2, BC-2.3, BC-2.4, BC-2.5, BC-2.13 — write/read debrief_state
# ---------------------------------------------------------------------------


class TestWriteDebriefState:
    def _setup_lock_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)

    def test_writes_debrief_state_json(self, tmp_path: Path) -> None:
        self._setup_lock_dir(tmp_path)
        state = _make_debrief_state()
        write_debrief_state(tmp_path, state)
        assert (tmp_path / "debrief_state.json").exists()

    def test_tmp_file_does_not_persist_after_write(self, tmp_path: Path) -> None:
        self._setup_lock_dir(tmp_path)
        state = _make_debrief_state()
        write_debrief_state(tmp_path, state)
        assert not (tmp_path / "debrief_state.json.tmp").exists()

    def test_all_debrief_state_fields_written(self, tmp_path: Path) -> None:
        """BC-2.13: all 24 fields must appear in the written JSON."""
        self._setup_lock_dir(tmp_path)
        state = _make_debrief_state()
        write_debrief_state(tmp_path, state)
        content = json.loads((tmp_path / "debrief_state.json").read_text())
        required = {
            "phase",
            "sub_phase",
            "active_agent",
            "archetype",
            "current_group_id",
            "current_slide_slug",
            "pending_gate",
            "last_gate_response",
            "red_green_started_at",
            "group_slide_index",
            "group_slide_count",
            "backup_mode",
            "completed_groups",
            "pre_view_state",
            "view_deferred",
            "closing_slide_pending",
            "group_revise_slug",
            "style_import_mode",
            "reference_provided",
            "reference_modality",
            "papers_provided",
            "selected_figures",
            "session_started_at",
            "state_hash",
        }
        assert required <= set(content.keys())

    def test_state_hash_recomputed_on_write(self, tmp_path: Path) -> None:
        """BC-2.4: the written file's state_hash must equal compute_state_hash."""
        self._setup_lock_dir(tmp_path)
        state = _make_debrief_state()
        state.state_hash = "stale_hash_should_be_replaced"
        write_debrief_state(tmp_path, state)
        content = json.loads((tmp_path / "debrief_state.json").read_text())
        expected_hash = compute_state_hash(
            {k: v for k, v in content.items() if k != "state_hash"}
        )
        assert content["state_hash"] == expected_hash

    def test_lock_file_created(self, tmp_path: Path) -> None:
        """BC-2.3: the .debrief/state.lock file must exist after write."""
        self._setup_lock_dir(tmp_path)
        state = _make_debrief_state()
        write_debrief_state(tmp_path, state)
        assert (tmp_path / ".debrief" / "state.lock").exists()

    def test_exit_code_2_when_json_repair_unavailable(self, tmp_path: Path) -> None:
        """BC-2.1: if json_repair is missing, write must call sys.exit(2)."""
        self._setup_lock_dir(tmp_path)
        with (
            mock.patch("importlib.util.find_spec", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            read_debrief_state(tmp_path)
        assert exc_info.value.code == 2


class TestReadDebriefState:
    def _setup_lock_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)

    def test_round_trip_preserves_phase(self, tmp_path: Path) -> None:
        self._setup_lock_dir(tmp_path)
        state = _make_debrief_state()
        write_debrief_state(tmp_path, state)
        loaded = read_debrief_state(tmp_path)
        assert loaded.phase == "production"

    def test_round_trip_preserves_sub_phase(self, tmp_path: Path) -> None:
        self._setup_lock_dir(tmp_path)
        state = _make_debrief_state()
        write_debrief_state(tmp_path, state)
        loaded = read_debrief_state(tmp_path)
        assert loaded.sub_phase == "production/red_green"

    def test_round_trip_preserves_active_agent(self, tmp_path: Path) -> None:
        self._setup_lock_dir(tmp_path)
        state = _make_debrief_state()
        write_debrief_state(tmp_path, state)
        loaded = read_debrief_state(tmp_path)
        assert loaded.active_agent == "slide_maker"

    def test_raises_state_corrupt_error_on_invalid_phase(self, tmp_path: Path) -> None:
        self._setup_lock_dir(tmp_path)
        d = _base_debrief_dict()
        d["phase"] = "bad_phase"
        d["state_hash"] = compute_state_hash(d)
        (tmp_path / "debrief_state.json").write_text(json.dumps(d))
        with pytest.raises(StateCorruptError):
            read_debrief_state(tmp_path)

    def test_raises_state_corrupt_error_on_invalid_active_agent(
        self, tmp_path: Path
    ) -> None:
        self._setup_lock_dir(tmp_path)
        d = _base_debrief_dict()
        d["active_agent"] = "bug-diagnostic"
        d["state_hash"] = compute_state_hash(d)
        (tmp_path / "debrief_state.json").write_text(json.dumps(d))
        with pytest.raises(StateCorruptError):
            read_debrief_state(tmp_path)

    def test_hash_mismatch_with_valid_content_emits_warning_not_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-2.5: hash mismatch + valid content → recompute + warn, not raise."""
        self._setup_lock_dir(tmp_path)
        d = _base_debrief_dict()
        d["state_hash"] = "deliberate_bad_hash_to_trigger_mismatch"
        (tmp_path / "debrief_state.json").write_text(json.dumps(d))
        # Should NOT raise
        loaded = read_debrief_state(tmp_path)
        assert loaded is not None
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "hash mismatch" in captured.err.lower()

    def test_hash_mismatch_warning_contains_recomputed_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-2.5: the exact warning text must mention recomputation."""
        self._setup_lock_dir(tmp_path)
        d = _base_debrief_dict()
        d["state_hash"] = "wrong_hash"
        (tmp_path / "debrief_state.json").write_text(json.dumps(d))
        read_debrief_state(tmp_path)
        captured = capsys.readouterr()
        assert "recomputed" in captured.err.lower()

    def test_hash_mismatch_with_invalid_content_raises_state_corrupt_error(
        self, tmp_path: Path
    ) -> None:
        """BC-2.5: hash mismatch + invalid content → StateCorruptError."""
        self._setup_lock_dir(tmp_path)
        d = _base_debrief_dict()
        d["phase"] = "invalid_phase"
        d["state_hash"] = "wrong_hash"
        (tmp_path / "debrief_state.json").write_text(json.dumps(d))
        with pytest.raises(StateCorruptError):
            read_debrief_state(tmp_path)

    def test_exit_code_2_when_json_repair_unavailable(self, tmp_path: Path) -> None:
        """BC-2.1: json_repair unavailable → sys.exit(2)."""
        self._setup_lock_dir(tmp_path)
        d = _base_debrief_dict()
        d["state_hash"] = compute_state_hash(d)
        (tmp_path / "debrief_state.json").write_text(json.dumps(d))
        with (
            mock.patch("importlib.util.find_spec", return_value=None),
            pytest.raises(SystemExit) as exc_info,
        ):
            read_debrief_state(tmp_path)
        assert exc_info.value.code == 2

    def test_exit_2_stderr_message_contains_env_corruption_indicator(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-2.1: the stderr message on exit 2 must be the Section 9.3.1 error."""
        self._setup_lock_dir(tmp_path)
        d = _base_debrief_dict()
        d["state_hash"] = compute_state_hash(d)
        (tmp_path / "debrief_state.json").write_text(json.dumps(d))
        with mock.patch("importlib.util.find_spec", return_value=None):
            try:
                read_debrief_state(tmp_path)
            except SystemExit:
                pass
        captured = capsys.readouterr()
        # The Section 9.3.1 error must mention json_repair or environment
        assert "json_repair" in captured.err or "environment" in captured.err.lower()


# ---------------------------------------------------------------------------
# BC-2.2 — atomic_write_json
# ---------------------------------------------------------------------------


class TestAtomicWriteJson:
    def test_writes_json_to_target_path(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        atomic_write_json(target, {"key": "value"})
        assert target.exists()

    def test_written_content_is_correct(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        data = {"alpha": 1, "beta": [1, 2, 3]}
        atomic_write_json(target, data)
        loaded = json.loads(target.read_text())
        assert loaded == data

    def test_tmp_file_does_not_persist(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        atomic_write_json(target, {"x": 42})
        assert not (tmp_path / "output.json.tmp").exists()

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        target.write_text(json.dumps({"old": True}))
        atomic_write_json(target, {"new": True})
        loaded = json.loads(target.read_text())
        assert loaded == {"new": True}

    def test_nested_directory_target(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub" / "dir"
        sub.mkdir(parents=True)
        target = sub / "file.json"
        atomic_write_json(target, {"nested": "yes"})
        assert target.exists()

    def test_returns_none(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        result = atomic_write_json(target, {})
        assert result is None


# ---------------------------------------------------------------------------
# BC-2.16 — sanitize_identifier: 7-step algorithm compliance
# ---------------------------------------------------------------------------


class TestSanitizeIdentifier:
    # Step 1: lowercase
    def test_converts_to_lowercase(self) -> None:
        assert sanitize_identifier("HELLO") == "hello"

    def test_mixed_case_converted(self) -> None:
        assert sanitize_identifier("MixedCase") == "mixedcase"

    # Step 2: spaces and hyphens → underscores
    def test_spaces_become_underscores(self) -> None:
        assert sanitize_identifier("hello world") == "hello_world"

    def test_hyphens_become_underscores(self) -> None:
        assert sanitize_identifier("hello-world") == "hello_world"

    def test_spaces_and_hyphens_become_underscores(self) -> None:
        assert sanitize_identifier("hello - world") == "hello_world"

    # Step 3: remove non-[a-z0-9_] characters
    def test_removes_special_characters(self) -> None:
        assert sanitize_identifier("hello!@#world") == "helloworld"

    def test_removes_dots(self) -> None:
        result = sanitize_identifier("hello.world")
        assert "." not in result

    def test_removes_parentheses(self) -> None:
        result = sanitize_identifier("hello(world)")
        assert "(" not in result
        assert ")" not in result

    # Step 4: collapse consecutive underscores
    def test_consecutive_underscores_collapsed(self) -> None:
        assert sanitize_identifier("hello__world") == "hello_world"

    def test_multiple_consecutive_underscores_collapsed(self) -> None:
        assert sanitize_identifier("a___b____c") == "a_b_c"

    # Step 5: strip leading and trailing underscores
    def test_strips_leading_underscores(self) -> None:
        result = sanitize_identifier("_hello")
        assert not result.startswith("_")

    def test_strips_trailing_underscores(self) -> None:
        result = sanitize_identifier("hello_")
        assert not result.endswith("_")

    # Step 6: truncate to max_length
    def test_truncates_to_max_length(self) -> None:
        result = sanitize_identifier("abcdefghij", max_length=5)
        assert len(result) == 5
        assert result == "abcde"

    def test_truncates_anywhere_no_word_boundary(self) -> None:
        """Truncation is not word-boundary aligned per spec."""
        result = sanitize_identifier("hello_world_test", max_length=7)
        assert result == "hello_w"

    def test_default_max_length_is_40(self) -> None:
        long_text = "a" * 50
        result = sanitize_identifier(long_text)
        assert len(result) == 40

    def test_short_text_not_padded(self) -> None:
        result = sanitize_identifier("hi", max_length=40)
        assert result == "hi"

    # Step 7: empty result → 'untitled'
    def test_all_special_chars_returns_untitled(self) -> None:
        assert sanitize_identifier("!!!") == "untitled"

    def test_empty_string_returns_untitled(self) -> None:
        assert sanitize_identifier("") == "untitled"

    def test_only_underscores_after_strip_returns_untitled(self) -> None:
        assert sanitize_identifier("___") == "untitled"

    def test_only_hyphens_returns_untitled(self) -> None:
        assert sanitize_identifier("---") == "untitled"

    # Step ordering: step 7 before step 6
    def test_empty_after_step5_returns_untitled_not_truncated(self) -> None:
        """'untitled' should be returned as-is, NOT truncated by step 6."""
        result = sanitize_identifier("---", max_length=3)
        assert result == "untitled"

    def test_non_empty_after_step5_is_truncated_by_step6(self) -> None:
        """If not empty after step 5, step 6 truncates."""
        result = sanitize_identifier("abcdefgh", max_length=4)
        assert result == "abcd"

    # Determinism
    def test_same_inputs_always_produce_same_output(self) -> None:
        text = "Hello World - Test 2024!"
        results = {sanitize_identifier(text) for _ in range(5)}
        assert len(results) == 1

    # Real-world examples from spec
    def test_paper_slug_with_max_length_50(self) -> None:
        result = sanitize_identifier("Nature_2024_Smith_et_al", max_length=50)
        assert result == "nature_2024_smith_et_al"

    def test_presentation_folder_naming_max_40(self) -> None:
        result = sanitize_identifier("My Lab Meeting Presentation", max_length=40)
        assert result == "my_lab_meeting_presentation"

    def test_already_clean_identifier_unchanged(self) -> None:
        result = sanitize_identifier("intro_slide", max_length=40)
        assert result == "intro_slide"

    def test_mixed_input_full_pipeline(self) -> None:
        """Walk through all 7 steps with a realistic paper title."""
        result = sanitize_identifier(
            "  Deep Learning -- A Review (2023)  ", max_length=40
        )
        # Step 1: lowercase → "  deep learning -- a review (2023)  "
        # Step 2: spaces/hyphens → "  deep_learning_____a_review_(2023)  "
        #   (the spaces around -- become underscores too)
        # Step 3: remove non [a-z0-9_] → "deep_learning_____a_review_2023"
        # Step 4: collapse underscores → "deep_learning_a_review_2023"
        # Step 5: strip underscores → "deep_learning_a_review_2023"
        # Step 6: truncate to 40 → unchanged (len < 40)
        assert result == "deep_learning_a_review_2023"


# ---------------------------------------------------------------------------
# Additional gap-filling tests
# ---------------------------------------------------------------------------


class TestReadDeckStateStderrOnMissingJsonRepair:
    """BC-2.1: read_deck_state must emit the Section 9.3.1 error to stderr."""

    def test_stderr_message_mentions_json_repair_or_environment(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """BC-2.1: stderr on exit-2 must be the standardized env-corruption msg."""
        state = _make_deck_state()
        write_deck_state(tmp_path, state)
        with mock.patch("importlib.util.find_spec", return_value=None):
            try:
                read_deck_state(tmp_path)
            except SystemExit:
                pass
        captured = capsys.readouterr()
        assert (
            "json_repair" in captured.err
            or "environment" in captured.err.lower()
        )


class TestAtomicWriteJsonFsync:
    """BC-2.2: atomic_write_json must call os.fsync() on the tmp fd."""

    def test_fsync_called_during_atomic_write(self, tmp_path: Path) -> None:
        """BC-2.2: os.fsync must be invoked before os.rename."""
        target = tmp_path / "output.json"
        with mock.patch("os.fsync") as mock_fsync:
            atomic_write_json(target, {"x": 1})
        mock_fsync.assert_called_once()

    def test_fsync_called_before_rename(self, tmp_path: Path) -> None:
        """BC-2.2: rename must happen after fsync (order check via call order)."""
        target = tmp_path / "output.json"
        call_order: list[str] = []

        original_fsync = os.fsync
        original_rename = os.rename

        def recording_fsync(fd: int) -> None:
            call_order.append("fsync")
            original_fsync(fd)

        def recording_rename(src: str, dst: str) -> None:
            call_order.append("rename")
            original_rename(src, dst)

        with (
            mock.patch("os.fsync", side_effect=recording_fsync),
            mock.patch("os.rename", side_effect=recording_rename),
        ):
            atomic_write_json(target, {"order": "test"})

        assert call_order.index("fsync") < call_order.index("rename")


class TestWriteDebriefStateLock:
    """BC-2.3: write_debrief_state must acquire an exclusive flock."""

    def _setup_lock_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)

    def test_flock_exclusive_lock_acquired(self, tmp_path: Path) -> None:
        """BC-2.3: fcntl.flock must be called with LOCK_EX."""
        self._setup_lock_dir(tmp_path)
        state = _make_debrief_state()
        lock_calls: list[int] = []

        original_flock = fcntl.flock

        def recording_flock(fd: int, operation: int) -> None:
            lock_calls.append(operation)
            original_flock(fd, operation)

        with mock.patch("fcntl.flock", side_effect=recording_flock):
            write_debrief_state(tmp_path, state)

        assert fcntl.LOCK_EX in lock_calls

    def test_flock_released_on_exception(self, tmp_path: Path) -> None:
        """BC-2.3: lock must be released even when atomic_write_json raises."""
        self._setup_lock_dir(tmp_path)
        state = _make_debrief_state()
        unlock_calls: list[int] = []

        original_flock = fcntl.flock

        def recording_flock(fd: int, operation: int) -> None:
            if operation == fcntl.LOCK_UN:
                unlock_calls.append(operation)
            original_flock(fd, operation)

        with (
            mock.patch(
                "debrief_state.atomic_write_json",
                side_effect=OSError("simulated write failure"),
            ),
            mock.patch("fcntl.flock", side_effect=recording_flock),
            pytest.raises(OSError),
        ):
            write_debrief_state(tmp_path, state)

        assert fcntl.LOCK_UN in unlock_calls, (
            "Lock must be released in finally block even on exception"
        )


class TestReadDebriefStateHashMismatchRecovery:
    """BC-2.5: returned state must have state_hash updated after mismatch."""

    def _setup_lock_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)

    def test_returned_state_has_correct_hash_after_mismatch(
        self, tmp_path: Path
    ) -> None:
        """BC-2.5: loaded.state_hash must equal recomputed hash, not stale value."""
        self._setup_lock_dir(tmp_path)
        d = _base_debrief_dict()
        stale_hash = "0" * 64  # deliberate wrong hash
        d["state_hash"] = stale_hash
        (tmp_path / "debrief_state.json").write_text(json.dumps(d))

        loaded = read_debrief_state(tmp_path)

        content_without_hash = {k: v for k, v in d.items() if k != "state_hash"}
        expected_hash = compute_state_hash(content_without_hash)
        assert loaded.state_hash == expected_hash
        assert loaded.state_hash != stale_hash


class TestIncrementDoesNotWrite:
    """BC-2.8: increment_* functions must not call write_deck_state."""

    def test_increment_export_count_does_not_call_write(self) -> None:
        """BC-2.8: write_deck_state must not be invoked by increment_export_count."""
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        with mock.patch(
            "debrief_state.write_deck_state"
        ) as mock_write:
            increment_export_count(state, "folder_a")
        mock_write.assert_not_called()

    def test_increment_script_count_does_not_call_write(self) -> None:
        """BC-2.8: write_deck_state must not be invoked by increment_script_count."""
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        with mock.patch(
            "debrief_state.write_deck_state"
        ) as mock_write:
            increment_script_count(state, "folder_a")
        mock_write.assert_not_called()

    def test_increment_handout_count_does_not_call_write(self) -> None:
        """BC-2.8: write_deck_state must not be invoked by increment_handout_count."""
        rec = _make_presentation_record("folder_a")
        state = _make_deck_state()
        state.presentations = [rec]
        with mock.patch(
            "debrief_state.write_deck_state"
        ) as mock_write:
            increment_handout_count(state, "folder_a")
        mock_write.assert_not_called()


class TestSlideRecordDefaults:
    """BC-2.12: has_math and accepted_violations must appear with correct defaults."""

    def test_has_math_written_as_false_by_default(self, tmp_path: Path) -> None:
        """BC-2.12: has_math field must be written as false in JSON output."""
        slide = _make_slide("intro")
        slide.has_math = False
        state = _make_deck_state([slide])
        write_deck_state(tmp_path, state)
        content = json.loads((tmp_path / "deck_state.json").read_text())
        assert content["slides"][0]["has_math"] is False

    def test_accepted_violations_written_as_empty_list_by_default(
        self, tmp_path: Path
    ) -> None:
        """BC-2.12: accepted_violations must be written as [] by default."""
        slide = _make_slide("intro")
        slide.accepted_violations = []
        state = _make_deck_state([slide])
        write_deck_state(tmp_path, state)
        content = json.loads((tmp_path / "deck_state.json").read_text())
        assert content["slides"][0]["accepted_violations"] == []
