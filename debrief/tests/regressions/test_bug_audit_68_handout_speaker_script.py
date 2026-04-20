# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-68.

BUG-AUDIT-68 closes a design gap in `/debrief:handout`: the handout
module never read `speaker_script.md`, so the speaker's actual words
never reached the handout's notes cells. Slides fell back to
`SlideRecord.content_summary` (often a terse label) or rendered
visually empty.

The fix introduces a deterministic three-level precedence per
BC-11.15a: (1) `speaker_script.md` section matched by slug or title,
(2) `content_summary`, (3) explicit `(no notes available)`
placeholder. Silent empty cells are forbidden.

TEST CLASSES:

1. TestSpeakerScriptLoader — unit tests for `_load_speaker_script`.
2. TestHandoutNotesPrecedence — end-to-end via `generate_layout_html`.
3. TestPlaceholderEmitted — placeholder is used when both sources
   are empty.

All tests run unconditionally in both workspace and delivered layouts
via the sibling-discovery path pattern established in
`test_bug_audit_21_handout_robustness.py`; zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-68 and
blueprint contract BC-11.15a.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution, mirroring BUG-AUDIT-21's pattern so the
# same test file runs unchanged in workspace and delivered layouts.
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


def _debrief_state_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_2"
    return _PROJECT_ROOT / "src" / "debrief"


for _dir in (_debrief_state_module_dir(), _utility_skills_module_dir()):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_slide(
    slug: str,
    *,
    title: str | None = None,
    content_summary: str | None = None,
    backup: bool = False,
) -> SimpleNamespace:
    """Build a minimal slide object compatible with generate_layout_html."""
    return SimpleNamespace(
        slug=slug,
        title=title or f"Title of {slug}",
        content_summary=content_summary,
        backup=backup,
    )


# Canonical section body — emitted by the script generator and matched
# by the handout loader. Matches `_extract_transition` grammar loosely
# so tests remain robust against future non-breaking additions.
def _script_section(
    slide_index: int,
    slug: str,
    title: str,
    talking_points: str,
    *,
    backup: bool = False,
) -> str:
    label = "(backup)" if backup else ""
    header = f"## Slide {slide_index}{' ' + label if label else ''}: {title}"
    return "\n".join(
        [
            header,
            "",
            f"**Slug:** `{slug}`",
            "",
            "### Key talking points",
            "",
            talking_points,
            "",
            "### Transition",
            "",
            "Lead into the next slide.",
            "",
            "### Estimated speaking time",
            "",
            "~1 minute",
            "",
            "---",
            "",
        ]
    )


def _write_script(project_root: Path, sections: list[str]) -> None:
    text = "\n".join(sections)
    (project_root / "speaker_script.md").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Test class 1: _load_speaker_script unit tests
# ---------------------------------------------------------------------------


class TestSpeakerScriptLoader:
    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert utility_skills._load_speaker_script(tmp_path) is None

    def test_empty_file_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "speaker_script.md").write_text("", encoding="utf-8")
        assert utility_skills._load_speaker_script(tmp_path) is None

    def test_whitespace_only_file_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "speaker_script.md").write_text(
            "\n   \n\t\n", encoding="utf-8"
        )
        assert utility_skills._load_speaker_script(tmp_path) is None

    def test_single_section_indexed_by_slug_and_title(
        self, tmp_path: Path
    ) -> None:
        section = _script_section(
            1, "intro", "Introduction", "Open with a hook."
        )
        _write_script(tmp_path, [section])
        out = utility_skills._load_speaker_script(tmp_path)
        assert out is not None
        assert "intro" in out
        assert "Introduction" in out
        assert "Open with a hook." in out["intro"]
        # The slug key and title key point to the same body.
        assert out["intro"] == out["Introduction"]

    def test_multiple_sections_each_recorded(self, tmp_path: Path) -> None:
        sections = [
            _script_section(1, "intro", "Introduction", "Alpha body."),
            _script_section(2, "middle", "Middle", "Beta body."),
            _script_section(3, "end", "End", "Gamma body."),
        ]
        _write_script(tmp_path, sections)
        out = utility_skills._load_speaker_script(tmp_path)
        assert out is not None
        assert "Alpha body." in out["intro"]
        assert "Beta body." in out["middle"]
        assert "Gamma body." in out["end"]

    def test_backup_section_parsed_with_qualifier_stripped(
        self, tmp_path: Path
    ) -> None:
        main = _script_section(1, "main", "Main", "Main body.")
        backup_divider = "## Backup Slides\n\nQ&A-only slides follow.\n\n---\n"
        backup_section = _script_section(
            2, "backup1", "Backup One", "Backup body.", backup=True
        )
        _write_script(tmp_path, [main, backup_divider, backup_section])
        out = utility_skills._load_speaker_script(tmp_path)
        assert out is not None
        assert "backup1" in out
        # The "(backup)" qualifier is stripped before title matching.
        assert "Backup One" in out
        assert "Backup body." in out["backup1"]

    def test_section_without_slug_marker_still_matched_by_title(
        self, tmp_path: Path
    ) -> None:
        # Hand-authored section without the generator's **Slug:** marker.
        section = (
            "## Slide 1: Manual Section\n\n"
            "No slug marker here — just prose.\n"
            "But we do want to find it by title.\n\n"
            "---\n"
        )
        _write_script(tmp_path, [section])
        out = utility_skills._load_speaker_script(tmp_path)
        assert out is not None
        assert "Manual Section" in out
        assert "No slug marker here" in out["Manual Section"]


