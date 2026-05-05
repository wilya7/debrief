# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-85: claims persistence in paper_analysis.

Before BUG-AUDIT-85, ``write_paper_analysis`` accepted a ``claims`` parameter
but never wrote it. Per-figure claims extracted by ``extract_figure_claims``
were silently dropped, leaving downstream consumers (consultant, slide-maker,
script-writer) with only captions to work from.

These tests pin BC-12.11: the ``## Figure Claims`` section must appear in the
output, must contain one line per ranked figure in document order, must follow
the line format ``^\\*\\*Figure (?P<n>\\d+)\\.\\*\\* (?P<claim>.+)$``, and must
render an explicit placeholder for figures whose extracted claim is empty.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# Ensure paper_analyzer is importable from either layout (workspace stub or
# delivered debrief.paper_analyzer). Sibling discovery first; package import
# second.
_HERE = Path(__file__).resolve().parent
_WORKSPACE_STUB = _HERE.parent.parent / "src" / "unit_12"
if _WORKSPACE_STUB.is_dir() and str(_WORKSPACE_STUB) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_STUB))

try:
    paper_analyzer = importlib.import_module("paper_analyzer")
except ModuleNotFoundError:  # pragma: no cover — exercised in delivered repo
    paper_analyzer = importlib.import_module("debrief.paper_analyzer")


_CLAIM_LINE_RE = re.compile(r"^\*\*Figure (?P<n>\d+)\.\*\* (?P<claim>.+)$")
_PLACEHOLDER = "_(no claim text extracted)_"


def _ranked(figs: list[tuple[int, str]]) -> list[dict[str, Any]]:
    """Return a minimal ranked_figures list — figure_num + caption + page_index."""
    return [
        {
            "figure_num": n,
            "caption": cap,
            "page_index": i,
            "pixmap": MagicMock(),
        }
        for i, (n, cap) in enumerate(figs)
    ]


_METADATA = {
    "title": "Test Paper",
    "authors": "Smith, Jones",
    "journal": "Test Journal",
    "year": "2026",
}


def _read_md(tmp_path: Path, slug: str) -> str:
    return (tmp_path / ".debrief" / f"paper_analysis_{slug}.md").read_text()


def _claims_section(content: str) -> list[str]:
    """Return the body lines of the ## Figure Claims section, trimmed."""
    inside = False
    body: list[str] = []
    for line in content.splitlines():
        if line.strip() == "## Figure Claims":
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside:
            body.append(line)
    return [ln for ln in body if ln.strip()]


class TestClaimsBlockExists:
    """BC-12.11: the Figure Claims block must appear in the output."""

    def test_section_header_present(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="hdr",
            metadata=_METADATA,
            ranked_figures=_ranked([(1, "First figure"), (2, "Second figure")]),
            claims={1: "Claim one.", 2: "Claim two."},
        )
        assert "## Figure Claims" in _read_md(tmp_path, "hdr")

    def test_section_appears_between_key_figures_and_narrative(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".debrief").mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="ord",
            metadata=_METADATA,
            ranked_figures=_ranked([(1, "Cap")]),
            claims={1: "C."},
        )
        content = _read_md(tmp_path, "ord")
        i_keyfigs = content.find("## Key Figures")
        i_claims = content.find("## Figure Claims")
        i_arc = content.find("## Suggested Narrative Arc")
        assert i_keyfigs >= 0 and i_claims >= 0 and i_arc >= 0
        assert i_keyfigs < i_claims < i_arc


class TestClaimLineFormat:
    """BC-12.11 regex: ^\\*\\*Figure (?P<n>\\d+)\\.\\*\\* (?P<claim>.+)$"""

    def test_every_claim_line_matches_pattern(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="fmt",
            metadata=_METADATA,
            ranked_figures=_ranked(
                [(1, "Cap one"), (2, "Cap two"), (3, "Cap three")]
            ),
            claims={
                1: "Activation reveals hierarchy.",
                2: "Accuracy improves.",
                3: "Effect persists across conditions.",
            },
        )
        for line in _claims_section(_read_md(tmp_path, "fmt")):
            assert _CLAIM_LINE_RE.match(line), (
                f"claim line does not match BC-12.11 pattern: {line!r}"
            )


