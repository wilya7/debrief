# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-45: debrief_config.json model + permission settings."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent

for _dir in (
    _PROJECT_ROOT / "src" / ("unit_3" if (_PROJECT_ROOT / "src" / "unit_3").is_dir() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if (_PROJECT_ROOT / "src" / "unit_2").is_dir() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

from launcher import ensure_project_settings  # noqa: E402


def _setup_project(root: Path, config: dict[str, Any]) -> Path:
    """Set up a minimal project with debrief_config.json."""
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / "debrief_config.json").write_text(
        json.dumps(config), encoding="utf-8"
    )
    # Fake plugin root (needed by ensure_project_settings)
    plugin_root = root / "fake_plugin"
    plugin_root.mkdir()
    (plugin_root.parent / ".claude-plugin").mkdir(exist_ok=True)
    (plugin_root.parent / ".claude-plugin" / "marketplace.json").write_text("{}")
    return plugin_root


class TestConfigModelSettings:

    def test_session_model_written_to_settings(self, tmp_path: Path) -> None:
        plugin_root = _setup_project(tmp_path, {
            "models": {"session": "opus", "subagents": "sonnet"},
            "permissions": {"bypass": False},
        })
        ensure_project_settings(tmp_path, plugin_root)

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert settings["model"] == "opus"

    def test_subagent_model_written_to_env(self, tmp_path: Path) -> None:
        plugin_root = _setup_project(tmp_path, {
            "models": {"session": "opus", "subagents": "sonnet"},
            "permissions": {"bypass": False},
        })
        ensure_project_settings(tmp_path, plugin_root)

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert settings["env"]["CLAUDE_CODE_SUBAGENT_MODEL"] == "sonnet"

    def test_same_model_for_all(self, tmp_path: Path) -> None:
        plugin_root = _setup_project(tmp_path, {
            "models": {"session": "sonnet", "subagents": "sonnet"},
            "permissions": {"bypass": False},
        })
        ensure_project_settings(tmp_path, plugin_root)

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert settings["model"] == "sonnet"
        assert settings["env"]["CLAUDE_CODE_SUBAGENT_MODEL"] == "sonnet"


class TestConfigPermissionSettings:

    def test_bypass_true_sets_default_mode(self, tmp_path: Path) -> None:
        plugin_root = _setup_project(tmp_path, {
            "models": {"session": "opus", "subagents": "sonnet"},
            "permissions": {"bypass": True},
        })
        ensure_project_settings(tmp_path, plugin_root)

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert settings["defaultMode"] == "bypassPermissions"

    def test_bypass_false_removes_default_mode(self, tmp_path: Path) -> None:
        plugin_root = _setup_project(tmp_path, {
            "models": {"session": "opus", "subagents": "sonnet"},
            "permissions": {"bypass": False},
        })
        # Pre-set bypassPermissions
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.write_text(json.dumps({"defaultMode": "bypassPermissions"}))

        ensure_project_settings(tmp_path, plugin_root)

        settings = json.loads(settings_path.read_text())
        assert "defaultMode" not in settings


class TestConfigMissingOrCorrupt:

    def test_no_config_file_uses_defaults(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir(parents=True)
        plugin_root = tmp_path / "fake_plugin"
        plugin_root.mkdir()
        (plugin_root.parent / ".claude-plugin").mkdir(exist_ok=True)
        (plugin_root.parent / ".claude-plugin" / "marketplace.json").write_text("{}")

        # No debrief_config.json — should not crash
        ensure_project_settings(tmp_path, plugin_root)

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        # Plugin settings should still be written
        assert settings["enabledPlugins"]["debrief@debrief"] is True
        # No model override if no config
        assert "model" not in settings

    def test_corrupt_config_file_ignored(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir(parents=True)
        (tmp_path / "debrief_config.json").write_text("not json!!!")
        plugin_root = tmp_path / "fake_plugin"
        plugin_root.mkdir()
        (plugin_root.parent / ".claude-plugin").mkdir(exist_ok=True)
        (plugin_root.parent / ".claude-plugin" / "marketplace.json").write_text("{}")

        # Should not crash on corrupt config
        ensure_project_settings(tmp_path, plugin_root)

        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert settings["enabledPlugins"]["debrief@debrief"] is True


class TestConfigTemplateCreation:

    def test_template_exists_in_plugin(self) -> None:
        tmpl = _PROJECT_ROOT / "src"
        if (_PROJECT_ROOT / "src" / "unit_1").is_dir():
            tmpl = _PROJECT_ROOT / "src" / "unit_1" / "templates" / "debrief_config.json"
        else:
            tmpl = _PROJECT_ROOT / "templates" / "debrief_config.json"
        assert tmpl.is_file(), f"debrief_config.json template not found at {tmpl}"

        config = json.loads(tmpl.read_text())
        assert "models" in config
        assert "session" in config["models"]
        assert "subagents" in config["models"]
        assert "permissions" in config
        assert "bypass" in config["permissions"]
