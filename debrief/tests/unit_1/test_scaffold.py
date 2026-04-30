# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Tests for Unit 1: Plugin Scaffold.

Synthetic data generation assumptions
--------------------------------------
- The plugin scaffold files are expected at ``src/unit_1/`` relative to the
  project root.  The project root is resolved as the grandparent of the
  ``tests/`` directory (i.e., two levels above this file).
- ``check-write-auth`` is exercised as a subprocess.  Tests that need a real
  ``deck_state.json`` write a minimal file into a ``tmp_path`` directory and
  point ``$PWD`` at that directory when invoking the script.
- Hooks tool-invocation JSON sent to ``check-write-auth`` via stdin follows the
  format documented in Section 24.3:
  ``{"tool_name": "Write", "tool_input": {"file_path": "<path>"}}``.
- For style-lock tests the synthetic ``deck_state.json`` contains only the
  ``style_locked`` key.  No other fields are required for the script to run.
- Environment variable ``CLAUDE_PLUGIN_ROOT`` is set to ``src/unit_1`` for all
  subprocess invocations so that the script can reference plugin-relative paths.
- ``jq`` is assumed to be on ``$PATH`` in the test environment (it is listed in
  ``environment.yml`` and must be available in the debrief conda env).
- VERSIONS.md parsing assumes tab-separated fields with no leading/trailing
  whitespace on each field, exactly matching the format:
  ``<filename>\\tversion <ver>\\tsha256:<hash>\\t<source_url>``.
- For BC-1.2a / BC-1.3b frontmatter tests, the exact per-skill and per-agent
  YAML field values come verbatim from stakeholder spec §5.2 and §6.2
  respectively.  Any deviation in the actual files (wrong description, wrong
  model, wrong maxTurns, etc.) is treated as a test failure.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_TESTS_DIR = Path(__file__).resolve().parent.parent  # tests/
_PROJECT_ROOT = _TESTS_DIR.parent  # delivered plugin root
_UNIT_ROOT = _PROJECT_ROOT  # plugin scaffold is at project root in delivered repo


def _unit(rel: str) -> Path:
    """Return the absolute path of a file inside the plugin root."""
    return _UNIT_ROOT / rel


# ---------------------------------------------------------------------------
# BC-1.1  plugin.json manifest completeness
# ---------------------------------------------------------------------------

# BUG-AUDIT-6: skills, agents, hooks MUST NOT be top-level keys — Claude
# Code auto-discovers those from default subdirectories, and the Zod schema
# validator rejects string-path forms. BC-1.1.
REQUIRED_PLUGIN_JSON_KEYS = {
    "name",
    "version",
    "description",
    "author",
    "license",
    "keywords",
}


class TestPluginJsonManifestCompleteness:
    """BC-1.1 — plugin.json must have exactly the required top-level keys."""

    @pytest.fixture(scope="class")
    def plugin_json(self) -> dict:
        path = _unit(".claude-plugin/plugin.json")
        assert path.exists(), f"plugin.json not found at {path}"
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_plugin_json_exists(self) -> None:
        assert _unit(".claude-plugin/plugin.json").exists()

    def test_plugin_json_has_exactly_required_top_level_keys(
        self, plugin_json: dict
    ) -> None:
        assert set(plugin_json.keys()) == REQUIRED_PLUGIN_JSON_KEYS

    def test_plugin_json_name_is_debrief(self, plugin_json: dict) -> None:
        assert plugin_json["name"] == "debrief"

    def test_plugin_json_version_is_1_1_0(self, plugin_json: dict) -> None:
        assert plugin_json["version"] == "1.1.0"

    def test_plugin_json_license_is_apache_2_0(self, plugin_json: dict) -> None:
        assert plugin_json["license"] == "Apache-2.0"

    def test_plugin_json_no_extra_top_level_keys(self, plugin_json: dict) -> None:
        # BUG-AUDIT-6: catches regressions where skills/agents/hooks/commands
        # are reintroduced as string paths (which fail Zod validation).
        extra = set(plugin_json.keys()) - REQUIRED_PLUGIN_JSON_KEYS
        assert extra == set(), f"Unexpected top-level keys: {extra}"

    def test_plugin_json_author_is_object_with_name(self, plugin_json: dict) -> None:
        # BUG-AUDIT-6: author must be an object with a name field, not a
        # plain string. Claude Code's Zod schema rejects the string form.
        author = plugin_json["author"]
        assert isinstance(author, dict), (
            f"BC-1.1 / BUG-AUDIT-6: author must be an object, got {type(author).__name__}."
        )
        assert "name" in author and isinstance(author["name"], str) and author["name"].strip(), (
            "BC-1.1 / BUG-AUDIT-6: author must contain a non-empty `name` field."
        )


# ---------------------------------------------------------------------------
# BC-1.2  Commands discovery pointer (BUG-AUDIT-9 — migrated from skills/)
# ---------------------------------------------------------------------------

# Expected command file names at ./commands/. Filenames have NO plugin
# prefix — the namespace `/debrief:` is added automatically by Claude
# Code from the plugin manifest's `name` field. Adding a `debrief_`
# prefix to the filename produces a double-prefixed invocation like
# `/debrief:debrief_slide` (see BUG-AUDIT-10).
EXPECTED_COMMAND_FILES = {
    "slide.md",
    "style.md",
    "export.md",
    "save.md",
    "view.md",
    "restore.md",
    "present.md",
    "quit.md",
    "script.md",
    "handout.md",
}

# Expected command names (filenames without the .md extension).
EXPECTED_COMMAND_NAMES = {
    name[:-len(".md")] for name in EXPECTED_COMMAND_FILES
}


class TestCommandsDiscoveryPointer:
    """BC-1.2 — commands/ auto-discovered as namespaced /debrief:<name>."""

    def test_commands_directory_exists(self) -> None:
        assert _unit("commands").is_dir(), (
            "BC-1.2 / BUG-AUDIT-9: plugin root must contain a commands/ directory."
        )

    def test_commands_directory_contains_exactly_nine_files(self) -> None:
        commands_dir = _unit("commands")
        actual = {p.name for p in commands_dir.iterdir() if p.is_file()}
        assert actual == EXPECTED_COMMAND_FILES, (
            f"BC-1.2 / BUG-AUDIT-9: commands/ must contain exactly {EXPECTED_COMMAND_FILES}, "
            f"found {actual}"
        )

    @pytest.mark.parametrize("command_file", sorted(EXPECTED_COMMAND_FILES))
    def test_command_file_exists(self, command_file: str) -> None:
        path = _unit("commands") / command_file
        assert path.exists() and path.is_file(), (
            f"BC-1.2 / BUG-AUDIT-9: commands/{command_file} must exist as a flat file."
        )

    def test_skills_directory_does_not_exist_or_is_empty(self) -> None:
        # BUG-AUDIT-9 negative sentinel: the old skills/<name>/SKILL.md
        # layout must not coexist with the new commands/ layout. If skills/
        # exists, it must be empty (no SKILL.md anywhere under it).
        skills_dir = _unit("skills")
        if not skills_dir.exists():
            return
        skill_md_files = list(skills_dir.rglob("SKILL.md"))
        assert not skill_md_files, (
            f"BUG-AUDIT-9 regression: skills/ contains SKILL.md files: {skill_md_files}. "
            f"User-invocable workflows must live in commands/debrief_<name>.md, not "
            f"skills/<name>/SKILL.md. See BC-1.2."
        )


