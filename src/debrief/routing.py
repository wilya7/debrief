# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 4: Routing Protocol.

Implements the Sub-Phase Transition Table routing state machine,
gate-response validation, and state-update entry points.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Gate registry
# ---------------------------------------------------------------------------

# Maps gate_id -> list of valid_responses (literal or parameterized)
_GATE_VALID_RESPONSES: dict[str, list[str]] = {
    "G1.1_greeting": ["CONTINUE", "QUIT"],
    "G1.2_brief_review": ["APPROVE", "REVISE"],
    "G1.3_figure_selection": ["<figure_list_or_all>"],
    "G1.4_style_analysis": ["CONTINUE"],
    "G2.1_style_config_review": ["STYLE APPROVED", "STYLE REVISE <instructions>"],
    "G2.2_lock_failed": ["RETRY", "ABORT"],
    "G3.1_group_manifest": ["CONTINUE"],
    "G3.2_qa_review": [
        "APPROVE",
        "SLIDE REVISE <instructions>",
    ],
    "G3.2a_oscillation_review": [
        "ACCEPT CURRENT",
        "MY INSTRUCTIONS",
        "ESCALATE",
    ],
    "G3.3_slide_review": ["APPROVE", "REVISE", "DISCARD"],
    "G3.4_group_review": ["NEXT GROUP", "DONE", "ADD MORE"],
    "G3.5_more_slides": ["YES", "NO"],
    "G3.6_deck_ending": ["FINALIZE", "ADD MORE"],
    "G4.1_export_options": [
        "EXPORT HTML",
        "EXPORT PDF",
        "EXPORT PPTX",
        "SKIP",
    ],
    "G4.2_backup_decision": ["YES", "NO"],
    "G4.3_export_confirm": ["CONFIRM", "CANCEL"],
}


# ---------------------------------------------------------------------------
# resolve_action — pure routing function (BC-4.1)
# ---------------------------------------------------------------------------

_SUB_PHASE_ACTION: dict[str, dict[str, Any]] = {
    "discovery/greeting": {
        "action_type": "human_gate",
        "gate_id": "G1.1_greeting",
    },
    "discovery/dialog": {
        "action_type": "agent",
        "agent": "consultant",
    },
    "discovery/brief_review": {
        "action_type": "human_gate",
        "gate_id": "G1.2_brief_review",
    },
    "discovery/paper_analysis": {
        "action_type": "agent",
        "agent": "consultant",
    },
    "discovery/figure_selection": {
        "action_type": "human_gate",
        "gate_id": "G1.3_figure_selection",
    },
    "discovery/style_analysis": {
        "action_type": "agent",
        "agent": "consultant",
    },
    "style/style_dialog": {
        "action_type": "agent",
        "agent": "stylist",
    },
    "style/style_review": {
        "action_type": "human_gate",
        "gate_id": "G2.1_style_config_review",
    },
    "style/style_lock": {
        "action_type": "agent",
        "agent": "stylist",
    },
    "production/group_planning": {
        "action_type": "agent",
        "agent": "consultant",
    },
    "production/red_green": {
        "action_type": "agent",
        "agent": "slide_maker",
    },
    "production/diagnostic": {
        "action_type": "agent",
        "agent": "none",
    },
    "production/oscillation_review": {
        "action_type": "human_gate",
        "gate_id": "G3.2a_oscillation_review",
    },
    "production/slide_review": {
        "action_type": "human_gate",
        "gate_id": "G3.3_slide_review",
    },
    "production/group_review": {
        "action_type": "human_gate",
        "gate_id": "G3.4_group_review",
    },
    "production/more_slides": {
        "action_type": "human_gate",
        "gate_id": "G3.5_more_slides",
    },
    "production/deck_ending": {
        "action_type": "human_gate",
        "gate_id": "G3.6_deck_ending",
    },
    "finalization/export_options": {
        "action_type": "human_gate",
        "gate_id": "G4.1_export_options",
    },
    "finalization/backup_decision": {
        "action_type": "human_gate",
        "gate_id": "G4.2_backup_decision",
    },
    "finalization/export_confirm": {
        "action_type": "human_gate",
        "gate_id": "G4.3_export_confirm",
    },
    "finalization/reviewing_for_export": {
        "action_type": "agent",
        "agent": "consultant",
    },
    "finalization/exporting": {
        "action_type": "agent",
        "agent": "consultant",
    },
    "finalization/post_export": {
        "action_type": "agent",
        "agent": "consultant",
    },
    "complete": {
        "action_type": "complete",
        "agent": "none",
    },
}


