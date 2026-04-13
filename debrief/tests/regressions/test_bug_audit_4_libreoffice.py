# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-4.

Bug: `environment.yml` pinned `libreoffice-still` unconditionally, but
that conda-forge package ships Linux builds only — macOS bootstrap failed
with `PackagesNotFoundError`. The fix removes the pin and adds a
LibreOffice discovery step in `bin/debrief` that, on macOS, writes a
wrapper shim at `${CONDA_PREFIX}/bin/soffice` pointing at the real
binary inside `/Applications/LibreOffice.app`. On Linux or other
platforms, it exits 1 with install instructions if LibreOffice is
missing.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-4 and
blueprint contracts BC-1.6 (amended) and BC-1.6a (new).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# Path helpers.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _bin_debrief_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "bin" / "debrief"
    delivered = _PROJECT_ROOT / "bin" / "debrief"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find bin/debrief at {workspace} or {delivered}"
    )


def _environment_yml_path() -> Path:
    workspace = _PROJECT_ROOT / "src" / "unit_1" / "environment.yml"
    delivered = _PROJECT_ROOT / "environment.yml"
    for candidate in (workspace, delivered):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find environment.yml at {workspace} or {delivered}"
    )


_SENTINEL_BEGIN = "# BEGIN LibreOffice discovery"
_SENTINEL_END = "# END LibreOffice discovery"


def _extract_discovery_block(text: str) -> str:
    """Return the lines strictly between the LibreOffice discovery sentinels."""
    lines = text.splitlines()
    try:
        begin_idx = next(i for i, line in enumerate(lines) if _SENTINEL_BEGIN in line)
        end_idx = next(i for i, line in enumerate(lines) if _SENTINEL_END in line)
    except StopIteration as exc:
        raise AssertionError(
            "LibreOffice discovery sentinels missing from bin/debrief — BC-1.6a violation."
        ) from exc
    assert begin_idx < end_idx, "BEGIN sentinel must precede END sentinel."
    return "\n".join(lines[begin_idx + 1 : end_idx])


@pytest.fixture(scope="module")
def bin_debrief_text() -> str:
    return _bin_debrief_path().read_text()


@pytest.fixture(scope="module")
def discovery_block(bin_debrief_text: str) -> str:
    return _extract_discovery_block(bin_debrief_text)


@pytest.fixture(scope="module")
def environment_yml_data() -> dict:
    return yaml.safe_load(_environment_yml_path().read_text())


# ---------------------------------------------------------------------------
# BUG-AUDIT-4 regression tests.
# ---------------------------------------------------------------------------


