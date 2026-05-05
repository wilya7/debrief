# debrief — AI Presentation Assistant for Scientists

**debrief** is a Claude Code plugin that turns research content — papers, data, narratives — into polished, structured slide decks via a multi-agent workflow. You describe what you want to present and to whom; debrief drives the conversation, picks an archetype, designs a visual style, authors slides one at a time with visual QA after each, and exports the deck as PDF + speaker script + handout.

What debrief actually does:

- **Conversation-first.** A `consultant` agent runs the briefing, asks the right questions per archetype, and dispatches specialist agents (`stylist`, `slide-maker`, `visual-qa`, `rewriter`, `script-writer`).
- **10 presentation archetypes** out of the box — journal_club, lab_meeting, lecture, seminar, conference_talk, thesis_discussion, grant_panel, job_talk, investor_pitch, custom — each with calibrated defaults for duration, slide density, narrative arc, rhetoric, and paper handling.
- **Paper ingestion.** Drop a PDF and debrief extracts figures, captions, and per-figure claims locally with PyMuPDF (no network, no LLM/VLM). Single-figure borrowing, multi-paper concept synthesis, figure-by-figure dissection, or background citation — driven by the archetype's `paper_role`.
- **Project-scoped memory.** The dialog archive (`.debrief/dialog.jsonl`), event timeline (`output/timeline.jsonl`), deck brief (`deck_brief.md`), and audience roster (`output/audience.yaml`) survive context compaction. The `rewriter` agent consolidates them automatically.
- **Deliverables.** Versioned deck PDF, print-optimized handout PDF, presenter speaker script, and a browser-based full-screen presentation mode.
- **12 namespaced slash commands** (`/debrief:slide`, `/debrief:style`, `/debrief:export`, `/debrief:handout`, `/debrief:script`, `/debrief:present`, `/debrief:view`, `/debrief:save`, `/debrief:restore`, `/debrief:refresh-brief`, `/debrief:archive-paper`, `/debrief:quit`).
- **`debrief doctor` diagnostics** with three audit modes: slide-state, brief-state, asset-state.

---

## Tutorial — Happy Paths

Four end-to-end walkthroughs covering the most common archetypes. Each shows the conversational shape and the commands that drop out the other end. None of these are full transcripts — they're distilled to ~15 user/consultant exchanges so you can see the rhythm of a session.

### 2.1 Journal Club — figure-by-figure paper dissection

You're presenting a recent paper to your lab. 20 minutes, peer audience, paper PDF on disk.

```bash
$ cd ~/work/journal_club_2026_05_05
$ debrief new
$ debrief
```

Conversational shape (compressed):

```
consultant: I see you're preparing a journal club. I've set up for a 20-minute presentation.
            Which paper(s) would you like to present? Give me the file path(s).
you:        ~/Downloads/Smith_2026_CellReports.pdf
consultant: [runs paper_analyzer; archives PDF; emits paper_attached event]
            Single paper or topic review across multiple papers?
you:        Single paper.
consultant: Audience is implied (lab/department peers) — confirming. The analyzer found 6 figures:
              1. Hippocampal place cells across conditions
              2. Cross-animal replication of the effect
              3. Chemogenetic silencing
              4. Behavioral readout
              5. Computational model
              6. Supplementary controls
            Reply ALL or a space-separated list of figure numbers.
you:        2 3 4
consultant: [emits figure_selected for each] Now let's discuss the paper before authoring.
            What's your read on the strongest claim and the weakest link in the methods?
you:        [substantive conversation about the paper]
consultant: Shall we proceed with figure-by-figure dissection? I'll propose 5 slides:
            title → context (1 slide) → fig 2 → fig 3 → fig 4 → critique → take-home.
you:        Yes.
consultant: Run /debrief:style to lock the visual identity.
```

Then:

```
/debrief:style       # stylist agent runs the style dialog; produces assets/style.css
/debrief:slide       # slide-maker authors slides one at a time, each followed by visual-qa
/debrief:view        # browser preview as you go
/debrief:export      # versioned PDF in output/<presentation>/deck_v001.pdf
/debrief:script      # speaker_script.md — presenter-ready prose with time checkpoints
/debrief:handout     # 2up handout PDF for the lab
/debrief:quit
```

Files produced (relevant excerpt):

