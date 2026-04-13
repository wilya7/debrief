---
name: slide
description: Enter the slide authoring loop. Creates new slides or opens visual revision for existing ones.
user-invocable: true
allowed-tools: Read, Write, Edit, Bash
argument-hint: "[slug]"
---

# /debrief:slide

Invoke the slide-maker agent to produce or revise a single slide.

## Trigger

Use `/debrief:slide` to generate, revise, or re-roll a presentation slide within the current group.

## Behavior

- Hands control to the `slide-maker` agent.
- The agent creates or revises the slide HTML file under `slides/`.
- On completion, the visual-qa agent automatically reviews the output.
- Style-lock must be active before any slide file can be written.

## Parameters

No parameters required. The consultant agent manages the active group and slug context.
