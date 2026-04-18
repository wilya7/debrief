# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-65 — /debrief:present always includes backup.

BUG-ST-a-e3-present (MEDIUM, UX): /debrief:present hardcoded non-backup
only. A presenter doing Q&A cannot navigate to a backup slide because
it isn't in the running presentation.html. Switching to another tool
at the podium is unacceptable.

REQ-PRESENT-BACKUP-1 / BC-11.18:

- main_present + build_presentation_html include every approved slide
  (main + backup) in output/presentation.html.
- When the deck has at least one main AND at least one backup slide, a
  blank separator slide (background color only) is inserted between
  them.
- No CLI flag; no consultant prompt — backup inclusion is unconditional.

Coverage:

1. Backup slides appear in presentation.html after main slides.
2. Blank separator slide is inserted between main and backup when both exist.
3. Separator uses the locked background color from style_config.json.
4. When there are NO backup slides, no separator is inserted.
5. When there are NO main slides (backup-only), the function returns None
   (main_present exits 2).
6. Progressive-disclosure builds are still injected for main slides
   (not for backup slides).
7. Total slide count in the HTML matches main + builds + (separator?) + backup.
"""

from __future__ import annotations

import json
import re
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def _init_project(
    project_root: Path,
    main_slugs: list[str],
    backup_slugs: list[str],
    bg_color: str = "#123456",
    builds: dict[str, int] | None = None,
) -> None:
    (project_root / ".debrief").mkdir(parents=True, exist_ok=True)
    (project_root / "slides").mkdir(parents=True, exist_ok=True)
    (project_root / "assets").mkdir(parents=True, exist_ok=True)

    # Slide HTML files
    for slug in main_slugs + backup_slugs:
        (project_root / "slides" / f"{slug}.html").write_text(
            f"<!doctype html><html><body><h1>{slug}</h1></body></html>",
            encoding="utf-8",
        )
    # Build files (only for main slides; backup shouldn't have any)
    if builds:
        for slug, count in builds.items():
            for i in range(1, count + 1):
                (project_root / "slides" / f"{slug}_build_{i}.html").write_text(
                    f"<!doctype html><html><body><h1>{slug} build {i}</h1></body></html>",
                    encoding="utf-8",
                )

    # style_config.json with a known background color so we can assert the
    # separator uses it.
    (project_root / "style_config.json").write_text(
        json.dumps({"colors": {"background": bg_color}}),
        encoding="utf-8",
    )

    deck = debrief_state.DeckState(
        project_name="demo",
        created_at="2026-04-18T00:00:00+00:00",
        archetype="conference_talk",
        style_locked=True,
        closing_slide=None,
        slides=[_make_slide(s) for s in main_slugs]
        + [_make_slide(s, backup=True) for s in backup_slugs],
        presentations=[],
    )
    debrief_state.write_deck_state(project_root, deck)


# ---------------------------------------------------------------------------
# 1. Backup slides appear in the HTML
# ---------------------------------------------------------------------------


def test_backup_slides_appear_in_presentation_html(tmp_path):
    """REQ-PRESENT-BACKUP-1: backup slides must be present in
    output/presentation.html alongside main slides."""
    _init_project(
        tmp_path,
        main_slugs=["hook", "body"],
        backup_slugs=["qa1", "qa2"],
    )
    out = utility_skills.build_presentation_html(tmp_path)
    assert out is not None and out.is_file()
    html = out.read_text(encoding="utf-8")
    for slug in ("hook", "body", "qa1", "qa2"):
        assert f"<h1>{slug}</h1>" in html, (
            f"{slug} missing from presentation.html (BUG-AUDIT-65 regression)"
        )


# ---------------------------------------------------------------------------
# 2. Blank separator between main and backup
# ---------------------------------------------------------------------------


def test_blank_separator_inserted_between_main_and_backup(tmp_path):
    """BC-11.18: when both main and backup exist, a blank separator slide
    must sit between them in the sequence."""
    _init_project(
        tmp_path,
        main_slugs=["a", "b"],
        backup_slugs=["qa"],
        bg_color="#abcdef",
    )
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")

    # Find positions of slide markers in document order.
    pos_a = html.find("<h1>a</h1>")
    pos_b = html.find("<h1>b</h1>")
    pos_qa = html.find("<h1>qa</h1>")
    pos_sep = html.find("slide-separator-inner")

    assert pos_a != -1 and pos_b != -1 and pos_qa != -1 and pos_sep != -1, (
        "one or more expected markers missing"
    )
    assert pos_a < pos_b < pos_sep < pos_qa, (
        f"ordering wrong: a={pos_a} b={pos_b} sep={pos_sep} qa={pos_qa}"
    )


def test_separator_uses_locked_background_color(tmp_path):
    """BC-11.18: the separator's background color comes from
    style_config.json.colors.background."""
    _init_project(
        tmp_path,
        main_slugs=["hook"],
        backup_slugs=["qa"],
        bg_color="#abcdef",
    )
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    # Separator div carries the background inline, sourced from style_config.
    assert "background:#abcdef" in html.lower() or "background: #abcdef" in html.lower()


def test_separator_has_no_text_content(tmp_path):
    """BC-11.18: separator is just background — no text, heading, or imagery.
    The specific class 'slide-separator-inner' marks the synthetic slide."""
    _init_project(
        tmp_path,
        main_slugs=["hook"],
        backup_slugs=["qa"],
        bg_color="#ffffff",
    )
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    # Extract the separator slide block by matching the inner class marker.
    sep_match = re.search(
        r'<div class="slide"[^>]*>\s*<div class="slide-separator-inner"[^>]*>\s*</div>\s*</div>',
        html,
    )
    assert sep_match is not None, (
        f"separator slide missing or has unexpected content; HTML: {html[:500]}"
    )


# ---------------------------------------------------------------------------
# 3. No separator when there are no backup slides
# ---------------------------------------------------------------------------


def test_no_separator_when_no_backup_slides(tmp_path):
    _init_project(
        tmp_path,
        main_slugs=["hook", "body"],
        backup_slugs=[],
    )
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    assert "slide-separator-inner" not in html, (
        "No separator should be present when there are no backup slides."
    )


# ---------------------------------------------------------------------------
# 4. Backup-only deck returns None
# ---------------------------------------------------------------------------


def test_backup_only_deck_returns_none(tmp_path):
    """A deck with no approved main slides must return None — you can't
    present backups alone. (main_present exits 2 in this case.)"""
    _init_project(
        tmp_path,
        main_slugs=[],
        backup_slugs=["qa1"],
    )
    # Need an approved slide for write_deck_state to accept the state;
    # actually our _init_project already creates the deck_state.json,
    # so just verify the behavior.
    result = utility_skills.build_presentation_html(tmp_path)
    assert result is None


# ---------------------------------------------------------------------------
# 5. Progressive-disclosure builds on main slides, not on backup
# ---------------------------------------------------------------------------


def test_main_slides_get_builds_backup_does_not(tmp_path):
    """Main slides expand their builds; backup slides do not."""
    _init_project(
        tmp_path,
        main_slugs=["progressive", "plain"],
        backup_slugs=["qa"],
        builds={"progressive": 2, "qa": 2},  # qa builds exist on disk but shouldn't be used
    )
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")

    # Main progressive builds should appear
    assert "<h1>progressive build 1</h1>" in html
    assert "<h1>progressive build 2</h1>" in html
    assert "<h1>progressive</h1>" in html
    # Backup build files must NOT be injected (BC-11.18: backup slides are terminal)
    assert "<h1>qa build 1</h1>" not in html
    assert "<h1>qa build 2</h1>" not in html
    # Backup's final slide IS included
    assert "<h1>qa</h1>" in html


# ---------------------------------------------------------------------------
# 6. Slide counter reflects full sequence including separator + backup
# ---------------------------------------------------------------------------


def test_slide_counter_reflects_full_sequence(tmp_path):
    """The final '1 / N' counter in the HTML matches main + builds +
    separator + backup total."""
    _init_project(
        tmp_path,
        main_slugs=["a", "b"],
        backup_slugs=["qa1", "qa2"],
    )
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    # 2 main + 1 separator + 2 backup = 5
    assert "1 / 5" in html, (
        f"expected slide counter '1 / 5'; got counter context: "
        f"{html[html.find('slide-counter'):html.find('slide-counter')+200]}"
    )


def test_slide_counter_no_backup(tmp_path):
    """2 main + no backup = 2 slides, no separator."""
    _init_project(
        tmp_path,
        main_slugs=["a", "b"],
        backup_slugs=[],
    )
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    assert "1 / 2" in html