```
output/<2026_05_05_journal_club_smith>/deck_v001.pdf
output/handouts/handout_v001.pdf
speaker_script.md
deck_brief.md
.debrief/paper_analysis_smith_2026_cellreports.md
assets/reference/papers/smith_2026_cellreports/Smith_2026_CellReports.pdf
assets/reference/papers/smith_2026_cellreports/figures/fig_2.png ... fig_4.png
output/timeline.jsonl   # paper_attached, figure_selected×3, slide_approved×N, script_done, ...
```

### 2.2 Lab Meeting — single figure from someone else's paper

5–15 min, peer audience. You read a paper this morning and want to discuss exactly Figure 2 of it tomorrow morning.

```bash
$ cd ~/work/lab_meeting_2026_05_06
$ debrief new
$ debrief
```

```
consultant: 10-minute lab meeting. Do you have data figures to include — yours or borrowed?
you:        I want to discuss only Figure 2 of ~/Downloads/Yarkoni_2022.pdf.
consultant: [runs paper_analyzer; archives PDF; emits paper_attached]
            The analyzer found 4 figures in Yarkoni_2022. Reply with figure numbers.
you:        2
consultant: [emits figure_selected with figure_num=2]
            One slide for Figure 2 of Yarkoni 2022, with proper attribution.
            Three more slides: setup (your motivation), the figure (anchor),
            critique/discussion. Sound right?
you:        Yes — 4 slides total, 10 minutes, conversational tone.
consultant: Run /debrief:style.
```

Lab-meeting-specific defaults (from the archetype): dense slides OK, peer audience implied, minimal background, multi-slide progressive disclosure available, handout default off.

The figure goes into the deck with `Figure from Yarkoni, 2022, <Journal>` rendered as a styled `<figcaption>` (visual-qa enforces VETO-07 for any paper-derived figure).

### 2.3 Conference Talk — narrative-arc deck without a paper

15–45 min, broad audience, your own data, hero-journey narrative.

```bash
$ cd ~/work/sfn_2026_my_talk
$ debrief new
$ debrief
```

```
consultant: I see you're preparing a conference talk. I've set up for 15 minutes, but the
            range is 10-45. How long is your slot?
you:        20 minutes including 5 minutes Q&A.
consultant: 15 minutes of talk + 5 minutes Q&A. Strict one-idea-per-slide for conference talks.
            Who is the audience?
you:        Systems neuroscience researchers, mixed seniority, ~200 people.
consultant: Q&A backup deck: I'll size ~3 backup slides (1 per 1.5 min Q&A). Now: tell me your
            hero journey. What is the question, what is the antagonist, what is the resolution?
you:        [3-4 turns of narrative shaping]
consultant: Proposed arc — title → hook (puzzle) → method → key result × 3 → implications →
            takeaway. 9 slides for the main deck. Then a backup-slide Socratic session.
            Run /debrief:style.
```

Then style → slide → after main deck approved, the consultant runs a Socratic backup-slide session ("what if a reviewer asks why method X over method Y?") and produces 3 backup slides marked `backup: true` in the slide records. They're appended to the deck PDF only when you pass `--include-backup` to `/debrief:export`.

### 2.4 Lecture — multi-paper concept-borrowing with LaTeX and code

60 min, students, drawing from 3 papers. One paper is a methods paper with statistical formulas you want to LaTeX-render; another suggests Python code snippets to teach with.

```bash
$ cd ~/work/repro_neuroscience_lecture_5
$ debrief new
$ debrief
```

