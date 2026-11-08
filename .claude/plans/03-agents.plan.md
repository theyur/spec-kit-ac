# Plan — Step 3: the three AC subagents

Spec: `docs/steps/03-agents.spec.md` (approved 2026-11-08, decisions 1–8 as drafted).

## Facts (observed)

- F1. CT agents (`<original project>\.claude\agents\ac-*.md`): frontmatter `name`, `description`, `tools`,
  `disallowedTools`, `omitClaudeMd: true`; bodies "What you can see / Your task / rules / Report /
  final message". CT prompt templates live only in the skills (CT doc §5.6).
- F2. Step 1 results 4.1/4.5: `agent_type` = the custom agent's `name`; `omitClaudeMd: true` works;
  the spike agents used `tools`, `disallowedTools: Skill, Agent, mcp__*`.
- F3. Guard (`payload/hooks/guard.py`):
  - `STRING_KEYS`/`LIST_KEYS` validation, unknown keys ignored (lines 30–32, 102–120);
    `aclib.load_config` mirrors it (aclib 20–22, 72–90).
  - `folders(role)`: translator = specInputs + `Samples/T` + `Features/T`; writer/judge = specInputs +
    `Features`, `Samples`, `StepDefinitions`, `Support`, `refsDir`. `specs/` is no search root.
  - `readable_file`: judge reads `specs/*/spec.md`, `specs/*/acceptance.md`, constitution, active
    `writer-report.md` and `ac-results.md`; writer/translator their own feature's spec/AC plus the
    active run's files; writer/judge read files directly in `<ac>/` that exist. Grep/Glob on `<ac>`
    itself is denied.
  - `CODE = ```|\[(Binding|Given|When|Then|StepArgumentTransformation)\b` screens hand-backs.
- F4. `aclib.Feature.paths()` keys: featureDir, tag, number, spec, acceptance, acDir, runsDir,
  sourcesLock, featuresLock, featuresDir, samplesDir, stepDefinitionsDir, supportDir,
  sharedSupportDir. `resolve_feature()` implements S02-R05.
- F5. `extract_feedback.py` markers `<!-- WRITER-FEEDBACK:BEGIN -->` / `<!-- WRITER-FEEDBACK:END -->`;
  `summarize_trx.py` `PENDING = ("PendingStepException", "MissingStepDefinitionException")`.
- F6. Reqnroll 3.3.4 (`<nuget-packages>/reqnroll/3.3.4/lib/netstandard2.0/Reqnroll.dll`) contains
  `RemoveLeadingAt`: a `[Scope(Tag = …)]` value matches with or without `@`. `ScopeAttribute` doc:
  "Restricts the binding attributes (step definition, hook, etc.)". Cached adapters:
  `reqnroll.xunit` (2.4.1, 3.1.2), `reqnroll.xunit.v3` (3.3.4).
- F7. Tests: `tests/acproject.py` (`make_project`, `run_script`, `run_guard`, `CONFIG`, `AC`, `BUILD`;
  features `001-alpha`, `002-beta`, AC folders for F001/F002 + `Support/Shared`);
  `tests/test_guard.py::test_invalid_config_blocks_everything` (parametrised configs);
  `tests/test_scripts.py` (`ok`, `failed`, feature tests).

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| A1 | A class-level `[Scope(Tag)]` scopes every step definition and scenario/feature hook in the class; `[BeforeTestRun]`/`[AfterTestRun]` cannot be scoped | 0.8 | Writer rule R11 would leave a cross-feature leak or forbid too much | F6 doc text; live check in step 7 |
| A2 | Step 4 commands will send the template lines verbatim, filled from `ac_feature.py`, config and the run scripts' output | 0.9 | Contract drifts | Step 4 test compares command templates with agent templates (noted for step 4) |
| A3 | A multi-line prompt of `Label: value` lines reaches the subagent unchanged (as in CT) | 0.9 | Agents misread inputs | Step 7 smoke test |
| A4 | Adding a required key to schema 1 breaks nobody (nothing released, no installs) | 0.95 | Old configs fail | Repo has no release; step 5 writes the key |
| A5 | spec-kit ignores `.specify/extensions/ac/agents/` | 0.7 | Low: duplicate agent definitions only if spec-kit registered them | Step 6 deploy check |
| A6 | The `tools:` whitelist does not remove the `SubagentHandback` tool, so the guard's hand-back screen runs | 0.75 | Agents end with plain text; the code screen never runs (prompt rule only) | Interactive smoke test, step 7 (tracker note) |

No assumption is blocking (none < 0.7 with high consequence).

## Design

### Placeholders (S03-R03)

Names are the UPPER_SNAKE form of the key they come from, so the step 4 command needs no mapping
table. (The spec's `<AC_DIR>` example is spelled `<AC_PROJECT_DIR>` for that reason.)

| Placeholder | Filled from |
|---|---|
| `<FEATURE_DIR>`, `<TAG>`, `<SPEC>`, `<ACCEPTANCE>`, `<RUNS_DIR>`, `<FEATURES_DIR>`, `<SAMPLES_DIR>`, `<STEP_DEFINITIONS_DIR>`, `<SUPPORT_DIR>`, `<SHARED_SUPPORT_DIR>` | `ac_feature.py [--feature …]` keys `featureDir`, `tag`, `spec`, … |
| `<AC_PROJECT_DIR>`, `<AC_PROJECT>`, `<REFS_DIR>`, `<AC_REF_BUILD_COMMAND>`, `<TEST_FRAMEWORK>`, `<SPEC_INPUTS>` | config keys (`specInputs` joined with `, `) |
| `<RUN_ID>`, `<ANALYZE_ID>` | `new_run.py` / `new_analyze.py` output |
| `<FEATURE_LIST>` | `ac_feature.py --all`, formatted `specs/001-a (F001), specs/002-b (F002)` |

The constitution line is the literal `.specify/memory/constitution.md` (fixed by spec-kit).

### Templates (S03-R04), verbatim

Translator:

```text
Feature: <FEATURE_DIR> (tag <TAG>)
Run: <RUN_ID>
Spec: <SPEC>
Constitution: .specify/memory/constitution.md
Other spec inputs: <SPEC_INPUTS>
Acceptance criteria: <ACCEPTANCE>
Golden samples: <SAMPLES_DIR>/
Write feature files to: <FEATURES_DIR>/
Allowed build command: <AC_REF_BUILD_COMMAND>
Write your report to: <RUNS_DIR>/<RUN_ID>/translation-report.md
```

Writer:

```text
Feature: <FEATURE_DIR> (tag <TAG>)
Run: <RUN_ID>
Spec: <SPEC>
Constitution: .specify/memory/constitution.md
Other spec inputs: <SPEC_INPUTS>
Acceptance criteria (context only): <ACCEPTANCE>
AC test project: <AC_PROJECT_DIR>/
Project file: <AC_PROJECT>
Test framework: <TEST_FRAMEWORK>
Feature files: <FEATURES_DIR>/
Golden samples: <SAMPLES_DIR>/
Write step definitions to: <STEP_DEFINITIONS_DIR>/
Feature support: <SUPPORT_DIR>/
Shared support: <SHARED_SUPPORT_DIR>/
Public API listings: <REFS_DIR>/api/
Allowed build command: <AC_REF_BUILD_COMMAND>
Feedback to address: <RUNS_DIR>/<RUN_ID>/input-feedback.md
Write your report to: <RUNS_DIR>/<RUN_ID>/writer-report.md
```

Judge:

```text
Current feature: <FEATURE_DIR> (tag <TAG>)
Run: <RUN_ID>
Analyze: <ANALYZE_ID>
Feature folders: <FEATURE_LIST>
Constitution: .specify/memory/constitution.md
Other spec inputs: <SPEC_INPUTS>
AC test project: <AC_PROJECT_DIR>/
Public API listings: <REFS_DIR>/api/
Writer report: <RUNS_DIR>/<RUN_ID>/writer-report.md
Test results: <RUNS_DIR>/<RUN_ID>/<ANALYZE_ID>/ac-results.md
Write your report to: <RUNS_DIR>/<RUN_ID>/<ANALYZE_ID>/judge-report.md
```

Optional lines (stated under each template): *Other spec inputs* only when `specInputs` is not
empty; *Feedback to address* only when that file exists. Each agent file also has the placeholder
table (its own subset).

Agent text refers to inputs by label ("the file in *Spec*"). Derived paths are described in words:
the writer's other-feature folders are "the siblings of *Feature files*, *Write step definitions
to* and *Feature support* (same parent, other tags)"; the judge's per-feature files are "`spec.md` and
`acceptance.md` inside each folder of *Feature folders*" and the AC subfolders "`Features`, `Samples`,
`StepDefinitions`, `Support` inside *AC test project*, one folder per tag". Writer and judge are told:
read the project files directly in *AC test project* with Read, and search only its subfolders (the
guard denies a search rooted at the project folder itself).

### Agent content beyond CT

- Translator (R07–R09): AC item = any entry in the AC list of `acceptance.md`; an entry without an
  `AC-NNN` id or traceability is an issue (id `—`); coverage tables and "not testable through the API"
  lists are context (review 1 F4). "What you can see" names only the active run's report (CT's
  "earlier translation reports" dropped, F3). One file `<FEATURES_DIR>/<name>.feature`, `<name>` = folder
  name without its number; one `Feature:`; English keywords; `@<TAG>` on the `Feature:` line; scenario
  tags `@AC-NNN` + one per traceability reference, never an `@F<digits>` tag; build errors outside the
  feature → report "build blocked outside this feature", stop; report title
  `# Translation report — <TAG> / <RUN_ID>`; CT's report sections; "Source .md" column dropped (one
  source). It never sees other features (one sentence, no path).
