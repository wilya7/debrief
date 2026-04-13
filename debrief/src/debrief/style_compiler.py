# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Shim for ``python -m debrief.style_compiler``.

Re-exports all public symbols from ``style_engine`` and provides the
``__main__`` entry point used by the canonical CLI invocation:

    python -m debrief.style_compiler <style_config_path> <output_css_path>
"""
from __future__ import annotations

from style_engine import (  # noqa: F401
    CSS_PROPERTY_MAP,
    compile_style,
    flatten_config,
    generate_css_root_block,
    parse_style_config,
    path_to_css_var,
)

if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if len(args) != 2:
        print(
            "Usage: python -m debrief.style_compiler <style_config_path> <output_css_path>",
            file=sys.stderr,
        )
        sys.exit(3)
    from pathlib import Path

    compile_style(Path(args[0]), Path(args[1]))
