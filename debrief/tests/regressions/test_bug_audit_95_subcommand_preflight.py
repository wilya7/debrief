# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-95.

Bug: `bin/debrief`'s post-activation smoke test (spec §24.4 step 5.5) ran
before subcommand dispatch (step 9). A user who forgot the `new` subcommand
got the §9.3.1 env-corruption error and the `debrief --rebuild-env` recovery
hint (a 5–15 minute env rebuild) instead of the spec'd "Run 'debrief new' to
create one." pointer. The misrouting fired any time the env was in a
non-pristine state — for example, after BUG-AUDIT-93 added `anthropic` to
`environment.yml` but the user's existing env had not been rebuilt.

Fix (BC-1.19): a preflight subcommand validation block runs immediately
after the `--rebuild-env` handler and before step 1 (conda detection). It
short-circuits two cases without invoking conda or Python:
  - empty $1 + no deck_state.json in cwd → print the spec'd error, exit 1.
  - unknown $1 (anything other than "", "new", "--rebuild-env") → print
    "Usage: debrief [new|--rebuild-env]", exit 1.

Tests below are structural assertions over `bin/debrief`'s source plus
end-to-end shell execution of the script with `command -v conda` shadowed
to FAIL — so that if the preflight does NOT short-circuit, conda detection
will exit 1 with the miniconda message instead of the preflight's message,
which the tests detect.

The tests must pass from both the workspace and the delivered repo.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers (same shape as test_bug_audit_1_bootstrap.py).
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
# Helpers to locate landmarks in the script source.
# ---------------------------------------------------------------------------


def _line_index_of(lines: list[str], needle: str) -> int:
    """Return the first 0-indexed line containing `needle`, or -1."""
    for i, line in enumerate(lines):
        if needle in line:
            return i
    return -1


def _line_index_matching(lines: list[str], pattern: str) -> int:
    rx = re.compile(pattern)
    for i, line in enumerate(lines):
        if rx.search(line):
            return i
    return -1


# ---------------------------------------------------------------------------
# Structural tests: preflight block exists, contains the right strings, and
# is positioned before the smoke test.
# ---------------------------------------------------------------------------


class TestBugAudit95PreflightStructure:
    """The preflight block exists and is sequenced before the smoke test."""

    def test_preflight_sentinel_comments_present(self, bin_debrief_text: str) -> None:
        assert "# BEGIN preflight subcommand validation" in bin_debrief_text, (
            "BC-1.19 requires sentinel `# BEGIN preflight subcommand validation`."
        )
        assert "# END preflight subcommand validation" in bin_debrief_text, (
            "BC-1.19 requires sentinel `# END preflight subcommand validation`."
        )

    def test_preflight_runs_before_smoke_test(self, bin_debrief_lines: list[str]) -> None:
        begin = _line_index_of(bin_debrief_lines, "# BEGIN preflight subcommand validation")
        smoke = _line_index_of(bin_debrief_lines, "import playwright")
        assert begin >= 0, "preflight begin sentinel missing"
        assert smoke >= 0, "smoke test (import playwright) missing"
        assert begin < smoke, (
            f"preflight begin (line {begin + 1}) must precede smoke test "
            f"(line {smoke + 1}) per BC-1.19."
        )

    def test_preflight_runs_before_conda_detection(self, bin_debrief_lines: list[str]) -> None:
        # Step 1 (conda detection) must come AFTER the preflight, since the
        # preflight uses only bash builtins and exits before any conda work.
        begin = _line_index_of(bin_debrief_lines, "# BEGIN preflight subcommand validation")
        # The conda-detection block has a section header comment we anchor on.
        step1_header = _line_index_of(bin_debrief_lines, "Step 1: conda detection")
        assert begin >= 0
        assert step1_header >= 0, "Step 1 section header missing"
        assert begin < step1_header, (
            f"preflight (line {begin + 1}) must precede Step 1 conda detection "
            f"(line {step1_header + 1}) per BC-1.19."
        )

    def test_preflight_runs_after_rebuild_env_branch(self, bin_debrief_lines: list[str]) -> None:
        # The preflight must come AFTER the --rebuild-env branch, since the
        # rebuild branch has its own early-exit semantics (conda env remove +
        # exec self) and must run before any subcommand validation strips it.
        rebuild_idx = _line_index_of(bin_debrief_lines, '"${1:-}" == "--rebuild-env"')
        begin = _line_index_of(bin_debrief_lines, "# BEGIN preflight subcommand validation")
        assert rebuild_idx >= 0, "--rebuild-env branch missing"
        assert begin >= 0
        assert rebuild_idx < begin, (
            f"--rebuild-env branch (line {rebuild_idx + 1}) must precede preflight "
            f"(line {begin + 1}) per BC-1.19."
        )

    def test_preflight_block_contains_no_project_error(self, bin_debrief_text: str) -> None:
        # Carve the preflight block out and assert the canonical error string
        # appears inside it (not just somewhere in the file).
        block = _extract_block(
            bin_debrief_text,
            "# BEGIN preflight subcommand validation",
            "# END preflight subcommand validation",
        )
        assert (
            "ERROR: No project found in the current directory. "
            "Run 'debrief new' to create one." in block
        ), (
            "Preflight block must contain the canonical no-project error string "
            "byte-identical to the late case dispatch (BC-1.19)."
        )

    def test_preflight_block_contains_usage_error(self, bin_debrief_text: str) -> None:
        block = _extract_block(
            bin_debrief_text,
            "# BEGIN preflight subcommand validation",
            "# END preflight subcommand validation",
        )
        assert "Usage: debrief [new|--rebuild-env]" in block, (
            "Preflight block must reject unknown subcommands with the canonical "
            "usage string per BC-1.19."
        )

    def test_preflight_block_checks_deck_state_json(self, bin_debrief_text: str) -> None:
        block = _extract_block(
            bin_debrief_text,
            "# BEGIN preflight subcommand validation",
            "# END preflight subcommand validation",
        )
        assert "deck_state.json" in block, (
            "Preflight must condition the empty-arg case on `deck_state.json` "
            "presence in cwd per BC-1.19."
        )

    def test_preflight_uses_only_bash_builtins(self, bin_debrief_text: str) -> None:
        # BC-1.19 requires the preflight to NOT invoke conda or Python.
        block = _extract_block(
            bin_debrief_text,
            "# BEGIN preflight subcommand validation",
            "# END preflight subcommand validation",
        )
        forbidden = ["conda ", "python ", "python3 ", "command -v conda"]
        for token in forbidden:
            assert token not in block, (
                f"Preflight block must not invoke `{token.strip()}` — it runs before "
                f"conda activation per BC-1.19."
            )


