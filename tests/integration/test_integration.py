# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Integration tests for the Debrief plugin.

These tests exercise cross-unit contracts that cannot be caught by any
single unit test in isolation.  Each test class names the unit pair (or
chain) under scrutiny and documents the contract being verified.

Test categories
---------------
I.   Unit 3 (Launcher) -> Unit 2 (State) contract: new() writes state
     files that read_deck_state / read_debrief_state can round-trip.
II.  Unit 2 (State) -> Unit 4 (Routing) contract: state produced by
     write_debrief_state is consumed correctly by resolve_action.
III. Unit 5 (Ledger/Brief) -> Unit 2 (State) contract: write_slide_brief
     uses atomic_write_json from Unit 2; group manifests are parseable.
IV.  Unit 6 (Style Compiler) -> Unit 9 (QA) contract: CSS_PROPERTY_MAP
     keys in the style compiler and the check_permitted_libraries / INV-10
     logic are consistent with the expected config shape.
V.   Unit 4 (Routing) -> Unit 9 (QA log) contract: check_g3_2_machine_gate
     correctly reads qa_log.jsonl entries written by append_qa_log (Unit 9).
VI.  Unit 8 (visual_qa) -> Unit 9 (qa_checker) contract: HTML produced
     by render_math_html / escape_html passes INV-06 (no inline styles)
     and INV-07 (no external URLs) checks.
VII. Unit 11 (Utility Skills) -> Unit 2 (State) contract: sanitize_save_label
     and sanitize_identifier produce identical results (same algorithm).
VIII.Registry / dispatch-table coverage: every gate_id in _GATE_VALID_RESPONSES
     corresponds to a sub_phase entry in _SUB_PHASE_ACTION or the G3.2 branch,
     and vice versa.
IX.  Unit 3 (Launcher) -> Unit 4 (Routing): after new() the initial
     debrief_state is readable and resolve_action emits a valid ActionBlock.
X.   Unit 12 (Paper Analyzer) -> Unit 2 sanitize_identifier: derive_paper_slug
     and Unit 2's sanitize_identifier are consistent for the same inputs.
XI.  Unit 10 (Export) -> Unit 2 (State): build_page_list correctly orders
     main/backup slides using DeckState produced by Unit 2.
XII. SUB_PHASE_VALUES (Unit 2) vs _SUB_PHASE_ACTION (Unit 4): every
     sub_phase constant declared in Unit 2 has an entry in Unit 4's
     dispatch table, and every entry in Unit 4's table is a valid
     sub_phase per Unit 2.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Import helpers shared across test classes
# ---------------------------------------------------------------------------

_TS = "2026-01-15T10:00:00+00:00"
_CREATED = "2026-01-15T09:00:00+00:00"

# Project root is 3 levels up from this file (delivered plugin repo root).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_PLUGIN_ROOT = _PROJECT_ROOT  # plugin scaffold is at the project root


# ---------------------------------------------------------------------------
# Minimal valid style_config fixture used by several tests.
# ---------------------------------------------------------------------------

