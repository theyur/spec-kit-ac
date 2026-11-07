# WORKFLOW-SETUP.md

> **For Claude Code.** Read this whole file first, then set up the workflow it describes in this repository.
>
> This is an **experiment**, not a production pipeline. Prefer simple, readable solutions over clever ones.
> The experiment ended 2026-11-05; the pipeline is kept as the original project’s acceptance-test workflow.
>
> If something here doesn't match your current Claude Code version or the repository, **stop and ask the user**. Don't silently change the design.
> Sections 0–9 are generic and meant to be reused in other .NET solutions. Section 10 recorded the choices for the original project and is not part of this copy.

---

## 0. What we are testing

The question: **can acceptance tests (AC tests) be written from the spec alone, without the test writer ever seeing the implementation?**

- Acceptance criteria are written by a developer **for humans**, in a Gherkin-like syntax in `.md` files, and reviewed by a lead in a PR. They are then **locked**, together with any golden sample files they use.
- A subagent (`ac-feature-translator`) turns each reviewed item into valid Gherkin in Reqnroll `.feature` files. The `.md` is not guaranteed to be valid Gherkin, complete or consistent, so the translator never guesses: it reports every item it can't translate faithfully, with a suggested fix for the `.md`. The user decides per item (skip it, or go back and fix the `.md`), or stops the whole translation. This happens **before implementation**, so AC problems surface before any code exists.
- The implementation is written normally, with its own unit tests.
- A separate subagent (`ac-test-writer`) binds the `.feature` files to Reqnroll step definitions. It sees **only** the spec inputs, the AC, the golden samples, and the **public API** taken from reference assemblies. It never sees source code or unit tests, and it never runs tests.
- The main agent runs the AC tests. If tests fail, another subagent (`ac-test-fail-judge`), which also never sees the implementation, decides whether each failure is the fault of the implementation, the test, or the translation.
- AC tests target the **core library API** (the "AC surface"), not hosts such as a CLI, web API or UI. Hosts are thin wrappers and stay out of scope.

Isolation is enforced **technically** (tool lists, one guard hook, separate folders, scripts), not only by instructions.

---

## 1. The flow

The user drives the flow. **After every step the main agent stops, reports, and waits.** It never starts the next step on its own.

| # | Step | Started by | Done by | Main output |
|---|------|-----------|---------|-------------|
| 1 | Write SPEC | user, in chat | main agent + user | `docs/SPEC.md` |
| 2 | Write AC (Gherkin-like `.md`) + golden samples, lead review, lock `sources` | developer / user | developer, lead (main agent helps on request) | `<acSources>/*.md`, `Samples/**`, `.workflow/sources.lock` |
| 3 | Translate AC to `.feature`, resolve issues, lock `features` | `/ac-translate` | `ac-feature-translator` subagent, then the user | `Features/*.feature`, `translation-report.md`, `.workflow/features.lock` |
| 4 | Implementation + unit tests | user, in chat | main agent | `src/**`, unit tests (green) |
| 5 | Write AC tests | `/ac-tests-write` | `ac-test-writer` subagent | step definitions, `writer-report.md` |
| 6 | Run AC tests and analyze | `/ac-tests-analyze` | main agent, plus `ac-test-fail-judge` if anything fails | `ac-results.md`, `judge-report.md` |

Translation issues (step 3): for each item the user chooses **skip** (no scenario, the item stays untested and is recorded) or **fix**, or a **full stop**. A fix always goes back to the `.md`: the developer edits it, the lead reviews, the user unlocks and re-locks `sources`, and `/ac-translate` runs again. The translator never applies fixes itself.

After step 6, the user decides what's next: fix the implementation (then `/ac-tests-analyze` again), rewrite the tests with the judge's feedback (`/ac-tests-write` again), re-translate (unlock `features`, `/ac-translate`), or fix the spec or the AC (review, unlock, edit, re-lock).

---

## 2. Isolation rules (the core of the experiment)

### 2.1 Who can see what

"Main agent" in this table also means **every other subagent type** (Explore, general-purpose, Plan, …). Only the three AC roles get their own rules. Otherwise the main agent could ask another subagent to read the step definitions for it.

| Artifact | Main agent | ac-feature-translator | ac-test-writer | ac-test-fail-judge |
|---|---|---|---|---|
| `specInputs` (SPEC and other spec documents/data, section 4) | read/write (step 1) | read | read | read |
| `<acSources>/*.md` (reviewed AC), `Samples/**` | read/write until `sources` locked, then read | read | read | read |
| `Features/*.feature` | read only (hook) | read/write until `features` locked | read | read |
| AC project files (`*.csproj`, `reqnroll.json`, `Directory.Build.props`) | read/write | no | read | read |
| AC `StepDefinitions/**`, `Support/**` | **no** (hook) | **no** | read/write | read |
| `src/**` (implementation) | read/write | **no** | **no** | **no** |
| Unit test project(s) | read/write | **no** | **no** | **no** |
| `artifacts/refs/**` (ref dlls + API listings) | read | no | read | read |
| `runs/translate-*/translation-report.md` | read | read/write | no | no |
| `runs/run-*/input-feedback.md` | read | no | read | no |
| `runs/run-*/writer-report.md` | read | no | read/write | read |
| `runs/run-*/analyze-*/ac-results.trx` (raw) | read | **no** | **no** | **no** |
| `runs/run-*/analyze-*/ac-results.md` (cleaned) | read | **no** | **no** | read |
| `runs/run-*/analyze-*/judge-report.md` | read | no | no | write |
| Everything else in the repo | read/write | **no** | **no** | **no** |
| Bash | yes | **only one exact command**: the ref-mode build of the AC project | same | **none** |
| Web, MCP, Skill, Agent tools | as usual | **none** | **none** | **none** |

(`runs/` means `.workflow/runs/`.)

### 2.2 Principles

1. **Default deny for the AC roles.** The guard allows only what is listed above. Unknown tools (including MCP tools) and unknown paths are denied.
2. **The main agent never writes anything a subagent reads, except the spec inputs, the AC `.md` files and golden samples (before they are locked), and project files.** All other files subagents read are produced by **deterministic scripts** or by another AC subagent: the API listings, the cleaned test results, the writer feedback, the `.feature` files. Reason: the main agent knows the implementation and could leak details by accident. (The *content* of the writer feedback is written by the judge, who has seen test output. See section 8.)
3. **Subagent prompts are fixed templates.** The skills invoke subagents with an exact prompt that contains only a run id and file paths. The main agent must not add explanations, hints, opinions or context. User decisions after a translation are recorded by a script that accepts only AC ids (`record_skips.py`), never free text.
4. **Subagents don't load `CLAUDE.md`** (`omitClaudeMd: true`, Claude Code 2.1.271+), because the main agent's `CLAUDE.md` may describe the implementation. Consequence: every domain rule the tests depend on must be in the SPEC, not only in `CLAUDE.md`.
5. **The test writer never sees test execution results.** It gets only the judge's feedback section, which must not contain values observed from the implementation.
6. **Expected values are literals.** Every expected value comes from the AC text or a golden sample file. Tests must not compute expected values from spec data at run time (for example by parsing a lookup table from the spec inputs). If they did, a misreading shared with the implementation would pass both.
7. **Translation changes form, never meaning.** The translator only normalizes syntax. Anything that would change, add or choose a meaning is reported as an issue, and fixes always go back to the reviewed `.md`.
8. **Hooks fail closed.** Inside the guard, any error exits with code **2** (block); in Claude Code, other non-zero exit codes do *not* block. If the guard **cannot be launched** (interpreter missing, timeout), the default is also non-blocking, so the hook entry sets `"onFailure": "block"` (Claude Code 2.1.295+).

---

## 3. Repository layout

Adapt names to the existing scaffold. Record the real paths in `.workflow/config.json` (section 4).

