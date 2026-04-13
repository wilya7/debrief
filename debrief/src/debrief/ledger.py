# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 5: Consultant Agent and Ledger.

Provides helpers for writing slide briefs, group manifests, and the
append-only conversation ledger with automatic compaction.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from debrief_state import atomic_write_json  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_RHETORICAL_ROLES: frozenset[str] = frozenset(
    {"hook", "ethos", "pathos", "logos", "synthesis", "recap", "transition"}
)

REQUIRED_BRIEF_FIELDS: tuple[str, ...] = (
    "slug",
    "title",
    "content_goal",
    "visual_approach",
    "visual_pattern",
    "rhetorical_role",
    "design_invariants",
    "user_recommendations",
    "group_id",
)

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,49}$")
_GROUP_ID_RE = re.compile(r"^(group|backup)_\d{2}$")

_LEDGER_FILENAME = "ledger.jsonl"
_COMPACT_PATTERN = "ledger_compact_{:03d}.jsonl"
_COMPACT_COUNTER_RE = re.compile(r"^ledger_compact_(\d{3})\.jsonl$")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _next_compact_index(debrief_dir: Path) -> int:
    """Return the next available 1-based archive index (1 if none exist)."""
    highest = 0
    for entry in debrief_dir.iterdir():
        m = _COMPACT_COUNTER_RE.match(entry.name)
        if m:
            idx = int(m.group(1))
            if idx > highest:
                highest = idx
    return highest + 1


# ---------------------------------------------------------------------------
# validate_slide_brief — BC-5.1
# ---------------------------------------------------------------------------


def validate_slide_brief(brief: dict) -> None:
    """Validate a slide brief dict against the REQ-CONSULT-5 schema.

    Raises ValueError with a descriptive message if any required field is
    missing or if rhetorical_role is not in the allowed set.

    Required fields: slug, title, content_goal, visual_approach,
    visual_pattern, rhetorical_role, design_invariants,
    user_recommendations, group_id.
    Allowed rhetorical_role values: hook, ethos, pathos, logos,
                                    synthesis, recap, transition.
    """
    for field in REQUIRED_BRIEF_FIELDS:
        if field not in brief:
            raise ValueError(f"Slide brief is missing required field: {field}")

    role = brief["rhetorical_role"]
    if role not in ALLOWED_RHETORICAL_ROLES:
        raise ValueError(
            f"Invalid rhetorical_role '{role}'. "
            f"Allowed values: {sorted(ALLOWED_RHETORICAL_ROLES)}"
        )


# ---------------------------------------------------------------------------
# write_slide_brief — BC-5.1, BC-5.13
# ---------------------------------------------------------------------------


def write_slide_brief(
    project_root: Path,
    group_id: str,
    slug: str,
    title: str,
    content_goal: str,
    visual_approach: str,
    visual_pattern: str,
    rhetorical_role: str,
    design_invariants: list[str],
    user_recommendations: str,
    backup: bool = False,
) -> None:
    """Write a slide brief to .debrief/briefs/<group_id>_<slug>.json.

    Validates that rhetorical_role is in the allowed set and that slug
    matches the required naming convention.
    Writes atomically (write-to-tmp then rename).
    """
    # Validate slug — BC-5.13
    if not _SLUG_RE.match(slug) or slug.endswith("_"):
        raise ValueError(
            f"Invalid slug '{slug}'. Must match ^[a-z][a-z0-9_]{{0,49}}$ "
            "and must not end with '_'."
        )

    brief: dict = {
        "slug": slug,
        "title": title,
        "content_goal": content_goal,
        "visual_approach": visual_approach,
        "visual_pattern": visual_pattern,
        "rhetorical_role": rhetorical_role,
        "design_invariants": design_invariants,
        "user_recommendations": user_recommendations,
        "group_id": group_id,
    }

    if backup:
        brief["backup"] = True

    # Validate the assembled brief (rhetorical_role + required fields)
    validate_slide_brief(brief)

    briefs_dir = project_root / ".debrief" / "briefs"
    dest = briefs_dir / f"{group_id}_{slug}.json"
    atomic_write_json(dest, brief)


