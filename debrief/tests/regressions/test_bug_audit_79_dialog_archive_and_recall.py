# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-79 — Cycle 2 Phase 1.

Phase 1 ships the dialog-archive append API + the recall CLI per
BC-2.17 / BC-3.19 / REQ-MEMORY-DIALOG-1 / REQ-MEMORY-RECALL-1. The
PreCompact hook wiring (Phase 4) and the rewrite agent (Phase 2) are
NOT shipped — tests synthesize archives via ``append_dialog_turn``
and exercise the recall path.

TEST CLASSES:

1. TestAppendDialogTurn — schema correctness, watermark advancement,
   monotonic turn numbering, atomicity across multiple appends.
2. TestReadHelpers — read_dialog_archive + read_event_timeline
   tolerate missing files / malformed lines.
3. TestRecall — search behavior across dialog only / dialog + timeline /
   no matches / context window correctness / case insensitivity.
4. TestMainRecallCli — exit codes + JSON-vs-table output detection
   based on stdout isatty.

All tests run unconditionally in both workspace and delivered layouts;
zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-79 and
blueprint contracts BC-2.17 / BC-3.19.
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


if str(_launcher_module_dir()) not in sys.path:
    sys.path.insert(0, str(_launcher_module_dir()))

from launcher import (  # noqa: E402
    append_dialog_turn,
    main_recall,
    read_dialog_archive,
    read_event_timeline,
    recall,
    RecallHit,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_dialog(tmp_path: Path, turns: list[tuple[str, str, str]]) -> None:
    """Seed the dialog archive with (role, responding_agent, content)
    tuples. Uses the public append API so the watermark advances."""
    for role, responding_agent, content in turns:
        append_dialog_turn(
            tmp_path,
            role=role,
            responding_agent=responding_agent,
            content=content,
            metadata={"phase": "discovery", "sub_phase": "discovery/dialog"},
        )


def _seed_timeline(tmp_path: Path, events: list[dict]) -> None:
    """Seed the event timeline with raw event dicts."""
    path = tmp_path / "output" / "timeline.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for evt in events:
            f.write(json.dumps(evt, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Test class 1: append_dialog_turn
# ---------------------------------------------------------------------------


class TestAppendDialogTurn:
    def test_first_append_returns_turn_1(self, tmp_path: Path) -> None:
        t = append_dialog_turn(
            tmp_path,
            role="user",
            responding_agent="consultant",
            content="hi",
            metadata={"phase": "discovery", "sub_phase": "discovery/greeting"},
        )
        assert t == 1

    def test_subsequent_appends_advance_monotonically(
        self, tmp_path: Path
    ) -> None:
        a = append_dialog_turn(tmp_path, role="user", responding_agent="consultant", content="a", metadata={})
        b = append_dialog_turn(tmp_path, role="consultant", responding_agent="consultant", content="b", metadata={})
        c = append_dialog_turn(tmp_path, role="user", responding_agent="stylist", content="c", metadata={})
        assert (a, b, c) == (1, 2, 3)

    def test_archive_file_is_jsonl(self, tmp_path: Path) -> None:
        append_dialog_turn(tmp_path, role="user", responding_agent="consultant", content="hi", metadata={})
        text = (tmp_path / ".debrief" / "dialog.jsonl").read_text(encoding="utf-8")
        # Each line parses as JSON.
        lines = [ln for ln in text.splitlines() if ln.strip()]
        for line in lines:
            json.loads(line)

    def test_entry_schema_has_required_fields(self, tmp_path: Path) -> None:
        append_dialog_turn(
            tmp_path,
            role="user",
            responding_agent="consultant",
            content="hi",
            metadata={"phase": "discovery", "sub_phase": "discovery/greeting"},
        )
        archive = read_dialog_archive(tmp_path)
        assert len(archive) == 1
        entry = archive[0]
        for field in ("turn", "timestamp", "role", "responding_agent",
                      "content", "metadata"):
            assert field in entry, f"missing schema field {field!r}"
        assert entry["role"] == "user"
        assert entry["responding_agent"] == "consultant"
        assert entry["content"] == "hi"
        assert entry["metadata"]["phase"] == "discovery"

    def test_watermark_advances_with_each_append(self, tmp_path: Path) -> None:
        for _ in range(3):
            append_dialog_turn(tmp_path, role="user", responding_agent="consultant", content="x", metadata={})
        meta = json.loads(
            (tmp_path / ".debrief" / "rewrite_metadata.json").read_text(encoding="utf-8")
        )
        assert meta["last_archived_turn"] == 3

    def test_watermark_preserves_other_fields(self, tmp_path: Path) -> None:
        # Pre-seed the watermark with rewrite-related fields populated.
        meta_path = tmp_path / ".debrief" / "rewrite_metadata.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps({
            "last_archived_turn": 0,
            "last_rewrite_timestamp": "2026-04-29T12:00:00Z",
            "agent_version": "v1",
            "model": "claude-sonnet-4-6",
            "bootstrap_complete": True,
        }), encoding="utf-8")
        append_dialog_turn(tmp_path, role="user", responding_agent="consultant", content="x", metadata={})
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["last_archived_turn"] == 1
        assert meta["last_rewrite_timestamp"] == "2026-04-29T12:00:00Z"
        assert meta["agent_version"] == "v1"
        assert meta["model"] == "claude-sonnet-4-6"
        assert meta["bootstrap_complete"] is True

    def test_metadata_defaults_to_empty_dict_when_none(
        self, tmp_path: Path
    ) -> None:
        append_dialog_turn(
            tmp_path,
            role="user",
            responding_agent="consultant",
            content="x",
            metadata=None,
        )
        archive = read_dialog_archive(tmp_path)
        assert archive[0]["metadata"] == {}


