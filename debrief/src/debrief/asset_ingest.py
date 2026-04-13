# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Shim for ``python -m debrief.asset_ingest``.

Re-exports image-ingestion helpers from ``visual_qa`` and provides the
``__main__`` entry point:

    python -m debrief.asset_ingest --src <path> --slug <slug>
        --project-root <path>
"""
from __future__ import annotations

from visual_qa import ingest_image, main_asset_ingest  # noqa: F401

if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Debrief asset ingest")
    parser.add_argument("--src", required=True, help="Source image path")
    parser.add_argument("--slug", required=True, help="Slide slug for naming")
    parser.add_argument("--project-root", required=True, help="Project root path")
    args = parser.parse_args()

    main_asset_ingest(
        src=Path(args.src),
        slug=args.slug,
        project_root=Path(args.project_root),
    )
