# Plan — Step 10: fixes for 0.1.2

Spec: `docs/steps/10-fixes-0.1.2.spec.md` (approved 2026-11-12, decisions 1–7 as drafted).

## Evidence (inspected)

- `src/speckit_ac/payload/scripts/export_refs.py`:
  - `LOGIC` is at `:26`;
  - `main()` (`:107–137`) runs `rmtree(refs)` right after it loads the config, then the builds, then the logic
    scan (`:128–131`);
  - `msbuild_json(project, *queries)` (`:40`) always adds `-p:Configuration=Debug` and parses the JSON;
  - `run()` exits with `FAIL:` on a non-zero return code;
  - the module imports only `aclib` from the payload.
- `init_detect.py`:
  - `describe()` (`:137–162`) builds the package list inline: `VersionOverride`, then `Version`, then the central
    pin from `PackageVersion`;
  - `_true()` is at `:133`;
  - `evaluate()` asks for the properties and items, and msbuild prints JSON with `Properties` / `Items`.
- `init_scaffold.py`:
  - `version_key()` / `highest()` are at `:40–47`;
  - the "public package" predicate is inline in `packages()` (`:55–57`);
  - the module imports `init_detect`.
- Tests:
  - `tests/test_scripts.py:653–735` loads `export_refs` through a module fixture and covers `LOGIC`
    (`test_logic_detection`, `:705`);
  - `tests/test_init.py:722` covers `msbuild_json`'s arguments;
  - `test_init.py:378` builds `describe()`-shaped package dicts for `packages()`;
  - no test references `highest` / `version_key` by name.
- `init_verify.py:278` runs `export_refs.py` as a subprocess. `fake_dotnet` patches only in-process calls.
  - Most unit tests stop at `[4] restore` or earlier.
  - `test_verify_reports_leftovers` (`test_init.py:568`) lets the restore succeed, so it starts the real
    subprocess. That subprocess now fails at the first `dotnet msbuild`, because the test project has no surface
    csproj.
  - That test asserts only on `[9]`, and `ref_mode()` tolerates a missing refs folder (critic round 1 traced
    this), so it should still pass. Step 7 watches it.
- `/speckit-ac-tests-write` step 8 is in `commands/speckit.ac.tests-write.md:72–73`. `test_commands.py:234`
  checks `"cross-feature changes, missing packages"`, so that phrase must stay.
- `docs/WORKFLOW.md` does not name `export_refs.py`. Its §3 describes the refs (tracker notes: §3.1 and §4).
  The sentence goes where the refs regeneration is described.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| 1 | `dotnet msbuild <proj> -getItem:X` with no `-getProperty` prints JSON with an `Items` key, and the key is missing when there are no items | 0.9 | The check crashes or misreads | `with_dependencies` already relies on it (`.get("ProjectReference", [])`). The step 4 real run (A04) confirms it |
| 2 | Evaluating the AC project with `-p:AcRefMode=true` needs no restore and no existing `refsDir` | 0.85 | The check fails on a fresh project before any export | A `Reference` glob over a missing folder evaluates to nothing. A04 (fresh scaffold + `init_verify` [4]) confirms it |
| 3 | `PackageReference` items from the shared, unconditional `ItemGroup` show in a ref-mode evaluation | 0.95 | Every package looks missing | MSBuild semantics. A04 and A05 confirm it |
| 4 | Moving `version_key` / `highest` to `init_detect`, with aliases left in `init_scaffold`, breaks nothing | 0.95 | Import errors | grep: no test names them, and `init_scaffold` keeps the names |
| 5 | ilspycmd writes string constants on one line, with C# escapes | 0.85 | Literal stripping misses a case | A04's real listings pass the scan. Multi-line constants are out of scope (spec) |

None is blocking.

## Steps

