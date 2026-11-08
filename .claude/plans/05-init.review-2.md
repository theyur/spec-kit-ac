# Plan review — step 5, round 2 (plan-critic)

Verdict: **REVISE** (0 BLOCKER, 1 MAJOR, 8 MINOR). All 16 round-1 findings were found resolved in the plan text.

1. [MAJOR] Step 6b needs the compiler codes, but verify prints only PASS/FAIL lines. Fix: a failed build check prints the build's `error CSnnnn`/`RQnnnn` lines (with file paths) under the FAIL line; exit 1 on any FAIL; test with a stubbed failing build.
2. [MINOR] Scaffold can't report `Directory.Packages.props` / tool manifest changes. Fix: hash them before the dotnet calls and compare afterwards; list as created/changed.
3. [MINOR] Render tests miss `ReqnrollUseIntermediateOutputPathForCodeBehind`, `Samples/**` copy, `DefaultItemExcludes`, `reqnroll.json` outcome. Fix: assert them.
4. [MINOR] The third manual smoke check (missing interpreter) is not in the command outline. Fix: list all three, assert in `test_init_rules`; spell the hook path as `.specify/extensions/ac/hooks/guard.py` (rendering rule).
5. [MINOR] Explore check: a bare `StepDefinitions/…` prompt passes the launch and the read is denied instead. Fix: accept either denial; showing the content is the failure.
6. [MINOR] Whitespace check on `solution` is over-strict; `unitTestProjects` go through `{project}` unchecked. Fix: drop it for solution, add it for unitTestProjects (or document).
7. [MINOR] `finally` before the snapshot exists. Fix: compare only when a snapshot exists; test a [1] build failure (no temp paths, no tree check, exit 1).
8. [MINOR] TWAE check ignores `WarningsNotAsErrors`. Fix: read it too; SKIP when it lists CS0168.
9. [MINOR] `export_refs.check_no_internals_visible_to` still reads strict UTF-8. Fix: `errors="replace"` there too (Step 0).
