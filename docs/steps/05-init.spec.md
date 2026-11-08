# Step 5 — `/speckit-ac-init`

**Status:** done (2026-11-08; decisions 1–10 approved as drafted; deviations D1–D4 recorded in the plan) · **Tracker row:** 5 · **Source of truth:** `docs/DESIGN.md`

## Goal

A user who has installed the extension types `/speckit-ac-init` once per project. It detects what
it can, asks the rest, writes `.workflow/config.json`, scaffolds the AC test project (Reqnroll plus
the detected test framework and runner), and runs the automatable checks from CT doc §6 (items 1
and 3–7). It ends with instructions for the live smoke test (§6 item 8), which the user runs in a
new session with `/speckit-ac-init smoke`. Out of scope: deploy (agents, guard registration,
`CLAUDE.md` blocks, step 6) and running the smoke test live (step 7).

## Context

- Sources (read only): CT doc §3–§7 (`docs/reference/WORKFLOW-SETUP-CT.md`) and CT's AC project
  `<original project>\tests\CT.AcceptanceTests\` (csproj, `Directory.Build.props`, `reqnroll.json`).
- DESIGN §2: the only things we may assume are spec-kit, `CLAUDE.md` and a .NET solution. Everything
  else is detected or asked once. The v1.0 environment is fixed: Windows, uv, pwsh, spec-kit
  `--script ps`, Python command `uv run --no-project python -I`.
- DESIGN §4: init offers a testability section through `/speckit-constitution` and never edits the
  constitution itself.
- Open items left for step 5 in the tracker:
  - init writes config schema 1, including `testFramework`;
  - spec inputs must not include implementation folders;
  - `acTestCommand` must write `{analyzeDir}/ac-results.trx` (the logger option depends on the runner);
  - add `speckit.ac.init` to `extension.yml` and to `NAMES` in `test_commands.py`;
  - the `.gitignore` entry for `refsDir`.
- **Found while drafting:** `payload/scripts/export_refs.py` calls `json.loads` (lines 38–39) but never
  imports `json`. Its dotnet path has never run (the step 2 tests cover only the pure functions), so
  the first real run would crash. §6 item 4 runs this path, so step 5 fixes it.
- **Consequence of step 4 for the smoke test:** the guard now lets the main agent start an AC subagent
  only with the `taskMessage` stored in the active-run marker, and blocks every AC-role call that has
  no matching marker. CT's smoke test (start each subagent directly with a "SMOKE TEST" prompt) is
  therefore always denied. The smoke test needs its own marker.
- The guard and the lock:
  - The guard logs only `agent_type`, tool and decision to `.workflow/guard.log`, with no path or time.
  - `ac_lock.py` hashes the raw bytes on disk, so line endings decide whether a lock verifies in
    another checkout.
- Checked on 2026-11-08:
  - Tools: dotnet SDK 10.0.403, uv 0.11.26, specify 1.0.2, pwsh 7.6.9.
  - NuGet is reachable and has `Reqnroll.xunit.v3`, `Reqnroll.xUnit`, `Reqnroll.NUnit` and
    `Reqnroll.MSTest`, all at 3.3.4.
  - CT runs xUnit v3 on Microsoft.Testing.Platform with Reqnroll 3.3.4 (CT doc §10), with central
    package management and `TreatWarningsAsErrors`.

## Requirements

### Command

- **S05-R01** `payload/commands/speckit.ac.init.md` (`/speckit-ac-init [smoke]`):
  - It follows the shared rules of the step 4 commands (S04-R03): numbered steps, stop at the first
    failure, no paths that spec-kit would rewrite, ends with a stop.
  - The scripts run as `uv run --no-project python -I .specify/extensions/ac/scripts/<name>.py`,
    because there is no config yet.
  - `extension.yml` provides `speckit.ac.init`. `test_commands.py` `NAMES` includes it.
  - It picks its mode from the project's state:
    - **setup**: no `.workflow/config.json` (R02–R08);
    - **verify**: the config exists. It shows the config and runs `init_verify.py` (R07) only. To
      change the configuration, the user edits the config by hand and runs `/speckit-ac-init` again;
    - **smoke**: argument `smoke` (R09).
- **S05-R02** Setup flow. Each step stops on failure.
  1. `init_detect.py` (R03).
  2. Ask the user only what detection could not settle (R04).
  3. Show one summary of every value about to be written, including detected values and defaults,
     and wait for an explicit confirmation.
  4. `init_config.py` (R05).
  5. `init_scaffold.py` (R06).
  6. `init_verify.py` (R07).
  7. Report (R08).

### Detection

- **S05-R03** New script `init_detect.py`. It prints JSON and makes no change.
  - **Environment (v1.0):**
    - The OS is Windows, and `uv`, `pwsh` and `dotnet` are available.
    - `.specify/init-options.json` has `"script": "ps"`.
    - Feature numbering is sequential: no timestamp feature folders.
    - `CLAUDE.md` exists, and the project is a git repository.
    - Any failure is reported, and the command stops.
  - **Solution:** the `.sln` / `.slnx` files at the root. With several, the user is asked to pick
    one.
  - **Projects in the solution:**
    - For each project: its path, `TargetFramework(s)`, `OutputType`, `IsTestProject`, and its test
      framework, found from package names (xUnit v2, xUnit v3, NUnit, MSTest).
    - Its `PackageReference` and `FrameworkReference` items, with `PrivateAssets` and versions.
    - Whether its source, csproj or props files use `InternalsVisibleTo`.
    - Values are read with `dotnet msbuild -getProperty` / `-getItem`, so root props and central
      package management are taken into account.
  - **Runner:** Microsoft.Testing.Platform when `global.json` has `"test": {"runner":
    "Microsoft.Testing.Platform"}`, otherwise VSTest.
  - **Central package management:** whether it is on (`Directory.Packages.props` with
    `ManagePackageVersionsCentrally`).
  - **Root `Directory.Build.props`:** whether it exists, and its `TreatWarningsAsErrors` value.
  - **Proposals:**
    - AC-surface candidates: the non-test projects that are not executables.
    - `unitTestProjects`: the test projects.
    - `testFramework`: the framework the test projects share. A mix of frameworks, or none, means
      the user is asked.
    - `acProjectDir`: `tests/<SolutionName>.AcceptanceTests`. If `tests/` does not exist, the folder
      goes next to the test projects.
    - `refsDir`: `artifacts/refs`.
    - The AC project's target framework: the unit test projects' TFM when they agree, otherwise the
      highest `netX.Y` of the surface projects. A surface that has only `netstandard` TFMs means the
      user is asked.
  - **Blockers:** these are reported so that the command stops or asks:
    - `acProjectDir` exists and is not empty;
    - `.workflow/config.json` exists (that case is verify mode);
    - a proposed surface project uses `InternalsVisibleTo`;
    - the solution does not build. This is checked later, in R07 item 1, not by detection.
- **S05-R04** Questions. Each one is asked only when it applies:
  - **AC surface projects:** asked when there is more than one candidate. A single candidate is
    proposed in the summary.
  - **Test framework:** asked when there is none or a mix. The default is `xunit3`.
  - **Extra spec inputs:** always asked, and the default is none. The command explains that the AC
    subagents will read them. The command refuses implementation folders and tells the user why: a
    folder that contains a `.csproj` file, `src/`, or the folder of any project in the solution. The
    config check (S02) already rejects overlaps with `specs/`, `.specify/`, `.workflow/`, the AC
    project and `refsDir`.
  - **`InternalsVisibleTo` in a surface project:** stop and ask. The options are to remove it (the
    user's change) or to leave that project out of the surface.
  - **A runner/framework combination that R05 does not support:** stop and ask.

### Config

- **S05-R05** New script `init_config.py`. Its flags carry every answer.
  - It builds config schema 1 (`docs/CONFIG.md`) with `python` = `uv run --no-project python -I`.
  - It builds the commands from (`testFramework`, runner) using one fixed table in the script:
    - `acRefBuildCommand`: `dotnet build <acProject> -p:AcRefMode=true -nologo -v q`.
    - `unitTestCommand` and `acTestCommand` in that runner's syntax.
    - `acTestCommand` writes the TRX to `{analyzeDir}/ac-results.trx` with that runner's (and, for
      Microsoft.Testing.Platform, that framework's) report option.
    - The table holds only combinations verified in this step (R12). Any other combination fails
      with a message that names the supported ones.
  - It validates the result with the same rules as `aclib.load_config` and refuses to overwrite an
    existing config. It writes `.workflow/config.json` and prints it.

### Scaffold

- **S05-R06** New script `init_scaffold.py`. It reads the config and the detection JSON, and writes
  only inside `acProjectDir`, plus the files named below. It never adds the AC project to the
  solution file.
  - **`<acProjectDir>/<Name>.csproj`**, rendered from `payload/templates/ac-project/`. It has:
    - an explicit `TargetFramework` (R03);
    - the framework/runner properties from the R05 table, such as `OutputType` and runner switches;
    - `ReqnrollUseIntermediateOutputPathForCodeBehind`;
    - global usings for `Reqnroll` and the framework's assertion namespace;
    - `Samples/**` copied to the output folder;
    - **ref mode** (`AcRefMode == true`): `<Reference Include="<refs>/*.dll" Private="false" />`,
      one glob over `refsDir`. This means no per-assembly entries, and new project-to-project
      dependencies need no csproj change;
    - **normal mode**: a `ProjectReference` for each surface project.
  - **`<acProjectDir>/Directory.Build.props`**, as in CT:
    - it imports the root props when they exist;
    - in ref mode it sets `obj-ref\` / `bin-ref\`;
    - `DefaultItemExcludes` covers both modes' output folders.
  - **`reqnroll.json`** with `missingOrPendingStepsOutcome: Error`.
  - **Folders**, each with a `.gitkeep`: `Features/`, `Samples/`, `StepDefinitions/`,
    `Support/Shared/`.
  - **Packages**, added with `dotnet add package`, which adds central `PackageVersion` entries when
    central package management is on. The list is:
    - the framework/runner packages from the R05 table;
    - the Reqnroll adapter;
    - `Microsoft.Extensions.TimeProvider.Testing`;
    - every `PackageReference` and `FrameworkReference` of the surface projects that is not
      `PrivateAssets=all`, so that public types from NuGet compile in ref mode.

    Version policy: a version already pinned centrally is kept. Without central package management,
    a package the unit test projects already reference gets their version. Anything else gets the
    latest stable version.
  - **Local tool `ilspycmd`:** installed with `dotnet tool install ilspycmd` into the existing tool
    manifest. If there is none, a manifest is created.
  - **`.gitignore`**, as a marked block (R10): `<refsDir>/`, `**/bin-ref/`, `**/obj-ref/`,
    `.workflow/guard.log`, `.workflow/active-run.json`.
  - **`.gitattributes`**, as a marked block:
    - `<acProjectDir>/Samples/** binary`;
    - `<acProjectDir>/Features/**/*.feature text eol=lf`;
    - `specs/*/acceptance.md text eol=lf`;
    - `specs/*/spec.md text eol=lf`.

    All of these are hashed by the locks.
  - It prints every file it created or changed.

### Verification

- **S05-R07** New script `init_verify.py`. It covers CT doc §6 items 1 and 3–7 and prints one line
  per check with PASS or FAIL, plus a total; it exits 1 on any FAIL.
  - Temporary files are only:
    - a temporary feature `specs/999-speckit-ac-check/` (it fails if `specs/999-*` exists);
    - its files in the AC project (`Features/F999/`, `Samples/F999/`, `StepDefinitions/F999/`);
    - a results folder under `.workflow/`.

    It never writes into the product's projects. Everything is removed in a `finally` block. A last
    check compares content hashes of the working tree before and after, skipping `bin*/`, `obj*/`
    and `refsDir`, and fails on any leftover.
  - The items:
    1. `dotnet build <solution>` and `dotnet build <acProject>` succeed.
    2. Item 3: `ac_lock.py` round trip on the temporary feature, for both groups:
       - `lock` → `verify` passes;
       - one byte changed in `acceptance.md`, a sample and a `.feature` file, and a file added: each
         makes `verify` fail;
       - restore → `unlock`.
    3. Item 4: `export_refs.py` succeeds on the current surface. Every copied dll is a reference
       assembly, and the listings exist.
    4. Item 5: the ref-mode build (`acRefBuildCommand`) succeeds:
       - its output is under `bin-ref/` / `obj-ref/`;
       - `bin-ref/` holds no copy of a surface assembly;
       - when the root props set `TreatWarningsAsErrors`, a temporary file with a deliberate nullable
         warning fails the ref-mode build (so the root props apply);
       - the normal-mode build still succeeds afterwards.
    5. Item 6: `check_features.py` passes on a valid temporary feature (scenario, outline,
       background) and fails on a mistyped keyword, a missing `When`, a missing `@AC-` tag and a
       duplicate id. The code-behind is under `obj-ref/`, not in `Features/`.
    6. Item 7:
       - The AC project is not in the solution (`dotnet sln list`).
       - With a temporary feature that has one bound scenario and one unbound scenario,
         `acTestCommand` writes `<analyzeDir>/ac-results.trx`. The bound scenario passes and the
         unbound one fails.
       - `summarize_trx.py` shows the step trace, the tags and the pending outcome.
  - If the generated code breaks a warnings-as-errors build, the command (not the script) adds only
    those warning codes to `NoWarn` in the AC csproj, tells the user, and runs `init_verify.py` again.

### Report, constitution and smoke test

- **S05-R08** The setup report lists:
  - the config values;
  - the files created or changed;
  - the verification lines;
  - any deviation, with its reason.

  It then:
  - **Offers a testability section** for the constitution, as text to pass to
    `/speckit-constitution` (time from `TimeProvider`, external effects behind public interfaces,
    observable errors, a public way to build the system with test doubles, no `InternalsVisibleTo`
    in surface projects). It never edits the constitution.
  - **Says what to do next:** start a new session in this folder, because agents and hooks load at
    session start and workspace trust is per folder. In it, run `/speckit-ac-init smoke`, and repeat
    that in every new checkout or worktree. Then stop.
- **S05-R09** New script `smoke_test.py` and the `smoke` mode, for CT doc §6 item 8 adapted to the
  marker.
  - `smoke_test.py start <role>`:
    - creates a temporary feature `specs/999-speckit-ac-smoke/` with a placeholder `spec.md`, and the
      run folder (`translate-001`, `run-001`, or `run-001/analyze-1`);
    - writes the marker with that role and `taskMessage` = the fixed smoke prompt for that role,
      which follows CT §6.8 (translator, writer and judge lists);
    - records the current number of lines in `guard.log`;
    - prints the prompt.
  - The command then starts the subagent with exactly that prompt, in the foreground.
  - `smoke_test.py end <role>`:
    - compares the `guard.log` lines added since `start` with the expected (tool, decision) entries
      for the role, which must include `SubagentHandback allow`;
    - prints each entry as present or missing, plus any unexpected `allow`;
    - deletes the marker and the temporary feature, always;
    - exits 1 on a missing entry or an unexpected allow.
  - The smoke mode runs this for the three roles. It then lists the manual checks for the user:
    - the main agent's `Read` of a temporary file in `StepDefinitions/` is blocked (`smoke_test.py`
      creates it and deletes it);
    - an `Explore` subagent's read of it is blocked;
    - a missing interpreter in the hook command blocks every call, and the user restores it by hand.

    It reports and stops. A failed check means: stop and tell the user (folder not trusted, wrong
    Python command, hook not registered).
- **S05-R10** Marked blocks in `.gitignore` / `.gitattributes`:
  - Each block sits between `# >>> speckit-ac (managed; do not edit)` and `# <<< speckit-ac`.
  - Writing a block again replaces it in place, so a re-run creates no duplicates.
  - The rest of the file is never touched.
  - The helper lives in `aclib.py`, and step 6's uninstall reuses it to remove the blocks.

