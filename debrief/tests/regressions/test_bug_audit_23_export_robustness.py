# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Regression tests for BUG-AUDIT-23.

BUG-AUDIT-23 hardens ``/debrief:export`` against two CRITICAL defects:

1. Silent data loss when PyMuPDF (fitz) is unavailable — the old code
   caught ImportError and silently wrote only the first PDF page.
   BUG-AUDIT-23 adds a fitz importability check at entry (exit 2) and
   deletes the fallback entirely.

2. State-coupled version numbering via ``export_count`` — replaced with
   filesystem-derived versioning (scan ``output/{folder}/deck_v*.pdf``,
   pick ``max + 1``). Consistent with handout's BC-11.17 approach.

TEST CLASSES:

1. TestExportFitzMissingExits2 — env check: fitz unavailable → exit 2
   with descriptive message. Playwright never launched.
2. TestExportVersionDerivedFromFilesystem — pre-seed version files,
   assert next version is max+1, assert deck_state.json not mutated.
3. TestExportNoSilentFallback — AST sentinel asserting no ``except
   ImportError`` block exists in the merge section of export.py.
"""

from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Dual-layout path resolution.
# ---------------------------------------------------------------------------

_REGRESSIONS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _REGRESSIONS_DIR.parent
_PROJECT_ROOT = _TESTS_DIR.parent


def _is_workspace_layout() -> bool:
    return (_PROJECT_ROOT / "src" / "unit_10").is_dir()


def _export_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_10"
    return _PROJECT_ROOT / "src" / "debrief"


def _debrief_state_module_dir() -> Path:
    if _is_workspace_layout():
        return _PROJECT_ROOT / "src" / "unit_2"
    return _PROJECT_ROOT / "src" / "debrief"


for _dir in (_debrief_state_module_dir(), _export_module_dir()):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

from export import main_export  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture helpers.
# ---------------------------------------------------------------------------

_TS = "2026-04-16T12:00:00Z"
_FOLDER = "2026_04_16_test_deck"


def _slide_dict(slug: str, **kw: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "slug": slug,
        "title": f"Title of {slug}",
        "status": "approved",
        "backup": False,
        "content_summary": f"Summary for {slug}",
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
    defaults.update(kw)
    return defaults


def _presentation_dict(**kw: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "folder": _FOLDER,
        "created_at": _TS,
        "slide_manifest": [],
        "export_count": 0,
        "script_count": 0,
        "handout_count": 0,
        "separator_position": None,
        "separator_content": None,
    }
    defaults.update(kw)
    return defaults


def _setup_export_project(
    root: Path,
    *,
    slides: Optional[list[dict[str, Any]]] = None,
    presentations: Optional[list[dict[str, Any]]] = None,
) -> None:
    """Create a minimal project that main_export can run against.

    Creates deck_state.json, style_config.json, assets/style.css (via
    a trivial compiler mock), and slide HTML files under slides/.
    """
    if slides is None:
        slides = [_slide_dict("intro"), _slide_dict("methods")]
    if presentations is None:
        presentations = [_presentation_dict()]

    state = {
        "project_name": "bug_audit_23_test",
        "created_at": _TS,
        "archetype": "lab_meeting",
        "style_locked": True,
        "closing_slide": None,
        "slides": slides,
        "presentations": presentations,
    }
    (root / "deck_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )

    # Minimal style_config.json
    style_config = {
        "colors": {"primary": "#000000", "background": "#ffffff",
                    "text": "#111111", "accent": "#0066cc",
                    "secondary_bg": "#f5f5f5", "border": "#cccccc"},
        "typography": {"heading_font": "sans-serif", "body_font": "sans-serif",
                        "base_size": "16px", "heading_weight": "700",
                        "body_weight": "400", "line_height": "1.5"},
        "spacing": {"slide_padding": "40px", "element_gap": "20px",
                     "section_gap": "32px"},
        "layout": {"slide_width": 1920, "slide_height": 1080,
                    "max_content_width": "1600px", "grid_columns": 12},
        "data_viz": {"chart_font": "sans-serif", "axis_color": "#333333",
                      "grid_color": "#eeeeee"},
        "constraints": {},
        "provenance": {},
    }
    (root / "style_config.json").write_text(
        json.dumps(style_config), encoding="utf-8"
    )

    # Create slide HTML files and assets/style.css
    slides_dir = root / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    for s in slides:
        (slides_dir / f"{s['slug']}.html").write_text(
            f"<!DOCTYPE html><html><head><link rel='stylesheet' "
            f"href='../assets/style.css'></head><body>"
            f"<h1>{s['title']}</h1></body></html>",
            encoding="utf-8",
        )

    assets_dir = root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "style.css").write_text(
        "body { font-family: sans-serif; }", encoding="utf-8"
    )


# ===========================================================================
# TestExportFitzMissingExits2
# ===========================================================================


class TestExportFitzMissingExits2:
    """BUG-AUDIT-23: missing fitz (PyMuPDF) must exit 2 at entry."""

    def test_fitz_unavailable_exits_2(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        _setup_export_project(tmp_path)

        _real_find_spec = importlib.util.find_spec

        def _no_fitz(name: str, *a: Any, **kw: Any) -> Any:
            if name == "fitz":
                return None
            return _real_find_spec(name, *a, **kw)

        with patch("importlib.util.find_spec", side_effect=_no_fitz):
            # Also patch subprocess so the style compiler doesn't run
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                with pytest.raises(SystemExit) as exc_info:
                    main_export(tmp_path)

        assert exc_info.value.code == 2
        msg = capsys.readouterr().err.lower()
        assert "pymupdf" in msg or "fitz" in msg

    def test_fitz_unavailable_message_mentions_rebuild_env(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        _setup_export_project(tmp_path)

        _real_find_spec = importlib.util.find_spec

        def _no_fitz(name: str, *a: Any, **kw: Any) -> Any:
            if name == "fitz":
                return None
            return _real_find_spec(name, *a, **kw)

        with patch("importlib.util.find_spec", side_effect=_no_fitz):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                with pytest.raises(SystemExit):
                    main_export(tmp_path)

        msg = capsys.readouterr().err.lower()
        assert "rebuild" in msg or "rebuild-env" in msg


# ===========================================================================
# TestExportVersionDerivedFromFilesystem
# ===========================================================================


class TestExportVersionDerivedFromFilesystem:
    """BUG-AUDIT-23 / BC-10.4: version number derived from dir scan."""

    def _run_export_with_mock_playwright(self, root: Path) -> None:
        """Run main_export with mocked playwright + mocked fitz merge.

        Uses sys.modules patching (same pattern as the existing
        test_export.py mocks) because export.py imports playwright
        and fitz locally inside the function body.
        """

        def _fake_page_pdf(**kwargs: Any) -> bytes:
            return (
                b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\n"
                b"endobj\n2 0 obj\n<< /Type /Pages /Count 0 /Kids [] >>\n"
                b"endobj\nxref\n0 3\ntrailer\n<< /Root 1 0 R >>\n"
                b"startxref\n0\n%%EOF\n"
            )

        mock_page = MagicMock()
        mock_page.pdf.side_effect = _fake_page_pdf
        mock_page.goto = MagicMock()
        mock_page.close = MagicMock()

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_context.close = MagicMock()

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_browser.close = MagicMock()

        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser

        mock_sync_ctx = MagicMock()
        mock_sync_ctx.__enter__ = MagicMock(return_value=mock_pw)
        mock_sync_ctx.__exit__ = MagicMock(return_value=False)

        mock_sync_fn = MagicMock(return_value=mock_sync_ctx)

        mock_fitz_doc = MagicMock()
        mock_fitz_doc.__enter__ = MagicMock(return_value=mock_fitz_doc)
        mock_fitz_doc.__exit__ = MagicMock(return_value=False)
        mock_merged = MagicMock()
        mock_merged.save.side_effect = lambda path: Path(path).write_bytes(
            b"%PDF-1.4 merged mock content placeholder bytes"
        )
        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = lambda **kw: (
            mock_fitz_doc if "stream" in kw else mock_merged
        )

        with (
            patch("subprocess.run", return_value=MagicMock(returncode=0, stderr="")),
            patch("importlib.util.find_spec", return_value=MagicMock()),
            patch.dict(
                "sys.modules",
                {
                    "playwright": MagicMock(),
                    "playwright.sync_api": MagicMock(
                        sync_playwright=mock_sync_fn
                    ),
                    "fitz": mock_fitz,
                },
            ),
        ):
            main_export(root)

    def test_first_export_creates_v001(self, tmp_path: Path) -> None:
        _setup_export_project(tmp_path)
        self._run_export_with_mock_playwright(tmp_path)
        expected = tmp_path / "output" / _FOLDER / "deck_v001.pdf"
        assert expected.is_file()

    def test_preexisting_v003_yields_v004(self, tmp_path: Path) -> None:
        _setup_export_project(tmp_path)
        out_dir = tmp_path / "output" / _FOLDER
        out_dir.mkdir(parents=True)
        (out_dir / "deck_v003.pdf").write_bytes(b"%PDF-stub")

        self._run_export_with_mock_playwright(tmp_path)
        assert (out_dir / "deck_v004.pdf").is_file()
        assert not (out_dir / "deck_v001.pdf").exists()

    def test_deck_state_version_fields_not_mutated(self, tmp_path: Path) -> None:
        """BUG-AUDIT-23 intent: `export_count` and `folder` MUST NOT change
        on export. Version numbering is filesystem-derived (BC-10.4), so
        export has no business bumping counters. Note: BUG-AUDIT-60 /
        BUG-ST-xp-2 added a narrow refresh to `slide_manifest` so that
        re-exports reflect the live approved-slug list — that is a
        manifest refresh, not a version mutation, and is permitted.
        """
        import json as _json

        _setup_export_project(tmp_path)
        state_path = tmp_path / "deck_state.json"
        before = _json.loads(state_path.read_text(encoding="utf-8"))

        self._run_export_with_mock_playwright(tmp_path)

        after = _json.loads(state_path.read_text(encoding="utf-8"))

        # Version-related fields must be unchanged (BUG-AUDIT-23)
        for i, (bp, ap) in enumerate(
            zip(before["presentations"], after["presentations"])
        ):
            assert bp["folder"] == ap["folder"], (
                f"presentation[{i}].folder changed: "
                f"{bp['folder']!r} → {ap['folder']!r}"
            )
            assert bp["export_count"] == ap["export_count"], (
                f"presentation[{i}].export_count changed: "
                f"{bp['export_count']} → {ap['export_count']} "
                "(BUG-AUDIT-23: filesystem-derived versioning)"
            )
            assert bp["script_count"] == ap["script_count"]
            assert bp["handout_count"] == ap["handout_count"]

        # Slides list must not have gained/lost entries
        assert len(before["slides"]) == len(after["slides"])


# ===========================================================================
# TestExportNoSilentFallback — AST sentinel
# ===========================================================================


class TestExportNoSilentFallback:
    """BUG-AUDIT-23: assert no ``except ImportError`` block in the
    merge section of export.py. Prevents re-introduction of the
    silent single-page fallback.
    """

    def test_no_except_import_error_in_export_py(self) -> None:
        export_path = _export_module_dir() / "export.py"
        source = export_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(export_path))

        import_error_handlers: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is not None:
                    if isinstance(node.type, ast.Name) and node.type.id == "ImportError":
                        import_error_handlers.append(node.lineno)

        assert not import_error_handlers, (
            f"BUG-AUDIT-23: export.py must not contain 'except "
            f"ImportError' handlers (silent fallback risk). Found at "
            f"line(s): {import_error_handlers}. If a new dependency "
            f"needs a fallback, add a fail-fast check at function "
            f"entry instead."
        )
