# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-103.

Final piece of the BUG-AUDIT-101/102 OAuth-everywhere arc. After cycles
101 and 102, the rewriter and script-writer route through Task-dispatch
for canonical user flows. The residual SDK-required path was
``/debrief:handout-cascade`` — fired inside the handout subprocess when
``speaker_script.md`` is missing. Cycle 103:

  1. Lifts the cascade up to the consultant orchestration layer
     (Option D in the planning chat). `main_handout` no longer
     auto-cascades; the consultant checks for ``speaker_script.md``
     before invoking handout, and runs the BUG-AUDIT-102 four-step
     Task-dispatch chain to generate it if absent.
  2. Demotes ``anthropic`` from required to optional. ``pyproject.toml``
     moves it to ``[project.optional-dependencies] sdk_fallback``;
     ``environment.yml`` removes it; ``bin/debrief``'s smoke test no
     longer imports it.
  3. Adds a ``## Handout Generation Dispatch`` section to the
     consultant card (BC-5.16c) documenting the precondition self-heal.

For OAuth-only users, every canonical workflow runs end-to-end after
this cycle.

Tests cover: (1) main_handout no longer imports main_script_writer;
(2) main_handout's missing-script branch exits 2 (not 0) with the
clear stderr message; (3) consultant card has the
``## Handout Generation Dispatch`` section with required content;
(4) commands/handout.md describes the new flow.

The dependency-related assertions for cycle 103 (anthropic moved to
optional, dropped from environment.yml, dropped from bin/debrief
smoke test) live in the inverted ``test_bug_audit_93_anthropic_dependency.py``
— same filename for git-history-traceability.

The tests must pass from both the workspace and the delivered repo.
"""

from __future__ import annotations

import importlib
import inspect
import os
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_TESTS_DIR = _HERE.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


for _u in ("unit_11", "unit_3", "unit_2", "unit_1"):
    _stub = _PROJECT_ROOT / "src" / _u
    if _stub.is_dir() and str(_stub) not in sys.path:
        sys.path.insert(0, str(_stub))
_delivered = _PROJECT_ROOT / "src" / "debrief"
if _delivered.is_dir() and str(_delivered) not in sys.path:
    sys.path.insert(0, str(_delivered))

try:
    utility_skills = importlib.import_module("utility_skills")
except ModuleNotFoundError:  # pragma: no cover
    utility_skills = importlib.import_module("debrief.utility_skills")

import debrief_state  # noqa: E402


def _consultant_md_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    delivered = _PROJECT_ROOT / "agents" / "consultant.md"
    if workspace.exists():
        return workspace
    if delivered.exists():
        return delivered
    raise FileNotFoundError("consultant.md not found")


def _commands_handout_md_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "commands" / "handout.md"
    delivered = _PROJECT_ROOT / "commands" / "handout.md"
    if workspace.exists():
        return workspace
    if delivered.exists():
        return delivered
    raise FileNotFoundError("commands/handout.md not found")


def _make_slide(slug: str, title: str) -> debrief_state.SlideRecord:
    return debrief_state.SlideRecord(
        slug=slug,
        title=title,
        status="approved",
        backup=False,
        content_summary=f"{title} content",
        visual_approach=None,
        design_choices=None,
        forks_not_taken=None,
        user_recommendations=None,
        qa_passed=True,
        accepted_violations=[],
        last_modified="2026-05-07T00:00:00+00:00",
        group_id=None,
        user_assets=[],
        has_math=False,
    )


def _seed_handout_project(project_root: Path) -> None:
    """Seed a project with one approved slide but NO speaker_script.md.

    The handout's pre-103 auto-cascade would have fired in this state;
    post-103 the handout exits 2 instead.
    """
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / ".debrief").mkdir(exist_ok=True)
    (project_root / "output").mkdir(exist_ok=True)
    deck = debrief_state.DeckState(
        project_name="bug_audit_103_test",
        created_at="2026-05-07T00:00:00+00:00",
        archetype="lab_meeting",
        style_locked=True,
        closing_slide=None,
        slides=[_make_slide("intro", "Introduction")],
        presentations=[],
    )
    debrief_state.write_deck_state(project_root, deck)


# ---------------------------------------------------------------------------
# (1) + (2) Handout no longer auto-cascades; missing script exits 2.
# ---------------------------------------------------------------------------


class TestBugAudit103HandoutNoAutoCascade:
    """`main_handout` no longer imports or invokes `main_script_writer`."""

    def test_main_handout_source_does_not_import_main_script_writer(
        self,
    ) -> None:
        """The auto-cascade `from launcher import main_script_writer`
        line that pre-103 used to fire when speaker_script.md was
        missing must be GONE."""
        src = inspect.getsource(utility_skills.main_handout)
        assert "from launcher import main_script_writer" not in src, (
            "BUG-AUDIT-103 regression: main_handout still imports "
            "main_script_writer. The auto-cascade is retired."
        )
        assert "main_script_writer(" not in src, (
            "BUG-AUDIT-103 regression: main_handout still calls "
            "main_script_writer. The script-precondition self-heal "
            "lives in the consultant per BC-5.16c."
        )

    def test_missing_script_exits_2_with_clear_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-11.16 (BUG-AUDIT-103 amendment): missing speaker_script.md
        causes main_handout to exit 2, not 0, with a 'Run /debrief:script
        first' stderr message."""
        _seed_handout_project(tmp_path)
        with pytest.raises(SystemExit) as excinfo:
            utility_skills.main_handout("2up", tmp_path)
        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "speaker_script.md is missing" in err
        assert "/debrief:script" in err

    def test_no_pdf_written_on_missing_script(
        self, tmp_path: Path
    ) -> None:
        """The handout subprocess does not partial-render when the
        precondition is violated."""
        _seed_handout_project(tmp_path)
        with pytest.raises(SystemExit):
            utility_skills.main_handout("2up", tmp_path)
        out_dir = tmp_path / "output" / "handouts"
        if out_dir.exists():
            assert not list(out_dir.glob("handout_v*.pdf"))


