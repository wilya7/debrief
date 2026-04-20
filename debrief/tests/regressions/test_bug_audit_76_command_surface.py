# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-76.

BUG-AUDIT-76 adds a live command-surface enumeration (`debrief
commands`) and attaches three consultant obligations: on-session-start
invocation, post-compaction re-inject, and a pre-reply check before
denying any feature (*"Debrief does not have X"*) to prevent the
surface-amnesia failure mode.

TEST CLASSES:

1. TestListCommands — pure-function behavior on the real plugin
   commands directory + empty/missing-directory edge cases +
   malformed-file tolerance + heading-slug parsing.
2. TestMainCommandsCli — main_commands exits 0, prints JSON to
   stdout, JSON round-trips.
3. TestConsultantCommandSurfaceSection — consultant.md carries the
   ## Command Surface Awareness section with BUG-AUDIT-76 anchors,
   the live-enumeration invocation, the failure-mode naming, and
   the three obligations.
4. TestSpecAndBlueprintAnchors — spec + blueprint carry
   BUG-AUDIT-76 + REQ-CONSULT-CMD-SURFACE-1 + BC-3.17 + BC-5.18.

All tests run unconditionally in both workspace and delivered layouts;
zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-76 and
blueprint contracts BC-3.17 / BC-5.18.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_3").is_dir()


def _launcher_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_3"
    return _PROJECT_ROOT / "src" / "debrief"


def _real_plugin_root() -> Path:
    """Return a plugin_root whose `commands/` subdirectory exists and
    holds the shipped plugin commands.

    Workspace: ``src/unit_1/`` is the plugin-root analog (commands
    live at ``src/unit_1/commands/``).
    Delivered: the project root itself is the plugin root
    (commands live at ``commands/``).
    """
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1"
    return _PROJECT_ROOT


def _consultant_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    return _PROJECT_ROOT / "agents" / "consultant.md"


def _spec_path() -> Path:
    return _PROJECT_ROOT / "spec" / "stakeholder_spec.md"


def _blueprint_path() -> Path:
    return _PROJECT_ROOT / "blueprint" / "blueprint_contracts.md"


if str(_launcher_module_dir()) not in sys.path:
    sys.path.insert(0, str(_launcher_module_dir()))

from launcher import list_commands, main_commands  # noqa: E402


# ---------------------------------------------------------------------------
# Test class 1: list_commands
# ---------------------------------------------------------------------------


_EXPECTED_COMMANDS = [
    "export",
    "handout",
    "present",
    "quit",
    "restore",
    "save",
    "script",
    "slide",
    "style",
    "view",
]


class TestListCommands:
    def test_real_plugin_root_returns_all_known_commands(self) -> None:
        commands = list_commands(_real_plugin_root())
        for slug in _EXPECTED_COMMANDS:
            assert slug in commands, (
                f"Command {slug!r} missing from list_commands output. "
                f"Got keys: {sorted(commands.keys())}"
            )

    def test_descriptions_are_non_empty_strings(self) -> None:
        commands = list_commands(_real_plugin_root())
        for slug, desc in commands.items():
            assert isinstance(desc, str) and desc.strip(), (
                f"Description for {slug!r} is empty or not a string."
            )

    def test_descriptions_do_not_contain_heading_marker(self) -> None:
        # A description that contains "/debrief:" means the parser
        # confused the heading with the description — a bug in
        # list_commands.
        commands = list_commands(_real_plugin_root())
        for slug, desc in commands.items():
            assert "/debrief:" not in desc, (
                f"Description for {slug!r} contains the heading "
                f"marker '/debrief:' — parser regression. "
                f"Description: {desc!r}"
            )

    def test_missing_commands_dir_returns_empty_dict(
        self, tmp_path: Path
    ) -> None:
        # No commands/ subdirectory.
        assert list_commands(tmp_path) == {}

    def test_empty_commands_dir_returns_empty_dict(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "commands").mkdir()
        assert list_commands(tmp_path) == {}

    def test_non_md_files_in_commands_dir_are_ignored(
        self, tmp_path: Path
    ) -> None:
        cmds = tmp_path / "commands"
        cmds.mkdir()
        (cmds / "notes.txt").write_text("ignore me", encoding="utf-8")
        (cmds / "hello.md").write_text(
            "# /debrief:hello\n\nSay hello.\n",
            encoding="utf-8",
        )
        result = list_commands(tmp_path)
        assert list(result.keys()) == ["hello"]

    def test_file_without_heading_is_skipped(
        self, tmp_path: Path
    ) -> None:
        cmds = tmp_path / "commands"
        cmds.mkdir()
        (cmds / "stray.md").write_text(
            "Some content without the /debrief: heading.\n",
            encoding="utf-8",
        )
        assert list_commands(tmp_path) == {}

    def test_file_with_heading_but_no_description_is_skipped(
        self, tmp_path: Path
    ) -> None:
        cmds = tmp_path / "commands"
        cmds.mkdir()
        (cmds / "empty_desc.md").write_text(
            "# /debrief:empty_desc\n\n",
            encoding="utf-8",
        )
        assert list_commands(tmp_path) == {}

    def test_multiline_description_joined_with_space(
        self, tmp_path: Path
    ) -> None:
        cmds = tmp_path / "commands"
        cmds.mkdir()
        (cmds / "multi.md").write_text(
            "# /debrief:multi\n\n"
            "First line of description.\n"
            "Second line of description.\n"
            "\n"
            "## Trigger\n",
            encoding="utf-8",
        )
        result = list_commands(tmp_path)
        assert result == {
            "multi": (
                "First line of description. "
                "Second line of description."
            )
        }

    def test_slug_from_heading_authoritative(
        self, tmp_path: Path
    ) -> None:
        # File named "wrong.md" but heading declares "right" —
        # the heading slug wins (and the regression will fire if
        # someone renames a file without updating the heading).
        cmds = tmp_path / "commands"
        cmds.mkdir()
        (cmds / "wrong.md").write_text(
            "# /debrief:right\n\nCorrect slug.\n",
            encoding="utf-8",
        )
        result = list_commands(tmp_path)
        assert "right" in result
        assert "wrong" not in result


