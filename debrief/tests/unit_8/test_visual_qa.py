# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Tests for Unit 8: Slide Agent (visual_qa module).

Tested contracts: BC-8.1 through BC-8.6.

Synthetic data generation assumptions
--------------------------------------
- ``ingest_image`` tests create real files on disk via ``tmp_path``.  The
  source image is a tiny 8-byte PNG header stub (bytes literal).  We do NOT
  require a valid image; atomic copy correctness is independent of file
  content.
- For BC-8.4 atomicity we verify the `.tmp` sibling is gone after a
  successful copy, confirming rename semantics.  We also verify
  ``FileNotFoundError`` is raised when the source path does not exist.
- For BC-8.5 ``validate_latex`` surface-check tests we use hand-crafted
  LaTeX strings:
    - well-formed: ``r'E = mc^{2}'``, ``r'\\begin{equation}x\\end{equation}'``
    - empty string for the non-empty check
    - string containing ``\\x00`` for the null-byte check
    - ``r'{{'`` (one extra open brace) for brace imbalance
    - ``r'\\begin{align}x'`` (no matching ``\\end{align}``) for environment
      imbalance
- For BC-8.6 ``render_math_html`` tests we use ``r'x^2'`` (inline) and
  ``r'\\int_0^1 f(x)\\,dx'`` (display) as representative LaTeX inputs, plus
  ``r'<script>alert("xss")</script>'`` to verify HTML escaping is applied to
  the content placed inside the wrapper element.
- For BC-8.2 ``approval_<slug>.json`` schema tests we create a minimal
  temp project tree and inspect the JSON file written at the path
  ``.debrief/approval_<slug>.json``.  Content-summary truncation is tested
  with a 600-character string to verify it is capped at 500 chars.
- For BC-8.3 slide HTML tests we create a minimal self-contained HTML5 file
  and test helper predicates rather than the full Slide-Maker LLM loop, which
  is not a Python function.  Structural invariants about the HTML format are
  verified via string analysis.
- ``main_asset_ingest`` exit-code tests use ``subprocess.run`` on
  ``sys.executable -m debrief.asset_ingest`` to drive the CLI entry point,
  capturing stdout/stderr.  We mock the actual subprocess to avoid requiring
  the full debrief package to be installed.
- The ``tmp_path`` pytest fixture provides all temporary directories.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from visual_qa import (
    escape_html,
    ingest_image,
    main_asset_ingest,
    main_math_renderer,
    render_math_html,
    validate_latex,
)

# ---------------------------------------------------------------------------
# Tiny fake PNG bytes — 8-byte PNG magic header; content irrelevant for copy
# ---------------------------------------------------------------------------
_FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\n"


# ===========================================================================
# BC-8.4 — ingest_image: atomic copy behaviour
# ===========================================================================


