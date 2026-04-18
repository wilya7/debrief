# Debrief Comprehensive Smoke Test — Two Sessions, One Pass

The smoke test needs **two Claude Code sessions** because `debrief new` calls `exec claude` — it replaces its shell with a fresh plugin-aware session. A single executor cannot drive across that boundary.

Total time ~75 min. Split as:

- **Phase 0 — Preflight session** (~15 min): any Claude Code session, no plugin required. Runs setup + Profile B + writes `profile_b.md`. Ends by telling the human to launch Phase 1.
- **Phase 1 — Plugin session** (~60 min): launched by `debrief new` in a terminal. The plugin-aware Claude session receives the Phase 1 portion of this prompt (A + C + A15 + A16 + cross-profile) and writes `profile_a.md`, `profile_c.md`, `cross_profile.md`.

Phase 0 runs first because Profile B is CLI-only and catches plugin-schema problems before you invest 60 min in Phase 1. A15 + A16 are at the end of Phase 1 so that C can inspect A's A9–A14 outputs (export, handout, script, presentation, view) before restore wipes them.

## Roles (read first)

This plan has **two distinct agents**. Do not confuse them.

- **Test executor** — whichever Claude session is running the current phase. Its job: invoke `/debrief:*` commands (Phase 1 only), observe filesystem state, run CLI verification via `Bash`, and write bug entries to per-profile files. The executor owns every `**Check:**` line in its phase. If a check fails, append a `BUG-ST-*` entry to the relevant profile file immediately.
- **Debrief consultant** — the presentation-creation agent loaded in the Phase 1 session. It does not know it is being smoke-tested. Treat it as a normal user would — give it the brief, accept its slide proposals, approve/reject at gates. If it does not spontaneously offer something the plan expects (e.g., backup slides), the executor asks explicitly. Do not stall.

## Bug reporting

Each profile gets its own file, written **directly** by the executor (no intermediate `bug_report.md`, no copy step):

- `~/smoke_test/results/profile_a.md`
- `~/smoke_test/results/profile_b.md`
- `~/smoke_test/results/profile_c.md`
- `~/smoke_test/results/cross_profile.md`

Each file starts with:

```markdown
# Smoke Test — Profile X Bug Report
Timestamp: <UTC timestamp>
Executor: Claude Code / <session-id-or-date>
```

Append each finding as:

```markdown
### BUG-ST-<profile>-<N>: <short title>
- **Step:** A4 / B3 / C2 / cross
- **Expected:** <what should have happened>
- **Actual:** <what happened instead>
- **Severity:** CRITICAL / HIGH / MEDIUM / LOW
- **Notes:** <path to evidence, CLI output excerpt, etc.>
```

At the end of each profile, append a summary block: total bugs by severity, steps skipped (with reason), overall assessment.

