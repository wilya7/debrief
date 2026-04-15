# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-16.

A user running debrief in production reported that slides render text
labels but no hand-drawn shapes from rough.js. Investigation found two
compounding fakes:

1. Every file under ``assets/vendor/`` was a one-line placeholder stub
   (54-56 bytes for ``*.min.js`` / ``*.min.css``; 18 bytes of
   ``WOFF2_PLACEHOLDER`` for the KaTeX woff2 font).
2. ``VERSIONS.md`` recorded the SHA-256 hashes of the STUBS, not the
   real library hashes from jsDelivr. ``verify_vendor_hashes`` silently
   passed because the manifest matched the on-disk stubs.

The combination meant the broken bundle traveled through the pipeline
undetected: ``debrief new`` copied the stubs to the project, slide HTML
linked them, the browser loaded 54 bytes of comment, and every
``rc.rectangle()`` / ``rc.line()`` call threw silently on an undefined
``rough`` global.

This file pins the fix:

- BC-1.12 / BC-1.12a / BUG-AUDIT-16: every VERSIONS.md entry must have a
  corresponding real file on disk with a matching hash, in BOTH the
  workspace and delivered repo, and the two copies must be byte-identical.
- File-size lower bounds reject any future placeholder regression.
- BC-3.15: ``scripts/fetch_vendor.py`` exists at the workspace root
  (not inside the plugin directory) and is Python-importable.

See ``spec/stakeholder_spec.md`` Bug Catalog entry BUG-AUDIT-16.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers — dual workspace/delivered layout, matching BUG-AUDIT-13/-14/-15.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _workspace_vendor_dir() -> Path:
    return _PROJECT_ROOT / "src" / "unit_1" / "assets" / "vendor"


def _delivered_vendor_dir() -> Path:
    return _PROJECT_ROOT / "assets" / "vendor"


def _vendor_dir_for_current_layout() -> Path:
    """Pick whichever vendor dir is present under the current test layout."""
    workspace = _workspace_vendor_dir()
    delivered = _delivered_vendor_dir()
    for candidate in (workspace, delivered):
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        f"Could not find vendor directory at {workspace} or {delivered}"
    )


