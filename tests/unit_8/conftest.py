# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Pytest configuration for unit tests.

Adds src/debrief to sys.path so that modules are importable
without a package prefix.
"""
from __future__ import annotations

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
_src_debrief = _project_root / "src" / "debrief"

if str(_src_debrief) not in sys.path:
    sys.path.insert(0, str(_src_debrief))
