# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-86: per-page figure-image distribution.

Before BUG-AUDIT-86, ``extract_figure_images`` always picked
``page.get_images(full=True)[0][0]`` for every caption it encountered. When
two figure captions shared a page (extremely common in two-column journals),
both received the same xref → save_figure produced identical PNGs for
distinct figures. The user's tomorrow lab-meeting case (a single figure
borrowed from a paper) was at risk because most papers put multiple figures
per page.

These tests pin BC-12.9's amended distribution rule: per page, the i-th
caption gets the i-th image; trailing captions on under-imaged pages get
``pixmap=None``; identical xrefs are never reused across captions.
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


def _mock_doc(pages: list[list[tuple[int, ...]]]) -> MagicMock:
    """Build a mock fitz Document where pages[i] is the images list for page i.

    Each image entry is a tuple whose [0] element is the xref. The mock pages
    return their respective image lists from get_images.
    """
    mock_pages = []
    for image_list in pages:
        mp = MagicMock()
        mp.get_images.return_value = image_list
        mock_pages.append(mp)

    doc = MagicMock()
    doc.__getitem__ = MagicMock(side_effect=lambda i: mock_pages[i])
    doc.__enter__ = MagicMock(return_value=doc)
    doc.__exit__ = MagicMock(return_value=False)
    return doc


def _captions(*entries: tuple[int, int]) -> list[dict[str, Any]]:
    """Return [{figure_num, caption, page_index}, ...] from (figure_num, page_index) tuples."""
    return [
        {
            "figure_num": fn,
            "caption": f"Caption for fig {fn}",
            "page_index": pi,
        }
        for fn, pi in entries
    ]


