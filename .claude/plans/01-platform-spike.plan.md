# Plan — Step 1: Platform spike

**Spec:** `docs/steps/01-platform-spike.spec.md` (approved 2026-11-07, decisions 1–4) · **Round:** 3

## Facts observed before planning

- Tools: specify 1.0.2, Claude Code 2.1.318, uv 0.11.26, .NET SDK 10.0.403, Windows 11, Git Bash.
  `python`, `python3`, `py` are **not** on PATH; uv-managed CPython 3.14.6 exists.
- A headless probe already ran: `claude -p "Reply with exactly: OK" --model haiku
  --max-budget-usd 0.05 --setting-sources project,local --output-format json`, launched with every
  `CLAUDE*` environment variable of this host session removed → answered, cost ≈ $0.002, 3 s. Auth
  comes from the CLI's own login (a credentials file exists; its content was not read).
- This session's environment carries ~35 `CLAUDE*` variables from the desktop host (session ids,
  messaging socket/token, entrypoint). A nested `claude` must not inherit them: every run strips
  them by an **explicit name list** = all `CLAUDE*` names present minus a keep-list of configuration
  knobs that locate tools (`CLAUDE_CODE_GIT_BASH_PATH`, `CLAUDE_CODE_USE_POWERSHELL_TOOL`,
  `CLAUDE_CODE_SHELL*`) — checked 2026-11-07: none of the keep-list names is set in this host, so
  Git Bash is found via PATH as for a normal CLI start (critic r2 F1). Names stripped and kept are
  recorded in `logs/env.txt`; values are never printed.
- `specify init` options: `--integration`, `--script sh|ps|py`, `--non-interactive`, `--here`,
  `--force`, `--extension`. `specify extension add`: `--dev`, `--from`, `--force`, `--priority`.
  `specify extension remove`: `--keep-config`, `--force` (skip confirmation).
- spec-kit's skill rendering for **extension** commands (`extensions/__init__.py:1685–1711`,
  `_register_extension_skills`): frontmatter rebuilt by `CommandRegistrar.build_skill_frontmatter`
  (`agents.py:439–455`: `name`, `description`, `compatibility`, `metadata`) plus only `argument-hint`
  (`apply_argument_hint`), then `ClaudeIntegration.post_process_skill_content`
  (`integrations/claude/__init__.py:218–228`) injects `user-invocable` and
  `disable-model-invocation: false` when absent. **Risk 1 is expected to FAIL deterministically**;
  steps 5 and 12 are therefore mandatory, and the only passthrough candidate for R05b is
  `argument-hint` (useless for this purpose; recorded, not tested further).
- `--dev` installs use `link_commands=True` (`extensions/_commands.py:986–992`): the rendered skill
  is written to `.specify/extensions/ac/.specify-dev/extension-skills/<skill>/SKILL.md` and
  `.claude/skills/<skill>/SKILL.md` becomes a **symlink** to it, with a plain-file fallback if
  `os.symlink` fails (`extensions/__init__.py:1628–1630, 1713–1728`). On Windows this depends on
  symlink privilege; DESIGN §9 plans `--dev` installs, so the result matters for committed files.
- `extension add/remove` re-serialize `.claude/settings.json` via `_refresh_events_and_warn`
  (`events.py:2337–2369, 2497`; critic F7). `manager.remove` backs up `*-config.yml` into
  `.specify/extensions/.backup/<id>/` (`extensions/__init__.py:2951–2964`; critic F8).
- `extensions.yml` stores the raw command id (`speckit.ac.probe`, `extensions/__init__.py:5045`); the
  core tasks template prints `` To execute: `/{command}` `` (`core_pack/commands/tasks.md:117–127`), so
  the hook prompt is expected to name `/speckit.ac.probe`, not the Claude skill name
  `/speckit-ac-probe` (critic F1).
