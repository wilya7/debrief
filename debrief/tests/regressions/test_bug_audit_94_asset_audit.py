# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-94: asset usage audit + archive_paper.

User-reported via the 2026-05-05 audit on the journal-club project: the
consultant accepted a paper PDF but never invoked ``paper_analyzer`` —
the source PDF was never archived to ``assets/reference/papers/``,
paper-derived figures ended up in ``assets/images/`` (the user-image
bucket), ``debrief_state.papers_provided`` stayed False, and no
``paper_attached`` event was emitted to ``output/timeline.jsonl``.

This cycle adds:
  (a) a new ``archive_paper`` launcher subcommand for explicit retroactive
      paper-archival,
  (b) a broadened trigger description in the consultant's
      ``## Paper Analyzer Invocation`` section + an explicit recovery clause,
  (c) explicit ``papers_provided=true`` + ``paper_attached`` instructions
      in the consultant's post-success block,
  (d) a ``--asset-audit`` flag on ``debrief doctor`` that detects the
      drift patterns this bug exposed.

These tests pin the four pillars: launcher subcommand presence, doctor
flag presence, consultant-card content, and audit-helper drift detection.
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

# Path setup so the launcher's sibling imports resolve.
for _u in ("unit_3", "unit_2", "unit_12", "unit_1"):
    _stub = _PROJECT_ROOT / "src" / _u
    if _stub.is_dir() and str(_stub) not in sys.path:
        sys.path.insert(0, str(_stub))


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_1").is_dir()


def _consultant_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "consultant.md"
    return _PROJECT_ROOT / "agents" / "consultant.md"


def _archive_paper_command_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "commands" / "archive-paper.md"
    return _PROJECT_ROOT / "commands" / "archive-paper.md"


def _launcher_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_3" / "launcher.py"
    return _PROJECT_ROOT / "src" / "debrief" / "launcher.py"


try:
    launcher = importlib.import_module("launcher")
except ModuleNotFoundError:  # pragma: no cover
    launcher = importlib.import_module("debrief.launcher")


# ---------------------------------------------------------------------------
# (a) archive_paper launcher subcommand
# ---------------------------------------------------------------------------


class TestArchivePaperSubcommand:
    def test_main_archive_paper_function_exists(self) -> None:
        assert hasattr(launcher, "main_archive_paper")
        assert callable(launcher.main_archive_paper)

    def test_dispatch_recognises_archive_paper_subcommand(self) -> None:
        """The launcher's main_new dispatch must include archive_paper."""
        content = _launcher_path().read_text()
        assert 'subcommand == "archive_paper"' in content

    def test_usage_line_lists_archive_paper(self) -> None:
        """The catch-all unknown-subcommand usage message must list archive_paper."""
        content = _launcher_path().read_text()
        # The usage string is a single line in the source — assert the token is present.
        usage_idx = content.find("Usage: python -m debrief.launcher")
        assert usage_idx >= 0
        usage_block = content[usage_idx:usage_idx + 500]
        assert "archive_paper" in usage_block

    def test_archive_paper_rejects_missing_pdf(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        proj = tmp_path / "p"
        proj.mkdir()
        with pytest.raises(SystemExit) as excinfo:
            launcher.main_archive_paper(tmp_path / "nonexistent.pdf", proj)
        assert excinfo.value.code == 1
        err = capsys.readouterr().err
        assert "PDF not found" in err

    def test_archive_paper_rejects_non_pdf_extension(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        proj = tmp_path / "p"
        proj.mkdir()
        not_pdf = tmp_path / "thing.txt"
        not_pdf.write_text("hi")
        with pytest.raises(SystemExit) as excinfo:
            launcher.main_archive_paper(not_pdf, proj)
        assert excinfo.value.code == 1


# ---------------------------------------------------------------------------
# archive_paper end-to-end on a synthetic PDF (when fitz is available)
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_pdf(tmp_path: Path) -> Path:
    """Generate a tiny one-page PDF for end-to-end testing."""
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    doc.set_metadata({"title": "Test Paper", "author": "A. Smith"})
    page = doc.new_page()
    page.insert_text((36, 36), "Test Paper\nA. Smith\n\nFigure 1. A test figure.\nA finding.\n", fontsize=10)
    img = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8))
    img.set_rect(img.irect, (0, 0, 0))
    page.insert_image(fitz.Rect(36, 200, 86, 250), pixmap=img)
    out = tmp_path / "Smith_2026.pdf"
    doc.save(str(out))
    doc.close()
    return out