class TestDistinctImagesForCaptionsOnSamePage:
    """BC-12.9: i-th caption on a page receives the i-th image's xref."""

    def test_two_captions_on_one_page_get_distinct_xrefs(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        # Page 0: two images with xrefs 11 and 22
        doc = _mock_doc([[(11,), (22,)]])

        captured_xrefs: list[int] = []

        def _pixmap_factory(d: Any, xref: int) -> MagicMock:
            captured_xrefs.append(xref)
            pm = MagicMock()
            pm.n = 3  # avoid CMYK conversion branch
            return pm

        captions = _captions((1, 0), (2, 0))
        with patch("fitz.open", return_value=doc), patch(
            "fitz.Pixmap", side_effect=_pixmap_factory
        ):
            paper_analyzer.extract_figure_images(pdf, captions)

        assert captured_xrefs == [11, 22], (
            f"i-th caption must receive i-th image's xref; got {captured_xrefs}"
        )

    def test_three_captions_on_one_page_each_get_unique_image(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _mock_doc([[(7,), (8,), (9,)]])

        captured_xrefs: list[int] = []

        def _pixmap_factory(d: Any, xref: int) -> MagicMock:
            captured_xrefs.append(xref)
            pm = MagicMock()
            pm.n = 3
            return pm

        captions = _captions((1, 0), (2, 0), (3, 0))
        with patch("fitz.open", return_value=doc), patch(
            "fitz.Pixmap", side_effect=_pixmap_factory
        ):
            paper_analyzer.extract_figure_images(pdf, captions)

        assert captured_xrefs == [7, 8, 9]
        assert len(set(captured_xrefs)) == 3, "no xref reuse"


class TestUnderImagedPage:
    """When a page has fewer images than captions, trailing captions get None."""

    def test_two_captions_one_image_second_gets_none(self, tmp_path: Path) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _mock_doc([[(42,)]])  # one image only

        def _pixmap_factory(d: Any, xref: int) -> MagicMock:
            pm = MagicMock()
            pm.n = 3
            return pm

        captions = _captions((1, 0), (2, 0))
        with patch("fitz.open", return_value=doc), patch(
            "fitz.Pixmap", side_effect=_pixmap_factory
        ):
            result = paper_analyzer.extract_figure_images(pdf, captions)

        assert result[0]["pixmap"] is not None
        assert result[1]["pixmap"] is None

    def test_caption_on_page_with_zero_images_gets_none(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _mock_doc([[]])  # empty page

        captions = _captions((5, 0))
        with patch("fitz.open", return_value=doc):
            result = paper_analyzer.extract_figure_images(pdf, captions)
        assert result[0]["pixmap"] is None


class TestMultipage:
    """Distribution is per-page; no cross-page leakage."""

    def test_one_caption_per_page_each_gets_first_image(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        # Page 0 image xref=10; page 1 image xref=20
        doc = _mock_doc([[(10,)], [(20,)]])

        captured: list[int] = []

        def _pixmap_factory(d: Any, xref: int) -> MagicMock:
            captured.append(xref)
            pm = MagicMock()
            pm.n = 3
            return pm

        captions = _captions((1, 0), (2, 1))
        with patch("fitz.open", return_value=doc), patch(
            "fitz.Pixmap", side_effect=_pixmap_factory
        ):
            paper_analyzer.extract_figure_images(pdf, captions)
        assert captured == [10, 20]

    def test_mixed_page_with_solo_and_shared_captions(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        # Page 0: two images for two captions; page 1: one image for one caption
        doc = _mock_doc([[(101,), (102,)], [(201,)]])

        captured: list[int] = []

        def _pixmap_factory(d: Any, xref: int) -> MagicMock:
            captured.append(xref)
            pm = MagicMock()
            pm.n = 3
            return pm

        captions = _captions((1, 0), (2, 0), (3, 1))
        with patch("fitz.open", return_value=doc), patch(
            "fitz.Pixmap", side_effect=_pixmap_factory
        ):
            result = paper_analyzer.extract_figure_images(pdf, captions)

        # Each caption sees a distinct xref
        assert sorted(captured) == [101, 102, 201]
        # Output preserves input caption order
        assert [r["figure_num"] for r in result] == [1, 2, 3]
        assert [r["page_index"] for r in result] == [0, 0, 1]


class TestOutputOrderMatchesInput:
    """The result list must be in the same order as figure_captions."""

    def test_input_order_preserved_even_when_grouped_internally(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        # Page 0 has 2 images; page 1 has 1 image
        doc = _mock_doc([[(11,), (12,)], [(99,)]])

        def _pixmap_factory(d: Any, xref: int) -> MagicMock:
            pm = MagicMock()
            pm.n = 3
            pm.xref = xref  # tag for inspection
            return pm

        # Captions interleave pages — ensures grouping logic doesn't reorder
        captions = [
            {"figure_num": 1, "caption": "p0-first", "page_index": 0},
            {"figure_num": 2, "caption": "p1-only", "page_index": 1},
            {"figure_num": 3, "caption": "p0-second", "page_index": 0},
        ]
        with patch("fitz.open", return_value=doc), patch(
            "fitz.Pixmap", side_effect=_pixmap_factory
        ):
            result = paper_analyzer.extract_figure_images(pdf, captions)

        assert [r["figure_num"] for r in result] == [1, 2, 3]
        # page-0 captions in input order get page-0 images in slot order
        assert result[0]["pixmap"].xref == 11
        assert result[2]["pixmap"].xref == 12
        # page-1 caption gets page-1 image
        assert result[1]["pixmap"].xref == 99


class TestNoXrefAliasing:
    """The historical bug: every caption on a page received images[0][0]."""

    def test_two_pixmaps_on_same_page_are_not_the_same_object(
        self, tmp_path: Path
    ) -> None:
        pdf = tmp_path / "p.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc = _mock_doc([[(1,), (2,)]])

        # Each call returns a NEW mock pixmap; if the code aliased to images[0]
        # only one pixmap would be created.
        created_pixmaps: list[Any] = []

        def _pixmap_factory(d: Any, xref: int) -> MagicMock:
            pm = MagicMock()
            pm.n = 3
            pm.xref_tag = xref
            created_pixmaps.append(pm)
            return pm

        captions = _captions((1, 0), (2, 0))
        with patch("fitz.open", return_value=doc), patch(
            "fitz.Pixmap", side_effect=_pixmap_factory
        ):
            result = paper_analyzer.extract_figure_images(pdf, captions)

        assert len(created_pixmaps) == 2, "expected one Pixmap per caption"
        assert result[0]["pixmap"] is not result[1]["pixmap"]
        assert result[0]["pixmap"].xref_tag != result[1]["pixmap"].xref_tag