- Core extension `git` shows the hook format: `hooks.<event>: {command, optional, prompt, description}`.
- CT registers its guard as `uv run --no-project python -I "$CLAUDE_PROJECT_DIR/.claude/hooks/guard.py"`,
  `"timeout": 15`, `"onFailure": "block"`.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| 1 | Headless `claude -p` loads project hooks, project agents and project skills the same way an interactive session does | 0.8 | Risk-4 results would not carry over to interactive use | Hook log must show calls for every run; if a run logs nothing, mark its rows `NOT RUN` and say why. Interactive confirmation stays in the step 7–8 smoke test (spec out-of-scope) |
| 2 | A nested `claude` with all `CLAUDE*` variables stripped behaves like a standalone CLI | 0.85 | Odd behaviour attributed to the platform | Already probed once (step "Facts"); every run's `system/init` event records tools, agents, skills seen — check it |
| 3 | `--setting-sources project,local` still loads the project `CLAUDE.md` | 0.8 | omitClaudeMd test (R09e) meaningless | Sanity question to the main agent in the same run: it must quote the canary |
| 4 | PreToolUse hooks run before the permission check, so a call that permissions would deny is still logged | 0.75 | Misattributed blocks | Every tool used in a check is in `--allowedTools`; blocks are attributed only from the hook log + tool_result text |
| 5 | The `PowerShell` tool may not be offered in headless mode | 0.5 | Low: R09f becomes `NOT RUN` | `system/init` tool list; no env tweaks beyond documented ones |
| 6 | Haiku follows the probe prompts reliably enough | 0.7 | Inconclusive rows | Re-run that single check once with Sonnet; record which model produced the evidence |
| 7 | `onFailure` covers a hook command that cannot start (exit 127) and/or a timeout | 0.5 | Wrong conclusion about fail-closed launch | Test both variants (missing interpreter; hook that sleeps past its timeout), each with a control run without `onFailure` |
| 8 | `specify init` needs no network (bundled core pack) | 0.7 | Low: network is available | Observe; record if it downloads |

No assumption is blocking (none is < 0.7 with high consequence except #7, which the plan tests
directly instead of assuming).

## Layout (all in the scratchpad, `$SP` = session scratchpad)

```
$SP/spike01/
  ext/        test extension source (id ac)
  ext-zz/     second dummy extension (id zz) for rewrite checks
  proj/       throwaway spec-kit project
  logs/       listings, run-NN.jsonl (stream-json), timings, notes
```

Hook log: `proj/.spike/hook.jsonl`. Nothing in this repo changes until step 12.

## Steps

1. **Environment record** (R02). Capture `specify --version`, `claude --version`, `uv --version`,
   `uv run --no-project python -I -c "import sys;print(sys.version)"`, `git --version`, OS build into
   `logs/env.txt`.
2. **Throwaway project** (R01, R02). In `$SP/spike01`: `specify init proj --integration claude
   --script sh --non-interactive`. Record whether it downloads anything and whether it runs `git init`.
   Write/append `proj/CLAUDE.md` with one canary line: `Project codeword: <random WORD-NNNN>` (random
   per run, generated with `$RANDOM`; recorded in `logs/canary.txt`). Snapshot with a `snap <n>`
   helper used for every listing in this plan: `find . \( -type f -o -type l \) | sort` plus, per
   entry, `L -> <target>` for symlinks (`readlink`) or the `sha256sum` for files →
   `logs/snap-<n>.txt` (critic F2: `-type f` alone drops symlinks).
3. **Test extension** (R03). Write `ext/`:
   - `extension.yml`: `schema_version: "1.0"`; `extension: {id: ac, name, version: "0.0.1",
     description, author, repository, license: MIT}`; `requires.speckit_version: ">=0.2.0"`;
     `provides.commands: [{name: speckit.ac.probe, file: commands/speckit.ac.probe.md, description}]`;
     `hooks.after_clarify|after_plan|after_tasks|after_implement: {command: speckit.ac.probe,
     optional: true, prompt: "Run the AC probe?", description: ...}`.
   - `commands/speckit.ac.probe.md`: frontmatter `description: ...` + `disable-model-invocation: true`;
     body: "Reply with the single line `PROBE-SKILL-RAN` and stop. Use no tools."
   - `agents/spike-agent.md`, `hooks/probe_hook.py` (same file as step 6), `scripts/probe.py`
     (`print("probe")`), `templates/probe.md`, `README.md`.
   - `ext-zz/`: same shape, id `zz`, one command `speckit.zz.noop`, no hooks.
