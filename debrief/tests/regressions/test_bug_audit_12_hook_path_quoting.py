# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-12.

Bug 12a (fixed): `hooks.json` PreToolUse command was
`"${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth"` (unquoted). When
`${CLAUDE_PLUGIN_ROOT}` expanded to a path with whitespace (the plugin
is installed under `/Users/.../Nextcloud/coding projects/...`), `/bin/sh`
split the path on whitespace and failed. Fix: wrap the command
reference in escaped double quotes inside the JSON string so the
shell receives a quoted path token.

Bug 12b (upstream, not fixed on our side): Claude Code v2.1.107's hook
runner raises "Messages are required for agent hooks. This is a bug."
for the PostToolUse agent-type handler. Our hook entry matches the
documented schema verbatim (`prompt` field per
code.claude.com/docs/en/hooks.md). The `messages` field the runner
expects is NOT documented. This test file preserves the `prompt` form
as a load-bearing invariant so a future well-meaning edit cannot
replace it with an undocumented `messages` guess. See `hooks/README.md`
and spec Bug Catalog entry BUG-AUDIT-12b.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers.
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


def _hooks_readme_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "hooks" / "README.md"
    delivered = _PROJECT_ROOT / "hooks" / "README.md"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find hooks/README.md at {workspace} or {delivered}"
    )


@pytest.fixture(scope="module")
def hooks_data() -> dict:
    return json.loads(_hooks_json_path().read_text())


@pytest.fixture(scope="module")
def hooks_json_text() -> str:
    return _hooks_json_path().read_text()


# ---------------------------------------------------------------------------
# BUG-AUDIT-12a regression tests (PreToolUse command path quoting).
# ---------------------------------------------------------------------------


class TestBugAudit12HookPathQuoting:
    """BC-1.4 / BUG-AUDIT-12a — PreToolUse command path must be wrapped
    in escaped double quotes so shell expansion survives whitespace.
    BC-1.4 / BUG-AUDIT-12b — PostToolUse agent hook must keep the
    documented `prompt` field (do not replace with undocumented
    `messages` as a workaround for the v2.1.107 upstream regression).
    """

    def test_pre_tool_use_command_is_wrapped_in_escaped_double_quotes(
        self, hooks_data: dict
    ) -> None:
        pre_wrappers = hooks_data["hooks"]["PreToolUse"]
        assert len(pre_wrappers) >= 1, (
            "BC-1.4: PreToolUse matcher wrapper is missing."
        )
        handler = pre_wrappers[0]["hooks"][0]
        cmd = handler["command"]
        assert cmd.startswith('"') and cmd.endswith('"'), (
            f"BC-1.4 / BUG-AUDIT-12a: PreToolUse command must be wrapped in "
            f"escaped double quotes so `${{CLAUDE_PLUGIN_ROOT}}` expansion "
            f"produces a quoted path tolerant of whitespace in the plugin "
            f"install path. Got: {cmd!r}"
        )

    def test_pre_tool_use_command_references_check_write_auth(
        self, hooks_data: dict
    ) -> None:
        cmd = hooks_data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert "${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth" in cmd, (
            f"BC-1.4: PreToolUse command must reference "
            f"`${{CLAUDE_PLUGIN_ROOT}}/bin/check-write-auth`. Got: {cmd!r}"
        )

    def test_no_unquoted_plugin_root_command_in_raw_json(
        self, hooks_json_text: str
    ) -> None:
        # BUG-AUDIT-12a negative sentinel. The legacy unquoted form
        # `"command": "${CLAUDE_PLUGIN_ROOT}/..."` must not appear in the
        # raw JSON. The valid form has an escaped quote before the `$`:
        # `"command": "\"${CLAUDE_PLUGIN_ROOT}/..."`. We check for the
        # absence of `"command": "$` (unquoted). The regex allows optional
        # whitespace between `:` and the opening quote of the value.
        legacy_pattern = re.compile(r'"command"\s*:\s*"\$\{CLAUDE_PLUGIN_ROOT\}')
        assert not legacy_pattern.search(hooks_json_text), (
            "BUG-AUDIT-12a regression: an unquoted `${CLAUDE_PLUGIN_ROOT}` "
            "command appeared in hooks.json. The command reference must be "
            "wrapped in escaped double quotes so the shell receives a quoted "
            "path token after variable expansion. See BC-1.4 and BUG-AUDIT-12a."
        )

    def test_post_tool_use_agent_hook_still_uses_prompt_field(
        self, hooks_data: dict
    ) -> None:
        # BC-1.4 / BUG-AUDIT-12b: the PostToolUse agent hook must retain
        # the documented `prompt` field. Claude Code v2.1.107 has a regression
        # in its hook runner that raises "Messages are required for agent
        # hooks. This is a bug." even though the documented schema at
        # code.claude.com/docs/en/hooks.md requires only `prompt`. Do NOT
        # "fix" the error by replacing `prompt` with an undocumented
        # `messages` field — that would be a guess at a schema that is not
        # published, and risks future breakage if Claude Code tightens
        # validation.
        post_wrappers = hooks_data["hooks"]["PostToolUse"]
        assert len(post_wrappers) >= 1, (
            "BC-1.4: PostToolUse matcher wrapper is missing."
        )
        handler = post_wrappers[0]["hooks"][0]
        assert handler["type"] == "agent", (
            "BC-1.4: PostToolUse inner hook must be type=agent per spec §7.3."
        )
        assert "prompt" in handler and isinstance(handler["prompt"], str), (
            "BC-1.4 / BUG-AUDIT-12b: PostToolUse agent hook must use the "
            "documented `prompt` field. The v2.1.107 'Messages are required' "
            "error is a Claude Code upstream regression, not a plugin bug. "
            "See hooks/README.md and spec BUG-AUDIT-12b."
        )
        assert handler["prompt"].strip(), (
            "BC-1.4: PostToolUse prompt must be non-empty."
        )


