# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 6: Style Compiler (style_engine).

Read a style_config.json and emit a CSS :root block of custom properties.

Entry point (CLI):
    python style_engine.py <style_config_path> <output_css_path>

Exit codes:
    0 — success
    1 — invalid JSON, missing required keys, or file I/O failure
    3 — usage error (wrong number of positional arguments)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Canonical CSS custom-property name mapping.
# 26 entries — single source of truth.  Drift vs style_guide.md is a bug.
# ---------------------------------------------------------------------------

CSS_PROPERTY_MAP: dict[str, str] = {
    "colors.primary": "--color-primary",
    "colors.secondary": "--color-secondary",
    "colors.accent": "--color-accent",
    "colors.background": "--color-background",
    "colors.text_primary": "--color-text-primary",
    "colors.text_secondary": "--color-text-secondary",
    "colors.code_background": "--color-code-background",
    "colors.border": "--color-border",
    "typography.heading_font_family": "--font-heading-family",
    "typography.body_font_family": "--font-body-family",
    "typography.code_font_family": "--font-code-family",
    "typography.heading_size_base": "--font-heading-size-base",
    "typography.body_size_base": "--font-body-size-base",
    "typography.heading_weight": "--font-heading-weight",
    "typography.body_weight": "--font-body-weight",
    "typography.line_height": "--font-line-height",
    "spacing.margin_pct": "--spacing-margin-pct",
    "spacing.gap": "--spacing-gap",
    "spacing.section_gap": "--spacing-section-gap",
    "layout.slide_width": "--layout-slide-width",
    "layout.slide_height": "--layout-slide-height",
    "layout.column_gap": "--layout-column-gap",
    "data_viz.primary_colormap": "--viz-primary-colormap",
    "data_viz.axis_color": "--viz-axis-color",
    "data_viz.grid_color": "--viz-grid-color",
    "data_viz.annotation_color": "--viz-annotation-color",
}

# Top-level config keys excluded from CSS output (structural metadata only).
_EXCLUDED_KEYS: frozenset[str] = frozenset({"constraints", "provenance"})


# ---------------------------------------------------------------------------
# Google Fonts allowlist (BUG-AUDIT-71 / BC-6.14 / REQ-STYLE-FONT-LOADER-1)
#
# Map canonical lowercased family name → Google Fonts CSS2 family-fragment.
# A "family-fragment" is the substring following `family=` in the Google Fonts
# CSS2 URL: ``family=Inter:wght@400;600;700`` — includes the human-cased
# family name, a ``:`` weight axis spec, and any weight list. The compiler
# emits one ``@import url('https://fonts.googleapis.com/css2?family=...&display=swap');``
# at the top of the compiled stylesheet containing every allowlist-matched
# family discovered in ``typography.*_font_family`` fields.
#
# Non-allowlist families (``Georgia``, ``Arial``, generic families like
# ``sans-serif`` / ``serif`` / ``monospace``) are system fonts — the browser
# resolves them locally, no loader needed.
#
# Weight lists are chosen conservatively to cover heading and body use:
# body weight 400, heading weight 600-700. Monospace families get 400 and
# 500 (typical for code). Entries can be tuned over time without breaking
# the contract — only the allowlist KEYS are semantically load-bearing.
# ---------------------------------------------------------------------------


_GOOGLE_FONTS_ALLOWLIST: dict[str, str] = {
    "inter": "Inter:wght@400;600;700",
    "ibm plex sans": "IBM+Plex+Sans:wght@400;600;700",
    "ibm plex serif": "IBM+Plex+Serif:wght@400;600;700",
    "ibm plex mono": "IBM+Plex+Mono:wght@400;500",
    "roboto": "Roboto:wght@400;500;700",
    "roboto mono": "Roboto+Mono:wght@400;500",
    "roboto slab": "Roboto+Slab:wght@400;600;700",
    "open sans": "Open+Sans:wght@400;600;700",
    "fira sans": "Fira+Sans:wght@400;600;700",
    "fira code": "Fira+Code:wght@400;500",
    "jetbrains mono": "JetBrains+Mono:wght@400;500",
    "lato": "Lato:wght@400;700",
    "merriweather": "Merriweather:wght@400;700",
    "source sans 3": "Source+Sans+3:wght@400;600;700",
    "source serif 4": "Source+Serif+4:wght@400;600;700",
    "source code pro": "Source+Code+Pro:wght@400;500",
    "work sans": "Work+Sans:wght@400;600;700",
    "space grotesk": "Space+Grotesk:wght@400;500;700",
    "space mono": "Space+Mono:wght@400;700",
    "noto sans": "Noto+Sans:wght@400;600;700",
    "noto serif": "Noto+Serif:wght@400;600;700",
    "poppins": "Poppins:wght@400;600;700",
    "montserrat": "Montserrat:wght@400;600;700",
}


