# Step 3 — The three AC subagents

**Status:** done (2026-11-08; decisions 1–8 approved as drafted; R04/R08 amended during plan review) · **Tracker row:** 3 · **Source of truth:** `docs/DESIGN.md`

## Goal

Port CT's three subagent definitions into the extension payload and adapt them to the per-feature
model (DESIGN §8): the translator works on one feature and tags it, the writer scopes its bindings to
its feature, keeps shared helpers in `Support/Shared/`, makes only listed compile fixes in other
features and uses the configured test framework, and the judge gains `SUPERSEDED`. Each agent file
also states the exact task message it expects, so step 4's commands can fill it in and nothing else.
A test suite checks the agent files against the guard. No commands, `extension.yml`, deploy or live
runs (steps 4–7).

## Context

- Sources (read only): `<original project>\.claude\agents\ac-feature-translator.md`, `ac-test-writer.md`,
  `ac-test-fail-judge.md` (CT doc §5.5), and the prompt templates in CT's skills (CT doc §5.6).
- CT agents work on one global AC set: `.md` files in `acSources`, `Features/`, `.workflow/runs/`,
  one `SPEC.md`. They describe their inputs as "listed in your task message" without fixing its
  format; the format lives only in the skills.
- Step 2 fixed what the guard lets each role do (S02-R10–R12, WORKFLOW §3.1). In particular:
  - the translator reads only its own feature (`spec.md`, `acceptance.md`, `Samples/FN`,
    `Features/FN`, its active report), constitution and `specInputs`; it writes only `.feature` files
    in `Features/FN/` and its report;
  - the writer reads all AC project folders and `refsDir`, but only its own feature's `spec.md` and
    `acceptance.md`; it writes `StepDefinitions/**`, `Support/**` (never `.feature`) and its report;
  - the judge reads every feature's `spec.md` and `acceptance.md` by exact path, but `specs/` is not a
    search root for it (Grep/Glob there would show `plan.md`), so it cannot find another feature's
    folder by searching;
  - every report path is pinned to the active run in `.workflow/active-run.json`.
- The DESIGN §2 values "test framework (xUnit v2/v3, NUnit, MSTest) and runner" are to be stored in
  `.workflow/config.json`, but the step 2 schema has no key for them yet. The guard and `aclib`
  ignore unknown keys.
- Step 1: `omitClaudeMd` works for custom agents; `SubagentHandback` is the hand-back tool in
  interactive Claude Code, and the guard denies a hand-back containing a code fence or a Reqnroll
  binding attribute.
- Deploy (step 6) copies the agent files to the target's `.claude/agents/`; spec-kit also copies
  them with the rest of the payload to `.specify/extensions/ac/agents/`, where nothing reads them.

## Requirements

### Files and frontmatter

- **S03-R01** New payload files `src/speckit_ac/payload/agents/ac-feature-translator.md`,
  `ac-test-writer.md`, `ac-test-fail-judge.md`. Frontmatter as in CT:
  - `name` equals the file name and the guard's role name;
  - `tools`: translator and writer `Read, Write, Edit, Grep, Glob, Bash`; judge
    `Read, Write, Grep, Glob`;
  - `disallowedTools`: `Skill, Agent, mcp__*`, plus `Bash` for the judge;
  - `omitClaudeMd: true`; no `hooks` (frontmatter hooks fail open in an untrusted folder, CT §5.4);
  - `description` says which `/speckit-ac-*` command invokes the agent and that it must never be
    invoked any other way.
- **S03-R02** No CT specifics in the agent files: no `SPEC.md`, `acSources`, `.workflow/runs`,
  `/ac-translate`, `/ac-tests-write`, `/ac-tests-analyze`, `experiment`, `knowledge-base`, `CT.`.
  Paths are the per-feature ones (CONFIG.md "Per-feature paths").

### Task message contract (new)

- **S03-R03** Each agent file has a section `## Your task message` with a fenced template: one
  `Label: <PLACEHOLDER>` line per input or output, the exact lines step 4's command sends.
  - Placeholders are `<UPPER_SNAKE>` names, each defined in a table below the template, each filled
    from `ac_feature.py` output, a config key, or the run/analyze id the run scripts print.
  - The agent text refers to inputs only by these labels ("the file named in *Spec*"), never by a
    hard-coded path.
  - Optional lines are marked optional, with the condition (feedback file exists; spec inputs not
    empty).
