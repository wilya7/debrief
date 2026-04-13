# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Tests for Unit 4: Routing Protocol.

Synthetic data generation assumptions
--------------------------------------
- ``DebriefState`` instances are constructed directly from the dataclass
  imported from ``debrief_state`` (Unit 2).  Field values are minimal
  valid values from the allowed enums defined in the Unit 2 signature and
  BC-2.11 / BC-2.14 / BC-2.15.
- ``debrief_state.json`` is written as raw JSON (bypassing Unit 2 writers)
  in tests that exercise ``main_routing``, so the test is independent of
  Unit 2 delivery state.  The ``state_hash`` field is set to an arbitrary
  64-hex-character string because routing is not responsible for hash
  validation.
- ``qa_log.jsonl`` entries use ISO-8601 timestamps.  "Old" entries are
  given timestamp ``2026-01-01T00:00:00Z`` and the cycle start is set to
  ``2026-06-01T00:00:00Z`` so filtering is deterministic.
- "Current-cycle" qa_log entries use timestamps >= ``2026-06-01T00:00:00Z``.
- The ``failures`` list in each qa_log entry is a list of dicts with at
  least an ``invariant`` key.
- Parameterized gate responses for ``validate_gate_response`` tests use the
  prefix ``SLIDE REVISE `` followed by a non-empty instruction payload.
- ``gate_data.json`` is written as minimal JSON with a ``gate_id`` field and
  a ``data`` dict.  Tests that verify mismatch exit use a gate_id that
  differs from the expected_gate_id by exactly one character.
- All ``project_root`` fixtures are fresh ``tmp_path``-based directories with
  the minimal subdirectory structure that the function under test requires
  (``output/``, ``.debrief/``, ``.debrief/snapshots/``, ``slides/``).
- ``promote_style_draft`` tests place a minimal valid ``style_config.json``
  (containing all seven required top-level keys) in
  ``.debrief/draft/style_config.json`` and a stub ``style_guide.md`` in
  ``.debrief/draft/style_guide.md``.  The style_compiler invocation is
  patched via ``unittest.mock`` so the test suite does not depend on a
  working style compiler binary.
- ``perform_snapshot`` tests create a real ``slides/<slug>.html`` file
  containing minimal HTML and verify the snapshot is written atomically.
- ``main_update_state`` invalid-response tests patch
  ``sys.exit`` to capture the exit code without terminating the process.
- All ISO-8601 timestamps in synthetic data use the Zulu suffix ``Z`` and
  are fixed strings (not generated at test-run time) for determinism.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from routing import (
    check_g3_2_machine_gate,
    consume_gate_data,
    handle_red_green_transition,
    main_routing,
    main_update_state,
    perform_snapshot,
    resolve_action,
    validate_gate_response,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DUMMY_HASH = "a" * 64
_OLD_TS = "2026-01-01T00:00:00Z"
_CYCLE_START = "2026-06-01T00:00:00Z"
_AFTER_CYCLE = "2026-06-02T00:00:00Z"
_AFTER_CYCLE_2 = "2026-06-03T00:00:00Z"


def _make_debrief_state_dict(
    phase: str = "discovery",
    sub_phase: str = "discovery/greeting",
    active_agent: str = "consultant",
    archetype: str = "lab_meeting",
    current_group_id: Any = None,
    current_slide_slug: Any = None,
    pending_gate: Any = None,
    last_gate_response: Any = None,
    red_green_iteration: int = 0,
    red_green_started_at: Any = None,
    group_slide_index: int = 0,
    group_slide_count: int = 0,
    backup_mode: bool = False,
    completed_groups: list[str] | None = None,
    pre_view_state: Any = None,
    view_deferred: bool = False,
    closing_slide_pending: bool = False,
    group_revise_slug: Any = None,
    style_import_mode: Any = None,
    reference_provided: bool = False,
    reference_modality: Any = None,
    papers_provided: bool = False,
    selected_figures: Any = None,
    session_started_at: str = "2026-04-11T10:00:00Z",
    state_hash: str = _DUMMY_HASH,
) -> dict[str, Any]:
    return {
        "phase": phase,
        "sub_phase": sub_phase,
        "active_agent": active_agent,
        "archetype": archetype,
        "current_group_id": current_group_id,
        "current_slide_slug": current_slide_slug,
        "pending_gate": pending_gate,
        "last_gate_response": last_gate_response,
        "red_green_iteration": red_green_iteration,
        "red_green_started_at": red_green_started_at,
        "group_slide_index": group_slide_index,
        "group_slide_count": group_slide_count,
        "backup_mode": backup_mode,
        "completed_groups": completed_groups if completed_groups is not None else [],
        "pre_view_state": pre_view_state,
        "view_deferred": view_deferred,
        "closing_slide_pending": closing_slide_pending,
        "group_revise_slug": group_revise_slug,
        "style_import_mode": style_import_mode,
        "reference_provided": reference_provided,
        "reference_modality": reference_modality,
        "papers_provided": papers_provided,
        "selected_figures": selected_figures,
        "session_started_at": session_started_at,
        "state_hash": state_hash,
    }


def _write_debrief_state(project_root: Path, state_dict: dict[str, Any]) -> None:
    """Write a debrief_state.json directly (bypasses Unit 2 writer)."""
    path = project_root / "debrief_state.json"
    path.write_text(json.dumps(state_dict), encoding="utf-8")


def _make_qa_entry(
    slug: str,
    passed: bool,
    timestamp: str,
    failure_invariants: list[str] | None = None,
) -> dict[str, Any]:
    failures: list[dict[str, str]] = (
        [{"invariant": inv} for inv in failure_invariants] if failure_invariants else []
    )
    return {
        "slug": slug,
        "passed": passed,
        "timestamp": timestamp,
        "failures": failures,
    }


def _write_qa_log(project_root: Path, entries: list[dict[str, Any]]) -> None:
    path = project_root / "qa_log.jsonl"
    lines = [json.dumps(e) for e in entries]
    path.write_text("\n".join(lines), encoding="utf-8")


def _make_project_root(tmp_path: Path) -> Path:
    pr = tmp_path / "project"
    pr.mkdir()
    (pr / "output").mkdir()
    (pr / ".debrief").mkdir()
    (pr / ".debrief" / "snapshots").mkdir()
    (pr / "slides").mkdir()
    (pr / ".debrief" / "state.lock").touch()
    return pr


# ---------------------------------------------------------------------------
# BC-4.1: resolve_action purity (no side effects, determinism)
# ---------------------------------------------------------------------------


class TestResolveActionPurity:
    """BC-4.1 — resolve_action must be a pure function with no side effects."""

    def test_same_state_produces_same_action_block(self, tmp_path: Path) -> None:
        """Given identical state, resolve_action returns identical output."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="discovery",
            sub_phase="discovery/greeting",
            active_agent="consultant",
        )
        state = DebriefState(**state_dict)
        result_1 = resolve_action(state, project_root)
        result_2 = resolve_action(state, project_root)
        assert result_1 == result_2

    def test_resolve_action_does_not_write_any_file(self, tmp_path: Path) -> None:
        """resolve_action must not create or modify any files."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="discovery",
            sub_phase="discovery/greeting",
        )
        state = DebriefState(**state_dict)

        files_before = set(project_root.rglob("*"))
        resolve_action(state, project_root)
        files_after = set(project_root.rglob("*"))
        assert files_before == files_after, "resolve_action must not write any files"

    def test_resolve_action_returns_dict(self, tmp_path: Path) -> None:
        """resolve_action must return a dict (the ActionBlock)."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state = DebriefState(
            **_make_debrief_state_dict(
                phase="discovery",
                sub_phase="discovery/greeting",
            )
        )
        result = resolve_action(state, project_root)
        assert isinstance(result, dict)

    def test_different_sub_phases_produce_different_blocks(
        self, tmp_path: Path
    ) -> None:
        """Different sub_phase values must produce different ActionBlocks."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state_greeting = DebriefState(
            **_make_debrief_state_dict(
                phase="discovery",
                sub_phase="discovery/greeting",
            )
        )
        state_dialog = DebriefState(
            **_make_debrief_state_dict(
                phase="discovery",
                sub_phase="discovery/dialog",
            )
        )
        block_greeting = resolve_action(state_greeting, project_root)
        block_dialog = resolve_action(state_dialog, project_root)
        assert block_greeting != block_dialog


