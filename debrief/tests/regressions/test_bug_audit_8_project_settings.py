# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-8.

Bug: under the BUG-AUDIT-1..7 architecture, `bin/debrief` launched
Claude Code via `claude --plugin-dir <plugin_root>`. That load path
skipped marketplace registration, so plugin skills registered with
bare names (`/export`, `/save`, `/quit`, etc.), colliding with Claude
Code built-ins. The user could not unambiguously invoke debrief skills.

The fix retires `--plugin-dir` and switches to the project-scoped
`.claude/settings.json` mechanism documented at
code.claude.com/docs/en/settings.md. `bin/debrief` now `exec claude`s
with no flags; Claude Code auto-discovers the project's settings file
(written by `ensure_project_settings`) and loads debrief via the
marketplace, namespacing skills as `/debrief:*`.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-8,
blueprint contracts BC-1.16 (amended) and BC-3.13 (new), and
BC-3.12 (extended with the `ensure_settings` dispatch arm).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _bin_debrief_path() -> Path:
    workspace_candidate = _PROJECT_ROOT / "src" / "unit_1" / "bin" / "debrief"
    delivered_candidate = _PROJECT_ROOT / "bin" / "debrief"
    for candidate in (workspace_candidate, delivered_candidate):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find bin/debrief at {workspace_candidate} or {delivered_candidate}"
    )


def _launcher_path() -> Path:
    workspace_candidate = _PROJECT_ROOT / "src" / "unit_3" / "launcher.py"
    delivered_candidate = _PROJECT_ROOT / "src" / "debrief" / "launcher.py"
    for candidate in (workspace_candidate, delivered_candidate):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find launcher.py at {workspace_candidate} or {delivered_candidate}"
    )


def _import_launcher_module():
    """Import the `launcher` module from whichever repo layout we are in.

    Workspace layout: `src/unit_3/launcher.py` — add `src/unit_3/` to
    sys.path then `import launcher`.
    Delivered layout: `src/debrief/launcher.py` (the installed `debrief`
    Python package) — add `src/debrief/` to sys.path then `import launcher`
    (this matches what `tests/unit_3/conftest.py` does in the delivered
    repo, since regression tests don't share that conftest).
    """
    # Try every candidate path; the first one whose parent contains a
    # `launcher.py` wins. Order: workspace, delivered.
    candidates = [
        _PROJECT_ROOT / "src" / "unit_3",
        _PROJECT_ROOT / "src" / "debrief",
    ]
    for candidate in candidates:
        if (candidate / "launcher.py").exists():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            try:
                import launcher  # type: ignore[import-not-found]
                return launcher
            except ImportError:
                continue
    pytest.skip(
        "Could not import launcher module — neither "
        "src/unit_3/launcher.py nor src/debrief/launcher.py exists "
        "relative to _PROJECT_ROOT."
    )


@pytest.fixture(scope="module")
def bin_debrief_text() -> str:
    return _bin_debrief_path().read_text()


@pytest.fixture(scope="module")
def launcher_text() -> str:
    return _launcher_path().read_text()


@pytest.fixture(scope="module")
def launcher_module():
    return _import_launcher_module()


# ---------------------------------------------------------------------------
# BUG-AUDIT-8 regression tests.
# ---------------------------------------------------------------------------


