# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-78 — Cycle 1 (spec + blueprint).

BUG-AUDIT-78 lands the contracts for the memory-architecture RFC at
``spec/memory_architecture_rfc.md``. Cycle 1 is doc + contract only:
no code, no agent edits, no hook wiring. These regressions enforce
that the spec + blueprint anchors are present so Cycle 2 has stable
references to cite.

TEST CLASSES:

1. TestSpecAnchors — BUG-AUDIT-78 Bug Catalog entry + 10 REQ-MEMORY-*
   normative requirements + REQ-CONSULT-DECK-BRIEF-1 supersession
   note + spec references the RFC file.
2. TestBlueprintAnchors — BC-2.17, BC-2.18, BC-3.18, BC-3.19, BC-5.19,
   BC-5.20 added; BC-5.16 carries the supersession note pointing at
   BC-5.19.
3. TestRfcFileAnchors — `spec/memory_architecture_rfc.md` exists,
   references BUG-AUDIT-78, and contains the implementation plan
   (§13) so Cycle 2 has a concrete starting point.

All tests run unconditionally in both workspace and delivered layouts;
zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-78 and
`spec/memory_architecture_rfc.md`.
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
    return _PROJECT_ROOT / "spec" / "memory_architecture_rfc.md"


# ---------------------------------------------------------------------------
# Test class 1: spec anchors
# ---------------------------------------------------------------------------


_REQ_MEMORY_ANCHORS = [
    "REQ-MEMORY-DIALOG-1",
    "REQ-MEMORY-TIMELINE-1",
    "REQ-MEMORY-REWRITE-1",
    "REQ-MEMORY-REWRITE-2",
    "REQ-MEMORY-REWRITE-3",
    "REQ-MEMORY-REWRITE-4",
    "REQ-MEMORY-RECALL-1",
    "REQ-MEMORY-CONSULT-1",
    "REQ-MEMORY-CONSULT-2",
    "REQ-MEMORY-LEDGER-1",
]


class TestSpecAnchors:
    def test_spec_has_bug_audit_78(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-78" in text

    @pytest.mark.parametrize("anchor", _REQ_MEMORY_ANCHORS)
    def test_spec_has_req_memory_anchor(self, anchor: str) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert anchor in text, (
            f"Spec missing normative requirement {anchor}"
        )

    def test_req_consult_deck_brief_1_carries_supersession_note(
        self,
    ) -> None:
        """REQ-CONSULT-DECK-BRIEF-1's write-through clause must
        explicitly note that BUG-AUDIT-78 supersedes it. Without
        this, a future reader could miss that the consultant no
        longer writes the brief."""
        text = _spec_path().read_text(encoding="utf-8")
        # The supersession note exists and references BUG-AUDIT-78.
        assert "Superseded by BUG-AUDIT-78" in text or (
            "superseded by BUG-AUDIT-78" in text.lower()
        )

    def test_spec_references_rfc_file(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "memory_architecture_rfc.md" in text


# ---------------------------------------------------------------------------
# Test class 2: blueprint anchors
# ---------------------------------------------------------------------------


_NEW_BC_ANCHORS = [
    "BC-2.17",
    "BC-2.18",
    "BC-3.18",
    "BC-3.19",
    "BC-5.19",
    "BC-5.20",
]


class TestBlueprintAnchors:
    @pytest.mark.parametrize("anchor", _NEW_BC_ANCHORS)
    def test_blueprint_has_new_bc_anchor(self, anchor: str) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        assert anchor in text, (
            f"Blueprint missing behavioral contract {anchor}"
        )

    def test_bc_5_16_carries_supersession_note(self) -> None:
        """BC-5.16's write-through clause (item 3) must explicitly
        note that BUG-AUDIT-78 supersedes it and point at BC-5.19."""
        text = _blueprint_path().read_text(encoding="utf-8")
        # The supersession appears with both anchors in close proximity.
        # Coarse check: both anchors appear in the same file (already
        # asserted) AND the supersession-language phrase appears.
        assert "BC-5.19" in text
        assert "Superseded by BUG-AUDIT-78" in text or (
            "superseded by BUG-AUDIT-78" in text.lower()
        )

    def test_blueprint_bc_5_19_references_rewriter_card(self) -> None:
        """BC-5.19 must name `agents/rewriter.md` so Cycle 2 has a
        clear path to ship."""
        text = _blueprint_path().read_text(encoding="utf-8")
        assert "agents/rewriter.md" in text

    def test_blueprint_bc_5_20_references_recall_invocation(self) -> None:
        """BC-5.20 must name the canonical recall invocation so the
        agent-card amendment in Cycle 2 has a verbatim string to
        embed."""
        text = _blueprint_path().read_text(encoding="utf-8")
        assert "python -m debrief.launcher recall" in text

    def test_blueprint_bc_3_18_references_anthropic_api(self) -> None:
        """BC-3.18 must commit to the hybrid invocation pattern (read
        agent-card, call API directly) per Q11 consensus. The
        verbatim phrase 'Anthropic API' anchors this."""
        text = _blueprint_path().read_text(encoding="utf-8")
        # We accept either "Anthropic API" or the lowercased form.
        assert "Anthropic API" in text or "anthropic API" in text


# ---------------------------------------------------------------------------
# Test class 3: RFC file anchors
# ---------------------------------------------------------------------------


class TestRfcFileAnchors:
    def test_rfc_file_exists(self) -> None:
        assert _rfc_path().is_file()

    def test_rfc_references_bug_audit_78(self) -> None:
        text = _rfc_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-78" in text

    def test_rfc_has_implementation_plan_section(self) -> None:
        """RFC §13 is the Cycle 2 starting point. The heading must
        be findable so future readers (and Cycle 2 plans) can
        anchor against it."""
        text = _rfc_path().read_text(encoding="utf-8")
        # The heading "## 13. Implementation plan" or similar.
        assert "Implementation plan" in text

    def test_rfc_status_is_v1(self) -> None:
        """RFC v1.0 means architecture is settled. v0.x would mean
        we shouldn't be landing contracts yet."""
        text = _rfc_path().read_text(encoding="utf-8")
        assert "v1.0" in text or "v1.0.0" in text

    def test_rfc_lists_three_triggers(self) -> None:
        """The Q8 consensus locked three triggers, no SessionStart
        for rewrite, no periodic. The RFC's §5.1 must reflect."""
        text = _rfc_path().read_text(encoding="utf-8")
        assert "PreCompact" in text
        # /debrief:quit and /debrief:refresh-brief are the other two.
        assert "/debrief:quit" in text
        assert "/debrief:refresh-brief" in text

    def test_rfc_locks_sonnet_4_6_model(self) -> None:
        """Q12 consensus: Sonnet 4.6, no override mechanism. The RFC
        must reflect."""
        text = _rfc_path().read_text(encoding="utf-8")
        assert "claude-sonnet-4-6" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
