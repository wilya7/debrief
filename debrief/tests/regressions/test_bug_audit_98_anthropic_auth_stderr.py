# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-98.

Bug: when ``ANTHROPIC_API_KEY`` is unset, ``anthropic.Anthropic()`` raises
a ``TypeError`` whose message starts with "Could not resolve authentication
method". A separate failure path is ``anthropic.AuthenticationError`` (HTTP
401 from a present-but-invalid credential). Pre-fix, the script-writer and
rewriter call sites in ``launcher.py`` classified exceptions only via
``_is_anthropic_module_error`` (BUG-AUDIT-93), which catches only
``ModuleNotFoundError``. Auth errors fell through the classifier into the
silent ``sys.exit(0)`` branch — the user typed ``/debrief:script``, saw
nothing, and had to read ``.debrief/script_errors.jsonl`` to find out why.

Fix (BC-3.18 / BC-3.20 amendments + BC-3.20a): a new classifier
``_is_anthropic_auth_error`` detects both auth failure shapes; a new
emitter ``_emit_anthropic_auth_missing_stderr`` prints an actionable
stderr line naming ``ANTHROPIC_API_KEY`` and the JSONL log path. Both
call sites get an ``elif`` branch that fires the auth-error path with
the same exit-code asymmetry as the missing-module case (script-writer
direct → exit 2; cascades → exit 0; rewriter always exits 0). The
script-writer agent card gets an opening note clarifying the canonical
invocation is via the launcher CLI, not direct Task-tool dispatch.

The tests must pass from both the workspace and the delivered repo.
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

# Mirror BUG-AUDIT-93's sibling-discovery pattern so the launcher's
# `from debrief_state import ...` resolves in both workspace and delivered layouts.
for _u in ("unit_3", "unit_2", "unit_1"):
    _stub = _PROJECT_ROOT / "src" / _u
    if _stub.is_dir() and str(_stub) not in sys.path:
        sys.path.insert(0, str(_stub))

try:
    launcher = importlib.import_module("launcher")
except ModuleNotFoundError:  # pragma: no cover
    launcher = importlib.import_module("debrief.launcher")


def _script_writer_agent_card_path() -> Path:
    """Locate script-writer.md in either layout."""
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "agents" / "script-writer.md"
    delivered = _PROJECT_ROOT / "agents" / "script-writer.md"
    if workspace.exists():
        return workspace
    if delivered.exists():
        return delivered
    raise FileNotFoundError(
        "script-writer.md not found in workspace or delivered layout"
    )


# ---------------------------------------------------------------------------
# Project bootstrapping (mirrors test_bug_audit_93's helper).
# ---------------------------------------------------------------------------


