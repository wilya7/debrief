# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Tests for Unit 3: Launcher.

Synthetic data generation assumptions
--------------------------------------
- ``plugin_root`` fixtures are created inside ``tmp_path`` with the minimal
  required directory tree:
    plugin_root/assets/vendor/VERSIONS.md
    plugin_root/assets/vendor/<listed files>
    plugin_root/templates/project_claude.md
    plugin_root/archetypes.json
  File contents are minimal valid synthetic data that satisfy VERSIONS.md
  format (tab-separated: filename, version, sha256:<hash>, url).
- SHA-256 hashes in VERSIONS.md are computed in-test via ``hashlib.sha256``
  over the exact bytes written to the corresponding vendor file, so the
  hash-match path is exercised with genuine matches.
- A mismatched VERSIONS.md entry is synthesised by writing a known hash that
  does NOT match the file content (a 64-character hex string of all zeros).
- ``project_root`` fixtures are fresh empty directories inside ``tmp_path``
  to satisfy BC-3.1's "empty or contains only CLAUDE.md" requirement.
- Archetype selection tests fake stdin via ``monkeypatch.setattr(sys, 'stdin',
  io.StringIO(...))``.
- The ``archetypes.json`` used in ``select_archetype`` tests contains the
  canonical eight keys: ``lab_meeting``, ``conference_talk``, ``seminar``,
  ``lecture``, ``journal_club``, ``grant_panel``, ``job_talk``, ``custom``.
- For BC-3.4/BC-3.5 initial state tests, the written JSON is read back via
  ``json.loads`` rather than through Unit 2's reader stubs, so tests verify
  the raw file content directly and are independent of Unit 2 delivery state.
- ``json_repair`` unavailability is simulated by patching
  ``importlib.util.find_spec`` to return ``None`` for the ``json_repair``
  query only.
- All timestamps produced by ``new()`` are only checked to be ISO 8601 strings
  (non-empty, containing 'T'), not to be exact values.
- The ``CLAUDE_PLUGIN_ROOT`` env variable is set in tests that need
  ``new()`` to locate the plugin root; it is restored after each test.
- ``create_project_structure`` is tested in an isolated empty ``tmp_path``
  to verify idempotency (calling twice must not raise).
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest
from launcher import (
    create_project_structure,
    new,
    preflight,
    render_project_claude_md,
    select_archetype,
    verify_vendor_hashes,
)

# ---------------------------------------------------------------------------
# Constants / helpers shared across tests
# ---------------------------------------------------------------------------

_ARCHETYPES = [
    "lab_meeting",
    "conference_talk",
    "seminar",
    "lecture",
    "journal_club",
    "grant_panel",
    "job_talk",
    "custom",
]

_VERSIONS_HEADER = (
    "# Vendor asset versions and provenance\n"
    "# Format: <filename>\\tversion <ver>\\tsha256:<hash>\\t<source_url>\n"
)


def _make_vendor_file(vendor_dir: Path, filename: str) -> str:
    """Write a synthetic vendor file; return its SHA-256 hex digest."""
    content = f"/* synthetic vendor content for {filename} */\n".encode()
    digest = hashlib.sha256(content).hexdigest()
    (vendor_dir / filename).write_bytes(content)
    return digest


def _make_versions_md(vendor_dir: Path, entries: list[tuple[str, str]]) -> None:
    """Write VERSIONS.md with the given (filename, sha256_hex) entries."""
    lines = [_VERSIONS_HEADER]
    for fname, sha in entries:
        lines.append(
            f"{fname}\tversion 1.0.0\tsha256:{sha}\thttps://example.com/{fname}\n"
        )
    (vendor_dir / "VERSIONS.md").write_text("".join(lines), encoding="utf-8")


def _make_plugin_root(tmp_path: Path) -> Path:
    """Build a minimal plugin_root tree with valid vendor hashes."""
    plugin_root = tmp_path / "plugin_root"
    vendor_dir = plugin_root / "assets" / "vendor"
    vendor_dir.mkdir(parents=True)

    vendor_files = ["mermaid.min.js", "rough.min.js", "katex.min.js"]
    entries = []
    for fname in vendor_files:
        digest = _make_vendor_file(vendor_dir, fname)
        entries.append((fname, digest))

    _make_versions_md(vendor_dir, entries)

    # templates
    templates_dir = plugin_root / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "project_claude.md").write_text(
        "# CLAUDE.md\nProject: {project_name}\n", encoding="utf-8"
    )

    # archetypes.json
    archetypes_data = {k: {"key": k} for k in _ARCHETYPES}
    (plugin_root / "archetypes.json").write_text(
        json.dumps(archetypes_data), encoding="utf-8"
    )

    return plugin_root


