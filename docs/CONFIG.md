# `.workflow/` — config and runtime files

`/speckit-ac-init` writes `.workflow/config.json` once per project, through `init_config.py` and
after the user has confirmed every value. It never overwrites an existing config: change it by hand,
then run `/speckit-ac-init` again to verify. The guard and the workflow scripts
(`.specify/extensions/ac/`) read it on every call. Design: [DESIGN.md](DESIGN.md) §2, §8.

## `config.json` (schema version 1)

| Key | Type | Meaning | Read by |
|---|---|---|---|
| `schemaVersion` | int, `1` | Config format version. Any other value is an error. | guard, scripts |
| `python` | string | Command that runs the guard and scripts, e.g. `uv run --no-project python -I`. | commands, deploy |
| `solution` | string | The product solution (`.sln` / `.slnx`). | commands |
| `specInputs` | list of strings | Extra project documents (files or folders) the AC subagents may read, besides each feature's `spec.md`, `acceptance.md` and the constitution. May be empty. | guard |
| `acSurfaceProjects` | list of strings | Projects whose public API the AC tests target (`.csproj`). | `export_refs.py` |
| `unitTestProjects` | list of strings | Unit test projects run before tests-write. | commands |
| `acProjectDir` | string | The AC test project folder (outside the solution file). | guard, scripts |
| `acProject` | string | The AC test project file. | commands |
| `refsDir` | string | Reference assemblies and API listings, shared by all features (default `artifacts/refs`, git-ignored). | guard, scripts |
| `acRefBuildCommand` | string | The one Bash command the translator and writer may run: the reference-mode build of the AC project. Compared after collapsing whitespace. | guard, commands |
| `unitTestCommand` | string | Unit test command; `{project}` is replaced. | commands |
| `acTestCommand` | string | AC test command; `{acProject}` and `{analyzeDir}` are replaced. | commands |
| `testFramework` | string | Test framework of the AC project: `xunit2`, `xunit3`, `nunit` or `mstest`. The test writer uses its assertion API. | commands (writer task message) |

### Commands per framework and runner

`init_config.py` builds the three commands from one table (`RECIPES`). The runner is
Microsoft.Testing.Platform when `global.json` has `"test": {"runner": "Microsoft.Testing.Platform"}`,
otherwise VSTest.

| | VSTest | Microsoft.Testing.Platform |
|---|---|---|
| `unitTestCommand` | `dotnet test {project}` | `dotnet test --project {project}` |
| `acTestCommand` | `dotnet test {acProject} --no-build --results-directory {analyzeDir} --logger "trx;LogFileName=ac-results.trx"` | `dotnet test --project {acProject} --no-build --results-directory {analyzeDir} <TRX option>` |
| TRX option | — | xUnit v3: `--report-xunit-trx --report-xunit-trx-filename ac-results.trx`; NUnit, MSTest: `--report-trx --report-trx-filename ac-results.trx` |

`acRefBuildCommand` is always `dotnet build <acProject> -p:AcRefMode=true -nologo -v q`.

