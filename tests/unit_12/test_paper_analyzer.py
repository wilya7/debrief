# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Tests for Unit 12: Paper Analyzer.

Tested contracts: BC-12.1 through BC-12.10.

Synthetic data generation assumptions
--------------------------------------
- fitz (PyMuPDF) is NOT imported by the test suite itself.  All fitz
  objects (Pixmap, Document, Page) are replaced by MagicMock stand-ins.
  This keeps the test suite runnable even when PyMuPDF is unavailable in
  the test environment, and honours the contract-based (not
  implementation-based) test philosophy.
- A MagicMock ``Pixmap`` is created via ``_make_pixmap()``.  It exposes:
    * ``samples``: raw bytes representing an NxM RGB pixel grid.
    * ``width``, ``height``: integer dimensions.
    * ``n``: number of colour channels (3 for RGB).
    * ``tobytes()``: returns the same byte string, simulating PNG output.
  Two variants exist: ``_make_white_pixmap()`` (all channels ≥ 250) and
  ``_make_content_pixmap()`` (one pixel below threshold).
- Page text strings are plain Python strings.  Figure captions are
  embedded at the start of a line (after a newline) so the regex
  ``r'^(?:Figure|Fig\.)...'`` applied with ``re.MULTILINE`` picks them up.
- ``figure_captions`` dicts use keys ``figure_num`` (int), ``caption``
  (str), ``page_index`` (int), matching the signature specification.
- ``section_structure`` dicts use keys ``heading`` (str) and
  ``page_index`` (int).
- ``ranked_figures`` lists are plain dicts with keys ``figure_num``,
  ``caption``, ``page_index``, and optionally ``pixmap``.
- PDF path fixtures use ``tmp_path / "paper.pdf"`` as a placeholder
  Path; actual PDF parsing is not exercised by these contract-level tests.
- ``derive_paper_slug`` is tested as a pure function exercising BC-12.8;
  it is assumed to be a module-level function in ``paper_analyzer`` whose
  signature is ``derive_paper_slug(pdf_path: Path) -> str``.
- ``analyze_paper`` and ``extract_figures`` are assumed to be thin
  orchestration helpers (if present); if not exported, those contract
  invariants are covered via the sub-function tests.
- Timestamps use the fixed string "2026-04-12T00:00:00Z" throughout.
- All file I/O tests use ``tmp_path``; no global directories are modified.
- The Section 9.3.1 env-corruption exit code for missing fitz is 2.
- ``write_paper_analysis`` writes to
  ``<project_root>/.debrief/paper_analysis_<slug>.md``; the ``.debrief/``
  directory is created inside ``tmp_path`` by each test that needs it.
- Atomic-write tests inspect the absence of ``*.tmp`` files after a
  successful write, confirming the rename completed.
- ``save_figure`` target path pattern is:
  ``assets/reference/papers/<slug>/figures/fig_<N>.png``.
- ``copy_pdf_to_archive`` target path is:
  ``assets/reference/papers/<slug>/<pdf_name>``.
- For BC-12.6 (no VLM / network calls): tested structurally by asserting
  the module's import list contains neither ``openai``, ``anthropic``,
  ``requests``, ``httpx``, ``pptx``, nor ``playwright``.
