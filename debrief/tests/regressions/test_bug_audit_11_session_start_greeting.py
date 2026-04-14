# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-11.

Bug: the consultant agent was silent on session start. `src/unit_3/launcher.py`
wrote `debrief_state.json` with `sub_phase: "discovery/greeting"`, and the
routing table in `src/unit_4/routing.py` mapped that to a human gate — but
nothing dispatched the gate. The project CLAUDE.md template had no
orchestration instructions, no SessionStart hook existed, and Claude Code
agents don't auto-emit messages before user input. The consultant was
loaded but silent.

Fix: (a) added a `## On Session Start` section to
`templates/project_claude.md` instructing the consultant to read state
files and dispatch on the first user turn, (b) added a visible terminal
message in `bin/debrief` before `exec claude` to tell the user to say
"hi" to begin. See `spec/stakeholder_spec.md` Bug Catalog entry
BUG-AUDIT-11 and blueprint BC-3.6a.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _bin_debrief_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "bin" / "debrief"
    delivered = _PROJECT_ROOT / "bin" / "debrief"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find bin/debrief at {workspace} or {delivered}"
    )


def _project_claude_md_template_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "templates" / "project_claude.md"
    delivered = _PROJECT_ROOT / "templates" / "project_claude.md"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find project_claude.md at {workspace} or {delivered}"
    )


def _hooks_json_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "hooks" / "hooks.json"
    delivered = _PROJECT_ROOT / "hooks" / "hooks.json"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find hooks.json at {workspace} or {delivered}"
    )


@pytest.fixture(scope="module")
def bin_debrief_text() -> str:
    return _bin_debrief_path().read_text()


@pytest.fixture(scope="module")
def template_text() -> str:
    return _project_claude_md_template_path().read_text()


@pytest.fixture(scope="module")
def hooks_json_text() -> str:
    return _hooks_json_path().read_text()


# ---------------------------------------------------------------------------
# BUG-AUDIT-11 regression tests.
# ---------------------------------------------------------------------------


