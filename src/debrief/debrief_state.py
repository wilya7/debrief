# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 2: State Management Library.

Provides read/write helpers for deck_state.json and debrief_state.json,
plus utility functions for identifier sanitization and atomic JSON writes.
"""

from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Sentinel: check for json_repair at import time is deferred to call sites
# ---------------------------------------------------------------------------

_ENV_CORRUPTION_MSG = (
    "ERROR: json_repair is not installed or the conda environment is corrupt.\n"
    "Run: conda env create -f environment.yml  (see Section 9.3.1)\n"
    "The json_repair package is required for safe state-file handling.\n"
)


def _require_json_repair() -> None:
    """Exit(2) with env-corruption error when json_repair is unavailable."""
    if importlib.util.find_spec("json_repair") is None:
        print(_ENV_CORRUPTION_MSG, file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class StateCorruptError(Exception):
    """Raised when a state file cannot be repaired or contains invalid values."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SlideRecord:
    slug: str
    title: str
    status: str  # "draft" | "approved" | "needs_revision" | "discarded"
    backup: bool
    content_summary: Optional[str]
    visual_approach: Optional[str]
    design_choices: Optional[str]
    forks_not_taken: Optional[str]
    user_recommendations: Optional[str]
    qa_passed: bool  # True when QA passed (may be True via accepted violation)
    accepted_violations: list[dict[str, str]]  # [{"invariant":..,"reason":..}]
    last_modified: str  # ISO 8601 timestamp
    group_id: Optional[str]
    user_assets: list[str]  # relative paths of user-provided images
    has_math: bool  # True if slide contains rendered LaTeX math


@dataclass
class PresentationRecord:
    folder: str
    created_at: str
    slide_manifest: list[str]
    export_count: int
    script_count: int
    handout_count: int
    separator_position: Optional[int]
    separator_content: Optional[str]


@dataclass
class DeckState:
    project_name: str
    created_at: str
    archetype: str
    style_locked: bool
    closing_slide: Optional[str]
    slides: list[SlideRecord]
    presentations: list[PresentationRecord]


@dataclass
class DebriefState:
    phase: str
    sub_phase: str
    # active_agent enum per Section 17.5:
    #   "consultant" | "slide_maker" | "stylist" | "qa" | "none"
    active_agent: str
    archetype: str
    current_group_id: Optional[str]
    current_slide_slug: Optional[str]
    pending_gate: Optional[str]
    last_gate_response: Optional[str]
    red_green_iteration: int
    red_green_started_at: Optional[str]
    group_slide_index: int
    group_slide_count: int
    backup_mode: bool
    completed_groups: list[str]
    pre_view_state: Optional[dict[str, Any]]
    view_deferred: bool
    closing_slide_pending: bool
    group_revise_slug: Optional[str]
    style_import_mode: Optional[str]
    reference_provided: bool
    reference_modality: Optional[str]
    papers_provided: bool
    selected_figures: Optional[list[int] | str]
    session_started_at: str
    state_hash: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUB_PHASE_VALUES: frozenset[str] = frozenset(
    {
        "discovery/greeting",
        "discovery/dialog",
        "discovery/brief_review",
        "discovery/paper_analysis",
        "discovery/figure_selection",
        "discovery/style_analysis",
        "style/style_dialog",
        "style/style_review",
        "style/style_lock",
        "production/group_planning",
        "production/red_green",
        "production/diagnostic",
        "production/oscillation_review",
        "production/slide_review",
        "production/group_review",
        "production/more_slides",
        "production/deck_ending",
        "finalization/export_options",
        "finalization/backup_decision",
        "finalization/export_confirm",
        "finalization/reviewing_for_export",
        "finalization/exporting",
        "finalization/post_export",
        "complete",
    }
)
"""All valid sub_phase string values per Section 14.17."""

_VALID_PHASES = frozenset(
    {"discovery", "style", "production", "finalization", "complete"}
)
_VALID_ACTIVE_AGENTS = frozenset({"consultant", "slide_maker", "stylist", "qa", "none"})
_VALID_STYLE_IMPORT_MODES = frozenset({"baseline", "inspiration", None})
_VALID_REFERENCE_MODALITIES = frozenset({"pptx", "pdf", "html", "html_dir", None})

