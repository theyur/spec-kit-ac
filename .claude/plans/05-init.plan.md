# Plan — step 5: `/speckit-ac-init`

Spec: `docs/steps/05-init.spec.md` (approved 2026-11-08, decisions 1–10 as drafted).

## Facts (observed, 2026-11-08)

Probes ran in the session scratchpad (`p5/`): a solution with a `net10.0` classlib, an AC project
written by hand per framework × runner, a feature with one bound and one unbound scenario, and the
real payload scripts.

- **F1 — msbuild evaluation.** `dotnet msbuild <proj> -getProperty:A -getProperty:B -getItem:PackageReference
  -getItem:FrameworkReference -getItem:PackageVersion` prints JSON (`Properties`, `Items`) without a restore.
  - The implicit `FrameworkReference Microsoft.NETCore.App` has `IsImplicitlyDefined: "true"` and
    `PrivateAssets: "All"`.
  - Under central package management (CPM), `PackageReference` items carry no `Version`; the
    `PackageVersion` items carry the pins.
- **F2 — CPM and `dotnet add package`.** With CPM on, `dotnet add <proj> package X` keeps an existing
  `PackageVersion` pin. For a package that has no pin, it adds one with the latest stable version and a
  version-less `PackageReference`.
- **F3 — `dotnet sln <x.slnx> list`.** It prints `Project(s)`, a dashed line, then one path per line
  with backslashes.
- **F4 — ref mode.** `<Reference Include="$(MSBuildThisFileDirectory)../../artifacts/refs/*.dll" Private="false" />`
  under `AcRefMode == true` works:
  - the AC project compiles a use of `App.Core.Class1` against the exported ref assembly;
  - `bin-ref/` holds no `App.Core.dll`;
  - the code-behind is in `obj-ref/Debug/net10.0/Features/F999/check.feature.cs`, and nothing is in
    `Features/`.
- **F5 — `export_refs.py`.** With `import json` added, it exports `App.Core.dll` and
  `api/App.Core.cs`. Without the import it raises `NameError` (S05 context).
- **F6 — ilspycmd.** `dotnet tool install ilspycmd --create-manifest-if-needed`, run at the root,
  installed 11.2.0.10050 into a new root `dotnet-tools.json`.
- **F7 — framework × runner matrix** (SDK 10.0.403, Reqnroll 3.3.4, latest stable packages):

  | Framework | Runner | Packages (besides the Reqnroll adapter) | Properties | TRX option | Result |
  |---|---|---|---|---|---|
  | xunit2 | VSTest | `xunit`, `xunit.runner.visualstudio`, `Microsoft.NET.Test.Sdk` | — | `--logger "trx;LogFileName=ac-results.trx"` | pass |
  | xunit2 | MTP | (same) + `UseMicrosoftTestingPlatformRunner` | `OutputType Exe` | — | **fail**: "global.json defines test runner to be Microsoft.Testing.Platform … projects using VSTest" — xUnit v2 has no first-party MTP runner |
  | xunit3 | VSTest | `xunit.v3.mtp-off`, `xunit.runner.visualstudio`, `Microsoft.NET.Test.Sdk` | `OutputType Exe` | `--logger "trx;…"` | pass. With plain `xunit.v3` it fails: "Testing with VSTest target is no longer supported by Microsoft.Testing.Platform on .NET 10 SDK" |
  | xunit3 | MTP | `xunit.v3` | `OutputType Exe` | `--report-xunit-trx --report-xunit-trx-filename ac-results.trx` | pass |
  | nunit | VSTest | `NUnit`, `NUnit3TestAdapter`, `Microsoft.NET.Test.Sdk` | — | `--logger "trx;…"` | pass |
  | nunit | MTP | `NUnit`, `NUnit3TestAdapter`, `Microsoft.Testing.Extensions.TrxReport` | `OutputType Exe`, `EnableNUnitRunner true` | `--report-trx --report-trx-filename ac-results.trx` | pass. Without TrxReport: exit 5, the option is unknown |
  | mstest | VSTest | `MSTest` | — | `--logger "trx;…"` | pass |
  | mstest | MTP | `MSTest` | `OutputType Exe`, `EnableMSTestRunner true` | `--report-trx --report-trx-filename ac-results.trx` | pass |

  Commands that worked:
  - VSTest: `dotnet test <proj> --no-build --results-directory <rel> <trx>`.
  - MTP: `dotnet test --project <proj> --no-build --results-directory <rel> <trx>`.

  In both cases the TRX lands at `<rel>/ac-results.trx`, where `<rel>` is relative to the working
  directory. The TRX `className` is `App.AcceptanceTests.Features.F999.CheckFeature` in all seven, which
  confirms step 2 assumption A2.
