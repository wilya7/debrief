# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-101.

Bug: the rewriter's "hybrid invocation" pattern (BC-5.19, pre-fix)
required ``ANTHROPIC_API_KEY`` because the launcher subprocess called
the Anthropic SDK directly. OAuth-authenticated Claude Code users (the
typical paid-subscription path) had no separate API key and could not
use the rewriter at any of its three triggers — every PreCompact hook,
every ``/debrief:refresh-brief``, and every ``/debrief:quit`` flush
silently failed.

Fix (BUG-AUDIT-101 / BC-3.18a / BC-3.18b / BC-3.18c / BC-5.16a /
BC-5.19 amended):

  1. PreCompact (`main_rewrite_brief --trigger PreCompact`) is now
     capture-only: appends transcript turns to .debrief/dialog.jsonl,
     writes a `.debrief/.brief_stale` sentinel, exits 0. NO SDK call.
     Synthesis is deferred to next session start.

  2. New `build_rewrite_prompt` CLI emits the structured prompt to
     stdout. The consultant captures it and feeds it to a Task
     dispatch.

  3. New `write_brief` CLI reads the agent's markdown output from
     `.debrief/draft/refresh_brief.md`, validates structure + roster
     YAML, atomically writes deck_brief.md + output/audience.yaml,
     removes draft + sentinel.

  4. The consultant agent card (`## Brief Refresh Dispatch`) and the
     project CLAUDE.md template document the four-step orchestration
     and the four triggers. The rewriter card no longer claims hybrid
     invocation.

For OAuth-only users with NO `ANTHROPIC_API_KEY`, all four triggers
work end-to-end after this fix. The Task dispatch (Step 2 of the
protocol) uses Claude Code's session credential, which the docs do
not contractually guarantee but which is empirically stable.

Tests cover: (1) PreCompact makes no SDK call and writes the sentinel;
(2) build_rewrite_prompt CLI emits the assembled prompt to stdout;
(3) write_brief CLI validates + atomically writes; (4) consultant card
contains the dispatch section; (5) CLAUDE.md template references the
sentinel check; (6) rewriter card no longer claims hybrid invocation.

The tests must pass from both the workspace and the delivered repo.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_HERE = Path(__file__).resolve().parent
_TESTS_DIR = _HERE.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_3").is_dir()


# Sibling-discovery sys.path setup matching BUG-AUDIT-93/98/99/100 pattern.
for _u in ("unit_3", "unit_2", "unit_1"):
    _stub = _PROJECT_ROOT / "src" / _u
    if _stub.is_dir() and str(_stub) not in sys.path:
        sys.path.insert(0, str(_stub))
_delivered = _PROJECT_ROOT / "src" / "debrief"
if _delivered.is_dir() and str(_delivered) not in sys.path:
    sys.path.insert(0, str(_delivered))

try:
    launcher = importlib.import_module("launcher")
except ModuleNotFoundError:  # pragma: no cover
    launcher = importlib.import_module("debrief.launcher")


def _consultant_md_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    delivered = _PROJECT_ROOT / "agents" / "consultant.md"
    if workspace.exists():
        return workspace
    if delivered.exists():
        return delivered
    raise FileNotFoundError("consultant.md not found")


def _rewriter_md_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "agents" / "rewriter.md"
    delivered = _PROJECT_ROOT / "agents" / "rewriter.md"
    if workspace.exists():
        return workspace
    if delivered.exists():
        return delivered
    raise FileNotFoundError("rewriter.md not found")


def _project_claude_template_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "templates" / "project_claude.md"
    delivered = _PROJECT_ROOT / "templates" / "project_claude.md"
    if workspace.exists():
        return workspace
    if delivered.exists():
        return delivered
    raise FileNotFoundError("project_claude.md template not found")


def _seed_minimal_project(project_root: Path) -> None:
    """Bare-minimum state files to make the launcher CLIs runnable."""
    project_root.mkdir(parents=True, exist_ok=True)
    debrief_dir = project_root / ".debrief"
    debrief_dir.mkdir(exist_ok=True)
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)
    (debrief_dir / "dialog.jsonl").write_text(
        '{"turn": 1, "timestamp": "2026-05-07T10:00:00Z", "role": "user", '
        '"responding_agent": null, "content": "test"}\n',
        encoding="utf-8",
    )
    (output_dir / "timeline.jsonl").write_text("", encoding="utf-8")


