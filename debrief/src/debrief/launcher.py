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
# Script writer — agent + script_writer CLI
# (BUG-AUDIT-84 Sub-cycle B / BC-3.20 / BC-5.21 / REQ-SCRIPT-WRITER-1..4).
#
# Sub-cycle B ships the agent-card invocation pattern + the six
# guardrail validators + backup-before-overwrite + atomic write.
# Sub-cycle C handles the handout simplification + auto-finalization
# at deck-complete.
# ---------------------------------------------------------------------------


_SPEAKER_SCRIPT_REL = "speaker_script.md"
_SCRIPT_BACKUPS_REL = ".debrief/script_backups"
_SCRIPT_ERRORS_REL = ".debrief/script_errors.jsonl"
_SCRIPT_WRITER_AGENT_VERSION = "v1"
_SCRIPT_WRITER_TOKEN_CAP = 200_000
_SCRIPT_WRITER_LENGTH_OVERRUN_FACTOR = 1.5
_SCRIPT_WRITER_VOICE_DRIFT_THRESHOLD = 0.5
_SCRIPT_WRITER_WORDS_PER_MINUTE = 150


def read_audience_yaml(project_root: Path) -> str:
    """Read ``output/audience.yaml`` if it exists; return empty string
    when absent. The script-writer agent receives the YAML body
    verbatim — it parses the structure itself in-context.
    """
    path = project_root / _AUDIENCE_YAML_REL
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def read_speaker_script(project_root: Path) -> Optional[str]:
    """Read ``<project_root>/speaker_script.md`` if it exists. Returns
    None when absent (no co-writer baseline to provide).
    """
    path = project_root / _SPEAKER_SCRIPT_REL
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _estimate_tokens(text: str) -> int:
    """Coarse token estimator: chars / 4. Sufficient for the 200K cap
    decision (we want comfortable headroom, not exact tokenization).
    """
    return max(0, len(text) // 4)


def truncate_dialog_to_token_cap(
    dialog: list[dict],
    fixed_inputs_text: str,
    cap_tokens: int = _SCRIPT_WRITER_TOKEN_CAP,
) -> list[dict]:
    """Head-truncate the dialog archive (oldest turns dropped first)
    until the assembled inputs fit within the token cap.

    ``fixed_inputs_text`` is a string approximation of every other
    input (brief + audience.yaml + timeline + slides + baseline
    speaker_script + the JSON envelope around external_documents).
    The caller assembles this once; we estimate tokens and trim
    the dialog until the total fits.

    Returns the (possibly truncated) dialog list. Order preserved.
    """
    fixed_tokens = _estimate_tokens(fixed_inputs_text)
    budget = cap_tokens - fixed_tokens
    if budget <= 0:
        # Fixed inputs alone exceed the cap; drop the entire dialog.
        # The agent will work with no archive; rare and the failure
        # log will surface this if it produces a weak script.
        return []
    dialog_text = "\n".join(json.dumps(e, ensure_ascii=False) for e in dialog)
    if _estimate_tokens(dialog_text) <= budget:
        return dialog
    # Trim from the head. We do binary-search-style trimming for speed:
    # a linear "drop one entry at a time" is O(n*m) where m is the
    # token count of the dialog. For typical sizes (a few hundred
    # turns), drop in batches.
    truncated = list(dialog)
    while truncated and _estimate_tokens(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in truncated)
    ) > budget:
        # Drop the oldest 10% of remaining entries (or at least 1).
        drop_n = max(1, len(truncated) // 10)
        truncated = truncated[drop_n:]
    return truncated


def build_script_writer_inputs(
    deck_brief_text: str,
    audience_yaml_text: str,
    timeline: list[dict],
    dialog: list[dict],
    slides_data: list[dict],
    existing_speaker_script: Optional[str],
) -> str:
    """Assemble the user-message body for the script-writer call.

    Structure (one section per input source, labeled), JSON-Lines
    payloads inside fenced code blocks where relevant. The closing
    section instructs the agent to emit the script markdown directly.

    The ``external_documents`` slot is ALWAYS present, ALWAYS empty
    in v1 — schema reservation per REQ-SCRIPT-WRITER-1 forward-
    compatibility for BUG-AUDIT-85.
    """
    parts: list[str] = []

    # 1. Brief
    parts.append(
        "## DECK BRIEF — current state of audience / room / intent / duration\n\n"
        f"```markdown\n{deck_brief_text}\n```\n"
    )

    # 2. Audience roster (when present)
    if audience_yaml_text.strip():
        parts.append(
            "## AUDIENCE ROSTER — named attendees\n\n"
            f"```yaml\n{audience_yaml_text}\n```\n"
        )

    # 3. Event timeline
    parts.append(
        "## EVENT TIMELINE — typed events in time order\n\n"
        f"```jsonl\n"
        + "\n".join(json.dumps(e, ensure_ascii=False) for e in timeline)
        + "\n```\n"
    )

    # 4. Dialog archive
    parts.append(
        "## DIALOG ARCHIVE — every user turn + every consultant reply\n\n"
        "Subject to a 200K-token cap on the assembled message; oldest "
        "turns are dropped first when truncation fires.\n\n"
        f"```jsonl\n"
        + "\n".join(json.dumps(e, ensure_ascii=False) for e in dialog)
        + "\n```\n"
    )

    # 5. Slides
    parts.append(
        "## SLIDES — approved slides in array order\n\n"
        "Each slide entry contains slug, title, content_summary, "
        "visual_approach, design_choices, user_assets paths.\n\n"
        f"```jsonl\n"
        + "\n".join(json.dumps(s, ensure_ascii=False) for s in slides_data)
        + "\n```\n"
    )

    # 6. Existing speaker_script.md (co-writer baseline)
    if existing_speaker_script is not None:
        parts.append(
            "## CO-WRITER BASELINE — existing speaker_script.md\n\n"
            "Use this for stylistic continuity. Preserve the user's "
            "verbatim phrasing on slides whose source data is unchanged. "
            "Adopt the user's voice when writing new sections.\n\n"
            f"```markdown\n{existing_speaker_script}\n```\n"
        )

    # 7. External documents — always empty in v1.
    parts.append(
        "## EXTERNAL DOCUMENTS — forward-compat slot, always empty in v1\n\n"
        "BUG-AUDIT-85 will populate this for archetypes that center "
        "external documents (journal_club: paper PDFs; "
        "thesis_discussion: thesis PDF; grant_panel: proposal PDF). "
        "v1 always has external_documents=[] and you do NOT mention "
        "paper-specific content in v1 even if a slide's user_assets "
        "references a paper image.\n\n"
        "```yaml\n"
        "external_documents: []\n"
        "```\n"
    )

    # 8. Instruction
    parts.append(
        "Produce the new `speaker_script.md` per the canonical structure "
        "and discipline rules in your system prompt. Output the script "
        "markdown directly — no preamble, no postscript."
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Validators — one function per guardrail (#2 is prompt-only)
# ---------------------------------------------------------------------------


_NUMERIC_PATTERN = re.compile(
    r"\b\d+\.?\d*\s*"
    r"(?:[%×]|"
    r"(?:mm|cm|kg|ms|s|min|h|x|fold|patients|samples|n\s*=)\b)"
)
_NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+\b")


def _slide_section_blocks(text: str) -> list[tuple[str, str, str]]:
    """Parse a script into (heading, slug, body) tuples per slide
    section. Heading is the full ``## Slide N: <title>`` line; slug
    is the value extracted from the ``**Slug:** \\`<slug>\\``` line;
    body is the prose between the heading and the next slide / EOF.
    """
    blocks: list[tuple[str, str, str]] = []
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("## Slide ") or line.startswith("## Backup Slides"):
            heading = line
            j = i + 1
            slug = ""
            while j < n and not (
                lines[j].startswith("## Slide ")
                or lines[j].startswith("## Backup Slides")
                or lines[j].startswith("---") and j > i + 2
            ):
                m = re.match(r"\*\*Slug:\*\*\s*`([^`]+)`", lines[j].strip())
                if m and not slug:
                    slug = m.group(1).strip()
                j += 1
            body = "\n".join(lines[i:j])
            if line.startswith("## Slide "):
                blocks.append((heading, slug, body))
            i = j
        else:
            i += 1
    return blocks


def validate_script_structure(
    script_text: str, slides_data: list[dict]
) -> Optional[str]:
    """Per-slide structure validator (guardrail #3).

    Returns None on success, error string on failure.
    """
    if not script_text.strip().startswith("# Speaker Script"):
        return "script must start with '# Speaker Script' heading"
    blocks = _slide_section_blocks(script_text)
    expected_main = [s for s in slides_data if not s.get("backup")]
    expected_backup = [s for s in slides_data if s.get("backup")]
    expected_total = len(expected_main) + len(expected_backup)
    if len(blocks) != expected_total:
        return (
            f"script section count {len(blocks)} != "
            f"expected {expected_total} (main: {len(expected_main)}, "
            f"backup: {len(expected_backup)})"
        )
    # Each section must have the four required subsections.
    required = (
        "### Key talking points",
        "### Transition",
        "### Estimated speaking time",
    )
    for heading, slug, body in blocks:
        for req in required:
            if req not in body:
                return (
                    f"section {heading!r} missing required subsection "
                    f"{req!r}"
                )
    return None


def validate_script_traceability(
    script_text: str,
    audience_entries: list[dict],
    timeline: list[dict],
    slides_data: list[dict],
    deck_brief_text: str,
    dialog: list[dict],
) -> Optional[str]:
    """Source-traceability validator (guardrail #1, lightweight).

    Returns None on pass, error string on the first failed check.
    """
    # Build the full traceable corpus (case-insensitive substring
    # search target).
    corpus_parts: list[str] = [deck_brief_text.lower()]
    for s in slides_data:
        for k in ("content_summary", "visual_approach", "design_choices"):
            v = s.get(k) or ""
            if isinstance(v, str):
                corpus_parts.append(v.lower())
    for e in dialog:
        c = e.get("content")
        if isinstance(c, str):
            corpus_parts.append(c.lower())
    corpus = "\n".join(corpus_parts)

    # Numeric claims in the script must appear in the corpus.
    for m in _NUMERIC_PATTERN.finditer(script_text):
        claim = m.group(0).strip().lower()
        # Allow the time-check checkpoint patterns (e.g., "~5 min")
        # which are derived numerics, not user-surfaced.
        if claim.startswith("~"):
            continue
        if claim not in corpus:
            # Be tolerant: trim trailing units and recheck.
            base = re.match(r"\d+\.?\d*", claim)
            if base and base.group(0) in corpus:
                continue
            return (
                f"numeric claim {claim!r} not found in brief / dialog "
                f"/ slide content_summary corpus"
            )

    # Names mentioned in the script must appear in the roster (when
    # roster is present). Skip when no roster — names may appear in
    # dialog but not yet in YAML, and we don't want false-positives
    # on common words that look like names (e.g., "Method", "Figure").
    if audience_entries:
        roster_names = {
            (e.get("name") or "").strip()
            for e in audience_entries
            if isinstance(e.get("name"), str)
        }
        roster_names.discard("")
        if roster_names:
            # Extract candidate names from the script's prose (the
            # heading and slug lines have title-case identifiers we
            # don't want to flag, so we exclude per-slide headers).
            prose_lines: list[str] = []
            for line in script_text.splitlines():
                stripped = line.strip()
                if (
                    stripped.startswith("## ")
                    or stripped.startswith("### ")
                    or stripped.startswith("#")
                    or stripped.startswith("**Slug:**")
                    or stripped.startswith("**")
                    or stripped.startswith(">")
                ):
                    continue
                prose_lines.append(line)
            prose = "\n".join(prose_lines)
            mentioned: set[str] = {
                m.group(0) for m in _NAME_PATTERN.finditer(prose)
            }
            # Filter to names that look like roster-style first names —
            # skip common English title-case words via a short
            # exclusion list. Keep this conservative.
            common_titlecase_words = {
                # Honorifics + structural slide-deck terms.
                "Slide", "Figure", "Method", "Results", "Audience",
                "Mr", "Ms", "Dr", "Prof",
                # Pronouns + determiners.
                "The", "We", "I", "Our", "Their", "His", "Her", "Its", "My",
                "Your", "He", "She", "It", "They", "You",
                "This", "That", "These", "Those", "Such",
                "All", "Some", "Most", "Many", "Few", "Each", "Every",
                "Both", "Neither", "Either",
                # Common sentence-starter verbs.
                "Open", "Close", "Frame", "Set", "Make", "Take", "Hold",
                "Move", "Turn", "Give", "Run", "Walk", "Show", "Tell",
                "Demonstrate", "Describe", "Explain", "Summarize", "Present",
                "Conclude", "Note", "Highlight", "Emphasize", "Underline",
                "Recall", "Remember", "Notice", "Compare", "Contrast",
                "Consider", "Suppose", "Assume", "Imagine", "Look", "See",
                "Listen", "Read", "Write", "Continue", "Begin", "Start",
                "End", "Stop", "Pause", "Skip", "Include", "Exclude",
                # Common sentence-starter adverbs / connectives.
                "Today", "Now", "Then", "Here", "There", "So", "Thus",
                "Hence", "Therefore", "However", "Yet", "Still", "Meanwhile",
                "Afterwards", "First", "Second", "Third", "Finally", "Last",
                "Initially", "Eventually", "Specifically", "Particularly",
                "Importantly", "Notably", "Crucially", "Critically",
                # Time vocabulary.
                "Yesterday", "Tomorrow", "Year", "Month", "Day", "Week",
                "Morning", "Afternoon", "Evening",
                # Common contentful sentence starters in scientific prose.
                "Background", "Methods", "Discussion", "Conclusion",
                "Introduction", "Summary", "Abstract", "References",
                "Appendix", "Acknowledgments", "Funding",
            }
            mentioned = {n for n in mentioned if n not in common_titlecase_words}
            for name in mentioned:
                # If the name looks like a roster name (any roster
                # entry's first word matches), it's allowed regardless
                # of full-string equality — handles "Alice" vs "Alice
                # Smith".
                first_words = {
                    rn.split()[0] for rn in roster_names if rn
                }
                if name in first_words or name in roster_names:
                    continue
                # Name not in roster — flag.
                return (
                    f"script mentions name {name!r} which is not in the "
                    f"audience roster"
                )

    # Citation checks (basic): references to "paper" should map to
    # at least one paper_attached event when timeline has any.
    paper_events = [e for e in timeline if e.get("event") == "paper_attached"]
    paper_paths_lc = {
        str((e.get("payload") or {}).get("path", "")).lower()
        for e in paper_events
    }
    paper_paths_lc.discard("")
    # Look for explicit `papers/...` citations in the script.
    for m in re.finditer(r"papers/[^\s)]+\.pdf", script_text, re.IGNORECASE):
        cited_path = m.group(0).lower()
        if not paper_paths_lc:
            return (
                f"script cites paper path {cited_path!r} but no "
                f"paper_attached events exist in the timeline"
            )
        if cited_path not in paper_paths_lc:
            return (
                f"script cites paper path {cited_path!r} which does not "
                f"match any paper_attached event in the timeline"
            )

    return None


def validate_script_length_budget(
    script_text: str,
    total_duration_minutes: Optional[float],
    main_slide_count: int,
) -> list[str]:
    """Length-budget validator (guardrail #4). Returns a list of
    warning strings (one per slide that exceeds budget by more than
    `_SCRIPT_WRITER_LENGTH_OVERRUN_FACTOR`). Empty list when within
    budget. NEVER blocks the write — overruns are warnings only.
    """
    if not total_duration_minutes or main_slide_count <= 0:
        return []
    per_slide_budget = total_duration_minutes / main_slide_count
    overrun_threshold = per_slide_budget * _SCRIPT_WRITER_LENGTH_OVERRUN_FACTOR
    warnings: list[str] = []
    for heading, slug, body in _slide_section_blocks(script_text):
        # Skip backup slides — they're not budgeted.
        if "(backup)" in heading.lower():
            continue
        # Estimate words in Key talking points + Transition only
        # (skip the metadata lines).
        ktp_idx = body.find("### Key talking points")
        eta_idx = body.find("### Estimated speaking time")
        if ktp_idx < 0 or eta_idx < 0 or eta_idx <= ktp_idx:
            continue
        prose = body[ktp_idx:eta_idx]
        words = len(prose.split())
        estimated_minutes = words / _SCRIPT_WRITER_WORDS_PER_MINUTE
        if estimated_minutes > overrun_threshold:
            warnings.append(
                f"slide {slug!r}: estimated {estimated_minutes:.1f}min "
                f"exceeds budget {per_slide_budget:.1f}min by more than "
                f"{int((_SCRIPT_WRITER_LENGTH_OVERRUN_FACTOR - 1) * 100)}%"
            )
    return warnings


def validate_script_roster_mentions(
    script_text: str,
    audience_entries: list[dict],
    slides_data: list[dict],
) -> Optional[str]:
    """Roster-aware mentions validator (guardrail #5). Returns None
    on pass, error string on first failure.

    A roster member's name appears in a slide's section ONLY if at
    least one content word (length > 4) from the roster entry's
    `notes` overlaps with the slide's `content_summary` /
    `visual_approach`.
    """
    if not audience_entries:
        return None
    blocks = _slide_section_blocks(script_text)
    slides_by_slug = {s.get("slug"): s for s in slides_data if s.get("slug")}
    name_to_entry: dict[str, dict] = {}
    for e in audience_entries:
        name = (e.get("name") or "").strip()
        if name:
            first = name.split()[0]
            name_to_entry[first] = e
            name_to_entry[name] = e

    common_titlecase_words = {
        # Honorifics + structural slide-deck terms.
        "Slide", "Figure", "Method", "Results", "Audience",
        "Mr", "Ms", "Dr", "Prof",
        # Pronouns + determiners.
        "The", "We", "I", "Our", "Their", "His", "Her", "Its", "My",
        "Your", "He", "She", "It", "They", "You",
        "This", "That", "These", "Those", "Such",
        "All", "Some", "Most", "Many", "Few", "Each", "Every",
        "Both", "Neither", "Either",
        # Common sentence-starter verbs.
        "Open", "Close", "Frame", "Set", "Make", "Take", "Hold",
        "Move", "Turn", "Give", "Run", "Walk", "Show", "Tell",
        "Demonstrate", "Describe", "Explain", "Summarize", "Present",
        "Conclude", "Note", "Highlight", "Emphasize", "Underline",
        "Recall", "Remember", "Notice", "Compare", "Contrast",
        "Consider", "Suppose", "Assume", "Imagine", "Look", "See",
        "Listen", "Read", "Write", "Continue", "Begin", "Start",
        "End", "Stop", "Pause", "Skip", "Include", "Exclude",
        # Common sentence-starter adverbs / connectives.
        "Today", "Now", "Then", "Here", "There", "So", "Thus",
        "Hence", "Therefore", "However", "Yet", "Still", "Meanwhile",
        "Afterwards", "First", "Second", "Third", "Finally", "Last",
        "Initially", "Eventually", "Specifically", "Particularly",
        "Importantly", "Notably", "Crucially", "Critically",
        # Time vocabulary.
        "Yesterday", "Tomorrow", "Year", "Month", "Day", "Week",
        "Morning", "Afternoon", "Evening", "Today",
        # Common contentful sentence starters in scientific prose.
        "Background", "Methods", "Discussion", "Conclusion",
        "Introduction", "Summary", "Abstract", "References",
        "Appendix", "Acknowledgments", "Funding",
    }

    for heading, slug, body in blocks:
        slide = slides_by_slug.get(slug, {})
        slide_content = " ".join([
            (slide.get("content_summary") or ""),
            (slide.get("visual_approach") or ""),
        ]).lower()
        slide_words = {
            w for w in re.findall(r"\b[a-z]{5,}\b", slide_content)
        }

        # Walk prose lines (skip metadata).
        prose_lines: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            if (
                stripped.startswith("## ")
                or stripped.startswith("### ")
                or stripped.startswith("**Slug:**")
                or stripped.startswith(">")
            ):
                continue
            prose_lines.append(line)
        prose = " ".join(prose_lines)

        for m in _NAME_PATTERN.finditer(prose):
            name = m.group(0)
            if name in common_titlecase_words:
                continue
            entry = name_to_entry.get(name)
            if entry is None:
                continue  # Caught by traceability check.
            notes = (entry.get("notes") or "").lower()
            notes_words = {
                w for w in re.findall(r"\b[a-z]{5,}\b", notes)
            }
            if not notes_words:
                return (
                    f"slide {slug!r} mentions roster member {name!r} but "
                    f"the roster entry has no notes — cannot justify the "
                    f"mention. Use neutral phrasing or extend the roster."
                )
            overlap = slide_words & notes_words
            if not overlap:
                return (
                    f"slide {slug!r} mentions roster member {name!r} but "
                    f"none of {name!r}'s notes keywords overlap with the "
                    f"slide's content. Either remove the mention or "
                    f"extend the roster entry's notes."
                )
    return None


def _bigrams(text: str) -> set[tuple[str, str]]:
    """Lowercased word bigrams from a body of text (punctuation-naive)."""
    words = re.findall(r"\b[a-z0-9_]+\b", text.lower())
    return {(words[i], words[i + 1]) for i in range(len(words) - 1)}


def validate_script_voice_drift(
    new_script: str,
    prior_script: Optional[str],
    slides_data: list[dict],
    prior_slide_signatures: dict[str, str],
) -> list[str]:
    """Co-writer voice-drift validator (guardrail #6). Returns a list
    of warning strings (one per slide whose Jaccard bigram similarity
    fell below `_SCRIPT_WRITER_VOICE_DRIFT_THRESHOLD` despite source
    data being unchanged). Empty list when no drift detected.

    ``prior_slide_signatures`` is a mapping from slug to a string
    fingerprint of the slide's source data at the time of the prior
    generation — content_summary + visual_approach + design_choices
    concatenated. The caller computes this from the prior generation's
    metadata; if it matches the current slide's signature the slide's
    source is "unchanged" and drift is meaningful.

    Backup-slide blocks are not checked (they're typically Q&A-only).
    """
    if prior_script is None or not prior_slide_signatures:
        return []
    new_blocks = {
        slug: body for _, slug, body in _slide_section_blocks(new_script)
    }
    prior_blocks = {
        slug: body for _, slug, body in _slide_section_blocks(prior_script)
    }
    warnings: list[str] = []
    for s in slides_data:
        if s.get("backup"):
            continue
        slug = s.get("slug")
        if not slug:
            continue
        prior_sig = prior_slide_signatures.get(slug)
        if prior_sig is None:
            continue  # Slide is new; no drift check.
        cur_sig = "|".join([
            s.get("content_summary") or "",
            s.get("visual_approach") or "",
            s.get("design_choices") or "",
        ])
        if cur_sig != prior_sig:
            continue  # Source changed; agent has reason to rewrite.
        prior_body = prior_blocks.get(slug)
        new_body = new_blocks.get(slug)
        if not prior_body or not new_body:
            continue
        prior_grams = _bigrams(prior_body)
        new_grams = _bigrams(new_body)
        if not prior_grams or not new_grams:
            continue
        union = prior_grams | new_grams
        intersection = prior_grams & new_grams
        if not union:
            continue
        similarity = len(intersection) / len(union)
        if similarity < _SCRIPT_WRITER_VOICE_DRIFT_THRESHOLD:
            warnings.append(
                f"slide {slug!r}: voice-drift Jaccard similarity "
                f"{similarity:.2f} < {_SCRIPT_WRITER_VOICE_DRIFT_THRESHOLD} "
                f"despite unchanged source data"
            )
    return warnings


# ---------------------------------------------------------------------------
# CLI orchestrator
# ---------------------------------------------------------------------------


def _is_anthropic_module_error(exc: BaseException) -> bool:
    """True when ``exc`` is the missing-anthropic-SDK ImportError (BUG-AUDIT-93)."""
    return isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", None) == "anthropic"


def _emit_anthropic_missing_stderr(command: str) -> None:
    """Print the actionable stderr line for missing anthropic SDK (BUG-AUDIT-93).

    Called whenever a lazy-import path raises ``ModuleNotFoundError`` for
    ``anthropic``. Pre-fix the consultant/script-writer/rewriter paths
    logged the error to JSONL and exited 0, leaving the user without any
    console signal that the deliverable had failed.
    """
    print(
        f"{command}: anthropic SDK not installed in this env; "
        f"install with `pip install 'anthropic>=0.40'` and retry. "
        f"If the env was created by `bin/debrief`, run `debrief --rebuild-env`.",
        file=sys.stderr,
    )


def _is_anthropic_auth_error(exc: BaseException) -> bool:
    """True when ``exc`` is an Anthropic auth/credential failure (BUG-AUDIT-98).

    Detects two cases without requiring a hard import of ``anthropic``
    (which may itself be missing — that's the BUG-AUDIT-93 path):

    1. ``TypeError`` from ``anthropic.Anthropic()`` constructor when no
       credential is found in the environment. The SDK's message starts
       with ``"Could not resolve authentication method"``. Fires when
       ``ANTHROPIC_API_KEY`` is unset and no other credential is provided.
    2. Class name ``"AuthenticationError"`` — ``anthropic.AuthenticationError``,
       raised by the SDK when the API rejects a present-but-invalid
       credential (HTTP 401). Class-name comparison avoids importing the
       SDK at classifier time.

    All other exception classes return False; they fall through to the
    silent-exit-0 branch per the BC-3.18 / BC-3.20 contract.
    """
    if isinstance(exc, TypeError) and "could not resolve authentication" in str(exc).lower():
        return True
    if type(exc).__name__ == "AuthenticationError":
        return True
    return False


def _emit_anthropic_auth_missing_stderr(command: str, *, log_path: str) -> None:
    """Print actionable stderr line for missing/invalid API credentials (BUG-AUDIT-98).

    Called when the lazy-import path raises a TypeError or AuthenticationError
    classified by ``_is_anthropic_auth_error``. Pre-fix the launcher caught
    only ``ModuleNotFoundError`` and silently exit-0'd on any other Anthropic
    failure mode, hiding auth errors from the user entirely.

    The ``log_path`` parameter accommodates the script-writer's
    ``.debrief/script_errors.jsonl`` and the rewriter's
    ``.debrief/rewrite_errors.jsonl`` so the user can inspect the captured
    failure detail with one ``cat``.
    """
    print(
        f"{command}: anthropic API authentication failed; "
        f"set ANTHROPIC_API_KEY in the environment and retry. "
        f"Details logged to {log_path}.",
        file=sys.stderr,
    )


def call_script_writer_agent(
    model: str,
    system_prompt: str,
    user_message: str,
) -> str:
    """Call the Anthropic API for the script-writer. Mockable seam.

    Lazy import so a missing SDK dependency surfaces as ImportError
    that the caller logs per REQ-SCRIPT-WRITER-2 rather than crashing
    on module import.
    """
    import anthropic  # type: ignore[import]

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=16384,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    parts: list[str] = []
    for block in response.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "".join(parts)


def log_script_error(
    project_root: Path,
    *,
    trigger: str,
    error_class: str,
    error_message: str,
) -> None:
    """Append a failure entry to ``.debrief/script_errors.jsonl``."""
    path = project_root / _SCRIPT_ERRORS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "trigger": trigger,
        "error_class": error_class,
        "error_message": error_message,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def backup_speaker_script(project_root: Path) -> Optional[Path]:
    """Copy existing ``speaker_script.md`` to
    ``.debrief/script_backups/speaker_script.<UTC ISO 8601>.md``.

    Returns the backup path on success, None when no existing script
    or on backup failure (logged but non-fatal per BC-11.20).
    """
    src = project_root / _SPEAKER_SCRIPT_REL
    if not src.is_file():
        return None
    backup_dir = project_root / _SCRIPT_BACKUPS_REL
    backup_dir.mkdir(parents=True, exist_ok=True)
    # Filesystem-safe timestamp: hyphens instead of colons.
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    dest = backup_dir / f"speaker_script.{ts}.md"
    try:
        shutil.copy2(src, dest)
    except OSError:
        return None
    return dest


def _parse_audience_yaml(yaml_text: str) -> list[dict]:
    """Parse the audience YAML body into a list of entry dicts.

    Light hand-rolled parser matching utility_skills.validate_roster_yaml's
    grammar so we don't introduce a PyYAML dependency for the trivial
    case. Returns empty list on parse failure or when no audience: key.
    """
    if not yaml_text.strip():
        return []
    entries: list[dict] = []
    current: Optional[dict] = None
    in_audience = False
    for raw_line in yaml_text.splitlines():
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
    return entries


def main_script_writer(
    project_root: Path,
    *,
    trigger: str = "/debrief:script",
    plugin_root: Optional[Path] = None,
) -> None:
    """Entry point for ``python -m debrief.launcher script_writer
    [--project-root PATH] [--trigger ...]``.

    Reads the script-writer agent-card, builds the user message from
    brief + audience.yaml + timeline + dialog + slides + (existing
    speaker_script.md as co-writer baseline), calls the Anthropic API
    via ``call_script_writer_agent``, validates the output against the
    six guardrails, backs up the existing script, atomically writes
    the new one, emits the ``script_done`` timeline event.

    On any failure path: logs to ``.debrief/script_errors.jsonl`` and
    exits 0 per REQ-SCRIPT-WRITER-2 — NEVER block the consultant.

    See BC-3.20 / BC-5.21 / REQ-SCRIPT-WRITER-1..4 / BUG-AUDIT-84.
    """
    project_root = project_root.resolve()

    # 1. Resolve agent card path (mirror main_rewrite_brief logic).
    if plugin_root is None:
        plugin_root_str = os.environ.get("CLAUDE_PLUGIN_ROOT")
        if plugin_root_str:
            plugin_root = Path(plugin_root_str)
        else:
            this_file = Path(__file__).resolve()
            workspace_card = (
                this_file.parent.parent / "unit_1" / "agents"
                / "script-writer.md"
            )
            delivered_card = (
                this_file.parent.parent.parent / "agents" / "script-writer.md"
            )
            if workspace_card.is_file():
                plugin_root = workspace_card.parent.parent.parent
            elif delivered_card.is_file():
                plugin_root = delivered_card.parent.parent
            else:
                plugin_root = this_file.parent.parent.parent

    card_path = plugin_root / "agents" / "script-writer.md"
    if not card_path.is_file():
        workspace_alt = (
            Path(__file__).resolve().parent.parent / "unit_1" / "agents"
            / "script-writer.md"
        )
        if workspace_alt.is_file():
            card_path = workspace_alt

    # 2. Read agent card.
    try:
        model, system_prompt = extract_agent_card(card_path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        log_script_error(
            project_root,
            trigger=trigger,
            error_class="agent_card_error",
            error_message=f"failed to read script-writer card at {card_path}: {exc}",
        )
        sys.exit(0)

    # 3. Load inputs.
    brief_path = project_root / _DECK_BRIEF_REL
    deck_brief_text = ""
    if brief_path.is_file():
        try:
            deck_brief_text = brief_path.read_text(encoding="utf-8")
        except OSError as exc:
            log_script_error(
                project_root,
                trigger=trigger,
                error_class="brief_read_error",
                error_message=str(exc),
            )

    audience_yaml_text = read_audience_yaml(project_root)
    audience_entries = _parse_audience_yaml(audience_yaml_text)
    timeline = read_event_timeline(project_root)
    dialog = read_dialog_archive(project_root)

    # 4. Slide records — read from deck_state.json.
    try:
        from debrief_state import read_deck_state  # type: ignore[import]

        deck_state = read_deck_state(project_root)
    except Exception as exc:  # noqa: BLE001
        log_script_error(
            project_root,
            trigger=trigger,
            error_class="deck_state_read_error",
            error_message=str(exc),
        )
        sys.exit(0)

    approved = [
        s for s in deck_state.slides
        if s.status == "approved"
    ]
    # Preserve the BUG-AUDIT-65 / REQ-SCRIPT-BACKUP-1 semantic: at
    # least one MAIN (non-backup) approved slide is required. A deck
    # of only backup slides would yield a script with no main talk.
    main_approved = [s for s in approved if not s.backup]
    if not main_approved:
        log_script_error(
            project_root,
            trigger=trigger,
            error_class="no_approved_slides",
            error_message="no approved main (non-backup) slides — cannot generate script",
        )
        sys.exit(0)

    slides_data: list[dict] = []
    for s in approved:
        slides_data.append({
            "slug": s.slug,
            "title": s.title,
            "content_summary": s.content_summary or "",
            "visual_approach": s.visual_approach or "",
            "design_choices": s.design_choices or "",
            "user_assets": list(s.user_assets or []),
            "backup": bool(s.backup),
        })

    main_slide_count = sum(1 for s in slides_data if not s["backup"])

    # 5. Co-writer baseline.
    existing_speaker_script = read_speaker_script(project_root)

    # 6. Truncate dialog if assembled inputs would exceed the cap.
    fixed_inputs = build_script_writer_inputs(
        deck_brief_text=deck_brief_text,
        audience_yaml_text=audience_yaml_text,
        timeline=timeline,
        dialog=[],  # placeholder for sizing
        slides_data=slides_data,
        existing_speaker_script=existing_speaker_script,
    )
    truncated_dialog = truncate_dialog_to_token_cap(
        dialog, fixed_inputs, cap_tokens=_SCRIPT_WRITER_TOKEN_CAP
    )
    user_message = build_script_writer_inputs(
        deck_brief_text=deck_brief_text,
        audience_yaml_text=audience_yaml_text,
        timeline=timeline,
        dialog=truncated_dialog,
        slides_data=slides_data,
        existing_speaker_script=existing_speaker_script,
    )

    # 7. Call API.
    try:
        response_text = call_script_writer_agent(model, system_prompt, user_message)
    except Exception as exc:  # noqa: BLE001
        log_script_error(
            project_root,
            trigger=trigger,
            error_class=type(exc).__name__,
            error_message=str(exc),
        )
        # BUG-AUDIT-93: surface missing-anthropic to stderr and exit non-zero
        # on direct CLI invocation so the user does not see a silent failure.
        # Cascades (deck-complete-finalization, /debrief:handout-cascade) keep
        # exit 0 per REQ-SCRIPT-WRITER-2 — the next step in the cascade still
        # runs, and the JSONL log captures the failure for later inspection.
        # BUG-AUDIT-98 extends the same shape to Anthropic auth failures
        # (missing or invalid ANTHROPIC_API_KEY).
        if _is_anthropic_module_error(exc):
            _emit_anthropic_missing_stderr("/debrief:script")
            sys.exit(2 if trigger == "/debrief:script" else 0)
        if _is_anthropic_auth_error(exc):
            _emit_anthropic_auth_missing_stderr(
                "/debrief:script", log_path=_SCRIPT_ERRORS_REL,
            )
            sys.exit(2 if trigger == "/debrief:script" else 0)
        sys.exit(0)

    # 8. Validate guardrails (3, 1, 5 are blockers; 4, 6 are warnings).
    err = validate_script_structure(response_text, slides_data)
    if err is not None:
        log_script_error(
            project_root,
            trigger=trigger,
            error_class="script_structure_invalid",
            error_message=err,
        )
        sys.exit(0)

    err = validate_script_traceability(
        response_text, audience_entries, timeline,
        slides_data, deck_brief_text, dialog,
    )
    if err is not None:
        log_script_error(
            project_root,
            trigger=trigger,
            error_class="script_traceability_invalid",
            error_message=err,
        )
        sys.exit(0)

    err = validate_script_roster_mentions(
        response_text, audience_entries, slides_data
    )
    if err is not None:
        log_script_error(
            project_root,
            trigger=trigger,
            error_class="script_roster_mention_invalid",
            error_message=err,
        )
        sys.exit(0)

    # Length-budget warnings (non-blocking).
    duration_match = re.search(
        r"\*\*Target duration:\*\*\s*(\d+(?:\.\d+)?)\s*minutes",
        response_text,
    )
    total_duration = float(duration_match.group(1)) if duration_match else None
    for w in validate_script_length_budget(
        response_text, total_duration, main_slide_count
    ):
        log_script_error(
            project_root,
            trigger=trigger,
            error_class="warning_length_overrun",
            error_message=w,
        )

    # Voice-drift warnings (co-writer mode only; non-blocking).
    if existing_speaker_script:
        prior_signatures: dict[str, str] = {}
        # Approximation: for slides present in the existing script,
        # we don't have stored prior signatures — use the current
        # signatures (which means drift is only flagged when source
        # data hasn't changed, which is the desired semantic). Future
        # enhancement: persist a per-slide signature in
        # rewrite_metadata.json or a sibling file.
        for s in slides_data:
            prior_signatures[s["slug"]] = "|".join([
                s["content_summary"], s["visual_approach"], s["design_choices"],
            ])
        for w in validate_script_voice_drift(
            response_text, existing_speaker_script,
            slides_data, prior_signatures,
        ):
            log_script_error(
                project_root,
                trigger=trigger,
                error_class="warning_voice_drift",
                error_message=w,
            )

    # 9. Backup existing script.
    backup_speaker_script(project_root)

    # 10. Atomic write of the new script.
    script_path = project_root / _SPEAKER_SCRIPT_REL
    try:
        _atomic_write_text(script_path, response_text)
    except OSError as exc:
        log_script_error(
            project_root,
            trigger=trigger,
            error_class="write_failure",
            error_message=str(exc),
        )
        sys.exit(0)

    # 11. Emit script_done timeline event.
    try:
        # Determine the active presentation folder for the payload —
        # use the most recent presentation record if one exists, else
        # leave folder absent (the rewrite agent and other consumers
        # don't depend on it).
        folder = (
            deck_state.presentations[-1].folder
            if deck_state.presentations
            else ""
        )
        append_timeline_event(
            project_root,
            event="script_done",
            payload={
                "presentation_folder": folder,
                "slide_count": main_slide_count,
                "backup_slide_count": sum(
                    1 for s in slides_data if s["backup"]
                ),
                "script_path": _SPEAKER_SCRIPT_REL,
                "agent_version": _SCRIPT_WRITER_AGENT_VERSION,
                "model": model,
            },
        )
    except Exception:  # noqa: BLE001 — best-effort timeline emission
        pass

    print(str(script_path), file=sys.stderr)
    sys.exit(0)


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
        # BUG-AUDIT-93: surface missing-anthropic to stderr so the user knows
        # the rewriter has not produced deck_brief.md / audience.yaml. Exit
        # remains 0 unconditionally per REQ-MEMORY-REWRITE-4 — PreCompact must
        # never block compaction even when the rewriter cannot run.
        # BUG-AUDIT-98 extends the same shape to Anthropic auth failures.
        if _is_anthropic_module_error(exc):
            _emit_anthropic_missing_stderr("rewrite_brief")
        elif _is_anthropic_auth_error(exc):
            _emit_anthropic_auth_missing_stderr(
                "rewrite_brief", log_path=_REWRITE_ERRORS_REL,
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


@dataclass
class BriefAuditReport:
    """Brief-audit dimensions surfaced by ``doctor --brief-audit``.

    See BC-3.16 (extended) and BUG-AUDIT-83.
    """

    brief_present: bool
    brief_structure_valid: Optional[bool]  # None when brief absent
    roster_valid: Optional[bool]           # None when brief or roster absent
    watermark_aligned: bool
    rewrite_stale: bool
    notes: list[str] = field(default_factory=list)


def _audit_brief(project_root: Path) -> BriefAuditReport:
    """Audit the memory-architecture state per BUG-AUDIT-83.

    Five dimensions:

    1. ``brief_present`` — ``deck_brief.md`` exists at project root.
    2. ``brief_structure_valid`` — top-level sections conform to
       BC-5.16's canonical set (uses ``validate_brief_structure``).
       ``None`` when the brief is absent.
    3. ``roster_valid`` — when ``### Roster`` is present, the YAML
       parses and every entry has ``name`` + ``role`` keys (uses
       ``validate_roster_yaml``). ``None`` when the brief is absent
       OR the brief has no roster.
    4. ``watermark_aligned`` — ``.debrief/rewrite_metadata.json``'s
       ``last_archived_turn`` equals the highest ``turn`` field in
       ``.debrief/dialog.jsonl``. Mismatch indicates an interrupted
       append or a hand-edited archive.
    5. ``rewrite_stale`` — ``True`` when more than 5 archived turns
       have accumulated since the last rewrite per the watermark
       timestamps. Threshold is heuristic and intentionally loose
       — the goal is to surface "you've had a lot of conversation
       since the last rewrite" not to be a hard limit.

    Notes are accumulated as human-readable strings the doctor's
    stderr summary can render.
    """
    notes: list[str] = []

    # 1. Brief presence.
    brief_path = project_root / _DECK_BRIEF_REL
    brief_present = brief_path.is_file()

    # 2. Brief structure validity.
    brief_structure_valid: Optional[bool] = None
    brief_text: Optional[str] = None
    if brief_present:
        try:
            brief_text = brief_path.read_text(encoding="utf-8")
            validate_brief_structure(brief_text)
            brief_structure_valid = True
        except OSError as exc:
            brief_structure_valid = False
            notes.append(f"brief unreadable: {exc}")
        except ValueError as exc:
            brief_structure_valid = False
            notes.append(f"brief structure invalid: {exc}")

    # 3. Roster validity (only when brief is present and structurally valid).
    roster_valid: Optional[bool] = None
    if brief_present and brief_text is not None and brief_structure_valid:
        roster_yaml = extract_roster_yaml(brief_text)
        if roster_yaml is not None:
            try:
                validate_roster_yaml(roster_yaml)
                roster_valid = True
            except ValueError as exc:
                roster_valid = False
                notes.append(f"roster YAML invalid: {exc}")

    # 4. Watermark alignment.
    meta = _read_rewrite_metadata(project_root)
    last_archived_turn = int(meta.get("last_archived_turn", 0))
    archive = read_dialog_archive(project_root)
    if archive:
        try:
            highest_turn = max(int(e.get("turn", 0)) for e in archive)
        except (ValueError, TypeError):
            highest_turn = 0
    else:
        highest_turn = 0
    watermark_aligned = last_archived_turn == highest_turn
    if not watermark_aligned:
        notes.append(
            f"watermark ({last_archived_turn}) != highest turn in "
            f"archive ({highest_turn}); the archive may have been "
            f"hand-edited or truncated."
        )

    # 5. Rewrite staleness — heuristic.
    rewrite_stale = False
    last_rewrite_ts = meta.get("last_rewrite_timestamp")
    if last_rewrite_ts is None and highest_turn > 5:
        rewrite_stale = True
        notes.append(
            f"no rewrite has run yet ({highest_turn} turns archived). "
            f"Run /debrief:refresh-brief to produce a brief."
        )
    elif last_rewrite_ts is not None and highest_turn > 0:
        # Count turns whose timestamp is newer than last_rewrite_ts.
        # This is a string-comparison shortcut that works because all
        # timestamps are ISO 8601 with the Z suffix (lexicographic
        # order matches chronological order).
        newer_count = sum(
            1 for e in archive
            if isinstance(e.get("timestamp"), str)
            and e["timestamp"] > last_rewrite_ts
        )
        if newer_count > 5:
            rewrite_stale = True
            notes.append(
                f"{newer_count} turns archived since the last rewrite "
                f"at {last_rewrite_ts}; consider running "
                f"/debrief:refresh-brief."
            )

    return BriefAuditReport(
        brief_present=brief_present,
        brief_structure_valid=brief_structure_valid,
        roster_valid=roster_valid,
        watermark_aligned=watermark_aligned,
        rewrite_stale=rewrite_stale,
        notes=notes,
    )


def main_archive_paper(
    pdf_path: Path,
    project_root: Path,
) -> None:
    """Entry point for ``python -m debrief.launcher archive_paper
    --pdf <path> --project-root <path>``.

    Retroactive paper-archival path (BUG-AUDIT-94). The consultant SHOULD
    run ``paper_analyzer`` automatically when the user provides a paper
    PDF (BC-5.11), but the trigger detection has historically missed
    drag-and-drop or oblique mentions. This subcommand provides an
    explicit, idempotent recovery path: invoke ``paper_analyzer``
    directly on the given PDF, set ``debrief_state.papers_provided`` to
    True, and emit ``paper_attached`` to ``output/timeline.jsonl``.

    Exit codes:
      * 0 — success.
      * 1 — PDF path missing or unreadable.
      * 2 — ``paper_analyzer`` failed (env corruption, parse error, write
        failure). The underlying error is propagated to stderr.
      * 3 — usage error (no project_root, no pdf path).

    See BC-3.21 and BUG-AUDIT-94.
    """
    project_root = project_root.resolve()
    pdf_path = pdf_path.resolve()

    if not pdf_path.is_file():
        print(
            f"archive_paper: PDF not found at {pdf_path}",
            file=sys.stderr,
        )
        sys.exit(1)
    if pdf_path.suffix.lower() != ".pdf":
        print(
            f"archive_paper: expected a .pdf file, got {pdf_path.suffix!r}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Lazy-import paper_analyzer (similar pattern to fitz / anthropic — keeps
    # the launcher importable when the optional unit is unavailable).
    try:
        # Workspace layout: src/unit_12/paper_analyzer.py
        # Delivered layout: src/debrief/paper_analyzer.py
        try:
            import paper_analyzer  # type: ignore[import]
        except ModuleNotFoundError:
            from debrief import paper_analyzer  # type: ignore[no-redef]
    except ModuleNotFoundError as exc:
        print(
            f"archive_paper: paper_analyzer module not found: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)

    slug = paper_analyzer.derive_paper_slug(pdf_path)
    print(f"archive_paper: archiving {pdf_path.name} as slug={slug!r}")

    try:
        paper_analyzer.main_paper_analyzer(
            pdf_path=pdf_path,
            paper_slug=slug,
            project_root=project_root,
        )
    except SystemExit as exc:
        # main_paper_analyzer uses sys.exit() for its own error codes; preserve
        # them but remap to 2 (paper_analyzer failure) for our caller surface.
        if exc.code not in (None, 0):
            print(
                f"archive_paper: paper_analyzer exited {exc.code}",
                file=sys.stderr,
            )
            sys.exit(2)

    # Verify the analyzer actually wrote the expected artifacts before we
    # update state. If the artifacts are missing, abort without flipping
    # papers_provided — the user can re-run after fixing the underlying issue.
    paper_dir = project_root / "assets" / "reference" / "papers" / slug
    if not paper_dir.is_dir():
        print(
            f"archive_paper: expected output directory {paper_dir} was not created",
            file=sys.stderr,
        )
        sys.exit(2)

    # Update debrief_state.papers_provided = True via the canonical path.
    try:
        from debrief_state import read_debrief_state, write_debrief_state  # type: ignore[import]
    except ModuleNotFoundError:
        from debrief.debrief_state import (  # type: ignore[no-redef]
            read_debrief_state,
            write_debrief_state,
        )
    state = read_debrief_state(project_root)
    state.papers_provided = True
    write_debrief_state(project_root, state)

    # Emit paper_attached event per BC-2.18 / consultant card.
    append_timeline_event(
        project_root,
        event="paper_attached",
        payload={"path": str(pdf_path), "slug": slug},
    )

    print(
        f"archive_paper: success — paper archived to "
        f"assets/reference/papers/{slug}/, paper_attached event emitted, "
        f"papers_provided=True. Run /debrief:refresh-brief to consolidate."
    )
    sys.exit(0)


# ---------------------------------------------------------------------------
# Asset audit (BUG-AUDIT-94 / BC-3.16 amendment)
# ---------------------------------------------------------------------------


def _audit_assets(project_root: Path) -> dict:
    """Audit the project's ``assets/`` tree against expected usage.

    Returns a dict with the audit findings. Drift is detected when:

    * paper-derived figures (filenames matching ``figure*`` or ``fig_*``)
      appear in ``assets/images/`` while ``assets/reference/papers/`` is
      empty — indicates ``paper_analyzer`` was bypassed.
    * ``debrief_state.papers_provided`` is True but no paper directories
      exist under ``assets/reference/papers/`` — state lies about reality.
    * ``debrief_state.papers_provided`` is False but
      ``assets/reference/papers/<slug>/`` directories exist — state lies
      the other direction.
    * ``output/timeline.jsonl`` lacks ``paper_attached`` events even
      though paper directories exist — events were missed.
    * ``assets/images/`` files lack the ``<slug>_`` prefix mandated by
      REQ-ASSET-1 — ``asset_ingest`` was bypassed.

    Returns a dict with keys: ``paper_directories``, ``paper_attached_event_count``,
    ``papers_provided_flag``, ``orphan_paper_figures_in_images``,
    ``unprefixed_image_files``, ``drift``, ``notes``.
    """
    notes: list[str] = []

    images_dir = project_root / "assets" / "images"
    papers_dir = project_root / "assets" / "reference" / "papers"

    paper_directories: list[str] = []
    if papers_dir.is_dir():
        paper_directories = sorted(
            p.name for p in papers_dir.iterdir() if p.is_dir()
        )

    image_files: list[Path] = []
    if images_dir.is_dir():
        image_files = sorted(p for p in images_dir.iterdir() if p.is_file() and not p.name.startswith("."))

    # Heuristic: filenames matching common paper-figure shapes (case-insensitive
    # prefix match; covers "figure2_panel_A.png", "fig_3.png", "panel_b.png",
    # "Figure 1.png", etc.). Slightly broad — catches user-named files starting
    # with "figure"/"fig"/"panel" too — but false positives only surface in the
    # drift report where the user can confirm. False negatives (paper figures
    # that DON'T start with these prefixes) are the bigger risk.
    paper_figure_re = re.compile(r"^(figure|fig|panel)", re.IGNORECASE)
    orphan_paper_figures: list[str] = []
    if not paper_directories:
        orphan_paper_figures = sorted(
            p.name for p in image_files if paper_figure_re.match(p.name)
        )

    # REQ-ASSET-1: every file in assets/images/ MUST be ``<slug>_<original>``.
    # The slug is derived from a deck slide slug (alphanumeric + underscores,
    # starts with a letter). Files lacking a clear slug prefix are anomalous.
    slug_prefix_re = re.compile(r"^[a-z][a-z0-9_]{0,49}_")
    unprefixed_image_files = sorted(
        p.name for p in image_files if not slug_prefix_re.match(p.name)
    )

    # paper_attached event count
    paper_attached_count = 0
    timeline_path = project_root / "output" / "timeline.jsonl"
    if timeline_path.is_file():
        for line in timeline_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("event") == "paper_attached":
                paper_attached_count += 1

    # papers_provided flag
    papers_provided: Optional[bool] = None
    state_file = project_root / "debrief_state.json"
    if state_file.is_file():
        try:
            state_dict = json.loads(state_file.read_text())
            papers_provided = state_dict.get("papers_provided")
        except (json.JSONDecodeError, OSError):
            pass

    # Drift detection
    drift = False
    if orphan_paper_figures:
        drift = True
        notes.append(
            f"{len(orphan_paper_figures)} paper-figure-shaped file(s) in "
            "assets/images/ but assets/reference/papers/ is empty — "
            "paper_analyzer was likely bypassed. Consider running "
            "`debrief archive_paper --pdf <path>` to retroactively archive."
        )
    if papers_provided is True and not paper_directories:
        drift = True
        notes.append(
            "papers_provided=true in debrief_state but assets/reference/papers/ "
            "has no paper directories — state lies."
        )
    if papers_provided is False and paper_directories:
        drift = True
        notes.append(
            f"papers_provided=false but {len(paper_directories)} paper "
            "director(ies) exist under assets/reference/papers/ — state lies."
        )
    if paper_directories and paper_attached_count == 0:
        drift = True
        notes.append(
            f"{len(paper_directories)} paper director(ies) exist but no "
            "paper_attached event in output/timeline.jsonl — event emission "
            "was missed (BC-2.18)."
        )
    if unprefixed_image_files:
        drift = True
        notes.append(
            f"{len(unprefixed_image_files)} file(s) in assets/images/ lack the "
            "<slug>_ prefix mandated by REQ-ASSET-1 — asset_ingest was bypassed."
        )

    return {
        "paper_directories": paper_directories,
        "paper_attached_event_count": paper_attached_count,
        "papers_provided_flag": papers_provided,
        "orphan_paper_figures_in_images": orphan_paper_figures,
        "unprefixed_image_files": unprefixed_image_files,
        "drift": drift,
        "notes": notes,
    }


def _audit_phase(project_root: Path) -> dict:
    """Audit ``debrief_state.phase`` / ``sub_phase`` against ``deck_state``.

    Per BC-3.16 amendment + BUG-AUDIT-99. Detects three drift signals:

    1. **Primary:** approved slides exist AND ``phase == "discovery"``.
       The consultant has authored slides without advancing the phase;
       downstream commands that key off ``phase`` produce wrong answers.
    2. ``style_locked`` is True AND ``phase == "discovery"`` AND
       ``sub_phase`` is not ``"discovery/style_analysis"`` — the style
       was approved/locked but the phase did not advance.
    3. ``phase == "production"`` AND ``sub_phase == "production/group_planning"``
       AND approved slides exist — the sub_phase did not advance past
       planning even though slide work has progressed.

    Returns a dict with keys: ``phase``, ``sub_phase``,
    ``approved_slide_count``, ``style_locked``, ``drift`` (bool),
    ``notes`` (list[str]; each note includes a copy-pasteable recovery
    CLI command). The audit is read-only — it surfaces the drift but
    does NOT auto-remediate.
    """
    from debrief_state import read_debrief_state, read_deck_state  # type: ignore[import]

    notes: list[str] = []

    # Fall back gracefully if state files are absent or unreadable; the
    # primary doctor codepath already surfaces those errors via its own
    # reporting, so this audit just emits a one-line note and returns.
    try:
        debrief_state_obj = read_debrief_state(project_root)
    except Exception as exc:  # noqa: BLE001
        return {
            "phase": None,
            "sub_phase": None,
            "approved_slide_count": 0,
            "style_locked": None,
            "drift": False,
            "notes": [f"could not read debrief_state.json: {exc}"],
        }
    try:
        deck_state_obj = read_deck_state(project_root)
    except Exception as exc:  # noqa: BLE001
        return {
            "phase": debrief_state_obj.phase,
            "sub_phase": debrief_state_obj.sub_phase,
            "approved_slide_count": 0,
            "style_locked": None,
            "drift": False,
            "notes": [f"could not read deck_state.json: {exc}"],
        }

    approved_slide_count = sum(
        1 for s in deck_state_obj.slides if s.status == "approved"
    )
    style_locked = deck_state_obj.style_locked
    phase = debrief_state_obj.phase
    sub_phase = debrief_state_obj.sub_phase

    drift = False

    # Drift signal 1 (primary): approved slides exist but phase=="discovery".
    if approved_slide_count > 0 and phase == "discovery":
        drift = True
        notes.append(
            f"{approved_slide_count} approved slide(s) exist but phase is "
            f"'discovery'. The consultant must advance the phase. Recovery: "
            f"`python -m debrief.debrief_state update "
            f"--set sub_phase=production/slide_review --project-root {project_root}` "
            f"(phase auto-derives from sub_phase prefix per BC-2.15a)."
        )

    # Drift signal 2: style_locked but phase still 'discovery' and sub_phase
    # not advanced past discovery/style_analysis.
    if (
        style_locked
        and phase == "discovery"
        and sub_phase != "discovery/style_analysis"
    ):
        drift = True
        notes.append(
            f"style_locked is True but phase=='discovery' and sub_phase=='{sub_phase}'. "
            f"Style approval should have advanced sub_phase. Recovery: "
            f"`python -m debrief.debrief_state update "
            f"--set sub_phase=style/style_lock --project-root {project_root}`."
        )

    # Drift signal 3: production phase but sub_phase stuck at group_planning
    # even though slides have been approved.
    if (
        phase == "production"
        and sub_phase == "production/group_planning"
        and approved_slide_count > 0
    ):
        drift = True
        notes.append(
            f"phase=='production' but sub_phase=='production/group_planning' "
            f"with {approved_slide_count} approved slide(s). The sub_phase "
            f"did not advance past planning. Recovery: "
            f"`python -m debrief.debrief_state update "
            f"--set sub_phase=production/slide_review --project-root {project_root}`."
        )

    return {
        "phase": phase,
        "sub_phase": sub_phase,
        "approved_slide_count": approved_slide_count,
        "style_locked": style_locked,
        "drift": drift,
        "notes": notes,
    }


def main_doctor(
    project_root: Path,
    *,
    reconstruct: bool = False,
    brief_audit: bool = False,
    asset_audit: bool = False,
    phase_audit: bool = False,
) -> None:
    """Entry point for ``python -m debrief.launcher doctor
    --project-root <path> [--reconstruct] [--brief-audit] [--asset-audit]
    [--phase-audit]``.

    Prints a JSON report to stdout and a human-readable summary to
    stderr.

    Exit codes (REQ-DOCTOR-1):
    * 0 — no drift detected, OR drift was remediated successfully under
      ``--reconstruct``.
    * 1 — drift detected in report-only mode (scripts can key off this).
    * 2 — remediation attempted under ``--reconstruct`` but failed.

    See BC-3.15, BC-3.16, and BUG-AUDIT-75 / BUG-AUDIT-83 / BUG-AUDIT-94 /
    BUG-AUDIT-99.
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

    summary: dict[str, object] = {
        "drift_detected": report.drift_detected,
        "orphan_files": report.orphan_files,
        "orphan_records": report.orphan_records,
        "matched_count": report.matched_count,
    }

    # BUG-AUDIT-83: --brief-audit extends the doctor with memory-
    # architecture audits. The slide-state report above is unchanged;
    # the brief_audit field is added when the flag is passed.
    brief_drift = False
    if brief_audit:
        audit = _audit_brief(project_root)
        summary["brief_audit"] = {
            "brief_present": audit.brief_present,
            "brief_structure_valid": audit.brief_structure_valid,
            "roster_valid": audit.roster_valid,
            "watermark_aligned": audit.watermark_aligned,
            "rewrite_stale": audit.rewrite_stale,
            "notes": audit.notes,
        }
        # Brief-side drift: structurally invalid brief, invalid roster,
        # watermark misalignment, or staleness all count as drift the
        # doctor reports via exit-code 1 (when not in remediation mode).
        if (
            audit.brief_structure_valid is False
            or audit.roster_valid is False
            or not audit.watermark_aligned
            or audit.rewrite_stale
        ):
            brief_drift = True

    # BUG-AUDIT-94: --asset-audit extends the doctor with asset-state
    # drift detection — paper-figure files in the wrong location, missing
    # paper_attached events, papers_provided flag mismatch, etc.
    asset_drift = False
    if asset_audit:
        asset_report = _audit_assets(project_root)
        summary["asset_audit"] = asset_report
        asset_drift = bool(asset_report.get("drift", False))

    # BUG-AUDIT-99: --phase-audit extends the doctor with phase/sub_phase
    # drift detection — approved slides without phase advancement, etc.
    phase_drift = False
    if phase_audit:
        phase_report = _audit_phase(project_root)
        summary["phase_audit"] = phase_report
        phase_drift = bool(phase_report.get("drift", False))

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
        # Brief-audit notes are also surfaced when slide-drift is the
        # primary report, so a single doctor run shows everything.
        if brief_audit:
            for note in summary["brief_audit"]["notes"]:  # type: ignore[index]
                print(f"  brief_audit: {note}", file=sys.stderr)
        if asset_audit:
            for note in summary["asset_audit"]["notes"]:  # type: ignore[index]
                print(f"  asset_audit: {note}", file=sys.stderr)
        if phase_audit:
            for note in summary["phase_audit"]["notes"]:  # type: ignore[index]
                print(f"  phase_audit: {note}", file=sys.stderr)
        sys.exit(1)

    if brief_drift or asset_drift or phase_drift:
        drift_labels = []
        if brief_drift:
            drift_labels.append("brief-audit DRIFT")
        if asset_drift:
            drift_labels.append("asset-audit DRIFT")
        if phase_drift:
            drift_labels.append("phase-audit DRIFT")
        headline = "slides in sync; " + " and ".join(drift_labels)
        print(f"debrief doctor: {headline} — see notes:", file=sys.stderr)
        if brief_drift:
            for note in summary["brief_audit"]["notes"]:  # type: ignore[index]
                print(f"  brief_audit: {note}", file=sys.stderr)
        if asset_drift:
            for note in summary["asset_audit"]["notes"]:  # type: ignore[index]
                print(f"  asset_audit: {note}", file=sys.stderr)
        if phase_drift:
            for note in summary["phase_audit"]["notes"]:  # type: ignore[index]
                print(f"  phase_audit: {note}", file=sys.stderr)
        sys.exit(1)

    msg = f"debrief doctor: OK — {report.matched_count} slide(s) in sync."
    if brief_audit:
        msg += " Brief audit: clean."
    if asset_audit:
        msg += " Asset audit: clean."
    if phase_audit:
        msg += " Phase audit: clean."
    print(msg, file=sys.stderr)
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
    elif subcommand == "script_writer":
        # BC-3.20 / BUG-AUDIT-84 Sub-cycle B / REQ-SCRIPT-WRITER-1..4.
        # Reads agents/script-writer.md, calls the Anthropic API,
        # validates the six guardrails, backs up the existing
        # speaker_script.md, atomically writes the new one, emits
        # script_done. Exits 0 always per contract.
        import argparse as _ap

        _parser = _ap.ArgumentParser(
            prog="debrief.launcher script_writer",
            description=(
                "Generate the speaker script from brief + audience + "
                "timeline + dialog + slide records. Sole writer of "
                "speaker_script.md per BC-5.21."
            ),
        )
        _parser.add_argument(
            "--project-root", type=Path, default=Path.cwd()
        )
        _parser.add_argument(
            "--trigger",
            choices=[
                "/debrief:script",
                "deck-complete-finalization",
                "/debrief:handout-cascade",
            ],
            default="/debrief:script",
            help=(
                "Which trigger fired the script generation. Recorded "
                "in any script_errors.jsonl entry. Default assumes "
                "manual /debrief:script invocation."
            ),
        )
        _args = _parser.parse_args(sys.argv[2:])
        main_script_writer(
            _args.project_root,
            trigger=_args.trigger,
            plugin_root=plugin_root,
        )
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
        _parser.add_argument(
            "--brief-audit",
            action="store_true",
            help=(
                "BUG-AUDIT-83 / Cycle 2 Phase 5: also audit the memory "
                "architecture state — brief presence + structure + "
                "roster YAML validity + watermark alignment + rewrite "
                "staleness. Adds a `brief_audit` field to the JSON "
                "report. Brief-side drift is reported via exit code 1."
            ),
        )
        _parser.add_argument(
            "--asset-audit",
            action="store_true",
            help=(
                "BUG-AUDIT-94: also audit the assets/ tree for paper-handling "
                "drift — paper-figure-shaped files in the wrong location, "
                "missing paper_attached events, papers_provided flag mismatch, "
                "REQ-ASSET-1 slug-prefix violations. Adds an `asset_audit` "
                "field to the JSON report. Asset drift is reported via exit "
                "code 1."
            ),
        )
        _parser.add_argument(
            "--phase-audit",
            action="store_true",
            help=(
                "BUG-AUDIT-99: also audit debrief_state.phase / sub_phase "
                "against deck_state.slides — approved slides without phase "
                "advancement, style locked without sub_phase advancement, "
                "production phase stuck at group_planning despite approved "
                "slides. Adds a `phase_audit` field to the JSON report. "
                "Phase drift is reported via exit code 1; each note in the "
                "report includes a copy-pasteable recovery CLI command."
            ),
        )
        _args = _parser.parse_args(sys.argv[2:])
        main_doctor(
            _args.project_root,
            reconstruct=_args.reconstruct,
            brief_audit=_args.brief_audit,
            asset_audit=_args.asset_audit,
            phase_audit=_args.phase_audit,
        )
    elif subcommand == "archive_paper":
        # BC-3.21 / BUG-AUDIT-94: explicit retroactive paper-archival path
        # for cases where the consultant's automatic trigger detection
        # missed the user's paper.
        import argparse as _ap

        _parser = _ap.ArgumentParser(
            prog="debrief.launcher archive_paper",
            description=(
                "Archive a paper PDF retroactively: run paper_analyzer, "
                "set debrief_state.papers_provided=true, emit "
                "paper_attached event."
            ),
        )
        _parser.add_argument(
            "--pdf",
            type=Path,
            required=True,
            help="Path to the paper PDF to archive.",
        )
        _parser.add_argument(
            "--project-root",
            type=Path,
            default=Path.cwd(),
        )
        _args = _parser.parse_args(sys.argv[2:])
        main_archive_paper(_args.pdf, _args.project_root)
    else:
        print(f"Unknown subcommand: {subcommand!r}", file=sys.stderr)
        print(
            "Usage: python -m debrief.launcher [new|preflight|"
            "ensure_project|ensure_settings|doctor|commands|recall|"
            "rewrite_brief|emit_event|script_writer|archive_paper] "
            "[project_root]",
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
