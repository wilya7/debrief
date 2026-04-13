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

## Troubleshooting

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