## Path resolution (set once, reuse)

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/debrief}"
ARCHETYPES="$PLUGIN_ROOT/archetypes.json"
CONSULTANT="$PLUGIN_ROOT/agents/consultant.md"
SMOKE_DIR="$HOME/smoke_test"
PROJECT_DIR="$SMOKE_DIR/project"
RESULTS_DIR="$SMOKE_DIR/results"
```

Executor should resolve these at the start of the run and substitute inline throughout. If `$CLAUDE_PLUGIN_ROOT` is unset and the fallback path does not exist, the executor must find the plugin via `debrief --help` / inspection and abort with a bug entry if it cannot.

## Known issues to verify (not surprises)

The following are **pre-known** bug candidates. When they trigger, log them with severity MEDIUM and move on — do not let them block the run.

- **KB-1** — `/debrief:restore` sweeps orphan HTML in `slides/`, including progressive-disclosure build files (`<slug>_build_1.html`, `<slug>_build_2.html`). Previous run's ledger confirmed: `"swept_slugs": ["ai-solved-code_build_1", "ai-solved-code_build_2"]`. Verify this happens at A15 and log.
- **KB-2** — `/debrief:restore` reverts state and deletes export/handout/script/present/view outputs generated after the save point. This is the expected semantic of restore, **but** if outputs in `output/<dated-folder>/` survive while the state says they don't, that's a real desync bug. Check both after A15.

## Setup

```bash
mkdir -p ~/smoke_test/project ~/smoke_test/results
```

If `~/smoke_test/project/` already contains a Debrief project from a previous run, **archive it** before continuing:

```bash
mv ~/smoke_test/project ~/smoke_test/project.prev.$(date +%s)
mkdir -p ~/smoke_test/project
```

Initialize the profile result files with the header block above.

---

# ═══════════════════════════════════════════════════════════════
# PHASE 0 — PREFLIGHT (current session, no plugin required)
# ═══════════════════════════════════════════════════════════════

In Phase 0 the executor does: (1) the setup above, (2) Profile B below, (3) writes `profile_b.md`. Then it hands off to the human with the launch instructions at the end of Phase 0.

## Profile B — Archetype & Duration Validation (CLI-only)

No project, no Debrief session. Pure file reads + `python -m debrief.launcher` CLI. Log to `profile_b.md`.

### B1: `archetypes.json` schema completeness

Read `$ARCHETYPES`.

**Check** for every archetype entry (lab_meeting, conference_talk, seminar, lecture, journal_club, grant_panel, job_talk, thesis_discussion, investor_pitch, custom):

- All 13 fields present: `consultant_instructions`, `time_default`, `time_range`, `slide_density`, `disclosure_emphasis`, `narrative_style`, `audience_implied`, `acknowledgment`, `handout_default`, `series_default`, `sub_modes`, `rhetorical_emphasis`, `expected_deliverables`.
- `time_range` parseable (e.g., "10-45 min") for all non-custom; `"any"` for custom.
- `audience_implied` is a boolean.
- `acknowledgment` ∈ {"required", "optional", "no"}.
- `expected_deliverables` non-empty list.
- `consultant_instructions` non-empty string.

### B2: Sub-mode definitions

| Archetype | Key | Options |
|-----------|-----|---------|
| journal_club | `paper_scope` | `single_paper`, `multi_paper` |
| job_talk | `position_type` | `postdoc`, `pi_faculty`, `phd_application` |
| thesis_discussion | `degree_type` | `phd`, `masters` |
| investor_pitch | `funding_stage` | `pre_seed`, `seed`, `series_a` |

**Check:** keys + options match; remaining 6 archetypes have `sub_modes: null`.

### B3: `check_duration` — in-range (all 10 should exit 0)

```bash
for pair in \
  "lab_meeting 10" "conference_talk 15" "seminar 45" "lecture 60" \
  "journal_club 20" "grant_panel 12" "job_talk 45" "thesis_discussion 35" \
  "investor_pitch 15" "custom 999"; do
  set -- $pair
  python -m debrief.launcher check_duration --archetype "$1" --minutes "$2" --archetypes-path "$ARCHETYPES"
  echo "exit=$? archetype=$1 minutes=$2"
done
```

**Check:** all 10 exit 0.

### B4: `check_duration` — out-of-range (all 4 should exit 1 and WARN)

```bash
for pair in "conference_talk 5" "lab_meeting 30" "grant_panel 60" "investor_pitch 1"; do
  set -- $pair
  python -m debrief.launcher check_duration --archetype "$1" --minutes "$2" --archetypes-path "$ARCHETYPES"
  echo "exit=$? archetype=$1 minutes=$2"
done
```

**Check:** all 4 exit 1; stderr contains "below" or "above".

### B5: `consultant.md` archetype-awareness

Read `$CONSULTANT`.

- Briefing Protocol references `archetypes.json` and loads the active entry on session start.
- Conditional question logic keyed on `audience_implied`, `series_default`, `sub_modes`.
- Archetype-specific questions for job_talk / journal_club / thesis_discussion / investor_pitch.
- Narrative arc proposal references `narrative_style`.
- Backup-slide section mentions panel mode (grant_panel / conference_talk) and interviewer mode (job_talk).

Append the Profile B summary to `profile_b.md`.

---

## Phase 0 handoff

The executor stops here and prints the following message to the human verbatim:

> **Phase 0 complete.** `profile_b.md` written to `~/smoke_test/results/`. To start Phase 1 (Profile A + C + restore/quit), open a new terminal and run:
>
> ```bash
> cd ~/smoke_test/project
> debrief new
> ```
>
> Select `conference_talk` (option 2). When the plugin-aware Claude session opens, say "hi" first (per Debrief's greeting prompt), then paste everything from the `# ═══ PHASE 1` marker to the end of `SMOKE_TEST_PROMPT.md`. Do NOT paste Phase 0 again.

The executor's Phase 0 responsibility ends here. It must NOT attempt A1–A16 or C1–C8.

---

# ═══════════════════════════════════════════════════════════════
# PHASE 1 — PLUGIN SESSION (launched by `debrief new`)
# ═══════════════════════════════════════════════════════════════

Phase 1 executor: you are in a Claude Code session that was `exec`ed by `debrief new` and has the debrief plugin loaded. The project is `~/smoke_test/project/`. A deck state already exists (the launcher wrote `deck_state.json` etc.). Phase 0 already produced `~/smoke_test/results/profile_b.md`.

