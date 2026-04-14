# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-13.

Bug: the `stylist` agent produced `style_config.json` with an invented
`{palette, typography, geometry, components}` schema that failed
`parse_style_config` at the very first required key (`colors`). Root cause:
`agents/stylist.md` was a 27-line stub with zero schema guidance, an internal
self-contradiction ("Only write to `assets/style.css`" while the frontmatter
description said it produced `style_config.json`), and no canonical template
to anchor against. With no schema, no template, and contradictory
instructions, the LLM reconstructed a plausible-sounding but compiler-
incompatible schema each session. `/debrief:export` then failed at BC-10.1.

Fix: ship a canonical template at `templates/style_config.json` with all
seven required top-level keys and all twenty-six canonical CSS dot-paths,
and rewrite `agents/stylist.md` to (a) enumerate the seven keys, (b) point
to the template as the mandatory starting skeleton, (c) remove the
self-contradiction, and (d) reference the canonical sources.

This file enforces:

- BC-6.11: the template file exists, satisfies `parse_style_config`,
  contains every mapped dot-path from `CSS_PROPERTY_MAP`, has a non-empty
  `constraints.permitted_diagram_types`, has a `provenance` dict, and
  compiles cleanly to a `:root` block.
- BC-1.3c: `agents/stylist.md` enumerates all seven `_REQUIRED_KEYS` names,
  references the template, contains no "Only write to `assets/style.css`"
  legacy contradiction, and anchors to REQ-STYLE-4 or BC-6.8 or
  `_REQUIRED_KEYS`.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-13.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers — dual workspace/delivered layout, matching BUG-AUDIT-12.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _style_engine_module_dir() -> Path:
    """Locate the directory containing ``style_engine.py`` for both layouts.

    Workspace: ``src/unit_6/style_engine.py``.
    Delivered: ``src/debrief/style_engine.py``.
    """
    workspace = _PROJECT_ROOT / "src" / "unit_6"
    delivered = _PROJECT_ROOT / "src" / "debrief"
    for candidate in (workspace, delivered):
        if (candidate / "style_engine.py").exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find style_engine.py under {workspace} or {delivered}"
    )


# Ensure ``style_engine`` is importable before any test runs. This file lives
# in ``tests/regressions/`` and has no unit-local conftest, so we prep sys.path
# ourselves — matching the pattern used by ``tests/unit_6/conftest.py``.
_engine_dir = _style_engine_module_dir()
if str(_engine_dir) not in sys.path:
    sys.path.insert(0, str(_engine_dir))

import style_engine  # noqa: E402  — intentional after sys.path manipulation


def _template_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "templates" / "style_config.json"
    delivered = _PROJECT_ROOT / "templates" / "style_config.json"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find templates/style_config.json at {workspace} or {delivered}"
    )


def _stylist_md_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "agents" / "stylist.md"
    delivered = _PROJECT_ROOT / "agents" / "stylist.md"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find agents/stylist.md at {workspace} or {delivered}"
    )


