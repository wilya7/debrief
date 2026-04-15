# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-21.

BUG-AUDIT-21 hardens `/debrief:handout` against four independent
defects that were all masked by fully-mocked unit tests in
`tests/unit_11/test_utility_skills.py`:

1. Hard crash on fresh projects — `main_handout` read
   `deck_state.presentations[-1]` without guarding the empty list.
   The fix decouples handout from `/debrief:export`: output goes
   to `output/handouts/handout_v{NNN}.pdf` with `NNN` derived by
   scanning the directory (max existing + 1), independent of
   `deck_state.presentations`.

2. REQ-HAND-5 spec↔code drift on styling — spec mandated
   `assets/style.css`, code used hardcoded inline CSS. Resolved
   in favor of Option B (dedicated `handout.css`) via BC-11.15;
   the stylesheet is now a first-class document beside the
   handout module.

3. Backup slide leakage — the approved-slide filter did not
   check `SlideRecord.backup`, so archived prior versions with
   `status == "approved"` contaminated the handout. Fixed by
   adding `and not s.backup` to the filter.

4. Mocked tests that catch no regressions — `TestMainHandoutVersionNumbering`
   patched `playwright.sync_api.sync_playwright` with `MagicMock`
   and relied on a production `out_path.touch()` to make
   `expected.exists()` pass. Zero bytes of real PDF were ever
   written by any test. This file adds a load-bearing
   integration test (`TestHandoutDecoupledFromExport`) that
   launches real Chromium via Playwright and asserts the
   generated PDF exists and begins with the `%PDF` magic bytes.
   Faster tests in the other three classes use targeted mocks
   that still exercise the code paths they claim to cover.

TEST CLASSES:

1. TestHandoutDecoupledFromExport — load-bearing real-PDF test.
   Synthetic project with approved slides but empty
   `presentations` list. Calls `main_handout("2up", root)` and
   asserts (a) exit succeeds, (b) `output/handouts/handout_v001.pdf`
   exists, (c) the file starts with `%PDF` magic bytes, (d) the
   file size is above a trivial threshold (real PDF bytes, not
   an empty placeholder).

2. TestHandoutExcludesBackupSlides — fast filter test. Uses a
   `generate_layout_html` spy to capture the slide list actually
   passed to the renderer and asserts only non-backup approved
   slides appear.

3. TestHandoutPreconditionsFailFast — fast error-path tests.
   Asserts exit code 2 with descriptive messages for (a) missing
   `deck_state.json`, (b) no approved slides, (c) only-backup
   approved slides. Uses a Playwright find_spec sentinel to
   verify the environment check is never reached on precondition
   failure.

4. TestHandoutVersionNumberingDecoupled — fast versioning test.
   Mocks `page.pdf()` to write a fake PDF byte payload so the
   file exists without launching real Chromium. Asserts consecutive
   invocations produce `handout_v001.pdf`, `handout_v002.pdf`,
   `handout_v003.pdf` in `output/handouts/` and that no other
   state mutation occurs (no writes to `deck_state.json`).

All tests run unconditionally in both workspace and delivered
layouts via the sibling-discovery path pattern established in
`test_bug_audit_20_orphan_audit.py`; zero skips.

See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-21 and
blueprint contracts BC-11.15, BC-11.16, BC-11.17.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution, mirroring BUG-AUDIT-20's pattern so the
# same test file runs unchanged in workspace and delivered layouts.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_11").is_dir()


def _utility_skills_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_11"
    return _PROJECT_ROOT / "src" / "debrief"


def _debrief_state_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_2"
    return _PROJECT_ROOT / "src" / "debrief"


# Prep sys.path so `import utility_skills` / `import debrief_state` work
# in either layout.
for _dir in (_debrief_state_module_dir(), _utility_skills_module_dir()):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

import utility_skills  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic-project fixture helpers.
# ---------------------------------------------------------------------------

_TS = "2026-04-15T12:00:00Z"


