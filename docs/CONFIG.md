# `.workflow/` — config and runtime files

`/speckit-ac-init` (tracker step 5) writes `.workflow/config.json` once per project. The guard and the
workflow scripts (`.specify/extensions/ac/`) read it on every call. Design: [DESIGN.md](DESIGN.md) §2, §8.

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

Rules checked by the guard and the scripts:

- every key is present, strings are non-empty, lists contain only non-empty strings, `testFramework`
  is one of its four values;
- `acProjectDir`, `refsDir` and every `specInputs` entry are project-relative paths below the root
  (normalised: `./tests\App.AcceptanceTests/` is stored as `tests/App.AcceptanceTests`; empty, `.`,
  absolute, drive-letter and `..` paths are invalid);
- a `specInputs` entry must not equal, contain or lie inside `specs/`, `.specify/`, `.workflow/`,
  `acProjectDir` or `refsDir` (it would hand the AC subagents `plan.md`, step definitions or locks);
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
  "acTestCommand": "dotnet test --project {acProject} --no-build --results-directory {analyzeDir}",
  "testFramework": "xunit3"
}
```

## Per-feature paths (derived, not configured)

A feature is a folder `specs/NNN-name` directly under `specs/` (≥ 3 digits; v1.0 rejects timestamp
and custom feature folders). Its tag is `FNNN`. `ac_feature.py` prints all of these as JSON; `ac_feature.py --all` lists every
feature folder with its tag (any folder under `specs/` that is not a valid feature fails the listing).
The subagents' task messages are filled from these keys and the config: a placeholder `<UPPER_SNAKE>`
is the key `upperSnake` (see `## Your task message` in each `payload/agents/*.md`).

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
| `active-run.json` | `new_run.py`, `new_analyze.py` | The active run: `role`, `feature`, `tag`, `run`, `analyze`. The guard pins every AC-subagent rule to it and blocks AC subagents without a matching marker. The main agent may not write it. |
| `guard.log` | guard | One line per subagent tool call: agent type, tool, allow/deny. |

`changed_files.py` stores its snapshot in the git directory. Order inside a command:
`new_run.py` / `new_analyze.py` → `changed_files.py snapshot` → subagent → `changed_files.py check <role>`.

## Invoking the scripts

Commands run the scripts from the session's working directory by their **relative** path:
`<python> .specify/extensions/ac/scripts/<name>.py …`. A script takes the project root from its own
location, so in a worktree session (`.claude/worktrees/<name>/`) it acts on that worktree, which is
also where the guard looks for the marker and the locks. Never call them via `$CLAUDE_PROJECT_DIR`: that
stays the main checkout, and the marker would land where the guard does not read it.