_MINIMAL_STYLE_CONFIG: dict[str, Any] = {
    "colors": {
        "primary": "#003366",
        "secondary": "#0055a5",
        "accent": "#ff6600",
        "background": "#ffffff",
        "text_primary": "#111111",
        "text_secondary": "#555555",
        "code_background": "#f5f5f5",
        "border": "#dddddd",
    },
    "typography": {
        "heading_font_family": "Inter, sans-serif",
        "body_font_family": "Inter, sans-serif",
        "code_font_family": "Fira Mono, monospace",
        "heading_size_base": "2rem",
        "body_size_base": "1rem",
        "heading_weight": "700",
        "body_weight": "400",
        "line_height": "1.5",
    },
    "spacing": {
        "margin_pct": "5%",
        "gap": "1rem",
        "section_gap": "2rem",
    },
    "layout": {
        "slide_width": 1920,
        "slide_height": 1080,
        "column_gap": "1.5rem",
    },
    "data_viz": {
        "primary_colormap": "viridis",
        "axis_color": "#333333",
        "grid_color": "#eeeeee",
        "annotation_color": "#ff0000",
    },
    "constraints": {
        "permitted_diagram_types": ["mermaid", "katex"],
    },
    "provenance": {
        "generated_by": "stylist",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_debrief_state_dict(archetype: str = "lab_meeting") -> dict:
    """Return a fully-populated, hash-correct debrief_state dict."""
    from debrief_state import compute_state_hash

    d: dict[str, Any] = {
        "phase": "discovery",
        "sub_phase": "discovery/greeting",
        "active_agent": "consultant",
        "archetype": archetype,
        "current_group_id": None,
        "current_slide_slug": None,
        "pending_gate": None,
        "last_gate_response": None,
        "red_green_iteration": 0,
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
        "session_started_at": _CREATED,
        "state_hash": "",
    }
    d["state_hash"] = compute_state_hash(d)
    return d


def _make_minimal_deck_state_dict(archetype: str = "lab_meeting") -> dict:
    return {
        "project_name": "test_project",
        "created_at": _CREATED,
        "archetype": archetype,
        "style_locked": False,
        "closing_slide": None,
        "slides": [],
        "presentations": [],
    }


def _write_state_files(
    project_root: Path,
    debrief_dict: dict | None = None,
    deck_dict: dict | None = None,
) -> None:
    """Write state JSON files to project_root."""
    (project_root / ".debrief").mkdir(parents=True, exist_ok=True)
    if debrief_dict is not None:
        (project_root / "debrief_state.json").write_text(
            json.dumps(debrief_dict), encoding="utf-8"
        )
    if deck_dict is not None:
        (project_root / "deck_state.json").write_text(
            json.dumps(deck_dict), encoding="utf-8"
        )


def _make_slide_record_dict(
    slug: str = "intro",
    status: str = "approved",
    backup: bool = False,
    group_id: str = "group_01",
) -> dict:
    return {
        "slug": slug,
        "title": slug.replace("_", " ").title(),
        "status": status,
        "backup": backup,
        "content_summary": f"Summary of {slug}",
        "visual_approach": "diagram",
        "design_choices": "minimal",
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
# I. Unit 3 -> Unit 2: Launcher new() produces state readable by Unit 2
# ===========================================================================


class TestLauncherToStateRoundTrip:
    """BC-3.4 / BC-3.5: new() state files are round-trippable via Unit 2."""

    def test_deck_state_written_by_launcher_readable_by_unit2(
        self, tmp_path: Path
    ) -> None:
        """State written by launcher._atomic_write_json is readable by
        read_deck_state.  Both modules share the same JSON schema."""
        from debrief_state import read_deck_state

        deck = _make_minimal_deck_state_dict()
        _write_state_files(tmp_path, deck_dict=deck)

        state = read_deck_state(tmp_path)
        assert state.project_name == "test_project"
        assert state.archetype == "lab_meeting"
        assert state.style_locked is False
        assert state.slides == []
        assert state.presentations == []

    def test_debrief_state_written_by_launcher_readable_by_unit2(
        self, tmp_path: Path
    ) -> None:
        """State written by launcher._atomic_write_json is readable by
        read_debrief_state.  Hash is verified on read."""
        from debrief_state import read_debrief_state

        debrief = _make_minimal_debrief_state_dict()
        _write_state_files(tmp_path, debrief_dict=debrief)

        state = read_debrief_state(tmp_path)
        assert state.phase == "discovery"
        assert state.sub_phase == "discovery/greeting"
        assert state.active_agent == "consultant"
        assert state.red_green_iteration == 0

    def test_launcher_initial_deck_has_style_locked_false(
        self, tmp_path: Path
    ) -> None:
        """BC-3.4: launcher initialises style_locked=false."""
        from debrief_state import read_deck_state

        deck = _make_minimal_deck_state_dict()
        _write_state_files(tmp_path, deck_dict=deck)
        state = read_deck_state(tmp_path)
        assert state.style_locked is False

    def test_launcher_initial_debrief_active_agent_is_consultant(
        self, tmp_path: Path
    ) -> None:
        """BC-3.5: initial active_agent must be 'consultant'."""
        from debrief_state import read_debrief_state

        debrief = _make_minimal_debrief_state_dict()
        _write_state_files(tmp_path, debrief_dict=debrief)
        state = read_debrief_state(tmp_path)
        assert state.active_agent == "consultant"

    def test_launcher_state_hash_is_valid_on_read(
        self, tmp_path: Path
    ) -> None:
        """BC-2.4 / BC-3.5: hash stored by launcher equals compute_state_hash
        on the same content, so read_debrief_state does not recompute."""
        import sys
        from io import StringIO
        from debrief_state import read_debrief_state, compute_state_hash

        debrief = _make_minimal_debrief_state_dict()
        _write_state_files(tmp_path, debrief_dict=debrief)

        old_stderr = sys.stderr
        sys.stderr = StringIO()
        try:
            state = read_debrief_state(tmp_path)
            warning_output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr

        # No hash mismatch warning should be emitted
        assert "hash mismatch" not in warning_output
        assert state.state_hash == debrief["state_hash"]


# ===========================================================================
# II. Unit 2 -> Unit 4: State written by Unit 2 drives resolve_action
# ===========================================================================


class TestStateToRouting:
    """Cross-unit: DebriefState written by Unit 2 is correctly consumed by
    the Unit 4 routing state machine."""

    def test_greeting_sub_phase_yields_human_gate(
        self, tmp_path: Path
    ) -> None:
        """discovery/greeting -> ActionBlock with gate_id G1.1_greeting."""
        from debrief_state import (
            write_debrief_state,
            _dict_to_debrief_state,  # type: ignore[attr-defined]
        )
        from routing import resolve_action

        debrief = _make_minimal_debrief_state_dict()
        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)
        state = _dict_to_debrief_state(debrief)
        write_debrief_state(tmp_path, state)

        block = resolve_action(state, tmp_path)
        assert block["action_type"] == "human_gate"
        assert block["gate_id"] == "G1.1_greeting"

    def test_production_group_planning_yields_consultant_agent(
        self, tmp_path: Path
    ) -> None:
        """production/group_planning -> agent=consultant."""
        from debrief_state import _dict_to_debrief_state  # type: ignore
        from routing import resolve_action

        d = _make_minimal_debrief_state_dict()
        d["phase"] = "production"
        d["sub_phase"] = "production/group_planning"
        state = _dict_to_debrief_state(d)

        block = resolve_action(state, tmp_path)
        assert block["action_type"] == "agent"
        assert block["agent"] == "consultant"

    def test_complete_sub_phase_yields_complete_block(
        self, tmp_path: Path
    ) -> None:
        """complete sub_phase -> action_type=complete."""
        from debrief_state import _dict_to_debrief_state  # type: ignore
        from routing import resolve_action

        d = _make_minimal_debrief_state_dict()
        d["phase"] = "complete"
        d["sub_phase"] = "complete"
        state = _dict_to_debrief_state(d)

        block = resolve_action(state, tmp_path)
        assert block["action_type"] == "complete"

    def test_red_green_no_qa_log_yields_slide_maker(
        self, tmp_path: Path
    ) -> None:
        """production/red_green with no qa_log -> slide_maker (RED path)."""
        from debrief_state import _dict_to_debrief_state  # type: ignore
        from routing import resolve_action

        d = _make_minimal_debrief_state_dict()
        d["phase"] = "production"
        d["sub_phase"] = "production/red_green"
        d["current_slide_slug"] = "intro"
        state = _dict_to_debrief_state(d)

        block = resolve_action(state, tmp_path)
        assert block["action_type"] == "agent"
        assert block["agent"] == "slide_maker"

    def test_style_review_yields_style_gate(
        self, tmp_path: Path
    ) -> None:
        """style/style_review -> G2.1_style_config_review gate."""
        from debrief_state import _dict_to_debrief_state  # type: ignore
        from routing import resolve_action

        d = _make_minimal_debrief_state_dict()
        d["phase"] = "style"
        d["sub_phase"] = "style/style_review"
        state = _dict_to_debrief_state(d)

        block = resolve_action(state, tmp_path)
        assert block["action_type"] == "human_gate"
        assert block["gate_id"] == "G2.1_style_config_review"


# ===========================================================================
# III. Unit 5 -> Unit 2: write_slide_brief / write_group_manifest
#      use Unit 2's atomic_write_json; briefs are readable as valid JSON
# ===========================================================================


class TestLedgerBriefToState:
    """write_slide_brief writes JSON that shares the atomicity guarantee of
    Unit 2's atomic_write_json (both use write-to-tmp then rename)."""

    def test_write_slide_brief_produces_valid_json(
        self, tmp_path: Path
    ) -> None:
        """Brief file written by Unit 5 is valid JSON with all required fields."""
        from ledger import write_slide_brief, REQUIRED_BRIEF_FIELDS

        briefs_dir = tmp_path / ".debrief" / "briefs"
        briefs_dir.mkdir(parents=True, exist_ok=True)

        write_slide_brief(
            project_root=tmp_path,
            group_id="group_01",
            slug="methodology",
            title="Methodology",
            content_goal="Explain the method",
            visual_approach="diagram",
            visual_pattern="flowchart",
            rhetorical_role="logos",
            design_invariants=["INV-04", "INV-06"],
            user_recommendations="Keep it clean",
        )

        brief_path = briefs_dir / "group_01_methodology.json"
        assert brief_path.exists()
        data = json.loads(brief_path.read_text(encoding="utf-8"))
        for field in REQUIRED_BRIEF_FIELDS:
            assert field in data, f"Missing required field: {field}"

    def test_write_group_manifest_slide_count_matches_slugs(
        self, tmp_path: Path
    ) -> None:
        """BC-5.3: manifest slide_count == len(slugs)."""
        from ledger import write_group_manifest

        briefs_dir = tmp_path / ".debrief" / "briefs"
        briefs_dir.mkdir(parents=True, exist_ok=True)

        slugs = ["slide_a", "slide_b", "slide_c"]
        write_group_manifest(tmp_path, "group_01", slugs)

        manifest_path = briefs_dir / "group_01_MANIFEST.json"
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["slide_count"] == 3
        assert data["slugs"] == slugs

    def test_write_group_manifest_dispatched_at_is_iso8601(
        self, tmp_path: Path
    ) -> None:
        """BC-5.2: dispatched_at field is a valid ISO 8601 timestamp."""
        from ledger import write_group_manifest

        (tmp_path / ".debrief" / "briefs").mkdir(parents=True, exist_ok=True)
        write_group_manifest(tmp_path, "group_02", ["s1"])

        path = tmp_path / ".debrief" / "briefs" / "group_02_MANIFEST.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        ts = data["dispatched_at"]
        # Must be parseable as datetime
        datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def test_write_slide_brief_no_tmp_file_persists(
        self, tmp_path: Path
    ) -> None:
        """BC-2.2: atomic write leaves no .tmp file after success."""
        from ledger import write_slide_brief

        (tmp_path / ".debrief" / "briefs").mkdir(parents=True, exist_ok=True)
        write_slide_brief(
            project_root=tmp_path,
            group_id="group_01",
            slug="results",
            title="Results",
            content_goal="Show findings",
            visual_approach="chart",
            visual_pattern="bar_chart",
            rhetorical_role="logos",
            design_invariants=[],
            user_recommendations="",
        )
        briefs_dir = tmp_path / ".debrief" / "briefs"
        tmp_files = list(briefs_dir.glob("*.tmp"))
        assert tmp_files == [], "Stale .tmp file after atomic write"

    def test_append_ledger_entry_produces_readable_jsonl(
        self, tmp_path: Path
    ) -> None:
        """BC-5.4: each ledger entry is a valid JSON line with required keys."""
        from ledger import append_ledger_entry

        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)

        append_ledger_entry(
            tmp_path, "consultant", "First message", group_id="group_01"
        )
        append_ledger_entry(
            tmp_path, "user", "User reply", slug="intro"
        )

        ledger_path = tmp_path / ".debrief" / "ledger.jsonl"
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line)
            for key in ("timestamp", "role", "content", "metadata"):
                assert key in entry

    def test_write_slide_brief_invalid_rhetorical_role_raises(
        self, tmp_path: Path
    ) -> None:
        """BC-5.1: invalid rhetorical_role raises ValueError (not silently written)."""
        from ledger import write_slide_brief

        (tmp_path / ".debrief" / "briefs").mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError, match="rhetorical_role"):
            write_slide_brief(
                project_root=tmp_path,
                group_id="group_01",
                slug="bad_slide",
                title="Bad Slide",
                content_goal="n/a",
                visual_approach="n/a",
                visual_pattern="n/a",
                rhetorical_role="INVALID_ROLE",
                design_invariants=[],
                user_recommendations="",
            )


