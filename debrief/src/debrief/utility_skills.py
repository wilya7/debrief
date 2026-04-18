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

    BUG-AUDIT-32: precondition check for project existence + descriptive
    "no slides match" message on empty query result.
    """
    project_root = project_root.resolve()
    # BUG-AUDIT-32: project precondition
    if not (project_root / "deck_state.json").is_file():
        print(
            "Cannot view slides: no project found at "
            f"{project_root} (deck_state.json missing). "
            "Run 'debrief new' to create a project first.",
            file=sys.stderr,
        )
        sys.exit(2)

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

    # BC-11.3: Red-green deferral (BUG-AUDIT-35: red_green_iteration
    # removed; use sub_phase + red_green_started_at as the active signal)
    rg_active = (
        "red_green" in (debrief_state.sub_phase or "")
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
            print(
                f"No slides match query: {query!r}. Try 'all', a "
                f"specific slug, or 'group:<id>'.",
                file=sys.stderr,
            )
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
        print(
            f"No slides match query: {query!r}. Try 'all', a "
            f"specific slug, or 'group:<id>'.",
            file=sys.stderr,
        )
        sys.exit(1)

    html = generate_view_html(slides, project_root)
    view_path = project_root / "output" / "view.html"
    view_path.parent.mkdir(parents=True, exist_ok=True)
    view_path.write_text(html, encoding="utf-8")
    webbrowser.open(view_path.as_uri())


# ---------------------------------------------------------------------------
# main_present (REQ-PRESENT-1..5 / BUG-AUDIT-50)
# ---------------------------------------------------------------------------


def main_present(project_root: Path) -> None:
    """Generate output/presentation.html and open in browser.

    BUG-AUDIT-50: browser-based full-screen presentation mode.
    Reads approved non-backup slides, detects progressive disclosure
    builds, generates a self-contained HTML file with keyboard
    navigation, and opens it in the default browser.
    """
    project_root = project_root.resolve()
    # Preconditions
    state_path = project_root / "deck_state.json"
    if not state_path.is_file():
        print(
            "Cannot present: no project found at "
            f"{project_root} (deck_state.json missing). "
            "Run 'debrief new' to create a project first.",
            file=sys.stderr,
        )
        sys.exit(2)

    deck_state = read_deck_state(project_root)
    approved = [
        s for s in deck_state.slides
        if s.status == "approved" and not s.backup
    ]
    if not approved:
        print(
            "Cannot present: no approved non-backup slides. "
            "Author slides with '/debrief:slide' and approve at "
            "least one before presenting.",
            file=sys.stderr,
        )
        sys.exit(2)

    slides_dir = project_root / "slides"

    # Build the slide sequence including progressive disclosure builds
    slide_sequence: list[Path] = []
    for slide in approved:
        slug = slide.slug
        # Check for build files: slug_build_1.html, slug_build_2.html, ...
        build_idx = 1
        while True:
            build_file = slides_dir / f"{slug}_build_{build_idx}.html"
            if build_file.is_file():
                slide_sequence.append(build_file)
                build_idx += 1
            else:
                break
        # The final complete slide
        final_file = slides_dir / f"{slug}.html"
        if final_file.is_file():
            slide_sequence.append(final_file)

    if not slide_sequence:
        print(
            "Cannot present: no slide HTML files found in slides/.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Read each slide's body content
    slide_bodies: list[str] = []
    for slide_path in slide_sequence:
        html = slide_path.read_text(encoding="utf-8")
        # Extract body content — look for <body> tags
        import re as _re
        body_match = _re.search(
            r"<body[^>]*>(.*?)</body>", html, _re.DOTALL | _re.IGNORECASE
        )
        if body_match:
            slide_bodies.append(body_match.group(1))
        else:
            slide_bodies.append(html)

    # Read the style.css if it exists
    css_path = project_root / "assets" / "style.css"
    css_content = ""
    if css_path.is_file():
        css_content = css_path.read_text(encoding="utf-8")

    # Generate presentation.html
    total = len(slide_bodies)
    slides_html = ""
    for i, body in enumerate(slide_bodies):
        display = "flex" if i == 0 else "none"
        slides_html += (
            f'<div class="slide" data-index="{i}" '
            f'style="display:{display};">{body}</div>\n'
        )

    presentation_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Debrief Presentation</title>
<style>
{css_content}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #000; overflow: hidden; }}
.slide {{
  width: 100vw; height: 100vh;
  align-items: center; justify-content: center;
  flex-direction: column;
  background: #fff;
}}
.slide-counter {{
  position: fixed; bottom: 12px; right: 20px;
  color: #888; font-family: sans-serif; font-size: 14px;
  z-index: 9999; pointer-events: none;
}}
</style>
</head>
<body>
{slides_html}
<div class="slide-counter" id="counter">1 / {total}</div>
<script>
(function() {{
  let current = 0;
  const slides = document.querySelectorAll('.slide');
  const total = slides.length;
  const counter = document.getElementById('counter');

  function show(idx) {{
    slides.forEach((s, i) => s.style.display = i === idx ? 'flex' : 'none');
    counter.textContent = (idx + 1) + ' / ' + total;
  }}

  document.addEventListener('keydown', function(e) {{
    if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'Enter') {{
      e.preventDefault();
      if (current < total - 1) {{ current++; show(current); }}
    }} else if (e.key === 'ArrowLeft') {{
      e.preventDefault();
      if (current > 0) {{ current--; show(current); }}
    }} else if (e.key === 'f' || e.key === 'F') {{
      if (!document.fullscreenElement) {{
        document.documentElement.requestFullscreen();
      }} else {{
        document.exitFullscreen();
      }}
    }}
  }});

  show(0);
}})();
</script>
</body>
</html>"""

    out_dir = project_root / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "presentation.html"
    out_path.write_text(presentation_html, encoding="utf-8")

    webbrowser.open(out_path.as_uri())
    print(str(out_path), file=sys.stderr)


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
    output/<folder>/script_v{NNN}.md. Print path to stderr.

    BUG-AUDIT-25: filesystem-derived versioning (scan dir, max + 1)
    replaces the old script_count + 1 state-field pattern. No state
    mutation. Precondition check for approved non-backup slides added.
    """
    project_root = project_root.resolve()
    deck_state = read_deck_state(project_root)

    # BC-11.5: precondition — presentations must exist
    if not deck_state.presentations:
        print(
            "No export has been done yet. Run /debrief:export first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # BUG-AUDIT-25: precondition — approved non-backup slides
    approved = [
        s for s in deck_state.slides
        if s.status == "approved" and not s.backup
    ]
    if not approved:
        print(
            "Cannot generate script: no approved non-backup slides. "
            "Author slides with '/debrief:slide' and approve at least "
            "one before retrying '/debrief:script'.",
            file=sys.stderr,
        )
        sys.exit(2)

    # BC-11.6: use most recent (last) presentation folder
    pres = deck_state.presentations[-1]
    folder = pres.folder

    # BUG-AUDIT-25: filesystem-derived versioning
    out_dir = project_root / "output" / folder
    out_dir.mkdir(parents=True, exist_ok=True)

    existing_versions: list[int] = []
    for existing in out_dir.glob("script_v*.md"):
        stem = existing.stem
        if stem.startswith("script_v"):
            suffix = stem[len("script_v"):]
            try:
                existing_versions.append(int(suffix))
            except ValueError:
                continue
    version = (max(existing_versions) + 1) if existing_versions else 1
    script_filename = f"script_v{version:03d}.md"

    # Read deck brief
    brief_path = project_root / "deck_brief.md"
    if brief_path.exists():
        deck_brief_content = brief_path.read_text(encoding="utf-8")
    else:
        deck_brief_content = ""

    content = generate_script_content(deck_brief_content, approved, folder)

    out_path = out_dir / script_filename
    out_path.write_text(content, encoding="utf-8")

    # BUG-AUDIT-25: no state mutation — versioning is filesystem-derived

    print(str(out_path), file=sys.stderr)


# ---------------------------------------------------------------------------
# generate_layout_html (BC-11.6, REQ-HAND-4)
# ---------------------------------------------------------------------------


# BC-11.15 / REQ-HAND-5 / BUG-AUDIT-21: the handout uses its own
# first-class stylesheet, not a derivative of style_config.json /
# assets/style.css. The CSS file lives beside this module and is
# loaded at render time via a sibling-path read.
_HANDOUT_CSS_PATH = Path(__file__).resolve().parent / "handout.css"


def _load_handout_css() -> str:
    """Read src/unit_11/handout.css (or the delivered mirror).

    BC-11.15: the stylesheet is a first-class document — edits happen
    in the .css file, never in this Python module. A missing file is
    a packaging defect, not a runtime fallback path, so we raise
    FileNotFoundError with a clear message instead of silently using
    an inline default.
    """
    if not _HANDOUT_CSS_PATH.is_file():
        raise FileNotFoundError(
            f"Missing handout.css at {_HANDOUT_CSS_PATH}. "
            "The handout stylesheet is packaged next to utility_skills.py "
            "in both the workspace (src/unit_11/) and the delivered "
            "plugin (src/debrief/). Reinstall the plugin if this file "
            "is missing."
        )
    return _HANDOUT_CSS_PATH.read_text(encoding="utf-8")


def generate_layout_html(
    mode: str,
    slides: list[Any],
    project_root: Path,
) -> str:
    """Generate the layout HTML combining slide screenshots and explanatory text.

    Mode '2up': two slides per page, detailed notes.
    Mode '4up': four slides per page, condensed notes.
    Notes are read from each slide's content_summary field.

    BC-11.15 / BUG-AUDIT-21: all visual styling lives in handout.css
    and is referenced via CSS classes; this function emits class-based
    markup only. No inline style attributes beyond dynamic image
    sources.
    """
    import base64

    is_2up = mode == "2up"
    per_page = 2 if is_2up else 4
    cell_class = "cell cell-2up" if is_2up else "cell cell-4up"
    notes_class = "notes notes-2up" if is_2up else "notes notes-4up"

    def _img_b64(slug: str) -> Optional[str]:
        for ext in ("png", "jpg", "jpeg", "webp"):
            p = project_root / "output" / "screenshots" / f"{slug}.{ext}"
            if p.exists():
                mime = "image/png" if ext == "png" else f"image/{ext}"
                data = base64.b64encode(p.read_bytes()).decode()
                return f"data:{mime};base64,{data}"
        return None

    pages: list[list[Any]] = []
    for i in range(0, max(len(slides), 1), per_page):
        pages.append(slides[i : i + per_page])

    body_parts: list[str] = []
    for page_slides in pages:
        cells = []
        for slide in page_slides:
            img_src = _img_b64(slide.slug)
            if img_src:
                img_tag = f'<img src="{img_src}" alt="{slide.slug}">'
            else:
                img_tag = '<div class="no-shot">[no screenshot]</div>'

            notes = slide.content_summary or ""
            cell = (
                f'<div class="{cell_class}">'
                f"{img_tag}"
                f'<div class="slug">{slide.slug}</div>'
                f'<div class="title">{slide.title}</div>'
                f'<div class="{notes_class}">{notes}</div>'
                f"</div>"
            )
            cells.append(cell)

        page_html = '<div class="page">' + "".join(cells) + "</div>"
        body_parts.append(page_html)

    body = "\n".join(body_parts)
    mode_label = "2-Up" if is_2up else "4-Up"
    css = _load_handout_css()

    html = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>Debrief Handout ({mode_label})</title>\n"
        "<style>\n"
        f"{css}\n"
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
    """Entry point for: python -m debrief.handout --mode <2up|4up>.

    BUG-AUDIT-21: handout is an independent output channel.

      - BC-11.16 precondition order: (1) deck_state.json must exist,
        (2) at least one non-backup slide must be status="approved",
        (3) playwright must be importable. Each check prints a
        descriptive message to stderr and exits code 2 on failure.
        The Playwright import is deliberately attempted LAST so a
        missing-slides run does not report a misleading
        environment-corruption error.
      - BC-11.17 output path: output/handouts/handout_v{NNN}.pdf,
        where NNN is filesystem-derived — we scan the directory for
        existing ``handout_v*.pdf`` files and pick (max + 1). The
        handout output is NOT routed through
        deck_state.presentations and does NOT require a prior
        /debrief:export. The output/handouts/ directory is created
        on first invocation.
      - BC-11.8 gate invariant: this function does NOT consume or
        clear any pending gate in debrief_state.json.

    Per BC-11.15 the rendered HTML uses handout.css (shipped beside
    this module), which is optimized for print density and ink
    efficiency. It does NOT read assets/style.css and does NOT
    require style_locked.
    """
    project_root = project_root.resolve()
    # REQ-HAND-2: validate mode argument
    _VALID_HANDOUT_MODES = {"2up", "4up"}
    if mode not in _VALID_HANDOUT_MODES:
        print(
            f"Invalid handout mode: {mode!r}. "
            f"Valid modes: {', '.join(sorted(_VALID_HANDOUT_MODES))}",
            file=sys.stderr,
        )
        sys.exit(2)

    # BC-11.16 step (1): project must exist.
    state_path = project_root / "deck_state.json"
    if not state_path.is_file():
        print(
            "Cannot generate handout: no project found at "
            f"{project_root} (deck_state.json missing). "
            "Run 'debrief new' to create a project first.",
            file=sys.stderr,
        )
        sys.exit(2)

    # BC-11.16 step (2): at least one approved non-backup slide.
    deck_state = read_deck_state(project_root)
    approved = [
        s for s in deck_state.slides
        if s.status == "approved" and not s.backup
    ]
    if not approved:
        print(
            "Cannot generate handout: no approved non-backup slides in "
            f"{project_root}. Author slides with '/debrief:slide' and "
            "approve at least one before retrying '/debrief:handout'.",
            file=sys.stderr,
        )
        sys.exit(2)

    # BC-11.16 step (3) / BC-11.7: environment check.
    if importlib.util.find_spec("playwright") is None:
        print(_ENV_CORRUPTION_MSG, file=sys.stderr)
        sys.exit(2)

    # BC-11.17: filesystem-derived version in output/handouts/.
    out_dir = project_root / "output" / "handouts"
    out_dir.mkdir(parents=True, exist_ok=True)

    existing_versions: list[int] = []
    for existing in out_dir.glob("handout_v*.pdf"):
        stem = existing.stem  # "handout_vNNN"
        if stem.startswith("handout_v"):
            suffix = stem[len("handout_v"):]
            try:
                existing_versions.append(int(suffix))
            except ValueError:
                continue
    next_version = (max(existing_versions) + 1) if existing_versions else 1
    handout_filename = f"handout_v{next_version:03d}.pdf"
    out_path = out_dir / handout_filename

    html_content = generate_layout_html(mode, approved, project_root)

    tmp_html = out_dir / f"handout_{next_version:03d}_tmp.html"
    tmp_html.write_text(html_content, encoding="utf-8")

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

    # BC-11.8: do NOT consume any pending gate. BC-11.17: no state
    # writes — versioning is filesystem-derived, so deck_state.json
    # is not mutated by a handout run.

    print(str(out_path), file=sys.stderr)


# ---------------------------------------------------------------------------
# promote_style_draft (BC-11.16 — restored from routing.py post-BUG-AUDIT-31)
# ---------------------------------------------------------------------------


def promote_style_draft(project_root: Path) -> None:
    """Promote draft style files to project root and compile CSS.

    1. Verify .debrief/draft/style_config.json and style_guide.md exist.
    2. Copy both to project_root/ (overwrite if exists).
    3. Run style compiler to produce assets/style.css.
    4. Set style_locked = True in deck_state.json.
    5. Delete .debrief/draft/ recursively.
    6. Print confirmation to stderr.
    """
    import json as _json

    project_root = project_root.resolve()

    draft_dir = project_root / ".debrief" / "draft"
    draft_config = draft_dir / "style_config.json"
    draft_guide = draft_dir / "style_guide.md"

    if not draft_config.is_file() or not draft_guide.is_file():
        missing = []
        if not draft_config.is_file():
            missing.append(str(draft_config))
        if not draft_guide.is_file():
            missing.append(str(draft_guide))
        print(
            f"Cannot promote style draft: missing file(s): "
            f"{', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Step 2: copy draft files to project root
    shutil.copy2(draft_config, project_root / "style_config.json")
    shutil.copy2(draft_guide, project_root / "style_guide.md")

    # Step 3: run style compiler
    try:
        from style_engine import compile_style  # type: ignore[import]

        compile_style(
            project_root / "style_config.json",
            project_root / "assets" / "style.css",
        )
    except Exception as exc:
        print(f"Style compilation failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Step 4: set style_locked = True in deck_state.json
    deck_state_path = project_root / "deck_state.json"
    deck_data = _json.loads(deck_state_path.read_text(encoding="utf-8"))
    deck_data["style_locked"] = True
    deck_state_path.write_text(
        _json.dumps(deck_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Step 5: delete draft directory
    shutil.rmtree(draft_dir)

    # Step 6: confirmation
    print(
        "Style draft promoted: style_config.json and style_guide.md "
        "copied to project root, assets/style.css compiled, "
        "style_locked set to true, draft directory removed.",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# skill_save (BC-11.9, BC-11.10)
# ---------------------------------------------------------------------------


def skill_save(label: str, project_root: Path) -> None:
    """Save a snapshot of deck_state.json and ledger.jsonl.

    BC-11.10: Does NOT copy debrief_state.json.
    BC-11.9: Sanitizes label; handles collisions; falls back to 'untitled'.
    """
    project_root = project_root.resolve()
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

    # BUG-AUDIT-32 / REQ-SAVE-3: confirmation output
    copied = []
    if (target_dir / "deck_state.json").is_file():
        copied.append("deck_state.json")
    if (target_dir / "ledger.jsonl").is_file():
        copied.append("ledger.jsonl")
    contents = ", ".join(copied) if copied else "(empty — no state files found)"
    print(
        f"Snapshot saved: {target_dir.name} ({contents})",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# skill_restore (BC-11.11, BC-11.12 — BUG-AUDIT-22)
#
# BUG-AUDIT-22 replaced the old hard-delete ``skill_reset`` with a
# backup-restore function. The hard-delete behavior is permanently
# dropped. See spec REQ-RESTORE-* and the Bug Catalog entry.
# ---------------------------------------------------------------------------


def _list_snapshots(project_root: Path) -> list[str]:
    """Return sorted list of valid snapshot labels in output/snapshots/.

    A snapshot is valid if its directory contains ``deck_state.json``.
    """
    snapshots_dir = project_root / "output" / "snapshots"
    if not snapshots_dir.is_dir():
        return []
    labels: list[str] = []
    for entry in sorted(snapshots_dir.iterdir()):
        if entry.is_dir() and (entry / "deck_state.json").is_file():
            labels.append(entry.name)
    return labels


def _sweep_orphan_slides(project_root: Path) -> list[str]:
    """Delete slides/*.html files whose stem is not in deck_state's slug set.

    Returns the list of swept filenames (stems) for logging.
    """
    deck_state = read_deck_state(project_root)
    known_slugs = {s.slug for s in deck_state.slides}

    slides_dir = project_root / "slides"
    if not slides_dir.is_dir():
        return []

    swept: list[str] = []
    for html_file in sorted(slides_dir.glob("*.html")):
        if html_file.stem not in known_slugs:
            html_file.unlink()
            swept.append(html_file.stem)
    return swept


def skill_restore(label: Optional[str], project_root: Path) -> None:
    """Restore project state from a named snapshot.

    BUG-AUDIT-22: replaces the old ``skill_reset`` hard-delete.

    Two-mode invocation (no ``input()`` calls):

    - ``label is None``: list available snapshots, print, return.
    - ``label is str``: validate snapshot exists, auto-save current
      state, overwrite ``deck_state.json`` (and ``ledger.jsonl`` if
      present in snapshot), sweep orphan slide HTML, write
      restore_log entry to ``ledger.jsonl``, print confirmation.

    BC-11.11: snapshot validation + auto-save + orphan sweep
    BC-11.12: restore only overwrites deck_state.json and optionally
              ledger.jsonl, then sweeps unmatched slides. All other
              project files (CLAUDE.md, debrief_state.json,
              style_config.json, style_guide.md, .debrief/, assets/)
              are untouched.
    """
    project_root = project_root.resolve()
    import json as _json
    from datetime import datetime, timezone

    # --- List mode ---
    if label is None:
        labels = _list_snapshots(project_root)
        if not labels:
            print(
                "No snapshots found. Run '/debrief:save' to create one.",
                file=sys.stderr,
            )
            return

        print("Available snapshots:", file=sys.stderr)
        snapshots_dir = project_root / "output" / "snapshots"
        for lbl in labels:
            snap_dir = snapshots_dir / lbl
            has_ledger = (snap_dir / "ledger.jsonl").is_file()
            contents = "deck_state.json, ledger.jsonl" if has_ledger else "deck_state.json"
            print(f"  - {lbl}  ({contents})", file=sys.stderr)
        print(
            "\nTo restore: /debrief:restore <label>",
            file=sys.stderr,
        )
        return

    # --- Restore mode ---
    snapshots_dir = project_root / "output" / "snapshots"
    snap_dir = snapshots_dir / label
    snap_deck = snap_dir / "deck_state.json"

    if not snap_deck.is_file():
        available = _list_snapshots(project_root)
        avail_str = ", ".join(available) if available else "(none)"
        print(
            f"Snapshot '{label}' not found (no deck_state.json in "
            f"{snap_dir}). Available snapshots: {avail_str}",
            file=sys.stderr,
        )
        sys.exit(2)

    # BUG-AUDIT-52 / BUG-ST-19: validate snapshot BEFORE overwriting.
    # If the snapshot's deck_state.json is structurally invalid, refuse
    # the restore with a clear message instead of crashing mid-sequence.
    try:
        read_deck_state(snap_dir)
    except Exception as exc:
        print(
            f"Cannot restore from '{label}': the snapshot's "
            f"deck_state.json is structurally invalid ({exc}). "
            f"The snapshot may have been saved with malformed state. "
            f"Your current project state is untouched.",
            file=sys.stderr,
        )
        sys.exit(2)

    # BC-11.11 step 1: auto-save current state before overwrite.
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    auto_label = f"pre_restore_{ts}"
    skill_save(auto_label, project_root)
    print(
        f"Auto-saved current state to output/snapshots/{auto_label}/",
        file=sys.stderr,
    )

    # BC-11.11 step 2: restore deck_state.json.
    shutil.copy2(snap_deck, project_root / "deck_state.json")

    # BC-11.11 step 3: restore ledger.jsonl if present in snapshot.
    snap_ledger = snap_dir / "ledger.jsonl"
    if snap_ledger.is_file():
        shutil.copy2(snap_ledger, project_root / "ledger.jsonl")

    # BC-11.11 step 4: sweep orphan slide HTML.
    swept = _sweep_orphan_slides(project_root)

    # BC-11.11 step 5: write restore_log entry to ledger.jsonl.
    log_entry = {
        "event": "restore",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "restored_from": label,
        "auto_saved_as": auto_label,
        "swept_slugs": swept,
    }
    ledger_path = project_root / "ledger.jsonl"
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(_json.dumps(log_entry) + "\n")

    # BC-11.11 step 6: print confirmation.
    swept_msg = (
        f"Swept {len(swept)} orphan slide(s): {', '.join(swept)}"
        if swept
        else "No orphan slides to sweep."
    )
    print(
        f"Restored from '{label}'. {swept_msg} "
        f"Auto-saved pre-restore state as '{auto_label}'.",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# skill_quit (BC-11.13, BC-11.14)
# ---------------------------------------------------------------------------

_DRAFT_RETAIN_SUB_PHASES = frozenset({"style/style_dialog", "style/style_review"})
_DRAFT_RETAIN_GATE = "G2.1_style_config_review"


def skill_quit(project_root: Path) -> None:
    """Flush state files, clean transient artifacts, print summary.

    BC-11.13: Flush debrief_state.json and deck_state.json (with correct
              state_hash) before cleaning transient artifacts.
    BC-11.14: Retain .debrief/draft/ only when pending_gate is
              G2.1_style_config_review OR sub_phase is in
              {style/style_dialog, style/style_review}.

    BUG-AUDIT-24 additions:
      - Defensive cycle-state check (belt-and-suspenders warning if
        quit is invoked during what appears to be an active red-green
        cycle — should never trigger in Claude Code's sequential model
        but documents the invariant in code).
      - Summary output to stderr per REQ-QUIT-1 step 5.
      - Transient artifact cleanup: .debrief/task_prompt.md and
        .debrief/gate_data.json (dead routing-loop artifact).
    """
    project_root = project_root.resolve()
    deck_state = read_deck_state(project_root)
    debrief_state = read_debrief_state(project_root)

    # BUG-AUDIT-24: defensive cycle-state check. Claude Code's
    # sequential message processing means skill_quit can only run
    # when no Task is in-flight, so this warning should never fire.
    # If it does, it means the concurrency model changed or state
    # is corrupted — either way, the user should know.
    if (
        "red_green" in (debrief_state.sub_phase or "")
        and debrief_state.red_green_started_at is not None
    ):
        print(
            "WARNING: quit invoked during what appears to be an "
            "active red-green cycle (sub_phase="
            f"{debrief_state.sub_phase}). State will be flushed "
            "as-is. If a slide agent was mid-turn, its partial "
            "work may be lost.",
            file=sys.stderr,
        )

    # BC-11.13: flush state files first
    write_deck_state(project_root, deck_state)
    write_debrief_state(project_root, debrief_state)

    # Flush ledger (no-op if empty, just touch)
    ledger_path = project_root / "ledger.jsonl"
    if ledger_path.exists():
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

    # BUG-AUDIT-24: clean transient artifacts beyond draft/
    for transient in ("task_prompt.md", "gate_data.json"):
        p = project_root / ".debrief" / transient
        if p.is_file():
            p.unlink()

    # BUG-AUDIT-24 / REQ-QUIT-1 step 5: summary output.
    approved_count = sum(
        1 for s in deck_state.slides
        if s.status == "approved" and not s.backup
    )
    last_export = ""
    if deck_state.presentations:
        last_export = f", last export folder: {deck_state.presentations[-1].folder}"

    print(
        f"Session complete. Phase: {debrief_state.phase}, "
        f"archetype: {deck_state.archetype}, "
        f"style_locked: {deck_state.style_locked}, "
        f"approved slides: {approved_count}"
        f"{last_export}. "
        f"Run 'debrief' to resume.",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# CLI dispatcher (__main__)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(description="Debrief utility skills")
    _parser.add_argument("command", choices=[
        "save", "restore", "quit", "present", "view", "promote_style_draft",
    ])
    _parser.add_argument("--project-root", type=Path, default=Path.cwd())
    _parser.add_argument("--label", default=None)
    _parser.add_argument("--query", default="all")
    _args = _parser.parse_args()
    _root = _args.project_root.resolve()

    if _args.command == "save":
        skill_save(_args.label or "snapshot", _root)
    elif _args.command == "restore":
        skill_restore(_args.label, _root)
    elif _args.command == "quit":
        skill_quit(_root)
    elif _args.command == "present":
        main_present(_root)
    elif _args.command == "view":
        main_view(_args.query, _root)
    elif _args.command == "promote_style_draft":
        promote_style_draft(_root)