- **F8 — `summarize_trx.py`** reads all seven TRX files: totals, `@F999 @AC-00N` tags, the `pending`
  outcome and the step text. It needed no change.
- **F9 — the tree check.** `changed_files.tree_hashes(root, cfg)` already hashes the tree (git-listed,
  untracked and ignored `.workflow/`, `refsDir`, `specs/*/ac`), skipping `bin*/obj*/.git`.
- **F10 — the config check.** `aclib.load_config` reads the file and checks it in one function. There is
  no `validate(cfg)` to reuse for a dict that is not yet written.
- **F11 — the existing tests.** `tests/test_commands.py`:
  - `NAMES` lists 4 commands; `test_named_commands_exist` still special-cases `init`;
  - the real `specify` test expects four skills;
  - `SUBCOMMANDS` lists the script subcommands.
- **F12 — the guard log.** It writes `agent_type\ttool\tdecision`, one line per AC-role call, and
  nothing for the main agent.
- **F13 — `IsTestProject` (added in round 1).** The evaluated `IsTestProject` is empty for the xUnit v3
  MTP project and `true` for the NUnit VSTest and MSTest MTP projects; it comes from package props. Test
  projects are therefore recognised by their framework packages as well (review 1, finding 2).
- **F14 — `dotnet tool list --local`.** It prints a table whose first column is the package id (here
  `ilspycmd`).
- **F15 — `dotnet new sln` on SDK 10** creates `.slnx` by default. `dotnet sln list` reads both formats.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| A1 | The F7 recipes still hold with a pre-existing unit test project in the solution (versions taken from it, CPM pins) | 0.75 | Restore or version conflicts (NU1605) in real projects | The opt-in end-to-end test builds each combination **with** a unit test project of the same recipe (step 12) |
| A2 | `dotnet msbuild -getItem` works on every SDK-style project without a restore (F1) | 0.85 | Detection fails before restore | The end-to-end test runs detection on a never-restored copy |
| A3 | A hand-written minimal csproj fixture is enough to test detection (no NuGet) | 0.85 | Detection tests need the network | Use only evaluation queries in the non-e2e tests |
| A4 | CS0168 (an unused local) is a compiler warning in every configuration, so it can stand in for the spec's "nullable warning" when checking that warnings-as-errors applies in ref mode (deviation D1) | 0.9 | False FAIL when a project suppresses CS0168 | The check runs only when the **evaluated** ref-mode `TreatWarningsAsErrors` is true and `NoWarn` doesn't contain CS0168; otherwise SKIP with the reason |
| A5 | Model behaviour in smoke mode (tries each action once) is out of scope for the tests: the tests check that the real guard gives every listed action its expected decision | 0.9 | — | step 7 runs it live |
| A6 | `git` is available wherever init runs (it is in the environment checks) | 0.95 | `tree_hashes` fails | the env check reports no git as a blocker |

None is blocking: the one with the lowest confidence (A1) is checked by the step 12 runs before the tracker is updated.

## Design

All new scripts live in `payload/scripts/`, use only the standard library, and run as
`<python> .specify/extensions/ac/scripts/<name>.py`. In setup mode `<python>` is the fixed
`uv run --no-project python -I`; in verify and smoke mode it is the config's `python`.

- **`aclib.py` additions:**
  - `validate_config(cfg) -> cfg`, split out of `load_config` (which now reads the file and calls it);
  - `BLOCK_BEGIN = "# >>> speckit-ac (managed; do not edit)"`, `BLOCK_END = "# <<< speckit-ac"`;
  - `write_block(path, lines) -> bool` (changed?): replaces an existing block in place, otherwise appends
    it after one blank line, keeps the file's other bytes, and creates the file if it is missing;
  - `remove_block(path) -> bool`.
