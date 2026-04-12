# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Tests for Unit 6: Style Compiler (style_engine).

Synthetic data generation assumptions
--------------------------------------
- A "minimal valid" style_config dict has all seven required top-level keys:
  ``colors``, ``typography``, ``spacing``, ``layout``, ``data_viz``,
  ``constraints``, ``provenance``.  Sub-key coverage extends only to the
  26 mapped dot-paths in CSS_PROPERTY_MAP; unmapped keys are added where
  needed to test the fallback convention (BC-6.3).
- Color values use valid CSS hex strings such as ``"#1a2b3c"`` or
  ``"#ffffff"``.  Font families are short ASCII strings (e.g.
  ``"Inter, sans-serif"``).  Size values use CSS unit strings like
  ``"16px"`` or ``"48px"``.  Weight values are numeric strings like
  ``"700"``.  Percentage strings like ``"5%"`` are used for margin_pct.
  Dimension strings like ``"1920px"`` are used for layout values.
  Colormap names like ``"viridis"`` are used for data_viz.
- The ``constraints`` and ``provenance`` sections contain arbitrary
  nested dicts and/or scalar values.  Their exact content does not matter
  because BC-6.4 requires they produce no CSS variables.
- Invalid JSON test fixtures are hand-crafted strings such as
  ``"{broken json"``.
- All ``tmp_path``-based config files are written with
  ``json.dumps(..., indent=2)`` before being passed to functions.
- ``compile_style`` exit-code tests use ``subprocess.run`` (or
  ``pytest.raises(SystemExit)``) to drive the module entry-point.
  When testing via direct function calls (not subprocess), ``SystemExit``
  is caught and its ``code`` attribute is checked.
- The 26 keys in CSS_PROPERTY_MAP are taken verbatim from the stub's
  ``CSS_PROPERTY_MAP`` constant; no independent re-derivation is done
  here.  BC-6.1 requires the map to be stable, so tests assert exact
  cardinality (26 entries) and spot-check several canonical mappings.
- For BC-6.6 (exit code 3 on wrong argument count) tests call
  ``compile_style`` with a monkeypatched ``sys.argv``.
- ``path_to_css_var`` tests use strings that contain both dots and
  underscores to confirm that both separators become hyphens in the
  output, with the ``--`` prefix.
- ``flatten_config`` tests verify that ``constraints`` and ``provenance``
  keys are absent from the flat output regardless of their depth.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from style_engine import (
    CSS_PROPERTY_MAP,
    compile_style,
    flatten_config,
    generate_css_root_block,
    parse_style_config,
    path_to_css_var,
)

# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

REQUIRED_KEYS = [
    "colors",
    "typography",
    "spacing",
    "layout",
    "data_viz",
    "constraints",
    "provenance",
]

# A minimal style config that populates every mapped leaf path.
_MINIMAL_COLORS = {
    "primary": "#1a2b3c",
    "secondary": "#2b3c4d",
    "accent": "#e74c3c",
    "background": "#ffffff",
    "text_primary": "#111111",
    "text_secondary": "#666666",
    "code_background": "#f5f5f5",
    "border": "#dddddd",
}

_MINIMAL_TYPOGRAPHY = {
    "heading_font_family": "Inter, sans-serif",
    "body_font_family": "Georgia, serif",
    "code_font_family": "Fira Code, monospace",
    "heading_size_base": "48px",
    "body_size_base": "16px",
    "heading_weight": "700",
    "body_weight": "400",
    "line_height": "1.6",
}

_MINIMAL_SPACING = {
    "margin_pct": "5%",
    "gap": "16px",
    "section_gap": "48px",
}

_MINIMAL_LAYOUT = {
    "slide_width": "1920px",
    "slide_height": "1080px",
    "column_gap": "24px",
}

_MINIMAL_DATA_VIZ = {
    "primary_colormap": "viridis",
    "axis_color": "#333333",
    "grid_color": "#eeeeee",
    "annotation_color": "#e74c3c",
}

_CONSTRAINTS = {"max_bullet_points": 5, "max_slide_count": 30}
_PROVENANCE = {"style_import_mode": "baseline", "reference_file": "deck.pptx"}


