# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-87: metadata heuristics + crop fallback.

Before BUG-AUDIT-87:
  - ``extract_paper_metadata`` always set ``journal=None``; ``title`` and
    ``authors`` came only from the PDF's metadata dict, which is often
    empty or producer-noise (e.g., "LaTeX with hyperref"). This made
    REQ-CONSULT-18's citation line ("Figure from <Authors>, <Year>,
    <Journal>") render "Figure from Unknown, YYYY, Unknown" in most cases.
  - ``crop_whitespace`` constructed a sub-pixmap via
    ``pixmap.set_origin(0, 0).__class__(pixmap, rect)``, which silently
    no-cropped on PyMuPDF versions where ``set_origin`` returns ``None``.

These tests pin: (a) heuristic title extraction when PDF metadata is
absent or filename-shaped; (b) heuristic author extraction when PDF
metadata is absent or producer-noise; (c) journal extraction from the
``subject`` field with a permissive page-1 fragment scan as fallback;
(d) crop_whitespace using ``fitz.Pixmap(src, irect)`` directly.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

_HERE = Path(__file__).resolve().parent
_WORKSPACE_STUB = _HERE.parent.parent / "src" / "unit_12"
if _WORKSPACE_STUB.is_dir() and str(_WORKSPACE_STUB) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_STUB))

try:
    paper_analyzer = importlib.import_module("paper_analyzer")
except ModuleNotFoundError:  # pragma: no cover
    paper_analyzer = importlib.import_module("debrief.paper_analyzer")


def _doc_with_metadata(metadata: dict[str, Any]) -> MagicMock:
    """Build a mock fitz Document whose `metadata` attr is the given dict."""
    doc = MagicMock()
    doc.metadata = metadata
    doc.__enter__ = MagicMock(return_value=doc)
    doc.__exit__ = MagicMock(return_value=False)
    return doc


# ===========================================================================
# Title heuristics
# ===========================================================================


