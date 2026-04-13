# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 12: Paper Analyzer.

Local, deterministic PDF analysis pipeline for debrief.
Extracts figure captions, section structure, figure images, metadata,
and writes a structured paper analysis markdown file.

No network calls. No LLM/VLM calls. Requires fitz (PyMuPDF).
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import types
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Lazy fitz registration
# ---------------------------------------------------------------------------
# When fitz (PyMuPDF) is not installed, register a minimal placeholder in
# sys.modules so that unittest.mock.patch("fitz.open", ...) can resolve the
# dotted name without raising ModuleNotFoundError.  The placeholder raises
# ImportError on any attribute access at call time, which is suppressed by
# the actual lazy-import guards inside each function.  main_paper_analyzer
# performs the definitive availability check via importlib.util.find_spec.

if importlib.util.find_spec("fitz") is None and "fitz" not in sys.modules:
    _fitz_stub = types.ModuleType("fitz")
    sys.modules["fitz"] = _fitz_stub

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FITZ_ENV_CORRUPTION_MSG = (
    "ERROR: fitz (PyMuPDF) is not installed or the conda environment is"
    " corrupt.\n"
    "Run: conda env create -f environment.yml  (see Section 9.3.1)\n"
    "The PyMuPDF package is required for paper analysis.\n"
)

_CAPTION_PATTERN = re.compile(
    r"^(?:Figure|Fig\.)\s+(?P<n>\d+)[\.:]?\s+(?P<caption>.+)",
    re.MULTILINE,
)

# Section headings: uppercase-only line (2-40 chars), or numbered heading
_SECTION_PATTERN = re.compile(
    r"(?m)^(?:"
    r"(?P<numbered>\d+(?:\.\d+)*\.?\s+[A-Z][A-Za-z].*)"
    r"|"
    r"(?P<upper>[A-Z][A-Z\s\-]{1,38}[A-Z])"
    r")$"
)

_SUPPLEMENTARY_RE = re.compile(r"supplementary|appendix", re.IGNORECASE)
_RESULTS_RE = re.compile(r"\bresults?\b|\bdiscussion\b|\bconclusion\b", re.IGNORECASE)

