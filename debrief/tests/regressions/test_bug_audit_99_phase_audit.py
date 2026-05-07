# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-99.

Bug: phase advancement is consultant-driven with no audit. Approved slides
could exist while ``debrief_state.phase`` stayed at ``"discovery"``;
downstream commands (``/debrief:view``, ``/debrief:export``, the rewriter)
branched on stale state and produced wrong answers. Pre-fix, ``debrief
doctor`` had no mode that detected this drift.

Fix (BC-3.16 amendment + BC-5.25):

- ``debrief doctor --phase-audit`` mode that detects three drift signals:
  approved-slides-but-phase-discovery, style-locked-but-phase-discovery,
  production-but-stuck-at-group-planning. Each detection includes a
  copy-pasteable recovery CLI command in the JSON ``notes`` field.
- ``## Doctor Discipline`` section in ``agents/consultant.md`` that
  prescribes routine ``doctor`` invocation at four transition points
  (session start, after slide-maker returns, before read-state commands,
  before phase transitions) and documents the surface-then-apply
  recovery loop.

Tests assert: (a) ``--phase-audit`` is registered in argparse; (b) drift
detection fires for each of the three signals; (c) clean state returns
no drift; (d) audit notes contain copy-pasteable recovery commands;
(e) consultant card has the ``## Doctor Discipline`` section with all
four prescribed run-points and all four audit-mode flags named.

The tests must pass from both the workspace and the delivered repo.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_TESTS_DIR = _HERE.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_3").is_dir()


# Sibling-discovery sys.path setup matching BUG-AUDIT-93/98 pattern.
for _u in ("unit_3", "unit_2", "unit_1"):
    _stub = _PROJECT_ROOT / "src" / _u
    if _stub.is_dir() and str(_stub) not in sys.path:
        sys.path.insert(0, str(_stub))
# Delivered layout fallback
_delivered = _PROJECT_ROOT / "src" / "debrief"
if _delivered.is_dir() and str(_delivered) not in sys.path:
    sys.path.insert(0, str(_delivered))

try:
    launcher = importlib.import_module("launcher")
except ModuleNotFoundError:  # pragma: no cover
    launcher = importlib.import_module("debrief.launcher")

import debrief_state  # noqa: E402


def _consultant_md_path() -> Path:
    """Locate consultant.md in either layout."""
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    delivered = _PROJECT_ROOT / "agents" / "consultant.md"
    if workspace.exists():
        return workspace
    if delivered.exists():
        return delivered
    raise FileNotFoundError(
        "consultant.md not found in workspace or delivered layout"
    )


# ---------------------------------------------------------------------------
# Helpers — synthesize state files for each drift case.
# ---------------------------------------------------------------------------


def _make_slide(slug: str, status: str = "approved") -> debrief_state.SlideRecord:
    return debrief_state.SlideRecord(
        slug=slug,
        title=slug.replace("-", " ").title(),
        status=status,
        backup=False,
        content_summary=None,
        visual_approach=None,
        design_choices=None,
        forks_not_taken=None,
        user_recommendations=None,
        qa_passed=(status == "approved"),
        accepted_violations=[],
        last_modified="2026-05-07T00:00:00+00:00",
        group_id=None,
        user_assets=[],
        has_math=False,
    )


def _seed_project(
    project_root: Path,
    *,
    phase: str,
    sub_phase: str,
    style_locked: bool,
    slides: list[debrief_state.SlideRecord],
) -> None:
    """Write deck_state.json + debrief_state.json with the requested values."""
    project_root.mkdir(parents=True, exist_ok=True)
    deck = debrief_state.DeckState(
        project_name="phase_audit_test",
        created_at="2026-05-07T00:00:00+00:00",
        archetype="lab_meeting",
        style_locked=style_locked,
        closing_slide=None,
        slides=slides,
        presentations=[],
    )
    debrief_state.write_deck_state(project_root, deck)
    ds = debrief_state.DebriefState(
        phase=phase,
        sub_phase=sub_phase,
        active_agent="consultant",
        archetype="lab_meeting",
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
        session_started_at="2026-05-07T00:00:00+00:00",
        state_hash="x",
    )
    debrief_state.write_debrief_state(project_root, ds)


# ---------------------------------------------------------------------------
# Argparse registration test.
# ---------------------------------------------------------------------------


