# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-74.

BUG-AUDIT-74 codifies the deck_brief.md canonical structure and
attaches five discipline obligations to the consultant agent card:
closed section set + machine-readable audience roster + write-through
+ on-session-start mandatory read + post-compaction audit.

TEST CLASSES:

1. TestDeckBriefMaintenanceSection — the new ## Deck Brief Maintenance
   section exists in consultant.md and anchors each obligation.
2. TestCanonicalSectionList — all seven canonical headings appear in
   the section's example block, in the specified order.
3. TestRosterYamlExample — the audience-roster YAML block demonstrates
   the required keys.
4. TestDisciplineRulesPresent — the write-through, on-session-start,
   and post-compaction-audit rules are each explicitly stated.
5. TestSpecAndBlueprintAnchors — BUG-AUDIT-74 / REQ-CONSULT-DECK-BRIEF-1
   / BC-5.16 are present in spec + blueprint.

All tests run unconditionally in both workspace and delivered layouts;
zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-74 and
blueprint contract BC-5.16.
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


def _consultant_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    return _PROJECT_ROOT / "agents" / "consultant.md"


def _spec_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "spec" / "stakeholder_spec.md"
    return _PROJECT_ROOT / "spec" / "stakeholder_spec.md"


def _blueprint_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "blueprint" / "blueprint_contracts.md"
    return _PROJECT_ROOT / "blueprint" / "blueprint_contracts.md"


def _get_section(text: str, heading: str) -> str:
    """Extract the body of a top-level `## ` section by its exact
    heading, running until the next top-level `## ` heading or EOF.
    """
    pattern = (
        re.escape(f"## {heading}")
        + r".*?(?=\n##\s[^#]|\Z)"
    )
    m = re.search(pattern, text, re.DOTALL)
    assert m is not None, (
        f"Section '## {heading}' not found in consultant.md"
    )
    return m.group(0)


# ---------------------------------------------------------------------------
# Test class 1: the new Deck Brief Maintenance section exists
# ---------------------------------------------------------------------------


