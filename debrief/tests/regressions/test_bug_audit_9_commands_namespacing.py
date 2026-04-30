# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-9.

Bug: debrief's 9 user-invocable workflows lived in `skills/<name>/SKILL.md`
with YAML frontmatter (`user-invocable: true`). That layout registered
them as BARE-named slash commands (`/slide`, `/save`, `/export`, etc.)
with only a `(debrief)` annotation — not as the namespaced form
`/debrief:slide`, `/debrief:save`, `/debrief:export`. Three of the nine
names collided with Claude Code built-ins.

Empirically, Claude Code's namespacing logic (`/<plugin>:<name>`) only
fires for plugins that put their commands in `commands/<plugin>_<name>.md`
(flat files, no YAML frontmatter, `# /<plugin>:<name>` heading). svp
demonstrates this layout working correctly; debrief's skills/ layout
did not. The docs at `code.claude.com/docs/en/plugins.md` claim skills
are always namespaced but empirical behavior in Claude Code v2.1.104
contradicts that claim — only commands/ produces the namespacing.

The fix migrated all 9 debrief workflows from
`skills/<name>/SKILL.md` → `commands/debrief_<name>.md`, matching svp's
working pattern. This file enforces the new layout with positive
assertions on commands/ and negative sentinels against the old skills/
layout. See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-9
and blueprint contract BC-1.2.
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


def _plugin_root() -> Path:
    """Return the plugin root in whichever repo layout we are in."""
    workspace = _PROJECT_ROOT / "src" / "unit_1"
    delivered = _PROJECT_ROOT  # delivered layout: plugin root at tests' grandparent
    for candidate in (workspace, delivered):
        if (candidate / ".claude-plugin" / "plugin.json").exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find plugin.json at {workspace}/.claude-plugin/ or "
        f"{delivered}/.claude-plugin/"
    )


_EXPECTED_COMMAND_FILES = {
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
    # BUG-AUDIT-82 (Cycle 2 Phase 4): /debrief:refresh-brief slash
    # command. Forces the rewrite agent to regenerate deck_brief.md
    # + output/audience.yaml on demand. One of the three rewrite
    # triggers per REQ-MEMORY-REWRITE-2.
    "refresh-brief.md",
}


# BUG-AUDIT-10: filenames are bare <name>.md with NO plugin prefix.
# Adding a `debrief_` prefix produces double-prefixed invocations like
# `/debrief:debrief_slide`.
_COMMAND_FILE_NAME_PATTERN = re.compile(r"^[a-z]+(?:-[a-z]+)*\.md$")


# ---------------------------------------------------------------------------
# BUG-AUDIT-9 regression tests.
# ---------------------------------------------------------------------------


