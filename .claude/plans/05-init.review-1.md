# Plan review — step 5, round 1 (plan-critic)

Verdict: **REVISE** (1 BLOCKER, 4 MAJOR, 11 MINOR). Full report as returned by the plan-critic subagent:

1. [BLOCKER] R07's NoWarn bullet is not in the plan; the command rule "never write files yourself" contradicts it. Fix: setup step 6b edits only the AC csproj `NoWarn` for generated-code warnings, reports, re-runs verify; assert in `test_init_rules`.
2. [MAJOR] `IsTestProject` is empty before restore (set by package props). Fix: test project = `IsTestProject` true OR a framework detected from packages; step 12 asserts on a never-restored copy.
3. [MAJOR] Tree snapshot before the first build: restore side effects (e.g. `packages.lock.json`) cause false leftovers. Fix: snapshot after the two normal builds; name `packages.lock.json` in the FAIL text.
4. [MAJOR] `TreatWarningsAsErrors` read from root props text; a Release-only condition gives a false FAIL. Fix: evaluate the AC project in ref mode (`TreatWarningsAsErrors`, `NoWarn`), check only when true and CS0168 not suppressed; otherwise SKIP with reason.
5. [MAJOR] Smoke `end` treats any extra allow as unexpected; extra benign `Read allow` is indistinguishable (no path in the log). Fix: unexpected = an allow for a tool with no expected allow at all; extra counts informational.
6. [MINOR] The Explore manual check: the launch prompt names `StepDefinitions/`, so the guard denies the launch itself. Fix: a denied launch counts as a pass; say why.
7. [MINOR] A4 (CS0168 instead of a nullable warning) is a deviation; the temp file must live under `StepDefinitions/F999/`. Fix: say so; add a Deviations list.
8. [MINOR] Paths with spaces break `shlex.split`, Bash and the guard's comparison. Fix: `init_config.py` rejects whitespace in `acProjectDir`, `refsDir`, `acProject`.
9. [MINOR] Undocumented deviations from R06: FrameworkReferences rendered, scaffold re-evaluates instead of reading detection JSON, surface version before unit tests' version; two surface pins → pick the highest and note it.
10. [MINOR] Scaffold failure leaves the config, so the next run is verify mode. Fix: the command tells the user to delete the config and review listed files; `dotnet tool list --local` non-zero = not installed.
11. [MINOR] `dotnet sln list` lists non-C# projects. Fix: evaluate `*.csproj` only, list others as `ignored`.
12. [MINOR] Unsupported combination found only after confirmation. Fix: `init_detect.py` reports `supported` and the supported list.
13. [MINOR] Smoke `end` must clean up with a missing marker; `write_marker` takes no extra keys. Fix: `end` deletes smoke/absent marker and the temp feature regardless, hint for a non-smoke marker; extend `write_marker` with `**extra`.
14. [MINOR] Interpreter for verify's sub-scripts unstated. Fix: `[sys.executable, "-I", script]`.
15. [MINOR] Verify refuses only `specs/999-*`; leftover temp AC paths would be deleted though not created by it. Fix: refuse when any temporary path exists.
16. [MINOR] `internals_visible_to` reads strict UTF-8. Fix: `errors="replace"`.
