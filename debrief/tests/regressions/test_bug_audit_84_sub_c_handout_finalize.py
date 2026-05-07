# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-84 Sub-cycle C.

Sub-cycle C of `spec/script_writer_rfc.md` ships three deliverables:

1. **Handout notes-source collapse (BC-11.15b).** The legacy
   three-level precedence (BC-11.15a: script → content_summary →
   placeholder) is reduced to two levels: script section →
   placeholder. The `content_summary` fallback is RETIRED.

2. **Handout precondition + auto-cascade (BC-11.16 amendment).**
   ``main_handout`` now requires ``<project_root>/speaker_script.md``
   to exist. If absent, the handout module auto-cascades by invoking
   ``launcher.main_script_writer(trigger="/debrief:handout-cascade")``
   first, then re-checks. If the script is still missing post-cascade
   (e.g. API outage), the handout exits 0 with a stderr message —
   the consultant is NEVER blocked.

3. **Consultant-card 4-step finalization milestone
   (REQ-SCRIPT-WRITER-4).** ``agents/consultant.md``'s
   ``## Export Transition`` section proposes the four-step sequence
   ``/debrief:refresh-brief → /debrief:script → /debrief:export →
   /debrief:handout`` at deck-complete.

TEST CLASSES:

1. TestNotesSourceCollapse — generate_layout_html falls through to
   placeholder when the script lacks a matching section, even when
   the slide's content_summary is non-empty.
2. TestHandoutPreconditionAutoCascade — main_handout invokes the
   script-writer cascade when speaker_script.md is missing; passes
   through with a stderr message if the cascade still leaves the
   script absent.
3. TestConsultantCardFinalizationMilestone — agents/consultant.md
   contains the verbatim 4-step finalization prompt and references
   REQ-SCRIPT-WRITER-4.

All tests run unconditionally in both workspace and delivered layouts;
zero skips.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


def _utility_skills_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_11"
    return _PROJECT_ROOT / "src" / "debrief"


def _launcher_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_3"
    return _PROJECT_ROOT / "src" / "debrief"


def _debrief_state_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_2"
    return _PROJECT_ROOT / "src" / "debrief"


