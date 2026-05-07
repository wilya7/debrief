# Changelog

All notable changes to debrief are documented in this file.

## [Unreleased] - 2026-05-07

### `anthropic` SDK demoted to optional dep + handout-cascade lifted to consultant (BUG-AUDIT-103)

Final piece of the BUG-AUDIT-101/-102 OAuth-everywhere arc. Two coordinated changes that complete the migration off the `ANTHROPIC_API_KEY` requirement for canonical user flows:

### Added (BUG-AUDIT-103)
- `[project.optional-dependencies] sdk_fallback = ["anthropic>=0.40"]` in `pyproject.toml`. Users who explicitly want the legacy direct-SDK paths install with `pip install '.[sdk_fallback]'`.
- `agents/consultant.md` `## Handout Generation Dispatch` section (BC-5.16c). Documents the precondition self-heal: when the user invokes `/debrief:handout`, the consultant FIRST checks for `speaker_script.md` and runs the BUG-AUDIT-102 four-step Task-dispatch chain to generate the script if absent, THEN proceeds with handout. Convenience preserved; credential model moved up to where Task is available.
- 12 regression tests across `main_handout`'s no-auto-cascade source check, exit-2-on-missing-script behavior, consultant card section content (4 dimensions: section exists, cites BUG-AUDIT, documents self-heal, states credential model), `commands/handout.md` updates.

### Changed (BUG-AUDIT-103)
- `anthropic>=0.40` REMOVED from `pyproject.toml` `[project.dependencies]` and from `environment.yml`'s pip section. It now lives only under `[project.optional-dependencies] sdk_fallback`.
- `bin/debrief` step 5.5 smoke test imports list reverted to its pre-BUG-AUDIT-93 shape: `playwright, pptx, fitz, json_repair`. `anthropic` is no longer required to be importable at bootstrap.
- `main_handout` (`src/unit_11/utility_skills.py`): the in-subprocess auto-cascade to `main_script_writer` is RETIRED. When `speaker_script.md` is missing, the function exits 2 with `"speaker_script.md is missing. Run /debrief:script first, then retry /debrief:handout."`. The consultant orchestration layer handles the precondition self-heal per BC-5.16c.
- `commands/handout.md` documents the new flow.
- BC-1.18 (anthropic-as-required-dep) RETIRED. New BC-1.18a codifies the optional-dep + extras-install contract. BC-1.16 (smoke-test imports) amended. BC-3.20 amended (handout-cascade trigger no longer auto-invoked, retained for backward compat). BC-11.16 amended (speaker_script.md precondition is now hard, exit 2 not 0).
- README troubleshooting section: the auth-error entry I added in the BUG-AUDIT-95-100 docs cycle is replaced with a "Legacy SDK paths and the optional `sdk_fallback` extras" subsection. The historical BUG-AUDIT-93 troubleshooting entry is removed.
- Dependencies section in README: `anthropic` moved from the required-Python-packages table to a new "Optional dependencies" subsection.
- `tests/regressions/test_bug_audit_93_anthropic_dependency.py` is INVERTED: same filename for git-history-traceability, opposite assertions. Now checks that `anthropic` is NOT in required deps, IS in `[project.optional-dependencies] sdk_fallback`, NOT in `environment.yml` pip section, NOT in the smoke test.
- `tests/regressions/test_bug_audit_84_sub_c_handout_finalize.py` `TestHandoutPreconditionAutoCascade` class adapted: the two pre-103 auto-cascade tests are retired in favor of the new BUG-AUDIT-103 contract (no auto-cascade, exit 2 on missing script).

### Fixed (BUG-AUDIT-103)
- OAuth-only Claude Code users have a complete API-key-free workflow end-to-end: PreCompact (capture-only), `/debrief:refresh-brief`, `/debrief:quit` flush, session-start sentinel-detected refresh, `/debrief:script`, `deck-complete-finalization` cascade, `/debrief:handout` (consultant self-heals when script missing), and the export/handout deliverables. The previously-residual `/debrief:handout-cascade` trigger no longer auto-fires from a subprocess context where Task-dispatch is unavailable.

---

## [Unreleased] - 2026-05-07

### Script-writer converted from direct-SDK to Task-dispatch (BUG-AUDIT-102)

Mirrors BUG-AUDIT-101's architectural fix, applied to the script-writer. The pre-fix hybrid invocation pattern (BC-5.21) had the launcher subprocess call the Anthropic SDK directly, requiring `ANTHROPIC_API_KEY`. OAuth-only Claude Code users hit the same auth failure as the rewriter did pre-101.