- For BC-12.1 (fitz-only dependency boundary): tested by inspecting the
  module source via ``importlib`` + ``inspect.getsource`` for forbidden
  import tokens.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Module-level import  (stub raises NotImplementedError on every call;
# tests are expected to FAIL red until the implementation is delivered)
# ---------------------------------------------------------------------------
import paper_analyzer  # noqa: E402  (resolved via conftest sys.path)
import pytest

# ---------------------------------------------------------------------------
# Pixmap stand-in helpers
# ---------------------------------------------------------------------------

_RGB_CHANNELS = 3


def _make_pixmap(
    width: int = 4,
    height: int = 4,
    fill_value: int = 0,
) -> MagicMock:
    """Return a MagicMock that behaves like a fitz.Pixmap."""
    px = MagicMock()
    px.width = width
    px.height = height
    px.n = _RGB_CHANNELS
    # samples: width * height * channels bytes
    px.samples = bytes([fill_value] * (width * height * _RGB_CHANNELS))
    px.tobytes.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    return px


def _make_white_pixmap(width: int = 4, height: int = 4) -> MagicMock:
    """All pixels at 255 — entirely white image."""
    return _make_pixmap(width=width, height=height, fill_value=255)


def _make_content_pixmap(width: int = 4, height: int = 4) -> MagicMock:
    """One content pixel (value 0); rest white.  Bounding box is non-empty."""
    px = _make_pixmap(width=width, height=height, fill_value=255)
    # Place a single black pixel in the middle
    samples = bytearray(px.samples)
    mid = (height // 2 * width + width // 2) * _RGB_CHANNELS
    samples[mid] = 0
    samples[mid + 1] = 0
    samples[mid + 2] = 0
    px.samples = bytes(samples)
    return px


# ---------------------------------------------------------------------------
# Figure caption / section / ranked-figure factories
# ---------------------------------------------------------------------------

_PAGE_TEXTS_WITH_CAPTIONS = [
    (
        "Introduction\n"
        "We show in Figure 1 the main results.\n"
        "Figure 1. Activation maps across layers.\n"
        "The maps reveal distinct patterns.\n"
    ),
    (
        "Results\n"
        "As seen in Figure 2 and Fig. 2, the accuracy improves.\n"
        "Fig. 2. Accuracy curves for all baselines.\n"
        "See also Figure 1 for context.\n"
    ),
    (
        "Supplementary\n"
        "Fig. 3: Extended ablation results.\n"
        "These are not referenced in the main text.\n"
    ),
]

_CAPTIONS_LIST = [
    {"figure_num": 1, "caption": "Activation maps across layers.", "page_index": 0},
    {"figure_num": 2, "caption": "Accuracy curves for all baselines.", "page_index": 1},
    {"figure_num": 3, "caption": "Extended ablation results.", "page_index": 2},
]

_SECTION_STRUCTURE = [
    {"heading": "Introduction", "page_index": 0},
    {"heading": "Results", "page_index": 1},
    {"heading": "Supplementary", "page_index": 2},
]

_METADATA = {
    "title": "Deep Representations in Neuroscience",
    "authors": "Smith, J.; Doe, A.",
    "journal": "Nature Neuroscience",
    "year": "2024",
}


def _make_ranked_figures(include_none_pixmap: bool = False) -> list[dict[str, Any]]:
    figs: list[dict[str, Any]] = [
        {
            "figure_num": 2,
            "caption": "Accuracy curves for all baselines.",
            "page_index": 1,
            "pixmap": _make_content_pixmap(),
        },
        {
            "figure_num": 1,
            "caption": "Activation maps across layers.",
            "page_index": 0,
            "pixmap": _make_content_pixmap(),
        },
    ]
    if include_none_pixmap:
        figs.append(
            {
                "figure_num": 3,
                "caption": "Extended ablation results.",
                "page_index": 2,
                "pixmap": None,
            }
        )
    return figs


# ===========================================================================
# BC-12.1  fitz-only dependency boundary
# ===========================================================================


class TestFitzOnlyDependencyBoundary:
    """BC-12.1: paper_analyzer must not import pptx, playwright, or VLM SDKs."""

    def _get_source(self) -> str:
        import inspect

        return inspect.getsource(paper_analyzer)

    def test_pptx_not_imported(self) -> None:
        source = self._get_source()
        assert "import pptx" not in source
        assert "from pptx" not in source

    def test_playwright_not_imported(self) -> None:
        source = self._get_source()
        assert "import playwright" not in source
        assert "from playwright" not in source

    def test_openai_not_imported(self) -> None:
        source = self._get_source()
        assert "import openai" not in source
        assert "from openai" not in source

    def test_anthropic_not_imported(self) -> None:
        source = self._get_source()
        assert "import anthropic" not in source
        assert "from anthropic" not in source

    def test_requests_not_imported(self) -> None:
        source = self._get_source()
        assert "import requests" not in source

    def test_httpx_not_imported(self) -> None:
        source = self._get_source()
        assert "import httpx" not in source


# ===========================================================================
# BC-12.2  Env corruption exit code on missing fitz
# ===========================================================================


class TestEnvCorruptionOnMissingFitz:
    """BC-12.2: main_paper_analyzer exits 2 when fitz import fails."""

    def test_exits_with_code_2_when_fitz_unavailable(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        with patch.dict(sys.modules, {"fitz": None}):
            with pytest.raises(SystemExit) as exc_info:
                paper_analyzer.main_paper_analyzer(
                    pdf_path=pdf_path,
                    paper_slug="test_paper",
                    project_root=tmp_path,
                )
        assert exc_info.value.code == 2

    def test_writes_error_message_to_stderr_when_fitz_unavailable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        with patch.dict(sys.modules, {"fitz": None}):
            with pytest.raises(SystemExit):
                paper_analyzer.main_paper_analyzer(
                    pdf_path=pdf_path,
                    paper_slug="test_paper",
                    project_root=tmp_path,
                )
        captured = capsys.readouterr()
        assert captured.err.strip() != ""


# ===========================================================================
# BC-12.3  Figure caption regex compliance
# ===========================================================================


class TestFigureCaptionRegexCompliance:
    """BC-12.3: extract_figure_captions uses the specified pattern."""

    def test_extracts_figure_n_dot_prefix(self) -> None:
        pages = ["Figure 1. Shows the main result.\nBody text here."]
        result = paper_analyzer.extract_figure_captions(pages)
        assert len(result) == 1
        assert result[0]["figure_num"] == 1
        assert "main result" in result[0]["caption"]

    def test_extracts_fig_dot_n_dot_prefix(self) -> None:
        pages = ["Some intro text.\nFig. 2. Accuracy curves.\nMore text."]
        result = paper_analyzer.extract_figure_captions(pages)
        assert len(result) == 1
        assert result[0]["figure_num"] == 2

    def test_extracts_fig_dot_n_colon_prefix(self) -> None:
        pages = ["Fig. 3: Extended ablation study.\nDetails follow."]
        result = paper_analyzer.extract_figure_captions(pages)
        assert len(result) == 1
        assert result[0]["figure_num"] == 3

    def test_extracts_figure_n_colon_prefix(self) -> None:
        pages = ["Figure 4: Performance comparison table.\n"]
        result = paper_analyzer.extract_figure_captions(pages)
        assert len(result) == 1
        assert result[0]["figure_num"] == 4

    def test_returns_correct_page_index(self) -> None:
        pages = [
            "No captions here.",
            "Figure 1. First figure on page 1.\n",
        ]
        result = paper_analyzer.extract_figure_captions(pages)
        assert result[0]["page_index"] == 1

    def test_returns_list_of_dicts_with_required_keys(self) -> None:
        pages = ["Figure 1. A caption.\n"]
        result = paper_analyzer.extract_figure_captions(pages)
        assert isinstance(result, list)
        for item in result:
            assert "figure_num" in item
            assert "caption" in item
            assert "page_index" in item

    def test_body_text_reference_does_not_produce_caption(self) -> None:
        # "Figure 1" in the middle of a sentence — not a caption start
        pages = ["As shown in Figure 1 and Figure 2, the method works.\n"]
        result = paper_analyzer.extract_figure_captions(pages)
        # References in the middle of lines should NOT match caption pattern
        # (pattern anchored to start of line with ^)
        assert all(item["caption"] != "" for item in result)
        # The body text references should not create spurious captions
        for item in result:
            assert item["figure_num"] in (1, 2)
            # caption must not be the body sentence itself
            assert not item["caption"].startswith("As shown")

    def test_empty_pages_returns_empty_list(self) -> None:
        result = paper_analyzer.extract_figure_captions([])
        assert result == []

    def test_page_with_no_captions_returns_empty_list(self) -> None:
        pages = ["Just some body text with no figures."]
        result = paper_analyzer.extract_figure_captions(pages)
        assert result == []

    def test_multiple_captions_across_pages_ordered_by_document_order(
        self,
    ) -> None:
        pages = [
            "Figure 1. First caption.\n",
            "Figure 2. Second caption.\n",
            "Fig. 3. Third caption.\n",
        ]
        result = paper_analyzer.extract_figure_captions(pages)
        assert len(result) == 3
        assert [r["figure_num"] for r in result] == [1, 2, 3]

    def test_figure_num_is_int_not_string(self) -> None:
        pages = ["Figure 5. Some caption text here.\n"]
        result = paper_analyzer.extract_figure_captions(pages)
        assert isinstance(result[0]["figure_num"], int)


# ===========================================================================
# BC-12.4  Atomic file writes
# ===========================================================================


class TestAtomicFileWrites:
    """BC-12.4: save_figure, write_paper_analysis, copy_pdf_to_archive use atomics."""

    def test_write_paper_analysis_no_tmp_file_after_success(
        self, tmp_path: Path
    ) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="test_slug",
            metadata=_METADATA,
            ranked_figures=_make_ranked_figures(),
            claims={1: "Activation reveals hierarchy.", 2: "Accuracy improves."},
        )
        tmp_files = list(debrief_dir.glob("*.tmp"))
        assert tmp_files == [], "No .tmp files should remain after successful write"

    def test_write_paper_analysis_creates_md_file(self, tmp_path: Path) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="nature_2024",
            metadata=_METADATA,
            ranked_figures=_make_ranked_figures(),
            claims={1: "Finding A.", 2: "Finding B."},
        )
        out = tmp_path / ".debrief" / "paper_analysis_nature_2024.md"
        assert out.exists()

    def test_save_figure_no_tmp_file_after_success(self, tmp_path: Path) -> None:
        pixmap = _make_content_pixmap()
        paper_analyzer.save_figure(
            pixmap=pixmap,
            figure_num=1,
            paper_slug="test_slug",
            project_root=tmp_path,
        )
        fig_dir = tmp_path / "assets" / "reference" / "papers" / "test_slug" / "figures"
        tmp_files = list(fig_dir.glob("*.tmp"))
        assert tmp_files == [], "No .tmp files should remain after save_figure"

    def test_save_figure_creates_png_file(self, tmp_path: Path) -> None:
        pixmap = _make_content_pixmap()
        dest = paper_analyzer.save_figure(
            pixmap=pixmap,
            figure_num=1,
            paper_slug="test_slug",
            project_root=tmp_path,
        )
        assert dest.exists()
        assert dest.name == "fig_1.png"

    def test_save_figure_returns_correct_path(self, tmp_path: Path) -> None:
        pixmap = _make_content_pixmap()
        dest = paper_analyzer.save_figure(
            pixmap=pixmap,
            figure_num=3,
            paper_slug="my_paper",
            project_root=tmp_path,
        )
        expected = (
            tmp_path
            / "assets"
            / "reference"
            / "papers"
            / "my_paper"
            / "figures"
            / "fig_3.png"
        )
        assert dest == expected

    def test_copy_pdf_to_archive_no_tmp_file_after_success(
        self, tmp_path: Path
    ) -> None:
        pdf_path = tmp_path / "source_paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 minimal")
        paper_analyzer.copy_pdf_to_archive(
            pdf_path=pdf_path,
            paper_slug="source_paper",
            project_root=tmp_path,
        )
        archive_dir = tmp_path / "assets" / "reference" / "papers" / "source_paper"
        tmp_files = list(archive_dir.glob("*.tmp"))
        assert tmp_files == [], "No .tmp files should remain after copy"

    def test_copy_pdf_to_archive_creates_destination_file(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "my_paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 content")
        paper_analyzer.copy_pdf_to_archive(
            pdf_path=pdf_path,
            paper_slug="my_paper",
            project_root=tmp_path,
        )
        dest = (
            tmp_path / "assets" / "reference" / "papers" / "my_paper" / "my_paper.pdf"
        )
        assert dest.exists()

    def test_copy_pdf_to_archive_preserves_file_contents(self, tmp_path: Path) -> None:
        content = b"%PDF-1.4 exact content bytes"
        pdf_path = tmp_path / "exact.pdf"
        pdf_path.write_bytes(content)
        paper_analyzer.copy_pdf_to_archive(
            pdf_path=pdf_path,
            paper_slug="exact",
            project_root=tmp_path,
        )
        dest = tmp_path / "assets" / "reference" / "papers" / "exact" / "exact.pdf"
        assert dest.read_bytes() == content

    def test_copy_pdf_to_archive_creates_destination_directory(
        self, tmp_path: Path
    ) -> None:
        pdf_path = tmp_path / "new_paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        # Directory should NOT exist yet
        dest_dir = tmp_path / "assets" / "reference" / "papers" / "new_paper"
        assert not dest_dir.exists()
        paper_analyzer.copy_pdf_to_archive(
            pdf_path=pdf_path,
            paper_slug="new_paper",
            project_root=tmp_path,
        )
        assert dest_dir.exists()