_GOOGLE_FONTS_URL_BASE = "https://fonts.googleapis.com/css2"

# All seven keys required at the top level of style_config.json.
_REQUIRED_KEYS: list[str] = [
    "colors",
    "typography",
    "spacing",
    "layout",
    "data_viz",
    "constraints",
    "provenance",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def path_to_css_var(dot_path: str) -> str:
    """Apply fallback CSS variable naming convention.

    Convert a dot-path (and underscores) to ``--hyphenated-name``.

    Examples::

        path_to_css_var("my_section.some_value")  # "--my-section-some-value"
        path_to_css_var("colors.primary")          # "--colors-primary"
    """
    # Replace both '.' and '_' with '-', then prepend '--'.
    hyphenated = dot_path.replace(".", "-").replace("_", "-")
    return f"--{hyphenated}"


def flatten_config(
    config: dict[str, Any],
    prefix: str = "",
) -> dict[str, Any]:
    """Recursively flatten a nested config dict into dot-path -> value pairs.

    Skips the ``constraints`` and ``provenance`` top-level keys entirely;
    they must not appear in the flattened output.

    Example::

        {"colors": {"primary": "#fff"}} -> {"colors.primary": "#fff"}
    """
    result: dict[str, Any] = {}
    for key, value in config.items():
        # Determine the full dot-path for this key.
        full_path = f"{prefix}.{key}" if prefix else key

        # Skip excluded top-level keys (only apply exclusion at root level,
        # i.e., when prefix is empty and the key itself is excluded).
        top_key = full_path.split(".")[0]
        if top_key in _EXCLUDED_KEYS:
            continue

        if isinstance(value, dict):
            # Recurse into nested dicts.
            nested = flatten_config(value, prefix=full_path)
            result.update(nested)
        else:
            result[full_path] = value
    return result


def generate_css_root_block(config: dict[str, Any]) -> str:
    """Generate the ``:root { ... }`` CSS block from the config dict.

    For each leaf value:
    - If its dot-path key is in ``CSS_PROPERTY_MAP``, emit the canonical
      mapped CSS variable name.
    - Otherwise, apply the fallback naming convention via ``path_to_css_var``.

    ``constraints`` and ``provenance`` sections are excluded from output.
    Returns the full ``:root`` block as a single string.
    """
    flat = flatten_config(config)

    # BUG-AUDIT-40: warn on unmapped config keys. These get the fallback
    # naming convention which may not match what slides expect. The
    # canonical template's keys are all in CSS_PROPERTY_MAP; unmapped
    # keys indicate the stylist drifted to non-canonical names.
    unmapped = [
        p for p in flat
        if p not in CSS_PROPERTY_MAP
    ]
    if unmapped:
        import sys

        print(
            f"WARNING: {len(unmapped)} style_config key(s) not in "
            f"CSS_PROPERTY_MAP (using fallback naming — may not match "
            f"slide CSS expectations): {', '.join(sorted(unmapped))}",
            file=sys.stderr,
        )

    lines: list[str] = [":root {"]
    for dot_path, value in flat.items():
        css_var = CSS_PROPERTY_MAP.get(dot_path, path_to_css_var(dot_path))
        lines.append(f"  {css_var}: {value};")
    lines.append("}")
    # Default slide background — ensures every slide inherits the deck's
    # background color via the custom property set above.
    lines.append(".slide { background-color: var(--color-background, #ffffff); }")

    return "\n".join(lines)


def _normalize_family(raw: str) -> str:
    """Normalize a comma-separated font stack's first family to its
    lookup key: strip whitespace and surrounding quotes, then lowercase.

    Used by ``extract_font_families`` to match against
    ``_GOOGLE_FONTS_ALLOWLIST`` (which is keyed by lowercased family name).
    """
    # First family is before the first comma; ignore fallbacks.
    first = raw.split(",", 1)[0].strip()
    # Strip matched surrounding quotes (single or double).
    if len(first) >= 2 and first[0] == first[-1] and first[0] in ("'", '"'):
        first = first[1:-1].strip()
    return first.lower()


def extract_font_families(config: dict[str, Any]) -> list[str]:
    """Return the deduped, stable-ordered list of Google Fonts allowlist
    keys referenced in the config's typography section.

    Scans ``typography.heading_font_family``, ``typography.body_font_family``,
    and ``typography.code_font_family`` — only the first family in each
    comma-separated stack is considered (fallbacks like ``sans-serif`` or
    ``Helvetica`` are browser-resolved and need no loader).

    Families not in ``_GOOGLE_FONTS_ALLOWLIST`` are filtered out silently.
    The order of the returned list is the discovery order across the three
    typography slots (heading → body → code), with later duplicates removed.

    Args:
        config: A parsed ``style_config.json`` dict.

    Returns:
        A list of allowlist keys (lowercased family names).

    See BC-6.14 and BUG-AUDIT-71.
    """
    typography = config.get("typography", {}) if isinstance(config, dict) else {}
    if not isinstance(typography, dict):
        return []

    # Discovery order matters: heading first, body second, code third —
    # so the emitted URL lists headings before body fonts.
    slots = (
        "heading_font_family",
        "body_font_family",
        "code_font_family",
    )
    seen: list[str] = []
    for slot in slots:
        value = typography.get(slot)
        if not isinstance(value, str) or not value.strip():
            continue
        canonical = _normalize_family(value)
        if canonical in _GOOGLE_FONTS_ALLOWLIST and canonical not in seen:
            seen.append(canonical)
    return seen


def generate_font_import_statement(families: list[str]) -> str:
    """Build the single ``@import`` line that loads every allowlist-matched
    family from Google Fonts CSS2, or return ``""`` when the list is empty.

    The resulting URL has one ``family=<fragment>`` parameter per family,
    in the order received, plus ``&display=swap`` as the final parameter
    so text renders in the system fallback while the web font downloads.

    Example::

        generate_font_import_statement(["inter", "fira code"])
        # "@import url('https://fonts.googleapis.com/css2"
        # "?family=Inter:wght@400;600;700"
        # "&family=Fira+Code:wght@400;500"
        # "&display=swap');"

    See BC-6.14 and BUG-AUDIT-71.
    """
    if not families:
        return ""
    fragments = [_GOOGLE_FONTS_ALLOWLIST[f] for f in families]
    query = "&".join(f"family={frag}" for frag in fragments)
    url = f"{_GOOGLE_FONTS_URL_BASE}?{query}&display=swap"
    return f"@import url('{url}');"


def parse_style_config(config_path: Path) -> dict[str, Any]:
    """Read and parse ``config_path`` as JSON.

    Validates that all seven required top-level keys are present.

    Raises:
        FileNotFoundError: if ``config_path`` does not exist.
        ValueError: if the file contains invalid JSON or is missing a
            required key.  The error message names the offending key.
    """
    raw = config_path.read_text(encoding="utf-8")
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"style_config must be a JSON object, got {type(data).__name__}"
        )

    for key in _REQUIRED_KEYS:
        if key not in data:
            raise ValueError(f"Missing required key: {key}")

    return data  # type: ignore[return-value]


