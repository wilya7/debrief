# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-100.

Bug: ``utility_skills._load_speaker_script`` used regexes that only
matched the script-writer agent's canonical generated form (colon-
separated header + bold-asterisk slug marker on its own line). Hand-
finalized scripts using natural markdown phrasing — em-dash separators,
italic slug markers with budget metadata — failed the parser silently.
``_load_speaker_script`` returned ``None``, ``_resolve_handout_notes``
fell through to the placeholder for every slide, and ``main_handout``
emitted no warning. The user's PDFs showed "(no notes available)" in
every cell despite a well-formed script existing.

Fix (BC-11.15a amendment + BC-11.15c):

  1. Header regex accepts ``:``, em-dash, en-dash, or hyphen as the
     separator after the slide number.
  2. Slug regex accepts optional asterisks before AND after ``Slug:``
     (handling ``**Slug:**``, ``*Slug:``, plain ``Slug:``) and tolerates
     trailing content after the backtick-wrapped slug (e.g. budget
     metadata).
  3. ``main_handout`` counts placeholder fallbacks; when the parser
     returned no matches OR the placeholder ratio is >= 50%, emits
     a stderr warning AND appends a JSON entry to
     ``.debrief/handout_warnings.jsonl``.

Tests: parser-tolerance for headers and slugs (each separator + each
asterisk variant + trailing-metadata case); strict-grammar still parses
(no regression of BUG-AUDIT-68); warning + JSONL log emitted on the
real-world scenario from the field bug report (em-dash headers, italic
slugs); warning suppressed on clean parse; no JSONL log when degradation
threshold not crossed.

The tests must pass from both the workspace and the delivered repo.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_TESTS_DIR = _HERE.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


# Sibling-discovery sys.path setup mirroring the BUG-AUDIT-93/98/99 pattern.
for _u in ("unit_11", "unit_3", "unit_2"):
    _stub = _PROJECT_ROOT / "src" / _u
    if _stub.is_dir() and str(_stub) not in sys.path:
        sys.path.insert(0, str(_stub))
_delivered = _PROJECT_ROOT / "src" / "debrief"
if _delivered.is_dir() and str(_delivered) not in sys.path:
    sys.path.insert(0, str(_delivered))

try:
    utility_skills = importlib.import_module("utility_skills")
except ModuleNotFoundError:  # pragma: no cover
    utility_skills = importlib.import_module("debrief.utility_skills")

import debrief_state  # noqa: E402


def _make_slide(slug: str, title: str, backup: bool = False) -> debrief_state.SlideRecord:
    return debrief_state.SlideRecord(
        slug=slug,
        title=title,
        status="approved",
        backup=backup,
        content_summary=None,
        visual_approach=None,
        design_choices=None,
        forks_not_taken=None,
        user_recommendations=None,
        qa_passed=True,
        accepted_violations=[],
        last_modified="2026-05-07T00:00:00+00:00",
        group_id=None,
        user_assets=[],
        has_math=False,
    )


