# Plan — Step 2: port the guard and scripts to the per-feature model

Spec: `docs/steps/02-runtime-port.spec.md` (approved 2026-11-07, decisions 1–8).
Sources (read only): `<original project>\.claude\hooks\{guard.py,test_guard.py}`, `<original project>\.claude\scripts\*.py`.

## Facts (observed)

| # | Fact | Where |
|---|---|---|
| F1 | CT guard: one file, `Guard` class, `main()` policy (G1 locks, G2 isolated folders, G3 features), `ac_role()` default-deny, `SubagentHandback` code regex, worktree root rule, fail-closed `__main__` | CT `hooks/guard.py` |
| F2 | CT test: 105 table cases + 2 input cases, run via `subprocess [sys.executable, -I, guard.py]` in a temp project with the CT config copied in; per-case lock files in root and worktree | CT `hooks/test_guard.py` |
| F3 | CT scripts take the root from `Path(__file__).parents[2]` and keep everything under `.workflow/`; `changed_files.py` stores the snapshot in the git dir; skip regex `^(\.git\|bin.*\|obj.*)$` | CT `scripts/*.py` |
| F4 | `.specify/feature.json` = `{"feature_directory": "specs/001-stub"}` | spike project, spec-kit `specify.md:99` |
| F5 | spec-kit numbering: sequential `NNN-` (≥ 3 digits) or `feature_numbering: "timestamp"` → `YYYYMMDD-HHMMSS-`; custom `SPECIFY_FEATURE_DIRECTORY` possible | spec-kit `specify.md:84–92`, `create-new-feature.ps1` |
| F6 | `tests/test_stdlib_only.py` scans `src/speckit_ac/**/*.py` (payload included) and allows only stdlib + `speckit_ac` | repo |
| F7 | `pyproject.toml`: `testpaths = ["tests"]`, Python ≥ 3.11; current suite 10 tests | repo |
| F8 | `python -I` implies `-P`: the script's folder is not on `sys.path` | Python docs (`-I` = `-E -P -s`) |

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| A1 | spec-kit copies `payload/` 1:1 to `.specify/extensions/ac/`, so `parents[4]` of a script/guard is the project root | 0.9 | Root wrong → scripts fail loudly (checked: `parents[3].name == ".specify"`) | Step 1 result 3.1 (copied); step 6 install test |
| A2 | Reqnroll puts the feature folder in the generated namespace (`…Features.F001.XFeature`), so `className` in the TRX carries `F001` | 0.7 | Feature column falls back to name lookup (still correct unless names collide) | Fallback implemented and tested; confirmed in step 7 e2e |
| A3 | A user-typed `/speckit-ac-x` is not a `Skill` tool call | 0.85 | Users could not start the commands | This session shows typed skills expand without a `Skill` call; step 7–8 smoke test |
| A4 | Target projects use git (snapshot lives in the git dir, as in CT) | 0.9 | `changed_files.py` fails with a clear message | spec-kit projects are git repos by default; init (step 5) can check |
| A5 | TRX from xUnit v3/MTP (`--report-xunit-trx`), VSTest xUnit/NUnit/MSTest share the `TeamTest/2010` schema and `UnitTest/TestMethod@className` | 0.8 | `summarize_trx` misses tests for some runner | Synthetic TRX tests now; real runners in steps 5/7 |

None is blocking (no `confidence < 0.7` with high consequence).

## Design

### Installed layout and root
- Guard: `.specify/extensions/ac/hooks/guard.py`; scripts: `.specify/extensions/ac/scripts/*.py`.
- `aclib.root()` = `Path(<script>).resolve().parents[4]`; FAIL unless `parents[3].name == ".specify"`.
  Computed inside `main()`, never at import (so tests can import `export_refs` for its pure functions).
- Guard root: `CLAUDE_PROJECT_DIR`, else the same location rule; CT worktree rule kept (F1).

### Config (`.workflow/config.json`, schema v1)
Required keys: `schemaVersion` (int 1), `python`, `solution`, `specInputs` (list of str),
`acSurfaceProjects` (list), `unitTestProjects` (list), `acProjectDir`, `acProject`, `refsDir`,
`acRefBuildCommand`, `unitTestCommand`, `acTestCommand` (str). `acProjectDir`, `refsDir` and every
`specInputs` entry: backslashes → `/`, `posixpath.normpath`, stored in that normalised form; invalid
when the result is empty, `.`, absolute, has a drive letter or starts with `..` (review 2 F1). Guard and `aclib` run the same check
(the guard keeps its own copy: decision 6).

