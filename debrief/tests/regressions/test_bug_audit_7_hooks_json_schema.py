# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-7.

Bug: `hooks/hooks.json` had event keys (`PreToolUse`, `PostToolUse`) at
the top level directly, with each event mapping to a flat list of
records. Claude Code's plugin hooks Zod schema requires Form B: a
top-level `hooks` record whose value is an object keyed by event names,
whose values are arrays of **matcher wrappers**. Each matcher wrapper
has a `matcher` string field and a nested `hooks` array of handler
dicts. The committed file did not wrap the event map in `hooks` at all,
so Claude Code rejected it with `expected record, received undefined`
at path `["hooks"]`.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-7,
spec §7.1 (which already showed the correct Form B), and blueprint
BC-1.4 (amended to require Form B).

The negative sentinel in `test_hooks_json_has_no_top_level_event_keys`
is the regression guard. Any future edit that reverts to the flat
top-level layout fails it immediately.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _hooks_json_path() -> Path:
    workspace_candidate = _PROJECT_ROOT / "src" / "unit_1" / "hooks" / "hooks.json"
    delivered_candidate = _PROJECT_ROOT / "hooks" / "hooks.json"
    for candidate in (workspace_candidate, delivered_candidate):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find hooks.json at {workspace_candidate} or {delivered_candidate}"
    )


# Conservative whitelist of Claude Code plugin hook event names. Any event
# outside this set in hooks.json either reflects a new event type (in which
# case this test fails and we update the list) or a typo (which we want to
# catch). Authoritative reference: code.claude.com/docs/en/plugins-reference.md.
_VALID_HOOK_EVENTS = {
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "SessionStart",
    "Notification",
    "UserPromptSubmit",
    "PreCompact",
    "SubagentStop",
}


@pytest.fixture(scope="module")
def hooks_data() -> dict:
    return json.loads(_hooks_json_path().read_text())


# ---------------------------------------------------------------------------
# BUG-AUDIT-7 regression tests.
# ---------------------------------------------------------------------------


