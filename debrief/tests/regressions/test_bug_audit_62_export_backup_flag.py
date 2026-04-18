# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-62 — export --include-backup flag.

BUG-ST-a-e1 (MEDIUM): `/debrief:export` PDF included backup slides at
end, while `/debrief:present` and `/debrief:view` (default) excluded
them. Cross-command inconsistency.

REQ-EXPORT-BACKUP-1 / BC-10.3a: `main_export` accepts `--include-backup`
CLI flag. Default behavior (flag absent) excludes backup slides. Passing
the flag restores backup-at-end ordering.

Coverage:

1. `build_page_list(state, project_root)` default excludes backup slides.
2. `build_page_list(..., include_backup=True)` includes backup at end.
3. `main_export` signature accepts `include_backup` kwarg with default False.
4. The CLI help output documents `--include-backup`.
5. Pages are emitted in canonical order (main before backup) when
   include_backup=True.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_10").is_dir()


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_10" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import export  # noqa: E402
import debrief_state  # noqa: E402


def _make_slide(slug: str, backup: bool = False) -> debrief_state.SlideRecord:
    return debrief_state.SlideRecord(
        slug=slug,
        title=slug,
        status="approved",
        backup=backup,
        content_summary=None,
        visual_approach=None,
        design_choices=None,
        forks_not_taken=None,
        user_recommendations=None,
        qa_passed=True,
        accepted_violations=[],
        last_modified="2026-04-18T00:00:00+00:00",
        group_id=None,
        user_assets=[],
        has_math=False,
    )


def _make_deck(main_slugs: list[str], backup_slugs: list[str]) -> debrief_state.DeckState:
    return debrief_state.DeckState(
        project_name="demo",
        created_at="2026-04-18T00:00:00+00:00",
        archetype="conference_talk",
        style_locked=True,
        closing_slide=None,
        slides=[_make_slide(s) for s in main_slugs]
        + [_make_slide(s, backup=True) for s in backup_slugs],
        presentations=[],
    )


# ---------------------------------------------------------------------------
# 1. Default excludes backup
# ---------------------------------------------------------------------------


def test_build_page_list_default_excludes_backup(tmp_path):
    """BUG-AUDIT-62 / BUG-ST-a-e1 / REQ-EXPORT-BACKUP-1:
    Default behavior must exclude backup slides, matching /debrief:present
    and /debrief:view default behavior."""
    state = _make_deck(
        main_slugs=["hook", "body", "close"],
        backup_slugs=["qa1", "qa2"],
    )
    pages = export.build_page_list(state, tmp_path)
    slugs = [p["path"].stem for p in pages if p["type"] == "slide"]
    assert "hook" in slugs
    assert "body" in slugs
    assert "close" in slugs
    assert "qa1" not in slugs
    assert "qa2" not in slugs
    assert all(not p.get("backup", False) for p in pages)


# ---------------------------------------------------------------------------
# 2. include_backup=True includes backup at end
# ---------------------------------------------------------------------------


def test_build_page_list_include_backup_appends_backup(tmp_path):
    """BC-10.3a: when include_backup is True, backup slides are appended
    after main + closing + separator."""
    state = _make_deck(
        main_slugs=["hook", "body"],
        backup_slugs=["qa1"],
    )
    pages = export.build_page_list(state, tmp_path, include_backup=True)
    slugs = [p["path"].stem for p in pages if p["type"] == "slide"]
    assert slugs == ["hook", "body", "qa1"], (
        f"Expected main-then-backup order; got {slugs}"
    )
    # Last page must be the backup slide
    assert pages[-1].get("backup") is True


# ---------------------------------------------------------------------------
# 3. main_export signature accepts include_backup kwarg, default False
# ---------------------------------------------------------------------------


def test_main_export_accepts_include_backup_kwarg():
    sig = inspect.signature(export.main_export)
    assert "include_backup" in sig.parameters, (
        "main_export must accept include_backup kwarg (BUG-AUDIT-62)."
    )
    default = sig.parameters["include_backup"].default
    assert default is False, (
        f"main_export include_backup default must be False; got {default!r}"
    )


# ---------------------------------------------------------------------------
# 4. CLI help documents --include-backup
# ---------------------------------------------------------------------------


def test_cli_help_documents_include_backup():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "export" if _is_workspace_layout() else "debrief.export",
            "--help",
        ],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT / "src" / ("unit_10" if _is_workspace_layout() else "")),
    )
    assert result.returncode == 0
    assert "--include-backup" in result.stdout, (
        "export --help must advertise the --include-backup flag "
        "(BUG-AUDIT-62 / REQ-EXPORT-BACKUP-1)."
    )


# ---------------------------------------------------------------------------
# 5. Canonical ordering with include_backup=True (main before backup)
# ---------------------------------------------------------------------------


def test_canonical_ordering_when_backup_included(tmp_path):
    state = _make_deck(
        main_slugs=["a", "b", "c"],
        backup_slugs=["x", "y"],
    )
    pages = export.build_page_list(state, tmp_path, include_backup=True)
    positions = {p["path"].stem: i for i, p in enumerate(pages) if p["type"] == "slide"}
    assert positions["a"] < positions["x"]
    assert positions["b"] < positions["x"]
    assert positions["c"] < positions["x"]
    assert positions["x"] < positions["y"]


# ---------------------------------------------------------------------------
# 6. No-approved-slides still returns empty (regression guard)
# ---------------------------------------------------------------------------


def test_no_approved_slides_returns_empty(tmp_path):
    """Regression guard — empty deck still returns empty page list."""
    state = debrief_state.DeckState(
        project_name="demo",
        created_at="2026-04-18T00:00:00+00:00",
        archetype="conference_talk",
        style_locked=True,
        closing_slide=None,
        slides=[],
        presentations=[],
    )
    assert export.build_page_list(state, tmp_path) == []
    assert export.build_page_list(state, tmp_path, include_backup=True) == []