# ---------------------------------------------------------------------------
# Test class 2: main_commands CLI
# ---------------------------------------------------------------------------


class TestMainCommandsCli:
    def test_exits_0_on_real_plugin_root(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as ei:
            main_commands(_real_plugin_root())
        assert ei.value.code == 0

    def test_stdout_is_pretty_printed_sorted_json(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            main_commands(_real_plugin_root())
        out = capsys.readouterr().out
        # Parses as JSON.
        parsed = json.loads(out)
        # Same content as direct helper call.
        direct = list_commands(_real_plugin_root())
        assert parsed == direct
        # Keys are sorted (the emitted JSON is sort_keys=True).
        assert list(parsed.keys()) == sorted(parsed.keys())
        # Pretty-printed (contains at least one indented line).
        assert "{\n" in out

    def test_missing_plugin_root_still_exits_0(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Enumeration on a project with no commands/ is not an error;
        # it is a valid empty-surface.
        with pytest.raises(SystemExit) as ei:
            main_commands(tmp_path)
        assert ei.value.code == 0
        assert json.loads(capsys.readouterr().out) == {}


# ---------------------------------------------------------------------------
# Test class 3: consultant.md carries the Command Surface Awareness section
# ---------------------------------------------------------------------------


class TestConsultantCommandSurfaceSection:
    def test_section_exists(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "## Command Surface Awareness" in text

    def test_section_cites_bug_audit_76(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-76" in text
        assert "REQ-CONSULT-CMD-SURFACE-1" in text
        assert "BC-5.18" in text

    def test_section_cites_live_enumeration_invocation(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        # The canonical invocation appears verbatim.
        assert "python -m debrief.launcher commands" in text
        assert "${CLAUDE_PLUGIN_ROOT}" in text

    def test_section_placement_between_drift_audit_and_brief(
        self,
    ) -> None:
        """The three compaction-recovery sections must appear as a
        trio, in order: State Drift Audit, Command Surface
        Awareness, Deck Brief Maintenance."""
        text = _consultant_md_path().read_text(encoding="utf-8")
        drift_pos = text.index("## State Drift Audit")
        cmd_pos = text.index("## Command Surface Awareness")
        brief_pos = text.index("## Deck Brief Maintenance")
        assert drift_pos < cmd_pos < brief_pos

    def test_section_names_the_failure_mode(self) -> None:
        """Section calls out the 'Debrief does not have X' failure
        mode so a future reader understands why the discipline
        exists."""
        text = _consultant_md_path().read_text(encoding="utf-8")
        # Look for the specific concrete example or the general
        # denial-without-check phrasing.
        found_example = "/debrief:present" in text
        found_phrase = "does not have" in text
        assert found_example or found_phrase, (
            "Section does not name the feature-denial failure mode"
        )

    def test_section_documents_three_obligations(self) -> None:
        """On-session-start + post-compaction + 'does Debrief have X'
        check — each must be recognizable."""
        text = _consultant_md_path().read_text(encoding="utf-8")
        # Case-insensitive match for each obligation.
        import re

        assert re.search(
            r"on session start|at every session start",
            text,
            re.IGNORECASE,
        )
        assert re.search(
            r"post-compaction|after (any )?compaction",
            text,
            re.IGNORECASE,
        )
        assert re.search(
            r"does Debrief have|feature denial|pre-reply check",
            text,
            re.IGNORECASE,
        )


# ---------------------------------------------------------------------------
# Test class 4: spec + blueprint anchors
# ---------------------------------------------------------------------------


class TestSpecAndBlueprintAnchors:
    def test_spec_has_bug_audit_76(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-76" in text

    def test_spec_has_req_consult_cmd_surface_1(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "REQ-CONSULT-CMD-SURFACE-1" in text

    def test_blueprint_has_bc_3_17(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        assert "BC-3.17" in text

    def test_blueprint_has_bc_5_18(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        assert "BC-5.18" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