4. **Install + inspect** (R04 → risks 1, 3a). In `proj/`: `specify extension add --dev ../ext`.
   Then:
   - `snap 1`, diff against snap 0 → `logs/diff-0-1.txt` (`.specify-dev/` inside the extension
     folder is expected and reported separately from the payload's extra files);
   - full frontmatter of `.claude/skills/speckit-ac-probe/SKILL.md` (or wherever it lands — find by
     `grep -rl speckit-ac-probe .claude`); `test -L` on it and its link target (critic F2);
   - registry file under `.specify/extensions/` (find it; record the `ac` entry incl. `source`);
   - `.specify/extensions.yml` hook entries for `ac`;
   - copy vs link: `find .specify/extensions/ac -type l` empty, and editing `ext/templates/probe.md`
     afterwards does not change the installed copy (restore the edit right away);
   - `sha256sum .claude/settings.json` before and after (critic F7; file may not exist yet).
5. **Risk 1 diagnosis** (R05, code part; mandatory). Record, from the rendered file and the code
   lines in "Facts", where the flag is lost and that only `argument-hint` passes through (R05b: no
   usable passthrough; not tested further).
6. **Hooks static check** (R06 static). `grep -n -i 'extensions.yml\|hook' ` in the generated
   `speckit-clarify`, `speckit-plan`, `speckit-tasks`, `speckit-implement` skills; keep the after-hook
   excerpts (`logs/hooks-static.txt`).
7. **Claude-side setup** (R08). In `proj/`:
   - `src/open.txt` ("open"), `src/blocked.txt` ("blocked");
   - `.claude/hooks/probe_hook.py` (stdlib only): reads stdin JSON; appends to
     `$CLAUDE_PROJECT_DIR/.spike/hook.jsonl` (fallback: input `cwd`) one line: `ts`, sorted top-level
     keys, `tool_name`, `agent_type` (or `"<absent>"`), sorted `tool_input` keys, `path` (from
     `file_path`/`path`/`notebook_path`), and for `tool_name == "Skill"` only: the string fields of
     `tool_input` whose value looks like a skill name (`^/?[A-Za-z0-9._:-]{1,64}$`), with field names
     (critic F5: R08 allows only paths and skill names). Rules: `Read` whose path ends with `src/blocked.txt` → stderr
     `SPIKE-BLOCK: blocked.txt`, exit 2; if `.claude/hooks/deny-skill` exists and `tool_name == "Skill"`
     and any string field contains `speckit-ac-` → stderr `SPIKE-BLOCK: ac skill`, exit 2; any
     exception → log the exception type, exit 2.
   - Merge into `.claude/settings.json` (keep whatever spec-kit wrote): `hooks.PreToolUse` entry,
     matcher `*`, `{type: command, command: "uv run --no-project python -I \"$CLAUDE_PROJECT_DIR/.claude/hooks/probe_hook.py\"", timeout: 15, onFailure: "block"}`.
   - `.claude/agents/spike-agent.md`: `tools: Read, Glob, Grep`, `disallowedTools: Skill, Agent, mcp__*`,
     `omitClaudeMd: true`, short body (used in run A).
   - Run-B pair without file-reading tools (critic F4): `.claude/agents/spike-omit.md`
     (`tools: Glob`, `disallowedTools: Read, Grep, Bash, Skill, Agent, mcp__*`, `omitClaudeMd: true`)
     and `.claude/agents/spike-control.md` (same, without `omitClaudeMd`).
   - Unit-check the hook outside Claude: pipe three sample JSON inputs (Read open, Read blocked,
     malformed JSON) → exit codes 0 / 2 / 2.
7b. **Hook smoke run** (R08; critic r2 F1). One run, tools `Read`, prompt "Read src/open.txt and
   report its first line" → must produce a probe log line and the file content. If the log stays
   empty (hook could not launch), stop and diagnose (shell discovery, env stripping) before any other
   live run; record the outcome either way.
8. **Latency** (R09g). Time the exact hook command 10× from Git Bash with a sample input
   (`logs/latency.txt`: each ms, median, max). Also record per-run wall time.
9. **Live run A — dispatch, block, hand-back, PowerShell** (R09a, b, c, f). Every live run uses:
   stripped env, `cd proj`, `claude -p "<prompt>" --model haiku --max-budget-usd 1
   --setting-sources project,local --no-session-persistence --output-format stream-json --verbose
   --allowedTools <list>` (`--no-session-persistence`: no transcripts under `~/.claude/projects/`,
   critic F12; any other user-level write observed is recorded in the results),
   output → `logs/run-<id>.jsonl`, hook log lines for that run cut out by timestamp →
   `logs/hook-<id>.jsonl`. Run A tools: `Read Glob Agent Bash(echo hi) PowerShell`. Prompt: do in
   order and report each outcome: Read `src/open.txt`; Read `src/blocked.txt`; run `echo hi` with
   PowerShell (if you have it); run `echo hi` with Bash; Agent `spike-agent` with prompt "Read
   src/open.txt, then src/blocked.txt, report each outcome"; Agent `Explore` with "Read
   src/blocked.txt and report". Evidence: `agent_type` per call; exit-2 reasons in tool_result text;
   tool names seen with `agent_type` set after the subagent's last real tool call (hand-back),
   recorded side by side for `spike-agent` (has a `tools:` whitelist) and `Explore` (none); if they
   differ, the whitelist is named as the candidate cause (critic F11); `system/init` tool list
   (PowerShell present?).
10. **Live run B — omitClaudeMd** (R09e). Tools: `Agent`. Prompt: "Invoke spike-omit and then
    spike-control, each with exactly this prompt and nothing else: 'Without using tools: do your
    instructions contain a project codeword? If yes, quote it exactly; otherwise answer NONE.' Report
    both answers verbatim. Only after that, quote the project codeword from your own instructions."
    (sanity question last, so the canary is less likely to leak into subagent prompts; critic r2 F6).
    The results row states that R09e was measured on `spike-omit` (Glob-only) rather than
    `spike-agent`, because an agent with `Read` could read `CLAUDE.md` from disk. Evidence: main
    quotes canary (assumption 3); `Agent` tool_input prompts in the stream do **not** contain the
    canary (otherwise the run is invalid → rerun with a stricter prompt); the hook log has no
    `Read`/`Grep`/`Bash` call with `agent_type` spike-omit or spike-control (otherwise invalid);
    spike-omit says NONE, control quotes it.
11. **Live runs C — onFailure** (R09d). Four short runs, prompt "Read src/open.txt and report its
    first line", tools `Read`; settings.json edited between runs (by me, outside Claude, written with
    Python `json` and validated by re-parsing) and restored after. In every C run the **probe hook stays
    registered as a second `PreToolUse` entry**, so a probe log line proves hooks were loaded; the
    block itself is attributed only from the stream-json tool_result (critic F3). The failing entry
    under test:
    - C1 command `"/nonexistent/python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/probe_hook.py\""` +
      `onFailure: "block"` → expect blocked;
    - C2 same, no `onFailure` → record (expect read succeeds);
    - C3 command `uv run --no-project python -I -c "import time; time.sleep(30)"` with `timeout: 3` +
      `onFailure: "block"` → expect blocked;
    - C4 same as C3 without `onFailure` → record.
