# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-38: 10 new programmatic INV checks."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent

for _dir in (
    _PROJECT_ROOT / "src" / ("unit_9" if (_PROJECT_ROOT / "src" / "unit_9").is_dir() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

from qa_checker import (  # noqa: E402
    check_css_vars_defined,
    check_diagrams_no_errors,
    check_image_paths_exist,
    check_images_respect_margins,
    check_math_assets_exist,
    check_valid_html5,
)


class TestInv12ValidHtml5:
    def test_valid_html_passes(self, tmp_path: Path) -> None:
        slide = tmp_path / "test.html"
        slide.write_text("<html><head></head><body><h1>Title</h1></body></html>")
        assert check_valid_html5(slide) is None

    def test_unclosed_div_fails(self, tmp_path: Path) -> None:
        slide = tmp_path / "test.html"
        slide.write_text("<html><body><div>open but not closed</body></html>")
        result = check_valid_html5(slide)
        assert result is not None
        assert result["invariant"] == "INV-12"


class TestInv17CssVarsDefined:
    def test_all_vars_defined_passes(self, tmp_path: Path) -> None:
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "style.css").write_text(
            ":root { --color-primary: #000; --spacing-gap: 20px; }"
        )
        slide = tmp_path / "slides" / "test.html"
        slide.parent.mkdir()
        slide.write_text(
            '<html><body><div style="color:var(--color-primary)">x</div></body></html>'
        )
        assert check_css_vars_defined(slide, tmp_path) is None

    def test_undefined_var_fails(self, tmp_path: Path) -> None:
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "style.css").write_text(":root { --color-primary: #000; }")
        slide = tmp_path / "slides" / "test.html"
        slide.parent.mkdir()
        slide.write_text(
            '<html><body><div style="gap:var(--missing-var)">x</div></body></html>'
        )
        result = check_css_vars_defined(slide, tmp_path)
        assert result is not None
        assert result["invariant"] == "INV-17"


class TestInv19ImagePathsExist:
    def test_existing_image_passes(self, tmp_path: Path) -> None:
        img = tmp_path / "assets" / "images" / "photo.png"
        img.parent.mkdir(parents=True)
        img.write_bytes(b"\x89PNG")
        slide = tmp_path / "slides" / "test.html"
        slide.parent.mkdir()
        slide.write_text('<html><body><img src="../assets/images/photo.png"></body></html>')
        assert check_image_paths_exist(slide, tmp_path) is None

    def test_missing_image_fails(self, tmp_path: Path) -> None:
        slide = tmp_path / "slides" / "test.html"
        slide.parent.mkdir()
        slide.write_text('<html><body><img src="../assets/images/gone.png"></body></html>')
        result = check_image_paths_exist(slide, tmp_path)
        assert result is not None
        assert result["invariant"] == "INV-19"

    def test_data_uri_skipped(self, tmp_path: Path) -> None:
        slide = tmp_path / "slides" / "test.html"
        slide.parent.mkdir()
        slide.write_text('<html><body><img src="data:image/png;base64,abc"></body></html>')
        assert check_image_paths_exist(slide, tmp_path) is None


class TestInv23MathAssetsExist:
    def test_katex_with_assets_passes(self, tmp_path: Path) -> None:
        vendor = tmp_path / "assets" / "vendor" / "katex"
        vendor.mkdir(parents=True)
        (vendor / "katex.min.css").write_text("/* katex */")
        slide = tmp_path / "slides" / "test.html"
        slide.parent.mkdir()
        slide.write_text('<html><body><span class="katex">x</span></body></html>')
        assert check_math_assets_exist(slide, tmp_path) is None

    def test_katex_without_assets_fails(self, tmp_path: Path) -> None:
        (tmp_path / "assets" / "vendor").mkdir(parents=True)
        slide = tmp_path / "slides" / "test.html"
        slide.parent.mkdir()
        slide.write_text('<html><body><span class="katex">x</span></body></html>')
        result = check_math_assets_exist(slide, tmp_path)
        assert result is not None
        assert result["invariant"] == "INV-23"

    def test_no_katex_skips_check(self, tmp_path: Path) -> None:
        slide = tmp_path / "slides" / "test.html"
        slide.parent.mkdir()
        slide.write_text("<html><body>No math here</body></html>")
        assert check_math_assets_exist(slide, tmp_path) is None


class TestInv13ImagesRespectMargins:
    def test_no_images_passes(self) -> None:
        page = MagicMock()
        page.evaluate.return_value = None
        assert check_images_respect_margins(page) is None

    def test_image_in_margins_passes(self) -> None:
        page = MagicMock()
        page.evaluate.return_value = None  # JS returns null if all ok
        assert check_images_respect_margins(page) is None


class TestInv15DiagramsNoErrors:
    def test_no_errors_passes(self) -> None:
        page = MagicMock()
        page.evaluate.return_value = None
        assert check_diagrams_no_errors(page) is None

    def test_error_detected(self) -> None:
        page = MagicMock()
        page.evaluate.return_value = "Syntax error in mermaid diagram"
        result = check_diagrams_no_errors(page)
        assert result is not None
        assert result["invariant"] == "INV-15"