```
docs/
  SPEC.md
  acceptance/                     # Gherkin-like AC (.md), reviewed by a lead — locked (`sources`)
src/
  <App>.Core/                     # "AC surface": public API the AC tests use (could be more than one project)
  ...                             # hosts (CLI, web, UI): not tested by this workflow
tests/
  <App>.UnitTests/
  <App>.AcceptanceTests/          # Reqnroll project. NOT in the main solution file (section 5.1)
    Features/                     # *.feature — written ONLY by ac-feature-translator, then locked (`features`)
    Samples/                      # golden input/output files — locked (`sources`), binary in git
    StepDefinitions/              # written ONLY by ac-test-writer
    Support/                      # written ONLY by ac-test-writer (context classes, fakes, hooks)
    reqnroll.json
    Directory.Build.props         # imports the root props; separate output folders for ref mode
    <App>.AcceptanceTests.csproj
artifacts/
  refs/                           # generated: ref dlls + api/*.cs listings (git-ignored)
.workflow/
  config.json
  sources.lock
  features.lock
  experiment-log.md
  guard.log                       # guard decisions for subagent tool calls (git-ignored)
  runs/
    translate-001/
      translation-report.md
      skipped.json                # AC ids the user chose to skip (made by script)
    run-001/
      input-feedback.md           # optional, made by script from the previous judge report
      writer-report.md
      analyze-1/
        ac-results.trx
        ac-results.md
        judge-report.md
        writer-feedback.md        # made by script from judge-report.md
.claude/
  agents/ac-feature-translator.md
  agents/ac-test-writer.md
  agents/ac-test-fail-judge.md
  skills/ac-translate/SKILL.md
  skills/ac-tests-write/SKILL.md
  skills/ac-tests-analyze/SKILL.md
  hooks/guard.py
  hooks/test_guard.py
  scripts/*.py
  settings.json
dotnet-tools.json                 # local tool manifest (ilspycmd)
```

---

## 4. `.workflow/config.json`

One place for paths and commands, so scripts and the guard stay generic. Example:

```json
{
  "python": "python3",
  "solution": "MyApp.slnx",
  "specInputs": ["docs/SPEC.md"],
  "specFile": "docs/SPEC.md",
  "acSources": "docs/acceptance",
  "acSurfaceProjects": ["src/MyApp.Core/MyApp.Core.csproj"],
  "unitTestProjects": ["tests/MyApp.UnitTests/MyApp.UnitTests.csproj"],
  "acProjectDir": "tests/MyApp.AcceptanceTests",
  "acProject": "tests/MyApp.AcceptanceTests/MyApp.AcceptanceTests.csproj",
  "lockedPaths": {
    "sources": ["docs/acceptance", "tests/MyApp.AcceptanceTests/Samples"],
    "features": ["tests/MyApp.AcceptanceTests/Features"]
  },
  "refsDir": "artifacts/refs",
  "acRefBuildCommand": "dotnet build tests/MyApp.AcceptanceTests/MyApp.AcceptanceTests.csproj -p:AcRefMode=true -nologo -v q",
  "unitTestCommand": "dotnet test --project {project}",
  "acTestCommand": "dotnet test --project {acProject} --no-build --results-directory {analyzeDir} <trx options>"
}
```

- `specInputs`: files and folders the AC roles may read as specification. `specFile` is the main SPEC and must be one of them.
- `acSources`: the folder with the reviewed Gherkin-like AC. Readable by all AC roles.
- `lockedPaths`: the two lock groups. Each group's lock is `.workflow/<group>.lock`.
- Detect the Python command during setup (`python3`, `python`, `py -3`, or `uv run --no-project python` where the repository says so). Run scripts with `-I` (isolated mode). If there is no Python 3, ask the user.
- Detect the test runner (VSTest or Microsoft.Testing.Platform, see `global.json`) and write the real commands, including the TRX options for that runner. Confirm the TRX options with `--help` on the built AC test project.

---

## 5. What to build

### 5.1 AC test project (Reqnroll)

- Create `tests/<App>.AcceptanceTests` with **Reqnroll** and a test framework adapter. If the solution already uses a test framework, use the same one, and check that the Reqnroll adapter supports that framework version **and** the test runner (VSTest or Microsoft.Testing.Platform). If it doesn't, stop and ask the user. If the solution has no test framework, ask the user (default: xUnit). Use the latest stable package versions that support the solution's target framework.
- **Keep the AC project out of the main solution file.** The skills build and run it by project path. Reasons: solution-wide `dotnet test` would run AC tests during step 4 (pending steps fail, and the main agent would see AC results outside step 6); solution-wide `dotnet format` would rewrite the writer's files; IDE indexing and IDE tools would expose step definitions; and compile errors in step definitions would block step 4 builds and show their contents to the main agent.
- Also add `Microsoft.Extensions.TimeProvider.Testing` (for `FakeTimeProvider`) and global usings for `Reqnroll` and the test framework's assertions. The writer can't edit the csproj, so add common test packages now.
- **Missing or pending steps must fail the run.** In `reqnroll.json`, set `runtime.missingOrPendingStepsOutcome` to `Error`.
- **Code-behind goes to `obj`.** Set `<ReqnrollUseIntermediateOutputPathForCodeBehind>true</ReqnrollUseIntermediateOutputPathForCodeBehind>`. By default Reqnroll writes `*.feature.cs` next to each feature, into `Features/`, where it would end up in the translator's folder and in the `features` lock.
- **Invalid Gherkin is not always a build error.** Reqnroll parses features at build time, so real syntax errors fail the build, but a mistyped keyword is valid Gherkin (description text). `check_features.py` covers that.
- **Reference switch** in the csproj:

  ```xml
  <!-- Ref mode: used only by ac-feature-translator and ac-test-writer to compile. Never executed. -->
  <ItemGroup Condition="'$(AcRefMode)' == 'true'">
    <Reference Include="MyApp.Core">
      <HintPath>$(MSBuildThisFileDirectory)../../artifacts/refs/MyApp.Core.dll</HintPath>
      <Private>false</Private>
    </Reference>
    <!-- one <Reference> per exported ref assembly -->
  </ItemGroup>

  <!-- Normal mode: real implementation, used by /ac-tests-analyze. -->
  <ItemGroup Condition="'$(AcRefMode)' != 'true'">
    <ProjectReference Include="../../src/MyApp.Core/MyApp.Core.csproj" />
  </ItemGroup>
  ```

