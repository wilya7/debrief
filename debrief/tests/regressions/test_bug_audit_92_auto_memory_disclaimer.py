# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-92: auto-memory disclaimer.

Claude Code's runtime injects a "you have auto-memory at
``~/.claude/projects/<encoded>/memory/``" system prompt at session start.
For a debrief session, that path is OUTSIDE the project root and any
attempt to use the Write tool against it is correctly blocked by the
``bin/check-write-auth`` hook (BC-1.9). The pre-fix consultant tried to
use the auto-memory anyway, hit the block, and surfaced it to the user
as "Hook blocked the memory write" - confusing because debrief has its
own (functional) project-scoped memory architecture.

BC-5.24 mandates a ``## Auto-Memory Disclaimer`` section in
``agents/consultant.md`` that:
  (a) acknowledges the auto-memory injection,
  (b) tells the consultant to ignore it for debrief sessions,
  (c) names the canonical debrief memory surfaces,
  (d) explains the hook block is by-design,
  (e) tells the consultant to re-route, not surface "memory failed".

This test pins the section's presence + key substrings.
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


def _line_start_offset(content: str, header: str) -> int:
    idx = 0
    while True:
        i = content.find(header, idx)
        if i < 0:
            return -1
        if i == 0 or content[i - 1] == "\n":
            return i
        idx = i + 1


def _section_body(content: str, header: str) -> str:
    start = _line_start_offset(content, header)
    assert start >= 0, f"section header missing at line start: {header!r}"
    after = content.find("\n## ", start + len(header))
    return content[start:after] if after >= 0 else content[start:]


# ---------------------------------------------------------------------------
# Section presence and placement
# ---------------------------------------------------------------------------


def test_auto_memory_disclaimer_section_exists() -> None:
    content = _consultant_md_path().read_text()
    assert "## Auto-Memory Disclaimer" in content


def test_disclaimer_precedes_recall_discipline() -> None:
    """BC-5.24 mandates placement before ## Recall Discipline."""
    content = _consultant_md_path().read_text()
    i_disc = _line_start_offset(content, "## Auto-Memory Disclaimer")
    i_recall = _line_start_offset(content, "## Recall Discipline")
    assert 0 <= i_disc < i_recall, (
        "## Auto-Memory Disclaimer must come before ## Recall Discipline "
        "so the carve-out is read before the existing memory sections"
    )


# ---------------------------------------------------------------------------
# Required substrings inside the section
# ---------------------------------------------------------------------------


def test_disclaimer_references_auto_memory_path() -> None:
    body = _section_body(_consultant_md_path().read_text(), "## Auto-Memory Disclaimer")
    assert "~/.claude/projects/" in body, (
        "the disclaimer must reference the auto-memory path explicitly so "
        "future models reading the prompt recognize the runtime injection"
    )


def test_disclaimer_names_canonical_debrief_memory_surfaces() -> None:
    body = _section_body(_consultant_md_path().read_text(), "## Auto-Memory Disclaimer")
    for surface in (
        ".debrief/dialog.jsonl",
        "output/timeline.jsonl",
        "deck_brief.md",
    ):
        assert surface in body, (
            f"canonical debrief memory surface missing from disclaimer: {surface!r}"
        )


def test_disclaimer_names_canonical_clis() -> None:
    body = _section_body(_consultant_md_path().read_text(), "## Auto-Memory Disclaimer")
    for cli in ("append_dialog_turn", "emit_event"):
        assert cli in body, f"CLI command missing from disclaimer: {cli!r}"


def test_disclaimer_references_hook_by_design() -> None:
    """The block must be framed as policy, not a bug."""
    body = _section_body(_consultant_md_path().read_text(), "## Auto-Memory Disclaimer")
    assert "check-write-auth" in body
    assert "BC-1.9" in body


def test_disclaimer_tells_consultant_not_to_surface_as_memory_failure() -> None:
    """If a hook block fires, the consultant must re-route, not say 'memory failed'."""
    body = _section_body(_consultant_md_path().read_text(), "## Auto-Memory Disclaimer")
    # The disclaimer must explicitly say something like "do not surface ... as memory failure"
    assert ("do not surface" in body.lower() or "must not surface" in body.lower())
    assert "memory" in body.lower()


def test_disclaimer_explicit_ignore_directive() -> None:
    """The section must contain an unambiguous 'ignore' or equivalent directive."""
    body = _section_body(_consultant_md_path().read_text(), "## Auto-Memory Disclaimer")
    body_lower = body.lower()
    assert "ignore it" in body_lower or "ignore the" in body_lower or "do not write" in body_lower