class TestClaimContentSurfaced:
    """The actual claim text must appear in the output, not just be hinted."""

    def test_claim_text_appears_verbatim(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir()
        claim_for_fig_1 = "Knockout reduces firing by 42% (n=18)."
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="verb",
            metadata=_METADATA,
            ranked_figures=_ranked([(1, "KO firing")]),
            claims={1: claim_for_fig_1},
        )
        assert claim_for_fig_1 in _read_md(tmp_path, "verb")


class TestClaimsBlockCardinality:
    """BC-12.11: one claim line per ranked figure (NOT per claims dict key)."""

    def test_line_count_equals_ranked_figures_count(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir()
        ranked = _ranked([(1, "A"), (2, "B"), (3, "C"), (4, "D")])
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="cnt",
            metadata=_METADATA,
            ranked_figures=ranked,
            claims={1: "x.", 2: "y."},  # missing 3 and 4 deliberately
        )
        body = _claims_section(_read_md(tmp_path, "cnt"))
        assert len(body) == len(ranked)


class TestEmptyClaimPlaceholder:
    """BC-12.11: missing/empty claim renders as a visible placeholder."""

    def test_missing_claim_renders_placeholder(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="ph_miss",
            metadata=_METADATA,
            ranked_figures=_ranked([(1, "Cap"), (2, "Cap2")]),
            claims={1: "Claim one."},  # 2 missing entirely
        )
        body = _claims_section(_read_md(tmp_path, "ph_miss"))
        assert any(_PLACEHOLDER in ln and "Figure 2" in ln for ln in body)

    def test_empty_string_claim_renders_placeholder(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="ph_empty",
            metadata=_METADATA,
            ranked_figures=_ranked([(1, "Cap")]),
            claims={1: ""},
        )
        body = _claims_section(_read_md(tmp_path, "ph_empty"))
        assert any(_PLACEHOLDER in ln and "Figure 1" in ln for ln in body)

    def test_whitespace_only_claim_renders_placeholder(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="ph_ws",
            metadata=_METADATA,
            ranked_figures=_ranked([(1, "Cap")]),
            claims={1: "   \t  "},
        )
        body = _claims_section(_read_md(tmp_path, "ph_ws"))
        assert any(_PLACEHOLDER in ln and "Figure 1" in ln for ln in body)


class TestClaimsDocumentOrder:
    """Claims appear in ranked-figures (document) order, not claims-dict order."""

    def test_order_follows_ranked_figures(self, tmp_path: Path) -> None:
        (tmp_path / ".debrief").mkdir()
        ranked = _ranked([(3, "third"), (1, "first"), (2, "second")])
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="ord_doc",
            metadata=_METADATA,
            ranked_figures=ranked,
            claims={1: "one.", 2: "two.", 3: "three."},
        )
        body = _claims_section(_read_md(tmp_path, "ord_doc"))
        nums = [int(_CLAIM_LINE_RE.match(ln).group("n")) for ln in body]
        assert nums == [3, 1, 2]


class TestNoSilentDrop:
    """The historical bug: claims silently dropped. This test would have failed."""

    def test_extracted_claim_actually_persisted(self, tmp_path: Path) -> None:
        # This is the canary: write claims, then read the file and confirm
        # the substantive claim text is recoverable. Pre-fix this assertion
        # always failed because the body of write_paper_analysis ignored its
        # claims parameter entirely.
        (tmp_path / ".debrief").mkdir()
        paper_analyzer.write_paper_analysis(
            project_root=tmp_path,
            paper_slug="canary",
            metadata=_METADATA,
            ranked_figures=_ranked([(1, "Cap")]),
            claims={1: "DISTINCTIVE_PAYLOAD_TOKEN"},
        )
        assert "DISTINCTIVE_PAYLOAD_TOKEN" in _read_md(tmp_path, "canary")
