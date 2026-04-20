# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-77.

BUG-AUDIT-77 codifies the generator output-path contract as a
canonical table in the spec (enumerating export / script / handout /
view / present output locations) and attaches a non-write invariant:
no generator module may write to ``<project_root>/speaker_script.md``
or to any other user-managed file at project root. The canonical
notes source established by BUG-AUDIT-68 / BC-11.15a must remain
strictly user-managed; generators read it via ``_load_speaker_script``
but never write it.

TEST CLASSES:

1. TestGeneratorModulesDoNotWriteSpeakerScript — AST-scans the
   generator modules (src/unit_10/export.py + src/unit_11/
   utility_skills.py, workspace layout; src/debrief/ for delivered)
   for write-expressions whose target string equals
   ``speaker_script.md``. Asserts none exist. This is the BC-11.19
   invariant that BUG-AUDIT-77 codifies as a hard contract.
2. TestSpeakerScriptIsReadOnlyCrossSource — sanity check that
   export.py does not reference the literal ``speaker_script.md``
   at all; only utility_skills.py mentions it (via
   ``_load_speaker_script`` — a pure read path).
3. TestSpecHasGeneratorOutputPathsTable — the spec's Generator
   Output Paths table is present and enumerates all five current
   generators with their output-path patterns.
4. TestSpecAndBlueprintAnchors — BUG-AUDIT-77 + REQ-GEN-PATHS-1 +
   BC-11.19 anchors are present.

Scope note on the "broader" user-managed-at-project-root list
(deck_brief.md, style_guide.md, style_config.json, deck_state.json,
debrief_state.json, ledger.jsonl, CLAUDE.md): utility_skills.py
hosts the /debrief:save / /debrief:restore / /debrief:quit skills,
which legitimately COPY and ARCHIVE these files to snapshots/ —
those are operator-class surfaces, not generators, and their
writes are governed by per-surface BCs (BC-11.9..BC-11.13). The
BUG-AUDIT-77 non-write invariant is deliberately narrow: it
protects ONLY speaker_script.md, the canonical notes source
established by BUG-AUDIT-68. A broader AST-scan would false-
positive on legitimate snapshot machinery.

All tests run unconditionally in both workspace and delivered layouts
via the sibling-discovery path pattern; zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-77 and
blueprint contract BC-11.19.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


def _generator_module_paths() -> list[Path]:
    """Return the generator module source files to scan in the current
    layout. When a new generator module is added, extend this list.

    Workspace: ``src/unit_10/export.py`` + ``src/unit_11/utility_skills.py``.
    Delivered: ``src/debrief/export.py`` + ``src/debrief/utility_skills.py``.
    """
    if _is_workspace_layout():
        return [
            _PROJECT_ROOT / "src" / "unit_10" / "export.py",
            _PROJECT_ROOT / "src" / "unit_11" / "utility_skills.py",
        ]
    return [
        _PROJECT_ROOT / "src" / "debrief" / "export.py",
        _PROJECT_ROOT / "src" / "debrief" / "utility_skills.py",
    ]


def _spec_path() -> Path:
    return _PROJECT_ROOT / "spec" / "stakeholder_spec.md"


def _blueprint_path() -> Path:
    return _PROJECT_ROOT / "blueprint" / "blueprint_contracts.md"


# ---------------------------------------------------------------------------
# AST scanner: collect write-expression targets
# ---------------------------------------------------------------------------


# Method names on pathlib.Path or file-like objects that PERFORM A WRITE.
# Reads (.read_text, .read_bytes, .exists, etc.) MUST NOT be in this set.
_WRITE_METHOD_NAMES: frozenset[str] = frozenset({
    "write_text",
    "write_bytes",
    "write",  # file-object.write or some APIs
    "save",   # e.g., fitz doc.save
})


class _WriteTargetCollector(ast.NodeVisitor):
    """Collect string literals that appear as components of write-target
    expressions.

    A "write-target expression" is either:
    * the RECEIVER of a method call from ``_WRITE_METHOD_NAMES`` (e.g.,
      ``path.write_text(...)`` — ``path`` is the target).
    * an argument to ``open(<path>, 'w'...)``.
    * an argument to ``os.rename(<src>, <dst>)`` — both positions.

    We recursively walk the target expression looking for any string
    literal and stash it. The goal is NOT to prove that a given write
    resolves to a specific filename (hard in general), but to detect
    whether any code path could even reach a write to a particular
    filename literal — which is enough for the BC-11.19 non-write
    invariant we want to enforce.
    """

    def __init__(self) -> None:
        self.string_literals_in_write_targets: list[str] = []

    def _collect_strings_under(self, node: ast.AST) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                self.string_literals_in_write_targets.append(sub.value)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        # Case 1: method call whose attribute name is a writer.
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _WRITE_METHOD_NAMES:
            # The receiver expression is func.value. Walk it for
            # string literals.
            self._collect_strings_under(func.value)

        # Case 2: open(<path>, 'w'...) / open(<path>, 'wb'...) /
        # open(<path>, 'a'...).
        if (
            isinstance(func, ast.Name)
            and func.id == "open"
            and len(node.args) >= 2
        ):
            mode_node = node.args[1]
            if (
                isinstance(mode_node, ast.Constant)
                and isinstance(mode_node.value, str)
                and any(c in mode_node.value for c in ("w", "a", "x"))
            ):
                self._collect_strings_under(node.args[0])

        # Case 3: Path(...).open('w'...) — handled by case 1 since
        # ``open`` as a method is in _WRITE_METHOD_NAMES? No — we did
        # not include "open" because it also covers reads. Handle it
        # explicitly with a mode check.
        if isinstance(func, ast.Attribute) and func.attr == "open":
            # Inspect the mode argument if present; if any write flag,
            # the receiver is a write target.
            mode_node: ast.AST | None = None
            if node.args:
                mode_node = node.args[0]
            for kw in node.keywords:
                if kw.arg == "mode":
                    mode_node = kw.value
            if (
                isinstance(mode_node, ast.Constant)
                and isinstance(mode_node.value, str)
                and any(c in mode_node.value for c in ("w", "a", "x"))
            ):
                self._collect_strings_under(func.value)

        # Case 4: os.rename(<src>, <dst>) — both positions are
        # write-target-adjacent.
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "rename"
            and isinstance(func.value, ast.Name)
            and func.value.id == "os"
        ):
            for arg in node.args[:2]:
                self._collect_strings_under(arg)

        # Case 5: shutil.copy / shutil.copy2 / shutil.copytree -
        # destination is a write target.
        if (
            isinstance(func, ast.Attribute)
            and func.attr in ("copy", "copy2", "copytree", "copyfile", "move")
            and isinstance(func.value, ast.Name)
            and func.value.id == "shutil"
        ):
            if len(node.args) >= 2:
                self._collect_strings_under(node.args[1])

        self.generic_visit(node)


