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
import re
import shutil
import sys
from dataclasses import dataclass, field
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


def check_duration(
    archetypes_path: Path, archetype: str, minutes: float,
) -> tuple[bool, str]:
    """Validate a user-specified duration against an archetype's time_range.

    BUG-AUDIT-59 / BUG-ST-1: Provides a programmatic check that the
    consultant (or CLI) can call to flag out-of-range durations.

    Returns (in_range, message). If in_range is False, message contains
    a warning string.
    """
    import re as _re

    data: dict = json.loads(archetypes_path.read_text(encoding="utf-8"))
    entry = data.get(archetype)
    if entry is None:
        return False, f"Unknown archetype: {archetype}"

    time_range = entry.get("time_range", "any")
    if time_range == "any":
        return True, f"{archetype} accepts any duration."

    m = _re.match(r"(\d+)\s*-\s*(\d+)", time_range)
    if not m:
        return True, f"Could not parse time_range '{time_range}'; skipping check."

    lo, hi = int(m.group(1)), int(m.group(2))
    if minutes < lo:
        return False, (
            f"WARNING: {minutes:.0f} min is below {archetype} range "
            f"({lo}-{hi} min). Consider adjusting."
        )
    if minutes > hi:
        return False, (
            f"WARNING: {minutes:.0f} min is above {archetype} range "
            f"({lo}-{hi} min). Consider adjusting."
        )
    return True, f"{minutes:.0f} min is within {archetype} range ({lo}-{hi} min)."


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

    # BUG-AUDIT-45: copy debrief_config.json template if not already present
    config_template = plugin_root / "templates" / "debrief_config.json"
    config_dest = project_root / "debrief_config.json"
    if config_template.exists() and not config_dest.exists():
        shutil.copy2(config_template, config_dest)

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

    # BUG-AUDIT-45: read debrief_config.json and merge model + permission
    # settings into the Claude Code settings. This makes model selection
    # and permission bypass work via native Claude Code mechanisms.
    config_path = project_root / "debrief_config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            config = {}

        # Model settings
        models = config.get("models", {})
        session_model = models.get("session")
        subagent_model = models.get("subagents")

        if session_model:
            data["model"] = session_model
        if subagent_model:
            env = data.get("env")
            if not isinstance(env, dict):
                env = {}
                data["env"] = env
            env["CLAUDE_CODE_SUBAGENT_MODEL"] = subagent_model

        # Permission settings
        permissions = config.get("permissions", {})
        if permissions.get("bypass", False):
            data["defaultMode"] = "bypassPermissions"
        elif "defaultMode" in data and data["defaultMode"] == "bypassPermissions":
            # Config says bypass=false but settings had it — remove
            del data["defaultMode"]

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
# Cross-platform LibreOffice discovery (BUG-AUDIT-42)
# ---------------------------------------------------------------------------

_SOFFICE_KNOWN_PATHS: list[str] = [
    # macOS
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    # Linux (distro packages)
    "/usr/bin/soffice",
    "/usr/lib/libreoffice/program/soffice",
    "/usr/local/bin/soffice",
    # Linux (snap)
    "/snap/bin/libreoffice.soffice",
    # Windows
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]

_INSTALL_INSTRUCTIONS = {
    "Darwin": (
        "Install LibreOffice from https://www.libreoffice.org/download/ "
        "or run: brew install --cask libreoffice"
    ),
    "Linux": (
        "Install LibreOffice via your package manager:\n"
        "  Debian/Ubuntu: sudo apt install libreoffice\n"
        "  Fedora/RHEL:   sudo dnf install libreoffice"
    ),
    "Windows": (
        "Install LibreOffice from https://www.libreoffice.org/download/ "
        "and ensure it is added to your system PATH."
    ),
}


def discover_soffice(project_root: Path) -> Path:
    """Find the LibreOffice ``soffice`` binary. Cross-platform.

    Strategy:
    1. Check persisted path in ``.debrief/soffice_path``.
    2. ``shutil.which("soffice")`` (works if on PATH).
    3. OS-specific known install locations.
    4. Persist the discovered path for subsequent runs.
    5. Raise FileNotFoundError with per-OS install instructions if not found.
    """
    import platform

    persist_file = project_root / ".debrief" / "soffice_path"

    # 1. Check persisted path
    if persist_file.is_file():
        persisted = Path(persist_file.read_text(encoding="utf-8").strip())
        if persisted.is_file():
            return persisted

    # 2. shutil.which (cross-platform PATH search)
    which_result = shutil.which("soffice")
    if which_result:
        found = Path(which_result)
        persist_file.parent.mkdir(parents=True, exist_ok=True)
        persist_file.write_text(str(found), encoding="utf-8")
        return found

    # 3. OS-specific known locations
    for candidate in _SOFFICE_KNOWN_PATHS:
        p = Path(candidate)
        if p.is_file():
            persist_file.parent.mkdir(parents=True, exist_ok=True)
            persist_file.write_text(str(p), encoding="utf-8")
            return p

    # 4. Not found — fail with per-OS instructions
    os_name = platform.system()
    instructions = _INSTALL_INSTRUCTIONS.get(
        os_name, _INSTALL_INSTRUCTIONS.get("Linux", "Install LibreOffice.")
    )
    raise FileNotFoundError(
        f"LibreOffice (soffice) not found. Debrief requires LibreOffice "
        f"for PPTX reference import.\n{instructions}"
    )


# ---------------------------------------------------------------------------
# Memory architecture — rewrite agent + rewrite_brief CLI
# (BUG-AUDIT-80 Cycle 2 Phase 2 / BC-3.18 / BC-5.19 /
# REQ-MEMORY-REWRITE-1..4).
#
# Phase 2 ships the rewrite_brief subcommand: extracts the agent-card
# system prompt, builds the user message from dialog + timeline (and
# bootstrap brief on first run), calls the Anthropic API, validates
# the output, and atomically writes deck_brief.md + output/audience.yaml.
# The PreCompact hook wiring (Phase 4) will invoke this CLI; Phase 2
# tests exercise it via mocked API calls.
# ---------------------------------------------------------------------------


_DECK_BRIEF_REL = "deck_brief.md"
_AUDIENCE_YAML_REL = "output/audience.yaml"
_REWRITE_ERRORS_REL = ".debrief/rewrite_errors.jsonl"
_REWRITER_AGENT_VERSION = "v1"


_CANONICAL_BRIEF_SECTIONS = [
    "## Audience",
    "## Room composition",
    "## Intent",
    "## Duration",
    "## Prior decisions",
    "## Open questions",
    "## Content Signals",
]


