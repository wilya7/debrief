# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Shim for ``python -m debrief.script_generator``.

Re-exports script-generation helpers from ``utility_skills`` and provides
the ``__main__`` entry point:

    python -m debrief.script_generator --project-root <path>
"""
from __future__ import annotations

from utility_skills import (  # noqa: F401
    generate_script_content,
    main_script_generator,
)

if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Debrief script generator")
    parser.add_argument("--project-root", required=True, help="Project root path")
    args = parser.parse_args()

    main_script_generator(project_root=Path(args.project_root))
