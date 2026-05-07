# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-97.

Bug: `python -m debrief.debrief_state update_slide ...` was documented in
the consultant agent card (BC-5.17 / REQ-CONSULT-SLIDE-WT-1) and the
blueprint, but the subcommand was never implemented in
`src/unit_2/debrief_state.py`'s argparse dispatcher. The consultant followed
the documented protocol and called a phantom CLI; every GREEN-QA slide
registration silently failed, leaving `deck_state.slides[]` empty across
production. `/debrief:view` then branched on the empty array and reported
"no slides yet" despite real `slides/*.html` on disk.

Fix (BC-2.20): implement `cli_update_slide` and register an `update_slide`
argparse subcommand. Contract:
  - --slug required; --project-root defaults to cwd
  - All SlideRecord fields exposed as optional flags; partial-update on
    existing slugs, create-with-defaults on new slugs
  - --title required for creates; rejected with stderr + exit 1 if missing
  - --status validated against {draft, approved, needs_revision, discarded}
  - --accepted-violations and --user-assets parsed as JSON
  - last_modified auto-set to current UTC ISO 8601 timestamp
  - Atomic write via write_deck_state

The tests must pass from both the workspace and the delivered repo.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers (resolve workspace vs delivered repo).
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_2").is_dir()


def _debrief_state_module_path() -> Path:
    """Return the directory that contains debrief_state.py.

    Workspace: ``src/unit_2/debrief_state.py``.
    Delivered repo: ``src/debrief/debrief_state.py`` (package layout).
    """
    workspace_candidate = _PROJECT_ROOT / "src" / "unit_2"
    delivered_candidate = _PROJECT_ROOT / "src" / "debrief"
    if (workspace_candidate / "debrief_state.py").exists():
        return workspace_candidate
    if (delivered_candidate / "debrief_state.py").exists():
        return delivered_candidate
    raise FileNotFoundError(
        "Could not find debrief_state.py in workspace or delivered layout"
    )


def _module_invocation() -> tuple[list[str], dict[str, str]]:
    """Return the argv prefix and env to invoke the CLI in either layout.

    Workspace layout: PYTHONPATH points at ``src/unit_2`` plus ``src/unit_3``
    (because writing deck_state imports from siblings); we invoke
    ``python -m debrief_state ...`` against that path.

    Delivered repo layout: the package is ``debrief.debrief_state``; we
    add ``src`` to PYTHONPATH so the package is importable, then invoke
    ``python -m debrief.debrief_state ...``.
    """
    env = os.environ.copy()
    if _is_workspace_layout():
        unit_2 = _PROJECT_ROOT / "src" / "unit_2"
        unit_3 = _PROJECT_ROOT / "src" / "unit_3"
        path_entries = [str(unit_2), str(unit_3)]
        existing = env.get("PYTHONPATH", "")
        if existing:
            path_entries.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(path_entries)
        argv = [sys.executable, "-m", "debrief_state"]
    else:
        # Delivered repo: package at src/debrief/
        src_root = _PROJECT_ROOT / "src"
        path_entries = [str(src_root)]
        existing = env.get("PYTHONPATH", "")
        if existing:
            path_entries.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(path_entries)
        argv = [sys.executable, "-m", "debrief.debrief_state"]
    return argv, env


def _seed_empty_deck_state(project_root: Path) -> None:
    """Write a minimal valid deck_state.json with an empty slides array."""
    if _is_workspace_layout():
        import_line = "from debrief_state import DeckState, write_deck_state\n"
    else:
        import_line = "from debrief.debrief_state import DeckState, write_deck_state\n"
    seed_script = (
        "from pathlib import Path\n"
        + import_line
        + "state = DeckState(\n"
        "    project_name='regression_test',\n"
        "    created_at='2026-05-07T00:00:00Z',\n"
        "    archetype='journal_club',\n"
        "    style_locked=True,\n"
        "    closing_slide=None,\n"
        "    slides=[],\n"
        "    presentations=[],\n"
        ")\n"
        f"write_deck_state(Path({str(project_root)!r}), state)\n"
    )
    _argv, env = _module_invocation()
    result = subprocess.run(
        [sys.executable, "-c", seed_script],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"seed failed: stdout={result.stdout!r} stderr={result.stderr!r}"
        )


