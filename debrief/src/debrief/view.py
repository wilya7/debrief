# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Shim for ``python -m debrief.view``.

Re-exports view helpers from ``utility_skills`` and provides the
``__main__`` entry point:

    python -m debrief.view <query> --project-root <path>
"""
from __future__ import annotations

from utility_skills import (  # noqa: F401
    generate_view_html,
    main_view,
    parse_view_query,
)

if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Debrief slide viewer")
    parser.add_argument("query", help="View query (all, <slug>, group:<id>, last, backup)")
    parser.add_argument("--project-root", required=True, help="Project root path")
    args = parser.parse_args()

    main_view(query=args.query, project_root=Path(args.project_root))