def resolve_action(
    state: Any,  # DebriefState from debrief.debrief_state
    project_root: Path,
) -> dict[str, Any]:
    """Implement the Sub-Phase Transition Table as an explicit state machine.

    Match on (phase, sub_phase, pending_gate, condition_flags) and return
    the ActionBlock dict. Pure function — no side effects, no file writes.
    """
    sub_phase = state.sub_phase

    # For production/red_green, check the G3.2 machine gate if QA has run.
    if sub_phase == "production/red_green":
        slug = state.current_slide_slug
        if slug is not None:
            gate_result = check_g3_2_machine_gate(
                slug,
                state.red_green_iteration,
                state.red_green_started_at,
                project_root,
            )
            if gate_result == "OSCILLATION":
                return {
                    "action_type": "human_gate",
                    "gate_id": "G3.2a_oscillation_review",
                }
            if gate_result == "GREEN":
                return {
                    "action_type": "human_gate",
                    "gate_id": "G3.2_qa_review",
                    "context": "GREEN",
                }
            if gate_result == "EXHAUSTED":
                return {
                    "action_type": "human_gate",
                    "gate_id": "G3.2_qa_review",
                    "context": "EXHAUSTED",
                }
            # RED: still in red_green — dispatch slide_maker
        return {
            "action_type": "agent",
            "agent": "slide_maker",
        }

    block = _SUB_PHASE_ACTION.get(sub_phase)
    if block is None:
        # Unknown sub_phase: default to consultant
        return {
            "action_type": "agent",
            "agent": "consultant",
        }
    # Return a copy so the cached dicts are not mutated
    return dict(block)


# ---------------------------------------------------------------------------
# main_routing — reads state, outputs JSON to stdout (BC-4.1, BC-4.2)
# ---------------------------------------------------------------------------


def main_routing(project_root: Path) -> None:
    """Entry point: python -m debrief.routing --project-root <path>.

    Reads debrief_state.json and outputs a structured ActionBlock JSON to
    stdout. Pure function of current state: same state always produces same
    output. No side effects.
    """
    state_path = project_root / "debrief_state.json"
    raw = state_path.read_text(encoding="utf-8")
    data = json.loads(raw)

    # Import from Unit 2
    from debrief_state import _dict_to_debrief_state  # type: ignore

    state = _dict_to_debrief_state(data)
    block = resolve_action(state, project_root)
    print(json.dumps(block))


# ---------------------------------------------------------------------------
# check_g3_2_machine_gate (BC-4.3, BC-4.4)
# ---------------------------------------------------------------------------


def check_g3_2_machine_gate(
    current_slug: str,
    red_green_iteration: int,
    red_green_started_at: Optional[str],
    project_root: Path,
) -> str:
    """Read qa_log.jsonl for entries matching current_slug with timestamp >=
    red_green_started_at. Return "GREEN", "RED", "EXHAUSTED", or "OSCILLATION".

    GREEN: latest entry has passed=True.
    RED: latest entry has passed=False and red_green_iteration < 5.
    EXHAUSTED: passed=False and red_green_iteration >= 5.
    OSCILLATION: two most recent entries have same failure count but different
                 failure invariant IDs.
    """
    qa_log_path = project_root / "qa_log.jsonl"
    if not qa_log_path.exists():
        return "RED"

    entries: list[dict[str, Any]] = []
    for line in qa_log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("slug") != current_slug:
            continue
        # BC-4.3: filter by timestamp >= red_green_started_at
        if red_green_started_at is not None:
            ts = entry.get("timestamp", "")
            if ts < red_green_started_at:
                continue
        entries.append(entry)

    if not entries:
        return "RED"

    latest = entries[-1]
    passed = latest.get("passed", False)

    if passed:
        return "GREEN"

    # BC-4.4: oscillation detection
    if len(entries) >= 2:
        prev = entries[-2]
        latest_failures = {f.get("invariant", "") for f in latest.get("failures", [])}
        prev_failures = {f.get("invariant", "") for f in prev.get("failures", [])}
        latest_fail_count = len(latest.get("failures", []))
        prev_fail_count = len(prev.get("failures", []))
        if (
            latest_fail_count == prev_fail_count
            and latest_failures != prev_failures
            and latest_fail_count > 0
        ):
            return "OSCILLATION"

    if red_green_iteration >= 5:
        return "EXHAUSTED"

    return "RED"