The packages and properties that `init_scaffold.py` puts into the AC project (besides the Reqnroll adapter,
`Microsoft.Extensions.TimeProvider.Testing` and the surface's own packages):

| Framework | VSTest | Microsoft.Testing.Platform |
|---|---|---|
| xUnit v2 | `xunit`, `xunit.runner.visualstudio`, `Microsoft.NET.Test.Sdk` | not supported (no runner) |
| xUnit v3 | `xunit.v3.mtp-off`, `xunit.runner.visualstudio`, `Microsoft.NET.Test.Sdk`; `OutputType Exe` | `xunit.v3`; `OutputType Exe` |
| NUnit | `NUnit`, `NUnit3TestAdapter`, `Microsoft.NET.Test.Sdk` | `NUnit`, `NUnit3TestAdapter`, `Microsoft.Testing.Extensions.TrxReport`; `OutputType Exe`, `EnableNUnitRunner` |
| MSTest | `MSTest` | `MSTest`; `OutputType Exe`, `EnableMSTestRunner` |

On the .NET 10 SDK, plain `xunit.v3` turns on Microsoft.Testing.Platform, which the SDK refuses under
VSTest; hence `xunit.v3.mtp-off`. Each pair was verified with SDK 10.0.403 and Reqnroll 3.3.4: build,
TRX written to `{analyzeDir}/ac-results.trx`, bound scenario passed, unbound scenario pending
(`tests/test_init_e2e.py`, opt-in).

Paths in `acProjectDir`, `refsDir` and `unitTestProjects` must not contain whitespace, because they end
up in commands that are split on spaces.

### Rules

Rules checked by the guard and the scripts:

- every key is present, strings are non-empty, lists contain only non-empty strings, `testFramework`
  is one of its four values;
- `solution`, `acProjectDir`, `acProject`, `refsDir` and every `specInputs`, `acSurfaceProjects` and
  `unitTestProjects` entry are project-relative paths below the root (normalised:
  `./tests\App.AcceptanceTests/` is stored as `tests/App.AcceptanceTests`; empty, `.`, absolute,
  drive-letter and `..` paths are invalid);
- `acProjectDir` must not overlap `specs/`, `.specify/`, `.workflow/`, `.git/` or `src/`, lie inside
  another project folder or contain one (build output aside), or hold any `.csproj` but `acProject`.
  `acProject` is a `.csproj` directly inside it and not a surface or unit-test project, and
  `acRefBuildCommand` is exactly `dotnet build <acProject> -p:AcRefMode=true -nologo -v q`.
  Otherwise an edited config would move the writer's allowlist or widen the AC roles' only Bash command;
- `refsDir` must not overlap `specs/`, `.specify/`, `.workflow/`, `.git/`, `acProjectDir` or an
  implementation folder (a `.csproj` at the root itself aside): `export_refs.py` deletes it before
  every export;
- a `specInputs` entry must not equal, contain or lie inside `specs/`, `.specify/`, `.workflow/`,
  `acProjectDir` or `refsDir` (it would hand the AC subagents `plan.md`, step definitions or locks),
  nor an implementation folder: `src/` or any folder that holds a `.csproj` (outside `bin/` / `obj/`).
  This is checked on every load, not only by init, because the config is changed by hand. Init's writer
  (`init_config.py`) applies the same rules against the project on disk, so it never writes a config that
  a later load would refuse;
- a broken config blocks **every** tool call (guard exit 2) and fails every script (exit 1);
- a **missing** config means the workflow is not initialised: the guard lets the main agent work
  (except starting `/speckit-ac-*` skills itself) and blocks the AC subagents.

Example:

```json
{
  "schemaVersion": 1,
  "python": "uv run --no-project python -I",
  "solution": "App.slnx",
  "specInputs": ["docs/domain"],
  "acSurfaceProjects": ["src/App.Core/App.Core.csproj"],
  "unitTestProjects": ["tests/App.Tests/App.Tests.csproj"],
  "acProjectDir": "tests/App.AcceptanceTests",
  "acProject": "tests/App.AcceptanceTests/App.AcceptanceTests.csproj",
  "refsDir": "artifacts/refs",
  "acRefBuildCommand": "dotnet build tests/App.AcceptanceTests/App.AcceptanceTests.csproj -p:AcRefMode=true -nologo -v q",
  "unitTestCommand": "dotnet test --project {project}",
  "acTestCommand": "dotnet test --project {acProject} --no-build --results-directory {analyzeDir} --report-xunit-trx --report-xunit-trx-filename ac-results.trx",
  "testFramework": "xunit3"
}
```

## Per-feature paths (derived, not configured)

A feature is a folder `specs/NNN-name` directly under `specs/` (≥ 3 digits; v1.0 rejects timestamp
and custom feature folders). Its tag is `FNNN`. `ac_feature.py` prints all of these as JSON; `ac_feature.py --all` lists every
feature folder with its tag (any folder under `specs/` that is not a valid feature fails the listing).
The subagents' task messages are filled by `task_message.py` from these keys and the config: a
placeholder `<UPPER_SNAKE>` is the key `upperSnake` (see `## Your task message` in each
`payload/agents/*.md`); `RUN_ID` / `ANALYZE_ID` come from the marker, `FEATURE_LIST` from
`ac_feature.py --all` (only the judge's message uses it). `check_acceptance.py` checks a feature's
`acceptance.md` (format: `templates/acceptance-template.md` in the extension) before `sources` is locked.

| Path | Contents |
|---|---|
| `specs/NNN-x/spec.md`, `acceptance.md` | spec-kit spec; the locked AC |
| `specs/NNN-x/ac/sources.lock`, `features.lock` | lock files (written only by `ac_lock.py`) |
| `specs/NNN-x/ac/runs/translate-NNN/` | `translation-report.md`, `skipped.json` |
| `specs/NNN-x/ac/runs/run-NNN/` | `input-feedback.md`, `writer-report.md` |
| `specs/NNN-x/ac/runs/run-NNN/analyze-K/` | `ac-results.trx`, `ac-results.md`, `judge-report.md`, `writer-feedback.md` |
| `<acProjectDir>/Features/FNNN/`, `Samples/FNNN/` | `.feature` files; golden samples |
| `<acProjectDir>/StepDefinitions/FNNN/`, `Support/FNNN/`, `Support/Shared/` | step definitions and helpers |

## Runtime files in `.workflow/`

| File | Written by | Purpose |
|---|---|---|
| `active-run.json` | `new_run.py`, `new_analyze.py`; `task_message.py` adds `taskMessage`; deleted by `changed_files.py check` or `changed_files.py clear` | The active run: `role`, `feature`, `tag`, `run`, `analyze`, and the exact task message. The guard pins every AC-subagent rule to it, blocks AC subagents without a matching marker, and lets the main agent start an AC role only with `prompt` = `taskMessage`, in the foreground. The main agent may not write it. `check` deletes it once it has compared the files (a usage error before that keeps it); it outlives a command only when the command stops before the check (tests-analyze with every test passed; a stop between `task_message.py` and the check). |
| `guard.log` | guard | One line per subagent tool call: agent type, tool, allow/deny. `smoke_test.py end` compares the lines a smoke run added with the expected decisions. |
| `init-check/` | `init_verify.py` | Temporary results of the setup checks (with `specs/999-speckit-ac-check/` and the AC project's `F999` folders); always removed at the end. |

The smoke test writes the marker itself (`smoke_test.py start`). The marker then holds the extra keys
`smoke: true` and `smokeLogLines`, and its feature is the temporary `specs/999-speckit-ac-smoke/`;
`smoke_test.py end` removes both.

## Deploy files (written by `speckit-ac install`)

| File | Purpose |
|---|---|
| `.workflow/deploy.json` | Deploy manifest, committed. `schemaVersion` 1, `version`, guard `command`, `installedAt`, `preexisting` (which of `.claude/settings.json`, `.claude/agents/` and each AC agent file, `.specify/extensions/`, `.specify/extensions.yml`, `.registry`, `.backup/` existed before install), `settingsCreatedKeys`, `settingsNewline`, `settingsReformatted`, and `files`: path, kind (`agent`, `skill`, `extension`) and sha256 of every deployed file (content with CRLF folded to LF). `uninstall` and `doctor` work from it; it never holds `settings.json` content. |
| `.claude/settings.json` | One `PreToolUse` group, `matcher` `*`: `uv run --no-project python -I "$CLAUDE_PROJECT_DIR/.specify/extensions/ac/hooks/guard.py"`, `timeout` 30, `onFailure` `block`. Registered only after the installed guard passed a self-test (a main-agent `Read` allowed, `Skill speckit-ac-init` blocked). The Python part is the v1.0 command; `doctor` checks that the config's `python` matches it. |
| `.claude/agents/ac-*.md` | Byte copies of `.specify/extensions/ac/agents/`. |
| `.claude/skills/speckit-ac-*/SKILL.md` | spec-kit renders them as symlinks; install replaces each with a real file and adds `disable-model-invocation: true` before `metadata:`. |
| `CLAUDE.md` | A block between `<!-- >>> speckit-ac (managed; do not edit) -->` and `<!-- <<< speckit-ac -->` with the main agent's soft rules. |

Managed blocks (written by `/speckit-ac-init`, removed by `speckit-ac uninstall`; between
`# >>> speckit-ac (managed; do not edit)` and `# <<< speckit-ac`, the rest of the file untouched):

- `.gitignore`: `/<refsDir>/`, `**/bin-ref/`, `**/obj-ref/`, `/.workflow/guard.log`,
  `/.workflow/active-run.json`, `/.specify/extensions/ac/**/__pycache__/`;
- `.gitattributes`: `<acProjectDir>/Samples/** binary`, `<acProjectDir>/Features/**/*.feature text eol=lf`,
  `specs/*/acceptance.md text eol=lf`, `specs/*/spec.md text eol=lf`.

`changed_files.py` stores its snapshot in the git directory. Order inside a command:
`new_run.py` / `new_analyze.py` → `task_message.py` → `changed_files.py snapshot` → subagent (`Agent`
tool, prompt = the output of `task_message.py`) → `changed_files.py check <role>`.

`acTestCommand` must write the TRX results to `{analyzeDir}/ac-results.trx` (the option depends on
the runner and framework; see the table above). `/speckit-ac-tests-analyze` stops when the
file is missing.

## Invoking the scripts

Commands run the scripts from the session's working directory by their **relative** path:
`<python> .specify/extensions/ac/scripts/<name>.py …`. A script takes the project root from its own
location, so in a worktree session (`.claude/worktrees/<name>/`) it acts on that worktree, which is
also where the guard looks for the marker and the locks. Never call them via `$CLAUDE_PROJECT_DIR`: that
stays the main checkout, and the marker would land where the guard does not read it.
