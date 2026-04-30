# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-25 — RETIRED by BUG-AUDIT-84.

BUG-AUDIT-25 introduced filesystem-derived versioning under
``output/<presentation_folder>/script_v{NNN}.md`` and an exit-2
precondition for ``main_script_generator``.

REQ-SCRIPT-WRITER-1 / BC-3.20 / BUG-AUDIT-84 Sub-cycle B retire that
contract:

- Versioned outputs are gone. The script is one canonical artifact
  at ``<project_root>/speaker_script.md``; prior versions land in
  ``.debrief/script_backups/`` instead.
- The "no approved slides" path no longer exits 2. It logs
  ``error_class: no_approved_slides`` to ``.debrief/script_errors.jsonl``
  and exits 0 — the script-writer NEVER blocks the consultant.

Successor coverage lives in
``tests/regressions/test_bug_audit_84_sub_b_script_writer.py``
(``TestMainScriptWriterOrchestrator``).

Only one invariant from BUG-AUDIT-25 survives the rewrite and is
re-asserted here: the script-writer must NOT mutate
``deck_state.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_1" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_3" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_11" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import launcher  # noqa: E402

_TS = "2026-04-16T12:00:00Z"
_VALID_SCRIPT = (
    "# Speaker Script\n\n**Target duration:** 10 minutes\n\n"
    "## Slide 1: Title of intro\n\n"
    "### Key talking points\n\nKey talking content for intro slide.\n\n"
    "### Transition\n\nMove on naturally.\n\n"
    "### Estimated speaking time\n\n~10.0 minutes\n"
)


def _slide_dict(slug: str, **kw: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "slug": slug, "title": f"Title of {slug}", "status": "approved",
        "backup": False, "content_summary": f"Summary for {slug}",
        "visual_approach": "Diagram", "design_choices": "Minimal",
        "forks_not_taken": None, "user_recommendations": None,
        "qa_passed": True, "accepted_violations": [],
        "last_modified": _TS, "group_id": "g1",
        "user_assets": [], "has_math": False,
    }
    defaults.update(kw)
    return defaults


def _plugin_root_for_tests() -> Path:
    """Locate the agent-card plugin root for the active layout."""
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1"
    return _PROJECT_ROOT


def test_deck_state_not_mutated_by_script_writer(tmp_path: Path) -> None:
    """BUG-AUDIT-25 (preserved invariant): the script-writer reads
    deck_state.json but never writes to it. Re-asserted under the
    BUG-AUDIT-84 contract via main_script_writer (mocked API)."""
    state = {
        "project_name": "test",
        "created_at": _TS,
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": [_slide_dict("intro")],
        "presentations": [],
    }
    state_path = tmp_path / "deck_state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    before = state_path.read_bytes()

    with patch.object(
        launcher, "call_script_writer_agent", return_value=_VALID_SCRIPT
    ):
        with pytest.raises(SystemExit) as ei:
            launcher.main_script_writer(
                tmp_path,
                trigger="/debrief:script",
                plugin_root=_plugin_root_for_tests(),
            )

    assert ei.value.code == 0
    after = state_path.read_bytes()
    assert before == after