### Feature resolution (`aclib.resolve_feature(root, arg)`)
- `arg` None → `.specify/feature.json` `feature_directory` (missing → FAIL "no current feature; pass
  `--feature`").
- `F<digits>` / `<digits>` (≥ 3 digits) → the single `specs/<digits>-*` folder.
- `specs/<name>`, `<name>`, absolute path inside the root, backslashes, trailing slash accepted.
- Rejected: `.specify/init-options.json` `feature_numbering == "timestamp"`; name matching
  `^\d{8}-\d{6}-`; name not matching `^\d{3,}-.+`; more than one segment below `specs/`; folder
  missing; another `specs/<same digits>-*` folder exists.
- Result `Feature(dir, number, tag)`, plus helpers for `spec`, `acceptance`, `ac`, `runs`, lock files
  and the AC project's `Features/T`, `Samples/T`, `StepDefinitions/T`, `Support/T`.

### Active-run marker (`.workflow/active-run.json`)
`{"role", "feature": "specs/001-alpha", "tag": "F001", "run": "run-002", "analyze": "analyze-1" | null}`.
Guard validation: role equals `agent_type`; feature matches `^specs/\d{3,}-[^/\\]+$`, no `..`, not a
timestamp name, folder exists, no other `specs/<same digits>-*` folder, `.specify/init-options.json`
not set to `feature_numbering: "timestamp"` (R05 in full, review F5); `tag == "F" + digits`; run matches `^translate-\d{3,}$` for the
translator and `^run-\d{3,}$` for writer/judge; `analyze` matches `^analyze-\d+$` for the judge and
is null otherwise. Any failure → deny with "no valid active run for <role>".

### Guard rules (paths are project-relative, case-folded on Windows; `<ac>` = `acProjectDir`)
- **Missing config:** main policy → only the `Skill` rule; AC roles → deny. **Invalid config** → exit 2.
- **Main policy:**
  1. `Skill`: `tool_input.skill`, stripped, leading `/` removed, lower-cased; starts with
     `speckit-ac-` or `speckit.ac.` → deny ("ask the user to type /…").
  2. Write tools with a path inside the project:
     - `specs/*/ac/*.lock` → deny always;
     - `specs/*/ac/runs/**`, `<refsDir>/**`, `.workflow/active-run.json` → deny;
     - `specs/<n>/acceptance.md` while `specs/<n>/ac/sources.lock` exists → deny;
     - `<ac>/Samples/F<d>/**` while any `specs/<d>-*/ac/sources.lock` exists → deny;
     - `<ac>/Features/**` → deny (G3).
  3. G2 unchanged from CT (texts, shell cwd rule, `file_path`/`notebook_path`/`path` fields, search
     rooted at `<ac>`).
- **AC roles** (marker gives `S`, `T`, `run`, `an`; `R = S/ac/runs/<run>`):

| | translator | writer | judge |
|---|---|---|---|
| read files | `S/spec.md`, `S/acceptance.md`, constitution, `R/translation-report.md` | `S/spec.md`, `S/acceptance.md`, constitution, `R/input-feedback.md`, `R/writer-report.md`, files directly in `<ac>/` | `specs/*/spec.md`, `specs/*/acceptance.md`, constitution, `R/writer-report.md`, `R/<an>/ac-results.md`, files directly in `<ac>/` |
| read folders (= search roots) | `specInputs`, `<ac>/Samples/T`, `<ac>/Features/T` | `specInputs`, `<ac>/{Features,Samples,StepDefinitions,Support}`, `refsDir` | same as writer |
| write | `<ac>/Features/T/**/*.feature` (not while `S/ac/features.lock`), `R/translation-report.md` | `<ac>/StepDefinitions/**`, `<ac>/Support/**` except `*.feature`, `R/writer-report.md` | `Write` of `R/<an>/judge-report.md` |
| Bash | exactly `acRefBuildCommand` | same | none |

  Grep/Glob: `path` required and must be a search root or a readable file; patterns (`Glob.pattern`,
  `Grep.glob`) relative, no `..`. `SubagentHandback`: CT code regex. Everything else denied.
  `specInputs` entries are matched with `under()`, so a file entry is a readable file and a folder
  entry is a search root. "Files directly in `<ac>/`" means `Path.is_file()` is true (review F1): the
  folders `<ac>/bin`, `<ac>/obj`, `<ac>/obj-ref` are neither readable nor search roots.
- Root fallback without `CLAUDE_PROJECT_DIR`: `parents[4]` of the guard, and an error (exit 2) unless
  `parents[3]` is named `.specify` (review F9).
- Log: `.workflow/guard.log`, one line per subagent call (OSError ignored).

### Scripts (all: `sys.path.insert(0, <own folder>)`, `import aclib`, `argparse`, FAIL → exit 1)
- `ac_feature.py [--feature]` → JSON with the paths above.
- `ac_lock.py {lock,verify,unlock,confirm-spec} {sources,features} [--feature]`, lock JSON
  `{group, feature, files, spec?}`; verify: files differ → exit 1, only spec differs/missing → exit 3;
  `confirm-spec` only for `sources`, only when files match.
- `new_run.py {translate,write} [--feature]`, `new_analyze.py [--feature]`: CT numbering in `R`, CT
  feedback copy, marker written, output = folder path + feature line.
- `changed_files.py {snapshot | check <role>}`: CT + extra folders `.workflow`, `refsDir`,
  `specs/*/ac`; skip `.workflow/guard.log`; skip segment regex tightened to
  `^(\.git|bin|obj)([-_.].*)?$` (CT's `bin.*` also skipped folders like `Bindings/`; spec R16 amended);
  allowlist from the marker (same as the guard's write rules); role ≠ marker role → FAIL. Required
  order (docstring + CONFIG.md): `new_run.py`/`new_analyze.py` → `snapshot` → subagent → `check`.
- `check_features.py [--feature]`: CT checks over `<ac>/Features/T/**/*.feature`; feature tags are
  those matching `^@F\d+$` (so `@Fast` is not one); feature-level ones must be exactly `{@T}`;
  scenario-level ones ⊆ `{@T}`; zero files → FAIL.
- `clear_generated.py {features,steps} [--feature]`: T folders only, `.gitkeep` kept, `features`
  refused while `features.lock` exists.
- `record_skips.py <translate-run> <AC-id>… [--feature]`: CT logic in `R`; the run id must match
  `^translate-\d{3,}$` (review F8).
- `summarize_trx.py <trx> <out> [--current FN]`: index `.feature` files by their `Features/F<d>/`
  folder; `testId → className` from `UnitTest/TestMethod`; feature from an `F\d{3,}` className segment
  that exists in the index, else name lookup (ambiguous across features → feature `?`, marked); table
  `Feature | Scenario | Tags | Outcome | Duration`; failures titled `FN/AC-NNN name`; `--current` →
  sections "Current feature (FN)" and "Regression (other features)" with their own totals.
- `export_refs.py`: CT; root/config via `aclib` inside `main()`. `extract_feedback.py`: CT unchanged
  apart from the docstring (no `aclib`).

## Steps

0. **`tests/test_stdlib_only.py`** — add `aclib` to `ALLOWED` first, so the suite stays green while
   the scripts land (review F2). *(R03)*
1. **`docs/CONFIG.md`** — schema v1 table (key, type, meaning, used by), example, validation rules,
   derived per-feature paths, `.workflow/` files (`config.json`, `active-run.json`, `guard.log`); scripts
   are invoked by the cwd-relative path `.specify/extensions/ac/scripts/<name>.py` (review 2 F6); the
   snapshot order.
   *(S02-R04, R24)*
2. **`payload/scripts/aclib.py`** — `root()`, `fail()`, `load_config()`, `resolve_feature()`,
   `Feature`, `glob_regex()`, `numbered()`, `sha256()`, `write_marker()`, `read_marker()`,
   `feature_arg(parser)`. *(R02, R03, R04, R05, R06, R07)*
3. **`payload/hooks/guard.py`** — port per Design; standalone. *(R02, R07, R08–R13)*
4. **`payload/scripts/ac_feature.py`**. *(R06)*
5. **`ac_lock.py`**. *(R14)*
6. **`new_run.py`, `new_analyze.py`**. *(R07, R15)*
7. **`changed_files.py`**. *(R16)*
8. **`check_features.py`**. *(R17)*
9. **`clear_generated.py`**. *(R18)*
10. **`record_skips.py`**. *(R19)*
11. **`summarize_trx.py`**. *(R20)*
12. **`export_refs.py`, `extract_feedback.py`**. *(R21)*
13. *(moved to step 0)*
14. **`tests/acproject.py`** (helper module imported by both test files) — `make_project(base, …)`:
    copies the payload to `.specify/extensions/ac/`, writes the neutral config (`App.*` names,
    `specInputs: ["docs/domain"]`) or a raw/missing config, `.specify/feature.json`,
    `.specify/memory/constitution.md`, `specs/001-alpha/` and `specs/002-beta/` (`spec.md`,
    `acceptance.md`, `plan.md`, `tasks.md`), the AC folders (`F001`, `F002`, `Support/Shared`) and the
    csproj; `run_script()` / `run_guard()` helpers (`sys.executable -I`, `CLAUDE_PROJECT_DIR`). The guard
    fixture builds the root project, a **full second project** at `.claude/worktrees/wt` (own config,
    specs, AC folders; locks and marker set per case like the root) and an empty `.claude/worktrees/bare`
    without config (review F3). *(R22, R23)*
15. **`tests/test_guard.py`** — `CT_CASES` (every CT case, CT description kept verbatim, paths per the
    mapping below), `NEW_CASES` (per-feature, cross-feature, marker, main-policy, `Skill`, config
    states), input cases. Per case: lock files and marker set in root and worktree, then run.
    *(R22; A02–A05)*
16. **`tests/test_scripts.py`** — per-script tests listed in "Test list". *(R23; A06)*
17. **Docs** — payload `README.md` layout table (files now present); `docs/WORKFLOW.md` §3.1 (marker
    row, main-agent write denials), §3.2 (principle on the active run; missing-config rule), §5
    (spec drift exit 3 + `confirm-spec`), §6 (Bash can still write denied paths; the main agent can
    edit the installed guard/scripts under `.specify/extensions/ac/` and `.claude/settings.json`,
    review F10). *(R01, R24)*
18. **Verify** — `uv run pytest -q --tb=short`; grep the payload for `SPEC.md|knowledge-base|CT\.|\.workflow/runs|experiment-log|WORKFLOW-SETUP`;
    optional 3.11 run in the scratchpad (as step 0). *(R25; A01, A07)*
19. **Tracker** — row 2 status, links, verification, open items (for step 4: invoke scripts by the
    cwd-relative path, clear or replace the marker after a subagent; v1.0 feature-folder limit, also in
    the user-level memory note on deferred portability issues); spec status line. *(R25)*

### CT case mapping (for S02-A02)
Every CT case keeps its description; substitutions:

| CT | New |
|---|---|
| `{SRC}/translate.md` (AC `.md`) | `specs/001-alpha/acceptance.md` |
| `docs/SPEC.md` | `specs/001-alpha/spec.md` |
| `knowledge-base/…` (spec input folder) | `docs/domain/…` |
| `{AC}/Features/X.feature`, `{AC}/Samples/x`, `{AC}/StepDefinitions/A.cs`, `{AC}/Support/Ctx.cs` | same under `F001/` |
| `.workflow/runs/translate-001/…`, `run-001/…`, `run-001/analyze-1/…` | `specs/001-alpha/ac/runs/…` (marker points at these runs) |
| `run-002/input-feedback.md` ("writer reads input feedback" ALLOW, "judge reads input feedback" DENY) | `run-001/input-feedback.md` (the active run; other runs are covered by new cases) |
| `.workflow/sources.lock`, `features.lock` | `specs/001-alpha/ac/sources.lock`, `features.lock` |
| `CT.Core`, `CT.AcceptanceTests`, `CT.Tests` | `App.Core`, `App.AcceptanceTests`, `App.Tests` |
| "translator Glob in AC sources" (`{SRC}`) | Glob in `{AC}/Samples/F001` (the AC `.md` is now a single file, its folder holds `plan.md`) |
| locked groups `SOURCES`/`FEATURES`/`BOTH` | the same groups on feature 001 |

No CT expectation flips.

### Test list (new)
- Guard, per/cross-feature: translator read/write `Features/F002`, read `specs/002-beta/spec.md`,
  read `specs/001-alpha/plan.md` → deny; translator reads constitution → allow; translator Glob
  `specs/001-alpha` → deny; translator writes `Features/F001` while `features.lock` → deny;
  writer edits `StepDefinitions/F002/X.cs` → allow; writer reads `specs/002-beta/acceptance.md` →
  deny; writer reads `Samples/F002/x` → allow; judge reads `specs/002-beta/spec.md` → allow; judge
  reads `specs/002-beta/plan.md` → deny; all three read `specs/001-alpha/tasks.md` → deny; Grep with
  `path` = readable file → allow.
- Marker: missing, malformed JSON, wrong role, feature with `..`, feature missing, timestamp
  feature, duplicate feature number, `feature_numbering: "timestamp"`, tag mismatch, run of the wrong
  kind, judge without `analyze`, translator with `analyze`, `SubagentHandback` without a marker →
  deny; report of `translate-002`/`run-002`/`analyze-2` while active is 001/1 → deny.
- `<ac>` folders (review F1): writer and judge Grep `path=<ac>/bin` → deny, Glob `path=<ac>/obj` →
  deny, Read `<ac>/bin` → deny, Grep `path=<ac>/App.AcceptanceTests.csproj` → allow. Judge `Edit` of its
  report → deny (F6).
- Root (F9): no `CLAUDE_PROJECT_DIR` (removed from the child env) → rules still apply from the
  installed location: main Read of a step definition → deny, translator Read of
  `specs/001-alpha/spec.md` with a valid marker → allow; guard copied to a folder outside
  `.specify/extensions/ac/hooks/` without the env var → exit 2.
- Shared feature-folder table (review 2 F3) in `tests/acproject.py`: `specs/001-alpha` valid,
  `specs/0001-delta` valid, `specs/01-x`, `specs/20260319-143022-login`, `specs/scope/001-x`,
  `specs/001-alpha` + `specs/001-other`, `specs/001-alpha/../002-beta`, `feature_numbering: timestamp`
  invalid — run through both `ac_feature.py --feature` and the guard's marker.
- Writes of `.feature` (review 2 F7, review 3 F1): translator writes `Features/F001/x.cs` → deny;
  writer writes `StepDefinitions/F001/Extra.feature` / `Support/Shared/Extra.FEATURE` → deny; main
  writes `Samples/F001/x.feature` (unlocked) and `<ac>/Extra.feature` → deny; `changed_files check`
  flags translator `Features/F001/Steps.cs` and writer `StepDefinitions/F001/Extra.feature`.
- `changed_files` with `.gitignore` (`artifacts/`, `specs/*/ac/runs/`): writer-phase writes into
  `specs/002-beta/ac/runs/run-001/` and `artifacts/refs/api/` are reported as breaches (review 2 F5).
- `check_features`: `@Fixture` on the Feature line and `@Fast` on a scenario → OK (review 2 F4).
- Every per-feature script prints `specs/001-alpha (F001)` (review 3 F3).
- `specInputs` overlapping `specs`, the AC project or each other's protected folders → invalid config
  (review 3 F5).
- Config paths (review 2 F1): `acProjectDir: "./tests/App.AcceptanceTests/"` → main Read of a step
  definition still denied; `acProjectDir: "."` → invalid config (deny all).
- Main policy: write `specs/002-beta/acceptance.md` while only 001 locked → allow; write
  `Samples/F001/x` while 001 sources locked → deny, while 002 locked only → allow; write
  `specs/002-beta/ac/sources.lock` unlocked → deny; write `specs/001-alpha/ac/runs/run-001/input-feedback.md`
  → deny; write `artifacts/refs/api/A.cs` → deny; write `.workflow/active-run.json` → deny; read
  `specs/001-alpha/ac/runs/…` → allow; `Skill speckit-ac-translate`, `/speckit-ac-init`,
  `SpecKit-AC-Critic` → deny; `Skill speckit-plan` → allow; Explore `Skill speckit-ac-tests-write` →
  deny.
- Config states (separate temp projects): missing → main Read allow, main `Skill speckit-ac-init`
  deny, writer Read deny; broken JSON / `schemaVersion` 2 / missing key / `acProjectDir` with `..` →
  main Read deny.
- Scripts: `ac_feature` (default, `F002`, `002`, `002-beta`, `specs\002-beta\`, absolute; errors:
  timestamp folder, `feature_numbering` timestamp, duplicate number, two digits, nested, no
  feature.json, missing config); `ac_lock` (lock/verify ok; changed/added/removed → 1; spec change →
  3; `confirm-spec` → verify 0; `confirm-spec` with changed files → 1; `confirm-spec features` →
  usage error; features lock without `.feature` → 1; unlock); `new_run`/`new_analyze` (numbering,
  marker contents per role, feedback copy, no run → 1, per-feature isolation of numbering);
  `changed_files` (git repo: allowed change → 0; `src/x.cs` → 1 breach; `Bindings/` not skipped;
  `bin/` skipped; role mismatch → 1; no snapshot → 1); `check_features` (valid; missing `@F001`;
  scenario `@F002`; duplicate `@AC-001`; no When; mistyped keyword; zero files); `clear_generated`
  (features: F001 only, `.gitkeep` kept, refused when locked; steps: keeps `Support/Shared` and
  F002); `record_skips` (ok, unknown id → 1, file in feature runs); `extract_feedback` (with/without
  markers); `summarize_trx` (two features via className, fallback by name, ambiguous name,
  `--current` sections, failure title `F001/AC-002 …`, non-AC stack frames hidden); `export_refs`
  pure functions (`public_only` drops an internal type and its empty namespace, keeps public;
  `LOGIC` flags `return`); a script run from outside `.specify/extensions/ac/scripts` → FAIL.

## Requirement coverage

| Req | Steps |
|---|---|
| R01 | 2–12, 17, 18 |
| R02 | 2, 3 |
| R03 | 2, 3, 13 |
| R04 | 1, 2, 3 |
| R05, R06 | 2, 4 |
| R07 | 2, 3, 6 |
| R08–R13 | 3, 15 |
| R14–R21 | 5–12, 16 |
| R22 | 14, 15 |
| R23 | 14, 16 |
| R24 | 1, 17 |
| R25 | 18, 19 |

## Review dispositions

### Round 1 (`02-runtime-port.review-1.md`, REVISE)

| # | Sev | Disposition |
|---|---|---|
| F1 | MAJOR | ACCEPTED. Design: the "files directly in `<ac>/`" branch requires `Path.is_file()`, so `<ac>/bin`, `<ac>/obj` (folders) are neither readable nor search roots. Test list: writer/judge Grep `<ac>/bin` → deny, Glob `<ac>/obj` → deny, Grep `<ac>/App.AcceptanceTests.csproj` → allow. |
| F2 | MINOR | ACCEPTED. Step 13 moved first (now step 0). |
| F3 | MINOR | ACCEPTED. Step 14 describes the worktree (full second project under `.claude/worktrees/wt`) and the `BARE` folder. |
| F4 | MINOR | ACCEPTED. Mapping table: `run-002` in CT's input-feedback cases → `run-001` (the active run). |
| F5 | MINOR | ACCEPTED. Guard marker validation also denies when `.specify/init-options.json` has `feature_numbering: "timestamp"` and when more than one `specs/<N>-*` folder exists. Tests added: malformed marker JSON, duplicate-number feature, timestamp numbering, `SubagentHandback` without a marker. |
| F6 | MINOR | ACCEPTED. Test: judge `Edit` of its report → deny. |
| F7 | MINOR | ACCEPTED. Spec R16 amended to name the tightened build-folder rule. Order `new_run.py`/`new_analyze.py → snapshot → subagent → check` stated in `changed_files.py`'s docstring and `docs/CONFIG.md`. |
| F8 | MINOR | ACCEPTED. `record_skips.py` validates `^translate-\d{3,}$`; test with `translate-001/../x` → 1. |
| F9 | MINOR | ACCEPTED. Guard fallback fails (exit 2) unless `parents[3]` is `.specify`; tests: no `CLAUDE_PROJECT_DIR` → allow; guard copied outside `.specify/extensions/ac/hooks/` with no env var → exit 2. |
| F10 | MINOR | ACCEPTED as documentation: WORKFLOW §6 names it (same exposure as CT; `.claude/settings.json` is equally editable). A guard denial is not in the approved spec; offered as a follow-up. |

### Round 2 (`02-runtime-port.review-2.md`, REVISE)

| # | Sev | Disposition |
|---|---|---|
| F1 | MAJOR | ACCEPTED. Design "Config": `acProjectDir`, `refsDir`, `specInputs[*]` are `posixpath.normpath`-ed (backslashes → `/` first) and stored normalised; empty, `.`, absolute, drive-letter or `..`-leading results are invalid. Tests: `"./tests/App.AcceptanceTests/"` → StepDefinitions read still denied; `"."` → invalid config. |
| F2 | MINOR | ACCEPTED. Fallback test: `run_guard(project_dir=None)` removes the variable from the child env; added translator Read of `specs/001-alpha/spec.md` with a valid marker → ALLOW (only passes if the root really is the temp project). |
| F3 | MINOR | ACCEPTED. `tests/acproject.py` holds `FEATURE_FOLDERS` (folder, extra setup, valid?); `test_scripts.py` runs `ac_feature.py --feature` and `test_guard.py` runs a marker for each row. |
| F4 | MINOR | ACCEPTED. Regex `^@F\d+$` named in step 8; test with `@Fast` on a scenario → OK. |
| F5 | MINOR | ACCEPTED. `changed_files` test repo gets `.gitignore` (`artifacts/`, `specs/*/ac/runs/`); a write into `specs/002-beta/ac/runs/…` and into `artifacts/refs/…` during the writer phase must be breaches. |
| F6 | MINOR | ACCEPTED. `docs/CONFIG.md` and tracker open items: commands invoke scripts by the cwd-relative path `.specify/extensions/ac/scripts/<name>.py`, never via `$CLAUDE_PROJECT_DIR`. |
| F7 | MINOR | ACCEPTED as a spec amendment (R10/R11 tightened): the translator writes only `*.feature` files under `Features/T/` (plus its report); the writer may not write any `*.feature`. Same rules in `aclib.write_allowlist` / `changed_files.py check`. Tests for both. |
| F8 | MINOR | DECLINED for step 2: the marker's lifecycle belongs to the command flow (step 4); recorded as a tracker open item for step 4. |
| F9 | MINOR | ACCEPTED. Step 19: tracker notes name the limit; the user-level memory note `deferred-portability-issues` item 7 already records it. |

### Round 3 (`02-runtime-port.review-3.md`, REVISE, no BLOCKER → implement per the workflow)

| # | Sev | Disposition |
|---|---|---|
| F1 | MAJOR | ACCEPTED. Main policy: any write under `<ac>/` whose path ends in `.feature` (case-insensitive) is denied, in addition to every write under `<ac>/Features/**`. Tests: main writes `Samples/F001/x.feature` (unlocked) → deny; main writes `<ac>/Extra.feature` → deny. |
| F2 | MINOR | ACCEPTED. Test list below now names `@Fast`/`@Fixture`, the `.gitignore` + ignored-folder breaches, and the `.feature` breach checks; step 1 lists the cwd-relative invocation rule. |
| F3 | MINOR | ACCEPTED. Every per-feature script prints `specs/NNN-x (FNNN)` in its result line (`ac_lock` all four commands, `check_features`, `clear_generated`, `record_skips`, `new_run`, `new_analyze`; `ac_feature` prints JSON). One parametrised test asserts it for each. |
| F4 | MINOR | ACCEPTED. WORKFLOW §6 also names `.workflow/config.json`. |
| F5 | MINOR | ACCEPTED (validation). A `specInputs` entry that equals, contains or lies under `specs`, `.specify`, `.workflow`, `acProjectDir` or `refsDir` makes the config invalid (guard exit 2, scripts exit 1). Tests: `specInputs: ["specs"]`, `["tests"]` (contains the AC project), `["specs/001-alpha"]` → invalid. Choosing sensible inputs (never `src/`) stays a step 5 init rule; tracker open item. |