_DEBRIEF_REQUIRED_FIELDS = (
    "phase",
    "sub_phase",
    "active_agent",
    "archetype",
    "current_group_id",
    "current_slide_slug",
    "pending_gate",
    "last_gate_response",
    "red_green_iteration",
    "red_green_started_at",
    "group_slide_index",
    "group_slide_count",
    "backup_mode",
    "completed_groups",
    "pre_view_state",
    "view_deferred",
    "closing_slide_pending",
    "group_revise_slug",
    "style_import_mode",
    "reference_provided",
    "reference_modality",
    "papers_provided",
    "selected_figures",
    "session_started_at",
    "state_hash",
)

_DECK_REQUIRED_FIELDS = (
    "project_name",
    "created_at",
    "archetype",
    "style_locked",
    "closing_slide",
    "slides",
    "presentations",
)

_SLIDE_REQUIRED_FIELDS = (
    "slug",
    "title",
    "status",
    "content_summary",
    "visual_approach",
    "design_choices",
    "forks_not_taken",
    "user_recommendations",
    "qa_passed",
    "accepted_violations",
    "last_modified",
    "group_id",
    "backup",
    "user_assets",
    "has_math",
)


# ---------------------------------------------------------------------------
# Utility: atomic JSON write
# ---------------------------------------------------------------------------


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write data as JSON to path atomically.

    Writes to path.parent / (path.name + '.tmp'), fsyncs, then os.rename.
    Used by both state modules and Phase 2 draft-file writers.
    """
    tmp_path = path.parent / (path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.rename(tmp_path, path)


# ---------------------------------------------------------------------------
# sanitize_identifier
# ---------------------------------------------------------------------------


def sanitize_identifier(text: str, max_length: int = 40) -> str:
    """Apply the Debrief Identifier Sanitization Algorithm (Section 24.10.1).

    Steps applied in order:
    1. Convert to lowercase.
    2. Replace spaces and hyphens with underscores.
    3. Remove all characters not matching [a-z0-9_].
    4. Collapse consecutive underscores to a single underscore.
    5. Strip leading and trailing underscores.
    6. Truncate to max_length characters.
    7. If the result is empty, return 'untitled'.
    """
    # Step 1: lowercase
    result = text.lower()
    # Step 2: spaces and hyphens → underscores
    result = re.sub(r"[ \-]", "_", result)
    # Step 3: remove non-[a-z0-9_]
    result = re.sub(r"[^a-z0-9_]", "", result)
    # Step 4: collapse consecutive underscores
    result = re.sub(r"_+", "_", result)
    # Step 5: strip leading and trailing underscores
    result = result.strip("_")
    # Step 7: empty check BEFORE step 6 (per BC-2.16 / Section 24.10.1)
    if not result:
        return "untitled"
    # Step 6: truncate to max_length
    result = result[:max_length]
    return result


# ---------------------------------------------------------------------------
# compute_state_hash
# ---------------------------------------------------------------------------


def compute_state_hash(state_dict: dict[str, Any]) -> str:
    """Compute SHA-256 over canonical JSON of content fields, excluding state_hash.

    Returns the hex digest string.
    """
    payload_dict = {k: v for k, v in state_dict.items() if k != "state_hash"}
    payload = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# validate_debrief_state
# ---------------------------------------------------------------------------


def validate_debrief_state(state_dict: dict[str, Any]) -> None:
    """Validate all required fields, enum values, and non-negative counters.

    Raises StateCorruptError with a descriptive message on first violation.
    """
    # Check required fields
    for fld in _DEBRIEF_REQUIRED_FIELDS:
        if fld not in state_dict:
            raise StateCorruptError(f"debrief_state is missing required field: '{fld}'")

    # phase enum
    phase = state_dict["phase"]
    if phase not in _VALID_PHASES:
        raise StateCorruptError(
            f"field phase has invalid value: {phase!r}. "
            f"Must be one of {sorted(_VALID_PHASES)}"
        )

    # sub_phase enum
    sub_phase = state_dict["sub_phase"]
    if sub_phase not in SUB_PHASE_VALUES:
        raise StateCorruptError(f"field sub_phase has invalid value: {sub_phase!r}")

    # active_agent enum
    active_agent = state_dict["active_agent"]
    if active_agent not in _VALID_ACTIVE_AGENTS:
        raise StateCorruptError(
            f"field active_agent has invalid value: {active_agent!r}. "
            f"Must be one of {sorted(_VALID_ACTIVE_AGENTS)}"
        )

    # style_import_mode enum (None is valid)
    style_import_mode = state_dict.get("style_import_mode")
    if style_import_mode not in _VALID_STYLE_IMPORT_MODES:
        raise StateCorruptError(
            f"field style_import_mode has invalid value: {style_import_mode!r}. "
            f"Must be one of {_VALID_STYLE_IMPORT_MODES!r}"
        )

    # reference_modality enum (None is valid)
    reference_modality = state_dict.get("reference_modality")
    if reference_modality not in _VALID_REFERENCE_MODALITIES:
        raise StateCorruptError(
            f"field reference_modality has invalid value: {reference_modality!r}. "
            f"Must be one of {_VALID_REFERENCE_MODALITIES!r}"
        )

    # Non-negative counters
    for counter in ("red_green_iteration", "group_slide_index", "group_slide_count"):
        val = state_dict[counter]
        if not isinstance(val, int) or val < 0:
            raise StateCorruptError(
                f"field {counter} must be a non-negative integer, got: {val!r}"
            )


# ---------------------------------------------------------------------------
# SlideRecord helpers
# ---------------------------------------------------------------------------


def _dict_to_slide_record(d: dict[str, Any]) -> SlideRecord:
    """Convert a dict to SlideRecord, applying defaults for optional fields."""
    return SlideRecord(
        slug=d["slug"],
        title=d["title"],
        status=d["status"],
        backup=d.get("backup", False),
        content_summary=d.get("content_summary"),
        visual_approach=d.get("visual_approach"),
        design_choices=d.get("design_choices"),
        forks_not_taken=d.get("forks_not_taken"),
        user_recommendations=d.get("user_recommendations"),
        qa_passed=d.get("qa_passed", False),
        accepted_violations=d.get("accepted_violations", []),
        last_modified=d.get("last_modified", ""),
        group_id=d.get("group_id"),
        user_assets=d.get("user_assets", []),
        has_math=d.get("has_math", False),
    )


def _slide_record_to_dict(s: SlideRecord) -> dict[str, Any]:
    """Convert SlideRecord to dict with all required fields."""
    return {
        "slug": s.slug,
        "title": s.title,
        "status": s.status,
        "backup": s.backup,
        "content_summary": s.content_summary,
        "visual_approach": s.visual_approach,
        "design_choices": s.design_choices,
        "forks_not_taken": s.forks_not_taken,
        "user_recommendations": s.user_recommendations,
        "qa_passed": s.qa_passed,
        "accepted_violations": s.accepted_violations,
        "last_modified": s.last_modified,
        "group_id": s.group_id,
        "user_assets": s.user_assets,
        "has_math": s.has_math,
    }


def _dict_to_presentation_record(d: dict[str, Any]) -> PresentationRecord:
    """Convert a dict to PresentationRecord."""
    return PresentationRecord(
        folder=d["folder"],
        created_at=d["created_at"],
        slide_manifest=d.get("slide_manifest", []),
        export_count=d.get("export_count", 0),
        script_count=d.get("script_count", 0),
        handout_count=d.get("handout_count", 0),
        separator_position=d.get("separator_position"),
        separator_content=d.get("separator_content"),
    )


def _presentation_record_to_dict(p: PresentationRecord) -> dict[str, Any]:
    """Convert PresentationRecord to dict."""
    return {
        "folder": p.folder,
        "created_at": p.created_at,
        "slide_manifest": p.slide_manifest,
        "export_count": p.export_count,
        "script_count": p.script_count,
        "handout_count": p.handout_count,
        "separator_position": p.separator_position,
        "separator_content": p.separator_content,
    }


# ---------------------------------------------------------------------------
# DeckState read/write
# ---------------------------------------------------------------------------


def _deck_state_to_dict(state: DeckState) -> dict[str, Any]:
    """Serialize DeckState to a JSON-compatible dict."""
    return {
        "project_name": state.project_name,
        "created_at": state.created_at,
        "archetype": state.archetype,
        "style_locked": state.style_locked,
        "closing_slide": state.closing_slide,
        "slides": [_slide_record_to_dict(s) for s in state.slides],
        "presentations": [_presentation_record_to_dict(p) for p in state.presentations],
    }


def _dict_to_deck_state(d: dict[str, Any]) -> DeckState:
    """Deserialize dict to DeckState."""
    slides = [_dict_to_slide_record(s) for s in d.get("slides", [])]
    presentations = [
        _dict_to_presentation_record(p) for p in d.get("presentations", [])
    ]
    return DeckState(
        project_name=d["project_name"],
        created_at=d["created_at"],
        archetype=d["archetype"],
        style_locked=d["style_locked"],
        closing_slide=d.get("closing_slide"),
        slides=slides,
        presentations=presentations,
    )


def read_deck_state(project_root: Path) -> DeckState:
    """Read and validate deck_state.json from project_root.

    Uses json_repair as a safety net for LLM-generated JSON.
    Raises StateCorruptError if repair fails or required top-level fields
    are missing after repair.
    """
    _require_json_repair()

    import json_repair  # noqa: PLC0415

    state_path = project_root / "deck_state.json"
    raw_text = state_path.read_text(encoding="utf-8")

    try:
        data = json_repair.repair_json(raw_text, return_objects=True)
    except Exception as exc:
        raise StateCorruptError(f"deck_state.json could not be parsed: {exc}") from exc

    if not isinstance(data, dict):
        raise StateCorruptError(
            "deck_state.json does not contain a JSON object after repair"
        )

    for fld in _DECK_REQUIRED_FIELDS:
        if fld not in data:
            raise StateCorruptError(
                f"deck_state.json is missing required field: '{fld}'"
            )

    try:
        return _dict_to_deck_state(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise StateCorruptError(
            f"deck_state.json contains invalid field values: {exc}"
        ) from exc


def write_deck_state(project_root: Path, state: DeckState) -> None:
    """Atomically write deck_state.json using write-to-tmp then os.rename().

    No file lock (single-session model, no concurrent writers for deck state).
    """
    dest = project_root / "deck_state.json"
    atomic_write_json(dest, _deck_state_to_dict(state))


# ---------------------------------------------------------------------------
# DeckState query helpers
# ---------------------------------------------------------------------------


def get_approved_slides(
    state: DeckState,
    backup: Optional[bool] = None,
) -> list[SlideRecord]:
    """Return slides with status == 'approved', preserving array order.

    If backup is not None, filter to slides where slide.backup == backup.
    """
    result = [s for s in state.slides if s.status == "approved"]
    if backup is not None:
        result = [s for s in result if s.backup == backup]
    return result


def get_slide_by_slug(state: DeckState, slug: str) -> Optional[SlideRecord]:
    """Return the slide record for the given slug, or None if absent or discarded."""
    for slide in state.slides:
        if slide.slug == slug:
            if slide.status == "discarded":
                return None
            return slide
    return None


# ---------------------------------------------------------------------------
# increment_* helpers
# ---------------------------------------------------------------------------


def increment_export_count(state: DeckState, folder: str) -> None:
    """Increment export_count for the matching presentation record in-place.

    Raises KeyError if no record with the given folder exists.
    Does NOT write the state.
    """
    for rec in state.presentations:
        if rec.folder == folder:
            rec.export_count += 1
            return
    raise KeyError(f"No presentation record with folder: {folder!r}")


def increment_script_count(state: DeckState, folder: str) -> None:
    """Increment script_count for the matching presentation record in-place.

    Raises KeyError if no record with the given folder exists.
    Does NOT write the state.
    """
    for rec in state.presentations:
        if rec.folder == folder:
            rec.script_count += 1
            return
    raise KeyError(f"No presentation record with folder: {folder!r}")


def increment_handout_count(state: DeckState, folder: str) -> None:
    """Increment handout_count for the matching presentation record in-place.

    Raises KeyError if no record with the given folder exists.
    Does NOT write the state.
    """
    for rec in state.presentations:
        if rec.folder == folder:
            rec.handout_count += 1
            return
    raise KeyError(f"No presentation record with folder: {folder!r}")


# ---------------------------------------------------------------------------
# DebriefState serialization helpers
# ---------------------------------------------------------------------------


def _debrief_state_to_dict(state: DebriefState) -> dict[str, Any]:
    """Serialize DebriefState to a JSON-compatible dict."""
    return {
        "phase": state.phase,
        "sub_phase": state.sub_phase,
        "active_agent": state.active_agent,
        "archetype": state.archetype,
        "current_group_id": state.current_group_id,
        "current_slide_slug": state.current_slide_slug,
        "pending_gate": state.pending_gate,
        "last_gate_response": state.last_gate_response,
        "red_green_iteration": state.red_green_iteration,
        "red_green_started_at": state.red_green_started_at,
        "group_slide_index": state.group_slide_index,
        "group_slide_count": state.group_slide_count,
        "backup_mode": state.backup_mode,
        "completed_groups": state.completed_groups,
        "pre_view_state": state.pre_view_state,
        "view_deferred": state.view_deferred,
        "closing_slide_pending": state.closing_slide_pending,
        "group_revise_slug": state.group_revise_slug,
        "style_import_mode": state.style_import_mode,
        "reference_provided": state.reference_provided,
        "reference_modality": state.reference_modality,
        "papers_provided": state.papers_provided,
        "selected_figures": state.selected_figures,
        "session_started_at": state.session_started_at,
        "state_hash": state.state_hash,
    }


def _dict_to_debrief_state(d: dict[str, Any]) -> DebriefState:
    """Deserialize dict to DebriefState."""
    return DebriefState(
        phase=d["phase"],
        sub_phase=d["sub_phase"],
        active_agent=d["active_agent"],
        archetype=d["archetype"],
        current_group_id=d.get("current_group_id"),
        current_slide_slug=d.get("current_slide_slug"),
        pending_gate=d.get("pending_gate"),
        last_gate_response=d.get("last_gate_response"),
        red_green_iteration=d["red_green_iteration"],
        red_green_started_at=d.get("red_green_started_at"),
        group_slide_index=d["group_slide_index"],
        group_slide_count=d["group_slide_count"],
        backup_mode=d["backup_mode"],
        completed_groups=d.get("completed_groups", []),
        pre_view_state=d.get("pre_view_state"),
        view_deferred=d["view_deferred"],
        closing_slide_pending=d["closing_slide_pending"],
        group_revise_slug=d.get("group_revise_slug"),
        style_import_mode=d.get("style_import_mode"),
        reference_provided=d["reference_provided"],
        reference_modality=d.get("reference_modality"),
        papers_provided=d["papers_provided"],
        selected_figures=d.get("selected_figures"),
        session_started_at=d["session_started_at"],
        state_hash=d.get("state_hash", ""),
    )


# ---------------------------------------------------------------------------
# DebriefState read/write
# ---------------------------------------------------------------------------


def read_debrief_state(project_root: Path) -> DebriefState:
    """Read and validate debrief_state.json from project_root.

    Performs SHA-256 hash verification. If hash mismatches but content is
    structurally valid, recomputes and updates the hash, emits warning to stderr.
    If content is malformed or any field holds an invalid value, raises
    StateCorruptError.
    """
    _require_json_repair()

    import json_repair  # noqa: PLC0415

    state_path = project_root / "debrief_state.json"
    raw_text = state_path.read_text(encoding="utf-8")

    try:
        data = json_repair.repair_json(raw_text, return_objects=True)
    except Exception as exc:
        raise StateCorruptError(
            f"debrief_state.json could not be parsed: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise StateCorruptError(
            "debrief_state.json does not contain a JSON object after repair"
        )

    # Check for required fields before hash verification
    for fld in _DEBRIEF_REQUIRED_FIELDS:
        if fld not in data:
            raise StateCorruptError(
                f"debrief_state.json is missing required field: '{fld}'"
            )

    # Hash verification (BC-2.5)
    stored_hash = data.get("state_hash", "")
    content_without_hash = {k: v for k, v in data.items() if k != "state_hash"}
    expected_hash = compute_state_hash(content_without_hash)

    if stored_hash != expected_hash:
        # Validate content first; raise if invalid
        validate_debrief_state(data)
        # Content is valid — recompute and warn
        data["state_hash"] = expected_hash
        print(
            "WARNING: debrief_state.json hash mismatch \u2014 recomputed. "
            "File may have been externally modified.",
            file=sys.stderr,
        )
    else:
        # Hash matches — still validate enum/counter fields
        validate_debrief_state(data)

    try:
        return _dict_to_debrief_state(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise StateCorruptError(
            f"debrief_state.json contains invalid field values: {exc}"
        ) from exc


def write_debrief_state(project_root: Path, state: DebriefState) -> None:
    """Atomically write debrief_state.json with fcntl.flock on .debrief/state.lock.

    Protocol:
    1. Acquire exclusive lock on .debrief/state.lock.
    2. Recompute state_hash before serializing.
    3. Write to debrief_state.json.tmp.
    4. fsync the tmp file.
    5. os.rename to debrief_state.json.
    6. Release lock.
    """
    lock_path = project_root / ".debrief" / "state.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    lock_fd = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)

        # Serialize to dict
        data = _debrief_state_to_dict(state)

        # BC-2.4: recompute hash before writing
        content_without_hash = {k: v for k, v in data.items() if k != "state_hash"}
        data["state_hash"] = compute_state_hash(content_without_hash)

        dest = project_root / "debrief_state.json"
        atomic_write_json(dest, data)
    finally:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()
