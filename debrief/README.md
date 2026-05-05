# debrief — AI Presentation Assistant for Scientists

**debrief** is a Claude Code plugin that turns research content into polished, structured slide decks. It orchestrates a multi-agent workflow: briefing, style design, slide production, visual QA, and export — all within your Claude Code session.

---

## Installation

debrief is distributed as a Claude Code plugin. Installation is handled automatically when you open a debrief-initialized project in Claude Code.

**Prerequisites:**
- [Claude Code](https://claude.ai/code) installed
- [Miniforge or Conda](https://github.com/conda-forge/miniforge) available on your system

**Setup steps:**

1. Clone or download the debrief plugin to a local directory.
2. Open your presentation project directory in Claude Code.
3. Claude Code will detect the `.claude-plugin/plugin.json` manifest and activate the plugin automatically.
4. The first time you run `/debrief:slide` or another skill, the plugin will verify the environment is ready.

The plugin uses a dedicated conda environment defined in `environment.yml`. This environment is created automatically on first use via the debrief initialization routine — you do not need to set it up manually.

---

## First Run

When you open a new project with debrief active for the first time:

1. The `consultant` agent will greet you and ask for your presentation context.
2. Provide your paper, notes, or a description of what you want to present.
3. The consultant will guide you through archetype selection and briefing.
4. Once briefed, you can proceed to style configuration and slide production.

---

## Quick Start

```
# Start a new presentation session
/debrief:style        # Design and lock the visual style
/debrief:slide        # Generate the first slide group
/debrief:view         # Preview slides in the browser
/debrief:export       # Export to PPTX and/or PDF
```

The consultant agent manages the workflow between these commands. Just follow the prompts.

---

## Working with Papers

debrief can ingest academic paper PDFs during discovery and extract their figures, captions, and per-figure claims into your presentation. **Every archetype accepts papers** - the question is whether the consultant proactively asks for one (`paper_required`) and how the paper is used once provided (`paper_role`).

| Archetype | `paper_role` | `paper_required` | Behavior |
|---|---|---|---|
| `journal_club` (single_paper) | `primary_dissection` | **yes** | Paper IS the presentation. Each selected figure becomes its own slide; figure-by-figure dissection. |
| `journal_club` (multi_paper) | `primary_thematic` | **yes** | Multiple papers compared thematically; cross-paper composite slides allowed. |
| `thesis_discussion` | `primary_document` | **yes** | Thesis PDF is mandatory; structure mapped to chapters with aggressive cuts. |
| `lecture` | `concept_source` | no | Papers are an **optional** resource pool. Pick specific concepts/figures to teach. |
| `lab_meeting` | `concept_source` | no | Same as lecture. Common case: borrow a single figure from someone else's paper for a 5-minute discussion. |
| `seminar` | `concept_source` | no | Same as lecture. |
| `custom` | `concept_source` | no | Most flexible default; you negotiate the actual handling per paper. |
| `conference_talk` | `background_reference` | no | Papers cited where relevant; not auto-converted to figure slides. |
| `job_talk` | `background_reference` | no | Same as conference_talk. |
| `grant_panel` | `background_reference` | no | Same; papers cited as background to a funding case. |
| `investor_pitch` | `background_reference` | no | Same; market research / technical references. |

When you supply a paper PDF path during discovery, the consultant runs the analyzer regardless of archetype. The `paper_role` shapes *how* the paper is used downstream; the `paper_required` flag determines whether the consultant *proactively demands* one. You can also override the role for a specific paper during discussion - e.g., a lecture user can say "I just want to cite this one as background, not build a figure slide" and that paper becomes `background_reference` for this deck.

### Single-figure case

For `concept_source` archetypes (lecture, lab_meeting, seminar), the figure-selection gate (G1.3) accepts either `ALL` or a space-separated list of figure numbers. A reply of `2` selects only Figure 2 - the consultant will build one slide for that figure with proper attribution and **will not** propose additional figure slides "for completeness." Your selection is the contract.

Example: tomorrow's 10-minute lab meeting where you want to discuss Figure 2 of a paper you read this morning. Drop the PDF path into the briefing, reply `2` when the figure list comes up, and the deck centres on that one figure.

### How extraction works

When you provide a PDF path during discovery, debrief runs a local, deterministic pipeline (PyMuPDF - no network calls, no LLM/VLM):

1. Parses the PDF, extracts text, section structure, figure captions, and figure images.
2. Distributes figure images across captions on each page (multi-figure-per-page is handled correctly - each caption gets its own image).
3. Extracts a 1-3 sentence claim per figure from the text following the caption.
4. Pulls metadata (title, authors, journal, year) from PDF metadata + page-1 heuristics, with conservative fallback to `Unknown` rather than wrong guesses.
5. Writes `.debrief/paper_analysis_<slug>.md` (captions + claims + narrative arc) and `assets/reference/papers/<slug>/figures/fig_N.png` per figure.

Slides built from extracted figures carry a citation line (`Figure from <Authors>, <Year>, <Journal>`) and the caption is rendered as a styled `<figcaption>` element, not body text - VETO-07 enforces this regardless of archetype.

---

## Troubleshooting

### "Hook blocked the memory write" / writes outside project denied

You may see the consultant report something like *"Hook blocked the memory write (debrief project policy)"*. This is by design and not a bug:

- The PreToolUse hook `bin/check-write-auth` blocks every Write/Edit outside the project directory, including writes Claude Code's runtime sometimes attempts to its own auto-memory location (`~/.claude/projects/<encoded>/memory/`).
- Debrief has its own project-scoped memory architecture (`.debrief/dialog.jsonl`, `output/timeline.jsonl`, `deck_brief.md`, `output/audience.yaml`, slide records in `deck_state.json`) - all inside the project, all written by Python CLIs that bypass the hook.
- Nothing is lost: the dialog archive captures every turn implicitly, and the rewriter agent consolidates the brief at PreCompact and on `/debrief:quit`.

If you see this message, the consultant in newer plugin versions (post-BUG-AUDIT-92) will silently re-route the action to the appropriate debrief CLI. If you are on an older plugin and see it interrupt your flow, the safe response is "continue" - your project memory is fine.

### Pre-v1.2 silent /debrief:script failure

If you installed an older version of debrief (before BUG-AUDIT-93 fix) and `/debrief:script` exited silently with no output, the cause is almost certainly that the `anthropic` SDK was not declared as a dependency and is therefore missing from your conda env. This also affects the rewriter (the agent that synthesizes `deck_brief.md`). The fix in this version of debrief declares `anthropic>=0.40` in both `pyproject.toml` and `environment.yml` and the bootstrap smoke test now catches a missing SDK on `bin/debrief` startup. To recover an existing install:

```bash
debrief --rebuild-env
```

Or, if you prefer not to rebuild the whole env:

```bash
/Users/<you>/anaconda3/envs/debrief/bin/pip install 'anthropic>=0.40'
```

After install, retry `/debrief:script`. You may also want to run `/debrief:refresh-brief` once to populate any `deck_brief.md` that the rewriter previously failed to synthesize.

### Other troubleshooting

**"Style config not yet locked" error:**
Run `/debrief:style` before attempting to create or edit slides. The style must be locked before any slide files can be written.

**"Write outside project directory is not permitted" error:**
The plugin enforces that all writes stay within the current project directory. Ensure your working directory is set to the presentation project root.

**Slide rendering fails or looks broken:**
Run `/debrief:view` to preview the slide and check for layout issues. The visual-qa agent automatically checks each slide after production; if QA fails, the consultant will report the specific violation.

**jq not found:**
Ensure the debrief conda environment is active. The `jq` utility is required by the `check-write-auth` hook and is included in `environment.yml`.

**Playwright browser not installed:**
On first use, Playwright may need to download its browser binaries. This happens automatically; ensure you have internet access for the initial setup.

---

## Uninstallation

To remove debrief from a project:

1. Remove the `.claude-plugin/` directory from the project root.
2. Delete `deck_state.json`, `debrief_state.json`, and the `slides/` directory if no longer needed.
3. The debrief conda environment can be removed with your conda manager if desired.

---

## Dependencies

### Conda packages (from conda-forge)

| Package | Purpose |
|---|---|
| `python=3.11` | Runtime |
| `jq` | JSON parsing in shell hooks |

### Python packages (pip)

| Package | Version | Purpose |
|---|---|---|
| `playwright` | >=1.40 | Headless browser rendering for slide screenshots |
| `python-pptx` | >=0.6.21 | PPTX assembly from rendered slides |
| `PyMuPDF` | >=1.23 | PDF parsing and figure extraction |
| `json-repair` | >=0.25 | Fault-tolerant JSON parsing for LLM-generated state |

### System dependencies (user-installed)

LibreOffice is required for PPTX-to-PNG conversion during reference-deck style import. It is **not** managed by conda (`libreoffice-still` on conda-forge is Linux-only, and bootstrapping it cross-platform is brittle). Install it once per machine via your OS's native channel:

| Platform | Install command |
|---|---|
| macOS | Download from https://www.libreoffice.org/download/download/ or `brew install --cask libreoffice` |
| Debian / Ubuntu | `sudo apt install libreoffice` |
| Fedora / RHEL | `sudo dnf install libreoffice` |
| Other | https://www.libreoffice.org/download/download/ |

On first run, `bin/debrief` checks for `soffice` on PATH. On macOS, if LibreOffice is installed at the standard `/Applications/LibreOffice.app` location but `soffice` is not on PATH, `bin/debrief` creates a wrapper shim inside the active conda env's `bin/` directory automatically — no shell-profile edits needed. If LibreOffice is not installed at all, the bootstrap exits with install instructions.

### Vendor assets (bundled)

Vendor JavaScript and CSS libraries are bundled under `assets/vendor/` for offline operation. See `assets/vendor/VERSIONS.md` for version and provenance information.

---

## Acknowledgments

### PaperBanana

debrief borrows architectural patterns from [PaperBanana](https://github.com/dwzhu-pku/PaperBanana) by dwzhu-pku, licensed under the Apache-2.0 license. Specifically, the style-guide critic loop, tiered evaluation approach, and exemplar-driven slide generation patterns were informed by PaperBanana's design.

**Attribution:** PaperBanana — Copyright (c) dwzhu-pku. Licensed under Apache-2.0.

**Patent risk disclosure:** PaperBanana and debrief incorporate techniques for AI-assisted presentation generation. Some methods used in automated slide composition, figure-to-slide layout mapping, and LLM-guided visual design may be subject to patent claims by third parties. Users and deployers of debrief should be aware of this potential patent risk, particularly in commercial contexts. No patent license is granted by this software's Apache-2.0 license beyond what is expressly stated therein. See the `NOTICE` file for full details.