- **`init_detect.py`:** pure functions plus thin `dotnet` / `git` calls.
  - `environment(root, which, system)` returns a list of problems;
  - `solutions(root)`;
  - `sln_projects(sln)` (F3);
  - `evaluate(project)`, one msbuild call per project (F1): `TargetFramework`, `TargetFrameworks`,
    `OutputType`, `IsTestProject`, `AssemblyName`, `ManagePackageVersionsCentrally`, plus the
    `PackageReference`, `FrameworkReference` and `PackageVersion` items;
  - `framework_of(package_ids)`: `xunit.v3*` → xunit3, `xunit`/`xunit.core` → xunit2, `NUnit` → nunit,
    `MSTest`/`MSTest.TestFramework`/`MSTest.Sdk` → mstest;
  - `runner(root)` from `global.json`;
  - `internals_visible_to(project_dir, root)`, the same search as `export_refs.check_no_internals_visible_to`,
    reading with `errors="replace"` (finding 16);
  - `root_props(root)`: whether it exists. Its `TreatWarningsAsErrors` text is for the report only; the
    verification evaluates it (finding 4);
  - **test project** = evaluated `IsTestProject` is true **or** `framework_of(...)` finds a framework
    (F13, finding 2). Only `*.csproj` entries of the solution are evaluated; the others are listed under
    `ignored` (finding 11);
  - `propose(...)`: surface candidates, unit tests, framework, `acProjectDir`, `refsDir`, TFM;
  - `supported`: whether the proposed (framework, runner) is in `init_config.RECIPES`, plus the
    supported list, so that the command stops and asks **before** the summary (finding 12);
  - `blockers`.

  It prints `{"environment": [...], "solution": ..., "solutions": [...], "runner": ..., "cpm": bool,
  "rootProps": {...}, "projects": [...], "ignored": [...], "proposal": {...}, "supported": {...},
  "blockers": [...]}`. With `--solution` it uses that file; with several and no flag, `solution` is null
  and the command asks. With `--framework` it re-evaluates `supported` for the user's chosen framework.
- **`init_config.py`:**
  - `RECIPES[(framework, runner)]` holds packages, properties and the TRX option (F7, without
    xunit2/MTP), and `UNSUPPORTED[("xunit2","mtp")]` holds the reason.
  - `build(args, root) -> cfg` uses `acProject = <dir>/<basename(dir)>.csproj` and these commands:

    | Runner | `unitTestCommand` | `acTestCommand` |
    |---|---|---|
    | VSTest | `dotnet test {project}` | `dotnet test {acProject} --no-build --results-directory {analyzeDir} --logger "trx;LogFileName=ac-results.trx"` |
    | MTP | `dotnet test --project {project}` | `dotnet test --project {acProject} --no-build --results-directory {analyzeDir} <framework's TRX option>` |

  - `implementation_folders(root)`: `src` plus every folder holding a `*.csproj`, outside `bin*/obj*`.
    A spec input that overlaps one of them fails (R04).
  - It rejects whitespace in `acProjectDir`, `refsDir` and every `unitTestProjects` entry, because they
    end up in commands split on whitespace by `shlex`, Bash and the guard's comparison (round 1 finding
    8; round 2 finding 6: not the solution, which is always passed as one argument).
  - It fails when the config exists, then calls `aclib.validate_config` and writes JSON with 2-space
    indentation.
  - Flags: `--solution`, `--surface` (repeat), `--unit-tests` (repeat, optional),
    `--ac-project-dir`, `--refs-dir` (default `artifacts/refs`), `--spec-input` (repeat, optional),
    `--framework`, `--runner {vstest,mtp}`.
- **`init_scaffold.py [--target-framework TFM]`:**
  - It reads the config with `load_config`, re-evaluates the surface and unit test projects by
    importing `init_detect` (no file handed over), and takes the recipe from `init_config.RECIPES`.
  - It refuses a non-empty `acProjectDir`.
  - `render(...)` is pure and returns `{relpath: text}` from `templates/ac-project/*.template`
    (`{{NAME}}` placeholders):
    - the csproj: TFM, properties, usings, `FrameworkReference`s, the ref glob, the `ProjectReference`s;
    - `Directory.Build.props`: a conditional import of the root props via `GetPathOfFileAbove`, with
      `Condition` != '' so that it also works with no root props;
    - `reqnroll.json`;
    - the `.gitkeep` files.
  - `packages(...)` is pure and returns `[(id, version|None)]`. The order is: recipe packages, the
    Reqnroll adapter, `Microsoft.Extensions.TimeProvider.Testing`, then the surface packages that are
    neither implicit nor `PrivateAssets=all`.
  - Version rule:
    - with CPM: no version (F2);
    - otherwise, the surface's own version for its packages (with two different versions across the
      surface projects, the highest, plus a printed note), then the version used by the unit test
      projects (highest likewise), then none (latest stable). See deviation D3.
  - Then it runs `dotnet add <acProject> package <id> [--version V]` per package.
  - Then ilspycmd: `dotnet tool list --local` at the root (a non-zero exit, as with no manifest, means
    "not installed"); if ilspycmd is not listed, `dotnet tool install ilspycmd --create-manifest-if-needed`.
  - Then the `.gitignore` and `.gitattributes` blocks.
  - On any failure it deletes the AC folder it created, lists the other files changed so far, and
    exits 1. The command then tells the user to delete `.workflow/config.json` and review the listed
    files before running setup again (finding 10).
  - It hashes the root `Directory.Packages.props` and the tool manifests (`dotnet-tools.json`,
    `.config/dotnet-tools.json`) before the `dotnet` calls and compares them afterwards, so that they
    are listed too (review 2, finding 2).
  - It prints `created:` / `changed:` lines.
