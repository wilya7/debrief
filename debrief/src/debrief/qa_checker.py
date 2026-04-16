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
    layout = style_config.get("layout", {})
    expected_w = layout.get("slide_width", 1920)
    expected_h = layout.get("slide_height", 1080)

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
# run_programmatic_checks
# ---------------------------------------------------------------------------


def run_programmatic_checks(
    slide_path: Path,
    screenshot_path: Path,
    style_config: dict[str, Any],
    page: "playwright.sync_api.Page",
) -> tuple[list[QAFailure], list[QAWarning]]:
    """Run all programmatic invariant checks assigned to qa_checker.py.

    Returns (failures, warnings) tuple.
    """
    failures: list[QAFailure] = []
    warnings: list[QAWarning] = []

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

    return failures, warnings


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

        # Run programmatic checks
        failures, warnings = run_programmatic_checks(
            slide_path, screenshot_path, style_config, page
        )
        checks_run = [
            "INV-04",
            "INV-06",
            "INV-07",
            "INV-08",
            "INV-10",
        ]
        passed = len(failures) == 0
        entry = build_qa_log_entry(
            slug=slug,
            passed=passed,
            veto=False,
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