```
consultant: I see you're preparing a lecture. Series continuity is the default for lectures —
            which lesson is this in your course?
you:        Lesson 5 of 12: Reproducibility in computational neuroscience.
consultant: 60 minutes, students audience, dense slides with heavy progressive disclosure,
            handout assumed. What should students be able to DO after this lesson?
you:        Run a bootstrap CI on their own data and explain why analysis flexibility
            inflates false-positive rates.
consultant: Good — that's two learning objectives. Do you have papers to draw from?
you:        Three:
            ~/Downloads/Botvinik_2020_NHB.pdf
            ~/Downloads/Yarkoni_2022_GeneralizabilityCrisis.pdf
            ~/Downloads/Efron_1979_BootstrapMethods.pdf
consultant: [runs paper_analyzer on each one in order, emits paper_attached × 3]
            paper_role = concept_source for lecture — these papers are an OPTIONAL resource
            pool. The user's G1.3 reply IS the contract — pick the figures you actually
            want to teach. Here's the figure list per paper:
              Botvinik 2020:
                1. Many-analyst pipeline divergence
                2. Effect-size variability across teams
              Yarkoni 2022:
                1. Generalizability dimensions matrix
                2. Population vs. condition validity
              Efron 1979:
                1. Bootstrap resampling schematic
                2. Coverage table for percentile vs. BCa CIs
            Per-paper reply (e.g., "Botvinik: 2; Yarkoni: 1; Efron: 1 2") or ALL.
you:        Botvinik: 1 2; Yarkoni: 1; Efron: 1 2
consultant: [emits figure_selected × 5]
            For the methods paper (Efron), do you want LaTeX-rendered formulas and code
            snippets in the slides? KaTeX is bundled in assets/vendor/.
you:        Yes — show the percentile-CI formula and a 6-line bootstrap snippet.
consultant: I'll route those to the slide-maker with has_math=true and a code block. The
            slide-maker uses KaTeX for math and a styled <pre><code> for the snippet.

            Proposed structure:
              1. Title + learning objectives
              2. Hook: replication crisis (Botvinik fig 1)
              3. The garden of forking paths (Botvinik fig 2)
              4. Why generalizability is a separate problem (Yarkoni fig 1)
              5. Bootstrap intuition (Efron fig 1 — schematic)
              6. The percentile CI — formula slide [LaTeX]
              7. The bootstrap in 6 lines [code slide, Python]
              8. Coverage in practice (Efron fig 2)
              9. When bootstrap fails
              10. Takeaway + further reading

            That's 10 dense slides for 60 minutes — about 6 minutes per slide, which fits a
            lecture cadence with progressive disclosure builds on slides 3 and 6.
you:        Looks good. Flag slide 6 for builds — formula first, then derivation, then example.
consultant: Build slug: percentile_ci, with percentile_ci_build_1 (formula), percentile_ci_build_2
            (derivation), percentile_ci_build_3 (example), percentile_ci.html (final composite).
            Run /debrief:style.
```

The math slide ends up looking like (rendered HTML):

```html
<section class="math-slide">
  <h2>Percentile bootstrap CI</h2>
  <div class="formula">
    \( \hat{\theta}^{(b)} = T(X^{*(b)}) \) for \( b = 1, \dots, B \)
    <br>
    \( \mathrm{CI}_{1-\alpha} = \big[ \hat{\theta}^{*}_{(\alpha/2)},\ \hat{\theta}^{*}_{(1-\alpha/2)} \big] \)
  </div>
  <figcaption class="figure-caption">Schematic from Efron, 1979.</figcaption>
  <div class="citation">Figure from Efron, 1979, Annals of Statistics</div>
</section>
```

The code slide:

```html
<section class="code-slide">
  <h2>The bootstrap, six lines</h2>
  <pre><code class="language-python">def bootstrap_ci(x, stat=np.mean, B=10_000, alpha=0.05):
    n = len(x)
    samples = np.random.choice(x, size=(B, n), replace=True)
    theta_star = np.apply_along_axis(stat, 1, samples)
    lo, hi = np.quantile(theta_star, [alpha/2, 1 - alpha/2])
    return lo, hi
  </code></pre>
  <div class="citation">After Efron, 1979.</div>
</section>
```

Then:

```
/debrief:style       # stylist proposes pedagogical defaults — clean, high-contrast, numbered slides
/debrief:slide       # slide-maker authors all 10 + 2 build files; visual-qa runs after each
/debrief:export      # 60-minute lecture PDF
/debrief:handout     # mandatory for lectures (handout_default: true) — defaults to 4up for compactness
/debrief:script      # speaker_script.md with time checkpoints ("at 30 min, you should be on slide 6")
/debrief:quit
```

Files produced:

```
output/<2026_05_06_lecture_repro>/deck_v001.pdf
output/handouts/handout_v001.pdf
speaker_script.md
deck_brief.md
.debrief/paper_analysis_botvinik_2020_nhb.md
.debrief/paper_analysis_yarkoni_2022_generalizabilitycrisis.md
.debrief/paper_analysis_efron_1979_bootstrapmethods.md
assets/reference/papers/botvinik_2020_nhb/...
assets/reference/papers/yarkoni_2022_generalizabilitycrisis/...
assets/reference/papers/efron_1979_bootstrapmethods/...
slides/percentile_ci_build_1.html
slides/percentile_ci_build_2.html
slides/percentile_ci_build_3.html
slides/percentile_ci.html       # final composite for non-build navigation
slides/<other slides>.html
```