# ---------------------------------------------------------------------------
# BC-4.2: ActionBlock schema compliance
# ---------------------------------------------------------------------------


class TestActionBlockSchema:
    """BC-4.2 — Every ActionBlock must have required fields."""

    def test_action_block_contains_action_type(self, tmp_path: Path) -> None:
        """ActionBlock must always contain 'action_type'."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state = DebriefState(
            **_make_debrief_state_dict(
                phase="discovery",
                sub_phase="discovery/greeting",
            )
        )
        block = resolve_action(state, project_root)
        assert "action_type" in block, "ActionBlock must contain 'action_type'"

    def test_action_block_contains_agent_or_gate_id(self, tmp_path: Path) -> None:
        """ActionBlock must contain at least one of 'agent' or 'gate_id'."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state = DebriefState(
            **_make_debrief_state_dict(
                phase="discovery",
                sub_phase="discovery/greeting",
            )
        )
        block = resolve_action(state, project_root)
        assert "agent" in block or "gate_id" in block, (
            "ActionBlock must contain 'agent' or 'gate_id'"
        )

    def test_prepare_field_is_complete_shell_string_when_present(
        self, tmp_path: Path
    ) -> None:
        """If 'prepare' is in the ActionBlock it must be a non-empty string."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state = DebriefState(
            **_make_debrief_state_dict(
                phase="discovery",
                sub_phase="discovery/greeting",
            )
        )
        block = resolve_action(state, project_root)
        if "prepare" in block:
            assert isinstance(block["prepare"], str) and block["prepare"].strip(), (
                "'prepare' must be a complete shell command string"
            )

    def test_post_field_is_complete_shell_string_when_present(
        self, tmp_path: Path
    ) -> None:
        """If 'post' is in the ActionBlock it must be a non-empty string."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state = DebriefState(
            **_make_debrief_state_dict(
                phase="discovery",
                sub_phase="discovery/greeting",
            )
        )
        block = resolve_action(state, project_root)
        if "post" in block:
            assert isinstance(block["post"], str) and block["post"].strip(), (
                "'post' must be a complete shell command string"
            )

    def test_action_block_action_type_is_string(self, tmp_path: Path) -> None:
        """action_type must be a non-empty string."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state = DebriefState(
            **_make_debrief_state_dict(
                phase="style",
                sub_phase="style/style_dialog",
                active_agent="stylist",
            )
        )
        block = resolve_action(state, project_root)
        assert isinstance(block["action_type"], str) and block["action_type"]

    def test_action_block_for_production_phase(self, tmp_path: Path) -> None:
        """ActionBlock for production/group_planning must be schema-compliant."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        # Write a minimal group manifest to satisfy any precondition checks
        briefs_dir = project_root / ".debrief" / "briefs"
        briefs_dir.mkdir(parents=True, exist_ok=True)
        state = DebriefState(
            **_make_debrief_state_dict(
                phase="production",
                sub_phase="production/group_planning",
                active_agent="consultant",
            )
        )
        block = resolve_action(state, project_root)
        assert "action_type" in block
        assert "agent" in block or "gate_id" in block


# ---------------------------------------------------------------------------
# BC-4.3: G3.2 machine gate — qa_log timestamp filter
# ---------------------------------------------------------------------------


class TestCheckG32MachineGateTimestampFilter:
    """BC-4.3 — Entries before red_green_started_at must be ignored."""

    def test_old_entry_before_cycle_start_is_ignored(self, tmp_path: Path) -> None:
        """
        A failing qa_log entry with timestamp < red_green_started_at must
        not influence the result; function should not return RED for it.
        """
        project_root = _make_project_root(tmp_path)
        old_entry = _make_qa_entry("intro_slide", passed=False, timestamp=_OLD_TS)
        # Current-cycle entry is GREEN
        new_entry = _make_qa_entry("intro_slide", passed=True, timestamp=_AFTER_CYCLE)
        _write_qa_log(project_root, [old_entry, new_entry])

        result = check_g3_2_machine_gate("intro_slide", 1, _CYCLE_START, project_root)
        assert result == "GREEN"

    def test_only_entries_from_current_cycle_count(self, tmp_path: Path) -> None:
        """Entries from prior cycles (before started_at) must be excluded."""
        project_root = _make_project_root(tmp_path)
        prior_pass = _make_qa_entry("methods_slide", passed=True, timestamp=_OLD_TS)
        current_fail = _make_qa_entry(
            "methods_slide",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-1"],
        )
        _write_qa_log(project_root, [prior_pass, current_fail])

        result = check_g3_2_machine_gate("methods_slide", 2, _CYCLE_START, project_root)
        assert result == "RED"

    def test_entries_for_different_slug_are_ignored(self, tmp_path: Path) -> None:
        """Entries for a different slug must not affect the result."""
        project_root = _make_project_root(tmp_path)
        other_slug_pass = _make_qa_entry(
            "other_slide", passed=True, timestamp=_AFTER_CYCLE
        )
        current_fail = _make_qa_entry(
            "target_slide",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-2"],
        )
        _write_qa_log(project_root, [other_slug_pass, current_fail])

        result = check_g3_2_machine_gate("target_slide", 1, _CYCLE_START, project_root)
        assert result == "RED"


# ---------------------------------------------------------------------------
# BC-4.3 / check_g3_2_machine_gate return values
# ---------------------------------------------------------------------------


