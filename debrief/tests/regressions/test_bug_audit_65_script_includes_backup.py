# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-65 — /debrief:script always includes backup.

BUG-ST-a-e3-script (MEDIUM, UX): /debrief:script hardcoded non-backup.
Speaker notes for backup slides are exactly what a presenter wants for
Q&A rehearsal — the answers they have already prepared.

REQ-SCRIPT-BACKUP-1 / BC-11.6b:

- generate_script_content accepts backup_slides list.
- When non-empty, a "## Backup Slides" section heading is emitted after
  the last main slide, followed by one block per backup slide.
- main_script_generator passes approved backup slides to the generator.
- Precondition (at least one approved main slide) is unchanged.
- Backup slides are NOT counted in TIME CHECK pacing markers.

Coverage:

1. Script contains "## Backup Slides" section header when deck has backups.
2. Script has no "## Backup Slides" header when deck has no backups.
3. Each backup slide gets its own block with Key talking points /
   Transition / Estimated speaking time.
4. Backup slide headers use "(backup)" marker for readability.
5. TIME CHECK pacing markers are computed over MAIN slides only,
   not extended to backups.
6. Precondition unchanged: deck with only backup slides fails to
   generate (no main precondition satisfied).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_11" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_3" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_7" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_10" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402
import debrief_state  # noqa: E402