# ---------------------------------------------------------------------------
# Test class 2: Handout notes precedence (end-to-end via generate_layout_html)
# ---------------------------------------------------------------------------


class TestHandoutNotesPrecedence:
    def test_no_script_uses_content_summary(self, tmp_path: Path) -> None:
        slide = _make_slide(
            "intro", content_summary="Terse internal label."
        )
        html = utility_skills.generate_layout_html(
            "2up", [slide], tmp_path
        )
        assert "Terse internal label." in html

    def test_script_section_matched_by_slug_wins_over_summary(
        self, tmp_path: Path
    ) -> None:
        _write_script(
            tmp_path,
            [
                _script_section(
                    1,
                    "intro",
                    "Introduction",
                    "Spoken prose that the audience should read.",
                )
            ],
        )
        slide = _make_slide(
            "intro",
            title="Introduction",
            content_summary="Terse internal label.",
        )
        html = utility_skills.generate_layout_html(
            "2up", [slide], tmp_path
        )
        assert "Spoken prose that the audience should read." in html
        # Summary text must NOT appear when the script overrides it.
        assert "Terse internal label." not in html

    def test_script_title_fallback_when_slug_differs(
        self, tmp_path: Path
    ) -> None:
        # Script section uses a different slug marker than the slide's
        # runtime slug — match must fall back to title.
        section = (
            "## Slide 1: Ratified Title\n\n"
            "**Slug:** `stale-slug-from-earlier-rename`\n\n"
            "### Key talking points\n\n"
            "Title-matched prose body.\n\n"
            "### Transition\n\n"
            "…\n\n"
            "---\n"
        )
        _write_script(tmp_path, [section])
        slide = _make_slide(
            "renamed-slug",
            title="Ratified Title",
            content_summary="Fallback summary.",
        )
        html = utility_skills.generate_layout_html(
            "2up", [slide], tmp_path
        )
        assert "Title-matched prose body." in html
        assert "Fallback summary." not in html

    def test_unmatched_slide_falls_back_to_content_summary(
        self, tmp_path: Path
    ) -> None:
        # Script covers only some slides; unmatched slides must use
        # their content_summary.
        _write_script(
            tmp_path,
            [
                _script_section(
                    1,
                    "matched",
                    "Matched Slide",
                    "Script prose for matched.",
                )
            ],
        )
        matched = _make_slide(
            "matched",
            title="Matched Slide",
            content_summary="summary-for-matched",
        )
        unmatched = _make_slide(
            "unmatched",
            title="Unmatched Slide",
            content_summary="summary-for-unmatched",
        )
        html = utility_skills.generate_layout_html(
            "2up", [matched, unmatched], tmp_path
        )
        assert "Script prose for matched." in html
        assert "summary-for-unmatched" in html
        # The matched slide's content_summary MUST be overridden by the
        # script section, so the summary text MUST NOT appear for it.
        assert "summary-for-matched" not in html


# ---------------------------------------------------------------------------
# Test class 3: Placeholder emitted when both sources empty
# ---------------------------------------------------------------------------


class TestPlaceholderEmitted:
    def test_no_script_no_summary_emits_placeholder(
        self, tmp_path: Path
    ) -> None:
        slide = _make_slide("empty", content_summary=None)
        html = utility_skills.generate_layout_html(
            "2up", [slide], tmp_path
        )
        assert utility_skills._HANDOUT_NOTES_PLACEHOLDER in html

    def test_empty_script_file_treated_as_absent(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "speaker_script.md").write_text(
            "", encoding="utf-8"
        )
        slide = _make_slide(
            "with-summary", content_summary="Summary survives."
        )
        html = utility_skills.generate_layout_html(
            "2up", [slide], tmp_path
        )
        assert "Summary survives." in html
        assert (
            utility_skills._HANDOUT_NOTES_PLACEHOLDER not in html
        )

    def test_whitespace_only_summary_triggers_placeholder(
        self, tmp_path: Path
    ) -> None:
        slide = _make_slide("ws-only", content_summary="   \n  ")
        html = utility_skills.generate_layout_html(
            "2up", [slide], tmp_path
        )
        assert utility_skills._HANDOUT_NOTES_PLACEHOLDER in html

    def test_placeholder_contract_value(self) -> None:
        # BC-11.15a mandates the exact placeholder string. Any drift
        # in this literal is a contract violation detectable here.
        assert (
            utility_skills._HANDOUT_NOTES_PLACEHOLDER
            == "(no notes available)"
        )


# ---------------------------------------------------------------------------
# Test class 4: Contract — handout does NOT read versioned script files
# ---------------------------------------------------------------------------


class TestHandoutIgnoresVersionedScript:
    def test_versioned_script_in_output_folder_not_used(
        self, tmp_path: Path
    ) -> None:
        # A generated script exists under output/<folder>/, but there
        # is no speaker_script.md at the project root. The handout
        # MUST NOT read the versioned file — it falls back to
        # content_summary.
        folder = tmp_path / "output" / "2026_04_20_lab_meeting"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "script_v001.md").write_text(
            _script_section(
                1,
                "intro",
                "Introduction",
                "Versioned-only prose that MUST NOT appear in handout.",
            ),
            encoding="utf-8",
        )
        slide = _make_slide(
            "intro",
            title="Introduction",
            content_summary="fallback-summary-text",
        )
        html = utility_skills.generate_layout_html(
            "2up", [slide], tmp_path
        )
        assert (
            "Versioned-only prose that MUST NOT appear in handout."
            not in html
        )
        assert "fallback-summary-text" in html


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
