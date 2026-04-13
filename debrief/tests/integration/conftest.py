# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Pytest configuration for integration tests.

Adds src/debrief to sys.path so that all modules are importable by their
bare names (e.g. ``debrief_state``, ``launcher``, ``ledger``,
``style_engine``, ``qa_checker``, ``visual_qa``, ``utility_skills``,
``paper_analyzer``).
"""
from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
_src_debrief = str(_project_root / "src" / "debrief")

if _src_debrief not in sys.path:
    sys.path.insert(0, _src_debrief)

# Expose the project root for tests that need it.
PROJECT_ROOT = _project_root
PLUGIN_ROOT = _project_root  # plugin scaffold is at the project root
