# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 11: Utility Skills.

Entry-point helpers for the /debrief:view, /debrief:script,
/debrief:handout, /debrief:save, /debrief:reset, and /debrief:quit
skills.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import webbrowser
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Imports from Unit 2 (added to sys.path by conftest.py)
# ---------------------------------------------------------------------------
from debrief_state import (  # type: ignore[import]
    increment_handout_count,
    increment_script_count,
    read_deck_state,
    read_debrief_state,
    sanitize_identifier,
    write_deck_state,
    write_debrief_state,
)

# ---------------------------------------------------------------------------
# Env-corruption message (Section 9.3.1)
# ---------------------------------------------------------------------------

_ENV_CORRUPTION_MSG = (
    "ERROR: playwright is not installed or the conda environment is corrupt.\n"
    "Run: conda env create -f environment.yml  (see Section 9.3.1)\n"
    "The playwright package is required for handout PDF generation.\n"
)

# ---------------------------------------------------------------------------
# sanitize_save_label (BC-11.9)
# ---------------------------------------------------------------------------


def sanitize_save_label(label: str) -> str:
    """Sanitize a /debrief:save snapshot label for use as a directory name.

    Applies the Debrief Identifier Sanitization Algorithm (Section 24.10.1)
    with max_length=50.  Returns the sanitized string, or "untitled" if
    the result would be empty after sanitization.

    Default timestamp labels (YYYYMMDD_HHMMSS) are NOT passed through this
    function -- they bypass sanitization and are used verbatim.
    """
    return sanitize_identifier(label, max_length=50)


# ---------------------------------------------------------------------------
# parse_view_query (BC-11.1/BC-11.2/BC-11.3 — REQ-VIEW-1)
# ---------------------------------------------------------------------------


def parse_view_query(
    query: str,
    state: Any,
) -> list[Any]:
    """Parse the query argument and return matching slide records.

    Query forms per REQ-VIEW-1:
      'all'               -> all approved slides (non-backup)
      '<slug>'            -> single slide by slug
      'group:<group_id>'  -> all slides in group_id
      'last'              -> last approved slide (non-backup)
      'backup'            -> all backup slides (approved)
    Returns empty list if no slides match.
    """
    slides = state.slides

    if query == "all":
        return [s for s in slides if s.status == "approved" and not s.backup]

    if query == "last":
        approved = [s for s in slides if s.status == "approved" and not s.backup]
        if not approved:
            return []
        return [approved[-1]]

    if query == "backup":
        return [s for s in slides if s.status == "approved" and s.backup]

    if query.startswith("group:"):
        group_id = query[len("group:") :]
        return [s for s in slides if s.status == "approved" and s.group_id == group_id]

    # Single-slug lookup
    for s in slides:
        if s.slug == query and s.status != "discarded":
            return [s]

    return []


# ---------------------------------------------------------------------------
# generate_view_html (BC-11.4)
# ---------------------------------------------------------------------------


def _read_screenshot_b64(project_root: Path, slug: str) -> Optional[str]:
    """Read the screenshot for a slide as a base64 data URI, or None."""
    import base64

    for ext in ("png", "jpg", "jpeg", "webp"):
        path = project_root / "output" / "screenshots" / f"{slug}.{ext}"
        if path.exists():
            mime = "image/png" if ext == "png" else f"image/{ext}"
            data = base64.b64encode(path.read_bytes()).decode()
            return f"data:{mime};base64,{data}"
    return None


