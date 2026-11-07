# Plan review — round 1 (plan-critic)

Spec: `docs/steps/02-runtime-port.spec.md` · Plan: `.claude/plans/02-runtime-port.plan.md`

**Verdict: REVISE** — one isolation hole in the Grep/Glob `path` rule must be closed and tested before
implementation; the rest are clarifications and test gaps.

## Requirement coverage (critic)

R01–R25 covered. Notes: R02 fallback untested; R05 only partly applied to the marker in the guard;
R10–R12 hole in the Grep/Glob `path` rule; R22 fixture description misses the worktree.
Verified: CT sources exist; `public_only`/`LOGIC`/`visible` exist; F6, F7 and A1 correct; no
contradiction with CLAUDE.md or DESIGN.

## Findings

- **F1 [MAJOR]** Grep/Glob `path` rule can open `<ac>/bin` and `<ac>/obj` to the writer and judge. The plan
  says the `path` "must be a search root or a readable file", and CT's `readable()` treats any
  `<ac>/<one-segment>` as a file directly in `<ac>/` without an `is_file()` check (CT used
  `search_root_ok()` only for searches). Reusing that branch allows `Grep path=<ac>/bin` /
  `Glob path=<ac>/obj`. Require `is_file()` for the file branch; add tests: writer/judge Grep `<ac>/bin`
  → deny, Glob `<ac>/obj` → deny, Grep on the csproj → allow.
- **F2 [MINOR]** Step 13 (`aclib` in `ALLOWED`) comes after steps 2–12; `test_stdlib_only` is red in
  between. Move it first.
- **F3 [MINOR]** Step 14 fixture omits the worktree (`.claude/worktrees/wt` with config, specs, AC
  folders, marker) and the `BARE` folder.
- **F4 [MINOR]** Mapping table claims "no flips" but omits `run-002`: CT "writer reads input feedback"
  (ALLOW) and "judge reads input feedback" use `run-002`; with the marker pinned to `run-001` they must
  be rewritten to `run-001`.
- **F5 [MINOR]** Guard marker validation applies R05 only partly: no duplicate-number check, no
  `feature_numbering: "timestamp"` check. Add them or justify. Missing tests: malformed marker JSON,
  `SubagentHandback` without a marker.
- **F6 [MINOR]** Judge "`Write` only" has no negative test (judge `Edit` of its report → deny).
- **F7 [MINOR]** `changed_files.py` skip regex tightened vs spec R16 (`bin*`/`obj*`): record as a
  disposition or spec amendment. Document the order `new_run.py → snapshot → subagent → check` (marker
  and copied `input-feedback.md` would otherwise show as breaches).
- **F8 [MINOR]** `record_skips.py` accepts any `translate-*` id (`translate-001/../../x` escapes);
  validate `^translate-\d{3,}$`.
- **F9 [MINOR]** Guard root fallback untested: add a case without `CLAUDE_PROJECT_DIR` (allow) and one
  with the guard copied to a non-`.specify` path (exit 2).
- **F10 [MINOR]** Not documented: nothing denies main-agent writes to `.specify/extensions/ac/**` (the
  guard itself). Name it in WORKFLOW §6 or add a denial.