def _slide_dict(
    slug: str,
    *,
    status: str = "approved",
    backup: bool = False,
    title: Optional[str] = None,
    content_summary: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "slug": slug,
        "title": title or f"Title of {slug}",
        "status": status,
        "backup": backup,
        "content_summary": content_summary or f"Summary for {slug}",
        "visual_approach": "Diagram",
        "design_choices": "Minimal",
        "forks_not_taken": None,
        "user_recommendations": None,
        "qa_passed": True,
        "accepted_violations": [],
        "last_modified": _TS,
        "group_id": "group_01",
        "user_assets": [],
        "has_math": False,
    }


def _write_minimal_deck_state(
    project_root: Path,
    slides: list[dict[str, Any]],
    *,
    presentations: Optional[list[dict[str, Any]]] = None,
) -> None:
    data = {
        "project_name": "bug_audit_21_test",
        "created_at": _TS,
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": slides,
        "presentations": presentations if presentations is not None else [],
    }
    (project_root / "deck_state.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Fake PDF writer — used by the faster tests that don't need real Chromium.
# Writes the minimal bytes of a valid PDF so the file is inspectable.
# ---------------------------------------------------------------------------

_FAKE_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Count 0 /Kids [] >>\nendobj\n"
    b"xref\n0 3\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n"
    b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n100\n%%EOF\n"
)


def _fake_playwright_context(captured_paths: list[Path]):
    """Return a context-manager mock for sync_playwright() whose
    page.pdf(path=...) writes _FAKE_PDF_BYTES to the requested path
    AND records the path into `captured_paths`.
    """

    def _fake_page_pdf(path: str) -> None:
        p = Path(path)
        p.write_bytes(_FAKE_PDF_BYTES)
        captured_paths.append(p)

    mock_page = MagicMock()
    mock_page.pdf.side_effect = _fake_page_pdf
    mock_page.goto = MagicMock()

    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page
    mock_browser.close = MagicMock()

    mock_pw = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_pw)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    mock_sync_playwright = MagicMock(return_value=mock_ctx)
    return mock_sync_playwright


# ===========================================================================
# TestHandoutDecoupledFromExport — load-bearing real-PDF integration test.
# ===========================================================================


