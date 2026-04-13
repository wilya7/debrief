# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Shim for ``python -m debrief.preview_renderer``.

Re-exports the preview renderer from ``slide_maker`` and provides the
``__main__`` entry point:

    python -m debrief.preview_renderer --project-root <path>
        --input-dir <dir> --output-dir <dir>
"""
from __future__ import annotations

from slide_maker import main_preview_renderer, render_html_to_png  # noqa: F401

if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Debrief preview renderer")
    parser.add_argument("--project-root", required=True, help="Project root path")
    parser.add_argument("--input-dir", required=True, help="Input HTML directory")
    parser.add_argument("--output-dir", required=True, help="Output PNG directory")
    args = parser.parse_args()

    main_preview_renderer(
        project_root=Path(args.project_root),
        input_dir=Path(args.input_dir),
        output_dir=Path(args.output_dir),
    )