Your responsibilities for Phase 1:
- Run A1–A14, then C1–C8, then A15, then A16.
- Write bugs directly to `~/smoke_test/results/profile_a.md`, `profile_c.md`, `cross_profile.md` using the `Write` tool. Do not write `bug_report.md`.
- For every `**Check:**` line, either confirm via filesystem/CLI inspection or log a `BUG-ST-*` entry.
- When the Debrief consultant asks for approval at gates, answer as a normal user (say `APPROVE` / `STYLE APPROVED` at the right moments per the step description).

Re-resolve the path helpers at the start of Phase 1:

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/debrief}"
ARCHETYPES="$PLUGIN_ROOT/archetypes.json"
SMOKE_DIR="$HOME/smoke_test"
PROJECT_DIR="$SMOKE_DIR/project"
RESULTS_DIR="$SMOKE_DIR/results"
```

Now proceed.

---

# Profile A — Full Pipeline Test (conference_talk)

## Artifacts (pass verbatim to the Debrief consultant)

**Reference PPTX:** `/Users/cfusco/Downloads/General-presentation-AI.pptx` (4 slides about AI revolution)

**Presenter script (5 minutes):**
> I strongly believe that AI has reached a point where we can no longer talk about innovation, but rather a revolution!
>
> Let me walk you through this:
>
> AI has solved code, meaning that now anyone can use natural language to produce computational artifacts.
>
> For those who are already coding literate, AI increases their reach and expand what is possible.
>
> But the true potential is realized when we write code that directly integrates AI. This is how we augment human cognition, by writing cognitive software!
>
> And to write cognitive software we need people with a new skill set, these are domain experts with competences from domains like neuroscience and cognitive science.
>
> Introducing these domain experts in the development cycle expands the research and scope of cognitive software, opening up a field which is ripe for plenty of technology patents.

**Style direction:** Clean, minimalistic, sleek, ultra-modern white background with accent colors. Excalidraw aesthetic for diagrams.

## Initialize

The human already ran `debrief new` (option 2: conference_talk) before starting this session, so `deck_state.json`, `debrief_state.json`, `.claude/settings.json`, and `debrief_config.json` are already in place. Verify before A1:

```bash
python -c "import json; d=json.load(open('deck_state.json')); print('archetype:', d.get('archetype'))"
```

Expected output: `archetype: conference_talk`. If not, log a CRITICAL `BUG-ST-a-0` and stop.

### A1 — Briefing + duration validation

- Tell the consultant: 5-minute conference talk, technology audience, use the script above as content.
- Confirm archetype as `conference_talk`.
- Expect the consultant to flag 5 min as below the 10–45 min range.

Checks:
- `deck_brief.md` exists and contains the script's key messages.
- `deck_state.json` has `archetype: "conference_talk"`.
- Consultant flagged the 5-minute deviation (check ledger or consultant dialogue).
- `python -m debrief.launcher check_duration --archetype conference_talk --minutes 5 --archetypes-path "$ARCHETYPES"` → exit 1, WARNING.

### A2 — Reference import

- Import `/Users/cfusco/Downloads/General-presentation-AI.pptx`.

Checks:
- `assets/reference/slides/` contains 4 PNGs.
- `.debrief/draft/analyzer_metadata.json` has `slide_count`, `font_sizes`, dimensions.
- Analyzer success message on stderr.

### A3 — Style dialog

- Run `/debrief:style` with the style direction above.
- Stylist reads each reference PNG before proposing.
- Approve at G2.1 with "STYLE APPROVED".

**BUG-AUDIT-62 BUG-ST-round5-x-1 fix-validation (no stylist direct state writes):** after `promote_style_draft` completes and the consultant's subsequent `sub_phase` transition fires, run any `python -m debrief.debrief_state update --set sub_phase=<value> --project-root .` invocation and confirm NO `WARNING: debrief_state.json hash mismatch — recomputed` line appears in stderr. A hash-mismatch warning at this point indicates a subagent bypassed the canonical write path — log `BUG-ST-round6-a-N`.

Checks:
- `.debrief/draft/style_config.json` has 7 top-level keys.
- `constraints.permitted_diagram_types` includes `rough.js`.
- `roughjs_defaults.roughness >= 2.5`, `bowing >= 2`.
- `.debrief/draft/style_guide.md` has 11 required sections.
- 3 preview slides under `.debrief/draft/preview_slides/`, PNGs under `.debrief/draft/preview_images/`.
- After promotion: `style_locked: true`, `assets/style.css` has ≥20 `--` vars, `.debrief/draft/` cleaned up.

### A4 — Slide production (3 slides, one with progressive disclosure)

- Ask the consultant to propose slide groups (expect 3–5 slides).
- Produce at least 3 slides via `/debrief:slide`:
  - Slide 1: standard (hook — "revolution not innovation").
  - Slide 2: **progressive disclosure** (2 build steps — "AI solved code"). Explicitly instruct the slide-maker to produce build files.
  - Slide 3: standard ("cognitive software").
- Approve each with "APPROVE".

Checks:
- `slides/<slug>.html` exists for all 3.
- For the build slide: `slides/<slug>_build_1.html` and `slides/<slug>_build_2.html` exist.
- `output/screenshots/<slug>.png` for each slide.
- `deck_state.json` has 3 slides with `status: "approved"`, `qa_passed: true`.

### A5 — Tier 2 QA dispatch

Checks (on at least one A4 slide):
- Slide-maker returned WITHOUT dispatching visual-qa itself.
- Consultant dispatched visual-qa via Task after slide-maker returned.
- `output/qa_log.jsonl` has a `tier: "2_merged"` entry for the slug.
- Tier 2 entry includes `veto_checks` (VETO-01..07).

### A6 — Red-green revision loop

- Ask the slide-maker to produce a 4th slide with a deliberate QA issue (external font link is easy).
- QA returns RED.

Checks:
- Consultant presents RED result with specific violations.
- Consultant runs `python -m debrief.qa_checker check_limit`.
- Revised slide goes through another Tier 1 + Tier 2 cycle.
- Revised slide eventually passes GREEN.
- `qa_log.jsonl` shows multiple entries for same slug (iteration progression).
- Approve the final revision.

### A7 — Backup slide session

- After all main slides are approved, ask the consultant: "I'd like backup slides for Q&A." (Do not wait for the consultant to volunteer — ask explicitly.)

Checks:
- Consultant role-plays as a skeptical audience member (Socratic sparring).
- Consultant asks probing questions about the talk's claims before proposing backup slides.
- Produce at least 1 backup slide; approve it.
- `deck_state.json` has backup slide with `backup: true`.
- Backup slide excluded from main slide count in summary.

### A8 — Save

- `/debrief:save` with label `full_pipeline_test`.

Checks:
- `output/snapshots/full_pipeline_test/deck_state.json` exists.
- Confirmation message printed.

### A9 — Export

- `/debrief:export` **without any flags** — the consultant should offer the `--include-backup` choice because A7 produced an approved backup slide.

**BUG-AUDIT-66 fix-validation (consultant asks about backup inclusion):**
- After invoking `/debrief:export` (no flags), the consultant MUST emit the fixed EXPORT prompt: `Ready to export. You have N approved backup slide(s). Include them in the PDF? Reply: - \`main only\` ... - \`include backup\` ...`.
- Reply `main only` for this test.
- Consultant dispatches `python -m debrief.export --project-root .` (no `--include-backup`).
- Then try the flag-bypass: `/debrief:export --include-backup` — the consultant MUST dispatch silently (no prompt).
- If the consultant never asks on the unflagged invocation, or asks on the flagged one, log `BUG-ST-round6-a-N`.

