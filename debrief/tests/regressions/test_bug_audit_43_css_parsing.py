# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-43: parse_css_int utility."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent

for _dir in (
    _PROJECT_ROOT / "src" / ("unit_2" if (_PROJECT_ROOT / "src" / "unit_2").is_dir() else "debrief"),
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

from debrief_state import parse_css_int  # noqa: E402


class TestParseCssInt:
    """BUG-AUDIT-43: parse_css_int must handle int, CSS strings, and fallback."""

    def test_int_passthrough(self) -> None:
        assert parse_css_int(1920) == 1920

    def test_float_passthrough(self) -> None:
        assert parse_css_int(1920.5) == 1920

    def test_string_with_px(self) -> None:
        assert parse_css_int("1920px") == 1920

    def test_string_with_em(self) -> None:
        assert parse_css_int("2em") == 2

    def test_string_with_percent(self) -> None:
        assert parse_css_int("50%") == 50

    def test_bare_numeric_string(self) -> None:
        assert parse_css_int("1080") == 1080

    def test_string_with_whitespace(self) -> None:
        assert parse_css_int("  1920px  ") == 1920

    def test_auto_returns_default(self) -> None:
        assert parse_css_int("auto") == 0
        assert parse_css_int("auto", default=1920) == 1920

    def test_none_returns_default(self) -> None:
        assert parse_css_int(None) == 0

    def test_empty_string_returns_default(self) -> None:
        assert parse_css_int("") == 0

    def test_custom_default(self) -> None:
        assert parse_css_int("invalid", default=42) == 42