class TestBugAudit11SessionStartGreeting:
    """BC-3.6a template content + bin/debrief terminal cue."""

    # --- Template content tests ---------------------------------------------

    def test_template_has_on_session_start_section(self, template_text: str) -> None:
        assert "## On Session Start" in template_text, (
            "BC-3.6a / BUG-AUDIT-11: project_claude.md template must contain "
            "a `## On Session Start` section with orchestration instructions "
            "for the consultant agent."
        )

    def test_template_references_debrief_state_json(
        self, template_text: str
    ) -> None:
        assert "debrief_state.json" in template_text, (
            "BC-3.6a / BUG-AUDIT-11: On Session Start section must reference "
            "`debrief_state.json` so the consultant knows which file to read."
        )

    def test_template_references_deck_state_json(self, template_text: str) -> None:
        assert "deck_state.json" in template_text, (
            "BC-3.6a / BUG-AUDIT-11: On Session Start section must reference "
            "`deck_state.json` so the consultant can read the archetype for "
            "the greeting."
        )

    def test_template_references_sub_phase_dispatch(
        self, template_text: str
    ) -> None:
        assert "sub_phase" in template_text, (
            "BC-3.6a / BUG-AUDIT-11: On Session Start section must describe "
            "dispatch by `sub_phase`."
        )

    def test_template_documents_discovery_greeting_dispatch(
        self, template_text: str
    ) -> None:
        # The critical dispatch arm: when sub_phase is discovery/greeting,
        # the consultant must emit the archetype-aware REQ-CONSULT-1 greeting.
        assert "discovery/greeting" in template_text, (
            "BC-3.6a / BUG-AUDIT-11: On Session Start section must document "
            "the `discovery/greeting` sub_phase dispatch, which triggers the "
            "REQ-CONSULT-1 archetype greeting."
        )

    def test_template_tells_agent_to_interpret_hi_as_dispatch(
        self, template_text: str
    ) -> None:
        # The instructions must explicitly tell the consultant that a bare
        # "hi" / "start" / short greeting is a dispatch request, not a
        # request for a generic greeting. Otherwise the consultant might
        # respond "Hello! How can I help?" instead of dispatching.
        content_lower = template_text.lower()
        has_hi_instruction = "hi" in content_lower and "start" in content_lower
        assert has_hi_instruction, (
            "BC-3.6a / BUG-AUDIT-11: On Session Start section must tell the "
            "consultant to interpret a first-turn 'hi' or 'start' as a "
            "dispatch request, not a generic greeting."
        )

    # --- bin/debrief terminal cue tests -------------------------------------

    def test_bin_debrief_prints_greeting_cue_before_exec_claude(
        self, bin_debrief_text: str
    ) -> None:
        # BUG-AUDIT-11: bin/debrief must print a visible "say hi to begin"
        # message before exec claude so the user knows they need to type
        # something to trigger the consultant.
        assert "hi" in bin_debrief_text.lower(), (
            "BUG-AUDIT-11: bin/debrief must print a terminal cue telling the "
            "user to say 'hi' to begin the consultation. See BC-3.6a."
        )
        assert "Debrief ready" in bin_debrief_text, (
            "BUG-AUDIT-11: bin/debrief terminal cue should begin with "
            "'Debrief ready' so it's recognizable."
        )

    def test_bin_debrief_greeting_cue_uses_stderr(
        self, bin_debrief_text: str
    ) -> None:
        # The greeting cue must be routed to stderr (`>&2`) so it survives
        # through `exec claude` (which takes over stdout). Without stderr
        # routing, the user might not see the message depending on terminal
        # buffering.
        assert ">&2" in bin_debrief_text, (
            "BUG-AUDIT-11: bin/debrief greeting cue must be routed to stderr "
            "(`>&2`) so it's visible before exec claude."
        )

    def test_greeting_cue_function_called_in_both_dispatch_arms(
        self, bin_debrief_text: str
    ) -> None:
        # The greeting cue helper must be called in both the `new)` arm and
        # the bare `""` arm of the step 9 dispatch, right before `exec claude`.
        # We check for the helper function name and its invocation count.
        assert "_debrief_print_greeting_prompt" in bin_debrief_text, (
            "BUG-AUDIT-11: bin/debrief should define a helper function like "
            "`_debrief_print_greeting_prompt` to print the terminal cue."
        )
        # Expected: 1 function definition + 2 invocations = 3 occurrences.
        occurrences = bin_debrief_text.count("_debrief_print_greeting_prompt")
        assert occurrences == 3, (
            f"BUG-AUDIT-11: `_debrief_print_greeting_prompt` must appear "
            f"exactly 3 times in bin/debrief (1 definition + 2 invocations "
            f"in the new and bare dispatch arms). Found {occurrences}."
        )

    # --- Negative sentinel: we did NOT add a SessionStart hook --------------

    def test_hooks_json_has_no_session_start_hook(
        self, hooks_json_text: str
    ) -> None:
        # BUG-AUDIT-11 deliberately did NOT add a SessionStart hook, because
        # Claude Code agents don't auto-emit messages before user input, and
        # a SessionStart hook with type="command" or type="agent" cannot
        # produce visible output that prompts the main agent to greet first.
        # The CLAUDE.md-instruction pattern is simpler and matches SVP's
        # proven approach.
        #
        # If a future change adds a SessionStart hook, update this test
        # and document the reason in a new BUG-AUDIT entry.
        assert "SessionStart" not in hooks_json_text, (
            "BUG-AUDIT-11: hooks.json must not contain a SessionStart hook. "
            "The fix uses the project CLAUDE.md's `## On Session Start` "
            "section as the trigger mechanism. If you're adding a "
            "SessionStart hook for a different reason, update this test "
            "and document the rationale."
        )