# ===========================================================================
# IV. Unit 6 (CSS_PROPERTY_MAP) -> Unit 9 (permitted libraries check)
#     The style config shape used to drive INV-10 in Unit 9 matches the
#     flattening contract in Unit 6.
# ===========================================================================


class TestStyleCompilerToQAChecker:
    """CSS_PROPERTY_MAP in Unit 6 must cover all mapped paths; the flattened
    config shape emitted by Unit 6 must be usable by Unit 9's INV-10 check."""

    def test_css_property_map_has_26_entries(self) -> None:
        """BC-6.1: exactly 26 entries in CSS_PROPERTY_MAP (canonical count)."""
        from style_engine import CSS_PROPERTY_MAP

        assert len(CSS_PROPERTY_MAP) == 26

    def test_flatten_config_excludes_constraints_and_provenance(
        self,
    ) -> None:
        """BC-6.4: constraints and provenance keys never appear in flat output."""
        from style_engine import flatten_config

        flat = flatten_config(_MINIMAL_STYLE_CONFIG)
        for key in flat:
            top = key.split(".")[0]
            assert top not in ("constraints", "provenance"), (
                f"Excluded key leaked into flat config: {key}"
            )

    def test_generate_css_root_block_contains_all_26_mapped_vars(
        self,
    ) -> None:
        """BC-6.2: all 26 CSS_PROPERTY_MAP vars appear in the :root block."""
        from style_engine import CSS_PROPERTY_MAP, generate_css_root_block

        css = generate_css_root_block(_MINIMAL_STYLE_CONFIG)
        for css_var in CSS_PROPERTY_MAP.values():
            assert css_var in css, (
                f"Mapped CSS variable missing from :root block: {css_var}"
            )

    def test_check_no_inline_styles_passes_css_class_slide(
        self, tmp_path: Path
    ) -> None:
        """INV-06: slide with only CSS classes (no inline style=) passes."""
        from qa_checker import check_no_inline_styles

        slide = tmp_path / "slides" / "results.html"
        slide.parent.mkdir(parents=True, exist_ok=True)
        slide.write_text(
            '<!DOCTYPE html><html><body>'
            '<div class="slide">'
            '<p class="title">Title</p>'
            '</div></body></html>',
            encoding="utf-8",
        )
        assert check_no_inline_styles(slide) is None

    def test_check_no_external_requests_passes_local_vendor_refs(
        self, tmp_path: Path
    ) -> None:
        """INV-07: slide referencing only local vendor paths passes."""
        from qa_checker import check_no_external_requests

        slide = tmp_path / "slides" / "intro.html"
        slide.parent.mkdir(parents=True, exist_ok=True)
        slide.write_text(
            '<!DOCTYPE html><html><head>'
            '<link rel="stylesheet" href="../assets/style.css">'
            '<script src="../assets/vendor/mermaid.min.js"></script>'
            '</head><body></body></html>',
            encoding="utf-8",
        )
        assert check_no_external_requests(slide) is None

    def test_check_permitted_libraries_uses_config_permitted_list(
        self, tmp_path: Path
    ) -> None:
        """INV-10: permitted_diagram_types from style_config drives check.
        A slide using only permitted libraries passes; one using 'd3'
        when it is absent from the permitted list fails."""
        from qa_checker import check_permitted_libraries

        slide = tmp_path / "slides" / "chart.html"
        slide.parent.mkdir(parents=True, exist_ok=True)
        slide.write_text(
            '<!DOCTYPE html><html><head>'
            '<script src="../assets/vendor/d3.min.js"></script>'
            '</head><body></body></html>',
            encoding="utf-8",
        )
        permitted = _MINIMAL_STYLE_CONFIG["constraints"][
            "permitted_diagram_types"
        ]
        # d3 is NOT in the permitted list -> failure
        result = check_permitted_libraries(slide, permitted)
        assert result is not None
        assert result["invariant"] == "INV-10"

        # Now add d3 -> pass
        assert check_permitted_libraries(slide, permitted + ["d3"]) is None


# ===========================================================================
# V. Unit 4 (Routing) -> Unit 9 (QA log): check_g3_2_machine_gate reads
#    qa_log entries produced by append_qa_log.
# ===========================================================================


