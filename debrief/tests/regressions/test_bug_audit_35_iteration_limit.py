# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-35: red-green iteration limit helper."""

from __future__ import annotations

import json
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

from qa_checker import check_slide_iteration_limit  # noqa: E402


def _write_qa_log(root: Path, entries: list[dict]) -> None:
    log_dir = root / "output"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / "qa_log.jsonl").open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _entry(slug: str, passed: bool) -> dict:
    return {"slug": slug, "passed": passed, "revision_instructions": []}


class TestCheckSlideIterationLimit:

    def test_no_log_file_returns_zero(self, tmp_path: Path) -> None:
        result = check_slide_iteration_limit("intro", tmp_path)
        assert result == {"limit_reached": False, "iteration": 0, "limit": 5}

    def test_all_green_returns_zero(self, tmp_path: Path) -> None:
        _write_qa_log(tmp_path, [_entry("intro", True)] * 3)
        result = check_slide_iteration_limit("intro", tmp_path)
        assert result["iteration"] == 0
        assert not result["limit_reached"]

    def test_three_consecutive_red_below_limit(self, tmp_path: Path) -> None:
        _write_qa_log(tmp_path, [
            _entry("intro", True),
            _entry("intro", False),
            _entry("intro", False),
            _entry("intro", False),
        ])
        result = check_slide_iteration_limit("intro", tmp_path)
        assert result["iteration"] == 3
        assert not result["limit_reached"]

    def test_five_consecutive_red_reaches_limit(self, tmp_path: Path) -> None:
        _write_qa_log(tmp_path, [_entry("intro", False)] * 5)
        result = check_slide_iteration_limit("intro", tmp_path)
        assert result["iteration"] == 5
        assert result["limit_reached"]

    def test_green_resets_count(self, tmp_path: Path) -> None:
        _write_qa_log(tmp_path, [
            _entry("intro", False),
            _entry("intro", False),
            _entry("intro", True),  # resets
            _entry("intro", False),
            _entry("intro", False),
        ])
        result = check_slide_iteration_limit("intro", tmp_path)
        assert result["iteration"] == 2

    def test_filters_by_slug(self, tmp_path: Path) -> None:
        _write_qa_log(tmp_path, [
            _entry("intro", False),
            _entry("methods", False),
            _entry("intro", False),
            _entry("methods", False),
            _entry("intro", False),
        ])
        result = check_slide_iteration_limit("intro", tmp_path)
        assert result["iteration"] == 3

    def test_custom_limit(self, tmp_path: Path) -> None:
        _write_qa_log(tmp_path, [_entry("intro", False)] * 3)
        result = check_slide_iteration_limit("intro", tmp_path, limit=3)
        assert result["limit_reached"]
        assert result["limit"] == 3
