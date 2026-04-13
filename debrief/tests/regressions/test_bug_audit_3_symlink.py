# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-3.

Bug 3a: `bin/debrief`'s `CLAUDE_PLUGIN_ROOT` fallback did not follow
symlinks, so installing the launcher as a symlink on PATH (e.g.,
`~/.local/bin/debrief → .../debrief1.0-repo/debrief/bin/debrief`) caused
every plugin-relative path — `environment.yml`, `.claude-plugin/plugin.json`,
`pip install -e`, `exec claude --plugin` — to point at the symlink's parent
directory instead of the real plugin root.

Bug 3b: the env-create failure cleanup ran `conda env remove -n debrief -y`
on every create failure and, when the env did not exist, the command's
non-zero exit triggered a misleading "Partial debrief env exists and could
not be removed automatically" error message.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-3 and blueprint
contracts BC-1.16a and BC-1.16b.

Test #5 is the high-value one: it extracts the real symlink-resolution
block from `bin/debrief` (delimited by sentinel comments), runs it under
an actual symlink in `tmp_path`, and asserts the output equals the real
plugin root.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers: locate bin/debrief in either layout.
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


_SENTINEL_BEGIN = "# BEGIN CLAUDE_PLUGIN_ROOT resolution (symlink-safe)"
_SENTINEL_END = "# END CLAUDE_PLUGIN_ROOT resolution (symlink-safe)"


def _extract_resolution_block(text: str) -> str:
    """Return the lines strictly between the sentinel comments."""
    lines = text.splitlines()
    try:
        begin_idx = next(i for i, line in enumerate(lines) if _SENTINEL_BEGIN in line)
        end_idx = next(i for i, line in enumerate(lines) if _SENTINEL_END in line)
    except StopIteration as exc:
        raise AssertionError(
            "Sentinel comments missing from bin/debrief — BC-1.16a violation."
        ) from exc
    assert begin_idx < end_idx, "BEGIN sentinel must precede END sentinel."
    return "\n".join(lines[begin_idx + 1 : end_idx])


@pytest.fixture(scope="module")
def bin_debrief_text() -> str:
    return _bin_debrief_path().read_text()


# ---------------------------------------------------------------------------
# BUG-AUDIT-3 regression tests.
# ---------------------------------------------------------------------------


