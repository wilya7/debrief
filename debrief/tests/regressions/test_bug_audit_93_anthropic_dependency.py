# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-93: declared-dependency on anthropic SDK.

Pre-fix, ``src/debrief/launcher.py`` lazy-imported ``anthropic`` at two
sites (``call_script_writer_agent``, ``call_rewrite_agent``) but neither
``pyproject.toml`` nor ``environment.yml`` declared the dependency. A
default install (``bin/debrief`` bootstrapping via environment.yml, or
``pip install .`` reading pyproject.toml) left the conda env without the
SDK; both ``/debrief:script`` and the rewriter (PreCompact + manual)
silently failed.

This test pins:
  (a) ``anthropic>=0.40`` is declared in pyproject.toml [project.dependencies]
  (b) ``anthropic>=0.40`` is declared in environment.yml pip section
  (c) the minimum version is consistent across both files
  (d) ``bin/debrief`` step 5.5 smoke test imports ``anthropic`` so a corrupt
      env is caught at bootstrap, not at the first /debrief:script invocation.
"""

from __future__ import annotations

import re
from pathlib import Path

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_1").is_dir()


def _pyproject_path() -> Path:
    # pyproject.toml is delivered-only by design (BC-1.17 / BUG-AUDIT-1) — no
    # workspace copy. In workspace runs we still locate it via the sibling
    # delivered repo so the test enforces the contract end-to-end.
    if _is_workspace_layout():
        return _PROJECT_ROOT.parent / "debrief1.0-repo" / "debrief" / "pyproject.toml"
    return _PROJECT_ROOT / "pyproject.toml"


def _environment_yml_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "environment.yml"
    return _PROJECT_ROOT / "environment.yml"


def _bin_debrief_path() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_1" / "bin" / "debrief"
    return _PROJECT_ROOT / "bin" / "debrief"


_ANTHROPIC_LINE_RE = re.compile(
    r"""anthropic\s*>=\s*(?P<version>\d+\.\d+(?:\.\d+)?)""",
    re.IGNORECASE,
)
_MIN_VERSION = (0, 40)


def _parse_min_version(line: str) -> tuple[int, ...]:
    m = _ANTHROPIC_LINE_RE.search(line)
    assert m, f"line does not match anthropic>=X.Y pattern: {line!r}"
    return tuple(int(p) for p in m.group("version").split("."))


# ---------------------------------------------------------------------------
# pyproject.toml
# ---------------------------------------------------------------------------


def test_pyproject_declares_anthropic_dependency() -> None:
    content = _pyproject_path().read_text()
    # The anthropic line must appear within the [project] dependencies list,
    # not in a [tool.X] section. Find the [project] block and grep within.
    project_start = content.find("[project]")
    next_section = content.find("\n[", project_start + 1)
    project_block = content[project_start:next_section] if next_section >= 0 else content[project_start:]
    assert _ANTHROPIC_LINE_RE.search(project_block), (
        "pyproject.toml [project.dependencies] must declare anthropic>=0.40 "
        "per BC-1.18 / BUG-AUDIT-93"
    )


def test_pyproject_anthropic_minimum_version() -> None:
    content = _pyproject_path().read_text()
    m = _ANTHROPIC_LINE_RE.search(content)
    assert m
    version = tuple(int(p) for p in m.group("version").split("."))
    assert version >= _MIN_VERSION, (
        f"pyproject.toml requires anthropic>={'.'.join(map(str, _MIN_VERSION))} "
        f"or newer; got >={m.group('version')}"
    )


# ---------------------------------------------------------------------------
# environment.yml
# ---------------------------------------------------------------------------


def test_environment_yml_declares_anthropic() -> None:
    content = _environment_yml_path().read_text()
    # Must be inside the pip section.
    pip_idx = content.find("- pip:")
    assert pip_idx >= 0, "environment.yml must contain a pip section"
    pip_block = content[pip_idx:]
    assert _ANTHROPIC_LINE_RE.search(pip_block), (
        "environment.yml pip section must declare anthropic>=0.40 "
        "per BC-1.18 / BUG-AUDIT-93"
    )


def test_environment_yml_anthropic_minimum_version() -> None:
    content = _environment_yml_path().read_text()
    pip_idx = content.find("- pip:")
    pip_block = content[pip_idx:]
    m = _ANTHROPIC_LINE_RE.search(pip_block)
    assert m
    version = tuple(int(p) for p in m.group("version").split("."))
    assert version >= _MIN_VERSION


# ---------------------------------------------------------------------------
# Cross-file consistency
# ---------------------------------------------------------------------------


def test_pyproject_and_environment_yml_anthropic_versions_match() -> None:
    """The two install specs must agree on the minimum version (BC-1.18)."""
    py_match = _ANTHROPIC_LINE_RE.search(_pyproject_path().read_text())
    yml_match = _ANTHROPIC_LINE_RE.search(_environment_yml_path().read_text())
    assert py_match and yml_match
    assert py_match.group("version") == yml_match.group("version"), (
        f"pyproject.toml requires anthropic>={py_match.group('version')} but "
        f"environment.yml requires anthropic>={yml_match.group('version')}"
    )


# ---------------------------------------------------------------------------
# bin/debrief smoke test (step 5.5)
# ---------------------------------------------------------------------------


def test_bin_debrief_smoke_test_imports_anthropic() -> None:
    """bin/debrief step 5.5 smoke test MUST import anthropic so a corrupt
    env is caught at bootstrap, not at the first /debrief:script invocation
    (which would otherwise log silently and exit 0 per REQ-SCRIPT-WRITER-2).
    """
    content = _bin_debrief_path().read_text()
    # The smoke test is a single python -c invocation listing the imports.
    smoke_re = re.compile(
        r"python\s+-c\s+'import\s+([^']+)'",
    )
    matches = smoke_re.findall(content)
    assert matches, "bin/debrief must contain a python -c smoke import line"
    # Find the smoke that includes 'fitz' (the canonical step-5.5 line).
    fitz_smoke = [m for m in matches if "fitz" in m]
    assert fitz_smoke, (
        "bin/debrief step 5.5 smoke test (the one importing fitz) not found"
    )
    imports = {x.strip() for x in fitz_smoke[0].split(",")}
    assert "anthropic" in imports, (
        "bin/debrief step 5.5 smoke test MUST import anthropic per BC-1.18"
    )
