# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Shim for ``python -m debrief.handout``.

Re-exports handout helpers from ``utility_skills`` and provides the
``__main__`` entry point:

    python -m debrief.handout --mode <2up|4up> --project-root <path>
"""
from __future__ import annotations

from utility_skills import generate_layout_html, main_handout  # noqa: F401

if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Debrief handout generator")
    parser.add_argument(
        "--mode", required=True, choices=["2up", "4up"], help="Layout mode"
    )
    parser.add_argument("--project-root", required=True, help="Project root path")
    args = parser.parse_args()

    main_handout(mode=args.mode, project_root=Path(args.project_root))
