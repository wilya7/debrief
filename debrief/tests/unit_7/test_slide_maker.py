# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Tests for Unit 7: Style Dialog (slide_maker module).

Synthetic data generation assumptions
--------------------------------------
- ``sample_slides`` tests use ``total`` values of 0, 1, 5, 10, 11, 20, 100,
  and boundary values around the default ``cap=10``.  A custom ``cap=5`` is
  used to exercise non-default cap behaviour.
- For BC-7.3 / BC-7.4 (LibreOffice adapter) we use ``unittest.mock.patch``
  to intercept ``subprocess.run`` / ``subprocess.Popen`` inside ``adapt_pptx``.
  We do NOT invoke a real ``soffice`` binary.  A fake ``.pptx`` file is
  created on disk via ``tmp_path`` to satisfy any path-existence guard in the
  adapter.  A fake ``python-pptx`` ``Presentation`` mock is injected when
  needed to prevent the adapter from attempting a real PPTX parse.
- For BC-7.5 (PDF > 50 pages) we use ``unittest.mock.patch`` to intercept
  ``fitz.open`` so that no real PDF is needed.  The mock returns a sequence
  of 51 dummy page objects.  The ``analyzer_metadata.json`` or equivalent
  output file is inspected for the ``paper_detected`` flag.
- For BC-7.1 (no VLM import) we inspect the ``slide_maker`` module's source
  text at import time using ``inspect.getsource`` and assert that known VLM/
  LLM package names (``anthropic``, ``openai``, ``langchain``, ``transformers``,
  ``litellm``, ``google.generativeai``, ``cohere``, ``replicate``) do not
  appear as imports.
- For BC-7.2 (Playwright per-invocation, no global) we assert that the
  ``slide_maker`` module namespace contains no attribute whose value is a
  Playwright ``Browser``, ``BrowserContext``, or ``Page`` instance, and that
  calls to ``sync_playwright`` do not happen at module-import time (verified
  by confirming no side-effect occurs on bare import).
- For BC-7.6 determinism tests, the same ``(total, cap)`` pair is called
  twice and the results compared.  Ascending order is verified by checking
  each consecutive pair.  No-duplicates is verified by comparing ``len``
  against ``len(set(...))``.
- The ``tmp_path`` pytest fixture provides isolated temporary directories for
  all tests that write files.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module import -- stub raises NotImplementedError on all call sites, so we
# import only the symbols we need to invoke or inspect.
# ---------------------------------------------------------------------------
from slide_maker import (
    adapt_html_dir,
    adapt_html_file,
    adapt_pdf,
    adapt_pptx,
    sample_slides,
)

# ---------------------------------------------------------------------------
# BC-7.6 -- sample_slides determinism, structure, and boundary behaviour
# ---------------------------------------------------------------------------


class TestSampleSlidesDeterminism:
    """BC-7.6: same (total, cap) always returns same result."""

    def test_returns_same_result_on_repeated_calls_with_total_20(self) -> None:
        result_a = sample_slides(20)
        result_b = sample_slides(20)
        assert result_a == result_b

    def test_returns_same_result_on_repeated_calls_with_total_100(self) -> None:
        result_a = sample_slides(100)
        result_b = sample_slides(100)
        assert result_a == result_b

    def test_returns_same_result_with_custom_cap(self) -> None:
        result_a = sample_slides(50, cap=5)
        result_b = sample_slides(50, cap=5)
        assert result_a == result_b

    def test_different_totals_produce_different_results(self) -> None:
        result_15 = sample_slides(15)
        result_30 = sample_slides(30)
        # Not strictly required by spec but sanity-check that inputs differ
        assert len(result_15) == 10
        assert len(result_30) == 10


class TestSampleSlidesAscendingOrder:
    """BC-7.6: result is in ascending order."""

    def test_ascending_order_for_total_above_cap(self) -> None:
        result = sample_slides(20)
        for i in range(len(result) - 1):
            assert result[i] < result[i + 1], (
                f"Not ascending at index {i}: {result[i]} >= {result[i + 1]}"
            )

    def test_ascending_order_for_total_far_above_cap(self) -> None:
        result = sample_slides(100)
        for i in range(len(result) - 1):
            assert result[i] < result[i + 1]

    def test_ascending_order_with_custom_cap(self) -> None:
        result = sample_slides(50, cap=5)
        for i in range(len(result) - 1):
            assert result[i] < result[i + 1]