class TestBugAudit9CommandsNamespacing:
    """BC-1.2 — commands/ layout for namespaced /debrief:* slash commands."""

    def test_commands_dir_exists(self) -> None:
        commands_dir = _plugin_root() / "commands"
        assert commands_dir.is_dir(), (
            "BC-1.2 / BUG-AUDIT-9: plugin root must contain a `commands/` "
            "directory. This is the canonical location for user-invocable "
            "slash commands with `/debrief:<name>` namespacing."
        )

    def test_all_nine_commands_present(self) -> None:
        commands_dir = _plugin_root() / "commands"
        actual = {p.name for p in commands_dir.iterdir() if p.is_file()}
        assert actual == _EXPECTED_COMMAND_FILES, (
            f"BC-1.2 / BUG-AUDIT-9: commands/ must contain exactly "
            f"{sorted(_EXPECTED_COMMAND_FILES)}, found {sorted(actual)}."
        )

    def test_command_files_use_bare_filename(self) -> None:
        # BUG-AUDIT-10: filenames must be <name>.md with no plugin prefix.
        commands_dir = _plugin_root() / "commands"
        for command_file in commands_dir.iterdir():
            if not command_file.is_file():
                continue
            assert _COMMAND_FILE_NAME_PATTERN.match(command_file.name), (
                f"BC-1.2 / BUG-AUDIT-10: command file {command_file.name} must "
                f"match the bare `<name>.md` naming convention. Filenames MUST "
                f"NOT include a plugin prefix like `debrief_`; Claude Code "
                f"prepends the namespace automatically from plugin.json."
            )

    def test_no_command_files_have_plugin_name_prefix(self) -> None:
        # BUG-AUDIT-10 negative sentinel: loading regression guard. Any
        # file in commands/ whose name starts with `debrief_` produces a
        # double-prefixed invocation like `/debrief:debrief_slide`.
        commands_dir = _plugin_root() / "commands"
        prefixed = [
            p.name for p in commands_dir.iterdir()
            if p.is_file() and p.name.startswith("debrief_")
        ]
        assert not prefixed, (
            f"BUG-AUDIT-10 regression: command files with `debrief_` prefix "
            f"found: {prefixed}. Claude Code prepends the `/debrief:` "
            f"namespace automatically; adding a plugin prefix to the "
            f"filename produces `/debrief:debrief_<name>` (double-prefixed). "
            f"Rename to bare `<name>.md`."
        )

    @pytest.mark.parametrize("command_file", sorted(_EXPECTED_COMMAND_FILES))
    def test_command_files_have_namespaced_heading(self, command_file: str) -> None:
        path = _plugin_root() / "commands" / command_file
        content = path.read_text(encoding="utf-8")
        first_nonblank = next(
            (line for line in content.splitlines() if line.strip()),
            "",
        )
        expected_name = command_file[:-len(".md")]
        expected_heading = f"# /debrief:{expected_name}"
        assert first_nonblank.strip() == expected_heading, (
            f"BC-1.2 / BUG-AUDIT-10: commands/{command_file} must start with "
            f"`{expected_heading}` as its first non-blank line. Got: "
            f"`{first_nonblank.strip()}`."
        )

    @pytest.mark.parametrize("command_file", sorted(_EXPECTED_COMMAND_FILES))
    def test_command_files_have_no_yaml_frontmatter(
        self, command_file: str
    ) -> None:
        # BUG-AUDIT-9 negative sentinel: command files are plain markdown.
        # Starting with `---` would indicate YAML frontmatter, which is
        # the pattern from the old SKILL.md layout. Catches a regression
        # to the old format.
        path = _plugin_root() / "commands" / command_file
        content = path.read_text(encoding="utf-8")
        assert not content.lstrip().startswith("---"), (
            f"BUG-AUDIT-9 regression: commands/{command_file} starts with "
            f"`---` (YAML frontmatter). Command files must be plain markdown "
            f"with no frontmatter. The frontmatter layout is the old "
            f"skills/<name>/SKILL.md format that produces bare-named slash "
            f"commands instead of namespaced ones."
        )

    def test_no_skills_user_invocable_skill_md_files(self) -> None:
        # BUG-AUDIT-9 negative sentinel: the old `skills/<name>/SKILL.md`
        # layout produced bare-named slash commands. If the skills/
        # directory exists at the plugin root, it must not contain any
        # SKILL.md files with `user-invocable: true` frontmatter.
        skills_dir = _plugin_root() / "skills"
        if not skills_dir.exists():
            return  # No skills/ — fine, the old layout was removed entirely.
        skill_md_files = list(skills_dir.rglob("SKILL.md"))
        for skill_md in skill_md_files:
            content = skill_md.read_text(encoding="utf-8")
            assert "user-invocable: true" not in content, (
                f"BUG-AUDIT-9 regression: {skill_md} contains "
                f"`user-invocable: true` in its frontmatter. User-invocable "
                f"workflows must live in commands/debrief_<name>.md (flat "
                f"files, no frontmatter), not skills/<name>/SKILL.md. See "
                f"BC-1.2."
            )
