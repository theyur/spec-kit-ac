# spec-kit-ac — design decisions

**Status:** agreed with the user on 2026-11-07, before any code. This file is the source of truth for
*what* the package is. Change a decision only with the user's explicit agreement, and record it in
the "Decision log" at the end.

## 1. Purpose

A spec-kit extension for **.NET** projects that adds an isolated acceptance-test (AC) workflow:

1. Acceptance criteria are written **before** implementation, reviewed by a human, and **locked**.
2. An isolated subagent translates them into Reqnroll `.feature` files and never guesses.
3. The implementation is written normally (`/speckit-implement`), with its own unit tests.
4. An isolated subagent writes the step definitions **without seeing the implementation or the unit
   tests**. It sees only the spec inputs, the AC, golden samples, and the **public API** taken from
   reference assemblies (listed as C# stubs by `ilspycmd`).
5. The AC tests run against the real implementation. An isolated judge (also blind to the
   implementation) classifies every failure.

Isolation is enforced **technically** (a fail-closed `PreToolUse` guard, tool lists, fixed prompt
templates, deterministic scripts as the only channel, content-hash change checks, `omitClaudeMd`),
not only by instructions.

The original design and a working implementation exist for one project (CT):

- `docs/reference/WORKFLOW-SETUP-CT.md`: the original setup document. Sections 0–9 are the generic
  method; section 10 is CT-specific and must **not** be copied.
- `<original project>\.claude\` (read-only source to port from): `hooks/guard.py`, `hooks/test_guard.py`,
  `scripts/*.py` (10 scripts), `agents/ac-*.md` (3), `skills/ac-*/SKILL.md` (3). About 1,400 lines,
  mostly config-driven already.
- `~\.claude\skills\speckit-critic\SKILL.md`: the critic skill to port.

## 2. What we may assume about a target project

**Only:** spec-kit is installed (`.specify/`, `specs/NNN-*/`, `.specify/memory/constitution.md`,
`.specify/feature.json`, `.specify/extensions.yml`), there is a `CLAUDE.md`, and the product is a
.NET solution (`.sln` or `.slnx`).

**Everything else varies** and is detected or asked once by `/speckit-ac-init`, then stored in
`.workflow/config.json`: AC-surface projects, test framework (xUnit v2/v3, NUnit, MSTest) and runner
(VSTest or Microsoft.Testing.Platform), Python command (`python3`, `python`, `py -3`,
`uv run --no-project python`), OS, existing hooks/settings, `InternalsVisibleTo`, extra spec inputs.
Never hard-code SPEC.md, ARCHITECTURE.md, CONTEXT.md or any other non-spec-kit file.

**v1.0 developer environment (fixed):** Windows + uv + PowerShell 7, with spec-kit initialised with
`--script ps` (`"script": "ps"` in `.specify/init-options.json`). The guard and scripts run via uv
(`uv run --no-project python -I`); no Python on PATH is required. Other OSes, spec-kit `sh`/`py`
scripts and PATH-Python detection are deferred; known traps are listed in
`docs/steps/01-platform-spike.results.md` (N1–N3 and the decision-4 follow-up).

## 3. AC source (option B)

- Per feature: `specs/NNN-x/acceptance.md`, Gherkin-like, written for humans. Items carry IDs and
  traceability: `AC-001 (FR-003; US1-AS2)`. Every value is a concrete literal.
- spec-kit's own `spec.md` scenarios stay abstract; `acceptance.md` makes them concrete.
- Lock group `sources` = `acceptance.md` + the feature's golden samples. The lock **also stores the
  hash of `spec.md`**: if `spec.md` changes after locking, later steps stop and ask the user to
  confirm the AC are still valid or to unlock / edit / relock.
- Coverage rule: every FR has at least one AC item; every spec scenario is covered or listed as
  "not testable through the API" with a reason.

## 4. Spec inputs for the AC subagents (per feature)

- Always: `specs/NNN/spec.md`, `.specify/memory/constitution.md`, `specs/NNN/acceptance.md`.
- Optional: extra project documents listed in config (asked at init; the main agent never adds them).
- Never: `plan.md`, `research.md`, `data-model.md`, `contracts/`, `tasks.md`, `CLAUDE.md`.
- Rules that live only in `CLAUDE.md` never reach the subagents. The draft phase flags them; init
  offers a testability section through `/speckit-constitution` (never edits the constitution itself).

## 5. Flow inside spec-kit

```
/speckit-specify → /speckit-clarify → (/speckit-ac-critic spec)
→ /speckit-ac-translate   phase 1: draft acceptance.md (+ coverage table) → (/speckit-ac-critic ac) → user review → lock sources
→ /speckit-ac-translate   phase 2: isolated translator → skip/fix/stop → (/speckit-ac-critic features) → approve → lock features
→ /speckit-plan → /speckit-tasks → /speckit-implement
→ /speckit-ac-tests-write → /speckit-ac-tests-analyze
```

After every step the agent reports and **stops**; it never starts the next step on its own.

## 6. Commands (skills) — spec-kit extension id `ac`

| Command | Skill | Notes |
|---|---|---|
| `speckit.ac.init` | `/speckit-ac-init` | Detect + ask, scaffold the AC project, write config, verify. Required once per project. |
| `speckit.ac.translate` | `/speckit-ac-translate` | Two phases (draft, translate), each ends with a stop. |
| `speckit.ac.tests-write` | `/speckit-ac-tests-write` | Per feature; passes the judge's feedback; `fresh` argument. |
| `speckit.ac.tests-analyze` | `/speckit-ac-tests-analyze` | All features by default, `--current` to narrow. |
| `speckit.ac.critic` | `/speckit-ac-critic` | Port of speckit-critic. Stages `spec`, `plan`, `tasks`, plus `ac` and `features`. |

Optional hooks in `extension.yml` (offered, never auto-run): `after_clarify` → translate and critic;
`after_plan` / `after_tasks` → critic; `after_implement` → tests-write.

## 7. Critic AC stages

- `ac`: reviews `acceptance.md` before `sources` is locked. Reference material: `spec.md`,
  constitution, configured spec inputs only; **no code reading** (prompt rule; not enforceable by
  the guard, since the critic has main-agent permissions). Checks coverage, concreteness, consistency
  with the spec, boundary/edge-case discrimination. Normal revise loop (max 3 passes).
- `features`: compares each `.feature` scenario with its `acceptance.md` item before `features` is
  locked. **Report-only**: nobody may edit `.feature` files; findings go to the user (approve /
  re-translate / fix `acceptance.md`).

## 8. Multi-feature model

- One AC project for all features, outside the solution file.
- Layout inside the AC project: `Features/F00N/`, `Samples/F00N/`, `StepDefinitions/F00N/`,
  `Support/F00N/`, `Support/Shared/`.
- Per-feature records: `specs/NNN-x/acceptance.md`, `specs/NNN-x/ac/{sources.lock,features.lock}`,
  `specs/NNN-x/ac/runs/{translate-NNN,run-NNN/analyze-K}/`.
- Tags: feature tag `@F00N` (added by the translator, enforced by `check_features.py`) plus `@AC-NNN`
  (unique within a feature). Reports key on `F00N/AC-NNN`.
- Reference assemblies + API listings: **one repo-level folder shared by all features**,
  `refsDir` in `.workflow/config.json` (default `artifacts/refs/`, git-ignored), regenerated by the
  export script at the start of translate and tests-write (as in CT).
- Writer binds with `[Scope(Tag = "F00N")]`; shared helpers only in `Support/Shared/`.
- Features are `specs/NNN-name` folders (sequential numbering only in v1.0); the tag is `F` + `NNN`.
- **Active run:** the run scripts (`new_run.py`, `new_analyze.py`) write `.workflow/active-run.json`
  (role, feature, run, analyze) right before a subagent starts. The guard pins every AC-role rule to
  that feature and run, and denies AC-role calls without a matching marker.
- Visibility: the translator sees only its own feature; the writer sees its own feature's spec and AC
  plus all AC project folders; the judge sees every feature's `spec.md` and `acceptance.md`.
- Writer may make **minimal compile fixes** in other features' step definitions after an API change,
  and must list each one in its report.
- `tests-analyze` runs all features by default; results are grouped "current feature" vs
  "regression". A failed build reports only error counts and codes (original rule).
- Judge verdicts: `TRANSLATION_FAULT`, `TEST_FAULT`, `IMPLEMENTATION_FAULT`, `SPEC_AMBIGUITY`,
  `UNEXPRESSIBLE`, `INCONCLUSIVE`, and new **`SUPERSEDED`** (an earlier feature's AC conflicts with a
  later feature's `spec.md`; the judge reads the failing scenario's feature spec plus the current
  feature's spec).

## 9. Packaging and distribution

- Own repository (this one). Habit Tracker (`<habit-tracker>`) is only
  the first consumer.
- A **native spec-kit extension** (`extension.yml`, id `ac`). spec-kit 1.0.2 facts checked on
  2026-11-07: command names must match `^speckit\.([a-z0-9-]+)\.([a-z0-9-]+)$`; the extension folder
  is copied to `.specify/extensions/<id>/`; `--dev` installs are recorded as `"source": "local"`;
  `--from` accepts only http(s) URLs; there are **no install/remove lifecycle hooks**.
- Therefore a **deploy step** handles the Claude-side files spec-kit doesn't know about: the three
  agents in `.claude/agents/`, the guard registration in `.claude/settings.json` (merged, added last,
  `onFailure: "block"`), marked blocks in `CLAUDE.md`, and a deploy manifest with hashes (`.workflow/deploy.json`,
  committed; not in the extension folder, which `upgrade` and `uninstall` replace). The marked
  blocks in `.gitignore` and `.gitattributes` depend on `acProjectDir` and `refsDir`, so
  `/speckit-ac-init` writes them (step 5 decision); `uninstall` removes them with the same helper.
- **Human-only `/speckit-ac-*` skills (two layers, step 1 result):** spec-kit 1.0.2 drops
  `disable-model-invocation` from extension skills, so the model could start them itself.
  1. The deploy step **patches** `disable-model-invocation: true` into every generated
     `.claude/skills/speckit-ac-*/SKILL.md`, changing only that key (`metadata.source` must stay:
     spec-kit's uninstall uses it). `doctor` checks it; `upgrade` re-applies it after its
     `extension add --force`. A user's own `specify integration upgrade` or `extension add --force`
     reverts it silently. `--dev` installs make these `SKILL.md` files **symlinks** into
     `.specify/extensions/ac/.specify-dev/`; the deploy step replaces each link with a real file
     (content read through the link, flag patched) and records its hash in the deploy manifest.
     Step 6 verifies what git records, what a clone gets, and that `specify extension remove`
     still deletes the real files.
  2. The **guard** blocks (exit 2) a main-agent `Skill` call whose `tool_input.skill` starts with
     `speckit-ac-`, so the rule holds even when the patch was reverted. Users still run the skills by
     typing `/speckit-ac-…`.
- Distributed as a Python CLI `speckit-ac` (mirrors `specify`):
  `uv tool install speckit-ac --from git+https://github.com/<owner>/spec-kit-ac`.
  - `install`: prerequisite checks → `specify extension add --dev <bundled payload>` → deploy.
  - `uninstall`: undo deploy (keep user-modified files, warn) → `specify extension remove ac`.
  - `upgrade`: re-add with `--force` + redeploy. `doctor`: hashes, guard registration, Python command.
- **Supported host: interactive Claude Code only** (terminal, desktop app, IDE). Headless `claude -p`
  is not supported (no `SubagentHandback` tool, no workspace trust). The guard **allows
  `SubagentHandback`** for the three AC roles — the subagents' only reporting channel — with CT's
  content check on the hand-back text, and never relies on seeing it. Confirmed in the interactive
  smoke test (steps 7–8).
- After install, the target repo is self-contained: teammates don't need the uv tool to use the flow.
  The guard command in the committed `settings.json` must **never** point into the uv tool's
  environment. Install writes it before any config exists, so it uses the v1.0 Python command
  (`uv run --no-project python -I`, the same constant init writes into the config); `doctor` checks
  that the config's `python` matches it. Hook `timeout` 30 s (a cold uv start is slower than the
  spike's 15 s, and a timeout blocks the call).
- Uninstall takes the guard registration off first (a registered guard whose file is gone blocks every
  call), keeps agents the user changed, and removes spec-kit's empty bookkeeping (`.registry` without
  extensions, `extensions.yml` in its empty state, empty `.backup/`) only where it did not exist before
  install, so a fresh project round-trips byte for byte. `doctor` never writes and runs no dotnet.