### Added (BUG-AUDIT-102)
- `python -m debrief.launcher build_script_prompt` (BC-3.20b). Emits the structured user-message body (deck brief + audience + timeline + truncated dialog + slides + existing speaker_script as co-writer baseline) to stdout for the consultant to feed into a Task dispatch. Same 200K-token-cap dialog truncation as today's launcher. Read-only; no model call. Exit 1 only when zero approved main slides.
- `python -m debrief.launcher write_script --trigger <t>` (BC-3.20c). Reads the agent's markdown from `.debrief/draft/refresh_script.md`, runs the same six guardrails as the legacy synthesis path (3 blockers — structure, traceability, roster-mentions; 2 warnings — length-budget, voice-drift), backup-before-overwrite per BC-11.20, atomically writes `speaker_script.md`, emits `script_done` timeline event, removes draft. Always exits 0 (REQ-SCRIPT-WRITER-2 unchanged).
- `agents/consultant.md` `## Script Generation Dispatch` section (BC-5.16b) prescribing the four-step Task-dispatch protocol for `/debrief:script` and `deck-complete-finalization`.
- 19 regression tests across build_script_prompt CLI (success + no-approved-main-slides + usage-message), write_script CLI (write+event success, invalid-script log+exit 0, missing-draft log+exit 0, backup-before-overwrite), consultant card section content, script-writer agent card retired BC-3.20a prose check, commands/script.md content checks.

### Changed (BUG-AUDIT-102)
- `agents/script-writer.md`: BC-3.20a "direct Task-tool dispatch unsupported" prose RETIRED; replaced with description of the new canonical Task-dispatch chain.
- BC-3.20 (script_writer CLI) further amended: synthesis path retired for in-session triggers; cascade trigger retained for backward compat.
- BC-5.21 (script-writer agent) amended for Task-dispatchability.
- `commands/script.md` describes the new four-step flow.

### Fixed (BUG-AUDIT-102)
- `/debrief:script` and the `deck-complete-finalization` cascade now work for OAuth-only Claude Code users without `ANTHROPIC_API_KEY`. The Task-dispatch step uses Claude Code's session credential (empirically stable across releases; not contractually documented per the subagent docs, but the BUG-AUDIT-101 prior-art file documents the `CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR` fallback path).

---

## [Unreleased] - 2026-05-07

### Rewriter converted from direct-SDK to Task-dispatch (BUG-AUDIT-101)

User-reported: an OAuth-authenticated Claude Code user (the standard paid-subscription path) cannot use the rewriter at any of its triggers because the launcher subprocess called the Anthropic SDK directly, requiring `ANTHROPIC_API_KEY`. Cycle 101 routes the rewriter through the consultant's Task tool for in-session triggers and turns PreCompact into a capture-only path with synthesis deferred to next session start. PreCompact runtime is now data-preservation-only — no model call, no auth.

### Added (BUG-AUDIT-101)
- `python -m debrief.launcher build_rewrite_prompt` (BC-3.18a). Emits the structured rewriter user-message body (deck_brief on bootstrap + dialog archive + event timeline) to stdout for the consultant to feed into a Task dispatch. Read-only; no model call.
- `python -m debrief.launcher write_brief --trigger <t>` (BC-3.18b). Reads the agent's markdown from `.debrief/draft/refresh_brief.md`, runs the same brief-structure + roster-YAML validators as the legacy synthesis path, atomically dual-writes `deck_brief.md` + `output/audience.yaml`, updates rewrite metadata, removes draft and `.brief_stale` sentinel on success. Always exits 0 (REQ-MEMORY-REWRITE-4 unchanged).
- `.debrief/.brief_stale` sentinel (BC-3.18c). PreCompact writes this JSON sentinel after capturing dialog turns; the consultant detects it on next session start and runs the deferred synthesis via Task-dispatch.
- `agents/consultant.md` `## Brief Refresh Dispatch` section (BC-5.16a) prescribing the four-trigger Task-dispatch protocol (session start sentinel-detected, /debrief:refresh-brief, /debrief:quit flush; PreCompact handles itself).
- `templates/project_claude.md` step 2.5: sentinel check on session start.
- 17 regression tests across PreCompact-capture-only behavior (in-process + subprocess-no-API-key paths), build_rewrite_prompt CLI, write_brief CLI (4 paths), consultant card section content, project_claude template content, rewriter card no-hybrid claim.

### Changed (BUG-AUDIT-101)
- `main_rewrite_brief --trigger PreCompact` is now capture-only: appends transcript turns to `.debrief/dialog.jsonl`, writes the `.brief_stale` sentinel, exits 0. **No SDK instantiation. No `ANTHROPIC_API_KEY` lookup. No auth.**
- BC-3.18 (rewrite_brief CLI) amended: PreCompact path is capture-only; synthesis retired for in-session triggers (consultant orchestrates via build_rewrite_prompt + Task + write_brief).
- BC-5.19 (rewriter agent) amended for Task-dispatchability. The pre-101 hybrid invocation pattern (launcher reads card + calls SDK directly) is retired for synthesis.
- `agents/rewriter.md` reframed as Task-dispatchable.
- `commands/refresh-brief.md` describes the new four-step flow.
- One existing BUG-AUDIT-80 test adapted: `test_api_failure_logs_error_exits_0` moved from `--trigger PreCompact` (now capture-only) to `--trigger /debrief:refresh-brief` (legacy synthesis path retained for backward compat during transition).