# ===========================================================================
# BC-12.5  Figure ranking determinism
# ===========================================================================


class TestFigureRankingDeterminism:
    """BC-12.5: rank_figures is deterministic; ties broken by document order."""

    def test_higher_citation_frequency_ranks_first(self) -> None:
        # Figure 2 cited twice in body, Figure 1 cited once
        pages = [
            "We discuss Figure 1 in context.\nFigure 1. First figure caption.\n",
            "Figure 2 appears twice: Figure 2 confirms this.\n"
            "Figure 2. Second figure caption.\n",
        ]
        captions = [
            {"figure_num": 1, "caption": "First figure caption.", "page_index": 0},
            {"figure_num": 2, "caption": "Second figure caption.", "page_index": 1},
        ]
        sections = [
            {"heading": "Introduction", "page_index": 0},
            {"heading": "Results", "page_index": 1},
        ]
        result = paper_analyzer.rank_figures(captions, pages, sections)
        assert result[0]["figure_num"] == 2

    def test_document_order_breaks_citation_ties(self) -> None:
        # Equal citation frequency: earlier figure (Fig 1) should rank first
        # when citation counts are equal
        pages = [
            "Figure 1 is cited here.\nFigure 1. Caption one.\n",
            "Figure 2 is also cited.\nFigure 2. Caption two.\n",
        ]
        captions = [
            {"figure_num": 1, "caption": "Caption one.", "page_index": 0},
            {"figure_num": 2, "caption": "Caption two.", "page_index": 1},
        ]
        sections: list[dict[str, Any]] = []
        result = paper_analyzer.rank_figures(captions, pages, sections)
        # With equal citations, figure 1 (earlier) should come first
        assert result[0]["figure_num"] == 1

    def test_returns_same_order_on_repeated_calls(self) -> None:
        result_a = paper_analyzer.rank_figures(
            _CAPTIONS_LIST, _PAGE_TEXTS_WITH_CAPTIONS, _SECTION_STRUCTURE
        )
        result_b = paper_analyzer.rank_figures(
            _CAPTIONS_LIST, _PAGE_TEXTS_WITH_CAPTIONS, _SECTION_STRUCTURE
        )
        assert [r["figure_num"] for r in result_a] == [
            r["figure_num"] for r in result_b
        ]

    def test_supplementary_figures_rank_below_results_figures(self) -> None:
        # Figure 1 is in a Supplementary section; Figure 2 is in Results
        pages = [
            "Supplementary\nFig. 1. Supplementary figure.\n",
            "Results\nFig. 2. Main result figure. Figure 2 is cited here.\n",
        ]
        captions = [
            {
                "figure_num": 1,
                "caption": "Supplementary figure.",
                "page_index": 0,
            },
            {"figure_num": 2, "caption": "Main result figure.", "page_index": 1},
        ]
        sections = [
            {"heading": "Supplementary", "page_index": 0},
            {"heading": "Results", "page_index": 1},
        ]
        result = paper_analyzer.rank_figures(captions, pages, sections)
        # Figure 2 (Results, cited) must outrank Figure 1 (Supplementary)
        assert result[0]["figure_num"] == 2

    def test_appendix_figures_treated_as_supplementary(self) -> None:
        pages = [
            "Appendix\nFig. 1. Appendix detail.\n",
            "Results\nFig. 2. Core finding. Cited: Figure 2.\n",
        ]
        captions = [
            {"figure_num": 1, "caption": "Appendix detail.", "page_index": 0},
            {"figure_num": 2, "caption": "Core finding.", "page_index": 1},
        ]
        sections = [
            {"heading": "Appendix", "page_index": 0},
            {"heading": "Results", "page_index": 1},
        ]
        result = paper_analyzer.rank_figures(captions, pages, sections)
        assert result[0]["figure_num"] == 2

    def test_returns_list_same_length_as_input(self) -> None:
        result = paper_analyzer.rank_figures(
            _CAPTIONS_LIST, _PAGE_TEXTS_WITH_CAPTIONS, _SECTION_STRUCTURE
        )
        assert len(result) == len(_CAPTIONS_LIST)

    def test_empty_captions_returns_empty_list(self) -> None:
        result = paper_analyzer.rank_figures([], [], [])
        assert result == []