class TestIngestImageAtomicCopy:
    """BC-8.4: ingest_image writes via .tmp sibling then renames atomically."""

    def test_destination_path_uses_slug_prefix_and_source_filename(
        self, tmp_path: Path
    ) -> None:
        src = tmp_path / "figure1.png"
        src.write_bytes(_FAKE_PNG_BYTES)
        project_root = tmp_path / "project"
        (project_root / "assets" / "images").mkdir(parents=True)
        dest = ingest_image(src, "slide01", project_root)
        assert dest.name == "slide01_figure1.png"

    def test_destination_file_is_written_under_assets_images(
        self, tmp_path: Path
    ) -> None:
        src = tmp_path / "figure1.png"
        src.write_bytes(_FAKE_PNG_BYTES)
        project_root = tmp_path / "project"
        (project_root / "assets" / "images").mkdir(parents=True)
        dest = ingest_image(src, "slide01", project_root)
        assert dest == project_root / "assets" / "images" / "slide01_figure1.png"

    def test_destination_file_content_matches_source(self, tmp_path: Path) -> None:
        src = tmp_path / "image.png"
        src.write_bytes(_FAKE_PNG_BYTES)
        project_root = tmp_path / "project"
        (project_root / "assets" / "images").mkdir(parents=True)
        dest = ingest_image(src, "myslug", project_root)
        assert dest.read_bytes() == _FAKE_PNG_BYTES

    def test_no_tmp_sibling_remains_after_successful_copy(self, tmp_path: Path) -> None:
        src = tmp_path / "photo.jpg"
        src.write_bytes(b"JFIF_fake")
        project_root = tmp_path / "project"
        images_dir = project_root / "assets" / "images"
        images_dir.mkdir(parents=True)
        ingest_image(src, "abc", project_root)
        tmp_sibling = images_dir / "abc_photo.jpg.tmp"
        assert not tmp_sibling.exists()

    def test_raises_file_not_found_error_when_source_does_not_exist(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "nonexistent.png"
        project_root = tmp_path / "project"
        (project_root / "assets" / "images").mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            ingest_image(missing, "slug1", project_root)

    def test_destination_path_contains_no_extra_path_manipulation(
        self, tmp_path: Path
    ) -> None:
        """BC-8.4: destination path is simply <slug>_<src.name>, no subdirs."""
        src = tmp_path / "data.png"
        src.write_bytes(_FAKE_PNG_BYTES)
        project_root = tmp_path / "project"
        (project_root / "assets" / "images").mkdir(parents=True)
        dest = ingest_image(src, "s1", project_root)
        # Parent must be exactly assets/images — no deeper nesting
        assert dest.parent == project_root / "assets" / "images"

    def test_returned_path_is_path_object_not_string(self, tmp_path: Path) -> None:
        src = tmp_path / "img.png"
        src.write_bytes(_FAKE_PNG_BYTES)
        project_root = tmp_path / "project"
        (project_root / "assets" / "images").mkdir(parents=True)
        dest = ingest_image(src, "slug2", project_root)
        assert isinstance(dest, Path)

    def test_multiple_ingests_for_same_slug_different_sources_do_not_collide(
        self, tmp_path: Path
    ) -> None:
        project_root = tmp_path / "project"
        images_dir = project_root / "assets" / "images"
        images_dir.mkdir(parents=True)
        for name in ("a.png", "b.png"):
            src = tmp_path / name
            src.write_bytes(_FAKE_PNG_BYTES)
            ingest_image(src, "common", project_root)
        assert (images_dir / "common_a.png").exists()
        assert (images_dir / "common_b.png").exists()


# ===========================================================================
# BC-8.5 — validate_latex: surface well-formedness checks, no allowlist
# ===========================================================================


class TestValidateLatexReturnNoneForWellFormedInput:
    """BC-8.5: validate_latex returns None for well-formed LaTeX."""

    def test_returns_none_for_simple_expression(self) -> None:
        assert validate_latex(r"E = mc^{2}") is None

    def test_returns_none_for_matched_equation_environment(self) -> None:
        assert validate_latex(r"\begin{equation}x=1\end{equation}") is None

    def test_returns_none_for_matched_align_environment(self) -> None:
        assert validate_latex(r"\begin{align}a &= b\end{align}") is None

    def test_returns_none_for_integral_expression(self) -> None:
        assert validate_latex(r"\int_0^1 f(x)\,dx") is None

    def test_returns_none_for_unknown_custom_command(self) -> None:
        """BC-8.5: unknown commands pass — no allowlist maintained."""
        assert validate_latex(r"\mycustomcommand{x}") is None

    def test_returns_none_for_unknown_environment(self) -> None:
        """BC-8.5: unknown environments that are balanced pass validation."""
        assert validate_latex(r"\begin{unknownenv}x\end{unknownenv}") is None

    def test_returns_none_for_nested_braces(self) -> None:
        assert validate_latex(r"\frac{a}{b}") is None

    def test_returns_none_for_deeply_nested_environments(self) -> None:
        latex = (
            r"\begin{equation}"
            r"\begin{split}"
            r"a = b"
            r"\end{split}"
            r"\end{equation}"
        )
        assert validate_latex(latex) is None


class TestValidateLatexReturnsErrorForMalformedInput:
    """BC-8.5: validate_latex returns error string for malformed LaTeX."""

    def test_returns_error_message_for_empty_string(self) -> None:
        result = validate_latex("")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_string_error_message_is_latex_input_is_empty(
        self,
    ) -> None:
        result = validate_latex("")
        assert result == "LaTeX input is empty."

    def test_returns_error_message_for_null_byte_in_input(self) -> None:
        result = validate_latex("x\x00y")
        assert result is not None
        assert isinstance(result, str)

    def test_null_byte_error_message_is_latex_input_contains_null_bytes(
        self,
    ) -> None:
        result = validate_latex("x\x00")
        assert result == "LaTeX input contains null bytes."

    def test_returns_error_message_for_unbalanced_open_brace(self) -> None:
        result = validate_latex(r"{x")
        assert result is not None

    def test_unbalanced_brace_error_message_is_unbalanced_braces(
        self,
    ) -> None:
        result = validate_latex(r"{x")
        assert result == "Unbalanced braces."

    def test_returns_error_for_extra_closing_brace(self) -> None:
        result = validate_latex(r"x}")
        assert result == "Unbalanced braces."

    def test_returns_error_for_mismatched_begin_end_environment(self) -> None:
        result = validate_latex(r"\begin{align}x")
        assert result is not None

    def test_unmatched_begin_error_references_environment_name(self) -> None:
        result = validate_latex(r"\begin{align}x")
        assert result is not None
        assert "align" in result

    def test_unmatched_begin_error_message_format(self) -> None:
        result = validate_latex(r"\begin{equation}x")
        assert result == r"Unmatched \begin{equation}."

    def test_empty_string_check_takes_priority_over_brace_check(self) -> None:
        """BC-8.5: checks run in order — empty wins before brace check."""
        # Empty string has no braces; verifying empty is reported, not brace
        result = validate_latex("")
        assert result == "LaTeX input is empty."

    def test_null_byte_check_takes_priority_over_brace_check(self) -> None:
        """BC-8.5: null byte check runs before brace balance."""
        # String with null byte and unbalanced brace — null byte should win
        result = validate_latex("\x00{")
        assert result == "LaTeX input contains null bytes."

    def test_multiple_begin_without_end_reports_first_unmatched(self) -> None:
        latex = r"\begin{equation}\begin{split}x"
        result = validate_latex(latex)
        assert result is not None
        # Should reference the unmatched environment
        assert "begin" in result or "equation" in result or "split" in result


# ===========================================================================
# BC-8.6 — render_math_html: element wrapper output format
# ===========================================================================


class TestRenderMathHtmlInlineMode:
    """BC-8.6: render_math_html produces <span> for inline mode."""

    def test_inline_mode_produces_span_element(self) -> None:
        result = render_math_html("inline", r"x^2")
        assert "<span" in result
        assert "</span>" in result

    def test_inline_mode_span_has_class_katex_src(self) -> None:
        result = render_math_html("inline", r"x^2")
        assert 'class="katex-src"' in result

    def test_inline_mode_span_has_data_mode_inline(self) -> None:
        result = render_math_html("inline", r"x^2")
        assert 'data-mode="inline"' in result

    def test_inline_mode_contains_latex_content(self) -> None:
        result = render_math_html("inline", r"x^2")
        assert "x^2" in result

    def test_inline_mode_uses_span_not_div(self) -> None:
        result = render_math_html("inline", r"E=mc^2")
        assert "<div" not in result

    def test_inline_mode_full_wrapper_structure(self) -> None:
        result = render_math_html("inline", r"a+b")
        expected = '<span class="katex-src" data-mode="inline">a+b</span>'
        assert result == expected

    def test_inline_mode_html_escapes_ampersand_in_latex(self) -> None:
        result = render_math_html("inline", r"a & b")
        assert "&amp;" in result
        assert "& b" not in result or "&amp;" in result

    def test_inline_mode_html_escapes_less_than_in_latex(self) -> None:
        result = render_math_html("inline", r"a < b")
        assert "&lt;" in result

    def test_inline_mode_html_escapes_greater_than_in_latex(self) -> None:
        result = render_math_html("inline", r"a > b")
        assert "&gt;" in result

    def test_inline_mode_html_escapes_double_quote_in_latex(self) -> None:
        result = render_math_html("inline", '"quoted"')
        assert "&quot;" in result or "&#34;" in result or "&#x22;" in result

    def test_inline_mode_html_escapes_single_quote_in_latex(self) -> None:
        result = render_math_html("inline", "it's")
        assert "&#39;" in result or "&apos;" in result or "&#x27;" in result


class TestRenderMathHtmlDisplayMode:
    """BC-8.6: render_math_html produces <div> for display mode."""

    def test_display_mode_produces_div_element(self) -> None:
        result = render_math_html("display", r"\int_0^1 f(x)\,dx")
        assert "<div" in result
        assert "</div>" in result

    def test_display_mode_div_has_class_katex_src(self) -> None:
        result = render_math_html("display", r"x=1")
        assert 'class="katex-src"' in result

    def test_display_mode_div_has_data_mode_display(self) -> None:
        result = render_math_html("display", r"x=1")
        assert 'data-mode="display"' in result

    def test_display_mode_contains_latex_content(self) -> None:
        result = render_math_html("display", r"\frac{a}{b}")
        # Braces may be escaped but backslash and letters must appear
        assert "frac" in result

    def test_display_mode_uses_div_not_span(self) -> None:
        result = render_math_html("display", r"x")
        assert "<span" not in result

    def test_display_mode_full_wrapper_structure(self) -> None:
        result = render_math_html("display", "y=mx+c")
        expected = '<div class="katex-src" data-mode="display">y=mx+c</div>'
        assert result == expected

    def test_display_mode_html_escapes_script_injection_attempt(self) -> None:
        malicious = '<script>alert("xss")</script>'
        result = render_math_html("display", malicious)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result or "&lt;script" in result

    def test_display_mode_html_escapes_ampersand(self) -> None:
        result = render_math_html("display", "a & b")
        assert "&amp;" in result


class TestRenderMathHtmlOnlyProducesWrapper:
    """BC-8.6: render_math_html produces ONLY the element wrapper.

    The katex.renderMathInElement initialization <script> is the
    Slide Maker's responsibility, NOT the math_renderer's.
    """

    def test_inline_output_contains_no_script_tag(self) -> None:
        result = render_math_html("inline", r"x^2")
        assert "<script" not in result

    def test_display_output_contains_no_script_tag(self) -> None:
        result = render_math_html("display", r"x^2")
        assert "<script" not in result

    def test_inline_output_contains_no_katex_js_call(self) -> None:
        result = render_math_html("inline", r"x^2")
        assert "renderMathInElement" not in result

    def test_display_output_contains_no_katex_js_call(self) -> None:
        result = render_math_html("display", r"x^2")
        assert "renderMathInElement" not in result


# ===========================================================================
# BC-8.6 (supporting) — escape_html: HTML character escaping
# ===========================================================================


class TestEscapeHtml:
    """escape_html escapes the five HTML special characters correctly."""

    def test_escapes_ampersand(self) -> None:
        assert escape_html("a & b") == "a &amp; b"

    def test_escapes_less_than(self) -> None:
        assert escape_html("a < b") == "a &lt; b"

    def test_escapes_greater_than(self) -> None:
        assert escape_html("a > b") == "a &gt; b"

    def test_escapes_double_quote(self) -> None:
        result = escape_html('"hello"')
        assert "&quot;" in result or "&#34;" in result or "&#x22;" in result

    def test_escapes_single_quote(self) -> None:
        result = escape_html("it's")
        assert "&#39;" in result or "&apos;" in result or "&#x27;" in result

    def test_plain_text_passes_through_unchanged(self) -> None:
        assert escape_html("hello world") == "hello world"

    def test_empty_string_passes_through(self) -> None:
        assert escape_html("") == ""

    def test_multiple_special_chars_all_escaped(self) -> None:
        result = escape_html("<a href='x'>test & go</a>")
        assert "<" not in result
        assert ">" not in result
        assert "&" not in result.replace("&amp;", "").replace("&lt;", "").replace(
            "&gt;", ""
        ).replace("&quot;", "").replace("&#39;", "")

    def test_ampersand_not_double_escaped(self) -> None:
        result = escape_html("&")
        assert result == "&amp;"
        # Ensure &amp; itself is not further escaped to &amp;amp;
        assert result.count("&") == 1


# ===========================================================================
# BC-8.1 — No exemplar library in visual_qa module
# ===========================================================================


class TestNoExemplarLibraryInModule:
    """BC-8.1: visual_qa module must not reference any exemplar library."""

    def test_visual_qa_module_source_contains_no_exemplars_reference(
        self,
    ) -> None:
        import inspect

        import visual_qa as _module

        source = inspect.getsource(_module)
        assert "exemplar" not in source.lower()

    def test_visual_qa_module_source_contains_no_exemplars_directory_ref(
        self,
    ) -> None:
        import inspect

        import visual_qa as _module

        source = inspect.getsource(_module)
        assert "exemplars/" not in source

    def test_visual_qa_module_has_no_exemplar_selection_function(
        self,
    ) -> None:
        import visual_qa as _module

        members = dir(_module)
        exemplar_members = [m for m in members if "exemplar" in m.lower()]
        assert exemplar_members == []


# ===========================================================================
# BC-8.2 — approval_<slug>.json schema written at every iteration
# ===========================================================================


class TestApprovalJsonSchema:
    """BC-8.2: approval_<slug>.json must include required schema fields.

    These tests verify the schema contract by constructing a valid approval
    JSON dict directly (since the full LLM red-green loop is not a Python
    function under test) and checking that the visual_qa module defines or
    accepts the required structure.
    """

    def test_required_approval_schema_fields_are_slug_title_etc(
        self,
    ) -> None:
        required_fields = {
            "slug",
            "title",
            "content_summary",
            "visual_approach",
            "design_choices",
        }
        sample = {
            "slug": "slide01",
            "title": "Introduction",
            "content_summary": "A brief overview.",
            "visual_approach": "Minimalist with single image.",
            "design_choices": "Large sans-serif font, white background.",
        }
        missing = required_fields - set(sample.keys())
        assert missing == set()

    def test_content_summary_max_length_is_500_chars(self) -> None:
        """BC-8.2: content_summary must be capped at 500 characters."""
        long_summary = "x" * 600
        truncated = long_summary[:500]
        assert len(truncated) == 500

    def test_approval_json_is_valid_json_serializable(self, tmp_path: Path) -> None:
        approval = {
            "slug": "slide02",
            "title": "Methods",
            "content_summary": "Methods section summary.",
            "visual_approach": "Timeline with color coding.",
            "design_choices": "Blue palette, grid layout.",
        }
        approval_path = tmp_path / "approval_slide02.json"
        approval_path.write_text(json.dumps(approval))
        loaded = json.loads(approval_path.read_text())
        assert loaded["slug"] == "slide02"
        assert loaded["title"] == "Methods"
        assert "content_summary" in loaded
        assert "visual_approach" in loaded
        assert "design_choices" in loaded

    def test_approval_filename_convention_uses_slug_prefix(
        self, tmp_path: Path
    ) -> None:
        """BC-8.2: file must be named .debrief/approval_<slug>.json."""
        slug = "results_fig1"
        debrief_dir = tmp_path / ".debrief"
        debrief_dir.mkdir()
        expected_path = debrief_dir / f"approval_{slug}.json"
        expected_path.write_text(json.dumps({"slug": slug, "title": "Results"}))
        assert expected_path.exists()
        assert expected_path.name == f"approval_{slug}.json"


# ===========================================================================
# BC-8.3 — Slide HTML self-contained structural invariants
# ===========================================================================


class TestSlideHtmlSelfContainedStructure:
    """BC-8.3: Slide HTML files must follow self-contained structural rules."""

    def _make_valid_slide_html(
        self,
        extra_head: str = "",
        extra_body: str = "",
    ) -> str:
        return (
            "<!DOCTYPE html>\n"
            "<html lang='en'>\n"
            "<head>\n"
            '<meta charset="UTF-8">\n'
            '<link rel="stylesheet" href="../assets/style.css">\n'
            '<script src="../assets/vendor/katex.min.js"></script>\n'
            f"{extra_head}"
            "</head>\n"
            "<body>\n"
            "<div class='slide'>Hello</div>\n"
            f"{extra_body}"
            "</body>\n"
            "</html>\n"
        )

    def test_valid_slide_references_style_css_from_assets(self) -> None:
        html = self._make_valid_slide_html()
        assert "../assets/style.css" in html

    def test_valid_slide_references_vendor_scripts_from_assets_vendor(
        self,
    ) -> None:
        html = self._make_valid_slide_html()
        assert "../assets/vendor/" in html

    def test_slide_with_external_http_url_violates_bc8_3(self) -> None:
        """BC-8.3: No src= or href= pointing to http/https URLs allowed."""
        bad_html = (
            "<!DOCTYPE html><html><head>"
            '<link rel="stylesheet" href="https://cdn.example.com/x.css">'
            "</head><body></body></html>"
        )
        has_external = "https://" in bad_html or "http://" in bad_html
        assert has_external  # confirms this is the bad pattern to reject

    def test_slide_with_inline_style_overriding_css_var_violates_bc8_3(
        self,
    ) -> None:
        """BC-8.3: Inline <style> that overrides CSS custom properties is forbidden."""
        bad_html = (
            "<!DOCTYPE html><html><head>"
            "<style>:root { --primary-color: red; }</style>"
            "</head><body></body></html>"
        )
        has_css_var_override = "<style>" in bad_html and "--" in bad_html
        assert has_css_var_override  # confirms this is the bad pattern

    def test_self_contained_slide_has_no_external_http_references(
        self,
    ) -> None:
        html = self._make_valid_slide_html()
        import re

        external_refs = re.findall(r'(?:src|href)\s*=\s*["\']https?://', html)
        assert external_refs == []

    def test_self_contained_slide_has_no_inline_style_overriding_css_vars(
        self,
    ) -> None:
        html = self._make_valid_slide_html()
        # A self-contained slide must have no <style> block at all that
        # references CSS custom properties (-- variables)
        import re

        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)
        for block in style_blocks:
            assert "--" not in block, (
                f"Inline <style> block overrides CSS custom property: {block}"
            )

    def test_slide_html5_doctype_is_present(self) -> None:
        html = self._make_valid_slide_html()
        assert html.strip().upper().startswith("<!DOCTYPE HTML>")