class TestCheckG32MachineGateReturnValues:
    """check_g3_2_machine_gate must return GREEN, RED, EXHAUSTED, or OSCILLATION."""

    def test_returns_green_when_latest_entry_passed(self, tmp_path: Path) -> None:
        """Latest entry with passed=True -> GREEN."""
        project_root = _make_project_root(tmp_path)
        entry = _make_qa_entry("slide_a", passed=True, timestamp=_AFTER_CYCLE)
        _write_qa_log(project_root, [entry])

        result = check_g3_2_machine_gate("slide_a", 1, _CYCLE_START, project_root)
        assert result == "GREEN"

    def test_returns_red_when_failed_and_iteration_below_5(
        self, tmp_path: Path
    ) -> None:
        """Latest entry with passed=False and iteration < 5 -> RED."""
        project_root = _make_project_root(tmp_path)
        entry = _make_qa_entry(
            "slide_b",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-3"],
        )
        _write_qa_log(project_root, [entry])

        result = check_g3_2_machine_gate("slide_b", 3, _CYCLE_START, project_root)
        assert result == "RED"

    def test_returns_exhausted_when_failed_and_iteration_equals_5(
        self, tmp_path: Path
    ) -> None:
        """passed=False and red_green_iteration == 5 -> EXHAUSTED."""
        project_root = _make_project_root(tmp_path)
        entry = _make_qa_entry(
            "slide_c",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-4"],
        )
        _write_qa_log(project_root, [entry])

        result = check_g3_2_machine_gate("slide_c", 5, _CYCLE_START, project_root)
        assert result == "EXHAUSTED"

    def test_returns_exhausted_when_iteration_exceeds_5(self, tmp_path: Path) -> None:
        """passed=False and red_green_iteration > 5 -> EXHAUSTED."""
        project_root = _make_project_root(tmp_path)
        entry = _make_qa_entry(
            "slide_d",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-5"],
        )
        _write_qa_log(project_root, [entry])

        result = check_g3_2_machine_gate("slide_d", 6, _CYCLE_START, project_root)
        assert result == "EXHAUSTED"


# ---------------------------------------------------------------------------
# BC-4.4: Oscillation detection
# ---------------------------------------------------------------------------


class TestOscillationDetection:
    """BC-4.4 — Oscillation: equal failure count, different invariant IDs."""

    def test_detects_oscillation_when_failure_sets_differ(self, tmp_path: Path) -> None:
        """
        Two most-recent entries with equal len(failures) but different
        invariant IDs -> OSCILLATION.
        """
        project_root = _make_project_root(tmp_path)
        entry_1 = _make_qa_entry(
            "slide_e",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-A"],
        )
        entry_2 = _make_qa_entry(
            "slide_e",
            passed=False,
            timestamp=_AFTER_CYCLE_2,
            failure_invariants=["INV-B"],
        )
        _write_qa_log(project_root, [entry_1, entry_2])

        result = check_g3_2_machine_gate("slide_e", 2, _CYCLE_START, project_root)
        assert result == "OSCILLATION"

    def test_no_oscillation_when_same_invariant_ids(self, tmp_path: Path) -> None:
        """Same failure invariant IDs across two entries is not oscillation."""
        project_root = _make_project_root(tmp_path)
        entry_1 = _make_qa_entry(
            "slide_f",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-A"],
        )
        entry_2 = _make_qa_entry(
            "slide_f",
            passed=False,
            timestamp=_AFTER_CYCLE_2,
            failure_invariants=["INV-A"],
        )
        _write_qa_log(project_root, [entry_1, entry_2])

        result = check_g3_2_machine_gate("slide_f", 2, _CYCLE_START, project_root)
        # Same invariant -> not oscillation; should be RED (iteration=2 < 5)
        assert result == "RED"

    def test_no_oscillation_when_failure_counts_differ(self, tmp_path: Path) -> None:
        """Different failure counts across entries is not oscillation."""
        project_root = _make_project_root(tmp_path)
        entry_1 = _make_qa_entry(
            "slide_g",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-A"],
        )
        entry_2 = _make_qa_entry(
            "slide_g",
            passed=False,
            timestamp=_AFTER_CYCLE_2,
            failure_invariants=["INV-A", "INV-B"],
        )
        _write_qa_log(project_root, [entry_1, entry_2])

        result = check_g3_2_machine_gate("slide_g", 2, _CYCLE_START, project_root)
        assert result != "OSCILLATION"


# ---------------------------------------------------------------------------
# BC-4.5: update_state invalid response exits with code 4
# ---------------------------------------------------------------------------


class TestMainUpdateStateInvalidResponseExitCode:
    """BC-4.5 — Invalid response must exit code 4 without writing state."""

    def test_invalid_response_exits_with_code_4(self, tmp_path: Path) -> None:
        """main_update_state exits code 4 on invalid response."""
        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="discovery",
            sub_phase="discovery/greeting",
        )
        _write_debrief_state(project_root, state_dict)

        with pytest.raises(SystemExit) as exc_info:
            main_update_state(
                gate_id="G1.1_greeting",
                response="TOTALLY_INVALID_RESPONSE_XYZ",
                project_root=project_root,
            )
        assert exc_info.value.code == 4

    def test_invalid_response_prints_to_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """On invalid response, stderr must contain 'Invalid response. Expected:'."""
        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="discovery",
            sub_phase="discovery/greeting",
        )
        _write_debrief_state(project_root, state_dict)

        with pytest.raises(SystemExit):
            main_update_state(
                gate_id="G1.1_greeting",
                response="TOTALLY_INVALID_RESPONSE_XYZ",
                project_root=project_root,
            )
        captured = capsys.readouterr()
        assert "Invalid response" in captured.err
        assert "Expected" in captured.err

    def test_invalid_response_does_not_write_state(self, tmp_path: Path) -> None:
        """main_update_state must not write state changes on invalid response."""
        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="discovery",
            sub_phase="discovery/greeting",
        )
        _write_debrief_state(project_root, state_dict)
        original_content = (project_root / "debrief_state.json").read_text()

        with pytest.raises(SystemExit):
            main_update_state(
                gate_id="G1.1_greeting",
                response="TOTALLY_INVALID_RESPONSE_XYZ",
                project_root=project_root,
            )
        after_content = (project_root / "debrief_state.json").read_text()
        assert original_content == after_content, (
            "debrief_state.json must not be modified on invalid response"
        )


# ---------------------------------------------------------------------------
# BC-4.5 + BC-4.13: skill-prelude mode skips validation
# ---------------------------------------------------------------------------


