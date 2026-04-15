# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-20.

BUG-AUDIT-18 and BUG-AUDIT-19 each surfaced the same class of defect:
a function named in a Blueprint Contract was defined and unit-tested
in isolation but had zero production callers — an "orphan helper".
BUG-AUDIT-18 was the typo-import case (`debrief.state` module that
didn't exist); BUG-AUDIT-19 was the missing-dispatch case
(`promote_style_draft` never called from `main_update_state`'s
G2.1 branch because the branch itself didn't exist). Both were
hidden by unit tests that exercised the orphan directly and pytest
didn't care.

BUG-AUDIT-20 closes this structural gap with (a) one direct fix —
`merge_approval_payload` was a third orphan surfaced by the audit
pass, analogous to BUG-AUDIT-19 — and (b) three standing audit
sentinels that run on every pytest invocation and catch new
instances of the same three patterns.

TEST CLASSES:

1. TestBugAudit20LegA — integration tests for the new G3.3 APPROVE
   dispatch branch in main_update_state that calls
   merge_approval_payload per spec §24.24. Mirrors the shape of
   BUG-AUDIT-19's TestBugAudit19G21StylePromotion.

2. TestBugAudit20GateDispatchSentinel — standing check (Pattern 1):
   walks _GATE_VALID_RESPONSES and asserts every gate either has
   an explicit `if gate_id == "..."` branch in main_update_state
   OR is on a hardcoded allowlist of "generic-write-only" gates
   whose response only needs last_gate_response persistence.

3. TestBugAudit20PhantomImportSentinel — standing check (Pattern 2):
   walks src/ for `from debrief.X` and `import debrief.X` imports,
   asserts each X resolves to a real module in the canonical set
   auto-discovered from the filesystem. Extends BUG-AUDIT-18's
   specific `debrief.state` sentinel to the full `debrief.*`
   namespace.

4. TestBugAudit20BcNamedOrphanSentinel — standing check (Pattern 3):
   for each function named in a Blueprint Contract (hardcoded map),
   asserts at least one production call site exists in src/.
   Temporary whitelist for `consume_gate_data` (deferred to
   BUG-AUDIT-21 because its fix requires non-trivial spec work on
   the action→expected_gate_id mapping).

All tests run unconditionally in both workspace and delivered
layouts via the sibling-discovery path pattern; zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-20.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Path helpers — resolve both layouts from either side; no skipping.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_4").is_dir()


def _routing_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_4"
    return _PROJECT_ROOT / "src" / "debrief"


def _debrief_state_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_2"
    return _PROJECT_ROOT / "src" / "debrief"


def _routing_source_path() -> Path:
    return _routing_module_dir() / "routing.py"


def _src_python_files() -> list[Path]:
    """All production .py files under the CURRENT layout's src tree.

    Workspace: src/unit_*/*.py (excludes __pycache__).
    Delivered: src/debrief/*.py.
    """
    if _is_workspace_layout():
        src_root = _PROJECT_ROOT / "src"
    else:
        src_root = _PROJECT_ROOT / "src" / "debrief"
    return [
        p
        for p in src_root.rglob("*.py")
        if "__pycache__" not in p.parts and not p.name.startswith("__")
    ]


# Prep sys.path so `import routing` / `import debrief_state` work in
# either layout.
for _dir in (_debrief_state_module_dir(), _routing_module_dir()):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import routing  # noqa: E402


# ---------------------------------------------------------------------------
# Leg A synthetic project fixture helpers.
# ---------------------------------------------------------------------------


def _minimal_deck_state_with_draft_slide(slug: str) -> dict:
    return {
        "project_name": "bug_audit_20_test",
        "created_at": "2026-04-15T10:00:00Z",
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": [
            {
                "slug": slug,
                "title": "Draft Title",
                "status": "draft",
                "backup": False,
                "content_summary": "draft summary",
                "visual_approach": "draft approach",
                "design_choices": "draft choices",
                "forks_not_taken": None,
                "user_recommendations": None,
                "qa_passed": False,
                "accepted_violations": [],
                "last_modified": "2026-04-15T10:00:00Z",
                "group_id": None,
                "user_assets": [],
                "has_math": False,
            }
        ],
        "presentations": [],
    }


def _minimal_debrief_state(slug: str) -> dict:
    return {
        "phase": "production",
        "sub_phase": "production/slide_review",
        "active_agent": "consultant",
        "archetype": "lab_meeting",
        "current_group_id": None,
        "current_slide_slug": slug,
        "pending_gate": "G3.3_slide_review",
        "last_gate_response": None,
        "red_green_iteration": 0,
        "red_green_started_at": None,
        "group_slide_index": 0,
        "group_slide_count": 0,
        "backup_mode": False,
        "completed_groups": [],
        "pre_view_state": None,
        "view_deferred": False,
        "reference_provided": False,
        "papers_provided": False,
        "closing_slide_pending": False,
        "state_hash": "x" * 64,
        "session_started_at": "2026-04-15T10:00:00Z",
    }


def _valid_approval_payload(slug: str) -> dict:
    return {
        "slug": slug,
        "title": "Approved Title",
        "content_summary": "approved summary",
        "visual_approach": "approved approach",
        "design_choices": "approved choices",
    }


def _setup_project_for_g33(tmp_path: Path, slug: str = "test_slide") -> Path:
    project = tmp_path / "project"
    (project / ".debrief").mkdir(parents=True)
    (project / "deck_state.json").write_text(
        json.dumps(_minimal_deck_state_with_draft_slide(slug)),
        encoding="utf-8",
    )
    (project / "debrief_state.json").write_text(
        json.dumps(_minimal_debrief_state(slug)),
        encoding="utf-8",
    )
    (project / ".debrief" / f"approval_{slug}.json").write_text(
        json.dumps(_valid_approval_payload(slug)),
        encoding="utf-8",
    )
    return project


# ---------------------------------------------------------------------------
# Leg A — merge_approval_payload integration tests (BC-4.2 / BUG-AUDIT-20).
# ---------------------------------------------------------------------------


class TestBugAudit20LegA:
    """BC-4.2 / BUG-AUDIT-20 — main_update_state must dispatch G3.3
    APPROVE to merge_approval_payload. Prior to BUG-AUDIT-20 this
    branch was missing; the function was defined but had zero callers.
    """

    def test_g33_approve_merges_and_deletes_approval_file(
        self, tmp_path: Path
    ) -> None:
        project = _setup_project_for_g33(tmp_path)
        routing.main_update_state(
            gate_id="G3.3_slide_review",
            response="APPROVE",
            project_root=project,
        )

        deck = json.loads((project / "deck_state.json").read_text())
        slide = deck["slides"][0]
        assert slide["title"] == "Approved Title", (
            "BC-4.2 / BUG-AUDIT-20: slide.title must be merged from "
            "the approval payload on G3.3 APPROVE."
        )
        assert slide["content_summary"] == "approved summary"
        assert slide["visual_approach"] == "approved approach"
        assert slide["design_choices"] == "approved choices"
        assert slide["status"] == "approved", (
            "BC-4.2: slide.status must become 'approved' after merge."
        )
        assert not (project / ".debrief" / "approval_test_slide.json").exists(), (
            "BC-4.2: approval_<slug>.json must be unlinked after merge."
        )
        dbf = json.loads((project / "debrief_state.json").read_text())
        assert dbf["last_gate_response"] == "APPROVE", (
            "BC-4.2: debrief_state.last_gate_response must be persisted."
        )

    def test_g33_revise_does_not_merge(self, tmp_path: Path) -> None:
        # Negative sentinel: REVISE path must NOT merge the approval
        # payload. The slide record stays in draft state and the
        # approval file remains on disk for the next iteration.
        project = _setup_project_for_g33(tmp_path)
        routing.main_update_state(
            gate_id="G3.3_slide_review",
            response="REVISE",
            project_root=project,
        )

        deck = json.loads((project / "deck_state.json").read_text())
        slide = deck["slides"][0]
        assert slide["title"] == "Draft Title", (
            "BC-4.2: REVISE must NOT merge the approval payload."
        )
        assert slide["status"] == "draft", (
            "BC-4.2: REVISE must leave slide.status unchanged."
        )
        assert (project / ".debrief" / "approval_test_slide.json").exists(), (
            "BC-4.2: REVISE must leave approval_<slug>.json intact so "
            "the next iteration can use it."
        )

    def test_g33_discard_does_not_merge(self, tmp_path: Path) -> None:
        # Same negative sentinel for DISCARD.
        project = _setup_project_for_g33(tmp_path)
        routing.main_update_state(
            gate_id="G3.3_slide_review",
            response="DISCARD",
            project_root=project,
        )

        deck = json.loads((project / "deck_state.json").read_text())
        slide = deck["slides"][0]
        assert slide["status"] == "draft", (
            "BC-4.2: DISCARD must not change slide.status via "
            "main_update_state. (Separate logic may handle the "
            "discard transition elsewhere.)"
        )

    def test_g33_approve_with_missing_slug_exits_code_4(
        self, tmp_path: Path
    ) -> None:
        # State corruption case: if current_slide_slug is None when
        # G3.3 APPROVE fires, main_update_state must exit code 4 per
        # the BC-4.2 amendment.
        project = _setup_project_for_g33(tmp_path)
        # Clear the slug in debrief_state.
        dbf = json.loads((project / "debrief_state.json").read_text())
        dbf["current_slide_slug"] = None
        (project / "debrief_state.json").write_text(
            json.dumps(dbf), encoding="utf-8"
        )

        with pytest.raises(SystemExit) as exc_info:
            routing.main_update_state(
                gate_id="G3.3_slide_review",
                response="APPROVE",
                project_root=project,
            )
        assert exc_info.value.code == 4

    def test_merge_approval_payload_called_from_main_update_state(
        self, tmp_path: Path
    ) -> None:
        # Integration sentinel — same pattern as BUG-AUDIT-19's
        # test_promote_style_draft_is_called_from_main_update_state.
        # Pins the direct call chain so a future maintainer cannot
        # orphan the function again.
        project = _setup_project_for_g33(tmp_path)
        call_count = 0
        original = routing.merge_approval_payload

        def _recording(slug: str, prj: Path) -> None:
            nonlocal call_count
            call_count += 1
            original(slug, prj)

        with patch.object(routing, "merge_approval_payload", _recording):
            routing.main_update_state(
                gate_id="G3.3_slide_review",
                response="APPROVE",
                project_root=project,
            )

        assert call_count == 1, (
            f"BC-4.2 / BUG-AUDIT-20: merge_approval_payload must be "
            f"called exactly once from main_update_state on G3.3 APPROVE. "
            f"Got {call_count} calls."
        )


# ---------------------------------------------------------------------------
# Pattern 1 — Gate dispatch sentinel (BC-4.20).
# ---------------------------------------------------------------------------


# Gates whose response needs ONLY last_gate_response persistence —
# no file promotion, no subprocess, no payload merge, no state-field
# mutation beyond last_gate_response. Per the Phase 1 audit, these 13
# gates legitimately use the generic writer.
_GENERIC_WRITE_ONLY_GATES = frozenset({
    "G1.1_greeting",
    "G1.2_brief_review",
    "G1.4_style_analysis",
    "G2.2_lock_failed",
    "G3.1_group_manifest",
    "G3.2a_oscillation_review",
    "G3.4_group_review",
    "G3.5_more_slides",
    "G3.6_deck_ending",
    "G4.1_export_options",
    "G4.2_backup_decision",
    "G4.3_export_confirm",
})


def _extract_gates_handled_in_main_update_state() -> set[str]:
    """Parse routing.py via AST and return the set of gate_id string
    literals compared against `gate_id` inside main_update_state."""
    source = _routing_source_path().read_text(encoding="utf-8")
    tree = ast.parse(source)

    handled: set[str] = set()
    for top in ast.walk(tree):
        if not (
            isinstance(top, ast.FunctionDef)
            and top.name == "main_update_state"
        ):
            continue
        for sub in ast.walk(top):
            if isinstance(sub, ast.Compare):
                # gate_id == "<literal>" or gate_id in ("<literal>", ...)
                left = sub.left
                if not (isinstance(left, ast.Name) and left.id == "gate_id"):
                    continue
                for comparator in sub.comparators:
                    if isinstance(comparator, ast.Constant) and isinstance(
                        comparator.value, str
                    ):
                        handled.add(comparator.value)
                    elif isinstance(comparator, (ast.Tuple, ast.List)):
                        for elt in comparator.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                handled.add(elt.value)
    return handled


class TestBugAudit20GateDispatchSentinel:
    """BC-4.20 / Pattern 1 — every gate in _GATE_VALID_RESPONSES must
    have either an explicit dispatch branch in main_update_state or
    be on the _GENERIC_WRITE_ONLY_GATES allowlist.
    """

    def test_every_gate_has_dispatch_or_is_allowlisted(self) -> None:
        all_gates = set(routing._GATE_VALID_RESPONSES.keys())
        handled = _extract_gates_handled_in_main_update_state()
        unaccounted: list[str] = []
        for gate in sorted(all_gates):
            if gate in handled:
                continue
            if gate in _GENERIC_WRITE_ONLY_GATES:
                continue
            unaccounted.append(gate)

        assert not unaccounted, (
            f"BC-4.20 / BUG-AUDIT-20: every gate in _GATE_VALID_RESPONSES "
            f"must either have an explicit dispatch branch in "
            f"main_update_state or be on the _GENERIC_WRITE_ONLY_GATES "
            f"allowlist in this test file. Unaccounted gates: "
            f"{unaccounted!r}. If a new gate was added, decide whether "
            f"it needs special handling and either add a dispatch branch "
            f"or extend the allowlist."
        )

    def test_allowlist_entries_are_all_real_gates(self) -> None:
        all_gates = set(routing._GATE_VALID_RESPONSES.keys())
        stale = _GENERIC_WRITE_ONLY_GATES - all_gates
        assert not stale, (
            f"BC-4.20 / BUG-AUDIT-20: _GENERIC_WRITE_ONLY_GATES contains "
            f"entries that are NOT in _GATE_VALID_RESPONSES. These are "
            f"stale allowlist entries and should be removed: {stale!r}"
        )


# ---------------------------------------------------------------------------
# Pattern 2 — Phantom `debrief.*` import sentinel (BC-4.20).
# ---------------------------------------------------------------------------


def _canonical_debrief_module_names() -> set[str]:
    """Auto-discover the set of real Python modules that legitimately
    live under the `debrief` package or the flat debrief namespace.

    Workspace: walks src/unit_*/*.py and collects filename stems.
    Delivered: walks src/debrief/*.py and collects filename stems.
    Both produce a set of strings like {'debrief_state', 'routing',
    'style_engine', ...}.
    """
    names: set[str] = set()
    for py_file in _src_python_files():
        if py_file.name.startswith("__"):
            continue
        names.add(py_file.stem)
    return names


class TestBugAudit20PhantomImportSentinel:
    """BC-4.20 / Pattern 2 — every `from debrief.X import ...` and
    `import debrief.X` in src/ must reference a real X module. Extends
    BUG-AUDIT-18's specific `debrief.state` sentinel to the full
    `debrief.*` namespace.
    """

    def test_no_src_file_imports_non_existent_debrief_submodule(
        self,
    ) -> None:
        # Find every `from debrief.X import ...` and `import debrief.X`
        # occurrence in src/. Use a regex that matches the import-
        # statement forms specifically; explanatory comments that
        # mention phantom names (like the BUG-AUDIT-18 rationale) are
        # not flagged because they don't start with `from` or `import`.
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
            f"BC-4.20 / BUG-AUDIT-20: `from debrief.X` and `import "
            f"debrief.X` imports in src/ must reference real modules. "
            f"Phantom imports found:\n" + "\n".join(offending)
        )

    def test_canonical_module_set_is_non_empty(self) -> None:
        # Sanity: the auto-discovery must find at least several
        # modules. A silent zero would make the phantom-import test
        # pass vacuously.
        canonical = _canonical_debrief_module_names()
        assert len(canonical) >= 5, (
            f"BC-4.20 / BUG-AUDIT-20: canonical module auto-discovery "
            f"returned only {len(canonical)} modules. Expected ≥5. "
            f"Discovered: {canonical!r}"
        )
        # Spot-check that well-known modules are present.
        for required in ("debrief_state", "routing"):
            assert required in canonical, (
                f"BC-4.20: expected canonical module {required!r} not "
                f"found in auto-discovery. Full set: {canonical!r}"
            )