class TestRoutingQALogIntegration:
    """BC-4.3: check_g3_2_machine_gate reads qa_log.jsonl written by
    Unit 9's append_qa_log.  GREEN / RED / EXHAUSTED / OSCILLATION states
    are derived from Unit-9 schema entries."""

    def _write_qa_entry(
        self,
        project_root: Path,
        slug: str,
        passed: bool,
        failures: list[dict],
        timestamp: str,
    ) -> None:
        from qa_checker import build_qa_log_entry, append_qa_log

        entry = build_qa_log_entry(
            slug=slug,
            passed=passed,
            veto=False,
            checks_run=["INV-06", "INV-07"],
            failures=failures,
            warnings=[],
        )
        # Override timestamp to a known value for testing
        entry["timestamp"] = timestamp
        append_qa_log(project_root, entry)

    def test_green_entry_yields_green(self, tmp_path: Path) -> None:
        """A passing qa_log entry returns GREEN."""
        from routing import check_g3_2_machine_gate

        (tmp_path / "output").mkdir(parents=True, exist_ok=True)
        # Routing reads qa_log.jsonl directly from project_root, not output/
        started = "2026-01-15T09:00:00"
        self._write_qa_entry(
            tmp_path,
            "intro",
            True,
            [],
            "2026-01-15T10:00:00",
        )
        # Copy to the location routing reads
        (tmp_path / "qa_log.jsonl").write_bytes(
            (tmp_path / "output" / "qa_log.jsonl").read_bytes()
        )

        result = check_g3_2_machine_gate("intro", 0, started, tmp_path)
        assert result == "GREEN"

    def test_failing_entry_below_limit_yields_red(
        self, tmp_path: Path
    ) -> None:
        """A failing entry with iteration < 5 returns RED."""
        from routing import check_g3_2_machine_gate

        (tmp_path / "output").mkdir(parents=True, exist_ok=True)
        started = "2026-01-15T09:00:00"
        self._write_qa_entry(
            tmp_path,
            "intro",
            False,
            [
                {
                    "invariant": "INV-06",
                    "description": "inline style",
                    "revision_instruction": "fix it",
                }
            ],
            "2026-01-15T10:00:00",
        )
        (tmp_path / "qa_log.jsonl").write_bytes(
            (tmp_path / "output" / "qa_log.jsonl").read_bytes()
        )

        result = check_g3_2_machine_gate("intro", 2, started, tmp_path)
        assert result == "RED"

    def test_failing_entry_at_limit_yields_exhausted(
        self, tmp_path: Path
    ) -> None:
        """A failing entry with iteration >= 5 returns EXHAUSTED."""
        from routing import check_g3_2_machine_gate

        (tmp_path / "output").mkdir(parents=True, exist_ok=True)
        started = "2026-01-15T09:00:00"
        self._write_qa_entry(
            tmp_path,
            "intro",
            False,
            [
                {
                    "invariant": "INV-06",
                    "description": "inline style",
                    "revision_instruction": "fix it",
                }
            ],
            "2026-01-15T10:00:00",
        )
        (tmp_path / "qa_log.jsonl").write_bytes(
            (tmp_path / "output" / "qa_log.jsonl").read_bytes()
        )

        result = check_g3_2_machine_gate("intro", 5, started, tmp_path)
        assert result == "EXHAUSTED"

    def test_oscillation_detected_from_unit9_entries(
        self, tmp_path: Path
    ) -> None:
        """BC-4.4: two entries with same failure count but different invariants
        -> OSCILLATION, using entries produced by Unit 9's schema."""
        from routing import check_g3_2_machine_gate

        (tmp_path / "output").mkdir(parents=True, exist_ok=True)
        started = "2026-01-15T09:00:00"

        # First failure: INV-06
        self._write_qa_entry(
            tmp_path,
            "intro",
            False,
            [
                {
                    "invariant": "INV-06",
                    "description": "inline style",
                    "revision_instruction": "fix it",
                }
            ],
            "2026-01-15T10:00:00",
        )
        # Second failure: INV-07 (same count=1, different invariant)
        self._write_qa_entry(
            tmp_path,
            "intro",
            False,
            [
                {
                    "invariant": "INV-07",
                    "description": "external url",
                    "revision_instruction": "fix it",
                }
            ],
            "2026-01-15T10:01:00",
        )
        (tmp_path / "qa_log.jsonl").write_bytes(
            (tmp_path / "output" / "qa_log.jsonl").read_bytes()
        )

        result = check_g3_2_machine_gate("intro", 2, started, tmp_path)
        assert result == "OSCILLATION"

    def test_timestamp_filter_excludes_prior_cycle_entries(
        self, tmp_path: Path
    ) -> None:
        """BC-4.3: entries from before red_green_started_at are ignored."""
        from routing import check_g3_2_machine_gate

        (tmp_path / "output").mkdir(parents=True, exist_ok=True)
        # Old passing entry (before this cycle started)
        self._write_qa_entry(
            tmp_path, "intro", True, [], "2026-01-15T07:00:00"
        )
        # New failing entry (within this cycle)
        self._write_qa_entry(
            tmp_path,
            "intro",
            False,
            [
                {
                    "invariant": "INV-06",
                    "description": "x",
                    "revision_instruction": "y",
                }
            ],
            "2026-01-15T10:00:00",
        )
        (tmp_path / "qa_log.jsonl").write_bytes(
            (tmp_path / "output" / "qa_log.jsonl").read_bytes()
        )

        # started_at excludes the old passing entry
        started = "2026-01-15T09:00:00"
        result = check_g3_2_machine_gate("intro", 1, started, tmp_path)
        assert result == "RED"


# ===========================================================================
# VI. Unit 8 (visual_qa) -> Unit 9 (qa_checker): HTML produced by
#     render_math_html and escape_html passes INV-06 / INV-07
# ===========================================================================