### Fix, docs and tests

- **S05-R11** `export_refs.py` gets the missing `import json`. A test imports the module and runs
  `msbuild_json` against a stubbed `run`.
- **S05-R12** Framework × runner matrix: xunit2, xunit3, nunit and mstest, each on VSTest and on
  Microsoft.Testing.Platform.
  - During implementation, each combination is run for real in the scratchpad: a minimal solution
    with one surface library, plus that framework's unit test project, then `init_detect` →
    `init_config` → `init_scaffold` → `init_verify`. These runs need network access to NuGet.
  - The R05 table keeps only the combinations that pass all checks. Each one that fails is recorded
    with its reason in the tracker and refused by `init_config.py` with a clear message.
  - This end-to-end test lives in pytest behind an opt-in environment variable
    (`SPECKIT_AC_DOTNET_E2E=1`). It is skipped by default.
- **S05-R13** Tests (pytest, no new dependency). Tests that need `dotnet` are skipped when it is
  missing.
  - `init_detect.py` on small fixture solutions:
    - framework detection per framework;
    - mixed frameworks or none;
    - runner from `global.json`;
    - central package management;
    - `InternalsVisibleTo`;
    - surface candidates;
    - TFM choice;
    - a non-empty `acProjectDir`;
    - environment failures, simulated: no `init-options.json`, script `sh`, timestamp folders, no
      git.
  - `init_config.py`:
    - each supported combination gives commands that `aclib.load_config` accepts, and an
      `acTestCommand` naming `{analyzeDir}` and `ac-results.trx`;
    - an unsupported combination, an existing config, a spec input that is an implementation folder
      and invalid paths all fail.
  - `init_scaffold.py`:
    - the rendered csproj and props for each supported combination (packages, properties, ref glob,
      `ProjectReference`s);
    - the folders and `.gitkeep` files;
    - marked blocks: insert, replace on re-run, the rest of the file unchanged, and removal.
  - `init_verify.py`:
    - the clean-up and the tree-unchanged check run on a stubbed failure halfway;
    - a pre-existing `specs/999-*` folder fails.
  - `smoke_test.py`:
    - the marker and the task message are written per role;
    - the launch of each smoke prompt passes the real guard, and any other prompt is denied;
    - each expected denial and allowance in the role's list matches the real guard's decision. This
      runs the guard in process with the smoke marker, and checks the guard's decisions, not a
      model's;
    - `end` evaluates a synthetic `guard.log` and always cleans up.
  - The command text: `test_commands.py` rules (scripts, flags, no rewritten paths), the three
    modes, and the summary confirmation before any write.
  - The real `specify` test (step 4) now expects five skills.
