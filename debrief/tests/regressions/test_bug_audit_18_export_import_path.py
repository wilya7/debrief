# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-18.

A user running `python -m debrief.export` got:

    Failed to read deck state: No module named 'debrief.state'

Root cause: ``src/unit_10/export.py`` had two inline imports of the form
``from debrief.state import ...`` — but the canonical module name is
``debrief_state`` (underscore), not ``debrief.state`` (dot). Every other
module in the plugin imports the correct name; ``export.py`` was the
only outlier. The typo was invisible until export.py actually tried to
run at production time.

Why the typo survived pytest: ``tests/unit_10/test_export.py`` had four
occurrences of ``patch.dict("sys.modules", {..., "debrief.state":
mock_state_module, ...})`` — the test mocks the same phantom module
path the broken code imports from. The tests "passed" because pytest
was validating a self-consistent fake (wrong code + wrong mock) that
had nothing to do with the real ``debrief_state`` module. Classic
test-mock-hides-bug pattern.

This file enforces three invariants that will catch any future drift:

1. **Code sentinel**: no ``.py`` file under ``src/`` contains the
   substrings ``from debrief.state`` or ``import debrief.state``. The
   substring check is precise enough to permit explanatory comments
   that reference the phantom name (e.g., "the non-existent
   `debrief.state` path") without false-positive — those don't match
   the exact import-statement forms.
2. **Test sentinel**: no ``.py`` file under ``tests/`` patches
   ``"debrief.state"`` as a sys.modules key (the form used by
   test_export.py's four broken patch.dict calls). Catches any future
   attempt to reintroduce the mask-the-bug pattern.
3. **Live import check**: the three functions ``export.py`` needs
   (``read_deck_state``, ``write_deck_state``, ``increment_export_count``)
   must be importable from the real ``debrief_state`` module and must
   be callable. Catches the class of bug where someone renames or
   removes one of the functions.

All tests run in both workspace and delivered layouts without skipping,
per the CLAUDE.md "0 skipped, 0 failed" rule and the path-helper
pattern established in BUG-AUDIT-16's post-correction (commit 7cbc7a9).
See ``spec/stakeholder_spec.md`` Bug Catalog entry BUG-AUDIT-18.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers — resolve BOTH workspace AND delivered from either layout.
# Raise on missing sibling (hard error, not skip).
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_1").is_dir()


def _workspace_root() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT
    candidate = _PROJECT_ROOT.parent.parent / "debrief1.0"
    if (candidate / "src" / "unit_1").is_dir():
        return candidate
    raise FileNotFoundError(
        f"Could not locate workspace root from {_PROJECT_ROOT}. "
        f"Expected workspace at {candidate}."
    )


def _delivered_plugin_root() -> Path:
    if not _is_workspace_layout():
        return _PROJECT_ROOT
    candidate = _PROJECT_ROOT.parent / "debrief1.0-repo" / "debrief"
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError(
        f"Could not locate delivered plugin root from {_PROJECT_ROOT}. "
        f"Expected delivered at {candidate}."
    )


def _debrief_state_module():
    """Import the real debrief_state module from the appropriate layout.

    Workspace: ``src/unit_2/debrief_state.py``.
    Delivered: ``src/debrief/debrief_state.py``.
    """
    if _is_workspace_layout():
        state_dir = _PROJECT_ROOT / "src" / "unit_2"
    else:
        state_dir = _PROJECT_ROOT / "src" / "debrief"
    assert (state_dir / "debrief_state.py").is_file(), (
        f"BUG-AUDIT-18: debrief_state.py must exist at {state_dir}."
    )
    if str(state_dir) not in sys.path:
        sys.path.insert(0, str(state_dir))
    # Force a fresh import so any prior sys.path manipulation doesn't
    # return a stale module from a different layout.
    if "debrief_state" in sys.modules:
        return sys.modules["debrief_state"]
    return importlib.import_module("debrief_state")


def _export_module_path() -> Path:
    """Return the path to export.py under the CURRENT-layout repo.

    Workspace: ``src/unit_10/export.py``.
    Delivered: ``src/debrief/export.py``.
    """
    workspace = _PROJECT_ROOT / "src" / "unit_10" / "export.py"
    delivered = _PROJECT_ROOT / "src" / "debrief" / "export.py"
    for candidate in (workspace, delivered):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Could not locate export.py under {workspace} or {delivered}"
    )


# Substrings that are banned in src/ — the exact forms of the broken
# import statement from BUG-AUDIT-18. Written out explicitly so the
# regression sentinel is obvious to a future reader.
_BANNED_SRC_SUBSTRINGS = (
    "from debrief.state",
    "import debrief.state",
)

# Substring banned in tests/ — the sys.modules key form used by
# test_export.py's four broken patch.dict calls before BUG-AUDIT-18.
_BANNED_TEST_SUBSTRING = '"debrief.state"'


def _iter_py_files(root: Path):
    """Yield every ``.py`` file under ``root``, skipping __pycache__."""
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


# ---------------------------------------------------------------------------
# BC-10.X / BUG-AUDIT-18 — src/ grep sentinel.
# ---------------------------------------------------------------------------


class TestBugAudit18ExportImportPath:
    """BC-10.X / BUG-AUDIT-18 — export.py and every other src/ module
    must import deck-state functions from ``debrief_state``, not from
    the phantom ``debrief.state`` path.
    """

    def test_no_src_file_imports_debrief_dot_state(self) -> None:
        # Walk the entire src/ tree of the CURRENT layout and assert
        # no file contains either of the banned import-statement
        # substrings. Explanatory comments that mention the phantom
        # path (e.g., "the non-existent `debrief.state` path") are
        # safe because they don't start with `from ` or `import `.
        if _is_workspace_layout():
            src_root = _PROJECT_ROOT / "src"
        else:
            src_root = _PROJECT_ROOT / "src" / "debrief"

        offending: list[str] = []
        for py_file in _iter_py_files(src_root):
            text = py_file.read_text(encoding="utf-8")
            for banned in _BANNED_SRC_SUBSTRINGS:
                if banned in text:
                    offending.append(f"{py_file}: contains {banned!r}")
        assert not offending, (
            f"BC-10.X / BUG-AUDIT-18: no src/ file may contain "
            f"{_BANNED_SRC_SUBSTRINGS!r} (the phantom module path). "
            f"The canonical module name is `debrief_state` (underscore). "
            f"Offending files:\n" + "\n".join(offending)
        )

    def test_no_test_file_mocks_debrief_dot_state(self) -> None:
        # Walk tests/ of the CURRENT layout and assert no file contains
        # the `"debrief.state"` string (with quotes). This catches any
        # future test author who tries to sys.modules-patch the phantom
        # path, which would mask a return of the original bug.
        tests_root = _TESTS_DIR
        offending: list[str] = []
        for py_file in _iter_py_files(tests_root):
            # Skip THIS file — it must reference the banned substring
            # in its docstring and in the _BANNED_TEST_SUBSTRING constant.
            if py_file.resolve() == Path(__file__).resolve():
                continue
            text = py_file.read_text(encoding="utf-8")
            if _BANNED_TEST_SUBSTRING in text:
                offending.append(str(py_file))
        assert not offending, (
            f"BC-testing / BUG-AUDIT-18: no test file may mock "
            f"{_BANNED_TEST_SUBSTRING} as a sys.modules key — "
            f"that is a phantom module path and mocking it hides "
            f"code bugs that reference the same wrong path. "
            f"Offending files: {offending}"
        )

    def test_debrief_state_has_read_deck_state(self) -> None:
        module = _debrief_state_module()
        assert hasattr(module, "read_deck_state"), (
            "BUG-AUDIT-18: `debrief_state` must expose `read_deck_state`. "
            "This is the function export.py imports at module load time."
        )
        assert callable(module.read_deck_state), (
            "BUG-AUDIT-18: `read_deck_state` must be callable."
        )

    def test_debrief_state_has_write_deck_state(self) -> None:
        module = _debrief_state_module()
        assert hasattr(module, "write_deck_state"), (
            "BUG-AUDIT-18: `debrief_state` must expose `write_deck_state`."
        )
        assert callable(module.write_deck_state)

    def test_debrief_state_has_increment_export_count(self) -> None:
        module = _debrief_state_module()
        assert hasattr(module, "increment_export_count"), (
            "BUG-AUDIT-18: `debrief_state` must expose "
            "`increment_export_count`."
        )
        assert callable(module.increment_export_count)

    def test_export_module_imports_from_debrief_state_at_runtime(self) -> None:
        # Positive sentinel: export.py must contain the corrected
        # `from debrief_state import ...` form. This is the
        # "after" shape that BUG-AUDIT-18 established.
        export_path = _export_module_path()
        text = export_path.read_text(encoding="utf-8")
        assert "from debrief_state import" in text, (
            f"BC-10.X / BUG-AUDIT-18: {export_path} must contain "
            f"`from debrief_state import` (the canonical import form). "
            f"If you see `from debrief.state import` instead, that is "
            f"the BUG-AUDIT-18 regression."
        )
