# Step 1 — Platform spike (gate)

**Status:** done, gate decisions made (2026-11-07; results in [01-platform-spike.results.md](01-platform-spike.results.md)) · **Tracker row:** 1 · **Source of truth:** `docs/DESIGN.md`

## Goal

Before any workflow code is written, check on this machine's real tool versions the platform
behaviours that DESIGN §10 lists as risks (plus a few that steps 2–6 depend on), using a throwaway
spec-kit project and a one-command test extension. The output is a **findings document**, not code.
If a risk fails, stop and decide with the user; DESIGN changes only with their agreement.

## Context

- DESIGN §10 risks: (1) `disable-model-invocation: true` kept in generated SKILL.md; (2) optional
  hooks in `extensions.yml` prompt after clarify / plan / tasks / implement; (3) extra payload files
  land in `.specify/extensions/ac/` and are removed by `specify extension remove`; (4) Claude Code
  support for `omitClaudeMd`, hook `onFailure: "block"`, `agent_type` in hook input, and the
  `SubagentHandback` tool name.
- Facts observed while drafting (to be confirmed by the spike, not assumed):
  - spec-kit 1.0.2's Claude integration (`specify_cli/integrations/claude/__init__.py`) builds a
    **new** skill frontmatter (`build_skill_frontmatter(name, description, source)`) and then injects
    `user-invocable` and `disable-model-invocation: false` **only if the key is absent**. Whether a
    command's own `disable-model-invocation: true` survives into the rendered skill is the open
    question for risk 1.
  - The core `git` extension declares hooks as `hooks.<event>: {command, optional, prompt,
    description}`.
  - The CT project already registers its guard with `"onFailure": "block"`, `"timeout": 15` and the
    command `uv run --no-project python -I "$CLAUDE_PROJECT_DIR/.claude/hooks/guard.py"`.
- Tools on this machine: specify 1.0.2, Claude Code 2.1.318, uv 0.11.26, .NET SDK 10.0.403,
  Windows 11 (Git Bash for hooks). **No `python`, `python3` or `py` on PATH**; Python exists only as
  uv-managed CPython 3.14.6, so `uv run --no-project python -I` is the realistic hook command here.

## Requirements

### Setup (throwaway, outside this repo)