def _collect_write_target_literals(source_path: Path) -> list[str]:
    """Parse ``source_path`` and return every string literal that
    participates in a write-target expression anywhere in the file.
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    collector = _WriteTargetCollector()
    collector.visit(tree)
    return collector.string_literals_in_write_targets


# ---------------------------------------------------------------------------
# Test class 1: generators do not write speaker_script.md
# ---------------------------------------------------------------------------


class TestGeneratorModulesDoNotWriteSpeakerScript:
    @pytest.mark.parametrize(
        "source_path",
        _generator_module_paths(),
        ids=lambda p: p.name,
    )
    def test_no_write_expression_targets_speaker_script_md(
        self, source_path: Path
    ) -> None:
        assert source_path.is_file(), (
            f"Generator source file missing: {source_path}"
        )
        literals = _collect_write_target_literals(source_path)
        offenders = [s for s in literals if s == "speaker_script.md"]
        assert offenders == [], (
            f"{source_path.name}: a write expression targets "
            f"'speaker_script.md'. BC-11.19 forbids this — the file is "
            f"user-managed per BC-11.15a / BUG-AUDIT-68. Offending "
            f"literals: {offenders}"
        )


# ---------------------------------------------------------------------------
# Test class 2: speaker_script.md references are read-only
# ---------------------------------------------------------------------------


class TestSpeakerScriptIsReadOnlyCrossSource:
    def test_speaker_script_literal_appears_only_in_utility_skills(
        self,
    ) -> None:
        """Cross-check: the only generator module that even mentions
        'speaker_script.md' as a string literal is utility_skills.py
        (via _load_speaker_script). export.py must not reference the
        name at all.
        """
        paths = _generator_module_paths()
        export_py = next(p for p in paths if p.name == "export.py")
        text = export_py.read_text(encoding="utf-8")
        assert "speaker_script.md" not in text, (
            f"export.py references 'speaker_script.md'. BC-11.19 keeps "
            f"the file exclusively as utility_skills.py's read-only "
            f"load target."
        )


# ---------------------------------------------------------------------------
# Test class 3: spec carries the Generator Output Paths table
# ---------------------------------------------------------------------------


class TestSpecHasGeneratorOutputPathsTable:
    def test_spec_references_generator_output_paths(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        # The exact phrase "Generator Output Paths" anchors the
        # table; future edits must keep this phrase so readers find
        # the table by search.
        assert "Generator Output Paths" in text

    @pytest.mark.parametrize(
        "generator_slug",
        ["debrief:export", "debrief:script", "debrief:handout",
         "debrief:view", "debrief:present"],
    )
    def test_spec_table_lists_generator(
        self, generator_slug: str
    ) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        # A minimal presence check — the table row naming each
        # generator must be findable. Exact match on the command name
        # is robust because the section is the only place where all
        # five are listed together.
        assert f"/{generator_slug}" in text, (
            f"Spec missing reference to /{generator_slug}"
        )

    def test_spec_table_lists_all_generator_output_patterns(
        self,
    ) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        # Each generator's output path pattern appears in the spec.
        expected_patterns = [
            "deck_v{NNN}.pdf",
            "script_v{NNN}.md",
            "handout_v{NNN}.pdf",
            "output/view.html",
            "output/presentation.html",
        ]
        for pattern in expected_patterns:
            assert pattern in text, (
                f"Spec missing output-path pattern: {pattern}"
            )


# ---------------------------------------------------------------------------
# Test class 4: spec + blueprint anchors
# ---------------------------------------------------------------------------


class TestSpecAndBlueprintAnchors:
    def test_spec_has_bug_audit_77(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "BUG-AUDIT-77" in text

    def test_spec_has_req_gen_paths_1(self) -> None:
        text = _spec_path().read_text(encoding="utf-8")
        assert "REQ-GEN-PATHS-1" in text

    def test_blueprint_has_bc_11_19(self) -> None:
        text = _blueprint_path().read_text(encoding="utf-8")
        assert "BC-11.19" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