- **S03-R04** Templates (labels; placeholders in brackets):
  - **Translator:** Feature `<FEATURE_DIR>` (tag `<TAG>`), Run `<RUN_ID>`, Spec, Constitution,
    Other spec inputs (optional), Acceptance criteria, Golden samples `<AC_DIR>/Samples/<TAG>/`,
    Write feature files to `<AC_DIR>/Features/<TAG>/`, Allowed build command, Write your report to
    `…/ac/runs/<RUN_ID>/translation-report.md`.
  - Placeholder names are the UPPER_SNAKE form of the key they are filled from (`<AC_PROJECT_DIR>`
    from `acProjectDir`, `<FEATURES_DIR>` from `featuresDir`, …); the `<AC_DIR>` spellings below are
    illustrative (amended during plan review round 1).
  - **Writer:** Feature + tag, Run, Spec, Constitution, Other spec inputs (optional), Acceptance
    criteria (context only), AC test project `<AC_DIR>`, Project file `<AC_PROJECT>` (added during plan
    review round 1: the writer cannot list the project folder), Test framework `<TEST_FRAMEWORK>`, Feature
    files `<AC_DIR>/Features/<TAG>/`, Golden samples, Write step definitions to
    `<AC_DIR>/StepDefinitions/<TAG>/`, Feature support `<AC_DIR>/Support/<TAG>/`, Shared support
    `<AC_DIR>/Support/Shared/`, Public API listings `<REFS_DIR>/api/`, Allowed build command,
    Feedback to address (optional), Write your report to `…/run-NNN/writer-report.md`.
  - **Judge:** Current feature + tag, Run, Analyze, Feature folders `<FEATURE_LIST>` (every feature
    folder with its tag), Constitution, Other spec inputs (optional), AC test project, Public API
    listings, Writer report, Test results `…/<ANALYZE_ID>/ac-results.md`, Write your report to
    `…/<ANALYZE_ID>/judge-report.md`.
- **S03-R05** `ac_feature.py --all` (new flag, mutually exclusive with `--feature`) prints a JSON list
  of every feature folder with its tag (`[{"featureDir": "specs/001-a", "tag": "F001"}, …]`, sorted by
  number), with the same S02-R05 validation. It fills `<FEATURE_LIST>`.
- **S03-R06** Config key `testFramework` (schema stays 1; nothing is released yet): one of `xunit2`,
  `xunit3`, `nunit`, `mstest`. Required and validated by the guard and `aclib` alike (same rule set,
  S02-R04); documented in `docs/CONFIG.md`; filled into the writer's `<TEST_FRAMEWORK>`.
  `/speckit-ac-init` (step 5) detects it. No runner key: no agent needs the runner.

### Translator

- **S03-R07** CT rules kept (form not meaning, one scenario or outline per item, `When` + `Then`, no
  free text, verbatim values, domain language only, golden samples by name, interpretations vs issues,
  issue kinds and scopes, 5 build attempts, 3–5-line final message without Gherkin).