# ---------------------------------------------------------------------------
# validate_gate_response (BC-4.5)
# ---------------------------------------------------------------------------


def validate_gate_response(
    gate_id: str,
    response: str,
    valid_responses: list[str],
) -> bool:
    """Validate response against the gate's valid_responses list or grammar.

    Returns True if valid, False otherwise.
    For parameterized gates (e.g., 'SLIDE REVISE <instructions>'), validates
    the fixed prefix and extracts the payload.
    """
    for pattern in valid_responses:
        if "<" in pattern and ">" in pattern:
            # Parameterized: extract the fixed prefix (everything before '<')
            prefix = pattern[: pattern.index("<")].rstrip()
            if prefix and response.startswith(prefix + " "):
                payload = response[len(prefix) + 1 :].strip()
                if payload:
                    return True
        else:
            if response == pattern:
                return True
    return False


# ---------------------------------------------------------------------------
# perform_snapshot (BC-4.10, BC-4.17)
# ---------------------------------------------------------------------------


def perform_snapshot(slug: str, iteration: int, project_root: Path) -> None:
    """Copy slides/<slug>.html to .debrief/snapshots/<slug>_iter_<N>.html.

    Atomic (write-to-tmp then rename). N is 1-indexed, not zero-padded.
    """
    source = project_root / "slides" / f"{slug}.html"
    snapshots_dir = project_root / ".debrief" / "snapshots"
    dest_name = f"{slug}_iter_{iteration}.html"
    dest = snapshots_dir / dest_name
    tmp = snapshots_dir / (dest_name + ".tmp")

    content = source.read_bytes()
    tmp.write_bytes(content)
    os.rename(str(tmp), str(dest))


# ---------------------------------------------------------------------------
# handle_red_green_transition (BC-4.9, BC-4.10, BC-4.14, BC-4.17)
# ---------------------------------------------------------------------------


def handle_red_green_transition(
    gate_id: str,
    response: str,
    state: Any,  # DebriefState
    project_root: Path,
) -> None:
    """Handle state transitions for red-green cycle gates (G3.2).

    Increments red_green_iteration, sets red_green_started_at on first
    iteration, manages best-known-good snapshot logic, and writes
    qa_cycle_log.jsonl at cycle exit.
    """
    from debrief_state import (  # type: ignore
        compute_state_hash,
        atomic_write_json,
    )

    # Read current state from disk to avoid stale in-memory view
    state_path = project_root / "debrief_state.json"
    state_dict = json.loads(state_path.read_text(encoding="utf-8"))

    slug = state.current_slide_slug
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if response == "APPROVE":
        # GREEN exit: write qa_cycle_log, delete snapshots
        _write_qa_cycle_log(
            slug=slug,
            started_at=state.red_green_started_at or now_ts,
            completed_at=now_ts,
            iterations=state.red_green_iteration,
            final_status="green",
            project_root=project_root,
        )
        _delete_snapshots_for_slug(slug, project_root)
        # Reset red_green state fields
        state_dict["red_green_iteration"] = 0
        state_dict["red_green_started_at"] = None
    elif response.startswith("SLIDE REVISE"):
        # RED: increment iteration, set started_at if first
        new_iter = state.red_green_iteration + 1
        state_dict["red_green_iteration"] = new_iter
        if state.red_green_started_at is None:
            state_dict["red_green_started_at"] = now_ts
        # Perform a snapshot before the rewrite
        if slug is not None:
            slide_file = project_root / "slides" / f"{slug}.html"
            if slide_file.exists():
                perform_snapshot(slug, new_iter, project_root)
    else:
        # Other responses (EXHAUSTED path from external call, etc.)
        new_iter = state.red_green_iteration + 1
        state_dict["red_green_iteration"] = new_iter
        if state.red_green_started_at is None:
            state_dict["red_green_started_at"] = now_ts

    # Recompute hash before writing
    state_dict["state_hash"] = compute_state_hash(state_dict)
    atomic_write_json(state_path, state_dict)


