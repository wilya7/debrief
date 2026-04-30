# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-80 — Cycle 2 Phase 2.

Phase 2 ships the rewrite agent (`agents/rewriter.md`) + the
`rewrite_brief` CLI per BC-3.18 / BC-5.19 / REQ-MEMORY-REWRITE-1..4.
The PreCompact hook wiring (Phase 4) does not depend on these tests
and will follow.

TEST CLASSES:

1. TestExtractAgentCard — frontmatter parser; missing/malformed
   handling; reads the shipped rewriter.md correctly.
2. TestBuildRewriteInputs — formats dialog + timeline + optional
   bootstrap brief into the user-message body.
3. TestValidateBriefStructure — accepts canonical sections; rejects
   missing heading / extra sections.
4. TestExtractRosterYaml — pulls YAML block from `### Roster`; None
   when absent.
5. TestValidateRosterYaml — accepts valid roster; rejects missing
   name/role keys.
6. TestRewriteAgentCard — the shipped rewriter.md card has the
   required structure (model, BC-5.19 discipline rules, canonical
   section list).
7. TestMainRewriteBriefOrchestrator — end-to-end with mocked API.
   Bootstrap mode (first run reads prior brief), normal mode (post-
   bootstrap), failure logging on each failure path, atomic write
   preserves prior versions on validation failure.

All tests run unconditionally in both workspace and delivered layouts;
zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-80 and
blueprint contracts BC-3.18 / BC-5.19.
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


def _rewriter_card_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "rewriter.md"
    return _PROJECT_ROOT / "agents" / "rewriter.md"


def _plugin_root_for_tests() -> Path:
    """Plugin root that contains agents/rewriter.md."""
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1"
    return _PROJECT_ROOT


if str(_launcher_module_dir()) not in sys.path:
    sys.path.insert(0, str(_launcher_module_dir()))