# ---------------------------------------------------------------------------
# BC-1.2  Command file structural verification (BUG-AUDIT-9)
# ---------------------------------------------------------------------------


class TestCommandFileStructure:
    """BC-1.2 — each commands/debrief_<name>.md is plain markdown with
    no YAML frontmatter and a `# /debrief:<name>` H1 heading on the
    first non-blank line."""

    @pytest.mark.parametrize("command_file", sorted(EXPECTED_COMMAND_FILES))
    def test_command_file_has_no_yaml_frontmatter(
        self, command_file: str
    ) -> None:
        # BUG-AUDIT-9 negative sentinel: command files MUST NOT start with
        # YAML frontmatter. The `---` delimiter is the canonical indicator
        # of frontmatter; its presence at the top of a command file is a
        # regression to the old SKILL.md format.
        path = _unit("commands") / command_file
        content = path.read_text(encoding="utf-8")
        assert not content.startswith("---"), (
            f"BC-1.2 / BUG-AUDIT-9: commands/{command_file} must NOT start with "
            f"YAML frontmatter. Command files are plain markdown starting with a "
            f"`# /debrief:<name>` heading."
        )

    @pytest.mark.parametrize("command_file", sorted(EXPECTED_COMMAND_FILES))
    def test_command_file_first_heading_is_namespaced(
        self, command_file: str
    ) -> None:
        path = _unit("commands") / command_file
        content = path.read_text(encoding="utf-8")
        first_nonblank = next(
            (line for line in content.splitlines() if line.strip()),
            "",
        )
        expected_name = command_file[:-len(".md")]
        expected_heading = f"# /debrief:{expected_name}"
        assert first_nonblank.strip() == expected_heading, (
            f"BC-1.2 / BUG-AUDIT-10: first non-blank line of commands/{command_file} "
            f"must be `{expected_heading}`, got `{first_nonblank.strip()}`."
        )

    @pytest.mark.parametrize("command_file", sorted(EXPECTED_COMMAND_FILES))
    def test_command_file_is_non_empty(self, command_file: str) -> None:
        path = _unit("commands") / command_file
        content = path.read_text(encoding="utf-8").strip()
        assert len(content) > 0, (
            f"BC-1.2 / BUG-AUDIT-9: commands/{command_file} must not be empty."
        )


# ---------------------------------------------------------------------------
# Shared helper (used by agent frontmatter tests below)
# ---------------------------------------------------------------------------


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    """Parse the YAML frontmatter block from a file.

    Raises AssertionError if the file does not start with '---\\n', does not
    contain a closing '---' delimiter, or if the YAML between delimiters is
    invalid.
    """
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n"), (
        f"{path} must start with '---\\n' (got: {content[:20]!r})"
    )
    # Find the closing '---' delimiter
    rest = content[4:]  # skip opening '---\n'
    close_idx = rest.find("\n---")
    assert close_idx != -1, (
        f"{path} is missing a closing '---' delimiter after the frontmatter block"
    )
    yaml_block = rest[:close_idx]
    parsed = yaml.safe_load(yaml_block)
    assert isinstance(parsed, dict), (
        f"Frontmatter in {path} did not parse as a YAML dict"
    )
    return parsed


# ---------------------------------------------------------------------------
# BC-1.3  Agents discovery pointer
# ---------------------------------------------------------------------------

EXPECTED_AGENT_FILES = {
    "consultant.md",
    "slide-maker.md",
    "visual-qa.md",
    "bug-diagnostic.md",
    "stylist.md",
    # BUG-AUDIT-80 (Cycle 2 Phase 2): rewriter agent-card added.
    # Sole writer of deck_brief.md per BC-5.19; invoked via the
    # rewrite_brief CLI subcommand (BC-3.18) at three triggers
    # (PreCompact hook, /debrief:quit, /debrief:refresh-brief).
    "rewriter.md",
}


class TestAgentsDiscoveryPointer:
    """BC-1.3 — agents/ directory at plugin root (auto-discovered; BUG-AUDIT-6)."""

    def test_agents_directory_exists(self) -> None:
        assert _unit("agents").is_dir()

    def test_all_five_required_agent_files_are_present(self) -> None:
        agents_dir = _unit("agents")
        actual = {p.name for p in agents_dir.glob("*.md")}
        assert actual == EXPECTED_AGENT_FILES

    def test_no_additional_md_files_in_agents_directory(self) -> None:
        agents_dir = _unit("agents")
        all_md = {p.name for p in agents_dir.glob("*.md")}
        extra = all_md - EXPECTED_AGENT_FILES
        assert extra == set(), f"Unexpected .md files in agents/: {extra}"


# ---------------------------------------------------------------------------
# BC-1.3a / BC-1.3b  Agent file frontmatter structural verification (spec §6.1/§6.2)
# ---------------------------------------------------------------------------

# Exact per-agent frontmatter from spec §6.2 — verbatim field values.
AGENT_FRONTMATTER_SPEC: dict[str, dict[str, Any]] = {
    "consultant.md": {
        "name": "consultant",
        "description": "Narrative architecture partner for deck content design",
        "model": "claude-sonnet-4-6",
        "maxTurns": 50,
        "tools": "Read, Write, Edit",
    },
    "slide-maker.md": {
        "name": "slide-maker",
        "description": (
            "Slide authoring agent that generates and revises styled HTML slides"
        ),
        "model": "claude-sonnet-4-6",
        "maxTurns": 20,
        # BC-8.4 / BUG-AUDIT-17: `Task` was added to the slide-maker's
        # tools list so it can spawn the visual-qa subagent as its final
        # action before returning (replacing the broken type="agent"
        # PostToolUse hook per BUG-AUDIT-12b). Do not remove `Task`
        # without updating BC-8.4 and the BUG-AUDIT-17 regression tests.
        "tools": "Read, Write, Edit, Bash, Task",
    },
    "visual-qa.md": {
        "name": "visual-qa",
        "description": (
            "Visual quality assurance agent that screenshots slides and checks"
            " design invariants"
        ),
        "model": "claude-sonnet-4-6",
        "maxTurns": 10,
        "tools": "Read, Write, Bash",
    },
    "bug-diagnostic.md": {
        "name": "bug-diagnostic",
        "description": (
            "Diagnostic agent that investigates rendering failures and authoring errors"
        ),
        "model": "claude-sonnet-4-6",
        "maxTurns": 15,
        "tools": "Read, Write, Edit, Bash",
    },
    "stylist.md": {
        "name": "stylist",
        "description": (
            "Style co-design agent that produces style_config.json and style_guide.md"
        ),
        "model": "claude-sonnet-4-6",
        "maxTurns": 20,
        "tools": "Read, Write, Edit, Bash",
    },
    # BC-5.19 / BUG-AUDIT-80: rewriter agent-card. Sole writer of
    # deck_brief.md per BC-5.19. Single turn (maxTurns: 1) — the
    # rewriter produces a complete brief in one call. Read-only tools
    # — the wrapping rewrite_brief CLI handles the writes atomically.
    "rewriter.md": {
        "name": "rewriter",
        "description": (
            "Memory rewriter that produces deck_brief.md from the raw "
            "dialog archive and event timeline"
        ),
        "model": "claude-sonnet-4-6",
        "maxTurns": 1,
        "tools": "Read",
    },
}

# Required frontmatter fields per spec §6.1
AGENT_REQUIRED_FIELDS = {"name", "description", "model", "maxTurns", "tools"}


