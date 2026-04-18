# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-60 Cluster 4 (ledger path divergence).

BUG-ST-c-3 / BUG-ST-xp-3 (MEDIUM): two `append_ledger_entry` functions
coexisted — `debrief_state.py` wrote to `project_root/ledger.jsonl` (the
canonical path per spec §3 + BC-11.10 + project_claude.md), while
`ledger.py` wrote to `project_root/.debrief/ledger.jsonl`. Audit trail
fragmented across two files.

Fix: `ledger.py`'s `append_ledger_entry` and `compact_ledger` now both
target the project root (BC-5.4 updated).

Coverage (BC-5.4 revised):

1. `ledger.append_ledger_entry` writes to `project_root / "ledger.jsonl"`.
2. `ledger.append_ledger_entry` does NOT write to `.debrief/ledger.jsonl`.
3. `ledger.compact_ledger` reads the primary ledger from project root.
4. `ledger.compact_ledger` writes archive files to project root.
5. Both `debrief_state.append_ledger_entry` and `ledger.append_ledger_entry`
   write to the same file (single audit trail).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_5").is_dir()


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_5" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import ledger as _ledger_module  # noqa: E402
import debrief_state  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_project(project_root: Path) -> None:
    """Create `.debrief/` so compact_ledger index discovery has somewhere to
    look (it no longer uses `.debrief/`, but ensuring a realistic project
    layout exercises the code path)."""
    (project_root / ".debrief").mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. ledger.append_ledger_entry writes to project root
# ---------------------------------------------------------------------------


def test_ledger_append_writes_to_project_root(tmp_path):
    """BUG-AUDIT-60 / BUG-ST-c-3 / BC-5.4:
    ledger.append_ledger_entry must target project_root/ledger.jsonl.
    """
    _init_project(tmp_path)
    _ledger_module.append_ledger_entry(
        project_root=tmp_path,
        role="system",
        content="test entry",
        event="smoke_test",
    )

    root_ledger = tmp_path / "ledger.jsonl"
    debrief_ledger = tmp_path / ".debrief" / "ledger.jsonl"

    assert root_ledger.exists(), (
        "ledger.append_ledger_entry must create project_root/ledger.jsonl"
    )
    assert not debrief_ledger.exists(), (
        f"ledger.append_ledger_entry must NOT write to {debrief_ledger} "
        "(that was the pre-fix behavior). Audit trail fragmented."
    )

    lines = root_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["role"] == "system"
    assert entry["content"] == "test entry"
    assert entry["metadata"]["event"] == "smoke_test"


def test_ledger_append_and_debrief_state_append_share_file(tmp_path):
    """Both append paths must write to the same ledger file.
    Otherwise two audit trails diverge (the exact BUG-ST-c-3 symptom).
    """
    _init_project(tmp_path)

    _ledger_module.append_ledger_entry(
        project_root=tmp_path,
        role="user",
        content="line-1 via unit_5",
        event="evt1",
    )
    debrief_state.append_ledger_entry(
        project_root=tmp_path, event="evt2", detail="line-2 via unit_2",
    )

    root_ledger = tmp_path / "ledger.jsonl"
    assert root_ledger.exists()
    lines = root_ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2, (
        f"Expected 2 entries in the single canonical ledger; got {len(lines)}"
    )
    assert not (tmp_path / ".debrief" / "ledger.jsonl").exists()


# ---------------------------------------------------------------------------
# 2. ledger.compact_ledger uses project root
# ---------------------------------------------------------------------------


def test_compact_ledger_reads_and_writes_project_root(tmp_path):
    """BC-5.4 / BC-5.6: compaction reads the primary ledger at project root
    and writes archive files alongside it at project root. Validates both
    the input source and the archive destination.
    """
    _init_project(tmp_path)
    # Seed a primary ledger with a couple of entries
    for i in range(3):
        _ledger_module.append_ledger_entry(
            project_root=tmp_path,
            role="system",
            content=f"entry-{i}",
            event="smoke_test",
        )

    _ledger_module.compact_ledger(tmp_path)

    archive = tmp_path / "ledger_compact_001.jsonl"
    primary = tmp_path / "ledger.jsonl"
    assert archive.exists(), (
        "compact_ledger must write ledger_compact_001.jsonl at project root"
    )
    assert primary.exists(), "primary ledger must be rewritten, not deleted"

    # Archive contains the 3 original entries.
    archived_lines = archive.read_text(encoding="utf-8").strip().splitlines()
    assert len(archived_lines) == 3

    # Primary now holds exactly the compaction summary.
    summary_lines = primary.read_text(encoding="utf-8").strip().splitlines()
    assert len(summary_lines) == 1
    summary = json.loads(summary_lines[0])
    assert summary["metadata"]["event"] == "compaction"
    assert summary["metadata"]["archived_count"] == 3
    assert summary["metadata"]["archived_file"] == "ledger_compact_001.jsonl"

    # Confirm NO ledger or archive landed in .debrief/
    assert not (tmp_path / ".debrief" / "ledger.jsonl").exists()
    assert not (tmp_path / ".debrief" / "ledger_compact_001.jsonl").exists()


def test_compact_ledger_monotonic_archive_naming(tmp_path):
    """BC-5.6: successive compactions increment the archive counter."""
    _init_project(tmp_path)

    # Pre-seed an existing archive
    (tmp_path / "ledger_compact_001.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "ledger.jsonl").write_text(
        json.dumps({"timestamp": "t", "role": "system", "content": "e",
                    "metadata": {"event": None}}) + "\n",
        encoding="utf-8",
    )

    _ledger_module.compact_ledger(tmp_path)
    assert (tmp_path / "ledger_compact_002.jsonl").exists(), (
        "next archive must be _002 when _001 already exists"
    )
