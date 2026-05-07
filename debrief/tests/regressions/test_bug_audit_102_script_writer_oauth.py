# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-102.

Bug: same architectural issue as BUG-AUDIT-101, applied to the
script-writer. The hybrid invocation pattern (BC-5.21 pre-fix) made
the launcher subprocess call the Anthropic SDK directly, requiring
ANTHROPIC_API_KEY. OAuth-only Claude Code users could not use
``/debrief:script`` or the deck-complete-finalization cascade.

Fix (BUG-AUDIT-102 / BC-3.20b / BC-3.20c / BC-5.16b / BC-5.21
amended):

  1. New ``build_script_prompt`` CLI emits the structured prompt
     (deck brief + audience + timeline + truncated dialog + slides +
     existing speaker_script as co-writer baseline) to stdout.
  2. New ``write_script`` CLI reads the agent's markdown from
     ``.debrief/draft/refresh_script.md``, runs the six guardrails
     (three blockers + two warnings), backup-before-overwrite,
     atomically writes ``speaker_script.md``, emits ``script_done``,
     removes the draft. Always exits 0.
  3. The consultant agent card gains a ``## Script Generation
     Dispatch`` section (BC-5.16b) prescribing the four-step Task
     dispatch for ``/debrief:script`` and the
     ``deck-complete-finalization`` cascade. The agent card retires
     the BC-3.20a "Task-tool dispatch unsupported" prose and
     describes the new canonical chain.
  4. The ``/debrief:handout-cascade`` trigger remains on the legacy
     ``main_script_writer`` direct-SDK path (cycle 103 cleanup
     decides what to do with it).

For OAuth-only users, ``/debrief:script`` and the
``deck-complete-finalization`` cascade now work end-to-end without
``ANTHROPIC_API_KEY``.

Tests cover: (1) build_script_prompt CLI emits the assembled prompt
and exits 1 when zero approved main slides; (2) write_script CLI
validates + atomically writes + emits script_done + removes draft;
(3) write_script logs blocker rejections and exits 0; (4) consultant
card has the dispatch section with required content; (5) script-writer
agent card retired the BC-3.20a unsupported prose and documents Task
dispatch; (6) commands/script.md describes the new flow.

The tests must pass from both the workspace and the delivered repo.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_TESTS_DIR = _HERE.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_3").is_dir()


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

import debrief_state  # noqa: E402


def _consultant_md_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    delivered = _PROJECT_ROOT / "agents" / "consultant.md"
    if workspace.exists():
        return workspace
    if delivered.exists():
        return delivered
    raise FileNotFoundError("consultant.md not found")


def _script_writer_md_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "agents" / "script-writer.md"
    delivered = _PROJECT_ROOT / "agents" / "script-writer.md"
    if workspace.exists():
        return workspace
    if delivered.exists():
        return delivered
    raise FileNotFoundError("script-writer.md not found")


def _commands_script_md_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "commands" / "script.md"
    delivered = _PROJECT_ROOT / "commands" / "script.md"
    if workspace.exists():
        return workspace
    if delivered.exists():
        return delivered
    raise FileNotFoundError("commands/script.md not found")


def _module_invocation_argv() -> list[str]:
    if _is_workspace_layout():
        return [sys.executable, "-m", "launcher"]
    return [sys.executable, "-m", "debrief.launcher"]


def _module_invocation_env() -> dict[str, str]:
    """ANTHROPIC_API_KEY removed — the BUG-AUDIT-102 path must work without."""
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


def _make_slide(slug: str, title: str, backup: bool = False) -> debrief_state.SlideRecord:
    return debrief_state.SlideRecord(
        slug=slug,
        title=title,
        status="approved",
        backup=backup,
        content_summary=f"{title} content summary",
        visual_approach=f"{title} visual",
        design_choices=f"{title} design",
        forks_not_taken=None,
        user_recommendations=None,
        qa_passed=True,
        accepted_violations=[],
        last_modified="2026-05-07T00:00:00+00:00",
        group_id=None,
        user_assets=[],
        has_math=False,
    )