def compile_style(
    style_config_path: Path,
    output_css_path: Path,
) -> None:
    """Read, validate, and compile a style config file to CSS.

    Reads ``style_config_path``, validates required top-level keys, generates
    CSS custom properties, and writes the result to ``output_css_path``.

    When invoked as the CLI entry-point (``__main__``), this function is
    called after argument validation.  Direct callers receive exceptions
    rather than ``SystemExit`` — callers that need exit-code behaviour should
    wrap accordingly.

    Raises:
        SystemExit(1): on JSON parse error, missing required keys, or I/O
            failure.
        FileNotFoundError / ValueError: propagated to non-CLI callers.
    """
    try:
        config = parse_style_config(style_config_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # BUG-AUDIT-71 / BC-6.14 / REQ-STYLE-FONT-LOADER-1: prepend a single
    # @import line to load every allowlist-matched Google Fonts family
    # named in the typography section. When none are named (all system
    # fonts), the import statement is empty and the compiled CSS is
    # byte-identical to the pre-BUG-AUDIT-71 output for that input.
    families = extract_font_families(config)
    import_line = generate_font_import_statement(families)
    root_block = generate_css_root_block(config)
    css_content = f"{import_line}\n{root_block}" if import_line else root_block

    try:
        output_css_path.parent.mkdir(parents=True, exist_ok=True)
        output_css_path.write_text(css_content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Failed to write output file: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _main() -> None:
    """CLI entry point: style_engine.py <config_path> <output_css_path>."""
    # sys.argv[0] is the script name; we need exactly 2 positional arguments.
    args = sys.argv[1:]
    if len(args) != 2:
        print(
            "Usage: style_engine.py <style_config_path> <output_css_path>",
            file=sys.stderr,
        )
        sys.exit(3)

    style_config_path = Path(args[0])
    output_css_path = Path(args[1])
    compile_style(style_config_path, output_css_path)


if __name__ == "__main__":
    _main()
