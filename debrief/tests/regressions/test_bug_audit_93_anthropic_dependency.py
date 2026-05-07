# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-93 — INVERTED by BUG-AUDIT-103.

Original (BUG-AUDIT-93) contract: ``anthropic>=0.40`` was REQUIRED in
both ``pyproject.toml`` ``[project.dependencies]`` AND
``environment.yml``'s pip section, and the ``bin/debrief`` step 5.5
smoke test imported it. The mandate was correct at BUG-AUDIT-93 time
because every canonical rewriter and script-writer trigger hit the SDK
on its critical path.

BUG-AUDIT-101 + BUG-AUDIT-102 moved those triggers to Task-dispatch via
the consultant. After cycle 102, the SDK is reachable only on legacy
direct-CLI paths. BUG-AUDIT-103 demoted ``anthropic`` to an optional
``[project.optional-dependencies]`` extras dep with key ``sdk_fallback``,
removed it from ``environment.yml``, and dropped it from the
``bin/debrief`` smoke test.

This test file's CONTRACT is therefore inverted by BUG-AUDIT-103 — same
filename for git-history-traceability, opposite assertions:

  (a) ``anthropic`` is NOT in ``pyproject.toml`` ``[project.dependencies]``.
  (b) ``anthropic>=0.40`` IS in ``pyproject.toml``
      ``[project.optional-dependencies]`` under the ``sdk_fallback`` key.
  (c) ``environment.yml``'s pip section does NOT contain ``anthropic``.
  (d) ``bin/debrief`` step 5.5 smoke test does NOT import ``anthropic``.

The original BUG-AUDIT-93 stderr-emission tests in
``test_bug_audit_93_anthropic_missing_stderr.py`` are unchanged and
continue to validate the legacy-path behavior — those code paths still
exist and still emit the actionable stderr line when invoked
explicitly without the SDK installed.
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


# ---------------------------------------------------------------------------
# pyproject.toml — inverted: not in required deps, IS in optional
# ---------------------------------------------------------------------------


def test_pyproject_does_not_declare_anthropic_in_required_dependencies() -> None:
    """BUG-AUDIT-103 / BC-1.18a: anthropic is NO LONGER in [project.dependencies]."""
    content = _pyproject_path().read_text()
    # Carve out the [project] block (everything from [project] to the
    # next top-level [section]).
    project_start = content.find("[project]")
    assert project_start >= 0, "[project] section not found"
    next_section = content.find("\n[", project_start + 1)
    project_block = (
        content[project_start:next_section] if next_section >= 0 else content[project_start:]
    )
    # The [project] block should NOT contain `anthropic>=...`.
    assert _ANTHROPIC_LINE_RE.search(project_block) is None, (
        "BC-1.18a (BUG-AUDIT-103): anthropic must NOT appear in "
        "[project.dependencies]; it has been demoted to "
        "[project.optional-dependencies].sdk_fallback."
    )


def test_pyproject_declares_anthropic_in_optional_dependencies() -> None:
    """BUG-AUDIT-103 / BC-1.18a: anthropic IS in [project.optional-dependencies]
    under the ``sdk_fallback`` extras key."""
    content = _pyproject_path().read_text()
    opt_start = content.find("[project.optional-dependencies]")
    assert opt_start >= 0, (
        "BC-1.18a (BUG-AUDIT-103): pyproject.toml must contain a "
        "[project.optional-dependencies] section."
    )
    next_section = content.find("\n[", opt_start + 1)
    opt_block = (
        content[opt_start:next_section] if next_section >= 0 else content[opt_start:]
    )
    # Must define an `sdk_fallback` extras key.
    assert "sdk_fallback" in opt_block, (
        "BC-1.18a (BUG-AUDIT-103): [project.optional-dependencies] must "
        "define an `sdk_fallback` extras key."
    )
    # And it must list anthropic>=0.40.
    assert _ANTHROPIC_LINE_RE.search(opt_block) is not None, (
        "BC-1.18a (BUG-AUDIT-103): the sdk_fallback extras must include "
        "anthropic>=0.40."
    )


# ---------------------------------------------------------------------------
# environment.yml — inverted: not in pip section
# ---------------------------------------------------------------------------


def test_environment_yml_does_not_declare_anthropic() -> None:
    """BUG-AUDIT-103 / BC-1.18a: environment.yml's pip section must NOT
    list anthropic. Users who want the SDK install with
    ``pip install '.[sdk_fallback]'`` after the conda env is built."""
    content = _environment_yml_path().read_text()
    pip_idx = content.find("- pip:")
    assert pip_idx >= 0, "environment.yml must contain a pip section"
    pip_block = content[pip_idx:]
    assert _ANTHROPIC_LINE_RE.search(pip_block) is None, (
        "BC-1.18a (BUG-AUDIT-103): anthropic must NOT appear in "
        "environment.yml's pip section."
    )


# ---------------------------------------------------------------------------
# bin/debrief smoke test (step 5.5) — inverted: anthropic NOT imported
# ---------------------------------------------------------------------------


def test_bin_debrief_smoke_test_does_not_import_anthropic() -> None:
    """BC-1.16 (BUG-AUDIT-103 amendment): the smoke test imports
    ``playwright, pptx, fitz, json_repair`` only — back to its
    pre-BUG-AUDIT-93 shape. anthropic is no longer required to be
    importable at bootstrap because cycles 101/102 retired the SDK
    from the canonical user flows."""
    content = _bin_debrief_path().read_text()
    smoke_re = re.compile(r"python\s+-c\s+'import\s+([^']+)'")
    matches = smoke_re.findall(content)
    assert matches, "bin/debrief must contain a python -c smoke import line"
    fitz_smoke = [m for m in matches if "fitz" in m]
    assert fitz_smoke, (
        "bin/debrief step 5.5 smoke test (the one importing fitz) not found"
    )
    imports = {x.strip() for x in fitz_smoke[0].split(",")}
    assert "anthropic" not in imports, (
        "BC-1.16 (BUG-AUDIT-103): bin/debrief step 5.5 smoke test must NOT "
        "import anthropic; the smoke list is "
        "{playwright, pptx, fitz, json_repair} only."
    )
