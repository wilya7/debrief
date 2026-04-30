# Debrief — Stakeholder Specification v1.1

> **This spec is a discovery log, not a build contract.** It reflects the current understanding of the correct process as discovered through 27 break-glass fixes (BUG-AUDIT-1..27). Append-style changes (new Bug Catalog entries, new blueprint contracts, new sections) are legal under the break-glass protocol. Changes that require editing existing spec structure to integrate a genuinely new feature (e.g., NanoBanana raster generation) trigger a rebuild from scratch — the rebuild consumes this spec as validated prior-art.

**Date:** 2026-04-08 (v1.0), 2026-04-09 (v1.1)
**Authors:** Carlo Fusco, Leonardo Restivo
**Archetype:** Claude Code plugin
**Built with:** SVP 2.2

---

## How to Read This Document

This is the complete, self-contained stakeholder specification for Debrief v1.1.
It contains every behavioral requirement and architectural constraint needed to
produce a correct blueprint.

**Part I** contains plugin architecture — the Claude Code plugin structure,
manifest, skill definitions, agent definitions, hook definitions, installation
instructions, and blueprint guidance for plugin implementation.

**Part II** contains behavioral requirements — what the system must do.

**Part III** contains architectural strategy — how the blueprint should be
structured.

---

# PART I — PLUGIN ARCHITECTURE

## 1. Overview of Three Distinct Directory Structures

The Debrief system involves THREE entirely separate directory structures that must
never be conflated:

1. **The distribution repository** — the git repository that developers clone and
   Claude Code installs from. Structured as a single-plugin marketplace monorepo
   (see Section 2.1). Contains the plugin subdirectory, the marketplace catalog,
   and repo-level metadata. Users interact with it only via
   `claude plugin marketplace add` and `claude plugin install`.

2. **The plugin directory** — the installed Debrief plugin, cached by Claude Code
   at `~/.claude/plugins/cache/{id}/`. This contains all code, agent definitions,
   skill definitions, hooks, and the Python package. It is installed once and
   shared across all projects. Users never touch this directory directly.

3. **The project directory** — a per-presentation directory created by `debrief new`
   in the user's working directory. This contains only project data: slides, state,
   configuration, and output. No plugin scripts live here.

Blueprint authors must keep these three structures completely separate. Nothing
from the plugin directory is copied into the project directory at runtime; the
distribution repository is read-only from the user's perspective and exists only
at install time.

---

## 2. Plugin Directory Layout

When installed, the Debrief plugin resides at
`~/.claude/plugins/cache/{id}/` and has the following structure:

```
debrief/                          <- plugin root (${CLAUDE_PLUGIN_ROOT})
├── .claude-plugin/
│   └── plugin.json               <- manifest (ONLY file inside .claude-plugin/)
├── skills/
│   ├── slide/
│   │   └── SKILL.md              <- /debrief:slide
│   ├── style/
│   │   └── SKILL.md              <- /debrief:style
│   ├── export/
│   │   └── SKILL.md              <- /debrief:export
│   ├── save/
│   │   └── SKILL.md              <- /debrief:save
│   ├── view/
│   │   └── SKILL.md              <- /debrief:view
│   ├── restore/
│   │   └── SKILL.md              <- /debrief:restore
│   ├── quit/
│   │   └── SKILL.md              <- /debrief:quit
│   ├── script/
│   │   └── SKILL.md              <- /debrief:script
│   └── handout/
│       └── SKILL.md              <- /debrief:handout
├── agents/
│   ├── consultant.md             <- consultant agent definition
│   ├── slide-maker.md             <- slide agent definition
│   ├── visual-qa.md              <- visual QA agent definition
│   ├── bug-diagnostic.md         <- bug diagnostic agent definition
│   └── stylist.md                <- style co-design agent definition
├── hooks/
│   └── hooks.json                <- hook configurations
├── bin/
│   ├── debrief                   <- startup script: installs Python package, pre-flight checks, launches Claude Code
│   └── check-write-auth          <- PreToolUse write authorization hook script
├── src/
│   └── debrief/                  <- Python package
│       ├── __init__.py
│       ├── launcher.py
│       ├── deck_state.py
│       ├── debrief_state.py
│       ├── style_compiler.py
│       ├── export.py
│       ├── view.py
│       ├── script_generator.py
│       ├── qa_checker.py
│       ├── math_renderer.py
│       ├── routing.py            <- (gutted -- BUG-AUDIT-31)
│       ├── update_state.py       <- (gutted -- BUG-AUDIT-31)
│       ├── prepare.py            <- (gutted -- BUG-AUDIT-31)
│       ├── style_analyzer.py
│       ├── paper_analyzer.py
│       ├── style_guide_generator.py
│       ├── preview_renderer.py
│       ├── asset_ingest.py
│       └── handout.py
├── templates/
│   └── project_claude.md         <- project CLAUDE.md template rendered by the launcher per REQ-INIT-3 (Section 24.7)
├── archetypes.json               <- archetype defaults per Section 24.26
├── assets/
│   └── vendor/                   <- bundled client-side libraries per Section 24.27
│       ├── mermaid.min.js
│       ├── mermaid.min.js.LICENSE.txt
│       ├── rough.min.js
│       ├── rough.min.js.LICENSE.txt
│       ├── katex.min.js
│       ├── katex.min.css
│       ├── katex-fonts/
│       │   └── <woff2 files>
│       └── VERSIONS.md           <- vendor SHA-256 hash manifest
├── references/
│   ├── paperbanana-diagram-style-distilled.md
│   ├── paperbanana-plot-style-distilled.md
│   ├── paperbanana-derivation-meta-prompt.md
│   ├── slide-qa-checklist.md
│   ├── ai4vis-survey-distilled.md
│   ├── preview_placeholder_content.md
│   └── VERSIONS.md
├── .mcp.json                     <- MCP server configs (empty — none needed)
├── settings.json                 <- plugin settings (sets main agent)
├── environment.yml               <- conda dependency specification (Python, Playwright, LibreOffice, etc.)
├── CHANGELOG.md
├── LICENSE                       <- Apache 2.0
├── NOTICE                        <- PaperBanana attribution + patent disclosure
└── README.md                     <- with Acknowledgments section
```

All components live at the plugin root, NOT inside `.claude-plugin/`. The
`.claude-plugin/` directory contains only `plugin.json`.

---

## 2.1 Distribution Repository Layout

Debrief is distributed as a **single-plugin marketplace monorepo**. The git
repository the developer pushes to GitHub has this structure:

```
debrief1.0-repo/                       <- git repo root (= marketplace root)
├── .claude-plugin/
│   └── marketplace.json               <- marketplace catalog (see below)
├── .git/, .gitignore
├── README.md                           <- repo-level README (GitHub landing)
└── debrief/                            <- plugin subdirectory
    └── <full Section 2 layout>         <- identical to the installed plugin tree
```

The repo root contains the marketplace catalog; the `debrief/` subdirectory IS
the plugin and matches Section 2's installed-plugin layout byte-for-byte. When a
user installs, Claude Code clones the repo, reads
`.claude-plugin/marketplace.json`, and copies `./debrief/` into
`~/.claude/plugins/cache/<id>/debrief/`. The installed tree at that cache
location matches Section 2 exactly.

**`marketplace.json` schema** (per Claude Code plugin marketplace reference):

```json
{
  "name": "debrief",
  "owner": { "name": "Carlo Fusco and Leonardo Restivo" },
  "plugins": [
    {
      "name": "debrief",
      "source": "./debrief",
      "description": "AI-powered presentation assistant for scientists"
    }
  ]
}
```

Required fields: `name`, `owner.name`, `plugins[].name`, `plugins[].source`. The
`source: "./debrief"` value resolves relative to the marketplace root (the
directory containing `.claude-plugin/`), pointing at the plugin subdirectory.
The plugin version lives in `debrief/.claude-plugin/plugin.json` as the single
source of truth — the marketplace entry does NOT duplicate it.

**Why a subdirectory, not a flat repo root?** The monorepo wrapper serves three
purposes: (a) it gives Claude Code a marketplace catalog to attach to, enabling
`claude plugin marketplace add <path>` + `claude plugin install debrief@debrief`
from the shell; (b) it lets the repo root hold GitHub-facing artifacts
(`README.md`, `.gitignore`, CI configs, release tooling) without shipping them
into the user's plugin cache; (c) it permits future expansion into a multi-plugin
marketplace without a breaking restructure.

**Repo-level `README.md` vs plugin-level `README.md`.** Both exist. The
repo-level README is seen by GitHub visitors and describes installation,
repository structure, and contributing. The plugin-level README
(`debrief/README.md`) is what ships into the Claude Code plugin cache and is
shown in the plugin manager UI; it follows Section 24.37. They may diverge in
content over time; the initial delivery carries an identical copy at both
locations.

This section is a documentation clarification of existing distribution
mechanics; it does not change the runtime behavior of any unit or add new
requirements.

---

## 3. Project Directory Layout

`debrief new` initializes the **current working directory** as the project
root. It does NOT create a subdirectory. The layout below shows `./ (current
working directory)` as the project root:

```
./ (current working directory)    <- project root, initialized by debrief new
├── CLAUDE.md                     <- generated by plugin system at project init
├── debrief_state.json            <- pipeline control state (routing)
├── deck_state.json               <- deck content state (slides, style, presentations)
├── style_config.json             <- locked after style approval
├── style_guide.md                <- human-readable design rationale, injected into agent prompts
├── deck_brief.md                 <- consultant's living narrative document
├── ledger.jsonl                  <- consultant conversation ledger
├── .debrief/                     <- pipeline working directory; created at init by create_project_structure and re-scaffolded on every debrief invocation per BC-3.14 / BUG-AUDIT-15
│   ├── task_prompt.md            <- assembled task prompt (overwritten each action)
│   ├── briefs/                   <- structured slide briefs per group
│   ├── draft/                    <- created at init by create_project_structure and re-scaffolded on every debrief invocation per BC-3.14. The directory may be empty at any given moment; emptiness is not an error condition. During Phase 2 style dialog the Stylist populates it with draft config+guide; on G2.1 STYLE APPROVED the contents are promoted to project root atomically and the directory is emptied on LOCK SUCCESS per BC-4.6 (see Section 24.8, REQ-STYLE-10). The next debrief entry restores the empty directory tree.
│   │   ├── derived_style_guide.md   <- reference-derived draft (produced by debrief.style_analyzer if user provided a reference at G1.2)
│   │   ├── style_config.json        <- Stylist's draft (pre-promotion)
│   │   ├── style_guide.md           <- Stylist's draft (pre-promotion)
│   │   ├── preview_style.css        <- compiled from draft style_config for preview rendering
│   │   ├── preview_slides/          <- created at init; populated by Stylist during preview generation per REQ-STYLE-10; emptied between style dialog cycles
│   │   │   └── preview_*.html
│   │   └── preview_images/          <- created at init; populated by Stylist during preview generation per REQ-STYLE-10; emptied between style dialog cycles
│   │       └── preview_*.png
│   ├── approval_<slug>.json      <- Slide Maker's approval payload per slide (see Section 24.24)
│   ├── gate_data.json            <- parsed parameterized gate response (short-lived, see Section 24.21)
│   ├── diagnostic_<slug>.md      <- bug-diagnostic report after EXHAUSTED (see Section 24.24 RL3)
│   ├── snapshots/                <- red-green iteration snapshots per REQ-SLIDE-14; retained on /debrief:quit
│   │   └── <slug>_iter_<N>.html
│   └── paper_analysis_<paper_slug>.md  <- journal club paper extraction per REQ-CONSULT-17 (one per imported paper)
├── slides/
│   └── <slug>.html               <- one file per approved slide
├── assets/
│   ├── style.css                 <- compiled from style_config.json
│   ├── fonts/                    <- local font files if needed
│   ├── images/                   <- user-provided images, copied on ingestion
│   │   └── <slug>_<filename>
│   ├── math/                     <- (reserved, empty in v1.1 — future server-side math rendering; see REQ-LATEX-4)
│   │   └── <hash>.svg
│   └── reference/
│       ├── <original>.{pptx,pdf,html}  <- imported reference (single-file modalities)
│       ├── <original_dir>/             <- imported reference (HTML directory modality)
│       │   └── *.html
│       ├── slides/                     <- extracted reference pages (LibreOffice for PPT, PyMuPDF for PDF, Playwright for HTML)
│       │   └── slide_001.png
│       └── papers/                     <- imported papers (journal club, separate from style reference)
│           └── <paper_slug>/
│               ├── <original>.pdf
│               └── figures/
│                   └── fig_001.png
└── output/                          <- created at init by create_project_structure and re-scaffolded on every debrief invocation per BC-3.14. Per-presentation dated subfolders are created on demand by the export module per REQ-EXPORT-3.
    ├── 2026_04_30_SVP_presentation/  <- dated presentation folder (created at export)
    │   ├── deck_v001.pdf
    │   └── script_v001.md
    ├── 2026_05_15_SVP_updated/       <- second presentation folder (different date/title)
    │   ├── deck_v001.pdf
    │   └── script_v001.md
    ├── screenshots/                  <- per-project QA working artifact; NOT inside presentation folders
    │   └── <slug>.png
    ├── view.html                     <- ephemeral; NOT inside a presentation folder
    ├── qa_log.jsonl                  <- per-project; NOT inside a presentation folder
    ├── qa_cycle_log.jsonl            <- machine-readable red-green cycle log
    ├── export_log.jsonl              <- per-project; NOT inside a presentation folder
    └── snapshots/                    <- named snapshots created by /debrief:save
        └── <label>/
```

`/debrief:restore` overwrites `deck_state.json` from a named snapshot and sweeps orphan slides that no longer appear in the restored state. It does NOT delete all project data files. *(BUG-AUDIT-22: replaced the old hard-delete `/debrief:reset` with restore-from-snapshot behavior; see REQ-RESTORE-1/2.)*

**Directory policy (BUG-AUDIT-15).** Every directory listed in the tree above is created by `create_project_structure` (Unit 3, BC-3.9) at `debrief new` time AND re-scaffolded on every subsequent `debrief` invocation via the `ensure_project` launcher subcommand (BC-3.14). The bare-invocation arm of `bin/debrief` calls `python -m debrief.launcher ensure_project "$(pwd)"` before launching Claude Code, so any directory removed by a cleanup operation since the previous session (BC-4.6 style-lock cleanup, `skill_restore`, `skill_quit`) is restored before the next session begins. Cleanup operations are intentional and do not need to recreate the directory themselves; the next `debrief` entry restores the canonical tree. **Empty directories are valid project state**; agents and code MAY rely on every canonical directory existing at every session boundary without checking or creating it themselves. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)* The dynamically-named per-presentation subfolders under `output/` (e.g., `output/2026_04_30_SVP_presentation/`) are NOT created at init — those are created by the export module per REQ-EXPORT-3 when the user actually exports, with the deterministic `<YYYY_MM_DD>_<shortened_title>` name proposed by `routing.propose_presentation_folder_name` per BC-4.7c.

---

## 4. Plugin Manifest (`plugin.json`)

The `.claude-plugin/plugin.json` file is the authoritative plugin manifest.
Required contents:

```json
{
  "name": "debrief",
  "version": "1.1.0",
  "description": "AI-assisted slide deck creation for domain experts",
  "author": { "name": "Carlo Fusco and Leonardo Restivo" },
  "license": "Apache-2.0",
  "keywords": ["slides", "presentation", "deck", "academic"]
}
```

Skills, agents, and hooks are **auto-discovered** by Claude Code from their default subdirectories (`./skills/`, `./agents/`, `./hooks/hooks.json`) — the manifest does NOT declare pointer fields for them. Attempting to declare `skills`, `agents`, or `hooks` as string paths in this manifest causes Claude Code's Zod schema validator to reject the plugin with `Invalid input` errors and the plugin fails to load (see BUG-AUDIT-6). The plugin root MUST contain these subdirectories at the default paths; Claude Code will find them automatically.

---

## 5. Command Definitions

Each user-invocable command is a flat `.md` file inside `commands/` at the plugin root. The file name is `<name>.md` (no plugin prefix); the invocation is `/debrief:<name>`. Command files are **plain markdown with no YAML frontmatter** — the first line is a `# /debrief:<name>` heading, the second paragraph is the one-sentence description shown in the slash-command discovery UI, and the body describes the command's trigger, behavior, and parameters. See BUG-AUDIT-9 (skills→commands migration) and BUG-AUDIT-10 (filename prefix correction) in the Bug Catalog for the history.

### 5.1 File Naming and Discovery

Commands are auto-discovered by Claude Code from the `commands/` subdirectory at the plugin root (`${CLAUDE_PLUGIN_ROOT}/commands/`). The plugin manifest `plugin.json` MUST NOT declare a `commands` field (per BC-1.1 — doing so fails Zod schema validation). Each file in `commands/` named `<name>.md` is registered as a user-invocable slash command `/<plugin>:<name>`, where `<plugin>` is the plugin manifest's `name` field (here, `debrief`). **The filename MUST NOT include a plugin prefix.** Naming a file `debrief_slide.md` produces the double-prefixed invocation `/debrief:debrief_slide` because Claude Code prepends the plugin namespace automatically but does NOT strip any prefix from the filename — see BUG-AUDIT-10. svp historically used a `svp_<name>.md` convention and thus registers its commands as `/svp:svp_bug`, `/svp:svp_save`, etc. (double-prefixed); this is a bug in svp that debrief does not replicate.

### 5.2 Per-Command Definitions

Each of the 9 Debrief commands is a separate file under `src/unit_1/commands/` (workspace) and `debrief1.0-repo/debrief/commands/` (delivered). The file contents for each command are listed below as one-line descriptions (the first paragraph after the H1 heading in the actual file). The full command body — with Trigger, Behavior, and Parameters subsections — lives in the command file itself; this section is the index, not the source of truth.

**`/debrief:slide`** (file: `commands/slide.md`) — Enter the slide authoring loop. Creates new slides or opens visual revision for existing ones. Hands control to the `slide-maker` agent; the visual-qa agent reviews output after each slide. Style-lock must be active.

**`/debrief:style`** (file: `commands/style.md`) — Run the style dialog to co-design and lock the visual style for the deck. Hands control to the `stylist` agent; produces or updates `assets/style.css`; sets `style_locked: true` in `deck_state.json` after approval.

**`/debrief:export`** (file: `commands/export.md`) — Render the complete deck to a versioned PDF using Playwright. Collects approved slides, renders each via Playwright for visual fidelity, assembles into PPTX using `python-pptx`, optionally converts to PDF via LibreOffice.

**`/debrief:save`** (file: `commands/save.md`) — Checkpoint the current deck state and ledger to a named snapshot. Writes `deck_state.json` to a timestamped backup under `.debrief_backups/`. Safe to invoke at any time.

**`/debrief:view`** (file: `commands/view.md`) — Generate a query-driven HTML view of selected slides for visual inspection. Launches a local HTTP server and opens the browser to the slide preview. Read-only; style-lock not required.

**`/debrief:restore`** (file: `commands/restore.md`) — Restore the project to a named snapshot. Lists available backup checkpoints, prompts for confirmation, overwrites `deck_state.json` from the chosen snapshot, and sweeps orphan slides. Does not delete all project data files or touch `.debrief/`. *(BUG-AUDIT-22: renamed from `/debrief:reset`; hard-delete behavior permanently dropped.)*

**`/debrief:quit`** (file: `commands/quit.md`) — Save state, clean up transient artifacts, and exit the session cleanly. Performs a final automatic save, summarizes the session, transitions `debrief_state.json` phase to `done`.

**`/debrief:script`** (file: `commands/script.md`) — Generate a versioned presenter script from the current deck brief and slide records. Saves to `exports/script.md`; respects the archetype's timing defaults.

**`/debrief:handout`** (file: `commands/handout.md`) — Generate a versioned handout PDF with slide thumbnails and explanatory text. Produces a multi-column PDF under `exports/handout.pdf`. Layout (2-up, 4-up, notes-only) may be requested in the conversation before invocation.

### 5.3 What skills/ is for (NOT slash commands)

The `skills/` plugin subdirectory is reserved for **model-auto-invoked knowledge capabilities** — context that Claude loads automatically based on task relevance, not user-invoked slash commands. svp uses `skills/orchestration/` for this purpose. Debrief currently has no such capability and does not ship a `skills/` directory. If a future Debrief feature needs a model-auto-invoked capability (for example, an automatic style-guide primer Claude consults whenever the user mentions PPTX import), that feature belongs in `skills/<name>/SKILL.md` with a `description` field guiding when Claude should load it. User-invocable workflows — everything the user types with a slash prefix — belong in `commands/` regardless of implementation complexity.

---

## 6. Agent Definitions

Each agent is a `.md` file in `agents/` with YAML frontmatter followed by the
system prompt body. The frontmatter defines the agent's identity and runtime
parameters.

### 6.1 Frontmatter Fields

All agents must declare:

- `name` — stable identifier used in skill and hook references
- `description` — one-sentence description of the agent's role
- `model` — the Claude model to use
- `maxTurns` — maximum number of turns before the agent halts
- `tools` — comma-separated list of tools the agent may use

### 6.2 Per-Agent Frontmatter

**`consultant.md`**
```yaml
---
name: consultant
description: Narrative architecture partner for deck content design
model: claude-sonnet-4-6
maxTurns: 50
tools: Read, Write, Edit
---
```

**`slide-maker.md`**
```yaml
---
name: slide-maker
description: Slide authoring agent that generates and revises styled HTML slides
model: claude-sonnet-4-6
maxTurns: 20
tools: Read, Write, Edit, Bash
---
```

**`visual-qa.md`**
```yaml
---
name: visual-qa
description: Visual quality assurance agent that screenshots slides and checks design invariants
model: claude-sonnet-4-6
maxTurns: 10
tools: Read, Write, Bash
---
```

**`bug-diagnostic.md`**
```yaml
---
name: bug-diagnostic
description: Diagnostic agent that investigates rendering failures and authoring errors
model: claude-sonnet-4-6
maxTurns: 15
tools: Read, Write, Edit, Bash
---
```

**`stylist.md`**
```yaml
---
name: stylist
description: Style co-design agent that produces style_config.json and style_guide.md
model: claude-sonnet-4-6
maxTurns: 20
tools: Read, Write, Edit
---
```

---

## 7. Hook Definitions

Hooks are configured in `hooks/hooks.json` and follow Claude Code's hook format.

### 7.1 hooks.json Structure

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth",
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "agent",
            "prompt": "Run visual QA on the written slide. Take a screenshot of the file just written, check all design invariants, and write results to the project qa_log.jsonl.",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

Note: Claude Code agent-type hooks use inline prompts. The prompt text is
passed directly to a new agent invocation; no named agent reference is
required.

Note: The PostToolUse hook uses an inline prompt, not a reference to the named
`visual-qa` agent. The `agents/visual-qa.md` file defines the agent's system
prompt and tool access for when it is invoked by name (e.g., from the slide
skill after fix-attempt failure). The hook's inline prompt is a separate,
shorter instruction tailored to the hook context. Both exist and serve different
invocation paths.

Note: Hook matchers use regex syntax. `Write|Edit` matches either the Write or
Edit tool.

### 7.2 PreToolUse Write-Authorization Hook

The `check-write-auth` command script enforces the write-time style lock invariant. See Section 24.3 (PreToolUse block) for the definitive script contract, including the step-by-step checks, exit codes, and error messages.

### 7.3 PostToolUse Visual QA Hook

The PostToolUse hook fires the visual QA agent after every Write or Edit operation. The agent screenshots the slide, runs invariant checks, and writes a result to `qa_log.jsonl`. See Section 24.3 (PostToolUse block) for the definitive hook contract, including the inline prompt, `qa_checker` invocation, failure handling, and timeout behavior.

---

## 8. Settings Integration

The plugin's `settings.json` sets the consultant as the main agent that greets
the user when they open a Debrief project:

```json
{
  "agent": "consultant"
}
```

---

## 9. Installation and Distribution

### 9.1 Prerequisites

Debrief has exactly one prerequisite that the user must install manually:

- **miniconda** (or **mambaforge**, which includes the faster `mamba` solver)

Everything else — Python 3.11+, Playwright and its Chromium binary, python-pptx, PyMuPDF, LibreOffice, and the Debrief Python package itself — is installed automatically by the `bin/debrief` launcher on first invocation. The user does NOT manually create conda environments, activate them, or run `pip install`. The launcher handles all bootstrap logic.

If miniconda is not installed, running `debrief new` prints a clear error with the miniconda install link and exits.

### 9.2 Plugin Installation

The user installs the Debrief plugin via Claude Code's plugin installation mechanism (typically `/plugin install <source>` or whatever the current Claude Code version supports). This places the plugin at `~/.claude/plugins/cache/<plugin_id>/` (per Claude Code's plugin cache convention). No manual configuration is needed.

After plugin installation, the user navigates to an empty directory and runs `debrief new`. On first invocation, the launcher performs bootstrap (see Section 9.4). On subsequent invocations, it runs directly.

**The user never runs `conda env create`, `conda activate`, or `pip install` manually.** All Python and system dependency management is automatic.

Concretely, for the canonical distribution at `https://github.com/<owner>/debrief1.0-repo`, the install workflow is:

```bash
# From a local clone:
cd /path/to/debrief1.0-repo
claude plugin marketplace add "$(pwd)"
claude plugin install debrief@debrief

# Or directly from GitHub (no local clone):
claude plugin marketplace add https://github.com/<owner>/debrief1.0-repo
claude plugin install debrief@debrief
```

Both paths resolve to the same plugin at `~/.claude/plugins/cache/<id>/debrief/`.
The first form is used during development (the marketplace catalog is read from
the local clone); the second form is the canonical user-facing path after the
repo is published. The `debrief@debrief` syntax is
`<plugin-name>@<marketplace-name>` — both happen to be `debrief` because the
marketplace contains a single plugin with the same name. See Section 2.1 for the
distribution repository layout and the `marketplace.json` schema.

### 9.3 Dependency Bootstrap (Automatic)

All Python dependencies required by Debrief are installed automatically by the `bin/debrief` launcher on first invocation. The launcher reads the plugin's bundled `environment.yml` and creates a dedicated `debrief` conda environment containing:

- Python 3.11+
- `playwright` (Python library) and its Chromium browser binary (installed via `python -m playwright install chromium` inside the env)
- `python-pptx` (PowerPoint style import)
- `PyMuPDF` (journal club paper extraction)
- `json-repair` (defensive JSON parsing, blueprint recommendation)
- `jq` (stdin JSON parsing in the `check-write-auth` hook script)

LibreOffice is a **system dependency** installed by the user (not managed by conda). See §9.3.1 for the discovery protocol and §24.25.1 for how the bootstrap creates a `${CONDA_PREFIX}/bin/soffice` shim on macOS. `libreoffice-still` used to be pinned in `environment.yml` but conda-forge only ships Linux binaries for it, so bootstrapping on macOS via conda was impossible. See BUG-AUDIT-4.

The environment is created once per user per machine and reused across all Debrief projects. The user does not interact with conda directly.

**Why conda is mandatory:** Conda provides hermetic, reproducible environments with pinned Python, Chromium, and LibreOffice versions. This eliminates the classes of failures caused by OS package manager lotteries, user-level Python conflicts, Chromium update drift, and LibreOffice profile lock collisions. Neuroscience and biomedical researchers — Debrief's target users — overwhelmingly already use conda for their computational stack (bioconda, conda-forge), so the install barrier is low for this population.

### 9.3.1 Managed Dependencies

All Debrief dependencies are managed inside the `debrief` conda environment. The plugin ships an `environment.yml` at the plugin root that pins every dependency:

```yaml
name: debrief
channels:
  - conda-forge
dependencies:
  - python=3.11
  - jq
  - pip
  - pip:
    - playwright>=1.40
    - python-pptx>=0.6.21
    - PyMuPDF>=1.23
    - json-repair>=0.25
```

`jq` is required by the `check-write-auth` PreToolUse hook script to parse the Claude Code tool-invocation JSON on stdin (see Section 24.3).

**LibreOffice is NOT a conda-managed dependency.** It is a system dependency the user installs via the OS-native channel (on macOS: LibreOffice.app from libreoffice.org or `brew install --cask libreoffice`; on Linux: `apt install libreoffice` or `dnf install libreoffice`). The `bin/debrief` bootstrap script, after activating the conda env and before installing the Python package, runs a LibreOffice discovery step (BC-1.6a, spec §24.4 step 5.6): if `soffice` is on PATH it proceeds; on macOS, if `soffice` is not on PATH but `/Applications/LibreOffice.app/Contents/MacOS/soffice` exists and is executable, it writes a wrapper shim at `${CONDA_PREFIX}/bin/soffice` (a 2-line bash script that `exec`s the real binary); otherwise it exits 1 with per-platform install instructions. The shim lives inside `${CONDA_PREFIX}/bin`, so destroying the env via `--rebuild-env` automatically invalidates it. Rationale: `libreoffice-still` on conda-forge only ships Linux builds, making the previous Linux-only assumption a silent cross-platform bug (see BUG-AUDIT-4).

Exact versions are pinned by the blueprint author and committed with the plugin. The `environment.yml` file is the single source of truth for Python dependency versions. System dependency versions (LibreOffice) are the user's responsibility.

**No conda dependencies are optional at the user level.** Every feature that depends on a conda-managed package (PowerPoint style import via python-pptx, journal club paper extraction via PyMuPDF, defensive JSON parsing via json-repair, HTML rendering via Playwright) is always available because every conda dependency is always installed. LibreOffice is always required but is verified via the discovery step above — users never see "optional dependency missing" errors; they see either "this works" or "install LibreOffice and retry" at bootstrap time, never at runtime.

**Standardized error contract (retained from prior revision):**

If a module detects that a dependency it expects is unavailable at invocation time (e.g., the conda env was externally modified), it MUST:

1. Exit with code 2.
2. Write to stderr in this format:
   ```
   ERROR: <feature_name> requires <package_name>, which is not available in the debrief conda environment.
   This indicates the environment is corrupt or was externally modified.
   Recovery: run `debrief --rebuild-env` to recreate the environment from environment.yml.
   ```
3. Not attempt any fallback or partial execution.

The routing script and skills surface this error message to the user verbatim. The machine-readable marker is the first line prefix: `ERROR: ... requires ... which is not available in the debrief conda environment.`

### 9.4 The `bin/debrief` Startup Script

The `bin/debrief` script is the single entry point for all Debrief operations. It handles conda environment bootstrap, activation, and subcommand dispatch. The script lives in the plugin's `bin/` directory and must be on the user's PATH (or invoked via its full path).

**High-level responsibilities:**

1. **Check conda availability.** If `conda` is not on PATH, print a clear error with the miniconda install link and exit with code 1.
2. **Check or create the `debrief` conda env.** If the env doesn't exist, create it from the plugin's bundled `environment.yml` (`conda env create -f ${CLAUDE_PLUGIN_ROOT}/environment.yml -n debrief`). Print a progress message: `First-run setup: creating the debrief conda environment (this takes a few minutes)...`
3. **Activate the env** (`conda activate debrief`).
4. **Install the Debrief Python package** into the env via `pip install -e ${CLAUDE_PLUGIN_ROOT}`, gated on a marker file `~/.cache/debrief/pkg_version_<plugin_version>.marker`. If the marker exists, skip this step (the package is already installed for this plugin version).
5. **Install Playwright's Chromium binary** into the env via `python -m playwright install chromium`, gated on a marker file `~/.cache/debrief/chromium_installed.marker`. If the marker exists, skip this step.
6. **Run vendor hash verification** per Section 24.27 (`python -m debrief.launcher verify_vendor_hashes`). A hash mismatch exits with code 1.
7. **Branch on subcommand:**
   - `debrief new` — initialize a new project in the current directory (see REQ-INIT-1).
   - `debrief` (bare) — resume the existing project in the current directory. If no `deck_state.json` exists, print an error and exit.
   - `debrief --rebuild-env` — delete and recreate the `debrief` conda env from `environment.yml`. Used for recovery.
8. **Launch Claude Code** with the plugin enabled.

The script is shell (bash) and uses `conda run -n debrief <command>` or `source activate debrief` depending on platform. See Section 24.4 for the definitive implementation contract.

**First-run experience:** The first invocation is slow (5-15 minutes depending on network speed) because it creates the conda env and downloads Chromium and LibreOffice. The launcher prints progress messages throughout. Subsequent invocations are fast (~500ms activation overhead).

**Marker file cleanup:** The marker files in `~/.cache/debrief/` are keyed by plugin version. When the user updates the plugin, new markers are created and the bootstrap steps re-run for the new version.

### 9.5 Creating a New Project

Navigate to the directory you want to use as the project root and run:
```bash
debrief new
```

`debrief new` initializes the **current working directory** as the project
root. It does NOT create a subdirectory. On first invocation, the startup
script bootstraps the `debrief` conda environment (see Section 9.4). On every
invocation, it activates the env, performs pre-flight checks for conda
availability and env integrity, creates the project directory structure in the
current directory, writes the initial `deck_state.json` and
`debrief_state.json`, generates the project `CLAUDE.md`, writes
`.claude/settings.json` so Claude Code knows to load the Debrief plugin in
this directory only (per Section 9.6), and then launches Claude Code.

### 9.6 Plugin Loading Architecture and Project-Scoped Activation

This section is a primer on how the Debrief plugin is loaded by Claude Code, why the loading mechanism is structured the way it is, and what configuration files are involved. Reading this section saves a future agent or maintainer from reconstructing the design from the eight Bug Catalog entries (BUG-AUDIT-1..8) at the end of this document — every entry in §9.6 is grounded in something one of those audits surfaced.

**The goal.** Two design constraints pull in opposite directions and must be satisfied simultaneously. **First**, Debrief's slash commands MUST be **namespaced** as `/debrief:slide`, `/debrief:export`, `/debrief:save`, etc. — never bare `/slide`, `/export`, `/save`. Three of Debrief's nine skill names (`export`, `save`, `quit`) collide with Claude Code built-in commands; without namespacing, the user would see two autocomplete entries for `/export` and have to disambiguate manually every time. Namespacing is achieved by registering Debrief in a Claude Code **marketplace** and **enabling** it as a plugin via the marketplace, because Claude Code's `/<plugin>:<skill>` namespacing logic only fires for marketplace-registered plugins. **Second**, Debrief must NOT be active in every Claude Code session on the user's machine. It is a domain-specific authoring tool — it should appear when the user is working on a deck project and disappear when they `cd` to a random directory and run `claude`. Project scoping is achieved by writing the marketplace registration and plugin enablement into a **project-local** `.claude/settings.json` instead of the user-wide config at `~/.claude/settings.json`. The combination — install at marketplace level, enable at project level — gives Debrief both correct namespacing AND project-scoped activation. The Debrief startup script `bin/debrief` orchestrates this: it writes the project-local settings file when the user runs `debrief new` and self-heals it on every bare `debrief` resume.

#### 9.6.1 Why namespaced commands matter

Three reasons:

1. **Collision avoidance.** Claude Code ships built-in slash commands `/export`, `/save`, `/quit`, `/help`, `/compact`, `/init`, `/loop`, and others. Three of Debrief's nine skills (`export`, `save`, `quit`) collide with built-ins by name. Without namespacing, the user typing `/export` sees two autocomplete entries — Claude Code's built-in plus Debrief's skill — and must pick the right one each time. With namespacing, the user types `/debrief:export` and gets exactly one match, unambiguously.

2. **Source traceability.** When the user sees `/debrief:slide` in their terminal or in agent logs, the prefix tells them at a glance which plugin owns the command. When debugging "what did this command actually do," `/debrief:export` is unambiguous in a way that bare `/export` never is.

3. **Future-proofing.** If the user later installs a second plugin that also has an `export` skill, the namespacing prevents collision: `/debrief:export` and `/<other-plugin>:export` are different commands and neither shadows the other. Without namespacing, the second plugin would shadow Debrief's command (or vice versa) and the user would see flaky behavior depending on load order.

#### 9.6.2 Claude Code plugin loading: how it actually works

**Settings precedence.** Claude Code reads settings from multiple sources in a defined precedence order, highest to lowest: (1) managed enterprise settings, (2) command-line arguments to `claude`, (3) local project settings (`.claude/settings.local.json`, gitignored), (4) shared project settings (`.claude/settings.json`, committed), (5) user settings (`~/.claude/settings.json`). Higher-precedence sources override lower. For Debrief we use level 4 — shared project settings — because the configuration must be both deterministic per project and visible (not gitignored) so the user can audit what the plugin enabled.

**Marketplaces and plugins.** A Claude Code **marketplace** is a catalog file `marketplace.json` that declares one or more plugins by relative path. A **plugin** is a directory containing a `plugin.json` manifest plus skills, agents, and hooks in convention-named subdirectories (`skills/`, `agents/`, `hooks/`). Marketplaces are not registries — they are descriptors that tell Claude Code "here's a plugin, here's its name, here's where to find it on disk." A marketplace can live anywhere on disk; Debrief's marketplace lives at the root of the `debrief1.0-repo/` repository, alongside the `debrief/` plugin directory it catalogues.

**Two settings keys, both required.** To activate a plugin, the project's `.claude/settings.json` must contain TWO entries: (a) `extraKnownMarketplaces.<name>` — pointing Claude Code at the marketplace by absolute filesystem path; (b) `enabledPlugins["<plugin>@<marketplace>"]: true` — explicitly enabling the named plugin from the named marketplace. Either one alone is insufficient. The `<plugin>@<marketplace>` syntax is `plugin-name@marketplace-name`; for Debrief both happen to be `debrief` because the marketplace contains a single plugin with the same name, so the literal key is `"debrief@debrief"`.

**Why namespacing only happens via the marketplace path.** Claude Code's slash command namespacing logic (`/<plugin>:<skill>`) is wired into the marketplace-installed plugin loader. Plugins loaded via the `--plugin-dir <path>` CLI flag bypass marketplace registration entirely — they are loaded directly into the session as "inline" plugins with no marketplace context, so their skills register with bare names (no `<plugin>:` prefix). This is documented behavior at `code.claude.com/docs/en/plugins.md`. The `--plugin-dir` mechanism is fine for quick development tests of an isolated plugin whose skill names do not collide with anything, but it is NOT suitable for production plugins whose skills collide with built-ins. BUG-AUDIT-8 retired Debrief's use of `--plugin-dir` for exactly this reason.

#### 9.6.3 The four configuration files

Debrief's plugin loading depends on four configuration files. The first three live in the source repository and are committed; the fourth lives in each user project directory and is auto-generated.

**(1) Marketplace catalog: `<repo>/.claude-plugin/marketplace.json`.** Lives at the source repository root (for Debrief: `debrief1.0-repo/.claude-plugin/marketplace.json`). Declares the marketplace name, owner, and the list of plugins it catalogues. Each plugin entry has a `name` and a `source` field; the `source` is a path relative to the marketplace file's parent directory. For Debrief there is exactly one entry pointing at `./debrief`. This file is the Claude Code primitive that gives the plugin a stable name within a marketplace context — it is the file that enables namespacing.

**(2) Plugin manifest: `<plugin>/.claude-plugin/plugin.json`.** Lives inside the plugin directory (for Debrief: `debrief1.0-repo/debrief/.claude-plugin/plugin.json`). Identifies the plugin via `name`, `version`, `description`, `author` (which MUST be an object, not a string — see BUG-AUDIT-6a), and declares the license and keywords. **It MUST NOT** declare top-level `skills`/`agents`/`hooks`/`commands` keys: Claude Code auto-discovers those from the convention subdirectories of the plugin directory, and declaring any of them as a string-path top-level key fails the Zod schema validator (BUG-AUDIT-6b) and the entire plugin fails to load with a `Plugin · unknown · failed to load` error. The convention subdirectories Claude Code auto-discovers inside the plugin directory include **`./commands/`** (flat `.md` files that register as namespaced user-invocable slash commands `/<plugin>:<name>`), **`./skills/<name>/SKILL.md`** (nested files for model-auto-invoked capabilities — these do NOT register as namespaced slash commands in the current Claude Code version, see BUG-AUDIT-9), **`./agents/`**, **`./hooks/hooks.json`**. Debrief currently uses `./skills/` for its user-invocable workflows, which is a documented bug — the correct location is `./commands/` (migration pending per BUG-AUDIT-9).

**(3) Hooks declaration: `<plugin>/hooks/hooks.json`.** Lives inside the plugin directory at the conventional path. Declares PreToolUse and PostToolUse hooks (and other event hooks if needed) using the "Form B" double-nested layout: a top-level `{"hooks": {<event>: [<matcher-wrapper>]}}` wrapper, where each matcher wrapper has a `matcher` regex and a nested `hooks` array of handler dicts. See §7.1 for the Debrief-specific shape and BUG-AUDIT-7 for the schema gotcha. `${CLAUDE_PLUGIN_ROOT}` inside command strings is expanded automatically by Claude Code; do not hand-expand.

**(4) Project settings: `<project>/.claude/settings.json`.** Lives in each deck project root. Contains `extraKnownMarketplaces.debrief` (registers the marketplace by absolute path so Claude Code knows where to find it) and `enabledPlugins["debrief@debrief"]: true` (enables the named plugin). May contain other unrelated keys (custom hooks, agent overrides, user-specific behavior); `ensure_project_settings` preserves them. **This file is written automatically** by `bin/debrief` during `debrief new` and self-healed on every bare `debrief` resume — the user never edits it by hand.

**(0) User settings: `~/.claude/settings.json` — intentionally unused.** Debrief deliberately does NOT write to user-scope settings. Keeping `~/.claude/settings.json` clean of any debrief-related entries ensures Debrief never leaks into unrelated Claude Code sessions. Users who want Debrief in a directory that lacks a `.claude/settings.json` must explicitly run `debrief new` (or bare `debrief` if a `deck_state.json` already exists) to generate the file.

#### 9.6.4 How `bin/debrief` manages the project settings file

The startup script's job is to ensure `.claude/settings.json` is correct **before** handing control to Claude Code. The two dispatch arms in `bin/debrief`'s step 9 (per spec §24.4) handle this:

1. **`debrief new`** (creating a new project). The script invokes `python -m debrief.launcher new "$(pwd)"`. The `new()` function in `debrief.launcher` writes `deck_state.json`, `debrief_state.json`, the project `CLAUDE.md`, AND — as its final step — calls `ensure_project_settings(project_root, plugin_root)` which writes `.claude/settings.json` with the correct marketplace path and `enabledPlugins` entry. After the launcher returns, `bin/debrief` invokes `exec claude` (no flags). Claude Code starts in the project directory, finds the freshly-written settings file, registers the marketplace, enables the plugin, and loads its skills with namespacing.

2. **`debrief`** (bare, resuming an existing project). The script checks for `deck_state.json` in cwd; if absent, it prints the "no project found" error and exits. If present, it runs `python -m debrief.launcher ensure_settings "$(pwd)"`. The `ensure_settings` subcommand of `main_new()` calls `ensure_project_settings(project_root, plugin_root)` — the same function used by `new()` — which is **idempotent** and **self-healing**: it creates `.claude/settings.json` if absent (the project existed before BUG-AUDIT-8 and lacks the file), updates the marketplace path if stale (the user moved the debrief repo on disk after the project was last opened), and preserves any unrelated keys the user added. After the self-heal, `bin/debrief` invokes `exec claude` (no flags).

The launch line is **plain `exec claude`** in both arms. No `--plugin-dir`, no `--plugin`, no flags whatsoever. The project's `.claude/settings.json` does all the work of declaring what to load. The startup script's job is to ensure that file is correct **before** handing control to Claude Code; once control transfers, Claude Code's normal settings-precedence machinery handles plugin discovery, marketplace registration, and skill namespacing. This separation — bash bootstrap writes the configuration; Python helper guarantees idempotency; Claude Code consumes the configuration — keeps each layer simple and testable.

#### 9.6.5 Concrete artifacts

The actual file contents and code excerpts that implement the architecture above. Each block is the canonical form; copying it elsewhere should produce a working configuration.

**Marketplace catalog** at `debrief1.0-repo/.claude-plugin/marketplace.json`:

```json
{
  "name": "debrief",
  "owner": {
    "name": "Carlo Fusco and Leonardo Restivo"
  },
  "plugins": [
    {
      "name": "debrief",
      "source": "./debrief",
      "description": "AI-powered presentation assistant for scientists"
    }
  ]
}
```

The `source` is relative to the marketplace file's parent directory (the repo root). The outer `name` is the marketplace name; the inner `plugins[].name` is the plugin name. Both are `debrief` — that is what makes the enable key `"debrief@debrief"`.

**Plugin manifest** at `debrief1.0-repo/debrief/.claude-plugin/plugin.json`:

```json
{
  "name": "debrief",
  "version": "1.1.0",
  "description": "AI-powered presentation assistant for scientists: generate structured slide decks from research content via Claude Code.",
  "author": { "name": "Carlo Fusco and Leonardo Restivo" },
  "license": "Apache-2.0",
  "keywords": ["presentation", "slides", "science", "research", "pptx", "llm"]
}
```

`author` is an OBJECT, not a string (BUG-AUDIT-6a). No `skills`/`agents`/`hooks` top-level keys (BUG-AUDIT-6b) — auto-discovery handles those from default subdirectories.

**Hooks declaration** at `debrief1.0-repo/debrief/hooks/hooks.json` (Form B):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth",
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "agent",
            "prompt": "A file was just written or edited. Review the change and verify it is consistent with the current slide deck state, design conventions, and any active style constraints. If anything looks inconsistent, report it briefly.",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

Top-level `{"hooks": {...}}` wrapper is mandatory (BUG-AUDIT-7). Each event is a LIST of matcher wrappers; each wrapper has a `matcher` string AND a nested `hooks` array of handlers. `${CLAUDE_PLUGIN_ROOT}` is expanded by Claude Code automatically.

**Project settings** at `<project>/.claude/settings.json` (template — the actual `path` field is filled in at runtime by `ensure_project_settings`):

```json
{
  "extraKnownMarketplaces": {
    "debrief": {
      "source": {
        "source": "directory",
        "path": "/Users/cfusco/Nextcloud/coding projects/debrief1.0/debrief1.0-repo"
      }
    }
  },
  "enabledPlugins": {
    "debrief@debrief": true
  }
}
```

The `path` is the absolute, symlink-resolved path of the marketplace ROOT (the directory that contains `.claude-plugin/marketplace.json`), NOT the inner plugin directory. The literal string `"debrief@debrief": true` is the entire enable expression.

**`bin/debrief` step 9 dispatch** (the relevant excerpt):

```bash
case "${1:-}" in
  new)
    python -m debrief.launcher new "$(pwd)"
    exec claude
    ;;
  "")
    if [[ ! -f "$(pwd)/deck_state.json" ]]; then
      echo "ERROR: No project found in the current directory. Run 'debrief new' to create one." >&2
      exit 1
    fi
    python -m debrief.launcher ensure_settings "$(pwd)"
    exec claude
    ;;
  *)
    echo "Usage: debrief [new|--rebuild-env]" >&2
    exit 1
    ;;
esac
```

`exec claude` has NO flags. NO `--plugin-dir`, NO `--plugin`. Both are wrong (BUG-AUDIT-5 retired `--plugin`; BUG-AUDIT-8 retired `--plugin-dir`). Project scoping comes from cwd having a `.claude/settings.json` that the launcher wrote.

**`ensure_project_settings`** in `src/unit_3/launcher.py` (the source of truth, BC-3.13):

```python
def ensure_project_settings(project_root: Path, plugin_root: Path) -> None:
    settings_dir = project_root / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_path = settings_dir / "settings.json"

    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
            if not isinstance(data, dict):
                data = {}
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    marketplace_root = str(plugin_root.parent.resolve())

    extra = data.get("extraKnownMarketplaces")
    if not isinstance(extra, dict):
        extra = {}
        data["extraKnownMarketplaces"] = extra
    extra["debrief"] = {
        "source": {
            "source": "directory",
            "path": marketplace_root,
        }
    }

    enabled = data.get("enabledPlugins")
    if not isinstance(enabled, dict):
        enabled = {}
        data["enabledPlugins"] = enabled
    enabled["debrief@debrief"] = True

    _atomic_write_json(settings_path, data)
```

`marketplace_root` is `plugin_root.parent.resolve()`. `plugin_root` is `${CLAUDE_PLUGIN_ROOT}`, which points at the inner plugin dir, so its parent is the marketplace root. `.resolve()` gives an absolute symlink-resolved path so the settings file works even when the user runs `bin/debrief` via a `~/.local/bin/debrief` symlink. Idempotent: re-running with the same inputs writes the same file. Non-destructive: any unrelated top-level keys in the existing settings file are preserved.

#### 9.6.6 Common mistakes (and the audit that caught each)

This is a checklist for future agents. Each entry: the mistake, the audit that caught it, and the file or symbol involved. Future contributors editing any of the configuration files above should re-read this list before committing.

- **Symlink resolution in `bin/debrief` plugin-root fallback (BUG-AUDIT-3a).** `${BASH_SOURCE[0]}` is the symlink path when the script is invoked via a symlink on PATH. `dirname` followed by `..` gives the symlink's parent, NOT the real plugin root. Fix: walk symlinks with `while [[ -L "$source" ]]; do source="$(readlink "$source")"; ...; done` before computing the parent. See `bin/debrief` step 1 (the `# BEGIN CLAUDE_PLUGIN_ROOT resolution` block).

- **Misleading "partial env" error after env create failure (BUG-AUDIT-3b).** The cleanup branch ran `conda env remove` unconditionally after any env create failure. When no env existed, the remove failed and the script printed "Partial debrief env exists" — false. Fix: gate the cleanup on `conda env list | awk '{print $1}' | grep -qx debrief` so the partial-env claim only fires when a real partial env exists.

- **`plugin.json` `author` as plain string (BUG-AUDIT-6a).** Must be an object: `{"name": "..."}`. Claude Code's Zod schema rejects the string form with `expected object, received string` and the entire plugin fails to load.

- **`plugin.json` `skills`/`agents`/`hooks` as top-level string paths (BUG-AUDIT-6b).** Must be ABSENT from `plugin.json`. Claude Code auto-discovers these from convention subdirectories (`./skills/`, `./agents/`, `./hooks/hooks.json`). Declaring them as string paths fails Zod validation with `Invalid input` and the entire plugin fails to load with `Plugin · unknown · failed to load`.

- **`hooks.json` missing top-level `hooks` wrapper (BUG-AUDIT-7).** The file MUST start with `{"hooks": {...}}`. Putting event keys (`PreToolUse`, `PostToolUse`) at the top level directly produces the Zod error `expected record, received undefined` at JSON path `["hooks"]`.

- **`hooks.json` flat handler shape (BUG-AUDIT-7).** Each event's value is a list of MATCHER WRAPPERS, not a list of handlers directly. The matcher wrapper has `{"matcher": "Write|Edit", "hooks": [...]}` — the actual handler dicts (with `type`, `command`, `timeout`) live INSIDE the inner `hooks` array. The "Form B" name refers to this double-nested layout: top-level `hooks` record, then per-event arrays of matcher wrappers, then per-wrapper inner `hooks` arrays of handlers.

- **`bin/debrief` using the non-existent `--plugin` flag (BUG-AUDIT-5).** Claude Code does not have a `--plugin` flag. Using it produces `error: unknown option '--plugin'` at launch and Claude Code exits without starting a session.

- **`bin/debrief` using `--plugin-dir` and getting bare-named skills (BUG-AUDIT-8).** `--plugin-dir <path>` exists and works as a session-scoped dev mechanism, but it bypasses marketplace registration. Plugins loaded this way have NO namespace prefix, so their skills register as bare `/export`, `/save`, `/quit` and collide with built-ins. The fix is to write `.claude/settings.json` and `exec claude` with no flags, letting Claude Code load the plugin via the marketplace mechanism.

- **`libreoffice-still` from conda-forge is Linux-only (BUG-AUDIT-4).** macOS bootstrap fails with `PackagesNotFoundError`. LibreOffice is reclassified as a system dependency installed by the user; `bin/debrief` discovers it and writes a wrapper shim into `${CONDA_PREFIX}/bin/soffice` on macOS so the runtime `subprocess.run(["soffice", ...])` calls find it via PATH.

- **Stale marketplace path in `.claude/settings.json`.** If the user moves the `debrief1.0-repo/` directory on disk after a project was created, the project's `extraKnownMarketplaces.debrief.source.path` becomes stale and Claude Code fails to find the marketplace. `ensure_project_settings` self-heals this on every bare `debrief` invocation by overwriting the path with the current `plugin_root.parent.resolve()`. Future agents who edit `ensure_project_settings` MUST preserve this self-heal property.

- **Mismatched `enabledPlugins` key syntax.** The literal key is `"debrief@debrief": true`. The first `debrief` is the plugin name; the second is the marketplace name; the `@` is the separator. Wrong forms that silently disable the plugin: `"debrief": true` (no marketplace), `"debrief/debrief": true` (wrong separator), `"@debrief": true` (missing plugin), `"debrief@debrief": "true"` (string instead of boolean). The exact syntax matters because Claude Code does not surface a parse error for these — the plugin simply does not appear in `/plugin`.

- **YAML quoting in `SKILL.md` and agent frontmatter.** YAML has subtle string-vs-bool, string-vs-number, and quoting rules. Always quote strings that look like other types: `"true"`, `"1.0"`, `"[]"`. Use the `|` block style for multi-line strings. Test by parsing with `yaml.safe_load` before committing. The `allowed-tools` field accepts a space-separated string (`"Read Write Edit Bash"`) or a YAML list (`["Read", "Write", "Edit", "Bash"]`); a comma-separated string (`"Read, Write, Edit, Bash"`) is undocumented and may be accepted leniently or rejected silently depending on Claude Code version.

- **JSON syntax pitfalls.** Trailing commas (legal in JS, illegal in JSON). Single quotes (illegal in JSON — use double). Comments (illegal in JSON — none of `//`, `/* */`, `#`). Always validate with `python -m json.tool < file.json` after editing any of the four configuration files above. The Bug Catalog has multiple entries that would have been caught earlier by a `json.tool` validation step.

- **Hook command paths referencing `${CLAUDE_PLUGIN_ROOT}` must be wrapped in escaped double quotes (BUG-AUDIT-12a).** Claude Code's hook runner invokes `command`-type hooks via `/bin/sh` after expanding `${CLAUDE_PLUGIN_ROOT}`. If the expanded path contains whitespace (e.g., macOS `/Users/cfusco/Nextcloud/coding projects/...`), an unquoted command token gets split by the shell and produces `/bin/sh: <first-word-of-path>: No such file or directory`. Fix by wrapping the full path in escaped double quotes: `"command": "\"${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth\""`. The `plugins-reference.md` doc page shows this pattern in its dependency-install walkthrough. Never rely on the plugin being installed at a path without spaces — users put the plugin repo wherever they want.

- **Plugin user-invocable commands belong in `commands/`, not `skills/` (BUG-AUDIT-9).** Claude Code's `commands/` plugin subdirectory produces namespaced slash commands (`/<plugin>:<name>`). Its `skills/` subdirectory — even with `user-invocable: true` frontmatter — produces bare-named commands that collide with Claude Code built-ins like `/export`, `/save`, `/quit`. The `code.claude.com/docs/en/plugins.md` page says plugin skills are always namespaced; empirically this is false in Claude Code v2.1.104 for the `skills/` plugin subdirectory — only `commands/` namespaces. Use flat `commands/<name>.md` files (bare filenames — see BUG-AUDIT-10 below for why the filename must NOT include a plugin prefix) with no YAML frontmatter, starting with a `# /<plugin>:<name>` markdown heading. The `skills/<name>/SKILL.md` layout is the correct location for model-auto-invoked **knowledge capabilities** (svp uses `skills/orchestration/` for this purpose) — NOT for user-invocable workflows.

- **Command filenames MUST NOT include a plugin prefix (BUG-AUDIT-10).** Claude Code registers a command file `commands/<name>.md` as `/<plugin>:<name>` by prepending the plugin namespace from `plugin.json`. It does NOT strip any prefix from the filename. Naming a file `commands/debrief_slide.md` produces `/debrief:debrief_slide` (double-prefixed), not `/debrief:slide`. The file's first-line `# /debrief:slide` heading is documentation only and has no effect on registration. svp currently uses the `<plugin>_<name>.md` convention and thus registers its commands as `/svp:svp_bug`, `/svp:svp_save`, etc. (double-prefixed); svp's documentation says `/svp:bug` but users actually have to type `/svp:svp_bug`. The correct pattern is bare filenames: `commands/slide.md` → `/debrief:slide`. svp is NOT a canonical reference for filename naming.

---

## 10. Plugin Root vs. Plugin Data

Blueprint authors must understand the distinction between two environment
variables provided by Claude Code:

- `${CLAUDE_PLUGIN_ROOT}` — the plugin installation directory
  (`~/.claude/plugins/cache/{id}/`). Use this for all references to plugin
  scripts, agent definitions, and static assets that are part of the plugin
  itself. This path changes when the plugin is updated.

- `${CLAUDE_PLUGIN_DATA}` — a persistent data directory that survives plugin
  updates. Use this for any plugin-level state that must survive across plugin
  version upgrades (e.g., a global project registry, cached font assets shared
  across projects). Do NOT use this for per-project data; per-project data lives
  in the project directory.

---

# PART II — BEHAVIORAL REQUIREMENTS

## 11. Domain Glossary

| Term | Definition |
|------|------------|
| Archetype | A pre-configured starting template selected at `debrief new` time. Sets the presentation type, default content signals, time constraint, expected deliverables, and rhetorical emphasis. The user can override any default during discovery. |
| Slide | A single self-contained HTML file representing one presentation unit |
| Deck | The ordered collection of approved slides for one project |
| Style config | A locked JSON file defining all visual properties: fonts, colors, spacing, layout grammar |
| Style guide | A human-readable markdown document capturing design rationale, injected into agent prompts alongside the style config |
| Slug | The stable human-readable label assigned to a slide at creation time (e.g., `intro`, `pipeline`, `oracle`) |
| Deck brief | The consultant's living document capturing the narrative arc of the deck |
| Slide record | The structured description of an approved slide: content, visuals, goal, forks not taken, design invariants, human recommendations |
| Slide group | One or more slides that form a thematic unit, defined by the Consultant and produced together in a single group cycle |
| View | An ephemeral HTML file tiling selected slides for visual inspection, generated by `/debrief:view` |
| Separator slide | A minimal styled slide inserted between the presentation section and the Q&A bank at export time |
| Ledger | The JSONL file recording the consultant's conversation history, compactable by summary |
| Active presentation record | During export, the record matching the target folder name. At all other times, the last entry in the `presentations` array in `deck_state.json`. |
| Red-green cycle | The autonomous machine-driven QA loop (generate, screenshot, check, fix, re-check) that eliminates mechanical visual defects before the user sees a slide |
| Pipeline control state | `debrief_state.json` — tracks where the workflow is (phase, sub-phase, active agent, current group/slide) |
| Visual pattern | A named entry from the style guide's Visual Patterns Catalog (e.g., 'Title Slide', 'Key Takeaway'). Used by the Slide Maker as structural guidance when generating slides; the pattern catalog lives in `style_guide.md` (REQ-STYLE-7), not in an external file. |
| Visual approach | Freeform text describing the visual strategy for a specific slide (e.g., 'diagram on the left, 3 bullet points on the right'). Both visual pattern and visual approach are included in slide briefs. |
| Session | One run of the `debrief` CLI from start to exit. |
| Turn | One user message followed by the system's complete response. |
| Agent invocation | One call to a named agent within a turn, using a prepared task prompt. |
| Derived style guide | A markdown ruleset produced by `debrief.style_analyzer` from a user-provided reference file (any of `.pptx`/`.pdf`/`.html`/html_dir). Lives at `.debrief/draft/derived_style_guide.md` during Phase 1/2 and is consumed by the Stylist during the style dialog (REQ-CONSULT-13, REQ-STYLE-2, REQ-STYLE-7). |
| Bundled reference | A markdown documentation file at `${CLAUDE_PLUGIN_ROOT}/references/` that provides craft-knowledge input to the Stylist and visual QA agent. The v1.1 set includes two distilled PaperBanana style guides, an AI4VIS survey distillation, a QA checklist, a preview placeholder content catalog, and a `VERSIONS.md` provenance tracker. See Section 24.39. |
| Provenance | A top-level object in `style_config.json` recording the source of each resolved style decision (one of `user_dialog`, `reference_baseline`, `reference_inspiration`, `bundled_reference`, `default`, with an optional `override_note`). Read by the visual QA agent to explain choices in its output. See Section 24.16 and REQ-STYLE-7. |
| Preview slide | A transient HTML placeholder slide rendered during the Phase 2 style dialog so the user can see the draft style applied before approving at G2.1. Lives under `.debrief/draft/preview_slides/` (HTML) and `.debrief/draft/preview_images/` (PNG). Not a real deck slide and not subject to Section 16 invariant checks. See REQ-STYLE-10 and Section 24.40. |

---

## 12. System Actors

| Actor | Role |
|-------|------|
| Domain expert | The single user. Describes intent, approves output, provides feedback. |
| Consultant agent | Conducts Socratic dialog to produce the deck brief and dispatch slide briefs. Top-down orchestrator of narrative. |
| Slide agent (Slide Maker) | Generates and revises styled HTML slides from briefs. Bottom-up detail executor. |
| Visual QA agent | Screenshots slides and checks all design invariants. |
| Bug diagnostic agent | Investigates rendering failures and authoring errors. |
| Launcher script | CLI entry point (`debrief`); handles new-project and resume flows. |
| Style compiler | Python module that compiles `style_config.json` to `style.css`. |
| Export module | Python module that renders all slides to a versioned PDF using Playwright. |
| Routing script | Python module (`debrief.routing`) that reads pipeline state and outputs deterministic action blocks. |

The Slide Maker agent is identified as `slide-maker` in agent definitions and `slide_maker` in state/routing identifiers.

---

## 13. Happy Path

**Phase 1 — Discovery:**

1. User navigates to an empty directory and runs `debrief new`. The launcher presents the archetype selection prompt. The user selects an archetype (or "Custom").
2. The launcher creates the project structure, writes initial `deck_state.json` and `debrief_state.json`, generates `CLAUDE.md`.
3. The Consultant greets the user with the archetype context pre-loaded (if not Custom) and begins a focused discovery dialog — confirming defaults and asking for the specific topic, audience, and key messages.
4. Based on the user's description, the Consultant asks progressive disclosure questions about content types (code, math, diagrams, plots, columns) — only those triggered by the user's description.
5. The Consultant produces `deck_brief.md` with a Content Signals section.

**Phase 2 — Style Definition:**

6. The Consultant announces the brief is ready and invokes the Stylist (`/debrief:style`).
7. The Stylist reads `deck_brief.md`, the bundled reference documentation, and (if the user imported a reference at G1.2) the derived style guide; conducts the style dialog; produces draft `style_config.json` and `style_guide.md` in `.debrief/draft/`; renders 3 preview slides using the draft style; and presents them at G2.1 alongside the written design rationale.
8. The user reviews the preview slides and design rationale. If approved, `update_state` promotes the draft files to the project root and locks the style. If the user requests `REGENERATE PREVIEWS`, the Stylist renders different placeholder content and re-presents G2.1 without changing the style. If the user requests `STYLE REVISE`, the draft is discarded and the Stylist iterates.
9. Control returns to the Consultant.

**Phase 3 — Slide Production:**

10. The Consultant proposes the first slide group based on the narrative arc.
11. The Consultant emits `DISPATCH_GROUP` with structured briefs (including `group_id` and `visual_pattern`) and announces the slug(s).
12. The Slide Maker generates each slide and enters the **red-green cycle**: an autonomous machine-driven loop that screenshots, checks Tier 1 invariants, reads structured revision instructions, rewrites, and re-checks — up to 5 iterations — until all mechanical defects are eliminated. The user is not involved in this loop.
13. The Slide Maker presents the mechanically-clean slide to the user with any Tier 2 warnings.
14. The user reviews: requesting detail changes (the Slide Maker revises, re-enters red-green), invoking `/debrief:view` to inspect in the browser (context-aware dispatch), or approving.
15. On `GROUP_APPROVED`, control returns to the Consultant.
16. The Consultant asks: "Is this the last slide, or do we need more?"
17. If more, repeat from step 10. If last, the system opens the full deck
    storyboard and asks how the presentation should end: as-is, with a new
    closing slide, or with an auto-generated empty closing slide (G3.6).
18. Once the ending is resolved, proceed to Phase 4.

**Phase 4 — Finalization:**

19. The Consultant confirms the user is ready to export (G4.1).
20. The Consultant asks: "Are there backup slides for Q&A?" (G4.2)
21. If yes, backup slide production loop (same as steps 10-17, tagged as backup).
    The backup slides are the final pages of the exported PDF — the last backup
    slide is the very last page of the presentation.
22. When backup is complete (or skipped), the Consultant invokes `/debrief:export`.
23. The export ordering dialog confirms slide sequence, separator position,
    separator content, and presentation folder name (G4.4).
24. The PDF is rendered. The page order is: main slides → closing slide (if any)
    → separator (if any) → backup slides (if any) (see Section 24.10 for canonical specification). Optionally, the user invokes
    `/debrief:script`.
25. The project reaches `complete`. It can be reopened at a future date for
    updates (see Section 14.12).

**Invariant:** The style dialog (`/debrief:style`) MUST NOT run before the deck
brief exists. The style agent requires the deck brief to make content-informed
style recommendations.

### 13.1 Dispatch Event Table

**Note:** The `From` and `To` columns describe *logical* context transitions in narrative form. The consultant handles all control transfer via Tool calls. *(BUG-AUDIT-31: the routing loop (`update_state` + routing cycle) is dead at runtime; the consultant agent handles all dispatch directly.)* No agent invokes another agent directly (REQ-ROUTE-1 prohibits agent-to-agent invocation via the Agent tool). The operational triggers for each event are the gate responses in Section 14.16 and the transition rules in Section 14.17. This table is a narrative overview, not a contract.

| Event | From | To | Trigger Condition | State Change |
|-------|------|----|-------------------|--------------|
| `STYLE_NEEDED` | Consultant | Stylist (via `/debrief:style`) | `deck_brief.md` complete with Content Signals | Phase 1 to Phase 2 |
| `STYLE_LOCKED` | Stylist | Consultant | `style_locked: true` in `deck_state.json` | Phase 2 to Phase 3 |
| `DISPATCH_GROUP` | Consultant | Slide Maker | Consultant has produced structured brief(s) | Consultant context to Slide Maker context |
| `REVISION_REQUEST` | User | Slide Maker | User asks for detail changes | (triggered by G3.3 `SLIDE REVISE`; stays in Slide Maker context; re-enters red-green) |
| `DETAIL_FIX` | User (via `/debrief:view`) | Slide Maker | User requests detail fix after visual inspection, while in Consultant context | Consultant context to Slide Maker context |
| `ESCALATE_TO_CONSULTANT` | User (via `/debrief:view`) | Consultant | User requests structural change after visual inspection, while in Slide Maker context | Slide Maker context to Consultant context |
| `GROUP_APPROVED` | User | Consultant | User approves all slides in group | Slide Maker context to Consultant context |
| `MORE_SLIDES` | User | Consultant | User confirms more slides needed | (stays in Phase 3, new group cycle) |
| `LAST_SLIDE` | User | Consultant | User confirms no more main slides | Phase 3 → G3.6 (deck ending review) |
| `DECK_ENDING_RESOLVED` | User | Consultant | User decides how the deck ends (G3.6) | G3.6 → Phase 4 (finalization), or back to group planning for a closing slide |
| `BACKUP_NEEDED` | User | Consultant | User confirms backup slides needed | (triggered by G4.2 `BACKUP YES`; Phase 4 enters backup production loop) |
| `BACKUP_COMPLETE` | User | Consultant | User confirms no more backup slides | (triggered by G4.3 `LAST BACKUP`; backup loop to Export) |
| `DECK_COMPLETE` | Consultant | Export | All slides (main + backup) done | (triggered by G4.4 `EXPORT NOW`; Phase 4 to Export flow) |
| `DIAGNOSTIC_REQUESTED` | `debrief.routing` | Bug diagnostic agent | `sub_phase == production/diagnostic` (set by `update_state` after G3.2 EXHAUSTED) | Slide Maker context to bug-diagnostic context; exits on diagnostic report write, transitions to `production/slide_review` with `pending_gate: G3.3_slide_review_post_diagnostic` |

---

## 14. Functional Requirements

### 14.1 Project Initialization (`debrief new`)

- **REQ-INIT-1:** The launcher MUST create the project directory structure as
  specified in Section 3, including `assets/images/` and `.debrief/`. The current directory MUST be empty or contain only
  `CLAUDE.md` (from a prior reset). If the directory contains other files, the
  launcher MUST print an error and exit without creating any files.
- **REQ-INIT-2:** The launcher MUST write an initial `deck_state.json` with all
  top-level fields initialized as follows (see Section 17.1 for the complete schema):
  ```json
  {
    "project_name": "<directory-name>",
    "created_at": "<ISO8601>",
    "archetype": "<archetype_value>",
    "style_locked": false,
    "closing_slide": null,
    "slides": [],
    "presentations": []
  }
  ```
- **REQ-INIT-3:** The launcher MUST generate the project `CLAUDE.md` by rendering the plugin-scaffold template at `${CLAUDE_PLUGIN_ROOT}/templates/project_claude.md` into the project directory. This template is a plugin-scaffold artifact committed to the plugin repository alongside `plugin.json` — it is owned by the scaffold, NOT by the agent definitions. The launcher performs any necessary placeholder substitution (e.g., project name) during rendering. The rendered file is not user-editable and is not deleted by `/debrief:restore`. *(BUG-AUDIT-22: `/debrief:restore` does not delete `CLAUDE.md` or any file outside `deck_state.json` and orphan slides.)* See Section 24.7 for the component-placement rule.
- **REQ-INIT-4:** If a `deck_state.json` already exists in the directory, the
  launcher MUST resume the existing project rather than reinitializing.
- **REQ-INIT-5:** The launcher MUST perform pre-flight checks in this order. The checks are split between the `bin/debrief` bash wrapper (steps that MUST run before any Python invocation, because the conda env does not yet exist) and `debrief.launcher` (steps that run after env activation, callable via `python -m debrief.launcher preflight`). The definitive implementation contract for both halves is Section 24.4.

  **Bash wrapper half (runs before any Python):**
  1. **Conda availability:** verify `conda --version` returns successfully. If not, print: `ERROR: Debrief requires miniconda or mambaforge. Install from https://docs.conda.io/en/latest/miniconda.html and retry.` Exit with code 1.
  2. **Source conda:** enable `conda activate` in the script via `source "$(conda info --base)/etc/profile.d/conda.sh"`.
  3. **Conda env existence:** check if the `debrief` env exists. If not, create it from `${CLAUDE_PLUGIN_ROOT}/environment.yml`. On `conda env create` failure, run `conda env remove -n debrief -y` to clean up any partial env before exiting.
  4. **Env activation:** `conda activate debrief`.
  5. **Post-activation smoke test:** run `python -c 'import playwright; import pptx; import fitz; import json_repair'`. On ImportError, emit the Section 9.3.1 env-corruption error and exit with code 2 recommending `debrief --rebuild-env`.

  **Python half (runs after env activation, via `python -m debrief.launcher preflight`):**
  6. **Package install marker:** check for `${HOME}/.cache/debrief/pkg_version_<plugin_version>.marker`. If missing, run `pip install -e ${CLAUDE_PLUGIN_ROOT}` inside the env; write the marker only on exit code 0.
  7. **Chromium install marker:** check for `${CONDA_PREFIX}/.debrief_chromium_installed`. If missing, run `python -m playwright install chromium` inside the env; write the marker only on exit code 0.
  8. **Vendor hash verification:** run `debrief.launcher.verify_vendor_hashes()` per Section 24.27. A hash mismatch exits with code 1 before touching project files, with a recovery instruction pointing to plugin reinstall (NOT `--rebuild-env`).

  Note: steps 6 and 7 are sometimes listed as bash-wrapper steps because their commands are simple enough to run from bash. Either implementation is acceptable provided the gating marker logic is identical.

  Python 3.11+, Node.js, and all Python/system dependencies are NOT checked individually — they are guaranteed by the conda environment. `conda` is the only top-level requirement.
- **REQ-INIT-6:** The launcher MUST write an initial `debrief_state.json` conforming to the schema in Section 17.5. Initial values: `phase: "discovery"`, `sub_phase: "greeting"`, `active_agent: "consultant"`, `archetype: <selected_at_init>`, `session_started_at: <current ISO8601 timestamp>`, `state_hash: <computed SHA-256>`, `red_green_iteration: 0`, `red_green_started_at: null`, and all other fields at their schema defaults (null, false, empty arrays, 0, as applicable per Section 17.5).
- **REQ-INIT-7:** The `debrief new` command MUST present an archetype selection prompt before creating the project. The prompt lists the available archetypes:

  ```
  Welcome to Debrief. What are you preparing?

    1. Lab meeting talk
    2. Conference presentation
    3. Seminar
    4. Lecture
    5. Journal club
    6. Grant panel / interview
    7. Job talk
    8. Custom (start from scratch)
  ```

  The user selects by number or name. The selection is recorded in `deck_state.json` as `"archetype"` and in `debrief_state.json`. The archetype pre-configures the presentation type, default content signals, time constraint, expected deliverables, and rhetorical emphasis. Option 8 ("Custom") sets `archetype: "custom"` and defers all configuration to the Consultant's discovery dialog.

  Alternatively, the archetype may be specified as a CLI argument: `debrief new --archetype lab_meeting`. If provided, the interactive prompt is skipped.

#### 14.1.1 Archetype Definitions

Each archetype pre-configures a set of defaults that the Consultant uses as the starting point for the discovery dialog. The user can override any default during discovery — archetypes are starting points, not constraints.

| Archetype | `archetype` value | Presentation Type | Time Default | Key Defaults |
|-----------|-------------------|-------------------|-------------|-------------|
| Lab meeting talk | `lab_meeting` | `findings_report` | 20 min | Diagrams likely, data-heavy, no handout expected. Rhetorical emphasis: logos (data) + hook. |
| Conference presentation | `conference_talk` | `findings_report` | 12 min | Tight time constraint, marketing + rigor, one-idea-per-slide strict. Rhetorical emphasis: hook + logos + pathos (significance). |
| Seminar | `seminar` | `findings_report` | 50 min | Deeper background, more slides, handout optional. Rhetorical emphasis: logos + ethos. |
| Lecture | `lecture` | `teaching` | 50 min | Dense content OK, recap slides, handout likely. Rhetorical emphasis: logos (teaching) + recap. |
| Journal club | `journal_club` | `journal_club` | 45 min | Expects paper PDFs. Figure-driven. Connective tissue generated. Rhetorical emphasis: logos + critique. |
| Grant panel / interview | `grant_panel` | `interview_grant` | 12 min | Persuasion-first, vision + impact, "so what?" framing. Rhetorical emphasis: ethos + pathos + logos. |
| Job talk | `job_talk` | `interview_grant` | 50 min | Blend of findings + vision, broad audience (not all domain experts). Rhetorical emphasis: all four devices balanced. |
| Custom | `custom` | (user-defined) | (user-defined) | No pre-configuration. Full discovery dialog. |

### 14.2 Consultant Agent

- **REQ-CONSULT-1:** The consultant MUST conduct a Socratic dialog with the user to
  elicit the presentation's purpose, audience, key messages, and narrative arc.

  When an archetype other than `custom` is selected, the Consultant MUST greet the user with the archetype context already loaded: "I see you're preparing a [archetype name]. I've set up for a [time]-minute [presentation type] presentation. What's the topic?" The discovery dialog becomes a **confirmation and refinement** pass — the Consultant confirms the pre-filled defaults and asks only for information not provided by the archetype (e.g., the specific topic, audience details, key messages). The Consultant MUST NOT re-ask questions whose answers are implied by the archetype.

  **Timing note (BUG-AUDIT-11):** Claude Code agents do not emit messages before receiving any user input — the consultant cannot "speak first" literally on session open. The greeting above therefore fires on the consultant's **first response to the user's first message**, which may be nothing more than "hi" or "start". The triggering mechanism is the project-level `CLAUDE.md` (rendered from `${CLAUDE_PLUGIN_ROOT}/templates/project_claude.md` per REQ-INIT-3) whose `## On Session Start` section instructs the consultant to read `debrief_state.json` / `deck_state.json` and dispatch based on the current `sub_phase`. The `bin/debrief` bash launcher prints a terminal message "Debrief ready. When Claude Code opens, say 'hi' to begin." before `exec claude` to cue the user. The consultant MUST interpret an initial "hi" / "start" / "begin" / short greeting as a request to dispatch per the state-file contents, not as a generic greeting. See BUG-AUDIT-11 for full background.
- **REQ-CONSULT-2:** The consultant MUST produce and maintain `deck_brief.md` as a
  living document. It must be updated after any turn in which the user provides
  new information about the deck's purpose, audience, structure, or content
  direction, or in which a slide is approved, reordered, deleted, or replaced.
- **REQ-CONSULT-3:** The consultant MUST record its conversation in `ledger.jsonl`.
  The ledger is append-only; each entry is a JSON object on a single line. Each ledger entry MUST conform to the schema: `{"timestamp": "ISO8601", "role": "user|consultant|system", "content": "string", "metadata": {"group_id": "string|null", "slug": "string|null", "event": "string|null"}}`. The `role` field distinguishes user messages, consultant responses, and system events (group approved, style locked, etc.). The `metadata` object is optional; its fields are all optional.
- **REQ-CONSULT-4:** The consultant MUST handle ledger compaction. When the ledger is
  compacted (by the blueprint author's chosen trigger), the consultant MUST
  reconstruct sufficient context from the deck brief and slide records to continue
  coherently. The exact compaction trigger condition (entry count, token estimate,
  etc.) is a blueprint decision.
- **REQ-CONSULT-5:** The consultant MUST dispatch a structured slide brief to the
  slide agent for each slide. The brief MUST include: slug, title, content goal,
  visual approach, visual pattern (from the style guide catalog), design invariants to enforce, and any user recommendations from
  prior turns. The consultant MUST print the slug to the session as a clearly
  labeled line (e.g., `Slug: pipeline`) before dispatching each brief, so the
  user can invoke `/debrief:slide [slug]` for revisions. Briefs are written as JSON files to `.debrief/briefs/<group_id>_<slug>.json`. The schema is: `{"slug": "string", "title": "string", "content_goal": "string", "visual_approach": "string", "visual_pattern": "string", "rhetorical_role": "string", "design_invariants": ["string"], "user_recommendations": "string", "group_id": "string"}`. The `rhetorical_role` field indicates the slide's rhetorical function per REQ-CONSULT-15. Valid values: `hook`, `ethos`, `pathos`, `logos`, `synthesis`, `recap`, `transition`.
- **REQ-CONSULT-6:** The consultant MUST **provide** the slide approval data (slug, title, content summary, visual approach, design choices, forks not taken, user recommendations) when a slide is approved. The `update_state` script writes this data to `deck_state.json`. The consultant does not write to `deck_state.json` directly.
- **REQ-CONSULT-7:** The Consultant MUST use progressive disclosure for style-relevant questions. Each question is gated by a trigger condition in the user's prior description. The Consultant MUST NOT present a checklist of all content types unprompted. Questions must feel like natural follow-ups, not an intake form. Trigger conditions include:
  - If the user mentions code, algorithms, or technical implementation: "Will you need to show source code on slides?"
  - If the user mentions formulas, equations, mathematical notation, or theoretical derivations: "Will you need mathematical formulas on slides? If so, I'll make sure the style handles them well."
  - If the user mentions data, metrics, or measurements: "Will you need graphs or plots?"
  - If the user mentions processes, flows, or architectures: "Will you need diagrams?"
  - If the user mentions comparisons, pros/cons, or alternatives: "Do you want bullet-point lists or side-by-side columns?"
  - If the user mentions dense explanations or long-form reasoning: "Should text be laid out in columns?"
  - If the user mentions an existing deck, corporate style, brand guidelines, or a previous presentation: "Do you have an existing PowerPoint deck whose visual style you'd like me to match? If so, just give me the file path."
  - If the user mentions journal club, paper presentation, presenting a paper, or reviewing published work: "Which paper(s) would you like to present? Give me the file path(s)."
- **REQ-CONSULT-8:** The `deck_brief.md` MUST include a `## Content Signals` section that records the content-type findings AND the presentation type from the discovery dialog. Content signals include: `code: yes/no`, `math: yes/no`, `diagrams: yes/no`, etc. The presentation type is one of:

  - `teaching` — lecture, seminar, or tutorial. Dense content acceptable. Repetition and summary slides encouraged. Handout deliverable may be requested.
  - `findings_report` — conference talk, lab meeting, or seminar presenting original research. Time-constrained. Must balance marketing (this is important/novel) with rigor (here's the data/statistics/limitations).
  - `interview_grant` — job talk, grant panel, or selection committee. Persuasion-first. Vision slides, "so what?" framing, ethos-dominant.
  - `journal_club` — presenting other researchers' published work. Paper-driven, not user-driven. Figures extracted from source PDFs. Connective tissue generated by the Consultant.

  The Consultant infers the type from the discovery dialog and records it. The user can correct it at brief review (G1.1). This section is read by the Stylist to inform style recommendations.

  When an archetype is selected, the Content Signals section is pre-filled with the archetype's defaults. The Consultant updates it during discovery as the user confirms or overrides defaults.
- **REQ-CONSULT-9:** After each group is approved, the Consultant MUST ask the user whether more slides are needed. The Consultant MUST NOT assume the deck is complete until the user explicitly confirms.
- **REQ-CONSULT-10:** The Consultant MUST propose slides in groups. A group is one or more slides that form a thematic unit (e.g., "the three methodology slides" or "the title slide"). The Consultant determines group boundaries based on the narrative arc. The user may request splitting or merging groups.
- **REQ-CONSULT-11:** After the user confirms the last main slide, the Consultant MUST ask about the export format and whether backup/Q&A slides are needed before proceeding to export.
- **REQ-CONSULT-12:** Backup slides MUST be produced using the same group cycle as main slides (Phase 3). The Consultant MUST tag backup slide briefs with `"backup": true`. Backup slides are placed after the separator position in the deck order.

- **REQ-CONSULT-13:** If the user provides a reference file during discovery
  (any of `.pptx`, `.pdf`, `.html`, or a directory of `.html` files), the
  Consultant MUST invoke the reference style analyzer module
  (`debrief.style_analyzer`) to derive a draft style guide from the reference.
  The analyzer uses a unified pipeline:

  1. **Modality adapter.** Convert the reference to a standardized image batch:
     - `.pptx` → LibreOffice headless → one PNG per slide (see Section 24.25); cap at 10 slides (first, last, and 8 representative slides sampled uniformly from the middle).
     - `.pdf` → PyMuPDF (`fitz.Page.get_pixmap()`) → one PNG per page at 150 DPI; cap at 10 pages (same sampling rule). If the PDF is longer than 50 pages the analyzer treats it as a paper-style document and surfaces a warning in the G1.2 gate prompt.
     - `.html` single file → Playwright → one PNG of the rendered page at 1920×1080.
     - `.html` directory → Playwright → one PNG per HTML file, up to 10 files (alphabetical order, first + last + 8 middle).
  2. **Optional structured metadata extraction** (PPT only). If the reference is `.pptx`, also run `python-pptx` to extract exact theme colors (hex), font families, font sizes, slide dimensions, and any embedded theme XML. This metadata is passed to the VLM as additional context in step 3 to anchor its natural-language observations to exact values. For `.pdf` and `.html` references, no structured metadata extraction is performed; the VLM eyeballs colors and fonts from the rendered images.
  3. **VLM-based style derivation.** The analyzer does NOT call a VLM itself. It writes the image batch to `assets/reference/slides/` and (for PPTX only) the extracted metadata to `.debrief/draft/analyzer_metadata.json`, then exits. The actual derivation happens when the Stylist agent is invoked: the Stylist reads the image batch directly (using its Read tool), applies the anti-prescriptive meta-prompt pattern from the bundled references at `${CLAUDE_PLUGIN_ROOT}/references/`, and writes `.debrief/draft/derived_style_guide.md`. See Section 24.25.4 for the full flow. This design avoids introducing a VLM SDK user-facing prerequisite (conflicts with Section 9.1). *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*
  4. **Output artifact.** The analyzer writes its output to `.debrief/draft/derived_style_guide.md` — a full markdown style guide in the same format as the final project `style_guide.md` (REQ-STYLE-7), with sections for color rationale, typography rationale, layout grammar, diagram conventions, visual patterns catalog, and anti-patterns. The draft is NOT a two-section natural-language impression; it is a complete ruleset that could, in principle, be used as-is (under BASELINE mode with no user changes).
  5. **Reference archival.** The imported reference file is copied to `assets/reference/<filename>` and the extracted image batch is saved to `assets/reference/slides/` for traceability. These are read-only project artifacts.

  The analyzer runs exactly once per reference, at the moment the user provides the reference path during discovery. It does NOT re-run at G1.1 BRIEF APPROVED or any later transition. The derived style guide is cached in `.debrief/draft/derived_style_guide.md` and referenced by later phases. If the reference file type is not one of the supported extensions, the Consultant surfaces an error ("Unsupported reference file type: <ext>. Supported: .pptx, .pdf, .html, or a directory of .html files") and asks the user to provide a different reference or skip the import.

  The `debrief.style_analyzer` module imports `python-pptx`, `fitz`, and `playwright` in-process; if any import fails at invocation time, the analyzer treats this as conda env corruption and reports the standardized env-corruption error per Section 9.3.1 (exit code 2, recovery via `debrief --rebuild-env`). For modality-specific adapter details (LibreOffice headless for PPT, PyMuPDF for PDF, Playwright for HTML), see Section 24.25.
- **REQ-CONSULT-14:** After the reference style analysis is complete, the
  Consultant MUST present a summary of the derived style to the user and ask a
  scripted question (gate G1.2):

  > "I've analyzed the reference you provided ({reference_filename}, {reference_modality}). Here is the derived style guide:
  >
  > {derived_style_guide_summary}
  >
  > Here are thumbnails of the reference pages I analyzed:
  >
  > {reference_thumbnail_links}
  >
  > How would you like to use this?
  > - **USE AS BASELINE** — Adopt this as the starting style; you can still adjust anything in the style dialog.
  > - **USE FOR INSPIRATION** — Keep it as a reference, but I'll build the style from scratch with this as context.
  > - **IGNORE** — Discard the analysis and define the style from scratch."

  The response is recorded in `debrief_state.json` as
  `style_import_mode: "baseline" | "inspiration" | null` (null on IGNORE). The
  Stylist's reading of `derived_style_guide.md` is determined by this mode per
  REQ-STYLE-2 and REQ-STYLE-7.

  If the reference is a PDF that appears to be a paper rather than a slide deck (detected heuristically: PDF has >5 pages with typical paper layout — single column main body, bibliography section, figure captions), the gate prompt adds a warning line: *"Note: the reference looks like a paper, not a slide deck. The derived style captures the paper's visual conventions but may need adjustment for slide format."*
- **REQ-CONSULT-15:** The Consultant MUST structure the narrative arc using rhetorical devices appropriate to the presentation type. Each slide brief MUST include a `rhetorical_role` field indicating the slide's rhetorical function. The Consultant applies the following framework:

  | Device | Description | Applies to |
  |--------|-------------|-----------|
  | **Hook** | Opening that grabs attention — a clinical case, a striking statistic, a provocative question. First content slide after the title. | All types |
  | **Ethos** | Credibility signals — methodology rigor, prior work, institutional context, team expertise. | Findings report, interview/grant |
  | **Pathos** | Emotional connection — patient stories, clinical significance, "why this matters to real people." | Interview/grant (dominant), findings report (opening/closing) |
  | **Logos** | Logical argument — data, statistical evidence, logical progression, evidence chain. | Findings report (dominant), teaching (dominant) |

  The `rhetorical_role` values are: `hook`, `ethos`, `pathos`, `logos`, `synthesis` (combining multiple), `recap`, `transition`. The Slide Maker uses this to adjust visual emphasis — a pathos slide may use a full-bleed image; a logos slide uses a clean data exhibit.
- **REQ-CONSULT-16:** The Consultant MUST ask about the allocated time for the presentation during discovery. From the time constraint, the Consultant derives:
  - Approximate slide count (guideline: 1-2 minutes per slide, adjusted by presentation type — teaching is denser, interview is sparser)
  - Maximum content density per slide
  - Whether a questions/discussion section is needed within the allocated time

  The time is recorded in `deck_brief.md` Content Signals as `allocated_time: "<N>min"`. The Consultant uses it to constrain the narrative arc — proposing fewer, punchier groups for short talks and more detailed groups for longer ones.
- **REQ-CONSULT-17:** If the user provides one or more academic paper PDFs during discovery (for journal club presentations), the Consultant MUST invoke the paper analyzer module (`debrief.paper_analyzer`) to extract content from each PDF. The extraction pipeline:

  1. **Parse the PDF** — extract full text, section structure, figure captions, and figure images (using PyMuPDF (imported as `fitz`)).
  2. **Identify key figures** — match figure references in text to extracted images. Rank by citation frequency and section location (results figures > supplementary figures).
  3. **Extract claims** — for each key figure, extract the main finding/claim from the surrounding text and caption.
  4. **Reformat figures** — crop whitespace from extracted figure images, save to `assets/reference/papers/<paper_slug>/figures/fig_<N>.png`. These are raster images at the source PDF's resolution.

  The module writes its output to `.debrief/paper_analysis_<paper_slug>.md` — a structured document with: paper metadata (title, authors, journal, year), key figures with captions and claims, and a suggested narrative arc.

  The imported PDFs are copied to `assets/reference/papers/<paper_slug>/`.

  The paper analyzer imports PyMuPDF in-process via `import fitz`. The Consultant agent does not import PyMuPDF directly — it invokes `python -m debrief.paper_analyzer` via Bash, which handles all PDF operations internally. PyMuPDF is the only supported PDF library for journal club extraction; alternative libraries are not permitted, to ensure reproducibility across deployments.

  `python-pptx` and `PyMuPDF` (imported as `fitz`) are both guaranteed by the `debrief` conda env via `environment.yml` (see Section 9.3.1). They are always available under normal operation. The paper analyzer imports `fitz` directly; if the import fails, this indicates conda env corruption and the analyzer reports the standardized env-corruption error per Section 9.3.1 (exit code 2, recovery via `debrief --rebuild-env`).

  **Paper slug derivation.** The paper slug is derived from the PDF filename by: (1) stripping the `.pdf` extension, (2) applying the Debrief Identifier Sanitization Algorithm (Section 24.10.1) with `max_length=50`. Example: `Nature_2024_Smith_et_al.pdf` → `nature_2024_smith_et_al`. The slug is used in: `.debrief/paper_analysis_<paper_slug>.md`, `assets/reference/papers/<paper_slug>/`, and all G1.3 placeholders. If the user provides multiple papers, each gets its own slug derived independently.

  The paper analyzer runs exactly once per paper, at the moment the user provides the paper path during discovery. It does NOT re-run at G1.1 BRIEF APPROVED or any later transition. The results (extracted figures, claims, narrative arc) are cached in `.debrief/paper_analysis_<paper_slug>.md` and referenced by later phases.
- **REQ-CONSULT-18:** For journal club presentations, the Consultant MUST build the narrative arc around the extracted figures and claims, generating connective tissue between them. The Consultant proposes slide groups structured as:
  - **Context slides** — background the paper assumes but the audience needs
  - **Figure slides** — each key figure as a standalone image slide (REQ-ASSET-4) or embedded in a multi-element slide, with the extracted claim as the key message
  - **Critique/discussion slides** — the presenter's interpretation, limitations, connections to other work

  Every slide that uses an extracted figure MUST include a citation line: "Figure from [Authors], [Year], [Journal]" — styled per the style guide and positioned as a caption, not body text.

  The Consultant presents the extracted figures as a numbered list in `.debrief/paper_analysis_<paper_slug>.md` (one line per figure with `<N>. <caption>` format). Gate G1.3 prompts the user with this list and accepts either `ALL` or a space-separated list of figure numbers. The user's selection is written directly to `debrief_state.json.selected_figures` (durable field per Section 17.5 and P-BP-13; not ephemeral `gate_data.json`). The Consultant reads this field when planning slide groups. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*

  When `archetype` is `journal_club`, the Consultant MUST ask for paper PDFs as its first question, without waiting for a trigger: "Which paper(s) would you like to present? Give me the file path(s)." This overrides the normal progressive disclosure gate for the journal club trigger.

  When `archetype` is `lecture`, the Consultant MUST proactively mention the handout option during discovery: "Since this is a lecture, would you like me to generate a handout for the students? I can do 2-up (slides + detailed notes) or 4-up (compact reference)." The response is recorded in the brief.

### 14.3 Style Dialog (`/debrief:style`)

**Layered synthesis model.** `style_guide.md` is synthesized by layering four sources in strict precedence order (see REQ-STYLE-7): the user's explicit dialog choices (highest), the reference-derived draft style guide under `USE AS BASELINE` mode (if the user provided a reference file during discovery), bundled reference craft knowledge at `${CLAUDE_PLUGIN_ROOT}/references/`, and the Stylist's defaults (lowest). Reference import and bundled references operate on mostly orthogonal dimensions — reference import provides project-specific values (exact colors, fonts, layout grammar, extracted from the user's `.pptx`/`.pdf`/`.html` reference via `debrief.style_analyzer`, see Section 24.25) while the bundled references provide domain-agnostic craft knowledge (connector semantics, colormap conventions, typography principles, veto rules, QA checklists). Where they DO conflict on the same dimension, the reference-derived value (under BASELINE mode) takes precedence, the conflict is surfaced to the user in the style dialog, and the outcome is recorded in `style_config.json` under a `provenance` field so downstream QA can explain every choice. If the user provides no reference, the bundled references are the only craft-knowledge input and the style dialog proceeds normally with defaults filled from those references.

- **REQ-STYLE-1:** The style skill MUST check preconditions before yielding:

  1. If `deck_brief.md` does not exist or is empty, print `The consultant must produce the deck brief before defining the style. Continue the discovery dialog first.` and exit without modifying state.
  2. If `style_locked` is `true` in `deck_state.json`, print `Style is already locked. To change the style, run 'debrief new' to start a new project.` and exit without modifying state. *(BUG-AUDIT-22: changed guidance from `/debrief:reset` to `debrief new` — restore does not start new projects.)*
  3. If both preconditions pass, the skill yields to routing as described in Section 24.19.
- **REQ-STYLE-2:** Before beginning the style dialog, the Stylist MUST read, in
  this order:
  1. `deck_brief.md` for content direction.
  2. The bundled reference documentation at
     `${CLAUDE_PLUGIN_ROOT}/references/paperbanana-diagram-style-distilled.md`,
     `paperbanana-plot-style-distilled.md`, and `ai4vis-survey-distilled.md`
     for craft-knowledge baseline (Section 24.39).
  3. **Reference-derivation mode:** if `reference_provided=true` in
     `debrief_state.json` AND `.debrief/draft/derived_style_guide.md` does
     NOT yet exist, the Stylist is in reference-derivation mode. It MUST
     read `${CLAUDE_PLUGIN_ROOT}/references/paperbanana-derivation-meta-prompt.md`
     (the anti-prescriptive meta-prompt adapted from PaperBanana's
     `generate_category_style_guide.py`) for instructions on how to analyze
     the reference image batch. It then reads every image in
     `assets/reference/slides/*.png` (and `.debrief/draft/analyzer_metadata.json`
     if `reference_modality == "pptx"`), applies the meta-prompt instructions,
     and writes `.debrief/draft/derived_style_guide.md` per Debrief's
     REQ-STYLE-7 output schema. See Section 24.25.4 for the full contract.
  4. If `style_import_mode` in `debrief_state.json` is `"baseline"` or
     `"inspiration"`, the reference-derived draft style guide at
     `.debrief/draft/derived_style_guide.md` (produced in step 3 of this
     invocation, or by a prior Stylist invocation if the user is iterating).

  The Stylist applies the precedence rules in REQ-STYLE-7 when these sources
  speak to the same dimension. Under `"baseline"` mode the reference-derived
  draft style guide is the authoritative project baseline — the Stylist
  pre-fills proposed values in the style dialog from it and the dialog focuses
  on refinement. Under `"inspiration"` mode the Stylist reads the derived
  draft as background context and references it when making recommendations,
  but MUST NOT pre-fill values. If `style_import_mode` is `null`, step (3) is
  skipped and the Stylist proceeds with the bundled references as the only
  craft-knowledge input.
- **REQ-STYLE-3:** The style dialog MUST cover: primary and accent colors, font
  family for headings and body, base font size, line height, slide background,
  layout grammar (single-column vs. two-column), permitted diagram libraries
  (a subset of: Mermaid, rough.js, inline SVG — the user selects which are
  allowed for this deck), and spacing scale. The selected permitted libraries are
  stored in `style_config.json` under a `constraints.permitted_diagram_types`
  array.
- **REQ-STYLE-4:** The style dialog MUST produce a `style_config.json` that specifies
  all visual properties. No visual property may remain unspecified after the dialog.
  The Stylist MUST start from the bundled template at
  `${CLAUDE_PLUGIN_ROOT}/templates/style_config.json` and fill in values through the
  dialog, rather than inventing the schema from scratch. The template enumerates all
  seven canonical top-level keys and every mapped CSS dot-path per §24.16.1 so the
  produced config is compiler-compatible by construction. See BUG-AUDIT-13 for the
  historical incident where the Stylist invented an alternative `palette/geometry/components`
  schema and broke `/debrief:export` at BC-10.1's mandatory compiler subprocess.
- **REQ-STYLE-5:** After the user approves the style config, the style compiler MUST
  write `assets/style.css`. The style config MUST then be locked. Locking means
  setting the file read-only (chmod 444) and recording `"style_locked": true` in
  `deck_state.json`.
- **REQ-STYLE-6:** The PreToolUse hook enforces two constraints: before style lock, no writes to `slides/` or `assets/style.css` are permitted (the style must be defined first); after style lock, INV-06 prohibits inline styles that override the locked config.
- **REQ-STYLE-7:** After the user approves the style config, the style skill MUST generate `style_guide.md` — a human-readable markdown document that captures the design rationale behind every choice in `style_config.json`. The style guide MUST include:
  - **Color rationale**: why these colors were chosen, what mood they convey, how primary/accent should be balanced, which color is for emphasis vs. background
  - **Typography rationale**: why these fonts were paired, how heading/body fonts create hierarchy, recommended heading levels per slide type
  - **Layout grammar**: when to use single-column vs. two-column, how to balance text and visual weight, whitespace rhythm expectations
  - **Diagram conventions**: for each permitted diagram library (from `constraints.permitted_diagram_types`), specific guidance on color usage within diagrams, line weights, label placement, and how diagram styling must harmonize with the slide palette
  - **Visual patterns catalog**: 3-5 named slide patterns (e.g., "Title Slide," "Content + Diagram," "Key Takeaway," "Comparison," "Data Exhibit") with natural-language descriptions of how each pattern should look and when to use it
  - **Anti-patterns**: explicit descriptions of visual mistakes to avoid with this specific style (e.g., "do not use the accent color for large background fills — it is designed for small highlights")
  - **Image Placement**: how standalone image slides should be framed (border, shadow, padding), how embedded images should be scaled relative to text columns, caption styling (font, size, color, position below image), and whether images should have rounded corners, drop shadows, or be flush
  - **Math Rendering**: font size for inline math relative to body text, font size for display math, color for math (typically `var(--color-text-primary)`), spacing above and below display math blocks, whether equation numbering is used, and alignment of multi-line equations
  - **Presentation Type Guidance**: conditional recommendations keyed by the presentation type from `deck_brief.md`. For example:
    - *Teaching:* "Dense layouts acceptable. Use definition slides, step-by-step process diagrams, and recap slides. Favor explanatory diagrams with labels over minimal illustrations."
    - *Findings report:* "One key finding per slide. Data exhibits must have clear axes, annotated key values, and statistical annotations. Balance visual marketing with data rigor."
    - *Interview/grant:* "Vision and impact first. Use bold typography for key claims. Include timeline/roadmap slides. Less data density, more 'so what?' framing."
    - *Journal club:* "Extracted figures are the primary content. Frame them with context slides. Annotate figures to highlight the key finding. Always include citation lines."
  - **Symmetry and Visual Balance**: guidance on equal sizing of adjacent elements, alignment rules, symmetric whitespace. "When placing multiple visual elements side by side, they MUST be equal in size unless there is an explicit content reason for asymmetry. A three-panel layout means three equal panels. Adjust content to fit containers, not containers to fit content."
  - **Rhetorical Role Styling**: per-role visual guidance (hook, ethos, pathos, logos, synthesis, recap, transition) describing how each role should look in this specific project's style. The Slide Maker reads this section when generating a slide with a given rhetorical_role.

  The style guide MUST use **anti-prescriptive language** where multiple valid approaches exist. Instead of "always use single-column layout," write "common layout choices include single-column (~60% of slides) and two-column for comparisons (~30%). Use single-column as the default; switch to two-column when comparing two alternatives or showing code alongside output." This gives the Slide Maker informed flexibility rather than rigid rules.

  The style guide MUST be locked alongside `style_config.json`.

  **Bundled reference craft-knowledge input.** The Stylist MUST read the bundled
  reference documentation at
  `${CLAUDE_PLUGIN_ROOT}/references/paperbanana-diagram-style-distilled.md`,
  `paperbanana-plot-style-distilled.md`, and `ai4vis-survey-distilled.md`
  (Section 24.39) as craft-knowledge input when generating the project's
  `style_guide.md`. The project style guide is a project-specific synthesis
  that layers four sources together (see precedence rules below) into a single
  imperative prompt artifact for the Slide Maker. The project style guide is
  NOT a copy of the reference documentation — it is a targeted, content-aware
  synthesis for this specific project's archetype, content signals, and
  imported style (if any).

  **Source-of-truth precedence (highest to lowest).** When synthesizing
  `style_guide.md` and populating `style_config.json`, the Stylist MUST layer
  the following sources in strict precedence order. Higher-precedence sources
  overwrite lower-precedence suggestions on any dimension where they conflict:

  1. **User's explicit style dialog choices** — the user's direct answers in
     the style dialog always win. The user can override anything, including
     reference-derived values.
  2. **Reference-derived draft style guide under `USE AS BASELINE`** — if the
     user provided a reference file (any of `.pptx`, `.pdf`, `.html`, or a
     directory of `.html` files) and selected `USE AS BASELINE` at gate G1.2,
     the derived draft style guide at `.debrief/draft/derived_style_guide.md`
     (produced by `debrief.style_analyzer`, see Section 24.25) is the
     **authoritative project baseline**. The Stylist reads it as the starting
     point for the project's `style_guide.md` and treats its recommendations
     as defaults the user must actively choose to override.
  3. **Reference-derived draft style guide under `USE FOR INSPIRATION`** —
     contextual reference only; the Stylist MUST cite it when recommending
     style choices but MUST NOT pre-fill `style_config.json` with its values.
  4. **Bundled reference craft knowledge** (PaperBanana-distilled + AI4VIS-
     distilled files at `${CLAUDE_PLUGIN_ROOT}/references/`) — domain-agnostic
     craft knowledge (palette conventions, connector semantics, typography
     pairing principles, pitfalls, QA veto rules, academic design principles).
     Used as baseline guidance and to fill gaps where neither the user nor the
     reference-derived draft specifies a value.
  5. **Stylist defaults** — only when no higher-precedence source speaks to a
     given dimension.

  **Conflict disclosure.** When a reference-derived value (under BASELINE
  mode) conflicts with a strong recommendation in the bundled reference
  documentation (e.g., the user's reference deck uses jet colormap, bundled
  references advise against jet), the Stylist MUST surface the conflict
  explicitly during the style dialog as a scripted question:

  > *"The imported reference uses jet colormap for data visualization. The
  > bundled style references (PaperBanana's plot guide; AI4VIS on perceptual
  > accuracy) advise against jet in favor of perceptually uniform colormaps
  > like viridis. How would you like to proceed?*
  > *- KEEP IMPORTED — use jet, matching the imported reference*
  > *- SWITCH TO RECOMMENDED — use viridis/magma/plasma as the bundled
  >   references recommend*
  > *- HYBRID — use viridis for new plots, keep jet only for slides that must
  >   match specific imported slides"*

  The user's answer is recorded in `style_config.json` under a `provenance`
  subfield so downstream QA can explain why a given choice was made. If the
  user chose `KEEP IMPORTED`, the Stylist suppresses the corresponding veto
  rule in `style_guide.md` for this project (the veto rule is still available
  globally, but marked "suppressed: user override" for this project).

  **Conflict detection scope.** Conflicts are only surfaced where the bundled
  references take an explicit stance (veto rules, "never use X" guidance, or
  strong "prefer X over Y" recommendations). Minor aesthetic differences
  (e.g., slightly different accent hex codes) are silently resolved in favor
  of the higher-precedence source without prompting the user.

  **Orthogonal dimensions.** Most of what the bundled references provide
  (connector semantics for diagrams, typography pairing principles, layout
  pitfalls, QA veto rules, math rendering conventions) is on different
  dimensions than what reference derivation provides (project-specific visual
  identity — colors, fonts, layout rhythm). On orthogonal dimensions there is
  no conflict: the Stylist uses the reference-derived values AND the bundled
  craft knowledge together. For example, the Stylist uses the reference's
  extracted font family but applies the bundled references' guidance on when
  to use italics vs. bold for emphasis.
- **REQ-STYLE-8:** The style guide MUST be written in imperative natural language addressed to the slide agent, not as documentation for the user. It is a prompt artifact, not a deliverable.
- **REQ-STYLE-9:** The plugin MUST include a style guide generation script (`debrief.style_guide_generator`) that the Stylist MAY invoke to auto-synthesize a first-draft `style_guide.md` from the layered inputs defined in REQ-STYLE-7. The script:

  1. Reads the bundled reference documentation at `${CLAUDE_PLUGIN_ROOT}/references/` (Section 24.39) as the craft-knowledge baseline.
  2. If `style_import_mode` is `"baseline"` or `"inspiration"`, reads `.debrief/draft/derived_style_guide.md` (produced by `debrief.style_analyzer`, per REQ-CONSULT-13).
  3. Reads the user's current style dialog choices from `style_config.json` (draft form, if present).
  4. Synthesizes a cohesive draft `style_guide.md` by layering these sources according to the precedence rules in REQ-STYLE-7 and using anti-prescriptive language ("common choices include single-column (~60% of slides) and two-column for comparisons (~30%)") rather than rigid prescriptions.

  This script does NOT read any exemplar HTML files and does NOT run Playwright. It is a text-synthesis utility that reduces the Stylist's authoring workload; the Stylist MAY further customize the generated draft during the style dialog based on the specific project's Content Signals and presentation type before presenting at gate G2.1.
- **REQ-STYLE-10 — Live style preview before approval.** Before presenting the style for approval at gate G2.1, the Stylist MUST generate a small set of preview slides rendered against the draft style so the user can see the result, not just read the description. This addresses the limitation that a style guide is a descriptive document and users often cannot fully predict how their choices will look until they see rendered output.

  **Preview generation flow.** After the Stylist finishes the Socratic style dialog Q&A and has produced draft versions of `style_config.json` and `style_guide.md` in `.debrief/draft/`, it MUST:

  1. Invoke the style compiler on the draft config: `python -m debrief.style_compiler .debrief/draft/style_config.json .debrief/draft/preview_style.css`. The draft CSS is NOT written to the locked `assets/style.css` path; it is a transient preview asset only.
  2. Generate **3 preview slides** in `.debrief/draft/preview_slides/` using generic placeholder content tuned to the project's presentation type from `deck_brief.md`:
     - `preview_01_title.html` — a title slide with a representative title, subtitle, author line, and institution.
     - `preview_02_content_diagram.html` — a content slide with a heading, 3-4 bullet points on the left, and a small placeholder diagram (or simple flowchart from one of the permitted diagram libraries) on the right. Demonstrates typography, layout grammar, and diagram styling.
     - `preview_03_data_exhibit.html` — a data exhibit slide with a heading, a placeholder chart image (or an SVG bar chart), and a caption line. Demonstrates data viz conventions (color palette application, axis/grid treatment, caption styling).

     The placeholder content is drawn from a fixed content template (bundled at `${CLAUDE_PLUGIN_ROOT}/references/preview_placeholder_content.md`, Section 24.39) keyed by `archetype` (which determines `presentation_type` via the Section 14.1.1 mapping) so the previews feel representative of the user's actual project without using their real content (which may not exist yet at this point in the pipeline).

  3. Render each preview HTML to PNG via Playwright: `python -m debrief.preview_renderer --project-root . --input-dir .debrief/draft/preview_slides/ --output-dir .debrief/draft/preview_images/`. Each PNG is slide-sized (16:9, 1920×1080) and captures the full rendered slide. The preview renderer is a thin wrapper around Playwright that loads each HTML file, waits for KaTeX/Mermaid/rough.js to finish rendering, and saves a screenshot.

  4. Present the previews to the user as part of the gate G2.1 prompt. The gate prompt now reads:

     > "I've drafted a style for your deck. Here is the design rationale:
     >
     > {draft_style_guide_summary}
     >
     > And here are three rendered preview slides using this style:
     >
     > - [preview_01_title.png](.debrief/draft/preview_images/preview_01_title.png)
     > - [preview_02_content_diagram.png](.debrief/draft/preview_images/preview_02_content_diagram.png)
     > - [preview_03_data_exhibit.png](.debrief/draft/preview_images/preview_03_data_exhibit.png)
     >
     > Look at the previews carefully — the typography, color balance, diagram treatment, and overall visual rhythm. Do they match what you want for your deck?
     >
     > Reply with one of:
     > - **STYLE APPROVED** — the style is good; proceed to Phase 3.
     > - **STYLE REVISE <free-form feedback>** — describe what needs to change; the Stylist will iterate.
     > - **REGENERATE PREVIEWS** — keep the same style but render new preview slides (useful if you want to see more examples before committing; the Stylist will pick different placeholder content for variety)."

  5. On `STYLE APPROVED`, the draft files are promoted (draft/style_config.json → style_config.json, draft/style_guide.md → style_guide.md) and the style lock proceeds at G2.2 per REQ-STYLE-5 and REQ-STYLE-6. The `.debrief/draft/` directory is cleaned up on successful lock.

  6. On `STYLE REVISE`, the Stylist re-reads the draft, the user's feedback, the bundled references, and the reference-derived draft style guide (if any); it regenerates the draft config and guide; then it re-runs steps 1-4. There is no limit on the number of iterations — the red-green-style loop is user-controlled.

  7. On `REGENERATE PREVIEWS`, the Stylist re-runs steps 2-4 with different placeholder content (different title text, different bullet examples, different diagram shape) but the same style values. This is a low-cost operation (no re-synthesis of the style guide, just re-rendering).

  **Mid-dialog inline previews (optional).** The Stylist MAY also generate narrower previews at key decision points within the style dialog (e.g., after the color selection is made, render a single preview tile showing the color palette applied to a small sample slide). This is non-normative guidance — the mandatory preview step is the end-of-dialog one described above. Inline mid-dialog previews are an optional enhancement the Stylist can choose to invoke when the user is making a high-stakes choice (e.g., between two candidate color palettes).

  **Preview placeholder content bundle.** The `references/preview_placeholder_content.md` file is bundled with the plugin and contains a per-archetype template for preview content. Example entry:

  ```
  ## lab_meeting
  - title: "Weekly Lab Meeting — Progress Update"
  - subtitle: "Week 14: Results from the behavioral cohort"
  - author: "Jane Doe, PhD"
  - institution: "Example Neuroscience Institute"
  - content_bullets:
    - "N=32 animals, split across 4 experimental groups"
    - "Cohort completed behavioral assay week 11-13"
    - "Preliminary analysis shows group effect p<0.01"
    - "Next steps: histology and c-Fos imaging"
  - data_exhibit_caption: "Figure 1. Freezing behavior across experimental groups (mean ± SEM)."
  ```

  Similar entries exist for `conference_talk`, `seminar`, `lecture`, `journal_club`, `grant_panel`, `job_talk`, and `custom`. Carlo and Leonardo author this file as a one-time task during distillation (~1-2 hours).

  **Why this matters.** A style guide is a descriptive document. Users can read it and still fail to anticipate how their choices will actually look. The preview step closes this gap by making the style dialog feel more like a design tool and less like a text-based configuration exercise. It also catches subtle issues (e.g., a color palette that looks fine in hex codes but is low-contrast in practice, a font pairing that looks academic in theory but clashes in execution) before the style is locked and downstream slide generation begins — failures at this stage are cheap; failures after style lock trigger expensive rework.

  **Performance bound.** The preview generation step MUST complete in under 30 seconds end-to-end (style compile + HTML generation + Playwright rendering of 3 slides). If it exceeds 60 seconds, the Stylist presents a timeout warning and offers the user the option to proceed without previews (with a warning that they're approving blind). This prevents preview generation from becoming a pipeline-stalling step.

  **Preview files are NOT part of the locked artifacts.** `.debrief/draft/` is transient and cleaned up after style lock. The previews are not versioned, not committed to git, and not included in the delivered deck. They exist only to help the user make an informed decision at G2.1.

### 14.4 Slide Authoring (`/debrief:slide`)

- **REQ-SLIDE-1:** The slide skill MUST accept an optional slug argument. Preconditions (checked by the skill before yielding to routing):

  1. If `style_locked` is `false` in `deck_state.json`, the skill MUST print `Style must be locked before creating slides. Run /debrief:style first.` and exit without modifying state.
  2. If a slug is provided: check that a slide with that slug exists in `deck_state.json` with `status != 'discarded'`. If not found, print an error listing all valid (non-discarded) slugs and exit without modifying state. Discarded slides are treated as non-existent — the slug may be re-used for a fresh slide.
  3. If a valid slug is provided and the slide exists, set `current_slide_slug: <slug>` in `debrief_state.json` and yield to routing. The consultant will re-enter the red-green or slide review sub-phase for that slide. *(BUG-AUDIT-31: the consultant handles all dispatch via Tool calls.)*
  4. If no slug is provided, set `current_slide_slug: null` in `debrief_state.json` and yield to routing. The consultant enters `production/group_planning` to request the next slide brief. *(BUG-AUDIT-31: the consultant handles all dispatch via Tool calls.)*
- **REQ-SLIDE-2:** The slide agent MUST generate a single HTML file at
  `slides/<slug>.html`. The file must be self-contained: all styles are loaded
  from `../assets/style.css`; no inline styles that override the style config
  are permitted. The slide agent MUST read `style_guide.md` before generating or revising any slide HTML. The style guide provides design intent and rationale that the agent must follow in addition to the mechanical constraints of `assets/style.css`.
- **REQ-SLIDE-3:** Every slide MUST conform to the design invariants enumerated in
  Section 16.
- **REQ-SLIDE-4:** The Slide Maker MUST NOT present a slide to the user until the red-green cycle has completed with a GREEN result (all Tier 1 invariants pass). The user MUST never see a slide with mechanical visual defects. The red-green cycle is fully autonomous — the user is not involved and is not informed of intermediate failures. Presenting a slide means opening the single-slide view in the default browser (REQ-VIEW-3 single-slide mode) using the screenshot from `output/screenshots/<slug>.png`.

  **Approval payload production.** Before the Slide Maker returns from any GREEN iteration of the red-green cycle, the Slide Maker MUST write `.debrief/approval_<slug>.json` with the slide's approval payload (per the schema in Section 24.24). This file is the approval payload for G3.3 `SLIDE APPROVED` — it sits on disk waiting for the user's eventual response, at which point `update_state` reads and merges it into `deck_state.json`. The Slide Maker is the sole producer of this file; no agent or script writes it at G3.3 response time. If the cycle does not reach GREEN (EXHAUSTED or oscillation revert), the file is still written (from the best-known-good iteration) so that `SLIDE APPROVED` remains a valid response even on the post-diagnostic variant of G3.3.

  Note: `.debrief/approval_<slug>.json` is distinct from `.debrief/gate_data.json`. The former carries the approval payload (Slide Maker writes it, `update_state` consumes it on `SLIDE APPROVED`). The latter carries user-supplied parameters for parameterized gates (G1.3 figure selection, G3.4 `GROUP REVISE <slug>`, G3.V `DETAIL FIX <slug>`, G3.3 post-diagnostic `SLIDE REVISE: <instructions>`) and is written by `update_state` when it parses the user's gate response. See Section 24.21 for the two-file split and Section 24.24 for the schemas.
- **REQ-SLIDE-5:** The red-green cycle runs for a maximum of **5 iterations**. Each iteration consists of: screenshot, Tier 1 check, (if red) read revision_instructions, rewrite, next iteration. Iteration 0 means no attempts have been made. Each attempt increments the counter before execution. EXHAUSTED fires when `red_green_iteration >= 5`, meaning 5 attempts have been made.

  **Post-EXHAUSTED flow.** After 5 failed iterations (EXHAUSTED), the pipeline transitions through a dedicated diagnostic sub-phase. The Slide Maker does NOT invoke the diagnostic agent directly (agent-to-agent invocation is prohibited per REQ-ROUTE-1 and Section 24.19). The sequence is:

  1. When EXHAUSTED is detected, `sub_phase` transitions to `production/diagnostic`. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles this transition directly via Tool calls.)*
  2. The consultant reads `sub_phase: production/diagnostic` and invokes the bug-diagnostic agent. This dispatch is also recorded in the Dispatch Event Table (Section 13.1) as `DIAGNOSTIC_REQUESTED`. *(BUG-AUDIT-31: the consultant handles all dispatch via Tool calls.)*
  3. The bug-diagnostic agent reads `qa_log.jsonl`, `output/qa_cycle_log.jsonl`, and the current `slides/<slug>.html`; it writes its report to `.debrief/diagnostic_<slug>.md` (see Section 24.24 and RL3 for the file contract).
  4. The diagnostic agent's `post` step transitions `sub_phase` back to `production/slide_review` with `pending_gate: G3.3_slide_review_post_diagnostic` (a distinct human gate — see Section 14.16).
  5. The consultant presents G3.3 (post-diagnostic variant) with `.debrief/diagnostic_<slug>.md`, the current slide HTML, and the screenshot in the context. The user is informed only at this point — not during intermediate fix attempts. *(BUG-AUDIT-31: the consultant handles all dispatch via Tool calls.)*

  When the cycle reaches GREEN, any Tier 2 warnings are collected. The slide is presented to the user with the Tier 2 warnings displayed alongside the preview. The user may accept the slide as-is or request revisions addressing the warnings. User-requested revisions re-enter the red-green cycle from iteration 0.

  **EXHAUSTED recovery constraint:** When the user responds to `G3.3_slide_review_post_diagnostic` with `SLIDE REVISE`, they MUST provide revision instructions as part of the response. The response format is `SLIDE REVISE: <instructions>` where `<instructions>` is free text describing what to change. The `update_state` script rejects bare `SLIDE REVISE` (with no instructions) at this gate with the error: `After an exhausted red-green cycle, revision requires explicit instructions. Please provide guidance or select SLIDE APPROVED to accept as-is.` This prevents infinite EXHAUSTED→REVISE loops with no new input. The normal-path `G3.3_slide_review` gate continues to accept bare `SLIDE REVISE`, which is a distinct gate ID.

- **REQ-SLIDE-6:** The red-green cycle uses the routing protocol's machine gate
  mechanism, not skill-side polling. *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)* After the Slide Maker writes
  `slides/<slug>.html`, the PostToolUse hook fires the QA agent synchronously
  (the hook does not return until the QA agent completes, up to its 60-second
  timeout). The QA agent writes its result to `qa_log.jsonl` before the hook
  returns. The Slide Maker agent's invocation completes, returning control to
  the consultant. The consultant reads
  the latest `qa_log.jsonl` entry for `current_slide_slug` as part of the G3.2
  check.

  **Timing contract:**
  - PostToolUse hook timeout: 60 seconds (hard kill, per `hooks.json`).
  - The QA agent MUST write its result to `qa_log.jsonl` before returning from
    the hook.
  - If the hook times out (60s exceeded), the G3.2 check finds
    no new entry and treats the iteration as an implicit RED with a `timeout`
    failure, incrementing `red_green_iteration` as normal. After 5 timeouts,
    EXHAUSTED fires. *(BUG-AUDIT-31: the consultant handles these checks directly.)*

  The qa_log.jsonl entry format is defined authoritatively in REQ-QA-3 (failure schema) and REQ-QA-7 (pass-with-warnings schema).

  There is no polling loop in any skill. Polling was considered and rejected
  because: (1) blocking a skill's turn on a Bash polling loop would stall the
  orchestrator; (2) the consultant already re-reads state on every
  iteration, making polling redundant. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*
- **REQ-SLIDE-7:** Each iteration of the red-green cycle is a full rewrite of the slide HTML by the Slide Maker, guided by the `revision_instructions` from the most recent QA failure record. The Slide Maker MUST read the latest `qa_log.jsonl` entry for the current slug before each rewrite and MUST address every `revision_instruction` listed. Each rewrite triggers QA via two mechanisms (per BUG-AUDIT-17): (a) Tier 1 programmatic checks run automatically via a `type: "command"` PostToolUse hook that invokes `bin/qa-run-on-write` → `python -m debrief.qa_checker` on every slide Write/Edit (BC-1.4); (b) Tier 2 VLM checks run when the Slide Maker invokes the visual-qa agent via the `Task` tool as its absolute final action before returning (BC-8.4). The Slide Maker's system prompt contains a load-bearing requirement for the `Task` dispatch; it MUST NOT return without invoking visual-qa. See §24.18 for the full red-green cycle orchestration.

  The iteration counter is tracked in `debrief_state.json` (field `red_green_iteration`) and managed by the `update_state` script. It resets to 0 when:
  - The user provides new revision instructions (outer loop)
  - A new slide is started
  - Control returns from the Consultant after an `ESCALATE_TO_CONSULTANT`
- **REQ-SLIDE-8:** The Slide Maker MUST generate each slide by applying the project's `style_guide.md` (REQ-STYLE-7), `style_config.json` (REQ-STYLE-4), the bundled reference documentation at `${CLAUDE_PLUGIN_ROOT}/references/` (Section 24.39), the slide brief, and the project's Content Signals. **The plugin does NOT ship an exemplar library.** There is no `exemplars/` directory, no `exemplar_index.json`, and no fallback "exemplar-guided" generation mode. The single generation path is style-guide-driven.

  **Rationale.** Style-by-example is covered by the reference import flow (REQ-CONSULT-13/14, gate G1.2). Craft knowledge is covered by the bundled reference documentation. Slide-pattern structural guidance is covered by the REQ-STYLE-7 "Visual patterns catalog" subsection. Anti-patterns are covered by the REQ-STYLE-7 "Anti-patterns" subsection. In-deck consistency across slides is handled organically because the Slide Maker has access to previously approved slides in `slides/` within the same project.

  **In-deck few-shot continuity (non-normative guidance).** When generating slide N (N ≥ 2), the Slide Maker MAY pass the most recent 1-2 approved slides from `slides/` as few-shot context to maintain visual consistency within the deck. This is an implementation detail of the Slide Maker unit, not a separate feature, and requires no plugin-level infrastructure.
- **REQ-SLIDE-9:** While the user is in the Slide Maker context (between `DISPATCH_GROUP` and `GROUP_APPROVED`), the Slide Maker is the active agent. The user talks to the Slide Maker for detail-level changes. The Consultant is not active during this period. The Slide Maker MUST NOT make narrative-arc decisions (e.g., reordering the deck, adding new slides outside the current group, changing the deck brief). However, if the user invokes `/debrief:view` and then describes a structural change, the system MUST emit `ESCALATE_TO_CONSULTANT` and yield control to the Consultant. The Slide Maker MUST NOT attempt structural changes itself.
- [REQ-SLIDE-10 reserved -- superseded by `/debrief:view` context-aware dispatch (REQ-VIEW-6)]
- **REQ-SLIDE-11:** During the red-green cycle, the Slide Maker MUST NOT communicate with the user. No intermediate results, no progress updates, no "attempting fix..." messages. The cycle is silent. The user sees only the final result: either a GREEN slide with optional Tier 2 warnings, or a diagnostic report after 5 failed iterations. The silence rule applies to intermediate iterations only. If the routing system detects oscillation (per REQ-SLIDE-14), the red-green cycle pauses and gate G3.2a is presented. This is a system-level decision, not a Slide Maker decision — the Slide Maker remains silent throughout.
- **REQ-SLIDE-12:** The red-green cycle MUST produce a machine-readable summary after completion, written to `output/qa_cycle_log.jsonl`:
  ```json
  {
    "slug": "methodology",
    "started_at": "ISO8601",
    "completed_at": "ISO8601",
    "iterations": 3,
    "final_status": "green",
    "tier1_failures_by_iteration": [
      ["INV-04", "INV-06"],
      ["INV-04"],
      []
    ],
    "tier2_warnings": ["INV-09"]
  }
  ```
  This log is for diagnostic purposes and is not shown to the user during normal operation.

  **Writer designation.** `qa_cycle_log.jsonl` is written by `update_state` only, at the transition out of `production/red_green` (to `production/slide_review` on GREEN, to `production/diagnostic` on EXHAUSTED, or to `production/slide_review` on G3.2a REVERT). The visual-qa agent does NOT write to `qa_cycle_log.jsonl` — it writes only to `qa_log.jsonl` (one entry per slide write). The per-cycle summary format described above is authoritative: **one entry per red-green cycle**, not one entry per iteration.

  **Schema immutability.** The fields `slug`, `started_at`, `completed_at`, `iterations`, `final_status`, `tier1_failures_by_iteration`, and `tier2_warnings` are required. No additional fields. No stream-style per-iteration entries. Blueprint implementations MUST NOT invent a per-iteration flat schema.

  **Mechanism.** `update_state` reads the `qa_log.jsonl` entries for `current_slide_slug` written since the cycle began, builds the per-iteration failure arrays, and writes the summary entry at cycle exit. To support this, `debrief_state.json` gains a new field `red_green_started_at` (see Section 17.5).
- **REQ-SLIDE-13:** At the end of a COMPLETED red-green cycle (GREEN, EXHAUSTED, or user-terminated via G3.2a REVERT), the Slide Maker MUST clean up transient working artifacts before presenting the result. Cleanup removes any intermediate HTML snapshots in `.debrief/snapshots/<slug>_iter_*.html`. Only the final `slides/<slug>.html` survives. The screenshot in `output/screenshots/<slug>.png` reflects the final iteration. The `qa_cycle_log.jsonl` entry is flushed.

  **Exception for mid-cycle quit:** If the user invokes `/debrief:quit` while the red-green cycle is active (per REQ-QUIT-1), snapshots are retained in `.debrief/snapshots/` for resume. On resume, the cycle continues from the saved iteration count with the snapshot history intact. The next cycle completion (success or exhaustion) cleans up per the normal rule.
- **REQ-SLIDE-14:** The red-green cycle MUST track the "best known good" version of the slide. Before each rewrite iteration, the current `slides/<slug>.html` is snapshotted to `.debrief/snapshots/<slug>_iter_<N>.html` where N is 1-indexed (first iteration writes `_iter_1`, not `_iter_0`) and NOT zero-padded (range: 1–5 per REQ-SLIDE-5). After each QA check, the system compares the current iteration's failure count (veto count + Tier 1 failure count) against the best previous iteration's failure count:

  - If the count **decreased** (improvement): update the best-known-good to the current version. Continue iterating.
  - If the count **increased** (regression): revert `slides/<slug>.html` to the best-known-good snapshot. Stop the red-green cycle. Present the best version to the user with remaining Tier 2 warnings.
  - If the count is **unchanged but the failures are different** (oscillation): see "Oscillation handling" below.

  **Oscillation handling:** If the current iteration's failure count equals the previous iteration's failure count BUT the failures are different (different invariant IDs), the cycle is oscillating — fixing one issue introduces another. On detection, `update_state` sets `sub_phase: 'oscillation_review'` and routes to gate G3.2a (Section 14.16). The user chooses KEEP TRYING, REVERT TO BEST, or MY INSTRUCTIONS. The MY INSTRUCTIONS branch uses an inline skill prompt (Section 24.30) to collect the user's guidance before re-entering `production/red_green`.

  **This does NOT violate REQ-SLIDE-11's silence rule.** REQ-SLIDE-11 prohibits the Slide Maker from communicating with the user during silent autonomous iterations. G3.2a is a gate, presented by the routing system, not by the Slide Maker. It breaks the silence only when the machine-driven loop cannot make progress, which is the correct moment for user involvement.

  Snapshots are cleaned up by REQ-SLIDE-13 at the end of the cycle.
- [Requirement slot 15 reserved — previously specified an exemplar-library fallback; removed when the exemplar library was dropped from v1.1. Do NOT renumber later REQ-SLIDE IDs.]

### 14.5 Visual QA Agent

- **REQ-QA-1:** The QA agent MUST take a screenshot of every slide using
  headless Chromium before passing it. The QA agent does not drive Playwright
  directly via tool use — it invokes `python -m debrief.qa_checker`, which
  uses the `playwright-python` library internally to launch Chromium, open a
  browser context, render the slide HTML, and capture the screenshot. The QA
  agent consumes the checker's output; it never imports or calls Playwright
  on its own.

  **Invocation mechanism (post-BUG-AUDIT-17).** The QA agent is invoked by
  the **slide-maker agent** via the `Task` tool at the end of each slide-
  write turn per BC-8.4, NOT by a PostToolUse agent hook. The prior mechanism
  used a `type: "agent"` PostToolUse hook that was broken by Claude Code
  v2.1.107 upstream (see BUG-AUDIT-12b) and was removed in BUG-AUDIT-17.
  Tier 1 programmatic checks (`qa_checker.py`) now run automatically via a
  `type: "command"` PostToolUse hook (`bin/qa-run-on-write`) on every
  `Write|Edit` matching `slides/*.html` per BC-1.4; the QA agent is
  responsible for the Tier 2 VLM review (VETO-\*, INV-01..03/05/09/11/18/21)
  and for merging its findings with the Tier 1 entry that the command hook
  has already written to `qa_log.jsonl`.
- **REQ-QA-2:** The QA agent MUST check all design invariants enumerated in Section 16.
- **REQ-QA-3:** The QA agent MUST write a structured result record to
  `output/qa_log.jsonl` for every slide checked. This REQ is the canonical definition of the `qa_log.jsonl` entry schema; any other reference in this spec (Section 24.3, REQ-QA-6, REQ-QA-7) cross-references this schema.

  **Canonical schema:**

  ```json
  {
    "slug": "<string>",
    "timestamp": "<ISO8601>",
    "passed": <bool>,
    "veto": <bool>,
    "checks_run": ["<invariant_id>"],
    "failures": [
      {"invariant": "<id>", "description": "<text>", "revision_instruction": "<text>"}
    ],
    "warnings": [
      {"invariant": "<id>", "description": "<text>", "revision_instruction": "<text>"}
    ],
    "revision_instructions": ["<string>"]
  }
  ```

  **Rules:**

  1. `failures` and `warnings` are always arrays — empty arrays if none.
  2. `revision_instructions` is always present as a top-level array (empty on pass per REQ-QA-6). Each string in this array corresponds to a concrete, actionable directive that the slide agent can execute without further interpretation. The QA agent MUST reference CSS custom property names from `style_guide.md` in its instructions where applicable.
  3. `veto: true` implies `passed: false` and only the vetoing entry appears in `failures` (Tier 1 and Tier 2 are skipped — see REQ-QA-7).
  4. `checks_run` lists the invariant IDs that were actually evaluated (veto rules + any Tier 1/Tier 2 IDs reached), not the full catalog.

  **Example (failure):**

  ```json
  {
    "slug": "intro",
    "timestamp": "2026-04-09T12:34:56Z",
    "passed": false,
    "veto": false,
    "checks_run": ["VETO-01", "VETO-02", "INV-04", "INV-06"],
    "failures": [
      {
        "invariant": "INV-04",
        "description": "Heading text #333 on background #555 has contrast ratio 2.1:1",
        "revision_instruction": "Change the heading text color to var(--color-text-primary) or increase the contrast by lightening the background to at least #888."
      }
    ],
    "warnings": [],
    "revision_instructions": [
      "Change the heading text color to var(--color-text-primary) or increase the contrast by lightening the background to at least #888."
    ]
  }
  ```

  All `qa_log.jsonl` examples elsewhere in the spec MUST conform to this canonical schema.
- **REQ-QA-4:** The QA agent runs as fast as it can. There is no per-slide time budget.
- **REQ-QA-5:** Screenshots MUST be saved to `output/screenshots/<slug>.png` at
  the project level. Screenshots are a per-project QA working artifact, not a
  per-presentation deliverable. They are overwritten each time a slide is
  re-rendered. Screenshots are NOT stored inside presentation folders.
- **REQ-QA-6:** When all checks pass, the QA agent MUST set `revision_instructions` to an empty array. This serves as the early-stopping signal.
- **REQ-QA-7:** The QA agent MUST check veto rules first. If any veto fires, the result is `passed: false, veto: true` and only the veto failure is reported. If no veto fires, proceed to Tier 1 checks. If any Tier 1 invariant fails, the result is `passed: false` and only Tier 1 failures are reported (Tier 2 checks may be skipped). If all Tier 1 invariants pass, the agent evaluates Tier 2 invariants. Tier 2 failures are reported as `warnings` in the QA result record but do NOT set `passed: false`. A slide with only Tier 2 warnings is considered passing.

  The `qa_log.jsonl` record for a passing slide with Tier 2 warnings (canonical schema per REQ-QA-3):
  ```json
  {
    "slug": "intro",
    "timestamp": "2026-04-09T12:34:56Z",
    "passed": true,
    "veto": false,
    "checks_run": ["VETO-01", "...", "INV-09", "..."],
    "failures": [],
    "warnings": [
      {
        "invariant": "INV-09",
        "description": "6 bullet points found (max 5)",
        "revision_instruction": "Condense to 5 bullets or split into two slides."
      }
    ],
    "revision_instructions": []
  }
  ```
- **REQ-QA-8:** Image-specific checks are enumerated as Tier 1 invariants. See: INV-07 (no external network requests — covers the "local path, not remote URL" rule), INV-13 (image overflow and 10% margins), INV-19 (user-provided image `src` file existence), INV-20 (image aspect-ratio distortion, 2% threshold). All four are Tier 1 (hard blockers). A broken image reference or a clipped image is a mechanical defect the red-green cycle must fix autonomously. Allocation between `qa_checker.py` and the QA agent is specified in Section 24.22.
- **REQ-QA-9:** Math-specific checks are enumerated as Tier 1 invariants. See: INV-14 (display math horizontal overflow within 10% margins), INV-21 (rendered math visible — not a blank box or error placeholder), INV-22 (inline math line-height break — distinct from INV-14's horizontal rule), INV-23 (math asset file existence). All four are Tier 1 (hard blockers). Math rendering errors (parse failures, blank output, vertical overflow) are mechanical defects the red-green cycle must fix. Allocation between `qa_checker.py` and the QA agent is specified in Section 24.22 — INV-21 is the one Tier 1 math check assigned to the VLM-based QA agent because "blank box vs. rendered math" is primarily a visual signal.

### 14.6 Export (`/debrief:export`)

- **REQ-EXPORT-1:** If `separator_position` in the active presentation record is non-null, the export module MUST generate a separator slide at export time. The separator is rendered in-memory using the locked style config (palette, fonts) and its content from `separator_content`. It is not a user-authored slide, has no slide record, and is not written to `slides/`. The separator is always placed between the last non-backup approved slide (or the closing slide, if present) and the first backup approved slide, regardless of the `separator_position` numeric value. See Section 17.4 for the `separator_position` field semantics and Section 24.10 for the canonical PDF page order.
- **REQ-EXPORT-2:** The export module MUST render all slides in the order determined
  by the `slides` array in `deck_state.json` to a single multi-page PDF using
  Playwright. The order of entries in the `slides` array is the canonical deck
  order for export. The export module reads only slides with `status: "approved"`
  from the `slides` array. All approved slides are printed in one browser
  session; no external merge tool is needed.
- **REQ-EXPORT-3:** The output PDF MUST be written to
  `output/<presentation_folder>/deck_v{NNN}.pdf` where `<presentation_folder>`
  is the folder confirmed during the export ordering dialog (see Section 24.10),
  and NNN is a zero-padded three-digit version number starting at 001 per
  folder. The version number is determined by counting existing PDFs in the
  target folder and incrementing by one.
- **REQ-EXPORT-4:** The PDF MUST be rendered at 16:9 aspect ratio, suitable for
  projection and for sharing on a compressed video stream.
- **REQ-EXPORT-5:** An export log entry MUST be appended to `output/export_log.jsonl`
  recording: timestamp, presentation folder, version number, slide count, and
  Playwright exit status. The canonical entry schema:

  ```json
  {
    "timestamp": "2026-04-11T14:32:01Z",
    "presentation_folder": "2026_04_11_SVP_presentation",
    "version": 2,
    "slide_count": 14,
    "playwright_exit_status": 0,
    "pdf_path": "output/2026_04_11_SVP_presentation/deck_v002.pdf",
    "error_message": null
  }
  ```

  The G4.5 machine gate (Section 14.18) reads the latest entry and fires `EXPORT SUCCESS` if `playwright_exit_status == 0`, else `EXPORT FAILED` with `error_message` injected into the gate context. *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)*
- **REQ-EXPORT-6:** The export skill MUST check preconditions before yielding:

  1. If `style_locked` is `false`, print `Cannot export: style is not locked. Complete the style dialog first.` and exit without modifying state.
  2. If no slides have `status: 'approved'` in `deck_state.json`, print `Cannot export: no approved slides. Approve at least one slide before exporting.` and exit.
  3. If any slides have `status: 'draft'` or `status: 'needs_revision'` (not approved, not discarded), print a warning listing those slugs: `Warning: the following slides are not approved and will be excluded from the export: <slug list>. Continue anyway? (yes/no)`. If the user responds `yes`, proceed to yield. Any other response cancels.
  4. If all preconditions pass, the skill yields to routing. The consultant enters `finalization/export_options` (G4.1) regardless of the current phase. *(BUG-AUDIT-31: the consultant handles all dispatch via Tool calls.)*

### 14.7 View (`/debrief:view`)

- **REQ-VIEW-1:** The `/debrief:view` skill operates in two visual modes depending on the query:

  **Storyboard mode** (multi-slide): When the query resolves to two or more slides, the view produces a thumbnail grid — a bird's-eye storyboard for narrative review.

  **Slide preview mode** (single slide): When the query resolves to exactly one slide, the view shows it at full size in the browser for detailed visual inspection.

  The user can invoke either mode at any time while talking to the Slide Maker or the Consultant. Typical usage during slide authoring:
  - "Let me see this slide" → `/debrief:view <slug>` → full-size preview
  - "Let me see the storyboard" → `/debrief:view current` or `/debrief:view` → thumbnail grid
  - "Show me this group and the previous one" → `/debrief:view both` → thumbnail grid

  Supported query forms:

  | Query | Mode | Meaning |
  |-------|------|---------|
  | `/debrief:view` (no argument) | Storyboard | Show all approved slides in deck order |
  | `/debrief:view current` | Storyboard | Show only slides in the current group being authored |
  | `/debrief:view previous` | Storyboard | Show slides in the previously completed group |
  | `/debrief:view current previous` or `/debrief:view both` | Storyboard | Show current + previous group together |
  | `/debrief:view last 2 of previous` | Storyboard | Show the last N slides of the previous group |
  | `/debrief:view <slug>` | Slide preview | Show a single slide by slug at full size |
  | `/debrief:view <slug1> <slug2> ...` | Storyboard | Show specific slides by slug, in the order given |
  | `/debrief:view backup` | Storyboard | Show only backup/Q&A slides |
  | `/debrief:view all` | Storyboard | Show all slides including drafts and needs_revision (not just approved) |

  The query is parsed left-to-right. Unrecognized tokens are treated as slug names.
- **REQ-VIEW-2:** In storyboard mode, the view skill MUST generate an HTML file at `output/view.html` that tiles the requested slides as thumbnail cards in a grid layout. Each card shows the rendered slide screenshot (from `output/screenshots/<slug>.png`), the slide's **slug** displayed as a label below the thumbnail (styled in a small monospace font), and the slide title below the slug. The slug label allows the user to reference specific slides by slug when requesting modifications. The grid respects the order specified by the query. If a screenshot does not exist for a requested slide, the view MUST display a placeholder card with the text 'Screenshot not available — run QA to generate' and the slide title.
- **REQ-VIEW-3:** In slide preview mode (single slug), the view MUST show the slide at full size, not as a thumbnail. The view MUST open in the default browser automatically in both modes.
- **REQ-VIEW-4:** The view skill is available at any time during Phase 3 and Phase 4 — during Slide Maker context, during Consultant context, and during the backup slide loop. It does not change the active pipeline context; it is a read-only inspection.

  **Phase restrictions:**
  - In Phase 1 (discovery) or Phase 2 (style definition), `/debrief:view` is NOT available. The skill MUST print `No slides yet. The view becomes available once slide production begins in Phase 3.` and exit without modifying state.
  - In Phase 4 (finalization), see REQ-VIEW-6 for the read-only `CONTINUE`-only dispatch restriction.

  **During red-green cycle:** If `sub_phase` is `red_green`, the view is deferred until the red-green cycle has exited (reached GREEN, EXHAUSTED, or user-terminated via G3.2a REVERT). The skill acknowledges the command, sets `view_deferred: true`, and yields. The consultant, after each red-green iteration, checks whether the cycle has exited AND `view_deferred` is true; if both, it runs the view module and presents G3.V. *(BUG-AUDIT-31: the consultant handles all dispatch via Tool calls.)*

  **Empty result:** If the query resolves to zero slides (e.g., `/debrief:view` called before any slide is approved), the skill MUST print `No slides match this query.` and not open the browser.

  **Nested view:** If `/debrief:view` is invoked while G3.V is already pending (e.g., the user wants to see a different slide while at G3.V), the skill MUST re-generate the view without modifying `pre_view_state` or `pending_gate`. The user remains at G3.V.
- **REQ-VIEW-5:** To resolve `current` and `previous`, the view skill reads `deck_state.json` to determine group boundaries. Group membership is tracked by a `group_id` field in each slide record (see Section 17.2). `current` resolves to slides whose `group_id` matches the active group. `previous` resolves to the group_id immediately before the current one.
- **REQ-VIEW-6:** In Phase 4 (`finalization/*` states), `/debrief:view` opens the browser but the dispatch is restricted to `CONTINUE` only. `DETAIL FIX` and `ESCALATE` are not available during finalization — the user must return to the export flow. The G3.V gate is NOT presented in Phase 4; the view is read-only.

  After the view opens in the browser, the system MUST ask the user: **"What would you like to do?"** The user's response determines the dispatch:
  - If the user describes a **detail-level change** (specific slide content, text, diagram, spacing on a particular slide), the system routes to the **Slide Maker** context for that slide. If the user is already in the Slide Maker context, control stays there. If the user is in the Consultant context, the system emits `DETAIL_FIX` to hand off to the Slide Maker for the specific slug(s) mentioned.
  - If the user describes a **structural change** (reordering slides, splitting/merging groups, changing the narrative arc, adding/removing slides from the plan), the system routes to the **Consultant** context. If the user is already in the Consultant context, control stays there. If the user is in the Slide Maker context, the system emits `ESCALATE_TO_CONSULTANT`.
  - If the user says the slides look good or has no feedback, the system returns to whichever context was active before the view was invoked.

### 14.8 Presenter Script (`/debrief:script`)

- **REQ-SCRIPT-1:** The script skill MUST generate a presenter script from the
  current `deck_brief.md` and all slide records in `deck_state.json`. The skill
  MUST NOT run if no export has been done (i.e., the `presentations` array in
  `deck_state.json` is empty). If invoked with no prior export, it MUST print an
  explanatory message and exit. The script skill does not modify `debrief_state.json` and does not change the pipeline state. It may be invoked at any time after the first export without affecting routing. On success, it prints: `Script written: output/<folder>/script_vNNN.md`.
- **REQ-SCRIPT-2:** The script MUST be written to
  `output/<presentation_folder>/script_v{NNN}.md`, where `<presentation_folder>`
  is the folder of the most recent export (the last entry in the `presentations`
  array). The version number NNN is zero-padded to three digits, starting at 001
  per folder, determined by counting existing script files in the target folder
  and incrementing by one.
- **REQ-SCRIPT-3:** The script MUST include one section per slide, with: slide title,
  key talking points, transitions to adjacent slides, and estimated speaking time.

### 14.8a Handout (`/debrief:handout`)

- **REQ-HAND-1:** The handout skill MUST generate a handout PDF combining slide thumbnails with explanatory text. The handout is an optional deliverable, available after at least one export has been produced.
- **REQ-HAND-2:** The handout MUST support two layout modes:
  - **2-up:** Two slides per page, each slide thumbnail on the left (or top) with the corresponding explanatory text on the right (or bottom). Best for detailed teaching handouts.
  - **4-up:** Four slides per page in a 2x2 grid, with condensed text below each thumbnail. Best for compact reference handouts.

  The user selects the mode via the argument (`/debrief:handout 2up` or `/debrief:handout 4up`). If the skill is invoked without an argument, it MUST prompt the user:

  ```
  Which handout layout?
    (1) 2-up  -- larger thumbnails, detailed notes (best for teaching)
    (2) 4-up  -- compact 2x2 grid, condensed notes (best for reference)
  [default: 2-up]
  ```

  A response of `1`, `2up`, or empty (just enter) selects 2-up. A response of `2` or `4up` selects 4-up. Any other response re-prompts.

  If an invalid argument is provided on the command line (e.g., `/debrief:handout 3up`), the skill MUST print an error listing valid modes and exit without generating a handout.
- **REQ-HAND-3:** *(BUG-AUDIT-68 — rewritten)* The explanatory text for each slide is assembled from a deterministic three-level precedence, in order. The handout module applies the first source that yields non-empty text:
  1. **Speaker script** — if `<project_root>/speaker_script.md` exists and contains a per-slide section matching the current slide, use that section's body. Matching is by slug (primary, via the `**Slug:** \`<slug>\`` marker emitted by the script generator) or by title (fallback, via the `## Slide N: <title>` header). `speaker_script.md` is origin-agnostic: it may be user-authored or a user-chosen copy of a generated `script_v{NNN}.md`; the handout treats it as the canonical notes source regardless of origin. Generator output continues to be written to versioned files at `output/<presentation_folder>/script_v{NNN}.md` and is NOT read by the handout.
  2. **Content summary** — the slide's `content_summary` field in `deck_state.json`.
  3. **Placeholder** — if both sources are empty, render the literal string `"(no notes available)"`. Silent empty cells are forbidden — every handout cell MUST contain either real text or the explicit placeholder so missing notes are visible on inspection.

  See BC-11.15a for the section-extraction grammar and BUG-AUDIT-68 for the original defect.
- **REQ-HAND-4:** *(BUG-AUDIT-21 — superseded by REQ-HAND-6)* The handout MUST be written as `handout_v{NNN}.pdf` with `NNN` zero-padded to three digits. The output directory and the version-derivation rule are defined in REQ-HAND-6; the earlier version of this requirement (which routed handouts through `output/<presentation_folder>/` and derived `NNN` from `handout_count + 1` in the presentation record) is discarded in favor of the decoupled path. See BUG-AUDIT-21.
- **REQ-HAND-5:** *(BUG-AUDIT-21 — rewritten)* The handout MUST use its own dedicated stylesheet, shipped as `handout.css` beside the handout module (workspace: `src/unit_11/handout.css`; delivered plugin: `src/debrief/handout.css`). The stylesheet is optimized for print density and ink efficiency — grayscale where feasible, minimal whitespace, class-based multi-column layout. The handout module loads it at render time and inlines it into the generated HTML. The handout MUST NOT read `assets/style.css` and MUST NOT require `style_locked: true` in `deck_state.json`. Rationale: the handout is a leave-behind reference document, not a branded artifact; print optimization takes precedence over deck visual continuity. Slide thumbnails are still rendered from `output/screenshots/` as before. The handout layout itself (margins, grid, text placement) is handled by class rules in `handout.css`; the handout module (`debrief.handout`) is responsible only for class-based markup generation.
- **REQ-HAND-6:** *(BUG-AUDIT-21 — rewritten)* The handout skill is **independent of `/debrief:export`** and runs on any project with at least one approved non-backup slide. Output goes to `output/handouts/handout_v{NNN}.pdf`, where `NNN` is filesystem-derived: the handout module scans `output/handouts/` for existing `handout_v*.pdf` files and picks `(max + 1)` (or `1` if none). The `output/handouts/` directory is created on first invocation via `mkdir(parents=True, exist_ok=True)`. Handout does NOT consult `deck_state.presentations` and does NOT mutate `deck_state.json`. Preconditions (validated at entry, before any Playwright import or browser launch, in the order defined by BC-11.16): (1) `deck_state.json` exists and is readable; (2) at least one slide has `status == "approved"` and `backup != True`. On any precondition failure, the module prints a descriptive message identifying the missing prerequisite and exits with code 2. Rationale: a user may want to produce a handout without first generating a projected-deck PDF — the handout is a different artifact with different use cases (distribution, pre-reading, note-taking reference). See BC-11.15 (handout.css), BC-11.16 (fail-fast preconditions), BC-11.17 (decoupled output path), and BUG-AUDIT-21.
- **REQ-HAND-7:** When `/debrief:handout` is invoked while gate G4.6 is pending, the skill MUST run the handout module to generate the requested handout and then return WITHOUT consuming the pending gate. G4.6 is re-presented after the skill completes, allowing the user to also generate the other layout, a script, or select DONE. The skill does not write to `debrief_state.json` and does not clear `pending_gate`.

### 14.9 Save (`/debrief:save`)

- **REQ-SAVE-1:** The save skill MUST create a named snapshot of `deck_state.json` and `ledger.jsonl` at the time of invocation. The snapshot does NOT include `debrief_state.json`; snapshots capture deck content state only. Pipeline control state is session-specific and is not snapshotted. There is no restore command; users wishing to restore a snapshot must manually copy the files back into the project directory.
- **REQ-SAVE-2:** Snapshots MUST be written to `output/snapshots/<label>/` inside
  the project directory. Snapshots survive `/debrief:restore` — restore overwrites `deck_state.json` from a snapshot but does not delete `output/` or its contents. *(BUG-AUDIT-22: the old `/debrief:reset` deleted `output/`, destroying snapshots; `/debrief:restore` does not.)*
- **REQ-SAVE-3:** The save skill MUST accept an optional label argument. If no label is provided, use the format `YYYYMMDD_HHMMSS` (e.g., `20260410_143022`) — default timestamp labels bypass sanitization. If the user provides a custom label, the label is sanitized using the Debrief Identifier Sanitization Algorithm (Section 24.10.1) with `max_length=50` before use as the directory name. If a snapshot with the sanitized label already exists, append a numeric suffix (e.g., `_2`, `_3`) to avoid overwriting.

  Label validation: the label MUST contain only alphanumeric characters, underscores, and hyphens. Other characters (including slashes, spaces, unicode) are rejected with an error: `Invalid label: labels may contain only letters, numbers, underscores, and hyphens.`

  On successful save, the skill MUST print: `Snapshot saved: <label> (deck_state.json, ledger.jsonl)` and return without modifying `debrief_state.json`.

### 14.10 Restore (`/debrief:restore`) *(BUG-AUDIT-22 — rewritten from `/debrief:reset`)*

BUG-AUDIT-22 replaced the old hard-delete `/debrief:reset` with a backup-restore command renamed to `/debrief:restore`. The hard-delete behavior is permanently dropped. See the BUG-AUDIT-22 Bug Catalog entry for rationale, Prior-Art for Rebuild, and the full architectural context.

- **REQ-RESTORE-1:** `/debrief:restore` has two invocation modes:
  - **List mode** (`/debrief:restore` with no label argument): scan `output/snapshots/` for valid snapshot directories (each must contain `deck_state.json`), print one line per snapshot with label and contents (`deck_state.json[, ledger.jsonl]`), and return. If no snapshots exist, print `"No snapshots found. Run '/debrief:save' to create one."` and return. Does not modify any files.
  - **Restore mode** (`/debrief:restore <label>`): restore the project to the named snapshot. The restore sequence is defined in REQ-RESTORE-2.
- **REQ-RESTORE-2:** The restore sequence (restore mode) MUST execute these steps in order:
  1. **Validate snapshot**: `output/snapshots/<label>/deck_state.json` must exist. If not, print a descriptive message listing available snapshots and exit code 2.
  2. **Auto-save current state**: before overwriting anything, invoke `skill_save("pre_restore_<YYYYMMDD_HHMMSS>", project_root)` to create a safety-net snapshot. Print confirmation of auto-save. This makes every restore reversible — the user can restore back to the auto-save if they regret the operation.
  3. **Overwrite `deck_state.json`**: copy the snapshot's `deck_state.json` to the project root, replacing the current file.
  4. **Optionally restore `ledger.jsonl`**: if the snapshot directory contains `ledger.jsonl`, copy it to the project root (overwrite). If not, leave the current `ledger.jsonl` untouched.
  5. **Sweep orphan slide HTML**: read the restored `deck_state.json`, collect all slide slugs. Scan `slides/*.html`. Delete any `.html` file whose stem (filename without extension) is not in the slug set. Collect the list of swept filenames.
  6. **Write restore_log entry**: append a JSON line to `ledger.jsonl` recording: `{"event": "restore", "timestamp": "<ISO>", "restored_from": "<label>", "auto_saved_as": "pre_restore_<ts>", "swept_slugs": [...]}`.
  7. **Print confirmation**: one message to stderr summarizing what happened — source snapshot, number and names of swept slides, auto-save label.
- **REQ-RESTORE-3:** The restore operation MUST NOT touch any project file other than `deck_state.json`, `ledger.jsonl` (optionally), and `slides/*.html` files that fail the orphan-slug check. Specifically, the following files and directories are NEVER modified by restore: `CLAUDE.md`, `debrief_state.json`, `style_config.json`, `style_guide.md`, `deck_brief.md`, `.debrief/`, `assets/`, `output/` (except the auto-save write to `output/snapshots/`). This is a deliberate design constraint: restore rolls back the deck content state only, not the entire project. Session state, style decisions, and project scaffolding survive the restore.
- **REQ-RESTORE-4:** The function MUST NOT use `input()` or any other blocking stdin call. The consultant passes the label as a function parameter via the Task tool. The conversational flow is mediated by the consultant agent, not by the restore function itself. This replaces the old REQ-RESET-3 `input("Type RESET")` pattern, which is an anti-pattern in Claude Code plugins.

### 14.11 Quit (`/debrief:quit`)

- **REQ-QUIT-1:** The quit skill MUST perform a clean shutdown. The shutdown sequence is:

  1. **Safe-checkpoint wait:** If a dispatch cycle is in progress (an agent is running), quit MUST wait for the current action to complete before proceeding. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)* Quit MUST NOT abort an in-flight agent invocation mid-turn. If the red-green cycle (`sub_phase: 'red_green'`) is active, quit MUST wait for the current iteration (Slide Maker + QA hook + snapshot update) to complete. `red_green_iteration` and the current best-known-good snapshot are saved to disk; intermediate snapshots in `.debrief/snapshots/<slug>_iter_*.html` are retained for resume.
  2. **Flush state:** Write any pending updates to `debrief_state.json` and `deck_state.json`. Verify both files are valid JSON with correct `state_hash`.
  3. **Flush ledger:** Ensure `ledger.jsonl` is flushed to disk.
  4. **Clean transient artifacts:** Remove `.debrief/task_prompt.md` and any temporary files in `.debrief/` that are not needed for resume. Retain: `.debrief/briefs/`, `.debrief/snapshots/` (if red-green is mid-cycle, per REQ-SLIDE-13 exception), `.debrief/approval_*.json` (if present), `.debrief/gate_data.json` (if present), `.debrief/diagnostic_*.md` (if the post-diagnostic gate is still pending), and **`.debrief/draft/` (if `pending_gate` is `G2.1_style_config_review` or the current sub_phase is `style/style_dialog` / `style/style_review`, so the Phase 2 style draft survives across resume and the user does not lose in-progress style work).**
  5. **Print summary** in the canonical format:
     ```
     Session saved.
       Phase: <phase>/<sub_phase>
       Archetype: <archetype>
       Approved slides: <N>
       In-progress: <slug or 'none'>
     Run `debrief` in this directory to resume.
     ```
  6. Exit the Claude Code session.
- **REQ-QUIT-2:** If the user exits the session without invoking `/debrief:quit`
  (e.g., Ctrl-C, closing the terminal), the system MUST NOT lose data. All state
  files (`debrief_state.json`, `deck_state.json`, `ledger.jsonl`) are written to
  disk after every gate transition and agent completion (see NFR-REL-1). The quit
  skill provides a *clean* shutdown with summary and cleanup; an unclean exit
  is survivable but may leave transient artifacts in `.debrief/`.
- **REQ-QUIT-3:** The quit skill is available at any time during any phase. It
  does not require confirmation. The user can quit mid-group, mid-slide, or
  mid-export-dialog. The pipeline state records exactly where the session stopped,
  enabling resume from that point.

### 14.12 Resume and Project Lifecycle

- **REQ-LIFE-1:** A debrief project has a defined lifecycle: **creation →
  authoring → deliverable → (optional) update rounds → (optional) further
  deliverables**. Each deliverable is an export (PDF + optional script) written
  to a dated presentation folder. The project is considered active as long as
  future updates are possible.
- **REQ-LIFE-2:** Running `debrief` (bare, no subcommand) in a directory
  containing `deck_state.json` MUST resume the existing project. The routing
  script reads `debrief_state.json` and picks up exactly where the last session
  ended — same phase, same sub_phase, same pending gate. No data is lost between
  sessions. Running `debrief` in a directory without `deck_state.json` MUST print
  an error: "No project found. Run `debrief new` to create one." and exit.
- **REQ-LIFE-3:** The project MAY be reopened at a future date to update the
  presentation. An update round follows the same pipeline phases as the initial
  authoring, but starts from the existing deck state:
  - The Consultant loads `deck_brief.md` and `deck_state.json`, reviews the
    existing slides with the user, and identifies what needs to change.
  - The update may be **minimal** (e.g., changing the title slide date and
    audience name) or **substantial** (e.g., adding new sections, rewriting
    multiple slides, changing the narrative arc).
  - The user works through the same group cycle (Phase 3) for any slides that
    need modification, using `/debrief:slide <slug>` for revisions and the
    Consultant for new groups.
  - Each update round ends with a new deliverable via `/debrief:export`, which
    creates a new dated folder in `output/`. Previous deliverables are never
    modified (see Section 24.13).
- **REQ-LIFE-4:** If the user stops a session before producing a deliverable
  (e.g., via `/debrief:quit`, Ctrl-C, or closing the terminal), the project
  state is preserved. The next `debrief` invocation resumes from the exact
  pipeline position. The user does not need to redo completed work — approved
  slides, locked style, and completed groups are all retained in
  `deck_state.json` and `debrief_state.json`.
- **REQ-LIFE-5:** When resuming a project that was previously in the `complete`
  phase (a deliverable was produced), the Consultant MUST greet the user and
  ask: **"Welcome back. Would you like to update the existing presentation or
  start a new version for a different audience?"** The response determines the
  scope of the update round. The pipeline transitions to `discovery/dialog`
  with the existing `deck_brief.md` and `deck_state.json` retained (see
  Section 14.17, transition from `complete`).

### 14.13 User-Provided Images (`assets/images/`)

- **REQ-ASSET-1:** The user MAY provide image files (JPG, PNG, SVG) by referencing a local file path in conversation with the Slide Maker or the Consultant. The referenced file MUST be copied into `assets/images/<slug>_<original_filename>` (prefixed with the target slide slug to avoid name collisions). The original file is never modified. The slide HTML references the local copy via a relative path (`../assets/images/...`).

  **Implementing module.** The image copy operation is performed by a dedicated helper module `debrief.asset_ingest` (part of Section 23 step 8's Content Utility Modules set — the same logical grouping as `debrief.math_renderer`). Its CLI contract:

  ```
  python -m debrief.asset_ingest --src <source_path> --slug <slug> --project-root <path>
  ```

  Postcondition: the source file is copied to `<project_root>/assets/images/<slug>_<basename(source_path)>` atomically (write-to-tmp then rename). Exit code 0 on success; exit code 1 on source-not-found or copy failure; exit code 3 on usage error. The module does NOT modify `deck_state.json` or `debrief_state.json` — it only writes the asset file.

  **Caller.** The Slide Maker invokes `debrief.asset_ingest` via Bash when the user references a local image path in conversation. The Slide Maker's `SKILL.md` (actually the slide-maker agent's system prompt) allowed-tools list MUST permit Bash invocations targeting `python -m debrief.asset_ingest`. The PreToolUse write-authorization hook MUST permit writes to `assets/images/*` (this path is already allowed post-style-lock per REQ-STYLE-6 — the scope is project-directory writes, not specifically `slides/` or `assets/style.css`).

  **Consultant pathway.** If the user provides an image path during the Consultant's discovery dialog (e.g., "I have a photo of the patient"), the Consultant records the intent in `deck_brief.md` and in the relevant slide brief, but does NOT invoke `debrief.asset_ingest` — asset ingestion happens at slide-authoring time, when the slug is known.
- **REQ-ASSET-2:** SVG files are treated as vector assets and embedded directly into the slide HTML via an `<img>` tag with a local `src`, or inlined as `<svg>` if the Slide Maker determines inlining is needed for styling (e.g., recoloring paths to match the palette). The choice between `<img>` and inline `<svg>` is a Slide Maker decision guided by the style guide. Inlined SVGs MUST have their colors adapted to use CSS custom properties from `assets/style.css` where feasible.
- **REQ-ASSET-3:** Raster images (JPG, PNG) are referenced via `<img>` tags with local `src` paths. The Slide Maker MUST NOT attempt to modify raster image content (no resizing, cropping, or color adjustment of the file itself). Sizing and positioning are controlled via CSS classes defined in `assets/style.css`.
- **REQ-ASSET-4:** The user MAY request one of two placement modes for a provided image:

  **Standalone image slide:** The image is the sole content of a dedicated slide. The Slide Maker generates a slide HTML that centers the image on a slide background consistent with the locked style (matching background color, margins, and optional title/caption styled per the style guide). The image is scaled to fill the available area while respecting INV-05 (10% margin) and INV-08 (16:9 aspect ratio).

  **Embedded in a multi-element slide:** The image is placed alongside other content (text, diagrams, formulas). The Slide Maker positions the image using the layout grammar from the style guide (e.g., image in the right column, text in the left). The image size is determined by the layout grammar, not hardcoded.
- **REQ-ASSET-5:** In both placement modes, the Slide Maker MUST ensure the image slide is **visually homogeneous** with the rest of the deck. This means:
  - Slide background color matches `var(--color-background)`
  - Any title or caption text uses the deck's font and color scheme
  - Image borders or shadows (if any) are defined in `assets/style.css`, not inline
  - The image does not bleed to the edge — INV-05 margins are respected

### 14.14 Presentation Archetypes

Debrief supports ten presentation archetypes. Each archetype encodes a rhetorical
direction, slide density, disclosure emphasis, audience assumptions, acknowledgment
policy, duration, sub-modes, and archetype-specific rules. The Consultant MUST
select an archetype during the discovery dialog and configure all downstream
behavior accordingly. The archetype choice is recorded in `deck_brief.md` and
propagated to every slide brief.

- **REQ-ARCH-1 (Lab Meeting):** The Consultant MUST configure lab meeting decks
  as short, dense, internal-audience presentations. Slide count: 2--3 slides.
  Duration: max 10 minutes. Font sizing: serif titles at minimum 36 px, sans-serif
  body at minimum 20 px. Structure: brief context, data/results, next steps.
  Progressive disclosure is available via multi-slide builds. Dense slides are
  acceptable provided legibility from the back of a room with a flat screen (not
  projector) is maintained. The Consultant MUST ask for data figure assets early;
  they are expected but not mandatory. Audience: implied (lab members, familiar with
  the project). Acknowledgment slide: optional.

- **REQ-ARCH-2 (Conference Talk):** The Consultant MUST always ask the user for
  duration first (range: 10--45 minutes). Strictly one idea per slide (enforced,
  not suggested). The Consultant MUST actively propose a narrative arc (hero
  journey, antagonist framing). Enhanced narrative structure emphasis during the
  briefing phase. Q&A calibration: the Consultant MUST ask for Q&A duration and
  size the backup deck at approximately one slide per 1.5 minutes of Q&A. Defensive
  backup session: the Consultant role-plays as a field expert using Socratic method
  and proposes alternatives when the user is stuck. Body text may use smaller font
  sizes than lab meeting (projector context allows it). Audience: implied (field
  peers at a conference). Acknowledgment slide: required.

- **REQ-ARCH-3 (Seminar):** Duration: 45 minutes default; the Consultant MUST ask
  to confirm. Audience: peers, standalone or loosely connected to the presenter's
  own research. May include the presenter's own research; discussion-oriented. Slide
  style: closer to conference talk (cleaner layouts, not densely packed). One idea
  per slide is preferred but not as strictly enforced as in conference talk.
  Progressive disclosure: available but not heavy. Handout: optional. Rhetoric:
  clarity over persuasion; rhetoric serves engagement. Logical progression replaces
  hero journey. The Consultant MUST frame: "What should the audience understand by
  the end?" The Consultant MUST ask about continuity: "Is this part of a series?"
  (unlikely but possible). The Consultant MUST perform a prerequisite check: "What
  can I assume the audience already knows?" Acknowledgment slide: required.

- **REQ-ARCH-4 (Lecture):** Duration: variable, likely part of a course series.
  Series continuity is the DEFAULT assumption — the Consultant MUST ask "Which
  lesson?" rather than "Is this part of a series?" Pure teaching: established
  knowledge; the presenter's own research is optional. Dense slides (similar to lab
  meeting), heavy progressive disclosure. Handout is ASSUMED (students need study
  material). Rhetoric: clarity is paramount; rhetoric serves student engagement. The
  Consultant MUST frame: "What is the learning objective? What should students be
  able to DO after this?" Prerequisite check references the course structure.
  Audience: implied (students in the course). Acknowledgment slide: no.

- **REQ-ARCH-5 (Journal Club):** The Consultant MUST ask: "Single paper or topic
  review across multiple papers?" This determines the sub-mode:

  **Single-paper mode:** Figure-by-figure dissection following the paper's own
  logic, with deep critique of methods and results. The paper PDF is the primary
  asset; ALL paper elements (every figure, every table, key equations) are candidate
  slides. The Consultant MUST propose all candidates and negotiate cuts with the
  user.

  **Multi-paper mode:** Thematic narrative across papers (seminar-like structure)
  with comparative critique. Additional assets accepted: other papers, custom
  diagrams.

  In both modes, the Consultant MUST act as an ethical guardian: ensure fair
  representation of the paper's claims, push back on misrepresentation or logical
  fallacies, and apply charitable criticism. If the user insists on a framing the
  Consultant considers unfair, the Consultant MUST comply but register dissent in
  the slide brief. The Consultant MUST verify that the presenter understands the
  methods (never present what you cannot defend). Duration: ask (typically 15--30
  minutes). Acknowledgment slide: optional.

- **REQ-ARCH-6 (Grant Panel):** Duration: ask (typically 10--15 minutes). The
  Consultant MUST ask for assets first: grant guidelines document and written
  proposal (both optional but common). When guidelines are provided, the Consultant
  MUST read them, extract evaluation criteria, and map the proposal to those
  criteria. Slide structure is DERIVED FROM the guidelines' evaluation criteria, not
  from a fixed template. The Consultant MUST ask whether guidelines require a budget
  slide. Q&A calibration: harshest sparring mode — the Consultant role-plays as a
  skeptical grant reviewer. Every slide MUST pass a "so what" test: each slide must
  justify funding in isolation. Rhetoric: heavily persuasive, logic-dominant,
  credibility-heavy, minimal pathos. Narrative arc: worth problem, right idea, I can
  deliver, real impact. This is NOT a hero journey — it is a structured argument /
  legal case. Every claim MUST be backed by evidence or credentials. The Consultant
  MUST coach: "Every slide is a premise — what is the argument?" Audience: implied
  (grant reviewers). Acknowledgment slide: required.

- **REQ-ARCH-7 (Job Talk):** Duration: ask (typically 20--30 minutes for postdoc,
  45 minutes for PI/faculty). The Consultant MUST ask two qualifying questions:
  "Postdoc or PI/faculty position?" and "What department/lab? What do they work on?"
  This determines the sub-mode:

  **Postdoc mode:** Older work establishes credibility; emphasis on recent work.
  Close with "what I bring to your lab."

  **PI mode:** Closer to grant panel rhetoric — vision-driven. Close with "why your
  department needs this."

  **PhD application mode:** Lead with motivation and learning ability over results.
  Show research aptitude. Humility is appropriate. The presenter MUST demonstrate
  deep knowledge of the target lab.

  Career trajectory slide: optional, brief. Q&A calibration: deep sparring covering
  both scientific AND career questions. Rhetoric: honest but directed persuasion;
  logic + credibility dominant. Audience: implied (hiring committee). Acknowledgment
  slide: required.

- **REQ-ARCH-8 (Thesis Discussion):** Primary asset: thesis document (mandatory,
  PDF). The Consultant MUST read the thesis, propose a slide structure mapped to
  chapters, then aggressively cut to highlights. Duration: ask (PhD typically 30--45
  minutes, Master's 20--30 minutes). The Consultant MUST ask: "PhD or Master's
  defense?" This determines the sub-mode:

  **PhD mode:** Hero journey narrative, beautiful slides, LESS content MORE impact.
  The goal is to demonstrate communication mastery. Nothing boring — the Consultant
  MUST push: "What is the exciting version?"

  **Master's mode:** All of PhD mode plus emphasis on showing learning, technique
  mastery, and scientific method understanding.

  Rhetoric: compelling narrative, ethos through presentation quality. Backup slides:
  methodology challenges, alternative interpretations. The Consultant MUST probe:
  "Why did you choose this method? Can you defend it?" Audience: implied (thesis
  committee). Acknowledgment slide: required.

- **REQ-ARCH-9 (Investor Pitch):** Stage matters: the Consultant MUST ask "Pre-
  seed, seed, or Series A?" because the answer changes emphasis. The Consultant MUST
  ask for the existing pitch deck as an asset. The Consultant MUST ask: "What is the
  ask? How much, for what?" Structure: problem, solution, market, traction, team,
  ask. Vocabulary is business, not academic (TAM/SAM, traction, moat, burn rate).
  Rhetoric: opportunity-driven persuasion. Pre-seed presentations are vision-heavy;
  Series A presentations are metrics-heavy. Audience: implied (investors).
  Acknowledgment slide: optional (the team slide serves a similar purpose).

- **REQ-ARCH-10 (Custom / Meta-Archetype):** Universal principles only; no
  archetype-specific defaults are applied. The Consultant MUST open with four
  questions: "What is the occasion?", "Who is the audience?", "How long?", "What do
  you need to achieve?" Based on the answers, the Consultant MUST propose which
  archetype principles to borrow and MUST explicitly name the borrowed rules. Custom
  is not the absence of rules — it is the conscious selection of rules from other
  archetypes.

**Archetype comparison table.** The Consultant uses this table as a reference when
configuring decks. Blueprint implementers use it to verify completeness.

| Archetype         | Duration          | Density     | Disclosure    | Narrative Arc                  | Rhetoric Emphasis             | Sparring        | Ack.     | Sub-Modes                           |
|-------------------|-------------------|-------------|---------------|--------------------------------|-------------------------------|-----------------|----------|-------------------------------------|
| Lab Meeting       | max 10 min        | Dense       | Multi-build   | Context-data-next steps        | Clarity                       | Light           | Optional | --                                  |
| Conference Talk   | 10--45 min (ask)  | 1 idea/slide| Multi-build   | Hero journey / antagonist      | Persuasion + logic            | Field expert    | Required | --                                  |
| Seminar           | 45 min (confirm)  | Clean       | Available     | Logical progression            | Clarity + engagement          | Light           | Required | --                                  |
| Lecture           | Variable (series) | Dense       | Heavy         | Teaching progression           | Clarity + student engagement  | None            | No       | --                                  |
| Journal Club      | 15--30 min (ask)  | Varies      | Varies        | Paper logic / thematic         | Clarity + critique            | Ethical guardian | Optional | Single-paper, multi-paper           |
| Grant Panel       | 10--15 min (ask)  | Structured  | Minimal       | Structured argument            | Logic + credibility           | Skeptical       | Required | --                                  |
| Job Talk          | 20--45 min (ask)  | Clean       | Moderate      | Career + research arc          | Logic + credibility           | Deep (sci+career)| Required | Postdoc, PI, PhD application        |
| Thesis Discussion | 20--45 min (ask)  | Highlights  | Moderate      | Hero journey / chapter map     | Narrative + ethos             | Deep (methods)  | Required | PhD, Master's                       |
| Investor Pitch    | Varies (ask)      | Structured  | Minimal       | Problem-solution-traction-ask  | Opportunity-driven persuasion | Light           | Optional | Pre-seed, seed, Series A            |
| Custom            | Ask               | Ask         | Ask           | Borrowed from selected rules   | Borrowed                      | Borrowed        | Ask      | --                                  |

### 14.15 Universal Presentation Principles

These principles apply to ALL archetypes unless an archetype-specific rule in
Section 14.14 explicitly overrides them.

**Rhetoric and narrative.**

- **REQ-UNIV-1 (Organic Narrative Flow):** Slides MUST flow as a continuous
  narrative. No context switches between slides — every transition MUST feel natural
  to the audience. The Consultant MUST verify narrative flow during the briefing
  phase and reject slide orderings that produce abrupt topic changes.
- **REQ-UNIV-2 (Hook and Conclusion):** Every presentation MUST open with a hook
  (a compelling opening that captures attention) and close with a high-tone
  conclusion (a forward-looking or inspiring takeaway). The Consultant MUST propose
  both during the briefing phase.
- **REQ-UNIV-3 (Rhetoric Rotation):** The Consultant MUST rotate rhetorical modes
  across slides: ethos (credibility, respect for the audience), pathos (adversity,
  emotion, human stakes), and logos (hypothesis, data, deduction). No single mode
  SHOULD dominate the entire deck unless the archetype mandates it (e.g., grant
  panel is logos-dominant by design).
- **REQ-UNIV-4 (Narrative Arc Suggestion):** The Consultant MUST suggest a
  narrative arc, antagonist framing, or hero journey structure. The Consultant MUST
  NOT force any narrative structure — suggestions are negotiated with the user.
- **REQ-UNIV-5 (Transition Sentences):** Every slide in the presenter script MUST
  include transition sentences leading to the next slide. These transitions are
  written by the Consultant during slide brief assembly and refined by the Slide
  Maker during script generation.

**Progressive disclosure.**

- **REQ-UNIV-6 (Disclosure Briefing):** The Consultant MUST ask during the
  briefing phase: "Do you want progressive disclosure?" The answer is recorded in
  `deck_brief.md` and applied globally unless overridden per slide.
- **REQ-UNIV-7 (Build Groups):** During production, the user declares build groups
  (which elements appear together on each build step). The Consultant describes the
  complete slide and negotiates disclosure order with the user. The Slide Maker
  produces build files: `<slug>_build_1.html`, `<slug>_build_2.html`, ...,
  `<slug>.html` (final complete slide). All build files share the same layout and
  incrementally add content.

**Assets, references, citations, and background papers.**

- **REQ-UNIV-8 (Asset Solicitation):** The Consultant MUST ask for assets early in
  the briefing phase. Assets are expected but never mandatory. Asset types include:
  data figures, images, diagrams, paper PDFs, BibTeX files, grant guidelines, thesis
  documents, pitch decks, and video files.
- **REQ-UNIV-9 (Asset Sourcing Enforcement):** The Consultant MUST enforce asset
  sourcing for every visual element on every slide. Each asset MUST have one of:
  a bibliographic reference, a credit line, or an "unpublished data" label. No
  visual element may appear without attribution.
- **REQ-UNIV-10 (Background Papers):** The Consultant MUST ask for background
  paper links, DOIs, PDFs, or BibTeX entries. When provided, the system uses
  `paper_analyzer` to extract claims and figures. The Consultant builds background
  slides autonomously with proper citations derived from the analysis.
- **REQ-UNIV-11 (Citation Formatting):** References on slides MUST use smaller,
  lower-contrast text positioned at the bottom of the slide. Statistical details
  MUST use a smaller font with intentionally lower contrast (visible on close
  inspection but not dominant). BibTeX input is supported for precise citation
  formatting.

**Confidentiality.**

- **REQ-UNIV-12 (Confidentiality Check):** For seminar and lab meeting archetypes,
  the Consultant MUST ask: "Does any data involve unpublished or confidential
  material?" If yes, a visible tag MUST be placed in the title area of affected
  slides: `[CONFIDENTIAL — DO NOT DISTRIBUTE]` rendered in the deck's accent color.
  If the user marks data as confidential in a public archetype (conference talk,
  lecture), the Consultant MUST warn that the archetype implies public distribution
  and confirm the user's intent.

**Backup slides and sparring.**

- **REQ-UNIV-13 (Sparring Protocol):** For all archetypes, the Consultant MUST
  conduct Socratic sparring to anticipate audience questions. The Consultant role-
  plays as a field expert, challenges weak arguments, and proposes alternatives when
  the user is stuck. For conference talk, job talk, and grant panel archetypes, the
  Consultant MUST additionally perform Q&A time calibration: the backup deck is
  sized at approximately one slide per 1.5 minutes of Q&A time. Grant panel sparring
  is the harshest (skeptical reviewer persona); job talk sparring covers both
  scientific and career questions.

**Visual rules and layout.**

- **REQ-UNIV-14 (Font Legibility):** All text MUST be readable from the back of
  the room. Minimum font sizes are archetype-dependent (see Section 14.14) but MUST
  never fall below 16 px for any text element. Title text MUST be at minimum 28 px
  across all archetypes.
- **REQ-UNIV-15 (White Space):** White space is intentional, not wasted. The Slide
  Maker MUST NOT fill empty space with decorative elements. Layouts MUST breathe.
- **REQ-UNIV-16 (Slide Numbering):** Every slide MUST display a slide number.
  Numbering is small and positioned in a bottom corner. Numbering style is defined
  in `assets/style.css`.
- **REQ-UNIV-17 (Closing Slide Content):** The closing slide MUST contain a
  takeaway message, not "Thank you" or "Questions?" The takeaway reinforces the
  presentation's core argument.
- **REQ-UNIV-18 (Acknowledgment Slide):** Whether an acknowledgment slide is
  included depends on the archetype (see the archetype comparison table in Section
  14.14). When required or requested, the Consultant MUST solicit acknowledgment
  content during the briefing phase.

**Video handling.**

- **REQ-UNIV-19 (Video Mode):** The Consultant MUST ask the user about
  presentation mode (PDF or browser) when video assets are present. In browser mode:
  video is embedded as inline `<video>` elements with playback controls. In PDF
  mode: video is rendered as a clickable still-frame that links to the system video
  player. The presenter script MUST include a video cue with duration for each video
  slide. A fallback instruction MUST be included in case the PDF link is blocked by
  the presentation environment.

**Time pacing.**

- **REQ-UNIV-20 (Pacing Checkpoints):** The presenter script MUST include time
  pacing checkpoints (e.g., "At 5 minutes you should be on slide 3"). Checkpoints
  are calibrated to the archetype's duration and the number of slides.

**Audience calibration.**

- **REQ-UNIV-21 (Audience Calibration):** For archetypes where the audience is not
  fully implied, the Consultant MUST ask qualifying questions to calibrate content
  depth and vocabulary. Examples: seminar prerequisite check ("What can I assume the
  audience already knows?"), lecture prerequisite check (references course
  structure), job talk department research alignment ("What does the department work
  on?").

### 14.16 Presentation Mode (`/debrief:present`)

The `/debrief:present` command launches a browser-based full-screen presentation of
the current deck. It is separate from `/debrief:export` (PDF generation) and
`/debrief:view` (preview/review mode).

- **REQ-PRESENT-1 (Browser-Based Full-Screen Presentation):** The
  `/debrief:present` command MUST generate a file at `output/presentation.html` that
  loads all slides in deck order, one at a time, in full-screen layout. The
  generated file is a self-contained vanilla JavaScript application (approximately
  50--80 lines, no framework dependencies). The file is opened in the user's default
  browser.
- **REQ-PRESENT-2 (Keyboard Navigation):** The presentation viewer MUST support
  the following keyboard controls: left arrow and up arrow navigate to the previous
  slide; right arrow, down arrow, and space bar navigate to the next slide; `F` or
  `F11` toggles browser full-screen mode; `Escape` exits full-screen mode. No other
  keyboard shortcuts are required.
- **REQ-PRESENT-3 (Progressive Disclosure Navigation):** When slides have
  progressive disclosure builds (see REQ-UNIV-7), each build step is a separate
  navigation entry. Pressing "next" advances through build steps before moving to
  the next slide. The navigation sequence is: `<slug>_build_1.html`,
  `<slug>_build_2.html`, ..., `<slug>.html`, then the next slide's first build (or
  full slide if no builds exist).
- **REQ-PRESENT-4 (Inline Video Playback):** Slides containing `<video>` elements
  MUST play video inline within the presentation viewer. The presenter controls
  playback using the browser's native video controls. Video does not auto-play on
  slide entry.
- **REQ-PRESENT-5 (Output Location):** The generated presentation file MUST be
  written to `output/presentation.html` within the project directory. If the
  `output/` directory does not exist, it MUST be created. The file is regenerated on
  every `/debrief:present` invocation (overwriting any previous version).

### 14.17 LaTeX Math Rendering

- **REQ-LATEX-1:** The user MAY provide LaTeX math source code in conversation with the Slide Maker. LaTeX input is delimited by `$...$` for inline math and `$$...$$` for display (block) math. The Slide Maker MUST recognize these delimiters in user messages and in slide briefs from the Consultant.
- **REQ-LATEX-2:** The system MUST render LaTeX math to a visual representation in the slide HTML. The rendering is performed by a **math renderer module** (`debrief.math_renderer`) that accepts LaTeX source and produces HTML output. The module's interface is:

  **Input:** A LaTeX math string (without delimiters — the caller strips `$` / `$$`).
  **Output:** An HTML fragment that, when inserted into the slide, displays the rendered math.
  **Modes:**
  - `inline` — produces an inline HTML element suitable for embedding within a text paragraph
  - `display` — produces a block-level HTML element suitable for centering on its own line

  **Contract:**
  ```
  python -m debrief.math_renderer --mode inline --input "E = mc^2"
  # stdout: HTML fragment

  python -m debrief.math_renderer --mode display --input "\int_0^\infty e^{-x} dx = 1"
  # stdout: HTML fragment
  ```

  Exit code: 0 on success, 1 on parse error (invalid LaTeX). On error, stderr contains the parse error message.

  If the math renderer fails (exit code 1), the Slide Maker MUST NOT write the slide HTML. Instead, it MUST report the LaTeX parse error to the user and request corrected LaTeX input. Math renderer failure is not handled by the red-green cycle -- it is a pre-write validation failure.
- **REQ-LATEX-3:** The canonical math rendering implementation is **client-side KaTeX bundled as static assets** in the plugin's `assets/vendor/` directory, following the same pattern as Mermaid and rough.js (Section 24.27). The implementation is:

  1. `katex.min.js` and `katex.min.css` are bundled in `${CLAUDE_PLUGIN_ROOT}/assets/vendor/` and copied to the project's `assets/vendor/` at `debrief new` time.
  2. The `debrief.math_renderer` Python module does NOT render math server-side. It emits an HTML wrapper: `<span class="katex-src" data-mode="inline|display">{escaped_latex}</span>` plus a reference to an initialization script that calls `katex.render()` on all `.katex-src` elements at browser load time.
  3. Rendering happens inside the Chromium browser (via Playwright) at screenshot time for QA, and again at PDF render time for export. Math appears in both the QA screenshot and the exported PDF because both use the same browser rendering path.
  4. The `debrief.math_renderer` module requires no external runtime dependencies — it is a pure Python string formatter. It MUST validate that the input is well-formed LaTeX math (via a simple bracket-balance check) and reject invalid input with exit code 1 and a clear stderr message before producing HTML.
  5. The KaTeX JavaScript library is the only component that actually renders math; it runs in the browser. No Node.js process, no subprocess, no Python port.

  **Math validation boundary.** The `debrief.math_renderer` module performs only surface well-formedness checks on the Python side: bracket balance on `{}`, balanced `\begin{...}\end{...}` environments, non-empty input, no null bytes. It does NOT maintain an allow-list of KaTeX commands — the source of truth for "supported" is KaTeX itself at browser render time. Unsupported-but-well-formed LaTeX (e.g., `\tikz`, `\pgfpicture`) passes the Python validation and produces a visible error placeholder at browser render time, which surfaces as a Tier 1 QA failure under REQ-QA-9 and re-enters the red-green cycle.

  This split (Python surface check + browser semantic check) is intentional: pre-write validation is fast and catches obvious errors; at-render validation is comprehensive and reuses KaTeX's own parser.

  This removes all Node.js dependencies from the Debrief runtime. The server-side `pdflatex` toolchain mentioned as a future extension remains a blueprint decision for v2.0+; the v1.1 implementation is strictly client-side KaTeX.
- **REQ-LATEX-4:** Rendered math MUST be visually consistent with the deck style:
  - Math font size MUST match the surrounding text context (body text size for inline, heading-appropriate size for display math in prominent positions)
  - Math color MUST use `var(--color-text-primary)` or the color of the surrounding text element
  - Display math MUST be centered horizontally and respect INV-05 margins
  - `assets/math/` is reserved for future use. The v1.1 canonical implementation (client-side KaTeX, REQ-LATEX-3) produces no asset files — math is rendered in-browser from HTML wrappers. The directory may be created by `debrief new` as a forward-compatibility placeholder but is not populated by any v1.1 code path. A future v2.0+ implementation that uses server-side SVG rendering would populate this directory.
- **REQ-LATEX-5:** For v1.0/v1.1, the system MUST support the following LaTeX math subset at minimum:
  - Standard math operators and symbols (`\sum`, `\int`, `\prod`, `\infty`, `\partial`, etc.)
  - Greek letters (`\alpha`, `\beta`, `\gamma`, etc.)
  - Fractions (`\frac{a}{b}`)
  - Subscripts and superscripts (`x_i`, `x^2`)
  - Square roots (`\sqrt{x}`)
  - Matrices (`\begin{pmatrix}...\end{pmatrix}`, `\begin{bmatrix}...\end{bmatrix}`)
  - Aligned equations (`\begin{aligned}...\end{aligned}`)
  - Common environments: `equation`, `aligned`, `cases`

  This subset is achievable with KaTeX out of the box. Full LaTeX class support (custom packages, `\usepackage`, TikZ, pgfplots) is **out of scope for v1.0/v1.1** but the rendering interface (REQ-LATEX-2, REQ-LATEX-3) is designed to accommodate it in future versions without spec changes.
- **REQ-LATEX-6:** The math renderer interface (REQ-LATEX-2) MUST be the **sole entry point** for all LaTeX rendering. No component may bypass the module and embed raw LaTeX source directly in slide HTML. This ensures that upgrading the renderer (e.g., from KaTeX to a full `pdflatex` toolchain) requires changing only the module implementation, not any calling code or slide templates.

### 14.15 Deterministic Routing Protocol

- **REQ-ROUTE-1:** Every agent invocation MUST be preceded by a **prepare step** that assembles the task prompt from the `context_files` specified in the action block. *(BUG-AUDIT-31: the prepare module is dead at runtime; the consultant handles context assembly via Tool calls.)* The task prompt is written to `.debrief/task_prompt.md`. The orchestrator passes this file's contents to the agent verbatim. The agent does NOT read the conversation history — it reads only the prepared context.
- **REQ-ROUTE-2:** The Consultant's conversation ledger (`ledger.jsonl`) MUST be used only by the **prepare script** to extract relevant prior context. The Consultant agent itself receives a prepared summary, not the raw ledger. This prevents the Consultant from re-reading its entire conversation history on every invocation.
- **REQ-ROUTE-3:** When control transfers between agents (Consultant to Slide Maker, Slide Maker to Consultant), the **receiving agent gets a fresh prompt** assembled by the prepare script. There is no shared conversation state between agents. The handoff contract is:
  - **Consultant to Slide Maker:** The prepare script writes the slide brief, style guide, and any user instructions into the task prompt. The Slide Maker does not see the Consultant's dialog history. (No exemplar is selected — the plugin does not ship an exemplar library per REQ-SLIDE-8; the Slide Maker MAY additionally receive the most recent 1-2 approved slides from `slides/` as in-deck few-shot context per REQ-SLIDE-8 non-normative guidance.)
  - **Slide Maker to Consultant (GROUP_APPROVED):** The prepare script writes the approved slide records, current deck_brief.md, and the "more slides?" question into the task prompt. The Consultant does not see the Slide Maker's fix iterations.
  - **Slide Maker to Consultant (ESCALATE_TO_CONSULTANT):** The prepare script writes the escalation description, current group state, and deck_brief.md into the task prompt.
  - **Consultant to Slide Maker (DETAIL_FIX):** The prepare script writes the specific slug, the user's detail instruction, and the current slide HTML into the task prompt.
- **REQ-ROUTE-4:** The debrief plugin MUST include a routing script (`debrief.routing`) and a state update script (`debrief.update_state`) that implement the six-step action cycle. *(BUG-AUDIT-31: `routing.py` is gutted -- all 13 public functions were deleted. The consultant agent handles all dispatch via Tool calls. This requirement is retained for historical reference.)* The orchestrator (the Claude Code main session) executes this cycle without reasoning about pipeline state. All routing decisions are made by the scripts, not by the LLM.
- **REQ-ROUTE-5:** The project `CLAUDE.md` (generated at init) MUST instruct the orchestrator to follow the six-step cycle. It MUST contain:
  - The routing script invocation command
  - The six-step cycle description
  - A prohibition on improvising pipeline flow
  - A prohibition on writing to `debrief_state.json` directly
- **REQ-ROUTE-6:** Machine gates MUST NOT require human input. *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)* The routing script detects the condition by reading state files and artifact timestamps. If a machine gate cannot be resolved (e.g., missing artifact), the routing script MUST emit an error action block that presents the problem to the user.
- **REQ-ROUTE-7:** The update_state script MUST validate that the gate response matches the gate's response grammar. For gates with literal responses, validation is exact string membership in `valid_responses`. For gates with parameterized responses, validation is grammar-based: the `update_state` script parses the user input against the gate's response grammar, extracts the payload (slug, figure numbers, instructions), writes the parsed payload to `.debrief/gate_data.json` per Section 24.21, and routes to the next state. Grammar mismatches are rejected with exit code 4 and the canonical message `Invalid response. Expected: <grammar>`. The orchestrator re-presents the gate until a valid response is received. This prevents the LLM from inventing novel transitions.

  **Response grammars for parameterized gates:**

  | Gate ID | Grammar |
  |---------|---------|
  | `G1.3_figure_selection` | `ALL \| <integer>( <integer>)*` where each integer is in range `[1, N]` (N = extracted figure count). |
  | `G2.1_style_config_review` | `STYLE APPROVED \| STYLE REVISE <non-empty feedback> \| REGENERATE PREVIEWS`. Delimiter for `STYLE REVISE` is a single space after the keyword (no colon); payload is trimmed of leading/trailing whitespace; empty payload is rejected with exit code 4. `STYLE APPROVED` and `REGENERATE PREVIEWS` are literal. *(BUG-AUDIT-29: renamed from STYLE NEEDS WORK to match code validator.)* |
  | `G3.3_slide_review` | `SLIDE APPROVED \| SLIDE REVISE` (literal; bare `SLIDE REVISE` is valid — prompts the user for instructions in the next turn). |
  | `G3.3_slide_review_post_diagnostic` | `SLIDE APPROVED \| SLIDE REVISE: <non-empty instructions>`. Bare `SLIDE REVISE` is rejected per REQ-SLIDE-5. |
  | `G3.4_group_review` | `GROUP APPROVED \| GROUP REVISE <slug>` where `<slug>` matches `^[a-z0-9_-]+$` and exists in the current group. |
  | `G3.V_view_dispatch` | `DETAIL FIX <slug> \| ESCALATE \| CONTINUE` where `<slug>` matches `^[a-z0-9_-]+$` and exists in the current group or deck. |

  The `valid_responses` column in Section 14.16 gate tables lists the response forms; the grammars above are the authoritative parsing rules. Literal-only gates (G1.1, G1.2, G3.5, G3.6, G4.1, G4.2, G4.3, G4.4, G4.6) use exact string membership; no grammar parsing is required.
- **REQ-ROUTE-8:** `debrief_state.json` MUST include a `state_hash` field — a SHA-256 hash of the state's content fields (excluding `state_hash` itself). The routing script verifies the hash on every read. If the hash doesn't match but the JSON content is valid and all field values are within expected ranges, the routing script re-computes the hash and emits a warning. If the content is malformed JSON or contains invalid field values, the routing script emits a fatal error requiring user intervention.
- **REQ-ROUTE-9:** At every human gate, the system MUST display a **gate prompt** that includes: (a) a brief description of what is being decided, (b) the valid responses, (c) available commands the user can run before responding (e.g., `/debrief:view`, `/debrief:quit`), and (d) a one-line description of what each response leads to. The gate prompt is assembled by the `prepare` script and included in the action block. The gate prompts are defined in Section 14.16.1.

### 14.16 Gate Catalog

Every decision point in the pipeline is a numbered gate with a type, a fixed vocabulary of responses, and deterministic transitions.

**Phase 1: Discovery**

| Gate ID | Type | Valid Responses | Context Loaded | Next State |
|---------|------|-----------------|----------------|------------|
| `G1.1_brief_review` | Human | `BRIEF APPROVED`, `BRIEF NEEDS WORK` | `deck_brief.md` | APPROVED: if papers provided → `discovery/paper_analysis`; else if a reference is provided (any modality) → G1.2 (reference style review); else → Phase 2 (`phase: "style"`, `sub_phase: "style_dialog"`). NEEDS WORK: stay in Phase 1, re-invoke Consultant |
| `G1.2_style_analysis` | Human | `USE AS BASELINE`, `USE FOR INSPIRATION`, `IGNORE` | `.debrief/draft/derived_style_guide.md`, reference thumbnail images under `assets/reference/slides/` | BASELINE: Phase 2 with reference-derived draft pre-filled. INSPIRATION: Phase 2 with derived draft as context. IGNORE: Phase 2 without the derived draft. All three → `style/style_dialog`. |
| `G1.3_figure_selection` | Human | `ALL`, `<number> <number> ...` (space-separated figure numbers) | `.debrief/paper_analysis_<paper_slug>.md` (extracted figures with numbered list) | ALL: include all extracted figures in the slide plan. Numbers: include only the specified figures. The routing script validates each number against the extracted figure count and rejects out-of-range responses with a re-prompt. |

**Phase 2: Style Definition**

| Gate ID | Type | Valid Responses | Context Loaded | Next State |
|---------|------|-----------------|----------------|------------|
| `G2.1_style_config_review` | Human | `STYLE APPROVED`, `STYLE REVISE <feedback>`, `REGENERATE PREVIEWS` | `style_config.json` (draft), `style_guide.md` (draft), `.debrief/draft/preview_images/*.png` | APPROVED: promote draft artifacts and proceed to machine gate G2.2 *(dead -- BUG-AUDIT-31)*. STYLE REVISE: re-invoke Stylist with user feedback (draft discarded). REGENERATE PREVIEWS: retain draft config/guide/derived-draft; re-invoke Stylist in preview-regeneration mode so it picks new placeholder content, rewrites the preview HTML, and re-runs `debrief.preview_renderer` (REQ-STYLE-10 step 7). |
| `G2.2_style_lock` | Machine *(dead -- BUG-AUDIT-31)* | `LOCK SUCCESS`, `LOCK FAILED` | `style_config.json`, `deck_state.json` | SUCCESS: Phase 3 (`phase: "production"`, `sub_phase: "group_planning"`). FAILED: error, present to user |

**Phase 3: Slide Production**

| Gate ID | Type | Valid Responses | Context Loaded | Next State |
|---------|------|-----------------|----------------|------------|
| `G3.1_group_brief_ready` | Machine *(dead -- BUG-AUDIT-31)* | `BRIEFS DISPATCHED` | `deck_brief.md`, `deck_state.json` | `sub_phase: "red_green"`, begin slide generation |
| `G3.2_red_green` | Machine *(dead -- BUG-AUDIT-31)* | `GREEN`, `RED`, `EXHAUSTED` | `qa_log.jsonl` (latest entry for slug) | GREEN: `production/slide_review`, present `G3.3_slide_review`. RED: increment `red_green_iteration`, rewrite. EXHAUSTED (iteration=5): transitions to `production/diagnostic`; the consultant invokes the bug-diagnostic agent (see Section 24.18). |
| `G3.2a_oscillation_review` | Human | `KEEP TRYING`, `REVERT TO BEST`, `MY INSTRUCTIONS` | best-known-good slide HTML + latest qa_log entry + iteration history (cycle log) | KEEP TRYING: continue red-green from current iteration. REVERT TO BEST: restore best-known-good snapshot, transition to `production/slide_review`, present G3.3. MY INSTRUCTIONS: prompt user for revision instructions (inline skill prompt per Section 24.30), reset `red_green_iteration` to 0, re-enter `production/red_green` with the user's instructions injected into the prepare context. |
| `G3.3_slide_review` | Human | `SLIDE APPROVED`, `SLIDE REVISE` | screenshot, Tier 2 warnings, slide HTML, `.debrief/approval_<slug>.json` (pre-written by Slide Maker) | APPROVED: `update_state` reads and merges `.debrief/approval_<slug>.json`, advances `group_slide_index`. If last slide in group, G3.4. Else, generate next slide (G3.2). REVISE: reset `red_green_iteration`, re-enter red-green. This is the normal-path gate after a GREEN cycle. |
| `G3.3_slide_review_post_diagnostic` | Human | `SLIDE APPROVED`, `SLIDE REVISE: <instructions>` (instructions required — bare `SLIDE REVISE` is rejected) | `.debrief/diagnostic_<slug>.md`, current slide HTML, screenshot, `.debrief/approval_<slug>.json` (pre-written by Slide Maker from the best-known-good iteration) | APPROVED: same as `G3.3_slide_review` APPROVED (read `.debrief/approval_<slug>.json`, merge, advance). `update_state` then deletes `.debrief/diagnostic_<slug>.md`. Next state: `production/slide_review` (with the usual group-advance logic via the reset sub_phase). REVISE: `update_state` parses instructions, writes them to `.debrief/gate_data.json` as `{"gate_id": "G3.3_slide_review_post_diagnostic", "data": {"slide_revise_instructions": "<instructions>"}}`, resets `red_green_iteration` to 0, transitions to `production/red_green`. `.debrief/diagnostic_<slug>.md` is deleted on either response. This is a distinct gate from `G3.3_slide_review` — see Section 14.16.1 for its canonical prompt. |
| `G3.4_group_review` | Human | `GROUP APPROVED`, `GROUP REVISE <slug>` | all slides in group (via `/debrief:view current`) | APPROVED: G3.5. REVISE: the `GROUP REVISE` response MUST include a slug identifying which slide to revise. The routing script extracts the slug and sets `current_slide_slug` before transitioning to `production/red_green`. |
| `G3.5_more_slides` | Human | `MORE SLIDES`, `LAST SLIDE` | `deck_brief.md`, `deck_state.json` (approved slide count) | MORE: `sub_phase: "group_planning"`, increment group_id, re-invoke Consultant. LAST: G3.6 (deck ending review). **Note:** When `backup_mode` is true, the routing script presents G4.3 instead of G3.5. |
| `G3.6_deck_ending` | Human | `END AS-IS`, `ADD CLOSING SLIDE`, `ADD EMPTY CLOSING SLIDE` | Full deck storyboard (auto-opened via `/debrief:view`) | AS-IS: proceed to Phase 4. ADD CLOSING SLIDE: Consultant plans one more ending slide group. ADD EMPTY CLOSING SLIDE: export module auto-generates a styled empty closing slide. See Section 14.17 transition table for the detailed routing (including `closing_slide_pending` skip/reset logic). |
| `G3.V_view_dispatch` | Human | `DETAIL FIX <slug>`, `ESCALATE`, `CONTINUE` | `/debrief:view` output | DETAIL FIX: route to Slide Maker for slug, `sub_phase: "red_green"`. After a `DETAIL FIX` completes (slide approved at G3.3), the system restores the pre-view `sub_phase` from the `pre_view_state` field stored in `debrief_state.json` when the view was invoked. ESCALATE: route to Consultant, `sub_phase: "group_planning"`. CONTINUE: return to pre-view state |

**Phase 4: Finalization**

| Gate ID | Type | Valid Responses | Context Loaded | Next State |
|---------|------|-----------------|----------------|------------|
| `G4.1_export_options` | Human | `PROCEED TO EXPORT` | `deck_state.json` summary | G4.2. G4.1 confirms the user is ready to begin the export dialog, which handles all options (see Section 24.10). |
| `G4.2_backup_decision` | Human | `BACKUP YES`, `BACKUP NO` | `deck_state.json` (approved slide count) | YES: `backup_mode: true`, `sub_phase: "group_planning"`, Phase 3 loop for backup. NO: G4.4 |
| `G4.3_backup_complete` | Human | `MORE BACKUP`, `LAST BACKUP` | `deck_state.json` (backup slides) | MORE: increment group_id, `sub_phase: "group_planning"` (backup_mode remains true). LAST: `backup_mode: false`, G4.4 |
| `G4.4_export_confirm` | Human | `EXPORT NOW`, `REVIEW FIRST` | export ordering summary | EXPORT NOW: machine gate G4.5 *(dead -- BUG-AUDIT-31)*. REVIEW FIRST: triggers a read-only view (no G3.V dispatch). After the user closes the browser, G4.4 is re-presented. |
| `G4.5_export_result` | Machine *(dead -- BUG-AUDIT-31)* | `EXPORT SUCCESS`, `EXPORT FAILED` | `export_log.jsonl` | SUCCESS: `finalization/post_export` (G4.6). FAILED: present error, user decides |
| `G4.6_post_export` | Human | `GENERATE SCRIPT`, `GENERATE HANDOUT 2UP`, `GENERATE HANDOUT 4UP`, `DONE` | `deck_state.json` (latest presentation record) | GENERATE SCRIPT: run script generator, re-present G4.6. GENERATE HANDOUT 2UP: run handout module (2up), re-present G4.6. GENERATE HANDOUT 4UP: run handout module (4up), re-present G4.6. DONE: `phase: "complete"`. G4.6 loops — after each deliverable is generated, the gate is re-presented until the user says DONE. |

#### 14.16.1 Gate Prompts

Per REQ-ROUTE-9, every human gate displays a gate prompt assembled by the `prepare` script. The canonical text for each gate is defined below. The `prepare` script MUST include the gate prompt verbatim in the action block. The orchestrator presents it to the user as-is.

**Placeholder syntax and substitution.** Gate prompt placeholders use `{placeholder_name}` syntax (Python format-string style). The `prepare` script is the sole substituter: it reads placeholder values from `debrief_state.json`, `deck_state.json`, `.debrief/*.md` context files, or computes them at prepare time per the table below, then substitutes them into the prompt template before writing `.debrief/task_prompt.md`. The prompts below use `{}` consistently; any lingering `[]` or `<>` forms in earlier revisions are informational placeholders and MUST be normalized to `{}` before the gate is presented.

**Placeholder syntax rule.** Gate prompts use two placeholder styles:
- `{name}` — runtime-substituted placeholder. The value is sourced from state, deck, or context files via the prepare script. The prepare script MUST apply all substitutions before the action block reaches the orchestrator. Blueprint implementations MUST NOT emit an `ActionBlock` with unresolved `{}` placeholders in the gate prompt text.
- `<literal_text>` — instruction to the user about what to type at the gate (not substituted). Example: `SLIDE REVISE: <your instructions>` means the user literally types `SLIDE REVISE: <your actual instructions here>`.

| Placeholder | Source | Computed from |
|-------------|--------|--------------|
| `{archetype_name}` | `debrief_state.json` → `archetype` | Mapped to display name via Section 14.1.1 table (e.g., `lab_meeting` → "Lab meeting talk"). |
| `{presentation_type}` | `deck_brief.md` `## Content Signals` → `presentation_type` | One of `teaching`, `findings_report`, `interview_grant`, `journal_club` (REQ-CONSULT-8). |
| `{allocated_time}` | `deck_brief.md` `## Content Signals` → `allocated_time` | e.g., `"20min"`. |
| `{last_slide_title}` | `deck_state.json` → `slides[-1].title` filtered to approved non-backup | Used in G3.6. |
| `{previous_failure_count}`, `{current_failure_count}` | Latest two `qa_log.jsonl` iterations for current slug | Used in G3.2a. |
| `{previous_failure_invariants}`, `{current_failure_invariants}` | Latest two `qa_log.jsonl` iterations for current slug | Used in G3.2a; comma-separated INV IDs. |
| `{derived_style_guide_summary}` | `.debrief/draft/derived_style_guide.md` → top-level headline plus key per-section bullets | Used in G1.2. Produced by `debrief.style_analyzer` per REQ-CONSULT-13. |
| `{reference_thumbnail_links}` | `assets/reference/slides/*.png` | Used in G1.2. Markdown-formatted link list to the extracted reference images. |
| `{reference_filename}` | `debrief_state.json` → (computed from the reference path captured at discovery time) | Used in G1.2. Bare filename of the imported reference. |
| `{reference_modality}` | `debrief_state.json` → `reference_modality` | One of `pptx`, `pdf`, `html`, `html_dir`. Used in G1.2. |
| `{draft_style_guide_summary}` | `.debrief/draft/style_guide.md` → top-level headline plus key per-section bullets | Used in G2.1. The Stylist writes the draft guide before rendering previews. |
| `{preview_image_links}` | `.debrief/draft/preview_images/preview_*.png` | Used in G2.1. Markdown-formatted bullet list of links to the rendered preview slides, one bullet per preview file. Produced by `debrief.preview_renderer` per REQ-STYLE-10. |
| `{N}` (figure count) | Count of extracted figures in `.debrief/paper_analysis_<paper_slug>.md` | Used in G1.3. |
| `{figure_N_caption}` | `.debrief/paper_analysis_<paper_slug>.md` → numbered figure list | Used in G1.3; the prepare script expands the numbered list into one line per figure. |
| `{paper_slug}` | Current paper slug from paper analyzer output | Used in G1.3 file path. |
| `{your instructions}` | N/A (this is USER input, not a template variable) | Appears as a literal in prompts to indicate where the user types. Not substituted. |

Placeholders whose value is null or empty (e.g., `{last_slide_title}` when no slides exist) are substituted with a neutral placeholder string (`"(none)"`) rather than raising an error; the prepare script logs the empty substitution to stderr.

**G1.1 — Brief Review**
```
You have reviewed the deck brief.
Archetype: {archetype_name} | Type: {presentation_type} | Time: {allocated_time}
  BRIEF APPROVED   -> Lock the brief and move to style definition
  BRIEF NEEDS WORK -> Return to the Consultant to revise the brief
Before deciding:
  /debrief:quit  to save and exit
```

**G1.2 — Reference Style Review**
```
I've analyzed the reference you provided ({reference_filename}, {reference_modality}). Here is the derived style guide:

{derived_style_guide_summary}

Here are thumbnails of the reference pages I analyzed:

{reference_thumbnail_links}

How would you like to use this?
  USE AS BASELINE     -> Adopt this as the starting style; you can still adjust anything in the style dialog
  USE FOR INSPIRATION -> Keep as reference context; build the style from scratch but informed by this
  IGNORE              -> Discard the derived style and define the style entirely from scratch
Before deciding:
  The extracted reference images are in assets/reference/slides/ — you can review them.
  /debrief:quit  to save and exit
```

**G1.3 — Figure Selection**
```
I extracted {N} key figures from the paper(s):
  1. {figure_1_caption}
  2. {figure_2_caption}
  3. {figure_3_caption}
  ...

Which figures would you like to present?
  ALL                -> Include all figures in the slide plan
  <numbers>          -> Space-separated figure numbers (e.g., "1 3 5")
Before deciding:
  The extracted figures are saved to assets/reference/papers/{paper_slug}/figures/
  /debrief:quit  to save and exit
```

**G2.1 — Style Review**
```
I've drafted a style for your deck. Here is the design rationale:

{draft_style_guide_summary}

And here are three rendered preview slides using this style:

{preview_image_links}

Look at the previews carefully — the typography, color balance, diagram treatment,
and overall visual rhythm. Do they match what you want for your deck?

  STYLE APPROVED                          -> Promote the draft style and move to slide production
  STYLE REVISE <your feedback>       -> Return to the Stylist with feedback; the Stylist will iterate
  REGENERATE PREVIEWS                     -> Keep the same style but re-render preview slides with different placeholder content
Before deciding: /debrief:quit to save and exit
```

**G3.2a — Oscillation Review**
```
The slide fixed one issue but introduced another. This has happened more than once
and the slide is not converging.

  Previous iteration failures: {previous_failure_count} ({previous_failure_invariants})
  Current iteration failures: {current_failure_count} ({current_failure_invariants})

How would you like to proceed?
  KEEP TRYING      -> Continue the red-green cycle for another iteration
  REVERT TO BEST   -> Go back to the best version so far and review it
  MY INSTRUCTIONS  -> Provide specific guidance and restart the cycle
Before deciding:
  /debrief:view <slug>  to see the current slide
  /debrief:quit         to save and exit
```

**G3.3_slide_review — Slide Review**

This is the canonical prompt for the normal-path `G3.3_slide_review` gate ID (the gate reached after a GREEN red-green cycle).

```
The slide has passed QA. Review it and decide.
  SLIDE APPROVED -> Accept this slide and move to the next one
  SLIDE REVISE   -> Send this slide back for revision
Before deciding:
  /debrief:view <slug>  to preview this slide full-size in the browser
  /debrief:quit         to save and exit
```

**G3.3_slide_review_post_diagnostic — Slide Review (after diagnostic)**

This is the canonical prompt for the `G3.3_slide_review_post_diagnostic` gate ID (distinct from `G3.3_slide_review`; see Section 14.16 for the two rows in the Gate Catalog).

```
This slide failed QA 5 times. A diagnostic report is attached above.
Review the slide and the diagnostic, then decide.
  SLIDE APPROVED                     -> Accept this slide despite the QA issues
  SLIDE REVISE: <your instructions>  -> Restart the red-green cycle with new guidance
Before deciding:
  /debrief:view <slug>  to preview this slide full-size in the browser
  /debrief:quit         to save and exit

Note: After an exhausted cycle, SLIDE REVISE requires instructions. Bare
`SLIDE REVISE` is rejected.
```

**G3.4 — Group Review**
```
All slides in this group are complete. Review the group storyboard and decide.
  GROUP APPROVED       -> Accept the group and continue
  GROUP REVISE <slug>  -> Send a specific slide back for revision (include the slug)
Before deciding:
  /debrief:view current  to see the group storyboard
  /debrief:view <slug>   to preview a specific slide full-size
  /debrief:quit          to save and exit
```

**G3.5 — More Slides?**
```
This group has been approved. Are there more slides to create?
  MORE SLIDES -> Plan another group of slides with the Consultant
  LAST SLIDE  -> Review how the deck ends, then proceed to finalization
Before deciding:
  /debrief:view          to see all approved slides
  /debrief:view current  to see the current group storyboard
  /debrief:quit          to save and exit
```

**G3.6 — Deck Ending**
```
Here is your complete deck. The last slide is "{last_slide_title}".
How would you like the presentation to end?
  END AS-IS               -> The deck ends with the current last slide
  ADD CLOSING SLIDE       -> Create a new ending slide (e.g., "Thank You", custom closing)
  ADD EMPTY CLOSING SLIDE -> Auto-generate a styled empty slide as the final slide
Before deciding:
  The full deck storyboard has been opened in your browser.
  /debrief:view <slug>  to inspect any slide full-size
  /debrief:quit         to save and exit
```

**G3.V — View Dispatch**
```
You have viewed the slides. What would you like to do?
  DETAIL FIX <slug> -> Send a specific slide to the Slide Maker for revision (include the slug)
  ESCALATE          -> Return to the Consultant to restructure or replan
  CONTINUE          -> Return to where you were before viewing
Before deciding:
  /debrief:view <slug>   to preview another slide full-size
  /debrief:view current  to see the current group storyboard
  /debrief:quit          to save and exit
```

**G4.1 — Export Options**
```
All slides are complete. Ready to begin the export process?
  PROCEED TO EXPORT -> Begin the export dialog (ordering, separator, folder name)
Before deciding:
  /debrief:view  to review all slides one more time
  /debrief:quit  to save and exit
```

**G4.2 — Backup Decision**
```
Would you like to create backup/Q&A slides before exporting?
  BACKUP YES -> Enter the backup slide loop (same process as main slides)
  BACKUP NO  -> Skip backup slides and proceed to export
Before deciding:
  /debrief:view  to review all approved slides
  /debrief:quit  to save and exit
```

**G4.3 — Backup Complete**
```
This group of backup slides has been approved. Create more backup slides?
The backup section is the final part of the presentation — the last backup
slide will be the very last page in the exported PDF.
  MORE BACKUP -> Plan another group of backup slides with the Consultant
  LAST BACKUP -> No more backup slides; proceed to export
Before deciding:
  /debrief:view backup  to see all backup slides
  /debrief:view         to see the full deck (main + backup)
  /debrief:quit         to save and exit
```

**G4.4 — Export Confirm**
```
Ready to render the final PDF?
  EXPORT NOW   -> Run the export and generate the PDF
  REVIEW FIRST -> Open a view of all slides before exporting
Before deciding:
  /debrief:view  to review all slides
  /debrief:quit  to save and exit
```

**G4.6 — Post-Export Deliverables**
```
The PDF has been exported successfully. Would you like to generate additional deliverables?
  GENERATE SCRIPT      -> Generate a versioned presenter script
  GENERATE HANDOUT 2UP -> Generate a 2-up handout (slides + detailed notes)
  GENERATE HANDOUT 4UP -> Generate a 4-up handout (compact reference)
  DONE                 -> Finish — no more deliverables needed
Before deciding:
  You can generate multiple deliverables — this prompt will repeat until you say DONE.
  /debrief:quit  to save and exit
```

### 14.17 Sub-Phase Transition Table

This is the definitive routing table. Every row is a state + condition to next state transition. No transition exists outside this table.

**Phase 1**

| Current State | Condition | Action | Next State |
|---------------|-----------|--------|------------|
| `discovery/greeting` | (entry) | invoke Consultant | `discovery/dialog` |
| `discovery/dialog` | Consultant writes `deck_brief.md` with Content Signals | (automatic) | `discovery/brief_review` |
| `discovery/brief_review` | G1.1: BRIEF APPROVED + papers provided | present already-extracted paper analysis results (analyzer ran during discovery dialog, REQ-CONSULT-17) | `discovery/paper_analysis` |
| `discovery/paper_analysis` | Consultant presents extraction results | present G1.3 | `discovery/figure_selection` |
| `discovery/figure_selection` | G1.3: ALL + `reference_provided=true` | write `selected_figures: "all"` to `debrief_state.json` | `discovery/style_analysis` |
| `discovery/figure_selection` | G1.3: ALL + `reference_provided=false` | write `selected_figures: "all"` to `debrief_state.json` | `style/style_dialog` |
| `discovery/figure_selection` | G1.3: `<numbers>` + `reference_provided=true` | write `selected_figures: [numbers]` to `debrief_state.json` | `discovery/style_analysis` |
| `discovery/figure_selection` | G1.3: `<numbers>` + `reference_provided=false` | write `selected_figures: [numbers]` to `debrief_state.json` | `style/style_dialog` |
| `discovery/brief_review` | G1.1: BRIEF APPROVED + reference provided (any modality; no papers) | run reference style analyzer, present derived draft | `discovery/style_analysis` |
| `discovery/brief_review` | G1.1: BRIEF APPROVED + no reference, no papers | advance phase | `style/style_dialog` |
| `discovery/brief_review` | G1.1: BRIEF NEEDS WORK | re-invoke Consultant | `discovery/dialog` |
| `discovery/style_analysis` | G1.2: USE AS BASELINE | set `style_import_mode: "baseline"` | `style/style_dialog` |
| `discovery/style_analysis` | G1.2: USE FOR INSPIRATION | set `style_import_mode: "inspiration"` | `style/style_dialog` |
| `discovery/style_analysis` | G1.2: IGNORE | set `style_import_mode: null` | `style/style_dialog` |

**Phase 2**

| Current State | Condition | Action | Next State |
|---------------|-----------|--------|------------|
| `style/style_dialog` | (entry) | invoke Stylist | `style/style_dialog` |
| `style/style_dialog` | Stylist produces config + guide | (automatic) | `style/style_review` |
| `style/style_review` | G2.1: STYLE APPROVED | promote `.debrief/draft/style_config.json` → `./style_config.json`, promote `.debrief/draft/style_guide.md` → `./style_guide.md`, then run style lock | `style/style_lock` |
| `style/style_review` | G2.1: STYLE REVISE | discard `.debrief/draft/` contents, re-invoke Stylist | `style/style_dialog` |
| `style/style_review` | G2.1: REGENERATE PREVIEWS | write `gate_data.json` with `{regenerate_previews: true}`; clear `.debrief/draft/preview_slides/` and `.debrief/draft/preview_images/`; retain `.debrief/draft/style_config.json`, `style_guide.md`, `derived_style_guide.md`, `preview_style.css`; re-invoke Stylist in preview-regeneration mode to re-run REQ-STYLE-10 steps 2-4 | `style/style_dialog` |
| `style/style_lock` | G2.2: LOCK SUCCESS | advance phase | `production/group_planning` |
| `style/style_lock` | G2.2: LOCK FAILED | present error | `style/style_review` |

**Phase 3**

| Current State | Condition | Action | Next State |
|---------------|-----------|--------|------------|
| `production/group_planning` | (entry) | invoke Consultant to plan next group | `production/group_planning` |
| `production/group_planning` | G3.1: BRIEFS DISPATCHED | begin first slide | `production/red_green` |
| `production/red_green` | (entry) | invoke Slide Maker to generate/rewrite | `production/red_green` |
| `production/red_green` | G3.2: GREEN | present slide | `production/slide_review` |
| `production/red_green` | G3.2: RED, iteration < 5 | increment iteration, rewrite | `production/red_green` |
| `production/red_green` | G3.2: EXHAUSTED | `update_state` transitions sub_phase; does NOT invoke any agent (see Section 24.18) | `production/diagnostic` |
| `production/diagnostic` | (entry) | routing emits `invoke_agent` targeting bug-diagnostic (DIAGNOSTIC_REQUESTED in Section 13.1); agent writes `.debrief/diagnostic_<slug>.md` | `production/diagnostic` |
| `production/diagnostic` | bug-diagnostic agent returns (diagnostic report written) | agent `post` step transitions sub_phase and sets pending_gate | `production/slide_review` with `pending_gate: G3.3_slide_review_post_diagnostic` |
| `production/red_green` | update_state detects oscillation (same failure count, different failures) | present G3.2a | `production/oscillation_review` |
| `production/oscillation_review` | G3.2a: KEEP TRYING | increment iteration, continue | `production/red_green` |
| `production/oscillation_review` | G3.2a: REVERT TO BEST | restore best-known-good snapshot | `production/slide_review` |
| `production/oscillation_review` | G3.2a: MY INSTRUCTIONS | reset iteration, inject user instructions into next prepare context | `production/red_green` |
| `production/slide_review` | `G3.3_slide_review` OR `G3.3_slide_review_post_diagnostic`: SLIDE APPROVED, `group_revise_slug` non-null | reset `group_revise_slug` to null; if current gate was the post-diagnostic variant, delete `.debrief/diagnostic_<slug>.md`; return to group review | `production/group_review` |
| `production/slide_review` | `G3.3_slide_review` OR `G3.3_slide_review_post_diagnostic`: SLIDE APPROVED, `pre_view_state` non-null, `group_revise_slug` null | restore `phase`, `sub_phase`, `pending_gate`, and `current_slide_slug` from `pre_view_state`; clear `pre_view_state`; if current gate was the post-diagnostic variant, delete `.debrief/diagnostic_<slug>.md` | (restored state) |
| `production/slide_review` | `G3.3_slide_review` OR `G3.3_slide_review_post_diagnostic`: SLIDE APPROVED, more slides in group | advance slide index; if current gate was the post-diagnostic variant, delete `.debrief/diagnostic_<slug>.md` | `production/red_green` |
| `production/slide_review` | `G3.3_slide_review` OR `G3.3_slide_review_post_diagnostic`: SLIDE APPROVED, last slide in group | present group; if current gate was the post-diagnostic variant, delete `.debrief/diagnostic_<slug>.md` | `production/group_review` |
| `production/slide_review` | `G3.3_slide_review`: SLIDE REVISE | reset `red_green_iteration`; no gate_data.json (bare response) | `production/red_green` |
| `production/slide_review` | `G3.3_slide_review_post_diagnostic`: SLIDE REVISE: `<instructions>` | reset `red_green_iteration`; write `.debrief/gate_data.json` with `{"gate_id": "G3.3_slide_review_post_diagnostic", "data": {"slide_revise_instructions": "<instructions>"}}` (cross-cycle consumer per Section 24.20); delete `.debrief/diagnostic_<slug>.md` | `production/red_green` |
| `production/group_review` | G3.4: GROUP APPROVED | ask more? | `production/more_slides` |
| `production/group_review` | G3.4: GROUP REVISE (slug) | set `group_revise_slug` to slug; route to specific slide | `production/red_green` |
| `production/more_slides` | `closing_slide_pending=true` | skip G3.5 and G3.6; reset `closing_slide_pending: false` | `finalization/export_options` |
| `production/more_slides` | G3.5: MORE SLIDES | increment group_id | `production/group_planning` |
| `production/more_slides` | G3.5: LAST SLIDE | show full deck, ask about ending | `production/deck_ending` |
| `production/deck_ending` | G3.6: END AS-IS | advance phase | `finalization/export_options` |
| `production/deck_ending` | G3.6: ADD CLOSING SLIDE | Consultant plans closing slide; set `closing_slide_pending: true` | `production/group_planning` |
| `production/deck_ending` | G3.6: ADD EMPTY CLOSING SLIDE | record `closing_slide: "empty"` in `deck_state.json`, advance | `finalization/export_options` |
| `production/more_slides` | `backup_mode=true` | present gate G4.3 (`MORE BACKUP` / `LAST BACKUP`), NOT G3.5 | (see Phase 4 table) |
| `production/*` (any) | `/debrief:view` invoked | set `pre_view_state` to `{"phase": <phase>, "sub_phase": <sub_phase>, "pending_gate": <pending_gate>, "current_slide_slug": <current_slide_slug>}` (only if `pre_view_state` is null — do not overwrite nested views); set `pending_gate: G3.V` | (view opens) |
| `production/*` (any) | G3.V: DETAIL FIX (slug) | set current_slide_slug | `production/red_green` |
| `production/*` (any) | G3.V: DETAIL FIX completes (G3.3 SLIDE APPROVED with `group_revise_slug` null) | restore `phase`, `sub_phase`, `pending_gate`, and `current_slide_slug` from `pre_view_state`; set `pre_view_state` to null; if restored `pending_gate` is non-null, re-present that gate on the next cycle | (restored state) |
| `production/*` (any) | G3.V: ESCALATE | set `pre_view_state` to null; return to Consultant | `production/group_planning` |
| `production/*` (any) | G3.V: CONTINUE | restore `phase`, `sub_phase`, `pending_gate`, and `current_slide_slug` from `pre_view_state`; set `pre_view_state` to null; if restored `pending_gate` is non-null, re-present that gate on the next cycle | (restored state) |

**G3.3 SLIDE APPROVED branch priority.** When G3.3 `SLIDE APPROVED` fires, `update_state` evaluates the possible branches from the `production/slide_review` rows above in the following fixed order and takes the first one whose condition matches:

1. `group_revise_slug` non-null → return to `production/group_review` (this completes a GROUP REVISE detour).
2. `pre_view_state` non-null → restore pre-view state and clear `pre_view_state` (this completes a DETAIL FIX dispatched from /debrief:view).
3. More slides in the current group (`group_slide_index + 1 < group_slide_count`) → advance `group_slide_index`, re-enter `production/red_green` for the next slide.
4. Last slide in group → present the group at `production/group_review`.

This priority is load-bearing: without it, a DETAIL FIX triggered from a view during a group would overwrite the view-restore path with the group-advance path, losing the `pre_view_state` capture. The priority applies to both `G3.3_slide_review` and `G3.3_slide_review_post_diagnostic` `SLIDE APPROVED` responses.

**Phase 4**

| Current State | Condition | Action | Next State |
|---------------|-----------|--------|------------|
| `finalization/export_options` | G4.1: PROCEED TO EXPORT | ask backup | `finalization/backup_decision` |
| `finalization/backup_decision` | G4.2: BACKUP YES | enter backup loop | `production/group_planning` (backup_mode=true) |
| `finalization/backup_decision` | G4.2: BACKUP NO | export dialog | `finalization/export_confirm` |
| `production/more_slides` (backup) | G4.3: MORE BACKUP | increment group_id | `production/group_planning` (backup_mode=true) |
| `production/more_slides` (backup) | G4.3: LAST BACKUP | exit backup | `finalization/export_confirm` (backup_mode=false) |
| `finalization/export_confirm` | G4.4: EXPORT NOW | run export | `finalization/exporting` |
| `finalization/export_confirm` | G4.4: REVIEW FIRST | set `pre_view_state` to `{"phase": "finalization", "sub_phase": "export_confirm", "pending_gate": "G4.4_export_confirm", "current_slide_slug": null}`; present a read-only view via `/debrief:view` (Phase 4 context restricts G3.V responses to `CONTINUE` only — no `DETAIL FIX` or `ESCALATE` because Phase 4 is read-only per Section 14.19) | `finalization/reviewing_for_export` |
| `finalization/reviewing_for_export` | G3.V: CONTINUE (Phase 4 context) | restore `phase`, `sub_phase`, `pending_gate` from `pre_view_state`; clear `pre_view_state`; re-present G4.4 | `finalization/export_confirm` |
| `finalization/exporting` | G4.5: EXPORT SUCCESS | offer post-export deliverables | `finalization/post_export` |
| `finalization/exporting` | G4.5: EXPORT FAILED | present error; do NOT re-run the ordering dialog (the `presentations` entry is retained per Section 24.10; retrying G4.4 `EXPORT NOW` re-exports into the same folder) | `finalization/export_confirm` |
| `finalization/post_export` | G4.6: GENERATE SCRIPT | run script generator | `finalization/post_export` (re-present G4.6) |
| `finalization/post_export` | G4.6: GENERATE HANDOUT 2UP | run handout module (2up) | `finalization/post_export` (re-present G4.6) |
| `finalization/post_export` | G4.6: GENERATE HANDOUT 4UP | run handout module (4up) | `finalization/post_export` (re-present G4.6) |
| `finalization/post_export` | G4.6: DONE | finish | `complete` |
| `complete` | user runs `debrief` (bare) | resume with existing `deck_brief.md` and `deck_state.json` retained | `discovery/dialog` (re-presentation flow per Section 24.13) |

### 14.18 Machine Gate Implementation

> **NOTE (BUG-AUDIT-31):** Machine gates are dead at runtime. All routing, update_state, and prepare functions were deleted in BUG-AUDIT-31 -- the consultant agent handles all dispatch via Tool calls. This section is retained for historical reference only.

Machine gates run automatically without human input. The routing script detects the condition, the update_state script advances. *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)*

| Machine Gate | How It Fires | Detection |
|--------------|-------------|-----------|
| G2.2 (style lock) | After `style_compiler` exits 0 and `chmod 444` succeeds | Check `style_locked: true` in `deck_state.json` and file permissions |
| G3.1 (briefs dispatched) | After Consultant writes structured briefs | Check that all briefs for the group exist in `.debrief/briefs/` |
| G3.2 (red-green) | After QA agent writes to `qa_log.jsonl` | Read latest entry for `current_slide_slug`: `passed: true` is GREEN, `passed: false` and iteration < 5 is RED, iteration >= 5 is EXHAUSTED |
| G4.5 (export result) | After export module exits | Read `export_log.jsonl` latest entry: exit status 0 is SUCCESS, else FAILED |

### 14.19 Skill Availability by Phase

The following matrix shows which user-invocable skills are valid in each pipeline phase. Skills invoked in a phase where they are not available MUST print a clear error message and exit without modifying state.

| Skill | Phase 1 (Discovery) | Phase 2 (Style) | Phase 3 (Production) | Phase 4 (Finalization) | `complete` |
|-------|:-------------------:|:---------------:|:--------------------:|:----------------------:|:----------:|
| `/debrief:slide [slug]` | — | — | ✓ | ✓ (backup only) | — |
| `/debrief:style` | ✓ (post-brief only) | ✓ | — | — | — |
| `/debrief:export` | — | — | — | ✓ | ✓ (re-export) |
| `/debrief:view [query]` | — | — | ✓ | ✓ (read-only) | ✓ |
| `/debrief:save [label]` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/debrief:restore` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/debrief:quit` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/debrief:script` | — | — | — | ✓ (post-export) | ✓ |
| `/debrief:handout [mode]` | — | — | — | ✓ (post-export) | ✓ |

**Legend:**
- ✓ = available
- — = not available; skill MUST print an error and exit without modifying state
- Qualified ✓ entries have additional preconditions noted in the skill's own requirement (e.g., `/debrief:handout` requires at least one prior export per REQ-HAND-6)

Skills marked "always available" (save, restore, quit) operate across all phases. Quit terminates the session; save and restore are non-destructive and return control to the current state. *(BUG-AUDIT-22: restore no longer terminates the session.)*

---

## 15. Non-Functional Requirements

### 15.1 Performance

- **NFR-PERF-1:** A single slide generation turn (brief to QA pass) MUST complete
  within 60 seconds on a machine with a standard broadband connection. The clock
  starts when the user invokes `/debrief:slide` (or when the slide skill
  dispatches to the slide agent) and ends when the QA agent writes a result
  record to `qa_log.jsonl`. This boundary is measured by comparing the timestamp
  in the qa_log entry with the invocation timestamp logged by the slide skill.
- **NFR-PERF-2:** PDF export for a deck of 20 slides MUST complete within 120 seconds.
- **NFR-PERF-3:** The view generation MUST complete within 10 seconds for a
  deck of up to 30 slides.

### 15.2 Reliability

- **NFR-REL-1:** All project state MUST be persisted to disk after every approved
  action. A session crash MUST NOT result in data loss beyond the current
  in-progress turn. A turn is defined as one user message followed by the
  system's complete response, including any agent invocations and tool calls
  triggered by that response.
- **NFR-REL-2:** The system MUST be resumable across sessions. Running `debrief` in
  an existing project directory MUST restore the full consultant context.
- **NFR-REL-3:** Export MUST be logically idempotent: running `/debrief:export`
  twice on the same deck state MUST produce PDFs with identical content and
  layout. Sub-pixel rendering differences from live diagram engines (Mermaid,
  rough.js) are acceptable.

### 15.3 Usability

- **NFR-USE-1:** The domain expert MUST be able to complete a 10-slide deck without
  writing any HTML, CSS, or JavaScript.
- **NFR-USE-2:** All error messages MUST be in plain English and MUST suggest a
  corrective action.
- **NFR-USE-3:** The consultant MUST be able to reconstruct deck context from
  `deck_brief.md` and `deck_state.json` alone, enabling recovery from ledger loss.

### 15.4 Portability

- **NFR-PORT-1:** The plugin MUST run on macOS and Linux. Windows is out of scope.
- **NFR-PORT-2:** The plugin MUST NOT assume a specific absolute path. All
  self-references MUST use `${CLAUDE_PLUGIN_ROOT}`.

---

## 16. Design Invariants

Every slide MUST conform to the following invariants. The visual QA agent checks
all of them before passing a slide. Invariants are organized into two tiers,
preceded by veto rules.

### Veto Rules (checked first — instant failure)

**Veto Rules** are checked before Tier 1 invariants. If any veto fires, the QA result is `passed: false` with `"veto": true` in the QA log record. The red-green cycle does not run the full Tier 1 checks — it immediately proceeds to rewrite based on the veto failure.

| ID | Veto Rule |
|----|-----------|
| VETO-01 | Text overflows beyond slide boundary (clipped or truncated content). |
| VETO-02 | Slide renders as blank (empty content area, white/background-only output). |
| VETO-03 | Content specified in the slide brief is entirely missing from the rendered slide. |
| VETO-04 | Raw HTML, CSS, or unrendered LaTeX source visible as literal text. |
| VETO-05 | Prompt artifacts visible as text ("Here is a slide about...", "As requested...", "This slide shows..."). |
| VETO-06 | Slide numbering, slug, or other meta-identifiers rendered as body content. |
| VETO-07 | Figure caption from an imported paper rendered inside the slide content area rather than as a properly styled caption element (journal club slides only). |

**Tier 1 — Structural Correctness (hard blockers: any failure blocks the slide)**

| ID | Invariant |
|----|-----------|
| INV-04 | Contrast ratio: all text/background pairs MUST meet WCAG AA (4.5:1 for normal text, 3:1 for large text). |
| INV-06 | No inline styles that override the locked style config. All styles come from `assets/style.css`. |
| INV-07 | No external network requests. All assets (fonts, images) are local. |
| INV-08 | Slide aspect ratio: exactly 16:9. |
| INV-10 | Diagrams must use only libraries from the `constraints.permitted_diagram_types` array in `style_config.json`. **User-provided raster images (inserted via REQ-ASSET-1) are exempt from this invariant** — they are explicitly requested content, not generated diagrams. The QA agent MUST still verify that user-provided images are local files (INV-07) and are properly referenced. Generated diagrams (Mermaid, rough.js, inline SVG produced by the Slide Maker) remain subject to INV-10. The distinction is: user-provided assets are exempt; agent-generated visual content is not. |
| INV-12 | Slide file must be valid HTML5. The QA agent must check for parse errors. |
| INV-13 | User-provided images must not overflow the slide canvas or be clipped. Image boundaries must respect 10% margins on all sides. |
| INV-14 | Rendered math must not overflow the slide width. Display math must be centered within 10% margins. |
| INV-15 | Generated diagrams (Mermaid, rough.js) must render without visible error messages, fallback text, or error placeholders. |
| INV-16 | All fonts referenced in `assets/style.css` must be loadable from local files in `assets/fonts/` or from standard system fonts. Missing font fallbacks are not permitted. |
| INV-17 | All CSS custom properties (`var(--...)`) used in slide HTML must be defined in `assets/style.css`. Undefined properties are not permitted. |
| INV-19 | User-provided image files referenced in slide HTML (`<img src="...">`) MUST exist on disk at the referenced path. No broken `src` attributes are permitted. Checked programmatically by `qa_checker.py` by resolving each `src` relative to the slide HTML and verifying file existence. |
| INV-20 | User-provided images MUST NOT be distorted beyond 2% of their intrinsic aspect ratio. For each `<img>` element, the rendered bounding-box aspect ratio (width/height) is compared to the source image's intrinsic aspect ratio; the absolute relative difference MUST be ≤ 0.02 (2%). Checked programmatically by `qa_checker.py`. |
| INV-21 | Rendered LaTeX math MUST be visible — not a blank box and not a KaTeX error placeholder. Checked by the QA agent (VLM-based) on the screenshot because the signal is primarily visual: a zero-height span or the KaTeX error color are not reliably detectable from HTML alone. This is the one Tier 1 invariant allocated to the VLM-based QA agent rather than to `qa_checker.py` (see Section 24.22). |
| INV-22 | Inline LaTeX math MUST NOT break the surrounding text's line height. Checked programmatically by `qa_checker.py` via bounding-box inspection: for each inline `.katex` element inside a text block, its rendered height MUST NOT exceed the containing line's computed line-height by more than 5%. Distinct from INV-14 (horizontal overflow of display math). |
| INV-23 | If the math renderer produces asset files (SVG, font, or other static assets referenced from the slide HTML), those files MUST exist at the referenced paths. Checked programmatically by `qa_checker.py`. With the v1.1 client-side KaTeX implementation (REQ-LATEX-3), the math renderer produces no per-slide asset files, so this invariant is a no-op in v1.1 — but it is retained for forward compatibility with future server-side rendering (e.g., `pdflatex`). |

**Tier 2 — Design Quality (soft signals: flagged as warnings after Tier 1 passes)**

| ID | Invariant |
|----|-----------|
| INV-01 | One idea per slide. No slide may contain more than one primary claim or topic. |
| INV-02 | Font size: body text no smaller than 28px; headings no smaller than 40px. |
| INV-03 | Line length: no text block wider than 70% of slide width. |
| INV-05 | White space: minimum 10% margin on all four sides of the slide canvas. |
| INV-09 | No more than 5 bullet points per slide. Where bullets exceed this, the consultant must split into multiple slides. |
| INV-11 | No speaker notes embedded in the slide HTML. Speaker notes belong in the presenter script. |
| INV-18 | Visual symmetry: adjacent panels, columns, or visual elements of the same type MUST be equal in size. Vertical alignment of tops and horizontal alignment of edges MUST be consistent. Whitespace margins MUST be symmetric (left ≈ right, top ≈ bottom). Asymmetry is permitted only when there is an explicit content reason. |

---

## 17. State Machine: `deck_state.json`

`deck_state.json` is the single source of truth for deck content state. It is the only
file the export module reads to determine slide order and content.

### 17.1 Top-Level Fields

```json
{
  "project_name": "<directory-name>",
  "created_at": "<ISO8601>",
  "archetype": "<archetype_value>",
  "style_locked": false,
  "closing_slide": null,
  "slides": [],
  "presentations": []
}
```

`archetype` — the archetype selected at project creation. One of: `lab_meeting`, `conference_talk`, `seminar`, `lecture`, `journal_club`, `grant_panel`, `job_talk`, `custom`. Immutable after project creation (changing the archetype requires running `debrief new` to start a fresh project). *(BUG-AUDIT-22: `/debrief:restore` does not start new projects; use `debrief new` instead.)*

The `slides` array stores ALL slide records regardless of status. The order of
entries in the `slides` array is the canonical deck order for view and
export. There is no separate `deck_order` field; reordering slides means
reordering entries in this array. Deck order is determined by the position of
`approved` slides in the array. Components reading the slides array for ordering
purposes (export, view, consultant) MUST filter to `status: "approved"`
entries only. Slides with any other status (e.g., `discarded`, `draft`,
`needs_revision`) are present in the array but do NOT participate in deck order.

`closing_slide` controls the auto-generated closing slide at the end of the main
deck (before the separator and backup slides). Values:
- `null` — no auto-generated closing slide; the deck ends with the last approved
  non-backup slide (the user chose `END AS-IS` at G3.6).
- `"empty"` — the export module generates a styled empty slide as the final main
  slide, using the locked style config (background color, margins). It has no
  content — just a clean, styled ending. Generated fresh at export time, like the
  separator. Not written to `slides/`, has no slide record.

`presentations` is an array of presentation folder records (see Section 17.4).
Each entry describes one dated export folder created from this project.
Per-presentation counters (`export_count`, `script_count`) and
`separator_position` live inside each presentation record, not at the top level.

### 17.2 Slide Record Fields

Each entry in the `slides` array:

```json
{
  "slug": "string",
  "title": "string",
  "status": "draft|approved|needs_revision|discarded",
  "content_summary": "string",
  "visual_approach": "string",
  "design_choices": "string",
  "forks_not_taken": "string",
  "user_recommendations": "string",
  "qa_passed": false,
  "accepted_violations": [],
  "last_modified": "ISO 8601 timestamp",
  "group_id": "string",
  "backup": false,
  "user_assets": [],
  "has_math": false
}
```

Deck order is determined solely by the position of `approved` slides in the `slides` array. There is no separate `order` field.

- `group_id` — a deterministic identifier assigned by the Consultant when dispatching a group. Format: `<prefix>_<NN>` where `prefix` is `group` for main slides or `backup` for Q&A/backup slides, and `NN` is a zero-padded 2-digit counter (01, 02, ..., 99), 1-indexed, monotonically increasing within each prefix class. The first main group is `group_01`, the second is `group_02`. The first backup group is `backup_01`. Group IDs are never reused; they are permanent identifiers for the lifetime of the project. Used by the view skill to resolve `current` and `previous` queries.
- `backup` — boolean, default false. When true, this slide is a backup/Q&A slide placed after the separator. The export module uses this field in conjunction with `separator_position` to order the deck correctly.
- `user_assets` — array of file paths (relative to project root) of user-provided images included in this slide. Used by the QA agent to verify all referenced assets exist.
- `has_math` — boolean indicating whether this slide contains rendered LaTeX math. Used by the QA agent to activate math-specific checks.

`accepted_violations` is an array of objects, each with:
```json
{
  "invariant": "INV-04",
  "reason": "user accepted low contrast for artistic effect",
  "accepted_at": "<ISO8601>"
}
```

**Slug naming convention.** Slugs are assigned by the Consultant when writing the slide brief per REQ-CONSULT-5. A valid slug:
- Contains only lowercase ASCII letters, digits, and underscores: regex `^[a-z][a-z0-9_]{0,49}$`
- Is 1–50 characters in length
- Does not end with an underscore
- Is unique within the project (no two slide records may share a slug, including discarded slides — the slug is permanently consumed)
- Is human-readable and descriptive of the slide's content (e.g., `intro`, `methodology_overview`, `results_cohort_a`, `backup_timeline`)

The Consultant MUST assign the slug; the user does not choose it directly. The Slide Maker receives the slug from the slide brief and creates `slides/<slug>.html`. All downstream artifacts keyed by slug (`output/screenshots/<slug>.png`, `.debrief/approval_<slug>.json`, `.debrief/diagnostic_<slug>.md`, `.debrief/snapshots/<slug>_iter_<N>.html`, `assets/images/<slug>_<filename>`) use the same slug verbatim.

### 17.3 State Transitions

```
(none)         -> draft           when slide agent writes slides/<slug>.html
draft          -> needs_revision  when QA fails or user requests revision
draft          -> approved        when QA passes AND user approves
draft          -> approved        (via accepted violation) when the user accepts a violation
                                  at the invariant gate (Section 18.3 option a); qa_passed is
                                  set to true and accepted_violations is populated. This is an
                                  explicit override path distinct from the normal QA-pass path.
needs_revision -> draft           when slide agent rewrites the slide
needs_revision -> approved        (via accepted violation) same as above; user accepts the
                                  violation rather than continuing revision
approved       -> needs_revision  when user requests revision of an approved slide
any            -> discarded       when user chooses discard at the invariant violation gate
```

When a slide transitions to `discarded`, `update_state` MUST perform the following cleanup atomically:

1. Delete `slides/<slug>.html`.
2. Delete `output/screenshots/<slug>.png` (if present). Screenshots are per-slide artifacts tied to the slide's lifetime; leaving them orphaned is a bug (an unused file that would either persist forever or be silently overwritten if the slug is later reused for a fresh slide).
3. Delete any `.debrief/approval_<slug>.json` or `.debrief/diagnostic_<slug>.md` files for this slug (if present).
4. Free the slug for reuse.

The entry remains in the `slides` array with `status: "discarded"`. The entry is excluded from deck order by all components that read the `slides` array (export, view, consultant context). See Section 17.1 for deck-order filtering rules.

### 17.4 Presentation Folder Records

Each entry in the `presentations` array describes one dated export folder:

```json
{
  "folder": "2026_04_30_SVP_presentation",
  "created_at": "<ISO8601>",
  "export_count": 1,
  "script_count": 0,
  "handout_count": 0,
  "separator_position": 8,
  "separator_content": "Questions?",
  "slide_manifest": ["intro", "overview", "pipeline", "results", "conclusion"]
}
```

- `folder` — the folder name inside `output/`, confirmed by the user during the
  export ordering dialog.
- `created_at` — ISO 8601 timestamp of the first export into this folder.
- `export_count` — number of PDF versions written to this folder. *(No longer incremented by current command implementations; versioning is filesystem-derived per BUG-AUDIT-23.)*
- `script_count` — number of script versions written to this folder. *(No longer incremented by current command implementations; versioning is filesystem-derived per BUG-AUDIT-25.)*
- `handout_count` — number of handout versions written to this folder. *(No longer incremented by current command implementations; versioning is filesystem-derived per BUG-AUDIT-21.)*
- `separator_position` — indicates where the user considers the "formal presentation" to end, expressed as a 0-based index into the `slides` array. This value is historical/intent-only — it captures the user's intent during the export ordering dialog but does NOT drive PDF page placement. See Section 24.10 for the canonical PDF page order. May differ from other presentations if the user splits the deck differently for a different audience. If null, no separator is inserted. `separator_position` lives ONLY in the per-presentation record; there is no top-level `separator_position` field.
- `separator_content` — the content choice for the separator slide for this
  presentation (e.g., `"Questions?"`, `"Acknowledgments"`, or a custom string).
- `slide_manifest` — a snapshot array of slide slugs in their export order at
  the time of export. This records exactly which slides were included in the
  exported PDF and in what order. It does not change after the export.

### 17.5 Pipeline Control State: `debrief_state.json`

`debrief_state.json` is the pipeline control state — separate from `deck_state.json` (which is the content state). `deck_state.json` tracks slides, styles, presentations. `debrief_state.json` tracks where we are in the workflow.

```json
{
  "phase": "discovery",
  "sub_phase": "greeting",
  "active_agent": "consultant",
  "archetype": "<archetype_value>",
  "current_group_id": null,
  "current_slide_slug": null,
  "pending_gate": null,
  "last_gate_response": null,
  "red_green_iteration": 0,
  "red_green_started_at": null,
  "group_slide_index": 0,
  "group_slide_count": 0,
  "backup_mode": false,
  "completed_groups": [],
  "pre_view_state": null,
  "view_deferred": false,
  "closing_slide_pending": false,
  "group_revise_slug": null,
  "style_import_mode": null,
  "reference_provided": false,
  "reference_modality": null,
  "papers_provided": false,
  "session_started_at": "ISO8601",
  "state_hash": "SHA-256"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `phase` | string | `"discovery"`, `"style"`, `"production"`, `"finalization"`, `"complete"` |
| `sub_phase` | string or null | Phase-specific sub-state (see Section 14.17) |
| `active_agent` | string | Which conversational agent the user is currently interacting with. One of: `"consultant"`, `"slide_maker"`, `"stylist"`, `"qa"`, `"none"`. The `"qa"` value corresponds to the `visual-qa` agent definition in Section 6.2 (same convention as `slide_maker` ↔ `slide-maker`: state/routing identifiers use underscores, agent definition filenames use hyphens). During `sub_phase == "production/diagnostic"` (while the bug-diagnostic agent runs autonomously via routing's `invoke_agent` mechanism), `active_agent` MUST be `"none"` — the diagnostic agent is not a conversational agent and the user is not interacting with it. |
| `archetype` | string | The archetype selected at init. Used by the routing script to determine default behavior and by the prepare script to assemble archetype-appropriate context. |
| `current_group_id` | string or null | The group currently being authored (e.g., `"group_01"`) |
| `current_slide_slug` | string or null | The slide currently in the red-green cycle or under review |
| `pending_gate` | string or null | Gate ID waiting for a response (null if no gate pending) |
| `last_gate_response` | string or null | The most recent gate response (used by routing to determine next action) |
| `red_green_iteration` | int | Current iteration count within the red-green cycle (0 = not in cycle) |
| `red_green_started_at` | string or null | ISO-8601 timestamp set by update_state when entering production/red_green for a new slide (first iteration). Used by update_state to determine which qa_log.jsonl entries belong to the current cycle when building the per-cycle summary per REQ-SLIDE-12. Cleared when exiting production/red_green. |
| `group_slide_index` | int | Index of current slide within the group (0-based) |
| `group_slide_count` | int | Total slides in current group |
| `backup_mode` | bool | True when producing backup/Q&A slides in Phase 4 |
| `completed_groups` | array | List of completed group_ids (for `previous` resolution in `/debrief:view`) |
| `pre_view_state` | object or null | An object storing the pipeline position at the time `/debrief:view` was invoked. Format: `{"phase": "<phase>", "sub_phase": "<sub_phase>", "pending_gate": "<gate_id_or_null>", "current_slide_slug": "<slug_or_null>"}`. Used to restore state after `DETAIL FIX`, `CONTINUE`, or `CANCEL` from G3.V. Null when no view is active. Nested view invocation does NOT overwrite the existing value. When the routing script restores from `pre_view_state`, it restores all four fields (`phase`, `sub_phase`, `pending_gate`, `current_slide_slug`); if the restored `pending_gate` is non-null, the routing script re-presents that gate on the next cycle. |
| `view_deferred` | boolean | True when `/debrief:view` was invoked during the red-green cycle and is waiting for the cycle to complete. Checked by the routing script after each red-green iteration. Default: `false`. |
| `closing_slide_pending` | boolean | Set to `true` when G3.6 response is `ADD CLOSING SLIDE`. Routing behavior is defined in Section 14.17 transition table. Default: `false`. |
| `group_revise_slug` | string or null | Set to the slug when G3.4 `GROUP REVISE <slug>` is selected. When non-null at G3.3 `SLIDE APPROVED`, routes to `production/group_review` (not to the next slide in the group). Reset to `null` after the return to group review. Default: `null`. |
| `style_import_mode` | string or null | Set by G1.2 response: `"baseline"`, `"inspiration"`, or `null` (IGNORE or no import). Read by the Stylist's prepare script to determine how to use `.debrief/draft/derived_style_guide.md`. |
| `reference_provided` | boolean | Set to `true` when the user provides a reference file path during discovery, in any supported modality (`.pptx`, `.pdf`, `.html`, or a directory of `.html` files). Used by the routing script to determine whether G1.2 is presented after G1.1. Replaces the earlier PPTX-only boolean field from v1.0 drafts. |
| `reference_modality` | string or null | One of `"pptx"`, `"pdf"`, `"html"`, `"html_dir"`, or `null` (no reference provided). Set alongside `reference_provided` when the user supplies a reference path during discovery. Used by `debrief.style_analyzer` to dispatch to the correct modality adapter (Section 24.25) and by the G1.2 prepare script to populate the `{reference_modality}` placeholder. |
| `papers_provided` | boolean | Set to true when the user provides paper PDFs during discovery (journal club). Used by routing to trigger paper analysis. |
| `selected_figures` | array or string or null | Result of G1.3 figure selection. Array of integers (1-based figure indices) when the user selected specific figures; the string `"all"` when the user selected ALL; null when no figures have been selected yet or when `papers_provided=false`. Written by `update_state` on G1.3 response per Section 24.21. Read by the Consultant's group_planning prepare context to know which extracted figures to include in slide briefs. |
| `session_started_at` | string | ISO8601 timestamp of session start |
| `state_hash` | string | SHA-256 hash of state content fields for integrity verification |

---

## 18. Error Semantics

### 18.1 Recoverable Errors

The following errors are recoverable. The system MUST surface a plain-English
message and propose a corrective action without halting the session:

- QA failure on a slide (auto-retry via red-green cycle, then surface after 5 iterations)
- Playwright timeout during screenshot
- Style compiler warning (non-fatal CSS issue)
- Ledger read error (fall back to deck_brief.md + deck_state.json for context)

### 18.2 Fatal Errors

The following errors MUST halt the current operation and require user
intervention:

- `deck_state.json` is corrupt or unreadable
- `debrief_state.json` is corrupt or has invalid `state_hash`
- `style_config.json` is corrupt after style lock
- Playwright is not installed (fail at pre-flight, not during export)
- Python environment not activated

### 18.3 Invariant Violations

If a design invariant check (Section 16) fails after five automatic fix attempts
(see REQ-SLIDE-5 and REQ-SLIDE-7):

1. The bug diagnostic agent is invoked.
2. The diagnostic agent produces a structured report of the failure.
3. The report is shown to the user with three options:

   (a) **Accept violation**: Slide status transitions to `approved` (from either
       `draft` or `needs_revision`); `qa_passed` is set to `true`; an entry is
       appended to the slide record's `accepted_violations` array recording the
       invariant ID, user-provided reason, and timestamp. The violation is logged
       but no longer blocks.

   (b) **Manually revise**: Slide status transitions to `needs_revision`. The
       user provides revision instructions to the Slide Maker (not raw HTML editing). This triggers a new red-green cycle with `red_green_iteration` reset to 0.

   (c) **Discard**: Slide status transitions to `discarded`. The HTML file is
       deleted from `slides/`. The slug is freed for reuse. The entry remains
       in the `slides` array with `status: "discarded"` and is excluded from
       deck order by all components that read the array.

---

## 19. Scope Boundaries

### 19.1 In Scope

- Single-user, single-project-per-directory workflow
- Archetype-based project initialization with 7 named archetypes + Custom
- HTML slide generation with Mermaid, rough.js, and inline SVG
- User-provided images (JPG, PNG, SVG) with standalone and embedded placement modes
- LaTeX math rendering (inline and display) via abstracted renderer interface
- Style co-design dialog and locked style config
- Reference style import: PowerPoint, PDF, HTML file, or HTML directory as a style "by example" input that the Stylist uses as a starting point during the style dialog (REQ-CONSULT-13, REQ-CONSULT-14, Section 24.25).
- Live style previews: before approval at G2.1, the Stylist renders 3 placeholder slides using the draft style so the user can see the result, not just read the description. Optional `REGENERATE PREVIEWS` response lets the user see different placeholder content (REQ-STYLE-10, Section 24.40).
- Style guide as LLM context artifact
- Automated visual QA with Playwright screenshots and tiered evaluation
- Deterministic routing protocol with state machine and gate vocabulary
- Versioned PDF export (single Playwright session, one multi-page PDF)
- Versioned presenter script generation
- Query-driven view (`/debrief:view`)
- Session resumability
- macOS and Linux
- Conda-managed environment with automatic bootstrap (user installs only miniconda; all other dependencies are installed by the launcher)

### 19.2 Out of Scope

- Multi-user collaboration
- Cloud sync or remote storage
- Slide templates (all slides are generated from scratch per deck brief)
- Automated raster image manipulation (resizing, cropping, color correction of user-provided images)
- Windows support
- Any presentation format other than HTML-to-PDF (e.g., PowerPoint, Keynote)
- Real-time preview during authoring (preview is QA screenshot only)
- Animation or transitions in exported PDF
- Full LaTeX class support (custom packages, `\usepackage`, TikZ, pgfplots) — reserved for future versions

---

## 20. Assumptions

- **A-01:** The user has a working internet connection for model API calls.
- **A-02:** The user has miniconda (or mambaforge) installed before running `debrief new`. All other dependencies (Python, Playwright, Chromium, LibreOffice, python-pptx, PyMuPDF, json-repair) are installed automatically by the `bin/debrief` bootstrap logic inside a dedicated `debrief` conda environment.
- **A-03:** The user operates a single project at a time in a single Claude Code session.
- **A-04:** The user's terminal supports color output for error messages.
- **A-05:** miniconda is installed (Python 3.11 is provided inside the debrief conda env). The pre-flight check verifies `conda` is available on PATH; it does not check for a user-level Python installation.
- **A-06:** The user has read/write access to the project directory and to
  `~/.claude/plugins/cache/`.

---

# PART III — ARCHITECTURAL STRATEGY

## 21. Separation of Concerns

The plugin architecture enforces a strict separation of concerns:

- **Plugin code** (agents, skills, hooks, Python modules) lives in the plugin
  directory and is managed by Claude Code's plugin system.
- **Project data** (slides, state, briefs, output) lives in the project directory
  and is managed by the plugin at runtime.
- **Pipeline control state** (`debrief_state.json`) lives in the project directory
  and is managed exclusively by the routing and update_state scripts.
- **Ledger** (conversation history) lives in the project directory and is owned
  by the consultant agent.

This separation ensures that plugin updates do not corrupt project data, and that
resetting a project does not require reinstalling the plugin.

---

## 22. Key Architectural Decisions

### 22.1 Style Lock Enforced by Hook

Style enforcement is not enforced by convention; it is enforced by the
PreToolUse hook. The hook checks `style_locked` in `deck_state.json` before
every write to `slides/` or `assets/style.css`. This makes violation of the
style lock a hard error, not a soft guideline.

### 22.2 QA Before User Sees Output

The PostToolUse hook fires the QA agent synchronously after every slide write.
The main session MUST NOT show the slide to the user until the
G3.2 check has confirmed a passing `qa_log.jsonl`
entry for the current slug. *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)* Enforcement is via the consultant's Tool calls, not
skill-side polling or a technical lock. Any skill that presents a slide
directly (without going through the G3.2 check) is non-conformant (REQ-SLIDE-6).

### 22.3 Ledger Compaction Is a Blueprint Decision

The exact trigger for ledger compaction (entry count, token estimate, wall-clock
time, or explicit user command) is left to the blueprint author. The spec
requires only that:

1. The consultant handles compaction gracefully (reconstructs context from
   `deck_brief.md` + `deck_state.json`).
2. The compacted ledger retains a summary entry that identifies the compaction
   event and the basis for context reconstruction.

### 22.4 Single Playwright Session for PDF

PDF export uses a single Playwright `BrowserContext` — created inside the
`debrief.export` Python module via the `playwright-python` library — that
navigates to each slide HTML file in order and appends each page to a
multi-page PDF. No external PDF merge tool is used, and no separate
Playwright process or CLI is invoked. The blueprint author must implement
this as a single `BrowserContext` managed in-process by the export module.

### 22.5 Deck Brief Precedes Style Dialog

The style dialog is designed to be content-aware. It runs after the deck brief
exists so that the style agent can inspect the content direction — the presence
of code blocks, diagrams, tables, or dense text — before recommending fonts,
colors, and layout grammar. Implementations that run the style dialog before the
deck brief will produce style configs that may be poorly matched to the content.

The style dialog produces two complementary artifacts: `style_config.json` (structured values consumed by the compiler and QA checker) and `style_guide.md` (design rationale consumed by generation agents). Together they form the complete style contract. The structured config answers "what"; the style guide answers "why" and "how."

### 22.6 Deterministic Routing Prevents Drift

Without deterministic routing, the system relies on the LLM to remember where it
is, what to do next, and what context to load. Over a long session (20+ slides,
multiple groups, view interludes, escalations), this causes drift,
wrong context loading, and ambiguous transitions. The routing protocol
(Section 14.15) solves this by making every transition deterministic: state file
as single source of truth, routing function reads state and outputs structured
action blocks, scoped context per action via the prepare script, and gate
vocabulary enforcement.

### 22.7 The Six-Step Action Cycle

The orchestrator's complete behavior is six steps, repeated:

1. Run `debrief.routing` — receive action block
2. Run PREPARE command (if present) — produces task prompt file
3. Execute the ACTION — invoke agent / present gate / run command
4. Capture the result — agent status line or gate response
5. Run POST command (if present) — updates `debrief_state.json`
6. Go to step 1

### 22.8 Context Scoping Rules

Each agent invocation gets a fresh prompt assembled from specific files, not the
conversation tail. This eliminates drift from accumulated context.

| Agent | Context Always Loaded | Context Conditionally Loaded |
|-------|----------------------|------------------------------|
| Consultant (discovery) | `deck_state.json` | (none — first invocation) |
| Consultant (group planning) | `deck_brief.md`, `deck_state.json`, `style_guide.md`, last 2 ledger entries | `debrief_state.json` (`completed_groups`, `selected_figures`); `.debrief/paper_analysis_<paper_slug>.md` when `papers_provided=true` |
| Consultant (after escalation) | `deck_brief.md`, `deck_state.json`, escalation description | current group's slide records |
| Stylist | `${CLAUDE_PLUGIN_ROOT}/templates/style_config.json` (injected as a `## Schema Starting Point` JSON fenced code block per §24.20 and BC-4.7b; see BUG-AUDIT-14 — this section is PREPENDED to the task prompt so the stylist's first turn begins with a compiler-valid schema instance), `deck_brief.md` (esp. Content Signals), `deck_state.json`, `${CLAUDE_PLUGIN_ROOT}/references/paperbanana-diagram-style-distilled.md`, `${CLAUDE_PLUGIN_ROOT}/references/paperbanana-plot-style-distilled.md`, `${CLAUDE_PLUGIN_ROOT}/references/ai4vis-survey-distilled.md`, `${CLAUDE_PLUGIN_ROOT}/references/preview_placeholder_content.md` (bundled craft-knowledge references per REQ-STYLE-2; `preview_placeholder_content.md` is the per-archetype placeholder catalog consumed on every Phase 2 preview-generation cycle per REQ-STYLE-10 step 2), plus any files matching `${CLAUDE_PLUGIN_ROOT}/references/reference-*.md` (Section 24.39 growth-model glob; currently empty in v1.1 — the prepare script MUST glob this pattern and append any matches to the Stylist's context in alphabetical order so the growth-model contract is honored without a Debrief version bump when a new reference file is added) | user's style-related dialog turns from ledger; `.debrief/draft/derived_style_guide.md` when `style_import_mode` is `"baseline"` or `"inspiration"`; `.debrief/draft/analyzer_metadata.json` when present (PPTX metadata from `debrief.style_analyzer`); `${CLAUDE_PLUGIN_ROOT}/references/paperbanana-derivation-meta-prompt.md` when `reference_provided=true` (the Stylist is in **reference-derivation mode** and needs the meta-prompt to know how to analyze the image batch and produce `.debrief/draft/derived_style_guide.md` per Section 24.25.4); `.debrief/gate_data.json` handled by Section 24.20 cross-cycle rule |
| Slide Maker (new slide) | `style_guide.md`, slide brief, Content Signals from `deck_brief.md` | `assets/style.css` (for reference); most recent 1-2 approved slides from `slides/` as few-shot context (REQ-SLIDE-8 non-normative guidance) |
| Slide Maker (red-green fix) | `style_guide.md`, slide HTML, latest `qa_log.jsonl` entry (with `revision_instructions`) | (nothing else — fixes are self-contained) |
| Slide Maker (user revision) | `style_guide.md`, slide HTML, user's revision instruction | latest QA result (for context) |
| QA agent | Slide HTML, screenshot path, `${CLAUDE_PLUGIN_ROOT}/references/slide-qa-checklist.md` (craft-knowledge baseline for Tier 2 judgment per Section 24.22; the Section 16 INV-*/VETO-* enumeration is separately baked into the agent's system prompt), `style_guide.md` | (nothing else) |

**Rhetorical role enforcement (REQ-CONSULT-15 downstream wiring).** The Slide Maker's prepare context MUST include the `rhetorical_role` field from the current slide brief. When the role is `hook`, the task prompt instructs the Slide Maker to use a visually prominent layout (large typography, minimal text, optional full-bleed image). When the role is `pathos`, the task prompt instructs the Slide Maker to prioritize emotional resonance (patient stories, photographs, clinical significance). When the role is `logos`, the task prompt instructs the Slide Maker to prioritize data clarity (clean data exhibits, statistical annotations, reference lines). When the role is `ethos`, the task prompt instructs the Slide Maker to prioritize credibility signals (citations, methodology callouts, prior work references). When the role is `synthesis`, `recap`, or `transition`, the task prompt provides role-specific guidance. The Slide Maker additionally reads the "Rhetorical Role Styling" section of `style_guide.md` (REQ-STYLE-7) to apply project-specific visual treatment for the role.

#### 22.8.1 Per-Gate Prepare Context

For every human gate in Section 14.16, the `prepare` script assembles a specific context by file path. The prompt template, placeholders, and file inputs are listed together so that blueprint implementers have one authoritative source for "what the user sees at each gate."

| Gate ID | Files loaded by prepare | Notes |
|---------|-------------------------|-------|
| `G1.1_brief_review` | `deck_brief.md`, `debrief_state.json` | Placeholders `{archetype_name}` sourced from `debrief_state.json`; `{presentation_type}`, `{allocated_time}` sourced from `deck_brief.md` Content Signals. |
| `G1.2_style_analysis` | `.debrief/draft/derived_style_guide.md`, `assets/reference/slides/*.png` (listed as links), `debrief_state.json` | Placeholder `{derived_style_guide_summary}` is the top-level headline plus key per-section bullets of the derived draft; `{reference_thumbnail_links}` is computed from `assets/reference/slides/`; `{reference_filename}` and `{reference_modality}` sourced from `debrief_state.json`. |
| `G1.3_figure_selection` | `.debrief/paper_analysis_<paper_slug>.md` | The prepare script expands the numbered figure list into one line per figure. Placeholder `{N}` is the figure count. |
| `G2.1_style_config_review` | `.debrief/draft/style_config.json`, `.debrief/draft/style_guide.md`, `.debrief/draft/preview_images/preview_*.png` | Draft files are included verbatim. Placeholder `{draft_style_guide_summary}` summarizes the draft guide; `{preview_image_links}` is the bullet list of preview image links (REQ-STYLE-10). |
| `G3.2a_oscillation_review` | `.debrief/snapshots/<slug>_iter_<N>.html` (best-known-good), latest two `qa_log.jsonl` entries for slug, `output/screenshots/<slug>.png` | Placeholders `{previous_failure_count}`, `{current_failure_count}`, `{previous_failure_invariants}`, `{current_failure_invariants}` are computed from the latest two `qa_log.jsonl` entries for the current slug per Section 14.16.1. |
| `G3.3_slide_review` | `slides/<slug>.html`, `output/screenshots/<slug>.png`, latest `qa_log.jsonl` entry for slug (Tier 2 warnings), `.debrief/approval_<slug>.json` (existence check only — consumed by `update_state` on APPROVED) | Normal-path gate after GREEN. |
| `G3.3_slide_review_post_diagnostic` | `.debrief/diagnostic_<slug>.md`, `slides/<slug>.html`, `output/screenshots/<slug>.png`, latest `qa_log.jsonl` entry for slug, `.debrief/approval_<slug>.json` (existence check) | Post-diagnostic variant gate after EXHAUSTED. |
| `G3.4_group_review` | `output/view.html` (group storyboard), per-slide files: `slides/<slug>.html` and `output/screenshots/<slug>.png` for every slide in the current group | Rendered via `/debrief:view current` as a side effect of prepare. |
| `G3.5_more_slides` | `deck_brief.md`, `deck_state.json` (approved slide count summary) | No placeholders. |
| `G3.6_deck_ending` | Full-deck `output/view.html`, `deck_state.json` summary | Placeholder `{last_slide_title}` sourced from `deck_state.json`. |
| `G3.V_view_dispatch` | `output/view.html` (from the view that was just opened) | No placeholders. |
| `G4.1_export_options` | `deck_state.json` summary (approved slide count, group summary) | No placeholders. |
| `G4.2_backup_decision` | `deck_state.json` (approved slide count) | No placeholders. |
| `G4.3_backup_complete` | `deck_state.json` (backup slide subset) | No placeholders. |
| `G4.4_export_confirm` | Export ordering summary (from the ordering dialog), `deck_state.json` active presentation record | No placeholders. |
| `G4.6_post_export` | `deck_state.json` latest presentation record (folder, export_count) | No placeholders. |

Machine gates (G2.2, G3.1, G3.2, G4.5) load no prepare context because they present nothing to the user; they read state files directly. See REQ-ROUTE-6. *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)*

---

## 23. Recommended Implementation Sequence

Blueprint authors should implement Debrief in the following order to allow
incremental testing. The order reflects a strict bottom-up dependency DAG: every step MUST complete before any later step that imports it.

1. Plugin scaffold: `plugin.json`, `settings.json`, `environment.yml`, `${CLAUDE_PLUGIN_ROOT}/templates/project_claude.md` (the project `CLAUDE.md` template, owned by the scaffold — see Section 24.7 and REQ-INIT-3).
2. **State Management Library** (`debrief.deck_state` and `debrief.debrief_state`): read/write/validate the two state files. This is a library module imported by both the Launcher (step 3) and all routing-adjacent modules (step 4). It exposes functions for reading, writing, and validating `deck_state.json` and `debrief_state.json`. The specific API (function signatures, validation rules) is a blueprint decision, but the module MUST enforce: JSON schema validation on read, atomic write (write-to-tmp then rename), fcntl.flock-based locking on `debrief_state.json` (per Section 24.33), SHA-256 state hash computation and verification (per REQ-ROUTE-8), and status filtering helpers for deck order queries.
3. **Launcher script** (`bin/debrief` + `debrief.launcher`): new-project and resume flows, pre-flight checks. The launcher IMPORTS the state management library from step 2 because its first job is to write initial `debrief_state.json` and `deck_state.json` with atomic rename + schema validation + state hash. It also consumes `${CLAUDE_PLUGIN_ROOT}/templates/project_claude.md` from step 1 and renders it into the project directory as `CLAUDE.md`. Putting Launcher before State Management Library would mean Launcher has to re-implement the atomic-rename + hash + validation logic, which is exactly what the library exists to centralize.
4. Routing protocol: `debrief.routing`, `debrief.update_state`, `debrief.prepare` *(gutted -- BUG-AUDIT-31; the consultant handles all dispatch via Tool calls)*
5. Consultant agent and ledger: dialog loop, deck brief production, compaction
6. Style compiler: `style_config.json` to `style.css`
7. Style skill: dialog, approval, lock, style guide generation
8. Slide agent: brief-to-HTML, design invariants, style-guide-driven single-path generation (REQ-SLIDE-8). `debrief.asset_ingest` (the user-image copy helper, per REQ-ASSET-1) is part of this step's content utility module set.
9. QA agent: screenshot, tiered invariant checks, revision_instructions, qa_log. `debrief.qa_checker` programmatic invariant module belongs here.
10. Math renderer module: `debrief.math_renderer`
11. Hook wiring: PreToolUse write-auth, PostToolUse QA
12. Export module: Playwright PDF render
13. Remaining skills: view, script, save, reset
14. End-to-end integration test: new project through export
15. **Self-evaluation and submission.** After the end-to-end integration test passes, the Blueprint Author MUST walk through every category in Section 24.35 (Categories 1-11), answer every item, and produce `blueprint/blueprint_self_eval.md` recording the answers. Categories 1-10 test semantic correctness; Category 11 tests mechanical consistency (static analysis). A completed self-eval document is required for submission. The Blueprint Reviewer will reject any blueprint that arrives without a self-eval or with an incomplete self-eval.

The step 2 ↔ step 3 ordering (State Management Library before Launcher) is load-bearing. Every atomic write, hash verification, and schema check that appears in the launcher's startup path is a call into step 2. Reversing the order forces step 3 to duplicate step 2's logic.

---

## 24. Blueprint Recommendations for Plugin Implementation

This section provides explicit guidance for the blueprint author implementing
the Debrief plugin. It addresses implementation details that are architectural
decisions (not behavioral requirements) but that critically affect correctness.

### 24.1 SKILL.md File Structure

Each `SKILL.md` file must have:

1. **YAML frontmatter** (fields as specified in Section 5). The frontmatter must
   be the first block in the file, delimited by `---`.
2. **Instruction body**: A markdown document that is the system prompt for the
   skill. It must cover:
   - What the skill does (one paragraph)
   - Pre-conditions the skill must check before acting (e.g., style lock status,
     deck brief existence)
   - Step-by-step behavior for each branch (new slide vs. revision, etc.)
   - How to handle the optional slug argument: if present, find the existing
     slide; if absent, yield by setting
     `current_slide_slug: null` (the consultant will invoke the Consultant agent
     to produce the next brief) *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*
   - That the skill MUST NOT poll `qa_log.jsonl` and MUST NOT loop on red-green
     iterations. Red-green orchestration is the consultant's responsibility
     via the G3.2 check (REQ-SLIDE-6). *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)*
   - What approval data to provide (the `update_state` script writes to `deck_state.json`)

The instruction body must be written as imperative instructions to Claude, not
as documentation for a human reader.

CORRECTNESS RISK: The QA gate before user presentation is enforced by the
G3.2 check, not by a technical lock and
not by skill-side polling. *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)* Any deviation from the consultant-driven red-green
orchestration (REQ-SLIDE-6) will silently break the QA gate. Blueprint authors
must treat the G3.2 check as safety-critical.

**Consultant brief acquisition for `/debrief:slide`:**

When `/debrief:slide` is invoked WITHOUT a slug argument, the skill does NOT
invoke the Consultant directly. Instead, it sets `current_slide_slug: null` in
`debrief_state.json` (via `update_state --skill-prelude`) and yields. The consultant, detecting `current_slide_slug: null` in
`production/group_planning`, dispatches the
Consultant agent with the current brief + completed_groups
context. The Consultant produces the next slide brief(s) as files in `.debrief/briefs/`.
Control returns to the consultant which transitions to `production/red_green`
with the first brief's slug. Skills have no `Agent` tool in their `allowed-tools`
list. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*

### 24.2 Agent `.md` File Structure

Each agent `.md` file must have:

1. **YAML frontmatter** (fields as specified in Section 6).
2. **System prompt body**: A markdown document that is the agent's system prompt.
   It must cover:
   - The agent's role and the single responsibility it holds
   - The files it is allowed to read and write (be explicit — agents should not
     write outside their designated files)
   - Context management instructions: what to read at session start to reconstruct
     state, what to write after each turn to persist state
   - For the consultant: explicit instructions on how to handle post-compaction
     context reconstruction from `deck_brief.md` + `deck_state.json`
   - For the slide agent: the complete list of design invariants (Section 16) as
     a checklist embedded in the prompt. The prompt MUST instruct the agent to read `style_guide.md` at the start of every generation or revision task. The style guide takes precedence over the agent's own aesthetic judgment. When the style guide specifies a visual pattern for a slide type, the agent MUST follow it.
   - For the QA agent: the complete invariant checklist with specific checking
     instructions for each (e.g., how to measure contrast ratio, how to count
     bullets, how to validate HTML5), organized by Tier 1 and Tier 2
   - For the bug diagnostic agent: how to read `qa_log.jsonl` to understand the
     failure history before diagnosing

### 24.3 hooks.json Structure and Behavior

The blueprint author must implement two hooks:

**PreToolUse (write-auth):**

- Type: `command` — executes a shell script synchronously before the write.
- Matcher: `Write|Edit` — fires on both tool types.
- The script at `${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth` must:
  1. Read the `style_locked` field from `deck_state.json` in the current
     working directory (the project directory).
  2. If the target path is inside `slides/` or is `assets/style.css` AND
     `style_locked` is `false` or absent, exit with code 2 and print to stderr:
     `"ERROR: Style config not yet locked. Run /debrief:style first."`
  3. If the target path is outside the project directory, exit with code 2 and
     print to stderr: `"ERROR: Write outside project directory is not permitted."`
  4. Otherwise, exit with code 0.

  (Exit code 2 is Claude Code's "deny and show stderr to the LLM" signal; exit code 1 is a non-blocking hook failure that does not block the tool call. The earlier revision of this spec said "exit code 1 to deny", which would silently permit the write under the Claude Code hook protocol. The correct deny code is 2.)
- The script must use `${CLAUDE_PLUGIN_ROOT}` for any references to plugin
  resources.
- The timeout of 10 seconds is sufficient; the script must complete in under 1 second
  in normal operation.

**Claude Code hook input format.** PreToolUse command hooks receive the tool invocation context as a JSON object on stdin. The JSON structure is:

```json
{
  "tool_name": "Write" | "Edit",
  "tool_input": {
    "file_path": "<absolute or cwd-relative path>",
    "content": "<file content>"
  }
}
```

The `check-write-auth` script MUST parse stdin as JSON and extract `tool_input.file_path` to determine the target write path. The recommended parser is `jq -r '.tool_input.file_path'` because it handles edge cases (quoted paths, special characters, null handling) correctly and is a single binary dependency. `jq` MUST be declared in the plugin's `environment.yml` conda dependencies so the bash hook script has access to it. `jq` is available on conda-forge and is a ~200KB binary.

**PostToolUse (visual-qa):**

- Type: `agent` — Claude Code spawns an agent-type hook with an inline prompt (per Section 7.1). The hook does NOT reference the named `visual-qa` agent; the inline prompt is a separate, shorter instruction tailored to the hook context. The `agents/visual-qa.md` file is used when the visual-qa agent is invoked by name elsewhere in the pipeline (e.g., as the diagnostic agent). See Section 7.1 for the distinction.
- Matcher: `Write|Edit`.
- The prompt must instruct the agent to:
  1. Identify the file just written from the tool use context.
  2. If the file is not in `slides/`, skip QA and exit immediately.
  3. The QA agent invokes `python -m debrief.qa_checker` via Bash, passing the slide HTML file path as an argument. The `qa_checker` module opens its own `sync_playwright()` context (per Section 24.10.2), renders the slide HTML, takes the screenshot, saves it to `output/screenshots/<slug>.png`, runs all programmatic invariant checks, and outputs a JSON result to stdout. The QA agent reads the checker's output and writes the final record to `qa_log.jsonl` (merging programmatic checks with any VLM-based checks the agent performs on the screenshot).
  4. Write a result record to `output/qa_log.jsonl` using the checker output,
     including `revision_instructions` for any Tier 1 failures and `warnings` for Tier 2 issues.
- If Playwright fails to take a screenshot (timeout, crash, or error), the QA agent MUST write a failure record to `qa_log.jsonl` with `passed: false` and a single failure entry: `{"invariant": "SCREENSHOT", "description": "Playwright screenshot failed: <error>", "revision_instruction": "Verify slide HTML is valid and does not cause render hangs."}`. This counts as one red-green iteration.
- The agent must NOT block indefinitely; it must exit within the 60-second timeout.
- After the Slide Maker writes the slide HTML, the PostToolUse hook fires the
  visual-qa agent synchronously. The QA agent invokes `qa_checker` (which takes the screenshot internally), runs any VLM-based checks on the resulting screenshot, and writes to `qa_log.jsonl` before the hook returns. No polling is
  needed — the G3.2 check reads the result
  directly. *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)* If the hook times out (60s), the missing qa_log entry is treated as
  an implicit RED with a `timeout` failure reason. (See REQ-SLIDE-6 for the
  definitive timing contract.)
- The qa_log.jsonl entry format is defined in REQ-QA-3 and REQ-QA-7.

**`qa_checker.py` module contract:**

The `debrief.qa_checker` module takes a slide HTML file path as input, opens its own `sync_playwright()` context (per Section 24.10.2), renders the slide HTML, takes the screenshot, saves it to `output/screenshots/<slug>.png`, runs all programmatic invariant checks (Section 16) in tiered order (Tier 1 first, then Tier 2), and outputs a JSON result to stdout.

### 24.4 `bin/debrief` Invocation Contract

This subsection is the canonical implementation contract for the `bin/debrief` launcher script. It supersedes Section 9.4's high-level overview.

**Script type:** Bash shell script. Must work on macOS and Linux.

**Environment variables expected:**
- `${CLAUDE_PLUGIN_ROOT}` — set by Claude Code to the plugin's cache directory.
- `${HOME}` — standard user home directory.

**Step-by-step contract:**

Steps 1–5 execute in the bash wrapper BEFORE any Python invocation because the conda env (and therefore the Python package) does not yet exist. Steps 5.5–8 execute after env activation and are implemented either inline in the bash wrapper (smoke test, marker checks) or via `python -m debrief.launcher preflight` (vendor hash verification). This split is load-bearing: the Python module cannot run before the env is activated.

1. **Conda detection.** Run `command -v conda`. If it returns empty, print:
   ```
   ERROR: Debrief requires miniconda or mambaforge.
   Install from https://docs.conda.io/en/latest/miniconda.html and retry.
   ```
   Exit code 1.

2. **Source conda.** Run `source "$(conda info --base)/etc/profile.d/conda.sh"` to enable `conda activate` in the script.

3. **Env existence check.** Run `conda env list | awk '{print $1}' | grep -qx debrief`. If the env does not exist, proceed to step 4. Otherwise, skip to step 5.

4. **Env creation.** Print `First-run setup: creating the debrief conda environment (this takes 5-15 minutes)...`. Run:
   ```bash
   conda env create -f "${CLAUDE_PLUGIN_ROOT}/environment.yml" -n debrief
   ```
   On failure, before exiting: run `conda env remove -n debrief -y` to clean up any partial env so the next invocation retries cleanly. If the partial removal also fails, print BOTH error messages and exit code 1 with the instruction:
   ```
   Partial debrief env exists and could not be removed automatically.
   Run `conda env remove -n debrief --force` manually, then retry `debrief new`.
   ```
   Otherwise print the conda error output and exit code 1.

5. **Env activation.** Run `conda activate debrief`. If activation fails, print the error and exit code 1.

5.5. **Post-activation smoke test.** After `conda activate debrief`, run:
   ```bash
   python -c 'import playwright; import pptx; import fitz; import json_repair'
   ```
   On ImportError or non-zero exit, print the Section 9.3.1 standardized env-corruption error (exit code 2):
   ```
   ERROR: debrief core dependencies (playwright, python-pptx, PyMuPDF, json-repair) are not importable in the debrief conda environment.
   This indicates the environment is corrupt or was externally modified.
   Recovery: run `debrief --rebuild-env` to recreate the environment from environment.yml.
   ```
   This catches externally-modified or corrupted envs before any project state is touched.

6. **Package install marker check.** Compute the plugin version (read from `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`, `version` field). Check for `${HOME}/.cache/debrief/pkg_version_<version>.marker`. If missing:
   ```bash
   mkdir -p "${HOME}/.cache/debrief"
   pip install -e "${CLAUDE_PLUGIN_ROOT}" || { echo "ERROR: pip install -e failed. Run 'debrief --rebuild-env' to retry."; exit 1; }
   touch "${HOME}/.cache/debrief/pkg_version_<version>.marker"
   ```
   The marker is written ONLY on `pip install` exit code 0. On failure, do NOT write the marker, print the error and the recovery hint, and exit code 1.

7. **Chromium install marker check.** Check for `${CONDA_PREFIX}/.debrief_chromium_installed`. If missing:
   ```bash
   python -m playwright install chromium || { echo "ERROR: playwright install chromium failed. Run 'debrief --rebuild-env' to retry."; exit 1; }
   touch "${CONDA_PREFIX}/.debrief_chromium_installed"
   ```
   The marker is written ONLY on exit code 0. Storing the marker inside `${CONDA_PREFIX}` means destroying the env (via `--rebuild-env` or external removal) automatically invalidates the marker — no separate cleanup step is needed.

8. **Vendor hash verification.** Run:
   ```bash
   python -m debrief.launcher preflight
   ```
   `debrief.launcher.main()`'s prologue executes (at minimum) `verify_vendor_hashes()` per Section 24.27. On hash mismatch, exit with code 1 and print the specific failing file PLUS the recovery instruction:
   ```
   ERROR: Plugin assets appear corrupted (vendor hash mismatch on <file>).
   Expected: <expected_hash>
   Actual:   <actual_hash>
   See: ${CLAUDE_PLUGIN_ROOT}/assets/vendor/VERSIONS.md
   Recovery: reinstall the Debrief plugin via Claude Code's plugin management
             (e.g., `/plugin reinstall debrief`). If reinstall fails, delete
             ${CLAUDE_PLUGIN_ROOT} and reinstall from source.
   ```
   `--rebuild-env` does NOT recover from vendor hash mismatches because vendor files live under `${CLAUDE_PLUGIN_ROOT}/assets/vendor/`, not inside the conda env.

9. **Subcommand dispatch.** Based on `$1`:
   - `new` — run `python -m debrief.launcher new`, then launch Claude Code with the plugin enabled.
   - `--rebuild-env` — execute the `--rebuild-env` branch defined below.
   - (no argument) — check for `deck_state.json` in cwd. If present, launch Claude Code with the plugin enabled. If absent, print: `ERROR: No project found in the current directory. Run 'debrief new' to create one.` Exit code 1.

10. **Launch Claude Code.** Use whatever command Claude Code provides to start a new session with the plugin enabled. The specific command is a blueprint decision based on the installed Claude Code version.

**`--rebuild-env` branch:**

The rebuild logic lives in the bash wrapper, NOT in `debrief.launcher` (the Python module cannot run before the env exists). The branch MUST:

1. Delete `${HOME}/.cache/debrief/pkg_version_*.marker` files so the next run reinstalls the package from scratch. (The chromium marker under `${CONDA_PREFIX}/.debrief_chromium_installed` does not need explicit deletion because removing the env removes the prefix.)
2. Run `conda env remove -n debrief -y`. On failure, print:
   ```
   ERROR: Failed to remove the debrief conda env.
   Run `conda env remove -n debrief --force` manually, then retry `debrief --rebuild-env`.
   ```
   Exit code 1.
3. Re-execute the script from step 3 (env existence check). The re-execution does NOT pass `--rebuild-env` again, preventing infinite recursion. In practice this is implemented by the wrapper setting a local `REBUILD_DONE=1` flag and recursing via `exec "$0"` with the flag in the environment.
4. If the rebuild itself fails (env creation fails the second time), exit code 1 with:
   ```
   ERROR: Rebuild failed. Manual intervention required.
   Try: `conda env remove -n debrief --force` and then `conda env create -f ${CLAUDE_PLUGIN_ROOT}/environment.yml -n debrief`.
   ```

**Marker file semantics:**

- `${HOME}/.cache/debrief/pkg_version_<version>.marker` — re-run `pip install -e` when the plugin version changes. Deleted by `--rebuild-env` (step 1 of rebuild branch).
- `${CONDA_PREFIX}/.debrief_chromium_installed` — run Chromium install once per env. Automatically invalidated when the env is removed (since the prefix ceases to exist). Neither marker persists across rebuilds. The earlier claim that the chromium marker survives `--rebuild-env` was incorrect: `conda env create` does not install Chromium — Playwright downloads it via a separate `python -m playwright install chromium` step — and destroying the env destroys the Playwright-managed Chromium install.

**Recovery matrix:**

- Partial / corrupt env: step 4 self-cleans; user can also run `debrief --rebuild-env`.
- `pip install -e` failure: marker not written; user runs `debrief --rebuild-env` or retries.
- `playwright install chromium` failure: marker not written; user runs `debrief --rebuild-env` or retries.
- Vendor hash mismatch: plugin reinstall (NOT `--rebuild-env`). See Section 24.27.
- Externally-modified env: step 5.5 smoke test exits 2; user runs `debrief --rebuild-env`.

### 24.5 `${CLAUDE_PLUGIN_ROOT}` vs. `${CLAUDE_PLUGIN_DATA}`

- Use `${CLAUDE_PLUGIN_ROOT}` in all scripts, skill bodies, agent prompts, and
  hooks for references to plugin code and static assets.
- Use `${CLAUDE_PLUGIN_DATA}` for any plugin-level state that must survive plugin
  version updates. Examples: a global index of known project directories (for
  discovery), shared font cache.
- Do NOT use `${CLAUDE_PLUGIN_DATA}` for per-project data. Per-project data
  belongs in the project directory only.
- Do NOT hardcode `~/.claude/plugins/cache/{id}/`; always use
  `${CLAUDE_PLUGIN_ROOT}`.

### 24.6 User Config Substitution

Claude Code performs `${user_config.KEY}` substitution in skill and agent
prompts. If any user-configurable values are needed (e.g., a preferred default
font family, a default export resolution), define them in `settings.json` under
a `user_config` key and reference them via `${user_config.KEY}` in skill bodies
and agent prompts. Do not hardcode user preferences in agent prompts.

### 24.7 Plugin Component Placement

All plugin components live at `${CLAUDE_PLUGIN_ROOT}`, **except** the manifest file `plugin.json` which lives inside `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` per Claude Code's plugin convention (see Section 2). No other files live inside `.claude-plugin/`.

**Plugin-scaffold artifacts** (owned by the scaffold, not by any agent or skill):

- `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` — plugin manifest (Claude Code convention requires this location).
- `${CLAUDE_PLUGIN_ROOT}/settings.json` — Claude Code settings integration.
- `${CLAUDE_PLUGIN_ROOT}/environment.yml` — conda env definition.
- `${CLAUDE_PLUGIN_ROOT}/templates/project_claude.md` — the project `CLAUDE.md` template rendered into each new project by the launcher (per REQ-INIT-3). This template is NOT part of the agents unit; it is scaffold data committed to the plugin repository alongside the manifest.
- `${CLAUDE_PLUGIN_ROOT}/assets/vendor/` — bundled Mermaid, rough.js, KaTeX (per Section 24.27).
- `${CLAUDE_PLUGIN_ROOT}/archetypes.json` — archetype defaults (per Section 24.26).
- `${CLAUDE_PLUGIN_ROOT}/references/` — bundled reference documentation (per Section 24.39): distilled PaperBanana style guides, the slide QA checklist, the AI4VIS distillation, the preview placeholder content catalog, and per-file `VERSIONS.md`. The plugin does NOT ship an exemplar library (per REQ-SLIDE-8); there is no `exemplars/` directory.
- `${CLAUDE_PLUGIN_ROOT}/hooks/hooks.json` — hook definitions.

Project data lives ONLY in the project directory. No project data is written to `${CLAUDE_PLUGIN_ROOT}` or `${CLAUDE_PLUGIN_DATA}` during normal operation.

### 24.8 Style Config Locking Implementation

Style locking must be implemented at two levels:

1. **File system**: `style_config.json` and `style_guide.md` are set read-only (`chmod 444`) after
   approval. This is a safety net.
2. **State field**: `deck_state.json` is updated to set `"style_locked": true`.
   This is the field checked by the PreToolUse hook.

The hook checks the state field, not the file system permissions. Both must be
set consistently.

**Caller and sequence (G2.1 STYLE APPROVED → G2.2 LOCK SUCCESS/FAILED).**

`update_state` is the sole caller for the compile-and-lock sequence. On G2.1 `STYLE APPROVED`, `update_state` performs the following sequence:

0. Validate preconditions: `.debrief/draft/style_config.json` and `.debrief/draft/style_guide.md` both exist and parse as valid JSON/Markdown. If either is missing or corrupt, fire machine gate G2.2 *(dead -- BUG-AUDIT-31)* with `LOCK FAILED` and attach a "draft artifacts missing" error to the gate context.
1. Atomically promote the draft artifacts to the project root:
   - `os.rename('.debrief/draft/style_config.json', 'style_config.json')`
   - `os.rename('.debrief/draft/style_guide.md', 'style_guide.md')`
   Both renames are performed before any compilation. On any OSError during promotion, abort: fire G2.2 `LOCK FAILED` with the concrete error and leave `.debrief/draft/` intact for retry.
2. Invoke `python -m debrief.style_compiler style_config.json assets/style.css` as a subprocess (from the project root).
3. On subprocess exit code 0, call `os.chmod()` to set `style_config.json`, `style_guide.md`, and `assets/style.css` to mode `0o444`.
4. Write `style_locked: true` to `deck_state.json` atomically (per Section 24.33).
5. Remove `.debrief/draft/` recursively (shutil.rmtree).
6. Fire machine gate G2.2 *(dead -- BUG-AUDIT-31)* with response `LOCK SUCCESS`.

On compiler failure (non-zero exit code or exception at step 2):
- Do NOT chmod any files.
- Do NOT set `style_locked`.
- Do NOT remove `.debrief/draft/` — it is now empty of the draft files (since they were atomically promoted in step 1) but any preview artifacts remain for diagnostic purposes.
- The just-promoted `style_config.json` and `style_guide.md` at the project root ARE the canonical versions; a re-lock attempt should re-run from step 2 (not step 1).
- Fire machine gate G2.2 *(dead -- BUG-AUDIT-31)* with response `LOCK FAILED` and attach the compiler's stderr to the gate context.

On G2.1 `STYLE REVISE`, `update_state` removes `.debrief/draft/` recursively (discarding all draft artifacts) before re-invoking the Stylist, so the next dialog starts from a clean slate.

On G2.1 `REGENERATE PREVIEWS`, `update_state` retains `.debrief/draft/style_config.json`, `.debrief/draft/style_guide.md`, `.debrief/draft/derived_style_guide.md`, and `.debrief/draft/preview_style.css` (no re-synthesis of the style). It writes `.debrief/gate_data.json` with `{"gate_id": "G2.1_style_config_review", "data": {"regenerate_previews": true}}`, removes `.debrief/draft/preview_slides/` and `.debrief/draft/preview_images/`, and transitions sub_phase to `style/style_dialog`. The next prepare cycle reads the gate_data flag and re-invokes the Stylist in preview-regeneration mode. The Stylist re-runs REQ-STYLE-10 steps 2-4: it selects a different placeholder content entry from `${CLAUDE_PLUGIN_ROOT}/references/preview_placeholder_content.md`, writes new preview HTML to `.debrief/draft/preview_slides/`, invokes `debrief.preview_renderer` to produce new PNGs in `.debrief/draft/preview_images/`, and re-presents G2.1. The style config, style guide, and derived draft are not re-synthesized.

`update_state` is the sole caller. No skill, agent, or action-block `run_command` fires the compiler — earlier spec drafts that hinted at a `run_command` action from G2.1's post-transition are superseded. The fire-and-forget subprocess model is owned by `update_state`.

### 24.9 Ledger Compaction

The exact compaction trigger is left to the blueprint author. Acceptable triggers
include:

- Entry count exceeds a threshold (e.g., 100 entries)
- Estimated token count of the ledger exceeds a threshold
- Explicit user command

Regardless of trigger, the compaction procedure must:

1. Summarize the ledger into a single compaction entry that captures: decisions
   made, slides approved, style choices locked, and narrative direction.
2. Archive the full ledger to a named file (e.g., `ledger_compact_001.jsonl`).
3. Write a new `ledger.jsonl` containing only the compaction summary entry.
4. The consultant must be able to reconstruct full context from the compaction
   summary entry + current `deck_brief.md` + current `deck_state.json`.

### 24.10 Export Implementation Detail

**Bash invocation contract:**

The `/debrief:export` skill invokes `python -m debrief.export` via Bash. The
module takes the project directory path (current working directory) as its first
argument. The module reads `deck_state.json`, the `slides/` directory, and
`style_config.json`. It orchestrates Playwright to produce the PDF. Before
invoking Playwright, the export module invokes the style compiler
(`python -m debrief.style_compiler style_config.json assets/style.css`) to
ensure `assets/style.css` is up to date with the current style config. Exit
code: 0 on success, 1 on error. Errors are printed to stderr.

**Export ordering dialog:**

Before rendering, the export skill MUST conduct a brief dialog with the user:

1. Present the current slide order (from the `slides` array) and ask: "Is the
   sequence correct?"
2. Ask: "Where does the formal presentation end?" The user designates a split
   point using 1-based human counting (e.g., "after slide 8"). The consultant
   converts this to a 0-based `separator_position` by taking the number as-is:
   "after slide 8" maps to `separator_position: 8`, meaning the separator is
   inserted before `slides[8]` (i.e., between the 8th and 9th slides in
   1-based counting). This value is written to the active presentation folder
   record in `deck_state.json`, not to the top-level `separator_position` field.
3. Ask: "What should the separator slide contain?" Options include: an
   acknowledgments slide, a summary slide, a "Questions?" title, or anything the
   user wants. Default: an empty slide styled with the deck's color palette. The
   separator content choice is stored as `separator_content` in the presentation
   folder record and passed to the separator generator.
4. Ask: "What should this presentation folder be named?" The proposed default
   MUST be computed deterministically by code, NOT invented by the LLM, per
   BC-4.7c / BUG-AUDIT-15. The canonical computation is
   `routing.propose_presentation_folder_name(deck_state, today)` which returns
   `<YYYY_MM_DD>_<shortened_title>` where `YYYY_MM_DD` is today's date (UTC)
   and `<shortened_title>` is derived from `deck_state.project_name` by
   applying the Debrief Identifier Sanitization Algorithm (Section 24.10.1)
   with `max_length=40`. The empty-input fallback is `"untitled"` per the
   sanitizer contract, so the proposal always has a non-empty title portion.
   Example: `2026_04_30_svp_presentation`. The proposal is injected into the
   export-dialog task prompt at prepare time per BC-4.7c (the prepare module *(dead -- BUG-AUDIT-31)*
   prepends a `## Proposed Presentation Folder` section to the task prompt
   for any action in `_EXPORT_DIALOG_ACTIONS`). The Consultant presents the
   default to the user, who MAY confirm or override it. The Consultant MUST
   NOT invent an alternative format — the deterministic computation is the
   single source of truth for the default value. The confirmed name is used
   as the folder name inside `output/`.

#### 24.10.1 Debrief Identifier Sanitization Algorithm

Several artifact paths require sanitizing a human-readable string into a filesystem-safe identifier. The Debrief sanitization algorithm is applied in this exact order:

1. Convert to lowercase.
2. Replace spaces and hyphens with underscores.
3. Remove all characters not matching `[a-z0-9_]`.
4. Collapse consecutive underscores to a single underscore.
5. Strip leading and trailing underscores.
6. Truncate to `max_length` characters (caller-specified; default 40). If truncation lands in the middle of a word, truncate anyway — do not attempt word-boundary alignment.
7. If the result is empty after steps 1–5 (e.g., the input was entirely non-ASCII or special characters), use the fallback value `"untitled"`.

**Usage sites:**
- **Presentation folder naming** (this section): `<YYYY_MM_DD>_<sanitize(title, max_length=40)>`
- **Paper slug derivation** (REQ-CONSULT-17): `sanitize(filename_without_extension, max_length=50)`
- **Snapshot label sanitization** (REQ-SAVE-3): `sanitize(user_label, max_length=50)` (applied only when the user provides a custom label; default timestamp labels `YYYYMMDD_HHMMSS` bypass sanitization)

**Worked examples:**
- `"SVP Presentation"` → `svp_presentation`
- `"AI/ML Tools & Tricks 2024"` → `ai_ml_tools_tricks_2024`
- `"Über-résumé (draft #3)"` → `ber_r_sum_draft_3`
- `"--- ???"` → `untitled` (fallback)
- `"A Very Long Title That Exceeds Forty Characters Easily"` → `a_very_long_title_that_exceeds_forty_cha` (truncated at 40)

If the user indicates no separator is needed, skip steps 2 and 3 and do not
insert a separator (record `separator_position: null` in the presentation folder
record).

If the user cancels the export dialog at any point, no state changes are made.
No folder is created, no `presentations` entry is added, and the export is
abandoned. The consultant confirms cancellation.

If the user provides a folder name that already exists in `output/`, the export
module treats it as a re-export into the same presentation. The version counter
continues from the last version in that folder (e.g., if `deck_v002.pdf` exists,
the next is `deck_v003.pdf`). The `presentations` array entry for that folder is
updated in place (not duplicated).

After the dialog, the export skill creates the presentation folder
`output/<presentation_folder>/` if it does not exist, adds or updates the record
in the `presentations` array in `deck_state.json` (including writing the
`slide_manifest` snapshot of slug order at the time of export), and proceeds to
render.

**Separator generation:**

The separator slide is always generated fresh at export time. It is NOT a
user-authored slide and has no slide record in `deck_state.json`. It is not
written to `slides/`; it is rendered in-memory during the Playwright session
using the locked style config.

`separator_position` is a 0-based index into the `slides` array. The separator
is inserted BEFORE the slide at that index. If `separator_position` is 8, the
separator appears between `slides[7]` and `slides[8]`.

`closing_slide` (top-level field in `deck_state.json`) controls an auto-generated
closing slide appended after the last non-backup approved slide and before the
separator. When `closing_slide` is `"empty"`, the export module generates a styled
empty slide in-memory (background color from the locked style config, no content)
and adds it to the PDF buffer after the last main slide. When `closing_slide` is
`null`, no closing slide is generated. Like the separator, the closing slide is
not a user-authored slide, has no slide record, and is not written to `slides/`.

**PDF page order:**

The exported PDF has the following page order. This is the canonical sequence;
every component that reads deck order must produce this sequence:

```
1. Main slides       — approved slides with backup=false, in slides array order
2. Closing slide     — if closing_slide="empty": auto-generated styled empty slide
                       if closing_slide=null: omitted
3. Separator slide   — if separator_position is non-null: auto-generated separator
                       if separator_position is null: omitted
4. Backup slides     — approved slides with backup=true, in slides array order
```

The backup slides are always the final pages of the PDF. The presentation
ends with the last backup slide. If there are no backup slides, the
presentation ends with the separator (if present) or the closing slide
(if present) or the last main slide.

**PDF rendering procedure:**

The PDF export module must use a single Playwright browser session:

1. Open a Playwright browser context via `playwright-python` (import
   `playwright.sync_api`, call `sync_playwright().start()`, launch Chromium,
   and create a single `BrowserContext` in-process).
2. Build the page list from `deck_state.json`:
   a. Collect all approved slides with `backup: false` in array order → main slides.
   b. If `closing_slide` is `"empty"`, append a placeholder for the empty closing slide.
   c. If `separator_position` is non-null, append a placeholder for the separator.
   d. Collect all approved slides with `backup: true` in array order → backup slides.
3. For each entry in the page list:
   a. If the entry is a slide: navigate to `slides/<slug>.html` (using a `file://`
      URL), wait for page load (network idle or sentinel element), add to PDF buffer.
   b. If the entry is the empty closing slide: generate styled empty slide HTML
      in-memory (background from locked style config, no content), render and add
      to PDF buffer.
   c. If the entry is the separator: generate separator slide HTML in-memory using
      `separator_content` from the active presentation record, render and add to
      PDF buffer.
4. Write the complete multi-page PDF to
   `output/<presentation_folder>/deck_v{NNN}.pdf`. NNN is determined by counting
   existing PDFs in the target folder and incrementing by one, starting at 001.
5. Close the browser context.
6. Increment `export_count` in the presentation folder record in
   `deck_state.json`. *(Superseded by filesystem-derived versioning -- BUG-AUDIT-23)*

No external PDF merge tool is used. Playwright's native multi-page PDF support
handles the entire document in one pass.

If the style compiler fails (exit code 1) during export, the export module MUST abort and report the error. It MUST NOT fall back to the existing `assets/style.css` -- a compiler failure indicates the style config may be inconsistent with the CSS on disk. The failure is logged to `export_log.jsonl`.

If the export process fails after the `presentations` entry has been created but before the PDF is written, the empty folder and the `presentations` entry are left in place. Re-running `/debrief:export` with the same folder name re-exports into the existing folder (the version counter increments normally). No cleanup of partial state is performed.

#### 24.10.1 Playwright Binding

All Playwright usage in Debrief uses the `playwright-python` library, not the
Node.js package, not the Playwright CLI, and not an MCP server. The four
Playwright-using modules — `debrief.export`, `debrief.qa_checker`,
`debrief.preview_renderer`, and the HTML adapter inside `debrief.style_analyzer`
(Section 24.25.3) — all import Playwright in Python and manage browser contexts
in-process. Agents never invoke Playwright directly via tool use — they invoke
Python modules (`python -m debrief.qa_checker`, `python -m debrief.export`,
`python -m debrief.preview_renderer`, `python -m debrief.style_analyzer`)
which encapsulate the Playwright calls. `debrief.style_guide_generator` does
NOT use Playwright; it is a text-synthesis utility (REQ-STYLE-9). See
Section 24.10.2 for the per-module Playwright lifecycle contract.

#### 24.10.2 Playwright Lifecycle per Module

Each module that uses Playwright MUST open its own `sync_playwright()` context at the start of its work and close it before exiting. There is NO shared Playwright process, browser instance, or `BrowserContext` across modules.

**Module-by-module lifecycle:**

- **`debrief.export`** opens one `sync_playwright()` session, launches Chromium, creates one `BrowserContext`, renders the full deck page-by-page into a single multi-page PDF, closes the context, closes the browser, stops the session. Exactly one `BrowserContext` per export invocation.
- **`debrief.qa_checker`** opens one `sync_playwright()` session per invocation (i.e., per slide check), launches Chromium, creates one `BrowserContext`, renders the single slide, takes the screenshot, closes everything. Each QA check is a fresh Playwright session. QA checks are NOT batched across slides.
- **`debrief.preview_renderer`** opens one `sync_playwright()` session per invocation (once per style-dialog preview generation, once per `REGENERATE PREVIEWS` response), launches Chromium, creates one `BrowserContext`, renders each preview HTML in `.debrief/draft/preview_slides/` to a 1920×1080 PNG in `.debrief/draft/preview_images/`, waits for KaTeX/Mermaid/rough.js to finish rendering, closes everything. The preview renderer uses a single BrowserContext for the batch of 3 preview slides within one invocation (unlike the QA checker's per-slide isolation) because previews are transient diagnostic artifacts and cross-slide state leakage has no correctness impact on the locked style.
- **`debrief.style_analyzer` (HTML adapter only, Section 24.25.3)** opens one `sync_playwright()` session per HTML reference-import invocation, launches Chromium, creates one `BrowserContext`, renders each HTML reference page (single file or directory entries) to a 1920×1080 PNG under `assets/reference/slides/`, waits for `networkidle` + 2 seconds for client-side libraries, closes everything. PPTX and PDF modalities do NOT use Playwright (they use LibreOffice and PyMuPDF respectively).
- **`debrief.style_guide_generator`** does NOT use Playwright. It is a text-synthesis utility (REQ-STYLE-9) that reads bundled references, the reference-derived draft (if any), and the current draft `style_config.json`, and emits a draft `style_guide.md`. Earlier spec revisions listed this module as a Playwright user; that was a documentation leftover from a removed exemplar-screenshot pipeline.

**Prohibition:** Blueprint authors MUST NOT introduce a helper module (e.g., `debrief.playwright_helper`) that holds a long-lived browser context shared across modules. Each module's Playwright usage is hermetic. Sharing browser state across modules would:

1. Violate the "single BrowserContext per export" invariant (Section 22.4)
2. Introduce cross-invocation state leaks (cookies, caches, JavaScript globals)
3. Complicate error recovery (a crashed context in one module would corrupt another)

The ~500ms Playwright startup cost per invocation is an acceptable tradeoff for hermeticity.

### 24.11 Script Generator Module

The presenter script is generated by the Python module `debrief.script_generator`
(located at `src/debrief/script_generator.py` in the plugin). The `/debrief:script`
skill invokes it directly via Bash — no agent is needed for script generation.

The module:

1. Reads `deck_brief.md` and `deck_state.json` from the current project directory.
2. Identifies the most recent presentation folder by reading the last entry in
   the `presentations` array of `deck_state.json`. If the array is empty, the
   module exits with a non-zero code and an error message: "No export has been
   done yet. Run /debrief:export first."
3. Produces a versioned presenter script at
   `output/<presentation_folder>/script_vNNN.md`. NNN is determined by counting
   existing script files in the target folder and incrementing by one, starting
   at 001.
4. Increments `script_count` in the presentation folder record in
   `deck_state.json` after writing. *(Superseded by filesystem-derived versioning -- BUG-AUDIT-25)*

Invocation from the skill's Bash call:

```bash
python -m debrief.script_generator
```

The skill does not invoke an agent. It calls the module, checks the exit code,
and reports success or failure to the user.

### 24.12 View Module

The view is generated by the Python module `debrief.view` (located
at `src/debrief/view.py` in the plugin). The `/debrief:view` skill
invokes it via Bash:

```bash
python -m debrief.view [query]
```

The module:

1. Reads `deck_state.json` from the current project directory for the slide list,
   their order, and group membership (`group_id` fields).
2. Parses the query argument to determine which slides to include (see REQ-VIEW-1
   for supported query forms). Resolves `current` and `previous` using `group_id`
   fields and `debrief_state.json`.
3. For each requested slide, reads the screenshot from `output/screenshots/<slug>.png`.
4. Produces `output/view.html` as a self-contained HTML file with inline
   CSS that tiles selected slides in the requested order. Each thumbnail card MUST include the slide slug as a visible label (small monospace font, e.g., `intro`, `methodology`, `results-01`) positioned below the screenshot. This allows the user to identify slides by slug when requesting modifications (e.g., `GROUP REVISE methodology` or `DETAIL FIX results-01`). If a single slide is
   requested, the view shows it at full size instead of as a thumbnail.
5. Opens the generated HTML file in the default browser.
6. Uses no external dependencies beyond the Python standard library. All CSS is
   inlined in the output file.

The output file is overwritten on each invocation. It is ephemeral and is deleted
by `/debrief:restore`'s orphan-slide sweep if the view's slides are no longer in the restored state. *(BUG-AUDIT-22: `/debrief:restore` does not delete `output/` wholesale; only orphan slides are swept.)*

### 24.13 Re-Presentation Workflow

A project directory may be used more than once to deliver the same content to
different audiences or at different times. Each re-presentation creates a new
dated folder inside `output/` and does not disturb any prior export folder.

**Canonical re-presentation flow:**

1. The user navigates to the existing project directory and runs `debrief` (the
   resume flow). The consultant agent loads context from `deck_brief.md` and
   `deck_state.json`.
2. The consultant reviews the existing deck with the user, identifying which
   slides need to be updated for the new audience (e.g., updating the title
   page, adding or removing slides, adjusting emphasis).
3. The user invokes `/debrief:slide [slug]` for each slide that needs revision,
   following the standard authoring loop.
4. When the deck is ready, the user invokes `/debrief:export`. The export
   ordering dialog proposes a new folder name using today's date and the current
   deck brief title (e.g., `2027_03_15_SVP_updated`). The user confirms or
   overrides.
5. The export module creates `output/2027_03_15_SVP_updated/` and writes
   `deck_v001.pdf` into it. The previous folder (`output/2026_04_30_SVP_presentation/`)
   is completely untouched.
6. The user now has both presentation versions available as independent,
   self-contained folders.

**Invariants for re-presentation:**

- Old presentation folders are NEVER modified by a new export. Each export
  creates a new folder.
- The `presentations` array in `deck_state.json` accumulates one record per
  export folder, preserving the full history of all presentations made from this
  project.
- `separator_position` and `separator_content` are per-presentation. The user
  may choose a different split point for a different audience.
- The version counter (NNN) resets to 001 in each new folder. Versions within
  a folder (e.g., `deck_v001.pdf`, `deck_v002.pdf`) represent iterations of
  the same presentation, not different presentations.
- During the re-presentation review, the consultant updates `deck_brief.md` to
  reflect the new audience context and any changes to the narrative direction.
  A new ledger entry is created for the re-presentation review session.
- Discarded slides cannot be resurrected. If the user wants to recreate a slide
  that was previously discarded, the consultant treats it as a new slide with a
  new slug. The discarded record remains in `deck_state.json` for audit purposes.

### 24.14 Style Compiler Module

The style compiler is implemented as the Python module `debrief.style_compiler`
(located at `src/debrief/style_compiler.py` in the plugin).

**Invocation:**

The `/debrief:style` skill invokes `python -m debrief.style_compiler` via Bash
after the user approves the style config:

```bash
python -m debrief.style_compiler style_config.json assets/style.css
```

The first argument is the path to `style_config.json`; the second argument is
the output path `assets/style.css`.

The `/debrief:export` skill also invokes the style compiler before PDF rendering
(via the export module — see Section 24.10) to ensure `assets/style.css` is up
to date with the current style config.

**Behavior:**

1. Reads `style_config.json` from the path given as the first argument.
2. Generates CSS custom properties (variables) for all visual properties defined
   in the config (colors, fonts, spacing, layout grammar, etc.).
3. Writes the resulting CSS to the output path given as the second argument
   (`assets/style.css`).

**Constraints:**

- The style compiler does NOT modify `style_config.json`. It is a pure reader.
- Exit code: 0 on success, 1 on error (invalid JSON, missing required fields).
- Errors are printed to stderr.

**Style guide generation** is performed by the style skill (not the compiler module). The style compiler remains a pure `style_config.json` to `assets/style.css` transformer. The style guide is authored by the style agent during the style dialog, capturing the design reasoning that informed the config values. The style guide references the CSS custom properties by name (e.g., "use `--color-accent` sparingly for callout borders and inline highlights").

### 24.15 Routing Script (`debrief.routing`)

A deterministic Python script (analogous to SVP's `routing.py`) that reads `debrief_state.json` and outputs a structured action block.

**Invocation:**
```bash
python -m debrief.routing --project-root .
```

**Output:** JSON action block to stdout.

**Action Block Schema:**
```json
{
  "action_type": "invoke_agent | human_gate | machine_gate | run_command | pipeline_complete",
  "agent": "consultant | slide_maker | stylist | qa | diagnostic",
  "gate_id": "G3.3_slide_review",
  "valid_responses": ["SLIDE APPROVED", "SLIDE REVISE"],
  "gate_prompt": "The slide has passed QA. Review it and decide.\n  SLIDE APPROVED -> Accept this slide and move to the next one\n  SLIDE REVISE   -> Send this slide back for revision\nBefore deciding:\n  /debrief:view <slug>  to preview this slide full-size in the browser\n  /debrief:quit         to save and exit",
  "context_files": ["deck_brief.md", "deck_state.json", "style_guide.md"],
  "task_prompt_file": ".debrief/task_prompt.md",
  "prepare": "python -m debrief.prepare --action G3.3_slide_review --project-root .",
  "post": "python -m debrief.update_state --gate G3.3_slide_review --project-root .",
  "reminder": "Review slide 'methodology' after QA passed."
}
```

| Field | Description |
|-------|-------------|
| `action_type` | What the orchestrator should do |
| `agent` | Which agent to invoke (for `invoke_agent`). **Note:** this enum is the **invocation target** and includes `diagnostic` as a valid value because the routing script emits `invoke_agent` targeting the bug-diagnostic agent when `sub_phase == production/diagnostic` (per Section 24.18). This is a **different enum** from `active_agent` in `debrief_state.json` (Section 17.5), which is the **current conversational agent** and does NOT include `diagnostic` — during the diagnostic sub_phase, `active_agent` is `none` (per P-BP-3). Do not reuse the `active_agent` enum for this field. |
| `gate_id` | Gate identifier (for `human_gate` / `machine_gate`) |
| `valid_responses` | Allowed responses for this gate |
| `gate_prompt` | The gate prompt text to display to the user (for `human_gate` only). Assembled by the `prepare` script from the canonical text in Section 14.16.1. See REQ-ROUTE-9. |
| `context_files` | Files the orchestrator should read before this action (for context scoping) |
| `task_prompt_file` | Path to the assembled task prompt (written by `prepare`) |
| `prepare` | Command to run before the action (assembles context) |
| `post` | Command to run after the action (updates state) |
| `reminder` | Human-readable description of what this action is |

### 24.16 `style_config.json` Schema Additions

The `style_config.json` schema includes a `constraints` object with the following fields:

```json
{
  "constraints": {
    "permitted_diagram_types": ["mermaid", "inline-svg"],
    "math_renderer": "katex"
  }
}
```

The `math_renderer` field records which math rendering backend is in use for this project. This is informational — the Slide Maker and QA agent read it to know how math is rendered, but do not select the renderer themselves. The value is set at project initialization based on the blueprint's chosen implementation.

**Provenance tracking** (REQ-STYLE-7). The `style_config.json` schema also includes a top-level `provenance` object that records the source of each resolved style decision so downstream QA can explain every choice. The object is keyed by style-config field path (dot-notation for nested fields) and the value is one of: `user_dialog`, `reference_baseline`, `reference_inspiration`, `bundled_reference`, `default`, plus an optional `override_note` field when the user overrode a bundled-reference veto rule during the style dialog's conflict-disclosure step.

```json
{
  "provenance": {
    "colors.primary": {"source": "reference_baseline"},
    "colors.accent": {"source": "user_dialog"},
    "typography.heading_font": {"source": "bundled_reference"},
    "data_viz.colormap": {
      "source": "reference_baseline",
      "override_note": "User chose KEEP IMPORTED at conflict disclosure: PPTX uses jet colormap, bundled references recommend viridis. Veto rule VETO-palette-jet suppressed for this project."
    },
    "layout.grammar": {"source": "default"}
  }
}
```

The Stylist writes `provenance` when it synthesizes `style_config.json`. The visual QA agent reads `provenance` to understand why a style choice was made (e.g., to explain a suppressed veto rule in its output). Blueprint authors MUST include the `provenance` field in the `style_config.json` schema.

### 24.16.1 `style_config.json` top-level schema enumeration

This section enumerates the seven required top-level keys of `style_config.json` and the canonical CSS dot-paths for the five visual keys. The single source of truth for both is `src/debrief/style_engine.py`: the constants `_REQUIRED_KEYS` (the seven keys) and `CSS_PROPERTY_MAP` (the twenty-six canonical dot-path → CSS custom-property names). Any divergence between this section and those constants is a blocking bug.

**Seven required top-level keys.** Every `style_config.json` MUST contain, at the top level, the keys `colors`, `typography`, `spacing`, `layout`, `data_viz`, `constraints`, and `provenance`. `parse_style_config` (Unit 6) raises `ValueError: Missing required key: <name>` on the first absent key and the style compiler exits with code 1 (BC-6.8). The first five are visual-property groups that the compiler flattens into CSS custom properties; the last two are structural metadata (BC-6.4) that the compiler excludes from CSS output but the QA agent and downstream tools read.

**Canonical CSS dot-paths (twenty-six).** The visual keys contain the following leaf fields. Each leaf MUST map to a CSS custom property per `CSS_PROPERTY_MAP`; a config that omits any of these leaves still parses but produces an incomplete `:root { ... }` block that fails downstream rendering expectations.

```
colors.primary              -> --color-primary
colors.secondary            -> --color-secondary
colors.accent               -> --color-accent
colors.background           -> --color-background
colors.text_primary         -> --color-text-primary
colors.text_secondary       -> --color-text-secondary
colors.code_background      -> --color-code-background
colors.border               -> --color-border
typography.heading_font_family  -> --font-heading-family
typography.body_font_family     -> --font-body-family
typography.code_font_family     -> --font-code-family
typography.heading_size_base    -> --font-heading-size-base
typography.body_size_base       -> --font-body-size-base
typography.heading_weight       -> --font-heading-weight
typography.body_weight          -> --font-body-weight
typography.line_height          -> --font-line-height
spacing.margin_pct          -> --spacing-margin-pct
spacing.gap                 -> --spacing-gap
spacing.section_gap         -> --spacing-section-gap
layout.slide_width          -> --layout-slide-width
layout.slide_height         -> --layout-slide-height
layout.column_gap           -> --layout-column-gap
data_viz.primary_colormap   -> --viz-primary-colormap
data_viz.axis_color         -> --viz-axis-color
data_viz.grid_color         -> --viz-grid-color
data_viz.annotation_color   -> --viz-annotation-color
```

**Structural keys.** `constraints` MUST contain `permitted_diagram_types` (non-empty list drawn from §24.16) and MAY contain `math_renderer`. `provenance` MUST be a mapping from dot-path strings to provenance objects whose `source` field is one of the values in §24.16. A config with an empty `provenance` object parses but carries no source attribution; the Stylist SHOULD write at least a `default` entry during dialog-driven synthesis.

**Template.** The plugin ships a canonical starting template at `${CLAUDE_PLUGIN_ROOT}/templates/style_config.json` containing all seven keys and all twenty-six dot-paths populated with sensible defaults. The Stylist MUST load this template and fill in values through the dialog, not reconstruct the schema from memory. BC-6.11 enforces that the template satisfies `parse_style_config` and contains every dot-path in `CSS_PROPERTY_MAP`. See BUG-AUDIT-13 for the failure mode this template is designed to prevent.

### 24.17 Defensive JSON Parsing

**Defensive JSON Parsing:** All modules that parse LLM-generated JSON output (QA agent results, slide briefs, ledger entries, `.debrief/gate_data.json`, `.debrief/approval_*.json`) SHOULD use the `json-repair` library as a safety net for common LLM output errors (trailing commas, unescaped quotes, truncated output). `json-repair` is guaranteed by the `debrief` conda env via `environment.yml`. Modules use it freely — no availability check is needed under normal operation. If `json_repair` cannot be imported at module load time, this indicates conda env corruption and the module reports the standardized env-corruption error per Section 9.3.1.

### 24.18 Red-Green Cycle Orchestration

Each red-green iteration is one full dispatch cycle. The consultant reads `debrief_state.json`, sees `sub_phase: 'red_green'`, and reads the latest `qa_log.jsonl` entry for `current_slide_slug`. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*

**First iteration (no prior QA entry):** The consultant invokes the Slide Maker with the task prompt containing the slide brief, style guide, and no QA feedback (first attempt). The Slide Maker writes `slides/<slug>.html`. The PostToolUse hook fires the QA agent synchronously, which writes to `qa_log.jsonl` before the hook returns. The Slide Maker agent's invocation completes. *(BUG-AUDIT-31: the consultant handles all dispatch via Tool calls.)*

**Subsequent iterations:** The consultant reads the latest `qa_log.jsonl` entry. Three outcomes: *(BUG-AUDIT-31: the consultant handles all dispatch via Tool calls.)*

1. **GREEN** (`passed: true`, no veto): `update_state` transitions to `production/slide_review`. G3.3_slide_review is presented. The Slide Maker has already written `.debrief/approval_<slug>.json` (per REQ-SLIDE-4); it sits on disk waiting for `SLIDE APPROVED`. Note: the Slide Maker writes this file at the end of **every** red-green iteration, not just GREEN ones — the file always reflects the current best-known-good state (Section 24.24). On GREEN, it reflects the just-completed iteration. On RED followed by EXHAUSTED or oscillation revert, it reflects whichever iteration had the lowest failure count, so the file is guaranteed to exist for both G3.3 variants.
2. **RED, iteration < 5**: `red_green_iteration` is incremented, the snapshot + regression check per REQ-SLIDE-14 is invoked. If not reverted, the consultant re-invokes the Slide Maker with context that includes the latest qa_log entry's `revision_instructions`. The Slide Maker rewrites, hook fires QA, the consultant reads the new result. *(BUG-AUDIT-31: the consultant handles all dispatch via Tool calls.)*
3. **EXHAUSTED** (iteration >= 5): `sub_phase` transitions to `production/diagnostic` and `pending_gate` is set to null. The consultant invokes the bug-diagnostic agent (recorded as `DIAGNOSTIC_REQUESTED` in the Dispatch Event Table, Section 13.1). The diagnostic agent reads `qa_log.jsonl`, `output/qa_cycle_log.jsonl`, and the current `slides/<slug>.html`; writes its report to `.debrief/diagnostic_<slug>.md`; and transitions `sub_phase` to `production/slide_review` with `pending_gate: G3.3_slide_review_post_diagnostic`. The consultant then presents the post-diagnostic variant gate (see Section 14.16). *(BUG-AUDIT-31: the consultant handles all dispatch via Tool calls.)*

*(BUG-AUDIT-31: The following paragraph described the `update_state`/routing-cycle split rationale. The entire routing loop is dead at runtime -- the consultant handles all dispatch via Tool calls.)* The split between "state transition" and "agent invocation" is intentional in the original design. `update_state` was a Python CLI script running from the POST step of the six-step action cycle; it could only modify state files. All agent invocations flowed through `invoke_agent` action blocks emitted by `debrief.routing` at the top of the next cycle.

**QA dispatch mechanism — hybrid command hook + slide-maker Task call (BUG-AUDIT-17).** The sentence in prior revisions of this section that said *"the hook is synchronous within the Slide Maker's write action"* referred specifically to a `type: "agent"` PostToolUse hook that fired the visual-QA agent after every `Write|Edit` matching slide HTML. Claude Code v2.1.107 broke that mechanism upstream with an internal assertion error *"Messages are required for agent hooks. This is a bug."* (see BUG-AUDIT-12b). The hook was left in place with a README note until BUG-AUDIT-17, at which point the entire dispatch mechanism was replaced with a hybrid architecture:

- **Tier 1 (programmatic, automatic).** A `type: "command"` PostToolUse hook on `Write|Edit` matching `slides/*.html` invokes `${CLAUDE_PLUGIN_ROOT}/bin/qa-run-on-write`, a Python wrapper that reads the hook input JSON from stdin, extracts `tool_input.file_path`, and — if and only if the path matches `slides/*.html` — shells out to `python -m debrief.qa_checker --slide-path <path> --screenshot-path output/screenshots/<slug>.png --project-root <cwd>`. The subprocess renders the slide via Playwright, takes a screenshot, runs the Tier 1 programmatic invariants (INV-04, INV-06, INV-07, INV-08, INV-10 per §24.22), and appends a Tier 1 entry to `output/qa_log.jsonl`. This tier is **fully deterministic**: the Claude Code hook runtime fires the command synchronously, no LLM is involved, no agent discretion is possible. See BC-1.4 (amended).

- **Tier 2 (VLM, slide-maker-dispatched).** The slide-maker agent MUST, as its absolute final action before returning from its turn, invoke the visual-qa agent via the `Task` tool. The slide-maker's frontmatter includes `Task` in its tools list, and its system prompt contains a load-bearing `## QA Dispatch (REQUIRED)` section instructing the agent to spawn visual-qa with the current slug, the slide HTML path, and the screenshot path (which the Tier 1 hook has just produced). Visual-qa reads the latest Tier 1 entry for the slug from `qa_log.jsonl`, runs its Tier 2 + veto checks (VETO-01..07 plus INV-01/02/03/05/09/11/18/21 per §24.22), and appends a merged `tier: "2_merged"` entry. This tier is **LLM-driven**: the dispatch is prompt-level enforced, which is the strongest guarantee achievable given that only an agent with the `Task` tool can spawn a subagent and only via its LLM-controlled turn. See BC-8.4 (new).

- **Red-green decision.** *(BUG-AUDIT-31: the routing loop is dead; the consultant handles this check directly.)* The read of `qa_log.jsonl` uses the same logic as before -- `latest entry passed=True` -> GREEN, `latest entry passed=False` and iter<5 -> RED, iter>=5 -> EXHAUSTED. If the latest entry is a `tier: "2_merged"` entry (the normal path), its result is used directly. If the latest entry is a `tier: 1` entry (the slide-maker returned without invoking visual-qa — a BC-8.4 contract violation), the consultant SHOULD flag the missing Tier 2 and re-dispatch, but the Tier 1 result provides a graceful-degradation floor. The graceful-degradation path is a safety net, not a design target; BC-8.4 is the primary guarantee.

Prior to BUG-AUDIT-17 this section described a single-mechanism dispatch (the `type: "agent"` PostToolUse hook). The mechanism has been split into Tier 1 (command hook, fully deterministic) and Tier 2 (slide-maker Task call, prompt-level deterministic). The plugin no longer uses any `type: "agent"` hooks anywhere in `hooks.json`, so the v2.1.107 upstream regression is no longer relevant to debrief regardless of whether it is ever fixed upstream. See BUG-AUDIT-12b (superseded by BUG-AUDIT-17) and BUG-AUDIT-17 (the canonical write-up).

**No polling, no Bash loops, no skill orchestration.** The consultant is the orchestrator. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)* Each iteration is one dispatch cycle. The Slide Maker agent runs exactly once per iteration and exits. Tier 1 fires synchronously within the Slide Maker's write action (via the command hook); Tier 2 fires as the Slide Maker's absolute final action (via the `Task` call) before the Slide Maker returns.

### 24.19 Skill vs. Routing Responsibility Boundary

Skills are invocation triggers, not orchestrators. Every skill either (a) sets state fields and yields to the consultant, or (b) runs a specific utility and returns without touching routing. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)* The table below enumerates the boundary for every skill:

| Skill | Mode | State writes before yielding | Run-and-return? |
|-------|------|-----------------------------|-----------------|
| `/debrief:slide [slug]` | Yield | `current_slide_slug: <slug or null>` | No |
| `/debrief:style` | Yield | `pending_gate: null`, `active_agent: 'stylist'`, `sub_phase: 'style_dialog'` (only if not already in Phase 2) | No |
| `/debrief:export` | Yield | `pending_gate: G4.1` (only if not already at G4.1+) | No |
| `/debrief:view [query]` (Phase 3) | Yield | Set `pre_view_state` (compound object), set `pending_gate: G3.V_view_dispatch`. Preconditions: at least one slide exists in `slides/` per REQ-VIEW-3. | No |
| `/debrief:view [query]` (Phase 4 / complete) | Run-and-return | Open read-only browser view of the approved deck. Do NOT set `pre_view_state` or `pending_gate`. No G3.V dispatch (Phase 4 is read-only per REQ-VIEW-6; the skill returns after the user closes the browser). Distinct from G4.4 `REVIEW FIRST`, which is triggered by a gate response and uses the `finalization/reviewing_for_export` sub_phase per Section 14.17. | No |
| `/debrief:save [label]` | Run-and-return | None | Yes — writes snapshot, prints confirmation, returns to current state |
| `/debrief:restore` | Run-and-return | Overwrites `deck_state.json` from snapshot, sweeps orphan slides | Yes — restores snapshot, prints confirmation, returns to current state *(BUG-AUDIT-22: no longer terminates session or deletes state files)* |
| `/debrief:quit` | Terminate | Flushes pending state; does not set new fields | N/A — exits session |
| `/debrief:script` | Run-and-return | None | Yes — writes script, prints confirmation, returns to current state |
| `/debrief:handout [2up\|4up]` | Run-and-return | None | Yes — writes handout, prints confirmation, returns to current state |

**Yield** means: the skill validates preconditions, updates `debrief_state.json` with the listed fields, then returns. The consultant reads the new state and handles the appropriate dispatch. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*

**Run-and-return** means: the skill validates preconditions, performs its utility (writing a file, generating output), prints a confirmation, and returns without modifying `debrief_state.json`. If a human gate is pending, it remains pending and is re-presented after the skill completes.

**Terminate** means: the skill exits the Claude Code session. The user must re-run `debrief` to resume (or `debrief new` to start a fresh project). *(BUG-AUDIT-22: only `/debrief:quit` is Terminate; `/debrief:restore` is now Run-and-return.)*

Skills never directly invoke agents, never poll state files in loops, and never manage iteration counters. These responsibilities belong to the consultant. *(BUG-AUDIT-31: the routing script and `update_state` script are dead; the consultant handles all dispatch via Tool calls.)*

**Yield protocol.** A Yield-mode skill's SKILL.md instruction body MUST end with the following steps:

1. Validate preconditions (per the skill's REQ). If any fail, print the error message to the chat and stop (do not yield).
2. Write the listed state fields via `python -m debrief.update_state --skill-prelude <skill_name> --field <name>=<value> [...]`. This is the exception mechanism from Section 24.33.
3. Print a one-line acknowledgment to the user (e.g., `Style dialog starting...`, `Opening view...`).
4. Run `python -m debrief.routing --project-root .` as the next Bash action to produce the next action block.
5. Execute the returned action block according to the standard six-step cycle.

The skill explicitly drives exactly ONE dispatch cycle after state update. The consultant picks up from there. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*

**Alternative (if the harness supports it):** If Claude Code's skill lifecycle guarantees that a user turn always ends in a cycle boundary where `CLAUDE.md` instructions re-run routing, the skill MAY omit step 4 and rely on the implicit next-cycle re-routing. Blueprint authors MUST verify this against the installed harness version and document the choice.

### 24.20 Prepare Module Contract

> **NOTE (BUG-AUDIT-31):** The functions described in this section were deleted in BUG-AUDIT-31. All routing, update_state, and prepare functions are dead at runtime -- the consultant agent handles all dispatch via Tool calls. This section is retained for historical reference only.

The `debrief.prepare` module assembles task prompts for agent invocations and gate presentations. CLI: `python -m debrief.prepare --action <gate_or_state_id> --project-root <path>`. Output: writes `.debrief/task_prompt.md`. The module reads `debrief_state.json` to determine which context files to assemble. For agent invocations, the context scoping is defined in Section 22.8. For human gate presentations, the per-gate file list is defined in Section 22.8.1. The task prompt format is markdown with `## Context: <filename>` sections containing the file contents. For QA revision context, the prepare module extracts the latest `qa_log.jsonl` entry and embeds it under `## QA Result`. The Slide Maker reads only the task prompt, not raw state files.

**Cross-cycle gate_data consumption.** When `.debrief/gate_data.json` is present AND its `gate_id` field matches the gate whose response triggered the current `sub_phase` transition (i.e., the gate whose response just caused the prior cycle's `update_state` to run), the prepare module MUST (a) read the file, (b) inject the `data` object into the agent's task prompt under a clearly-labeled `## Gate Data` section, and (c) delete the file after successful injection. This rule supersedes the per-agent context lists in Section 22.8 for the case of cross-cycle gate_data payloads. Same-invocation gate_data consumers (G3.4 `GROUP REVISE`, G3.V `DETAIL FIX`) do NOT trigger this rule because `update_state` has already deleted the file in its own invocation before the next routing cycle begins. Cross-cycle consumers include: G2.1 `STYLE REVISE` (`style_revise_feedback` → Stylist prepare context), G2.1 `REGENERATE PREVIEWS` (`regenerate_previews: true` → Stylist prepare context), G3.3_slide_review_post_diagnostic `SLIDE REVISE` (`slide_revise_instructions` → Slide Maker prepare context).

**Stylist schema injection.** For any action that invokes the Stylist agent (currently `style/style_dialog` and `style/style_lock` per the routing table in §17.3), `main_prepare` MUST inject the full contents of `${CLAUDE_PLUGIN_ROOT}/templates/style_config.json` into the task prompt as a `## Schema Starting Point` section containing a JSON fenced code block. The section MUST be **prepended** to the task prompt so it appears before any other context and the stylist's first user-message turn begins with a compiler-valid schema instance already visible. The section's explanatory paragraph MUST cite §24.16.1 (the canonical schema enumeration) and BC-6.11 (the template-validity contract) so future maintainers can trace the schema back to the single source of truth. Failure to resolve the template file is a hard error: `main_prepare` exits with code 1 and a diagnostic message citing BUG-AUDIT-14. The resolution strategy tries `${CLAUDE_PLUGIN_ROOT}/templates/style_config.json` first and MAY fall back to a path relative to `routing.py`'s source location for test and offline contexts. This injection rule exists as belt-and-suspenders over the system-prompt guidance in `agents/stylist.md` (added by BUG-AUDIT-13), closing the failure mode where an agent that ignores the "load the template" instruction reconstructs a compiler-incompatible schema from memory. BC-4.7b enforces every part of this rule; a regression test at `tests/regressions/test_bug_audit_14_prepare_injects_stylist_template.py` parses the injected JSON and passes it through `style_engine.parse_style_config` so any drift between the injected bytes and the compiler's expectations is caught at test time.

### 24.21 update_state Module Contract

> **NOTE (BUG-AUDIT-31):** The functions described in this section were deleted in BUG-AUDIT-31. All routing, update_state, and prepare functions are dead at runtime -- the consultant agent handles all dispatch via Tool calls. This section is retained for historical reference only.

CLI: `python -m debrief.update_state --gate <gate_id> --response <response_text> --project-root <path>`. The gate response is passed as a CLI argument. The module validates the response against the gate's `valid_responses` (REQ-ROUTE-7). For the red-green cycle, `update_state` manages `red_green_iteration`, snapshot creation (REQ-SLIDE-14), and regression detection.

**Two-file split for gate-adjacent data.** Gates that need data beyond the response text use one of two files in `.debrief/`, never both for the same gate:

1. **`.debrief/approval_<slug>.json`** — carries the Slide Maker's approval payload for one specific slug. Written by the Slide Maker at the end of **every** red-green iteration (not just GREEN — per REQ-SLIDE-4, the file always reflects the current best-known-good state so that `SLIDE APPROVED` remains a valid response even on the post-diagnostic variant of G3.3). The write happens before the PostToolUse hook returns. Consumed by `update_state` on `G3.3_slide_review` `SLIDE APPROVED` and on `G3.3_slide_review_post_diagnostic` `SLIDE APPROVED`. Deleted by `update_state` after successful merge into `deck_state.json`. See Section 24.24 for the schema.

2. **`.debrief/gate_data.json`** — carries user-supplied parameters parsed out of a parameterized gate response. Written by `update_state` itself as it parses the user's response. The orchestrator and agents do NOT write this file. The file has two consumption modes:

   - **Same-invocation consumers** (G3.4 `GROUP REVISE`, G3.V `DETAIL FIX`): `update_state` reads the file, applies the payload directly to `debrief_state.json`, and deletes the file before its own invocation returns.
   - **Cross-cycle consumers** (G2.1 `STYLE REVISE`, G2.1 `REGENERATE PREVIEWS`, G3.3_slide_review_post_diagnostic `SLIDE REVISE`, G3.2a `MY INSTRUCTIONS`): `update_state` writes the file and leaves it in place. On the next routing cycle, the prepare step detects the file, validates `gate_id` against the current pending gate, injects the `data` payload into the agent's task prompt, and deletes the file. See Section 24.20 for the global prepare-module rule.

   In both modes the file is strictly short-lived: it never persists beyond the routing cycle immediately following the gate response that produced it.

**Gate data usage by gate:**

- **G1.3 `<numbers>` or `ALL`:** `update_state` parses the response and writes `selected_figures` directly to `debrief_state.json` (durable field per Section 17.5, not ephemeral gate_data). No gate_data.json is produced for this gate. Consumed by the Consultant's group_planning prepare context (Section 22.8, conditional load) when the first slide group is planned — this may be many routing cycles after G1.3 fires, so durable state is required.
- **G2.1 `STYLE APPROVED`:** no gate_data.json. `update_state` validates that `.debrief/draft/style_config.json` and `.debrief/draft/style_guide.md` exist, atomically promotes them to the project root, invokes the style compiler, sets `style_locked: true`, and removes `.debrief/draft/` recursively (see Section 24.8 for the full sequence).
- **G2.1 `STYLE REVISE <feedback>`:** `update_state` parses the feedback text, writes `.debrief/gate_data.json` with `{"gate_id": "G2.1_style_config_review", "data": {"style_revise_feedback": "<feedback>"}}`, removes `.debrief/draft/` recursively (draft discarded), and re-invokes the Stylist with the feedback in prepare context.
- **G2.1 `REGENERATE PREVIEWS`:** `update_state` writes `.debrief/gate_data.json` with `{"gate_id": "G2.1_style_config_review", "data": {"regenerate_previews": true}}`. It retains `.debrief/draft/style_config.json`, `.debrief/draft/style_guide.md`, `.debrief/draft/derived_style_guide.md`, and `.debrief/draft/preview_style.css`; removes `.debrief/draft/preview_slides/` and `.debrief/draft/preview_images/`; and transitions sub_phase to `style/style_dialog`. The next prepare cycle reads the gate_data flag and re-invokes the Stylist in preview-regeneration mode (REQ-STYLE-10 step 7) so it re-runs REQ-STYLE-10 steps 2-4 without re-synthesizing the style config or style guide. See Section 24.8 for the full flow.
- **G3.3_slide_review `SLIDE APPROVED`:** no gate_data.json. `update_state` reads `.debrief/approval_<slug>.json` (written earlier by the Slide Maker) and merges it into the slide record.
- **G3.3_slide_review_post_diagnostic `SLIDE APPROVED`:** same as above — reads the existing `.debrief/approval_<slug>.json`.
- **G3.3_slide_review_post_diagnostic `SLIDE REVISE: <instructions>`:** `update_state` parses the instructions, writes `.debrief/gate_data.json` with `{"gate_id": "G3.3_slide_review_post_diagnostic", "data": {"slide_revise_instructions": "<instructions>"}}`. Consumed by the next prepare step when re-entering `production/red_green`.
- **G3.4 `GROUP REVISE <slug>`:** `update_state` parses the slug, writes `.debrief/gate_data.json` with `{"gate_id": "G3.4_group_review", "data": {"group_revise_slug": "<slug>"}}`. Consumed by `update_state` itself to set `group_revise_slug` in `debrief_state.json`.
- **G3.V `DETAIL FIX <slug>`:** `update_state` parses the slug, writes `.debrief/gate_data.json` with `{"gate_id": "G3.V_view_dispatch", "data": {"detail_fix_slug": "<slug>"}}`. Consumed by `update_state` itself to set `current_slide_slug` in `debrief_state.json`.
- **G3.6 `END AS-IS`, `ADD CLOSING SLIDE`, `ADD EMPTY CLOSING SLIDE`:** no gate data.
- **G4.4 `EXPORT NOW`:** no gate data; the export ordering dialog writes directly to the presentation record before G4.4 fires.
- **G3.2a `MY INSTRUCTIONS`:** `update_state` prompts the user for revision instructions (inline skill prompt per Section 24.30), writes `.debrief/gate_data.json` with `{"gate_id": "G3.2a_oscillation_review", "data": {"my_instructions": "<user_text>"}}`, resets `red_green_iteration` to 0, transitions to `production/red_green`. Cross-cycle consumer: the next prepare step reads and deletes the file, injecting the user's instructions into the Slide Maker's task prompt as a `## User Instructions` section.
- **All other gates:** no gate_data.json, no approval_<slug>.json.

**`.debrief/gate_data.json` file format:**

```json
{
  "gate_id": "<id>",
  "data": { ...gate-specific fields... }
}
```

When `update_state` reads `.debrief/gate_data.json`, it validates `gate_id` matches the current pending gate. If the file is present but `gate_id` mismatches, `update_state` exits with code 4 (state corruption). For same-invocation consumers (G3.4, G3.V), `update_state` deletes the file after applying its payload. For cross-cycle consumers (G2.1 `STYLE REVISE`, G2.1 `REGENERATE PREVIEWS`, G3.3 post-diagnostic `SLIDE REVISE`), `update_state` leaves the file in place so the next prepare cycle can read it; the prepare cycle is responsible for deletion after use (Section 24.20).

When `update_state` reads `.debrief/approval_<slug>.json`, it validates the file's `slug` field matches `current_slide_slug` and that required fields are present (per Section 24.24). A missing file at `G3.3 SLIDE APPROVED` time indicates Slide Maker failed to produce its approval payload — `update_state` exits with code 4 (state corruption).

### 24.22 QA Checker Architecture

**Allocation.** `qa_checker.py` performs programmatic HTML/DOM analysis. The QA agent (VLM-capable) performs visual analysis of the screenshot.

- **`qa_checker.py` (programmatic, Tier 1):** INV-04 (contrast), INV-06 (no inline styles), INV-07 (no external requests), INV-08 (aspect ratio), INV-10 (permitted libraries — reads `style_config.json` from project root at check time), INV-12 (valid HTML5), INV-13 (image overflow), INV-14 (math horizontal overflow), INV-15 (diagram render errors), INV-16 (font loading), INV-17 (CSS property completeness), INV-19 (image `src` existence), INV-20 (image aspect-ratio distortion, 2% threshold), INV-22 (inline math line-height break), INV-23 (math asset file existence).
- **QA agent (VLM, vetoes + Tier 1 visual + Tier 2):** all VETO rules (VETO-01..VETO-07), INV-21 (rendered math visible — the one Tier 1 invariant assigned to the VLM because the signal is primarily visual), INV-01 (one idea), INV-02 (font sizes), INV-03 (line length), INV-05 (margins), INV-09 (bullet count), INV-11 (no speaker notes), INV-18 (symmetry).

The QA agent merges both result sets into the final `qa_log.jsonl` entry.

**Pipeline order (post-BUG-AUDIT-17).** The two tiers now run in reverse order of the prior revisions of this section. **Tier 1 runs first**, automatically, via the `type: "command"` PostToolUse hook (`bin/qa-run-on-write`) that fires synchronously on every slide Write/Edit per BC-1.4. The command hook invokes `qa_checker.py` as a subprocess, which renders the slide via Playwright, takes a screenshot, runs the programmatic invariants, and appends a Tier 1 entry to `qa_log.jsonl`. **Tier 2 runs second**, dispatched by the slide-maker agent's final `Task` call to visual-qa per BC-8.4. Visual-qa reads the Tier 1 entry from `qa_log.jsonl`, runs its Tier 2 + veto checks (VETO-01..07 plus the VLM-observable invariants listed above), and appends a merged `tier: "2_merged"` entry containing both tiers' findings. The red-green decision in `check_g3_2_machine_gate` reads the latest entry, which under normal operation is the merged Tier 2 entry. Prior to BUG-AUDIT-17, this section described a "QA agent runs first, invokes qa_checker second" pipeline driven by a `type: "agent"` PostToolUse hook; that mechanism was broken by Claude Code v2.1.107 upstream (BUG-AUDIT-12b) and is no longer used. See §24.18 and BC-1.4 / BC-8.4 for the current dispatch contract.

**Tier 2 craft-knowledge input.** When performing Tier 2 judgment, the QA agent MUST read `${CLAUDE_PLUGIN_ROOT}/references/slide-qa-checklist.md` (Section 24.39) as context. The checklist is an adapted version of PaperBanana's 4-dimensional evaluation rubric (Faithfulness, Conciseness, Readability, Aesthetics) and contains **19 explicit named rules** — V-FAI-01..04 (Faithfulness), V-CON-01..03 (Conciseness), V-REA-01..07 (Readability), V-AES-01..05 (Aesthetics). The QA agent MUST check each of these 19 V-\* rules at Tier 2 in addition to the INV-\* rules enumerated above. These V-\* rules are NOT duplicates of the INV taxonomy — they cover VLM-observable patterns that have no programmatic analog, including embedded-image colormap detection (V-AES-02 flags jet/rainbow heatmaps pasted into slides, which bypass CSS-level enforcement entirely), amateurish clip-art or cartoon iconography (V-AES-03), narrative gibberish in body text (V-FAI-04), chaotic diagram routing (V-REA-03), and per-bullet word density beyond INV-09's bullet-count check (V-CON-01). The checklist's Section 8 mapping table in `slide-qa-checklist.md` gives the full rule-to-invariant cross-reference and indicates which V-\* rules are pure VLM judgment (no INV backing) versus which have partial INV overlap. The QA agent records any triggered V-\* rule as a `warnings[]` sub-object in `qa_log.jsonl` per REQ-QA-3, carrying the `invariant` field set to the closest INV (or the V-\* rule ID directly if no INV exists) plus the Debrief-specific Tier 2 extras (`dimension`, `rule_id`, `rule_name`, `severity`) as additional properties on the sub-object.

This resolves the historical "veto-first" confusion: there are zero vetoes allocated to `qa_checker.py`. The QA agent owns vetoes; `qa_checker.py` owns programmatic Tier 1; the QA agent owns VLM Tier 1 (only INV-21) and all VLM Tier 2.

**`qa_checker.py` invocation contract.** `qa_checker.py` accepts the slide HTML path, the screenshot path, AND the project root as arguments. It reads `style_config.json` from the project root to evaluate INV-10 (permitted diagram types) at check time — the permitted set is per-project data, not a hardcoded list. The checker opens its own `sync_playwright()` context (per Section 24.10.2) when it needs to measure rendered DOM (e.g., for INV-13, INV-14, INV-20, INV-22), renders the slide HTML, and measures element bounding boxes via Playwright's `bounding_box()` API.

**Preview slides are exempt from QA checks.** The transient preview slides under `.debrief/draft/preview_slides/` (generated during the Phase 2 style dialog per REQ-STYLE-10) are NOT passed to `qa_checker.py` or the QA agent. They use placeholder content and a non-locked draft style, and their only consumer is `debrief.preview_renderer` which screenshots them for display at G2.1. The PostToolUse hook (Section 7.3 / Section 24.3) scopes its triggering to writes under `slides/`, not `.debrief/draft/preview_slides/`. See Section 24.40 for the preview directory lifecycle.

### 24.23 deck_brief.md Template

```
# Deck Brief
## Presentation Context
- Archetype: <archetype_value>
- Presentation type: <type>
- Allocated time: <N>min
- Audience: <description>
- Occasion: <description>
## Content Signals
- presentation_type: findings_report
- allocated_time: 20min
- code: no
- math: yes
- diagrams: yes
- plots: yes
- columns: no
- bullet_heavy: no
## Key Messages
1. <message>
2. <message>
## Narrative Arc
<structured description of planned slide groups and their sequence>
## Rhetorical Strategy
<which devices are emphasized for this presentation type>
```

**Parser contract:** Each line in the `## Content Signals` section MUST match the regex `^- (?P<key>[a-z_]+): (?P<value>.+)$`. Keys are lowercase with underscores. Values for boolean fields are exactly `yes` or `no`. `allocated_time` is unquoted in the format `<N>min` (e.g., `20min`). `presentation_type` is one of the four values from REQ-CONSULT-8 (`teaching`, `findings_report`, `interview_grant`, `journal_club`). The Stylist's prepare script parses these lines and passes them to the Stylist as structured input. Unrecognized keys are preserved in the file but not interpreted by the Stylist.

### 24.24 Slide Approval Payload and Gate Data

Debrief uses two distinct files under `.debrief/` to carry gate-adjacent data. The split is canonical; no data is ever written to both files for the same gate.

**`.debrief/approval_<slug>.json`** — the slide approval payload. The Slide Maker is the sole writer; it writes this file at the end of **every** red-green iteration (GREEN, RED-with-improvement, RED-with-regression-revert, EXHAUSTED, oscillation revert), always reflecting the current best-known-good state per REQ-SLIDE-4. The write happens before the PostToolUse hook returns. This guarantees the file exists for both `G3.3_slide_review` and `G3.3_slide_review_post_diagnostic` `SLIDE APPROVED` paths (v1 L1 / post-diagnostic reachability lesson). The file is consumed by `update_state` on `G3.3_slide_review` `SLIDE APPROVED` and on `G3.3_slide_review_post_diagnostic` `SLIDE APPROVED`. After successful merge into `deck_state.json`, `update_state` deletes the file.

Rationale: G3.3 is a human gate presented *after* the Slide Maker has exited. At the moment the user types `SLIDE APPROVED`, no agent is active; the approval payload must already be on disk. Having the Slide Maker write it at the end of the GREEN iteration guarantees that.

**`.debrief/approval_<slug>.json` schema:**

```json
{
  "slug": "string (required)",
  "title": "string (required)",
  "content_summary": "string (required, max 500 chars)",
  "visual_approach": "string (required)",
  "design_choices": "string (required)",
  "forks_not_taken": "string (optional, empty string if none)",
  "user_recommendations": "string (optional, empty string if none)",
  "accepted_violations": "array (optional, matches Section 17.2 slide record format)"
}
```

`update_state` rejects files missing required fields with exit code 4. Extra fields are silently ignored. A missing file at `SLIDE APPROVED` time (either variant of G3.3) indicates Slide Maker failed to produce its approval payload — `update_state` exits with code 4 (state corruption).

**`.debrief/gate_data.json`** — user-supplied parameters parsed out of parameterized gate responses. `update_state` is the sole writer. No agent and no skill writes this file. The file is short-lived: `update_state` writes it as part of parsing the user's response, then either reads it back during the same invocation to drive the next state (for gates whose payload directly advances state) or leaves it in place so the next prepare step can reference the parsed payload by file path.

**`.debrief/gate_data.json` schema:**

```json
{
  "gate_id": "<id>",
  "data": { ...gate-specific fields... }
}
```

Gates that write `gate_data.json`:

- `G1.3_figure_selection`: **Exception — does NOT write `gate_data.json`** despite appearing in this list for schema-documentation completeness. Per Section 24.21 and P-BP-13, G1.3's parsed result is written directly to `debrief_state.json.selected_figures` (durable field). The payload format is `{"selected_figures": [1, 3, 5]}` or `{"selected_figures": "all"}`, but the delivery mechanism is a direct `debrief_state.json` write, not an ephemeral `gate_data.json` file.
- `G3.3_slide_review_post_diagnostic` `SLIDE REVISE: <instructions>`: `{"slide_revise_instructions": "<instructions>"}`
- `G3.4_group_review` `GROUP REVISE <slug>`: `{"group_revise_slug": "<slug>"}`
- `G3.V_view_dispatch` `DETAIL FIX <slug>`: `{"detail_fix_slug": "<slug>"}`

See Section 24.21 for the complete gate-data usage table and lifecycle rules. No other files in `.debrief/` are used for gate-adjacent data handoff.

**Consultant slide approval data (legacy note).** Earlier revisions of this spec stated the Consultant writes `.debrief/approval_<slug>.json`. That is superseded: the Slide Maker writes it. The Consultant does not write any approval file; its handoff of narrative-level decisions (group boundaries, rhetorical roles) happens through the slide brief (see "Brief dispatch ordering" below) and through `deck_brief.md`.

**Brief dispatch ordering:** When the Consultant dispatches a group of briefs, it MUST write the files in this order:

1. All brief JSON files to `.debrief/briefs/<group_id>_<slug>.json` (one per slide in the group).
2. An atomic marker file `.debrief/briefs/<group_id>_MANIFEST.json` containing:
   ```json
   {
     "group_id": "<id>",
     "slide_count": N,
     "slugs": ["slug1", "slug2", ...],
     "dispatched_at": "<ISO8601>"
   }
   ```

The routing script fires machine gate G3.1 *(dead -- BUG-AUDIT-31)* (briefs dispatched) only when the manifest file exists AND its `slide_count` matches the number of brief files for that group. This avoids a race where the routing script could fire G3.1 early if briefs were being written one at a time.

**Group cleanup on G3.4 GROUP APPROVED.** When the group completes (G3.4 `GROUP APPROVED`), `update_state` MUST delete, atomically:

1. `.debrief/briefs/<group_id>_MANIFEST.json`
2. All `.debrief/briefs/<group_id>_*.json` brief files for that group.

Cleanup is atomic in the sense that `update_state` removes all files for the group in a single pass. If any removal fails (e.g., filesystem error), `update_state` MUST NOT leave a partial state — it either removes all of them or rolls back by leaving all of them (and reports the error). The per-slide `.debrief/approval_<slug>.json` files for that group, if any remain (they normally do not — they are deleted at each `SLIDE APPROVED`), are also removed as part of the group-completion sweep so stale approval payloads cannot leak into a later group.

**`.debrief/diagnostic_<slug>.md` — bug-diagnostic report.**

The bug-diagnostic agent (invoked by routing when `sub_phase == production/diagnostic`, per Section 24.18 and the L2 dispatch flow) writes its report to `.debrief/diagnostic_<slug>.md`. The file is a structured markdown document with at minimum these sections:

- `## Summary` — one-paragraph description of what went wrong across the 5 iterations.
- `## Failure Pattern` — which invariants failed and in what sequence.
- `## Root Cause Hypothesis` — the diagnostic agent's best guess at the underlying problem.
- `## Suggested Fix` — concrete instruction addressed to the Slide Maker.

**Lifecycle:**

1. **Written** by the bug-diagnostic agent at the end of its invocation, before the `post` step that transitions to `production/slide_review` with `pending_gate: G3.3_slide_review_post_diagnostic`.
2. **Read** by `prepare` when assembling the context for `G3.3_slide_review_post_diagnostic` (per Section 22.8.1).
3. **Deleted** by `update_state` when `G3.3_slide_review_post_diagnostic` resolves, regardless of response (SLIDE APPROVED or SLIDE REVISE: ...). The file is also deleted if the gate is superseded (e.g., a fresh EXHAUSTED for the same slug overwrites it). *(BUG-AUDIT-22: `/debrief:restore` does not touch `.debrief/`, so diagnostic files are retained across restore.)*
4. **Retained** across `/debrief:quit` if the diagnostic gate is still pending (the user can resume and still see the report).
5. **Retained** across `/debrief:restore` — restore does not touch `.debrief/`. *(BUG-AUDIT-22: the old `/debrief:reset` deleted `.debrief/` wholesale; `/debrief:restore` does not.)*

One diagnostic file per slug. If a second EXHAUSTED occurs for the same slug (post-REVISE), the diagnostic agent overwrites the existing file.

### 24.25 Reference Modality Adapters

The reference style analyzer (`debrief.style_analyzer`, REQ-CONSULT-13) supports four reference modalities: `.pptx`, `.pdf`, `.html` (single file), and a directory of `.html` files. Each modality has a dedicated adapter that converts the reference into a standardized PNG image batch. The batch is written to `assets/reference/slides/` (plus `.debrief/draft/analyzer_metadata.json` for PPTX metadata) and consumed by the Stylist agent, which performs the actual VLM-based derivation and writes `.debrief/draft/derived_style_guide.md` — see Section 24.25.4 for the rationale. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*

Common constraints: image batches are capped at 10 images regardless of modality (first + last + 8 middle, sampled uniformly) so the VLM's context budget is predictable. Output PNGs are written to `assets/reference/slides/` as a read-only project artifact for traceability.

#### 24.25.1 PPTX adapter (LibreOffice headless)

The PPT adapter converts PPTX slides to PNG using **LibreOffice headless** as the only supported method:

```bash
soffice --headless --convert-to png --outdir <output_dir> <input.pptx>
```

LibreOffice produces one PNG per slide in the output directory. The adapter caps at 10 slides (first, last, and 8 representative slides sampled uniformly from the middle).

**Note:** The `python-pptx` library does NOT provide slide rendering or thumbnail extraction — it only parses XML metadata. Do not attempt to use `python-pptx` for image generation. A PPTX file's `docProps/thumbnail.jpeg` contains only a single cover thumbnail, not per-slide images, and is insufficient for style analysis. (`python-pptx` IS used separately for the optional structured metadata extraction step described in REQ-CONSULT-13 step 2.)

**LibreOffice availability:** LibreOffice is a **system dependency** installed by the user (not managed by conda — see BUG-AUDIT-4). `bin/debrief` runs a discovery step (§24.4 step 5.6) after env activation: if `soffice` is not already on PATH, and the user is on macOS with `/Applications/LibreOffice.app/Contents/MacOS/soffice` installed, `bin/debrief` writes a wrapper shim at `${CONDA_PREFIX}/bin/soffice` so the runtime `soffice` PATH lookup inside the active conda env succeeds. If LibreOffice is not installed at all, `bin/debrief` exits 1 during bootstrap with platform-specific install instructions — the user cannot reach this adapter without LibreOffice being available. The analyzer therefore does not need to check for LibreOffice as an "optional" dependency — under any normal operation where `debrief new` succeeded, `soffice` is reachable on PATH inside the activated env.

**Env corruption detection:** If `soffice` is missing at invocation time, the env has been corrupted or externally modified. The analyzer MUST exit with code 2 and print the standardized env-corruption error (per Section 9.3.1):

```
ERROR: PowerPoint style import requires LibreOffice (libreoffice-still), which is not available in the debrief conda environment.
This indicates the environment is corrupt or was externally modified.
Recovery: run `debrief --rebuild-env` to recreate the environment from environment.yml.
```

**LibreOffice invocation contract:**

- **Timeout:** 120 seconds for the `soffice --convert-to png` call. On timeout, kill the process and exit with code 1 (not 2 — LibreOffice *is* installed, it just hung). Report: `LibreOffice headless timed out after 120s. Try closing any running LibreOffice instance and retry.`
- **Profile isolation:** invoke with `-env:UserInstallation=file:///<tmp-profile-dir>` to avoid conflicts with a desktop LibreOffice instance. Create and delete the temp profile per invocation.
- **Partial success detection:** after LibreOffice exits with code 0, count the PNG files in the output directory. If fewer than the number of slides in the PPTX (as determined via `python-pptx` slide count), treat as failure and exit with code 1. Print which slide indices are missing.
- **Warnings on stderr:** ignored if exit code is 0 AND the expected number of PNGs were produced.
- **Non-zero exit:** report LibreOffice's stderr output verbatim and exit with code 1.

#### 24.25.2 PDF adapter (PyMuPDF)

The PDF adapter uses PyMuPDF (`fitz.Page.get_pixmap()`) to render each page to PNG at 150 DPI. PyMuPDF is preferred over `pdftoppm` because `fitz` is already guaranteed by the conda env (it is used by the paper analyzer per REQ-CONSULT-17). The adapter caps at 10 pages (first + last + 8 middle, sampled uniformly). If the PDF has more than 50 pages, the adapter sets a heuristic flag that downstream code uses to surface a paper-vs-deck warning in the G1.2 gate prompt (REQ-CONSULT-14).

#### 24.25.3 HTML adapter (Playwright + Chromium)

The HTML adapter uses Playwright with Chromium to load each HTML file and screenshot it at 1920×1080. Single-file input produces one PNG; directory input produces one PNG per `.html` file, capped at 10 (alphabetical order: first + last + 8 middle). The HTML is loaded with `wait_until="networkidle"` and an additional 2-second delay to allow KaTeX, Mermaid, and rough.js to finish rendering before the screenshot is taken. The adapter uses the same Playwright lifecycle rules as the QA checker (Section 24.10.2): one `sync_playwright()` session per invocation, closed before the adapter returns.

#### 24.25.4 Reference style derivation (Stylist agent, not a Python subprocess)

After `debrief.style_analyzer` produces a standardized PNG batch in `assets/reference/slides/` (per the adapters in 24.25.1–24.25.3), the derived style guide is produced by the **Stylist agent**, not by a Python subprocess. This matches the pattern used by the visual-qa agent for screenshot analysis: the Stylist is a VLM-capable Claude subagent that can read images directly using its Read tool and produce markdown output as part of its normal REQ-STYLE-2 / REQ-STYLE-7 work.

**Derivation flow:**

1. `debrief.style_analyzer` produces the image batch and (for PPTX only) a metadata file at `.debrief/draft/analyzer_metadata.json` containing exact hex codes, font family names, font sizes, slide dimensions, and theme XML extracted via `python-pptx`. The analyzer does NOT call a VLM; it exits after writing the image batch and metadata.
2. The Stylist is invoked with its context per Section 22.8 (Stylist row). *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)* The context includes (a) the bundled craft-knowledge references at `${CLAUDE_PLUGIN_ROOT}/references/`, (b) `.debrief/draft/analyzer_metadata.json` when present, and (c) pointers to the image batch at `assets/reference/slides/`.
3. The Stylist reads the image batch directly and applies the instructions in `${CLAUDE_PLUGIN_ROOT}/references/paperbanana-derivation-meta-prompt.md` (the anti-prescriptive meta-prompt adapted from PaperBanana's `style_guides/generate_category_style_guide.py`, Apache-2.0). The meta-prompt file is loaded by the Stylist's prepare context per REQ-STYLE-2 step 3 when `reference_provided=true`. It contains verbatim-reused blocks from PaperBanana (anti-prescriptive philosophy, multi-option framing guidelines, observation-format rules) plus Debrief-specific additions (REQ-STYLE-7 output schema, PPTX metadata preservation rule, conflict handling with bundled references, biomedical domain framing). The Stylist follows the meta-prompt's Analysis Dimensions (Section 5 of the meta-prompt), Formatting Guidelines (Section 6), and Output Schema (Section 9), then writes `.debrief/draft/derived_style_guide.md` — a full markdown style guide matching the REQ-STYLE-7 11-section schema.
4. When PPTX metadata is present in `analyzer_metadata.json`, the Stylist preserves exact hex codes and font names from the metadata verbatim in the derived draft, rather than eyeballing them from the screenshots.

**Why no Python subprocess.** Debrief is a Claude Code plugin. Spawning a Python subprocess that calls a VLM (via SDK + API key) from within an already-running Claude Code session would introduce a user-facing prerequisite (the API key) that conflicts with Section 9.1's "conda is the only user-facing prerequisite" rule. The Stylist agent is the natural place to do the derivation work because it is already a VLM-capable agent invoked as part of the style-dialog flow.

**PaperBanana pattern adoption.** The anti-prescriptive meta-prompt pattern is adopted from PaperBanana's `style_guides/generate_category_style_guide.py` (Section 25.2 pattern #7) as a **prompt-engineering pattern**, not as forked code. The Stylist's task prompt incorporates the pattern. No Python fork of the upstream script exists in Debrief.

#### 24.25.5 Preview Renderer Module (`debrief.preview_renderer`)

`debrief.preview_renderer` is a thin Playwright wrapper used during the style dialog (REQ-STYLE-10) to render preview slide HTML files to PNG images. CLI: `python -m debrief.preview_renderer --project-root <path> --input-dir <dir> --output-dir <dir>` (explicit flags per Section 24.34). It loads each `.html` file in the input directory, waits for client-side libraries (KaTeX, Mermaid, rough.js) to finish before screenshotting at 1920×1080, and writes one PNG per HTML file to the output directory. It uses the same Playwright lifecycle rules as the QA checker and HTML reference adapter (Section 24.10.2): one `sync_playwright()` session per invocation, closed before the module returns. The module performs no state-file writes and no project-level archival — it exists solely to produce transient preview images under `.debrief/draft/preview_images/`, which are cleaned up after style lock.

### 24.26 Archetype Defaults Storage

Archetype defaults are stored in `${CLAUDE_PLUGIN_ROOT}/archetypes.json`. The prepare script reads this file when assembling the Consultant's discovery context. The file maps each archetype value to its defaults (presentation_type, time_default, content_signal_defaults, rhetorical_emphasis, expected_deliverables, key_defaults_text).

**`archetypes.json` schema example:**

```json
{
  "lab_meeting": {
    "presentation_type": "findings_report",
    "time_default": "20min",
    "content_signal_defaults": {
      "code": "no",
      "math": "no",
      "diagrams": "yes",
      "plots": "yes",
      "columns": "no",
      "bullet_heavy": "no"
    },
    "rhetorical_emphasis": ["logos", "hook"],
    "expected_deliverables": ["pdf"],
    "key_defaults_text": "Diagrams likely, data-heavy, no handout expected."
  },
  "conference_talk": { "...": "..." },
  "seminar": { "...": "..." },
  "lecture": {
    "presentation_type": "teaching",
    "time_default": "50min",
    "content_signal_defaults": { "...": "..." },
    "rhetorical_emphasis": ["logos", "recap"],
    "expected_deliverables": ["pdf", "handout"],
    "key_defaults_text": "Dense content OK, recap slides, handout likely."
  },
  "journal_club": { "...": "..." },
  "grant_panel": { "...": "..." },
  "job_talk": { "...": "..." },
  "custom": {
    "presentation_type": null,
    "time_default": null,
    "content_signal_defaults": {},
    "rhetorical_emphasis": [],
    "expected_deliverables": [],
    "key_defaults_text": ""
  }
}
```

All eight archetype values from Section 14.1.1 MUST appear as top-level keys. All fields are required per key. `custom` has empty/default values for all fields.

### 24.27 Diagram Library Bundling

Mermaid, rough.js, and KaTeX are bundled in `${CLAUDE_PLUGIN_ROOT}/assets/vendor/` and copied to `assets/vendor/` at project init. Slide HTML references them via `../assets/vendor/mermaid.min.js`, `../assets/vendor/rough.min.js`, `../assets/vendor/katex.min.js`, and `../assets/vendor/katex.min.css`. The style compiler may include vendor script references in a shared preamble, or each slide includes them directly. This satisfies INV-07 (no external network requests).

The vendor directory layout is:

```
assets/vendor/
├── mermaid.min.js
├── rough.min.js
├── katex.min.js
├── katex.min.css
├── katex-fonts/
│   └── (KaTeX woff2 fonts)
└── VERSIONS.md
```

**Version pinning:** The bundled versions of Mermaid, rough.js, and KaTeX MUST be pinned in a `VERSIONS.md` file inside `${CLAUDE_PLUGIN_ROOT}/assets/vendor/`. The file records the exact version, source URL, and SHA-256 hash of each bundled library. Versions MUST NOT be upgraded without regression testing against Debrief's test slide suite — a library update that changes rendering output could break existing slides.

Example `VERSIONS.md`:
```
mermaid.min.js    version 10.9.0   sha256:abc123...   https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.min.js
rough.min.js      version 4.6.6    sha256:def456...   https://cdn.jsdelivr.net/npm/roughjs@4.6.6/bundled/rough.min.js
katex.min.js      version 0.16.11  sha256:ghi789...   https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js
katex.min.css     version 0.16.11  sha256:jkl012...   https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css
```

**Hash verification timing:** SHA-256 hash verification of bundled vendor libraries MUST run during the `bin/debrief` pre-flight phase, immediately after the Python package install step and before any project directory operation (new or resume). The check is implemented in `debrief.launcher.verify_vendor_hashes()`. A hash mismatch prints a clear error naming the offending file, its expected hash, its actual hash, and the `VERSIONS.md` location, then exits with code 1 without touching project files.

**Real files, not stubs (BUG-AUDIT-16).** The bundled files MUST be the real minified libraries whose SHA-256 matches the authentic hash of the upstream jsDelivr artifact, NOT placeholder stubs whose hashes happen to match each other. A regression test in `tests/regressions/test_bug_audit_16_vendor_real_files.py` catches placeholder stubs by asserting that (a) every entry in VERSIONS.md has a corresponding real file on disk at the declared path, (b) each file is byte-for-byte what `fetch_vendor.py` would produce from the manifest's source URL, and (c) sanity bounds on file size — rough.js > 10 KB, mermaid > 100 KB, katex.js > 100 KB, katex.css > 10 KB, KaTeX woff2 > 5 KB — that a placeholder stub cannot satisfy. Maintainers acquire the real files via `python3 scripts/fetch_vendor.py` from the workspace root, which downloads from jsDelivr, verifies the hashes against VERSIONS.md, and fails loudly on any mismatch. The acquisition script is a maintainer-only build step; end users never download anything at runtime, preserving INV-07 (no external network requests from a running project). See BUG-AUDIT-16 for the historical incident where both the placeholder stubs AND the VERSIONS.md hashes were fake (the stub hashes were recorded instead of the real library hashes, making `verify_vendor_hashes` silently pass on a broken bundle).

**Recovery on vendor hash mismatch.** Vendor files live at `${CLAUDE_PLUGIN_ROOT}/assets/vendor/`, which is part of the plugin install — NOT inside the conda env. `debrief --rebuild-env` does NOT recover from vendor hash mismatches (it only rebuilds the conda env). The error message MUST include this recovery instruction verbatim:

```
Plugin assets appear corrupted. Reinstall the Debrief plugin via Claude Code's
plugin management (e.g., `/plugin reinstall debrief` or equivalent). If reinstall
fails, delete ${CLAUDE_PLUGIN_ROOT} and reinstall from source.
```

The same recovery instruction MUST appear in the README troubleshooting section (Section 24.37).

"Plugin initialization" in this spec refers to this pre-flight check. It happens once per `debrief` invocation (new or resume), before the project state is touched.

### 24.28 (Reserved)

Content merged into Section 17.4 (`separator_position` field semantics) and Section 24.10 (canonical PDF page order). No content lives at this number.

### 24.29 (Reserved)

This subsection number is reserved. Content that previously lived here was merged into Section 24.35 (Blueprint Writer Self-Evaluation Checklist). No content lives at this number.

### 24.30 User Prompting Mechanism

Debrief skills ask the user for input in exactly **two ways**:

**1. Through the gate catalog (canonical, state-affecting).** Any decision that advances pipeline state MUST go through a gate in Section 14.16. The gate prompt is displayed by the orchestrator after `prepare` writes the action block; the user's response is captured by the orchestrator, passed to `update_state` as a CLI argument, validated against `valid_responses`, and written to `debrief_state.json`. Examples: G3.3 slide review, G4.6 post-export deliverables, G1.2 style analysis choice.

**2. Through inline skill prompts (non-routing, transient).** Some skills need a one-shot confirmation or choice that does NOT affect pipeline state. Examples:

- `/debrief:restore` — "Type the snapshot label to restore" *(BUG-AUDIT-22: replaced hard-delete confirmation with snapshot-label selection)*
- `/debrief:handout` — "Which layout? (1) 2-up / (2) 4-up"
- `/debrief:export` — "Continue anyway? (yes/no)" when draft slides are present
- Red-green oscillation escalation (REQ-SLIDE-14) — "Keep trying / revert / your instructions"

Inline prompts are rendered by the SKILL.md instruction body telling Claude to:

1. Print the exact prompt text verbatim to the chat.
2. Stop producing output and wait for the next user message.
3. On the next turn, match the response against the documented valid options (case-insensitive unless specified).
4. Branch on the match, re-prompting for invalid input (except `/debrief:restore` which cancels on any non-match).

These inline prompts MUST NOT write to `debrief_state.json`, MUST NOT create a new gate entry, and MUST NOT call `input()` or read stdin from a Python module. They live entirely inside the skill's turn.

**Prohibited mechanisms:**

- Python modules calling `input()` or reading `sys.stdin`.
- Skills calling back to the main session via the Agent tool for user prompting.
- File-based prompt queues (e.g., `.debrief/pending_prompt.txt`).
- Any mechanism outside the orchestrator's chat I/O channel.

Each skill that performs an inline prompt MUST enumerate in its SKILL.md body: (a) the exact prompt text, (b) the valid responses, (c) the fallback for invalid responses.

### 24.31 Session Termination Mechanism

Skills in "Terminate" mode (`/debrief:quit`) end the Claude Code session by the following mechanism: the SKILL.md body instructs Claude to invoke the built-in `/exit` slash command after printing the confirmation/summary. *(BUG-AUDIT-22: `/debrief:restore` is now Run-and-return, not Terminate — only `/debrief:quit` terminates.)*

If the Claude Code version does not support programmatic `/exit` invocation from a skill context, the fallback protocol is:

1. Print the confirmation/summary.
2. Print the literal sentinel string: `[DEBRIEF SESSION ENDED — type /exit to return to your shell]`
3. Stop producing output on that turn.

Python modules MUST NOT attempt to kill the session via `os._exit()`, signals, or process termination — the harness owns the session lifetime.

The blueprint author MUST verify which mechanism is supported by the installed Claude Code version and document the choice in the project README.

### 24.32 View Invocation State Semantics

This subsection specifies the exact state mutations for `/debrief:view` invocation across all edge cases.

**Capture semantics (non-nested, not in red-green):** When `/debrief:view` is invoked, the skill reads current values of `phase`, `sub_phase`, `pending_gate`, and `current_slide_slug` from `debrief_state.json` and writes them as a compound object to `pre_view_state`:

```json
"pre_view_state": {
  "phase": "production",
  "sub_phase": "slide_review",
  "pending_gate": "G3.3_slide_review",
  "current_slide_slug": "methodology"
}
```

`pending_gate` may be null (user is mid-conversation with an agent) or non-null (user is at a human gate) — both are valid captures. `current_slide_slug` may also be null (e.g., during group planning). The skill then sets `pending_gate: "G3.V_view_dispatch"` and yields.

**Red-green deferral:** If `sub_phase` is `"red_green"` at invocation time, the skill MUST:

1. Print: `Red-green cycle in progress. The view will open after the current iteration completes.`
2. Set `pre_view_state` normally (compound object as above).
3. Set a new field `view_deferred: true` in `debrief_state.json`.
4. NOT set `pending_gate: G3.V` (the red-green cycle owns the pending state).
5. Yield.

The consultant, at each dispatch boundary, checks `view_deferred` after each red-green iteration. *(BUG-AUDIT-31: the routing script is dead; the consultant handles this check directly.)* If true AND the red-green cycle has exited (reached GREEN or EXHAUSTED), the consultant runs the view module and presents G3.V. `view_deferred` is then set to false.

**Precedence with red-green terminal states.** When the consultant detects both a red-green terminal state AND `view_deferred: true` in the same cycle:

1. Apply the G3.2 transition first: GREEN → `production/slide_review` (with `pending_gate: G3.3_slide_review`); EXHAUSTED → `production/diagnostic` (the diagnostic agent is invoked on the next cycle, which eventually leads to `production/slide_review` with `pending_gate: G3.3_slide_review_post_diagnostic`).
2. Open the view browser by running the view module.
3. Set `view_deferred: false`.
4. Set `pending_gate: G3.V_view_dispatch` for the current cycle, overriding the G3.3 (normal or post-diagnostic) pending gate that would otherwise be presented.
5. Capture the deferred G3.3 gate in `pre_view_state.pending_gate` so that it is restored on `CONTINUE` (per the restore semantics above) or when the DETAIL FIX dispatched from this view completes.

In the EXHAUSTED+view_deferred case, the diagnostic agent still runs (its invocation is not deferred), but the presentation of its result via G3.3_slide_review_post_diagnostic is deferred behind the view. The diagnostic report (`.debrief/diagnostic_<slug>.md`) is written to disk before the view is presented, so that when G3.V CONTINUE restores the deferred gate, the diagnostic context is already in place for prepare.

**Nested view:** If `pre_view_state` is already non-null when `/debrief:view` is invoked, the skill MUST:

1. NOT overwrite `pre_view_state` (preserve the original capture).
2. NOT modify `pending_gate` (G3.V is already the pending gate).
3. Re-run the view module with the new query, producing a new `output/view.html`.
4. Return. The user remains at G3.V with the new view displayed.

**Restore semantics (CONTINUE, DETAIL FIX completion):** On restore, `pre_view_state` is read and its four fields are written back to the top-level `phase`, `sub_phase`, `pending_gate`, and `current_slide_slug` fields, then `pre_view_state` is set to null. If the restored `pending_gate` is non-null, the consultant re-presents that gate. *(BUG-AUDIT-31: the routing script is dead; the consultant handles this directly.)*

### 24.33 State File Write Discipline

**Writers of `debrief_state.json`.** Exactly four entry points may write to `debrief_state.json`:

1. `debrief.launcher` — at project initialization (new project flow).
2. `debrief.update_state` — all post-action state transitions. *(BUG-AUDIT-31: `update_state` is dead at runtime; the consultant handles all dispatch via Tool calls.)*
3. `debrief.routing` — hash repair only, per REQ-ROUTE-8.
4. Yield-mode skills — via `python -m debrief.update_state --skill-prelude <skill_name> --field <name>=<value> [...]`, which validates the field set against the Section 24.19 table and rejects any write outside the allowed fields for that skill.

**REQ-ROUTE-5 clarification:** REQ-ROUTE-5's prohibition on direct `debrief_state.json` writes applies to the **orchestrator's conversational reasoning** — i.e., Claude MUST NOT decide to edit `debrief_state.json` as part of reasoning about what to do next. Skills in Yield mode are permitted to write specific fields via the `--skill-prelude` entry point above, which is an exception to REQ-ROUTE-5, not a violation of it.

Direct use of the `Write` or `Edit` tools on `debrief_state.json` by the orchestrator is prohibited in all cases. Direct writes by agents (Consultant, Slide Maker, Stylist, QA) are also prohibited. The Slide Maker writes `.debrief/approval_<slug>.json` (slide approval payloads); the Consultant writes `.debrief/briefs/<group_id>_*.json` and updates `deck_brief.md`. `update_state` is the sole writer of `.debrief/gate_data.json` (parsed parameterized gate responses) — no agent writes it. `update_state` merges all of these into the appropriate state file.

**Atomic writes and locking.** All writes to `debrief_state.json` MUST:

1. Write to a temporary file `.debrief/state.tmp`, fsync, then atomically rename to `debrief_state.json`.
2. Acquire an exclusive file lock (`fcntl.flock` on POSIX) on `.debrief/state.lock` before the read-modify-write sequence. Release the lock after the rename.

Because Claude Code processes user turns serially, concurrent writes are rare in the single-session model. The lock is a safety net against chained Bash subshells and subprocess cycles.

`deck_state.json` follows the same atomic-rename discipline but without the lock, because its writers (`update_state`, `export`, `launcher`) are never concurrent in the single-session model.

**Draft files under `.debrief/draft/`.** The draft artifacts created during Phase 2 (`style_config.json`, `style_guide.md`, `derived_style_guide.md`, `preview_style.css`, preview slide HTML, preview PNG images) follow the same atomic-rename discipline as `deck_state.json`: writes use a temporary file (`<path>.tmp`) and `os.rename()` to swap in place. File locking is NOT required because the Stylist and `update_state` never write to `.debrief/draft/` concurrently — the Stylist writes during its invocation, and `update_state` writes only at G2.1 post-transition (promotion) or REGENERATE PREVIEWS post-transition (preview re-render). See Section 24.8 for the promotion sequence.

### 24.34 Python Module Invocation Contract

All `debrief.*` Python modules invoked via `python -m debrief.<module>` MUST follow this contract.

**Exit codes (standardized):**

- `0` — success
- `1` — generic fatal error (module-specific semantics)
- `2` — conda env corruption detected: a required package is not importable, indicating the `debrief` conda env is corrupt or was externally modified (per Section 9.3.1)
- `3` — usage error (invalid or missing CLI arguments)
- `4` — state file corrupt or validation error

**Stream conventions:**

- **stdout** is reserved for the module's primary data output:
  - `routing`: JSON action block
  - `qa_checker`: JSON result
  - `math_renderer`: HTML fragment
  - Modules without a primary data output (`update_state`, `export`, `script_generator`, `handout`, `view`, `style_compiler`, `style_analyzer`, `paper_analyzer`, `style_guide_generator`, `preview_renderer`, `launcher`, `prepare`, `asset_ingest`) MUST NOT write to stdout on success.
- **stderr** is used for all human-readable messages (progress, warnings, confirmations, errors). Even success messages such as `Snapshot saved: foo` are printed to stderr, not stdout, so callers can distinguish machine-readable data from human-readable chat.
- **stdin** is never read. Modules MUST NOT call `input()` or `sys.stdin.read()`. User prompting is the skill's responsibility (Section 24.30).

**Argument conventions:**

- All modules accept `--project-root <path>` as their standard argument for specifying the project directory.
- Other arguments use explicit flags (e.g., `--mode`, `--input`, `--gate`, `--response`), never positional arguments beyond the project root.
- Exceptions: `math_renderer` takes `--input <latex_string>` quoted; `style_compiler` takes two positional paths for backward compatibility with its signature in Section 24.14.

**Logging:** Modules do not write their own log files. They write to stderr; the caller (skill or orchestrator) captures stderr if logging is needed.

**Env corruption detection:** All modules that depend on specific Python packages (e.g., `paper_analyzer` depends on PyMuPDF, `style_analyzer` depends on python-pptx) MUST check availability via `importlib.util.find_spec` at module entry. If a required package is not found, the module exits with code 2 and prints the standardized env-corruption error from Section 9.3.1. This is a corruption-detection mechanism, not an optional-feature gate — all dependencies are guaranteed by the conda env under normal operation.

#### ActionBlock prepare/post field format

The `prepare` and `post` fields in `ActionBlock` (see Section 14.17 and Section 22.7) are **shell command strings**, not action identifiers. The orchestrator executes them verbatim via Bash at step 2 (prepare) and step 5 (post) of the six-step cycle. Either field may be `null` if no command is needed for that action.

**Example action block with non-null prepare and post:**

```json
{
  "action_type": "human_gate",
  "gate_id": "G3.3_slide_review",
  "prepare": "python -m debrief.prepare --action G3.3_slide_review --project-root .",
  "post": "python -m debrief.update_state --gate G3.3_slide_review --response \"SLIDE APPROVED\" --project-root .",
  "reminder": "Review the slide at output/view.html."
}
```

The orchestrator does not parse or interpret these strings — it executes them. The Blueprint Author MUST ensure that the `routing.py` implementation produces `prepare` and `post` values as complete, executable shell command strings, and MUST NOT return bare gate IDs or action names in these fields.

### 24.35 Blueprint Writer Self-Evaluation Checklist

After drafting the blueprint, the Blueprint Author MUST walk through this checklist before submitting and produce `blueprint_self_eval.md` in the blueprint directory recording the answer to every item. Each item is a yes/no verification with a brief rationale or evidence pointer (e.g., "Yes — see Unit 4 API section, line 127" or "Yes — verified by grep `debrief_state.py` across all unit write-sets").

Any "no" answer requires one of:

1. **Fix before submission.** Preferred path for most failures.
2. **Open Item.** If the gap cannot be resolved without a clarification from the Blueprint Reviewer or a spec change, record it as a dedicated "Open Items" section of the blueprint with a proposed resolution. Do NOT silently ignore failing checks.

**Two check tiers.** Categories 1-10 require **semantic judgment** (e.g., "is this dispatch flow correct for the stated use case?"). Category 11 is **mechanical** — every item can be answered by grep + cross-reference without design knowledge. The Blueprint Author MUST run every Cat 11 check. A Cat 11 failure is almost certainly a bug, not a design choice: these are the kinds of drift (missing fields, orphaned modules, dead references, producer/consumer asymmetries) that scrapped v1 (36 audit findings) and v2 (8 reviewer findings). Cat 11 exists specifically to catch these before the reviewer has to.

**Self-eval document contract.** The `blueprint_self_eval.md` MUST:

- List every category (1-11) with its items.
- Answer each item with "Yes" or "No" followed by a brief rationale (1-2 sentences) or a concrete evidence pointer (file path, line number, grep result).
- For any "No" answer, indicate whether it was fixed (with the commit or line reference) or flagged as an Open Item.
- Be committed alongside the blueprint at `blueprint/blueprint_self_eval.md`.

The Blueprint Reviewer will verify the self-eval document exists and cross-check its answers against the blueprint. A missing or incomplete self-eval is a rejection condition.

#### Category 1: Routing Completeness

1. Does every human gate in the Gate Catalog (Section 14.16) have a matching entry in the Sub-Phase Transition Table (Section 14.17)?
2. Does every `valid_responses` entry for every gate have a transition row?
3. Does every sub_phase in the Transition Table have at least one exit transition? (List them all and verify none is a dead end.)
4. Does every sub_phase in the Transition Table have at least one entry transition? (No unreachable states.)
5. Are all conditional branches (e.g., `backup_mode=true`, `papers_provided=true`, `closing_slide_pending=true`, `group_revise_slug` non-null) covered with explicit rows in the Transition Table?
6. When multiple conditions are true simultaneously (e.g., `papers_provided=true` AND `reference_provided=true`), is the priority order explicit?
7. Does the `complete` state have a defined re-entry path for resume?
8. Does every machine gate (G2.2, G3.1, G3.2, G4.5) have a defined detection mechanism that reads specific state files or artifacts? *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)*
9. Is the `pre_view_state` set/restore/clear lifecycle complete for every path through G3.V (DETAIL FIX, ESCALATE, CONTINUE)?
10. Does the red-green cycle have a defined exit for both GREEN and EXHAUSTED cases?
11. Does the blueprint's `sub_phase` enum include every sub_phase present in the Section 14.17 transition table: `discovery/greeting`, `discovery/dialog`, `discovery/brief_review`, `discovery/paper_analysis`, `discovery/figure_selection`, `discovery/style_analysis`, `style/style_dialog`, `style/style_review`, `style/style_lock`, `production/group_planning`, `production/red_green`, `production/diagnostic`, `production/oscillation_review`, `production/slide_review`, `production/group_review`, `production/more_slides`, `production/deck_ending`, `finalization/export_options`, `finalization/backup_decision`, `finalization/export_confirm`, `finalization/reviewing_for_export`, `finalization/exporting`, `finalization/post_export`, `complete`? Each sub_phase has at least one entry row AND at least one exit row in Section 14.17?

#### Category 2: Dispatch & Agent Handoff

1. Does every dispatch event in Section 13.1 have a defined source and target?
2. When an agent completes, does the spec define how the next agent's context is assembled?
3. Does every agent invocation go through the `prepare` script as required by REQ-ROUTE-1?
4. Is the handoff data flow from Slide Maker → update_state → deck_state.json explicit? (Via `.debrief/approval_<slug>.json` per Section 24.24, written by the Slide Maker at the end of each GREEN iteration.)
5. Are the `.debrief/briefs/<group_id>_<slug>.json` files written atomically with the manifest file before G3.1 fires (per Section 24.24 manifest ordering)?
6. Is the `.debrief/gate_data.json` schema defined for every gate that needs it (per Section 24.21)?
7. Does every agent's prepare context (per Section 22.8) match what the agent's prompt actually needs?
8. Are all agent invocations routed through the orchestrator's six-step cycle via `prepare` (REQ-ROUTE-1)? No direct agent-to-agent invocations via the Agent tool are permitted.

#### Category 3: Branching & Edge Cases

1. Does every skill have preconditions defined for every phase where it might be invoked?
2. When a skill is invoked in a phase where it's not valid (per Section 14.19 matrix), does the spec define the error message?
3. Does the nested view case (user invokes `/debrief:view` while G3.V is already pending) behave correctly?
4. Does the red-green deferral case (user invokes `/debrief:view` during active red-green cycle) use `view_deferred` correctly?
5. Does the closing slide loop (G3.6 ADD CLOSING SLIDE) avoid infinite recursion via `closing_slide_pending`?
6. Does the GROUP REVISE single-slide fix return to G3.4 via `group_revise_slug` correctly?
7. Does the backup loop use G4.3 instead of G3.5 when `backup_mode=true`?
8. When both papers and a reference (any modality: .pptx/.pdf/.html/html_dir) are provided, does the routing correctly chain paper_analysis → style_analysis → style_dialog per REQ-CONSULT-13 and Section 14.17?
9. What happens if the user quits mid-red-green cycle? Is the resume behavior defined?
10. What happens if the QA hook times out (60s)? (The G3.2 check finds no new qa_log entry and treats the iteration as an implicit RED with a `timeout` failure, per REQ-SLIDE-6.) *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)*

#### Category 4: Module Contracts

1. Does every Python module follow the exit code convention (0/1/2/3/4) from Section 24.34?
2. Does every Python module follow the stdout/stderr convention from Section 24.34?
3. Does every Python module in the Section 2 `src/debrief/` plugin layout perform an `importlib.util.find_spec` check at module entry per Section 24.34 and Section 24.17? The per-module dependency list:
   - `debrief.launcher` — `json_repair` (reads state files during new/resume flows)
   - `debrief.deck_state`, `debrief.debrief_state` — `json_repair` (state library; parses state files)
   - `debrief.routing` — `json_repair` (state hash repair path per REQ-ROUTE-8)
   - `debrief.update_state` — `json_repair` (parses `.debrief/gate_data.json`, `.debrief/approval_*.json`, `qa_log.jsonl`)
   - `debrief.prepare` — `json_repair` (reads qa_log + gate_data for task prompt assembly)
   - `debrief.style_analyzer` — `python-pptx`, `fitz`, `playwright` (4 modality adapters per Section 24.25)
   - `debrief.preview_renderer` — `playwright` (REQ-STYLE-10)
   - `debrief.paper_analyzer` — `fitz` (REQ-CONSULT-17)
   - `debrief.qa_checker` — `playwright`, `json_repair`
   - `debrief.export` — `playwright`
   - `debrief.style_compiler` — stdlib only, no imports to check
   - `debrief.style_guide_generator` — stdlib only (NOT Playwright per REQ-STYLE-9 — v2 F4 lesson)
   - `debrief.view` — stdlib only (NOT Playwright, NOT json_repair, NOT PyMuPDF, NOT python-pptx — v2 F4 lesson: a prior blueprint falsely listed these as error conditions for view.py)
   - `debrief.asset_ingest` — stdlib only (v1 T1 lesson)
   - `debrief.math_renderer` — stdlib only
   - `debrief.script_generator` — stdlib only
   - `debrief.handout` — `playwright` (handout rendering uses the same Playwright path as export)

   Every module MUST exit with code 2 and the standardized Section 9.3.1 env-corruption error if any required import fails.
4. Does every module accept `--project-root` as its standard argument?
5. Are all CLI arguments documented per module?
6. Does `debrief.routing` output conform to the action block schema (Section 24.15)?
7. Does `debrief.update_state` validate gate responses against `valid_responses` and exit with code 4 on invalid?
8. Does `debrief.prepare` write to `.debrief/task_prompt.md` in the defined format?
9. Does every module reject invalid JSON input with exit code 4?
10. Does every module that writes state use atomic write + file lock per Section 24.33?

#### Category 5: Schemas & Data Formats

1. Is `deck_state.json` schema complete — every field has a type, required/optional status, and initial value?
2. Is `debrief_state.json` schema complete per Section 17.5 — EVERY field in the Section 17.5 table is present in the blueprint's DebriefState model: `phase`, `sub_phase`, `active_agent` (enum includes `none` for diagnostic sub_phase per P-BP-3), `archetype`, `current_group_id`, `current_slide_slug`, `pending_gate`, `last_gate_response`, `red_green_iteration`, `red_green_started_at` (REQ-SLIDE-12), `group_slide_index`, `group_slide_count`, `backup_mode`, `completed_groups`, `pre_view_state` (compound object), `view_deferred`, `closing_slide_pending`, `group_revise_slug`, `style_import_mode`, `reference_provided` (NOT `pptx_provided`), `reference_modality`, `papers_provided`, `selected_figures` (durable per P-BP-13, NOT ephemeral), `session_started_at`, `state_hash`?
3. Is `style_config.json` schema complete with all fields REQ-STYLE-3 mandates AND the top-level `provenance` object from REQ-STYLE-7 and Section 24.16?
4. Is the slide record schema (Section 17.2) complete with `backup`, `group_id`, `user_assets`, `has_math`? Is the slide brief schema (REQ-CONSULT-5) complete with `rhetorical_role` per REQ-CONSULT-15?
5. Is `deck_brief.md` structure documented including the Content Signals parser contract from Section 24.23?
6. Is `archetypes.json` schema documented per Section 24.26 with all 8 archetypes?
7. Is `.debrief/approval_<slug>.json` schema documented per Section 24.24?
8. Is `.debrief/gate_data.json` schema documented per gate per Section 24.21?
9. Is the `qa_log.jsonl` entry format documented including `veto`, `warnings`, `revision_instructions` fields?
10. Is the ledger entry schema documented per REQ-CONSULT-3?
11. Is the `qa_cycle_log.jsonl` entry schema the **per-cycle summary form** from REQ-SLIDE-12 (one entry per completed red-green cycle with fields `slug`, `started_at`, `completed_at`, `iterations`, `final_status`, `tier1_failures_by_iteration`, `tier2_warnings`) — NOT a per-iteration flat schema (v2 F7 lesson)? Is the sole writer `update_state` per P-BP-1?

#### Category 6: Error Paths & Recovery

1. Does every skill precondition failure have a defined error message?
2. Does every machine gate failure have a defined recovery path? *(BUG-AUDIT-31: machine gates are dead at runtime; the consultant handles these checks directly)*
3. Does every red-green cycle exhaustion case (EXHAUSTED after 5 iterations) route to the diagnostic agent?
4. Does every external tool failure (Playwright crash, LibreOffice timeout, PyMuPDF missing) have a defined error contract per Section 9.3.1?
5. Does every hash verification failure (Section 24.27) produce a clear error and exit without touching project files?
6. Does every state file corruption case trigger the `state_hash` recovery logic per REQ-ROUTE-8?
7. Does every ledger compaction trigger (per REQ-CONSULT-4) produce a valid summary entry that lets the Consultant reconstruct context?
8. Does the rollback-on-failure mechanism (REQ-SLIDE-14) correctly handle both clear regressions (fewer failures) and oscillation (same count, different failures)?
9. Does every user-invocable skill define its behavior when the project is in a corrupt state (state_hash invalid)?
10. Does every fatal error message include an actionable recovery instruction?
11. Does `update_state` delete `.debrief/diagnostic_<slug>.md` on every transition out of `G3.3_slide_review_post_diagnostic`? Specifically: on the SLIDE REVISE branch (Section 14.17 post-diagnostic SLIDE REVISE row) AND on all four G3.3 SLIDE APPROVED sub-branches (group_revise_slug, pre_view_state, more slides, last slide) per Section 14.17 and Section 24.24 lifecycle rule 3?

#### Category 7: User Interaction

1. Does every inline skill prompt follow Section 24.30 (print to chat, wait for next message, match against valid options)?
2. Does every gate prompt in Section 14.16.1 follow the canonical format?
3. Does every skill that takes arguments handle missing arguments gracefully (prompt or default per REQ)?
4. Does every error message include the install command for missing dependencies?
5. Does the archetype selection prompt (REQ-INIT-7) handle invalid input by re-prompting?
6. Does the "Continue anyway?" prompt at REQ-EXPORT-6 have a defined default and timeout behavior?
7. Does the "Type RESET to confirm" prompt (REQ-RESET-3) reject any non-exact-match response?
8. Does every Consultant question follow progressive disclosure (REQ-CONSULT-7) rather than upfront checklists?
9. Does every skill that terminates the session follow Section 24.31 (`/exit` invocation)?
10. Does every skill in Run-and-return mode print a confirmation to stderr and return without modifying state?

#### Category 8: Tooling & Dependencies

1. Does the Playwright usage across `debrief.export`, `debrief.qa_checker`, `debrief.preview_renderer`, and the HTML adapter inside `debrief.style_analyzer` follow Section 24.10.2 (no shared contexts)? Is `debrief.style_guide_generator` correctly implemented as a non-Playwright text-synthesis utility per REQ-STYLE-9?
2. Does the math renderer (`debrief.math_renderer`) emit only HTML wrappers and rely on browser-side KaTeX rendering per REQ-LATEX-3?
3. Does each reference-modality adapter in Section 24.25 use exactly the documented method: PPTX via LibreOffice headless (24.25.1), PDF via PyMuPDF `fitz.Page.get_pixmap()` (24.25.2), HTML (single file or directory) via Playwright (24.25.3)?
4. Does the PDF extraction use only PyMuPDF per REQ-CONSULT-17?
5. Are all bundled vendor libraries (Mermaid, rough.js, KaTeX) version-pinned in `VERSIONS.md` with SHA-256 hashes per Section 24.27?
6. Does the hash verification run during `bin/debrief` pre-flight per Section 24.27?
7. Are all managed dependencies (python-pptx, PyMuPDF, LibreOffice, json-repair, playwright, Python 3.11) pinned in the plugin's `environment.yml` per Section 9.3.1?
8. Does every dependency-consuming module check availability at invocation time and exit with code 2 and the standardized error format if a dependency is missing (indicating a corrupt conda env)?
9. Is the LibreOffice invocation contract (120s timeout, profile isolation, partial-success detection) implemented per Section 24.25?
10. Is Node.js explicitly NOT required (per REQ-INIT-5)?
11. Is conda the only user-facing prerequisite (per Section 9.1), with all other dependencies installed automatically by the `bin/debrief` bootstrap logic per Section 24.4?
12. Does the `bin/debrief` script create the `debrief` conda env from `environment.yml` on first run, gate package install and Chromium install on marker files in `~/.cache/debrief/`, and support `--rebuild-env` for recovery per Section 24.4?
13. Does `environment.yml` exist at the plugin root (per Section 2) and pin specific versions for Python, playwright, python-pptx, PyMuPDF, json-repair, and libreoffice-still?
14. Are the pre-flight checks in REQ-INIT-5 scoped to conda availability and env integrity only (not individual Python package checks, which are guaranteed by the env)?
15. Does the package install marker file path (`~/.cache/debrief/pkg_version_<plugin_version>.marker`) include the plugin version so plugin upgrades trigger re-install?
16. Does the `bin/debrief` script source conda via `conda info --base` before calling `conda activate`, so the script works in non-interactive shells?
17. Does `bin/debrief` implement Section 24.4 steps 1-5 and 5.5 in the **bash wrapper** (before any Python invocation — the conda env does not yet exist) and steps 6-8 in `python -m debrief.launcher preflight` (after env activation)? The split is load-bearing: putting all preflight in Python creates a chicken-and-egg problem where the Python interpreter does not yet exist (v1 C7 lesson).

#### Category 9: Blueprint-Specific Concerns

1. Is every unit in the blueprint traceable to at least one REQ in the stakeholder spec?
2. Does every REQ in the spec map to at least one blueprint unit?
3. Are the unit boundaries aligned with the skill/routing boundary (Section 24.19)?
4. Does the blueprint specify contract tests for every module's public interface?
5. Does the blueprint specify integration tests for every routing transition?
6. Does the blueprint specify integration tests for every agent handoff?
7. Does the blueprint document the chosen mechanism for Session Termination (Section 24.31)?
8. Does the blueprint document the chosen mechanism for Yield protocol step 4 (Section 24.19)?
9. Does the blueprint specify regression tests against Debrief's bundled test slide suite (not an exemplar library — the plugin does not ship one per REQ-SLIDE-8) for bundled library version changes?
10. Does the blueprint specify the `debrief.launcher.verify_vendor_hashes()` implementation?
11. Does the blueprint produce a `README.md` at the plugin root that follows ALL sections required by Section 24.37 (Installation, First Run, Quick Start, Troubleshooting, Uninstallation, Dependencies, Acknowledgments)?
12. Does the README explicitly state that the user does NOT need to run `conda env create`, `conda activate`, or `pip install` manually (per Section 24.37)?
13. Does the README cover the `debrief --rebuild-env` recovery command in the Troubleshooting section (per Section 24.37)?
14. Does the blueprint specify integration tests that exercise the full bootstrap flow (fresh machine → miniconda → plugin install → first `debrief new`) on at least macOS and Linux (per NFR-PORT-1)?
15. Does the blueprint specify how the `environment.yml` file is bundled with the plugin distribution, ensuring the launcher can always find it at `${CLAUDE_PLUGIN_ROOT}/environment.yml`?
16. Does the blueprint verify that `libreoffice-still` (or the chosen LibreOffice conda-forge package) works on both Intel macOS and Apple Silicon? If Apple Silicon support is limited, does the blueprint document the limitation in the README Troubleshooting section?
17. Does the blueprint specify the generalized `debrief.style_analyzer` contract with all 4 modality adapters (PPT via LibreOffice, PDF via PyMuPDF, HTML single-file via Playwright, HTML directory via Playwright) per Section 24.25?
18. Does the blueprint correctly encode reference style derivation as an in-agent Stylist responsibility (per Section 24.25.4) — i.e., `debrief.style_analyzer` writes the image batch and PPTX metadata but does NOT call a VLM; the Stylist reads the batch directly and produces `.debrief/draft/derived_style_guide.md` using the anti-prescriptive meta-prompt pattern from the bundled references? No `style_derivation.py` Python subprocess exists. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*
19. Does the blueprint specify the `debrief.preview_renderer` contract per REQ-STYLE-10: Playwright lifecycle conformance to Section 24.10.2, output at 1920×1080 PNG, input from `.debrief/draft/preview_slides/`, output to `.debrief/draft/preview_images/`, 30-second target / 60-second hard timeout?
20. Does the blueprint specify the `.debrief/draft/` directory lifecycle per Section 24.8, REQ-STYLE-10, REQ-QUIT-1 step 4, and Section 24.21 (creation, population, promotion on STYLE APPROVED, cleanup on LOCK SUCCESS, retention on /debrief:quit mid-Phase-2)?
21. Does the blueprint write G1.3's parsed response to `debrief_state.json.selected_figures` as durable state (per Section 17.5 and Section 24.21 G1.3 row), NOT to `.debrief/gate_data.json`? See P-BP-13. (`selected_figures` is consumed by the Consultant's group_planning context long after G1.3 fires, so ephemeral `gate_data.json` would be lost.)

#### Category 10: Known Blueprint Pitfalls (P-BP-1 through P-BP-16)

These items correspond to specific failures observed in prior blueprint drafts. See Section 24.38 for full descriptions.

- [ ] 10.01: Every file referenced in any unit's write set is written by exactly one unit (no dual writers) — P-BP-1
- [ ] 10.02: Every JSON schema in the blueprint contracts matches the corresponding spec schema field-for-field — P-BP-2
- [ ] 10.03: No state fields are added to DebriefState/DeckState/PresentationRecord without a corresponding spec update — P-BP-3
- [ ] 10.04: Every version-counted deliverable type has a matching counter field in PresentationRecord and a matching increment function — P-BP-4
- [ ] 10.05: ActionBlock.prepare and ActionBlock.post are shell command strings (not bare identifiers) with complete format specified — P-BP-5
- [ ] 10.06: `check-write-auth` parses stdin as JSON using `jq` (or equivalent) and `jq` is in environment.yml — P-BP-6
- [ ] 10.07: Each unit's Tier 3 error conditions list only dependencies actually used by that unit — P-BP-7
- [ ] 10.08: Gate prompts in blueprint's `gate_prompt_text` implementation correctly distinguish `{name}` (substituted) from `<literal>` (user-input indicator) — P-BP-8
- [ ] 10.09: The blueprint does NOT contain an exemplar library unit (no Unit 11), no `exemplars/` directory, no `exemplar_index.json`, and no fallback branching on exemplar availability. The Slide Maker has a single style-guide-driven generation path per REQ-SLIDE-8 — P-BP-9
- [ ] 10.10: Any schema mismatch between spec and blueprint is resolved by raising a clarification question, following the spec, or flagging as an Open Item — never by silent invention — P-BP-10
- [ ] 10.11: The blueprint correctly implements the `.debrief/draft/` lifecycle: atomic promotion on `STYLE APPROVED`, discard on `STYLE REVISE`, partial cleanup on `REGENERATE PREVIEWS`, retention through `/debrief:quit` mid-Phase-2, and removal on `LOCK SUCCESS` — P-BP-11
- [ ] 10.12: `check-write-auth` PreToolUse hook exits with code 2 (NOT 1) on both deny branches per Section 24.3 — P-BP-12
- [ ] 10.13: G1.3 `selected_figures` is written directly to `debrief_state.json`, NOT to `.debrief/gate_data.json` — P-BP-13
- [ ] 10.14: Reference style derivation is in-agent (Stylist reads images directly); no `style_derivation.py` Python subprocess exists, no VLM SDK pinned in environment.yml — P-BP-14
- [ ] 10.15: G3.3 is two distinct gate IDs (`G3.3_slide_review` and `G3.3_slide_review_post_diagnostic`) with different grammars; bare `SLIDE REVISE` is rejected at the post-diagnostic variant — P-BP-15
- [ ] 10.16: `update_state` does NOT unconditionally delete `.debrief/gate_data.json`; same-invocation consumers delete, cross-cycle consumers leave the file for the next prepare cycle — P-BP-16

#### Category 11: Mechanical Consistency Checks (static analysis)

These items are purely mechanical — each can be answered by grep and cross-reference without design judgment. The Blueprint Author MUST run every item. A failing Cat 11 check is almost certainly a bug, not a design choice. These are the kinds of drift that scrapped prior blueprints: missing fields, orphaned modules, dead references, producer/consumer asymmetries. The Blueprint Author records the answer to every item in `blueprint_self_eval.md` per the Section 24.35 preamble.

**Schema completeness (forward direction: spec → blueprint)**

- [ ] 11.01: For every field in every schema table in Sections 17.1, 17.2, 17.4, 17.5, 24.16, 24.21, 24.24, and 24.26: is there a matching field in the corresponding blueprint Pydantic model / dataclass / JSON schema, with the same type, same domain values (enums), and same required/optional marking? Enumerate the field count per schema in the self-eval.

- [ ] 11.02: Conversely (backward direction: blueprint → spec): for every field in every blueprint schema, does the spec's matching schema section declare it? Extra fields not in the spec MUST be either removed or raised as clarification questions per P-BP-3 / P-BP-10. List any extras in the self-eval.

**Gate ↔ transition bidirectional coverage**

- [ ] 11.03: For every gate in Section 14.16 Gate Catalog, for every response in its `valid_responses` list: grep Section 14.17 Sub-Phase Transition Table for a row whose condition column references that gate response. Every response MUST have at least one matching transition row (or be documented as covered by a catch-all rule).

- [ ] 11.04: Conversely: for every row in Section 14.17 whose condition column references a specific gate response, is the gate defined in Section 14.16 with that response listed in `valid_responses`?

**Sub_phase ↔ enum bidirectional coverage**

- [ ] 11.05: For every `sub_phase` value in the blueprint's `sub_phase` enum (DebriefState model): is there at least one row in Section 14.17 where the value appears in either the `Current State` or `Next State` column?

- [ ] 11.06: Conversely: for every `sub_phase` value appearing in Section 14.17 (either column), is it present in the blueprint's enum?

**Module call graph — no orphans, no undefined callees**

- [ ] 11.07: For every Python module file listed in Section 2 `src/debrief/` tree: grep the blueprint (action blocks, skill scripts, hook scripts, and inter-module imports) for at least one invocation path. If a module has zero invocations, either (a) justify it as an intentional library (e.g., `__init__.py`, `deck_state.py`, `debrief_state.py` — imported, not `python -m`'d) or (b) mark it as dead code and REMOVE it from Section 2.

- [ ] 11.08: For every `python -m debrief.X` command appearing anywhere in the blueprint (action blocks, prepare/post strings, skills, hooks, documentation): verify `src/debrief/X.py` exists in Section 2's layout.

**File contract symmetry — producer and consumer for every path**

- [ ] 11.09: For every file path in every unit's declared `write` set: is there at least one unit, skill, or hook that **reads** the file? Exceptions — **terminal artifacts** (written but not read by any unit):
    - `output/<date>_*/deck_v*.pdf`
    - `output/<date>_*/script_v*.md`
    - `output/<date>_*/handout_v*.pdf`
    - `output/view.html`
    - `output/screenshots/<slug>.png`
    - `output/qa_log.jsonl` (read only externally / for debug)
    - `output/qa_cycle_log.jsonl` (same)
    - `output/export_log.jsonl` (read by G4.5 machine gate *(dead -- BUG-AUDIT-31)*; otherwise terminal)
    - `.debrief/task_prompt.md` (consumed by the orchestrator, not by a blueprint unit)

    For any file written that is NOT in this exception list, a reader MUST exist somewhere in the blueprint.

- [ ] 11.10: For every file path in every unit's declared `read` set: is there at least one unit that **writes** the file? Exceptions — **bundled plugin-root files** (read but not written by any blueprint unit):
    - `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`
    - `${CLAUDE_PLUGIN_ROOT}/settings.json`
    - `${CLAUDE_PLUGIN_ROOT}/environment.yml`
    - `${CLAUDE_PLUGIN_ROOT}/archetypes.json`
    - `${CLAUDE_PLUGIN_ROOT}/hooks/hooks.json`
    - `${CLAUDE_PLUGIN_ROOT}/references/*`
    - `${CLAUDE_PLUGIN_ROOT}/templates/project_claude.md`
    - `${CLAUDE_PLUGIN_ROOT}/assets/vendor/*`
    - `${CLAUDE_PLUGIN_ROOT}/agents/*.md`
    - `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md`

    For any file read that is NOT in this exception list AND is not a user-provided reference (`assets/reference/*`, `assets/images/*`), a writer MUST exist somewhere in the blueprint.

**State field symmetry — producer and consumer for every field**

- [ ] 11.11: For every `debrief_state.json` field referenced in any unit's prepare-context assembly, routing logic, or gate handler: is there at least one unit that writes it? Exception: `state_hash` is updated implicitly by the State Management Library on every write.

- [ ] 11.12: Conversely: for every `debrief_state.json` field written by any unit: is there at least one reader? Fields that are written but never read are **dead state** and MUST be either (a) justified (e.g., diagnostic-only logging) or (b) removed.

**REQ ↔ Unit bidirectional coverage**

- [ ] 11.13: For every REQ-* in the main spec (all REQ groups — INIT, CONSULT, STYLE, SLIDE, QA, HOOK, ROUTE, VIEW, EXPORT, SCRIPT, HAND, ASSET, LATEX, RESET, QUIT, SAVE): does at least one blueprint unit claim to implement it? Produce the mapping table as `blueprint/req_coverage.md` if it does not already exist.

- [ ] 11.14: Conversely: for every blueprint unit, does it cite at least one REQ or Section 24.X subsection it implements? A unit that cites nothing is suspect — either (a) the unit is infrastructure (e.g., State Management Library implementing atomic-write discipline from Section 24.33) and its anchor is the Section 24 subsection number, or (b) the unit is speculative addition and MUST be removed.

**Action block and invocation conformance**

- [ ] 11.15: For every action block example in the blueprint's `routing.py` / `update_state.py` code and every `ActionBlock` emission point: do the fields match Section 24.15's schema (`action_type`, `agent`, `gate_id`, `valid_responses`, `gate_prompt`, `context_files`, `task_prompt_file`, `prepare`, `post`, `reminder`) with types and enum domains matching?

- [ ] 11.16: For every `invoke_agent` action in the blueprint: is the target agent name in Section 6.2's agents list (`consultant`, `slide-maker`, `stylist`, `visual-qa`, `bug-diagnostic`)? Note the `agent` field enum in the action block includes `diagnostic` as an invocation target even though `active_agent` does NOT include it (per the Section 24.15 enum note and P-BP-3).

- [ ] 11.17: For every `prepare` and `post` shell command string in the blueprint's action blocks: does the invoked Python module's CLI (per its Section 24.X subsection) accept all the flags/arguments supplied? No undocumented flags, no missing required flags. Specifically verify the `--project-root` convention per Section 24.34 and the per-module exceptions (`math_renderer`, `style_compiler`).

**Hook contract conformance**

- [ ] 11.18: PreToolUse hook — does the blueprint's `hooks/hooks.json` match Section 24.3 exactly on matcher (`Write|Edit`), command path (`${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth`), and timeout (10s)? Does the `check-write-auth` script use **exit code 2** on both deny branches (per P-BP-12 — NOT exit 1)? Does it parse stdin as JSON using `jq` per P-BP-6?

- [ ] 11.19: PostToolUse hook — does the blueprint's `hooks/hooks.json` match Section 24.3 exactly on matcher, hook type (`agent` with inline prompt, NOT a named-agent reference), prompt text, and timeout (60s)?

**Gate_data lifecycle symmetry**

- [ ] 11.20: For every `gate_data.json` write in the blueprint's `update_state` branches: is there a matching reader? Per Section 24.21 and P-BP-16: same-invocation consumers (G3.4 `GROUP REVISE`, G3.V `DETAIL FIX`) are read and deleted within `update_state`; cross-cycle consumers (G2.1 `STYLE REVISE`, G2.1 `REGENERATE PREVIEWS`, G3.3 post-diagnostic `SLIDE REVISE`) are read and deleted by the NEXT cycle's `prepare` step per Section 24.20. Verify the write→read chain for each.

#### Category 12: Artifact Naming Determinism

Every file and directory the plugin creates at runtime must have a fully specified, deterministic path. Two independent implementers reading only the blueprint and spec must produce identical file paths for the same logical artifact. This category was added after the v3 blueprint passed Categories 1–11 but left 19 of 42 runtime artifacts with ambiguous naming conventions.

- [ ] 12.01: Does every slug-keyed artifact path (`slides/<slug>.html`, `output/screenshots/<slug>.png`, `.debrief/approval_<slug>.json`, `.debrief/diagnostic_<slug>.md`, `.debrief/snapshots/<slug>_iter_<N>.html`, `assets/images/<slug>_<filename>`) reference the slug naming convention from Section 17.2?
- [ ] 12.02: Does the blueprint's slug validation enforce `^[a-z][a-z0-9_]{0,49}$` (no trailing underscore) per Section 17.2?
- [ ] 12.03: Does the blueprint's group_id format enforce `^(group|backup)_\d{2}$` per Section 17.2?
- [ ] 12.04: Does the blueprint's presentation-folder naming apply the Debrief Identifier Sanitization Algorithm (Section 24.10.1) with `max_length=40`?
- [ ] 12.05: Does the blueprint's paper-slug derivation apply the Debrief Identifier Sanitization Algorithm (Section 24.10.1) with `max_length=50`?
- [ ] 12.06: Does the blueprint's snapshot iteration filename use `<slug>_iter_<N>.html` with N 1-indexed and NOT zero-padded per REQ-SLIDE-14?
- [ ] 12.07: Does the blueprint's snapshot label sanitization apply the Debrief Identifier Sanitization Algorithm (Section 24.10.1) with `max_length=50` per REQ-SAVE-3?
- [ ] 12.08: For every file path in every unit's write set: is the complete path pattern (including all variable components like slugs, group_ids, counters, dates) unambiguously specified so a second implementer would produce the same path for the same inputs?
- [ ] 12.09: Are all version counters (`deck_v<NNN>`, `script_v<NNN>`, `handout_v<NNN>`) explicitly specified as 3-digit zero-padded?
- [ ] 12.10: Does the sanitization algorithm produce the same output for all edge cases: empty input, all-numeric input, all-special-character input, Unicode input, consecutive separators?

### 24.36 Gate Transition Diagram

```
PHASE 1: DISCOVERY
===================
                  +----------------+
     start ------>| Consultant     |
                  | (greeting)     |
                  +-------+--------+
                          | brief produced
                          v
                  +----------------+     BRIEF NEEDS WORK
                  | G1.1 HUMAN     |----------------------+
                  | Brief Review   |                      |
                  +-------+--------+                      |
                          | BRIEF APPROVED                v
                          |                    Consultant (revise)
                          |                          |
                          |                          +---> G1.1
                          |
                  papers provided?
                     /          \
                   yes           no
                   /               \
          +----------------+        |
          | Paper Analyzer |        |
          +-------+--------+        |
                  |                  |
                  v                  |
          +----------------+        |
          | G1.3 HUMAN     |        |
          | Figure Select  |        |
          +---+--------+---+        |
              |        |            |
         ALL  |   SELECT            |
         FIGS |   FIGS              |
              |  (sub-dialog)       |
              v        |            |
              +--------+            |
              |                     |
              | reference provided? |
              | (any modality)      |
              |    /          \     |
              |  yes           no   |
              |  /               \  |
          +---v--------------------+|
          | Style Analyzer         ||
          | (debrief.style_analyzer)|
          +-------+----------------+|
                  |              |  |
                  v              |  |
          +----------------+     |  |
          | G1.2 HUMAN     |     |  |
          | Style Analysis |     |  |
          +---+----+---+---+     |  |
              |    |   |         |  |
         BASELINE  |  IGNORE     |  |
              |  INSPO  |        |  |
              |    |    |        |  |
              v    v    v        |  |
              +----+----+--------+--+
              |
              v

PHASE 2: STYLE DEFINITION
==========================
                  +----------------+
  G1.1/G1.2/  -->| Stylist        |
  G1.3           | (dialog)       |
                  +-------+--------+
                          | draft config + guide + previews
                          v
                  +-----------------------+
                  | Preview Renderer      |
                  | debrief.preview_renderer
                  +-------+---------------+
                          |
                          v
                  +----------------+     STYLE REVISE
                  | G2.1 HUMAN     |----------------------+
                  | Style Review   |                      |
                  | (+ previews)   |                      |
                  +---+---+--------+                      |
                      |   |                               v
                      |   |  REGENERATE PREVIEWS   Stylist (revise)
                      |   +---> preview renderer         |
                      |          (same style)            v
                      |          re-present G2.1    +---> G2.1
                      |
                      | STYLE APPROVED (promote drafts, lock)
                      v
                  +----------------+
                  | G2.2 MACHINE   |
                  | Style Lock     |
                  +-------+--------+
                    |             |
              LOCK  |             | LOCK FAILED
              SUCCESS             +---> G2.1
                    |
                    v

PHASE 3: SLIDE PRODUCTION (per group)
======================================
                  +----------------+
     G2.2 ------>| Consultant     |<---- MORE SLIDES (from G3.5)
     or G3.5      | (plan group)   |<---- ESCALATE (from G3.V)
                  +-------+--------+
                          | BRIEFS DISPATCHED (G3.1 machine)
                          v
              +-----------------------+
              | FOR EACH SLIDE:       |
              |                       |
              |  +-----------------+  |
              |  | Slide Maker     |  |
              |  | (generate)      |  |
              |  +--------+--------+  |
              |           |           |
              |           v           |
              |  +-----------------+  |     RED (iteration < 5)
              |  | G3.2 MACHINE   |--+---------------------+
              |  | Red-Green QA   |  |                     |
              |  +--------+--------+  |        Slide Maker  |
              |           |           |        (rewrite)    |
              |           | GREEN     |             |       |
              |           v           |             +--> G3.2
              |  +-----------------+  |                     |
              |  | G3.3 HUMAN     |  |  EXHAUSTED --> Diagnostic
              |  | Slide Review   |  |
              |  +--------+--------+  |
              |     |          |      |
              |  APPROVED   REVISE    |
              |     |          |      |
              |     |    Slide Maker  |
              |     |    (revision)   |
              |     |       |         |
              |     |       +--> G3.2 |
              |     v                 |
              |   next slide          |
              +-----------+-----------+
                          | all slides done
                          v
              +-----------------+      GROUP REVISE <slug>
              | G3.4 HUMAN      |-----------------+
              | Group Review    |          pick slide(s)
              +--------+--------+                 |
                       | GROUP APPROVED            +--> G3.2 (red_green)
                       v
              +-----------------+
              | G3.5 HUMAN      |
              | More Slides?    |
              +---+--------+----+
                  |        |
           MORE   |        | LAST
           SLIDES |        | SLIDE
                  |        |
                  v        v

            (loop)  +-----------------+
                    | G3.6 HUMAN      |
                    | Deck Ending     |
                    +--+-----+-----+--+
                       |     |     |
                 AS-IS |     |     | ADD CLOSING
                       |     |     | SLIDE
                       |  EMPTY    |
                       |  CLOSING  +--> Consultant
                       |     |          (one more group,
                       v     v          closing_slide_pending=true)
                                            |
                     G3.6 --->  G4.1        +--> G3.5 skipped
                     (AS-IS /               +--> finalization/
                      EMPTY)                     export_options

              +-----------------+
   (anytime)  | G3.V HUMAN      |  <-- user invokes /debrief:view
              | View Dispatch   |
              +---+---+----+----+
                  |   |    |
          DETAIL  | CONT.  | ESCALATE
          FIX     |   |    |
            |     |   |    |
            v     v   |    v
         G3.2  (return |  Consultant
         (slug) to     |  (replan)
                pre-   |
                view)  |

PHASE 4: FINALIZATION
=====================
              +-----------------+
   G3.6 ---->| G4.1 HUMAN      |
              | Export Options  |
              +--------+--------+
                       v
              +-----------------+     BACKUP YES
              | G4.2 HUMAN      |------------------+
              | Backup?         |                  |
              +--------+--------+                  v
                       |               Phase 3 loop
                BACKUP |               (backup_mode=true)
                NO     |                       |
                       |<----------------------+
                       |               LAST BACKUP (G4.3)
                       v
              +-----------------+     REVIEW FIRST
              | G4.4 HUMAN      |--------+
              | Export Confirm  |        | (read-only view,
              +--------+--------+        |  no G3.V dispatch)
                       |                 +---> G4.4 (self-loop)
                       | EXPORT NOW
                       v
              +-----------------+     EXPORT FAILED
              | G4.5 MACHINE    |--------+
              | Export Result   |        +---> G4.4
              +--------+--------+
                       | SUCCESS
                       v
              +-----------------+     GENERATE SCRIPT /
              | G4.6 HUMAN      |<--- GENERATE HANDOUT
              | Post-Export     |     (self-loop)
              +--------+--------+
                       | DONE
                       v
                   COMPLETE
```

### 24.37 README Content Requirements

The plugin's `README.md` (at the plugin root) is the user-facing install and troubleshooting guide. The blueprint author MUST ensure the README includes the following sections, in this order:

**1. Installation**

Two-step process, clearly numbered:

1. Install miniconda (or mambaforge). Link to `https://docs.conda.io/en/latest/miniconda.html`. State that this is the ONLY software the user needs to install manually.
2. Install the Debrief plugin via Claude Code's plugin system. Give the exact command for the current Claude Code version (e.g., `/plugin install debrief` or the equivalent).

The README MUST explicitly say: "You do NOT need to run `conda env create`, `conda activate`, or `pip install` manually. The launcher handles all of that automatically on first run."

**2. First Run**

Describe what happens on first invocation of `debrief new`:
- The launcher creates a dedicated `debrief` conda environment.
- It downloads Python 3.11, Playwright, Chromium (~170 MB), LibreOffice (~500 MB), and other Python packages.
- The total first-run setup takes 5-15 minutes depending on network speed.
- Progress messages are printed throughout.
- Subsequent runs are fast (~500ms startup).

**3. Quick Start**

Minimal example: `cd ~/my-talk && debrief new`. Walk the user through the archetype selection prompt and the initial Consultant greeting.

The plugin generates slides by applying the project's `style_guide.md` to each slide brief. The style guide is authored during Phase 2 by the Stylist, which combines (a) the user's dialog choices, (b) a reference import if the user provided one (`.pptx`, `.pdf`, `.html`, or a directory of `.html` files — see REQ-CONSULT-13), and (c) the bundled craft-knowledge references at `${CLAUDE_PLUGIN_ROOT}/references/` (derived from PaperBanana's NeurIPS 2025 style guides and QA rubric plus the AI4VIS survey). The plugin does NOT ship an exemplar library; the style guide and bundled references are the single source of truth for visual design.

**4. Troubleshooting**

Cover the following common failure modes:
- "conda: command not found" → install miniconda from the link above.
- Bootstrap fails during env creation → `debrief --rebuild-env` to retry.
- Chromium download fails → check network connectivity, retry with `debrief --rebuild-env`.
- LibreOffice not available → this should never happen because it's in `environment.yml`, but if it does, `debrief --rebuild-env`.
- "Environment is corrupt or externally modified" → `debrief --rebuild-env`.
- "Plugin assets appear corrupted" / vendor hash mismatch → `debrief --rebuild-env` does NOT recover from this (vendor files live outside the conda env). Reinstall the Debrief plugin via Claude Code's plugin management (e.g., `/plugin reinstall debrief`). If reinstall fails, delete `${CLAUDE_PLUGIN_ROOT}` and reinstall from source. See Section 24.27 for the full recovery instruction.
- Partial or corrupt debrief env that prevents both normal launch and `--rebuild-env` → run `conda env remove -n debrief --force` manually, then retry `debrief new`.

**5. Uninstallation**

Tell the user how to cleanly remove Debrief:
1. Uninstall the plugin via Claude Code's plugin system.
2. Remove the conda env: `conda env remove -n debrief`.
3. Optionally remove the cache: `rm -rf ~/.cache/debrief`.

**6. Dependencies (for transparency)**

List the pinned versions from `environment.yml` so the user can see what's installed in the conda env. This is informational — the user does not install these manually.

**7. Acknowledgments and License**

Per Section 25 (Licensing and Attribution). Include the PaperBanana attribution and citation.

---

**Why this matters for the blueprint:** The README is the user's first touchpoint. If the install instructions mention `conda env create` or `pip install` as user-facing steps, the user will run them manually and create a broken environment that conflicts with the launcher's automatic bootstrap. The blueprint author must ensure the README tells the user **exactly one thing**: install miniconda, install the plugin, run `debrief new`.

### 24.38 Known Blueprint Pitfalls (Lessons from Prior Drafts)

The following pitfalls were observed in prior blueprint drafts (v1 and v2, archived in `blueprint/scrapped_v1/` and `blueprint/scrapped_v2/`). The Blueprint Author MUST explicitly verify that the current draft does not repeat them.

**P-BP-1 — Dual writer ambiguity for shared state files.**
When a file is written by more than one component, the blueprint MUST name a single canonical writer and forbid all other components from writing. Example: `qa_cycle_log.jsonl` is written by `update_state` only (per REQ-SLIDE-12). The visual-qa agent does NOT write to `qa_cycle_log.jsonl`. The PostToolUse hook's inline prompt does NOT instruct the agent to append to `qa_cycle_log.jsonl`. Another example: `.debrief/approval_<slug>.json` is written by the Slide Maker ONLY, at the end of every red-green iteration (per REQ-SLIDE-4 and Section 24.24). `update_state` reads it at G3.3 `SLIDE APPROVED` time and deletes it after merging. No agent or skill other than the Slide Maker writes this file. (v1 L1 lesson: early drafts put `update_state` as the writer for this file, causing dual-writer ambiguity with the Slide Maker.) Any file referenced in more than one unit's write set is a bug.

**P-BP-2 — Schema drift between spec and blueprint.**
Every JSON schema in the blueprint (dataclass, Pydantic model, or JSON example in the contracts appendix) MUST match the spec's schema field-for-field. Common drift: inventing new fields not in the spec, omitting fields present in the spec, renaming fields between spec and blueprint, using different value domains (e.g., `Literal["a", "b"]` vs. the spec's enumeration). Example prior failure: v1 blueprint invented object-form descriptor fields for an index schema that the spec specified as string arrays. The resolution was to update the spec to match (Q1 fix in audit). Future drift MUST be resolved by the Blueprint Author raising it as a clarification question, not by silently inventing fields.

**P-BP-3 — Invented state fields.**
If the blueprint adds a field to `DebriefState` or `DeckState` or `PresentationRecord` that isn't in the spec's Section 17 schemas, the blueprint MUST flag it as a clarification question. Example prior failure: v2 blueprint added `"diagnostic"` to the `active_agent` Literal enum because the spec's `production/diagnostic` sub_phase had no defined `active_agent` value. The correct resolution was to update the spec to clarify that `active_agent` is `"none"` during diagnostic execution. The incorrect resolution would have been to silently add `"diagnostic"` to the enum and hope the checker catches it.

**P-BP-4 — Missing version counter for new deliverable types.**
When a new deliverable type (handout, script, export) uses "version numbering follows the same convention as X", the blueprint MUST add a matching counter field to `PresentationRecord` and a matching `increment_<type>_count` function to `deck_state.py`. Example prior failure: v2 blueprint had `export_count` and `script_count` in `PresentationRecord` but no `handout_count`, forcing the handout module to scan disk for version counting instead of using a state counter.

**P-BP-5 — ActionBlock prepare/post field format must be shell command strings.**
The `prepare` and `post` fields in `ActionBlock` are shell command strings executed verbatim by the orchestrator (per Section 24.34). They are NOT action identifiers, gate names, or symbolic references. The Blueprint Author MUST specify the full format: e.g., `"python -m debrief.prepare --action G3.3_slide_review --project-root ."`. Returning bare identifiers here is a bug — the orchestrator cannot execute them.

**P-BP-6 — Claude Code hook input format is JSON on stdin.**
The `check-write-auth` PreToolUse command hook receives its input as a JSON object on stdin (per Section 24.3). The Blueprint Author MUST specify the JSON structure and the parser (recommended: `jq`). The script MUST NOT read the target path from an environment variable or a positional argument — Claude Code does not pass it that way. `jq` MUST be declared in `environment.yml` so the hook script can parse stdin.

**P-BP-7 — Spurious error conditions copied from other modules.**
Each unit's Tier 3 error conditions MUST list only error paths that actually apply to that unit. Copy-paste from other units' templates is a bug. Example prior failure: v2 Unit 9 (View Module) listed `playwright/json_repair import failure → exit 2` as an error condition, but `view.py` uses neither library. Error conditions must be derived from the unit's actual dependencies, not from a boilerplate template.

**P-BP-8 — Gate prompt placeholder syntax confusion.**
Gate prompts in Section 14.16.1 use `{name}` for runtime-substituted placeholders (value sourced by the prepare script) and `<literal>` for instructions to the user about what to type at the gate. The Blueprint Author MUST use the correct syntax in any gate prompt emitted by `gate_prompt_text`, and the implementation MUST NOT emit action blocks with unresolved `{}` placeholders in the gate prompt text. All substitutions are applied by the prepare script before the action block reaches the orchestrator.

**P-BP-9 — No exemplar library in v1.1.**
REQ-SLIDE-8 specifies that the plugin does NOT ship an exemplar library. There is no `exemplars/` directory, no `exemplar_index.json`, no `SLIDE APPROVED REFERENCE` gate response, and no fallback branching on exemplar availability. The Slide Maker has a single generation path that reads the project's `style_guide.md` (REQ-STYLE-7), `style_config.json`, the bundled reference documentation at `${CLAUDE_PLUGIN_ROOT}/references/` (Section 24.39), the slide brief, and the project's Content Signals. The blueprint's Unit 11 (exemplar library) is DELETED — the blueprint's Slide Maker unit (formerly Unit 12 or per the blueprint's numbering) handles all generation directly. The blueprint author MUST NOT re-introduce an exemplar library or an "exemplar availability" branching mode on their own initiative. If the v1.1 release ships and slide quality proves insufficient, an exemplar library may be added in v1.2 — but that is a future spec change, not a v1.1 blueprint decision.

**P-BP-10 — Spec schema drift resolution rule.**
When the Blueprint Author discovers a schema mismatch between the spec and a proposed blueprint contract, the resolution MUST be one of:
1. **Raise a clarification question** before writing the contract. Do not silently invent fields or silently omit fields.
2. **Follow the spec exactly** if the spec is unambiguous. The blueprint is downstream of the spec; the spec is authoritative.
3. **Flag the gap** in the blueprint prose as an "Open Item" if the gap is unresolvable without spec changes, and proceed with the best interpretation while noting the uncertainty.

The prior blueprints violated this rule several times (invented `"diagnostic"` active_agent value, invented a `description` field in a since-removed index schema, mismatched `qa_cycle_log.jsonl` schema). The Blueprint Author MUST follow the rule explicitly in the current draft.

**P-BP-11 — Draft promotion lifecycle for Phase 2 style lock.**
Prior drafts risk: blueprint implementations miss the `.debrief/draft/` directory lifecycle entirely. Specifically: (a) compiling the style CSS against a project-root `style_config.json` that does not yet exist at G2.1-fire time (it only exists in `.debrief/draft/`); (b) forgetting to atomically promote `.debrief/draft/style_config.json` and `.debrief/draft/style_guide.md` to the project root before running the compiler; (c) forgetting to remove `.debrief/draft/` after `LOCK SUCCESS`, leaving transient preview slides and draft CSS on disk indefinitely; (d) deleting `.debrief/draft/` on `/debrief:quit` mid-Phase-2, losing user work on resume; (e) treating `REGENERATE PREVIEWS` as a synonym for `STYLE REVISE` and discarding the draft style along with the preview images.

Fix: the blueprint MUST implement the Section 24.8 sequence exactly (precondition validation → atomic rename → compile → chmod → state update → cleanup), the REQ-QUIT-1 retention exception for `.debrief/draft/`, and the `REGENERATE PREVIEWS`-vs-`STYLE REVISE` distinction in `update_state`. See Section 24.8, Section 24.21 (G2.1 gate data usage), REQ-STYLE-10, and REQ-QUIT-1 step 4.

**P-BP-12 — PreToolUse hook deny uses exit code 2.**
The `check-write-auth` PreToolUse command hook (Section 24.3) MUST exit with code 2 on every deny branch. Exit code 2 is Claude Code's "deny tool call and show stderr to the LLM" signal. Exit code 1 is a non-blocking hook failure that does NOT block the write — using exit 1 silently permits every slide write and defeats the style-lock enforcement mechanism (Section 22.1). Bash convention is that exit 1 = failure, so the natural-language phrasing "exit on failure" can lead a blueprint author astray. The Blueprint Author MUST specify exit code 2 for both deny branches in `check-write-auth` (style-not-locked and write-outside-project) and document the distinction inline in the script. This is the single most dangerous pitfall in the v1 draft: v1 M1 silently broke the entire style-lock enforcement chain.

**P-BP-13 — Durable G1.3 figure selection lives in `debrief_state.json`, not `gate_data.json`.**
Every other parameterized gate in Section 24.21 writes its parsed payload to `.debrief/gate_data.json` (either same-invocation or cross-cycle consumer). G1.3 is the **exception**: its parsed result is written directly to `debrief_state.json.selected_figures` as durable state (per Section 17.5 and Section 24.21 G1.3 row) because it is consumed by the Consultant's `production/group_planning` context, which may run long after G1.3 fires (the user has to go through G2.1, G2.2, and the Phase 2 style dialog in between). *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)* Using the ephemeral `gate_data.json` for this value would cause the payload to be deleted, leaving `selected_figures` unavailable when it is actually needed. The Blueprint Author MUST ensure `selected_figures` is written to `debrief_state.json`, NOT to `.debrief/gate_data.json`.

**P-BP-14 — Reference style derivation is an in-agent Stylist responsibility, not a Python subprocess.**
Per Section 24.25.4, `debrief.style_analyzer` writes the image batch to `assets/reference/slides/` and (for PPTX only) extracts metadata to `.debrief/draft/analyzer_metadata.json`, then exits. The actual VLM-based derivation happens when the Stylist subagent is invoked: the Stylist reads the images directly using its Read tool and writes `.debrief/draft/derived_style_guide.md`. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)* The Blueprint Author MUST NOT introduce a Python subprocess (e.g., `debrief.style_derivation` or a fork of PaperBanana's `generate_category_style_guide.py`) that calls a VLM SDK — this would introduce a user-facing API-key prerequisite that conflicts with Section 9.1's "conda is the only user-facing prerequisite" rule. The PaperBanana anti-prescriptive meta-prompt pattern is adopted as a **prompt-engineering pattern** embedded in the Stylist's task prompt, NOT as forked code (Section 25.2 pattern #7). No `style_derivation.py` file exists in the plugin's `src/debrief/` layout (Section 2). Any blueprint unit that adds such a module is wrong.

**P-BP-15 — G3.3 is two distinct gate IDs with distinct grammars.**
Section 14.16 defines two G3.3 gate IDs: `G3.3_slide_review` (the normal post-GREEN gate, grammar = `SLIDE APPROVED | SLIDE REVISE`, bare `SLIDE REVISE` is valid — the user is prompted for instructions on the next turn) and `G3.3_slide_review_post_diagnostic` (after EXHAUSTED + diagnostic, grammar = `SLIDE APPROVED | SLIDE REVISE: <non-empty instructions>`, bare `SLIDE REVISE` is REJECTED with exit code 4 per REQ-SLIDE-5). The two gate IDs share a common prose pattern but are NOT the same gate. The Blueprint Author MUST:

1. Enumerate both gate IDs in the GateID enum and the valid_responses table.
2. Implement two canonical prompts (Section 14.16.1) and two prepare-context profiles (Section 22.8.1 — the post-diagnostic variant additionally loads `.debrief/diagnostic_<slug>.md`).
3. Implement two `update_state` branches with different grammar validators. Bare `SLIDE REVISE` at the post-diagnostic gate MUST exit with code 4 and the canonical message "After an exhausted red-green cycle, revision requires explicit instructions."
4. Honor the Section 14.17 G3.3 SLIDE APPROVED branch-priority table for BOTH gate IDs.
5. Delete `.debrief/diagnostic_<slug>.md` on every transition out of the post-diagnostic variant (both SLIDE APPROVED sub-branches and SLIDE REVISE).

Collapsing the two gate IDs into one is the v1 R5 error. The correct split is the v1 R5 fix applied in the spec.

**P-BP-16 — Cross-cycle `gate_data.json` is not deleted by `update_state`.**
`.debrief/gate_data.json` has two consumption modes (Section 24.21):

- **Same-invocation consumers** (G3.4 `GROUP REVISE`, G3.V `DETAIL FIX`): `update_state` reads the file, applies the payload to `debrief_state.json`, and deletes the file in its own invocation.
- **Cross-cycle consumers** (G2.1 `STYLE REVISE`, G2.1 `REGENERATE PREVIEWS`, G3.3 post-diagnostic `SLIDE REVISE`): `update_state` writes the file and **leaves it in place** for the NEXT dispatch cycle to consume and delete. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*

The Blueprint Author MUST:

1. Implement `update_state` so it does NOT unconditionally delete `gate_data.json` after reading. For same-invocation consumers, delete after applying payload. For cross-cycle consumers, do NOT delete — leave the file for the next prepare cycle.
2. Implement `prepare` to check for `.debrief/gate_data.json` at every invocation, validate its `gate_id` field against the current pending gate, inject the `data` object under a `## Gate Data` section of the task prompt, and delete the file after successful injection (per Section 24.20).
3. Never let `gate_data.json` persist beyond the dispatch cycle immediately following the gate response that produced it. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)*
4. Reject a mismatched `gate_id` with exit code 4 (state corruption) per Section 24.21.

The wrong pattern: `update_state` deletes the file immediately after writing it, leaving the cross-cycle consumer with nothing to read. This silently drops the STYLE REVISE feedback, the REGENERATE PREVIEWS flag, and the post-diagnostic SLIDE REVISE instructions.

**Self-check:** Before submitting the blueprint, the Blueprint Author MUST explicitly verify each of P-BP-1 through P-BP-16 against the current draft. Section 24.35 (Blueprint Writer Self-Evaluation Checklist) has a dedicated Category 10 covering these pitfalls.

### 24.39 Bundled Reference Documentation

The plugin ships a `references/` directory at `${CLAUDE_PLUGIN_ROOT}/references/` containing curated reference documentation used as craft-knowledge input to the Stylist and the slide QA pipeline. These files are bundled with the plugin (not generated at runtime) and are read-only for the Debrief runtime.

**Contents:**

- `references/paperbanana-diagram-style-distilled.md` — adapted from PaperBanana's NeurIPS 2025 Diagram Style Guide (Apache-2.0, © 2026 Google LLC). The distilled version retains the color palettes, shape grammar, connector/arrow semantics, typography conventions, and pitfall list from the original, rewritten for biomedical visualization context (e.g., the "Agent/LLM paper" domain section is replaced with a "Biomedical publication" section; connector semantics are retained as-is since they generalize).

- `references/paperbanana-plot-style-distilled.md` — adapted from PaperBanana's NeurIPS 2025 Plot Style Guide (same provenance). Color palette recommendations (viridis/magma/plasma/coolwarm, no jet/rainbow), axis/grid conventions, typography, and per-plot-type guidelines are retained; the biomedical focus adds guidance for survival curves, box plots of patient cohorts, and heatmaps of gene expression.

- `references/paperbanana-derivation-meta-prompt.md` — the anti-prescriptive meta-prompt pattern adapted from PaperBanana's `style_guides/generate_category_style_guide.py` (Apache-2.0, © 2026 Google LLC). Consumed by the Stylist when the user has imported a reference file (`.pptx`/`.pdf`/`.html`/html_dir) and the Stylist is in **reference-derivation mode** per REQ-STYLE-10 and Section 24.25.4. Tells the Stylist how to observe patterns in the reference image batch and produce `.debrief/draft/derived_style_guide.md` in Debrief's REQ-STYLE-7 output schema. Retained verbatim from upstream: the anti-prescriptive philosophy block, the multi-option framing guidelines, and the observation-format rules. Debrief-specific additions: single-stage prompt structure (PaperBanana's 2-stage batch→synthesis pipeline unified for a single Stylist invocation), REQ-STYLE-7 11-section output schema, PPTX metadata preservation rule (exact hex codes and fonts from `.debrief/draft/analyzer_metadata.json` when present), conflict-handling with bundled craft-knowledge references (flag for user resolution at the style dialog's conflict-disclosure step), biomedical domain framing. Attribution follows the same per-file NOTICE block format as the other distilled references.

- `references/slide-qa-checklist.md` — adapted from PaperBanana's 4-dimensional evaluation rubric (Faithfulness, Conciseness, Readability, Aesthetics) with veto rules. The veto rules are lifted and rewritten as programmatic or VLM-based checks that integrate with Debrief's INV-* and VETO-* invariant taxonomy in Section 16. This document is consumed by the visual-qa agent as context for its Tier 2 (warnings) judgment.

- `references/ai4vis-survey-distilled.md` — adapted from **AI4VIS: Survey on Artificial Intelligence Approaches for Data Visualization** by Wu et al., 2021 (arXiv:2102.01330). This is the foundational academic survey that sits behind PaperBanana's prescriptive style guides — it catalogs AI techniques for generating, storing, and analyzing visualization data and discusses the design principles that distinguish high-quality machine-generated charts from low-quality ones. The distilled version retains the principles that inform visualization QA (chart type selection, encoding choices, perceptual accuracy, information density thresholds) and explicitly cross-references PaperBanana's concrete recommendations so the Stylist can ground its advice in primary literature when asked. This file is cited under a "Primary Literature" attribution block (see below), not under the PaperBanana Apache-2.0 attribution block.

- `references/preview_placeholder_content.md` — per-presentation-type placeholder content catalog used by the Stylist to populate live preview slides during the style dialog (REQ-STYLE-10). Contains one entry per `presentation_type`/`archetype` with fields for title, subtitle, author, institution, content bullets, and data-exhibit caption.

- `references/VERSIONS.md` — attribution and version tracking. Records the PaperBanana source commit hash, the Debrief distillation date, the AI4VIS paper version, and the modification log per Apache-2.0 §4(b) and per fair-use academic citation discipline.

**Attribution discipline — PaperBanana-derived files.** Each distilled `.md` file that adapts PaperBanana content starts with a NOTICE block in this exact format:

```
NOTICE

This document is adapted from PaperBanana (https://github.com/dwzhu-pku/PaperBanana),
© 2026 Google LLC, licensed under Apache License 2.0.

Source file: <original file path>
Source commit: <hash>
Modifications: <brief description>
Modified by: Carlo Fusco and Leonardo Restivo
Modification date: <ISO date>

The original file is available at <upstream URL>.
```

**Attribution discipline — primary literature (AI4VIS).** `references/ai4vis-survey-distilled.md` is a summary/distillation of copyrighted academic work used under fair-use academic citation norms, not under Apache-2.0. It starts with a citation block in this format:

```
CITATION

This document distills concepts and principles from:

  Wu, A., Wang, Y., Shu, X., Moritz, D., Cui, W., Zhang, H., Zhang, D., and Qu, H.
  "AI4VIS: Survey on Artificial Intelligence Approaches for Data Visualization."
  arXiv preprint arXiv:2102.01330 (2021).
  https://arxiv.org/abs/2102.01330

Used under academic fair use for the purpose of documenting design principles
in a derivative software system (Debrief). This document paraphrases rather
than reproduces the paper's text. For authoritative statements, consult the
original paper.

Distilled by: Carlo Fusco and Leonardo Restivo
Distillation date: <ISO date>
```

**Patent notice.** The PaperBanana README states that patents have been filed by Google covering the specific multi-agent pipeline workflows (Retriever → Planner → Stylist → Visualizer → Critic). This distillation does NOT reproduce the pipeline architecture — it reuses only the documented craft knowledge and the evaluation rubric, both of which are documentation, not workflow implementation. The distillation is consistent with Apache-2.0 permissions and does not invoke the patented workflow. See the `NOTICE` file at the plugin root for the full PaperBanana attribution (Section 25.2).

**Consumer contracts.**

- The Stylist agent MUST read `paperbanana-diagram-style-distilled.md`, `paperbanana-plot-style-distilled.md`, and `ai4vis-survey-distilled.md` as part of its context when generating `style_guide.md` per REQ-STYLE-7. The project's `style_guide.md` is the project-specific distillation of these bundled references plus the user's style dialog choices. The Stylist MUST cite `ai4vis-survey-distilled.md` (and by extension the AI4VIS paper) when a user questions WHY a particular design principle is being recommended — this provides an academic grounding for the Stylist's recommendations beyond "PaperBanana said so."

- The visual-qa agent MUST read `slide-qa-checklist.md` when performing Tier 2 judgment per Section 24.22.

- The Slide Maker does NOT read these reference files directly — it reads the project's `style_guide.md`, which already encodes the relevant craft knowledge.

**Growth model.** The reference library can be expanded in future releases. Additional `.md` files in `references/` are picked up automatically by the Stylist if they match the naming convention `reference-*.md`. Users MAY add their own reference files to `references/` in their local install, though Debrief will not track or version user-added references.

### 24.40 `.debrief/draft/` Directory Lifecycle

The `.debrief/draft/` directory is a transient working area used exclusively during Phase 1 reference import and Phase 2 style definition. It is created, populated, promoted, and cleaned up across multiple dispatch cycles. *(BUG-AUDIT-31: the routing loop is dead; the consultant handles all dispatch via Tool calls.)* The blueprint MUST implement each lifecycle stage described below.

**Creation.** The directory is created on first write, not at project initialization. Two triggers create it:

1. **Reference import (Phase 1, G1.2 time).** When the Consultant invokes `debrief.style_analyzer` per REQ-CONSULT-13 and the user provided a reference file (any of `.pptx`, `.pdf`, `.html`, or a directory of `.html`), the analyzer writes `.debrief/draft/derived_style_guide.md` (and nothing else — the reference thumbnails live under `assets/reference/slides/`).

2. **Style dialog (Phase 2).** When the Stylist begins producing the draft config and guide, it writes `.debrief/draft/style_config.json` and `.debrief/draft/style_guide.md`. Per REQ-STYLE-10, the Stylist then invokes `debrief.style_compiler` to produce `.debrief/draft/preview_style.css`, writes `.debrief/draft/preview_slides/preview_*.html` placeholder slides, and invokes `debrief.preview_renderer` which writes `.debrief/draft/preview_images/preview_*.png`.

**Contents inventory:**

| File | Writer | Purpose |
|------|--------|---------|
| `derived_style_guide.md` | `debrief.style_analyzer` | Reference-derived draft ruleset (if user imported a reference) |
| `analyzer_metadata.json` | `debrief.style_analyzer` | PPTX theme metadata (exact hex codes, fonts, dimensions) extracted by python-pptx for the PPT modality only; consumed by the Stylist during derivation per Section 24.25.4. Written during Phase 1 reference import; retained through Phase 2 style dialog; cleaned up alongside the rest of `.debrief/draft/` on LOCK SUCCESS. |
| `style_config.json` | Stylist | Draft of the locked config; promoted to project root on APPROVED |
| `style_guide.md` | Stylist | Draft of the locked guide; promoted to project root on APPROVED |
| `preview_style.css` | `debrief.style_compiler` | Compiled CSS from draft config for preview rendering |
| `preview_slides/preview_*.html` | Stylist | Placeholder HTML slides using draft style |
| `preview_images/preview_*.png` | `debrief.preview_renderer` | Rendered previews shown at G2.1 |

**Promotion on G2.1 STYLE APPROVED.** Per Section 24.8, `update_state` atomically renames `.debrief/draft/style_config.json` → `./style_config.json` and `.debrief/draft/style_guide.md` → `./style_guide.md` BEFORE invoking the style compiler. The compiler operates on the project-root files. On `LOCK SUCCESS`, `update_state` removes the entire `.debrief/draft/` directory recursively. On `LOCK FAILED`, the just-promoted files at the project root are retained (as canonical draft), and the remaining `.debrief/draft/` is retained for diagnostic inspection.

**Discard on G2.1 STYLE REVISE.** `update_state` removes `.debrief/draft/` recursively before re-invoking the Stylist, so the next dialog iteration starts from a clean slate.

**Partial cleanup on G2.1 REGENERATE PREVIEWS.** `update_state` removes ONLY `.debrief/draft/preview_slides/` and `.debrief/draft/preview_images/` — NOT `style_config.json`, `style_guide.md`, `derived_style_guide.md`, or `preview_style.css`. It signals preview-regeneration mode by writing `.debrief/gate_data.json` with `{"gate_id": "G2.1_style_config_review", "data": {"regenerate_previews": true}}` (per Section 24.21). The Stylist is re-invoked in preview-regeneration mode with the same draft style values; only the preview placeholder content is regenerated (REQ-STYLE-10 step 7).

**Retention on `/debrief:quit`.** Per REQ-QUIT-1 step 4, `.debrief/draft/` is retained when `pending_gate` is `G2.1_style_config_review` or `sub_phase` is `style/style_dialog` / `style/style_review`. This ensures users do not lose in-progress style work on resume.

**Retention on `/debrief:restore`.** `/debrief:restore` does not touch `.debrief/` or its contents (including `draft/`). The restore command only overwrites `deck_state.json` from a snapshot and sweeps orphan slides. *(BUG-AUDIT-22: the old `/debrief:reset` deleted `.debrief/` wholesale; that behavior is permanently dropped.)*

**Invariants:**

- `.debrief/draft/` is NEVER created outside Phase 1 G1.2 (reference import) or Phase 2 (style dialog).
- `.debrief/draft/` is NEVER populated after Phase 2 is complete (after `style_locked: true`).
- The Slide Maker, QA checker, export module, and all Phase 3 / Phase 4 modules MUST NOT read from or write to `.debrief/draft/`.
- After G2.2 LOCK SUCCESS, the directory does not exist and MUST NOT be re-created by any downstream module.

**Atomic write discipline.** See Section 24.33 (draft files note) for the atomic-rename rule that applies to all draft files.

---

## 25. Licensing and Attribution

### 25.1 License

Debrief 1.0/1.1 is licensed under the Apache License 2.0. The plugin
root MUST contain a `LICENSE` file with the standard Apache 2.0 text
and a `NOTICE` file with the attribution and patent disclosures
described below.

### 25.2 PaperBanana Attribution

Seven architectural and content patterns in this spec are inspired by
PaperBanana (dwzhu-pku/PaperBanana, Apache 2.0), a multi-agent framework
for academic illustration generation. The NOTICE file MUST enumerate
these patterns and their provenance. The README MUST include an
Acknowledgments section with the same information.

The borrowed patterns are design-level adaptations; two of them
(distilled documentation files and a forked utility script) reuse
PaperBanana's content under Apache-2.0 with the attribution discipline
described in Section 24.39 and below. No source code from PaperBanana's
multi-agent pipeline is included. The seven patterns are:

1. Style guide as LLM prompt context (inspired by PaperBanana's NeurIPS 2025 style guide injection into agent prompts)
2. Multi-round critic feedback loop (inspired by PaperBanana's Critic to Visualizer iterative refinement cycle)
3. Reference-driven generation with few-shot retrieval (inspired by PaperBanana's RetrieverAgent few-shot pattern; in Debrief this takes the form of in-deck few-shot continuity using previously approved slides, per REQ-SLIDE-8 non-normative guidance — Debrief does NOT ship an exemplar library)
4. Tiered evaluation with content-first, aesthetics-second prioritization (inspired by PaperBanana's 2-tier scoring)
5. Documented style guides as primary source of truth for visual design (inspired by PaperBanana's `style_guides/*.md`). Debrief ships adapted versions of these style guides in `${CLAUDE_PLUGIN_ROOT}/references/`, with per-file attribution blocks (Section 24.39).
6. 4-dimensional evaluation rubric (Faithfulness, Conciseness, Readability, Aesthetics) with explicit veto rules (inspired by PaperBanana's evaluation framework). Debrief ships an adapted rubric at `${CLAUDE_PLUGIN_ROOT}/references/slide-qa-checklist.md` and integrates it with the INV-* / VETO-* taxonomy in Section 16.
7. Reference style derivation via VLM-batched images with an anti-prescriptive meta-prompt (adapted from PaperBanana's `style_guides/generate_category_style_guide.py`, 304 LOC). Debrief adopts this as a **prompt-engineering pattern**, not as forked code: the Stylist agent (a VLM-capable Claude subagent) applies the anti-prescriptive meta-prompt directly as part of its own invocation when producing `.debrief/draft/derived_style_guide.md`. No Python subprocess calls a VLM SDK. See Section 24.25.4 for the flow. This design avoids introducing a user-facing API-key prerequisite (conflicts with Section 9.1).

**NOTICE file content for the distilled references.** The plugin root's `NOTICE` file MUST include, in addition to the pattern list above, a paragraph stating that the files under `${CLAUDE_PLUGIN_ROOT}/references/paperbanana-*-distilled.md` and `${CLAUDE_PLUGIN_ROOT}/references/slide-qa-checklist.md` are adapted from PaperBanana (© 2026 Google LLC, Apache-2.0) and are subject to the Apache-2.0 attribution requirements. The NOTICE file points readers to the per-file NOTICE blocks embedded in each distilled reference (per Section 24.39) for the full modification notices. The anti-prescriptive meta-prompt pattern (item #7 above) is adopted as a prompt-engineering pattern rather than as forked code, so no file-level Apache-2.0 attribution is required beyond this pattern-list entry. `references/ai4vis-survey-distilled.md` is listed separately under a "Primary Literature" paragraph noting that it is a fair-use academic distillation, not an Apache-2.0 derivative.

### 25.3 Patent Risk Disclosure

Google has filed patents covering multi-agent workflows described
in PaperBanana. The NOTICE file MUST disclose this risk. Users of
Debrief 1.0/1.1 should evaluate patent exposure before commercial use.

The distilled documentation files in `references/` do NOT reproduce the patented multi-agent pipeline architecture — they reuse only craft knowledge (color palettes, layout conventions, veto rules) and not the Retriever → Planner → Stylist → Visualizer → Critic workflow. The anti-prescriptive meta-prompt pattern adopted from PaperBanana's `generate_category_style_guide.py` (Section 25.2 pattern #7) is applied in-agent by the Stylist as a prompt-engineering technique, not as a replica of the patented pipeline. This reuse is consistent with Apache-2.0 permissions. Commercial Debrief usage does not trigger the Google patents unless the commercial product replicates the multi-agent pipeline, which Debrief does not do.

### 25.4 Citation

The README MUST include the BibTeX entry for the PaperBanana paper
as requested by its authors:

```bibtex
@article{zhu2026paperbanana,
  title={PaperBanana: Automating Academic Illustration for AI Scientists},
  author={Zhu, Dawei and Meng, Rui and Song, Yale and Wei, Xiyu and
          Li, Sujian and Pfister, Tomas and Yoon, Jinsung},
  journal={arXiv preprint arXiv:2601.23265},
  year={2026}
}
```

---

## Bug Catalog

Entries in this section document bugs found after Stage 5 delivery. Each entry records the symptom, root cause, detection method, and fix summary so that future agents and reviewers can trace the reasoning behind post-delivery amendments. Bug entries may reference specific sections elsewhere in this spec; when a fix requires a contract change, the change is applied in place and the bug entry points to the affected section.

### BUG-AUDIT-1: `bin/debrief` is a thin shim and `pyproject.toml` declares a competing entry point

**Symptom.** A first-run user who follows the README (`plugin marketplace add "$(pwd)"` then `plugin install debrief@debrief`, then `debrief new` on their PATH) gets `ModuleNotFoundError: No module named 'debrief'` the moment any Python code tries to import the package. The 5–15 minute "first-run setup" progress message described in §9.4 never prints. The conda `debrief` env is never created. Playwright's Chromium binary is never downloaded. Vendor hash verification is never executed.

**Root cause (two coupled defects).**

1. The `bin/debrief` script delivered in `debrief1.0-repo/debrief/bin/debrief` is an 11-line thin shim whose only effective action is `exec claude --plugin "$PLUGIN_ROOT" "$@"`. It does NOT implement any of steps 1–10 of §24.4 (conda detection, env creation, activation, smoke test, marker-gated package install, marker-gated Chromium install, vendor hash preflight, subcommand dispatch). All of §9.4 and §24.4 assume this script performs the first-run bootstrap; the delivered script does not.
2. `debrief1.0-repo/debrief/pyproject.toml` declares `[project.scripts] debrief = "debrief.launcher:main_new"`. When any user runs `pip install -e` on the delivered plugin directory — which `bin/debrief` is itself supposed to do during step 6 of §24.4 — setuptools writes a `debrief` console-script shim into the active env's `bin/`. That shim invokes `debrief.launcher:main_new` directly, completely bypassing `${CLAUDE_PLUGIN_ROOT}/bin/debrief` and therefore the entire §24.4 bootstrap. §9.4 line 683 is explicit: "The `bin/debrief` script is the **single entry point** for all Debrief operations." The pyproject entry breaks that invariant: it creates a second, silently-winning entry point that skips conda detection, env creation, smoke test, marker gating, and vendor hash verification.

The two defects are coupled: removing the `[project.scripts]` entry without also fixing `bin/debrief` leaves users with no working `debrief` command at all; fixing `bin/debrief` without removing the pyproject entry leaves a half-correct state in which step 6's `pip install -e` would overwrite the correct entry point with the broken one on every first run. They must be fixed in a single change.

**Detection method.** Post-delivery audit of `debrief1.0-repo/debrief/` performed 2026-04-13. `bin/debrief` content was read directly and compared against §24.4 — 10 of 10 steps missing. `pyproject.toml` was parsed with `tomllib` — `[project.scripts]` contained the offending key. Structural regression tests (`tests/regressions/test_bug_audit_1_bootstrap.py`) added during the fix now detect both defects and any recurrence.

**Fix summary.**

- `src/unit_1/bin/debrief` rewritten to implement §24.4 steps 1–10 verbatim, including the `--rebuild-env` branch and the `DEBRIEF_REBUILD_DONE` re-exec recursion guard. The rewrite uses structured error messages for each failure mode, gates `pip install -e` on `${HOME}/.cache/debrief/pkg_version_<version>.marker` (reading `<version>` from `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`), gates Chromium install on `${CONDA_PREFIX}/.debrief_chromium_installed`, and delegates vendor hash verification to `python -m debrief.launcher preflight`.
- `debrief1.0-repo/debrief/pyproject.toml` `[project.scripts]` block removed entirely. There is no workspace source for this file — it was authored directly in the delivered repo and is not generated by `scripts/generate_assembly_map.py`'s `assemble_plugin_project()`. This asymmetry is noted so future Stage 5 assembly must not regenerate or re-introduce the entry.
- Blueprint amended with two new contracts in Unit 1:
  - **BC-1.16** forces `bin/debrief` to implement §24.4 verbatim and explicitly forbids the thin-shim form.
  - **BC-1.17** forbids any `[project.scripts]` entry named `debrief` in the delivered repo's `pyproject.toml`.
- Regression tests in `tests/regressions/test_bug_audit_1_bootstrap.py` cover every distinct step of §24.4 as structural content assertions over the bash source plus a `tomllib`-based assertion over `pyproject.toml`. Structural tests are used because the full end-to-end bootstrap (`conda env create`, `pip install`, `playwright install chromium`) cannot be exercised in unit-test CI.

**Pre-existing drift flagged during this fix.** The workspace `src/unit_3/launcher.py` is missing `main_new()` and the `if __name__ == "__main__"` block; the delivered `debrief1.0-repo/debrief/src/debrief/launcher.py` has them at lines 424 and 442. This is protocol drift from a direct edit to the delivered repo and is not remediated by BUG-AUDIT-1. Fixed as BUG-AUDIT-2.

### BUG-AUDIT-2: `src/unit_3/launcher.py` drift and latent BC-3.11 violation in `main_new()`

**Symptom (dormant).** Invoking `python -m debrief.launcher preflight` or `python -m debrief.launcher new` works in the delivered repo today but would break silently if anyone re-ran Stage 5 assembly from the workspace, because the workspace `src/unit_3/launcher.py` does not contain the `main_new()` entry point at all. BUG-AUDIT-1's §24.4 steps 8 and 9 both depend on this entry point. Separately, the version of `main_new()` that exists in the delivered repo does not call `_require_json_repair()` at entry; a corrupt env would surface as an ImportError inside `preflight()` or `new()` instead of the Section 9.3.1 standardized error (exit code 2). Both manifestations are dormant in the current delivered repo because the delivered `main_new()` exists and `preflight()` still runs its own `_require_json_repair()` check at line 393 — but both are time bombs.

**Root cause.** A direct edit to `debrief1.0-repo/debrief/src/debrief/launcher.py` added `main_new()` and `if __name__ == "__main__"` during Stage 5 or a post-Stage 5 patch without mirroring the change in the workspace stub `src/unit_3/launcher.py`. This violates CLAUDE.md's break-glass rule that "stubs are the single source of truth; never edit files in the delivered repo directly." The delivered `main_new()` also omitted the BC-3.11-mandated entry-level `_require_json_repair()` call because BC-3.11 was added to the blueprint after the delivered edit and was never re-validated against `main_new()` (tests/unit_3/test_launcher.py has zero tests for `main_new()` — confirmed by grep).

**Detection method.** Post-BUG-AUDIT-1 audit performed 2026-04-13. `wc -l` on both launcher files revealed the workspace (416 lines) was shorter than delivered (443 lines). `diff -u` showed the delta was exactly the 27-line trailing block containing `main_new()` and `__main__`. Blueprint grep for BC-3.11 surfaced the json_repair-at-entry requirement; inspection of the delivered `main_new()` body showed no such call, just direct dispatch.

**Fix summary.**

- Workspace `src/unit_3/launcher.py` extended with a `main_new()` entry point and `if __name__ == "__main__"` guard. `main_new()` calls `_require_json_repair()` as its first statement (BC-3.11 compliance) before resolving `plugin_root`, reading `sys.argv`, and dispatching to `preflight()`, `new()`, or an "unknown subcommand" exit-1 path with a usage message.
- Delivered `debrief1.0-repo/debrief/src/debrief/launcher.py` replaced its existing `main_new()`/`__main__` block with the workspace-sourced BC-3.11-compliant version. After the fix, the two files are byte-equal.
- Blueprint amended: **BC-3.11** strengthened to spell out that the `_require_json_repair()` call must be the first executable statement in `main_new()` (not merely "at entry" in the abstract); new contract **BC-3.12** added to require the existence of `main_new()`, its 3-arm dispatch shape, and the `__main__` guard, so that a future Stage 5 regeneration against a workspace missing these elements fails structural validation instead of silently shipping a broken launcher.
- New regression tests in `tests/regressions/test_bug_audit_2_launcher_drift.py` cover: existence of `main_new`, `__main__` guard, preflight/new dispatch arms, unknown-subcommand exit code and usage message, `CLAUDE_PLUGIN_ROOT` env lookup in the `main_new` body, BC-3.11 entry-level `_require_json_repair()` ordering, and a byte-equal drift-detection test that compares the workspace launcher to the delivered launcher whenever both paths resolve.

**Coupling note.** BUG-AUDIT-2 is structurally independent of BUG-AUDIT-1 but functionally dependent: BUG-AUDIT-1's `bin/debrief` invokes `python -m debrief.launcher preflight` and `python -m debrief.launcher new`, both of which require `main_new()` to exist as the module entry point. Fixing BUG-AUDIT-1 without BUG-AUDIT-2 would leave the delivered repo correct today and fragile to any Stage 5 re-run. Both fixes are now landed.

### BUG-AUDIT-3: `bin/debrief` does not follow symlinks when resolving `CLAUDE_PLUGIN_ROOT`, and the env-create failure cleanup reports a misleading "partial env" error for unrelated failures

**Symptom.** A user who symlinks `~/.local/bin/debrief` (or any PATH location) to the real `bin/debrief` and runs `debrief new` sees:

```
First-run setup: creating the debrief conda environment (this takes 5-15 minutes)...
Retrieving notices: done

EnvironmentFileNotFound: '/Users/cfusco/.local/environment.yml' file not found

Partial debrief env exists and could not be removed automatically.
Run `conda env remove -n debrief --force` manually, then retry `debrief new`.
```

Two things are wrong in this transcript:

1. The `EnvironmentFileNotFound` error is reading `environment.yml` from the **symlink's** parent directory (`~/.local/`) instead of the real plugin root. The file doesn't exist there — it lives at `${real_plugin_root}/environment.yml`.
2. The "Partial debrief env exists and could not be removed automatically" message is false. No `debrief` conda env existed at any point; `conda env list` before and after the failed run showed zero matches. The script falsely claimed a partial env was present because its cleanup branch ran `conda env remove -n debrief -y` unconditionally after any create failure, and that command returns a non-zero exit code when the env is absent.

**Root cause (two sub-defects).**

**BUG-AUDIT-3a: symlink-unaware plugin root fallback.** `bin/debrief` must resolve `CLAUDE_PLUGIN_ROOT` from its own filesystem location when the environment variable is unset (direct invocation, dev mode, or symlinked-onto-PATH installation). The original fallback used `"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`, which does not follow symlinks: when the script is invoked via `~/.local/bin/debrief → real/plugin/bin/debrief`, `${BASH_SOURCE[0]}` is the symlink path, `dirname` of the symlink is `~/.local/bin`, and `../` is `~/.local`. Every subsequent reference to `${CLAUDE_PLUGIN_ROOT}/environment.yml`, `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`, `pip install -e "${CLAUDE_PLUGIN_ROOT}"`, and `exec claude --plugin "$CLAUDE_PLUGIN_ROOT"` then points at the wrong directory. The first one to fail is the `conda env create -f "${CLAUDE_PLUGIN_ROOT}/environment.yml"` call, producing the `EnvironmentFileNotFound` error.

**BUG-AUDIT-3b: mandatory cleanup on every env-create failure.** The current cleanup branch attempts `conda env remove -n debrief -y` whenever `conda env create` returns non-zero, regardless of whether a partial env was actually left behind. `conda env remove` of a non-existent env itself returns non-zero, so the `if !` guard on that command fires for any create failure that does not leave a partial env — printing the "Partial debrief env exists and could not be removed automatically" message and the manual-recovery instructions. The real error (file not found, network timeout, disk full, etc.) is still visible above, but the "Partial debrief env exists" line at the bottom is load-bearing for the user's attention and consistently directs them to the wrong recovery action.

The two defects surfaced in the same transcript but they are logically independent. BUG-AUDIT-3a is the trigger; BUG-AUDIT-3b is the amplifier that made the error harder to diagnose. A future unrelated create failure (network error during conda solve, disk full) would have surfaced BUG-AUDIT-3b on its own. They are bundled into a single fix because they live in adjacent blocks of the same ~15 lines of bash and share regression-test infrastructure.

**Detection method.** User reported the full transcript from their machine on 2026-04-13 after running `debrief new` via a `~/.local/bin/debrief` symlink from `/Users/cfusco/Nextcloud/work/lab_meetings/20260421_Lab_meeting`. Verified the symlink target (`ls -l ~/.local/bin/debrief`) and the absence of any `debrief` conda env (`conda env list | grep debrief` → no match). Re-read `bin/debrief` lines 20–24 and the env-create cleanup block to confirm both root causes. Regression tests (`tests/regressions/test_bug_audit_3_symlink.py`) now cover the symlink resolution functionally (subprocess invocation of a real symlink pointing at a bash script extracted from `bin/debrief`) and the cleanup invariant structurally.

**Fix summary.**

- `src/unit_1/bin/debrief` plugin-root fallback block replaced with a pure-bash symlink-walking idiom delimited by sentinel comments `# BEGIN CLAUDE_PLUGIN_ROOT resolution (symlink-safe)` and `# END CLAUDE_PLUGIN_ROOT resolution (symlink-safe)`. The new block uses a `while [[ -L "$_debrief_source" ]]` loop with `readlink` and `cd -P` so it walks chained symlinks and handles relative targets without requiring GNU `readlink -f` (macOS ships BSD coreutils only). Loop variables are prefixed `_debrief_` and `unset` at the end to avoid polluting the outer script.
- `src/unit_1/bin/debrief` env-create cleanup block amended: the `conda env remove -n debrief -y` call and the "Partial debrief env exists" message are now gated on an explicit `conda env list | awk '{print $1}' | grep -qx debrief` existence check. When `conda env create` fails and no env is present, the script now prints only `ERROR: conda env creation failed. See output above for details.` and exits 1, allowing the real conda error above to be the visible diagnosis.
- Blueprint **BC-1.16** strengthened with two new requirement clauses: (a) the plugin-root fallback must resolve symlink chains so that invoking `bin/debrief` via a symlink on `PATH` yields the correct `CLAUDE_PLUGIN_ROOT`; (b) the env-create failure cleanup must not claim "partial env exists" unless `conda env list` actually contains the `debrief` env after the failure.
- New regression tests in `tests/regressions/test_bug_audit_3_symlink.py` cover: presence of the symlink-walking idiom, presence of the sentinel comments, absence of the legacy unsafe 2-line pattern, source-order invariant on the cleanup guard, and one functional subprocess test that extracts the resolution block between sentinels, runs it under a real symlink in `tmp_path`, and asserts the output equals the real plugin root (not the symlink's parent).

**User recovery after the fix lands.** No conda state cleanup needed — the failed run left nothing behind. Re-invoking `debrief new` from the project directory will proceed normally through the bootstrap.

### BUG-AUDIT-4: `libreoffice-still` is Linux-only on conda-forge and blocks macOS bootstrap

**Symptom.** After BUG-AUDIT-3 landed, a macOS user (Intel, `Darwin x86_64`) re-ran `debrief new`. The symlink-resolution fix worked, conda correctly found the real `environment.yml`, started solving, and failed:

```
Channels:
 - conda-forge
 - defaults
Platform: osx-64
Collecting package metadata (repodata.json): done
Solving environment: failed

PackagesNotFoundError: The following packages are not available from current channels:

  - libreoffice-still

Current channels:

  - https://conda.anaconda.org/conda-forge
  - https://repo.anaconda.com/pkgs/main
  - https://repo.anaconda.com/pkgs/r

ERROR: conda env creation failed. See output above for details.
```

**Root cause.** `libreoffice-still` on conda-forge ships `linux-64` and `linux-aarch64` builds only — no `osx-64` or `osx-arm64`. The LibreOffice project distributes macOS as `.app` bundles via libreoffice.org, and no one has maintained a conda-forge feedstock for macOS LibreOffice. The blueprint **BC-1.6** required `libreoffice-still` in `environment.yml` unconditionally, so the env creation fails on macOS with `PackagesNotFoundError`. Nobody caught this during Stage 5 assembly because Stage 5 tests did not exercise `conda env create` end-to-end on macOS. Spec §33 blueprint-check question 16 explicitly asks whether libreoffice-still works on both Intel macOS and Apple Silicon — the answer was never verified.

Secondary complication: even if the user has `/Applications/LibreOffice.app` installed on macOS (the standard install location), `soffice` is not on PATH. `src/debrief/slide_maker.py:107` invokes `subprocess.run(["soffice", ...])` unqualified, relying on PATH lookup inside the active conda env. So a macOS user with LibreOffice.app still hits a runtime failure in `adapt_pptx` because the Python code cannot find the binary.

**Detection method.** User ran `debrief new` after BUG-AUDIT-3 landed and pasted the full transcript on 2026-04-13. The `PackagesNotFoundError` message clearly identifies `libreoffice-still` as the blocked package and the channel list as conda-forge + defaults. Confirmed via direct filesystem check that `/Applications/LibreOffice.app/Contents/MacOS/soffice` exists on the user's machine but `which soffice` returns empty. Platform confirmed as `Darwin x86_64` via `uname -sm`.

**Fix summary.**

- `src/unit_1/environment.yml` no longer pins `libreoffice-still`. LibreOffice is reclassified as a **system dependency** the user installs via their OS-native channel.
- `src/unit_1/bin/debrief` gains a new **Step 5.6: LibreOffice discovery** between the post-activation smoke test (step 5.5) and the package install marker check (step 6). The step checks `command -v soffice`. If soffice is missing, and the user is on macOS (`uname -s` == Darwin) with `/Applications/LibreOffice.app/Contents/MacOS/soffice` present and executable, it writes a 2-line bash wrapper shim into `${CONDA_PREFIX}/bin/soffice` that `exec`s the real binary. The heredoc delimiter is quoted (`<<'DEBRIEF_SOFFICE_SHIM_EOF'`) so variable expansion is disabled and the hardcoded path lands verbatim. If LibreOffice is not installed at all, the step exits 1 (not 2 — this is a missing system dep, not env corruption per §9.3.1) with platform-specific install instructions pointing at libreoffice.org/download, `brew install --cask libreoffice` on macOS, and `apt install libreoffice` / `dnf install libreoffice` on Linux.
- Blueprint: **BC-1.6** is amended to remove the `libreoffice-still` requirement. New **BC-1.6a** requires `bin/debrief` to run the discovery step at the §24.4 step 5.6 position, mandates the `${CONDA_PREFIX}/bin/soffice` shim on macOS, and fixes exit code 1 for the missing-install branch.
- Spec: §9.3 dependency list no longer lists `libreoffice-still`; §9.3.1 documents LibreOffice as a system dep and cross-references BC-1.6a; §24.25.1 replaces "LibreOffice is guaranteed by the conda environment" with the new discovery-and-shim model.
- README: `libreoffice-still` removed from the conda packages table; a new "System dependencies" subsection lists LibreOffice with per-platform install instructions.
- `tests/unit_1/test_scaffold.py`: `test_environment_yml_includes_libreoffice_still` was inverted to `test_environment_yml_does_not_pin_libreoffice_still`, keeping the BC-1.6 → BUG-AUDIT-4 traceability and preventing accidental reintroduction.
- New regression tests in `tests/regressions/test_bug_audit_4_libreoffice.py` cover: absence of `libreoffice-still` from `environment.yml`, presence of the discovery sentinels in `bin/debrief`, the `command -v soffice` check, the macOS shim creation (paths + `chmod +x`), the quoted heredoc delimiter, the install-instructions messages, `exit 1` (not `exit 2`) for missing install, and a source-order invariant that pins the discovery block between the smoke test and the pip install marker check.

**Behavioral change for Linux users.** Before this fix, `conda env create` would install LibreOffice automatically on Linux via `libreoffice-still`. After this fix, Linux users must install LibreOffice via their distro package manager before running `debrief new`. The discovery step detects the omission and exits with instructions. This is a minor user-experience regression on Linux, justified by the need to keep the env-setup path uniform across platforms and by the fact that `libreoffice-still` on conda-forge is Linux-only maintained and has historically lagged behind distro packages.

**User recovery.** No conda state cleanup needed — the failed `debrief new` did not create any env. After the fix lands and `bin/debrief` is updated via the existing symlink, the user re-runs `debrief new` from the project directory. The discovery step finds the existing `/Applications/LibreOffice.app/Contents/MacOS/soffice`, writes the shim, and the bootstrap proceeds through steps 6–10 normally.

### BUG-AUDIT-5: `bin/debrief` step 10 uses `claude --plugin` but the CLI flag is `--plugin-dir`

**Symptom.** After BUG-AUDIT-4 landed, the user ran `debrief new` on macOS. Every step of the spec §24.4 bootstrap completed successfully — conda env created, pip deps installed, env activated, smoke test passed, LibreOffice discovery ran, `pip install -e` of the Debrief Python package succeeded, Playwright Chromium downloaded (170 MB), vendor hash preflight ran, `python -m debrief.launcher new "$(pwd)"` prompted for archetype selection and wrote `deck_state.json` / `debrief_state.json` / project `CLAUDE.md`. The final line of `bin/debrief` then failed:

```
error: unknown option '--plugin'
```

`bin/debrief` step 10 was `exec claude --plugin "$CLAUDE_PLUGIN_ROOT"`. The Claude Code CLI has no `--plugin` flag. The correct flag is `--plugin-dir`, which loads plugins from the specified directory for a single session.

**Root cause.** `claude --help` shows:

```
--plugin-dir <path>   Load plugins from a directory for this session only
                      (repeatable: --plugin-dir A --plugin-dir B) (default: [])
```

The pre-BUG-AUDIT-1 thin shim invoked `exec claude --plugin "$PLUGIN_ROOT" "$@"`. When BUG-AUDIT-1 rewrote `bin/debrief` to implement the full 10-step bootstrap, the launch line was preserved verbatim on the assumption that the old shim at least launched Claude Code correctly. It did not — the flag had never been valid. BUG-AUDIT-1 was never manually verified end-to-end against a real Claude Code installation because the user was hitting earlier-stage failures (missing conda env, wrong plugin root, missing LibreOffice binaries). Subsequent audits (BUG-AUDIT-2/3/4) touched other parts of the wrapper and also never exercised the launch. The BUG-AUDIT-1 regression test `test_bin_debrief_launches_claude_with_plugin` was written to assert the literal string `exec claude --plugin "$CLAUDE_PLUGIN_ROOT"`, so it codified the bad flag as the required invocation — the test passed even though the flag was wrong, because the test checked for string presence, not runtime behavior.

**Detection method.** User ran `debrief new` on `Darwin x86_64` from `/Users/cfusco/Nextcloud/work/lab_meetings/20260421_Lab_meeting` on 2026-04-13 after BUG-AUDIT-4 landed. The transcript showed the complete spec §24.4 step 1–9 sequence succeeding, the archetype selection prompt, and then a terminal `error: unknown option '--plugin'` from the Claude Code CLI. The user pasted the full transcript. `claude --help` confirmed `--plugin-dir` as the correct flag; the claude-code-guide agent confirmed via `code.claude.com/docs/en/cli-reference.md` that `--plugin-dir` expects the plugin directory itself (containing `.claude-plugin/plugin.json`), which is exactly what `$CLAUDE_PLUGIN_ROOT` resolves to in our wrapper.

**Fix summary.**

- `src/unit_1/bin/debrief` step 10 launch lines (both the `new)` arm and the bare `"")` arm of the step 9 subcommand dispatch) changed from `exec claude --plugin "$CLAUDE_PLUGIN_ROOT"` to `exec claude --plugin-dir "$CLAUDE_PLUGIN_ROOT"`.
- Blueprint **BC-1.16** step 10 wording updated to require `--plugin-dir`. An explanatory parenthetical was added noting the flag name and that `--plugin` is not a valid option, referencing BUG-AUDIT-5.
- BUG-AUDIT-1 regression test `test_bin_debrief_launches_claude_with_plugin` renamed to `test_bin_debrief_launches_claude_with_plugin_dir` and retargeted to expect the correct flag. The assertion message explicitly references BC-1.16, §24.4 step 10, and BUG-AUDIT-5 so that a future regression surfaces the right context.
- New regression tests in `tests/regressions/test_bug_audit_5_plugin_dir_flag.py` cover: (a) positive assertion that the `--plugin-dir` invocation with `$CLAUDE_PLUGIN_ROOT` appears, (b) **negative sentinel** that the bare `--plugin` flag (literal `--plugin` followed by a space, distinguishing it from `--plugin-dir`) does NOT appear anywhere in `bin/debrief`, and (c) that the `--plugin-dir` invocation appears exactly twice in the file (once per dispatch arm in step 9). The negative sentinel is the key regression-prevention: any future edit that reverts to `--plugin` fails this test loudly.

**Historical note on other Bug Catalog entries.** BUG-AUDIT-1's and BUG-AUDIT-3a's entries above contain quoted prose references to `exec claude --plugin "$CLAUDE_PLUGIN_ROOT"`. Those quotes are historically accurate — the original pre-BUG-AUDIT-1 shim really did contain `--plugin`, and my BUG-AUDIT-1 rewrite preserved that line verbatim. The quoted strings in BUG-AUDIT-1 and BUG-AUDIT-3a reflect the state of `bin/debrief` at the time those audits landed; I am not rewriting them to preserve the audit trail. BUG-AUDIT-5 is the entry in which the wrong flag is finally identified and fixed.

**Why this slipped through 4 audits.** End-to-end functional verification of the launch step requires a real Claude Code installation and a real plugin. The workspace test suite cannot exercise this — tests can only check that certain strings appear in the bash source. Once the string-presence test pinned the wrong flag, the feedback loop was closed and the bug was invisible to automation. The lesson: structural tests are necessary but not sufficient for commands that execute external programs. Manual end-to-end verification against the real CLI is the only way to catch "valid string, invalid behavior" bugs. Future audits touching `bin/debrief`'s launch step SHOULD include a manual `debrief new` run on both macOS and Linux before declaring the fix complete.

**User recovery after the fix lands.** The user's previous run created a valid Debrief project at `/Users/cfusco/Nextcloud/work/lab_meetings/20260421_Lab_meeting` (deck_state.json and friends were written before the exec failed). The next invocation should be a bare `debrief` (no `new`) from that same directory. The bootstrap will short-circuit steps 4, 6, and 7 thanks to the marker files cached during the previous run, so it should take ~5–10 seconds end-to-end and finally `exec claude --plugin-dir` into a Claude Code session with the Debrief plugin loaded.

### BUG-AUDIT-6: `plugin.json` schema validation — `author` must be object, `skills`/`agents`/`hooks` must not be string paths

**Symptom.** After BUG-AUDIT-5 landed and the user re-ran `debrief` bare, `bin/debrief` successfully launched `claude --plugin-dir` pointing at the delivered plugin directory. Claude Code discovered the plugin but the `/plugin` UI reported:

```
inline[0] Plugin · unknown · ✘ failed to load · 1 error

Failed to load plugin: Plugin debrief has an invalid manifest file at
.../debrief1.0-repo/debrief/.claude-plugin/plugin.json.

Validation errors: author: Invalid input: expected object, received string,
                   agents: Invalid input  [truncated]
```

No `/debrief:*` slash commands were available because the plugin never loaded. The launch itself was correct — this is a manifest schema violation, not a launch issue.

**Root cause (two sub-defects).**

**BUG-AUDIT-6a: `author` is a string.** The committed `plugin.json` had `"author": "Carlo Fusco and Leonardo Restivo"`, a plain string. Claude Code's plugin manifest schema (per `code.claude.com/docs/en/plugins-reference.md`) requires `author` to be an **object** with optional fields `name`, `email`, `url`. The Zod validator rejects the string form outright. This is a direct schema violation.

**BUG-AUDIT-6b: `skills`, `agents`, `hooks` declared as string paths.** The committed `plugin.json` also had `"skills": "./skills/"`, `"agents": "./agents/"`, `"hooks": "./hooks/hooks.json"`. Claude Code **auto-discovers** skills, agents, and hooks from default subdirectories at the plugin root (`./skills/`, `./agents/`, `./hooks/hooks.json`). The manifest schema does NOT accept string-path pointers for these fields. The `hooks` field is accepted only as an inline object (not relevant here). The `skills`, `agents`, `commands` fields must be entirely absent from the manifest — attempting to declare them as string paths causes Zod validation failure.

**Internal evidence the correct schema was known.** `scripts/structural_check.py:570-631` defines `generate_plugin_json()`, the Stage 5 assembly-time generator for plugin manifests. It contains an explicit comment:

```python
# NOTE (Bug S3-43): agents, commands, skills are auto-discovered by
# Claude Code from the plugin directory structure. Including them as
# string paths causes the Zod schema validator to reject the manifest.
# hooks is only valid as an inline object, not a string path.
_AUTO_DISCOVERED = {"agents", "commands", "skills"}
```

The generator excludes `agents`/`commands`/`skills` from the output. But the generator was never re-run against the committed `plugin.json` — the static file at `src/unit_1/.claude-plugin/plugin.json` and its delivered copy `debrief1.0-repo/debrief/.claude-plugin/plugin.json` was hand-authored (or generated by an older pre-S3-43 generator) and never updated. The runtime generator and the static committed manifest diverged. Claude Code loads the static file, not whatever `generate_plugin_json()` would produce.

Additionally, `spec/stakeholder_spec.md:292-313` (§4 Plugin Manifest) had `author` correct (object form) but still showed `skills`/`agents`/`hooks` as string paths — the spec's own example has been broken since Stage 5, and BC-1.1 in the blueprint enforced the broken shape explicitly. BC-1.2, BC-1.3, BC-1.4 further pinned the wrong manifest pointer requirements.

**Detection method.** User launched `debrief` on macOS after BUG-AUDIT-5 landed. Claude Code opened, no `/debrief:*` commands appeared, user ran `/plugin` and reported: `inline[0] Plugin · unknown · ✘ failed to load · 1 error`. User drilled into the Errors tab and pasted the validation errors verbatim. Cross-referenced with `code.claude.com/docs/en/plugins-reference.md` (via the claude-code-guide agent) to confirm the required schema. Additional internal evidence found in `scripts/structural_check.py` confirming the project already knew about this class of error but the static file was never updated.

**Fix summary.**

- `src/unit_1/.claude-plugin/plugin.json` rewritten to the minimal valid shape: `name`, `version`, `description`, `author` (as `{"name": "..."}`), `license`, `keywords`. The `skills`, `agents`, `hooks` fields are removed entirely. Claude Code auto-discovers those from their default paths.
- `debrief1.0-repo/debrief/.claude-plugin/plugin.json` synced byte-for-byte from the workspace.
- Spec §4 updated to show the corrected minimal manifest and to explicitly document that skills / agents / hooks are auto-discovered and MUST NOT be declared as string paths.
- Blueprint **BC-1.1** rewritten: required top-level keys are `name`, `version`, `description`, `author`, `license`, `keywords`. `author` MUST be an object with at least a `name` field. Forbidden top-level keys: `skills`, `agents`, `hooks`, `commands` (all cause Zod validation failure when present).
- Blueprint **BC-1.2** reframed: requires the `skills/` directory at the plugin root with exactly the nine expected subdirectories; no manifest pointer is expected.
- Blueprint **BC-1.3** reframed: requires the `agents/` directory at the plugin root; no manifest pointer is expected.
- Blueprint **BC-1.4** reframed: requires `hooks/hooks.json` at the plugin root with the PreToolUse/PostToolUse declarations; no manifest pointer is expected.
- `tests/unit_1/test_scaffold.py` (both workspace and delivered copies) updated: `REQUIRED_PLUGIN_JSON_KEYS` set to the new six-key whitelist; a new `test_plugin_json_author_is_object_with_name` test added; the three `test_*_field_points_to_*_directory` tests (skills, agents, hooks) removed; the surrounding directory-existence and subdirectory-listing tests kept unchanged. Edits applied via the Edit tool per-site (not whole-file cp) because workspace and delivered have intentionally different path helpers.
- New regression tests in `tests/regressions/test_bug_audit_6_plugin_json_schema.py` cover: valid JSON parse, `author` is an object with a `name` field, negative sentinels that `skills`/`agents`/`hooks`/`commands` are absent as top-level keys, positive top-level-keys whitelist derived from the authoritative schema, `name == "debrief"`, `version` matches SemVer, and that `skills/` / `agents/` / `hooks/hooks.json` directories-and-file exist at the default paths.

**User recovery.** No cleanup needed. After the fix is synced and committed, re-run `debrief` bare from the lab_meeting project directory. Bootstrap short-circuits through cached markers (~5 seconds), Claude Code opens, `/plugin` UI shows `debrief · ✔ enabled`, and `/debrief:*` slash commands appear in `/help`.

### BUG-AUDIT-7: `hooks.json` missing top-level `hooks` record and matcher-wrapper shape

**Symptom.** After BUG-AUDIT-6 landed and the user re-ran `debrief` bare, `plugin.json` now loaded successfully — but Claude Code then failed to load the hooks:

```
Failed to load hooks from .../debrief1.0-repo/debrief/hooks/hooks.json: [
  {
    "expected": "record",
    "code": "invalid_type",
    "path": ["hooks"],
    "message": "Invalid input: expected record, received undefined"
  }
]
```

The plugin still did not load fully; no `/debrief:*` slash commands were available.

**Root cause.** The committed `hooks.json` (at `src/unit_1/hooks/hooks.json` and `debrief1.0-repo/debrief/hooks/hooks.json`) had event keys (`PreToolUse`, `PostToolUse`) as top-level keys directly, with each event mapping to a flat array of records containing `matcher`, `type`, `command`/`prompt`, and `timeout` fields:

```json
{
  "PreToolUse": [
    { "matcher": "Write|Edit", "type": "command", "command": "...", "timeout": 10 }
  ],
  "PostToolUse": [
    { "matcher": "Write|Edit", "type": "agent", "prompt": "...", "timeout": 60 }
  ]
}
```

Claude Code's actual schema (per `code.claude.com/docs/en/plugins-reference.md`) requires:

1. A top-level `"hooks"` record wrapping the event map. The committed file had no top-level `hooks` key at all — hence the Zod error `expected record, received undefined` at path `["hooks"]`.
2. Each event's array is a list of **matcher wrappers**. Each matcher wrapper is an object with a `matcher` string field and a nested `hooks` array. The nested array contains individual hook handlers (`type`, `command`/`prompt`, `timeout`). The flat handler-per-matcher shape the committed file used is NOT a valid layout at all.

**Internal evidence this was known.** Spec §7.1 (`spec/stakeholder_spec.md:509-540`) already shows the correct Form B verbatim. The committed file diverged from the spec's own example. Additionally, `tests/unit_1/test_scaffold.py:681-708`'s `_get_hooks_by_event` helper has explicit branches for the nested form, commenting "Each element may itself be a wrapper with a nested `hooks` list" — proving the test authors knew about the correct shape but never actually rewrote the committed `hooks.json` file. Same divergence pattern as BUG-AUDIT-6 (`plugin.json`): the spec and tests knew, but the static file was never updated.

**Why this surfaced after BUG-AUDIT-6 and not before.** Claude Code loads `plugin.json` first; if it fails, the plugin is rejected before any other components are considered. BUG-AUDIT-6 fixed `plugin.json`, so Claude Code proceeded to load hooks, which is the next validation step. This bug was always going to be the next error after the plugin.json fix. The audits did not anticipate it because each audit was triggered by the user running `debrief` and reporting the visible error; each time we fixed the current blocker and moved forward, exposing the next latent bug in the loading pipeline.

**Detection method.** User launched `debrief` bare after BUG-AUDIT-6 landed and pasted the full `/plugin` error transcript from a terminal on 2026-04-13. Validation error message was specific enough to identify the missing top-level key and the required Zod shape (`record` at path `["hooks"]`). Cross-verified with the claude-code-guide agent against `code.claude.com/docs/en/plugins-reference.md` and against the project's own spec §7.1 example.

**Fix summary.**

- `src/unit_1/hooks/hooks.json` rewritten to Form B exactly as spec §7.1 documents: a top-level `hooks` record, each event (`PreToolUse`, `PostToolUse`) an array of matcher wrappers, each wrapper containing a `matcher` string and a nested `hooks` array of handlers. The PreToolUse command content (`${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth`, timeout 10) and the PostToolUse inline prompt and timeout 60 are preserved verbatim.
- `debrief1.0-repo/debrief/hooks/hooks.json` synced byte-for-byte from the workspace copy.
- Blueprint **BC-1.4** (last touched in BUG-AUDIT-6) extended with explicit structural requirements: single top-level `hooks` record; inner record keyed by valid Claude Code event names; each event value is a list of matcher wrappers with `matcher` (string) + `hooks` (array) fields; each inner hook has `type` plus handler-specific fields. The contract explicitly cites spec §7.1 as the canonical shape and BUG-AUDIT-7 as the detection reference.
- `tests/unit_1/test_scaffold.py` updated in two sites (workspace and delivered copies, via targeted Edit — not whole-file cp, because the files have intentionally different path helpers): (a) `_get_hooks_by_event` helper now merges the outer wrapper's `matcher` field into each unwrapped inner hook so that existing matcher assertions continue to pass; (b) `test_hooks_json_declares_pre_tool_use_hook` switched from a bespoke top-level-key check to `_get_hooks_by_event(hooks_json, "PreToolUse")` — simpler and layout-agnostic.
- New regression tests in `tests/regressions/test_bug_audit_7_hooks_json_schema.py` cover: valid JSON parse, top-level `hooks` key presence and shape, negative sentinel that no event keys appear at the top level (catches regressions to the old flat layout), inner record validation, matcher-wrapper shape for both `PreToolUse` and `PostToolUse`, matcher value `"Write|Edit"`, PreToolUse inner-hook type/command/timeout values, PostToolUse inner-hook type/prompt/timeout values, and a redundant assertion specifically naming the `expected record, received undefined` error for future audit traceability.

**User recovery.** No state cleanup needed. After the fix is synced and committed, re-run `debrief` bare from the lab_meeting project directory. Bootstrap short-circuits through cached markers, Claude Code opens, `/plugin` UI now shows `debrief · ✔ enabled` with no hooks error, `/debrief:*` skills appear in `/help`.

### BUG-AUDIT-8: skills register as bare `/export`, `/save`, `/quit` and collide with Claude Code built-ins; project scoping is implicit-via-wrapper rather than explicit-via-settings

**Symptom.** After BUG-AUDIT-7 landed, `debrief` launched Claude Code with the plugin loaded via `claude --plugin-dir <plugin_root>`. The `/plugin` UI showed `debrief · ✔ enabled` and all 9 skills registered. But typing `/export` produced two autocomplete entries — Claude Code's built-in `/export` and our debrief skill, also bare-named `/export`. The same collision applied to `/save` (likely a built-in) and `/quit` (definitely a built-in). The user expected namespaced commands like `/debrief:export`, `/debrief:save`, `/debrief:quit` to avoid collisions and to make the skill source obvious.

The user also explicitly raised a separate concern: they wanted the debrief plugin to be active **only** in deck project directories, not in every Claude Code session on their machine. Under BUG-AUDIT-1..7 this was implicit — the `bin/debrief` wrapper had to be invoked manually from a project directory, which acted as a de-facto scope guard. But the user wanted explicit, documented project-scoping rather than relying on the wrapper convention.

**Root cause.** Two coupled architectural problems with the `--plugin-dir` load path:

1. **`--plugin-dir` skips marketplace registration.** Claude Code's plugin namespacing (`/<plugin-name>:<skill-name>`) requires the plugin to be loaded via the marketplace machinery — `/plugin marketplace add` plus `/plugin install <name>@<marketplace>`, OR the project-scoped equivalent in `.claude/settings.json`. The `--plugin-dir` flag is a session-scoped dev shortcut that loads plugin components but does NOT register the plugin in the marketplace context, so skills register with bare names. This is documented behavior at `code.claude.com/docs/en/plugins.md` — the namespacing guarantee specifically applies to marketplace-installed plugins.
2. **Project scoping was implicit.** The `bin/debrief` wrapper made plugin activation feel project-scoped because the user had to `cd` into a project before invoking it, but Claude Code itself had no record of which directories were debrief projects. There was no way to launch Claude Code directly (without the wrapper) and get debrief active in some directories and absent in others.

The right architecture, per the authoritative docs at `code.claude.com/docs/en/settings.md`, is to use a project-scoped `.claude/settings.json` file in each deck project directory. This file declares an `extraKnownMarketplaces` entry pointing at the local `debrief1.0-repo/` marketplace root and an `enabledPlugins` entry enabling `debrief@debrief`. When Claude Code is launched from such a directory, it auto-discovers the settings file, registers the marketplace, enables the plugin, and namespaces skills correctly. In any other directory, the file is absent and debrief is not loaded.

The `--plugin-dir` load path used in BUG-AUDIT-1..7 was a workaround for a problem (lack of project-scoped enablement) that Claude Code already had a documented solution for. We adopted the wrong tool first and only switched after the namespacing collision surfaced.

**Detection method.** User pasted the autocomplete output from a live Claude Code session showing `/export` resolving to two entries: Claude Code built-in plus debrief skill, both bare-named. Cross-verified the namespacing rules with the claude-code-guide agent against `code.claude.com/docs/en/plugins.md` and `settings.md`. Confirmed that project-scoped `.claude/settings.json` produces both project-scoped activation AND automatic namespacing in a single mechanism.

**Fix summary.**

- New public function `ensure_project_settings(project_root, plugin_root)` added to `src/unit_3/launcher.py`. The function creates `.claude/settings.json` in a project directory if absent, or updates only the `extraKnownMarketplaces.debrief` and `enabledPlugins["debrief@debrief"]` keys if present. Marketplace path is computed as `plugin_root.parent.resolve()` (the absolute, symlink-resolved path of `debrief1.0-repo/`, the directory containing `.claude-plugin/marketplace.json`). The function is idempotent, preserves unrelated keys, recovers from corrupt JSON, and self-heals stale marketplace paths when the user moves the debrief repo on disk. Documented as **BC-3.13** in the blueprint.
- `new()` (the project initializer in `debrief.launcher`) now calls `ensure_project_settings` as its final step, after `render_project_claude_md`. Newly created deck projects ship with `.claude/settings.json` ready to go.
- `main_new()` (the `python -m debrief.launcher` dispatcher) gained a new `ensure_settings` subcommand arm that calls `ensure_project_settings(project_root, plugin_root)`. This is the entry point `bin/debrief` uses for self-healing existing projects.
- `bin/debrief` step 9 + 10 rewritten:
  - The `new` arm calls `python -m debrief.launcher new "$(pwd)"` (which now also writes `.claude/settings.json` via the integration above) and then `exec claude` (no flags).
  - The bare `""` arm checks for `deck_state.json`, then calls `python -m debrief.launcher ensure_settings "$(pwd)"` to self-heal the settings file (creates it if missing, refreshes the marketplace path if stale), then `exec claude` (no flags).
  - Both `exec claude` invocations no longer pass `--plugin-dir` because Claude Code auto-discovers `.claude/settings.json` from the current working directory.
- Spec §9.4 step 7 / §24.4 step 9 amended to document that `bin/debrief new` writes `.claude/settings.json` and that bare `bin/debrief` self-heals it. Spec §9.4 step 8 / §24.4 step 10 amended to drop `--plugin-dir` from the launch invocation. New §24.5 area subsection added documenting the project-scoped settings file format.
- Blueprint **BC-1.16** step 9 amended to require both the launcher-side settings write (new arm) and the self-heal call (bare arm). BC-1.16 step 10 amended to require `exec claude` with no flags. New **BC-3.13** added documenting the `ensure_project_settings` contract.
- BUG-AUDIT-1's `test_bin_debrief_launches_claude_with_plugin_dir` retargeted to expect the plain `exec claude` form; renamed `test_bin_debrief_launches_claude_no_flags`. BUG-AUDIT-5's three tests inverted: they now assert `exec claude` (plain), forbid `--plugin-dir`, and check exact-count of plain `exec claude` in both dispatch arms. The bare `--plugin` negative sentinel is preserved (still wrong) and joined by a new `--plugin-dir` negative sentinel.
- New regression tests in `tests/regressions/test_bug_audit_8_project_settings.py` covering: bin/debrief launch shape (plain `exec claude`, no `--plugin-dir`), `ensure_settings` call presence, function existence and signature, functional behavior (creates `.claude/settings.json`, writes correct marketplace path and enabledPlugins entry, idempotent, preserves unrelated keys, updates stale paths, recovers from corrupt JSON), AST-level `main_new` dispatch wiring, and AST-level confirmation that `new()` calls `ensure_project_settings`.

**Why this supersedes BUG-AUDIT-5 instead of layering on top.** BUG-AUDIT-5 fixed the wrong CLI flag (`--plugin` → `--plugin-dir`) for the load path we were using at the time. BUG-AUDIT-8 retires that load path entirely. The BUG-AUDIT-5 regression tests pinned `--plugin-dir` as required, so they need to be inverted as part of this fix. BUG-AUDIT-5's lesson — "structural string tests are insufficient for command invocations against external programs" — is still valid and is reinforced here: if we had end-to-end tested the slash command namespacing before declaring BUG-AUDIT-5 done, we'd have caught this two audits earlier.

**User recovery.** No conda or project state cleanup needed. After the fix is synced and committed, re-run `debrief` bare from `/Users/cfusco/Nextcloud/work/lab_meetings/20260421_Lab_meeting`. Bootstrap short-circuits through cached markers; bin/debrief calls `ensure_settings`, which writes `.claude/settings.json`; `exec claude` opens with project-scoped settings; `/plugin` shows `debrief · ✔ enabled` (loaded via marketplace this time, not inline); `/export` autocompletes to **two entries** — Claude Code built-in `/export` AND namespaced `/debrief:export` — but the user can pick the namespaced one unambiguously. In any other directory, `claude` opens with no debrief components at all.

### BUG-AUDIT-9: debrief skills register as bare `/slide`, `/save`, `/export` instead of namespaced `/debrief:*` — `commands/` is required for namespacing, not `skills/` (documentation only; code fix pending)

**Symptom.** After BUG-AUDIT-8 fixed project-scoped plugin enablement, the debrief plugin loads via the marketplace mechanism and appears in `/plugin` as `✔ enabled`. But when the user types `/debrief:` in the session, autocomplete shows:

```
/quit                      (debrief) Save state, clean up transient artifacts, and exit the session cleanly.
/view                      (debrief) Generate a query-driven HTML view of selected slides for visual inspection.
/save                      (debrief) Checkpoint the current deck state and ledger to a named snapshot.
/slide                     (debrief) Enter the slide authoring loop. Creates new slides or opens visual revision for existing ones.
/style                     (debrief) Run the style dialog to co-design and lock the visual style for the deck.
/reset                     (debrief) Delete all project data files and return the project directory to its initial empty state.
```

The commands register with **bare names** (`/quit`, `/view`, `/save`, `/slide`, `/style`, `/reset`, plus `/export`, `/script`, `/handout`) — the `(debrief)` annotation tells the user which plugin owns them, but the actual invocation syntax has no `/debrief:` prefix. Three of the nine names (`export`, `save`, `quit`) collide with Claude Code built-ins: typing `/export` shows two autocomplete entries that look identical except for the `(debrief)` annotation, forcing manual disambiguation on every invocation.

The entire goal of BUG-AUDIT-8 — installing the plugin via marketplace so that Claude Code's namespacing logic would produce `/debrief:export` and eliminate collisions — is defeated.

**Root cause (empirical).** Claude Code's plugin loader treats the `commands/` and `skills/` plugin subdirectories with different namespacing rules, contrary to what the `code.claude.com/docs/en/plugins.md` documentation claims.

- **`commands/` plugin subdirectory**: flat `.md` files produce **namespaced** slash commands of the form `/<plugin>:<name>`. File naming convention is `<plugin>_<name>.md` (plugin-prefixed). File content is plain markdown — no YAML frontmatter required — and begins with a `# /<plugin>:<name>` heading.
- **`skills/<name>/SKILL.md` plugin subdirectory**: nested-directory layout with YAML frontmatter containing `name`, `description`, `user-invocable: true`, `allowed-tools`, `argument-hint`, etc. Files register as **bare-named** slash commands (no `/<plugin>:` prefix), even when `user-invocable: true` is set in the frontmatter.

The docs page `plugins.md` explicitly says "Plugin skills use a `plugin-name:skill-name` namespace, so they cannot conflict with other levels." Empirically, in Claude Code v2.1.104, this guarantee does NOT hold for the `skills/` plugin subdirectory — it only holds for `commands/`.

**Empirical verification.** This diagnosis was confirmed by comparing two sibling plugins installed under identical conditions on the same machine during this audit:

- **svp** (Stratified Verification Pipeline, installed at user scope) uses `commands/svp_<name>.md` with flat files, no frontmatter, and `# /svp:<name>` headings. Its slash commands register as `/svp:bug`, `/svp:save`, `/svp:clean`, `/svp:quit`, etc. — all namespaced. The user can type `/svp:bug` and the command resolves unambiguously.
- **debrief** uses `skills/<name>/SKILL.md` with nested directories and full YAML frontmatter. Its slash commands register as bare `/slide`, `/save`, `/export`, `/quit`, etc. Typing `/debrief:` in the autocomplete panel filters to debrief-annotated entries (probably by matching the `(debrief)` annotation substring), but the actual invocation syntax omits the prefix.

Both plugins are loaded by the same Claude Code version (2.1.104), via the same marketplace-plus-project-scoped-settings mechanism established in BUG-AUDIT-8, with identically minimal `plugin.json` shape (`name`, `version`, `description`, `author`-as-object, `license`, `keywords`). The only difference in their plugin-level layout is `commands/` vs. `skills/`. That difference is what produces namespacing vs. bare-naming.

**svp's `skills/` directory — for contrast.** svp has a single `skills/orchestration/` subdirectory that is **not** a user-invocable slash command. It is a model-auto-invoked knowledge capability that Claude loads contextually when SVP-related tasks arise. This confirms the design intent: `skills/` is for model-auto-invoked capabilities; `commands/` is for user-invoked slash commands. debrief's 9 user-facing workflows all belong in `commands/`, not `skills/`. The distinction is load-bearing even though the docs blur it.

**Docs / guide divergence.** Multiple queries to the `claude-code-guide` subagent during this audit returned contradictory answers. One call asserted skills ARE automatically namespaced per `plugins.md` and directed us to keep the `skills/` layout. The same call then failed to explain why debrief's `skills/` plugin was producing bare-named commands. Take-away for future audits: the Claude Code docs describe intended behavior, not observed behavior, for plugin namespacing. Always test against a known-working sibling plugin (svp is the canonical reference in this workspace) before trusting docs on plugin loader semantics.

**Detection method.** User verified the namespacing failure on 2026-04-14 by typing `/debrief:` in a lab_meeting Claude Code session and pasting the autocomplete output. Cross-verified against svp's `commands/` layout by inspecting `commands/svp_bug.md`, `commands/svp_save.md` — both plain markdown, no frontmatter, `# /svp:<name>` headings. Confirmed the directory structure and file naming convention by listing `svp2.2-pass2-repo/svp/commands/` (11 flat `.md` files, all `svp_<name>.md`) and `svp2.2-pass2-repo/svp/skills/` (one subdirectory `orchestration/`, not a slash command).

**Fix approach (documentation-only in this entry; code migration is deferred to a separate pass).**

The code fix is to migrate all 9 debrief user-invocable workflows from `skills/<name>/SKILL.md` to `commands/<name>.md`, matching svp's proven layout:

1. **Delete** `src/unit_1/skills/<name>/SKILL.md` and the 9 containing subdirectories. The `src/unit_1/skills/` directory becomes empty or absent. Future model-auto-invoked capabilities can go there if we ever need them (following svp's `skills/orchestration/` pattern).
2. **Create** `src/unit_1/commands/<name>.md` for each of the 9 workflows (`slide`, `style`, `export`, `save`, `view`, `reset`, `quit`, `script`, `handout`). Each file is plain markdown with no YAML frontmatter, a first-line `# /debrief:<name>` heading, the old `description` field as the paragraph after the heading, and the original SKILL.md body below.
3. **Rewrite** blueprint contracts BC-1.2 (discovery pointer) and delete BC-1.2a (SKILL.md frontmatter structural verification) because the frontmatter contract no longer applies. BC-1.3b (frontmatter structural verification) keeps its agent half but drops the SKILL.md half.
4. **Rewrite** spec §5 (Skill Definitions) to describe the new `commands/<name>.md` layout. The per-skill content (§5.2) moves into per-command entries. The §5.1 frontmatter-fields table is deleted.
5. **Delete** the `TestSkillsDiscoveryPointer` class and the BC-1.2a frontmatter-verification tests in `tests/unit_1/test_scaffold.py` (substantial deletions — the frontmatter verification alone is ~300 lines). Replace with a `TestCommandsDirectory` class that checks for the 9 expected `debrief_<name>.md` files with the right heading shape and the absence of YAML frontmatter.
6. **Add** a new regression test file `tests/regressions/test_bug_audit_9_commands_namespacing.py` with positive sentinels (commands/ exists, 9 files present, correct `debrief_<name>.md` naming convention, correct `# /debrief:<name>` heading shape) and a negative sentinel (no user-invocable SKILL.md files remain under skills/).
7. **Sync** to the delivered repo: delete `debrief/skills/` entirely, create `debrief/commands/` with the 9 migrated files, apply targeted Edit changes to the delivered `test_scaffold.py`.

**Example migration — `skills/slide/SKILL.md` → `commands/slide.md`.** The old file has YAML frontmatter with `name: slide`, `description: "Enter the slide authoring loop. Creates new slides or opens visual revision for existing ones."`, `user-invocable: true`, `allowed-tools: Read, Write, Edit, Bash`, `argument-hint: "[slug]"`, followed by a markdown body starting with `# /debrief:slide`. The new file is plain markdown with no frontmatter at all, starting with `# /debrief:slide`, then the description paragraph, then the original body (Behavior, Parameters). The file name encodes the plugin prefix and command name; the frontmatter fields are either redundant (the name), moved into the body (the description), or dropped entirely (allowed-tools, argument-hint, user-invocable). Use this as the canonical template for the other 8 files when the migration runs.

**Interim behavior.** Until the migration lands, debrief's bare-named commands still work. Users who want to invoke a debrief command whose name collides with a Claude Code built-in (`/export`, `/save`, `/quit`) must select the `(debrief)` entry from the autocomplete manually rather than typing the command name and pressing Enter. Non-colliding commands (`/slide`, `/style`, `/view`, `/reset`, `/script`, `/handout`) work fine with bare names — they're just not namespaced and show up in autocomplete for any project rather than only for `/debrief:` prefix searches. This is annoying but not broken; the migration can wait for a dedicated implementation pass.

**Traceability.** This BUG-AUDIT-9 entry is documentation-only. The code migration is tracked separately — when that pass lands, it should cite this entry as the diagnosis, use the example migration above as the canonical template for the other 8 files, and add the regression test described in step 6 to lock the commands/ layout against a regression to skills/.

### BUG-AUDIT-10: command filenames included the plugin prefix, producing double-prefixed invocations `/debrief:debrief_slide`

**Symptom.** After BUG-AUDIT-9 migrated the 9 user-invocable workflows to `commands/debrief_<name>.md`, typing `/debrief:` in a Claude Code session showed:

```
/debrief:debrief_view        (debrief) /debrief:view
/debrief:debrief_save        (debrief) /debrief:save
/debrief:debrief_slide       (debrief) /debrief:slide
/debrief:debrief_style       (debrief) /debrief:style
...
```

The actual registered commands were `/debrief:debrief_view`, `/debrief:debrief_save`, etc. — double-prefixed. The `(debrief) /debrief:view` annotation on the right was the description text, pulled from the first line of the file (`# /debrief:view`), not the registered command name. Users who read the annotation would assume the invocation was `/debrief:view`, but typing that produces "no match" — the real form is `/debrief:debrief_view`.

**Root cause.** BUG-AUDIT-9 assumed Claude Code would strip a plugin-name prefix from command filenames. The assumption was wrong. Claude Code's rule for `commands/<file>.md` is to register the file as `/<plugin>:<filename-stem>` — the plugin namespace is prepended from `plugin.json`'s `name` field, but no prefix is stripped from the filename. The `# /svp:bug` heading in svp's `commands/svp_bug.md` and the `# /debrief:slide` heading in debrief's `commands/debrief_slide.md` are documentation only; they do not influence registration. The actual registration uses the filename.

**Empirical verification (the same svp comparison that revealed the bug).** BUG-AUDIT-9 cited svp's `commands/svp_<name>.md` layout as the canonical working reference. Post-BUG-AUDIT-9 testing of debrief produced `/debrief:debrief_slide`, matching svp's actual behavior where typing `/svp:` shows entries like:

```
/svp:svp_bug                 (svp) /svp:bug
/svp:svp_ref                 (svp) /svp:ref
/svp:svp_quit                (svp) /svp:quit
```

svp has been silently double-prefixed all along. svp's maintainers chose to document `/svp:bug` in file bodies but the actual invocation requires typing `/svp:svp_bug`. This is a latent bug in svp that BUG-AUDIT-9 inherited by copying svp's filename convention. BUG-AUDIT-10 fixes it for debrief by dropping the prefix; svp's maintainers can make their own decision.

**Detection method.** User tested the post-BUG-AUDIT-9 state on 2026-04-14, typed `/debrief:` in a fresh Claude Code session after a cache refresh, and observed the double-prefixed entries. Confirmed against svp by typing `/svp:` in the same session — svp showed the same double-prefix pattern. Inspected svp's command files to rule out any frontmatter or heading-based command-name extraction — svp files are plain markdown with a `# /svp:<name>` heading as their first line, identical in shape to debrief's files. The ONLY difference between svp's working-as-intended (and its double-prefix behavior) and debrief's post-BUG-AUDIT-9 state is whether the user knows about the double prefix. Both plugins have the same bug; svp hides it by using `/svp:<name>` in docs and never surfacing the real `/svp:svp_<name>` form.

**Fix summary.**

- Renamed 9 files: `src/unit_1/commands/debrief_<name>.md` → `src/unit_1/commands/<name>.md` for `slide`, `style`, `export`, `save`, `view`, `reset`, `quit`, `script`, `handout`. File bodies unchanged — each still starts with `# /debrief:<name>` as its first line (now matching reality).
- Same rename applied to the delivered repo at `debrief1.0-repo/debrief/commands/`.
- Spec §5.1 (File Naming and Discovery) rewritten to state that filenames are bare `<name>.md` with no plugin prefix, and that adding a prefix produces double-prefixed invocations. Called out svp as an example of the anti-pattern rather than a canonical reference.
- Spec §5.2 per-command index updated: 9 `(file: commands/debrief_<name>.md)` references → `(file: commands/<name>.md)`.
- Spec §9.6.6 (Common mistakes) checklist augmented: the BUG-AUDIT-9 bullet now references BUG-AUDIT-10 for the filename correction, and a new BUG-AUDIT-10 bullet explicitly calls out the "filename prefix is load-bearing" anti-pattern with the svp example.
- Blueprint **BC-1.2** filename list rewritten: `debrief_slide.md`, `debrief_style.md`, etc. → `slide.md`, `style.md`, etc. The contract text explicitly says filenames MUST NOT include a plugin prefix, with a reference to BUG-AUDIT-10 for why.
- Tests updated in lockstep. `EXPECTED_COMMAND_FILES` in `tests/unit_1/test_scaffold.py` and `_EXPECTED_COMMAND_FILES` in `tests/regressions/test_bug_audit_9_commands_namespacing.py` changed from `{"debrief_slide.md", …}` to `{"slide.md", …}`. The `_COMMAND_FILE_NAME_PATTERN` regex changed from `^debrief_[a-z]+\.md$` to `^[a-z]+\.md$`. The `test_command_file_first_heading_is_namespaced` slicing logic updated. A new negative sentinel `test_no_command_files_have_plugin_name_prefix` added to the BUG-AUDIT-9 regression test file — it fails loudly if any file in `commands/` starts with `debrief_`, catching any future regression to the double-prefix layout.

**User recovery.** As with BUG-AUDIT-9, the cached plugin at `~/.claude/plugins/cache/debrief/debrief/1.1.0/` still has the BUG-AUDIT-9 (prefixed) filenames. The user must refresh the cache before testing: `claude plugin uninstall debrief@debrief --scope project && claude plugin install debrief@debrief --scope project` from the lab_meeting project directory, or wipe `~/.claude/plugins/cache/debrief/` manually. Then `debrief` bare from the project directory, and inside the new session `/debrief:` should show nine entries `/debrief:slide`, `/debrief:style`, `/debrief:export`, `/debrief:save`, `/debrief:view`, `/debrief:reset`, `/debrief:quit`, `/debrief:script`, `/debrief:handout` — no double prefix. Typing `/export` should show only Claude Code's built-in; no `(debrief)` entry, because debrief's export is now `/debrief:export` and does not collide with the built-in.

### BUG-AUDIT-11: no session-start greeting — the consultant is loaded but silent

**Symptom.** User reports: "When I start debrief, no prompt is shown to me. I had a prompt the first time I initialized the project, but then I quit due to the bug. Any subsequent call never shows the initial prompt." User runs `debrief` bare from an existing lab_meeting project directory; Claude Code opens; `@consultant` appears in the status line; the input prompt is empty; nothing greets the user. Typing `hi` produces a generic "Hello! How can I help you today?" response instead of the archetype-aware REQ-CONSULT-1 greeting.

**What the user actually saw on first run.** Not a consultant-agent greeting — the interactive **archetype selection prompt** from `src/unit_3/launcher.py:186-246` `select_archetype()`. That prompt is a Python `print()` + `sys.stdin.readline()` loop that runs during `python -m debrief.launcher new "$(pwd)"` BEFORE `exec claude`. It exits after the user picks a number (1–8) and does NOT fire on bare resume (the archetype is already stored in `deck_state.json`). The user conflated the archetype selection prompt (a pre-Claude-Code terminal dialog) with an expected consultant greeting (which was never implemented).

**Root cause (a broken chain).**

1. `src/unit_3/launcher.py:346-347` writes `debrief_state.json` with `sub_phase: "discovery/greeting"` at project-init time.
2. `src/unit_4/routing.py:62-66` maps that sub_phase to `{"action_type": "human_gate", "gate_id": "G1.1_greeting"}`. The gate is real; it's in the routing table.
3. But **nobody dispatches the gate action on session start**. There is no `SessionStart` hook in `src/unit_1/hooks/hooks.json` (only `PreToolUse` and `PostToolUse`). The project CLAUDE.md template `src/unit_1/templates/project_claude.md` does NOT tell the consultant to read state files and emit anything on session start — it just lists available commands.
4. `src/unit_1/settings.json` contains `{"agent": "consultant"}`. This makes the consultant the default agent but per Claude Code's documented behavior at `code.claude.com/docs/en/plugins.md` it does NOT auto-invoke or make the agent speak first. Agents wait for user input.
5. The user opens Claude Code via `exec claude`, sees `@consultant` in the status line, and gets an empty input prompt. The consultant is loaded and silent.
6. REQ-CONSULT-1 of this very spec says "The Consultant MUST greet the user with the archetype context already loaded" — but spec authors implicitly assumed Claude Code agents can speak first, which is false in v2.1.104.

**Comparison with SVP** (which solves this correctly). SVP's project `CLAUDE.md` has an explicit **"On Session Start"** section at the top instructing the active agent to run `python scripts/routing.py --project-root .` immediately. That instruction is read by the agent as context when CLAUDE.md auto-loads, and when the user sends any first message, the agent follows the instruction, runs the routing script, and dispatches. SVP effectively uses CLAUDE.md as an automatic first-turn dispatcher. Debrief's project CLAUDE.md has no such section — the consultant has no orchestration instructions on what to do when a session starts.

**Authoritative Claude Code constraints.** Verified via the `claude-code-guide` agent against `code.claude.com/docs/en/hooks.md` and `plugins.md`:

- `SessionStart` hook event exists. `type: "command"` injects stdout into the session as context Claude sees. `type: "agent"` spawns a subagent that returns a yes/no decision (not a visible message). Neither makes the main agent emit a message BEFORE user input.
- `settings.json` supports only `agent` and `subagentStatusLine` keys — no `initial-prompt`, `greeting`, or `kickoff` field.
- There is no built-in Claude Code mechanism for an agent to speak first in v2.1.104.

**Therefore the spec's expectation ("consultant MUST greet first") must be reconciled with reality: the greeting fires on the user's FIRST message.** The user needs to type something — even just "hi" — to trigger the consultant's first response. The consultant then reads the state files, recognizes it's in `discovery/greeting`, and emits the archetype-aware greeting.

**Detection method.** User ran `debrief` from the lab_meeting project on 2026-04-14 after BUG-AUDIT-10 landed and reported the silent session. Investigation confirmed (a) the archetype selection ran on first-run but not resume, (b) the routing table maps `discovery/greeting` to a human gate with no dispatcher, (c) no `SessionStart` hook exists, (d) the project CLAUDE.md template has no orchestration instructions, (e) `settings.json` `agent` key sets default but doesn't auto-invoke.

**Fix summary.**

- `src/unit_1/templates/project_claude.md` gains a new `## On Session Start` section (placed after the "Active Plugin" block, before "Project Context"). The section instructs the consultant to read `debrief_state.json` and `deck_state.json` as its very first action, then dispatch based on `sub_phase`:
  - `discovery/greeting` → emit the REQ-CONSULT-1 greeting with archetype context pre-loaded from `deck_state.json` and `archetypes.json`.
  - `discovery/dialog` → read the last entries of `ledger.jsonl`, summarize where the conversation left off, and ask a clarifying question.
  - `discovery/brief_review` → read `deck_brief.md` and present it for approval.
  - `style/*`, `production/*` → state-specific dispatch.
  - Other → consult the routing table in `src/debrief/routing.py`.
  The section explicitly tells the consultant to interpret a short "hi" / "start" / "begin" user message as a dispatch request, not as a request for a generic greeting.
- `src/unit_1/bin/debrief` prints a visible terminal message before `exec claude` in both dispatch arms (new and bare resume). The message is routed to stderr with `>&2`, uses box-drawing characters for visibility, and reads `Debrief ready. When Claude Code opens, say 'hi' to begin.` This cues the user that they need to type something — the greeting is not automatic.
- Spec REQ-CONSULT-1 amended with a "timing note" documenting the first-message trigger honestly and cross-referencing BUG-AUDIT-11.
- Blueprint BC-3.6 (CLAUDE.md template rendering) extended with a requirement that the rendered `CLAUDE.md` contains the `## On Session Start` section with dispatch instructions referencing `debrief_state.json`, `deck_state.json`, and the routing table. The existing `{project_name}` substitution requirement is preserved.
- `tests/unit_1/test_scaffold.py` gains assertions that the `templates/project_claude.md` file contains the `## On Session Start` heading and references `debrief_state.json`.
- New regression tests in `tests/regressions/test_bug_audit_11_session_start_greeting.py` cover: (a) template has the On Session Start section, (b) section references state files and sub_phase dispatch, (c) bin/debrief prints the greeting message before both `exec claude` calls, (d) the message is routed to stderr, (e) no `SessionStart` hook was added (we explicitly rejected that approach).

**User recovery (one-time migration).** Existing deck projects created before BUG-AUDIT-11 (the user's lab_meeting directory) have an OLD `CLAUDE.md` rendered from the pre-fix template — that file does NOT have the `## On Session Start` section. The user must manually add the section to the existing `CLAUDE.md`, OR delete the existing `CLAUDE.md` and re-run `debrief new` in the same directory to re-render from the new template (risky — may overwrite user edits). The simplest migration: copy the `## On Session Start` section verbatim from `${CLAUDE_PLUGIN_ROOT}/templates/project_claude.md` into the existing project's `CLAUDE.md`, place it near the top, then relaunch `debrief`. A future BUG-AUDIT could add an automatic migration helper that detects a missing `## On Session Start` section and offers to update the file; out of scope for BUG-AUDIT-11.

**Verification after the fix lands.** Exit Claude Code, manually add the `## On Session Start` section to the lab_meeting project's `CLAUDE.md`, run `debrief` bare. Terminal shows "Debrief ready. Say 'hi' to begin." Claude Code opens. Type `hi`. Expected: consultant reads `debrief_state.json`, sees `sub_phase: "discovery/greeting"`, reads `deck_state.json`, sees `archetype: "lab_meeting"`, and responds with something like "I see you're preparing a lab_meeting. I've set up for a 12-minute lab meeting presentation. What's the topic?" If the consultant responds with a generic greeting, the CLAUDE.md instructions aren't being loaded as context and we need to investigate further.

### BUG-AUDIT-12: two hook runtime errors during the first end-to-end verification

**Symptom.** During BUG-AUDIT-11's end-to-end acceptance test, the consultant agent attempted to save information via the Write tool ("Wrote 3 memories"). The Write succeeded, but Claude Code emitted two non-blocking hook errors each time:

```
PreToolUse:Write hook error
Failed with non-blocking status code:
  /bin/sh: /Users/cfusco/Nextcloud/coding: No such file or directory

PostToolUse:Write hook error
Failed to run: Messages are required for agent hooks. This is a bug.
```

The errors repeated three times (once per memory write). The Write operations proceeded regardless (the errors are non-blocking), but the error output cluttered the conversation UI. Two distinct failure modes requiring separate treatment.

#### BUG-AUDIT-12a: PreToolUse space-in-path (fixed)

**Root cause.** The plugin repo is installed at `/Users/cfusco/Nextcloud/coding projects/debrief1.0/debrief1.0-repo/debrief/`. The space in `coding projects/` is the problem. The `hooks.json` PreToolUse command was declared as `"command": "${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth"`. Claude Code's hook runner invokes `command`-type hooks via `/bin/sh` after expanding `${CLAUDE_PLUGIN_ROOT}`. The expansion yielded `/Users/cfusco/Nextcloud/coding projects/debrief1.0/debrief1.0-repo/debrief/bin/check-write-auth` — a path with a space — and `sh` received this as an unquoted command string. `sh` split on whitespace and interpreted `/Users/cfusco/Nextcloud/coding` as the command name (which doesn't exist) and `projects/debrief1.0/.../bin/check-write-auth` as the first argument. The `sh: ... No such file or directory` error followed.

**Detection method.** Empirical — first user writing event after BUG-AUDIT-11's verification revealed the cascading hook errors. Cross-checked `code.claude.com/docs/en/plugins-reference.md`, which shows the canonical form in its dependency-install walkthrough using escaped double quotes around `${CLAUDE_PLUGIN_ROOT}` references.

**Fix.** Wrap the command path in escaped double quotes inside the JSON string:

```json
"command": "\"${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth\""
```

The `\"` escape sequence becomes a literal `"` character in the value. When Claude Code expands the variable and passes the result to `sh`, the result is `"/Users/cfusco/Nextcloud/coding projects/.../bin/check-write-auth"` — a shell-quoted path token that survives whitespace. `sh` executes the script correctly.

**Blueprint contract amendment.** BC-1.4 now requires any `command`-type hook whose `command` field references `${CLAUDE_PLUGIN_ROOT}` or `${CLAUDE_PLUGIN_DATA}` to wrap the reference in escaped double quotes so the expansion survives whitespace. A regression test in `tests/regressions/test_bug_audit_12_hook_path_quoting.py` enforces both the positive form (the quoted version is present) and a negative sentinel (the unquoted `"command": "${CLAUDE_PLUGIN_ROOT}` form is forbidden).

**User action after the fix lands.** Refresh the plugin cache so the stale copy at `~/.claude/plugins/cache/debrief/debrief/<version>/hooks/hooks.json` is replaced. Either `claude plugin uninstall debrief@debrief --scope project && claude plugin install debrief@debrief --scope project` from the project directory, or `rm -rf ~/.claude/plugins/cache/debrief` and let Claude Code re-cache on next launch.

#### BUG-AUDIT-12b: PostToolUse "Messages are required for agent hooks. This is a bug." (upstream, not fixed on our side)

**Root cause.** The error text literally contains the phrase "This is a bug" — that's Claude Code's own developer-facing acknowledgment of an internal assertion failure. The assertion is `"Messages are required for agent hooks"`, implying Claude Code v2.1.107's hook runner expects a `messages` field in the handler that we are not providing. But the field is NOT documented.

Our `hooks.json` entry matches the documented schema at `code.claude.com/docs/en/hooks.md` verbatim:

```json
{
  "type": "agent",
  "prompt": "A file was just written or edited. Review the change...",
  "timeout": 60
}
```

The docs explicitly state that `type: "agent"` handlers require a `prompt` field (singular, not `messages`). There is no `messages` field in the documented schema. Yet Claude Code v2.1.107 raises the assertion. This is a regression in the hook runner between v2.1.104 (when BUG-AUDIT-7 wrote the current hooks.json and the test suite verified it at 1322 passing) and v2.1.107 (when the error first appeared during BUG-AUDIT-11's end-to-end test).

**Why we are NOT patching it on our side.**

1. **The hook entry is correct per documented schema.** Adding an undocumented `messages` field as a guess at what the runner wants is speculative and risks future breakage if Claude Code tightens the schema.
2. **Converting to `type: "command"` loses the agent-based visual QA** that spec §7.3 requires (REQ-SLIDE-7 specifies synchronous QA agent invocation after each slide write, not a shell-script check).
3. **The error is non-blocking.** Writes still succeed; the plugin functions normally. The error is cosmetic UI clutter.
4. **SVP sidesteps this entirely** by using only `type: "command"` hooks (verified by reading `svp/hooks/hooks.json`). SVP has no agent-type hooks, so never hits the v2.1.107 regression. Debrief cannot fully copy SVP's approach because debrief has a genuine need for agent-based post-write visual QA.

**What we DO instead.**

1. **Keep the `prompt`-based PostToolUse hook entry unchanged.** It matches documented schema. When Claude Code upstream fixes the regression, our hook will work without further changes.
2. **Document the regression** in `hooks/README.md` alongside `hooks.json` so future maintainers seeing the error don't try to "fix" it by replacing `prompt` with an undocumented `messages` array.
3. **Add a positive regression test** `test_post_tool_use_agent_hook_still_uses_prompt_field` in `test_bug_audit_12_hook_path_quoting.py` that asserts the hook still uses `prompt`, so a well-meaning future edit cannot silently remove the documented form.
4. **Users are advised** to file feedback via `/feedback` in an active Claude Code session if they encounter the error, quoting the `hooks/README.md` explanation.

**Pending upstream fix.** When Claude Code v2.1.108+ (or whichever release addresses this) arrives, the PostToolUse error will stop appearing without any plugin change. At that point, `tests/regressions/test_bug_audit_12_hook_path_quoting.py` should be revisited to add a positive runtime smoke test that confirms the hook actually produces visible output during a real Write event.

#### Verification

Test suite gains 6 new regression tests in `tests/regressions/test_bug_audit_12_hook_path_quoting.py`. Full workspace and delivered pytest runs both pass at 1378 tests. End-to-end user verification: after cache refresh and a new debrief session, writing a file triggers the PreToolUse hook cleanly (no more space-in-path error) while the PostToolUse error remains as the known upstream issue pending a Claude Code fix.

### BUG-AUDIT-13: `stylist` agent and `style_engine` disagree on `style_config.json` schema; from-scratch `/debrief:export` fails at BC-10.1 compiler step

**Symptom.** A user running the `/debrief:style` dialog from scratch (archetype `custom`, no reference file) approved the Stylist's proposed style, ran `/debrief:slide` for several slides, then ran `/debrief:export`. Export failed at BC-10.1's mandatory `style_compiler` subprocess with:

```
Style compiler failed:
ERROR: Missing required key: colors
```

No PDF was produced. The user's workaround was to skip `/debrief:export` entirely and drive Playwright + `pdfunite` directly from a hand-written script — a deep regression of the plugin's value proposition for any from-scratch dialog path.

**Root cause.** The Stylist agent had no schema guidance. `agents/stylist.md` was a 27-line stub that:

1. Contained **zero enumeration** of the canonical `style_config.json` schema — no list of required top-level keys, no CSS dot-path mapping, no `constraints`/`provenance` sub-schema guidance.
2. Was **internally contradictory**: the YAML frontmatter `description` declared the agent "produces `style_config.json` and `style_guide.md`", but the body's Constraints section said "Only write to `assets/style.css`". The two halves of the file described mutually exclusive behavior.
3. Gave the agent **no template to anchor against**. The `templates/` directory existed but contained only `project_claude.md` — there was no `style_config.json` template the agent could load and fill in.

With no schema, no template, and a contradictory instruction, the Stylist LLM reconstructed a plausible-sounding schema from memory each session. The user saw `{palette, typography, geometry, components}` — a perfectly reasonable design-document schema, but completely incompatible with `_REQUIRED_KEYS = [colors, typography, spacing, layout, data_viz, constraints, provenance]` (`src/debrief/style_engine.py`). The two schemas overlap on exactly one key (`typography`); `parse_style_config` raises `ValueError: Missing required key: colors` on the very first check.

The canonical schema is authoritative and locked down by BC-6.1–BC-6.10 and REQ-STYLE-7 provenance semantics. The compiler is correct; the Stylist was wrong.

The `paperbanana` / `style_analyzer` / reference-derivation path likely produces compiler-compatible output because the values are code-driven, which is why the bug had not been caught — it only fires on the "from-scratch dialog, no reference" path that was not covered in prior end-to-end verification.

**Detection method.** A real user hit the blocker during a `custom` archetype dialog and filed a detailed bug report at `~/Nextcloud/work/lab_meetings/leo/.debrief/bug_report_style_schema_mismatch.md`. The report traced the mismatch: what the Stylist wrote vs. what `parse_style_config` required, with exact file/line references. The report's hypothesis 1 ("the two schemas were never synced") was correct; hypothesis 3 ("the Stylist bypasses the compiler entirely") was half-correct — it bypasses in the sense of never running the compiler during synthesis, so the mismatch is silent until export time.

**Fix summary.**

1. **Ship a canonical template** at `templates/style_config.json` containing all seven top-level keys and all twenty-six `CSS_PROPERTY_MAP` dot-paths populated with sensible defaults, a non-empty `constraints.permitted_diagram_types`, and an illustrative `provenance` object. The Stylist loads this template as the starting skeleton and fills in values through the dialog rather than inventing the schema.

2. **Rewrite `agents/stylist.md`** to (a) resolve the self-contradiction (remove "Only write to `assets/style.css`" — the compiler produces `assets/style.css` from the locked config per REQ-STYLE-5), (b) enumerate the seven required top-level keys with one-line descriptions, (c) enumerate the twenty-six canonical dot-paths, (d) point to the template at `${CLAUDE_PLUGIN_ROOT}/templates/style_config.json` as the mandatory starting skeleton, and (e) reference the spec anchors (REQ-STYLE-4, REQ-STYLE-7, §24.16.1, BC-6.8) so future maintainers can find the source of truth.

3. **Amend spec** with this Bug Catalog entry, a new §24.16.1 schema-enumeration section documenting the seven required keys and twenty-six dot-paths, and a one-sentence addition to REQ-STYLE-4 requiring the Stylist to start from the bundled template.

4. **Amend blueprint** with a BC-1.3 extension requiring `agents/stylist.md` to enumerate all seven top-level keys from `_REQUIRED_KEYS` and reference `templates/style_config.json`, and a new BC-6.11 contract requiring the template file to exist, satisfy `parse_style_config`, and contain values for all twenty-six mapped dot-paths.

**Out of scope.**

- Rewriting `style_engine.py` to accept an alternative schema (`palette/geometry/components`). The canonical schema is locked by BC-6.1–BC-6.10 and REQ-STYLE-7 provenance semantics; changing it would be a deep spec revision with no benefit.
- The bug report's option 3 (gating BC-10.1 on a `hand_authored: true` flag). This is a legitimate future enhancement but requires REQ-STYLE-5 and BC-10.1 surgery; option 2 (template) is the minimal fix.
- Retroactively fixing the user's already-broken `style_config.json` on disk. The fix makes future from-scratch dialogs work; the user must regenerate their deck or keep using their Playwright helper script.
- Injecting schema guidance at `debrief.prepare` invocation time. The agent prompt is a simpler and sufficient fix; prepare-time injection would be duplicative.

**Verification.** Test suite gains a new regression file `tests/regressions/test_bug_audit_13_stylist_schema.py` with two classes covering (a) template validity — file exists, `parse_style_config` accepts it, `flatten_config` produces all twenty-six mapped keys, `compile_style` emits a valid `:root` block — and (b) `agents/stylist.md` content — enumerates all seven required keys, references `templates/style_config.json`, contains no "Only write to `assets/style.css`" legacy string (negative sentinel), references REQ-STYLE-4 or BC-6.8. The test that iterates over `_REQUIRED_KEYS` imports the list from `style_engine` directly so the test tracks drift automatically.

**User action after the fix lands.** Refresh the plugin cache (same procedure as BUG-AUDIT-12): `claude plugin uninstall debrief@debrief --scope project && claude plugin install debrief@debrief --scope project` from the project directory. Then re-run `/debrief:style` from scratch in a fresh `custom`-archetype project, approve the proposal, and run `/debrief:export`. Expected: the compiler subprocess exits 0 and a PDF is produced. **User action required** to validate the end-to-end fix — the LLM-driven Stylist path cannot be exercised from pytest alone.

### BUG-AUDIT-14: stylist schema fix (BUG-AUDIT-13) relies on the agent choosing to load the template; prepare must inject it unconditionally

**Symptom (potential, not manifested).** BUG-AUDIT-13 fixed the Stylist's system prompt (`agents/stylist.md`) to instruct the agent to `Read()` the canonical template at `${CLAUDE_PLUGIN_ROOT}/templates/style_config.json` before beginning the style dialog. That fix relies on the agent **choosing** to follow an instruction. A future LLM session could skip the Read step because it believes it remembers the schema — which is precisely how BUG-AUDIT-13 happened in the first place. The system-prompt fix leaves a "agent must choose to follow instructions" hole that an adversarial or simply forgetful LLM can still walk through.

**Root cause.** Defense-in-depth is missing. The schema guidance in `agents/stylist.md` is the only layer that tells the stylist what `style_config.json` looks like. If that one instruction is ignored, no other layer catches the mistake until `/debrief:export` fails at BC-10.1 — the exact failure mode we are supposedly now protected against.

**Fix summary.** Have the prepare module (`debrief.prepare`, backed by `src/unit_4/routing.py:main_prepare`) **paste the full template contents** directly into the stylist's `.debrief/task_prompt.md` under a `## Schema Starting Point` section containing a JSON fenced code block. The section is **prepended** to the task prompt so the stylist's first user-message turn begins with a compiler-valid schema instance already visible. No Read tool call required; no instruction to follow; the schema is physically in front of the agent on turn zero. The system-prompt guidance from BUG-AUDIT-13 stays in place — prepare-time injection is redundant-on-purpose.

**Concrete changes.**

1. `src/unit_4/routing.py` gains three symbols: `_STYLIST_ACTIONS` (frozenset of stylist-bound action IDs derived from the routing table), `_resolve_template_path(plugin_root)` (tries `plugin_root / templates / style_config.json` first, falls back to a `__file__`-relative path for tests, hard-errors if neither exists), and `_stylist_schema_section(plugin_root)` (reads the resolved template, returns a markdown section header + explanatory paragraph + JSON fenced code block).
2. `main_prepare` detects stylist-bound actions and prepends the section to the assembled task prompt before the atomic write.
3. Spec §22.8 (stylist context row) gains an entry for the injected template. Spec §24.20 (Prepare Module Contract) gains a **Stylist schema injection** paragraph with the full rule.
4. Blueprint gains new **BC-4.7b** specifying the contract, including the resolver fallback sequence, the hard-error exit code, the section layout, and the requirement that the injected JSON pass `parse_style_config` (verified at test time).
5. A new regression file `tests/regressions/test_bug_audit_14_prepare_injects_stylist_template.py` covers the stylist-action injection, negative sentinel for non-stylist actions, JSON extraction and validity, plugin_root env-var vs. source-relative resolution, and the hard-error path.

**Out of scope.**

- **Wiring up the per-agent context file list.** `main_prepare` currently passes `[]` to `assemble_task_prompt`, so the task prompt contains no `deck_brief.md`, no `references/*.md`, etc. That is a separate gap in the prepare module that is not addressed here; BUG-AUDIT-14 injects the Schema Starting Point section regardless of whether other context files are wired up.
- **Injecting schemas for other agents.** The Slide Maker and Consultant have their own context expectations that are not known to drift the way the Stylist's did. If a future bug report shows a similar failure mode for another agent, add a new injection rule for that agent following the same pattern.
- **Removing the system-prompt schema guidance in `agents/stylist.md`.** The BUG-AUDIT-13 instructions stay in place. Prepare-time injection is belt-and-suspenders over system-prompt guidance, not a replacement.
- **Validating the injected JSON at prepare time.** BC-6.11's tests already prove the template itself is compiler-valid. Calling `parse_style_config` inside `main_prepare` at runtime would couple the prepare module to the style_engine import, which is structurally undesirable. The regression test at test-time is the enforcement point.

**Verification.** Test suite gains ~10 new regression tests in `test_bug_audit_14_prepare_injects_stylist_template.py`. Workspace and delivered pytest runs both pass at 1402 (baseline 1392 + 10 new). Manual smoke test: run `python -m debrief.prepare --action style/style_dialog --project-root /tmp/smoke` and inspect `/tmp/smoke/.debrief/task_prompt.md` — expect the Schema Starting Point section at the top with a JSON block containing `"colors"`, `"typography"`, etc.

**User action after the fix lands.** The fix is transparent to users: since BUG-AUDIT-13 already fixed the system-prompt schema guidance, end-to-end behavior is unchanged. BUG-AUDIT-14 is a defense-in-depth guarantee, not a visible UX improvement. Users refreshing the plugin cache after both fixes land will pick up the combined protection. No specific user verification step is needed beyond the BUG-AUDIT-13 verification.

### BUG-AUDIT-15: project directory tree non-deterministic across init, cleanup, and re-entry; `commands/export.md` stale; deliverable-folder name LLM-proposed

**Symptom.** Three separate but related drifts in how the project directory tree and deliverable folders are produced:

1. **Init gap.** `debrief new` did not create five canonical directories from spec §3 — `.debrief/`, `.debrief/draft/`, `.debrief/draft/preview_slides/`, `.debrief/draft/preview_images/`, and `output/` (root). The Stylist agent was told to write to `.debrief/draft/preview_slides/*.html` with no mkdir instruction in its prompt and no upstream code creating the directory; success depended on Claude Code's `Write` tool implicitly mkdir-ing parents, which is non-deterministic and undocumented. The same gap left `.debrief/draft/` to be created on demand by either the reference-import code paths in `unit_7/slide_maker.py` or by the Stylist's first write — depending on whether the user provided a reference file at G1.2.

2. **Re-entry gap.** Several cleanup operations remove canonical directories during normal operation: `routing.py:701` `shutil.rmtree(.debrief/draft/)` after style lock per BC-4.6, `utility_skills.py:609` `shutil.rmtree(...)` in `skill_reset()`, and `utility_skills.py:657` `shutil.rmtree(.debrief/draft/)` in `skill_quit()` unless `retain_draft`. When the user re-enters the project (the bare `debrief` arm at `bin/debrief:224-235`), only `python -m debrief.launcher ensure_settings` ran — that subcommand self-heals `.claude/settings.json` but does not re-scaffold any directories. So a project where style-lock cleanup removed `.debrief/draft/` and the user came back to add more slides (or restart a style dialog if that flow ever lands) had a hole in its canonical tree, and any code path that needed `.debrief/draft/` either silently failed or relied on agent-side mkdir judgment.

3. **Stale skill + LLM-driven folder name.** `src/unit_1/commands/export.md` described a removed PPTX-via-LibreOffice implementation, pointed to a non-existent `exports/` directory, and did not mention the export ordering dialog or the `<YYYY_MM_DD>_<shortened_title>` proposal at all — three points of drift between the user-facing skill description and the actual `src/unit_10/export.py` (which uses Playwright directly to write `output/<presentation_folder>/deck_v{NNN}.pdf`). And the proposed `<presentation_folder>` name was generated by the Consultant LLM during the export ordering dialog: nothing in code computed the spec-canonical default; the spec's instruction "the consultant proposes a name of the form `<YYYY_MM_DD>_<shortened_title>`" was a free-text prompt the LLM was supposed to follow but nothing forced it to.

**Root cause.** Split init scope (`launcher.py:_REQUIRED_DIRS` listed only 10 of the 15 canonical directories), absent re-scaffolding hook (`bin/debrief`'s bare arm only called `ensure_settings`, not a directory-aware orchestrator), skill drift (`commands/export.md` was never updated when the export module switched from PPTX/LibreOffice to Playwright), and LLM judgment in the proposal path (the spec told the LLM what format to produce but no code ever computed the default deterministically).

**Detection method.** The user manually requested an audit of the directory tree handling after BUG-AUDIT-14 landed, prompted by the user-facing observation that the Stylist agent's `.debrief/draft/preview_*/` writes were non-deterministic. The audit was conducted via an Explore subagent that grepped for `mkdir` calls across all units, cross-referenced against spec §3, and identified the five drifting directories. Follow-up reading of `bin/debrief` confirmed the re-entry gap; reading `commands/export.md` confirmed the stale skill content; reading `routing.py` and `blueprint_prose.md` confirmed the LLM-proposal gap.

**Fix summary.**

1. **Tree existence (Legs 1–5).** Extend `src/unit_3/launcher.py:_REQUIRED_DIRS` from 10 to 15 entries — adds `.debrief/`, `.debrief/draft/`, `.debrief/draft/preview_slides/`, `.debrief/draft/preview_images/`, and `output/` explicitly. Add a new `ensure_project(project_root, plugin_root)` orchestrator function that calls `create_project_structure` then `ensure_project_settings`. Add a new `ensure_project` subcommand to `main_new`'s dispatch table. Change `bin/debrief`'s bare arm to call `python -m debrief.launcher ensure_project` instead of `ensure_settings`. The existing `ensure_settings` subcommand and `ensure_project_settings` function remain for backward compatibility. Spec §3 is rewritten to drop "transient" / "created on demand" wording for the directories that are now init-time, and a new "Directory policy" paragraph at the end of §3 makes the new contract explicit.

2. **Stale skill rewrite (Leg 6).** Replace the ~20-line `src/unit_1/commands/export.md` body with a current-truth description: Playwright PDF rendering, `output/<presentation_folder>/deck_v{NNN}.pdf` per REQ-EXPORT-3, version-within-folder for re-exports of the same presentation, new dated folder for re-presentations per REQ-LIFE-3 and §24.13, references to BC-10.1, BC-4.7c, REQ-EXPORT-1..6, §24.10, and §24.13. Removes all mention of `exports/`, `python-pptx`, and `LibreOffice`.

3. **Deterministic deliverable-folder name (Leg 7).** Add `propose_presentation_folder_name(deck_state, today=None)` to `src/unit_4/routing.py`. It returns `f"{today.strftime('%Y_%m_%d')}_{sanitize_identifier(deck_state.project_name, max_length=40)}"`, reusing the canonical `sanitize_identifier` from `src/unit_2/debrief_state.py:250` so the format is algorithmically identical to the spec §24.10.1 algorithm. Add a `_proposed_folder_section(project_root)` helper that loads `deck_state.json`, calls the propose function, and returns a `## Proposed Presentation Folder` markdown section with a fenced code block containing the computed name and an explanatory paragraph instructing the LLM to present it as the default and forbidding alternative formats. Add a `_load_deck_state_for_proposal(project_root)` helper that hard-exits with code 1 if `deck_state.json` is missing or malformed (export-dialog actions only fire after Phase 3 completes — by that time a deck must exist; missing state at this point indicates corruption). Add an `_EXPORT_DIALOG_ACTIONS` frozenset of `{finalization/export_options, finalization/export_confirm}`. Extend `main_prepare` to prepend the proposed-folder section for any action in `_EXPORT_DIALOG_ACTIONS`. Spec §24.10 is amended to lock this requirement: the proposal MUST be computed by code, not invented by the LLM. Blueprint gets a new BC-4.7c parallel to BC-4.7b.

**Blueprint contracts amended.** BC-3.9 (`_REQUIRED_DIRS` list) extended with the five new entries. New BC-3.14 specifying that `ensure_project` runs on every bare-`debrief` invocation and that the canonical tree is restored before any agent or routing cycle can begin. New BC-4.7c specifying the deterministic folder-name proposal contract.

**Out of scope.** Removing the cleanup operations themselves (intentional and orthogonal). Server-side validation of the user's confirmed/overridden folder name (input validation, not determinism — flag for a future audit if a real abuse path is found). Removing the user-override path (the user can still type a different name during the dialog; only the default is locked). Refactoring the export ordering dialog itself (only the folder-name leg is brought into the deterministic regime; slide order, separator position, and separator content remain LLM-driven content judgment calls).

**Verification.** Test suite gains ~20 new regression tests in `tests/regressions/test_bug_audit_15_canonical_tree_deterministic.py`. The existing `tests/unit_3/test_launcher.py::test_creates_all_required_subdirectories` is extended with the five new entries via its `_EXPECTED_DIRS` constant. Workspace and delivered pytest runs both pass at 1422 (baseline 1402 + 20 new). Smoke tests confirm: (a) `create_project_structure` produces all 15 directories; (b) `ensure_project` is idempotent and restores `.debrief/draft/{,preview_slides,preview_images}` after a manual cleanup; (c) `main_prepare` for `finalization/export_confirm` emits a task prompt whose first section is `## Proposed Presentation Folder` containing a date-prefixed name computed from a synthetic deck_state.

**User action after the fix lands.** Refresh the plugin cache (same procedure as BUG-AUDIT-12 / -13 / -14): `claude plugin uninstall debrief@debrief --scope project && claude plugin install debrief@debrief --scope project` from the project directory. The next bare `debrief` invocation in any existing project will automatically restore the full canonical directory tree and the lab_meetings/leo project will pick up the deterministic deliverable-folder behavior on its next export.

### BUG-AUDIT-16: vendor assets shipped as placeholder stubs AND VERSIONS.md recorded the stub hashes as if they were real

**Symptom.** A user running `/debrief:slide` during a real production session reported that slides render text labels (plain inline SVG text) but no hand-drawn shapes from rough.js. Their exact observation: *"the `<script src="../assets/vendor/rough.min.js">` loads nothing, so rough is undefined, and all the `rc.rectangle() / rc.line()` calls throw silently — no shapes ever get appended."* Text labels survived because they are SVG `<text>` elements that do not depend on any library; hand-drawn geometry vanished entirely because every rough.js method call threw on an undefined global.

**Root cause.** Two fakes compounded each other:

1. **The vendor files were one-line placeholder stubs.** Every file in `src/unit_1/assets/vendor/` (and the identical copy at `debrief1.0-repo/debrief/assets/vendor/`) contained just a comment line like `/* rough.min.js placeholder - debrief vendor asset */`. Sizes: 54-56 bytes for each `*.min.js` and `*.min.css` file; 18 bytes (`WOFF2_PLACEHOLDER`) for `katex-fonts/KaTeX_Main-Regular.woff2`. Git history shows the stubs have been in place since the initial plugin scaffold — they were never real files.

2. **`VERSIONS.md` recorded the stub hashes, not the real library hashes.** When BUG-AUDIT-16 investigation first ran `python3 scripts/fetch_vendor.py` the script reported `[skip] rough.min.js already correct` for every entry. Direct verification showed the actual SHA-256 of the 54-byte stub (`fa353f5d...`) was identical to the value recorded in VERSIONS.md. Someone had hashed the placeholders and written those hashes into the manifest as if they were the real jsDelivr hashes. Result: `verify_vendor_hashes()` in `src/unit_3/launcher.py` silently passed because the manifest and the files matched each other — even though neither had anything to do with the real libraries. The self-consistent lie defeated the existing hash verification entirely.

**Why the runtime user was not blocked.** `verify_vendor_hashes()` is only invoked when `bin/debrief` explicitly runs `python -m debrief.launcher preflight`, and the bare-invocation arm of `bin/debrief` (after BUG-AUDIT-15) calls `ensure_project` which does not include preflight. Even if preflight had been wired in, the hash check would still have passed because the manifest was fake. The combination of "preflight never runs" and "manifest is fake" meant the broken bundle traveled through the whole pipeline — `debrief new` copied the stubs to the project, slide HTML linked them, the browser loaded 54 bytes of comment, and the user saw text-only slides with no explanation.

**Detection method.** User report during a production slide session (`Defect 1 (the real bug): assets/vendor/rough.min.js is a placeholder file — literally one line`). I confirmed via (a) file-size audit across all vendor files, (b) reading each file's first line to see the `/* placeholder */` comment, (c) running `shasum -a 256` on the stubs and comparing to VERSIONS.md, which revealed the self-consistent fake. Re-verification via an actual jsDelivr download showed the real hashes differ completely:

| File | Fake hash in VERSIONS.md | Real jsDelivr hash |
|---|---|---|
| `rough.min.js` | `fa353f5d...2d8bd5cbba2d53` | `d5d56118...3c267a41e53796e45` |
| `mermaid.min.js` | `32eb8479...9b1174ae` | `9a6dd17b...fd9b3577e3d4d0011a77ddcc916be58df9bfb` |
| `katex.min.js` | `7b6ff4d0...a998d247b7ecc5b` | `dc84b296...137f4e138f46a58ae` |
| `katex.min.css` | `5189f4be...37f573352578` | `505d5f82...a1141cd7bba67afe411d1240335f820960b5c3` |
| `KaTeX_Main-Regular.woff2` | `1352ecd8...26a2a88c23c9` | `c2342cd8...1d43f2cf316abd7866` |

**Fix summary.**

1. **Corrected VERSIONS.md.** The five hash values are replaced with the actual SHA-256 of the real jsDelivr artifacts (mermaid@10.6.1, roughjs@4.6.6, katex@0.16.9). A comment line at the top of the file records that the hashes were verified against jsDelivr downloads on 2026-04-15 per BUG-AUDIT-16.
2. **Real files downloaded and committed.** `python3 scripts/fetch_vendor.py` now downloads the real libraries from jsDelivr, verifies each against the corrected manifest, and writes to `src/unit_1/assets/vendor/`. Sizes jump from 54-56 bytes to 28 KB (rough), 2.9 MB (mermaid), 270 KB (katex.js), 23 KB (katex.css), and 26 KB (font). Both workspace and delivered repos get identical real files.
3. **New `scripts/fetch_vendor.py`.** A maintainer build step at the workspace root (alongside `routing.py` and `prepare_task.py`) that reads VERSIONS.md, downloads from each listed URL via `urllib.request` (stdlib only, no new dependency), verifies SHA-256, and writes the verified bytes. Idempotent: re-running on an already-correct vendor directory is a no-op. Fails loudly on any hash mismatch — never writes a file whose hash does not match the manifest. End users never run this script; it is a reproducible recipe for the maintainer acquisition step so VERSIONS.md can be bumped without manual wget/shasum sequences.
4. **New regression tests** in `tests/regressions/test_bug_audit_16_vendor_real_files.py` catch the whole class of bugs:
   - Every VERSIONS.md entry has a corresponding real file on disk at the declared path, in both workspace and delivered.
   - Each file's SHA-256 matches its manifest entry.
   - Workspace and delivered vendor directories are byte-identical (closing the workspace-delivered drift hole per BC-1.12a).
   - File-size lower bounds reject placeholder stubs: rough > 10 KB, mermaid > 100 KB, katex.js > 100 KB, katex.css > 10 KB, woff2 > 5 KB.
   - `scripts/fetch_vendor.py` exists at the workspace root, is Python-importable, and does NOT ship inside the plugin directory (it is a maintainer tool, not a runtime artifact).

**Blueprint contracts added or amended.** BC-1.12 (VERSIONS.md format) extended with the requirement that every listed file must exist at the declared path with a hash that matches the manifest. New BC-1.12a specifies that workspace and delivered vendor directories must be byte-identical. New BC-3.15 specifies the `scripts/fetch_vendor.py` contract (stdlib-only, idempotent, hard-fail on mismatch).

**Out of scope.** (a) Wiring `bin/debrief` to run `preflight` (and therefore `verify_vendor_hashes`) on bare invocations — the regression tests catch artifact regressions at `pytest` time, which is sufficient defense-in-depth until a separate audit decides whether runtime verification is worth the latency cost. (b) Bumping the pinned library versions — upgrades follow the same workflow (edit VERSIONS.md, run `fetch_vendor.py`, run tests, commit). (c) Adding additional vendor libraries (D3, Chart.js, etc.) — separate decision. (d) License-text fetching — jsDelivr does not ship `*.LICENSE.txt` files alongside the minified artifacts and the URLs in VERSIONS.md point to the licenses for attribution.

**Verification.** Test suite gains 8 new regression tests in `test_bug_audit_16_vendor_real_files.py`. `verify_vendor_hashes()` now passes on the real files and on the corrected manifest. Workspace and delivered pytest runs both pass at 1436 (baseline 1428 + 8 new). Manual `shasum -a 256 src/unit_1/assets/vendor/rough.min.js` matches `d5d561189ea0ad7a2818d586dc964d84fa4751124a5270c6b267a41e53796e45`.

**User action after the fix lands.** Refresh the plugin cache (same procedure as BUG-AUDIT-12 through -15): `claude plugin uninstall debrief@debrief --scope project && claude plugin install debrief@debrief --scope project`. The next `debrief new` or `/debrief:slide` will copy the real vendor files to the project's `assets/vendor/`, and rough.js / mermaid / KaTeX will load correctly in slide HTML. Any project created before this fix has stub vendor files on disk — those need to be manually copied from the refreshed plugin cache (`cp -r ~/.claude/plugins/cache/debrief/.../debrief/assets/vendor/* <project>/assets/vendor/`) or the project re-created. The lab_meetings/leo project specifically needs this copy-over to recover rough.js rendering.

### BUG-AUDIT-17: visual-QA not dispatched after slide writes; PostToolUse agent hook broken upstream; no deterministic fallback

**Symptom.** A user running debrief in production reported the following, verbatim: *"I didn't dispatch visual-qa after either slide was produced. The slide-maker explicitly noted 'No automated visual-QA ran in this thread' for slide 1, and I ignored it. That's my failure as the consultant — the CLAUDE.md workflow expects visual-qa to review every slide before the red-green gate, and I skipped it."* Slides were written to `slides/` but no entry was appended to `output/qa_log.jsonl`, so the red-green gate had no data to act on. The consultant moved on to the next slide without any QA check running.

**Historical root cause.** Spec §24.18 (prior to this entry) and REQ-SLIDE-7 (prior to this entry) described the red-green cycle as relying on a `type: "agent"` PostToolUse hook to fire the visual-QA agent synchronously after every `Write|Edit` matching a slide. BUG-AUDIT-12b documented in 2026-04-14 that Claude Code v2.1.107 broke this hook upstream with an internal assertion error: *"Messages are required for agent hooks. This is a bug."* The plugin-side schema matched `code.claude.com/docs/en/hooks.md` verbatim, so BUG-AUDIT-12b left the hook in place with a README note and documented the regression as upstream-pending. Since then, every slide write has silently failed to trigger QA; the error was non-blocking (cosmetic), so the write succeeded and the session continued, but no qa_log entry ever appeared.

**Architectural root cause (discovered during BUG-AUDIT-17 course correction).** An initial draft of this fix proposed adding a `production/qa_check` sub_phase to `routing._SUB_PHASE_ACTION` so visual-qa would fire via a dedicated routing cycle. Investigation showed this was based on a wrong mental model. **Debrief has no runtime routing loop.** `main_routing` and `main_update_state` are library functions defined in `src/unit_4/routing.py`, but nothing in the plugin invokes them during a live session. Orchestration is driven by the **consultant agent** (per `templates/project_claude.md`) which reads state files, uses its `Task` tool to spawn subagents, and interleaves them in its own LLM-driven flow. Between subagent calls, no Python code runs — there is no "next routing cycle" for a new sub_phase to dispatch into. Any fix that relies on routing cycles is inapplicable to debrief as currently implemented. (A future audit could separately wire `bin/debrief` to actually run a routing loop; that is outside BUG-AUDIT-17's scope.)

Combined, these two facts created a silent failure mode: the spec prescribed a dispatch mechanism (the hook) that was broken upstream, with no fallback. The consultant was informally expected to notice the missing QA and manually spawn visual-qa via its Task tool, but nothing in code forced the dispatch. The user's report is exactly this failure: the consultant saw the slide-maker's "no QA ran" note and did not spawn visual-qa.

**Classification.** The spec is **underspecified on the failure path**. §24.18 prescribed a single dispatch mechanism with no graceful-degradation story. The blueprint contracts followed the spec. The code followed the blueprint. The system had no defense-in-depth against the mechanism being unavailable.

**Detection method.** User report during a real slide-production session (Defect 2 in the user's note: *"That's my failure as the consultant"*). I audited via reading §24.18, §24.22, REQ-SLIDE-7, REQ-QA-1 in the spec, then tracing the actual implementation through `hooks/hooks.json` (found the still-broken `type: "agent"` PostToolUse entry), `src/unit_1/agents/slide-maker.md` (found no QA dispatch instruction and no `Task` tool in frontmatter), `src/unit_4/routing.py` (found `check_g3_2_machine_gate` still reading qa_log.jsonl but with nothing producing new entries), and `commands/slide.md` (found the aspirational "On completion, the visual-qa agent automatically reviews the output" text with no implementation anywhere). The architectural course-correction happened when I realized the routing loop I was planning to use doesn't actually run in production.

**Fix summary — hybrid Tier 1 command hook + Tier 2 slide-maker Task dispatch.**

1. **Tier 1 (programmatic, fully deterministic).** A new `type: "command"` PostToolUse handler in `hooks/hooks.json` invokes `${CLAUDE_PLUGIN_ROOT}/bin/qa-run-on-write` on every `Write|Edit` matching `slides/*.html`. `bin/qa-run-on-write` is a new Python wrapper (~100 lines) that reads the hook input JSON from stdin, extracts `tool_input.file_path`, and — if and only if the path matches a slide HTML file — shells out to `python -m debrief.qa_checker --slide-path <path> --screenshot-path output/screenshots/<slug>.png --project-root <cwd>`. The subprocess runs Tier 1 programmatic invariants (INV-04, INV-06, INV-07, INV-08, INV-10 plus the other deterministic checks from §24.22) and appends a Tier 1 entry to `qa_log.jsonl`. This tier is **fully deterministic**: Claude Code's hook runtime fires the command synchronously on every slide write; no LLM discretion is possible; non-blocking by design (the script always exits 0 even if `qa_checker` fails internally, so the parent Write never blocks per spec §7.3).

2. **Tier 2 (VLM, slide-maker-dispatched).** The slide-maker agent's frontmatter `tools` list is extended with `Task`, and its system prompt gains a load-bearing `## QA Dispatch (REQUIRED)` section instructing the agent to invoke visual-qa via `Task` as its absolute final action before returning from its turn. The instruction is as strong as prompt text can be — *"you MUST invoke visual-qa"*, *"this is not optional"*, *"your absolute final action"*, *"a slide that returns without Tier 2 QA is a contract violation per BC-8.4"*. Visual-qa, when spawned, reads the latest Tier 1 entry from qa_log.jsonl, runs its Tier 2 + veto checks (VETO-01..07 plus INV-01/02/03/05/09/11/18/21 per §24.22), and appends a merged `tier: "2_merged"` entry that replaces the Tier-1-only entry as the latest for that slug. This tier is **LLM-driven** — prompt-level enforcement via slide-maker's system prompt is the strongest achievable guarantee given that only an agent with the `Task` tool can spawn a subagent and only via its LLM-controlled turn.

3. **PostToolUse `type: "agent"` hook removed entirely.** The broken agent-type handler from BUG-AUDIT-12b is deleted from `hooks/hooks.json` and replaced with the command handler above. The plugin no longer uses any `type: "agent"` hooks anywhere, so the v2.1.107 upstream regression is no longer relevant to debrief regardless of whether it is ever fixed upstream. **BUG-AUDIT-12b closes as superseded by BUG-AUDIT-17.** A regression test pins the "no agent hooks" invariant so a future well-meaning maintainer cannot re-introduce a broken pattern.

**Blueprint contracts amended.** BC-1.4 extended to require the `type: "command"` PostToolUse handler invoking `bin/qa-run-on-write`, and to forbid `type: "agent"` handlers anywhere in `hooks.json`. New BC-8.4 specifies the slide-maker's `Task` tool requirement and the load-bearing system-prompt instruction.

**Out of scope.** (a) Fully deterministic Tier 2 dispatch — the plugin architecture has no mechanism to force a subagent spawn outside an agent's LLM turn; prompt-level enforcement is the strongest available guarantee. (b) Restoring agent hooks if Claude Code upstream fixes v2.1.107 — debrief will not reintroduce any `type: "agent"` hook because the command-hook + slide-maker-Task architecture is strictly superior (deterministic, version-independent, simpler state). (c) Wiring `commands/slide.md` to actually invoke `main_routing` — the consultant-as-orchestrator model is inherited from `templates/project_claude.md` and is orthogonal to this bug. A separate audit could revisit whether debrief should run a routing loop similar to SVP's six-step cycle. (d) Tier 2 coverage verification — a future defense-in-depth fix could add a post-session test that reads `qa_log.jsonl` and flags slides with only Tier 1 entries (indicating the slide-maker skipped the Task dispatch).

**Verification.** Test suite gains ~10 new regression tests in `tests/regressions/test_bug_audit_17_qa_dispatch.py`. The existing `tests/regressions/test_bug_audit_12_hook_path_quoting.py::test_post_tool_use_agent_hook_still_uses_prompt_field` is renamed and inverted to `test_post_tool_use_uses_command_type_not_agent_per_bug_audit_17`, asserting the command-type hook replaces the agent-type hook. Workspace and delivered pytest both pass at the new baseline. Smoke tests: `echo '{"tool_input":{"file_path":"slides/test.html"}}' | bin/qa-run-on-write` exits 0; a non-slide path `echo '{"tool_input":{"file_path":"assets/images/x.png"}}' | bin/qa-run-on-write` also exits 0 (non-slide writes are a silent no-op).

**User action after the fix lands.** Refresh the plugin cache (same procedure as prior BUG-AUDIT fixes): `claude plugin uninstall debrief@debrief --scope project && claude plugin install debrief@debrief --scope project`. The next slide write in any project will automatically trigger Tier 1 QA via the command hook, and the slide-maker's updated system prompt will direct it to spawn visual-qa as its final action. The *"Messages are required for agent hooks"* cosmetic error from v2.1.107 will stop appearing entirely because debrief no longer uses any agent hooks.

### BUG-AUDIT-18: `export.py` imports non-existent `debrief.state` module; test mocks masked it

**Symptom.** A user running `python -m debrief.export --project-root <dir>` in production got:

```
Failed to read deck state: No module named 'debrief.state'
```

`/debrief:export` failed at the deck-state load step and never reached the Playwright rendering phase. The user could not produce any PDF from their approved slides.

**Root cause.** `src/unit_10/export.py` had two inline imports that referenced a module path that does not exist anywhere in the plugin:

- Line 76: `from debrief.state import read_deck_state`
- Line 183: `from debrief.state import (increment_export_count, write_deck_state)`

The canonical module name is `debrief_state` with an underscore — matching the actual filename `src/debrief/debrief_state.py` (delivered) or `src/unit_2/debrief_state.py` (workspace). Every other module in the plugin imports it correctly (verified across `src/unit_4/routing.py`, `src/unit_5/ledger.py`, `src/unit_11/utility_skills.py`, and every test file's conftest). `src/unit_10/export.py` was the only outlier — presumably a typo or copy-paste error that never noticed because pytest didn't exercise the import path.

**Why pytest never caught the typo.** `tests/unit_10/test_export.py` had five occurrences of the phantom `debrief.state` string: one in a docstring and four in `patch.dict("sys.modules", {..., "debrief.state": mock_state_module, ...})` calls. The tests were injecting fake modules at the exact wrong key that the broken code imports from — making `from debrief.state import ...` resolve to the mock without ever reaching the real module. The test suite was self-consistent with the bug: wrong code + wrong mock + no independent verification = green tests.

This is a classic **test-mock-hides-bug** pattern. A mock that points at a phantom import path provides zero defense against the production code referencing that same phantom path. The only defense is either (a) an integration test that uses the real module, or (b) a grep-based sentinel that forbids the phantom path anywhere in the codebase.

**Classification.** Pure **code defect** masked by a **test-design defect**. The spec never mentioned `debrief.state` — it consistently names the module `debrief_state` throughout. No spec amendment is needed beyond this Bug Catalog entry. The blueprint gets a small new contract (BC-10.X) pinning `export.py`'s import source to `debrief_state`, plus a testing-side contract forbidding future test authors from mocking non-existent module paths.

**Detection method.** Direct user report during a production session: *"Plugin bug #5: export.py line 76 imports from debrief.state import read_deck_state but the module is debrief_state.py — no debrief/state.py exists, so the export CLI dies at startup. Same import appears elsewhere. Adding to the upstream bug list."* Follow-up grep audit confirmed two import lines in export.py and five occurrences in test_export.py; no other file in the plugin references the phantom path.

**Fix summary.**

1. **`src/unit_10/export.py` (synced to `debrief1.0-repo/debrief/src/debrief/export.py`):** two inline import statements fixed, changing `from debrief.state import ...` to `from debrief_state import ...`. The defensive `try/except` wrapping is preserved — the imports remain inline so ImportError raises a user-friendly "Failed to read deck state" / "Failed to update export count" message instead of a raw module-load traceback. An explanatory comment above each fixed import references BUG-AUDIT-18 so future maintainers can trace the history.

2. **`tests/unit_10/test_export.py`:** five occurrences of the phantom string updated. The docstring now says "debrief_state module"; the four `patch.dict("sys.modules", ...)` calls now use `"debrief_state"` as the key. The mock objects themselves are unchanged — the fix is purely a key rename so the tests exercise the corrected import path against mocks installed at the real module location.

3. **Blueprint BC-10.X (new) — Canonical deck-state import source.** The export module MUST import deck-state functions from `debrief_state`. Any form of `from debrief.state import ...` or `import debrief.state` is a defect. Enforced by the grep-based regression sentinel at `tests/regressions/test_bug_audit_18_export_import_path.py`.

4. **Blueprint BC-testing.X (new) — Tests MUST NOT mock non-existent module paths.** Test files MUST NOT call `patch.dict('sys.modules', {...})` with a dict key that does not resolve to a real plugin module. Mocking a phantom module path makes the test suite self-consistent with any production-code reference to the same wrong path, hiding the bug. The BUG-AUDIT-18 regression test specifically forbids `"debrief.state"` as a sys.modules key anywhere under `tests/`; general enforcement is reviewer-gated.

5. **`tests/regressions/test_bug_audit_18_export_import_path.py` (new):** six regression tests in one class:
   - **Code sentinel**: walk `src/` and assert no `.py` file contains `from debrief.state` or `import debrief.state`.
   - **Test sentinel**: walk `tests/` and assert no `.py` file contains `"debrief.state"` as a sys.modules key (the docstring of this test file itself references the phantom name for documentation purposes, so the test skips its own file to avoid false-positive).
   - **Live import checks (3 tests)**: import `read_deck_state`, `write_deck_state`, `increment_export_count` from the real `debrief_state` module and assert each is callable. Catches the class of bug where someone renames or removes one of the functions.
   - **Positive sentinel**: read `export.py` and assert it contains `from debrief_state import` at least once (the canonical "after" shape).

   All tests use sibling-discovery path helpers (`_workspace_root()`, `_delivered_plugin_root()`) and run unconditionally in both layouts — zero skips per the CLAUDE.md break-glass rule and the BUG-AUDIT-17 correction.

**Out of scope.** (a) Restructuring `export.py`'s inline imports into top-level imports. The inline shape is defensive against ImportError and is worth preserving. (b) Auditing every other module for similar typos — the grep-based regression sentinel is the structural defense against this class of bug across the entire `src/` tree. (c) Adding `src/debrief/__init__.py` + `state.py` to make `debrief.state` a valid package path as an alternative "fix" — the canonical module name is flat `debrief_state` everywhere else; changing package structure to accommodate a typo would be worse than fixing the typo. (d) General cleanup of other mocks in `test_export.py` (Playwright, fitz, etc.) — those are unrelated to BUG-AUDIT-18.

**Verification.** Test suite gains 6 new regression tests in `tests/regressions/test_bug_audit_18_export_import_path.py`. Both workspace and delivered pytest runs pass at 1462 / 0 failed / 0 skipped (1456 baseline + 6 new). Manual smoke test: `python -m debrief.export --project-root <tmp_project>` in a freshly-created debrief project no longer produces the `ModuleNotFoundError: No module named 'debrief.state'` error (it may fail for other reasons if no slides exist, but the specific phantom-module error is gone).

**User action after the fix lands.** Refresh the plugin cache via the standard `claude plugin uninstall debrief@debrief --scope project && claude plugin install debrief@debrief --scope project`. After refresh, `/debrief:export` will reach the Playwright rendering stage and produce a PDF (assuming approved slides exist and style is locked). No project-state migration is needed — the fix is purely in the plugin code, not in any per-project artifact.

### BUG-AUDIT-19: `main_update_state` has no G2.1 STYLE APPROVED dispatch branch; `promote_style_draft` is orphaned from production code

**Symptom.** A user approving the style proposal at G2.1 was told "Gate response logged", but the 7-step compile-and-lock sequence from §24.8 never ran. The Consultant agent (acting as orchestrator) observed verbatim:

> *"Gate response logged, but the drafts haven't been promoted yet — `style_locked` is still false and the files are still in `.debrief/draft/`. The update_state CLI records the response; the actual promote + compile step is separate. Let me trigger it."*

`style_config.json` and `style_guide.md` stayed in `.debrief/draft/`. `assets/style.css` was never compiled. `deck_state.json` still had `style_locked: false`. The user could not write slides because `check-write-auth` (BUG-AUDIT-6 / BC-1.10) blocks `slides/*.html` writes until the style lock is set. The session was stuck.

**Root cause.** `main_update_state()` in `src/unit_4/routing.py` had an incomplete dispatch table. It handled exactly three cases by name: `--skill-prelude` mode, `gate_id == "G1.3_figure_selection"`, and `gate_id == "G3.2_qa_review"`. Everything else fell through to a generic `last_gate_response` writer that wrote the response string to `debrief_state.json` and returned. **`gate_id == "G2.1_style_config_review"` took this generic path** — the function recorded `last_gate_response = "STYLE APPROVED"` and returned without calling `promote_style_draft()` or writing `style_locked: true` anywhere.

**`promote_style_draft()` was defined but orphaned.** At `src/unit_4/routing.py:632` the function implemented the full 7-step §24.8 sequence (validate draft, atomically rename files, invoke style_compiler, chmod 444, set style_locked, rmtree draft). `tests/unit_4/test_routing.py` had a `TestPromoteStyleDraft` class with 6 unit tests — they all passed by calling `promote_style_draft()` directly. **No test ever called `main_update_state` with G2.1 STYLE APPROVED and asserted the promotion happened.** Pytest was green while the function was disconnected from the dispatch chain.

**Classification.** Pure **code defect** (missing dispatch branch) masked by a **test-gap defect** (unit-testing the helper in isolation without walking the production call site). Spec §24.8 is authoritative and explicit — *"`update_state` is the sole caller for the compile-and-lock sequence"* — and the implementation violated that contract. This is structurally the same test-hides-bug pattern as BUG-AUDIT-18, applied to a different axis: BUG-AUDIT-18 masked a typo by mocking the wrong import path; BUG-AUDIT-19 masked a missing call site by testing the orphan in isolation.

**Detection method.** Direct user report during a production session (quoted above). Follow-up grep of `main_update_state` confirmed no G2.1 branch. Grep of `promote_style_draft` callers showed the function was called only from tests, never from production code. Cross-reference with spec §24.8 and BC-4.6 confirmed the implementation diverged from both.

**Fix summary.**

1. **`src/unit_4/routing.py` (synced to `debrief1.0-repo/debrief/src/debrief/routing.py`):** `main_update_state` gains a new branch after the G3.2 handler and before the generic fallback:
    ```python
    if gate_id == "G2.1_style_config_review":
        if response == "STYLE APPROVED":
            promote_style_draft(project_root)
        elif response.startswith("STYLE REVISE"):
            _handle_g21_style_revise(response, project_root)
        # Fall through to generic last_gate_response writer below.
    ```
    The intentional fall-through means `debrief_state.last_gate_response` is always persisted (via the existing generic writer at the end of `main_update_state`), regardless of which G2.1 sub-response was handled. `promote_style_draft` writes `style_locked: true` and `state_hash` to `deck_state.json` (a separate state file), so there is no double-write or conflict.

    A new helper `_handle_g21_style_revise(response, project_root)` implements the REVISE path per §24.21: extract the feedback payload after the `"STYLE REVISE "` prefix, write `.debrief/gate_data.json` atomically with `{"gate_id": "G2.1_style_config_review", "data": {"style_revise_feedback": "<feedback>"}}`, and recursively remove `.debrief/draft/` (the draft is discarded per §24.21; the Stylist starts fresh on the next cycle with the feedback in prepare context). The validator in `main_update_state` has already rejected empty or malformed feedback with `sys.exit(4)` by the time the helper runs, so the helper trusts the grammar.

2. **`tests/unit_4/test_routing.py` — new `TestG21StylePromotionDispatch` class** with one integration sentinel test. It constructs a synthetic project with draft files, invokes `main_update_state("G2.1_style_config_review", "STYLE APPROVED", project_root)`, and asserts (via a counting wrapper on `promote_style_draft`) that the helper was called exactly once. It also asserts the post-conditions (files promoted, draft removed, `style_locked=true`). This test lives alongside the existing `TestPromoteStyleDraft` so a future maintainer editing `main_update_state` sees the integration assertion right next to the helper's unit tests and is less likely to orphan the function again.

3. **`tests/regressions/test_bug_audit_19_g21_style_promotion.py` (new)** — `TestBugAudit19G21StylePromotion` class with 8 tests covering the full post-condition surface: file promotion, style_compiler subprocess invocation, chmod 444, compiler-failure-no-rollback per BC-4.6, STYLE REVISE gate-data writing, STYLE REVISE empty-payload rejection, unknown-response rejection, and an integration sentinel parallel to the unit_4 version. All 8 tests use `tmp_path` fixtures with real state files on disk, mock `subprocess.run` for the style_compiler call, and run unconditionally in both workspace and delivered layouts via the zero-skip sibling-discovery path pattern.

**Blueprint contracts amended.** **BC-4.6** extended to require the G2.1 dispatch branch in `main_update_state` (the prior version only described what `promote_style_draft` does internally, not who calls it). **New BC-4.19** adds a general "integration tests must walk the dispatch" rule: whenever a Blueprint Contract names a helper function that a higher-level entry point must call, the test suite must include at least one integration test that invokes the higher-level entry point and verifies the helper's side effects. BUG-AUDIT-19 is the illustrative incident.

**Out of scope.** (a) The naming drift between `_GATE_VALID_RESPONSES["G2.1_style_config_review"]` (uses `"STYLE REVISE <instructions>"`) and spec §24.21 (which uses `"STYLE REVISE"`). Both names appear in the codebase; unifying the vocabulary is a separate cleanup deferred to a future audit. (b) Wiring the spec §24.8 G2.2 LOCK SUCCESS / LOCK FAILED machine gate — debrief has no active routing loop that fires machine gates automatically (BUG-AUDIT-17 architectural finding), so G2.2 remains a documented-but-not-enforced concept. The style-lock fix works without it: on success, `promote_style_draft` sets `style_locked: true` directly, and the Consultant observes this via state file reads on the next turn. (c) Auditing other gates (G1.2, G3.3, G4.X) for similar missing dispatch branches — the new BC-4.19 testing rule is the structural defense against recurrence; a full audit is a separate task. (d) Rewriting `commands/style.md` or `agents/consultant.md` — the Consultant in the observed session already knew to invoke `update_state` (hence "Gate response logged"); the bug was purely in `update_state`'s internal dispatch, not in consultant prompts.

**Verification.** Test suite gains 9 new tests (8 in `test_bug_audit_19_g21_style_promotion.py` + 1 integration sentinel in `test_routing.py::TestG21StylePromotionDispatch`). Both workspace and delivered pytest runs pass at **1471 / 0 failed / 0 skipped** (1462 baseline + 9 new). Manual smoke test of `main_update_state` with a synthetic project confirms files get promoted, draft is removed, `style_locked` is set to True, and `last_gate_response` is persisted — none of which worked pre-fix.

**User action after the fix lands.** Refresh the plugin cache via `claude plugin uninstall debrief@debrief --scope project && claude plugin install debrief@debrief --scope project`. After refresh, run `/debrief:style` in any project, complete the dialog, and say STYLE APPROVED at G2.1. The Consultant will invoke `main_update_state` (as it already does), and the promotion + compilation + locking will happen automatically. The user should observe `style_config.json` and `style_guide.md` at the project root, `.debrief/draft/` gone, `style_locked: true` in `deck_state.json`, and `assets/style.css` freshly compiled.

### BUG-AUDIT-20: orphan-hunter audit — `merge_approval_payload` missing from G3.3 dispatch + three standing audit sentinels

**Motivation.** The out-of-scope sections of BUG-AUDIT-16 through -19 surfaced the same class of structural defect three times in a row: **a function named in a Blueprint Contract was defined, unit-tested in isolation, yet had zero production callers** — an orphan helper that pytest couldn't see because the isolation tests never walked the dispatch chain. BUG-AUDIT-18 was the typo-import variant; BUG-AUDIT-19 was the missing-gate-dispatch variant. Their out-of-scope notes each suggested "audit the rest of the codebase for other instances of this class". BUG-AUDIT-20 is that audit pass — framed as (a) a one-shot Explore-agent sweep that finds any remaining instances, (b) a direct fix for what the audit found, and (c) three standing pytest sentinels that automate the audit so future drift fails loudly at `pytest` time rather than in production.

**Audit methodology (three patterns).**

1. **Pattern 1 — missing gate dispatch**: walk `_GATE_VALID_RESPONSES` and cross-reference every gate against the explicit `if gate_id == "..."` branches in `main_update_state`. Any gate whose response should trigger a side effect beyond `last_gate_response` persistence, but which lacks a dispatch branch, is a candidate orphan (the BUG-AUDIT-19 failure mode on a different gate).
2. **Pattern 2 — phantom import paths**: walk every `from debrief.X` and `import debrief.X` in `src/` and verify `X` resolves to a real module. BUG-AUDIT-18 already forbade the specific `debrief.state` phantom; Pattern 2 generalizes the sentinel.
3. **Pattern 3 — BC-named orphan helpers**: for every function named in a Blueprint Contract (BC-3.*, BC-4.*, BC-6.*, etc.), verify at least one production call site exists in `src/`. Any BC-named function with zero callers is an orphan by the BUG-AUDIT-19 definition.

**Phase 1 audit findings.**

- **Pattern 1 — zero violations.** All 17 gates in `_GATE_VALID_RESPONSES` are either handled by an explicit dispatch branch (G1.3, G2.1, G3.2, and the new G3.3 added in this entry) or legitimately use the generic `last_gate_response` writer (13 "simple acknowledgment" gates like G1.1 CONTINUE, G3.5 YES/NO, etc.). BC-4.19's structural rule from BUG-AUDIT-19 holds.
- **Pattern 2 — zero violations.** Every `from debrief.X import ...` and `import debrief.X` in `src/unit_*/` resolves to a real module. All imports use the correct flat `debrief_state` form rather than a phantom package path. BUG-AUDIT-18's lesson has held.
- **Pattern 3 — TWO violations found**:

  1. **`merge_approval_payload(slug, project_root)`** at `src/unit_4/routing.py:635`. Spec §24.24 defines this as merging the Slide Maker's pre-written `.debrief/approval_<slug>.json` into `deck_state.json` on G3.3 SLIDE APPROVED; BC-4.21 (new in BUG-AUDIT-20) pins the dispatch requirement. The function had **zero production callers AND zero test coverage** — the purest form of orphan surfaced so far. The current G3.3 handling fell through to the generic `last_gate_response` writer, leaving every approved slide with stale title/content_summary/visual_approach/design_choices fields in `deck_state.json` and the approval payload file orphaned on disk. This is the structural twin of BUG-AUDIT-19's `promote_style_draft` orphan on a different gate.

  2. **`consume_gate_data(expected_gate_id, project_root)`** at `src/unit_4/routing.py:773`. BC-4.7 defines this as the consumer for cross-cycle `.debrief/gate_data.json` payloads, called by `main_prepare` per spec §24.20. The function has thorough unit tests (6 in `TestConsumeGateData`) but **zero production call sites**. `main_prepare` does not invoke it. Cross-cycle gate data (G2.1 STYLE REVISE feedback, G3.3 post-diagnostic SLIDE REVISE instructions, G3.2a MY INSTRUCTIONS) is written to `.debrief/gate_data.json` by `main_update_state` but then sits on disk, never read and never injected into any agent's task prompt.

**Classification.** Both findings are pure **code defects** (missing wiring) masked by **test-gap defects** (unit-testing the helper in isolation without walking the dispatch chain). BC-4.19 from BUG-AUDIT-19 was the structural defense going forward; BUG-AUDIT-20 finds the instances that existed before BC-4.19 was written.

**Scope decision.** BUG-AUDIT-20 fixes **finding 1** (`merge_approval_payload`) directly because it is a direct analog of BUG-AUDIT-19: add a G3.3 APPROVE dispatch branch in `main_update_state` that calls the helper, mirror the test shape. **Finding 2** (`consume_gate_data`) is **deferred to BUG-AUDIT-21** because its fix requires non-trivial spec investigation: the caller is `main_prepare`, not `main_update_state`; the invocation requires mapping the current action sub_phase to the expected gate_id whose payload should be consumed (spec §24.20 describes the mapping for each cross-cycle consumer, but the list is scattered across §24.20 / §24.21 / §14.16 and needs careful reading). BUG-AUDIT-20 whitelists `consume_gate_data` in the Pattern 3 sentinel with a TODO pointing at the follow-up, so the structural defense remains tight.

**Detection method.** Carlo asked me to review the out-of-scope items from BUG-AUDIT-16 through -19 and prioritize follow-up work. Item A of that review was "bundle 18b, 19c, and similar into one audit pass". I dispatched an Explore subagent with three grep-based patterns; the audit returned zero findings for Patterns 1 and 2, and two findings for Pattern 3. The Phase 1 Explore then became the starting point for this Bug Catalog entry.

**Fix summary.**

1. **`src/unit_4/routing.py` (synced to delivered)** — `main_update_state` gains an explicit G3.3 APPROVE dispatch branch that calls `merge_approval_payload(current_slide_slug, project_root)`. State-corruption case (APPROVE with null `current_slide_slug`) exits code 4. REVISE and DISCARD responses fall through to the generic writer unchanged (they do not trigger a merge). The branch sits between BUG-AUDIT-19's G2.1 branch and the generic fallback, mirroring BUG-AUDIT-19's architectural shape.

2. **`tests/regressions/test_bug_audit_20_orphan_audit.py` (new)** — four test classes, 12 tests total:
   - **`TestBugAudit20LegA` (5 tests)** — integration tests for the new G3.3 dispatch. Constructs synthetic projects with draft slide records and approval payloads; asserts APPROVE merges the payload, REVISE/DISCARD don't, missing-slug APPROVE exits code 4, and an integration sentinel pins `merge_approval_payload`'s call-site via monkey-patch (same pattern as BUG-AUDIT-19's integration sentinel).
   - **`TestBugAudit20GateDispatchSentinel` (2 tests)** — Pattern 1 sentinel. Uses `ast.walk` to parse `routing.py`'s `main_update_state` function body, extract every `gate_id == "<literal>"` and `gate_id in ("<literal>", ...)` comparison, and assert every key in `_GATE_VALID_RESPONSES` is either in that set or on a hardcoded `_GENERIC_WRITE_ONLY_GATES` allowlist. A meta-test asserts every allowlist entry corresponds to a real gate (prevents stale allowlist entries).
   - **`TestBugAudit20PhantomImportSentinel` (2 tests)** — Pattern 2 sentinel. Auto-discovers the canonical module name set from the current-layout directory listing (`src/unit_*/*.py` in workspace, `src/debrief/*.py` in delivered). For every `from debrief.X import ...` and `import debrief.X` match in `src/`, asserts `X` is in the canonical set. A sanity meta-test asserts the auto-discovery returns a non-empty set with known-required modules present.
   - **`TestBugAudit20BcNamedOrphanSentinel` (3 tests)** — Pattern 3 sentinel. Hardcoded map `{bc_id: function_name}` covering 10 current BCs that name production-called functions. For each entry, walks `src/` line by line (skipping comments and definition lines) and counts call sites. An `_ORPHAN_WHITELIST` permits `consume_gate_data` with a TODO citing BUG-AUDIT-21. Two meta-tests: every whitelist entry must cite a BUG-AUDIT number, and no whitelist entry may correspond to a function that is actually wired up (stale-whitelist detection).

3. **Spec** — this Bug Catalog entry. No amendments to existing sections — §24.24 already prescribes the G3.3 approval merge; the code just needs to follow the spec.

4. **Blueprint** — new **BC-4.21** specifies the `main_update_state` G3.3 APPROVE dispatch requirement for `merge_approval_payload`, parallel to BC-4.6's BUG-AUDIT-19 amendment for `promote_style_draft`. New **BC-4.22** formalizes the three standing sentinels as a blueprint contract, so future test authors understand the sentinels are load-bearing and must not be weakened.

**Out of scope.** (a) **Leg B — `consume_gate_data` wiring** — deferred to BUG-AUDIT-21 for scope control; needs spec-investigation of the action→expected_gate_id mapping. (b) **General dead-code detection beyond BC-named functions** — `vulture`-style sweeps are separate maintenance; BUG-AUDIT-20 focuses on BCs because contracts are explicit promises of production use. (c) **Auditing private helper functions for orphans** — private helpers (`_foo`) are file-internal by convention; grep-based sentinels would produce too many false positives. (d) **Retroactive audits of BUG-AUDIT-1 through -17** — the standing sentinels cover current state, not historical archaeology.

**Verification.** Test suite gains 12 new tests in `test_bug_audit_20_orphan_audit.py`. Workspace and delivered pytest both pass at **1483 / 0 failed / 0 skipped** (1471 baseline + 12 new). Manual smoke test: `main_update_state("G3.3_slide_review", "APPROVE", tmp_project)` merges the approval payload, deletes the file, updates `slide.status` to `"approved"` — none of which happened pre-fix.

**User action after the fix lands.** Refresh the plugin cache via `claude plugin uninstall debrief@debrief --scope project && claude plugin install debrief@debrief --scope project`. After refresh, any slide approval at G3.3 will automatically merge the approval payload into `deck_state.json`. No per-project migration needed; the fix is purely in the plugin code. Existing projects where slides were "approved" before BUG-AUDIT-20 may have stale slide records in `deck_state.json` (title/content_summary still reflecting the draft), but those slides' HTML at `slides/<slug>.html` is still correct — only the deck state's description of the slide is stale. Users can re-approve the slide via the next G3.3 cycle, or manually edit `deck_state.json` to reflect the current `slides/<slug>.html` content.

---

### BUG-AUDIT-21: Handout Robustness Hardening — decouple from export, dedicated `handout.css`, precondition fail-fast, real-PDF regression test

**Symptom cluster.** Four independent problems in `/debrief:handout`, all masked by mocked unit tests:

1. **Hard crash on fresh projects.** `main_handout` read `deck_state.presentations[-1]` without guarding the empty-list case. Any user who ran `/debrief:handout` before ever running `/debrief:export` got an `IndexError` with a raw Python traceback. This was the most common real-world failure mode for the handout skill — users on a first-draft deck typically have slides but no export.

2. **Spec↔code mismatch on styling.** REQ-HAND-5 (pre-BUG-AUDIT-21) mandated that the handout read `assets/style.css` (the main deck style) and inherit typography/colors from the locked deck style. The actual implementation used a hardcoded inline CSS string inside `generate_layout_html` and never touched `assets/style.css`. The code had silently diverged from the spec, and the divergence was correct by a different architectural argument (the handout is a print-optimized leave-behind, not a branded artifact — see "Prior-Art for Rebuild" below).

3. **No first-class handout stylesheet.** The ink-efficient layout existed only as a Python string literal, not as a version-controlled `handout.css` document. Iterating on handout appearance required Python edits. This made the stylesheet both invisible (no one would think to audit a Python string literal as a design document) and fragile (Python syntax coupling to CSS content).

4. **Backup slide leakage.** The approved-slide filter was `s.status == "approved"` with no `backup` check. `SlideRecord.backup: bool` is a first-class field — an archived prior version of a slide can have `status == "approved"` (it was approved before it was superseded). These backup copies leaked into handouts, producing leave-behind documents that showed superseded slide content alongside the current deck.

**Additional defect found during investigation: mocked tests catch no regressions.** `TestMainHandoutVersionNumbering` patched `playwright.sync_api.sync_playwright` with `MagicMock`, then used `out_path.touch()` inside `main_handout` to make the subsequent `expected.exists()` assertion pass. If Playwright broke, the entire handout pipeline broke, or the rendered HTML became malformed, every test would still pass. Zero bytes of real PDF were ever written by any test. The `touch()` line in production code was a testing artifact smuggled into the shipping codebase.

**Root cause.** Two architectural decisions were never resolved in the original spec, and the code drifted to one answer while the spec held the other:

- *Handout style: inherit from deck vs. dedicated print style.* Spec said inherit; code said dedicated. Neither party knew the conflict existed until BUG-AUDIT-21's investigation surfaced it. BUG-AUDIT-21 resolves it in favor of dedicated (Option B) because the handout's use cases (audience leave-behind, pre-reading, note-taking reference) favor ink efficiency over deck brand continuity.
- *Handout coupling to export: downstream of export vs. independent output channel.* Spec said downstream (REQ-HAND-6 mandated a prior export); code implemented the coupling via `presentations[-1]` but never guarded the empty-list case. BUG-AUDIT-21 resolves it in favor of independent: handout runs on any project with approved slides, scans `output/handouts/` to derive its own version counter, never consults `deck_state.presentations`.

These two decisions are not technically bugs in the old sense — nothing "broke." They are *architectural drift* between spec and code that was never reconciled and that produced user-visible bugs (the IndexError crash and the stale-look handout) as downstream effects.

**Detection.** Manual investigation during the planning of handout robustness work. An Explore agent was briefed to trace handout end-to-end — command file → Python entry point → precondition checks → Playwright call → output path — and report gaps. The investigation surfaced all four symptoms in one pass; no prior break-glass entry had caught them because the mocked test suite was specifically designed to avoid exercising Playwright.

**Classification.** This is **reconciliation**, not feature work, per the prototype rebuild-trigger rule documented in the Debrief project ethos: *"if the thing being added has no new user-visible surface, it is reconciliation."* No new command is added (handout already exists), no new state field is introduced (versioning is filesystem-derived, not state-field-derived), and the new `handout.css` file is an internal template, not a user-facing surface. Break-glass legal.

**Fix — five coordinated changes.**

1. **Extract `handout.css` as a first-class stylesheet.** `src/unit_11/handout.css` is added to the workspace and mirrored into `debrief/src/debrief/handout.css` in the delivered plugin. The stylesheet is grayscale-leaning, uses `mm`-based print units, employs class-based markup (`.page`, `.cell`, `.cell-2up`, `.cell-4up`, `.slug`, `.title`, `.notes`, `.notes-2up`, `.notes-4up`, `.no-shot`), and is designed for Chromium headless print rendering. `generate_layout_html` loads it via `_load_handout_css()` (a new helper that reads `Path(__file__).parent / "handout.css"`) and emits class-based markup only — no per-element inline styles other than dynamic image sources.

2. **Decouple handout from `/debrief:export`.** `main_handout` no longer reads `deck_state.presentations[-1]`. Instead, the output directory is `output/handouts/` (created on first invocation via `mkdir(parents=True, exist_ok=True)`), and the version counter is filesystem-derived: the function scans `output/handouts/` for existing `handout_v*.pdf` files, parses their trailing version numbers, and picks `(max + 1)` — or `1` if the directory is empty. No state mutation, no presentation-folder lookup, no dependency on a prior export.

3. **Precondition fail-fast before Playwright import.** `main_handout` validates all preconditions at entry, in this order: (a) `deck_state.json` exists and is readable, (b) at least one slide has `status == "approved"` and `backup != True`, (c) `playwright` is importable. On any failure, the function prints a descriptive message identifying the missing prerequisite and exits code 2. The Playwright check is deliberately attempted *last* so that a missing-slides run does not report a misleading environment-corruption error. No raw tracebacks.

4. **Exclude backup slides.** The approved-slide filter is now `s.status == "approved" and not s.backup`. Archived prior versions are excluded from handouts by default. Spec REQ-HAND-5/6 and BC-11.10 document this.

5. **Real-PDF regression test.** `tests/regressions/test_bug_audit_21_handout_robustness.py` launches real Playwright and asserts the generated PDF exists, starts with the `%PDF` magic bytes, and has a non-trivial file size. It runs alongside the existing mocked unit tests (which are kept as fast logic-only checks) rather than replacing them. The production `out_path.touch()` line is removed — tests that depend on the touch hack are updated to patch `page.pdf` with a real-bytes writer instead.

**Scope changes.** `src/unit_11/utility_skills.py` (handout functions), new `src/unit_11/handout.css`, `tests/unit_11/test_utility_skills.py` (existing handout tests updated to new path and precondition shape), new `tests/regressions/test_bug_audit_21_handout_robustness.py`, spec REQ-HAND-4/5/6 rewritten, three new blueprint contracts (BC-11.15 handout dedicated stylesheet, BC-11.16 handout fail-fast preconditions, BC-11.17 handout decoupled output path) plus amendments to BC-11.6 (handout versioning rule carved out) and BC-11.7 (playwright check reordered), `debrief/commands/handout.md` rewritten to describe the Option B reality.

**Out of scope.**

- `consume_gate_data` cleanup (the original BUG-AUDIT-21 scope, now re-scoped for a later narrow fix). The function remains whitelisted in BUG-AUDIT-20's orphan sentinel.
- BUG-AUDIT-22 pruning pass (dead-code sweep of `main_routing`, `main_update_state`, `main_prepare`, and the machine-gate chain).
- Centralized `preconditions.py` module for all commands. Handout's preconditions live inline in `main_handout` for now; a general refactor is deferred to BUG-AUDIT-22.
- Prototype banner at the top of `stakeholder_spec.md` declaring the spec as a discovery log. Deferred.
- Other commands (`/debrief:style`, `/debrief:slide`, `/debrief:export`, `/debrief:script`, `/debrief:view`, `/debrief:save`, `/debrief:quit`, `/debrief:reset`). Their precondition tables are designed but unimplemented.
- Handout layout-mode reconciliation against the stale `commands/handout.md` references to "3up, notes-only" (implementation supports only `2up` and `4up`) — doc is updated to match code, no new modes added.

**Verification.** Full pytest must pass from BOTH the workspace and the delivered repo with zero skipped. The new integration test actually launches Chromium and writes a real PDF — it fails loudly if Playwright is broken or missing, which is the correct signal. Manual smoke test: in a real debrief project, `/debrief:handout` produces a readable PDF at `output/handouts/handout_v001.pdf` that opens in a PDF reader and visually shows the approved non-backup slides in ink-efficient layout.

**User action after the fix lands.** Refresh the plugin cache via `claude plugin uninstall debrief@debrief --scope project && claude plugin install debrief@debrief --scope project`. After refresh: `/debrief:handout` can be invoked on any project with at least one approved slide, regardless of whether `/debrief:export` has been run. Existing handout PDFs produced under the old `output/<presentation_folder>/` convention are NOT migrated or deleted — they stay where they are. New invocations write to the new `output/handouts/` location. Users who want the two sets combined can manually move old handout files; there is no automated migration because the old files may be load-bearing for a user's existing organization scheme.

**Prior-Art for Rebuild.** When this prototype is rebuilt from scratch, the following lessons should be baked into the new spec from day one, not discovered after shipping:

1. **The handout is an independent output channel, not a variant of the main deck.** Its use cases (audience leave-behind, pre-reading, note-taking reference) drive different visual priorities (ink efficiency, density, grayscale) from the projected deck (vibrant, brand-consistent, low information density per slide). A rebuild should spec handout with its own stylesheet and its own output path from the first draft. Do not try to unify handout styling with deck styling.
2. **File-based versioning beats state-field versioning for append-only artifacts.** The old design tracked handout count in a state field inside a presentation record. The new design scans the filesystem. Both work, but the filesystem approach eliminates an entire class of state-migration headaches and gracefully handles user edits (deletes, moves, manual renames) without drift.
3. **Mocked tests for PDF generation are worse than no tests.** The mocked `TestMainHandoutVersionNumbering` passed while production was silently broken in four distinct ways. A rebuild should treat "real Playwright writes a real PDF" as a mandatory integration test for any command whose core behavior is artifact generation, even if the test is slower. Mocks can complement, not replace.
4. **Precondition checks must be named and fail-fast.** A raw `IndexError` on `presentations[-1]` is the worst possible user-facing error — it leaks implementation details and gives no fix instruction. Every command's entry point should validate preconditions in an explicit order, print a named message on failure, and exit with a documented non-zero code. This pattern should be a rebuild-level standard, not an optional quality gate.
5. **`assets/style.css` should NOT be a shared dependency across output artifacts.** When multiple output pipelines (deck, handout, script, future formats) are forced through a single stylesheet, the stylesheet acquires contradictory constraints (deck wants vibrancy, handout wants ink efficiency, script doesn't care) and drifts toward a lowest-common-denominator compromise. A rebuild should give each output format its own stylesheet from day one. Share assets (fonts, base reset) via a common `base.css` import, not via a monolithic `style.css`.

---

### BUG-AUDIT-22: Rename `/debrief:reset` → `/debrief:restore` — replace hard-delete with backup-restore

**Symptom.** Two CRITICAL defects in `/debrief:reset`:

1. **Architectural mismatch between documentation and implementation.** `commands/reset.md` described a backup-restore operation ("lists available backup checkpoints, prompts user to confirm which checkpoint to restore, replaces deck_state.json with the chosen backup"). The code (`skill_reset`) implemented a hard-delete of 10 paths — slides/, output/, .debrief/, deck_state.json, debrief_state.json, ledger.jsonl, deck_brief.md, style_config.json, style_guide.md, and assets/. A user reading the command documentation expected restore-from-backup and got permanent deletion of all project data.

2. **No confirmation output or session exit after destructive delete.** After the user typed "RESET" at the confirmation prompt, `skill_reset` silently deleted all files and returned to the Claude Code prompt with no print, no summary, and no session termination (violating REQ-RESET-4). The user had no visual confirmation that the operation succeeded and was left in a session where all state files were missing — a confusing and potentially data-losing state.

**Root cause.** The hard-delete implementation was an SVP-era design suited to "nuke and rebuild from scratch" workflows. The command documentation was written later to describe a more user-friendly backup-restore model, but the code was never updated to match. The two diverged silently because the test suite only exercised the hard-delete path (confirmation string matching and a few file-deletion assertions) and never tested the backup-restore behavior described in the docs.

**Detection.** Systematic command audit across all 9 `/debrief:*` commands, conducted after BUG-AUDIT-21.

**Classification.** Reconciliation. The command already existed (`/debrief:reset`), the backup-restore design was already documented in `commands/reset.md`, and the snapshot infrastructure already existed via `/debrief:save`. No new user-visible surface is added — the command is renamed and its implementation is aligned to the already-documented behavior. Break-glass legal.

**Fix.** Complete replacement of `skill_reset` with `skill_restore`. The hard-delete behavior is permanently dropped.

1. **Rename**: `/debrief:reset` → `/debrief:restore`. Command file renamed from `commands/reset.md` to `commands/restore.md`.
2. **Two-mode invocation** (no `input()` calls): `skill_restore(label=None, ...)` lists available snapshots and returns; `skill_restore(label="my_save", ...)` restores from the named snapshot.
3. **Restore sequence**: validate snapshot → auto-save current state → overwrite deck_state.json → optionally restore ledger.jsonl → sweep orphan slide HTML → write restore_log entry → print confirmation.
4. **Auto-save safety net**: before overwriting, the function calls `skill_save("pre_restore_<timestamp>")` to create a rollback point. Every restore is reversible.
5. **Orphan sweep**: after restoring deck_state.json, any `slides/*.html` file whose stem does not match a slug in the restored state is deleted. Swept filenames are logged.
6. **Restore_log entry**: a JSON line appended to `ledger.jsonl` recording timestamp, source snapshot label, auto-save label, and list of swept slugs. Supports the "log as prototype truth" principle established in BUG-AUDIT-21.

**Spec changes.** REQ-RESET-1..4 rewritten as REQ-RESTORE-1..4 describing backup-restore, auto-save, orphan sweep, restore_log, and preconditions. The `input()` confirmation prompt is removed per REQ-RESTORE-4.

**Blueprint changes.** BC-11.11 rewritten from "exact RESET confirmation string" to "restore snapshot validation + auto-save + orphan sweep sequence." BC-11.12 rewritten from "CLAUDE.md exemption during hard-delete" to "restore scope limits — only overwrites deck_state.json and optionally ledger.jsonl, then sweeps orphan slides; all other files untouched."

**Out of scope.** Other command CRITICALs (export, quit, script, slide) — separate BUG-AUDITs. Stale command docs bundle — separate pass after all CRITICALs. Centralized `preconditions.py` module — deferred. Prototype banner — deferred.

**Prior-Art for Rebuild.**

1. **Restore-from-snapshot is the correct model for a presentation tool.** Hard-delete is never what a user wants when they say "start over" — they want to go back to a known-good state, not lose everything. A rebuild should not offer hard-delete as a user-facing command at all. If hard-delete is needed for dev/testing, it should be a developer tool, not a `/debrief:*` command.
2. **Auto-save before overwrite should be a default pattern.** It costs one directory + two file copies and makes every state-mutating command reversible. A rebuild should bake this into the state-management layer, not into individual command implementations.
3. **`input()` calls in Claude Code plugin functions are an anti-pattern.** The consultant mediates user interaction; Python functions should take parameters and return results. Blocking stdin is a holdover from standalone CLI design. A rebuild should enforce "no input() in any plugin function" as a lint rule.
4. **Orphan-sweep on state restore is the reconciliation point** between state files and filesystem artifacts. State and files can drift; the restore operation is where they are realigned. A rebuild should centralize the orphan-sweep logic so all state-mutating operations (restore, import, merge) can use it.

---

### BUG-AUDIT-23: Export robustness — fail-fast on PyMuPDF failure + filesystem-derived versioning

**Symptom.** Two CRITICAL defects: (1) When PyMuPDF (fitz) was unavailable, `main_export` silently wrote only the first PDF page — multi-page decks lost all content after page 1 with no error message. The fallback code at the merge step caught `ImportError` and wrote `pdf_buffers[0]` as "best effort." (2) Version numbering via `export_count` state field could drift if state was rolled back.

**Root cause.** The fallback was designed as a graceful degradation path but produced the worst possible outcome: a file that looks correct (valid PDF, opens in a viewer) but is missing all slides after the first. The user presents to an audience with a 1-page PDF and discovers the loss live.

**Fix.** (1) Add `importlib.util.find_spec("fitz")` check at entry alongside playwright. If missing, exit 2 with env-corruption message pointing at `debrief --rebuild-env`. Delete the `except ImportError` fallback entirely — no silent single-page writes ever. Remove the redundant playwright try/except at import time (find_spec already checked). (2) Replace `export_count + 1` with filesystem-derived versioning: scan `output/{folder}/deck_v*.pdf` and pick `(max + 1)`. Remove `increment_export_count` and `write_deck_state` calls. Export no longer mutates `deck_state.json` for version counting. (3) AST sentinel in regression tests asserting no `except ImportError` handlers exist in export.py — prevents re-introduction.

**Verification.** Workspace + delivered: 1508 passed / 0 failed / 0 skipped.

**Prior-Art for Rebuild.** Multi-page PDF merging must NEVER silently degrade to single-page on missing dependencies. Fail loudly or don't ship the feature. Check all merge-related dependencies at entry, not at merge time.

---

### BUG-AUDIT-24: Quit robustness — defensive cycle check, summary output, transient artifact cleanup

**Symptom.** One CRITICAL (safe-checkpoint wait during active red-green cycle) and two HIGHs (no summary output, no session exit). Investigation revealed the CRITICAL is structurally impossible in Claude Code's sequential message processing model — `skill_quit` can only run when no Task is in-flight. A belt-and-suspenders defensive check was added: if `red_green_iteration > 0` and `sub_phase` contains `"red_green"`, print a warning to stderr. The warning documents the invariant in code and catches any future concurrency-model change.

**Fix.** (1) Defensive cycle-state warning. (2) Summary output to stderr: phase, archetype, style_locked, approved slide count, last export folder, resume instruction. (3) Transient artifact cleanup: delete `.debrief/task_prompt.md` and `.debrief/gate_data.json` (dead routing-loop artifact) alongside the existing conditional draft/ cleanup. (4) Session exit documented as not implementable from a skill function — `sys.exit()` crashes the process; the consultant handles session closure at the conversation level after `skill_quit` returns.

**Spec amendment.** REQ-QUIT-1 step 1 (safe-checkpoint wait): documented as structurally guaranteed by Claude Code's sequential model; no code mechanism needed. REQ-QUIT-1 step 5 (summary output): now implemented. REQ-QUIT-1 step 6 (session exit): documented as consultant responsibility, not skill function responsibility.

**Verification.** Workspace + delivered: 1517 passed / 0 failed / 0 skipped.

---

### BUG-AUDIT-25: Script filesystem-derived versioning + approved-slide precondition

**Symptom.** `main_script_generator` used `presentations[-1].script_count + 1` for version numbering (state-field coupled, can drift) and had no precondition check for approved slides (silent empty script). **Fix.** (1) Filesystem-derived versioning: scan `output/{folder}/script_v*.md`, pick max + 1. No state mutation — `increment_script_count` and `write_deck_state` calls removed. (2) Precondition: at least one approved non-backup slide required, exit 2 with descriptive message. (3) Backup slides excluded from script content.

**Verification.** Workspace + delivered: 1523 passed / 0 failed / 0 skipped.

---

### BUG-AUDIT-26: Slide style_locked precondition — already enforced at hook layer (docs-only)

**Symptom (reported by audit).** "style_locked precondition not validated at command or agent level for /debrief:slide." **Finding.** Already structurally enforced by the `check-write-auth` PreToolUse hook (`bin/check-write-auth` lines 64-76). The hook reads `deck_state.json` and blocks writes to `slides/` or `assets/style.css` with exit 2 and the message "Style config not yet locked. Run /debrief:style first." if `style_locked` is false. This is a hard gate — the slide-maker agent cannot write any slide file without style lock, regardless of prompt compliance. The audit misidentified this as a gap because it looked for enforcement at the command/agent layer and didn't trace the hook chain. **Fix.** Documentation only — added precondition note to `commands/slide.md` advising the consultant to check `style_locked` before dispatching (saves wasted agent turns). No code change, no regression test (the hook IS the structural guarantee).

---

### BUG-AUDIT-27: Stale command docs bundle — rewrite save.md, script.md, style.md, quit.md

**Symptom.** Four of nine command documentation files described behavior that diverged from the shipping code. save.md said output goes to `.debrief_backups/` and mutates presentations (code writes to `output/snapshots/` and does not touch presentations). script.md said output goes to `exports/script.md` with state-field versioning (code writes to `output/{folder}/script_v{NNN}.md` with filesystem-derived versioning per BUG-AUDIT-25). style.md said the agent writes `assets/style.css` (agent is explicitly forbidden; only the compiler writes CSS). quit.md said it calls save, transitions phase to "done," and exits the session (code flushes state as-is, prints a summary per BUG-AUDIT-24, and returns without termination). **Fix.** All four command docs rewritten in both workspace (`src/unit_1/commands/`) and delivered (`debrief/commands/`) to match the actual code behavior. No code changes.

---

### BUG-AUDIT-28: Prototype banner — spec declared as discovery log (docs-only)

Added the discovery-log banner to the top of `stakeholder_spec.md`. The banner states: append-style changes are break-glass legal; changes that require editing existing spec structure to integrate a new feature trigger a rebuild. The rebuild consumes this spec as validated prior-art. No code changes.

---

### BUG-AUDIT-29: Vocabulary reconciliation — STYLE NEEDS WORK → STYLE REVISE (docs-only)

Replaced all `STYLE NEEDS WORK` references with `STYLE REVISE` across `stakeholder_spec.md` (~15 occurrences), `blueprint_contracts.md` (1), `blueprint_prose.md` (4), `blueprint_self_eval.md` (7). Also fixed the gate-response grammar description: old delimiter was `: ` (colon-space); actual code uses a plain space. Scrapped/archived blueprints left untouched. No code or test changes — tests already used the code's vocabulary.

---

### BUG-AUDIT-30: Delete consume_gate_data — dead cross-cycle handoff consumer

Deleted `consume_gate_data` from `routing.py`. The function was dead at runtime — called only from `main_prepare`, which has zero callers in commands/hooks/agents. The producer side (`_handle_g21_style_revise`'s gate_data.json write) is also dead. The consultant carries STYLE REVISE / SLIDE REVISE / MY INSTRUCTIONS feedback natively via Task-tool prompts. BC-4.7 removed. BUG-AUDIT-20's `_ORPHAN_WHITELIST` emptied. 4 unit tests deleted. **Prior-Art for Rebuild:** file-based cross-cycle handoff is redundant in a consultant-orchestrated runtime. A rebuild should not reintroduce it.

---

### BUG-AUDIT-31: Dead-machinery pruning pass — delete all 13 dead functions from routing.py

All 13 public functions in `routing.py` were dead at runtime — zero external callers in commands/hooks/agents/bin. No `__main__` block, no subprocess invocations. The entire routing loop (`main_routing` → `main_update_state` → `main_prepare` and all helpers) was a dead-code island from SVP Stage 5 onward.

**Deleted:** `resolve_action`, `main_routing`, `check_g3_2_machine_gate`, `validate_gate_response`, `perform_snapshot`, `handle_red_green_transition`, `main_update_state`, `merge_approval_payload`, `promote_style_draft`, `propose_presentation_folder_name`, `main_prepare`, `assemble_task_prompt`, `substitute_gate_placeholders`. Also deleted: `_GATE_VALID_RESPONSES`, `_GATE_RESPONSES`, `_SUB_PHASE_ACTION`, all private helpers, all constants.

**Test impact:** ~130 tests deleted across `test_routing.py` (gutted), `test_integration.py` (6 dead-routing classes removed), `test_bug_audit_14` (gutted), `test_bug_audit_15` (2 dead classes removed), `test_bug_audit_19` (gutted). BUG-AUDIT-20 sentinel simplified to keep only Pattern 2 (phantom imports) and a reduced Pattern 3 (launcher.py BCs only).

**Prior-Art for Rebuild.** (1) The routing loop was an SVP-era pattern for safety-critical software. A presentation tool whose worst case is a broken slide does not need machine gates, state-transition tables, or automated routing cycles. (2) BUG-AUDIT-19 and -20 each "fixed" dispatch branches inside dead code — structurally correct fixes that were operationally meaningless because the parent function had no runtime callers. A rebuild should verify that every fix targets code that actually runs, not just code that exists. (3) When 13 out of 13 public functions in a module are dead, the module is the unit of deletion, not the individual function.

**Verification.** Workspace + delivered: 1389 passed / 0 failed / 0 skipped (down from 1519 — ~130 dead-code tests removed).

---

### BUG-AUDIT-32: View/save preconditions + style locked warning

Added precondition checks to `/debrief:view` (project existence + "no slides match" message) and `/debrief:save` (confirmation output per REQ-SAVE-3). Added "already locked" warning to `commands/style.md`. **Spec gap:** REQ-VIEW and REQ-SAVE didn't mandate precondition error messages. **Blueprint recommendation:** every command entry point MUST validate preconditions at entry with named error messages before doing any expensive work.

---

### BUG-AUDIT-33: Consultant.md tightened with dispatch menu + preconditions

Rewrote `agents/consultant.md` from 29 minimal lines to a full dispatch reference with precondition table for all 9 commands, "ask rather than guess" clause, typical workflow order, and backup-slide guidance. **Spec gap:** no section required the consultant prompt to enumerate dispatchable commands. **Blueprint recommendation:** every orchestrator agent prompt MUST contain an explicit dispatch menu with preconditions.

---

### BUG-AUDIT-34: Trivial coverage-audit gap fixes

Five fixes: REQ-HAND-2 (handout mode validation), BC-5.10/BC-8.7 (escalation instructions in slide-maker.md), BC-8.9 (rhetorical_role visual treatment), BC-9.8 (bug-diagnostic write restriction), REQ-CONSULT-12 (backup-slide guidance). All were spec requirements with no corresponding implementation. **Blueprint recommendation:** every BC and REQ-* entry should have at least one test or agent-prompt instruction that exercises it.

---

### BUG-AUDIT-35: Red-green iteration limit + oscillation detection + dead field removal

REQ-SLIDE-5: deterministic `check_slide_iteration_limit` helper (counts consecutive RED qa_log entries per slug). REQ-SLIDE-14: prompt-level oscillation detection in consultant.md (LLM reads revision_instructions for semantic contradictions). Removed dead `red_green_iteration` field from DebriefState. **Spec gap:** the spec described these features in terms of routing-loop callbacks that were deleted. **Blueprint recommendation:** when a spec requirement references a deleted mechanism, the blueprint author must redesign the enforcement path for the current architecture (deterministic helper + LLM-mediated detection).

---

### BUG-AUDIT-36: PARTIAL items — export first-run + prompt enrichment + preview exemption

REQ-LIFE-2: `main_export` now auto-creates the first PresentationRecord if presentations is empty (self-bootstrapping). REQ-CONSULT-2/9/11: archetype confirmation + export transition dialog in consultant.md. REQ-ASSET-1..5: image handling in slide-maker.md. BC-7.8/BC-9.5/BC-9.6: verified as already working (preview exempt via path filter; INV-10 reads style_config dynamically). **Spec gap:** REQ-LIFE-2 described folder creation logic that lived in the deleted routing loop. **Blueprint recommendation:** when the routing loop is removed, every state-creation step it performed must be re-homed to the command that needs it (export creates its own presentation record).

---

### BUG-AUDIT-37: 7 veto rules (REQ-QA-2)

3 programmatic (VETO-01 text overflow, VETO-04 raw source, VETO-06 slug in content) in qa_checker.py. 4 VLM-only (VETO-02 blank, VETO-03 missing content, VETO-05 prompt artifacts, VETO-07 caption placement) in visual-qa.md. `veto` field in qa_log entries now set to True when vetoes fire. **Spec gap:** the spec defined 7 veto rules but the veto field was always False in code. **Blueprint recommendation:** every REQ that defines behavioral rules (like veto) should have a corresponding BC that names the function implementing each rule and specifies the exit/flag behavior.

---

### BUG-AUDIT-38: 10 remaining programmatic INV checks

INV-12 (valid HTML5), INV-13 (image margins), INV-14 (math overflow), INV-15 (diagram errors), INV-16 (fonts loadable), INV-17 (CSS vars defined), INV-19 (image paths exist), INV-20 (image aspect ratio), INV-22 (inline math line-height), INV-23 (math assets exist). QA system now has 15 programmatic + 3 veto + 11 VLM checks covering all 24 INV + 7 VETO rules. **Spec gap:** spec defined 24 invariants but only 5 were implemented. **Blueprint recommendation:** the implementation stage should track INV-check coverage as a metric and block Stage 5 delivery if coverage is below 100% for programmatic checks.

---

### BUG-AUDIT-39..42: Smoke-test bugs — PPTX adapter, CSS naming, export subprocess, soffice discovery

Six bugs found by component smoke-testing with a real 4-slide PPTX. Spec-vs-code analysis:

**BUG-2 (PPTX multi-slide):** Spec §24.25.1 correctly mandates "one PNG per slide" but is silent on the conversion method. The code used `soffice --convert-to png` which only renders the first slide. Fixed by two-step PPTX→PDF→PNG via fitz. **Spec amendment:** conversion method MUST be two-step (PPTX→PDF→PNG); single-step `--convert-to png` is a known-broken anti-pattern and MUST NOT be used. Post-conversion validation (compare PNG count vs slide count) is mandatory.

**BUG-1/3 (metadata extraction):** Spec §24.25.1 mandates extraction and preservation but is silent on partial-failure handling and schema. **Spec amendment:** `analyzer_metadata.json` MUST use a defined schema; fields that cannot be extracted are omitted (not null). Extraction failure MUST NOT block the image batch.

**BUG-4 (CSS variable naming):** Spec §24.16 defines the canonical CSS_PROPERTY_MAP but doesn't mandate compile-time validation. Unmapped keys silently get fallback names that don't match slide expectations. **Spec amendment:** the compiler MUST warn (or error) on any config key not in CSS_PROPERTY_MAP. Fallback naming without warning is an anti-pattern.

**BUG-5 (export subprocess):** Spec §24.10 mandates `python -m debrief.style_compiler` subprocess. The code couldn't find the module outside the conda env. Fixed by direct in-process function call. **Spec amendment:** the style compiler MUST be callable both as a subprocess and as a direct import. In-process calling is preferred for reliability; subprocess is acceptable only when the module is guaranteed importable.

**BUG-6 (LibreOffice discovery):** Spec §24.25.1 documents macOS discovery only. Linux is missing despite NFR-PORT-1 mandating Linux support. **Spec amendment:** discovery MUST be platform-aware (macOS known path, Linux shutil.which + known paths, Windows known paths). Discovered path MUST be persisted to `.debrief/soffice_path` and revalidated on each bootstrap.

---

## Prior-Art for Rebuild: Smoke-Test Lessons (BUG-AUDIT-39..42)

These lessons apply to a future from-scratch rebuild. They supplement the Per-BUG-AUDIT Prior-Art entries in the individual Bug Catalog entries above.

1. **Two-step conversion is mandatory for multi-page document imports.** Any time LibreOffice converts a multi-page format (PPTX, ODP, DOCX) to a raster format, the single-step `--convert-to png/jpg` path renders only the first page. The correct pipeline is always: document → PDF (all pages) → per-page raster via fitz. A rebuild MUST enforce this in the spec's adapter contracts. The blueprint author should add a "forbidden methods" section to each adapter contract listing single-step conversions that are known to lose pages.

2. **Config schema validation is a compiler responsibility.** The style compiler should not silently accept keys it doesn't recognize. A rebuild should treat the CSS_PROPERTY_MAP as a closed set — any key not in the set is a drift signal that must be surfaced before CSS is generated. The blueprint author should add a validation contract: "the compiler MUST exit non-zero on unknown keys."

3. **Subprocess vs in-process is an architectural decision.** The original spec mandated subprocess for the style compiler. The prototype discovered this is fragile (requires pip install). A rebuild should explicitly choose: in-process (simpler, no install dependency) or subprocess (isolation, but requires module availability). The blueprint author should document the tradeoff in the implementation unit's prose.

4. **Cross-platform dependency discovery must be spec-level, not code-level.** The macOS-only soffice shim was a code-level hack that the spec didn't mention for Linux. A rebuild spec MUST enumerate every system dependency with per-OS discovery algorithms. The blueprint author should create a "System Dependencies" section in the spec listing: dependency name, minimum version, per-OS discovery strategy, persistence mechanism, and user-facing error message for missing dependencies.

5. **Smoke-test with real artifacts before shipping.** The 6 bugs were invisible to the 1425-test suite because all tests used synthetic data. A real PPTX exposed bugs that synthetic HTML slides and mocked subprocesses could never catch. A rebuild should include at least one integration test that processes a real multi-page PPTX end-to-end. The test artifact should be committed to the repo.

6. **CSS values in config must be parsed defensively.** The canonical `style_config.json` stores layout dimensions as CSS strings ("1920px"). Any code that needs integer pixels MUST use a parsing utility (like `parse_css_int`) that strips unit suffixes. The blueprint author should add a contract: "all consumers of layout dimensions MUST accept both integer and CSS-string forms."

7. **python-pptx font extraction is unreliable for inherited fonts.** `run.font.name` returns `None` when the font is inherited from the slide master. The blueprint author should document this as a known limitation and require fallback to `para.font.name` and the slide layout's default theme font.

---

### BUG-AUDIT-43: CSS-unit parsing + font extraction fallback (agent smoke-test)

Three bugs found by agent-driven end-to-end smoke test (10-step workflow with real 4-slide PPTX):

**BUG-ST-2/3 (HIGH):** `qa_checker.check_aspect_ratio()` and `export.main_export()` crashed on CSS string layout values ("1920px") from the canonical template. Both called `int(value)` which raises on "1920px". Fixed by adding `parse_css_int()` utility to `debrief_state.py`. **Spec amendment:** any code consuming `style_config.json` layout dimensions MUST accept CSS-string forms.

**BUG-ST-1 (LOW):** `font_families` empty in PPTX metadata because `python-pptx` returns None for `run.font.name` when inherited from slide master. Fixed with paragraph-level font fallback.

---

## Blueprint Author's Guide: Consolidated Lessons from 43 BUG-AUDITs

This section consolidates every Prior-Art lesson from BUG-AUDIT-1 through -43 into a single reference for the blueprint author of a future rebuild. Organized by theme, not by BUG-AUDIT number.

### Architecture

1. **Consultant-orchestrated, not routing-loop.** The SVP-era routing loop (main_routing → main_update_state → main_prepare) was dead at runtime from day one. The consultant agent handles all dispatch via Tool calls. A rebuild MUST NOT reintroduce machine gates, state-transition tables, or automated routing cycles for a presentation tool. (BUG-AUDIT-17, -19, -20, -31)

2. **input() is an anti-pattern in plugin functions.** The consultant mediates all user interaction via Tool parameters. Python functions MUST NOT block on stdin. (BUG-AUDIT-22)

3. **Subprocess calls to internal modules are fragile.** `python -m debrief.X` requires pip-install. Prefer direct in-process function calls for intra-plugin invocations. Reserve subprocess for system dependencies (soffice, playwright). (BUG-AUDIT-41)

4. **Every command must be callable independently.** Handout without prior export, script without prior handout. Decouple output artifacts from each other. (BUG-AUDIT-21)

### Preconditions and Error Handling

5. **Every command entry point MUST validate preconditions at entry** with named, fix-instruction error messages. No raw Python tracebacks ever reach the user. (BUG-AUDIT-21, -23, -24, -25, -32)

6. **Precondition order matters.** Check project existence → check data prerequisites → check environment (playwright, fitz). Report the most actionable error first. (BUG-AUDIT-21, -23)

7. **Silent fallbacks are worse than loud failures.** The export's PyMuPDF ImportError fallback silently dropped all pages after the first. Every fallback MUST either produce equivalent output or fail with a clear message. (BUG-AUDIT-23)

8. **The orchestrator agent prompt MUST enumerate every dispatchable command** with its preconditions. "If unsure, ask the user" beats "guess and waste agent turns." (BUG-AUDIT-33)

### Versioning and State

9. **Filesystem-derived versioning beats state-field counters** for append-only artifacts. Scan the output directory for existing files, pick max+1. No state mutation, no migration headaches. (BUG-AUDIT-21, -23, -25)

10. **Auto-save before any state-mutating operation.** Restore creates a pre_restore snapshot before overwriting. This pattern makes every mutation reversible. (BUG-AUDIT-22)

11. **Restore, not hard-delete.** Users never want to lose everything. The "start over" command should roll back to a snapshot, not delete all files. (BUG-AUDIT-22)

### QA System

12. **Every INV and VETO rule defined in the spec MUST have a corresponding implementation** — programmatic check in qa_checker.py OR VLM instruction in visual-qa.md. Track coverage as a metric; block delivery if below 100%. (BUG-AUDIT-37, -38)

13. **Veto rules are hard blockers; INV checks are quality gates.** The qa_log `veto` field must be True when a VETO fires. The consultant must refuse to advance past a veto. (BUG-AUDIT-37)

14. **Mocked tests for artifact generation are worse than no tests.** A mocked `page.pdf()` that returns `b"%PDF mock"` catches nothing. Every command that generates an artifact needs at least one real-integration test that writes actual bytes and asserts %PDF magic. (BUG-AUDIT-21, -23)

### File Formats and Parsing

15. **CSS values in style_config.json MUST be parsed defensively.** The canonical template stores layout dimensions as CSS strings ("1920px"). Use `parse_css_int()` everywhere — never raw `int()`. (BUG-AUDIT-43)

16. **Config schema validation is a compiler responsibility.** The CSS_PROPERTY_MAP is a closed set. Unknown keys MUST produce a warning (or error) at compile time, not silently get fallback names. (BUG-AUDIT-40)

17. **Two-step conversion for multi-page documents.** LibreOffice `--convert-to png` renders only the first page. ALWAYS convert via PDF intermediate (document → PDF → per-page PNG via fitz). Post-conversion validation: compare PNG count against page count. (BUG-AUDIT-39)

### Cross-Platform and Dependencies

18. **Cross-platform dependency discovery must be spec-level.** Every system dependency (soffice, playwright, chromium) needs per-OS discovery algorithms, persistence of the found path, and user-facing error messages for missing dependencies. (BUG-AUDIT-4, -42)

19. **LibreOffice is a prerequisite, not a managed dependency.** Document it in README alongside Python and Conda. The launcher discovers but does not install it. (BUG-AUDIT-4, -42)

20. **python-pptx font extraction is unreliable for inherited fonts.** `run.font.name` returns None when the font comes from the slide master. Always fall back to paragraph-level and layout-level defaults. (BUG-AUDIT-43)

### Plugin Structure

21. **Commands live in `commands/`, not `skills/`.** Filenames are bare `<name>.md` with no plugin prefix. Claude Code namespaces them automatically as `/debrief:<name>`. (BUG-AUDIT-9, -10)

22. **Project-scoped settings via `.claude/settings.json`**, not `--plugin-dir` flags. The launcher writes settings; Claude Code reads them. (BUG-AUDIT-8)

23. **hooks.json requires the top-level `hooks` wrapper** and each entry needs the tool-matcher structure. Agent-type hooks are broken upstream; use command-type hooks + Task dispatch. (BUG-AUDIT-7, -12, -17)

### Testing

24. **Smoke-test with real artifacts before shipping.** Synthetic test data hides bugs that real PPTX/PDF files expose (multi-page rendering, font extraction, CSS-unit parsing). Commit at least one real test artifact to the repo. (BUG-AUDIT-39..43)

25. **Behavioral tests (Tier 1) survive rebuilds; implementation tests (Tier 2) don't.** Write acceptance tests that interact via CLI and file I/O, not internal function imports. See `REBUILD_PROCEDURE.md`. (BUG-AUDIT-21)

26. **Standing sentinel tests prevent regression classes.** The phantom-import sentinel catches typo imports; the BC-named-orphan sentinel catches unconnected helpers. Keep these as structural defenses. (BUG-AUDIT-18, -20)

### Spec Discipline

27. **The spec is a discovery log, not a build contract** (for the prototype). Append-style changes are legal; editing existing structure to integrate a new feature triggers a rebuild. (BUG-AUDIT-28)

28. **Every Bug Catalog entry should have a Prior-Art for Rebuild section** documenting what the rebuild should adopt or avoid. The bug fix is ephemeral; the lesson is permanent. (BUG-AUDIT-21+)

29. **Vocabulary must be consistent.** The spec and code must use the same term for the same concept. If the code uses STYLE REVISE, the spec must not say STYLE NEEDS WORK. (BUG-AUDIT-29)

---

### BUG-AUDIT-46: Archetype system spec amendment — 10 archetypes + universal principles + /debrief:present

**Spec gap.** The archetype data existed (`archetypes.json` with 8 entries) but the spec had no requirements for archetype-aware behavior. The consultant treated all archetypes identically. Additionally, no spec coverage existed for universal presentation principles (rhetoric, progressive disclosure, citations, confidentiality, video, etc.) or browser-based presentation mode.

**Fix.** Added three new spec sections via Socratic dialog with the user:
- §14.14 Presentation Archetypes (REQ-ARCH-1..10): 10 archetypes with full rhetorical instructions, sub-modes, audience rules, acknowledgment policies
- §14.15 Universal Presentation Principles (REQ-UNIV-1..21): organic narrative flow, progressive disclosure, assets/references/BibTeX, confidentiality, sparring, visual rules, video, pacing, audience calibration
- §14.16 Presentation Mode (REQ-PRESENT-1..5): browser-based full-screen presentation with keyboard navigation

New archetypes added: investor_pitch, thesis_discussion. Custom redefined as meta-archetype.

---

### BUG-AUDIT-51..54: Smoke test Round 1 — 19 bugs found, 16 fixed, 2 architectural fixes

**19 bugs found** by agent-driven 10-step smoke test with real PPTX. All 10 steps passed but with caveats. Six HIGH, eight MEDIUM, five LOW.

**BUG-AUDIT-51** (7 quick fixes): qa_checker viewport 1920x1080, export __main__ block, resolve() relative paths, VETO-01 skip html/body, stale shims gutted, CLAUDE.md routing ref removed, MuPDF warnings suppressed.

**BUG-AUDIT-52** (3 medium fixes): SlideRecord defensive parsing (d.get with defaults for title/status/backup), snapshot validation before restore (read_deck_state on snapshot before overwriting), stylist gets Bash tool.

**BUG-AUDIT-53** (4 prompt fixes): stylist reads reference PNGs explicitly, slide-maker never adds external font links, slide-maker doesn't claim Tier 1 PASS without evidence, consultant pushes back on off-range duration.

**BUG-AUDIT-54** (2 architectural fixes): (1) Slide-maker runs qa_checker explicitly via Bash — PostToolUse hooks don't fire in subagent sandboxes, so hooks are defense-in-depth, not primary enforcement. (2) write_debrief_state auto-appends a ledger entry after every successful state write — ledger is never empty.

## Blueprint Author's Guide: Additions from Smoke Test (items 30-34)

30. **Subagent hooks are not reliable.** PostToolUse hooks don't fire in Task-dispatched subagent sandboxes. Any QA or validation that depends on hooks must have an explicit fallback path in the agent prompt. The blueprint author should treat hooks as defense-in-depth, not primary enforcement. (BUG-ST-10)

31. **Ledger auto-append on state transitions.** The ledger must never be empty after a session. Every `write_debrief_state` call should auto-append a structural event entry. Conversational entries are optional consultant-contributed enrichment. (BUG-ST-15)

32. **SlideRecord schema must be validated on write, not just read.** Defensive parsing with defaults prevents downstream crashes but masks the root cause (consultant wrote malformed state). The blueprint author should add a `validate_and_write_slide` helper that the consultant MUST use. (BUG-ST-17)

33. **CLI entry points must have `__main__` blocks.** Every module that documents `python -m debrief.X` must have a corresponding `if __name__ == "__main__":` footer. Add a structural sentinel test. (BUG-ST-16)

34. **Relative paths must be resolved at entry.** Every CLI entry point must call `.resolve()` on path arguments before any file I/O. (BUG-ST-18)

35. **Style-lock utilities are NOT routing-loop code.** `promote_style_draft` copies drafts to project root, compiles CSS, and sets `style_locked`. BUG-AUDIT-31 deleted it as "dead routing code" — it wasn't. The blueprint author must classify functions by whether they serve a USER-FACING workflow step (keep) vs whether they only fire from the deleted routing loop (delete). (BUG-ST-4)

36. **Every agent-writable state field must be documented in the agent prompt.** If the consultant writes to `deck_state.json` without knowing the exact field names, it writes non-canonical fields that get silently dropped on the next read cycle. The blueprint author must include the full schema table in the orchestrator's prompt. (BUG-ST-13)

37. **Universal principles must not contradict stylist-authored style guides.** If a universal principle says "always do X" and the stylist's style guide says "never do X," the slide-maker and QA cannot both be satisfied. Any universal principle that can be overridden must say so explicitly, with the override path documented. (BUG-ST-7)

38. **Script generation requires enriched content_summary.** The deterministic script generator uses `content_summary` verbatim for narration. If the consultant writes only topic labels ("Results"), the script emits placeholder transitions. The consultant must populate each slide's `content_summary` with real narration text including transitions BEFORE invoking the script generator. (BUG-ST-14)

39. **Valid sub_phase values must be enumerated in the orchestrator prompt.** Without a documented enum, the consultant invents values that pass the write but crash on the next read. Include the full `SUB_PHASE_VALUES` list. (BUG-ST-15)

40. **Style compiler must emit a default slide background rule.** Without `.slide { background-color: var(--color-background); }`, the container computes transparent, Playwright renders over black, and INV-04 (contrast) fails on the very first slide. (BUG-ST-10)

41. **Library-name matching must be exact, not substring.** Substring matching `"rough" in src` false-positives when the permitted list says `"rough.js"`. Normalize both sides by stripping `.js`/`.min.js` suffixes before comparison. (BUG-ST-9)

---

### BUG-AUDIT-55..58: Smoke test Round 1b — 15 bugs including CRITICAL style-lock

**CRITICAL (BUG-ST-4):** `promote_style_draft` was prematurely deleted in BUG-AUDIT-31 as "routing-loop dead code." It is NOT routing code — it's a style-lock utility that copies draft files to project root, compiles CSS, and sets `style_locked`. Without it, no user could lock a style after the style dialog. Restored as a standalone function in `utility_skills.py` with CLI access via `python -m debrief.utility_skills promote_style_draft`.

**HIGH (4):** (1) CLI `__main__` dispatcher for save/restore/quit/present/view added to utility_skills.py. (2) SlideRecord schema + SUB_PHASE_VALUES enumerated in consultant.md — prevents consultant from writing non-canonical fields that get silently dropped. (3) Script transition quality — consultant now enriches `content_summary` with real transitions before generating script. (4) Slide numbering universal principle revised: default ON, stylist may opt out for minimalist styles.

**MEDIUM (6):** INV-10 exact library matching (rough.js no longer false-positive). Default `.slide` background in compiler output. roughjs_defaults added to canonical template. Slide-maker reads and respects anti-patterns section. Ledger auto-append already wired (BUG-AUDIT-54). SUB_PHASE_VALUES documented.

**LOW (4):** CLAUDE.md template reset→restore. Duration push-back already in prompt. style_analyzer CLI cosmetic. @import in previews cosmetic.

**Prior-Art for Rebuild:** When deleting "dead" code during a pruning pass, classify each function by whether it serves a USER-FACING workflow step (style-lock is user-facing: the user says "STYLE APPROVED" and the system promotes drafts) vs whether it only fires from an automated routing loop (the routing loop is dead, so its entry points are dead). Functions that serve user-facing steps must be preserved even if their only caller was the routing loop — they need a NEW caller (the consultant, a CLI shim, or a command).

### BUG-AUDIT-59: Smoke test Round 2 — 13 bugs (0 CRITICAL, 2 HIGH, 6 MEDIUM, 7 LOW)

**HIGH (2):**
- **BUG-ST-5:** slide-maker subagent cannot dispatch `Task` when invoked from another subagent (consultant → slide-maker → visual-qa fails). Claude Code platform limitation: nested subagents do not inherit the Task tool. Fix: consultant is the canonical Tier 2 (visual-qa) dispatcher. slide-maker runs Tier 1 qa_checker via Bash and returns; consultant dispatches visual-qa after slide-maker returns. Updated slide-maker.md and consultant.md.
- **BUG-ST-12:** Script generator emits placeholder transitions even when `content_summary` contains a real transition sentence. Fix: `generate_script_content` now extracts the last sentence from `content_summary` if it contains transition-signal words (e.g., "next", "which leads", "sets the stage"), and uses it as the Transition block instead of the hardcoded placeholder.

**MEDIUM (6):**
- **BUG-ST-6:** rough.js canvas rendering needs a `load` guard; slide-maker's default template did not include one. Fix: added constraint to slide-maker.md requiring `window.addEventListener('load', () => { requestAnimationFrame(() => { ... }); })` wrapping for all rough.js canvas code.
- **BUG-ST-8:** `ledger.jsonl` never produced during discovery/style/production because the consultant writes state directly, bypassing `write_debrief_state`'s auto-append. Fix: added `append_ledger` CLI subcommand to debrief_state.py; consultant.md instructs explicit ledger entry after every major state transition.
- **BUG-ST-10:** NOT A BUG. `export_count` stays at 0 because filesystem-derived versioning (BUG-AUDIT-23) made the field vestigial. The export correctly produces `deck_v001.pdf`, `deck_v002.pdf`, etc. by scanning existing files.
- **BUG-ST-13:** Script generator omits time-pacing checkpoints required by Universal Principle 20. Fix: `generate_script_content` now accepts `total_duration_minutes`, computes per-slide time, and inserts checkpoints at 25%, 50%, 75% marks. `main_script_generator` parses duration from `deck_brief.md`.
- **BUG-ST-14:** `.debrief/state.lock` persists after quit. Fix: `skill_quit` now deletes the lock file after flushing state.
- **BUG-ST-15:** No CLI helper for consultant-side state transitions; hash warnings inevitable when consultant writes `debrief_state.json` directly. Fix: added `update` CLI subcommand to debrief_state.py that reads/modifies/writes via the proper `write_debrief_state` path, recomputing hash and auto-appending ledger.

**LOW (7):**
- **BUG-ST-1:** No tool for archetype duration validation. Fix: added `check_duration` function to launcher.py with CLI access.
- **BUG-ST-2:** `style_analyzer` silent on success. Fix: prints slide count and metadata confirmation to stderr after import.
- **BUG-ST-3:** Stylist falsely reported a `style_compiler` packaging bug. Fix: added "verify before reporting" constraint to stylist.md.
- **BUG-ST-4:** `CLAUDE_PLUGIN_ROOT` path ambiguous for subagents. Fix: documented fallback cache path in stylist.md.
- **BUG-ST-7:** Positive observation — red-green loop works end-to-end. No fix needed.
- **BUG-ST-9:** Export confirmation message doesn't name the PDF. Fix: added success print to export.py.
- **BUG-ST-11:** Handout CLI requires `--mode` with no default. Fix: added `handout` command to utility_skills.py CLI with `--mode` defaulting to `2up`.

---

#### Blueprint Author's Guide additions (BUG-AUDIT-59)

42. **Nested subagents cannot dispatch Task.** Claude Code does not surface the `Task` tool to agents invoked from within another agent. Only the top-level orchestrator (consultant) can dispatch other agents. If a design requires A → B → C dispatch, restructure so A dispatches B, waits for B to return, then dispatches C. (BUG-ST-5)

43. **Filesystem-derived versioning makes state counters vestigial.** When a module scans for existing files (e.g., `deck_v*.pdf`) to derive the next version number, the corresponding state field (e.g., `export_count`) is never incremented. Do not file bugs against zero-valued counters when filesystem scanning is the intended versioning mechanism. Document which counters are vestigial. (BUG-ST-10)

44. **Consultant must be the canonical Tier 2 dispatcher.** Due to the nested-Task limitation (item 42), the consultant — not the slide-maker — dispatches visual-qa for Tier 2 VLM review. The slide-maker runs only Tier 1 (qa_checker via Bash) and returns. The consultant reads the Tier 1 result and dispatches Tier 2 before presenting the gate prompt. (BUG-ST-5)

45. **Provide CLI helpers for every state mutation the orchestrator performs.** If the orchestrator writes a state file directly (via Write tool), it bypasses hash recomputation, ledger auto-append, and atomic write guarantees. Every state file that has integrity mechanisms (hash, lock, ledger) needs a CLI helper that the orchestrator calls instead of writing directly. (BUG-ST-15, BUG-ST-8)

---

### BUG-AUDIT-60: Smoke test Round 3 — 12 bugs across Profiles A/C/cross (5 HIGH, 3 MEDIUM, 4 LOW)

Round 3 exercised the full pipeline in one `debrief new` session (conference_talk, 5-min AI revolution script), then Profile C feature spot-checks (images, video, confidentiality, math, acknowledgment, style re-lock, iteration limit, filesystem versioning), then cross-profile verification. Results: `profile_a.md`, `profile_c.md`, `cross_profile.md` in `~/smoke_test/results/`.

**Cluster 1 — Sub_phase state management (2 HIGH, 1 LOW):**

- **BUG-ST-a-2 (HIGH):** `consultant.md` §"Valid sub_phase Values" drifted from the authoritative enumeration (spec §14.17 + blueprint BC-2.15 + `SUB_PHASE_VALUES` in `debrief_state.py`). Consultant card listed 9 values that do not exist in code (`discovery/reference_import`, `production/brief_dispatch`, `production/slide_authoring`, `production/backup_decision` (code places under `finalization/`), `production/closing_slide`, `finalization/export_ordering`, `finalization/complete`, `complete/done`, `complete/idle`) and omitted 9 that do. Secondary: `write_debrief_state` did not invoke `validate_debrief_state` before writing — invalid sub_phase values persisted to disk and produced `StateCorruptError` on the next read. **Detection:** smoke test A7 wrote `production/backup_decision`; A8 read failed. **Fix:** (a) replace consultant.md's enumeration with the canonical 24-value list; (b) `write_debrief_state` now calls `_validate_state_fields(data)` before `atomic_write_json` and raises `StateCorruptError` on invalid values (file on disk unchanged, lock released via `finally`); (c) new regression test enforces consultant.md ≡ `SUB_PHASE_VALUES`.

- **BUG-ST-a-3 (HIGH):** Smoke test prompt `SMOKE_TEST_PROMPT.md` A14 instructions used `finalization/complete` and `complete/done` — both invalid. Symptom of a-2 (plan author copied from consultant.md). **Fix:** smoke prompt updated to `finalization/post_export` and bare `complete`.

- **BUG-ST-a-5 (LOW):** `cli_update_state` set fields blindly with no coupling between `sub_phase` prefix and `phase`. A consultant-side `--set sub_phase=production/slide_review` left `phase=discovery`, causing `/debrief:view` (which gates on `phase`) to misfire with "No slides yet." **Fix:** `cli_update_state` now derives `phase` from the `sub_phase` prefix when `sub_phase` is set without an explicit `phase`; when both are passed, they must agree (phase == sub_phase.split('/')[0]) or the command exits 1 with a descriptive error.

**Cluster 1 new normative requirements (amends §14.17):**

- **REQ-STATE-ENUM-1:** The consultant-facing `sub_phase` enumeration (consultant.md §"Valid sub_phase Values") MUST be set-equal to `SUB_PHASE_VALUES` in `debrief_state.py`. A regression test MUST parse both and assert equality. Drift is a CRITICAL bug class.

- **REQ-STATE-ENUM-2:** `write_debrief_state` MUST invoke `validate_debrief_state` on the serialized dict before `atomic_write_json`. A failed validation MUST raise `StateCorruptError` and leave the on-disk file unchanged. The lock MUST be released in a `finally` block regardless of outcome.

- **REQ-STATE-ENUM-3:** `cli_update_state` MUST derive `phase` from the `sub_phase` prefix when the user passes `sub_phase` without an explicit `phase`. When both are passed, they MUST be consistent (`phase == sub_phase.split('/')[0]`). Inconsistent pairs MUST cause the command to exit 1 with a message naming the conflict.

**Cluster 2 — KaTeX false positives (2 HIGH):**

- **BUG-ST-c-1 (HIGH):** `_KNOWN_DIAGRAM_LIBS` in `qa_checker.py:175` included `katex`. INV-10 (`check_permitted_libraries`) therefore failed every math slide unless the user added `katex` to `constraints.permitted_diagram_types`. But KaTeX is a math renderer, not a diagram library; its assets are gated separately by `validate_math_renderer_assets` (line 638+) keyed on `constraints.math_renderer`. **Fix:** removed `katex` from `_KNOWN_DIAGRAM_LIBS`. Math-renderer enforcement remains intact via the existing separate path.

- **BUG-ST-c-2 (HIGH):** VETO-01 (`check_text_overflow`) flagged `SPAN.katex-mathml` as overflowing its container. KaTeX renders a hidden accessibility sibling span using the standard screen-reader-only pattern (`position:absolute; clip:rect(1px,1px,1px,1px); overflow:hidden; width:1px; height:1px`) — visually invisible but `scrollWidth > clientWidth`. The check caught all such a11y-hidden elements. **Fix:** `check_text_overflow` now skips elements with `aria-hidden="true"` or class `katex-mathml` / `sr-only` / `visually-hidden`.

**Cluster 2 new normative requirements (amends §14.17 / Section 24 QA contracts):**

- **REQ-QA-INV10-1:** INV-10's diagram-library check MUST NOT include math renderers. KaTeX (and any future math renderer) is gated by `constraints.math_renderer`, not by `constraints.permitted_diagram_types`. `_KNOWN_DIAGRAM_LIBS` MUST enumerate only true diagram libraries.

- **REQ-QA-VETO01-1:** VETO-01 overflow detection MUST exclude elements that are intentionally hidden for accessibility. The exclusion set MUST include: `aria-hidden="true"`, class `katex-mathml`, class `sr-only`, class `visually-hidden`. A regression test MUST render a slide with KaTeX math and assert VETO-01 does not trip.

- **Cluster 2 (2 HIGH):** BUG-ST-c-1 (INV-10 conflates KaTeX with diagram libraries), BUG-ST-c-2 (VETO-01 false-positives on `SPAN.katex-mathml` hidden a11y markup). Fix surface: `qa_checker.py`.
**Cluster 3 — Script duration parser (1 HIGH):**

- **BUG-ST-a-4 (HIGH):** `_parse_duration_from_brief` in `utility_skills.py:451` had two regex defects. (1) Primary pattern `(?:duration|time|length)\s*[:=]\s*(\d+)\s*(?:min|minute)` required strict whitespace-or-colon between the keyword and the digit; it failed on `**Duration:** 5 minutes` because `**` is neither whitespace nor colon. (2) Fallback pattern `(\d+)\s*[-\s]?\s*(?:minute|min)\b` placed `\b` after `minute`, but `\b` does not match between `e` and `s` (both word characters) — so "5 minutes" (plural) silently failed. Fallback then picked up "45 min" from the duration-warning sentence ("5 min is below conference_talk range (10-45 min)"), causing the script to report `Target duration: 45 minutes` for a user who asked for 5. **Fix:** primary now allows `[\s:*=\-]{0,8}?` between keyword and digit (accepts markdown bold markers, capped at 8 chars to prevent cross-sentence false matches); both patterns add `s?` before `\b` to accept the plural. Regression test covers the exact smoke-test brief shape.

- **Cluster 3 (1 HIGH):** BUG-ST-a-4 (`_parse_duration_from_brief` regex misses markdown-bold headings and plural "minutes" → picks up "45 min" from warning text instead of user's "5 minutes"). Fix: loosen keyword/digit gap and add `minutes?` alternation.
**Cluster 4 — Ledger path divergence (1 MEDIUM + xref):**

- **BUG-ST-c-3 / BUG-ST-xp-3 (MEDIUM):** Two `append_ledger_entry` functions coexist: `debrief_state.py:819` writes to `project_root/ledger.jsonl` (correct — spec §3 layout, BC-11.10 snapshot behavior, project_claude.md discovery-resume instructions), while `ledger.py:193` wrote to `project_root/.debrief/ledger.jsonl`. When the consultant (or any caller) imported the `ledger.py` version, its entries went to a second file the rest of the pipeline never read. Save/snapshot captured only the root ledger; `tail ledger.jsonl` missed events; audit trail fragmented. **Fix:** `ledger.py` now writes to `project_root/ledger.jsonl`; compact archives (`ledger_compact_NNN.jsonl`) also live at project root for consistency. `_next_compact_index` parameter renamed for clarity.

- **Cluster 4 (1 MEDIUM, 1 xref):** BUG-ST-c-3 / BUG-ST-xp-3 (ledger fragmentation: `debrief.ledger.append_ledger_entry` writes to `.debrief/ledger.jsonl`, but the project root `ledger.jsonl` is the CLAUDE.md-documented canonical path). Fix: consolidate to root.
**Cluster 5 — Export/presentation desync (1 MEDIUM, 1 LOW):**

- **BUG-ST-xp-1 (MEDIUM):** `output/presentation.html` was generated only by `/debrief:present`, never refreshed by subsequent `/debrief:export` runs. After re-export, the counter ("1/6") and embedded bodies drifted from the live PDF ("1/8"). **Fix:** extracted `build_presentation_html(project_root)` from `main_present` (browser-less writer). `main_export` now calls it post-PDF-write, so every export keeps `presentation.html` in sync. Best-effort — failure logs a note, does not fail the export.

- **BUG-ST-xp-2 (LOW):** `presentation.slide_manifest` was populated at the first export (from approved non-backup slugs) and then never updated. On re-export the same record is reused, so `slide_manifest` froze at 4 while the deck grew to 8. **Fix:** `main_export` now refreshes `presentation.slide_manifest` from the live approved non-backup slug list on every export and calls `write_deck_state` when the list changed.

**Cluster 6 — Minor polish (2 LOW):**

- **BUG-ST-a-1 (LOW):** slide-maker agent card contained contradictory guidance — line 34 said "Do NOT claim 'Tier 1 PASSED'" while line 134 said "Include the Tier 1 result summary (PASS/FAIL...)". Slide-maker defaulted to the permissive phrasing. **Fix:** reconciled line 134 to require only the qa_log path + failing IDs; explicit prohibition on verdict claims. Gate decisions remain consultant-only.

- **BUG-ST-c-4 (LOW):** `python -m debrief.qa_checker check_limit --help` did not disclose the default limit (5). **Fix:** added a descriptive `help=` string to the `--limit` argument including the default.

- **Cluster 5 (1 MEDIUM, 1 LOW):** BUG-ST-xp-1 (`presentation.html` stale after re-export — not regenerated), BUG-ST-xp-2 (`deck_state.presentations[].slide_manifest` frozen at initial export).
- **Cluster 6 (2 LOW):** BUG-ST-a-1 (slide-maker return text says "Tier 1 PASSED" — violates BUG-ST-14 agent-card guidance). BUG-ST-c-4 (`check_limit --help` does not disclose default of 5).

**Round 3 Prior-Art for Rebuild:**
- Any enumeration documented in more than one place (agent card, spec, code constant) is a drift risk. Either consolidate to one source of truth that the other two cite by reference, OR add a regression test that reads all copies and asserts equality. Drift discovered by users in production is too late.
- Write-path validation is not optional when the read path validates. An asymmetric validator creates a store-then-crash pattern that is worse than no validation (corrupts the audit trail, wastes the user's session).
- CLI field mutations that touch a tuple of coupled fields (phase/sub_phase, current_slide_slug/current_group_id) MUST either co-validate or derive one from the other. Blind attribute-set is unsafe when the data model has invariants between fields.

---

### BUG-AUDIT-61: Smoke test Round 4 — 2 new bugs (2 MEDIUM); BUG-AUDIT-60 fixes all hold

Round 4 ran against the fixed plugin (BUG-AUDIT-60 applied). All 11 fix-validation checkpoints held. Two new bugs surfaced.

**BUG-ST-round4-c-1 (MEDIUM, design tension):** REQ-ASSET-2 mandates `<img>` embed for user-provided images. INV-13 (`check_images_respect_margins` in `qa_checker.py:707`) mandates 10% horizontal margin on every `<img>`. Full-bleed images (REQ-ASSET-4 placement mode) have 0 margin by definition — the two requirements structurally conflict. The slide-maker worked around this by embedding a 0×0 `<img>` tag plus CSS `background-image: url(...); background-size: cover`. Works, but is a hack that obscures REQ-ASSET-2's intent. **Fix:** INV-13 now exempts any `<img>` that has class `fullbleed` or an ancestor with class `fullbleed`. Slide-maker guidance updated to use `<img class="fullbleed" src="...">` directly for full-bleed placement, removing the workaround.

**BUG-ST-round4-a-1 (MEDIUM, KB-2):** `/debrief:restore` overwrites `deck_state.json` from the snapshot (per BC-11.11) and scopes its destructive action to `deck_state.json` + optionally `ledger.jsonl` + orphan `slides/*.html` (per BC-11.12). Export folders under `output/<YYYY_MM_DD_*>/` are explicitly out of scope — they survive the restore. But the restored `deck_state.presentations` may be empty or reference different folders, leaving PDFs/scripts/handouts on disk that look active but are orphaned from the live state. No warning was emitted. Detected by Round 4 Phase 4: `deck_v001.pdf` / `deck_v002.pdf` / `script_v*.md` survived a restore that wiped `presentations` to `[]`. **Fix:** after the restore sequence, `skill_restore` now enumerates `output/<YYYY_MM_DD_*>/` folders, diffs against restored `presentations[].folder`, and for each orphan prints a warning to stderr naming the folder + its file count AND appends a `{"event": "restore_orphan_warning", ...}` ledger entry. MUST NOT delete files — the contract preserves user data; warnings are advisory only.

**BUG-AUDIT-61 new normative requirements:**

- **REQ-QA-INV13-1:** INV-13's `check_images_respect_margins` MUST exempt any `<img>` whose class list contains `fullbleed`, OR that has an ancestor with class `fullbleed`. The exemption is explicit and discoverable via the DOM — hidden-via-0×0 workarounds are obsolete. A regression test MUST render a full-bleed image slide and assert INV-13 returns None.

- **REQ-RESTORE-WARN-1:** `/debrief:restore` (restore mode) MUST, after the BC-11.11 step 6 confirmation print, perform an orphan-output audit. It MUST enumerate immediate subdirectories of `output/` matching the pattern `YYYY_MM_DD_*`, compare each against `presentations[].folder` in the restored deck_state, and for every subdirectory not referenced in the restored state: (a) print a warning to stderr naming the path + the count of files inside it, (b) append a `{"event": "restore_orphan_warning", "timestamp": "<ISO>", "orphan_folder": "<path>", "file_count": N}` entry to `ledger.jsonl`. MUST NOT delete or modify the orphan files. A restore with no orphans MUST NOT emit either the stderr warning or the ledger entry.

**Round 4 Prior-Art for Rebuild:**

- When two requirements on the same element structurally conflict, the fix is a DOM-discoverable exemption marker (a specific class, attribute, or ARIA role), not a hidden workaround. Workarounds compound over time; exemptions are self-documenting and testable.
- Restore/rollback operations that scope narrowly (e.g., deck_state-only) MUST surface every implication of the narrow scope. Orphan artifacts from out-of-scope files are a silent-data class — cheap to warn about, expensive when a user discovers PDFs that don't match their state weeks later.

---

### BUG-AUDIT-62: Smoke test Round 5 — 3 new bugs (3 MEDIUM) + 7 LOW observations; BUG-AUDIT-60/-61 fixes all hold

Round 5 ran against the plugin with BUG-AUDIT-60 and BUG-AUDIT-61 applied. All 15 fix-validation checkpoints (6 BUG-AUDIT-60 clusters + 2 BUG-AUDIT-61 bugs + auxiliary checks) held under the real pipeline. Three new MEDIUM bugs surfaced, plus seven LOW enhancement observations.

**BUG-ST-round5-x-1 (MEDIUM, regression-class):** During Profile A/A7, `python -m debrief.debrief_state update ... --project-root .` printed `WARNING: debrief_state.json hash mismatch — recomputed. File may have been externally modified.` before applying the update. Root cause: the stylist subagent wrote `debrief_state.json` directly during Phase 2 promotion (to transition `sub_phase` from `discovery/brief_review` to `production/group_planning`), bypassing `write_debrief_state` which recomputes `state_hash`. The next read saw a stale hash. Same failure mode BC-5.7 ("Consultant does not write state files") was designed to prevent, but the contract named only the consultant. Subagents like the stylist, slide-maker, visual-qa, and bug-diagnostic inherit the same constraint but were never explicitly covered. **Fix:** (a) extend BC-5.7 to all subagents; (b) update `stylist.md`, `slide-maker.md`, `visual-qa.md`, and `bug-diagnostic.md` to each contain an explicit prohibition on direct `deck_state.json` / `debrief_state.json` writes; (c) regression test parses each agent card and asserts the prohibition string is present.

**BUG-ST-a-e1 (MEDIUM, cross-command inconsistency):** `/debrief:export` produces a PDF that includes backup slides at the end (per `export.py:build_page_list` following spec §24.10 canonical order). But `/debrief:present` and `/debrief:view` (default mode) EXCLUDE backup slides. Across commands that render the same deck, backup-slide inclusion is inconsistent — the main PDF is a "backup-inclusive" artifact while the browser-facing surfaces are "main-only". Users exporting a conference-talk PDF don't expect their Q&A backups bundled in. **Fix (option C):** add a `--include-backup` CLI flag to `/debrief:export` (default `false`). Without the flag, the PDF contains main-only slides, matching the present/view default. With the flag, backup slides are appended at the end (current behavior). `/debrief:handout` unchanged (it already consumes the deck; users choose which export flavor to handout-ify).

**BUG-ST-a-e2 (MEDIUM, narrow extractor):** `script_generator`'s `_extract_transition` recognizes a narrow `_TRANSITION_SIGNALS` list (`next`, `which leads`, `sets the stage`, `explore next`, `where we go next`, `which brings us`, `let's turn to`, `this leads`, `moving on`, `that's why`). When the consultant writes a `content_summary` that ends with phrasing outside this list — OR uses an explicit `Transition: ...` format marker — no transition is extracted and the script falls back to the placeholder `Lead into **<next>** by connecting the key findings above.` BUG-ST-12's fix established the extraction path; BUG-AUDIT-62 extends the grammar. **Fix:** (a) recognize the explicit `Transition:` prefix marker anywhere in the last paragraph — when present, extract the text after the marker; (b) broaden the signal list to also catch common phrasings (`set up`, `the first move`, `next up`, `move into`, `turn to`, `bringing us to`, `leading into`, `into the next`). Placeholder remains the fallback for content_summary with no transition signal at all.

**BUG-AUDIT-62 new normative requirements:**

- **REQ-AGENT-STATE-1:** No subagent (stylist, slide-maker, visual-qa, bug-diagnostic) MAY write directly to `deck_state.json` or `debrief_state.json` via the Write tool. All state mutations MUST flow through `write_debrief_state`/`write_deck_state` (via their own CLIs — `python -m debrief.debrief_state update` or the `promote_style_draft` utility for style lock) so that hash recomputation, atomic write, and auto-ledger remain invariant. A regression test MUST parse each subagent card and assert a prohibition string is present.

- **REQ-EXPORT-BACKUP-1:** `/debrief:export` MUST accept an optional `--include-backup` CLI flag. Default behavior (flag absent) produces a main-only PDF, excluding any slide with `backup: true` from the page list. When the flag is present, backup slides are appended at the end of the PDF in approval order. `/debrief:present` and `/debrief:view` (default) continue to exclude backup slides unchanged. `export_log.jsonl`'s `slide_count` reflects the actual page count (which depends on the flag).

- **REQ-SCRIPT-TRANSITION-1:** `script_generator._extract_transition` MUST recognize an explicit `Transition:` prefix marker in the last paragraph of `content_summary`. When a sentence or line begins with `Transition:` (case-insensitive, optional Markdown bold/italic around it), the text after the marker is the transition. When no explicit marker is present, the extractor falls back to signal-word matching against an extended `_TRANSITION_SIGNALS` list that additionally includes at minimum: `set up`, `the first move`, `next up`, `move into`, `turn to`, `bringing us to`, `leading into`, `into the next`. When neither the marker nor any signal word is found, the placeholder text remains.

**Enhancement backlog (LOW-severity observations from Round 5):**

These are not blocking bugs; they are logged here for future work:

- **LOW-OBS-1 (`BUG-ST-x-observe1`) — RESOLVED AS NOT-A-BUG (Round 6 post-audit clarification):** the original observation ("`deck_state.closing_slide` not auto-populated when a slide is authored into a closing-role group") was based on a wrong mental model. Per Section 17.4 and the export page-order spec (lines 3807-3823), `closing_slide` is an **auto-injection marker** for an in-memory styled blank closing slide, not a pointer to a user-authored slide. Valid values are `null` (omit auto-injection) and `"empty"` (inject a styled blank closing slide). When the user authors a real closing slide, `closing_slide` correctly stays `null` — auto-populating it to `"empty"` would cause the export module to ALSO inject a blank slide after the user's real closing slide, producing a double-closing artifact. No enhancement needed; current behavior is correct semantics.

- **LOW-OBS-2 (`BUG-ST-a-observe3`):** `/debrief:restore` does not emit a warning for orphan entries under `assets/images/` that the restored state no longer references. Consistent with BC-11.12's deliberate "preserve user assets" scope, but a mirror of BUG-AUDIT-61's orphan-output warning pattern would be more discoverable. Enhancement: `skill_restore` audits `assets/images/` as well as `output/<YYYY_MM_DD_*>/`.

- **LOW-OBS-3 (`BUG-ST-c-observe1`):** `script_generator` has no awareness of user_assets — a slide with a `<video>` tag produces a script section with no video cue. Presenters have to infer playback timing from the content summary. Enhancement: when a slide's HTML contains a `<video>` or `user_assets` includes a video path, emit a `[VIDEO CUE: <filename>]` bullet in the script.

- **LOW-OBS-4 (`BUG-ST-c-observe2`):** No programmatic QA invariant scans for confidentiality markers (`CONFIDENTIAL`, `DO NOT DISTRIBUTE`, `INTERNAL ONLY`) on slides whose archetype is in the public set (`conference_talk`, `seminar`, `lecture`, etc.). Consultant-level vigilance is the only signal. Enhancement: add INV-XX for archetype/confidentiality mismatch.

- **LOW-OBS-5 (`BUG-ST-c-observe3`):** `qa_checker check_limit` reports `limit_reached / iteration / limit` but does NOT surface whether the recent failure set is *oscillating* (A → B → A → B) vs monotonically reducing. Oscillation is a stronger signal than a flat red streak. Enhancement: add `oscillating: true` flag when the distinct failure invariant IDs in the last 3+ iterations cycle.

- **LOW-OBS-6 (`BUG-ST-c-observe4`):** `presentations[0].export_count` stays at 0 after export because filesystem-derived versioning is canonical (per BUG-AUDIT-23, documented vestigial). The field's presence is still misleading to readers. Enhancement: either remove the field from the `PresentationRecord` dataclass entirely, or have export populate it as a convenience cache (while filesystem remains authoritative).

- **LOW-OBS-7 (A2 dimensions naming):** `analyzer_metadata.json` exposes `slide_width_emu` and `slide_height_emu` separately rather than a combined `dimensions` object. Content-equivalent; naming-divergent from early spec language. Enhancement: either update the spec text to match the current JSON shape, or rename to a unified `dimensions` object. No functional impact.

**Round 5 Prior-Art for Rebuild:**

- When a contract names a specific agent role (e.g., "Consultant does not write state files"), verify that EVERY agent subject to the same invariant is explicitly listed. Inheritance by common sense is not testable and not enforceable. Enumerate all covered agents, or enforce via code, not prose.
- Rendering commands on the same deck should share a single backup-inclusion invariant (always-include, always-exclude, or opt-in). Divergence across export/present/view is an accident, not a feature. Pick one default and make others opt in.
- Signal-word extractors need an explicit format-marker escape hatch. Consultants writing `content_summary` can reliably produce text OR the marker; relying solely on free-text heuristics leaves legitimate inputs un-handled.

---

### BUG-AUDIT-63: State-file write enforcement via PreToolUse hook — completes BUG-AUDIT-62 BUG-ST-round5-x-1

BUG-AUDIT-62 added prose-level prohibitions to four subagent cards and hardened `promote_style_draft` to use `write_deck_state`. Self-review after BUG-AUDIT-62 revealed the fix was defensive-only: **no enforcement layer exists** for state-file writes. The `bin/check-write-auth` PreToolUse hook gated only `slides/*` and `assets/style.css` (BC-1.10); `deck_state.json` and `debrief_state.json` were unconditionally passed through (BC-1.11). An agent ignoring BC-5.7 would still succeed silently, and the hash-mismatch warning that surfaced in Round 5 would recur.

**Root cause (completing Round 5's diagnosis):** the Round 5 hash-mismatch warning was surfaced on `debrief_state.json`, but no Python code path under `src/unit_*/*.py` writes `debrief_state.json` outside `write_debrief_state` (or `launcher._atomic_write_json` for the initial project-creation write, which has no prior hash). That leaves exactly one code path that can produce the observed warning: an agent invoking the Write tool on `debrief_state.json` directly. The canonical CLI paths (`python -m debrief.debrief_state update`) use Python writes, not the Write tool, so they are unaffected by the PreToolUse hook. Extending the hook to reject Write-tool writes to state files is therefore safe: it blocks agent-originated state writes while leaving canonical CLI paths intact.

**Fix:** `bin/check-write-auth` rejects Write-tool calls whose resolved path equals `$PWD/deck_state.json` or `$PWD/debrief_state.json`. The error message names the canonical alternatives so agents receiving the rejection have a clear remediation path.

**Normative requirement:**

- **REQ-WRITE-AUTH-STATE-1:** `bin/check-write-auth` MUST reject Write-tool invocations targeting `deck_state.json` or `debrief_state.json` at the project root, with exit code 2 and a stderr message naming `python -m debrief.debrief_state update` (for `debrief_state.json`) or `python -m debrief.utility_skills promote_style_draft` / the equivalent canonical-write Python CLI (for `deck_state.json`). This rejection MUST run before BC-1.10's style-lock check (different protected-path branch). Python code paths that use `atomic_write_json` / `write_debrief_state` / `write_deck_state` are NOT affected — the hook sits on the Write tool, not on file writes from Python processes.

**Prior-Art for Rebuild:** Prose-level prohibitions in agent cards are necessary but insufficient when a tool can bypass them. If BC-5.7 says "Agent X must not do Y" and Y is technically possible via an available tool, write a hook that rejects Y. Otherwise BC-5.7 is a style guide, not a contract.

---

### BUG-AUDIT-64: Handout backup-inclusion parity — extends BUG-AUDIT-62 option C

BUG-AUDIT-62 added `--include-backup` to `/debrief:export` (BC-10.3a, default excludes backup). For cross-command consistency with BUG-ST-a-e1's intent, `/debrief:handout` needs the same flag with the same semantics — currently it hardcodes non-backup only (`main_handout` line ~957), so a user cannot produce a Q&A-ready handout PDF that includes the backup slides even though the backup content is legitimately part of the deck.

Without parity, the cross-command invariant from BUG-AUDIT-62 (main-only default, opt-in inclusion) is incomplete: export + present + view + handout should all share the same default and the same opt-in name.

**Fix:** `main_handout` now accepts `include_backup: bool = False` (matching `main_export`). When `True`, the handout's page list is extended to include approved backup slides. CLI `--include-backup` flag added with the same help text and semantics as `/debrief:export`'s.

**Normative requirement:**

- **REQ-HAND-BACKUP-1:** `/debrief:handout` MUST accept an `--include-backup` CLI flag. Default (flag absent) produces a handout of main slides only (backup slides with `backup: true` excluded from the layout). When `--include-backup` is passed, approved backup slides are appended after the main slides, in array order. This matches `/debrief:export`'s `--include-backup` semantics exactly (BC-10.3a) so users learn one flag and reuse it.

**Prior-Art for Rebuild:** When multiple commands render the same underlying deck, every command MUST share the same backup-inclusion invariant and the same flag name. Selective parity (e.g., flag on export but not handout) re-creates the cross-command inconsistency that BUG-AUDIT-62 set out to fix.

---

### BUG-AUDIT-65: Backup slides always in presenter surfaces (`/debrief:present`, `/debrief:script`)

BUG-AUDIT-62 set the invariant that **audience-facing** artifacts (export PDF, printed handout) default to main-only with an opt-in `--include-backup` flag. BUG-AUDIT-65 completes the symmetry for **presenter-facing** artifacts: `/debrief:present` (the browser-based podium vehicle) and `/debrief:script` (speaker notes) MUST always contain everything — including approved backup slides — because the presenter cannot switch tools mid-talk to reach them. The presenter controls navigation; the medium does not gate what is available.

**BUG-ST-a-e3-present (MEDIUM, UX):** `/debrief:present` hardcoded `not s.backup` in its slide selection. During Q&A, if a question triggers a backup slide, the presenter has no way to navigate to it inside the running presentation — they would have to leave the browser, switch to a shell, run `/debrief:view backup`, and interrupt the room's attention. **Fix:** `/debrief:present` now includes ALL approved slides (main + backup). A **blank separator slide** — background color only, no text or imagery — is inserted between the last main slide and the first backup slide so the end-of-main-talk transition is visually marked without signalling anything noisy to the audience. The presenter sees it as a beat; the audience just sees a clean frame during which the presenter can take a breath before Q&A begins.

**BUG-ST-a-e3-script (MEDIUM, UX):** `/debrief:script` hardcoded `not s.backup`. Speaker notes for backup slides are exactly what a presenter most wants during Q&A — the answers they've already rehearsed. **Fix:** `/debrief:script` now includes all approved slides. A `## Backup Slides` section heading precedes the backup entries for readability.

**Normative requirements:**

- **REQ-PRESENT-BACKUP-1:** `/debrief:present` MUST include every approved slide — both main (`backup != True`) and backup (`backup == True`) — in the generated `output/presentation.html`. Progressive-disclosure build files are ONLY injected for main slides (backup slides are terminal; they have no builds). When the deck has at least one main slide AND at least one backup slide, a blank separator slide MUST be inserted between the last main slide (and any closing slide or main-deck separator before it) and the first backup slide. The separator slide is rendered in-memory; it is NOT a user-authored slide, has no slide record, and is not written to `slides/`. It inherits the background color from the locked `style_config.json` (`colors.background` dot-path) and has no other visual content. No CLI flag — backup inclusion is unconditional. No consultant prompt — the consultant dispatches silently.

- **REQ-SCRIPT-BACKUP-1:** `/debrief:script` MUST include every approved slide in the generated script. Main slides appear first under their existing per-slide headers (`## Slide N: <title>`). Backup slides appear after a `## Backup Slides` section heading, each as a `## Slide N (backup): <title>` entry with the same Key talking points / Transition / Estimated speaking time subsections. No CLI flag — backup inclusion is unconditional. No consultant prompt — the consultant dispatches silently.

**Rationale for no flag and no consultant ask:** per the Round 5 follow-up discussion, a presenter never wants LESS than the full deck at the podium or in their speaker notes. The presenter decides in the moment whether to show a backup slide; the live vehicle must carry it in case they need it. Adding an opt-out flag would only expose a footgun with no compelling use case.

**Prior-Art for Rebuild:** Classify every output artifact by its *consumer*. Audience-facing artifacts (PDF, print) default to the curated main deck with opt-in extras. Presenter-facing artifacts (live deck, speaker notes) carry everything — the presenter is the gatekeeper, and a missing tool is worse than an unnavigated section.

---

### BUG-AUDIT-66: Consultant alternative-dispatch prompts for `/debrief:export` and `/debrief:handout`

BUG-AUDIT-62 + BUG-AUDIT-64 added `--include-backup` to export and handout; BUG-AUDIT-64 also documented `/debrief:handout`'s `--mode 2up|4up` as a first-class axis. Both flags live only on the CLI — there is no conversational path that surfaces the choice to the user. A user who types `/debrief:handout` with no flags gets the default (`--mode 2up`, main-only) without ever knowing they had a choice. The consultant, which is the user's primary interface, never asks.

This is the symmetric user-facing UX gap that BUG-AUDIT-65 closed on the presenter side (no flags — always full deck). For audience-facing artifacts, we went the other way: flags exist but remain invisible. BUG-AUDIT-66 closes the gap by teaching the consultant to offer the choices at dispatch time with deterministic phrasing.

**Scope:**

- `/debrief:export` — ask about `--include-backup` ONLY when approved backup slides exist AND the flag was not supplied in the user's turn.
- `/debrief:handout` — ask about `--mode` (always, since 2up vs 4up is always a taste choice) AND `--include-backup` (only when approved backups exist), combining both into a single dispatch turn when both are missing.
- `/debrief:present` and `/debrief:script` — NEVER ask. They carry the full deck unconditionally per BUG-AUDIT-65.
- `/debrief:view`, `/debrief:save`, `/debrief:restore`, `/debrief:style`, `/debrief:slide`, `/debrief:quit` — unchanged. Their existing UX is complete (positional query / user-authored label / dedicated warning gate / approval gate).

**Normative requirements:**

- **REQ-CONSULT-ALT-DISPATCH-1 (deterministic prompting):** `consultant.md` MUST contain a dedicated "## Alternative Dispatch Prompts" section that enumerates: (a) the four commands the rule applies to (`export`, `handout`) and the two it does NOT (`present`, `script`, plus the remaining six commands), (b) a deterministic step-by-step decision rule (read the user's turn, check for existing flags, read `deck_state.slides` for approved backup count, emit the matching prompt case), (c) the EXACT prompt text for each case (handout with both missing, handout with only mode missing, handout with only backup missing, export with backup question), (d) a dispatch-mapping table that translates natural-language user replies (`main only`, `include backup`, `2up`, `4up`, combined replies) into CLI flags.

  The consultant MUST NOT improvise the wording of the prompts. Drift from the fixed strings is a CRITICAL regression — a regression test parses `consultant.md` and asserts the canonical prompt substrings are present verbatim.

- **REQ-CONSULT-ALT-DISPATCH-2 (flag-bypass rule):** when the user's slash-command turn already contains explicit flags that fully determine the alternatives, the consultant MUST dispatch without asking. Examples: `/debrief:handout --mode 4up --include-backup` → dispatch silently; `/debrief:export --include-backup` → dispatch silently; `/debrief:handout --mode 4up` → if approved backups exist, ask ONLY about `--include-backup`; if no backups exist, dispatch silently. The rule must avoid double-prompting: once the user has answered for a dimension (either by flag or by reply), that dimension is decided.

- **REQ-CONSULT-ALT-DISPATCH-3 (zero-backup quiet dispatch):** if `count([s for s in deck_state.slides if s.status=="approved" and s.backup]) == 0`, the consultant MUST NOT emit the backup question for any command, because the alternative is meaningless (there are no backup slides to include). For `/debrief:handout` with zero backups, the consultant still asks about `--mode` (always meaningful).

**Out-of-scope (future BUG-AUDIT-XX candidates):** consultant-driven dispatch prompts for other parameters (e.g., `save --label` collision resolution, `restore` list-then-pick flow, `style` re-lock warning already exists per BC-1.10). Not addressed here.

**Prior-Art for Rebuild:** a CLI flag that is never surfaced in the conversational UX is a feature that silently doesn't exist for most users. Either the consultant offers the choice at dispatch time, or the default must be so overwhelmingly right that the flag is vestigial. The intermediate case (flag exists, consultant ignores it) is the worst outcome — it creates the illusion of choice without the mechanism to access it.

---

### BUG-AUDIT-67: `/debrief:present` renders each slide in a srcdoc iframe to preserve per-slide CSS

**BUG-ST-present-empty (HIGH, layout regression):** `/debrief:present` produced a visually-empty presentation.html. Root cause: `_write_presentation_html` extracted only `<body>…</body>` from each standalone slide HTML and discarded the `<head>`. But every slide's `<head>` carries a ~2,400-character `<style>` block defining slide-specific classes (`.statement-block`, `.main-heading`, `.accent`, `.label-replaced`, `.label-replacement`, `.slide-number`, plus per-slide `body` and `.slide` sizing rules). When the body is embedded without that style block, none of those class rules exist in the rendered document — every styled element collapses to unstyled defaults. Verified on the Round 5 artifact: `presentation.html preserves ANY per-slide class rules: False`.

This is a layout regression, not a content regression — all the DOM is present, just visually degenerate. The user's report ("empty web page") was accurate from a visual standpoint. The per-slide `<style>` block has been a stylist convention since BUG-AUDIT-13 (canonical template); standalone slides rendered correctly during Playwright QA (head preserved), so the bug only surfaced in the aggregated `/debrief:present` output.

**Fix:** each file-backed slide is now embedded as `<div class="slide" data-index="N"><iframe srcdoc="<escaped full slide HTML>"></iframe></div>`. The iframe's `srcdoc` attribute carries the verbatim original HTML of the slide (head + body) inline — no stripping, no re-assembly. Per-slide CSS is naturally scoped to its iframe. presentation.html stays a single self-contained file: `srcdoc` embeds content inline, it is not a URL reference. String-backed slide bodies (the blank separator from REQ-PRESENT-BACKUP-1) remain plain `<div>`s and are NOT wrapped in an iframe — they have no per-slide styling to preserve.

Keyboard navigation is preserved regardless of which frame holds focus. The top-level window registers the keydown handler; when each iframe loads, the same handler is attached to its `contentDocument`. Arrow keys targeting `<video>`, `<input>`, `<textarea>`, or `<select>` are allowed to reach the element (not intercepted for slide navigation) so native behavior (video seeking, form input) works.

**Normative requirements:**

- **REQ-PRESENT-IFRAME-1 (srcdoc-embedded per-slide HTML):** `_write_presentation_html` MUST emit each file-backed slide as an `<iframe srcdoc="…">` inside its `<div class="slide" data-index="N">` wrapper. The srcdoc content MUST be the verbatim original slide HTML (no modification of head, body, or scripts). The iframe MUST have `style="width:100%;height:100%;border:0;display:block;"` so it fills the wrapper without chrome. String-backed bodies (blank separator) remain plain div content.

- **REQ-PRESENT-IFRAME-2 (keyboard nav across frames):** the presentation's navigation script MUST attach its keydown handler to the top-level window AND — on each iframe's `load` event — to the iframe's `contentDocument`. The handler MUST pass through arrow-key events whose `event.target` is a `<video>`, `<input>`, `<textarea>`, or `<select>` element so native behavior is preserved. The slide-counter element, and the `F` fullscreen toggle, remain at the top-level window and are not duplicated per-iframe.

**Prior-Art for Rebuild:** "embedding" a fragment of an HTML document (e.g., inlining only its `<body>`) silently breaks any styling that lives in the fragment's `<head>`. If the source is a fully standalone HTML document — as each Debrief slide is by design — embed it whole (iframe srcdoc, shadow DOM, or similar isolation mechanism) rather than cherry-picking body. The body-only extraction pattern works ONLY when all relevant styling lives in shared external stylesheets, which is not the case here and imposing that constraint on slide authors is a larger refactor than the iframe fix.

---

### BUG-AUDIT-68: `/debrief:handout` never reads the speaker script — notes collapse to `content_summary` or silent empty

**Symptom (HIGH, output regression).** The rendered `output/handouts/handout_v{NNN}.pdf` contained empty notes cells for every slide despite a complete, user-authored `speaker_script.md` existing at the project root. Slides with a populated `SlideRecord.content_summary` fell back to that field's text (which was often a terse internal label, not the speaker's real words); slides without a summary rendered visually empty. The artifact was useless as a leave-behind: the entire point of a handout is to let the audience read *what the speaker actually said*, and the implementation merged neither the user-authored nor the generator-written script.

**Root cause.** `generate_layout_html` in `utility_skills.py` read notes directly from `SlideRecord.content_summary` (`notes = slide.content_summary or ""`). No code path anywhere in the handout module, the script generator, or their shared helpers opened `speaker_script.md`. REQ-HAND-3 (pre-BUG-AUDIT-68) nominally listed "the corresponding section from the presenter script" as a secondary source, but the requirement was never implemented — the code matched only clause (1) of that three-clause spec. The discrepancy was masked by unit tests that supplied a `content_summary` on every synthetic slide and never exercised the script-merge path, and by BUG-AUDIT-21's integration test, which asserted that the PDF began with `%PDF` magic bytes but did not inspect the notes text.

Additionally, no canonical filename was defined for the handout's notes source. The script generator writes versioned files to `output/<presentation_folder>/script_v{NNN}.md` (correct: non-destructive, preserves history), but no file at a stable, predictable path carried the "use this for notes" contract. Users wanting their speaker prose merged had no path to name.

**Detection method.** Inspect a generated `handout_v*.pdf` with slides authored against a separate `speaker_script.md`. Notes cells read either the terse `content_summary` text or are empty. `grep -r speaker_script src/unit_11/` and equivalent on the delivered `src/debrief/` return zero matches.

**Fix summary.** REQ-HAND-3 is rewritten with a deterministic three-level precedence: (1) `speaker_script.md` at project root, parsed into per-slide sections and matched by slug (primary) or title (fallback); (2) `SlideRecord.content_summary`; (3) explicit placeholder `"(no notes available)"` — silent empty notes are forbidden. BC-11.15a (new contract) specifies the section-extraction grammar and lookup semantics. `generate_layout_html` is modified to load `speaker_script.md` once per invocation via `_load_speaker_script(project_root)` and apply the precedence per slide. The generator-side path (`output/<folder>/script_v{NNN}.md`) is unchanged; the handout does NOT read it. Promotion from versioned script to handout notes is a user action (copy → rename → `speaker_script.md`), chosen deliberately to keep the versioned script file non-destructive while giving the handout one stable filename to resolve.

Regression tests cover the baseline (no script → content_summary is used), the canonical path (script section by slug → script wins), the title fallback, unmatched slides (mixed deck), the placeholder rule, and the empty-file edge case.

**Normative requirements:**

- **REQ-HAND-NOTES-1 (speaker_script.md precedence):** `generate_layout_html` MUST resolve each slide's notes text in the order defined by REQ-HAND-3: script section → `content_summary` → placeholder. The precedence is per-slide independent (some slides may be resolved from the script while others fall back). Silent empty cells are forbidden.

- **REQ-HAND-NOTES-2 (section extraction):** when `speaker_script.md` is present, section matching MUST be deterministic per BC-11.15a: primary match is the line `**Slug:** \`<slug>\`` inside a per-slide block; fallback match is the slide title in the `## Slide N: <title>` header. The extracted body text is everything between the per-slide `## Slide` header and the next `## Slide` header (or `## Backup Slides`, or end of file), minus the header line itself. Leading and trailing whitespace are stripped.

**Prior-Art for Rebuild:** a spec clause saying "source A or source B" is not implementable as code until the priority and resolution rule are deterministic. REQ-HAND-3's original three-clause list described candidate sources but neither the merging rule nor the canonical path of "the presenter script" — so the implementation defaulted to the simplest source (`content_summary` only) and the spec-code drift was invisible. Normative requirements that list alternatives MUST name the resolution order, the parse rule, and the fallback, or the implementation will diverge silently. The handout's output-broken failure mode was the delayed signal of that underspecification.

---

### BUG-AUDIT-69: Slide filename and screenshot filename must equal `<slug>.html` / `<slug>.png` — Tier-1 QA invariant `INV-24`

**Symptom (HIGH, silent-break cluster).** Two related output failures, both silent until export/handout time:

1. **Slide-path drift.** The slide-maker wrote slide HTML files with a numeric prefix (e.g., `slides/01_title.html`, `slides/11_closing.html`) — presumably for author-readable filesystem ordering. The export module (`debrief.export.build_page_list`) resolves slides via `project_root / "slides" / f"{slide.slug}.html"`; the handout's image lookup (`utility_skills.generate_layout_html`) and the view/present surfaces use the same slug-based resolution. Every downstream consumer expects `slides/<slug>.html` *exactly*; any prefix or suffix breaks them all silently. `/debrief:export` aborts on the first slide with `Page.goto: net::ERR_FILE_NOT_FOUND`. The deck-local workaround was a filesystem rename pass stripping the `NN_` prefix.

2. **Screenshot-path drift.** When slide filenames carried a prefix (as above), the screenshots written by Tier-1 qa_checker inherited the same prefix (`output/screenshots/01_title.png`). After the slide files were renamed, screenshots were NOT — so the handout image lookup at `output/screenshots/<slug>.png` came back empty and every handout cell rendered `[no screenshot]`. The fix was a second rename pass over `output/screenshots/`.

Both failures were invisible to automated QA because the filename mismatch is a structural violation, not a visual one — Playwright rendered the file it was handed, and the rendered screenshot was fine; it was simply saved under the wrong name.

**Root cause.** No Tier-1 invariant enforced the filename↔slug contract. `main_qa_checker` derived slug as `slide_path.stem`, so any filename the slide-maker chose became the implicit slug — authoritatively wrong if the rest of the system was computing from a different slug. The spec already said "Only write to `slides/<slug>.html`" (agent constraint in `agents/slide-maker.md`), but no mechanical check fired when the constraint was violated. Spec → code drift at the detection layer.

**Detection method.** Run `/debrief:export` or `/debrief:handout` against a project whose slide files or screenshots carry a prefix. Exports fail with `ERR_FILE_NOT_FOUND`; handouts render `[no screenshot]` placeholders. Pre-execution detection via Tier-1 QA (INV-24) now fires on the slide-maker's very first authoring turn, red-gating any slide whose filename drifts from the contract.

**Fix summary.** A new Tier-1 invariant `INV-24` (filename/slug consistency) is added to `qa_checker.run_programmatic_checks` and its enumerated `checks_run` list in `main_qa_checker`. Two sub-rules (BC-9.3a):

- **Rule A (always active).** `slide_path.stem == screenshot_path.stem`. A mismatch names either a stale slide file or a stale screenshot — downstream resolution breaks either way.
- **Rule B (state-aware).** When `deck_state.json` is readable AND its `slides` array is non-empty, the slide's filename stem MUST equal `SlideRecord.slug` for some recorded slide. A mismatch means the filesystem artifact carries a name that no downstream consumer will ever resolve. Skipped silently when state is absent or contains no slides — the consultant may not have written the record yet; this is the legitimate first-author state and a false positive there would gate every new project.

Both rules emit a single `INV-24` failure with a canonical `revision_instruction` naming the expected paths. INV-24 is non-VETO (it reads as a regular INV failure in the qa_log and participates in the red-green cycle like any other soft blocker).

Agent-side, `slide-maker.md` and `visual-qa.md` gain a one-line callout referencing INV-24 as the mechanical enforcement of the filename rule.

Regression tests cover both rules, the skip semantics, the error message grammar, and the existing Tier-1 callers (so backward-compat tests continue to pass — their synthetic slide_path/screenshot_path pairs already have matching stems).

**Normative requirements:**

- **REQ-QA-FILENAME-CONTRACT-1:** Tier-1 `qa_checker` MUST enforce the filename↔slug contract via invariant `INV-24`. The invariant MUST fail any slide whose (a) slide_path filename stem and screenshot_path filename stem differ, OR (b) when `deck_state.json` is readable with a non-empty `slides` array, whose slide_path filename stem is not equal to `SlideRecord.slug` for any recorded slide. The emitted `revision_instruction` MUST name the canonical filesystem paths (`slides/<slug>.html`, `output/screenshots/<slug>.png`) so the slide-maker can rewrite without guessing. The invariant participates in `run_programmatic_checks` and appears in the `checks_run` enumeration emitted to `qa_log.jsonl`. It is NOT a VETO — a filename drift is a soft blocker that the red-green cycle can resolve through rewrite.

**Prior-Art for Rebuild:** a naming contract that is specified agent-side but not checked code-side is a contract in appearance only. The spec said "Only write to `slides/<slug>.html`"; the agent drifted; no mechanical check fired; the drift propagated to every downstream consumer and surfaced as cryptic file-not-found errors at the worst possible moment (seconds before a presentation). Structural contracts MUST have mechanical enforcement at the earliest point in the pipeline where the drift is detectable. For the filename contract, that point is Tier-1 QA — the slide-maker's own return-path — so the drift is caught on the authoring turn, not export hours later.

---

### BUG-AUDIT-70: Routing-surgery aftermath — `commands/export.md` references deleted functions; first-export folder bootstrap double-dates when `project_name` already carries a date

**Symptom cluster.** Two related defects, both downstream of BUG-AUDIT-31's gutting of `routing.py`. Neither is caught at test time because both surface only at user-facing first-run moments.

1. **Stale `commands/export.md` doc.** The canonical command documentation claimed (a) "The skill yields to routing, which guides the user through the export ordering dialog (G4.1 → G4.4) before invoking the export module" and (b) the presentation folder default is "computed deterministically by `routing.propose_presentation_folder_name(deck_state)` using the format `<YYYY_MM_DD>_<shortened_title>` per spec §24.10 / blueprint BC-4.7c" and (c) the Parameters section said options "are handled by the export ordering dialog at gates G4.1–G4.4" and "the dialog reads the proposed folder name from the prepare-time injection per BC-4.7c". All three claims were false after BUG-AUDIT-31 deleted `propose_presentation_folder_name`, `main_routing`, `main_prepare`, and the entire G-gate dispatch loop. A user reading `/debrief:export --help` or the in-repo doc before running the command is misled about how the dispatch actually works — the doc says "yields to routing"; reality is "consultant dispatches directly".

2. **Double-dated auto-bootstrap folder name.** On first export (when `deck_state.presentations` is empty), `main_export` self-bootstraps a `PresentationRecord` at `src/unit_10/export.py:117-149`. The old routing loop computed the folder name; in the consultant-orchestrated model, export handles this itself. But the bootstrap unconditionally prepended `date.today()` to `sanitize_identifier(state.project_name, max_length=40)`. When `project_name` already carried a date — which is the common case for dated events like lab meetings, conference talks, and dated seminar series — the resulting folder was `YYYY_MM_DD_YYYYMMDD_<title>` (e.g., `2026_04_19_20260420_lab_meeting`). Two dates. Confusing, and the TODAY date rather than the TALK date. The deck-local workaround was to pre-create the `PresentationRecord` with a hand-picked folder name before invoking export, so the auto-bootstrap saw a non-empty `presentations` list and skipped the computation.

**Root cause.** BUG-AUDIT-31 correctly removed the dead routing code, but the downstream surfaces that depended on the routing model were not updated to match the new consultant-orchestrated reality. The export command doc, the blueprint contract (BC-4.7c), and the export auto-bootstrap all still assumed the routing layer would (a) compute the folder name and (b) present it to the user through a prepare-time injection. When routing went away, the folder-name computation got informally reinvented inside `main_export` with a simpler but less-correct algorithm (no date-detection), and the doc was never updated.

**Detection method.** Run `/debrief:export` on a fresh project whose `project_name` begins with a date prefix (e.g., `20260420_Lab_meeting`). The created folder is `output/2026_04_XX_20260420_lab_meeting/` (today's date, then the embedded project-name date again). Independently, `grep routing src/unit_1/commands/export.md` returns three matches, all referencing symbols that no longer exist.

**Fix summary.** Two independent fixes under the same BUG-AUDIT entry because they share the same root cause.

1. **New helper `compute_presentation_folder_name(project_name, today=None)`** in `src/unit_2/debrief_state.py`, next to `sanitize_identifier` (natural neighbor; `routing.py` is a gutted shell and should not grow new code). The rule: if `project_name` begins with a `YYYYMMDD`, `YYYY_MM_DD`, or `YYYY-MM-DD` date-shape followed by a separator or end-of-string, that date is normalized to `YYYY_MM_DD` form and the remainder (if any) is sanitized as the title; today's date is NOT prepended. Otherwise, today's date (or the injected `today` parameter for deterministic tests) is prepended, and the whole `project_name` is sanitized as the title. The detection pattern is loose (4+2+2 digits with optional `-`/`_` separators) but requires a trailing boundary (separator or end-of-string) so bare four-digit years (`"2024_annual_report"`) are not mis-identified as dates.

2. **Export bootstrap `main_export`** at `src/unit_10/export.py:117-149` now calls the new helper and uses its return value as the `PresentationRecord.folder`. The old in-line `f"{today}_{title_part}"` is deleted. All other fields of the bootstrap record are unchanged.

3. **`commands/export.md` rewritten** to remove every reference to `routing.propose_presentation_folder_name`, "yields to routing", "G4.1 → G4.4", and "prepare-time injection per BC-4.7c". The Trigger section now describes the consultant-orchestrated dispatch. The folder-name paragraph cites the new helper and REQ-EXPORT-BOOTSTRAP-1 / BC-10.9. The Parameters section describes the consultant's pre-dispatch dialog for `--include-backup` (per BC-5.15) and explicitly notes there is no CLI-time export-ordering dialog.

4. **BC-4.7c amended** with a supersession note pointing at BC-10.9 + BUG-AUDIT-70. The old function name (`routing.propose_presentation_folder_name`) is retained only as historical context; the contract now delegates to `compute_presentation_folder_name` in `debrief_state.py`.

5. **Blueprint gains BC-10.9** documenting the bootstrap rule with date-detection and today-fallback semantics.

`routing.py` remains a 32-line shell per BUG-AUDIT-31; it is NOT deleted (the empty-module form is cheap and prevents `ModuleNotFoundError` from any stragglers that do `import routing`).

Regression tests cover: all six date-shape inputs (YYYYMMDD, YYYY_MM_DD, YYYY-MM-DD, bare date, year-only prefix, empty string), the `today=` parameter, idempotence (running the helper on its own output yields the same name), the full `main_export` bootstrap path, and a doc regression that `grep routing commands/export.md` returns zero matches.

**Normative requirements:**

- **REQ-EXPORT-BOOTSTRAP-1:** On first `/debrief:export` for a presentation (when `deck_state.presentations` is empty), the export module MUST compute the `PresentationRecord.folder` value by calling `debrief_state.compute_presentation_folder_name(state.project_name)`. The helper enforces the date-detection rule (no double-dating when `project_name` already carries a YYYYMMDD/YYYY_MM_DD/YYYY-MM-DD prefix) and otherwise prepends today's date. The export module MUST NOT re-implement the folder-name algorithm inline. Subsequent re-exports (when `presentations` is non-empty) reuse `presentations[-1].folder` unchanged — the helper is called only on the self-bootstrap path.

**Prior-Art for Rebuild:** "gutting a dead module is easy; propagating the gut to every surface that assumed the module was alive is the harder, slower half of the job." BUG-AUDIT-31 correctly removed the dead code; BUG-AUDIT-70 patches the three surfaces (command doc, inline bootstrap algorithm, blueprint contract) that had drifted from the new orchestration model. When deleting a dependency, audit for (a) documentation referencing the deleted symbols, (b) code paths that informally reinvent the deleted function's behavior with a simpler but less-correct algorithm, (c) blueprint contracts whose preconditions (e.g., "the prepare module injects this") are now unsatisfiable. All three are silent regressions by construction — type-checking doesn't catch them because the deleted API never typed its callers, and tests don't catch them because the dead code had no tests after removal.

---

### BUG-AUDIT-71: `style_engine` emits font-family names without emitting any loader (`@import` / `@font-face`) — web fonts silently fall back to system

**Symptom (MEDIUM, silent visual regression).** The compiled `assets/style.css` named Google Fonts families in every font-family variable (`--font-heading-family: Inter, sans-serif;`, `--font-body-family: Georgia, serif;`, `--font-code-family: Fira Code, monospace;`) but NEVER emitted an `@import` URL, `@font-face` rule, or any other loader directive. When a slide rendered in Chromium, the browser could not resolve `Inter` or `Fira Code` (no loader → no web font download), fell through to the CSS fallback (`sans-serif`, `monospace`), and the browser selected Helvetica or the system monospace. The wrong font is superficially plausible at body sizes (a sans-serif is a sans-serif) but wrong at display sizes: x-height, weight axis, stroke contrast, and vertical rhythm are all off, so headings look subtly misshapen even though body text reads fine. The deck-local workaround was to hand-inject an `@import url('https://fonts.googleapis.com/css2?family=...')` line at the top of the compiled `assets/style.css` on every compile.

**Root cause.** `style_engine.compile_style` (and its inner `generate_css_root_block`) only wrote CSS custom properties plus one `.slide` background-color rule. There was no code path that inspected the `typography.*_font_family` fields, detected which families were Google Fonts vs system fonts, and emitted the corresponding loader statement. The contract implicit in the style-dialog spec — "the stylist picks fonts, the compiler loads them" — was only half-implemented: the config carried the names, the compiler ignored them. This was invisible to automated QA because a headless Chromium that fails to fetch a web font still renders, using whatever fallback is available, and the screenshot pipeline takes whatever the browser produced.

**Detection method.** Inspect a compiled `assets/style.css` from any existing project. Grep for `@import` or `@font-face` — zero matches. Open a slide in a browser whose system lacks the referenced font (common for `Inter` and `Fira Code` on machines without a design toolchain installed) and compare to the rendered version on a machine that DOES have the font installed locally — the difference is visible at 48px headings.

**Fix summary.** Allowlist-driven Google Fonts `@import` emission. A module-level dictionary `_GOOGLE_FONTS_ALLOWLIST` in `style_engine.py` maps lowercased family names to their Google Fonts CSS2 URL fragments (e.g., `"inter"` → `"Inter:wght@400;600;700"`). `compile_style` now (a) extracts the first family name from each of `typography.{heading,body,code}_font_family`, (b) normalizes it (strip quotes/whitespace, lowercase), (c) keeps only allowlist matches, (d) builds a single `@import url('https://fonts.googleapis.com/css2?family=X&family=Y&display=swap');` line from the survivors, and (e) prepends it to the `:root` block in the emitted CSS. When no allowlisted family is present (all system fonts), the compiled CSS is byte-identical to the pre-BUG-AUDIT-71 output for the same input — so projects using only system fonts are unaffected.

The allowlist is chosen pragmatically to cover the fonts the stylist is most likely to pick: Inter, IBM Plex Sans/Serif/Mono, Roboto (+ Mono + Slab), Open Sans, Fira Sans, Fira Code, JetBrains Mono, Lato, Merriweather, Source Sans 3, Source Serif 4, Source Code Pro, Work Sans, Space Grotesk, Space Mono, Noto Sans, Noto Serif, Poppins, Montserrat. Growing the list is a one-line edit; the contract binds only the allowlist KEYS, not the values (weight lists can be tuned over time without breaking callers). Non-allowlist families pass through silently — system fonts like `Georgia`, `Arial`, `Helvetica`, `sans-serif`, `serif`, `monospace` are correctly resolved by the browser locally.

The loader lives in `compile_style`, not in `generate_css_root_block`, so the pure-function invariants of `generate_css_root_block` (nothing before `:root`; one `:root` only) remain intact and the existing unit tests keep passing.

Regression tests cover: allowlist extraction (template config → `["inter", "fira code"]`; system-only → `[]`; mixed quotes → stripped; duplicate families deduped), URL assembly (empty list → empty string; multiple families joined by `&`; `display=swap` always present), and the `compile_style` integration path (`@import` appears BEFORE `:root {`; no `@import` when no allowlisted family is configured).

**Normative requirements:**

- **REQ-STYLE-FONT-LOADER-1:** `style_engine.compile_style` MUST emit a single `@import url('https://fonts.googleapis.com/css2?...&display=swap');` line at the top of the compiled CSS (before the `:root` block) for every Google-Fonts family named in `typography.heading_font_family`, `typography.body_font_family`, or `typography.code_font_family` that matches the module-level `_GOOGLE_FONTS_ALLOWLIST`. Only the first family in each comma-separated stack is considered; fallbacks are browser-resolved. Families not in the allowlist are assumed to be system fonts and MUST NOT produce an `@import`. When no allowlisted family is present, the compiled CSS MUST contain no `@import` line. Allowlist entries and weight lists are implementation-detail; the normative requirement binds only the EMISSION contract (when to emit, where to emit, and what URL shape to use).

**Prior-Art for Rebuild:** a named font in a config file without a corresponding loader is a silent regression by construction — the browser still renders something (the fallback), so the screenshot pipeline reports no failure. This is the "silent substitution" pattern: any contract that says "the stylesheet will reference font/asset X" MUST be paired with a contract that says "the stylesheet will also load X from a reachable source." The two belong in the same code path or the authoring surface will drift from the rendering surface indefinitely. For future stylesheet-adjacent features (@keyframes with external assets, custom @property rules with external value sources, etc.) write the loader emission in the same commit as the reference emission, not "in a follow-up."

---

### BUG-AUDIT-72: Slide HTML clips below the fold in sub-1920×1080 browsers — Tier-1 invariant `INV-25` enforces a viewport-fit IIFE in every slide

**Symptom (MEDIUM, author UX regression; silent under automated QA).** Compiled slide templates hardcode `html, body { width: 1920px; height: 1080px; overflow: hidden }`. When the browser viewport is smaller than 1920×1080 — which is the typical laptop case (macOS menu bar + browser chrome consumes a dozen vertical pixels; a 1920×1080 physical display + any browser chrome produces an inner viewport of ~1920×1000) — the bottom and right edges of the slide are clipped without scrollbars. Authors opening `slides/<slug>.html` directly, running `/debrief:view` against a file:// URL, or previewing `/debrief:present` in a sub-1920×1080 window see missing content below the fold. PNG and PDF exports are correct only because the Playwright-based screenshot and export pipelines force a 1920×1080 `viewport_size`; the discrepancy hides the defect from automated visual QA. Every author hits this on their first direct-browser view of a slide; the deck-local workaround is a hand-authored `assets/fit.js` that applies a viewport-fit transform to the `.slide` element and is included by every slide via a `<script src>` tag.

**Root cause.** No contract — neither agent-side nor code-side — requires a viewport-fit script in authored slide HTML. The slide-maker agent writes `slides/<slug>.html` with the canonical 1920×1080 body shell (correct for the screenshot pipeline) but omits the browser-side fitter that would scale the slide to the actual viewport when displayed directly. No Tier-1 or Tier-2 QA check detects the omission. The screenshot pipeline's forced viewport masks the defect at every automated checkpoint. The only surface where the defect appears is the author's direct-browser view, which is not part of the red-green QA cycle.

**Detection method.** Open any authored `slides/<slug>.html` in a browser whose window is smaller than 1920×1080 (e.g., a 1920×1080 monitor with native chrome). Content in the bottom-right ~80–120 pixels is clipped with no scrollbar. Independently, `grep -l 'data-debrief-viewport-fit' slides/*.html` returns zero matches on any legacy project.

**Fix summary.** Canonical viewport-fit IIFE included inline in every slide, enforced by new Tier-1 invariant `INV-25`. Design choices:

- **Inline, not external file.** A bundled `assets/fit.js` would require a plugin-to-project copy step (via `debrief new` / `ensure_project`) and would add a build-time contract; inline script is self-contained per slide, survives deck copies, and adds ~400 bytes per slide (negligible).
- **Marker-based detection.** The opening `<script>` tag MUST carry the attribute `data-debrief-viewport-fit="v1"`. INV-25 detects the marker via regex; it does NOT require byte-equality of the script body. Script body is free to evolve without breaking the contract — only the marker is load-bearing. Version suffix `v1` lets us rev the contract (`v2`, `v3`) without losing detection specificity.
- **No-op at 1920×1080.** The script early-returns (clearing any `style.transform`) when `scale === 1 && tx === 0 && ty === 0`, so the Playwright-driven screenshot and export pipelines see an identity transform — no stacking-context side-effect, no pixel drift, no regression on the PNG/PDF output.
- **Soft blocker, not VETO.** INV-25 red-gates slides missing the marker and surfaces a `revision_instruction` pointing at `agents/slide-maker.md`'s canonical block; the red-green cycle rewrites the slide and moves on. A VETO would be disproportionate to the failure mode (authoring UX, not output correctness).

The canonical script block is placed verbatim in `agents/slide-maker.md` (Constraints section) as the authoritative specimen. A regression test asserts the agent-spec still contains the marker attribute so the specimen and the enforcement stay aligned.

Regression tests cover: marker-present → pass; marker-absent → INV-25 failure; wrong version (`v2`) → INV-25 failure (so future rev-ups are detected); single/double quote tolerance in the attribute syntax; end-to-end wire-in via `run_programmatic_checks`; and a spec-alignment test that the canonical script block in `slide-maker.md` carries the marker.

**Normative requirements:**

- **REQ-SLIDE-VIEWPORT-FIT-1:** Every authored `slides/<slug>.html` MUST include exactly one `<script>` tag whose opening tag carries the attribute `data-debrief-viewport-fit="v1"`. The script's body MUST implement the viewport-fit behavior specified in `agents/slide-maker.md`'s canonical block — functionally: compute `scale = min(innerWidth/1920, innerHeight/1080)`, apply `transform: translate(tx, ty) scale(scale)` to the `.slide` element, re-apply on `window.resize`, and early-return (clearing any prior transform) when `scale === 1 && tx === 0 && ty === 0` so the 1920×1080 screenshot pipeline sees an identity transform. Tier-1 invariant `INV-25` enforces the marker presence; the invariant detects marker drift, not body drift, so the script body may evolve without breaking the contract. Slides missing the marker MUST red-gate on their first QA run. INV-25 is a soft blocker (NOT a VETO).

**Prior-Art for Rebuild:** "automated QA that forces the canonical viewport masks every viewport-dependent defect." Any rendering behavior that depends on the runtime viewport (scale, overflow, media queries, container queries) MUST be exercised at at least two viewports — one canonical (the export viewport), one author-realistic (a sub-canonical laptop viewport) — or the regression will land in every release and be discovered first by the author, worst. INV-25 closes the specific case of fixed-dimension slide bodies, but the same pattern applies to future viewport-dependent features: pair the feature with a non-canonical-viewport check.

---

### BUG-AUDIT-73: `/debrief:handout` command doc is stale — lists non-existent modes, wrong output path, and omits landed features

**Symptom (MEDIUM, onboarding regression).** The canonical `commands/handout.md` still described the pre-BUG-AUDIT-21 handout surface, even though four subsequent BUG-AUDIT entries had materially changed it. Concrete drift:

- Layout modes advertised as `"2-up, 3-up, notes-only"` — the CLI only ever accepted `2up` and `4up` (REQ-HAND-2; `_VALID_HANDOUT_MODES = {"2up", "4up"}` in `utility_skills.main_handout`). `3-up` and `notes-only` never existed in code.
- Output path advertised as `exports/handout.pdf` — actual path is `output/handouts/handout_v{NNN}.pdf` with filesystem-derived versioning (BC-11.17 / BUG-AUDIT-21).
- Parameters section said "No parameters required" — the CLI has `--mode` (required semantically, even when defaulted by the consultant dialog) and `--include-backup` (BC-11.16a / BUG-AUDIT-64).
- No mention of the `speaker_script.md` notes-source precedence (BC-11.15a / BUG-AUDIT-68).
- No cross-reference to the consultant's Alternative Dispatch Prompts section (BC-5.15 / BUG-AUDIT-66) where the mode + backup-inclusion choices are surfaced conversationally.

A user reading `/debrief:handout --help` or the in-repo doc before running the command was misled about modes, parameters, and output location.

**Root cause.** Per-command documentation lagged the implementation. BUG-AUDIT-21 rewrote the handout module end-to-end and the blueprint contracts tracked the change, but `commands/handout.md` was not refreshed. Subsequent fixes (BUG-AUDIT-64, BUG-AUDIT-66, BUG-AUDIT-68) landed cleanly in code and spec but the per-command doc continued to describe the pre-BUG-AUDIT-21 world. Same contract-drift pattern as BUG-AUDIT-70's export-doc staleness.

Separately, a protocol-adherence concern: the consultant in at least one documented project session dispatched `/debrief:handout` directly with defaults, skipping the Alternative Dispatch Prompts dialog specified at BC-5.15. The contract was emphatic ("must be surfaced conversationally before dispatch") but the consultant's agent-card did not call out skipping as a contract violation; the failure mode was an implicit "I have defaults, I'll just use them" — acceptable in a fast-path but wrong against the spec.

**Detection method.** Read `src/unit_1/commands/handout.md` — layout modes, output path, and parameters are all wrong. Independently, grep the delivered consultant-dispatched commands in a transcript for handout invocations and check whether the pre-dispatch dialog fired on each; absences are skips.

**Fix summary.** Two parallel doc fixes under the same BUG-AUDIT entry:

1. **`commands/handout.md` full rewrite** describing current reality: fail-fast preconditions (BC-11.16), decoupled output path (BC-11.17), handout.css styling (BC-11.15), speaker-script notes precedence (BC-11.15a / BUG-AUDIT-68), `--mode` and `--include-backup` parameters (REQ-HAND-2, BC-11.16a / BUG-AUDIT-64), consultant-orchestrated dispatch dialog (BC-5.15 / BUG-AUDIT-66). Mirrors the rewrite done for `commands/export.md` under BUG-AUDIT-70.

2. **`agents/consultant.md` Alternative Dispatch Prompts preamble hardened** with an explicit NEVER-SKIP notice: emitting the fixed prompt and waiting for the user's reply is a contract obligation when the Decision rule says it MUST fire. Dispatching with defaults when the user did not explicitly supply the corresponding flag is flagged as a protocol violation. The notice is placed at the top of the section where a consultant scanning the spec cannot miss it.

Regression tests cover: negative checks that the stale terms (`3-up`, `notes-only`, `exports/handout.pdf`) no longer appear in `handout.md`; positive checks that the current terms (`2up`, `4up`, `--include-backup`, `output/handouts/`, `speaker_script.md`, `handout_v`) are present; and a consultant-spec alignment check that the NEVER-SKIP notice appears in the Alternative Dispatch Prompts section.

No blueprint change — BC-11.15, BC-11.15a, BC-11.16, BC-11.16a, BC-11.17, and BC-5.15 are all current. This BUG-AUDIT entry is pure doc tidy plus one sentence of agent-prompt hardening.

**Normative requirements:** none new. This entry closes a doc-sync gap; the code contracts it references are stable under their existing normative requirements (REQ-HAND-1..7, REQ-HAND-NOTES-1/-2, REQ-HAND-BACKUP-1, REQ-CONSULT-ALT-DISPATCH-1..3).

**Prior-Art for Rebuild:** per-command user-facing documentation is a separate surface from blueprint contracts and spec requirements, and it drifts independently. After every BUG-AUDIT that changes CLI flags, output paths, or mode enumerations, sweep `commands/*.md` for references to the changed surface and rewrite the affected doc in the SAME commit. A "docs follow later" pattern produces the exact silent-regression mode BUG-AUDIT-73 and BUG-AUDIT-70 both document.

---

### BUG-AUDIT-74: `deck_brief.md` is nominally a living document but lacks canonical structure, machine-readable audience roster, on-session-start read, and post-compaction audit

**Symptom (HIGH, orchestration regression; the cost accrues every long session).** In the documented Apr 2026 lab-meeting deck, the consultant lost audience context after a context-compaction event. Alice had been introduced during the briefing dialog as the lab's engineer in Rome (attending on Teams); several turns later, when she became relevant to a backup slide, the consultant had forgotten her existence and had to re-ask the user. `deck_brief.md` was already the prescribed recovery surface (REQ-CONSULT-2, REQ-CONSULT-4) but four structural gaps made it unreliable:

1. **No canonical section structure** beyond `## Content Signals` (REQ-CONSULT-8). The consultant wrote the brief in whatever shape seemed natural turn-by-turn — facts about audience, intent, and prior decisions ended up scattered or omitted.
2. **No machine-readable audience roster schema.** When the consultant later wanted to enumerate named attendees, it had to re-parse prose — and LLMs are bad at exhaustive prose enumeration.
3. **No "on session start" mandate to read `deck_brief.md` in full.** The consultant's session-start protocol (per project `CLAUDE.md` + `agents/consultant.md`) read `deck_state.json` and `debrief_state.json` but did NOT require a full brief read. After compaction, the in-context memory was lossy and the brief was never consulted to repair the gaps.
4. **No write-through discipline.** The spec implied the brief was produced at the end of discovery; individual facts surfaced mid-dialog were held in conversation memory until a "write the brief" turn. When compaction fired before that turn, those facts were lost.

The combined effect was a spec-blessed living document that lived in name only — it was never the authoritative recovery source in practice because the consultant didn't have the discipline (or the prescribed discipline) to make it one.

**Root cause.** REQ-CONSULT-2 and REQ-CONSULT-4 specified the document's purpose but not its shape, its timing, or its recovery-read protocol. Without a canonical section list, the agent improvised. Without a write-through rule, the agent batched. Without an on-session-start mandate, the agent relied on its fallible in-context memory. Without a post-compaction audit rule, the agent silently proceeded with degraded knowledge until the user caught a hallucination or an omission.

This is the same pattern as BUG-AUDIT-69's filename contract: a naming rule specified agent-side but not code-side is a contract in appearance only. Here a discipline rule specified as "living document" but not with enforceable timing is a discipline in appearance only. The fix is to make each obligation explicit, list the required sections, name the YAML schema for the audience roster, and write the post-compaction audit as a hard rule.

**Detection method.** A long session with multiple rounds of discovery + slide production. At any point after a context-compaction event, ask the consultant to enumerate the named audience members from the briefing. If the answer omits names that were clearly established in the dialog (and that still exist in `deck_brief.md`), the consultant is not consulting its own recovery surface. Independently, grep `agents/consultant.md` for "on session start" plus "deck_brief.md" plus "read in full" — all three phrases must appear in the mandatory-read rule; absence signals the discipline is not wired in.

**Fix summary.** No code change. Fix is spec + blueprint + agent-prompt discipline, mirroring the "orchestration hardening" shape of BUG-AUDIT-73 but for state rather than for a dispatch dialog.

1. **Canonical deck-brief structure** (REQ-CONSULT-DECK-BRIEF-1): fixed section list — `## Audience` (with nested `### Roster` YAML block), `## Room composition`, `## Intent`, `## Duration`, `## Prior decisions`, `## Open questions`, `## Content Signals`. Missing sections during discovery are allowed (they're added as information surfaces); extra sections are forbidden so the file shape is closed.
2. **Machine-readable audience roster YAML schema** inside `## Audience`: a fenced ` ```yaml ` block with an `audience:` list whose entries have required `name` and `role` keys plus recommended `location`, `attendance`, `notes` keys.
3. **Write-through rule:** every confirmed fact is appended to the matching section in the SAME turn it is learned — no batching until end-of-discovery.
4. **On-session-start mandatory read:** after loading `archetypes.json` and `deck_state.json`, the consultant MUST read `deck_brief.md` in full regardless of `sub_phase`.
5. **Post-compaction audit rule:** when the consultant detects it has lost recent facts (summarization event, resume, inability-to-recall, user challenge), it MUST stop, re-read the brief, diff against in-context memory, and surface the loss to the user explicitly. Silent proceeding with degraded state is forbidden.

The entire fix lives in `agents/consultant.md`'s new `## Deck Brief Maintenance` section (placed before `## Command Dispatch Menu` so it's impossible to miss when scanning). The spec clause (REQ-CONSULT-DECK-BRIEF-1) and the blueprint contract (BC-5.16) codify the rule so future edits that drop any of the five obligations fail a doc regression test.

Regression tests (doc-regression style, mirroring BUG-AUDIT-73): `agents/consultant.md` contains the new section; all seven canonical headings appear in the specified order inside the section's example block; the YAML audience-roster example carries the required keys; the three discipline rules (write-through, on-session-start, post-compaction audit) each appear with specific marker phrasings. Spec contains `REQ-CONSULT-DECK-BRIEF-1` and `BUG-AUDIT-74`. Blueprint contains `BC-5.16`.

**Normative requirements:**

- **REQ-CONSULT-DECK-BRIEF-1:** `deck_brief.md` MUST be produced and maintained in the canonical structure defined in `agents/consultant.md`'s Deck Brief Maintenance section. The following obligations MUST be enforced:
  - The section set is `## Audience` (with `### Roster` YAML sub-block using required keys `name`, `role`), `## Room composition`, `## Intent`, `## Duration`, `## Prior decisions`, `## Open questions`, `## Content Signals`. These are the only permitted top-level sections; they MAY be absent during discovery if their content has not yet been established, but MUST NOT be replaced with alternative headings.
  - **Write-through:** *(Superseded by BUG-AUDIT-78 / REQ-MEMORY-CONSULT-1.)* The original clause required the consultant to append every new fact in the same turn. This is now superseded — `deck_brief.md` is owned exclusively by the rewrite agent (BC-5.19); the consultant does NOT write to it. The same-turn capture guarantee is now provided by the `PreCompact` hook firing the rewrite agent against the dialog archive (REQ-MEMORY-DIALOG-1 + REQ-MEMORY-REWRITE-1). The canonical-structure clauses above remain in force unchanged.
  - **On-session-start:** after loading `archetypes.json` and `deck_state.json`, the consultant MUST read `deck_brief.md` in full if the file exists, regardless of `sub_phase`.
  - **Post-compaction audit:** when the consultant detects context loss (summarization, resume, failure to recall a fact the user implies should be known), the consultant MUST re-read `deck_brief.md`, diff against in-context memory, surface the loss to the user explicitly, and proceed only from the brief's authoritative contents. Silent proceeding with degraded state is forbidden.

  REQ-CONSULT-4 (compaction handling) continues to hold; REQ-CONSULT-DECK-BRIEF-1's post-compaction audit clause is its operational refinement. See also `spec/memory_architecture_rfc.md` for the full architectural rationale of the BUG-AUDIT-78 amendment.

**Prior-Art for Rebuild:** "living document" as a spec phrase is insufficient — it names the lifecycle (updated over time) but not the structure (what goes where), the timing (when updates happen), or the recovery protocol (when the document is re-read). A document whose role is to survive context loss MUST have a section contract tight enough that a recipient can locate any fact deterministically, a write-through rule tight enough that no fact can be "in transit" between conversation memory and disk when compaction fires, and an explicit re-read obligation attached to the events that produce context loss. Any recovery surface specified without all three is a recovery surface in name only.

---

### BUG-AUDIT-75: `deck_state.json` and `slides/*.html` can desync silently — `debrief doctor` reconciler + consultant drift-audit discipline + slide-record write-through

**Symptom (HIGH, silent until export; worst-possible timing).** In the documented Apr 2026 lab-meeting deck, after a context-compaction event the project ended with 14 approved slide HTMLs on disk, a complete `speaker_script.md`, `style_locked: true` — but `deck_state.json` still showed `"slides": []` and `"presentations": []`, and `debrief_state.json` still showed `"sub_phase": "discovery/greeting"`. Running `/debrief:export` against this state would have exported zero slides (the export module filters on `status == "approved"` against the empty array). The drift was invisible until export time — the hash-validated state machine does not notice, because an empty state is internally consistent; it just doesn't match disk.

This is the silent-until-critical-moment pattern at its worst: the user only discovers the desync seconds before a presentation, when the export produces an empty PDF.

**Root cause.** Two reinforcing gaps:

1. **No reconciler.** There was no `debrief doctor` (or equivalent) CLI to compare `slides/*.html` against `deck_state.slides[*].slug` and flag drift. The consultant had no mechanical check to run at session start; the first notice of drift was the export module silently producing an empty PDF.

2. **No slide-record write-through discipline.** After a slide-maker dispatch returned GREEN QA, the consultant was supposed to write the `SlideRecord` to `deck_state.json` — but the spec didn't pin down the timing. In long sessions the consultant deferred the write across multiple gates or batched at "end of group," and compaction could fire between the dispatch and the deferred write. The HTML file existed, the record did not, and nothing surfaced the drift.

The fix combines a mechanical reconciler with an explicit discipline rule, mirroring the BUG-AUDIT-74 shape but for slide records rather than for the brief.

**Detection method.** Run `python -m debrief.launcher doctor --project-root <path>` on any project. If the JSON output has `drift_detected: true`, `orphan_files`, or `orphan_records`, state is out of sync with the filesystem. In the Apr 2026 project, the doctor would have reported 14 orphan files immediately on first export attempt (or, better, on session start under the new consultant protocol).

**Fix summary.** Three parallel additions.

1. **`debrief doctor` CLI** (BC-3.16 / REQ-DOCTOR-1). New subcommand of `python -m debrief.launcher`. Pure-function helpers `detect_slide_state_drift(project_root)` and `reconstruct_slide_records_from_files(project_root, slugs)` live in `src/unit_3/launcher.py` (co-located with the existing subcommand dispatcher). The orchestrator `main_doctor(project_root, *, reconstruct=False)` prints a JSON report to stdout and a human-readable summary to stderr. Exit codes: 0 no drift or successful reconstruction, 1 drift detected in report-only mode, 2 reconstruction failure.

   `--reconstruct` appends minimal draft `SlideRecord` entries (status=`"draft"`, qa_passed=False, empty optional fields, last_modified=now) for every orphan HTML file. Each reconstructed slide MUST be re-vetted through the normal red-green cycle — the reconstruction does NOT assume approval. Orphan STATE records (slugs with no matching HTML) are reported but NOT auto-fixed — the appropriate remediation depends on whether the user wants to re-author the slide or delete the record, and the consultant decides with user confirmation.

2. **Consultant drift-audit discipline** (new `## State Drift Audit` section in `agents/consultant.md`, placed immediately before the `## Deck Brief Maintenance` section so both recovery protocols sit together). Three obligations:

   - **On session start (before any dispatch):** run `debrief doctor` immediately after loading state files.
   - **Surface drift to the user explicitly** before proceeding — report the counts, ask before auto-remediating.
   - **Re-run the doctor after context compaction,** paired with the Deck Brief Maintenance post-compaction audit (BC-5.16). Compaction can erode the consultant's mental model of which slides exist; re-grounding on filesystem reality complements re-grounding on the brief.

3. **Slide-record write-through rule** (new Responsibilities bullet in `agents/consultant.md` + BC-5.17). After every GREEN QA decision, the consultant writes the `SlideRecord` to `deck_state.json` in the SAME turn. No batching across gates. Parallel to BC-5.16's brief write-through, for the same reason: context compaction can fire between the dispatch and a later batched write.

No change to slide-maker or qa_checker — they already correctly decline to write state (BUG-AUDIT-62 / BC-5.7 / BUG-AUDIT-63 enforcement hook). The failure mode is entirely on the consultant's side and the fix is consultant-side discipline plus a mechanical drift-detection tool the consultant invokes.

Regression tests cover: `detect_slide_state_drift` on clean / orphan-file / orphan-record / bidirectional / missing-state / missing-dir projects; `reconstruct_slide_records_from_files` minimal-record shape, default values, idempotence; `main_doctor` CLI exit codes (0 / 1 / with `--reconstruct` returning to 0); doc regressions that `consultant.md` contains the `## State Drift Audit` section, the `debrief.launcher doctor` invocation, and the slide-record write-through obligation.

**Normative requirements:**

- **REQ-DOCTOR-1:** The plugin MUST ship a `doctor` subcommand under `python -m debrief.launcher` that compares `slides/*.html` against `deck_state.slides[*].slug` and prints a JSON drift report to stdout. The report MUST include the boolean `drift_detected` field plus the lists `orphan_files` (HTML stems with no matching record) and `orphan_records` (state slugs with no matching file) and the integer `matched_count`. The subcommand MUST accept an optional `--reconstruct` flag that, when passed, appends a minimal draft `SlideRecord` per orphan HTML file (status=`"draft"`, qa_passed=False, empty optional fields, last_modified=current UTC ISO-8601) via `write_deck_state`; reconstruction MUST be idempotent (slugs already present are skipped). Exit codes: 0 no drift or successful reconstruction; 1 drift detected in report-only mode; 2 reconstruction failure. The subcommand MUST NOT auto-delete orphan HTML files or orphan state records — destructive remediation requires explicit user confirmation and is outside this contract.

- **REQ-CONSULT-DOCTOR-1:** The consultant MUST invoke `python -m debrief.launcher doctor --project-root .` at every session start after loading state files and MUST surface any drift to the user explicitly before the next dispatch. The consultant MUST also re-run the doctor after every context-compaction event detected per REQ-CONSULT-DECK-BRIEF-1's post-compaction audit clause. Silent proceeding when drift is detected is a protocol violation.

- **REQ-CONSULT-SLIDE-WT-1:** After every GREEN QA decision from the red-green cycle, the consultant MUST write the `SlideRecord` to `deck_state.json` in the SAME turn via `python -m debrief.debrief_state update_slide …`. Batching the write across gates or deferring to end-of-group is forbidden — the write-through rule exists because context compaction can fire between the dispatch and a later write, leaving the HTML on disk with no matching record (REQ-DOCTOR-1 backstops this failure mode but cannot recover the `content_summary` / `visual_approach` / `design_choices` fields that live only in the in-flight conversation).

**Prior-Art for Rebuild:** "the hash-validated state machine does not notice because the empty state is internally consistent" — structural integrity is not truth. A state machine that checks its own hash is checking that its own history is consistent, not that it matches the world. When the state is supposed to mirror an external filesystem, the integrity check MUST extend to the filesystem — either via a reconciler that runs at every boundary the state might drift (session start, compaction, resume) OR via a write-through discipline tight enough that drift cannot open. Debrief uses both belt-and-suspenders: the doctor catches post-hoc drift; the write-through rule closes the window in which new drift can form.

---

### BUG-AUDIT-76: Consultant loses command-surface awareness after compaction — denies features the installed plugin actually ships

**Symptom (MEDIUM-HIGH, user-trust regression).** In the documented Apr 2026 lab-meeting deck, the user asked *"how do I export the presentation as an HTML file?"* and the consultant replied *"Debrief does not have a built-in HTML export command"* and offered to hand-build a bundler. In fact, `/debrief:present` exists and does exactly this — it generates `output/presentation.html` as a single self-contained file with arrow-key navigation. The user had to remind the consultant that the command existed. Every false-negative-about-features is a direct hit on the product's thesis ("SVP teaches you how to express intent") — the user ends up teaching the tool about itself.

**Root cause.** The consultant's session-start protocol reads state files but does NOT enumerate the commands directory at `${CLAUDE_PLUGIN_ROOT}/commands/`. After context compaction the consultant has only its in-context memory of what commands exist, which is lossy. The agent card (`agents/consultant.md`) carries a hand-maintained `## Command Dispatch Menu` table, but that table captures preconditions and wrong-context guidance — it is not the authoritative list of installed commands, and it can drift from the installed plugin as commands are renamed or added (BUG-AUDIT-9's `debrief_<name>.md` → `<name>.md` rename was the last such drift event).

The failure mode is a compound of two pre-existing conditions that BUG-AUDIT-76 closes together:

1. There is no mechanical helper that returns the live command surface — the consultant would have to list files and read each one to check whether a feature exists, which is N Read calls per question.
2. There is no discipline rule that says *"before you say 'Debrief does not have X', check the live surface"*. The absence of the rule plus the absence of the helper compound to the surface-amnesia failure.

**Detection method.** Ask the consultant about a feature it has recently been distracted from (easy after compaction): *"does Debrief have an HTML export?"*, *"can I save a snapshot?"*, *"is there a way to generate a handout?"*. If any true feature is denied, the command-surface awareness is absent. Independently, grep `agents/consultant.md` for `python -m debrief.launcher commands` — absence signals the live-enumeration invocation is not wired into the consultant protocol.

**Fix summary.** Mechanical helper + consultant discipline, same shape as BUG-AUDIT-75's doctor + drift-audit pair.

1. **`debrief commands` subcommand** (BC-3.17 / REQ-CONSULT-CMD-SURFACE-1 backs this). New CLI subcommand of `python -m debrief.launcher`. Pure helper `list_commands(plugin_root)` returns a dict mapping command slug to the one-paragraph description immediately below the `# /debrief:<slug>` heading. The CLI entry prints pretty-printed JSON to stdout and exits 0. The consultant reads this JSON as the authoritative list of installed commands for the current session.

2. **Consultant command-surface discipline** (new `## Command Surface Awareness` section in `agents/consultant.md`, placed between `## State Drift Audit` and `## Deck Brief Maintenance` so the three compaction-recovery obligations sit as a trio). Three rules:
   - **On session start,** run the enumeration right after the drift audit and the brief read.
   - **Post-compaction re-inject** when context-loss signals fire.
   - **"Does Debrief have X?" check** — before replying with any denial of a feature, consult the live enumeration (or the cached result from the last invocation this session) and grep for the concept the user named. Denial without the live check is a protocol violation.

The hand-maintained `## Command Dispatch Menu` table in the agent card is RETAINED — it carries precondition guidance that the live enumeration doesn't replace. The new section explicitly states the table is a backstop for dispatch, NOT a source of truth about which commands exist.

Regression tests exercise `list_commands` against real command files, the CLI exit-0 contract, and the agent-card contents.

**Normative requirements:**

- **REQ-CONSULT-CMD-SURFACE-1:** The plugin MUST ship a `commands` subcommand under `python -m debrief.launcher` that enumerates installed commands at `<plugin_root>/commands/*.md` and prints a JSON object keyed by slug with the one-paragraph description as the value. The consultant MUST invoke this subcommand at every session start and after every detected context-compaction event, and MUST consult the result before replying *"Debrief does not have X"* for any feature X. Replying with a feature denial without first consulting the live enumeration is a protocol violation.

**Prior-Art for Rebuild:** "agent in-context memory about the tool it runs inside is lossy by construction." Any agent that sometimes says *"I don't have that capability"* needs a mechanical way to check the live capability surface before the denial is emitted — the denial's cost is a user who stops trusting the tool, which compounds across subsequent denials even when correct. Pair the denial-class reply with a live-surface check, the same way the drift-class reply (BUG-AUDIT-75) is paired with a filesystem-audit check.

---

### BUG-AUDIT-77: No canonical table of generator output paths — contract documentation gap; `speaker_script.md` non-write invariant uncodified

**Symptom (LOW-MEDIUM, contract-drift risk).** The bug report that motivated the BUG-AUDIT-68/-70/-73/-77 series asserted that `/debrief:script` silently overwrote a user-authored `speaker_script.md`. Code inspection falsifies the concrete claim — `main_script_generator` writes to `output/<presentation_folder>/script_v{NNN}.md` with filesystem-derived versioning (BC-11.6 / BUG-AUDIT-25) and never touches `speaker_script.md` at project root. Similarly, `/debrief:handout` writes to `output/handouts/handout_v{NNN}.pdf` (BC-11.17 / BUG-AUDIT-21) and `/debrief:export` writes to `output/<folder>/deck_v{NNN}.pdf` (BC-10.4). The current generators are correct.

The residual legitimate concern: **no canonical place in spec or blueprint lists every generator's output path and declares which paths are versioned (non-destructive) vs. fixed (intentionally overwritten on re-run).** A future generator — or a refactor of an existing one — could silently write to `speaker_script.md` and break the canonical notes-source contract BUG-AUDIT-68 established for the handout (BC-11.15a). Without a codified non-write invariant on `speaker_script.md`, such a regression would not be caught by any existing test.

This is a contract-documentation gap, not a present-tense bug. BUG-AUDIT-77 closes it by (a) publishing a canonical table of generator output paths in this spec, (b) codifying the `speaker_script.md` non-write invariant in BC-11.19, and (c) adding a regression test that AST-scans the generator modules for any write expression targeting `speaker_script.md`.

**Root cause.** Generators shipped incrementally (BUG-AUDIT-21 handout, BUG-AUDIT-25 script, BUG-AUDIT-60 view/present, BUG-AUDIT-70 export) and each BUG-AUDIT specified its OWN output path per BC, but no rolling register summarized the output contract across generators. The lack of a cross-generator overview is exactly how the false-overwrite concern arose: a reader scanning spec for "where does the script go?" had no single authoritative answer and had to read multiple BCs to compose one.

**Detection method.** Try to answer "which generator writes where?" from the spec alone without reading any BC. The answer is not present in any single location. Independently, try to grep the source for writes to `speaker_script.md`: `grep 'speaker_script' src/unit_*/` — every hit is a READ (via `_load_speaker_script`) per BUG-AUDIT-68. The invariant holds in code but is not asserted anywhere.

**Fix summary.** Contract documentation + mechanical assertion — no code change.

1. **Generator Output Paths table** (in section 14 or as a dedicated sub-section referenced from the generator REQs). Four rows for the current generators:

   | Command | Output path | Versioning | Destructive? | Citation |
   |---|---|---|---|---|
   | `/debrief:export` | `output/<presentation_folder>/deck_v{NNN}.pdf` | `NNN` derived from `output/<folder>/deck_v*.pdf` (max + 1) | No — new version per invocation | BC-10.4, REQ-EXPORT-3 |
   | `/debrief:script` | `output/<presentation_folder>/script_v{NNN}.md` | `NNN` derived from `output/<folder>/script_v*.md` (max + 1) | No — new version per invocation | BC-11.6, REQ-SCRIPT-2 |
   | `/debrief:handout` | `output/handouts/handout_v{NNN}.pdf` | `NNN` derived from `output/handouts/handout_v*.pdf` (max + 1) | No — new version per invocation | BC-11.17, REQ-HAND-6 |
   | `/debrief:view` | `output/view.html` | None — fixed filename | **Yes** — overwritten on each invocation per BC-11.4 (intentional; file is ephemeral) | BC-11.4, REQ-VIEW |
   | `/debrief:present` | `output/presentation.html` | None — fixed filename | **Yes** — regenerated on each invocation | BC-11.18, BC-11.18a |

   The `/debrief:save` command writes to `output/snapshots/<label>/` and is NOT listed here — it is a user-authored artifact collector, not a deliverable generator. Analogously `/debrief:restore` is a state operator, not a generator.

2. **Non-write invariant on `speaker_script.md`.** No generator module (`src/unit_10/export.py`, `src/unit_11/utility_skills.py`, and any future generator added to the plugin) writes to `<project_root>/speaker_script.md`. The file is the canonical notes source per BC-11.15a / BUG-AUDIT-68 and is user-managed: the user copies a chosen `script_v{NNN}.md` into it (optionally with edits) to activate the BUG-AUDIT-68 handout-merge path, or authors it from scratch. Generators are strictly READ-ONLY against it — enforced by the regression test at `tests/regressions/test_bug_audit_77_generator_output_paths.py` via AST scan of the generator modules for write-expressions targeting `speaker_script.md`.

3. **No confirmation prompts for `/debrief:view` and `/debrief:present`.** Both overwrite fixed filenames by design — the files are ephemeral render products, not user-authored documents. Per-command contracts (BC-11.4, BC-11.18) are explicit about this and BUG-AUDIT-77 affirms them rather than tightening them.

**Normative requirements:**

- **REQ-GEN-PATHS-1:** Every generator command listed in the Generator Output Paths table MUST write only to the path(s) shown in that table. The plugin MUST NOT add a new generator whose output path shadows a user-managed file at project root — specifically `speaker_script.md`, `deck_brief.md`, `style_guide.md`, `style_config.json`, `deck_state.json`, `debrief_state.json`, `ledger.jsonl`, `CLAUDE.md`. If a new generator is added, its output path MUST be appended to the table and a matching behavioral contract added to the blueprint. The non-write invariant on `speaker_script.md` is enforced by a source-AST regression test that parses each generator module and asserts no write expression targets that filename at project root.

**Prior-Art for Rebuild:** "contract drift accumulates in the gaps between BCs." When multiple features add output surfaces incrementally, each documented in its own behavioral contract, the implicit cross-surface invariants (this generator does NOT write where that generator does; this file is exclusively user-managed) live nowhere and can break silently the next time a surface is added. Publish a rolling register — a single table with every output path, destructive/non-destructive status, and citation back to the per-surface BC — every time a new generator lands, and pin the cross-surface invariants (non-write-to-user-managed-files) with source-AST regressions that actively test for regressions rather than just documenting the intent.

---

### BUG-AUDIT-78: Memory architecture RFC adopted — dialog archive + event timeline + rewrite-agent-owned brief; consultant write-through retracted

**Status:** Cycle 1 — spec + blueprint contracts only. Cycle 2 (separate BUG-AUDIT entries per phase) implements per `spec/memory_architecture_rfc.md` §13.

**Problem (recap of the architectural audit prompted by BUG-AUDIT-74).** The BUG-AUDIT-74 model relied on the consultant agent to classify-and-write-through user-surfaced facts into `deck_brief.md` in the same turn they were learned. This is LLM discipline, not mechanical enforcement. Three failure modes remained: silent write-skip (consultant doesn't classify a statement as a fact), deferred-write-collides-with-compaction (consultant intends to write later but compaction fires first), reactive-post-compaction-audit (the rule depends on the agent self-detecting context loss via fallible signals). The Apr 2026 lab-meeting deck's *Alice was forgotten* failure is the canonical exhibit.

**Architecture (full design in `spec/memory_architecture_rfc.md`).** Three persistent surfaces plus one new agent.

- **`.debrief/dialog.jsonl`** — append-only raw dialog archive. Captures every user turn + every consultant reply in the main thread (subagent replies excluded per the Q4 capture rule). Source of truth for *"what was actually said?"* Never deleted.
- **`output/timeline.jsonl`** — append-only typed-event stream. State transitions, gate decisions, slide approvals, exports, AND non-verbal user actions (paper attached, figure selected). Programmatic consumers read directly.
- **`deck_brief.md` + `output/audience.yaml`** — the polished brief plus a standalone roster artifact for programmatic consumers. Both regenerated atomically by the rewrite agent on every trigger event.
- **Rewrite agent (new)** — sole writer of brief + roster. Reads dialog + timeline (and prior brief on bootstrap only). Regenerates from scratch every run for self-healing idempotence. Runs at three triggers: `PreCompact` hook (primary, blocking-ish), `/debrief:quit` (session-end flush), `/debrief:refresh-brief` (explicit). Failures are logged to `.debrief/rewrite_errors.jsonl`; compaction is NEVER blocked.
- **`output/ledger.jsonl`** is **repurposed** as the agent-internal orchestration log; user-facing content (turns, decisions) moves to the new surfaces.

**Detection method.** Long sessions in the BUG-AUDIT-74 architecture lose facts to compaction whenever the consultant's write-through discipline lapses; no tool surfaces the loss until the user notices a recall failure. After Cycle 2 ships, the doctor's `--brief-audit` mode (Phase 5) compares the brief against the dialog archive and surfaces drift; the rewrite-agent's own validation rejects malformed output.

**Fix summary (Cycle 1 — this BUG-AUDIT entry).** Spec + blueprint contracts only. The 10 normative requirements below + the corresponding behavioral contracts in `blueprint_contracts.md` (BC-2.17, BC-2.18, BC-3.18, BC-3.19, BC-5.19, BC-5.20 added; BC-5.16 amended). No code lands in this cycle. Cycle 2 implements per RFC §13 across five phases.

**Normative requirements:**

- **REQ-MEMORY-DIALOG-1:** `.debrief/dialog.jsonl` MUST exist as an append-only JSONL archive recording every main-thread user turn and every consultant reply. Subagent replies (stylist, slide-maker, visual-qa, bug-diagnostic) MUST NOT be archived. Each entry's schema MUST include at minimum: `turn` (int, monotonic), `timestamp` (ISO 8601 UTC), `role` (`"user"` | `"consultant"`), `responding_agent` (string identifying which agent the user was addressing — `"consultant"` | `"stylist"` | etc.), `content` (string), and `metadata` (object containing at least `phase` and `sub_phase`). Marker entries with `event` keys (`"session_start"`, `"compaction"`) MAY appear but MUST NOT truncate the archive. Idempotence-safe append uses a watermark file `.debrief/rewrite_metadata.json` tracking `last_archived_turn`.

- **REQ-MEMORY-TIMELINE-1:** `output/timeline.jsonl` MUST exist as an append-only JSONL stream of typed events. Each entry's schema MUST include: `event` (string from a closed enumeration extensible per feature: `briefing_complete`, `style_locked`, `slide_approved`, `slide_discarded`, `export_done`, `handout_done`, `script_done`, `paper_attached`, `figure_selected`, `backup_session_started`), `timestamp` (ISO 8601 UTC), `turn` (int, the dialog turn at which the event was captured, optional for system-emitted events), and `payload` (object whose schema is event-type-specific). Multiple emitters write to this file (state machine, export/handout/script modules, consultant action-capture); writes MUST be atomic single-line appends.

- **REQ-MEMORY-REWRITE-1:** A new rewrite agent MUST be the SOLE writer of `deck_brief.md` and `output/audience.yaml`. The agent MUST regenerate both files from scratch on every trigger event, reading inputs from `.debrief/dialog.jsonl` + `output/timeline.jsonl` (and, on the very first rewrite of a project only, the prior `deck_brief.md` per REQ-MEMORY-REWRITE-3). The agent MUST NOT read the prior brief on subsequent rewrites — same inputs MUST always produce same output (idempotent, self-healing). Both output files MUST be written atomically via `.tmp` sibling + atomic rename. The brief MUST conform to the canonical section structure of REQ-CONSULT-DECK-BRIEF-1; the roster YAML MUST parse and have required `name`/`role` keys per entry. Output validation failure causes the agent to retain the prior versions and emit an error entry per REQ-MEMORY-REWRITE-4.

- **REQ-MEMORY-REWRITE-2:** The rewrite agent MUST run on exactly three triggers: (1) Claude Code `PreCompact` hook (primary), (2) `/debrief:quit` (session-end flush), (3) `/debrief:refresh-brief` (explicit user-invokable). Triggers SHALL NOT include `SessionStart` (the prior session's PreCompact / `/debrief:quit` already produced a fresh brief; if neither fired, the user invokes `/debrief:refresh-brief` after seeing a stale-brief greeting). Triggers SHALL NOT be periodic.

- **REQ-MEMORY-REWRITE-3:** On the first rewrite of a project (detected by absence of `.debrief/rewrite_metadata.json`), the rewrite agent MAY read the prior `deck_brief.md` as a one-time bootstrap input alongside dialog + timeline. After the bootstrap rewrite completes, the watermark MUST be written. From the second rewrite onward, the prior brief MUST NOT be an input — REQ-MEMORY-REWRITE-1's strict source-derived rule applies. This preserves legacy projects' existing user work.

- **REQ-MEMORY-REWRITE-4:** Rewrite-agent failures (model error, malformed output, validation failure, timeout) MUST cause the `PreCompact` hook to log the error to `.debrief/rewrite_errors.jsonl` (append; schema: `timestamp`, `trigger`, `error_class`, `error_message`, `transcript_path` if available) and exit code 0. Compaction MUST NOT be blocked on rewrite failure. The next trigger event retries from the current dialog tail; transient errors self-heal.

- **REQ-MEMORY-RECALL-1:** `python -m debrief.launcher recall <query>` MUST be available as a CLI tool that greps both `.debrief/dialog.jsonl` and `output/timeline.jsonl` for the query (literal string match, case-insensitive). Output MUST include matched entries with ±2 entries of context, source-labeled (`dialog` vs `timeline`). Output format: pretty-printed table when stdout is a TTY; JSON when stdout is not a TTY. Exit codes: 0 when matches found OR no matches and the archives exist; 1 when a project file is missing or malformed; 3 on usage error. Grep-only for v1; future full-text-search index MAY be added without changing the CLI surface.

- **REQ-MEMORY-CONSULT-1:** The consultant agent MUST NOT write to `deck_brief.md` directly. The rewrite agent (REQ-MEMORY-REWRITE-1) is the sole writer. This requirement supersedes REQ-CONSULT-DECK-BRIEF-1's write-through clause — same-turn fact capture is now provided mechanically by the `PreCompact` hook firing the rewrite agent against the dialog archive, NOT by consultant Write-tool calls. The consultant's role on `deck_brief.md` collapses to read-only consumer.

- **REQ-MEMORY-CONSULT-2:** Before any reply that asserts a fact about a named person, paper, figure, decision, or any prior dialog content — and especially before any reply of the form *"I don't recall X"* / *"the user did not say Y"* — the consultant MUST run `python -m debrief.launcher recall <query>` and ground the reply in the returned hits. Answering from in-context memory alone when the recall tool is available is a protocol violation. This extends BUG-AUDIT-76's *"does Debrief have X?"* discipline (live-enumerate before denying a feature) to dialog content (live-recall before asserting a fact).

- **REQ-MEMORY-LEDGER-1:** `output/ledger.jsonl` SHALL be repurposed as the consultant-internal orchestration log. It continues to record subagent dispatch attempts, internal errors, gate-data writes, hash-validation messages, and similar agent-internal events. User-facing content (user turns, consultant replies, user-action capture, decision events) is migrated OUT of `ledger.jsonl` and into `dialog.jsonl` + `timeline.jsonl` per REQ-MEMORY-DIALOG-1 + REQ-MEMORY-TIMELINE-1. Existing entries in `ledger.jsonl` from before BUG-AUDIT-78 are not migrated — historical readers MAY consult both old ledger and new files; new writers MUST follow the post-BUG-AUDIT-78 split. REQ-CONSULT-3's ledger schema continues to apply for the orchestration-only contents.

**Prior-Art for Rebuild:** "agent-discipline rules without a mechanical backstop are aspiration, not contract." When BUG-AUDIT-74 specified write-through as an in-turn obligation on the consultant agent, the rule was correct in intent but had no mechanism to enforce it — and the failure mode (lossy classification, deferred writes) duly appeared in production. The lesson generalizes: any rule whose violation is silent and whose enforcement depends on LLM judgment WILL fail under load, regardless of how clearly the spec phrases the rule. Pair every such rule with a mechanical backstop — a hook, a reconciler, a capture-then-process pipeline — or expect the rule to be aspirational. BUG-AUDIT-78 retracts BUG-AUDIT-74's write-through aspiration in favor of the capture-then-process pipeline that decouples raw recording from semantic compression.

---

### BUG-AUDIT-79: Memory architecture Cycle 2 Phase 1 — dialog archive append API + recall CLI

**Status:** Cycle 2 Phase 1 of `spec/memory_architecture_rfc.md` §13. The PreCompact hook wiring (Phase 4), the rewrite agent (Phase 2), the event timeline emitters (Phase 3), and the migration tooling (Phase 5) are NOT shipped in this BUG-AUDIT — they will follow in BUG-AUDIT-80..83. This entry covers Phase 1 only.

**Scope.** Implements BC-2.17 (dialog archive schema + watermark) and BC-3.19 (recall subcommand) per BUG-AUDIT-78's Cycle 1 contracts. Concretely:

- `append_dialog_turn(project_root, *, role, responding_agent, content, metadata)` — atomic per-turn append API in `src/unit_3/launcher.py`. Computes the next turn number from the watermark, writes a JSONL line conforming to BC-2.17, advances the watermark in `.debrief/rewrite_metadata.json` atomically. Returns the assigned turn number.
- `read_dialog_archive(project_root)` and `read_event_timeline(project_root)` — read helpers tolerant of missing files / malformed lines.
- `recall(project_root, query)` — pure search function. Greps both archives via case-insensitive recursive substring match across all string-valued fields (including nested metadata and payload). Returns `RecallHit` records with ±2 entries of context per match, source-labeled.
- `main_recall(project_root, query)` — CLI orchestrator wired to `python -m debrief.launcher recall <query> [--project-root PATH]`. Pretty-printed table output when `sys.stdout.isatty()`; JSON list output otherwise. Exits 0 (matches found OR no-matches but archives readable) per BC-3.19.
- `recall` dispatch branch in `main_new()`; usage-line extended.

**Decoupling from PreCompact.** The append API is the per-turn primitive that Phase 4 will wrap with a Claude-Code-transcript parser inside the PreCompact hook. Phase 1 ships the primitive standalone — the regression test seeds the archive via direct API calls, exercising the contract without depending on the hook.

**Detection method (forward-looking).** A user querying the recall CLI on a freshly-installed plugin should see no matches because no append has happened yet (`append_dialog_turn` has no caller in code). After Phase 4 wires the hook, the recall starts surfacing real content. In Phase 1, the value is in having the storage and search primitives ready and tested.

**Normative requirements:** none new. BUG-AUDIT-78 / Cycle 1 already established `REQ-MEMORY-DIALOG-1` and `REQ-MEMORY-RECALL-1`. Phase 1 implements them.

**Prior-Art for Rebuild:** sub-cycle phases that ship standalone primitives BEFORE the integration that uses them tend to ship cleanly — the per-turn append + the recall CLI are testable in isolation, and a regression failure here is unambiguous (the primitive is broken, not the integration). The opposite pattern (ship the hook + agent + primitives all together) tangles the failure modes: a regression could be in the hook, the agent prompt, or the storage layer, and bisection becomes harder. BUG-AUDIT-79 ships the bottom of the stack first by design.

---

### BUG-AUDIT-80: Memory architecture Cycle 2 Phase 2 — rewriter agent-card + rewrite_brief CLI

**Status:** Cycle 2 Phase 2 of `spec/memory_architecture_rfc.md` §13. Builds on BUG-AUDIT-79's dialog archive + recall (Phase 1). The PreCompact hook wiring (Phase 4) and event timeline emitters (Phase 3) are NOT shipped here — they will follow in BUG-AUDIT-81..82. This entry covers Phase 2 only.

**Scope.** Implements BC-3.18 (`rewrite_brief` CLI) and BC-5.19 (rewriter agent-card + hybrid invocation pattern) per BUG-AUDIT-78's Cycle 1 contracts.

**What ships:**

- **`src/unit_1/agents/rewriter.md`** — agent-card declaring `model: claude-sonnet-4-6` + `tools: Read`. Body is the system prompt encoding the BC-5.19 discipline rules: no invention, latest-state-only, canonical sections only, roster YAML schema, subagent-replies-not-archived, sections-may-be-absent, verbatim-when-possible, bootstrap honor system. Output format clause: emit ONLY the brief markdown, no preamble or postscript.

- **`extract_agent_card(card_path) -> (model, system_prompt)`** in `launcher.py` — parses YAML frontmatter (light hand-rolled, avoids PyYAML for the trivial case), returns the `model` value and the body. Raises `ValueError` on malformed frontmatter or missing `model` key.

- **`build_rewrite_inputs(dialog, timeline, prior_brief=None) -> str`** — formats the user-message body. Three labeled sections (BOOTSTRAP if applicable, DIALOG ARCHIVE, EVENT TIMELINE) with JSON-Lines payloads inside fenced code blocks. The closing line instructs the agent to emit the brief markdown directly.

- **`validate_brief_structure(text)`** — verifies `# Deck Brief` heading + canonical top-level section list (no extras).

- **`extract_roster_yaml(brief_text) -> str | None`** — pulls the YAML body from the `### Roster` section's fenced ```yaml ``` block. Returns `None` when the brief has no roster (allowed during early discovery).

- **`validate_roster_yaml(yaml_text)`** — light hand-rolled YAML parser checking that every entry under `audience:` has non-empty `name` and `role` keys. Raises `ValueError` on schema violations.

- **`call_rewrite_agent(model, system_prompt, user_message) -> str`** — Anthropic API call with lazy SDK import. Tests mock this function entirely so the test suite has no API dependency.

- **`log_rewrite_error(project_root, *, trigger, error_class, error_message, transcript_path=None)`** — appends a structured failure entry to `.debrief/rewrite_errors.jsonl` per REQ-MEMORY-REWRITE-4.

- **`main_rewrite_brief(project_root, *, trigger, plugin_root)`** — orchestrator. Reads agent-card → builds inputs → detects bootstrap from `.debrief/rewrite_metadata.json` → calls API → validates structure + roster → atomic dual-write of `deck_brief.md` + `output/audience.yaml` → updates watermark. **Exits 0 on every failure path** per REQ-MEMORY-REWRITE-4; failures are logged, not fatal.

- **`rewrite_brief` dispatch branch** in `main_new()` with `--project-root` and `--trigger` argparse; usage-line extended.

**Decoupling from PreCompact.** The CLI is callable standalone (`python -m debrief.launcher rewrite_brief --project-root .`). Phase 4 will wire the PreCompact hook to invoke it with `--trigger PreCompact`. Tests exercise the CLI via direct function calls with a mocked `call_rewrite_agent`.

**Detection method (forward-looking).** A user invoking `python -m debrief.launcher rewrite_brief` on a project with seed dialog produces a fresh `deck_brief.md` and `output/audience.yaml`. On bootstrap (first invocation), the prior brief (if present) is included as a stylistic baseline; subsequent invocations exclude it. Failures (API errors, invalid output, write failures) appear in `.debrief/rewrite_errors.jsonl` and the prior brief is preserved.

**Normative requirements:** none new. BUG-AUDIT-78 / Cycle 1 already established `REQ-MEMORY-REWRITE-1..4`. Phase 2 implements them.

**Prior-Art for Rebuild:** "decoupling the LLM call from its callers via a single mockable seam makes complex orchestrators testable." `call_rewrite_agent` is a one-function boundary that tests replace with `patch.object(launcher, "call_rewrite_agent", ...)`. Every failure path (API outage, validation failure, write error) is exercised against a deterministic input. The contrast: an orchestrator that calls the API inline at three different points would require three patches and a more fragile test. One seam, many tests.

---

*End of Debrief Stakeholder Specification v1.1*