class TestBugAudit4LibreOfficeDiscovery:
    """BC-1.6 (libreoffice-still absent) + BC-1.6a (discovery + shim)."""

    def test_environment_yml_does_not_pin_libreoffice_still(
        self, environment_yml_data: dict
    ) -> None:
        deps = environment_yml_data.get("dependencies", [])
        conda_deps = [d for d in deps if isinstance(d, str)]
        pip_sections = [d for d in deps if isinstance(d, dict) and "pip" in d]
        pip_deps: list[str] = []
        for section in pip_sections:
            for entry in section.get("pip", []):
                if isinstance(entry, str):
                    pip_deps.append(entry)
        assert not any("libreoffice-still" in d for d in conda_deps), (
            f"BUG-AUDIT-4 regression: libreoffice-still in environment.yml conda deps: "
            f"{conda_deps}. It's Linux-only on conda-forge and blocks macOS bootstrap. "
            f"See BC-1.6."
        )
        assert not any("libreoffice-still" in d for d in pip_deps), (
            f"BUG-AUDIT-4 regression: libreoffice-still in environment.yml pip deps: "
            f"{pip_deps}. Pip cannot install LibreOffice either; it's a system dep."
        )

    def test_bin_debrief_has_libreoffice_discovery_sentinels(
        self, bin_debrief_text: str
    ) -> None:
        assert _SENTINEL_BEGIN in bin_debrief_text, (
            f"BC-1.6a requires `{_SENTINEL_BEGIN}` sentinel so regression tests "
            "can extract and scope-check the discovery block."
        )
        assert _SENTINEL_END in bin_debrief_text, (
            f"BC-1.6a requires `{_SENTINEL_END}` sentinel."
        )

    def test_bin_debrief_checks_soffice_on_path(self, discovery_block: str) -> None:
        assert "command -v soffice" in discovery_block, (
            "BC-1.6a: discovery must check `command -v soffice` before falling "
            "back to platform-specific discovery."
        )

    def test_bin_debrief_creates_macos_soffice_shim(self, discovery_block: str) -> None:
        assert "/Applications/LibreOffice.app/Contents/MacOS/soffice" in discovery_block, (
            "BC-1.6a: macOS branch must reference the standard LibreOffice.app path."
        )
        assert '"${CONDA_PREFIX}/bin/soffice"' in discovery_block or \
               "${CONDA_PREFIX}/bin/soffice" in discovery_block, (
            "BC-1.6a: macOS branch must write the shim into ${CONDA_PREFIX}/bin/soffice."
        )
        assert "uname -s" in discovery_block, (
            "BC-1.6a: platform detection via `uname -s` is required."
        )
        assert "Darwin" in discovery_block, (
            "BC-1.6a: macOS branch must gate on `uname -s` returning Darwin."
        )
        assert "chmod +x" in discovery_block, (
            "BC-1.6a: the shim must be marked executable via chmod +x."
        )

    def test_bin_debrief_shim_heredoc_is_quoted(self, discovery_block: str) -> None:
        # The heredoc delimiter must be single-quoted so variable expansion
        # is disabled and the hardcoded macOS path lands verbatim in the
        # shim file.
        assert "<<'DEBRIEF_SOFFICE_SHIM_EOF'" in discovery_block, (
            "BC-1.6a: the shim heredoc delimiter must be quoted "
            "(`<<'DEBRIEF_SOFFICE_SHIM_EOF'`) to disable variable expansion. "
            "An unquoted delimiter would expand ${...} inside the shim and "
            "write an empty path."
        )

    def test_bin_debrief_prints_install_instructions_if_missing(
        self, discovery_block: str
    ) -> None:
        assert "libreoffice.org/download" in discovery_block, (
            "BC-1.6a: install instructions must reference libreoffice.org/download."
        )
        assert "apt install libreoffice" in discovery_block, (
            "BC-1.6a: Linux branch must mention `apt install libreoffice` for Debian/Ubuntu."
        )
        assert "dnf install libreoffice" in discovery_block, (
            "BC-1.6a: Linux branch must mention `dnf install libreoffice` for Fedora/RHEL."
        )
        assert "brew" in discovery_block, (
            "BC-1.6a: macOS branch should mention brew as an install option."
        )
        assert "ERROR: LibreOffice" in discovery_block, (
            "BC-1.6a: the error message must begin with `ERROR: LibreOffice`."
        )

    def test_bin_debrief_libreoffice_exit_code_is_1_not_2(
        self, discovery_block: str
    ) -> None:
        # Scope the exit code check to the missing-install branch: everything
        # after the `ERROR: LibreOffice` line and before the final `fi` of the
        # discovery block.
        error_idx = discovery_block.find("ERROR: LibreOffice")
        assert error_idx != -1, "Discovery block missing error message."
        after_error = discovery_block[error_idx:]
        assert "exit 1" in after_error, (
            "BC-1.6a: the missing-install branch must `exit 1` (missing system dep)."
        )
        # exit 2 is reserved for env-corruption per §9.3.1 and must not appear
        # in the missing-install branch of the discovery block.
        assert "exit 2" not in after_error, (
            "BC-1.6a: the missing-install branch must NOT use `exit 2` (that's "
            "reserved for env corruption per §9.3.1). Missing system deps use exit 1."
        )

    def test_discovery_step_appears_between_smoke_test_and_pip_install(
        self, bin_debrief_text: str
    ) -> None:
        # BC-1.6a: discovery must run at §24.4 step 5.6 — after the smoke
        # test (step 5.5) and before the pip install marker check (step 6).
        smoke_test_idx = bin_debrief_text.find(
            "import playwright, pptx, fitz, json_repair"
        )
        begin_sentinel_idx = bin_debrief_text.find(_SENTINEL_BEGIN)
        pip_install_idx = bin_debrief_text.find('pip install -e "${CLAUDE_PLUGIN_ROOT}"')
        assert smoke_test_idx != -1, "Smoke test missing from bin/debrief."
        assert begin_sentinel_idx != -1, "Discovery sentinel missing from bin/debrief."
        assert pip_install_idx != -1, "pip install -e call missing from bin/debrief."
        assert smoke_test_idx < begin_sentinel_idx, (
            "BC-1.6a: LibreOffice discovery must appear AFTER the smoke test "
            "(step 5.5) in source order."
        )
        assert begin_sentinel_idx < pip_install_idx, (
            "BC-1.6a: LibreOffice discovery must appear BEFORE the pip install "
            "marker check (step 6) in source order."
        )