# ---------------------------------------------------------------------------
# BUG-AUDIT-12b documentation tests (hooks/README.md).
# ---------------------------------------------------------------------------


class TestBugAudit12HooksReadme:
    """BUG-AUDIT-12b — hooks/README.md must document the v2.1.107
    PostToolUse agent-hook regression so future maintainers don't
    try to 'fix' it by replacing `prompt` with undocumented schema.
    """

    def test_hooks_readme_exists(self) -> None:
        # Just verify it's findable in either workspace or delivered layout.
        path = _hooks_readme_path()
        assert path.is_file(), (
            f"BUG-AUDIT-12b: hooks/README.md must exist at {path} "
            f"documenting the known v2.1.107 PostToolUse agent-hook regression."
        )

    def test_hooks_readme_documents_v2_1_107_regression(self) -> None:
        content = _hooks_readme_path().read_text()
        assert "v2.1.107" in content, (
            "BUG-AUDIT-12b: hooks/README.md must mention the Claude Code "
            "version (v2.1.107) where the regression first appeared."
        )
        assert "PostToolUse" in content, (
            "BUG-AUDIT-12b: hooks/README.md must mention the affected hook "
            "event (PostToolUse)."
        )
        assert "Messages are required" in content, (
            "BUG-AUDIT-12b: hooks/README.md must quote the exact error "
            "message 'Messages are required' so grep-based debugging finds it."
        )

    def test_hooks_readme_advises_against_replacing_prompt(self) -> None:
        content = _hooks_readme_path().read_text()
        # Check for the guidance that replacing `prompt` with `messages` is
        # the wrong fix. Allow either phrasing.
        assert "messages" in content.lower() and "prompt" in content.lower(), (
            "BUG-AUDIT-12b: hooks/README.md should explicitly advise against "
            "replacing `prompt` with an undocumented `messages` field."
        )
