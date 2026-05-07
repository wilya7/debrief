# Debrief Blueprint v3 — Contracts (Tiers 2 and 3)

**Date:** 2026-04-11
**Spec:** Debrief Stakeholder Specification v1.1
**Blueprint version:** 3.0

---

## Unit 1: Plugin Scaffold

### Tier 2 — Signatures

```python
# Unit 1 has no Python source code.
# All artifacts are static files (JSON, YAML, Markdown, Bash, CSS).
# The only Python-adjacent artifact is the bin/check-write-auth bash script.
# Its behavioral contract is in Tier 3.
#
# Stub for ast.parse() compliance:
from typing import NoReturn

def check_write_auth_contract() -> NoReturn:
    """
    Placeholder documenting the check-write-auth exit-code contract.
    Actual implementation is a bash script at bin/check-write-auth.
    Exit 0  -> write authorized.
    Exit 2  -> write denied (message on stderr, shown to LLM).
    """
    raise NotImplementedError
```

### Tier 3 -- Behavioral Contracts

**BC-1.1 Manifest completeness.** `plugin.json` must contain exactly the keys: `name`, `version`, `description`, `author`, `license`, `keywords`. No additional top-level keys. Value of `name` must be `"debrief"`. Value of `version` must be `"1.1.0"`. Value of `license` must be `"Apache-2.0"`. `author` MUST be an object with at least a `name` field (e.g., `{"name": "Carlo Fusco and Leonardo Restivo"}`); the plain-string form fails Claude Code's Zod schema validator (see BUG-AUDIT-6). The following keys MUST NOT appear as top-level keys in `plugin.json`: `skills`, `agents`, `hooks`, `commands`. Claude Code auto-discovers those from their default subdirectories at the plugin root (`./skills/`, `./agents/`, `./hooks/hooks.json`, `./commands/`); attempting to declare any of them as a string path causes Zod validation failure and the plugin fails to load entirely (see BUG-AUDIT-6).

**BC-1.2 Commands layout (auto-discovered, namespaced slash commands).** The plugin root MUST contain a `commands/` directory. Claude Code auto-discovers user-invocable slash commands from this default path; `plugin.json` MUST NOT declare a `commands` field (BC-1.1). The `commands/` directory MUST contain exactly nine flat `.md` files: `slide.md`, `style.md`, `export.md`, `save.md`, `view.md`, `reset.md`, `quit.md`, `script.md`, `handout.md`. Each file is plain markdown with **no YAML frontmatter**. The first non-blank line of each file MUST be a `# /debrief:<name>` H1 heading, where `<name>` matches the filename stem (e.g., `commands/slide.md` starts with `# /debrief:slide`). **Filenames MUST NOT include a plugin prefix.** Claude Code registers a command file `commands/<name>.md` as `/<plugin>:<name>` by prepending the plugin namespace from `plugin.json`; it does NOT strip any prefix from the filename. Naming a file `debrief_slide.md` produces the double-prefixed invocation `/debrief:debrief_slide`, which is wrong. The first-line `# /debrief:<name>` heading is documentation only — it does not influence command registration, only the filename does. See BUG-AUDIT-10 for the historical incident where debrief inherited svp's buggy `<plugin>_<name>.md` convention and produced `/debrief:debrief_slide` before being corrected. The plugin root MUST NOT contain a `skills/` directory populated with user-invocable `SKILL.md` files — the `skills/` subdirectory is reserved for model-auto-invoked knowledge capabilities (not currently used by Debrief), and populating it with user-invocable SKILL.md files produces bare-named slash commands that collide with Claude Code built-ins (see BUG-AUDIT-9).

**BC-1.2a (deleted in BUG-AUDIT-9).** The previous BC-1.2a required SKILL.md frontmatter in `skills/<name>/SKILL.md`. That contract is obsolete after the skills→commands migration — command files have no frontmatter, so there is no frontmatter contract to enforce. This contract number is retained as a placeholder so cross-references from BUG-AUDIT-1..8 remain valid; see BC-1.2 above for the current commands layout contract.

**BC-1.3 Agents layout (auto-discovered).** The plugin root MUST contain an `agents/` directory. Claude Code auto-discovers agents from this default path; `plugin.json` MUST NOT declare an `agents` field (BC-1.1). The `agents/` directory MUST contain exactly five `.md` files: `consultant.md`, `slide-maker.md`, `visual-qa.md`, `bug-diagnostic.md`, `stylist.md`. No additional `.md` files.

**BC-1.3c Stylist schema anchoring.** `agents/stylist.md` MUST enumerate, verbatim, all seven top-level keys from `_REQUIRED_KEYS` (`src/debrief/style_engine.py`): `colors`, `typography`, `spacing`, `layout`, `data_viz`, `constraints`, `provenance`. It MUST reference the bundled template at `templates/style_config.json` (path as used by the agent; `${CLAUDE_PLUGIN_ROOT}/templates/style_config.json` when expanded) and MUST instruct the agent to load that template as the starting skeleton rather than invent the schema. It MUST NOT contain the phrase `"Only write to \`assets/style.css\`"` — that legacy instruction contradicts REQ-STYLE-4 and REQ-STYLE-5 and produced BUG-AUDIT-13. The agent prompt MUST reference at least one of the canonical sources (`REQ-STYLE-4`, `BC-6.8`, or `_REQUIRED_KEYS`) so future maintainers can find the source of truth. A regression test in `tests/regressions/test_bug_audit_13_stylist_schema.py` enforces every part of this contract by importing `_REQUIRED_KEYS` from `style_engine` directly so it tracks drift automatically.

**BC-1.3a Agent file frontmatter.** Each agent `.md` file is a YAML frontmatter block (delimited by `---` on the first line and a closing `---`) followed by the agent system prompt body. The frontmatter must declare all five fields defined in stakeholder spec §6.1 (`name`, `description`, `model`, `maxTurns`, `tools`) and the field values must match the per-agent frontmatter in spec §6.2 verbatim for the corresponding agent. All five agent `.md` files must have valid YAML frontmatter per spec §6.2. A file that begins with anything other than `---` loses its declared `model`, `maxTurns`, and `tools` constraints silently; no agent file is exempt.

**BC-1.3b Agent frontmatter structural verification.** The unit 1 test suite must include an assertion, for each of the five agent `.md` files, that the file starts with `---\n`, contains a matching closing `---` delimiter before the body, and that the block between the delimiters parses as valid YAML containing every field listed in BC-1.3a with the exact values required by spec §6.2. File-existence and non-empty assertions alone do NOT satisfy this contract. The previous version of BC-1.3b also covered `SKILL.md` files; after the BUG-AUDIT-9 skills→commands migration, command files have no frontmatter and no frontmatter test applies to them. The command-file structural verification (heading shape, absence of frontmatter) is handled by a separate `TestCommandFileStructure` class in `tests/unit_1/test_scaffold.py`; see BC-1.2.

**BC-1.4 Hooks layout (auto-discovered, Form B required).** The plugin root MUST contain a `hooks/hooks.json` file. Claude Code auto-discovers hooks from this default path; `plugin.json` MUST NOT declare a `hooks` field as a string path (BC-1.1).

`hooks.json` MUST follow Claude Code's plugin hooks schema, documented canonically in spec §7.1 and authoritatively at `code.claude.com/docs/en/plugins-reference.md`. The required shape (referred to as "Form B" throughout BUG-AUDIT-7):

1. The file MUST contain a single top-level key `hooks` whose value is a record (object). Event keys (`PreToolUse`, `PostToolUse`, etc.) MUST NOT appear at the top level directly — they live inside the `hooks` record. A file with top-level event keys fails Zod validation with `expected record, received undefined` at path `["hooks"]` (see BUG-AUDIT-7).

2. Inside the `hooks` record, each event key maps to a **list of matcher wrappers**. A matcher wrapper is an object with two fields: `matcher` (a string in regex form, e.g., `"Write|Edit"`) and `hooks` (an array of hook handlers).

3. Each hook handler inside the inner `hooks` array is an object with a `type` field plus handler-specific fields. `type: "command"` handlers have `command` (string) and `timeout` (integer seconds). `type: "agent"` handlers have `prompt` (inline string) and `timeout` (integer seconds). Other handler types (`inline_prompt`, etc.) are out of scope for this plugin.

4. Debrief `hooks.json` MUST declare exactly: a `PreToolUse` matcher wrapper with `matcher: "Write|Edit"` and one inner `command`-type handler whose `command` field is the literal string `"\"${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth\""` (that is: the JSON string value contains the variable reference wrapped in literal escaped double quotes so shell expansion produces a quoted path token), with `timeout: 10`; and a `PostToolUse` matcher wrapper with `matcher: "Write|Edit"` and one inner **`command`**-type handler (as of BUG-AUDIT-17, replacing the earlier `agent`-type form that was broken by Claude Code v2.1.107 upstream — see BUG-AUDIT-12b) whose `command` field is the literal string `"\"${CLAUDE_PLUGIN_ROOT}/bin/qa-run-on-write\""` with `timeout: 120`. `${CLAUDE_PLUGIN_ROOT}` is expanded automatically by Claude Code at hook-runtime — do NOT hand-expand. **The escaped double quotes around the command reference are load-bearing (BUG-AUDIT-12a):** when `${CLAUDE_PLUGIN_ROOT}` expands to a filesystem path containing whitespace (e.g., `/Users/cfusco/Nextcloud/coding projects/...`), an unquoted command string is split by `/bin/sh` into multiple tokens, the first of which is interpreted as a non-existent command. Wrapping the reference in escaped double quotes produces `"/path with spaces/bin/check-write-auth"` (or `"/path with spaces/bin/qa-run-on-write"`) after expansion, which `sh` treats as a single token. Any `command`-type hook handler that references `${CLAUDE_PLUGIN_ROOT}` or `${CLAUDE_PLUGIN_DATA}` — not just these specific PreToolUse/PostToolUse entries — MUST follow the same escaped-double-quote pattern. Violations are caught by `tests/regressions/test_bug_audit_12_hook_path_quoting.py`'s negative sentinel plus the new BUG-AUDIT-17 regression tests.

**No `type: "agent"` hooks (BUG-AUDIT-17).** As of BUG-AUDIT-17, debrief's `hooks.json` MUST NOT contain any handler with `type: "agent"` anywhere in the file — under PreToolUse, PostToolUse, or any other event key. The prior PostToolUse agent handler was broken upstream by Claude Code v2.1.107's *"Messages are required for agent hooks. This is a bug."* regression (documented in BUG-AUDIT-12b) and is replaced permanently by the command-type handler above. Debrief will NOT reintroduce agent hooks even if Claude Code upstream fixes the regression — the command-hook + slide-maker-Task architecture (see BC-8.4) is strictly superior because it is deterministic, version-independent, and easier to test. A regression test in `tests/regressions/test_bug_audit_17_qa_dispatch.py` performs a deep scan of `hooks.json` asserting no handler has `type: "agent"`; violations fail pytest loudly.

**`bin/qa-run-on-write` script contract.** The plugin root MUST contain an executable Python script at `bin/qa-run-on-write` (workspace path `src/unit_1/bin/qa-run-on-write`, delivered path `debrief1.0-repo/debrief/bin/qa-run-on-write`). The script MUST: (a) read a hook input JSON from stdin; (b) extract `tool_input.file_path`; (c) silently exit 0 if the path is absent, not a string, not ending in `.html`, or does not contain `slides` in its path components; (d) otherwise compute `slug = Path(file_path).stem`, resolve `project_root` from `$CLAUDE_PROJECT_ROOT` env var or `os.getcwd()` fallback, and invoke `python -m debrief.qa_checker --slide-path <slide_path> --screenshot-path output/screenshots/<slug>.png --project-root <project_root>` as a subprocess with a 120-second timeout; (e) always exit 0, even if the subprocess fails or times out — PostToolUse hooks MUST NOT block Write/Edit operations per spec §7.3. Failures are reported to stderr and (via `qa_checker.py`'s own output) to `qa_log.jsonl` for downstream consumption. The script is stdlib-only (no third-party dependencies); it imports `json`, `os`, `subprocess`, `sys`, and `pathlib` only. See BUG-AUDIT-17.

If the inline-object form of `hooks` in `plugin.json` ever becomes the preferred distribution mechanism for this plugin, that is a separate design change requiring its own contract amendment; the current contract requires the file-based form at the default path.

**BC-1.5 settings.json.** Must contain exactly `{"agent": "consultant"}`. No other fields.

**BC-1.6 environment.yml completeness.** Must pin `python=3.11`, include `jq` from conda-forge, and include pip dependencies: `playwright>=1.40`, `python-pptx>=0.6.21`, `PyMuPDF>=1.23`, `json-repair>=0.25`. No conflicting channels (all from `conda-forge`). The environment MUST NOT pin `libreoffice-still` — that package is Linux-only on conda-forge and blocks macOS bootstrap (see BUG-AUDIT-4). LibreOffice is a system dependency, discovered at bootstrap time per BC-1.6a, not a conda-managed package.

**BC-1.6a LibreOffice discovery and macOS shim.** The `bin/debrief` bash wrapper MUST run a LibreOffice discovery step at spec §24.4 step 5.6 (after the post-activation smoke test, before the pip install marker check). The step MUST: (1) check whether `soffice` is already on PATH via `command -v soffice`; (2) if not, and `uname -s` returns `Darwin`, and `/Applications/LibreOffice.app/Contents/MacOS/soffice` exists and is executable, write a wrapper shim at `${CONDA_PREFIX}/bin/soffice` containing `#!/usr/bin/env bash` followed by `exec /Applications/LibreOffice.app/Contents/MacOS/soffice "$@"`, and `chmod +x` the shim. The heredoc delimiter used to create the shim MUST be quoted (e.g., `<<'DEBRIEF_SOFFICE_SHIM_EOF'`) so variable expansion is disabled and the hardcoded path is written verbatim; (3) if neither PATH nor the macOS location yields a usable `soffice`, print to stderr: `ERROR: LibreOffice (soffice) is required but was not found.` followed by platform-specific install instructions (macOS: libreoffice.org/download or `brew install --cask libreoffice`; Linux: `apt install libreoffice` or `dnf install libreoffice`; other: libreoffice.org/download) and exit with code **1** (not 2 — missing system deps are not env corruption per §9.3.1). The discovery block MUST be delimited by sentinel comments `# BEGIN LibreOffice discovery` and `# END LibreOffice discovery` so regression tests can locate and scope-check it. The shim is idempotent: once written, re-running `bin/debrief` short-circuits at the `command -v soffice` check. Destroying the env via `--rebuild-env` removes the shim automatically because it lives inside `${CONDA_PREFIX}/bin`. See BUG-AUDIT-4.

**BC-1.7 check-write-auth exit codes.** The script must exit 0 to authorize, exit 2 to block. Exit code 1 is not used. Any other exit code is a bug. The stderr message on exit 2 must be human-readable and identifiable by the LLM.

**BC-1.8 check-write-auth stdin parsing.** The script reads the Claude Code tool-invocation JSON from stdin via `jq -r '.tool_input.file_path'`. If `jq` exits non-zero or the parsed path is null/empty, the script exits 2 with `ERROR: Unable to parse tool invocation.` It must NOT exit 0 on parse failure.

**BC-1.9 check-write-auth path escaping.** If the resolved absolute path of `tool_input.file_path` does not begin with `$PWD/`, the script exits 2 with `ERROR: Write outside project directory is not permitted.`

**BC-1.10 check-write-auth style-lock enforcement.** If the resolved path is under `slides/` or equals `assets/style.css`, the script reads `$PWD/deck_state.json`. If `style_locked` is not `true` (absent, false, or file does not exist), exit 2 with `ERROR: Style config not yet locked. Run /debrief:style first.`

**BC-1.10a check-write-auth state-file protection (BUG-AUDIT-63 / REQ-WRITE-AUTH-STATE-1).** If the resolved path equals `$PWD/deck_state.json` or `$PWD/debrief_state.json`, the script exits 2 with an error message naming the canonical CLI alternative. For `debrief_state.json`: `ERROR: Direct writes to debrief_state.json are not permitted. Use: python -m debrief.debrief_state update --set <field>=<value> --project-root .`. For `deck_state.json`: `ERROR: Direct writes to deck_state.json are not permitted. Use the canonical write_deck_state path via the appropriate CLI (e.g., python -m debrief.utility_skills promote_style_draft for style-lock).`. This check runs BEFORE BC-1.10's style-lock check. Python code paths (`atomic_write_json`, `write_debrief_state`, `write_deck_state`) are NOT affected — this hook sits on the Write tool only.

**BC-1.11 check-write-auth unconditional pass.** For paths not under `slides/`, not equal to `assets/style.css`, and not equal to `deck_state.json` or `debrief_state.json` (state-file protection per BC-1.10a), the script always exits 0 regardless of style-lock status.

**BC-1.12 VERSIONS.md format (vendor).** Each entry follows `<filename>\tversion <ver>\tsha256:<hash>\t<source_url>`. Every file in `assets/vendor/` (excluding `VERSIONS.md` itself and `*.LICENSE.txt`) must have a corresponding entry. The `mermaid.min.js`, `rough.min.js`, `katex.min.js`, `katex.min.css`, and all `katex-fonts/*.woff2` files must be listed. Per BUG-AUDIT-16, every entry in VERSIONS.md MUST also satisfy three load-bearing invariants: (a) the file exists at the declared path relative to `assets/vendor/`, (b) the file's SHA-256 matches the manifest hash exactly (no drift), (c) the hash corresponds to the **real** upstream library bytes from the `source_url`, not to a placeholder stub that happens to match a fake self-consistent entry. The regression test at `tests/regressions/test_bug_audit_16_vendor_real_files.py` enforces (a) and (b) directly, plus file-size lower bounds that a placeholder stub cannot satisfy (rough > 10 KB, mermaid > 100 KB, katex.js > 100 KB, katex.css > 10 KB, KaTeX woff2 > 5 KB) so a future fake-hash regression cannot slip through.

**BC-1.12a Vendor sync parity.** The vendor directory MUST be byte-identical between workspace (`src/unit_1/assets/vendor/`) and delivered (`debrief1.0-repo/debrief/assets/vendor/`). A regression test in `test_bug_audit_16_vendor_real_files.py` hashes each file under both directories and asserts equality file-by-file. Rationale: the delivered repo is the shipped artifact; any drift between workspace and delivered means the workspace tests exercise different bytes than users get at install time. See BUG-AUDIT-16.

**BC-1.13 archetypes.json completeness.** Must have exactly eight top-level keys: `lab_meeting`, `conference_talk`, `seminar`, `lecture`, `journal_club`, `grant_panel`, `job_talk`, `custom`. Each key maps to an object with exactly six required fields: `presentation_type`, `time_default`, `content_signal_defaults`, `rhetorical_emphasis`, `expected_deliverables`, `key_defaults_text` — all six are required per Section 24.26 ("All fields are required per key"). Missing or extra top-level keys are a bug. Missing fields within any archetype entry are a bug.

**BC-1.14 README sections.** `README.md` must include sections: Installation, First Run, Quick Start, Troubleshooting, Uninstallation, Dependencies, Acknowledgments. The Acknowledgments section must reference PaperBanana with an Apache-2.0 attribution and the patent risk disclosure per Section 25. The README must NOT instruct the user to run `conda env create` or `conda activate` manually.

**BC-1.15 NOTICE attribution.** `NOTICE` must attribute PaperBanana (dwzhu-pku/PaperBanana) and include the patent risk disclosure. The Apache-2.0 license text must appear in `LICENSE` verbatim.

**BC-1.16 `bin/debrief` bootstrap contract.** The `bin/debrief` bash wrapper MUST implement spec §24.4 steps 1–10 verbatim. Specifically, it must: (1) detect `conda` on PATH and exit 1 with the miniconda install message if missing; (2) `source "$(conda info --base)/etc/profile.d/conda.sh"`; (3) check env existence via `conda env list | awk '{print $1}' | grep -qx debrief`; (4) create the env from `${CLAUDE_PLUGIN_ROOT}/environment.yml` via `conda env create -f ... -n debrief` on first run, printing the `First-run setup: creating the debrief conda environment (this takes 5-15 minutes)...` message, and cleaning up partial envs on failure; (5) `conda activate debrief`; (5.5) run the post-activation dependency smoke test `python -c 'import playwright, pptx, fitz, json_repair'`, exiting with code 2 and the Section 9.3.1 error on ImportError; (6) gate `pip install -e "${CLAUDE_PLUGIN_ROOT}"` on `${HOME}/.cache/debrief/pkg_version_<version>.marker`, where `<version>` is read from `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`; (7) gate `python -m playwright install chromium` on `${CONDA_PREFIX}/.debrief_chromium_installed`; (8) run `python -m debrief.launcher preflight` for vendor hash verification; (9) dispatch on `${1:-}` — `new` runs `python -m debrief.launcher new "$(pwd)"` (which itself writes `.claude/settings.json` per BC-3.13) before launching Claude Code; bare invocation requires `deck_state.json` in cwd and otherwise prints the "No project found" error and exits 1, then runs `python -m debrief.launcher ensure_settings "$(pwd)"` to self-heal `.claude/settings.json` (BC-3.13 / BUG-AUDIT-8) before launching; and `--rebuild-env` deletes pkg-version markers, runs `conda env remove -n debrief -y`, and re-executes the script with `DEBRIEF_REBUILD_DONE=1` to prevent infinite recursion; (10) `exec claude` (with NO flags — no `--plugin-dir`, no `--plugin`) as the final launch. Claude Code auto-discovers the project-scoped `.claude/settings.json` written in step 9 and loads the debrief plugin via the marketplace mechanism, namespacing skills as `/debrief:*` and avoiding collisions with built-in commands like `/export`, `/save`, `/quit` (see BUG-AUDIT-8). The historical `--plugin-dir` form (BUG-AUDIT-5) loaded the plugin without marketplace context, leaving skills bare-named — that load path is retired. The script MUST NOT be a thin shim that only sets an environment variable and immediately delegates to `claude` — any version that omits steps 1–9 is a bug (see BUG-AUDIT-1).

**BC-1.16a `CLAUDE_PLUGIN_ROOT` fallback must follow symlinks.** When `CLAUDE_PLUGIN_ROOT` is unset at script entry, `bin/debrief` MUST resolve its own filesystem location by walking any symlink chain on `${BASH_SOURCE[0]}` before computing the plugin root as the script's parent directory. The resolution MUST work on macOS without GNU coreutils (i.e., without `readlink -f`); a pure-bash `while [[ -L ]]` loop using `readlink` and `cd -P` is the portable idiom and is required. The resolution block MUST be delimited by the sentinel comments `# BEGIN CLAUDE_PLUGIN_ROOT resolution (symlink-safe)` and `# END CLAUDE_PLUGIN_ROOT resolution (symlink-safe)` so that regression tests can extract and functionally exercise it in isolation. Installing `bin/debrief` as a symlink on `PATH` (e.g., `~/.local/bin/debrief → .../debrief1.0-repo/debrief/bin/debrief`) MUST produce a `CLAUDE_PLUGIN_ROOT` equal to the real plugin root, not the symlink's parent. Violations are a bug (see BUG-AUDIT-3a).

**BC-1.16b Env-create cleanup must not misreport a partial env.** When `conda env create -f "${CLAUDE_PLUGIN_ROOT}/environment.yml" -n debrief` fails, the cleanup branch MUST check env existence via `conda env list | awk '{print $1}' | grep -qx debrief` BEFORE attempting `conda env remove -n debrief -y` and BEFORE printing the `Partial debrief env exists and could not be removed automatically.` message. If no `debrief` env exists after the failed create, the script MUST print only `ERROR: conda env creation failed. See output above for details.` and exit 1, so that the real error (e.g., `EnvironmentFileNotFound`, network failure, disk full) printed by `conda env create` above is the visible diagnosis. The "Partial debrief env exists" path is reserved for the case where a partial env actually exists and cannot be removed automatically. Violations are a bug (see BUG-AUDIT-3b).

**BC-1.17 No competing Python entry point.** The delivered repo's `pyproject.toml` MUST NOT declare any `[project.scripts]` entry whose key is `debrief`. `bin/debrief` is the sole user-facing entry point for all Debrief operations per spec §9.4 line 683, and a `pip install -e` of the package — performed by `bin/debrief` itself at §24.4 step 6 — must not register a competing console-script shim that would bypass the bash bootstrap. The pyproject source-of-truth for this fact is the delivered `debrief1.0-repo/debrief/pyproject.toml` (no workspace `src/` copy exists; `scripts/generate_assembly_map.py`'s `assemble_plugin_project()` does not write `pyproject.toml`). Any future Stage 5 assembly logic that generates or amends this file must preserve this invariant. Violations are a bug (see BUG-AUDIT-1).

**BC-1.18 Anthropic SDK is a declared dependency (BUG-AUDIT-93).** Both `pyproject.toml` `[project.dependencies]` AND `environment.yml` pip section MUST declare `anthropic>=0.40`. The launcher's hybrid invocation pattern (BC-3.18 rewriter, BC-3.20 script-writer) lazy-imports the SDK at the call site so a missing dep surfaces as `ModuleNotFoundError` rather than a top-level import crash; that pattern is correct, but the dep MUST still be declared so a default install (`bin/debrief` bootstrap via environment.yml, or `pip install .` reading pyproject.toml) ships a working env. Pre-fix the dep was undeclared and both `/debrief:script` and the rewriter (PreCompact + manual) silently failed on every fresh install — the rewriter's silent failure was particularly load-bearing because `deck_brief.md` and `output/audience.yaml` were never synthesized. The two install specs MUST agree on the minimum version. `bin/debrief` step 5.5 smoke test MUST also import `anthropic` so a corrupt env is caught at bootstrap, not at the first invocation. A regression test in `tests/regressions/test_bug_audit_93_anthropic_dependency.py` enforces all four invariants (declared in pyproject, declared in environment.yml, version match, smoke-test imports it).

**BC-1.19 Preflight subcommand validation precedes env smoke test (BUG-AUDIT-95).** `bin/debrief` MUST validate `$1` BEFORE running step 1 (conda detection), step 5 (`conda activate debrief`), and step 5.5 (post-activation smoke test). The preflight block MUST execute immediately after the `--rebuild-env` handler (which has its own early-exit semantics) and MUST handle two cases without invoking conda or Python: (a) when `$1` is empty AND `deck_state.json` is absent in `$(pwd)`, print `ERROR: No project found in the current directory. Run 'debrief new' to create one.` to stderr and exit code 1; (b) when `$1` is anything other than `""`, `new`, or `--rebuild-env`, print `Usage: debrief [new|--rebuild-env]` to stderr and exit code 1. The preflight MUST use only bash builtins (`[[ ]]`, `case`) — it MUST NOT invoke `command -v conda`, `conda activate`, `python`, or any logic that depends on the conda env existing. The preflight block MUST be delimited by sentinel comments `# BEGIN preflight subcommand validation` and `# END preflight subcommand validation` so regression tests can locate and scope-check it. The error strings MUST be byte-identical to the corresponding strings in the late case dispatch (step 9) so that any future code path that bypasses the preflight still produces consistent output. The late case dispatch is retained for actual launch logic (`new` runs `python -m debrief.launcher new`; bare invocation with `deck_state.json` present runs `python -m debrief.launcher ensure_project` and launches Claude Code) — the preflight only short-circuits the user-input-error cases. Violations are a bug (see BUG-AUDIT-95).

**BC-1.20 Env removal robustness — no `--force`, surface stderr, post-check by listing (BUG-AUDIT-96).** Both the `--rebuild-env` branch and the env-creation cleanup branch in `bin/debrief` MUST: (1) invoke `conda env remove -n debrief -y` WITHOUT redirecting stderr to `/dev/null`, so conda's actual failure message (lock errors, permission errors, metadata corruption) reaches the user; (2) after the remove attempt, verify the env's actual absence by running `conda env list | awk '{print $1}' | grep -qx debrief` and treating absence-after-remove as success regardless of `conda env remove`'s exit code (this decouples the script from conda's version-dependent exit-code semantics — e.g., `EnvironmentLocationNotFound` exits 0 on conda 25.7 but exited 1 on earlier versions); (3) print recovery hints that reference `rm -rf "$(conda info --base)/envs/debrief"` rather than `conda env remove -n debrief --force` — the `--force` flag was removed from `conda env remove` between conda 22.x and 25.x, and modern conda rejects it with `unrecognized arguments: --force`. The script MUST NOT contain any string matching the regex `conda env remove[^|;\n]*--force` in any active code path or user-facing message. The recovery hint string MUST contain `rm -rf` AND a path expression that resolves to the env directory under the active conda installation (the canonical form is `rm -rf "$(conda info --base)/envs/debrief"`). Violations are a bug (see BUG-AUDIT-96).

---

## Unit 2: State Management Library

### Tier 2 — Signatures