Checks:
- `output/<YYYY_MM_DD_title>/deck_v001.pdf` exists, multi-page (one page per approved non-backup slide).
- Success message names PDF + slide count.
- `output/export_log.jsonl` entry has `playwright_exit_status: 0`.

**BUG-AUDIT-62 BUG-ST-a-e1 fix-validation (export backup-exclusion default):**

- The PDF page count MUST equal the approved non-backup slide count. Example: with 4 main slides + 1 backup approved, the page count is 4, not 5.
- `export_log.jsonl` entry's `slide_count` MUST match the main-only count.
- Then run `/debrief:export --include-backup` (second export invocation) and confirm:
  - `deck_v002.pdf` exists with page count equal to main + backup (e.g., 5).
  - `export_log.jsonl` second entry's `slide_count` reflects the higher count.
- If the default includes backup, log `BUG-ST-round6-a-N`.

### A10 — Handout

- `/debrief:handout` **without any flags** — consultant must ask about BOTH mode AND backup inclusion in a single combined turn.

**BUG-AUDIT-66 fix-validation (consultant asks about mode + backup in one turn):**
- After invoking `/debrief:handout` (no flags), the consultant MUST emit the COMBINED prompt covering both dimensions: `Ready to generate the handout. Two choices: 1. Slides per page: \`2up\` ... or \`4up\` ... 2. Include backup slides? You have N approved backups ...`.
- Reply `2up, main only`.
- Consultant dispatches `python -m debrief.utility_skills handout --mode 2up --project-root .` (no `--include-backup`).
- Flag-bypass check: `/debrief:handout --mode 4up --include-backup` MUST dispatch silently.
- Partial flag: `/debrief:handout --mode 4up` — consultant emits the BACKUP-ONLY prompt (asks only about `--include-backup`, since `--mode` is supplied).
- If any of these fail, log `BUG-ST-round6-a-N`.

