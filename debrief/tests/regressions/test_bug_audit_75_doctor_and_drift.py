# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-75.

BUG-AUDIT-75 adds a filesystem/state drift reconciler (``debrief
doctor``) and attaches three consultant obligations: on-session-start
drift audit, post-compaction re-audit, and slide-record write-through
(the SlideRecord is written in the same turn as GREEN QA, never
batched).

TEST CLASSES:

1. TestDetectSlideStateDrift — pure-function drift detection across
   every branch of the drift grid (clean / orphan-files /
   orphan-records / bidirectional / missing-state / missing-dir /
   malformed state).
2. TestReconstructSlideRecords — minimal-record shape + defaults +
   idempotence + no-op when slugs=[].
3. TestMainDoctorCli — main_doctor exit codes (0 clean, 1 drift
   report-only, 0 after --reconstruct, 2 on reconstruction failure)
   and JSON-on-stdout shape.
4. TestConsultantDriftAuditSection — consultant.md carries the
   ## State Drift Audit section + the slide-record write-through
   Responsibilities bullet + cross-references to BUG-AUDIT-75.
5. TestSpecAndBlueprintAnchors — spec + blueprint carry the new
   anchors (BUG-AUDIT-75, REQ-DOCTOR-1, BC-3.16, BC-5.17).

