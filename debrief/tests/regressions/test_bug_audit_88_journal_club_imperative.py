# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression test for BUG-AUDIT-88: journal-club paper-first imperative.

Spec line 1245 mandates that for the journal_club archetype, the consultant
MUST ask for paper PDFs as its first archetype-specific question — before
any sub-mode discussion. Pre-fix, ``agents/consultant.md`` Step 5 only
contained the sub-mode question ("Single paper or topic review across
multiple papers?") and the imperative ask was missing entirely. This drift
meant the consultant might never explicitly demand the paper, defeating
the journal-club workflow which is defined by the paper as primary asset.

This test pins BC-5.11's amended requirement: the consultant agent card
MUST contain the literal imperative substring from spec line 1245.
"""

from __future__ import annotations

from pathlib import Path

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_1").is_dir()


def _consultant_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    return _PROJECT_ROOT / "agents" / "consultant.md"


_IMPERATIVE = "Which paper(s) would you like to present? Give me the file path(s)."


def test_consultant_card_contains_journal_club_imperative_verbatim() -> None:
    """The literal imperative from spec line 1245 must appear in the agent card."""
    content = _consultant_md_path().read_text()
    assert _IMPERATIVE in content, (
        f"agents/consultant.md must contain the journal-club paper-first "
        f"imperative substring verbatim per BC-5.11 / BUG-AUDIT-88: "
        f"{_IMPERATIVE!r}"
    )


def test_imperative_appears_in_step_5_journal_club_entry() -> None:
    """The imperative must be inside the journal_club bullet of Step 5.

    Detects the bullet by searching for the literal '**journal_club**:' label
    and asserts the imperative appears in the same paragraph (i.e., before
    the next blank line or next archetype bullet).
    """
    content = _consultant_md_path().read_text()
    marker = "- **journal_club**:"
    idx = content.find(marker)
    assert idx >= 0, "journal_club bullet not found in consultant.md Step 5"
    # Read until the next archetype bullet (- **) or blank line gap
    tail = content[idx:]
    next_bullet = tail.find("\n- **", len(marker))
    para = tail[:next_bullet] if next_bullet >= 0 else tail
    assert _IMPERATIVE in para, (
        "the imperative must live inside the journal_club bullet, not "
        "elsewhere in the document"
    )


def test_imperative_precedes_sub_mode_question_in_journal_club_entry() -> None:
    """Per spec, the paper ask comes BEFORE the sub-mode question."""
    content = _consultant_md_path().read_text()
    marker = "- **journal_club**:"
    idx = content.find(marker)
    tail = content[idx:]
    next_bullet = tail.find("\n- **", len(marker))
    para = tail[:next_bullet] if next_bullet >= 0 else tail
    i_imperative = para.find(_IMPERATIVE)
    i_submode = para.find("Single paper or topic review")
    assert i_imperative >= 0 and i_submode >= 0
    assert i_imperative < i_submode, (
        "imperative ask must precede the sub-mode question per "
        "spec REQ-CONSULT-18 line 1245"
    )
