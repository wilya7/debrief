# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Debrief: AI-powered presentation assistant for scientists.

A Claude Code plugin that turns a domain expert's narrative intent into
a professionally styled, QA-verified PDF slide deck.

The modules in this package use flat intra-package imports (e.g.
``from debrief_state import ...``) for compatibility with the
SVP-native test layout. The __init__.py adds the package directory
to sys.path so those imports resolve whether the package is invoked
as ``python -m debrief.X`` or via conftest sys.path injection.
"""
from __future__ import annotations

import sys
from pathlib import Path

_here = Path(__file__).parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