# ---------------------------------------------------------------------------
# Pattern 3 — BC-named orphan sentinel (BC-4.20).
# ---------------------------------------------------------------------------


# Map of Blueprint Contract ID → function name the contract names as
# something that MUST be called from production code. Keep this list
# focused on functions where a BC explicitly asserts a call site;
# don't add every helper that happens to be named in any BC.
_BC_NAMED_FUNCTIONS = {
    "BC-3.9": "create_project_structure",
    "BC-3.13": "ensure_project_settings",
    "BC-3.14": "ensure_project",
    "BC-4.1": "resolve_action",
    "BC-4.3": "check_g3_2_machine_gate",
    "BC-4.5": "validate_gate_response",
    "BC-4.6": "promote_style_draft",
    "BC-4.7": "consume_gate_data",
    "BC-4.7c": "propose_presentation_folder_name",
    "BC-4.21": "merge_approval_payload",
}


# Whitelist for functions that are intentionally orphaned pending a
# tracked BUG-AUDIT. Each entry MUST reference a BUG-AUDIT number.
_ORPHAN_WHITELIST = {
    "BC-4.7": (
        "consume_gate_data — pending cross-cycle wiring in main_prepare. "
        "See BUG-AUDIT-21 (deferred from BUG-AUDIT-20 for scope control)."
    ),
}