- **`init_verify.py`:**
  - A `Checks` collector prints `PASS|FAIL|SKIP <id> <text>` and a total; exit 1 on any FAIL. A failed
    build check ([1], the [5] ref build, the [5] normal rebuild) prints, indented under its FAIL line, the
    build output's `error`/`warning` lines with codes (`CSnnnn`, `RQnnnn`) and file paths (at most 40),
    which is the input for the command's step 6b (review 2, finding 1).
  - Temporary feature `specs/999-speckit-ac-check` (tag F999) with `spec.md` (FR-001), `acceptance.md`,
    `Samples/F999/sample.txt`, `Features/F999/check.feature` (Background, a bound scenario, a bound
    outline, an unbound scenario) and `StepDefinitions/F999/CheckSteps.cs`.
  - Results go to `.workflow/init-check/analyze/`.
  - Sub-scripts (`ac_lock.py`, `export_refs.py`, `check_features.py`, `summarize_trx.py`) run as
    `[sys.executable, "-I", <script>]`. `init_verify.py` itself already runs under the configured Python
    (finding 14).
  - The sequence:
    1. Refuse (exit 1, nothing deleted) if **any** temporary path exists: `specs/999-*`,
       `Features/F999`, `Samples/F999`, `StepDefinitions/F999`, `.workflow/init-check` (finding 15).
    2. **[1]** Build the solution, then the AC project in normal mode.
    3. Take the tree snapshot **after** these builds (`changed_files.tree_hashes`, refsDir entries
       dropped), so that restore side effects such as `packages.lock.json` are not reported as leftovers
       (finding 3). From here on, every step writes only to `bin*/obj*`, `refsDir` or the temporary paths.
       Then write the temporary files.
    4. **[3]** The lock round trip with `ac_lock.py` subprocesses:
       - sources: lock → verify 0; acceptance byte → 1; restore → 0; sample byte → 1; restore; extra
         sample file → 1; remove; `spec.md` byte → 3; restore; unlock;
       - features: lock → verify 0; feature byte → 1; restore; extra file → 1; remove; unlock.
    5. **[4]** `export_refs.py` exits 0. Every `refsDir/*.dll` contains `ReferenceAssemblyAttribute`,
       and `api/<stem>.cs` exists.
    6. **[5]** `acRefBuildCommand` (`shlex.split`, no shell) exits 0:
       - `bin-ref/` and `obj-ref/` exist;
       - no exported assembly file name is under `bin-ref/`;
       - `check.feature.cs` is under `obj-ref/`, and no `*.feature.cs` is under `Features/`;
       - `dotnet msbuild <acProject> -p:AcRefMode=true -getProperty:TreatWarningsAsErrors
         -getProperty:NoWarn -getProperty:WarningsNotAsErrors` (the AC project imports the root props).
         When TWAE is `true` and neither `NoWarn` nor `WarningsNotAsErrors` lists CS0168 (round 2
         finding 8): with a temporary `StepDefinitions/F999/AcInitCheckWarning.cs` (an unused
         local, CS0168; deviation D1), the ref build fails and names CS0168. The file is removed. Otherwise
         a SKIP line with the reason (finding 4, finding 7);
       - then the AC project is built again in normal mode, which must pass.
    7. **[6]** `check_features.py --feature 999`:
       - it passes on the valid file;
       - it fails on each of four variants: a mistyped keyword, no `When`, no `@AC-` tag, a duplicate
         id. The valid file is restored afterwards.
    8. **[7]** `dotnet sln <solution> list` does not contain the AC project. `acTestCommand` is filled
       with `{acProject}` and `{analyzeDir}` and run with `shlex.split`, after the normal build from
       step 6; it may exit non-zero. Then:
       - the TRX exists at `<analyzeDir>/ac-results.trx`;
       - `summarize_trx.py <trx> <md> --current F999` exits 0;
       - the md shows `| passed |` for AC-001, `| pending |` for AC-003, the tags `@F999 @AC-001`, and
         the unbound step's text.
    9. In the `finally` block: remove every temporary path, then, **only when a snapshot was taken**
       (round 2 finding 7), compare the tree hashes (refsDir excluded). Any difference is a FAIL listing the paths. The FAIL text names `packages.lock.json`
       and other build side effects as a possible cause.
  - It never writes into the product's projects (decision 6).
