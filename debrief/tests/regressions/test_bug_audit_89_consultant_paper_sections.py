# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-89: paper-analyzer agent-card sections.

BC-5.22 mandates two new sections in ``agents/consultant.md`` to close the
sequencing gaps surfaced by FINDING-SEQ-2/3/4 in the 2026-05-03 audit:

  ## Paper Analyzer Invocation  — deterministic shell. Trigger + command
                                  template + sub_phase transitions + event
                                  emissions + multi-paper loop. Substring
                                  drift is a CRITICAL bug.

  ## Paper Discussion           — open Socratic engagement. Branches by
                                  paper_role (six values). Prose is NOT
                                  pinned — substantive engagement is where
                                  LLM judgment is the value.

This test asserts (a) both sections exist in order; (b) deterministic
substrings present; (c) all six paper_role values mentioned in the
Discussion section; (d) discovery/figure_selection appears in both.
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


def _section_body(content: str, header: str) -> str:
    """Return the substring between a line-start header and the next line-start ``## `` header.

    Skips inline mentions of the header text (e.g., inside backticks or
    quotes) — only matches when the header begins at column 0 of a line.
    """
    idx = 0
    start = -1
    while True:
        i = content.find(header, idx)
        if i < 0:
            break
        if i == 0 or content[i - 1] == "\n":
            start = i
            break
        idx = i + 1
    assert start >= 0, f"section header missing at line start: {header!r}"
    after = content.find("\n## ", start + len(header))
    return content[start:after] if after >= 0 else content[start:]


# ---------------------------------------------------------------------------
# Section presence + ordering
# ---------------------------------------------------------------------------


def test_paper_analyzer_invocation_section_exists() -> None:
    content = _consultant_md_path().read_text()
    assert "## Paper Analyzer Invocation" in content


def test_paper_discussion_section_exists() -> None:
    content = _consultant_md_path().read_text()
    assert "## Paper Discussion" in content


def test_invocation_precedes_discussion() -> None:
    content = _consultant_md_path().read_text()
    i_inv = _line_start_offset(content, "## Paper Analyzer Invocation")
    i_disc = _line_start_offset(content, "## Paper Discussion")
    assert 0 <= i_inv < i_disc


def _line_start_offset(content: str, header: str) -> int:
    idx = 0
    while True:
        i = content.find(header, idx)
        if i < 0:
            return -1
        if i == 0 or content[i - 1] == "\n":
            return i
        idx = i + 1


def test_invocation_section_lives_between_event_emission_and_deck_brief() -> None:
    """BC-5.22 mandates placement between Event Timeline Emission and Deck Brief Maintenance."""
    content = _consultant_md_path().read_text()
    i_event = _line_start_offset(content, "## Event Timeline Emission")
    i_inv = _line_start_offset(content, "## Paper Analyzer Invocation")
    i_brief = _line_start_offset(content, "## Deck Brief Maintenance")
    assert 0 <= i_event < i_inv < i_brief


# ---------------------------------------------------------------------------
# Deterministic substrings inside ## Paper Analyzer Invocation
# ---------------------------------------------------------------------------


def test_command_template_present() -> None:
    body = _section_body(_consultant_md_path().read_text(), "## Paper Analyzer Invocation")
    assert "python -m debrief.paper_analyzer --pdf" in body


def test_all_sub_phase_strings_present() -> None:
    body = _section_body(_consultant_md_path().read_text(), "## Paper Analyzer Invocation")
    for sp in ("discovery/dialog", "discovery/paper_analysis", "discovery/figure_selection"):
        assert sp in body, f"sub_phase value missing from invocation section: {sp!r}"


def test_both_event_names_present() -> None:
    body = _section_body(_consultant_md_path().read_text(), "## Paper Analyzer Invocation")
    for ev in ("paper_attached", "figure_selected"):
        assert ev in body, f"event name missing from invocation section: {ev!r}"


def test_multi_paper_loop_described() -> None:
    body = _section_body(_consultant_md_path().read_text(), "## Paper Analyzer Invocation")
    # Loose markers: must mention "multi-paper" and ordered processing language
    assert "Multi-paper" in body or "multi-paper" in body
    # Some ordering language (per-path, in order received, etc.)
    assert any(
        marker in body
        for marker in ("in the order they appear", "in the order received", "per path", "per-path")
    )


def test_path_shape_trigger_described() -> None:
    body = _section_body(_consultant_md_path().read_text(), "## Paper Analyzer Invocation")
    assert ".pdf" in body
    # Some "exists" / file-presence language
    assert any(marker in body for marker in ("file at that path exists", "the file exists"))


# ---------------------------------------------------------------------------
# Open-discussion section: header exists; six paper_role values mentioned;
# prose NOT pinned
# ---------------------------------------------------------------------------


def test_all_six_paper_roles_mentioned_in_discussion() -> None:
    body = _section_body(_consultant_md_path().read_text(), "## Paper Discussion")
    for role in (
        "primary_dissection",
        "primary_thematic",
        "primary_document",
        "concept_source",
        "background_reference",
        "none",
    ):
        assert role in body, f"paper_role value missing from discussion section: {role!r}"


def test_single_figure_case_called_out_in_discussion() -> None:
    """User's tomorrow lab-meeting case (only Figure 2) must be a documented valid path."""
    body = _section_body(_consultant_md_path().read_text(), "## Paper Discussion")
    # Look for some indication a single-figure reply is OK
    assert "Figure 2" in body or "single specific figure" in body or "figure number" in body


# ---------------------------------------------------------------------------
# Cross-section: discovery/figure_selection mentioned in both
# ---------------------------------------------------------------------------


def test_figure_selection_transition_present_in_both_sections() -> None:
    content = _consultant_md_path().read_text()
    inv_body = _section_body(content, "## Paper Analyzer Invocation")
    disc_body = _section_body(content, "## Paper Discussion")
    assert "discovery/figure_selection" in inv_body
    assert "discovery/figure_selection" in disc_body