- **S05-R14** Docs:
  - `docs/CONFIG.md`: written by `init_config.py`, the command table per runner, and the new
    runtime/temporary files.
  - `docs/WORKFLOW.md`: a setup section (init modes, smoke test, LF pinning), and in known limits
    that a CRLF file locked before it reaches git does not verify in an LF checkout.
  - The payload README rows: init, the scripts, `templates/ac-project/`.
  - A DESIGN decision-log row, and a change to DESIGN §9: `.gitignore` and `.gitattributes` move from
    deploy to init.
- **S05-R15** `uv run pytest -q --tb=short` passes, the R12 runs are recorded, and tracker row 5 is
  updated. No commit unless the user asks.

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S05-A01 | `speckit.ac.init` is in `extension.yml`; the command text tests pass; the real `specify` test renders five skills | R01, R02 |
| S05-A02 | The `init_detect.py` tests pass | R03, R04 |
| S05-A03 | The `init_config.py` tests pass for every supported combination | R05 |
| S05-A04 | The `init_scaffold.py` tests and the marked-block tests pass | R06, R10 |
| S05-A05 | The `init_verify.py` clean-up and leftover tests pass | R07 |
| S05-A06 | The `smoke_test.py` tests pass against the real guard | R09 |
| S05-A07 | Every combination in the R05 table passed a real run in the scratchpad (opt-in test); each excluded one is recorded with its reason | R05–R07, R12 |
| S05-A08 | The `export_refs.py` import test passes, and the real runs reach the export step | R11 |
| S05-A09 | `uv run pytest -q --tb=short` passes (count reported) | R15 |