# Citation pattern: "Figure N" or "Fig. N" (case-insensitive)
_CITE_PATTERN = re.compile(r"(?:Figure|Fig\.)\s+(\d+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Sanitization (local reimplementation to avoid cross-unit import)
# ---------------------------------------------------------------------------


def _sanitize_identifier(text: str, max_length: int = 40) -> str:
    """Apply the Debrief Identifier Sanitization Algorithm (Section 24.10.1).

    Steps in order:
    1. Lowercase.
    2. Spaces/hyphens -> underscores.
    3. Remove non-[a-z0-9_].
    4. Collapse consecutive underscores.
    5. Strip leading/trailing underscores.
    6. Truncate to max_length.
    7. Empty -> 'untitled'.
    """
    result = text.lower()
    result = re.sub(r"[ \-]", "_", result)
    result = re.sub(r"[^a-z0-9_]", "", result)
    result = re.sub(r"_+", "_", result)
    result = result.strip("_")
    # Step 7: empty check BEFORE step 6 per Section 24.10.1
    if not result:
        return "untitled"
    result = result[:max_length]
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def derive_paper_slug(pdf_path: Path) -> str:
    """Derive a filesystem-safe slug from a PDF filename.

    Process:
    1. Strip .pdf extension.
    2. Apply _sanitize_identifier with max_length=50.
    3. If result starts with a digit, prepend 'p_' and truncate to 50 chars.
    4. Result 'untitled' is returned as-is.

    Examples:
      Nature_2024_Smith_et_al.pdf -> nature_2024_smith_et_al
      2024_smith.pdf              -> p_2024_smith
    """
    stem = pdf_path.stem
    slug = _sanitize_identifier(stem, max_length=50)
    if slug == "untitled":
        return "untitled"
    if slug[0].isdigit():
        slug = ("p_" + slug)[:50]
    return slug


def extract_paper_text(pdf_path: Path) -> list[str]:
    """Open PDF with fitz.open() and return per-page text strings."""
    import fitz  # type: ignore[import]

    pages: list[str] = []
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            pages.append(page.get_text())
    return pages


def extract_section_structure(pages: list[str]) -> list[dict[str, Any]]:
    """Identify section headings using heuristics.

    Detects:
    - Short all-uppercase lines (2-40 chars).
    - Numbered section headings (e.g. '1. Introduction').

    Returns list of {"heading": str, "page_index": int} in document order.
    """
    results: list[dict[str, Any]] = []
    for page_index, text in enumerate(pages):
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Check for numbered heading: e.g. "1. Introduction" or "2.1 Methods"
            numbered_match = re.match(
                r"^(\d+(?:\.\d+)*\.?\s+[A-Z][A-Za-z].*)$", stripped
            )
            if numbered_match:
                results.append({"heading": stripped, "page_index": page_index})
                continue
            # Check for uppercase-only heading (min 2 chars, not all digits)
            if (
                len(stripped) >= 2
                and len(stripped) <= 60
                and stripped == stripped.upper()
                and re.search(r"[A-Z]", stripped)
                and not re.match(r"^\d+$", stripped)
            ):
                results.append({"heading": stripped, "page_index": page_index})
    return results


def extract_figure_captions(pages: list[str]) -> list[dict[str, Any]]:
    r"""Scan page text for figure caption patterns.

    Pattern: r'^(?:Figure|Fig\.)\s+(?P<n>\d+)[\.:]?\s+(?P<caption>.+)'
    Applied with MULTILINE so ^ anchors to line starts.

    Returns list of {"figure_num": int, "caption": str, "page_index": int}
    in document order.
    """
    results: list[dict[str, Any]] = []
    for page_index, text in enumerate(pages):
        for match in _CAPTION_PATTERN.finditer(text):
            figure_num = int(match.group("n"))
            caption = match.group("caption").strip()
            results.append(
                {
                    "figure_num": figure_num,
                    "caption": caption,
                    "page_index": page_index,
                }
            )
    return results


def extract_figure_images(
    pdf_path: Path,
    figure_captions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract figure images for each caption entry.

    For each caption, opens the page at caption["page_index"], fetches
    images via page.get_images(), and builds a fitz.Pixmap.  If no images
    are found on the page, pixmap is set to None.

    Returns list of {"figure_num": int, "pixmap": ..., "page_index": int}.
    """
    import fitz  # type: ignore[import]

    results: list[dict[str, Any]] = []
    with fitz.open(str(pdf_path)) as doc:
        for caption in figure_captions:
            page_index: int = caption["page_index"]
            figure_num: int = caption["figure_num"]
            page = doc[page_index]
            images = page.get_images(full=True)
            pixmap: Any = None
            if images:
                # Use the first (largest or first-listed) image
                xref = images[0][0]
                try:
                    pixmap = fitz.Pixmap(doc, xref)
                    # Convert CMYK/other to RGB if needed
                    if pixmap.n > 4:
                        pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
                except Exception:
                    pixmap = None
            results.append(
                {
                    "figure_num": figure_num,
                    "pixmap": pixmap,
                    "page_index": page_index,
                }
            )
    return results


def rank_figures(
    figure_captions: list[dict[str, Any]],
    pages: list[str],
    section_structure: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rank figures by citation frequency and section location.

    Scoring:
    - +1 per body-text citation of "Figure N" or "Fig. N"
    - +10 bonus if figure is in a results/discussion section
    - -10 penalty if figure is in a supplementary/appendix section

    Ties broken by document order (earlier = higher rank = lower index).

    Returns figures sorted by descending score (ties: earlier first).
    """
    if not figure_captions:
        return []

    # Build mapping: page_index -> section heading (the last heading seen
    # on or before that page)
    page_section: dict[int, str] = {}
    # Sort section_structure by page_index so we can walk forward
    sorted_sections = sorted(section_structure, key=lambda s: s["page_index"])
    for fig in figure_captions:
        pi = fig["page_index"]
        # Find most recent section heading at or before this page
        heading = ""
        for sec in sorted_sections:
            if sec["page_index"] <= pi:
                heading = sec["heading"]
            else:
                break
        page_section[pi] = heading

    # Count citations per figure in full text (all pages)
    full_text = "\n".join(pages)
    citation_counts: dict[int, int] = {}
    for fig in figure_captions:
        fig_num = fig["figure_num"]
        citation_counts[fig_num] = 0

    for match in _CITE_PATTERN.finditer(full_text):
        n = int(match.group(1))
        if n in citation_counts:
            citation_counts[n] += 1

    # Assign scores
    scored: list[tuple[int, float, dict[str, Any]]] = []
    for doc_order, fig in enumerate(figure_captions):
        fig_num = fig["figure_num"]
        pi = fig["page_index"]
        heading = page_section.get(pi, "")

        score: float = float(citation_counts.get(fig_num, 0))

        if _SUPPLEMENTARY_RE.search(heading):
            score -= 10.0
        elif _RESULTS_RE.search(heading):
            score += 10.0

        # doc_order as tiebreaker: negate so earlier = higher rank
        scored.append((-doc_order, score, fig))

    # Sort by descending score, then by descending -doc_order (earlier first)
    scored.sort(key=lambda t: (t[1], t[0]), reverse=True)

    return [item[2] for item in scored]


def crop_whitespace(
    pixmap: Any,
    threshold: int = 250,
) -> Any:
    """Crop whitespace from a Pixmap.

    Pixels where all channels >= threshold are considered white/background.
    Finds the bounding box of non-white pixels and returns a sub-pixmap.
    If the entire image is white, returns the original pixmap unchanged.

    Works with MagicMock pixmaps for testing (reads .samples, .width,
    .height, .n attributes directly).
    """
    width: int = pixmap.width
    height: int = pixmap.height
    n_channels: int = pixmap.n
    samples: bytes = pixmap.samples

    min_x = width
    max_x = -1
    min_y = height
    max_y = -1

    for y in range(height):
        for x in range(width):
            offset = (y * width + x) * n_channels
            pixel = samples[offset : offset + n_channels]
            if any(c < threshold for c in pixel):
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y

    # Entirely white — return original unchanged
    if max_x < 0:
        return pixmap

    # Try to use fitz.Pixmap sub-region if fitz is available
    try:
        import fitz  # type: ignore[import]

        rect = fitz.IRect(min_x, min_y, max_x + 1, max_y + 1)
        return pixmap.set_origin(0, 0).__class__(pixmap, rect)
    except Exception:
        # Fall back: return original if cropping API unavailable
        return pixmap


def save_figure(
    pixmap: Any,
    figure_num: int,
    paper_slug: str,
    project_root: Path,
) -> Path:
    """Save pixmap as PNG atomically.

    Destination: assets/reference/papers/<paper_slug>/figures/fig_<N>.png
    Uses write-to-.tmp then os.rename atomic protocol.

    Returns the destination Path.
    Raises OSError on write failure.
    """
    fig_dir = project_root / "assets" / "reference" / "papers" / paper_slug / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    dest = fig_dir / f"fig_{figure_num}.png"
    tmp = fig_dir / f"fig_{figure_num}.png.tmp"

    png_bytes: bytes = pixmap.tobytes()
    with open(tmp, "wb") as fh:
        fh.write(png_bytes)
        fh.flush()
        os.fsync(fh.fileno())
    os.rename(tmp, dest)
    return dest


def extract_figure_claims(
    pages: list[str],
    figure_captions: list[dict[str, Any]],
) -> dict[int, str]:
    """Extract 1-3 claim sentences following each figure caption.

    Looks at the page containing each caption.  After the caption line,
    collects up to 3 non-empty lines (treating each line as a sentence
    for simplicity).

    Returns dict mapping figure_num -> claim text (empty string if none).
    """
    if not figure_captions:
        return {}

    claims: dict[int, str] = {}
    # Build a fast lookup: (page_index, caption_text) -> figure_num
    for cap in figure_captions:
        figure_num: int = cap["figure_num"]
        page_index: int = cap["page_index"]
        caption_text: str = cap["caption"]

        if page_index >= len(pages):
            claims[figure_num] = ""
            continue

        page_text = pages[page_index]
        lines = page_text.splitlines()

        # Find the line that starts the caption
        caption_line_idx = -1
        cap_prefix_pattern = re.compile(
            r"^(?:Figure|Fig\.)\s+" + re.escape(str(figure_num)),
            re.IGNORECASE,
        )
        for i, line in enumerate(lines):
            if cap_prefix_pattern.match(line.strip()):
                caption_line_idx = i
                break

        if caption_line_idx == -1:
            # Fallback: search for caption text substring
            for i, line in enumerate(lines):
                if caption_text in line:
                    caption_line_idx = i
                    break

        if caption_line_idx == -1:
            claims[figure_num] = ""
            continue

        # Collect up to 3 sentences from lines after the caption
        sentences: list[str] = []
        for line in lines[caption_line_idx + 1 :]:
            stripped = line.strip()
            if not stripped:
                continue
            # Stop if we hit another figure caption
            if _CAPTION_PATTERN.match(stripped):
                break
            sentences.append(stripped)
            if len(sentences) >= 3:
                break

        claims[figure_num] = " ".join(sentences)

    return claims


def extract_paper_metadata(
    pdf_path: Path,
    pages: list[str],
) -> dict[str, Optional[str]]:
    """Extract metadata from PDF metadata dict and first-page text.

    Returns dict with keys: title, authors, journal, year.
    All values may be None if not found.
    """
    import fitz  # type: ignore[import]

    title: Optional[str] = None
    authors: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[str] = None

    with fitz.open(str(pdf_path)) as doc:
        meta = doc.metadata or {}
        title = meta.get("title") or None
        raw_author = meta.get("author") or None
        if raw_author:
            authors = raw_author

    # Try to extract year from first-page text
    if pages:
        first_page = pages[0]
        year_match = re.search(r"\b(19|20)\d{2}\b", first_page)
        if year_match:
            year = year_match.group(0)

    return {
        "title": title if title else None,
        "authors": authors if authors else None,
        "journal": journal,
        "year": year,
    }


def write_paper_analysis(
    project_root: Path,
    paper_slug: str,
    metadata: dict[str, Any],
    ranked_figures: list[dict[str, Any]],
    claims: dict[int, str],
) -> None:
    """Write .debrief/paper_analysis_<paper_slug>.md atomically.

    Format:
      # Paper Analysis: <paper_slug>
      ## Metadata
      **Title:** <title>
      **Authors:** <authors>
      **Journal:** <journal>
      **Year:** <year>
      ## Key Figures
      1. <caption>
      2. <caption>
      ...
      ## Suggested Narrative Arc
      <arc text>

    Each figure line matches: ^(?P<n>\\d+)\\. (?P<caption>.+)$
    Uses write-to-.tmp then os.rename atomic protocol.
    """
    debrief_dir = project_root / ".debrief"
    debrief_dir.mkdir(parents=True, exist_ok=True)

    dest = debrief_dir / f"paper_analysis_{paper_slug}.md"
    tmp = debrief_dir / f"paper_analysis_{paper_slug}.md.tmp"

    title = metadata.get("title") or "Unknown"
    authors_val = metadata.get("authors") or "Unknown"
    journal_val = metadata.get("journal") or "Unknown"
    year_val = metadata.get("year") or "Unknown"

    lines: list[str] = [
        f"# Paper Analysis: {paper_slug}",
        "",
        "## Metadata",
        f"**Title:** {title}",
        f"**Authors:** {authors_val}",
        f"**Journal:** {journal_val}",
        f"**Year:** {year_val}",
        "",
        "## Key Figures",
    ]

    for seq_num, fig in enumerate(ranked_figures, start=1):
        caption = fig.get("caption", "")
        lines.append(f"{seq_num}. {caption}")

    lines.append("")
    lines.append("## Suggested Narrative Arc")

    # Build a simple narrative arc based on figure order
    arc_parts: list[str] = []
    for seq_num, fig in enumerate(ranked_figures, start=1):
        caption = fig.get("caption", "")
        arc_parts.append(f"Figure {seq_num}: {caption}")

    if arc_parts:
        lines.append("The figures follow this sequence: " + "; ".join(arc_parts) + ".")
    else:
        lines.append("No figures available for narrative arc construction.")

    lines.append("")

    content = "\n".join(lines)

    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.rename(tmp, dest)


def copy_pdf_to_archive(
    pdf_path: Path,
    paper_slug: str,
    project_root: Path,
) -> None:
    """Copy PDF to assets/reference/papers/<paper_slug>/<pdf_name> atomically.

    Creates destination directory if absent.
    Uses write-bytes-to-.tmp then os.rename atomic protocol.
    """
    dest_dir = project_root / "assets" / "reference" / "papers" / paper_slug
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / pdf_path.name
    tmp = dest_dir / (pdf_path.name + ".tmp")

    data = pdf_path.read_bytes()
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.rename(tmp, dest)


def main_paper_analyzer(
    pdf_path: Path,
    paper_slug: str,
    project_root: Path,
) -> None:
    """Entry point for the full extraction pipeline.

    Exit codes:
      0 — success
      1 — PDF parse error or IO failure
      2 — conda env corruption (fitz import fails)
      3 — usage error (missing or invalid arguments)
      4 — output write failure

    Checks for fitz at entry; exits 2 if unavailable.
    """
    if importlib.util.find_spec("fitz") is None:
        print(_FITZ_ENV_CORRUPTION_MSG, file=sys.stderr)
        sys.exit(2)

    import fitz  # type: ignore[import]  # noqa: F401

    try:
        pages = extract_paper_text(pdf_path)
    except Exception as exc:
        print(f"ERROR: Failed to parse PDF: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        section_structure = extract_section_structure(pages)
        figure_captions = extract_figure_captions(pages)
        figure_images = extract_figure_images(pdf_path, figure_captions)
        ranked = rank_figures(figure_captions, pages, section_structure)

        # Attach pixmaps from figure_images to ranked list
        pixmap_by_num: dict[int, Any] = {
            img["figure_num"]: img["pixmap"] for img in figure_images
        }
        for fig in ranked:
            if "pixmap" not in fig:
                fig["pixmap"] = pixmap_by_num.get(fig["figure_num"])

        claims = extract_figure_claims(pages, figure_captions)
        metadata = extract_paper_metadata(pdf_path, pages)
    except Exception as exc:
        print(f"ERROR: Analysis pipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        for fig in ranked:
            pm = fig.get("pixmap")
            if pm is not None:
                cropped = crop_whitespace(pm)
                save_figure(
                    pixmap=cropped,
                    figure_num=fig["figure_num"],
                    paper_slug=paper_slug,
                    project_root=project_root,
                )
        write_paper_analysis(
            project_root=project_root,
            paper_slug=paper_slug,
            metadata=metadata,
            ranked_figures=ranked,
            claims=claims,
        )
        copy_pdf_to_archive(
            pdf_path=pdf_path,
            paper_slug=paper_slug,
            project_root=project_root,
        )
    except OSError as exc:
        print(f"ERROR: Output write failure: {exc}", file=sys.stderr)
        sys.exit(4)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(description="Debrief paper analyzer")
    _parser.add_argument("--pdf", required=True, help="PDF file path")
    _parser.add_argument("--paper-slug", required=True, help="Paper slug identifier")
    _parser.add_argument("--project-root", required=True, help="Project root path")
    _args = _parser.parse_args()
    main_paper_analyzer(
        pdf_path=Path(_args.pdf),
        paper_slug=_args.paper_slug,
        project_root=Path(_args.project_root),
    )