class TestAgentFrontmatterStructure:
    """BC-1.3a / BC-1.3b — Each agent .md file must start with '---\\n',
    contain a closing '---', and the YAML block must contain all required
    fields with exact values from spec §6.2."""

    @pytest.mark.parametrize("agent_file", sorted(EXPECTED_AGENT_FILES))
    def test_agent_md_starts_with_yaml_frontmatter_delimiter(
        self, agent_file: str
    ) -> None:
        path = _unit("agents") / agent_file
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---\n"), (
            f"agents/{agent_file} must start with '---\\n' for Claude Code agent"
            f" registration; got: {content[:30]!r}"
        )

    @pytest.mark.parametrize("agent_file", sorted(EXPECTED_AGENT_FILES))
    def test_agent_md_contains_closing_frontmatter_delimiter(
        self, agent_file: str
    ) -> None:
        path = _unit("agents") / agent_file
        content = path.read_text(encoding="utf-8")
        rest = content[4:] if content.startswith("---\n") else content
        assert "\n---" in rest, (
            f"agents/{agent_file} must contain a closing '---' delimiter to end"
            f" the frontmatter block"
        )

    @pytest.mark.parametrize("agent_file", sorted(EXPECTED_AGENT_FILES))
    def test_agent_md_frontmatter_parses_as_valid_yaml(self, agent_file: str) -> None:
        path = _unit("agents") / agent_file
        fm = _parse_frontmatter(path)
        assert isinstance(fm, dict), (
            f"agents/{agent_file} frontmatter must parse as a YAML mapping"
        )

    @pytest.mark.parametrize("agent_file", sorted(EXPECTED_AGENT_FILES))
    def test_agent_md_frontmatter_contains_all_required_fields(
        self, agent_file: str
    ) -> None:
        path = _unit("agents") / agent_file
        fm = _parse_frontmatter(path)
        missing = AGENT_REQUIRED_FIELDS - set(fm.keys())
        assert missing == set(), (
            f"agents/{agent_file} frontmatter is missing required fields: {missing}"
        )

    @pytest.mark.parametrize("agent_file", sorted(EXPECTED_AGENT_FILES))
    def test_agent_md_frontmatter_name_matches_spec(self, agent_file: str) -> None:
        path = _unit("agents") / agent_file
        fm = _parse_frontmatter(path)
        expected = AGENT_FRONTMATTER_SPEC[agent_file]["name"]
        assert fm.get("name") == expected, (
            f"agents/{agent_file} frontmatter 'name' must be {expected!r},"
            f" got {fm.get('name')!r}"
        )

    @pytest.mark.parametrize("agent_file", sorted(EXPECTED_AGENT_FILES))
    def test_agent_md_frontmatter_description_matches_spec(
        self, agent_file: str
    ) -> None:
        path = _unit("agents") / agent_file
        fm = _parse_frontmatter(path)
        expected = AGENT_FRONTMATTER_SPEC[agent_file]["description"]
        assert fm.get("description") == expected, (
            f"agents/{agent_file} frontmatter 'description' must be {expected!r},"
            f" got {fm.get('description')!r}"
        )

    @pytest.mark.parametrize("agent_file", sorted(EXPECTED_AGENT_FILES))
    def test_agent_md_frontmatter_model_matches_spec(self, agent_file: str) -> None:
        path = _unit("agents") / agent_file
        fm = _parse_frontmatter(path)
        expected = AGENT_FRONTMATTER_SPEC[agent_file]["model"]
        assert fm.get("model") == expected, (
            f"agents/{agent_file} frontmatter 'model' must be {expected!r},"
            f" got {fm.get('model')!r}"
        )

    @pytest.mark.parametrize("agent_file", sorted(EXPECTED_AGENT_FILES))
    def test_agent_md_frontmatter_max_turns_matches_spec(self, agent_file: str) -> None:
        path = _unit("agents") / agent_file
        fm = _parse_frontmatter(path)
        expected = AGENT_FRONTMATTER_SPEC[agent_file]["maxTurns"]
        assert fm.get("maxTurns") == expected, (
            f"agents/{agent_file} frontmatter 'maxTurns' must be {expected!r},"
            f" got {fm.get('maxTurns')!r}"
        )

    @pytest.mark.parametrize("agent_file", sorted(EXPECTED_AGENT_FILES))
    def test_agent_md_frontmatter_tools_matches_spec(self, agent_file: str) -> None:
        path = _unit("agents") / agent_file
        fm = _parse_frontmatter(path)
        expected = AGENT_FRONTMATTER_SPEC[agent_file]["tools"]
        assert fm.get("tools") == expected, (
            f"agents/{agent_file} frontmatter 'tools' must be {expected!r},"
            f" got {fm.get('tools')!r}"
        )


# ---------------------------------------------------------------------------
# BC-1.4  Hooks pointer and hooks.json structure
# ---------------------------------------------------------------------------


