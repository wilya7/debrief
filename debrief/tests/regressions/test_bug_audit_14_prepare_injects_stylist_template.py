# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-14.

BUG-AUDIT-13 fixed the Stylist's system prompt (``agents/stylist.md``) to
instruct the agent to ``Read()`` the canonical ``templates/style_config.json``
template before beginning the style dialog. That fix relies on the agent
**choosing** to follow the instruction. A forgetful or imprecise LLM session
could skip the Read step and reconstruct a compiler-incompatible schema from
memory — the exact failure mode of BUG-AUDIT-13.

BUG-AUDIT-14 closes the hole by having ``main_prepare`` inject the template
contents **directly into the task prompt** as a ``## Schema Starting Point``
JSON fenced code block for any stylist-bound action
(``style/style_dialog`` or ``style/style_lock``). The section is prepended
so the schema is the first thing the stylist's first user-message turn sees.
No Read tool call required; no instruction to follow.

This file enforces BC-4.7b:

- ``main_prepare`` injects the section for stylist actions.
- Non-stylist actions get NO injection (negative sentinel).
- The section is at the top of the task prompt (prepended, not appended).
- The JSON block is parseable and contains all seven ``_REQUIRED_KEYS``.
- The JSON block passes ``style_engine.parse_style_config`` end-to-end.
- Plugin root resolution tries ``CLAUDE_PLUGIN_ROOT`` first and falls
  back to a ``__file__``-relative path for test/offline contexts.
- A missing template is a hard error (``SystemExit(1)``).
- The explanatory paragraph cites §24.16.1 and BC-6.11.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Dual-layout sys.path setup — matches test_bug_audit_13.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _routing_module_dir() -> Path:
    """Locate the directory containing ``routing.py`` for both layouts."""
    workspace = _PROJECT_ROOT / "src" / "unit_4"
    delivered = _PROJECT_ROOT / "src" / "debrief"
    for candidate in (workspace, delivered):
        if (candidate / "routing.py").exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find routing.py under {workspace} or {delivered}"
    )


def _style_engine_module_dir() -> Path:
    """Locate the directory containing ``style_engine.py`` for both layouts."""
    workspace = _PROJECT_ROOT / "src" / "unit_6"
    delivered = _PROJECT_ROOT / "src" / "debrief"
    for candidate in (workspace, delivered):
        if (candidate / "style_engine.py").exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find style_engine.py under {workspace} or {delivered}"
    )


def _real_template_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "templates" / "style_config.json"
    delivered = _PROJECT_ROOT / "templates" / "style_config.json"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find templates/style_config.json at {workspace} or {delivered}"
    )


# Ensure both modules are importable before any test runs.
_routing_dir = _routing_module_dir()
if str(_routing_dir) not in sys.path:
    sys.path.insert(0, str(_routing_dir))

_engine_dir = _style_engine_module_dir()
if str(_engine_dir) not in sys.path:
    sys.path.insert(0, str(_engine_dir))

import routing  # noqa: E402
import style_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


_FENCED_JSON_RE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def _call_main_prepare(
    action: str,
    project_root: Path,
) -> str:
    """Invoke ``routing.main_prepare`` and return the task-prompt contents."""
    (project_root / ".debrief").mkdir(parents=True, exist_ok=True)
    routing.main_prepare(action, project_root)
    prompt_path = project_root / ".debrief" / "task_prompt.md"
    return prompt_path.read_text(encoding="utf-8")


def _extract_fenced_json(text: str) -> str:
    match = _FENCED_JSON_RE.search(text)
    assert match, (
        "BC-4.7b: task prompt must contain a ```json fenced block "
        "(BUG-AUDIT-14 / § Stylist schema injection)."
    )
    return match.group(1)


# ---------------------------------------------------------------------------
# BC-4.7b / BUG-AUDIT-14 — stylist schema injection.
# ---------------------------------------------------------------------------