# ---------------------------------------------------------------------------
# Test class 2: read helpers
# ---------------------------------------------------------------------------


class TestReadHelpers:
    def test_read_dialog_missing_returns_empty(
        self, tmp_path: Path
    ) -> None:
        assert read_dialog_archive(tmp_path) == []

    def test_read_dialog_skips_malformed_lines(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / ".debrief" / "dialog.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"turn": 1, "role": "user", "content": "ok"}\n'
            'NOT JSON\n'
            '{"turn": 2, "role": "consultant", "content": "ok2"}\n',
            encoding="utf-8",
        )
        archive = read_dialog_archive(tmp_path)
        assert len(archive) == 2
        assert archive[0]["turn"] == 1
        assert archive[1]["turn"] == 2

    def test_read_timeline_missing_returns_empty(
        self, tmp_path: Path
    ) -> None:
        assert read_event_timeline(tmp_path) == []

    def test_read_timeline_returns_entries_in_order(
        self, tmp_path: Path
    ) -> None:
        events = [
            {"event": "briefing_complete", "timestamp": "t1", "payload": {}},
            {"event": "style_locked", "timestamp": "t2", "payload": {}},
        ]
        _seed_timeline(tmp_path, events)
        result = read_event_timeline(tmp_path)
        assert [e["event"] for e in result] == [
            "briefing_complete", "style_locked"
        ]


# ---------------------------------------------------------------------------
# Test class 3: recall
# ---------------------------------------------------------------------------


