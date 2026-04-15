# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 3: Launcher.

Provides project initialization (new), archetype selection, vendor-hash
verification, CLAUDE.md template rendering, and directory-structure creation
for the Debrief plugin.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Section 9.3.1 env-corruption error message (shared with Unit 2)
# ---------------------------------------------------------------------------

_ENV_CORRUPTION_MSG = (
    "ERROR: json_repair is not installed or the conda environment is corrupt.\n"
    "Run: conda env create -f environment.yml  (see Section 9.3.1)\n"
    "The json_repair package is required for safe state-file handling.\n"
)

# ---------------------------------------------------------------------------
# Section 24.27 vendor-reinstall recovery instruction
# ---------------------------------------------------------------------------

_VENDOR_CORRUPT_MSG = (
    "Plugin assets appear corrupted. Reinstall the Debrief plugin via "
    "Claude Code's plugin management (e.g., /plugin reinstall debrief or "
    "equivalent). If reinstall fails, delete ${CLAUDE_PLUGIN_ROOT} and "
    "reinstall from source."
)

# ---------------------------------------------------------------------------
# Archetype ordered list (REQ-INIT-7)
# ---------------------------------------------------------------------------

_ARCHETYPE_ORDER = [
    "lab_meeting",
    "conference_talk",
    "seminar",
    "lecture",
    "journal_club",
    "grant_panel",
    "job_talk",
    "custom",
]

# ---------------------------------------------------------------------------
# Required project subdirectories (Section 3 / BC-3.9 / BUG-AUDIT-15)
# ---------------------------------------------------------------------------

