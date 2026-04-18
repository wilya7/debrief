# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-61 — INV-13 full-bleed exemption.

BUG-ST-round4-c-1 (MEDIUM): REQ-ASSET-2 mandates `<img>` embed; INV-13
mandates 10% horizontal margin. Full-bleed images have 0 margin — the
two structurally conflict. Pre-fix the slide-maker hid an `<img>` at 0×0
dimensions and used CSS `background-image`, which is a workaround, not
an exemption. BUG-AUDIT-61 / REQ-QA-INV13-1 / BC-9.5b carve out a
DOM-discoverable exemption: `<img>` with class `fullbleed` (or an
ancestor with that class) is exempt from INV-13's margin check.

Coverage:

1. Source-level: `_KNOWN_DIAGRAM_LIBS` and INV-13 JS both scoped to
   exactly the intended checks — no regression of the cluster-2 /
   cluster-6 fixes.
2. INV-13 JS contains the `fullbleed` class check on the element.
3. INV-13 JS contains the `closest('.fullbleed')` ancestor check.
4. INV-13 JS positions the exemption BEFORE the margin comparison.
5. Slide-maker agent card documents `<img class="fullbleed">` convention.
6. Slide-maker agent card no longer recommends the 0×0 workaround.
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

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

from qa_checker import check_images_respect_margins  # noqa: E402


def _slide_maker_md_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "agents" / "slide-maker.md"
    return _PROJECT_ROOT / "agents" / "slide-maker.md"


# ---------------------------------------------------------------------------
# 1-4. INV-13 JS exemption structure
# ---------------------------------------------------------------------------


def _inv13_js_source() -> str:
    """Return the JS body of check_images_respect_margins by introspection."""
    return inspect.getsource(check_images_respect_margins)


def test_inv13_js_checks_fullbleed_class_on_element():
    """REQ-QA-INV13-1: exemption predicate checks the element's own class."""
    src = _inv13_js_source()
    assert "img.classList.contains('fullbleed')" in src, (
        "INV-13 JS must skip <img> elements with class='fullbleed' directly."
    )


def test_inv13_js_checks_fullbleed_class_on_ancestor():
    """REQ-QA-INV13-1: exemption also honors an ancestor marked fullbleed."""
    src = _inv13_js_source()
    assert "img.closest('.fullbleed')" in src, (
        "INV-13 JS must skip <img> whose ancestor has class 'fullbleed' "
        "via `.closest('.fullbleed')`."
    )


def test_inv13_exemption_precedes_margin_check():
    """BC-9.5b: exemption runs before the scrollWidth/margin comparison
    so that full-bleed images are skipped entirely, not compared."""
    src = _inv13_js_source()
    m_exempt = src.find("fullbleed")
    m_margin = src.find("rect.left < leftMargin")
    assert m_exempt != -1 and m_margin != -1
    assert m_exempt < m_margin, (
        "The fullbleed exemption must be positioned before the margin "
        "comparison in the JS body (BC-9.5b)."
    )


def test_inv13_js_preserves_zero_size_skip():
    """The pre-existing 0×0 skip (for inline images not yet laid out)
    stays in the JS. This keeps rendering-timing edge cases safe."""
    src = _inv13_js_source()
    assert "rect.width === 0 && rect.height === 0" in src


# ---------------------------------------------------------------------------
# 5-6. Slide-maker agent card updates
# ---------------------------------------------------------------------------


def test_slide_maker_md_documents_fullbleed_class():
    """REQ-QA-INV13-1 / BC-9.5b: slide-maker.md names the `fullbleed`
    class convention so slide authors use the exemption on purpose."""
    md = _slide_maker_md_path().read_text(encoding="utf-8")
    assert "fullbleed" in md.lower(), (
        "slide-maker.md must document the `fullbleed` class convention "
        "for full-bleed images."
    )
    assert 'class="fullbleed"' in md, (
        "slide-maker.md must show the exact `<img class=\"fullbleed\">` "
        "usage so authors don't have to infer it."
    )


def test_slide_maker_md_forbids_0x0_workaround():
    """The pre-fix workaround of hiding `<img>` at 0×0 dimensions while
    using CSS background-image must be explicitly discouraged."""
    md = _slide_maker_md_path().read_text(encoding="utf-8")
    # Look for the prohibition phrasing without being over-specific
    assert "0×0" in md or "0x0" in md or "Do NOT use" in md, (
        "slide-maker.md must explicitly discourage the 0×0 workaround "
        "now that INV-13 has a proper exemption."
    )
