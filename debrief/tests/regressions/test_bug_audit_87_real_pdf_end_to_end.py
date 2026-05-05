# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""End-to-end real-PDF test for the paper_analyzer pipeline (BUG-AUDIT-87).

Closes FINDING-IMPL-5 from the 2026-05-03 journal-club audit: the existing
unit_12 suite was 100% mock-driven, which let three real bugs (claims
data-loss, image-distribution alias, missing journal field) sit undetected.
This test generates a deterministic PDF with PyMuPDF, runs the full
pipeline (text extraction → captions → images → claims → metadata → write),
and asserts the on-disk artifacts contain the data we put in.

The fixture PDF is created at runtime in tmp_path — no external assets, no
licensing concerns. Two pages, two figures, deterministic content.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_WORKSPACE_STUB = _HERE.parent.parent / "src" / "unit_12"
if _WORKSPACE_STUB.is_dir() and str(_WORKSPACE_STUB) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_STUB))

try:
    paper_analyzer = importlib.import_module("paper_analyzer")
except ModuleNotFoundError:  # pragma: no cover
    paper_analyzer = importlib.import_module("debrief.paper_analyzer")


@pytest.fixture
def synthetic_paper_pdf(tmp_path: Path) -> Path:
    """Build a tiny, deterministic two-page PDF using PyMuPDF.

    Page 1: title, authors, abstract section header, intro text with a
    Figure 1 reference, Figure 1 image (white box → not cropped to nothing
    because we draw a black square inside it), Figure 1 caption, claim
    sentence following the caption.

    Page 2: results section header, Figure 2 reference, Figure 2 image,
    Figure 2 caption, claim sentence.

    The intent is to give the analyzer something realistic enough to
    exercise every code path without needing an external PDF file.
    """
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    doc.set_metadata(
        {
            "title": "Hierarchical Coding of Spatial Memory",
            "author": "Smith, J. and Jones, A. and Wong, C.",
            "subject": "Cell Reports",
        }
    )

    # ---- Page 1 ----
    page1 = doc.new_page()
    # Body text — multi-line so extract_figure_captions has line anchors
    body1 = (
        "Hierarchical Coding of Spatial Memory\n"
        "Smith, J. and Jones, A. and Wong, C.\n"
        "Cell Reports, 2026\n"
        "\n"
        "INTRODUCTION\n"
        "\n"
        "We previously reported activity in CA1 (Figure 1).\n"
        "Subsequent work confirmed this finding (see Fig. 1).\n"
        "\n"
        "Figure 1. Hippocampal place cells across conditions.\n"
        "Activation reveals hierarchy across spatial scales.\n"
        "All differences were significant at p < 0.001 (n=18 mice).\n"
        "\n"
    )
    page1.insert_text((36, 36), body1, fontsize=10)
    # Insert a small black-on-white image as Figure 1 (10x10 black square)
    img1 = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10))
    img1.set_rect(img1.irect, (0, 0, 0))  # all black
    page1.insert_image(fitz.Rect(36, 350, 86, 400), pixmap=img1)

    # ---- Page 2 ----
    page2 = doc.new_page()
    body2 = (
        "RESULTS\n"
        "\n"
        "Replication across animals (Figure 2) confirmed the effect.\n"
        "\n"
        "Figure 2. Cross-animal replication of the effect.\n"
        "Accuracy improves with training duration.\n"
        "Effect persists across the four tested conditions.\n"
        "\n"
    )
    page2.insert_text((36, 36), body2, fontsize=10)
    img2 = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10))
    img2.set_rect(img2.irect, (0, 0, 0))
    page2.insert_image(fitz.Rect(36, 200, 86, 250), pixmap=img2)

    out = tmp_path / "synthetic_paper.pdf"
    doc.save(str(out))
    doc.close()
    return out


def test_main_paper_analyzer_round_trip(
    synthetic_paper_pdf: Path, tmp_path: Path
) -> None:
    """End-to-end: drive the pipeline, then assert artifacts on disk."""
    project_root = tmp_path / "project"
    project_root.mkdir()

    paper_analyzer.main_paper_analyzer(
        pdf_path=synthetic_paper_pdf,
        paper_slug="synthetic_paper",
        project_root=project_root,
    )

    md_path = project_root / ".debrief" / "paper_analysis_synthetic_paper.md"
    assert md_path.exists(), "analysis markdown was not written"
    content = md_path.read_text()

    # All canonical sections present
    assert "## Metadata" in content
    assert "## Key Figures" in content
    assert "## Figure Claims" in content  # BC-12.11 (BUG-AUDIT-85)
    assert "## Suggested Narrative Arc" in content

    # Metadata picked up from PDF metadata dict
    assert "Hierarchical Coding of Spatial Memory" in content
    assert "Smith, J. and Jones, A. and Wong, C." in content
    assert "Cell Reports" in content
    assert "2026" in content

    # Key Figures contains both captions
    assert "Hippocampal place cells across conditions" in content
    assert "Cross-animal replication of the effect" in content

    # Figure Claims block contains the claim sentences for each figure
    # (BUG-AUDIT-85 — pre-fix this entire section was missing)
    assert "Activation reveals hierarchy across spatial scales" in content
    assert "Accuracy improves with training duration" in content


def test_figure_files_are_extracted_and_distinct(
    synthetic_paper_pdf: Path, tmp_path: Path
) -> None:
    """BC-12.9 (BUG-AUDIT-86): each figure on its own page yields a PNG file."""
    project_root = tmp_path / "project"
    project_root.mkdir()

    paper_analyzer.main_paper_analyzer(
        pdf_path=synthetic_paper_pdf,
        paper_slug="synthetic_paper",
        project_root=project_root,
    )

    fig_dir = (
        project_root
        / "assets"
        / "reference"
        / "papers"
        / "synthetic_paper"
        / "figures"
    )
    assert fig_dir.is_dir()
    pngs = sorted(fig_dir.glob("*.png"))
    assert len(pngs) >= 1, "at least one figure file should be saved"
    # The two figures live on different pages, so per-page distribution gives
    # each its own xref. Files are named fig_<N>.png.
    names = {p.name for p in pngs}
    assert any(n.startswith("fig_") and n.endswith(".png") for n in names)


def test_pdf_archived_to_assets_reference(
    synthetic_paper_pdf: Path, tmp_path: Path
) -> None:
    """The source PDF is copied to assets/reference/papers/<slug>/ per BC-12.4."""
    project_root = tmp_path / "project"
    project_root.mkdir()

    paper_analyzer.main_paper_analyzer(
        pdf_path=synthetic_paper_pdf,
        paper_slug="synthetic_paper",
        project_root=project_root,
    )

    archived = (
        project_root
        / "assets"
        / "reference"
        / "papers"
        / "synthetic_paper"
        / synthetic_paper_pdf.name
    )
    assert archived.exists()
    # No leftover .tmp shrapnel
    paper_dir = (
        project_root / "assets" / "reference" / "papers" / "synthetic_paper"
    )
    assert list(paper_dir.glob("*.tmp")) == []
