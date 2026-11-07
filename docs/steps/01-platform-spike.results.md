# Step 1 — Platform spike: results

**Date:** 2026-11-07 · **Spec:** [01-platform-spike.spec.md](01-platform-spike.spec.md) ·
**Plan:** [plan](../../.claude/plans/01-platform-spike.plan.md) (critic: REVISE → REVISE → APPROVE)

**Gate outcome: STOP — decision needed.** DESIGN §10 risk 1 **FAIL** (with working workarounds),
risk 4 **PARTIAL** (hand-back tool), risks 2 and 3 **PASS**. Two findings outside §10 also need a
decision (§ "New findings"). Nothing in DESIGN.md was changed.

## Environment

| Item | Value |
|---|---|
| specify | 1.0.2 |
| Claude Code | 2.1.318, headless `claude -p`, model `claude-haiku-5-5` for every run |
| uv | 0.11.26 |
| Python | uv-managed CPython 3.14.6 only; **no `python`, `python3`, `py` on PATH** |
| Git / shell | git 2.56.0.windows.4; Git Bash 5.3.15 |
| OS | Windows 11, build 10.0.26300.9711 |

## How it was run

- Everything in the session scratchpad (`…\scratchpad\spike01\`): `proj/` (throwaway project),
  `ext/` (test extension `ac`), `ext-zz/` (second extension `zz`), `logs/`.
- `specify init proj --integration claude --script sh --non-interactive` — offline, < 1 s; no
  `git init`, no `CLAUDE.md`, no `.claude/settings.json` created. A `CLAUDE.md` with a random canary
  codeword was added.
- Live runs: a wrapper `crun <id> "<allowedTools>" "<prompt>"` that runs, inside `proj/`,

  ```bash
  env -u <36 host CLAUDE* names> claude -p "<prompt>" --model haiku --max-budget-usd 1 \
    --setting-sources project,local --no-session-persistence \
    --output-format stream-json --verbose --allowedTools "<allowedTools>"
  ```

  The stripped names (desktop-host session ids, messaging socket/token, entrypoint, …) are listed in
  `logs/env.txt`; values were never read or printed. None of the keep-list names
  (`CLAUDE_CODE_GIT_BASH_PATH`, `CLAUDE_CODE_USE_POWERSHELL_TOOL`, `CLAUDE_CODE_SHELL*`) was set.
- 11 live runs (7b, A, B, C1–C4, D1–D3, E), no Sonnet reruns needed. Summed `total_cost_usd`:
  **$0.037** (worst case allowed by the caps: $11).

## Results

Status: `PASS` / `FAIL` / `PARTIAL` / `NOT RUN`. "Consequence" = what steps 2–6 must do.

### Risk 1 — `disable-model-invocation: true` kept in the generated skill

| # | Check | Status | Evidence | Consequence |
|---|---|---|---|---|
| 1.1 | Skill path/name (R04) | PASS | `.claude/skills/speckit-ac-probe/SKILL.md` (name `speckit-ac-probe`) | Command `speckit.ac.<x>` → skill `/speckit-ac-<x>` as DESIGN §6 assumes |
| 1.2 | Flag survives (R04, **risk 1**) | **FAIL** | Rendered frontmatter has **no** `disable-model-invocation` and no `user-invocable` key (quoted below); Claude Code's default = model-invocable | Needs a workaround (options below) |
| 1.3 | Where it is lost (R05) | PASS | `extension add` → `CommandRegistrar.register_commands` (`agents.py:795`) → `render_skill_command` (`agents.py:395–437`), which rebuilds frontmatter from `build_skill_frontmatter` (`agents.py:439–455`: `name`, `description`, `compatibility`, `metadata`) only. (The critic's predicted path `_register_extension_skills` is not used for `--dev` here: `registered_skills: []`.) | — |
| 1.4 | Passthrough field (R05b) | FAIL | None for this flag; only `argument-hint` passes through on some paths | Not a usable route |
| 1.5 | Model can invoke the skill as rendered (R09h) | confirmed | D1: `CALL Skill {"skill": "speckit-ac-probe"}` → `Launching skill` → `PROBE-SKILL-RAN` | The risk is real, not theoretical |
| 1.6 | Patched flag works (R05a, R09h) | PASS | D3: patch `disable-model-invocation: true`, forced attempt → `<tool_use_error>Skill speckit-ac-probe cannot be used with Skill tool due to disable-model-invocation. Ask the user to run /speckit-ac-probe themselves`. Skill stays in the slash-command list (user can still type it). **Note:** the hook log is empty for D3 — Claude Code rejects the call *before* `PreToolUse`; the attempt and error are taken from the stream-json (the plan's "attempt in hook log" rule could not apply) | Patch is effective when present |
| 1.7 | Patch survives later `specify` operations (R05a) | PARTIAL | Both variants (through the symlink / replaced by a real file): survives `extension add zz`, `extension remove zz`. **Reverted** by `specify integration upgrade claude` (re-rendered as a plain file with explicit `disable-model-invocation: false`, `metadata.source: extension:ac`) and by `specify extension add --dev ac --force` (link regenerated, no key). `--force` overwrote even a user-modified real file. Logs: `rewrite-v1.txt`, `rewrite-v2.txt` | A deploy patch must be re-applied after our own `upgrade`, checked by `doctor`; a user's own `specify integration upgrade` silently reverts it. The patch must change only that key and keep `metadata.source` (spec-kit's ownership check on uninstall) |
| 1.8 | Guard deny (R05c, R09h) | PASS | D2 with deny marker: `PreToolUse:Skill hook error: [...]: SPIKE-BLOCK: ac skill`; model reports it blocked. Skill input = `{"skill": "speckit-ac-probe"}` — field **`skill`**, bare name, no leading `/` | Guard (step 2) can enforce it: main role, `tool_name == "Skill"`, `tool_input.skill` starts with `speckit-ac-` → exit 2 |

Rendered `SKILL.md` (1.2):

```markdown
---
name: speckit-ac-probe
description: Spike probe command. Replies PROBE-SKILL-RAN.
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: ac:commands/speckit.ac.probe.md
---

Reply with the single line `PROBE-SKILL-RAN` and stop. Use no tools.
```

### Risk 2 — optional hooks prompt after clarify / plan / tasks / implement

| # | Check | Status | Evidence | Consequence |
|---|---|---|---|---|
| 2.1 | `extensions.yml` registration (R04) | PASS | four `hooks.after_*` entries `{extension: ac, command: speckit.ac.probe, enabled: true, optional: true, priority: 10, prompt, description, condition: null}`; file also gets `settings.auto_execute_hooks: true` | — |
| 2.2 | Static: core skills read the hooks (R06) | PASS | `speckit-clarify` (l. 248), `speckit-plan` (77), `speckit-tasks` (97), `speckit-implement` (190) each have a "Mandatory Post-Execution Hooks" block reading `hooks.after_<x>`, with the optional-hook output format, and the rule "replace dots with hyphens" (`speckit.git.commit` → `/speckit-git-commit`) | — |
| 2.3 | Live: `/speckit-tasks` (R06) | PASS | Run E: skill launched, `specs/001-stub/tasks.md` written, `setup-tasks.sh` called (it failed — see N2). Final output: `**Optional Hook**: ac` / ``Command: `/speckit-ac-probe` `` / `Prompt: Run the AC probe?` / ``To execute: `/speckit-ac-probe` `` / "I did not run this hook because it is optional." No `Skill` call for the probe in the hook log | Optional hooks are offered, not run |
| 2.4 | Accepted hook when the skill is not model-invocable (R05, last sentence) | PASS (by composition) | The prompt prints the real skill name `/speckit-ac-probe` (hyphen form, from 2.2), which the user can type; with the flag patched, the model cannot run it (1.6 error text tells it to ask the user) | Step 4 hook `prompt` text should say "type `/speckit-ac-…`"; without the patch, a "yes" would let the model run it itself |

### Risk 3 — extra payload files land and are removed

| # | Check | Status | Evidence | Consequence |
|---|---|---|---|---|
| 3.1 | Folder copied with all extra files (R04, **3a**) | PASS | `.specify/extensions/ac/{README.md, extension.yml, commands/…, agents/spike-agent.md, hooks/probe_hook.py, scripts/probe.py, templates/probe.md}`; no symlinks inside; editing the source afterwards does not change the copy; registry `"source": "local"` | Agents/hooks/scripts can ship in the payload |
| 3.2 | Generated skill is a **symlink** (R04) | observed | `.claude/skills/speckit-ac-probe/SKILL.md -> ../../../.specify/extensions/ac/.specify-dev/agent-commands/claude/speckit-ac-probe/SKILL.md` (a real NTFS symlink was created on this machine) | See N1 |
| 3.3 | `add --dev --force` (R07) | PASS | Folder is rebuilt: a file deleted from the source disappears, a changed file is updated; `.registry` rewritten | `upgrade` = `add --force` gives a clean copy (and drops any patch, 1.7) |
| 3.4 | `remove ac --force` (R07, **3b**) | PASS | Removed: extension folder with all extra files and `.specify-dev/`, the skill dir, the four hook entries, the registry entry. Left: `.specify/extensions/.registry` = `{"extensions": {}}`, `.specify/extensions.yml` = `installed: []`, `hooks: {}`, empty `.specify/extensions/.backup/ac/` (and `.backup/zz/`). No `ac` file left (`diff-0-3.txt`) | Our `uninstall` should mention the leftovers; `.registry` matters (N2) |
| 3.5 | `settings.json` touched by `specify extension …` (critic F7) | PASS | hash unchanged across add/remove/`--force`/`integration upgrade` (the file already had `indent=2` JSON) | Deploy merge rule unaffected |

### Risk 4 — Claude Code platform features

| # | Check | Status | Evidence | Consequence |
|---|---|---|---|---|
| 4.1 | Hook fires main + subagent; `agent_type` (R09a) | PASS | Run A hook log: main calls have no `agent_type` key; inside subagents `agent_type` = `spike-agent` (custom agent's `name`) and `Explore`; subagent input also carries `agent_id` | Guard dispatch by `agent_type` works as designed |
| 4.2 | Exit 2 blocks, reason reaches model (R09b) | PASS | `Read src/blocked.txt` denied for main, `spike-agent` and `Explore`: `PreToolUse:Read hook error: [<command>]: SPIKE-BLOCK: blocked.txt`; model quoted it | — |
| 4.3 | Hand-back tool name (R09c, **SubagentHandback**) | **PARTIAL** | In headless CLI 2.1.318 **no** hand-back tool call reached the hook, for `spike-agent` and `Explore` alike (so not caused by the `tools:` whitelist); the subagent's final text is returned in the `Agent` tool result. The desktop-app host does use a tool named `SubagentHandback` (seen in this session's own harness), but whether it passes `PreToolUse` there was not tested | The guard must not depend on seeing it, and must **allow** `SubagentHandback` for AC roles (default-deny would otherwise break hand-back in the desktop app). Confirm in the interactive smoke test (steps 7–8) |
| 4.4 | `onFailure: "block"` (R09d) | PASS | C1 missing interpreter: `failed; blocking because onFailure is "block"` (`/usr/bin/bash: … No such file`); C3 timeout 3 s: `timed out; blocking because onFailure is "block"`; controls C2/C4 without `onFailure`: read succeeded. Probe hook logged in every C run, so hooks were loaded | Keep `onFailure: "block"` + `timeout` on the guard entry |
| 4.5 | `omitClaudeMd: true` (R09e) | PASS | Run B (measured on `spike-omit`, Glob-only, because an agent with `Read` could read `CLAUDE.md` from disk): `spike-omit` → `NONE`; `spike-control` → quoted the codeword; main agent quoted it too; codeword absent from both subagent prompts; no Read/Grep/Bash by either subagent | Keep `omitClaudeMd: true` on the three AC agents |
| 4.6 | `PowerShell` tool fires the hook (R09f) | PASS | Run A: `PowerShell` offered headless; hook log `tool_name: PowerShell`, input keys `command, description`. Hook commands themselves run in Git Bash (`/usr/bin/bash` in C1's error) | Guard treats `PowerShell` like `Bash` (as in CT) |
| 4.7 | Hook latency (R09g) | measured | `uv run --no-project python -I probe_hook.py`, 12 calls: median **150 ms**, max 168 ms (bare interpreter, single sample: 156 ms) | ~0.15 s per tool call with matcher `*`; acceptable |
| 4.8 | Hook input shape (R08) | observed | top-level keys: `cwd, effort, hook_event_name, permission_mode, prompt_id, session_id, tool_input, tool_name, tool_use_id, transcript_path` (+ `agent_id, agent_type` in subagents) | Input for the guard port (step 2) |

## New findings (outside DESIGN §10)

- **N1 — `--dev` installs symlink the skills.** `.claude/skills/speckit-ac-*/SKILL.md` is a symlink
  into `.specify/extensions/ac/.specify-dev/…` (plain-file fallback only if symlink creation fails).
  DESIGN §9 installs with `--dev`. A committed symlink is fragile for Windows teammates
  (`core.symlinks=false` here). How git records it and what a clone gets was **not verified** — step
  6 must decide (e.g. deploy replaces links with files, or `.gitignore` + regenerate).
- **N2 — spec-kit's scripts need a PATH Python once any extension is installed.**
  `common.sh:401–483`: when `.specify/extensions/.registry` exists, `_python3_command` looks for
  `python3`, `python` or `py -3` on PATH and otherwise fails with "Python 3 is required to honor the
  extension registry". Run E: `setup-tasks.sh` failed this way (the model worked around it by hand).
  Moving `.registry` aside made the script work; `remove` leaves an empty `.registry`, so the
  requirement persists after uninstall. `uv run --no-project python` (our guard's command) does not
  satisfy it. Steps 5/6: install/doctor must check for a PATH Python and tell the user; this machine
  (and possibly the Habit Tracker dogfood, step 8) currently has none.
- **N3 — user-level writes.** Despite `--no-session-persistence`: `~/.claude.json` changed (not
  opened; it holds account data), and four subagent `*.meta.json` files were written under
  `~/.claude/projects/<spike01-proj>/<session>/subagents/`. `~/.claude/stats-cache.json` and
  `history.jsonl` unchanged. One earlier probe (before the plan, without the flag) left a transcript
  folder `~/.claude/projects/<spike01-probe0>/`. Spec R01's "no change to `~/.claude/`" therefore
  holds only in this limited sense; the folders can be deleted on request.

## Decisions needed (gate, R12)

1. **Risk 1 workaround** — options:
   - **A. Guard denies main-agent `Skill` calls for `speckit-ac-*`** (1.8). Fail-closed, independent
     of spec-kit, survives every `specify` operation. The model still sees the skill descriptions and
     may try, then gets blocked.
   - **B. Deploy patches `disable-model-invocation: true`** into the generated skills (1.6), `doctor`
     checks it, our `upgrade` re-applies it. Silently reverted by a user's `specify integration
     upgrade` or `extension add --force` (1.7).
   - **C. A + B** (recommended): B hides the skills from the model in normal operation; A enforces it
     when B has been reverted.
   - D. Accept model-invocable skills (prompt text only) — loses the human gates of DESIGN §5.
2. **Hand-back (4.3)** — recommended: guard allows `SubagentHandback` for AC roles without relying on
   it; verify in the interactive smoke test (steps 7–8).
3. **N1 symlinks** — decide in step 6 (needs a git check), or now.
4. **N2 PATH Python** — make it a documented prerequisite checked by `install`/`doctor`/init.

If accepted, DESIGN §9/§10 and the decision log get the corresponding entries (only after agreement).

**Decided 2026-11-07:** 1 → **C**, 3 (N1) → **A**, 4 (N2) → v1.0 environment fixed to
Windows + uv + pwsh with spec-kit `--script ps`, other setups deferred (user). Recorded in DESIGN §2,
§9, §10 and the decision log. 2 (hand-back) → **A**: interactive Claude Code only, `claude -p`
unsupported, guard allows `SubagentHandback` for AC roles (user). All gate decisions made.

**Follow-up check for decision 4 (2026-11-07):** a second throwaway project initialised with
`--script ps`, with the same extension installed and no Python on PATH: spec-kit's
`setup-tasks.ps1 -Json` succeeded. `common.ps1` reads the extension registry natively
(`ConvertFrom-Json`, l. 357–381) and needs Python only for **preset** template composition
(l. 594–602). So N2 affects projects that use spec-kit's `sh` (or `py`) scripts, not `ps`. Hook start
latency for comparison: `pwsh -NoProfile -NonInteractive -File` with a minimal script, 12 calls:
median 294 ms, max 309 ms (vs 150 ms for `uv run --no-project python -I`).

## Fixtures (for repeating the spike)

`ext/extension.yml` (abridged: four identical hook entries):

```yaml
schema_version: "1.0"
extension: {id: ac, name: "AC spike", version: "0.0.1", description: "…", author: spike,
            repository: https://example.invalid/spike, license: MIT}
requires: {speckit_version: ">=0.2.0"}
provides:
  commands:
    - {name: speckit.ac.probe, file: commands/speckit.ac.probe.md, description: "Spike probe command"}
hooks:
  after_tasks: {command: speckit.ac.probe, optional: true, prompt: "Run the AC probe?",
                description: "Spike optional hook after tasks"}
  # same for after_clarify, after_plan, after_implement
```

`ext/commands/speckit.ac.probe.md`:

```markdown
---
description: "Spike probe command. Replies PROBE-SKILL-RAN."
disable-model-invocation: true
---

Reply with the single line `PROBE-SKILL-RAN` and stop. Use no tools.
```

Extra payload files: `agents/spike-agent.md`, `hooks/probe_hook.py`, `scripts/probe.py`
(`print("probe")`), `templates/probe.md`, `README.md`. Second extension `zz`: one command
`speckit.zz.noop`, no hooks.

Agents in `proj/.claude/agents/`:

```markdown
---
name: spike-agent            # run A
description: Spike test agent with a tool whitelist and omitClaudeMd. Use only when explicitly asked.
tools: Read, Glob, Grep
disallowedTools: Skill, Agent, mcp__*
omitClaudeMd: true
---
---
name: spike-omit             # run B; spike-control = same without omitClaudeMd
description: Spike omit agent for the CLAUDE.md visibility test. Use only when explicitly asked.
tools: Glob
disallowedTools: Read, Grep, Bash, Skill, Agent, mcp__*
omitClaudeMd: true
---
```

`proj/.claude/settings.json` (runs C1–C4 added a second entry: missing interpreter
`C:/nonexistent/python3.exe …` or `uv run --no-project python -I -c "import time; time.sleep(30)"`
with `timeout: 3`, each with and without `onFailure`):

```json
{"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command",
  "command": "uv run --no-project python -I \"$CLAUDE_PROJECT_DIR/.claude/hooks/probe_hook.py\"",
  "timeout": 15, "onFailure": "block"}]}]}}
