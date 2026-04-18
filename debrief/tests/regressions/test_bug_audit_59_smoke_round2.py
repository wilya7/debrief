# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-59.

Smoke test Round 2 found 13 real bugs across the 10-step conference_talk
workflow. This file covers:

- BUG-ST-5:  Consultant-as-Tier-2-dispatcher (slide-maker no longer
             dispatches visual-qa via Task)
- BUG-ST-12: Script generator transition extraction from content_summary
- BUG-ST-13: Script generator time-pacing checkpoints
- BUG-ST-14: skill_quit removes .debrief/state.lock
- BUG-ST-15: debrief_state CLI helpers (update + append_ledger)
- BUG-ST-1:  check_duration archetype validation
- BUG-ST-2:  style_analyzer success output
- BUG-ST-6:  rough.js load guard in slide-maker.md
- BUG-ST-8:  append_ledger_entry helper in debrief_state.py
- BUG-ST-9:  export success message (structural check)
- BUG-ST-11: handout in utility_skills CLI
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


# Add source directories to sys.path
for _dir in (
    _PROJECT_ROOT / "src" / ("unit_11" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_3" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_7" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_10" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402
import debrief_state  # noqa: E402
import launcher  # noqa: E402


# ---------------------------------------------------------------------------
# Slide-maker.md path helper
# ---------------------------------------------------------------------------


def _slide_maker_md_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "agents" / "slide-maker.md"
    delivered = _PROJECT_ROOT / "agents" / "slide-maker.md"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError("slide-maker.md not found")


def _consultant_md_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    delivered = _PROJECT_ROOT / "agents" / "consultant.md"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError("consultant.md not found")


def _archetypes_json_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "archetypes.json"
    delivered = _PROJECT_ROOT / "archetypes.json"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError("archetypes.json not found")


# ---------------------------------------------------------------------------
# Slide record helpers
# ---------------------------------------------------------------------------

_TS = "2026-04-18T12:00:00Z"


class _FakeSlide:
    def __init__(self, slug: str, title: str, content_summary: str = "",
                 transition: str | None = None):
        self.slug = slug
        self.title = title
        self.content_summary = content_summary
        self.status = "approved"
        self.backup = False
        if transition is not None:
            self.transition = transition


# ---------------------------------------------------------------------------
# BUG-ST-5: Consultant dispatches Tier 2 (not slide-maker)
# ---------------------------------------------------------------------------


class TestBugST5ConsultantDispatchesTier2:
    """BUG-AUDIT-59 / BUG-ST-5: slide-maker no longer claims to dispatch
    visual-qa via Task. Consultant.md contains the Tier 2 dispatch section.
    """

    def test_slide_maker_does_not_instruct_task_dispatch_as_final_action(
        self,
    ) -> None:
        text = _slide_maker_md_path().read_text(encoding="utf-8")
        # The old instruction "absolute final action" + "Do NOT return"
        # should be gone.
        assert "absolute final action" not in text, (
            "BUG-AUDIT-59 / BUG-ST-5: slide-maker.md must not instruct "
            "Task dispatch as its 'absolute final action' — this is now "
            "the consultant's responsibility."
        )

    def test_slide_maker_mentions_consultant_dispatches_tier2(self) -> None:
        text = _slide_maker_md_path().read_text(encoding="utf-8")
        assert "consultant" in text.lower(), (
            "BUG-AUDIT-59 / BUG-ST-5: slide-maker.md should mention that "
            "the consultant dispatches Tier 2."
        )

    def test_consultant_has_tier2_dispatch_section(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "Tier 2 QA Dispatch" in text, (
            "BUG-AUDIT-59 / BUG-ST-5: consultant.md must contain a "
            "'Tier 2 QA Dispatch' section."
        )

    def test_consultant_tier2_mentions_visual_qa(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        # Find the Tier 2 section and check it mentions visual-qa
        idx = text.find("Tier 2 QA Dispatch")
        assert idx >= 0
        section = text[idx:idx + 800]
        assert "visual-qa" in section, (
            "BUG-AUDIT-59 / BUG-ST-5: Tier 2 QA Dispatch section must "
            "mention visual-qa."
        )

    def test_slide_maker_cites_bug_audit_59(self) -> None:
        text = _slide_maker_md_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-59" in text, (
            "BUG-AUDIT-59 / BUG-ST-5: slide-maker.md must cite "
            "BUG-AUDIT-59 for traceability."
        )


# ---------------------------------------------------------------------------
# BUG-ST-6: rough.js load guard in slide-maker.md
# ---------------------------------------------------------------------------


class TestBugST6RoughjsLoadGuard:
    def test_slide_maker_mentions_load_guard(self) -> None:
        text = _slide_maker_md_path().read_text(encoding="utf-8")
        assert "load" in text and "requestAnimationFrame" in text, (
            "BUG-AUDIT-59 / BUG-ST-6: slide-maker.md must instruct "
            "wrapping rough.js canvas code in window.addEventListener"
            "('load', ...) + requestAnimationFrame."
        )


# ---------------------------------------------------------------------------
# BUG-ST-12: Transition extraction from content_summary
# ---------------------------------------------------------------------------


class TestBugST12TransitionExtraction:
    """BUG-AUDIT-59 / BUG-ST-12: generate_script_content extracts
    transition sentences from content_summary."""

    def test_extract_transition_finds_signal_in_last_sentence(self) -> None:
        summary = (
            "AI has solved code. This sets the stage for why it matters."
        )
        points, trans = utility_skills._extract_transition(summary)
        assert trans is not None, (
            "BUG-ST-12: _extract_transition must find 'sets the stage' "
            "in the last sentence."
        )
        assert "sets the stage" in trans
        assert "AI has solved code" in points

    def test_extract_transition_returns_none_when_no_signal(self) -> None:
        summary = "AI has solved code. Performance is excellent."
        _, trans = utility_skills._extract_transition(summary)
        assert trans is None, (
            "BUG-ST-12: _extract_transition must return None when no "
            "transition signal is present."
        )

    def test_extract_transition_single_sentence_returns_none(self) -> None:
        summary = "AI has solved code."
        _, trans = utility_skills._extract_transition(summary)
        assert trans is None

    def test_script_content_uses_extracted_transition(self) -> None:
        slides = [
            _FakeSlide(
                "s1", "Slide One",
                "AI has changed everything. This sets the stage for what's next.",
            ),
            _FakeSlide("s2", "Slide Two", "Deep learning rocks."),
        ]
        content = utility_skills.generate_script_content(
            "Brief", slides, "test_folder",
        )
        # Slide 1 should have the extracted transition, not the placeholder
        assert "sets the stage" in content
        assert "Lead into **Slide Two** by connecting" not in content, (
            "BUG-ST-12: placeholder transition must not appear when a "
            "real transition was extracted from content_summary."
        )

    def test_script_content_uses_placeholder_when_no_transition(self) -> None:
        slides = [
            _FakeSlide("s1", "Slide One", "Some topic."),
            _FakeSlide("s2", "Slide Two", "Another topic."),
        ]
        content = utility_skills.generate_script_content(
            "Brief", slides, "test_folder",
        )
        assert "Lead into **Slide Two**" in content

    def test_explicit_transition_field_takes_priority(self) -> None:
        slides = [
            _FakeSlide(
                "s1", "Slide One", "Topic summary.",
                transition="Custom transition text here.",
            ),
            _FakeSlide("s2", "Slide Two", "Another."),
        ]
        content = utility_skills.generate_script_content(
            "Brief", slides, "test_folder",
        )
        assert "Custom transition text here." in content


# ---------------------------------------------------------------------------
# BUG-ST-13: Time-pacing checkpoints
# ---------------------------------------------------------------------------


class TestBugST13TimePacingCheckpoints:
    """BUG-AUDIT-59 / BUG-ST-13: Script generator inserts time checkpoints
    when total_duration_minutes is provided."""

    def test_checkpoints_present_when_duration_provided(self) -> None:
        slides = [_FakeSlide(f"s{i}", f"Slide {i}") for i in range(1, 5)]
        content = utility_skills.generate_script_content(
            "Brief", slides, "folder", total_duration_minutes=20.0,
        )
        assert "TIME CHECK" in content, (
            "BUG-ST-13: Script must contain TIME CHECK markers when "
            "total_duration_minutes is provided."
        )
        # Should have halfway marker at minimum
        assert "halfway" in content.lower()

    def test_no_checkpoints_when_no_duration(self) -> None:
        slides = [_FakeSlide(f"s{i}", f"Slide {i}") for i in range(1, 5)]
        content = utility_skills.generate_script_content(
            "Brief", slides, "folder", total_duration_minutes=None,
        )
        assert "TIME CHECK" not in content

    def test_per_slide_time_computed_from_duration(self) -> None:
        slides = [_FakeSlide(f"s{i}", f"Slide {i}") for i in range(1, 5)]
        content = utility_skills.generate_script_content(
            "Brief", slides, "folder", total_duration_minutes=20.0,
        )
        # 20 minutes / 4 slides = 5.0 minutes per slide
        assert "~5.0 minutes" in content, (
            "BUG-ST-13: Per-slide time must be computed from total "
            "duration / slide count."
        )

    def test_parse_duration_from_brief_explicit_label(self) -> None:
        brief = "# Deck Brief\n\nDuration: 15 minutes\n\nTopic: AI"
        result = utility_skills._parse_duration_from_brief(brief)
        assert result == 15.0

    def test_parse_duration_from_brief_inline(self) -> None:
        brief = "This is a 20-minute conference talk about AI."
        result = utility_skills._parse_duration_from_brief(brief)
        assert result == 20.0

    def test_parse_duration_returns_none_when_absent(self) -> None:
        brief = "This is a talk about AI. No timing info."
        result = utility_skills._parse_duration_from_brief(brief)
        assert result is None

    def test_target_duration_shown_in_header(self) -> None:
        slides = [_FakeSlide("s1", "Slide 1")]
        content = utility_skills.generate_script_content(
            "Brief", slides, "folder", total_duration_minutes=10.0,
        )
        assert "Target duration" in content


# ---------------------------------------------------------------------------
# BUG-ST-14: skill_quit removes state.lock
# ---------------------------------------------------------------------------


class TestBugST14StateLockCleanup:
    """BUG-AUDIT-59 / BUG-ST-14: skill_quit deletes .debrief/state.lock."""

    def test_state_lock_removed_after_quit(self, tmp_path: Path) -> None:
        # Set up a minimal project
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        lock_file = debrief_dir / "state.lock"
        lock_file.write_text("")

        # Write minimal state files (matching full schema)
        deck_state = {
            "project_name": "test",
            "created_at": _TS,
            "archetype": "conference_talk",
            "style_locked": False,
            "closing_slide": None,
            "slides": [],
            "presentations": [],
        }
        (tmp_path / "deck_state.json").write_text(json.dumps(deck_state))

        debrief_st = {
            "phase": "discovery",
            "sub_phase": "discovery/greeting",
            "active_agent": "none",
            "archetype": "conference_talk",
            "current_group_id": None,
            "current_slide_slug": None,
            "pending_gate": None,
            "last_gate_response": None,
            "red_green_started_at": None,
            "group_slide_index": 0,
            "group_slide_count": 0,
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
            "session_started_at": _TS,
            "state_hash": "",
        }
        (tmp_path / "debrief_state.json").write_text(json.dumps(debrief_st))

        utility_skills.skill_quit(tmp_path)

        assert not lock_file.exists(), (
            "BUG-ST-14: .debrief/state.lock must be deleted after quit."
        )


# ---------------------------------------------------------------------------
# BUG-ST-15: debrief_state CLI helpers
# ---------------------------------------------------------------------------


class TestBugST15DebriefStateCLI:
    """BUG-AUDIT-59 / BUG-ST-15: debrief_state.py exposes update and
    append_ledger CLI subcommands."""

    def test_cli_update_state_function_exists(self) -> None:
        assert hasattr(debrief_state, "cli_update_state"), (
            "BUG-ST-15: debrief_state must expose cli_update_state."
        )

    def test_append_ledger_entry_function_exists(self) -> None:
        assert hasattr(debrief_state, "append_ledger_entry"), (
            "BUG-ST-8/15: debrief_state must expose append_ledger_entry."
        )

    def test_append_ledger_entry_writes_to_file(self, tmp_path: Path) -> None:
        debrief_state.append_ledger_entry(tmp_path, "test_event", "detail")
        ledger_path = tmp_path / "ledger.jsonl"
        assert ledger_path.exists(), "append_ledger_entry must create ledger.jsonl"
        entry = json.loads(ledger_path.read_text().strip())
        assert entry["metadata"]["event"] == "test_event"
        assert "detail" in entry["content"]

    def test_cli_update_state_modifies_and_rehashes(
        self, tmp_path: Path,
    ) -> None:
        # Write initial state
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        initial = {
            "phase": "discovery",
            "sub_phase": "discovery/greeting",
            "active_agent": "none",
            "archetype": "conference_talk",
            "current_group_id": None,
            "current_slide_slug": None,
            "pending_gate": None,
            "last_gate_response": None,
            "red_green_started_at": None,
            "group_slide_index": 0,
            "group_slide_count": 0,
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
            "session_started_at": _TS,
            "state_hash": "",
        }
        (tmp_path / "debrief_state.json").write_text(json.dumps(initial))

        debrief_state.cli_update_state(
            tmp_path, ["phase=production", "sub_phase=production/group_planning"],
        )

        # Re-read and verify
        updated = json.loads(
            (tmp_path / "debrief_state.json").read_text()
        )
        assert updated["phase"] == "production"
        assert updated["sub_phase"] == "production/group_planning"
        # Hash should be recomputed (non-empty)
        assert updated.get("state_hash", "") != ""

        # Ledger should have an entry (auto-append from write_debrief_state)
        ledger = tmp_path / "ledger.jsonl"
        assert ledger.exists(), (
            "BUG-ST-15: cli_update_state must trigger ledger auto-append."
        )


# ---------------------------------------------------------------------------
# BUG-ST-1: check_duration archetype validation
# ---------------------------------------------------------------------------


class TestBugST1CheckDuration:
    """BUG-AUDIT-59 / BUG-ST-1: check_duration validates user-specified
    duration against archetype time_range."""

    def test_duration_in_range(self) -> None:
        apath = _archetypes_json_path()
        ok, msg = launcher.check_duration(apath, "conference_talk", 20)
        assert ok, f"20 min should be in conference_talk range. Got: {msg}"

    def test_duration_below_range(self) -> None:
        apath = _archetypes_json_path()
        ok, msg = launcher.check_duration(apath, "conference_talk", 5)
        assert not ok, "5 min should be below conference_talk range"
        assert "WARNING" in msg
        assert "below" in msg

    def test_duration_above_range(self) -> None:
        apath = _archetypes_json_path()
        ok, msg = launcher.check_duration(apath, "conference_talk", 60)
        assert not ok, "60 min should be above conference_talk range"
        assert "above" in msg

    def test_custom_archetype_any_duration(self) -> None:
        apath = _archetypes_json_path()
        ok, msg = launcher.check_duration(apath, "custom", 999)
        assert ok, "custom archetype should accept any duration"

    def test_unknown_archetype(self) -> None:
        apath = _archetypes_json_path()
        ok, msg = launcher.check_duration(apath, "nonexistent", 10)
        assert not ok


# ---------------------------------------------------------------------------
# BUG-ST-2: style_analyzer success output (structural)
# ---------------------------------------------------------------------------


class TestBugST2StyleAnalyzerOutput:
    """BUG-AUDIT-59 / BUG-ST-2: main_style_analyzer prints success to stderr."""

    def test_success_print_in_source(self) -> None:
        # Structural check: the source must contain the success print.
        if _is_workspace_layout():
            src = (_PROJECT_ROOT / "src" / "unit_7" / "slide_maker.py")
        else:
            src = (_PROJECT_ROOT / "src" / "debrief" / "slide_maker.py")
        text = src.read_text(encoding="utf-8")
        assert "Imported" in text and "analyzer_metadata" in text, (
            "BUG-ST-2: main_style_analyzer must print a success message "
            "containing 'Imported' and 'analyzer_metadata'."
        )


# ---------------------------------------------------------------------------
# BUG-ST-9: export success message (structural)
# ---------------------------------------------------------------------------


class TestBugST9ExportSuccessMessage:
    """BUG-AUDIT-59 / BUG-ST-9: export prints PDF path on success."""

    def test_success_print_in_export_source(self) -> None:
        if _is_workspace_layout():
            src = (_PROJECT_ROOT / "src" / "unit_10" / "export.py")
        else:
            src = (_PROJECT_ROOT / "src" / "debrief" / "export.py")
        text = src.read_text(encoding="utf-8")
        assert "Wrote" in text and "slides" in text, (
            "BUG-ST-9: export.py must print a success message containing "
            "'Wrote' and 'slides'."
        )


# ---------------------------------------------------------------------------
# BUG-ST-11: handout in utility_skills CLI
# ---------------------------------------------------------------------------


class TestBugST11HandoutCLI:
    """BUG-AUDIT-59 / BUG-ST-11: utility_skills __main__ includes handout."""

    def test_handout_in_cli_source(self) -> None:
        if _is_workspace_layout():
            src = (_PROJECT_ROOT / "src" / "unit_11" / "utility_skills.py")
        else:
            src = (_PROJECT_ROOT / "src" / "debrief" / "utility_skills.py")
        text = src.read_text(encoding="utf-8")
        assert '"handout"' in text, (
            "BUG-ST-11: utility_skills __main__ must include 'handout' "
            "as a command choice."
        )
        assert '--mode' in text, (
            "BUG-ST-11: utility_skills __main__ must include '--mode' "
            "argument for handout."
        )
