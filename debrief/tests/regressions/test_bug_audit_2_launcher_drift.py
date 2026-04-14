# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-2.

Bug: workspace `src/unit_3/launcher.py` had drifted from the delivered
`debrief1.0-repo/debrief/src/debrief/launcher.py` — the delivered repo had
been edited directly to add `main_new()` and an `if __name__ == "__main__"`
guard while the workspace stub stayed at its original 416 lines. The
delivered `main_new()` was also latently non-compliant with BC-3.11 because
it dispatched to subcommands without first calling `_require_json_repair()`
at entry. See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-2.

These tests assert the structural shape of `main_new()` and detect future
drift by comparing the workspace and delivered launcher byte-for-byte
whenever both paths resolve from the current layout. As with BUG-AUDIT-1,
the tests are structural rather than functional: there is no
installed `debrief` package in the workspace layout, so subprocess
execution of `python -m debrief.launcher` would be flaky.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers: locate launcher.py in either layout.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _launcher_path() -> Path:
    """Return the path to launcher.py in whichever layout we are in.

    Workspace layout (SVP source of truth): src/unit_3/launcher.py.
    Delivered repo layout: src/debrief/launcher.py at the plugin root.
    """
    workspace_candidate = _PROJECT_ROOT / "src" / "unit_3" / "launcher.py"
    delivered_candidate = _PROJECT_ROOT / "src" / "debrief" / "launcher.py"
    for candidate in (workspace_candidate, delivered_candidate):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find launcher.py at {workspace_candidate} or {delivered_candidate}"
    )


def _both_launcher_paths() -> tuple[Path, Path] | None:
    """Return (workspace_path, delivered_path) if both exist, else None.

    When running from the workspace root, the workspace launcher is at
    ``src/unit_3/launcher.py`` (relative to ``_PROJECT_ROOT``) and the
    delivered launcher is at
    ``../debrief1.0-repo/debrief/src/debrief/launcher.py``.

    When running from the delivered plugin root, the delivered launcher is
    at ``src/debrief/launcher.py`` and the workspace launcher is at
    ``../../debrief1.0/src/unit_3/launcher.py``.

    The drift-detection test relies on this helper: if neither relative
    layout yields both files (e.g., the repo was redistributed standalone),
    the test is skipped rather than failing.
    """
    workspace_from_workspace_root = _PROJECT_ROOT / "src" / "unit_3" / "launcher.py"
    delivered_from_workspace_root = (
        _PROJECT_ROOT.parent / "debrief1.0-repo" / "debrief" / "src" / "debrief" / "launcher.py"
    )
    if workspace_from_workspace_root.exists() and delivered_from_workspace_root.exists():
        return (workspace_from_workspace_root, delivered_from_workspace_root)

    delivered_from_delivered_root = _PROJECT_ROOT / "src" / "debrief" / "launcher.py"
    workspace_from_delivered_root = (
        _PROJECT_ROOT.parent.parent / "debrief1.0" / "src" / "unit_3" / "launcher.py"
    )
    if delivered_from_delivered_root.exists() and workspace_from_delivered_root.exists():
        return (workspace_from_delivered_root, delivered_from_delivered_root)

    return None


@pytest.fixture(scope="module")
def launcher_text() -> str:
    return _launcher_path().read_text()


@pytest.fixture(scope="module")
def main_new_body(launcher_text: str) -> str:
    """Return just the body of main_new() — everything from `def main_new` to
    the next top-level `def` or `if __name__` guard. Structural assertions
    that target main_new() scope their searches to this substring so they
    don't accidentally match references elsewhere in the file.
    """
    marker = "def main_new("
    idx = launcher_text.find(marker)
    assert idx != -1, "def main_new( not found — BC-3.12 requires this function to exist."
    rest = launcher_text[idx:]
    lines = rest.splitlines(keepends=True)
    body_lines = [lines[0]]
    for line in lines[1:]:
        if line.startswith("def ") or line.startswith("if __name__"):
            break
        body_lines.append(line)
    return "".join(body_lines)


@pytest.fixture(scope="module")
def main_new_ast(launcher_text: str) -> ast.FunctionDef:
    """Parse launcher.py and return the ast.FunctionDef for main_new().

    Using the AST instead of text search avoids false positives from
    references to `subcommand`, `sys.argv`, or `_require_json_repair` inside
    the function's docstring.
    """
    tree = ast.parse(launcher_text)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main_new":
            return node
    raise AssertionError("main_new() not found in launcher AST — BC-3.12 violation.")


# ---------------------------------------------------------------------------
# BUG-AUDIT-2 regression tests for main_new() and __main__ guard (BC-3.12).
# ---------------------------------------------------------------------------


