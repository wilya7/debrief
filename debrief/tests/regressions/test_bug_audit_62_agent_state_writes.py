# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-62 — subagent state-write prohibition.

BUG-ST-round5-x-1 (MEDIUM): stylist subagent wrote `debrief_state.json`
directly during style-lock promotion, bypassing `write_debrief_state` +
producing a `hash mismatch — recomputed` warning on the next CLI read.
BC-5.7 originally prohibited only the consultant; BUG-AUDIT-62 extends
the prohibition to every subagent.

REQ-AGENT-STATE-1 / BC-5.7 (extended):

Each subagent card (stylist, slide-maker, visual-qa, bug-diagnostic)
MUST contain an explicit prohibition on writing `deck_state.json` or
`debrief_state.json` via the Write tool. The prohibition MUST name a
concrete CLI alternative so authors have a clear path instead.

Coverage:

1. Each of the four subagent cards contains a "MUST NOT write"
   phrase covering both state files.
2. Each of the four cards cites the canonical CLI alternative
   (`python -m debrief.debrief_state update` or
   `python -m debrief.utility_skills promote_style_draft`).
3. `promote_style_draft` now uses `write_deck_state` — verified via
   source inspection of the function.
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


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


_SUBAGENTS = ("stylist", "slide-maker", "visual-qa", "bug-diagnostic")


def _agent_md_path(name: str) -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / f"{name}.md"
    return _PROJECT_ROOT / "agents" / f"{name}.md"


# ---------------------------------------------------------------------------
# 1. Every subagent card has a "MUST NOT write" prohibition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("agent", _SUBAGENTS)
def test_subagent_card_prohibits_state_writes(agent: str) -> None:
    """BUG-AUDIT-62 / REQ-AGENT-STATE-1 / BC-5.7:
    Each subagent card must contain an explicit MUST NOT clause covering
    both deck_state.json and debrief_state.json.
    """
    path = _agent_md_path(agent)
    md = path.read_text(encoding="utf-8").lower()
    assert "must not write" in md, (
        f"{agent}.md: expected an explicit 'MUST NOT write' prohibition "
        "for state files (BUG-AUDIT-62 / BC-5.7 extended)."
    )
    assert "deck_state.json" in md, f"{agent}.md: must name deck_state.json"
    assert "debrief_state.json" in md, (
        f"{agent}.md: must name debrief_state.json"
    )


# ---------------------------------------------------------------------------
# 2. Every subagent card cites the canonical CLI alternative
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("agent", _SUBAGENTS)
def test_subagent_card_cites_cli_alternative(agent: str) -> None:
    """The prohibition must be paired with a concrete CLI escape hatch.
    Without it, agents can't tell HOW to change state — just that they
    shouldn't Write-tool it. We accept either the debrief_state CLI or
    promote_style_draft as evidence of a named alternative.
    """
    md = _agent_md_path(agent).read_text(encoding="utf-8")
    has_state_cli = "python -m debrief.debrief_state update" in md
    has_promote = "promote_style_draft" in md
    assert has_state_cli or has_promote, (
        f"{agent}.md: must cite `python -m debrief.debrief_state update` "
        "or `promote_style_draft` as the state-mutation alternative."
    )


# ---------------------------------------------------------------------------
# 3. promote_style_draft uses write_deck_state (not raw write_text)
# ---------------------------------------------------------------------------


def test_promote_style_draft_uses_write_deck_state() -> None:
    """BUG-AUDIT-62 / BUG-ST-round5-x-1:
    promote_style_draft previously wrote deck_state.json via write_text,
    bypassing hash recomputation. It must now route through
    write_deck_state so the state_hash stays consistent with the
    debrief_state.json hash.
    """
    src = inspect.getsource(utility_skills.promote_style_draft)
    assert "write_deck_state(" in src, (
        "promote_style_draft must call write_deck_state for the "
        "style_locked mutation (BUG-AUDIT-62 / BC-5.7 extended)."
    )
    # And must NOT revert to raw write_text on deck_state.json
    assert "deck_state_path.write_text" not in src, (
        "promote_style_draft must NOT write deck_state.json via "
        "write_text; use write_deck_state to preserve hash invariants."
    )