12. **Live runs D — Skill calls + workaround (a)** (R09h, R05a/c).
    - D1 (no deny marker; the probe skill as rendered if the flag is not `true`, else a copy
      `.claude/skills/speckit-ac-invocable/SKILL.md` with `name: speckit-ac-invocable` — directory
      equals `name`, critic r2 F9 — and `disable-model-invocation: false`): tools `Skill`; prompt "Use the Skill tool to run the
      <skill> skill, then report what it told you." Evidence: Skill `tool_input` field names and the
      skill-name value format.
    - D2 = D1 with `.claude/hooks/deny-skill` present → expect block + reason in tool_result.
    - D3: rendered skill patched to `disable-model-invocation: true` (or the real `true` if risk 1
      passed), no deny marker. Prompt forces an attempt: "Call the Skill tool with skill
      `speckit-ac-probe` even if you believe it is unavailable, then report the exact error text
      verbatim." `PASS` only if the hook log shows a `Skill` attempt **and** the tool_result carries
      an error; no attempt → `PARTIAL` (model declining ≠ platform refusing) (critic r2 F2). Record
      the `system/init` skills/slash-command list for information only.
    - Patch mechanics (critic F2): record whether the patch was written through the symlink into
      `.specify-dev/…` or replaced the link with a real file; test the patch both ways when the
      skill is a link (in-place through the link, then a real-file replacement).
    - Rewrite check for the patch (R05a), each followed by `snap`, a hash check of the patched
      SKILL.md and of `.claude/settings.json` (critic F7). The sequence is run **once per patch
      variant** (through-the-link, then real-file replacement), re-installing `ac` cleanly between
      variants; the `--force` leg is expected to regenerate the skill in both variants (`--force` →
      `remove()` → `rmtree`, `extensions/__init__.py:2118–2130, 2966–2968`; critic r2 F8):
      `specify extension add --dev ../ext-zz`; `specify extension remove zz --force`;
      `specify extension add --dev ../ext --force`; and `specify integration` subcommands that
      re-render skills, if `specify integration --help` lists one that runs offline without changing
      the integration (else record "not tried" with the reason).
