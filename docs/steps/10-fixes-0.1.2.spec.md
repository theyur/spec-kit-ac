# Step 10 — Fixes for 0.1.2 (Habit Tracker slice 1)

**Status:** done (2026-11-12; decisions 1–7 approved as drafted; no deviation) · **Tracker row:** 10 · **Source of truth:** `docs/DESIGN.md`

## Goal

Port the two fixes that Habit Tracker slice 1 patched locally into its installed copy
(`<habit-tracker>/speckit-ac-fixes.md`) into the package, each with regression tests:

1. `export_refs.py` no longer reports `[return: …]` attribute targets, or keywords inside string literals and
   comments, as logic.
2. Ref mode stops losing packages that the surface projects gained after `/speckit-ac-init`. `export_refs.py`
   fails early and names the exact `dotnet add` lines. A writer report that lists missing packages names the
   next step.

The release of 0.1.2 and the Habit Tracker upgrade are not part of this step.

## Context (inspected 2026-11-12)

- **Fix 1.** `export_refs.py:26` defines `LOGIC` with a bare `\breturn\b`. It scans every line of the full
  ilspycmd listing (`:128–131`), before `public_only()`, and that order is correct: logic anywhere in a reference
  assembly means it is not one.
  - In HT an internal `ILookupNormalizer` implementation carries `[return: NotNullIfNotNull("name")]`, and the
    export failed.
  - Any nullability contract on a return value would trigger it (`[return: MaybeNull]`, `[return: NotNull]`).
  - The same regex also matches keywords inside string literals, for example a public
    `const string Hint = "return the habit";`. ilspycmd writes such constants with their values.
  - The current test is `tests/test_scripts.py:705` (`test_logic_detection`, three asserts).
- **Fix 2: the cause differs from the one the HT notes give.** The notes say that ref mode never gets the
  surface's packages. In fact `init_scaffold.py` already adds every direct package of the surface projects that is
  not implicit and not `PrivateAssets=all` (`packages()`, `:50–80`). Its versions come from the central pins, then
  the surface, then the unit tests (DESIGN decision log, 2026-11-08). It does this **once**, at init. In HT:
  - the AC project was scaffolded on 2026-11-09 (HT `2752ce9`);
  - on 2026-11-11 (HT `8e31fad`), `HT.Persistence` gained `Microsoft.AspNetCore.Identity.EntityFrameworkCore`
    and `Microsoft.EntityFrameworkCore.SqlServer`, and `HT.Application` gained
    `Microsoft.Extensions.DependencyInjection.Abstractions`;
  - nothing re-checks the AC project, so ref mode lacked all three. Normal mode got them through the
    `ProjectReference`s.

  EF Core depends on `Microsoft.Extensions.DependencyInjection`, so with an up-to-date package list the writer's
  `ServiceCollection` would have compiled in ref mode too. The local workaround (a direct
  `Microsoft.Extensions.DependencyInjection` reference in the AC csproj) hides the drift but does not remove it.
- `export_refs.py` runs at the start of `/speckit-ac-translate` phase 2 (step 11) and `/speckit-ac-tests-write`
  (step 5), and in `init_verify.py` item [4]. Both commands already say "if it fails: stop and report its message".
- `init_detect.describe()` (`:137–162`) already turns an msbuild evaluation into
  `packages: [{id, version, privateAssets, implicit}]`. It resolves versions as `VersionOverride`, then
  `Version`, then the central pin.
- The writer agent lists `## Missing packages` in its report (`ac-test-writer.md:172`). `/speckit-ac-tests-write`
  step 8 relays them without a next step. The writer never edits project files (`ac-test-writer.md:159`).

## Decisions to approve

1. **Fix 2 = drift check that fails** (user, 2026-11-12). The AC project is never edited automatically.
   Rejected: a warning only (the writer still wastes a run), auto-sync through a generated props file (it needs a
   csproj migration and handling for duplicates and versions), and documentation only.
2. **Required set = init's set.** These are the direct `PackageReference`s of each `acSurfaceProjects` entry that
   are not implicit and not `PrivateAssets=all`. The packages of their project-to-project dependencies are not
   included, as in init. A fresh scaffold therefore always passes. Widening both is out of scope.
