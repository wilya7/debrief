---
name: script
description: Generate a versioned presenter script from the current deck brief and slide records.
user-invocable: true
allowed-tools: Read, Write, Bash
argument-hint: ""
---

# /debrief:script

Generate a speaker script for the current presentation.

## Trigger

Use `/debrief:script` to produce a narration script aligned with the approved slide deck.

## Behavior

- Reads all approved slides from `deck_state.json`.
- Generates spoken-word narration for each slide based on its content summary and visual approach.
- Saves the script to `exports/script.md` and increments `script_count` in state.
- The script respects the archetype's timing defaults (e.g., 12-minute lab meeting vs. 45-minute seminar).

## Parameters

No parameters required. An optional target duration (in minutes) may be specified in the conversation.