class TestHandoutDecoupledFromExport:
    """BC-11.17: handout is independent of /debrief:export.

    Real Playwright test. Launches actual Chromium via
    ``playwright.sync_api.sync_playwright()`` and renders a real PDF.
    This is the load-bearing test that BUG-AUDIT-21 was specifically
    designed to add — it would have failed on the IndexError pre-fix
    AND on a Playwright-broken environment, which the mocked unit
    tests cannot detect.
    """

    def test_handout_succeeds_with_empty_presentations_list(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.17: a project with approved slides and empty
        presentations[] must produce a real handout PDF at
        output/handouts/handout_v001.pdf.
        """
        _write_minimal_deck_state(
            tmp_path,
            slides=[
                _slide_dict("intro"),
                _slide_dict("methods"),
                _slide_dict("results"),
            ],
            presentations=[],  # no exports yet — the decoupling case
        )

        utility_skills.main_handout("2up", tmp_path)

        expected_path = tmp_path / "output" / "handouts" / "handout_v001.pdf"
        assert expected_path.is_file(), (
            f"BC-11.17: handout must be written to {expected_path} but "
            f"nothing is there. Contents of output/: "
            f"{list((tmp_path / 'output').rglob('*'))}"
        )

    def test_real_pdf_file_has_pdf_magic_bytes(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.16 / BC-11.17: the rendered file must be a real PDF,
        not an empty placeholder. Asserts the file begins with the
        %PDF magic header. This would have failed pre-fix because the
        old ``out_path.touch()`` hack produced a zero-byte file.
        """
        _write_minimal_deck_state(
            tmp_path,
            slides=[_slide_dict("only_slide")],
            presentations=[],
        )

        utility_skills.main_handout("2up", tmp_path)

        expected_path = tmp_path / "output" / "handouts" / "handout_v001.pdf"
        raw = expected_path.read_bytes()
        assert raw.startswith(b"%PDF"), (
            f"BC-11.17: handout output must begin with %PDF magic "
            f"bytes, got first 16 bytes = {raw[:16]!r}"
        )

    def test_real_pdf_file_has_non_trivial_size(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.17: real PDF must be substantially larger than a
        zero-byte ``touch``. The exact minimum depends on Playwright's
        Chromium output, but any valid PDF with even one blank page
        is well above 1024 bytes.
        """
        _write_minimal_deck_state(
            tmp_path,
            slides=[_slide_dict("one")],
            presentations=[],
        )

        utility_skills.main_handout("2up", tmp_path)

        expected_path = tmp_path / "output" / "handouts" / "handout_v001.pdf"
        size = expected_path.stat().st_size
        assert size > 1024, (
            f"BC-11.17: real PDF expected > 1024 bytes (a zero-byte "
            f"touch hack would have produced 0). Got {size} bytes. "
            f"This usually means Playwright failed to render or the "
            f"old touch() hack is still in main_handout."
        )

    def test_output_handouts_directory_created_on_first_run(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.17: the ``output/handouts/`` directory is created on
        first invocation via ``mkdir(parents=True, exist_ok=True)``.
        A caller should not have to create it beforehand.
        """
        _write_minimal_deck_state(
            tmp_path,
            slides=[_slide_dict("one")],
            presentations=[],
        )

        assert not (tmp_path / "output" / "handouts").exists()
        utility_skills.main_handout("2up", tmp_path)
        assert (tmp_path / "output" / "handouts").is_dir()

    def test_deck_state_json_is_not_mutated(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.17: versioning is filesystem-derived, so the
        handout run must NOT write ``deck_state.json``. Asserts the
        file's content hash is identical before and after.
        """
        _write_minimal_deck_state(
            tmp_path,
            slides=[_slide_dict("one")],
            presentations=[],
        )
        state_path = tmp_path / "deck_state.json"
        before = state_path.read_bytes()

        utility_skills.main_handout("2up", tmp_path)

        after = state_path.read_bytes()
        assert before == after, (
            "BC-11.17: handout must not mutate deck_state.json "
            "because versioning is filesystem-derived."
        )


# ===========================================================================
# TestHandoutExcludesBackupSlides — fast filter test via layout spy.
# ===========================================================================


class TestHandoutExcludesBackupSlides:
    """BC-11.15 / BC-11.16: approved-slide filter must exclude
    backup slides even when their status field says 'approved'.
    """

    def _spy_on_layout(self) -> tuple[Any, list[list[Any]]]:
        """Return (patched_generate_layout_html, captured_slide_lists).

        The spy calls the real function but records every slide list
        it was called with so tests can assert on filter behavior
        without coupling to the rendered HTML text.
        """
        captured: list[list[Any]] = []
        real_fn = utility_skills.generate_layout_html

        def _spy(mode: str, slides: list[Any], project_root: Path) -> str:
            captured.append(list(slides))
            return real_fn(mode, slides, project_root)

        return _spy, captured

    def test_backup_slides_filtered_out_even_when_approved(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.16 step (2): ``s.backup == True`` slides are
        excluded even if their ``status == 'approved'``.
        """
        _write_minimal_deck_state(
            tmp_path,
            slides=[
                _slide_dict("live_1"),
                _slide_dict("backup_old", backup=True),
                _slide_dict("live_2"),
                _slide_dict("backup_older", backup=True),
            ],
            presentations=[],
        )

        spy, captured = self._spy_on_layout()
        captured_paths: list[Path] = []

        with patch.object(utility_skills, "generate_layout_html", spy):
            with patch(
                "playwright.sync_api.sync_playwright",
                _fake_playwright_context(captured_paths),
            ):
                utility_skills.main_handout("2up", tmp_path)

        assert len(captured) == 1, (
            f"Expected one call to generate_layout_html, got "
            f"{len(captured)}"
        )
        slugs_passed = [s.slug for s in captured[0]]
        assert slugs_passed == ["live_1", "live_2"], (
            f"BC-11.16: backup slides must be filtered out. Passed "
            f"slugs: {slugs_passed} (expected ['live_1', 'live_2'])"
        )

    def test_draft_slides_filtered_out(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.16 step (2): ``status != 'approved'`` slides are
        always excluded regardless of backup flag.
        """
        _write_minimal_deck_state(
            tmp_path,
            slides=[
                _slide_dict("approved_1"),
                _slide_dict("draft_1", status="draft"),
                _slide_dict("needs_revision_1", status="needs_revision"),
                _slide_dict("discarded_1", status="discarded"),
                _slide_dict("approved_2"),
            ],
            presentations=[],
        )

        spy, captured = self._spy_on_layout()
        captured_paths: list[Path] = []

        with patch.object(utility_skills, "generate_layout_html", spy):
            with patch(
                "playwright.sync_api.sync_playwright",
                _fake_playwright_context(captured_paths),
            ):
                utility_skills.main_handout("2up", tmp_path)

        slugs_passed = [s.slug for s in captured[0]]
        assert slugs_passed == ["approved_1", "approved_2"], (
            f"Non-approved statuses must be filtered. Got: {slugs_passed}"
        )


# ===========================================================================
# TestHandoutPreconditionsFailFast — error-path tests.
# ===========================================================================


class TestHandoutPreconditionsFailFast:
    """BC-11.16: each precondition failure path must produce a
    descriptive stderr message and exit code 2, WITHOUT reaching
    the Playwright environment check.
    """

    def _install_find_spec_sentinel(self) -> Any:
        """Return a patch context-manager whose ``find_spec`` raises
        AssertionError if called. Used to verify that the playwright
        check is not reached on pure-precondition failure paths.
        """
        real_find_spec = importlib.util.find_spec

        def _guarded(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "playwright":
                raise AssertionError(
                    "BC-11.16: precondition failure paths must NOT "
                    "reach the playwright find_spec check. The "
                    "preconditions are ordered so missing-project / "
                    "missing-slides runs produce accurate messages, "
                    "not environment-corruption warnings."
                )
            return real_find_spec(name, *args, **kwargs)

        return patch("importlib.util.find_spec", side_effect=_guarded)

    def test_missing_deck_state_exits_2_with_message(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """BC-11.16 step (1): missing deck_state.json → exit 2 with
        a message that names the missing file.
        """
        # tmp_path is empty; no deck_state.json written.
        with self._install_find_spec_sentinel():
            with pytest.raises(SystemExit) as exc_info:
                utility_skills.main_handout("2up", tmp_path)
        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        msg = (captured.out + captured.err).lower()
        assert any(
            tok in msg
            for tok in ("deck_state.json", "no project", "debrief new")
        ), f"Missing-project message not found in stderr. Got: {msg!r}"

    def test_no_approved_slides_exits_2_with_message(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """BC-11.16 step (2): project with only draft slides → exit 2
        with a message that names the missing prerequisite.
        """
        _write_minimal_deck_state(
            tmp_path,
            slides=[
                _slide_dict("draft_1", status="draft"),
                _slide_dict("draft_2", status="draft"),
            ],
            presentations=[],
        )

        with self._install_find_spec_sentinel():
            with pytest.raises(SystemExit) as exc_info:
                utility_skills.main_handout("2up", tmp_path)
        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        msg = (captured.out + captured.err).lower()
        assert "approved" in msg, (
            f"No-approved-slides message should mention 'approved'. "
            f"Got: {msg}"
        )

    def test_only_backup_approved_slides_exits_2(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """BC-11.16 step (2): a project where the ONLY approved
        slides are backups must still fail fast — backups are
        filtered out even though they have ``status == 'approved'``.
        """
        _write_minimal_deck_state(
            tmp_path,
            slides=[
                _slide_dict("backup_1", backup=True),
                _slide_dict("backup_2", backup=True),
                _slide_dict("draft_1", status="draft"),
            ],
            presentations=[],
        )

        with self._install_find_spec_sentinel():
            with pytest.raises(SystemExit) as exc_info:
                utility_skills.main_handout("2up", tmp_path)
        assert exc_info.value.code == 2


# ===========================================================================
# TestHandoutVersionNumberingDecoupled — filesystem-derived versioning.
# ===========================================================================


class TestHandoutVersionNumberingDecoupled:
    """BC-11.17: handout version numbering is derived from scanning
    ``output/handouts/`` for existing ``handout_v*.pdf`` files. No
    state field is read or written.
    """

    def test_first_handout_is_v001(
        self,
        tmp_path: Path,
    ) -> None:
        """Fresh project: first handout is ``handout_v001.pdf``."""
        _write_minimal_deck_state(
            tmp_path,
            slides=[_slide_dict("one")],
            presentations=[],
        )

        captured_paths: list[Path] = []
        with patch(
            "playwright.sync_api.sync_playwright",
            _fake_playwright_context(captured_paths),
        ):
            utility_skills.main_handout("2up", tmp_path)

        assert (tmp_path / "output" / "handouts" / "handout_v001.pdf").is_file()

    def test_second_handout_increments_to_v002(
        self,
        tmp_path: Path,
    ) -> None:
        """Two consecutive runs produce v001 and v002."""
        _write_minimal_deck_state(
            tmp_path,
            slides=[_slide_dict("one")],
            presentations=[],
        )

        captured_paths: list[Path] = []
        fake_ctx_factory = _fake_playwright_context(captured_paths)
        with patch("playwright.sync_api.sync_playwright", fake_ctx_factory):
            utility_skills.main_handout("2up", tmp_path)
            utility_skills.main_handout("2up", tmp_path)

        assert (tmp_path / "output" / "handouts" / "handout_v001.pdf").is_file()
        assert (tmp_path / "output" / "handouts" / "handout_v002.pdf").is_file()

    def test_version_derives_from_max_existing_file(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.17 directory-scan rule: if ``handout_v005.pdf``
        already exists (e.g., because the user manually renamed or
        copied files), the next invocation picks v006, not v002.
        """
        _write_minimal_deck_state(
            tmp_path,
            slides=[_slide_dict("one")],
            presentations=[],
        )
        handouts_dir = tmp_path / "output" / "handouts"
        handouts_dir.mkdir(parents=True)
        (handouts_dir / "handout_v005.pdf").write_bytes(_FAKE_PDF_BYTES)

        captured_paths: list[Path] = []
        with patch(
            "playwright.sync_api.sync_playwright",
            _fake_playwright_context(captured_paths),
        ):
            utility_skills.main_handout("2up", tmp_path)

        assert (handouts_dir / "handout_v006.pdf").is_file()
        assert not (handouts_dir / "handout_v002.pdf").exists()

    def test_noise_files_in_handouts_directory_are_ignored(
        self,
        tmp_path: Path,
    ) -> None:
        """BC-11.17: files that don't match the ``handout_v{NNN}.pdf``
        pattern must not affect version derivation. Stray files
        (user notes, README, backups with different names) are
        common; they must not crash or confuse the scanner.
        """
        _write_minimal_deck_state(
            tmp_path,
            slides=[_slide_dict("one")],
            presentations=[],
        )
        handouts_dir = tmp_path / "output" / "handouts"
        handouts_dir.mkdir(parents=True)
        (handouts_dir / "README.txt").write_text("user notes", encoding="utf-8")
        (handouts_dir / "handout_vXYZ.pdf").write_bytes(_FAKE_PDF_BYTES)
        (handouts_dir / "old_handout.pdf").write_bytes(_FAKE_PDF_BYTES)

        captured_paths: list[Path] = []
        with patch(
            "playwright.sync_api.sync_playwright",
            _fake_playwright_context(captured_paths),
        ):
            utility_skills.main_handout("2up", tmp_path)

        # None of the noise files matched handout_v{digits}.pdf,
        # so next version is v001.
        assert (handouts_dir / "handout_v001.pdf").is_file()
