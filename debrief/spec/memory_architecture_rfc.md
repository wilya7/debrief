# Debrief Memory Architecture — RFC

**Status:** v1.0 — architecture settled, ready for implementation planning
**Date:** 2026-04-29
**Authors:** Carlo Fusco, Claude Opus 4.7
**Supersedes (on implementation):** BUG-AUDIT-74's consultant-side write-through model. Existing recovery surfaces (`debrief doctor`, `debrief commands`) are extended, not replaced.

---

## 1. Problem

The current memory architecture relies on the consultant agent to **classify-and-write-through** user-surfaced facts into `deck_brief.md` in the same turn they are learned. This is LLM discipline, not mechanical enforcement. Three failure modes have been observed or remain open:

1. **Silent write-skip.** The consultant doesn't classify a user statement as a "fact worth writing" and so doesn't write it. Compaction fires later. Fact lost.
2. **Deferred write collides with compaction.** The consultant intends to write later. Compaction fires between intent and write.
3. **Reactive post-compaction audit.** BC-5.16's audit rule requires the agent to detect context loss via fallible signals (summarization-marker recognition, inability-to-recall, user challenge). False negatives are silent.

The Apr 2026 lab-meeting deck's *Alice was forgotten* failure is the canonical exhibit.

## 2. Goal

Make the recovery surfaces a consultant needs for coherent long-session behavior **produced by code, not in-turn LLM discipline**, so facts established in dialog survive any compaction event regardless of the consultant's turn-level behavior.

## 3. Non-goals

- Replace the consultant agent or restructure its dialog protocol.
- Record subagent (slide-maker, stylist, visual-qa) replies — those are scaffolding, not interview content.
- Replace the existing BC-5.16 deck_brief.md structure — the polished brief is reused as the rewrite target.
- Build semantic search. Grep-level recall is sufficient for v1.

## 4. Architecture overview

Three persistent surfaces plus one new agent.

### 4.1 Surfaces

| Surface | Path | Semantics | Writer | Destructive? |
|---|---|---|---|---|
| **Raw dialog archive** | `.debrief/dialog.jsonl` | Append-only record of *every user turn* and *every consultant reply* in the main thread. Subagent replies (stylist, slide-maker, visual-qa) are NOT archived. Never deleted. Source of truth for *"what was actually said?"* | `PreCompact` hook + `/debrief:quit` | No — append-only |
| **Event timeline** | `output/timeline.jsonl` | Append-only stream of *typed events*: state transitions, gate decisions, slide approvals, exports, AND non-verbal user actions (paper attached, figure selected, gate approved). Programmatic consumers (export, handout, doctor) read this directly. | Multiple emitters (export module, consultant action-capture, gate machinery) | No — append-only |
| **Polished deck brief** | `deck_brief.md` + `output/audience.yaml` | Compressed structured representation of intent. Canonical sections per BC-5.16. The audience roster is duplicated to a standalone YAML file for programmatic consumers. | **Rewrite agent** (sole writer) | Yes — fully regenerated each rewrite |

The pre-existing `output/ledger.jsonl` is **repurposed** as the agent-internal orchestration log (subagent dispatch trail, internal errors, gate-data writes). User-facing content (turns, decisions) leaves the ledger and moves to the new files.

### 4.2 Agents

- **Consultant** (unchanged in role): conducts dialog, dispatches specialists, reads brief + timeline + searches dialog archive when needed. Does **not** write `deck_brief.md`.
- **Rewrite agent** (new, sole writer of brief + roster): processes dialog + timeline into the polished brief. Runs at three trigger points (§5.1).

### 4.3 Data flow

```
user turn / consultant reply
        │
        ▼
Claude Code transcript (ephemeral between compactions)
        │
        │  [PreCompact / /debrief:quit / /debrief:refresh-brief]
        ▼
.debrief/dialog.jsonl (append new user + consultant turns)
        │
        ▼
Rewrite agent (reads dialog + timeline)
        │
        ▼
deck_brief.md  +  output/audience.yaml (atomic regeneration)
        │
        │  [compaction proceeds]
        ▼
post-compaction: consultant reads fresh brief
```

## 5. Rewrite agent — contract

### 5.1 Triggers

The rewrite agent runs on exactly three events:

1. **`PreCompact` hook (primary).** Fires before auto + manual compaction. Synchronous and blocking per Claude Code docs. Guarantees a fresh brief before context is summarized.
2. **`/debrief:quit` (session-end flush).** Catches any session that ends cleanly without an intervening compaction.
3. **`/debrief:refresh-brief` (explicit).** User-invokable for *"capture what I just told you, now."*