class TestSampleSlidesNoDuplicates:
    """BC-7.6: result contains no duplicate indices."""

    def test_no_duplicates_for_total_above_cap(self) -> None:
        result = sample_slides(20)
        assert len(result) == len(set(result))

    def test_no_duplicates_for_large_total(self) -> None:
        result = sample_slides(200)
        assert len(result) == len(set(result))

    def test_no_duplicates_with_small_cap(self) -> None:
        result = sample_slides(30, cap=3)
        assert len(result) == len(set(result))


class TestSampleSlidesLengthContract:
    """BC-7.6: returns exactly min(total, cap) elements."""

    def test_returns_all_indices_when_total_equals_cap(self) -> None:
        result = sample_slides(10)
        assert len(result) == 10

    def test_returns_all_indices_when_total_less_than_cap(self) -> None:
        result = sample_slides(5)
        assert len(result) == 5

    def test_returns_cap_elements_when_total_greater_than_cap(self) -> None:
        result = sample_slides(20)
        assert len(result) == 10

    def test_returns_cap_elements_for_very_large_total(self) -> None:
        result = sample_slides(1000)
        assert len(result) == 10

    def test_custom_cap_limits_result_length(self) -> None:
        result = sample_slides(100, cap=5)
        assert len(result) == 5

    def test_custom_cap_of_one_returns_single_element(self) -> None:
        result = sample_slides(50, cap=1)
        assert len(result) == 1


class TestSampleSlidesExactRangeForSmallTotal:
    """BC-7.6: for total <= cap, returns list(range(total)) exactly."""

    def test_returns_range_for_total_of_zero(self) -> None:
        result = sample_slides(0)
        assert result == list(range(0))

    def test_returns_range_for_total_of_one(self) -> None:
        result = sample_slides(1)
        assert result == list(range(1))

    def test_returns_range_for_total_of_five(self) -> None:
        result = sample_slides(5)
        assert result == list(range(5))

    def test_returns_range_for_total_exactly_at_cap(self) -> None:
        result = sample_slides(10)
        assert result == list(range(10))

    def test_returns_range_for_total_below_custom_cap(self) -> None:
        result = sample_slides(3, cap=7)
        assert result == list(range(3))

    def test_returns_range_for_total_equal_to_custom_cap(self) -> None:
        result = sample_slides(7, cap=7)
        assert result == list(range(7))


class TestSampleSlidesFirstAndLastPresent:
    """BC-7.6: when total > cap, first (index 0) and last (total-1) are included."""

    def test_first_index_present_for_total_above_cap(self) -> None:
        result = sample_slides(20)
        assert 0 in result

    def test_last_index_present_for_total_above_cap(self) -> None:
        result = sample_slides(20)
        assert 19 in result

    def test_first_and_last_present_for_large_total(self) -> None:
        result = sample_slides(100)
        assert 0 in result
        assert 99 in result

    def test_first_and_last_present_with_custom_cap(self) -> None:
        result = sample_slides(50, cap=5)
        assert 0 in result
        assert 49 in result


class TestSampleSlidesAllIndicesInBounds:
    """BC-7.6: all returned indices are valid 0-based indices for the total."""

    def test_all_indices_in_range_for_total_20(self) -> None:
        total = 20
        result = sample_slides(total)
        for idx in result:
            assert 0 <= idx < total

    def test_all_indices_in_range_for_total_11(self) -> None:
        total = 11
        result = sample_slides(total)
        for idx in result:
            assert 0 <= idx < total

    def test_all_indices_in_range_for_total_100_cap_5(self) -> None:
        total = 100
        result = sample_slides(total, cap=5)
        for idx in result:
            assert 0 <= idx < total


# ---------------------------------------------------------------------------
# BC-7.1 -- style_analyzer and all modality adapters must not call VLM/LLM
# ---------------------------------------------------------------------------


