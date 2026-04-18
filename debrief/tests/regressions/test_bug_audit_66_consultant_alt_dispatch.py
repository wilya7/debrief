# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-66 — consultant alternative-dispatch prompts.

BUG-AUDIT-62 + -64 added `--include-backup` to /debrief:export and
/debrief:handout. BUG-AUDIT-64 documented /debrief:handout's `--mode
2up|4up` as a first-class axis. But both flags live only on the CLI —
the consultant, which is the user's primary interface, never surfaced
the choice. Typing `/debrief:handout` with no flags silently produced
the default (2up, main-only) without asking.

BUG-AUDIT-66 / REQ-CONSULT-ALT-DISPATCH-1..3 / BC-5.15: consultant.md
now contains a dedicated "## Alternative Dispatch Prompts" section
documenting:
- the deterministic decision rule (which command, which flags present,
  how many approved backups, which prompt case),
- the exact canonical prompt text for each case (drift-tested),
- the dispatch mapping from natural-language replies to CLI flags,
- the explicit exclusion of /debrief:present and /debrief:script from
  the prompting behavior (they carry the full deck unconditionally per
  BUG-AUDIT-65).

Coverage:

1. The "## Alternative Dispatch Prompts" section exists.
2. The EXPORT prompt canonical text is present verbatim.
3. The HANDOUT COMBINED prompt canonical text is present verbatim.
4. The HANDOUT MODE-ONLY prompt text is present.
5. The HANDOUT BACKUP-ONLY prompt text is present.
6. The decision rule enumerates the four handout branches.
7. The flag-bypass rule is documented (REQ-CONSULT-ALT-DISPATCH-2).
8. The zero-backup quiet-dispatch rule is documented
   (REQ-CONSULT-ALT-DISPATCH-3).
9. /debrief:present and /debrief:script are explicitly excluded.
10. The dispatch-mapping table covers the canonical reply shapes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_1").is_dir()


def _consultant_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    return _PROJECT_ROOT / "agents" / "consultant.md"


@pytest.fixture(scope="module")
def consultant_md_text() -> str:
    return _consultant_md_path().read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Section exists
# ---------------------------------------------------------------------------


def test_alternative_dispatch_section_exists(consultant_md_text):
    """BC-5.15 / REQ-CONSULT-ALT-DISPATCH-1: consultant.md MUST contain
    a section titled exactly '## Alternative Dispatch Prompts'."""
    assert "## Alternative Dispatch Prompts" in consultant_md_text


def test_section_references_bug_audit_and_requirement(consultant_md_text):
    """Traceability: section names BUG-AUDIT-66, REQ-CONSULT-ALT-DISPATCH-1,
    and BC-5.15 so future readers can trace the contract."""
    assert "BUG-AUDIT-66" in consultant_md_text
    assert "REQ-CONSULT-ALT-DISPATCH" in consultant_md_text
    assert "BC-5.15" in consultant_md_text


# ---------------------------------------------------------------------------
# 2-5. Canonical prompt text (drift guard)
# ---------------------------------------------------------------------------


def test_export_prompt_canonical_text_present(consultant_md_text):
    """REQ-CONSULT-ALT-DISPATCH-1: the export prompt must appear verbatim
    (no improvised wording). Drift from this text is a CRITICAL regression
    because the consultant reproduces it at runtime to the user."""
    # Key substrings the consultant must emit verbatim
    assert "Ready to export. You have {N} approved backup slide(s)." in consultant_md_text
    assert "Include them in the PDF? Reply:" in consultant_md_text
    assert "`main only`" in consultant_md_text
    assert "`include backup`" in consultant_md_text


def test_handout_combined_prompt_canonical_text_present(consultant_md_text):
    """HANDOUT COMBINED: both dimensions missing + backups exist."""
    assert "Ready to generate the handout. Two choices:" in consultant_md_text
    assert "Slides per page" in consultant_md_text
    assert "`2up`" in consultant_md_text
    assert "`4up`" in consultant_md_text
    assert "Include backup slides?" in consultant_md_text
    assert "Reply with your choices" in consultant_md_text


def test_handout_mode_only_prompt_text_present(consultant_md_text):
    """MODE-ONLY: the handout prompt when no backups exist (or
    --include-backup already supplied)."""
    # Distinguishing feature: "Ready to generate the handout." followed
    # shortly by a mode-only question with no backup mention.
    mode_only_section = re.search(
        r"### HANDOUT — MODE-ONLY.*?(?=### |\Z)",
        consultant_md_text,
        re.DOTALL,
    )
    assert mode_only_section is not None, (
        "MODE-ONLY prompt section header missing"
    )
    body = mode_only_section.group(0)
    assert "Slides per page" in body
    assert "`2up`" in body and "`4up`" in body


def test_handout_backup_only_prompt_text_present(consultant_md_text):
    """BACKUP-ONLY: user already supplied --mode, backups exist."""
    backup_only_section = re.search(
        r"### HANDOUT — BACKUP-ONLY.*?(?=### |\Z)",
        consultant_md_text,
        re.DOTALL,
    )
    assert backup_only_section is not None, (
        "BACKUP-ONLY prompt section header missing"
    )
    body = backup_only_section.group(0)
    assert "approved backup slide(s)" in body
    assert "`main only`" in body
    assert "`include backup`" in body


# ---------------------------------------------------------------------------
# 6. Decision rule enumerates handout branches
# ---------------------------------------------------------------------------


def test_decision_rule_covers_handout_branches(consultant_md_text):
    """REQ-CONSULT-ALT-DISPATCH-1: the decision rule section must
    enumerate the four handout branches so the consultant follows a
    deterministic tree, not vibes."""
    # Extract the "### Decision rule" block
    dec = re.search(
        r"### Decision rule.*?(?=###|\Z)",
        consultant_md_text,
        re.DOTALL,
    )
    assert dec is not None, "Decision rule subsection missing"
    body = dec.group(0)
    # Four handout branches
    assert "Both" in body and "missing" in body, (
        "Decision rule must name the 'both missing' branches"
    )
    assert "MODE-ONLY" in body or "MODE\\-ONLY" in body
    assert "BACKUP-ONLY" in body or "BACKUP\\-ONLY" in body
    assert "COMBINED" in body
    # Export branch
    assert "/debrief:export" in body


# ---------------------------------------------------------------------------
# 7. Flag-bypass rule documented
# ---------------------------------------------------------------------------


def test_flag_bypass_rule_documented(consultant_md_text):
    """REQ-CONSULT-ALT-DISPATCH-2: when flags are supplied in the user's
    turn, the consultant MUST NOT re-ask."""
    # Match on the substantive phrasing
    assert (
        "do not re-ask" in consultant_md_text.lower()
        or "do not re\\-ask" in consultant_md_text.lower()
        or "dispatch silently with defaults" in consultant_md_text.lower()
        or "that dimension is decided" in consultant_md_text.lower()
    ), (
        "consultant.md must document the flag-bypass rule "
        "(REQ-CONSULT-ALT-DISPATCH-2)."
    )


# ---------------------------------------------------------------------------
# 8. Zero-backup quiet dispatch documented
# ---------------------------------------------------------------------------


def test_zero_backup_quiet_dispatch_documented(consultant_md_text):
    """REQ-CONSULT-ALT-DISPATCH-3: zero approved backups → do not ask
    about --include-backup."""
    # Match on phrasing about counting approved backups AND quiet dispatch
    text_lower = consultant_md_text.lower()
    assert "approved_backup" in text_lower or "approved backup" in text_lower
    # And somewhere it explains quiet dispatch when count is zero
    assert (
        "approved_backup == 0" in consultant_md_text
        or "zero approved backups" in text_lower
        or "no backups" in text_lower
        or "approved_backup > 0" in consultant_md_text
    ), (
        "consultant.md must document that zero approved backups = no ask "
        "(REQ-CONSULT-ALT-DISPATCH-3)."
    )


# ---------------------------------------------------------------------------
# 9. /debrief:present and /debrief:script explicitly excluded
# ---------------------------------------------------------------------------


def test_present_and_script_explicitly_excluded(consultant_md_text):
    """BUG-AUDIT-65 + BUG-AUDIT-66: present and script MUST NEVER emit
    these prompts. The exclusion must be explicit in the agent card."""
    # Look inside the Alternative Dispatch Prompts section
    section = re.search(
        r"## Alternative Dispatch Prompts.*?(?=\n## |\Z)",
        consultant_md_text,
        re.DOTALL,
    )
    assert section is not None
    body = section.group(0)
    assert "/debrief:present" in body, (
        "Alternative Dispatch Prompts must explicitly mention present"
    )
    assert "/debrief:script" in body, (
        "Alternative Dispatch Prompts must explicitly mention script"
    )
    # And the exclusion language
    text_lower = body.lower()
    assert (
        "never emit" in text_lower
        or "must not emit" in text_lower
        or "never ask" in text_lower
    ), (
        "Exclusion must be explicit — present/script NEVER prompt"
    )


# ---------------------------------------------------------------------------
# 10. Dispatch-mapping table covers canonical reply shapes
# ---------------------------------------------------------------------------


def test_dispatch_mapping_covers_reply_shapes(consultant_md_text):
    """The mapping table must cover the natural-language replies a user
    is likely to send in response to the prompts."""
    # Find the Dispatch Mapping section
    mapping = re.search(
        r"### Dispatch Mapping.*?(?=\n### |\n## |\Z)",
        consultant_md_text,
        re.DOTALL,
    )
    assert mapping is not None
    body = mapping.group(0)
    # Each canonical reply shape should appear
    required_replies = [
        "main only", "include backup",
        "2up", "4up",
        "2up, include backup",
    ]
    for reply in required_replies:
        assert reply in body, f"Mapping missing canonical reply: {reply!r}"
    # CLI flag strings
    assert "--include-backup" in body
    assert "--mode 2up" in body
    assert "--mode 4up" in body


# ---------------------------------------------------------------------------
# Bonus: the old Export Transition section still exists (no accidental delete)
# ---------------------------------------------------------------------------


def test_export_transition_section_still_present(consultant_md_text):
    """Regression guard: BUG-AUDIT-66 adds a new section but must not
    displace the existing 'Export Transition' block."""
    assert "## Export Transition" in consultant_md_text