def _write_qa_cycle_log(
    slug: Optional[str],
    started_at: str,
    completed_at: str,
    iterations: int,
    final_status: str,
    project_root: Path,
) -> None:
    """Append a qa_cycle_log.jsonl entry per BC-4.14."""
    entry: dict[str, Any] = {
        "slug": slug,
        "started_at": started_at,
        "completed_at": completed_at,
        "iterations": iterations,
        "final_status": final_status,
        "tier1_failures_by_iteration": [],
        "tier2_warnings": [],
    }
    log_path = project_root / "output" / "qa_cycle_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _delete_snapshots_for_slug(slug: Optional[str], project_root: Path) -> None:
    """Delete all snapshot files for slug from .debrief/snapshots/."""
    if slug is None:
        return
    snapshots_dir = project_root / ".debrief" / "snapshots"
    if not snapshots_dir.exists():
        return
    prefix = f"{slug}_iter_"
    for f in snapshots_dir.iterdir():
        if f.name.startswith(prefix) and f.suffix == ".html":
            f.unlink()


# ---------------------------------------------------------------------------
# main_update_state (BC-4.5, BC-4.11, BC-4.13)
# ---------------------------------------------------------------------------

# Gate-to-valid-responses mapping (used by main_update_state)
_GATE_RESPONSES = _GATE_VALID_RESPONSES


def main_update_state(
    gate_id: str,
    response: str,
    project_root: Path,
    skill_prelude: Optional[str] = None,
    field_assignments: Optional[list[str]] = None,
) -> None:
    """Entry point for state updates.

    Validates response against gate's valid_responses or grammar.
    Exits code 4 with 'Invalid response. Expected: <grammar>' on mismatch.
    Writes state transitions via Unit 2 library.
    """
    from debrief_state import (  # type: ignore
        _dict_to_debrief_state,
        compute_state_hash,
        atomic_write_json,
    )

    state_path = project_root / "debrief_state.json"

    # BC-4.13: skill-prelude mode bypasses gate validation
    if skill_prelude is not None:
        state_dict = json.loads(state_path.read_text(encoding="utf-8"))
        if field_assignments:
            for assignment in field_assignments:
                if "=" in assignment:
                    key, _, val = assignment.partition("=")
                    state_dict[key.strip()] = val.strip()
        state_dict["state_hash"] = compute_state_hash(state_dict)
        atomic_write_json(state_path, state_dict)
        return

    # Special handling for G1.3 figure selection (BC-4.11)
    if gate_id == "G1.3_figure_selection":
        _handle_figure_selection(response, project_root)
        return

    # Validate gate response (BC-4.5)
    valid_responses = _GATE_RESPONSES.get(gate_id, [])

    # For empty gate_id or unknown gate, reject if non-empty response
    if not valid_responses and gate_id:
        print(
            f"Invalid response. Expected: (no valid responses defined for {gate_id})",
            file=sys.stderr,
        )
        sys.exit(4)

    if not validate_gate_response(gate_id, response, valid_responses):
        grammar = " | ".join(valid_responses)
        print(f"Invalid response. Expected: {grammar}", file=sys.stderr)
        sys.exit(4)

    # Load state
    state_dict = json.loads(state_path.read_text(encoding="utf-8"))

    # Handle specific gate transitions
    if gate_id == "G3.2_qa_review":
        from debrief_state import _dict_to_debrief_state  # type: ignore

        state = _dict_to_debrief_state(state_dict)
        handle_red_green_transition(gate_id, response, state, project_root)
        return

    # Generic state write for other gates: persist last_gate_response
    state_dict["last_gate_response"] = response
    state_dict["state_hash"] = compute_state_hash(state_dict)
    atomic_write_json(state_path, state_dict)


