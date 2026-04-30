# /debrief:refresh-brief

Force the rewrite agent to regenerate `deck_brief.md` and `output/audience.yaml` from the current dialog archive and event timeline.

## Trigger

Use `/debrief:refresh-brief` when you've just told the consultant something important (a new audience member, a duration change, a major decision) and you want it captured in the brief immediately, without waiting for the next compaction or session-end. This is one of the three rewrite-agent triggers per **REQ-MEMORY-REWRITE-2** / **BC-3.18**:

- `PreCompact` hook (primary, automatic).
- `/debrief:quit` (session-end flush).
- `/debrief:refresh-brief` (this command — explicit user-invokable).

## Behavior

- The command dispatches `python -m debrief.launcher rewrite_brief --project-root . --trigger /debrief:refresh-brief`.
- The rewrite agent (`agents/rewriter.md`) reads `.debrief/dialog.jsonl` + `output/timeline.jsonl` and regenerates `deck_brief.md` + `output/audience.yaml` atomically per **BC-5.19**.
- On the very first rewrite of a project (when `.debrief/rewrite_metadata.json` is absent), the prior `deck_brief.md` IS used as a one-time bootstrap input per **REQ-MEMORY-REWRITE-3**. After that, the strict source-derived rule applies.
- On any failure path (API error, validation failure, write error), the failure is logged to `.debrief/rewrite_errors.jsonl` and the prior brief + audience.yaml are retained per **REQ-MEMORY-REWRITE-4**. The command does NOT block compaction or surface a fatal error to the user.

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
- Blueprint BC-3.18 — rewrite_brief subcommand contract.
- Blueprint BC-5.19 — rewriter agent-card + hybrid invocation.
- `agents/rewriter.md` — rewriter agent system prompt.
- `spec/memory_architecture_rfc.md` — architectural rationale (BUG-AUDIT-78 onwards).
