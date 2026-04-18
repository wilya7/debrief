# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 7: Style Dialog — modality adapters and slide sampling utilities.

This module provides:
  - adapt_pptx   -- PPTX -> PNG via LibreOffice headless
  - adapt_pdf    -- PDF  -> PNG via PyMuPDF (fitz)
  - adapt_html_file -- single HTML -> PNG via Playwright
  - adapt_html_dir  -- HTML directory -> PNGs via Playwright
  - sample_slides   -- deterministic slide-index sampler
  - main_style_analyzer -- dispatch entry point
  - main_style_guide_generator -- style guide synthesis
  - main_preview_renderer      -- preview rendering entry point
  - render_html_to_png         -- single-page screenshot helper

No LLM/VLM SDK imports are present in this module.
No Playwright context is stored as a module-level global.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Helper: deterministic slide sampling (BC-7.6)
# ---------------------------------------------------------------------------


def sample_slides(total: int, cap: int = 10) -> list[int]:
    """Return 0-based indices of slides to render.

    If total <= cap: return list(range(total)).
    Otherwise: include index 0 (first) and index total-1 (last), plus
    (cap-2) evenly-spaced indices from the interior range [1, total-2].
    Result is sorted ascending with no duplicates.
    """
    if total <= cap:
        return list(range(total))

    if cap == 1:
        return [0]

    if cap == 2:
        return [0, total - 1]

    # cap >= 3: always include first and last, fill middle with (cap-2) items.
    middle_count = cap - 2
    # Interior indices: [1 .. total-2]
    interior_size = total - 2  # number of interior slots

    # Evenly space middle_count samples across interior_size positions.
    # Use the formula: round(i * (interior_size - 1) / (middle_count - 1))
    # for middle_count > 1, or just pick the midpoint for middle_count == 1.
    middle: list[int] = []
    if middle_count == 1:
        # Single midpoint (offset +1 because interior starts at 1)
        mid = 1 + (interior_size - 1) // 2
        middle = [mid]
    else:
        for i in range(middle_count):
            pos = round(i * (interior_size - 1) / (middle_count - 1))
            middle.append(1 + pos)  # offset by 1 (interior starts at 1)

    indices = sorted(set([0, total - 1] + middle))
    return indices


# ---------------------------------------------------------------------------
# PPTX adapter (BC-7.3, BC-7.4)
# ---------------------------------------------------------------------------


