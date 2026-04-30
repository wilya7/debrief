# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-84 — Sub-cycle A (spec + blueprint).

BUG-AUDIT-84 lands the contracts for the script-writer architecture
RFC at `spec/script_writer_rfc.md`. Sub-cycle A is doc + contract
only: no code, no agent edits. These regressions enforce that the
spec + blueprint anchors are present so Sub-cycles B (script-writer
agent + CLI) and C (handout simplification + auto-finalization) have
stable references to cite.

TEST CLASSES:

1. TestSpecAnchors — BUG-AUDIT-84 Bug Catalog entry + 4 REQ-SCRIPT-
   WRITER-* normative requirements + supersession notes on REQ-
   SCRIPT-2, REQ-HAND-3, REQ-HAND-6 + spec references the RFC file.
2. TestBlueprintAnchors — BC-3.20, BC-5.21, BC-11.15b, BC-11.20
   added; BC-11.6, BC-11.15a, BC-11.16, BC-11.19 carry supersession
   / amendment notes pointing at BUG-AUDIT-84 and the new BCs.
3. TestRfcFileAnchors — `spec/script_writer_rfc.md` exists, is v1.0,
   references BUG-AUDIT-84, contains §13 (the implementation plan).

All tests run unconditionally in both workspace and delivered layouts;
zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-84 and
`spec/script_writer_rfc.md`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _spec_path() -> Path:
    return _PROJECT_ROOT / "spec" / "stakeholder_spec.md"


def _blueprint_path() -> Path:
    return _PROJECT_ROOT / "blueprint" / "blueprint_contracts.md"


def _rfc_path() -> Path:
    return _PROJECT_ROOT / "spec" / "script_writer_rfc.md"


# ---------------------------------------------------------------------------
# Test class 1: spec anchors
# ---------------------------------------------------------------------------


_REQ_SCRIPT_WRITER_ANCHORS = [
    "REQ-SCRIPT-WRITER-1",
    "REQ-SCRIPT-WRITER-2",
    "REQ-SCRIPT-WRITER-3",
    "REQ-SCRIPT-WRITER-4",
]