Checks:
- `output/handouts/handout_v001.pdf` exists, non-zero bytes.
- Command succeeded without requiring `--mode`.

**BUG-AUDIT-64 fix-validation (handout `--include-backup` parity):**
- Then run `/debrief:handout --include-backup`. Expected: `output/handouts/handout_v002.pdf` produced, and its page count is higher than v001 by the number of approved backup slides.
- Default handout page count should match the main-only slide count (e.g., 4 for the smoke-test deck with 4 main + 1 backup); `--include-backup` variant should match main + backup count (e.g., 5).
- If the default includes backup, or `--include-backup` has no effect, log `BUG-ST-round6-a-N`.

### A11 — Script

- `/debrief:script`.

Checks:
- `output/<folder>/script_v001.md` exists.
- Header contains `**Target duration:** 5 minutes`. **Cluster 3 fix-validation (BUG-ST-a-4):** this must be **5**, not **45**. Pre-fix the regex picked up "45 min" from the duration-warning sentence. A value of 45 means the fix regressed — log as `BUG-ST-round4-a-N`.
- **BUG-AUDIT-62 BUG-ST-a-e2 fix-validation (transition extractor):** for any slide whose `content_summary` contains an explicit `Transition:` marker (case-insensitive; optional Markdown bold/italic around it), the generated script's `### Transition` section MUST contain the text after the marker — NOT the placeholder `Lead into **<next>** by connecting...`. If the placeholder appears for a slide whose `content_summary` has a `Transition:` marker, log `BUG-ST-round6-a-N`.

**BUG-AUDIT-65 BUG-ST-a-e3-script fix-validation (script includes backup):** if the deck has at least one approved backup slide (from A7), the script MUST contain a `## Backup Slides` section heading after the main slide blocks, followed by one entry per backup slide (marked `(backup)` in its header). TIME CHECK markers MUST count only main slides. If the `## Backup Slides` heading is missing or backup slide content is absent, log `BUG-ST-round6-a-N`.
- Each slide has `### Key talking points`, `### Transition`, `### Estimated speaking time`.
- When `content_summary` contains a transition sentence, `### Transition` uses it (not the placeholder).
- TIME CHECK markers appear (e.g., "TIME CHECK (halfway mark)").
- Per-slide time computed from total / slide count, not hardcoded.

### A12 — Present

- `/debrief:present`.

Checks:
- `output/presentation.html` exists.
- Valid HTML (has `<html>` and `</html>`).
- Embeds slide content via `<iframe srcdoc="…">` (BUG-AUDIT-67 / BC-11.18a). `srcdoc` is inline content, NOT a URL reference — the file remains self-contained.
- Each file-backed slide is one `<iframe class="slide-frame" srcdoc="…">` inside its `<div class="slide" data-index="N">` wrapper.
- srcdoc content begins with `<!DOCTYPE` (full slide HTML preserved).
- Contains keyboard-nav JS (arrow keys, Space, Enter, F for fullscreen) AT THE TOP-LEVEL window AND also attached to each iframe's `contentDocument` on load (BC-11.18b).
- Arrow keys targeting `<video>`, `<input>`, `<textarea>`, `<select>` pass through (not intercepted for slide navigation).
- Includes a slide counter at the top level; counter value reflects main + separator + backup counts.
- Progressive-disclosure slide: each of build_1, build_2, final gets its own iframe in sequence.

**BUG-AUDIT-67 fix-validation (visual correctness):** open `output/presentation.html` in a browser. The first slide MUST render with per-slide styling intact — the hook slide should display its heading, styled text, and background per the locked style config. If the page renders as an empty white/black page, the iframe embedding regressed — log `BUG-ST-round6-a-N`. Also verify: pressing arrow right advances one slide at a time (including through build steps); the slide counter increments in lockstep.

**BUG-AUDIT-65 BUG-ST-a-e3-present fix-validation (present includes backup):** the approved backup slide from A7 MUST appear in `output/presentation.html`. Between the last main slide and the first backup slide, a **blank separator slide** must be present (a `<div class="slide"><div class="slide-separator-inner" style="...background:<locked-color>...">` marker with no text content). The slide counter MUST reflect main + builds + 1 separator + backup count. If the backup slide is missing, or the separator slide is missing/has text content, log `BUG-ST-round6-a-N`.

