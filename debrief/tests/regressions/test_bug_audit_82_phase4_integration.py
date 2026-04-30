# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-82 — Cycle 2 Phase 4.

Phase 4 wires the integration layer for the memory architecture:
PreCompact hook + transcript parser + emit_event CLI + style_locked
emitter + slash command + consultant-card amendments.

TEST CLASSES:

1. TestAppendDialogTurnsFromTranscript — Q4 capture rule (every user
   turn + only consultant replies; subagent replies excluded);
   tolerance for content-block format; idempotent against the
   watermark.
2. TestPreCompactHookEntry — hooks.json contains the PreCompact entry
   with the correct command + timeout.
3. TestRefreshBriefSlashCommand — commands/refresh-brief.md exists
   with the canonical heading + description + invocation.
4. TestEmitEventCli — emit_event subcommand argparse + payload
   validation + appended timeline entry.
5. TestStyleLockedEmitter — promote_style_draft emits style_locked
   after a successful promotion.
6. TestConsultantRecallDisciplineSection — `## Recall Discipline`
   section anchors.
7. TestConsultantEventEmissionSection — `## Event Timeline Emission`
   section anchors and event-type table.
8. TestConsultantWriteThroughSupersession — the BC-5.16 write-through
   item now reflects the BUG-AUDIT-78 ownership change.

All tests run unconditionally in both workspace and delivered layouts;
zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-82 and
blueprint contracts BC-5.16 (amended), BC-5.20.
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


def _consultant_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    return _PROJECT_ROOT / "agents" / "consultant.md"


def _refresh_brief_md_path() -> Path:
    if _is_workspace_layout():
        return (
            _PROJECT_ROOT / "src" / "unit_1" / "commands" / "refresh-brief.md"
        )
    return _PROJECT_ROOT / "commands" / "refresh-brief.md"


def _hooks_json_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "hooks" / "hooks.json"
    return _PROJECT_ROOT / "hooks" / "hooks.json"


for _dir in (
    _launcher_module_dir(),
    _utility_skills_module_dir(),
    _debrief_state_module_dir(),
    _style_engine_module_dir(),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import launcher  # noqa: E402
from launcher import (  # noqa: E402
    append_dialog_turns_from_transcript,
    append_timeline_event,
    read_dialog_archive,
    read_event_timeline,
)


# ---------------------------------------------------------------------------
# Test class 1: append_dialog_turns_from_transcript
# ---------------------------------------------------------------------------


def _write_transcript(path: Path, turns: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in turns),
        encoding="utf-8",
    )


class TestAppendDialogTurnsFromTranscript:
    def test_captures_user_and_consultant_turns(
        self, tmp_path: Path
    ) -> None:
        transcript = tmp_path / "transcript.jsonl"
        _write_transcript(transcript, [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "what about Alice?"},
            {"role": "assistant", "content": "Tell me about Alice."},
        ])
        n = append_dialog_turns_from_transcript(tmp_path, transcript)
        assert n == 4
        archive = read_dialog_archive(tmp_path)
        assert [e["role"] for e in archive] == [
            "user", "assistant", "user", "assistant",
        ]

    def test_skips_subagent_replies(self, tmp_path: Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        _write_transcript(transcript, [
            {"role": "user", "content": "user msg 1"},
            {"role": "assistant", "subagent_type": "slide-maker",
             "content": "subagent reply (skip)"},
            {"role": "assistant", "content": "consultant reply (capture)"},
        ])
        n = append_dialog_turns_from_transcript(tmp_path, transcript)
        # Two captured: user + consultant. Subagent skipped.
        assert n == 2
        archive = read_dialog_archive(tmp_path)
        contents = [e["content"] for e in archive]
        assert "user msg 1" in contents
        assert any("consultant reply" in c for c in contents)
        assert not any("subagent reply" in c for c in contents)

    def test_handles_content_blocks_format(self, tmp_path: Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        _write_transcript(transcript, [
            {"role": "user",
             "content": [{"type": "text", "text": "block-form user msg"}]},
            {"role": "assistant",
             "content": [
                 {"type": "text", "text": "block-form "},
                 {"type": "text", "text": "consultant reply"},
             ]},
        ])
        n = append_dialog_turns_from_transcript(tmp_path, transcript)
        assert n == 2
        archive = read_dialog_archive(tmp_path)
        assert archive[0]["content"] == "block-form user msg"
        assert archive[1]["content"] == "block-form consultant reply"

    def test_idempotent_against_watermark(self, tmp_path: Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        _write_transcript(transcript, [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "second"},
        ])
        n1 = append_dialog_turns_from_transcript(tmp_path, transcript)
        assert n1 == 2
        # Re-running with same transcript produces no new appends.
        n2 = append_dialog_turns_from_transcript(tmp_path, transcript)
        assert n2 == 0
        archive = read_dialog_archive(tmp_path)
        assert len(archive) == 2

    def test_appends_only_new_turns_after_watermark(
        self, tmp_path: Path
    ) -> None:
        transcript = tmp_path / "transcript.jsonl"
        _write_transcript(transcript, [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "second"},
        ])
        append_dialog_turns_from_transcript(tmp_path, transcript)
        # Add new turns to the transcript.
        _write_transcript(transcript, [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "second"},
            {"role": "user", "content": "third"},
            {"role": "assistant", "content": "fourth"},
        ])
        n = append_dialog_turns_from_transcript(tmp_path, transcript)
        assert n == 2
        archive = read_dialog_archive(tmp_path)
        assert [e["content"] for e in archive] == [
            "first", "second", "third", "fourth",
        ]

    def test_missing_transcript_returns_zero(self, tmp_path: Path) -> None:
        assert append_dialog_turns_from_transcript(
            tmp_path, tmp_path / "nope.jsonl"
        ) == 0

    def test_malformed_lines_skipped(self, tmp_path: Path) -> None:
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            json.dumps({"role": "user", "content": "ok"}) + "\n"
            "NOT JSON\n"
            + json.dumps({"role": "assistant", "content": "also ok"}) + "\n",
            encoding="utf-8",
        )
        n = append_dialog_turns_from_transcript(tmp_path, transcript)
        assert n == 2


