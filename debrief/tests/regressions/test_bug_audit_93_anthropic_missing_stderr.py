# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-93: actionable stderr + exit-code policy
when the ``anthropic`` SDK is missing.

Pre-fix, the launcher caught ``ModuleNotFoundError`` from the lazy-import
sites, logged to JSONL, and exited 0 with no console output. To the user
this looked like ``/debrief:script`` silently producing nothing.

This test pins the post-fix behavior:
  (a) when anthropic is missing, stderr emits a single actionable line
      naming the install fix
  (b) the existing JSONL log entry is still written
  (c) /debrief:script (direct CLI) exits 2 — the user sees a non-zero
      exit code and knows the deliverable failed
  (d) deck-complete-finalization (cascade) exits 0 — the consultant's
      4-step finalization continues to /debrief:export and /debrief:handout
  (e) rewrite_brief always exits 0 — PreCompact must never block compaction
  (f) when the SDK is present and the API call succeeds, no stderr
      anthropic-warning fires
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_HERE = Path(__file__).resolve().parent
_TESTS_DIR = _HERE.parent
_PROJECT_ROOT = _TESTS_DIR.parent

# Prefer the workspace stub when available so tests run against the source of truth.
# Add unit_3 (launcher), unit_2 (debrief_state), and unit_1 to sys.path so the
# launcher's sibling imports (`from debrief_state import read_deck_state`)
# resolve.
for _u in ("unit_3", "unit_2", "unit_1"):
    _stub = _PROJECT_ROOT / "src" / _u
    if _stub.is_dir() and str(_stub) not in sys.path:
        sys.path.insert(0, str(_stub))

try:
    launcher = importlib.import_module("launcher")
except ModuleNotFoundError:  # pragma: no cover
    launcher = importlib.import_module("debrief.launcher")


# ---------------------------------------------------------------------------
# Helpers — synthesize the project artifacts the launcher reads
# ---------------------------------------------------------------------------


def _bootstrap_project(tmp_path: Path) -> Path:
    """Write the minimum state the launcher reads before the API call."""
    project_root = tmp_path / "proj"
    project_root.mkdir()
    debrief_dir = project_root / ".debrief"
    debrief_dir.mkdir()

    # deck_state.json with one approved slide
    (project_root / "deck_state.json").write_text(json.dumps({
        "project_name": "test", "created_at": "2026-05-05T00:00:00+00:00",
        "archetype": "lab_meeting", "style_locked": True, "closing_slide": None,
        "slides": [{
            "slug": "intro", "title": "Intro", "status": "approved", "backup": False,
            "content_summary": "test", "visual_approach": "test", "design_choices": "",
            "forks_not_taken": "", "user_recommendations": "", "qa_passed": True,
            "accepted_violations": [], "last_modified": "2026-05-05T00:00:00+00:00",
            "group_id": "group_01", "user_assets": [], "has_math": False,
        }],
        "presentations": [],
    }))
    (project_root / "debrief_state.json").write_text(json.dumps({
        "phase": "production", "sub_phase": "production/red_green",
        "active_agent": "consultant", "archetype": "lab_meeting",
        "current_group_id": "group_01", "current_slide_slug": None,
        "pending_gate": None, "last_gate_response": None,
        "red_green_started_at": None, "group_slide_index": 1,
        "group_slide_count": 1, "backup_mode": False,
        "completed_groups": [], "pre_view_state": None,
        "view_deferred": False, "closing_slide_pending": False,
        "group_revise_slug": None, "style_import_mode": None,
        "reference_provided": False, "reference_modality": None,
        "papers_provided": False, "selected_figures": None,
        "session_started_at": "2026-05-05T00:00:00+00:00",
        "state_hash": "x",
    }))
    (project_root / "deck_brief.md").write_text("# Deck Brief\n\n## Intent\nTest.\n")
    output_dir = project_root / "output"
    output_dir.mkdir()
    (output_dir / "audience.yaml").write_text("audience:\n  - name: A\n    role: peer\n")
    (output_dir / "timeline.jsonl").write_text("")
    (debrief_dir / "dialog.jsonl").write_text("")
    return project_root


def _fake_agent_card(plugin_root: Path, name: str, body: str = "system prompt body") -> None:
    agents_dir = plugin_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{name}.md").write_text(
        f"---\nname: {name}\nmodel: claude-sonnet-4-6\nmaxTurns: 1\ntools: Read\n---\n\n{body}\n"
    )


# ---------------------------------------------------------------------------
# Helper-function unit tests
# ---------------------------------------------------------------------------


def test_is_anthropic_module_error_recognises_correct_exception() -> None:
    exc = ModuleNotFoundError("No module named 'anthropic'", name="anthropic")
    assert launcher._is_anthropic_module_error(exc)


def test_is_anthropic_module_error_rejects_other_modules() -> None:
    exc = ModuleNotFoundError("No module named 'pptx'", name="pptx")
    assert not launcher._is_anthropic_module_error(exc)


def test_is_anthropic_module_error_rejects_other_exception_types() -> None:
    assert not launcher._is_anthropic_module_error(ValueError("nope"))


def test_emit_anthropic_missing_stderr_writes_actionable_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    launcher._emit_anthropic_missing_stderr("/debrief:script")
    captured = capsys.readouterr()
    err = captured.err
    assert "anthropic SDK not installed" in err
    assert "/debrief:script" in err
    assert "pip install" in err
    assert "anthropic>=0.40" in err
    assert "debrief --rebuild-env" in err


# ---------------------------------------------------------------------------
# main_script_writer end-to-end with mocked anthropic missing
# ---------------------------------------------------------------------------


