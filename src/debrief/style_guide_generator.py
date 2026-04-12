# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Shim for ``python -m debrief.style_guide_generator``.

Re-exports the style-guide generator from ``slide_maker`` and provides the
``__main__`` entry point:

    python -m debrief.style_guide_generator --project-root <path>
"""
from __future__ import annotations

from slide_maker import main_style_guide_generator  # noqa: F401

if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Debrief style guide generator")
    parser.add_argument("--project-root", required=True, help="Project root path")
    args = parser.parse_args()

    main_style_guide_generator(project_root=Path(args.project_root))