### Fixed (BUG-AUDIT-101)
- OAuth-only Claude Code users with no `ANTHROPIC_API_KEY` can use the rewriter end-to-end. PreCompact is fast and reliable (no API call). The synthesis happens at session-start when the consultant has a live Task surface to dispatch into.

---

## [Unreleased] - 2026-05-07

### Handout parser tolerance + degradation warning (BUG-AUDIT-100)

Field-reported via the journal-club orchestrating session: `/debrief:handout` produced PDFs with `(no notes available)` in every slide cell despite a well-formed `speaker_script.md` in the project. Root cause: `_load_speaker_script`'s regexes only matched the script-writer agent's strict canonical form (`## Slide N: <title>` + `**Slug:** \`<slug>\``), and the user's hand-finalized script used em-dash separators and italic slug markers with budget metadata — both valid markdown but rejected by the parser. The handout exited 0 with no warning; the user discovered the degradation only by opening the PDF.

### Added (BUG-AUDIT-100)
- `_emit_handout_degradation_warning` helper that fires when `_load_speaker_script` returns `None` (zero matches) OR placeholder ratio ≥ 50%. Emits a one-line stderr warning naming the count, the diagnosed reason (one of: `speaker_script.md is missing` / `... is empty` / `... matched zero sections` / `slug/title mismatch`), and the expected grammar.
- `.debrief/handout_warnings.jsonl` log — appended one JSON entry per degraded run, recording timestamp, mode, total/placeholder counts, script presence, parsed-section count, and the first unmatched `## Slide` header line for diagnosis.
- `_first_unmatched_handout_header` helper exposed for the JSONL log + future tooling.
- 19 regression tests across header tolerance (4 separators), slug tolerance (3 marker shapes + trailing metadata), field-scenario end-to-end (full 11-slide em-dash + italic script), strict-grammar regression (BUG-AUDIT-68 cases still parse), and warning emission (4 trigger paths).

### Changed (BUG-AUDIT-100)
- Header regex relaxed from `r"^##\s+Slide\s+\d+\s*(?:\(backup\))?\s*:\s*(.+?)\s*$"` to `r"^##\s+Slide\s+\d+\s*(?:\(backup\))?\s*[:—–\-]\s*(.+?)\s*$"` — accepts `:`, em-dash (U+2014), en-dash (U+2013), or hyphen as the separator.
- Slug regex relaxed from `r"^\*\*Slug:\*\*\s*\`([^\`]+)\`\s*$"` to `r"^\s*\*?\*?\s*Slug:\s*\*?\*?\s*\`([^\`]+)\`"` — accepts bold (`**Slug:**`), italic (`*Slug:`), or plain (`Slug:`) marker styles, and tolerates trailing content after the backticked slug (no `$` anchor).
- BC-11.15a amended with the new tolerant grammar; new BC-11.15c codifies the degradation-warning emission contract.

### Fixed (BUG-AUDIT-100)
- The exact field scenario (em-dash headers + italic slug markers with `· Budget: 0:20`) now parses cleanly. Re-running `/debrief:handout` against the user's project produces 22 mappings (11 slugs + 11 titles) with full notes content per cell.

---

## [Unreleased] - 2026-05-07

### `doctor --phase-audit` mode + Doctor Discipline section (BUG-AUDIT-99)

Field-reported via the journal-club orchestrating session: after 11 approved slides were authored, `debrief_state.phase` stayed at `"discovery"`. `/debrief:view` then branched on `phase != "production"` and emitted *"No slides yet. The view becomes available once slide production begins in Phase 3."* despite real slides on disk. Phase advancement is consultant-driven by design (no automatic trigger), but there was no audit to detect when it had been skipped — and no prescribed routine for the consultant to catch its own drift.

### Added (BUG-AUDIT-99)
- `debrief doctor --phase-audit` mode (BC-3.16 amendment). Detects three drift signals: approved slides exist but `phase == "discovery"`; `style_locked` is True but `phase == "discovery"` and `sub_phase != "discovery/style_analysis"`; `phase == "production"` but `sub_phase == "production/group_planning"` despite approved slides. Each drift entry in the JSON `notes` field includes a copy-pasteable `python -m debrief.debrief_state update --set sub_phase=... --project-root <path>` recovery command. Reported via exit code 1, mirroring `--brief-audit` and `--asset-audit`.
- `_audit_phase` helper in `launcher.py`.
- New `## Doctor Discipline` section in `agents/consultant.md` (BC-5.25). Prescribes routine `doctor` invocation at four run-points: at session start (compaction recovery), after every successful slide-maker dispatch returns, before any read-state command (`/debrief:view`, `/debrief:export`, `/debrief:script`), and before phase transitions. Documents the surface-then-apply recovery loop (read drift report → surface to user → apply recovery command → re-run doctor → proceed).
- 14 regression tests covering argparse registration, drift detection (each of three signals + 3 clean-state cases), `main_doctor` exit-code integration, and consultant-card discipline content.

