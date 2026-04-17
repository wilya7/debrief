# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-47: archetypes.json schema completeness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _archetypes_path() -> Path:
    if (_PROJECT_ROOT / "src" / "unit_1").is_dir():
        return _PROJECT_ROOT / "src" / "unit_1" / "archetypes.json"
    return _PROJECT_ROOT / "archetypes.json"


@pytest.fixture()
def archetypes() -> dict:
    return json.loads(_archetypes_path().read_text(encoding="utf-8"))


EXPECTED_KEYS = {
    "lab_meeting", "conference_talk", "seminar", "lecture",
    "journal_club", "grant_panel", "job_talk", "thesis_discussion",
    "investor_pitch", "custom",
}

REQUIRED_FIELDS = {
    "presentation_type", "time_default", "time_range", "slide_density",
    "disclosure_emphasis", "narrative_style", "audience_implied",
    "audience_default", "acknowledgment", "handout_default",
    "series_default", "sub_modes", "rhetorical_emphasis",
    "consultant_instructions", "key_defaults_text",
    "content_signal_defaults", "expected_deliverables",
}


class TestArchetypesSchema:

    def test_exactly_10_archetypes(self, archetypes: dict) -> None:
        assert len(archetypes) == 10, (
            f"Expected 10 archetypes, got {len(archetypes)}: {list(archetypes.keys())}"
        )

    def test_all_expected_keys_present(self, archetypes: dict) -> None:
        assert set(archetypes.keys()) == EXPECTED_KEYS

    def test_every_archetype_has_all_required_fields(self, archetypes: dict) -> None:
        for key, entry in archetypes.items():
            missing = REQUIRED_FIELDS - set(entry.keys())
            assert not missing, (
                f"Archetype '{key}' missing fields: {missing}"
            )

    def test_slide_density_values(self, archetypes: dict) -> None:
        valid = {"light", "medium", "dense"}
        for key, entry in archetypes.items():
            assert entry["slide_density"] in valid, (
                f"{key}: slide_density={entry['slide_density']!r} not in {valid}"
            )

    def test_disclosure_emphasis_values(self, archetypes: dict) -> None:
        valid = {"available", "heavy"}
        for key, entry in archetypes.items():
            assert entry["disclosure_emphasis"] in valid, (
                f"{key}: disclosure_emphasis={entry['disclosure_emphasis']!r}"
            )

    def test_acknowledgment_values(self, archetypes: dict) -> None:
        valid = {"required", "optional", "no"}
        for key, entry in archetypes.items():
            assert entry["acknowledgment"] in valid, (
                f"{key}: acknowledgment={entry['acknowledgment']!r}"
            )

    def test_sub_modes_structure(self, archetypes: dict) -> None:
        for key, entry in archetypes.items():
            sm = entry["sub_modes"]
            if sm is not None:
                assert "mode_field" in sm, f"{key}: sub_modes missing mode_field"
                assert "options" in sm, f"{key}: sub_modes missing options"
                assert isinstance(sm["options"], (list, dict)), (
                    f"{key}: sub_modes.options must be list or dict"
                )

    def test_archetypes_with_sub_modes(self, archetypes: dict) -> None:
        should_have = {"journal_club", "job_talk", "thesis_discussion", "investor_pitch"}
        for key in should_have:
            assert archetypes[key]["sub_modes"] is not None, (
                f"{key} should have sub_modes"
            )

    def test_consultant_instructions_non_empty(self, archetypes: dict) -> None:
        for key, entry in archetypes.items():
            assert len(entry["consultant_instructions"]) > 50, (
                f"{key}: consultant_instructions too short ({len(entry['consultant_instructions'])} chars)"
            )

    def test_valid_json(self) -> None:
        path = _archetypes_path()
        json.loads(path.read_text(encoding="utf-8"))