def _make_slide(slug: str, backup: bool = False, title: str = None, summary: str = None):
    return debrief_state.SlideRecord(
        slug=slug,
        title=title or slug.replace("-", " ").title(),
        status="approved",
        backup=backup,
        content_summary=summary,
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


# ---------------------------------------------------------------------------
# 1-2. "## Backup Slides" section header
# ---------------------------------------------------------------------------


def test_script_contains_backup_section_header_when_backups_exist():
    """REQ-SCRIPT-BACKUP-1 / BC-11.6b: when backup_slides is a non-empty
    list, the script must include a ## Backup Slides heading after the
    main slide blocks."""
    main = [_make_slide("hook"), _make_slide("body")]
    backup = [_make_slide("qa-reliability", backup=True, summary="What about hallucinations?")]
    content = utility_skills.generate_script_content(
        deck_brief_content="",
        slides=main,
        folder="2026_04_18_demo",
        total_duration_minutes=10.0,
        backup_slides=backup,
    )
    assert "## Backup Slides" in content
    # Heading appears AFTER the main content
    assert content.index("## Backup Slides") > content.index("Hook"), (
        "Backup section must follow main slide blocks"
    )


def test_script_omits_backup_section_when_no_backups():
    """No ## Backup Slides heading when backup_slides is empty or None."""
    main = [_make_slide("hook")]
    content = utility_skills.generate_script_content(
        deck_brief_content="",
        slides=main,
        folder="2026_04_18_demo",
        total_duration_minutes=5.0,
        backup_slides=None,
    )
    assert "## Backup Slides" not in content
    content2 = utility_skills.generate_script_content(
        deck_brief_content="",
        slides=main,
        folder="2026_04_18_demo",
        total_duration_minutes=5.0,
        backup_slides=[],
    )
    assert "## Backup Slides" not in content2


# ---------------------------------------------------------------------------
# 3. Each backup slide gets its own block
# ---------------------------------------------------------------------------


def test_each_backup_slide_has_its_own_block():
    main = [_make_slide("hook")]
    backup = [
        _make_slide("qa-reliability", backup=True, summary="Reliability rebuttal."),
        _make_slide("qa-scope", backup=True, summary="Scope rebuttal."),
    ]
    content = utility_skills.generate_script_content(
        deck_brief_content="",
        slides=main,
        folder="2026_04_18_demo",
        backup_slides=backup,
    )
    # Each backup slide has its own Slug, Key talking points, Transition,
    # Estimated speaking time subsections.
    assert content.count("### Key talking points") == 1 + 2  # main (1) + 2 backups
    assert content.count("### Transition") == 1 + 2
    assert content.count("### Estimated speaking time") == 1 + 2
    assert "qa-reliability" in content
    assert "qa-scope" in content
    assert "Reliability rebuttal" in content
    assert "Scope rebuttal" in content


# ---------------------------------------------------------------------------
# 4. Backup slide headers marked with "(backup)"
# ---------------------------------------------------------------------------


def test_backup_slide_headers_marked_backup():
    main = [_make_slide("hook")]
    backup = [_make_slide("qa-one", backup=True)]
    content = utility_skills.generate_script_content(
        deck_brief_content="",
        slides=main,
        folder="2026_04_18_demo",
        backup_slides=backup,
    )
    # Backup slide header should say something like "## Slide 2 (backup): Qa One"
    assert "(backup)" in content, (
        "Backup slide headers must be visually distinguishable "
        "(e.g., '(backup)' marker). Current output: "
        f"{content[content.find('Backup Slides'):]}"
    )


# ---------------------------------------------------------------------------
# 5. TIME CHECK markers apply to main slides only
# ---------------------------------------------------------------------------


def test_time_check_markers_count_main_slides_only():
    """BC-11.6b: pacing checkpoints are for the main talk. Backup slides
    are for Q&A and are explicitly not timed. total_duration_minutes /
    n uses the MAIN slide count, not main+backup."""
    main = [_make_slide(f"m{i}") for i in range(8)]  # 8 main slides
    backup = [_make_slide(f"qa{i}", backup=True) for i in range(4)]  # 4 backup
    content = utility_skills.generate_script_content(
        deck_brief_content="",
        slides=main,
        folder="2026_04_18_demo",
        total_duration_minutes=40.0,
        backup_slides=backup,
    )
    # Per-main-slide time = 40 / 8 = 5.0 minutes
    assert "~5.0 minutes" in content
    # Per-slide time should NOT be 40/(8+4) = ~3.3 minutes
    assert "~3.3 minutes" not in content
    # 3 TIME CHECK markers (25/50/75%) on main slides only
    assert content.count("TIME CHECK") == 3


def test_time_check_not_inside_backup_section():
    """TIME CHECK markers must sit inside the main slide blocks, never
    inside the Backup Slides section."""
    main = [_make_slide(f"m{i}") for i in range(4)]
    backup = [_make_slide("qa", backup=True)]
    content = utility_skills.generate_script_content(
        deck_brief_content="",
        slides=main,
        folder="2026_04_18_demo",
        total_duration_minutes=20.0,
        backup_slides=backup,
    )
    backup_section_start = content.index("## Backup Slides")
    # Every TIME CHECK occurs before the backup section
    for match in content.split("TIME CHECK")[1:]:  # skip before-first
        # We know TIME CHECK tokens exist; assert none appear after the header.
        pass
    # Structural assertion: no "TIME CHECK" after the backup header.
    assert "TIME CHECK" not in content[backup_section_start:], (
        "TIME CHECK markers must not appear in the Backup Slides section."
    )


# ---------------------------------------------------------------------------
# 6. Precondition unchanged (at least one main slide required)
# ---------------------------------------------------------------------------


def test_precondition_unchanged_with_only_backup_slides(tmp_path, capsys):
    """BC-11.16 equivalent: a deck with ONLY backup slides must still
    fail to generate a script. The main-slide precondition is
    unchanged by BUG-AUDIT-65."""
    (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)
    (tmp_path / "slides").mkdir(parents=True, exist_ok=True)
    (tmp_path / "deck_brief.md").write_text(
        "**Duration:** 10 minutes\n", encoding="utf-8"
    )
    # Create a presentation record so the `presentations` precondition passes.
    pres = debrief_state.PresentationRecord(
        folder="2026_04_18_demo",
        created_at="2026-04-18",
        slide_manifest=[],
        export_count=0,
        script_count=0,
        handout_count=0,
        separator_position=None,
        separator_content=None,
    )
    deck = debrief_state.DeckState(
        project_name="demo",
        created_at="2026-04-18T00:00:00+00:00",
        archetype="conference_talk",
        style_locked=True,
        closing_slide=None,
        slides=[_make_slide("qa-only", backup=True)],
        presentations=[pres],
    )
    debrief_state.write_deck_state(tmp_path, deck)

    with pytest.raises(SystemExit) as excinfo:
        utility_skills.main_script_generator(tmp_path)
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "no approved non-backup slides" in captured.err.lower()
