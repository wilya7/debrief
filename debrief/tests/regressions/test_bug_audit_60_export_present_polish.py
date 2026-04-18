# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-60 Clusters 5 + 6.

Cluster 5 — Export/presentation desync:
  BUG-ST-xp-1 (MEDIUM): presentation.html stale after re-export.
  BUG-ST-xp-2 (LOW):    slide_manifest frozen at first export.

Cluster 6 — Minor polish:
  BUG-ST-a-1 (LOW): slide-maker agent card has conflicting "PASS" guidance.
  BUG-ST-c-4 (LOW): check_limit --help omits default value.

These bugs share low complexity and target three files
(utility_skills.py, export.py, qa_checker.py CLI) + one agent card.

Coverage:

1. `build_presentation_html` writes a valid `output/presentation.html`
   when a project is initialized with approved slides.
2. `build_presentation_html` returns None (no exit) when preconditions
   are not met — export.py's post-write call is safe on empty decks.
3. `check_limit --help` output contains the text `Default: 5`.
4. `slide-maker.md` no longer contains the permissive PASS/FAIL phrasing
   in the final-action instruction; BUG-ST-14 directive is preserved.
"""

from __future__ import annotations

import subprocess
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
    _PROJECT_ROOT / "src" / ("unit_9" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_10" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_3" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_7" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402
import debrief_state  # noqa: E402


def _slide_maker_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "slide-maker.md"
    return _PROJECT_ROOT / "agents" / "slide-maker.md"


# ---------------------------------------------------------------------------
# Cluster 5 — build_presentation_html
# ---------------------------------------------------------------------------


def _init_minimal_project_with_slide(project_root: Path) -> None:
    """Create a deck_state.json with one approved non-backup slide and a
    matching slides/<slug>.html file so build_presentation_html has
    something to assemble.
    """
    (project_root / ".debrief").mkdir(parents=True, exist_ok=True)
    (project_root / "slides").mkdir(parents=True, exist_ok=True)
    (project_root / "assets").mkdir(parents=True, exist_ok=True)

    slug = "demo"
    (project_root / "slides" / f"{slug}.html").write_text(
        "<!doctype html><html><head></head>"
        "<body><div class='slide'><h1>Demo</h1></div></body></html>",
        encoding="utf-8",
    )

    # Minimal deck_state.json with one approved slide
    slide = debrief_state.SlideRecord(
        slug=slug,
        title="Demo",
        status="approved",
        backup=False,
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
    deck = debrief_state.DeckState(
        project_name="demo",
        created_at="2026-04-18T00:00:00+00:00",
        archetype="conference_talk",
        style_locked=True,
        closing_slide=None,
        slides=[slide],
        presentations=[],
    )
    debrief_state.write_deck_state(project_root, deck)

    # Minimal debrief_state.json so downstream readers don't trip
    db_state = debrief_state.DebriefState(
        phase="production",
        sub_phase="production/slide_review",
        active_agent="consultant",
        archetype="conference_talk",
        current_group_id=None,
        current_slide_slug=None,
        pending_gate=None,
        last_gate_response=None,
        red_green_started_at=None,
        group_slide_index=0,
        group_slide_count=0,
        backup_mode=False,
        completed_groups=[],
        pre_view_state=None,
        view_deferred=False,
        closing_slide_pending=False,
        group_revise_slug=None,
        style_import_mode=None,
        reference_provided=False,
        reference_modality=None,
        papers_provided=False,
        selected_figures=None,
        session_started_at="2026-04-18T00:00:00+00:00",
        state_hash="",
    )
    debrief_state.write_debrief_state(project_root, db_state)


def test_build_presentation_html_writes_file_without_browser(tmp_path):
    """BUG-AUDIT-60 / BUG-ST-xp-1 (refresh-from-export flow) +
    BUG-AUDIT-67 / BC-11.18a (srcdoc iframe embedding):
    build_presentation_html must write output/presentation.html and
    return its path — without launching a browser. Each file-backed
    slide is embedded as a srcdoc iframe so per-slide CSS survives."""
    _init_minimal_project_with_slide(tmp_path)

    out_path = utility_skills.build_presentation_html(tmp_path)

    assert out_path is not None
    assert out_path == tmp_path / "output" / "presentation.html"
    assert out_path.is_file()

    html = out_path.read_text(encoding="utf-8")
    # BUG-AUDIT-67: file-backed slides are embedded via <iframe srcdoc=...>.
    # Content is inline (srcdoc carries verbatim HTML), not a URL reference,
    # so presentation.html remains self-contained.
    assert "<iframe" in html
    assert "srcdoc=" in html
    # Slide content still reachable (srcdoc preserves < and > literal;
    # the standalone slide body included <h1>Demo</h1>).
    assert "Demo" in html
    # Counter markup present
    assert "slide-counter" in html
    assert "1 / 1" in html
    # Keyboard nav JS present
    assert "ArrowRight" in html
    assert "fullscreenElement" in html


def test_build_presentation_html_returns_none_when_no_project(tmp_path):
    """No deck_state.json → return None, no exit."""
    result = utility_skills.build_presentation_html(tmp_path)
    assert result is None


def test_build_presentation_html_returns_none_when_no_approved_slides(tmp_path):
    """Project exists but no approved slides → return None, no exit."""
    (tmp_path / ".debrief").mkdir(parents=True, exist_ok=True)
    deck = debrief_state.DeckState(
        project_name="empty",
        created_at="2026-04-18T00:00:00+00:00",
        archetype="conference_talk",
        style_locked=True,
        closing_slide=None,
        slides=[],
        presentations=[],
    )
    debrief_state.write_deck_state(tmp_path, deck)

    result = utility_skills.build_presentation_html(tmp_path)
    assert result is None


def test_main_present_still_works(tmp_path, monkeypatch):
    """main_present must still write the file. Browser-open is stubbed."""
    _init_minimal_project_with_slide(tmp_path)
    monkeypatch.setattr(utility_skills.webbrowser, "open", lambda *a, **k: True)

    utility_skills.main_present(tmp_path)
    assert (tmp_path / "output" / "presentation.html").is_file()


# ---------------------------------------------------------------------------
# Cluster 6 — check_limit --help discloses default
# ---------------------------------------------------------------------------


def test_check_limit_help_discloses_default():
    """BUG-ST-c-4: --help for check_limit must mention the default value."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "qa_checker" if _is_workspace_layout() else "debrief.qa_checker",
            "check_limit",
            "--help",
        ],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT_ROOT / "src" / ("unit_9" if _is_workspace_layout() else "")),
    )
    assert result.returncode == 0, f"help exited {result.returncode}: {result.stderr}"
    assert "Default: 5" in result.stdout or "default: 5" in result.stdout, (
        f"help output missing default disclosure; stdout was:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Cluster 6 — slide-maker agent card: no permissive PASS/FAIL phrasing
# ---------------------------------------------------------------------------


def test_slide_maker_final_action_bans_pass_verdict():
    """BUG-ST-a-1: the final-action instruction must explicitly forbid
    'Tier 1 PASSED' verdicts and must not carry the old permissive
    'Include the Tier 1 result summary (PASS/FAIL...)' phrasing.
    """
    md = _slide_maker_md_path().read_text(encoding="utf-8")
    # Pre-fix conflict: the `(PASS/FAIL` parenthetical legitimized verdict
    # text. After the fix that phrasing must be gone.
    assert "(PASS/FAIL" not in md, (
        "slide-maker.md still contains the permissive '(PASS/FAIL' "
        "phrasing that conflicted with BUG-ST-14 / BUG-ST-a-1."
    )
    assert "Do NOT state" in md or "Do NOT claim" in md, (
        "slide-maker.md must explicitly prohibit declaring a Tier 1 verdict."
    )


def test_slide_maker_bug_st_14_reference_preserved():
    """The BUG-ST-14 reference (original prohibition) must still be in
    the agent card; the fix strengthens it, not removes it."""
    md = _slide_maker_md_path().read_text(encoding="utf-8")
    assert "BUG-ST-14" in md