class TestSpecAnchors:
    def test_spec_has_bug_audit_84(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-84" in text

    @pytest.mark.parametrize("anchor", _REQ_SCRIPT_WRITER_ANCHORS)
    def test_spec_has_req_anchor(self, anchor: str) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert anchor in text, (
            f"Spec missing normative requirement {anchor}"
        )

    def test_req_script_2_marked_superseded(self) -> None:
        """REQ-SCRIPT-2 (BUG-AUDIT-25 versioned outputs) MUST carry
        a supersession note pointing at BUG-AUDIT-84 / REQ-SCRIPT-
        WRITER-1."""
        text = _spec_path().read_text(encoding="utf-8")
        # The first occurrence of REQ-SCRIPT-2: in the spec proper
        # (not in the Bug Catalog summary). It must carry the
        # supersession note.
        idx = text.find("- **REQ-SCRIPT-2:**")
        assert idx >= 0
        # Within the next 500 chars (the requirement body), the
        # supersession note appears.
        body = text[idx:idx + 500]
        assert "Superseded" in body or "superseded" in body
        assert "BUG-AUDIT-84" in body
        assert "REQ-SCRIPT-WRITER-1" in body

    def test_req_hand_3_carries_bug_audit_84_amendment_note(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        idx = text.find("- **REQ-HAND-3:**")
        assert idx >= 0
        body = text[idx:idx + 600]
        assert "BUG-AUDIT-84" in body
        # Reference to the new BC that collapses the precedence.
        assert "BC-11.15b" in body

    def test_req_hand_6_carries_bug_audit_84_amendment_note(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        idx = text.find("- **REQ-HAND-6:**")
        assert idx >= 0
        body = text[idx:idx + 600]
        assert "BUG-AUDIT-84" in body
        # Reference to the precondition addition.
        assert "speaker_script.md" in body

    def test_spec_references_rfc_file(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "script_writer_rfc.md" in text


# ---------------------------------------------------------------------------
# Test class 2: blueprint anchors
# ---------------------------------------------------------------------------


_NEW_BC_ANCHORS = [
    "BC-3.20",
    "BC-5.21",
    "BC-11.15b",
    "BC-11.20",
]


class TestBlueprintAnchors:
    @pytest.mark.parametrize("anchor", _NEW_BC_ANCHORS)
    def test_blueprint_has_new_bc_anchor(self, anchor: str) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        assert anchor in text, (
            f"Blueprint missing behavioral contract {anchor}"
        )

    def test_bc_11_6_marked_superseded_by_bug_audit_84(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        # BC-11.6's supersession note must cite BUG-AUDIT-84 +
        # REQ-SCRIPT-WRITER-1.
        idx = text.find("**BC-11.6 ")
        assert idx >= 0
        body = text[idx:idx + 800]
        assert "BUG-AUDIT-84" in body
        assert "REQ-SCRIPT-WRITER-1" in body
        assert "Superseded" in body or "superseded" in body

    def test_bc_11_15a_marked_amended(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        idx = text.find("**BC-11.15a ")
        assert idx >= 0
        body = text[idx:idx + 600]
        assert "BUG-AUDIT-84" in body
        assert "BC-11.15b" in body

    def test_bc_11_16_carries_speaker_script_precondition(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        idx = text.find("**BC-11.16 ")
        assert idx >= 0
        body = text[idx:idx + 1500]
        assert "BUG-AUDIT-84" in body
        # The new precondition requires speaker_script.md to exist.
        assert "speaker_script.md" in body

    def test_bc_11_19_marked_amended_by_bug_audit_84(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        idx = text.find("**BC-11.19 ")
        assert idx >= 0
        body = text[idx:idx + 1000]
        assert "BUG-AUDIT-84" in body
        # The amendment retracts the speaker_script.md non-write
        # invariant.
        assert "retract" in body.lower() or "non-write" in body.lower()

    def test_blueprint_bc_3_20_references_anthropic_api(self) -> None:
        """BC-3.20 must commit to the hybrid invocation pattern (read
        agent-card, call API directly) — same pattern as BC-3.18."""
        text = _blueprint_path().read_text(encoding="utf-8")
        idx = text.find("**BC-3.20 ")
        assert idx >= 0
        body = text[idx:idx + 3000]
        assert "Anthropic API" in body or "anthropic API" in body
        # References the agent-card.
        assert "script-writer.md" in body

    def test_blueprint_bc_5_21_references_six_guardrails(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        idx = text.find("**BC-5.21 ")
        assert idx >= 0
        body = text[idx:idx + 3000]
        # Names each of the six guardrails by short label.
        for guardrail_keyword in [
            "source traceability",
            "no new positions",
            "per-slide structure",
            "length budget",
            "roster-aware",
            "co-writer",
        ]:
            assert guardrail_keyword in body.lower(), (
                f"BC-5.21 missing guardrail label: {guardrail_keyword!r}"
            )

    def test_blueprint_bc_11_20_references_backup_path(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        idx = text.find("**BC-11.20 ")
        assert idx >= 0
        body = text[idx:idx + 1500]
        assert ".debrief/script_backups/" in body
        assert "REQ-SCRIPT-WRITER-3" in body


# ---------------------------------------------------------------------------
# Test class 3: RFC file anchors
# ---------------------------------------------------------------------------


class TestRfcFileAnchors:
    def test_rfc_file_exists(self) -> None:
        assert _rfc_path().is_file()

    def test_rfc_status_is_v1(self) -> None:
        text = _rfc_path().read_text(encoding="utf-8")
        # Header line indicates v1.0.
        assert "v1.0" in text

    def test_rfc_references_bug_audit_84(self) -> None:
        text = _rfc_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-84" in text

    def test_rfc_has_implementation_plan_section(self) -> None:
        text = _rfc_path().read_text(encoding="utf-8")
        # §13 implementation plan with three sub-cycles A/B/C.
        assert "Implementation plan" in text
        assert "Sub-cycle A" in text
        assert "Sub-cycle B" in text
        assert "Sub-cycle C" in text

    def test_rfc_locks_token_cap(self) -> None:
        """200K-token cap on assembled inputs (Q1 from refinement)."""
        text = _rfc_path().read_text(encoding="utf-8")
        assert "200K" in text or "200,000" in text

    def test_rfc_locks_voice_drift_threshold(self) -> None:
        """Jaccard similarity 0.5 threshold for voice-drift warnings."""
        text = _rfc_path().read_text(encoding="utf-8")
        assert "0.5" in text

    def test_rfc_documents_external_documents_schema(self) -> None:
        """The forward-compat slot's per-entry schema is documented in
        v1 so BUG-AUDIT-85 lands as population, not schema design."""
        text = _rfc_path().read_text(encoding="utf-8")
        assert "external_documents" in text
        # Per-entry schema fields.
        for field in ("paper_path", "figure_num", "caption", "results_paragraph"):
            assert field in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
