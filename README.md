# spec-kit-ac

A [spec-kit](https://github.com/github/spec-kit) extension (id `ac`) plus a `speckit-ac` CLI that add
an **isolated acceptance-test workflow** to .NET projects. Acceptance criteria are written before
implementation, reviewed and locked; isolated Claude Code subagents translate them into Reqnroll
`.feature` files, write step definitions from the spec and the public API alone (never the
implementation), and judge every failing test. Isolation is enforced by a fail-closed guard hook and
deterministic scripts, not only by instructions.

> **Status: pre-release, under construction.** The CLI and the extension are built and have run end
> to end with a live model on a sample project (step 7) and are installed in their first real project, Habit
> Tracker (step 8: install, init, live smoke test). Not yet released. Progress is tracked in
> [docs/steps/TRACKER.md](docs/steps/TRACKER.md).

## Prerequisites (target project)

- spec-kit installed and initialised (`.specify/`, `specs/NNN-*/`, constitution).
- A `CLAUDE.md`.
- A .NET solution (`.sln` or `.slnx`).

Everything else (AC-surface projects, test framework and runner, Python command, extra spec inputs)
is detected or asked once by `/speckit-ac-init`.

## Install (pre-release: from a local checkout or the git URL)

```bash
uv tool install speckit-ac --from git+https://github.com/<owner>/spec-kit-ac
```

Then, from the root of the spec-kit project (the folder with `.specify/`):

```bash
speckit-ac install
```

`install` checks the prerequisites (Windows, uv, PowerShell 7, spec-kit ≥ 1.0.2 initialised with
`--script ps` and the Claude integration, `CLAUDE.md`, a solution, git), adds the spec-kit extension and
deploys the Claude-side files: the three AC agents, the guard registration in `.claude/settings.json`,
the human-only `speckit-ac-*` skills (real files with `disable-model-invocation: true`), a block in
`CLAUDE.md` and the manifest `.workflow/deploy.json`. Then:

1. start a **new** Claude Code session in the project and trust the folder (agents and hooks load at
   session start);
2. run `/speckit-ac-init`;
3. in another new session, run `/speckit-ac-init smoke` (live guard smoke test);
4. commit the deployed files. Teammates need only the committed files; `speckit-ac doctor` (with the
   tool installed) checks a checkout.

## Commands

| Command | What it does |
|---|---|
| `speckit-ac install` | Check prerequisites, add the spec-kit extension, deploy the Claude-side files |
| `speckit-ac uninstall` | Undo the deploy (keeping user-modified files), remove the extension |
| `speckit-ac upgrade` | Re-add the extension and redeploy |
| `speckit-ac doctor` | Check the deployed files' hashes, the skills' flag, the guard registration and self-test, the Python command; writes nothing |
| `/speckit-ac-init` | Once per project: detect and ask, scaffold the AC project, write config, verify |
| `/speckit-ac-translate` | Draft and lock `acceptance.md`, then translate it to `.feature` files |
| `/speckit-ac-tests-write` | Write step definitions in isolation |
| `/speckit-ac-tests-analyze` | Run the AC tests and judge failures |
| `/speckit-ac-critic` | Critic review of spec, plan, tasks, AC or features |

## Documentation

- [docs/WORKFLOW.md](docs/WORKFLOW.md): the workflow and its isolation rules.
- [docs/DESIGN.md](docs/DESIGN.md): agreed design decisions.
- [docs/steps/TRACKER.md](docs/steps/TRACKER.md): implementation steps and status.

## Development

Requires [uv](https://docs.astral.sh/uv/). Runtime code is Python 3.11+, standard library only;
pytest is a dev dependency.

```bash
uv sync
```

```bash
uv run pytest -q --tb=short
```

## License

[MIT](LICENSE).