def _make_archetypes_json(path: Path) -> None:
    """Write a valid archetypes.json to ``path``."""
    data = {k: {"key": k} for k in _ARCHETYPES}
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# BC-3.9 — create_project_structure: idempotent mkdir
# ---------------------------------------------------------------------------


class TestCreateProjectStructure:
    """Tests for create_project_structure (BC-3.9)."""

    # Extended to 15 entries per BUG-AUDIT-15: the canonical project tree
    # must include `.debrief/`, `.debrief/draft/`, both preview subdirectories,
    # and `output/` explicitly so the Stylist's preview writes and any other
    # code that depends on the canonical tree never lands in a hole.
    _EXPECTED_DIRS = [
        ".debrief",
        ".debrief/briefs",
        ".debrief/draft",
        ".debrief/draft/preview_slides",
        ".debrief/draft/preview_images",
        ".debrief/snapshots",
        "assets/images",
        "assets/fonts",
        "assets/vendor",
        "assets/math",
        "assets/reference/slides",
        "assets/reference/papers",
        "slides",
        "output",
        "output/screenshots",
    ]

    def test_creates_all_required_subdirectories(self, tmp_path: Path) -> None:
        create_project_structure(tmp_path)
        for rel in self._EXPECTED_DIRS:
            assert (tmp_path / rel).is_dir(), (
                f"Expected directory {rel!r} to exist after create_project_structure"
            )

    def test_calling_twice_does_not_raise(self, tmp_path: Path) -> None:
        create_project_structure(tmp_path)
        # Second call must not raise (exist_ok=True on all mkdirs)
        create_project_structure(tmp_path)

    def test_assets_images_is_created(self, tmp_path: Path) -> None:
        create_project_structure(tmp_path)
        assert (tmp_path / "assets" / "images").is_dir()

    def test_debrief_snapshots_is_created(self, tmp_path: Path) -> None:
        create_project_structure(tmp_path)
        assert (tmp_path / ".debrief" / "snapshots").is_dir()

    def test_output_screenshots_is_created(self, tmp_path: Path) -> None:
        create_project_structure(tmp_path)
        assert (tmp_path / "output" / "screenshots").is_dir()


# ---------------------------------------------------------------------------
# BC-3.6 — render_project_claude_md
# ---------------------------------------------------------------------------


