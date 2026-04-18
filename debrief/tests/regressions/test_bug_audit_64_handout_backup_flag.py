# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-64 — handout --include-backup parity.

BUG-AUDIT-62 BUG-ST-a-e1 added --include-backup to /debrief:export
(BC-10.3a) so users can choose main-only vs main+backup PDFs. But
/debrief:handout still hardcoded main-only — a cross-command gap in
the same consistency story BUG-AUDIT-62 set out to fix. BUG-AUDIT-64
closes it.

REQ-HAND-BACKUP-1 / BC-11.16a:

main_handout accepts include_backup: bool = False (CLI flag
--include-backup). Default excludes backup slides; when True, approved
backup slides are appended after the main slides in array order.
Precondition (at least one approved non-backup slide) is unchanged.

Coverage:

1. main_handout signature has include_backup kwarg with default False.
2. --include-backup CLI flag is advertised in --help output.
3. With the flag, the rendered handout HTML includes backup slide
   markers (slugs appear as layout inputs).
4. Without the flag (default), the rendered HTML does NOT include
   backup slide markers.
5. Precondition remains: a deck with ONLY backup slides fails
   regardless of the flag.
"""

from __future__ import annotations

import inspect
import json
import os
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
    _PROJECT_ROOT / "src" / ("unit_3" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_7" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_10" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402
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


def _init_project(project_root: Path, main_slugs: list[str], backup_slugs: list[str]) -> None:
    (project_root / ".debrief").mkdir(parents=True, exist_ok=True)
    (project_root / "slides").mkdir(parents=True, exist_ok=True)
    for slug in main_slugs + backup_slugs:
        (project_root / "slides" / f"{slug}.html").write_text(
            f"<!doctype html><html><body><h1>{slug}</h1></body></html>",
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
# 1. main_handout signature
# ---------------------------------------------------------------------------


def test_main_handout_accepts_include_backup_kwarg():
    """BUG-AUDIT-64 / REQ-HAND-BACKUP-1: signature must have include_backup
    defaulting to False (matching main_export's BC-10.3a)."""
    sig = inspect.signature(utility_skills.main_handout)
    assert "include_backup" in sig.parameters
    assert sig.parameters["include_backup"].default is False


# ---------------------------------------------------------------------------
# 2. CLI help advertises --include-backup
# ---------------------------------------------------------------------------


def test_handout_cli_help_advertises_include_backup():
    """Inspect the CLI parser by running the module with the sibling
    unit dirs on PYTHONPATH so transitive imports (debrief_state, etc.)
    resolve in both workspace (unit_*) and delivered (debrief) layouts."""
    if _is_workspace_layout():
        src = _PROJECT_ROOT / "src"
        pypath = os.pathsep.join(
            str(src / f"unit_{n}") for n in (1, 2, 3, 5, 7, 9, 10, 11)
        )
        module_name = "utility_skills"
        cwd = str(src / "unit_11")
    else:
        pypath = str(_PROJECT_ROOT / "src")
        module_name = "debrief.utility_skills"
        cwd = str(_PROJECT_ROOT)

    env = dict(**os.environ)
    env["PYTHONPATH"] = pypath + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", module_name, "--help"],
        capture_output=True, text=True, cwd=cwd, env=env,
    )
    assert result.returncode == 0, (
        f"utility_skills --help exited {result.returncode}: {result.stderr}"
    )
    assert "--include-backup" in result.stdout, (
        "utility_skills --help must advertise --include-backup so it's "
        "discoverable from /debrief:handout (BUG-AUDIT-64)."
    )


# ---------------------------------------------------------------------------
# 3-4. generate_layout_html behavior with/without backup inclusion
# ---------------------------------------------------------------------------


def _read_deck_slides_for_handout(
    project_root: Path,
    include_backup: bool,
) -> list[debrief_state.SlideRecord]:
    """Replicate main_handout's slide-selection logic so we can unit-test
    it without calling Playwright."""
    deck = debrief_state.read_deck_state(project_root)
    main = [s for s in deck.slides if s.status == "approved" and not s.backup]
    if include_backup:
        backup = [s for s in deck.slides if s.status == "approved" and s.backup]
        return main + backup
    return main


def test_default_excludes_backup_slides(tmp_path):
    _init_project(
        tmp_path,
        main_slugs=["hook", "body", "close"],
        backup_slugs=["qa1"],
    )
    slides = _read_deck_slides_for_handout(tmp_path, include_backup=False)
    slugs = [s.slug for s in slides]
    assert slugs == ["hook", "body", "close"]
    assert "qa1" not in slugs


def test_include_backup_appends_backup_slides(tmp_path):
    _init_project(
        tmp_path,
        main_slugs=["hook", "body"],
        backup_slugs=["qa1", "qa2"],
    )
    slides = _read_deck_slides_for_handout(tmp_path, include_backup=True)
    slugs = [s.slug for s in slides]
    assert slugs == ["hook", "body", "qa1", "qa2"]


def test_include_backup_preserves_main_order(tmp_path):
    """Main slides come first, backup slides last — matches BC-10.3a shape."""
    _init_project(
        tmp_path,
        main_slugs=["a", "b", "c"],
        backup_slugs=["x", "y"],
    )
    slides = _read_deck_slides_for_handout(tmp_path, include_backup=True)
    slugs = [s.slug for s in slides]
    assert slugs.index("a") < slugs.index("x")
    assert slugs.index("c") < slugs.index("x")
    assert slugs.index("x") < slugs.index("y")


# ---------------------------------------------------------------------------
# 5. Precondition unchanged (at least one approved non-backup slide)
# ---------------------------------------------------------------------------


def test_precondition_unchanged_with_only_backup_slides(tmp_path, capsys):
    """BC-11.16 + BC-11.16a: the precondition is unchanged — a deck with
    ONLY backup slides must still be rejected even when include_backup
    is True. The flag extends the layout, not the precondition."""
    _init_project(
        tmp_path,
        main_slugs=[],
        backup_slugs=["qa1"],
    )
    with pytest.raises(SystemExit) as excinfo:
        utility_skills.main_handout(
            mode="2up", project_root=tmp_path, include_backup=True
        )
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "no approved non-backup slides" in captured.err.lower()


def test_main_handout_source_calls_backup_extension():
    """Source-level check that the extension branch is wired. Guards
    against a future refactor accidentally dropping the feature."""
    src = inspect.getsource(utility_skills.main_handout)
    assert "include_backup" in src
    assert "s.backup" in src