**Not triggered on `SessionStart`.** The cases SessionStart would have covered (rewrite failed last session, transient error now resolved) are handled by the explicit trigger when the user notices a stale brief. Periodic triggers are also rejected — no failure case they cover that the three primary triggers don't.

### 5.2 Inputs

- `.debrief/dialog.jsonl` — full archive since project inception.
- `output/timeline.jsonl` — full event timeline.
- (Bootstrap-only, see §5.6) `deck_brief.md` — the prior brief. Only on the very first rewrite of a project.

### 5.3 Outputs

- `deck_brief.md` — fully regenerated, conforms to BC-5.16's canonical structure.
- `output/audience.yaml` — fully regenerated, the standalone roster artifact.

Both are written atomically: write to `.tmp` sibling, fsync, rename. On failure, the prior versions are retained.

### 5.4 Process

1. **Ingest.** Load dialog + timeline (and prior brief, only on bootstrap).
2. **Compress and structure.** Produce canonical sections from dialog + timeline content, deduplicating and reflecting the latest state of every fact (e.g., *"Alice moved from Rome to Milan"* → roster shows Milan, no change-log entry).
3. **Validate.** Output must parse as markdown with exactly the canonical section set. YAML roster must parse and have required `name`/`role` keys per entry.
4. **Atomic dual write.** Write `deck_brief.md.tmp` + `output/audience.yaml.tmp`, then atomically rename both.
5. **Update watermark.** Write `.debrief/rewrite_metadata.json` with last-rewrite timestamp + last-archived turn index + agent version.

### 5.5 Regenerate-from-scratch invariant

Every rewrite reads the entire dialog archive + timeline. Inputs do **NOT** include the prior brief (except on bootstrap). This guarantees:

- **Idempotent.** Same inputs → same output.
- **Self-healing.** A bad rewrite N is corrected by rewrite N+1 reading from source.
- **Easy to test.** Output is a function of recorded source data only.

Token cost on a typical project (~200 turns × ~200 tok = ~40k tokens) is comfortably within Sonnet's window and well under the PreCompact 60s timeout. If projects ever blow past ~150k tokens of dialog, a hybrid (regenerate periodically + incremental between) can be added without breaking this contract.

### 5.6 Bootstrap on first run

On a project's first rewrite (detected by absence of `.debrief/rewrite_metadata.json`), the agent IS allowed to read the prior `deck_brief.md` as a one-time input. It produces a normalized version conforming to BC-5.16, then writes the watermark. From the second rewrite onward, the strict source-derived rule applies. This preserves user work in projects that pre-date this RFC.

### 5.7 Model and prompt

- **Model:** `claude-sonnet-4-6`. No user-configurable override. Faithfulness is sufficient for compression; latency under 60s timeout.
- **Prompt source:** `agents/rewriter.md` agent-card — frontmatter declares model + tool-list (just `Read`); body is the system prompt. The hybrid model in §5.8 means the card is *read* by the hook script, not dispatched as a Task subagent.
- **Discipline rules in prompt:**
  - No invention. Facts not in inputs are not in output.
  - Latest-state-only. No change-log sections.
  - Canonical sections only (BC-5.16 set; never invent new sections).
  - Roster YAML required keys (`name`, `role`) per entry; recommended (`location`, `attendance`, `notes`).
  - Subagent replies are NOT in the archive; do not infer subagent-internal content.

### 5.8 Invocation (hybrid agent-card)

The PreCompact hook runs `python -m debrief.launcher rewrite_brief --project-root ${CLAUDE_PROJECT_DIR}`. That script:

1. Reads `${CLAUDE_PLUGIN_ROOT}/agents/rewriter.md`. Extracts the model declaration from frontmatter and the system prompt from the body.
2. Calls the Anthropic API directly (`anthropic.messages.create()` or equivalent CLI wrapper) with the extracted prompt as `system` and the inputs (dialog + timeline + bootstrap-brief if applicable) as the `user` message.
3. Writes outputs atomically.

This avoids spawning a Claude Code subagent from inside a hook (which is awkward) while preserving Debrief's "every agent has a card" convention.

### 5.9 Failure handling

If the rewrite fails (model error, malformed output, validation failure):

- The PreCompact hook prints the error to stderr and **exits 0**. Compaction proceeds. The brief stays stale this cycle.
- A failure entry is appended to `.debrief/rewrite_errors.jsonl` so the user can audit.
- The next trigger event (next compaction, `/debrief:quit`, or `/debrief:refresh-brief`) retries from the current dialog tail. Transient errors self-heal.