@pytest.fixture(scope="module")
def template_data() -> dict:
    return json.loads(_template_path().read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def stylist_md_text() -> str:
    return _stylist_md_path().read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# BC-6.11 — canonical template validity.
# ---------------------------------------------------------------------------


class TestBugAudit13TemplateValid:
    """BC-6.11 / BUG-AUDIT-13 — the bundled ``templates/style_config.json``
    MUST exist and be a compiler-valid starting skeleton.
    """

    def test_template_file_exists(self) -> None:
        path = _template_path()
        assert path.is_file(), (
            f"BC-6.11 / BUG-AUDIT-13: templates/style_config.json must exist "
            f"at {path}. The Stylist loads this file as the mandatory "
            f"starting skeleton per REQ-STYLE-4."
        )

    def test_template_satisfies_parse_style_config(self) -> None:
        # If parse_style_config raises, the test fails with the exact
        # ``Missing required key: <name>`` message — the same error the
        # user saw during BUG-AUDIT-13.
        style_engine.parse_style_config(_template_path())

    def test_template_contains_all_seven_required_keys(
        self, template_data: dict
    ) -> None:
        for key in style_engine._REQUIRED_KEYS:
            assert key in template_data, (
                f"BC-6.11: templates/style_config.json must contain top-level "
                f"key {key!r} per _REQUIRED_KEYS in style_engine. Missing keys "
                f"cause parse_style_config to raise and BC-10.1's style "
                f"compiler subprocess to exit code 1 — the exact failure "
                f"mode of BUG-AUDIT-13."
            )

    def test_template_contains_all_mapped_dot_paths(
        self, template_data: dict
    ) -> None:
        flat = style_engine.flatten_config(template_data)
        missing = [
            dot_path
            for dot_path in style_engine.CSS_PROPERTY_MAP
            if dot_path not in flat
        ]
        assert not missing, (
            f"BC-6.11: templates/style_config.json must contain a value for "
            f"every dot-path in CSS_PROPERTY_MAP so the Stylist has a "
            f"complete starting skeleton to fill in. Missing: {missing!r}. "
            f"BUG-AUDIT-13 incident: a Stylist with no template invented the "
            f"wrong schema and broke /debrief:export."
        )

    def test_template_permitted_diagram_types_non_empty(
        self, template_data: dict
    ) -> None:
        # Spec section 24.16 requires constraints.permitted_diagram_types
        # to be a non-empty list of permitted libraries.
        constraints = template_data.get("constraints", {})
        diagram_types = constraints.get("permitted_diagram_types")
        assert isinstance(diagram_types, list) and len(diagram_types) > 0, (
            f"BC-6.11 / spec section 24.16: "
            f"templates/style_config.json must contain "
            f"constraints.permitted_diagram_types as a non-empty list. "
            f"Got: {diagram_types!r}"
        )

    def test_template_provenance_is_object(self, template_data: dict) -> None:
        # REQ-STYLE-7 / spec section 24.16 require provenance to be a dict.
        # May be empty, but must exist and be the right type.
        provenance = template_data.get("provenance")
        assert isinstance(provenance, dict), (
            f"BC-6.11 / REQ-STYLE-7: templates/style_config.json must "
            f"contain a `provenance` object (dict). Got: "
            f"{type(provenance).__name__}"
        )

    def test_template_compiles_to_root_block(self, tmp_path: Path) -> None:
        # End-to-end contract: compile_style(template) must succeed and
        # produce a non-empty `:root` block. This is the exact code path
        # that BC-10.1's subprocess invokes during /debrief:export.
        out = tmp_path / "style.css"
        style_engine.compile_style(_template_path(), out)
        assert out.exists(), (
            f"BC-6.11: compile_style must write output to {out}"
        )
        content = out.read_text(encoding="utf-8")
        assert content.strip(), (
            "BC-6.11: compile_style output must be non-empty."
        )
        assert ":root {" in content, (
            f"BC-6.11 / BC-6.5: compile_style output must contain a "
            f":root {{ ... }} block. Got:\n{content[:200]}"
        )

    def test_template_emits_all_twenty_six_mapped_css_vars(
        self, tmp_path: Path
    ) -> None:
        # BC-6.2: all twenty-six mapped vars must appear in the CSS output
        # when the template supplies every mapped dot-path. This is the
        # positive complement to test_template_contains_all_mapped_dot_paths.
        out = tmp_path / "style.css"
        style_engine.compile_style(_template_path(), out)
        content = out.read_text(encoding="utf-8")
        missing_vars = [
            var for var in style_engine.CSS_PROPERTY_MAP.values()
            if var not in content
        ]
        assert not missing_vars, (
            f"BC-6.2 / BC-6.11: every mapped CSS variable from "
            f"CSS_PROPERTY_MAP must appear in the compiled output when the "
            f"template populates every mapped dot-path. Missing: "
            f"{missing_vars!r}"
        )


# ---------------------------------------------------------------------------
# BC-1.3c — stylist.md schema anchoring.
# ---------------------------------------------------------------------------


class TestBugAudit13StylistAgentPrompt:
    """BC-1.3c / BUG-AUDIT-13 — ``agents/stylist.md`` MUST enumerate the
    canonical schema, reference the template, and contain no legacy
    contradictions.
    """

    def test_stylist_enumerates_seven_required_keys(
        self, stylist_md_text: str
    ) -> None:
        # Iterate over the authoritative list imported from style_engine so
        # this test tracks drift automatically if _REQUIRED_KEYS ever changes.
        for key in style_engine._REQUIRED_KEYS:
            assert key in stylist_md_text, (
                f"BC-1.3c / BUG-AUDIT-13: agents/stylist.md must enumerate "
                f"the required top-level key {key!r} so the Stylist LLM has "
                f"an explicit schema to anchor against. Without this, the "
                f"agent reconstructs the schema from memory and drifts "
                f"(BUG-AUDIT-13 incident)."
            )

    def test_stylist_references_template(self, stylist_md_text: str) -> None:
        assert "templates/style_config.json" in stylist_md_text, (
            "BC-1.3c: agents/stylist.md must reference the canonical "
            "starting template at templates/style_config.json so the Stylist "
            "loads a compiler-valid skeleton rather than inventing one."
        )

    def test_stylist_no_longer_claims_only_style_css(
        self, stylist_md_text: str
    ) -> None:
        # BUG-AUDIT-13 negative sentinel. The 27-line stub said
        # "Only write to `assets/style.css`" which contradicted its own
        # frontmatter description ("produces style_config.json and
        # style_guide.md"). The style compiler produces assets/style.css;
        # the Stylist must not.
        legacy_contradiction = "Only write to `assets/style.css`"
        assert legacy_contradiction not in stylist_md_text, (
            f"BC-1.3c / BUG-AUDIT-13 regression: agents/stylist.md must not "
            f"contain the legacy phrase {legacy_contradiction!r}. The style "
            f"compiler produces assets/style.css at style-lock time per "
            f"REQ-STYLE-5 and BC-10.1; the Stylist writes "
            f".debrief/draft/style_config.json and "
            f".debrief/draft/style_guide.md."
        )

    def test_stylist_anchors_to_canonical_sources(
        self, stylist_md_text: str
    ) -> None:
        # The agent prompt must reference at least one of the canonical
        # sources so future maintainers can find the source of truth.
        anchors = ("REQ-STYLE-4", "BC-6.8", "_REQUIRED_KEYS")
        found = [anchor for anchor in anchors if anchor in stylist_md_text]
        assert found, (
            f"BC-1.3c: agents/stylist.md must reference at least one of the "
            f"canonical schema sources {anchors!r} so future maintainers can "
            f"trace the schema back to style_engine.py and the spec."
        )

    def test_stylist_mentions_bug_audit_13_reference(
        self, stylist_md_text: str
    ) -> None:
        # A single BUG-AUDIT-13 reference anchors the "don't re-invent the
        # schema" warning to the historical incident — so a future maintainer
        # reading only the agent file can find the full bug write-up in the
        # spec Bug Catalog. This is a load-bearing breadcrumb, not cosmetic.
        assert "BUG-AUDIT-13" in stylist_md_text, (
            "BC-1.3c: agents/stylist.md must mention BUG-AUDIT-13 so future "
            "maintainers can find the historical incident in the spec Bug "
            "Catalog when they see the 'do not invent the schema' instruction."
        )