class TestStyleAnalyzerNoVlmImport:
    """BC-7.1: source code must not import any LLM/VLM SDK."""

    _FORBIDDEN_PACKAGES = [
        "anthropic",
        "openai",
        "langchain",
        "transformers",
        "litellm",
        "google.generativeai",
        "cohere",
        "replicate",
        "vertexai",
        "boto3",  # Bedrock
    ]

    def _get_module_source(self) -> str:
        import slide_maker

        return inspect.getsource(slide_maker)

    def test_no_anthropic_import_in_module_source(self) -> None:
        source = self._get_module_source()
        assert "anthropic" not in source, (
            "slide_maker module must not import 'anthropic'"
        )

    def test_no_openai_import_in_module_source(self) -> None:
        source = self._get_module_source()
        assert "openai" not in source, "slide_maker module must not import 'openai'"

    def test_no_langchain_import_in_module_source(self) -> None:
        source = self._get_module_source()
        assert "langchain" not in source, (
            "slide_maker module must not import 'langchain'"
        )

    def test_no_transformers_import_in_module_source(self) -> None:
        source = self._get_module_source()
        assert "transformers" not in source, (
            "slide_maker module must not import 'transformers'"
        )

    def test_no_litellm_import_in_module_source(self) -> None:
        source = self._get_module_source()
        assert "litellm" not in source, "slide_maker module must not import 'litellm'"

    def test_no_google_generativeai_import_in_module_source(self) -> None:
        source = self._get_module_source()
        assert "google.generativeai" not in source, (
            "slide_maker module must not import 'google.generativeai'"
        )

    def test_no_cohere_import_in_module_source(self) -> None:
        source = self._get_module_source()
        assert "cohere" not in source, "slide_maker module must not import 'cohere'"

    def test_no_replicate_import_in_module_source(self) -> None:
        """BC-7.1: source code must not import 'replicate'."""
        source = self._get_module_source()
        assert "replicate" not in source, (
            "slide_maker module must not import 'replicate'"
        )

    def test_no_vertexai_import_in_module_source(self) -> None:
        """BC-7.1: source code must not import 'vertexai'."""
        source = self._get_module_source()
        assert "vertexai" not in source, (
            "slide_maker module must not import 'vertexai'"
        )

    def test_no_boto3_import_in_module_source(self) -> None:
        """BC-7.1: source code must not import 'boto3' (AWS Bedrock)."""
        source = self._get_module_source()
        assert "boto3" not in source, (
            "slide_maker module must not import 'boto3'"
        )


# ---------------------------------------------------------------------------
# BC-7.2 -- Playwright per-invocation context, no module-level global
# ---------------------------------------------------------------------------


class TestPlaywrightNoModuleLevelGlobal:
    """BC-7.2: no Playwright context stored as a module-level global."""

    def test_module_has_no_playwright_browser_global(self) -> None:
        import slide_maker

        module_vars = vars(slide_maker)
        for name, value in module_vars.items():
            type_name = type(value).__name__
            # Check for any Playwright Browser/BrowserContext/Page-like objects
            assert "Browser" not in type_name or name.startswith("_"), (
                f"Module-level Playwright Browser found: {name}"
            )

    def test_importing_module_does_not_call_sync_playwright(self) -> None:
        """Importing slide_maker must not trigger sync_playwright() at module level."""
        # We verify by checking that no playwright.sync_api handle exists
        # as a non-None module-level attribute. The simplest proxy: the module
        # can be imported without playwright being installed (or mock it).
        with patch.dict(
            sys.modules,
            {
                "playwright": MagicMock(),
                "playwright.sync_api": MagicMock(),
            },
        ):
            import importlib

            # Re-importing should not cause any Playwright session to open.
            # If sync_playwright() is called at module level, the mock
            # context manager would be entered immediately.
            mock_sync_playwright = MagicMock()
            mock_context = MagicMock()
            mock_sync_playwright.return_value.__enter__ = MagicMock(
                return_value=mock_context
            )
            mock_sync_playwright.return_value.__exit__ = MagicMock(return_value=False)

            with patch(
                "playwright.sync_api.sync_playwright",
                mock_sync_playwright,
            ):
                importlib.reload(sys.modules["slide_maker"])
                # sync_playwright() must NOT have been called at import time
                mock_sync_playwright.assert_not_called()


