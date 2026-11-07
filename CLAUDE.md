# CLAUDE.md

spec-kit-ac: a spec-kit extension (id `ac`) plus a `speckit-ac` CLI that installs an isolated
acceptance-test workflow into **.NET** projects that already use spec-kit.

## Source of truth

- `docs/DESIGN.md`: every agreed decision. If a request or a plan conflicts with it, stop and ask.
- `docs/steps/TRACKER.md`: implementation steps and their status. Follow its per-step process.
- `docs/reference/WORKFLOW-SETUP-CT.md`: the original method (§0–9 generic, §10 CT-only — never copy
  CT specifics).
- Port from `<original project>\.claude\` (read only; never edit that repo) and
  `~\.claude\skills\speckit-critic\SKILL.md`.

## Working rules

- Every step: draft `docs/steps/NN-<name>.spec.md` → user approves → `/spec-implement <spec>` →
  update the tracker → stop. Never start the next step on your own.
- Target projects are unknown: assume only spec-kit, `CLAUDE.md` and a .NET solution. Detect or ask
  everything else (DESIGN §2).
- Runtime code (guard, scripts, CLI): Python 3, standard library only. Dev-only: pytest.
- Hooks fail closed: inside the guard any error exits 2.
- Commit only when the user asks.

## Test

`uv run pytest -q --tb=short`