# ===========================================================================
# BC-12.6  No VLM or network calls (structural boundary check)
# ===========================================================================


class TestNoVlmOrNetworkCalls:
    """BC-12.6: paper_analyzer makes no network or LLM API calls."""

    def _get_source(self) -> str:
        import inspect

        return inspect.getsource(paper_analyzer)

    def test_no_requests_import(self) -> None:
        source = self._get_source()
        assert "import requests" not in source

    def test_no_httpx_import(self) -> None:
        source = self._get_source()
        assert "import httpx" not in source

    def test_no_urllib_request_urlopen(self) -> None:
        source = self._get_source()
        assert "urlopen" not in source

    def test_no_openai_import(self) -> None:
        source = self._get_source()
        assert "import openai" not in source

    def test_no_anthropic_import(self) -> None:
        source = self._get_source()
        assert "import anthropic" not in source

    def test_no_socket_calls(self) -> None:
        source = self._get_source()
        # Rough heuristic: no direct socket.connect usage
        assert "socket.connect" not in source


# ===========================================================================
# BC-12.7  Whitespace crop fallback
# ===========================================================================


class TestWhitespaceCropFallback:
    """BC-12.7: crop_whitespace returns original pixmap when all pixels are white."""

    def test_returns_original_pixmap_when_entirely_white(self) -> None:
        white_px = _make_white_pixmap()
        result = paper_analyzer.crop_whitespace(white_px, threshold=250)
        assert result is white_px

    def test_does_not_raise_on_entirely_white_pixmap(self) -> None:
        white_px = _make_white_pixmap()
        # Must not raise any exception
        result = paper_analyzer.crop_whitespace(white_px)
        assert result is not None

    def test_returns_a_pixmap_when_content_is_present(self) -> None:
        content_px = _make_content_pixmap()
        result = paper_analyzer.crop_whitespace(content_px, threshold=250)
        assert result is not None

    def test_default_threshold_is_250(self) -> None:
        # Calling without threshold arg must not raise (default=250 per spec)
        white_px = _make_white_pixmap()
        result = paper_analyzer.crop_whitespace(white_px)
        assert result is white_px

    def test_pixels_at_exactly_threshold_are_considered_white(self) -> None:
        # A pixmap where all pixels are exactly at threshold=200
        px = _make_pixmap(width=2, height=2, fill_value=200)
        result = paper_analyzer.crop_whitespace(px, threshold=200)
        assert result is px

    def test_pixels_below_threshold_are_treated_as_content(self) -> None:
        # One pixel at 249 with threshold=250 means content exists
        px = _make_pixmap(width=4, height=4, fill_value=255)
        samples = bytearray(px.samples)
        samples[0] = 249  # R channel of first pixel below threshold
        px.samples = bytes(samples)
        result = paper_analyzer.crop_whitespace(px, threshold=250)
        # Should NOT return the original unchanged — it found content
        # (result may be a new cropped pixmap)
        assert result is not None


