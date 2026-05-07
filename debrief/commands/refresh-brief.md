# /debrief:refresh-brief

Force the rewrite agent to regenerate `deck_brief.md` and `output/audience.yaml` from the current dialog archive and event timeline.

## Trigger

Use `/debrief:refresh-brief` when you've just told the consultant something important (a new audience member, a duration change, a major decision) and you want it captured in the brief immediately, without waiting for the next compaction or session-end. This is one of four rewriter triggers per **REQ-MEMORY-REWRITE-2** / **BC-3.18** / **BC-5.16a** (BUG-AUDIT-101):

- `PreCompact` hook — capture-only (writes `.debrief/.brief_stale` sentinel; no model call).
- Session-start sentinel-detected refresh — automatic; the consultant detects the sentinel and runs the deferred synthesis.
- `/debrief:quit` (session-end flush) — automatic.
- `/debrief:refresh-brief` (this command — explicit user-invokable).

## Behavior (BUG-AUDIT-101)

The consultant orchestrates a four-step Task-dispatch (per `agents/consultant.md` `## Brief Refresh Dispatch`):

1. **Build prompt:** `python -m debrief.launcher build_rewrite_prompt --project-root .` — emits the structured prompt to stdout.
2. **Dispatch:** `Task(subagent_type="rewriter", prompt=<captured stdout>)` — uses Claude Code's session credential (OAuth or whatever the user is authenticated with). No separate `ANTHROPIC_API_KEY` required.
3. **Stage:** consultant writes the agent's markdown to `.debrief/draft/refresh_brief.md` via Bash heredoc.
4. **Validate + atomic write:** `python -m debrief.launcher write_brief --project-root . --trigger /debrief:refresh-brief` — validates brief structure + roster YAML, atomically writes `deck_brief.md` + `output/audience.yaml`, updates `.debrief/rewrite_metadata.json`, removes draft + sentinel.

On the very first rewrite of a project (when `.debrief/rewrite_metadata.json` is absent), the prior `deck_brief.md` IS used as a one-time bootstrap input per **REQ-MEMORY-REWRITE-3**. After that, the strict source-derived rule applies.

On any failure path (Task dispatch error, validation rejection, write error), the failure is logged to `.debrief/rewrite_errors.jsonl` and the prior brief + audience.yaml are retained per **REQ-MEMORY-REWRITE-4**. The command exits 0 — it does NOT surface a fatal error.

## Parameters

No parameters.

## Output location

```
<project_root>/deck_brief.md
<project_root>/output/audience.yaml
```

The brief uses the canonical structure of REQ-CONSULT-DECK-BRIEF-1 (Audience / Roster / Room composition / Intent / Duration / Prior decisions / Open questions / Content Signals). The audience.yaml is the standalone roster artifact derived from the brief's `### Roster` block — emitted only when the brief contains a roster.

## See also

- Spec REQ-MEMORY-REWRITE-1..4 — rewrite agent contract.
- Spec REQ-MEMORY-DIALOG-1 — dialog archive contract (the rewrite source).
- Spec REQ-MEMORY-TIMELINE-1 — event timeline contract.
- Blueprint BC-3.18 — rewrite_brief subcommand contract (PreCompact capture-only after BUG-AUDIT-101).
- Blueprint BC-3.18a / BC-3.18b / BC-3.18c — `build_rewrite_prompt` + `write_brief` + PreCompact-capture-only contracts (BUG-AUDIT-101).
- Blueprint BC-5.16a — consultant `## Brief Refresh Dispatch` (BUG-AUDIT-101).
- Blueprint BC-5.19 — rewriter agent-card (Task-dispatchable after BUG-AUDIT-101).
- `agents/rewriter.md` — rewriter agent system prompt.
- `agents/consultant.md` `## Brief Refresh Dispatch` section — the four-step orchestration protocol.
- `spec/memory_architecture_rfc.md` — architectural rationale (BUG-AUDIT-78 onwards; updated for BUG-AUDIT-101).
