# Debrief Blueprint v3 — Prose (Tier 1)

**Date:** 2026-04-11
**Spec:** Debrief Stakeholder Specification v1.1
**Blueprint version:** 3.0

---

## Overview

Debrief is a Claude Code plugin that turns a domain expert's narrative intent into a professionally styled, QA-verified PDF slide deck without requiring the user to write any HTML, CSS, or JavaScript. The plugin coordinates five specialized Claude sub-agents (Consultant, Stylist, Slide Maker, Visual QA, Bug Diagnostic), a deterministic routing engine, a family of Python utility modules, and a set of user-invocable skills into a four-phase pipeline: Discovery → Style Definition → Slide Production → Finalization.

The implementation is decomposed into twelve units in strict bottom-up dependency order. Each unit has a single, bounded responsibility. No unit has a circular dependency on another.

---

## Unit 1: Plugin Scaffold

### Tier 1 — Description

The Plugin Scaffold is the set of static artifacts committed to the plugin repository that Claude Code reads to discover, install, and configure Debrief. It includes every file that exists before the first Python process runs and every file that is read by Claude Code's plugin machinery (manifest, settings) or by the `bin/debrief` launcher before project initialization.

**Scope of this unit:**

- `.claude-plugin/plugin.json` — the Claude Code plugin manifest. Declares the plugin name (`debrief`), version (`1.1.0`), description, authors, license (Apache-2.0), and three discovery pointers: `skills`, `agents`, `hooks`.
- `skills/<name>/SKILL.md` — the nine skill files (one per subdirectory: `slide`, `style`, `export`, `save`, `view`, `reset`, `quit`, `script`, `handout`). Each file begins with a YAML frontmatter block (per spec §5.1/§5.2) followed by the skill instruction body. Claude Code requires the frontmatter to register the skill as a user-invocable slash command — a SKILL.md that begins with anything other than `---` is silently dropped from skill discovery and the corresponding `/debrief:<name>` command will not appear. See BC-1.2 and BC-1.2a.
- `agents/<name>.md` — the five agent files (`consultant.md`, `slide-maker.md`, `visual-qa.md`, `bug-diagnostic.md`, `stylist.md`). Each file begins with a YAML frontmatter block (per spec §6.1/§6.2) followed by the agent system prompt body. The frontmatter declares `name`, `description`, `model`, `maxTurns`, and `tools`; absent or malformed frontmatter causes Claude Code to silently drop these declared constraints. See BC-1.3 and BC-1.3a.
- `settings.json` — sets the default agent to `consultant` so Claude Code opens the Consultant when the user starts a session.
- `environment.yml` — the conda environment specification pinning Python 3.11, playwright, python-pptx, PyMuPDF, json-repair, libreoffice-still, jq, and pip. This is the single source of truth for all managed dependencies.
- `templates/project_claude.md` — the template that the Launcher renders into each new project directory as `CLAUDE.md`. It contains the orchestrator's six-step cycle instructions, the routing command invocation, and all prohibitions against improvising pipeline flow (REQ-ROUTE-5). Owned by the scaffold, not by any agent.
- `hooks/hooks.json` — declares both hooks: a PreToolUse `command` hook targeting `bin/check-write-auth` on Write|Edit tool calls (10-second timeout), and a PostToolUse `agent` hook with an inline QA prompt on Write|Edit (60-second timeout).
- `archetypes.json` — maps each of the eight archetype values to their defaults (presentation_type, time_default, content_signal_defaults, rhetorical_emphasis, expected_deliverables, key_defaults_text). All eight archetypes from Section 14.1.1 must appear as top-level keys.
- `assets/vendor/` — bundled client-side libraries: `mermaid.min.js`, `rough.min.js`, `katex.min.js`, `katex.min.css`, the `katex-fonts/` directory of woff2 files, and `VERSIONS.md` recording the exact version, source URL, and SHA-256 hash of each bundled file.
- `references/` — seven bundled reference markdown files: `paperbanana-diagram-style-distilled.md`, `paperbanana-plot-style-distilled.md`, `paperbanana-derivation-meta-prompt.md`, `slide-qa-checklist.md`, `ai4vis-survey-distilled.md`, `preview_placeholder_content.md`, and `VERSIONS.md`. These are read-only inputs to agents and preparation scripts; no runtime code writes to them.
- `.mcp.json` — empty MCP server configuration (no MCP servers in v1.1).
- `bin/check-write-auth` — the PreToolUse hook script (bash). Reads the Claude Code tool-invocation JSON from stdin via `jq`, extracts `tool_input.file_path`, and enforces the write-time style-lock invariant. Deny exit code is 2 (Claude Code's "block the write and show stderr to LLM" signal). See Section 24.3 for the full contract.
- `LICENSE` — Apache 2.0 full text.
- `NOTICE` — PaperBanana attribution, patent risk disclosure per Section 25.
- `README.md` — user-facing guide with sections: Installation, First Run, Quick Start, Troubleshooting, Uninstallation, Dependencies, Acknowledgments. Content follows Section 24.37. The README explicitly states that the user does NOT run `conda env create`, `conda activate`, or `pip install` manually.
- `CHANGELOG.md` — Keep a Changelog format, starting at v1.1.0.

**`bin/check-write-auth` logic:**

1. Read stdin as JSON with `jq -r '.tool_input.file_path'`. If parsing fails, exit 2 with error "Unable to parse tool invocation".
2. Resolve the target path to an absolute path relative to `$PWD` (the project directory). If the path escapes the project directory, exit 2: `ERROR: Write outside project directory is not permitted.`
3. If the target path is under `slides/` or equals `assets/style.css`, read `deck_state.json` from `$PWD`. If `style_locked` is `false` or absent or the file does not exist, exit 2: `ERROR: Style config not yet locked. Run /debrief:style first.`
4. Otherwise, exit 0.

**`jq` availability note:** `jq` is listed in `environment.yml` and is therefore always available inside the activated `debrief` conda env. The hook fires only after the launcher has activated the env.

**`VERSIONS.md` in `assets/vendor/`:** Each entry follows the format:
```
<filename>    version <ver>   sha256:<hash>   <source_url>
```

**`VERSIONS.md` in `references/`:** Records the PaperBanana source commit hash, distillation date, and AI4VIS paper version per file.

This unit has no Python code. It is the static foundation on which all other units build.

**Distribution wrapper note.** Unit 1's artifacts are committed to the plugin subdirectory `debrief/` inside the distribution repository (see spec Section 2.1), NOT to the repository root. The repository root holds only `.claude-plugin/marketplace.json` (the catalog that points at `./debrief`), `README.md` for GitHub visitors, and git metadata. Unit 1 does not own the marketplace catalog — it is a distribution-time artifact authored once by the repository maintainer, not generated by any unit. When Claude Code installs the plugin, the installer copies the `debrief/` subdirectory into the plugin cache, so every `${CLAUDE_PLUGIN_ROOT}` path referenced in this unit resolves inside that copied subtree exactly as Section 2 describes.

---

## Unit 2: State Management Library

### Tier 1 — Description

The State Management Library is a pair of Python modules — `debrief.deck_state` and `debrief.debrief_state` — that own every read, write, and validation operation on the two project state files: `deck_state.json` and `debrief_state.json`. All other units that need to touch these files call into this library; no unit reads or writes them directly with `open()`.

**`debrief.deck_state`** manages `deck_state.json` — the deck content state. It provides:

- `read_deck_state(project_root)` — reads and validates `deck_state.json`. Returns a `DeckState` dataclass. Uses `json_repair` as a safety net for LLM-generated JSON. Raises `StateCorruptError` if repair also fails or if required top-level fields are missing.
- `write_deck_state(project_root, state)` — atomic write via write-to-tmp then `os.rename()`. No file lock (deck_state writers are never concurrent in the single-session model).
- `get_approved_slides(state, backup=None)` — returns slides whose `status` is `approved`, optionally filtered by the `backup` boolean field. Preserves the order of entries in the `slides` array.
- `get_slide_by_slug(state, slug)` — returns the slide record for the given slug, or `None` if absent or discarded.
- `increment_export_count(state, folder)`, `increment_script_count(state, folder)`, `increment_handout_count(state, folder)` — find the matching presentation record by folder name and increment the counter in-place.

**`debrief.debrief_state`** manages `debrief_state.json` — the pipeline control state. It provides:

- `read_debrief_state(project_root)` — reads and validates `debrief_state.json`. Performs SHA-256 hash verification per REQ-ROUTE-8: if the stored `state_hash` does not match a freshly computed hash of all content fields (excluding `state_hash` itself), the library checks whether the JSON is structurally valid and all field values are within expected ranges. If they are, it recomputes and updates the hash and emits a warning to stderr. If the content is malformed or any field holds an invalid value, it raises `StateCorruptError`.
- `write_debrief_state(project_root, state)` — atomic write using the write-to-tmp then rename protocol. Acquires an exclusive `fcntl.flock` on `.debrief/state.lock` before the read-modify-write sequence. Releases the lock after the rename. Recomputes `state_hash` before writing.
- `compute_state_hash(state_dict)` — computes SHA-256 over the canonical JSON serialization of all content fields in `debrief_state.json` excluding `state_hash`.
- `validate_debrief_state(state_dict)` — validates that all required fields are present, that enum fields hold only allowed values (e.g., `phase` in `{"discovery","style","production","finalization","complete"}`), and that numeric counters are non-negative.

**Shared utilities:**

- `StateCorruptError` — exception raised on unrecoverable state file errors.
- `atomic_write_json(path, data)` — writes data to `<path>.tmp`, fsyncs, renames to `path`. Used by both state modules and by Phase 2 draft-file writers.
- All modules in the library check for `json_repair` availability via `importlib.util.find_spec` at entry and exit with code 2 + the Section 9.3.1 standardized message if the package is absent.

**Why this unit exists first:** Every other unit that touches state files calls into this library. The Launcher (Unit 3) uses it to write the initial `deck_state.json` and `debrief_state.json` with atomic rename, schema validation, and hash computation. Routing (Unit 4) uses it for every read and hash-repair operation. Implementing the Launcher before this library would require duplicating atomic-write and hash logic, which is precisely what this library centralizes.

### Preferences

No user-specific preferences captured for this unit.

---

## Unit 3: Launcher

### Tier 1 — Description

The Launcher is the entry point for all Debrief operations. It comprises two parts that run in strict sequence: the `bin/debrief` bash wrapper (executes before any Python process exists) and `debrief.launcher` (the Python half, invoked after the conda env is activated). See spec Section 2.1 for the distribution-repo wrapper: `bin/debrief` lives at `debrief/bin/debrief` inside the repo before installation, and at `${CLAUDE_PLUGIN_ROOT}/bin/debrief` after. The self-relative path resolution in the bash wrapper (`dirname "$0"/..`) correctly resolves `CLAUDE_PLUGIN_ROOT` in both locations.

**`bin/debrief` bash wrapper responsibilities (steps 1–10 of Section 24.4):**

1. Conda availability: `command -v conda`. Missing conda → error + install link + exit 1.
2. Source conda: `source "$(conda info --base)/etc/profile.d/conda.sh"` to enable `conda activate`.
3. Env existence: `conda env list | awk '{print $1}' | grep -qx debrief`. If absent, proceed to creation.
4. Env creation: `conda env create -f "${CLAUDE_PLUGIN_ROOT}/environment.yml" -n debrief`. On failure, run `conda env remove -n debrief -y` before exit 1.
5. Env activation: `conda activate debrief`.
6. Post-activation smoke test: `python -c 'import playwright; import pptx; import fitz; import json_repair'`. On failure, emit the standardized env-corruption error (Section 9.3.1) and exit 2.
7. Package install marker: check `${HOME}/.cache/debrief/pkg_version_<version>.marker`. If absent, run `pip install -e "${CLAUDE_PLUGIN_ROOT}"`. Write marker only on exit code 0.
8. Chromium install marker: check `${CONDA_PREFIX}/.debrief_chromium_installed`. If absent, run `python -m playwright install chromium`. Write marker only on exit code 0.
9. Vendor hash verification: `python -m debrief.launcher preflight`. On hash mismatch, exit 1 with the file name, expected hash, actual hash, and the mandatory plugin-reinstall recovery instruction.
10. Subcommand dispatch: `new` → `python -m debrief.launcher new` then launch Claude Code; `--rebuild-env` → rebuild branch; bare → check for `deck_state.json`, launch Claude Code if present.

**`--rebuild-env` branch:** deletes `${HOME}/.cache/debrief/pkg_version_*.marker` files, runs `conda env remove -n debrief -y`, then re-executes the script from step 3 with a `REBUILD_DONE=1` guard to prevent infinite recursion.

**`debrief.launcher` Python module responsibilities:**

- `preflight()` — called by the bash wrapper via `python -m debrief.launcher preflight`. Runs `verify_vendor_hashes()`, which reads `${CLAUDE_PLUGIN_ROOT}/assets/vendor/VERSIONS.md`, parses each SHA-256 entry, and computes the actual hash of each listed file. A mismatch exits 1 with the full error message from Section 24.27.
- `new(project_root)` — called by the bash wrapper via `python -m debrief.launcher new`.
  1. Checks that `project_root` is empty or contains only `CLAUDE.md`. If other files exist, prints an error and exits 1.
  2. Presents the archetype selection prompt (REQ-INIT-7). Accepts a number 1–8 or the archetype name. Accepts `--archetype <value>` from argv to skip the interactive prompt.
  3. Creates the project directory structure per Section 3: `assets/images/`, `assets/fonts/`, `assets/vendor/`, `assets/reference/slides/`, `assets/reference/papers/`, `assets/math/`, `.debrief/briefs/`, `.debrief/snapshots/`, `slides/`, `output/screenshots/`. Copies the vendor assets from `${CLAUDE_PLUGIN_ROOT}/assets/vendor/` into `assets/vendor/`.
  4. Writes initial `deck_state.json` via `write_deck_state()` (Unit 2). Initial values per REQ-INIT-2.
  5. Writes initial `debrief_state.json` via `write_debrief_state()` (Unit 2). Initial values per REQ-INIT-6.
  6. Renders `${CLAUDE_PLUGIN_ROOT}/templates/project_claude.md` into `CLAUDE.md` by substituting the `{project_name}` placeholder with the directory name. Writes atomically.

**Archetype selection prompt format (REQ-INIT-7):**
```
Welcome to Debrief. What are you preparing?

  1. Lab meeting talk
  2. Conference presentation
  3. Seminar
  4. Lecture
  5. Journal club
  6. Grant panel / interview
  7. Job talk
  8. Custom (start from scratch)

Enter a number or archetype name:
```

Invalid input re-prompts once; a second invalid input exits with a message and exit code 1.

**What this unit does NOT do:** The launcher does not invoke any Python agent, does not write to `debrief_state.json` except during init, and does not start any Playwright session.

### Preferences

No user-specific preferences captured for this unit.

---

## Unit 4: Routing Protocol

### Tier 1 — Description

The Routing Protocol comprises three tightly coupled Python modules — `debrief.routing`, `debrief.update_state`, and `debrief.prepare` — that together implement the deterministic six-step action cycle described in Section 22.7. These three modules are the only components that may advance pipeline state. No agent, skill, or hook drives its own state transitions.

**`debrief.routing`** — reads `debrief_state.json` and outputs a structured ActionBlock JSON to stdout. It is a pure function of current state: given the same state, it always emits the same action block. Routing has no side effects. Its logic implements the Sub-Phase Transition Table from Section 14.17 as an explicit state machine: a match on `(phase, sub_phase, pending_gate, condition_flags)` selects which action block to emit. Condition flags read from state include `backup_mode`, `closing_slide_pending`, `group_revise_slug`, `pre_view_state`, `view_deferred`, `reference_provided`, `papers_provided`, `red_green_iteration`, and the latest `qa_log.jsonl` entry for `current_slide_slug` (for the G3.2 machine gate check). The routing script also reads `archetypes.json` when assembling Consultant context.

The routing script handles the G3.2 machine gate (red-green) by reading the latest `qa_log.jsonl` entry for `current_slide_slug` whose timestamp is >= `red_green_started_at`. If `passed: true`, it emits GREEN. If `passed: false` and `red_green_iteration < 5`, it emits RED. If `red_green_iteration >= 5`, it emits EXHAUSTED.

The routing script detects oscillation (same failure count, different failure invariant IDs) by comparing the two most recent `qa_log.jsonl` entries for the current slug. On oscillation, it emits a `human_gate` action block for G3.2a.

The `ActionBlock` schema (Section 24.15) is strictly followed: `action_type`, `agent`, `gate_id`, `valid_responses`, `gate_prompt`, `context_files`, `task_prompt_file`, `prepare`, `post`, `reminder`. The `prepare` and `post` fields are complete shell command strings, not bare identifiers. The `agent` field in `invoke_agent` actions uses the routing-target enum which includes `diagnostic` (distinct from the `active_agent` field in `debrief_state.json`).

**`debrief.update_state`** — CLI `python -m debrief.update_state --gate <gate_id> --response <response_text> --project-root <path>`. Validates the response against the gate's `valid_responses` list or grammar. Exits with code 4 and the message `Invalid response. Expected: <grammar>` on mismatch. For parameterized gates, parses the response according to the grammar in REQ-ROUTE-7 and extracts payload. Writes state transitions to `debrief_state.json` and `deck_state.json` via the Unit 2 library. Also invoked with `--skill-prelude <skill_name> --field <name>=<value>` by Yield-mode skills to write the pre-yield state fields listed in Section 24.19.

`update_state` manages the following responsibilities explicitly:

- **Red-green iteration:** increments `red_green_iteration`, sets `red_green_started_at` on first iteration, reads snapshots, performs regression detection (per REQ-SLIDE-14), reverts `slides/<slug>.html` to best-known-good if regression is detected. Writes `qa_cycle_log.jsonl` at the end of each completed red-green cycle (per REQ-SLIDE-12). `qa_cycle_log.jsonl` writer: `update_state` only.
- **Snapshot management:** before each rewrite iteration, copies current `slides/<slug>.html` to `.debrief/snapshots/<slug>_iter_<N>.html`. Cleans up snapshots per REQ-SLIDE-13 at cycle exit.
- **Approval payload merging:** on G3.3 `SLIDE APPROVED`, reads `.debrief/approval_<slug>.json`, validates required fields, merges into the slide record in `deck_state.json`, deletes the approval file.
- **Group cleanup:** on G3.4 `GROUP APPROVED`, atomically deletes `.debrief/briefs/<group_id>_MANIFEST.json` and all `.debrief/briefs/<group_id>_*.json` brief files. Also sweeps any remaining `.debrief/approval_<slug>.json` for slides in the completed group.
- **Diagnostic file lifecycle:** deletes `.debrief/diagnostic_<slug>.md` on every exit from `G3.3_slide_review_post_diagnostic` (both SLIDE APPROVED sub-branches and SLIDE REVISE). A second EXHAUSTED for the same slug overwrites the diagnostic file.
- **Phase 2 lifecycle:** implements the Section 24.8 compile-and-lock sequence on G2.1 `STYLE APPROVED` (precondition validation → atomic rename → compile → chmod 444 → `style_locked: true` → remove `.debrief/draft/`). On `STYLE REVISE`, removes `.debrief/draft/` recursively. On `REGENERATE PREVIEWS`, removes only `.debrief/draft/preview_slides/` and `.debrief/draft/preview_images/`, writes `.debrief/gate_data.json` with `{"regenerate_previews": true}`, leaves style files intact.
- **G1.3 figure selection:** writes `selected_figures` directly to `debrief_state.json` as a durable field (NOT to `gate_data.json`), per P-BP-13.
- **gate_data.json lifecycle:** same-invocation consumers (G3.4, G3.V) are read and deleted in the same `update_state` invocation. Cross-cycle consumers (G2.1 `STYLE REVISE`, G2.1 `REGENERATE PREVIEWS`, G3.3 post-diagnostic `SLIDE REVISE`) write the file and leave it for the next prepare cycle. The prepare cycle validates `gate_id`, injects the `data` payload, and deletes the file.
- **Discard cleanup:** on slide discard, atomically deletes `slides/<slug>.html`, `output/screenshots/<slug>.png`, `.debrief/approval_<slug>.json`, and `.debrief/diagnostic_<slug>.md` for that slug.

**`debrief.prepare`** — CLI `python -m debrief.prepare --action <gate_or_state_id> --project-root <path>`. Assembles `.debrief/task_prompt.md` from the context files specified for the current action. Context rules follow Section 22.8 (per-agent) and Section 22.8.1 (per-gate). The task prompt is a markdown document with `## Context: <filename>` sections. For QA revision context, the prepare module extracts the latest `qa_log.jsonl` entry and embeds it under `## QA Result`. For agent invocations, `rhetorical_role` is always included from the slide brief when the Slide Maker is the target.

**Cross-cycle gate_data consumption rule (Section 24.20):** At every invocation, `prepare` checks for `.debrief/gate_data.json`. If present AND its `gate_id` matches the gate whose response caused the current `sub_phase` transition, the `data` object is injected under a `## Gate Data` section and the file is deleted. If `gate_id` mismatches, `prepare` exits with code 4 (state corruption).

**Gate prompts:** The prepare script implements all gate prompt templates from Section 14.16.1. All `{placeholder}` values are substituted before the ActionBlock reaches the orchestrator. The `gate_prompt_text` distinguishes between `{name}` (substituted) and `<literal>` (user-input indicator, not substituted). No unresolved `{}` placeholders are emitted.

**Bundled reference globbing (Section 24.39 growth model):** The prepare script, when assembling the Stylist context, globs `${CLAUDE_PLUGIN_ROOT}/references/reference-*.md` in alphabetical order and appends any matches to the context list. In v1.1 this glob is empty; in future releases new reference files matching this pattern are picked up automatically without a version bump.

**Archetype context loading:** When assembling the Consultant discovery context, `prepare` reads `${CLAUDE_PLUGIN_ROOT}/archetypes.json` and injects the matching archetype defaults under a `## Archetype Defaults` section.

### Preferences

No user-specific preferences captured for this unit.

---

## Unit 5: Consultant Agent and Ledger

### Tier 1 — Description

The Consultant Agent is the primary user-facing conversational agent throughout the pipeline. It appears in Phase 1 (discovery dialog, brief production, paper/reference processing), Phase 3 (group planning, escalation handling), and Phase 4 (backup slide planning). Its system prompt is defined in `agents/consultant.md` and its conversation record lives in `ledger.jsonl`.

**Consultant agent system prompt (`agents/consultant.md`):**

The system prompt instructs the Consultant to:

- Read its full context from the assembled task prompt at `.debrief/task_prompt.md` at session start.
- Conduct the Socratic discovery dialog per REQ-CONSULT-1. When an archetype other than `custom` is selected, greet with the archetype context pre-loaded and focus the dialog on confirmation and refinement, not re-asking already-answered questions.
- Apply progressive disclosure per REQ-CONSULT-7: ask only trigger-conditioned follow-up questions. Never present a checklist of all content types unprompted.
- Structure the narrative arc using rhetorical devices per REQ-CONSULT-15. Every slide brief MUST include a `rhetorical_role` field.
- Produce and maintain `deck_brief.md` following the template in Section 24.23. The Content Signals section must parse correctly against the `^- (?P<key>[a-z_]+): (?P<value>.+)$` regex.
- Record every turn in `ledger.jsonl`. Each entry: `{"timestamp": "ISO8601", "role": "user|consultant|system", "content": "string", "metadata": {"group_id": null, "slug": null, "event": null}}`.
- Handle ledger compaction: when the ledger exceeds 100 entries, summarize it into a single compaction entry capturing decisions made, slides approved, style choices locked, and narrative direction; archive the full ledger to `ledger_compact_<NNN>.jsonl`; write a new `ledger.jsonl` containing only the compaction summary entry.
- Dispatch slide briefs as structured JSON files to `.debrief/briefs/<group_id>_<slug>.json` and then write the manifest `.debrief/briefs/<group_id>_MANIFEST.json` atomically. The G3.1 machine gate fires only when the manifest exists and `slide_count` matches the brief files. Brief schema per REQ-CONSULT-5 includes: `slug`, `title`, `content_goal`, `visual_approach`, `visual_pattern`, `rhetorical_role`, `design_invariants`, `user_recommendations`, `group_id`. Group IDs use monotonically increasing labels (`group_01`, `group_02`, ...). Backup group IDs use `backup_01`, `backup_02`, ... with the `backup: true` flag set in briefs.
- NOT write directly to `deck_state.json` or `debrief_state.json`. The Consultant writes only `deck_brief.md`, `ledger.jsonl`, and `.debrief/briefs/` files.
- Announce the slug clearly before dispatching each brief (e.g., `Slug: pipeline`) so the user can reference it with `/debrief:slide [slug]`.
- Handle post-compaction context reconstruction from `deck_brief.md` + `deck_state.json` alone (NFR-USE-3).
- For journal club archetypes: ask for paper PDFs as the first question without waiting for a trigger (REQ-CONSULT-18).
- For lecture archetypes: proactively mention the handout option during discovery.
- Invoke `debrief.style_analyzer` via Bash when the user provides a reference file path during discovery (REQ-CONSULT-13). The Consultant does NOT wait for the analyzer to call a VLM; `debrief.style_analyzer` only produces the image batch and (for PPTX) metadata. The actual VLM derivation happens on the next routing cycle when the Stylist is invoked.
- Invoke `debrief.paper_analyzer` via Bash when the user provides academic paper PDFs (REQ-CONSULT-17). Each invocation produces `.debrief/paper_analysis_<paper_slug>.md` and copies figures to `assets/reference/papers/<paper_slug>/figures/`.
- NOT invoke other agents via the Agent tool. All agent handoffs go through the routing cycle.

**Ledger compaction trigger:** 100 entries. This threshold is chosen to keep the Consultant's effective context manageable while ensuring enough history is retained for context reconstruction without compaction.

**`/debrief:slide` skill SKILL.md (discovery trigger):**

`skills/slide/SKILL.md` is classified here because the slide skill's primary role in Phase 3 is to serve as the entry point for the group cycle. The skill's frontmatter declares `allowed-tools: Read, Write, Edit, Bash`. Its instruction body covers:

1. Precondition checks: if `style_locked` is `false`, print `Style must be locked before creating slides. Run /debrief:style first.` and exit. If a slug is provided and no non-discarded slide with that slug exists in `deck_state.json`, print an error listing valid slugs and exit.
2. If a valid slug is provided: write `current_slide_slug: <slug>` via `python -m debrief.update_state --skill-prelude slide --field current_slide_slug=<slug>`, then yield to routing.
3. If no slug: write `current_slide_slug: null` via `update_state --skill-prelude slide`, then yield to routing. The next routing cycle sees `production/group_planning` and invokes the Consultant to produce the next brief.
4. The skill MUST NOT poll `qa_log.jsonl` or loop on red-green iterations.
5. Yield protocol per Section 24.19: validate → write state fields → print one-line acknowledgment → run `python -m debrief.routing --project-root .` → execute the action block.

### Preferences

No user-specific preferences captured for this unit.

---

## Unit 6: Style Compiler

### Tier 1 — Description

The Style Compiler is the Python module `debrief.style_compiler`. It is a pure read-transform-write function: given a `style_config.json` file, it generates `assets/style.css` containing CSS custom properties for every visual property in the config. No state files are read or written. No Playwright is used.

**Invocation:**
```
python -m debrief.style_compiler <style_config_path> <output_css_path>
```
The two positional arguments are the exception to the `--project-root` convention, preserved for backward compatibility with the signature in Section 24.14.

**Input: `style_config.json`**

The config must be valid JSON. Required top-level keys include: `colors`, `typography`, `spacing`, `layout`, `data_viz`, `constraints`, `provenance`. Missing required keys exit with code 1 and a descriptive stderr message.

**Strict CSS custom-property name mapping:**

The following table is canonical and pinned. The Slide Maker reads these variable names from `style_guide.md` and uses them in generated HTML. Drift between this mapping and what `style_guide.md` documents is a bug.

| `style_config.json` path | CSS custom property |
|--------------------------|---------------------|
| `colors.primary` | `--color-primary` |
| `colors.secondary` | `--color-secondary` |
| `colors.accent` | `--color-accent` |
| `colors.background` | `--color-background` |
| `colors.text_primary` | `--color-text-primary` |
| `colors.text_secondary` | `--color-text-secondary` |
| `colors.code_background` | `--color-code-background` |
| `colors.border` | `--color-border` |
| `typography.heading_font_family` | `--font-heading-family` |
| `typography.body_font_family` | `--font-body-family` |
| `typography.code_font_family` | `--font-code-family` |
| `typography.heading_size_base` | `--font-heading-size-base` |
| `typography.body_size_base` | `--font-body-size-base` |
| `typography.heading_weight` | `--font-heading-weight` |
| `typography.body_weight` | `--font-body-weight` |
| `typography.line_height` | `--font-line-height` |
| `spacing.margin_pct` | `--spacing-margin-pct` |
| `spacing.gap` | `--spacing-gap` |
| `spacing.section_gap` | `--spacing-section-gap` |
| `layout.slide_width` | `--layout-slide-width` |
| `layout.slide_height` | `--layout-slide-height` |
| `layout.column_gap` | `--layout-column-gap` |
| `data_viz.primary_colormap` | `--viz-primary-colormap` |
| `data_viz.axis_color` | `--viz-axis-color` |
| `data_viz.grid_color` | `--viz-grid-color` |
| `data_viz.annotation_color` | `--viz-annotation-color` |

All custom properties are emitted inside a `:root { ... }` block. Fields not in the table are emitted using a fallback convention: dot-separated JSON path → `--<segment1>-<segment2>-...` with underscores converted to hyphens.

**Exit codes:** 0 on success, 1 on error (invalid JSON, missing required fields, file I/O failure). Exit code 3 on usage error (wrong number of positional arguments). No exit code 2 (the style compiler has no conda-env dependency beyond stdlib).

**What this unit does NOT do:** The compiler does not read `debrief_state.json`, does not invoke Playwright, and does not generate the `style_guide.md`. The style guide is authored by the Stylist agent (Unit 7).

### Preferences

No user-specific preferences captured for this unit.

---

## Unit 7: Style Dialog

### Tier 1 — Description

The Style Dialog unit implements Phase 2: the interactive co-design of the visual style for the deck. It comprises:

- `agents/stylist.md` — the Stylist agent system prompt.
- `skills/style/SKILL.md` — the `/debrief:style` skill (Yield-mode entry point with precondition checks).
- `debrief.style_guide_generator` — text-synthesis utility (no Playwright) that synthesizes a first-draft `style_guide.md` from layered inputs.
- `debrief.preview_renderer` — thin Playwright wrapper that renders preview HTML files to 1920×1080 PNGs.
- `debrief.style_analyzer` — reference modality adapters that convert a user-provided reference file into a standardized PNG image batch and (for PPTX) structured metadata. The analyzer does NOT call a VLM.

**`/debrief:style` skill preconditions (REQ-STYLE-1):**

1. If `deck_brief.md` does not exist or is empty: print `The consultant must produce the deck brief before defining the style. Continue the discovery dialog first.` Exit.
2. If `style_locked` is `true` in `deck_state.json`: print `Style is already locked. To change the style, run /debrief:reset to start a new project.` Exit.
3. If preconditions pass, yield to routing per Section 24.19 Yield protocol.

**Stylist agent system prompt (`agents/stylist.md`):**

The Stylist's system prompt instructs it to:

- Read context in order per REQ-STYLE-2: (1) `deck_brief.md`, (2) the bundled reference documentation at `${CLAUDE_PLUGIN_ROOT}/references/`, (3) if `reference_provided=true` in its task prompt AND `.debrief/draft/derived_style_guide.md` does not yet exist: enter reference-derivation mode — read every image in `assets/reference/slides/*.png` (and `.debrief/draft/analyzer_metadata.json` if the PPTX modality), apply the anti-prescriptive meta-prompt from `paperbanana-derivation-meta-prompt.md`, and write `.debrief/draft/derived_style_guide.md` per the REQ-STYLE-7 11-section schema, (4) if `style_import_mode` is `baseline` or `inspiration`, read `.debrief/draft/derived_style_guide.md`.
- Conduct the style dialog covering all fields in REQ-STYLE-3: primary/accent colors, font families, base font size, line height, slide background, layout grammar, permitted diagram libraries, spacing scale. The selected permitted libraries are stored in `style_config.json.constraints.permitted_diagram_types`.
- Apply the precedence rules in REQ-STYLE-7 when layering sources. Surface conflicts per the conflict-disclosure scripted question template when a reference-derived value conflicts with a bundled-reference veto rule.
- Under `baseline` mode: pre-fill proposed values from the derived draft. Under `inspiration` mode: cite the derived draft but do NOT pre-fill values. Under no-reference or `IGNORE` mode: proceed with bundled references as the only craft-knowledge input.
- Write `style_guide.md` (the project-specific synthesis) to `.debrief/draft/style_guide.md` in the REQ-STYLE-7 11-section format: Color rationale, Typography rationale, Layout grammar, Diagram conventions, Visual patterns catalog, Anti-patterns, Image Placement, Math Rendering, Presentation Type Guidance, Symmetry and Visual Balance, Rhetorical Role Styling. Use anti-prescriptive language throughout (REQ-STYLE-8).
- Write `style_config.json` (with the `provenance` object per Section 24.16) to `.debrief/draft/style_config.json`.
- Invoke the style compiler on the draft config: `python -m debrief.style_compiler .debrief/draft/style_config.json .debrief/draft/preview_style.css`.
- Invoke `debrief.style_guide_generator` (optionally) to produce a first-draft `style_guide.md` as a starting point.
- Generate 3 preview slides in `.debrief/draft/preview_slides/` using placeholder content from `${CLAUDE_PLUGIN_ROOT}/references/preview_placeholder_content.md` keyed by archetype (REQ-STYLE-10).
- Invoke `python -m debrief.preview_renderer --project-root . --input-dir .debrief/draft/preview_slides/ --output-dir .debrief/draft/preview_images/`.
- On `REGENERATE PREVIEWS` (signaled by `regenerate_previews: true` in `## Gate Data` from `.debrief/gate_data.json`): regenerate only the preview slides with different placeholder content; do not re-synthesize style values.
- NOT directly write to `debrief_state.json` or `deck_state.json`. The `update_state` script handles promotion and locking.

**`debrief.style_analyzer`** — CLI: `python -m debrief.style_analyzer --reference <path> --project-root <path>`. Dispatches to the correct modality adapter:

- PPTX adapter: LibreOffice headless (`soffice --headless --convert-to png --outdir <tmpdir> <input.pptx>` with `-env:UserInstallation=file:///<tmp-profile>` isolation). 120-second timeout. Cap at 10 slides (first + last + 8 middle). Also runs `python-pptx` to extract theme colors, font families, font sizes, slide dimensions; writes `.debrief/draft/analyzer_metadata.json`. Copies the reference file to `assets/reference/<filename>`. Writes PNGs to `assets/reference/slides/`.
- PDF adapter: PyMuPDF `fitz.Page.get_pixmap()` at 150 DPI. Cap at 10 pages. If PDF has > 50 pages, sets a heuristic flag that causes a paper-vs-deck warning in the G1.2 gate prompt. Copies reference file to `assets/reference/<filename>`. Writes PNGs to `assets/reference/slides/`.
- HTML single-file adapter: Playwright, `wait_until="networkidle"` + 2-second delay, 1920×1080 screenshot. One PNG. Copies reference file to `assets/reference/<filename>`. Writes PNG to `assets/reference/slides/`.
- HTML directory adapter: Playwright, one PNG per `.html` file, cap at 10 (alphabetical order: first + last + 8 middle). Same wait strategy. Copies reference directory to `assets/reference/<dirname>/`. Writes PNGs to `assets/reference/slides/`.

The analyzer does NOT call any VLM. VLM-based derivation of `.debrief/draft/derived_style_guide.md` is the Stylist agent's responsibility on the next routing cycle (P-BP-14).

Env corruption detection: if `soffice` is missing, exits 2 with the standardized env-corruption error. If `fitz` cannot be imported, exits 2. If `playwright` cannot be imported, exits 2. If `pptx` cannot be imported (for PPTX metadata), exits 2.

**`debrief.style_guide_generator`** — text-synthesis utility, no Playwright. CLI: `python -m debrief.style_guide_generator --project-root <path>`. Reads the bundled reference documentation, the draft `style_config.json` (if present), and the derived style guide (if present); synthesizes a first-draft `style_guide.md` at `.debrief/draft/style_guide.md` using anti-prescriptive language. The Stylist MAY invoke this module before customizing the draft further. No LLM calls, no subprocess spawning.

**`debrief.preview_renderer`** — thin Playwright wrapper. CLI: `python -m debrief.preview_renderer --project-root <path> --input-dir <dir> --output-dir <dir>`. Opens one `sync_playwright()` session per invocation, one `BrowserContext`, renders each `.html` file in the input directory to a 1920×1080 PNG in the output directory. Waits for KaTeX/Mermaid/rough.js to finish rendering before screenshot. Target: complete in < 30 seconds for 3 preview slides. If > 60 seconds, prints a timeout warning and exits with code 1. Closes the session before returning.

**`.debrief/draft/` lifecycle:** Created on first reference-import or Stylist write. Promoted on G2.1 STYLE APPROVED (atomic rename + compile + chmod + state update + rmtree of remaining draft contents). Discarded on STYLE REVISE (rmtree). Partially cleaned on REGENERATE PREVIEWS (only preview dirs removed). Retained on `/debrief:quit` mid-Phase-2. Deleted by `/debrief:reset`. See Section 24.40 for the canonical lifecycle.

### Preferences

No user-specific preferences captured for this unit.

---

## Unit 8: Slide Agent

### Tier 1 — Description

The Slide Agent unit implements Phase 3 slide generation. It comprises:

- `agents/slide-maker.md` — the Slide Maker agent system prompt.
- `debrief.asset_ingest` — user-provided image copy helper.
- `debrief.math_renderer` — KaTeX HTML wrapper generator.

The Slide Maker's generation path is entirely style-guide-driven (REQ-SLIDE-8). There is no exemplar library, no `exemplars/` directory, no `exemplar_index.json`, and no exemplar-availability branch. The single generation path reads `style_guide.md`, `style_config.json`, the slide brief, Content Signals, and the bundled reference documentation at `${CLAUDE_PLUGIN_ROOT}/references/`.

**Slide Maker agent system prompt (`agents/slide-maker.md`):**

The system prompt instructs the Slide Maker to:

- Read `style_guide.md` at the start of every generation or revision task. The style guide takes precedence over the agent's own aesthetic judgment.
- Generate `slides/<slug>.html` as a self-contained HTML5 file. All styles from `../assets/style.css`. No inline styles that override the locked config. Vendor scripts from `../assets/vendor/`.
- Read the full slide brief from the task prompt, including `rhetorical_role`. Apply rhetorical-role-specific visual treatment per the style guide's "Rhetorical Role Styling" section: hook slides use large typography + minimal text; pathos slides prioritize photographs/emotional imagery; logos slides prioritize data exhibits; ethos slides emphasize citations and methodology callouts.
- For slides N >= 2, MAY include the most recent 1-2 approved slides from `slides/` as in-deck few-shot context for visual consistency (non-normative, REQ-SLIDE-8).
- Write `.debrief/approval_<slug>.json` at the end of EVERY red-green iteration (not just GREEN), always reflecting the current best-known-good state. The approval payload schema per Section 24.24.
- Respect the silence rule (REQ-SLIDE-11): no intermediate status updates during the red-green cycle. Communicate with the user only when presenting the final result.
- NOT make narrative-arc decisions. If the user requests a structural change, the Slide Maker MUST output `ESCALATE_TO_CONSULTANT` rather than attempting the change itself.
- When invoking `debrief.math_renderer`: `python -m debrief.math_renderer --mode inline --input "<latex>"` or `--mode display`. If the renderer exits non-zero, report the LaTeX parse error to the user and wait for corrected input. Never write the slide HTML if the math renderer fails.
- When ingesting a user-provided image: `python -m debrief.asset_ingest --src <source_path> --slug <slug> --project-root <path>`. The slide HTML then references `../assets/images/<slug>_<filename>`.

**`debrief.asset_ingest`** — CLI: `python -m debrief.asset_ingest --src <path> --slug <slug> --project-root <path>`. Copies the source file to `<project_root>/assets/images/<slug>_<basename(source_path)>` atomically (write-to-tmp then rename). Does NOT modify `deck_state.json`. Exit 0 on success, exit 1 on source-not-found or copy failure, exit 3 on usage error.

**`debrief.math_renderer`** — CLI: `python -m debrief.math_renderer --mode <inline|display> --input <latex_string>`. Pure Python string formatter. Emits an HTML wrapper: for inline, `<span class="katex-src" data-mode="inline">{escaped_latex}</span>`; for display, `<div class="katex-src" data-mode="display">{escaped_latex}</div>`. An initialization `<script>` block in each slide HTML calls `katex.renderMathInElement()` on all `.katex-src` elements at browser load time. Performs surface well-formedness checks: bracket balance on `{}`, balanced `\begin{...}\end{...}` environments, non-empty input, no null bytes. Does NOT maintain an allowlist of KaTeX commands. Exits 0 on well-formed input, 1 on malformed input. No Playwright dependency.

**Snapshot management:** Before each rewrite iteration, `update_state` (not the Slide Maker) copies `slides/<slug>.html` to `.debrief/snapshots/<slug>_iter_<N>.html`. The Slide Maker does not manage snapshots directly.

**Approval payload:** Written by the Slide Maker via the Write tool to `.debrief/approval_<slug>.json`. Schema:
- `slug` (required), `title` (required), `content_summary` (required, max 500 chars), `visual_approach` (required), `design_choices` (required), `forks_not_taken` (optional), `user_recommendations` (optional), `accepted_violations` (optional array).

### Preferences

No user-specific preferences captured for this unit.

---

## Unit 9: QA System

### Tier 1 — Description

The QA System implements the automated visual quality assurance layer that runs after every slide write. It comprises:

- `agents/visual-qa.md` — the Visual QA agent system prompt.
- `agents/bug-diagnostic.md` — the Bug Diagnostic agent system prompt.
- `debrief.qa_checker` — programmatic Tier 1 invariant checker.

**QA architecture (Section 24.22):**

The QA agent (VLM-capable) and `qa_checker` have distinct, non-overlapping responsibilities:

- `qa_checker.py` (programmatic): INV-04 (contrast), INV-06 (no inline styles), INV-07 (no external requests), INV-08 (aspect ratio), INV-10 (permitted libraries — reads `style_config.json` at check time), INV-12 (valid HTML5), INV-13 (image overflow), INV-14 (math horizontal overflow), INV-15 (diagram render errors), INV-16 (font loading), INV-17 (CSS property completeness), INV-19 (image src existence), INV-20 (image aspect-ratio distortion ≤ 2%), INV-22 (inline math line-height break), INV-23 (math asset file existence), INV-24 (filename/slug consistency — BUG-AUDIT-69).
- QA agent (VLM): all VETO rules (VETO-01..VETO-07), INV-21 (rendered math visible — the one Tier 1 invariant assigned to VLM), and all Tier 2 invariants: INV-01, INV-02, INV-03, INV-05, INV-09, INV-11, INV-18, plus the 19 V-* rules from `slide-qa-checklist.md`.

**Pipeline order:** QA agent runs first (veto checks on screenshot). If any veto fires, the QA agent writes the veto failure and does NOT invoke `qa_checker.py`. If no veto, the QA agent invokes `qa_checker.py` which runs programmatic Tier 1 checks. After `qa_checker.py` returns, the QA agent runs VLM-based Tier 1 (INV-21) and all Tier 2 checks on the screenshot. The final `qa_log.jsonl` entry merges all results.

**Visual QA agent system prompt (`agents/visual-qa.md`):**

The system prompt instructs the QA agent to:

- Invoke `python -m debrief.qa_checker --slide-path <path> --screenshot-path output/screenshots/<slug>.png --project-root <path>` via Bash.
- Identify the file just written from the tool-use context. If NOT in `slides/`, skip and exit immediately.
- Read the screenshot and run VLM-based checks: all VETO rules (VETO-01..VETO-07), INV-21, Tier 2 invariants.
- For Tier 2 judgment, read `${CLAUDE_PLUGIN_ROOT}/references/slide-qa-checklist.md` as context and evaluate all 19 V-* rules.
- Merge `qa_checker.py` results with VLM-based results into a single `qa_log.jsonl` entry per REQ-QA-3 canonical schema.
- Write the result to `output/qa_log.jsonl` (append-only). MUST write before the hook returns (within the 60-second timeout).
- On Playwright screenshot failure: write a failure record with `"invariant": "SCREENSHOT"` per Section 24.3.
- NOT write to `qa_cycle_log.jsonl` (that is `update_state`'s responsibility per P-BP-1).

**`debrief.qa_checker`** — CLI: `python -m debrief.qa_checker --slide-path <path> --screenshot-path <path> --project-root <path>`. Opens its own `sync_playwright()` context per invocation (per Section 24.10.2). Renders the slide HTML, takes the screenshot, saves to `output/screenshots/<slug>.png`, runs all programmatic invariant checks in tiered order, outputs JSON result to stdout. Checks INV-04 via the WCAG contrast ratio formula applied to computed background/foreground colors. Checks INV-10 by reading `style_config.json.constraints.permitted_diagram_types`. Checks INV-13, INV-14, INV-20, INV-22 using Playwright's `bounding_box()` API on rendered DOM elements. Exits 0 (result on stdout), 1 (generic failure), 2 (env corruption), 3 (usage error).

**Preview slides are exempt from QA:** The PostToolUse hook fires on writes to `slides/` only. Writes to `.debrief/draft/preview_slides/` are exempt.

**Bug Diagnostic agent system prompt (`agents/bug-diagnostic.md`):**

The system prompt instructs the Bug Diagnostic agent to:

- Read `qa_log.jsonl` (all entries for the current slug since `red_green_started_at`), `output/qa_cycle_log.jsonl`, and the current `slides/<slug>.html`.
- Produce `.debrief/diagnostic_<slug>.md` with sections: `## Summary`, `## Failure Pattern`, `## Root Cause Hypothesis`, `## Suggested Fix`.
- NOT invoke other agents. NOT write to any state file. The `post` step's `update_state` invocation handles the transition to `production/slide_review` with `pending_gate: G3.3_slide_review_post_diagnostic`.

**`qa_log.jsonl` canonical schema (REQ-QA-3):**
```json
{
  "slug": "<string>",
  "timestamp": "<ISO8601>",
  "passed": <bool>,
  "veto": <bool>,
  "checks_run": ["<invariant_id>"],
  "failures": [{"invariant": "<id>", "description": "<text>", "revision_instruction": "<text>"}],
  "warnings": [{"invariant": "<id>", "description": "<text>", "revision_instruction": "<text>"}],
  "revision_instructions": ["<string>"]
}
```

### Preferences

No user-specific preferences captured for this unit.

---

## Unit 10: Export Module

### Tier 1 — Description

The Export Module renders the complete deck to a versioned PDF using a single Playwright `BrowserContext`. It comprises:

- `debrief.export` — the Playwright-based PDF renderer.
- `skills/export/SKILL.md` — the `/debrief:export` skill (Yield-mode with precondition checks).

**`/debrief:export` skill preconditions (REQ-EXPORT-6):**

1. If `style_locked` is `false`: print `Cannot export: style is not locked. Complete the style dialog first.` Exit.
2. If no slides have `status: "approved"`: print `Cannot export: no approved slides. Approve at least one slide before exporting.` Exit.
3. If draft slides exist (status `draft` or `needs_revision`): print the warning listing their slugs and ask `Continue anyway? (yes/no)`. Only `yes` proceeds; anything else cancels.
4. If preconditions pass: yield to routing (transitions to `finalization/export_options`).

**Export ordering dialog (Section 24.10):**

This dialog is conducted by the skill/Consultant before G4.4 `EXPORT NOW` fires. It covers:

1. Current slide order confirmation.
2. Separator position: "Where does the formal presentation end?" Maps 1-based user count to 0-based `separator_position`. If no separator needed, `separator_position: null`.
3. Separator content: acknowledgments, "Questions?", summary, or custom. Stored as `separator_content`.
4. Presentation folder name: proposed as `<YYYY_MM_DD>_<shortened_title>`. User confirms or overrides.

If the folder already exists in `output/`, the export appends into it (version counter increments). If the user cancels at any point, no state changes.

After the dialog, the skill creates `output/<folder>/`, adds or updates the `presentations` array entry in `deck_state.json` (including `slide_manifest` snapshot), and yields to routing for G4.4.

**`debrief.export` module:**

CLI: `python -m debrief.export --project-root <path>`. 

1. Invokes `python -m debrief.style_compiler style_config.json assets/style.css` before Playwright to ensure CSS is current. If the compiler fails, aborts with an error (does NOT fall back to existing CSS).
2. Opens one `sync_playwright()` session, launches Chromium, creates one `BrowserContext`.
3. Builds the page list from `deck_state.json` in canonical PDF page order (Section 24.10):
   a. Approved slides with `backup: false` in array order (main slides).
   b. Closing slide if `closing_slide == "empty"` — styled empty slide generated in-memory from locked style config.
   c. Separator if `separator_position` is non-null — generated in-memory from `separator_content`.
   d. Approved slides with `backup: true` in array order (backup slides).
4. For each slide, navigates to `file:///<project_root>/slides/<slug>.html`, waits for page load, adds to PDF buffer.
5. For in-memory slides (closing, separator), generates minimal HTML in-memory and renders.
6. Writes multi-page PDF to `output/<folder>/deck_v{NNN}.pdf`. NNN determined by `export_count + 1`.
7. Closes the browser context.
8. Increments `export_count` in the presentation record via `increment_export_count()` (Unit 2).
9. Appends an entry to `output/export_log.jsonl` per the canonical schema in REQ-EXPORT-5.

PDF is rendered at 16:9 aspect ratio per REQ-EXPORT-4.

Env corruption: checks `playwright` availability at module entry; exits 2 if absent.

**G4.5 machine gate detection:** The routing script reads the latest `export_log.jsonl` entry after the export module exits. `playwright_exit_status == 0` → EXPORT SUCCESS → `finalization/post_export`. Non-zero → EXPORT FAILED → re-present G4.4.

### Preferences

No user-specific preferences captured for this unit.

---

## Unit 11: Utility Skills

### Tier 1 — Description

The Utility Skills unit implements the six remaining user-invocable skills and their backing Python modules. Each skill has a bounded, well-defined responsibility and operates in either Run-and-return mode or Terminate mode (per Section 24.19).

**`/debrief:view` skill and `debrief.view`:**

The skill operates in two modes: Yield mode in Phase 3 (sets `pre_view_state`, sets `pending_gate: G3.V_view_dispatch`, yields to routing) and Run-and-return mode in Phase 4/complete (opens browser, no routing side effects). In Phase 1 or Phase 2: print `No slides yet. The view becomes available once slide production begins in Phase 3.` and exit.

The skill handles all edge cases from Section 24.32: nested view (does not overwrite `pre_view_state`), red-green deferral (sets `view_deferred: true`, does not set `pending_gate: G3.V`).

`debrief.view` module — CLI: `python -m debrief.view <query> --project-root <path>`. Reads `deck_state.json` and `debrief_state.json`. Parses the query argument per the query table in REQ-VIEW-1. For each requested slide, reads `output/screenshots/<slug>.png`. Generates `output/view.html` — a self-contained HTML file with inline CSS tiling slides as thumbnail cards (each card: screenshot, slug label in small monospace, slide title) or full-size for single-slide queries. Opens in the default browser via `python -m webbrowser`. Uses no external dependencies beyond stdlib. Overwrites `output/view.html` on each invocation. Exits 0 on success, 1 if no slides match the query (also prints `No slides match this query.`).

**`/debrief:script` skill and `debrief.script_generator`:**

Run-and-return. Precondition: `presentations` array in `deck_state.json` must be non-empty; otherwise print `No export has been done yet. Run /debrief:export first.` and exit.

`debrief.script_generator` — CLI: `python -m debrief.script_generator --project-root <path>`. Reads `deck_brief.md` and `deck_state.json`. Identifies the most recent presentation folder from the last entry in `presentations`. Writes `output/<folder>/script_v{NNN}.md` where NNN is `script_count + 1`. Content per REQ-SCRIPT-3: one section per slide with title, key talking points, transitions, estimated speaking time. Increments `script_count` via `increment_script_count()` (Unit 2). Prints to stderr: `Script written: output/<folder>/script_vNNN.md`. Exits 0.

**`/debrief:handout` skill and `debrief.handout`:**

Run-and-return. Precondition: same as script (at least one export). If no export: print error and exit. Accepts `2up` or `4up` argument. If no argument, presents the inline prompt per Section 24.30:
```
Which handout layout?
  (1) 2-up  -- larger thumbnails, detailed notes (best for teaching)
  (2) 4-up  -- compact 2x2 grid, condensed notes (best for reference)
[default: 2-up]
```

`debrief.handout` — CLI: `python -m debrief.handout --mode <2up|4up> --project-root <path>`. Uses Playwright to render a layout HTML file (generated in-memory combining slide screenshots and explanatory text) to a multi-page PDF. Opens one `sync_playwright()` session per invocation. Reads slide thumbnails from `output/screenshots/<slug>.png`. Assembles explanatory text from slide `content_summary` fields in `deck_state.json`, falling back to the script if available. Writes `output/<folder>/handout_v{NNN}.pdf` where NNN is `handout_count + 1`. Increments `handout_count` via `increment_handout_count()` (Unit 2). When invoked at G4.6, does NOT consume the pending gate (per REQ-HAND-7).

**`/debrief:save` skill:**

Run-and-return. Creates a snapshot of `deck_state.json` and `ledger.jsonl` (NOT `debrief_state.json`) to `output/snapshots/<label>/`. Label: optional user argument, defaults to `YYYYMMDD_HHMMSS`. Label must match `^[a-zA-Z0-9_-]+$`; invalid label: print `Invalid label: labels may contain only letters, numbers, underscores, and hyphens.` and exit. If label already exists, appends `_2`, `_3` suffix. Prints: `Snapshot saved: <label> (deck_state.json, ledger.jsonl)`. Does not modify `debrief_state.json`. Available in all phases.

**`/debrief:reset` skill:**

Terminate mode. Precondition: presents the canonical confirmation prompt per REQ-RESET-3. Accepts only the exact string `RESET`; any other input cancels. On confirmation, deletes all items in REQ-RESET-1: `deck_state.json`, `debrief_state.json`, `style_config.json`, `style_guide.md`, `deck_brief.md`, `ledger.jsonl`, `.debrief/` (entire dir), `slides/` (entire dir), `assets/` (entire dir), `output/` (entire dir). Does NOT delete `CLAUDE.md`. After deletion, prints `Project reset. Run 'debrief new' to create a new project in this directory.` Terminates the Claude Code session per Section 24.31 (invokes `/exit`).

**`/debrief:quit` skill:**

Terminate mode. No confirmation required. Shutdown sequence per REQ-QUIT-1:
1. If red-green cycle active, wait for the current iteration to complete (Slide Maker + QA + snapshot update).
2. Flush `debrief_state.json` and `deck_state.json` with correct `state_hash`.
3. Flush `ledger.jsonl`.
4. Clean transient artifacts from `.debrief/`: delete `task_prompt.md` and any temporaries. Retain: `briefs/`, `snapshots/` (if mid-red-green), `approval_*.json`, `gate_data.json`, `diagnostic_*.md` (if pending), and `draft/` (if `pending_gate == G2.1_style_config_review` or `sub_phase` in `{style/style_dialog, style/style_review}`).
5. Print the canonical summary in the format specified in REQ-QUIT-1.
6. Invoke `/exit` per Section 24.31.

### Preferences

No user-specific preferences captured for this unit.

---

## Unit 12: Paper Analyzer

### Tier 1 — Description

The Paper Analyzer is the Python module `debrief.paper_analyzer`. It extracts structured content from academic paper PDFs using PyMuPDF, producing slide-planning artifacts for journal club presentations. It is deliberately separated from Unit 5 (Consultant Agent and Ledger) because it has its own PyMuPDF-only dependency boundary and its own exit-code contract. Unit tests for this module do not require paper fixtures to be present in the Consultant test suite.

**Invocation:**
```
python -m debrief.paper_analyzer --pdf <path> --paper-slug <slug> --project-root <path>
```

The Consultant invokes this module via Bash when the user provides paper PDF paths during discovery (REQ-CONSULT-17). The Consultant does not import PyMuPDF directly.

**Processing pipeline:**

1. **Parse:** Open the PDF with `fitz.open()`. Extract full text page by page using `page.get_text()`. Extract the section structure from headings. Extract figure captions by scanning for patterns like `"Figure N."` or `"Fig. N."` in the text stream.
2. **Extract figures:** For each figure caption found, identify the page where the caption appears. Extract the corresponding figure image using `page.get_images()` and `fitz.Pixmap`. If a figure spans multiple pages, extract from the page containing the caption.
3. **Rank figures:** Rank by (a) citation frequency in the body text (count references to the figure number in non-caption text) and (b) section location — results section figures score higher than supplementary figures.
4. **Reformat/crop:** For each selected figure image, crop whitespace using a threshold on pixel intensity. Save to `assets/reference/papers/<paper_slug>/figures/fig_<N>.png` at the source PDF resolution. Files are written atomically (write-to-tmp then rename).
5. **Extract claims:** For each key figure, extract the 1-3 sentences immediately following the figure caption that contain the primary finding. Also extract the figure's title line if present.
6. **Write output:** Write `.debrief/paper_analysis_<paper_slug>.md` with sections: paper metadata (title, authors, journal, year — extracted from the first page or PDF metadata), numbered figure list (`N. <caption>`), and suggested narrative arc.

The numbered figure list format must parse correctly for G1.3: each line matches `^(?P<n>\d+)\. (?P<caption>.+)$`.

**Output artifacts:**

- `.debrief/paper_analysis_<paper_slug>.md` — structured markdown document consumed by the Consultant's group-planning context and by the G1.3 gate prepare script.
- `assets/reference/papers/<paper_slug>/figures/fig_<N>.png` — cropped raster images at source PDF resolution.
- The original PDF is copied to `assets/reference/papers/<paper_slug>/<original_filename.pdf>` atomically.

**Exit codes:** 0 on success, 1 on PDF parse error or IO failure (message on stderr), 2 on conda env corruption (fitz import fails — standardized Section 9.3.1 error), 3 on usage error (missing or invalid arguments), 4 on output write failure.

**What this module does NOT do:** It does not call any VLM or LLM API. It does not render slides. It does not write to `deck_state.json` or `debrief_state.json`. All narrative decisions (which figures to include, how to sequence them) belong to the Consultant agent after reading the paper analysis output.

### Preferences

No user-specific preferences captured for this unit.

---

## Profile Integration Summary

The project profile (from `project_profile.json`) is reflected in the following blueprint decisions:

**Quality tooling (ruff, mypy, line length 88):** Every Python module in the `src/debrief/` package targets line length 88, uses ruff for linting and formatting (including import sorting), and satisfies mypy with strict type annotations on all public functions.

**VCS (conventional commits, semver tagging, keep-a-changelog):** The `CHANGELOG.md` follows Keep a Changelog format. Commits follow Conventional Commits style. The plugin is tagged with semver (`v1.1.0`, etc.). Branch strategy is main-only.

**Delivery (conda, environment.yml, conventional source layout):** The Python package lives at `src/debrief/` with `pyproject.toml` or `setup.cfg` declaring it. The `environment.yml` at the plugin root is the single source of truth for all managed dependencies. The launcher handles bootstrap; users never run `conda env create` manually.

**README (domain expert audience, standard depth):** The README targets domain experts (neuroscientists, biomedical researchers) who know conda but not necessarily Python packaging. It covers Installation, First Run, Quick Start, Troubleshooting, Uninstallation, Dependencies, Acknowledgments. No math notation, no API reference, no contributing guide.

**Testing (80% coverage target, readable test names):** Tests are written with pytest. Test names use descriptive verb-object format (e.g., `test_atomic_write_survives_sigkill`, `test_qa_checker_exits_2_on_missing_playwright`). Coverage target: 80% measured across the `src/debrief/` package.

---

*End of blueprint_prose.md*