- **`smoke_test.py`:**
  - `ACTIONS[role]` is a list of `(label, tool, tool_input template, expected "allow"|"deny")`:
    - translator: Read the first surface csproj → deny; Write `<ac>/StepDefinitions/F999/Smoke.cs` →
      deny; Bash `ls` → deny; Read `specs/999-speckit-ac-smoke/spec.md` → allow; Bash
      `acRefBuildCommand` → allow;
    - writer: Read surface → deny; Bash `ls` → deny; Glob `**/*.cs` without a path → deny; Read spec →
      allow; Bash build → allow;
    - judge: Read surface → deny; Read spec → allow;
    - plus, for every role, `SubagentHandback` → allow.
  - `prompt(role, cfg)` renders the CT §6.8 text: "SMOKE TEST — do not do your normal task. Try each
    action once, report which were blocked, then hand back a short summary", followed by the numbered
    actions with concrete paths.
  - `start <role>`:
    - refuses when a marker or `specs/999-*` exists;
    - creates the feature and its run folder;
    - writes the marker with `aclib.write_marker(..., **extra)`, a new keyword parameter (finding 13),
      adding `taskMessage` = the prompt, `smoke: true` and `smokeLogLines` = the current `guard.log`
      line count;
    - prints the prompt.
  - `end <role>`:
    - reads the marker. If it is a smoke marker for that role, it evaluates. If it is missing, it skips
      the evaluation and reports that. If it is a non-smoke marker, it leaves it alone and prints a
      recovery hint (finding 13);
    - takes the new `guard.log` lines whose `agent_type` equals the role, and counts them per
      (tool, decision);
    - reports each expected entry as present or missing. **Unexpected** means an `allow` for a tool that
      has no expected allow for that role (for example `Write` for the translator, `Glob` for the
      writer, `Bash` for the judge). Extra allows of an expected tool, such as a second `Read` of the
      spec, are printed as information only, because the log carries no path (finding 5);
    - cleans up in a `finally`: a smoke marker or no marker is deleted, and `specs/999-speckit-ac-smoke`
      is always deleted;
    - exits 1 on a missing entry or an unexpected allow.
  - `isolation-file create|delete` writes or removes `<ac>/StepDefinitions/smoke-test.txt` and prints
    its path.
- **`templates/ac-project/`:** `AcceptanceTests.csproj.template`, `Directory.Build.props.template`,
  `reqnroll.json`.
- **`commands/speckit.ac.init.md`:**
  - frontmatter `description` ("… Started only by the user.") and `argument-hint: "[smoke]"`;
  - User input and Rules: fixed python in setup mode; stop at the first failure. The scripts write every
    file, and the **only** file you edit yourself is the AC csproj's `<NoWarn>` (R07, finding 1);
  - "Mode" picks setup, verify or smoke;
  - "## Steps (setup)" R02 1–7, with the question rules R04 and the one summary confirmation. An
    unsupported pair from `init_detect.py` (`supported: false`) stops and asks **before** the summary.
    Scaffold failure: tell the user to delete `.workflow/config.json` and review the listed files.
    **Step 6b (R07):** if `init_verify.py` FAILs a build with warnings-as-errors codes (`CSnnnn`,
    `RQnnnn`) reported for generated files under `obj*/` (`*.feature.cs`), add exactly those codes to
    `<NoWarn>` in `<acProject>` (`$(NoWarn);CSnnnn`), tell the user which codes and why, and run
    `init_verify.py` once more. Any other build failure: stop and report;
  - "## Steps (verify)", with the same step 6b;
  - "## Steps (smoke)": for each role, `smoke_test.py start <role>` → the `Agent` tool with
    `subagent_type`, `run_in_background: false`, prompt = the exact output → `smoke_test.py end <role>`;
    then the three manual checks:
    - (a) the main agent's `Read` of the `isolation-file` path is blocked;
    - (b) an `Explore` subagent asked to read it: either the guard denies the **launch** (its prompt
      names `<AcDir>/StepDefinitions/`), or the Explore subagent reports that its read was blocked.
      Showing the file's content is the failure (round 1 finding 6, round 2 finding 5);
    - (c) the user points the hook command in `.claude/settings.json` at a missing interpreter, any
      tool call is blocked, and the user restores it by hand (round 2 finding 4). The hook is named by
      its full path `.specify/extensions/ac/hooks/guard.py`, never a bare `hooks/` path;
  - the report and constitution offer text (R08);
  - a stop.

