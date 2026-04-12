# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Shim for ``python -m debrief.update_state``.

Re-exports state-update helpers from ``routing`` and provides the
``__main__`` entry point:

    python -m debrief.update_state --gate <gate_id> --response <text>
        --project-root <path>
    python -m debrief.update_state --skill-prelude <skill>
        --field <name>=<value> --project-root <path>
"""
from __future__ import annotations

from routing import (  # noqa: F401
    handle_red_green_transition,
    main_update_state,
    merge_approval_payload,
    perform_snapshot,
    promote_style_draft,
    validate_gate_response,
)

if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Debrief state updater")
    parser.add_argument("--gate", help="Gate ID for response validation")
    parser.add_argument("--response", help="Gate response text")
    parser.add_argument("--project-root", required=True, help="Project root path")
    parser.add_argument("--skill-prelude", help="Skill prelude mode skill name")
    parser.add_argument(
        "--field", action="append", dest="fields", help="field=value assignment"
    )
    args = parser.parse_args()

    project_root = Path(args.project_root)

    if args.skill_prelude is not None:
        main_update_state(
            gate_id="",
            response="",
            project_root=project_root,
            skill_prelude=args.skill_prelude,
            field_assignments=args.fields,
        )
    elif args.gate and args.response:
        main_update_state(
            gate_id=args.gate,
            response=args.response,
            project_root=project_root,
        )
    else:
        print(
            "ERROR: Either --gate/--response or --skill-prelude/--field required.",
            file=sys.stderr,
        )
        sys.exit(4)