## Out of scope

- Deploy: agents, guard registration, `CLAUDE.md` blocks, patching the skills. `doctor` re-checks
  (step 6).
- A live run of `/speckit-ac-init` with a model, and a live smoke test (steps 7–8).
- Other OSes, `sh` scripts, Python on PATH (deferred, DESIGN §2).
- Reconfiguring an existing config through questions (a manual edit, then verify mode).
- Editing the constitution (only the offer to run `/speckit-constitution`).
- Normalising line endings inside `ac_lock.py` (a known limit; see R14).

## Decisions taken in this spec (confirm on approval)

1. **Init is a command plus deterministic scripts** (`init_detect`, `init_config`, `init_scaffold`,
   `init_verify`, `smoke_test`). The model only asks questions and reports, and every file is written
   by a script. There is one summary confirmation before anything is written (R02).
2. **Init writes the `.gitignore` and `.gitattributes` entries** as marked blocks, not deploy, because
   they depend on `acProjectDir` and `refsDir`, which exist only after init. **This changes DESIGN §9,**
   which assigned them to the deploy step. Step 6's uninstall removes the blocks with the same helper
   (R06, R10).
3. **LF is pinned for every file a lock hashes**, `spec.md` and `acceptance.md` included, not only the
   `.feature` files. Samples are marked `binary` (R06).