# The full canonical project directory tree per spec §3. Created at every
# `debrief new` AND re-scaffolded on every bare `debrief` re-entry via the
# `ensure_project` orchestrator (BC-3.14). All entries use forward slashes;
# `mkdir(parents=True, exist_ok=True)` makes nested paths and idempotency
# both free. Empty directories are valid project state — the canonical tree
# is "always present" regardless of whether agents have produced content
# inside it (see BUG-AUDIT-15 and the directory policy paragraph in spec §3).
_REQUIRED_DIRS = [
    ".debrief",
    ".debrief/briefs",
    ".debrief/draft",
    ".debrief/draft/preview_slides",
    ".debrief/draft/preview_images",
    ".debrief/snapshots",
    "assets/images",
    "assets/fonts",
    "assets/vendor",
    "assets/math",
    "assets/reference/slides",
    "assets/reference/papers",
    "slides",
    "output",
    "output/screenshots",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_json_repair() -> None:
    """Exit(2) with env-corruption error when json_repair is unavailable."""
    if importlib.util.find_spec("json_repair") is None:
        print(_ENV_CORRUPTION_MSG, file=sys.stderr)
        sys.exit(2)


def _iso_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# create_project_structure (BC-3.9)
# ---------------------------------------------------------------------------


def create_project_structure(project_root: Path) -> None:
    """Create all required project subdirectories per Section 3.

    Uses exist_ok=True for all mkdir calls so that calling twice is safe.
    """
    for rel in _REQUIRED_DIRS:
        (project_root / rel).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# render_project_claude_md (BC-3.6)
# ---------------------------------------------------------------------------


def render_project_claude_md(
    template_path: Path,
    project_root: Path,
    project_name: str,
) -> None:
    """Read the CLAUDE.md template, substitute {project_name}, write atomically.

    Only {project_name} is substituted; all other {…} tokens are left unchanged.
    The write is atomic: write-to-tmp then os.rename (no .tmp file persists).
    """
    raw = template_path.read_text(encoding="utf-8")
    rendered = raw.replace("{project_name}", project_name)

    dest = project_root / "CLAUDE.md"
    tmp = project_root / "CLAUDE.md.tmp"
    tmp.write_text(rendered, encoding="utf-8")
    # fsync before rename for durability
    with open(tmp, "rb") as fh:
        os.fsync(fh.fileno())
    os.rename(tmp, dest)


# ---------------------------------------------------------------------------
# verify_vendor_hashes (BC-3.8)
# ---------------------------------------------------------------------------


def verify_vendor_hashes(plugin_root: Path) -> None:
    """Read VERSIONS.md and verify each listed file's SHA-256 hash.

    Exits with code 1 on any mismatch; error goes to stderr.
    """
    versions_path = plugin_root / "assets" / "vendor" / "VERSIONS.md"
    vendor_dir = plugin_root / "assets" / "vendor"

    lines = versions_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        filename = parts[0].strip()
        # Find the sha256:<hash> field
        sha_field = None
        for part in parts:
            p = part.strip()
            if p.startswith("sha256:"):
                sha_field = p
                break
        if sha_field is None:
            continue
        expected_hash = sha_field[len("sha256:") :]
        file_path = vendor_dir / filename
        if not file_path.exists():
            continue
        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            print(
                f"ERROR: Vendor file hash mismatch for '{filename}'.\n"
                f"  Expected: {expected_hash}\n"
                f"  Actual:   {actual_hash}\n"
                f"{_VENDOR_CORRUPT_MSG}",
                file=sys.stderr,
            )
            sys.exit(1)


# ---------------------------------------------------------------------------
# select_archetype (BC-3.2, BC-3.3)
# ---------------------------------------------------------------------------


def select_archetype(archetypes_path: Path) -> str:
    """Present the archetype selection prompt and return the chosen key.

    Accepts a 1-based number (1–8) or an archetype name (case-insensitive).
    Re-prompts exactly once on invalid input; exits code 1 on second failure.
    """
    archetypes_data: dict = json.loads(archetypes_path.read_text(encoding="utf-8"))
    # Build ordered keys from the canonical order, preserving only those
    # actually present in the file.
    ordered_keys = [k for k in _ARCHETYPE_ORDER if k in archetypes_data]
    # Append any keys from the file not covered by the canonical order.
    for k in archetypes_data:
        if k not in ordered_keys:
            ordered_keys.append(k)

    def _build_prompt() -> str:
        lines = ["Select a presentation archetype:"]
        for i, key in enumerate(ordered_keys, start=1):
            lines.append(f"  {i}. {key}")
        lines.append("Enter a number (1–8) or archetype name: ")
        return "\n".join(lines)

    def _parse(raw: str) -> Optional[str]:
        stripped = raw.strip().lower()
        # Try numeric
        try:
            idx = int(stripped) - 1
            if 0 <= idx < len(ordered_keys):
                return ordered_keys[idx]
            return None
        except ValueError:
            pass
        # Try name match (case-insensitive)
        if stripped in {k.lower() for k in ordered_keys}:
            for k in ordered_keys:
                if k.lower() == stripped:
                    return k
        return None

    prompt = _build_prompt()
    print(prompt, end="", flush=True)
    first_input = sys.stdin.readline()
    result = _parse(first_input)
    if result is not None:
        return result

    # Re-prompt once
    print(prompt, end="", flush=True)
    second_input = sys.stdin.readline()
    result = _parse(second_input)
    if result is not None:
        return result

    # Second failure: print error and exit 1
    msg = (
        "Invalid selection. Please run 'debrief new' again and enter "
        "a number 1-8 or an archetype name."
    )
    print(msg, file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# new() (BC-3.1, BC-3.4, BC-3.5, BC-3.6, BC-3.7, BC-3.11)
# ---------------------------------------------------------------------------


def new(project_root: Path, archetype: Optional[str] = None) -> None:
    """Initialize a new Debrief project in project_root.

    Steps:
    1. Check json_repair availability (BC-3.11).
    2. Verify project_root is empty or contains only CLAUDE.md (BC-3.1).
    3. Select archetype interactively if not provided (BC-3.2/3.3).
    4. Create required subdirectories (BC-3.9).
    5. Copy vendor assets from plugin_root (BC-3.7).
    6. Write initial deck_state.json (BC-3.4).
    7. Write initial debrief_state.json (BC-3.5).
    8. Render project_claude.md template into CLAUDE.md (BC-3.6).
    """
    # BC-3.11: json_repair entry check
    _require_json_repair()

    # Resolve plugin_root from env
    plugin_root_env = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    plugin_root = Path(plugin_root_env) if plugin_root_env else None

    # BC-3.1: verify project_root is empty or contains only CLAUDE.md
    if project_root.exists():
        contents = list(project_root.iterdir())
        unexpected = [p for p in contents if p.name != "CLAUDE.md"]
        if unexpected:
            print(
                f"ERROR: Project directory '{project_root}' is not empty. "
                "Remove unexpected files before running 'debrief new'.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Determine archetype
    if archetype is None:
        if plugin_root is None:
            print(
                "ERROR: CLAUDE_PLUGIN_ROOT environment variable is not set.",
                file=sys.stderr,
            )
            sys.exit(1)
        archetypes_path = plugin_root / "archetypes.json"
        archetype = select_archetype(archetypes_path)

    # BC-3.7: check vendor directory
    if plugin_root is None:
        print(
            "ERROR: CLAUDE_PLUGIN_ROOT environment variable is not set.",
            file=sys.stderr,
        )
        sys.exit(1)

    vendor_src = plugin_root / "assets" / "vendor"
    if not vendor_src.exists() or not vendor_src.is_dir():
        print(
            "ERROR: Vendor directory not found at "
            f"'{vendor_src}'. Cannot initialize project.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not any(vendor_src.iterdir()):
        print(
            "ERROR: Vendor directory is empty at "
            f"'{vendor_src}'. Cannot initialize project.",
            file=sys.stderr,
        )
        sys.exit(1)

    # BC-3.9: create project structure
    create_project_structure(project_root)

    # BC-3.7: copy vendor assets
    vendor_dest = project_root / "assets" / "vendor"
    for item in vendor_src.iterdir():
        if item.is_file():
            shutil.copy2(item, vendor_dest / item.name)

    # BC-3.4: write initial deck_state.json
    now = _iso_now()
    project_name = project_root.name
    deck_state_data = {
        "project_name": project_name,
        "created_at": now,
        "archetype": archetype,
        "style_locked": False,
        "closing_slide": None,
        "slides": [],
        "presentations": [],
    }
    _atomic_write_json(project_root / "deck_state.json", deck_state_data)

    # BC-3.5: write initial debrief_state.json
    debrief_data: dict = {
        "phase": "discovery",
        "sub_phase": "discovery/greeting",
        "active_agent": "consultant",
        "archetype": archetype,
        "current_group_id": None,
        "current_slide_slug": None,
        "pending_gate": None,
        "last_gate_response": None,
        "red_green_iteration": 0,
        "red_green_started_at": None,
        "group_slide_index": 0,
        "group_slide_count": 0,
        "backup_mode": False,
        "completed_groups": [],
        "pre_view_state": None,
        "view_deferred": False,
        "closing_slide_pending": False,
        "group_revise_slug": None,
        "style_import_mode": None,
        "reference_provided": False,
        "reference_modality": None,
        "papers_provided": False,
        "selected_figures": None,
        "session_started_at": now,
        "state_hash": "",
    }
    # Compute state_hash per BC-2.4 / BC-3.5
    debrief_data["state_hash"] = _compute_state_hash(debrief_data)
    _atomic_write_json(project_root / "debrief_state.json", debrief_data)

    # BC-3.6: render CLAUDE.md template
    template_path = plugin_root / "templates" / "project_claude.md"
    if template_path.exists():
        render_project_claude_md(template_path, project_root, project_name)

    # BC-3.13 / BUG-AUDIT-8: write project-scoped Claude Code settings so
    # `claude` (without --plugin-dir) loads debrief from the local
    # marketplace and namespaces its skills as /debrief:*.
    ensure_project_settings(project_root, plugin_root)


# ---------------------------------------------------------------------------
# ensure_project_settings (BC-3.13, BUG-AUDIT-8)
# ---------------------------------------------------------------------------


def ensure_project_settings(project_root: Path, plugin_root: Path) -> None:
    """Create or update `.claude/settings.json` for project-scoped plugin loading.

    BC-3.13: idempotent helper that ensures Claude Code, when launched from
    `project_root`, discovers the debrief plugin via the local marketplace
    at `plugin_root.parent` and enables it. Writes only the
    `extraKnownMarketplaces.debrief` and `enabledPlugins["debrief@debrief"]`
    keys; preserves any unrelated keys already present in the file.

    The `path` field on the marketplace entry is the absolute, symlink-
    resolved path of `plugin_root.parent` — the directory containing
    `.claude-plugin/marketplace.json`. Re-running with a different
    `plugin_root` updates the path automatically (self-heal when the user
    moves the debrief repo on disk).

    On corrupt JSON or non-dict contents, silently starts over with an
    empty dict to avoid blocking bin/debrief over a developer mistake.
    """
    settings_dir = project_root / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.json"

    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
            if not isinstance(data, dict):
                data = {}
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    marketplace_root = str(plugin_root.parent.resolve())

    extra = data.get("extraKnownMarketplaces")
    if not isinstance(extra, dict):
        extra = {}
        data["extraKnownMarketplaces"] = extra
    extra["debrief"] = {
        "source": {
            "source": "directory",
            "path": marketplace_root,
        }
    }

    enabled = data.get("enabledPlugins")
    if not isinstance(enabled, dict):
        enabled = {}
        data["enabledPlugins"] = enabled
    enabled["debrief@debrief"] = True

    _atomic_write_json(settings_path, data)


# ---------------------------------------------------------------------------
# preflight (BC-3.8, BC-3.11)
# ---------------------------------------------------------------------------


def preflight(plugin_root: Path) -> None:
    """Python half of pre-flight checks: verifies vendor hashes only.

    BC-3.11: checks json_repair availability at entry.
    BC-3.8: calls verify_vendor_hashes(); exits 1 on mismatch.
    """
    _require_json_repair()
    verify_vendor_hashes(plugin_root)


# ---------------------------------------------------------------------------
# Internal helpers (not part of the public API)
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write data as JSON to path atomically (write-to-tmp then os.rename)."""
    tmp = path.parent / (path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.rename(tmp, path)


def _compute_state_hash(state_dict: dict) -> str:
    """Compute SHA-256 over canonical JSON of all fields except state_hash."""
    payload_dict = {k: v for k, v in state_dict.items() if k != "state_hash"}
    payload = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# ensure_project orchestrator (BC-3.14, BUG-AUDIT-15)
# ---------------------------------------------------------------------------


def ensure_project(project_root: Path, plugin_root: Path) -> None:
    """Re-scaffold an existing debrief project on every bare ``debrief`` entry.

    BC-3.14 / BUG-AUDIT-15: this orchestrator is the canonical entry hook
    for the ``debrief`` (no-args) bare-invocation arm in ``bin/debrief``. It
    composes two existing helpers in a fixed order:

    1. :func:`create_project_structure` — re-scaffolds the canonical project
       directory tree from spec §3 / :data:`_REQUIRED_DIRS`. Idempotent
       (``mkdir(parents=True, exist_ok=True)``); restores any directory that
       a cleanup operation removed since the previous session (BC-4.6
       style-lock cleanup, ``skill_reset``, ``skill_quit``).
    2. :func:`ensure_project_settings` — self-heals ``.claude/settings.json``
       per BC-3.13 / BUG-AUDIT-8.

    The ordering matters: directories first, then settings. The settings
    helper writes into ``project_root / .claude/`` which it creates itself,
    so it does not depend on the canonical tree. But the broader contract
    — *the canonical tree exists at every routing-cycle boundary* — means
    we run the directory pass first so any agent or routing code invoked
    after this returns can rely on the tree.
    """
    create_project_structure(project_root)
    ensure_project_settings(project_root, plugin_root)


# ---------------------------------------------------------------------------
# Entry point — spec §24.4 steps 8 & 9 dispatch (BC-3.12).
# ---------------------------------------------------------------------------


def main_new() -> None:
    """Entry point for ``python -m debrief.launcher [new|preflight]``.

    BC-3.12: three-arm dispatch on ``sys.argv[1]`` — ``preflight`` invokes
    vendor-hash verification per spec §24.4 step 8; ``new`` initializes a
    project per spec §24.4 step 9; any other value prints the usage message
    and exits with code 1.

    BC-3.11: the ``_require_json_repair()`` call below must remain the first
    executable statement so that a corrupt env surfaces the Section 9.3.1
    standardized error before any subcommand dispatch.
    """
    _require_json_repair()

    plugin_root = Path(
        os.environ.get(
            "CLAUDE_PLUGIN_ROOT",
            str(Path(__file__).parent.parent.parent),
        )
    )
    subcommand = sys.argv[1] if len(sys.argv) > 1 else ""
    project_root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()

    if subcommand == "preflight":
        preflight(plugin_root)
    elif subcommand == "new":
        new(project_root=project_root)
    elif subcommand == "ensure_project":
        # BC-3.14 / BUG-AUDIT-15: re-scaffold canonical directory tree AND
        # self-heal settings on every bare `debrief` entry. This is the
        # canonical re-entry hook called from bin/debrief's bare-invocation
        # arm — replaces the older ensure_settings entry which only handled
        # settings and left the directory tree to drift.
        ensure_project(project_root, plugin_root)
    elif subcommand == "ensure_settings":
        # BC-3.13 / BUG-AUDIT-8: self-heal `.claude/settings.json` only.
        # Retained as an additive subcommand for backward compatibility with
        # any caller that invoked it directly. New code should call
        # `ensure_project` instead, which is a strict superset.
        ensure_project_settings(project_root, plugin_root)
    else:
        print(f"Unknown subcommand: {subcommand!r}", file=sys.stderr)
        print(
            "Usage: python -m debrief.launcher [new|preflight|ensure_project|ensure_settings] [project_root]",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main_new()