class TestBugAudit99ArgparseRegistration:
    """``--phase-audit`` is registered in the doctor subcommand's argparse."""

    def test_phase_audit_flag_in_doctor_help(self) -> None:
        # Trigger the doctor subcommand's argparse via subprocess so
        # we exercise the actual dispatch path.
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in sys.path if p and Path(p).is_dir()
        )
        import subprocess
        if _is_workspace_layout():
            argv = [sys.executable, "-m", "launcher", "doctor", "--help"]
        else:
            argv = [sys.executable, "-m", "debrief.launcher", "doctor", "--help"]
        result = subprocess.run(
            argv, capture_output=True, text=True, env=env, timeout=15
        )
        assert "--phase-audit" in result.stdout, (
            f"`--phase-audit` flag missing from doctor --help output. "
            f"stdout={result.stdout!r}"
        )


# ---------------------------------------------------------------------------
# `_audit_phase` unit tests covering the three drift signals + clean case.
# ---------------------------------------------------------------------------


class TestBugAudit99AuditPhaseDriftDetection:
    """`_audit_phase` detects each of the three drift signals."""

    def test_primary_signal_approved_slides_but_phase_discovery(
        self, tmp_path: Path
    ) -> None:
        _seed_project(
            tmp_path,
            phase="discovery",
            sub_phase="discovery/dialog",
            style_locked=False,
            slides=[_make_slide("intro", status="approved")],
        )
        report = launcher._audit_phase(tmp_path)
        assert report["drift"] is True
        assert report["approved_slide_count"] == 1
        assert report["phase"] == "discovery"
        # The note must reference the recovery CLI command.
        notes_joined = " ".join(report["notes"])
        assert "python -m debrief.debrief_state update" in notes_joined
        assert "sub_phase=production/slide_review" in notes_joined

    def test_style_locked_signal(self, tmp_path: Path) -> None:
        _seed_project(
            tmp_path,
            phase="discovery",
            sub_phase="discovery/dialog",
            style_locked=True,
            slides=[],
        )
        report = launcher._audit_phase(tmp_path)
        assert report["drift"] is True
        assert report["style_locked"] is True
        notes_joined = " ".join(report["notes"])
        assert "style_locked is True" in notes_joined
        assert "sub_phase=style/style_lock" in notes_joined

    def test_production_stuck_at_group_planning_signal(
        self, tmp_path: Path
    ) -> None:
        _seed_project(
            tmp_path,
            phase="production",
            sub_phase="production/group_planning",
            style_locked=True,
            slides=[_make_slide("intro", status="approved")],
        )
        report = launcher._audit_phase(tmp_path)
        assert report["drift"] is True
        notes_joined = " ".join(report["notes"])
        assert "production/group_planning" in notes_joined
        assert "sub_phase=production/slide_review" in notes_joined

    def test_clean_state_no_drift(self, tmp_path: Path) -> None:
        _seed_project(
            tmp_path,
            phase="production",
            sub_phase="production/slide_review",
            style_locked=True,
            slides=[_make_slide("intro", status="approved")],
        )
        report = launcher._audit_phase(tmp_path)
        assert report["drift"] is False
        assert report["notes"] == []

    def test_clean_state_during_discovery(self, tmp_path: Path) -> None:
        # During discovery with no approved slides and style not locked,
        # phase=='discovery' is correct, not drift.
        _seed_project(
            tmp_path,
            phase="discovery",
            sub_phase="discovery/dialog",
            style_locked=False,
            slides=[],
        )
        report = launcher._audit_phase(tmp_path)
        assert report["drift"] is False
        assert report["notes"] == []

    def test_draft_slides_during_discovery_no_drift(self, tmp_path: Path) -> None:
        # Draft slides during discovery shouldn't fire the primary signal —
        # only approved slides indicate the user has moved past discovery.
        _seed_project(
            tmp_path,
            phase="discovery",
            sub_phase="discovery/dialog",
            style_locked=False,
            slides=[_make_slide("intro", status="draft")],
        )
        report = launcher._audit_phase(tmp_path)
        assert report["drift"] is False


# ---------------------------------------------------------------------------
# Integration: main_doctor with --phase-audit flag.
# ---------------------------------------------------------------------------


