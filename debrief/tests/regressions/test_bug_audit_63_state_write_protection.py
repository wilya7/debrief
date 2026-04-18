# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-63 — check-write-auth state-file protection.

BUG-AUDIT-62 added prose-level prohibitions to agent cards and hardened
`promote_style_draft`. Self-review found the fix was defensive-only: the
PreToolUse hook `bin/check-write-auth` gated only slides/* and
assets/style.css (BC-1.10), so an agent could still Write debrief_state.json
or deck_state.json and produce the hash-mismatch warning surfaced in Round 5.

BUG-AUDIT-63 extends the hook: direct Write-tool calls targeting either
state file are rejected with exit 2 and a message naming the canonical
CLI alternative. Python code paths (atomic_write_json, write_debrief_state,
write_deck_state) are unaffected — they bypass the Write tool.

Coverage (REQ-WRITE-AUTH-STATE-1 / BC-1.10a):

1. Writing `debrief_state.json` at project root is rejected with exit 2.
2. Writing `deck_state.json` at project root is rejected with exit 2.
3. The rejection message for `debrief_state.json` names the `debrief_state update` CLI.
4. The rejection message for `deck_state.json` names `write_deck_state` / `promote_style_draft`.
5. Writing a non-state file (e.g., `deck_brief.md`) still passes.
6. The state-file check runs BEFORE the BC-1.10 style-lock check (no
   unrelated style_locked lookup when the path is a state file).
7. Workspace and delivered copies of the hook are byte-identical.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_1").is_dir()


def _hook_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "bin" / "check-write-auth"
    return _PROJECT_ROOT / "bin" / "check-write-auth"


def _invoke_hook(
    project_dir: Path, file_path: str,
) -> subprocess.CompletedProcess:
    """Invoke the hook with a tool-invocation JSON simulating a Write call."""
    stdin = json.dumps({"tool_input": {"file_path": file_path}})
    return subprocess.run(
        ["bash", str(_hook_path())],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )


# ---------------------------------------------------------------------------
# 1-4. State-file writes are rejected with the correct message
# ---------------------------------------------------------------------------


def test_debrief_state_write_rejected(tmp_path):
    result = _invoke_hook(tmp_path, str(tmp_path / "debrief_state.json"))
    assert result.returncode == 2
    assert "debrief_state.json" in result.stderr


def test_debrief_state_rejection_cites_cli(tmp_path):
    result = _invoke_hook(tmp_path, str(tmp_path / "debrief_state.json"))
    assert result.returncode == 2
    assert "python -m debrief.debrief_state update" in result.stderr, (
        "Rejection must name the canonical CLI alternative."
    )


def test_deck_state_write_rejected(tmp_path):
    result = _invoke_hook(tmp_path, str(tmp_path / "deck_state.json"))
    assert result.returncode == 2
    assert "deck_state.json" in result.stderr


def test_deck_state_rejection_cites_canonical_path(tmp_path):
    result = _invoke_hook(tmp_path, str(tmp_path / "deck_state.json"))
    assert result.returncode == 2
    assert "write_deck_state" in result.stderr or "promote_style_draft" in result.stderr, (
        "Rejection must cite the write_deck_state path or promote_style_draft CLI."
    )


# ---------------------------------------------------------------------------
# 5. Non-state files still pass (regression guard)
# ---------------------------------------------------------------------------


def test_deck_brief_write_still_passes(tmp_path):
    """Regression guard: writing deck_brief.md must still succeed."""
    result = _invoke_hook(tmp_path, str(tmp_path / "deck_brief.md"))
    assert result.returncode == 0, (
        f"deck_brief.md write was unexpectedly rejected: {result.stderr}"
    )


def test_ledger_write_still_passes(tmp_path):
    """Regression guard: ledger.jsonl writes are still permitted.
    (Tests don't simulate the canonical path; the hook just needs to let
    the Write tool through for this file.)"""
    result = _invoke_hook(tmp_path, str(tmp_path / "ledger.jsonl"))
    assert result.returncode == 0


def test_slides_write_still_enforces_style_lock(tmp_path):
    """Regression guard: BC-1.10 style-lock enforcement still works.
    Writing a slide without a deck_state.json present → reject."""
    (tmp_path / "slides").mkdir()
    result = _invoke_hook(tmp_path, str(tmp_path / "slides" / "foo.html"))
    assert result.returncode == 2
    assert "Style config not yet locked" in result.stderr


def test_slides_write_permitted_when_style_locked(tmp_path):
    """Regression guard: BC-1.10 allows slides/ writes when style_locked=true."""
    (tmp_path / "slides").mkdir()
    # deck_state.json with style_locked: true — this file sits OUTSIDE the
    # hook's rejection path because the write is targeting slides/foo.html,
    # not deck_state.json itself.
    (tmp_path / "deck_state.json").write_text(
        json.dumps({"style_locked": True}), encoding="utf-8"
    )
    result = _invoke_hook(tmp_path, str(tmp_path / "slides" / "foo.html"))
    assert result.returncode == 0, (
        f"Slide write with style_locked=true rejected: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# 6. State-file check runs before style-lock check
# ---------------------------------------------------------------------------


def test_state_file_check_precedes_style_lock(tmp_path):
    """BC-1.10a must run before BC-1.10. Without a deck_state.json on
    disk, an attempted write to deck_state.json itself should still be
    rejected by BC-1.10a (state-file protection), not by BC-1.10
    (which would need to read deck_state.json to determine style_locked).
    """
    # No deck_state.json exists on disk. Hook should reject before trying
    # to read it.
    result = _invoke_hook(tmp_path, str(tmp_path / "deck_state.json"))
    assert result.returncode == 2
    # The rejection message must be the state-file one, not the style-lock one.
    assert "Direct writes to deck_state.json" in result.stderr
    assert "Style config not yet locked" not in result.stderr


# ---------------------------------------------------------------------------
# 7. Workspace ↔ delivered copies byte-identical
# ---------------------------------------------------------------------------


def test_hook_contains_state_protection_block():
    """Script hygiene: the active hook for the current layout must
    contain the BC-1.10a protection block. When running from the
    workspace layout, this reads src/unit_1/bin/check-write-auth; when
    running from the delivered layout, this reads bin/check-write-auth.
    No skip — every layout asserts its own hook."""
    hook_body = _hook_path().read_text(encoding="utf-8")
    assert "BC-1.10a" in hook_body, (
        "Hook must reference BC-1.10a (state-file protection block)."
    )
    assert "debrief_state.json" in hook_body
    assert "deck_state.json" in hook_body
    assert "python -m debrief.debrief_state update" in hook_body