- Writer (R10–R14): binds only scenarios in *Feature files*; every `[Binding]` class it writes carries
  `[Scope(Tag = "<TAG>")]`; no `[BeforeTestRun]`/`[AfterTestRun]` hooks (they run for every feature and
  cannot be scoped, A1); `[Binding]` classes only in *Write step definitions to* and *Feature support*;
  *Shared support* = plain helpers used by more than one feature, no `[Binding]`, changes keep every
  feature compiling and are listed; cross-feature compile fixes and `API-CHANGED:` pending steps with
  the report section "Cross-feature changes" (`| File | Change | Reason |`); framework mapping for
  assertions; never edits project files, runner or framework configuration; missing package →
  report; report title `# Writer report — <TAG> / <RUN_ID>`; Coverage keyed by `@AC-NNN`.
- Judge (R15–R18): current vs regression by tag; regression reads that feature's `acceptance.md`,
  `spec.md` and the current `spec.md`; `SUPERSEDED` definition (regression only, names both sides,
  action); `API-CHANGED:` rule; Summary columns
  `| Feature/AC | Scope (current / regression) | Verdict | Confidence | One-line reason |`; Details
  headings `### F00N/AC-NNN <scenario name>`; feedback rule (current-feature `TEST_FAULT`s and
  regression ones in this run's "Cross-feature changes"; others → Details with "run
  `/speckit-ac-tests-write` for that feature"); final message = Summary table only.

## Steps

0. **Facts** above (done while planning). — R01, R11
1. **`testFramework` config key.** `guard.py` and `aclib.py`: `ENUM_KEYS = {"testFramework": ("xunit2",
   "xunit3", "nunit", "mstest")}`, checked after the string keys with the same message style
   (`missing or invalid key testFramework (one of …)`). `tests/acproject.py` `CONFIG` gets
   `"testFramework": "xunit3"`. Tests: `test_invalid_config_blocks_everything` gains "testFramework
   missing" and "testFramework unknown" (`"xunit"`); `test_scripts.py` gains a parametrised test that
   `ac_feature.py` exits 1 for both. — R06, R20
2. **`ac_feature.py --all`.** `aclib.all_features(root, cfg) -> list[Feature]`: timestamp numbering →
   error; every directory directly under `specs/` goes through `resolve_feature`, so a bad folder or a
   duplicate number fails the listing naming it; files under `specs/` are ignored; no `specs/` →
   `[]`; sorted by `int(number)`. `ac_feature.py`: argparse mutually exclusive group `--feature` /
   `--all`; `--all` prints `[{"featureDir", "tag"}]`. Tests: list for the two-feature project, empty
   `specs/`, `--all --feature` → exit 2 (argparse), a timestamp folder → exit 1. — R05, R20
3. **`agents/ac-feature-translator.md`** per Design. — R01–R04, R07–R09
4. **`agents/ac-test-writer.md`** per Design. — R01–R04, R10–R14
5. **`agents/ac-test-fail-judge.md`** per Design. — R01–R04, R15–R18
6. **`tests/test_agents.py`:**
   - `frontmatter(path)`: lines between the first two `---`, `key: value`; tools split on `,`.
     Assert R01 per role (exact `tools`, `disallowedTools`, `omitClaudeMd == "true"`, `name` = file
     stem, no `hooks`, description names the `/speckit-ac-*` command and "never").
   - R02 strings absent in every payload file (`agents/`, `hooks/`, `scripts/`, README); hard-coded
     path fragments (`specs/`, `.workflow/`, `Features/`, `StepDefinitions/`, `Support/`, `Samples/`)
     absent from agent text outside the whole `## Your task message` section (template, placeholder
     table, optional-line note; the tables carry no example paths) (review 1 F5).
   - `template(path)`: first ```` ```text ```` block after `## Your task message`; lines
     `Label: value`; every `<PLACEHOLDER>` in the template is defined in the agent's own placeholder
     table and vice versa; label set equals the test's per-role `KINDS` map (so a new label forces a
     test decision).
   - **Mechanical fill** (review 1 F2): `fill(template, feature_json, all_json, config, ids)` maps
     `<UPPER_SNAKE>` → camelCase and looks it up in the `ac_feature.py --feature F001` output, then
     in the config; `RUN_ID`, `ANALYZE_ID`, `FEATURE_LIST` (and `SPEC_INPUTS`, joined) are the only
     special cases; a placeholder with no source raises. The guard-consistency tests use this fill, so
     renaming a `Feature.paths()` or config key fails them.
   - **Guard consistency** (one test per role): `make_project`; run `new_run.py translate|write
     --feature F001` (and `new_analyze.py` for the judge after a write run) — this writes the real
     marker; fill placeholders from `ac_feature.py --feature F001`, `ac_feature.py --all`, `CONFIG`
     and the printed ids; create a sample file in each folder input, plus `input-feedback.md`,
     `writer-report.md` and `ac-results.md` where the template names them; then run the guard with
     that role's `agent_type`:
     - file input → Read allowed; folder input → Glob (`path` = folder, `pattern` `**/*`) and Read of
       the sample file allowed; *AC test project* → Read of the csproj allowed and Glob rooted at it
       denied (the agent text's warning is true); *Project file* → Read allowed; *Feature folders* → Read of each `spec.md` and
       `acceptance.md` allowed; *Public API listings* → Read of `api/A.cs` allowed;
     - outputs: translator Write `<FEATURES_DIR>/alpha.feature`, writer Write
       `<STEP_DEFINITIONS_DIR>/A.cs`, `<SUPPORT_DIR>/B.cs`, `<SHARED_SUPPORT_DIR>/C.cs`, and each
       report path → allowed;
     - *Allowed build command* → Bash with that command allowed;
     - value lines (Feature, Run, Analyze, Test framework, Current feature) → no call.
   - Text checks (A05): translator has `@<TAG>` and the `<name>.feature` rule; writer has
     `[Scope(Tag = "<TAG>")]`, `Cross-feature changes`, `API-CHANGED:`, `UNEXPRESSIBLE:`,
     `PendingStepException`, `BeforeTestRun`; judge lists the seven verdicts, the Summary header,
     both markers equal to `extract_feedback.BEGIN/END` (read from the script source by regex, not
     imported), and `API-CHANGED:`; `summarize_trx.PENDING` contains `PendingStepException`.
   - Hand-back sanity: each agent's "final message" example (if any) does not match the guard's
     `CODE` regex (copied from the guard source by regex).
   — R19, A01–A05
7. **Docs:** payload README (agents row done; `ac_feature.py` row mentions `--all`); `docs/CONFIG.md`
   (`testFramework` row and example, `--all`); `docs/WORKFLOW.md` §3.2 principle 3 (templates are
   in the agent files) and §4 (`SUPERSEDED` for regression only, `API-CHANGED`, scoped bindings,
   no test-run hooks); DESIGN decision-log row; spec status. — R21
8. **Verify:** `uv run pytest -q --tb=short` (log in scratchpad); optional 3.11 run as in step 2; grep
   payload for R02 strings; mutation spot-check: drop `testFramework` from the guard's enum check and
   from an agent's placeholder table → tests fail. — R22, A06
9. **Tracker** row 3 + notes (step 4: copy templates verbatim and test them against the agents; the
   marker lifecycle issue that the main agent could invoke an AC agent itself with a stale marker;
   `ac_feature.py --all` fails on any non-feature folder under `specs/`, so init or the command should
   warn early; step 5: init detects `testFramework`; step 7: confirm A1/A3/A6). — R22

## Test list

- `test_guard.py::test_invalid_config_blocks_everything[testFramework missing|unknown]`
- `test_scripts.py`: `test_config_test_framework_invalid[missing|unknown]`, `test_feature_all`,
  `test_feature_all_empty`, `test_feature_all_with_feature_is_usage_error`,
  `test_feature_all_bad_folder`
- `test_agents.py`: `test_frontmatter[3]`, `test_no_ct_strings`, `test_no_hard_coded_paths[3]`,
  `test_placeholders_defined[3]`, `test_template_labels_known[3]`, `test_guard_consistency[3]`,
  `test_translator_rules`, `test_writer_rules`, `test_judge_rules`, `test_pending_is_counted`

## Review dispositions

### Round 1 (`03-agents.review-1.md`, REVISE)

- F1 MAJOR — ACCEPTED. Writer template gets `Project file: <AC_PROJECT>` after *AC test project*
  (config `acProject`; guard `readable_file` allows it). Spec R04 amended (writer label list); the judge
  does not need it. `test_guard_consistency` reads it.
- F2 MAJOR — ACCEPTED. Step 6: templates are filled mechanically (`<UPPER_SNAKE>` → camelCase → key of
  `ac_feature.py --feature F001` output, then `CONFIG`; only `RUN_ID`, `ANALYZE_ID`, `FEATURE_LIST` are
  special); a placeholder with no source fails the test. Hand-written "Design table" check dropped.
- F3 MINOR — ACCEPTED. Step 3: the translator's "What you can see" lists only the active run's report;
  CT's "earlier translation reports" sentence is dropped.
- F4 MINOR — ACCEPTED. Step 3: an AC item is any entry in the AC list of `acceptance.md`; an entry
  without an `AC-NNN` id or traceability is an issue (id `—`); coverage tables and "not testable" lists
  are context. Spec R08 wording amended accordingly.
- F5 MINOR — ACCEPTED. The scan for hard-coded paths skips the whole `## Your task message` section
  (template, placeholder table, optional-line note); the placeholder tables carry no example paths.
- F6 MINOR — ACCEPTED as a tracker note (step 4/5: init or the command warns about non-feature folders
  under `specs/`); behaviour unchanged (spec R20).
- F7 MINOR — ACCEPTED. Spec R04 amended with the placeholder spellings (UPPER_SNAKE of the source key).
- F8 MINOR — ACCEPTED. Assumption A6 added; step 9 tracker note lists it for step 7.

### Round 2 (`03-agents.review-2.md`, APPROVE)

- F1 MINOR — ACCEPTED. Step 6: the judge and the writer get Glob on `<AC_PROJECT_DIR>/Features`,
  `Samples`, `StepDefinitions`, `Support` (and the writer on another feature's sibling folder,
  `StepDefinitions/F002`) asserted allowed. Agent text names those subfolders without a trailing
  slash (`Shared` inside `Support`), so the path scan stays meaningful.
- F2 MINOR — ACCEPTED. Step 9 tracker note: the step 4 command builds `<FEATURE_LIST>` and
  `<SPEC_INPUTS>` with a deterministic join (or a text-output flag), never by hand.
- F3 MINOR — ACCEPTED. Steps 3–5 name `/speckit-ac-translate`, `/speckit-ac-tests-write`,
  `/speckit-ac-tests-analyze`; `test_frontmatter` asserts the exact name per role.
- F4 MINOR — ACCEPTED. Step 4: "every `[Binding]` class it creates"; "never change another class's
  `[Scope]`".