- **S01-R01** All spike files live in the session scratchpad: the throwaway project, the test
  extension, logs. Nothing is written to `<original project>\`, nothing is installed globally (no
  `uv tool install`, no Python install, no change to `~/.claude/` or other user-level settings). In
  this repo, only `docs/steps/01-platform-spike.results.md`, this spec's status line and
  `docs/steps/TRACKER.md` change (plus DESIGN.md only per S01-R12).
- **S01-R02** Throwaway project created with `specify init <dir> --integration claude` in
  non-interactive mode (exact flags taken from `specify init --help`), plus a `CLAUDE.md` holding a
  **canary** line (a made-up codeword) used by S01-R09e. Record the versions of specify, Claude Code,
  uv, Python and the OS.
- **S01-R03** Test extension, id **`ac`** (the real id, so command and skill names are realistic),
  `schema_version: "1.0"`, `license: MIT`:
  - one command `speckit.ac.probe` (`commands/speckit.ac.probe.md`) whose frontmatter contains
    `description` and `disable-model-invocation: true`;
  - optional hooks `after_clarify`, `after_plan`, `after_tasks`, `after_implement` → `speckit.ac.probe`,
    each `optional: true` with a `prompt` and `description`;
  - extra payload files that spec-kit does not know about: `agents/spike-agent.md`,
    `hooks/probe_hook.py`, `scripts/probe.py`, `templates/probe.md`, `README.md`.

### spec-kit behaviour (risks 1–3)

- **S01-R04** `specify extension add --dev <ext dir>`: record the generated skill's path and name
  (expected `.claude/skills/speckit-ac-probe/SKILL.md`), its complete frontmatter, and whether
  `disable-model-invocation: true` survived (**risk 1**). Record the registry entry (expected
  `"source": "local"`), whether the extension folder is **copied** (not linked) to
  `.specify/extensions/ac/` with every extra file (**risk 3a**), and what `.specify/extensions.yml`
  holds for the four hooks.
- **S01-R05** If risk 1 fails: locate where the flag is lost (file and line in `specify_cli`) and try,
  **without modifying spec-kit**, the candidate workarounds: (a) patching the generated SKILL.md
  after install (the future deploy step) and checking which later `specify` operations rewrite it
  (adding/removing another extension, `extension add --force` of `ac`); (b) any frontmatter or
  manifest field that spec-kit passes through; (c) the guard denying a main-agent `Skill` call whose
  skill name starts with `speckit-ac-` (evidence from S01-R09h). Record results; choose nothing — the
  choice goes to the user (S01-R12). Whatever the outcome, record how an accepted optional hook
  behaves when the skill is not model-invocable (the user has to type the command), as input for the
  hook prompt wording in step 4.
- **S01-R06** Hooks (**risk 2**):
  - static: the generated core skills `speckit-clarify`, `speckit-plan`, `speckit-tasks`,
    `speckit-implement` contain the after-hook instructions that read `.specify/extensions.yml`;
  - live: one headless run of `/speckit-tasks` on a stub feature (`specs/001-stub/spec.md` +
    `plan.md`) whose final output shows the optional hook for `/speckit-ac-probe` as a prompt and does
    **not** run it.
- **S01-R07** Removal (**risk 3b**): `specify extension remove ac` (non-interactive flags as available).
  Record which of these are removed and which remain: the extension folder with its extra files, the
  generated skill, the `extensions.yml` hook entries, the registry entry, any config files.
  Also record what `specify extension add --dev --force` does to a file deleted from the source and a
  file changed in it (input for `upgrade`, DESIGN §9).

### Claude Code behaviour (risk 4)

- **S01-R08** Live checks run headless in the throwaway project with `claude -p`, using only the
  throwaway project's settings (`--setting-sources project,local`, so the user's global hooks do not
  interfere), `--output-format stream-json --verbose`, an explicit `--allowedTools` list (never
  `bypassPermissions`), a cheap model, and `--max-budget-usd` on every run. A probe hook is
  registered in the throwaway `.claude/settings.json` as `PreToolUse`, matcher `*`, command
  `uv run --no-project python -I "$CLAUDE_PROJECT_DIR/.claude/hooks/probe_hook.py"`,
  `"onFailure": "block"`, a timeout. The probe hook (stdlib only) appends one JSON line per call —
  top-level input keys, `tool_name`, `agent_type` (or its absence), timestamp, and the **keys** of
  `tool_input` — and blocks (stderr reason, exit 2) any `Read` of `src/blocked.txt` and, when a
  marker file is present, any `Skill` call for a skill named `speckit-ac-*`. The log contains no
  prompt text or tool input values except file paths and skill names.
- **S01-R09** Using a custom agent `spike-agent` (`.claude/agents/spike-agent.md`, with `tools`,
  `disallowedTools`, `omitClaudeMd: true`) and a control agent without `omitClaudeMd`, record:
  - a. the hook fires for the main agent and inside the subagent; the exact `agent_type` value for
    `spike-agent` and for the built-in `Explore`; `agent_type` absent in the main conversation;
  - b. exit 2 blocks the `Read` for both main agent and subagent, and the model receives the reason;
  - c. the tool name the hook sees when a subagent hands its result back (DESIGN expects
    `SubagentHandback`); list every tool name observed;
  - d. `onFailure: "block"`: with the command pointing at a missing interpreter, a tool call is
    blocked; control run without `onFailure`: not blocked;
  - e. `omitClaudeMd: true`: the subagent cannot quote the canary codeword, the control agent can;
  - f. on Windows, a `PowerShell` tool call (if the tool is available headless) fires the same hook
    with `tool_name` `PowerShell`;
  - g. latency of the hook command (`uv run --no-project python -I …`): median and max over at least
    10 calls;
  - h. `Skill` tool calls: with `speckit-ac-probe` model-invocable (as rendered by spec-kit, or a
    copy with `disable-model-invocation: false`), ask the main agent to use it and record the exact
    `tool_input` field that carries the skill name and its value format (with or without a leading
    `/`, namespaced or not); then, with the deny marker present, record that exit 2 blocks the call and
    the model receives the reason. If the flag survived (risk 1 `PASS`), also record that the model
    cannot invoke the skill at all.

### Findings and gate

- **S01-R10** `docs/steps/01-platform-spike.results.md`: environment and versions; the exact commands
  run; a table with one row per check (risks 1–4 split into their parts, plus S01-R07 `--force` and
  S01-R09f–h) → `PASS` / `FAIL` / `PARTIAL` / `NOT RUN`, evidence (key output lines or file excerpts),
  and the consequence for steps 2–6; the test extension's and probe hook's contents inlined (short) so
  the spike can be repeated. No secrets, tokens or account details in the document or the logs.
- **S01-R11** Throwaway files are deleted at the end (or left only in the scratchpad). No files under
  `src/` or `tests/` change; `uv run pytest -q --tb=short` still passes.
- **S01-R12** Gate: if any DESIGN §10 risk is `FAIL` or `PARTIAL`, stop and present the options with
  their consequences. DESIGN.md is changed only after the user agrees (decision log + §10). If all
  pass, propose (not apply) a §10 note "verified 2026-11-07 on specify 1.0.2 / Claude Code 2.1.318".
- **S01-R13** `docs/steps/TRACKER.md` row 1 updated (status, links, verification summary, open items).
  No commit unless the user asks.

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S01-A01 | The results document exists and has a row with a status and evidence for every check in R04–R09 | R10 |
| S01-A02 | Risk 1: the rendered `SKILL.md` frontmatter is quoted in the results; status follows from it | R04, R05 |
| S01-A03 | Risk 2: static excerpt from the four core skills + the live `/speckit-tasks` output line(s) showing the `/speckit-ac-probe` prompt | R06 |
| S01-A04 | Risk 3: before/after file listings of `.specify/extensions/ac/`, `.claude/skills/`, `extensions.yml` and the registry for add, `--force` re-add and remove | R04, R07 |
| S01-A05 | Risk 4: probe-hook log excerpts for R09a–c, f, g, h; run outputs for R09d (both runs), R09e (both agents) and R09h (allowed and denied `Skill` call) | R05, R08, R09 |
| S01-A06 | `git status` in this repo shows changes only to the results doc, this spec, the tracker (and DESIGN.md only with recorded user agreement); `uv run pytest -q --tb=short` passes | R01, R11, R13 |
| S01-A07 | `grep` of the results document and spike logs for token/key patterns finds nothing | R08, R10 |

## Out of scope

- The real `extension.yml`, commands, agents (steps 3–4), the guard (step 2), deploy and CLI
  subcommands (step 6), `/speckit-ac-init` (step 5).
- .NET build, Reqnroll, `ilspycmd`, reference-assembly export (steps 5 and 7).
- Workspace trust: headless `claude -p` skips the trust dialog, so trust-dependent behaviour is not
  checked here; it stays in the live smoke test (CT doc §6.8) of steps 7–8.
- Interactive (non-headless) Claude Code sessions; other OSes than this Windows machine.
- Any change to spec-kit itself or upstream issues/PRs.

## Decisions taken in this spec (confirm on approval)

1. **Live checks run headless (`claude -p`) under your Claude account.** Small cost: cheap model,
   `--max-budget-usd` per run (≤ $1), roughly 8–10 runs. The alternative is that you run an
   interactive session with prompts I give you.
2. **Spike assets are throwaway** (scratchpad only). The results doc inlines the small fixture files,
   so the spike can be repeated without keeping code in the repo.
3. **Hook command under test = `uv run --no-project python -I`** (the only working Python command on
   this machine, same as CT). Other commands (`python`, `py -3`) are step 5's detection work.
4. **Risk 2 is checked live only via `/speckit-tasks`** (mechanical, no clarifying questions). Clarify,
   plan and implement are checked statically (same hook block in their skills).