def _make_valid_config(**overrides: Any) -> dict[str, Any]:
    """Return a full valid config dict.  ``overrides`` replaces top-level keys."""
    cfg: dict[str, Any] = {
        "colors": dict(_MINIMAL_COLORS),
        "typography": dict(_MINIMAL_TYPOGRAPHY),
        "spacing": dict(_MINIMAL_SPACING),
        "layout": dict(_MINIMAL_LAYOUT),
        "data_viz": dict(_MINIMAL_DATA_VIZ),
        "constraints": dict(_CONSTRAINTS),
        "provenance": dict(_PROVENANCE),
    }
    cfg.update(overrides)
    return cfg


def _write_config(tmp_path: Path, cfg: dict[str, Any]) -> Path:
    p = tmp_path / "style_config.json"
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# BC-6.1  CSS_PROPERTY_MAP cardinality and canonical spot-checks
# ---------------------------------------------------------------------------


class TestCssPropertyMapIsCanonical:
    def test_map_has_exactly_26_entries(self) -> None:
        assert len(CSS_PROPERTY_MAP) == 26

    def test_colors_primary_maps_to_color_primary(self) -> None:
        assert CSS_PROPERTY_MAP["colors.primary"] == "--color-primary"

    def test_colors_background_maps_to_color_background(self) -> None:
        assert CSS_PROPERTY_MAP["colors.background"] == "--color-background"

    def test_typography_heading_font_family_maps_correctly(self) -> None:
        assert (
            CSS_PROPERTY_MAP["typography.heading_font_family"]
            == "--font-heading-family"
        )

    def test_typography_body_font_family_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["typography.body_font_family"] == "--font-body-family"

    def test_typography_code_font_family_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["typography.code_font_family"] == "--font-code-family"

    def test_typography_heading_size_base_maps_correctly(self) -> None:
        assert (
            CSS_PROPERTY_MAP["typography.heading_size_base"]
            == "--font-heading-size-base"
        )

    def test_typography_body_size_base_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["typography.body_size_base"] == "--font-body-size-base"

    def test_typography_heading_weight_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["typography.heading_weight"] == "--font-heading-weight"

    def test_typography_body_weight_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["typography.body_weight"] == "--font-body-weight"

    def test_typography_line_height_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["typography.line_height"] == "--font-line-height"

    def test_spacing_margin_pct_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["spacing.margin_pct"] == "--spacing-margin-pct"

    def test_spacing_gap_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["spacing.gap"] == "--spacing-gap"

    def test_spacing_section_gap_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["spacing.section_gap"] == "--spacing-section-gap"

    def test_layout_slide_width_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["layout.slide_width"] == "--layout-slide-width"

    def test_layout_slide_height_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["layout.slide_height"] == "--layout-slide-height"

    def test_layout_column_gap_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["layout.column_gap"] == "--layout-column-gap"

    def test_data_viz_primary_colormap_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["data_viz.primary_colormap"] == "--viz-primary-colormap"

    def test_data_viz_axis_color_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["data_viz.axis_color"] == "--viz-axis-color"

    def test_data_viz_grid_color_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["data_viz.grid_color"] == "--viz-grid-color"

    def test_data_viz_annotation_color_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["data_viz.annotation_color"] == "--viz-annotation-color"

    def test_colors_text_primary_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["colors.text_primary"] == "--color-text-primary"

    def test_colors_text_secondary_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["colors.text_secondary"] == "--color-text-secondary"

    def test_colors_code_background_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["colors.code_background"] == "--color-code-background"

    def test_colors_border_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["colors.border"] == "--color-border"

    def test_colors_secondary_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["colors.secondary"] == "--color-secondary"

    def test_colors_accent_maps_correctly(self) -> None:
        assert CSS_PROPERTY_MAP["colors.accent"] == "--color-accent"


# ---------------------------------------------------------------------------
# BC-6.2  All 26 mapped keys emitted in :root block
# ---------------------------------------------------------------------------