### A13 — View

- `/debrief:view`.

Checks:
- HTML view produced and opened.
- View includes approved slides.

### A14 — State CLI + ledger

```bash
python -m debrief.debrief_state update --set sub_phase=finalization/post_export --project-root .
python -m debrief.debrief_state update --set sub_phase=complete --project-root .
python -m debrief.debrief_state append_ledger --event smoke_test_complete --detail "Profile A A1-A14 passed" --project-root .
```

Checks:
- Each command prints confirmation.
- `debrief_state.json` reflects each update; no hash mismatch warning on second call.
- `ledger.jsonl` contains `"event": "smoke_test_complete"`.
- `ledger.jsonl` has many entries from throughout the session (not just quit/restore).

**Cluster 1 fix-validation (BUG-AUDIT-60):** immediately after the three commands above, attempt a DELIBERATELY invalid sub_phase and assert the write fails at write time (not on next read):

```bash
python -m debrief.debrief_state update --set sub_phase=production/backup_decision --project-root .
# Expected: non-zero exit; stderr contains "sub_phase" and "invalid".
# debrief_state.json must remain unchanged (`sub_phase: complete` from the prior step).
```

Also verify phase derivation: `python -m debrief.debrief_state update --set sub_phase=production/red_green --project-root .` without passing `phase=` should leave `phase: production` in the state file. Log any deviation as BUG-ST-round4-a-N.

Append Profile A summary to `profile_a.md`. **Do NOT run A15 or A16 yet — they are deferred to Phase 4.**

---

# Profile C — Feature Spot-Checks

Same session, same project. Profile A's post-A14 state is live (3 main + 1 backup + revised 4th slide, style locked, exports present). Log to `profile_c.md`.

### C1 — User-provided images

Use a small real image file (e.g., `/Users/cfusco/Downloads/General-presentation-AI.pptx` slide PNG from `assets/reference/slides/`, or any PNG from disk).

- Request a slide via `/debrief:slide` whose brief's `user_assets` field references the image, placed **inline**.
- Approve.
- Request a second slide using the same image as **full-bleed background**.

Checks:
- Image copied to `assets/images/<filename>`.
- Inline slide HTML: `<img src="../assets/images/<filename>">`.
- Slide maintains typography/spacing homogeneity.
- Full-bleed slide: image fills slide area with text overlay.

### C2 — Video placeholder

- Include a video reference (`assets/videos/clip.mp4` — file does not need to exist, just the reference).
- Tell consultant you'll present from browser, not PDF.

Checks:
- Slide HTML contains `<video controls>` with `src="../assets/videos/clip.mp4"`.
- Re-run `/debrief:script`; script includes a video cue with duration for that slide.

### C3 — Confidentiality tag

- Mark a slide as confidential during slide production.

Checks:
- Slide HTML contains `[CONFIDENTIAL — DO NOT DISTRIBUTE]` or `.confidential-tag` element.
- Tag styled with an accent color.
- For `conference_talk` (public): consultant warned about marking public content as confidential.

### C4 — Math / KaTeX

- Request a slide with Bayes' theorem: `P(A|B) = P(B|A)P(A)/P(B)`.
- **Cluster 2 fix-validation (BUG-ST-c-1 / c-2):** do NOT pre-add `katex` to `style_config.json.constraints.permitted_diagram_types`. The default should pass as-is.

Checks:
- Slide HTML contains `.katex-src` / KaTeX markup.
- References KaTeX vendor assets under `../assets/vendor/`.
- `deck_state.json` slide record has `has_math: true`.
- **Fix-validation:** Tier 1 QA passes **clean** on the first try — no INV-10 failure on `katex.min.js`, no VETO-01 failure on `SPAN.katex-mathml`. If either fires, the fix regressed — log as `BUG-ST-round4-c-N`.
- `slide.accepted_violations` is an **empty list** (pre-fix it contained `VETO-01_katex_mathml_overflow_false_positive`).

### C5 — Acknowledgment slide

- For the active conference_talk archetype (`acknowledgment: "required"`), ask for an acknowledgment slide.
- Provide: 3 collaborator names, funding agency, grant number.

Checks:
- Names + affiliations only (no paragraph text).
- Funding agency + grant number present.
- Typography/spacing matches deck.

### C6 — Style re-lock warning + ledger path validation

- With `style_locked: true`, run `/debrief:style` again.