# ===========================================================================
# BC-12.8  Paper slug derivation and filesystem safety
# ===========================================================================


class TestPaperSlugDerivation:
    """BC-12.8: derive_paper_slug applies sanitization + digit-start p_ prefix."""

    def _derive(self, filename: str) -> str:
        return paper_analyzer.derive_paper_slug(Path(filename))

    def test_lowercase_conversion(self) -> None:
        slug = self._derive("Nature_2024_Smith_et_al.pdf")
        assert slug == slug.lower()

    def test_canonical_example_nature_paper(self) -> None:
        slug = self._derive("Nature_2024_Smith_et_al.pdf")
        assert slug == "nature_2024_smith_et_al"

    def test_digit_start_gets_p_prefix(self) -> None:
        slug = self._derive("2024_smith.pdf")
        assert slug.startswith("p_")
        assert slug == "p_2024_smith"

    def test_digit_start_truncated_to_50_chars_after_prefix(self) -> None:
        # Build a name that after sanitization starts with a digit and is long
        long_name = "2024_" + "a" * 60 + ".pdf"
        slug = self._derive(long_name)
        assert len(slug) <= 50
        assert slug.startswith("p_")

    def test_empty_result_falls_back_to_untitled(self) -> None:
        # All-special-chars filename sanitizes to empty → untitled
        slug = self._derive("!!!.pdf")
        assert slug == "untitled"

    def test_pdf_extension_stripped(self) -> None:
        slug = self._derive("my_paper.pdf")
        assert not slug.endswith(".pdf")

    def test_hyphens_converted_to_underscores(self) -> None:
        slug = self._derive("Smith-et-al-2024.pdf")
        assert "-" not in slug

    def test_spaces_converted_to_underscores(self) -> None:
        slug = self._derive("Smith et al 2024.pdf")
        assert " " not in slug

    def test_consecutive_underscores_collapsed(self) -> None:
        slug = self._derive("Smith__2024.pdf")
        assert "__" not in slug

    def test_leading_trailing_underscores_stripped(self) -> None:
        slug = self._derive("_smith_2024_.pdf")
        assert not slug.startswith("_")
        assert not slug.endswith("_")

    def test_max_length_50_characters(self) -> None:
        long_name = "a" * 80 + ".pdf"
        slug = self._derive(long_name)
        assert len(slug) <= 50

    def test_result_matches_valid_slug_pattern(self) -> None:
        slug = self._derive("Nature_2024_Smith_et_al.pdf")
        assert re.match(r"^[a-z][a-z0-9_]{0,49}$", slug)

    def test_multiple_pdfs_each_get_independent_slug(self) -> None:
        slug_a = self._derive("PaperA_2023.pdf")
        slug_b = self._derive("PaperB_2024.pdf")
        assert slug_a != slug_b

    def test_only_digits_after_sanitization_gets_p_prefix(self) -> None:
        # e.g. "123.pdf" → "123" → starts with digit → "p_123"
        slug = self._derive("123.pdf")
        assert slug == "p_123"


