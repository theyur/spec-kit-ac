# spec-kit-ac

A [spec-kit](https://github.com/github/spec-kit) extension (id `ac`) plus a `speckit-ac` CLI that add
an **isolated acceptance-test workflow** to .NET projects. Acceptance criteria are written before
implementation, reviewed and locked; isolated Claude Code subagents translate them into Reqnroll
`.feature` files, write step definitions from the spec and the public API alone (never the
implementation), and judge every failing test. Isolation is enforced by a fail-closed guard hook and
deterministic scripts, not only by instructions.

> **Status: pre-release, under construction.** Nothing below is usable yet; progress is tracked in
> [docs/steps/TRACKER.md](docs/steps/TRACKER.md).

## Prerequisites (target project)

- spec-kit installed and initialised (`.specify/`, `specs/NNN-*/`, constitution).
- A `CLAUDE.md`.
- A .NET solution (`.sln` or `.slnx`).

Everything else (AC-surface projects, test framework and runner, Python command, extra spec inputs)
is detected or asked once by `/speckit-ac-init`.

## Install (planned — not available yet)

```bash
uv tool install speckit-ac --from git+https://github.com/<owner>/spec-kit-ac
```

## Commands (planned)

| Command | What it does |
|---|---|
| `speckit-ac install` | Check prerequisites, add the spec-kit extension, deploy the Claude-side files |
| `speckit-ac uninstall` | Undo the deploy (keeping user-modified files), remove the extension |
| `speckit-ac upgrade` | Re-add the extension and redeploy |
| `speckit-ac doctor` | Check hashes, guard registration and the Python command |
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
