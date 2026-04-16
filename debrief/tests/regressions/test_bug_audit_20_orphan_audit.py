# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-20 — SIMPLIFIED by BUG-AUDIT-31.

BUG-AUDIT-31 deleted all functions from routing.py (the entire routing
loop was dead at runtime). This gutted the BUG-AUDIT-20 regression
tests as follows:

- **Leg A** (G3.3 integration tests): DELETED. Tests exercised
  ``merge_approval_payload`` dispatch inside ``main_update_state``,
  which no longer exists.
- **Pattern 1** (gate-dispatch sentinel): DELETED. Walked routing.py's
  AST for gate-id comparisons inside ``main_update_state``; both are
  gone.
- **Pattern 2** (phantom-import sentinel): KEPT. Walks src/ for
  ``from debrief.X`` and ``import debrief.X`` imports and asserts
  each X resolves to a real module. Independent of routing.py.
- **Pattern 3** (BC-named-orphan sentinel): SIMPLIFIED. Routing.py
  entries removed from ``_BC_NAMED_FUNCTIONS``. Only launcher.py
  entries remain (``create_project_structure``,
  ``ensure_project_settings``, ``ensure_project``).

See spec/stakeholder_spec.md Bug Catalog entries BUG-AUDIT-20 and
BUG-AUDIT-31.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers — resolve both layouts from either side; no skipping.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_4").is_dir()


def _src_python_files() -> list[Path]:
    if _is_workspace_layout():
        src_root = _PROJECT_ROOT / "src"
    else:
        src_root = _PROJECT_ROOT / "src" / "debrief"
    return [
        p
        for p in src_root.rglob("*.py")
        if "__pycache__" not in p.parts and not p.name.startswith("__")
    ]


def _canonical_debrief_module_names() -> set[str]:
    if _is_workspace_layout():
        src_root = _PROJECT_ROOT / "src"
        names: set[str] = set()
        for unit_dir in src_root.iterdir():
            if unit_dir.is_dir() and unit_dir.name.startswith("unit_"):
                for py in unit_dir.glob("*.py"):
                    if not py.name.startswith("__"):
                        names.add(py.stem)
        return names
    else:
        debrief_pkg = _PROJECT_ROOT / "src" / "debrief"
        return {
            py.stem
            for py in debrief_pkg.glob("*.py")
            if not py.name.startswith("__")
        }


# ===========================================================================
# Pattern 2 — phantom-import sentinel (unchanged from BUG-AUDIT-20).
# ===========================================================================


class TestBugAudit20PhantomImportSentinel:
    """BC-4.20 / Pattern 2 — every `from debrief.X import ...` and
    `import debrief.X` in src/ must reference a real X module.
    """

    def test_no_src_file_imports_non_existent_debrief_submodule(
        self,
    ) -> None:
        from_pattern = re.compile(
            r"^\s*from\s+debrief\.([a-zA-Z_][a-zA-Z0-9_]*)",
            re.MULTILINE,
        )
        import_pattern = re.compile(
            r"^\s*import\s+debrief\.([a-zA-Z_][a-zA-Z0-9_]*)",
            re.MULTILINE,
        )

        canonical = _canonical_debrief_module_names()
        offending: list[str] = []
        for py_file in _src_python_files():
            text = py_file.read_text(encoding="utf-8")
            for match in from_pattern.finditer(text):
                sub = match.group(1)
                if sub not in canonical:
                    offending.append(
                        f"{py_file}: `from debrief.{sub}` — not a real "
                        f"module"
                    )
            for match in import_pattern.finditer(text):
                sub = match.group(1)
                if sub not in canonical:
                    offending.append(
                        f"{py_file}: `import debrief.{sub}` — not a real "
                        f"module"
                    )

        assert not offending, (
            f"BC-4.20 / BUG-AUDIT-20: phantom imports found:\n"
            + "\n".join(offending)
        )

    def test_canonical_module_set_is_non_empty(self) -> None:
        canonical = _canonical_debrief_module_names()
        assert len(canonical) >= 5, (
            f"BC-4.20: canonical module auto-discovery returned only "
            f"{len(canonical)} modules. Expected ≥5. "
            f"Discovered: {canonical!r}"
        )
        assert "debrief_state" in canonical


# ===========================================================================
# Pattern 3 — BC-named orphan sentinel (simplified by BUG-AUDIT-31).
# ===========================================================================

_BC_NAMED_FUNCTIONS = {
    "BC-3.9": "create_project_structure",
    "BC-3.13": "ensure_project_settings",
    "BC-3.14": "ensure_project",
    # BUG-AUDIT-31: all routing.py entries removed (functions deleted).
}

_ORPHAN_WHITELIST: dict[str, str] = {}


def _function_has_production_caller(func_name: str) -> tuple[bool, list[str]]:
    call_pattern = re.compile(rf"\b{re.escape(func_name)}\s*\(")
    def_pattern = re.compile(rf"^\s*def\s+{re.escape(func_name)}\s*\(")

    caller_files: list[str] = []
    total_call_sites = 0

    for py_file in _src_python_files():
        text = py_file.read_text(encoding="utf-8")
        file_has_caller = False
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if def_pattern.match(line):
                continue
            if call_pattern.search(line):
                total_call_sites += 1
                file_has_caller = True
        if file_has_caller:
            caller_files.append(str(py_file))

    return (total_call_sites > 0, caller_files)


class TestBugAudit20BcNamedOrphanSentinel:
    """BC-4.20 / Pattern 3 — simplified to launcher.py BCs only."""

    def test_bc_named_functions_have_production_callers(self) -> None:
        orphans: list[str] = []
        for bc_id, func_name in _BC_NAMED_FUNCTIONS.items():
            if bc_id in _ORPHAN_WHITELIST:
                continue
            has_caller, _ = _function_has_production_caller(func_name)
            if not has_caller:
                orphans.append(f"{bc_id}: {func_name}")
        assert not orphans, (
            f"BC-named functions without production callers:\n"
            + "\n".join(orphans)
        )

    def test_orphan_whitelist_entries_are_tracked_bugs(self) -> None:
        for bc_id, reason in _ORPHAN_WHITELIST.items():
            assert "BUG-AUDIT" in reason

    def test_no_orphan_whitelist_entries_for_already_wired_functions(
        self,
    ) -> None:
        stale: list[str] = []
        for bc_id in _ORPHAN_WHITELIST:
            func_name = _BC_NAMED_FUNCTIONS.get(bc_id)
            if func_name is None:
                continue
            has_caller, callers = _function_has_production_caller(func_name)
            if has_caller:
                stale.append(f"{bc_id}: {func_name}")
        assert not stale