class TestHooksPointerAndStructure:
    """BC-1.4 — hooks/hooks.json at plugin root (auto-discovered; BUG-AUDIT-6)."""

    @pytest.fixture(scope="class")
    def hooks_json(self) -> dict:
        path = _unit("hooks/hooks.json")
        assert path.exists(), f"hooks.json not found at {path}"
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_hooks_json_file_exists(self) -> None:
        assert _unit("hooks/hooks.json").exists()

    def test_hooks_json_declares_pre_tool_use_hook(self, hooks_json: dict) -> None:
        # BUG-AUDIT-7: use the helper, which supports both the legacy flat
        # layout and the required Form B layout (top-level `hooks` wrapper).
        pre_hooks = _get_hooks_by_event(hooks_json, "PreToolUse")
        assert len(pre_hooks) > 0, "hooks.json must declare a PreToolUse hook"

    def test_pre_tool_use_hook_matches_write_or_edit(self, hooks_json: dict) -> None:
        pre_hooks = _get_hooks_by_event(hooks_json, "PreToolUse")
        matchers = [h.get("matcher", h.get("tool", "")) for h in pre_hooks]
        assert any("Write" in m and "Edit" in m for m in matchers), (
            f"PreToolUse hook must match Write|Edit; found matchers: {matchers}"
        )

    def test_pre_tool_use_hook_type_is_command(self, hooks_json: dict) -> None:
        pre_hooks = _get_hooks_by_event(hooks_json, "PreToolUse")
        types = [h.get("type", h.get("hook_type", "")) for h in pre_hooks]
        assert any(t == "command" for t in types), (
            f"PreToolUse hook must have type 'command'; found: {types}"
        )

    def test_pre_tool_use_hook_command_references_check_write_auth(
        self, hooks_json: dict
    ) -> None:
        pre_hooks = _get_hooks_by_event(hooks_json, "PreToolUse")
        commands = [h.get("command", "") for h in pre_hooks]
        assert any("check-write-auth" in cmd for cmd in commands), (
            f"PreToolUse command must reference check-write-auth; found: {commands}"
        )

    def test_pre_tool_use_hook_command_uses_claude_plugin_root(
        self, hooks_json: dict
    ) -> None:
        pre_hooks = _get_hooks_by_event(hooks_json, "PreToolUse")
        commands = [h.get("command", "") for h in pre_hooks]
        assert any("${CLAUDE_PLUGIN_ROOT}" in cmd for cmd in commands), (
            "PreToolUse command must use ${CLAUDE_PLUGIN_ROOT}"
        )

    def test_pre_tool_use_hook_timeout_is_10(self, hooks_json: dict) -> None:
        pre_hooks = _get_hooks_by_event(hooks_json, "PreToolUse")
        timeouts = [h.get("timeout") for h in pre_hooks]
        assert any(t == 10 for t in timeouts), (
            f"PreToolUse hook timeout must be 10; found: {timeouts}"
        )

    def test_hooks_json_declares_post_tool_use_hook(self, hooks_json: dict) -> None:
        post_hooks = _get_hooks_by_event(hooks_json, "PostToolUse")
        assert len(post_hooks) > 0, "hooks.json must declare a PostToolUse hook"

    def test_post_tool_use_hook_matches_write_or_edit(self, hooks_json: dict) -> None:
        post_hooks = _get_hooks_by_event(hooks_json, "PostToolUse")
        matchers = [h.get("matcher", h.get("tool", "")) for h in post_hooks]
        assert any("Write" in m and "Edit" in m for m in matchers), (
            f"PostToolUse hook must match Write|Edit; found: {matchers}"
        )

    def test_post_tool_use_hook_type_is_command_per_bug_audit_17(
        self, hooks_json: dict
    ) -> None:
        # BC-1.4 / BUG-AUDIT-17 (supersedes BUG-AUDIT-7): the PostToolUse
        # handler is type="command" invoking bin/qa-run-on-write. The
        # prior type="agent" form was broken by Claude Code v2.1.107
        # upstream (BUG-AUDIT-12b) and removed in BUG-AUDIT-17.
        post_hooks = _get_hooks_by_event(hooks_json, "PostToolUse")
        types = [h.get("type", h.get("hook_type", "")) for h in post_hooks]
        assert any(t == "command" for t in types), (
            f"BC-1.4 / BUG-AUDIT-17: PostToolUse hook must have type "
            f"'command'; found: {types}"
        )

    def test_post_tool_use_hook_timeout_per_bug_audit_17(
        self, hooks_json: dict
    ) -> None:
        # BC-1.4 / BUG-AUDIT-17: timeout must be >= 60 (BUG-AUDIT-17
        # bumped it to 120 for Playwright rendering inside qa_checker.py).
        post_hooks = _get_hooks_by_event(hooks_json, "PostToolUse")
        timeouts = [h.get("timeout") for h in post_hooks]
        assert any(t is not None and t >= 60 for t in timeouts), (
            f"BC-1.4 / BUG-AUDIT-17: PostToolUse hook timeout must be "
            f">= 60s; found: {timeouts}"
        )

    def test_post_tool_use_hook_has_command_per_bug_audit_17(
        self, hooks_json: dict
    ) -> None:
        # BC-1.4 / BUG-AUDIT-17: the command hook has a `command` field
        # replacing the old agent hook's `prompt` field.
        post_hooks = _get_hooks_by_event(hooks_json, "PostToolUse")
        assert any("command" in h for h in post_hooks), (
            "BC-1.4 / BUG-AUDIT-17: PostToolUse command hook must have "
            "a `command` field."
        )


def _get_hooks_by_event(hooks_json: dict, event: str) -> list[dict]:
    """Extract hooks for a given event from various hooks.json layouts.

    BUG-AUDIT-7: when unwrapping the nested Form B layout, the outer
    wrapper's `matcher` field is merged into each inner hook so that
    downstream tests calling `h.get("matcher")` still find the matcher
    on the flattened handler dict.
    """
    # Direct key layout: {"PreToolUse": [...], "PostToolUse": [...]}
    if event in hooks_json and isinstance(hooks_json[event], list):
        return hooks_json[event]
    # Form B nested layout: {"hooks": {"PreToolUse": [{"matcher": "...", "hooks": [...]}]}}
    if "hooks" in hooks_json and isinstance(hooks_json["hooks"], dict):
        inner = hooks_json["hooks"]
        if event in inner and isinstance(inner[event], list):
            result: list[dict] = []
            for item in inner[event]:
                if isinstance(item, dict):
                    outer_matcher = item.get("matcher")
                    nested = item.get("hooks", [])
                    if isinstance(nested, list):
                        for h in nested:
                            if isinstance(h, dict):
                                merged = dict(h)  # shallow copy
                                if outer_matcher is not None and "matcher" not in merged:
                                    merged["matcher"] = outer_matcher
                                result.append(merged)
                    else:
                        result.append(item)
            return result
    # Flat list layout: {"hooks": [{"event": "PreToolUse", ...}]}
    for val in hooks_json.values():
        if isinstance(val, list):
            matches = [
                h for h in val if isinstance(h, dict) and h.get("event") == event
            ]
            if matches:
                return matches
    return []


# ---------------------------------------------------------------------------
# BC-1.5  settings.json
# ---------------------------------------------------------------------------