class TestBugAudit14PrepareInjectsStylistTemplate:
    """BC-4.7b / BUG-AUDIT-14: ``main_prepare`` injects the canonical
    ``templates/style_config.json`` as a ``## Schema Starting Point``
    section for stylist-bound actions.
    """

    def test_main_prepare_injects_schema_section_for_style_dialog(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Let the resolver use the __file__-relative fallback by unsetting
        # the env var — we're exercising the test/offline code path.
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

        content = _call_main_prepare("style/style_dialog", tmp_path)

        assert "## Schema Starting Point" in content, (
            "BC-4.7b: stylist task prompt must contain the Schema "
            "Starting Point section header."
        )
        assert "```json" in content, (
            "BC-4.7b: section must contain a ```json fenced block."
        )

    def test_main_prepare_injects_schema_section_for_style_lock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

        content = _call_main_prepare("style/style_lock", tmp_path)

        assert "## Schema Starting Point" in content, (
            "BC-4.7b: style/style_lock must also trigger injection per "
            "the stylist-bound action set."
        )

    def test_injected_json_block_parses_as_dict_with_seven_required_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

        content = _call_main_prepare("style/style_dialog", tmp_path)
        raw = _extract_fenced_json(content)
        data = json.loads(raw)

        assert isinstance(data, dict), (
            "BC-4.7b: injected JSON block must parse to a dict."
        )
        for key in style_engine._REQUIRED_KEYS:
            assert key in data, (
                f"BC-4.7b / BC-6.11: injected template must contain "
                f"required top-level key {key!r}."
            )

    def test_injected_json_passes_parse_style_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # End-to-end contract: what prepare injects MUST itself satisfy
        # parse_style_config. A regression that breaks the template file
        # would be caught here as well as in BUG-AUDIT-13's tests.
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

        content = _call_main_prepare("style/style_dialog", tmp_path)
        raw = _extract_fenced_json(content)

        extracted = tmp_path / "extracted_style_config.json"
        extracted.write_text(raw, encoding="utf-8")

        # If this raises, the fix has drifted from BUG-AUDIT-13's canonical
        # schema — either the template or the injection is broken.
        style_engine.parse_style_config(extracted)

    def test_main_prepare_no_injection_for_non_stylist_action(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Negative sentinel: production/red_green is not stylist-bound.
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

        content = _call_main_prepare("production/red_green", tmp_path)

        assert "## Schema Starting Point" not in content, (
            "BC-4.7b: the Schema Starting Point section must only be "
            "injected for stylist-bound actions. A non-stylist action "
            "must NOT contain the section — otherwise the injection is "
            "triggering too broadly and polluting other agents' prompts."
        )

    def test_schema_section_is_prepended_not_appended(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

        content = _call_main_prepare("style/style_dialog", tmp_path)

        # The section header MUST be the very first non-empty line of the
        # task prompt. Prepending guarantees the agent sees the schema
        # before any other context section.
        first_line = content.lstrip().splitlines()[0]
        assert first_line == "## Schema Starting Point", (
            f"BC-4.7b: the Schema Starting Point section must be prepended "
            f"to the task prompt, not appended. The stylist's first "
            f"user-message turn must begin with the schema. Got first "
            f"non-empty line: {first_line!r}"
        )

    def test_plugin_root_resolution_uses_env_var_when_set(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Copy the real template into a synthetic plugin root, point
        # CLAUDE_PLUGIN_ROOT at it, and verify the resolver picks that
        # path (not the __file__-relative fallback). We prove this by
        # modifying the synthetic template's contents so we can tell
        # which copy was injected.
        fake_plugin_root = tmp_path / "fake_plugin_root"
        (fake_plugin_root / "templates").mkdir(parents=True)
        sentinel_value = "__bug_audit_14_sentinel_primary__"
        with _real_template_path().open(encoding="utf-8") as f:
            real_template = json.load(f)
        real_template["colors"]["primary"] = sentinel_value
        (fake_plugin_root / "templates" / "style_config.json").write_text(
            json.dumps(real_template, indent=2), encoding="utf-8"
        )
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(fake_plugin_root))

        project_root = tmp_path / "project"
        content = _call_main_prepare("style/style_dialog", project_root)

        assert sentinel_value in content, (
            "BC-4.7b: when CLAUDE_PLUGIN_ROOT is set, _resolve_template_path "
            "must prefer the env-var path over the __file__-relative "
            "fallback. The sentinel value from the synthetic template "
            "should appear in the injected section."
        )

    def test_plugin_root_resolution_falls_back_to_source_relative(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When CLAUDE_PLUGIN_ROOT is unset, resolution must find the real
        # template via the __file__-relative fallback, which is how every
        # other test in this file already exercises the code path. This
        # test exists as an explicit contract anchor for BC-4.7b's
        # fallback requirement.
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

        # Non-existent project root — plugin_root will default to
        # str(project_root) per main_prepare's env lookup, so the first
        # resolver candidate (plugin_root/templates/...) will miss and
        # the fallback must engage.
        project_root = tmp_path / "empty_project"
        content = _call_main_prepare("style/style_dialog", project_root)

        # The real template's baseline primary color is "#1a2b3c".
        assert '"primary"' in content and "1a2b3c" in content, (
            "BC-4.7b: the __file__-relative fallback must locate the "
            "real templates/style_config.json when CLAUDE_PLUGIN_ROOT "
            "is unset. Expected the baseline primary colour from the "
            "real template to appear in the injected section."
        )

    def test_missing_template_causes_hard_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Point the resolver at a plugin root with no templates dir AND
        # shadow the __file__-relative fallback so no candidate exists.
        empty_plugin_root = tmp_path / "empty_plugin_root"
        empty_plugin_root.mkdir()
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(empty_plugin_root))

        def _broken_resolver(plugin_root: Path) -> Path:
            return empty_plugin_root / "templates" / "style_config.json"

        monkeypatch.setattr(routing, "_resolve_template_path", _broken_resolver)

        project_root = tmp_path / "proj"
        (project_root / ".debrief").mkdir(parents=True)

        with pytest.raises(SystemExit) as exc_info:
            routing.main_prepare("style/style_dialog", project_root)
        assert exc_info.value.code == 1, (
            "BC-4.7b / BUG-AUDIT-14: a missing template must cause "
            "main_prepare to exit with code 1, not silently omit the "
            "Schema Starting Point section."
        )

    def test_injected_section_cites_spec_anchors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The explanatory paragraph must cite the canonical sources so
        # future maintainers can trace the schema back. This is a
        # load-bearing breadcrumb, not cosmetic.
        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)

        content = _call_main_prepare("style/style_dialog", tmp_path)

        assert "24.16.1" in content, (
            "BC-4.7b: explainer paragraph must cite spec §24.16.1 "
            "(canonical schema enumeration)."
        )
        assert "BC-6.11" in content, (
            "BC-4.7b: explainer paragraph must cite BC-6.11 "
            "(template-validity contract)."
        )
        assert "BUG-AUDIT-13" in content, (
            "BC-4.7b: explainer paragraph must reference BUG-AUDIT-13 "
            "so maintainers can find the historical failure mode."
        )