4. **Ref mode references `<refsDir>/*.dll` by one glob**, so `export_refs.py` can add assemblies
   without any csproj change. The writer cannot edit the csproj anyway (R06).
5. **Packages:** a fixed recipe per framework/runner, plus the surface projects' public NuGet and
   framework references. Versions come from central pins, then the unit tests' versions, then the
   latest stable (R06).
6. **Verification never writes into product projects.** CT §6 items 4 and 5 put a temporary class into
   the surface project. That is dropped, because the logic and internals checks of the listing are
   covered by pytest (step 2). The checks here are an `export_refs` run on the real surface, the
   ref-mode build checks, and a tree-unchanged check at the end (R07).
7. **Re-running `/speckit-ac-init` with a config only verifies.** There is no reconfiguration dialogue
   (R01).
8. **The smoke test gets its own marker** (`smoke_test.py`, `/speckit-ac-init smoke`), because the step
   4 launch rule denies CT's direct smoke prompts. It is built and tested against the real guard here,
   and run live in step 7 (R09).
9. **Only verified framework × runner combinations are supported.** Each is checked by a real
   scaffold-and-verify run during this step. Unsupported combinations stop with a clear message. The
   end-to-end test is opt-in, because it needs dotnet and NuGet and takes minutes (R12).
10. **`.workflow/active-run.json` is git-ignored**, since it is transient. The `runs/` history stays in
    git (R06).
