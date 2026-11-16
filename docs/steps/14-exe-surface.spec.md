# Step 14 — An `Exe` project as the AC surface (GitHub issue #16)

**Status:** done (2026-11-16; spec-approved 2026-11-16, `/spec-implement` with the critic on Opus at the user's request; no amendment, plan deviation D1 withdrawn in review 2) · **Tracker row:** 14 · **Source of truth:** `docs/DESIGN.md`

## Goal

Some products are one host project: a worker service or a web API whose `Exe` holds all the logic, with no
library to split out. Today `/speckit-ac-init` proposes only libraries as the AC surface, so such a product
cannot be set up. After this step:

1. libraries are still the default proposal;
2. detection also lists the `Exe` projects, and the user can choose one by hand as the AC surface. The summary
   marks it as a host;
3. the AC project builds against a web host in ref mode (today the implicit `Microsoft.AspNetCore.App`
   framework reference is not copied, so the writer's build fails with CS0012).

The 0.1.4 release is not part of this step.

## Context (inspected 2026-11-16)

- **Detection.** `init_detect.propose()` (`init_detect.py:219–254`) takes as surface candidates only the
  non-test projects whose evaluated `OutputType` is `Library` (`:221`). This follows S05-R03
  (`05-init.spec.md:96`, "the non-test projects that are not executables"). The reason is a scope rule
  (`WORKFLOW.md:27–28`, "Hosts are thin wrappers and stay out of scope"), not an isolation rule. Every
  project's `outputType` is already in the detection JSON (`:178`). `test_detect_solution` (`test_init.py:185`)
  pins that an `Exe` (`App.Cli`) is not a candidate.
- **The command.** `speckit.ac.init.md:47–50`: the AC-surface question asks when there is more than one
  candidate, and a single candidate is only shown in the summary. Nothing says what to do with **no**
  candidate. Summary: `:62–66`.
- **Config.** `init_config.py` takes `--surface` paths as given (`:118`). It never checks the output type, so a
  hand-chosen `Exe` is already accepted there. The guard and `aclib.validate_config` only check paths and
  overlaps.
- **Scaffold.** The AC project references the surface with `ProjectReference` in normal mode and with
  `<refsDir>/*.dll` in ref mode (`templates/ac-project/AcceptanceTests.csproj.template`).
  `init_scaffold.framework_references()` (`init_scaffold.py:73–79`) copies only the **non-implicit**
  `FrameworkReference` items of the surface projects. A `Microsoft.NET.Sdk.Web` project gets
  `Microsoft.AspNetCore.App` implicitly (`IsImplicitlyDefined=true`, probe below), so it is dropped.
- **Export.** `export_refs.export()` builds each surface with `ProduceReferenceAssembly=true` and reads
  `TargetRefPath`. It has nothing specific to libraries.
- **Probe** (scratchpad, not committed; .NET SDK 11.0.100, ilspycmd 11.2, `dotnet new worker` and
  `dotnet new web` on `net11.0`, each with one public class; AC project in the template's form, xUnit v3 on
  VSTest):
  - Both evaluate to `OutputType` `Exe`. The worker has only the implicit `Microsoft.NETCore.App` framework
    reference. The web project also has an implicit `Microsoft.AspNetCore.App`.
  - The reference assembly exists at `obj/Release/net11.0/ref/<name>.dll` and carries
    `ReferenceAssemblyAttribute`, as for a library.
  - Listings: the worker's top-level `Program` is `internal` with a private `Main`, and `public_only()`
    drops it. The web project's `Program` is `public` (the .NET 10+ Web SDK makes it public), and only its
    constructor is kept because `Main` is private. The worker's async state machine (a private nested struct)
    is stripped. `logic_lines`, `friends` and `hidden_lines` find nothing on either listing.
  - **Ref mode:** a step file that uses the worker's public types builds (the surface's
    `Microsoft.Extensions.Hosting` package is in the AC project, as init adds it). A step file that calls the
    web host's `MapGreeting(this IEndpointRouteBuilder)` fails with **CS0012** (`Microsoft.AspNetCore.Routing`
    not referenced) and CS0234. With `<FrameworkReference Include="Microsoft.AspNetCore.App" />` in the AC
    project, it builds.
  - **Normal mode:** the `ProjectReference` to both `Exe` projects builds with no warnings and no errors.
    `dotnet test` passed 4 of 4 (pure methods, the `Worker` constructor, `MapGreeting` on a built
    `WebApplication`). The output also gets each host's `.exe`, `runtimeconfig.json`, `deps.json` and
    `appsettings*.json`. `FrameworkReference` flows through `ProjectReference`, so normal mode needs no
    change.

