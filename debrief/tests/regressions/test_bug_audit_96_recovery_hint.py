# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-96.

Bug: `bin/debrief`'s `--rebuild-env` branch and env-creation cleanup branch
(a) suppressed conda's stderr via `2>/dev/null`, hiding the real failure
mode from users, and (b) printed a stale recovery hint instructing the user
to run `conda env remove -n debrief --force`. The `--force` flag was removed
from `conda env remove` between conda 22.x and 25.x; on `conda 25.7.0` the
command exits non-zero with `unrecognized arguments: --force`. Users hit a
recovery dead end.

Fix (BC-1.20): three coordinated changes per BUG-AUDIT-96:
  - drop `2>/dev/null` on `conda env remove` so conda's stderr reaches the
    user;
  - verify env absence post-remove via `conda env list | grep -qx debrief`
    rather than trusting the remove's exit code (conda's exit semantics
    differ across versions);
  - replace the `--force` recovery hint with `rm -rf "$(conda info
    --base)/envs/debrief"` — a filesystem operation that does not depend
    on conda CLI flag stability.

Tests below are structural assertions over `bin/debrief`'s source. The
end-to-end recovery flow cannot be exercised in unit-test CI because it
requires a real conda env to remove; structural assertions are sufficient
to catch any regression to the pre-fix state.

