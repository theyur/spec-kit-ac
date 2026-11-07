# Plan review — round 3 (plan-critic, final)

Spec: `docs/steps/02-runtime-port.spec.md` · Plan: `.claude/plans/02-runtime-port.plan.md`

**Verdict: REVISE** (narrow, no BLOCKER) — one main-policy rule plus test-list propagation. Round 1–2
items landed; CT case mapping sound; no DESIGN.md/CLAUDE.md contradiction; no hole found in the AC-role
rules or marker validation.

## Findings

- **F1 [MAJOR]** Main-policy G3 is narrowed to `<ac>/Features/**`; spec R13 says ".feature files are never
  written". Reqnroll compiles every `*.feature` in the AC project, so `Write <ac>/Samples/F001/x.feature`
  (unlocked) or `Write <ac>/Extra.feature` adds unlocked scenarios that `check_features.py` never sees.
  Deny any main-policy write under `<ac>/` ending in `.feature` (case-insensitive); tests for both paths.
- **F2 [MINOR]** Round 2 dispositions not propagated to the Test list / step 1: F4 (`@Fast`), F5
  (`.gitignore` + ignored-folder breaches), F6 (cwd-relative invocation in CONFIG.md content).
- **F3 [MINOR]** R06: every per-feature script must print the resolved folder and tag; the plan says so
  only for `new_run`/`new_analyze`. State where and assert it.
- **F4 [MINOR]** WORKFLOW §6 note should also name `.workflow/config.json` as main-agent-editable (it
  reshapes every guard rule; a denial is impossible because init writes it).
- **F5 [MINOR]** Config validation does not reject a `specInputs` entry under/over `specs/`, `<ac>`,
  `<refsDir>` or `.workflow/`; `specInputs: ["specs"]` would hand every role `plan.md`/`tasks.md`. Reject as
  invalid config, or record as a step 5 open item.
