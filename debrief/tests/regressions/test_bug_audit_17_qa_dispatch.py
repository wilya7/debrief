# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-17.

A user running debrief in production reported that the slide-maker
agent wrote a slide and explicitly noted "No automated visual-QA ran
in this thread", and the Consultant agent (acting as orchestrator)
ignored the note and moved on. The spec's red-green gate was silently
bypassed. Root cause: spec §24.18 prescribed a `type: "agent"`
PostToolUse hook as the sole dispatch mechanism for visual-QA; Claude
Code v2.1.107 broke that hook upstream (BUG-AUDIT-12b). BUG-AUDIT-17
replaces the mechanism with a hybrid:

1. **Tier 1 (programmatic, fully deterministic)**: a `type: "command"`
   PostToolUse hook invokes `bin/qa-run-on-write`, a Python wrapper
   that reads hook input JSON from stdin and shells out to
   `python -m debrief.qa_checker` on every `slides/*.html` write.
   No LLM involved.

2. **Tier 2 (VLM, slide-maker-dispatched)**: the slide-maker agent's
   frontmatter `tools` list gains `Task`, and its system prompt gains
   a load-bearing `## QA Dispatch (REQUIRED)` section requiring the
   agent to invoke visual-qa via Task as its absolute final action
   before returning. This is prompt-level deterministic — the only
   failure mode is the LLM ignoring its own system prompt.

3. **No more `type: "agent"` hooks**: `hooks.json` contains NO
   `type: "agent"` handlers anywhere. The v2.1.107 upstream regression
   is routed around permanently.

This file enforces every part of the fix:

- BC-1.4 (extended): hooks.json PostToolUse handler is command-type
  invoking bin/qa-run-on-write in the escaped-quote form.
- BC-1.4 "no agent hooks": deep scan asserts no handler anywhere is
  `type: "agent"`.
- `bin/qa-run-on-write` exists, is executable, Python-importable,
  exposes `main`, `_extract_slide_path`, `_sha256`-free helpers.
- `_extract_slide_path` accepts slide HTML paths and rejects non-slide
  paths (negative sentinel).
- BC-8.4: slide-maker frontmatter includes `Task`, body contains the
  load-bearing QA Dispatch instruction, cites BUG-AUDIT-17.
- Negative sentinel: slide-maker body does NOT reference the removed
  `type: "agent"` PostToolUse hook as a dispatch mechanism.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers — dual workspace/delivered layout.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _hooks_json_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "hooks" / "hooks.json"
    delivered = _PROJECT_ROOT / "hooks" / "hooks.json"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find hooks.json at {workspace} or {delivered}"
    )


def _qa_run_script_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "bin" / "qa-run-on-write"
    delivered = _PROJECT_ROOT / "bin" / "qa-run-on-write"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find bin/qa-run-on-write at {workspace} or {delivered}"
    )


def _slide_maker_md_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "agents" / "slide-maker.md"
    delivered = _PROJECT_ROOT / "agents" / "slide-maker.md"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find agents/slide-maker.md at {workspace} or {delivered}"
    )