# ---------------------------------------------------------------------------
# (3) Consultant card has the Handout Generation Dispatch section.
# ---------------------------------------------------------------------------


class TestBugAudit103ConsultantCardHandoutDispatch:
    """`agents/consultant.md` documents the precondition self-heal."""

    @pytest.fixture(scope="class")
    def card_text(self) -> str:
        return _consultant_md_path().read_text()

    def test_handout_generation_dispatch_section_exists(self, card_text: str) -> None:
        assert "## Handout Generation Dispatch" in card_text, (
            "BC-5.16c (BUG-AUDIT-103): agents/consultant.md must contain "
            "a `## Handout Generation Dispatch` section."
        )

    def test_section_cites_bug_audit_103(self, card_text: str) -> None:
        lines = card_text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("## Handout Generation Dispatch"):
                window = "\n".join(lines[i : i + 3])
                assert "BUG-AUDIT-103" in window or "BC-5.16c" in window
                return
        pytest.fail("Handout Generation Dispatch section not found")

    def test_section_documents_precondition_self_heal(self, card_text: str) -> None:
        body = self._extract_section_body(card_text)
        # The precondition check must be named.
        assert "speaker_script.md" in body
        # The script-generation chain reference must be there.
        assert "build_script_prompt" in body or "script-generation" in body.lower() or "Script Generation Dispatch" in body
        # The hard-failure path message must appear.
        assert "/debrief:script" in body

    def test_section_states_credential_model(self, card_text: str) -> None:
        body = self._extract_section_body(card_text).lower()
        assert "anthropic_api_key" in body
        # Either "session credential" OR "OAuth" qualifies.
        assert "session credential" in body or "oauth" in body

    @staticmethod
    def _extract_section_body(text: str) -> str:
        lines = text.splitlines()
        body: list[str] = []
        in_section = False
        for line in lines:
            if line.startswith("## Handout Generation Dispatch"):
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if in_section:
                body.append(line)
        return "\n".join(body)


# ---------------------------------------------------------------------------
# (4) commands/handout.md describes the new flow.
# ---------------------------------------------------------------------------


class TestBugAudit103CommandsHandoutMd:
    """`commands/handout.md` reflects the BUG-AUDIT-103 amendment."""

    def test_describes_retired_auto_cascade(self) -> None:
        text = _commands_handout_md_path().read_text()
        assert "BUG-AUDIT-103" in text, (
            "commands/handout.md must reference BUG-AUDIT-103 in its "
            "preconditions section."
        )

    def test_documents_consultant_orchestration(self) -> None:
        text = _commands_handout_md_path().read_text()
        # The consultant's orchestration layer is the new home of the
        # precondition self-heal.
        assert "consultant" in text.lower()
        assert "speaker_script.md" in text

    def test_documents_exit_2_on_missing_script(self) -> None:
        text = _commands_handout_md_path().read_text()
        # The post-103 behavior is exit 2, not exit 0 — make sure the
        # docs name this so users know what to expect.
        assert "exit 2" in text.lower() or "exits 2" in text.lower()
