# /debrief:script

Generate a versioned presenter script from the current deck brief and approved slides.

## Trigger

Use `/debrief:script` after at least one slide is approved and at least one export has been done. The script is a spoken-word narration aligned with the projected deck.

## Behavior

- Reads `deck_state.json` and selects approved non-backup slides. Backup and non-approved slides are excluded.
- Reads `deck_brief.md` for the presentation context (optional — if missing, proceeds with slide content only).
- Generates a Markdown script with per-slide sections: title, key talking points, transition notes, and estimated timing (~1-2 minutes per slide).
- Writes the output to `output/<presentation_folder>/script_v{NNN}.md`, where `NNN` is filesystem-derived (scan existing `script_v*.md` files, pick max + 1). The presentation folder comes from the most recent entry in `deck_state.presentations`.
- Does NOT mutate `deck_state.json` — versioning is purely filesystem-derived (BUG-AUDIT-25).

## Preconditions

1. At least one presentation must exist in `deck_state.presentations` (i.e., `/debrief:export` has been run). If missing, exits with "No export has been done yet."
2. At least one approved non-backup slide must exist. If missing, exits code 2 with a descriptive message.

## Parameters

No parameters required. An optional target duration (in minutes) may be specified in the conversation.