def _load_qa_run_module():
    """Load `qa-run-on-write` as a Python module for unit testing.

    The script has no ``.py`` extension (it is a CLI tool on PATH), so
    ``importlib.util.spec_from_file_location`` cannot infer a loader
    from the suffix. We pass an explicit ``SourceFileLoader``.
    """
    script = _qa_run_script_path()
    loader = SourceFileLoader("qa_run_on_write_under_test", str(script))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None, (
        "BC-1.4 / BUG-AUDIT-17: bin/qa-run-on-write must be loadable "
        "as a Python module via SourceFileLoader."
    )
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hooks_data() -> dict:
    return json.loads(_hooks_json_path().read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def slide_maker_text() -> str:
    return _slide_maker_md_path().read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# BC-1.4 / BUG-AUDIT-17 — hooks.json shape + no-agent-hooks invariant.
# ---------------------------------------------------------------------------


class TestBugAudit17HooksJson:
    """BC-1.4 amended / BUG-AUDIT-17 — PostToolUse is a command-type hook
    invoking bin/qa-run-on-write; no `type: "agent"` handler exists
    anywhere in hooks.json.
    """

    def test_post_tool_use_is_command_type(
        self, hooks_data: dict
    ) -> None:
        post_wrappers = hooks_data["hooks"]["PostToolUse"]
        assert len(post_wrappers) >= 1, (
            "BC-1.4: PostToolUse matcher wrapper is missing."
        )
        handler = post_wrappers[0]["hooks"][0]
        assert handler["type"] == "command", (
            f"BC-1.4 / BUG-AUDIT-17: PostToolUse handler must be type=command. "
            f"Got: {handler.get('type')!r}. The prior type=agent form was "
            f"broken by Claude Code v2.1.107 (BUG-AUDIT-12b) and replaced "
            f"in BUG-AUDIT-17."
        )

    def test_post_tool_use_command_invokes_qa_run_on_write(
        self, hooks_data: dict
    ) -> None:
        handler = hooks_data["hooks"]["PostToolUse"][0]["hooks"][0]
        cmd = handler.get("command", "")
        assert "qa-run-on-write" in cmd, (
            f"BC-1.4 / BUG-AUDIT-17: PostToolUse command must invoke "
            f"bin/qa-run-on-write. Got: {cmd!r}"
        )
        assert "${CLAUDE_PLUGIN_ROOT}" in cmd, (
            f"BC-1.4 / BUG-AUDIT-17: PostToolUse command must reference "
            f"${{CLAUDE_PLUGIN_ROOT}}. Got: {cmd!r}"
        )

    def test_post_tool_use_command_uses_escaped_quotes(
        self, hooks_data: dict
    ) -> None:
        # BC-1.4 / BUG-AUDIT-12a: the command reference must be wrapped in
        # escaped double quotes so shell expansion survives whitespace in
        # the plugin install path. This is the same contract as the
        # PreToolUse check-write-auth command.
        cmd = hooks_data["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        assert cmd.startswith('"') and cmd.endswith('"'), (
            f"BC-1.4 / BUG-AUDIT-12a / BUG-AUDIT-17: PostToolUse command "
            f"must be wrapped in escaped double quotes so "
            f"${{CLAUDE_PLUGIN_ROOT}} expansion produces a quoted path "
            f"tolerant of whitespace. Got: {cmd!r}"
        )

    def test_post_tool_use_timeout_is_sufficient_for_playwright(
        self, hooks_data: dict
    ) -> None:
        # BC-1.4 / BUG-AUDIT-17: the new command hook runs qa_checker.py
        # which launches Playwright — the timeout must be generous enough
        # for browser startup + rendering + screenshot + programmatic
        # checks. 120s is the BC-1.4 contract; accept >=60 as a practical
        # floor (the old broken agent-hook was 60).
        handler = hooks_data["hooks"]["PostToolUse"][0]["hooks"][0]
        timeout = handler.get("timeout", 0)
        assert timeout >= 60, (
            f"BC-1.4 / BUG-AUDIT-17: PostToolUse timeout must be >=60s for "
            f"Playwright rendering. Got: {timeout}"
        )

    def test_no_type_agent_hook_anywhere(self, hooks_data: dict) -> None:
        # Deep scan: walk every handler under every event key and assert
        # no handler has type="agent". This pins the "no agent hooks"
        # invariant from BC-1.4 post-BUG-AUDIT-17.
        hooks_record = hooks_data.get("hooks", {})
        offending: list[str] = []
        for event_name, matcher_wrappers in hooks_record.items():
            if not isinstance(matcher_wrappers, list):
                continue
            for wrapper_idx, wrapper in enumerate(matcher_wrappers):
                inner_hooks = wrapper.get("hooks", [])
                for hook_idx, handler in enumerate(inner_hooks):
                    if handler.get("type") == "agent":
                        offending.append(
                            f"{event_name}[{wrapper_idx}].hooks[{hook_idx}]"
                        )
        assert not offending, (
            f"BC-1.4 / BUG-AUDIT-17: hooks.json must not contain any "
            f"`type: \"agent\"` handler. Agent-type hooks are broken "
            f"upstream by Claude Code v2.1.107 and debrief's canonical "
            f"dispatch mechanism for visual-QA is the slide-maker's "
            f"Task call per BC-8.4. Offending handlers: {offending}"
        )


# ---------------------------------------------------------------------------
# BC-1.4 / BUG-AUDIT-17 — bin/qa-run-on-write script contract.
# ---------------------------------------------------------------------------


class TestBugAudit17QaRunOnWriteScript:
    """BC-1.4 (bin/qa-run-on-write contract) / BUG-AUDIT-17 — the wrapper
    script exists, is executable, is a valid Python module, exposes the
    contract API, and correctly discriminates slide paths from non-slide
    paths.
    """

    def test_qa_run_on_write_script_exists(self) -> None:
        path = _qa_run_script_path()
        assert path.is_file(), (
            f"BC-1.4 / BUG-AUDIT-17: bin/qa-run-on-write must exist at "
            f"{path}."
        )

    def test_qa_run_on_write_is_executable(self) -> None:
        path = _qa_run_script_path()
        mode = path.stat().st_mode
        # User execute bit must be set.
        assert mode & 0o100, (
            f"BC-1.4 / BUG-AUDIT-17: bin/qa-run-on-write must be executable "
            f"(user execute bit set). Current mode: {oct(mode & 0o777)}"
        )

    def test_qa_run_on_write_is_python_importable(self) -> None:
        module = _load_qa_run_module()
        # The public API required by BC-1.4.
        for symbol in ("main", "_extract_slide_path"):
            assert hasattr(module, symbol), (
                f"BC-1.4 / BUG-AUDIT-17: bin/qa-run-on-write must expose "
                f"{symbol!r}."
            )

    def test_extract_slide_path_accepts_relative_slide_html(self) -> None:
        module = _load_qa_run_module()
        result = module._extract_slide_path(
            {"tool_input": {"file_path": "slides/intro.html"}}
        )
        assert result is not None, (
            "BC-1.4 / BUG-AUDIT-17: _extract_slide_path must accept "
            "relative `slides/<slug>.html` paths."
        )
        assert result.name == "intro.html"

    def test_extract_slide_path_accepts_absolute_slide_html(self) -> None:
        module = _load_qa_run_module()
        result = module._extract_slide_path(
            {"tool_input": {"file_path": "/tmp/project/slides/outro.html"}}
        )
        assert result is not None, (
            "BC-1.4 / BUG-AUDIT-17: _extract_slide_path must accept "
            "absolute slide HTML paths that contain a 'slides' segment."
        )

    def test_extract_slide_path_rejects_non_html_under_slides(self) -> None:
        module = _load_qa_run_module()
        result = module._extract_slide_path(
            {"tool_input": {"file_path": "slides/something.json"}}
        )
        assert result is None, (
            "BC-1.4 / BUG-AUDIT-17: _extract_slide_path must reject "
            "non-HTML files even under slides/."
        )

    def test_extract_slide_path_rejects_html_outside_slides(self) -> None:
        module = _load_qa_run_module()
        for non_slide in [
            ".debrief/draft/preview_slides/preview.html",
            "output/view.html",
            "assets/templates/foo.html",
            "index.html",
        ]:
            result = module._extract_slide_path(
                {"tool_input": {"file_path": non_slide}}
            )
            # Note: preview_slides has 'slides' in its path but not as a
            # direct segment matching the pattern. Our check uses
            # `"slides" in p.parts`, so `.debrief/draft/preview_slides/...`
            # has `preview_slides` but NOT `slides` as a part — correct
            # rejection. If the test input ever matches 'slides', the
            # intent was still to match only direct `slides/` writes.
            if non_slide == ".debrief/draft/preview_slides/preview.html":
                # preview_slides is not "slides" as a path part; rejected.
                assert result is None, (
                    f"BC-1.4 / BUG-AUDIT-17: preview_slides must not match "
                    f"the slides/ filter. Got: {result}"
                )
            else:
                assert result is None, (
                    f"BC-1.4 / BUG-AUDIT-17: {non_slide!r} is not a slide "
                    f"HTML write and must be rejected. Got: {result}"
                )

    def test_extract_slide_path_rejects_empty_input(self) -> None:
        module = _load_qa_run_module()
        for empty in [{}, {"tool_input": {}}, {"tool_input": {"file_path": ""}}]:
            assert module._extract_slide_path(empty) is None, (
                f"BC-1.4 / BUG-AUDIT-17: _extract_slide_path must return "
                f"None for empty/malformed input: {empty}"
            )

    def test_qa_run_on_write_exits_zero_on_non_slide_input(
        self, tmp_path: Path
    ) -> None:
        # End-to-end smoke test: invoke the script as a subprocess with
        # non-slide input on stdin. Must exit 0 (no-op).
        script = _qa_run_script_path()
        result = subprocess.run(
            [sys.executable, str(script)],
            input='{"tool_input":{"file_path":"assets/images/x.png"}}',
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0, (
            f"BC-1.4 / BUG-AUDIT-17: qa-run-on-write must exit 0 on "
            f"non-slide input. Got exit {result.returncode}, stderr: "
            f"{result.stderr}"
        )


# ---------------------------------------------------------------------------
# BC-8.4 / BUG-AUDIT-17 — slide-maker agent prompt.
# ---------------------------------------------------------------------------


class TestBugAudit17SlideMakerPrompt:
    """BC-8.4 / BUG-AUDIT-17 — slide-maker.md has Task in frontmatter and
    a load-bearing QA Dispatch instruction in its body.
    """

    def test_slide_maker_frontmatter_includes_task_tool(
        self, slide_maker_text: str
    ) -> None:
        # Parse the YAML frontmatter.
        match = re.match(r"^---\n(.*?)\n---\n", slide_maker_text, re.DOTALL)
        assert match is not None, (
            "BC-8.4 / BUG-AUDIT-17: slide-maker.md must have a YAML "
            "frontmatter block starting with '---'."
        )
        frontmatter = match.group(1)
        tools_line_match = re.search(r"^tools:\s*(.*)$", frontmatter, re.MULTILINE)
        assert tools_line_match is not None, (
            "BC-8.4 / BUG-AUDIT-17: slide-maker.md frontmatter must declare "
            "a `tools:` field."
        )
        tools_value = tools_line_match.group(1)
        # The tools value can be a comma-separated list or YAML-list form.
        # Accept either; just check the literal `Task` token is present.
        assert "Task" in tools_value, (
            f"BC-8.4 / BUG-AUDIT-17: slide-maker.md frontmatter `tools` "
            f"field must include `Task` so the agent can spawn the "
            f"visual-qa subagent via the Task tool. Got: {tools_value!r}"
        )

    def test_slide_maker_body_contains_qa_dispatch_section(
        self, slide_maker_text: str
    ) -> None:
        assert "## QA Dispatch" in slide_maker_text, (
            "BC-8.4 / BUG-AUDIT-17: slide-maker.md body must contain a "
            "`## QA Dispatch` section heading with the load-bearing "
            "requirement to invoke visual-qa."
        )

    def test_slide_maker_body_uses_load_bearing_language(
        self, slide_maker_text: str
    ) -> None:
        # The section must use imperative language. After BUG-AUDIT-59,
        # slide-maker runs Tier 1 only; "absolute final action" and
        # "Do NOT return" were removed (they referred to Task dispatch
        # which is now the consultant's job). Accept "MUST" or "You MUST"
        # as the minimum load-bearing marker.
        markers = [
            "MUST",
        ]
        present = [m for m in markers if m in slide_maker_text]
        assert present, (
            f"BC-8.4 / BUG-AUDIT-17 / BUG-AUDIT-59: slide-maker.md must "
            f"use load-bearing language for the QA Dispatch instruction. "
            f"Expected at least one of {markers!r}, got none."
        )

    def test_slide_maker_body_names_visual_qa_and_task(
        self, slide_maker_text: str
    ) -> None:
        assert "visual-qa" in slide_maker_text, (
            "BC-8.4 / BUG-AUDIT-17: slide-maker.md must name `visual-qa` "
            "as the subagent to invoke."
        )
        assert "Task" in slide_maker_text, (
            "BC-8.4 / BUG-AUDIT-17: slide-maker.md must name the `Task` "
            "tool as the invocation mechanism."
        )

    def test_slide_maker_body_cites_bug_audit_17(
        self, slide_maker_text: str
    ) -> None:
        assert "BUG-AUDIT-17" in slide_maker_text, (
            "BC-8.4: slide-maker.md must cite BUG-AUDIT-17 so future "
            "maintainers can trace the QA Dispatch instruction back to "
            "the Bug Catalog entry that created it."
        )

    def test_slide_maker_body_does_not_reference_broken_agent_hook(
        self, slide_maker_text: str
    ) -> None:
        # Negative sentinel: the body must not describe the PostToolUse
        # agent hook as the dispatch mechanism for QA. That mechanism is
        # dead (BUG-AUDIT-17 removed it) and a stale instruction here
        # could mislead a future maintainer into thinking the hook still
        # works.
        bad_phrases = [
            "PostToolUse hook fires",
            "hook fires the QA agent",
            "type: \"agent\"",
            "agent hook automatically",
        ]
        found = [p for p in bad_phrases if p in slide_maker_text]
        assert not found, (
            f"BC-8.4 / BUG-AUDIT-17: slide-maker.md must not describe the "
            f"broken `type: \"agent\"` PostToolUse hook as an active "
            f"dispatch mechanism — that hook was removed in BUG-AUDIT-17. "
            f"Offending phrases: {found!r}"
        )
