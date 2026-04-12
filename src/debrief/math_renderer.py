# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Shim for ``python -m debrief.math_renderer``.

Re-exports math-rendering helpers from ``visual_qa`` and provides the
``__main__`` entry point:

    python -m debrief.math_renderer --mode <inline|display> --input <latex_string>
"""
from __future__ import annotations

from visual_qa import (  # noqa: F401
    escape_html,
    main_math_renderer,
    render_math_html,
    validate_latex,
)

if __name__ == "__main__":
    import argparse
    from pathlib import Path  # noqa: F401

    parser = argparse.ArgumentParser(description="Debrief math renderer")
    parser.add_argument(
        "--mode", required=True, choices=["inline", "display"], help="Render mode"
    )
    parser.add_argument("--input", required=True, help="LaTeX input string")
    args = parser.parse_args()

    main_math_renderer(mode=args.mode, latex_input=args.input)
