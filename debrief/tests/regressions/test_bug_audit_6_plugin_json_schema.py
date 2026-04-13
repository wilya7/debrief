# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-6.

Bug: `plugin.json` had `author` as a plain string and declared
`skills`, `agents`, `hooks` as string paths. Both violate Claude Code's
plugin manifest Zod schema:

  author: expected object, received string
  agents: Invalid input  [truncated, same applies to skills/hooks]

The correct schema (authoritative: code.claude.com/docs/en/plugins-reference.md)
requires `author` as an object and auto-discovers skills/agents/hooks from
their default subdirectories — they MUST NOT be declared as string paths.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-6 and
blueprint contracts BC-1.1 (rewritten) and BC-1.2/1.3/1.4 (reframed).

The negative sentinels (tests 3, 4, 5, 6) are the key regression guard —
any future edit that reintroduces a forbidden top-level key fails them
immediately, before the broken manifest can reach Claude Code.
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


def _plugin_root() -> Path:
    """Return the plugin root in whichever layout we are in.

    Workspace layout: src/unit_1/
    Delivered layout: the plugin root itself (the dir containing
    .claude-plugin/plugin.json at the delivered plugin level).
    """
    workspace_root = _PROJECT_ROOT / "src" / "unit_1"
    delivered_root = _PROJECT_ROOT
    for candidate in (workspace_root, delivered_root):
        if (candidate / ".claude-plugin" / "plugin.json").exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find plugin.json at {workspace_root}/.claude-plugin/plugin.json "
        f"or {delivered_root}/.claude-plugin/plugin.json"
    )


def _plugin_json_path() -> Path:
    return _plugin_root() / ".claude-plugin" / "plugin.json"


# Authoritative whitelist of allowed top-level keys in plugin.json,
# derived from code.claude.com/docs/en/plugins-reference.md. Any key
# outside this set is either (a) a new field in a future schema version
# (which fails this test and prompts us to revisit) or (b) a regression
# to the pre-BUG-AUDIT-6 broken shape.
_ALLOWED_TOP_LEVEL_KEYS = {
    "name",
    "version",
    "description",
    "author",
    "license",
    "keywords",
    "homepage",
    "repository",
    "mcpServers",
    "lspServers",
    "outputStyles",
    "tools",
    "userConfig",
    "channels",
    # `hooks` is allowed ONLY as an inline object (not a string path).
    # We don't include it in this whitelist because our plugin does not
    # use the inline form; if we add hooks later, update this whitelist
    # and the negative sentinel tests.
}


@pytest.fixture(scope="module")
def plugin_json_data() -> dict:
    return json.loads(_plugin_json_path().read_text())


# ---------------------------------------------------------------------------
# BUG-AUDIT-6 regression tests.
# ---------------------------------------------------------------------------


class TestBugAudit6PluginJsonSchema:
    """BC-1.1: author object + forbidden top-level keys (BUG-AUDIT-6)."""

    def test_plugin_json_parses_as_valid_json(self) -> None:
        json.loads(_plugin_json_path().read_text())  # raises on parse failure

    def test_plugin_json_author_is_object_with_name(
        self, plugin_json_data: dict
    ) -> None:
        author = plugin_json_data.get("author")
        assert isinstance(author, dict), (
            f"BC-1.1 / BUG-AUDIT-6: `author` must be an object, got "
            f"{type(author).__name__}. The plain-string form "
            f"(e.g. `\"author\": \"Name\"`) fails Claude Code's Zod schema "
            f"validator with `expected object, received string`."
        )
        name = author.get("name")
        assert isinstance(name, str) and name.strip(), (
            "BC-1.1 / BUG-AUDIT-6: `author` object must contain a non-empty "
            "`name` field."
        )

    def test_plugin_json_does_not_contain_skills_key(
        self, plugin_json_data: dict
    ) -> None:
        assert "skills" not in plugin_json_data, (
            "BC-1.1 / BUG-AUDIT-6: `skills` MUST NOT appear as a top-level key "
            "in plugin.json. Claude Code auto-discovers skills from the "
            "`./skills/` directory at the plugin root; declaring `skills` as "
            "a string path causes Zod validation failure."
        )

    def test_plugin_json_does_not_contain_agents_key(
        self, plugin_json_data: dict
    ) -> None:
        assert "agents" not in plugin_json_data, (
            "BC-1.1 / BUG-AUDIT-6: `agents` MUST NOT appear as a top-level key "
            "in plugin.json. Claude Code auto-discovers agents from the "
            "`./agents/` directory at the plugin root; declaring `agents` as "
            "a string path causes Zod validation failure."
        )

    def test_plugin_json_does_not_contain_hooks_key_as_string(
        self, plugin_json_data: dict
    ) -> None:
        # Strict form: hooks must be absent for our plugin (we use the
        # auto-discovered ./hooks/hooks.json file form). If a future design
        # adopts the inline-object form, update this test to permit a dict
        # value but still forbid a string.
        hooks = plugin_json_data.get("hooks")
        assert hooks is None, (
            f"BC-1.1 / BUG-AUDIT-6: `hooks` MUST NOT appear as a top-level "
            f"key (our plugin uses the auto-discovered `./hooks/hooks.json` "
            f"file form). Found: {hooks!r}. The string-path form fails Zod "
            f"validation; the inline-object form is not currently used by "
            f"this plugin."
        )

    def test_plugin_json_does_not_contain_commands_key_as_string(
        self, plugin_json_data: dict
    ) -> None:
        commands = plugin_json_data.get("commands")
        if commands is None:
            return
        assert not isinstance(commands, str), (
            "BC-1.1 / BUG-AUDIT-6: `commands` as a string path causes Zod "
            "validation failure. Commands are auto-discovered from the "
            "`./commands/` directory at the plugin root."
        )

    def test_plugin_json_top_level_keys_are_in_allowed_set(
        self, plugin_json_data: dict
    ) -> None:
        top_level_keys = set(plugin_json_data.keys())
        disallowed = top_level_keys - _ALLOWED_TOP_LEVEL_KEYS
        assert not disallowed, (
            f"BC-1.1 / BUG-AUDIT-6: plugin.json contains top-level keys not "
            f"in the allowed whitelist: {sorted(disallowed)}. The authoritative "
            f"schema is at code.claude.com/docs/en/plugins-reference.md."
        )

    def test_plugin_json_name_is_debrief(self, plugin_json_data: dict) -> None:
        assert plugin_json_data.get("name") == "debrief"

    def test_plugin_json_version_is_semver(self, plugin_json_data: dict) -> None:
        version = plugin_json_data.get("version")
        assert isinstance(version, str) and re.match(r"^\d+\.\d+\.\d+", version), (
            f"BC-1.1: `version` must be a SemVer string, got {version!r}."
        )

    def test_skills_agents_hooks_directories_exist_at_default_paths(self) -> None:
        root = _plugin_root()
        assert (root / "skills").is_dir(), (
            "BC-1.2 / BUG-AUDIT-6: `skills/` directory must exist at the "
            "plugin root for auto-discovery."
        )
        assert (root / "agents").is_dir(), (
            "BC-1.3 / BUG-AUDIT-6: `agents/` directory must exist at the "
            "plugin root for auto-discovery."
        )
        assert (root / "hooks" / "hooks.json").is_file(), (
            "BC-1.4 / BUG-AUDIT-6: `hooks/hooks.json` must exist at the "
            "plugin root for auto-discovery."
        )