```python
from __future__ import annotations
import hashlib
import json
import os
import fcntl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class StateCorruptError(Exception):
    """Raised when a state file cannot be repaired or contains invalid values."""


@dataclass
class SlideRecord:
    slug: str
    title: str
    status: str  # "draft" | "approved" | "needs_revision" | "discarded"
    backup: bool
    content_summary: Optional[str]
    visual_approach: Optional[str]
    design_choices: Optional[str]
    forks_not_taken: Optional[str]
    user_recommendations: Optional[str]
    qa_passed: bool  # True when QA has passed for this slide (may be True via accepted violation)
    accepted_violations: list[dict[str, str]]  # [{"invariant": str, "reason": str, "accepted_at": str}]
    last_modified: str  # ISO 8601 timestamp
    group_id: Optional[str]
    user_assets: list[str]  # relative paths of user-provided images included in this slide
    has_math: bool  # True if slide contains rendered LaTeX math


@dataclass
class PresentationRecord:
    folder: str
    created_at: str
    slide_manifest: list[str]
    export_count: int
    script_count: int
    handout_count: int
    separator_position: Optional[int]
    separator_content: Optional[str]


@dataclass
class DeckState:
    project_name: str
    created_at: str
    archetype: str
    style_locked: bool
    closing_slide: Optional[str]
    slides: list[SlideRecord]
    presentations: list[PresentationRecord]


@dataclass
class DebriefState:
    phase: str
    sub_phase: str
    # active_agent enum per Section 17.5:
    #   "consultant" | "slide_maker" | "stylist" | "qa" | "none"
    # "none" is required during production/diagnostic (bug-diagnostic runs
    # autonomously, user is not interacting with it per P-BP-3).
    # "qa" corresponds to the visual-qa agent (underscore vs hyphen convention).
    active_agent: str
    archetype: str
    current_group_id: Optional[str]
    current_slide_slug: Optional[str]
    pending_gate: Optional[str]
    last_gate_response: Optional[str]
    red_green_iteration: int
    red_green_started_at: Optional[str]
    group_slide_index: int
    group_slide_count: int
    backup_mode: bool
    completed_groups: list[str]
    pre_view_state: Optional[dict[str, Any]]
    view_deferred: bool
    closing_slide_pending: bool
    group_revise_slug: Optional[str]
    style_import_mode: Optional[str]
    reference_provided: bool
    reference_modality: Optional[str]
    papers_provided: bool
    selected_figures: Optional[list[int] | str]
    session_started_at: str
    state_hash: str


def read_deck_state(project_root: Path) -> DeckState:
    """
    Read and validate deck_state.json from project_root.

    Uses json_repair as a safety net for LLM-generated JSON.
    Raises StateCorruptError if repair fails or required top-level fields
    are missing after repair.
    """
    ...


def write_deck_state(project_root: Path, state: DeckState) -> None:
    """
    Atomically write deck_state.json using write-to-tmp then os.rename().
    No file lock (single-session model, no concurrent writers for deck state).
    """
    ...


def get_approved_slides(
    state: DeckState,
    backup: Optional[bool] = None,
) -> list[SlideRecord]:
    """
    Return slides with status == 'approved', preserving array order.
    If backup is not None, filter to slides where slide.backup == backup.
    """
    ...


def get_slide_by_slug(state: DeckState, slug: str) -> Optional[SlideRecord]:
    """
    Return the slide record for the given slug, or None if absent or discarded.
    """
    ...


def increment_export_count(state: DeckState, folder: str) -> None:
    """
    Find the presentation record matching folder and increment export_count in-place.
    Does NOT write the state; caller must call write_deck_state.
    Raises KeyError if no record with the given folder exists.
    """
    ...


def increment_script_count(state: DeckState, folder: str) -> None:
    """
    Find the presentation record matching folder and increment script_count in-place.
    Does NOT write the state; caller must call write_deck_state.
    Raises KeyError if no record with the given folder exists.
    """
    ...


def increment_handout_count(state: DeckState, folder: str) -> None:
    """
    Find the presentation record matching folder and increment handout_count in-place.
    Does NOT write the state; caller must call write_deck_state.
    Raises KeyError if no record with the given folder exists.
    """
    ...


def read_debrief_state(project_root: Path) -> DebriefState:
    """
    Read and validate debrief_state.json from project_root.

    Performs SHA-256 hash verification. If hash mismatches but content is
    structurally valid, recomputes and updates the hash, emits warning to stderr.
    If content is malformed or any field holds an invalid value, raises
    StateCorruptError.
    """
    ...


def write_debrief_state(project_root: Path, state: DebriefState) -> None:
    """
    Atomically write debrief_state.json with fcntl.flock on .debrief/state.lock.

    Protocol:
    1. Acquire exclusive lock on .debrief/state.lock.
    2. Recompute state_hash before serializing.
    3. Write to debrief_state.json.tmp.
    4. fsync the tmp file.
    5. os.rename to debrief_state.json.
    6. Release lock.
    """
    ...


def compute_state_hash(state_dict: dict[str, Any]) -> str:
    """
    Compute SHA-256 over the canonical JSON serialization of all content fields
    in debrief_state.json, excluding the 'state_hash' key itself.
    Returns the hex digest string.
    """
    ...


def validate_debrief_state(state_dict: dict[str, Any]) -> None:
    """
    Validate that all required fields are present, enum fields hold only allowed
    values, and numeric counters are non-negative.

    Raises StateCorruptError with a descriptive message on the first violation.

    Validated enums:
      phase: {"discovery", "style", "production", "finalization", "complete"}
      active_agent: {"consultant", "slide_maker", "stylist", "qa", "none"}
        Note: "none" is required during production/diagnostic sub_phase per
        Section 17.5 and P-BP-3. "qa" corresponds to the visual-qa agent;
        routing/state use underscored identifiers while agent filenames use hyphens.
      style_import_mode: {"baseline", "inspiration", None}
      reference_modality: {"pptx", "pdf", "html", "html_dir", None}
    """
    ...


SUB_PHASE_VALUES: frozenset[str] = frozenset({
    "discovery/greeting",
    "discovery/dialog",
    "discovery/brief_review",
    "discovery/paper_analysis",
    "discovery/figure_selection",
    "discovery/style_analysis",
    "style/style_dialog",
    "style/style_review",
    "style/style_lock",
    "production/group_planning",
    "production/red_green",
    "production/diagnostic",
    "production/oscillation_review",
    "production/slide_review",
    "production/group_review",
    "production/more_slides",
    "production/deck_ending",
    "finalization/export_options",
    "finalization/backup_decision",
    "finalization/export_confirm",
    "finalization/reviewing_for_export",
    "finalization/exporting",
    "finalization/post_export",
    "complete",
})
"""All valid sub_phase string values per Section 14.17. Used by validate_debrief_state."""


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """
    Write data as JSON to path atomically: write to path.parent / (path.name + '.tmp'),
    fsync, then os.rename to path.
    Used by both state modules and Phase 2 draft-file writers.
    """
    ...


def sanitize_identifier(text: str, max_length: int = 40) -> str:
    """
    Apply the Debrief Identifier Sanitization Algorithm (Section 24.10.1).

    Steps applied in order:
    1. Convert to lowercase.
    2. Replace spaces and hyphens with underscores.
    3. Remove all characters not matching [a-z0-9_].
    4. Collapse consecutive underscores to a single underscore.
    5. Strip leading and trailing underscores.
    6. Truncate to max_length characters.
    7. If the result is empty, return 'untitled'.

    Callers are responsible for any additional validation (e.g., ensuring
    the result starts with a letter for slug contexts).

    Usage sites per Section 24.10.1:
      - Presentation folder naming:  max_length=40  (prepend YYYY_MM_DD_)
      - Paper slug derivation:       max_length=50  (REQ-CONSULT-17)
      - Snapshot label sanitization: max_length=50  (REQ-SAVE-3)
    """
    ...
```

### Tier 3 -- Behavioral Contracts

**BC-2.1 json_repair safety net.** `read_deck_state` and `read_debrief_state` must import `json_repair` at entry. If `json_repair` is unavailable (importlib.util.find_spec returns None), both functions must exit with code 2 and the standardized Section 9.3.1 env-corruption error on stderr.

**BC-2.2 Atomic write protocol.** `write_deck_state`, `write_debrief_state`, and `atomic_write_json` must write to a `.tmp` sibling file, call `os.fsync()` on the file descriptor, then call `os.rename()`. A process kill between write and rename must leave the original state file intact. The `.tmp` file must not persist after a successful rename.

**BC-2.3 Lock acquisition for debrief_state.** `write_debrief_state` must acquire an exclusive `fcntl.flock` on `.debrief/state.lock` before the read-modify-write sequence and release it after the rename completes. Lock must be released in a `finally` block to prevent deadlock on exception.

**BC-2.4 Hash recompute on write.** `write_debrief_state` must call `compute_state_hash` on the state dict (excluding `state_hash`) immediately before serializing, and store the resulting hex digest in `state_hash` before writing. The written file must always have a valid hash.

**BC-2.5 Hash mismatch recovery.** When `read_debrief_state` finds a hash mismatch, it must first call `validate_debrief_state`. If validation passes, it recomputes the hash, updates the in-memory dict, and emits a warning to stderr: `WARNING: debrief_state.json hash mismatch — recomputed. File may have been externally modified.` It must NOT raise StateCorruptError in this case. If validation fails, it must raise StateCorruptError.

**BC-2.6 get_approved_slides ordering.** The returned list must preserve the order of entries in `state.slides`. The `backup` filter, when provided, applies after ordering. No sort is applied.

**BC-2.7 get_slide_by_slug discarded.** A slide with `status == "discarded"` must return None from `get_slide_by_slug`, even if the slug exists.

**BC-2.8 increment_* does not write.** All three increment functions modify the state in-place and return None. They do not call `write_deck_state`. The caller is responsible for the subsequent write. Calling increment without a subsequent write is a bug in the caller, not in this library.

**BC-2.9 StateCorruptError propagation.** No function in this library catches `StateCorruptError` and re-raises it as a different exception. All callers receive the original exception with its descriptive message.

**BC-2.10 canonical JSON serialization.** `compute_state_hash` must serialize the dict with `json.dumps(sorted_keys=True, separators=(',', ':'))` to ensure determinism across Python versions and implementations. The hash input must not include any trailing whitespace or newlines.

**BC-2.11 phase enum enforcement.** `validate_debrief_state` must raise `StateCorruptError` if `phase` is not in `{"discovery", "style", "production", "finalization", "complete"}`. Similarly for all other enum fields.

**BC-2.12 SlideRecord field completeness.** Every `SlideRecord` written to `deck_state.json` must include ALL fields from Section 17.2: `slug`, `title`, `status`, `content_summary`, `visual_approach`, `design_choices`, `forks_not_taken`, `user_recommendations`, `qa_passed`, `accepted_violations`, `last_modified`, `group_id`, `backup`, `user_assets`, `has_math`. Fields `qa_passed` and `has_math` default to `false`; `user_assets` defaults to `[]`; `accepted_violations` defaults to `[]`; `last_modified` is set to the ISO 8601 timestamp of the most recent write.

**BC-2.13 DebriefState field completeness.** Every `debrief_state.json` write must include ALL fields from Section 17.5: `phase`, `sub_phase`, `active_agent`, `archetype`, `current_group_id`, `current_slide_slug`, `pending_gate`, `last_gate_response`, `red_green_iteration`, `red_green_started_at`, `group_slide_index`, `group_slide_count`, `backup_mode`, `completed_groups`, `pre_view_state`, `view_deferred`, `closing_slide_pending`, `group_revise_slug`, `style_import_mode`, `reference_provided`, `reference_modality`, `papers_provided`, `selected_figures`, `session_started_at`, `state_hash`. No field may be omitted.

**BC-2.14 active_agent enum.** `validate_debrief_state` must raise `StateCorruptError` if `active_agent` is not in `{"consultant", "slide_maker", "stylist", "qa", "none"}` per Section 17.5. The value `"none"` is required during `production/diagnostic` sub_phase (the bug-diagnostic agent is not a conversational agent; the user does not interact with it directly).

**BC-2.15 sub_phase enum enforcement.** `validate_debrief_state` must raise `StateCorruptError` if `sub_phase` is not in the set of 24 valid values enumerated in the `SUB_PHASE_VALUES` constant: `discovery/greeting`, `discovery/dialog`, `discovery/brief_review`, `discovery/paper_analysis`, `discovery/figure_selection`, `discovery/style_analysis`, `style/style_dialog`, `style/style_review`, `style/style_lock`, `production/group_planning`, `production/red_green`, `production/diagnostic`, `production/oscillation_review`, `production/slide_review`, `production/group_review`, `production/more_slides`, `production/deck_ending`, `finalization/export_options`, `finalization/backup_decision`, `finalization/export_confirm`, `finalization/reviewing_for_export`, `finalization/exporting`, `finalization/post_export`, `complete`. **BUG-AUDIT-60 / REQ-STATE-ENUM-2:** `write_debrief_state` MUST also invoke `validate_debrief_state` on the serialized dict before `atomic_write_json`. A failed validation MUST raise `StateCorruptError` and leave the on-disk file unchanged; the lock MUST be released in a `finally` block regardless of outcome.

**BC-2.15a cli_update_state phase/sub_phase coupling (BUG-AUDIT-60 / REQ-STATE-ENUM-3).** `cli_update_state` MUST derive `phase` from the `sub_phase` prefix (the substring before the first `/`, or the whole value when it has no `/` — e.g., `complete`) when the user passes `sub_phase` without an explicit `phase`. When both are passed in the same invocation, they MUST be consistent: `phase == sub_phase.split('/')[0]` (for values containing `/`) or `phase == sub_phase` (for values without `/`). Inconsistent pairs MUST cause the command to exit 1 with a message naming the conflict. Neither update writes to disk if the pair is inconsistent.