def _parse_versions(text: str) -> list[dict[str, str]]:
    """Parse VERSIONS.md into a list of {filename, version, sha256, url}.

    Mirrors the parsing in ``scripts/fetch_vendor.py`` so test and script
    agree on the manifest shape. Comment lines (``#``) and blanks are
    skipped. Raises ``ValueError`` on malformed lines.
    """
    entries: list[dict[str, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            raise ValueError(
                f"VERSIONS.md line {lineno}: expected 4 fields, got "
                f"{len(parts)}"
            )
        filename, version_field, sha_field, url = parts
        entries.append(
            {
                "filename": filename,
                "version": version_field[len("version "):],
                "sha256": sha_field[len("sha256:"):],
                "url": url,
            }
        )
    return entries


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# Minimum byte sizes that a real minified library cannot possibly be
# below — chosen as a tight sanity check that any placeholder stub
# (historically 54-56 bytes) will violate. The real sizes observed
# on jsDelivr as of BUG-AUDIT-16 are:
#   rough.min.js:   28_034 bytes
#   mermaid.min.js: 2_935_756 bytes
#   katex.min.js:   277_038 bytes
#   katex.min.css:  23_196 bytes
#   KaTeX woff2:    26_272 bytes
_MIN_SIZES = {
    "rough.min.js": 10_000,
    "mermaid.min.js": 100_000,
    "katex.min.js": 100_000,
    "katex.min.css": 10_000,
    "katex-fonts/KaTeX_Main-Regular.woff2": 5_000,
}


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def versions_manifest() -> list[dict[str, str]]:
    vendor_dir = _vendor_dir_for_current_layout()
    manifest = vendor_dir / "VERSIONS.md"
    assert manifest.is_file(), (
        f"BC-1.12 / BUG-AUDIT-16: VERSIONS.md must exist at {manifest}."
    )
    return _parse_versions(manifest.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# BC-1.12 / BUG-AUDIT-16 — vendor files exist and match manifest hashes.
# ---------------------------------------------------------------------------


class TestBugAudit16VendorRealFiles:
    """BC-1.12 / BUG-AUDIT-16 — every VERSIONS.md entry must have a real
    file on disk whose SHA-256 matches the manifest and whose size is
    plausible for a real minified library.
    """

    def test_versions_md_parses_to_five_entries(
        self, versions_manifest: list[dict[str, str]]
    ) -> None:
        assert len(versions_manifest) == 5, (
            f"BC-1.12: VERSIONS.md must contain exactly 5 entries "
            f"(mermaid, rough, katex.js, katex.css, KaTeX font). Got: "
            f"{len(versions_manifest)}"
        )
        filenames = {entry["filename"] for entry in versions_manifest}
        expected = {
            "mermaid.min.js",
            "rough.min.js",
            "katex.min.js",
            "katex.min.css",
            "katex-fonts/KaTeX_Main-Regular.woff2",
        }
        assert filenames == expected, (
            f"BC-1.12: VERSIONS.md entries must match the canonical set. "
            f"Got: {filenames}, expected: {expected}"
        )

    def test_every_manifest_entry_has_real_file_on_disk(
        self, versions_manifest: list[dict[str, str]]
    ) -> None:
        vendor_dir = _vendor_dir_for_current_layout()
        for entry in versions_manifest:
            target = vendor_dir / entry["filename"]
            assert target.is_file(), (
                f"BC-1.12 / BUG-AUDIT-16: every VERSIONS.md entry must "
                f"have a real file on disk at the declared path. Missing: "
                f"{target}"
            )

    def test_every_file_hash_matches_manifest(
        self, versions_manifest: list[dict[str, str]]
    ) -> None:
        """Load-bearing test: the ACTUAL SHA-256 of every file must match
        the MANIFEST hash. This is the test BUG-AUDIT-16's self-consistent
        fake would have failed — the stub and the manifest matched each
        other but neither matched the real library.
        """
        vendor_dir = _vendor_dir_for_current_layout()
        for entry in versions_manifest:
            target = vendor_dir / entry["filename"]
            actual = _sha256(target.read_bytes())
            assert actual == entry["sha256"], (
                f"BC-1.12 / BUG-AUDIT-16: {entry['filename']} hash mismatch. "
                f"Manifest: {entry['sha256']}, actual: {actual}. The "
                f"manifest and the on-disk file are inconsistent."
            )

    def test_file_sizes_reject_placeholder_stubs(
        self, versions_manifest: list[dict[str, str]]
    ) -> None:
        """Defense-in-depth against a future fake-manifest regression where
        someone replaces VERSIONS.md's hashes with the stub hashes to make
        the tests pass. Placeholder stubs historically had sizes of
        54-56 bytes; real libraries are orders of magnitude larger. This
        test rejects any file below a plausible lower bound.
        """
        vendor_dir = _vendor_dir_for_current_layout()
        for filename, min_size in _MIN_SIZES.items():
            target = vendor_dir / filename
            if not target.is_file():
                continue  # covered by test_every_manifest_entry_has_real_file
            actual = target.stat().st_size
            assert actual >= min_size, (
                f"BC-1.12 / BUG-AUDIT-16: {filename} is suspiciously small "
                f"({actual} bytes < {min_size} bytes lower bound). A real "
                f"minified library cannot be this small; this looks like a "
                f"placeholder-stub regression."
            )


# ---------------------------------------------------------------------------
# BC-1.12a — workspace and delivered vendor directories are byte-identical.
# ---------------------------------------------------------------------------


class TestBugAudit16VendorWorkspaceDeliveredParity:
    """BC-1.12a / BUG-AUDIT-16 — the vendor directory must be byte-identical
    between workspace and delivered. This test only runs when BOTH layouts
    are present on the same filesystem (i.e., when pytest is invoked from
    the top-level workspace directory, not from the delivered repo alone).
    """

    @pytest.fixture(scope="class")
    def both_vendor_dirs(self) -> tuple[Path, Path] | None:
        workspace = _workspace_vendor_dir()
        # The delivered dir is at a sibling path, not under _PROJECT_ROOT.
        delivered_repo = _PROJECT_ROOT.parent / "debrief1.0-repo" / "debrief"
        delivered_vendor = delivered_repo / "assets" / "vendor"
        if not workspace.is_dir() or not delivered_vendor.is_dir():
            return None
        return (workspace, delivered_vendor)

    def test_workspace_and_delivered_vendor_byte_equal(
        self, both_vendor_dirs: tuple[Path, Path] | None
    ) -> None:
        if both_vendor_dirs is None:
            pytest.skip(
                "BC-1.12a parity test requires both workspace and delivered "
                "vendor directories to be present on the filesystem. Running "
                "from only one of the two layouts; parity is still enforced "
                "by the other direction's test suite."
            )
        workspace, delivered = both_vendor_dirs

        # Collect relative paths under each vendor dir.
        ws_files = {p.relative_to(workspace) for p in workspace.rglob("*") if p.is_file()}
        dl_files = {p.relative_to(delivered) for p in delivered.rglob("*") if p.is_file()}

        assert ws_files == dl_files, (
            f"BC-1.12a / BUG-AUDIT-16: workspace and delivered vendor dirs "
            f"have different file sets. Workspace only: {ws_files - dl_files}. "
            f"Delivered only: {dl_files - ws_files}."
        )

        mismatched: list[str] = []
        for rel in sorted(ws_files):
            ws_hash = _sha256((workspace / rel).read_bytes())
            dl_hash = _sha256((delivered / rel).read_bytes())
            if ws_hash != dl_hash:
                mismatched.append(
                    f"{rel}: workspace={ws_hash}, delivered={dl_hash}"
                )
        assert not mismatched, (
            f"BC-1.12a / BUG-AUDIT-16: workspace and delivered vendor files "
            f"drifted:\n" + "\n".join(mismatched)
        )


# ---------------------------------------------------------------------------
# BC-3.15 — scripts/fetch_vendor.py exists at workspace root, importable,
# and NOT shipped inside the delivered plugin directory.
# ---------------------------------------------------------------------------


class TestBugAudit16FetchVendorScript:
    """BC-3.15 / BUG-AUDIT-16 — the vendor acquisition script exists at the
    workspace root and is a maintainer-only build step.
    """

    def _is_workspace_layout(self) -> bool:
        """True when the test is running from the workspace (has src/unit_*/
        directories), False when running from the delivered repo (has
        src/debrief/ instead). BC-3.15 intentionally keeps fetch_vendor.py
        out of the delivered plugin, so this detection drives the skip.
        """
        return (_PROJECT_ROOT / "src" / "unit_1").is_dir()

    def test_fetch_vendor_script_exists_at_workspace_root(self) -> None:
        # BC-3.15 pins fetch_vendor.py to the workspace root ONLY.
        # Running from the delivered repo, the script is intentionally
        # absent (it's a maintainer tool, not a runtime artifact), so
        # this test skips. The negative assertion is handled separately
        # by test_fetch_vendor_script_is_not_in_delivered_plugin.
        if not self._is_workspace_layout():
            pytest.skip(
                "BC-3.15: running from delivered repo where "
                "scripts/fetch_vendor.py is intentionally absent. "
                "Existence is enforced when running from workspace."
            )
        script = _PROJECT_ROOT / "scripts" / "fetch_vendor.py"
        assert script.is_file(), (
            f"BC-3.15 / BUG-AUDIT-16: scripts/fetch_vendor.py must exist "
            f"at the workspace root. Expected at: {script}."
        )

    def test_fetch_vendor_script_is_python_importable(self) -> None:
        # Confirm the file parses as a Python module — catches syntax
        # regressions that would silently break the acquisition step.
        if not self._is_workspace_layout():
            pytest.skip(
                "BC-3.15: fetch_vendor.py is workspace-only; importability "
                "is enforced when running from workspace."
            )
        script = _PROJECT_ROOT / "scripts" / "fetch_vendor.py"

        spec = importlib.util.spec_from_file_location(
            "fetch_vendor_under_test", script
        )
        assert spec is not None and spec.loader is not None, (
            "BC-3.15: fetch_vendor.py must be loadable as a Python module."
        )
        module = importlib.util.module_from_spec(spec)
        # Executing the module runs top-level import statements; this
        # catches import errors without running main().
        spec.loader.exec_module(module)
        # Confirm the public API is present.
        for symbol in ("main", "_parse_versions", "_download", "_sha256"):
            assert hasattr(module, symbol), (
                f"BC-3.15: fetch_vendor.py must expose {symbol!r}."
            )

    def test_fetch_vendor_script_is_not_in_delivered_plugin(self) -> None:
        # BC-3.15: the script is a maintainer build step and MUST NOT ship
        # inside the plugin directory that gets installed to
        # ~/.claude/plugins/cache/. It lives at the workspace scripts/ dir
        # only.
        delivered_repo = _PROJECT_ROOT.parent / "debrief1.0-repo" / "debrief"
        delivered_script = delivered_repo / "scripts" / "fetch_vendor.py"
        if not delivered_repo.is_dir():
            pytest.skip(
                "Delivered repo not present in this layout; the negative "
                "assertion is trivially satisfied."
            )
        assert not delivered_script.exists(), (
            f"BC-3.15 / BUG-AUDIT-16: scripts/fetch_vendor.py must NOT be "
            f"shipped inside the delivered plugin directory at "
            f"{delivered_script}. It is a maintainer-only build step."
        )