All tests run unconditionally in both workspace and delivered layouts
via the sibling-discovery path pattern; zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-75 and
blueprint contracts BC-3.16 / BC-5.17.
"""

from __future__ import annotations

import json
import sys
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
    return (_PROJECT_ROOT / "src" / "unit_3").is_dir()


def _launcher_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_3"
    return _PROJECT_ROOT / "src" / "debrief"


def _debrief_state_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_2"
    return _PROJECT_ROOT / "src" / "debrief"


def _consultant_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    return _PROJECT_ROOT / "agents" / "consultant.md"


def _spec_path() -> Path:
    return _PROJECT_ROOT / "spec" / "stakeholder_spec.md"


def _blueprint_path() -> Path:
    return _PROJECT_ROOT / "blueprint" / "blueprint_contracts.md"


for _dir in (_debrief_state_module_dir(), _launcher_module_dir()):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import launcher  # noqa: E402
from launcher import (  # noqa: E402
    DriftReport,
    detect_slide_state_drift,
    main_doctor,
    reconstruct_slide_records_from_files,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_state_with_slugs(project_root: Path, slugs: list[str]) -> None:
    slides = [
        {
            "slug": s,
            "title": f"Title of {s}",
            "status": "approved",
            "backup": False,
            "content_summary": None,
            "visual_approach": None,
            "design_choices": None,
            "forks_not_taken": None,
            "user_recommendations": None,
            "qa_passed": True,
            "accepted_violations": [],
            "last_modified": "2026-04-20T00:00:00Z",
            "group_id": None,
            "user_assets": [],
            "has_math": False,
        }
        for s in slugs
    ]
    data = {
        "project_name": "drift_test",
        "created_at": "2026-04-20T00:00:00Z",
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": slides,
        "presentations": [],
    }
    (project_root / "deck_state.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


def _make_slide_files(project_root: Path, slugs: list[str]) -> None:
    slides_dir = project_root / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    for s in slugs:
        (slides_dir / f"{s}.html").write_text(
            "<html><body></body></html>", encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Test class 1: detect_slide_state_drift
# ---------------------------------------------------------------------------


class TestDetectSlideStateDrift:
    def test_clean_project_no_drift(self, tmp_path: Path) -> None:
        _write_state_with_slugs(tmp_path, ["intro", "body", "closing"])
        _make_slide_files(tmp_path, ["intro", "body", "closing"])
        report = detect_slide_state_drift(tmp_path)
        assert report.drift_detected is False
        assert report.orphan_files == []
        assert report.orphan_records == []
        assert report.matched_count == 3

    def test_orphan_files_reported(self, tmp_path: Path) -> None:
        _write_state_with_slugs(tmp_path, [])
        _make_slide_files(tmp_path, ["alpha", "beta"])
        report = detect_slide_state_drift(tmp_path)
        assert report.drift_detected is True
        assert report.orphan_files == ["alpha", "beta"]
        assert report.orphan_records == []
        assert report.matched_count == 0

    def test_orphan_records_reported(self, tmp_path: Path) -> None:
        _write_state_with_slugs(tmp_path, ["missing_slide"])
        # No slide files.
        report = detect_slide_state_drift(tmp_path)
        assert report.drift_detected is True
        assert report.orphan_files == []
        assert report.orphan_records == ["missing_slide"]
        assert report.matched_count == 0

    def test_bidirectional_drift(self, tmp_path: Path) -> None:
        _write_state_with_slugs(tmp_path, ["intro", "missing"])
        _make_slide_files(tmp_path, ["intro", "orphan"])
        report = detect_slide_state_drift(tmp_path)
        assert report.drift_detected is True
        assert report.orphan_files == ["orphan"]
        assert report.orphan_records == ["missing"]
        assert report.matched_count == 1

    def test_missing_state_file_treats_as_zero_records(
        self, tmp_path: Path
    ) -> None:
        _make_slide_files(tmp_path, ["alpha"])
        # No deck_state.json at all.
        report = detect_slide_state_drift(tmp_path)
        assert report.drift_detected is True
        assert report.orphan_files == ["alpha"]
        assert report.orphan_records == []

    def test_missing_slides_dir_treats_as_zero_files(
        self, tmp_path: Path
    ) -> None:
        _write_state_with_slugs(tmp_path, ["intro"])
        # No slides/ dir.
        report = detect_slide_state_drift(tmp_path)
        assert report.drift_detected is True
        assert report.orphan_files == []
        assert report.orphan_records == ["intro"]

    def test_malformed_state_treated_as_empty_gracefully(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "deck_state.json").write_text(
            "not valid json", encoding="utf-8"
        )
        _make_slide_files(tmp_path, ["alpha"])
        # Must not raise; treat malformed state as zero slides.
        report = detect_slide_state_drift(tmp_path)
        assert report.orphan_files == ["alpha"]

    def test_orphan_files_sorted_stable(self, tmp_path: Path) -> None:
        _write_state_with_slugs(tmp_path, [])
        _make_slide_files(tmp_path, ["charlie", "alpha", "bravo"])
        report = detect_slide_state_drift(tmp_path)
        assert report.orphan_files == ["alpha", "bravo", "charlie"]

    def test_returns_drift_report_dataclass(
        self, tmp_path: Path
    ) -> None:
        _write_state_with_slugs(tmp_path, [])
        report = detect_slide_state_drift(tmp_path)
        assert isinstance(report, DriftReport)


# ---------------------------------------------------------------------------
# Test class 2: reconstruct_slide_records_from_files
# ---------------------------------------------------------------------------


class TestReconstructSlideRecords:
    def test_writes_minimal_record_per_slug(self, tmp_path: Path) -> None:
        _write_state_with_slugs(tmp_path, [])
        written = reconstruct_slide_records_from_files(
            tmp_path, ["alpha", "beta"]
        )
        assert written == 2
        raw = (tmp_path / "deck_state.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        slugs = [s["slug"] for s in data["slides"]]
        assert set(slugs) == {"alpha", "beta"}

    def test_record_defaults_match_contract(
        self, tmp_path: Path
    ) -> None:
        _write_state_with_slugs(tmp_path, [])
        reconstruct_slide_records_from_files(tmp_path, ["intro"])
        data = json.loads(
            (tmp_path / "deck_state.json").read_text(encoding="utf-8")
        )
        rec = data["slides"][0]
        assert rec["slug"] == "intro"
        assert rec["title"] == "intro"
        assert rec["status"] == "draft"
        assert rec["backup"] is False
        assert rec["qa_passed"] is False
        assert rec["accepted_violations"] == []
        assert rec["group_id"] is None
        assert rec["user_assets"] == []
        assert rec["has_math"] is False
        assert rec["content_summary"] is None
        # last_modified is a non-empty ISO-ish string.
        assert isinstance(rec["last_modified"], str)
        assert len(rec["last_modified"]) >= 10

    def test_idempotent_on_existing_slug(self, tmp_path: Path) -> None:
        _write_state_with_slugs(tmp_path, ["already_present"])
        written = reconstruct_slide_records_from_files(
            tmp_path, ["already_present", "new_one"]
        )
        assert written == 1
        data = json.loads(
            (tmp_path / "deck_state.json").read_text(encoding="utf-8")
        )
        slugs = [s["slug"] for s in data["slides"]]
        assert slugs.count("already_present") == 1
        assert "new_one" in slugs

    def test_empty_slugs_is_noop(self, tmp_path: Path) -> None:
        _write_state_with_slugs(tmp_path, ["existing"])
        written = reconstruct_slide_records_from_files(tmp_path, [])
        assert written == 0
        data = json.loads(
            (tmp_path / "deck_state.json").read_text(encoding="utf-8")
        )
        slugs = [s["slug"] for s in data["slides"]]
        assert slugs == ["existing"]


# ---------------------------------------------------------------------------
# Test class 3: main_doctor CLI
# ---------------------------------------------------------------------------


class TestMainDoctorCli:
    def test_clean_project_exits_0(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_state_with_slugs(tmp_path, ["alpha"])
        _make_slide_files(tmp_path, ["alpha"])
        with pytest.raises(SystemExit) as ei:
            main_doctor(tmp_path)
        assert ei.value.code == 0
        out = capsys.readouterr()
        data = json.loads(out.out)
        assert data["drift_detected"] is False
        assert data["matched_count"] == 1

    def test_drift_report_only_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_state_with_slugs(tmp_path, [])
        _make_slide_files(tmp_path, ["alpha", "beta"])
        with pytest.raises(SystemExit) as ei:
            main_doctor(tmp_path)
        assert ei.value.code == 1
        out = capsys.readouterr()
        data = json.loads(out.out)
        assert data["drift_detected"] is True
        assert data["orphan_files"] == ["alpha", "beta"]
        # Human-readable summary on stderr directs at --reconstruct.
        assert "--reconstruct" in out.err

    def test_reconstruct_fixes_drift_exits_0(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_state_with_slugs(tmp_path, [])
        _make_slide_files(tmp_path, ["alpha", "beta"])
        with pytest.raises(SystemExit) as ei:
            main_doctor(tmp_path, reconstruct=True)
        assert ei.value.code == 0
        data = json.loads(capsys.readouterr().out)
        assert data["drift_detected"] is False
        # State now carries both records.
        state = json.loads(
            (tmp_path / "deck_state.json").read_text(encoding="utf-8")
        )
        slugs = {s["slug"] for s in state["slides"]}
        assert slugs == {"alpha", "beta"}

    def test_reconstruction_failure_exits_2(
        self, tmp_path: Path
    ) -> None:
        _write_state_with_slugs(tmp_path, [])
        _make_slide_files(tmp_path, ["alpha"])
        # Force reconstruction to raise.
        with patch.object(
            launcher,
            "reconstruct_slide_records_from_files",
            side_effect=RuntimeError("simulated failure"),
        ):
            with pytest.raises(SystemExit) as ei:
                main_doctor(tmp_path, reconstruct=True)
        assert ei.value.code == 2

    def test_stdout_is_pretty_printed_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_state_with_slugs(tmp_path, ["alpha"])
        _make_slide_files(tmp_path, ["alpha"])
        with pytest.raises(SystemExit):
            main_doctor(tmp_path)
        out = capsys.readouterr().out
        # Indented pretty-print — contains at least one newline between
        # braces.
        assert "{\n" in out


# ---------------------------------------------------------------------------
# Test class 4: consultant.md carries the drift-audit section and the
# slide-record write-through obligation
# ---------------------------------------------------------------------------


class TestConsultantDriftAuditSection:
    def test_state_drift_audit_section_exists(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "## State Drift Audit" in text

    def test_section_references_bug_audit_75(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-75" in text
        assert "REQ-DOCTOR-1" in text
        assert "BC-3.16" in text

    def test_section_references_doctor_invocation(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "python -m debrief.launcher doctor" in text

    def test_section_appears_before_deck_brief_maintenance(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        drift_pos = text.index("## State Drift Audit")
        brief_pos = text.index("## Deck Brief Maintenance")
        assert drift_pos < brief_pos

    def test_responsibilities_carries_slide_record_write_through(
        self,
    ) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "Slide-record write-through" in text
        assert "BC-5.17" in text


# ---------------------------------------------------------------------------
# Test class 5: spec + blueprint anchors
# ---------------------------------------------------------------------------


class TestSpecAndBlueprintAnchors:
    def test_spec_has_bug_audit_75(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-75" in text

    def test_spec_has_req_doctor_1(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "REQ-DOCTOR-1" in text

    def test_spec_has_req_consult_slide_wt_1(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "REQ-CONSULT-SLIDE-WT-1" in text

    def test_blueprint_has_bc_3_16(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        assert "BC-3.16" in text

    def test_blueprint_has_bc_5_17(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        assert "BC-5.17" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