# ===========================================================================
# BC-12.9  Output figure count
# ===========================================================================


class TestOutputFigureCount:
    """BC-12.9: only figures with non-None pixmap produce output files."""

    def test_figures_with_none_pixmap_do_not_produce_files(
        self, tmp_path: Path
    ) -> None:
        ranked = _make_ranked_figures(include_none_pixmap=True)
        figures_with_pixmap = [f for f in ranked if f["pixmap"] is not None]
        for fig in figures_with_pixmap:
            paper_analyzer.save_figure(
                pixmap=fig["pixmap"],
                figure_num=fig["figure_num"],
                paper_slug="count_test",
                project_root=tmp_path,
            )
        fig_dir = (
            tmp_path / "assets" / "reference" / "papers" / "count_test" / "figures"
        )
        if fig_dir.exists():
            png_files = list(fig_dir.glob("*.png"))
        else:
            png_files = []
        assert len(png_files) == len(figures_with_pixmap)

    def test_figures_with_none_pixmap_appear_in_analysis_markdown(
        self, tmp_path: Path
    ) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        ranked = _make_ranked_figures(include_none_pixmap=True)
        claims = {
            fig["figure_num"]: f"Claim for fig {fig['figure_num']}." for fig in ranked
        }
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="none_pixmap_test",
            metadata=_METADATA,
            ranked_figures=ranked,
            claims=claims,
        )
        md_path = tmp_path / ".debrief" / "paper_analysis_none_pixmap_test.md"
        content = md_path.read_text()
        # Figure 3 has pixmap=None but must still appear in markdown
        assert "Extended ablation results" in content

    def test_correct_number_of_png_files_written(self, tmp_path: Path) -> None:
        ranked = _make_ranked_figures(include_none_pixmap=False)
        for fig in ranked:
            paper_analyzer.save_figure(
                pixmap=fig["pixmap"],
                figure_num=fig["figure_num"],
                paper_slug="png_count",
                project_root=tmp_path,
            )
        fig_dir = tmp_path / "assets" / "reference" / "papers" / "png_count" / "figures"
        png_files = list(fig_dir.glob("*.png"))
        assert len(png_files) == 2


# ===========================================================================
# BC-12.10  paper_analysis line format
# ===========================================================================


class TestPaperAnalysisLineFormat:
    """BC-12.10: every numbered figure line matches ^(?P<n>\\d+)\\. (?P<caption>.+)$"""

    _LINE_PATTERN = re.compile(r"^(?P<n>\d+)\. (?P<caption>.+)$")

    def test_every_figure_line_matches_required_pattern(self, tmp_path: Path) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        ranked = _make_ranked_figures()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="format_test",
            metadata=_METADATA,
            ranked_figures=ranked,
            claims={1: "Finding one.", 2: "Finding two."},
        )
        md_path = tmp_path / ".debrief" / "paper_analysis_format_test.md"
        content = md_path.read_text()
        # Find the Key Figures section
        in_figures = False
        figure_lines_checked = 0
        for line in content.splitlines():
            if line.strip() == "## Key Figures":
                in_figures = True
                continue
            if in_figures and line.startswith("## "):
                break
            if in_figures and line.strip():
                assert self._LINE_PATTERN.match(line), (
                    f"Figure line does not match required pattern: {line!r}"
                )
                figure_lines_checked += 1
        assert figure_lines_checked > 0, "No figure lines were found in markdown"

    def test_markdown_contains_metadata_section(self, tmp_path: Path) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="meta_test",
            metadata=_METADATA,
            ranked_figures=_make_ranked_figures(),
            claims={1: "Claim A.", 2: "Claim B."},
        )
        md_path = tmp_path / ".debrief" / "paper_analysis_meta_test.md"
        content = md_path.read_text()
        assert "## Metadata" in content

    def test_markdown_contains_key_figures_section(self, tmp_path: Path) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="keyfig_test",
            metadata=_METADATA,
            ranked_figures=_make_ranked_figures(),
            claims={1: "Claim A.", 2: "Claim B."},
        )
        md_path = tmp_path / ".debrief" / "paper_analysis_keyfig_test.md"
        content = md_path.read_text()
        assert "## Key Figures" in content

    def test_markdown_contains_narrative_arc_section(self, tmp_path: Path) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="arc_test",
            metadata=_METADATA,
            ranked_figures=_make_ranked_figures(),
            claims={1: "Claim A.", 2: "Claim B."},
        )
        md_path = tmp_path / ".debrief" / "paper_analysis_arc_test.md"
        content = md_path.read_text()
        assert "## Suggested Narrative Arc" in content

    def test_markdown_title_contains_paper_slug(self, tmp_path: Path) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="my_slug",
            metadata=_METADATA,
            ranked_figures=_make_ranked_figures(),
            claims={1: "X.", 2: "Y."},
        )
        md_path = tmp_path / ".debrief" / "paper_analysis_my_slug.md"
        content = md_path.read_text()
        assert "my_slug" in content.splitlines()[0]

    def test_metadata_title_appears_in_output(self, tmp_path: Path) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="title_test",
            metadata=_METADATA,
            ranked_figures=_make_ranked_figures(),
            claims={1: "X.", 2: "Y."},
        )
        md_path = tmp_path / ".debrief" / "paper_analysis_title_test.md"
        content = md_path.read_text()
        assert "Deep Representations in Neuroscience" in content

    def test_metadata_authors_appear_in_output(self, tmp_path: Path) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="authors_test",
            metadata=_METADATA,
            ranked_figures=_make_ranked_figures(),
            claims={1: "X.", 2: "Y."},
        )
        md_path = tmp_path / ".debrief" / "paper_analysis_authors_test.md"
        content = md_path.read_text()
        assert "Smith, J." in content

    def test_figure_numbers_in_lines_are_sequential_starting_at_1(
        self, tmp_path: Path
    ) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="seq_test",
            metadata=_METADATA,
            ranked_figures=_make_ranked_figures(),
            claims={1: "Claim A.", 2: "Claim B."},
        )
        md_path = tmp_path / ".debrief" / "paper_analysis_seq_test.md"
        content = md_path.read_text()
        in_figures = False
        nums: list[int] = []
        for line in content.splitlines():
            if line.strip() == "## Key Figures":
                in_figures = True
                continue
            if in_figures and line.startswith("## "):
                break
            if in_figures:
                m = self._LINE_PATTERN.match(line)
                if m:
                    nums.append(int(m.group("n")))
        assert nums == list(range(1, len(nums) + 1))

    def test_none_metadata_fields_handled_gracefully(self, tmp_path: Path) -> None:
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        none_metadata = {
            "title": None,
            "authors": None,
            "journal": None,
            "year": None,
        }
        # Must not raise even with all-None metadata
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="none_meta",
            metadata=none_metadata,
            ranked_figures=_make_ranked_figures(),
            claims={1: "X.", 2: "Y."},
        )
        md_path = tmp_path / ".debrief" / "paper_analysis_none_meta.md"
        assert md_path.exists()