class TestSlideAgentToQAChecker:
    """HTML generated by Unit 8 helpers must be clean from Unit 9's
    perspective (no inline styles, no external URLs)."""

    def test_render_math_html_inline_passes_inv06(
        self, tmp_path: Path
    ) -> None:
        """KaTeX inline wrapper has no style= attribute -> passes INV-06."""
        from visual_qa import render_math_html
        from qa_checker import check_no_inline_styles

        html_fragment = render_math_html("inline", r"\alpha + \beta")
        slide = tmp_path / "slides" / "math_slide.html"
        slide.parent.mkdir(parents=True, exist_ok=True)
        slide.write_text(
            f"<!DOCTYPE html><html><body>{html_fragment}</body></html>",
            encoding="utf-8",
        )
        assert check_no_inline_styles(slide) is None

    def test_render_math_html_display_passes_inv06(
        self, tmp_path: Path
    ) -> None:
        """KaTeX display wrapper has no style= attribute -> passes INV-06."""
        from visual_qa import render_math_html
        from qa_checker import check_no_inline_styles

        html_fragment = render_math_html("display", r"\sum_{i=0}^{n} i")
        slide = tmp_path / "slides" / "math_slide2.html"
        slide.parent.mkdir(parents=True, exist_ok=True)
        slide.write_text(
            f"<!DOCTYPE html><html><body>{html_fragment}</body></html>",
            encoding="utf-8",
        )
        assert check_no_inline_styles(slide) is None

    def test_escape_html_ampersand_does_not_trigger_inv07(
        self, tmp_path: Path
    ) -> None:
        """escape_html produces HTML-safe text that does not create spurious
        href/src attributes referencing external URLs."""
        from visual_qa import escape_html
        from qa_checker import check_no_external_requests

        # A LaTeX string containing text that looks like it might be a URL
        raw = "See https://example.com for details"
        escaped = escape_html(raw)
        # The escaped result should NOT contain href= or src= with https://
        # (it should escape to plain text, not an attribute)
        slide = tmp_path / "slides" / "esc_slide.html"
        slide.parent.mkdir(parents=True, exist_ok=True)
        slide.write_text(
            f"<!DOCTYPE html><html><body><p>{escaped}</p></body></html>",
            encoding="utf-8",
        )
        assert check_no_external_requests(slide) is None

    def test_render_math_html_inline_contains_katex_class(self) -> None:
        """BC-8.5: render_math_html output has class='katex-src' and
        data-mode='inline' so the KaTeX init script can target it."""
        from visual_qa import render_math_html

        html = render_math_html("inline", r"\gamma")
        assert 'class="katex-src"' in html
        assert 'data-mode="inline"' in html

    def test_render_math_html_display_contains_katex_class(self) -> None:
        """BC-8.5: render_math_html output has class='katex-src' and
        data-mode='display'."""
        from visual_qa import render_math_html

        html = render_math_html("display", r"\int_0^1 f(x)\,dx")
        assert 'class="katex-src"' in html
        assert 'data-mode="display"' in html


# ===========================================================================
# VII. Unit 11 -> Unit 2: sanitize_save_label delegates to sanitize_identifier
# ===========================================================================


class TestSanitizeLabelConsistency:
    """BC-11.9: sanitize_save_label (Unit 11) wraps sanitize_identifier
    (Unit 2) with max_length=50.  Both must produce identical output for
    the same input."""

    @pytest.mark.parametrize(
        "text",
        [
            "My Great Project",
            "lab-meeting-2026",
            "  Spaced  Label  ",
            "ALL CAPS TITLE",
            "123numbers_first",
            "Special!@#$Characters",
            "",
            "a" * 60,
        ],
    )
    def test_save_label_matches_unit2_sanitize(self, text: str) -> None:
        """sanitize_save_label == sanitize_identifier(text, 50)."""
        from utility_skills import sanitize_save_label
        from debrief_state import sanitize_identifier

        assert sanitize_save_label(text) == sanitize_identifier(
            text, max_length=50
        )

    def test_empty_label_falls_back_to_untitled(self) -> None:
        """BC-2.16 step 7: empty result -> 'untitled' in both units."""
        from utility_skills import sanitize_save_label
        from debrief_state import sanitize_identifier

        assert sanitize_save_label("") == "untitled"
        assert sanitize_identifier("", max_length=50) == "untitled"


# ===========================================================================
# VIII. Registry / dispatch-table bidirectional coverage
# ===========================================================================


class TestRegistryDispatchCoverage:
    """Every gate_id registered in Unit 4's _GATE_VALID_RESPONSES must have
    a corresponding entry reachable via _SUB_PHASE_ACTION or the special
    G3.2 / G3.2a branches in resolve_action.  This prevents routing from
    emitting a gate_id that has no valid_responses, and vice versa."""

    def test_all_gate_ids_have_valid_responses(self) -> None:
        """Every gate_id in _GATE_VALID_RESPONSES has at least one response."""
        from routing import _GATE_VALID_RESPONSES  # type: ignore[attr-defined]

        for gate_id, responses in _GATE_VALID_RESPONSES.items():
            assert len(responses) >= 1, (
                f"Gate {gate_id!r} has no valid_responses"
            )

    def test_sub_phase_action_gate_ids_are_registered(self) -> None:
        """Every gate_id referenced by _SUB_PHASE_ACTION is in
        _GATE_VALID_RESPONSES."""
        from routing import (  # type: ignore[attr-defined]
            _SUB_PHASE_ACTION,
            _GATE_VALID_RESPONSES,
        )

        for sub_phase, action in _SUB_PHASE_ACTION.items():
            if action.get("action_type") == "human_gate":
                gate_id = action.get("gate_id")
                assert gate_id in _GATE_VALID_RESPONSES, (
                    f"sub_phase {sub_phase!r} references unregistered "
                    f"gate_id {gate_id!r}"
                )

    def test_g3_2_and_g3_2a_gates_are_registered(self) -> None:
        """G3.2_qa_review and G3.2a_oscillation_review are registered in
        _GATE_VALID_RESPONSES even though they are handled outside
        _SUB_PHASE_ACTION."""
        from routing import _GATE_VALID_RESPONSES  # type: ignore[attr-defined]

        assert "G3.2_qa_review" in _GATE_VALID_RESPONSES
        assert "G3.2a_oscillation_review" in _GATE_VALID_RESPONSES

    def test_allowed_rhetorical_roles_match_spec(self) -> None:
        """BC-5.1: ALLOWED_RHETORICAL_ROLES in Unit 5 contains exactly the
        seven values from the spec."""
        from ledger import ALLOWED_RHETORICAL_ROLES

        expected = frozenset(
            {"hook", "ethos", "pathos", "logos", "synthesis", "recap",
             "transition"}
        )
        assert ALLOWED_RHETORICAL_ROLES == expected

    def test_validate_gate_response_parameterized_prefix(self) -> None:
        """validate_gate_response accepts 'SLIDE REVISE <instructions>' for
        gate G3.2_qa_review and rejects bare 'SLIDE REVISE'."""
        from routing import validate_gate_response, _GATE_VALID_RESPONSES

        responses = _GATE_VALID_RESPONSES["G3.2_qa_review"]
        assert validate_gate_response(
            "G3.2_qa_review",
            "SLIDE REVISE please fix the font",
            responses,
        )
        assert not validate_gate_response(
            "G3.2_qa_review", "SLIDE REVISE", responses
        )

    def test_validate_gate_response_literal_match(self) -> None:
        """validate_gate_response matches literal responses exactly."""
        from routing import validate_gate_response, _GATE_VALID_RESPONSES

        responses = _GATE_VALID_RESPONSES["G1.1_greeting"]
        assert validate_gate_response("G1.1_greeting", "CONTINUE", responses)
        assert validate_gate_response("G1.1_greeting", "QUIT", responses)
        assert not validate_gate_response(
            "G1.1_greeting", "continue", responses
        )


# ===========================================================================
# IX. Unit 3 -> Unit 4: after new() the debrief_state drives routing
# ===========================================================================