def _seed_minimal_project(
    project_root: Path,
    *,
    slides: list[debrief_state.SlideRecord] | None = None,
) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / ".debrief").mkdir(exist_ok=True)
    (project_root / "output").mkdir(exist_ok=True)
    if slides is None:
        slides = [_make_slide("intro", "Introduction")]
    deck = debrief_state.DeckState(
        project_name="script_writer_oauth_test",
        created_at="2026-05-07T00:00:00+00:00",
        archetype="lab_meeting",
        style_locked=True,
        closing_slide=None,
        slides=slides,
        presentations=[],
    )
    debrief_state.write_deck_state(project_root, deck)
    (project_root / "deck_brief.md").write_text(
        "# Deck Brief\n\n## Intent\n\nTesting script writer.\n",
        encoding="utf-8",
    )
    (project_root / "output" / "audience.yaml").write_text(
        "audience:\n  - name: Test Person\n    role: peer\n",
        encoding="utf-8",
    )
    (project_root / "output" / "timeline.jsonl").write_text("", encoding="utf-8")
    (project_root / ".debrief" / "dialog.jsonl").write_text("", encoding="utf-8")


# ---------------------------------------------------------------------------
# (1) build_script_prompt CLI.
# ---------------------------------------------------------------------------


class TestBugAudit102BuildScriptPromptCli:
    """`build_script_prompt` CLI emits the structured prompt to stdout."""

    def test_emits_assembled_prompt(self, tmp_path: Path) -> None:
        _seed_minimal_project(tmp_path)
        argv = _module_invocation_argv() + [
            "build_script_prompt",
            "--project-root", str(tmp_path),
        ]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"exit 0 expected; stderr={result.stderr!r}"
        )
        # Key blocks the prompt assembler always emits.
        assert "DECK BRIEF" in result.stdout
        assert "EVENT TIMELINE" in result.stdout
        # The slide we seeded must appear (slug + title).
        assert "intro" in result.stdout
        assert "Introduction" in result.stdout

    def test_exits_1_on_no_approved_main_slides(self, tmp_path: Path) -> None:
        # Only a backup slide → no approved main → precondition failure.
        _seed_minimal_project(
            tmp_path,
            slides=[_make_slide("qa-only", "QA backup", backup=True)],
        )
        argv = _module_invocation_argv() + [
            "build_script_prompt",
            "--project-root", str(tmp_path),
        ]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert result.returncode == 1, (
            "BC-3.20b: build_script_prompt must exit 1 when no approved "
            "main (non-backup) slides exist."
        )
        assert "no approved" in result.stderr.lower()

    def test_subcommand_in_usage_message(self) -> None:
        argv = _module_invocation_argv() + ["nonexistent_subcommand"]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert "build_script_prompt" in result.stderr
        assert "write_script" in result.stderr


# ---------------------------------------------------------------------------
# (2) + (3) write_script CLI.
# ---------------------------------------------------------------------------


_VALID_SCRIPT = """# Speaker Script

**Target duration:** 10 minutes

---

## Slide 1: Introduction

**Slug:** `intro`

### Key talking points

- Open the meeting and outline the agenda for the audience.

### Transition

Move to the next slide.

### Estimated speaking time

10 minutes.

"""


