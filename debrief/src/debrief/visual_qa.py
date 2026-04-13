# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Visual QA module for debrief: asset ingestion and math rendering.

Implements BC-8.1 through BC-8.6.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# HTML escaping
# ---------------------------------------------------------------------------


def escape_html(text: str) -> str:
    """Escape HTML special characters in text: &, <, >, ", '.

    Returns the escaped string.
    """
    # Order matters: & must be escaped first to avoid double-escaping.
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&#39;")
    return text


# ---------------------------------------------------------------------------
# LaTeX surface validation  (BC-8.5)
# ---------------------------------------------------------------------------


def validate_latex(latex_input: str) -> Optional[str]:
    """Surface well-formedness check on a LaTeX string.

    Returns None if the input is well-formed.
    Returns an error message string if malformed.

    Checks (in order):
    1. Non-empty: empty string -> 'LaTeX input is empty.'
    2. No null bytes: presence of \\x00 -> 'LaTeX input contains null bytes.'
    3. Brace balance: count of '{' must equal count of '}' ->
       'Unbalanced braces.'
    4. Environment balance: every \\begin{X} has a matching \\end{X}
       -> 'Unmatched \\begin{<env>}.'
    """
    # Check 1 — empty
    if not latex_input:
        return "LaTeX input is empty."

    # Check 2 — null bytes
    if "\x00" in latex_input:
        return "LaTeX input contains null bytes."

    # Check 3 — brace balance
    if latex_input.count("{") != latex_input.count("}"):
        return "Unbalanced braces."

    # Check 4 — environment balance
    begins = re.findall(r"\\begin\{([^}]+)\}", latex_input)
    ends = re.findall(r"\\end\{([^}]+)\}", latex_input)

    # Use a stack to track nesting
    stack: list[str] = []
    # Re-scan in document order to find the first unmatched \begin
    tokens = re.finditer(
        r"\\(begin|end)\{([^}]+)\}",
        latex_input,
    )
    for match in tokens:
        command = match.group(1)
        env_name = match.group(2)
        if command == "begin":
            stack.append(env_name)
        else:  # end
            if stack and stack[-1] == env_name:
                stack.pop()
            else:
                # Unmatched \end — still report the first unmatched \begin
                # but we continue; the stack may hold the real culprit.
                pass

    if stack:
        # Report the innermost unmatched \begin (last on stack)
        first_unmatched = stack[0]
        return rf"Unmatched \begin{{{first_unmatched}}}."

    # Suppress unused variable warnings — these are computed but not used
    # after the stack approach; kept for clarity.
    _ = begins
    _ = ends

    return None


# ---------------------------------------------------------------------------
# Math HTML renderer  (BC-8.6)
# ---------------------------------------------------------------------------


def render_math_html(mode: str, latex_input: str) -> str:
    """Produce the KaTeX HTML wrapper for the given LaTeX string.

    For inline mode:
        <span class="katex-src" data-mode="inline">{escaped}</span>
    For display mode:
        <div class="katex-src" data-mode="display">{escaped}</div>

    The escaped value is the LaTeX string with HTML special characters
    escaped.
    """
    escaped = escape_html(latex_input)
    if mode == "inline":
        return f'<span class="katex-src" data-mode="inline">{escaped}</span>'
    else:
        return f'<div class="katex-src" data-mode="display">{escaped}</div>'


def main_math_renderer(mode: str, latex_input: str) -> None:
    """Entry point for math renderer CLI.

    Validate latex_input for surface well-formedness.
    Emit the HTML wrapper to stdout.
    Exit 0 on well-formed input.
    Exit 1 on malformed input (message on stderr).
    """
    error = validate_latex(latex_input)
    if error is not None:
        print(error, file=sys.stderr)
        sys.exit(1)
    print(render_math_html(mode, latex_input))
    sys.exit(0)


# ---------------------------------------------------------------------------
# Asset ingestion  (BC-8.4)
# ---------------------------------------------------------------------------


def ingest_image(src: Path, slug: str, project_root: Path) -> Path:
    """Copy src to assets/images/<slug>_<src.name> atomically.

    Returns the destination path.
    Raises FileNotFoundError if src does not exist.
    Raises OSError on copy failure.
    """
    if not src.exists():
        raise FileNotFoundError(f"Source image not found: {src}")

    dest_name = f"{slug}_{src.name}"
    images_dir = project_root / "assets" / "images"
    dest = images_dir / dest_name
    tmp_dest = images_dir / f"{dest_name}.tmp"

    # Read source content
    data = src.read_bytes()

    # Write to .tmp sibling
    tmp_dest.write_bytes(data)

    # Atomic rename
    os.rename(tmp_dest, dest)

    return dest


def main_asset_ingest(src: Path, slug: str, project_root: Path) -> None:
    """Entry point for asset ingest CLI.

    Copy src to project_root/assets/images/<slug>_<src.name> atomically.
    Exit 0 on success.
    Exit 1 on source-not-found or copy failure.
    Exit 3 on usage error.
    Does NOT modify deck_state.json.
    """
    try:
        ingest_image(src, slug, project_root)
        sys.exit(0)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