def extract_agent_card(card_path: Path) -> tuple[str, str]:
    """Parse an agent-card markdown file and return (model, system_prompt).

    Frontmatter is YAML between two ``---`` delimiters at the top of
    the file. The ``model`` key is required. The body (everything
    after the closing ``---``) is the system prompt.

    Raises ``ValueError`` on malformed frontmatter or missing model.
    """
    text = card_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(
            f"agent card {card_path} missing opening --- frontmatter"
        )
    # Find closing ---
    closing_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_idx = i
            break
    if closing_idx is None:
        raise ValueError(
            f"agent card {card_path} missing closing --- frontmatter"
        )
    fm_lines = lines[1:closing_idx]
    body_lines = lines[closing_idx + 1:]
    # Light-touch frontmatter parse — extract model key by line match.
    # We avoid pulling in PyYAML for a trivial case.
    model: Optional[str] = None
    for fm_line in fm_lines:
        s = fm_line.strip()
        if s.startswith("model:"):
            model = s.split(":", 1)[1].strip()
            # Strip surrounding quotes if any.
            if len(model) >= 2 and model[0] == model[-1] and model[0] in ("'", '"'):
                model = model[1:-1]
            break
    if not model:
        raise ValueError(
            f"agent card {card_path} frontmatter missing 'model:' field"
        )
    body = "\n".join(body_lines).strip()
    return model, body


def build_rewrite_inputs(
    dialog: list[dict],
    timeline: list[dict],
    prior_brief: Optional[str] = None,
) -> str:
    """Format dialog + timeline + (optional) prior brief into the
    user-message body for the rewrite call.

    The format is structured-but-simple: three labeled sections, each
    a JSON-serialized list (or the prior brief verbatim). The agent
    card's system prompt explains what each section is.
    """
    parts: list[str] = []
    if prior_brief is not None:
        parts.append(
            "## BOOTSTRAP — prior deck_brief.md\n\n"
            "This is the existing brief. Use it for stylistic continuity "
            "on this first rewrite. It will NOT be provided on "
            "subsequent rewrites — those are strictly source-derived.\n\n"
            f"```markdown\n{prior_brief}\n```\n"
        )
    parts.append(
        "## DIALOG ARCHIVE — every user turn + every consultant reply\n\n"
        f"```jsonl\n"
        + "\n".join(json.dumps(e, ensure_ascii=False) for e in dialog)
        + "\n```\n"
    )
    parts.append(
        "## EVENT TIMELINE — typed events\n\n"
        f"```jsonl\n"
        + "\n".join(json.dumps(e, ensure_ascii=False) for e in timeline)
        + "\n```\n"
    )
    parts.append(
        "Produce the new `deck_brief.md` per the canonical structure "
        "and discipline rules in your system prompt. Output the "
        "brief markdown directly — no preamble, no postscript."
    )
    return "\n".join(parts)


def validate_brief_structure(text: str) -> None:
    """Validate that ``text`` conforms to the canonical brief structure.

    The brief MUST start with ``# Deck Brief`` and contain only the
    canonical top-level sections (subset is allowed; supersets are
    not). Raises ``ValueError`` on violations.
    """
    if not text.strip().startswith("# Deck Brief"):
        raise ValueError(
            "brief must start with '# Deck Brief' heading"
        )
    # Find every top-level `## ` heading and check it's in the
    # canonical set.
    found_sections: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            found_sections.append(line.rstrip())
    canonical_set = set(_CANONICAL_BRIEF_SECTIONS)
    extras = [h for h in found_sections if h not in canonical_set]
    if extras:
        raise ValueError(
            f"brief contains non-canonical top-level sections: "
            f"{extras}. Canonical set: {_CANONICAL_BRIEF_SECTIONS}"
        )


def extract_roster_yaml(brief_text: str) -> Optional[str]:
    """Extract the YAML block under ``### Roster`` inside ``## Audience``.

    Returns the YAML body (without the fence delimiters), or None when
    the brief has no roster (which is allowed during early discovery
    per the rewriter's discipline rule 4).
    """
    # Locate "### Roster" inside the Audience section.
    idx = brief_text.find("### Roster")
    if idx < 0:
        return None
    # From there, find the next ```yaml fence.
    after_heading = brief_text[idx:]
    fence_open = re.search(r"```yaml\s*\n", after_heading)
    if fence_open is None:
        return None
    body_start = fence_open.end()
    fence_close = re.search(r"\n```", after_heading[body_start:])
    if fence_close is None:
        return None
    body_end = body_start + fence_close.start()
    return after_heading[body_start:body_end]


def validate_roster_yaml(yaml_text: str) -> None:
    """Parse the roster YAML and validate the BC-2.17 / BC-5.19 schema:
    each entry has non-empty ``name`` and ``role`` keys.

    We use a light hand-rolled parser to avoid the PyYAML dependency
    in Phase 2 — the format is constrained (only ``name``, ``role``,
    and the recommended optional keys; values are strings).

    Raises ``ValueError`` on schema violations.
    """
    # Hand-rolled minimal YAML for the audience-roster shape:
    #   audience:
    #     - name: Alice
    #       role: engineer
    #       location: Rome
    #       ...
    lines = yaml_text.splitlines()
    if not any(line.strip().startswith("audience:") for line in lines):
        raise ValueError(
            "roster YAML missing 'audience:' top-level key"
        )

    entries: list[dict[str, str]] = []
    current: Optional[dict[str, str]] = None
    in_audience = False
    for raw_line in lines:
        s = raw_line.rstrip()
        if not s.strip():
            continue
        stripped_left = s.lstrip()
        if stripped_left == "audience:" and not s.startswith(" "):
            in_audience = True
            continue
        if not in_audience:
            continue
        if stripped_left.startswith("- "):
            # New entry.
            if current is not None:
                entries.append(current)
            current = {}
            after_dash = stripped_left[2:].strip()
            if ":" in after_dash:
                k, v = after_dash.split(":", 1)
                current[k.strip()] = v.strip()
        elif current is not None and ":" in stripped_left:
            k, v = stripped_left.split(":", 1)
            current[k.strip()] = v.strip()
    if current is not None:
        entries.append(current)

    if not entries:
        # An audience: section with zero entries is acceptable — the
        # rewriter is allowed to omit the roster entirely. If it
        # emitted the heading + empty list, treat as no roster.
        return
    for i, entry in enumerate(entries):
        if not entry.get("name"):
            raise ValueError(
                f"roster entry {i} missing required 'name' key"
            )
        if not entry.get("role"):
            raise ValueError(
                f"roster entry {i} missing required 'role' key"
            )


def call_rewrite_agent(
    model: str,
    system_prompt: str,
    user_message: str,
) -> str:
    """Call the Anthropic API with the given system prompt and user
    message. Return the model's response text.

    Lazy import of the ``anthropic`` SDK so a missing dependency
    surfaces as ImportError that the caller logs per
    REQ-MEMORY-REWRITE-4 rather than crashing on module import.

    Tests mock this function entirely.
    """
    import anthropic  # type: ignore[import]

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    # Concatenate text blocks from the response.
    parts: list[str] = []
    for block in response.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts)


