# `payload/` — the spec-kit extension `ac`

This folder **is** the spec-kit extension. `speckit-ac install` passes it to
`specify extension add --dev`, which copies it to `.specify/extensions/ac/` in the target project.
The Claude-side files that spec-kit does not know about (agents, guard registration, `CLAUDE.md`
blocks) are deployed by the `speckit-ac` CLI from here as well.

It is shipped as package data and is **never imported as Python** (no `__init__.py`). Scripts in it
run later, inside the target project, with the Python command stored in `.workflow/config.json`.

## Planned layout

| Path | Contents | Filled in tracker step |
|---|---|---|
| `extension.yml` | Extension manifest (id `ac`, commands, optional hooks) | 4 |
| `commands/speckit.ac.*.md` | `init`, `translate`, `tests-write`, `tests-analyze`, `critic` | 4 (`init`: 5) |
| `agents/` | `ac-feature-translator`, `ac-test-writer`, `ac-test-fail-judge` | 3 |
| `hooks/guard.py` | Fail-closed `PreToolUse` guard | 2 |
| `scripts/` | Deterministic helper scripts (locks, runs, feedback, results) | 2 |
| `templates/` | AC project scaffolding, `acceptance.md` template, config template | 4–5 |

Until those steps are done this README is the only file here.