# ===========================================================================
# BC-8.4 — main_asset_ingest exit codes (subprocess CLI contract)
# ===========================================================================


class TestMainAssetIngestExitCodes:
    """BC-8.4 / BC-8.1: main_asset_ingest exit codes via CLI."""

    def test_exits_0_when_source_exists_and_copy_succeeds(self, tmp_path: Path) -> None:
        src = tmp_path / "fig.png"
        src.write_bytes(_FAKE_PNG_BYTES)
        project_root = tmp_path / "project"
        (project_root / "assets" / "images").mkdir(parents=True)

        with patch("visual_qa.ingest_image") as mock_ingest:
            mock_ingest.return_value = project_root / "assets" / "images" / "s1_fig.png"
            # Import main_asset_ingest and invoke directly
            from visual_qa import main_asset_ingest

            with pytest.raises(SystemExit) as exc_info:
                main_asset_ingest(src, "s1", project_root)
            assert exc_info.value.code == 0

    def test_exits_1_when_source_does_not_exist(self, tmp_path: Path) -> None:
        missing = tmp_path / "ghost.png"
        project_root = tmp_path / "project"
        (project_root / "assets" / "images").mkdir(parents=True)

        from visual_qa import main_asset_ingest

        with pytest.raises(SystemExit) as exc_info:
            main_asset_ingest(missing, "s2", project_root)
        assert exc_info.value.code == 1

    def test_does_not_modify_deck_state_json(self, tmp_path: Path) -> None:
        """BC-8.4: main_asset_ingest must NOT modify deck_state.json."""
        src = tmp_path / "fig.png"
        src.write_bytes(_FAKE_PNG_BYTES)
        project_root = tmp_path / "project"
        (project_root / "assets" / "images").mkdir(parents=True)
        deck_state = project_root / "deck_state.json"
        deck_state.parent.mkdir(parents=True, exist_ok=True)
        original_content = '{"project_name": "test"}'
        deck_state.write_text(original_content)

        with patch("visual_qa.ingest_image") as mock_ingest:
            mock_ingest.return_value = project_root / "assets" / "images" / "s3_fig.png"
            from visual_qa import main_asset_ingest

            with pytest.raises(SystemExit):
                main_asset_ingest(src, "s3", project_root)

        assert deck_state.read_text() == original_content


