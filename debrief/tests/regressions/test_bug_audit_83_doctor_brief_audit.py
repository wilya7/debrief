# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-83 — Cycle 2 Phase 5.

Phase 5 closes Cycle 2 by extending ``debrief doctor`` with a
``--brief-audit`` mode that audits the memory architecture state:
brief presence, structure validity, roster YAML, watermark alignment,
rewrite staleness.

TEST CLASSES:

1. TestAuditBrief — pure-function ``_audit_brief`` across every
   audit dimension (brief absent / present-valid / present-invalid;
   roster absent / valid / invalid; watermark aligned / drifted;
   rewrite fresh / stale).
2. TestMainDoctorBriefAudit — CLI ``--brief-audit`` flag adds
   ``brief_audit`` to JSON output; exit codes (0 clean, 1 drift)
   honor brief-side drift.
3. TestDoctorWithoutBriefAuditFlag — without --brief-audit, the
   slide-state report is unchanged (Phase 1 contract preserved).

All tests run unconditionally in both workspace and delivered layouts;
zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-83 and
blueprint contract BC-3.16 (extended).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
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

import launcher  # noqa: E402
from launcher import (  # noqa: E402
    BriefAuditReport,
    _audit_brief,
    _read_rewrite_metadata,
    _write_rewrite_metadata,
    append_dialog_turn,
    main_doctor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_VALID_BRIEF = """\
# Deck Brief

## Audience

A test audience.

### Roster

```yaml
audience:
  - name: Alice
    role: engineer
  - name: Bob
    role: PI
```

## Intent

Test intent.
"""


_BRIEF_NO_ROSTER = """\
# Deck Brief

## Audience

Audience without a roster yet.

## Intent

Test intent.
"""


_BRIEF_INVALID_STRUCTURE = """\
# Deck Brief

## Audience

text

## Strategy

This section is not in the canonical set.
"""


_BRIEF_INVALID_ROSTER = """\
# Deck Brief

## Audience

text

### Roster

```yaml
audience:
  - role: engineer
```

## Intent

text
"""


def _seed_dialog(tmp_path: Path, n: int) -> None:
    for i in range(n):
        append_dialog_turn(
            tmp_path,
            role="user" if i % 2 == 0 else "consultant",
            responding_agent="consultant",
            content=f"turn {i}",
            metadata={},
        )


def _seed_brief(tmp_path: Path, content: str) -> None:
    (tmp_path / "deck_brief.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test class 1: _audit_brief
# ---------------------------------------------------------------------------


class TestAuditBrief:
    def test_no_brief_no_dialog_clean(self, tmp_path: Path) -> None:
        audit = _audit_brief(tmp_path)
        assert audit.brief_present is False
        assert audit.brief_structure_valid is None
        assert audit.roster_valid is None
        assert audit.watermark_aligned is True  # both 0
        assert audit.rewrite_stale is False

    def test_brief_present_valid(self, tmp_path: Path) -> None:
        _seed_brief(tmp_path, _VALID_BRIEF)
        audit = _audit_brief(tmp_path)
        assert audit.brief_present is True
        assert audit.brief_structure_valid is True
        assert audit.roster_valid is True

    def test_brief_present_no_roster_valid_is_none(
        self, tmp_path: Path
    ) -> None:
        _seed_brief(tmp_path, _BRIEF_NO_ROSTER)
        audit = _audit_brief(tmp_path)
        assert audit.brief_present is True
        assert audit.brief_structure_valid is True
        assert audit.roster_valid is None

    def test_brief_invalid_structure(self, tmp_path: Path) -> None:
        _seed_brief(tmp_path, _BRIEF_INVALID_STRUCTURE)
        audit = _audit_brief(tmp_path)
        assert audit.brief_present is True
        assert audit.brief_structure_valid is False
        # When structure is invalid we don't trust roster either.
        assert audit.roster_valid is None
        assert any("structure invalid" in n for n in audit.notes)

    def test_brief_invalid_roster(self, tmp_path: Path) -> None:
        _seed_brief(tmp_path, _BRIEF_INVALID_ROSTER)
        audit = _audit_brief(tmp_path)
        assert audit.brief_present is True
        assert audit.brief_structure_valid is True
        assert audit.roster_valid is False
        assert any("roster YAML invalid" in n for n in audit.notes)

    def test_watermark_alignment_clean(self, tmp_path: Path) -> None:
        _seed_dialog(tmp_path, 3)
        audit = _audit_brief(tmp_path)
        assert audit.watermark_aligned is True

    def test_watermark_drift_when_archive_truncated(
        self, tmp_path: Path
    ) -> None:
        _seed_dialog(tmp_path, 3)
        # Hand-edit the archive to remove the last entry while leaving
        # the watermark advanced.
        archive_path = tmp_path / ".debrief" / "dialog.jsonl"
        lines = archive_path.read_text(encoding="utf-8").splitlines()
        archive_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        audit = _audit_brief(tmp_path)
        assert audit.watermark_aligned is False
        assert any("watermark" in n.lower() for n in audit.notes)

    def test_rewrite_stale_when_no_rewrite_yet(
        self, tmp_path: Path
    ) -> None:
        _seed_dialog(tmp_path, 6)  # > 5 threshold
        audit = _audit_brief(tmp_path)
        # No rewrite has run yet (last_rewrite_timestamp is None).
        assert audit.rewrite_stale is True
        assert any("no rewrite has run yet" in n for n in audit.notes)

    def test_rewrite_not_stale_with_few_turns(
        self, tmp_path: Path
    ) -> None:
        _seed_dialog(tmp_path, 3)  # below threshold
        audit = _audit_brief(tmp_path)
        assert audit.rewrite_stale is False

    def test_rewrite_stale_when_many_turns_after_last_rewrite(
        self, tmp_path: Path
    ) -> None:
        _seed_dialog(tmp_path, 1)  # T1 has a current timestamp
        # Pin a stale rewrite timestamp far in the past.
        meta = _read_rewrite_metadata(tmp_path)
        # Pre-rewrite timestamp = epoch (lex-comparable to all real
        # ISO 8601 timestamps with the Z suffix).
        meta["last_rewrite_timestamp"] = "1970-01-01T00:00:00Z"
        _write_rewrite_metadata(tmp_path, meta)
        # Append several more turns AFTER the rewrite timestamp.
        for _ in range(7):
            append_dialog_turn(
                tmp_path,
                role="user",
                responding_agent="consultant",
                content="x",
                metadata={},
            )
        audit = _audit_brief(tmp_path)
        assert audit.rewrite_stale is True
        assert any("turns archived since the last rewrite" in n for n in audit.notes)

    def test_rewrite_fresh_when_rewrite_timestamp_recent(
        self, tmp_path: Path
    ) -> None:
        _seed_dialog(tmp_path, 3)
        # Set a future rewrite timestamp (lex-greater than any seeded
        # turn timestamp).
        meta = _read_rewrite_metadata(tmp_path)
        meta["last_rewrite_timestamp"] = "9999-12-31T23:59:59Z"
        _write_rewrite_metadata(tmp_path, meta)
        audit = _audit_brief(tmp_path)
        assert audit.rewrite_stale is False

    def test_returns_brief_audit_report_dataclass(
        self, tmp_path: Path
    ) -> None:
        audit = _audit_brief(tmp_path)
        assert isinstance(audit, BriefAuditReport)


# ---------------------------------------------------------------------------
# Test class 2: main_doctor with --brief-audit
# ---------------------------------------------------------------------------


class TestMainDoctorBriefAudit:
    def test_brief_audit_added_to_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_brief(tmp_path, _VALID_BRIEF)
        _seed_dialog(tmp_path, 2)
        with pytest.raises(SystemExit) as ei:
            main_doctor(tmp_path, brief_audit=True)
        assert ei.value.code == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "brief_audit" in data
        ba = data["brief_audit"]
        assert ba["brief_present"] is True
        assert ba["brief_structure_valid"] is True
        assert ba["roster_valid"] is True
        assert ba["watermark_aligned"] is True
        assert ba["rewrite_stale"] is False
        assert isinstance(ba["notes"], list)

    def test_brief_drift_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_brief(tmp_path, _BRIEF_INVALID_STRUCTURE)
        with pytest.raises(SystemExit) as ei:
            main_doctor(tmp_path, brief_audit=True)
        assert ei.value.code == 1
        # Stderr names brief-audit DRIFT.
        err = capsys.readouterr().err
        assert "brief-audit DRIFT" in err

    def test_watermark_drift_exits_1(
        self, tmp_path: Path
    ) -> None:
        _seed_dialog(tmp_path, 3)
        # Truncate the archive without resetting the watermark.
        archive_path = tmp_path / ".debrief" / "dialog.jsonl"
        lines = archive_path.read_text(encoding="utf-8").splitlines()
        archive_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        with pytest.raises(SystemExit) as ei:
            main_doctor(tmp_path, brief_audit=True)
        assert ei.value.code == 1

    def test_rewrite_stale_exits_1(self, tmp_path: Path) -> None:
        _seed_dialog(tmp_path, 7)  # > 5 threshold; no rewrite yet
        with pytest.raises(SystemExit) as ei:
            main_doctor(tmp_path, brief_audit=True)
        assert ei.value.code == 1

    def test_clean_brief_audit_with_clean_slides_exits_0(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_brief(tmp_path, _VALID_BRIEF)
        _seed_dialog(tmp_path, 2)
        with pytest.raises(SystemExit) as ei:
            main_doctor(tmp_path, brief_audit=True)
        assert ei.value.code == 0
        err = capsys.readouterr().err
        assert "OK" in err
        assert "Brief audit: clean" in err

    def test_brief_audit_via_cli_dispatch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # End-to-end: invoke main_new() with crafted argv. This is the
        # path the consultant would call from Bash.
        _seed_brief(tmp_path, _VALID_BRIEF)
        argv = [
            "launcher",
            "doctor",
            "--project-root", str(tmp_path),
            "--brief-audit",
        ]
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit) as ei:
                launcher.main_new()
        assert ei.value.code == 0
        out = capsys.readouterr().out
        assert "brief_audit" in out


# ---------------------------------------------------------------------------
# Test class 3: backward compat — doctor without --brief-audit
# ---------------------------------------------------------------------------


class TestDoctorWithoutBriefAuditFlag:
    def test_default_doctor_omits_brief_audit_field(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Even when the brief is malformed, default doctor (without
        # --brief-audit) doesn't audit it.
        _seed_brief(tmp_path, _BRIEF_INVALID_STRUCTURE)
        with pytest.raises(SystemExit) as ei:
            main_doctor(tmp_path)
        assert ei.value.code == 0  # slides clean, brief NOT audited
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "brief_audit" not in data
        # Slide-state fields still present.
        assert "drift_detected" in data
        assert "orphan_files" in data
        assert "orphan_records" in data
        assert "matched_count" in data


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