def _bootstrap_project(tmp_path: Path) -> Path:
    """Write the minimum project state the launcher reads before the API call."""
    project_root = tmp_path / "proj"
    project_root.mkdir()
    debrief_dir = project_root / ".debrief"
    debrief_dir.mkdir()

    (project_root / "deck_state.json").write_text(json.dumps({
        "project_name": "test", "created_at": "2026-05-07T00:00:00+00:00",
        "archetype": "lab_meeting", "style_locked": True, "closing_slide": None,
        "slides": [{
            "slug": "intro", "title": "Intro", "status": "approved", "backup": False,
            "content_summary": "test", "visual_approach": "test", "design_choices": "",
            "forks_not_taken": "", "user_recommendations": "", "qa_passed": True,
            "accepted_violations": [], "last_modified": "2026-05-07T00:00:00+00:00",
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
        "session_started_at": "2026-05-07T00:00:00+00:00",
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


# Synthesize a class named "AuthenticationError" without importing anthropic,
# so the classifier's class-name check fires identically to the SDK shape.
class _AuthenticationError(Exception):
    """Stand-in for anthropic.AuthenticationError. Class name match is what the classifier keys on."""


_AuthenticationError.__name__ = "AuthenticationError"


# ---------------------------------------------------------------------------
# Classifier unit tests.
# ---------------------------------------------------------------------------


class TestBugAudit98Classifier:
    """`_is_anthropic_auth_error` recognises both auth shapes, rejects others."""

    def test_recognises_typeerror_with_authentication_message(self) -> None:
        exc = TypeError(
            "Could not resolve authentication method. Expected one of "
            "api_key, auth_token, or credentials to be set."
        )
        assert launcher._is_anthropic_auth_error(exc)

    def test_recognises_typeerror_message_case_insensitive(self) -> None:
        exc = TypeError("could not resolve authentication method...")
        assert launcher._is_anthropic_auth_error(exc)

    def test_rejects_typeerror_with_unrelated_message(self) -> None:
        exc = TypeError("expected str, got int")
        assert not launcher._is_anthropic_auth_error(exc)

    def test_recognises_authentication_error_class_name(self) -> None:
        exc = _AuthenticationError("invalid x-api-key")
        assert launcher._is_anthropic_auth_error(exc)

    def test_rejects_unrelated_exception(self) -> None:
        assert not launcher._is_anthropic_auth_error(ValueError("nope"))
        assert not launcher._is_anthropic_auth_error(RuntimeError("boom"))

    def test_rejects_module_not_found_error(self) -> None:
        # ModuleNotFoundError is BUG-AUDIT-93's territory; the auth
        # classifier MUST NOT match it (otherwise both stderr emitters
        # would fire and the user would see two confusing messages).
        exc = ModuleNotFoundError("No module named 'anthropic'", name="anthropic")
        assert not launcher._is_anthropic_auth_error(exc)


# ---------------------------------------------------------------------------
# Stderr emitter unit test.
# ---------------------------------------------------------------------------


class TestBugAudit98StderrEmitter:
    """`_emit_anthropic_auth_missing_stderr` writes the canonical line."""

    def test_writes_actionable_line_for_script_writer(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        launcher._emit_anthropic_auth_missing_stderr(
            "/debrief:script", log_path=".debrief/script_errors.jsonl"
        )
        err = capsys.readouterr().err
        assert "anthropic API authentication failed" in err
        assert "/debrief:script" in err
        assert "ANTHROPIC_API_KEY" in err
        assert ".debrief/script_errors.jsonl" in err

    def test_writes_actionable_line_for_rewriter(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        launcher._emit_anthropic_auth_missing_stderr(
            "rewrite_brief", log_path=".debrief/rewrite_errors.jsonl"
        )
        err = capsys.readouterr().err
        assert "anthropic API authentication failed" in err
        assert "rewrite_brief" in err
        assert "ANTHROPIC_API_KEY" in err
        assert ".debrief/rewrite_errors.jsonl" in err


# ---------------------------------------------------------------------------
# main_script_writer end-to-end with mocked auth failure.
# ---------------------------------------------------------------------------


class TestBugAudit98ScriptWriterTypeError:
    """Direct CLI: TypeError "could not resolve authentication" → exit 2."""

    def test_direct_invocation_exits_2_on_auth_typeerror(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project_root = _bootstrap_project(tmp_path)
        plugin_root = tmp_path / "plugin"
        _fake_agent_card(plugin_root, "script-writer")

        def _raise(*a: object, **kw: object) -> str:
            raise TypeError(
                "Could not resolve authentication method. Expected one of "
                "api_key, auth_token, or credentials to be set."
            )

        with patch.object(launcher, "call_script_writer_agent", side_effect=_raise):
            with pytest.raises(SystemExit) as excinfo:
                launcher.main_script_writer(
                    project_root, trigger="/debrief:script", plugin_root=plugin_root,
                )
        assert excinfo.value.code == 2, (
            "BC-3.20 (amended by BUG-AUDIT-98): direct CLI invocation must "
            "exit 2 on auth failure."
        )

        err = capsys.readouterr().err
        assert "anthropic API authentication failed" in err
        assert "ANTHROPIC_API_KEY" in err
        assert "/debrief:script" in err
        # The missing-SDK stderr line must NOT also fire — that would
        # confuse the user about the actual remediation.
        assert "anthropic SDK not installed" not in err

        # JSONL log entry preserved.
        log = (project_root / ".debrief" / "script_errors.jsonl").read_text().strip()
        assert log
        entry = json.loads(log.splitlines()[-1])
        assert entry["error_class"] == "TypeError"
        assert "Could not resolve authentication" in entry["error_message"]

    def test_cascade_invocation_exits_0_on_auth_typeerror(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project_root = _bootstrap_project(tmp_path)
        plugin_root = tmp_path / "plugin"
        _fake_agent_card(plugin_root, "script-writer")

        def _raise(*a: object, **kw: object) -> str:
            raise TypeError("Could not resolve authentication method.")

        with patch.object(launcher, "call_script_writer_agent", side_effect=_raise):
            with pytest.raises(SystemExit) as excinfo:
                launcher.main_script_writer(
                    project_root,
                    trigger="deck-complete-finalization",
                    plugin_root=plugin_root,
                )
        assert excinfo.value.code == 0, (
            "BC-3.20: cascade invocation must keep exit 0 so the "
            "consultant's finalization sequence continues."
        )

        # Stderr still fires on cascade so the user knows the script failed.
        err = capsys.readouterr().err
        assert "anthropic API authentication failed" in err

    def test_handout_cascade_exits_0_on_auth_typeerror(
        self, tmp_path: Path
    ) -> None:
        project_root = _bootstrap_project(tmp_path)
        plugin_root = tmp_path / "plugin"
        _fake_agent_card(plugin_root, "script-writer")

        def _raise(*a: object, **kw: object) -> str:
            raise TypeError("Could not resolve authentication method.")

        with patch.object(launcher, "call_script_writer_agent", side_effect=_raise):
            with pytest.raises(SystemExit) as excinfo:
                launcher.main_script_writer(
                    project_root,
                    trigger="/debrief:handout-cascade",
                    plugin_root=plugin_root,
                )
        assert excinfo.value.code == 0


class TestBugAudit98ScriptWriterAuthenticationError:
    """Direct CLI: anthropic.AuthenticationError → exit 2."""

    def test_direct_invocation_exits_2_on_authentication_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project_root = _bootstrap_project(tmp_path)
        plugin_root = tmp_path / "plugin"
        _fake_agent_card(plugin_root, "script-writer")

        def _raise(*a: object, **kw: object) -> str:
            raise _AuthenticationError("Invalid x-api-key")

        with patch.object(launcher, "call_script_writer_agent", side_effect=_raise):
            with pytest.raises(SystemExit) as excinfo:
                launcher.main_script_writer(
                    project_root, trigger="/debrief:script", plugin_root=plugin_root,
                )
        assert excinfo.value.code == 2

        err = capsys.readouterr().err
        assert "anthropic API authentication failed" in err
        assert "ANTHROPIC_API_KEY" in err

        log = (project_root / ".debrief" / "script_errors.jsonl").read_text().strip()
        entry = json.loads(log.splitlines()[-1])
        assert entry["error_class"] == "AuthenticationError"


class TestBugAudit98UnrelatedErrorsStillSilent:
    """Errors that are neither missing-module nor auth-shaped keep exit-0 silent."""

    def test_runtime_error_keeps_silent_exit_0(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project_root = _bootstrap_project(tmp_path)
        plugin_root = tmp_path / "plugin"
        _fake_agent_card(plugin_root, "script-writer")

        def _raise(*a: object, **kw: object) -> str:
            raise RuntimeError("transient API hiccup")

        with patch.object(launcher, "call_script_writer_agent", side_effect=_raise):
            with pytest.raises(SystemExit) as excinfo:
                launcher.main_script_writer(
                    project_root, trigger="/debrief:script", plugin_root=plugin_root,
                )
        assert excinfo.value.code == 0, (
            "Generic exceptions retain the existing silent exit-0 behavior — "
            "BUG-AUDIT-98 only adds stderr for the two well-known auth shapes."
        )
        err = capsys.readouterr().err
        assert "anthropic API authentication failed" not in err
        assert "anthropic SDK not installed" not in err


# ---------------------------------------------------------------------------
# main_rewrite_brief: always exits 0 (PreCompact must never block).
# ---------------------------------------------------------------------------


class TestBugAudit98Rewriter:
    """Rewriter exits 0 on auth failure but emits stderr."""

    def test_rewriter_exits_0_on_auth_typeerror(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project_root = _bootstrap_project(tmp_path)
        plugin_root = tmp_path / "plugin"
        _fake_agent_card(plugin_root, "rewriter")

        def _raise(*a: object, **kw: object) -> str:
            raise TypeError(
                "Could not resolve authentication method. Expected one of "
                "api_key, auth_token, or credentials to be set."
            )

        with patch.object(launcher, "call_rewrite_agent", side_effect=_raise):
            with pytest.raises(SystemExit) as excinfo:
                launcher.main_rewrite_brief(
                    project_root, trigger="manual", plugin_root=plugin_root,
                )
        assert excinfo.value.code == 0, (
            "REQ-MEMORY-REWRITE-4: rewriter MUST never block PreCompact, "
            "so even auth failures keep exit 0."
        )

        err = capsys.readouterr().err
        assert "anthropic API authentication failed" in err
        assert "rewrite_brief" in err
        assert ".debrief/rewrite_errors.jsonl" in err

        log = (project_root / ".debrief" / "rewrite_errors.jsonl").read_text().strip()
        entry = json.loads(log.splitlines()[-1])
        assert entry["error_class"] == "TypeError"

    def test_rewriter_exits_0_on_authentication_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project_root = _bootstrap_project(tmp_path)
        plugin_root = tmp_path / "plugin"
        _fake_agent_card(plugin_root, "rewriter")

        def _raise(*a: object, **kw: object) -> str:
            raise _AuthenticationError("HTTP 401")

        with patch.object(launcher, "call_rewrite_agent", side_effect=_raise):
            with pytest.raises(SystemExit) as excinfo:
                launcher.main_rewrite_brief(
                    project_root, trigger="manual", plugin_root=plugin_root,
                )
        assert excinfo.value.code == 0
        err = capsys.readouterr().err
        assert "anthropic API authentication failed" in err


# ---------------------------------------------------------------------------
# Agent-card invocation-mode constraint (BC-3.20a).
# ---------------------------------------------------------------------------


class TestBugAudit98ScriptWriterAgentCard:
    """`script-writer.md` documents the canonical invocation path.

    BUG-AUDIT-98 (this cycle) added a constraint that direct Task-tool
    dispatch was unsupported — the launcher CLI was the only canonical
    path. BUG-AUDIT-102 RETIRED that constraint: Task dispatch is now
    the canonical path for the in-session triggers via the new
    build_script_prompt + write_script CLIs. This test was adapted
    in-place to assert the BUG-AUDIT-102 contract instead. The
    BUG-AUDIT-98 prior-art (auth-error stderr behavior) is unchanged
    and still tested by the other classes in this file.
    """

    def test_agent_card_documents_canonical_invocation(self) -> None:
        text = _script_writer_agent_card_path().read_text()
        # Post-BUG-AUDIT-102: the canonical path is Task-dispatched via
        # the consultant's build_script_prompt + write_script chain.
        # The agent card MUST document this. The legacy
        # `python -m debrief.launcher script_writer` invocation is
        # mentioned only for the residual /debrief:handout-cascade
        # trigger; build_script_prompt + write_script + Task are the
        # canonical references.
        assert "build_script_prompt" in text, (
            "BC-3.20b (BUG-AUDIT-102): script-writer.md must name "
            "the build_script_prompt CLI as part of the canonical "
            "Task-dispatch chain."
        )
        assert "write_script" in text, (
            "BC-3.20c (BUG-AUDIT-102): script-writer.md must name "
            "the write_script CLI."
        )
        lower = text.lower()
        assert "task" in lower, (
            "BC-5.21 amended (BUG-AUDIT-102): script-writer.md must "
            "document Task-dispatch as the canonical invocation."
        )
        # Must reference at least one BC/BUG-AUDIT for traceability.
        # BUG-AUDIT-98 was the original anchor; BUG-AUDIT-102 is the
        # current contract. Either is acceptable.
        assert any(
            anchor in text
            for anchor in ("BC-3.20a", "BC-3.20b", "BC-3.20c", "BUG-AUDIT-98", "BUG-AUDIT-102", "BC-5.21")
        )