### Changed (BUG-AUDIT-99)
- BC-3.16 amended with the new audit mode; BC-5.25 added codifying the Doctor Discipline contract for `agents/consultant.md`.

### Fixed (BUG-AUDIT-99)
- The user's exact field scenario: `_audit_phase` now flags 11-approved-slides + `phase=="discovery"` and surfaces the recovery command in the doctor's `notes`. With the new Doctor Discipline section, the consultant runs the audit automatically before `/debrief:view` would otherwise misreport "no slides yet."

---

## [Unreleased] - 2026-05-07

### Anthropic auth-error stderr + script-writer agent-card constraint (BUG-AUDIT-98)

Field-reported via the same journal-club session: `/debrief:script` exited silently with no output when `ANTHROPIC_API_KEY` was unset. Root cause: BUG-AUDIT-93 wired actionable stderr emission for the missing-SDK case (`ModuleNotFoundError`) but the classifier `_is_anthropic_module_error` only catches that one exception class. Anthropic's `Anthropic()` constructor raises `TypeError` ("Could not resolve authentication method") when no credential is in the environment, and `AuthenticationError` (HTTP 401) when a credential is invalid — both fell through the classifier into the silent `sys.exit(0)` branch. The user saw a successful run that produced no `speaker_script.md`.

### Added (BUG-AUDIT-98)
- `_is_anthropic_auth_error` classifier detecting two cases without hard-importing the SDK: (1) `TypeError` whose stringified message contains `"could not resolve authentication"` (case-insensitive), (2) any exception whose class name is `"AuthenticationError"`.
- `_emit_anthropic_auth_missing_stderr(command, *, log_path)` emitter — single actionable line: `"<command>: anthropic API authentication failed; set ANTHROPIC_API_KEY in the environment and retry. Details logged to <log_path>."`. Parameterised log path accommodates `.debrief/script_errors.jsonl` (script-writer) and `.debrief/rewrite_errors.jsonl` (rewriter).
- New BC-3.20a codifies the script-writer agent-card invocation-mode constraint: `agents/script-writer.md` documents that `python -m debrief.launcher script_writer` (via the consultant's Bash tool) is the canonical invocation, and direct `Task`-tool dispatch with a free-form prompt is unsupported.
- 16 regression tests covering classifier (6 cases), emitter (2 contexts), end-to-end script-writer flow (4 trigger/exception combinations), unrelated errors stay silent, rewriter exits 0 unconditionally, and agent-card constraint sentence is present.

### Changed (BUG-AUDIT-98)
- BC-3.18 (rewriter CLI) and BC-3.20 (script-writer CLI) further amended with the auth-error stderr branch — preserving BUG-AUDIT-93's exit-code asymmetry: direct `/debrief:script` exits 2 on auth failure; cascades exit 0; rewriter always exits 0 (PreCompact must never block compaction).
- `agents/script-writer.md` `## Inputs` section gains an opening note clarifying the canonical invocation. Free-form `Task`-tool dispatch produces empty output by design (the source-traceability guardrail rejects claims without structured input blocks); the new note tells the caller to invoke via the launcher CLI.

### Fixed (BUG-AUDIT-98)
- `/debrief:script` and `/debrief:refresh-brief` now produce a clear stderr line on auth failure naming `ANTHROPIC_API_KEY` and the JSONL log path. No more silent exit 0 on the most common Anthropic failure mode.

---

## [Unreleased] - 2026-05-07

### `update_slide` CLI implementation (BUG-AUDIT-97)

Field-reported via the same session: after 11 slides were authored, `deck_state.slides[]` was `[]`. The consultant agent card (`agents/consultant.md:33`, BC-5.17 / REQ-CONSULT-SLIDE-WT-1) instructs the consultant to register every GREEN-QA slide via `python -m debrief.debrief_state update_slide …` in the same turn. The consultant followed the documented protocol verbatim, but the CLI did not exist — `debrief_state.py`'s argparse dispatcher registered only `update` and `append_ledger`. Every slide-registration call produced `argparse: invalid choice: 'update_slide'` and the slide write-through silently failed.

### Added (BUG-AUDIT-97)
- `python -m debrief.debrief_state update_slide --slug <slug> [--title <text>] [--status {draft|approved|needs_revision|discarded}] [--backup ...] [--content-summary ...] [--visual-approach ...] [--design-choices ...] [--forks-not-taken ...] [--user-recommendations ...] [--qa-passed ...] [--accepted-violations <json>] [--group-id ...] [--user-assets <json>] [--has-math ...] [--project-root <path>]` — upserts a `SlideRecord` in `deck_state.json`. Partial update on existing slugs (only passed fields touched); create on new slugs (`--title` required for creates). Auto-sets `last_modified`. JSON parsing for list-shaped fields. Atomic write via `write_deck_state`. New BC-2.20 codifies the contract.
- `SLIDE_STATUS_VALUES` frozenset constant and `_coerce_bool` helper.
- 13 regression tests across subcommand registration, create path, update path, validation (status enum + JSON shape), JSON-parsing for list fields, last_modified auto-update, and idempotence.

### Changed (BUG-AUDIT-97)
- Argparse dispatcher in `debrief_state.py` extended from 2 subcommands (`update`, `append_ledger`) to 3 (`update_slide` added).
- BC-5.17 (consultant slide-record write-through) clarified — the previously-broken `…` placeholder in the documented invocation now points at a concrete contract.

### Fixed (BUG-AUDIT-97)
- The consultant's documented slide-registration protocol works end-to-end. Pre-fix: 0 of 11 slides registered. Post-fix: every GREEN-QA call lands a real `SlideRecord` in the same turn, closing the BUG-AUDIT-75 write-through gap.

---

## [Unreleased] - 2026-05-07

### `bin/debrief --rebuild-env` robustness — surface stderr, post-check by listing, retire `--force` (BUG-AUDIT-96)

Field-reported via the journal-club session: `debrief --rebuild-env` failed with `ERROR: Failed to remove the debrief conda env. Run \`conda env remove -n debrief --force\` manually, then retry \`debrief --rebuild-env\`.` The user followed the hint and got `conda: error: unrecognized arguments: --force` — the `--force` flag was removed from `conda env remove` between conda 22.x and 25.x, so on `conda 25.7.0` the suggested manual command does not exist. Plus, the script suppressed conda's actual stderr via `2>/dev/null`, so the real failure mode was invisible.

### Added (BUG-AUDIT-96)
- BC-1.20 codifies the `--force`-free + stderr-surfacing + post-check-by-listing trio.
- 8 regression tests across no-`--force`-anywhere, no-stderr-suppression on `conda env remove` lines, recovery-hint references `rm -rf "$(conda info --base)/envs/debrief"`, post-check via `conda env list | grep -qx debrief` exists in both branches, and echo-escape rendering is correct.

### Changed (BUG-AUDIT-96)
- `bin/debrief` `--rebuild-env` branch and partial-env cleanup branch (a) drop the `2>/dev/null` redirect on `conda env remove` so conda's actual error message reaches the user, (b) verify env absence post-remove via `conda env list | awk '{print $1}' | grep -qx debrief` rather than trusting the remove's exit code (which differs across conda versions), (c) replace the stale `conda env remove -n debrief --force` recovery hint with `rm -rf "$(conda info --base)/envs/debrief"` — a filesystem operation that doesn't depend on conda CLI flag stability.
- Spec recovery hints in §24.4 (4 places) and §9.4 (1 place) updated to the new `rm -rf` form. The historical BUG-AUDIT-3b transcript at §24.4 retained verbatim as a record of the pre-fix state.

### Fixed (BUG-AUDIT-96)
- Users who hit a partial-env or rebuild-env failure now see conda's stderr (so they can diagnose the real cause) and a recovery hint that actually works on modern conda.

---

## [Unreleased] - 2026-05-07

### `bin/debrief` preflight subcommand validation (BUG-AUDIT-95)

Field-reported via the journal-club session: the user invoked `debrief` (no args) in a non-project directory intending to start a new project, expecting the spec'd `"No project found in the current directory. Run 'debrief new' to create one."` error. Instead they got the §9.3.1 env-corruption error and a `debrief --rebuild-env` recovery hint (a 5–15 minute env rebuild). The user's actual mistake was forgetting the `new` subcommand; the env error misrouted them entirely.

Root cause: `bin/debrief` step 5.5 (post-activation smoke test) ran before step 9 (subcommand dispatch). Any non-pristine env state — including the post-BUG-AUDIT-93 case where `environment.yml` declared `anthropic` but the user's existing env hadn't been rebuilt yet — triggered the env-corruption error first, regardless of what subcommand the user typed.

### Added (BUG-AUDIT-95)
- BC-1.19 codifies the preflight-before-env-checks ordering contract.
- A "Preflight subcommand validation" block in `bin/debrief` (delimited by `# BEGIN preflight subcommand validation` / `# END preflight subcommand validation`), running immediately after the `--rebuild-env` handler and before step 1 (conda detection). Uses only bash builtins (`[[ ]]`, `case`) — no conda or Python invocation.
- 14 regression tests across structural assertions (preflight precedes smoke test, precedes conda detection, follows `--rebuild-env`, contains the canonical error strings, uses only bash builtins, late dispatch retains the same strings as defense-in-depth fallback) and behavioral end-to-end (no-args + no project emits the spec'd error; unknown subcommand emits usage; bare invocation in a project falls through to env activation; `new` falls through to env activation).

### Changed (BUG-AUDIT-95)
- Spec §24.4 reordered to introduce step 0.5 (preflight subcommand validation) explicitly. The error strings emitted by the preflight are byte-identical to the corresponding strings in the late case-dispatch (step 9) so any future code path that bypasses the preflight still produces consistent output.

### Fixed (BUG-AUDIT-95)
- Users who type `debrief` (no args) in a non-project directory now get `ERROR: No project found in the current directory. Run 'debrief new' to create one.` and exit 1 — without conda activation, without the smoke test, without misrouting through the env-rebuild flow. Same for unknown subcommands: `Usage: debrief [new|--rebuild-env]` and exit 1, before any env work.

---

## [Unreleased] - 2026-05-05

### Asset usage audit + paper archival recovery (BUG-AUDIT-94)

User-reported via the 2026-05-05 audit: the journal-club project's source paper PDF was never archived to `assets/reference/papers/`, paper-derived figures landed in `assets/images/` (the user-image bucket), `papers_provided` flag stayed false, and `paper_attached` event was never emitted - the entire deterministic paper pipeline was bypassed in real-session usage. The user observed: *"the provided paper from which the figures were created was never saved in assets. There is a whole folder structure there that almost never gets used."*

### Added (BUG-AUDIT-94)
- New `/debrief:archive-paper <path-to-pdf>` command (BC-3.21). Explicit retroactive paper-archival path: runs `paper_analyzer`, sets `papers_provided=true`, emits `paper_attached` event. Idempotent. Exit codes 0/1/2/3 for success/missing-PDF/analyzer-failure/usage-error.
- `commands/archive-paper.md` — user-facing documentation.
- `debrief doctor --asset-audit` flag (BC-3.16 amendment). Detects asset-state drift: paper-figure-shaped files in `assets/images/` while `assets/reference/papers/` is empty; `papers_provided` flag inconsistency; missing `paper_attached` events; REQ-ASSET-1 slug-prefix violations. Adds an `asset_audit` field to the doctor's JSON output and exits 1 on drift.
- 22 regression tests across launcher subcommand, audit helper, consultant-card content, and command-file presence.

### Changed (BUG-AUDIT-94)
- `agents/consultant.md` `## Paper Analyzer Invocation` § Trigger broadened to enumerate three detection signals: path-shaped string ending in `.pdf`; bare PDF filename resolved against project root + `~/Downloads/`; verbal mention of "paper"/"PDF"/"preprint" with explicit clarifying prompt. The consultant MUST NOT silently proceed when a verbal mention has no associated path - it asks the user explicitly.
- `agents/consultant.md` post-success block now requires BOTH (a) emitting `paper_attached` via `python -m debrief.launcher emit_event` AND (b) updating `papers_provided=true` via `python -m debrief.debrief_state update`. Neither is optional. Tool failures must be surfaced visibly.
- `agents/consultant.md` documents the `/debrief:archive-paper` recovery path: when the consultant detects mid-session drift (paper-figures in slides without paper-analyzer outputs), it surfaces the command to the user as the recovery action.
- BC-3.21 added; BC-3.16 (doctor) amended; BC-5.11 (paper_analyzer invocation) amended.

### Fixed (BUG-AUDIT-94)
- The deterministic paper-handling pipeline (BC-5.11 / BC-12.* / BC-5.22) being silently bypassed in real-session usage. The fix is process-level (broadened triggers + recovery command + observability) since the underlying analyzer code was always correct - the gap was in detection robustness and post-bypass diagnostics.

## [Unreleased] - 2026-05-05

### Anthropic SDK declared as dependency + actionable feedback on missing-SDK (BUG-AUDIT-93)

User-reported via a child project's bug report: `/debrief:script` silently produced nothing on a fresh install. Root cause: `anthropic` Python SDK is lazy-imported at two sites in `launcher.py` (script-writer and rewriter) but was NOT declared in either `pyproject.toml` or `environment.yml`. The lazy-import correctly converted the missing-dependency state to a logged `ModuleNotFoundError` and exit 0 - but with no console output, the user saw a silent no-op. Diagnosis surfaced that the same root cause silently broke the rewriter on every default install, which means `deck_brief.md` and `output/audience.yaml` were never being synthesized.

### Added (BUG-AUDIT-93)
- `anthropic>=0.40` declared in BOTH `pyproject.toml` `[project.dependencies]` AND `environment.yml` pip section. New BC-1.18 enforces cross-file consistency.
- `bin/debrief` step 5.5 smoke test (line 114) now imports `anthropic` alongside `playwright, pptx, fitz, json_repair`. A corrupt env is now caught at bootstrap, not at the first `/debrief:script` invocation.
- Two helper functions in `launcher.py` (`_is_anthropic_module_error`, `_emit_anthropic_missing_stderr`) plus call-site logic that, when the lazy-import path raises `ModuleNotFoundError` for `anthropic`, emits a single actionable line to stderr naming the install fix.
- 15 regression tests across two new test files for the dependency declaration + the stderr/exit-code behavior.

### Changed (BUG-AUDIT-93)
- `/debrief:script` (direct CLI invocation, `trigger == "/debrief:script"`) now exits **2** when the anthropic SDK is missing, instead of silently exiting 0. Cascades from the consultant's 4-step finalization (`deck-complete-finalization`, `/debrief:handout-cascade`) keep the exit-0 contract because the next step in the cascade must continue. The rewriter (`rewrite_brief`) always exits 0 unconditionally because PreCompact must never block compaction (REQ-MEMORY-REWRITE-4) - but it now also prints the actionable stderr line so the user knows the brief did not synthesize.
- BC-3.18 and BC-3.20 amended with the new stderr + exit-code policy.

### Fixed (BUG-AUDIT-93)
- `/debrief:script` and the rewriter (PreCompact / `/debrief:refresh-brief` / `/debrief:quit`) silently failing on default installs because the anthropic SDK was never installed. The fix is purely additive - existing installs that have `anthropic` already (because the user manually `pip install`-ed it) are unaffected.

## [Unreleased] - 2026-05-03

### Auto-memory disclaimer (BUG-AUDIT-92)

User-reported during a live journal-club session: the consultant said "Hook blocked the memory write (debrief project policy)" because Claude Code's runtime auto-memory injection (pointing to `~/.claude/projects/<encoded>/memory/`) collided with debrief's project-scoped memory policy. Diagnosis: the consultant inherited Claude Code's auto-memory injection, tried to use the Write tool against an out-of-project path, and the `check-write-auth` hook correctly blocked it per BC-1.9.

### Added (BUG-AUDIT-92)
- `## Auto-Memory Disclaimer` section in `agents/consultant.md` (placed before `## Recall Discipline`). Tells the consultant to ignore Claude Code's auto-memory injection for debrief sessions, names the canonical debrief memory surfaces, references the hook block as by-design, and instructs the consultant to re-route blocked actions to the appropriate debrief CLI rather than surface them as "memory failed".
- BC-5.24 in `blueprint_contracts.md` formalising the disclaimer section structure and regression obligations.
- Troubleshooting note in `README.md` for users who hit the message in older plugin versions.

### Fixed (BUG-AUDIT-92)
- Confusing UX where the consultant surfaced an out-of-project hook block as a "memory failure" rather than re-routing to debrief's working CLIs. No data was actually lost - the dialog archive captures everything via `append_dialog_turn` and the rewriter consolidates at PreCompact.

## [Unreleased] - 2026-05-03

### Two-axis paper handling refinement (BUG-AUDIT-91)

Universalized paper acceptance after the user observed that `paper_role: none` was over-restrictive. Paper handling is now available across all archetypes; only `journal_club` and `thesis_discussion` proactively demand a paper.

### Added (BUG-AUDIT-91)
- `paper_required` boolean field on every archetype in `archetypes.json`. `true` only for `journal_club` and `thesis_discussion`; `false` everywhere else - papers are optional but accepted.
- Per-paper role override during the consultant's `## Paper Discussion`: a user can say "treat this one as background" and the consultant honors that for the specific paper, regardless of the archetype default.

### Changed (BUG-AUDIT-91)
- `paper_role: none` retired. The three archetypes that previously had it now declare positive defaults: `grant_panel` and `investor_pitch` → `background_reference`; `custom` → `concept_source`.
- `paper_analyzer` trigger is now archetype-agnostic. The consultant runs it whenever the user supplies a PDF path during discovery, regardless of `paper_role`. The role only shapes downstream slide-planning behavior.
- BC-5.23 (`blueprint_contracts.md`) split into a two-axis taxonomy: `paper_role` (behavior) + `paper_required` (proactive demand). The closed `paper_role` set drops `none`; the contract documents the universal trigger and the override mechanism.
- README "Working with Papers" table updated with a `paper_required` column and the new `none`-free archetype mapping.
- Spec REQ-CONSULT-17 re-scoped to remove the `paper_role != none` gate.

## [Unreleased] - 2026-05-03

### Paper-handling cycle (BUG-AUDIT-85 through BUG-AUDIT-90)

Coordinated audit + 7-cycle break-glass remediation of the journal-club / paper-handling pipeline. The audit identified silent data-loss bugs, a spec-vs-prompt drift, and an architectural gap that prevented papers from being used in any archetype other than journal_club. The cycles fix all three.

### Added
- `paper_role` taxonomy across all archetypes (`primary_dissection`, `primary_thematic`, `primary_document`, `concept_source`, `background_reference`, `none`) - BUG-AUDIT-90 / BC-5.23. Lab_meeting, lecture, and seminar can now use papers as an optional concept source; the user's single-figure use case (e.g., reply `2` to G1.3 to build only Figure 2) is now a first-class path.
- `## Figure Claims` block in `paper_analysis_<slug>.md` (one line per figure, format `**Figure N.** <claim>`) - BUG-AUDIT-85 / BC-12.11. Per-figure claims extracted by `paper_analyzer` are now persisted to disk; pre-fix they were silently dropped.
- `## Paper Analyzer Invocation` and `## Paper Discussion` sections in `agents/consultant.md` - BUG-AUDIT-89 / BC-5.22. The first pins deterministic plumbing (trigger, command template, sub_phase transitions, event emissions, multi-paper loop); the second describes open Socratic engagement that branches by `paper_role`.
- `## Paper-Derived Figures` section in `agents/slide-maker.md` - BUG-AUDIT-90. Documents caption styling, attribution format, single-figure rule for `concept_source`, and figure-by-figure rule for `primary_dissection`.
- Programmatic real-PDF end-to-end test (`tests/regressions/test_bug_audit_87_real_pdf_end_to_end.py`) - BUG-AUDIT-87. Generates a deterministic synthetic PDF with PyMuPDF and exercises the full pipeline; closes FINDING-IMPL-5 (mock-heavy test substrate).
- Lab-meeting single-figure smoke test in `SMOKE_TEST_PROMPT.md`.

### Changed
- `extract_figure_images` distributes images across captions on the same page in document order - BUG-AUDIT-86 / BC-12.9. Pre-fix, every caption on a shared page received `images[0][0]`, producing identical PNGs for distinct figures. The single-figure lab-meeting case was at risk on multi-figure-per-page papers.
- `extract_paper_metadata` adds page-1 heuristics for title, authors, and journal when PDF metadata is empty or producer-noise (e.g., `LaTeX with hyperref`) - BUG-AUDIT-87 / BC-12.12. Pre-fix, `journal` was always `None` and the citation line typically rendered "Figure from Unknown, YYYY, Unknown."
- `crop_whitespace` constructs sub-pixmaps via documented `fitz.Pixmap(src, irect)` constructor instead of the fragile `pixmap.set_origin(0,0).__class__(...)` chain - BUG-AUDIT-87 / BC-12.7.
- `agents/consultant.md` Step 5 `journal_club` bullet contains the literal imperative "Which paper(s) would you like to present? Give me the file path(s)." per spec line 1245 - BUG-AUDIT-88 / BC-5.11. Pre-fix, only the sub-mode question was present.
- `agents/visual-qa.md` VETO-07 detects paper-derived figures by file path under `assets/reference/papers/`, not by archetype name - BUG-AUDIT-90. Now fires for any archetype with `paper_role != none`.
- `REQ-CONSULT-17` and `REQ-CONSULT-18` re-scoped from "for journal club presentations" to "any archetype where paper_role != none" - BUG-AUDIT-90.
- Spec line 4769 (open priority question for `papers_provided=true` AND `reference_provided=true`) resolved: the two flags are independent, target disjoint state surfaces, and when both fire from one turn the consultant runs `paper_analyzer` first because paper-derived content informs the brief that informs the style dialog - BUG-AUDIT-90.

### Fixed
- Per-figure claims silently dropped from `paper_analysis_<slug>.md` despite being correctly extracted - BUG-AUDIT-85.
- Multiple captions on one page received the same image xref, producing identical figure PNGs - BUG-AUDIT-86.
- `extract_paper_metadata` always returned `journal=None`; producer-noise treated as a valid author string - BUG-AUDIT-87.
- `crop_whitespace` silently no-cropped on PyMuPDF versions where `set_origin` returns `None` - BUG-AUDIT-87.

## [1.1.0] - 2026-04-11

### Added
- Initial plugin scaffold with full multi-agent workflow
- Nine skill commands: slide, style, export, save, view, reset, quit, script, handout
- Five agent definitions: consultant, slide-maker, visual-qa, bug-diagnostic, stylist
- PreToolUse hook (check-write-auth) for write authorization enforcement
- PostToolUse hook for automated consistency review after file writes
- Eight presentation archetypes: lab_meeting, conference_talk, seminar, lecture, journal_club, grant_panel, job_talk, custom
- Bundled vendor assets: mermaid.js, rough.js, KaTeX
- Apache-2.0 license with PaperBanana attribution and patent risk disclosure