def log_rewrite_error(
    project_root: Path,
    *,
    trigger: str,
    error_class: str,
    error_message: str,
    transcript_path: Optional[str] = None,
) -> None:
    """Append a failure entry to ``.debrief/rewrite_errors.jsonl``.

    Schema per REQ-MEMORY-REWRITE-4:
    ``{"timestamp": "...", "trigger": "PreCompact" | "/debrief:quit" |
       "/debrief:refresh-brief", "error_class": "...",
       "error_message": "...", "transcript_path": "..." | null}``
    """
    path = project_root / _REWRITE_ERRORS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "trigger": trigger,
        "error_class": error_class,
        "error_message": error_message,
        "transcript_path": transcript_path,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _atomic_write_text(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically: .tmp + fsync + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    fd = os.open(str(tmp_path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rename(tmp_path, path)


def main_rewrite_brief(
    project_root: Path,
    *,
    trigger: str = "/debrief:refresh-brief",
    plugin_root: Optional[Path] = None,
) -> None:
    """Entry point for ``python -m debrief.launcher rewrite_brief
    [--project-root PATH] [--trigger ...]``.

    Reads the rewriter agent-card, builds the user message from
    dialog + timeline (+ bootstrap brief on first run), calls the
    Anthropic API via ``call_rewrite_agent``, validates the output,
    and atomically writes ``deck_brief.md`` + ``output/audience.yaml``.

    On any failure path (missing card, API error, validation failure,
    write error), the function logs to ``.debrief/rewrite_errors.jsonl``
    via ``log_rewrite_error`` and exits 0 per REQ-MEMORY-REWRITE-4 —
    NEVER block compaction.

    See BC-3.18 / BC-5.19 / REQ-MEMORY-REWRITE-1..4 / BUG-AUDIT-80.
    """
    project_root = project_root.resolve()

    # 0. PreCompact stdin envelope: when invoked from the PreCompact
    # hook, Claude Code passes a JSON object on stdin with a
    # `transcript_path` field. We read the transcript and append any
    # new turns to .debrief/dialog.jsonl BEFORE running the rewrite,
    # so the rewrite sees the freshest archive.
    #
    # Stdin handling is defensive: when the launcher is invoked
    # interactively (sys.stdin.isatty() is True) or under pytest's
    # captured-stdin (where read() raises ValueError), we skip the
    # transcript capture silently — only the explicit hook-invocation
    # path with a real piped JSON envelope counts.
    if trigger == "PreCompact":
        stdin_text: Optional[str] = None
        try:
            if not sys.stdin.isatty():
                stdin_text = sys.stdin.read()
        except (ValueError, OSError):
            # pytest captures stdin in a way that raises ValueError on
            # read; an interactive terminal without input may also
            # raise. Either case means "no envelope provided" — skip
            # the capture, do not log an error.
            stdin_text = None
        if stdin_text and stdin_text.strip():
            try:
                envelope = json.loads(stdin_text)
                transcript_path_str = envelope.get("transcript_path")
                if isinstance(transcript_path_str, str) and transcript_path_str:
                    append_dialog_turns_from_transcript(
                        project_root, Path(transcript_path_str)
                    )
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                log_rewrite_error(
                    project_root,
                    trigger=trigger,
                    error_class="transcript_capture_error",
                    error_message=str(exc),
                )
                # Continue anyway — the rewrite still runs against the
                # existing dialog archive (just without the new turns).

    # 1. Resolve agent card path.
    if plugin_root is None:
        plugin_root_str = os.environ.get("CLAUDE_PLUGIN_ROOT")
        if plugin_root_str:
            plugin_root = Path(plugin_root_str)
        else:
            # Fallback: assume workspace layout (delivered layout puts
            # agents at <repo>/agents; workspace at src/unit_1/agents).
            this_file = Path(__file__).resolve()
            workspace_card = (
                this_file.parent.parent / "unit_1" / "agents" / "rewriter.md"
            )
            delivered_card = this_file.parent.parent.parent / "agents" / "rewriter.md"
            if workspace_card.is_file():
                plugin_root = workspace_card.parent.parent.parent  # src/unit_1
            elif delivered_card.is_file():
                plugin_root = delivered_card.parent.parent
            else:
                plugin_root = this_file.parent.parent.parent

    # 2. Read the agent card.
    card_path = plugin_root / "agents" / "rewriter.md"
    if not card_path.is_file():
        # Try the workspace fallback path.
        workspace_alt = (
            Path(__file__).resolve().parent.parent / "unit_1" / "agents" / "rewriter.md"
        )
        if workspace_alt.is_file():
            card_path = workspace_alt
    try:
        model, system_prompt = extract_agent_card(card_path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        log_rewrite_error(
            project_root,
            trigger=trigger,
            error_class="agent_card_error",
            error_message=f"failed to read rewriter card at {card_path}: {exc}",
        )
        sys.exit(0)

    # 3. Detect bootstrap.
    meta = _read_rewrite_metadata(project_root)
    is_bootstrap = not meta.get("bootstrap_complete", False)
    prior_brief: Optional[str] = None
    brief_path = project_root / _DECK_BRIEF_REL
    if is_bootstrap and brief_path.is_file():
        try:
            prior_brief = brief_path.read_text(encoding="utf-8")
        except OSError as exc:
            # Read failure is logged but doesn't block the rewrite —
            # we proceed without a bootstrap (treat as no prior brief).
            log_rewrite_error(
                project_root,
                trigger=trigger,
                error_class="bootstrap_read_error",
                error_message=f"failed to read prior brief: {exc}",
            )
            prior_brief = None

    # 4. Build inputs.
    dialog = read_dialog_archive(project_root)
    timeline = read_event_timeline(project_root)
    user_message = build_rewrite_inputs(dialog, timeline, prior_brief)

    # 5. Call API.
    try:
        response_text = call_rewrite_agent(model, system_prompt, user_message)
    except Exception as exc:  # noqa: BLE001 — log and exit per contract
        log_rewrite_error(
            project_root,
            trigger=trigger,
            error_class=type(exc).__name__,
            error_message=str(exc),
        )
        sys.exit(0)

    # 6. Validate brief structure.
    try:
        validate_brief_structure(response_text)
    except ValueError as exc:
        log_rewrite_error(
            project_root,
            trigger=trigger,
            error_class="brief_structure_invalid",
            error_message=str(exc),
        )
        sys.exit(0)

    # 7. Extract + validate roster YAML (may be absent during discovery).
    roster_yaml = extract_roster_yaml(response_text)
    if roster_yaml is not None:
        try:
            validate_roster_yaml(roster_yaml)
        except ValueError as exc:
            log_rewrite_error(
                project_root,
                trigger=trigger,
                error_class="roster_yaml_invalid",
                error_message=str(exc),
            )
            sys.exit(0)

    # 8. Atomic dual write. Brief first, then audience.yaml. If either
    # rename fails, the prior versions remain.
    try:
        _atomic_write_text(brief_path, response_text)
        if roster_yaml is not None:
            audience_path = project_root / _AUDIENCE_YAML_REL
            _atomic_write_text(
                audience_path,
                f"audience:\n{roster_yaml.rstrip()}\n"
                if not roster_yaml.lstrip().startswith("audience:")
                else roster_yaml.rstrip() + "\n",
            )
    except OSError as exc:
        log_rewrite_error(
            project_root,
            trigger=trigger,
            error_class="write_failure",
            error_message=str(exc),
        )
        sys.exit(0)

    # 9. Update watermark.
    meta["last_rewrite_timestamp"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    meta["agent_version"] = _REWRITER_AGENT_VERSION
    meta["model"] = model
    meta["bootstrap_complete"] = True
    _write_rewrite_metadata(project_root, meta)

    sys.exit(0)


# ---------------------------------------------------------------------------
# Memory architecture — dialog archive + recall (BUG-AUDIT-79 Cycle 2 Phase 1
# / BC-2.17 / BC-3.19 / REQ-MEMORY-DIALOG-1 / REQ-MEMORY-RECALL-1).
#
# Phase 1 ships the per-turn capture API + the recall CLI. The PreCompact
# hook wiring (Phase 4) and the rewrite agent (Phase 2) are NOT here —
# tests synthesize archives via append_dialog_turn() and exercise recall.
# ---------------------------------------------------------------------------


_DIALOG_ARCHIVE_REL = ".debrief/dialog.jsonl"
_REWRITE_METADATA_REL = ".debrief/rewrite_metadata.json"
_TIMELINE_REL = "output/timeline.jsonl"


def _read_rewrite_metadata(project_root: Path) -> dict:
    """Read the watermark file; return defaults on missing/malformed."""
    path = project_root / _REWRITE_METADATA_REL
    if not path.is_file():
        return {
            "last_archived_turn": 0,
            "last_rewrite_timestamp": None,
            "agent_version": None,
            "model": None,
            "bootstrap_complete": False,
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "last_archived_turn": 0,
            "last_rewrite_timestamp": None,
            "agent_version": None,
            "model": None,
            "bootstrap_complete": False,
        }


def _write_rewrite_metadata(project_root: Path, data: dict) -> None:
    """Atomically write the watermark file."""
    path = project_root / _REWRITE_METADATA_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    fd = os.open(str(tmp_path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rename(tmp_path, path)


def append_dialog_turn(
    project_root: Path,
    *,
    role: str,
    responding_agent: str,
    content: str,
    metadata: Optional[dict] = None,
) -> int:
    """Append one turn to ``.debrief/dialog.jsonl`` and advance the
    ``last_archived_turn`` watermark in ``.debrief/rewrite_metadata.json``.

    Per BC-2.17 / REQ-MEMORY-DIALOG-1, callers MUST honor the capture
    rule (every user turn + only consultant replies; subagent replies
    excluded). This function does NOT enforce the capture rule — it
    is the per-turn append primitive that callers (the PreCompact
    hook in Phase 4, regression tests in Phase 1) wrap.

    The function is atomic on a single archive: it computes the next
    turn number from the watermark, writes the JSONL line via append,
    then advances the watermark. The watermark file is itself written
    atomically (.tmp + fsync + rename).

    Args:
        project_root: Project root directory.
        role: One of ``"user"`` | ``"consultant"`` (the schema requires
            this; callers pass other values at their own risk —
            validation is light-touch in Phase 1).
        responding_agent: Which agent the user was addressing
            (``"consultant"`` | ``"stylist"`` | ``"slide-maker"`` |
            ``"visual-qa"`` | ``"bug-diagnostic"`` | etc.).
        content: Verbatim turn body.
        metadata: Optional metadata object; MUST contain ``phase`` and
            ``sub_phase`` per BC-2.17, but the function does not
            enforce. Defaults to an empty dict if None.

    Returns:
        The turn number assigned to this entry (monotonic from the
        prior watermark).

    See BC-2.17 and BUG-AUDIT-79.
    """
    project_root = project_root.resolve()
    metadata_obj = dict(metadata) if metadata else {}

    meta = _read_rewrite_metadata(project_root)
    next_turn = int(meta.get("last_archived_turn", 0)) + 1
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entry = {
        "turn": next_turn,
        "timestamp": timestamp,
        "role": role,
        "responding_agent": responding_agent,
        "content": content,
        "metadata": metadata_obj,
    }

    archive_path = project_root / _DIALOG_ARCHIVE_REL
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with archive_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Advance the watermark. Other fields preserved.
    meta["last_archived_turn"] = next_turn
    _write_rewrite_metadata(project_root, meta)

    return next_turn


def read_dialog_archive(project_root: Path) -> list[dict]:
    """Return all dialog entries in archive order. Empty list when
    the archive is missing or unreadable.
    """
    path = (project_root / _DIALOG_ARCHIVE_REL).resolve()
    if not path.is_file():
        return []
    entries: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return entries


def append_dialog_turns_from_transcript(
    project_root: Path,
    transcript_path: Path,
) -> int:
    """Parse a Claude Code transcript and append new turns to
    ``.debrief/dialog.jsonl`` per the Q4 capture rule.

    Capture rule (BC-2.17 / REQ-MEMORY-DIALOG-1):

    * Every user turn is captured (regardless of which agent the user
      was addressing).
    * Assistant turns are captured with ``responding_agent="consultant"``
      by default. Subagent-only assistant turns (when distinguishable
      from the transcript) are skipped.

    The Claude Code transcript is JSONL with at minimum ``role`` (one
    of ``"user"`` / ``"assistant"``) and ``content`` (string or list
    of content blocks). The parser is tolerant of additional fields.

    Idempotence is provided by the watermark: only turns numbered
    GREATER than ``last_archived_turn`` (relative to the transcript's
    ordering) are appended. The watermark advances with each append.

    Returns the count of newly appended turns.

    See BC-2.17, BC-3.18, REQ-MEMORY-DIALOG-1, and BUG-AUDIT-82.
    """
    project_root = project_root.resolve()
    if not transcript_path.is_file():
        return 0
    try:
        text = transcript_path.read_text(encoding="utf-8")
    except OSError:
        return 0

    # Parse all transcript entries first so we can index against the
    # watermark (which counts only entries that pass the capture rule).
    raw_entries: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw_entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    meta = _read_rewrite_metadata(project_root)
    already_archived = int(meta.get("last_archived_turn", 0))

    written = 0
    captured_index = 0  # Counts entries that pass the capture rule.
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        if role not in ("user", "assistant"):
            continue
        # Capture rule: user turns always; assistant turns default to
        # consultant unless the entry explicitly names a different
        # subagent (e.g., via a "subagent_type" field, when present).
        responding_agent = "consultant"
        if role == "assistant":
            sub_type = entry.get("subagent_type") or entry.get("agent")
            if isinstance(sub_type, str) and sub_type and sub_type != "consultant":
                # Subagent reply — skip per Q4 capture rule.
                continue
        else:
            # User turn — preserve responding_agent if the transcript
            # tagged it (so a future rewrite can know which subagent
            # the user was addressing).
            sub_type = entry.get("responding_agent") or entry.get("subagent_type")
            if isinstance(sub_type, str) and sub_type:
                responding_agent = sub_type
        captured_index += 1
        if captured_index <= already_archived:
            continue
        # Extract content as a single string (Claude Code content can
        # be a list of content blocks; concatenate text blocks).
        content = entry.get("content", "")
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    text_field = block.get("text") or block.get("content")
                    if isinstance(text_field, str):
                        parts.append(text_field)
                elif isinstance(block, str):
                    parts.append(block)
            content_str = "".join(parts)
        elif isinstance(content, str):
            content_str = content
        else:
            content_str = str(content)
        # Build metadata from any tagged fields the transcript provides.
        metadata: dict = {}
        for key in ("phase", "sub_phase", "session_id", "timestamp"):
            v = entry.get(key)
            if isinstance(v, str):
                metadata[key] = v
        # Use append_dialog_turn for atomic per-turn append + watermark
        # advancement. (Each call advances the watermark by 1; the
        # captured_index logic above ensures we don't replay turns
        # already archived.)
        append_dialog_turn(
            project_root,
            role=role,
            responding_agent=responding_agent,
            content=content_str,
            metadata=metadata,
        )
        written += 1
    return written


def append_timeline_event(
    project_root: Path,
    *,
    event: str,
    payload: dict,
    turn: Optional[int] = None,
) -> None:
    """Append one event to ``output/timeline.jsonl`` per BC-2.18.

    Schema (REQ-MEMORY-TIMELINE-1):

    * ``event`` (str) — event type from the BC-2.18 enumeration
      (extensible; readers MUST tolerate unknown types).
    * ``timestamp`` (str) — UTC ISO 8601 with ``Z`` suffix; written
      by this function from ``datetime.now(timezone.utc)``.
    * ``turn`` (int, optional) — the dialog turn at which the event
      was captured; absent for system-emitted events without a turn.
    * ``payload`` (dict) — event-type-specific fields; the function
      does not validate payload shape. Callers are responsible for
      passing the right keys for the event type.

    Concurrency: multiple emitters may call this function from
    different processes simultaneously. POSIX guarantees atomicity
    of single ``write()`` calls under ``PIPE_BUF`` (4 KiB on most
    systems). Each event line is well under that limit in practice
    (~200-500 bytes), so no explicit file-locking is needed.

    See BC-2.18, REQ-MEMORY-TIMELINE-1, and BUG-AUDIT-81.
    """
    path = project_root / _TIMELINE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry: dict = {
        "event": event,
        "timestamp": timestamp,
        "payload": payload,
    }
    if turn is not None:
        entry["turn"] = int(turn)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def read_event_timeline(project_root: Path) -> list[dict]:
    """Return all timeline entries in archive order. Empty list when
    the file is missing or unreadable. Phase 3 will populate; Phase 1
    only reads.
    """
    path = (project_root / _TIMELINE_REL).resolve()
    if not path.is_file():
        return []
    entries: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return entries


@dataclass
class RecallHit:
    """One match from a recall search.

    ``source`` is ``"dialog"`` | ``"timeline"`` indicating which
    archive the match came from.
    ``match`` is the full entry that matched.
    ``context_before`` and ``context_after`` are up to 2 entries each
    from the same archive, immediately adjacent to the match.
    """

    source: str
    match: dict
    context_before: list[dict] = field(default_factory=list)
    context_after: list[dict] = field(default_factory=list)


def _entry_matches_query(entry: dict, query_lower: str) -> bool:
    """Return True if any string-valued field in the entry contains
    the query (case-insensitive). Recursively descends into nested
    dicts/lists so payload fields (timeline) and metadata (dialog)
    are searched too.
    """
    def _walk(node: object) -> bool:
        if isinstance(node, str):
            return query_lower in node.lower()
        if isinstance(node, dict):
            return any(_walk(v) for v in node.values())
        if isinstance(node, list):
            return any(_walk(v) for v in node)
        return False

    return _walk(entry)


def _collect_context(
    entries: list[dict], match_index: int, n: int = 2
) -> tuple[list[dict], list[dict]]:
    """Return up to ``n`` entries before and after the match index."""
    before = entries[max(0, match_index - n): match_index]
    after = entries[match_index + 1: match_index + 1 + n]
    return list(before), list(after)


def recall(project_root: Path, query: str) -> list[RecallHit]:
    """Search both dialog and timeline archives for ``query``.

    Returns a list of ``RecallHit`` records, dialog hits first then
    timeline hits, each in archive order.

    Match rule: case-insensitive literal substring against any string-
    valued field in the entry (recursively). Each match contributes
    one hit with ±2 entries of context from the same archive.

    See BC-3.19 and BUG-AUDIT-79.
    """
    if not query:
        return []
    q = query.lower()
    hits: list[RecallHit] = []

    dialog = read_dialog_archive(project_root)
    for i, entry in enumerate(dialog):
        if _entry_matches_query(entry, q):
            before, after = _collect_context(dialog, i, n=2)
            hits.append(
                RecallHit(
                    source="dialog",
                    match=entry,
                    context_before=before,
                    context_after=after,
                )
            )

    timeline = read_event_timeline(project_root)
    for i, entry in enumerate(timeline):
        if _entry_matches_query(entry, q):
            before, after = _collect_context(timeline, i, n=2)
            hits.append(
                RecallHit(
                    source="timeline",
                    match=entry,
                    context_before=before,
                    context_after=after,
                )
            )

    return hits


def _hit_to_dict(hit: RecallHit) -> dict:
    return {
        "source": hit.source,
        "match": hit.match,
        "context_before": hit.context_before,
        "context_after": hit.context_after,
    }


def main_recall(project_root: Path, query: str) -> None:
    """Entry point for ``python -m debrief.launcher recall <query>
    [--project-root PATH]``.

    Output format:

    * When stdout is a TTY: pretty-printed table with one section per
      hit, source-labeled, showing match + context entries.
    * When stdout is not a TTY (piped, redirected): JSON list of
      hits per the BC-3.19 schema.

    Exit codes (BC-3.19):

    * 0 — search ran (matches OR no matches).
    * 1 — a project file is missing or malformed AND we cannot fall
      back gracefully. Phase 1's read helpers tolerate missing files
      so this exit code is reserved for future strictness; in Phase
      1 it is effectively unreachable.
    * 3 — usage error. Argparse handles via SystemExit(2) on bad
      args; we promote that to 3 for consistency with the BC.

    See BC-3.19 and BUG-AUDIT-79.
    """
    project_root = project_root.resolve()
    hits = recall(project_root, query)

    if sys.stdout.isatty():
        # Pretty-printed table for humans.
        if not hits:
            print(f"No matches for: {query!r}")
            sys.exit(0)
        for hit in hits:
            print(f"--- [{hit.source}] match ---")
            for before in hit.context_before:
                _print_recall_context_line(before, hit.source, marker=" ")
            _print_recall_context_line(hit.match, hit.source, marker=">")
            for after in hit.context_after:
                _print_recall_context_line(after, hit.source, marker=" ")
            print()
    else:
        # JSON for programmatic consumers.
        payload = [_hit_to_dict(h) for h in hits]
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    sys.exit(0)


def _print_recall_context_line(
    entry: dict, source: str, *, marker: str
) -> None:
    """Render one entry as a single line for the human-friendly
    pretty-printed recall output. Defensive against missing fields.
    """
    if source == "dialog":
        turn = entry.get("turn", "?")
        role = entry.get("role", "?")
        content = entry.get("content", "")
        # Trim long content for the table view; full content is in JSON
        # when piped.
        snippet = content[:120] + ("…" if len(content) > 120 else "")
        print(f"{marker} T#{turn} {role}: {snippet}")
    elif source == "timeline":
        evt = entry.get("event", "?")
        ts = entry.get("timestamp", "?")
        payload = entry.get("payload", {})
        print(f"{marker} [{ts}] {evt}: {payload}")
    else:
        print(f"{marker} {entry}")


# ---------------------------------------------------------------------------
# debrief doctor — filesystem/state reconciler (BUG-AUDIT-75 / BC-3.15 /
# REQ-DOCTOR-1).
#
# Purpose: detect drift between on-disk slide HTML files and the SlideRecord
# entries in deck_state.json. Drift is silent until export/handout time —
# this check surfaces it at session start (via the consultant's dispatch)
# or on demand from the CLI.
# ---------------------------------------------------------------------------


@dataclass
class DriftReport:
    """Structured report of filesystem <-> deck_state drift.

    ``orphan_files``: slug stems of ``slides/*.html`` files with no
        matching ``SlideRecord`` in ``deck_state.json``. Produced by a
        slide-maker turn whose state-write was dropped (e.g., context
        compaction before the consultant wrote the record).

    ``orphan_records``: slugs in ``deck_state.slides`` with no matching
        ``slides/<slug>.html`` file. Produced by a state write that
        preceded — or survived the deletion of — its slide file.

    ``matched_count``: slugs present in both file and state.

    ``drift_detected`` is True when either orphan list is non-empty.
    """

    drift_detected: bool
    orphan_files: list[str] = field(default_factory=list)
    orphan_records: list[str] = field(default_factory=list)
    matched_count: int = 0


def _list_slide_file_stems(project_root: Path) -> list[str]:
    """Return sorted slug stems of all ``slides/*.html`` files under
    ``project_root``. Non-HTML files are ignored. Missing ``slides/`` dir
    yields an empty list (not an error — a brand-new project has none).
    """
    slides_dir = project_root / "slides"
    if not slides_dir.is_dir():
        return []
    stems: list[str] = []
    for p in slides_dir.iterdir():
        if p.is_file() and p.suffix.lower() == ".html":
            stems.append(p.stem)
    return sorted(stems)


def _list_state_slugs(project_root: Path) -> list[str]:
    """Return slugs recorded in ``deck_state.json``'s ``slides`` array,
    in the order they appear. Missing or malformed state file yields an
    empty list so the doctor can still report filesystem orphans — the
    caller decides whether an absent state is itself a problem.
    """
    state_path = project_root / "deck_state.json"
    if not state_path.is_file():
        return []
    try:
        raw = state_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return []
    slides = data.get("slides") if isinstance(data, dict) else None
    if not isinstance(slides, list):
        return []
    result: list[str] = []
    for entry in slides:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug")
        if isinstance(slug, str) and slug:
            result.append(slug)
    return result


def detect_slide_state_drift(project_root: Path) -> DriftReport:
    """Scan ``slides/*.html`` against ``deck_state.slides[*].slug`` and
    return a structured drift report.

    The comparison is pure and idempotent. The helper does NOT modify
    any file; remediation happens in ``reconstruct_slide_records_from_files``.

    See BC-3.15 and BUG-AUDIT-75.
    """
    file_stems = set(_list_slide_file_stems(project_root))
    state_slugs = set(_list_state_slugs(project_root))

    orphan_files = sorted(file_stems - state_slugs)
    orphan_records = sorted(state_slugs - file_stems)
    matched_count = len(file_stems & state_slugs)
    drift = bool(orphan_files or orphan_records)

    return DriftReport(
        drift_detected=drift,
        orphan_files=orphan_files,
        orphan_records=orphan_records,
        matched_count=matched_count,
    )


def reconstruct_slide_records_from_files(
    project_root: Path,
    slugs: list[str],
) -> int:
    """Append a minimal ``SlideRecord`` to ``deck_state.json`` for every
    slug in ``slugs`` that is not already recorded.

    Written records carry ``status="draft"``, ``qa_passed=False``,
    ``accepted_violations=[]``, and empty optional fields so the
    consultant is forced to re-vet each reconstructed slide through
    the normal red-green cycle. ``last_modified`` is the current UTC
    timestamp; ``title`` defaults to the slug.

    Idempotent: slugs already present in state are skipped; the
    function returns the count of records actually written.

    Writes atomically via ``write_deck_state``. Raises the underlying
    IO/JSON error if the state file is malformed — callers detect this
    earlier via ``detect_slide_state_drift`` (which tolerates missing
    state but this writer does not reconstruct from scratch).

    See BC-3.15 and BUG-AUDIT-75.
    """
    # Import locally — the delivered layout has these in the same
    # package as launcher.py; the workspace layout needs the sibling
    # dir on sys.path (handled by conftest in test contexts and by
    # pip install -e in production).
    try:
        from debrief_state import (  # type: ignore[import]
            read_deck_state,
            write_deck_state,
            SlideRecord,
        )
    except ImportError:
        # Fallback for delivered-as-package layouts where imports are
        # rooted differently.
        from debrief.debrief_state import (  # type: ignore[import]
            read_deck_state,
            write_deck_state,
            SlideRecord,
        )

    state = read_deck_state(project_root)
    existing = {s.slug for s in state.slides}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    written = 0
    for slug in slugs:
        if slug in existing:
            continue
        state.slides.append(
            SlideRecord(
                slug=slug,
                title=slug,
                status="draft",
                backup=False,
                content_summary=None,
                visual_approach=None,
                design_choices=None,
                forks_not_taken=None,
                user_recommendations=None,
                qa_passed=False,
                accepted_violations=[],
                last_modified=now,
                group_id=None,
                user_assets=[],
                has_math=False,
            )
        )
        existing.add(slug)
        written += 1

    if written > 0:
        write_deck_state(project_root, state)
    return written


def main_doctor(project_root: Path, *, reconstruct: bool = False) -> None:
    """Entry point for ``python -m debrief.launcher doctor
    --project-root <path> [--reconstruct]``.

    Prints a JSON report to stdout and a human-readable summary to
    stderr.

    Exit codes (REQ-DOCTOR-1):
    * 0 — no drift detected, OR drift was remediated successfully under
      ``--reconstruct``.
    * 1 — drift detected in report-only mode (scripts can key off this).
    * 2 — remediation attempted under ``--reconstruct`` but failed.

    See BC-3.15 and BUG-AUDIT-75.
    """
    project_root = project_root.resolve()
    report = detect_slide_state_drift(project_root)

    if reconstruct and report.orphan_files:
        try:
            written = reconstruct_slide_records_from_files(
                project_root, report.orphan_files
            )
        except Exception as exc:  # noqa: BLE001 — surface the error
            print(
                f"debrief doctor: reconstruction failed: {exc}",
                file=sys.stderr,
            )
            sys.exit(2)
        # Re-scan after the write so the final report reflects the fix.
        report = detect_slide_state_drift(project_root)
        print(
            f"debrief doctor: reconstructed {written} SlideRecord entries "
            f"with status=\"draft\"; re-vet each slide via the normal "
            f"red-green cycle.",
            file=sys.stderr,
        )

    summary = {
        "drift_detected": report.drift_detected,
        "orphan_files": report.orphan_files,
        "orphan_records": report.orphan_records,
        "matched_count": report.matched_count,
    }
    print(json.dumps(summary, indent=2))

    if report.drift_detected:
        file_count = len(report.orphan_files)
        rec_count = len(report.orphan_records)
        print(
            f"debrief doctor: DRIFT — "
            f"{file_count} orphan HTML file(s), "
            f"{rec_count} orphan SlideRecord(s), "
            f"{report.matched_count} matched.",
            file=sys.stderr,
        )
        if not reconstruct:
            print(
                "Run with --reconstruct to add minimal draft SlideRecord "
                "entries for orphan files.",
                file=sys.stderr,
            )
        sys.exit(1)

    print(
        f"debrief doctor: OK — {report.matched_count} slide(s) in sync.",
        file=sys.stderr,
    )
    sys.exit(0)


# ---------------------------------------------------------------------------
# debrief commands — live command-surface enumeration
# (BUG-AUDIT-76 / BC-3.17 / REQ-CONSULT-CMD-SURFACE-1).
#
# Purpose: the consultant needs a machine-readable list of installed
# plugin commands so its dispatch-related replies stay grounded in the
# actual surface, not in the hand-maintained table in its agent card.
# After context compaction, the consultant's in-context memory is
# lossy; re-invoking this enumeration makes "does Debrief have X?"
# answerable from the live filesystem instead of recall.
# ---------------------------------------------------------------------------


def list_commands(plugin_root: Path) -> dict[str, str]:
    """Enumerate installed plugin commands under ``<plugin_root>/commands/``.

    Returns a dict keyed by command slug (file stem) with the
    one-paragraph description that sits immediately below the
    ``# /debrief:<slug>`` heading. Parsing rule:

    * Read the file as UTF-8 text.
    * Locate the first non-blank line. It MUST be a heading of the
      form ``# /debrief:<slug>``; if not, the file is skipped.
    * Skip subsequent blank lines.
    * The first non-blank line after the heading, up to the next
      blank line, is the description. Multi-line paragraphs are
      joined with a single space.

    The function is pure and idempotent. An empty or missing
    ``<plugin_root>/commands/`` directory yields ``{}``.

    See BC-3.17 and BUG-AUDIT-76.
    """
    commands_dir = plugin_root / "commands"
    if not commands_dir.is_dir():
        return {}

    result: dict[str, str] = {}
    for path in sorted(commands_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        lines = text.splitlines()
        # Find the first non-blank line; it must be the heading.
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx >= len(lines):
            continue
        heading = lines[idx].strip()
        if not heading.startswith("# /debrief:"):
            continue
        # Extract slug from heading (prefer the heading over file stem
        # so a future rename of file-vs-heading mismatch is caught by
        # regression, not silently smoothed).
        slug_from_heading = heading[len("# /debrief:"):].strip()
        # Walk past blank lines to the first description line.
        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        # Accumulate description until next blank line.
        desc_parts: list[str] = []
        while idx < len(lines) and lines[idx].strip():
            desc_parts.append(lines[idx].strip())
            idx += 1
        description = " ".join(desc_parts).strip()
        if not description:
            # Heading without a description is a malformed doc; skip
            # rather than return an empty-value entry.
            continue
        # Key by slug from heading (authoritative per the command-file
        # convention); fall back to file stem if heading slug somehow
        # empty.
        slug = slug_from_heading or path.stem
        result[slug] = description
    return result


def main_commands(plugin_root: Path) -> None:
    """Entry point for ``python -m debrief.launcher commands
    [--plugin-root PATH]``.

    Prints a pretty-printed JSON object keyed by command slug with
    the one-paragraph description as the value. Empty dict if no
    commands directory exists. Always exits 0 — this is a read-only
    enumeration that any caller is free to consume.

    See BC-3.17 and BUG-AUDIT-76.
    """
    plugin_root = plugin_root.resolve()
    commands = list_commands(plugin_root)
    print(json.dumps(commands, indent=2, sort_keys=True))
    sys.exit(0)


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
    elif subcommand == "commands":
        # BC-3.17 / BUG-AUDIT-76: live enumeration of installed plugin
        # commands. Parses --plugin-root; default resolves from the
        # CLAUDE_PLUGIN_ROOT env var (set by Claude Code at runtime)
        # falling back to the already-derived `plugin_root` at the top
        # of main_new().
        import argparse as _ap

        _parser = _ap.ArgumentParser(
            prog="debrief.launcher commands",
            description=(
                "Enumerate installed plugin commands from "
                "<plugin_root>/commands/*.md. Prints a JSON object "
                "keyed by command slug with the one-paragraph "
                "description as the value."
            ),
        )
        _parser.add_argument(
            "--plugin-root",
            type=Path,
            default=plugin_root,
            help=(
                "Plugin root directory (default: CLAUDE_PLUGIN_ROOT "
                "env var, else the workspace root)."
            ),
        )
        _args = _parser.parse_args(sys.argv[2:])
        main_commands(_args.plugin_root)
    elif subcommand == "emit_event":
        # BC-2.18 / BUG-AUDIT-82 (Cycle 2 Phase 4) /
        # REQ-MEMORY-TIMELINE-1. Wraps append_timeline_event for
        # consultant-driven emissions (briefing_complete, slide_approved,
        # paper_attached, etc.). Deterministic code-path emitters
        # (export_done / handout_done / script_done) call
        # append_timeline_event directly per BUG-AUDIT-81.
        import argparse as _ap

        _parser = _ap.ArgumentParser(
            prog="debrief.launcher emit_event",
            description=(
                "Append a typed event to output/timeline.jsonl. For "
                "consultant-driven event emission via Bash."
            ),
        )
        _parser.add_argument(
            "--event",
            required=True,
            help=(
                "Event type. Recommended values per BC-2.18: "
                "briefing_complete, style_locked, slide_approved, "
                "slide_discarded, paper_attached, figure_selected, "
                "backup_session_started. Other values are accepted "
                "(extensible enumeration); readers tolerate unknowns."
            ),
        )
        _parser.add_argument(
            "--payload-json",
            default="{}",
            help=(
                "JSON object with event-specific fields. Default: "
                "empty object. Example for slide_approved: "
                '\'{"slug": "intro", "group_id": "g1"}\'.'
            ),
        )
        _parser.add_argument(
            "--turn",
            type=int,
            default=None,
            help=(
                "Optional dialog turn at which the event was captured. "
                "Omit for system-emitted events without a turn."
            ),
        )
        _parser.add_argument(
            "--project-root", type=Path, default=Path.cwd()
        )
        _args = _parser.parse_args(sys.argv[2:])
        try:
            payload = json.loads(_args.payload_json)
        except json.JSONDecodeError as exc:
            print(
                f"emit_event: --payload-json is not valid JSON: {exc}",
                file=sys.stderr,
            )
            sys.exit(3)
        if not isinstance(payload, dict):
            print(
                "emit_event: --payload-json must encode a JSON object",
                file=sys.stderr,
            )
            sys.exit(3)
        append_timeline_event(
            _args.project_root.resolve(),
            event=_args.event,
            payload=payload,
            turn=_args.turn,
        )
        sys.exit(0)
    elif subcommand == "rewrite_brief":
        # BC-3.18 / BUG-AUDIT-80 (Cycle 2 Phase 2) /
        # REQ-MEMORY-REWRITE-1..4. Reads agents/rewriter.md, calls
        # the Anthropic API, atomically writes deck_brief.md +
        # output/audience.yaml. Exits 0 always per contract; any
        # failure is logged to .debrief/rewrite_errors.jsonl.
        import argparse as _ap

        _parser = _ap.ArgumentParser(
            prog="debrief.launcher rewrite_brief",
            description=(
                "Rewrite deck_brief.md from the dialog archive and "
                "event timeline. Sole writer of the brief per BC-5.19."
            ),
        )
        _parser.add_argument(
            "--project-root", type=Path, default=Path.cwd()
        )
        _parser.add_argument(
            "--trigger",
            choices=[
                "PreCompact",
                "/debrief:quit",
                "/debrief:refresh-brief",
            ],
            default="/debrief:refresh-brief",
            help=(
                "Which trigger fired the rewrite. Recorded in any "
                "rewrite_errors.jsonl entry. Default assumes manual "
                "invocation by the user."
            ),
        )
        _args = _parser.parse_args(sys.argv[2:])
        main_rewrite_brief(
            _args.project_root,
            trigger=_args.trigger,
            plugin_root=plugin_root,
        )
    elif subcommand == "recall":
        # BC-3.19 / BUG-AUDIT-79 (Cycle 2 Phase 1) / REQ-MEMORY-RECALL-1.
        # Greps both .debrief/dialog.jsonl and output/timeline.jsonl for
        # the query string. Source-labeled output; pretty-table for TTYs,
        # JSON for piped consumers.
        import argparse as _ap

        _parser = _ap.ArgumentParser(
            prog="debrief.launcher recall",
            description=(
                "Search the dialog archive and event timeline for a "
                "query. Returns matches with +/-2 entries of context, "
                "source-labeled."
            ),
        )
        _parser.add_argument("query", help="Substring to search for.")
        _parser.add_argument(
            "--project-root",
            type=Path,
            default=Path.cwd(),
        )
        _args = _parser.parse_args(sys.argv[2:])
        main_recall(_args.project_root, _args.query)
    elif subcommand == "doctor":
        # BC-3.15 / BUG-AUDIT-75: filesystem <-> deck_state drift
        # reconciler. Parses --project-root and --reconstruct via a
        # local argparse pass (sys.argv has already been consumed for
        # subcommand+positional project_root in main_new; we re-parse
        # from sys.argv[2:] so flags work either ordering). Exit codes
        # per REQ-DOCTOR-1.
        import argparse as _ap

        _parser = _ap.ArgumentParser(
            prog="debrief.launcher doctor",
            description=(
                "Detect drift between slides/*.html and "
                "deck_state.slides[*].slug; optionally reconstruct "
                "missing SlideRecord entries with --reconstruct."
            ),
        )
        _parser.add_argument(
            "--project-root", type=Path, default=Path.cwd()
        )
        _parser.add_argument(
            "--reconstruct",
            action="store_true",
            help=(
                "Append minimal draft SlideRecord entries for orphan "
                "HTML files. Each reconstructed slide gets "
                "status=\"draft\" so the consultant re-vets it through "
                "the normal red-green cycle."
            ),
        )
        _args = _parser.parse_args(sys.argv[2:])
        main_doctor(
            _args.project_root,
            reconstruct=_args.reconstruct,
        )
    else:
        print(f"Unknown subcommand: {subcommand!r}", file=sys.stderr)
        print(
            "Usage: python -m debrief.launcher [new|preflight|"
            "ensure_project|ensure_settings|doctor|commands|recall|"
            "rewrite_brief|emit_event] [project_root]",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    # BUG-AUDIT-59 / BUG-ST-1: check_duration uses argparse; all other
    # subcommands (new, preflight, ensure_project, ensure_settings) are
    # handled by main_new() which parses sys.argv directly. Route
    # check_duration here; everything else falls through.
    if len(sys.argv) > 1 and sys.argv[1] == "check_duration":
        import argparse as _ap

        _parser = _ap.ArgumentParser(
            description="Debrief duration validation",
        )
        _parser.add_argument("command")  # consume "check_duration"
        _parser.add_argument("--archetype", required=True)
        _parser.add_argument("--minutes", type=float, required=True)
        _parser.add_argument("--archetypes-path", type=Path, default=None,
                             help="Path to archetypes.json (auto-detected if omitted)")
        _args = _parser.parse_args()
        _apath = _args.archetypes_path
        if _apath is None:
            _apath = Path(os.environ.get(
                "CLAUDE_PLUGIN_ROOT", ".",
            )) / "archetypes.json"
        ok, msg = check_duration(_apath, _args.archetype, _args.minutes)
        print(msg, file=sys.stderr)
        sys.exit(0 if ok else 1)
    else:
        main_new()