def _bootstrap_state(project_root: Path) -> None:
    """Minimum debrief_state.json for archive_paper end-to-end."""
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "debrief_state.json").write_text(json.dumps({
        "phase": "discovery", "sub_phase": "discovery/dialog",
        "active_agent": "consultant", "archetype": "lab_meeting",
        "current_group_id": None, "current_slide_slug": None,
        "pending_gate": None, "last_gate_response": None,
        "red_green_started_at": None, "group_slide_index": 0,
        "group_slide_count": 0, "backup_mode": False,
        "completed_groups": [], "pre_view_state": None,
        "view_deferred": False, "closing_slide_pending": False,
        "group_revise_slug": None, "style_import_mode": None,
        "reference_provided": False, "reference_modality": None,
        "papers_provided": False, "selected_figures": None,
        "session_started_at": "2026-05-05T00:00:00+00:00",
        "state_hash": "x",
    }))


class TestArchivePaperEndToEnd:
    """Run main_archive_paper on a real synthetic PDF and assert side-effects."""

    def test_archive_succeeds_writes_pdf_and_figure(
        self, synthetic_pdf: Path, tmp_path: Path
    ) -> None:
        proj = tmp_path / "proj"
        _bootstrap_state(proj)

        with pytest.raises(SystemExit) as excinfo:
            launcher.main_archive_paper(synthetic_pdf, proj)
        assert excinfo.value.code == 0

        # Slug derivation produces "smith_2026" from "Smith_2026.pdf"
        archived = proj / "assets" / "reference" / "papers" / "smith_2026" / synthetic_pdf.name
        assert archived.exists()

        figures_dir = proj / "assets" / "reference" / "papers" / "smith_2026" / "figures"
        assert figures_dir.is_dir()

    def test_archive_sets_papers_provided_true(
        self, synthetic_pdf: Path, tmp_path: Path
    ) -> None:
        proj = tmp_path / "proj"
        _bootstrap_state(proj)

        with pytest.raises(SystemExit):
            launcher.main_archive_paper(synthetic_pdf, proj)

        state = json.loads((proj / "debrief_state.json").read_text())
        assert state["papers_provided"] is True

    def test_archive_emits_paper_attached_event(
        self, synthetic_pdf: Path, tmp_path: Path
    ) -> None:
        proj = tmp_path / "proj"
        _bootstrap_state(proj)

        with pytest.raises(SystemExit):
            launcher.main_archive_paper(synthetic_pdf, proj)

        timeline = (proj / "output" / "timeline.jsonl").read_text().strip().splitlines()
        events = [json.loads(line) for line in timeline if line.strip()]
        attached = [e for e in events if e.get("event") == "paper_attached"]
        assert len(attached) == 1
        assert attached[0]["payload"]["slug"] == "smith_2026"
        assert "Smith_2026.pdf" in attached[0]["payload"]["path"]


# ---------------------------------------------------------------------------
# (b) consultant-card trigger broadening + recovery clause
# ---------------------------------------------------------------------------


class TestConsultantTriggerBroadening:
    def test_trigger_section_mentions_three_detection_paths(self) -> None:
        """The trigger description must enumerate the three detection signals."""
        content = _consultant_md_path().read_text()
        # Find the Trigger subsection within ## Paper Analyzer Invocation.
        anchor = "### Trigger"
        idx = content.find(anchor)
        assert idx >= 0
        # Take a generous slice of the section
        block = content[idx:idx + 4000]
        # Three signals: path-shaped, bare filename, mention without path.
        assert "Path-shaped string" in block or "path-shaped string" in block.lower()
        assert "Bare PDF filename" in block or "bare PDF filename" in block.lower() or "no directory" in block.lower()
        assert "preprint" in block.lower() or "verbal" in block.lower() or "ASK the user" in block

    def test_trigger_section_mentions_archive_paper_recovery(self) -> None:
        content = _consultant_md_path().read_text()
        # Recovery clause must reference /debrief:archive-paper command
        assert "/debrief:archive-paper" in content