3. **Present = the AC project's evaluated `PackageReference` ids in ref mode** (`-p:AcRefMode=true`), compared
   case-insensitively.
   - Versions are not compared. In normal mode a mismatch already surfaces as a NuGet downgrade error.
   - A package that reaches the AC project only transitively counts as missing. The check stays deterministic
     with no restore, and it matches what init would have added.
4. **The check runs first in `export_refs.py`**, before any build. It is cheap (msbuild evaluation only) and stops
   the command before the translator or the writer starts.
5. **The message gives the fix verbatim.** It prints one line per missing package:
   `dotnet add "<acProject>" package <id> --version <v>`. The `--version` part is left out under central package
   management or when the surface has no version. The message ends with "add them (shared ItemGroup, both modes),
   then run the command again". The main agent reports it and stops (the existing command rule).
6. **Fix 1 keeps the order** (logic scan on the full listing). Only the scanned text changes:
   - the `return` lookahead from the notes (`\breturn\b(?!\s*:)`);
   - string literals, char literals and comments are stripped from each line before the scan.

   The FAIL message still quotes the original lines.
7. **Version.** The changes go under `## [Unreleased]` in `CHANGELOG.md`. The release (`0.1.2`, tag, README pin)
   is a separate release PR, as for 0.1.1.

## Requirements

### Fix 1: logic scan (`export_refs.py`)

- **S10-R01** `LOGIC` no longer matches `return` followed by optional whitespace and `:`. Every other alternative
  is unchanged. The comment above it says why.
- **S10-R02** A new pure function `code_only(line)` returns the line with these replaced by an empty literal or
  removed:
  - regular strings `"…"` with `\` escapes;
  - verbatim strings `@"…"` with `""`;
  - interpolated strings `$"…"` / `$@"…"` / `@$"…"`;
  - single-line raw strings `"""…"""`;
  - char literals `'…'`;
  - `//` comments to the end of the line (after the strings are removed);
  - single-line `/* … */` comments.

  The logic scan applies `LOGIC` to `code_only(line)`. The FAIL message lists the original stripped lines, as
  today.
- **S10-R03** Regression tests (pure functions, no dotnet):

  | Must match | Must not match |
  | --- | --- |
  | `return x;` | `[return: NotNullIfNotNull("name")]` |
  | `\treturn;` | `\t[return: MaybeNull]` |
  | `return cond ? a : b;` | `[return : NotNull]` |
  | `if (x) throw null;` | `public string? NormalizeName(string? name)` |
  | `foreach (var i in xs)` | `throw null;` |
  | `await Task.Delay(1);` | `public const string Hint = "return the habit";` |
  | `switch (x)` | `public const string P = @"if (a) ""b""";` |
  | `try` | `public const char C = '"'; // return` |
  | `return "a"; // x` | `/* while (x) */ public int X;` |
  |   | `public const string E = "say \"return\" now";` |

  `code_only` also gets its own cases: an escaped quote, a verbatim `""`, a `//` inside a string kept as string
  content, and a char literal `'\''`.

### Fix 2: package drift (`export_refs.py`, `/speckit-ac-tests-write`)

- **S10-R04** A new pure function `missing_packages(surface, ac, cpm)`.
  - `surface` holds the `describe()`-shaped package lists of the surface projects; `ac` holds the AC project's
    package ids.
  - It returns `[(id, version or None)]` in first-seen order, without duplicates (case-insensitive), for each
    required package (decision 2) absent from `ac`.
  - The version is the surface's: the highest when several projects disagree, using init's `highest()`. It is
    `None` under central package management.

  The package-list logic is shared with `init_detect` / `init_scaffold` rather than copied: the plan picks the
  smallest refactor, such as a `package_refs(evaluation)` helper in `init_detect` that `describe()` also uses.