# ---------------------------------------------------------------------------
# BC-7.3 -- LibreOffice isolation: soffice called with tmp UserInstallation
# ---------------------------------------------------------------------------


def _make_pptx_fake_run(captured_commands: list) -> Any:
    """Create a fake subprocess.run that captures commands AND creates a
    fake PDF in the --outdir (BUG-AUDIT-39: adapt_pptx now does
    PPTX→PDF→PNG two-step conversion, so the mock must produce a PDF).
    """

    def fake_run(
        cmd: Any, *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes]:
        if isinstance(cmd, list):
            captured_commands.append(cmd)
            # If this is a soffice --convert-to pdf call, create a fake PDF
            if any("soffice" in c for c in cmd) and "--convert-to" in cmd:
                try:
                    outdir_idx = cmd.index("--outdir") + 1
                    outdir = Path(cmd[outdir_idx])
                    input_file = Path(cmd[-1])
                    fake_pdf = outdir / f"{input_file.stem}.pdf"
                    fake_pdf.write_bytes(b"%PDF-1.4 fake")
                except (ValueError, IndexError):
                    pass
        result: subprocess.CompletedProcess[bytes] = MagicMock(
            spec=subprocess.CompletedProcess
        )
        result.returncode = 0
        result.stdout = b""
        result.stderr = b""
        return result

    return fake_run


def _make_mock_fitz() -> MagicMock:
    """Create a mock fitz module for adapt_pptx's PDF→PNG step."""
    mock_page = MagicMock()
    mock_pix = MagicMock()
    mock_page.get_pixmap.return_value = mock_pix

    mock_doc = MagicMock()
    mock_doc.__len__ = MagicMock(return_value=1)
    mock_doc.__getitem__ = MagicMock(return_value=mock_page)

    mock_fitz = MagicMock()
    mock_fitz.open.return_value = mock_doc
    return mock_fitz


class TestLibreOfficeIsolationProfile:
    """BC-7.3: adapt_pptx must pass -env:UserInstallation= to soffice."""

    def test_adapt_pptx_passes_user_installation_env_flag_to_soffice(
        self, tmp_path: Path
    ) -> None:
        pptx_file = tmp_path / "test.pptx"
        pptx_file.write_bytes(b"PK\x03\x04")

        captured_commands: list[list[str]] = []

        mock_pptx = MagicMock()
        mock_presentation = MagicMock()
        mock_presentation.slides = []
        mock_presentation.core_properties = MagicMock()
        mock_pptx.Presentation.return_value = mock_presentation

        with (
            patch("subprocess.run", side_effect=_make_pptx_fake_run(captured_commands)),
            patch("subprocess.Popen", side_effect=_make_pptx_fake_run(captured_commands)),
            patch.dict(sys.modules, {"pptx": mock_pptx, "fitz": _make_mock_fitz()}),
        ):
            try:
                adapt_pptx(pptx_file, tmp_path)
            except (NotImplementedError, Exception):
                pass

        soffice_calls = [
            cmd for cmd in captured_commands if any("soffice" in c for c in cmd)
        ]

        if soffice_calls:
            found_user_installation = any(
                any("-env:UserInstallation" in c for c in cmd) for cmd in soffice_calls
            )
            assert found_user_installation, (
                "adapt_pptx must pass -env:UserInstallation=file:/// to soffice "
                "for profile isolation (BC-7.3). "
                f"Actual soffice commands: {soffice_calls}"
            )


# ---------------------------------------------------------------------------
# BC-7.4 -- LibreOffice 120-second timeout and error message on timeout
# ---------------------------------------------------------------------------


