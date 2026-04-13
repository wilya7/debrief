---
name: view
description: Generate a query-driven HTML view of selected slides for visual inspection.
user-invocable: true
allowed-tools: Read, Write, Bash
argument-hint: "[query]"
---

# /debrief:view

Open a live preview of one or more slides in the browser.

## Trigger

Use `/debrief:view` to render and display the current slide or the full deck in a browser window.

## Behavior

- Launches a local HTTP server to serve slide HTML files.
- Opens the default browser to the slide preview URL.
- The preview reflects the current on-disk slide files.
- Does not require style-lock to be active (read-only operation).

## Parameters

Optional: provide a slide slug to preview a specific slide. Defaults to the full deck.
