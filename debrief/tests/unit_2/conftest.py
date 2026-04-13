# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Pytest configuration for Unit 2 tests.

Adds src/debrief to sys.path so that ``debrief_state`` is importable
without a package prefix.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Project root is 2 levels above this file (tests/unit_2/conftest.py)
_project_root = Path(__file__).resolve().parent.parent.parent
_src_debrief = _project_root / "src" / "debrief"

if str(_src_debrief) not in sys.path:
    sys.path.insert(0, str(_src_debrief))
