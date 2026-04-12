# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Shim for ``python -m debrief.style_analyzer``.

Re-exports style-analysis helpers from ``slide_maker`` and provides the
``__main__`` entry point:

    python -m debrief.style_analyzer --reference <path> --project-root <path>
"""
from __future__ import annotations

from slide_maker import (  # noqa: F401
    adapt_html_dir,
    adapt_html_file,
    adapt_pdf,
    adapt_pptx,
    main_style_analyzer,
    sample_slides,
)

if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Debrief style analyzer")
    parser.add_argument("--reference", required=True, help="Reference file path")
    parser.add_argument("--project-root", required=True, help="Project root path")
    args = parser.parse_args()

    main_style_analyzer(
        reference=Path(args.reference), project_root=Path(args.project_root)
    )