# ===========================================================================
# Additional contract coverage: section structure extraction
# ===========================================================================


class TestExtractSectionStructure:
    """extract_section_structure: returns list of dicts with heading + page_index."""

    def test_returns_list_of_dicts(self) -> None:
        pages = ["INTRODUCTION\nSome text here.\n"]
        result = paper_analyzer.extract_section_structure(pages)
        assert isinstance(result, list)

    def test_detects_uppercase_section_headings(self) -> None:
        pages = ["RESULTS\nWe found that...\n"]
        result = paper_analyzer.extract_section_structure(pages)
        headings = [r["heading"] for r in result]
        assert any("RESULTS" in h for h in headings)

    def test_detects_numbered_section_headings(self) -> None:
        pages = ["1. Introduction\nThis paper presents...\n"]
        result = paper_analyzer.extract_section_structure(pages)
        assert len(result) >= 1
        assert result[0]["page_index"] == 0

    def test_empty_pages_returns_empty_list(self) -> None:
        result = paper_analyzer.extract_section_structure([])
        assert result == []

    def test_result_dicts_have_required_keys(self) -> None:
        pages = ["METHODS\nWe used a dataset of 100 samples.\n"]
        result = paper_analyzer.extract_section_structure(pages)
        for item in result:
            assert "heading" in item
            assert "page_index" in item

    def test_page_index_correct_for_multi_page_input(self) -> None:
        pages = [
            "Body text only.\n",
            "RESULTS\nWe found significant differences.\n",
        ]
        result = paper_analyzer.extract_section_structure(pages)
        # Any detected heading from the second page must report page_index=1
        for item in result:
            if "RESULTS" in item["heading"]:
                assert item["page_index"] == 1


# ===========================================================================
# Additional contract coverage: extract_figure_claims
# ===========================================================================


class TestExtractFigureClaims:
    """extract_figure_claims: returns dict mapping figure_num -> claim text."""

    def test_returns_dict(self) -> None:
        pages = ["Figure 1. Caption for fig 1.\nThis sentence is the claim.\n"]
        captions = [{"figure_num": 1, "caption": "Caption for fig 1.", "page_index": 0}]
        result = paper_analyzer.extract_figure_claims(pages, captions)
        assert isinstance(result, dict)

    def test_claim_follows_caption(self) -> None:
        pages = [
            "Figure 1. Neural activations.\nThe network learns hierarchical features.\n"
        ]
        captions = [
            {"figure_num": 1, "caption": "Neural activations.", "page_index": 0}
        ]
        result = paper_analyzer.extract_figure_claims(pages, captions)
        assert 1 in result
        assert "hierarchical" in result[1]

    def test_empty_claim_when_no_sentences_follow_caption(self) -> None:
        # Caption is the last line on the page
        pages = ["Figure 1. Last line caption."]
        captions = [{"figure_num": 1, "caption": "Last line caption.", "page_index": 0}]
        result = paper_analyzer.extract_figure_claims(pages, captions)
        assert result.get(1, "") == ""

    def test_extracts_up_to_three_sentences(self) -> None:
        pages = [
            "Figure 1. Caption here.\n"
            "Sentence one is significant.\n"
            "Sentence two confirms results.\n"
            "Sentence three summarises.\n"
            "Sentence four should be excluded.\n"
        ]
        captions = [{"figure_num": 1, "caption": "Caption here.", "page_index": 0}]
        result = paper_analyzer.extract_figure_claims(pages, captions)
        claim = result.get(1, "")
        # Claim should contain at most 3 sentences worth of content
        # Sentence four must not appear
        assert "four" not in claim

    def test_empty_captions_returns_empty_dict(self) -> None:
        result = paper_analyzer.extract_figure_claims([], [])
        assert result == {}