class TestRenderProjectClaudeMd:
    """Tests for render_project_claude_md (BC-3.6)."""

    def test_substitutes_project_name_placeholder(self, tmp_path: Path) -> None:
        template = tmp_path / "project_claude.md"
        template.write_text("# CLAUDE.md\nProject: {project_name}\n", encoding="utf-8")
        out_dir = tmp_path / "project"
        out_dir.mkdir()
        render_project_claude_md(template, out_dir, "my_presentation")
        result = (out_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert "my_presentation" in result
        assert "{project_name}" not in result

    def test_writes_to_project_root_slash_claude_md(self, tmp_path: Path) -> None:
        template = tmp_path / "tmpl.md"
        template.write_text("hello {project_name}", encoding="utf-8")
        out_dir = tmp_path / "proj"
        out_dir.mkdir()
        render_project_claude_md(template, out_dir, "alpha")
        assert (out_dir / "CLAUDE.md").exists()

    def test_leaves_unrecognized_tokens_unchanged(self, tmp_path: Path) -> None:
        template = tmp_path / "t.md"
        template.write_text(
            "Name: {project_name} Other: {unrelated_token}",
            encoding="utf-8",
        )
        out_dir = tmp_path / "proj2"
        out_dir.mkdir()
        render_project_claude_md(template, out_dir, "beta")
        result = (out_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert "{unrelated_token}" in result

    def test_substitutes_every_occurrence_of_project_name(self, tmp_path: Path) -> None:
        template = tmp_path / "t2.md"
        template.write_text("{project_name} and also {project_name}", encoding="utf-8")
        out_dir = tmp_path / "proj3"
        out_dir.mkdir()
        render_project_claude_md(template, out_dir, "gamma")
        result = (out_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert result.count("gamma") == 2
        assert "{project_name}" not in result

    def test_write_is_atomic_no_tmp_file_left_behind(self, tmp_path: Path) -> None:
        """The .tmp sibling must not persist after a successful render."""
        template = tmp_path / "t3.md"
        template.write_text("{project_name}", encoding="utf-8")
        out_dir = tmp_path / "proj4"
        out_dir.mkdir()
        render_project_claude_md(template, out_dir, "delta")
        tmp_sibling = out_dir / "CLAUDE.md.tmp"
        assert not tmp_sibling.exists()


# ---------------------------------------------------------------------------
# BC-3.8 — verify_vendor_hashes: failure format
# ---------------------------------------------------------------------------


class TestVerifyVendorHashes:
    """Tests for verify_vendor_hashes (BC-3.8)."""

    def test_passes_silently_when_all_hashes_match(self, tmp_path: Path) -> None:
        plugin_root = tmp_path / "pr"
        vendor_dir = plugin_root / "assets" / "vendor"
        vendor_dir.mkdir(parents=True)
        digest = _make_vendor_file(vendor_dir, "mermaid.min.js")
        _make_versions_md(vendor_dir, [("mermaid.min.js", digest)])
        # Should return None (no exception, no SystemExit)
        verify_vendor_hashes(plugin_root)

    def test_exits_1_when_hash_mismatches(self, tmp_path: Path) -> None:
        plugin_root = tmp_path / "pr"
        vendor_dir = plugin_root / "assets" / "vendor"
        vendor_dir.mkdir(parents=True)
        _make_vendor_file(vendor_dir, "mermaid.min.js")
        bad_hash = "0" * 64
        _make_versions_md(vendor_dir, [("mermaid.min.js", bad_hash)])
        with pytest.raises(SystemExit) as exc_info:
            verify_vendor_hashes(plugin_root)
        assert exc_info.value.code == 1

    def test_error_message_includes_filename(self, tmp_path: Path, capsys) -> None:
        plugin_root = tmp_path / "pr"
        vendor_dir = plugin_root / "assets" / "vendor"
        vendor_dir.mkdir(parents=True)
        _make_vendor_file(vendor_dir, "rough.min.js")
        bad_hash = "a" * 64
        _make_versions_md(vendor_dir, [("rough.min.js", bad_hash)])
        with pytest.raises(SystemExit):
            verify_vendor_hashes(plugin_root)
        captured = capsys.readouterr()
        assert "rough.min.js" in captured.err

    def test_error_message_includes_expected_hash(self, tmp_path: Path, capsys) -> None:
        plugin_root = tmp_path / "pr"
        vendor_dir = plugin_root / "assets" / "vendor"
        vendor_dir.mkdir(parents=True)
        _make_vendor_file(vendor_dir, "katex.min.js")
        expected_hash = "b" * 64
        _make_versions_md(vendor_dir, [("katex.min.js", expected_hash)])
        with pytest.raises(SystemExit):
            verify_vendor_hashes(plugin_root)
        captured = capsys.readouterr()
        assert expected_hash in captured.err

    def test_error_message_includes_actual_hash(self, tmp_path: Path, capsys) -> None:
        plugin_root = tmp_path / "pr"
        vendor_dir = plugin_root / "assets" / "vendor"
        vendor_dir.mkdir(parents=True)
        content = b"real content here"
        actual_hash = hashlib.sha256(content).hexdigest()
        (vendor_dir / "katex.min.css").write_bytes(content)
        wrong_hash = "c" * 64
        _make_versions_md(vendor_dir, [("katex.min.css", wrong_hash)])
        with pytest.raises(SystemExit):
            verify_vendor_hashes(plugin_root)
        captured = capsys.readouterr()
        assert actual_hash in captured.err

    def test_error_message_includes_verbatim_recovery_instruction(
        self, tmp_path: Path, capsys
    ) -> None:
        plugin_root = tmp_path / "pr"
        vendor_dir = plugin_root / "assets" / "vendor"
        vendor_dir.mkdir(parents=True)
        _make_vendor_file(vendor_dir, "mermaid.min.js")
        _make_versions_md(vendor_dir, [("mermaid.min.js", "d" * 64)])
        with pytest.raises(SystemExit):
            verify_vendor_hashes(plugin_root)
        captured = capsys.readouterr()
        assert "Plugin assets appear corrupted" in captured.err
        assert "Reinstall the Debrief plugin" in captured.err

    def test_error_message_goes_to_stderr_not_stdout(
        self, tmp_path: Path, capsys
    ) -> None:
        plugin_root = tmp_path / "pr"
        vendor_dir = plugin_root / "assets" / "vendor"
        vendor_dir.mkdir(parents=True)
        _make_vendor_file(vendor_dir, "mermaid.min.js")
        _make_versions_md(vendor_dir, [("mermaid.min.js", "e" * 64)])
        with pytest.raises(SystemExit):
            verify_vendor_hashes(plugin_root)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert len(captured.err) > 0


# ---------------------------------------------------------------------------
# BC-3.1 — new(): non-empty project rejection
# ---------------------------------------------------------------------------


class TestNewNonEmptyProjectRejection:
    """Tests for new() rejecting non-empty project roots (BC-3.1)."""

    def test_exits_1_when_project_root_contains_unexpected_file(
        self, tmp_path: Path
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        (project_root / "some_file.txt").write_text("content")
        with pytest.raises(SystemExit) as exc_info:
            new(project_root)
        assert exc_info.value.code == 1

    def test_exits_1_when_project_root_contains_unexpected_directory(
        self, tmp_path: Path
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        (project_root / "subdir").mkdir()
        with pytest.raises(SystemExit) as exc_info:
            new(project_root)
        assert exc_info.value.code == 1

    def test_allows_empty_project_root(self, tmp_path: Path, monkeypatch) -> None:
        """An empty project_root must NOT trigger the exit-1 guard."""
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        # Provide archetype to skip interactive prompt
        new(project_root, archetype="lab_meeting")
        # If we reach here, the guard did not fire

    def test_allows_project_root_containing_only_claude_md(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A project_root containing only CLAUDE.md is allowed."""
        project_root = tmp_path / "proj"
        project_root.mkdir()
        (project_root / "CLAUDE.md").write_text("# existing")
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype="lab_meeting")

    def test_does_not_create_files_before_exiting_on_nonempty_root(
        self, tmp_path: Path
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        (project_root / "blocker.txt").write_text("boom")
        with pytest.raises(SystemExit):
            new(project_root)
        # No deck_state.json must have been written
        assert not (project_root / "deck_state.json").exists()


# ---------------------------------------------------------------------------
# BC-3.2 / BC-3.3 — select_archetype: prompt format and re-prompt once
# ---------------------------------------------------------------------------


class TestSelectArchetype:
    """Tests for select_archetype prompt behaviour (BC-3.2, BC-3.3)."""

    def _write_archetypes(self, tmp_path: Path) -> Path:
        p = tmp_path / "archetypes.json"
        _make_archetypes_json(p)
        return p

    def test_returns_archetype_value_for_valid_number_input(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
        result = select_archetype(archetypes_path)
        assert result == "lab_meeting"

    def test_returns_archetype_value_for_valid_name_input(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("seminar\n"))
        result = select_archetype(archetypes_path)
        assert result == "seminar"

    def test_name_input_is_case_insensitive(self, tmp_path: Path, monkeypatch) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("LAB_MEETING\n"))
        result = select_archetype(archetypes_path)
        assert result == "lab_meeting"

    def test_returns_last_archetype_for_number_8(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("8\n"))
        result = select_archetype(archetypes_path)
        assert result == "custom"

    def test_repromptes_once_on_first_invalid_input(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        # First input invalid, second valid
        monkeypatch.setattr(sys, "stdin", io.StringIO("invalid\nlecture\n"))
        result = select_archetype(archetypes_path)
        assert result == "lecture"

    def test_exits_1_on_second_invalid_input(self, tmp_path: Path, monkeypatch) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("bad_one\nbad_two\n"))
        with pytest.raises(SystemExit) as exc_info:
            select_archetype(archetypes_path)
        assert exc_info.value.code == 1

    def test_second_invalid_error_message_content(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("wrong\nalso_wrong\n"))
        with pytest.raises(SystemExit):
            select_archetype(archetypes_path)
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        # The required error message per BC-3.3
        assert "Invalid selection" in combined
        assert "debrief new" in combined

    def test_does_not_loop_after_second_invalid_input(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Exactly two prompts; does not read a third line."""
        archetypes_path = self._write_archetypes(tmp_path)
        # Only two lines provided; if it loops, it would raise StopIteration
        monkeypatch.setattr(sys, "stdin", io.StringIO("nope\nalso_nope\n"))
        with pytest.raises(SystemExit):
            select_archetype(archetypes_path)

    def test_prompt_is_printed_to_stdout(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
        select_archetype(archetypes_path)
        captured = capsys.readouterr()
        # Prompt must appear on stdout
        assert len(captured.out) > 0

    def test_prompt_lists_all_eight_archetypes(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
        select_archetype(archetypes_path)
        captured = capsys.readouterr()
        for archetype in _ARCHETYPES:
            assert archetype in captured.out.lower(), (
                f"Archetype {archetype!r} missing from prompt"
            )

    def test_prompt_uses_numbered_list(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
        select_archetype(archetypes_path)
        captured = capsys.readouterr()
        # Numbers 1-8 must appear
        for n in range(1, 9):
            assert str(n) in captured.out, f"Number {n} missing from archetype prompt"


# ---------------------------------------------------------------------------
# BC-3.4 — new(): initial deck_state values
# ---------------------------------------------------------------------------


class TestNewInitialDeckStateValues:
    """Tests for new() writing correct initial deck_state.json (BC-3.4)."""

    def _run_new(
        self,
        tmp_path: Path,
        monkeypatch,
        archetype: str = "lab_meeting",
    ) -> dict:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype=archetype)
        return json.loads(
            (project_root / "deck_state.json").read_text(encoding="utf-8")
        )

    def test_style_locked_is_false(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["style_locked"] is False

    def test_slides_is_empty_list(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["slides"] == []

    def test_presentations_is_empty_list(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["presentations"] == []

    def test_closing_slide_is_null(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["closing_slide"] is None

    def test_project_name_is_directory_basename(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_root = tmp_path / "my_presentation"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype="lab_meeting")
        state = json.loads(
            (project_root / "deck_state.json").read_text(encoding="utf-8")
        )
        assert state["project_name"] == "my_presentation"

    def test_archetype_matches_selected_value(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        state = self._run_new(tmp_path, monkeypatch, archetype="seminar")
        assert state["archetype"] == "seminar"

    def test_created_at_is_iso8601_timestamp(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        created_at = state["created_at"]
        assert isinstance(created_at, str)
        assert "T" in created_at, (
            f"created_at {created_at!r} is not ISO 8601 (missing 'T')"
        )


# ---------------------------------------------------------------------------
# BC-3.5 — new(): initial debrief_state values
# ---------------------------------------------------------------------------


class TestNewInitialDebriefStateValues:
    """Tests for new() writing correct initial debrief_state.json (BC-3.5)."""

    def _run_new(
        self,
        tmp_path: Path,
        monkeypatch,
        archetype: str = "lab_meeting",
    ) -> dict:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype=archetype)
        return json.loads(
            (project_root / "debrief_state.json").read_text(encoding="utf-8")
        )

    def test_phase_is_discovery(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["phase"] == "discovery"

    def test_sub_phase_is_greeting(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        # BC-3.5 says sub_phase: "greeting"; full value is
        # "discovery/greeting" per the sub_phase enum convention
        assert "greeting" in state["sub_phase"]

    def test_active_agent_is_consultant(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["active_agent"] == "consultant"

    def test_red_green_iteration_is_zero(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["red_green_iteration"] == 0

    def test_red_green_started_at_is_null(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["red_green_started_at"] is None

    def test_group_slide_index_is_zero(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["group_slide_index"] == 0

    def test_group_slide_count_is_zero(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["group_slide_count"] == 0

    def test_completed_groups_is_empty_list(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["completed_groups"] == []

    def test_last_gate_response_is_null(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["last_gate_response"] is None

    def test_backup_mode_is_false(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["backup_mode"] is False

    def test_closing_slide_pending_is_false(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["closing_slide_pending"] is False

    def test_view_deferred_is_false(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["view_deferred"] is False

    def test_reference_provided_is_false(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["reference_provided"] is False

    def test_papers_provided_is_false(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert state["papers_provided"] is False

    def test_state_hash_is_present_and_nonempty(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        assert isinstance(state.get("state_hash"), str)
        assert len(state["state_hash"]) == 64  # SHA-256 hex digest length

    def test_nullable_fields_are_null(self, tmp_path: Path, monkeypatch) -> None:
        state = self._run_new(tmp_path, monkeypatch)
        nullable_fields = [
            "current_group_id",
            "current_slide_slug",
            "pending_gate",
            "pre_view_state",
            "group_revise_slug",
            "style_import_mode",
            "reference_modality",
            "selected_figures",
        ]
        for field in nullable_fields:
            assert state.get(field) is None, (
                f"Expected {field!r} to be null in initial debrief_state"
            )


# ---------------------------------------------------------------------------
# BC-3.7 — new(): vendor copy
# ---------------------------------------------------------------------------


class TestNewVendorCopy:
    """Tests for new() copying vendor assets (BC-3.7)."""

    def test_vendor_files_are_copied_to_project_root(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype="lab_meeting")
        for fname in ["mermaid.min.js", "rough.min.js", "katex.min.js"]:
            dest = project_root / "assets" / "vendor" / fname
            assert dest.exists(), f"Expected vendor file {fname!r} to be copied"

    def test_vendor_file_contents_are_preserved(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        # Record original content
        src = plugin_root / "assets" / "vendor" / "mermaid.min.js"
        original_bytes = src.read_bytes()
        new(project_root, archetype="lab_meeting")
        dest = project_root / "assets" / "vendor" / "mermaid.min.js"
        assert dest.read_bytes() == original_bytes

    def test_exits_1_when_vendor_directory_is_missing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = tmp_path / "plugin_root_no_vendor"
        plugin_root.mkdir()
        # No assets/vendor directory
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        with pytest.raises(SystemExit) as exc_info:
            new(project_root, archetype="lab_meeting")
        assert exc_info.value.code == 1

    def test_exits_1_when_vendor_directory_is_empty(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = tmp_path / "plugin_root_empty_vendor"
        plugin_root.mkdir()
        (plugin_root / "assets" / "vendor").mkdir(parents=True)
        monkeypatch.setenv(
            "CLAUDE_PLUGIN_ROOT", str(plugin_root)
        )
        with pytest.raises(SystemExit) as exc_info:
            new(project_root, archetype="lab_meeting")
        assert exc_info.value.code == 1

    def test_versions_md_is_copied_to_project_vendor(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype="lab_meeting")
        assert (project_root / "assets" / "vendor" / "VERSIONS.md").exists()


# ---------------------------------------------------------------------------
# BC-3.1 (error output) — error printed before exit
# ---------------------------------------------------------------------------


class TestNewErrorOutputOnNonEmptyRoot:
    """Tests that new() prints an error message when project_root is dirty."""

    def test_prints_error_message_to_stderr_or_stdout_on_nonempty_root(
        self, tmp_path: Path, capsys
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        (project_root / "leftover.txt").write_text("junk")
        with pytest.raises(SystemExit):
            new(project_root)
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert len(combined) > 0, "Expected an error message but nothing was printed"


# ---------------------------------------------------------------------------
# BC-3.11 — json_repair entry check in preflight and new/main_new
# ---------------------------------------------------------------------------


class TestJsonRepairEntryCheck:
    """Tests for json_repair entry check per BC-3.11."""

    def test_preflight_exits_2_when_json_repair_unavailable(
        self, tmp_path: Path
    ) -> None:
        plugin_root = _make_plugin_root(tmp_path)

        def fake_find_spec(name: str):
            if name == "json_repair":
                return None
            return importlib.util.find_spec(name)

        with mock.patch("importlib.util.find_spec", side_effect=fake_find_spec):
            with pytest.raises(SystemExit) as exc_info:
                preflight(plugin_root)
        assert exc_info.value.code == 2

    def test_preflight_exit_2_message_is_env_corruption_error(
        self, tmp_path: Path, capsys
    ) -> None:
        plugin_root = _make_plugin_root(tmp_path)

        def fake_find_spec(name: str):
            if name == "json_repair":
                return None
            return importlib.util.find_spec(name)

        with mock.patch("importlib.util.find_spec", side_effect=fake_find_spec):
            with pytest.raises(SystemExit):
                preflight(plugin_root)
        captured = capsys.readouterr()
        # Section 9.3.1 env-corruption message must appear on stderr
        combined = captured.out + captured.err
        low = combined.lower()
        assert "json_repair" in low or "environment" in low or "corrupt" in low

    def test_new_exits_2_when_json_repair_unavailable(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))

        def fake_find_spec(name: str):
            if name == "json_repair":
                return None
            return importlib.util.find_spec(name)

        with mock.patch("importlib.util.find_spec", side_effect=fake_find_spec):
            with pytest.raises(SystemExit) as exc_info:
                new(project_root, archetype="lab_meeting")
        assert exc_info.value.code == 2

    def test_new_exit_2_error_message_goes_to_stderr(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))

        def fake_find_spec(name: str):
            if name == "json_repair":
                return None
            return importlib.util.find_spec(name)

        with mock.patch("importlib.util.find_spec", side_effect=fake_find_spec):
            with pytest.raises(SystemExit):
                new(project_root, archetype="lab_meeting")
        captured = capsys.readouterr()
        assert len(captured.err) > 0


# ---------------------------------------------------------------------------
# BC-3.1 combined: project created when root is clean
# ---------------------------------------------------------------------------


class TestNewCreatesRequiredFiles:
    """Integration: new() creates all required files (BC-3.4–3.7)."""

    def test_deck_state_json_is_created(self, tmp_path: Path, monkeypatch) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype="lab_meeting")
        assert (project_root / "deck_state.json").exists()

    def test_debrief_state_json_is_created(self, tmp_path: Path, monkeypatch) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype="lab_meeting")
        assert (project_root / "debrief_state.json").exists()

    def test_claude_md_is_created(self, tmp_path: Path, monkeypatch) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype="lab_meeting")
        assert (project_root / "CLAUDE.md").exists()

    def test_project_structure_directories_are_created(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype="lab_meeting")
        assert (project_root / "slides").is_dir()
        assert (project_root / "assets" / "images").is_dir()
        assert (project_root / ".debrief" / "briefs").is_dir()


# ---------------------------------------------------------------------------
# BC-3.6 — CLAUDE.md contains rendered project_name
# ---------------------------------------------------------------------------


class TestNewRendersProjectName:
    """Tests that new() correctly renders project_name into CLAUDE.md."""

    def test_claude_md_contains_project_directory_basename(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_root = tmp_path / "my_cool_project"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype="lab_meeting")
        content = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
        assert "my_cool_project" in content

    def test_claude_md_does_not_contain_raw_placeholder(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_root = tmp_path / "any_project"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype="lab_meeting")
        content = (project_root / "CLAUDE.md").read_text(encoding="utf-8")
        assert "{project_name}" not in content


# ---------------------------------------------------------------------------
# BC-3.3 — archetype passed to new() skips interactive prompt
# ---------------------------------------------------------------------------


class TestNewWithArchetypeSkipsPrompt:
    """Tests that passing archetype= skips interactive selection."""

    def test_new_with_archetype_does_not_read_stdin(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        # Set stdin to empty; if select_archetype were called it would fail
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        # Should complete without reading stdin
        new(project_root, archetype="conference_talk")
        state = json.loads(
            (project_root / "deck_state.json").read_text(encoding="utf-8")
        )
        assert state["archetype"] == "conference_talk"


# ---------------------------------------------------------------------------
# BC-3.8 — preflight calls verify_vendor_hashes
# ---------------------------------------------------------------------------


class TestPreflightCallsVerifyVendorHashes:
    """Tests that preflight() calls verify_vendor_hashes (BC-3.8)."""

    def test_preflight_passes_when_hashes_are_valid(self, tmp_path: Path) -> None:
        plugin_root = _make_plugin_root(tmp_path)
        # Should not raise or exit
        preflight(plugin_root)

    def test_preflight_exits_1_when_vendor_hash_mismatches(
        self, tmp_path: Path
    ) -> None:
        plugin_root = tmp_path / "pr"
        vendor_dir = plugin_root / "assets" / "vendor"
        vendor_dir.mkdir(parents=True)
        _make_vendor_file(vendor_dir, "mermaid.min.js")
        _make_versions_md(vendor_dir, [("mermaid.min.js", "f" * 64)])
        with pytest.raises(SystemExit) as exc_info:
            preflight(plugin_root)
        assert exc_info.value.code == 1

    def test_preflight_does_not_check_package_install_markers(
        self, tmp_path: Path
    ) -> None:
        """preflight() Python half only calls verify_vendor_hashes."""
        plugin_root = _make_plugin_root(tmp_path)
        # Absence of package/chromium markers must not cause preflight to fail
        preflight(plugin_root)


# ---------------------------------------------------------------------------
# BC-3.5 (gaps) — initial debrief_state: archetype and session_started_at
# ---------------------------------------------------------------------------


class TestNewInitialDebriefStateGaps:
    """Additional BC-3.5 coverage for fields not exercised elsewhere."""

    def _run_new(
        self,
        tmp_path: Path,
        monkeypatch,
        archetype: str = "lab_meeting",
    ) -> dict:
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))
        new(project_root, archetype=archetype)
        return json.loads(
            (project_root / "debrief_state.json").read_text(encoding="utf-8")
        )

    def test_debrief_state_archetype_matches_selected_value(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """BC-3.5: debrief_state.archetype must match the selected archetype."""
        state = self._run_new(tmp_path, monkeypatch, archetype="seminar")
        assert state["archetype"] == "seminar"

    def test_debrief_state_archetype_lab_meeting(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """BC-3.5: debrief_state.archetype field persists for lab_meeting."""
        state = self._run_new(tmp_path, monkeypatch, archetype="lab_meeting")
        assert state["archetype"] == "lab_meeting"

    def test_session_started_at_is_iso8601_string(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """BC-3.5: session_started_at must be an ISO 8601 timestamp."""
        state = self._run_new(tmp_path, monkeypatch)
        val = state.get("session_started_at")
        assert isinstance(val, str) and len(val) > 0, (
            "session_started_at must be a non-empty string"
        )
        assert "T" in val, (
            f"session_started_at {val!r} is not ISO 8601 (missing 'T')"
        )


# ---------------------------------------------------------------------------
# BC-3.2 (gap) — archetype prompt order: 1=lab_meeting … 8=custom
# ---------------------------------------------------------------------------


class TestSelectArchetypePromptOrder:
    """BC-3.2: the numbered list must follow the canonical archetype order."""

    def _write_archetypes(self, tmp_path: Path) -> Path:
        p = tmp_path / "archetypes.json"
        _make_archetypes_json(p)
        return p

    def test_option_1_maps_to_lab_meeting(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Selecting '1' must return 'lab_meeting' (first in canonical order)."""
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
        assert select_archetype(archetypes_path) == "lab_meeting"

    def test_option_2_maps_to_conference_talk(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("2\n"))
        assert select_archetype(archetypes_path) == "conference_talk"

    def test_option_5_maps_to_journal_club(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("5\n"))
        assert select_archetype(archetypes_path) == "journal_club"

    def test_option_7_maps_to_job_talk(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("7\n"))
        assert select_archetype(archetypes_path) == "job_talk"

    def test_option_8_maps_to_custom(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Selecting '8' must return 'custom' (last in canonical order)."""
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("8\n"))
        assert select_archetype(archetypes_path) == "custom"

    def test_prompt_output_lists_archetypes_in_canonical_order(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """BC-3.2: archetypes appear in the prompt in canonical 1-8 order."""
        archetypes_path = self._write_archetypes(tmp_path)
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
        select_archetype(archetypes_path)
        prompt = capsys.readouterr().out
        # Verify that each archetype appears after the previous one in the
        # prompt text — confirming the canonical ordering is preserved.
        positions = [prompt.lower().index(k) for k in _ARCHETYPES]
        assert positions == sorted(positions), (
            "Archetypes are not listed in canonical order in the prompt"
        )


# ---------------------------------------------------------------------------
# BC-3.11 (gap) — new() exit-2 message contains env-corruption content
# ---------------------------------------------------------------------------


class TestNewJsonRepairMessageContent:
    """BC-3.11: new() exit-2 message must contain the env-corruption text."""

    def test_new_exit_2_message_contains_env_corruption_keywords(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """The stderr message must reference json_repair or environment/corrupt."""
        project_root = tmp_path / "proj"
        project_root.mkdir()
        plugin_root = _make_plugin_root(tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(plugin_root))

        def fake_find_spec(name: str):
            if name == "json_repair":
                return None
            return importlib.util.find_spec(name)

        with mock.patch("importlib.util.find_spec", side_effect=fake_find_spec):
            with pytest.raises(SystemExit) as exc_info:
                new(project_root, archetype="lab_meeting")
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        combined = (captured.out + captured.err).lower()
        assert "json_repair" in combined or "environment" in combined or (
            "corrupt" in combined
        ), (
            "Expected env-corruption error keywords in new() exit-2 message"
        )
