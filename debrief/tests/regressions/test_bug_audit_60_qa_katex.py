# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-60 Cluster 2 (KaTeX false positives).

Smoke test Round 3 found two HIGH-severity bugs in the QA gates for math
slides. Both forced `accepted_violations` bookkeeping on every KaTeX slide
until workarounds were applied.

- BUG-ST-c-1 (HIGH): `_KNOWN_DIAGRAM_LIBS` in qa_checker.py:175 included
  `katex`. INV-10's permitted-library check treated KaTeX as a diagram
  library, so math slides failed unless the user added `katex` to
  `constraints.permitted_diagram_types`. KaTeX is a math renderer, gated
  by `constraints.math_renderer`.
- BUG-ST-c-2 (HIGH): VETO-01's `check_text_overflow` walked every element
  and skipped only `display:none` / `visibility:hidden`. KaTeX's
  `.katex-mathml` accessibility sibling uses the SR-only pattern
  (`position:absolute; clip:rect(1px,1px,1px,1px); overflow:hidden;
  width:1px; height:1px`) — visually invisible but scrollWidth >
  clientWidth. The check tripped on every math slide.

Coverage (REQ-QA-INV10-1, REQ-QA-VETO01-1; BC-9.5, BC-9.5a):

1. `_KNOWN_DIAGRAM_LIBS` no longer contains `katex`.
2. INV-10 passes on a slide referencing katex.min.js even when `katex`
   is not in `permitted_diagram_types`.
3. INV-10 still catches a non-permitted true diagram library (regression
   guard — scope of fix did not break anything).
4. VETO-01 overflow script excludes aria-hidden, .katex-mathml, .sr-only,
   .visually-hidden.
5. VETO-01 still catches genuine overflow (MagicMock-backed).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_9").is_dir()


