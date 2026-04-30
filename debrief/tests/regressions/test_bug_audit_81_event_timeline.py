# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-81 — Cycle 2 Phase 3.

Phase 3 ships the ``append_timeline_event`` helper per BC-2.18 and
wires three deterministic code-path emitters: ``export_done`` (in
``main_export``), ``handout_done`` (in ``main_handout``), and
``script_done`` (in ``main_script_generator``). Other event types
(briefing_complete, style_locked, slide_approved, slide_discarded,
paper_attached, figure_selected, backup_session_started) require
either state-machine code or consultant-card amendments; they are
deferred to Phase 4.

TEST CLASSES:

1. TestAppendTimelineEvent — schema correctness, append-only,
   optional turn handling, multi-line accumulation, payload shape
   passthrough.
2. TestExportEmitsExportDone — export.main_export emits
   export_done with the expected payload after a successful PDF
   write.
3. TestHandoutEmitsHandoutDone — utility_skills.main_handout emits
   handout_done with mode + version + slide_count.
4. TestScriptEmitsScriptDone — main_script_generator emits
   script_done with version + slide_count.
5. TestRecallSurfacesTimelineEvents — recall (Phase 1) over a
   timeline that contains BUG-AUDIT-81 emitted entries returns hits.

All tests run unconditionally in both workspace and delivered layouts;
zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-81 and
blueprint contract BC-2.18.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def _export_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_10"
    return _PROJECT_ROOT / "src" / "debrief"


def _utility_skills_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_11"
    return _PROJECT_ROOT / "src" / "debrief"


def _debrief_state_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_2"
    return _PROJECT_ROOT / "src" / "debrief"


def _style_engine_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_6"
    return _PROJECT_ROOT / "src" / "debrief"


