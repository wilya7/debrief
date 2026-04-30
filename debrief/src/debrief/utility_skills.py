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
import re
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


def _blank_separator_body(project_root: Path) -> str:
    """Return an HTML body snippet for a blank separator slide.

    BUG-AUDIT-65 / REQ-PRESENT-BACKUP-1: the separator is inserted
    between the last main slide and the first backup slide in
    /debrief:present. It's just the locked background color — no text,
    no imagery, no heading. Gives the presenter a clean beat before Q&A
    without signalling anything explicit to the audience.
    """
    import json as _json
    bg = "#ffffff"
    config_path = project_root / "style_config.json"
    if config_path.is_file():
        try:
            cfg = _json.loads(config_path.read_text(encoding="utf-8"))
            bg = cfg.get("colors", {}).get("background", bg)
        except Exception:
            pass  # keep default white — style config is optional for present
    # Emit a simple filled frame. The outer .slide class (set by the
    # caller in its own <div>) already handles sizing; we just nudge
    # the background so the separator's surface matches the deck.
    return (
        f'<div class="slide-separator-inner" '
        f'style="width:100%;height:100%;background:{bg};"></div>'
    )


def _collect_presentation_sequence(
    project_root: Path,
) -> Optional[list]:
    """Build the ordered list of slide inputs for presentation.html.

    Each item is either a Path (file-backed slide or build) or a str
    (pre-rendered body HTML, used for the blank separator). Returns
    None when the project is missing, no approved slides exist, or no
    slide HTML files exist on disk. Does NOT call sys.exit.

    BUG-AUDIT-65 / REQ-PRESENT-BACKUP-1: presenter surfaces ALWAYS
    include approved backup slides. When both main and backup exist, a
    blank separator slide is inserted between them. Main slides carry
    progressive-disclosure build expansion; backup slides do not.
    """
    project_root = project_root.resolve()
    state_path = project_root / "deck_state.json"
    if not state_path.is_file():
        return None

    deck_state = read_deck_state(project_root)
    main_slides = [
        s for s in deck_state.slides
        if s.status == "approved" and not s.backup
    ]
    backup_slides = [
        s for s in deck_state.slides
        if s.status == "approved" and s.backup
    ]
    if not main_slides:
        # BC-11.16-equivalent precondition for present: at least one
        # main approved slide (backup-only decks are meaningless here).
        return None

    slides_dir = project_root / "slides"

    def _expand_with_builds(slug: str) -> list[Path]:
        items: list[Path] = []
        build_idx = 1
        while True:
            build_file = slides_dir / f"{slug}_build_{build_idx}.html"
            if build_file.is_file():
                items.append(build_file)
                build_idx += 1
            else:
                break
        final_file = slides_dir / f"{slug}.html"
        if final_file.is_file():
            items.append(final_file)
        return items

    main_sequence: list = []
    for slide in main_slides:
        main_sequence.extend(_expand_with_builds(slide.slug))

    backup_sequence: list = []
    for slide in backup_slides:
        # Backup slides have no build expansion per BC-11.18.
        final_file = slides_dir / f"{slide.slug}.html"
        if final_file.is_file():
            backup_sequence.append(final_file)

    sequence: list = list(main_sequence)
    if backup_sequence:
        # BC-11.18: blank separator slide between main and backup.
        sequence.append(_blank_separator_body(project_root))
        sequence.extend(backup_sequence)

    if not sequence:
        return None
    return sequence


def build_presentation_html(project_root: Path) -> Optional[Path]:
    """Write `output/presentation.html` from the current approved slides.

    BUG-AUDIT-60 / BUG-ST-xp-1: split out of `main_present` so that
    `/debrief:export` can refresh presentation.html after each re-export
    without opening a browser. Returns the written path on success, or
    None if preconditions fail (no project, no approved main slides, no
    slide HTML files). Does NOT call sys.exit.

    BUG-AUDIT-65: backup slides are ALWAYS included at the end of the
    sequence, preceded by a blank separator slide. See BC-11.18.
    """
    sequence = _collect_presentation_sequence(project_root.resolve())
    if not sequence:
        return None
    return _write_presentation_html(project_root.resolve(), sequence)


