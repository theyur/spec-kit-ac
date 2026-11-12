# Plan review — round 3 (plan-critic, final)

Spec: `docs/steps/10-fixes-0.1.2.spec.md` · Plan: `.claude/plans/10-fixes-0.1.2.plan.md`

## Round-2 dispositions

| # | Round-2 finding | Applied? |
|---|---|---|
| 1 | The bare `LOGIC.search` mutation cannot be killed | Applied; the end-to-end `main()` test is feasible as written |
| 2 | Central package management and `-p:AcRefMode=true` untested | Applied; the CPM test needs one detail (MINOR 1) |
| 3 | `<acProject>` undefined | Applied |

Feasibility trace of `test_main_runs_to_the_end_without_drift`:

- `aclib.root` must be patched, through `export_refs.aclib`.
- `load_config` stays real.
- `with_dependencies` stays real with the `chdir`; the fake answers `-getItem:ProjectReference` with `Items`.
- `check_no_internals_visible_to` stays real; the surface folder is missing.
- `TargetRefPath` needs `Properties`, a `ref/` folder and the `ReferenceAssemblyAttribute` bytes.
- The fallback (patching `with_dependencies`) is not needed.

Also verified:

- `import init_detect` passes `test_stdlib_only.py`.
- The step 4 text passes the command checks.
- `test_verify_reports_leftovers` still passes.
- The scanner rules handle every R03 row and `x = @"""a"" b"; return y;`.

## Findings

- **[MINOR] 1.** The CPM test can pass vacuously when the fake surface item has no version.
  - Props-file variant: give the item `Version` and leave the property not true.
  - Property variant: give a `PackageVersion` pin.
- **[MINOR] 2.** No dotnet-free test reaches `package_refs()`'s metadata names (`IsImplicitlyDefined`,
  `PrivateAssets`). Fix: in the drift `main()` test, add an implicit item and a `PrivateAssets=all` item, and
  assert that neither is listed.
- **[MINOR] 3.** `main()` sets the module global `ROOT` on a module-scoped fixture. Fix:
  `monkeypatch.setattr(export_refs, "ROOT", None)` in each `main()` test.

## Verdict: APPROVE

No blocker, no major. The minors can be folded in during implementation.
