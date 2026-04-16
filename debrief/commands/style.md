# /debrief:style

Run the style dialog to co-design and lock the visual style for the deck.

## Trigger

Use `/debrief:style` to define or update the design system (colors, fonts, layout) and commit it to `assets/style.css`.

## Behavior

- Hands control to the `stylist` agent.
- The agent conducts a dialog to produce `style_config.json` and `style_guide.md` under `.debrief/draft/`. It renders preview slides for user review.
- The agent does **not** write `assets/style.css` directly — only the `style_compiler` (invoked by `promote_style_draft` on approval) writes CSS. This separation is enforced by the `check-write-auth` PreToolUse hook.
- On approval at G2.1 (STYLE APPROVED), `promote_style_draft` moves the draft files to the project root and runs the compiler to produce `assets/style.css`. `style_locked` is set to `true` in `deck_state.json`.
- After locking, slides can be written and the style file cannot be re-opened without explicit `/debrief:style` invocation.

## Precondition: style already locked

If `style_locked: true` in `deck_state.json`, re-running `/debrief:style` will re-open the style dialog from scratch. **Warn the user** that this may invalidate existing slides that were authored against the current style — after a style change, slides may need visual revision to match the new design system. This is not blocked (the user may intentionally want to restyle), but the consequence should be explicit before dispatching.

## Parameters

No parameters required. Optionally provide a reference image or style description in the conversation before invoking.
