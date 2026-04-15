# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-19.

A user running debrief approved the style proposal at gate G2.1 by
saying "STYLE APPROVED". The Consultant agent logged the gate response
but observed that the drafts had NOT been promoted: `style_locked` was
still False, `style_config.json` and `style_guide.md` were still in
`.debrief/draft/`, and `assets/style.css` was never compiled. The user
was stuck — `check-write-auth` blocks slide writes until style is
locked, and the lock never happened.

ROOT CAUSE. `main_update_state()` in `src/unit_4/routing.py` had no
dispatch branch for `gate_id == "G2.1_style_config_review"`. It handled
G1.3 (figure selection) and G3.2 (red-green) explicitly, then fell
through to a generic handler that only wrote `last_gate_response` to
`debrief_state.json` and returned. `promote_style_draft()` — the
function that executes the 7-step compile-and-lock sequence per spec
§24.8 — was defined at line 632 and thoroughly unit-tested in
isolation (`TestPromoteStyleDraft` class, 6 tests) but was **never
called from any production code path**. The unit tests hid the orphan
by exercising the helper directly; no integration test walked
`main_update_state → promote_style_draft`.

THE FIX adds a G2.1 dispatch branch in `main_update_state` that:
  - On `STYLE APPROVED`: calls `promote_style_draft(project_root)`.
  - On `STYLE REVISE <feedback>`: parses the feedback, writes
    `.debrief/gate_data.json`, discards the draft directory, then falls
    through to the generic `last_gate_response` writer.

This file pins every part of the fix through integration tests that
invoke `main_update_state` directly and assert the post-conditions —
the class of test that was missing pre-BUG-AUDIT-19. Zero skips per
the CLAUDE.md break-glass protocol; tests run in both workspace and
delivered layouts via the sibling-discovery path pattern established
in BUG-AUDIT-16/17.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-19.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Path helpers — resolve both layouts from either side; no skipping.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_4").is_dir()


def _routing_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_4"
    return _PROJECT_ROOT / "src" / "debrief"


def _debrief_state_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_2"
    return _PROJECT_ROOT / "src" / "debrief"


# Prep sys.path so `import routing` and `import debrief_state` work from
# either layout, same pattern as BUG-AUDIT-18 test file.
for _dir in (_debrief_state_module_dir(), _routing_module_dir()):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import routing  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic project fixture helpers.
# ---------------------------------------------------------------------------


_MINIMAL_VALID_STYLE_CONFIG = {
    "colors": {
        "primary": "#000000",
        "secondary": "#111111",
        "accent": "#ff0000",
        "background": "#ffffff",
        "text_primary": "#222222",
        "text_secondary": "#666666",
        "code_background": "#eeeeee",
        "border": "#cccccc",
    },
    "typography": {
        "heading_font_family": "Arial",
        "body_font_family": "Georgia",
        "code_font_family": "Courier",
        "heading_size_base": "48px",
        "body_size_base": "16px",
        "heading_weight": "700",
        "body_weight": "400",
        "line_height": "1.6",
    },
    "spacing": {"margin_pct": "5%", "gap": "16px", "section_gap": "48px"},
    "layout": {
        "slide_width": "1920px",
        "slide_height": "1080px",
        "column_gap": "24px",
    },
    "data_viz": {
        "primary_colormap": "viridis",
        "axis_color": "#333333",
        "grid_color": "#eeeeee",
        "annotation_color": "#ff0000",
    },
    "constraints": {"permitted_diagram_types": ["mermaid", "inline-svg"]},
    "provenance": {},
}


_MINIMAL_DEBRIEF_STATE = {
    "phase": "style",
    "sub_phase": "style/style_review",
    "active_agent": "consultant",
    "archetype": "lab_meeting",
    "current_group_id": None,
    "current_slide_slug": None,
    "pending_gate": "G2.1_style_config_review",
    "last_gate_response": None,
    "red_green_iteration": 0,
    "red_green_started_at": None,
    "group_slide_index": 0,
    "group_slide_count": 0,
    "backup_mode": False,
    "completed_groups": [],
    "pre_view_state": None,
    "view_deferred": False,
    "reference_provided": False,
    "papers_provided": False,
    "closing_slide_pending": False,
    "state_hash": "x" * 64,
    "session_started_at": "2026-04-15T10:00:00Z",
}


_MINIMAL_DECK_STATE = {
    "project_name": "bug_audit_19_test",
    "created_at": "2026-04-15T10:00:00Z",
    "archetype": "lab_meeting",
    "style_locked": False,
    "closing_slide": None,
    "slides": [],
    "presentations": [],
}