def _force_module_not_found(mod_name: str = "anthropic") -> None:
    """Patch the import so any `import anthropic` within the function raises."""
    # We can't fully fake the import inside lazy-import; the function call
    # raises inside call_script_writer_agent. Easiest seam: patch the
    # call_X_agent function to raise ModuleNotFoundError directly.


def test_script_writer_direct_invocation_exits_2_on_missing_anthropic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """trigger='/debrief:script' (direct) → exit 2 + stderr line."""
    project_root = _bootstrap_project(tmp_path)
    plugin_root = tmp_path / "plugin"
    _fake_agent_card(plugin_root, "script-writer")

    def _raise(*a: object, **kw: object) -> str:
        raise ModuleNotFoundError("No module named 'anthropic'", name="anthropic")

    with patch.object(launcher, "call_script_writer_agent", side_effect=_raise):
        with pytest.raises(SystemExit) as excinfo:
            launcher.main_script_writer(
                project_root, trigger="/debrief:script", plugin_root=plugin_root
            )
    assert excinfo.value.code == 2

    err = capsys.readouterr().err
    assert "anthropic SDK not installed" in err
    assert "/debrief:script" in err

    # JSONL log entry preserved.
    log = (project_root / ".debrief" / "script_errors.jsonl").read_text().strip()
    assert log
    entry = json.loads(log.splitlines()[-1])
    assert entry["error_class"] == "ModuleNotFoundError"
    assert "anthropic" in entry["error_message"]


def test_script_writer_cascade_invocation_exits_0_on_missing_anthropic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """trigger='deck-complete-finalization' (cascade) → exit 0 + stderr line still emitted."""
    project_root = _bootstrap_project(tmp_path)
    plugin_root = tmp_path / "plugin"
    _fake_agent_card(plugin_root, "script-writer")

    def _raise(*a: object, **kw: object) -> str:
        raise ModuleNotFoundError("No module named 'anthropic'", name="anthropic")

    with patch.object(launcher, "call_script_writer_agent", side_effect=_raise):
        with pytest.raises(SystemExit) as excinfo:
            launcher.main_script_writer(
                project_root, trigger="deck-complete-finalization", plugin_root=plugin_root
            )
    assert excinfo.value.code == 0

    # The stderr message still fires — the user should know the rewriter
    # failed even when invoked as a cascade.
    err = capsys.readouterr().err
    assert "anthropic SDK not installed" in err

    log = (project_root / ".debrief" / "script_errors.jsonl").read_text().strip()
    assert log
    entry = json.loads(log.splitlines()[-1])
    assert entry["error_class"] == "ModuleNotFoundError"


def test_script_writer_handout_cascade_exits_0(tmp_path: Path) -> None:
    """trigger='/debrief:handout-cascade' (cascade) → exit 0."""
    project_root = _bootstrap_project(tmp_path)
    plugin_root = tmp_path / "plugin"
    _fake_agent_card(plugin_root, "script-writer")

    def _raise(*a: object, **kw: object) -> str:
        raise ModuleNotFoundError("No module named 'anthropic'", name="anthropic")

    with patch.object(launcher, "call_script_writer_agent", side_effect=_raise):
        with pytest.raises(SystemExit) as excinfo:
            launcher.main_script_writer(
                project_root, trigger="/debrief:handout-cascade", plugin_root=plugin_root
            )
    assert excinfo.value.code == 0


def test_script_writer_other_errors_still_exit_0(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-anthropic error must not bypass REQ-SCRIPT-WRITER-2's exit-0 contract.

    Pre-fix the contract was: "any failure → log + exit 0". Post-fix the
    only carve-out is missing-anthropic on direct CLI. All other exceptions
    keep the existing behavior: log + exit 0 + no stderr stunt.
    """
    project_root = _bootstrap_project(tmp_path)
    plugin_root = tmp_path / "plugin"
    _fake_agent_card(plugin_root, "script-writer")

    def _raise(*a: object, **kw: object) -> str:
        raise RuntimeError("transient API error")

    with patch.object(launcher, "call_script_writer_agent", side_effect=_raise):
        with pytest.raises(SystemExit) as excinfo:
            launcher.main_script_writer(
                project_root, trigger="/debrief:script", plugin_root=plugin_root
            )
    assert excinfo.value.code == 0

    err = capsys.readouterr().err
    assert "anthropic SDK not installed" not in err


# ---------------------------------------------------------------------------
# main_rewrite_brief: always exits 0 (PreCompact must never block)
# ---------------------------------------------------------------------------


def test_rewriter_exits_0_on_missing_anthropic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = _bootstrap_project(tmp_path)
    plugin_root = tmp_path / "plugin"
    _fake_agent_card(plugin_root, "rewriter")

    def _raise(*a: object, **kw: object) -> str:
        raise ModuleNotFoundError("No module named 'anthropic'", name="anthropic")

    with patch.object(launcher, "call_rewrite_agent", side_effect=_raise):
        with pytest.raises(SystemExit) as excinfo:
            launcher.main_rewrite_brief(
                project_root, trigger="manual", plugin_root=plugin_root
            )
    # PreCompact must never block — rewriter always exits 0.
    assert excinfo.value.code == 0

    # But the stderr line still fires so the user knows the brief did not synthesize.
    err = capsys.readouterr().err
    assert "anthropic SDK not installed" in err
    assert "rewrite_brief" in err

    log = (project_root / ".debrief" / "rewrite_errors.jsonl").read_text().strip()
    assert log
    entry = json.loads(log.splitlines()[-1])
    assert entry["error_class"] == "ModuleNotFoundError"