class TestSettingsJson:
    """BC-1.5 — settings.json must contain exactly {"agent": "consultant"}."""

    def test_settings_json_exists(self) -> None:
        assert _unit("settings.json").exists()

    def test_settings_json_contains_exactly_agent_consultant(self) -> None:
        with open(_unit("settings.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        assert data == {"agent": "consultant"}, (
            f'settings.json must be exactly {{"agent": "consultant"}}, got: {data}'
        )

    def test_settings_json_has_no_extra_fields(self) -> None:
        with open(_unit("settings.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        assert set(data.keys()) == {"agent"}, (
            "settings.json must have exactly one key 'agent',"
            f" found: {set(data.keys())}"
        )


# ---------------------------------------------------------------------------
# BC-1.6  environment.yml completeness
# ---------------------------------------------------------------------------


class TestEnvironmentYmlCompleteness:
    """BC-1.6 — environment.yml completeness."""

    @pytest.fixture(scope="class")
    def env_yml(self) -> dict:
        path = _unit("environment.yml")
        assert path.exists(), f"environment.yml not found at {path}"
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def test_environment_yml_exists(self) -> None:
        assert _unit("environment.yml").exists()

    def test_environment_yml_pins_python_3_11(self, env_yml: dict) -> None:
        deps = env_yml.get("dependencies", [])
        conda_deps = [d for d in deps if isinstance(d, str)]
        assert any(re.fullmatch(r"python=3\.11(?:\.\d+)?", d) for d in conda_deps), (
            f"environment.yml must pin python=3.11; conda deps: {conda_deps}"
        )

    def test_environment_yml_does_not_pin_libreoffice_still(
        self, env_yml: dict
    ) -> None:
        """BUG-AUDIT-4: libreoffice-still is Linux-only on conda-forge and
        blocks macOS bootstrap. LibreOffice is a system dependency now
        (BC-1.6 amended, BC-1.6a added). bin/debrief discovers a system
        install and creates a ${CONDA_PREFIX}/bin/soffice shim on macOS.
        """
        deps = env_yml.get("dependencies", [])
        conda_deps = [d for d in deps if isinstance(d, str)]
        pip_deps = _get_pip_deps(env_yml)
        assert not any("libreoffice-still" in d for d in conda_deps), (
            f"BUG-AUDIT-4 regression: libreoffice-still reappeared in "
            f"environment.yml conda deps: {conda_deps}. See BC-1.6."
        )
        assert not any("libreoffice-still" in d for d in pip_deps), (
            f"BUG-AUDIT-4 regression: libreoffice-still reappeared in "
            f"environment.yml pip deps: {pip_deps}. See BC-1.6."
        )

    def test_environment_yml_includes_jq(self, env_yml: dict) -> None:
        deps = env_yml.get("dependencies", [])
        conda_deps = [d for d in deps if isinstance(d, str)]
        assert any(re.fullmatch(r"jq(?:[>=<].*)?", d) for d in conda_deps), (
            f"environment.yml must include jq; conda deps: {conda_deps}"
        )

    def test_environment_yml_uses_only_conda_forge_channel(self, env_yml: dict) -> None:
        channels = env_yml.get("channels", [])
        assert channels == ["conda-forge"], (
            f"environment.yml must use only conda-forge channel; found: {channels}"
        )

    def test_environment_yml_includes_pip_section(self, env_yml: dict) -> None:
        deps = env_yml.get("dependencies", [])
        pip_sections = [d for d in deps if isinstance(d, dict) and "pip" in d]
        assert len(pip_sections) == 1, (
            "environment.yml must have exactly one pip: section"
        )

    def test_environment_yml_pip_includes_playwright(self, env_yml: dict) -> None:
        pip_deps = _get_pip_deps(env_yml)
        assert any("playwright" in d for d in pip_deps), (
            f"pip section must include playwright>=1.40; pip deps: {pip_deps}"
        )

    def test_environment_yml_playwright_meets_minimum_version(
        self, env_yml: dict
    ) -> None:
        pip_deps = _get_pip_deps(env_yml)
        pw = next((d for d in pip_deps if d.startswith("playwright")), None)
        assert pw is not None
        _assert_version_constraint(pw, "playwright", "1.40")

    def test_environment_yml_pip_includes_python_pptx(self, env_yml: dict) -> None:
        pip_deps = _get_pip_deps(env_yml)
        assert any("python-pptx" in d for d in pip_deps), (
            f"pip section must include python-pptx>=0.6.21; pip deps: {pip_deps}"
        )

    def test_environment_yml_python_pptx_meets_minimum_version(
        self, env_yml: dict
    ) -> None:
        pip_deps = _get_pip_deps(env_yml)
        pptx = next((d for d in pip_deps if "python-pptx" in d), None)
        assert pptx is not None
        _assert_version_constraint(pptx, "python-pptx", "0.6.21")

    def test_environment_yml_pip_includes_pymupdf(self, env_yml: dict) -> None:
        pip_deps = _get_pip_deps(env_yml)
        assert any("PyMuPDF" in d or "pymupdf" in d.lower() for d in pip_deps), (
            f"pip section must include PyMuPDF>=1.23; pip deps: {pip_deps}"
        )

    def test_environment_yml_pymupdf_meets_minimum_version(self, env_yml: dict) -> None:
        pip_deps = _get_pip_deps(env_yml)
        mupdf = next(
            (d for d in pip_deps if "PyMuPDF" in d or "pymupdf" in d.lower()), None
        )
        assert mupdf is not None
        _assert_version_constraint(mupdf, "PyMuPDF", "1.23")

    def test_environment_yml_pip_includes_json_repair(self, env_yml: dict) -> None:
        pip_deps = _get_pip_deps(env_yml)
        assert any("json-repair" in d for d in pip_deps), (
            f"pip section must include json-repair>=0.25; pip deps: {pip_deps}"
        )

    def test_environment_yml_json_repair_meets_minimum_version(
        self, env_yml: dict
    ) -> None:
        pip_deps = _get_pip_deps(env_yml)
        jr = next((d for d in pip_deps if "json-repair" in d), None)
        assert jr is not None
        _assert_version_constraint(jr, "json-repair", "0.25")


def _get_pip_deps(env_yml: dict) -> list[str]:
    deps = env_yml.get("dependencies", [])
    for d in deps:
        if isinstance(d, dict) and "pip" in d:
            return d["pip"]
    return []


def _assert_version_constraint(spec: str, package: str, min_version: str) -> None:
    """Assert pip dep spec has >= constraint."""
    # e.g. "playwright>=1.40" or "PyMuPDF>=1.23"
    match = re.search(r">=(\S+)", spec)
    assert match, f"{package} spec '{spec}' must include a >= version constraint"
    actual_ver = tuple(int(x) for x in match.group(1).split("."))
    required_ver = tuple(int(x) for x in min_version.split("."))
    assert actual_ver >= required_ver, (
        f"{package} version {match.group(1)} does not satisfy >={min_version}"
    )


# ---------------------------------------------------------------------------
# BC-1.7  check-write-auth exit codes
# ---------------------------------------------------------------------------

_SCRIPT_PATH = _unit("bin/check-write-auth")


def _run_auth_script(
    stdin_json: dict,
    *,
    cwd: Optional[str] = None,
    env_overrides: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """Run check-write-auth with given stdin JSON, returns CompletedProcess."""
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(_UNIT_ROOT)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["bash", str(_SCRIPT_PATH)],
        input=json.dumps(stdin_json),
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )


class TestCheckWriteAuthScript:
    """BC-1.7 — script must exist, be executable, and use only exit codes 0 and 2."""

    def test_check_write_auth_script_exists(self) -> None:
        assert _SCRIPT_PATH.exists(), (
            f"bin/check-write-auth not found at {_SCRIPT_PATH}"
        )

    def test_check_write_auth_script_is_executable(self) -> None:
        assert os.access(_SCRIPT_PATH, os.X_OK), (
            "bin/check-write-auth must be executable"
        )

    def test_check_write_auth_script_never_exits_with_code_1(
        self, tmp_path: Path
    ) -> None:
        # Authorized path outside slides/ — should exit 0
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "notes.md")},
        }
        result = _run_auth_script(
            stdin, cwd=str(tmp_path), env_overrides={"PWD": str(tmp_path)}
        )
        assert result.returncode != 1, (
            "check-write-auth must never exit with code 1; "
            f"got code {result.returncode}"
        )


# ---------------------------------------------------------------------------
# BC-1.7 / BC-1.11  Unconditional pass for non-protected paths
# ---------------------------------------------------------------------------


class TestCheckWriteAuthUnconditionalPass:
    """BC-1.11 — paths outside slides/ and not assets/style.css always exit 0."""

    def test_write_to_arbitrary_non_protected_path_exits_0(
        self, tmp_path: Path
    ) -> None:
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "README.md")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 0

    def test_write_to_nested_non_protected_path_exits_0(self, tmp_path: Path) -> None:
        (tmp_path / "output").mkdir()
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "output" / "export.pdf")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 0

    def test_write_to_non_protected_path_ignores_style_lock_status(
        self, tmp_path: Path
    ) -> None:
        # deck_state.json has style_locked=false but path is not protected
        (tmp_path / "deck_state.json").write_text(
            json.dumps({"style_locked": False}), encoding="utf-8"
        )
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "CLAUDE.md")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# BC-1.8  stdin parsing
# ---------------------------------------------------------------------------


