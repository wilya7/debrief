# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-62 — script transition extractor extended.

BUG-ST-a-e2 (MEDIUM): `_extract_transition` recognized a narrow list of
signal words. Consultants whose `content_summary` ended with an explicit
`Transition: <text>` marker (a natural consultant convention) OR used
phrasings outside the signal list got placeholder transitions in their
generated script.

REQ-SCRIPT-TRANSITION-1 / BC-11.6a extends the extractor:

1. Explicit marker `Transition:` (case-insensitive, optional Markdown
   bold/italic) takes precedence. Text after the marker is the
   transition; text before is the talking-points body.
2. Signal-word fallback list broadened to include common phrasings like
   `the first move`, `move into`, `into the next`, etc.
3. When neither the marker nor any signal word matches, the placeholder
   fallback is still used (no regression of existing behavior).

Coverage:

1. Explicit marker `Transition: ...` is extracted.
2. Marker with Markdown bold (`**Transition:**`) is extracted.
3. Marker with italic (`*Transition:*`) is extracted.
4. When both a marker and a signal word are present, the marker wins.
5. New signal words in the broadened list trigger extraction.
6. Pre-existing signal words (backward compat) still trigger.
7. Content with neither marker nor signal returns (content, None).
8. Short content (single sentence with no signal) returns (content, None).
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# 1-4. Explicit Transition: marker (highest precedence)
# ---------------------------------------------------------------------------


def test_explicit_marker_plain_is_extracted():
    """REQ-SCRIPT-TRANSITION-1: the `Transition:` prefix wins."""
    content = (
        "The hook opens with AI as a revolution — not innovation. "
        "This is the frame we'll build on.\n\n"
        "Transition: But what makes this a revolution? The first move: AI has solved code."
    )
    body, trans = utility_skills._extract_transition(content)
    assert trans is not None
    assert "what makes this a revolution" in trans
    assert "The first move" in trans
    assert "the frame we'll build on" in body
    assert "Transition:" not in body


def test_explicit_marker_markdown_bold_is_extracted():
    content = (
        "Body paragraph about AI solving code.\n\n"
        "**Transition:** This sets up the cognitive software argument."
    )
    body, trans = utility_skills._extract_transition(content)
    assert trans is not None
    assert "cognitive software" in trans
    assert "Body paragraph" in body
    assert "Transition" not in body


def test_explicit_marker_italic_is_extracted():
    content = (
        "Body paragraph about AI solving code.\n\n"
        "*Transition:* This sets up the cognitive software argument."
    )
    body, trans = utility_skills._extract_transition(content)
    assert trans is not None
    assert "cognitive software" in trans
    assert "Body paragraph" in body


def test_explicit_marker_wins_over_signal_word():
    """BC-11.6a: when both a marker and a signal word are present, marker wins."""
    content = (
        "Setup paragraph that mentions the word next in passing. "
        "More content here.\n\n"
        "Transition: Explicit marker line."
    )
    body, trans = utility_skills._extract_transition(content)
    assert trans == "Explicit marker line."
    # body contains the sentence with "next" — not pulled out as transition
    assert "mentions the word next" in body


# ---------------------------------------------------------------------------
# 5. Broadened signal list — new phrases trigger extraction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "signal_phrase",
    [
        "the first move",
        "move into",
        "into the next",
        "turn to",
        "bringing us to",
        "leading into",
        "next up",
        "set up",
    ],
)
def test_broadened_signal_words_trigger(signal_phrase: str):
    """REQ-SCRIPT-TRANSITION-1: new signal phrases must be recognized
    in the final sentence even without an explicit marker."""
    content = (
        "First body sentence about the topic. "
        f"We now {signal_phrase} the next stage of the argument."
    )
    body, trans = utility_skills._extract_transition(content)
    assert trans is not None, (
        f"Signal phrase {signal_phrase!r} should trigger extraction."
    )
    assert signal_phrase in trans.lower()
    assert "First body sentence" in body


# ---------------------------------------------------------------------------
# 6. Pre-existing signal words still work (backward compat)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "signal_phrase",
    [
        "which leads",
        "sets the stage",
        "which brings us",
        "this leads",
    ],
)
def test_preexisting_signals_still_work(signal_phrase: str):
    content = (
        "Body paragraph introducing the concept. "
        f"This {signal_phrase} naturally into the follow-on."
    )
    body, trans = utility_skills._extract_transition(content)
    assert trans is not None
    assert signal_phrase in trans.lower()


# ---------------------------------------------------------------------------
# 7. No marker, no signal → placeholder fallback expected
# ---------------------------------------------------------------------------


def test_no_marker_no_signal_returns_none():
    content = (
        "A simple body paragraph. With two sentences and no transition phrasing."
    )
    body, trans = utility_skills._extract_transition(content)
    assert trans is None
    assert body == content


# ---------------------------------------------------------------------------
# 8. Single-sentence content — no transition
# ---------------------------------------------------------------------------


def test_single_sentence_content_returns_none():
    content = "One short sentence with no transition."
    body, trans = utility_skills._extract_transition(content)
    assert trans is None
    assert body == content


# ---------------------------------------------------------------------------
# 9. Empty content
# ---------------------------------------------------------------------------


def test_empty_content_returns_none():
    body, trans = utility_skills._extract_transition("")
    assert trans is None
    assert body == ""


# ---------------------------------------------------------------------------
# 10. Case-insensitive marker matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("marker", ["Transition:", "TRANSITION:", "transition:"])
def test_marker_case_insensitive(marker):
    content = f"Body paragraph.\n\n{marker} the transition text."
    body, trans = utility_skills._extract_transition(content)
    assert trans is not None
    assert "transition text" in trans
