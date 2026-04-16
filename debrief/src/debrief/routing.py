# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Carlo Fusco and Leonardo Restivo
"""Unit 4: Routing Protocol — GUTTED by BUG-AUDIT-31.

BUG-AUDIT-31 deleted all 13 public functions from this module. Every
function was dead at runtime — zero external callers in commands/,
hooks/, agents/, or bin/. The entire routing loop (main_routing →
main_update_state → main_prepare and all their helpers) was a
dead-code island from SVP Stage 5 onward. The consultant agent
handles all dispatch and state transitions via Tool calls, not
through this module.

Deleted functions: resolve_action, main_routing, check_g3_2_machine_gate,
validate_gate_response, perform_snapshot, handle_red_green_transition,
main_update_state, merge_approval_payload, promote_style_draft,
propose_presentation_folder_name, main_prepare, assemble_task_prompt,
substitute_gate_placeholders. Also deleted: _GATE_VALID_RESPONSES,
_GATE_RESPONSES, _SUB_PHASE_ACTION, _STYLE_CONFIG_REQUIRED_KEYS,
_STYLIST_ACTIONS, _EXPORT_ACTIONS, and all private helpers
(_handle_g21_style_revise, _handle_figure_selection, _write_qa_cycle_log,
_delete_snapshots_for_slug, _proposed_folder_section, _gate_prompt_section).

See spec/stakeholder_spec.md Bug Catalog entry BUG-AUDIT-31 for the
full rationale, the Prior-Art for Rebuild lessons, and references to
the original function contracts in the blueprint.

This module is kept as an empty shell (rather than deleted) to prevent
ImportError in any code that does `import routing` or
`from routing import ...` — those imports will fail with a specific
ImportError naming the deleted function, not a ModuleNotFoundError
for the entire module.
"""