def _extract_block(text: str, begin_marker: str, end_marker: str) -> str:
    """Return the substring between begin_marker and end_marker (exclusive)."""
    begin = text.index(begin_marker) + len(begin_marker)
    end = text.index(end_marker)
    return text[begin:end]


# ---------------------------------------------------------------------------
# Behavioral tests: run bin/debrief with conda shadowed to FAIL on the PATH.
# If the preflight short-circuits, we see the preflight error. If it does
# NOT short-circuit (regression), we see the conda-detection error.
# ---------------------------------------------------------------------------


@pytest.fixture
def bin_debrief_no_conda(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Build an env that runs bin/debrief with no `conda` on PATH.

    Returns (script_path, env_dict). Tests use these to invoke the script
    in a subprocess without any conda available, simulating a fresh
    machine. The preflight must short-circuit BEFORE the missing-conda
    error fires; if it does not, the test sees the conda error instead.
    """
    # Build a minimal PATH containing only standard utilities (no conda).
    # We pull /bin and /usr/bin, which are sufficient for bash, awk, grep,
    # and the script's own shebang.
    minimal_path = "/bin:/usr/bin:/usr/local/bin"
    env = {
        "PATH": minimal_path,
        "HOME": str(tmp_path / "home"),
        # Force CLAUDE_PLUGIN_ROOT so the symlink-resolution path doesn't
        # try to resolve through arbitrary parent dirs.
        "CLAUDE_PLUGIN_ROOT": str(_PROJECT_ROOT / "src" / "unit_1"),
    }
    (tmp_path / "home").mkdir()
    return _bin_debrief_path(), env


def _run_script(script: Path, args: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestBugAudit95PreflightBehavior:
    """End-to-end: preflight short-circuits before conda detection fires."""

    def test_no_args_no_project_emits_run_debrief_new(
        self, bin_debrief_no_conda: tuple[Path, dict[str, str]], tmp_path: Path
    ) -> None:
        script, env = bin_debrief_no_conda
        empty_dir = tmp_path / "empty_project"
        empty_dir.mkdir()
        result = _run_script(script, [], cwd=empty_dir, env=env)
        assert result.returncode == 1, (
            f"Expected exit 1, got {result.returncode}. stderr={result.stderr!r}"
        )
        assert (
            "Run 'debrief new' to create one." in result.stderr
        ), (
            f"Expected the spec'd no-project error in stderr, got: {result.stderr!r}.\n"
            "If stderr mentions 'miniconda' or 'environment is corrupt', the "
            "preflight is NOT short-circuiting before conda checks (BUG-AUDIT-95 "
            "regression)."
        )
        # Negative assertion: the conda-detection error must NOT have fired.
        # If the preflight is broken, this is what the user sees instead.
        assert "miniconda" not in result.stderr.lower(), (
            "BUG-AUDIT-95 regression: missing-conda error fired before preflight."
        )
        assert "environment is corrupt" not in result.stderr, (
            "BUG-AUDIT-95 regression: env-corruption error fired before preflight."
        )

    def test_unknown_subcommand_emits_usage(
        self, bin_debrief_no_conda: tuple[Path, dict[str, str]], tmp_path: Path
    ) -> None:
        script, env = bin_debrief_no_conda
        cwd = tmp_path / "anywhere"
        cwd.mkdir()
        result = _run_script(script, ["bogus_subcommand"], cwd=cwd, env=env)
        assert result.returncode == 1, (
            f"Expected exit 1, got {result.returncode}. stderr={result.stderr!r}"
        )
        assert "Usage: debrief [new|--rebuild-env]" in result.stderr, (
            f"Expected usage string in stderr, got: {result.stderr!r}"
        )
        assert "miniconda" not in result.stderr.lower(), (
            "BUG-AUDIT-95 regression: missing-conda error fired before preflight."
        )

    def test_no_args_with_deck_state_falls_through_to_conda_detection(
        self, bin_debrief_no_conda: tuple[Path, dict[str, str]], tmp_path: Path
    ) -> None:
        # When the user is in a project directory, the preflight must NOT
        # short-circuit — it must fall through to step 1, which (since we
        # shadow conda) will then fail with the miniconda message. This
        # confirms the preflight is not over-triggering on legitimate
        # bare-invocation in a real project.
        script, env = bin_debrief_no_conda
        project_dir = tmp_path / "real_project"
        project_dir.mkdir()
        (project_dir / "deck_state.json").write_text("{}")
        result = _run_script(script, [], cwd=project_dir, env=env)
        # Falls through to conda detection, which fails because we removed
        # conda from PATH. This proves the preflight did not block.
        assert result.returncode == 1
        assert "miniconda" in result.stderr.lower(), (
            "Preflight should fall through when deck_state.json is present; "
            f"saw stderr: {result.stderr!r}"
        )
        # Negative assertion: the no-project error must NOT have fired.
        assert "Run 'debrief new' to create one." not in result.stderr, (
            "Preflight over-triggered: fired no-project error even though "
            "deck_state.json was present."
        )

    def test_new_subcommand_falls_through_to_conda_detection(
        self, bin_debrief_no_conda: tuple[Path, dict[str, str]], tmp_path: Path
    ) -> None:
        # `debrief new` must fall through to conda detection. Same shadow
        # technique: we expect the miniconda error, which proves the
        # preflight did not over-reject.
        script, env = bin_debrief_no_conda
        cwd = tmp_path / "new_project_dir"
        cwd.mkdir()
        result = _run_script(script, ["new"], cwd=cwd, env=env)
        assert result.returncode == 1
        assert "miniconda" in result.stderr.lower(), (
            f"Preflight must let `new` fall through; saw stderr: {result.stderr!r}"
        )
        assert "Usage: debrief" not in result.stderr, (
            "Preflight over-rejected: treated `new` as unknown subcommand."
        )


# ---------------------------------------------------------------------------
# Defense-in-depth: the late case dispatch must still contain the same
# canonical strings, so that any future code path bypassing the preflight
# still produces consistent output. This guards against a future refactor
# that deletes the strings from one location but not the other.
# ---------------------------------------------------------------------------


class TestBugAudit95LateDispatchConsistency:
    """The late case dispatch retains the same error strings (defense-in-depth)."""

    def test_late_dispatch_retains_no_project_error(self, bin_debrief_text: str) -> None:
        # The string must appear at least twice: once in the preflight, once
        # in the late case dispatch. This is the byte-identical-fallback
        # guarantee from BC-1.19.
        target = "ERROR: No project found in the current directory. Run 'debrief new' to create one."
        count = bin_debrief_text.count(target)
        assert count >= 2, (
            f"Expected the no-project error string to appear ≥2 times "
            f"(preflight + late case dispatch); found {count}."
        )

    def test_late_dispatch_retains_usage_error(self, bin_debrief_text: str) -> None:
        target = "Usage: debrief [new|--rebuild-env]"
        count = bin_debrief_text.count(target)
        assert count >= 2, (
            f"Expected the usage error string to appear ≥2 times "
            f"(preflight + late case dispatch); found {count}."
        )
