# Step 4 — Commands and extension manifest

**Status:** done (2026-11-08; decisions 1–9 approved as drafted; R08/R09 amended during plan review) · **Tracker row:** 4 · **Source of truth:** `docs/DESIGN.md`

## Goal

Make the payload a working spec-kit extension: `extension.yml` and four commands
(`/speckit-ac-translate`, `/speckit-ac-tests-write`, `/speckit-ac-tests-analyze`,
`/speckit-ac-critic`) that drive the scripts and start the three AC subagents with their exact task
messages. Add the `acceptance.md` template and the pieces the commands need to stay deterministic: a
script that builds the task message, a guard rule for subagent launches, the active-run marker's end,
and an `acceptance.md` check. No `/speckit-ac-init` (step 5), no deploy (step 6), no live runs (step 7).

## Context

- Sources (read only): CT's `skills/ac-translate`, `ac-tests-write`, `ac-tests-analyze`
  (`SKILL.md`, CT doc §5.6) and `~\.claude\skills\speckit-critic\SKILL.md`.
- CT skills work on one global AC set, fill the subagent prompt by hand from a template inside the
  skill, and log to `.workflow/experiment-log.md` (dropped in step 2).
- Steps 2–3 left these open items for step 4 (tracker notes): scripts are called by the cwd-relative
  path; the marker's lifecycle; spec drift (`ac_lock.py verify` exit 3 → ask → `confirm-spec`); the
  snapshot order; templates copied verbatim and tested; `<FEATURE_LIST>` / `<SPEC_INPUTS>` built
  deterministically; `ac_feature.py --all` fails on any non-feature folder; a stale marker lets the
  main agent start an AC agent with its own prompt.
- **Finding while drafting (verified by reading the code):** the guard's step-definition text rule
  (`guard.py:158–159`, applied to every string of a main-agent tool call, `:255–266`) matches
  `<AC folder name>/StepDefinitions` and `/Support`. The writer's task message names
  `StepDefinitions/<TAG>/`, `Support/<TAG>/` and `Support/Shared/`, so today the guard **denies the
  main agent's `Agent` call that starts the writer**. Step 3's tests checked the writer's own calls,
  not its launch.
- Spike logs (step 1, run A): a main-agent subagent launch reaches the guard as `tool_name: "Agent"`
  with `tool_input` keys `description`, `prompt`, `run_in_background`, `subagent_type`.
- spec-kit 1.0.2 facts (read in its installed source, `specify_cli/extensions/__init__.py:220–560`,
  `agents.py:195–530`):
  - manifest: `schema_version: "1.0"`; required `extension` (`id`, `name`, `version`,
    `description`, all strings), `requires.speckit_version` (non-empty string), `provides`;
    `hooks.<event>` is one mapping **or a list** of mappings, each with `command`, optional integer
    `priority ≥ 1`;
  - when rendering a command into a skill, spec-kit **rewrites paths in the body**: a bare
    `scripts/`, `templates/`, `agents/`, `hooks/` or `memory/` after whitespace, a backtick, a quote
    or `(` becomes `.specify/extensions/ac/<dir>/` or `.specify/memory/`; `{SCRIPT}`, `{ARGS}` and
    `__AGENT__` are replaced; `$ARGUMENTS` stays for Claude;
  - skill frontmatter is rebuilt (`name`, `description`, `compatibility`, `metadata`);
    `argument-hint` is copied only on some code paths (step 1: not seen for `--dev`).
- spec-kit's spec template: user stories `### User Story N - …` with numbered
  `**Acceptance Scenarios**` (`1. **Given** …`), requirements `- **FR-NNN**: …`. DESIGN §3 names
  scenario references `US<N>-AS<M>`.

## Requirements

### Extension manifest

- **S04-R01** `payload/extension.yml`: `schema_version: "1.0"`; `extension` with `id: ac`, `name`,
  `version` equal to the package version, `description`, `author`, `license: MIT` (no `repository`
  until step 9); `requires.speckit_version: ">=1.0.2"`; `provides.commands` for the four commands
  of this step (`speckit.ac.translate`, `speckit.ac.tests-write`, `speckit.ac.tests-analyze`,
  `speckit.ac.critic`), each with `file: commands/<name>.md` and a description. `speckit.ac.init` is
  added in step 5.
