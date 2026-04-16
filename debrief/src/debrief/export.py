# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 10: Export Module.

Implements main_export, build_page_list, render_page_to_pdf_buffer,
generate_closing_slide_html, generate_separator_html, and
append_export_log per BC-10.1 through BC-10.9.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Section 9.3.1 standardized env-corruption error message
# ---------------------------------------------------------------------------
_ENV_CORRUPT_MSG = (
    "ERROR: Required package not available in the current environment. "
    "This indicates environment corruption. "
    "Please reinstall the Debrief conda environment: "
    "conda env create -f environment.yml"
)


def main_export(project_root: Path) -> None:
    """Entry point for: python -m debrief.export --project-root <path>

    1. Run style_compiler to ensure CSS is current.
    2. Open sync_playwright() session, launch Chromium, one BrowserContext.
    3. Build page list in canonical PDF order (Section 24.10).
    4. Render each slide to PDF.
    5. Write output/<folder>/deck_v{NNN}.pdf.
    6. Close browser context.
    7. Increment export_count via increment_export_count().
    8. Append entry to output/export_log.jsonl.

    Exit 0 on success. Exit 1 on Playwright or file failure.
    Exit 2 on env corruption.
    """
    # BC-10.7 / BUG-AUDIT-23: Check env dependencies at entry.
    # Order: playwright first (needed for rendering), then fitz
    # (needed for multi-page merge). Both checked before any
    # expensive work so missing-dep failures are fast and clear.
    if importlib.util.find_spec("playwright") is None:
        print(_ENV_CORRUPT_MSG, file=sys.stderr)
        sys.exit(2)
    if importlib.util.find_spec("fitz") is None:
        print(
            "Cannot export: PyMuPDF (fitz) is not importable. "
            "Multi-page PDF merging requires PyMuPDF. "
            "Run 'debrief --rebuild-env' to restore the environment.",
            file=sys.stderr,
        )
        sys.exit(2)

    # BC-10.1: Run style_compiler before opening Playwright
    compiler_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "debrief.style_compiler",
            "style_config.json",
            "assets/style.css",
        ],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if compiler_result.returncode != 0:
        print(
            f"Style compiler failed:\n{compiler_result.stderr}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load state
    try:
        # BC-10.X / BUG-AUDIT-18: the canonical module name is
        # `debrief_state` (underscore), matching the actual filename
        # src/debrief/debrief_state.py. Prior revisions of this file
        # imported from the non-existent `debrief.state` path, which
        # was masked by test_export.py mocking the same phantom key.
        from debrief_state import read_deck_state  # type: ignore[import]

        state = read_deck_state(project_root)
    except Exception as exc:
        print(f"Failed to read deck state: {exc}", file=sys.stderr)
        sys.exit(1)

    # Load style_config
    style_config_path = project_root / "style_config.json"
    try:
        with style_config_path.open(encoding="utf-8") as f:
            style_config: dict[str, Any] = json.load(f)
    except Exception as exc:
        print(f"Failed to read style_config.json: {exc}", file=sys.stderr)
        sys.exit(1)

    # Determine presentation folder and export version
    if not state.presentations:
        print("No presentation record found.", file=sys.stderr)
        sys.exit(1)

    presentation = state.presentations[-1]
    folder = presentation.folder
    output_dir = project_root / "output" / folder
    output_dir.mkdir(parents=True, exist_ok=True)

    # BUG-AUDIT-23 / BC-10.4: filesystem-derived versioning. Scan the
    # output directory for existing deck_v*.pdf files and pick (max + 1).
    # This replaces the old presentation.export_count + 1 pattern, which
    # could drift if state was rolled back or corrupted. Consistent with
    # handout's BC-11.17 approach.
    existing_versions: list[int] = []
    for existing in output_dir.glob("deck_v*.pdf"):
        stem = existing.stem
        if stem.startswith("deck_v"):
            suffix = stem[len("deck_v"):]
            try:
                existing_versions.append(int(suffix))
            except ValueError:
                continue
    version = (max(existing_versions) + 1) if existing_versions else 1
    pdf_file = output_dir / f"deck_v{version:03d}.pdf"

    # Build page list
    pages = build_page_list(state, project_root)
    slide_count = len(pages)

    # BC-10.2: One BrowserContext per export.
    # BUG-AUDIT-23: find_spec check at entry guarantees playwright is
    # importable, so no try/except ImportError here.
    from playwright.sync_api import sync_playwright  # type: ignore[import]

    error_message: Optional[str] = None
    pdf_path_str = ""

    try:
        layout = style_config.get("layout", {})
        width = int(layout.get("slide_width", 1920))
        height = int(layout.get("slide_height", 1080))

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(
                viewport={"width": width, "height": height},
            )
            try:
                pdf_buffers: list[bytes] = []
                for page_descriptor in pages:
                    pw_page = context.new_page()
                    try:
                        buf = render_page_to_pdf_buffer(
                            pw_page, page_descriptor, project_root
                        )
                        pdf_buffers.append(buf)
                    finally:
                        pw_page.close()

                # BUG-AUDIT-23: merge PDF buffers using PyMuPDF (fitz).
                # fitz is guaranteed importable after the entry check.
                # No except ImportError fallback — the old fallback
                # silently wrote only the first page for multi-page
                # decks, producing silent data loss. If fitz raises a
                # runtime error here, let it propagate as a real bug.
                import fitz  # type: ignore[import]

                merged = fitz.open()
                for buf in pdf_buffers:
                    with fitz.open(stream=buf, filetype="pdf") as doc:
                        merged.insert_pdf(doc)
                merged.save(str(pdf_file))
                merged.close()

            finally:
                context.close()
                browser.close()

        pdf_path_str = str(Path("output") / folder / f"deck_v{version:03d}.pdf")

    except SystemExit:
        raise
    except Exception as exc:
        error_message = str(exc)
        print(f"Export failed: {error_message}", file=sys.stderr)
        append_export_log(
            project_root=project_root,
            presentation_folder=folder,
            version=version,
            slide_count=slide_count,
            playwright_exit_status=1,
            pdf_path="",
            error_message=error_message,
        )
        sys.exit(1)

    # BUG-AUDIT-23: no state mutation. Version is filesystem-derived
    # (BC-10.4 amendment), so increment_export_count and
    # write_deck_state are no longer called. The old block was:
    #   increment_export_count(state, folder)
    #   write_deck_state(project_root, state)
    # with a catch-all except that silently swallowed errors.

    # BC-10.5: append log AFTER PDF is written
    append_export_log(
        project_root=project_root,
        presentation_folder=folder,
        version=version,
        slide_count=slide_count,
        playwright_exit_status=0,
        pdf_path=pdf_path_str,
        error_message=None,
    )


def build_page_list(
    state: Any,
    project_root: Path,
) -> list[dict[str, Any]]:
    """Build the ordered list of pages for the PDF in canonical order per
    Section 24.10:
    1. Approved slides with backup=False in array order.
    2. Closing slide if closing_slide == 'empty' (in-memory styled slide).
    3. Separator if separator_position is not None
       (in-memory from separator_content).
    4. Approved slides with backup=True in array order.

    Each page is a dict: {"type": "slide"|"closing"|"separator",
    "path": Path|None, "content": str|None}.
    """
    pages: list[dict[str, Any]] = []

    # 1. Main approved slides (backup=False)
    for slide in state.slides:
        if slide.status != "approved":
            continue
        if slide.backup:
            continue
        slide_path = project_root / "slides" / f"{slide.slug}.html"
        pages.append(
            {
                "type": "slide",
                "path": slide_path,
                "content": None,
                "backup": False,
            }
        )

    # 2. Closing slide if closing_slide == 'empty'
    if getattr(state, "closing_slide", None) == "empty":
        # Load style_config for generating HTML
        style_config = _load_style_config(project_root)
        closing_html = generate_closing_slide_html(style_config)
        pages.append(
            {
                "type": "closing",
                "path": None,
                "content": closing_html,
            }
        )

    # 3. Separator if any presentation has separator_position set
    separator_added = False
    for pres in getattr(state, "presentations", []):
        if (
            not separator_added
            and getattr(pres, "separator_position", None) is not None
        ):
            sep_content = getattr(pres, "separator_content", "") or ""
            style_config = _load_style_config(project_root)
            sep_html = generate_separator_html(sep_content, style_config)
            pages.append(
                {
                    "type": "separator",
                    "path": None,
                    "content": sep_html,
                }
            )
            separator_added = True

    # 4. Backup approved slides (backup=True)
    for slide in state.slides:
        if slide.status != "approved":
            continue
        if not slide.backup:
            continue
        slide_path = project_root / "slides" / f"{slide.slug}.html"
        pages.append(
            {
                "type": "slide",
                "path": slide_path,
                "content": None,
                "backup": True,
            }
        )

    return pages


def _load_style_config(project_root: Path) -> dict[str, Any]:
    """Load style_config.json from project_root, return empty dict on error."""
    style_config_path = project_root / "style_config.json"
    if style_config_path.exists():
        try:
            with style_config_path.open(encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception:
            pass
    return {}


def render_page_to_pdf_buffer(
    page: Any,
    page_descriptor: dict[str, Any],
    project_root: Path,
) -> bytes:
    """Render one page (slide file or in-memory HTML) to a PDF buffer.

    For 'slide' type: navigate to file:// URL, wait for load.
    For 'closing'/'separator' type: set_content() with generated HTML.
    Return the PDF bytes for the page.
    """
    page_type = page_descriptor["type"]
    if page_type == "slide":
        slide_path = page_descriptor["path"]
        url = slide_path.as_uri()
        page.goto(url, wait_until="load")
    else:
        content = page_descriptor.get("content") or ""
        page.set_content(content, wait_until="load")

    pdf_bytes: bytes = page.pdf(
        print_background=True,
        width="1920px",
        height="1080px",
    )
    return pdf_bytes


def generate_closing_slide_html(style_config: dict[str, Any]) -> str:
    """Generate minimal HTML for a styled empty closing slide using only
    CSS custom properties from the locked style config. No text content.
    """
    colors = style_config.get("colors", {})
    bg = colors.get("background", "#ffffff")
    primary = colors.get("primary", "#1a1a2e")

    layout = style_config.get("layout", {})
    width = layout.get("slide_width", "1920")
    height = layout.get("slide_height", "1080")

    # Use inline styles to avoid leaving CSS text after tag-stripping.
    # CSS custom properties (--color-*) appear as inline style attributes.
    body_style = (
        f"margin:0;padding:0;width:{width}px;height:{height}px;"
        f"background-color:{bg};overflow:hidden;"
        f"--color-background:{bg};--color-primary:{primary};"
        f"--slide-width:{width}px;--slide-height:{height}px;"
    )
    div_style = (
        f"width:{width}px;height:{height}px;"
        f"background-color:var(--color-background,{bg});"
        "display:flex;align-items:center;justify-content:center;"
    )

    html = (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="UTF-8">'
        f'<meta name="viewport" content="width={width}, height={height}">'
        "</head>"
        f'<body style="{body_style}">'
        f'<div class="slide" style="{div_style}"></div>'
        "</body>"
        "</html>"
    )
    return html


def generate_separator_html(
    separator_content: str,
    style_config: dict[str, Any],
) -> str:
    """Generate HTML for the separator slide from separator_content.

    separator_content is one of: 'acknowledgments', 'questions', 'summary',
    or custom text. Uses CSS custom properties from locked style config.
    """
    # Map recognised keywords to display titles
    _LABELS: dict[str, str] = {
        "acknowledgments": "Acknowledgments",
        "questions": "Questions?",
        "summary": "Summary",
    }
    label = _LABELS.get(separator_content.lower(), separator_content)

    colors = style_config.get("colors", {})
    bg = colors.get("background", "#ffffff")
    primary = colors.get("primary", "#1a1a2e")
    text_primary = colors.get("text_primary", "#000000")

    typography = style_config.get("typography", {})
    heading_font = typography.get("heading_font_family", "Inter, sans-serif")
    heading_size = typography.get("heading_size_base", "2rem")
    heading_weight = typography.get("heading_weight", "700")

    layout = style_config.get("layout", {})
    width = layout.get("slide_width", "1920")
    height = layout.get("slide_height", "1080")

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={width}, height={height}">
<style>
:root {{
  --color-background: {bg};
  --color-primary: {primary};
  --color-text-primary: {text_primary};
  --heading-font-family: {heading_font};
  --heading-size-base: {heading_size};
  --heading-weight: {heading_weight};
  --slide-width: {width}px;
  --slide-height: {height}px;
}}
* {{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}}
html, body {{
  width: var(--slide-width);
  height: var(--slide-height);
  background-color: var(--color-background);
  overflow: hidden;
}}
.slide {{
  width: var(--slide-width);
  height: var(--slide-height);
  background-color: var(--color-background);
  display: flex;
  align-items: center;
  justify-content: center;
}}
.separator-label {{
  font-family: var(--heading-font-family);
  font-size: var(--heading-size-base);
  font-weight: var(--heading-weight);
  color: var(--color-text-primary);
  text-align: center;
}}
</style>
</head>
<body>
<div class="slide">
  <h1 class="separator-label">{label}</h1>
</div>
</body>
</html>"""
    return html


def append_export_log(
    project_root: Path,
    presentation_folder: str,
    version: int,
    slide_count: int,
    playwright_exit_status: int,
    pdf_path: str,
    error_message: Optional[str],
) -> None:
    """Append one entry to output/export_log.jsonl per REQ-EXPORT-5 schema.

    Schema: {"timestamp": str, "presentation_folder": str, "version": int,
             "slide_count": int, "playwright_exit_status": int,
             "pdf_path": str, "error_message": str | null}.
    All 7 fields are required per REQ-EXPORT-5. On success, error_message
    is null. On failure, error_message contains the error text and pdf_path
    may be empty if no PDF was produced.
    """
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry: dict[str, Any] = {
        "timestamp": timestamp,
        "presentation_folder": presentation_folder,
        "version": version,
        "slide_count": slide_count,
        "playwright_exit_status": playwright_exit_status,
        "pdf_path": pdf_path,
        "error_message": error_message,
    }
    log_path = project_root / "output" / "export_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