```

`probe_hook.py` (stdlib only):

```python
import json, os, re, sys, time
SKILL_NAME = re.compile(r"^/?[A-Za-z0-9._:-]{1,64}$")

def main() -> int:
    data = json.loads(sys.stdin.read())
    project = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    tool, tin = data.get("tool_name"), data.get("tool_input") or {}
    path = next((tin[k] for k in ("file_path", "path", "notebook_path") if isinstance(tin.get(k), str)), "")
    rec = {"ts": round(time.time(), 3), "keys": sorted(data), "tool_name": tool,
           "agent_type": data.get("agent_type", "<absent>"),
           "tool_input_keys": sorted(tin) if isinstance(tin, dict) else str(type(tin)), "path": path}
    if tool == "Skill" and isinstance(tin, dict):
        rec["skill_fields"] = {k: v for k, v in tin.items() if isinstance(v, str) and SKILL_NAME.match(v)}
    decision, reason = "allow", ""
    if tool == "Read" and path.replace("\\", "/").lower().endswith("src/blocked.txt"):
        decision, reason = "deny", "SPIKE-BLOCK: blocked.txt"
    elif tool == "Skill" and os.path.exists(os.path.join(project, ".claude", "hooks", "deny-skill")):
        if any("speckit-ac-" in v for v in rec.get("skill_fields", {}).values()):
            decision, reason = "deny", "SPIKE-BLOCK: ac skill"
    rec["decision"] = decision
    os.makedirs(os.path.join(project, ".spike"), exist_ok=True)
    with open(os.path.join(project, ".spike", "hook.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    if decision == "deny":
        print(reason, file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # fail closed
        print(f"SPIKE-HOOK-ERROR: {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
```

Raw logs (listings `snap-*.txt`, `run-*.jsonl`, `hook-*.jsonl`, `rewrite-v*.txt`, `latency.txt`) stay in
the session scratchpad, outside the repo.