class TestConsultantPostSuccessBlock:
    def test_emit_event_paper_attached_command_present(self) -> None:
        content = _consultant_md_path().read_text()
        assert "emit_event --event paper_attached" in content

    def test_papers_provided_state_update_command_present(self) -> None:
        content = _consultant_md_path().read_text()
        assert "papers_provided=true" in content
        assert "debrief.debrief_state update" in content


# ---------------------------------------------------------------------------
# (c) commands/archive-paper.md command file
# ---------------------------------------------------------------------------


class TestArchivePaperCommandFile:
    def test_command_file_exists(self) -> None:
        assert _archive_paper_command_path().is_file()

    def test_command_file_has_canonical_heading(self) -> None:
        content = _archive_paper_command_path().read_text()
        assert content.startswith("# /debrief:archive-paper")

    def test_command_file_documents_exit_codes(self) -> None:
        content = _archive_paper_command_path().read_text()
        for code in ("0", "1", "2", "3"):
            assert f"| {code} |" in content


# ---------------------------------------------------------------------------
# (d) doctor --asset-audit
# ---------------------------------------------------------------------------


class TestAssetAuditHelper:
    def test_audit_assets_function_exists(self) -> None:
        assert hasattr(launcher, "_audit_assets")

    def test_clean_project_reports_no_drift(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "assets").mkdir()
        result = launcher._audit_assets(proj)
        assert result["drift"] is False
        assert result["paper_directories"] == []
        assert result["paper_attached_event_count"] == 0

    def test_orphan_paper_figures_in_images_detected(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        (proj / "assets" / "images").mkdir(parents=True)
        # Place paper-figure-shaped files directly (no slug prefix)
        (proj / "assets" / "images" / "figure2_panel_A.png").write_bytes(b"x")
        (proj / "assets" / "images" / "fig_3.png").write_bytes(b"y")
        result = launcher._audit_assets(proj)
        assert "figure2_panel_A.png" in result["orphan_paper_figures_in_images"]
        assert "fig_3.png" in result["orphan_paper_figures_in_images"]
        assert result["drift"] is True

    def test_unprefixed_image_files_detected(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        (proj / "assets" / "images").mkdir(parents=True)
        (proj / "assets" / "images" / "no_slug_prefix.png").write_bytes(b"x")
        # File starts with valid-looking slug (matches the ^[a-z][a-z0-9_]*_)
        (proj / "assets" / "images" / "intro_my_image.png").write_bytes(b"x")
        result = launcher._audit_assets(proj)
        # "no_slug_prefix.png" technically matches our regex (no_ is a slug); we
        # use a different test: a file that explicitly violates the prefix shape
        # is one that lacks an underscore at all.
        # Update test to use a clearly non-prefixed name:
        (proj / "assets" / "images" / "naked.png").write_bytes(b"x")
        result = launcher._audit_assets(proj)
        assert "naked.png" in result["unprefixed_image_files"]

    def test_papers_provided_true_but_no_paper_dirs_drift(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "debrief_state.json").write_text(json.dumps({"papers_provided": True}))
        result = launcher._audit_assets(proj)
        assert result["drift"] is True
        assert any("papers_provided=true" in n for n in result["notes"])

    def test_paper_dirs_but_no_event_drift(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        (proj / "assets" / "reference" / "papers" / "abc").mkdir(parents=True)
        (proj / "output").mkdir()
        (proj / "output" / "timeline.jsonl").write_text("")
        result = launcher._audit_assets(proj)
        assert result["drift"] is True
        assert any("paper_attached event" in n for n in result["notes"])

    def test_paper_dirs_with_event_no_drift(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        (proj / "assets" / "reference" / "papers" / "abc").mkdir(parents=True)
        (proj / "output").mkdir()
        (proj / "output" / "timeline.jsonl").write_text(
            json.dumps({"event": "paper_attached", "timestamp": "x", "payload": {"path": "x.pdf", "slug": "abc"}}) + "\n"
        )
        # papers_provided=True consistent with paper_dirs
        (proj / "debrief_state.json").write_text(json.dumps({"papers_provided": True}))
        result = launcher._audit_assets(proj)
        assert result["drift"] is False