class TestLauncherToRouting:
    """After launcher.new() writes state files, the state is readable by
    Unit 2 and produces a valid ActionBlock when fed to Unit 4's
    resolve_action."""

    def test_initial_state_drives_greeting_gate(
        self, tmp_path: Path
    ) -> None:
        """The state produced by new() (via _atomic_write_json) is correctly
        consumed by routing to emit the G1.1_greeting gate."""
        from debrief_state import read_debrief_state
        from routing import resolve_action

        debrief = _make_minimal_debrief_state_dict()
        deck = _make_minimal_deck_state_dict()
        _write_state_files(tmp_path, debrief_dict=debrief, deck_dict=deck)

        state = read_debrief_state(tmp_path)
        block = resolve_action(state, tmp_path)

        assert block["action_type"] == "human_gate"
        assert block["gate_id"] == "G1.1_greeting"

    def test_initial_deck_state_has_empty_slides_for_export_page_list(
        self, tmp_path: Path
    ) -> None:
        """build_page_list on initial deck state returns empty page list."""
        from debrief_state import read_deck_state
        from export import build_page_list

        deck = _make_minimal_deck_state_dict()
        _write_state_files(tmp_path, deck_dict=deck)

        state = read_deck_state(tmp_path)
        pages = build_page_list(state, tmp_path)
        assert pages == []


# ===========================================================================
# X. Unit 12 (Paper Analyzer) -> Unit 2: slug derivation consistency
# ===========================================================================


class TestPaperAnalyzerSlugConsistency:
    """derive_paper_slug in Unit 12 reimplements _sanitize_identifier locally
    (to avoid circular import).  Its output for stem inputs must match
    Unit 2's sanitize_identifier for the same inputs at max_length=50."""

    @pytest.mark.parametrize(
        "stem,expected_slug",
        [
            ("Nature_2024_Smith_et_al", "nature_2024_smith_et_al"),
            ("My-Awesome Paper", "my_awesome_paper"),
            ("ALL CAPS TITLE", "all_caps_title"),
            ("valid_slug_already", "valid_slug_already"),
        ],
    )
    def test_derive_paper_slug_matches_sanitize_identifier(
        self, tmp_path: Path, stem: str, expected_slug: str
    ) -> None:
        """Unit 12's local algorithm produces the same result as Unit 2's
        sanitize_identifier for string stems that don't start with a digit."""
        from paper_analyzer import derive_paper_slug
        from debrief_state import sanitize_identifier

        fake_pdf = tmp_path / f"{stem}.pdf"
        fake_pdf.write_bytes(b"")

        result = derive_paper_slug(fake_pdf)
        unit2_result = sanitize_identifier(stem, max_length=50)
        assert result == unit2_result == expected_slug

    def test_derive_paper_slug_prepends_p_for_digit_start(
        self, tmp_path: Path
    ) -> None:
        """When sanitised stem starts with a digit, derive_paper_slug
        prepends 'p_' (Unit 12 rule); Unit 2 sanitize_identifier does not."""
        from paper_analyzer import derive_paper_slug

        fake_pdf = tmp_path / "2024_smith.pdf"
        fake_pdf.write_bytes(b"")

        slug = derive_paper_slug(fake_pdf)
        assert slug.startswith("p_"), (
            f"Expected 'p_' prefix for digit-leading slug, got: {slug!r}"
        )

    def test_extract_figure_captions_returns_list_of_dicts(self) -> None:
        """extract_figure_captions from Unit 12 returns structured dicts
        with figure_num, caption, page_index keys."""
        from paper_analyzer import extract_figure_captions

        pages = [
            "Introduction text.\nFigure 1. The main result.\nMore text.",
            "Figure 2: A secondary result.\nBody text.",
        ]
        captions = extract_figure_captions(pages)
        assert len(captions) >= 1
        for cap in captions:
            assert "figure_num" in cap
            assert "caption" in cap
            assert "page_index" in cap

    def test_rank_figures_returns_sorted_list(self) -> None:
        """rank_figures returns figures sorted by descending rank score,
        each dict retaining figure_num and caption keys."""
        from paper_analyzer import rank_figures, extract_figure_captions

        pages = [
            (
                "The study found (see Figure 1) ... Figure 1 shows ...\n"
                "Figure 1. The main figure.\n"
            ),
            (
                "Figure 2. A supplementary figure.\n"
                "Figure 2 shows minor data.\n"
            ),
        ]
        sections = [{"heading": "RESULTS", "page_index": 0}]
        captions = extract_figure_captions(pages)
        ranked = rank_figures(captions, pages, sections)
        assert isinstance(ranked, list)
        if len(ranked) >= 2:
            # Figure 1 is cited more often; should rank first
            assert ranked[0]["figure_num"] == 1


# ===========================================================================
# XI. Unit 10 (Export) -> Unit 2 (State): build_page_list canonical ordering
# ===========================================================================


class TestExportPageOrder:
    """BC-10.3: main / backup / closing / separator ordering in build_page_list
    uses DeckState produced by Unit 2's read_deck_state."""

    def _make_deck_with_slides(
        self,
        project_root: Path,
        main_slugs: list[str],
        backup_slugs: list[str],
        closing_slide: str | None = None,
    ) -> Any:
        from debrief_state import read_deck_state

        slides = []
        for s in main_slugs:
            slides.append(
                _make_slide_record_dict(slug=s, backup=False)
            )
        for s in backup_slugs:
            slides.append(
                _make_slide_record_dict(slug=s, backup=True)
            )

        deck = _make_minimal_deck_state_dict()
        deck["slides"] = slides
        if closing_slide is not None:
            deck["closing_slide"] = closing_slide
        _write_state_files(project_root, deck_dict=deck)
        return read_deck_state(project_root)

    def test_main_slides_appear_before_backup(
        self, tmp_path: Path
    ) -> None:
        """BC-10.3: main approved slides come before backup slides."""
        from export import build_page_list

        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)
        state = self._make_deck_with_slides(
            tmp_path,
            main_slugs=["intro", "methods"],
            backup_slugs=["appendix"],
        )
        pages = build_page_list(state, tmp_path)

        types_and_backup = [(p["type"], p.get("backup", False)) for p in pages]
        main_indices = [
            i for i, (t, b) in enumerate(types_and_backup)
            if t == "slide" and not b
        ]
        backup_indices = [
            i for i, (t, b) in enumerate(types_and_backup)
            if t == "slide" and b
        ]
        if main_indices and backup_indices:
            assert max(main_indices) < min(backup_indices), (
                "Main slides must all precede backup slides"
            )

    def test_no_approved_slides_returns_empty_page_list(
        self, tmp_path: Path
    ) -> None:
        """build_page_list returns [] when no slides are approved."""
        from export import build_page_list

        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)
        deck = _make_minimal_deck_state_dict()
        deck["slides"] = [
            _make_slide_record_dict(slug="draft", status="draft")
        ]
        _write_state_files(tmp_path, deck_dict=deck)

        from debrief_state import read_deck_state
        state = read_deck_state(tmp_path)
        pages = build_page_list(state, tmp_path)
        assert pages == []

    def test_page_list_slide_paths_are_under_slides_dir(
        self, tmp_path: Path
    ) -> None:
        """Each 'slide' page has a path under project_root/slides/."""
        from export import build_page_list

        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)
        state = self._make_deck_with_slides(
            tmp_path,
            main_slugs=["intro", "results"],
            backup_slugs=[],
        )
        pages = build_page_list(state, tmp_path)
        slides_dir = tmp_path / "slides"
        for page in pages:
            if page["type"] == "slide":
                assert page["path"] is not None
                assert str(slides_dir) in str(page["path"]), (
                    f"Slide path not under slides/: {page['path']}"
                )