def _function_has_production_caller(func_name: str) -> tuple[bool, list[str]]:
    """Return (has_caller, list_of_caller_files) for func_name.

    A "production call site" is any occurrence of `<func_name>(` in a
    .py file under src/ that is NOT the function's own `def` line and
    NOT inside a comment. Callers can live in the same file as the
    definition (the common case for intra-module helpers like
    `merge_approval_payload` called from `main_update_state` in
    routing.py) OR in a different file entirely.

    Implementation: walk every line of every src file. For each line,
    ignore comment lines (``#`` as the first non-whitespace character).
    For each non-comment line, check for ``<func_name>(`` — if present
    AND the line is not a ``def`` line, it counts as a call site.
    """
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
                continue  # skip blank and comment lines
            if def_pattern.match(line):
                continue  # definition line — not a call
            if call_pattern.search(line):
                total_call_sites += 1
                file_has_caller = True
        if file_has_caller:
            caller_files.append(str(py_file))

    return (total_call_sites > 0, caller_files)


class TestBugAudit20BcNamedOrphanSentinel:
    """BC-4.20 / Pattern 3 — every BC-named function must have at
    least one production call site outside its defining file, OR be
    on the _ORPHAN_WHITELIST with a tracking BUG-AUDIT reference.
    """

    def test_bc_named_functions_have_production_callers(self) -> None:
        orphans: list[str] = []
        for bc_id, func_name in _BC_NAMED_FUNCTIONS.items():
            if bc_id in _ORPHAN_WHITELIST:
                continue  # handled by the whitelist check below
            has_caller, _ = _function_has_production_caller(func_name)
            if not has_caller:
                orphans.append(f"{bc_id}: {func_name}")
        assert not orphans, (
            f"BC-4.20 / BUG-AUDIT-20: BC-named functions without "
            f"production callers (orphan pattern — BUG-AUDIT-18 / "
            f"-19 / -20 root cause). These functions are defined and "
            f"may have unit tests, but no production code invokes "
            f"them:\n" + "\n".join(orphans) + "\n\n"
            f"Fix: add a dispatch branch (or equivalent call site) "
            f"in the appropriate higher-level entry point, OR add "
            f"the BC to _ORPHAN_WHITELIST with a tracking BUG-AUDIT "
            f"number if the fix is intentionally deferred."
        )

    def test_orphan_whitelist_entries_are_tracked_bugs(self) -> None:
        # Every whitelist entry must reference a BUG-AUDIT number so
        # no function is silently whitelisted.
        for bc_id, reason in _ORPHAN_WHITELIST.items():
            assert "BUG-AUDIT" in reason, (
                f"BC-4.20 / BUG-AUDIT-20: whitelist entry for {bc_id!r} "
                f"must reference a tracking BUG-AUDIT number. Got: "
                f"{reason!r}"
            )

    def test_no_orphan_whitelist_entries_for_already_wired_functions(
        self,
    ) -> None:
        # Negative sentinel: if a function was added to the whitelist
        # but has since been wired up, the whitelist entry is stale
        # and must be removed. This prevents the whitelist from
        # accumulating dead entries that mask new orphans.
        stale: list[str] = []
        for bc_id in _ORPHAN_WHITELIST:
            func_name = _BC_NAMED_FUNCTIONS.get(bc_id)
            if func_name is None:
                continue
            has_caller, callers = _function_has_production_caller(func_name)
            if has_caller:
                stale.append(
                    f"{bc_id}: {func_name} — now has callers in "
                    f"{[Path(c).name for c in callers]}. Remove from "
                    f"_ORPHAN_WHITELIST."
                )
        assert not stale, (
            f"BC-4.20 / BUG-AUDIT-20: _ORPHAN_WHITELIST contains stale "
            f"entries for functions that are now wired up. Remove them "
            f"so new orphans can't hide:\n" + "\n".join(stale)
        )