- **S03-R08** Per feature:
  - It translates only the AC items of the feature named in its task message. An AC item is an entry
    in the AC list of `acceptance.md`, normally with an id `AC-NNN` and traceability, e.g.
    `AC-001 (FR-003; US1-AS2)`; an entry without them is an issue (id `—`), as in CT. Coverage tables
    and "not testable through the API" lists are context, not items (amended during plan review
    round 1).
  - Output: **one** `.feature` file per feature, `<AC_DIR>/Features/<TAG>/<name>.feature`, `<name>` =
    the feature folder name without its number (`specs/001-login` → `login.feature`); one `Feature:`;
    English Gherkin keywords.
  - Tags: `@<TAG>` on the `Feature:` line; each scenario carries `@AC-NNN` plus one tag per
    traceability reference (`@FR-003 @US1-AS2`) and no `@F<digits>` tag (enforced by
    `check_features.py`, S02-R17).
  - Build: errors in its own `.feature` files are its to fix. If the build fails only on files
    outside `Features/<TAG>/` (other features' step definitions after an API change), it does not
    try to fix or read them: it records "build blocked outside this feature" and stops.
- **S03-R09** Report sections as CT (Build, Items, Issues, Interpretations), with the AC id column
  holding `AC-NNN` and a title line `# Translation report — <TAG> / <RUN_ID>`.

### Writer

- **S03-R10** CT rules kept (spec-only expected values as literals, public API only, fakes in
  `Support/`, `FakeTimeProvider`, real assertions, the "not allowed" list, `UNEXPRESSIBLE` pending
  steps, literal interpretation, bind the `.feature` as written, 8 build attempts, never run tests,
  3–5-line final message without code).
- **S03-R11** Per feature:
  - It binds every scenario in `Features/<TAG>/`, and only those.
  - Every class it writes with `[Binding]` (step definitions and hooks) carries
    `[Scope(Tag = "<TAG>")]`, so equal step texts in different features never collide.
  - Feature-specific code goes to `StepDefinitions/<TAG>/` and `Support/<TAG>/`.
  - `Support/Shared/` holds only plain helpers used by more than one feature (context classes, fakes,
    builders), never a `[Binding]` class. A change there must keep every feature compiling and is
    listed in the report.
- **S03-R12** Other features:
  - After an API change it may make **minimal compile fixes** in other features' step definitions
    and support code: renames and type or signature adjustments that do not change what a step does,
    its setup, its expected values or its assertion.
  - When a fix would need a new value or a different assertion, it replaces only that step's body
    with `throw new PendingStepException("API-CHANGED: <short reason>");`.
  - Both are listed per file in a report section "Cross-feature changes" (file, change, reason). It
    never binds or rewrites another feature's scenarios otherwise.
- **S03-R13** Test framework: it uses the assertion API of the framework named in *Test framework*
  (`xunit2`/`xunit3` → xUnit `Assert`, `nunit` → `Assert.That`, `mstest` → `Assert`), and only
  packages the AC project already references (it may read the project files; it never edits them).
  It never writes runner or framework configuration. A missing package it needs is reported, not
  worked around.
- **S03-R14** Report: CT's sections (Build, Coverage, Unexpressible steps, Interpretations and
  assumptions, Feedback addressed) plus "Cross-feature changes"; title
  `# Writer report — <TAG> / <RUN_ID>`; the Coverage table keys scenarios by `@AC-NNN`.

### Judge

- **S03-R15** CT method kept (failing step, `.feature` vs `acceptance.md` item, step code vs Gherkin
  and spec, literal expected values) and the verdicts `TRANSLATION_FAULT`, `TEST_FAULT`,
  `IMPLEMENTATION_FAULT`, `SPEC_AMBIGUITY`, `UNEXPRESSIBLE`, `INCONCLUSIVE` with confidence.
- **S03-R16** Multi-feature:
  - Each non-passed scenario is keyed `F00N/AC-NNN` and marked **current** (its tag is the current
    feature's) or **regression**.
  - For a regression scenario it reads that feature's `acceptance.md` and `spec.md` (folder from
    *Feature folders*) plus the current feature's `spec.md`.
  - New verdict **`SUPERSEDED`**, for regression scenarios only: the scenario faithfully expresses
    its own feature's AC, but that AC conflicts with the current feature's `spec.md`. The reasoning
    names both sides. Suggested action: revise or retire the old feature's AC (unlock its `sources`,
    edit, re-lock, translate and write its tests again).
  - A step pending with `API-CHANGED:` (S03-R12): `SUPERSEDED` if the current spec changed that
    behaviour; `UNEXPRESSIBLE` if the behaviour still applies but the API no longer offers it;
    `TEST_FAULT` if a faithful compile fix was possible.
- **S03-R17** Report: CT's layout with the Summary columns
  `| Feature/AC | Scope (current / regression) | Verdict | Confidence | One-line reason |`, title
  `# Judge report — <TAG> / <RUN_ID> / <ANALYZE_ID>`, and the writer-feedback markers exactly as
  `extract_feedback.py` reads them.
- **S03-R18** Writer feedback: CT's rule (no observed values, no exception messages, no
  `TRANSLATION_FAULT` items), and only `TEST_FAULT`s the next writer of **this** feature can fix:
  current-feature scenarios, and regression scenarios whose faulty code is listed under this run's
  "Cross-feature changes". Other regression `TEST_FAULT`s go only to Details, with the action
  "run `/speckit-ac-tests-write` for that feature".