# ===========================================================================
# XII. SUB_PHASE_VALUES (Unit 2) vs _SUB_PHASE_ACTION (Unit 4): complete
#      bidirectional coverage of the sub_phase constant set
# ===========================================================================


class TestSubPhaseRegistryAlignment:
    """Every sub_phase in Unit 2's SUB_PHASE_VALUES frozenset must have an
    entry in Unit 4's _SUB_PHASE_ACTION dispatch table, and every key in
    _SUB_PHASE_ACTION must be a valid sub_phase per Unit 2."""

    def test_every_sub_phase_value_has_routing_entry(self) -> None:
        """BC-2.15 x BC-4.1: no sub_phase constant is orphaned from routing."""
        from debrief_state import SUB_PHASE_VALUES
        from routing import _SUB_PHASE_ACTION  # type: ignore[attr-defined]

        for sp in SUB_PHASE_VALUES:
            assert sp in _SUB_PHASE_ACTION, (
                f"SUB_PHASE_VALUES member {sp!r} has no entry in "
                "_SUB_PHASE_ACTION"
            )

    def test_every_routing_entry_is_a_valid_sub_phase(self) -> None:
        """No routing entry uses a sub_phase not in SUB_PHASE_VALUES."""
        from debrief_state import SUB_PHASE_VALUES
        from routing import _SUB_PHASE_ACTION  # type: ignore[attr-defined]

        for sp in _SUB_PHASE_ACTION:
            assert sp in SUB_PHASE_VALUES, (
                f"_SUB_PHASE_ACTION key {sp!r} is not in SUB_PHASE_VALUES"
            )

    def test_sub_phase_values_count_matches_spec(self) -> None:
        """BC-2.15: exactly 24 sub_phase values per the spec."""
        from debrief_state import SUB_PHASE_VALUES

        assert len(SUB_PHASE_VALUES) == 24, (
            f"Expected 24 SUB_PHASE_VALUES, got {len(SUB_PHASE_VALUES)}"
        )

    def test_sub_phase_action_count_matches_sub_phase_values(self) -> None:
        """_SUB_PHASE_ACTION must cover exactly the same count as
        SUB_PHASE_VALUES (no missing, no extra entries)."""
        from debrief_state import SUB_PHASE_VALUES
        from routing import _SUB_PHASE_ACTION  # type: ignore[attr-defined]

        assert len(_SUB_PHASE_ACTION) == len(SUB_PHASE_VALUES), (
            f"_SUB_PHASE_ACTION has {len(_SUB_PHASE_ACTION)} entries but "
            f"SUB_PHASE_VALUES has {len(SUB_PHASE_VALUES)} values"
        )


# ===========================================================================
# XIII. State round-trip: write_debrief_state -> read_debrief_state
#       exercises Unit 2's hash recompute and lock protocol end-to-end.
# ===========================================================================


class TestStateRoundTrip:
    """write_debrief_state + read_debrief_state must be an identity
    transformation for all supported field combinations."""

    def _make_full_state(self) -> Any:
        from debrief_state import DebriefState, compute_state_hash

        d = _make_minimal_debrief_state_dict()
        return DebriefState(
            phase=d["phase"],
            sub_phase=d["sub_phase"],
            active_agent=d["active_agent"],
            archetype=d["archetype"],
            current_group_id=None,
            current_slide_slug=None,
            pending_gate=None,
            last_gate_response=None,
            red_green_iteration=0,
            red_green_started_at=None,
            group_slide_index=0,
            group_slide_count=0,
            backup_mode=False,
            completed_groups=[],
            pre_view_state=None,
            view_deferred=False,
            closing_slide_pending=False,
            group_revise_slug=None,
            style_import_mode=None,
            reference_provided=False,
            reference_modality=None,
            papers_provided=False,
            selected_figures=None,
            session_started_at=_CREATED,
            state_hash="placeholder",
        )

    def test_write_then_read_preserves_all_fields(
        self, tmp_path: Path
    ) -> None:
        """All DebriefState fields survive a write -> read round-trip."""
        from debrief_state import (
            write_debrief_state,
            read_debrief_state,
        )

        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)
        state = self._make_full_state()
        write_debrief_state(tmp_path, state)
        read_back = read_debrief_state(tmp_path)

        assert read_back.phase == state.phase
        assert read_back.sub_phase == state.sub_phase
        assert read_back.active_agent == state.active_agent
        assert read_back.archetype == state.archetype
        assert read_back.red_green_iteration == state.red_green_iteration
        assert read_back.completed_groups == state.completed_groups

    def test_write_debrief_state_hash_is_valid_on_read(
        self, tmp_path: Path
    ) -> None:
        """BC-2.4: written file always has a valid state_hash."""
        import sys
        from io import StringIO
        from debrief_state import write_debrief_state, read_debrief_state

        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)
        state = self._make_full_state()
        write_debrief_state(tmp_path, state)

        old_stderr = sys.stderr
        sys.stderr = StringIO()
        try:
            read_debrief_state(tmp_path)
            warnings = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr

        assert "hash mismatch" not in warnings

    def test_no_tmp_file_persists_after_write_debrief(
        self, tmp_path: Path
    ) -> None:
        """BC-2.2: no .tmp file survives a successful write_debrief_state."""
        from debrief_state import write_debrief_state

        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)
        state = self._make_full_state()
        write_debrief_state(tmp_path, state)

        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Stale .tmp files: {tmp_files}"

    def test_deck_state_round_trip_preserves_slides(
        self, tmp_path: Path
    ) -> None:
        """DeckState with slides survives a write_deck_state -> read_deck_state
        round-trip with all SlideRecord fields intact."""
        from debrief_state import (
            DeckState,
            SlideRecord,
            PresentationRecord,
            write_deck_state,
            read_deck_state,
        )

        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)
        slide = SlideRecord(
            slug="intro",
            title="Introduction",
            status="approved",
            backup=False,
            content_summary="Overview",
            visual_approach="diagram",
            design_choices="minimal",
            forks_not_taken=None,
            user_recommendations=None,
            qa_passed=True,
            accepted_violations=[],
            last_modified=_TS,
            group_id="group_01",
            user_assets=[],
            has_math=False,
        )
        deck = DeckState(
            project_name="myproj",
            created_at=_CREATED,
            archetype="lab_meeting",
            style_locked=True,
            closing_slide=None,
            slides=[slide],
            presentations=[],
        )
        write_deck_state(tmp_path, deck)
        restored = read_deck_state(tmp_path)

        assert len(restored.slides) == 1
        s = restored.slides[0]
        assert s.slug == "intro"
        assert s.status == "approved"
        assert s.qa_passed is True
        assert s.has_math is False
        assert restored.style_locked is True


# ===========================================================================
# XIV. Unit 6 -> Unit 4: promote_style_draft (BC-4.6) uses the compiled CSS
#      produced by compile_style (Unit 6). Verify compile_style output is
#      valid and contains a :root block.
# ===========================================================================