for _dir in (
    _PROJECT_ROOT / "src" / ("unit_9" if _is_workspace_layout() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import qa_checker  # noqa: E402
from qa_checker import (  # noqa: E402
    _KNOWN_DIAGRAM_LIBS,
    check_permitted_libraries,
    check_text_overflow,
)


# ---------------------------------------------------------------------------
# 1. _KNOWN_DIAGRAM_LIBS no longer contains "katex"
# ---------------------------------------------------------------------------


def test_known_diagram_libs_excludes_katex():
    """BUG-AUDIT-60 / BUG-ST-c-1 / REQ-QA-INV10-1:
    Math renderers MUST NOT live in the diagram-library list.
    """
    assert "katex" not in _KNOWN_DIAGRAM_LIBS, (
        f"_KNOWN_DIAGRAM_LIBS still contains 'katex': {_KNOWN_DIAGRAM_LIBS}. "
        "KaTeX is a math renderer gated by constraints.math_renderer, "
        "not a diagram library. See BUG-ST-c-1."
    )


def test_known_diagram_libs_contract_shape():
    """Sanity check: the list still contains the real diagram libs."""
    expected = {"mermaid", "rough", "d3", "chart"}
    assert set(_KNOWN_DIAGRAM_LIBS) == expected, (
        f"_KNOWN_DIAGRAM_LIBS shape changed unexpectedly: {_KNOWN_DIAGRAM_LIBS}. "
        f"Expected exactly {expected}."
    )


# ---------------------------------------------------------------------------
# 2. INV-10 passes on a KaTeX slide without katex in permitted_diagram_types
# ---------------------------------------------------------------------------


_KATEX_SLIDE_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <link rel="stylesheet" href="../assets/vendor/katex/katex.min.css">
  <script src="../assets/vendor/katex/katex.min.js"></script>
</head>
<body>
  <div class="slide">
    <h1>Bayes' theorem</h1>
    <div class="katex-src" data-display="true">P(A|B) = P(B|A)P(A)/P(B)</div>
  </div>
</body>
</html>
"""


def test_inv10_passes_on_katex_slide_without_katex_in_permitted(tmp_path):
    """BUG-AUDIT-60 / BUG-ST-c-1:
    A slide with <script src=katex.min.js> must pass INV-10 even when
    katex is NOT in permitted_diagram_types — math rendering is gated by
    constraints.math_renderer, not by permitted_diagram_types.
    """
    slide = tmp_path / "bayes.html"
    slide.write_text(_KATEX_SLIDE_HTML, encoding="utf-8")

    # Deliberately DO NOT include katex in the permitted list — replicates
    # the smoke-test baseline (["rough.js", "mermaid", "inline-svg"]).
    result = check_permitted_libraries(
        slide, permitted=["rough.js", "mermaid", "inline-svg"]
    )
    assert result is None, (
        f"INV-10 incorrectly failed on a KaTeX-bearing slide: {result}. "
        "KaTeX should not trigger the diagram-library check."
    )


def test_inv10_still_catches_forbidden_diagram_lib(tmp_path):
    """Regression guard: removing katex must not break the real check.
    A slide referencing an unpermitted diagram library must still fail.
    """
    forbidden_slide_html = """<!doctype html>
<html><head><script src="../assets/vendor/mermaid.min.js"></script></head>
<body><div class="slide"></div></body></html>
"""
    slide = tmp_path / "diagram.html"
    slide.write_text(forbidden_slide_html, encoding="utf-8")

    # permitted list excludes mermaid
    result = check_permitted_libraries(
        slide, permitted=["rough.js", "inline-svg"]
    )
    assert result is not None, "INV-10 must still fail on unpermitted diagram lib"
    assert result["invariant"] == "INV-10"
    assert "mermaid" in result["description"].lower()


def test_inv10_accepts_permitted_diagram_lib(tmp_path):
    """Baseline: permitted library does not trip the check."""
    rough_slide_html = """<!doctype html>
<html><head><script src="../assets/vendor/rough.min.js"></script></head>
<body><div class="slide"></div></body></html>
"""
    slide = tmp_path / "rough.html"
    slide.write_text(rough_slide_html, encoding="utf-8")
    result = check_permitted_libraries(
        slide, permitted=["rough.js", "mermaid", "inline-svg"]
    )
    assert result is None


# ---------------------------------------------------------------------------
# 3. VETO-01 overflow script excludes a11y-hidden elements
# ---------------------------------------------------------------------------


def _veto01_script() -> str:
    """Extract the JS source embedded in check_text_overflow by introspecting
    the function. We want to verify the exclusion predicate is present
    without running a real browser."""
    import inspect
    return inspect.getsource(check_text_overflow)


def test_veto01_script_excludes_aria_hidden():
    src = _veto01_script()
    assert "aria-hidden" in src, (
        "check_text_overflow must skip aria-hidden='true' elements"
    )


def test_veto01_script_excludes_katex_mathml():
    src = _veto01_script()
    assert "katex-mathml" in src, (
        "check_text_overflow must skip .katex-mathml (SR-only a11y span)"
    )


def test_veto01_script_excludes_sr_only_patterns():
    src = _veto01_script()
    assert "sr-only" in src, (
        "check_text_overflow must skip .sr-only elements"
    )
    assert "visually-hidden" in src, (
        "check_text_overflow must skip .visually-hidden elements"
    )


def test_veto01_exclusion_applied_before_overflow_check():
    """Per BC-9.5a: exclusions MUST run before the scrollWidth check to
    avoid evaluating overflow on intentionally-clipped SR-only nodes.
    """
    src = _veto01_script()
    # Find positions of the exclusion markers and the scrollWidth check
    m_aria = src.find("aria-hidden")
    m_scroll = src.find("scrollWidth > el.clientWidth")
    assert m_aria != -1 and m_scroll != -1
    assert m_aria < m_scroll, (
        "a11y exclusion predicate must be positioned before the scrollWidth "
        "check in the JS body"
    )


# ---------------------------------------------------------------------------
# 4. VETO-01 still catches real overflow
# ---------------------------------------------------------------------------


def _mock_page(overflow_element: str = None) -> MagicMock:
    page = MagicMock()
    page.evaluate.return_value = overflow_element
    return page


def test_veto01_still_fires_on_genuine_overflow():
    """Regression guard: mocking an overflow return value must still
    produce the expected VETO-01 failure dict."""
    page = _mock_page(overflow_element="DIV.content-area")
    result = check_text_overflow(page)
    assert result is not None
    assert result["invariant"] == "VETO-01"
    assert "overflow" in result["description"].lower()


def test_veto01_no_overflow_returns_none():
    page = _mock_page(overflow_element=None)
    assert check_text_overflow(page) is None