def _seed_project(
    project_root: Path,
    slides: list[debrief_state.SlideRecord],
    script_text: str | None,
) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / ".debrief").mkdir(exist_ok=True)
    deck = debrief_state.DeckState(
        project_name="parser_tolerance_test",
        created_at="2026-05-07T00:00:00+00:00",
        archetype="lab_meeting",
        style_locked=True,
        closing_slide=None,
        slides=slides,
        presentations=[],
    )
    debrief_state.write_deck_state(project_root, deck)
    if script_text is not None:
        (project_root / "speaker_script.md").write_text(script_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Header regex tolerance: accept :, em-dash, en-dash, hyphen separators.
# ---------------------------------------------------------------------------


class TestBugAudit100HeaderTolerance:
    """``_load_speaker_script`` accepts all four separator characters."""

    @pytest.mark.parametrize(
        "separator,label",
        [
            (":", "colon"),
            ("—", "em-dash"),
            ("–", "en-dash"),
            ("-", "hyphen"),
        ],
    )
    def test_header_separator_accepted(
        self, tmp_path: Path, separator: str, label: str
    ) -> None:
        script = (
            f"## Slide 1 {separator} Welcome\n\n"
            "**Slug:** `welcome`\n\n"
            "Body text for the welcome slide.\n"
        )
        _seed_project(tmp_path, [_make_slide("welcome", "Welcome")], script)
        out = utility_skills._load_speaker_script(tmp_path)
        assert out is not None, (
            f"BC-11.15a (BUG-AUDIT-100): header with {label} separator must parse"
        )
        assert "welcome" in out, (
            f"slug lookup must succeed with {label} separator; got keys {list(out.keys())}"
        )
        assert "Body text for the welcome slide." in out["welcome"]


# ---------------------------------------------------------------------------
# Slug regex tolerance: accept bold/italic/plain marker shapes + trailing meta.
# ---------------------------------------------------------------------------


class TestBugAudit100SlugTolerance:
    """``_load_speaker_script`` accepts all three slug-marker shapes."""

    def test_bold_slug_marker_canonical_form(self, tmp_path: Path) -> None:
        # Strict canonical form from BUG-AUDIT-68. Must still parse.
        script = (
            "## Slide 1: Welcome\n\n"
            "**Slug:** `welcome`\n\n"
            "Body text.\n"
        )
        _seed_project(tmp_path, [_make_slide("welcome", "Welcome")], script)
        out = utility_skills._load_speaker_script(tmp_path)
        assert out is not None
        assert "welcome" in out

    def test_italic_slug_marker(self, tmp_path: Path) -> None:
        script = (
            "## Slide 1 — Welcome\n\n"
            "*Slug: `welcome`*\n\n"
            "Body text.\n"
        )
        _seed_project(tmp_path, [_make_slide("welcome", "Welcome")], script)
        out = utility_skills._load_speaker_script(tmp_path)
        assert out is not None
        assert "welcome" in out

    def test_plain_slug_marker(self, tmp_path: Path) -> None:
        script = (
            "## Slide 1 — Welcome\n\n"
            "Slug: `welcome`\n\n"
            "Body text.\n"
        )
        _seed_project(tmp_path, [_make_slide("welcome", "Welcome")], script)
        out = utility_skills._load_speaker_script(tmp_path)
        assert out is not None
        assert "welcome" in out

    def test_slug_marker_with_trailing_metadata(self, tmp_path: Path) -> None:
        # The exact form from the field bug report: italic, with budget
        # annotation following the slug.
        script = (
            "## Slide 1 — Title + frame\n\n"
            "*Slug: `title-frame` · Budget: 0:20*\n\n"
            "Body text for slide 1.\n"
        )
        _seed_project(tmp_path, [_make_slide("title-frame", "Title + frame")], script)
        out = utility_skills._load_speaker_script(tmp_path)
        assert out is not None, (
            "BC-11.15a (BUG-AUDIT-100): slug marker with trailing metadata must parse"
        )
        assert "title-frame" in out


# ---------------------------------------------------------------------------
# Real-world scenario from the field bug report.
# ---------------------------------------------------------------------------


class TestBugAudit100FieldScenario:
    """End-to-end parse of the exact format from the user's project."""

    def test_eleven_slide_em_dash_italic_script_parses(
        self, tmp_path: Path
    ) -> None:
        # Synthesize 11 slides in the exact shape of the user's project.
        slugs = [
            ("title-frame", "Title + frame"),
            ("adhd-constraints", "ADHD operating constraints"),
            ("four-commitments", "Cogito's four commitments"),
            ("today-cogito", "Today's Cogito"),
            ("next-steps", "Next steps"),
            ("collab-window", "Collaboration window"),
            ("evaluation", "Evaluation plan"),
            ("risks", "Open risks"),
            ("docs", "What I want you to read"),
            ("ask", "The ask"),
            ("close", "Close"),
        ]
        sections = []
        for i, (slug, title) in enumerate(slugs, start=1):
            sections.append(
                f"## Slide {i} — {title}\n\n"
                f"*Slug: `{slug}` · Budget: 0:30*\n\n"
                f"Body text for slide {i}.\n"
            )
        script = "# Speaker Script\n\n" + "---\n\n".join(sections)
        slides = [_make_slide(s, t) for s, t in slugs]
        _seed_project(tmp_path, slides, script)

        out = utility_skills._load_speaker_script(tmp_path)
        assert out is not None, (
            "Field scenario: 11-slide em-dash + italic script must parse"
        )
        for slug, _ in slugs:
            assert slug in out, f"slug {slug!r} missing from parsed map"
            assert f"Body text for slide" in out[slug]


# ---------------------------------------------------------------------------
# Strict-grammar regression: BUG-AUDIT-68 cases still parse.
# ---------------------------------------------------------------------------


class TestBugAudit100StrictGrammarStillWorks:
    """The amended regexes are extensions, not replacements."""

    def test_strict_canonical_form_still_parses(self, tmp_path: Path) -> None:
        # Verbatim shape produced by the script-writer agent (REQ-SCRIPT-WRITER-1).
        script = (
            "## Slide 1: Introduction\n\n"
            "**Slug:** `intro`\n\n"
            "Body for intro.\n\n"
            "## Slide 2 (backup): Q&A backup\n\n"
            "**Slug:** `qa-backup`\n\n"
            "Body for backup.\n"
        )
        _seed_project(
            tmp_path,
            [
                _make_slide("intro", "Introduction"),
                _make_slide("qa-backup", "Q&A backup", backup=True),
            ],
            script,
        )
        out = utility_skills._load_speaker_script(tmp_path)
        assert out is not None
        assert "intro" in out
        assert "qa-backup" in out


# ---------------------------------------------------------------------------
# Warning emission (BC-11.15c).
# ---------------------------------------------------------------------------


class TestBugAudit100WarningEmission:
    """``_emit_handout_degradation_warning`` triggers correctly."""

    def test_warning_fires_when_script_notes_is_none(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_project(tmp_path, [_make_slide("intro", "Intro")], None)
        utility_skills._emit_handout_degradation_warning(
            tmp_path,
            mode="2up",
            total_main_slides=5,
            placeholder_count=5,
            script_notes=None,
        )
        err = capsys.readouterr().err
        assert "WARNING:" in err
        assert "5/5 handout slides used" in err
        assert "(no notes available)" in err
        assert "speaker_script.md is missing" in err
        # JSONL log written.
        log = tmp_path / ".debrief" / "handout_warnings.jsonl"
        assert log.is_file(), (
            "BC-11.15c: .debrief/handout_warnings.jsonl must be written on "
            "degradation"
        )
        entry = json.loads(log.read_text().splitlines()[-1])
        assert entry["mode"] == "2up"
        assert entry["total_main_slides"] == 5
        assert entry["placeholder_count"] == 5
        assert entry["script_present"] is False

    def test_warning_fires_at_50_percent_placeholder_rate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # script_notes is non-None (parser worked) but only 5/10 slides
        # matched — the rest fell through to placeholder. Emit anyway.
        script = "## Slide 1: Title\n\n**Slug:** `intro`\n\nBody.\n"
        _seed_project(tmp_path, [_make_slide("intro", "Intro")], script)
        notes = utility_skills._load_speaker_script(tmp_path)
        utility_skills._emit_handout_degradation_warning(
            tmp_path,
            mode="4up",
            total_main_slides=10,
            placeholder_count=5,
            script_notes=notes,
        )
        err = capsys.readouterr().err
        assert "WARNING:" in err
        assert "5/10" in err
        assert "slug/title mismatch" in err

    def test_warning_suppressed_below_50_percent_threshold(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        script = "## Slide 1: Title\n\n**Slug:** `intro`\n\nBody.\n"
        _seed_project(tmp_path, [_make_slide("intro", "Intro")], script)
        notes = utility_skills._load_speaker_script(tmp_path)
        utility_skills._emit_handout_degradation_warning(
            tmp_path,
            mode="2up",
            total_main_slides=10,
            placeholder_count=4,  # 40% - below threshold
            script_notes=notes,
        )
        err = capsys.readouterr().err
        assert "WARNING:" not in err
        # No JSONL log either.
        log = tmp_path / ".debrief" / "handout_warnings.jsonl"
        assert not log.is_file(), (
            "Below-threshold runs must not produce a warnings log entry"
        )

    def test_warning_suppressed_on_clean_parse(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        script = (
            "## Slide 1: Intro\n\n**Slug:** `intro`\n\nBody.\n"
        )
        _seed_project(tmp_path, [_make_slide("intro", "Intro")], script)
        notes = utility_skills._load_speaker_script(tmp_path)
        utility_skills._emit_handout_degradation_warning(
            tmp_path,
            mode="2up",
            total_main_slides=1,
            placeholder_count=0,
            script_notes=notes,
        )
        err = capsys.readouterr().err
        assert err == ""

    def test_warning_diagnoses_empty_script(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed_project(tmp_path, [_make_slide("intro", "Intro")], "")
        utility_skills._emit_handout_degradation_warning(
            tmp_path,
            mode="2up",
            total_main_slides=3,
            placeholder_count=3,
            script_notes=None,
        )
        err = capsys.readouterr().err
        assert "speaker_script.md is empty" in err

    def test_warning_diagnoses_unparseable_script_with_first_unmatched_header(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The user's actual format — em-dash header — but with the OLD
        # strict regex this would fail. With the new tolerant regex it
        # parses, so simulate "still unparseable" by using a totally bad
        # header shape that even the new regex rejects.
        bad_script = (
            "## Slide 1 // Welcome\n\n"   # `//` is not a valid separator
            "Slug: `intro`\n\n"
            "Body.\n"
        )
        _seed_project(tmp_path, [_make_slide("intro", "Intro")], bad_script)
        utility_skills._emit_handout_degradation_warning(
            tmp_path,
            mode="2up",
            total_main_slides=1,
            placeholder_count=1,
            script_notes=None,
        )
        err = capsys.readouterr().err
        assert "exists but the parser matched zero sections" in err
        log = tmp_path / ".debrief" / "handout_warnings.jsonl"
        assert log.is_file()
        entry = json.loads(log.read_text().splitlines()[-1])
        # The first unmatched header must be reported in the JSONL.
        assert entry["first_unmatched_header"] == "## Slide 1 // Welcome"


# ---------------------------------------------------------------------------
# Helper functions exposed (callers may want to use them in other contexts).
# ---------------------------------------------------------------------------


class TestBugAudit100HelperExports:
    """Public-ish helper symbols exist on the module."""

    def test_first_unmatched_handout_header_returns_none_on_clean(
        self, tmp_path: Path
    ) -> None:
        good = (
            "## Slide 1 — Title\n\n"
            "*Slug: `title`*\n\n"
            "Body.\n"
        )
        (tmp_path / "speaker_script.md").write_text(good)
        result = utility_skills._first_unmatched_handout_header(
            tmp_path / "speaker_script.md"
        )
        assert result is None

    def test_first_unmatched_handout_header_returns_offending_line(
        self, tmp_path: Path
    ) -> None:
        bad = (
            "## Slide 1 // Bad separator\n"
            "## Slide 2: Good separator\n"
        )
        (tmp_path / "speaker_script.md").write_text(bad)
        result = utility_skills._first_unmatched_handout_header(
            tmp_path / "speaker_script.md"
        )
        assert result == "## Slide 1 // Bad separator"

    def test_handout_warnings_rel_path_constant(self) -> None:
        assert utility_skills._HANDOUT_WARNINGS_REL == ".debrief/handout_warnings.jsonl"