def _module_invocation_argv() -> list[str]:
    """Return the python -m argv prefix appropriate to either layout."""
    if _is_workspace_layout():
        return [sys.executable, "-m", "launcher"]
    return [sys.executable, "-m", "debrief.launcher"]


def _module_invocation_env() -> dict[str, str]:
    """Return env with PYTHONPATH set per layout, ANTHROPIC_API_KEY removed.

    The point of BUG-AUDIT-101 is to make this work WITHOUT the API key.
    """
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    if _is_workspace_layout():
        path_entries = [
            str(_PROJECT_ROOT / "src" / _u) for _u in ("unit_3", "unit_2", "unit_4")
        ]
    else:
        path_entries = [str(_PROJECT_ROOT / "src")]
    existing = env.get("PYTHONPATH", "")
    if existing:
        path_entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(path_entries)
    return env


# ---------------------------------------------------------------------------
# (1) PreCompact capture-only: makes no SDK call, writes sentinel.
# ---------------------------------------------------------------------------


class TestBugAudit101PreCompactCaptureOnly:
    """`main_rewrite_brief --trigger PreCompact` does not call the SDK."""

    def test_precompact_makes_no_sdk_call_and_writes_sentinel(
        self, tmp_path: Path
    ) -> None:
        _seed_minimal_project(tmp_path)

        # Mock call_rewrite_agent: if PreCompact reaches the SDK call,
        # this would raise loud + fail the test.
        def _explode(*a: object, **kw: object) -> str:
            raise AssertionError(
                "BUG-AUDIT-101 regression: PreCompact must NOT reach "
                "call_rewrite_agent — it is supposed to be capture-only."
            )

        with patch.object(launcher, "call_rewrite_agent", side_effect=_explode):
            with pytest.raises(SystemExit) as excinfo:
                launcher.main_rewrite_brief(tmp_path, trigger="PreCompact")
        assert excinfo.value.code == 0
        sentinel = tmp_path / ".debrief" / ".brief_stale"
        assert sentinel.is_file(), (
            "BC-3.18c: PreCompact must write the .brief_stale sentinel."
        )
        payload = json.loads(sentinel.read_text())
        assert payload["trigger"] == "PreCompact"
        assert "timestamp" in payload
        assert "last_archived_turn" in payload

    def test_precompact_via_subprocess_no_api_key(self, tmp_path: Path) -> None:
        # Full subprocess path with ANTHROPIC_API_KEY explicitly removed.
        # If the launcher tries to instantiate Anthropic(), it fails with
        # the auth TypeError. Post-fix, no instantiation happens.
        _seed_minimal_project(tmp_path)
        argv = _module_invocation_argv() + [
            "rewrite_brief",
            "--trigger", "PreCompact",
            "--project-root", str(tmp_path),
        ]
        env = _module_invocation_env()
        # Send an empty stdin envelope — the launcher should still write
        # the sentinel.
        result = subprocess.run(
            argv, input="", env=env, capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, (
            f"PreCompact subprocess should exit 0 without API key; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        # No "auth" / "api key" / "ANTHROPIC_API_KEY" mentions in stderr.
        stderr_lower = result.stderr.lower()
        assert "anthropic api authentication failed" not in stderr_lower
        assert "anthropic_api_key" not in stderr_lower
        assert (tmp_path / ".debrief" / ".brief_stale").is_file()


# ---------------------------------------------------------------------------
# (2) build_rewrite_prompt CLI.
# ---------------------------------------------------------------------------


class TestBugAudit101BuildRewritePromptCli:
    """`build_rewrite_prompt` CLI emits the structured prompt to stdout."""

    def test_emits_dialog_and_timeline_blocks(self, tmp_path: Path) -> None:
        _seed_minimal_project(tmp_path)
        argv = _module_invocation_argv() + [
            "build_rewrite_prompt",
            "--project-root", str(tmp_path),
        ]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"exit 0 expected; stderr={result.stderr!r}"
        )
        assert "DIALOG ARCHIVE" in result.stdout, (
            "build_rewrite_prompt must emit a DIALOG ARCHIVE block."
        )
        assert "EVENT TIMELINE" in result.stdout, (
            "build_rewrite_prompt must emit an EVENT TIMELINE block."
        )

    def test_subcommand_in_help(self) -> None:
        argv = _module_invocation_argv() + ["nonexistent_subcommand"]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        # The catch-all usage-line lists all subcommands; build_rewrite_prompt
        # MUST appear in it.
        assert "build_rewrite_prompt" in result.stderr, (
            "Catch-all usage message must list the new subcommand."
        )
        assert "write_brief" in result.stderr


# ---------------------------------------------------------------------------
# (3) write_brief CLI: validate + atomic write + cleanup.
# ---------------------------------------------------------------------------


_VALID_BRIEF = """# Deck Brief

## Audience

Working session with a collaborator.

### Roster

```yaml
audience:
  - name: Test Collaborator
    role: collaborator
```

## Room composition

1:1 working session.

## Intent

Test BUG-AUDIT-101's write_brief CLI.

## Duration

10 minutes.

## Prior decisions

None yet.

## Open questions

None yet.

## Content Signals

Test data.
"""


class TestBugAudit101WriteBriefCli:
    """`write_brief` CLI validates + atomically writes + clears sentinel."""

    def test_writes_brief_and_audience_yaml(self, tmp_path: Path) -> None:
        _seed_minimal_project(tmp_path)
        draft_dir = tmp_path / ".debrief" / "draft"
        draft_dir.mkdir(parents=True, exist_ok=True)
        (draft_dir / "refresh_brief.md").write_text(_VALID_BRIEF, encoding="utf-8")
        argv = _module_invocation_argv() + [
            "write_brief",
            "--project-root", str(tmp_path),
            "--trigger", "/debrief:refresh-brief",
        ]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"write_brief should always exit 0; stderr={result.stderr!r}"
        )
        # Brief written.
        brief = tmp_path / "deck_brief.md"
        assert brief.is_file()
        assert "## Audience" in brief.read_text()
        # Audience YAML written.
        audience = tmp_path / "output" / "audience.yaml"
        assert audience.is_file()
        assert "Test Collaborator" in audience.read_text()
        # Draft cleaned up.
        assert not (draft_dir / "refresh_brief.md").exists()
        # Rewrite metadata updated.
        meta = json.loads(
            (tmp_path / ".debrief" / "rewrite_metadata.json").read_text()
        )
        assert meta.get("bootstrap_complete") is True
        assert meta.get("last_rewrite_timestamp") is not None

    def test_clears_brief_stale_sentinel_on_success(self, tmp_path: Path) -> None:
        _seed_minimal_project(tmp_path)
        # Pre-write the sentinel as if PreCompact had set it.
        sentinel = tmp_path / ".debrief" / ".brief_stale"
        sentinel.write_text(
            json.dumps({
                "timestamp": "2026-05-07T10:00:00Z",
                "last_archived_turn": 5,
                "compaction_event_id": None,
                "trigger": "PreCompact",
            })
        )
        draft_dir = tmp_path / ".debrief" / "draft"
        draft_dir.mkdir(parents=True, exist_ok=True)
        (draft_dir / "refresh_brief.md").write_text(_VALID_BRIEF, encoding="utf-8")
        argv = _module_invocation_argv() + [
            "write_brief",
            "--project-root", str(tmp_path),
            "--trigger", "session_start_recovery",
        ]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert not sentinel.exists(), (
            "BC-3.18b: write_brief must remove the sentinel on success."
        )

    def test_invalid_brief_logs_and_exits_0(self, tmp_path: Path) -> None:
        _seed_minimal_project(tmp_path)
        draft_dir = tmp_path / ".debrief" / "draft"
        draft_dir.mkdir(parents=True, exist_ok=True)
        (draft_dir / "refresh_brief.md").write_text(
            "## Not a valid brief — missing # Deck Brief heading\n",
            encoding="utf-8",
        )
        argv = _module_invocation_argv() + [
            "write_brief",
            "--project-root", str(tmp_path),
            "--trigger", "/debrief:refresh-brief",
        ]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            "REQ-MEMORY-REWRITE-4: write_brief always exits 0."
        )
        # Brief NOT written.
        assert not (tmp_path / "deck_brief.md").exists()
        # Error logged.
        errors = (tmp_path / ".debrief" / "rewrite_errors.jsonl").read_text()
        assert "brief_structure_invalid" in errors

    def test_missing_draft_logs_and_exits_0(self, tmp_path: Path) -> None:
        _seed_minimal_project(tmp_path)
        # No draft file written.
        argv = _module_invocation_argv() + [
            "write_brief",
            "--project-root", str(tmp_path),
            "--trigger", "/debrief:refresh-brief",
        ]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert not (tmp_path / "deck_brief.md").exists()
        errors = (tmp_path / ".debrief" / "rewrite_errors.jsonl").read_text()
        assert "draft_missing" in errors