Checks:
- Consultant warns that re-opening may invalidate slides.
- Consultant asks for confirmation.
- Say "cancel" — do not proceed.

**Cluster 4 fix-validation (BUG-ST-c-3):** after the re-lock warning records its event, verify that consultant-side ledger writes land at project root, not in `.debrief/`:

```bash
# Trigger a consultant-style ledger entry via the unit_5 code path
python -c "import sys; sys.path.insert(0, '/Users/cfusco/.claude/plugins/cache/debrief/debrief/1.1.0/src/debrief'); import ledger; from pathlib import Path; ledger.append_ledger_entry(Path('.'), role='system', content='round4 ledger path test', event='smoke_round4_ledger_check')"

# Check outcomes
tail -1 ledger.jsonl | grep "smoke_round4_ledger_check"   # expected: match
ls .debrief/ledger.jsonl 2>&1                              # expected: No such file or directory
```

If `.debrief/ledger.jsonl` exists, the fix regressed — log as `BUG-ST-round4-c-N`.

### C7 — Iteration limit + oscillation

```bash
# pick any approved slug, e.g. hook-revolution
SLUG="smoke-test-limit"
for i in 1 2 3 4 5; do
  python -c "import json,datetime,pathlib; p=pathlib.Path('output/qa_log.jsonl'); p.write_text((p.read_text() if p.exists() else '') + json.dumps({'slug':'$SLUG','tier':'2_merged','timestamp':datetime.datetime.utcnow().isoformat(),'iteration':$i,'passed':False,'veto':False,'failures':['test'],'warnings':[]}) + '\n')"
done
python -m debrief.qa_checker check_limit --slug "$SLUG" --project-root .
```

Checks:
- JSON output has `"limit_reached": true`, `"iteration": 5`.
- If consultant asked to revise this slug, it refuses to re-dispatch and offers accept/override/discard.

### C8 — Filesystem-derived versioning + presentation/manifest refresh

- A9 already produced `deck_v001.pdf`. Run `/debrief:export` once more.

Checks:
- Both `deck_v001.pdf` AND `deck_v002.pdf` exist.
- `deck_state.json` presentation record: `export_count: 0` (vestigial per BUG-AUDIT-23 — confirms NOT a bug).
- `output/export_log.jsonl` has 2 entries.

**Cluster 5 fix-validation (BUG-ST-xp-1 / xp-2):**
- `output/presentation.html` has been **refreshed** by this export. Its slide counter (`<div class="slide-counter">1 / N</div>`) and embedded slide count must match the new post-C deck size (likely 8+, including C-phase additions). Pre-fix the counter stayed frozen at A12's count.
- `deck_state.presentations[0].slide_manifest` now lists the **current** approved non-backup slugs (including acknowledgments, bayes-theorem, video-demo, confidential-data, image slides from Profile C). Pre-fix the manifest was frozen at the 4 slugs from first export.

**BUG-AUDIT-61 C1 fix-validation (full-bleed INV-13 exemption):** the full-bleed image slide in C1 MUST be produced using `<img class="fullbleed" src="...">` — NOT the pre-fix 0×0 hidden-img + CSS-background workaround. Check the slide HTML:

```bash
grep -E 'class="[^"]*fullbleed' slides/c1-image-fullbleed.html   # expected: match (img carries fullbleed class)
grep -E 'width="0"|width:0|width: 0' slides/c1-image-fullbleed.html  # expected: no match (workaround gone)
```

Tier 1 must still pass clean — INV-13 no longer fires on the full-bleed image. If the slide-maker reverts to the 0×0 workaround OR INV-13 trips, log as `BUG-ST-round5-c-N`.

```bash
python3 -c "import json; d=json.load(open('deck_state.json')); m=d['presentations'][0]['slide_manifest']; slides=[s['slug'] for s in d['slides'] if s['status']=='approved' and not s['backup']]; print('manifest:', m); print('live:   ', slides); print('match:', m==slides)"
# Expected: `match: True`. If False, BUG-ST-xp-2 fix regressed.
```

If the counter or the manifest does not reflect the live deck, log `BUG-ST-round4-xp-N`.

Append Profile C summary to `profile_c.md`.

---

# Phase 4 — A15 Restore + A16 Quit (deferred)

These run after C so that C can inspect A's post-A14 outputs. A15 will wipe them; that's the test.

### A15 — Restore

- `/debrief:restore` (no label) to list snapshots.
- `/debrief:restore --label full_pipeline_test`.