class TestBugAudit3SymlinkResolution:
    """BC-1.16a symlink-safe plugin root + BC-1.16b accurate cleanup."""

    def test_resolution_block_uses_symlink_safe_idiom(self, bin_debrief_text: str) -> None:
        assert "while [[ -L" in bin_debrief_text, (
            "BC-1.16a requires a `while [[ -L ... ]]` loop to walk symlink chains."
        )
        assert "readlink" in bin_debrief_text, (
            "BC-1.16a requires `readlink` for portable macOS symlink resolution."
        )

    def test_resolution_block_has_sentinels(self, bin_debrief_text: str) -> None:
        assert _SENTINEL_BEGIN in bin_debrief_text, (
            f"BC-1.16a requires the `{_SENTINEL_BEGIN}` sentinel so the resolution "
            "block can be extracted and functionally tested."
        )
        assert _SENTINEL_END in bin_debrief_text, (
            f"BC-1.16a requires the `{_SENTINEL_END}` sentinel."
        )

    def test_no_legacy_unsafe_resolution_pattern(self, bin_debrief_text: str) -> None:
        legacy_line_1 = 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"'
        legacy_line_2 = 'CLAUDE_PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"'
        assert legacy_line_1 not in bin_debrief_text, (
            "BUG-AUDIT-3a regression: the legacy unsafe SCRIPT_DIR idiom is back "
            "in bin/debrief. See BC-1.16a."
        )
        assert legacy_line_2 not in bin_debrief_text, (
            "BUG-AUDIT-3a regression: the legacy unsafe CLAUDE_PLUGIN_ROOT "
            "assignment is back in bin/debrief. See BC-1.16a."
        )

    def test_cleanup_checks_env_existence_before_claiming_partial(
        self, bin_debrief_text: str
    ) -> None:
        # BC-1.16b: the existence check must appear in source order before
        # the "Partial debrief env exists" literal so that the false-alarm
        # path cannot fire without a real env present.
        env_create_idx = bin_debrief_text.find(
            'conda env create -f "${CLAUDE_PLUGIN_ROOT}/environment.yml" -n debrief'
        )
        assert env_create_idx != -1, (
            "bin/debrief must still call `conda env create -f ... -n debrief`."
        )
        partial_msg_idx = bin_debrief_text.find(
            "Partial debrief env exists and could not be removed automatically."
        )
        assert partial_msg_idx != -1, (
            "Partial-env error message must still exist for the real-partial-env case."
        )
        between = bin_debrief_text[env_create_idx:partial_msg_idx]
        assert "grep -qx debrief" in between, (
            "BC-1.16b: the env existence check `grep -qx debrief` must appear "
            "between `conda env create` and the `Partial debrief env exists` "
            "literal, guarding the partial-env claim on real existence."
        )

    def test_symlink_resolution_works_functionally(
        self, bin_debrief_text: str, tmp_path: Path
    ) -> None:
        # Extract the resolution block between sentinels from the REAL
        # bin/debrief and exercise it under a real symlink. This is the
        # high-value test: it catches any regression where the idiom
        # looks correct but doesn't actually resolve the symlink.
        resolution_block = _extract_resolution_block(bin_debrief_text)

        # Build a standalone bash script: clear CLAUDE_PLUGIN_ROOT, run the
        # extracted block, print the resolved value, then exit.
        script_content = (
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            'CLAUDE_PLUGIN_ROOT=""\n'
            f"{resolution_block}\n"
            'echo "$CLAUDE_PLUGIN_ROOT"\n'
        )

        # Create a tmp plugin layout: <tmp>/real/bin/resolver is the real
        # script; <tmp>/symlink_dir/debrief is a symlink pointing at it.
        real_plugin_dir = tmp_path / "real"
        real_bin_dir = real_plugin_dir / "bin"
        real_bin_dir.mkdir(parents=True)
        real_script = real_bin_dir / "resolver"
        real_script.write_text(script_content)
        real_script.chmod(real_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        symlink_dir = tmp_path / "symlink_dir"
        symlink_dir.mkdir()
        symlink = symlink_dir / "debrief"
        symlink.symlink_to(real_script)

        # Invoke via the symlink.
        result = subprocess.run(
            [str(symlink)],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "CLAUDE_PLUGIN_ROOT": ""},
        )
        resolved = result.stdout.strip()

        # The resolved plugin root must equal the REAL plugin directory,
        # not the symlink's parent. Use realpath on both sides to normalize
        # /private/var vs /var on macOS.
        expected = str(real_plugin_dir.resolve())
        assert os.path.realpath(resolved) == expected, (
            f"BUG-AUDIT-3a regression: symlink resolution returned {resolved!r}, "
            f"expected {expected!r} (the REAL plugin dir, not the symlink parent)."
        )

        # Negative check: ensure the symlink's parent doesn't leak through.
        symlink_parent_real = os.path.realpath(str(symlink_dir))
        assert os.path.realpath(resolved) != symlink_parent_real, (
            f"BUG-AUDIT-3a regression: resolution leaked the symlink's parent dir "
            f"({symlink_parent_real!r}) as CLAUDE_PLUGIN_ROOT."
        )

    def test_env_create_error_without_partial_env_does_not_print_misleading_message(
        self, bin_debrief_text: str
    ) -> None:
        # BC-1.16b: between the `conda env create -f ...` call and the
        # "Partial debrief env exists" literal, there must be exactly one
        # env existence check (`grep -qx debrief` inside a `conda env list`
        # pipeline) guarding the inner block. This is the source-order
        # invariant that prevents the misleading message from firing on
        # unrelated failures.
        lines = bin_debrief_text.splitlines()
        create_line_idx = next(
            (
                i
                for i, line in enumerate(lines)
                if 'conda env create -f "${CLAUDE_PLUGIN_ROOT}/environment.yml" -n debrief'
                in line
            ),
            None,
        )
        assert create_line_idx is not None, "conda env create call missing from bin/debrief."
        partial_msg_line_idx = next(
            (
                i
                for i, line in enumerate(lines)
                if "Partial debrief env exists and could not be removed automatically."
                in line
            ),
            None,
        )
        assert partial_msg_line_idx is not None, "Partial-env message missing."
        assert partial_msg_line_idx > create_line_idx, (
            "Partial-env message must appear after the create call in source order."
        )
        guard_slice = lines[create_line_idx:partial_msg_line_idx]
        guard_text = "\n".join(guard_slice)
        assert "grep -qx debrief" in guard_text, (
            "BC-1.16b: the env existence guard `grep -qx debrief` must appear "
            "between `conda env create` and the partial-env error message."
        )
        assert "conda env list" in guard_text, (
            "BC-1.16b: the env existence check must use `conda env list`."
        )
