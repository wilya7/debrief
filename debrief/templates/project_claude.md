# CLAUDE.md — debrief Presentation Project

This project is managed by the **debrief** plugin for Claude Code.

## Active Plugin

Plugin: `debrief` v1.1.0
Agent: `consultant`

## Project Context

<!-- The consultant agent will populate this section during briefing. -->

- **Archetype:** (set during briefing)
- **Presentation title:** (set during briefing)
- **Target audience:** (set during briefing)
- **Duration:** (set during briefing)

## Workflow State

State is tracked in:
- `deck_state.json` — slide manifest, style lock status, export counts
- `debrief_state.json` — session phase, active agent, gate status

## Available Commands

| Command | Description |
|---|---|
| `/debrief:style` | Design and lock the visual style |
| `/debrief:slide` | Generate or revise a slide |
| `/debrief:view` | Preview slides in the browser |
| `/debrief:export` | Export to PPTX and/or PDF |
| `/debrief:script` | Generate a speaker script |
| `/debrief:handout` | Generate a printable handout |
| `/debrief:save` | Save a checkpoint |
| `/debrief:reset` | Restore from a checkpoint |
| `/debrief:quit` | End the session |

## Notes

- Do not manually edit `slides/` files or `assets/style.css` outside of debrief commands.
- All writes to protected paths are gated by the `check-write-auth` hook.