class TestBugAudit102WriteScriptCli:
    """`write_script` CLI validates + atomically writes + emits script_done."""

    def test_writes_script_and_emits_event(self, tmp_path: Path) -> None:
        _seed_minimal_project(tmp_path)
        draft_dir = tmp_path / ".debrief" / "draft"
        draft_dir.mkdir(parents=True, exist_ok=True)
        (draft_dir / "refresh_script.md").write_text(_VALID_SCRIPT, encoding="utf-8")
        argv = _module_invocation_argv() + [
            "write_script",
            "--project-root", str(tmp_path),
            "--trigger", "/debrief:script",
        ]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"write_script always exits 0; stderr={result.stderr!r}"
        )
        # speaker_script.md written with the new content.
        script = tmp_path / "speaker_script.md"
        assert script.is_file()
        assert "# Speaker Script" in script.read_text()
        assert "Open the meeting" in script.read_text(), (
            "Validators must accept the canonical fixture so the new "
            "content actually lands."
        )
        # Draft cleaned up.
        assert not (draft_dir / "refresh_script.md").exists()
        # script_done event emitted.
        timeline = (tmp_path / "output" / "timeline.jsonl").read_text()
        assert "script_done" in timeline

    def test_invalid_script_logs_and_exits_0(self, tmp_path: Path) -> None:
        _seed_minimal_project(tmp_path)
        draft_dir = tmp_path / ".debrief" / "draft"
        draft_dir.mkdir(parents=True, exist_ok=True)
        (draft_dir / "refresh_script.md").write_text(
            # Missing "# Speaker Script" heading — fails the structure validator.
            "Some random text without the required heading.\n",
            encoding="utf-8",
        )
        argv = _module_invocation_argv() + [
            "write_script",
            "--project-root", str(tmp_path),
            "--trigger", "/debrief:script",
        ]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            "REQ-SCRIPT-WRITER-2: write_script always exits 0."
        )
        # speaker_script.md NOT written.
        assert not (tmp_path / "speaker_script.md").exists()
        # Error logged.
        errors = (tmp_path / ".debrief" / "script_errors.jsonl").read_text()
        assert "script_structure_invalid" in errors

    def test_missing_draft_logs_and_exits_0(self, tmp_path: Path) -> None:
        _seed_minimal_project(tmp_path)
        argv = _module_invocation_argv() + [
            "write_script",
            "--project-root", str(tmp_path),
            "--trigger", "/debrief:script",
        ]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert not (tmp_path / "speaker_script.md").exists()
        errors = (tmp_path / ".debrief" / "script_errors.jsonl").read_text()
        assert "draft_missing" in errors

    def test_backup_before_overwrite(self, tmp_path: Path) -> None:
        # Seed an existing speaker_script.md; write_script must back it up
        # before overwriting per BC-11.20.
        _seed_minimal_project(tmp_path)
        (tmp_path / "speaker_script.md").write_text(
            "# Speaker Script\n\nPrior content.\n", encoding="utf-8",
        )
        draft_dir = tmp_path / ".debrief" / "draft"
        draft_dir.mkdir(parents=True, exist_ok=True)
        (draft_dir / "refresh_script.md").write_text(_VALID_SCRIPT, encoding="utf-8")
        argv = _module_invocation_argv() + [
            "write_script",
            "--project-root", str(tmp_path),
            "--trigger", "/debrief:script",
        ]
        result = subprocess.run(
            argv, env=_module_invocation_env(), capture_output=True, text=True,
            timeout=15,
        )
        assert result.returncode == 0
        # New script written.
        assert "Open the meeting" in (tmp_path / "speaker_script.md").read_text()
        # Backup created.
        backup_dir = tmp_path / ".debrief" / "script_backups"
        assert backup_dir.is_dir()
        backups = list(backup_dir.glob("speaker_script.*.md"))
        assert len(backups) == 1, (
            f"Expected exactly one backup file; got {backups}"
        )


# ---------------------------------------------------------------------------
# (4) Consultant agent card has the dispatch section.
# ---------------------------------------------------------------------------


