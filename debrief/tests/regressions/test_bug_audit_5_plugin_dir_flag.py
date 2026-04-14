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
    """BC-1.16 step 10: `claude` (no flags) is the launch invocation.

    Inverted from the original BUG-AUDIT-5 form: BUG-AUDIT-8 retired the
    `--plugin-dir` load path because it skipped marketplace registration
    and produced bare-named skills that collided with built-in slash
    commands. The launch is now plain `exec claude`; project-scoped
    `.claude/settings.json` does the discovery.
    """

    def test_bin_debrief_uses_no_plugin_flag(self, bin_debrief_text: str) -> None:
        # Positive: bare `exec claude` (no flags) must appear at least once
        # in the dispatch. Match the form on its own line.
        assert re.search(r"\bexec claude\s*(?:\n|$)", bin_debrief_text, re.MULTILINE), (
            "BC-1.16 step 10 / BUG-AUDIT-8 requires plain `exec claude` "
            "(no flags) as the launch invocation."
        )

    def test_bin_debrief_does_not_use_deprecated_plugin_flag(
        self, bin_debrief_text: str
    ) -> None:
        # Negative sentinel preserved from the original BUG-AUDIT-5 fix:
        # the bare `--plugin` flag (literal `--plugin` followed by a
        # non-word character or EOL, NOT `--plugin-dir`) must not appear
        # anywhere. Catches any edit that reverts to `exec claude --plugin ...`.
        deprecated_flag_pattern = re.compile(r"--plugin(?![-\w])")
        matches = deprecated_flag_pattern.findall(bin_debrief_text)
        assert not matches, (
            "BUG-AUDIT-5 regression: bin/debrief uses the deprecated bare "
            "`--plugin` flag. `--plugin` does not exist as a Claude Code CLI "
            "option and produces `error: unknown option '--plugin'` at launch."
        )

    def test_bin_debrief_does_not_use_plugin_dir_flag(
        self, bin_debrief_text: str
    ) -> None:
        # BUG-AUDIT-8 negative sentinel: the `--plugin-dir` flag was used
        # by BUG-AUDIT-5 but retired by BUG-AUDIT-8 because it skipped
        # marketplace registration and produced bare-named skills. The
        # current architecture uses project-scoped `.claude/settings.json`
        # for discovery, so `--plugin-dir` MUST NOT appear. Any edit that
        # reverts to `exec claude --plugin-dir ...` fails here.
        assert "--plugin-dir" not in bin_debrief_text, (
            "BUG-AUDIT-8 regression: bin/debrief uses `--plugin-dir`. That "
            "load path was retired because it skips marketplace registration "
            "and produces bare-named skills that collide with built-in slash "
            "commands. The current architecture uses project-scoped "
            "`.claude/settings.json` (BC-3.13). See BUG-AUDIT-8."
        )

    def test_exec_claude_appears_in_both_dispatch_arms(
        self, bin_debrief_text: str
    ) -> None:
        # The plain `exec claude` invocation must appear exactly twice: once
        # in the `new)` arm and once in the bare `""` arm of step 9.
        # Use regex on its own line to avoid matching `exec claude` inside
        # comments or strings.
        matches = re.findall(r"^\s*exec claude\s*$", bin_debrief_text, re.MULTILINE)
        assert len(matches) == 2, (
            f"BC-1.16 step 10: bare `exec claude` must appear exactly twice "
            f"in bin/debrief (once in the `new)` arm and once in the bare "
            f"`\"\"` arm of the step 9 subcommand dispatch). Found {len(matches)} "
            f"occurrences."
        )