- Runtime code (guard, scripts, CLI): Python 3, standard library only. pytest for development only.

## 10. Known risks to verify early (step 1 spike)

- Whether spec-kit preserves `disable-model-invocation: true` in generated SKILL.md frontmatter.
- Whether optional hooks in `extensions.yml` prompt as expected after clarify / plan / tasks /
  implement.
- Whether extra payload files (agents, scripts, templates) land in `.specify/extensions/ac/` and are
  removed by `specify extension remove`.
- Current Claude Code support for `omitClaudeMd`, hook `onFailure: "block"`, `agent_type` in hook
  input, and the `SubagentHandback` tool name (the CT doc relied on Claude Code 2.1.271+ / 2.1.295+).

**Step 1 results (2026-11-07, specify 1.0.2 / Claude Code 2.1.318, headless; details in
`docs/steps/01-platform-spike.results.md`):** flag dropped (FAIL → two-layer workaround in §9);
optional hooks prompt and are not auto-run (PASS); payload files copied and removed (PASS);
`omitClaudeMd`, `onFailure: "block"` (missing interpreter and timeout), `agent_type` (PASS);
no hand-back tool call reached the hook in headless mode (PARTIAL → interactive-only support, guard
allows `SubagentHandback`, §9).

## Decision log

| Date | Decision |
|---|---|
| 2026-11-07 | Option B: separate locked `acceptance.md` per feature, drafted inside `/speckit-ac-translate`. |
| 2026-11-07 | Target projects: assume only spec-kit + .NET + CLAUDE.md. |
| 2026-11-07 | Own repo; native spec-kit extension `ac` + deploy step; `speckit-ac` CLI via `uv tool install`. |
| 2026-11-07 | Critic ported as `/speckit-ac-critic`, with `ac` (revise loop) and `features` (report-only) stages. |
| 2026-11-07 | AC runs cover all features by default; `@F00N` tags; writer compile fixes across features; `SUPERSEDED` verdict. |
| 2026-11-07 | Defaults: runs under `specs/NNN/ac/runs/`; one AC project for all features. |
| 2026-11-07 | Every implementation step goes through `/spec-implement` with a per-step spec; progress in `docs/steps/TRACKER.md`. |
| 2026-11-07 | Refs: one shared `refsDir` (default `artifacts/refs/`, git-ignored, configurable), not per feature. |
| 2026-11-07 | License: MIT (same as spec-kit). `LICENSE` added in step 0; `extension.yml` uses `license: MIT`. |
| 2026-11-07 | Step 1 gate, risk 1 (option C): deploy patches `disable-model-invocation: true` into the `speckit-ac-*` skills **and** the guard blocks main-agent `Skill` calls for `speckit-ac-*` (§9). |
| 2026-11-07 | Step 1 gate, N1 (option A): deploy replaces the `--dev` skill symlinks with real, patched files (§9); verified in step 6. |
| 2026-11-07 | Step 1 gate, hand-back (option A): interactive Claude Code only, `claude -p` unsupported; guard allows `SubagentHandback` for AC roles with a content check (§9). |
| 2026-11-07 | v1.0 environment: Windows + uv + pwsh, spec-kit `--script ps` (§2). Resolves N2 for v1.0 (PowerShell scripts need no PATH Python); other environments deferred. |
| 2026-11-07 | Step 2 spec: active-run marker `.workflow/active-run.json` (§8); missing config → guard allows the main agent, denies AC roles (invalid config blocks all); v1.0 supports only `specs/NNN-name` features; per-role visibility (§8); main agent may not write lock files, `runs/`, `refsDir`, the marker; scripts share `aclib.py`, guard standalone; spec drift = `ac_lock.py verify` exit 3 + `confirm-spec`; CT's experiment log dropped. |
| 2026-11-08 | Step 3 spec: each agent file defines its task-message template; config key `testFramework` (`xunit2`/`xunit3`/`nunit`/`mstest`, no runner key); `ac_feature.py --all` for the judge; one `.feature` file per feature; translator stops on build errors outside its feature; writer scopes every `[Binding]`, no bindings in `Support/Shared/`, `API-CHANGED:` pending steps for unfaithful cross-feature fixes; `SUPERSEDED` only for regression scenarios; writer feedback only what the current feature's writer can fix. |
| 2026-11-08 | Step 4 spec: `task_message.py` builds each subagent's task message from its agent file and records it in the active-run marker; the guard lets the main agent start an AC role only with that exact prompt, in the foreground (also fixes the writer launch the step-definition text rule blocked); `changed_files.py check` deletes the marker; `acceptance.md` format (Coverage table, `### AC-NNN (refs) title` items) with `check_acceptance.py` before `sources` is locked (every FR covered, a scenario may be "not testable through the API"); translate picks its phase from the lock state; tests-analyze always runs all features' tests, `--current` narrows only the judge's input; tests-analyze verifies every feature's existing locks (drift elsewhere warns); critic on Fable/high, `ac` revises only before the lock, `features` is one report-only pass; manifest checked by the real `specify` (test skipped without it), `requires.speckit_version: ">=1.0.2"`. |
| 2026-11-08 | Step 6 spec: deploy manifest `.workflow/deploy.json` (committed; hashes the installed extension files too, so `doctor` needs no bundled payload); guard hook `timeout: 30`, Python = the v1.0 constant, checked against the config by `doctor`; `settings.json` re-serialised with `indent=2` (no content in the manifest); uninstall removes spec-kit's empty leftovers only when they did not exist before install; `doctor` runs no dotnet; uninstall needs the manifest; no `argument-hint` patch; payload `.extensionignore`. Implementation: hashes fold CRLF to LF (an `autocrlf=true` clone); the settings file's line ending is recorded before spec-kit rewrites it and restored on uninstall. |
| 2026-11-08 | Step 5 spec: `/speckit-ac-init` = command + deterministic scripts (`init_detect`, `init_config`, `init_scaffold`, `init_verify`, `smoke_test`), one summary confirmation before any write; init (not deploy) writes the `.gitignore` / `.gitattributes` managed blocks (§9); LF pinned for every locked text file, samples `binary`; ref mode references `<refsDir>/*.dll` by one glob; packages from a fixed framework × runner recipe plus the surface's public packages (central pins, then the surface's, then the unit tests' versions, then latest stable); verification never writes into product projects; re-running init with a config only verifies; the smoke test writes its own marker (`/speckit-ac-init smoke`); only verified pairs are supported (7 of 8: xUnit v2 has no Microsoft.Testing.Platform runner); `.workflow/active-run.json` is git-ignored. |
| 2026-11-09 | Step 8 (user, after the Habit Tracker PR review): `new_run.py` / `new_analyze.py` **refuse** while another run's active-run marker exists instead of overwriting it (option B). Subagents run in the background, so re-pinning a still-working subagent to another run would break it silently. The user ends an interrupted run with the new `changed_files.py clear` (`smoke_test.py end` for a smoke marker); `/speckit-ac-tests-analyze` runs `clear` itself at every stop before the judge. Config validation tightened on every load (guard and scripts): spec inputs, `refsDir` and the AC project may not overlap implementation or protected folders, every path is project-relative, `acRefBuildCommand` is exactly the generated command (WORKFLOW §3.9, CONFIG.md) |