- **S10-R05** `export_refs.main()` runs the check before any build.
  - It evaluates each surface project (`-getItem:PackageReference -getItem:PackageVersion`
    `-getProperty:ManagePackageVersionsCentrally`).
  - It evaluates the AC project with `-p:AcRefMode=true -getItem:PackageReference`.
  - On missing packages it exits 1 with S10-R06's message, and `refsDir` is left as it was. In the code today
    `rmtree` runs first, so the check must come before it.
  - Central package management is on when any surface project evaluates it as true, or when the root
    `Directory.Packages.props` exists (init's rule).
- **S10-R06** The message:

  ```text
  FAIL: the AC project lacks packages that the AC surface references (ref mode compiles only against the
  reference assemblies, so their types are missing there):
    dotnet add "<acProject>" package <id> --version <v>
    ...
  Add them to the AC project (they go into the shared ItemGroup, so both modes get them), then run the command again.
  ```

  The text is ASCII only, as all script output (step 5 finding).
- **S10-R07** `/speckit-ac-tests-write` step 8: when the writer report's `## Missing packages` lists anything, the
  report to the user names the next step:
  - add each package to the AC project (`dotnet add "<acProject>" package <id>`, shared ItemGroup);
  - then run `/speckit-ac-tests-write` again **without** `fresh`, so the bound step definitions are kept.

  The main agent never adds the packages itself.
- **S10-R08** Tests, with dotnet stubbed through monkeypatched `run` / `msbuild_json`:
  - `missing_packages`:
    - none missing;
    - a missing package, with its version;
    - case-insensitive ids;
    - implicit and `PrivateAssets=all` packages skipped;
    - a version conflict resolved to the highest;
    - central package management gives no version;
    - a package required by two projects listed once.
  - `main()`: with drift it exits 1 with the `dotnet add` lines, has run no `dotnet build`, and leaves a
    pre-existing `refsDir` untouched; without drift it goes on to the build.
  - `/speckit-ac-tests-write`: a `test_commands.py` text check for the R07 sentence (`without` + `fresh`).
  - The existing `init_verify` tests that stub `export_refs.py` keep passing unchanged.

### Docs

- **S10-R09** `CHANGELOG.md` `## [Unreleased]`:
  - `### Fixed`: the `[return: …]` and string-literal false positives;
  - `### Changed`: the package drift check, and the tests-write next step for missing packages;
  - a migration note: projects with drift now fail at `export_refs.py` until the listed packages are added.
- **S10-R10** `docs/DESIGN.md` gets a decision-log row (decisions 1–6). `docs/WORKFLOW.md`, where it describes
  `export_refs.py`, gets one sentence on the package check. The `export_refs.py` module docstring mentions both
  checks.

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S10-A01 | `uv run pytest -q --tb=short` passes on CPython 3.14 and 3.11 | all |
| S10-A02 | The R03 table and the `code_only` cases pass; dropping the lookahead or the literal stripping fails at least one test (mutation spot-check) | R01–R03 |
| S10-A03 | The `missing_packages` and `main()` tests pass; dropping the check, putting it after the build or the `rmtree`, or comparing ids case-sensitively fails at least one test (mutation spot-check) | R04–R06, R08 |
| S10-A04 | Opt-in real runs pass with the check active: `SPECKIT_AC_DOTNET_E2E=1` `test_e2e_sample.py` and the `test_init_e2e.py` matrix (a fresh scaffold has no drift) | R04, R05 |
| S10-A05 | Manual, HT untouched: in a throwaway HT worktree in the scratchpad, with the new `export_refs.py` copied in, check two states. Without the local DI line, the check lists exactly the three slice-1 packages. With them added, it passes and the AC project builds in ref mode | R05, R06 |
| S10-A06 | The tests-write command text has the R07 next step; no other command changes | R07 |
| S10-A07 | The changelog, DESIGN and WORKFLOW entries exist; no local absolute path in any changed file | R09, R10 |

## Out of scope

- The 0.1.2 release (version bump, tag, README pin, release PR) and `speckit-ac upgrade` in Habit Tracker. After
  the upgrade, HT must add its three surface packages; its local DI line may then stay or go (the user decides).
- Packages of the surface projects' project-to-project dependencies (decision 2), and transitive presence.
- Version comparison between the surface and the AC project.
- Automatically adding packages to the AC project, from a script or the main agent.
- Multi-line string literals and multi-line comments in the listing. ilspycmd writes constants on one line; a
  multi-line raw string constant stays a known limit.
- A `doctor` check for package drift.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | The literal stripper mis-parses an exotic literal and hides a real `return` | Real logic sits outside literals, and an unbalanced quote strips at most the rest of one line. The R03 table includes a `return` before a string and a comment |
| 2 | A target's surface has packages that make no sense in the AC project (analyzers that are not `PrivateAssets=all`, build-only tools) | Same rule as init, which already adds them. A wrong case is a new init and check exclusion, discussed when seen |
| 3 | The extra msbuild evaluations slow `export_refs.py` | One evaluation per surface project plus one for the AC project, with no restore; seconds next to the builds |
