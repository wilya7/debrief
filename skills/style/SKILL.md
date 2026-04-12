# /debrief:style

Configure and lock the visual style for this presentation.

## Trigger

Use `/debrief:style` to define or update the design system (colors, fonts, layout) and commit it to `assets/style.css`.

## Behavior

- Hands control to the `stylist` agent.
- The agent produces or updates `assets/style.css` based on the reference design or user preferences.
- Once the style is approved, `style_locked` is set to `true` in `deck_state.json`.
- After locking, slides can be written and the style file cannot be re-opened without explicit `/debrief:style` invocation.

## Parameters

No parameters required. Optionally provide a reference image or style description in the conversation before invoking.