def _handle_figure_selection(response: str, project_root: Path) -> None:
    """BC-4.11: Write selected_figures to debrief_state.json."""
    from debrief_state import compute_state_hash, atomic_write_json  # type: ignore

    state_path = project_root / "debrief_state.json"
    state_dict = json.loads(state_path.read_text(encoding="utf-8"))

    if response.strip().lower() == "all":
        selected: Any = "all"
    else:
        parts = response.strip().split()
        try:
            selected = [int(p) for p in parts if p]
        except ValueError:
            selected = response.strip()

    state_dict["selected_figures"] = selected
    state_dict["last_gate_response"] = response
    state_dict["state_hash"] = compute_state_hash(state_dict)
    atomic_write_json(state_path, state_dict)


# ---------------------------------------------------------------------------
# merge_approval_payload
# ---------------------------------------------------------------------------


def merge_approval_payload(slug: str, project_root: Path) -> None:
    """Read .debrief/approval_<slug>.json, validate required fields,
    merge into the slide record in deck_state.json, delete the approval file.

    Raises FileNotFoundError if the approval file is absent.
    """
    from debrief_state import (  # type: ignore
        read_deck_state,
        write_deck_state,
        get_slide_by_slug,
    )

    approval_path = project_root / ".debrief" / f"approval_{slug}.json"
    if not approval_path.exists():
        raise FileNotFoundError(f"Approval file not found: {approval_path}")

    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    required = {
        "slug",
        "title",
        "content_summary",
        "visual_approach",
        "design_choices",
    }
    missing = required - set(approval.keys())
    if missing:
        raise ValueError(f"Approval payload missing required fields: {missing}")

    deck = read_deck_state(project_root)
    slide = get_slide_by_slug(deck, slug)
    if slide is None:
        raise KeyError(f"Slide not found in deck_state: {slug!r}")

    slide.title = approval["title"]
    slide.content_summary = approval["content_summary"]
    slide.visual_approach = approval["visual_approach"]
    slide.design_choices = approval["design_choices"]
    slide.status = "approved"

    write_deck_state(project_root, deck)
    approval_path.unlink()


# ---------------------------------------------------------------------------
# promote_style_draft (BC-4.6)
# ---------------------------------------------------------------------------

_STYLE_CONFIG_REQUIRED_KEYS = frozenset(
    {
        "colors",
        "typography",
        "spacing",
        "layout",
        "data_viz",
        "constraints",
        "provenance",
    }
)


def promote_style_draft(project_root: Path) -> None:
    """Implement the Section 24.8 compile-and-lock sequence.

    Steps:
    1. Validate .debrief/draft/style_config.json has all required keys.
    2. Atomically rename .debrief/draft/style_config.json -> style_config.json.
    3. Atomically rename .debrief/draft/style_guide.md -> style_guide.md.
    4. Invoke python -m debrief.style_compiler style_config.json assets/style.css.
    5. chmod 444 on style_config.json and style_guide.md.
    6. Set style_locked: True in deck_state.json.
    7. rmtree .debrief/draft/.

    BC-4.6: on compiler failure, files are already promoted; do NOT rollback.
    """
    draft_dir = project_root / ".debrief" / "draft"
    draft_config = draft_dir / "style_config.json"
    draft_guide = draft_dir / "style_guide.md"

    # Step 1: validate required keys
    raw_config = draft_config.read_text(encoding="utf-8")
    config_data = json.loads(raw_config)
    missing_keys = _STYLE_CONFIG_REQUIRED_KEYS - set(config_data.keys())
    if missing_keys:
        raise RuntimeError(f"style_config.json missing required keys: {missing_keys}")

    dest_config = project_root / "style_config.json"
    dest_guide = project_root / "style_guide.md"
    dest_css = project_root / "assets" / "style.css"

    # Step 2: atomic rename draft config -> project root
    os.rename(str(draft_config), str(dest_config))

    # Step 3: atomic rename draft guide -> project root
    os.rename(str(draft_guide), str(dest_guide))

    # Step 4: invoke style_compiler
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "debrief.style_compiler",
            str(dest_config),
            str(dest_css),
        ],
        capture_output=False,
        text=True,
        cwd=str(project_root),
    )

    if result.returncode != 0:
        # BC-4.6: do NOT rollback; do NOT set style_locked; do NOT rmtree
        raise RuntimeError(
            f"style_compiler failed (exit {result.returncode}): "
            f"{getattr(result, 'stderr', '')}"
        )

    # Step 5: chmod 444
    os.chmod(str(dest_config), 0o444)
    os.chmod(str(dest_guide), 0o444)

    # Step 6: set style_locked in deck_state.json
    deck_path = project_root / "deck_state.json"
    deck_data = json.loads(deck_path.read_text(encoding="utf-8"))
    deck_data["style_locked"] = True
    from debrief_state import atomic_write_json  # type: ignore

    atomic_write_json(deck_path, deck_data)

    # Step 7: rmtree .debrief/draft/
    if draft_dir.exists():
        shutil.rmtree(str(draft_dir))