## Decisions to approve

1. **Libraries stay the default.** `acSurfaceProjects` keeps its meaning: the proposed libraries.
   Detection adds `hostProjects`, the non-test projects whose `OutputType` is `Exe` (any case). They are
   never proposed, only offered for a hand choice. `WinExe` is not offered: desktop hosts need a `-windows`
   target framework and the Windows Desktop framework in the AC project, and neither is verified.
2. **The AC-surface question.**
   - At least one library: ask as today. The summary also lists the `hostProjects` as projects that can be
     chosen instead (information).
   - No library and at least one host: always ask which hosts to use, even when there is only one. The
     question explains that hosts are normally out of scope (WORKFLOW §0), and that the acceptance tests then
     use the host's public types, not its startup.
   - Neither: stop, and say that no project can be the AC surface.
   - A surface value must be one of `acSurfaceProjects` or `hostProjects`. A mix of libraries and hosts is
     allowed. The summary marks each chosen host as "host (`Exe`)".
3. **The scaffold also copies the implicit `Microsoft.AspNetCore.App`.** `framework_references()` returns the
   non-implicit references, as today, plus `Microsoft.AspNetCore.App` when a surface has it implicitly.
   `Microsoft.NETCore.App` stays out. Other implicit framework references, such as the Windows Desktop ones,
   stay out too (decision 1). This also fixes a library built with the Web SDK, which had the same gap.
4. **`export_refs.py` and the guard do not change.** The probe shows that an `Exe` surface exports and checks
   like a library. A committed fixture pins it.
5. **Scope wording.** WORKFLOW §0 keeps "hosts stay out of scope" and adds the exception: a product that is one
   host project may choose that `Exe` as the surface by hand, and its public API is then the surface.

## Requirements

### Detection

- **S14-R01** `init_detect.propose()` returns `hostProjects`: the paths of the non-test projects whose
  `outputType` is `exe` in any case, in the order of `projects`. `acSurfaceProjects` is unchanged. Projects
  with another output type (`WinExe`, empty, …) are in neither list.

### Init command

- **S14-R02** `speckit.ac.init.md`, the AC-surface question and the summary, as decision 2:
  - the three cases (libraries, hosts only, neither) with the stop sentence for the last;
  - the host explanation in the question;
  - only values from `acSurfaceProjects` or `hostProjects` are accepted. Any other answer: say why and ask
    again;
  - the summary marks chosen hosts and lists the hosts not chosen when libraries were proposed;
  - a chosen host's `internalsVisibleTo` files are listed as information, as for a library (step 13).

### Scaffold

- **S14-R03** `init_scaffold.framework_references()` follows decision 3. The order is first seen, and there are
  no duplicates across surfaces (the comparison ignores case).

### Tests

- **S14-R04** Detection (unit, faked evaluation where the existing tests do so):
  - an `Exe`-only solution with a unit-test project gives `acSurfaceProjects == []` and
    `hostProjects == [<exe>]`;
  - a library plus an `Exe` gives the library as a candidate and the `Exe` as a host;
  - `WinExe` and an `Exe` test project are in neither list. `OutputType` `exe` in lower case is a host;
  - `test_detect_solution` (real msbuild) also asserts `hostProjects == ["src/App.Cli/App.Cli.csproj"]`.
- **S14-R05** Config and scaffold:
  - `init_config.py` with `--surface` set to an `Exe` writes the config;
  - `render()` writes its `ProjectReference`;
  - `framework_references()`: an implicit `Microsoft.AspNetCore.App` is kept, an implicit
    `Microsoft.NETCore.App` and an implicit `Microsoft.WindowsDesktop.App` are dropped, explicit ones are kept,
    and two surfaces give no duplicate. The existing `test_packages_order_and_filters` still passes.
- **S14-R06** Export fixture: committed ilspycmd 11.2 listings of a worker and a web host, in the probe's
  form, under `tests/fixtures/exe/`. They hold no local path and no `UserSecretsId`. Through `logic_lines`,
  `check_friends` (no friend), `visible_members(public_only(...))` and `hidden_lines`:
  - no FAIL;
  - the internal `Program` is gone, the public `Program` keeps only its constructor, no `Main` is left, and
    the state machine is gone;
  - every public member of the probe source is kept.
- **S14-R07** Init command text (`test_commands.py`): `hostProjects`, the stop sentence for no candidate, and
  the host mark in the summary.