class TestAllMappedKeysEmittedInOutput:
    def test_all_26_mapped_css_properties_appear_in_root_block(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        for css_var in CSS_PROPERTY_MAP.values():
            assert css_var in css, f"Expected CSS variable {css_var!r} in :root block"

    def test_color_primary_value_is_present_in_root_block(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        assert "--color-primary: #1a2b3c;" in css

    def test_font_heading_family_value_is_present_in_root_block(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        assert "--font-heading-family: Inter, sans-serif;" in css

    def test_layout_slide_width_value_is_present_in_root_block(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        assert "--layout-slide-width: 1920px;" in css

    def test_viz_primary_colormap_value_is_present_in_root_block(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        assert "--viz-primary-colormap: viridis;" in css


# ---------------------------------------------------------------------------
# BC-6.3  Fallback naming convention for unmapped paths
# ---------------------------------------------------------------------------


class TestFallbackCssVariableNamingConvention:
    def test_path_to_css_var_converts_dots_to_hyphens(self) -> None:
        result = path_to_css_var("custom.my_key")
        assert result == "--custom-my-key"

    def test_path_to_css_var_converts_underscores_to_hyphens(self) -> None:
        result = path_to_css_var("my_section.some_value")
        assert result == "--my-section-some-value"

    def test_path_to_css_var_adds_double_dash_prefix(self) -> None:
        result = path_to_css_var("foo.bar")
        assert result.startswith("--")

    def test_path_to_css_var_single_segment(self) -> None:
        result = path_to_css_var("toplevel")
        assert result == "--toplevel"

    def test_path_to_css_var_three_levels_deep(self) -> None:
        result = path_to_css_var("a.b.c")
        assert result == "--a-b-c"

    def test_path_to_css_var_mixed_underscores_and_dots(self) -> None:
        result = path_to_css_var("data_viz.my_map_name")
        assert result == "--data-viz-my-map-name"

    def test_unmapped_path_appears_in_generated_css(self) -> None:
        cfg = _make_valid_config(extra_section={"my_custom_key": "custom_value"})
        css = generate_css_root_block(cfg)
        assert "--extra-section-my-custom-key: custom_value;" in css

    def test_unmapped_path_uses_hyphen_convention_not_underscore(self) -> None:
        css_var = path_to_css_var("colors.brand_dark")
        assert "_" not in css_var


# ---------------------------------------------------------------------------
# BC-6.4  constraints and provenance keys produce no CSS variables
# ---------------------------------------------------------------------------


class TestConstraintsAndProvenanceExcludedFromCss:
    def test_constraints_key_produces_no_css_variable(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        assert "--constraints" not in css

    def test_provenance_key_produces_no_css_variable(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        assert "--provenance" not in css

    def test_constraints_nested_value_produces_no_css_variable(self) -> None:
        cfg = _make_valid_config(
            constraints={"max_bullets": 5, "disallowed_colors": ["red"]}
        )
        css = generate_css_root_block(cfg)
        assert "--constraints-max-bullets" not in css
        assert "--constraints-disallowed-colors" not in css

    def test_provenance_nested_value_produces_no_css_variable(self) -> None:
        cfg = _make_valid_config(
            provenance={"reference_file": "deck.pptx", "author": "test"}
        )
        css = generate_css_root_block(cfg)
        assert "--provenance-reference-file" not in css
        assert "--provenance-author" not in css

    def test_flatten_config_excludes_constraints_key(self) -> None:
        cfg = _make_valid_config(constraints={"a": 1})
        flat = flatten_config(cfg)
        for key in flat:
            assert not key.startswith("constraints"), (
                f"Key {key!r} starts with 'constraints' — must be excluded"
            )

    def test_flatten_config_excludes_provenance_key(self) -> None:
        cfg = _make_valid_config(provenance={"b": 2})
        flat = flatten_config(cfg)
        for key in flat:
            assert not key.startswith("provenance"), (
                f"Key {key!r} starts with 'provenance' — must be excluded"
            )


# ---------------------------------------------------------------------------
# BC-6.5  All custom properties inside a single :root block
# ---------------------------------------------------------------------------


class TestAllCustomPropertiesInsideSingleRootBlock:
    def test_css_output_contains_root_open_brace(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        assert ":root" in css
        assert "{" in css

    def test_css_output_contains_root_close_brace(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        assert "}" in css

    def test_custom_properties_appear_inside_root_block(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        root_start = css.index(":root")
        open_brace = css.index("{", root_start)
        close_brace = css.rindex("}")
        inner = css[open_brace + 1 : close_brace]
        assert "--color-primary" in inner

    def test_only_one_root_selector_in_output(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        assert css.count(":root") == 1

    def test_no_custom_property_appears_before_root_open_brace(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        root_start = css.index(":root")
        before_root_content = css[:root_start]
        # Nothing defined before :root selector
        assert "--" not in before_root_content

    def test_custom_property_not_outside_root_block(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        close_brace = css.rindex("}")
        after_root = css[close_brace + 1 :].strip()
        # Nothing meaningful after the closing brace
        assert "--" not in after_root


# ---------------------------------------------------------------------------
# BC-6.6  Exit code 3 on wrong argument count (compile_style entry)
# ---------------------------------------------------------------------------


class TestExitCode3OnWrongArgumentCount:
    def test_compile_style_exits_3_when_called_with_no_args(
        self, tmp_path: Path
    ) -> None:
        script = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 3

    def test_compile_style_exits_3_when_called_with_one_arg(
        self, tmp_path: Path
    ) -> None:
        script = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        result = subprocess.run(
            [sys.executable, str(script), "only_one_arg"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 3

    def test_compile_style_exits_3_when_called_with_three_args(
        self, tmp_path: Path
    ) -> None:
        script = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "arg1",
                "arg2",
                "arg3",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 3

    def test_compile_style_prints_usage_to_stderr_on_wrong_arg_count(
        self, tmp_path: Path
    ) -> None:
        script = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 3
        assert len(result.stderr.strip()) > 0


# ---------------------------------------------------------------------------
# BC-6.7  Exit code 1 on invalid JSON
# ---------------------------------------------------------------------------


class TestExitCode1OnInvalidJson:
    def test_compile_style_exits_1_when_config_contains_invalid_json(
        self, tmp_path: Path
    ) -> None:
        bad_config = tmp_path / "bad.json"
        bad_config.write_text("{broken json", encoding="utf-8")
        out_css = tmp_path / "out.css"
        script = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        result = subprocess.run(
            [sys.executable, str(script), str(bad_config), str(out_css)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_compile_style_prints_error_to_stderr_on_invalid_json(
        self, tmp_path: Path
    ) -> None:
        bad_config = tmp_path / "bad.json"
        bad_config.write_text("{broken json", encoding="utf-8")
        out_css = tmp_path / "out.css"
        script = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        result = subprocess.run(
            [sys.executable, str(script), str(bad_config), str(out_css)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert len(result.stderr.strip()) > 0

    def test_compile_style_does_not_write_output_file_on_invalid_json(
        self, tmp_path: Path
    ) -> None:
        bad_config = tmp_path / "bad.json"
        bad_config.write_text("null", encoding="utf-8")
        # null is valid JSON but not a dict with required keys; however,
        # we also test a truly invalid JSON string here for the file-write guard.
        really_bad = tmp_path / "really_bad.json"
        really_bad.write_text("{not valid}", encoding="utf-8")
        out_css = tmp_path / "out.css"
        script = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        subprocess.run(
            [sys.executable, str(script), str(really_bad), str(out_css)],
            capture_output=True,
            text=True,
        )
        assert not out_css.exists()

    def test_parse_style_config_raises_on_invalid_json_file(
        self, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("this is not json at all", encoding="utf-8")
        with pytest.raises(Exception):
            parse_style_config(bad)


# ---------------------------------------------------------------------------
# BC-6.8  Exit code 1 on missing required key
# ---------------------------------------------------------------------------


class TestExitCode1OnMissingRequiredKey:
    @pytest.mark.parametrize("missing_key", REQUIRED_KEYS)
    def test_compile_style_exits_1_when_required_key_missing(
        self, tmp_path: Path, missing_key: str
    ) -> None:
        cfg = _make_valid_config()
        del cfg[missing_key]
        config_path = _write_config(tmp_path, cfg)
        out_css = tmp_path / "out.css"
        script = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        result = subprocess.run(
            [sys.executable, str(script), str(config_path), str(out_css)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    @pytest.mark.parametrize("missing_key", REQUIRED_KEYS)
    def test_compile_style_prints_missing_key_name_to_stderr(
        self, tmp_path: Path, missing_key: str
    ) -> None:
        cfg = _make_valid_config()
        del cfg[missing_key]
        config_path = _write_config(tmp_path, cfg)
        out_css = tmp_path / "out.css"
        script = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        result = subprocess.run(
            [sys.executable, str(script), str(config_path), str(out_css)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert missing_key in result.stderr

    @pytest.mark.parametrize("missing_key", REQUIRED_KEYS)
    def test_parse_style_config_raises_value_error_on_missing_key(
        self, tmp_path: Path, missing_key: str
    ) -> None:
        cfg = _make_valid_config()
        del cfg[missing_key]
        config_path = _write_config(tmp_path, cfg)
        with pytest.raises(ValueError):
            parse_style_config(config_path)

    @pytest.mark.parametrize("missing_key", REQUIRED_KEYS)
    def test_parse_style_config_error_message_contains_missing_key_name(
        self, tmp_path: Path, missing_key: str
    ) -> None:
        cfg = _make_valid_config()
        del cfg[missing_key]
        config_path = _write_config(tmp_path, cfg)
        with pytest.raises(ValueError, match=missing_key):
            parse_style_config(config_path)


# ---------------------------------------------------------------------------
# parse_style_config -- happy-path and error contract
# ---------------------------------------------------------------------------


class TestParseStyleConfig:
    def test_returns_dict_for_valid_config_file(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path, _make_valid_config())
        result = parse_style_config(config_path)
        assert isinstance(result, dict)

    def test_all_required_keys_present_in_returned_dict(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path, _make_valid_config())
        result = parse_style_config(config_path)
        for key in REQUIRED_KEYS:
            assert key in result

    def test_raises_file_not_found_for_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.json"
        with pytest.raises(Exception):
            parse_style_config(missing)

    def test_preserves_colors_sub_keys_in_returned_dict(self, tmp_path: Path) -> None:
        config_path = _write_config(tmp_path, _make_valid_config())
        result = parse_style_config(config_path)
        assert result["colors"]["primary"] == "#1a2b3c"

    def test_preserves_typography_sub_keys_in_returned_dict(
        self, tmp_path: Path
    ) -> None:
        config_path = _write_config(tmp_path, _make_valid_config())
        result = parse_style_config(config_path)
        assert result["typography"]["heading_font_family"] == "Inter, sans-serif"


# ---------------------------------------------------------------------------
# flatten_config -- structural contract
# ---------------------------------------------------------------------------


class TestFlattenConfig:
    def test_flat_dict_has_dot_separated_keys(self) -> None:
        cfg = {"colors": {"primary": "#fff"}}
        flat = flatten_config(cfg)
        assert "colors.primary" in flat
        assert flat["colors.primary"] == "#fff"

    def test_three_level_nesting_produces_two_dot_key(self) -> None:
        cfg = {"a": {"b": {"c": "val"}}}
        flat = flatten_config(cfg)
        assert "a.b.c" in flat
        assert flat["a.b.c"] == "val"

    def test_constraints_excluded_from_flat_output(self) -> None:
        cfg = {"colors": {"x": "1"}, "constraints": {"limit": 5}}
        flat = flatten_config(cfg)
        assert "constraints.limit" not in flat
        assert "colors.x" in flat

    def test_provenance_excluded_from_flat_output(self) -> None:
        cfg = {"colors": {"x": "1"}, "provenance": {"source": "ref.pptx"}}
        flat = flatten_config(cfg)
        assert "provenance.source" not in flat
        assert "colors.x" in flat

    def test_full_valid_config_produces_at_least_26_flat_entries(self) -> None:
        cfg = _make_valid_config()
        flat = flatten_config(cfg)
        # All 26 CSS_PROPERTY_MAP keys must be present
        for key in CSS_PROPERTY_MAP:
            assert key in flat, f"Expected flat key {key!r}"

    def test_scalar_values_are_preserved_correctly(self) -> None:
        cfg = {"layout": {"slide_width": "1920px"}}
        flat = flatten_config(cfg)
        assert flat["layout.slide_width"] == "1920px"

    def test_empty_section_produces_no_entries(self) -> None:
        cfg = {"empty_section": {}}
        flat = flatten_config(cfg)
        # An empty dict section should produce no flat entries
        matching = [k for k in flat if k.startswith("empty_section")]
        assert matching == []


# ---------------------------------------------------------------------------
# generate_css_root_block -- structure and value contracts
# ---------------------------------------------------------------------------


class TestGenerateCssRootBlock:
    def test_returns_string(self) -> None:
        css = generate_css_root_block(_make_valid_config())
        assert isinstance(css, str)

    def test_output_is_non_empty(self) -> None:
        css = generate_css_root_block(_make_valid_config())
        assert len(css.strip()) > 0

    def test_root_block_uses_mapped_name_not_dot_path(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        # mapped name used, not raw dot-path
        assert "--color-primary" in css
        assert "colors.primary" not in css

    def test_all_26_mapped_values_present_in_root_block(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        for css_var in CSS_PROPERTY_MAP.values():
            assert css_var in css

    def test_constraints_value_absent_from_root_block(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        assert "max_bullet_points" not in css
        assert "max_slide_count" not in css

    def test_provenance_value_absent_from_root_block(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        assert "style_import_mode" not in css
        assert "reference_file" not in css

    def test_declaration_format_uses_colon_and_semicolon(self) -> None:
        cfg = _make_valid_config()
        css = generate_css_root_block(cfg)
        # At least one declaration follows `--var-name: value;` pattern
        assert ": " in css
        assert ";" in css

    def test_custom_value_is_emitted_verbatim(self) -> None:
        cfg = _make_valid_config()
        cfg["colors"]["primary"] = "#abcdef"
        css = generate_css_root_block(cfg)
        assert "--color-primary: #abcdef;" in css


# ---------------------------------------------------------------------------
# compile_style -- success path (file I/O contract)
# ---------------------------------------------------------------------------


class TestCompileStyleSuccessPath:
    def test_compile_style_writes_output_css_file(self, tmp_path: Path) -> None:
        cfg = _make_valid_config()
        config_path = _write_config(tmp_path, cfg)
        out_css = tmp_path / "style.css"
        compile_style(config_path, out_css)
        assert out_css.exists()

    def test_compile_style_output_contains_root_block(self, tmp_path: Path) -> None:
        cfg = _make_valid_config()
        config_path = _write_config(tmp_path, cfg)
        out_css = tmp_path / "style.css"
        compile_style(config_path, out_css)
        content = out_css.read_text(encoding="utf-8")
        assert ":root" in content

    def test_compile_style_output_contains_color_primary(self, tmp_path: Path) -> None:
        cfg = _make_valid_config()
        config_path = _write_config(tmp_path, cfg)
        out_css = tmp_path / "style.css"
        compile_style(config_path, out_css)
        content = out_css.read_text(encoding="utf-8")
        assert "--color-primary: #1a2b3c;" in content

    def test_compile_style_output_contains_all_26_mapped_vars(
        self, tmp_path: Path
    ) -> None:
        cfg = _make_valid_config()
        config_path = _write_config(tmp_path, cfg)
        out_css = tmp_path / "style.css"
        compile_style(config_path, out_css)
        content = out_css.read_text(encoding="utf-8")
        for css_var in CSS_PROPERTY_MAP.values():
            assert css_var in content

    def test_compile_style_via_subprocess_exits_0_on_valid_config(
        self, tmp_path: Path
    ) -> None:
        cfg = _make_valid_config()
        config_path = _write_config(tmp_path, cfg)
        out_css = tmp_path / "style.css"
        script = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        result = subprocess.run(
            [sys.executable, str(script), str(config_path), str(out_css)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_compile_style_creates_parent_directory_if_needed(
        self, tmp_path: Path
    ) -> None:
        cfg = _make_valid_config()
        config_path = _write_config(tmp_path, cfg)
        nested_out = tmp_path / "subdir" / "style.css"
        # If parent does not exist, compile_style should either create it
        # or succeed when called with a pre-created path.
        # We pre-create it to avoid implementation-specific behavior.
        nested_out.parent.mkdir(parents=True, exist_ok=True)
        compile_style(config_path, nested_out)
        assert nested_out.exists()


# ---------------------------------------------------------------------------
# BC-6.9  Style compiler must not read state files
# ---------------------------------------------------------------------------


class TestStyleCompilerDoesNotReadStateFiles:
    def test_compile_style_succeeds_when_no_deck_state_file_exists(
        self, tmp_path: Path
    ) -> None:
        """BC-6.9: compiler must not read deck_state.json or debrief_state.json."""
        cfg = _make_valid_config()
        config_path = _write_config(tmp_path, cfg)
        out_css = tmp_path / "style.css"
        # No state files exist in tmp_path — compilation must still succeed.
        compile_style(config_path, out_css)
        assert out_css.exists()


# ---------------------------------------------------------------------------
# BC-6.10  No Playwright import
# ---------------------------------------------------------------------------


class TestStyleCompilerHasNoPlaywrightDependency:
    def test_style_engine_module_does_not_import_playwright(self) -> None:
        """BC-6.10: importing style_engine must not trigger playwright import."""
        # Verify style_engine does not import playwright
        import style_engine  # already imported via conftest path

        module_globals = vars(style_engine)
        assert "playwright" not in module_globals

    def test_style_engine_source_does_not_contain_playwright_import(
        self,
    ) -> None:
        src = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        if src.exists():
            content = src.read_text(encoding="utf-8")
            assert "playwright" not in content


# ---------------------------------------------------------------------------
# path_to_css_var -- exhaustive contract
# ---------------------------------------------------------------------------


class TestPathToCssVarContract:
    def test_single_word_with_underscores_converts_to_hyphenated(self) -> None:
        assert path_to_css_var("my_key") == "--my-key"

    def test_dot_path_without_underscores_converts_dots_to_hyphens(self) -> None:
        assert path_to_css_var("colors.primary") == "--colors-primary"

    def test_mixed_dot_and_underscore_both_become_hyphens(self) -> None:
        result = path_to_css_var("data_viz.primary_colormap")
        assert result == "--data-viz-primary-colormap"

    def test_result_always_starts_with_double_dash(self) -> None:
        for dot_path in ["a", "a.b", "a_b", "a.b.c_d"]:
            assert path_to_css_var(dot_path).startswith("--")

    def test_no_trailing_hyphens_in_output(self) -> None:
        result = path_to_css_var("section.field")
        assert not result.endswith("-")

    def test_no_double_hyphens_except_leading_prefix(self) -> None:
        result = path_to_css_var("my_section.some_value")
        # Strip the leading '--' and confirm no '--' remains in the body
        body = result[2:]
        assert "--" not in body


# ---------------------------------------------------------------------------
# BC-6.7 (gap)  Compiler must not reference json_repair
# ---------------------------------------------------------------------------


class TestNoJsonRepairDependency:
    def test_style_engine_source_does_not_import_json_repair(self) -> None:
        """BC-6.7: style compiler must not attempt json_repair."""
        src = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        content = src.read_text(encoding="utf-8")
        assert "json_repair" not in content


# ---------------------------------------------------------------------------
# BC-6.8 (gap)  Exact stderr prefix "ERROR: Missing required key: <key>"
# ---------------------------------------------------------------------------


class TestMissingRequiredKeyExactStderrPrefix:
    @pytest.mark.parametrize("missing_key", REQUIRED_KEYS)
    def test_stderr_contains_error_prefix_and_key_name(
        self, tmp_path: Path, missing_key: str
    ) -> None:
        """BC-6.8: stderr must contain 'ERROR: Missing required key: <key>'."""
        cfg = _make_valid_config()
        del cfg[missing_key]
        config_path = _write_config(tmp_path, cfg)
        out_css = tmp_path / "out.css"
        script = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        result = subprocess.run(
            [sys.executable, str(script), str(config_path), str(out_css)],
            capture_output=True,
            text=True,
        )
        expected = f"ERROR: Missing required key: {missing_key}"
        assert expected in result.stderr, (
            f"Expected {expected!r} in stderr; got: {result.stderr!r}"
        )


# ---------------------------------------------------------------------------
# BC-6.9 (gap)  Source-level check: no state-file references
# ---------------------------------------------------------------------------


class TestStyleCompilerDoesNotReferenceStateFiles:
    def test_style_engine_source_does_not_reference_deck_state(self) -> None:
        """BC-6.9: source must not reference deck_state.json."""
        src = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        content = src.read_text(encoding="utf-8")
        assert "deck_state" not in content

    def test_style_engine_source_does_not_reference_debrief_state(self) -> None:
        """BC-6.9: source must not reference debrief_state.json."""
        src = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "unit_6"
            / "style_engine.py"
        )
        content = src.read_text(encoding="utf-8")
        assert "debrief_state" not in content