# ---------------------------------------------------------------------------
# Test class 2: PreCompact hook entry
# ---------------------------------------------------------------------------


class TestPreCompactHookEntry:
    def test_hooks_json_has_precompact_entry(self) -> None:
        data = json.loads(_hooks_json_path().read_text(encoding="utf-8"))
        assert "PreCompact" in data["hooks"]
        entries = data["hooks"]["PreCompact"]
        assert isinstance(entries, list) and len(entries) == 1
        wrapper = entries[0]
        # Empty-string matcher means fires on auto + manual compaction.
        assert wrapper["matcher"] == ""
        # Inner hook block.
        inner = wrapper["hooks"]
        assert isinstance(inner, list) and len(inner) == 1
        h = inner[0]
        assert h["type"] == "command"
        assert "rewrite_brief" in h["command"]
        assert "PreCompact" in h["command"]
        assert "${CLAUDE_PROJECT_DIR}" in h["command"]
        assert h["timeout"] == 60


# ---------------------------------------------------------------------------
# Test class 3: /debrief:refresh-brief slash command
# ---------------------------------------------------------------------------


class TestRefreshBriefSlashCommand:
    def test_file_exists(self) -> None:
        assert _refresh_brief_md_path().is_file()

    def test_canonical_heading(self) -> None:
        text = _refresh_brief_md_path().read_text(encoding="utf-8")
        assert text.lstrip().startswith("# /debrief:refresh-brief")

    def test_describes_invocation(self) -> None:
        text = _refresh_brief_md_path().read_text(encoding="utf-8")
        assert "rewrite_brief" in text
        assert "/debrief:refresh-brief" in text

    def test_references_rfc(self) -> None:
        text = _refresh_brief_md_path().read_text(encoding="utf-8")
        assert "memory_architecture_rfc.md" in text


# ---------------------------------------------------------------------------
# Test class 4: emit_event CLI
# ---------------------------------------------------------------------------


class TestEmitEventCli:
    def test_appends_to_timeline_via_cli_main(
        self, tmp_path: Path
    ) -> None:
        # We exercise the dispatch branch directly by invoking
        # main_new() with crafted argv. This is the same path the
        # PreCompact hook would run.
        argv = [
            "launcher",
            "emit_event",
            "--event", "briefing_complete",
            "--payload-json", '{"archetype": "lab_meeting", "duration_min": 20}',
            "--project-root", str(tmp_path),
        ]
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit) as ei:
                launcher.main_new()
        assert ei.value.code == 0
        events = read_event_timeline(tmp_path)
        assert len(events) == 1
        assert events[0]["event"] == "briefing_complete"
        assert events[0]["payload"]["archetype"] == "lab_meeting"

    def test_invalid_payload_json_exits_3(self, tmp_path: Path) -> None:
        argv = [
            "launcher",
            "emit_event",
            "--event", "x",
            "--payload-json", "not valid json",
            "--project-root", str(tmp_path),
        ]
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit) as ei:
                launcher.main_new()
        assert ei.value.code == 3

    def test_payload_must_be_object_not_array(self, tmp_path: Path) -> None:
        argv = [
            "launcher",
            "emit_event",
            "--event", "x",
            "--payload-json", "[1, 2, 3]",
            "--project-root", str(tmp_path),
        ]
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit) as ei:
                launcher.main_new()
        assert ei.value.code == 3

    def test_optional_turn_recorded(self, tmp_path: Path) -> None:
        argv = [
            "launcher",
            "emit_event",
            "--event", "slide_approved",
            "--payload-json", '{"slug": "intro"}',
            "--turn", "42",
            "--project-root", str(tmp_path),
        ]
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit):
                launcher.main_new()
        events = read_event_timeline(tmp_path)
        assert events[0]["turn"] == 42


