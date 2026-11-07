# Plan review — round 2 (plan-critic)

Spec: `docs/steps/02-runtime-port.spec.md` · Plan: `.claude/plans/02-runtime-port.plan.md`

**Verdict: REVISE** (narrow) — config path normalisation (MAJOR) and a tighter root-fallback test; the rest
are test-strength and documentation items. All ten round 1 dispositions verified as addressed; no
contradiction with DESIGN.md or CLAUDE.md.

## Findings

- **F1 [MAJOR]** Config path validation ("relative, no `..`") lets `""`, `"."`, `"./tests/App.AcceptanceTests"`
  through; `fold()` never makes `./x` equal a normalised `rel`, so G2/G3 and AC-role roots silently stop
  matching while the guard exits 0. `posixpath.normpath` each of `acProjectDir`, `refsDir`,
  `specInputs[*]`; reject `.`, empty, absolute, drive letter, leading `..`; store the normalised form.
  Tests: `acProjectDir: "./tests/AC"` → StepDefinitions read still denied (or config rejected);
  `acProjectDir: "."` → invalid config.
- **F2 [MINOR]** The F9 fallback test can pass vacuously if `CLAUDE_PROJECT_DIR` leaks from the Claude
  session running pytest. Pin it to a case whose outcome depends on the root (translator reads
  `specs/001-alpha/spec.md` with a valid marker → ALLOW) with the env var removed.
- **F3 [MINOR]** R05 is implemented twice (`aclib.resolve_feature`, guard marker check) with separate
  test lists; drift would pass both. One feature-folder table in `tests/acproject.py`, used by both suites.
- **F4 [MINOR]** Name the `check_features.py` tag regex `^@F\d+$`; test `@Fast` on a scenario → OK.
- **F5 [MINOR]** `changed_files.py` tests don't exercise git-ignored folders (the reason for the extra
  scan). Add `.gitignore` for `artifacts/` and `specs/*/ac/runs/`, write into another feature's `runs/`,
  assert a breach.
- **F6 [MINOR]** Guard roots from `cwd` (worktree rule), scripts from their own location: if step 4
  calls scripts via `$CLAUDE_PROJECT_DIR/...`, a worktree session writes marker/locks into the main
  checkout. Record that scripts are invoked by a path relative to the session cwd.
- **F7 [MINOR]** Writer may write `*.feature` under `StepDefinitions/**`/`Support/**`; Reqnroll compiles
  `**/*.feature`, so unlocked scenarios could appear. Exclude `.feature` from the writer's writes and flag
  it in `changed_files.py check ac-test-writer`.
- **F8 [MINOR]** Nothing clears `.workflow/active-run.json`; a later direct AC-role spawn reuses it. Note as
  a follow-up for step 4.
- **F9 [MINOR]** Name where the timestamp/custom-folder limit is recorded as a portability issue.