def generate_view_html(slides: list[Any], project_root: Path) -> str:
    """Generate a self-contained HTML file tiling slides as thumbnail cards.

    Each card: screenshot image, slug label (small monospace), slide title.
    Single-slide query: render full-size instead of thumbnail.
    No external CSS or JS dependencies.
    """
    is_single = len(slides) == 1
    img_width = "100%" if is_single else "280px"

    card_style = (
        "display:inline-block;margin:8px;padding:8px;"
        "border:1px solid #ccc;border-radius:4px;"
        "vertical-align:top;text-align:center;"
        "background:#fafafa;"
    )

    cards_html = []
    for slide in slides:
        img_src = _read_screenshot_b64(project_root, slide.slug)
        if img_src:
            img_tag = (
                f'<img src="{img_src}" alt="{slide.slug}" '
                f'style="width:{img_width};max-width:100%;">'
            )
        else:
            img_tag = (
                f'<div style="width:{img_width};height:160px;'
                f"background:#eee;display:flex;"
                f'align-items:center;justify-content:center;">'
                f"[no screenshot]</div>"
            )
        card = (
            f'<div style="{card_style}">'
            f"{img_tag}"
            f'<br><code style="font-size:0.75em;">{slide.slug}</code>'
            f'<br><span style="font-size:0.85em;">{slide.title}</span>'
            f"</div>"
        )
        cards_html.append(card)

    body = "\n".join(cards_html)
    count_label = f"{len(slides)} slide(s)"

    html = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>Debrief View</title>\n"
        "<style>\n"
        "body{font-family:sans-serif;margin:16px;background:#fff;}\n"
        "h1{font-size:1.1em;margin-bottom:8px;}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"<h1>Slide View &mdash; {count_label}</h1>\n"
        f"{body}\n"
        "</body>\n"
        "</html>"
    )
    return html


# ---------------------------------------------------------------------------
# main_view (BC-11.1, BC-11.2, BC-11.3)
# ---------------------------------------------------------------------------


def main_view(query: str, project_root: Path) -> None:
    """Entry point for: python -m debrief.view <query> --project-root <path>

    Read deck_state.json and debrief_state.json. Parse query. Collect matching
    slide screenshots. Generate output/view.html. Open in default browser.
    Exit 0 on success. Exit 1 if no slides match the query.
    """
    deck_state = read_deck_state(project_root)
    debrief_state = read_debrief_state(project_root)

    phase = debrief_state.phase

    # BC-11.1: Phase 1 and 2 — no slides yet
    if phase in ("discovery", "style"):
        msg = (
            "No slides yet. The view becomes available once slide "
            "production begins in Phase 3."
        )
        print(msg, file=sys.stderr)
        sys.exit(0)

    # BC-11.3: Red-green deferral
    rg_active = (
        debrief_state.red_green_iteration > 0
        and debrief_state.red_green_started_at is not None
    )
    if rg_active:
        debrief_state.view_deferred = True
        write_debrief_state(project_root, debrief_state)
        return

    # BC-11.1: Phase 3 — yield to routing (set pre_view_state, pending_gate)
    # BC-11.2: Do not overwrite existing pre_view_state
    if phase == "production":
        if debrief_state.pre_view_state is None:
            debrief_state.pre_view_state = {
                "phase": debrief_state.phase,
                "sub_phase": debrief_state.sub_phase,
            }
            debrief_state.pending_gate = "G3.V_view_dispatch"
            write_debrief_state(project_root, debrief_state)

        # Still generate and display the view in production phase
        slides = parse_view_query(query, deck_state)
        if not slides:
            sys.exit(1)

        html = generate_view_html(slides, project_root)
        view_path = project_root / "output" / "view.html"
        view_path.parent.mkdir(parents=True, exist_ok=True)
        view_path.write_text(html, encoding="utf-8")
        webbrowser.open(view_path.as_uri())
        return

    # Phase 4 / complete — Run-and-return mode (no routing side effects)
    slides = parse_view_query(query, deck_state)
    if not slides:
        sys.exit(1)

    html = generate_view_html(slides, project_root)
    view_path = project_root / "output" / "view.html"
    view_path.parent.mkdir(parents=True, exist_ok=True)
    view_path.write_text(html, encoding="utf-8")
    webbrowser.open(view_path.as_uri())


# ---------------------------------------------------------------------------
# generate_script_content (BC-11.6 / REQ-SCRIPT-3)
# ---------------------------------------------------------------------------


