# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-90: paper_role taxonomy across archetypes.

BC-5.23 mandates that every archetype in ``archetypes.json`` declares a
``paper_role`` field whose value belongs to a closed set. The mapping is
pinned: journal_club is ``primary_dissection``, lab_meeting is
``concept_source`` (the user's tomorrow lab-meeting case is a valid
concept_source path), thesis_discussion is ``primary_document``, etc.

This test pins the schema (every archetype has the field, value is in the
closed set) and the canonical mapping (each archetype's role is the one
specified). Drift breaks the consultant's branching logic per BC-5.22.

Cross-cutting checks: VETO-07 was generalized in agents/visual-qa.md;
slide-maker.md gained a ## Paper-Derived Figures section; spec
REQ-CONSULT-17 was re-scoped from "for journal club presentations" to
"any archetype where paper_role != none" — these are pinned here too.
"""

from __future__ import annotations

import json
from pathlib import Path

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_1").is_dir()


def _archetypes_json_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "archetypes.json"
    return _PROJECT_ROOT / "archetypes.json"


def _agent_card_path(name: str) -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / name
    return _PROJECT_ROOT / "agents" / name


def _spec_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "spec" / "stakeholder_spec.md"
    return _PROJECT_ROOT / "spec" / "stakeholder_spec.md"


VALID_ROLES = frozenset(
    {
        "primary_dissection",
        "primary_thematic",
        "primary_document",
        "concept_source",
        "background_reference",
    }
)
# BUG-AUDIT-91 retired the `none` value; paper handling is universally available.
RETIRED_ROLES = frozenset({"none"})

EXPECTED_MAPPING = {
    "lab_meeting": "concept_source",
    "conference_talk": "background_reference",
    "seminar": "concept_source",
    "lecture": "concept_source",
    "journal_club": "primary_dissection",
    "grant_panel": "background_reference",  # was "none" pre-BUG-AUDIT-91
    "job_talk": "background_reference",
    "thesis_discussion": "primary_document",
    "investor_pitch": "background_reference",  # was "none" pre-BUG-AUDIT-91
    "custom": "concept_source",  # was "none" pre-BUG-AUDIT-91
}

# BUG-AUDIT-91: paper_required is true ONLY for archetypes where the paper IS the
# defended/dissected subject. All other archetypes accept papers if offered.
EXPECTED_PAPER_REQUIRED = {
    "journal_club": True,
    "thesis_discussion": True,
    "lab_meeting": False,
    "conference_talk": False,
    "seminar": False,
    "lecture": False,
    "grant_panel": False,
    "job_talk": False,
    "investor_pitch": False,
    "custom": False,
}


# ---------------------------------------------------------------------------
# archetypes.json schema
# ---------------------------------------------------------------------------


def test_every_archetype_has_paper_role_field() -> None:
    archetypes = json.loads(_archetypes_json_path().read_text())
    for name, entry in archetypes.items():
        assert "paper_role" in entry, (
            f"archetype {name!r} is missing the paper_role field per BC-5.23"
        )


def test_paper_role_values_are_in_closed_set() -> None:
    archetypes = json.loads(_archetypes_json_path().read_text())
    for name, entry in archetypes.items():
        role = entry["paper_role"]
        assert role in VALID_ROLES, (
            f"archetype {name!r} has paper_role={role!r} not in valid set "
            f"{sorted(VALID_ROLES)}"
        )


def test_retired_none_role_does_not_appear_anywhere() -> None:
    """BUG-AUDIT-91: paper_role=none was retired — paper handling is universal now."""
    archetypes = json.loads(_archetypes_json_path().read_text())
    for name, entry in archetypes.items():
        assert entry["paper_role"] not in RETIRED_ROLES, (
            f"archetype {name!r} has retired paper_role={entry['paper_role']!r}; "
            "BUG-AUDIT-91 retired this value — every archetype accepts papers now"
        )


def test_every_archetype_has_paper_required_field() -> None:
    archetypes = json.loads(_archetypes_json_path().read_text())
    for name, entry in archetypes.items():
        assert "paper_required" in entry, (
            f"archetype {name!r} is missing paper_required field per BC-5.23 "
            "(BUG-AUDIT-91 amendment)"
        )
        assert isinstance(entry["paper_required"], bool), (
            f"archetype {name!r}: paper_required must be a bool, got "
            f"{type(entry['paper_required']).__name__}"
        )


def test_canonical_paper_required_mapping_pinned() -> None:
    archetypes = json.loads(_archetypes_json_path().read_text())
    for name, expected in EXPECTED_PAPER_REQUIRED.items():
        actual = archetypes[name]["paper_required"]
        assert actual == expected, (
            f"archetype {name!r}: expected paper_required={expected!r}, got {actual!r}"
        )


def test_only_journal_club_and_thesis_have_paper_required_true() -> None:
    """The two-axis design: only the archetypes where the paper IS the subject demand it."""
    archetypes = json.loads(_archetypes_json_path().read_text())
    required_archetypes = {
        name for name, entry in archetypes.items() if entry["paper_required"]
    }
    assert required_archetypes == {"journal_club", "thesis_discussion"}, (
        f"Only journal_club and thesis_discussion may set paper_required=true; "
        f"got {sorted(required_archetypes)}"
    )


def test_canonical_paper_role_mapping_pinned() -> None:
    archetypes = json.loads(_archetypes_json_path().read_text())
    for name, expected in EXPECTED_MAPPING.items():
        assert name in archetypes, f"archetype {name!r} missing from archetypes.json"
        actual = archetypes[name]["paper_role"]
        assert actual == expected, (
            f"archetype {name!r}: expected paper_role={expected!r}, got {actual!r}"
        )


def test_lab_meeting_is_concept_source() -> None:
    """The user's tomorrow case: lab_meeting + Figure 2 of a paper."""
    archetypes = json.loads(_archetypes_json_path().read_text())
    assert archetypes["lab_meeting"]["paper_role"] == "concept_source"