class TestRecall:
    def test_match_in_dialog(self, tmp_path: Path) -> None:
        _seed_dialog(tmp_path, [
            ("user", "consultant", "Alice is the engineer in Rome."),
            ("consultant", "consultant", "Got it."),
            ("user", "consultant", "Bob is the PI."),
        ])
        hits = recall(tmp_path, "Alice")
        assert len(hits) == 1
        assert hits[0].source == "dialog"
        assert "Alice" in hits[0].match["content"]

    def test_match_case_insensitive(self, tmp_path: Path) -> None:
        _seed_dialog(tmp_path, [
            ("user", "consultant", "Alice is here."),
        ])
        assert len(recall(tmp_path, "ALICE")) == 1
        assert len(recall(tmp_path, "alice")) == 1
        assert len(recall(tmp_path, "Ali")) == 1

    def test_match_in_timeline(self, tmp_path: Path) -> None:
        _seed_timeline(tmp_path, [
            {"event": "paper_attached", "timestamp": "t1",
             "payload": {"path": "papers/lab2024_alice_first_author.pdf"}},
        ])
        hits = recall(tmp_path, "alice")
        assert len(hits) == 1
        assert hits[0].source == "timeline"
        assert hits[0].match["event"] == "paper_attached"

    def test_match_in_both_archives(self, tmp_path: Path) -> None:
        _seed_dialog(tmp_path, [
            ("user", "consultant", "Discussing Alice's role."),
        ])
        _seed_timeline(tmp_path, [
            {"event": "figure_selected", "timestamp": "t1",
             "payload": {"slug": "alice_method", "figure": 3}},
        ])
        hits = recall(tmp_path, "alice")
        sources = sorted(h.source for h in hits)
        assert sources == ["dialog", "timeline"]

    def test_no_matches_returns_empty(self, tmp_path: Path) -> None:
        _seed_dialog(tmp_path, [
            ("user", "consultant", "Bob is the PI."),
        ])
        assert recall(tmp_path, "Carol") == []

    def test_empty_query_returns_empty(self, tmp_path: Path) -> None:
        _seed_dialog(tmp_path, [
            ("user", "consultant", "anything"),
        ])
        assert recall(tmp_path, "") == []

    def test_context_before_and_after_2(self, tmp_path: Path) -> None:
        _seed_dialog(tmp_path, [
            ("user", "consultant", "first"),       # T#1
            ("consultant", "consultant", "second"),  # T#2
            ("user", "consultant", "third"),        # T#3 (match)
            ("consultant", "consultant", "fourth"),  # T#4
            ("user", "consultant", "fifth"),        # T#5
            ("consultant", "consultant", "sixth"),   # T#6
        ])
        hits = recall(tmp_path, "third")
        assert len(hits) == 1
        h = hits[0]
        assert [e["turn"] for e in h.context_before] == [1, 2]
        assert [e["turn"] for e in h.context_after] == [4, 5]

    def test_context_truncated_at_archive_edges(
        self, tmp_path: Path
    ) -> None:
        _seed_dialog(tmp_path, [
            ("user", "consultant", "first"),    # T#1 (match)
            ("user", "consultant", "second"),
        ])
        hits = recall(tmp_path, "first")
        h = hits[0]
        # No before (edge); 1 after available.
        assert h.context_before == []
        assert [e["turn"] for e in h.context_after] == [2]

    def test_match_in_metadata_fields(self, tmp_path: Path) -> None:
        # Metadata fields are searched too (recursive walk over string
        # values in nested dicts).
        append_dialog_turn(
            tmp_path,
            role="user",
            responding_agent="consultant",
            content="ok",
            metadata={"phase": "production", "sub_phase": "production/red_green"},
        )
        hits = recall(tmp_path, "red_green")
        assert len(hits) == 1
        assert hits[0].source == "dialog"

    def test_returns_recall_hit_dataclass(self, tmp_path: Path) -> None:
        _seed_dialog(tmp_path, [
            ("user", "consultant", "Alice"),
        ])
        hits = recall(tmp_path, "Alice")
        assert isinstance(hits[0], RecallHit)


# ---------------------------------------------------------------------------
# Test class 4: main_recall CLI
# ---------------------------------------------------------------------------


class TestMainRecallCli:
    def test_no_matches_exits_0(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_dialog(tmp_path, [
            ("user", "consultant", "Bob"),
        ])
        # Force isatty() True for the table-output branch (just covers
        # that branch without dictating exit-code semantics).
        with patch("sys.stdout.isatty", return_value=True):
            with pytest.raises(SystemExit) as ei:
                main_recall(tmp_path, "Carol")
        assert ei.value.code == 0
        assert "No matches" in capsys.readouterr().out

    def test_matches_exit_0_pretty_when_tty(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_dialog(tmp_path, [
            ("user", "consultant", "Alice is the engineer."),
        ])
        with patch("sys.stdout.isatty", return_value=True):
            with pytest.raises(SystemExit) as ei:
                main_recall(tmp_path, "Alice")
        assert ei.value.code == 0
        out = capsys.readouterr().out
        # Pretty output includes the source label and the match marker.
        assert "[dialog]" in out
        assert "Alice is the engineer." in out

    def test_matches_emit_json_when_not_tty(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_dialog(tmp_path, [
            ("user", "consultant", "Alice is the engineer."),
        ])
        with patch("sys.stdout.isatty", return_value=False):
            with pytest.raises(SystemExit) as ei:
                main_recall(tmp_path, "Alice")
        assert ei.value.code == 0
        out = capsys.readouterr().out
        # JSON parses and contains the expected shape.
        payload = json.loads(out)
        assert isinstance(payload, list)
        assert len(payload) == 1
        assert payload[0]["source"] == "dialog"
        assert "match" in payload[0]
        assert "context_before" in payload[0]
        assert "context_after" in payload[0]

    def test_empty_archive_no_match_exits_0(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # No archive at all — recall returns empty, CLI exits 0.
        with patch("sys.stdout.isatty", return_value=False):
            with pytest.raises(SystemExit) as ei:
                main_recall(tmp_path, "anything")
        assert ei.value.code == 0
        assert json.loads(capsys.readouterr().out) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