## Steps

0. **Fix** (R11): add `import json` to `export_refs.py`; read files in `check_no_internals_visible_to` with
   `errors="replace"` (review 2, finding 9).
1. **`aclib.py`** (R05, R10): `validate_config` split; `write_block` / `remove_block`; constants.
   `load_config` behaviour is unchanged (the existing tests guard it).
2. **`init_detect.py`** (R03, R04 inputs).
3. **`init_config.py`** with `RECIPES` (R05, R12). The table holds the 7 combinations that passed in F7.
4. **Templates and `init_scaffold.py`** (R06, R10).
5. **`init_verify.py`** (R07).
6. **`smoke_test.py`** (R09).
7. **Command `speckit.ac.init.md`**, and `speckit.ac.init` added to `extension.yml` as the first command
   (R01, R02, R04, R08).
8. **Tests, `tests/test_init.py`** (R13). A shared fixture builder writes minimal csproj, slnx,
   global.json and Directory.*.props files.
   - detect (`dotnet` needed; skipped without it):
     - frameworks by package ids (pure);
     - a fixture solution with a classlib, an exe, a test project recognised only by its packages (no
       `IsTestProject`, never restored) and a non-C# project entry → candidates, unit tests, framework,
       TFM, `ignored` (findings 2 and 11);
     - `supported` false for xunit2 + MTP (finding 12);
     - `InternalsVisibleTo` search on a Latin-1 file (finding 16);
     - runner;
     - CPM, with pinned versions read;
     - `InternalsVisibleTo` blocker;
     - a mixed frameworks fixture;
     - a non-empty `acProjectDir`;
     - environment problems through injected `which` / `system` and files (`init-options` missing or
       `sh`, timestamp folder, no `CLAUDE.md`, no git).
   - config: every `RECIPES` entry → `validate_config` passes, `acTestCommand` contains `{acProject}`,
     `{analyzeDir}` and `ac-results.trx`, the MTP/VSTest syntax is right; xunit2/MTP fails and names the
     supported combinations; an existing config, a spec input of `src/`, of a project folder, of a
     folder containing a csproj, a `..` path, and whitespace in a path all fail (finding 8).
   - scaffold `render` and `packages` (pure) per recipe: properties, usings, ref glob relative path,
     `ReqnrollUseIntermediateOutputPathForCodeBehind`, `Samples/**` copied to output, `DefaultItemExcludes`
     with both modes' folders, `reqnroll.json` `missingOrPendingStepsOutcome: Error` (review 2, finding 3),
     `ProjectReference`s, `FrameworkReference`s, the conditional root import; the version rules with
     and without CPM, two surface pins → the highest; implicit and `PrivateAssets=all` are skipped; a
     non-empty folder is refused; the tool-list parse treats a non-zero exit as "not installed".
   - blocks: insert into a missing file, into one with content (other bytes kept, CRLF file kept),
     replace on a second write (no duplicate), remove.
   - verify:
     - a pre-existing `specs/999-x`, and a pre-existing `Features/F999`, each give exit 1 and delete
       nothing (finding 15);
     - the snapshot is taken after the builds: a stubbed build that writes `packages.lock.json` into a
       product folder is not a leftover (finding 3);
     - the TWAE check runs or SKIPs from the evaluated properties, including `WarningsNotAsErrors`
       (stubbed msbuild JSON; finding 4, round 2 finding 8);
     - a stubbed failing build prints its `error CSnnnn` lines under the FAIL line (round 2 finding 1);
     - a failure at [1] writes no temporary path, skips the tree check and exits 1 (round 2 finding 7);
     - with `subprocess` stubbed to fail at the export step, every temporary path is gone afterwards and
       the tree-unchanged check runs. The script is imported as a module, `run` is monkeypatched, and a
       git-initialised temp project is used.
   - smoke:
     - start/end per role write and remove the marker and the feature;
     - the launch of the smoke prompt passes the real guard (`run_guard`, `Agent`);
     - a changed prompt is denied;
     - every `ACTIONS` entry run through the real guard with the smoke marker gives its expected
       decision;
     - `end` on a synthetic `guard.log` reports present, missing and unexpected entries and exits 1/0;
       an extra `Read allow` is information only, a `Write allow` for the translator is unexpected
       (finding 5); cleanup happens on failure too, with no marker, and leaves a non-smoke marker alone
       (finding 13);
     - `isolation-file` create and delete.
   - export_refs: `msbuild_json` with a stubbed `run` returns parsed JSON (R11).