for _dir in (
    _debrief_state_module_dir(),
    _utility_skills_module_dir(),
    _launcher_module_dir(),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import launcher  # noqa: E402
import utility_skills  # noqa: E402


def _consultant_card_path() -> Path:
    """Locate agents/consultant.md in either layout."""
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    return _PROJECT_ROOT / "agents" / "consultant.md"


# ---------------------------------------------------------------------------
# Test class 1: notes-source collapse (BC-11.15b)
# ---------------------------------------------------------------------------


def _slide(slug: str, **kw) -> SimpleNamespace:
    return SimpleNamespace(
        slug=slug,
        title=kw.get("title") or f"Title of {slug}",
        content_summary=kw.get("content_summary"),
        backup=kw.get("backup", False),
    )


class TestNotesSourceCollapse:
    """BC-11.15b: handout's per-slide notes precedence drops the
    content_summary fallback. Only script section → placeholder."""

    def test_no_script_emits_placeholder(self, tmp_path: Path) -> None:
        slide = _slide("intro", content_summary="Internal label that must not leak.")
        html = utility_skills.generate_layout_html("2up", [slide], tmp_path)
        assert utility_skills._HANDOUT_NOTES_PLACEHOLDER in html
        assert "Internal label that must not leak." not in html

    def test_unmatched_slide_emits_placeholder_not_summary(
        self, tmp_path: Path
    ) -> None:
        # Script covers slide A only; slide B is unmatched.
        (tmp_path / "speaker_script.md").write_text(
            "# Speaker Script\n\n"
            "## Slide 1: Title of intro\n\n"
            "**Slug:** `intro`\n\n"
            "### Key talking points\n\nProse for intro.\n\n"
            "### Transition\n\nNext.\n\n"
            "### Estimated speaking time\n\n~1 minute\n\n---\n",
            encoding="utf-8",
        )
        intro = _slide("intro", content_summary="intro-summary")
        unmatched = _slide("methods", content_summary="methods-summary")
        html = utility_skills.generate_layout_html(
            "2up", [intro, unmatched], tmp_path
        )
        assert "Prose for intro." in html
        assert "methods-summary" not in html
        # Placeholder shows up for the unmatched slide.
        assert utility_skills._HANDOUT_NOTES_PLACEHOLDER in html

    def test_resolve_handout_notes_directly(self) -> None:
        # Direct unit test of the helper to lock in the two-level
        # precedence regardless of HTML rendering surface.
        slide = _slide("foo", content_summary="ignored-now")
        # No script_notes → placeholder, NOT content_summary.
        out = utility_skills._resolve_handout_notes(slide, None)
        assert out == utility_skills._HANDOUT_NOTES_PLACEHOLDER
        # Empty script_notes dict → still placeholder.
        out2 = utility_skills._resolve_handout_notes(slide, {})
        assert out2 == utility_skills._HANDOUT_NOTES_PLACEHOLDER
        # Script section present → returns the section body, not the summary.
        out3 = utility_skills._resolve_handout_notes(
            slide, {"foo": "Script body."}
        )
        assert out3 == "Script body."


# ---------------------------------------------------------------------------
# Test class 2: handout precondition + auto-cascade (BC-11.16 amendment)
# ---------------------------------------------------------------------------


def _seed_handout_project(tmp_path: Path) -> None:
    """Minimal project: deck_state with one approved main slide."""
    data = {
        "project_name": "x",
        "created_at": "",
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": [{
            "slug": "intro",
            "title": "Intro",
            "status": "approved",
            "backup": False,
            "content_summary": "Summary.",
            "visual_approach": None,
            "design_choices": None,
            "forks_not_taken": None,
            "user_recommendations": None,
            "qa_passed": True,
            "accepted_violations": [],
            "last_modified": "",
            "group_id": None,
            "user_assets": [],
            "has_math": False,
        }],
        "presentations": [],
    }
    (tmp_path / "deck_state.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


class TestHandoutPreconditionAutoCascade:
    """BC-11.16 amendment: main_handout requires speaker_script.md.

    BUG-AUDIT-103 amendment: the in-subprocess auto-cascade is RETIRED.
    `main_handout` no longer imports or calls `main_script_writer`. The
    script-precondition self-heal lives at the consultant orchestration
    layer (BC-5.16c). When `speaker_script.md` is missing,
    `main_handout` exits 2 with a clear stderr message — not 0 with a
    silent skip. The two pre-103 tests in this class are RETIRED in
    favor of the new BUG-AUDIT-103 contract; the third test
    (existing-script-no-cascade) is preserved as a no-op-equivalent
    check that asserts main_handout does NOT touch the script-writer.
    """

    def test_missing_script_exits_2_with_message(
        self, tmp_path: Path
    ) -> None:
        """BC-11.16 (BUG-AUDIT-103 amendment): missing speaker_script.md
        causes main_handout to exit 2 with a 'Run /debrief:script first'
        stderr message. The pre-103 auto-cascade is gone."""
        _seed_handout_project(tmp_path)
        # Sentinel: if main_handout still imports main_script_writer and
        # invokes it, this raise would fire and fail the test.
        if hasattr(launcher, "main_script_writer"):
            sentinel_calls: list[int] = []

            def _explode(*a, **kw):
                sentinel_calls.append(1)
                raise AssertionError(
                    "BUG-AUDIT-103 regression: main_handout must NOT "
                    "invoke main_script_writer. The auto-cascade is "
                    "retired; precondition is hard."
                )

            with patch.object(launcher, "main_script_writer", side_effect=_explode):
                with pytest.raises(SystemExit) as ei:
                    utility_skills.main_handout("2up", tmp_path)
            assert sentinel_calls == [], (
                "main_handout invoked main_script_writer despite "
                "BUG-AUDIT-103's hard-precondition contract."
            )
        else:
            with pytest.raises(SystemExit) as ei:
                utility_skills.main_handout("2up", tmp_path)
        assert ei.value.code == 2, (
            f"BC-11.16 (BUG-AUDIT-103): missing speaker_script.md must "
            f"exit 2, not 0; got {ei.value.code}"
        )

    def test_main_handout_does_not_import_main_script_writer(
        self, tmp_path: Path
    ) -> None:
        """BC-11.16 (BUG-AUDIT-103): the auto-cascade import is gone.
        Inspect main_handout's module source (not the test runtime —
        we already mock launcher above) for the `from launcher import
        main_script_writer` line that pre-103 used."""
        import inspect
        src = inspect.getsource(utility_skills.main_handout)
        assert "from launcher import main_script_writer" not in src, (
            "BUG-AUDIT-103 regression: main_handout still imports "
            "main_script_writer for the auto-cascade. The cascade is "
            "retired; the import should be gone."
        )

    def test_existing_script_skips_cascade(self, tmp_path: Path) -> None:
        """When speaker_script.md already exists, the handout does
        NOT invoke the script-writer — the cascade is not triggered."""
        _seed_handout_project(tmp_path)
        (tmp_path / "speaker_script.md").write_text(
            "# Speaker Script\n", encoding="utf-8"
        )
        cascade_calls: list[int] = []

        def _fake_writer(*a, **kw):
            cascade_calls.append(1)
            raise SystemExit(0)

        with patch.object(launcher, "main_script_writer", side_effect=_fake_writer):
            import playwright.sync_api as _pw_mod
            with patch.object(_pw_mod, "sync_playwright") as _pw_sp:
                ctx = _pw_sp.return_value.__enter__.return_value
                browser = ctx.chromium.launch.return_value
                page = browser.new_page.return_value

                def _fake_pdf(path: str) -> None:
                    Path(path).write_bytes(b"%PDF-1.4 test bytes")

                page.pdf.side_effect = _fake_pdf
                try:
                    utility_skills.main_handout("2up", tmp_path)
                except SystemExit:
                    pass
        assert cascade_calls == []  # cascade not invoked


# ---------------------------------------------------------------------------
# Test class 3: consultant card 4-step finalization milestone
# ---------------------------------------------------------------------------


class TestConsultantCardFinalizationMilestone:
    """REQ-SCRIPT-WRITER-4: agents/consultant.md's Export Transition
    section proposes the 4-step finalization sequence."""

    @pytest.fixture(scope="class")
    def card_text(self) -> str:
        return _consultant_card_path().read_text(encoding="utf-8")

    def test_card_exists(self) -> None:
        assert _consultant_card_path().is_file()

    def test_card_has_four_step_finalization_prompt(self, card_text: str) -> None:
        # Each of the four slash commands is named in the finalization
        # prompt, in the prescribed order.
        assert "/debrief:refresh-brief" in card_text
        assert "/debrief:script" in card_text
        assert "/debrief:export" in card_text
        assert "/debrief:handout" in card_text
        # Order: refresh-brief precedes script precedes export
        # precedes handout in the finalization narrative.
        export_section = card_text.split("## Export Transition", 1)[1]
        # Slice up to the next top-level heading so we only inspect
        # the finalization narrative itself.
        next_heading = export_section.find("\n## ")
        if next_heading != -1:
            export_section = export_section[:next_heading]
        i_brief = export_section.find("/debrief:refresh-brief")
        i_script = export_section.find("/debrief:script")
        i_export = export_section.find("/debrief:export")
        i_handout = export_section.find("/debrief:handout")
        assert -1 < i_brief < i_script < i_export < i_handout, (
            "Finalization prompt must order refresh-brief → script "
            "→ export → handout. Indices: "
            f"brief={i_brief}, script={i_script}, "
            f"export={i_export}, handout={i_handout}"
        )

    def test_card_references_req_script_writer_4(self, card_text: str) -> None:
        assert "REQ-SCRIPT-WRITER-4" in card_text

    def test_card_retires_bug_audit_57_content_summary_workflow(
        self, card_text: str
    ) -> None:
        """The pre-BUG-AUDIT-84 instruction to hand-edit
        content_summary before /debrief:script is RETIRED — the
        script is now agent-authored from the full memory surface,
        not template-rendered from content_summary."""
        # The new card must explicitly retract the legacy workflow.
        export_section = card_text.split("## Export Transition", 1)[1]
        next_heading = export_section.find("\n## ")
        if next_heading != -1:
            export_section = export_section[:next_heading]
        # The legacy "before running /debrief:script ensure
        # content_summary..." instruction must be retired.
        assert "retired" in export_section.lower() or "do not" in export_section.lower(), (
            "Export Transition section must explicitly retire the "
            "legacy BUG-AUDIT-57 content_summary workflow."
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
