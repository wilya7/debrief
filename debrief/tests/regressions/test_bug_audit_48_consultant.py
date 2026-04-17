# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-48: consultant.md archetype-aware rewrite."""

from __future__ import annotations

from pathlib import Path

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _consultant_path() -> Path:
    if (_PROJECT_ROOT / "src" / "unit_1").is_dir():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    return _PROJECT_ROOT / "agents" / "consultant.md"


@pytest.fixture(scope="module")
def consultant_text() -> str:
    return _consultant_path().read_text(encoding="utf-8")


class TestConsultantStructure:

    def test_has_briefing_protocol(self, consultant_text: str) -> None:
        assert "## Briefing Protocol" in consultant_text

    def test_has_universal_principles(self, consultant_text: str) -> None:
        assert "## Universal Presentation Principles" in consultant_text

    def test_has_backup_slide_session(self, consultant_text: str) -> None:
        assert "## Backup Slide Session" in consultant_text

    def test_has_dispatch_menu(self, consultant_text: str) -> None:
        assert "## Command Dispatch Menu" in consultant_text

    def test_has_iteration_limit(self, consultant_text: str) -> None:
        assert "check_limit" in consultant_text

    def test_has_oscillation_detection(self, consultant_text: str) -> None:
        assert "oscillat" in consultant_text.lower()


class TestConsultantArchetypeAwareness:

    @pytest.mark.parametrize("archetype", [
        "lab_meeting", "conference_talk", "seminar", "lecture",
        "journal_club", "grant_panel", "job_talk",
        "thesis_discussion", "investor_pitch", "custom",
    ])
    def test_mentions_each_archetype(self, consultant_text: str, archetype: str) -> None:
        assert archetype in consultant_text, (
            f"consultant.md must reference archetype '{archetype}'"
        )

    def test_reads_archetypes_json(self, consultant_text: str) -> None:
        assert "archetypes.json" in consultant_text


class TestConsultantUniversalPrinciples:

    @pytest.mark.parametrize("term", [
        "progressive disclosure",
        "ethos",
        "pathos",
        "logos",
        "confidential",
        "BibTeX",
        "video",
        "narrative flow",
        "acknowledgment",
        "closing slide",
        "font",
        "white space",
        "slide numbering",
        "backup",
    ])
    def test_mentions_universal_principle(self, consultant_text: str, term: str) -> None:
        assert term.lower() in consultant_text.lower(), (
            f"consultant.md must reference universal principle: '{term}'"
        )


class TestConsultantSparringModes:

    def test_panel_mode(self, consultant_text: str) -> None:
        assert "panel" in consultant_text.lower()

    def test_single_interviewer_mode(self, consultant_text: str) -> None:
        assert "single interviewer" in consultant_text.lower() or "one-on-one" in consultant_text.lower()

    def test_socratic_method(self, consultant_text: str) -> None:
        assert "socratic" in consultant_text.lower()