# ---------------------------------------------------------------------------
# Test class 5: style_locked emitter
# ---------------------------------------------------------------------------


class TestStyleLockedEmitter:
    def test_promote_emits_style_locked(self, tmp_path: Path) -> None:
        # Seed minimal state + draft files.
        slides: list[dict] = []
        data = {
            "project_name": "x",
            "created_at": "",
            "archetype": "lab_meeting",
            "style_locked": False,
            "closing_slide": None,
            "slides": slides,
            "presentations": [],
        }
        (tmp_path / "deck_state.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
        (tmp_path / "assets").mkdir(parents=True, exist_ok=True)
        # Draft files.
        draft = tmp_path / ".debrief" / "draft"
        draft.mkdir(parents=True, exist_ok=True)
        cfg = {
            "colors": {"primary": "#000", "background": "#fff"},
            "typography": {},
            "spacing": {},
            "layout": {"slide_width": "1920px", "slide_height": "1080px"},
            "data_viz": {},
            "constraints": {"permitted_diagram_types": []},
            "provenance": {},
        }
        (draft / "style_config.json").write_text(
            json.dumps(cfg), encoding="utf-8"
        )
        (draft / "style_guide.md").write_text(
            "# style guide\n\nrules.\n", encoding="utf-8"
        )

        import utility_skills  # type: ignore[import]

        try:
            utility_skills.promote_style_draft(tmp_path)
        except SystemExit:
            pass

        events = read_event_timeline(tmp_path)
        style_locked = [e for e in events if e["event"] == "style_locked"]
        assert len(style_locked) == 1
        payload = style_locked[0]["payload"]
        assert payload["style_config_path"] == "style_config.json"
        assert payload["style_guide_path"] == "style_guide.md"


# ---------------------------------------------------------------------------
# Test class 6: consultant Recall Discipline section
# ---------------------------------------------------------------------------


class TestConsultantRecallDisciplineSection:
    def test_section_exists(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "## Recall Discipline" in text

    def test_section_cites_anchors(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-78" in text
        assert "REQ-MEMORY-CONSULT-2" in text
        assert "BC-5.20" in text

    def test_section_names_canonical_invocation(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "python -m debrief.launcher recall" in text

    def test_section_names_failure_mode(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        # Must explicitly cite "I don't recall" or similar phrasing.
        assert (
            "I don't recall" in text
            or "the user did not say" in text
            or "feature denial" in text
        )


# ---------------------------------------------------------------------------
# Test class 7: consultant Event Timeline Emission section
# ---------------------------------------------------------------------------


class TestConsultantEventEmissionSection:
    def test_section_exists(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "## Event Timeline Emission" in text

    def test_section_cites_anchors(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-82" in text
        assert "REQ-MEMORY-TIMELINE-1" in text
        assert "BC-2.18" in text

    def test_section_names_canonical_invocation(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "python -m debrief.launcher emit_event" in text

    @pytest.mark.parametrize("event", [
        "briefing_complete",
        "slide_approved",
        "slide_discarded",
        "paper_attached",
        "figure_selected",
        "backup_session_started",
    ])
    def test_section_lists_consultant_driven_event(self, event: str) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert event in text


# ---------------------------------------------------------------------------
# Test class 8: write-through supersession in Deck Brief Maintenance
# ---------------------------------------------------------------------------


class TestConsultantWriteThroughSupersession:
    def test_write_through_section_marked_superseded(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "Write-through rule (SUPERSEDED" in text

    def test_section_states_rewrite_agent_owns_brief(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "rewrite agent" in text
        assert "SOLE writer" in text or "sole writer" in text

    def test_section_names_refresh_brief_recovery_path(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "/debrief:refresh-brief" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