class TestMainUpdateStateSkillPreludeMode:
    """BC-4.13 — skill-prelude mode writes field assignments, skips validation."""

    def test_skill_prelude_does_not_validate_gate_response(
        self, tmp_path: Path
    ) -> None:
        """
        In skill-prelude mode, no gate validation occurs: the call must
        not exit with code 4 even when gate_id is absent or response is empty.
        """
        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="production",
            sub_phase="production/red_green",
            active_agent="slide_maker",
            current_slide_slug="my_slide",
        )
        _write_debrief_state(project_root, state_dict)

        # Should not raise SystemExit
        main_update_state(
            gate_id="",
            response="",
            project_root=project_root,
            skill_prelude="slide",
            field_assignments=["current_slide_slug=my_slide"],
        )

    def test_skill_prelude_writes_field_assignment_to_state(
        self, tmp_path: Path
    ) -> None:
        """
        skill-prelude mode must write the given field assignments to
        debrief_state.json.
        """
        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="production",
            sub_phase="production/red_green",
            active_agent="slide_maker",
        )
        _write_debrief_state(project_root, state_dict)

        main_update_state(
            gate_id="",
            response="",
            project_root=project_root,
            skill_prelude="slide",
            field_assignments=["current_slide_slug=results_overview"],
        )
        written = json.loads((project_root / "debrief_state.json").read_text())
        assert written["current_slide_slug"] == "results_overview"


# ---------------------------------------------------------------------------
# BC-4.6: promote_style_draft sequence
# ---------------------------------------------------------------------------


class TestPromoteStyleDraft:
    """BC-4.6 — promote_style_draft executes the seven-step sequence."""

    def _make_draft_dir(self, project_root: Path) -> None:
        draft = project_root / ".debrief" / "draft"
        draft.mkdir(parents=True, exist_ok=True)
        style_config = {
            "colors": {},
            "typography": {},
            "spacing": {},
            "layout": {},
            "data_viz": {},
            "constraints": {},
            "provenance": {},
        }
        (draft / "style_config.json").write_text(
            json.dumps(style_config), encoding="utf-8"
        )
        (draft / "style_guide.md").write_text("# Style Guide\n", encoding="utf-8")

    def _make_deck_state(self, project_root: Path) -> None:
        deck = {
            "project_name": "test_project",
            "created_at": "2026-04-11T10:00:00Z",
            "archetype": "lab_meeting",
            "style_locked": False,
            "closing_slide": None,
            "slides": [],
            "presentations": [],
        }
        (project_root / "deck_state.json").write_text(
            json.dumps(deck), encoding="utf-8"
        )

    def test_style_config_promoted_to_project_root_on_success(
        self, tmp_path: Path
    ) -> None:
        """
        On successful compilation, style_config.json and style_guide.md
        must exist at project root.
        """
        from routing import promote_style_draft

        project_root = _make_project_root(tmp_path)
        (project_root / "assets" / "style.css").parent.mkdir(
            parents=True, exist_ok=True
        )
        self._make_draft_dir(project_root)
        self._make_deck_state(project_root)

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0, stderr="")
            promote_style_draft(project_root)

        assert (project_root / "style_config.json").exists()
        assert (project_root / "style_guide.md").exists()

    def test_style_locked_set_true_on_success(self, tmp_path: Path) -> None:
        """After successful promote_style_draft, style_locked must be True."""
        from routing import promote_style_draft

        project_root = _make_project_root(tmp_path)
        (project_root / "assets" / "style.css").parent.mkdir(
            parents=True, exist_ok=True
        )
        self._make_draft_dir(project_root)
        self._make_deck_state(project_root)

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0, stderr="")
            promote_style_draft(project_root)

        deck = json.loads((project_root / "deck_state.json").read_text())
        assert deck["style_locked"] is True

    def test_draft_dir_removed_after_success(self, tmp_path: Path) -> None:
        """After successful compile, .debrief/draft/ must be removed."""
        from routing import promote_style_draft

        project_root = _make_project_root(tmp_path)
        (project_root / "assets" / "style.css").parent.mkdir(
            parents=True, exist_ok=True
        )
        self._make_draft_dir(project_root)
        self._make_deck_state(project_root)

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0, stderr="")
            promote_style_draft(project_root)

        assert not (project_root / ".debrief" / "draft").exists()

    def test_compiler_failure_does_not_set_style_locked(self, tmp_path: Path) -> None:
        """
        BC-4.6: on compiler failure, style_locked must remain False.
        """
        from routing import promote_style_draft

        project_root = _make_project_root(tmp_path)
        (project_root / "assets" / "style.css").parent.mkdir(
            parents=True, exist_ok=True
        )
        self._make_draft_dir(project_root)
        self._make_deck_state(project_root)

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                returncode=1, stderr="compilation error"
            )
            with pytest.raises((RuntimeError, SystemExit)):
                promote_style_draft(project_root)

        deck = json.loads((project_root / "deck_state.json").read_text())
        assert deck["style_locked"] is False

    def test_compiler_failure_leaves_promoted_files_intact(
        self, tmp_path: Path
    ) -> None:
        """
        BC-4.6: on compiler failure, the promoted style_config.json
        and style_guide.md at project root must NOT be rolled back.
        """
        from routing import promote_style_draft

        project_root = _make_project_root(tmp_path)
        (project_root / "assets" / "style.css").parent.mkdir(
            parents=True, exist_ok=True
        )
        self._make_draft_dir(project_root)
        self._make_deck_state(project_root)

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                returncode=1, stderr="compilation error"
            )
            with pytest.raises((RuntimeError, SystemExit)):
                promote_style_draft(project_root)

        # The files must have been promoted to project root even on failure
        assert (project_root / "style_config.json").exists()
        assert (project_root / "style_guide.md").exists()


# ---------------------------------------------------------------------------
# BC-4.7: consume_gate_data cross-cycle rule
# ---------------------------------------------------------------------------


