# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 9: QA System — qa_checker module.

Programmatic slide invariant checks and QA log management.
Behavioral contracts: BC-9.1 through BC-9.11.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import playwright.sync_api  # type: ignore[import-not-found]

# Import sync_playwright lazily so the module remains importable even when
# playwright is not installed (tests mock qa_checker.sync_playwright directly).
try:
    from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    sync_playwright = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

QAFailure = dict[str, str]
# {"invariant": str, "description": str, "revision_instruction": str}

QAWarning = dict[str, str]
# {"invariant": str, "description": str, "revision_instruction": str}

# ---------------------------------------------------------------------------
# Environment-corruption check helper
# ---------------------------------------------------------------------------

_ENV_CORRUPTION_MSG = (
    "ERROR: Conda environment is corrupted or incomplete. "
    "The package 'json_repair' is required but not found. "
    "Please reinstall the Debrief conda environment: "
    "conda env create -f environment.yml --force"
)


def _check_json_repair() -> None:
    """Exit with code 2 if json_repair is not available (BC-9.11)."""
    if importlib.util.find_spec("json_repair") is None:
        print(_ENV_CORRUPTION_MSG, file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------------------
# BC-9.4: build_qa_log_entry
# ---------------------------------------------------------------------------


def build_qa_log_entry(
    slug: str,
    passed: bool,
    veto: bool,
    checks_run: list[str],
    failures: list[QAFailure],
    warnings: list[QAWarning],
) -> dict[str, Any]:
    """Build a qa_log.jsonl entry conforming to the REQ-QA-3 canonical schema.

    Derives revision_instructions from failure.revision_instruction fields.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    revision_instructions: list[str] = [
        f["revision_instruction"] for f in failures if "revision_instruction" in f
    ]
    return {
        "slug": slug,
        "timestamp": timestamp,
        "passed": passed,
        "veto": veto,
        "checks_run": checks_run,
        "failures": failures,
        "warnings": warnings,
        "revision_instructions": revision_instructions,
    }


# ---------------------------------------------------------------------------
# BC-9.4: append_qa_log
# ---------------------------------------------------------------------------


def append_qa_log(project_root: Path, entry: dict[str, Any]) -> None:
    """Append a QA log entry to output/qa_log.jsonl.

    Opens in append mode. Each entry is a single JSON line.
    """
    log_path = project_root / "output" / "qa_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# BC-9.4 / INV-06: check_no_inline_styles
# ---------------------------------------------------------------------------

_INLINE_STYLE_RE = re.compile(r'\bstyle\s*=\s*["\']', re.IGNORECASE)


def check_no_inline_styles(slide_path: Path) -> Optional[QAFailure]:
    """INV-06: Verify slide HTML contains no inline style= attributes.

    Returns QAFailure if found, else None.
    """
    html = slide_path.read_text(encoding="utf-8")
    if _INLINE_STYLE_RE.search(html):
        return {
            "invariant": "INV-06",
            "description": (
                "Slide contains inline style= attributes that may override "
                "locked CSS custom properties."
            ),
            "revision_instruction": (
                "Remove all inline style= attributes from the slide HTML. "
                "Use CSS classes and custom properties from assets/style.css "
                "instead."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# BC-9.4 / INV-07: check_no_external_requests
# ---------------------------------------------------------------------------

_EXTERNAL_URL_RE = re.compile(r'(?:src|href)\s*=\s*["\']https?://', re.IGNORECASE)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def check_no_external_requests(slide_path: Path) -> Optional[QAFailure]:
    """INV-07: Verify slide HTML contains no external http/https references.

    src= or href= referencing http:// or https:// URLs triggers a failure.
    Returns QAFailure if found, else None.
    """
    html = slide_path.read_text(encoding="utf-8")
    # Strip HTML comments to avoid false positives from commented-out URLs
    stripped = _HTML_COMMENT_RE.sub("", html)
    if _EXTERNAL_URL_RE.search(stripped):
        return {
            "invariant": "INV-07",
            "description": (
                "Slide contains external URL references (http:// or https://) "
                "in src= or href= attributes."
            ),
            "revision_instruction": (
                "Remove all external URL references from src= and href= "
                "attributes. Use only local relative paths to bundled vendor "
                "assets."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# BC-9.4 / INV-10: check_permitted_libraries
# ---------------------------------------------------------------------------

# Known diagram library filename patterns
_KNOWN_DIAGRAM_LIBS = ["mermaid", "katex", "rough", "d3", "chart"]


def check_permitted_libraries(
    slide_path: Path,
    permitted: list[str],
) -> Optional[QAFailure]:
    """INV-10: Verify slide HTML only references permitted diagram libraries.

    Returns QAFailure if a non-permitted library is referenced, else None.
    """
    html = slide_path.read_text(encoding="utf-8")
    # Find all script src attributes referencing vendor/*.min.js files
    script_src_re = re.compile(
        r'<script[^>]+src\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE
    )
    for match in script_src_re.finditer(html):
        src = match.group(1).lower()
        # Check if this src refers to a known diagram library
        for lib in _KNOWN_DIAGRAM_LIBS:
            if lib in src:
                if lib not in permitted:
                    return {
                        "invariant": "INV-10",
                        "description": (
                            f"Slide references diagram library '{lib}' "
                            f"which is not in the permitted list: {permitted}."
                        ),
                        "revision_instruction": (
                            f"Remove the <script> tag referencing '{lib}' "
                            f"or switch to a permitted diagram library: "
                            f"{permitted}."
                        ),
                    }
    return None


# ---------------------------------------------------------------------------
# BC-9.4 / INV-04: check_contrast (Playwright-based)
# ---------------------------------------------------------------------------


def check_contrast(
    page: "playwright.sync_api.Page",
) -> Optional[QAFailure]:
    """INV-04: Compute WCAG contrast ratio from computed colors.

    Returns a QAFailure if contrast ratio < 4.5:1, else None.
    """
    script = """
    () => {
        const el = document.querySelector('.slide') ||
                   document.querySelector('body');
        if (!el) return null;
        const style = window.getComputedStyle(el);
        return {
            color: style.color,
            background: style.backgroundColor,
        };
    }
    """
    result = page.evaluate(script)
    if result is None:
        return None

    def _parse_rgb(css_color: str) -> tuple[float, float, float] | None:
        m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", css_color)
        if not m:
            return None
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def _luminance(r: float, g: float, b: float) -> float:
        def _c(v: float) -> float:
            v /= 255.0
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        return 0.2126 * _c(r) + 0.7152 * _c(g) + 0.0722 * _c(b)

    fg = _parse_rgb(result.get("color", ""))
    bg = _parse_rgb(result.get("background", ""))
    if fg is None or bg is None:
        return None

    lum_fg = _luminance(*fg)
    lum_bg = _luminance(*bg)
    lighter = max(lum_fg, lum_bg)
    darker = min(lum_fg, lum_bg)
    ratio = (lighter + 0.05) / (darker + 0.05)

    if ratio < 4.5:
        return {
            "invariant": "INV-04",
            "description": (
                f"WCAG contrast ratio is {ratio:.2f}:1, below the 4.5:1 minimum."
            ),
            "revision_instruction": (
                "Increase the contrast between the foreground text color and "
                "background color to meet the WCAG 2.1 AA minimum of 4.5:1."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# BC-9.4 / INV-08: check_aspect_ratio (Playwright-based)
# ---------------------------------------------------------------------------


def check_aspect_ratio(
    page: "playwright.sync_api.Page",
    style_config: dict[str, Any],
) -> Optional[QAFailure]:
    """INV-08: Verify rendered slide matches 16:9 aspect ratio.

    Tolerance: ±1 pixel. Returns QAFailure if mismatch, else None.
    """
    from debrief_state import parse_css_int  # type: ignore[import]

    layout = style_config.get("layout", {})
    expected_w = parse_css_int(layout.get("slide_width", 1920), default=1920)
    expected_h = parse_css_int(layout.get("slide_height", 1080), default=1080)

    result = page.evaluate(
        "() => ({ width: document.body.scrollWidth, "
        "height: document.body.scrollHeight })"
    )
    if result is None:
        return None

    actual_w = result.get("width", 0)
    actual_h = result.get("height", 0)

    if abs(actual_w - expected_w) > 1 or abs(actual_h - expected_h) > 1:
        return {
            "invariant": "INV-08",
            "description": (
                f"Slide dimensions {actual_w}x{actual_h} do not match "
                f"expected {expected_w}x{expected_h} (±1 px tolerance)."
            ),
            "revision_instruction": (
                "Ensure the slide container has the exact dimensions "
                f"defined in style_config.json: "
                f"{expected_w}x{expected_h} pixels."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# VETO checks (BUG-AUDIT-37 / REQ-QA-2)
# ---------------------------------------------------------------------------

_RAW_SOURCE_PATTERNS = re.compile(
    r"<div\b|</div>|<span\b|</span>|<p\b|</p>"
    r"|\\begin\{|\\end\{|\\frac\{|\\sum_|\\int_"
    r"|style\s*=\s*[\"']",
    re.IGNORECASE,
)


def check_text_overflow(
    page: "playwright.sync_api.Page",
) -> Optional[QAFailure]:
    """VETO-01: detect text overflowing beyond its container boundary."""
    script = """
    () => {
        const els = document.querySelectorAll('*');
        for (const el of els) {
            const s = window.getComputedStyle(el);
            if (s.display === 'none' || s.visibility === 'hidden') continue;
            if (el.tagName === 'HTML' || el.tagName === 'BODY') continue;
            if (el.scrollWidth > el.clientWidth + 2 ||
                el.scrollHeight > el.clientHeight + 2) {
                if (s.overflow === 'hidden' || s.overflowX === 'hidden' ||
                    s.overflowY === 'hidden') {
                    return el.tagName + (el.className ? '.' + el.className.split(' ')[0] : '');
                }
            }
        }
        return null;
    }
    """
    result = page.evaluate(script)
    if result:
        return {
            "invariant": "VETO-01",
            "description": (
                f"Text overflows beyond slide boundary at element: {result}. "
                "Content is clipped or truncated."
            ),
            "revision_instruction": (
                "Reduce content length, decrease font size, or restructure "
                "layout so all text fits within the slide boundary."
            ),
        }
    return None


def check_raw_source_visible(
    page: "playwright.sync_api.Page",
) -> Optional[QAFailure]:
    """VETO-04: detect raw HTML/CSS/LaTeX source visible as literal text."""
    try:
        visible_text = page.inner_text("body")
    except Exception:
        return None
    if _RAW_SOURCE_PATTERNS.search(visible_text):
        return {
            "invariant": "VETO-04",
            "description": (
                "Raw HTML, CSS, or LaTeX source code is visible as "
                "literal text in the rendered slide."
            ),
            "revision_instruction": (
                "Ensure all HTML tags are properly rendered (not escaped "
                "as text), all LaTeX is processed by KaTeX, and no CSS "
                "properties appear as visible content."
            ),
        }
    return None


def check_slug_not_in_content(
    page: "playwright.sync_api.Page",
    slug: str,
) -> Optional[QAFailure]:
    """VETO-06: detect the slide's slug rendered as visible body content."""
    if not slug:
        return None
    try:
        visible_text = page.inner_text("body")
    except Exception:
        return None
    if slug in visible_text:
        return {
            "invariant": "VETO-06",
            "description": (
                f"Slide slug '{slug}' appears as visible text in the "
                "rendered content. Meta-identifiers must not be shown."
            ),
            "revision_instruction": (
                f"Remove the literal string '{slug}' from the slide's "
                "visible content area. Slugs are internal identifiers, "
                "not presentation text."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# INV-12: check_valid_html5
# ---------------------------------------------------------------------------

# Void elements that do not require closing tags in HTML5.
_VOID_ELEMENTS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input",
     "link", "meta", "param", "source", "track", "wbr"}
)


def check_valid_html5(slide_path: Path) -> Optional[QAFailure]:
    """INV-12: Verify slide HTML has balanced open/close tags.

    Uses html.parser.HTMLParser to track opened vs closed tags.
    Void elements (img, br, hr, meta, link, input, etc.) are ignored.
    Returns QAFailure if any tag opens but never closes, else None.
    """

    class _TagTracker(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.stack: list[str] = []
            self.unclosed: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag.lower() not in _VOID_ELEMENTS:
                self.stack.append(tag.lower())

        def handle_endtag(self, tag: str) -> None:
            tag_l = tag.lower()
            if tag_l in _VOID_ELEMENTS:
                return
            # Walk the stack backward to find the matching open tag
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i] == tag_l:
                    self.stack.pop(i)
                    return

    html = slide_path.read_text(encoding="utf-8")
    tracker = _TagTracker()
    tracker.feed(html)
    if tracker.stack:
        unclosed = list(dict.fromkeys(tracker.stack))  # unique, order-preserving
        return {
            "invariant": "INV-12",
            "description": (
                f"Slide HTML has unclosed tags: {', '.join(unclosed)}."
            ),
            "revision_instruction": (
                "Close all opened HTML tags properly. Unclosed tags: "
                f"{', '.join(unclosed)}."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# INV-16: check_fonts_loadable
# ---------------------------------------------------------------------------

_FONT_FACE_RE = re.compile(r"@font-face\s*\{[^}]*\}", re.DOTALL | re.IGNORECASE)
_FONT_SRC_URL_RE = re.compile(r"url\(\s*['\"]?([^'\")\s]+)['\"]?\s*\)", re.IGNORECASE)


def check_fonts_loadable(slide_path: Path, project_root: Path) -> Optional[QAFailure]:
    """INV-16: Verify all @font-face src: url() references resolve to files.

    Parses <style> sections in the slide HTML for @font-face blocks, then
    resolves each url() path relative to the slide's directory (slides/).
    Returns QAFailure listing missing font files, else None.
    """
    html = slide_path.read_text(encoding="utf-8")
    slides_dir = slide_path.parent

    missing: list[str] = []
    for ff_match in _FONT_FACE_RE.finditer(html):
        block = ff_match.group(0)
        for url_match in _FONT_SRC_URL_RE.finditer(block):
            url = url_match.group(1)
            # Skip data URIs and remote URLs
            if url.startswith("data:") or url.startswith("http://") or url.startswith("https://"):
                continue
            resolved = (slides_dir / url).resolve()
            if not resolved.is_file():
                missing.append(url)

    if missing:
        return {
            "invariant": "INV-16",
            "description": (
                f"Font files referenced in @font-face are missing: "
                f"{', '.join(missing)}."
            ),
            "revision_instruction": (
                "Ensure all font files referenced in @font-face src: url() "
                "exist at the specified paths relative to the slides/ "
                f"directory. Missing: {', '.join(missing)}."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# INV-17: check_css_vars_defined
# ---------------------------------------------------------------------------

_CSS_VAR_DEF_RE = re.compile(r"(--[a-zA-Z0-9_-]+)\s*:")
_CSS_VAR_USAGE_RE = re.compile(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*[,)]")
_ROOT_BLOCK_RE = re.compile(r":root\s*\{([^}]*)\}", re.DOTALL)


def check_css_vars_defined(slide_path: Path, project_root: Path) -> Optional[QAFailure]:
    """INV-17: Verify all var(--name) usages in slide HTML are defined.

    Reads assets/style.css and collects --var-name definitions from
    :root { ... } blocks. Then scans slide HTML for var(--name) usages.
    Returns QAFailure listing any undefined vars, else None.
    """
    style_css_path = project_root / "assets" / "style.css"
    defined_vars: set[str] = set()
    if style_css_path.is_file():
        css_text = style_css_path.read_text(encoding="utf-8")
        for root_match in _ROOT_BLOCK_RE.finditer(css_text):
            root_block = root_match.group(1)
            for var_match in _CSS_VAR_DEF_RE.finditer(root_block):
                defined_vars.add(var_match.group(1))

    html = slide_path.read_text(encoding="utf-8")
    used_vars: set[str] = set()
    for usage_match in _CSS_VAR_USAGE_RE.finditer(html):
        used_vars.add(usage_match.group(1))

    undefined = sorted(used_vars - defined_vars)
    if undefined:
        return {
            "invariant": "INV-17",
            "description": (
                f"CSS variables used in slide HTML but not defined in "
                f"assets/style.css :root: {', '.join(undefined)}."
            ),
            "revision_instruction": (
                "Define the following CSS custom properties in the :root "
                f"block of assets/style.css: {', '.join(undefined)}."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# INV-19: check_image_paths_exist
# ---------------------------------------------------------------------------

_IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)


def check_image_paths_exist(slide_path: Path, project_root: Path) -> Optional[QAFailure]:
    """INV-19: Verify all <img src="..."> paths resolve to existing files.

    Resolves paths relative to the slide's directory. Skips data: URIs.
    Returns QAFailure listing missing image files, else None.
    """
    html = slide_path.read_text(encoding="utf-8")
    slides_dir = slide_path.parent

    missing: list[str] = []
    for match in _IMG_SRC_RE.finditer(html):
        src = match.group(1)
        if src.startswith("data:"):
            continue
        resolved = (slides_dir / src).resolve()
        if not resolved.is_file():
            missing.append(src)

    if missing:
        return {
            "invariant": "INV-19",
            "description": (
                f"Image files referenced by <img> tags are missing: "
                f"{', '.join(missing)}."
            ),
            "revision_instruction": (
                "Ensure all image files referenced in <img src=...> "
                "exist at the specified paths relative to the slides/ "
                f"directory. Missing: {', '.join(missing)}."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# INV-23: check_math_assets_exist
# ---------------------------------------------------------------------------


def check_math_assets_exist(slide_path: Path, project_root: Path) -> Optional[QAFailure]:
    """INV-23: Verify KaTeX assets exist when KaTeX is referenced in slide.

    If the slide HTML contains 'katex' (case-insensitive), checks that
    a KaTeX stylesheet exists under assets/vendor/. Returns QAFailure
    if KaTeX is referenced but assets are missing, else None.
    """
    html = slide_path.read_text(encoding="utf-8")
    if "katex" not in html.lower():
        return None

    vendor_dir = project_root / "assets" / "vendor"
    # Check common KaTeX stylesheet locations
    katex_paths = [
        vendor_dir / "katex" / "katex.min.css",
        vendor_dir / "katex" / "katex.css",
    ]
    # Also search for any katex*.css under vendor/
    found = False
    for candidate in katex_paths:
        if candidate.is_file():
            found = True
            break
    if not found and vendor_dir.is_dir():
        for css_file in vendor_dir.rglob("katex*.css"):
            found = True
            break

    if not found:
        return {
            "invariant": "INV-23",
            "description": (
                "Slide references KaTeX but no KaTeX stylesheet was found "
                "under assets/vendor/."
            ),
            "revision_instruction": (
                "Ensure KaTeX assets are bundled under assets/vendor/katex/. "
                "At minimum, assets/vendor/katex/katex.min.css must exist."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# INV-13: check_images_respect_margins (Playwright-based)
# ---------------------------------------------------------------------------


def check_images_respect_margins(
    page: "playwright.sync_api.Page",
) -> Optional[QAFailure]:
    """INV-13: Verify all images stay within 10% horizontal margins.

    Evaluates JS to check each <img> bounding rect against 10% margins
    of the slide width. Returns QAFailure if any image violates.
    """
    script = """
    () => {
        const imgs = document.querySelectorAll('img');
        const slideWidth = document.body.scrollWidth || window.innerWidth;
        const leftMargin = slideWidth * 0.1;
        const rightMargin = slideWidth * 0.9;
        const violations = [];
        for (const img of imgs) {
            const rect = img.getBoundingClientRect();
            if (rect.width === 0 && rect.height === 0) continue;
            if (rect.left < leftMargin || rect.right > rightMargin) {
                violations.push({
                    src: img.getAttribute('src') || '(no src)',
                    left: Math.round(rect.left),
                    right: Math.round(rect.right),
                });
            }
        }
        return violations.length > 0 ? violations : null;
    }
    """
    result = page.evaluate(script)
    if result:
        descs = [
            f"{v['src']} (left={v['left']}, right={v['right']})"
            for v in result
        ]
        return {
            "invariant": "INV-13",
            "description": (
                f"Images exceed 10% horizontal margins: "
                f"{'; '.join(descs)}."
            ),
            "revision_instruction": (
                "Resize or reposition images so they stay within the 10% "
                "horizontal margin on each side of the slide."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# INV-14: check_math_no_overflow (Playwright-based)
# ---------------------------------------------------------------------------


def check_math_no_overflow(
    page: "playwright.sync_api.Page",
) -> Optional[QAFailure]:
    """INV-14: Verify math (KaTeX) elements do not overflow their parents.

    Evaluates JS to check each .katex element's scrollWidth against
    its parent's clientWidth. Returns QAFailure if overflow detected.
    """
    script = """
    () => {
        const els = document.querySelectorAll('.katex');
        const overflows = [];
        for (const el of els) {
            if (el.scrollWidth > el.parentElement.clientWidth) {
                overflows.push({
                    text: el.textContent.substring(0, 60),
                    scrollW: el.scrollWidth,
                    parentW: el.parentElement.clientWidth,
                });
            }
        }
        return overflows.length > 0 ? overflows : null;
    }
    """
    result = page.evaluate(script)
    if result:
        return {
            "invariant": "INV-14",
            "description": (
                f"Math (KaTeX) elements overflow their containers: "
                f"{len(result)} element(s) affected."
            ),
            "revision_instruction": (
                "Reduce the size of math expressions or increase the "
                "container width so that KaTeX-rendered math does not "
                "overflow horizontally."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# INV-15: check_diagrams_no_errors (Playwright-based)
# ---------------------------------------------------------------------------


def check_diagrams_no_errors(
    page: "playwright.sync_api.Page",
) -> Optional[QAFailure]:
    """INV-15: Verify no diagram rendering errors are present in the DOM.

    Checks for .mermaid .error, .error-text, [data-error], and elements
    containing "Syntax error" or "Parse error". Returns QAFailure if found.
    """
    script = """
    () => {
        const selectors = [
            '.mermaid .error',
            '.error-text',
            '[data-error]',
        ];
        for (const sel of selectors) {
            if (document.querySelector(sel)) {
                return sel;
            }
        }
        const allEls = document.querySelectorAll('*');
        for (const el of allEls) {
            const text = el.textContent || '';
            if (/Syntax error/i.test(text) || /Parse error/i.test(text)) {
                if (el.children.length === 0) {
                    return 'text:' + text.substring(0, 80);
                }
            }
        }
        return null;
    }
    """
    result = page.evaluate(script)
    if result:
        return {
            "invariant": "INV-15",
            "description": (
                f"Diagram rendering error detected in DOM: {result}."
            ),
            "revision_instruction": (
                "Fix the diagram source code to eliminate rendering errors. "
                "Check Mermaid syntax and ensure all diagram definitions "
                "are valid."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# INV-20: check_image_aspect_ratio (Playwright-based)
# ---------------------------------------------------------------------------


def check_image_aspect_ratio(
    page: "playwright.sync_api.Page",
) -> Optional[QAFailure]:
    """INV-20: Verify images are not distorted beyond 2% aspect ratio change.

    Compares each <img>'s naturalWidth/naturalHeight to its rendered
    width/height. Returns QAFailure if distortion exceeds 2%.
    """
    script = """
    () => {
        const imgs = document.querySelectorAll('img');
        const distorted = [];
        for (const img of imgs) {
            if (!img.naturalWidth || !img.naturalHeight) continue;
            if (!img.width || !img.height) continue;
            const naturalRatio = img.naturalWidth / img.naturalHeight;
            const renderedRatio = img.width / img.height;
            const distortion = Math.abs(naturalRatio - renderedRatio) / naturalRatio;
            if (distortion > 0.02) {
                distorted.push({
                    src: img.getAttribute('src') || '(no src)',
                    naturalRatio: naturalRatio.toFixed(3),
                    renderedRatio: renderedRatio.toFixed(3),
                    distortion: (distortion * 100).toFixed(1),
                });
            }
        }
        return distorted.length > 0 ? distorted : null;
    }
    """
    result = page.evaluate(script)
    if result:
        descs = [
            f"{v['src']} ({v['distortion']}% distortion)"
            for v in result
        ]
        return {
            "invariant": "INV-20",
            "description": (
                f"Images have aspect ratio distortion >2%: "
                f"{'; '.join(descs)}."
            ),
            "revision_instruction": (
                "Preserve image aspect ratios by using CSS "
                "object-fit: contain or removing explicit width/height "
                "overrides that distort the original proportions."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# INV-22: check_inline_math_line_height (Playwright-based)
# ---------------------------------------------------------------------------


def check_inline_math_line_height(
    page: "playwright.sync_api.Page",
) -> Optional[QAFailure]:
    """INV-22: Verify inline math does not increase line height by >5%.

    Finds .katex-inline elements and compares each element's offsetHeight
    to the parent's computed lineHeight. Returns QAFailure if any inline
    math causes >5% line-height increase.
    """
    script = """
    () => {
        const els = document.querySelectorAll('.katex-inline');
        const violations = [];
        for (const el of els) {
            const parent = el.parentElement;
            if (!parent) continue;
            const parentLineHeight = parseFloat(
                window.getComputedStyle(parent).lineHeight
            );
            if (isNaN(parentLineHeight) || parentLineHeight === 0) continue;
            const elHeight = el.offsetHeight;
            const increase = (elHeight - parentLineHeight) / parentLineHeight;
            if (increase > 0.05) {
                violations.push({
                    text: el.textContent.substring(0, 40),
                    elHeight: Math.round(elHeight),
                    lineHeight: Math.round(parentLineHeight),
                    increase: (increase * 100).toFixed(1),
                });
            }
        }
        return violations.length > 0 ? violations : null;
    }
    """
    result = page.evaluate(script)
    if result:
        return {
            "invariant": "INV-22",
            "description": (
                f"Inline math elements increase line height by >5%: "
                f"{len(result)} element(s) affected."
            ),
            "revision_instruction": (
                "Reduce the size of inline math expressions or adjust "
                "CSS to prevent .katex-inline elements from increasing "
                "the surrounding line height by more than 5%."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# run_programmatic_checks
# ---------------------------------------------------------------------------


def run_programmatic_checks(
    slide_path: Path,
    screenshot_path: Path,
    style_config: dict[str, Any],
    page: "playwright.sync_api.Page",
    slug: str = "",
    project_root: Optional[Path] = None,
) -> tuple[list[QAFailure], list[QAWarning], bool]:
    """Run all programmatic invariant checks assigned to qa_checker.py.

    Returns (failures, warnings, veto) tuple. If veto is True, the
    slide has a hard-blocker violation per REQ-QA-2.

    BUG-AUDIT-38: added 10 new INV checks (12-23) alongside the
    original 5 (04/06/07/08/10) and 3 VETOs (01/04/06).
    """
    failures: list[QAFailure] = []
    warnings: list[QAWarning] = []
    veto = False

    # Infer project_root from slide_path if not provided
    if project_root is None:
        project_root = slide_path.parent.parent  # slides/<slug>.html → project/

    # --- Original INV checks ---

    # INV-04: contrast
    result = check_contrast(page)
    if result is not None:
        failures.append(result)

    # INV-06: no inline styles
    result = check_no_inline_styles(slide_path)
    if result is not None:
        failures.append(result)

    # INV-07: no external requests
    result = check_no_external_requests(slide_path)
    if result is not None:
        failures.append(result)

    # INV-08: aspect ratio
    result = check_aspect_ratio(page, style_config)
    if result is not None:
        failures.append(result)

    # INV-10: permitted libraries
    permitted = style_config.get("constraints", {}).get("permitted_diagram_types", [])
    result = check_permitted_libraries(slide_path, permitted)
    if result is not None:
        failures.append(result)

    # --- BUG-AUDIT-38: 10 new INV checks ---

    # INV-12: valid HTML5
    result = check_valid_html5(slide_path)
    if result is not None:
        failures.append(result)

    # INV-13: images respect margins
    result = check_images_respect_margins(page)
    if result is not None:
        failures.append(result)

    # INV-14: math doesn't overflow
    result = check_math_no_overflow(page)
    if result is not None:
        failures.append(result)

    # INV-15: diagrams render clean
    result = check_diagrams_no_errors(page)
    if result is not None:
        failures.append(result)

    # INV-16: fonts loadable
    result = check_fonts_loadable(slide_path, project_root)
    if result is not None:
        failures.append(result)

    # INV-17: CSS vars defined
    result = check_css_vars_defined(slide_path, project_root)
    if result is not None:
        failures.append(result)

    # INV-19: image paths exist
    result = check_image_paths_exist(slide_path, project_root)
    if result is not None:
        failures.append(result)

    # INV-20: image aspect ratio
    result = check_image_aspect_ratio(page)
    if result is not None:
        failures.append(result)

    # INV-22: inline math line-height
    result = check_inline_math_line_height(page)
    if result is not None:
        failures.append(result)

    # INV-23: math assets exist
    result = check_math_assets_exist(slide_path, project_root)
    if result is not None:
        failures.append(result)

    # --- BUG-AUDIT-37: VETO checks (hard blockers) ---

    result = check_text_overflow(page)
    if result is not None:
        failures.append(result)
        veto = True

    result = check_raw_source_visible(page)
    if result is not None:
        failures.append(result)
        veto = True

    result = check_slug_not_in_content(page, slug)
    if result is not None:
        failures.append(result)
        veto = True

    return failures, warnings, veto


# ---------------------------------------------------------------------------
# BC-9.2 / BC-9.3: main_qa_checker
# ---------------------------------------------------------------------------


def main_qa_checker(
    slide_path: Path,
    screenshot_path: Path,
    project_root: Path,
) -> None:
    """Entry point for the QA checker.

    Open own sync_playwright() context per invocation (BC-9.2).
    Render slide HTML, take screenshot, save to screenshot_path (BC-9.3).
    Run all programmatic invariant checks in tiered order.
    Output JSON result to stdout.

    Exit codes:
      0 — result on stdout (may include failures)
      1 — generic failure (Playwright crash, file not found)
      2 — conda env corruption (json_repair unavailable)
      3 — usage error
    """
    # BC-9.11: check json_repair at entry
    _check_json_repair()

    slug = slide_path.stem

    # Read style_config.json if available
    style_config: dict[str, Any] = {}
    style_config_path = project_root / "style_config.json"
    if style_config_path.exists():
        try:
            style_config = json.loads(style_config_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    ctx = sync_playwright()
    pw = ctx.__enter__()
    try:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})

        # BC-9.3: screenshot BEFORE checks
        slide_url = slide_path.resolve().as_uri()
        page.goto(slide_url)
        page.wait_for_load_state("load")

        try:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_path))
        except Exception as exc:
            # Screenshot failed — write failure entry to qa_log and exit 1
            failure: QAFailure = {
                "invariant": "SCREENSHOT",
                "description": (f"Playwright screenshot failed: {exc}"),
                "revision_instruction": (
                    "Re-render the slide. If the error persists, "
                    "check the slide HTML for syntax errors."
                ),
            }
            entry = build_qa_log_entry(
                slug=slug,
                passed=False,
                veto=False,
                checks_run=[],
                failures=[failure],
                warnings=[],
            )
            append_qa_log(project_root, entry)
            sys.exit(1)

        # Run programmatic checks (BUG-AUDIT-37 veto + BUG-AUDIT-38 full INV)
        failures, warnings, veto = run_programmatic_checks(
            slide_path, screenshot_path, style_config, page,
            slug=slug, project_root=project_root,
        )
        checks_run = [
            "INV-04", "INV-06", "INV-07", "INV-08", "INV-10",
            "INV-12", "INV-13", "INV-14", "INV-15", "INV-16",
            "INV-17", "INV-19", "INV-20", "INV-22", "INV-23",
            "VETO-01", "VETO-04", "VETO-06",
        ]
        passed = len(failures) == 0
        entry = build_qa_log_entry(
            slug=slug,
            passed=passed,
            veto=veto,
            checks_run=checks_run,
            failures=failures,
            warnings=warnings,
        )
        append_qa_log(project_root, entry)
        print(json.dumps(entry))
        browser.close()
        sys.exit(0)

    except SystemExit:
        raise
    except Exception as exc:
        failure = {
            "invariant": "PLAYWRIGHT",
            "description": f"Playwright error: {exc}",
            "revision_instruction": (
                "Check that the slide HTML is valid and Playwright is "
                "properly installed."
            ),
        }
        entry = build_qa_log_entry(
            slug=slug,
            passed=False,
            veto=False,
            checks_run=[],
            failures=[failure],
            warnings=[],
        )
        append_qa_log(project_root, entry)
        sys.exit(1)
    finally:
        ctx.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# check_slide_iteration_limit (REQ-SLIDE-5 / BUG-AUDIT-35)
# ---------------------------------------------------------------------------


def check_slide_iteration_limit(
    slug: str,
    project_root: Path,
    limit: int = 5,
) -> dict[str, Any]:
    """Count consecutive RED qa_log entries for a slug from the tail.

    Reads ``output/qa_log.jsonl``, filters for the given slug, and
    counts how many consecutive ``passed: false`` entries appear from
    the most recent entry backward. Stops at the first GREEN (passed)
    entry or at the beginning of the log.

    Returns ``{"limit_reached": bool, "iteration": int, "limit": int}``.
    """
    log_path = project_root / "output" / "qa_log.jsonl"
    if not log_path.is_file():
        return {"limit_reached": False, "iteration": 0, "limit": limit}

    entries: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("slug") == slug:
            entries.append(entry)

    consecutive_red = 0
    for entry in reversed(entries):
        if entry.get("passed", True):
            break
        consecutive_red += 1

    return {
        "limit_reached": consecutive_red >= limit,
        "iteration": consecutive_red,
        "limit": limit,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> tuple:
    import argparse

    parser = argparse.ArgumentParser(
        description="Debrief QA checker — programmatic slide invariant checks"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Default: run QA checks
    check_parser = subparsers.add_parser("check", help="Run QA checks")
    check_parser.add_argument("--slide-path", required=True, type=Path)
    check_parser.add_argument("--screenshot-path", required=True, type=Path)
    check_parser.add_argument("--project-root", required=True, type=Path)

    # BUG-AUDIT-35: check iteration limit
    limit_parser = subparsers.add_parser(
        "check_limit", help="Check red-green iteration limit for a slug"
    )
    limit_parser.add_argument("--slug", required=True)
    limit_parser.add_argument("--project-root", required=True, type=Path)
    limit_parser.add_argument("--limit", type=int, default=5)

    args = parser.parse_args()

    if args.command == "check_limit":
        return ("check_limit", args)
    if args.command == "check":
        return ("check", args)
    # Backward compat: no subcommand → original positional args
    parser2 = argparse.ArgumentParser()
    parser2.add_argument("--slide-path", required=True, type=Path)
    parser2.add_argument("--screenshot-path", required=True, type=Path)
    parser2.add_argument("--project-root", required=True, type=Path)
    args2 = parser2.parse_args()
    return ("check", args2)


if __name__ == "__main__":
    _cmd, _args = _parse_args()
    if _cmd == "check_limit":
        result = check_slide_iteration_limit(
            _args.slug, _args.project_root, _args.limit
        )
        print(json.dumps(result))
    else:
        main_qa_checker(_args.slide_path, _args.screenshot_path, _args.project_root)