1. **Shared package helpers in `init_detect.py`** (S10-R04).
   - Add `package_refs(evaluation) -> list[dict]`. It moves the loop out of `describe()` unchanged:
     `{id, version, privateAssets, implicit}`, with versions from `VersionOverride`, then `Version`, then the
     pin.
   - Add `public_package(p) -> bool`: `not p["implicit"] and p["privateAssets"].strip().lower() != "all"`.
   - Move `version_key()` / `highest()` here from `init_scaffold.py`.
   - `describe()` calls `package_refs()`. `init_scaffold.packages()` uses `init_detect.public_package()`.
   - `init_scaffold` keeps `version_key = init_detect.version_key` and `highest = init_detect.highest`, so its
     callers and namespace stay the same.
   - Behaviour does not change. The existing `test_init.py` tests cover it.
2. **Fix 1 in `export_refs.py`** (S10-R01, R02).
   - `LOGIC`: change `\breturn\b` to `\breturn\b(?!\s*:)`, with a comment on the `[return: …]` attribute target.
   - Add `code_only(line)`, a single left-to-right scanner:
     - `//` → stop;
     - `/* … */` → removed, or the rest of the line if it is unclosed;
     - `'…'` with `\` escapes → `''`;
     - a string start matched by `(\$*@\$*|\$+)?("{3,}|")` at the position, decided **by the prefix first**:
       - a prefix that contains `@` means verbatim, whatever the quote count. The scan restarts right after the
         `@…"` opening quote, and `""` is an escape. So `@"""a"" b"` is a verbatim string that starts with an
         escaped quote (critic round 1, MINOR 3);
       - otherwise 3 or more quotes start a raw string, which ends at the same run of quotes;
       - otherwise it is a regular string, with `\` escapes.

       Each literal becomes `""`.
     - An unterminated literal strips the rest of the line.
   - Add the pure function `logic_lines(listing) -> list[str]`. It returns `line.strip()` of every line where
     `LOGIC.search(code_only(line))`. `main()` uses it for the FAIL check (critic round 1, MAJOR 1).
3. **Fix 2 in `export_refs.py`** (S10-R04–R06).
   - `import init_detect` next to `aclib`.
   - Add the pure function `missing_packages(surface, ac, cpm)`:
     - `surface` is a list of `package_refs()` lists, `ac` an iterable of ids;
     - it collects the public packages in first-seen order, deduplicated case-insensitively, that are absent from
       `{a.lower() for a in ac}`;
     - the version is `None` under central package management, else
       `init_detect.highest(all versions of that id across the surface)`, which is `None` when there are none.
   - Add `check_packages(cfg)`:
     - evaluate each surface project with `msbuild_json(p, "-getItem:PackageReference", "-getItem:PackageVersion",
       "-getProperty:ManagePackageVersionsCentrally")`;
     - set `cpm` = any `_true(Properties.ManagePackageVersionsCentrally)` or `ROOT / "Directory.Packages.props"`
       exists;
     - evaluate the AC project with `msbuild_json(cfg["acProject"], "-p:AcRefMode=true",
       "-getItem:PackageReference")` and take `Items.get("PackageReference", [])` → `Identity`;
     - if anything is missing, `sys.exit()` with the spec's R06 message (ASCII, one `dotnet add "<acProject>"
       package <id>[ --version <v>]` line per package).
   - `main()` calls `check_packages(cfg)` right after `load_config`, **before** `rmtree`.
   - The module docstring names both checks.
4. **`/speckit-ac-tests-write` step 8** (S10-R07). Keep the existing sentence, then add: "If the writer report
   lists missing packages: tell the user to add each one to the AC project (`dotnet add "<acProject>" package
   <id>`, `acProject` from the config; it goes into the shared ItemGroup, so both modes get it), then run `/speckit-ac-tests-write` again
   without `fresh`, so the bound step definitions are kept. Never add them yourself." The body must keep no bare
   `scripts/` and so on (S04-R03, which `test_commands` already checks).
   - In `## Report and stop` (`:77`), qualify the next step (critic round 1, MAJOR 2): "The next step is
     `/speckit-ac-tests-analyze`, unless step 8 named missing packages: then it is this command again, without
     `fresh`." The sentence "Never start it, or any other command, yourself." stays word for word
     (`test_commands.py:216`).
