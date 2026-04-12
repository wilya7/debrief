# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Shim for ``python -m debrief.prepare``.

Re-exports context-assembly helpers from ``routing`` and provides the
``__main__`` entry point:

    python -m debrief.prepare --action <id> --project-root <path>
"""
from __future__ import annotations

from routing import (  # noqa: F401
    assemble_task_prompt,
    consume_gate_data,
    main_prepare,
    substitute_gate_placeholders,
)

if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Debrief task prompt assembler")
    parser.add_argument("--action", required=True, help="Action / gate ID")
    parser.add_argument("--project-root", required=True, help="Project root path")
    args = parser.parse_args()

    main_prepare(action=args.action, project_root=Path(args.project_root))