def adapt_pptx(reference: Path, project_root: Path) -> None:
    """Convert .pptx to per-slide PNG batch via LibreOffice + PyMuPDF.

    BUG-AUDIT-39: two-step conversion (PPTX → PDF → per-page PNG).
    The old single-step ``--convert-to png`` only rendered the first
    slide. The PDF intermediate renders all slides.

    - Cap at 10 slides using sample_slides().
    - Extract theme metadata via python-pptx.
    - Write analyzer_metadata.json.
    - Copy reference to assets/reference/<filename>.
    - Use -env:UserInstallation=file:///<tmp> for LibreOffice isolation.
    - 120-second timeout; exits 1 on timeout.
    """
    pptx_mod = importlib.import_module("pptx")
    fitz = importlib.import_module("fitz")
    fitz.TOOLS.mupdf_display_errors(False)

    slides_out = project_root / "assets" / "reference" / "slides"
    slides_out.mkdir(parents=True, exist_ok=True)

    ref_dest = project_root / "assets" / "reference" / reference.name
    if not ref_dest.exists():
        shutil.copy2(reference, ref_dest)

    # BUG-AUDIT-42: discover soffice path (cross-platform)
    try:
        from launcher import discover_soffice  # type: ignore[import]
        soffice_bin = str(discover_soffice(project_root))
    except (ImportError, FileNotFoundError):
        soffice_bin = shutil.which("soffice") or "soffice"

    # Step 1: PPTX → PDF via LibreOffice (BC-7.3, BC-7.4)
    with tempfile.TemporaryDirectory() as tmp_dir:
        profile_uri = f"file:///{tmp_dir}/profile"
        cmd = [
            soffice_bin,
            "--headless",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "pdf",
            "--outdir",
            tmp_dir,
            str(reference),
        ]
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            print(
                "ERROR: LibreOffice conversion timed out after 120 seconds.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Find the produced PDF
        pdf_candidates = list(Path(tmp_dir).glob("*.pdf"))
        if not pdf_candidates:
            print(
                f"ERROR: LibreOffice produced no PDF from {reference.name}. "
                f"stderr: {result.stderr.decode(errors='replace')[:200]}",
                file=sys.stderr,
            )
            sys.exit(1)
        pdf_path = pdf_candidates[0]

        # Step 2: PDF → per-page PNG via fitz (same approach as adapt_pdf)
        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        sampled = sample_slides(page_count)

        for idx in sampled:
            if idx >= page_count:
                continue
            page = doc[idx]
            pix = page.get_pixmap(dpi=150)
            out_name = f"slide_{idx + 1:03d}.png"
            pix.save(str(slides_out / out_name))
        doc.close()

    # Extract metadata via python-pptx
    prs = pptx_mod.Presentation(str(reference))
    slide_count = len(prs.slides)

    metadata: dict = {
        "slide_count": slide_count,
        "sampled_indices": sample_slides(slide_count),
    }

    # Theme colors / fonts (best-effort)
    # BUG-AUDIT-43 / BUG-ST-1: try run.font.name first, then
    # para.font.name (paragraph-level default), then slide layout
    # default. python-pptx returns None when the font is inherited
    # from the slide master rather than set on the run.
    try:
        font_names: list[str] = []
        font_sizes: list[float] = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        # Try paragraph-level font as fallback
                        para_font = getattr(para.font, "name", None)
                        for run in para.runs:
                            fn = run.font.name or para_font
                            if fn:
                                font_names.append(fn)
                            fs = run.font.size
                            if fs is not None:
                                font_sizes.append(fs / 12700)  # EMU -> pt

        # BUG-AUDIT-55 / BUG-ST-4: resolve theme fonts from the PPTX ZIP.
        # Slide master elements return placeholders (+mj-lt, +mn-lt);
        # the actual font names live in ppt/theme/theme1.xml.
        try:
            import zipfile
            from lxml import etree as _etree

            _ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
            with zipfile.ZipFile(str(reference)) as zf:
                for name in zf.namelist():
                    if "theme" in name and name.endswith(".xml"):
                        root = _etree.fromstring(zf.read(name))
                        for major in root.findall(".//a:majorFont/a:latin", _ns):
                            tf = major.get("typeface")
                            if tf and tf not in font_names:
                                font_names.append(tf)
                        for minor in root.findall(".//a:minorFont/a:latin", _ns):
                            tf = minor.get("typeface")
                            if tf and tf not in font_names:
                                font_names.append(tf)
        except Exception:
            pass

        metadata["font_families"] = list(dict.fromkeys(font_names))
        metadata["font_sizes"] = sorted(set(font_sizes))
    except Exception:
        pass

    # Slide dimensions
    try:
        metadata["slide_width_emu"] = prs.slide_width
        metadata["slide_height_emu"] = prs.slide_height
    except Exception:
        pass

    draft_dir = project_root / ".debrief" / "draft"
    draft_dir.mkdir(parents=True, exist_ok=True)
    meta_path = draft_dir / "analyzer_metadata.json"
    _atomic_write_json(meta_path, metadata)


# ---------------------------------------------------------------------------
# PDF adapter (BC-7.5)
# ---------------------------------------------------------------------------


def adapt_pdf(reference: Path, project_root: Path) -> None:
    """Convert .pdf to PNG batch via PyMuPDF at 150 DPI.

    - Cap at 10 pages using sample_slides().
    - Set paper_detected: true in analyzer_metadata.json if > 50 pages.
    - Copy reference to assets/reference/<filename>.
    """
    fitz = importlib.import_module("fitz")

    slides_out = project_root / "assets" / "reference" / "slides"
    slides_out.mkdir(parents=True, exist_ok=True)

    ref_dest = project_root / "assets" / "reference" / reference.name
    if not ref_dest.exists():
        shutil.copy2(reference, ref_dest)

    doc = fitz.open(str(reference))
    page_count = len(doc)
    paper_detected = page_count > 50

    indices = sample_slides(page_count)
    dpi = 150
    zoom = dpi / 72.0
    mat = None
    try:
        fitz_mat = importlib.import_module("fitz")
        mat = fitz_mat.Matrix(zoom, zoom)
    except Exception:
        pass

    for idx in indices:
        page = doc[idx]
        try:
            if mat is not None:
                pix = page.get_pixmap(matrix=mat)
            else:
                pix = page.get_pixmap()
            out_path = slides_out / f"slide_{idx:04d}.png"
            pix.save(str(out_path))
        except Exception:
            pass

    draft_dir = project_root / ".debrief" / "draft"
    draft_dir.mkdir(parents=True, exist_ok=True)
    metadata: dict = {
        "page_count": page_count,
        "sampled_indices": indices,
        "paper_detected": paper_detected,
    }
    meta_path = draft_dir / "analyzer_metadata.json"
    _atomic_write_json(meta_path, metadata)


# ---------------------------------------------------------------------------
# HTML adapters (BC-7.2)
# ---------------------------------------------------------------------------


def adapt_html_file(reference: Path, project_root: Path) -> None:
    """Render a single .html reference to PNG via Playwright.

    Opens its own sync_playwright() context per invocation (BC-7.2).
    Screenshot size: 1920x1080. wait_until='networkidle' + 2s delay.
    Copies reference to assets/reference/<filename>.
    """
    sync_api = importlib.import_module("playwright.sync_api")
    sync_playwright = sync_api.sync_playwright

    slides_out = project_root / "assets" / "reference" / "slides"
    slides_out.mkdir(parents=True, exist_ok=True)

    ref_dest = project_root / "assets" / "reference" / reference.name
    if not ref_dest.exists():
        shutil.copy2(reference, ref_dest)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(
            f"file://{reference.resolve()}",
            wait_until="networkidle",
        )
        time.sleep(2)
        out_path = slides_out / f"{reference.stem}.png"
        page.screenshot(path=str(out_path))
        browser.close()


def adapt_html_dir(reference: Path, project_root: Path) -> None:
    """Render up to 10 .html files from a directory via Playwright.

    Selection: first + last + 8 middle in alphabetical order (BC-7.6).
    Opens its own sync_playwright() context per invocation (BC-7.2).
    Copies reference directory to assets/reference/<dirname>/.
    """
    sync_api = importlib.import_module("playwright.sync_api")
    sync_playwright = sync_api.sync_playwright

    slides_out = project_root / "assets" / "reference" / "slides"
    slides_out.mkdir(parents=True, exist_ok=True)

    ref_dest_dir = project_root / "assets" / "reference" / reference.name
    if not ref_dest_dir.exists():
        shutil.copytree(reference, ref_dest_dir)

    html_files = sorted(reference.glob("*.html"))
    indices = sample_slides(len(html_files))
    selected = [html_files[i] for i in indices]

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})
        for html_file in selected:
            page.goto(
                f"file://{html_file.resolve()}",
                wait_until="networkidle",
            )
            time.sleep(2)
            out_path = slides_out / f"{html_file.stem}.png"
            page.screenshot(path=str(out_path))
        browser.close()