class TestBugAudit2LauncherMainNewDrift:
    """BC-3.12 structural shape + BC-3.11 ordering + byte-equal drift check."""

    def test_main_new_exists_in_launcher_source(self, launcher_text: str) -> None:
        assert "def main_new(" in launcher_text, (
            "BC-3.12 requires launcher.py to define `main_new()` as the module entry point."
        )

    def test_launcher_has_main_guard(self, launcher_text: str) -> None:
        # BC-3.12: the file must end with an `if __name__ == "__main__"` block
        # that calls main_new(). Permit either single or double quotes.
        assert (
            'if __name__ == "__main__":' in launcher_text
            or "if __name__ == '__main__':" in launcher_text
        ), "BC-3.12 requires an `if __name__ == \"__main__\":` guard."
        # The guard body must call main_new() (not just any function).
        guard_idx = launcher_text.find("__name__")
        assert guard_idx != -1
        after_guard = launcher_text[guard_idx:]
        assert "main_new()" in after_guard, (
            "BC-3.12 requires the __main__ guard to call `main_new()`."
        )

    def test_main_new_dispatches_preflight_subcommand(self, main_new_body: str) -> None:
        assert 'subcommand == "preflight"' in main_new_body, (
            "BC-3.12 requires main_new() to dispatch on `subcommand == \"preflight\"`."
        )
        assert "preflight(" in main_new_body, (
            "BC-3.12 preflight arm must call `preflight(...)`."
        )

    def test_main_new_dispatches_new_subcommand(self, main_new_body: str) -> None:
        assert 'subcommand == "new"' in main_new_body, (
            "BC-3.12 requires main_new() to dispatch on `subcommand == \"new\"`."
        )
        assert "new(" in main_new_body, (
            "BC-3.12 new arm must call `new(...)`."
        )

    def test_main_new_prints_usage_for_unknown_subcommand(self, main_new_body: str) -> None:
        # BUG-AUDIT-8 added the `ensure_settings` arm to the dispatch, so
        # the usage message now lists three subcommands. We accept either
        # the legacy two-subcommand form or the current three-subcommand
        # form to avoid coupling the BUG-AUDIT-2 contract to the specific
        # subcommand list — the structural invariant is that SOME usage
        # message exists in the else arm.
        assert "Usage: python -m debrief.launcher" in main_new_body, (
            "BC-3.12 requires the else arm to print a `Usage: python -m "
            "debrief.launcher ...` message."
        )
        # Sanity: the message must list at least the two original subcommands.
        assert "new" in main_new_body and "preflight" in main_new_body, (
            "Usage message must mention `new` and `preflight` subcommands."
        )

    def test_main_new_exits_1_on_unknown_subcommand(self, main_new_body: str) -> None:
        assert "sys.exit(1)" in main_new_body, (
            "BC-3.12 requires the else arm to call `sys.exit(1)`."
        )

    def test_main_new_reads_plugin_root_from_env(self, main_new_body: str) -> None:
        assert "CLAUDE_PLUGIN_ROOT" in main_new_body, (
            "BC-3.12 requires main_new() to resolve plugin_root from CLAUDE_PLUGIN_ROOT."
        )

    def test_main_new_checks_json_repair_at_entry_bc_3_11(
        self, main_new_ast: ast.FunctionDef
    ) -> None:
        # BC-3.11: _require_json_repair() must be the FIRST executable
        # statement of main_new() — before any subcommand dispatch, argv
        # parsing, or plugin-root resolution. Using AST so the check ignores
        # docstring references to _require_json_repair, sys.argv, etc.
        body = list(main_new_ast.body)
        # Skip the docstring if present (it's an ast.Expr wrapping ast.Constant(str)).
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]
        assert body, "main_new() has no executable body."
        first_stmt = body[0]
        # First executable statement must be an expression-statement calling
        # _require_json_repair().
        assert isinstance(first_stmt, ast.Expr), (
            f"BC-3.11: first statement of main_new() must be a call to "
            f"_require_json_repair(); got {type(first_stmt).__name__}."
        )
        call = first_stmt.value
        assert isinstance(call, ast.Call), (
            "BC-3.11: first statement of main_new() must be a call expression."
        )
        assert isinstance(call.func, ast.Name) and call.func.id == "_require_json_repair", (
            f"BC-3.11: first statement of main_new() must call "
            f"`_require_json_repair()`; got "
            f"{ast.dump(call.func) if not isinstance(call.func, ast.Name) else call.func.id}."
        )
        assert call.args == [] and call.keywords == [], (
            "BC-3.11: `_require_json_repair()` must be called with no arguments."
        )

    def test_workspace_and_delivered_launcher_are_byte_equal(self) -> None:
        paths = _both_launcher_paths()
        if paths is None:
            pytest.skip(
                "Both workspace and delivered launcher.py paths could not be "
                "resolved from the current layout — drift detection requires "
                "access to both repos."
            )
        workspace_path, delivered_path = paths
        workspace_bytes = workspace_path.read_bytes()
        delivered_bytes = delivered_path.read_bytes()
        assert workspace_bytes == delivered_bytes, (
            f"BUG-AUDIT-2 regression: {workspace_path} and {delivered_path} "
            f"are not byte-equal. One repo has drifted. Re-sync from the "
            f"workspace source of truth."
        )