No exit-2 / blocking option. The cost of disrupting the user's flow exceeds the marginal data-safety benefit; persistent failures are visible in the error log and the consultant detects stale-brief signals on next session start.

## 6. Raw dialog archive — contract

### 6.1 Schema

`.debrief/dialog.jsonl`. One JSON object per line:

```json
{"turn": 42,
 "timestamp": "2026-04-29T14:32:17Z",
 "role": "user",
 "responding_agent": "consultant",
 "content": "Alice is the engineer in Rome.",
 "metadata": {"phase": "discovery", "sub_phase": "discovery/dialog"}}
```

`role` ∈ `"user" | "consultant"`. `responding_agent` indicates which agent the user was talking to (consultant when the consultant is the active agent; stylist when stylist was active; etc.). The capture rule (Q4 consensus): **all user turns** are archived regardless of `responding_agent`; **only consultant replies** are archived (subagent replies are not).

### 6.2 Writers

- **`PreCompact` hook** reads the Claude Code transcript (path passed via stdin), filters per the capture rule, appends new turns since the last archived turn.
- **`/debrief:quit`** runs the same logic at session end as a flush.
- The watermark in `.debrief/rewrite_metadata.json` tracks `last_archived_turn` so appends are deduplication-safe.

### 6.3 Append-only invariant

Never deleted, never edited. Session and compaction boundaries are noted via marker entries (`{"event": "session_start"}`, `{"event": "compaction"}`) but do not truncate the archive. This is the source of truth for interview content.

## 7. Event timeline — contract

### 7.1 Schema

`output/timeline.jsonl`. One JSON object per line:

```json
{"event": "slide_approved",
 "timestamp": "2026-04-29T14:42:01Z",
 "turn": 73,
 "payload": {"slug": "intro", "group_id": "g1"}}
```

Event types include: `briefing_complete`, `style_locked`, `slide_approved`, `slide_discarded`, `export_done`, `handout_done`, `script_done`, `paper_attached`, `figure_selected`, `backup_session_started`. New event types are added as features ship.

### 7.2 Writers

Per-event-type emitters across the plugin:
- State machine writes phase/sub_phase transitions.
- Export / handout / script modules write deliverable events.
- Consultant writes action-capture events (`paper_attached`, `figure_selected`).
- Gate machinery writes gate decisions.

### 7.3 Consumers

- **Rewrite agent** — reads to populate `## Prior decisions` in the brief.
- **Programmatic consumers** — export, handout, doctor; can directly read timeline entries by type.
- **`/debrief:quit` session-summary** — renders a human-readable summary.

## 8. Recall

### 8.1 CLI

```bash
python -m debrief.launcher recall <query>
```

Greps both `.debrief/dialog.jsonl` and `output/timeline.jsonl`. Returns matched entries with ±2 entries of context, source-labeled. JSON output for programmatic consumers; pretty-printed table for humans (auto-detected via stdout isatty).

Grep-only for v1. Full-text-search index can be added later without changing the CLI surface.

### 8.2 Consultant discipline

Before replying to a recall question (*"do you remember when we talked about X?"* / *"what did the user say about Y?"*) — and before any reply that asserts a fact about a named person, paper, figure, or decision — the consultant MUST run `recall` first and ground the reply in the returned hits. Answering from in-context memory alone when the recall tool is available is a protocol violation.

This extends BUG-AUDIT-76's *"does Debrief have X?"* pattern (live-enumerate before denying a feature) to *"does the conversation contain X?"* (live-recall before asserting a fact).

## 9. Hooks wiring

### 9.1 `PreCompact` hook

```json
{
  "event": "PreCompact",
  "matcher": "",
  "hooks": [{
    "type": "command",
    "command": "python -m debrief.launcher rewrite_brief --project-root ${CLAUDE_PROJECT_DIR}",
    "timeout": 60
  }]
}
```

Fires on auto + manual compaction. Synchronous / blocking. Hook reads the transcript path from stdin, appends new dialog turns, runs the rewrite, exits 0 (regardless of rewrite success — failures are logged, not blocked).

### 9.2 `SessionStart` hook (existing, NOT extended for rewrite)

Continues to invoke `debrief doctor` + `debrief commands` per BUG-AUDIT-75 / BUG-AUDIT-76. Does NOT run the rewrite agent — the brief is already fresh from the prior session's PreCompact / `/debrief:quit`.

## 10. Consultant discipline (amended)

The consultant's existing on-session-start protocol (BC-5.16, BC-3.16, BC-5.18) is **amended** by this RFC:

- **Replace BC-5.16's write-through rule.** The rewrite agent owns `deck_brief.md`. The consultant does NOT write to it. Job collapses to "have the conversation"; the brief is produced from the conversation automatically.
- **New obligation: recall before recall-class replies.** Before any reply asserting a fact about a named person, paper, figure, or decision, run `python -m debrief.launcher recall <query>` and ground the reply in the returned hits.
- **Retain post-compaction audit.** Catches the residual case where a rewrite failed and the consultant has stale data. The audit re-reads the brief; if drift is detected against in-context memory, the consultant calls `/debrief:refresh-brief` to force a rewrite.

## 11. Open operational items (NOT architecture)

Resolved during implementation, not blocking:

1. **Recall: grep vs full-text-search.** Grep for v1; FTS index can be added without API change if performance demands.
2. **Test refactor for BUG-AUDIT-74/75/76.** Existing regression tests reference write-through and will need amendments to match the rewrite-agent ownership model. Backward-compat: old test names retained where possible; new tests added for rewrite-agent invariants.

## 12. What this does NOT solve

- **Hallucination within the rewrite.** If the rewrite agent invents a fact, the brief carries it. Mitigation: the no-invention prompt rule + dialog archive as queryable source-of-truth that can be consulted to verify any suspicious brief content.
- **Consultant choosing to ignore the brief.** The architecture makes the brief reliably populated; it does NOT make the consultant read it. Existing on-session-start discipline + recall obligation remain load-bearing.
- **Subagent-side context loss.** Slide-maker and stylist have their own contexts and can still lose facts within their short sessions. Scope for a future RFC.

---

## 13. Implementation plan

Five phases, each independently shippable. Total estimate: ~13h.

### Phase 1 — dialog archive + recall CLI (~3h)
- New `.debrief/dialog.jsonl` schema + watermark file.
- Schema-validated capture logic that filters Claude Code transcript per the Q4 capture rule (every user turn, only consultant replies).
- `python -m debrief.launcher recall <query>` grep CLI; greps dialog + timeline; pretty-printed for humans, JSON for programmatic.
- Regression tests for archive-append idempotence + recall-match grammar + watermark advancement.

### Phase 2 — rewrite agent (~4h)
- New `agents/rewriter.md` agent-card with `model: claude-sonnet-4-6` frontmatter and the system prompt body covering canonical sections, no-invention rule, no-change-log rule, latest-state-only rule.
- `python -m debrief.launcher rewrite_brief` entry point: extracts prompt from card, calls Anthropic API directly (no Task-tool dispatch), writes `deck_brief.md` + `output/audience.yaml` atomically, updates watermark.
- Bootstrap-from-prior-brief logic for first-rewrite case (watermark absent).
- Failure handling: log to `.debrief/rewrite_errors.jsonl`, exit 0.
- Regression tests for rewrite idempotence, section-structure validation, roster-YAML extraction, bootstrap mode, error logging.

### Phase 3 — event timeline (~2h)
- New `output/timeline.jsonl` schema.
- Emitter wiring across export, handout, script, visual-qa, consultant action-capture points.
- Recall extended to search both dialog + timeline.
- Regression tests for append-only contract + schema validation + per-event-type coverage.

### Phase 4 — hooks + consultant card amendments (~2h)
- Wire PreCompact hook into `hooks.json` with the rewrite_brief command and 60s timeout.
- Amend `agents/consultant.md`: drop write-through rule, add rewrite-agent ownership statement, add pre-recall-class-reply discipline.
- Add `/debrief:refresh-brief` slash command.
- Update BUG-AUDIT-74/75/76 regression tests for the new invariants.

### Phase 5 — migration, ledger repurposing, doctor extension (~2h)
- Migrate `output/ledger.jsonl` semantics: stop writing user/consultant turns there; keep orchestration log.
- Document migration in spec/blueprint with a Bug-Audit-78 entry.
- Extend `debrief doctor` with `--brief-audit` mode that validates brief structure + roster YAML parse + watermark freshness vs dialog archive last-turn timestamp.
- Update spec/blueprint with new normative requirements (REQ-MEMORY-*) and contracts (BC-5.19 rewrite-agent ownership, BC-5.20 recall discipline, BC-3.18 PreCompact hook).
- BUG-AUDIT-78 entry in spec Bug Catalog.

Each phase ships standalone; Phase 1 is useful before Phase 2 (just dialog archive + recall, no rewrite); Phase 2 is useful before Phase 3 (rewrite from dialog only, no timeline); Phase 3 enriches; Phase 4 wires; Phase 5 migrates and documents.

---

**End of RFC v1.0.** Architecture is settled. Ready for implementation per §13.