class TestCheckWriteAuthStdinParsing:
    """BC-1.8 — script must exit 2 on malformed stdin, null path, or empty path."""

    def test_malformed_json_on_stdin_exits_2(self, tmp_path: Path) -> None:
        result = subprocess.run(
            ["bash", str(_SCRIPT_PATH)],
            input="not valid json",
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={
                **os.environ,
                "CLAUDE_PLUGIN_ROOT": str(_UNIT_ROOT),
                "PWD": str(tmp_path),
            },
        )
        assert result.returncode == 2

    def test_malformed_json_stderr_contains_unable_to_parse(
        self, tmp_path: Path
    ) -> None:
        result = subprocess.run(
            ["bash", str(_SCRIPT_PATH)],
            input="not valid json",
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={
                **os.environ,
                "CLAUDE_PLUGIN_ROOT": str(_UNIT_ROOT),
                "PWD": str(tmp_path),
            },
        )
        assert "Unable to parse tool invocation" in result.stderr, (
            f"Expected 'Unable to parse' in stderr; got: {result.stderr!r}"
        )

    def test_null_file_path_in_tool_input_exits_2(self, tmp_path: Path) -> None:
        stdin = {"tool_name": "Write", "tool_input": {"file_path": None}}
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 2

    def test_null_file_path_stderr_contains_unable_to_parse(
        self, tmp_path: Path
    ) -> None:
        stdin = {"tool_name": "Write", "tool_input": {"file_path": None}}
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert "Unable to parse tool invocation" in result.stderr

    def test_empty_file_path_in_tool_input_exits_2(self, tmp_path: Path) -> None:
        stdin = {"tool_name": "Write", "tool_input": {"file_path": ""}}
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 2

    def test_missing_tool_input_key_exits_2(self, tmp_path: Path) -> None:
        stdin = {"tool_name": "Write"}
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 2

    def test_empty_file_path_stderr_contains_unable_to_parse(
        self, tmp_path: Path
    ) -> None:
        # BC-1.8: empty file_path must produce the exact error message on stderr
        stdin = {"tool_name": "Write", "tool_input": {"file_path": ""}}
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert "Unable to parse tool invocation" in result.stderr, (
            f"Expected 'Unable to parse tool invocation' in stderr for empty path; "
            f"got: {result.stderr!r}"
        )

    def test_missing_tool_input_key_stderr_contains_unable_to_parse(
        self, tmp_path: Path
    ) -> None:
        # BC-1.8: missing tool_input key must produce the exact error message on stderr
        stdin = {"tool_name": "Write"}
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert "Unable to parse tool invocation" in result.stderr, (
            f"Expected 'Unable to parse tool invocation' in stderr for missing "
            f"tool_input; got: {result.stderr!r}"
        )

    def test_parse_failure_does_not_exit_0(self, tmp_path: Path) -> None:
        result = subprocess.run(
            ["bash", str(_SCRIPT_PATH)],
            input="",
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={
                **os.environ,
                "CLAUDE_PLUGIN_ROOT": str(_UNIT_ROOT),
                "PWD": str(tmp_path),
            },
        )
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# BC-1.9  Path escaping (write outside project directory)
# ---------------------------------------------------------------------------


class TestCheckWriteAuthPathEscaping:
    """BC-1.9 — writes outside $PWD/ must exit 2 with the project-directory error."""

    def test_write_to_absolute_path_outside_project_root_exits_2(
        self, tmp_path: Path
    ) -> None:
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        outside_path = tmp_path / "other" / "file.txt"
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(outside_path)},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(project_dir),
            env_overrides={"PWD": str(project_dir)},
        )
        assert result.returncode == 2

    def test_write_outside_project_directory_stderr_message(
        self, tmp_path: Path
    ) -> None:
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        outside_path = tmp_path / "etc" / "passwd"
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(outside_path)},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(project_dir),
            env_overrides={"PWD": str(project_dir)},
        )
        assert "Write outside project directory is not permitted" in result.stderr, (
            f"Expected project-directory error in stderr; got: {result.stderr!r}"
        )

    def test_write_to_path_with_directory_traversal_exits_2(
        self, tmp_path: Path
    ) -> None:
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        # Traversal attempt: project/../other/file
        traversal = str(project_dir) + "/../other/file.txt"
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": traversal},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(project_dir),
            env_overrides={"PWD": str(project_dir)},
        )
        assert result.returncode == 2

    def test_write_inside_project_root_is_not_rejected_for_path_escaping(
        self, tmp_path: Path
    ) -> None:
        # A path clearly inside $PWD should not trigger the path-escaping error
        # (may still fail style-lock, but that's a different error)
        (tmp_path / "deck_state.json").write_text(
            json.dumps({"style_locked": True}), encoding="utf-8"
        )
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "notes.md")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert "Write outside project directory" not in result.stderr


# ---------------------------------------------------------------------------
# BC-1.10  Style-lock enforcement
# ---------------------------------------------------------------------------


class TestCheckWriteAuthStyleLockEnforcement:
    """BC-1.10 — style-lock enforcement."""

    def _make_deck_state(self, tmp_path: Path, style_locked: object) -> None:
        (tmp_path / "deck_state.json").write_text(
            json.dumps({"style_locked": style_locked}), encoding="utf-8"
        )

    def test_write_to_slides_dir_without_style_lock_exits_2(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "slides").mkdir()
        self._make_deck_state(tmp_path, False)
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "slides" / "intro.html")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 2

    def test_write_to_slides_dir_without_style_lock_has_correct_stderr_message(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "slides").mkdir()
        self._make_deck_state(tmp_path, False)
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "slides" / "intro.html")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert "Style config not yet locked" in result.stderr, (
            f"Expected style-lock error in stderr; got: {result.stderr!r}"
        )

    def test_style_lock_error_message_instructs_to_run_debrief_style(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "slides").mkdir()
        self._make_deck_state(tmp_path, False)
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "slides" / "title.html")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert "/debrief:style" in result.stderr, (
            f"Error message must reference /debrief:style; got: {result.stderr!r}"
        )

    def test_write_to_slides_dir_with_style_locked_true_exits_0(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "slides").mkdir()
        self._make_deck_state(tmp_path, True)
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "slides" / "intro.html")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 0

    def test_write_to_assets_style_css_without_style_lock_exits_2(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "assets").mkdir()
        self._make_deck_state(tmp_path, False)
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "assets" / "style.css")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 2

    def test_write_to_assets_style_css_with_style_locked_true_exits_0(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "assets").mkdir()
        self._make_deck_state(tmp_path, True)
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "assets" / "style.css")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 0

    def test_write_to_slides_dir_when_deck_state_json_absent_exits_2(
        self, tmp_path: Path
    ) -> None:
        # No deck_state.json present => style_locked is absent => must block
        (tmp_path / "slides").mkdir()
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "slides" / "intro.html")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 2

    def test_write_to_slides_dir_when_style_locked_is_string_true_exits_0(
        self, tmp_path: Path
    ) -> None:
        # The bash script reads with jq; boolean true in JSON is canonical
        (tmp_path / "slides").mkdir()
        self._make_deck_state(tmp_path, True)
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "slides" / "body.html")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 0

    def test_write_to_assets_other_file_with_unlocked_style_exits_0(
        self, tmp_path: Path
    ) -> None:
        # assets/images/logo.png is NOT the protected assets/style.css
        (tmp_path / "assets" / "images").mkdir(parents=True)
        self._make_deck_state(tmp_path, False)
        stdin = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / "assets" / "images" / "logo.png")
            },
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 0

    def test_write_to_slides_dir_when_style_locked_key_absent_in_deck_state_exits_2(
        self, tmp_path: Path
    ) -> None:
        # BC-1.10: deck_state.json exists but style_locked key is absent — must block
        (tmp_path / "slides").mkdir()
        (tmp_path / "deck_state.json").write_text(
            json.dumps({"project_name": "test"}), encoding="utf-8"
        )
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "slides" / "intro.html")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 2, (
            "When deck_state.json exists but style_locked key is absent, "
            "write to slides/ must be blocked (exit 2)"
        )

    def test_write_to_assets_style_css_when_style_locked_key_absent_in_deck_state_exits_2(
        self, tmp_path: Path
    ) -> None:
        # BC-1.10: deck_state.json exists but style_locked key is absent — must block
        (tmp_path / "assets").mkdir()
        (tmp_path / "deck_state.json").write_text(
            json.dumps({"project_name": "test"}), encoding="utf-8"
        )
        stdin = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "assets" / "style.css")},
        }
        result = _run_auth_script(
            stdin,
            cwd=str(tmp_path),
            env_overrides={"PWD": str(tmp_path)},
        )
        assert result.returncode == 2, (
            "When deck_state.json exists but style_locked key is absent, "
            "write to assets/style.css must be blocked (exit 2)"
        )