def test_journal_club_is_primary_dissection() -> None:
    archetypes = json.loads(_archetypes_json_path().read_text())
    assert archetypes["journal_club"]["paper_role"] == "primary_dissection"


def test_thesis_discussion_is_primary_document() -> None:
    archetypes = json.loads(_archetypes_json_path().read_text())
    assert archetypes["thesis_discussion"]["paper_role"] == "primary_document"


# ---------------------------------------------------------------------------
# visual-qa.md VETO-07 generalization
# ---------------------------------------------------------------------------


def test_veto_07_no_longer_journal_club_only() -> None:
    """VETO-07 detection switched from archetype to file-path under BC-5.23."""
    content = _agent_card_path("visual-qa.md").read_text()
    # The post-fix VETO-07 entry mentions assets/reference/papers/ as the
    # detection signal, rather than restricting to "journal-club archetypes".
    assert "VETO-07" in content
    veto_07_block_start = content.find("VETO-07")
    block = content[veto_07_block_start : veto_07_block_start + 1200]
    assert "assets/reference/papers/" in block, (
        "VETO-07 must use the file-path detection signal, not archetype-name detection"
    )


# ---------------------------------------------------------------------------
# slide-maker.md ## Paper-Derived Figures section
# ---------------------------------------------------------------------------


def test_slide_maker_has_paper_derived_figures_section() -> None:
    content = _agent_card_path("slide-maker.md").read_text()
    assert "## Paper-Derived Figures" in content


def test_slide_maker_documents_concept_source_single_figure_case() -> None:
    """The user's tomorrow case must be explicitly documented in slide-maker."""
    content = _agent_card_path("slide-maker.md").read_text()
    # Look in the Paper-Derived Figures section
    idx = content.find("## Paper-Derived Figures")
    assert idx >= 0
    after = content.find("\n## ", idx + 5)
    section = content[idx:after] if after >= 0 else content[idx:]
    assert "concept_source" in section
    # Single-figure case must be addressed
    assert "single figure" in section.lower() or "one slide" in section.lower()


def test_slide_maker_attribution_format_documented() -> None:
    content = _agent_card_path("slide-maker.md").read_text()
    idx = content.find("## Paper-Derived Figures")
    assert idx >= 0
    after = content.find("\n## ", idx + 5)
    section = content[idx:after] if after >= 0 else content[idx:]
    # The attribution citation line format from REQ-CONSULT-18
    assert "Figure from" in section


# ---------------------------------------------------------------------------
# spec REQ-CONSULT-17 / 18 re-scoping
# ---------------------------------------------------------------------------


def test_req_consult_17_no_longer_journal_club_only() -> None:
    content = _spec_path().read_text()
    # Find REQ-CONSULT-17 paragraph
    idx = content.find("**REQ-CONSULT-17:**")
    assert idx >= 0
    para_end = content.find("\n  4.", idx)  # ends at step 4 of the pipeline
    para = content[idx:para_end] if para_end >= 0 else content[idx : idx + 2000]
    assert "paper_role" in para, (
        "REQ-CONSULT-17 must be re-scoped to mention paper_role per BUG-AUDIT-90"
    )


def test_spec_resolves_papers_plus_reference_priority_question() -> None:
    """Line 4769 open question must be resolved per BUG-AUDIT-90."""
    content = _spec_path().read_text()
    # Find the question
    q_idx = content.find("papers_provided=true` AND `reference_provided=true")
    assert q_idx >= 0
    # The resolution phrase must appear nearby (within ~2 KB after the question)
    near = content[q_idx : q_idx + 2000]
    assert "BUG-AUDIT-90" in near
    assert "paper_analyzer first" in near or "papers_provided` triggers" in near
