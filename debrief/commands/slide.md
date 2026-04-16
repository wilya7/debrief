# /debrief:slide

Enter the slide authoring loop. Creates new slides or opens visual revision for existing ones.

## Trigger

Use `/debrief:slide` to generate, revise, or re-roll a presentation slide within the current group.

## Behavior

- Hands control to the `slide-maker` agent.
- The agent creates or revises the slide HTML file under `slides/`.
- On completion, the visual-qa agent automatically reviews the output.
- Style-lock must be active before any slide file can be written. The `check-write-auth` PreToolUse hook enforces this at the Write tool level — the slide-maker agent cannot write to `slides/` unless `deck_state.json: style_locked == true`. However, **check `style_locked` before dispatching** to avoid wasting agent turns on work that will be blocked at the first Write attempt. If style is not locked, instruct the user to run `/debrief:style` first.

## Iteration limit (REQ-SLIDE-5 / BUG-AUDIT-35)

Before re-dispatching the slide-maker for a slug that just received a RED QA result, run the iteration-limit check:

```
python -m debrief.qa_checker check_limit --slug <slug> --project-root <path>
```

This prints a JSON object: `{"limit_reached": true/false, "iteration": N, "limit": 5}`. If `limit_reached` is true, do NOT re-dispatch. Instead present the user with the current slide and ask: "This slide has failed QA N times. Accept with known issues, provide override instructions, or discard?"

## Parameters

No parameters required. The consultant agent manages the active group and slug context.
