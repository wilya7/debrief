# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-71.

BUG-AUDIT-71 closes a silent-substitution defect in `style_engine`:
the compiler named Google Fonts families in its CSS custom properties
but never emitted an @import or @font-face loader, so the browser fell
through to system fonts without warning. The fix adds an allowlist-
driven @import emission pass to `compile_style`.

TEST CLASSES:

1. TestExtractFontFamilies — allowlist filtering, normalization,
   dedup, stable order.
2. TestGenerateFontImportStatement — URL grammar (base, family params,
   display=swap).
3. TestCompileStyleFontLoader — end-to-end via compile_style: @import
   appears before :root, no @import when no allowlisted family.

All tests run unconditionally in both workspace and delivered layouts
via the sibling-discovery path pattern established in
`test_bug_audit_21_handout_robustness.py`; zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-71 and
blueprint contract BC-6.14.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_6").is_dir()


def _style_engine_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_6"
    return _PROJECT_ROOT / "src" / "debrief"


if str(_style_engine_module_dir()) not in sys.path:
    sys.path.insert(0, str(_style_engine_module_dir()))

import style_engine  # noqa: E402
from style_engine import (  # noqa: E402
    compile_style,
    extract_font_families,
    generate_font_import_statement,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config_with_typography(
    heading: str,
    body: str,
    code: str,
) -> dict[str, Any]:
    """Minimal valid style_config with configurable typography fields."""
    return {
        "colors": {"primary": "#000", "background": "#fff"},
        "typography": {
            "heading_font_family": heading,
            "body_font_family": body,
            "code_font_family": code,
        },
        "spacing": {},
        "layout": {"slide_width": "1920px", "slide_height": "1080px"},
        "data_viz": {},
        "constraints": {"permitted_diagram_types": []},
        "provenance": {},
    }


# ---------------------------------------------------------------------------
# Test class 1: extract_font_families
# ---------------------------------------------------------------------------


class TestExtractFontFamilies:
    def test_template_config_detects_inter_and_fira_code(
        self, tmp_path: Path
    ) -> None:
        # The shipped template at src/unit_1/templates/style_config.json
        # references Inter (heading), Georgia (body), Fira Code (code).
        # Only Inter and Fira Code are Google-Fonts allowlisted.
        template_path = _PROJECT_ROOT / "src" / "unit_1" / "templates" / "style_config.json"
        if not template_path.exists():
            # Delivered layout: template lives in debrief/templates/
            template_path = _PROJECT_ROOT / "templates" / "style_config.json"
        cfg = json.loads(template_path.read_text(encoding="utf-8"))
        result = extract_font_families(cfg)
        assert result == ["inter", "fira code"]

    def test_all_system_fonts_yields_empty(self) -> None:
        cfg = _config_with_typography(
            heading="Helvetica, sans-serif",
            body="Georgia, serif",
            code="Menlo, monospace",
        )
        assert extract_font_families(cfg) == []

    def test_single_google_font_detected(self) -> None:
        cfg = _config_with_typography(
            heading="Inter, sans-serif",
            body="Georgia, serif",
            code="Menlo, monospace",
        )
        assert extract_font_families(cfg) == ["inter"]

    def test_mixed_quotes_stripped(self) -> None:
        cfg = _config_with_typography(
            heading="'Inter', sans-serif",
            body='"Open Sans", serif',
            code="Menlo, monospace",
        )
        assert extract_font_families(cfg) == ["inter", "open sans"]

    def test_duplicate_families_deduped(self) -> None:
        # Stylist chose Inter everywhere — should appear once.
        cfg = _config_with_typography(
            heading="Inter, sans-serif",
            body="Inter, sans-serif",
            code="Inter, monospace",
        )
        assert extract_font_families(cfg) == ["inter"]

    def test_stable_order_heading_body_code(self) -> None:
        cfg = _config_with_typography(
            heading="Fira Code, monospace",
            body="Inter, sans-serif",
            code="Open Sans, sans-serif",
        )
        # Order reflects discovery order, not allowlist iteration order.
        assert extract_font_families(cfg) == [
            "fira code",
            "inter",
            "open sans",
        ]

    def test_empty_typography_yields_empty(self) -> None:
        cfg: dict[str, Any] = {
            "colors": {},
            "typography": {},
            "spacing": {},
            "layout": {},
            "data_viz": {},
            "constraints": {},
            "provenance": {},
        }
        assert extract_font_families(cfg) == []

    def test_missing_typography_yields_empty(self) -> None:
        cfg: dict[str, Any] = {
            "colors": {},
            "spacing": {},
            "layout": {},
            "data_viz": {},
            "constraints": {},
            "provenance": {},
        }
        assert extract_font_families(cfg) == []

    def test_non_string_font_value_ignored(self) -> None:
        cfg = _config_with_typography(
            heading="Inter, sans-serif",
            body="Georgia",
            code="Menlo",
        )
        # Swap one slot to a non-string; extractor must skip it gracefully.
        cfg["typography"]["body_font_family"] = None
        assert extract_font_families(cfg) == ["inter"]

    def test_case_insensitive_match(self) -> None:
        cfg = _config_with_typography(
            heading="iNtEr, sans-serif",
            body="Georgia, serif",
            code="Menlo, monospace",
        )
        assert extract_font_families(cfg) == ["inter"]


# ---------------------------------------------------------------------------
# Test class 2: generate_font_import_statement
# ---------------------------------------------------------------------------


class TestGenerateFontImportStatement:
    def test_empty_list_yields_empty_string(self) -> None:
        assert generate_font_import_statement([]) == ""

    def test_single_family_url_structure(self) -> None:
        out = generate_font_import_statement(["inter"])
        assert out.startswith("@import url('https://fonts.googleapis.com/css2?")
        assert "family=Inter:wght@400;600;700" in out
        assert out.endswith("&display=swap');")

    def test_multiple_families_joined_by_ampersand(self) -> None:
        out = generate_font_import_statement(["inter", "fira code"])
        # Two family= parameters appear in the order given.
        first = out.index("family=Inter")
        second = out.index("family=Fira+Code")
        assert first < second
        # Both connected by &, and &display=swap is the tail.
        assert out.count("family=") == 2
        assert out.endswith("&display=swap');")

    def test_display_swap_always_present(self) -> None:
        out = generate_font_import_statement(["inter"])
        assert "display=swap" in out

    def test_all_allowlist_entries_produce_valid_urls(self) -> None:
        # Every entry in the allowlist must produce a non-empty @import.
        for key in style_engine._GOOGLE_FONTS_ALLOWLIST:
            out = generate_font_import_statement([key])
            assert out.startswith("@import url('")
            assert out.endswith("');")
            # Sanity: the fragment stored in the allowlist appears verbatim.
            fragment = style_engine._GOOGLE_FONTS_ALLOWLIST[key]
            assert fragment in out


# ---------------------------------------------------------------------------
# Test class 3: compile_style integration
# ---------------------------------------------------------------------------


class TestCompileStyleFontLoader:
    def test_import_appears_before_root_for_google_fonts(
        self, tmp_path: Path
    ) -> None:
        cfg = _config_with_typography(
            heading="Inter, sans-serif",
            body="Georgia, serif",
            code="Fira Code, monospace",
        )
        cfg_path = tmp_path / "style_config.json"
        css_path = tmp_path / "style.css"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        compile_style(cfg_path, css_path)
        css = css_path.read_text(encoding="utf-8")

        assert "@import url(" in css
        assert "family=Inter:wght@400;600;700" in css
        assert "family=Fira+Code:wght@400;500" in css
        # @import must come before :root in the text.
        import_pos = css.index("@import")
        root_pos = css.index(":root")
        assert import_pos < root_pos

    def test_no_import_when_only_system_fonts(
        self, tmp_path: Path
    ) -> None:
        cfg = _config_with_typography(
            heading="Helvetica, sans-serif",
            body="Georgia, serif",
            code="Menlo, monospace",
        )
        cfg_path = tmp_path / "style_config.json"
        css_path = tmp_path / "style.css"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        compile_style(cfg_path, css_path)
        css = css_path.read_text(encoding="utf-8")

        assert "@import" not in css
        # Baseline preserved: :root block is still there.
        assert ":root" in css

    def test_single_google_font_emits_single_family_param(
        self, tmp_path: Path
    ) -> None:
        cfg = _config_with_typography(
            heading="Open Sans, sans-serif",
            body="Georgia, serif",
            code="Menlo, monospace",
        )
        cfg_path = tmp_path / "style_config.json"
        css_path = tmp_path / "style.css"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        compile_style(cfg_path, css_path)
        css = css_path.read_text(encoding="utf-8")

        assert css.count("family=") == 1
        assert "family=Open+Sans" in css

    def test_template_config_compiles_with_inter_and_fira_code(
        self, tmp_path: Path
    ) -> None:
        template_path = _PROJECT_ROOT / "src" / "unit_1" / "templates" / "style_config.json"
        if not template_path.exists():
            template_path = _PROJECT_ROOT / "templates" / "style_config.json"
        css_path = tmp_path / "style.css"
        compile_style(template_path, css_path)
        css = css_path.read_text(encoding="utf-8")

        # Two family= params: Inter (heading) + Fira Code (code).
        assert css.count("family=") == 2
        assert "family=Inter" in css
        assert "family=Fira+Code" in css


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