# ---------------------------------------------------------------------------
# BC-1.12  VERSIONS.md format for vendor assets
# ---------------------------------------------------------------------------

REQUIRED_VENDOR_FILES = {
    "mermaid.min.js",
    "rough.min.js",
    "katex.min.js",
    "katex.min.css",
}

_VERSIONS_MD_ENTRY_RE = re.compile(
    r"^(?P<filename>\S+)\t"
    r"version (?P<ver>\S+)\t"
    r"sha256:(?P<hash>[0-9a-fA-F]{64})\t"
    r"(?P<url>https?://\S+)$"
)


class TestVersionsMdFormat:
    """BC-1.12 — VERSIONS.md vendor file format."""

    @pytest.fixture(scope="class")
    def versions_entries(self) -> dict[str, re.Match]:
        path = _unit("assets/vendor/VERSIONS.md")
        assert path.exists(), f"assets/vendor/VERSIONS.md not found at {path}"
        entries: dict[str, re.Match] = {}
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                m = _VERSIONS_MD_ENTRY_RE.match(line)
                assert m is not None, f"VERSIONS.md line {lineno} bad format: {line!r}"
                entries[m.group("filename")] = m
        return entries

    def test_versions_md_exists(self) -> None:
        assert _unit("assets/vendor/VERSIONS.md").exists()

    def test_mermaid_min_js_is_listed_in_versions_md(
        self, versions_entries: dict
    ) -> None:
        assert "mermaid.min.js" in versions_entries

    def test_rough_min_js_is_listed_in_versions_md(
        self, versions_entries: dict
    ) -> None:
        assert "rough.min.js" in versions_entries

    def test_katex_min_js_is_listed_in_versions_md(
        self, versions_entries: dict
    ) -> None:
        assert "katex.min.js" in versions_entries

    def test_katex_min_css_is_listed_in_versions_md(
        self, versions_entries: dict
    ) -> None:
        assert "katex.min.css" in versions_entries

    def test_all_vendor_files_excluding_license_and_versions_have_entries(
        self, versions_entries: dict
    ) -> None:
        vendor_dir = _unit("assets/vendor")
        assert vendor_dir.is_dir()
        actual_files: list[str] = []
        for p in vendor_dir.rglob("*"):
            if (
                p.is_file()
                and p.name != "VERSIONS.md"
                and not p.name.endswith(".LICENSE.txt")
            ):
                rel = str(p.relative_to(vendor_dir))
                actual_files.append(rel)
        missing = [f for f in actual_files if f not in versions_entries]
        assert missing == [], f"These vendor files lack a VERSIONS.md entry: {missing}"

    def test_katex_fonts_woff2_files_are_listed_in_versions_md(
        self, versions_entries: dict
    ) -> None:
        vendor_dir = _unit("assets/vendor")
        katex_fonts_dir = vendor_dir / "katex-fonts"
        if not katex_fonts_dir.is_dir():
            pytest.skip("katex-fonts/ directory not present in vendor assets")
        woff2_files = list(katex_fonts_dir.glob("*.woff2"))
        assert len(woff2_files) > 0, (
            "katex-fonts/ must contain at least one .woff2 file"
        )
        for wf in woff2_files:
            rel = str(wf.relative_to(vendor_dir))
            assert rel in versions_entries, (
                f"katex font file {rel} must be listed in VERSIONS.md"
            )

    def test_every_versions_md_entry_has_sha256_hash_of_correct_length(
        self, versions_entries: dict
    ) -> None:
        for filename, match in versions_entries.items():
            h = match.group("hash")
            assert len(h) == 64, f"{filename} hash length {len(h)}, expected 64"

    def test_every_versions_md_entry_has_source_url(
        self, versions_entries: dict
    ) -> None:
        for filename, match in versions_entries.items():
            url = match.group("url")
            assert url.startswith("http"), (
                f"VERSIONS.md entry for {filename} missing valid source URL: {url!r}"
            )


# ---------------------------------------------------------------------------
# BC-1.13  archetypes.json completeness
# ---------------------------------------------------------------------------

EXPECTED_ARCHETYPE_KEYS = {
    "lab_meeting",
    "conference_talk",
    "seminar",
    "lecture",
    "journal_club",
    "grant_panel",
    "job_talk",
    "thesis_discussion",
    "investor_pitch",
    "custom",
}

REQUIRED_ARCHETYPE_FIELDS = {
    "presentation_type",
    "time_default",
    "time_range",
    "slide_density",
    "disclosure_emphasis",
    "narrative_style",
    "audience_implied",
    "audience_default",
    "acknowledgment",
    "handout_default",
    "series_default",
    "sub_modes",
    "rhetorical_emphasis",
    "consultant_instructions",
    "key_defaults_text",
    "content_signal_defaults",
    "expected_deliverables",
}


class TestArchetypesJsonCompleteness:
    """BC-1.13 — archetypes.json completeness."""

    @pytest.fixture(scope="class")
    def archetypes(self) -> dict:
        path = _unit("archetypes.json")
        assert path.exists(), f"archetypes.json not found at {path}"
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_archetypes_json_exists(self) -> None:
        assert _unit("archetypes.json").exists()

    def test_archetypes_json_has_exactly_eight_top_level_keys(
        self, archetypes: dict
    ) -> None:
        assert set(archetypes.keys()) == EXPECTED_ARCHETYPE_KEYS, (
            f"archetypes.json must have exactly keys {EXPECTED_ARCHETYPE_KEYS}; "
            f"found: {set(archetypes.keys())}"
        )

    def test_archetypes_json_has_no_extra_top_level_keys(
        self, archetypes: dict
    ) -> None:
        extra = set(archetypes.keys()) - EXPECTED_ARCHETYPE_KEYS
        assert extra == set(), f"archetypes.json has unexpected keys: {extra}"

    @pytest.mark.parametrize("archetype", sorted(EXPECTED_ARCHETYPE_KEYS))
    def test_each_archetype_entry_has_all_six_required_fields(
        self, archetype: str, archetypes: dict
    ) -> None:
        entry = archetypes.get(archetype, {})
        missing = REQUIRED_ARCHETYPE_FIELDS - set(entry.keys())
        assert missing == set(), (
            f"archetype '{archetype}' is missing required fields: {missing}"
        )

    @pytest.mark.parametrize("archetype", sorted(EXPECTED_ARCHETYPE_KEYS))
    def test_each_archetype_entry_has_no_extra_fields(
        self, archetype: str, archetypes: dict
    ) -> None:
        entry = archetypes.get(archetype, {})
        extra = set(entry.keys()) - REQUIRED_ARCHETYPE_FIELDS
        assert extra == set(), f"archetype '{archetype}' has unexpected fields: {extra}"

    @pytest.mark.parametrize("archetype", sorted(EXPECTED_ARCHETYPE_KEYS))
    def test_each_archetype_entry_is_a_dict(
        self, archetype: str, archetypes: dict
    ) -> None:
        assert isinstance(archetypes.get(archetype), dict), (
            f"archetypes['{archetype}'] must be a dict"
        )

    @pytest.mark.parametrize("archetype", sorted(EXPECTED_ARCHETYPE_KEYS))
    def test_each_archetype_presentation_type_is_a_non_empty_string(
        self, archetype: str, archetypes: dict
    ) -> None:
        val = archetypes.get(archetype, {}).get("presentation_type", "")
        assert isinstance(val, str) and val, (
            f"archetypes['{archetype}']['presentation_type'] must be a non-empty string"
        )


