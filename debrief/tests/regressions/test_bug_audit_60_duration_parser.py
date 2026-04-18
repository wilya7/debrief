# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-60 Cluster 3 (script duration parser).

BUG-ST-a-4 (HIGH): `_parse_duration_from_brief` returned 45 for a brief
that unambiguously declared a 5-minute talk. Two regex defects:

1. Primary `(?:duration|time|length)\\s*[:=]\\s*(\\d+)\\s*(?:min|minute)`
   failed on `**Duration:** 5 minutes` — `**` after the colon is not
   whitespace or colon.

2. Fallback `(\\d+)\\s*[-\\s]?\\s*(?:minute|min)\\b` used `\\b` after
   `minute`. `\\b` does not match between `e` and `s` (both word chars),
   so "5 minutes" (plural) silently failed. The fallback then picked up
   "45 min" from the duration-warning sentence elsewhere in the brief.

Fix: primary allows `[\\s:*=\\-]{0,8}?` between keyword and digit; both
patterns accept `s?` before `\\b`.

Coverage:

1. `**Duration:** 5 minutes` → 5.0 (smoke-test repro).
2. `Duration: 5 minutes` (plain) → 5.0.
3. Brief containing BOTH `**Duration:** 5 minutes` AND a warning line with
   "10-45 min" → 5.0 (primary wins; fallback never reached).
4. Existing forms (unchanged contract): `Duration: 15 minutes`, inline
   "20-minute talk", absent → None.
5. Singular still works: "5 minute talk", "30 min".
6. False-match guard: "duration was discussed, 10 minutes later" does
   not match the keyword→digit gap (gap exceeds 8 chars of allowed
   punctuation), so the primary does not fire on it.
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


# utility_skills imports from sibling units; mirror the pattern used by
# test_bug_audit_59_smoke_round2 so both workspace and delivered layouts work.
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
# 1. Primary regex accepts markdown-bold headers
# ---------------------------------------------------------------------------


def test_markdown_bold_duration_parses_correctly():
    """BUG-ST-a-4: the exact smoke-test brief form."""
    brief = "# Deck Brief\n\n**Duration:** 5 minutes\n\n**Audience:** tech"
    assert utility_skills._parse_duration_from_brief(brief) == 5.0


def test_markdown_bold_with_italic_emphasis():
    """Extended markdown: bold+italic and other punctuation around the label."""
    brief = "***Duration:*** 10 minutes"
    assert utility_skills._parse_duration_from_brief(brief) == 10.0


def test_plain_duration_label_still_works():
    """Pre-existing contract: plain `Duration: N minutes` continues to parse."""
    brief = "Duration: 15 minutes"
    assert utility_skills._parse_duration_from_brief(brief) == 15.0


def test_equals_separator_still_works():
    """Pre-existing contract: `duration=N min`."""
    brief = "duration=20 min"
    assert utility_skills._parse_duration_from_brief(brief) == 20.0


# ---------------------------------------------------------------------------
# 2. The exact smoke-test collision: user says 5 min, warning mentions 45 min
# ---------------------------------------------------------------------------


_SMOKE_REPRO_BRIEF = """# Deck Brief

**Archetype:** conference_talk
**Duration:** 5 minutes
**Audience:** tech conference attendees

## Duration warning

WARNING: 5 min is below conference_talk range (10-45 min). Consider
adjusting. The user accepted the compressed format.

## Content

AI is not an innovation — it's a revolution.
"""


def test_smoke_test_brief_returns_user_duration_not_warning_bound():
    """BUG-ST-a-4 exact repro: a brief that declares 5 minutes AND contains
    the duration-warning text "10-45 min" must return 5, not 45.
    The fix here is that the PRIMARY regex now matches `**Duration:** 5
    minutes` (it used to fail); the fallback — which would pick up 45
    from "10-45 min" — must therefore never fire.
    """
    result = utility_skills._parse_duration_from_brief(_SMOKE_REPRO_BRIEF)
    assert result == 5.0, (
        f"Expected 5.0 (user's stated duration), got {result!r}. "
        "BUG-ST-a-4 regression: primary regex must match markdown-bold "
        "duration headers before the fallback sees unrelated `N min` text."
    )


# ---------------------------------------------------------------------------
# 3. Plural vs. singular handling (both must work)
# ---------------------------------------------------------------------------


def test_plural_minutes_label_free():
    """BUG-ST-a-4 secondary defect: fallback `\\b` failed on "5 minutes"."""
    brief = "This is a 5 minutes talk."
    assert utility_skills._parse_duration_from_brief(brief) == 5.0


def test_singular_minute_label_free():
    brief = "This is a 5-minute talk."
    assert utility_skills._parse_duration_from_brief(brief) == 5.0


def test_singular_min_abbreviation():
    brief = "30 min lecture."
    assert utility_skills._parse_duration_from_brief(brief) == 30.0


def test_plural_mins_abbreviation():
    brief = "30 mins lecture."
    assert utility_skills._parse_duration_from_brief(brief) == 30.0


# ---------------------------------------------------------------------------
# 4. Contract preserved: absent → None
# ---------------------------------------------------------------------------


def test_returns_none_when_no_duration_text():
    brief = "This is a talk about AI. No timing info anywhere."
    assert utility_skills._parse_duration_from_brief(brief) is None


def test_returns_none_for_empty_brief():
    assert utility_skills._parse_duration_from_brief("") is None


# ---------------------------------------------------------------------------
# 5. Gap cap prevents cross-sentence false matches
# ---------------------------------------------------------------------------


def test_keyword_far_from_digit_does_not_match_primary():
    """The primary regex gap is capped at 8 chars of markdown punctuation;
    long stretches of arbitrary text between the keyword and the digit
    must not fire. Falls through to fallback, which picks up the first
    N-minute-like pattern it finds."""
    brief = "duration was discussed at length, 10 minutes later..."
    # Primary regex should NOT match "duration" with 25+ chars to the first
    # digit. But fallback sees "10 minutes" and returns 10.0 — that's the
    # documented looser behavior for the no-explicit-label case.
    result = utility_skills._parse_duration_from_brief(brief)
    assert result == 10.0, (
        f"Fallback should still find '10 minutes' after primary fails "
        f"on the noise-gap, got {result!r}"
    )


def test_primary_wins_when_both_patterns_present():
    """Primary label-matching fires first; ordering preserved."""
    brief = "Duration: 7 minutes. Note: will also mention 20 min pacing."
    assert utility_skills._parse_duration_from_brief(brief) == 7.0
