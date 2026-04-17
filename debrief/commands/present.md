# /debrief:present

Launch a browser-based full-screen presentation of the approved slides.

## Trigger

Use `/debrief:present` when you are ready to present. This generates a self-contained `presentation.html` file and opens it in the default browser. Navigate with keyboard controls.

## Behavior

- Reads `deck_state.json` and collects all approved non-backup slides in order.
- Detects progressive disclosure builds: if `slides/<slug>_build_1.html`, `slides/<slug>_build_2.html`, etc. exist alongside `slides/<slug>.html`, includes them in sequence before the final slide.
- Generates `output/presentation.html` — a single self-contained HTML file with all slide content embedded and keyboard navigation.
- Opens the file in the default browser.
- Does NOT require style_locked (read-only operation).
- Does NOT mutate `deck_state.json`.

## Keyboard Controls

| Key | Action |
|---|---|
| Arrow Right / Space / Enter | Next slide |
| Arrow Left | Previous slide |
| F | Toggle fullscreen |
| Escape | Exit fullscreen |

A slide counter ("3 / 12") is displayed at the bottom of the screen.

## Progressive Disclosure

Build files (`<slug>_build_1.html`, `<slug>_build_2.html`, ...) are treated as individual navigation steps. Pressing "next" advances through each build step before moving to the next logical slide.

## Video

`<video>` tags in slides play natively in the browser. Click to play, or use the video's built-in controls.

## Preconditions

1. `deck_state.json` must exist.
2. At least one approved non-backup slide must exist.

On failure, prints a descriptive message and exits code 2.

## Output location

```
output/presentation.html
```

## See also

- `commands/export.md` — generate the deck PDF for sharing.
- `commands/handout.md` — generate a print-ready leave-behind.