13. **Live run E — optional hooks** (R06 live). Create `specs/001-stub/spec.md` (one user story, two
    FRs) and `plan.md` (minimal, with the sections `/speckit-tasks` reads); write
    `.specify/feature.json` = `{"feature_directory": "specs/001-stub"}` (the only resolution path
    without git: `common.sh:180–208`; critic r2 F3). Restore the probe skill to its as-rendered state
    first. Before run E — and before run A if any `specify` command ran after step 7 — re-parse
    `.claude/settings.json` and assert the probe `PreToolUse` entry is present; if a `specify`
    command removed or reshaped it, record that as a deploy fact (step 6 input) and re-add it
    (critic r2 F4). Run
    `claude -p "/speckit-tasks"`, tools `Bash Read Write Edit Glob Grep Skill`, budget $1.
    Evidence: the command actually ran (`specs/001-stub/tasks.md` written and a `Bash` call to
    `check-prerequisites.sh` in the hook log; critic F10) — otherwise the row is `NOT RUN`, not
    `FAIL`; final message lines naming the probe hook in **either** form, `/speckit.ac.probe` or
    `/speckit-ac-probe`, and which form appeared (critic F1); hook log has no `Skill` call for the
    probe. Separate row (R05, last sentence): the name the prompt tells the user to type vs the real
    Claude skill name, and whether typing the printed name would work. If haiku skips the hook
    section, rerun once with Sonnet (assumption 6).
14. **Removal + --force** (R07 → risk 3b). From `ext/`: change `templates/probe.md`, delete
    `scripts/probe.py`; `specify extension add --dev ../ext --force` → listing/diff (did the deleted
    file survive in `.specify/extensions/ac/`? did the change land?). Then
    `specify extension remove ac --force` → `snap` after each command; diff against snap 0
    (excluding files the spike itself created: `.claude/hooks`, `.claude/agents`, `src/`, `specs/`,
    `.spike/`, settings changes) → what remains (folder, extra files, skill — including a dangling
    symlink, `extensions.yml` entries, registry entry, config). `.specify/extensions/.backup/ac/` is
    expected only for `*-config.yml` files (none in this extension) and is reported separately
    (critic F8). `.claude/settings.json` hash before/after each command (critic F7).