---

## Installation

debrief is distributed as a Claude Code plugin. Installation is handled automatically when you open a debrief-initialized project in Claude Code.

**Prerequisites:**

- [Claude Code](https://claude.ai/code) installed
- [Miniforge or Conda](https://github.com/conda-forge/miniforge) available on your system
- LibreOffice on macOS / Linux (see Dependencies → System dependencies)

**Setup:**

1. Clone the marketplace repo and add it as a Claude Code marketplace, then install the plugin:
   ```bash
   git clone https://github.com/wilya7/debrief.git
   # In Claude Code:
   /plugin marketplace add /path/to/debrief
   /plugin install debrief@debrief
   ```
2. To start a project, change into a working directory and bootstrap:
   ```bash
   debrief new
   debrief
   ```
3. The first run creates a dedicated conda environment from `environment.yml` (5–15 minutes), installs Playwright's Chromium, verifies vendor assets, and launches Claude Code with the consultant agent active.

The plugin uses a dedicated `debrief` conda environment. You do not manage it manually — `debrief --rebuild-env` recreates it from scratch when needed.

---

## Archetypes

Every project picks one archetype at creation time. The archetype calibrates timing, slide density, narrative shape, audience defaults, paper handling, and rhetoric. You can override any default during the briefing.

| Archetype | Default duration | Range | Slide density | Narrative shape | `paper_role` | `paper_required` |
|---|---|---|---|---|---|---|
| `lab_meeting` | 10 min | 5–15 | dense | brief context → data → next steps | concept_source | no |
| `conference_talk` | 15 min | 10–45 | light | hero journey with antagonist | background_reference | no |
| `seminar` | 45 min | 30–60 | medium | logical progression, clarity over persuasion | concept_source | no |
| `lecture` | 60 min | 30–90 | dense | stepwise concept building, learning objectives | concept_source | no |
| `journal_club` | 20 min | 15–30 | medium | figure-by-figure critical dissection | primary_dissection | **yes** |
| `grant_panel` | 12 min | 10–15 | medium | structured argument: worthy problem → right idea → I can deliver → real impact | background_reference | no |
| `job_talk` | 45 min | 20–45 | medium | scientific identity narrative + career trajectory | background_reference | no |
| `thesis_discussion` | 35 min | 20–45 | medium | hero journey with aggressive cuts to highlights | primary_document | **yes** |
| `investor_pitch` | 15 min | 5–20 | light | problem → solution → market → traction → team → ask | background_reference | no |
| `custom` | 20 min | any | medium | borrowed from matched archetypes | concept_source | no |

`paper_required: yes` means the consultant proactively demands the paper as the first archetype-specific question. Otherwise papers are optional but accepted.

`paper_role` defines downstream behavior when a paper is provided: `primary_dissection` (figure-by-figure), `primary_thematic` (cross-paper composite), `primary_document` (defended subject), `concept_source` (resource pool, single-figure-OK), `background_reference` (cited but not auto-converted to figure slides).

---

## Command Reference

All commands are namespaced as `/debrief:<name>` (no prefix on filenames per BUG-AUDIT-10).

| Command | One-line | Typical use |
|---|---|---|
| `/debrief:slide` | Enter the slide authoring loop. Creates new slides or opens visual revision for existing ones. | After style lock; the main production loop. |
| `/debrief:style` | Run the style dialog with the stylist agent. Produces `assets/style.css`. | Once per project, before any slide is authored. |
| `/debrief:view` | Generate a query-driven HTML view of selected slides for visual inspection. | During production, to preview WIP. |
| `/debrief:export` | Render the complete deck to a versioned PDF. | After all main slides approved. |
| `/debrief:script` | Generate the canonical speaker script from the deck's full memory. | After export. |
| `/debrief:handout` | Generate a versioned handout PDF combining slide thumbnails with speaker notes. | After script. |
| `/debrief:present` | Launch a browser-based full-screen presentation. | At rehearsal / talk time. |
| `/debrief:archive-paper` | Retroactively archive a paper PDF when the consultant's automatic trigger missed it. | Recovery path; idempotent. |
| `/debrief:refresh-brief` | Force the rewriter to regenerate `deck_brief.md` and `output/audience.yaml`. | Mid-session, after major decisions; or after `/debrief:archive-paper`. |
| `/debrief:save` | Checkpoint the deck state and ledger to a named snapshot. | Before risky restructuring. |
| `/debrief:restore` | Restore the project to a previously saved snapshot. | Recovery from a snapshotted state. |
| `/debrief:quit` | Flush state, clean transient artifacts, print a session summary, and return. | End of session. |

The `consultant` agent manages the workflow — most users only invoke `/debrief:style` and `/debrief:slide` explicitly; the other commands are dispatched automatically at the deck-complete finalization milestone.

---

## Working with Papers

debrief can ingest academic paper PDFs during discovery and extract their figures, captions, and per-figure claims into your presentation. **Every archetype accepts papers** — the question is whether the consultant proactively asks for one (`paper_required`) and how the paper is used once provided (`paper_role`). See the Archetypes table above for the per-archetype mapping.

When you supply a paper PDF path during discovery, the consultant runs `paper_analyzer` regardless of archetype. The `paper_role` shapes *how* the paper is used downstream; the `paper_required` flag determines whether the consultant *proactively demands* one. You can also override the role for a specific paper during discussion — e.g., a lecture user can say "I just want to cite this one as background, not build a figure slide" and that paper becomes `background_reference` for this deck.

### Single-figure case

For `concept_source` archetypes (lecture, lab_meeting, seminar, custom), the figure-selection gate (G1.3) accepts either `ALL` or a space-separated list of figure numbers. A reply of `2` selects only Figure 2 — the consultant will build one slide for that figure with proper attribution and **will not** propose additional figure slides "for completeness." Your selection is the contract.

### How extraction works

When you provide a PDF path during discovery, debrief runs a local, deterministic pipeline (PyMuPDF — no network calls, no LLM/VLM):

1. Parses the PDF, extracts text, section structure, figure captions, and figure images.
2. Distributes figure images across captions on each page (multi-figure-per-page is handled correctly — each caption gets its own image).
3. Extracts a 1–3 sentence claim per figure from the text following the caption.
4. Pulls metadata (title, authors, journal, year) from PDF metadata + page-1 heuristics, with conservative fallback to `Unknown` rather than wrong guesses.
5. Writes `.debrief/paper_analysis_<slug>.md` (captions + claims + narrative arc) and `assets/reference/papers/<slug>/figures/fig_N.png` per figure.
6. Archives the source PDF to `assets/reference/papers/<slug>/<original-filename>.pdf`.
7. Emits `paper_attached` to `output/timeline.jsonl` and sets `papers_provided=true` in `debrief_state.json`.

Slides built from extracted figures carry a citation line (`Figure from <Authors>, <Year>, <Journal>`) and the caption is rendered as a styled `<figcaption>` element, not body text — VETO-07 enforces this regardless of archetype.

### When paper handling goes off-script

If the consultant accepts a paper but you later find that `assets/reference/papers/` is empty (the source PDF was never archived) or `output/timeline.jsonl` lacks a `paper_attached` event, the deterministic pipeline was bypassed — typically because the trigger detection missed your file (drag-and-drop, bare filename, or verbal mention without a path).

**Recovery:** invoke the explicit retroactive command

```bash
/debrief:archive-paper /path/to/your-paper.pdf
```

This runs `paper_analyzer` directly, sets `papers_provided=true`, and emits `paper_attached`. It is idempotent — safe to run twice on the same PDF. After running, invoke `/debrief:refresh-brief` once so the rewriter picks up the new event into `deck_brief.md`.

**Diagnosis:** to check the asset state of any project, run

```bash
debrief doctor --project-root . --asset-audit
```

The doctor reports drift between `assets/`, `output/timeline.jsonl`, and `debrief_state.json` — paper-figure-shaped files in the wrong location, missing events, flag mismatches, REQ-ASSET-1 slug-prefix violations.

---

## Memory Architecture

debrief persists every meaningful fact about your deck inside the project. Unlike Claude Code's session memory (lossy across compaction), debrief's memory survives compaction by design.

| Surface | Path | Purpose | Writer |
|---|---|---|---|
| Dialog archive | `.debrief/dialog.jsonl` | Append-only record of every user turn + every consultant reply. | `append_dialog_turns_from_transcript` (called by the rewriter) |
| Event timeline | `output/timeline.jsonl` | Typed-event stream — `paper_attached`, `figure_selected`, `slide_approved`, `style_locked`, `script_done`, `handout_done`, etc. | code-path emitters + consultant via `python -m debrief.launcher emit_event` |
| Deck brief | `deck_brief.md` | Canonical recovery surface — audience, intent, duration, prior decisions, open questions, content signals. | rewriter agent (sole writer) |
| Audience roster | `output/audience.yaml` | Machine-readable audience list with names, roles, attendance, notes. | rewriter agent |
| Slide records | `deck_state.json` `slides[]` | Per-slide canonical metadata (slug, status, group_id, qa_passed, accepted_violations, …). | `python -m debrief.debrief_state update_slide` |
| Rewrite metadata | `.debrief/rewrite_metadata.json` | Watermark for what's been rewritten, last-archived turn, agent version. | rewriter |

The **rewriter agent** runs automatically at three triggers:

1. **PreCompact hook** — Claude Code is about to compact; the rewriter consolidates new dialog turns into the brief before the in-context memory is lost.
2. **`/debrief:refresh-brief`** — manual on-demand refresh after major decisions.
3. **`/debrief:quit`** — final consolidation at session end.

The **`recall` CLI** searches both archives:

```bash
python -m debrief.launcher recall "Yarkoni" --project-root .
# or via the consultant card's recall_discipline section, automatically
```

When the consultant needs to assert a fact about prior dialog content (especially negative facts like "you did not mention X"), it grounds the reply in `recall` results rather than its lossy in-context memory.

---

## Deliverables

A complete debrief session produces these artifacts:

| Artifact | Path | Triggered by | Purpose |
|---|---|---|---|
| Deck PDF | `output/<presentation>/deck_v{NNN}.pdf` | `/debrief:export` | The presentation. Versioned within each presentation folder. |
| Handout PDF | `output/handouts/handout_v{NNN}.pdf` | `/debrief:handout` | Print-optimized leave-behind with thumbnails + speaker notes (2up or 4up). Versioned globally. |
| Speaker script | `speaker_script.md` | `/debrief:script` | Presenter-ready prose, one section per slide, with time checkpoints and transitions. Single canonical file (not versioned). Backed up to `.debrief/script_backups/` on each regeneration. |
| Browser presentation | `output/presentation.html` | `/debrief:present` | Self-contained single-file HTML with keyboard navigation; opens fullscreen in your default browser. |
| Slide screenshots | `output/screenshots/<slug>.png` | automatic during slide production | Used for handouts + visual-qa input. |
| Deck brief | `deck_brief.md` | rewriter (PreCompact / `/debrief:refresh-brief` / `/debrief:quit`) | Canonical project memory. Read-only for the user — the rewriter is sole writer. |
| Audience roster | `output/audience.yaml` | rewriter | Machine-readable audience list. |
| Paper analyses | `.debrief/paper_analysis_<slug>.md` | `paper_analyzer` (per attached paper) | Captions, claims, narrative arc per paper. |
| Archived papers | `assets/reference/papers/<slug>/<original.pdf>` | `paper_analyzer` | Source PDFs — never modified. |
| Extracted figures | `assets/reference/papers/<slug>/figures/fig_<N>.png` | `paper_analyzer` | Cropped per-figure PNGs at source resolution. |

Snapshots (`/debrief:save --label <name>`) are stored under `.debrief/snapshots/` and contain a copy of `deck_state.json`, `ledger.jsonl`, and the current `slides/` HTML. `/debrief:restore --label <name>` rolls those three surfaces back; everything else (style, brief, assets, output) is left untouched.

---

## Diagnostics — `debrief doctor`

`debrief doctor` is a read-only health check for any project. Use it when something looks off, when you've recovered from a hook block, or as a sanity check before exporting.

```bash
debrief doctor --project-root .
```

Three audit modes (composable):

| Flag | What it checks | Drift signals |
|---|---|---|
| (default) | Slide-state — `slides/*.html` files vs. `deck_state.json` slide records | orphan HTML files, orphan SlideRecord entries |
| `--brief-audit` | Memory architecture — brief presence + structure + roster YAML validity + watermark alignment + rewrite staleness | invalid brief, invalid roster, drift between dialog-archive watermark and last rewrite |
| `--asset-audit` | Asset usage — paper handling, REQ-ASSET-1 slug-prefix compliance, event/state consistency | paper-figure-shaped files in `assets/images/` while `assets/reference/papers/` is empty; `papers_provided` flag mismatch; missing `paper_attached` events; image files lacking `<slug>_` prefix |

Exit codes:

- `0` — no drift in the requested audits.
- `1` — drift detected (report-only mode). The JSON output identifies the specific drift.
- `2` — `--reconstruct` was requested and remediation failed.

Combine flags for a comprehensive check:

```bash
debrief doctor --project-root . --brief-audit --asset-audit
```

`--reconstruct` is the only remediation flag. It applies to slide-state drift only — appends minimal draft `SlideRecord` entries for orphan HTML files. Brief-side and asset-side drift are read-only by design; remediation requires explicit user action (e.g., `/debrief:refresh-brief` or `/debrief:archive-paper`).

---

## Troubleshooting

### "Hook blocked the memory write" / writes outside project denied

You may see the consultant report something like *"Hook blocked the memory write (debrief project policy)"*. This is by design and not a bug:

- The PreToolUse hook `bin/check-write-auth` blocks every Write/Edit outside the project directory, including writes Claude Code's runtime sometimes attempts to its own auto-memory location (`~/.claude/projects/<encoded>/memory/`).
- Debrief has its own project-scoped memory architecture (`.debrief/dialog.jsonl`, `output/timeline.jsonl`, `deck_brief.md`, `output/audience.yaml`, slide records in `deck_state.json`) — all inside the project, all written by Python CLIs that bypass the hook.
- Nothing is lost: the dialog archive captures every turn implicitly, and the rewriter agent consolidates the brief at PreCompact and on `/debrief:quit`.

If you see this message, the consultant in newer plugin versions (post-BUG-AUDIT-92) will silently re-route the action to the appropriate debrief CLI. If you are on an older plugin and see it interrupt your flow, the safe response is "continue" — your project memory is fine.

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

### Paper PDF not archived / `assets/reference/papers/` is empty

The deterministic paper pipeline was bypassed — typically because the trigger detection missed your file (drag-and-drop, bare filename, or verbal mention without a path). Recovery:

```bash
/debrief:archive-paper /path/to/your-paper.pdf
/debrief:refresh-brief
```

See "When paper handling goes off-script" above.

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

**Stale state across sessions:**
Run `debrief doctor --project-root . --brief-audit --asset-audit` to identify drift. The doctor's JSON output names the specific surface that's out of sync.

---

## Uninstallation

To remove debrief from a project:

1. Remove the `.claude-plugin/` directory from the project root.
2. Delete `deck_state.json`, `debrief_state.json`, and the `slides/` directory if no longer needed.
3. The debrief conda environment can be removed with `conda env remove -n debrief` if desired.

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
| `PyMuPDF` | >=1.23 | PDF parsing and figure extraction (paper_analyzer) |
| `json-repair` | >=0.25 | Fault-tolerant JSON parsing for LLM-generated state |
| `anthropic` | >=0.40 | Anthropic SDK — used by the rewriter and script-writer agents (BUG-AUDIT-93) |

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

Vendor JavaScript and CSS libraries are bundled under `assets/vendor/` for offline operation:

- `mermaid.min.js` — diagram rendering
- `rough.min.js` — sketchy hand-drawn shapes
- `katex.min.js` + `katex.min.css` + `katex-fonts/` — LaTeX math rendering

See `assets/vendor/VERSIONS.md` for version and provenance information. Versions are pinned with SHA-256 hashes verified at bootstrap (BUG-AUDIT-16).

---

## Acknowledgments

### PaperBanana

debrief borrows architectural patterns from [PaperBanana](https://github.com/dwzhu-pku/PaperBanana) by dwzhu-pku, licensed under the Apache-2.0 license. Specifically, the style-guide critic loop, tiered evaluation approach, and exemplar-driven slide generation patterns were informed by PaperBanana's design.

**Attribution:** PaperBanana — Copyright (c) dwzhu-pku. Licensed under Apache-2.0.

**Patent risk disclosure:** PaperBanana and debrief incorporate techniques for AI-assisted presentation generation. Some methods used in automated slide composition, figure-to-slide layout mapping, and LLM-guided visual design may be subject to patent claims by third parties. Users and deployers of debrief should be aware of this potential patent risk, particularly in commercial contexts. No patent license is granted by this software's Apache-2.0 license beyond what is expressly stated therein. See the `NOTICE` file for full details.

### License

debrief is distributed under the Apache License 2.0. See the `LICENSE` file at the repo root for the full text. The license also lives at `debrief/LICENSE` inside the plugin distribution.