- **S14-R08** Opt-in end to end (`test_init_e2e.py`, `SPECKIT_AC_DOTNET_E2E=1`, real dotnet, NuGet and
  ilspycmd). There are two cases, each a solution with one host and one unit-test project and no library:
  - a worker (`Microsoft.NET.Sdk.Worker`, the `Microsoft.Extensions.Hosting` package, one public class and
    one `BackgroundService`) on xUnit v3 / VSTest;
  - a web host (`Microsoft.NET.Sdk.Web`, one public static class with an `IEndpointRouteBuilder` extension
    method) on MSTest / Microsoft.Testing.Platform.

  Each case checks:
  - `init_detect.py` gives no candidate and the host in `hostProjects`;
  - `init_config.py` with the host as `--surface`, then `init_scaffold.py` and `init_verify.py`, gives every
    line PASS or SKIP;
  - the API listing in `<refsDir>/api/` has the public class and no `Main`;
  - a step file under the AC project that uses the host's public API builds with `acRefBuildCommand`. For the
    web host, that is a call that needs `Microsoft.AspNetCore.Routing`, which fails before R03.

### Docs

- **S14-R09** `CHANGELOG.md` `## [Unreleased]`:
  - `### Changed`: an `Exe` project may be chosen by hand as the AC surface (#16). Detection lists
    `hostProjects`, libraries stay the default, and init stops when there is neither;
  - `### Fixed`: the AC project gets the implicit `Microsoft.AspNetCore.App` framework reference of a Web SDK
    surface (ref mode failed with CS0012);
  - known limits: `WinExe` is not offered. In normal mode the AC output also gets the host's
    `appsettings*.json`, so a test that builds the host reads the product's configuration.
- **S14-R10** Docs:
  - **`docs/WORKFLOW.md` §0:** the decision 5 text;
  - **`docs/steps/05-init.spec.md:96`:** a note that step 14 adds `hostProjects`;
  - **`docs/DESIGN.md`:** a decision-log row for decisions 1–5;
  - **`docs/steps/TRACKER.md`:** row 14;
  - no local absolute path in any changed file.

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S14-A01 | `uv run pytest -q --tb=short` passes on CPython 3.14 and 3.11 | all |
| S14-A02 | The R04 and R05 tests pass. Each of these mutations fails at least one test: proposing an `Exe` as a candidate; leaving `hostProjects` out; counting `WinExe` as a host; a case-sensitive `exe` compare; dropping the implicit `Microsoft.AspNetCore.App`; copying the implicit `Microsoft.NETCore.App` | R01, R03 |
| S14-A03 | The R06 fixture test passes | decision 4 |
| S14-A04 | The R07 test passes | R02 |
| S14-A05 | Opt-in R08 (`SPECKIT_AC_DOTNET_E2E=1`): both host cases pass. The web case's ref-mode step file fails to build when R03 is reverted | R03, R08 |
| S14-A06 | Changelog, WORKFLOW, 05 spec note, DESIGN and tracker entries exist. No local absolute path in any changed file | R09, R10 |

## Out of scope

- The 0.1.4 release.
- `WinExe` and desktop hosts (WPF, WinForms), and the `-windows` target framework for the AC project.
- Hosting a web app in the acceptance tests with `WebApplicationFactory<Program>`. It needs
  `Microsoft.AspNetCore.Mvc.Testing` in the AC project. The writer reports it as a missing package, and the
  existing tests-write step names it.
- Checking `FrameworkReference` drift in `export_refs.py`. The package drift check (step 10) covers packages
  only, and a surface that later moves to the Web SDK needs the reference added by hand.
- Validating `--surface` in `init_config.py` against detection. The command restricts the choice (R02), and
  a hand-edited config is the user's own.
- The blank line left inside a type after a stripped nested type (cosmetic, any async class).

## Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | An MTP test project referencing an `Exe` behaves differently from VSTest (entry points, `runtimeconfig`) | The web case in R08 runs on MSTest / MTP through `init_verify.py`'s bound scenario |
| 2 | A host's content files (`appsettings.json`) collide with the AC project's own files in the output | The AC template has none. Documented as a known limit (R09) |
| 3 | Copying `Microsoft.AspNetCore.App` changes the scaffold for an existing Web SDK library | That library failed in ref mode as soon as a step used an ASP.NET type. Init writes the AC project once, so existing projects are not changed |
| 4 | The user picks a host when a library exists and loses the library's narrower API | A host is offered only by hand and is marked in the summary. The choice is explicit |
