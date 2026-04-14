# Debrief Hooks — notes on known Claude Code upstream regressions

This file documents hook-related bugs that are NOT the debrief plugin's fault and should not be "fixed" by editing `hooks.json` to work around them. Read this before touching the hook configuration.

## PostToolUse agent hook error in Claude Code v2.1.107+ (BUG-AUDIT-12b)

**Symptom.** When any `Write` or `Edit` tool invocation triggers the PostToolUse hook, Claude Code emits:

```
PostToolUse:Write hook error
Failed to run: Messages are required for agent hooks. This is a bug.
```

The error is **non-blocking** — the Write/Edit operation completes successfully and the session continues normally. The error is cosmetic but clutters the conversation UI.

**Root cause (upstream).** Claude Code's hook runner raises an internal assertion "Messages are required for agent hooks" that references a `messages` field which is NOT documented in the agent-hook schema at `code.claude.com/docs/en/hooks.md`. The documented schema requires only a `prompt` field, which this `hooks.json` provides. The assertion error text literally contains "This is a bug" as Claude Code's own developer-facing acknowledgment that the code reached an impossible state.

**Why we are NOT patching it on our side.** The hook entry matches the documented schema verbatim:

```json
{
  "type": "agent",
  "prompt": "A file was just written or edited. Review the change...",
  "timeout": 60
}
```

per `code.claude.com/docs/en/hooks.md`:

> `prompt` (required): Prompt text to send to the model. Use `$ARGUMENTS` as a placeholder for the hook input JSON.

Adding an undocumented `messages` field as a guess at what the runner wants invites future breakage. Converting the PostToolUse hook to `type: "command"` would lose the agent-based visual QA that spec §7.3 (REQ-SLIDE-7 and related) explicitly requires. The right place to fix this is Claude Code upstream.

**What to do if you see this error.** Ignore it. It does not prevent the plugin from working. The consultant's Write/Edit operations still succeed; only the PostToolUse visual QA agent fails to launch. If the PostToolUse visual QA is critical for your workflow, invoke it manually via `/debrief:view` or `/debrief:slide` after a write.

**Pending upstream fix.** See `spec/stakeholder_spec.md` Bug Catalog entry BUG-AUDIT-12b for the full write-up and the comparison against SVP's hooks.json (which avoids the issue by using only `type: "command"` hooks). Users who hit this behavior should consider filing feedback via `/feedback` in an active Claude Code session, quoting this README.

## PreToolUse command path quoting (BUG-AUDIT-12a, FIXED)

The PreToolUse command references `${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth` wrapped in escaped double quotes:

```json
"command": "\"${CLAUDE_PLUGIN_ROOT}/bin/check-write-auth\""
```

The `\"` characters are load-bearing: when `${CLAUDE_PLUGIN_ROOT}` expands to a path containing whitespace (e.g., `/Users/cfusco/Nextcloud/coding projects/debrief1.0/debrief1.0-repo/debrief`), the quoted form ensures the shell treats the full path as a single token. Without the quotes, `sh` splits on whitespace and reports `/bin/sh: /Users/cfusco/Nextcloud/coding: No such file or directory`. See BC-1.4 and BUG-AUDIT-12a in the spec Bug Catalog.

**Do not remove the escaped quotes** in a future refactor without updating the regression test at `tests/regressions/test_bug_audit_12_hook_path_quoting.py` and documenting the decision. The negative sentinel test will fail loudly if anyone drops the quotes.