9. **`tests/test_commands.py`** (R13, F11):
   - `NAMES` gains `"init"`, first, matching the manifest order;
   - the `init` special case is dropped;
   - `SUBCOMMANDS` gains `smoke_test.py` (`start`, `end`, `isolation-file`);
   - `test_init_rules`: three modes, the fixed python, the confirmation before `init_config.py`, the
     step order `init_detect` → `init_config` → `init_scaffold` → `init_verify`, smoke start → Agent →
     end per role, the constitution offer, a stop; the `NoWarn` step 6b and "the only file you edit
     yourself" rule (finding 1); `supported` stops before the summary (finding 12); the Explore launch
     denial or a blocked read both count as the pass (finding 6, round 2 finding 5); the three manual
     checks, including the missing interpreter (round 2 finding 4);
   - the real `specify` test checks five skills.
10. **Docs** (R14):
    - CONFIG.md: who writes the config, the command table per runner, the supported matrix, temporary
      files;
    - WORKFLOW.md: a §1 setup subsection (modes, smoke test, LF pins), and in §6 the CRLF-before-git
      limit;
    - the payload README rows;
    - DESIGN §9 (gitignore/gitattributes now from init) and a decision-log row.
11. **Run** `uv run pytest -q --tb=short` (also on CPython 3.11 as before).
12. **Real matrix** (R12, A1, A2): opt-in test `test_init_e2e` (`SPECKIT_AC_DOTNET_E2E=1`), parametrized
    over the 7 combinations plus xunit2/MTP (expects `init_config` to refuse it).
    - Per combination: `git init` a temp solution (classlib surface with one public class, a unit test
      project of the same recipe with real packages via `dotnet add`, `global.json` for MTP, a CPM
      variant for one combination); copy the payload; `CLAUDE.md`; `.specify/init-options.json` with
      script ps; run detect → config (flags from the proposal) → scaffold → verify; assert every line is
      PASS or SKIP.
    - Detection runs on the copy before any restore, and asserts `unitTestProjects` and the surface
      candidates (A2, finding 2).
    - Run in the background with the log in the scratchpad.
13. **Tracker** row 5, step 5 notes and open items; spec status.

## Test list (new or changed)

`tests/test_init.py` (new), `tests/test_commands.py` (`NAMES`, `SUBCOMMANDS`, init rules, five skills),
`tests/test_scripts.py` (layout list gets the new scripts and templates; `msbuild_json`).

## Deviations from the spec (recorded for the tracker and R08)

- **D1 (R07, item 5):** the warnings-as-errors check uses CS0168 (an unused local) instead of a nullable
  warning, because a nullable warning needs `<Nullable>enable</Nullable>`. The temporary file lives in
  `StepDefinitions/F999/`. The check runs only when the **evaluated** ref-mode `TreatWarningsAsErrors`
  is true.
- **D2 (R06):** `FrameworkReference`s of the surface are rendered into the csproj, not added with
  `dotnet add package`, because they are not packages. `init_scaffold.py` re-evaluates the projects
  instead of reading the detection JSON, so nothing is handed over through a file.
- **D3 (R06):** without CPM, the surface's own package version comes before the unit tests' version
  (the ref-mode compile must match the surface). With several versions, the highest wins and a note is
  printed.
- **D4 (R03):** a test project is any project with `IsTestProject` true **or** test framework packages.
  Only `*.csproj` projects of the solution are evaluated.

## Review dispositions

### Round 1 (`05-init.review-1.md`, REVISE)

1. BLOCKER, NoWarn step missing → **ACCEPTED**: command step 6b; rule "the only file you edit yourself
   is the AC csproj's `NoWarn`"; asserted in `test_init_rules`.
2. MAJOR, `IsTestProject` empty before restore → **ACCEPTED**: test project = `IsTestProject` or
   framework packages (D4, F13); fixture and e2e check on an unrestored copy.
3. MAJOR, snapshot before the builds → **ACCEPTED**: snapshot after sequence step 2; FAIL text names
   `packages.lock.json`; test with a stubbed build side effect.
