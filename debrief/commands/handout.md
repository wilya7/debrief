# /debrief:handout

Generate a versioned handout PDF with slide thumbnails and explanatory text.

## Trigger

Use `/debrief:handout` to create a condensed, audience-friendly handout document.

## Behavior

- Reads all approved slides from `deck_state.json`.
- Produces a multi-column PDF handout (slide thumbnail + speaker notes layout).
- Saves the output to `exports/handout.pdf` and increments `handout_count` in state.
- Handout formatting respects the archetype (e.g., grant panel handouts include budget slides).

## Parameters

No parameters required. Layout preferences (2-up, 3-up, notes-only) may be specified in the conversation.
