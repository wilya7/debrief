# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Pytest configuration for Unit 11 tests.

Adds src/unit_11, src/unit_3, and src/unit_2 to sys.path so that
``utility_skills``, ``launcher``, and ``debrief_state`` are importable
without a package prefix. ``launcher`` is required because
BUG-AUDIT-84 made ``utility_skills.main_script_generator`` a thin
delegator to ``launcher.main_script_writer``.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Project root is 2 levels above this file (tests/unit_11/conftest.py)
_project_root = Path(__file__).resolve().parent.parent.parent
_src_unit11 = _project_root / "src" / "unit_11"
_src_unit3 = _project_root / "src" / "unit_3"
_src_unit2 = _project_root / "src" / "unit_2"

if str(_src_unit11) not in sys.path:
    sys.path.insert(0, str(_src_unit11))

if str(_src_unit3) not in sys.path:
    sys.path.insert(0, str(_src_unit3))

if str(_src_unit2) not in sys.path:
    sys.path.insert(0, str(_src_unit2))