The tests must pass from both the workspace and the delivered repo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers (same shape as test_bug_audit_1_bootstrap.py and
# test_bug_audit_95_subcommand_preflight.py).
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _bin_debrief_path() -> Path:
    workspace_candidate = _PROJECT_ROOT / "src" / "unit_1" / "bin" / "debrief"
    delivered_candidate = _PROJECT_ROOT / "bin" / "debrief"
    if workspace_candidate.exists():
        return workspace_candidate
    if delivered_candidate.exists():
        return delivered_candidate
    raise FileNotFoundError(
        f"Could not find bin/debrief at {workspace_candidate} or {delivered_candidate}"
    )


@pytest.fixture(scope="module")
def bin_debrief_text() -> str:
    return _bin_debrief_path().read_text()


@pytest.fixture(scope="module")
def bin_debrief_lines(bin_debrief_text: str) -> list[str]:
    return bin_debrief_text.splitlines()


# ---------------------------------------------------------------------------
# Static checks: no `--force` in any conda env remove invocation, anywhere.
# ---------------------------------------------------------------------------


class TestBugAudit96NoForceFlag:
    """The `--force` recovery hint has been retired from bin/debrief."""

    def test_no_conda_env_remove_force_anywhere(self, bin_debrief_text: str) -> None:
        # The script must contain no `conda env remove ... --force` substring.
        # We check the substring rather than the regex from BC-1.20 because
        # the prose form is the user-facing failure mode.
        assert "conda env remove -n debrief --force" not in bin_debrief_text, (
            "BUG-AUDIT-96 regression: bin/debrief still contains the legacy "
            "`conda env remove -n debrief --force` recovery hint. Modern conda "
            "(25.x+) rejects --force with `unrecognized arguments: --force`."
        )

    def test_no_force_flag_in_any_env_remove_invocation(self, bin_debrief_text: str) -> None:
        # BC-1.20: the script must contain no `conda env remove ... --force`
        # in any active code path. Regex per BC-1.20.
        rx = re.compile(r"conda env remove[^|;\n]*--force")
        matches = rx.findall(bin_debrief_text)
        assert not matches, (
            f"BUG-AUDIT-96 regression: found `--force` flag in conda env remove "
            f"invocation(s): {matches!r}"
        )


# ---------------------------------------------------------------------------
# Static checks: stderr is NOT suppressed on `conda env remove` lines.
# ---------------------------------------------------------------------------


class TestBugAudit96StderrNotSuppressed:
    """`conda env remove` invocations must surface their stderr."""

    def test_no_stderr_redirect_on_conda_env_remove_lines(
        self, bin_debrief_lines: list[str]
    ) -> None:
        # Any line that invokes `conda env remove` must not contain
        # `2>/dev/null` or `2>&1 >/dev/null` — those mask conda's actual
        # error output from the user.
        offenders: list[tuple[int, str]] = []
        for i, line in enumerate(bin_debrief_lines, start=1):
            if "conda env remove" not in line:
                continue
            # Allow comments that mention `conda env remove` (e.g., the
            # cleanup-branch comment that explains the design). A line is
            # a comment if its first non-whitespace char is `#`.
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if "2>/dev/null" in line or "2>&1 >/dev/null" in line or "2> /dev/null" in line:
                offenders.append((i, line.rstrip()))
        assert not offenders, (
            "BUG-AUDIT-96 regression: `conda env remove` is invoked with stderr "
            "redirected to /dev/null. BC-1.20 requires stderr to reach the user. "
            f"Offending lines: {offenders!r}"
        )


# ---------------------------------------------------------------------------
# Static checks: recovery hints reference rm -rf of the env directory.
# ---------------------------------------------------------------------------


class TestBugAudit96RecoveryHintFormat:
    """Recovery hints reference `rm -rf` of the env directory."""

    def test_recovery_hint_contains_rm_rf(self, bin_debrief_text: str) -> None:
        # BC-1.20: the recovery hint MUST contain `rm -rf` AND a path
        # expression resolving to the env directory under the active
        # conda installation. Canonical form: `rm -rf "$(conda info --base)/envs/debrief"`.
        assert "rm -rf" in bin_debrief_text, (
            "BC-1.20: recovery hint must reference `rm -rf` of the env directory."
        )
        assert "conda info --base" in bin_debrief_text, (
            "BC-1.20: recovery hint must reference `$(conda info --base)` to "
            "resolve the env directory portably."
        )
        assert "envs/debrief" in bin_debrief_text, (
            "BC-1.20: recovery hint must point to the `envs/debrief` directory."
        )

    def test_recovery_hint_appears_in_both_branches(self, bin_debrief_text: str) -> None:
        # The `rm -rf "$(conda info --base)/envs/debrief"` recovery hint
        # must appear at least twice: once in the --rebuild-env branch,
        # once in the partial-env cleanup branch. After bash escape
        # processing, both echo statements produce the same recovery line,
        # but the source text contains the escaped form.
        # We count occurrences of the env-directory path expression as a
        # proxy for recovery-hint instances.
        count = bin_debrief_text.count("envs/debrief")
        assert count >= 2, (
            f"Expected `envs/debrief` recovery path to appear ≥2 times "
            f"(rebuild-env branch + partial-env cleanup branch); found {count}."
        )


# ---------------------------------------------------------------------------
# Static checks: post-remove env-list verification is in place.
# ---------------------------------------------------------------------------


class TestBugAudit96PostCheckByListing:
    """Both branches verify env absence via `conda env list | grep -qx debrief`."""

    def test_rebuild_branch_post_checks_env_absence(
        self, bin_debrief_text: str, bin_debrief_lines: list[str]
    ) -> None:
        # Find the --rebuild-env branch (between `"${1:-}" == "--rebuild-env"`
        # and the closing `fi` that wraps it). Inside that block, after the
        # `conda env remove` line, there must be a `conda env list | ... |
        # grep -qx debrief` check that drives the failure decision.
        rebuild_idx = next(
            (
                i for i, line in enumerate(bin_debrief_lines)
                if '"${1:-}" == "--rebuild-env"' in line
            ),
            -1,
        )
        assert rebuild_idx >= 0, "--rebuild-env branch missing"

        # Look at the next ~25 lines (the entire branch body).
        branch_body = "\n".join(bin_debrief_lines[rebuild_idx : rebuild_idx + 25])
        assert "conda env remove -n debrief -y" in branch_body, (
            "Rebuild branch must invoke `conda env remove -n debrief -y`."
        )
        assert "conda env list" in branch_body, (
            "BC-1.20: rebuild branch must run a post-check `conda env list` "
            "after the remove attempt to verify env absence."
        )
        assert "grep -qx debrief" in branch_body, (
            "BC-1.20: rebuild branch's post-check must use `grep -qx debrief` "
            "for exact-name matching."
        )

    def test_cleanup_branch_post_checks_env_absence(
        self, bin_debrief_text: str
    ) -> None:
        # The env-creation cleanup branch already had a pre-check that the
        # env exists before attempting removal (BC-1.16b / BUG-AUDIT-3b).
        # BUG-AUDIT-96 adds a *post-check* that the env is gone after the
        # removal attempt. We assert the structural pattern: there is a
        # block where `conda env remove -n debrief -y` is followed by a
        # `conda env list | ... | grep -qx debrief` check.
        # We use a relaxed regex to avoid coupling to whitespace. DOTALL
        # lets `.` match newlines so the pattern can span the post-remove
        # `if conda env list | awk ... | grep -qx debrief` check.
        rx = re.compile(
            r"conda env remove -n debrief -y.*?conda env list.*?grep -qx debrief",
            re.DOTALL,
        )
        matches = rx.findall(bin_debrief_text)
        # Both branches (rebuild-env and partial-env cleanup) match this
        # pattern, so we expect at least 2 matches.
        assert len(matches) >= 2, (
            f"BC-1.20 requires both rebuild branch AND partial-env cleanup "
            f"branch to post-check env absence via `conda env list | grep -qx "
            f"debrief` after `conda env remove`. Found {len(matches)} matches."
        )


# ---------------------------------------------------------------------------
# Echo-escaping smoke test: the recovery hint, after bash interpolation,
# renders as the canonical user-facing string. This guards against shell
# escape errors in the multi-level-quoted echo statements.
# ---------------------------------------------------------------------------


class TestBugAudit96RecoveryHintRenders:
    """The escaped echo statements render as the canonical user-facing hint."""

    def test_recovery_hint_renders_correctly(self, bin_debrief_text: str) -> None:
        # The script source contains, e.g.:
        #   echo "Run \`rm -rf \"\$(conda info --base)/envs/debrief\"\` manually, then retry \`debrief --rebuild-env\`." >&2
        # After bash processes the escapes, this renders as:
        #   Run `rm -rf "$(conda info --base)/envs/debrief"` manually, then retry `debrief --rebuild-env`.
        # We assert the source contains the escaped form for both branches.
        rebuild_escaped = (
            r'Run \`rm -rf \"\$(conda info --base)/envs/debrief\"\` manually, '
            r"then retry \`debrief --rebuild-env\`."
        )
        new_escaped = (
            r'Run \`rm -rf \"\$(conda info --base)/envs/debrief\"\` manually, '
            r"then retry \`debrief new\`."
        )
        assert rebuild_escaped in bin_debrief_text, (
            "BC-1.20: --rebuild-env branch must contain the canonical "
            f"recovery-hint echo. Expected substring: {rebuild_escaped!r}"
        )
        assert new_escaped in bin_debrief_text, (
            "BC-1.20: partial-env cleanup branch must contain the canonical "
            f"recovery-hint echo. Expected substring: {new_escaped!r}"
        )