# ---------------------------------------------------------------------------
# (4) Consultant agent card has the dispatch section + (5) template + (6).
# ---------------------------------------------------------------------------


class TestBugAudit101ConsultantCardDispatchSection:
    """`agents/consultant.md` documents the four-step Task dispatch."""

    @pytest.fixture(scope="class")
    def card_text(self) -> str:
        return _consultant_md_path().read_text()

    def test_brief_refresh_dispatch_section_exists(self, card_text: str) -> None:
        assert "## Brief Refresh Dispatch" in card_text, (
            "BC-5.16a: agents/consultant.md must contain a "
            "`## Brief Refresh Dispatch` section."
        )

    def test_section_cites_bug_audit_101(self, card_text: str) -> None:
        # Anchor on the section header line and check the next ~3 lines.
        lines = card_text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("## Brief Refresh Dispatch"):
                window = "\n".join(lines[i : i + 3])
                assert "BUG-AUDIT-101" in window or "BC-5.16a" in window
                return
        pytest.fail("Brief Refresh Dispatch section header not found")

    def test_section_names_all_four_triggers(self, card_text: str) -> None:
        body = self._extract_section_body(card_text, "## Brief Refresh Dispatch")
        body_lower = body.lower()
        assert "session start" in body_lower
        assert "/debrief:refresh-brief" in body
        assert "/debrief:quit" in body
        # PreCompact must be named (and explicitly excluded as a trigger here).
        assert "precompact" in body_lower

    def test_section_documents_four_step_protocol(self, card_text: str) -> None:
        body = self._extract_section_body(card_text, "## Brief Refresh Dispatch")
        # The four canonical CLI invocations must all appear.
        assert "build_rewrite_prompt" in body
        assert "write_brief" in body
        # Task dispatch must be named.
        assert "Task(subagent_type=\"rewriter\"" in body
        # Heredoc staging step.
        assert ".debrief/draft/refresh_brief.md" in body

    def test_section_states_oauth_credential_model(self, card_text: str) -> None:
        body = self._extract_section_body(card_text, "## Brief Refresh Dispatch")
        body_lower = body.lower()
        assert "anthropic_api_key" in body_lower, (
            "BC-5.16a: section must explicitly state ANTHROPIC_API_KEY is "
            "NOT required."
        )
        assert "session credential" in body_lower or "oauth" in body_lower

    @staticmethod
    def _extract_section_body(text: str, header: str) -> str:
        lines = text.splitlines()
        body: list[str] = []
        in_section = False
        for line in lines:
            if line.startswith(header):
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if in_section:
                body.append(line)
        return "\n".join(body)