class TestDeckBriefMaintenanceSection:
    def test_section_exists(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "## Deck Brief Maintenance" in text

    def test_section_cites_bug_audit_74(self) -> None:
        # The section heading begins with this prefix; BUG-AUDIT-78 /
        # BC-5.19 amended the heading to also cite the supersession,
        # so we match by prefix rather than by full heading.
        text = _consultant_md_path().read_text(encoding="utf-8")
        # Locate the section by prefix.
        idx = text.find(
            "## Deck Brief Maintenance (BUG-AUDIT-74"
        )
        assert idx >= 0, "Section heading prefix not found"
        # Slice from the heading to the next top-level `## ` (excluding
        # nested markdown sub-headings inside fenced blocks).
        section_end = text.find("\n## ", idx + 1)
        section = text[idx:section_end] if section_end > 0 else text[idx:]
        assert "BUG-AUDIT-74" in section
        assert "REQ-CONSULT-DECK-BRIEF-1" in section
        assert "BC-5.16" in section

    def test_section_appears_before_command_dispatch_menu(self) -> None:
        """Placement invariant: Deck Brief Maintenance must come
        before Command Dispatch Menu so a scanning consultant reads
        the recovery-surface discipline before getting to dispatch.
        """
        text = _consultant_md_path().read_text(encoding="utf-8")
        brief_pos = text.index("## Deck Brief Maintenance")
        dispatch_pos = text.index("## Command Dispatch Menu")
        assert brief_pos < dispatch_pos


# ---------------------------------------------------------------------------
# Test class 2: canonical section list
# ---------------------------------------------------------------------------


_CANONICAL_SECTIONS = [
    "## Audience",
    "## Room composition",
    "## Intent",
    "## Duration",
    "## Prior decisions",
    "## Open questions",
    "## Content Signals",
]


class TestCanonicalSectionList:
    def test_all_seven_headings_present_in_section(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        for heading in _CANONICAL_SECTIONS:
            assert heading in text, (
                f"Canonical brief heading {heading!r} missing from "
                f"consultant.md"
            )

    def test_headings_appear_in_specified_order(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        positions = [text.index(h) for h in _CANONICAL_SECTIONS]
        # Monotonically increasing positions prove the order is correct.
        assert positions == sorted(positions), (
            f"Canonical brief headings out of order. "
            f"Positions: {list(zip(_CANONICAL_SECTIONS, positions))}"
        )

    def test_audience_has_nested_roster_heading(self) -> None:
        text = _consultant_md_path().read_text(encoding="utf-8")
        assert "### Roster" in text


# ---------------------------------------------------------------------------
# Test class 3: audience-roster YAML example
# ---------------------------------------------------------------------------


class TestRosterYamlExample:
    def _get_yaml_block(self) -> str:
        text = _consultant_md_path().read_text(encoding="utf-8")
        # Find the first ```yaml fenced block inside the Deck Brief
        # Maintenance section. We scope the search to the section to
        # avoid accidentally matching a yaml block elsewhere in the
        # agent card.
        brief_start = text.index("## Deck Brief Maintenance")
        # Find the end of this section by locating the next top-level
        # `## ` heading that is NOT nested inside a markdown code fence.
        # Simpler: scan for the next `## Command Dispatch Menu` which
        # is the section following ours.
        dispatch_start = text.index("## Command Dispatch Menu", brief_start)
        section = text[brief_start:dispatch_start]
        m = re.search(
            r"```yaml\s*\n(.*?)\n```",
            section,
            re.DOTALL,
        )
        assert m is not None, (
            "No yaml fenced block found in Deck Brief Maintenance section"
        )
        return m.group(1)

    def test_yaml_block_declares_audience_list(self) -> None:
        body = self._get_yaml_block()
        assert "audience:" in body

    def test_yaml_block_includes_name_key(self) -> None:
        body = self._get_yaml_block()
        assert re.search(r"\bname:\s", body)

    def test_yaml_block_includes_role_key(self) -> None:
        body = self._get_yaml_block()
        assert re.search(r"\brole:\s", body)

    def test_yaml_block_includes_recommended_keys(self) -> None:
        body = self._get_yaml_block()
        # location / attendance / notes are recommended; at least one
        # should appear in the example so authors see the shape.
        recommended = ["location", "attendance", "notes"]
        present = [k for k in recommended if re.search(rf"\b{k}:\s", body)]
        assert len(present) >= 2, (
            f"Expected at least 2 of {recommended} in yaml example, "
            f"got {present}"
        )


# ---------------------------------------------------------------------------
# Test class 4: the three discipline rules are present
# ---------------------------------------------------------------------------


class TestDisciplineRulesPresent:
    def _maintenance_section(self) -> str:
        text = _consultant_md_path().read_text(encoding="utf-8")
        brief_start = text.index("## Deck Brief Maintenance")
        dispatch_start = text.index("## Command Dispatch Menu", brief_start)
        return text[brief_start:dispatch_start]

    def test_write_through_rule_present(self) -> None:
        # BUG-AUDIT-74's original write-through rule was SUPERSEDED by
        # BUG-AUDIT-78 / BC-5.19 (the rewrite agent is now the sole
        # writer of deck_brief.md). The Deck Brief Maintenance section
        # still has a Write-through subsection, but its content has
        # changed to document the supersession. This test pins the
        # current expectation: the subsection exists, marked as
        # superseded, and points at the new owner.
        section = self._maintenance_section()
        assert "Write-through" in section
        # Marked as superseded.
        assert re.search(
            r"SUPERSEDED|superseded", section
        ), "Write-through subsection must be marked as superseded"
        # Points at BC-5.19 (the new owner).
        assert "BC-5.19" in section, (
            "Write-through subsection must cross-reference BC-5.19"
        )
        # Names the rewrite agent as the new sole writer.
        assert re.search(
            r"sole writer|SOLE writer", section
        ), "Write-through subsection must name the rewrite agent as sole writer"

    def test_on_session_start_read_rule_present(self) -> None:
        section = self._maintenance_section()
        assert "On-session-start" in section
        assert re.search(
            r"read\s+`deck_brief\.md`\s+in\s+full",
            section,
            re.IGNORECASE,
        )
        # Must fire regardless of sub_phase.
        assert re.search(r"regardless of.*sub_phase", section, re.IGNORECASE)

    def test_post_compaction_audit_rule_present(self) -> None:
        section = self._maintenance_section()
        assert "Post-compaction audit" in section
        # Surface-the-loss language.
        assert re.search(
            r"surface (?:the )?loss|surface to the user",
            section,
            re.IGNORECASE,
        )
        # Silent proceeding is forbidden.
        assert re.search(
            r"silent proceeding.*forbidden|silently proceed",
            section,
            re.IGNORECASE,
        )


# ---------------------------------------------------------------------------
# Test class 5: spec + blueprint anchors
# ---------------------------------------------------------------------------


class TestSpecAndBlueprintAnchors:
    def test_spec_contains_bug_audit_74(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-74" in text

    def test_spec_contains_normative_requirement(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "REQ-CONSULT-DECK-BRIEF-1" in text

    def test_blueprint_contains_bc_5_16(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        assert "BC-5.16" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