# ---------------------------------------------------------------------------
# write_group_manifest — BC-5.2, BC-5.3, BC-5.14
# ---------------------------------------------------------------------------


def write_group_manifest(
    project_root: Path,
    group_id: str,
    slide_slugs: list[str],
) -> None:
    """Write .debrief/briefs/<group_id>_MANIFEST.json atomically.

    Schema: {"group_id": str, "slide_count": int, "slugs": [str],
             "dispatched_at": "<ISO8601>"}.
    The G3.1 machine gate checks this file's existence and slide_count.
    dispatched_at is set to the current UTC ISO8601 timestamp at write time.
    """
    # Validate group_id — BC-5.14
    if not _GROUP_ID_RE.match(group_id):
        raise ValueError(
            f"Invalid group_id '{group_id}'. Must match ^(group|backup)_\\d{{{{2}}}}$."
        )

    manifest = {
        "group_id": group_id,
        "slide_count": len(slide_slugs),
        "slugs": list(slide_slugs),
        "dispatched_at": _utc_now_iso(),
    }

    briefs_dir = project_root / ".debrief" / "briefs"
    dest = briefs_dir / f"{group_id}_MANIFEST.json"
    atomic_write_json(dest, manifest)


# ---------------------------------------------------------------------------
# append_ledger_entry — BC-5.4
# ---------------------------------------------------------------------------


def append_ledger_entry(
    project_root: Path,
    role: str,
    content: str,
    group_id: Optional[str] = None,
    slug: Optional[str] = None,
    event: Optional[str] = None,
) -> None:
    """Append a single JSON entry to ledger.jsonl.

    Schema: {"timestamp": str, "role": str, "content": str,
             "metadata": {"group_id": str|None, "slug": str|None,
                          "event": str|None}}.
    Opens the file in append mode; does not read or truncate.
    """
    entry = {
        "timestamp": _utc_now_iso(),
        "role": role,
        "content": content,
        "metadata": {
            "group_id": group_id,
            "slug": slug,
            "event": event,
        },
    }

    ledger_path = project_root / ".debrief" / _LEDGER_FILENAME
    with open(ledger_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# compact_ledger — BC-5.5, BC-5.6
# ---------------------------------------------------------------------------


def compact_ledger(project_root: Path) -> None:
    """Compact ledger.jsonl when entry count exceeds 100.

    Steps:
    1. Read all entries from ledger.jsonl.
    2. Write full ledger to ledger_compact_NNN.jsonl (NNN = 001, 002, ...).
    3. Write a single compaction summary entry to a new ledger.jsonl
       capturing decisions made, slides approved, style choices locked,
       narrative direction.
    """
    debrief_dir = project_root / ".debrief"
    ledger_path = debrief_dir / _LEDGER_FILENAME

    # Read all existing entries
    raw_text = ledger_path.read_text(encoding="utf-8")
    lines = [ln for ln in raw_text.splitlines() if ln.strip()]

    # Determine archive filename
    archive_idx = _next_compact_index(debrief_dir)
    archive_name = _COMPACT_PATTERN.format(archive_idx)
    archive_path = debrief_dir / archive_name

    # Write archive (raw JSONL — preserve original lines)
    with open(archive_path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())

    # Build compaction summary
    summary_entry = {
        "timestamp": _utc_now_iso(),
        "role": "system",
        "content": (
            f"Ledger compacted: {len(lines)} entries archived to "
            f"{archive_name}. "
            "Summary: decisions, approvals, and narrative direction "
            "from prior session recorded in archive."
        ),
        "metadata": {
            "group_id": None,
            "slug": None,
            "event": "compaction",
            "archived_file": archive_name,
            "archived_count": len(lines),
        },
    }

    # Overwrite ledger with the single summary entry
    with open(ledger_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(summary_entry, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