- **`Directory.Build.props` in the AC project folder.** MSBuild imports only the nearest `Directory.Build.props`, so this file must first import the root one: `<Import Project="$([MSBuild]::GetPathOfFileAbove('Directory.Build.props', '$(MSBuildThisFileDirectory)../'))" />`. Then, when `AcRefMode == true`, set `BaseIntermediateOutputPath` to `obj-ref\` and `BaseOutputPath` to `bin-ref\`, so the two modes never mix restore and build state. (This has to be here, not in the csproj: the csproj is evaluated too late for `BaseIntermediateOutputPath`.) Each mode excludes only its own output folders from default items, so also add `bin/**;obj/**;bin-ref/**;obj-ref/**` to `DefaultItemExcludes`, or the other mode's generated code gets compiled.
- If the solution treats warnings as errors, check that Reqnroll's generated code builds cleanly. If it doesn't, suppress only the specific generated-code warnings in the AC project and tell the user.
- If public types of the AC surface come from NuGet packages, add those packages to the AC project unconditionally, so ref mode compiles.
- **Golden samples** go in `Samples/`. Copy them to the output directory (`<None Include="Samples/**" CopyToOutputDirectory="PreserveNewest" />`) so tests load them by relative path. Mark them binary in `.gitattributes` (`<acProjectDir>/Samples/** binary`), so line endings are never converted. Pin `.feature` files to one line ending (`<acProjectDir>/Features/*.feature text eol=lf`) so their lock hashes are the same in every checkout.
- Create empty `Features/`, `StepDefinitions/` and `Support/` folders and `<acSources>/` (each with a `.gitkeep`). **The main agent never writes into `Features/`, `StepDefinitions/` or `Support/`.**

### 5.2 Reference assemblies and API listings

Script `.claude/scripts/export_refs.py`:

1. Delete and recreate `artifacts/refs/`.
2. Build each AC surface project (Release or Debug, whichever is consistent) with `ProduceReferenceAssembly=true` (on by default in SDK-style projects; set it explicitly anyway).
3. Copy the **reference** assembly of each AC surface project **and of its project-to-project dependencies** into `artifacts/refs/`. Find it with `dotnet msbuild <project> -getProperty:TargetRefPath` (it is in `obj/<config>/<tfm>/ref/`). **Do not** copy the real dlls, `.pdb`, or XML doc files.
4. Generate a readable C# API listing per ref assembly into `artifacts/refs/api/<Assembly>.cs`. Use **`ilspycmd`**, installed as a **local** dotnet tool (`dotnet new tool-manifest` + `dotnet tool install ilspycmd`). The writer can't read binary dlls, so this listing is how it "sees" the API. A ref assembly still keeps **every type**, internal and private nested ones included, with their non-private members, so the script removes every non-public type (with its attributes and body) and every namespace left empty, along with its `using`. Public and protected nested types stay.
5. **Verify**, and fail loudly on any problem:
   - each copied dll contains `ReferenceAssemblyAttribute` (a simple binary search for the string is enough)
   - the AC surface projects don't use `InternalsVisibleTo`. With it, internal members end up in the ref assembly. Search source, csproj and props files. If the scaffold already has it, stop and ask the user (section 7).
   - in the listings, method bodies are only `throw null` (or equivalent stubs) and there is no real logic (no `return`, `if (`, loops, `switch`, `await`, `try`).
   - after filtering, no line of a listing starts with `internal`, `private` or `file`.

The translator's build also needs `artifacts/refs/`, so `/ac-translate` runs this script too. It works on an empty AC surface project.

### 5.3 Scripts (`.claude/scripts/`, Python 3, standard library only)

| Script | Does |
|---|---|
| `ac_lock.py lock <group>` | Writes `.workflow/<group>.lock` (`sources` or `features`): SHA-256 of every file under `lockedPaths[<group>]`, hashed as the bytes on disk. |
| `ac_lock.py verify <group>` | Fails if the lock is missing, a hash differs, or a file was added or removed. |
| `ac_lock.py unlock <group>` | Deletes the lock. Run **only** when the user explicitly asks in chat. |
| `export_refs.py` | Section 5.2. |
| `clear_generated.py features` / `steps` | Deletes the generated files in `Features/`, or in `StepDefinitions/` and `Support/`, keeping `.gitkeep`. Refuses `features` while they are locked. A script, because the guard blocks main-agent tool calls that name the step-definition folders. |
| `new_run.py translate` / `write` | Creates the next `.workflow/runs/translate-NNN/` or `run-NNN/` and prints its id. For `write`: if the newest `analyze-*` folder of the previous `run-*` has a `writer-feedback.md`, copies it to `input-feedback.md`. |
| `new_analyze.py` | Creates the next `analyze-K/` folder in the latest `run-*`. Prints its path. |
| `record_skips.py <translate-run> <AC-id>…` | Writes `skipped.json` in that translate run. Accepts only ids listed in its report's Issues table. |
| `check_features.py` | Structural check of the generated `.feature` files. Gherkin reads a line that doesn't start with a keyword (even a mistyped one, like `Givn`) as description text, so the build passes, the step silently disappears, and a scenario without steps passes. Fails on: a scenario without steps or without both a `When` and a `Then`; non-step text inside a scenario or `Background`; a scenario without exactly one `@AC-` tag; one `@AC-` id on two scenarios. |
| `summarize_trx.py <trx> <out.md>` | Writes the **cleaned** results (section 5.3.1). |
| `extract_feedback.py <judge-report.md> <out.md>` | Copies the text between `<!-- WRITER-FEEDBACK:BEGIN -->` and `<!-- WRITER-FEEDBACK:END -->`. Writes an empty-feedback note if the markers are missing. |
| `changed_files.py snapshot` / `changed_files.py check <role>` | Before/after a subagent runs: records SHA-256 of every file in the working tree (tracked, untracked, and the ignored folders `artifacts/` and `.workflow/`; skip `.git/`, `bin*/`, `obj*/` and `guard.log`), keeping the snapshot in the git directory. Then fails if any file was added, changed or removed outside that role's write allowlist. Content hashes, not `git status`: `git status` can't see a second change to an already-modified file, or writes to ignored paths. |

#### 5.3.1 Cleaned results (`ac-results.md`)

For each test: scenario name, tags, outcome (passed / failed / pending / skipped), and duration. Tags come from the `.feature` files (match the TRX test name to the scenario name; outline rows get example values appended), because the TRX doesn't carry them. For each non-passed test, also:
- the Reqnroll step trace (on MTP with xUnit v3 it is in `Output/TextMessages`; on other runners check `Output/StdOut`). Check during setup that the trace reaches the TRX; if it doesn't, stop and ask.
- the exception type and message (`PendingStepException` / `MissingStepDefinitionException` → outcome `pending`)
- the stack trace, keeping **only frames whose file is inside the AC project**. Replace each run of other frames with a single line `[non-AC frame(s) hidden]`.

At the top: totals. If the repo isn't a git repo yet, ask the user whether to run `git init`.

### 5.4 Hook: `.claude/hooks/guard.py`

**One script, one registration.** It is registered once in `.claude/settings.json` as a `PreToolUse` hook with matcher `*`. Hooks from settings files also fire for tool calls made inside subagents, so the script itself picks the policy from `agent_type`. There are **no hooks in agent frontmatter**: frontmatter hooks are silently skipped when the folder hasn't been trusted, so a guard there fails open.

**Input:** hook JSON on stdin. Use `tool_name`, `tool_input`, `cwd`, and `agent_type` (present when the hook fires inside a subagent, absent in the main conversation; confirm the exact value for a custom agent in smoke test 8).
**Policy by `agent_type`:** `ac-feature-translator`, `ac-test-writer`, `ac-test-fail-judge` → that role. Absent, or **any other value** → role `main`.
**Block:** print the reason to stderr and exit **2**. **Allow:** exit 0 with no output. **Fail closed:** wrap everything in `try/except` and exit 2 on any error.
**Log:** append `agent_type`, tool and decision to `.workflow/guard.log` for every subagent call (the experiment's record of isolation attempts).

**Path handling:**
- Path fields: `Read`, `Write`, `Edit`, `MultiEdit` use `file_path`. `NotebookEdit` uses `notebook_path`. `Grep` and `Glob` use `path` (optional) plus `pattern` / `glob`.
- Resolve relative paths against the hook's `cwd` (fallback `CLAUDE_PROJECT_DIR`), then `os.path.realpath`.
- Compare case-insensitively on Windows, and treat `\` and `/` the same.
- Deny anything outside the project directory for the AC roles. For the `main` role, writes outside the project (scratchpad, memory files) are allowed: G1 and G3 only concern project paths.
- Shell tools: on Windows Claude Code has a `PowerShell` tool next to `Bash`. Hook commands always run through Git Bash, whichever tool the model picks, and matcher `*` covers both. For the `main` role, treat `PowerShell` exactly like `Bash`. The AC roles have no `PowerShell` tool, and default deny blocks it anyway.

#### Rules for every role

- **G1.** For each lock group whose `.workflow/<group>.lock` exists: deny `Write`, `Edit`, `MultiEdit`, `NotebookEdit` on any file under that group's paths and on the lock file itself.

#### Role `main` (main agent and every other subagent type)

- **G2.** Deny any tool call that reaches `<acProjectDir>/StepDefinitions/` or `<acProjectDir>/Support/`:
  - write tools: by their path field only (file content may legitimately mention the folders);
  - Bash and PowerShell: by the command text, and any mention of `StepDefinitions` / `Support` while `cwd` is inside the AC project;
  - every other tool, **including MCP tools** (IDE integrations such as Rider have their own file and search tools with their own field names): by **every string field at any depth**, plus `Grep`/`Glob` `path` resolved to those folders or to the AC project folder itself.
  A string "reaches" them when it contains the AC project folder name followed by `/StepDefinitions` or `/Support`. Message: *"Main agent must not look at AC step definitions (isolation rule). Use test results and the judge report instead."*
- **G3.** Deny write tools on `<acProjectDir>/Features/`, locked or not. Feature files are generated by `ac-feature-translator`; the main agent changes the `.md` instead.
- Otherwise allow.

#### Role `ac-feature-translator`

Default deny. Allowed:

- `Read`: `specInputs`, `acSources`, `<acProjectDir>/Features/`, `<acProjectDir>/Samples/`, `.workflow/runs/translate-*/translation-report.md`.
- `Write` / `Edit`: under `<acProjectDir>/Features/` (G1 applies), and `.workflow/runs/translate-*/translation-report.md`.
- `Grep` / `Glob`: `path` **required** and inside `specInputs`, `acSources`, `Features/` or `Samples/`. `pattern` (Glob) / `glob` (Grep) must not be absolute and must not contain `..`.
- `Bash`: only if the command, trimmed with whitespace collapsed, is **exactly** `acRefBuildCommand` from config. No `&&`, `;`, pipes, or extra flags. Deny message: show the one allowed command.
- Every other tool (including `Skill`, `Agent`, MCP tools): deny.

#### Role `ac-test-writer`

Default deny. Allowed:

- `Read`: `specInputs`; `acSources`; `refsDir`; in `acProjectDir`: the project files at its root and `Features/`, `Samples/`, `StepDefinitions/`, `Support/` (never `bin*/`, `obj*/`); `.workflow/runs/run-*/input-feedback.md`; `.workflow/runs/run-*/writer-report.md`.
- `Write` / `Edit`: under `<acProjectDir>/StepDefinitions/`, under `<acProjectDir>/Support/`, and `.workflow/runs/run-*/writer-report.md`.
- `Grep` / `Glob`: `path` **required** and inside `specInputs`, `acSources`, `refsDir`, or one of the four AC subfolders (never the AC project folder itself). Same pattern rules as the translator.
- `Bash`: exactly `acRefBuildCommand`, as for the translator.
- Every other tool: deny.

#### Role `ac-test-fail-judge`

Default deny. Allowed:

- `Read`, `Grep`, `Glob`: as the writer, but `.workflow/runs/run-*/writer-report.md` and `.workflow/runs/run-*/analyze-*/ac-results.md` instead of the feedback file.
- `Write`: `.workflow/runs/run-*/analyze-*/judge-report.md` only.
- No Bash, no other tools.

#### Hand-back (all AC roles)

A subagent delivers its final message to the main agent with the `SubagentHandback` tool, so default deny must not catch it: without it, no AC skill ever gets the subagent's summary. Allow it for the three AC roles, but deny a hand-back whose text contains a fenced code block or a Reqnroll binding attribute (`[Binding]`, `[Given(`, `[When(`, `[Then(`, `[StepArgumentTransformation`): the main agent must never see step-definition code. For the `main` role (other subagent types), G2's string scan applies to the hand-back like to any other tool, so a hand-back that names a step-definition path is denied and the subagent rephrases.

All AC-role deny messages end with: *"This restriction is intentional. Do not try to work around it. If you cannot continue, record the problem in your report."*

#### `.claude/hooks/test_guard.py`

A table of sample hook payloads with expected allow/deny. Each case runs the guard in a throwaway project folder (config plus the lock files the case needs). Cover at least:
- translator: reads an AC `.md` / the SPEC → allow; writes a `.feature` and its report → allow; writes a `.feature` while `features` is locked → deny; edits an AC `.md`, writes or reads a step definition, reads an API listing or `src/` → deny; runs the build → allow; runs `ls`, calls `Skill` → deny
- writer: reads `src/...cs` or a unit test → deny; reads an API listing, a spec input, an AC `.md`, a feature, the csproj → allow; reads AC `bin/` or `obj-ref/` → deny; writes a feature, a sample or the csproj → deny; edits `StepDefinitions/` or `Support/` and writes its report → allow; reads `ac-results.md` or the judge report → deny
- writer Bash: `ls` → deny; the exact build command (also with extra whitespace) → allow; build + `&& cat src/x.cs`, build + an extra flag → deny
- writer `Glob` without `path`, on the AC project root, or with `..` → deny; `Grep` with `path=src` or an absolute `glob` → deny; `Skill`, `Agent`, `mcp__*`, `WebFetch` → deny
- path traversal `tests/X.AcceptanceTests/../../src/a.cs`, a path outside the project, a relative path into `src/` → deny
- judge: Bash, the trx, the feedback file, `src/` → deny; `ac-results.md`, a step definition, an AC `.md` → allow; writes its report → allow; edits a step definition → deny
- main agent (no `agent_type`): reads/writes/searches a step definition (also with a Windows path, a `Glob` pattern, Bash `cat`, a bare path with `cwd` inside the AC project, an MCP tool with an unknown field, an `Agent` prompt) → deny; `agent_type` = `Explore` reads a step definition → deny; an unknown subagent type reads `src/` → allow
- main agent writes a `.feature` (unlocked) → deny; reads a feature → allow; edits an AC `.md` unlocked → allow, locked → deny; writes a sample while `sources` is locked → deny, while only `features` is locked → allow; edits either lock file → deny; edits a doc whose text mentions the step-definition folders → allow; `git status`, Bash with `cwd` outside the project → allow; writes outside the project (memory, scratchpad) and a write without a path → allow
- PowerShell: main agent `Get-Content` with the full step-definition path, or a bare `Support\…` path with `cwd` inside the AC project → deny; `git status` → allow; writer running the build command through PowerShell → deny; writer writes outside the project → deny
- hand-back: translator, writer (also naming its files) and judge summaries → allow; writer hand-back with a code fence or a binding attribute → deny; `Explore` hand-back naming a step-definition path → deny, a plain one → allow
- malformed JSON, empty input → exit 2

Runs with `<python> .claude/hooks/test_guard.py`, no external packages.

#### `.claude/settings.json`

Register the guard as a `PreToolUse` hook with matcher `*`, using the Python command from config, `"$CLAUDE_PROJECT_DIR/.claude/hooks/guard.py"`, and `"onFailure": "block"` on the hook entry (confirm the exact key and placement in the current hooks documentation). Keep any existing settings and hooks. Register it **last**, after `test_guard.py` passes: a broken fail-closed guard on matcher `*` blocks every tool call, including the ones needed to fix it.

### 5.5 Subagents

The `tools` list removes everything not listed, including MCP tools. `disallowedTools` is added anyway, because the docs say subagents can still reach skills through the `Skill` tool. The guard denies all of them too.

#### `.claude/agents/ac-feature-translator.md`

```markdown
---
name: ac-feature-translator
description: Translates reviewed Gherkin-like acceptance criteria (.md) into valid Reqnroll .feature files and reports every inconsistency instead of guessing. Invoked only by the /ac-translate skill.
tools: Read, Write, Edit, Grep, Glob, Bash
disallowedTools: Skill, Agent, mcp__*
omitClaudeMd: true
---

You turn human-written acceptance criteria into valid Gherkin for Reqnroll.

## What you can see
- The specification: the SPEC and the other spec inputs listed in your task message.
- The acceptance criteria: `.md` files written by a developer in a Gherkin-like syntax and reviewed by a lead. They are locked. You cannot change them. They are meant for humans, so they are **not** guaranteed to be valid Gherkin, complete or consistent.
- The golden sample files in the AC project's `Samples/` folder (their names; you don't need to open them).
- The AC project's `Features/` folder, where you write, and your own earlier translation reports.

You can NOT see the implementation, its API, the unit tests or any test code. You don't need them: your job is the scenarios, not the code that runs them.

Use Read, Grep and Glob for files (Grep and Glob always with an explicit `path`). Bash runs only the one build command from your task message; any other Bash command, including reading files, is blocked. This overrides any general advice to prefer shell commands.

## Your task
1. Read the SPEC and the other spec inputs, then every AC `.md` file.
2. For each AC item, decide: can it be written as Gherkin **without changing or guessing its meaning**?
   - Yes → write it into `Features/<md file name>.feature`, one `.feature` file per `.md` file.
   - No → write nothing for that item, and record an issue (below).
3. Build with the single allowed command (it's in your task message). Reqnroll parses every `.feature` file during the build, so a build error here means invalid Gherkin. Fix your syntax. Stop after 5 build attempts.
4. Write your report (format below).

## Translation rules
- Change the form, never the meaning. Keep each step's wording as close to the `.md` as valid Gherkin allows.
- One `Scenario` (or one `Scenario Outline`) per AC item. Tag it with the item's id and requirement exactly as the `.md` gives them, e.g. `@AC-001 @FR-1`.
- Every scenario has at least one `When` and one `Then` step. No free description text under `Scenario` or `Background`: Gherkin silently reads a line that doesn't start with a keyword (even a mistyped one, like `Givn`) as description, and the scenario then runs without that step. The skill checks this after you finish.
- Normalize only syntax: keywords (`Feature`, `Background`, `Scenario`, `Scenario Outline`, `Examples`, `Given` / `When` / `Then` / `And` / `But`), indentation, tables, quoting. Variations the `.md` lists explicitly become a `Scenario Outline` with `Examples`.
- Copy every concrete value verbatim (bytes, names, numbers, file names). Never add a value, step, assertion or precondition the `.md` doesn't state, and never drop one it does.
- Use domain language only. No class, method or property names.
- A golden sample named in an item must exist in `Samples/` (check with Glob). Refer to it by file name.
- Record every syntax-only normalization under "Interpretations". Anything that would change, add or choose a meaning is an issue, not an interpretation.

## Issues
Record an issue, and write no scenario for the item, when the item:
- is ambiguous (more than one reasonable meaning),
- contradicts another AC item, the SPEC or another spec input (name both sides),
- lacks a concrete value it needs, or uses a value the spec inputs contradict,
- names a golden sample that doesn't exist,
- has no id or no requirement reference,
- can't be expressed as Given / When / Then without guessing what to do or what to check.

For each issue, suggest a fix **for the `.md` text**: the smallest change that would make the item translatable. Set the scope: `item` (only this item is affected) or `global` (several items or the SPEC are affected, so translating the rest may be pointless).

## Report: `.workflow/runs/<RUN_ID>/translation-report.md`
    # Translation report — <RUN_ID>
    ## Build
    success | failure, number of attempts, remaining errors if any
    ## Items
    | AC id | Source .md | Status (translated / issue) | Feature file | Scenario name |
    ## Issues
    | AC id | Kind | Problem | Suggested fix for the .md | Scope (item / global) |
    ## Interpretations
    - <AC id>: <what was normalized and how>

The Issues table must list one row per AC id (use `—` for an item without an id). If there are no issues, keep the heading and write "No issues."

Your final message back: 3–5 lines (build status, items translated, issues by scope). No Gherkin.
```

#### `.claude/agents/ac-test-writer.md`

```markdown
---
name: ac-test-writer
description: Writes Reqnroll step definitions for locked Gherkin acceptance criteria, using only the spec and the public API from reference assemblies. Invoked only by the /ac-tests-write skill.
tools: Read, Write, Edit, Grep, Glob, Bash
disallowedTools: Skill, Agent, mcp__*
omitClaudeMd: true
---

You write acceptance test step definitions for a .NET project using Reqnroll.

## What you can see
- The specification: the SPEC and the other spec inputs listed in your task message.
- The acceptance criteria: the `*.feature` files in the AC test project. They were translated from reviewed `.md` files (also readable, listed in your task message) and are locked. You cannot change them. The `.feature` files are what you bind; the `.md` files are only context.
- Golden sample files in the AC project's `Samples/` folder. They are locked too. The project copies them to the output directory; load them at run time by their relative path. You don't need to open them yourself.
- The public API of the system under test: C# listings in `artifacts/refs/api/*.cs`. These come from reference assemblies, so all method bodies are empty stubs. That is expected.
- The AC test project files, and your own earlier step definitions in `StepDefinitions/` and `Support/`.
- Optionally, a feedback file from a reviewer about your earlier tests.

You can NOT see the implementation source, the unit tests, or any test results. This is on purpose: the experiment checks whether tests can be written from the spec alone. Do not try to get around the restrictions.

Use Read, Grep and Glob for files (Grep and Glob always with an explicit `path`). Bash runs only the one build command from your task message; any other Bash command, including reading files, is blocked. This overrides any general advice to prefer shell commands.

## Your task
Write step definitions so that every step of every scenario is bound to code that faithfully does what the step says.

1. Read the SPEC and the other spec inputs, all feature files, and all API listings. Read the feedback file if your task message names one, and address every point in it.
2. Write step definition classes in `StepDefinitions/`. Put shared state (Reqnroll context injection classes), test doubles, and Reqnroll hooks in `Support/`.
3. Build with the single allowed command (it's in your task message). Fix compile errors. Stop after 8 build attempts.
4. Write your report (format below).

## Rules
- Derive every expected value and every assertion from the Gherkin, the golden samples and the SPEC only. Never guess how the implementation might behave.
- Expected values must be literals from the Gherkin or the content of a named golden sample file. Never compute an expected value at run time from spec data (for example by parsing a lookup table from the spec inputs).
- The spec inputs may describe where the system reads its data from at run time. If the API needs such a location, pass the real one as the SPEC describes.
- Use only the public API from the listings. Choose the most direct API that expresses each step.
- For external effects (time, email, storage, etc.), use public interfaces from the API and your own fakes in `Support/`. For time, use `FakeTimeProvider` if the API accepts a `TimeProvider`.
- Every `Then` step must contain a real assertion that would fail if the behavior were wrong.
- Not allowed: empty step bodies, `Assert.True(true)`, try/catch that hides failures, conditional assertions (`if (...) Assert...`), weaker checks than the step states, hardcoded results.
- If a step **cannot** be expressed through the public API (for example, there is no way to observe that an email was sent), do NOT weaken it. Implement it as
  `throw new PendingStepException("UNEXPRESSIBLE: <short reason>");`
  and list it in your report.
- If a step is ambiguous, choose the most literal reading of the Gherkin and SPEC, and list the interpretation in your report.
- If a `.feature` scenario seems to differ from its `.md` item, bind the `.feature` as written and list the difference in your report.
- You never run tests, and you never edit `.feature` files, sample files or project files.

## Report: `.workflow/runs/<RUN_ID>/writer-report.md`
    # Writer report — <RUN_ID>
    ## Build
    success | failure, number of attempts, remaining errors if any
    ## Coverage
    | Scenario tag | Scenario name | Step definition file(s) |
    ## Unexpressible steps
    | Scenario tag | Step text | Why it cannot be expressed | What the API would need |
    ## Interpretations and assumptions
    - <scenario tag>: <step> — <how you interpreted it and why>
    ## Feedback addressed
    - <feedback item> — <what you changed>   (only if a feedback file was given)

Your final message back: 3–5 lines (build status, number of scenarios bound, number of unexpressible steps). No code.
```

#### `.claude/agents/ac-test-fail-judge.md`

```markdown
---
name: ac-test-fail-judge
description: Decides, for each failing acceptance test, whether the implementation or the test is at fault, without seeing the implementation. Invoked only by the /ac-tests-analyze skill.
tools: Read, Write, Grep, Glob
disallowedTools: Skill, Agent, Bash, mcp__*
omitClaudeMd: true
---

You judge failing acceptance tests in a .NET project that uses Reqnroll.

## What you can see
- The SPEC and the other spec inputs, the reviewed acceptance criteria (`.md`), the `*.feature` files translated from them, the golden samples, and the step definitions (`StepDefinitions/`, `Support/`)
- The public API listings in `artifacts/refs/api/*.cs` (bodies are stubs on purpose)
- The test writer's report: `writer-report.md`
- The cleaned test results: `ac-results.md` (frames outside the AC project are hidden on purpose)

You can NOT see the implementation or the unit tests. Do not try to.

Use Read, Grep and Glob for files (Grep and Glob always with an explicit `path`). You have no Bash. This overrides any general advice to prefer shell commands.

## Your method
For each non-passed scenario:
1. Find the failing step in the step trace.
2. Compare the scenario with its `.md` item (same `@AC-` tag): does the `.feature` say exactly what the reviewed item says?
3. Compare the step definition code with the Gherkin step text and the SPEC. Ask: **does this test do exactly what the scenario says, no more and no less?** Check setup, the API calls used, the expected values, and the assertion. Expected values must be literals from the Gherkin or a named golden sample; a test that computes them from spec data is a `TEST_FAULT`.
4. Choose one verdict:
   - `TRANSLATION_FAULT` — the `.feature` scenario does not faithfully express its `.md` item (changed, added or dropped meaning).
   - `TEST_FAULT` — the test does not faithfully express the scenario (wrong setup, wrong expected value, wrong API use, a bug in the test code, stronger or weaker than the step).
   - `IMPLEMENTATION_FAULT` — the test is faithful, so the failure shows the system does not meet the scenario.
   - `SPEC_AMBIGUITY` — the scenario or SPEC is unclear or contradicts itself, and the test's reasonable reading differs from what the system does. The user must decide.
   - `UNEXPRESSIBLE` — the step is pending because the public API gives no way to perform or observe it.
   - `INCONCLUSIVE` — you can't decide from what you can see. Say what's missing.
5. Give a confidence: high / medium / low.

## Report: `.workflow/runs/<RUN_ID>/analyze-<K>/judge-report.md`
    # Judge report — <RUN_ID> / analyze-<K>
    ## Summary
    | Scenario tag | Verdict | Confidence | One-line reason |
    ## Details (for the user)
    ### <tag> <scenario name>
    - Failing step:
    - What the test does:
    - What the AC item / scenario / SPEC requires:
    - Verdict and reasoning:
    - Suggested action:
    <!-- WRITER-FEEDBACK:BEGIN -->
    ## Feedback for the test writer
    One item per TEST_FAULT scenario: which step definition is wrong and what the scenario/SPEC requires instead.
    <!-- WRITER-FEEDBACK:END -->

**Rule for the feedback section:** it goes to the test writer, who must not learn how the implementation behaves. Do NOT include actual values, exception messages, or anything else observed from running the system. Describe problems only in terms of the AC, the Gherkin, the SPEC, the golden samples and the test code. `TRANSLATION_FAULT` items don't go here (the writer can't change features). If there are no TEST_FAULT items, write "No feedback." between the markers.

You never edit tests, features, samples, or any file other than your report.
Your final message back: the summary table only.
```

### 5.6 Skills

#### `.claude/skills/ac-translate/SKILL.md`

```markdown
---
name: ac-translate
description: Step 3 of the AC experiment. Has the isolated ac-feature-translator subagent turn the reviewed Gherkin-like AC (.md) into Reqnroll .feature files, then walks the user through any issues it found. Run only when the user invokes it.
disable-model-invocation: true
---

Follow these steps exactly. Stop at the first failure and report it. `<python>` is `python` from `.workflow/config.json`; run every script from the repository root.

1. Read `.workflow/config.json`.
2. Run `<python> .claude/scripts/ac_lock.py verify sources`. If it fails: stop and tell the user that the AC `.md` files and golden samples must be reviewed and locked first.
3. If `.workflow/features.lock` exists: stop and tell the user the generated features are locked. Unlock them (`ac_lock.py unlock features`) only if the user explicitly asks.
4. Run `<python> .claude/scripts/export_refs.py` (the translator's build compiles the AC project in ref mode). If it fails: stop and report.
5. Run `<python> .claude/scripts/clear_generated.py features`.
6. Run `<python> .claude/scripts/new_run.py translate` and note the run id.
7. Run `<python> .claude/scripts/changed_files.py snapshot`.
8. Invoke the `ac-feature-translator` subagent with EXACTLY this prompt. Fill in only the placeholders. Add nothing else: no hints, no explanations, no opinions about the AC.

   Run id: <RUN_ID>
   SPEC: <specFile>
   Other spec inputs: <specInputs except specFile>
   Acceptance criteria (.md): <acSources>/
   Golden samples: <acProjectDir>/Samples/
   Write feature files to: <acProjectDir>/Features/
   Allowed build command: <acRefBuildCommand>
   Write your report to: .workflow/runs/<RUN_ID>/translation-report.md

9. Run `<python> .claude/scripts/changed_files.py check ac-feature-translator`. If it reports files outside the allowlist: report an **isolation breach** to the user and stop.
10. Run `<python> .claude/scripts/check_features.py` and note the result.
11. Read `translation-report.md`. Report to the user: run id, build status, the feature check result, items translated, and the full Issues table (AC id, kind, problem, suggested fix for the `.md`, scope).
    If the build failed or the feature check failed: stop. Tell the user to run `/ac-translate` again (the translator gets no message from you; a repeated failure is a finding for the experiment log).
12. If there are issues: ask the user to decide. They can **skip** single items (no scenario, the item stays untested), or choose **fix** for any item or a **full stop**. Wait for the answer.
    - **Fix** or **full stop** (any item): stop. The developer changes the `.md` (the suggested fixes are a starting point), the lead reviews it, and the user asks for `ac_lock.py unlock sources`, edits, `ac_lock.py lock sources`, then `/ac-translate` again. Lock nothing.
    - **Skip** for every remaining issue: run `<python> .claude/scripts/record_skips.py <RUN_ID> <AC ids>`, then go on to step 13.
13. Show the user the generated feature file names and the number of scenarios. The main agent may read them to answer questions, but never edits them. Ask the user to approve the features. Only after an explicit yes: run `<python> .claude/scripts/ac_lock.py lock features`.
14. Append one line to `.workflow/experiment-log.md`: date, run id, `translate`, build status, items translated, issue count, skipped ids, locked yes/no.
15. Stop. Tell the user the next step is the implementation (step 4).
```

#### `.claude/skills/ac-tests-write/SKILL.md`

```markdown
---
name: ac-tests-write
description: Step 5 of the AC experiment. Exports reference assemblies and has the isolated ac-test-writer subagent write Reqnroll step definitions. Run only when the user invokes it.
disable-model-invocation: true
argument-hint: "[fresh]"
---

Follow these steps exactly. Stop at the first failure and report it. `<python>` is `python` from `.workflow/config.json`; run every script from the repository root.

1. Read `.workflow/config.json`.
2. Run `<python> .claude/scripts/ac_lock.py verify sources` and `<python> .claude/scripts/ac_lock.py verify features`. If either fails: stop and tell the user that the AC must be reviewed, translated (`/ac-translate`) and locked first.
3. Build `solution`, then run `unitTestCommand` for each project in `unitTestProjects`. Never run tests for the whole solution. If either fails: stop and report. The implementation step isn't finished.
4. Run `<python> .claude/scripts/export_refs.py`. If verification fails: stop and report the exact problem.
5. If the argument is `fresh`: run `<python> .claude/scripts/clear_generated.py steps`. Do not read the files first.
6. Run `<python> .claude/scripts/new_run.py write` and note the run id.
7. Run `<python> .claude/scripts/changed_files.py snapshot`.
8. Invoke the `ac-test-writer` subagent with EXACTLY this prompt. Fill in only the placeholders. Include the feedback line only if `.workflow/runs/<RUN_ID>/input-feedback.md` exists. Add nothing else: no hints, no explanations, no context about the implementation.

   Run id: <RUN_ID>
   SPEC: <specFile>
   Other spec inputs: <specInputs except specFile>
   Acceptance criteria (.md, context only): <acSources>/
   AC test project: <acProjectDir>
   Feature files: <acProjectDir>/Features/
   Golden samples: <acProjectDir>/Samples/
   Public API listings: <refsDir>/api/
   Allowed build command: <acRefBuildCommand>
   Feedback to address: .workflow/runs/<RUN_ID>/input-feedback.md
   Write your report to: .workflow/runs/<RUN_ID>/writer-report.md

9. Run `<python> .claude/scripts/changed_files.py check ac-test-writer`. If it reports files outside the allowlist: report an **isolation breach** to the user and stop.
10. Do NOT read the step definitions. Do NOT run the AC tests.
11. Read `writer-report.md`. Report to the user: run id, build status, created/changed file names (names only, from step 9), number of scenarios bound, unexpressible steps, interpretations.
12. Append one line to `.workflow/experiment-log.md`: date, run id, `write`, build status, scenarios bound, unexpressible count.
13. Stop. Tell the user the next step is `/ac-tests-analyze`.
```

#### `.claude/skills/ac-tests-analyze/SKILL.md`

```markdown
---
name: ac-tests-analyze
description: Step 6 of the AC experiment. Runs the AC tests against the real implementation and, if any fail, has the ac-test-fail-judge subagent decide whether the test or the implementation is at fault. Run only when the user invokes it.
disable-model-invocation: true
---

Follow these steps exactly. Stop at the first failure and report it. `<python>` is `python` from `.workflow/config.json`; run every script from the repository root.

1. Read `.workflow/config.json`.
2. Run `<python> .claude/scripts/ac_lock.py verify sources` and `<python> .claude/scripts/ac_lock.py verify features`. If either fails: stop and report.
3. Check that the latest `.workflow/runs/run-*` folder (not `translate-*`) has `writer-report.md`. If not: stop and tell the user to run `/ac-tests-write` first.
4. Run `<python> .claude/scripts/new_analyze.py` and note the folder path.
5. Build `acProject` in normal mode (`dotnet build <acProject> -nologo -v q`, no `AcRefMode`). The AC project is not in the solution, so build it by path.
   If it does not compile: the public API probably changed after the reference assemblies were exported. Report only the number of errors and their error codes (no file contents, no message text that quotes step-definition code) and tell the user to run `/ac-tests-write` again. Stop.
6. Run the AC tests with `acTestCommand` from config (`{acProject}` and `{analyzeDir}` filled in). It writes `ac-results.trx` into the analyze folder. A non-zero exit code only means tests failed; continue.
7. Run `<python> .claude/scripts/summarize_trx.py <analyze folder>/ac-results.trx <analyze folder>/ac-results.md`.
8. If every scenario passed: report totals and the AC ids skipped at translation (`skipped.json` in the latest `translate-*` run, if any), append to the experiment log, and stop. Pending/unexpressible steps count as failures.
9. Otherwise run `<python> .claude/scripts/changed_files.py snapshot`, then invoke `ac-test-fail-judge` with EXACTLY this prompt (fill placeholders only, add nothing):

   Run id: <RUN_ID>
   Analyze folder: <analyze folder>
   SPEC: <specFile>
   Other spec inputs: <specInputs except specFile>
   Acceptance criteria (.md): <acSources>/
   AC test project: <acProjectDir>
   Golden samples: <acProjectDir>/Samples/
   Public API listings: <refsDir>/api/
   Writer report: .workflow/runs/<RUN_ID>/writer-report.md
   Test results: <analyze folder>/ac-results.md
   Write your report to: <analyze folder>/judge-report.md

10. Run `<python> .claude/scripts/changed_files.py check ac-test-fail-judge`. Report any breach.
11. Run `<python> .claude/scripts/extract_feedback.py <analyze folder>/judge-report.md <analyze folder>/writer-feedback.md`.
12. Report to the user:
    - totals (passed / failed / pending), and the AC ids skipped at translation, if any
    - the judge's summary table
    - next actions grouped by verdict:
      - TRANSLATION_FAULT → "The feature doesn't match the reviewed AC. Ask me to unlock the features, then run /ac-translate and /ac-tests-write again."
      - IMPLEMENTATION_FAULT → "Ask me to fix the implementation, then run /ac-tests-analyze again."
      - TEST_FAULT → "Run /ac-tests-write. The judge's feedback will be passed to the writer."
      - SPEC_AMBIGUITY → "Decide the intended behavior. Changing the SPEC or the AC .md needs a review and an unlock, then /ac-translate again."
      - UNEXPRESSIBLE → "The public API needs a way to perform/observe this. Ask me to change the implementation, then run /ac-tests-write."
      - INCONCLUSIVE → show the judge's reasoning.
13. Append one line to `.workflow/experiment-log.md`: date, run id, analyze K, passed/failed/pending, verdict counts.
14. Stop.
```

### 5.7 Add a section to `CLAUDE.md`

Add this (adapt paths; the CT version also names the golden samples and the KB rules). Subagents don't load `CLAUDE.md`, so this text is for the main agent only.

```markdown
## AC experiment workflow (see WORKFLOW-SETUP.md)

Steps: 1 SPEC → 2 Gherkin-like AC (.md, lead review) + golden samples, lock `sources` → 3 /ac-translate, lock `features` →
4 implementation + unit tests → 5 /ac-tests-write → 6 /ac-tests-analyze.
**After each step: report, then stop and wait for the user. Never start the next step on your own.**
At the end of each step, offer to make a git commit.

### Step 1 — SPEC (`docs/SPEC.md`)
Write together with the user. Ask questions until the behavior is clear. Sections:
Purpose · Glossary · Functional requirements (numbered FR-1, FR-2, …) · Rules and edge cases · Out of scope ·
Testability requirements · Open questions.
The AC subagents don't load `CLAUDE.md`. Every domain rule the behavior depends on must be in the SPEC (or in another
file listed in `specInputs`, which the SPEC then cites), not only in `CLAUDE.md`.
Testability requirements must include, where relevant:
- time comes from `TimeProvider`, never `DateTime.Now`
- external effects (email, HTTP, files, …) go through public interfaces
- errors are observable (exception types or result types), never silent
- the AC surface project has a public way to create the system with test doubles

### Step 2 — Acceptance criteria (`<acSources>/*.md`, Gherkin-like)
- Written by a developer for humans and reviewed by a lead in a PR. The main agent may help draft them when asked.
- Every item has an id and a requirement reference, e.g. `AC-001 (FR-1)`, and uses domain language and concrete values.
- Golden samples go in `<acProjectDir>/Samples/`; items name them by file name. A golden sample only proves what its
  content can tell apart: add items for the inputs where the behavior differs.
- Self-check: every FR is covered by at least one item. Show the coverage to the user.
- After the lead's approval, and only when the user explicitly asks: `ac_lock.py lock sources`. Unlock only when the
  user explicitly asks; lock again after the reviewed change.

### Step 3 — Translation (`/ac-translate`)
- `ac-feature-translator` writes the `.feature` files and lists every item it couldn't translate faithfully, with a
  suggested `.md` fix. The user decides: skip single items, or fix / full stop, which always goes back to the `.md`.
- The main agent may read the generated features but never writes them (a hook blocks it). `ac_lock.py lock features`
  only after the user explicitly approves them; unlock only when the user explicitly asks.

### Step 4 — Implementation + unit tests
- Implement to satisfy SPEC and the feature files. Use TDD with unit tests as usual.
- Follow the testability requirements from SPEC.
- No `InternalsVisibleTo` in AC surface projects (it leaks internals into reference assemblies). Unit tests use the public API.
- Run unit tests per project (`unitTestProjects`) or for the solution (the AC project isn't in it). Never run the AC project here.
- Done when the solution builds and all unit tests pass.

### Isolation rules for the main agent
- Never read, search, or edit `<acProjectDir>/StepDefinitions/` or `Support/` (a hook blocks this, for every tool and
  for every subagent except the AC roles). Don't bypass it with Bash, IDE tools, or other subagents.
- Don't show their contents indirectly either: no `git diff`, `git show`, `git log -p` or review skills/tools over those
  folders. Exclude them with a pathspec: `git diff -- . ':!**/StepDefinitions/**' ':!**/Support/**'`.
- Never edit locked AC `.md` files or samples, and never write `.feature` files.
- When invoking an AC subagent, use the exact prompt template from the skill. Never add implementation details, hints, opinions, or summaries.
- When fixing the implementation after the judge's verdict: work from `judge-report.md` and `ac-results.md`/`.trx`. Don't change behavior only to match a test's numbers. The goal is to meet the SPEC.
```

### 5.8 `.gitignore` and `.gitattributes`

- `.gitignore`: add `artifacts/`, `**/bin-ref/`, `**/obj-ref/`, `.workflow/guard.log`. Keep the rest of `.workflow/` in git (it is the experiment's history), except `*.trx` if the user prefers.
- `.gitattributes`: add `<acProjectDir>/Samples/** binary` and `<acProjectDir>/Features/*.feature text eol=lf`. With `text=auto` or `core.autocrlf`, git would otherwise convert line endings in text-like samples (binary samples without NUL bytes are detected as text), and feature files would hash differently per OS.

---

## 6. Verification (all must pass before you report that setup is done)

1. `dotnet build <solution>` and `dotnet build <acProject>` succeed. With no features yet, the AC project contains no tests; that's fine.
2. `<python> .claude/hooks/test_guard.py` passes all cases.
3. `ac_lock.py` for each group: `lock` → `verify` passes → change one byte in a feature file, in a sample, add a file → `verify` fails each time → restore → `unlock`. (Use temporary files, then delete them.)
4. `export_refs.py` works on the current scaffold (create a tiny temporary public class with logic and an internal member if the AC surface project is empty; remove it afterwards). Check that the listing has stub bodies only and no internal member, and that a temporary `InternalsVisibleTo` makes the script fail.
5. Ref-mode build: run `acRefBuildCommand` against a temporary file that uses the temporary class, and check that output goes to `bin-ref/` / `obj-ref/`, that the real AC surface dll is not copied there, that the root `Directory.Build.props` settings still apply (a deliberate nullable warning fails the build if warnings are errors), and that the normal-mode build still works afterwards.
6. Feature check: `check_features.py` passes on a temporary valid feature (plain scenario, outline, background) and fails on one with a mistyped keyword, a missing `When`, a missing `@AC-` tag and a duplicated id. The ref-mode build puts the code-behind under `obj-ref/`, not in `Features/`.
7. Test runner: the unit test command does not run the AC project. With a temporary feature (one bound scenario, one unbound) and `acTestCommand`, a TRX file is written, the bound scenario passes, the unbound one fails, and `summarize_trx.py` shows the step trace, tags, `pending` outcome and hidden frames.
8. **Live hook smoke test.** Run it in every new checkout or worktree: workspace trust applies per folder, and trusting a parent folder is not enough. The agents and the hook registration are read at session start, so start a new session first.
   - Invoke `ac-feature-translator` with: *"SMOKE TEST — do not translate. Try each action below once and report which were blocked: (a) Read any file under src/, (b) Write a file in StepDefinitions/, (c) run `ls` with Bash, (d) Read the SPEC file if it exists, (e) run the allowed build command. Then stop."* Expected: a, b, c blocked; d and e allowed.
   - Invoke `ac-test-writer` with: *"SMOKE TEST — do not write tests. Try each action below once and report which were blocked: (a) Read any file under src/, (b) run `ls` with Bash, (c) Glob `**/*.cs` with no path, (d) Read the SPEC file if it exists, (e) run the allowed build command. Then stop."* Expected: a, b, c blocked; d and e allowed.
   - Invoke `ac-test-fail-judge` with a similar prompt: (a) Read under src/ → blocked, (b) Bash → blocked/unavailable.
   - Each subagent must actually deliver its report (`SubagentHandback allow` in the log). A subagent that "can't report back" means the guard is denying the hand-back.
   - Check `.workflow/guard.log`: it shows the three `agent_type` values the guard dispatched on. The judge's Bash attempt has no log line: the judge has no Bash tool at all, so it is stopped by its tool list before the hook runs.
   - Create a temporary empty file in `StepDefinitions/` (with a script, since the guard now blocks the main agent). As the main agent, try to Read it → blocked. Invoke an `Explore` subagent and ask it to read the same file → blocked. Delete the file with `clear_generated.py steps`.
   - Temporarily point the hook command at a missing interpreter and run any tool → blocked (`onFailure`). Restore it **by hand** (the user edits `settings.json`), because the blocked guard also blocks the edit.
   - If any check did not block, **stop and tell the user**. Possible causes: folder not trusted, wrong Python command, `onFailure` not supported or misplaced, or a hook syntax problem.
9. Delete all temporary files created for verification.

---

## 7. Ask the user during setup (only if you can't determine it)

- Test framework for the AC project (if the scaffold has none), or what to do if Reqnroll doesn't support the existing framework version or test runner.
- Which `src` project(s) form the AC surface (if there are several).
- What to do if an AC surface project already uses `InternalsVisibleTo`.
- Which files besides the SPEC belong in `specInputs`, and where the AC `.md` files live (`acSources`).
- Python command, if Python 3 isn't found.
- Whether to run `git init`, if the repo isn't a git repository.

---

## 8. Known limits (accepted for this experiment)

- G2 and G3 are tool-level rules. The main agent could still reach step definitions with a Bash command that doesn't name them (for example a recursive `grep` over `tests/`), or change a `.feature` with Bash or an IDE edit tool. These are soft rules in `CLAUDE.md`. A main-agent `Grep` over the whole repo is blocked only if its `path` points into the AC folders.
- `git diff`, `git show`, `git log -p` and review tools (code-review skills, PR review bots) show step definitions to the main agent unless their folders are excluded. Soft rule in `CLAUDE.md`.
- API names and signatures are visible to the writer. That's by design: tests must use them.
- Exception messages from the implementation reach the judge through `ac-results.md`. They don't reach the writer only because the judge is told to keep observed values out of the feedback section. The script that extracts the feedback is deterministic, but its content is not.
- `const` values and default parameter values are visible in reference assemblies.
- The hand-back screen catches code by its markers only. A subagent could still describe step-definition logic in prose in its final message; its prompt forbids it.
- The guard depends on the Python interpreter being found and on the folder being trusted. `onFailure: block` and smoke test 8 cover this.
- Golden samples are only as strong as their content. A sample that contains none of the inputs where alternatives differ passes for all of them.
- The translator decides what counts as "changing the meaning". The user sees every issue it reports, and the judge checks translation fidelity when a test fails, but a faithful-looking mistranslation of a passing scenario goes unnoticed unless someone reads the features.

---

## 9. When setup is complete

Report to the user: files created, verification results (section 6), any deviations from this document and why. Then stop and wait for the user to start **Step 1 (SPEC)**.

---

§10 (choices specific to the original project) is not part of this copy.
