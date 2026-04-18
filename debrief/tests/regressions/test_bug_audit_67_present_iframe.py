# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-67 — /debrief:present srcdoc iframes.

BUG-ST-present-empty (HIGH, layout regression): /debrief:present
produced a visually-empty presentation.html. Root cause:
_write_presentation_html extracted only <body>…</body> from each
standalone slide HTML and dropped the <head>. But every slide's
<head> carries a ~2,400-character <style> block defining slide-specific
classes (.statement-block, .main-heading, .accent, etc.). Without
those rules, every styled element collapsed to unstyled defaults.

REQ-PRESENT-IFRAME-1 / BC-11.18a: each file-backed slide is now
embedded as `<iframe srcdoc="…full slide HTML…">`. The srcdoc carries
the verbatim original HTML (head + body) inline. Per-slide CSS is
naturally scoped to its iframe.

REQ-PRESENT-IFRAME-2 / BC-11.18b: keyboard navigation works across
iframes. The handler is attached to the top-level window AND each
iframe's contentDocument on load. Arrow keys targeting VIDEO / INPUT
/ TEXTAREA / SELECT pass through so native behavior is preserved.

Coverage:

1. presentation.html contains one <iframe class="slide-frame"> per
   file-backed slide.
2. Each iframe has a `srcdoc` attribute whose value begins with
   `<!DOCTYPE` (it's a full HTML document).
3. The srcdoc-escaped content preserves per-slide <style> blocks
   verbatim (the critical fix — class rules reach the render pipeline).
4. srcdoc escaping uses &amp; and &quot; but leaves < and > literal.
5. The blank separator (BUG-AUDIT-65) is NOT an iframe (string-backed
   body stays a plain div).
6. Keyboard handler is attached to iframes' contentDocument on load
   (attach() logic present in the embedded JS).
7. Keyboard handler passes through arrow keys for VIDEO / INPUT / etc.
8. Top-level slide counter reflects top-level .slide wrappers only,
   not nested .slide divs inside iframe content.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest


_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_11" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_2" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_3" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_7" if _is_workspace_layout() else "debrief"),
    _PROJECT_ROOT / "src" / ("unit_10" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402
import debrief_state  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_STANDALONE_SLIDE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<link rel="stylesheet" href="../assets/style.css">
<style>
  body {{ width: 1920px; height: 1080px; }}
  .slide {{ padding: 7%; display: flex; }}
  .{slug_class} {{ font-size: 56px; color: #1a1a1a; }}
  .special-{slug_class} {{ font-weight: 800; }}
</style>
</head>
<body>
<div class="slide">
  <h1 class="{slug_class}">{title}</h1>
  <p class="special-{slug_class}">Body content for {slug}.</p>
</div>
</body>
</html>
"""


def _make_slide(slug: str, backup: bool = False) -> debrief_state.SlideRecord:
    return debrief_state.SlideRecord(
        slug=slug,
        title=slug.replace("-", " ").title(),
        status="approved",
        backup=backup,
        content_summary=None,
        visual_approach=None,
        design_choices=None,
        forks_not_taken=None,
        user_recommendations=None,
        qa_passed=True,
        accepted_violations=[],
        last_modified="2026-04-18T00:00:00+00:00",
        group_id=None,
        user_assets=[],
        has_math=False,
    )


def _init_project(
    project_root: Path,
    main_slugs: list[str],
    backup_slugs: list[str] = None,
    bg_color: str = "#ffffff",
) -> None:
    backup_slugs = backup_slugs or []
    (project_root / ".debrief").mkdir(parents=True, exist_ok=True)
    (project_root / "slides").mkdir(parents=True, exist_ok=True)
    (project_root / "assets").mkdir(parents=True, exist_ok=True)

    for slug in main_slugs + backup_slugs:
        slug_class = slug.replace("-", "_")
        (project_root / "slides" / f"{slug}.html").write_text(
            _STANDALONE_SLIDE_TEMPLATE.format(
                title=slug.replace("-", " ").title(),
                slug=slug,
                slug_class=slug_class,
            ),
            encoding="utf-8",
        )

    (project_root / "style_config.json").write_text(
        json.dumps({"colors": {"background": bg_color}}), encoding="utf-8"
    )

    deck = debrief_state.DeckState(
        project_name="demo",
        created_at="2026-04-18T00:00:00+00:00",
        archetype="conference_talk",
        style_locked=True,
        closing_slide=None,
        slides=[_make_slide(s) for s in main_slugs]
        + [_make_slide(s, backup=True) for s in backup_slugs],
        presentations=[],
    )
    debrief_state.write_deck_state(project_root, deck)


# ---------------------------------------------------------------------------
# 1. Iframes emitted for file-backed slides
# ---------------------------------------------------------------------------


def test_each_file_backed_slide_becomes_an_iframe(tmp_path):
    """BC-11.18a: file-backed slides emit <iframe class="slide-frame"
    srcdoc="…"> inside the .slide wrapper div."""
    _init_project(tmp_path, main_slugs=["hook", "body", "close"])
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    iframes = re.findall(r'<iframe class="slide-frame"', html)
    assert len(iframes) == 3, (
        f"Expected 3 iframes for 3 main slides; got {len(iframes)}"
    )


# ---------------------------------------------------------------------------
# 2. Srcdoc value is a full HTML document
# ---------------------------------------------------------------------------


def test_srcdoc_begins_with_doctype(tmp_path):
    """REQ-PRESENT-IFRAME-1: the srcdoc carries the verbatim original
    slide HTML, which always starts with <!DOCTYPE html>."""
    _init_project(tmp_path, main_slugs=["hook"])
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    # Extract the srcdoc attribute value
    m = re.search(r'srcdoc="([^"]*)"', html)
    # Since srcdoc can't contain literal "" we look for a longer match:
    # Actually the escaper converts " to &quot;, so the outer "…" always
    # terminates at the RIGHT spot. This greedy-to-" regex is safe.
    assert m is not None, "srcdoc attribute not found"
    srcdoc = m.group(1)
    assert srcdoc.startswith("<!DOCTYPE"), (
        f"srcdoc should begin with <!DOCTYPE; got: {srcdoc[:50]!r}"
    )


# ---------------------------------------------------------------------------
# 3. Per-slide <style> blocks are preserved — THE critical fix
# ---------------------------------------------------------------------------


def test_per_slide_style_block_preserved_in_srcdoc(tmp_path):
    """BUG-ST-present-empty root-cause fix: the per-slide class rules
    (defined in the slide's own <head><style>) MUST be present in the
    srcdoc attribute. Pre-fix they were dropped because only <body> was
    extracted."""
    _init_project(tmp_path, main_slugs=["hook"])
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    # The template defines .hook and .special-hook classes in its
    # per-slide <style> block. Those must reach the srcdoc.
    assert ".hook" in html, (
        "Per-slide class rule `.hook` missing from presentation.html "
        "(BUG-ST-present-empty regression — per-slide <style> dropped)"
    )
    assert ".special-hook" in html, (
        "Per-slide class rule `.special-hook` missing"
    )


def test_per_slide_body_size_rule_preserved_in_srcdoc(tmp_path):
    """Global `body { width: 1920px; height: 1080px }` rule from the
    per-slide <style> must reach the srcdoc. Without it, slides
    collapse to unstyled defaults when rendered inside the iframe."""
    _init_project(tmp_path, main_slugs=["hook"])
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    # Presence of the 1920px/1080px sizing anywhere in the document
    # (inside srcdoc) signals the per-slide <style> was preserved.
    assert "1920px" in html
    assert "1080px" in html


# ---------------------------------------------------------------------------
# 4. Srcdoc escaping: & and " escaped, < and > literal
# ---------------------------------------------------------------------------


def test_srcdoc_escapes_ampersand_and_quote_only(tmp_path):
    """REQ-PRESENT-IFRAME-1 (via _escape_srcdoc): only & and " are
    escaped inside the srcdoc attribute value; < and > remain literal."""
    _init_project(tmp_path, main_slugs=["hook"])
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    # The standalone slide contains <meta charset="UTF-8"> with double
    # quotes. In the srcdoc those " get escaped to &quot;.
    assert "&quot;UTF-8&quot;" in html or "&quot;utf-8&quot;" in html.lower(), (
        "Inner double quotes must be escaped to &quot; in srcdoc value"
    )
    # The slide body has <h1> and the per-slide style has `.hook { … }`.
    # < and > should be literal (HTML5 allows them in attribute values).
    assert "<style>" in html  # top-level presentation <style>
    # In srcdoc, the slide's <style> also appears literally because we
    # don't escape < / >:
    assert html.count("<style>") >= 2, (
        "Per-slide <style> should appear literally in srcdoc (not &lt;style&gt;)"
    )


def test_srcdoc_escapes_ampersand(tmp_path):
    """Unit check: _escape_srcdoc escapes & to &amp; first."""
    src = utility_skills._escape_srcdoc
    assert src("A & B") == "A &amp; B"
    assert src('foo="bar"') == "foo=&quot;bar&quot;"
    # Order matters: & must be escaped first so already-escaped &amp;
    # doesn't double-escape.
    assert src("already &amp; escaped") == "already &amp;amp; escaped"
    # Left literal:
    assert src("<b>x</b>") == "<b>x</b>"


# ---------------------------------------------------------------------------
# 5. Blank separator stays non-iframe (BUG-AUDIT-65 interaction)
# ---------------------------------------------------------------------------


def test_blank_separator_is_not_iframe(tmp_path):
    """BC-11.18 + BC-11.18a: the blank separator is string-backed and
    has no per-slide styling; it stays a plain <div class="slide">
    with the inline separator inner div — NO iframe wrap."""
    _init_project(
        tmp_path, main_slugs=["a"], backup_slugs=["qa"], bg_color="#abcdef"
    )
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    # The separator: a .slide wrapper containing a
    # .slide-separator-inner div (no iframe).
    sep_match = re.search(
        r'<div class="slide" data-index="\d+"[^>]*>\s*'
        r'<div class="slide-separator-inner"[^>]*>\s*</div>\s*</div>',
        html,
    )
    assert sep_match is not None, (
        "Blank separator should be a plain div (no iframe)"
    )


# ---------------------------------------------------------------------------
# 6. Keyboard handler attaches to iframes on load
# ---------------------------------------------------------------------------


def test_keydown_handler_attaches_to_iframe_contentDocument(tmp_path):
    """REQ-PRESENT-IFRAME-2 / BC-11.18b: the inline JS must attach the
    keydown handler to each iframe's contentDocument on load so key
    events fire regardless of which frame has focus."""
    _init_project(tmp_path, main_slugs=["a"])
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    # Structural markers of the attach-on-load logic:
    assert "iframe.slide-frame" in html
    assert "iframe.contentDocument" in html
    assert "addEventListener('keydown', handleKeyDown)" in html
    assert "iframe.addEventListener('load'" in html


# ---------------------------------------------------------------------------
# 7. Arrow keys pass through for VIDEO/INPUT/TEXTAREA/SELECT
# ---------------------------------------------------------------------------


def test_keydown_passthrough_for_video_and_form_elements(tmp_path):
    """REQ-PRESENT-IFRAME-2: arrow keys targeting <video>/<input>/
    <textarea>/<select> must not be intercepted for slide navigation."""
    _init_project(tmp_path, main_slugs=["a"])
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    # The PASS_THROUGH_TAGS list must name each target tag
    assert "'VIDEO'" in html
    assert "'INPUT'" in html
    assert "'TEXTAREA'" in html
    assert "'SELECT'" in html
    # And there's a pass-through branch
    assert "PASS_THROUGH_TAGS.includes(tag)" in html


# ---------------------------------------------------------------------------
# 8. Top-level slide counter excludes nested .slide divs
# ---------------------------------------------------------------------------


def test_top_level_slide_selector_excludes_nested(tmp_path):
    """BC-11.18a: standalone slide HTML contains its own <div class="slide">
    inside <body>. When embedded in an iframe, that nested .slide is
    in a separate document and not visible to top-level querySelectorAll.
    The selector MUST target only top-level wrappers so the counter
    matches the real slide count."""
    _init_project(tmp_path, main_slugs=["a", "b", "c"])
    out = utility_skills.build_presentation_html(tmp_path)
    html = out.read_text(encoding="utf-8")
    # Top-level selector must be scoped (body > .slide or similar).
    # Counter reflects 3 slides.
    assert "body > .slide" in html or "document.querySelectorAll('.slide[data-index" in html, (
        "Top-level slide selector must be scoped to top-level wrappers "
        "to avoid counting .slide divs inside iframe content."
    )
    assert "1 / 3" in html