Checks:
- List includes `full_pipeline_test`.
- Auto-saves current state before restoring (new `pre_restore_*` label appears).
- `deck_state.json` matches the `full_pipeline_test` snapshot (3 main + 1 backup slides; no C-phase additions; no presentation record).
- **KB-1 verification:** `ledger.jsonl` restore entry includes `swept_slugs` listing the progressive-disclosure build files and any C-phase slide HTML. Log an entry in `profile_a.md` confirming KB-1 behavior.

**BUG-AUDIT-61 A15 fix-validation (restore orphan-output warning):** the restore MUST emit an orphan-output warning because the restored state has `presentations: []` but `output/<YYYY_MM_DD_*>/` folders persist on disk.

- Stderr output from the restore MUST contain the word "orphan" and the dated folder path (e.g., `output/2026_04_18_project/`).
- `ledger.jsonl` MUST contain at least one `{"event": "restore_orphan_warning", ...}` entry whose `orphan_folder` equals the dated folder path and whose `file_count` is a positive integer:

```bash
tail -20 ledger.jsonl | grep restore_orphan_warning   # expected: at least 1 match
python3 -c "import json; [print(e) for e in (json.loads(l) for l in open('ledger.jsonl').read().splitlines() if l.strip()) if e.get('event')=='restore_orphan_warning']"
```

- Orphan files MUST still exist on disk after restore (scope preservation — the warning is advisory, not destructive):

```bash
ls output/2026_04_18_project/deck_v*.pdf   # expected: v001 and v002 still present
```

If the warning is missing OR files are deleted, log as `BUG-ST-round5-a-N`.

### A16 — Quit

- `/debrief:quit`.

Checks:
- Session summary printed (phase, archetype, style_locked, approved slide count).
- `.debrief/state.lock` deleted.
- `.debrief/task_prompt.md` and `.debrief/gate_data.json` cleaned up.
- `ledger.jsonl` exists with entries from throughout the session.
- Exit message includes "Run 'debrief' to resume".

---

# Cross-profile verification

Append to `cross_profile.md`.

- [ ] **No external URLs:** No slide HTML contains `<link>`/`<script>` loading from the internet. (`grep -rE 'https?://(fonts\.googleapis|cdn\.|unpkg)' slides/ assets/` should return nothing.)
- [ ] **No duplicate diagram labels:** rough.js/Excalidraw diagrams label either inside shapes OR adjacent, never both.
- [ ] **No decorative dividers:** If style guide forbids them, no slide contains `<hr>`, `.separator`, or horizontal rules.
- [ ] **Slide numbering:** Present on all slides (or explicitly opted out in style guide).
- [ ] **Closing slide:** Last main slide has a takeaway, not "Thank you" / "Questions?"
- [ ] **State hash integrity:** `debrief_state.json` shows no hash-mismatch warnings during the session.
- [ ] **Ledger populated:** `ledger.jsonl` has entries from throughout (not just quit/restore).
- [ ] **No `pytest.skip`:** If regression tests are run post-smoke, 0 skipped.

**Cluster 6 fix-validation (BUG-ST-a-1 / c-4):**

- [ ] `python -m debrief.qa_checker check_limit --help` output contains `Default: 5` (BUG-ST-c-4 — pre-fix the help did not disclose the default).
- [ ] Across all slide-maker return messages in this session (grep the ledger or agent-output logs), no return contains the literal string `Tier 1 PASSED` or `Tier 1 PASS` as a verdict declaration (BUG-ST-a-1 — the slide-maker must report only the qa_log path and failing invariant IDs, not a PASS verdict). Reports of failing invariants (e.g., `INV-07 failed: external URL`) are permitted and expected in A6.

---

# Quick reference — CLI commands

```bash
# Duration validation
python -m debrief.launcher check_duration --archetype <name> --minutes <N> --archetypes-path "$ARCHETYPES"

# QA iteration limit
python -m debrief.qa_checker check_limit --slug <slug> --project-root .

# State transition
python -m debrief.debrief_state update --set phase=production sub_phase=production/group_planning --project-root .

# Ledger entry
python -m debrief.debrief_state append_ledger --event <name> --detail "<text>" --project-root .

# Style compiler
python -m debrief.style_compiler style_config.json assets/style.css

# Export / Handout / Script / Present / Save / Restore / Quit
python -m debrief.export --project-root .
python -m debrief.utility_skills handout --project-root .
python -m debrief.script_generator --project-root .
python -m debrief.utility_skills present --project-root .
python -m debrief.utility_skills save --label <label> --project-root .
python -m debrief.utility_skills restore --label <label> --project-root .
python -m debrief.utility_skills quit --project-root .
```