def generate_script_content(
    deck_brief_content: str,
    slides: list[Any],
    folder: str,
) -> str:
    """Produce script markdown per REQ-SCRIPT-3.

    One section per slide with title, key talking points, transitions,
    estimated speaking time.
    """
    lines: list[str] = []
    lines.append("# Speaker Script")
    lines.append("")
    lines.append(f"**Presentation folder:** `{folder}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    if not slides:
        lines.append("*(No approved slides found.)*")
        return "\n".join(lines)

    for i, slide in enumerate(slides):
        lines.append(f"## Slide {i + 1}: {slide.title}")
        lines.append("")
        lines.append(f"**Slug:** `{slide.slug}`")
        lines.append("")
        lines.append("### Key talking points")
        lines.append("")
        if slide.content_summary:
            lines.append(f"- {slide.content_summary}")
        else:
            lines.append("- *(No content summary available.)*")
        lines.append("")
        lines.append("### Transition")
        lines.append("")
        if i < len(slides) - 1:
            next_slide = slides[i + 1]
            lines.append(
                f"Lead into **{next_slide.title}** by connecting the "
                f"key findings above."
            )
        else:
            lines.append("Conclude and invite questions.")
        lines.append("")
        lines.append("### Estimated speaking time")
        lines.append("")
        lines.append("~1–2 minutes")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main_script_generator (BC-11.5, BC-11.6)
# ---------------------------------------------------------------------------


def main_script_generator(project_root: Path) -> None:
    """Entry point for: python -m debrief.script_generator --project-root <path>

    Read deck_brief.md and deck_state.json. Write
    output/<folder>/script_v{NNN}.md. Increment script_count.
    Print path to stderr.
    """
    deck_state = read_deck_state(project_root)

    # BC-11.5: precondition check
    if not deck_state.presentations:
        print(
            "No export has been done yet. Run /debrief:export first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # BC-11.6: use most recent (last) presentation folder
    pres = deck_state.presentations[-1]
    folder = pres.folder
    version = pres.script_count + 1
    script_filename = f"script_v{version:03d}.md"

    # Read deck brief
    brief_path = project_root / "deck_brief.md"
    if brief_path.exists():
        deck_brief_content = brief_path.read_text(encoding="utf-8")
    else:
        deck_brief_content = ""

    # Get approved slides
    approved = [s for s in deck_state.slides if s.status == "approved"]

    content = generate_script_content(deck_brief_content, approved, folder)

    out_dir = project_root / "output" / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / script_filename
    out_path.write_text(content, encoding="utf-8")

    # Increment script_count and write state
    increment_script_count(deck_state, folder)
    write_deck_state(project_root, deck_state)

    print(str(out_path), file=sys.stderr)


# ---------------------------------------------------------------------------
# generate_layout_html (BC-11.6, REQ-HAND-4)
# ---------------------------------------------------------------------------


def generate_layout_html(
    mode: str,
    slides: list[Any],
    project_root: Path,
) -> str:
    """Generate the layout HTML combining slide screenshots and explanatory text.

    Mode '2up': two slides per page, detailed notes.
    Mode '4up': four slides per page (2x2 grid), condensed notes.
    Notes from content_summary fields, falling back to script if available.
    """
    import base64

    is_2up = mode == "2up"

    per_page = 2 if is_2up else 4

    def _img_b64(slug: str) -> Optional[str]:
        for ext in ("png", "jpg", "jpeg", "webp"):
            p = project_root / "output" / "screenshots" / f"{slug}.{ext}"
            if p.exists():
                mime = "image/png" if ext == "png" else f"image/{ext}"
                data = base64.b64encode(p.read_bytes()).decode()
                return f"data:{mime};base64,{data}"
        return None

    # Build pages
    pages: list[list[Any]] = []
    for i in range(0, max(len(slides), 1), per_page):
        pages.append(slides[i : i + per_page])

    if is_2up:
        slide_width = "45%"
        notes_style = "font-size:0.85em;margin-top:4px;"
    else:
        slide_width = "22%"
        notes_style = "font-size:0.7em;margin-top:2px;"

    body_parts: list[str] = []
    for page_idx, page_slides in enumerate(pages):
        page_style = (
            "page-break-after:always;padding:16px;display:flex;flex-wrap:wrap;gap:16px;"
        )
        cells = []
        for slide in page_slides:
            img_src = _img_b64(slide.slug)
            if img_src:
                img_tag = (
                    f'<img src="{img_src}" alt="{slide.slug}" '
                    f'style="width:100%;max-width:100%;">'
                )
            else:
                img_tag = (
                    '<div style="width:100%;height:120px;background:#eee;'
                    "display:flex;align-items:center;"
                    'justify-content:center;">[no screenshot]</div>'
                )

            notes = slide.content_summary or ""
            cell = (
                f'<div style="width:{slide_width};box-sizing:border-box;">'
                f"{img_tag}"
                f'<div style="font-family:monospace;font-size:0.75em;">'
                f"{slide.slug}</div>"
                f'<div style="font-weight:bold;font-size:0.85em;">'
                f"{slide.title}</div>"
                f'<div style="{notes_style}">{notes}</div>'
                f"</div>"
            )
            cells.append(cell)

        page_html = f'<div style="{page_style}">' + "".join(cells) + "</div>"
        body_parts.append(page_html)

    body = "\n".join(body_parts)
    mode_label = "2-Up" if is_2up else "4-Up"

    html = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>Debrief Handout ({mode_label})</title>\n"
        "<style>\n"
        "body{font-family:sans-serif;margin:0;}\n"
        "@media print{.page-break{page-break-after:always;}}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>"
    )
    return html


# ---------------------------------------------------------------------------
# main_handout (BC-11.7, BC-11.8)
# ---------------------------------------------------------------------------


def main_handout(mode: str, project_root: Path) -> None:
    """Entry point for: python -m debrief.handout --mode <2up|4up> ...

    Use Playwright to render layout HTML to multi-page PDF.
    Write output/<folder>/handout_v{NNN}.pdf. Increment handout_count.
    Open one sync_playwright() session per invocation.
    """
    # BC-11.7: check playwright at entry
    if importlib.util.find_spec("playwright") is None:
        print(_ENV_CORRUPTION_MSG, file=sys.stderr)
        sys.exit(2)

    deck_state = read_deck_state(project_root)
    pres = deck_state.presentations[-1]
    folder = pres.folder
    version = pres.handout_count + 1
    handout_filename = f"handout_v{version:03d}.pdf"

    # Get approved slides (non-backup for main deck)
    approved = [s for s in deck_state.slides if s.status == "approved"]

    html_content = generate_layout_html(mode, approved, project_root)

    out_dir = project_root / "output" / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / handout_filename

    # Write a temporary HTML file for Playwright to render
    tmp_html = out_dir / f"handout_{version:03d}_tmp.html"
    tmp_html.write_text(html_content, encoding="utf-8")

    # Touch the output file so it exists even if playwright is mocked
    out_path.touch()

    try:
        import playwright.sync_api as _pw_api  # type: ignore

        with _pw_api.sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(tmp_html.as_uri())
                page.pdf(path=str(out_path))
            finally:
                browser.close()
    finally:
        if tmp_html.exists():
            tmp_html.unlink()

    # BC-11.8: do NOT consume any pending gate

    # Increment handout_count and write state
    increment_handout_count(deck_state, folder)
    write_deck_state(project_root, deck_state)

    print(str(out_path), file=sys.stderr)


# ---------------------------------------------------------------------------
# skill_save (BC-11.9, BC-11.10)
# ---------------------------------------------------------------------------


def skill_save(label: str, project_root: Path) -> None:
    """Save a snapshot of deck_state.json and ledger.jsonl.

    BC-11.10: Does NOT copy debrief_state.json.
    BC-11.9: Sanitizes label; handles collisions; falls back to 'untitled'.
    """
    sanitized = sanitize_save_label(label)

    snapshots_dir = project_root / "output" / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    # Collision handling (BC-11.9): append _2, _3, ...
    target_dir = snapshots_dir / sanitized
    if target_dir.exists():
        counter = 2
        while (snapshots_dir / f"{sanitized}_{counter}").exists():
            counter += 1
        target_dir = snapshots_dir / f"{sanitized}_{counter}"

    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy deck_state.json
    deck_src = project_root / "deck_state.json"
    if deck_src.exists():
        shutil.copy2(deck_src, target_dir / "deck_state.json")

    # Copy ledger.jsonl (do NOT copy debrief_state.json)
    ledger_src = project_root / "ledger.jsonl"
    if ledger_src.exists():
        shutil.copy2(ledger_src, target_dir / "ledger.jsonl")


# ---------------------------------------------------------------------------
# skill_reset (BC-11.11, BC-11.12)
# ---------------------------------------------------------------------------

_RESET_PROMPT = (
    "WARNING: This will delete all slides, state, and output. "
    "This action cannot be undone.\n"
    "Type RESET to confirm, or anything else to cancel: "
)

_RESET_ITEMS = [
    "slides",
    "output",
    ".debrief",
    "deck_state.json",
    "debrief_state.json",
    "ledger.jsonl",
    "deck_brief.md",
    "style_config.json",
    "style_guide.md",
    "assets",
]


def skill_reset(project_root: Path) -> None:
    """Reset the project directory, preserving CLAUDE.md (BC-11.12).

    BC-11.11: Only 'RESET' (exact, no whitespace) confirms the reset.
    """
    confirmation = input(_RESET_PROMPT)
    if confirmation != "RESET":
        print("Reset cancelled.", file=sys.stderr)
        return

    for item_name in _RESET_ITEMS:
        item_path = project_root / item_name
        if item_path.is_dir():
            shutil.rmtree(item_path)
        elif item_path.is_file():
            item_path.unlink()


# ---------------------------------------------------------------------------
# skill_quit (BC-11.13, BC-11.14)
# ---------------------------------------------------------------------------

_DRAFT_RETAIN_SUB_PHASES = frozenset({"style/style_dialog", "style/style_review"})
_DRAFT_RETAIN_GATE = "G2.1_style_config_review"


def skill_quit(project_root: Path) -> None:
    """Flush state files and clean transient artifacts.

    BC-11.13: Flush debrief_state.json and deck_state.json (with correct
              state_hash) before cleaning transient artifacts.
    BC-11.14: Retain .debrief/draft/ only when pending_gate is
              G2.1_style_config_review OR sub_phase is in
              {style/style_dialog, style/style_review}.
    """
    deck_state = read_deck_state(project_root)
    debrief_state = read_debrief_state(project_root)

    # BC-11.13: flush state files first
    write_deck_state(project_root, deck_state)
    write_debrief_state(project_root, debrief_state)

    # Flush ledger (no-op if empty, just touch)
    ledger_path = project_root / "ledger.jsonl"
    if ledger_path.exists():
        # Ledger is append-only; flushing means ensuring it's on disk
        with open(ledger_path, "a", encoding="utf-8") as _fh:
            _fh.flush()
            os.fsync(_fh.fileno())

    # BC-11.14: decide whether to retain .debrief/draft/
    sub_phase = debrief_state.sub_phase
    pending_gate = debrief_state.pending_gate

    retain_draft = (
        pending_gate == _DRAFT_RETAIN_GATE or sub_phase in _DRAFT_RETAIN_SUB_PHASES
    )

    if not retain_draft:
        draft_dir = project_root / ".debrief" / "draft"
        if draft_dir.exists():
            shutil.rmtree(draft_dir)