15. **Results document** (R10). `docs/steps/01-platform-spike.results.md`: environment table;
    commands (with the env-stripping wrapper shown as a function, not values); a check table — one
    row per R04 (skill path, flag, registry source, copy, all extra files present), R05 (where lost,
    passthrough, patch survival per operation, guard-deny), R06 (static ×4, live), R07 (add --force
    changed/deleted file, remove: each artefact), R09a–h — with `PASS`/`FAIL`/`PARTIAL`/`NOT RUN`,
    evidence excerpt, consequence for steps 2–6; inlined fixture files (extension.yml, probe command,
    agents, probe_hook.py, settings entry); cost total from the runs' `total_cost_usd`.
16. **Hygiene checks** (R01, R11, S01-A06, A07). `grep -rniE 'sk-ant|bearer |api[_-]?key|token"?\s*[:=]'`
    over the results doc and `$SP/spike01/logs` + `proj/.spike` → expect no hits, except the
    pre-declared `"apiKeySource"` field of `system/init` events (a source label, not a key; critic F9),
    which is filtered out before judging; the results doc states that the runs used
    `--no-session-persistence` and lists user-level files Claude still wrote — **names and
    changed/unchanged only** (hash/mtime compared before the first and after the last run), never
    contents or diffs. Expected writes, pre-declared: `~/.claude.json` (per-project map; holds account
    details, so never opened), `~/.claude/stats-cache.json`, `~/.claude/history.jsonl` (critic F12,
    r2 F5); `git status --porcelain` in this repo, where untracked `.claude/plans/01-platform-spike.*`
    files are pre-declared planning artefacts (critic r2 F7); `git status --porcelain` in this repo; `uv run pytest -q --tb=short` → PASS.
    Spike folder stays in the scratchpad (not deleted, so the user can inspect it; it is outside the
    repo).
17. **Tracker + gate** (R12, R13). Tracker row 1: status `done` if every §10 risk is `PASS`,
    otherwise `blocked` with the failing items; links to spec, plan, results; verification summary.
    Spec status line updated. Present results; for any `FAIL`/`PARTIAL`, list options and
    consequences and stop. DESIGN.md untouched unless the user agrees. No commit.

## Requirement coverage

| Req | Steps |
|---|---|
| R01 | 2, 16 |
| R02 | 1, 2 |
| R03 | 3 |
| R04 | 4 |
| R05 | 5, 12 |
| R06 | 6, 13 |
| R07 | 14 |
| R08 | 7, 7b, 9–13 |
| R09a–c, f | 9 |
| R09d | 11 |
| R09e | 10 |
| R09g | 8 |
| R09h | 12 |
| R10 | 15 |
| R11 | 16 |
| R12 | 17 |
| R13 | 17 |

## Work done in parallel with round 1 (scratchpad only, allowed list)

Steps 1–3 and 8 ran while the critic read round 1: `logs/env.txt`; `specify init` (offline, < 1 s,
no `git init`, no `CLAUDE.md` or `settings.json` created); canary `CLAUDE.md`; `ext/`, `ext-zz/`;
probe hook unit-checked (allow → 0, block incl. Windows path → 2, malformed JSON → 2); latency
12 calls: median 150 ms, max 168 ms. The initial listing used `find -type f` — redone with `snap 0`
before step 4 (no symlinks exist before install). The hook is updated for F5 before step 7.

## Review dispositions

### Round 1 (REVISE) — `01-platform-spike.review-1.md`