for _dir in (
    _launcher_module_dir(),
    _export_module_dir(),
    _utility_skills_module_dir(),
    _debrief_state_module_dir(),
    _style_engine_module_dir(),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import launcher  # noqa: E402
from launcher import (  # noqa: E402
    append_timeline_event,
    read_event_timeline,
    recall,
)


# ---------------------------------------------------------------------------
# Test class 1: append_timeline_event
# ---------------------------------------------------------------------------


class TestAppendTimelineEvent:
    def test_writes_one_jsonl_line(self, tmp_path: Path) -> None:
        append_timeline_event(
            tmp_path,
            event="briefing_complete",
            payload={"phase_to": "style"},
        )
        path = tmp_path / "output" / "timeline.jsonl"
        text = path.read_text(encoding="utf-8")
        # Exactly one non-empty line.
        lines = [ln for ln in text.splitlines() if ln.strip()]
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["event"] == "briefing_complete"
        assert entry["payload"] == {"phase_to": "style"}

    def test_includes_iso8601_timestamp(self, tmp_path: Path) -> None:
        append_timeline_event(
            tmp_path, event="style_locked", payload={}
        )
        entry = read_event_timeline(tmp_path)[0]
        assert "timestamp" in entry
        assert entry["timestamp"].endswith("Z")

    def test_optional_turn_is_recorded_when_present(
        self, tmp_path: Path
    ) -> None:
        append_timeline_event(
            tmp_path,
            event="paper_attached",
            payload={"path": "papers/x.pdf"},
            turn=42,
        )
        entry = read_event_timeline(tmp_path)[0]
        assert entry["turn"] == 42

    def test_optional_turn_is_omitted_when_absent(
        self, tmp_path: Path
    ) -> None:
        append_timeline_event(
            tmp_path, event="style_locked", payload={}
        )
        entry = read_event_timeline(tmp_path)[0]
        assert "turn" not in entry

    def test_appends_accumulate_in_order(self, tmp_path: Path) -> None:
        append_timeline_event(tmp_path, event="briefing_complete", payload={})
        append_timeline_event(tmp_path, event="style_locked", payload={})
        append_timeline_event(tmp_path, event="export_done", payload={})
        entries = read_event_timeline(tmp_path)
        assert [e["event"] for e in entries] == [
            "briefing_complete", "style_locked", "export_done",
        ]

    def test_payload_passes_through_verbatim(self, tmp_path: Path) -> None:
        payload = {
            "slug": "intro",
            "group_id": "g1",
            "qa_passed": True,
            "nested": {"a": 1, "b": [2, 3, 4]},
        }
        append_timeline_event(
            tmp_path, event="slide_approved", payload=payload
        )
        entry = read_event_timeline(tmp_path)[0]
        assert entry["payload"] == payload

    def test_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        # No output/ directory yet.
        assert not (tmp_path / "output").exists()
        append_timeline_event(tmp_path, event="briefing_complete", payload={})
        assert (tmp_path / "output" / "timeline.jsonl").is_file()


# ---------------------------------------------------------------------------
# Test class 2: export_done emission
# ---------------------------------------------------------------------------


class TestExportEmitsExportDone:
    def _seed_minimal_project(self, tmp_path: Path) -> None:
        # Minimal deck_state with one approved non-backup slide.
        slides = [{
            "slug": "intro",
            "title": "Intro",
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
        }]
        data = {
            "project_name": "x",
            "created_at": "",
            "archetype": "lab_meeting",
            "style_locked": True,
            "closing_slide": None,
            "slides": slides,
            "presentations": [],
        }
        (tmp_path / "deck_state.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        # Minimal style_config.
        cfg = {
            "colors": {"primary": "#000", "background": "#fff"},
            "typography": {},
            "spacing": {},
            "layout": {"slide_width": "1920px", "slide_height": "1080px"},
            "data_viz": {},
            "constraints": {"permitted_diagram_types": []},
            "provenance": {},
        }
        (tmp_path / "style_config.json").write_text(
            json.dumps(cfg), encoding="utf-8"
        )
        (tmp_path / "assets").mkdir(parents=True, exist_ok=True)
        (tmp_path / "slides").mkdir(parents=True, exist_ok=True)
        (tmp_path / "slides" / "intro.html").write_text(
            "<!DOCTYPE html><html><body>x</body></html>",
            encoding="utf-8",
        )

    def test_export_emits_export_done(self, tmp_path: Path) -> None:
        self._seed_minimal_project(tmp_path)
        import export  # type: ignore[import]
        import playwright.sync_api as _pw_mod

        # Mock Playwright + fitz + style_engine.compile_style.
        with (
            patch.object(_pw_mod, "sync_playwright") as _pw_sp,
            patch("fitz.open") as _fitz_open,
        ):
            ctx = _pw_sp.return_value.__enter__.return_value
            browser = ctx.chromium.launch.return_value
            page = browser.new_context.return_value.new_page.return_value
            page.pdf.return_value = b"%PDF-1.4 test"
            merged = _fitz_open.return_value
            merged.insert_pdf.return_value = None
            merged.save.return_value = None
            merged.close.return_value = None
            try:
                export.main_export(tmp_path)
            except SystemExit:
                pass

        events = read_event_timeline(tmp_path)
        export_done = [e for e in events if e.get("event") == "export_done"]
        assert len(export_done) == 1
        payload = export_done[0]["payload"]
        assert payload["slide_count"] >= 1
        assert payload["include_backup"] is False
        assert payload["version"] >= 1
        assert "presentation_folder" in payload
        assert payload["pdf_path"].endswith(".pdf")


# ---------------------------------------------------------------------------
# Test class 3: handout_done emission
# ---------------------------------------------------------------------------


class TestHandoutEmitsHandoutDone:
    def _seed_minimal_project(
        self, tmp_path: Path
    ) -> None:
        slides = [{
            "slug": "intro",
            "title": "Intro",
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
        }]
        data = {
            "project_name": "x",
            "created_at": "",
            "archetype": "lab_meeting",
            "style_locked": True,
            "closing_slide": None,
            "slides": slides,
            "presentations": [],
        }
        (tmp_path / "deck_state.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def test_handout_emits_handout_done(self, tmp_path: Path) -> None:
        self._seed_minimal_project(tmp_path)
        import utility_skills  # type: ignore[import]
        import playwright.sync_api as _pw_mod

        with patch.object(_pw_mod, "sync_playwright") as _pw_sp:
            ctx = _pw_sp.return_value.__enter__.return_value
            browser = ctx.chromium.launch.return_value
            page = browser.new_page.return_value

            # The handout module's page.pdf(path=...) writes the file
            # at `path`. Simulate by writing real PDF magic bytes there.
            def _fake_pdf(path: str) -> None:
                Path(path).write_bytes(b"%PDF-1.4 test bytes")

            page.pdf.side_effect = _fake_pdf

            try:
                utility_skills.main_handout("2up", tmp_path)
            except SystemExit:
                pass

        events = read_event_timeline(tmp_path)
        handout_done = [e for e in events if e.get("event") == "handout_done"]
        assert len(handout_done) == 1
        payload = handout_done[0]["payload"]
        assert payload["mode"] == "2up"
        assert payload["include_backup"] is False
        assert payload["version"] >= 1
        assert payload["slide_count"] == 1
        assert "handout_path" in payload


# ---------------------------------------------------------------------------
# Test class 4: script_done emission
# ---------------------------------------------------------------------------


class TestScriptEmitsScriptDone:
    def _seed_project_with_presentation(self, tmp_path: Path) -> None:
        slides = [{
            "slug": "intro",
            "title": "Intro",
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
        }]
        presentations = [{
            "folder": "2026_04_30_lab_meeting",
            "created_at": "",
            "slide_manifest": ["intro"],
            "export_count": 0,
            "script_count": 0,
            "handout_count": 0,
            "separator_position": None,
            "separator_content": None,
        }]
        data = {
            "project_name": "x",
            "created_at": "",
            "archetype": "lab_meeting",
            "style_locked": True,
            "closing_slide": None,
            "slides": slides,
            "presentations": presentations,
        }
        (tmp_path / "deck_state.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        # Pre-create the presentation folder so the script generator
        # has somewhere to write.
        (tmp_path / "output" / "2026_04_30_lab_meeting").mkdir(
            parents=True, exist_ok=True
        )

    def test_script_emits_script_done(self, tmp_path: Path) -> None:
        self._seed_project_with_presentation(tmp_path)
        import utility_skills  # type: ignore[import]

        try:
            utility_skills.main_script_generator(tmp_path)
        except SystemExit:
            pass

        events = read_event_timeline(tmp_path)
        script_done = [e for e in events if e.get("event") == "script_done"]
        assert len(script_done) == 1
        payload = script_done[0]["payload"]
        assert payload["presentation_folder"] == "2026_04_30_lab_meeting"
        assert payload["version"] >= 1
        assert payload["slide_count"] == 1
        assert "script_path" in payload


# ---------------------------------------------------------------------------
# Test class 5: recall surfaces timeline events
# ---------------------------------------------------------------------------


class TestRecallSurfacesTimelineEvents:
    def test_recall_finds_export_done_payload(self, tmp_path: Path) -> None:
        append_timeline_event(
            tmp_path,
            event="export_done",
            payload={
                "presentation_folder": "2026_04_30_lab_meeting",
                "version": 3,
                "slide_count": 14,
                "include_backup": False,
                "pdf_path": "output/2026_04_30_lab_meeting/deck_v003.pdf",
            },
        )
        hits = recall(tmp_path, "lab_meeting")
        timeline_hits = [h for h in hits if h.source == "timeline"]
        assert len(timeline_hits) == 1
        assert timeline_hits[0].match["event"] == "export_done"

    def test_recall_finds_event_type_string(self, tmp_path: Path) -> None:
        append_timeline_event(
            tmp_path, event="figure_selected", payload={"slug": "intro", "figure": 3}
        )
        hits = recall(tmp_path, "figure_selected")
        assert any(h.source == "timeline" for h in hits)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