class TestBugAudit101ProjectClaudeTemplate:
    """`templates/project_claude.md` references the sentinel check."""

    def test_template_references_brief_stale_sentinel(self) -> None:
        text = _project_claude_template_path().read_text()
        assert ".debrief/.brief_stale" in text, (
            "BC-5.16a: project_claude.md template must reference the "
            "sentinel check on session start."
        )

    def test_template_references_session_start_recovery_trigger(self) -> None:
        text = _project_claude_template_path().read_text()
        assert "session_start_recovery" in text


class TestBugAudit101RewriterCardNotHybrid:
    """`agents/rewriter.md` no longer claims hybrid invocation."""

    def test_rewriter_card_documents_task_dispatch(self) -> None:
        text = _rewriter_md_path().read_text()
        # New language: agent is invoked via Task.
        assert "Task" in text
        assert "build_rewrite_prompt" in text
        assert "write_brief" in text

    def test_rewriter_card_does_not_claim_pure_hybrid(self) -> None:
        # The pre-fix card said "hybrid invocation pattern" without
        # qualification. Post-fix, the new section must explicitly
        # describe the Task-dispatch path. We assert the BUG-AUDIT-101
        # reference is present so a future cleanup pass can find this
        # context.
        text = _rewriter_md_path().read_text()
        assert "BUG-AUDIT-101" in text or "BC-3.18a" in text or "BC-3.18b" in text