def main_present(project_root: Path) -> None:
    """Generate output/presentation.html and open in browser.

    BUG-AUDIT-50: browser-based full-screen presentation mode.
    BUG-AUDIT-65 / REQ-PRESENT-BACKUP-1: reads every approved slide
    (both main and backup). Main slides carry progressive-disclosure
    build expansion; backup slides are appended terminal. When the
    deck has both main and backup, a blank separator slide (background
    color only) is inserted between them per BC-11.18. Generates a
    self-contained HTML file with keyboard navigation and opens it in
    the default browser.
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
    main_approved = [
        s for s in deck_state.slides
        if s.status == "approved" and not s.backup
    ]
    if not main_approved:
        print(
            "Cannot present: no approved non-backup slides. "
            "Author slides with '/debrief:slide' and approve at "
            "least one before presenting.",
            file=sys.stderr,
        )
        sys.exit(2)

    sequence = _collect_presentation_sequence(project_root)
    if not sequence:
        print(
            "Cannot present: no slide HTML files found in slides/.",
            file=sys.stderr,
        )
        sys.exit(2)

    out_path = _write_presentation_html(project_root, sequence)
    webbrowser.open(out_path.as_uri())
    print(str(out_path), file=sys.stderr)


def _escape_srcdoc(html_content: str) -> str:
    """Escape an HTML document for embedding in an iframe srcdoc attribute.

    BUG-AUDIT-67 / REQ-PRESENT-IFRAME-1: per the HTML5 attribute-value
    grammar, only `&` and the attribute's delimiter (`"`) MUST be
    escaped inside a double-quoted attribute value. `<` and `>` are
    legal literal characters inside attribute values and are left as-is
    so existing tests + human inspection of presentation.html can still
    grep for slide-body markup directly.
    """
    return html_content.replace("&", "&amp;").replace('"', "&quot;")


def _write_presentation_html(
    project_root: Path,
    slide_sequence: "list[Any]",
) -> Path:
    """Shared writer used by `main_present` and `build_presentation_html`.
    Returns the path written. Kept private — callers should use one of the
    two public entry points.

    Each item in ``slide_sequence`` is either a ``Path`` to a slide HTML
    file or a ``str`` body snippet already rendered (used for the blank
    separator per BC-11.18 / BUG-AUDIT-65).

    BUG-AUDIT-67 / REQ-PRESENT-IFRAME-1 / BC-11.18a: file-backed slides
    are embedded via `<iframe srcdoc="…">` carrying the verbatim
    original slide HTML (head + body). This preserves per-slide
    `<style>` blocks that define slide-specific class rules
    (`.statement-block`, `.main-heading`, etc.) — extracting only
    `<body>` dropped those rules and left every element unstyled.
    String-backed bodies (blank separator) have no per-slide styling
    and remain plain div content.
    """
    # Build each slide's wrapper HTML. Path items → iframe srcdoc; str
    # items → plain div content.
    slide_markups: list[str] = []
    for item in slide_sequence:
        if isinstance(item, Path):
            full_html = item.read_text(encoding="utf-8")
            slide_markups.append(
                '<iframe class="slide-frame" srcdoc="'
                + _escape_srcdoc(full_html)
                + '" style="width:100%;height:100%;border:0;display:block;"'
                + "></iframe>"
            )
        else:
            slide_markups.append(str(item))

    css_path = project_root / "assets" / "style.css"
    css_content = ""
    if css_path.is_file():
        css_content = css_path.read_text(encoding="utf-8")

    total = len(slide_markups)
    slides_html = ""
    for i, markup in enumerate(slide_markups):
        display = "flex" if i == 0 else "none"
        slides_html += (
            f'<div class="slide" data-index="{i}" '
            f'style="display:{display};">{markup}</div>\n'
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
  // BC-11.18a: count top-level .slide wrappers only. Nested .slide
  // divs inside iframes live in separate documents and are not seen
  // by this querySelectorAll.
  const slides = document.querySelectorAll('body > .slide');
  const total = slides.length;
  const counter = document.getElementById('counter');

  function show(idx) {{
    slides.forEach((s, i) => s.style.display = i === idx ? 'flex' : 'none');
    counter.textContent = (idx + 1) + ' / ' + total;
  }}

  // BC-11.18b / REQ-PRESENT-IFRAME-2: keydown must work across iframes.
  // Arrow keys targeting VIDEO/INPUT/TEXTAREA/SELECT pass through so
  // native behavior (video seeking, form input) is preserved.
  const PASS_THROUGH_TAGS = ['VIDEO', 'INPUT', 'TEXTAREA', 'SELECT'];
  const NAV_KEYS = ['ArrowRight', 'ArrowLeft', ' ', 'Enter'];
  function handleKeyDown(e) {{
    const tag = (e.target && e.target.tagName) || '';
    if (NAV_KEYS.includes(e.key) && PASS_THROUGH_TAGS.includes(tag)) {{
      return; // let the focused element handle it
    }}
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
  }}

  // Top-level window
  document.addEventListener('keydown', handleKeyDown);

  // Each iframe: attach keydown handler to its contentDocument on load,
  // so key events fire regardless of which frame holds focus.
  document.querySelectorAll('iframe.slide-frame').forEach(function(iframe) {{
    function attach() {{
      try {{
        if (iframe.contentDocument) {{
          iframe.contentDocument.addEventListener('keydown', handleKeyDown);
        }}
      }} catch (err) {{ /* cross-origin or detached — skip */ }}
    }}
    iframe.addEventListener('load', attach);
    // srcdoc iframes load synchronously in most browsers; attempt immediate
    // attach as well in case we missed the load event.
    if (iframe.contentDocument && iframe.contentDocument.readyState === 'complete') {{
      attach();
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
    return out_path


# ---------------------------------------------------------------------------
# generate_script_content (BC-11.6 / REQ-SCRIPT-3)
# ---------------------------------------------------------------------------


def _parse_duration_from_brief(brief_text: str) -> float | None:
    """Extract total duration in minutes from deck_brief.md text.

    BUG-AUDIT-59 / BUG-ST-13: Looks for common patterns like
    "duration: 15 min", "20 minutes", "5-minute talk", etc.

    BUG-AUDIT-60 / BUG-ST-a-4: the prior primary regex required
    `\\s*[:=]\\s*` between the keyword and the digit, which failed on
    markdown-bold headers like `**Duration:** 5 minutes` because `**` is
    not whitespace or colon. The fallback regex used `\\b` after
    `(?:minute|min)`, which does not match between `e` and `s` (both word
    characters) — so "5 minutes" silently fell through and the fallback
    picked up "45 min" from an unrelated duration-warning sentence elsewhere
    in the brief, returning 9× the correct duration. Both are fixed below.

    Returns None if no duration is found.
    """
    import re
    # Primary: explicit "duration"/"time"/"length" keyword, possibly inside
    # markdown bold/colon/equals punctuation, followed by a number and
    # "min(ute)(s)?". Gap is capped at 8 characters to avoid matching
    # across unrelated sentences.
    m = re.search(
        r'(?:duration|time|length)[\s:*=\-]{0,8}?(\d+)\s*(?:min|minute)s?\b',
        brief_text, re.IGNORECASE,
    )
    if m:
        return float(m.group(1))
    # Fallback: loose "<N> min(ute)(s)?" anywhere in the brief.
    m = re.search(
        r'(\d+)\s*[-\s]?\s*(?:minute|min)s?\b', brief_text, re.IGNORECASE,
    )
    if m:
        return float(m.group(1))
    return None


_TRANSITION_SIGNALS = (
    "next", "which leads", "sets the stage", "explore next",
    "where we go next", "which brings us", "let's turn to",
    "this leads", "moving on", "that's why",
    # BUG-AUDIT-62 / BUG-ST-a-e2 / REQ-SCRIPT-TRANSITION-1: broaden.
    "set up", "the first move", "next up", "move into", "turn to",
    "bringing us to", "leading into", "into the next",
)

_TRANSITION_MARKER_RE = re.compile(
    # Markdown wraps the whole "Transition:" phrase — leading `**`/`*`/`_`
    # sit BEFORE the label and closing `**`/`*`/`_` sit AFTER the colon
    # (e.g., `**Transition:**`, `*Transition:*`). Consume both so the
    # captured group contains only the actual transition text.
    r'(?:^|\n|\.\s+|!\s+|\?\s+)[*_]*transition[*_]*\s*:[*_]*\s*(.+?)(?:\n\s*\n|$)',
    re.IGNORECASE | re.DOTALL,
)


def _extract_transition(content_summary: str) -> tuple[str, str | None]:
    """Split content_summary into (talking_points, transition_sentence).

    BUG-AUDIT-59 / BUG-ST-12 (signal-word fallback).
    BUG-AUDIT-62 / BUG-ST-a-e2 / REQ-SCRIPT-TRANSITION-1 (explicit marker):
    two patterns, marker wins:

    1. **Explicit marker** — a line or sentence beginning with
       `Transition:` (case-insensitive, optional Markdown bold/italic).
       When matched, the text after the marker is the transition and the
       text before it is the talking-points body.
    2. **Signal-word fallback** — if no marker, check whether the final
       sentence contains any phrase in `_TRANSITION_SIGNALS`.

    Returns (talking_points, transition) where transition may be None.
    """
    import re as _re

    text = content_summary.strip()

    # 1. Explicit Transition: marker (highest precedence).
    match = _TRANSITION_MARKER_RE.search(text)
    if match:
        transition = match.group(1).strip()
        body = text[: match.start()].rstrip()
        # Strip a trailing isolated newline/period if the marker ate one.
        if body and body[-1] not in ".!?":
            body = body + "."
        return body or content_summary, transition

    # 2. Signal-word fallback on the final sentence.
    sentences = _re.split(r'(?<=[.!?])\s+', text)
    if len(sentences) < 2:
        return content_summary, None
    last = sentences[-1]
    if any(signal in last.lower() for signal in _TRANSITION_SIGNALS):
        return " ".join(sentences[:-1]), last
    return content_summary, None


def generate_script_content(
    deck_brief_content: str,
    slides: list[Any],
    folder: str,
    total_duration_minutes: float | None = None,
    backup_slides: list[Any] | None = None,
) -> str:
    """Produce script markdown per REQ-SCRIPT-3.

    One section per slide with title, key talking points, transitions,
    estimated speaking time.

    BUG-AUDIT-59 / BUG-ST-12: Extracts transition sentences from
    content_summary instead of using hardcoded placeholders.
    BUG-AUDIT-59 / BUG-ST-13: Inserts time-pacing checkpoints when
    total_duration_minutes is known.
    BUG-AUDIT-65 / REQ-SCRIPT-BACKUP-1 / BC-11.6b: when ``backup_slides``
    is a non-empty list, a ``## Backup Slides`` section is emitted after
    the main slide blocks, followed by one block per backup slide using
    the same per-slide format. Backup slides are NOT counted in the
    per-slide time computation or the TIME CHECK markers (those apply
    to the main talk only; backups are for Q&A and are not paced).
    """
    lines: list[str] = []
    lines.append("# Speaker Script")
    lines.append("")
    lines.append(f"**Presentation folder:** `{folder}`")
    if total_duration_minutes is not None:
        lines.append(f"**Target duration:** {total_duration_minutes:.0f} minutes")
    lines.append("")
    lines.append("---")
    lines.append("")

    if not slides:
        lines.append("*(No approved slides found.)*")
        return "\n".join(lines)

    n = len(slides)
    per_slide = (
        total_duration_minutes / n if total_duration_minutes and n > 0 else None
    )

    # Precompute checkpoint positions (25%, 50%, 75%)
    checkpoints: dict[int, str] = {}
    if total_duration_minutes and n > 1:
        for pct in (0.25, 0.50, 0.75):
            target_time = total_duration_minutes * pct
            slide_idx = int(pct * n)
            slide_idx = min(slide_idx, n - 1)
            label = {0.25: "quarter", 0.50: "halfway", 0.75: "three-quarter"}[pct]
            checkpoints[slide_idx] = (
                f"TIME CHECK ({label} mark): "
                f"At ~{target_time:.0f} min you should be on this slide."
            )

    def _emit_slide_block(slide: Any, header: str, is_last_main: bool) -> None:
        lines.append(header)
        lines.append("")
        lines.append(f"**Slug:** `{slide.slug}`")
        lines.append("")
        lines.append("### Key talking points")
        lines.append("")
        transition_text: str | None = getattr(slide, "transition", None)
        if slide.content_summary:
            talking_points = slide.content_summary
            if transition_text is None:
                talking_points, extracted = _extract_transition(
                    slide.content_summary
                )
                if extracted is not None:
                    transition_text = extracted
            lines.append(f"- {talking_points}")
        else:
            lines.append("- *(No content summary available.)*")
        lines.append("")
        lines.append("### Transition")
        lines.append("")
        if transition_text:
            lines.append(transition_text)
        elif is_last_main:
            lines.append("Conclude and invite questions.")
        else:
            lines.append("Lead into the next section.")
        lines.append("")
        lines.append("### Estimated speaking time")
        lines.append("")
        if per_slide is not None:
            lines.append(f"~{per_slide:.1f} minutes")
        else:
            lines.append("~1–2 minutes")
        lines.append("")
        lines.append("---")
        lines.append("")

    for i, slide in enumerate(slides):
        # Per-slide header (main slide)
        lines.append(f"## Slide {i + 1}: {slide.title}")
        lines.append("")
        lines.append(f"**Slug:** `{slide.slug}`")
        lines.append("")

        # BUG-ST-13: time checkpoint
        if i in checkpoints:
            lines.append(f"> {checkpoints[i]}")
            lines.append("")

        lines.append("### Key talking points")
        lines.append("")

        # BUG-ST-12: extract transition from content_summary
        transition_text: str | None = getattr(slide, "transition", None)
        if slide.content_summary:
            talking_points = slide.content_summary
            if transition_text is None:
                talking_points, extracted = _extract_transition(
                    slide.content_summary
                )
                if extracted is not None:
                    transition_text = extracted
            lines.append(f"- {talking_points}")
        else:
            lines.append("- *(No content summary available.)*")
        lines.append("")

        lines.append("### Transition")
        lines.append("")
        if i < n - 1:
            next_slide = slides[i + 1]
            if transition_text:
                lines.append(transition_text)
            else:
                lines.append(
                    f"Lead into **{next_slide.title}** by connecting the "
                    f"key findings above."
                )
        else:
            lines.append("Conclude and invite questions.")
        lines.append("")

        lines.append("### Estimated speaking time")
        lines.append("")
        if per_slide is not None:
            lines.append(f"~{per_slide:.1f} minutes")
        else:
            lines.append("~1–2 minutes")
        lines.append("")
        lines.append("---")
        lines.append("")

    # BUG-AUDIT-65 / BC-11.6b: emit backup slides under a clearly
    # labelled section. No time pacing (they're Q&A-only, not paced).
    if backup_slides:
        lines.append("## Backup Slides")
        lines.append("")
        lines.append(
            "The following slides are available during Q&A. They are NOT "
            "part of the main talk timing."
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        for j, slide in enumerate(backup_slides):
            _emit_slide_block(
                slide,
                header=f"## Slide {n + j + 1} (backup): {slide.title}",
                is_last_main=False,
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main_script_generator (BC-11.5, BC-11.6)
# ---------------------------------------------------------------------------


def main_script_generator(project_root: Path) -> None:
    """Entry point for: python -m debrief.script_generator --project-root <path>

    BUG-AUDIT-84 Sub-cycle B: this function is now a thin delegator
    to ``launcher.main_script_writer``. The legacy versioned-output
    behavior (write to ``output/<folder>/script_v{NNN}.md`` via the
    deterministic template ``generate_script_content``) is RETIRED.

    The new path: the script-writer agent (``agents/script-writer.md``)
    produces presenter-ready prose from the full memory surface;
    output goes to ``<project_root>/speaker_script.md`` with backup-
    before-overwrite per BC-11.20.

    Existing CLI invocations (``python -m debrief.utility_skills
    generate_script ...``) continue to work via this delegator. The
    historical preconditions ("at least one presentation must exist")
    are RELAXED — the script-writer no longer requires a prior export.

    BUG-AUDIT-25's filesystem-derived versioning: superseded.
    """
    try:
        from launcher import main_script_writer  # type: ignore[import]
    except ImportError as exc:
        print(
            f"BUG-AUDIT-84: cannot import launcher.main_script_writer: {exc}. "
            f"Verify the plugin is installed correctly.",
            file=sys.stderr,
        )
        sys.exit(1)

    main_script_writer(project_root, trigger="/debrief:script")
    return  # main_script_writer calls sys.exit(0) on its own.

    # ---- Legacy implementation retained below for reference; never executes ----
    project_root = project_root.resolve()
    deck_state = read_deck_state(project_root)

    # BC-11.5: precondition — presentations must exist
    if not deck_state.presentations:
        print(
            "No export has been done yet. Run /debrief:export first.",
            file=sys.stderr,
        )
        sys.exit(1)

    # BUG-AUDIT-25: precondition — approved non-backup slides.
    # BUG-AUDIT-65 / BC-11.6b: also collect approved backup slides for
    # inclusion in a trailing "## Backup Slides" section. Precondition
    # is unchanged (at least one main slide); backup slides are added
    # to the script but do not satisfy the precondition on their own.
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

    approved_backup = [
        s for s in deck_state.slides
        if s.status == "approved" and s.backup
    ]

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

    # BUG-AUDIT-59 / BUG-ST-13: parse duration from deck brief
    total_duration = _parse_duration_from_brief(deck_brief_content)

    content = generate_script_content(
        deck_brief_content,
        approved,
        folder,
        total_duration,
        backup_slides=approved_backup or None,
    )

    out_path = out_dir / script_filename
    out_path.write_text(content, encoding="utf-8")

    # BUG-AUDIT-25: no state mutation — versioning is filesystem-derived

    print(str(out_path), file=sys.stderr)

    # BC-2.18 / BUG-AUDIT-81 (Cycle 2 Phase 3): emit `script_done` to
    # output/timeline.jsonl. Best-effort — a timeline failure MUST NOT
    # mask the script's success.
    try:
        from launcher import append_timeline_event  # type: ignore[import]

        append_timeline_event(
            project_root,
            event="script_done",
            payload={
                "presentation_folder": folder,
                "version": version,
                "slide_count": len(approved),
                "backup_slide_count": len(approved_backup),
                "script_path": str(out_path.relative_to(project_root))
                if out_path.is_relative_to(project_root)
                else str(out_path),
            },
        )
    except Exception:  # noqa: BLE001 — best-effort timeline emission
        pass


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


_HANDOUT_NOTES_PLACEHOLDER = "(no notes available)"


def _load_speaker_script(project_root: Path) -> Optional[dict[str, str]]:
    r"""Parse ``<project_root>/speaker_script.md`` into per-slide notes bodies.

    Returns a mapping keyed by BOTH slug (primary, from the
    ``**Slug:** `<slug>` `` marker) and title (fallback, from the
    ``## Slide N: <title>`` header). Sections under ``## Backup Slides``
    are parsed with the same grammar; the ``(backup)`` qualifier is
    stripped before title matching.

    The body text for each section is everything between the per-slide
    `## Slide` header and the next `## Slide` header (or
    `## Backup Slides`, or end of file), minus the header line, with
    leading/trailing whitespace stripped.

    Returns None if the file does not exist, is empty, or produces
    zero sections. Best-effort parse — malformed files do not raise.

    See BC-11.15a and BUG-AUDIT-68.
    """
    script_path = project_root / "speaker_script.md"
    if not script_path.is_file():
        return None
    try:
        text = script_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return None

    mapping: dict[str, str] = {}
    # Split on lines beginning with "## Slide " or "## Backup Slides".
    # We walk line-by-line, delimiting a section at each header.
    lines = text.splitlines()
    header_indices: list[int] = []
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("## Slide ") or stripped.startswith(
            "## Backup Slides"
        ):
            header_indices.append(i)

    # Append a sentinel so the last section has an end index.
    header_indices.append(len(lines))

    # Regexes for header and slug marker.
    # Header captures: slide number (unused), optional " (backup)"
    # qualifier, and title.
    _header_re = re.compile(
        r"^##\s+Slide\s+\d+\s*(?:\(backup\))?\s*:\s*(.+?)\s*$"
    )
    _slug_re = re.compile(r"^\*\*Slug:\*\*\s*`([^`]+)`\s*$")

    for idx in range(len(header_indices) - 1):
        start = header_indices[idx]
        end = header_indices[idx + 1]
        if start >= len(lines):
            continue
        header_line = lines[start].lstrip()
        # Skip the "## Backup Slides" section heading itself — it is
        # a divider, not a slide section. Its child blocks are the
        # subsequent "## Slide N (backup): <title>" entries, which are
        # picked up by their own header indices.
        if header_line.startswith("## Backup Slides"):
            continue

        m_header = _header_re.match(header_line)
        if m_header is None:
            continue
        title = m_header.group(1).strip()

        body_lines = lines[start + 1 : end]
        # Locate slug marker within the body, if present.
        slug: Optional[str] = None
        for bline in body_lines:
            m_slug = _slug_re.match(bline.strip())
            if m_slug is not None:
                slug = m_slug.group(1).strip()
                break

        body = "\n".join(body_lines).strip()
        if not body:
            continue
        if slug:
            mapping[slug] = body
        if title and title not in mapping:
            mapping[title] = body

    return mapping if mapping else None


def _resolve_handout_notes(
    slide: Any,
    script_notes: Optional[dict[str, str]],
) -> str:
    """Resolve the notes text for one slide per BC-11.15b precedence.

    BUG-AUDIT-84 Sub-cycle C collapses the legacy three-level
    precedence (BC-11.15a) to two levels:

    (1) speaker_script.md section matched by slug or title.
    (2) placeholder string ``"(no notes available)"``.

    The ``slide.content_summary`` fallback is RETIRED. Every successful
    ``/debrief:script`` run now produces a presenter-ready
    ``speaker_script.md`` per REQ-SCRIPT-WRITER-1, and
    ``/debrief:handout``'s precondition (BC-11.16 amendment) requires
    the script to exist before the handout is rendered. The handout
    no longer needs a fallback to terse internal labels.
    """
    if script_notes:
        by_slug = script_notes.get(slide.slug)
        if by_slug and by_slug.strip():
            return by_slug
        by_title = script_notes.get(slide.title)
        if by_title and by_title.strip():
            return by_title

    return _HANDOUT_NOTES_PLACEHOLDER


def generate_layout_html(
    mode: str,
    slides: list[Any],
    project_root: Path,
) -> str:
    """Generate the layout HTML combining slide screenshots and explanatory text.

    Mode '2up': two slides per page, detailed notes.
    Mode '4up': four slides per page, condensed notes.

    BC-11.15b / BUG-AUDIT-84 Sub-cycle C: per-slide notes text follows
    a two-level precedence — speaker_script.md section, then the
    explicit placeholder "(no notes available)". The legacy
    ``content_summary`` fallback (BC-11.15a) is RETIRED.
    ``speaker_script.md`` is loaded once per invocation via
    ``_load_speaker_script()``; the script's existence is guaranteed
    by ``main_handout``'s precondition + auto-cascade per BC-11.16
    amendment.

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

    script_notes = _load_speaker_script(project_root)

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

            notes = _resolve_handout_notes(slide, script_notes)
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


def main_handout(
    mode: str,
    project_root: Path,
    include_backup: bool = False,
) -> None:
    """Entry point for: python -m debrief.handout --mode <2up|4up> [--include-backup].

    BUG-AUDIT-21: handout is an independent output channel.

      - BC-11.16 precondition order: (1) deck_state.json must exist,
        (2) at least one non-backup slide must be status="approved",
        (3) playwright must be importable. Each check prints a
        descriptive message to stderr and exits code 2 on failure.
        The Playwright import is deliberately attempted LAST so a
        missing-slides run does not report a misleading
        environment-corruption error.
      - BC-11.16a backup-inclusion flag (BUG-AUDIT-64 / REQ-HAND-BACKUP-1):
        ``include_backup`` extends the layout to include approved
        backup slides after the main slides. Default False matches
        /debrief:export's BC-10.3a — one flag name across commands.
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
    # The precondition is unchanged by --include-backup — users still
    # need at least one main slide; the flag only extends the layout.
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

    # BC-11.16a (BUG-AUDIT-64): when --include-backup is passed, append
    # approved backup slides after the main slides in array order.
    if include_backup:
        approved_backup = [
            s for s in deck_state.slides
            if s.status == "approved" and s.backup
        ]
        approved = approved + approved_backup

    # BC-11.16 amendment (BUG-AUDIT-84 Sub-cycle C): speaker_script.md
    # MUST exist. If absent, auto-cascade /debrief:script first, then
    # re-check. The cascade NEVER blocks (script-writer always exits 0
    # per REQ-SCRIPT-WRITER-2); if the script is still absent after
    # the cascade (e.g. API outage logged to script_errors.jsonl), the
    # handout is skipped with a stderr message — exit 0, do not block.
    script_path = project_root / "speaker_script.md"
    if not script_path.is_file():
        print(
            "speaker_script.md is missing — running /debrief:script first.",
            file=sys.stderr,
        )
        try:
            from launcher import main_script_writer  # type: ignore[import]

            try:
                main_script_writer(
                    project_root, trigger="/debrief:handout-cascade"
                )
            except SystemExit:
                # main_script_writer exits 0 always; absorb so the
                # cascade is transparent to the handout caller.
                pass
        except ImportError as exc:
            print(
                f"Cannot auto-cascade /debrief:script: {exc}. "
                "Run '/debrief:script' manually before '/debrief:handout'.",
                file=sys.stderr,
            )
            sys.exit(0)

        if not script_path.is_file():
            print(
                "speaker_script.md still missing after auto-cascade — "
                "handout skipped. See .debrief/script_errors.jsonl for "
                "the script-writer failure.",
                file=sys.stderr,
            )
            sys.exit(0)

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

    # BC-2.18 / BUG-AUDIT-81 (Cycle 2 Phase 3): emit `handout_done` to
    # output/timeline.jsonl. Best-effort — a timeline failure MUST NOT
    # mask the handout's success.
    try:
        from launcher import append_timeline_event  # type: ignore[import]

        append_timeline_event(
            project_root,
            event="handout_done",
            payload={
                "mode": mode,
                "include_backup": include_backup,
                "version": next_version,
                "slide_count": len(approved),
                "handout_path": str(out_path.relative_to(project_root))
                if out_path.is_relative_to(project_root)
                else str(out_path),
            },
        )
    except Exception:  # noqa: BLE001 — best-effort timeline emission
        pass


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

    # Step 4: set style_locked = True in deck_state.json.
    # BUG-AUDIT-62 / BUG-ST-round5-x-1: use write_deck_state so hash
    # recomputation + atomic write + ledger auto-append all happen.
    # Prior code wrote the file directly, which left the on-disk state
    # out of sync with any adjacent debrief_state.json writes and
    # surfaced as `hash mismatch — recomputed` warnings on the next read.
    deck_state = read_deck_state(project_root)
    deck_state.style_locked = True
    write_deck_state(project_root, deck_state)

    # Step 5: delete draft directory
    shutil.rmtree(draft_dir)

    # Step 6: confirmation
    print(
        "Style draft promoted: style_config.json and style_guide.md "
        "copied to project root, assets/style.css compiled, "
        "style_locked set to true, draft directory removed.",
        file=sys.stderr,
    )

    # BC-2.18 / BUG-AUDIT-82 (Cycle 2 Phase 4): emit `style_locked`
    # to output/timeline.jsonl. Best-effort — a timeline failure
    # MUST NOT mask the style-promotion's success.
    try:
        from launcher import append_timeline_event  # type: ignore[import]

        append_timeline_event(
            project_root,
            event="style_locked",
            payload={
                "style_config_path": "style_config.json",
                "style_guide_path": "style_guide.md",
                "style_css_path": "assets/style.css",
            },
        )
    except Exception:  # noqa: BLE001 — best-effort timeline emission
        pass


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

    # BC-11.12a / BUG-AUDIT-61 / REQ-RESTORE-WARN-1: orphan-output audit.
    # Enumerate output/<YYYY_MM_DD_*>/ folders on disk and diff against
    # presentations[].folder in the restored state. For each folder the
    # restored state does NOT reference, print a warning + log a ledger
    # entry. We never delete these files — scope preservation of
    # BC-11.12 is upheld; warnings are advisory.
    _emit_orphan_output_warnings(project_root, ledger_path)


_DATED_FOLDER_RE = re.compile(r"^\d{4}_\d{2}_\d{2}_")


def _emit_orphan_output_warnings(project_root: Path, ledger_path: Path) -> None:
    """BC-11.12a: warn about output/<YYYY_MM_DD_*>/ folders no longer
    referenced by the restored deck_state.presentations.
    """
    from datetime import datetime, timezone
    import json as _json

    output_dir = project_root / "output"
    if not output_dir.is_dir():
        return

    try:
        restored = read_deck_state(project_root)
    except Exception:
        # Can't read restored state — the restore contract already printed
        # its confirmation; don't fail the session because the audit can't
        # run. Treat as "no references known" — emit warnings for every
        # dated folder on disk.
        referenced: set[str] = set()
    else:
        referenced = {
            pres.folder for pres in restored.presentations if pres.folder
        }

    orphans: list[tuple[Path, int]] = []
    for entry in sorted(output_dir.iterdir()):
        if not entry.is_dir():
            continue
        if not _DATED_FOLDER_RE.match(entry.name):
            continue
        if entry.name in referenced:
            continue
        file_count = sum(1 for _ in entry.rglob("*") if _.is_file())
        orphans.append((entry, file_count))

    if not orphans:
        return

    print(
        f"Warning: {len(orphans)} orphan output folder(s) remain from "
        "prior exports and are NOT referenced by the restored deck_state:",
        file=sys.stderr,
    )
    with ledger_path.open("a", encoding="utf-8") as fh:
        for folder, file_count in orphans:
            rel = folder.relative_to(project_root)
            print(
                f"  - {rel}/  ({file_count} file{'s' if file_count != 1 else ''})",
                file=sys.stderr,
            )
            entry = {
                "event": "restore_orphan_warning",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "orphan_folder": str(rel),
                "file_count": file_count,
            }
            fh.write(_json.dumps(entry) + "\n")


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

    # BUG-AUDIT-59 / BUG-ST-14: remove state.lock after quit.
    # write_debrief_state releases the flock but leaves the file on disk.
    lock_path = project_root / ".debrief" / "state.lock"
    if lock_path.is_file():
        lock_path.unlink()

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
        "save", "restore", "quit", "present", "view",
        "promote_style_draft", "handout",
    ])
    _parser.add_argument("--project-root", type=Path, default=Path.cwd())
    _parser.add_argument("--label", default=None)
    _parser.add_argument("--query", default="all")
    _parser.add_argument("--mode", default="2up",
                         help="Handout mode (default: 2up)")
    _parser.add_argument(
        "--include-backup",
        action="store_true",
        help=(
            "Include approved backup slides at the end of the handout. "
            "Default: exclude, matching /debrief:export, /debrief:present, "
            "and /debrief:view default behavior (BUG-AUDIT-64 / BC-11.16a)."
        ),
    )
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
    elif _args.command == "handout":
        main_handout(_args.mode, _root, include_backup=_args.include_backup)
