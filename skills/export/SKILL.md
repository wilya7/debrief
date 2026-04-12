# /debrief:export

Export the approved slide deck to PPTX and/or PDF.

## Trigger

Use `/debrief:export` to render all approved slides into a deliverable file.

## Behavior

- Collects all slides with `status == "approved"` from `deck_state.json`.
- Renders each slide via Playwright to capture full visual fidelity.
- Assembles the rendered slides into a PPTX file using `python-pptx`.
- Optionally converts to PDF via LibreOffice.
- Saves the output under `exports/` and increments `export_count` in state.

## Parameters

No parameters required. The export format (pptx, pdf, or both) may be specified in the conversation.