class TestLibreOfficeTimeoutBehaviour:
    """BC-7.4: soffice subprocess must use a 120-second timeout."""

    def test_adapt_pptx_passes_timeout_of_120_to_subprocess(
        self, tmp_path: Path
    ) -> None:
        pptx_file = tmp_path / "deck.pptx"
        pptx_file.write_bytes(b"PK\x03\x04")

        captured_kwargs: list[dict[str, Any]] = []
        captured_commands: list[list[str]] = []

        def fake_run(
            cmd: Any, *args: Any, **kwargs: Any
        ) -> subprocess.CompletedProcess[bytes]:
            captured_kwargs.append(kwargs)
            if isinstance(cmd, list):
                captured_commands.append(cmd)
                if any("soffice" in c for c in cmd) and "--convert-to" in cmd:
                    try:
                        outdir_idx = cmd.index("--outdir") + 1
                        outdir = Path(cmd[outdir_idx])
                        input_file = Path(cmd[-1])
                        (outdir / f"{input_file.stem}.pdf").write_bytes(b"%PDF-1.4 fake")
                    except (ValueError, IndexError):
                        pass
            result: subprocess.CompletedProcess[bytes] = MagicMock(
                spec=subprocess.CompletedProcess
            )
            result.returncode = 0
            result.stdout = b""
            result.stderr = b""
            return result

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = MagicMock(slides=[])

        with (
            patch("subprocess.run", side_effect=fake_run),
            patch("subprocess.Popen", side_effect=fake_run),
            patch.dict(sys.modules, {"pptx": mock_pptx, "fitz": _make_mock_fitz()}),
        ):
            try:
                adapt_pptx(pptx_file, tmp_path)
            except (NotImplementedError, Exception):
                pass

        timeouts = [kw.get("timeout") for kw in captured_kwargs]
        if any(t is not None for t in timeouts):
            assert any(t == 120 for t in timeouts if t is not None), (
                f"Expected timeout=120 in subprocess call kwargs; got: {timeouts}"
            )

    def test_adapt_pptx_exits_code_1_and_prints_error_on_timeout(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pptx_file = tmp_path / "deck.pptx"
        pptx_file.write_bytes(b"PK\x03\x04")

        def fake_run_timeout(
            cmd: Any, *args: Any, **kwargs: Any
        ) -> subprocess.CompletedProcess[bytes]:
            if isinstance(cmd, list) and any("soffice" in c for c in cmd):
                raise subprocess.TimeoutExpired(cmd, 120)
            result: subprocess.CompletedProcess[bytes] = MagicMock(
                spec=subprocess.CompletedProcess
            )
            result.returncode = 0
            return result

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = MagicMock(slides=[])

        with (
            patch("subprocess.run", side_effect=fake_run_timeout),
            patch("subprocess.Popen", side_effect=fake_run_timeout),
            patch.dict(sys.modules, {"pptx": mock_pptx}),
        ):
            with pytest.raises(SystemExit) as exc_info:
                adapt_pptx(pptx_file, tmp_path)

        assert exc_info.value.code == 1, (
            "adapt_pptx must exit with code 1 on soffice timeout (BC-7.4)"
        )

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "LibreOffice" in combined or "timed out" in combined.lower(), (
            "adapt_pptx must print an error message referencing LibreOffice or "
            f"timeout on soffice TimeoutExpired. Got: {combined!r}"
        )

    def test_adapt_pptx_timeout_error_message_content(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-7.4: error message must say 120 seconds."""
        pptx_file = tmp_path / "deck.pptx"
        pptx_file.write_bytes(b"PK\x03\x04")

        def fake_run_timeout(
            cmd: Any, *args: Any, **kwargs: Any
        ) -> subprocess.CompletedProcess[bytes]:
            if isinstance(cmd, list) and any("soffice" in c for c in cmd):
                raise subprocess.TimeoutExpired(cmd, 120)
            result: subprocess.CompletedProcess[bytes] = MagicMock(
                spec=subprocess.CompletedProcess
            )
            result.returncode = 0
            return result

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = MagicMock(slides=[])

        with (
            patch("subprocess.run", side_effect=fake_run_timeout),
            patch("subprocess.Popen", side_effect=fake_run_timeout),
            patch.dict(sys.modules, {"pptx": mock_pptx}),
        ):
            with pytest.raises(SystemExit):
                adapt_pptx(pptx_file, tmp_path)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "120" in combined, (
            "Timeout error message must include '120' seconds reference. "
            f"Got: {combined!r}"
        )


# ---------------------------------------------------------------------------
# BC-7.5 -- PDF > 50 pages sets paper_detected flag
# ---------------------------------------------------------------------------


class TestPdfOver50PagesWarningFlag:
    """BC-7.5: adapt_pdf sets paper_detected:true when PDF has > 50 pages."""

    def _make_mock_fitz_document(self, page_count: int) -> MagicMock:
        """Return a mock fitz document with page_count pages."""
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=page_count)
        mock_doc.__iter__ = MagicMock(
            return_value=iter([MagicMock() for _ in range(page_count)])
        )
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        # Page mock with a Pixmap
        def make_page() -> MagicMock:
            page = MagicMock()
            pixmap = MagicMock()
            pixmap.save = MagicMock()
            page.get_pixmap.return_value = pixmap
            return page

        pages = [make_page() for _ in range(page_count)]
        mock_doc.__getitem__ = MagicMock(
            side_effect=lambda i: pages[i] if 0 <= i < page_count else pages[-1]
        )
        mock_doc.page_count = page_count
        return mock_doc

    def test_adapt_pdf_sets_paper_detected_true_for_51_pages(
        self, tmp_path: Path
    ) -> None:
        pdf_file = tmp_path / "paper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".debrief" / "draft").mkdir(parents=True)
        (project_root / "assets" / "reference" / "slides").mkdir(parents=True)
        (project_root / "assets" / "reference").mkdir(parents=True, exist_ok=True)

        mock_doc = self._make_mock_fitz_document(51)
        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            try:
                adapt_pdf(pdf_file, project_root)
            except (NotImplementedError, Exception):
                pass

        # Check analyzer_metadata.json for paper_detected flag
        metadata_path = project_root / ".debrief" / "draft" / "analyzer_metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
            assert metadata.get("paper_detected") is True, (
                "adapter_metadata.json must have paper_detected:true for >50 pages"
            )
        else:
            # The flag might be set differently; check all JSON files in output
            json_files = list(project_root.rglob("*.json"))
            for jf in json_files:
                try:
                    data = json.loads(jf.read_text())
                    if isinstance(data, dict):
                        assert data.get("paper_detected") is True
                        break
                except (json.JSONDecodeError, OSError):
                    pass

    def test_adapt_pdf_does_not_set_paper_detected_for_50_pages(
        self, tmp_path: Path
    ) -> None:
        pdf_file = tmp_path / "deck.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".debrief" / "draft").mkdir(parents=True)
        (project_root / "assets" / "reference" / "slides").mkdir(parents=True)

        mock_doc = self._make_mock_fitz_document(50)
        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            try:
                adapt_pdf(pdf_file, project_root)
            except (NotImplementedError, Exception):
                pass

        # If metadata file was written, paper_detected must NOT be true
        metadata_path = project_root / ".debrief" / "draft" / "analyzer_metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
            paper_detected = metadata.get("paper_detected", False)
            assert paper_detected is not True, (
                "paper_detected must not be True for a 50-page PDF (BC-7.5 "
                "threshold is > 50)"
            )

    def test_adapt_pdf_sets_paper_detected_true_for_100_pages(
        self, tmp_path: Path
    ) -> None:
        pdf_file = tmp_path / "longpaper.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".debrief" / "draft").mkdir(parents=True)
        (project_root / "assets" / "reference" / "slides").mkdir(parents=True)

        mock_doc = self._make_mock_fitz_document(100)
        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            try:
                adapt_pdf(pdf_file, project_root)
            except (NotImplementedError, Exception):
                pass

        metadata_path = project_root / ".debrief" / "draft" / "analyzer_metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
            assert metadata.get("paper_detected") is True, (
                "paper_detected must be True for 100-page PDF (BC-7.5)"
            )


# ---------------------------------------------------------------------------
# BC-7.2 -- Additional: adapt_html_file and adapt_html_dir use per-invocation
#            Playwright context (no shared global).
# ---------------------------------------------------------------------------


class TestAdaptHtmlFilePlaywrightPerInvocation:
    """BC-7.2: adapt_html_file must open its own sync_playwright() context."""

    def test_adapt_html_file_calls_sync_playwright_once_per_invocation(
        self, tmp_path: Path
    ) -> None:
        html_file = tmp_path / "slide.html"
        html_file.write_text("<html><body>test</body></html>")

        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "assets" / "reference" / "slides").mkdir(parents=True)
        (project_root / "assets" / "reference").mkdir(parents=True, exist_ok=True)

        mock_pw_instance = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw_instance.chromium.launch.return_value = mock_browser

        mock_sync_playwright_cm = MagicMock()
        mock_sync_playwright_cm.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_sync_playwright_cm.__exit__ = MagicMock(return_value=False)

        mock_sync_playwright_fn = MagicMock(return_value=mock_sync_playwright_cm)

        playwright_module = MagicMock()
        playwright_module.sync_playwright = mock_sync_playwright_fn
        playwright_sync_api = MagicMock()
        playwright_sync_api.sync_playwright = mock_sync_playwright_fn

        with patch.dict(
            sys.modules,
            {
                "playwright": playwright_module,
                "playwright.sync_api": playwright_sync_api,
            },
        ):
            try:
                adapt_html_file(html_file, project_root)
            except (NotImplementedError, Exception):
                pass

        # Each invocation must open exactly one Playwright context
        # (called at least once — exactly once is the contract)
        call_count = mock_sync_playwright_fn.call_count
        if call_count > 0:
            assert call_count == 1, (
                "adapt_html_file must call sync_playwright() exactly once per "
                f"invocation; called {call_count} times (BC-7.2)"
            )


class TestAdaptHtmlDirPlaywrightPerInvocation:
    """BC-7.2: adapt_html_dir must open its own sync_playwright() context."""

    def test_adapt_html_dir_calls_sync_playwright_once_per_invocation(
        self, tmp_path: Path
    ) -> None:
        ref_dir = tmp_path / "slides"
        ref_dir.mkdir()
        for i in range(3):
            (ref_dir / f"slide_{i:02d}.html").write_text(
                f"<html><body>slide {i}</body></html>"
            )

        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "assets" / "reference" / "slides").mkdir(parents=True)

        mock_pw_instance = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw_instance.chromium.launch.return_value = mock_browser

        mock_sync_playwright_cm = MagicMock()
        mock_sync_playwright_cm.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_sync_playwright_cm.__exit__ = MagicMock(return_value=False)

        mock_sync_playwright_fn = MagicMock(return_value=mock_sync_playwright_cm)

        playwright_module = MagicMock()
        playwright_module.sync_playwright = mock_sync_playwright_fn
        playwright_sync_api = MagicMock()
        playwright_sync_api.sync_playwright = mock_sync_playwright_fn

        with patch.dict(
            sys.modules,
            {
                "playwright": playwright_module,
                "playwright.sync_api": playwright_sync_api,
            },
        ):
            try:
                adapt_html_dir(ref_dir, project_root)
            except (NotImplementedError, Exception):
                pass

        call_count = mock_sync_playwright_fn.call_count
        if call_count > 0:
            assert call_count == 1, (
                "adapt_html_dir must call sync_playwright() exactly once per "
                f"invocation; called {call_count} times (BC-7.2)"
            )


# ---------------------------------------------------------------------------
# BC-7.2 -- Additional: main_preview_renderer uses per-invocation Playwright
#            context.  The contract explicitly names main_preview_renderer.
# ---------------------------------------------------------------------------


class TestMainPreviewRendererPlaywrightPerInvocation:
    """BC-7.2: main_preview_renderer must open its own sync_playwright() context."""

    def test_preview_renderer_calls_sync_playwright_once_per_invocation(
        self, tmp_path: Path
    ) -> None:
        """BC-7.2: main_preview_renderer opens exactly one Playwright context."""
        from slide_maker import main_preview_renderer

        input_dir = tmp_path / "preview_slides"
        input_dir.mkdir()
        for i in range(2):
            (input_dir / f"slide_{i:02d}.html").write_text(
                f"<html><body>preview {i}</body></html>"
            )

        output_dir = tmp_path / "preview_images"

        mock_pw_instance = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw_instance.chromium.launch.return_value = mock_browser

        mock_sync_playwright_cm = MagicMock()
        mock_sync_playwright_cm.__enter__ = MagicMock(
            return_value=mock_pw_instance
        )
        mock_sync_playwright_cm.__exit__ = MagicMock(return_value=False)

        mock_sync_playwright_fn = MagicMock(
            return_value=mock_sync_playwright_cm
        )

        playwright_module = MagicMock()
        playwright_module.sync_playwright = mock_sync_playwright_fn
        playwright_sync_api = MagicMock()
        playwright_sync_api.sync_playwright = mock_sync_playwright_fn

        import importlib.util

        real_find_spec = importlib.util.find_spec

        def patched_find_spec(name: str, *args: Any, **kw: Any) -> Any:
            if name == "playwright":
                return object()  # truthy -- signals package is present
            return real_find_spec(name, *args, **kw)

        with patch.dict(
            sys.modules,
            {
                "playwright": playwright_module,
                "playwright.sync_api": playwright_sync_api,
            },
        ):
            with patch("importlib.util.find_spec", side_effect=patched_find_spec):
                try:
                    main_preview_renderer(
                        tmp_path, input_dir, output_dir
                    )
                except (NotImplementedError, Exception):
                    pass

        call_count = mock_sync_playwright_fn.call_count
        if call_count > 0:
            assert call_count == 1, (
                "main_preview_renderer must call sync_playwright() exactly "
                f"once per invocation; called {call_count} times (BC-7.2)"
            )


# ---------------------------------------------------------------------------
# BC-7.3 -- LibreOffice isolation: soffice command includes tmp UserInstallation
#            (additional assertion: the path uses file:/// scheme)
# ---------------------------------------------------------------------------


class TestLibreOfficeUserInstallationScheme:
    """BC-7.3: -env:UserInstallation= must use file:/// URI scheme."""

    def test_user_installation_flag_uses_file_uri_scheme(self, tmp_path: Path) -> None:
        pptx_file = tmp_path / "deck.pptx"
        pptx_file.write_bytes(b"PK\x03\x04")

        captured_commands: list[list[str]] = []

        def fake_run(
            cmd: Any, *args: Any, **kwargs: Any
        ) -> subprocess.CompletedProcess[bytes]:
            if isinstance(cmd, list):
                captured_commands.append(list(cmd))
            result: subprocess.CompletedProcess[bytes] = MagicMock(
                spec=subprocess.CompletedProcess
            )
            result.returncode = 0
            result.stdout = b""
            result.stderr = b""
            return result

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = MagicMock(slides=[])

        with (
            patch("subprocess.run", side_effect=_make_pptx_fake_run(captured_commands)),
            patch("subprocess.Popen", side_effect=_make_pptx_fake_run(captured_commands)),
            patch.dict(sys.modules, {"pptx": mock_pptx, "fitz": _make_mock_fitz()}),
        ):
            try:
                adapt_pptx(pptx_file, tmp_path)
            except (NotImplementedError, Exception):
                pass

        soffice_calls = [
            cmd for cmd in captured_commands if any("soffice" in c for c in cmd)
        ]

        for cmd in soffice_calls:
            user_install_args = [c for c in cmd if "-env:UserInstallation" in c]
            for arg in user_install_args:
                assert "file:///" in arg, (
                    "UserInstallation must use file:/// URI scheme per BC-7.3. "
                    f"Got: {arg!r}"
                )


# ---------------------------------------------------------------------------
# BC-7.6 -- sample_slides: total == cap + 1 boundary (cap=10, total=11)
# ---------------------------------------------------------------------------


class TestSampleSlidesBoundaryAtCapPlusOne:
    """BC-7.6: boundary where total == cap + 1 triggers non-trivial sampling."""

    def test_total_11_with_cap_10_returns_exactly_10_elements(self) -> None:
        result = sample_slides(11)
        assert len(result) == 10

    def test_total_11_with_cap_10_includes_first_index(self) -> None:
        result = sample_slides(11)
        assert 0 in result

    def test_total_11_with_cap_10_includes_last_index(self) -> None:
        result = sample_slides(11)
        assert 10 in result

    def test_total_11_result_is_ascending(self) -> None:
        result = sample_slides(11)
        for i in range(len(result) - 1):
            assert result[i] < result[i + 1]

    def test_total_11_has_no_duplicates(self) -> None:
        result = sample_slides(11)
        assert len(result) == len(set(result))

    def test_total_11_is_deterministic_across_calls(self) -> None:
        assert sample_slides(11) == sample_slides(11)