# ---------------------------------------------------------------------------
# Main entry point: style analyzer dispatch
# ---------------------------------------------------------------------------


def main_style_analyzer(reference: Path, project_root: Path) -> None:
    """Dispatch to the correct modality adapter based on reference type.

    Exit codes:
      0 -- success
      1 -- unsupported reference type or reference file not found
      2 -- conda env corruption (any required import fails)
      3 -- usage error (missing or invalid arguments)
    """
    if not reference.exists():
        print(
            f"ERROR: Reference not found: {reference}",
            file=sys.stderr,
        )
        sys.exit(1)

    suffix = reference.suffix.lower()

    if reference.is_dir():
        adapt_html_dir(reference, project_root)
    elif suffix == ".pptx":
        adapt_pptx(reference, project_root)
    elif suffix == ".pdf":
        adapt_pdf(reference, project_root)
    elif suffix in (".html", ".htm"):
        adapt_html_file(reference, project_root)
    else:
        print(
            f"ERROR: Unsupported reference type: {suffix}",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Style guide generator (BC-7.9)
# ---------------------------------------------------------------------------


def main_style_guide_generator(project_root: Path) -> None:
    """Synthesize a first-draft style_guide.md from local files only.

    No network calls, no subprocess calls, no LLM API calls.
    """
    draft_dir = project_root / ".debrief" / "draft"
    draft_dir.mkdir(parents=True, exist_ok=True)

    style_config_path = draft_dir / "style_config.json"
    derived_guide_path = draft_dir / "derived_style_guide.md"
    output_path = draft_dir / "style_guide.md"

    lines: list[str] = ["# Style Guide (Draft)\n\n"]

    if style_config_path.exists():
        try:
            config = json.loads(style_config_path.read_text(encoding="utf-8"))
            lines.append("## Observed Style Characteristics\n\n")
            for key, value in config.items():
                lines.append(f"- **{key}**: {value}\n")
            lines.append("\n")
        except Exception:
            pass

    if derived_guide_path.exists():
        lines.append("## Derived Style Notes\n\n")
        lines.append(derived_guide_path.read_text(encoding="utf-8"))
        lines.append("\n")

    content = "".join(lines)
    tmp_path = output_path.with_suffix(".md.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.rename(tmp_path, output_path)


# ---------------------------------------------------------------------------
# Preview renderer (BC-7.2, BC-7.10)
# ---------------------------------------------------------------------------


def render_html_to_png(
    page: "object",
    html_path: Path,
    output_path: Path,
) -> None:
    """Navigate to file://<html_path>, screenshot to output_path.

    Wait for networkidle plus 2-second delay.
    Raises RuntimeError on navigation or screenshot failure.
    """
    try:
        page.goto(  # type: ignore[attr-defined]
            f"file://{html_path.resolve()}",
            wait_until="networkidle",
        )
        time.sleep(2)
        page.screenshot(path=str(output_path))  # type: ignore[attr-defined]
    except Exception as exc:
        raise RuntimeError(
            f"Failed to render {html_path} to {output_path}: {exc}"
        ) from exc


def main_preview_renderer(
    project_root: Path,
    input_dir: Path,
    output_dir: Path,
) -> None:
    """Render each .html in input_dir to a 1920x1080 PNG in output_dir.

    Opens one sync_playwright() session per invocation (BC-7.2).
    Closes session in a finally block (BC-7.10).
    Exits 1 if total render time > 60 seconds.
    """
    if importlib.util.find_spec("playwright") is None:
        _env_corruption_exit()

    sync_api = importlib.import_module("playwright.sync_api")
    sync_playwright = sync_api.sync_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    html_files = sorted(input_dir.glob("*.html"))

    start = time.monotonic()
    pw_ctx = sync_playwright()
    pw = pw_ctx.__enter__()
    try:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            for html_file in html_files:
                out_path = output_dir / f"{html_file.stem}.png"
                render_html_to_png(page, html_file, out_path)
                elapsed = time.monotonic() - start
                if elapsed > 60:
                    print(
                        "WARNING: Preview rendering exceeded 60 seconds.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
        finally:
            browser.close()
    finally:
        pw_ctx.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write data as JSON to path atomically."""
    tmp_path = path.with_suffix(".json.tmp")
    content = json.dumps(data, indent=2, sort_keys=True)
    tmp_path.write_text(content, encoding="utf-8")
    fd = os.open(str(tmp_path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rename(tmp_path, path)


def _env_corruption_exit() -> None:
    """Print Section 9.3.1 env-corruption error and exit with code 2."""
    print(
        "ERROR: Conda environment is corrupted or incomplete. "
        "Required packages are missing. "
        "Run: conda env update --file environment.yml --prune",
        file=sys.stderr,
    )
    sys.exit(2)