def _read_slides(project_root: Path) -> list[dict]:
    """Return the slides array from deck_state.json as a list of dicts."""
    return json.loads((project_root / "deck_state.json").read_text())["slides"]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    argv, env = _module_invocation()
    return subprocess.run(
        argv + args,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------


class TestBugAudit97SubcommandRegistered:
    """The argparse dispatcher exposes `update_slide` alongside `update`."""

    def test_help_lists_update_slide_subcommand(self) -> None:
        result = _run(["--help"], cwd=Path.cwd())
        assert result.returncode == 0, (
            f"help should exit 0; got {result.returncode}, stderr={result.stderr!r}"
        )
        # The subcommand name must appear in the help output.
        assert "update_slide" in result.stdout, (
            f"`update_slide` subcommand missing from help. stdout={result.stdout!r}"
        )

    def test_invalid_subcommand_no_longer_includes_argparse_choice_error(
        self,
    ) -> None:
        # Pre-fix, calling `update_slide` produced "argparse: invalid
        # choice: 'update_slide' (choose from 'update', 'append_ledger')".
        # Post-fix, the subcommand is registered and at minimum requires
        # --slug; calling with no args should now produce a "--slug
        # required" error, NOT a "choose from" error.
        result = _run(["update_slide"], cwd=Path.cwd())
        assert "invalid choice" not in (result.stdout + result.stderr), (
            f"`update_slide` is still rejected as invalid choice (BUG-AUDIT-97 "
            f"regression). stderr={result.stderr!r}"
        )


class TestBugAudit97CreatePath:
    """Creating a SlideRecord from CLI args."""

    def test_create_with_required_args(self, tmp_path: Path) -> None:
        _seed_empty_deck_state(tmp_path)
        result = _run(
            [
                "update_slide",
                "--slug", "intro",
                "--title", "Introduction",
                "--status", "approved",
                "--qa-passed", "true",
                "--content-summary", "Opening",
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0, (
            f"expected exit 0; got {result.returncode}, "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        slides = _read_slides(tmp_path)
        assert len(slides) == 1
        record = slides[0]
        assert record["slug"] == "intro"
        assert record["title"] == "Introduction"
        assert record["status"] == "approved"
        assert record["qa_passed"] is True
        assert record["content_summary"] == "Opening"
        # Defaults for unset fields:
        assert record["backup"] is False
        assert record["accepted_violations"] == []
        assert record["user_assets"] == []
        assert record["has_math"] is False

    def test_create_without_title_rejected_with_stderr(
        self, tmp_path: Path
    ) -> None:
        _seed_empty_deck_state(tmp_path)
        result = _run(
            [
                "update_slide",
                "--slug", "newslide",
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        assert result.returncode != 0, (
            "create without --title must reject (BC-2.20)"
        )
        assert "title" in result.stderr.lower(), (
            f"stderr should name the missing --title flag; got {result.stderr!r}"
        )
        # Verify no record was written.
        assert _read_slides(tmp_path) == []

    def test_last_modified_auto_set_on_create(self, tmp_path: Path) -> None:
        _seed_empty_deck_state(tmp_path)
        before = datetime.now(timezone.utc)
        result = _run(
            [
                "update_slide",
                "--slug", "intro",
                "--title", "Introduction",
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        after = datetime.now(timezone.utc)
        assert result.returncode == 0
        record = _read_slides(tmp_path)[0]
        last_modified = datetime.fromisoformat(record["last_modified"])
        # Tolerate one-second drift from clock granularity.
        assert before.replace(microsecond=0) <= last_modified <= after, (
            f"last_modified={last_modified} not in [{before}, {after}]"
        )


class TestBugAudit97UpdatePath:
    """Updating an existing SlideRecord preserves untouched fields."""

    def test_partial_update_preserves_other_fields(self, tmp_path: Path) -> None:
        _seed_empty_deck_state(tmp_path)
        # Create
        _run(
            [
                "update_slide",
                "--slug", "intro",
                "--title", "Original",
                "--status", "draft",
                "--content-summary", "First version",
                "--qa-passed", "false",
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        # Partial update: change only status
        result = _run(
            [
                "update_slide",
                "--slug", "intro",
                "--status", "approved",
                "--qa-passed", "true",
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0
        record = _read_slides(tmp_path)[0]
        # Updated fields:
        assert record["status"] == "approved"
        assert record["qa_passed"] is True
        # Preserved fields:
        assert record["title"] == "Original"
        assert record["content_summary"] == "First version"

    def test_last_modified_auto_set_on_update(self, tmp_path: Path) -> None:
        _seed_empty_deck_state(tmp_path)
        _run(
            [
                "update_slide",
                "--slug", "intro",
                "--title", "Original",
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        first_modified = _read_slides(tmp_path)[0]["last_modified"]
        # Sleep briefly to ensure clock progression
        import time
        time.sleep(0.01)
        _run(
            [
                "update_slide",
                "--slug", "intro",
                "--status", "needs_revision",
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        second_modified = _read_slides(tmp_path)[0]["last_modified"]
        assert second_modified > first_modified, (
            f"last_modified should advance on update; "
            f"first={first_modified} second={second_modified}"
        )


class TestBugAudit97Validation:
    """Argument validation rejects malformed inputs."""

    def test_invalid_status_rejected(self, tmp_path: Path) -> None:
        _seed_empty_deck_state(tmp_path)
        result = _run(
            [
                "update_slide",
                "--slug", "intro",
                "--title", "Introduction",
                "--status", "totally_bogus",
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        # Either argparse-level (exit 2) or function-level (exit 1)
        # rejection is acceptable per BC-2.20 — both are non-zero.
        assert result.returncode != 0, "invalid --status must be rejected"
        # Verify no record was created.
        assert _read_slides(tmp_path) == []

    def test_invalid_accepted_violations_json(self, tmp_path: Path) -> None:
        _seed_empty_deck_state(tmp_path)
        result = _run(
            [
                "update_slide",
                "--slug", "intro",
                "--title", "Introduction",
                "--accepted-violations", "not valid json {",
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        assert result.returncode != 0
        assert "json" in result.stderr.lower(), (
            f"stderr should name the JSON parse error; got {result.stderr!r}"
        )
        assert _read_slides(tmp_path) == []

    def test_accepted_violations_must_be_array(self, tmp_path: Path) -> None:
        _seed_empty_deck_state(tmp_path)
        result = _run(
            [
                "update_slide",
                "--slug", "intro",
                "--title", "Introduction",
                "--accepted-violations", '{"not": "an array"}',
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        assert result.returncode != 0
        assert "array" in result.stderr.lower()
        assert _read_slides(tmp_path) == []


class TestBugAudit97JsonFields:
    """JSON-shaped fields are parsed and stored as lists."""

    def test_accepted_violations_stored_as_list(self, tmp_path: Path) -> None:
        _seed_empty_deck_state(tmp_path)
        violations = json.dumps([
            {"invariant": "INV-12", "reason": "Acceptable for this slide"},
        ])
        result = _run(
            [
                "update_slide",
                "--slug", "intro",
                "--title", "Introduction",
                "--accepted-violations", violations,
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        record = _read_slides(tmp_path)[0]
        assert record["accepted_violations"] == [
            {"invariant": "INV-12", "reason": "Acceptable for this slide"},
        ]

    def test_user_assets_stored_as_list(self, tmp_path: Path) -> None:
        _seed_empty_deck_state(tmp_path)
        assets = json.dumps(["assets/images/foo.png", "assets/images/bar.png"])
        result = _run(
            [
                "update_slide",
                "--slug", "intro",
                "--title", "Introduction",
                "--user-assets", assets,
                "--project-root", str(tmp_path),
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        record = _read_slides(tmp_path)[0]
        assert record["user_assets"] == [
            "assets/images/foo.png",
            "assets/images/bar.png",
        ]


class TestBugAudit97Idempotence:
    """Running the same upsert twice produces a stable record."""

    def test_double_create_becomes_update(self, tmp_path: Path) -> None:
        _seed_empty_deck_state(tmp_path)
        for _ in range(2):
            result = _run(
                [
                    "update_slide",
                    "--slug", "intro",
                    "--title", "Introduction",
                    "--status", "approved",
                    "--project-root", str(tmp_path),
                ],
                cwd=tmp_path,
            )
            assert result.returncode == 0, result.stderr
        # Should be exactly one slide, not duplicated.
        slides = _read_slides(tmp_path)
        assert len(slides) == 1
        assert slides[0]["slug"] == "intro"