import launcher  # noqa: E402
from launcher import (  # noqa: E402
    append_dialog_turn,
    build_rewrite_inputs,
    extract_agent_card,
    extract_roster_yaml,
    log_rewrite_error,
    main_rewrite_brief,
    validate_brief_structure,
    validate_roster_yaml,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_VALID_BRIEF = """\
# Deck Brief

## Audience

A small mixed-audience lab meeting.

### Roster

```yaml
audience:
  - name: Alice
    role: engineer
    location: Rome
    attendance: remote (Teams)
  - name: Bob
    role: PI
    attendance: in-person
```

## Room composition

mixed: 5 in-person + 2 on Teams

## Intent

Convince Bob the funding decision is justified.

## Duration

20 minutes

## Prior decisions

Archetype: lab_meeting. Narrative arc: hero journey.

## Open questions

Whether to include the latest preliminary results.

## Content Signals

code: no
math: yes
diagrams: yes
presentation_type: findings_report
allocated_time: 20min
"""


_VALID_BRIEF_NO_ROSTER = """\
# Deck Brief

## Audience

Lab meeting attendees - no specific names captured yet.

## Intent

Share preliminary findings.
"""


def _seed_minimal_dialog(project_root: Path, *, count: int = 3) -> None:
    for i in range(count):
        append_dialog_turn(
            project_root,
            role="user" if i % 2 == 0 else "consultant",
            responding_agent="consultant",
            content=f"turn body {i}",
            metadata={"phase": "discovery", "sub_phase": "discovery/dialog"},
        )


# ---------------------------------------------------------------------------
# Test class 1: extract_agent_card
# ---------------------------------------------------------------------------


class TestExtractAgentCard:
    def test_shipped_rewriter_card_parses(self) -> None:
        model, prompt = extract_agent_card(_rewriter_card_path())
        assert model == "claude-sonnet-4-6"
        assert "Rewriter Agent" in prompt or "rewriter" in prompt.lower()
        # Body is non-trivial.
        assert len(prompt) > 1000

    def test_missing_frontmatter_raises(self, tmp_path: Path) -> None:
        card = tmp_path / "card.md"
        card.write_text("# No frontmatter\n", encoding="utf-8")
        with pytest.raises(ValueError, match="frontmatter"):
            extract_agent_card(card)

    def test_unclosed_frontmatter_raises(self, tmp_path: Path) -> None:
        card = tmp_path / "card.md"
        card.write_text("---\nmodel: x\n# no closing\n", encoding="utf-8")
        with pytest.raises(ValueError, match="closing"):
            extract_agent_card(card)

    def test_missing_model_raises(self, tmp_path: Path) -> None:
        card = tmp_path / "card.md"
        card.write_text(
            "---\nname: x\ntools: Read\n---\n\n# Body\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="model"):
            extract_agent_card(card)

    def test_quoted_model_value_stripped(self, tmp_path: Path) -> None:
        card = tmp_path / "card.md"
        card.write_text(
            '---\nmodel: "claude-sonnet-4-6"\n---\n\nBody\n',
            encoding="utf-8",
        )
        model, _ = extract_agent_card(card)
        assert model == "claude-sonnet-4-6"

    def test_body_strips_leading_blank(self, tmp_path: Path) -> None:
        card = tmp_path / "card.md"
        card.write_text(
            "---\nmodel: claude-sonnet-4-6\n---\n\n\n# Heading\nBody\n",
            encoding="utf-8",
        )
        _, prompt = extract_agent_card(card)
        assert prompt.startswith("# Heading")


# ---------------------------------------------------------------------------
# Test class 2: build_rewrite_inputs
# ---------------------------------------------------------------------------


class TestBuildRewriteInputs:
    def test_includes_dialog_section(self) -> None:
        out = build_rewrite_inputs(
            dialog=[{"turn": 1, "role": "user", "content": "hello"}],
            timeline=[],
            prior_brief=None,
        )
        assert "DIALOG ARCHIVE" in out
        assert '"turn": 1' in out

    def test_includes_timeline_section(self) -> None:
        out = build_rewrite_inputs(
            dialog=[],
            timeline=[{"event": "style_locked", "timestamp": "t1"}],
            prior_brief=None,
        )
        assert "EVENT TIMELINE" in out
        assert "style_locked" in out

    def test_omits_bootstrap_when_no_prior_brief(self) -> None:
        out = build_rewrite_inputs(
            dialog=[], timeline=[], prior_brief=None
        )
        assert "BOOTSTRAP" not in out

    def test_includes_bootstrap_when_prior_brief_provided(self) -> None:
        out = build_rewrite_inputs(
            dialog=[],
            timeline=[],
            prior_brief="# Deck Brief\n\n## Audience\nfoo",
        )
        assert "BOOTSTRAP" in out
        assert "## Audience" in out


# ---------------------------------------------------------------------------
# Test class 3: validate_brief_structure
# ---------------------------------------------------------------------------


class TestValidateBriefStructure:
    def test_valid_brief_passes(self) -> None:
        validate_brief_structure(_VALID_BRIEF)

    def test_no_deck_brief_heading_raises(self) -> None:
        with pytest.raises(ValueError, match="# Deck Brief"):
            validate_brief_structure("## Audience\nfoo")

    def test_extra_section_raises(self) -> None:
        bad = (
            "# Deck Brief\n\n## Audience\nfoo\n\n"
            "## Strategy\nnot canonical\n"
        )
        with pytest.raises(ValueError, match="non-canonical"):
            validate_brief_structure(bad)

    def test_subset_of_sections_passes(self) -> None:
        # Sections may be absent during discovery.
        validate_brief_structure(_VALID_BRIEF_NO_ROSTER)


# ---------------------------------------------------------------------------
# Test class 4: extract_roster_yaml
# ---------------------------------------------------------------------------


class TestExtractRosterYaml:
    def test_extracts_yaml_block(self) -> None:
        yaml_text = extract_roster_yaml(_VALID_BRIEF)
        assert yaml_text is not None
        assert "audience:" in yaml_text
        assert "Alice" in yaml_text
        assert "Bob" in yaml_text

    def test_returns_none_when_no_roster_heading(self) -> None:
        assert extract_roster_yaml(_VALID_BRIEF_NO_ROSTER) is None

    def test_returns_none_when_no_yaml_fence(self) -> None:
        bad = "# Deck Brief\n\n## Audience\n\n### Roster\n\nno fence here\n"
        assert extract_roster_yaml(bad) is None


# ---------------------------------------------------------------------------
# Test class 5: validate_roster_yaml
# ---------------------------------------------------------------------------


class TestValidateRosterYaml:
    def test_valid_roster_passes(self) -> None:
        yaml_text = extract_roster_yaml(_VALID_BRIEF)
        assert yaml_text is not None
        validate_roster_yaml(yaml_text)

    def test_missing_audience_key_raises(self) -> None:
        bad = "people:\n  - name: Alice\n    role: engineer\n"
        with pytest.raises(ValueError, match="audience"):
            validate_roster_yaml(bad)

    def test_missing_name_raises(self) -> None:
        bad = "audience:\n  - role: engineer\n"
        with pytest.raises(ValueError, match="name"):
            validate_roster_yaml(bad)

    def test_missing_role_raises(self) -> None:
        bad = "audience:\n  - name: Alice\n"
        with pytest.raises(ValueError, match="role"):
            validate_roster_yaml(bad)

    def test_empty_audience_list_passes(self) -> None:
        # Allowed: rewriter may emit an empty audience list (preferred:
        # omit roster entirely, but empty is tolerated to avoid
        # false-positive failures during early discovery).
        validate_roster_yaml("audience:\n")


# ---------------------------------------------------------------------------
# Test class 6: shipped rewriter.md content
# ---------------------------------------------------------------------------


class TestRewriterCard:
    def test_card_exists(self) -> None:
        assert _rewriter_card_path().is_file()

    def test_card_declares_sonnet_4_6(self) -> None:
        model, _ = extract_agent_card(_rewriter_card_path())
        assert model == "claude-sonnet-4-6"

    def test_card_body_lists_canonical_sections(self) -> None:
        _, body = extract_agent_card(_rewriter_card_path())
        for heading in (
            "## Audience",
            "## Room composition",
            "## Intent",
            "## Duration",
            "## Prior decisions",
            "## Open questions",
            "## Content Signals",
        ):
            assert heading in body, f"card missing canonical section {heading!r}"

    def test_card_body_states_no_invention_rule(self) -> None:
        _, body = extract_agent_card(_rewriter_card_path())
        assert "No invention" in body or "no invention" in body.lower()

    def test_card_body_states_latest_state_only_rule(self) -> None:
        _, body = extract_agent_card(_rewriter_card_path())
        assert "Latest-state-only" in body or "latest-state-only" in body.lower()

    def test_card_body_explains_bootstrap_honor_system(self) -> None:
        _, body = extract_agent_card(_rewriter_card_path())
        assert "Bootstrap" in body or "bootstrap" in body.lower()

    def test_card_body_describes_roster_yaml_required_keys(self) -> None:
        _, body = extract_agent_card(_rewriter_card_path())
        assert "name" in body
        assert "role" in body


# ---------------------------------------------------------------------------
# Test class 7: main_rewrite_brief end-to-end (mocked API)
# ---------------------------------------------------------------------------


class TestMainRewriteBriefOrchestrator:
    def test_happy_path_writes_brief_and_audience(
        self, tmp_path: Path
    ) -> None:
        _seed_minimal_dialog(tmp_path)
        with patch.object(
            launcher, "call_rewrite_agent", return_value=_VALID_BRIEF
        ):
            with pytest.raises(SystemExit) as ei:
                main_rewrite_brief(
                    tmp_path,
                    trigger="/debrief:refresh-brief",
                    plugin_root=_plugin_root_for_tests(),
                )
        assert ei.value.code == 0

        brief = (tmp_path / "deck_brief.md").read_text(encoding="utf-8")
        assert brief == _VALID_BRIEF

        audience = (tmp_path / "output" / "audience.yaml").read_text(
            encoding="utf-8"
        )
        assert "audience:" in audience
        assert "Alice" in audience
        assert "Bob" in audience

    def test_watermark_advances_on_success(self, tmp_path: Path) -> None:
        _seed_minimal_dialog(tmp_path)
        with patch.object(
            launcher, "call_rewrite_agent", return_value=_VALID_BRIEF
        ):
            with pytest.raises(SystemExit):
                main_rewrite_brief(
                    tmp_path,
                    plugin_root=_plugin_root_for_tests(),
                )
        meta = json.loads(
            (tmp_path / ".debrief" / "rewrite_metadata.json").read_text(
                encoding="utf-8"
            )
        )
        assert meta["bootstrap_complete"] is True
        assert meta["model"] == "claude-sonnet-4-6"
        assert meta["agent_version"] == "v1"
        assert meta["last_rewrite_timestamp"] is not None

    def test_bootstrap_includes_prior_brief(self, tmp_path: Path) -> None:
        # Seed a prior brief.
        (tmp_path / "deck_brief.md").write_text(
            "# Deck Brief\n\n## Intent\n\nPrior text.\n",
            encoding="utf-8",
        )
        _seed_minimal_dialog(tmp_path)
        captured: dict[str, str] = {}

        def _fake_call(model: str, system_prompt: str, user_message: str) -> str:
            captured["user_message"] = user_message
            return _VALID_BRIEF

        with patch.object(launcher, "call_rewrite_agent", side_effect=_fake_call):
            with pytest.raises(SystemExit):
                main_rewrite_brief(
                    tmp_path,
                    plugin_root=_plugin_root_for_tests(),
                )
        assert "BOOTSTRAP" in captured["user_message"]
        assert "Prior text." in captured["user_message"]

    def test_post_bootstrap_omits_prior_brief(
        self, tmp_path: Path
    ) -> None:
        # Mark bootstrap complete in metadata.
        meta_path = tmp_path / ".debrief" / "rewrite_metadata.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps({
            "last_archived_turn": 0,
            "last_rewrite_timestamp": "2026-04-29T12:00:00Z",
            "agent_version": "v1",
            "model": "claude-sonnet-4-6",
            "bootstrap_complete": True,
        }), encoding="utf-8")
        # Seed a prior brief that the rewriter should NOT see.
        (tmp_path / "deck_brief.md").write_text(
            "# Deck Brief\n\n## Intent\n\nWILL_NOT_LEAK.\n",
            encoding="utf-8",
        )
        _seed_minimal_dialog(tmp_path)
        captured: dict[str, str] = {}

        def _fake_call(model: str, system_prompt: str, user_message: str) -> str:
            captured["user_message"] = user_message
            return _VALID_BRIEF

        with patch.object(launcher, "call_rewrite_agent", side_effect=_fake_call):
            with pytest.raises(SystemExit):
                main_rewrite_brief(
                    tmp_path,
                    plugin_root=_plugin_root_for_tests(),
                )
        assert "BOOTSTRAP" not in captured["user_message"]
        assert "WILL_NOT_LEAK." not in captured["user_message"]

    def test_api_failure_logs_error_exits_0(self, tmp_path: Path) -> None:
        _seed_minimal_dialog(tmp_path)
        with patch.object(
            launcher,
            "call_rewrite_agent",
            side_effect=RuntimeError("simulated API outage"),
        ):
            with pytest.raises(SystemExit) as ei:
                main_rewrite_brief(
                    tmp_path,
                    trigger="PreCompact",
                    plugin_root=_plugin_root_for_tests(),
                )
        assert ei.value.code == 0
        errors_path = tmp_path / ".debrief" / "rewrite_errors.jsonl"
        assert errors_path.is_file()
        entries = [
            json.loads(line) for line in errors_path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        assert len(entries) == 1
        assert entries[0]["error_class"] == "RuntimeError"
        assert "simulated API outage" in entries[0]["error_message"]
        assert entries[0]["trigger"] == "PreCompact"

    def test_validation_failure_preserves_prior_brief(
        self, tmp_path: Path
    ) -> None:
        # Seed a valid prior brief, then have the API return junk.
        (tmp_path / "deck_brief.md").write_text(
            _VALID_BRIEF, encoding="utf-8"
        )
        # Mark bootstrap complete so the prior brief isn't fed BACK to
        # the agent (we want to observe what happens when the new
        # output is bad).
        meta_path = tmp_path / ".debrief" / "rewrite_metadata.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps({
            "last_archived_turn": 0,
            "last_rewrite_timestamp": None,
            "agent_version": None,
            "model": None,
            "bootstrap_complete": True,
        }), encoding="utf-8")
        _seed_minimal_dialog(tmp_path)
        with patch.object(
            launcher,
            "call_rewrite_agent",
            return_value="garbage that does not start with # Deck Brief",
        ):
            with pytest.raises(SystemExit) as ei:
                main_rewrite_brief(
                    tmp_path,
                    plugin_root=_plugin_root_for_tests(),
                )
        assert ei.value.code == 0
        # Prior brief is still intact.
        assert (tmp_path / "deck_brief.md").read_text(encoding="utf-8") == _VALID_BRIEF
        # Failure logged.
        errors_path = tmp_path / ".debrief" / "rewrite_errors.jsonl"
        assert errors_path.is_file()
        entries = [
            json.loads(line) for line in errors_path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        assert any(e["error_class"] == "brief_structure_invalid" for e in entries)

    def test_roster_yaml_invalid_logs_and_preserves(
        self, tmp_path: Path
    ) -> None:
        _seed_minimal_dialog(tmp_path)
        bad_brief = """\
# Deck Brief

## Audience

text

### Roster

```yaml
audience:
  - role: engineer
```
"""
        with patch.object(
            launcher, "call_rewrite_agent", return_value=bad_brief
        ):
            with pytest.raises(SystemExit) as ei:
                main_rewrite_brief(
                    tmp_path,
                    plugin_root=_plugin_root_for_tests(),
                )
        assert ei.value.code == 0
        # No deck_brief.md written (validation failed before write).
        assert not (tmp_path / "deck_brief.md").exists()
        # Failure logged.
        errors_path = tmp_path / ".debrief" / "rewrite_errors.jsonl"
        entries = [
            json.loads(line) for line in errors_path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        assert any(e["error_class"] == "roster_yaml_invalid" for e in entries)

    def test_brief_without_roster_writes_brief_no_audience_yaml(
        self, tmp_path: Path
    ) -> None:
        _seed_minimal_dialog(tmp_path)
        with patch.object(
            launcher,
            "call_rewrite_agent",
            return_value=_VALID_BRIEF_NO_ROSTER,
        ):
            with pytest.raises(SystemExit) as ei:
                main_rewrite_brief(
                    tmp_path,
                    plugin_root=_plugin_root_for_tests(),
                )
        assert ei.value.code == 0
        # Brief written.
        assert (tmp_path / "deck_brief.md").read_text(encoding="utf-8") == _VALID_BRIEF_NO_ROSTER
        # No audience.yaml emitted (roster absent).
        assert not (tmp_path / "output" / "audience.yaml").exists()


# ---------------------------------------------------------------------------
# Test class 8: log_rewrite_error helper
# ---------------------------------------------------------------------------


class TestLogRewriteError:
    def test_appends_jsonl_entry(self, tmp_path: Path) -> None:
        log_rewrite_error(
            tmp_path,
            trigger="PreCompact",
            error_class="TestError",
            error_message="something failed",
            transcript_path="/tmp/x.jsonl",
        )
        path = tmp_path / ".debrief" / "rewrite_errors.jsonl"
        line = path.read_text(encoding="utf-8").strip()
        entry = json.loads(line)
        assert entry["trigger"] == "PreCompact"
        assert entry["error_class"] == "TestError"
        assert entry["error_message"] == "something failed"
        assert entry["transcript_path"] == "/tmp/x.jsonl"
        assert "timestamp" in entry

    def test_multiple_appends_accumulate(self, tmp_path: Path) -> None:
        for i in range(3):
            log_rewrite_error(
                tmp_path,
                trigger="/debrief:quit",
                error_class=f"E{i}",
                error_message=f"m{i}",
            )
        path = tmp_path / ".debrief" / "rewrite_errors.jsonl"
        lines = [
            line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        assert len(lines) == 3


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