# ---------------------------------------------------------------------------
# BC-1.14  README.md sections
# ---------------------------------------------------------------------------

REQUIRED_README_SECTIONS = {
    "Installation",
    "First Run",
    "Quick Start",
    "Troubleshooting",
    "Uninstallation",
    "Dependencies",
    "Acknowledgments",
}


class TestReadmeSections:
    """BC-1.14 — README.md required sections."""

    @pytest.fixture(scope="class")
    def readme_text(self) -> str:
        path = _unit("README.md")
        assert path.exists(), f"README.md not found at {path}"
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_readme_md_exists(self) -> None:
        assert _unit("README.md").exists()

    @pytest.mark.parametrize("section", sorted(REQUIRED_README_SECTIONS))
    def test_readme_contains_required_section_heading(
        self, section: str, readme_text: str
    ) -> None:
        pattern = re.compile(
            r"^#{1,6}\s+" + re.escape(section), re.MULTILINE | re.IGNORECASE
        )
        assert pattern.search(readme_text), (
            f"README.md must include a section heading matching '{section}'"
        )

    def test_readme_acknowledgments_references_paperbanana(
        self, readme_text: str
    ) -> None:
        assert "PaperBanana" in readme_text, (
            "README.md Acknowledgments section must reference PaperBanana"
        )

    def test_readme_acknowledgments_includes_apache_2_0_attribution(
        self, readme_text: str
    ) -> None:
        assert "Apache-2.0" in readme_text or "Apache 2.0" in readme_text, (
            "README.md must include Apache-2.0 attribution for PaperBanana"
        )

    def test_readme_acknowledgments_includes_patent_risk_disclosure(
        self, readme_text: str
    ) -> None:
        patent_indicators = ["patent", "Patent"]
        assert any(kw in readme_text for kw in patent_indicators), (
            "README.md Acknowledgments must include patent risk disclosure"
        )

    def test_readme_does_not_instruct_user_to_run_conda_env_create_manually(
        self, readme_text: str
    ) -> None:
        assert "conda env create" not in readme_text, (
            "README.md must NOT instruct the user to run 'conda env create'"
        )

    def test_readme_does_not_instruct_user_to_run_conda_activate_manually(
        self, readme_text: str
    ) -> None:
        assert "conda activate" not in readme_text, (
            "README.md must NOT instruct the user to run 'conda activate'"
        )


# ---------------------------------------------------------------------------
# BC-1.15  NOTICE attribution
# ---------------------------------------------------------------------------


class TestNoticeAttribution:
    """BC-1.15 — NOTICE attribution."""

    @pytest.fixture(scope="class")
    def notice_text(self) -> str:
        path = _unit("NOTICE")
        assert path.exists(), f"NOTICE not found at {path}"
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_notice_file_exists(self) -> None:
        assert _unit("NOTICE").exists()

    def test_notice_attributes_paperbanana(self, notice_text: str) -> None:
        assert "PaperBanana" in notice_text, "NOTICE must attribute PaperBanana"

    def test_notice_includes_dwzhu_pku_paperbanana_repository_reference(
        self, notice_text: str
    ) -> None:
        assert "dwzhu-pku/PaperBanana" in notice_text, (
            "NOTICE must reference dwzhu-pku/PaperBanana"
        )

    def test_notice_includes_patent_risk_disclosure(self, notice_text: str) -> None:
        assert "patent" in notice_text.lower(), (
            "NOTICE must include patent risk disclosure"
        )

    def test_license_file_exists_with_apache_2_0_text(self) -> None:
        path = _unit("LICENSE")
        assert path.exists(), f"LICENSE not found at {path}"
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        assert "Apache License" in content and "Version 2.0" in content, (
            "LICENSE must contain verbatim Apache-2.0 license text"
        )

    def test_license_file_contains_apache_license_header(self) -> None:
        with open(_unit("LICENSE"), encoding="utf-8") as fh:
            content = fh.read()
        assert "Apache License" in content


# ---------------------------------------------------------------------------
# Additional structural checks
# ---------------------------------------------------------------------------


class TestPluginStructuralRequirements:
    """Verify the overall plugin directory structure exists as required."""

    def test_claude_plugin_directory_contains_only_plugin_json(self) -> None:
        claude_plugin_dir = _unit(".claude-plugin")
        assert claude_plugin_dir.is_dir()
        files = [p for p in claude_plugin_dir.iterdir() if p.is_file()]
        assert len(files) == 1 and files[0].name == "plugin.json", (
            ".claude-plugin/ must contain ONLY plugin.json;"
            f" found: {[f.name for f in files]}"
        )

    def test_bin_directory_contains_debrief_script(self) -> None:
        assert _unit("bin/debrief").exists(), "bin/debrief launcher script must exist"

    def test_bin_directory_contains_check_write_auth_script(self) -> None:
        assert _unit("bin/check-write-auth").exists()

    def test_hooks_directory_exists(self) -> None:
        assert _unit("hooks").is_dir()

    def test_agents_directory_exists(self) -> None:
        assert _unit("agents").is_dir()

    def test_templates_directory_contains_project_claude_md(self) -> None:
        assert _unit("templates/project_claude.md").exists(), (
            "templates/project_claude.md template must exist for REQ-INIT-3"
        )

    def test_project_claude_md_has_on_session_start_section(self) -> None:
        # BC-3.6a / BUG-AUDIT-11: the rendered CLAUDE.md must instruct the
        # consultant to read state files and dispatch on the first user turn,
        # because Claude Code agents don't auto-emit messages before user
        # input. The orchestration instructions live in a `## On Session Start`
        # section at the top of the file.
        template = _unit("templates/project_claude.md").read_text()
        assert "## On Session Start" in template, (
            "BC-3.6a / BUG-AUDIT-11: project_claude.md template must contain "
            "a `## On Session Start` section with orchestration instructions."
        )
        assert "debrief_state.json" in template, (
            "BC-3.6a / BUG-AUDIT-11: On Session Start section must reference "
            "`debrief_state.json` so the consultant knows to read it."
        )
        assert "sub_phase" in template, (
            "BC-3.6a / BUG-AUDIT-11: On Session Start section must reference "
            "the `sub_phase` field for dispatch logic."
        )
        assert "discovery/greeting" in template, (
            "BC-3.6a / BUG-AUDIT-11: On Session Start section must document "
            "the `discovery/greeting` sub_phase dispatch that emits the "
            "REQ-CONSULT-1 archetype greeting."
        )

    def test_assets_vendor_directory_exists(self) -> None:
        assert _unit("assets/vendor").is_dir()

    def test_mcp_json_file_exists(self) -> None:
        assert _unit(".mcp.json").exists(), ".mcp.json must exist (may be empty)"

    def test_changelog_md_exists(self) -> None:
        assert _unit("CHANGELOG.md").exists(), "CHANGELOG.md must exist"