class TestTitleHeuristic:
    def test_pdf_metadata_title_used_when_present(self, tmp_path: Path) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({"title": "A Long and Specific Paper Title"})
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [])
        assert result["title"] == "A Long and Specific Paper Title"

    def test_filename_shaped_metadata_title_falls_through_to_heuristic(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        # Filename-shaped: ends with .pdf
        doc = _doc_with_metadata({"title": "smith_2024_neuron.pdf"})
        page1 = (
            "Hierarchical Coding of Spatial Memory in the Hippocampus\n"
            "John Smith, Anne Jones, and Carla Wong\n"
            "Department of Neuroscience\n"
            "ABSTRACT\n"
            "We show that activation reveals hierarchy.\n"
        )
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        assert result["title"] == (
            "Hierarchical Coding of Spatial Memory in the Hippocampus"
        )

    def test_underscore_only_metadata_title_treated_as_filename(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({"title": "draft_v3"})  # no spaces, has _
        page1 = "A Robust Method for Joint Inference of Phenotype and Genotype\n"
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        assert result["title"] == (
            "A Robust Method for Joint Inference of Phenotype and Genotype"
        )

    def test_heuristic_skips_all_uppercase_section_headers(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({})
        page1 = (
            "ABSTRACT\n"
            "INTRODUCTION TO THE STUDY\n"
            "A Robust Method for Joint Inference of Phenotype and Genotype\n"
        )
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        assert result["title"] == (
            "A Robust Method for Joint Inference of Phenotype and Genotype"
        )

    def test_heuristic_skips_numbered_section_headings(self, tmp_path: Path) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({})
        page1 = (
            "1. Introduction to the basic concepts of memory\n"
            "Beautifully Concise Title for the Paper Itself\n"
        )
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        assert result["title"] == (
            "Beautifully Concise Title for the Paper Itself"
        )

    def test_no_plausible_title_yields_none(self, tmp_path: Path) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({})
        # All lines too short, all-caps, or numbered
        page1 = "ABSTRACT\n1. Intro\nshort\n"
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        assert result["title"] is None


# ===========================================================================
# Authors heuristic
# ===========================================================================


class TestAuthorsHeuristic:
    def test_pdf_metadata_authors_used_when_present(self, tmp_path: Path) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({"author": "Smith, J. and Jones, A."})
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [])
        assert result["authors"] == "Smith, J. and Jones, A."

    def test_producer_noise_falls_through_to_heuristic(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({"author": "LaTeX with hyperref"})
        page1 = (
            "A Robust Method for Joint Inference of Phenotype\n"
            "John Smith, Anne Jones, and Carla Wong\n"
            "ABSTRACT\n"
        )
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        assert result["authors"] == "John Smith, Anne Jones, and Carla Wong"

    def test_heuristic_finds_ampersand_separated_authors(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({})
        page1 = (
            "A Distinctive Title For This Paper Right Here\n"
            "John Smith and Anne Jones\n"
        )
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        assert result["authors"] == "John Smith and Anne Jones"

    def test_heuristic_rejects_lines_with_section_keywords(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({})
        page1 = (
            "A Distinctive Title For This Paper Right Here\n"
            "Abstract: We received the manuscript and reviewed the figure.\n"
        )
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        # The "abstract/received/figure" line is rejected; no authors found
        assert result["authors"] is None


# ===========================================================================
# Journal heuristic
# ===========================================================================


class TestJournalHeuristic:
    def test_subject_field_used_when_present(self, tmp_path: Path) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({"subject": "Nature Neuroscience"})
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [])
        assert result["journal"] == "Nature Neuroscience"

    def test_subject_with_producer_noise_falls_through(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({"subject": "LaTeX with hyperref"})
        page1 = "Cell Reports, 2026\n"
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        assert result["journal"] == "Cell Reports, 2026"

    def test_page_one_fragment_scan_finds_recognizable_journal(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({})
        page1 = "PLOS Biology 2026\nA Distinctive Title Right Here\n"
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        assert result["journal"] == "PLOS Biology 2026"

    def test_no_signal_yields_none_journal(self, tmp_path: Path) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({})
        page1 = "A Distinctive Title Right Here\nJohn Smith and Anne Jones\n"
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        assert result["journal"] is None  # conservative: prefer None over guess


# ===========================================================================
# All-None / robustness
# ===========================================================================


class TestAllFieldsAbsent:
    def test_empty_metadata_and_no_pages_yields_all_none(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({})
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [])
        assert result == {
            "title": None,
            "authors": None,
            "journal": None,
            "year": None,
        }

    def test_year_extraction_independent_of_other_fields(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _doc_with_metadata({})
        page1 = "Some text without title-like content. Published 2026.\n"
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_paper_metadata(pdf, [page1])
        assert result["year"] == "2026"


# ===========================================================================
# Crop fitz fallback (BUG-AUDIT-87 part b)
# ===========================================================================


class TestCropFitzFallback:
    def _make_pixmap_with_content(self) -> MagicMock:
        # 3-channel 4x4 image, black square in middle of white field
        white = bytes([255, 255, 255])
        black = bytes([0, 0, 0])
        rows: list[bytes] = []
        for y in range(4):
            row = b""
            for x in range(4):
                row += black if 1 <= x <= 2 and 1 <= y <= 2 else white
            rows.append(row)
        pm = MagicMock()
        pm.width = 4
        pm.height = 4
        pm.n = 3
        pm.samples = b"".join(rows)
        return pm

    def test_crop_uses_fitz_pixmap_constructor_directly(self) -> None:
        pm = self._make_pixmap_with_content()
        captured: list[Any] = []

        class _FakeIRect:
            def __init__(self, *a: int) -> None:
                self.coords = a

        def _pixmap_factory(src: Any, rect: Any) -> Any:
            captured.append((src, rect))
            return MagicMock()

        fake_fitz = MagicMock()
        fake_fitz.IRect = _FakeIRect
        fake_fitz.Pixmap = _pixmap_factory

        with patch.dict(sys.modules, {"fitz": fake_fitz}):
            result = paper_analyzer.crop_whitespace(pm)
        assert len(captured) == 1, "fitz.Pixmap must be called exactly once"
        src, rect = captured[0]
        assert src is pm
        assert isinstance(rect, _FakeIRect)
        # rect should be (1, 1, 3, 3) — content bbox + 1 in max coords
        assert rect.coords == (1, 1, 3, 3)
        assert result is not pm  # cropped result should be the new pixmap

    def test_crop_falls_back_to_original_when_fitz_constructor_raises(
        self,
    ) -> None:
        pm = self._make_pixmap_with_content()

        def _raising_pixmap(src: Any, rect: Any) -> Any:
            raise RuntimeError("simulated fitz failure")

        fake_fitz = MagicMock()
        fake_fitz.IRect = lambda *a: None
        fake_fitz.Pixmap = _raising_pixmap

        with patch.dict(sys.modules, {"fitz": fake_fitz}):
            result = paper_analyzer.crop_whitespace(pm)
        assert result is pm  # fall-through preserves the original

    def test_all_white_image_returns_original_unchanged(self) -> None:
        pm = MagicMock()
        pm.width = 3
        pm.height = 3
        pm.n = 3
        pm.samples = bytes([255] * (3 * 3 * 3))  # all white
        result = paper_analyzer.crop_whitespace(pm)
        assert result is pm  # BC-12.7 unchanged
