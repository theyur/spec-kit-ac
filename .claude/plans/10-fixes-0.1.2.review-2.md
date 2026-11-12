# Plan review — round 2 (plan-critic)

Spec: `docs/steps/10-fixes-0.1.2.spec.md` · Plan: `.claude/plans/10-fixes-0.1.2.plan.md`

## Round-1 dispositions

| # | Round-1 finding | Applied? |
|---|---|---|
| 1 | `logic_lines()` and mutations | Applied, but it added a mutation that no planned test can kill (MAJOR 1) |
| 2 | `## Report and stop` qualified | Applied correctly; `test_commands.py:216` sentence kept |
| 3 | Prefix decides before quote count | Applied correctly (`@""`, `@""""`, `@"""a"" b"` traced as verbatim) |
| 4 | Evidence on `test_verify_reports_leftovers` | Applied correctly; the test still passes (re-traced) |
| 5 | A05 `--detach`, two files copied | Applied correctly |

Verified:

- `init_verify.script()` runs scripts with `-I`, and `export_refs.py` puts its own folder on `sys.path`, so
  `import init_detect` works.
- `run_main` gives exit 1 on `sys.exit(text)`.
- `init_verify.export()` prints the output tail under `FAIL [4]`.
- The csproj template has no `PackageReference` group.
- The planned command text passes the existing command checks.
- `WORKFLOW.md:222–224` is the right place for the new sentence.
- A05 holds at HT HEAD: no central package management, and exactly three public packages missing, all at 10.0.15.

## Findings

- **[MAJOR] 1.** The mutation "make `main()` scan with a bare `LOGIC.search(line)`" cannot be killed. Neither
  `main()` test reaches the scan: one exits on drift, the other fails at the build.
  - Option A: run the no-drift `main()` test to the end. Use `chdir`, a fake build success, an empty
    `ProjectReference` list, a fake `ref/` assembly file holding `ReferenceAssemblyAttribute`, and a fake
    ilspycmd listing with `[return: NotNull]` and a `"return …"` constant. Assert that `api/<name>.cs` is
    written. Then a second listing with `return x;` must FAIL and quote that line.
  - Option B: drop the mutation and record that the call site is covered by code review only.
- **[MINOR] 2.** The R05 central-package-management detection and the `-p:AcRefMode=true` flag on the AC
  evaluation are not tested.
  - Fix: add a drift case with `ManagePackageVersionsCentrally: "true"` or a root `Directory.Packages.props`,
    expecting no `--version`.
  - Assert that the AC `msbuild` call has `-p:AcRefMode=true`.
- **[MINOR] 3.** Step 4 uses `<acProject>`, but the command file does not define it.
  - Fix: add "(`acProject` from the config)".

## Verdict: REVISE

No blocker.