class TestConsumeGateData:
    """BC-4.7 — consume_gate_data delete-on-match, exit-4 on mismatch."""

    def test_returns_none_when_file_absent(self, tmp_path: Path) -> None:
        """When gate_data.json does not exist, return None."""
        project_root = _make_project_root(tmp_path)
        result = consume_gate_data("G1.3_figure_selection", project_root)
        assert result is None

    def test_returns_data_and_deletes_file_on_match(self, tmp_path: Path) -> None:
        """When gate_id matches, return data dict and delete the file."""
        project_root = _make_project_root(tmp_path)
        gate_data = {
            "gate_id": "G1.3_figure_selection",
            "data": {"selected_figures": [1, 2, 3]},
        }
        gate_file = project_root / ".debrief" / "gate_data.json"
        gate_file.write_text(json.dumps(gate_data), encoding="utf-8")

        result = consume_gate_data("G1.3_figure_selection", project_root)

        assert result == {"selected_figures": [1, 2, 3]}
        assert not gate_file.exists(), "gate_data.json must be deleted after match"

    def test_exits_code_4_on_gate_id_mismatch(self, tmp_path: Path) -> None:
        """When gate_id mismatches expected, must exit with code 4."""
        project_root = _make_project_root(tmp_path)
        gate_data = {
            "gate_id": "G1.3_figure_selection",
            "data": {"selected_figures": [1, 2]},
        }
        gate_file = project_root / ".debrief" / "gate_data.json"
        gate_file.write_text(json.dumps(gate_data), encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            consume_gate_data("G2.1_style_config_review", project_root)
        assert exc_info.value.code == 4

    def test_gate_data_file_not_deleted_on_mismatch(self, tmp_path: Path) -> None:
        """On gate_id mismatch, the file must remain (we exit before deleting)."""
        project_root = _make_project_root(tmp_path)
        gate_data = {
            "gate_id": "G1.3_figure_selection",
            "data": {},
        }
        gate_file = project_root / ".debrief" / "gate_data.json"
        gate_file.write_text(json.dumps(gate_data), encoding="utf-8")

        with pytest.raises(SystemExit):
            consume_gate_data("G2.1_style_config_review", project_root)

        # File should still exist (we exited before any delete could happen)
        assert gate_file.exists()


# ---------------------------------------------------------------------------
# validate_gate_response — exact matches, parameterized gates
# ---------------------------------------------------------------------------


class TestValidateGateResponse:
    """validate_gate_response must correctly accept and reject responses."""

    def test_exact_match_returns_true(self) -> None:
        """Exact string in valid_responses returns True."""
        result = validate_gate_response(
            "G1.1_greeting",
            "CONTINUE",
            ["CONTINUE", "QUIT"],
        )
        assert result is True

    def test_non_matching_response_returns_false(self) -> None:
        """Response not in valid_responses returns False."""
        result = validate_gate_response(
            "G1.1_greeting",
            "INVALID_OPTION",
            ["CONTINUE", "QUIT"],
        )
        assert result is False

    def test_empty_response_returns_false_for_non_empty_list(self) -> None:
        """Empty string is not valid when valid_responses is non-empty."""
        result = validate_gate_response(
            "G1.1_greeting",
            "",
            ["CONTINUE", "QUIT"],
        )
        assert result is False

    def test_parameterized_gate_valid_prefix_returns_true(self) -> None:
        """Parameterized gate: valid prefix with payload returns True."""
        result = validate_gate_response(
            "G3.2_qa_review",
            "SLIDE REVISE fix the title alignment",
            ["APPROVE", "SLIDE REVISE <instructions>"],
        )
        assert result is True

    def test_parameterized_gate_prefix_only_returns_false(self) -> None:
        """Parameterized gate: prefix without payload returns False."""
        result = validate_gate_response(
            "G3.2_qa_review",
            "SLIDE REVISE",
            ["APPROVE", "SLIDE REVISE <instructions>"],
        )
        assert result is False

    def test_parameterized_gate_wrong_prefix_returns_false(self) -> None:
        """Parameterized gate: wrong prefix returns False."""
        result = validate_gate_response(
            "G3.2_qa_review",
            "SLIDE REVERT some instructions",
            ["APPROVE", "SLIDE REVISE <instructions>"],
        )
        assert result is False

    def test_case_sensitive_matching(self) -> None:
        """Matching is case-sensitive: 'continue' != 'CONTINUE'."""
        result = validate_gate_response(
            "G1.1_greeting",
            "continue",
            ["CONTINUE", "QUIT"],
        )
        assert result is False

    def test_second_exact_match_returns_true(self) -> None:
        """A response matching the second item in valid_responses returns True."""
        result = validate_gate_response(
            "G1.1_greeting",
            "QUIT",
            ["CONTINUE", "QUIT"],
        )
        assert result is True


# ---------------------------------------------------------------------------
# perform_snapshot — atomic copy with 1-indexed filename
# ---------------------------------------------------------------------------


class TestPerformSnapshot:
    """perform_snapshot must write <slug>_iter_<N>.html atomically."""

    def test_snapshot_is_written_at_correct_path(self, tmp_path: Path) -> None:
        """Snapshot written to .debrief/snapshots/<slug>_iter_<N>.html."""
        project_root = _make_project_root(tmp_path)
        (project_root / "slides" / "results_slide.html").write_text(
            "<html></html>", encoding="utf-8"
        )

        perform_snapshot("results_slide", 1, project_root)

        expected = project_root / ".debrief" / "snapshots" / "results_slide_iter_1.html"
        assert expected.exists()

    def test_snapshot_content_matches_source(self, tmp_path: Path) -> None:
        """Snapshot file must contain identical content to the source slide."""
        project_root = _make_project_root(tmp_path)
        source_content = "<html><body>slide content</body></html>"
        (project_root / "slides" / "discussion.html").write_text(
            source_content, encoding="utf-8"
        )

        perform_snapshot("discussion", 3, project_root)

        snapshot = project_root / ".debrief" / "snapshots" / "discussion_iter_3.html"
        assert snapshot.read_text(encoding="utf-8") == source_content

    def test_snapshot_filename_is_1_indexed_not_zero_padded(
        self, tmp_path: Path
    ) -> None:
        """Iteration N appears in filename as 'iter_N' (not 'iter_0N')."""
        project_root = _make_project_root(tmp_path)
        (project_root / "slides" / "intro.html").write_text(
            "<html></html>", encoding="utf-8"
        )

        perform_snapshot("intro", 2, project_root)

        # Should be iter_2, NOT iter_02
        expected = project_root / ".debrief" / "snapshots" / "intro_iter_2.html"
        assert expected.exists()
        # Confirm zero-padded path does NOT exist
        wrong = project_root / ".debrief" / "snapshots" / "intro_iter_02.html"
        assert not wrong.exists()

    def test_no_leftover_tmp_file_after_snapshot(self, tmp_path: Path) -> None:
        """No .tmp file must remain after perform_snapshot completes."""
        project_root = _make_project_root(tmp_path)
        (project_root / "slides" / "conclusion.html").write_text(
            "<html></html>", encoding="utf-8"
        )

        perform_snapshot("conclusion", 1, project_root)

        snapshots_dir = project_root / ".debrief" / "snapshots"
        tmp_files = list(snapshots_dir.glob("*.tmp"))
        assert tmp_files == [], "No .tmp files must remain after snapshot"


# ---------------------------------------------------------------------------
# handle_red_green_transition
# ---------------------------------------------------------------------------


class TestHandleRedGreenTransition:
    """handle_red_green_transition manages iteration counter and snapshot logic."""

    def test_increments_red_green_iteration(self, tmp_path: Path) -> None:
        """red_green_iteration must be incremented on each RED cycle."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="production",
            sub_phase="production/red_green",
            active_agent="none",
            current_slide_slug="methodology_overview",
            red_green_iteration=1,
            red_green_started_at=_CYCLE_START,
        )
        state = DebriefState(**state_dict)
        _write_debrief_state(project_root, state_dict)
        (project_root / "slides" / "methodology_overview.html").write_text(
            "<html></html>", encoding="utf-8"
        )

        handle_red_green_transition(
            "G3.2_qa_review", "SLIDE REVISE fix alignment", state, project_root
        )

        written = json.loads((project_root / "debrief_state.json").read_text())
        assert written["red_green_iteration"] == 2

    def test_sets_red_green_started_at_on_first_iteration(self, tmp_path: Path) -> None:
        """
        When red_green_started_at is None, it must be set to a non-empty
        ISO-8601 timestamp on the first iteration.
        """
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="production",
            sub_phase="production/red_green",
            active_agent="none",
            current_slide_slug="intro_slide",
            red_green_iteration=0,
            red_green_started_at=None,
        )
        state = DebriefState(**state_dict)
        _write_debrief_state(project_root, state_dict)
        (project_root / "slides" / "intro_slide.html").write_text(
            "<html></html>", encoding="utf-8"
        )

        handle_red_green_transition(
            "G3.2_qa_review", "SLIDE REVISE fix content", state, project_root
        )

        written = json.loads((project_root / "debrief_state.json").read_text())
        assert written["red_green_started_at"] is not None
        ts = written["red_green_started_at"]
        assert isinstance(ts, str) and "T" in ts, (
            "red_green_started_at must be an ISO-8601 timestamp"
        )

    def test_writes_qa_cycle_log_on_green_exit(self, tmp_path: Path) -> None:
        """
        BC-4.9: On GREEN exit, update_state must write qa_cycle_log.jsonl.
        handle_red_green_transition is responsible for this write.
        """
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="production",
            sub_phase="production/red_green",
            active_agent="none",
            current_slide_slug="results_slide",
            red_green_iteration=2,
            red_green_started_at=_CYCLE_START,
        )
        state = DebriefState(**state_dict)
        _write_debrief_state(project_root, state_dict)
        (project_root / "slides" / "results_slide.html").write_text(
            "<html></html>", encoding="utf-8"
        )

        handle_red_green_transition("G3.2_qa_review", "APPROVE", state, project_root)

        qa_log_path = project_root / "output" / "qa_cycle_log.jsonl"
        assert qa_log_path.exists(), "qa_cycle_log.jsonl must be written on cycle exit"

    def test_qa_cycle_log_entry_has_required_fields_on_green(
        self, tmp_path: Path
    ) -> None:
        """
        BC-4.14: qa_cycle_log.jsonl entry must contain the 7 required fields.
        """
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="production",
            sub_phase="production/red_green",
            active_agent="none",
            current_slide_slug="summary_slide",
            red_green_iteration=1,
            red_green_started_at=_CYCLE_START,
        )
        state = DebriefState(**state_dict)
        _write_debrief_state(project_root, state_dict)
        (project_root / "slides" / "summary_slide.html").write_text(
            "<html></html>", encoding="utf-8"
        )

        handle_red_green_transition("G3.2_qa_review", "APPROVE", state, project_root)

        qa_log_path = project_root / "output" / "qa_cycle_log.jsonl"
        entry = json.loads(qa_log_path.read_text().strip().splitlines()[-1])
        required_fields = {
            "slug",
            "started_at",
            "completed_at",
            "iterations",
            "final_status",
            "tier1_failures_by_iteration",
            "tier2_warnings",
        }
        assert required_fields == set(entry.keys()), (
            f"qa_cycle_log entry must have exactly {required_fields}"
        )

    def test_qa_cycle_log_final_status_is_green_lowercase(self, tmp_path: Path) -> None:
        """BC-4.14: final_status for APPROVE must be 'green' (lowercase)."""
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="production",
            sub_phase="production/red_green",
            active_agent="none",
            current_slide_slug="discussion_slide",
            red_green_iteration=1,
            red_green_started_at=_CYCLE_START,
        )
        state = DebriefState(**state_dict)
        _write_debrief_state(project_root, state_dict)
        (project_root / "slides" / "discussion_slide.html").write_text(
            "<html></html>", encoding="utf-8"
        )

        handle_red_green_transition("G3.2_qa_review", "APPROVE", state, project_root)

        qa_log_path = project_root / "output" / "qa_cycle_log.jsonl"
        entry = json.loads(qa_log_path.read_text().strip().splitlines()[-1])
        assert entry["final_status"] == "green"

    def test_snapshots_deleted_on_green_exit(self, tmp_path: Path) -> None:
        """
        BC-4.10: on GREEN exit, snapshots for the completed slug must be
        deleted.
        """
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        slug = "closing_slide"
        state_dict = _make_debrief_state_dict(
            phase="production",
            sub_phase="production/red_green",
            active_agent="none",
            current_slide_slug=slug,
            red_green_iteration=2,
            red_green_started_at=_CYCLE_START,
        )
        state = DebriefState(**state_dict)
        _write_debrief_state(project_root, state_dict)
        (project_root / "slides" / f"{slug}.html").write_text(
            "<html></html>", encoding="utf-8"
        )

        # Create synthetic snapshot files for this slug
        snapshots_dir = project_root / ".debrief" / "snapshots"
        snap1 = snapshots_dir / f"{slug}_iter_1.html"
        snap2 = snapshots_dir / f"{slug}_iter_2.html"
        snap1.write_text("<html></html>", encoding="utf-8")
        snap2.write_text("<html></html>", encoding="utf-8")

        # Create a snapshot for a different slug that must be preserved
        other_snap = snapshots_dir / "other_slide_iter_1.html"
        other_snap.write_text("<html></html>", encoding="utf-8")

        handle_red_green_transition("G3.2_qa_review", "APPROVE", state, project_root)

        assert not snap1.exists(), "iter_1 snapshot must be deleted on GREEN"
        assert not snap2.exists(), "iter_2 snapshot must be deleted on GREEN"
        assert other_snap.exists(), "Snapshots for other slugs must be preserved"


# ---------------------------------------------------------------------------
# main_routing — reads debrief_state.json, outputs ActionBlock to stdout
# ---------------------------------------------------------------------------


class TestMainRouting:
    """main_routing must write an ActionBlock JSON to stdout with no side effects."""

    def test_outputs_json_to_stdout(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """main_routing must print valid JSON to stdout."""
        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="discovery",
            sub_phase="discovery/greeting",
        )
        _write_debrief_state(project_root, state_dict)

        main_routing(project_root)

        captured = capsys.readouterr()
        block = json.loads(captured.out)
        assert isinstance(block, dict)

    def test_output_contains_action_type(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Stdout JSON must contain 'action_type'."""
        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="discovery",
            sub_phase="discovery/greeting",
        )
        _write_debrief_state(project_root, state_dict)

        main_routing(project_root)

        captured = capsys.readouterr()
        block = json.loads(captured.out)
        assert "action_type" in block

    def test_does_not_write_any_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """main_routing must have no side effects (no file writes)."""
        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="discovery",
            sub_phase="discovery/greeting",
        )
        _write_debrief_state(project_root, state_dict)

        files_before = {p: p.stat().st_mtime for p in project_root.rglob("*")}
        main_routing(project_root)
        files_after = {p: p.stat().st_mtime for p in project_root.rglob("*")}

        assert files_before == files_after, "main_routing must not write any file"

    def test_same_state_always_same_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-4.1: same state always produces same ActionBlock (purity)."""
        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="style",
            sub_phase="style/style_dialog",
            active_agent="stylist",
        )
        _write_debrief_state(project_root, state_dict)

        main_routing(project_root)
        out1 = capsys.readouterr().out

        main_routing(project_root)
        out2 = capsys.readouterr().out

        assert json.loads(out1) == json.loads(out2)


# ---------------------------------------------------------------------------
# BC-4.17: Snapshot iteration filename format (1-indexed, not zero-padded)
# ---------------------------------------------------------------------------


class TestSnapshotFilenameFormat:
    """BC-4.17 — Snapshots use <slug>_iter_<N>.html (1-indexed, no padding)."""

    @pytest.mark.parametrize("iteration", [1, 2, 3, 4, 5])
    def test_snapshot_filename_range_1_to_5(
        self, tmp_path: Path, iteration: int
    ) -> None:
        """perform_snapshot writes the correct filename for iterations 1-5."""
        project_root = _make_project_root(tmp_path)
        (project_root / "slides" / "test_slide.html").write_text(
            "<html></html>", encoding="utf-8"
        )

        perform_snapshot("test_slide", iteration, project_root)

        expected = (
            project_root
            / ".debrief"
            / "snapshots"
            / f"test_slide_iter_{iteration}.html"
        )
        assert expected.exists(), (
            f"Snapshot for iteration {iteration} must be at "
            f"test_slide_iter_{iteration}.html"
        )


# ---------------------------------------------------------------------------
# BC-4.11: G1.3 figure selection writes selected_figures to debrief_state
# ---------------------------------------------------------------------------


class TestFigureSelectionWritesToDebriefState:
    """BC-4.11 — G1.3 response must persist selected_figures in debrief_state."""

    def test_integer_list_written_to_debrief_state(self, tmp_path: Path) -> None:
        """selected_figures as a list of ints must be written to state."""
        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="discovery",
            sub_phase="discovery/figure_selection",
            active_agent="consultant",
            papers_provided=True,
        )
        _write_debrief_state(project_root, state_dict)

        main_update_state(
            gate_id="G1.3_figure_selection",
            response="1 2 3",
            project_root=project_root,
        )

        written = json.loads((project_root / "debrief_state.json").read_text())
        sf = written.get("selected_figures")
        # Must be a list of ints or the string "all"
        assert sf is not None
        if isinstance(sf, list):
            assert all(isinstance(x, int) for x in sf)
        else:
            assert sf == "all"

    def test_all_string_written_to_debrief_state(self, tmp_path: Path) -> None:
        """selected_figures='all' must be written directly to debrief_state."""
        project_root = _make_project_root(tmp_path)
        state_dict = _make_debrief_state_dict(
            phase="discovery",
            sub_phase="discovery/figure_selection",
            active_agent="consultant",
            papers_provided=True,
        )
        _write_debrief_state(project_root, state_dict)

        main_update_state(
            gate_id="G1.3_figure_selection",
            response="all",
            project_root=project_root,
        )

        written = json.loads((project_root / "debrief_state.json").read_text())
        sf = written.get("selected_figures")
        assert sf is not None, "selected_figures must be written to debrief_state"
        # selected_figures must NOT be written to gate_data.json
        gate_data_file = project_root / ".debrief" / "gate_data.json"
        if gate_data_file.exists():
            gd = json.loads(gate_data_file.read_text())
            if isinstance(gd, dict) and "data" in gd:
                assert "selected_figures" not in gd.get("data", {}), (
                    "selected_figures must not be written to gate_data.json"
                )


# ---------------------------------------------------------------------------
# BC-4.1 gap: resolve_action must not invoke any subprocess
# ---------------------------------------------------------------------------


class TestResolveActionNoSubprocess:
    """BC-4.1 — resolve_action must not invoke any subprocess."""

    def test_resolve_action_does_not_invoke_subprocess(
        self, tmp_path: Path
    ) -> None:
        """
        resolve_action must not call subprocess.run, subprocess.Popen,
        os.system, or any equivalent. BC-4.1 states explicitly: no
        subprocess invocations.
        """
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state = DebriefState(
            **_make_debrief_state_dict(
                phase="production",
                sub_phase="production/group_planning",
                active_agent="consultant",
            )
        )

        with mock.patch("subprocess.run") as mock_run, mock.patch(
            "subprocess.Popen"
        ) as mock_popen, mock.patch("os.system") as mock_sys:
            resolve_action(state, project_root)
            mock_run.assert_not_called()
            mock_popen.assert_not_called()
            mock_sys.assert_not_called()

    def test_resolve_action_no_subprocess_for_style_phase(
        self, tmp_path: Path
    ) -> None:
        """
        resolve_action must not invoke a subprocess even in style phase
        sub-states.
        """
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)
        state = DebriefState(
            **_make_debrief_state_dict(
                phase="style",
                sub_phase="style/style_lock",
                active_agent="stylist",
            )
        )

        with mock.patch("subprocess.run") as mock_run, mock.patch(
            "subprocess.Popen"
        ) as mock_popen:
            resolve_action(state, project_root)
            mock_run.assert_not_called()
            mock_popen.assert_not_called()


# ---------------------------------------------------------------------------
# BC-4.4 gap: resolve_action emits G3.2a human_gate on OSCILLATION
# ---------------------------------------------------------------------------


class TestResolveActionOscillationRouting:
    """BC-4.4 — resolve_action must emit human_gate G3.2a on oscillation."""

    def test_resolve_action_emits_g32a_when_oscillation_detected(
        self, tmp_path: Path
    ) -> None:
        """
        When check_g3_2_machine_gate returns OSCILLATION, resolve_action
        must return an ActionBlock with action_type='human_gate' and
        gate_id='G3.2a_oscillation_review', NOT a RED slide_maker dispatch.
        """
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)

        # Two current-cycle entries: same failure count, different invariants
        entry_1 = _make_qa_entry(
            "osc_slide",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-A"],
        )
        entry_2 = _make_qa_entry(
            "osc_slide",
            passed=False,
            timestamp=_AFTER_CYCLE_2,
            failure_invariants=["INV-B"],
        )
        _write_qa_log(project_root, [entry_1, entry_2])

        state = DebriefState(
            **_make_debrief_state_dict(
                phase="production",
                sub_phase="production/red_green",
                active_agent="none",
                current_slide_slug="osc_slide",
                red_green_iteration=2,
                red_green_started_at=_CYCLE_START,
            )
        )

        block = resolve_action(state, project_root)

        assert block.get("action_type") == "human_gate", (
            "resolve_action must emit human_gate on oscillation"
        )
        assert block.get("gate_id") == "G3.2a_oscillation_review", (
            "resolve_action must route to G3.2a_oscillation_review on oscillation"
        )

    def test_resolve_action_does_not_emit_g32a_when_no_oscillation(
        self, tmp_path: Path
    ) -> None:
        """
        When check_g3_2_machine_gate does not detect oscillation (RED),
        resolve_action must return an agent ActionBlock for slide_maker,
        NOT G3.2a.
        """
        from debrief_state import DebriefState

        project_root = _make_project_root(tmp_path)

        # Two current-cycle entries: same failure invariant (not oscillation)
        entry_1 = _make_qa_entry(
            "stable_slide",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-A"],
        )
        entry_2 = _make_qa_entry(
            "stable_slide",
            passed=False,
            timestamp=_AFTER_CYCLE_2,
            failure_invariants=["INV-A"],
        )
        _write_qa_log(project_root, [entry_1, entry_2])

        state = DebriefState(
            **_make_debrief_state_dict(
                phase="production",
                sub_phase="production/red_green",
                active_agent="none",
                current_slide_slug="stable_slide",
                red_green_iteration=2,
                red_green_started_at=_CYCLE_START,
            )
        )

        block = resolve_action(state, project_root)

        assert block.get("action_type") == "agent", (
            "resolve_action must dispatch to agent when not oscillating"
        )
        assert block.get("agent") == "slide_maker", (
            "resolve_action must route to slide_maker on RED (non-oscillation)"
        )


# ---------------------------------------------------------------------------
# BC-4.4 gap: timestamp filter is applied before oscillation detection
# ---------------------------------------------------------------------------


class TestOscillationTimestampFilter:
    """
    BC-4.3/BC-4.4 — old-cycle entries must not participate in oscillation
    detection. The timestamp filter is applied first; oscillation is
    evaluated on current-cycle entries only.
    """

    def test_oscillation_not_detected_when_only_one_current_cycle_entry(
        self, tmp_path: Path
    ) -> None:
        """
        If only one entry falls within the current cycle (the other is a
        prior-cycle entry that would otherwise look like an oscillating
        pair), oscillation must NOT be detected.
        """
        project_root = _make_project_root(tmp_path)

        # Prior-cycle entry with a different invariant
        old_entry = _make_qa_entry(
            "cycle_filter_slide",
            passed=False,
            timestamp=_OLD_TS,
            failure_invariants=["INV-OLD"],
        )
        # Current-cycle entry with a different invariant
        new_entry = _make_qa_entry(
            "cycle_filter_slide",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-NEW"],
        )
        _write_qa_log(project_root, [old_entry, new_entry])

        # Only one current-cycle entry exists, so oscillation cannot fire
        result = check_g3_2_machine_gate(
            "cycle_filter_slide", 1, _CYCLE_START, project_root
        )
        assert result != "OSCILLATION", (
            "Oscillation must not be detected when only one current-cycle "
            "entry is present (the other belongs to a prior cycle)"
        )

    def test_oscillation_detected_only_on_current_cycle_entries(
        self, tmp_path: Path
    ) -> None:
        """
        With two current-cycle entries that have different invariant IDs
        (and one earlier prior-cycle entry with yet another invariant),
        oscillation IS detected -- confirming prior entries are excluded
        from the pair comparison.
        """
        project_root = _make_project_root(tmp_path)

        old_entry = _make_qa_entry(
            "pair_slide",
            passed=False,
            timestamp=_OLD_TS,
            failure_invariants=["INV-PRE"],
        )
        entry_1 = _make_qa_entry(
            "pair_slide",
            passed=False,
            timestamp=_AFTER_CYCLE,
            failure_invariants=["INV-A"],
        )
        entry_2 = _make_qa_entry(
            "pair_slide",
            passed=False,
            timestamp=_AFTER_CYCLE_2,
            failure_invariants=["INV-B"],
        )
        _write_qa_log(project_root, [old_entry, entry_1, entry_2])

        result = check_g3_2_machine_gate(
            "pair_slide", 2, _CYCLE_START, project_root
        )
        assert result == "OSCILLATION", (
            "Oscillation must be detected when the two most-recent "
            "current-cycle entries have equal failure count but "
            "different invariant IDs"
        )


# ---------------------------------------------------------------------------
# BC-4.6 gap: chmod 444 applied to promoted files after successful compile
# ---------------------------------------------------------------------------


class TestPromoteStyleDraftChmod:
    """BC-4.6 — style_config.json and style_guide.md must be chmod 444."""

    def _make_draft_dir(self, project_root: Path) -> None:
        draft = project_root / ".debrief" / "draft"
        draft.mkdir(parents=True, exist_ok=True)
        style_config = {
            "colors": {},
            "typography": {},
            "spacing": {},
            "layout": {},
            "data_viz": {},
            "constraints": {},
            "provenance": {},
        }
        (draft / "style_config.json").write_text(
            json.dumps(style_config), encoding="utf-8"
        )
        (draft / "style_guide.md").write_text(
            "# Style Guide\n", encoding="utf-8"
        )

    def _make_deck_state(self, project_root: Path) -> None:
        deck = {
            "project_name": "test_project",
            "created_at": "2026-04-11T10:00:00Z",
            "archetype": "lab_meeting",
            "style_locked": False,
            "closing_slide": None,
            "slides": [],
            "presentations": [],
        }
        (project_root / "deck_state.json").write_text(
            json.dumps(deck), encoding="utf-8"
        )

    def test_style_config_is_readonly_after_successful_promote(
        self, tmp_path: Path
    ) -> None:
        """
        BC-4.6 step 5: style_config.json must have mode 0o444
        (read-only for all) after a successful promotion.
        """
        import stat
        from routing import promote_style_draft

        project_root = _make_project_root(tmp_path)
        (project_root / "assets" / "style.css").parent.mkdir(
            parents=True, exist_ok=True
        )
        self._make_draft_dir(project_root)
        self._make_deck_state(project_root)

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0, stderr="")
            promote_style_draft(project_root)

        cfg_path = project_root / "style_config.json"
        mode = cfg_path.stat().st_mode & 0o777
        assert mode == 0o444, (
            f"style_config.json must be chmod 444 after promotion, "
            f"got {oct(mode)}"
        )

    def test_style_guide_is_readonly_after_successful_promote(
        self, tmp_path: Path
    ) -> None:
        """
        BC-4.6 step 5: style_guide.md must have mode 0o444
        (read-only for all) after a successful promotion.
        """
        import stat
        from routing import promote_style_draft

        project_root = _make_project_root(tmp_path)
        (project_root / "assets" / "style.css").parent.mkdir(
            parents=True, exist_ok=True
        )
        self._make_draft_dir(project_root)
        self._make_deck_state(project_root)

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(returncode=0, stderr="")
            promote_style_draft(project_root)

        guide_path = project_root / "style_guide.md"
        mode = guide_path.stat().st_mode & 0o777
        assert mode == 0o444, (
            f"style_guide.md must be chmod 444 after promotion, "
            f"got {oct(mode)}"
        )