**BC-2.15b consultant.md / SUB_PHASE_VALUES equality (BUG-AUDIT-60 / REQ-STATE-ENUM-1).** The consultant-facing enumeration in `agents/consultant.md` §"Valid sub_phase Values" MUST be set-equal to `SUB_PHASE_VALUES` in `debrief_state.py`. A regression test MUST parse both (the consultant card's comma-delimited backticked list and the Python frozenset) and assert exact set equality. Any drift is a CRITICAL regression.

**BC-2.16 sanitize_identifier algorithm compliance.** `sanitize_identifier` must implement the 7-step Debrief Identifier Sanitization Algorithm exactly as specified in Section 24.10.1, in order: (1) lowercase, (2) spaces/hyphens → underscores, (3) remove non-`[a-z0-9_]`, (4) collapse consecutive underscores, (5) strip leading/trailing underscores, (6) truncate to `max_length` (truncate anywhere — no word-boundary alignment), (7) empty result → `"untitled"`. **Note on step ordering:** Step 7 (empty-check) is evaluated on the result of step 5, BEFORE step 6 (truncation), per Section 24.10.1 ("If the result is empty after steps 1–5"). If the result after step 5 is non-empty, step 6 truncates it; if empty, step 7 returns `"untitled"` immediately without truncation. Given the same inputs, `sanitize_identifier` must always return the same output. No randomness. Callers must not pass already-sanitized strings to avoid double-sanitization.

**BC-2.17 `.debrief/dialog.jsonl` schema (BUG-AUDIT-78 / REQ-MEMORY-DIALOG-1).** `.debrief/dialog.jsonl` is the append-only raw dialog archive. Each line is a JSON object:

```json
{"turn": 42,
 "timestamp": "2026-04-29T14:32:17Z",
 "role": "user",
 "responding_agent": "consultant",
 "content": "Alice is the engineer in Rome.",
 "metadata": {"phase": "discovery", "sub_phase": "discovery/dialog"}}
```

Required fields: `turn` (int, monotonic across the project's lifetime), `timestamp` (ISO 8601 UTC with `Z` suffix), `role` (one of `"user"` | `"consultant"`), `responding_agent` (string identifying which agent the user was addressing — `"consultant"` | `"stylist"` | `"slide-maker"` | `"visual-qa"` | `"bug-diagnostic"`), `content` (string, the verbatim turn body), `metadata` (object containing at least `phase` and `sub_phase`; MAY contain additional implementation-defined fields).

Capture rule (REQ-MEMORY-DIALOG-1): every USER turn is archived regardless of `responding_agent`; only CONSULTANT replies are archived (subagent replies are excluded). Marker entries with `event` keys (`"session_start"`, `"compaction"`) MAY appear interleaved but MUST NOT truncate the archive. The `dialog.jsonl` file is append-only: no edits, no deletions, no truncation across project lifetime.

Watermark file `.debrief/rewrite_metadata.json` MUST track `last_archived_turn` (int) so dialog-append operations are idempotent against the same Claude Code transcript. The watermark file's full schema is defined by BC-3.18.

**BC-2.18 `output/timeline.jsonl` schema (BUG-AUDIT-78 / REQ-MEMORY-TIMELINE-1).** `output/timeline.jsonl` is the append-only typed-event stream. Each line is a JSON object:

```json
{"event": "slide_approved",
 "timestamp": "2026-04-29T14:42:01Z",
 "turn": 73,
 "payload": {"slug": "intro", "group_id": "g1"}}
```

Required fields: `event` (string from a closed extensible enumeration), `timestamp` (ISO 8601 UTC), `payload` (object whose schema is event-type-specific). Optional: `turn` (int, the dialog turn at which the event was captured; absent for system-emitted events that have no associated turn).

Initial event-type enumeration: `briefing_complete`, `style_locked`, `slide_approved`, `slide_discarded`, `export_done`, `handout_done`, `script_done`, `paper_attached`, `figure_selected`, `backup_session_started`. Cycle 2 adds new event types as features ship; the enumeration is extensible without breaking the contract — readers MUST tolerate unknown event types (skip-and-continue).

Multiple emitters write to this file concurrently — the state machine, export/handout/script/visual-qa modules, the consultant's action-capture path. Each write MUST be a single-line atomic JSON append (open-and-append-with-fsync), so concurrent writers do not corrupt the file.

**BC-2.20 `update_slide` CLI (BUG-AUDIT-97 / BC-5.17).** `debrief_state.py` MUST register an `update_slide` argparse subcommand alongside `update` and `append_ledger`. The subcommand is the canonical CLI write path for `deck_state.json:slides[]` per BC-5.17 / REQ-CONSULT-SLIDE-WT-1; the consultant invokes it after every GREEN QA decision. The CLI MUST: (1) require `--slug <slug>` and accept `--project-root <path>` (defaulting to cwd); (2) accept these optional flags, each mapping directly to a `SlideRecord` field — `--title <text>`, `--status {draft|approved|needs_revision|discarded}`, `--backup {true|false}`, `--content-summary <text>`, `--visual-approach <text>`, `--design-choices <text>`, `--forks-not-taken <text>`, `--user-recommendations <text>`, `--qa-passed {true|false}`, `--accepted-violations <json>` (JSON-encoded list of `{"invariant": str, "reason": str}` dicts), `--group-id <text>`, `--user-assets <json>` (JSON-encoded list of strings), `--has-math {true|false}`; (3) read `deck_state.json` via `read_deck_state`, locate the slide whose `slug` matches `--slug`, partial-update only the fields the user passed (others remain) for an existing record, OR create a new `SlideRecord` from the passed fields plus dataclass defaults if no matching slug exists; (4) require `--title` for create-path invocations and reject with stderr error + exit 1 if missing; (5) validate `--status` is one of `{"draft", "approved", "needs_revision", "discarded"}` per the dataclass docstring at `debrief_state.py:59` and reject with stderr error + exit 1 on invalid status; (6) coerce booleans via the same `value.lower() in ("true","1","yes")` rule that `cli_update_state` uses (BUG-AUDIT-60); (7) parse `--accepted-violations` and `--user-assets` as JSON via `json.loads` and reject with stderr error + exit 1 on JSON parse failure or wrong shape; (8) set `last_modified` to the current UTC ISO 8601 timestamp before writing in both update and create paths; (9) write atomically via `write_deck_state`; (10) print `Updated deck_state.json: slide '<slug>'` to stderr on success and exit 0. The CLI MUST NOT touch any field the user did not explicitly pass on update — this preserves `cli_update_state`-style merge semantics. A regression test (`tests/regressions/test_bug_audit_97_update_slide_cli.py`) MUST exercise: subcommand registration, create with required args, partial update, status validation, JSON parsing of list-shaped fields, last_modified auto-update, and atomic write semantics. Pre-fix all assertions fail because the subcommand was never implemented.

---

## Unit 3: Launcher

### Tier 2 — Signatures

```python
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from typing import Optional


def preflight(plugin_root: Path) -> None:
    """
    Python half of the pre-flight checks, called via:
        python -m debrief.launcher preflight

    Runs ONLY verify_vendor_hashes(). Package-install and Chromium-install
    markers are checked by the bash wrapper inline after conda activate,
    NOT by this Python function. On hash mismatch, prints the error to
    stderr with file name, expected hash, actual hash, and the verbatim
    plugin-reinstall recovery instruction from Section 24.27, then exits
    with code 1.
    """
    ...


def verify_vendor_hashes(plugin_root: Path) -> None:
    """
    Read plugin_root/assets/vendor/VERSIONS.md, parse each SHA-256 entry,
    and compute the actual SHA-256 hash of each listed file.

    Raises SystemExit(1) on any mismatch, with the full Section 24.27 error
    message on stderr (per Section 24.34 stream convention).
    """
    ...


def new(project_root: Path, archetype: Optional[str] = None) -> None:
    """
    Initialize a new Debrief project in project_root.

    Steps:
    1. Verify project_root is empty or contains only CLAUDE.md.
    2. Present archetype selection prompt if archetype is None; otherwise skip.
    3. Create all required subdirectories per Section 3.
    4. Copy vendor assets from plugin_root/assets/vendor/ to project_root/assets/vendor/.
    5. Write initial deck_state.json via write_deck_state().
    6. Write initial debrief_state.json via write_debrief_state().
    7. Render project_claude.md template into project_root/CLAUDE.md.

    Exits with code 1 if project_root contains unexpected files.
    Exits with code 1 on second invalid archetype input.
    """
    ...


def select_archetype(archetypes_path: Path) -> str:
    """
    Present the archetype selection prompt, read stdin, validate input.
    Returns the selected archetype value string (e.g. 'lab_meeting').

    Accepts a 1-based number or an archetype name (case-insensitive).
    On first invalid input: re-prompts once.
    On second invalid input: prints error and calls sys.exit(1).
    """
    ...


def render_project_claude_md(
    template_path: Path,
    project_root: Path,
    project_name: str,
) -> None:
    """
    Read the CLAUDE.md template from template_path, substitute {project_name}
    with project_name, and write the result atomically to project_root/CLAUDE.md.
    """
    ...


def create_project_structure(project_root: Path) -> None:
    """
    Create all required project subdirectories per Section 3:
      assets/images/, assets/fonts/, assets/vendor/, assets/reference/slides/,
      assets/reference/papers/, assets/math/, .debrief/briefs/,
      .debrief/snapshots/, slides/, output/screenshots/.
    Uses exist_ok=True for all mkdir calls.
    """
    ...
```

### Tier 3 -- Behavioral Contracts

**BC-3.1 Non-empty project rejection.** If `project_root` contains any file or directory other than `CLAUDE.md`, `new()` must print an error message and exit with code 1 without creating any files.

**BC-3.2 Archetype prompt format.** The prompt presented by `select_archetype` must exactly match the eight-option format in REQ-INIT-7, including the exact option text and numbered list. The prompt must print to stdout. Input is read from stdin.

**BC-3.3 Archetype re-prompt once.** On invalid input, the function re-prompts exactly once. On the second invalid input, it prints `Invalid selection. Please run 'debrief new' again and enter a number 1-8 or an archetype name.` and exits with code 1. It does not loop indefinitely.

**BC-3.4 Initial deck_state values.** `new()` must write `deck_state.json` with `style_locked: false`, `slides: []`, `presentations: []`, `closing_slide: null`, `created_at` as an ISO 8601 timestamp, `project_name` as the directory basename, and `archetype` matching the selected value.

**BC-3.5 Initial debrief_state values.** `new()` must write `debrief_state.json` with `phase: "discovery"`, `sub_phase: "greeting"`, `active_agent: "consultant"`, `red_green_iteration: 0`, `red_green_started_at: null`, `group_slide_index: 0`, `group_slide_count: 0`, `completed_groups: []`, `last_gate_response: null`, `state_hash` computed by `compute_state_hash`, `backup_mode: false`, `closing_slide_pending: false`, `view_deferred: false`, `reference_provided: false`, `papers_provided: false`, and all other nullable fields set to `null`.

**BC-3.6 CLAUDE.md template rendering.** `render_project_claude_md` must substitute every occurrence of `{project_name}` with the directory basename. The write must be atomic (write-to-tmp then rename). No other placeholders are substituted. Unrecognized `{...}` tokens are left unchanged.

**BC-3.6a CLAUDE.md template content.** The source template at `${CLAUDE_PLUGIN_ROOT}/templates/project_claude.md` MUST contain a top-level `## On Session Start` section that instructs the consultant agent to read `debrief_state.json` and `deck_state.json` on session entry and dispatch based on the current `sub_phase`. The section MUST reference: (a) the `debrief_state.json` file and its `sub_phase` field, (b) the `deck_state.json` file and its `archetype` field, (c) the dispatch logic for `sub_phase == "discovery/greeting"` which requires the consultant to emit the REQ-CONSULT-1 greeting with archetype context pre-loaded from `deck_state.json` and `${CLAUDE_PLUGIN_ROOT}/archetypes.json`, and (d) the instruction that a first user message of "hi" / "start" / "begin" / short greeting MUST be interpreted as a dispatch request, not as a request for a generic greeting. Rationale: Claude Code agents do not auto-emit messages before user input; the consultant's greeting fires on the first user turn, triggered by the orchestration instruction read from this CLAUDE.md section. Without this section, the consultant is loaded but silent, and the REQ-CONSULT-1 greeting never fires. See BUG-AUDIT-11 in the spec Bug Catalog.

**BC-3.7 Vendor copy.** `new()` must copy the full contents of `${CLAUDE_PLUGIN_ROOT}/assets/vendor/` into `project_root/assets/vendor/`. The copy preserves file contents exactly. If the vendor directory is empty or missing, the function exits with code 1.

**BC-3.8 verify_vendor_hashes failure format.** On hash mismatch, the error message to **stderr** (per Section 24.34 stream convention: all human-readable messages go to stderr) must include: the filename, the expected SHA-256 hash (from VERSIONS.md), the actual SHA-256 hash, and the verbatim recovery instruction from Section 24.27: `Plugin assets appear corrupted. Reinstall the Debrief plugin via Claude Code's plugin management (e.g., /plugin reinstall debrief or equivalent). If reinstall fails, delete ${CLAUDE_PLUGIN_ROOT} and reinstall from source.`

**BC-3.9 idempotent mkdir.** `create_project_structure` must use `exist_ok=True` for all `os.makedirs` calls. Running it twice must not raise an exception. Per BUG-AUDIT-15, the `_REQUIRED_DIRS` list MUST contain all 15 canonical directories from spec §3: `.debrief`, `.debrief/briefs`, `.debrief/draft`, `.debrief/draft/preview_slides`, `.debrief/draft/preview_images`, `.debrief/snapshots`, `assets/images`, `assets/fonts`, `assets/vendor`, `assets/math`, `assets/reference/slides`, `assets/reference/papers`, `slides`, `output`, `output/screenshots`. Empty directories are valid project state per spec §3 directory policy paragraph; the canonical tree is "always present" regardless of whether any agent has written content into it.

**BC-3.10 Resume behavior.** The `bin/debrief` bash wrapper, when invoked without `new`, checks for `deck_state.json` in the current directory. If absent, it prints `No Debrief project found in this directory. Run 'debrief new' to create one.` and exits with code 1. If present, it launches Claude Code without calling `new()`.

**BC-3.11 Launcher json_repair entry check.** `debrief.launcher` must check `importlib.util.find_spec('json_repair')` at entry of both `main_new()` and `preflight()` per Section 24.35 Category 4.3 (which lists `debrief.launcher — json_repair`). This is a direct entry-level check in addition to the transitive check through Unit 2's library functions. If unavailable, exit with code 2 and the standardized Section 9.3.1 env-corruption error. The check MUST be the first executable statement inside each function body — not merely "somewhere early" — so that a corrupt env fails fast before `sys.argv` parsing, plugin-root resolution, or any subcommand dispatch. Concretely, in `main_new()` the call `_require_json_repair()` (or an equivalent direct `importlib.util.find_spec` check) must precede the `CLAUDE_PLUGIN_ROOT` lookup and the `sys.argv[1]` read. See BUG-AUDIT-2 for the latent violation this clarification closes.

**BC-3.12 Launcher module entry point.** `debrief.launcher` MUST define a module-level callable `main_new()` that serves as the `python -m debrief.launcher` entry point, and MUST end with an `if __name__ == "__main__":` guard that calls `main_new()`. `main_new()` MUST implement a four-arm dispatch on `sys.argv[1]` (BUG-AUDIT-8 added the fourth arm to the original three-arm dispatch from BUG-AUDIT-2): (a) the string `"preflight"` calls `preflight(plugin_root)` per spec §24.4 step 8; (b) the string `"new"` calls `new(project_root=project_root)` per spec §24.4 step 9 (the `new` arm of the `bin/debrief` subcommand dispatch); (c) the string `"ensure_settings"` calls `ensure_project_settings(project_root, plugin_root)` per BC-3.13 (used by `bin/debrief`'s bare-invocation arm to self-heal `.claude/settings.json`); (d) any other value (including the empty string) prints `Unknown subcommand: <value>` and `Usage: python -m debrief.launcher [new|preflight|ensure_settings] [project_root]` to stderr and exits with code 1. `plugin_root` is resolved from the `CLAUDE_PLUGIN_ROOT` environment variable with a best-effort fallback to `Path(__file__).parent.parent.parent`. `project_root` is resolved from `sys.argv[2]` with a fallback to `Path.cwd()`. The `main_new()` callable, the `__main__` guard, and all four dispatch arms are load-bearing: BUG-AUDIT-1's `bin/debrief` §24.4 steps 8 and 9 invoke `python -m debrief.launcher preflight`, `python -m debrief.launcher new`, and (per BUG-AUDIT-8) `python -m debrief.launcher ensure_settings` respectively; any of those invocations fails with `AttributeError` or silent no-op if the corresponding arm is missing. See BUG-AUDIT-2 (initial dispatch wiring) and BUG-AUDIT-8 (ensure_settings arm).

**BC-3.13 `ensure_project_settings` contract.** `debrief.launcher` MUST provide a public function `ensure_project_settings(project_root: Path, plugin_root: Path) -> None`. The function ensures the project at `project_root` has a `.claude/settings.json` file that makes Claude Code load the debrief plugin via the local marketplace and namespace its skills as `/debrief:*`. Specifically, it MUST: (1) create `project_root/.claude/` if absent (`mkdir(parents=True, exist_ok=True)`); (2) read existing `project_root/.claude/settings.json` if present, parse as JSON, default to an empty dict on `JSONDecodeError` or non-dict content (corrupt-JSON recovery — pragmatic, do not block bin/debrief over a developer mistake); (3) set `data["extraKnownMarketplaces"]["debrief"] = {"source": {"source": "directory", "path": str(plugin_root.parent.resolve())}}` — the path field is the absolute, symlink-resolved path of `plugin_root.parent`, the directory containing `.claude-plugin/marketplace.json`; (4) set `data["enabledPlugins"]["debrief@debrief"] = True`; (5) write the result atomically via `_atomic_write_json`. The function MUST be idempotent (re-running with the same inputs produces a byte-equal file). The function MUST preserve any unrelated top-level keys already present in the settings file — only `extraKnownMarketplaces.debrief` and `enabledPlugins["debrief@debrief"]` are touched. The function MUST self-heal a stale marketplace path: re-running with a different `plugin_root` overwrites the path field with the new value. `ensure_project_settings` MUST be called from two places: (a) at the end of `new()`, after `render_project_claude_md`, so newly created projects ship with a valid settings file; (b) historically from the `ensure_settings` arm of `main_new()` directly, but per BC-3.14 / BUG-AUDIT-15 the bare-invocation re-entry now goes through the `ensure_project` orchestrator which composes `create_project_structure` with `ensure_project_settings` so the canonical tree is also restored. See BUG-AUDIT-8.

**BC-3.14 `ensure_project` orchestrator.** `debrief.launcher` MUST provide a public function `ensure_project(project_root: Path, plugin_root: Path) -> None`. The function is the canonical re-entry hook for the `debrief` (no-args) bare-invocation arm in `bin/debrief`. It composes two existing helpers in a fixed order: (1) `create_project_structure(project_root)` — re-scaffolds the canonical project directory tree from spec §3 / `_REQUIRED_DIRS`; (2) `ensure_project_settings(project_root, plugin_root)` — self-heals `.claude/settings.json` per BC-3.13. The ordering is load-bearing: directories first, then settings. The function MUST be idempotent (re-running produces no observable change beyond what would happen by running each helper twice). The new `ensure_project` arm in `main_new()` invokes this function (extending BC-3.12's dispatch table from four arms to five — `preflight`, `new`, `ensure_project`, `ensure_settings`, fallback). `bin/debrief`'s bare-invocation arm MUST call `python -m debrief.launcher ensure_project "$(pwd)"` (NOT `ensure_settings`) so the canonical directory tree is restored on every entry, closing the BUG-AUDIT-15 re-entry gap where cleanup operations (BC-4.6 style-lock, `skill_reset`, `skill_quit`) removed canonical directories that the next session needed. The legacy `ensure_settings` subcommand and `ensure_project_settings` function are retained for backward compatibility but are strictly subsumed by `ensure_project`. See BUG-AUDIT-15.

**BC-3.16 `debrief doctor` subcommand (BUG-AUDIT-75 / REQ-DOCTOR-1).** `src/unit_3/launcher.py` MUST provide three public helpers and MUST wire a `doctor` subcommand into `main_new()`'s dispatch table:

- `@dataclass DriftReport(drift_detected: bool, orphan_files: list[str], orphan_records: list[str], matched_count: int)` — structured result shape.
- `detect_slide_state_drift(project_root: Path) -> DriftReport` — pure. Lists `slides/*.html` stems via `(project_root / "slides").iterdir()` filtering on `is_file() and suffix == ".html"`, compares the set against the `slug` fields of `deck_state.slides` as read through `debrief_state.read_deck_state` (or a direct `json.load` tolerant of missing / malformed state — the doctor MUST NOT fail on a malformed state file; it treats it as zero slides and proceeds to report filesystem orphans). Returns the populated report. Missing `slides/` directory is treated as zero files. Order within each orphan list is stable (sorted ascending).
- `reconstruct_slide_records_from_files(project_root: Path, slugs: list[str]) -> int` — appends a minimal `SlideRecord` per slug not already present in `deck_state.slides`, via `write_deck_state`. Field defaults: `status="draft"`, `title=slug`, `backup=False`, `content_summary=None`, `visual_approach=None`, `design_choices=None`, `forks_not_taken=None`, `user_recommendations=None`, `qa_passed=False`, `accepted_violations=[]`, `last_modified=<current UTC ISO-8601>`, `group_id=None`, `user_assets=[]`, `has_math=False`. Idempotent: slugs already present are skipped; returns the count actually written. The write is atomic (single `write_deck_state` call after all records are appended in-memory).
- `main_doctor(project_root: Path, *, reconstruct: bool = False) -> None` — CLI orchestrator. Calls `detect_slide_state_drift`; when `reconstruct=True` AND `orphan_files` is non-empty, invokes `reconstruct_slide_records_from_files` and re-scans before printing the final report. Prints a pretty-printed JSON object to stdout with keys `drift_detected`, `orphan_files`, `orphan_records`, `matched_count`. Prints a human-readable summary to stderr naming the orphan counts and (in report-only mode) directing the user at `--reconstruct`. Exit codes: 0 if `not drift_detected OR reconstruction ran successfully AND the re-scan shows no orphan_files`; 1 if `drift_detected AND not reconstruct` (the report-only signal scripts key off); 2 if reconstruction raised.

The dispatch branch `elif subcommand == "doctor":` in `main_new()` parses `--project-root` (type=Path, default=Path.cwd()) and `--reconstruct` (store_true) from `sys.argv[2:]` via a local `argparse.ArgumentParser`. The subcommand MUST appear in the usage-line string printed by the catch-all `else` branch so users discover it when they type an unknown subcommand.

Destructive remediation (deleting orphan HTML files or orphan state records) is OUT OF SCOPE for this contract — those decisions require explicit user intent and are outside the mechanical drift detector's role. See REQ-DOCTOR-1 and BUG-AUDIT-75.

**BC-3.18 `rewrite_brief` subcommand (BUG-AUDIT-78 / REQ-MEMORY-REWRITE-1..4).** `src/unit_3/launcher.py` MUST provide a `rewrite_brief` subcommand wired into `main_new()`'s dispatch table. The subcommand:

- Parses `--project-root` (Path, default `Path.cwd()`).
- Optionally accepts a transcript path on stdin (PreCompact hook passes `transcript_path` as a JSON field on stdin); when present, the subcommand uses it to append new dialog turns to `.debrief/dialog.jsonl` per the REQ-MEMORY-DIALOG-1 capture rule.
- Reads `agents/rewriter.md` (the agent-card per BC-5.19), extracts the model declaration from the YAML frontmatter and the system prompt from the body, calls the Anthropic API with that prompt as `system` and the inputs (dialog archive + event timeline + bootstrap-brief if applicable per REQ-MEMORY-REWRITE-3) as the user message.
- On success: validates the response (canonical brief sections per REQ-CONSULT-DECK-BRIEF-1, roster YAML parses with `name`/`role` keys per entry), writes `deck_brief.md.tmp` + `output/audience.yaml.tmp`, atomically renames both, updates `.debrief/rewrite_metadata.json` (schema: `last_rewrite_timestamp`, `last_archived_turn`, `agent_version`, `model`, `bootstrap_complete`).
- On failure: appends a JSON entry to `.debrief/rewrite_errors.jsonl` (schema: `timestamp`, `trigger` ∈ `"PreCompact" | "/debrief:quit" | "/debrief:refresh-brief"`, `error_class`, `error_message`, optional `transcript_path`) and **exits 0**. The hook MUST NOT block compaction on rewrite failure (REQ-MEMORY-REWRITE-4). When the failure is specifically `ModuleNotFoundError` for the `anthropic` SDK (BUG-AUDIT-93), the launcher MUST additionally emit a single actionable line to stderr — `"rewrite_brief: anthropic SDK not installed in this env; install with 'pip install anthropic>=0.40' and retry. If the env was created by bin/debrief, run 'debrief --rebuild-env'."` — so the user knows the brief did not synthesize. **BUG-AUDIT-98 amendment:** when the failure is an Anthropic auth error — either `TypeError` whose stringified message contains `"could not resolve authentication"` (case-insensitive; the SDK constructor failure when no credential is in the environment) OR an exception whose class name is `"AuthenticationError"` (the SDK's `anthropic.AuthenticationError` raised on HTTP 401) — the launcher MUST also emit a single actionable line to stderr: `"rewrite_brief: anthropic API authentication failed; set ANTHROPIC_API_KEY in the environment and retry. Details logged to .debrief/rewrite_errors.jsonl."`. Exit code remains 0 unconditionally for the rewriter; PreCompact must never block. All other exception types (network errors, rate-limit errors, validation failures) keep the silent-exit-0 behavior — only the two well-known categories (missing module, auth) get user-visible stderr.
- The atomic dual write MUST not produce partial state: if the second rename fails after the first succeeded, the implementation MUST roll back the first rename. (Implementation hint: rename to `.tmp.staged` first, run a final paired rename only after both temp files exist and validate.)

The `rewrite_brief` subcommand MUST appear in the usage-line string printed by the catch-all `else` branch in `main_new()` so users discover it when they type an unknown subcommand. Cycle 2 implementation lands in Phase 2 of RFC §13.

**BC-3.19 `recall` subcommand (BUG-AUDIT-78 / REQ-MEMORY-RECALL-1).** `src/unit_3/launcher.py` MUST provide a `recall` subcommand wired into `main_new()`'s dispatch table. The subcommand:

- Parses `<query>` (positional, required, string) and `--project-root` (Path, default `Path.cwd()`).
- Greps `.debrief/dialog.jsonl` and `output/timeline.jsonl` for the query (case-insensitive literal-string match against the `content` field of dialog entries and against any string-valued field of timeline entries).
- Returns matched entries with ±2 entries of context, source-labeled (each output record carries `"source": "dialog" | "timeline"`).
- Output format: pretty-printed table when `sys.stdout.isatty()`; JSON list otherwise. JSON shape: `[{"source": "dialog" | "timeline", "match": <entry>, "context_before": [<entry>...], "context_after": [<entry>...]}, ...]`.
- Exit codes: 0 when matches found OR no matches but archives exist (no-match is not an error); 1 when a project file is missing or malformed; 3 on usage error.
- v1 implementation uses Python `in` substring match on the relevant fields. A future full-text-search index (e.g., `tantivy`) MAY be added without changing the CLI surface — only the indexer would change.

The `recall` subcommand MUST appear in the usage-line string printed by the catch-all `else` branch in `main_new()`. Cycle 2 implementation lands in Phase 1 of RFC §13.

**BC-3.20 `script_writer` subcommand (BUG-AUDIT-84 / REQ-SCRIPT-WRITER-1..4, amended by BUG-AUDIT-93).** `src/unit_3/launcher.py` MUST provide a `script_writer` subcommand wired into `main_new()`'s dispatch table. Mirrors BC-3.18's `rewrite_brief` shape:

- Parses `--project-root` (Path, default `Path.cwd()`) and `--trigger` (one of `/debrief:script`, `deck-complete-finalization`, `/debrief:handout-cascade`, default `/debrief:script`).
- The trigger value distinguishes direct CLI invocation (`/debrief:script`) from cascades (`deck-complete-finalization` from BC-5.21's 4-step finalization, `/debrief:handout-cascade` from BC-11.16). Per BUG-AUDIT-93, when the API call fails with `ModuleNotFoundError` for the `anthropic` SDK, the launcher MUST: (a) emit a single actionable line to stderr — `"/debrief:script: anthropic SDK not installed in this env; install with 'pip install anthropic>=0.40' and retry. If the env was created by bin/debrief, run 'debrief --rebuild-env'."`; (b) log to `.debrief/script_errors.jsonl` per the existing schema; (c) exit 2 if `trigger == "/debrief:script"` (direct CLI — the user typed the command and expects a deliverable; non-zero exit signals failure visibly), otherwise exit 0 (cascade — REQ-SCRIPT-WRITER-2's exit-0-always rule still applies because the next step in the consultant's finalization sequence must continue). **BUG-AUDIT-98 amendment:** when the failure is an Anthropic auth error — either `TypeError` whose stringified message contains `"could not resolve authentication"` (case-insensitive; the SDK constructor failure when no credential is in the environment) OR an exception whose class name is `"AuthenticationError"` (the SDK's `anthropic.AuthenticationError` raised on HTTP 401) — the launcher MUST follow the same exit-code asymmetry as the missing-module case: emit `"/debrief:script: anthropic API authentication failed; set ANTHROPIC_API_KEY in the environment and retry. Details logged to .debrief/script_errors.jsonl."` to stderr; log to JSONL per the existing schema; exit 2 if `trigger == "/debrief:script"`, otherwise exit 0. All OTHER exception types (transient API errors not classified as auth-shaped, validation failures, network errors) keep the existing exit-0 behavior — only the two well-known categories (missing module, auth) get user-visible stderr and the exit-2-on-direct-CLI signaling.
- Reads `agents/script-writer.md` per BC-5.21, extracts the model declaration from the YAML frontmatter and the system prompt from the body.
- Builds the user-message body from the inputs enumerated in `spec/script_writer_rfc.md` §6.1: deck_brief.md (full markdown); output/audience.yaml (when present); output/timeline.jsonl (full); .debrief/dialog.jsonl (subject to a 200K-token cap on the assembled message — when exceeded, the dialog archive is truncated from the head, oldest turns dropped first; brief, audience, timeline, slide records, and the existing speaker_script.md are NEVER truncated); deck_state.slides (per-slide slug, title, content_summary, visual_approach, design_choices, user_assets); the existing `speaker_script.md` (when present, included as the co-writer baseline); the `external_documents` slot (always present, always empty in v1, schema reserved per `spec/script_writer_rfc.md` §10).
- Calls the Anthropic API with the extracted prompt as `system` and the assembled inputs as the user message, via the same hybrid-invocation pattern as the rewriter (BC-5.19).
- On API success, validates the agent's output against the six guardrails per REQ-SCRIPT-WRITER-2: source-traceability (names against roster, numerics against sources, paper citations against `paper_attached` events); per-slide structure (section count + required subsections); length budget per slide (compute target = duration / slide_count, flag slides > 1.5×); roster-aware mentions (name mentions require ≥1 keyword overlap between the roster entry's notes and the slide's content_summary or visual_approach); co-writer voice-drift (Jaccard bigram similarity below 0.5 on slides whose source data is unchanged since the last generation). The "no new positions" rule is prompt-only in v1 — no code-side validator.
- On any guardrail failure (excluding warnings), the CLI logs to `.debrief/script_errors.jsonl` with `{timestamp, trigger, error_class, error_message}` and exits 0; the prior `speaker_script.md` is retained. Warnings (voice-drift below threshold, length-budget overrun ≤ 1.5×) are logged with `error_class: warning_<rule>` but do NOT block the write.
- On guardrail-pass, copies the existing `speaker_script.md` (if any) to `.debrief/script_backups/speaker_script.<UTC ISO 8601>.md` per BC-11.20, then atomically writes the new content via the `.tmp` + fsync + rename pattern. Backup-write failure is logged but does NOT block the new generation.
- Exit codes: 0 on success or logged failure (mirroring BC-3.18's exit-0-always pattern); 3 on usage error.
- Cycle implementation: Sub-cycle B of RFC §13.

**BC-3.20a `script-writer` agent-card invocation-mode constraint (BUG-AUDIT-98).** `agents/script-writer.md` MUST contain an opening note (placed in or immediately after the `## Inputs` section) stating that the canonical invocation is `python -m debrief.launcher script_writer` via the consultant's Bash tool, NOT direct dispatch via the `Task` tool. The structured-input contract (DECK BRIEF / AUDIENCE ROSTER / EVENT TIMELINE / DIALOG ARCHIVE / SLIDES / EXISTING SPEAKER_SCRIPT / EXTERNAL DOCUMENTS blocks) assumes the inputs are assembled by `build_script_writer_inputs(...)`, which is the launcher CLI's responsibility. A `Task`-dispatched invocation with a free-form prompt is unsupported and will produce empty or placeholder output because the agent's source-traceability guardrails (REQ-SCRIPT-WRITER-2 #1) reject any claim that does not trace to one of the structured blocks. Rationale: a user who hits the auth-failure bug from BUG-AUDIT-98 (or the missing-SDK bug from BUG-AUDIT-93) and looks for a `Task`-dispatch fallback gets a second silent failure when the agent emits nothing. The agent-card note prevents that confusion. A regression test asserts the constraint sentence is present in `script-writer.md`.

**BC-3.17 `list_commands` + commands subcommand (BUG-AUDIT-76 / REQ-CONSULT-CMD-SURFACE-1).** `src/unit_3/launcher.py` MUST provide two public helpers and MUST wire a `commands` subcommand into `main_new()`'s dispatch table:

- `list_commands(plugin_root: Path) -> dict[str, str]` — pure. Scans `<plugin_root>/commands/*.md`, opens each file, locates the first non-blank line (which MUST be a heading of the form `# /debrief:<slug>`; non-matching files are skipped), walks past blank lines to the first non-blank description line, accumulates description text up to the next blank line joining multi-line paragraphs with a single space, and records the result in the returned dict keyed by the slug extracted from the heading. Files with a heading but no description are skipped (not emitted with empty string). Missing `commands/` directory yields `{}`. The function MUST be idempotent and read-only.
- `main_commands(plugin_root: Path) -> None` — CLI orchestrator. Calls `list_commands` and prints the result as pretty-printed JSON (indented 2 spaces, keys sorted) to stdout. Always exits 0 — enumeration is a read-only operation and any caller is free to consume the result.

The dispatch branch `elif subcommand == "commands":` in `main_new()` parses `--plugin-root` (type=Path, default=the `plugin_root` already derived at the top of `main_new()` from `CLAUDE_PLUGIN_ROOT` or the workspace root) from `sys.argv[2:]` via a local `argparse.ArgumentParser`. The subcommand MUST appear in the usage-line string printed by the catch-all `else` branch so users discover it when they type an unknown subcommand.

Regression tests in `tests/regressions/test_bug_audit_76_command_surface.py` enforce: the helper returns a non-empty dict on the real plugin commands directory; every known command (export, handout, script, slide, style, view, save, restore, quit, present) appears with a non-empty description; each description does NOT contain the heading marker `/debrief:` (so the parser does not confuse heading with description); missing directory returns `{}`; the CLI exits 0 and the stdout JSON round-trips. See REQ-CONSULT-CMD-SURFACE-1 and BUG-AUDIT-76.

**BC-5.17 Slide-record write-through (BUG-AUDIT-75 / REQ-CONSULT-SLIDE-WT-1).** `agents/consultant.md` MUST contain a Responsibilities bullet stating that after every GREEN QA decision from the red-green cycle, the consultant writes the `SlideRecord` to `deck_state.json` in the SAME turn via `python -m debrief.debrief_state update_slide …`. Batching across gates or deferring to end-of-group is forbidden. This parallels BC-5.16's `deck_brief.md` write-through for the same reason: context compaction can fire between a slide-maker dispatch and a later batched state-write turn, leaving the HTML on disk with no matching record.

**BC-5.18 Consultant command-surface awareness (BUG-AUDIT-76 / REQ-CONSULT-CMD-SURFACE-1).** `agents/consultant.md` MUST contain a dedicated section titled `## Command Surface Awareness` placed between `## State Drift Audit` and `## Deck Brief Maintenance` so the three compaction-recovery obligations appear as a trio. The section MUST:

1. **Name the failure mode.** Denying a feature the installed plugin actually ships (e.g., claiming Debrief has no HTML export when `/debrief:present` produces exactly that) erodes user trust every time it happens.
2. **Cite the live enumeration command.** The consultant-facing invocation MUST be `python -m debrief.launcher commands --plugin-root "${CLAUDE_PLUGIN_ROOT}"`. Alternative invocations (shell-globbing `commands/*.md` directly, reading individual files with Read) are strictly worse and MUST NOT be presented as equivalent.
3. **List three obligations:** (a) on-session-start invocation right after the drift audit and the brief read; (b) post-compaction re-inject paired with BC-5.16's post-compaction audit; (c) a pre-reply check before any feature denial (*"Debrief does not have X"*) — consult the live enumeration or the cached same-session result first. A reply denying a feature without the check is a protocol violation.

The hand-maintained `## Command Dispatch Menu` table in the agent card is RETAINED — it carries precondition and wrong-context guidance that the live enumeration does not replace — but the new section MUST make clear that the table is a backstop for dispatch, NOT the source of truth about which commands exist. See REQ-CONSULT-CMD-SURFACE-1 and BUG-AUDIT-76.

`agents/consultant.md` MUST also contain a dedicated section titled `## State Drift Audit` codifying three on-session-start / post-compaction obligations:

1. **On session start,** after loading `deck_state.json` and `debrief_state.json` and BEFORE any dispatch, invoke `python -m debrief.launcher doctor --project-root .`. Surface exit-code-1 drift to the user explicitly with an actionable prompt (report counts, ask before auto-remediating via `--reconstruct`).
2. **Reconstruction is not approval.** When the consultant invokes `doctor --reconstruct` on user confirmation, the reconstructed `SlideRecord` entries have `status="draft"` and MUST be re-vetted through the normal red-green cycle before they count as part of the deck.
3. **Post-compaction re-audit.** When the consultant detects context loss per BC-5.16's post-compaction audit clause, it MUST re-run `debrief doctor` alongside re-reading `deck_brief.md` — compaction can erode the consultant's mental model of which slides exist, and filesystem reality is the authoritative backstop.

Regression tests in `tests/regressions/test_bug_audit_75_doctor_and_drift.py` enforce the CLI behavior (drift detection, exit codes, reconstruction idempotence, minimal-record shape) and the consultant-card obligations (the Responsibilities bullet, the `## State Drift Audit` section, the three contents checks). See REQ-DOCTOR-1, REQ-CONSULT-DOCTOR-1, REQ-CONSULT-SLIDE-WT-1, and BUG-AUDIT-75.

**BC-5.19 Rewrite agent (BUG-AUDIT-78 / REQ-MEMORY-REWRITE-1..4).** The plugin MUST ship a new agent at `agents/rewriter.md` that is the SOLE writer of `deck_brief.md` and `output/audience.yaml`. Contract:

- **Agent-card frontmatter** declares `model: claude-sonnet-4-6` (no user-configurable override) and `tools: Read` (no Write tool — the rewrite-script wraps the model output and writes the files atomically; the agent itself is read-only on its working directory).
- **Card body** is the system prompt. The body MUST encode at minimum these discipline rules: (a) no invention — facts not in inputs are not in output; (b) latest-state-only — no change-log sections inside the brief; (c) canonical sections only per REQ-CONSULT-DECK-BRIEF-1; (d) roster YAML required keys (`name`, `role`) per entry, recommended (`location`, `attendance`, `notes`); (e) subagent replies are NOT in the dialog archive — do not infer subagent-internal content.
- **Hybrid invocation pattern.** The rewrite is dispatched NOT via Claude Code's Task tool (which is awkward from a hook context) but by the `rewrite_brief` CLI subcommand (BC-3.18) reading the agent-card file, extracting the model declaration from frontmatter and the system prompt from the body, and calling the Anthropic API directly with that prompt as `system` and the inputs as the user message. This preserves Debrief's "every agent has a card" convention while keeping the hook fast.
- **Sole-writer invariant.** No other code path MAY write to `deck_brief.md` or `output/audience.yaml`. The consultant agent is forbidden from calling Write on either file (REQ-MEMORY-CONSULT-1). A regression test SHALL AST-scan `agents/consultant.md` (and any other agent card that references the brief) for forbidden Write-tool usage on those paths.
- **Regenerate-from-scratch invariant.** Inputs to the rewrite MUST be `.debrief/dialog.jsonl` + `output/timeline.jsonl` only, EXCEPT on the very first rewrite of a project (per REQ-MEMORY-REWRITE-3, when `.debrief/rewrite_metadata.json` is absent), where the prior `deck_brief.md` MAY be a one-time bootstrap input. After bootstrap, the strict rule applies.
- **Output validation.** Before atomic rename, the script MUST validate: (1) the rendered brief contains exactly the canonical section headings of REQ-CONSULT-DECK-BRIEF-1; (2) the `### Roster` YAML block parses; (3) every roster entry has non-empty `name` and `role` keys. Validation failure causes the script to log per REQ-MEMORY-REWRITE-4 and exit 0 with the prior versions retained.

Cycle 2 implementation lands in Phase 2 of `spec/memory_architecture_rfc.md` §13. Regression tests in `tests/regressions/test_bug_audit_78_*` (Cycle 1) anchor the spec/blueprint contracts; Cycle 2 adds tests that exercise the actual rewrite path.

**BC-5.20 Recall discipline (BUG-AUDIT-78 / REQ-MEMORY-CONSULT-2).** `agents/consultant.md` MUST contain a dedicated section titled `## Recall Discipline` placed within the existing compaction-recovery cluster (between `## Command Surface Awareness` and `## Deck Brief Maintenance`, OR appended to the cluster — exact placement to be determined in Cycle 2 Phase 4). The section MUST:

1. **Name the failure mode.** Asserting a fact (about a named person, paper, figure, decision, or any prior dialog content) from in-context memory alone, when `recall` is available — especially asserting a NEGATIVE fact (*"the user did not say X"* / *"I don't recall Y"*) — produces silent fabrication.
2. **Cite the canonical invocation.** `python -m debrief.launcher recall <query>`.
3. **List the obligation.** Before any reply that asserts a fact about prior dialog content, the consultant MUST run `recall` and ground the reply in the returned hits. Negative replies (*"I don't recall X"*) MUST be backed by an empty `recall` result, not by silence in working memory. This extends BUG-AUDIT-76's *"does Debrief have X?"* live-check pattern (BC-5.18) from features to dialog content.

Cycle 2 implementation lands in Phase 4 of `spec/memory_architecture_rfc.md` §13. The Cycle 1 regression test asserts only that the spec + blueprint anchors exist; the Cycle 2 test will additionally assert the agent-card section is present and contains the marker phrasings.

**BC-5.21 Script-writer agent (BUG-AUDIT-84 / REQ-SCRIPT-WRITER-1..2).** The plugin MUST ship a new agent at `agents/script-writer.md` that is the SOLE writer of `<project_root>/speaker_script.md`. Mirrors BC-5.19's rewriter shape:

- **Agent-card frontmatter** declares `model: claude-sonnet-4-6` (no user-configurable override), `maxTurns: 1` (single call per generation), `tools: Read` (no Write — the wrapping CLI BC-3.20 handles atomic write; the agent itself is read-only on its working directory).
- **Card body** is the system prompt. The body MUST encode the six guardrails from REQ-SCRIPT-WRITER-2: (a) source traceability — no invention of facts, names, numbers, or citations beyond brief / dialog / timeline / slides / roster; (b) no new positions — script does not editorialize beyond what the user surfaced; (c) per-slide structure fixed — one section per slide with the canonical four subsections (Key talking points, Transition, Estimated speaking time; the optional time-checkpoint marker per REQ-SCRIPT-3); (d) length budget per slide — target = duration / slide_count; compress or expand to fit; (e) roster-aware mentions — name a roster member only when their notes plausibly justify it; (f) co-writer mode — when an existing `speaker_script.md` is provided as input, prefer the user's verbatim phrasing for sections whose source data is unchanged; new sections adopt the user's voice. The body MUST also document the `external_documents` input slot (always present, always empty in v1) so the agent's prompt anticipates BUG-AUDIT-85's archetype-aware paper-content extension without breaking changes when v2 ships.
- **Hybrid invocation pattern.** Same as BC-5.19's rewriter: dispatched NOT via Claude Code's Task tool but by the `script_writer` CLI subcommand (BC-3.20), which reads the agent-card file, extracts the model declaration from frontmatter and the system prompt from the body, and calls the Anthropic API directly.
- **Sole-writer invariant.** No other code path MAY write to `<project_root>/speaker_script.md`. After Sub-cycle B ships, BUG-AUDIT-77's regression test (`tests/regressions/test_bug_audit_77_generator_output_paths.py`) is updated to enforce that ONLY the `script_writer` CLI's atomic-write code path writes to the file; legacy generator modules (`src/unit_10/export.py`, the rest of `src/unit_11/utility_skills.py`) still cannot.
- **Validation before write.** Per REQ-SCRIPT-WRITER-2 the wrapping CLI runs the six guardrail validators on the agent's output. Validation failure → log + exit 0 + retain prior `speaker_script.md` (mirror BC-5.19's failure pattern). Warnings (voice-drift, length-overrun) are logged with `error_class: warning_<rule>` but do NOT block the write.
- **Output format clause.** The agent MUST emit ONLY the script markdown — no preamble, no postscript, no commentary. The first character of the output is the `#` of the `# Speaker Script` heading. The wrapping CLI does not strip preambles; an offending preamble fails the structural validator.

Cycle implementation: Sub-cycle B of `spec/script_writer_rfc.md` §13. Regression tests in `tests/regressions/test_bug_audit_84_*` (Sub-cycle A) anchor the spec/blueprint contracts; Sub-cycle B adds tests exercising the actual script-writer path.

**BC-5.22 Paper-analyzer invocation sections in `agents/consultant.md` (BUG-AUDIT-89).** `agents/consultant.md` MUST contain two adjacent sections, in the following order, between `## Event Timeline Emission` and `## Deck Brief Maintenance`:

1. **`## Paper Analyzer Invocation`** — the deterministic shell. The section MUST contain: (a) a "Trigger" subsection naming the path-shape detection rule (path-shaped string ending in `.pdf`, file exists); (b) a "Command template" subsection containing the literal substring `python -m debrief.paper_analyzer --pdf` (BC-5.11 grammar); (c) a "Sub-phase transitions" subsection naming all three relevant sub_phase values literally — `discovery/dialog`, `discovery/paper_analysis`, `discovery/figure_selection`; (d) an "Event emissions" subsection naming both event types literally — `paper_attached` and `figure_selected`; (e) a "Multi-paper loop" subsection describing per-path processing in document order, no batching, error handling that surfaces non-zero exit codes to the user. This subsection's prose IS pinned by regression — drift is a CRITICAL bug because the deterministic plumbing must be reliable across compaction boundaries.

2. **`## Paper Discussion`** — the open Socratic engagement layer. The section header MUST exist literally. The body describes branching by `paper_role` (Cycle 5 / BUG-AUDIT-90 introduces the taxonomy, amended in Cycle 8 / BUG-AUDIT-91 to retire `none`: `primary_dissection`, `primary_thematic`, `primary_document`, `concept_source`, `background_reference`) and what discussion shape applies per role. The body's prose is NOT pinned by regression — substantive engagement with the user's content is where LLM judgment is the value, not the smell. The regression test asserts the section header exists and all five `paper_role` values are mentioned, but does NOT pin discussion prose word-for-word.

A single regression test in `tests/regressions/test_bug_audit_89_consultant_paper_sections.py` enforces: (a) both section headers exist in the specified order; (b) the deterministic substrings (command template fragment, all three sub_phase strings, both event names) appear in `## Paper Analyzer Invocation`; (c) all five `paper_role` values appear in `## Paper Discussion` (the retired `none` value MUST NOT appear); (d) the literal phrase "discovery/figure_selection" appears in both sections (transition into the gate from the discussion).

**BC-5.23 paper_role taxonomy + paper_required across archetypes (BUG-AUDIT-90, amended by BUG-AUDIT-91).** Every entry in `archetypes.json` MUST have BOTH a `paper_role` field AND a `paper_required` boolean field. Together they describe a two-axis design: `paper_role` describes *how* papers are used if provided, `paper_required` describes *whether* the consultant proactively demands a paper.

**`paper_role`** value is one of: `primary_dissection`, `primary_thematic`, `primary_document`, `concept_source`, `background_reference`. Semantics:

- `primary_dissection`: paper IS the presentation, figure-by-figure. Use: journal_club / single_paper.
- `primary_thematic`: multiple papers compared thematically. Use: journal_club / multi_paper (sub-mode override on top of the archetype-level `primary_dissection`).
- `primary_document`: a single document (thesis, monograph, proposal) is the defended subject. Use: thesis_discussion.
- `concept_source`: papers are an optional resource pool the user draws specific concepts/figures from. The user's G1.3 reply IS the contract — a single-figure reply (e.g., `2`) is fully valid; the consultant MUST NOT propose additional figure slides beyond the user's selection. Use: lecture, lab_meeting, seminar, custom.
- `background_reference`: papers, if supplied, are cited but not auto-converted to figure slides. Use: conference_talk, job_talk, grant_panel, investor_pitch.

The value `none` was retired in BUG-AUDIT-91 — paper handling is now universally available across archetypes; the role describes *how to use a paper if provided*, not *whether the archetype accepts one*.

**`paper_required`** is `true` only for `journal_club` and `thesis_discussion` (the two archetypes where the paper is the defended/dissected subject). When `paper_required: true`, `agents/consultant.md` Step 5 MUST include an explicit imperative demanding the paper as the first archetype-specific question, and the briefing MUST NOT proceed past Step 5 until paper paths are supplied. When `paper_required: false`, papers are accepted if offered but not demanded.

Behavioural consequences:

- **Trigger of `paper_analyzer`** (BC-5.11): fires whenever the user supplies a paper PDF path during discovery, regardless of archetype. The pre-amendment "fires for `paper_role != none`" gate is dropped per BUG-AUDIT-91 — every archetype accepts papers; the `paper_role` shapes downstream behavior only.
- **G1.3 figure-selection gate** fires for any archetype once the analyzer has run on at least one paper.
- **VETO-07** (caption-as-body) fires whenever a slide's `user_assets` references a path under `assets/reference/papers/`, regardless of archetype.
- **Slide-maker behavior** (`agents/slide-maker.md` `## Paper-Derived Figures` section) branches: `concept_source` produces one slide per user-selected figure with no over-design; `primary_dissection` produces figure-by-figure in paper order; `primary_thematic` allows cross-paper composite slides; `background_reference` does not auto-generate figure slides.
- **Consultant behavior** (`agents/consultant.md` `## Paper Discussion` section) branches discussion shape per role per BC-5.22. The user MAY override the default `paper_role` for a specific paper during the discussion; the role is the *default*, not a rigid rule.

A regression test in `tests/regressions/test_bug_audit_90_paper_role_taxonomy.py` (extended in BUG-AUDIT-91) enforces: (a) every archetype has both `paper_role` and `paper_required` fields; (b) `paper_role` value is in the closed set above with `none` rejected; (c) `paper_required` is `true` only for `journal_club` and `thesis_discussion`; (d) the canonical mapping is pinned (lab_meeting, lecture, seminar, custom → `concept_source`; conference_talk, job_talk, grant_panel, investor_pitch → `background_reference`; journal_club → `primary_dissection`; thesis_discussion → `primary_document`).

**BC-5.24 Auto-memory disclaimer in `agents/consultant.md` (BUG-AUDIT-92).** `agents/consultant.md` MUST contain a dedicated section titled exactly `## Auto-Memory Disclaimer` placed before `## Recall Discipline` (BC-5.20) so the agent reads the carve-out before it reaches the existing dialog/timeline sections. The section MUST:

1. Acknowledge that Claude Code's runtime may inject a system prompt naming an auto-memory path under `~/.claude/projects/...`.
2. Instruct the consultant to ignore that injection for debrief sessions and explain why — the `bin/check-write-auth` hook (BC-1.9) blocks all writes outside `$PWD/` by design.
3. Enumerate debrief's project-scoped memory surfaces (dialog archive, event timeline, deck brief, audience roster, slide records) with their canonical CLI write paths (`append_dialog_turn`, `emit_event`, the rewriter agent, `update_slide`).
4. Instruct the consultant that on encountering a hook block of an out-of-project Write, it MUST NOT surface the block to the user as a "memory failure" — instead it re-routes the intended action to the appropriate debrief CLI.

This section is a behavioral disclaimer; the prose may evolve, but the four obligations above MUST be present. A regression test in `tests/regressions/test_bug_audit_92_auto_memory_disclaimer.py` enforces: (a) the section header exists; (b) the section is placed before `## Recall Discipline`; (c) the literal substring `~/.claude/projects/` appears (so the disclaimer references the auto-memory path explicitly); (d) the canonical debrief memory paths (`.debrief/dialog.jsonl`, `output/timeline.jsonl`, `deck_brief.md`) are all named; (e) the BC-1.9 / `check-write-auth` reference is present so a future model reading the prompt understands the block is by-design.

**BC-5.25 Doctor discipline (BUG-AUDIT-99).** `agents/consultant.md` MUST contain a dedicated section titled exactly `## Doctor Discipline` placed within the existing compaction-recovery cluster (alongside `## Recall Discipline` per BC-5.20 — exact placement is a stylistic choice but the section MUST exist). The section MUST:

1. **Name the failure mode.** State drift accumulates silently when the consultant skips required state-mutation calls (slide registration, phase advancement, paper archival, brief synthesis). Downstream commands that branch on state — `/debrief:view`, `/debrief:export`, `/debrief:script`, the rewriter — produce wrong answers when the recorded state has diverged from filesystem and event-stream reality. Per-bug fixes have wired up *detection* (the doctor's audit modes) but routine *invocation* of the audits is what closes the loop.

2. **Cite the canonical invocation.** `python -m debrief.launcher doctor --reconstruct --brief-audit --asset-audit --phase-audit --project-root .` (the no-arg run with all four modes). The four modes MUST be named explicitly in the section so the consultant has the full discovery surface and can pick a subset when only some checks apply.

3. **List the prescribed run-points.** The consultant MUST run `doctor` (with all four modes) at:
   - **Session start**, after Claude Code resumes the project (compaction recovery).
   - **After every successful `slide-maker` dispatch returns**, in the same turn as the BC-5.17 `update_slide` call. The doctor confirms the registration landed and no other drift has crept in.
   - **Before any read-state command that branches on `phase` / `sub_phase` / `slides[]`**: `/debrief:view`, `/debrief:export`, `/debrief:script`. Running doctor first prevents the misleading "no slides yet" / "no presentations exist" / "no approved slides" failure modes that a stale state file produces.
   - **Before phase transitions** (discovery → production, production → finalization). The transition itself happens via `python -m debrief.debrief_state update --set sub_phase=...`; running doctor first surfaces any drift that should be fixed before advancing.

4. **Document the recovery loop.** When `doctor` reports drift, the consultant MUST: (a) read the `notes` field in the JSON report — each note names a copy-pasteable recovery CLI command; (b) surface a one-line drift summary to the user before applying the fix, so the user knows what self-healing happened; (c) execute the recommended recovery command via the Bash tool; (d) re-run `doctor` to confirm the drift is resolved; (e) proceed with the original action only after the doctor reports clean. The consultant MUST NOT silently apply recovery without surfacing the drift to the user — observability of the self-heal is part of the contract.

5. **Document the auto-remediation exception.** The `--reconstruct` flag is the one exception to the surface-then-apply pattern: it is itself the remediation for the orphan-files drift mode (BUG-AUDIT-75), not a separate command. The consultant MAY use it directly when slide-file/state drift is the detected mode and the recovery is "reconstruct minimal SlideRecord entries." Other modes' recoveries (CLI invocations from the audit's `notes`) MUST go through the surface-then-apply pattern.

A regression test in `tests/regressions/test_bug_audit_99_phase_audit.py` enforces: (a) the section header exists; (b) the canonical doctor invocation appears in the section with all four mode flags; (c) all four prescribed run-points are named (session start, after slide-maker, before read-state commands, before phase transitions); (d) the recovery loop's surface-then-apply discipline is described; (e) the section references all four audit modes by name.

**BC-3.21 `archive_paper` subcommand (BUG-AUDIT-94).** `src/unit_3/launcher.py` MUST provide an `archive_paper` subcommand wired into `main_new()`'s dispatch table. The subcommand provides the explicit retroactive paper-archival path for cases where the consultant's automatic trigger detection (BC-5.11 / `## Paper Analyzer Invocation`) missed the user's paper. Contract:

- Parses `--pdf <path>` (Path, required) and `--project-root` (Path, default `Path.cwd()`).
- Validates the PDF path exists and ends with `.pdf`; exits 1 with a clear stderr message otherwise.
- Computes the paper slug via `paper_analyzer.derive_paper_slug(pdf_path)` per BC-12.8.
- Calls `paper_analyzer.main_paper_analyzer(pdf_path, paper_slug, project_root)` directly (not via subprocess — the launcher and paper_analyzer are in the same package).
- After successful analyzer return, verifies `assets/reference/papers/<slug>/` was created. If absent, exits 2.
- Updates `debrief_state.papers_provided=True` via the canonical `read_debrief_state` / `write_debrief_state` path (BC-2.15a).
- Appends a `paper_attached` event to `output/timeline.jsonl` via `append_timeline_event(project_root, event="paper_attached", payload={"path": str(pdf_path), "slug": slug})` per BC-2.18.
- Prints a one-line success summary and exits 0.
- Exit codes: 0 success; 1 PDF missing/invalid; 2 paper_analyzer failure or missing post-condition; 3 usage error.
- Idempotent: running it twice on the same PDF re-archives the file and re-emits the event without corruption (the analyzer's atomic-write contract handles overwrite).

The subcommand MUST appear in the usage-line string printed by the catch-all `else` branch in `main_new()`. A new command file at `commands/archive-paper.md` (workspace: `src/unit_1/commands/archive-paper.md`) carries the user-facing documentation; `/debrief:archive-paper <path>` is the user-invocable form.

**BC-3.16 amendment for `--asset-audit` (BUG-AUDIT-94).** The `doctor` subcommand (BC-3.16) MUST accept an `--asset-audit` flag in addition to the existing `--reconstruct` and `--brief-audit`. When passed, the subcommand calls `_audit_assets(project_root)` and adds an `asset_audit` field to the JSON output containing: `paper_directories` (list of slug subdirectories under `assets/reference/papers/`), `paper_attached_event_count` (count of `paper_attached` events in `output/timeline.jsonl`), `papers_provided_flag` (the `debrief_state.papers_provided` value), `orphan_paper_figures_in_images` (filenames in `assets/images/` matching paper-figure shapes when `assets/reference/papers/` is empty), `unprefixed_image_files` (filenames in `assets/images/` that lack the `<slug>_` prefix mandated by REQ-ASSET-1), `drift` (bool), `notes` (human-readable diagnoses).

**BC-3.16 amendment for `--phase-audit` (BUG-AUDIT-99).** The `doctor` subcommand (BC-3.16) MUST accept a `--phase-audit` flag in addition to `--reconstruct`, `--brief-audit`, and `--asset-audit`. When passed, the subcommand calls `_audit_phase(project_root)` and adds a `phase_audit` field to the JSON output containing: `phase` (the current `debrief_state.phase` value), `sub_phase` (the current `debrief_state.sub_phase` value), `approved_slide_count` (count of `deck_state.slides` entries with `status == "approved"`), `style_locked` (the `deck_state.style_locked` value), `drift` (bool), `notes` (human-readable diagnoses, each line including a copy-pasteable recovery CLI command). The audit detects three drift signals: (1) primary — `approved_slide_count > 0` AND `phase == "discovery"` (slides exist but the state file says we're still in discovery; recovery: `python -m debrief.debrief_state update --set sub_phase=production/slide_review --project-root <path>`); (2) `style_locked` is True AND `phase == "discovery"` AND `sub_phase != "discovery/style_analysis"` (style was locked but phase did not advance; recovery: same `update --set sub_phase=...` invocation, with the appropriate sub_phase for the user's current activity); (3) `phase == "production"` AND `sub_phase == "production/group_planning"` AND `approved_slide_count > 0` (sub_phase did not advance past planning even though slides have been approved; recovery: `update --set sub_phase=production/red_green` or `production/slide_review`). Phase drift is reported via exit code 1, mirroring `--brief-audit` and `--asset-audit`. The audit MUST NOT auto-remediate — like the other doctor modes, it surfaces drift and emits the recovery command but leaves the actual write to the consultant or user.

Asset-side drift fires when ANY of: orphan paper figures in `assets/images/`; `papers_provided=true` but no paper directories; `papers_provided=false` but paper directories exist; paper directories exist but zero `paper_attached` events in timeline; image files lack the slug prefix. Drift is reported via exit code 1 in report-only mode (matching the brief-audit pattern). The asset audit is read-only — there is no asset-side `--reconstruct` mode in v1; remediation is the user invoking `/debrief:archive-paper` explicitly.

**BC-5.11 amendment for trigger robustness (BUG-AUDIT-94).** In addition to the path-shaped-string-ending-in-.pdf primary trigger, `agents/consultant.md` `## Paper Analyzer Invocation` § Trigger MUST document two secondary signals:

1. **Bare PDF filename** with no directory prefix (e.g., `Smith2024.pdf`). The consultant attempts resolution against `<project_root>/`, `~/Downloads/`, and any user-stated paper-storage location before concluding the file does not exist.
2. **Verbal mention of "paper", "PDF", or "preprint"** without a path-shaped string. The consultant MUST NOT silently proceed; it MUST ask the user explicitly for the file path or basename and refuse to advance past Step 5 (or accept the paper as a slide source) without an analyzed file under `assets/reference/papers/`.

The card MUST also document a recovery path: if the consultant detects mid-session that a paper was discussed but `paper_analyzer` was never run (signals: `papers_provided=false` despite paper-discussion in the dialog, or `assets/reference/papers/` empty despite figures in slide drafts), the consultant MUST surface the `/debrief:archive-paper <path>` command to the user as the recovery action.

The post-success block MUST require BOTH (a) emitting the `paper_attached` event via `python -m debrief.launcher emit_event --event paper_attached --payload-json '{"path": "<path>", "slug": "<slug>"}'`, AND (b) updating the state via `python -m debrief.debrief_state update --set papers_provided=true`. Neither is optional. A regression test parses the agent card and asserts both command substrings appear after the path-shape trigger description.

**BC-3.15 `scripts/fetch_vendor.py` — vendor asset acquisition script.** The workspace MUST contain a script at `scripts/fetch_vendor.py` (at the workspace root, alongside `routing.py` and `prepare_task.py`; NOT inside the plugin directory — it is a maintainer build step, not a runtime artifact, and must not ship in `~/.claude/plugins/cache/`). The script: (a) reads `src/unit_1/assets/vendor/VERSIONS.md` via `_parse_versions`, which enforces the tab-separated `<filename>\tversion <ver>\tsha256:<hash>\t<source_url>` shape per BC-1.12 and raises `ValueError` on any malformed line; (b) for each listed entry, downloads the file from `<source_url>` via `urllib.request.urlopen` with a 30-second timeout (stdlib only; no `requests` or other third-party dependency); (c) computes SHA-256 of the downloaded bytes; (d) compares to the manifest hash and SKIPS the write if the target already exists and its hash already matches (idempotent no-op on a fully populated vendor directory); (e) FAILS LOUDLY on any hash mismatch — prints a stderr error naming the file, the manifest hash, and the downloaded hash, adds the file to a failure list, and exits with code 1 without writing anything; (f) on success, writes the verified bytes to the target path under `src/unit_1/assets/vendor/` and prints a `[fetch]` or `[skip]` line per entry plus a final summary count. The script MUST be invoked manually by the maintainer whenever VERSIONS.md is bumped — it is never auto-run by `bin/debrief` or any other user-facing entry point, preserving INV-07 (no external network requests from a running project). A regression test in `tests/regressions/test_bug_audit_16_vendor_real_files.py` asserts the script exists at the workspace root and is Python-importable. See BUG-AUDIT-16.

---

## Unit 4: Routing Protocol

### Tier 2 — Signatures

```python
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any, Optional


# --- debrief.routing ---

def main_routing(project_root: Path) -> None:
    """
    Entry point for: python -m debrief.routing --project-root <path>

    Reads debrief_state.json and outputs a structured ActionBlock JSON to stdout.
    Pure function of current state: same state always produces same output.
    No side effects.
    """
    ...


def resolve_action(
    state: "DebriefState",  # from debrief.debrief_state
    project_root: Path,
) -> dict[str, Any]:
    """
    Implement the Sub-Phase Transition Table from Section 14.17 as an explicit
    state machine. Match on (phase, sub_phase, pending_gate, condition_flags)
    and return the ActionBlock dict.
    """
    ...


def check_g3_2_machine_gate(
    current_slug: str,
    red_green_iteration: int,
    red_green_started_at: Optional[str],
    project_root: Path,
) -> str:
    """
    Read qa_log.jsonl for entries matching current_slug with timestamp >=
    red_green_started_at. Return "GREEN", "RED", "EXHAUSTED", or "OSCILLATION".

    GREEN: latest entry has passed=True.
    RED: latest entry has passed=False and red_green_iteration < 5.
    EXHAUSTED: passed=False and red_green_iteration >= 5.
    OSCILLATION: two most recent entries have same failure count but different
                 failure invariant IDs.
    """
    ...


# --- debrief.update_state ---

def main_update_state(
    gate_id: str,
    response: str,
    project_root: Path,
    skill_prelude: Optional[str] = None,
    field_assignments: Optional[list[str]] = None,
) -> None:
    """
    Entry point for:
        python -m debrief.update_state --gate <gate_id> --response <text>
            --project-root <path>
        python -m debrief.update_state --skill-prelude <skill_name>
            --field <name>=<value> --project-root <path>

    Validates response against gate's valid_responses or grammar.
    Exits code 4 with 'Invalid response. Expected: <grammar>' on mismatch.
    Writes state transitions via Unit 2 library.
    """
    ...


def validate_gate_response(
    gate_id: str,
    response: str,
    valid_responses: list[str],
) -> bool:
    """
    Validate response against the gate's valid_responses list or grammar.
    Returns True if valid, False otherwise.
    For parameterized gates (e.g., 'SLIDE REVISE <instructions>'), validates
    the fixed prefix and extracts the payload.
    """
    ...


def handle_red_green_transition(
    gate_id: str,
    response: str,
    state: "DebriefState",
    project_root: Path,
) -> None:
    """
    Handle state transitions for red-green cycle gates (G3.2).
    Increments red_green_iteration, sets red_green_started_at on first iteration,
    manages best-known-good snapshot logic, and writes qa_cycle_log.jsonl at
    cycle exit.
    """
    ...


def perform_snapshot(slug: str, iteration: int, project_root: Path) -> None:
    """
    Copy slides/<slug>.html to .debrief/snapshots/<slug>_iter_<N>.html
    before a rewrite iteration. Atomic (write-to-tmp then rename).
    """
    ...


def merge_approval_payload(slug: str, project_root: Path) -> None:
    """
    Read .debrief/approval_<slug>.json, validate required fields
    (slug, title, content_summary, visual_approach, design_choices),
    merge into the slide record in deck_state.json, delete the approval file.
    Raises FileNotFoundError if the approval file is absent.
    """
    ...


def promote_style_draft(project_root: Path) -> None:
    """
    Implement the Section 24.8 compile-and-lock sequence:
    1. Validate .debrief/draft/style_config.json has all required keys.
    2. Atomically rename .debrief/draft/style_config.json -> style_config.json.
    3. Atomically rename .debrief/draft/style_guide.md -> style_guide.md.
    4. Invoke python -m debrief.style_compiler style_config.json assets/style.css.
    5. chmod 444 on style_config.json and style_guide.md.
    6. Set style_locked: True in deck_state.json.
    7. rmtree .debrief/draft/.
    Raises RuntimeError if any step fails; does not leave a half-promoted state.
    """
    ...


# --- debrief.prepare ---

def main_prepare(action: str, project_root: Path) -> None:
    """
    Entry point for: python -m debrief.prepare --action <id> --project-root <path>

    Assembles .debrief/task_prompt.md from context files for the current action.
    Handles gate_data.json injection per Section 24.20 cross-cycle rule.
    Substitutes all {placeholder} values in gate prompt templates.
    Exits code 4 if gate_data.json gate_id mismatches expected gate_id.
    """
    ...


def assemble_task_prompt(
    action: str,
    context_files: list[str],
    project_root: Path,
    plugin_root: Path,
) -> str:
    """
    Build the task prompt markdown string from the list of context file paths.
    Each section: '## Context: <filename>\n<content>\n'.
    For QA revision context, extract the latest qa_log.jsonl entry and embed
    under '## QA Result'.
    Always includes rhetorical_role from slide brief when Slide Maker is the target.
    """
    ...


def substitute_gate_placeholders(
    template: str,
    state: "DebriefState",
    project_root: Path,
) -> str:
    """
    Substitute all {placeholder} tokens in gate prompt templates with resolved
    values from state and project files. After substitution, no unresolved {}
    tokens may remain. <literal> tokens (user-input indicators) are left unchanged.
    """
    ...


def consume_gate_data(
    expected_gate_id: str,
    project_root: Path,
) -> Optional[dict[str, Any]]:
    """
    Read .debrief/gate_data.json if present. If gate_id matches expected_gate_id,
    return the data payload and delete the file. If gate_id mismatches, exit with
    code 4. If file absent, return None.
    """
    ...
```

### Tier 3 -- Behavioral Contracts

**BC-4.1 Routing purity.** `resolve_action` must have no side effects. Given the same `debrief_state.json` content, it must always emit the same ActionBlock. It must not write to any file. It must not invoke any subprocess.

**BC-4.2 ActionBlock schema compliance.** Every emitted ActionBlock must conform to the Section 24.15 schema. Required fields: `action_type`, at least one of `agent`/`gate_id`. `prepare` and `post` fields, when present, must be complete shell command strings, not bare identifiers.

**BC-4.3 G3.2 machine gate — qa_log timestamp filter.** `check_g3_2_machine_gate` must filter qa_log entries to only those with `timestamp >= red_green_started_at`. Entries from prior cycles for the same slug must not influence the current cycle's result.

**BC-4.4 Oscillation detection.** Oscillation is detected when the two most recent qa_log entries for the current slug (within the current cycle) have equal `len(failures)` but different sets of `failure.invariant` IDs. On oscillation, routing must emit a `human_gate` ActionBlock for gate G3.2a, not RED. Note: the Section 14.17 transition table's condition column uses the shorthand "update_state detects oscillation" — this is a specification-level shorthand; the detection logic runs in the routing script's `check_g3_2_machine_gate()` because routing is the module that reads `qa_log.jsonl` for G3.2 analysis. The routing script emits a `human_gate` ActionBlock for G3.2a when oscillation is detected; `update_state` does not participate in oscillation detection.

**BC-4.5 update_state invalid response exit code.** On invalid gate response, `main_update_state` must exit with code 4 and print `Invalid response. Expected: <grammar>` to stderr. It must not write any state changes before exiting.

**BC-4.6 G2.1 STYLE APPROVED sequence atomicity.** `promote_style_draft` executes the seven-step sequence from Section 24.8: (1) atomically rename draft config and guide to project root via `os.rename`, (2) invoke `style_compiler` on the project-root files, (3–7) chmod, set `style_locked`, rmtree `.debrief/draft/`. **On compiler failure (step 2):** do NOT roll back the file promotion — the just-promoted `style_config.json` and `style_guide.md` at the project root ARE the canonical versions per Section 24.8. Do NOT remove `.debrief/draft/` (it is already empty of draft config/guide after step 1; any remaining preview artifacts are retained for diagnostic purposes). Do NOT set `style_locked`. Fire G2.2 LOCK FAILED with the compiler's stderr injected into the gate context. A retry re-runs from step 2 (re-invoke style compiler on project-root files), NOT from step 1 (files are already at project root). `style_locked` remains `false` until a successful compilation.

**BC-4.6 amendment (BUG-AUDIT-19) — `main_update_state` MUST dispatch G2.1.** `main_update_state()` in `routing.py` MUST contain an explicit dispatch branch for `gate_id == "G2.1_style_config_review"`. The branch runs AFTER the generic gate-response validator (which has already rejected any malformed response with `sys.exit(4)`) and BEFORE the generic `last_gate_response` writer at the end of the function. On `response == "STYLE APPROVED"`, the branch MUST call `promote_style_draft(project_root)` as its first action. On `response` starting with `"STYLE REVISE "` (with trailing space per the `_GATE_VALID_RESPONSES` grammar `"STYLE REVISE <instructions>"`), the branch MUST call `_handle_g21_style_revise(response, project_root)` which (a) extracts the feedback payload after the prefix, (b) writes `.debrief/gate_data.json` atomically with `{"gate_id": "G2.1_style_config_review", "data": {"style_revise_feedback": "<feedback>"}}`, and (c) recursively removes `.debrief/draft/` per spec §24.21. Both branches intentionally FALL THROUGH to the generic `last_gate_response` writer so `debrief_state.last_gate_response` is always persisted. Prior to BUG-AUDIT-19, `main_update_state` had no G2.1 branch at all — the function recorded the gate response in `debrief_state.json` and returned, leaving the drafts unpromoted and `style_locked` false. `promote_style_draft` was defined, thoroughly unit-tested in isolation, but NEVER called from production code — an orphan. Falling through to the generic writer on any G2.1 response is a **contract violation** of spec §24.8's requirement that `update_state` is the sole caller for the compile-and-lock sequence. A regression test at `tests/regressions/test_bug_audit_19_g21_style_promotion.py` enforces both branches with synthetic project fixtures; an integration sentinel in `tests/unit_4/test_routing.py::TestG21StylePromotionDispatch` duplicates the STYLE APPROVED case next to the `TestPromoteStyleDraft` unit tests so a future maintainer editing `main_update_state` sees the integration assertion beside the helper tests. See BUG-AUDIT-19.

**BC-4.19 Integration tests MUST walk helper-function dispatch chains (BUG-AUDIT-19).** Whenever a Blueprint Contract names a helper function (e.g., `promote_style_draft`, `handle_red_green_transition`, `_handle_figure_selection`) that a higher-level entry point (`main_update_state`, `main_routing`, `main_prepare`, etc.) MUST call under specific conditions, the test suite MUST include at least one integration test that invokes the higher-level entry point and verifies the helper's side effects. Unit tests of the helper in isolation are necessary but NOT sufficient: a missing call site is invisible to isolation tests by construction — the test harness happily passes while the production dispatch chain is broken. BUG-AUDIT-19 is the illustrative incident: `promote_style_draft` had six passing unit tests while being completely orphaned from `main_update_state`, and the orphan surfaced only when a user hit it in production. The integration test for each contract MUST live either in the regression test file for the relevant BUG-AUDIT or in the same unit test file as the helper's isolation tests (preferred: co-locate so a future maintainer editing the dispatch sees the integration assertion next to the unit tests of the helper it must call). See BUG-AUDIT-19.

**BC-4.21 G3.3 SLIDE APPROVED merge dispatch (BUG-AUDIT-20).** `main_update_state()` in `routing.py` MUST contain an explicit dispatch branch for `gate_id == "G3.3_slide_review"`. On `response == "APPROVE"`, the branch MUST read `debrief_state.current_slide_slug` (exit code 4 with a diagnostic message if it is null — that is state corruption, the slug must be set before a slide can be approved) and call `merge_approval_payload(slug, project_root)` as its first action. The helper reads `.debrief/approval_<slug>.json`, validates the required fields (`slug`, `title`, `content_summary`, `visual_approach`, `design_choices`), merges the payload into the slide record in `deck_state.json`, sets the slide's `status` to `"approved"`, writes `deck_state.json` atomically, and unlinks the approval file. The dispatch branch then falls through to the generic `last_gate_response` writer so `debrief_state.last_gate_response` is persisted in its own state file. On `response == "REVISE"` or `response == "DISCARD"`, the branch MUST NOT call `merge_approval_payload` — those responses fall through to the generic writer unchanged, leaving the slide record and the approval file intact for the next iteration. Prior to BUG-AUDIT-20 this entire branch was missing and `main_update_state` fell through to the generic writer for every G3.3 response, leaving approved slides with stale `title`/`content_summary`/`visual_approach`/`design_choices` fields in `deck_state.json` and orphaned `approval_<slug>.json` files on disk. `merge_approval_payload` was defined in routing.py and described in the Tier 2 signature block at line 658, but was NEVER called from production code AND had zero test coverage — the purest orphan surfaced by the BUG-AUDIT-20 audit pass. A regression test at `tests/regressions/test_bug_audit_20_orphan_audit.py::TestBugAudit20LegA` enforces the dispatch and the post-conditions (payload merged, status updated, approval file deleted, last_gate_response persisted). See BUG-AUDIT-20.

**BC-4.22 Standing orphan/drift sentinels (BUG-AUDIT-20).** The test suite MUST include three standing audit sentinels in `tests/regressions/test_bug_audit_20_orphan_audit.py` that catch the structural defect classes surfaced by BUG-AUDIT-18, -19, and -20. (1) **Gate dispatch sentinel**: parses `routing.py` via `ast.walk`, extracts every `gate_id == "<literal>"` and `gate_id in ("<literal>", ...)` comparison inside `main_update_state`'s function body, and asserts every key in `routing._GATE_VALID_RESPONSES` is either in that set OR on a hardcoded allowlist of "generic-write-only" gates whose response needs only `last_gate_response` persistence. If a new gate is added to `_GATE_VALID_RESPONSES` without a dispatch branch and without an allowlist entry, this test fails loudly. A meta-test asserts every allowlist entry corresponds to a real gate (no stale allowlist). (2) **Phantom `debrief.*` import sentinel**: auto-discovers the canonical set of real modules from the filesystem (walks `src/unit_*/*.py` in workspace or `src/debrief/*.py` in delivered), then walks every `.py` file under `src/` and, for each `from debrief.X import ...` or `import debrief.X` match, asserts `X` is in the canonical set. A meta-test asserts the auto-discovery returned a non-empty set with known-required modules present. Extends BUG-AUDIT-18's specific `debrief.state` sentinel to the full `debrief.*` namespace. (3) **BC-named orphan sentinel**: hardcoded map of `{bc_id: function_name}` covering BCs that name production-called functions. For each entry, walks `src/` line by line (skipping comments and def lines) and counts call sites for the function. If zero production call sites exist, the function is flagged as an orphan unless it is on the `_ORPHAN_WHITELIST` map (each whitelist entry MUST reference a tracking BUG-AUDIT number). A meta-test asserts no whitelist entry corresponds to a function that is actually wired up (stale-whitelist detection). These three sentinels are the structural defense against recurrence of BUG-AUDIT-18's typo-import pattern, BUG-AUDIT-19's missing-dispatch pattern, and BUG-AUDIT-20's BC-named-orphan pattern. Unit tests of helpers in isolation are necessary but NOT sufficient — the sentinels catch the "is the caller wired up" gap that unit tests cannot. See BUG-AUDIT-20.

**BC-4.7 gate_data.json cross-cycle rule.** `consume_gate_data` must delete the file after reading and matching. It must exit code 4 (not silently ignore) if the file is present but the `gate_id` does not match. This prevents stale gate data from contaminating future cycles.

**BC-4.7b Stylist task-prompt schema injection.** For any action in the set `{style/style_dialog, style/style_lock}`, `main_prepare` MUST prepend a `## Schema Starting Point` section to the assembled task prompt before the atomic write to `.debrief/task_prompt.md`. The section structure is load-bearing: (a) the literal section header `## Schema Starting Point`, (b) a short explanatory paragraph referencing spec §24.16.1 and BC-6.11, (c) a JSON fenced code block whose contents are the verbatim bytes of the file resolved by `_resolve_template_path(plugin_root)`. The resolver MUST try `plugin_root / 'templates' / 'style_config.json'` first and MAY fall back to a path derived from `routing.py`'s `__file__` for test and offline contexts where `CLAUDE_PLUGIN_ROOT` is not set. If no candidate resolves to an existing file, `main_prepare` MUST exit with code 1 and a diagnostic message naming BUG-AUDIT-14. The injected JSON MUST pass `style_engine.parse_style_config` — enforced by a regression test in `tests/regressions/test_bug_audit_14_prepare_injects_stylist_template.py` that extracts the JSON block from the assembled task prompt, writes it to a tmp file, and calls `parse_style_config` on the result. This contract closes the BUG-AUDIT-13 failure-mode hole where the Stylist's system prompt tells the agent to `Read()` the template but the agent may choose to skip the instruction; prepare-time injection is belt-and-suspenders over `agents/stylist.md` so the schema is physically present in the task prompt on turn zero regardless of LLM discipline. See BUG-AUDIT-14.

**BC-4.7c Deterministic deliverable-folder name proposal.** *(Superseded in part by BUG-AUDIT-70 / BC-10.9.)* `routing.py` MUST provide a public function `propose_presentation_folder_name(deck_state, today=None) -> str` that returns the canonical `<YYYY_MM_DD>_<shortened_title>` proposal per spec §24.10. The function MUST: (a) default `today` to `date.today()` when not provided; (b) format the date portion as `today.strftime("%Y_%m_%d")`; (c) derive the title portion by calling `debrief_state.sanitize_identifier(deck_state.project_name, max_length=40)` so the algorithm is identical to spec §24.10.1 (lowercase, spaces and hyphens to underscores, strip non-`[a-z0-9_]`, collapse runs, strip edges, fallback to `"untitled"`); (d) return the joined string `f"{date_part}_{title_part}"`. For any action in the set `_EXPORT_DIALOG_ACTIONS = {finalization/export_options, finalization/export_confirm}`, `main_prepare` MUST prepend a `## Proposed Presentation Folder` section to the assembled task prompt containing (a) the literal section header, (b) an explanatory paragraph citing spec §24.10, REQ-EXPORT-3, REQ-LIFE-3, and instructing the agent NOT to invent an alternative format, (c) a fenced code block containing the computed name. If `deck_state.json` is missing or malformed at this point, `main_prepare` MUST exit with code 1 and a diagnostic message — export-dialog actions only fire after Phase 3 completes so missing state indicates corruption. The user MAY override the proposed default during the export ordering dialog; only the default itself is locked. This contract eliminates the LLM-judgment failure mode where the Consultant could invent an off-spec folder name (`presentation_v2`, `final_version`, etc.) instead of following the `<YYYY_MM_DD>_<shortened_title>` convention. See BUG-AUDIT-15.

**Amendment (BUG-AUDIT-70 / REQ-EXPORT-BOOTSTRAP-1).** `propose_presentation_folder_name` was deleted from `routing.py` by BUG-AUDIT-31 (which gutted the routing module). Its role as the folder-name computer is now fulfilled by `debrief_state.compute_presentation_folder_name(project_name, today=None)` per BC-10.9. The new helper extends the original algorithm with a date-prefix detection rule: if `project_name` already begins with a `YYYYMMDD`, `YYYY_MM_DD`, or `YYYY-MM-DD` shape followed by a separator or end-of-string, that leading date is normalized to `YYYY_MM_DD` form and today's date is NOT prepended (avoids double-dating). The prepare-time injection clause of BC-4.7c is void — `main_prepare` was also deleted by BUG-AUDIT-31. The folder name is now proposed by the export module's self-bootstrap path (BC-10.9) when `deck_state.presentations` is empty; the consultant may renegotiate the folder name with the user before dispatch but has no prepare-time injection to rely on.

**BC-4.8 Prepare no-unresolved-placeholders.** After `substitute_gate_placeholders`, the resulting string must contain no tokens matching the regex `\{[a-z_]+\}`. If any remain, `main_prepare` must exit code 4 with `Unresolved placeholder in gate prompt: {<name>}`.

**BC-4.9 qa_cycle_log.jsonl writer.** Only `update_state` writes to `output/qa_cycle_log.jsonl`. The QA agent and routing script must not write to this file.

**BC-4.10 Snapshot cleanup.** At red-green cycle exit (GREEN or EXHAUSTED), `update_state` must delete all snapshot files for the completed slug from `.debrief/snapshots/` per REQ-SLIDE-13. Snapshots for other slugs are left intact.

**BC-4.11 G1.3 figure selection to debrief_state.** `update_state` handling for G1.3 must write `selected_figures` to `debrief_state.json` directly (not to `gate_data.json`). The field value is either a list of integers or the string `"all"`.

**BC-4.12 Bundled reference globbing.** `assemble_task_prompt`, when assembling Stylist context, must glob `${CLAUDE_PLUGIN_ROOT}/references/reference-*.md` in alphabetical order and append any matches. In v1.1 this glob produces zero results; the behavior must be correct for both zero and non-zero match counts.

**BC-4.13 skill-prelude mode.** When `main_update_state` is invoked with `--skill-prelude`, it must write only the specified field assignments to `debrief_state.json` and exit 0. It must not validate against any gate's `valid_responses`.

**BC-4.14 qa_cycle_log.jsonl schema.** Every `qa_cycle_log.jsonl` entry MUST contain exactly these 7 fields per REQ-SLIDE-12: `slug` (str), `started_at` (ISO 8601), `completed_at` (ISO 8601), `iterations` (int), `final_status` (str: `"green"` or `"exhausted"` — lowercase per the canonical schema example in REQ-SLIDE-12), `tier1_failures_by_iteration` (list of lists), `tier2_warnings` (list). No additional fields. No per-iteration flat entries — each entry is a per-cycle summary. Sole writer: `update_state` (per BC-9.7).

**BC-4.15 Mandatory bundled-reference files for Stylist context.** `assemble_task_prompt`, when assembling Stylist context, MUST load these four files from `${CLAUDE_PLUGIN_ROOT}/references/` on every Stylist invocation: `paperbanana-diagram-style-distilled.md`, `paperbanana-plot-style-distilled.md`, `ai4vis-survey-distilled.md`, `preview_placeholder_content.md`. These are required per Section 22.8's Stylist always-loaded column. In addition, the growth-model glob (BC-4.12) appends any `reference-*.md` matches.

**BC-4.16 G3.2a MY INSTRUCTIONS payload mechanism.** When `update_state` processes the `G3.2a MY INSTRUCTIONS` response, it MUST: (1) prompt the user for revision instructions using the inline skill prompt mechanism (Section 24.30), (2) write `gate_data.json` with the canonical envelope format `{"gate_id": "G3.2a_oscillation_review", "data": {"my_instructions": "<user_text>"}}`, (3) reset `red_green_iteration` to 0, (4) transition to `production/red_green`. The next prepare cycle reads `gate_data.json`, validates `gate_id` via `consume_gate_data` (BC-4.7), injects the user's instructions into the Slide Maker's task prompt as a `## User Instructions` section, and deletes `gate_data.json` after use. This is a cross-cycle consumer per Section 24.20 and Section 24.21.

**BC-4.17 Snapshot iteration filename.** `update_state` MUST write red-green iteration snapshots using `<slug>_iter_<N>.html` where N is the current `red_green_iteration` value (1-indexed per REQ-SLIDE-5, NOT zero-padded). Range: 1–5. Example: first iteration writes `.debrief/snapshots/methodology_overview_iter_1.html`.

**BC-4.18 QA agent mandatory context load.** `assemble_task_prompt`, when assembling QA agent context, MUST load `${CLAUDE_PLUGIN_ROOT}/references/slide-qa-checklist.md` on every QA agent invocation per Section 22.8's QA agent always-loaded column. This is the craft-knowledge baseline for Tier 2 judgment. The Section 16 INV-*/VETO-* enumeration is separately baked into the agent's system prompt (per Section 24.2 lines 2827-2829) and is NOT loaded via this file path.

---

## Unit 5: Consultant Agent and Ledger

### Tier 2 — Signatures

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional


# These signatures represent the data contracts that the Consultant agent
# produces and consumes. The agent itself is implemented as agents/consultant.md.
# Python helpers that support the Consultant's file outputs are described below.


def write_slide_brief(
    project_root: Path,
    group_id: str,
    slug: str,
    title: str,
    content_goal: str,
    visual_approach: str,
    visual_pattern: str,
    rhetorical_role: str,
    design_invariants: list[str],
    user_recommendations: str,
    backup: bool = False,
) -> None:
    """
    Write a slide brief to .debrief/briefs/<group_id>_<slug>.json.
    Validates that rhetorical_role is in the allowed set.
    Writes atomically (write-to-tmp then rename).
    """
    ...


def write_group_manifest(
    project_root: Path,
    group_id: str,
    slide_slugs: list[str],
) -> None:
    """
    Write .debrief/briefs/<group_id>_MANIFEST.json atomically.
    Schema: {"group_id": str, "slide_count": int, "slugs": [str],
             "dispatched_at": "<ISO8601>"}.
    The G3.1 machine gate checks this file's existence and slide_count.
    dispatched_at is set to the current UTC ISO8601 timestamp at write time.
    """
    ...


def append_ledger_entry(
    project_root: Path,
    role: str,
    content: str,
    group_id: Optional[str] = None,
    slug: Optional[str] = None,
    event: Optional[str] = None,
) -> None:
    """
    Append a single JSON entry to ledger.jsonl.
    Schema: {"timestamp": str, "role": str, "content": str,
             "metadata": {"group_id": str|None, "slug": str|None, "event": str|None}}.
    Opens the file in append mode; does not read or truncate.
    """
    ...


def compact_ledger(project_root: Path) -> None:
    """
    Compact ledger.jsonl when entry count exceeds 100.
    Steps:
    1. Read all entries from ledger.jsonl.
    2. Write full ledger to ledger_compact_NNN.jsonl (NNN = 001, 002, ...).
    3. Write a single compaction summary entry to a new ledger.jsonl capturing:
       decisions made, slides approved, style choices locked, narrative direction.
    """
    ...


def validate_slide_brief(brief: dict) -> None:
    """
    Validate a slide brief dict against the REQ-CONSULT-5 schema.
    Raises ValueError with a descriptive message if any required field is missing
    or if rhetorical_role is not in the allowed set.

    Required fields: slug, title, content_goal, visual_approach, visual_pattern,
    rhetorical_role, design_invariants, user_recommendations, group_id.
    Allowed rhetorical_role values: hook, ethos, pathos, logos,
                                    synthesis, recap, transition.
    """
    ...
```

### Tier 3 -- Behavioral Contracts

**BC-5.1 Brief schema completeness.** Every slide brief written to `.debrief/briefs/` must contain all nine required fields from REQ-CONSULT-5. A brief missing `rhetorical_role` is invalid and must be rejected by `validate_slide_brief`.

**BC-5.2 Manifest atomicity.** `write_group_manifest` must write atomically. The G3.1 machine gate reads this file; a partial write could cause the gate to fire prematurely. The manifest is written AFTER all brief files for the group.

**BC-5.3 Manifest slide_count match.** The `slide_count` field in the manifest must equal `len(slide_slugs)` exactly. A mismatch triggers a routing error at G3.1.

**BC-5.4 Ledger append-only.** `append_ledger_entry` must open the file in append mode (`"a"`). It must never truncate or overwrite the ledger. Compaction is the only legitimate ledger-truncation operation. **BUG-AUDIT-60 / BUG-ST-c-3:** the ledger file lives at `project_root / "ledger.jsonl"` (NOT under `.debrief/`). This is the path documented in spec Section 3 layout tree, referenced by BC-11.10 (save copies from root) and project_claude.md (discovery-resume reads from root). All writers — `debrief_state.append_ledger_entry`, `debrief_state._auto_append_ledger`, `ledger.append_ledger_entry`, and `ledger.compact_ledger` — MUST write to this canonical path. Compaction archives (`ledger_compact_NNN.jsonl`) also live at project root alongside the primary ledger.

**BC-5.5 Compaction trigger.** `compact_ledger` is triggered when the ledger entry count exceeds 100. The trigger check occurs after each append. Compaction must produce exactly one summary entry in the new ledger.

**BC-5.6 Compaction archive naming.** The archived full ledger is named `ledger_compact_NNN.jsonl` where NNN is zero-padded to 3 digits and increments monotonically. If `ledger_compact_001.jsonl` already exists, the next is `ledger_compact_002.jsonl`.

**BC-5.7 No agent writes state files directly (BUG-AUDIT-62 / REQ-AGENT-STATE-1 extension).** Neither the Consultant nor any subagent — stylist, slide-maker, visual-qa, bug-diagnostic — may write to `deck_state.json` or `debrief_state.json` via the Write tool. All state changes flow through `write_debrief_state` / `write_deck_state` (via `python -m debrief.debrief_state update`, `python -m debrief.utility_skills promote_style_draft`, or the equivalent CLI entry points), so that hash recomputation, atomic write, and auto-ledger remain invariant. Violation of this contract causes state desynchronization — typically a `WARNING: debrief_state.json hash mismatch — recomputed` on the next read. Each agent card (`stylist.md`, `slide-maker.md`, `visual-qa.md`, `bug-diagnostic.md`) MUST contain an explicit prohibition phrase (e.g., "MUST NOT write to `deck_state.json` or `debrief_state.json` directly"). A regression test parses each agent card and asserts the prohibition is present.

**BC-5.8 Group ID monotonic labeling.** Main slide group IDs use `group_01`, `group_02`, ... in monotonically increasing order. Backup group IDs use `backup_01`, `backup_02`, .... No gaps, no reuse.

**BC-5.9 Slug announcement.** Before dispatching each brief, the Consultant must print a clearly labeled line: `Slug: <slug>`. This appears in the conversation before any brief file is written.

**BC-5.10 Escalation output.** When a structural change is requested during the Slide Maker's context, the Slide Maker must output the literal string `ESCALATE_TO_CONSULTANT` as its response. The Slide Maker must not attempt the structural change itself.

**BC-5.11 paper_analyzer invocation.** When the user provides a paper PDF path during discovery, the Consultant invokes `python -m debrief.paper_analyzer --pdf <path> --paper-slug <slug> --project-root <path>` via Bash. The Consultant does not import `fitz` directly. For the `journal_club` archetype, `agents/consultant.md` Step 5 MUST contain the literal substring `Which paper(s) would you like to present? Give me the file path(s).` (per spec REQ-CONSULT-18 line 1245 and BUG-AUDIT-88) and the briefing MUST NOT proceed past Step 5 until paper paths are supplied — the paper PDF is the primary asset for journal_club. A regression test parses the agent card and asserts the imperative substring is present.

**BC-5.12 style_analyzer invocation.** When the user provides a reference file path during discovery, the Consultant invokes `python -m debrief.style_analyzer --reference <path> --project-root <path>` via Bash. The Consultant does not call any VLM; the VLM derivation happens on the next Stylist routing cycle.

**BC-5.13 Slug naming enforcement.** The Consultant's slide brief MUST assign a slug matching `^[a-z][a-z0-9_]{0,49}$` that does not end with `_`, per the Section 17.2 slug naming convention. The `write_slide_brief` function MUST validate the slug against this regex and raise `ValueError` if it fails. The slug MUST NOT already exist in `deck_state.json.slides` (including discarded slides — slugs are permanently consumed).

**BC-5.14 Group ID format enforcement.** `write_group_manifest` MUST validate that `group_id` matches `^(group|backup)_\d{2}$` per Section 17.2. The counter MUST be 1-indexed and monotonically increasing within each prefix class. The Consultant's group-planning prompt MUST include the next available group_id as a pre-computed field (the prepare module reads `completed_groups` from `debrief_state.json` to determine the next counter value).

**BC-5.15 Alternative-dispatch prompt grammar (BUG-AUDIT-66 / REQ-CONSULT-ALT-DISPATCH-1..3).** `agents/consultant.md` MUST contain a dedicated section titled exactly `## Alternative Dispatch Prompts` documenting the decision rule and the deterministic prompt text for two commands:

1. **`/debrief:export`** — when the user's turn does NOT include `--include-backup` AND `count([s for s in deck_state.slides if s.status=="approved" and s.backup]) > 0`, the consultant MUST emit the fixed EXPORT prompt (defined verbatim in the agent card) and await the user's reply before dispatching. If the flag is present OR zero approved backups exist, dispatch silently with defaults.

2. **`/debrief:handout`** — based on which flags are missing from the user's turn:
   - If neither `--mode` nor `--include-backup` is supplied AND approved backups exist: emit the COMBINED prompt asking both questions.
   - If neither is supplied AND zero approved backups exist: emit the MODE-ONLY prompt.
   - If `--mode` is supplied but `--include-backup` is not AND approved backups exist: emit the BACKUP-ONLY prompt.
   - If both flags are supplied, or the missing flag is irrelevant (backup question with zero backups): dispatch silently.

3. **`/debrief:present` and `/debrief:script`** MUST NEVER emit these prompts. Per BUG-AUDIT-65 they always carry the full deck.

The agent card MUST also include a dispatch-mapping table translating natural-language replies (`main only`, `include backup`, `2up`, `4up`, `2up, include backup`, etc.) into CLI flag combinations. A regression test parses the agent card and asserts (a) the `## Alternative Dispatch Prompts` section exists, (b) the canonical prompt substrings are present verbatim (drift guard), (c) the decision rule explicitly names the four case branches for handout + the two for export, (d) `/debrief:present` and `/debrief:script` are explicitly excluded from the prompting behavior. Drift from the fixed prompt text is a CRITICAL regression.

**BC-5.16 deck_brief.md canonical structure and consultant discipline (BUG-AUDIT-74 / REQ-CONSULT-DECK-BRIEF-1).** `agents/consultant.md` MUST contain a dedicated section titled exactly `## Deck Brief Maintenance` that codifies five obligations the consultant must enforce on `deck_brief.md`:

1. **Canonical section set.** The brief uses exactly these top-level sections, in this order: `## Audience` (with nested `### Roster` YAML sub-block), `## Room composition`, `## Intent`, `## Duration`, `## Prior decisions`, `## Open questions`, `## Content Signals`. Sections MAY be absent during discovery (they are added as the matching information surfaces) but MUST NOT be replaced with alternative headings. Additional top-level `##` sections not in the canonical set are forbidden — the set is closed so a scanning reader locates any fact deterministically.

2. **Machine-readable audience roster.** Inside `## Audience`, a fenced ```yaml ``` block MUST carry an `audience:` list. Each entry MUST include keys `name` (string) and `role` (string). Recommended keys: `location`, `attendance` (one of `in-person` / `remote` / `remote (Teams)` etc.), `notes`. The roster is the machine-readable anchor; the `## Audience` prose above it is free-form narrative that complements but does not replace the roster.

3. **Write-through.** *(Superseded by BUG-AUDIT-78 / BC-5.19.)* The original clause required the consultant to append every fact in the same turn it was learned. As of BUG-AUDIT-78, `deck_brief.md` is owned exclusively by the rewrite agent (BC-5.19) — the consultant does NOT write to it. Same-turn capture is now provided mechanically by the `PreCompact` hook firing the rewrite agent against `.debrief/dialog.jsonl` (BC-2.17). The canonical-structure clauses (1) and (2) above remain in force; only the writer changes. Cycle 2 implementation lands in Phase 4 of `spec/memory_architecture_rfc.md` §13.

4. **On-session-start mandatory read.** After loading `archetypes.json` and `deck_state.json`, the consultant MUST read `deck_brief.md` in full if the file exists, regardless of `sub_phase`. This makes the brief the recovery source of truth across every session boundary — fresh start, resume, or re-open.

5. **Post-compaction audit.** When the consultant detects context loss (summarization event, resume from `.debrief/` state, user challenge implying recall failure, explicit inability to recall), it MUST stop, re-read `deck_brief.md` in full, diff against in-context memory, surface the loss to the user explicitly (suggested phrasing: *"I'd lost [items] from my working memory — re-reading `deck_brief.md` now."*), and proceed only from the brief's authoritative contents. Silent proceeding with degraded state is a protocol violation.

Regression tests in `tests/regressions/test_bug_audit_74_deck_brief_discipline.py` enforce: the `## Deck Brief Maintenance` section exists; the seven canonical headings appear in the specified order inside an example block; the YAML example includes `name` and `role` keys; the three discipline rules are each documented with marker phrases (write-through, on-session-start, post-compaction audit). See REQ-CONSULT-DECK-BRIEF-1 and BUG-AUDIT-74.

---

## Unit 6: Style Compiler

### Tier 2 — Signatures

```python
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any


# Canonical CSS custom-property name mapping.
# This dict is the single source of truth for the mapping.
# The Slide Maker reads these variable names from style_guide.md.
# Drift between this mapping and style_guide.md documentation is a bug.
CSS_PROPERTY_MAP: dict[str, str] = {
    "colors.primary": "--color-primary",
    "colors.secondary": "--color-secondary",
    "colors.accent": "--color-accent",
    "colors.background": "--color-background",
    "colors.text_primary": "--color-text-primary",
    "colors.text_secondary": "--color-text-secondary",
    "colors.code_background": "--color-code-background",
    "colors.border": "--color-border",
    "typography.heading_font_family": "--font-heading-family",
    "typography.body_font_family": "--font-body-family",
    "typography.code_font_family": "--font-code-family",
    "typography.heading_size_base": "--font-heading-size-base",
    "typography.body_size_base": "--font-body-size-base",
    "typography.heading_weight": "--font-heading-weight",
    "typography.body_weight": "--font-body-weight",
    "typography.line_height": "--font-line-height",
    "spacing.margin_pct": "--spacing-margin-pct",
    "spacing.gap": "--spacing-gap",
    "spacing.section_gap": "--spacing-section-gap",
    "layout.slide_width": "--layout-slide-width",
    "layout.slide_height": "--layout-slide-height",
    "layout.column_gap": "--layout-column-gap",
    "data_viz.primary_colormap": "--viz-primary-colormap",
    "data_viz.axis_color": "--viz-axis-color",
    "data_viz.grid_color": "--viz-grid-color",
    "data_viz.annotation_color": "--viz-annotation-color",
}


def compile_style(
    style_config_path: Path,
    output_css_path: Path,
) -> None:
    """
    Entry point for: python -m debrief.style_compiler <config_path> <output_path>

    Read style_config_path, validate required top-level keys, generate CSS
    custom properties, write to output_css_path.

    Exit codes:
      0 — success
      1 — invalid JSON, missing required keys, or file I/O failure
      3 — usage error (wrong number of positional arguments)
    """
    ...


def parse_style_config(config_path: Path) -> dict[str, Any]:
    """
    Read and parse style_config_path as JSON.
    Validate that all required top-level keys are present:
    colors, typography, spacing, layout, data_viz, constraints, provenance.
    Raises ValueError with a descriptive message if any required key is missing.
    """
    ...


def generate_css_root_block(config: dict[str, Any]) -> str:
    """
    Generate the :root { ... } CSS block from the config dict.

    For each leaf value, resolve its dot-path key against CSS_PROPERTY_MAP.
    If found, emit '--<mapped-name>: <value>;'.
    If not found, apply the fallback convention:
      dot-separated path -> '--<seg1>-<seg2>-...' with underscores -> hyphens.
    Returns the full :root block as a string.
    """
    ...


def flatten_config(
    config: dict[str, Any],
    prefix: str = "",
) -> dict[str, Any]:
    """
    Recursively flatten nested config dict into dot-path -> value pairs.
    e.g. {"colors": {"primary": "#fff"}} -> {"colors.primary": "#fff"}
    Skips the 'constraints' and 'provenance' top-level keys
    (they are not emitted as CSS variables).
    """
    ...


def path_to_css_var(dot_path: str) -> str:
    """
    Apply fallback CSS variable naming convention for paths not in CSS_PROPERTY_MAP.
    Convert dot-path to '--<seg1>-<seg2>-...' with underscores replaced by hyphens.
    e.g. 'my_section.some_value' -> '--my-section-some-value'
    """
    ...
```

### Tier 3 -- Behavioral Contracts

**BC-6.1 Strict mapping table is canonical.** The 26 entries in `CSS_PROPERTY_MAP` are pinned and must not be modified without a coordinated change to `style_guide.md` documentation and all Slide Maker prompts that reference CSS variable names. Any discrepancy between `CSS_PROPERTY_MAP` and the variable names documented in `style_guide.md` is a blocking bug.

**BC-6.2 All mapped keys emitted.** For a `style_config.json` that contains all 26 mapped dot-paths, all 26 corresponding `--custom-property: value;` declarations must appear in the `:root {}` block of the output CSS. No mapped key may be silently omitted.

**BC-6.3 Fallback convention for unmapped paths.** For any leaf path not in `CSS_PROPERTY_MAP`, the compiler emits a CSS variable using the fallback convention: dots become hyphens, underscores become hyphens, prefix `--`. This ensures no config field is silently dropped.

**BC-6.4 constraints and provenance excluded.** The `constraints` and `provenance` top-level keys must not generate any CSS variables. They are structural metadata, not visual properties.

**BC-6.5 :root wrapper.** All custom properties must be emitted inside a single `:root { ... }` block. No custom properties may appear outside this block.

**BC-6.6 Exit code 3 on wrong argument count.** If invoked with fewer than 2 or more than 2 positional arguments, the compiler must print a usage message to stderr and exit with code 3.

**BC-6.7 Exit code 1 on invalid JSON.** If the config file contains invalid JSON (even after `json.loads` attempt), the compiler must print the parse error to stderr and exit with code 1. It must not attempt `json_repair` (the style compiler has no conda-env dependency beyond stdlib).

**BC-6.8 Exit code 1 on missing required key.** If any of `colors`, `typography`, `spacing`, `layout`, `data_viz`, `constraints`, `provenance` is absent from the top-level config, the compiler must print `ERROR: Missing required key: <key>` to stderr and exit with code 1.

**BC-6.9 No state file reads.** The style compiler must not read `deck_state.json`, `debrief_state.json`, or any other pipeline state file. It is a pure read-transform-write function.

**BC-6.10 No Playwright dependency.** The style compiler must not import playwright, launch any browser, or take any screenshot.

**BC-6.11 Canonical template ships with the plugin.** The plugin MUST ship a bundled starting template at `templates/style_config.json` (workspace path `src/unit_1/templates/style_config.json`; delivered path `debrief/templates/style_config.json`). The template MUST (a) satisfy `parse_style_config` — i.e., contain all seven required top-level keys (`colors`, `typography`, `spacing`, `layout`, `data_viz`, `constraints`, `provenance`) — and (b) contain a value for every one of the twenty-six dot-paths in `CSS_PROPERTY_MAP`, so `flatten_config(template)` produces a superset of `CSS_PROPERTY_MAP.keys()`. The template's `constraints.permitted_diagram_types` MUST be a non-empty list drawn from the set allowed by spec §24.16. The template's `provenance` MUST be an object (MAY be empty but MUST be a dict, not null or missing). Calling `compile_style(template_path, <tmp>)` MUST succeed and produce a non-empty `:root { ... }` CSS block. The Stylist loads this template as the starting skeleton during the style dialog per REQ-STYLE-4 and BC-1.3c; the template exists to eliminate the BUG-AUDIT-13 failure mode where the Stylist invented an incompatible `palette/geometry/components` schema. A regression test in `tests/regressions/test_bug_audit_13_stylist_schema.py` enforces every part of this contract.

**BC-6.14 Font loader emission (BUG-AUDIT-71 / REQ-STYLE-FONT-LOADER-1).** `style_engine.compile_style` MUST prepend a single `@import url('https://fonts.googleapis.com/css2?...&display=swap');` line to the compiled CSS when one or more Google-Fonts families are referenced in the config's typography section. Emission grammar:

- **Family discovery.** Scan `typography.heading_font_family`, `typography.body_font_family`, and `typography.code_font_family` (in that order). For each field, split on `,` and take the first element as the primary family; subsequent comma-separated entries are browser fallbacks and MUST NOT produce a loader. Normalize the primary family by stripping leading/trailing whitespace and matched surrounding quotes (single or double), then lowercasing.
- **Allowlist match.** Compare the normalized family against `_GOOGLE_FONTS_ALLOWLIST` (a module-level dict mapping lowercased family names → Google Fonts CSS2 URL fragments of the form `Inter:wght@400;600;700`). Families not present in the allowlist MUST NOT produce a loader — they are assumed system fonts and resolved by the browser locally.
- **URL assembly.** When one or more families match, assemble a single `@import` URL whose query string has one `family=<fragment>` parameter per matched family (joined by `&`, in the discovery order established above), followed by `&display=swap` as the final parameter. The URL base MUST be `https://fonts.googleapis.com/css2`. The resulting line is `@import url('<full-url>');` and is prepended to the compiled CSS with a single `\n` separator before the `:root` block. When no families match, the compiled CSS MUST contain no `@import` line and MUST be byte-identical to the pre-BUG-AUDIT-71 output for the same input.
- **Placement.** The `@import` line lives in `compile_style`, NOT in `generate_css_root_block`, so `generate_css_root_block`'s pure-function invariants (nothing before `:root`, one `:root` only, no `--` outside `:root`) remain intact and BC-6.5-adjacent unit tests continue to hold.
- **Allowlist and weight lists are implementation detail.** New Google Fonts can be added by extending the dict without changing this contract; weight lists within a fragment MAY be tuned over time. Only the emission contract (when to emit, where to emit, URL shape) is normative.

Regression tests in `tests/regressions/test_bug_audit_71_font_loader.py` cover allowlist extraction (template config → both `inter` and `fira code` detected; system-only configs → empty; mixed quotes; duplicate families deduped), URL assembly (empty → empty string; single and multi-family URLs; `display=swap` always present), and the `compile_style` integration path (`@import` appears before `:root`; no `@import` when no allowlisted family is configured). See REQ-STYLE-FONT-LOADER-1 and BUG-AUDIT-71.

---

## Unit 7: Style Dialog

### Tier 2 — Signatures

```python
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from typing import Optional


# --- debrief.style_analyzer ---

def main_style_analyzer(reference: Path, project_root: Path) -> None:
    """
    Entry point for:
        python -m debrief.style_analyzer --reference <path> --project-root <path>

    Dispatch to the correct modality adapter based on the reference path extension
    or directory status. Write images to assets/reference/slides/. Write metadata
    (PPTX only) to .debrief/draft/analyzer_metadata.json.

    Exit codes:
      0 — success
      1 — unsupported reference type or reference file not found
      2 — conda env corruption (any required import fails)
      3 — usage error (missing or invalid arguments)
    """
    ...


def adapt_pptx(reference: Path, project_root: Path) -> None:
    """
    Convert a .pptx reference to a PNG batch using LibreOffice headless.
    Cap at 10 slides (first + last + 8 middle).
    Also extract theme colors, font families, font sizes, slide dimensions
    via python-pptx and write to .debrief/draft/analyzer_metadata.json.
    Copy the reference file to assets/reference/<filename>.
    120-second timeout on soffice invocation.
    """
    ...


def adapt_pdf(reference: Path, project_root: Path) -> None:
    """
    Convert a .pdf reference to a PNG batch using PyMuPDF at 150 DPI.
    Cap at 10 pages (first + last + 8 middle).
    Set heuristic flag in output if PDF > 50 pages (paper-vs-deck warning).
    Copy the reference file to assets/reference/<filename>.
    """
    ...


def adapt_html_file(reference: Path, project_root: Path) -> None:
    """
    Render a single .html reference to one PNG using Playwright.
    wait_until='networkidle' plus 2-second explicit delay.
    Screenshot size: 1920x1080.
    Copy the reference file to assets/reference/<filename>.
    """
    ...


def adapt_html_dir(reference: Path, project_root: Path) -> None:
    """
    Render up to 10 .html files from a reference directory using Playwright.
    Selection: first + last + 8 middle in alphabetical order.
    Same wait strategy as adapt_html_file.
    Copy the reference directory to assets/reference/<dirname>/.
    """
    ...


def sample_slides(total: int, cap: int = 10) -> list[int]:
    """
    Given total slide/page count, return 0-based indices of slides to render.
    If total <= cap: return list(range(total)).
    Otherwise: first, last, and (cap-2) uniformly sampled from the middle.
    Result always has exactly min(total, cap) elements, with no duplicates,
    in ascending order.
    """
    ...


# --- debrief.style_guide_generator ---

def main_style_guide_generator(project_root: Path) -> None:
    """
    Entry point for:
        python -m debrief.style_guide_generator --project-root <path>

    Read bundled reference documentation, draft style_config.json (if present),
    and derived style guide (if present). Synthesize a first-draft style_guide.md
    at .debrief/draft/style_guide.md using anti-prescriptive language.
    No LLM calls, no subprocess spawning, no Playwright.
    """
    ...


# --- debrief.preview_renderer ---

def main_preview_renderer(
    project_root: Path,
    input_dir: Path,
    output_dir: Path,
) -> None:
    """
    Entry point for:
        python -m debrief.preview_renderer --project-root <path>
            --input-dir <dir> --output-dir <dir>

    Open one sync_playwright() session per invocation. Render each .html file
    in input_dir to a 1920x1080 PNG in output_dir. Wait for KaTeX/Mermaid/rough.js
    before screenshot. Close session before returning.

    If total render time > 60 seconds, print a timeout warning and exit code 1.
    Target: complete in < 30 seconds for 3 preview slides.
    """
    ...


def render_html_to_png(
    page: "playwright.sync_api.Page",
    html_path: Path,
    output_path: Path,
) -> None:
    """
    Navigate to file://<html_path>, wait for networkidle plus 2-second delay,
    take a 1920x1080 screenshot, save to output_path.
    Raises RuntimeError on navigation or screenshot failure.
    """
    ...
```

### Tier 3 -- Behavioral Contracts

**BC-7.1 style_analyzer does not call VLM.** `main_style_analyzer` and all modality adapters must not import or invoke any LLM/VLM SDK. The derivation of `.debrief/draft/derived_style_guide.md` is the Stylist agent's responsibility on the next routing cycle (P-BP-14).

**BC-7.2 Playwright per-invocation context.** `adapt_html_file`, `adapt_html_dir`, and `main_preview_renderer` must each open their own `sync_playwright()` context per invocation. No Playwright context may be shared across invocations or stored as a module-level global.

**BC-7.3 LibreOffice isolation.** The PPTX adapter must invoke `soffice` with `-env:UserInstallation=file:///<tmp-profile>` to prevent profile lock collisions when multiple invocations run concurrently or sequentially.

**BC-7.4 LibreOffice 120-second timeout.** The `soffice` subprocess invocation must use a 120-second timeout. If the timeout elapses, the adapter kills the process, exits with code 1, and prints `ERROR: LibreOffice conversion timed out after 120 seconds.`

**BC-7.5 PDF > 50 pages warning.** If a PDF reference has more than 50 pages, `adapt_pdf` must set a flag (e.g., `paper_detected: true`) in its output or in `analyzer_metadata.json` so the G1.2 gate prompt can include the paper-vs-deck warning.

**BC-7.6 sample_slides determinism.** Given the same `total` and `cap`, `sample_slides` always returns the same indices. The result is in ascending order with no duplicates. For `total <= cap`, it returns `list(range(total))` exactly.

**BC-7.7 Env corruption exit code 2.** If any of `playwright`, `fitz`, `pptx` (for PPTX adapter), or `subprocess` (for soffice) cannot be imported at entry, `main_style_analyzer` must exit with code 2 and the standardized Section 9.3.1 message. Missing `soffice` binary detected at runtime also exits 2.

**BC-7.8 Preview slides exempt from QA.** The PostToolUse hook fires on writes to `slides/` only. Writes to `.debrief/draft/preview_slides/` must not trigger the QA hook. The preview_renderer writes to `.debrief/draft/preview_images/` (PNG output), not `slides/`.

**BC-7.9 style_guide_generator no external calls.** `main_style_guide_generator` must make no network calls, no subprocess calls, and no LLM API calls. It is a pure text synthesis function operating on local files.

**BC-7.10 preview_renderer env check and session closure.** `main_preview_renderer` must check `importlib.util.find_spec('playwright')` at entry per Section 24.35 Category 4.3. If unavailable, exit with code 2 and the standardized Section 9.3.1 env-corruption error. The Playwright session must be closed in a `finally` block to prevent zombie browser processes even if an exception occurs during rendering.

**BC-7.11 Draft lifecycle — STYLE REVISE.** On G2.1 `STYLE REVISE`, `update_state` removes `.debrief/draft/` recursively. A subsequent `/debrief:style` invocation must find no residual draft files.

**BC-7.12 Draft lifecycle — REGENERATE PREVIEWS.** On G2.1 `REGENERATE PREVIEWS`, `update_state` removes only `.debrief/draft/preview_slides/` and `.debrief/draft/preview_images/`. Style config and derived guide files are retained. The `gate_data.json` contains `{"regenerate_previews": true}` for the next prepare cycle.

---

## Unit 8: Slide Agent

### Tier 2 — Signatures

```python
from __future__ import annotations
import re
import sys
from pathlib import Path
from typing import Optional


# --- debrief.asset_ingest ---

def main_asset_ingest(src: Path, slug: str, project_root: Path) -> None:
    """
    Entry point for:
        python -m debrief.asset_ingest --src <path> --slug <slug>
            --project-root <path>

    Copy src to project_root/assets/images/<slug>_<src.name> atomically.
    Exit 0 on success.
    Exit 1 on source-not-found or copy failure.
    Exit 3 on usage error.
    Does NOT modify deck_state.json.
    """
    ...


def ingest_image(src: Path, slug: str, project_root: Path) -> Path:
    """
    Copy src to assets/images/<slug>_<src.name> atomically.
    Returns the destination path.
    Raises FileNotFoundError if src does not exist.
    Raises OSError on copy failure.
    """
    ...


# --- debrief.math_renderer ---

def main_math_renderer(mode: str, latex_input: str) -> None:
    """
    Entry point for:
        python -m debrief.math_renderer --mode <inline|display>
            --input <latex_string>

    Validate latex_input for surface well-formedness.
    Emit the HTML wrapper to stdout.
    Exit 0 on well-formed input.
    Exit 1 on malformed input (message on stderr).
    """
    ...


def render_math_html(mode: str, latex_input: str) -> str:
    """
    Produce the KaTeX HTML wrapper for the given LaTeX string.

    For inline mode:
        <span class="katex-src" data-mode="inline">{escaped}</span>
    For display mode:
        <div class="katex-src" data-mode="display">{escaped}</div>

    The escaped value is the LaTeX string with HTML special characters escaped.
    """
    ...


def validate_latex(latex_input: str) -> Optional[str]:
    """
    Surface well-formedness check on a LaTeX string.
    Returns None if the input is well-formed.
    Returns an error message string if malformed.

    Checks (in order):
    1. Non-empty: empty string -> 'LaTeX input is empty.'
    2. No null bytes: presence of \\x00 -> 'LaTeX input contains null bytes.'
    3. Brace balance: count of '{' must equal count of '}' -> 'Unbalanced braces.'
    4. Environment balance: every \\begin{X} has a matching \\end{X}
       -> 'Unmatched \\begin{<env>}.'
    """
    ...


def escape_html(text: str) -> str:
    """
    Escape HTML special characters in text: &, <, >, ", '.
    Returns the escaped string.
    """
    ...
```

### Tier 3 -- Behavioral Contracts

**BC-8.1 Slide Maker style-guide-driven path only.** There is no exemplar library, no `exemplars/` directory, and no exemplar-availability branch. The single generation path reads `style_guide.md`, `style_config.json`, the slide brief, and Content Signals. Any code branch referencing exemplar selection is a bug.

**BC-8.2 approval_<slug>.json written at every iteration.** The Slide Maker must write `.debrief/approval_<slug>.json` at the end of EVERY red-green iteration, not only on GREEN. The file always reflects the current best-known-good state. The schema must include `slug`, `title`, `content_summary` (max 500 chars), `visual_approach`, `design_choices`.

**BC-8.3 Slide HTML self-contained.** Each `slides/<slug>.html` must be a self-contained HTML5 file. It must reference `../assets/style.css` for styles. It must reference vendor scripts from `../assets/vendor/`. It must contain no inline `<style>` blocks that override locked CSS custom properties (INV-06).

**BC-8.4 Tier 2 visual-QA dispatch (BUG-AUDIT-17, amended BUG-AUDIT-59 / BUG-ST-5).** The Tier 2 VLM review (visual-qa) is dispatched by the **consultant**, not by the slide-maker. This is a platform constraint: Claude Code does not surface the `Task` tool to nested subagents (consultant → slide-maker → visual-qa fails with "Task tool is not available").

The architecture is now:

1. **slide-maker** runs Tier 1 qa_checker via Bash (explicit call, not hook). Returns terminal status with Tier 1 result summary.
2. **consultant** reads slide-maker's return, dispatches visual-qa via `Task` with `subagent_type: "visual-qa"`. Visual-qa reads the Tier 1 qa_log.jsonl entry, runs Tier 2 + veto checks, and appends a `tier: "2_merged"` entry.
3. **consultant** reads the Tier 2 merged entry and presents the GREEN/RED gate prompt to the user.

The `agents/slide-maker.md` MUST satisfy:
1. **Frontmatter.** The YAML frontmatter `tools` list MUST include `Task` (retained for forward compatibility, even though the current platform does not surface it in nested contexts).
2. **System prompt body — QA Dispatch section.** The section MUST instruct the slide-maker to run Tier 1 qa_checker explicitly via Bash, then return. It MUST NOT instruct the slide-maker to dispatch visual-qa via Task (that is the consultant's responsibility per BUG-AUDIT-59).

The `agents/consultant.md` MUST contain a "Tier 2 QA Dispatch" section instructing the consultant to dispatch visual-qa after every slide-maker return.

A regression test at `tests/regressions/test_bug_audit_17_qa_dispatch.py` asserts structural properties of slide-maker.md including the QA Dispatch section and BUG-AUDIT-17/BC-8.4 citation. The test was updated for BUG-AUDIT-59 to reflect the consultant-as-dispatcher architecture.

**BC-8.4 asset_ingest atomic copy.** `ingest_image` must write to a `.tmp` sibling and rename atomically. If the source does not exist, it raises `FileNotFoundError` (which `main_asset_ingest` catches and converts to exit code 1). The destination path convention is `<slug>_<src.name>` with no additional path manipulation.

**BC-8.5 math_renderer no KaTeX allowlist.** `validate_latex` must not maintain an allowlist of KaTeX commands. Surface checks only: brace balance, environment balance, non-empty, no null bytes. Unknown commands pass validation and are left for the browser's KaTeX runtime to report.

**BC-8.6 math_renderer inline script.** Each slide HTML file that includes KaTeX math must contain an initialization `<script>` block that calls `katex.renderMathInElement()` on all `.katex-src` elements at browser load time. The math_renderer module generates only the element wrapper; the initialization script is the Slide Maker's responsibility.

**BC-8.7 Escalation literal string.** When the Slide Maker must escalate a structural change, it outputs the exact string `ESCALATE_TO_CONSULTANT` with no surrounding text or markup.

**BC-8.8 Silence rule.** The Slide Maker must not emit any intermediate status messages to the user during the red-green cycle. It communicates with the user only when presenting the final result after the cycle completes.

**BC-8.9 rhetorical_role visual treatment.** The Slide Maker must read the `rhetorical_role` field from the slide brief and apply the visual treatment specified in `style_guide.md`'s "Rhetorical Role Styling" section. Hook slides must use large typography and minimal text. Logos slides must prioritize data exhibits. Pathos slides must prioritize photographs or emotional imagery. Ethos slides must emphasize citations and methodology callouts.

**BC-8.10 Viewport-fit script in every slide (BUG-AUDIT-72 / REQ-SLIDE-VIEWPORT-FIT-1).** The Slide Maker MUST include in every `slides/<slug>.html` a single inline `<script>` element whose opening tag carries the attribute `data-debrief-viewport-fit="v1"`. The canonical script block lives verbatim in `agents/slide-maker.md`'s Constraints section as the authoritative specimen. The script MUST:

- On `DOMContentLoaded` (or immediately, if the document is already interactive) compute `scale = min(window.innerWidth / 1920, window.innerHeight / 1080)` and translation offsets `tx = (innerWidth - 1920*scale) / 2`, `ty = (innerHeight - 1080*scale) / 2`.
- When `scale === 1 && tx === 0 && ty === 0`, early-return after clearing `transform` and `transformOrigin` on the `.slide` element — guarantees no stacking-context / transform side-effect on the 1920×1080 Playwright viewport used by screenshot and export pipelines.
- Otherwise, apply `transformOrigin: '0 0'` and `transform: translate(<tx>px, <ty>px) scale(<scale>)` to the first `.slide` element.
- Re-run on `window.resize`.

The script MUST be inline (no `src=` attribute) so INV-07 (no external URL references) continues to hold. The marker attribute on the opening tag is the contract primitive; the script body may evolve without breaking detection. Version suffix (`v1`) lets future revisions of the contract (`v2`, `v3`) be detected unambiguously. See BC-9.3b (INV-25 enforcement) and BUG-AUDIT-72.

**BC-9.3b Viewport-fit invariant (BUG-AUDIT-72 / REQ-SLIDE-VIEWPORT-FIT-1 / INV-25).** `qa_checker.run_programmatic_checks` MUST run a new invariant `INV-25` whose implementation is `check_viewport_fit_script(slide_path)`. The check reads the slide HTML and searches for a `<script>` opening tag carrying the attribute `data-debrief-viewport-fit="v1"`. Detection is marker-based (case-insensitive, tolerates single or double quotes around the attribute value, tolerates arbitrary whitespace and other attributes around the marker); the script body is NOT checked. On marker absence, INV-25 emits a `QAFailure` whose `revision_instruction` points the slide-maker at `agents/slide-maker.md`'s canonical block. INV-25 is a SOFT blocker — it participates in the red-green cycle like any Tier-1 invariant and MUST NOT flip the `veto` flag. INV-25 MUST appear in the `checks_run` enumeration emitted by `main_qa_checker`. See REQ-SLIDE-VIEWPORT-FIT-1 and BUG-AUDIT-72.

---

## Unit 9: QA System

### Tier 2 — Signatures

```python
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any, Optional


# QA check result types
QAFailure = dict[str, str]   # {"invariant": str, "description": str, "revision_instruction": str}
QAWarning = dict[str, str]   # {"invariant": str, "description": str, "revision_instruction": str}


def main_qa_checker(
    slide_path: Path,
    screenshot_path: Path,
    project_root: Path,
) -> None:
    """
    Entry point for:
        python -m debrief.qa_checker --slide-path <path>
            --screenshot-path <path> --project-root <path>

    Open own sync_playwright() context per invocation.
    Render slide HTML, take screenshot, save to screenshot_path.
    Run all programmatic invariant checks in tiered order.
    Output JSON result to stdout.

    Exit codes:
      0 — result on stdout (may include failures)
      1 — generic failure (Playwright crash, file not found)
      2 — conda env corruption (playwright unavailable)
      3 — usage error
    """
    ...


def run_programmatic_checks(
    slide_path: Path,
    screenshot_path: Path,
    style_config: dict[str, Any],
    page: "playwright.sync_api.Page",
) -> tuple[list[QAFailure], list[QAWarning]]:
    """
    Run all programmatic invariant checks assigned to qa_checker.py:
    INV-04, INV-06, INV-07, INV-08, INV-10, INV-12, INV-13, INV-14,
    INV-15, INV-16, INV-17, INV-19, INV-20, INV-22, INV-23, INV-24.

    Returns (failures, warnings) tuple. Failures trigger RED; warnings do not.
    """
    ...


def check_contrast(page: "playwright.sync_api.Page") -> Optional[QAFailure]:
    """
    INV-04: Compute WCAG contrast ratio from computed background/foreground colors
    using the WCAG 2.1 relative luminance formula.
    Returns a QAFailure if contrast ratio < 4.5:1, else None.
    """
    ...


def check_no_inline_styles(slide_path: Path) -> Optional[QAFailure]:
    """
    INV-06: Verify slide HTML contains no inline style= attributes that would
    override locked CSS custom properties. Returns QAFailure if found, else None.
    """
    ...


def check_no_external_requests(slide_path: Path) -> Optional[QAFailure]:
    """
    INV-07: Verify slide HTML contains no src= or href= referencing http:// or
    https:// URLs. Returns QAFailure if found, else None.
    """
    ...


def check_aspect_ratio(
    page: "playwright.sync_api.Page",
    style_config: dict[str, Any],
) -> Optional[QAFailure]:
    """
    INV-08: Verify rendered slide matches the 16:9 aspect ratio defined in
    layout.slide_width / layout.slide_height. Tolerance: ±1 pixel.
    Returns QAFailure if mismatch, else None.
    """
    ...


def check_permitted_libraries(
    slide_path: Path,
    permitted: list[str],
) -> Optional[QAFailure]:
    """
    INV-10: Read constraints.permitted_diagram_types from style_config.json.
    Verify slide HTML only references permitted diagram libraries.
    Returns QAFailure if a non-permitted library is referenced.
    """
    ...


def build_qa_log_entry(
    slug: str,
    passed: bool,
    veto: bool,
    checks_run: list[str],
    failures: list[QAFailure],
    warnings: list[QAWarning],
) -> dict[str, Any]:
    """
    Build a qa_log.jsonl entry conforming to the REQ-QA-3 canonical schema.
    Derives revision_instructions from failure.revision_instruction fields.
    """
    ...


def append_qa_log(project_root: Path, entry: dict[str, Any]) -> None:
    """
    Append a QA log entry to output/qa_log.jsonl.
    Opens in append mode. Each entry is a single JSON line.
    """
    ...
```

### Tier 3 -- Behavioral Contracts

**BC-9.1 QA agent runs before qa_checker.** In the PostToolUse hook sequence, the Visual QA agent runs veto checks (VETO-01..VETO-07) on the screenshot first. If any veto fires, the agent writes the failure and does NOT invoke `qa_checker.py`. `qa_checker.py` runs only if no veto fires.

**BC-9.2 qa_checker per-invocation Playwright context.** `main_qa_checker` must open its own `sync_playwright()` context. It must not import or use any shared browser context. The context must be closed in a `finally` block.

**BC-9.3 Screenshot written before checks.** `main_qa_checker` must write `output/screenshots/<slug>.png` before running any invariant check. If screenshot fails (Playwright crash or timeout), it must write a failure entry with `"invariant": "SCREENSHOT"` to `qa_log.jsonl` and exit with code 1. The screenshot path MUST share the slug-derived stem with `slide_path`; the filename/slug contract is enforced at the invariant layer by BC-9.3a (INV-24).

**BC-9.3a Filename/slug consistency invariant (BUG-AUDIT-69 / REQ-QA-FILENAME-CONTRACT-1).** `qa_checker.run_programmatic_checks` MUST run a new invariant `INV-24` whose implementation is `check_filename_consistency(slide_path, screenshot_path, project_root)`. The check emits a single `QAFailure` on the first violating rule, else returns `None`. The two rules are:

- **Rule A (always active):** `slide_path.stem == screenshot_path.stem`. On mismatch the failure's `description` MUST name both stems and state that the two files must share a slug for downstream tools to resolve them together. The `revision_instruction` MUST name both canonical paths (`slides/<slug>.html`, `output/screenshots/<slug>.png`) so the slide-maker can rewrite without guessing.

- **Rule B (state-aware, best-effort):** when `<project_root>/deck_state.json` is readable and its `slides` array is a non-empty list containing at least one record with a non-empty `slug`, `slide_path.stem` MUST equal `SlideRecord.slug` for some recorded slide. On mismatch the failure's `description` MUST include a preview of the first few known slugs (capped to avoid log bloat) and state that the filename will not resolve downstream. Rule B is skipped silently when `deck_state.json` is missing, unreadable, not a JSON object, has no `slides` field, has an empty `slides` list, or has no slide entry with a non-empty `slug` — this is the legitimate first-author state and we MUST NOT false-positive there.

INV-24 is a SOFT-blocker (not a VETO) — it participates in the red-green cycle like any Tier-1 invariant. It MUST appear in the `checks_run` enumeration emitted by `main_qa_checker` and in the signature docstring of `run_programmatic_checks`. Agent-side guidance (in `agents/slide-maker.md` and `agents/visual-qa.md`) MUST cross-reference INV-24 as the mechanical enforcement of the filename rule, so authors see the connection between the spec constraint and the QA invariant. See REQ-QA-FILENAME-CONTRACT-1 and BUG-AUDIT-69.

**BC-9.4 qa_log.jsonl canonical schema.** Every entry must include: `slug`, `timestamp` (ISO 8601), `passed` (bool), `veto` (bool), `checks_run` (list), `failures` (list of QAFailure objects), `warnings` (list of QAWarning objects), `revision_instructions` (list of strings). The `revision_instructions` field is derived from `failure.revision_instruction` for all failures.

**BC-9.5 INV-10 reads style_config at check time.** `check_permitted_libraries` must read `style_config.json.constraints.permitted_diagram_types` at check time, not cache it. If `style_config.json` is unreadable, the check exits with code 1. **BUG-AUDIT-60 / REQ-QA-INV10-1:** `_KNOWN_DIAGRAM_LIBS` MUST contain only true diagram libraries. Math renderers (KaTeX, MathJax, etc.) are gated separately by `constraints.math_renderer` via `validate_math_renderer_assets`. Adding `katex` or any math renderer to `_KNOWN_DIAGRAM_LIBS` forces users to pollute `permitted_diagram_types` with non-diagram libraries and is prohibited.

**BC-9.5a VETO-01 a11y exclusions (BUG-AUDIT-60 / REQ-QA-VETO01-1).** `check_text_overflow` MUST exclude elements that are intentionally hidden for screen readers from the overflow walk. The exclusion predicate MUST match at minimum: (a) `aria-hidden="true"` attribute, (b) class membership in `{katex-mathml, sr-only, visually-hidden}`. The exclusion MUST occur before the `scrollWidth > clientWidth` / `scrollHeight > clientHeight` comparison — SR-only elements use the `position:absolute; clip:rect(1px,1px,1px,1px); overflow:hidden; width:1px; height:1px` pattern and have overflow by construction. Failure to exclude forces `accepted_violations` bookkeeping on every math slide, eroding audit signal.

**BC-9.5b INV-13 full-bleed exemption (BUG-AUDIT-61 / REQ-QA-INV13-1).** `check_images_respect_margins` MUST skip any `<img>` element whose class list contains `fullbleed`, OR that has an ancestor (via DOM traversal / `closest('.fullbleed')`) with class `fullbleed`. This exemption resolves the structural conflict between REQ-ASSET-2 (mandatory `<img>` embed) and INV-13 (10% horizontal margin) for the REQ-ASSET-4 full-bleed placement mode. The exemption MUST be DOM-discoverable (class-based), not a hidden-dimension workaround. The Slide Maker agent card MUST document the `<img class="fullbleed">` convention.

**BC-9.6 Preview slides exempt.** The PostToolUse hook checks whether the written file is under `slides/`. Writes to `.debrief/draft/preview_slides/` must not trigger the QA pipeline.

**BC-9.7 qa_cycle_log.jsonl writer exclusivity.** Only `update_state` writes to `output/qa_cycle_log.jsonl`. The QA agent must not write to this file. The `qa_log.jsonl` and `qa_cycle_log.jsonl` are distinct files with distinct schemas and distinct writers.

**BC-9.8 Bug Diagnostic agent write restriction.** `agents/bug-diagnostic.md` must instruct the agent to write only `.debrief/diagnostic_<slug>.md`. It must not write to any state file, `qa_log.jsonl`, or `qa_cycle_log.jsonl`.

**BC-9.9 Diagnostic file lifecycle.** `update_state` deletes `.debrief/diagnostic_<slug>.md` on every exit from `G3.3_slide_review_post_diagnostic` (both SLIDE APPROVED sub-branches and SLIDE REVISE). A second EXHAUSTED for the same slug overwrites the diagnostic file.

**BC-9.10 VETO exclusivity.** When `veto: true` in a qa_log entry, the `failures` list must contain exactly the VETO failure(s) and no Tier 1 invariant failures. The `checks_run` list must not include programmatic Tier 1 check IDs when a veto fires.

**BC-9.11 qa_checker json_repair env check.** `main_qa_checker` must check `importlib.util.find_spec('json_repair')` at entry per Section 24.35 Category 4.3. If unavailable, exit with code 2 and the standardized Section 9.3.1 env-corruption error message.

---

## Unit 10: Export Module

### Tier 2 — Signatures

```python
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any, Optional


def main_export(project_root: Path) -> None:
    """
    Entry point for: python -m debrief.export --project-root <path>

    1. Run style_compiler to ensure CSS is current.
    2. Open sync_playwright() session, launch Chromium, one BrowserContext.
    3. Build page list in canonical PDF order (Section 24.10).
    4. Render each slide to PDF.
    5. Write output/<folder>/deck_v{NNN}.pdf.
    6. Close browser context.
    7. Increment export_count via increment_export_count().
    8. Append entry to output/export_log.jsonl.

    Exit 0 on success. Exit 1 on Playwright or file failure. Exit 2 on env corruption.
    """
    ...


def build_page_list(
    state: "DeckState",
    project_root: Path,
) -> list[dict[str, Any]]:
    """
    Build the ordered list of pages for the PDF in canonical order per Section 24.10:
    1. Approved slides with backup=False in array order.
    2. Closing slide if closing_slide == 'empty' (in-memory styled slide).
    3. Separator if separator_position is not None (in-memory from separator_content).
    4. Approved slides with backup=True in array order.

    Each page is a dict: {"type": "slide"|"closing"|"separator", "path": Path|None,
    "content": str|None}.
    """
    ...


def render_page_to_pdf_buffer(
    page: "playwright.sync_api.Page",
    page_descriptor: dict[str, Any],
    project_root: Path,
) -> bytes:
    """
    Render one page (slide file or in-memory HTML) to a PDF buffer.
    For 'slide' type: navigate to file:// URL, wait for load.
    For 'closing'/'separator' type: set_content() with generated HTML.
    Return the PDF bytes for the page.
    """
    ...


def generate_closing_slide_html(style_config: dict[str, Any]) -> str:
    """
    Generate minimal HTML for a styled empty closing slide using only
    CSS custom properties from the locked style config. No text content.
    """
    ...


def generate_separator_html(
    separator_content: str,
    style_config: dict[str, Any],
) -> str:
    """
    Generate HTML for the separator slide from separator_content.
    separator_content is one of: 'acknowledgments', 'questions', 'summary',
    or custom text.
    Uses CSS custom properties from locked style config.
    """
    ...


def append_export_log(
    project_root: Path,
    presentation_folder: str,
    version: int,
    slide_count: int,
    playwright_exit_status: int,
    pdf_path: str,
    error_message: Optional[str],
) -> None:
    """
    Append one entry to output/export_log.jsonl per REQ-EXPORT-5 canonical schema.
    Schema: {"timestamp": str, "presentation_folder": str, "version": int,
             "slide_count": int, "playwright_exit_status": int,
             "pdf_path": str, "error_message": str | null}.
    All 7 fields are required per REQ-EXPORT-5. On success, error_message is null.
    On failure, error_message contains the Playwright/compiler error text and
    pdf_path may be empty if no PDF was produced.
    """
    ...
```

### Tier 3 -- Behavioral Contracts

**BC-10.1 Style compiler invocation before Playwright.** `main_export` must invoke `python -m debrief.style_compiler style_config.json assets/style.css` as a subprocess before opening any Playwright session. If the compiler exits non-zero, `main_export` must abort and print the compiler's stderr. It must NOT fall back to existing `assets/style.css`.

**BC-10.2 One BrowserContext per export.** `main_export` opens one `sync_playwright()` session, launches Chromium, creates one `BrowserContext`, reuses it for all pages, and closes it after writing the PDF. No per-page browser launch.

**BC-10.3 Canonical PDF page order.** The page list must follow Section 24.10 order exactly: main approved slides → closing slide (if any) → separator (if any) → backup slides (if any, **only when `--include-backup` is passed per BC-10.3a**). Any deviation from this order is a blocking bug.

**BC-10.3a Export backup-inclusion flag (BUG-AUDIT-62 / REQ-EXPORT-BACKUP-1).** `main_export` MUST accept an optional `--include-backup` CLI flag. Default (flag absent) excludes all slides with `backup == True` from the page list — the resulting PDF contains main slides + closing slide + separator ONLY. When `--include-backup` is passed, backup slides are appended after the separator per BC-10.3. This default matches `/debrief:present` and `/debrief:view` (default mode) which both exclude backup slides, eliminating the cross-command inconsistency surfaced by BUG-ST-a-e1. `export_log.jsonl`'s `slide_count` reflects the actual page count (which differs depending on the flag). `/debrief:handout` shares the same `--include-backup` flag with identical semantics per BC-11.16a (BUG-AUDIT-64).

**BC-10.4 PDF file naming.** The output file must be named `deck_v{NNN}.pdf` where NNN is zero-padded to 3 digits and equals `export_count + 1` at the time of export. `export_count` is read from the active presentation record before writing.

**BC-10.5 export_log written after PDF.** `append_export_log` is called after the PDF file is written and closed. If the PDF write fails, no export_log entry is written.

**BC-10.6 G4.5 machine gate reads export_log.** The routing script reads the latest `export_log.jsonl` entry after `main_export` exits. `playwright_exit_status == 0` → EXPORT SUCCESS. Non-zero → EXPORT FAILED with `error_message` injected into the gate context → re-present G4.4.

**BC-10.7 Env corruption check.** `main_export` must check `playwright` availability at entry via `importlib.util.find_spec('playwright')`. If unavailable, exit with code 2 and the standardized Section 9.3.1 message.

**BC-10.8 16:9 PDF page dimensions.** All PDF pages are rendered at 16:9 aspect ratio per REQ-EXPORT-4. The exact pixel dimensions match `layout.slide_width` and `layout.slide_height` from the locked `style_config.json`.

**BC-10.9 Presentation folder naming (BUG-AUDIT-70 / REQ-EXPORT-BOOTSTRAP-1).** *(Rewritten by BUG-AUDIT-70 — original version referenced a `create_presentation_folder` helper and an export-dialog proposal flow that no longer exist after BUG-AUDIT-31.)* On first export of a presentation (when `deck_state.presentations` is empty), `main_export` MUST compute the new `PresentationRecord.folder` value by calling the pure helper `compute_presentation_folder_name(project_name: str, today: date | None = None) -> str` from `debrief_state.py`. The helper implements the following deterministic algorithm:

- **Date detection.** If `project_name` (trimmed of leading whitespace) matches the regex `^(\d{4})([-_]?)(\d{2})([-_]?)(\d{2})(?:[_\- ]+(.*)|$)`, the leading date is normalized to `YYYY_MM_DD` form. The remainder (group 6, if present) is passed through `sanitize_identifier(..., max_length=40)` as the title part; if the remainder is empty, the title part is the fallback `"untitled"`. Today's date is NOT prepended — the user has already committed to a talk date in the project name and the helper honors it. This rule MUST use a TRAILING separator (or end-of-string) in the date detection to avoid false-positives on bare four-digit year prefixes (`"2024_annual_report"` MUST NOT be treated as carrying a date).

- **Today fallback.** If the regex does not match, today's date (from `date.today()`, or the injected `today` parameter for deterministic testing) is formatted as `today.strftime("%Y_%m_%d")` and prepended. The whole `project_name` (including any non-date prefix like a four-digit year) is sanitized via `sanitize_identifier(project_name, max_length=40)` as the title part.

- **Return value.** In both branches, the returned string has the form `f"{date_part}_{title_part}"` where `date_part` matches `^\d{4}_\d{2}_\d{2}$` and `title_part` is the `sanitize_identifier` output (or `"untitled"`).

Re-exports of an existing presentation (when `presentations` is non-empty) MUST reuse `presentations[-1].folder` unchanged — the helper is called only on the self-bootstrap path. Re-exports against a different folder constitute a new presentation per REQ-LIFE-3 and are handled by appending a new `PresentationRecord` (not by calling this helper).

The helper is hosted in `debrief_state.py` rather than `routing.py` because `routing.py` is a gutted shell post-BUG-AUDIT-31 and SHOULD NOT grow new code. `sanitize_identifier` — the helper's own dependency — already lives in `debrief_state.py`, so the two naming utilities cluster naturally. See REQ-EXPORT-BOOTSTRAP-1 and BUG-AUDIT-70.

**BC-10.10 Canonical deck-state import source (BUG-AUDIT-18).** `src/debrief/export.py` (workspace path `src/unit_10/export.py`) MUST import deck-state functions — specifically `read_deck_state`, `write_deck_state`, and `increment_export_count` — from the `debrief_state` module. The module name is `debrief_state` with an underscore, matching the actual filename `debrief_state.py`. Any import of the form `from debrief.state import ...` or `import debrief.state` is a defect: `debrief.state` is not a module that exists in the plugin and has never existed. Prior revisions of `export.py` had this exact typo (two inline import statements), hidden from pytest because `tests/unit_10/test_export.py` was mocking the same phantom path via `patch.dict("sys.modules", {"debrief.state": <mock>, ...})`. The bug surfaced only when a user ran `python -m debrief.export` in production and got `ModuleNotFoundError: No module named 'debrief.state'`. A regression test at `tests/regressions/test_bug_audit_18_export_import_path.py` enforces this contract via (a) a grep-based sentinel over `src/` forbidding the banned substrings `from debrief.state` and `import debrief.state`, and (b) a live-import check that `read_deck_state`, `write_deck_state`, and `increment_export_count` are reachable from the real `debrief_state` module and are callable. The sentinel also walks `tests/` and forbids any file from using `"debrief.state"` as a sys.modules key (the mask-the-bug pattern). See BUG-AUDIT-18.

**BC-10.11 Test files MUST NOT mock non-existent module paths (BUG-AUDIT-18).** Pytest test files anywhere in the plugin MUST NOT call `patch.dict('sys.modules', {'<path>': <mock>})` for any `<path>` that does not resolve to a real module in the plugin. Mocking a phantom module path makes the test suite self-consistent with any production code that imports from the same wrong path, hiding code bugs that should have failed loudly. The BUG-AUDIT-18 regression test enforces this invariant specifically for the `"debrief.state"` key (the historical phantom); general enforcement for other phantom keys is reviewer-gated. If a new test legitimately needs to shadow a real module via sys.modules, the key MUST match a real plugin module whose own import can be verified to succeed in the same Python environment. See BUG-AUDIT-18.

---

## Unit 11: Utility Skills

### Tier 2 — Signatures

```python
from __future__ import annotations
import sys
import webbrowser
from pathlib import Path
from typing import Optional


# --- debrief.view ---

def main_view(query: str, project_root: Path) -> None:
    """
    Entry point for: python -m debrief.view <query> --project-root <path>

    Read deck_state.json and debrief_state.json. Parse query. Collect matching
    slide screenshots. Generate output/view.html. Open in default browser.
    Exit 0 on success. Exit 1 if no slides match the query.
    """
    ...


def parse_view_query(
    query: str,
    state: "DeckState",
) -> list["SlideRecord"]:
    """
    Parse the query argument and return matching slide records.
    Query forms per REQ-VIEW-1:
      'all'               -> all approved slides
      '<slug>'            -> single slide by slug
      'group:<group_id>'  -> all slides in group_id
      'last'              -> last approved slide
      'backup'            -> all backup slides
    Returns empty list if no slides match.
    """
    ...


def generate_view_html(slides: list["SlideRecord"], project_root: Path) -> str:
    """
    Generate a self-contained HTML file tiling slides as thumbnail cards.
    Each card: screenshot image, slug label (small monospace), slide title.
    Single-slide query: render full-size instead of thumbnail.
    No external CSS or JS dependencies.
    """
    ...


# --- debrief.script_generator ---

def main_script_generator(project_root: Path) -> None:
    """
    Entry point for: python -m debrief.script_generator --project-root <path>

    Read deck_brief.md and deck_state.json. Write output/<folder>/script_v{NNN}.md.
    Increment script_count via increment_script_count(). Print path to stderr.
    """
    ...


def generate_script_content(
    deck_brief_content: str,
    slides: list["SlideRecord"],
    folder: str,
) -> str:
    """
    Produce script markdown per REQ-SCRIPT-3: one section per slide with title,
    key talking points, transitions, estimated speaking time.
    """
    ...


# --- debrief.handout ---

def main_handout(mode: str, project_root: Path) -> None:
    """
    Entry point for: python -m debrief.handout --mode <2up|4up>
        --project-root <path>

    Use Playwright to render layout HTML to multi-page PDF.
    Write output/<folder>/handout_v{NNN}.pdf. Increment handout_count.
    Open one sync_playwright() session per invocation.
    """
    ...


def generate_layout_html(
    mode: str,
    slides: list["SlideRecord"],
    project_root: Path,
) -> str:
    """
    Generate the layout HTML combining slide screenshots and explanatory text.
    Mode '2up': two slides per page, detailed notes.
    Mode '4up': four slides per page (2x2 grid), condensed notes.
    Notes from content_summary fields, falling back to script if available.
    """
    ...


def sanitize_save_label(label: str) -> str:
    """
    Sanitize a /debrief:save snapshot label for use as a directory name.
    Applies the Debrief Identifier Sanitization Algorithm (Section 24.10.1)
    with max_length=50.  Returns the sanitized string, or "untitled" if
    the result would be empty after sanitization.

    Default timestamp labels (YYYYMMDD_HHMMSS) are NOT passed through this
    function — they bypass sanitization and are used verbatim.
    """
    ...
```

### Tier 3 -- Behavioral Contracts

**BC-11.1 view mode by phase.** In Phase 1 or Phase 2, the `/debrief:view` skill must print `No slides yet. The view becomes available once slide production begins in Phase 3.` and exit without writing any file or modifying state. In Phase 3, it yields to routing (setting `pre_view_state`, `pending_gate: G3.V_view_dispatch`). In Phase 4/complete, it runs in Run-and-return mode with no routing side effects.

**BC-11.2 view nested protection.** The `/debrief:view` skill must not overwrite `pre_view_state` if it is already set. Nested view calls in Phase 3 do not stack.

**BC-11.3 view red-green deferral.** If a red-green cycle is active when `/debrief:view` is invoked, the skill sets `view_deferred: true` and does not set `pending_gate: G3.V_view_dispatch`. The deferred view fires after the cycle completes.

**BC-11.4 view.html overwrites.** `generate_view_html` must overwrite `output/view.html` on each invocation. The file is ephemeral and not subject to versioning.

**BC-11.5 script_generator precondition.** `main_script_generator` must check that `presentations` is non-empty in `deck_state.json`. If empty, it prints `No export has been done yet. Run /debrief:export first.` and exits with code 1.

**BC-11.6 script folder selection.** *(Superseded by BUG-AUDIT-84 / REQ-SCRIPT-WRITER-1.)* The original rule placed the script at `output/<presentation_folder>/script_v{NNN}.md` with filesystem-derived versioning. As of BUG-AUDIT-84, the script collapses to a single canonical artifact at `<project_root>/speaker_script.md`. Versioned outputs are retired; the wrapping CLI backs up the prior `speaker_script.md` to `.debrief/script_backups/speaker_script.<UTC ISO 8601>.md` before each overwrite per BC-11.20. See `spec/script_writer_rfc.md`. *(Earlier supersession noted by BUG-AUDIT-21: the handout versioning rule formerly bundled here has been moved to BC-11.17.)*

**BC-11.6a Transition extraction grammar (BUG-AUDIT-62 / REQ-SCRIPT-TRANSITION-1).** `_extract_transition` MUST recognize two patterns in the last paragraph of `content_summary`. (1) Explicit marker: a line or sentence beginning with `Transition:` (case-insensitive; optional Markdown bold/italic asterisks allowed before or around the marker — e.g., `**Transition:**`, `*Transition:*`, `Transition: ...`). When matched, the text after the marker is the transition; the remainder (before the marker) is the talking-points body. (2) Signal-word fallback: if no explicit marker, check whether the final sentence contains a transition signal from `_TRANSITION_SIGNALS`. This list MUST include at minimum: `next`, `which leads`, `sets the stage`, `explore next`, `where we go next`, `which brings us`, `let's turn to`, `this leads`, `moving on`, `that's why`, `set up`, `the first move`, `next up`, `move into`, `turn to`, `bringing us to`, `leading into`, `into the next`. When neither the marker nor any signal word is present in the final sentence, the extractor returns `(content_summary, None)` and the script falls back to the placeholder text `Lead into **<next_title>** by connecting the key findings above.`. The explicit-marker branch takes precedence over the signal-word branch when both would match.

**BC-11.6b Script backup inclusion (BUG-AUDIT-65 / REQ-SCRIPT-BACKUP-1).** `main_script_generator` MUST pass every approved slide (both `backup != True` and `backup == True`) to `generate_script_content`. Main slides appear first. When the deck has at least one approved backup slide, `generate_script_content` MUST emit a `## Backup Slides` section heading after the last main slide's block, then generate a script section per backup slide using the same per-slide format (`## Slide N (backup): <title>` with Key talking points, Transition, Estimated speaking time subsections). No CLI flag; backup inclusion is unconditional. Precondition (at least one approved non-backup slide) is unchanged.

**BC-11.7 handout Playwright per-invocation and env check.** `main_handout` must check `importlib.util.find_spec('playwright')` at entry per Section 24.35 Category 4.3. If unavailable, exit with code 2 and the standardized Section 9.3.1 env-corruption error. It must open its own `sync_playwright()` session per invocation, reuse it for all pages of the handout, and close it in a `finally` block. *(BUG-AUDIT-21 amendment: "at entry" now means "after the BC-11.16 precondition checks in order"; the playwright check runs last so that missing-project or missing-slides failures produce accurate, non-misleading error messages instead of a spurious environment-corruption report.)*

**BC-11.8 handout does not consume gate.** When invoked at G4.6, `/debrief:handout` must NOT consume the pending gate. Per REQ-HAND-7, the gate persists until the user explicitly responds to it.

**BC-11.9 save label sanitization.** User-provided labels are sanitized using the Debrief Identifier Sanitization Algorithm (Section 24.10.1) with `max_length=50` before use as the snapshot directory name per REQ-SAVE-3. Default timestamp labels (`YYYYMMDD_HHMMSS`) bypass sanitization. If the sanitized label collides with an existing snapshot directory, append `_2`, `_3`, etc. per REQ-SAVE-3. If the sanitized label is empty (fallback: `"untitled"`), use the fallback.

**BC-11.10 save does not touch debrief_state.** `/debrief:save` copies `deck_state.json` and `ledger.jsonl` to `output/snapshots/<label>/`. It must not copy or modify `debrief_state.json`.

**BC-11.11 restore snapshot validation and restore sequence (BUG-AUDIT-22).** `/debrief:restore` (formerly `/debrief:reset`) operates in two modes: list mode (`label is None`) prints available snapshots and returns; restore mode (`label is str`) validates that `output/snapshots/<label>/deck_state.json` exists, auto-saves current state via `skill_save("pre_restore_<YYYYMMDD_HHMMSS>", project_root)`, overwrites `deck_state.json` from the snapshot (and optionally `ledger.jsonl` if present), sweeps orphan `slides/*.html` files whose stems do not match any slug in the restored state, appends a `{"event": "restore", ...}` JSON line to `ledger.jsonl`, and prints a confirmation to stderr. On invalid label, the function prints a descriptive message listing available snapshots and exits code 2. See REQ-RESTORE-1 and REQ-RESTORE-2.

**BC-11.12 restore scope limits (BUG-AUDIT-22).** `/debrief:restore` MUST NOT touch any project file other than `deck_state.json`, `ledger.jsonl` (optionally), and orphan `slides/*.html` files. Specifically: `CLAUDE.md`, `debrief_state.json`, `style_config.json`, `style_guide.md`, `deck_brief.md`, `.debrief/`, `assets/`, and `output/` (except the auto-save write to `output/snapshots/`) are never modified or deleted by a restore operation. The old hard-delete behavior (BC-11.11 pre-BUG-AUDIT-22) is permanently removed. See REQ-RESTORE-3.

**BC-11.12a orphan-output warning (BUG-AUDIT-61 / REQ-RESTORE-WARN-1).** After BC-11.11's step 6 confirmation print, `skill_restore` MUST perform an orphan-output audit: enumerate immediate subdirectories of `output/` whose names match `YYYY_MM_DD_*`, compare against `presentations[].folder` in the restored deck_state, and for each subdirectory not referenced in the restored state (a) print a warning to stderr naming the path + the count of files inside it, (b) append a `{"event": "restore_orphan_warning", "timestamp": "<ISO>", "orphan_folder": "<path>", "file_count": N}` JSON line to `ledger.jsonl`. MUST NOT delete or modify the orphan files — the scope preservation of BC-11.12 is upheld. A restore with no orphans MUST NOT emit either the stderr warning or the ledger entry.

**BC-11.13 quit flush sequence.** `/debrief:quit` must flush `debrief_state.json` and `deck_state.json` with correct `state_hash` before cleaning any transient artifacts. The flush uses the Unit 2 atomic-write protocol. Ledger is flushed after state files.

**BC-11.14 quit draft retention condition.** `/debrief:quit` retains `.debrief/draft/` only if `pending_gate == "G2.1_style_config_review"` or `sub_phase` is in `{"style/style_dialog", "style/style_review"}`. In all other phases, `.debrief/draft/` is cleaned. Note: `style/style_lock` is intentionally NOT in the retention set — by the time `style/style_lock` is active, `promote_style_draft()` (BC-4.6) has already moved the draft config and guide to the project root via `os.rename`, so `.debrief/draft/` contains only transient preview artifacts that are safe to clean. If the compiler fails mid-lock (G2.2 LOCK FAILED → back to `style/style_review`), the promoted files at the project root are the canonical copies and `.debrief/draft/` is already empty per Section 24.8.

**BC-11.15 handout dedicated stylesheet (BUG-AUDIT-21).** The handout module uses its own first-class stylesheet, shipped as `handout.css` in the workspace at `src/unit_11/handout.css` and mirrored into the delivered plugin at `src/debrief/handout.css`. The stylesheet is loaded at render time by `generate_layout_html` via the sibling-path helper `_load_handout_css()`, which reads `Path(__file__).resolve().parent / "handout.css"` and raises `FileNotFoundError` with a clear packaging-defect message if the file is missing. No silent fallback to an inline default is permitted. The rendered HTML emitted by `generate_layout_html` uses class-based markup only (no per-element `style=` attributes other than dynamic image `src` values); all layout, typography, and color rules live in `handout.css`. The stylesheet is NOT derived from `style_config.json` or `assets/style.css` and is maintained as a standalone design document optimized for print density and ink efficiency. See REQ-HAND-5, BC-11.15a (notes source precedence), and BUG-AUDIT-21.

**BC-11.15a handout notes source precedence (BUG-AUDIT-68 / REQ-HAND-NOTES-1, REQ-HAND-NOTES-2 — amended by BUG-AUDIT-84 / BC-11.15b).** *(Superseded by BC-11.15b once Sub-cycle C ships: the three-level precedence collapses to a single source — `speaker_script.md` section → placeholder. The `content_summary` fallback is retired because every successful `/debrief:script` run now produces a presenter-ready `speaker_script.md` per REQ-SCRIPT-WRITER-1, and `/debrief:handout`'s precondition requires the script to exist per the BC-11.16 amendment.)* `generate_layout_html` MUST resolve each slide's notes text via a deterministic three-level precedence, applied independently per slide:

1. **Speaker script (`<project_root>/speaker_script.md`).** A sibling helper `_load_speaker_script(project_root)` reads the file if present and parses it into a mapping of `{slug_or_title: body_text}`. Parse rule: split on `## Slide ` headers; for each per-slide block, record the block's body keyed by slug (primary, extracted from the `**Slug:** \`<slug>\`` marker when present) AND by title (fallback, extracted from the `## Slide N: <title>` header). The body is everything between the per-slide `## Slide` header and the next `## Slide` header (or `## Backup Slides`, or end of file), minus the header line itself; leading and trailing whitespace are stripped. If the file does not exist, is empty, or parses to zero sections, `_load_speaker_script` returns `None`. Sections under the optional `## Backup Slides` heading are parsed with the same grammar and added to the same mapping (the `(backup)` qualifier in the header is stripped before title matching). The helper MUST NOT raise on malformed files — a best-effort parse returning `None` for unmatched lookups is the correct failure mode.

2. **Content summary (`SlideRecord.content_summary`).** Used when `_load_speaker_script` returned `None` OR when the returned mapping does not contain an entry matching either `slide.slug` or `slide.title`.

3. **Placeholder string `"(no notes available)"`.** Used when both sources produce an empty or missing value. Silent empty cells are forbidden: every rendered notes cell MUST contain either text from a higher-priority source or this exact placeholder string. The placeholder is emitted as plain text inside the existing `.notes` / `.notes-2up` / `.notes-4up` container — no special class, no visual marker, so that authors who add notes later see a natural replacement on re-render.

The handout module MUST NOT read any file under `output/<folder>/script_v*.md`. The generator-written script remains versioned and non-destructive at its original path; promotion to `speaker_script.md` is an explicit user action. `_load_speaker_script` is called once per `generate_layout_html` invocation and the resulting mapping is passed to the per-slide resolution; the file MUST NOT be re-read per slide. The precedence holds for both `2up` and `4up` modes and for both main and backup slides when `include_backup=True`.

See REQ-HAND-3 (rewritten under BUG-AUDIT-68), REQ-HAND-NOTES-1, REQ-HAND-NOTES-2, BC-11.15, and BUG-AUDIT-68.

**BC-11.16 handout fail-fast preconditions (BUG-AUDIT-21 — amended by BUG-AUDIT-84).** `main_handout` validates preconditions at entry, BEFORE any Playwright import or browser launch, in this explicit order: (1) `deck_state.json` exists and is readable; (2) at least one slide has `status == "approved"` AND `backup != True`; (3) `<project_root>/speaker_script.md` exists *(added by BUG-AUDIT-84 — the handout is a pure packager of slides + script; absence triggers consultant auto-cascade to run `/debrief:script` first rather than a hard failure surfaced to the user)*; (4) `importlib.util.find_spec("playwright")` returns a non-`None` spec (see BC-11.7). On any failure, the function prints a descriptive message to stderr identifying the specific missing prerequisite (the message MUST name the prerequisite and MUST NOT be a raw Python exception traceback) and exits with code 2. The playwright check is deliberately attempted last so that missing-project, missing-slides, or missing-script runs produce accurate error messages. The `speaker_script.md` precondition (3) is added at index 3 — after the slides check, before the playwright check — so users get the cheapest informative failure at each level. See REQ-HAND-6, BUG-AUDIT-21, and BUG-AUDIT-84.

**BC-11.16a Handout backup-inclusion flag (BUG-AUDIT-64 / REQ-HAND-BACKUP-1).** `main_handout` MUST accept an optional `include_backup: bool = False` parameter (CLI flag `--include-backup`). Default (flag absent) builds the handout layout from main slides only — approved slides with `backup != True`. When `include_backup` is True, the layout is extended to include approved backup slides in array order (appended after main slides, before any rendering). This mirrors `/debrief:export`'s BC-10.3a semantics exactly so users learn one flag and reuse it across commands. The precondition in BC-11.16 (at least one approved non-backup slide) is unchanged — the flag extends the layout but does not change what counts as "at least one slide worth handing out."

**BC-11.17 handout decoupled output path (BUG-AUDIT-21).** The handout output path is `output/handouts/handout_v{NNN}.pdf`, where `NNN` is a zero-padded three-digit version number derived filesystem-side: `main_handout` scans `output/handouts/` for existing files matching `handout_v*.pdf`, parses their version numbers, and picks `(max existing + 1)`, or `1` if the directory is empty or absent. The `output/handouts/` directory is created on first invocation via `mkdir(parents=True, exist_ok=True)`. The handout module does NOT consult `deck_state.presentations` — it is independent of `/debrief:export` and does not require a prior export. The handout module does NOT mutate `deck_state.json` — versioning is purely filesystem-derived, so no state writes are issued during a handout run. See REQ-HAND-4, REQ-HAND-6, and BUG-AUDIT-21.

**BC-11.18 Present always includes backup (BUG-AUDIT-65 / REQ-PRESENT-BACKUP-1).** `build_presentation_html` and `main_present` MUST include every approved slide in the generated `output/presentation.html` — both `backup != True` (main) and `backup == True` (backup). Main slides appear first in array order, with progressive-disclosure builds expanded per BC-11.10a-equivalent logic (build_1, build_2, ..., final). Backup slides appear after the main sequence in array order; they have no build expansion (backup slides are terminal per the universal slide model). When the deck has at least one main slide AND at least one backup slide, a blank separator slide MUST be inserted between the last main slide and the first backup slide. The separator is rendered in-memory as a `<div class="slide">` whose ONLY content is the locked background color (sourced from `style_config.json` at `colors.background`, with a `#ffffff` fallback). It has no text, no heading, no imagery, no slide counter entry mutation beyond its position in the sequence. When the deck has NO backup slides, no separator is inserted. No CLI flag — backup inclusion is unconditional.

**BC-11.18a Present embeds file-backed slides via srcdoc iframes (BUG-AUDIT-67 / REQ-PRESENT-IFRAME-1..2).** `_write_presentation_html` MUST emit each file-backed slide as `<div class="slide" data-index="N"><iframe srcdoc="…"></iframe></div>`. The srcdoc attribute content MUST be the verbatim original slide HTML (head + body, unmodified) with HTML-attribute escaping applied (at minimum `&`, `<`, `>`, `"` escaped). The iframe MUST carry inline styling `width:100%;height:100%;border:0;display:block;` so it fills the parent wrapper. String-backed bodies from `_collect_presentation_sequence` (the blank separator per BC-11.18) remain plain div content and are NOT wrapped in an iframe. Rationale: each standalone slide's `<head>` carries a per-slide `<style>` block with slide-specific class rules (`.statement-block`, `.main-heading`, etc.); extracting only `<body>` dropped those rules and collapsed every styled element to defaults. Srcdoc preserves the full document. Keyboard navigation (BC-11.18b) must work across the iframe boundary.

**BC-11.19 Generator output-path contract (BUG-AUDIT-77 / REQ-GEN-PATHS-1 — amended by BUG-AUDIT-84).** *(BUG-AUDIT-84 retracts the speaker_script.md non-write invariant. After Sub-cycle B ships the script-writer agent, the SOLE writer of `speaker_script.md` is the `script_writer` CLI subcommand (BC-3.20) operating on output from `agents/script-writer.md` (BC-5.21). Every other code path — including the legacy `main_script_generator` in `utility_skills.py` once it is rewired in Sub-cycle B — MUST NOT write to `speaker_script.md` directly; the file flows through the validated atomic-write pipeline of the wrapping CLI. The Generator Output Paths table below is updated in Sub-cycle B to retire the `output/<folder>/script_v{NNN}.md` row and replace it with `<project_root>/speaker_script.md` — destructive (versioned via `.debrief/script_backups/`).)* Every generator command shipped by the plugin MUST write its output ONLY to the path(s) enumerated in the spec's Generator Output Paths table (appended to Section 14 under BUG-AUDIT-77). Current entries:

- `/debrief:export` → `output/<presentation_folder>/deck_v{NNN}.pdf` (versioned, non-destructive per BC-10.4).
- `/debrief:script` → `output/<presentation_folder>/script_v{NNN}.md` (versioned, non-destructive per BC-11.6).
- `/debrief:handout` → `output/handouts/handout_v{NNN}.pdf` (versioned, non-destructive per BC-11.17).
- `/debrief:view` → `output/view.html` (fixed filename, intentionally overwritten per BC-11.4).
- `/debrief:present` → `output/presentation.html` (fixed filename, intentionally regenerated per BC-11.18).

**Non-write invariant on `speaker_script.md`.** No generator module (`src/unit_10/export.py`, `src/unit_11/utility_skills.py`, and any future generator added to the plugin) MAY write to `<project_root>/speaker_script.md`. The file is the canonical notes source per BC-11.15a / BUG-AUDIT-68 and is user-managed: the user copies a chosen `script_v{NNN}.md` into it (optionally with edits) to activate the handout-merge path, or authors it from scratch. Generators remain strictly READ-ONLY against it — the `_load_speaker_script` helper in `utility_skills.py` is the ONLY code path that touches `speaker_script.md`.

**Scope note on the broader user-managed-at-project-root list.** `deck_brief.md`, `style_guide.md`, `style_config.json`, `deck_state.json`, `debrief_state.json`, `ledger.jsonl`, and `CLAUDE.md` are also user-managed at project root, but their read/write contracts are governed by per-surface BCs — specifically BC-4.6 (stylist promote step), BC-11.9..BC-11.13 (save / restore / quit), BC-6.X (style compiler), and BC-2.X (state machine writers). In particular, `utility_skills.py` hosts both generator skills (script/handout/view/present) AND operator skills (save/restore/quit) whose writes legitimately archive state files to `output/snapshots/`. The BUG-AUDIT-77 non-write invariant is therefore deliberately narrow: it protects ONLY `speaker_script.md` — the canonical notes source established by BUG-AUDIT-68 / BC-11.15a — as a file that has NO legitimate writer anywhere in the plugin (generator or operator). The AST scan runs against the generator modules and flags any write targeting `"speaker_script.md"`; the broader list is documented here for future-reader context but is not mechanically enforced by this test.

**Regression test contract.** `tests/regressions/test_bug_audit_77_generator_output_paths.py` MUST parse each generator module with `ast.parse` and walk the AST for write-expressions (method calls to `.write_text`, `.write_bytes`, `.write`, `open(…, "w")`, `os.rename`, `.save` on file objects); MUST assert that no string literal equal to `"speaker_script.md"` is passed as the target in any such expression. The test runs in both workspace (`src/unit_10/`, `src/unit_11/`) and delivered (`src/debrief/`) layouts via the sibling-discovery path pattern. When a new generator is added in the future, the test author MUST extend the module-scan list.

**When adding a new generator.** Append a row to the Generator Output Paths table in the spec, add a matching BC to this file, and extend the regression test's module-scan list. If the new generator's output path would shadow a user-managed file at project root, the proposal MUST be rejected — BUG-AUDIT-77 rules this out by invariant. See REQ-GEN-PATHS-1 and BUG-AUDIT-77.

**BC-11.18b Keyboard navigation across iframes (BUG-AUDIT-67 / REQ-PRESENT-IFRAME-2).** The presentation.html navigation script MUST register its keydown handler on the top-level window AND — on each iframe's `load` event — attach the same handler to that iframe's `contentDocument`. The handler MUST allow arrow-key events to propagate normally (i.e., return without intercepting) when `event.target` is one of `VIDEO`, `INPUT`, `TEXTAREA`, or `SELECT`, so native element behavior (video seeking, form input, select dropdowns) is preserved. Space/Enter/F behavior is unchanged from BUG-AUDIT-50 baseline. The slide-counter element and fullscreen-toggle behavior remain top-level, not replicated per-iframe.

**BC-11.15b Handout single-source notes (BUG-AUDIT-84 / amends BC-11.15a).** *(Sub-cycle C of `spec/script_writer_rfc.md` §13 makes this contract live. Until then, BC-11.15a's three-level precedence is in force.)* `generate_layout_html` MUST resolve each slide's notes text via a deterministic two-level precedence:

1. **`speaker_script.md` section matched by slug or title.** Same parse rule as BC-11.15a's source #1. The wrapping handout module reads `<project_root>/speaker_script.md` once per generation via `_load_speaker_script` and applies the per-slide section lookup.

2. **Placeholder string `"(no notes available)"`.** Used when the script has no section matching the slide. Silent empty cells are forbidden.

The `SlideRecord.content_summary` fallback that BC-11.15a defined as source #2 is RETIRED. Rationale: every successful `/debrief:script` run now produces a presenter-ready `speaker_script.md` per REQ-SCRIPT-WRITER-1, and `/debrief:handout`'s precondition (BC-11.16 amendment) requires the script to exist before the handout is rendered. The handout no longer needs a fallback to terse internal labels.

Sub-cycle C of the RFC retires `_resolve_handout_notes`'s `content_summary` branch and the BUG-AUDIT-68 regression tests that exercised it. The script-section precedence (matching by slug primary, by title fallback) is preserved unchanged.

**BC-11.15a amendment for parser tolerance (BUG-AUDIT-100).** `_load_speaker_script` MUST accept the following grammar variations in `speaker_script.md` (each backward-compatible with the original strict form):

1. **Header line separator.** The character between the slide number (and optional `(backup)` qualifier) and the title MAY be any of: colon `:`, em-dash `—` (U+2014), en-dash `–` (U+2013), or plain hyphen `-`. The implementing regex MUST be `r"^##\s+Slide\s+\d+\s*(?:\(backup\))?\s*[:—–\-]\s*(.+?)\s*$"`. The title capture group is unchanged from the strict form.

2. **Slug marker shape.** The line carrying the slug marker MAY use any of: bold double-asterisk (`**Slug:** \`<slug>\``), italic single-asterisk (`*Slug: \`<slug>\`*`), or plain (`Slug: \`<slug>\``). The line MAY contain trailing content after the backtick-wrapped slug — for example a budget annotation in the form `· Budget: 0:20` — and the trailing content MUST NOT cause a parse failure. The implementing regex MUST be `r"^\s*\*?\*?\s*Slug:\s*\*?\*?\s*\`([^\`]+)\`"` (no `$` anchor; the slug capture group's bounds are the backticks). The slug capture is unchanged from the strict form.

These tolerances are extensions, not replacements. The strict canonical form (`## Slide N: <title>` with `**Slug:** \`<slug>\``) is what the script-writer agent emits and what BUG-AUDIT-68's regression tests pin; both forms continue to match. The tolerances exist because hand-finalized scripts (when the script-writer agent fails for any reason — see BUG-AUDIT-93/98 for failure modes) often use natural markdown phrasing that the strict form rejects.

**BC-11.15c Handout degradation warning emission (BUG-AUDIT-100).** `main_handout` MUST count placeholder fallbacks in the rendered layout (i.e., the number of slides for which `_resolve_handout_notes` returned `_HANDOUT_NOTES_PLACEHOLDER`) and emit a degradation warning when EITHER condition holds:

1. `_load_speaker_script` returned `None` (the script file was absent, empty, or produced zero matched sections).
2. `placeholder_count / total_main_slides >= 0.5` (more than half of the rendered main slides used the placeholder).

When triggered, `main_handout` MUST:

(a) Print a single-line warning to stderr in the form: `"WARNING: <placeholder_count>/<total_main_slides> handout slides used the '(no notes available)' placeholder. <reason>. Expected grammar: '## Slide N: <title>' (':', em-dash, en-dash, or hyphen separator) with 'Slug: \`<slug>\`' marker (optionally bold or italic)."`. The `<reason>` is one of: `"speaker_script.md is missing"`, `"speaker_script.md is empty"`, `"speaker_script.md exists but the parser matched zero sections"`, or `"slug/title mismatch between script sections and SlideRecord entries"` (the four cases the parser distinguishes).

(b) Append a JSON entry to `<project_root>/.debrief/handout_warnings.jsonl` with this schema:

```json
{
  "timestamp": "2026-05-07T13:42:01Z",
  "mode": "2up" | "4up",
  "total_main_slides": <int>,
  "placeholder_count": <int>,
  "script_path": "speaker_script.md",
  "script_present": <bool>,
  "script_parsed_sections": <int>,
  "first_unmatched_header": <string|null>
}
```

`first_unmatched_header` MUST contain the verbatim first `## Slide` line in the file that the header regex did not match, or `null` if all headers matched (i.e., the degradation is from slug/title mismatches rather than header parse failures). The JSONL append MUST be atomic-by-line (single open-and-append-with-newline per write).

Exit code remains 0 — handout-render's exit-0-always discipline (BC-11.16) is preserved. The warning is observability, not a failure mode. A regression test in `tests/regressions/test_bug_audit_100_handout_parser_tolerance.py` enforces both the parser-tolerance and the warning-emission contracts. Pre-fix, the warning is never emitted because `main_handout` does not inspect placeholder counts; post-fix, every parse-zero-match scenario produces a stderr line and a JSONL entry.

**BC-11.20 Backup-before-overwrite for `speaker_script.md` (BUG-AUDIT-84 / REQ-SCRIPT-WRITER-3).** Before each `/debrief:script` generation that would overwrite an existing `<project_root>/speaker_script.md`, the wrapping CLI (BC-3.20) MUST copy the existing file to `.debrief/script_backups/speaker_script.<UTC ISO 8601>.md`. Timestamp format: `YYYY-MM-DDTHH-MM-SSZ` (using hyphens instead of colons in the time portion for cross-filesystem compatibility on Windows). Backups are retained indefinitely; the user MAY delete `.debrief/script_backups/` manually. Backup-write failure is logged via `log_script_error(error_class="backup_write_failure", …)` but MUST NOT block the new generation — the source data (dialog archive, brief, timeline) is the canonical record; backups are a recovery convenience for hand-edited scripts. The new write to `speaker_script.md` itself uses the atomic `.tmp` + fsync + rename pattern; on rename failure, the prior `speaker_script.md` remains intact and the failure is logged with `error_class: write_failure`. Cycle implementation: Sub-cycle B of `spec/script_writer_rfc.md` §13.

---

## Unit 12: Paper Analyzer

### Tier 2 — Signatures

```python
from __future__ import annotations
import re
import sys
from pathlib import Path
from typing import Optional


def main_paper_analyzer(
    pdf_path: Path,
    paper_slug: str,
    project_root: Path,
) -> None:
    """
    Entry point for:
        python -m debrief.paper_analyzer --pdf <path>
            --paper-slug <slug> --project-root <path>

    Run the full extraction pipeline and write output artifacts.

    Exit codes:
      0 — success
      1 — PDF parse error or IO failure
      2 — conda env corruption (fitz import fails)
      3 — usage error (missing or invalid arguments)
      4 — output write failure
    """
    ...


def extract_paper_text(pdf_path: Path) -> list[str]:
    """
    Open PDF with fitz.open(). Extract text page by page using page.get_text().
    Return list of page text strings in order.
    Raises fitz.FileDataError on corrupt PDF.
    """
    ...


def extract_section_structure(pages: list[str]) -> list[dict]:
    """
    Identify section headings from page text using heuristics
    (short uppercase lines, numbered sections, typical academic heading patterns).
    Return list of {"heading": str, "page_index": int} in document order.
    """
    ...


def extract_figure_captions(pages: list[str]) -> list[dict]:
    """
    Scan page text for figure caption patterns:
      - 'Figure N.' or 'Fig. N.' at the start of a paragraph.
    Return list of {"figure_num": int, "caption": str, "page_index": int}
    in document order.
    Caption regex: r'^(?:Figure|Fig\.)\s+(?P<n>\d+)[\.\:]?\s+(?P<caption>.+)'
    """
    ...


def extract_figure_images(
    pdf_path: Path,
    figure_captions: list[dict],
) -> list[dict]:
    """
    For each figure caption, extract the figure image from the page containing
    the caption using page.get_images() and fitz.Pixmap.
    Return list of {"figure_num": int, "pixmap": fitz.Pixmap, "page_index": int}.
    If a page has no images, the figure entry has pixmap=None.
    """
    ...


def rank_figures(
    figure_captions: list[dict],
    pages: list[str],
    section_structure: list[dict],
) -> list[dict]:
    """
    Rank figures by:
    (a) Citation frequency: count references to 'Figure N' or 'Fig. N' in
        non-caption body text. Higher count -> higher rank.
    (b) Section location: figures in results sections score higher than
        supplementary. Supplementary detection: heading contains 'supplementary'
        or 'appendix' (case-insensitive).
    Return figures sorted by descending rank score.
    """
    ...


def crop_whitespace(pixmap: "fitz.Pixmap", threshold: int = 250) -> "fitz.Pixmap":
    """
    Crop whitespace from a Pixmap using pixel intensity threshold.
    Pixels with all channels >= threshold are considered white/background.
    Find the bounding box of non-white pixels and crop to that box.
    If the entire image is white, return the original pixmap unchanged.
    """
    ...


def save_figure(
    pixmap: "fitz.Pixmap",
    figure_num: int,
    paper_slug: str,
    project_root: Path,
) -> Path:
    """
    Save pixmap to assets/reference/papers/<paper_slug>/figures/fig_<N>.png
    atomically (write bytes to .tmp file then rename).
    Return the destination path.
    Raises OSError on write failure (caller converts to exit code 4).
    """
    ...


def extract_figure_claims(
    pages: list[str],
    figure_captions: list[dict],
) -> dict[int, str]:
    """
    For each figure, extract the 1-3 sentences immediately following the
    figure caption that contain the primary finding.
    Return dict mapping figure_num -> claim text.
    If no sentences follow the caption on the same page, claim is empty string.
    """
    ...


def extract_paper_metadata(
    pdf_path: Path,
    pages: list[str],
) -> dict:
    """
    Extract paper metadata from PDF metadata fields (via fitz.Document.metadata)
    and from the first page text.
    Return dict with keys: title, authors, journal, year.
    All fields may be None if not found.
    """
    ...


def write_paper_analysis(
    project_root: Path,
    paper_slug: str,
    metadata: dict,
    ranked_figures: list[dict],
    claims: dict[int, str],
) -> None:
    """
    Write .debrief/paper_analysis_<paper_slug>.md atomically.
    Format:
      # Paper Analysis: <paper_slug>
      ## Metadata
      **Title:** <title>
      **Authors:** <authors>
      **Journal:** <journal>
      **Year:** <year>
      ## Key Figures
      1. <caption>
      2. <caption>
      ...
      ## Suggested Narrative Arc
      <arc text based on figure sequence and section structure>

    Each figure line must match: ^(?P<n>\\d+)\\. (?P<caption>.+)$
    """
    ...


def copy_pdf_to_archive(pdf_path: Path, paper_slug: str, project_root: Path) -> None:
    """
    Copy pdf_path to assets/reference/papers/<paper_slug>/<pdf_path.name>
    atomically (write bytes to .tmp then rename).
    Create the destination directory if it does not exist.
    """
    ...
```

### Tier 3 -- Behavioral Contracts

**BC-12.1 fitz-only dependency boundary.** `debrief.paper_analyzer` must not import `pptx`, `playwright`, or any VLM SDK. Its only non-stdlib imports are `fitz` (PyMuPDF). The Consultant does not import `fitz` directly.

**BC-12.2 Env corruption on fitz import failure.** If `import fitz` fails at entry, `main_paper_analyzer` must exit with code 2 and the standardized Section 9.3.1 error on stderr.

**BC-12.3 Figure caption regex compliance.** `extract_figure_captions` must use the pattern `r'^(?:Figure|Fig\.)\s+(?P<n>\d+)[\.\:]?\s+(?P<caption>.+)'` (or equivalent). Each matched caption string in the output analysis document must conform to `^(?P<n>\d+)\. (?P<caption>.+)$` on its numbered list line so G1.3 can parse it.

**BC-12.4 Atomic file writes.** `save_figure`, `write_paper_analysis`, and `copy_pdf_to_archive` must all use write-to-tmp then rename atomics. A process kill during any write must leave the destination file either intact (old version) or absent, never partially written.

**BC-12.5 Figure ranking determinism.** Given the same PDF, `rank_figures` must always produce the same ordering. The ranking is deterministic: citation frequency (integer) breaks ties by document order (earlier figure = lower rank).

**BC-12.6 No VLM calls.** `debrief.paper_analyzer` must make no network calls and no LLM API calls. All processing is local and deterministic.

**BC-12.7 Whitespace crop fallback.** If `crop_whitespace` finds that the entire figure image is white (no content pixels), it must return the original pixmap unchanged rather than raising an exception or returning an empty image. When content is present, the cropped sub-pixmap MUST be constructed via the documented `fitz.Pixmap(src_pixmap, fitz.IRect(...))` two-argument constructor (not via the prior `pixmap.set_origin(0, 0).__class__(pixmap, rect)` chain, which silently no-cropped on PyMuPDF versions where `set_origin` returns `None`). On any exception during sub-pixmap construction, return the original pixmap unchanged. *(BUG-AUDIT-87.)*

**BC-12.8 Paper slug derivation and filesystem safety.** The paper slug MUST be derived from the PDF filename by: (1) stripping the `.pdf` extension, (2) applying the Debrief Identifier Sanitization Algorithm (Section 24.10.1) with `max_length=50`. The resulting slug is validated against `^[a-z][a-z0-9_]{0,49}$`. Two fallback cases apply: (a) if the sanitization result is empty (step 7 of the algorithm), use `"untitled"`; (b) if the sanitization result begins with a digit (e.g., PDF named `2024_paper.pdf` → `2024_paper`), prepend `p_` and truncate to 50 characters. Example: `Nature_2024_Smith_et_al.pdf` → `nature_2024_smith_et_al`; `2024_smith.pdf` → `p_2024_smith`. If the user provides multiple papers, each gets its own slug derived independently.

**BC-12.9 Output figure count and per-page image distribution.** The number of figures written to `assets/reference/papers/<paper_slug>/figures/` must equal the number of figures in the ranked list whose `pixmap` is not None. Figures with `pixmap=None` (pages with no extractable images, or fewer images than captions on the page) do not produce an output file but still appear in the analysis markdown with their caption.

When multiple figure captions appear on the same page, `extract_figure_images` MUST distribute the page's images across those captions in document order: the i-th caption on the page receives the i-th image returned by `page.get_images(full=True)`. If a page has fewer images than captions, the trailing captions receive `pixmap=None`. Two captions on the same page MUST NOT receive the same xref — pre-fix behaviour assigned `images[0][0]` to every caption on a shared page, producing identical output PNGs for distinct figures (BUG-AUDIT-86).

**BC-12.10 paper_analysis line format.** Every numbered figure line in `paper_analysis_<paper_slug>.md` must exactly match the regex `^(?P<n>\d+)\. (?P<caption>.+)$`. This is required for G1.3 parsing. Lines that do not match this format are a blocking bug.

**BC-12.11 Figure Claims block format (BUG-AUDIT-85).** `write_paper_analysis` MUST emit a `## Figure Claims` section after `## Key Figures` and before `## Suggested Narrative Arc`. The section contains one line per ranked figure in document order. Each claim line MUST exactly match the regex `^\*\*Figure (?P<n>\d+)\.\*\* (?P<claim>.+)$`. When the extracted claim for a figure is the empty string (no sentences followed the caption on the same page), the line MUST render as `**Figure N.** _(no claim text extracted)_` so the absence is visible to the consultant and the slide-maker rather than silently swallowed. The number of claim lines MUST equal the number of entries in `ranked_figures` (NOT the keys in the `claims` dict — pixmap-none figures still get a claim line). Drift from this format is a blocking bug because the consultant parses the section to map claims to slide briefs.

**BC-12.12 Metadata extraction heuristics (BUG-AUDIT-87).** `extract_paper_metadata` MUST first read the PDF metadata dictionary (`doc.metadata['title' | 'author' | 'subject']`) and use any string values that are not (a) filename-shaped (for `title`: ends with `.pdf` or contains underscores and no spaces) or (b) producer-noise (for `author` and `subject`: matches the producer-noise allowlist in code — `LaTeX (with X)?`, `pdfTeX-…`, `Microsoft® Word`, `Adobe (X)?`, `Skia/PDF mNN`, `MiKTeX-…`). When the PDF metadata is absent or filtered out, the function MUST run page-1 text heuristics: title = first non-trivial line (≥6 words, ≥20 chars, not all-uppercase, not numbered-section); authors = a line within the first 12 non-blank lines that contains commas or " and " and ≥2 capitalized words and no section-keyword stoplist hits; journal = a line within the first 5 non-blank lines containing a recognized journal-name fragment (`Nature|Science|Cell|PLoS|PLOS|eLife|BMC|Journal|Proceedings|Reports?|Letters?|Reviews?|Trends?|Neuron|Lancet|JAMA|Biorxiv|Medrxiv|Frontiers|EMBO|FEBS`). Year extraction is unchanged: regex `\b(?:19|20)\d{2}\b` over page-1 text. The function MUST return `None` for any field where neither the PDF metadata nor the heuristics produced a plausible value — wrong guesses are worse than `Unknown` because they propagate into the slide citation line per REQ-CONSULT-18.

---

## Profile Integration Behavioral Contracts

**BC-PROF-1 ruff lint and format.** All Python modules in `src/debrief/` must pass `ruff check` with no errors and `ruff format --check` with no diff. Line length 88. Import sorting via ruff's isort-compatible rules. No ruff suppressions without inline comment justification.

**BC-PROF-2 mypy strict type checking.** All public functions in `src/debrief/` must satisfy mypy with strict mode (`--strict`). No untyped `Any` returns, no missing annotations on public functions. Type stubs or `# type: ignore` comments require justification.

**BC-PROF-3 Conventional commits.** All commits to the plugin repository must follow the Conventional Commits specification: `<type>(<scope>): <summary>`. Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`. Breaking changes marked with `!` after type. No squash-all-to-main merge commits.

**BC-PROF-4 Semver tagging.** Releases are tagged `v<major>.<minor>.<patch>`. The initial release is `v1.1.0`. Patch bumps for bug fixes, minor bumps for new features, major bumps for breaking changes.

**BC-PROF-5 Keep a Changelog format.** `CHANGELOG.md` follows the Keep a Changelog format with sections: `[Unreleased]`, `[x.y.z] — YYYY-MM-DD`. Each release section has subsections: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

**BC-PROF-6 Main-only branch strategy.** All development merges to `main`. Feature branches are short-lived and deleted after merge. No long-lived `develop` or `release` branches.

**BC-PROF-7 pytest 80% coverage.** The test suite uses pytest. Coverage is measured across `src/debrief/` with a target of 80%. Test names follow `test_<verb>_<subject>` format (e.g., `test_atomic_write_survives_rename_failure`, `test_qa_checker_exits_2_on_missing_playwright`).

**BC-PROF-8 README target audience.** `README.md` targets domain experts (neuroscientists, biomedical researchers) who know conda but not Python packaging. It must not contain API reference sections, contributing guides, or math notation. The Installation section must not instruct the user to run `conda env create` or `pip install` manually.

---

*End of blueprint_contracts.md*