5. **Tests** (S10-R03, R08).
   - `tests/test_scripts.py`:
     - replace `test_logic_detection` with a parametrised R03 table run through `logic_lines()` on a one-line
       listing: a match returns the line, a no match returns `[]`. Add the must-match case
       `x = @"""a"" b"; return y;`;
     - assert that `logic_lines` returns the original line with its literal and comment
       (`return "a"; // x` comes back unchanged);
     - add `test_code_only` (escaped quote, verbatim `""`, verbatim starting with `""`, `//` inside a string kept,
       `'\''`, raw string, unterminated string);
     - add `test_missing_packages` (none missing; missing with version; case-insensitive; implicit and
       `PrivateAssets=all` skipped; conflict → highest; CPM → `None`; duplicate across projects listed once;
       no version → `None`);
     - add `test_check_packages_stops_before_any_build_or_delete`. It builds a temporary project with config and
       a pre-existing `refsDir/keep.dll`, monkeypatches `aclib.root` / `export_refs.run` to a fake dotnet that
       answers `msbuild` per project and records calls, and runs `main()`. The test expects `SystemExit` with
       the `dotnet add` lines, no `dotnet build` in the calls, and `keep.dll` still present.
     - in the drift test, assert that the recorded AC-project `msbuild` call contains `-p:AcRefMode=true`
       (critic round 2, MINOR 2);
     - add `test_check_packages_cpm_gives_no_version`: drift with a root `Directory.Packages.props`, and a
       variant where the surface evaluation returns `ManagePackageVersionsCentrally: "true"`. The `dotnet add`
       lines must have no `--version` (critic round 2, MINOR 2);
     - add `test_main_runs_to_the_end_without_drift` (critic round 2, MAJOR 1, option A):
       - `chdir` to the temp project, which has `aclib.root` patched;
       - the fake dotnet answers each call:
         - `msbuild` package queries with nothing missing;
         - `dotnet build` with success;
         - `-getItem:ProjectReference` with `[]`;
         - `TargetRefPath` with a temp `…/ref/App.Core.dll` whose bytes contain `ReferenceAssemblyAttribute`;
         - `tool run ilspycmd` with a listing that holds `[return: NotNull]` and
           `public const string Hint = "return the habit";` on a public type;
       - assert that `main()` finishes and writes `refsDir/api/App.Core.cs`;
       - a second run whose listing holds `\t\t\treturn x;` must raise `SystemExit` whose text quotes `return x;`.

       This also tests R02's "the FAIL message lists the original lines" at the `main()` level. If the real
       `with_dependencies` / `ref` checks need more stubbing than this, the test patches `with_dependencies` to
       return the surface path and keeps the rest real.
   - `tests/test_commands.py`: in `test_tests_write_rules`, assert the new step 8 sentence (`without \`fresh\``,
     `dotnet add`, "Never add them yourself") and the qualified next step ("unless step 8 named missing
     packages").
6. **Docs** (S10-R09, R10).
   - `CHANGELOG.md` `[Unreleased]`: replace `_Nothing yet._` with `### Fixed` / `### Changed` and the migration
     note.
   - `docs/DESIGN.md`: a decision-log row dated 2026-11-12.
   - `docs/WORKFLOW.md`: one sentence where the refs are regenerated.
7. **Verify** (S10-A01–A07).
   - `uv run pytest -q --tb=short` on 3.14, then on 3.11 (the scratchpad venv pattern from the tracker notes).
     `test_verify_reports_leftovers` must pass unchanged.
   - Mutation spot-check, reverting each mutation in turn:
     - drop the lookahead;
     - remove `code_only` from `logic_lines`;
     - make `main()` scan with a bare `LOGIC.search(line)` instead of `logic_lines`;
     - drop the call to `check_packages`;
     - move the call after `rmtree`;
     - compare ids case-sensitively.
   - Opt-in real runs with `SPECKIT_AC_DOTNET_E2E=1`, in the background: `test_e2e_sample.py` and
     `test_init_e2e.py`.
   - A05 (critic round 1, MINOR 5):
     - `git worktree add --detach <scratchpad>/ht-a05 HEAD` of HT;
     - copy only the new `export_refs.py` and `init_detect.py` over its installed scripts, so the check runs with
       HT's installed `aclib` / `init_config`, as after a real upgrade;
     - remove the DI line in the worktree's AC csproj, run `export_refs.py`, and expect exactly the three
       packages;
     - add them with `dotnet add` in the worktree, rerun, then run `dotnet build <ac> -p:AcRefMode=true`;
     - finish with `git worktree remove --force` and `git worktree prune`. HT's own checkout and branches are not
       touched.

     If the export there also needs the `[return:]` fix (HT slice 1 code), that run checks fix 1 for real too.
   - Leak grep on the changed files: no local absolute path.
8. **Tracker**: row 10 status, links, verification, deviations.

## Review dispositions

### Round 1 (`10-fixes-0.1.2.review-1.md`, REVISE, no blocker)

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | MAJOR | The scan wiring in `main()` is untested; dropping `code_only` there passes every test | ACCEPTED: `logic_lines()` in step 2, the R03 table and an original-line assertion run against it in step 5, two mutations in step 7 |
| 2 | MAJOR | `## Report and stop` still names `/speckit-ac-tests-analyze` without condition | ACCEPTED: qualified in step 4 (the asserted sentence is kept), and tested in step 5 |
| 3 | MINOR | `@"""…` is read as a raw string | ACCEPTED: the prefix decides first (step 2); new must-match case (step 5) |
| 4 | MINOR | The evidence claim about `init_verify` tests is wrong for `test_verify_reports_leftovers` | ACCEPTED: evidence corrected, and the test is watched in step 7 |
| 5 | MINOR | A05's worktree would create an HT branch; `aclib` need not be copied | ACCEPTED: `--detach` + `remove --force` + `prune`, and only the two changed scripts are copied |

### Round 2 (`10-fixes-0.1.2.review-2.md`, REVISE, no blocker)

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | MAJOR | The "bare `LOGIC.search` in `main()`" mutation cannot be killed, because no test reaches the scan | ACCEPTED, option A: `test_main_runs_to_the_end_without_drift` in step 5 runs `main()` to the end, with a pass listing and a FAIL listing |
| 2 | MINOR | Central package management detection and the `-p:AcRefMode=true` flag are untested | ACCEPTED: CPM drift test (props file + property variant), and an AC-call flag assertion |
| 3 | MINOR | `<acProject>` is undefined in the command | ACCEPTED: "`acProject` from the config" added to the step 8 sentence |

### Round 3 (`10-fixes-0.1.2.review-3.md`, APPROVE)

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | MINOR | The CPM test passes vacuously without a version on the fake item | ACCEPTED: the props-file variant gives the item a `Version`; the property variant gives a `PackageVersion` pin |
| 2 | MINOR | `package_refs()` metadata names are reached by no dotnet-free test | ACCEPTED: the drift `main()` test adds an implicit item and a `PrivateAssets=all` item, and asserts neither is listed |
| 3 | MINOR | `main()` leaves a stale `ROOT` on the module-scoped fixture | ACCEPTED: `monkeypatch.setattr(export_refs, "ROOT", None)` in each `main()` test |

## Verification (2026-11-12)

- pytest: 845 passed, 9 skipped on CPython 3.14 and on 3.11.15 (scratchpad venv). `test_verify_reports_leftovers`
  passes unchanged.
- Mutations: 10 of 10 caught. These covered the lookahead, `code_only` in `logic_lines`, a bare `LOGIC` in `main()`,
  the `check_packages` call removed or moved after `rmtree`, case-sensitive ids, the AC evaluation without
  `-p:AcRefMode=true`, each half of the CPM rule, and implicit packages counted.
- Opt-in real runs: `test_e2e_sample.py` + `test_init_e2e.py`, 9 passed.
- A05 in a detached HT worktree, then removed. Before: exactly the three slice-1 packages are listed. After
  `dotnet add`: the export of 3 assemblies passes, and the ref-mode build has 0 warnings and 0 errors. HT's
  status and branches are unchanged.
- Leak grep: no local absolute path in a changed file. The FAIL text is ASCII (asserted in a test).
- Deviations: none.
