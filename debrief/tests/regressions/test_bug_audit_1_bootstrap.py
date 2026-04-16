# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-1.

Bug: `bin/debrief` was a thin shim and `pyproject.toml` declared a competing
`[project.scripts] debrief = "debrief.launcher:main_new"` entry point. Both
bypassed the spec §24.4 bootstrap sequence, causing first-run users to hit
ModuleNotFoundError before any bootstrap could run. See
`spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-1.

The tests below are structural assertions over the content of
`bin/debrief` and `pyproject.toml`. Structural tests are chosen because the
full end-to-end bootstrap (conda env create, pip install, playwright install
chromium) cannot be exercised in unit-test CI. The assertions cover every
distinct step of spec §24.4 so that any regression to a thin shim or the
re-introduction of the pyproject entry point fails loudly.

The tests must pass from both the workspace and the delivered repo. In the
workspace, `bin/debrief` lives at `src/unit_1/bin/debrief` and no
`pyproject.toml` exists at the project root (the only `pyproject.toml` is in
the sibling `debrief1.0-repo/debrief/` delivered repo). In the delivered
repo, `bin/debrief` lives at `bin/debrief` and `pyproject.toml` sits at the
plugin root. The path helpers below resolve whichever location applies.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Path helpers: locate bin/debrief and pyproject.toml in either layout.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _bin_debrief_path() -> Path:
    """Return the path to bin/debrief in whichever repo layout we're in.

    Workspace layout (SVP source of truth): src/unit_1/bin/debrief.
    Delivered repo layout: bin/debrief at the plugin root.
    """
    workspace_candidate = _PROJECT_ROOT / "src" / "unit_1" / "bin" / "debrief"
    delivered_candidate = _PROJECT_ROOT / "bin" / "debrief"
    if workspace_candidate.exists():
        return workspace_candidate
    if delivered_candidate.exists():
        return delivered_candidate
    raise FileNotFoundError(
        f"Could not find bin/debrief at {workspace_candidate} or {delivered_candidate}"
    )


def _pyproject_path() -> Path:
    """Return the path to the authoritative pyproject.toml.

    In the delivered repo it sits at the plugin root. In the workspace it
    lives only in the sibling delivered repo (there is no workspace copy).
    """
    delivered_at_root = _PROJECT_ROOT / "pyproject.toml"
    if delivered_at_root.exists():
        return delivered_at_root
    sibling_delivered = _PROJECT_ROOT.parent / "debrief1.0-repo" / "debrief" / "pyproject.toml"
    if sibling_delivered.exists():
        return sibling_delivered
    raise FileNotFoundError(
        f"Could not find pyproject.toml at {delivered_at_root} or {sibling_delivered}"
    )


@pytest.fixture(scope="module")
def bin_debrief_text() -> str:
    return _bin_debrief_path().read_text()


@pytest.fixture(scope="module")
def bin_debrief_lines(bin_debrief_text: str) -> list[str]:
    return bin_debrief_text.splitlines()


# ---------------------------------------------------------------------------
# BUG-AUDIT-1 regression tests for bin/debrief (BC-1.16).
# ---------------------------------------------------------------------------


class TestBugAudit1BinDebriefBootstrap:
    """Every step of spec §24.4 must appear in bin/debrief content."""

    def test_bin_debrief_is_not_thin_shim(self, bin_debrief_lines: list[str]) -> None:
        # The broken shim was 11 lines. A compliant §24.4 implementation has
        # step headers plus error messages plus subcommand dispatch and is
        # substantially longer. 50 lines is a comfortable lower bound that
        # will catch any future regression to a shim-like form.
        assert len(bin_debrief_lines) > 50, (
            f"bin/debrief is {len(bin_debrief_lines)} lines — too short to be a "
            "compliant §24.4 implementation. See BUG-AUDIT-1."
        )

    def test_bin_debrief_detects_conda(self, bin_debrief_text: str) -> None:
        assert "command -v conda" in bin_debrief_text, (
            "§24.4 step 1 requires conda detection via `command -v conda`."
        )
        assert "miniconda" in bin_debrief_text.lower(), (
            "§24.4 step 1 requires the miniconda install hint in the error message."
        )

    def test_bin_debrief_sources_conda_init(self, bin_debrief_text: str) -> None:
        assert "conda info --base" in bin_debrief_text
        assert "profile.d/conda.sh" in bin_debrief_text, (
            "§24.4 step 2 requires sourcing `$(conda info --base)/etc/profile.d/conda.sh`."
        )

    def test_bin_debrief_checks_env_existence(self, bin_debrief_text: str) -> None:
        assert "conda env list" in bin_debrief_text, (
            "§24.4 step 3 requires checking env existence via `conda env list`."
        )
        assert "grep -qx debrief" in bin_debrief_text, (
            "§24.4 step 3 requires the `grep -qx debrief` exact-match check."
        )

    def test_bin_debrief_creates_env_from_environment_yml(self, bin_debrief_text: str) -> None:
        assert "conda env create -f" in bin_debrief_text
        assert "${CLAUDE_PLUGIN_ROOT}/environment.yml" in bin_debrief_text
        assert "-n debrief" in bin_debrief_text, (
            "§24.4 step 4 requires `conda env create -f ${CLAUDE_PLUGIN_ROOT}/environment.yml -n debrief`."
        )

    def test_bin_debrief_prints_first_run_message(self, bin_debrief_text: str) -> None:
        assert (
            "First-run setup: creating the debrief conda environment"
            in bin_debrief_text
        ), "§24.4 step 4 prescribes the exact first-run progress message."

    def test_bin_debrief_handles_partial_env_cleanup(self, bin_debrief_text: str) -> None:
        assert "conda env remove -n debrief" in bin_debrief_text, (
            "§24.4 step 4 requires cleaning up partial envs on creation failure."
        )
        assert "Partial debrief env exists and could not be removed automatically." in bin_debrief_text

    def test_bin_debrief_activates_env(self, bin_debrief_text: str) -> None:
        assert "conda activate debrief" in bin_debrief_text, (
            "§24.4 step 5 requires `conda activate debrief`."
        )

    def test_bin_debrief_runs_smoke_test(self, bin_debrief_text: str) -> None:
        # §24.4 step 5.5 smoke test — verbatim imports and exit code 2 for the
        # Section 9.3.1 standardized error.
        assert "import playwright" in bin_debrief_text
        assert "import pptx" in bin_debrief_text or "pptx" in bin_debrief_text
        assert "import fitz" in bin_debrief_text or "fitz" in bin_debrief_text
        assert "json_repair" in bin_debrief_text
        assert "exit 2" in bin_debrief_text, (
            "§24.4 step 5.5 requires exit code 2 on smoke-test failure per §9.3.1."
        )

    def test_bin_debrief_gates_pip_install_on_marker(self, bin_debrief_text: str) -> None:
        assert "pkg_version_" in bin_debrief_text
        assert ".marker" in bin_debrief_text
        assert "pip install -e" in bin_debrief_text
        assert "${CLAUDE_PLUGIN_ROOT}" in bin_debrief_text, (
            "§24.4 step 6 requires `pip install -e ${CLAUDE_PLUGIN_ROOT}` gated on a version marker."
        )
        # Marker must live under ~/.cache/debrief (spec §24.4 marker file semantics).
        assert "${HOME}/.cache/debrief" in bin_debrief_text

    def test_bin_debrief_reads_plugin_version_from_manifest(self, bin_debrief_text: str) -> None:
        assert ".claude-plugin/plugin.json" in bin_debrief_text, (
            "§24.4 step 6 requires reading <version> from .claude-plugin/plugin.json."
        )

    def test_bin_debrief_gates_chromium_on_conda_prefix_marker(self, bin_debrief_text: str) -> None:
        assert "${CONDA_PREFIX}/.debrief_chromium_installed" in bin_debrief_text, (
            "§24.4 step 7 requires the chromium marker at ${CONDA_PREFIX}/.debrief_chromium_installed."
        )
        assert "playwright install chromium" in bin_debrief_text

    def test_bin_debrief_runs_vendor_hash_preflight(self, bin_debrief_text: str) -> None:
        assert "python -m debrief.launcher preflight" in bin_debrief_text, (
            "§24.4 step 8 requires `python -m debrief.launcher preflight` for vendor hash verification."
        )

    def test_bin_debrief_dispatches_new_subcommand(self, bin_debrief_text: str) -> None:
        # §24.4 step 9: `new` arm invokes python -m debrief.launcher new before
        # launching Claude Code.
        assert "python -m debrief.launcher new" in bin_debrief_text
        assert "new)" in bin_debrief_text or '"new"' in bin_debrief_text

    def test_bin_debrief_dispatches_bare_invocation_checks_deck_state(
        self, bin_debrief_text: str
    ) -> None:
        # §24.4 step 9 bare arm: check deck_state.json existence; if absent,
        # print the exact "No project found" error and exit 1.
        assert "deck_state.json" in bin_debrief_text
        assert "No project found in the current directory" in bin_debrief_text

    def test_bin_debrief_handles_rebuild_env(self, bin_debrief_text: str) -> None:
        # §24.4 --rebuild-env branch: deletes pkg markers, removes env,
        # re-execs with DEBRIEF_REBUILD_DONE=1 to prevent recursion.
        assert "--rebuild-env" in bin_debrief_text
        assert "DEBRIEF_REBUILD_DONE" in bin_debrief_text
        assert 'exec "$0"' in bin_debrief_text, (
            "§24.4 --rebuild-env branch requires re-execution via `exec \"$0\"` with a recursion guard."
        )
        assert "pkg_version_*.marker" in bin_debrief_text, (
            "§24.4 --rebuild-env branch must delete pkg_version_*.marker files."
        )

    def test_bin_debrief_launches_claude_no_flags(
        self, bin_debrief_text: str
    ) -> None:
        # §24.4 step 10 / BC-1.16 / BUG-AUDIT-8: the launch invocation is
        # plain `exec claude` with NO flags. Claude Code auto-discovers the
        # project-scoped `.claude/settings.json` (written by
        # `ensure_project_settings`) and loads the debrief plugin via the
        # marketplace mechanism, namespacing skills as `/debrief:*`.
        # Historical note: BUG-AUDIT-5 pinned `--plugin-dir` here; that
        # load path was retired by BUG-AUDIT-8 because it skipped
        # marketplace registration and produced bare-named skills that
        # collided with built-in `/export`, `/save`, `/quit`.
        import re
        # BUG-AUDIT-45: exec claude may now have $_DEBRIEF_CLAUDE_FLAGS
        assert re.search(r"\bexec claude\b", bin_debrief_text, re.MULTILINE), (
            "§24.4 step 10 / BC-1.16 requires `exec claude` as the final "
            "launch. BUG-AUDIT-45 allows optional flags via config."
        )

    def test_bin_debrief_is_executable(self) -> None:
        path = _bin_debrief_path()
        assert os.access(path, os.X_OK), f"{path} must be executable (chmod +x)."

    def test_bin_debrief_starts_with_bash_shebang(self, bin_debrief_lines: list[str]) -> None:
        assert bin_debrief_lines[0].startswith("#!") and "bash" in bin_debrief_lines[0], (
            "§24.4 requires a bash shebang on the first line."
        )


# ---------------------------------------------------------------------------
# BUG-AUDIT-1 regression test for pyproject.toml (BC-1.17).
# ---------------------------------------------------------------------------


class TestBugAudit1NoCompetingEntryPoint:
    """The delivered pyproject.toml must not declare a `debrief` console script."""

    def test_pyproject_has_no_competing_entry_point(self) -> None:
        data = tomllib.loads(_pyproject_path().read_text())
        scripts = data.get("project", {}).get("scripts", {})
        assert "debrief" not in scripts, (
            "pyproject.toml [project.scripts] must NOT contain a `debrief` entry. "
            "bin/debrief is the sole entry point per spec §9.4 line 683 and BC-1.17. "
            "A console_script shim would bypass the conda bootstrap. See BUG-AUDIT-1."
        )