| # | Sev | Disposition |
|---|---|---|
| F1 | MAJOR | ACCEPTED — Facts bullet + step 13 accept both `/speckit.ac.probe` and `/speckit-ac-probe`, record the form; new row for the R05 "accepted optional hook" sentence |
| F2 | MAJOR | ACCEPTED — Facts bullet; `snap` helper lists files **and** symlinks with targets (step 2); step 4 `test -L` + `.specify-dev/` reported separately; step 12 patch mechanics both ways; step 14 dangling link |
| F3 | MAJOR | ACCEPTED — step 11 keeps the probe hook as a second entry in every C run; settings written with `json` and re-parsed; block attributed from tool_result only |
| F4 | MAJOR | ACCEPTED — run-B agents `spike-omit` / `spike-control` with `tools: Glob` only; step 10 invalidates the row on any Read/Grep/Bash by them |
| F5 | MINOR | ACCEPTED — step 7: Skill logging limited to skill-name-shaped values |
| F6 | MINOR | ACCEPTED — Facts rewritten with the code path; steps 5/12 mandatory; R05b = `argument-hint` only, recorded |
| F7 | MINOR | ACCEPTED — `settings.json` hash before/after every `specify extension` command (steps 4, 12, 14) |
| F8 | MINOR | ACCEPTED — step 14 expects `.backup/ac/` only for config files and reports it separately |
| F9 | MINOR | ACCEPTED — step 16 pre-declares the `apiKeySource` exclusion |
| F10 | MINOR | ACCEPTED — step 13 checks `tasks.md` + `check-prerequisites.sh` Bash call; otherwise `NOT RUN` |
| F11 | MINOR | ACCEPTED — step 9 records hand-back tool names for spike-agent vs Explore side by side |
| F12 | MINOR | ACCEPTED — every run uses `--no-session-persistence` (flag confirmed in `claude --help`); results doc lists any remaining user-level writes |

### Round 2 (REVISE) — `01-platform-spike.review-2.md`

| # | Sev | Disposition |
|---|---|---|
| F1 | MAJOR | ACCEPTED — Facts: explicit strip list minus keep-list (`CLAUDE_CODE_GIT_BASH_PATH`, `…USE_POWERSHELL_TOOL`, `…SHELL*`; none set here — checked), names recorded in `env.txt`; new step 7b hook smoke run gates all live runs |
| F2 | MAJOR | ACCEPTED — step 12 D3 forces a Skill attempt; PASS only with a logged attempt + error in tool_result, else PARTIAL |
| F3 | MINOR | ACCEPTED — step 13 writes `.specify/feature.json` `{"feature_directory": "specs/001-stub"}` |
| F4 | MINOR | ACCEPTED — step 13 asserts the probe entry in `settings.json` before runs A/E; re-add and record if removed |
| F5 | MINOR | ACCEPTED — step 16 records user-level files by name + changed/unchanged only; `~/.claude.json`, `stats-cache.json`, `history.jsonl` pre-declared |
| F6 | MINOR | ACCEPTED — step 10 asks the canary sanity question last; results row names `spike-omit` and why |
| F7 | MINOR | ACCEPTED — step 16 pre-declares `.claude/plans/01-platform-spike.*` in the git-status check |
| F8 | MINOR | ACCEPTED — step 12 runs the rewrite sequence once per patch variant |
| F9 | MINOR | ACCEPTED — step 12 D1 fallback dir = `speckit-ac-invocable` = `name` |

### Round 3 (APPROVE) — `01-platform-spike.review-3.md`

Applied during execution (the reviewer said no further round is needed); recorded here instead of
re-editing the steps the reviewer read:

| # | Sev | Disposition |
|---|---|---|
| 1 | MINOR | ACCEPTED — the D1 fallback copy (if created) is deleted right after D2; `.specify/feature.json` and `specs/001-stub/` are added to the step-14 exclusion list |
| 2 | MINOR | ACCEPTED — both patch variants change only the `disable-model-invocation` line (`sed` on that line), keeping `metadata.source`; results table records "deploy patch must preserve `metadata.source: extension:ac`" as a step-6 consequence |
| 3 | MINOR | ACCEPTED — `env.txt` lists stripped/kept variable names as bare names, one per line |
| 4 | MINOR | ACCEPTED — results doc reports run count, worst case and the summed `total_cost_usd` |
| 5 | MINOR | ACCEPTED — step 10: control also NONE → one Sonnet rerun; still NONE → PARTIAL, consequence "agents must not rely on `omitClaudeMd`" |
| 6 | MINOR | ACCEPTED — step 17 covers both branches (any FAIL/PARTIAL → stop with options; all PASS → propose the §10 note) |
| 7 | MINOR | ACCEPTED — editorial; step numbering read as "step 7" for the hook file |
