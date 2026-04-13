# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-5.

Bug: `bin/debrief` step 10 invoked `exec claude --plugin "$CLAUDE_PLUGIN_ROOT"`
but `--plugin` is not a valid Claude Code CLI option. The correct flag is
`--plugin-dir`, which loads plugins from a directory for the current
session (`claude --help` documents it; code.claude.com/docs/en/cli-reference.md
is authoritative). The bug only surfaced when a real end-to-end `debrief new`
invocation reached the final launch — structural tests had codified the
wrong flag and kept passing. See `spec/stakeholder_spec.md` Bug Catalog
entry BUG-AUDIT-5 and BC-1.16 step 10.

The negative sentinel in `test_bin_debrief_does_not_use_deprecated_plugin_flag`
is the key regression guard. Any future edit that reverts to the bare
`--plugin` form fails it immediately.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _bin_debrief_path() -> Path:
    workspace_candidate = _PROJECT_ROOT / "src" / "unit_1" / "bin" / "debrief"
    delivered_candidate = _PROJECT_ROOT / "bin" / "debrief"
    for candidate in (workspace_candidate, delivered_candidate):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find bin/debrief at {workspace_candidate} or {delivered_candidate}"
    )


@pytest.fixture(scope="module")
def bin_debrief_text() -> str:
    return _bin_debrief_path().read_text()


# ---------------------------------------------------------------------------
# BUG-AUDIT-5 regression tests.
# ---------------------------------------------------------------------------


class TestBugAudit5PluginDirFlag:
    """BC-1.16 step 10: `claude --plugin-dir` is the correct launch invocation."""

    def test_bin_debrief_uses_plugin_dir_flag(self, bin_debrief_text: str) -> None:
        # Positive: the full, exact invocation must appear at least once.
        assert 'exec claude --plugin-dir "$CLAUDE_PLUGIN_ROOT"' in bin_debrief_text, (
            "BC-1.16 step 10 / BUG-AUDIT-5 requires "
            "`exec claude --plugin-dir \"$CLAUDE_PLUGIN_ROOT\"` as the launch "
            "invocation in both the `new)` and bare `\"\"` arms of the step 9 "
            "subcommand dispatch."
        )

    def test_bin_debrief_does_not_use_deprecated_plugin_flag(
        self, bin_debrief_text: str
    ) -> None:
        # Negative sentinel: the bare `--plugin` flag (literal `--plugin`
        # followed by a space, NOT `--plugin-dir`) must not appear anywhere.
        # Use regex so `--plugin-dir` does not false-match. We look for
        # `--plugin` followed by a whitespace character or end-of-string,
        # which specifically excludes `--plugin-dir`, `--plugin-foo`, etc.
        #
        # This is the key regression guard: any edit that reverts to
        # `exec claude --plugin ...` will fail here immediately.
        deprecated_flag_pattern = re.compile(r"--plugin(?![-\w])")
        matches = deprecated_flag_pattern.findall(bin_debrief_text)
        assert not matches, (
            "BUG-AUDIT-5 regression: bin/debrief uses the deprecated bare "
            "`--plugin` flag. The correct Claude Code CLI flag is "
            "`--plugin-dir`. `--plugin` does not exist and produces "
            "`error: unknown option '--plugin'` at launch. See BC-1.16 step 10."
        )

    def test_plugin_dir_flag_appears_in_both_dispatch_arms(
        self, bin_debrief_text: str
    ) -> None:
        # The full launch invocation must appear exactly twice: once in the
        # `new)` arm of the step 9 dispatch, and once in the bare `"")` arm.
        # This locks the structural invariant so a future edit that only
        # fixes one arm (or adds a third) fails the test.
        count = bin_debrief_text.count('exec claude --plugin-dir "$CLAUDE_PLUGIN_ROOT"')
        assert count == 2, (
            f"BC-1.16 step 10: `exec claude --plugin-dir \"$CLAUDE_PLUGIN_ROOT\"` "
            f"must appear exactly twice in bin/debrief (once in the `new)` arm "
            f"and once in the bare `\"\"` arm of the step 9 subcommand dispatch). "
            f"Found {count} occurrences."
        )