class TestBugAudit7HooksJsonSchema:
    """BC-1.4 Form B: top-level `hooks` record + matcher wrappers (BUG-AUDIT-7)."""

    def test_hooks_json_parses_as_valid_json(self) -> None:
        json.loads(_hooks_json_path().read_text())

    def test_hooks_json_has_top_level_hooks_key(self, hooks_data: dict) -> None:
        assert "hooks" in hooks_data, (
            "BUG-AUDIT-7: hooks.json must have a top-level `hooks` key. "
            "Its absence produces the Zod error: "
            "`expected record, received undefined` at path `[\"hooks\"]`."
        )
        assert isinstance(hooks_data["hooks"], dict), (
            f"BC-1.4: top-level `hooks` must be a record (object), got "
            f"{type(hooks_data['hooks']).__name__}."
        )

    def test_hooks_json_has_no_top_level_event_keys(self, hooks_data: dict) -> None:
        # Negative sentinel: if anyone reverts to the flat top-level layout,
        # this fires immediately.
        top_level_event_keys = set(hooks_data.keys()) & _VALID_HOOK_EVENTS
        assert not top_level_event_keys, (
            f"BUG-AUDIT-7 regression: hooks.json has event keys at the top "
            f"level: {sorted(top_level_event_keys)}. Event keys must live "
            f"inside the top-level `hooks` record (Form B). See BC-1.4."
        )

    def test_hooks_inner_is_record_of_events(self, hooks_data: dict) -> None:
        inner = hooks_data["hooks"]
        assert isinstance(inner, dict) and len(inner) > 0, (
            "BC-1.4: `hooks_data['hooks']` must be a non-empty record of events."
        )
        unknown = set(inner.keys()) - _VALID_HOOK_EVENTS
        assert not unknown, (
            f"BC-1.4: unknown event keys in hooks.json: {sorted(unknown)}. "
            f"Valid events per Claude Code plugin schema: {sorted(_VALID_HOOK_EVENTS)}."
        )

    def test_hooks_pre_tool_use_is_list_of_matcher_wrappers(
        self, hooks_data: dict
    ) -> None:
        pre_tool_use = hooks_data["hooks"].get("PreToolUse")
        assert isinstance(pre_tool_use, list) and len(pre_tool_use) > 0, (
            "BC-1.4: `hooks.PreToolUse` must be a non-empty list of matcher wrappers."
        )
        for wrapper in pre_tool_use:
            assert isinstance(wrapper, dict), (
                f"BC-1.4: each PreToolUse element must be a dict, got {type(wrapper).__name__}."
            )
            assert "matcher" in wrapper and isinstance(wrapper["matcher"], str), (
                "BC-1.4: each PreToolUse matcher wrapper must have a `matcher` string field."
            )
            assert "hooks" in wrapper and isinstance(wrapper["hooks"], list), (
                "BC-1.4: each PreToolUse matcher wrapper must have a `hooks` array of handlers."
            )

    def test_hooks_post_tool_use_is_list_of_matcher_wrappers(
        self, hooks_data: dict
    ) -> None:
        post_tool_use = hooks_data["hooks"].get("PostToolUse")
        assert isinstance(post_tool_use, list) and len(post_tool_use) > 0, (
            "BC-1.4: `hooks.PostToolUse` must be a non-empty list of matcher wrappers."
        )
        for wrapper in post_tool_use:
            assert isinstance(wrapper, dict)
            assert "matcher" in wrapper and isinstance(wrapper["matcher"], str)
            assert "hooks" in wrapper and isinstance(wrapper["hooks"], list)

    def test_pre_tool_use_matcher_is_write_or_edit(self, hooks_data: dict) -> None:
        pre_tool_use = hooks_data["hooks"]["PreToolUse"]
        matchers = [w["matcher"] for w in pre_tool_use]
        assert any(m == "Write|Edit" for m in matchers), (
            f"BC-1.4: PreToolUse matcher must be `Write|Edit`; found: {matchers}"
        )

    def test_pre_tool_use_inner_hook_is_command_type_with_check_write_auth(
        self, hooks_data: dict
    ) -> None:
        wrappers = hooks_data["hooks"]["PreToolUse"]
        write_edit_wrapper = next(
            (w for w in wrappers if w["matcher"] == "Write|Edit"), None
        )
        assert write_edit_wrapper is not None, "Write|Edit wrapper missing."
        inner_hooks = write_edit_wrapper["hooks"]
        assert len(inner_hooks) > 0, "PreToolUse Write|Edit wrapper has no inner hooks."
        handler = inner_hooks[0]
        assert handler.get("type") == "command", (
            f"BC-1.4: PreToolUse inner hook must be type=command; got {handler.get('type')!r}."
        )
        command = handler.get("command", "")
        assert "check-write-auth" in command, (
            f"BC-1.4: PreToolUse command must reference check-write-auth; got {command!r}."
        )
        assert "${CLAUDE_PLUGIN_ROOT}" in command, (
            f"BC-1.4: PreToolUse command must use ${{CLAUDE_PLUGIN_ROOT}} expansion."
        )
        assert handler.get("timeout") == 10, (
            f"BC-1.4: PreToolUse timeout must be 10; got {handler.get('timeout')!r}."
        )

    def test_post_tool_use_inner_hook_is_command_type_per_bug_audit_17(
        self, hooks_data: dict
    ) -> None:
        # BC-1.4 extended (BUG-AUDIT-17): the PostToolUse handler was
        # originally type="agent" with an inline `prompt`. Claude Code
        # v2.1.107 broke that form upstream with the "Messages are
        # required for agent hooks" assertion (BUG-AUDIT-12b), and
        # BUG-AUDIT-17 replaced it with a type="command" handler that
        # invokes bin/qa-run-on-write. See spec §24.18 and Bug Catalog
        # entry BUG-AUDIT-17 for the full architectural write-up.
        wrappers = hooks_data["hooks"]["PostToolUse"]
        write_edit_wrapper = next(
            (w for w in wrappers if w["matcher"] == "Write|Edit"), None
        )
        assert write_edit_wrapper is not None, "Write|Edit wrapper missing in PostToolUse."
        inner_hooks = write_edit_wrapper["hooks"]
        assert len(inner_hooks) > 0, "PostToolUse Write|Edit wrapper has no inner hooks."
        handler = inner_hooks[0]
        assert handler.get("type") == "command", (
            f"BC-1.4 / BUG-AUDIT-17: PostToolUse inner hook must be "
            f"type=command; got {handler.get('type')!r}. The prior "
            f"type=agent form was broken by Claude Code v2.1.107 upstream."
        )
        command = handler.get("command", "")
        assert isinstance(command, str) and command.strip(), (
            "BC-1.4 / BUG-AUDIT-17: PostToolUse command handler must have "
            "a non-empty `command` field."
        )
        assert "qa-run-on-write" in command, (
            f"BC-1.4 / BUG-AUDIT-17: PostToolUse command must invoke "
            f"bin/qa-run-on-write; got {command!r}."
        )
        assert handler.get("timeout", 0) >= 60, (
            f"BC-1.4 / BUG-AUDIT-17: PostToolUse timeout must be >= 60s "
            f"for Playwright rendering; got {handler.get('timeout')!r}."
        )

    def test_hooks_json_loads_without_claude_code_zod_error(
        self, hooks_data: dict
    ) -> None:
        # Redundant with test_hooks_json_has_top_level_hooks_key, but
        # includes the exact Zod error string for future-diagnosis grep.
        #
        # If Claude Code reports: `expected record, received undefined`
        # at path `["hooks"]`, it means this assertion is false.
        assert isinstance(hooks_data.get("hooks"), dict), (
            "BUG-AUDIT-7: hooks.json top-level `hooks` key must be a record. "
            "Absence produces: `expected record, received undefined` at path `[\"hooks\"]`."
        )