class TestBugAudit102ConsultantCardDispatchSection:
    """`agents/consultant.md` documents the four-step Task dispatch."""

    @pytest.fixture(scope="class")
    def card_text(self) -> str:
        return _consultant_md_path().read_text()

    def test_section_exists(self, card_text: str) -> None:
        assert "## Script Generation Dispatch" in card_text, (
            "BC-5.16b: agents/consultant.md must contain a "
            "`## Script Generation Dispatch` section."
        )

    def test_section_cites_bug_audit_102(self, card_text: str) -> None:
        body = self._extract_section_body(card_text)
        # Header line OR body should reference BUG-AUDIT-102 / BC-5.16b.
        lines = card_text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("## Script Generation Dispatch"):
                window = "\n".join(lines[i : i + 3])
                assert "BUG-AUDIT-102" in window or "BC-5.16b" in window
                return
        pytest.fail("Script Generation Dispatch section header not found")

    def test_section_names_in_session_triggers(self, card_text: str) -> None:
        body = self._extract_section_body(card_text)
        assert "/debrief:script" in body
        assert "deck-complete-finalization" in body

    def test_section_acknowledges_residual_cascade(self, card_text: str) -> None:
        body = self._extract_section_body(card_text)
        assert "/debrief:handout-cascade" in body, (
            "BC-5.16b: section must name the residual cascade trigger "
            "as a transitional concern."
        )

    def test_section_documents_four_step_protocol(self, card_text: str) -> None:
        body = self._extract_section_body(card_text)
        assert "build_script_prompt" in body
        assert "write_script" in body
        assert "Task(subagent_type=\"script-writer\"" in body
        assert ".debrief/draft/refresh_script.md" in body

    def test_section_states_credential_model(self, card_text: str) -> None:
        body = self._extract_section_body(card_text)
        body_lower = body.lower()
        assert "anthropic_api_key" in body_lower
        # Either explicitly stating "session credential" OR "OAuth"
        # qualifies the credential model statement.
        assert "session credential" in body_lower or "oauth" in body_lower

    @staticmethod
    def _extract_section_body(text: str) -> str:
        lines = text.splitlines()
        body: list[str] = []
        in_section = False
        for line in lines:
            if line.startswith("## Script Generation Dispatch"):
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if in_section:
                body.append(line)
        return "\n".join(body)


# ---------------------------------------------------------------------------
# (5) Script-writer agent card retired BC-3.20a unsupported prose.
# ---------------------------------------------------------------------------


class TestBugAudit102ScriptWriterCardRetiresBc320a:
    """`agents/script-writer.md` retires the 'Task unsupported' prose."""

    def test_card_documents_task_dispatch(self) -> None:
        text = _script_writer_md_path().read_text()
        assert "Task" in text
        assert "build_script_prompt" in text
        assert "write_script" in text

    def test_card_no_longer_says_task_dispatch_unsupported(self) -> None:
        text = _script_writer_md_path().read_text().lower()
        # The pre-fix prose said "Task-dispatched invocation with a
        # free-form prompt is unsupported". Post-BUG-AUDIT-102 this
        # claim is RETIRED — Task is the canonical path.
        assert "is unsupported" not in text, (
            "BUG-AUDIT-102 retires BC-3.20a's 'Task dispatch unsupported' "
            "prose; the agent card should no longer contain it."
        )

    def test_card_cites_bug_audit_102(self) -> None:
        text = _script_writer_md_path().read_text()
        assert (
            "BUG-AUDIT-102" in text
            or "BC-3.20b" in text
            or "BC-3.20c" in text
        )


# ---------------------------------------------------------------------------
# (6) commands/script.md describes the new flow.
# ---------------------------------------------------------------------------


class TestBugAudit102CommandsScriptMd:
    """`commands/script.md` describes the four-step flow."""

    def test_describes_build_script_prompt_and_write_script(self) -> None:
        text = _commands_script_md_path().read_text()
        assert "build_script_prompt" in text
        assert "write_script" in text

    def test_describes_task_dispatch(self) -> None:
        text = _commands_script_md_path().read_text()
        assert "Task" in text and "subagent_type" in text

    def test_credential_model_documented(self) -> None:
        text = _commands_script_md_path().read_text().lower()
        assert "anthropic_api_key" in text
