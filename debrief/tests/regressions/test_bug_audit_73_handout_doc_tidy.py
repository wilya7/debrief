# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-73.

BUG-AUDIT-73 refreshes `commands/handout.md` to reflect the post-
BUG-AUDIT-21/-64/-66/-68 handout surface (correct modes, correct
output path, correct parameters, speaker-script merge) and hardens
the consultant's Alternative Dispatch Prompts section with an
explicit NEVER-SKIP notice so the dispatch dialog is treated as a
contract obligation, not a courtesy.

TEST CLASSES:

1. TestHandoutMdCurrent — stale terms removed; current terms present.
2. TestConsultantNeverSkipNotice — NEVER-SKIP notice is present in
   the Alternative Dispatch Prompts section of agents/consultant.md.

All tests run unconditionally in both workspace and delivered layouts
via the sibling-discovery path pattern established in
`test_bug_audit_21_handout_robustness.py`; zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-73.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_1").is_dir()


def _handout_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "commands" / "handout.md"
    return _PROJECT_ROOT / "commands" / "handout.md"


def _consultant_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    return _PROJECT_ROOT / "agents" / "consultant.md"


# ---------------------------------------------------------------------------
# Test class 1: commands/handout.md staleness sweep
# ---------------------------------------------------------------------------


class TestHandoutMdCurrent:
    """Negative + positive term checks ensure handout.md describes
    the current surface and not the pre-BUG-AUDIT-21 world."""

    # ---- Negative checks: stale terms MUST NOT appear ----

    def test_no_reference_to_three_up_mode(self) -> None:
        text = _handout_md_path().read_text(encoding="utf-8")
        # "3-up" was advertised pre-BUG-AUDIT-21; the CLI never supported it.
        assert "3-up" not in text
        assert "3up" not in text

    def test_no_reference_to_notes_only_mode(self) -> None:
        text = _handout_md_path().read_text(encoding="utf-8")
        assert "notes-only" not in text.lower()

    def test_no_reference_to_old_exports_path(self) -> None:
        text = _handout_md_path().read_text(encoding="utf-8")
        # Old output path was `exports/handout.pdf`.
        assert "exports/handout.pdf" not in text

    def test_no_reference_to_no_parameters(self) -> None:
        # The old doc said "No parameters required" — the CLI has --mode
        # and --include-backup.
        text = _handout_md_path().read_text(encoding="utf-8")
        assert "No parameters required" not in text

    # ---- Positive checks: current surface IS described ----

    def test_references_2up_mode(self) -> None:
        text = _handout_md_path().read_text(encoding="utf-8")
        assert "2up" in text

    def test_references_4up_mode(self) -> None:
        text = _handout_md_path().read_text(encoding="utf-8")
        assert "4up" in text

    def test_references_include_backup_flag(self) -> None:
        text = _handout_md_path().read_text(encoding="utf-8")
        assert "--include-backup" in text

    def test_references_output_handouts_directory(self) -> None:
        text = _handout_md_path().read_text(encoding="utf-8")
        assert "output/handouts/" in text

    def test_references_versioned_filename_pattern(self) -> None:
        text = _handout_md_path().read_text(encoding="utf-8")
        assert "handout_v" in text

    def test_references_speaker_script_merge(self) -> None:
        """The BUG-AUDIT-68 speaker_script.md precedence is user-visible
        behavior that belongs in the command doc."""
        text = _handout_md_path().read_text(encoding="utf-8")
        assert "speaker_script.md" in text

    def test_references_handout_css_and_decoupling(self) -> None:
        """handout.css is a first-class stylesheet (BUG-AUDIT-21) and
        the handout is decoupled from /debrief:export — both facts
        belong in the doc."""
        text = _handout_md_path().read_text(encoding="utf-8")
        assert "handout.css" in text
        # Decoupling language appears in some form.
        assert re.search(r"independent of|decoupled", text, re.IGNORECASE)

    def test_references_consultant_dispatch_dialog(self) -> None:
        """The consultant's pre-dispatch dialog (BC-5.15 /
        BUG-AUDIT-66) is the first thing a user encounters — it
        MUST be cross-referenced in the doc."""
        text = _handout_md_path().read_text(encoding="utf-8")
        assert "Alternative Dispatch Prompts" in text

    def test_bug_audit_68_referenced_for_notes_precedence(self) -> None:
        text = _handout_md_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-68" in text
        assert "BC-11.15a" in text


# ---------------------------------------------------------------------------
# Test class 2: consultant NEVER-SKIP notice
# ---------------------------------------------------------------------------


class TestConsultantNeverSkipNotice:
    def _get_dispatch_section(self) -> str:
        text = _consultant_md_path().read_text(encoding="utf-8")
        # Find the "Alternative Dispatch Prompts" heading.
        m = re.search(
            r"##\s+Alternative Dispatch Prompts.*?(?=\n##\s|\Z)",
            text,
            re.DOTALL,
        )
        assert m is not None, (
            "Alternative Dispatch Prompts section not found in consultant.md"
        )
        return m.group(0)

    def test_section_contains_never_skip_language(self) -> None:
        section = self._get_dispatch_section()
        # Case-insensitive match for any of: "NEVER SKIP", "must fire",
        # "contract obligation" — we accept any of the emphatic-language
        # patterns BUG-AUDIT-73 described.
        patterns = [r"NEVER SKIP", r"contract obligation", r"MUST fire"]
        matched = any(
            re.search(p, section, re.IGNORECASE) for p in patterns
        )
        assert matched, (
            f"Alternative Dispatch Prompts section missing NEVER-SKIP "
            f"language. Looked for any of: {patterns}"
        )

    def test_never_skip_notice_references_bug_audit_73(self) -> None:
        section = self._get_dispatch_section()
        # The notice should cite BUG-AUDIT-73 as the anchor so future
        # readers can find the rationale.
        assert "BUG-AUDIT-73" in section

    def test_never_skip_notice_appears_near_top_of_section(self) -> None:
        """The notice belongs where a scanning consultant can't miss
        it — within the first 600 characters of the section body."""
        section = self._get_dispatch_section()
        head = section[:600]
        assert re.search(r"NEVER SKIP|contract obligation", head, re.IGNORECASE), (
            f"NEVER-SKIP notice is not in the first 600 chars of the "
            f"section. Section head: {head!r}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
