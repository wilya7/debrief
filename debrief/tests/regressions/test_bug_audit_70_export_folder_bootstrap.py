# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-70.

BUG-AUDIT-70 closes the routing-surgery aftermath in /debrief:export:

1. `commands/export.md` no longer references deleted routing functions
   (`routing.propose_presentation_folder_name`, "yields to routing",
   the G4.1-G4.4 dialog, or BC-4.7c's prepare-time injection).

2. First-export auto-bootstrap folder name is computed by a new
   deterministic helper `debrief_state.compute_presentation_folder_name`
   that detects when `project_name` already begins with a YYYYMMDD /
   YYYY_MM_DD / YYYY-MM-DD date prefix, and in that case uses the
   embedded date instead of prepending today's date. This eliminates
   the double-date failure mode (`2026_04_19_20260420_lab_meeting`).

TEST CLASSES:

1. TestComputePresentationFolderName — pure-function behavior.
2. TestExportBootstrapIntegration — end-to-end via main_export's
   self-bootstrap path, mocked Playwright.
3. TestExportDocRegression — `commands/export.md` has no references
   to the deleted routing symbols.

All tests run unconditionally in both workspace and delivered layouts
via the sibling-discovery path pattern established in
`test_bug_audit_21_handout_robustness.py`; zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-70 and
blueprint contracts BC-4.7c (amended) and BC-10.9 (rewritten).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_2").is_dir()


def _debrief_state_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_2"
    return _PROJECT_ROOT / "src" / "debrief"


def _export_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_10"
    return _PROJECT_ROOT / "src" / "debrief"


def _style_engine_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_6"
    return _PROJECT_ROOT / "src" / "debrief"


def _export_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "commands" / "export.md"
    return _PROJECT_ROOT / "commands" / "export.md"


for _dir in (
    _debrief_state_module_dir(),
    _export_module_dir(),
    _style_engine_module_dir(),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import debrief_state  # noqa: E402
from debrief_state import compute_presentation_folder_name  # noqa: E402


# ---------------------------------------------------------------------------
# Test class 1: compute_presentation_folder_name pure-function tests
# ---------------------------------------------------------------------------


# Deterministic "today" for all tests. Avoid picking a day that
# coincides with any of the embedded-date fixtures so false-positive
# matches are loud.
_FIXED_TODAY = date(2026, 4, 19)


class TestComputePresentationFolderName:
    def test_yyyymmdd_prefix_is_detected(self) -> None:
        assert (
            compute_presentation_folder_name(
                "20260420_Lab_meeting", today=_FIXED_TODAY
            )
            == "2026_04_20_lab_meeting"
        )

    def test_yyyy_mm_dd_prefix_is_detected(self) -> None:
        assert (
            compute_presentation_folder_name(
                "2026_04_20_lab_meeting", today=_FIXED_TODAY
            )
            == "2026_04_20_lab_meeting"
        )

    def test_yyyy_dash_mm_dash_dd_prefix_is_detected(self) -> None:
        assert (
            compute_presentation_folder_name(
                "2026-04-20_lab_meeting", today=_FIXED_TODAY
            )
            == "2026_04_20_lab_meeting"
        )

    def test_yyyy_dash_mm_dash_dd_with_space_separator(self) -> None:
        assert (
            compute_presentation_folder_name(
                "2026-04-20 Lab Meeting", today=_FIXED_TODAY
            )
            == "2026_04_20_lab_meeting"
        )

    def test_date_only_no_title(self) -> None:
        assert (
            compute_presentation_folder_name(
                "20260420", today=_FIXED_TODAY
            )
            == "2026_04_20_untitled"
        )

    def test_no_date_prefix_prepends_today(self) -> None:
        assert (
            compute_presentation_folder_name(
                "lab_meeting", today=_FIXED_TODAY
            )
            == "2026_04_19_lab_meeting"
        )

    def test_empty_project_name_uses_today_and_untitled(self) -> None:
        assert (
            compute_presentation_folder_name("", today=_FIXED_TODAY)
            == "2026_04_19_untitled"
        )

    def test_bare_year_prefix_is_not_a_date(self) -> None:
        # "2024_annual_report" starts with a four-digit year but no
        # month/day, so it MUST be treated as a plain title.
        result = compute_presentation_folder_name(
            "2024_annual_report", today=_FIXED_TODAY
        )
        assert result.startswith("2026_04_19_")
        # The original string survives sanitization intact (it is
        # already lowercase + underscores + alphanumeric).
        assert result.endswith("2024_annual_report")

    def test_today_defaults_to_date_today(self) -> None:
        # Without the today parameter, the helper uses date.today().
        # We can't assert the exact string without mocking, but we can
        # assert the shape and that the title portion is correct.
        result = compute_presentation_folder_name("lab_meeting")
        # Shape: YYYY_MM_DD_<title>
        parts = result.split("_", 3)
        assert len(parts) == 4
        yyyy, mm, dd, title = parts
        assert yyyy.isdigit() and len(yyyy) == 4
        assert mm.isdigit() and len(mm) == 2
        assert dd.isdigit() and len(dd) == 2
        assert title == "lab_meeting"

    def test_idempotent_on_own_output(self) -> None:
        # The helper's output itself has a YYYY_MM_DD prefix, so
        # running it through the helper again should NOT prepend
        # today's date a second time.
        first = compute_presentation_folder_name(
            "Lab Meeting", today=_FIXED_TODAY
        )
        second = compute_presentation_folder_name(first, today=_FIXED_TODAY)
        assert first == second

    def test_long_title_is_truncated_to_max_40(self) -> None:
        # sanitize_identifier uses max_length=40 for the title part.
        long_suffix = "a" * 200
        result = compute_presentation_folder_name(
            f"20260420_{long_suffix}", today=_FIXED_TODAY
        )
        prefix, title = result[:10], result[11:]
        assert prefix == "2026_04_20"
        assert len(title) == 40

    def test_special_characters_stripped_from_title(self) -> None:
        # Characters outside [a-z0-9_] are stripped by
        # sanitize_identifier. Validate the helper inherits that.
        result = compute_presentation_folder_name(
            "lab!!!meeting@@@2026", today=_FIXED_TODAY
        )
        assert result == "2026_04_19_labmeeting2026"


# ---------------------------------------------------------------------------
# Test class 2: main_export bootstrap integration
# ---------------------------------------------------------------------------


def _write_minimal_deck_state(
    project_root: Path, *, project_name: str, slide_slug: str
) -> None:
    slides = [
        {
            "slug": slide_slug,
            "title": "Title of " + slide_slug,
            "status": "approved",
            "backup": False,
            "content_summary": "Summary.",
            "visual_approach": None,
            "design_choices": None,
            "forks_not_taken": None,
            "user_recommendations": None,
            "qa_passed": True,
            "accepted_violations": [],
            "last_modified": "",
            "group_id": None,
            "user_assets": [],
            "has_math": False,
        }
    ]
    data = {
        "project_name": project_name,
        "created_at": "",
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": slides,
        "presentations": [],
    }
    (project_root / "deck_state.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


def _write_minimal_style_config(project_root: Path) -> None:
    cfg = {
        "colors": {"primary": "#000", "background": "#fff"},
        "typography": {},
        "spacing": {},
        "layout": {"slide_width": "1920px", "slide_height": "1080px"},
        "data_viz": {},
        "constraints": {"permitted_diagram_types": []},
        "provenance": {},
    }
    (project_root / "style_config.json").write_text(
        json.dumps(cfg), encoding="utf-8"
    )
    (project_root / "assets").mkdir(parents=True, exist_ok=True)


class TestExportBootstrapIntegration:
    """End-to-end: main_export self-bootstraps a PresentationRecord
    whose folder name comes from compute_presentation_folder_name.

    main_export performs its function-local imports of
    ``playwright.sync_api.sync_playwright`` and
    ``style_engine.compile_style`` just before calling them. We patch
    both at the module level so the bootstrap runs normally and then
    Playwright explodes — the export writes the export_log entry and
    exits with code 1 after the bootstrap has already persisted the
    folder name. We read the written folder name and assert it came
    from the helper.
    """

    def _run_bootstrap_and_capture_folder(
        self, project_root: Path
    ) -> str:
        import playwright.sync_api as _pw_mod
        import style_engine as _se_mod

        with (
            patch.object(
                _pw_mod,
                "sync_playwright",
                side_effect=RuntimeError(
                    "stopping after bootstrap for test isolation"
                ),
            ),
            patch.object(_se_mod, "compile_style", lambda *a, **kw: None),
        ):
            import export  # type: ignore[import]

            try:
                export.main_export(project_root)
            except SystemExit:
                # main_export catches RuntimeError and exits 1 after
                # writing the export_log entry. Bootstrap has already
                # completed by then.
                pass

        raw = (project_root / "deck_state.json").read_text(encoding="utf-8")
        state = json.loads(raw)
        assert state["presentations"], (
            "bootstrap did not persist a PresentationRecord"
        )
        folder: str = state["presentations"][0]["folder"]
        return folder

    def test_dated_project_name_does_not_double_date(
        self, tmp_path: Path
    ) -> None:
        _write_minimal_deck_state(
            tmp_path,
            project_name="20260420_Lab_meeting",
            slide_slug="intro",
        )
        _write_minimal_style_config(tmp_path)
        (tmp_path / "slides").mkdir(parents=True, exist_ok=True)
        (tmp_path / "slides" / "intro.html").write_text(
            "<!DOCTYPE html><html><body>x</body></html>",
            encoding="utf-8",
        )

        folder = self._run_bootstrap_and_capture_folder(tmp_path)
        # Key assertion: NO double-dating. Embedded 20260420 is used;
        # today's date is NOT prepended.
        assert folder == "2026_04_20_lab_meeting", (
            f"Expected 2026_04_20_lab_meeting (date detected from "
            f"project_name), got {folder!r}"
        )

    def test_bare_title_project_name_gets_today_prepended(
        self, tmp_path: Path
    ) -> None:
        _write_minimal_deck_state(
            tmp_path, project_name="lab_meeting", slide_slug="intro"
        )
        _write_minimal_style_config(tmp_path)
        (tmp_path / "slides").mkdir(parents=True, exist_ok=True)
        (tmp_path / "slides" / "intro.html").write_text(
            "<!DOCTYPE html><html><body>x</body></html>",
            encoding="utf-8",
        )

        folder = self._run_bootstrap_and_capture_folder(tmp_path)
        # Shape: YYYY_MM_DD + "_lab_meeting"
        parts = folder.split("_")
        assert len(parts) >= 5, folder
        yyyy, mm, dd = parts[0], parts[1], parts[2]
        assert yyyy.isdigit() and len(yyyy) == 4, folder
        assert mm.isdigit() and len(mm) == 2, folder
        assert dd.isdigit() and len(dd) == 2, folder
        assert folder.endswith("_lab_meeting"), folder


# ---------------------------------------------------------------------------
# Test class 3: commands/export.md doc regression
# ---------------------------------------------------------------------------


class TestExportDocRegression:
    def test_export_md_has_no_routing_references(self) -> None:
        """The doc MUST NOT reference deleted routing symbols.

        After BUG-AUDIT-31 gutted routing.py, every reference in user-
        facing docs to routing functions or the dead dialog flow is
        stale. This test asserts the sweep is complete.
        """
        text = _export_md_path().read_text(encoding="utf-8")
        # Specific deleted symbols.
        assert "propose_presentation_folder_name" not in text
        # Stale flow claims.
        assert "yields to routing" not in text
        assert "prepare-time injection" not in text
        # The word "routing" may legitimately appear in the historical
        # note ("routing.py was gutted in BUG-AUDIT-31") — we allow it
        # but forbid the specific deleted-symbol references above.

    def test_export_md_references_new_helper(self) -> None:
        text = _export_md_path().read_text(encoding="utf-8")
        assert "compute_presentation_folder_name" in text
        assert "REQ-EXPORT-BOOTSTRAP-1" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