### Tests and docs

- **S03-R19** `tests/test_agents.py`:
  - frontmatter (parsed with the standard library) matches R01; R02's strings are absent;
  - each template's placeholders are all defined and come from the allowed sources (R03);
  - **guard consistency:** in a temp project (as in `test_guard.py`), each template is filled with a
    sample feature and run; with the matching active-run marker, the guard allows the role to read
    every input and to write every output the template names, and allows the build command;
  - the judge's verdict list holds all seven; the feedback markers equal `extract_feedback.py`'s;
  - the pending prefixes `UNEXPRESSIBLE:` and `API-CHANGED:` use `PendingStepException`, which
    `summarize_trx.py` counts as pending.
- **S03-R20** Script and config tests: `ac_feature.py --all` (sorted list, `--all` with `--feature`
  is an error, a bad folder fails as in S02-R05); `testFramework` missing / invalid → guard exit 2 and
  script exit 1; the shared test config gets the key.
- **S03-R21** Docs: payload README (agents row done), `docs/CONFIG.md` (`testFramework`,
  `ac_feature.py --all`), `docs/WORKFLOW.md` (§3.2 principle 3 points to the agents' task-message
  sections; §4 `SUPERSEDED` and `API-CHANGED`), DESIGN decision-log row for this spec.
- **S03-R22** `uv run pytest -q --tb=short` passes; tracker row 3 updated. No commit unless the user
  asks.

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S03-A01 | The three agent files exist with R01's frontmatter; a grep for R02's strings finds nothing in the payload | R01, R02 |
| S03-A02 | Every template placeholder is defined and sourced; agent texts contain no hard-coded `specs/`, `Features/`, `.workflow/` paths outside the template | R03, R04 |
| S03-A03 | Guard-consistency tests pass for all three roles (reads, writes, build command) | R03, R04, R08, R11, R16 |
| S03-A04 | `ac_feature.py --all` and `testFramework` tests pass | R05, R06, R20 |
| S03-A05 | Agent text checks pass: `@<TAG>` and one-file rule (translator), `[Scope(Tag = …)]`, `Support/Shared` and "Cross-feature changes" (writer), seven verdicts, Scope column, feedback rule and markers (judge) | R08–R18 |
| S03-A06 | `uv run pytest -q --tb=short` passes (count reported) | R22 |

## Out of scope

- The commands that send the task messages, run the scripts and handle the marker's lifecycle; the
  `acceptance.md` format and template; `extension.yml` (step 4).
- Init detecting `testFramework`, scaffolding (`reqnroll.json`, global usings) (step 5).
- Copying the agents to `.claude/agents/` (step 6).
- Running the agents against a real project; checking the `[Scope]` behaviour and TRX output on a
  real Reqnroll build (step 7).

## Decisions taken in this spec (confirm on approval)

1. **The task message is defined in each agent file** (R03–R04), not only in the commands. One source
   per role; step 4 copies the template, and a test checks it against the guard. CT kept it only in
  the skills, so an agent and its skill could drift apart.
2. **`testFramework` becomes a config key now** (R06). The writer needs the assertion API; DESIGN §2
   already says the framework is stored in config. Alternative: the writer reads it from the csproj.
   Rejected: package references may live in props files it cannot read, and a deterministic value
   beats an inferred one. No runner key until a consumer needs it (step 5 may add one).
3. **`ac_feature.py --all`** (R05) gives the judge every feature folder, so `specs/` stays closed to
   searching.
4. **One `.feature` file per feature**, named after the feature folder (R08). The `acceptance.md`
   format is decided in step 4; a fixed file name keeps locks, checks and re-translations simple.
5. **Translator stops on build errors outside its feature** (R08) instead of fixing or reading them;
   it can't see step definitions anyway.
6. **Writer: `[Binding]` only under `StepDefinitions/<TAG>/` and `Support/<TAG>/`, always scoped**;
   `Support/Shared/` has plain helpers only (R11).
7. **`API-CHANGED:` pending steps** for cross-feature changes that a compile fix can't make faithfully
   (R12), and the judge's rule for them (R16).
8. **`SUPERSEDED` only for regression scenarios**, judged against the current feature's spec (R16);
   writer feedback carries only what the current feature's writer can fix (R18).