def _setup_project(tmp_path: Path) -> Path:
    """Build a minimal project with draft style files ready for G2.1."""
    project = tmp_path / "project"
    draft_dir = project / ".debrief" / "draft"
    draft_dir.mkdir(parents=True)
    (draft_dir / "style_config.json").write_text(
        json.dumps(_MINIMAL_VALID_STYLE_CONFIG, indent=2),
        encoding="utf-8",
    )
    (draft_dir / "style_guide.md").write_text(
        "# Style Guide\n\nTest content.\n", encoding="utf-8"
    )
    (project / "deck_state.json").write_text(
        json.dumps(_MINIMAL_DECK_STATE), encoding="utf-8"
    )
    (project / "debrief_state.json").write_text(
        json.dumps(_MINIMAL_DEBRIEF_STATE), encoding="utf-8"
    )
    (project / "assets").mkdir()
    return project


# ---------------------------------------------------------------------------
# BC-4.6 / BUG-AUDIT-19 — G2.1 dispatch branch in main_update_state.
# ---------------------------------------------------------------------------


class TestBugAudit19G21StylePromotion:
    """BC-4.6 / BUG-AUDIT-19 — main_update_state must dispatch G2.1
    STYLE APPROVED to promote_style_draft (was previously orphaned).
    """

    def test_main_update_state_g21_approved_promotes_draft_files(
        self, tmp_path: Path
    ) -> None:
        project = _setup_project(tmp_path)
        with patch.object(routing.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            routing.main_update_state(
                gate_id="G2.1_style_config_review",
                response="STYLE APPROVED",
                project_root=project,
            )

        # Files promoted from .debrief/draft/ to project root.
        assert (project / "style_config.json").is_file(), (
            "BC-4.6 / BUG-AUDIT-19: style_config.json must be promoted "
            "to the project root on G2.1 STYLE APPROVED."
        )
        assert (project / "style_guide.md").is_file(), (
            "BC-4.6 / BUG-AUDIT-19: style_guide.md must be promoted to "
            "the project root on G2.1 STYLE APPROVED."
        )
        # Draft directory removed.
        assert not (project / ".debrief" / "draft").exists(), (
            "BC-4.6 / BUG-AUDIT-19: .debrief/draft/ must be rmtree'd "
            "on G2.1 STYLE APPROVED."
        )
        # style_locked flipped to True.
        deck = json.loads((project / "deck_state.json").read_text())
        assert deck["style_locked"] is True, (
            "BC-4.6 / BUG-AUDIT-19: deck_state.style_locked must be "
            "True after promotion."
        )
        # last_gate_response persisted in debrief_state.
        dbf = json.loads((project / "debrief_state.json").read_text())
        assert dbf["last_gate_response"] == "STYLE APPROVED", (
            "BC-4.6 / BUG-AUDIT-19: debrief_state.last_gate_response "
            "must reflect the STYLE APPROVED response."
        )

    def test_main_update_state_g21_approved_invokes_style_compiler(
        self, tmp_path: Path
    ) -> None:
        project = _setup_project(tmp_path)
        with patch.object(routing.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            routing.main_update_state(
                gate_id="G2.1_style_config_review",
                response="STYLE APPROVED",
                project_root=project,
            )

        assert mock_run.call_count == 1, (
            f"BC-4.6 / BUG-AUDIT-19: style_compiler subprocess must be "
            f"called exactly once; got {mock_run.call_count}."
        )
        # Inspect the call: args[0] is the command list.
        call_args = mock_run.call_args[0][0]
        # Must be a python -m debrief.style_compiler invocation.
        assert "debrief.style_compiler" in call_args, (
            f"BC-4.6 / BUG-AUDIT-19: style_compiler subprocess must be "
            f"invoked via `python -m debrief.style_compiler`; got: "
            f"{call_args}"
        )

    def test_main_update_state_g21_approved_sets_file_perms_444(
        self, tmp_path: Path
    ) -> None:
        project = _setup_project(tmp_path)
        with patch.object(routing.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            routing.main_update_state(
                gate_id="G2.1_style_config_review",
                response="STYLE APPROVED",
                project_root=project,
            )

        for name in ("style_config.json", "style_guide.md"):
            mode = (project / name).stat().st_mode & 0o777
            assert mode == 0o444, (
                f"BC-4.6 / BUG-AUDIT-19: {name} must be chmod 444 after "
                f"promotion; got {oct(mode)}."
            )

    def test_main_update_state_g21_approved_compiler_failure_no_rollback(
        self, tmp_path: Path
    ) -> None:
        # Per BC-4.6: on compiler failure, do NOT rollback the promotion.
        # Files stay at project root; style_locked remains false; draft
        # dir stays (the existing implementation only calls rmtree on
        # success, per the function code).
        project = _setup_project(tmp_path)
        with patch.object(routing.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stderr="compiler exploded"
            )
            with pytest.raises(RuntimeError, match="style_compiler failed"):
                routing.main_update_state(
                    gate_id="G2.1_style_config_review",
                    response="STYLE APPROVED",
                    project_root=project,
                )

        # Files WERE promoted (step 2 and 3 ran before step 4).
        assert (project / "style_config.json").is_file(), (
            "BC-4.6: files must be promoted before compiler runs; on "
            "compiler failure, no rollback happens."
        )
        assert (project / "style_guide.md").is_file()
        # style_locked still false (step 6 never ran).
        deck = json.loads((project / "deck_state.json").read_text())
        assert deck["style_locked"] is False, (
            "BC-4.6: style_locked must remain False on compiler failure."
        )

    def test_main_update_state_g21_revise_writes_gate_data_and_discards_draft(
        self, tmp_path: Path
    ) -> None:
        # Per the _GATE_VALID_RESPONSES grammar "STYLE REVISE <instructions>",
        # the feedback follows the keyword with a space separator (no colon).
        project = _setup_project(tmp_path)
        routing.main_update_state(
            gate_id="G2.1_style_config_review",
            response="STYLE REVISE the colors are too dark",
            project_root=project,
        )

        # gate_data.json written with the feedback.
        gate_data_path = project / ".debrief" / "gate_data.json"
        assert gate_data_path.is_file(), (
            "BC-4.6 / BUG-AUDIT-19: STYLE REVISE must write "
            ".debrief/gate_data.json."
        )
        payload = json.loads(gate_data_path.read_text())
        assert payload["gate_id"] == "G2.1_style_config_review"
        assert payload["data"]["style_revise_feedback"] == (
            "the colors are too dark"
        ), f"Got: {payload['data']['style_revise_feedback']!r}"

        # Draft directory discarded.
        assert not (project / ".debrief" / "draft").exists(), (
            "BC-4.6 / BUG-AUDIT-19: STYLE REVISE must rmtree "
            ".debrief/draft/ per spec §24.21."
        )
        # Style NOT locked (user rejected the proposal).
        deck = json.loads((project / "deck_state.json").read_text())
        assert deck["style_locked"] is False

    def test_main_update_state_g21_revise_empty_feedback_exits_code_4(
        self, tmp_path: Path
    ) -> None:
        # Per the grammar contract "STYLE REVISE <instructions>", the
        # validator requires a non-empty payload after the keyword +
        # space. "STYLE REVISE " (trailing space, empty payload) is
        # rejected by validate_gate_response with exit code 4.
        project = _setup_project(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            routing.main_update_state(
                gate_id="G2.1_style_config_review",
                response="STYLE REVISE ",
                project_root=project,
            )
        assert exc_info.value.code == 4, (
            "BC-4.6 / BUG-AUDIT-19: STYLE REVISE with empty feedback "
            "must exit code 4."
        )

    def test_main_update_state_g21_unknown_response_exits_code_4(
        self, tmp_path: Path
    ) -> None:
        # A malformed response must be rejected by the existing gate
        # validator, which exits code 4 before the new G2.1 branch runs.
        project = _setup_project(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            routing.main_update_state(
                gate_id="G2.1_style_config_review",
                response="STYLE LOOKS GOOD",
                project_root=project,
            )
        assert exc_info.value.code == 4

    def test_promote_style_draft_is_called_from_main_update_state(
        self, tmp_path: Path
    ) -> None:
        # Integration sentinel: the bug was that promote_style_draft
        # existed in isolation but was never called from
        # main_update_state. This test pins the direct call chain so a
        # future maintainer cannot orphan the function again.
        project = _setup_project(tmp_path)
        call_record: list[Path] = []
        original = routing.promote_style_draft

        def _recording_wrapper(project_root: Path) -> None:
            call_record.append(project_root)
            original(project_root)

        with patch.object(routing.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            with patch.object(
                routing, "promote_style_draft", _recording_wrapper
            ):
                routing.main_update_state(
                    gate_id="G2.1_style_config_review",
                    response="STYLE APPROVED",
                    project_root=project,
                )

        assert len(call_record) == 1, (
            f"BC-4.6 / BUG-AUDIT-19: promote_style_draft must be called "
            f"exactly once from main_update_state on G2.1 STYLE APPROVED. "
            f"Got {len(call_record)} calls."
        )
        assert call_record[0] == project, (
            f"BC-4.6 / BUG-AUDIT-19: promote_style_draft must be called "
            f"with project_root={project}; got {call_record[0]}."
        )