class TestBugAudit99MainDoctorIntegration:
    """`main_doctor(..., phase_audit=True)` surfaces phase drift via exit 1."""

    def test_main_doctor_exit_1_on_phase_drift(self, tmp_path: Path) -> None:
        _seed_project(
            tmp_path,
            phase="discovery",
            sub_phase="discovery/dialog",
            style_locked=False,
            slides=[_make_slide("intro", status="approved")],
        )
        # Add slides/intro.html so the slide-state drift report doesn't fire
        # — we want to isolate the phase-audit drift signal here.
        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        (slides_dir / "intro.html").write_text("<html></html>")

        with pytest.raises(SystemExit) as excinfo:
            launcher.main_doctor(tmp_path, phase_audit=True)
        assert excinfo.value.code == 1, (
            f"Expected exit 1 on phase drift; got {excinfo.value.code}"
        )

    def test_main_doctor_exit_0_on_clean_phase(self, tmp_path: Path) -> None:
        _seed_project(
            tmp_path,
            phase="production",
            sub_phase="production/slide_review",
            style_locked=True,
            slides=[_make_slide("intro", status="approved")],
        )
        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        (slides_dir / "intro.html").write_text("<html></html>")

        with pytest.raises(SystemExit) as excinfo:
            launcher.main_doctor(tmp_path, phase_audit=True)
        assert excinfo.value.code == 0


# ---------------------------------------------------------------------------
# Consultant card: `## Doctor Discipline` section presence + content.
# ---------------------------------------------------------------------------


class TestBugAudit99ConsultantCardDiscipline:
    """`agents/consultant.md` has the `## Doctor Discipline` section per BC-5.25."""

    @pytest.fixture(scope="class")
    def card_text(self) -> str:
        return _consultant_md_path().read_text()

    def test_doctor_discipline_section_header_present(self, card_text: str) -> None:
        assert "## Doctor Discipline" in card_text, (
            "BC-5.25: agents/consultant.md must contain a `## Doctor Discipline` section."
        )

    def test_section_references_bug_audit_99(self, card_text: str) -> None:
        # The section header line should reference BUG-AUDIT-99 / BC-5.25
        # for traceability.
        # Find the section and check for either reference within ~5 lines.
        lines = card_text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("## Doctor Discipline"):
                window = "\n".join(lines[i : i + 3])
                assert "BUG-AUDIT-99" in window or "BC-5.25" in window, (
                    f"Section header should cite BUG-AUDIT-99 or BC-5.25: {window!r}"
                )
                return
        pytest.fail("Doctor Discipline section not found")

    def test_canonical_invocation_lists_all_four_modes(
        self, card_text: str
    ) -> None:
        # The canonical doctor invocation must name all four mode flags.
        assert "--reconstruct" in card_text
        assert "--brief-audit" in card_text
        assert "--asset-audit" in card_text
        assert "--phase-audit" in card_text, (
            "BC-5.25: Doctor Discipline section must name `--phase-audit`."
        )

    def test_section_lists_four_prescribed_run_points(
        self, card_text: str
    ) -> None:
        # Extract the Doctor Discipline section body up to the next ## heading.
        lines = card_text.splitlines()
        body_lines: list[str] = []
        in_section = False
        for line in lines:
            if line.startswith("## Doctor Discipline"):
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if in_section:
                body_lines.append(line)
        body = "\n".join(body_lines)
        body_lower = body.lower()

        # Each of the four prescribed run-points must be mentioned.
        assert "session start" in body_lower, (
            "BC-5.25: must prescribe doctor at session start."
        )
        assert "slide-maker" in body_lower, (
            "BC-5.25: must prescribe doctor after slide-maker dispatch."
        )
        assert "/debrief:view" in body or "view" in body_lower, (
            "BC-5.25: must prescribe doctor before /debrief:view."
        )
        assert "phase transition" in body_lower or "phase transitions" in body_lower, (
            "BC-5.25: must prescribe doctor before phase transitions."
        )

    def test_section_documents_recovery_loop(self, card_text: str) -> None:
        # The recovery loop's surface-then-apply discipline must be documented.
        # Anchor on the literal "surface" and "before applying" / "before the fix"
        # phrasing.
        lines = card_text.splitlines()
        body_lines: list[str] = []
        in_section = False
        for line in lines:
            if line.startswith("## Doctor Discipline"):
                in_section = True
                continue
            if in_section and line.startswith("## "):
                break
            if in_section:
                body_lines.append(line)
        body = "\n".join(body_lines).lower()

        assert "surface" in body, (
            "BC-5.25: recovery loop must document surfacing the drift before applying."
        )
        # The loop must mention re-running doctor after the fix.
        assert "re-run" in body or "rerun" in body, (
            "BC-5.25: recovery loop must document re-running doctor after the fix."
        )
        # And mention the JSON `notes` field as the source of recovery commands.
        assert "notes" in body, (
            "BC-5.25: recovery loop must reference the audit's `notes` field "
            "as the source of recovery CLI commands."
        )