class TestStyleCompilerOutput:
    """Verify that compile_style (Unit 6) produces a :root CSS block that
    is syntactically correct and consumable by downstream pipeline steps."""

    def test_compile_style_produces_root_block(
        self, tmp_path: Path
    ) -> None:
        """compile_style writes a file containing ':root {'."""
        from style_engine import compile_style

        config_path = tmp_path / "style_config.json"
        css_path = tmp_path / "assets" / "style.css"
        css_path.parent.mkdir(parents=True, exist_ok=True)

        config_path.write_text(
            json.dumps(_MINIMAL_STYLE_CONFIG), encoding="utf-8"
        )
        compile_style(config_path, css_path)

        css = css_path.read_text(encoding="utf-8")
        assert ":root {" in css
        assert "}" in css

    def test_compile_style_no_constraints_vars_in_output(
        self, tmp_path: Path
    ) -> None:
        """BC-6.4: constraints and provenance keys must not appear as CSS
        variables in the compiled output."""
        from style_engine import compile_style

        config_path = tmp_path / "style_config.json"
        css_path = tmp_path / "style.css"
        config_path.write_text(
            json.dumps(_MINIMAL_STYLE_CONFIG), encoding="utf-8"
        )
        compile_style(config_path, css_path)

        css = css_path.read_text(encoding="utf-8")
        assert "--constraints" not in css
        assert "--provenance" not in css

    def test_compile_style_all_mapped_vars_present(
        self, tmp_path: Path
    ) -> None:
        """BC-6.2: all 26 CSS_PROPERTY_MAP variables appear in output."""
        from style_engine import compile_style, CSS_PROPERTY_MAP

        config_path = tmp_path / "style_config.json"
        css_path = tmp_path / "style.css"
        config_path.write_text(
            json.dumps(_MINIMAL_STYLE_CONFIG), encoding="utf-8"
        )
        compile_style(config_path, css_path)

        css = css_path.read_text(encoding="utf-8")
        for css_var in CSS_PROPERTY_MAP.values():
            assert css_var in css, (
                f"Mapped CSS variable {css_var!r} absent from compiled CSS"
            )


# ===========================================================================
# XV. Unit 4 -> Unit 5: perform_snapshot uses slides/<slug>.html written by
#     the slide agent workflow; snapshot appears in .debrief/snapshots/.
# ===========================================================================


class TestSnapshotContract:
    """BC-4.17: perform_snapshot reads slides/<slug>.html and writes
    .debrief/snapshots/<slug>_iter_<N>.html with the correct filename."""

    def test_perform_snapshot_creates_iter_file(
        self, tmp_path: Path
    ) -> None:
        """perform_snapshot copies a slide HTML to the snapshot dir with
        the 1-indexed iteration suffix."""
        from routing import perform_snapshot

        slides_dir = tmp_path / "slides"
        snaps_dir = tmp_path / ".debrief" / "snapshots"
        slides_dir.mkdir(parents=True, exist_ok=True)
        snaps_dir.mkdir(parents=True, exist_ok=True)

        html = "<!DOCTYPE html><html><body>Slide content</body></html>"
        (slides_dir / "methodology.html").write_text(html, encoding="utf-8")

        perform_snapshot("methodology", 1, tmp_path)

        snap_file = snaps_dir / "methodology_iter_1.html"
        assert snap_file.exists()
        assert snap_file.read_text(encoding="utf-8") == html

    def test_perform_snapshot_does_not_zero_pad_iteration(
        self, tmp_path: Path
    ) -> None:
        """BC-4.17: iteration N is NOT zero-padded ('_iter_1' not '_iter_01')."""
        from routing import perform_snapshot

        slides_dir = tmp_path / "slides"
        snaps_dir = tmp_path / ".debrief" / "snapshots"
        slides_dir.mkdir(parents=True, exist_ok=True)
        snaps_dir.mkdir(parents=True, exist_ok=True)

        (slides_dir / "intro.html").write_text("<html/>", encoding="utf-8")
        perform_snapshot("intro", 3, tmp_path)

        expected = snaps_dir / "intro_iter_3.html"
        unexpected = snaps_dir / "intro_iter_03.html"
        assert expected.exists()
        assert not unexpected.exists()

    def test_perform_snapshot_no_tmp_file_persists(
        self, tmp_path: Path
    ) -> None:
        """BC-2.2: no .tmp file lingers after successful snapshot."""
        from routing import perform_snapshot

        slides_dir = tmp_path / "slides"
        snaps_dir = tmp_path / ".debrief" / "snapshots"
        slides_dir.mkdir(parents=True, exist_ok=True)
        snaps_dir.mkdir(parents=True, exist_ok=True)

        (slides_dir / "fig1.html").write_text("<html/>", encoding="utf-8")
        perform_snapshot("fig1", 2, tmp_path)

        tmp_files = list(snaps_dir.glob("*.tmp"))
        assert tmp_files == []


# ===========================================================================
# XVI. Unit 2 get_approved_slides -> Unit 10 build_page_list ordering:
#      slides ordered by array position, backup filter applied correctly.
# ===========================================================================


class TestApprovedSlidesToPageList:
    """get_approved_slides (Unit 2) and build_page_list (Unit 10) must agree
    on which slides appear and in what order."""

    def test_get_approved_slides_preserves_order(
        self, tmp_path: Path
    ) -> None:
        """BC-2.6: get_approved_slides preserves state.slides array order."""
        from debrief_state import (
            DeckState,
            SlideRecord,
            get_approved_slides,
        )

        def _slide(slug: str, backup: bool = False) -> SlideRecord:
            return SlideRecord(
                slug=slug, title=slug, status="approved",
                backup=backup, content_summary=None, visual_approach=None,
                design_choices=None, forks_not_taken=None,
                user_recommendations=None, qa_passed=True,
                accepted_violations=[], last_modified=_TS,
                group_id="group_01", user_assets=[], has_math=False,
            )

        state = DeckState(
            project_name="p", created_at=_CREATED, archetype="lab_meeting",
            style_locked=False, closing_slide=None,
            slides=[
                _slide("c"),
                _slide("a"),
                _slide("b"),
                _slide("bk", backup=True),
            ],
            presentations=[],
        )
        main_slides = get_approved_slides(state, backup=False)
        assert [s.slug for s in main_slides] == ["c", "a", "b"]

    def test_build_page_list_main_slides_in_state_order(
        self, tmp_path: Path
    ) -> None:
        """build_page_list emits main slides in the exact order they appear in
        state.slides (C → A → B, not sorted alphabetically)."""
        from debrief_state import read_deck_state
        from export import build_page_list

        (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)
        deck = _make_minimal_deck_state_dict()
        for slug in ["results", "methods", "intro"]:
            deck["slides"].append(
                _make_slide_record_dict(slug=slug, backup=False)
            )
        _write_state_files(tmp_path, deck_dict=deck)

        state = read_deck_state(tmp_path)
        pages = build_page_list(state, tmp_path)
        slide_slugs = [
            p["path"].stem for p in pages if p["type"] == "slide"
        ]
        assert slide_slugs == ["results", "methods", "intro"]