class TestBugAudit8ProjectSettings:
    """BC-1.16 (amended) + BC-3.13 (new) — project-scoped plugin enablement."""

    # --- bin/debrief launch shape ------------------------------------------

    def test_bin_debrief_launches_claude_with_no_flags(
        self, bin_debrief_text: str
    ) -> None:
        # BC-1.16 step 10 / BUG-AUDIT-8: the launch is plain `exec claude`,
        # no flags. Match the form on its own line so we don't false-match
        # a comment or substring.
        matches = re.findall(r"^\s*exec claude\s*$", bin_debrief_text, re.MULTILINE)
        assert len(matches) >= 1, (
            "BC-1.16 step 10 / BUG-AUDIT-8: bin/debrief must `exec claude` "
            "with no flags. Found no matches."
        )

    def test_bin_debrief_does_not_pass_plugin_dir(
        self, bin_debrief_text: str
    ) -> None:
        # BUG-AUDIT-8 negative sentinel: the retired `--plugin-dir` flag
        # must not appear anywhere in bin/debrief.
        assert "--plugin-dir" not in bin_debrief_text, (
            "BUG-AUDIT-8 regression: bin/debrief uses `--plugin-dir`. That "
            "flag was retired in BUG-AUDIT-8 because it skips marketplace "
            "registration and produces bare-named skills."
        )

    def test_bin_debrief_calls_ensure_settings_in_bare_arm(
        self, bin_debrief_text: str
    ) -> None:
        # BC-1.16 step 9 (bare arm) / BC-3.13: the bare `""` arm of the
        # subcommand dispatch must call `python -m debrief.launcher
        # ensure_settings` to self-heal `.claude/settings.json` for
        # existing projects (BUG-AUDIT-1..7 era projects don't have it).
        assert "python -m debrief.launcher ensure_settings" in bin_debrief_text, (
            "BC-3.13 / BUG-AUDIT-8: bin/debrief's bare-invocation arm must "
            "call `python -m debrief.launcher ensure_settings \"$(pwd)\"` "
            "before exec'ing claude, so existing projects self-heal their "
            "`.claude/settings.json`."
        )

    # --- ensure_project_settings: existence and signature -----------------

    def test_ensure_project_settings_function_exists(self, launcher_module) -> None:
        assert hasattr(launcher_module, "ensure_project_settings"), (
            "BC-3.13: `debrief.launcher` must define `ensure_project_settings`."
        )
        assert callable(launcher_module.ensure_project_settings), (
            "BC-3.13: `ensure_project_settings` must be callable."
        )

    # --- ensure_project_settings: functional behavior ---------------------

    def _make_fake_layout(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create a tmp project_root and a tmp plugin_root whose parent is the
        marketplace root. Returns (project_root, plugin_root).
        """
        marketplace = tmp_path / "fake_marketplace"
        marketplace.mkdir()
        (marketplace / ".claude-plugin").mkdir()
        plugin = marketplace / "debrief"
        plugin.mkdir()
        (plugin / ".claude-plugin").mkdir()
        project = tmp_path / "fake_project"
        project.mkdir()
        return project, plugin

    def test_ensure_project_settings_creates_dot_claude_dir_and_settings_json(
        self, launcher_module, tmp_path: Path
    ) -> None:
        project, plugin = self._make_fake_layout(tmp_path)
        launcher_module.ensure_project_settings(project, plugin)
        settings_path = project / ".claude" / "settings.json"
        assert settings_path.exists(), (
            "BC-3.13: ensure_project_settings must create "
            "`<project>/.claude/settings.json`."
        )

    def test_ensure_project_settings_writes_extra_known_marketplaces(
        self, launcher_module, tmp_path: Path
    ) -> None:
        project, plugin = self._make_fake_layout(tmp_path)
        launcher_module.ensure_project_settings(project, plugin)
        data = json.loads((project / ".claude" / "settings.json").read_text())
        assert "extraKnownMarketplaces" in data
        assert "debrief" in data["extraKnownMarketplaces"]
        entry = data["extraKnownMarketplaces"]["debrief"]
        assert entry["source"]["source"] == "directory", (
            "BC-3.13: marketplace source.source must be 'directory'."
        )
        # The path field MUST be the absolute resolved path of plugin.parent.
        expected_path = str(plugin.parent.resolve())
        assert entry["source"]["path"] == expected_path, (
            f"BC-3.13: marketplace path must be {expected_path!r}, "
            f"got {entry['source']['path']!r}."
        )

    def test_ensure_project_settings_writes_enabled_plugins(
        self, launcher_module, tmp_path: Path
    ) -> None:
        project, plugin = self._make_fake_layout(tmp_path)
        launcher_module.ensure_project_settings(project, plugin)
        data = json.loads((project / ".claude" / "settings.json").read_text())
        assert data.get("enabledPlugins", {}).get("debrief@debrief") is True, (
            "BC-3.13: enabledPlugins['debrief@debrief'] must be True."
        )

    def test_ensure_project_settings_is_idempotent(
        self, launcher_module, tmp_path: Path
    ) -> None:
        project, plugin = self._make_fake_layout(tmp_path)
        launcher_module.ensure_project_settings(project, plugin)
        first = (project / ".claude" / "settings.json").read_bytes()
        launcher_module.ensure_project_settings(project, plugin)
        second = (project / ".claude" / "settings.json").read_bytes()
        assert first == second, (
            "BC-3.13: ensure_project_settings must be idempotent (byte-equal "
            "output on repeated calls with the same inputs)."
        )

    def test_ensure_project_settings_preserves_unrelated_keys(
        self, launcher_module, tmp_path: Path
    ) -> None:
        project, plugin = self._make_fake_layout(tmp_path)
        settings_dir = project / ".claude"
        settings_dir.mkdir()
        settings_path = settings_dir / "settings.json"
        # Pre-populate with unrelated keys.
        original = {
            "someUnrelatedKey": "value",
            "agent": "consultant",
            "myCustomList": [1, 2, 3],
        }
        settings_path.write_text(json.dumps(original))

        launcher_module.ensure_project_settings(project, plugin)
        data = json.loads(settings_path.read_text())

        assert data.get("someUnrelatedKey") == "value", (
            "BC-3.13: ensure_project_settings must preserve unrelated keys "
            "(`someUnrelatedKey` was lost)."
        )
        assert data.get("agent") == "consultant", (
            "BC-3.13: ensure_project_settings must preserve unrelated keys "
            "(`agent` was lost)."
        )
        assert data.get("myCustomList") == [1, 2, 3], (
            "BC-3.13: ensure_project_settings must preserve unrelated keys "
            "(`myCustomList` was lost)."
        )
        assert "extraKnownMarketplaces" in data
        assert data["enabledPlugins"]["debrief@debrief"] is True

    def test_ensure_project_settings_updates_stale_marketplace_path(
        self, launcher_module, tmp_path: Path
    ) -> None:
        project, plugin = self._make_fake_layout(tmp_path)
        # First call with the original plugin_root.
        launcher_module.ensure_project_settings(project, plugin)
        # Now create a different plugin_root and re-run.
        new_marketplace = tmp_path / "moved_marketplace"
        new_marketplace.mkdir()
        new_plugin = new_marketplace / "debrief"
        new_plugin.mkdir()
        launcher_module.ensure_project_settings(project, new_plugin)
        data = json.loads((project / ".claude" / "settings.json").read_text())
        actual_path = data["extraKnownMarketplaces"]["debrief"]["source"]["path"]
        expected_path = str(new_plugin.parent.resolve())
        assert actual_path == expected_path, (
            f"BC-3.13: ensure_project_settings must self-heal stale "
            f"marketplace paths. Expected {expected_path!r}, got {actual_path!r}."
        )

    def test_ensure_project_settings_recovers_from_corrupt_json(
        self, launcher_module, tmp_path: Path
    ) -> None:
        project, plugin = self._make_fake_layout(tmp_path)
        settings_dir = project / ".claude"
        settings_dir.mkdir()
        settings_path = settings_dir / "settings.json"
        settings_path.write_text("not valid json {{{ ][")
        # Should not raise.
        launcher_module.ensure_project_settings(project, plugin)
        # The corrupt file is now overwritten with valid JSON containing
        # the debrief keys.
        data = json.loads(settings_path.read_text())
        assert data["enabledPlugins"]["debrief@debrief"] is True
        assert "debrief" in data["extraKnownMarketplaces"]

    # --- AST checks: main_new and new() integration -----------------------

    def test_main_new_dispatches_ensure_settings_subcommand(
        self, launcher_text: str
    ) -> None:
        # BC-3.12 (extended) / BC-3.13: main_new() must include an arm
        # comparing subcommand to "ensure_settings". Use AST to scope the
        # check to main_new's body so we don't false-match elsewhere.
        tree = ast.parse(launcher_text)
        main_new = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == "main_new"
            ),
            None,
        )
        assert main_new is not None, "main_new() not found in launcher.py."

        # Walk main_new's body looking for a Compare node like
        # `subcommand == "ensure_settings"`.
        found = False
        for node in ast.walk(main_new):
            if isinstance(node, ast.Compare):
                for comparator in node.comparators:
                    if (
                        isinstance(comparator, ast.Constant)
                        and comparator.value == "ensure_settings"
                    ):
                        found = True
                        break
                if found:
                    break
        assert found, (
            "BC-3.12 / BC-3.13: main_new() must contain a dispatch arm "
            "comparing `subcommand == \"ensure_settings\"`."
        )

    def test_new_calls_ensure_project_settings(self, launcher_text: str) -> None:
        # BC-3.13: new() must call ensure_project_settings as part of its
        # initialization sequence.
        tree = ast.parse(launcher_text)
        new_func = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == "new"
            ),
            None,
        )
        assert new_func is not None, "new() not found in launcher.py."

        found = False
        for node in ast.walk(new_func):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "ensure_project_settings":
                    found = True
                    break
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "ensure_project_settings"
                ):
                    found = True
                    break
        assert found, (
            "BC-3.13: new() must call `ensure_project_settings` as part of "
            "the initialization sequence (so newly created projects ship "
            "with `.claude/settings.json`)."
        )