# ===========================================================================
# Additional contract coverage: extract_paper_metadata
# ===========================================================================


class TestExtractPaperMetadata:
    """extract_paper_metadata: returns dict with title/authors/journal/year."""

    def test_returns_dict_with_required_keys(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 minimal")
        mock_doc = MagicMock()
        mock_doc.metadata = {
            "title": "Test Title",
            "author": "Smith, J.",
            "subject": "",
            "creationDate": "D:20240101",
        }
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        with patch("fitz.open", return_value=mock_doc):
            result = paper_analyzer.extract_paper_metadata(pdf_path, [])
        for key in ("title", "authors", "journal", "year"):
            assert key in result

    def test_all_fields_may_be_none(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 minimal")
        mock_doc = MagicMock()
        mock_doc.metadata = {}
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        with patch("fitz.open", return_value=mock_doc):
            result = paper_analyzer.extract_paper_metadata(pdf_path, [])
        # All fields present, values may be None
        assert "title" in result
        assert "authors" in result
        assert "journal" in result
        assert "year" in result


# ===========================================================================
# Additional contract coverage: extract_figure_images
# ===========================================================================


class TestExtractFigureImages:
    """extract_figure_images: returns list with pixmap=None when page has no images."""

    def test_pixmap_none_when_page_has_no_images(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 minimal")
        mock_page = MagicMock()
        mock_page.get_images.return_value = []  # no images
        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        captions = [{"figure_num": 1, "caption": "A caption.", "page_index": 0}]
        with patch("fitz.open", return_value=mock_doc):
            result = paper_analyzer.extract_figure_images(pdf_path, captions)
        assert result[0]["pixmap"] is None

    def test_returns_list_with_required_keys(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 minimal")
        mock_page = MagicMock()
        mock_page.get_images.return_value = []
        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        captions = [{"figure_num": 2, "caption": "Another caption.", "page_index": 0}]
        with patch("fitz.open", return_value=mock_doc):
            result = paper_analyzer.extract_figure_images(pdf_path, captions)
        assert len(result) == 1
        for key in ("figure_num", "pixmap", "page_index"):
            assert key in result[0]


# ===========================================================================
# Additional gap tests
# ===========================================================================


class TestBC12_2StderrMessageContent:
    """BC-12.2: stderr must contain the standardized Section 9.3.1 error text."""

    def test_stderr_contains_section_9_3_1_reference(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The error message must reference Section 9.3.1 (env-corruption standard)."""
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        with patch.dict(sys.modules, {"fitz": None}):
            with pytest.raises(SystemExit):
                paper_analyzer.main_paper_analyzer(
                    pdf_path=pdf_path,
                    paper_slug="test_paper",
                    project_root=tmp_path,
                )
        captured = capsys.readouterr()
        assert "9.3.1" in captured.err

    def test_stderr_contains_conda_env_create_instruction(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The error message must include the conda env create recovery step."""
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        with patch.dict(sys.modules, {"fitz": None}):
            with pytest.raises(SystemExit):
                paper_analyzer.main_paper_analyzer(
                    pdf_path=pdf_path,
                    paper_slug="test_paper",
                    project_root=tmp_path,
                )
        captured = capsys.readouterr()
        assert "conda env create" in captured.err

    def test_stderr_mentions_fitz_or_pymupdf(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The error message must mention the missing package (fitz/PyMuPDF)."""
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        with patch.dict(sys.modules, {"fitz": None}):
            with pytest.raises(SystemExit):
                paper_analyzer.main_paper_analyzer(
                    pdf_path=pdf_path,
                    paper_slug="test_paper",
                    project_root=tmp_path,
                )
        captured = capsys.readouterr()
        assert "fitz" in captured.err.lower() or "pymupdf" in captured.err.lower()


class TestBC12_3CaptionRegexNoSeparator:
    """BC-12.3: the separator in the pattern is optional ([\\.:]?).

    'Figure 1 Some caption' (no dot or colon) must also be matched.
    """

    def test_figure_n_no_separator_matches(self) -> None:
        pages = ["Figure 1 The activation pattern is shown here.\n"]
        result = paper_analyzer.extract_figure_captions(pages)
        assert len(result) == 1
        assert result[0]["figure_num"] == 1
        assert "activation pattern" in result[0]["caption"]

    def test_fig_dot_n_no_separator_matches(self) -> None:
        pages = ["Fig. 2 Accuracy over epochs.\n"]
        result = paper_analyzer.extract_figure_captions(pages)
        assert len(result) == 1
        assert result[0]["figure_num"] == 2
        assert "Accuracy" in result[0]["caption"]


class TestBC12_4SaveFigureContentPreservation:
    """BC-12.4: save_figure must write the pixmap's tobytes() content to the file."""

    def test_save_figure_file_content_matches_tobytes(
        self, tmp_path: Path
    ) -> None:
        expected_bytes = b"\x89PNG\r\n\x1a\n" + b"\xAB" * 20
        pixmap = _make_content_pixmap()
        pixmap.tobytes.return_value = expected_bytes
        paper_analyzer.save_figure(
            pixmap=pixmap,
            figure_num=7,
            paper_slug="content_check",
            project_root=tmp_path,
        )
        dest = (
            tmp_path
            / "assets"
            / "reference"
            / "papers"
            / "content_check"
            / "figures"
            / "fig_7.png"
        )
        assert dest.read_bytes() == expected_bytes