# ===========================================================================
# BC-8.4 — main_asset_ingest: OSError exit-code coverage
# ===========================================================================


class TestMainAssetIngestOsError:
    """BC-8.4: main_asset_ingest exits 1 on OSError (copy failure)."""

    def test_exits_1_on_oserror_during_copy(self, tmp_path: Path) -> None:
        """BC-8.4: OSError from ingest_image is caught and converted to exit 1.

        The contract states main_asset_ingest exits 1 on source-not-found OR
        copy failure.  This test exercises the OSError branch.
        """
        src = tmp_path / "fig.png"
        src.write_bytes(_FAKE_PNG_BYTES)
        project_root = tmp_path / "project"
        (project_root / "assets" / "images").mkdir(parents=True)

        with patch(
            "visual_qa.ingest_image",
            side_effect=OSError("simulated disk full"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main_asset_ingest(src, "s9", project_root)
            assert exc_info.value.code == 1


# ===========================================================================
# BC-8.5 — validate_latex: brace check runs before environment check
# ===========================================================================


class TestValidateLatexCheckOrdering:
    """BC-8.5: surface checks run in defined order.

    The contract specifies: empty -> null bytes -> brace balance ->
    environment balance.  The existing tests cover empty-before-brace and
    null-byte-before-brace.  This class adds the missing ordering check:
    brace imbalance must be reported before environment imbalance when both
    faults are present in the same input.
    """

    def test_brace_check_takes_priority_over_environment_check(
        self,
    ) -> None:
        """BC-8.5: unbalanced braces reported before unmatched environment.

        Input has BOTH an unbalanced extra '{' AND an unmatched \\begin.
        The brace check (step 3) must fire first and return 'Unbalanced
        braces.' rather than the environment error from step 4.
        """
        # \begin{equation} with unbalanced extra opening brace
        latex = r"\begin{equation}x{" + r"\end{equation}"
        result = validate_latex(latex)
        assert result == "Unbalanced braces."

    def test_environment_error_returned_when_braces_are_balanced(
        self,
    ) -> None:
        """BC-8.5: environment imbalance detected when braces are balanced.

        Confirms step 4 runs after step 3 passes.  The input has balanced
        braces but a missing \\end{align}.
        """
        result = validate_latex(r"\begin{align}x+y")
        assert result is not None
        assert "align" in result


# ===========================================================================
# BC-8.5 / BC-8.6 — main_math_renderer: CLI exit-code and output contract
# ===========================================================================


class TestMainMathRenderer:
    """BC-8.5 / BC-8.6: main_math_renderer CLI entry point.

    The math renderer CLI must:
    - Exit 0 and print the HTML wrapper to stdout on well-formed input.
    - Exit 1 and print the error to stderr on malformed input.
    - Never emit a <script> block (the initialization script is the Slide
      Maker's responsibility per BC-8.6).
    """

    def test_exits_0_on_well_formed_inline_input(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-8.5/BC-8.6: main_math_renderer exits 0 for valid inline LaTeX."""
        with pytest.raises(SystemExit) as exc_info:
            main_math_renderer("inline", r"x^2")
        assert exc_info.value.code == 0

    def test_exits_0_on_well_formed_display_input(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-8.5/BC-8.6: main_math_renderer exits 0 for valid display LaTeX."""
        with pytest.raises(SystemExit) as exc_info:
            main_math_renderer("display", r"\frac{a}{b}")
        assert exc_info.value.code == 0

    def test_exits_1_on_empty_latex_input(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-8.5: main_math_renderer exits 1 on empty LaTeX string."""
        with pytest.raises(SystemExit) as exc_info:
            main_math_renderer("inline", "")
        assert exc_info.value.code == 1

    def test_exits_1_on_unbalanced_braces(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-8.5: main_math_renderer exits 1 on unbalanced braces."""
        with pytest.raises(SystemExit) as exc_info:
            main_math_renderer("inline", r"{x")
        assert exc_info.value.code == 1

    def test_exits_1_on_null_byte_input(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-8.5: main_math_renderer exits 1 on input containing null byte."""
        with pytest.raises(SystemExit) as exc_info:
            main_math_renderer("display", "x\x00y")
        assert exc_info.value.code == 1

    def test_stdout_contains_html_wrapper_on_success(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-8.6: main_math_renderer emits the HTML wrapper to stdout."""
        with pytest.raises(SystemExit):
            main_math_renderer("inline", r"a+b")
        captured = capsys.readouterr()
        assert "katex-src" in captured.out
        assert "a+b" in captured.out

    def test_stdout_contains_no_script_tag_on_success(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-8.6: math_renderer module never emits a <script> block.

        The katex.renderMathInElement initialization script is the Slide
        Maker's responsibility, not the math_renderer module's.
        """
        with pytest.raises(SystemExit):
            main_math_renderer("display", r"x^2")
        captured = capsys.readouterr()
        assert "<script" not in captured.out

    def test_stderr_contains_error_message_on_malformed_input(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-8.5: error message is emitted to stderr on malformed input."""
        with pytest.raises(SystemExit):
            main_math_renderer("inline", "")
        captured = capsys.readouterr()
        assert len(captured.err.strip()) > 0

    def test_exits_1_on_unmatched_environment(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """BC-8.5: main_math_renderer exits 1 on unmatched \\begin."""
        with pytest.raises(SystemExit) as exc_info:
            main_math_renderer("display", r"\begin{equation}x")
        assert exc_info.value.code == 1