- **S04-R02** Optional hooks (DESIGN §6), all `optional: true`, never auto-run:
  `after_clarify` → `speckit.ac.critic` (prompt: type `/speckit-ac-critic spec`) and
  `speckit.ac.translate` (lower priority, i.e. offered after the critic); `after_plan` →
  `speckit.ac.critic` (`plan`); `after_tasks` → `speckit.ac.critic` (`tasks`); `after_implement` →
  `speckit.ac.tests-write`. Each prompt tells the user to type the command (step 1, check 2.4).

### Command files (shared rules)

- **S04-R03** `payload/commands/speckit.ac.<name>.md`, frontmatter `description` and
  `argument-hint`; the body is instructions for the main agent:
  - "Follow these steps exactly. Stop at the first failure and report it." Every step is numbered.
  - `<python>` is `python` from `.workflow/config.json`; scripts are called as
    `<python> .specify/extensions/ac/scripts/<name>.py …` from the session's working directory
    (CONFIG.md "Invoking the scripts"), never via `$CLAUDE_PROJECT_DIR`.
  - Missing `.workflow/config.json` → stop: run `/speckit-ac-init` first.
  - The feature is the argument if given (`--feature <arg>` for every script), otherwise spec-kit's
    current feature (`.specify/feature.json`, resolved by the scripts). The command shows the resolved
    feature and tag from `ac_feature.py` before doing anything else.
  - The body survives spec-kit's rendering unchanged: no bare `scripts/`, `templates/`, `agents/`,
    `hooks/` or `memory/` path that the rewrite would touch, no `{SCRIPT}`, `{ARGS}`, `__AGENT__`.
  - No CT specifics (S03-R02's strings, `experiment-log`), no implementation or step-definition
    content in what the command tells the main agent to read or report.
  - Ends with a stop and names the next step; never starts it.
- **S04-R04** Lock handling, the same in every command: `ac_lock.py verify <group>` exit 0 → go on;
  exit 1 → stop with the script's message and the fix (lock, or unlock / edit / re-lock only on the
  user's explicit request); exit 3 (spec drift, `sources` only) → show which file changed and ask the
  user whether the AC are still valid: yes → `ac_lock.py confirm-spec sources` and go on; no → stop
  (unlock, edit, re-lock, translate again).
- **S04-R05** Starting an AC subagent, the same in every command:
  1. `new_run.py <kind>` or `new_analyze.py` (writes the marker);
  2. `task_message.py` (R06) — prints the task message;
  3. `changed_files.py snapshot`;
  4. the `Agent` tool with `subagent_type` = the role, `run_in_background: false`, and `prompt` =
     the exact output of step 2, nothing added or changed;
  5. `changed_files.py check <role>` — any file outside the allowlist is an **isolation breach**:
     report the file names and stop.
  The main agent never reads step definitions or `Support/` and never shows their content.

### Task message, guard and marker

- **S04-R06** New script `task_message.py [--feature …]`: reads the active-run marker, the config,
  the feature's paths and the role's agent file (`.specify/extensions/ac/agents/<role>.md`, the
  installed payload copy); fills the `## Your task message` template exactly as S03-R03 defines
  (placeholders = UPPER_SNAKE of an `ac_feature.py` key, else a config key, lists joined with
  `", "`; `RUN_ID` / `ANALYZE_ID` from the marker; `FEATURE_LIST` = every feature as
  `specs/NNN-x (FNNN)`, joined with `", "`); drops the optional lines when their condition does not
  hold (*Other spec inputs*: `specInputs` empty; *Feedback to address*: no `input-feedback.md` in the
  run folder); stores the message in the marker (`taskMessage`) and prints only the message.
  It fails (exit 1) on an unknown placeholder, a marker for another feature, or a missing agent file.
  The test filler in `tests/test_agents.py` is replaced by this script.
- **S04-R07** Guard, new main-agent rule for `Agent` (and `Task`) calls whose `subagent_type` is an
  AC role (only when the config exists):
  - the marker must be valid for that role (the existing marker check) and hold `taskMessage`;
  - the `prompt`, normalised (CRLF → LF, trailing spaces per line and surrounding blank lines
    removed), must equal `taskMessage` normalised the same way;
  - `run_in_background` must not be `true`;
  - otherwise exit 2 with a reason naming the rule ("start AC subagents only from the AC commands,
    with the exact output of task_message.py, in the foreground").
  A call that passes is exempt from the step-definition text rule (its message names those folders by
  design). `Agent` calls for other subagent types are unchanged.
- **S04-R08** Marker lifecycle: `changed_files.py check <role>` deletes `.workflow/active-run.json`
  once the check has run (it found the snapshot and a marker for that role), whatever the result; a
  usage error before that (no snapshot, another role) keeps it (amended during plan review round 1). Until the next run script no AC subagent can start (R07) and
  no AC-role tool call is allowed (no marker → deny, S02). `changed_files.py snapshot` must run after
  `task_message.py` (the marker changes there).

### `acceptance.md`

- **S04-R09** `payload/templates/acceptance-template.md`, the format of `specs/NNN-x/acceptance.md`:
  - a title and a line naming the feature folder, tag and `spec.md`;
  - `## Coverage`: one row per `FR-NNN` and per spec scenario `US<N>-AS<M>` with the AC items that
    cover it; a **scenario** row may instead say `Not testable through the API: <reason>`, an FR row
    may not (DESIGN §3: every FR has at least one AC item; amended during plan review round 1);
  - `## Acceptance criteria`: one item per heading `### AC-NNN (<ref>; <ref>…) <title>`, refs being
    `FR-NNN` or `US<N>-AS<M>`, followed by `Given` / `When` / `Then` (and `And`) lines in plain
    language with concrete literal values; golden samples by file name relative to
    `Samples/<TAG>/`; an optional `Examples` table for outlines;
  - a short instructions block (how to write items) inside an HTML comment, to be deleted.
- **S04-R10** New script `check_acceptance.py [--feature …]` (exit 0 / 1, findings one per line,
  no file contents beyond ids):
  - item headings parse; ids are `AC-NNN`, unique; each item has at least one ref and at least one
    `When` and one `Then` line;
  - every ref exists in `spec.md` (`FR-NNN` from the requirements list; `US<N>-AS<M>` from the
    numbered acceptance scenarios of user story N);
  - every `FR-NNN` in `spec.md` is covered by at least one item; every spec scenario is covered or
    listed in Coverage as not testable with a reason;
  - every golden sample named in an item exists under `Samples/<TAG>/`.

### `/speckit-ac-translate`

- **S04-R11** Phase by state: no `sources.lock` → **phase 1**; `sources` verifies (R04) → **phase 2**.
  `features.lock` present → stop (features are locked; unlock only on explicit request).
- **S04-R12** Phase 1 (draft):
  - inputs: the feature's `spec.md`, the constitution, the configured `specInputs`, the template;
    **never** `plan.md`, `research.md`, `data-model.md`, `contracts/`, `tasks.md`, code, or
    `CLAUDE.md` as a source of AC content;
  - drafts or revises `acceptance.md` (asks before overwriting an existing one) and golden samples in
    `Samples/<TAG>/`;
  - lists to the user every rule the AC would depend on that exists only in `CLAUDE.md` (to move into
    the spec or constitution) — never copies it into `acceptance.md`;
  - runs `check_acceptance.py` until it passes;
  - suggests `/speckit-ac-critic ac`, asks the user to review; locks `sources`
    (`ac_lock.py lock sources`) only after an explicit approval and a passing check; stops.
- **S04-R13** Phase 2 (translate), CT's flow per feature: `export_refs.py` → `clear_generated.py
  features` → R05 with `new_run.py translate` and `ac-feature-translator` → `check_features.py` →
  report from `translation-report.md` (run id, build status, check result, items translated, the full
  Issues table). Build or check failed → stop (run the command again; no message to the translator).
  Issues → the user chooses **skip** (per item), **fix** or **full stop**: any fix or stop → stop, lock
  nothing; skip for all → `record_skips.py <run> <ids>`. Then: feature file names and scenario count,
  suggest `/speckit-ac-critic features`, lock `features` only after an explicit approval. Next step:
  `/speckit-plan`.

### `/speckit-ac-tests-write`

- **S04-R14** CT's flow per feature, argument `fresh` optional: verify `sources` and `features`
  (R04) → build `solution`, run `unitTestCommand` for each `unitTestProjects` entry (never the whole
  solution's tests; failure → stop) → `export_refs.py` → `fresh`: `clear_generated.py steps` (without
  reading the files) → R05 with `new_run.py write` and `ac-test-writer` → report from
  `writer-report.md`: run id, build status, changed file **names** (from the check), scenarios bound,
  unexpressible steps, interpretations, **cross-feature changes** and **missing packages** (S03-R14).
  It never runs the AC tests. Next step: `/speckit-ac-tests-analyze`.

### `/speckit-ac-tests-analyze`

- **S04-R15** Flow, argument `--current` optional:
  1. `ac_feature.py --all` (stops early on a non-feature folder under `specs/`);
  2. verify the current feature's `sources` and `features` (R04); for every other feature with lock
     files, verify both: mismatch → stop; spec drift → warn only;
  3. the current feature's latest `run-NNN` has `writer-report.md`, else stop
     (`/speckit-ac-tests-write` first);
  4. `new_analyze.py`; build `acProject` normally (`dotnet build <acProject> -nologo -v q`, no
     `AcRefMode`). Build fails → report only the number of errors and their codes; stop;
  5. run `acTestCommand` (`{acProject}`, `{analyzeDir}` filled); it must write
     `<analyzeDir>/ac-results.trx` (init, step 5, builds the command so). A non-zero exit only means
     failures;
  6. `summarize_trx.py … --current <TAG>`, with `--only-current` when the argument is `--current`;
  7. all passed → totals, AC ids skipped at translation (current feature's latest `skipped.json`),
     stop. Pending counts as failed;
  8. otherwise R05 with `ac-test-fail-judge` (marker from step 4), then `extract_feedback.py`;
  9. report: totals per scope (current / regression), the judge's Summary table, next actions per
     verdict (CT's six plus `SUPERSEDED`: revise or retire the old feature's AC; regression
     `TEST_FAULT`: `/speckit-ac-tests-write` for that feature). Stop.
- **S04-R16** Scope: the AC test run always covers all features (no runner-specific test filter).
  `--current` narrows what the judge sees and judges: `summarize_trx.py --only-current` writes only
  the current feature's section, plus a one-line count of regression results with their
  `F00N/AC-NNN` keys and no details.

### `/speckit-ac-critic`

- **S04-R17** Port of speckit-critic: arguments `[spec|plan|tasks|ac|features] [feature] [focus]`;
  feature resolved by `ac_feature.py`; critic = `general-purpose` subagent, `model: fable`,
  `effort: high`, foreground; the hard rules, report format, verdict rule, pass numbering
  (`specs/<feature>/critic-<stage>-pass-<n>.md`), verification of findings, and the 3-pass cap with
  the user's choice kept word for word where generic; legacy-report renaming dropped.
- **S04-R18** Stage `ac`: under review `acceptance.md` and `Samples/<TAG>/`; reference material
  `spec.md`, the constitution, `specInputs`; extra focus: coverage, concreteness, consistency with the
  spec, boundary and edge-case discrimination; the critic prompt forbids reading code, plans, tests
  or `CLAUDE.md` (prompt rule, WORKFLOW §6). Revise loop only while `sources` is not locked; locked →
  stop (unlock first).
- **S04-R19** Stage `features`: under review `Features/<TAG>/*.feature` against `acceptance.md`
  (item by `@AC-` id); **report-only**: one pass per invocation, no revise loop, nobody edits a
  `.feature`; findings go to the user with the options approve / re-translate / fix `acceptance.md`.
  `features` locked or not doesn't matter.

### Tests and docs

- **S04-R20** Tests (pytest, no new dependency):
  - `task_message.py`: output equals the template filled for each role; optional lines dropped and
    kept; unknown placeholder, wrong marker, missing agent file fail; `taskMessage` stored;
  - guard: AC `Agent` launch allowed with the exact (normalised) message; denied with a changed or
    extended prompt, `run_in_background: true`, another role's marker, no marker, no `taskMessage`;
    the writer launch is **allowed** although its message names `StepDefinitions/` (regression for
    the finding); other subagent types still hit the step-definition text rule;
  - marker: `changed_files.py check` deletes it on success and on breach; afterwards the guard denies
    the launch and the role's tool calls;
  - command walk: for translate phase 2, tests-write and tests-analyze, the command's script steps run
    in a temp project in the documented order, the launch passes the guard, a stub subagent writes
    its allowed files, the check passes, the marker is gone;
  - command texts: every script named exists and every subcommand / flag used is one the script
    accepts; R05's order appears in each subagent command; R03's no-rewrite rule; no CT strings;
    every `/speckit-ac-*` named is a command in `extension.yml` or `init`;
  - `extension.yml`: version equals the package version, every command file exists, every hook
    command is a provided command (checked on the text; no YAML library);
  - real spec-kit (skipped when `specify` is not on PATH): `specify init --script ps` in a temp
    folder, `specify extension add --dev <payload>`: install succeeds, four `speckit-ac-*` skills
    exist, each skill body equals its command body, the hooks are registered;
  - `check_acceptance.py` and `summarize_trx.py --only-current` cases; the template passes
    `check_acceptance.py` against a matching sample spec.
- **S04-R21** Docs: `docs/WORKFLOW.md` (§3.2 principle 3 now guard-enforced; principle 9 marker end;
  §5 drift flow; §6 the `Agent` call's `description` field is not checked), `docs/CONFIG.md`
  (`taskMessage` in the marker, its deletion, `acTestCommand` must write `ac-results.trx`,
  `task_message.py` / `check_acceptance.py`), payload README (commands, `extension.yml`, templates
  rows), DESIGN decision-log row.
- **S04-R22** `uv run pytest -q --tb=short` passes; tracker row 4 updated. No commit unless the user
  asks.

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S04-A01 | `extension.yml` and four command files exist; text checks pass; real `specify extension add --dev` renders four skills with unchanged bodies and the hooks | R01–R03 |
| S04-A02 | `task_message.py` tests pass for all three roles | R06 |
| S04-A03 | Guard launch tests pass, including the writer-launch regression | R07 |
| S04-A04 | Marker deletion tests pass | R08 |
| S04-A05 | Command walks pass for translate phase 2, tests-write, tests-analyze | R04, R05, R13–R16 |
| S04-A06 | `check_acceptance.py` tests pass; the template passes against its sample spec | R09, R10, R12 |
| S04-A07 | Critic command text has the five stages, the hard rules, `ac` prompt rule, `features` report-only | R17–R19 |
| S04-A08 | `uv run pytest -q --tb=short` passes (count reported) | R22 |

## Out of scope

- `/speckit-ac-init`, `speckit.ac.init` in the manifest, AC project scaffolding, how `acTestCommand`
  is built (step 5).
- Deploy: copying agents, patching `disable-model-invocation`, settings merge (step 6).
- Running the commands with a live model; whether the `Agent` call's `description` reaches the
  subagent; whether a model passes a multi-line message unchanged (step 7).
- A per-feature test filter for the AC run (needs a runner key; not in v1.0).

## Decisions taken in this spec (confirm on approval)

1. **`task_message.py` builds the task message** (R06) and the command passes its output verbatim,
   instead of each command holding a copy of the template that the model fills in. Deterministic,
   one source (the agent file), no hand-made joins. Replaces the tracker item "copy the templates into
   the commands".
2. **The guard checks AC subagent launches** (R07): exact message from the marker, foreground only.
   This makes principle 3 ("add nothing") technical, closes the stale-marker hole, and fixes the
   writer launch that the step-definition text rule blocks today.
3. **The marker ends at `changed_files.py check`** (R08): deleted, so nothing can start or act as an
   AC role between commands.
4. **`acceptance.md` format** (R09) with a Coverage table and `### AC-NNN (refs) title` items, and a
   **deterministic coverage check** `check_acceptance.py` (R10) that must pass before `sources` is
   locked.
5. **Translate picks its phase from the lock state** (R11); no phase argument.
6. **tests-analyze always runs every feature's tests**; `--current` only narrows what the judge sees
   (R16). A real test filter would need a runner key and per-framework filter syntax.
7. **tests-analyze verifies every locked feature**: a changed lock anywhere stops; spec drift in
   another feature only warns (R15).
8. **Critic stays on Fable, high effort** (R17), as in the source skill; `ac` revises only before the
   lock, `features` is one report-only pass (R18–R19).
9. **The manifest is checked by the real `specify`** in a test that is skipped when `specify` is not
   installed; no PyYAML dev dependency (R20). `requires.speckit_version: ">=1.0.2"`, the only version
   verified.