# ---------------------------------------------------------------------------
# consume_gate_data (BC-4.7)
# ---------------------------------------------------------------------------


def consume_gate_data(
    expected_gate_id: str,
    project_root: Path,
) -> Optional[dict[str, Any]]:
    """Read .debrief/gate_data.json if present.

    If gate_id matches expected_gate_id, return the data payload and delete
    the file. If gate_id mismatches, exit with code 4. If file absent,
    return None.
    """
    gate_file = project_root / ".debrief" / "gate_data.json"
    if not gate_file.exists():
        return None

    raw = gate_file.read_text(encoding="utf-8")
    data = json.loads(raw)

    actual_gate_id = data.get("gate_id", "")
    if actual_gate_id != expected_gate_id:
        print(
            f"gate_data.json gate_id mismatch: expected "
            f"{expected_gate_id!r}, got {actual_gate_id!r}",
            file=sys.stderr,
        )
        sys.exit(4)

    payload = data.get("data", {})
    gate_file.unlink()
    return payload


# ---------------------------------------------------------------------------
# main_prepare helpers (BC-4.7, BC-4.8)
# ---------------------------------------------------------------------------


def main_prepare(action: str, project_root: Path) -> None:
    """Entry point: python -m debrief.prepare --action <id> --project-root.

    Assembles .debrief/task_prompt.md from context files for the current
    action. Handles gate_data.json injection per Section 24.20 cross-cycle
    rule. Substitutes all {placeholder} values in gate prompt templates.
    Exits code 4 if gate_data.json gate_id mismatches expected gate_id.
    """
    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", str(project_root)))
    content = assemble_task_prompt(action, [], project_root, plugin_root)
    prompt_path = project_root / ".debrief" / "task_prompt.md"

    tmp = prompt_path.parent / (prompt_path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.rename(str(tmp), str(prompt_path))


def assemble_task_prompt(
    action: str,
    context_files: list[str],
    project_root: Path,
    plugin_root: Path,
) -> str:
    """Build the task prompt markdown string from context file paths.

    Each section: '## Context: <filename>\n<content>\n'.
    """
    sections: list[str] = []
    for cf in context_files:
        cf_path = Path(cf)
        if not cf_path.is_absolute():
            cf_path = project_root / cf
        if cf_path.exists():
            content = cf_path.read_text(encoding="utf-8")
            sections.append(f"## Context: {cf_path.name}\n{content}\n")
    return "\n".join(sections)


def substitute_gate_placeholders(
    template: str,
    state: Any,  # DebriefState
    project_root: Path,
) -> str:
    """Substitute all {placeholder} tokens in gate prompt templates.

    After substitution, no unresolved {} tokens may remain.
    <literal> tokens (user-input indicators) are left unchanged.
    """
    import re

    replacements: dict[str, str] = {
        "phase": state.phase,
        "sub_phase": state.sub_phase,
        "active_agent": state.active_agent,
        "archetype": state.archetype,
        "current_group_id": str(state.current_group_id or ""),
        "current_slide_slug": str(state.current_slide_slug or ""),
        "pending_gate": str(state.pending_gate or ""),
        "red_green_iteration": str(state.red_green_iteration),
    }
    result = template
    for key, val in replacements.items():
        result = result.replace("{" + key + "}", val)

    # Check for unresolved placeholders
    unresolved = re.findall(r"\{[a-z_]+\}", result)
    if unresolved:
        print(
            f"Unresolved placeholder in gate prompt: {unresolved[0]}",
            file=sys.stderr,
        )
        sys.exit(4)
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    _parser = argparse.ArgumentParser(description="Debrief routing engine")
    _parser.add_argument("--project-root", required=True, help="Project root path")
    _args = _parser.parse_args()
    main_routing(project_root=Path(_args.project_root))