4. MAJOR, TWAE from text → **ACCEPTED**: evaluated ref-mode `TreatWarningsAsErrors` / `NoWarn`, SKIP
   with reason; `root_props` for the report only.
5. MAJOR, smoke extra-allow rule → **ACCEPTED**: unexpected = an allow for a tool with no expected
   allow; extra counts are information.
6. MINOR, Explore launch is denied → **ACCEPTED**: a denied launch counts as the pass, explained in the
   command.
7. MINOR, A4 deviation and file location → **ACCEPTED**: D1; the file is under `StepDefinitions/F999/`.
8. MINOR, whitespace in paths → **ACCEPTED**: `init_config.py` rejects it.
9. MINOR, R06 deviations → **ACCEPTED**: D2, D3; with several versions the highest wins, with a note.
10. MINOR, scaffold failure leaves the config → **ACCEPTED**: the command tells the user to delete the
    config and review the files; a non-zero `tool list` exit means not installed.
11. MINOR, non-C# projects → **ACCEPTED**: only `*.csproj` is evaluated; the others go under `ignored`.
12. MINOR, unsupported pair found late → **ACCEPTED**: `supported` in the detection JSON; the command
    stops before the summary.
13. MINOR, smoke cleanup and `write_marker` → **ACCEPTED**: `end` handles a missing or foreign marker;
    `write_marker(**extra)`.
14. MINOR, sub-script interpreter → **ACCEPTED**: `[sys.executable, "-I", script]`.
15. MINOR, other leftover temporary paths → **ACCEPTED**: refuse when any temporary path exists.
16. MINOR, strict UTF-8 → **ACCEPTED**: `errors="replace"`.

### Round 2 (`05-init.review-2.md`, REVISE)

1. MAJOR, step 6b has no input → **ACCEPTED**: failed build checks print the build's error/warning lines
   with codes and paths under the FAIL line; exit 1 on any FAIL; test with a stubbed failing build.
2. MINOR, CPM and tool-manifest changes unreported → **ACCEPTED**: hashed before and after the dotnet
   calls, listed as created/changed.
3. MINOR, render assertions incomplete → **ACCEPTED**: added to step 8.
4. MINOR, the missing-interpreter check missing → **ACCEPTED**: all three manual checks in the command;
   full hook path; asserted in `test_init_rules`.
5. MINOR, Explore denial point → **ACCEPTED**: either a denied launch or a blocked read passes.
6. MINOR, whitespace on the solution → **ACCEPTED**: dropped for the solution, added for
   `unitTestProjects`.
7. MINOR, `finally` before a snapshot → **ACCEPTED**: the tree check runs only after a snapshot; a test
   for a failure at [1].
8. MINOR, `WarningsNotAsErrors` → **ACCEPTED**: read and honoured (SKIP).
9. MINOR, strict UTF-8 in `export_refs` → **ACCEPTED**: `errors="replace"` in Step 0.

New fact **F16** (probed during round 2): the Reqnroll 3.3.4 adapters' minimum dependency versions are low
(`xunit.v3.extensibility.core` ≥ 2.0.0, `xunit.core` ≥ 2.8.1, `NUnit` ≥ 3.13.1, `MSTest.TestFramework` ≥
2.2.8), so taking the unit tests' versions (A1) is unlikely to clash.

### Round 3 (`05-init.review-3.md`, REVISE, no BLOCKER → implement per the workflow)

1. MAJOR, timestamp numbering option → **ACCEPTED**: `init_detect.environment()` also reports
   `feature_numbering`/`branch_numbering` = `timestamp` (via `aclib._feature_numbering`); env test case.
2. MINOR, implementation folders late → **ACCEPTED**: `init_detect.py` prints `implementationFolders`
   (the function lives in `init_detect`, `init_config` imports it); the command re-asks; `init_config.py`
   remains the hard gate.
3. MINOR, stale marker in smoke start → **ACCEPTED**: the refusal names the marker, why it can be left
   over, and tells the user to delete it by hand.
4. MINOR, missing TRX without cause → **ACCEPTED**: the test command's last 40 lines under the FAIL.
5. MINOR, netstandard-only TFM → **ACCEPTED**: `propose` gives `targetFramework: null` + reason; the
   command always passes `--target-framework` with the confirmed value (the flag becomes required);
   netstandard-only fixture.
6. MINOR, tool restore → **ACCEPTED**: `init_verify.py` runs `dotnet tool restore` at the root before [4].
