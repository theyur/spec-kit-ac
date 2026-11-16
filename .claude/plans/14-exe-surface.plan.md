# Plan — Step 14: an `Exe` project as the AC surface (GitHub issue #16)

Spec: `docs/steps/14-exe-surface.spec.md` (spec-approved 2026-11-16). Critic: `plan-critic` on Opus (user's
request), up to 3 rounds.

## Facts observed (repository and probe, 2026-11-16)

- `init_detect.propose()` (`init_detect.py:219–254`): `candidates` = non-test projects with `outputType` `library`
  (`:221`). The target-framework fallback, used when no test project gives a common runnable TFM, takes the highest
  runnable TFM of `candidates` (`:239–243`). Its reason text says "the surface candidates target only netstandard".
- The proposal is read only by the init command, by `init_detect.blockers()` / `detect()` (`acProjectDir`,
  `testFramework`: `:269–290`), and by tests (`test_init.py`, `test_init_e2e.py`, `test_e2e_sample.py`). Nothing reads
  the key set as a whole, so a new key breaks no consumer (grep `proposal`).
- `project_facts()` in `test_init.py:128` builds fake project facts for `propose()` unit tests (no dotnet).
- `init_config.py:118` writes `--surface` values as given. There is no output-type check (verified by reading
  `build()` `:91–131`).
- `init_scaffold.framework_references()` (`:73–79`): non-implicit ids, deduplicated by exact id, first-seen order.
  The callers are `main()` (`:164`) and `test_packages_order_and_filters` (`test_init.py:399–408`, which expects
  `["Microsoft.AspNetCore.App"]` from an explicit AspNetCore plus an implicit NETCore.App).
- `init_verify.py` already runs the export (`[4]`), the ref-mode build (`[5]`), the normal-mode build (`[1]`, `[5]`)
  and a bound scenario (`[7]`). Its own files never use a surface type, so a missing framework reference shows only
  when a step file uses a host type (hence the R08 step file).
- `tests/initproject.make_solution()` writes a library `src/App.Core` and optionally `tests/App.Tests`. Its csproj
  helper is `Microsoft.NET.Sdk` only.
- Probe (scratchpad `exe/`, SDK 11.0.100, ilspycmd 11.2): the facts in the spec's Context. Also, the fixture filters
  run clean on both listings (`exe_listing.py`): `logic_lines` = [], `friends` = [], `hidden_lines` = [] after
  `visible_members(public_only(...))`.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| 1 | Nothing besides the init command consumes `proposal` as a whole, so adding `hostProjects` is compatible | 0.95 | A consumer breaks on the new key | grep done (Facts); full suite |
| 2 | A `ProjectReference` from the AC project to an `Exe` builds and runs for every recipe, not only the probed xUnit v3 / VSTest | 0.8 | Normal mode fails for some recipes | R08 runs MSTest / MTP as the second recipe; the other 5 recipes are not run (gap, reported) |
| 3 | The Web SDK's implicit `Microsoft.AspNetCore.App` is the only implicit framework reference to copy | 0.8 | Another SDK (Razor, Blazor WASM, Windows Desktop) needs one too | Razor class libraries declare AspNetCore explicitly (copied as today); desktop is out of scope (spec decision 1) |
| 4 | An `Exe` listing has the same shape as a library's for the export filters | 0.9 | The export fails or leaks on a host | R06 fixture and R08 real run |
| 5 | ~~Dropping an explicit `Microsoft.NETCore.App`~~ withdrawn (review 1, F1): explicit references are copied as today, whatever their id | — | — | — |
| 6 | `hostProjects` in the target-framework fallback (D1) is wanted | 0.8 | The user is asked for a TFM that could have been detected | See D1; it only adds a proposal when the old code had none |

## Deviations from the spec (for the critic and the user)

- ~~D1~~ **withdrawn (review 2, F1).** `propose()`'s target-framework fallback stays as it is (libraries only). The
  command's target-framework rule (step 2) covers a host surface instead, so the spec has no deviation.

## Steps

1. **Detection (S14-R01).** `init_detect.py`:
   - in `propose()`, add `hosts = [p for p in projects if not p["isTestProject"] and p["outputType"].lower() == "exe"]`
     and the key `"hostProjects": [p["path"] for p in hosts]` right after `acSurfaceProjects`;
   - the TFM fallback is unchanged (D1 withdrawn);
   - module docstring: "proposals for every config value (libraries as the AC surface, `Exe` projects as hosts the
     user may choose by hand)".
2. **Init command (S14-R02).** `speckit.ac.init.md` setup step 2, the AC-surface item becomes:
   - "**AC surface** (`proposal.acSurfaceProjects`, the libraries): the projects whose public API the acceptance
     tests use. Ask when there is more than one candidate; a single candidate is only shown in the summary.";
   - sub-bullet: "No candidate, and `proposal.hostProjects` is not empty: always ask which hosts to use, even when
     there is only one. Hosts (`Exe` projects) normally stay out of scope; with a host as the surface, the
     acceptance tests use its public types, not its startup.";
   - sub-bullet: "No candidate and no host: stop. No project can be the AC surface (every project is a test project
     or has another output type).";
   - sub-bullet: "Accept only projects from `acSurfaceProjects` or `hostProjects`; several, libraries and hosts
     mixed, are fine. For any other answer say why and ask again.";
   - the existing `internalsVisibleTo` sentence stays, with "(a library or a host)".
   - Step 3 summary: "AC surface projects (mark each chosen host as "host (`Exe`)"; when libraries were proposed, also
     list the `hostProjects` not chosen, as projects that can be chosen instead)".
   - Step 3's "Any change: update the value" is unchanged; the accept rule above applies to a changed surface too
     ("also when the user changes the surface at the summary").
   - **Target framework** item (`:56`) gains (review 1, F6; reworded after review 2, F1): "Also ask when the chosen
     surface is not `proposal.acSurfaceProjects` and `proposal.targetFramework` is lower than the highest runnable
     `netX.Y` in a chosen project's `targetFrameworks` (from `projects`): the AC project could not reference it.
     Offer that highest one."
3. **Scaffold (S14-R03).** `init_scaffold.py`:
   ```python
   # Implicit framework references the AC project needs too: the Web SDK adds Microsoft.AspNetCore.App implicitly,
   # and ref mode compiles against the surface's ASP.NET Core types. Microsoft.NETCore.App (every project) and the
   # Windows Desktop ones (not supported) stay out.
   IMPLICIT_KEPT = {"microsoft.aspnetcore.app"}

   def framework_references(surface):
       refs, seen = [], set()
       for project in surface:
           for ref in project["frameworkReferences"]:
               key = ref["id"].lower()
               if key in seen or (ref["implicit"] and key not in IMPLICIT_KEPT):
                   continue
               seen.add(key)
               refs.append(ref["id"])
       return refs
   ```
   Explicit references are copied as today, whatever their id (review 1, F1). Docstring line: "framework
   references: the surface's non-implicit ones and an implicit `Microsoft.AspNetCore.App`".
4. **Unit tests (S14-R04, R05, R07).**
   - `test_init.py`:
     - `test_propose_hosts` (fake facts): Exe-only plus a unit test gives `acSurfaceProjects == []` and
       `hostProjects == ["src/H/H.csproj"]`; library plus Exe gives each in its list; `WinExe`, an empty output type
       and an `Exe` test project are in neither; `outputType` `exe` (lower case) and `EXE` are hosts; the order
       follows `projects`;
     - `test_propose_target_framework` is unchanged (D1 withdrawn);
     - `test_detect_solution`: assert `proposal["hostProjects"] == ["src/App.Cli/App.Cli.csproj"]`;
     - `test_framework_references` (parametrized table): implicit AspNetCore kept; implicit NETCore.App dropped;
       explicit NETCore.App kept (as today); implicit `Microsoft.WindowsDesktop.App` dropped; explicit
       WindowsDesktop kept; two surfaces with `Microsoft.AspNetCore.App` and `microsoft.aspnetcore.app` give one
       (first spelling); first-seen order across surfaces;
     - `test_config_accepts_an_exe_surface`: write a real `src/App.Host/App.Host.csproj` with `OutputType Exe`
       (`Microsoft.NET.Sdk.Web`) in tmp (review 1, F5: pins the intent if an output-type check is ever added);
       `init_config.py` with `--surface src/App.Host/App.Host.csproj` writes it; `render()` with that config has
       `<ProjectReference Include="../../src/App.Host/App.Host.csproj" />` in the normal-mode group, and the given
       framework reference.
   - `test_commands.py` `test_init_offers_hosts_by_hand`: `hostProjects`, "always ask which hosts to use", the stop
     sentence, "host (`Exe`)", "Accept only projects from `acSurfaceProjects` or `hostProjects`", and the TFM
     sentence for a surface that is not the proposal.
5. **Export fixture (S14-R06).**
   - Regenerate the probe without `UserSecretsId` (remove it from the worker csproj, rebuild, list with ilspycmd
     11.2), and normalise to LF.
   - Commit `tests/fixtures/exe/worker.source.cs.txt` (Program, Pricing, Worker), `worker.listing.cs.txt`,
     `web.source.cs.txt` (Program, Greeting) and `web.listing.cs.txt`.
   - Check that neither listing holds a drive or UNC path or `UserSecretsId`, by test and before the commit.
   - `test_scripts.py` `test_real_exe_listings` (parametrized worker / web), with its own loader for
     `fixtures/exe` (not `filtered_fixture()`, which reads `fixtures/ivt` and asserts no blank line after `{`; the
     stripped state machine leaves one, out of scope; review 1, F3):
     - `logic_lines` = [];
     - `check_friends(dll, listing, "App.AcceptanceTests", project)` returns with a fake DLL whose bytes lack the
       attribute (tmp file);
     - after `visible_members(public_only(...))`, `hidden_lines` = [];
     - no line contains `Main(`;
     - explicit lists (review 1, F4). Worker: kept `public static class Pricing`, `public static long
       ToCents(decimal amount)`, `public class Worker : BackgroundService`, `public Worker(ILogger<Worker> logger)`,
       `protected override Task ExecuteAsync(CancellationToken stoppingToken)`; gone `class Program`, `Main(`,
       `struct <ExecuteAsync>d__` (the declaration; the `[AsyncStateMachine(typeof(<ExecuteAsync>d__2))]` attribute
       on the kept method stays, as the probe listing shows; review 2, F2), `Decimals`. Web: kept `public class Program`, `public Program()`, `public static class Greeting`,
       `public static string Hello(string name)`, `public static IEndpointRouteBuilder MapGreeting(this
       IEndpointRouteBuilder routes)`; gone `Main(`; the `Program` body holds only the constructor;
     - the listings have no drive / UNC path and no `UserSecretsId`.
6. **Opt-in e2e (S14-R08).**
   - `tests/initproject.py`: add an `sdk="Microsoft.NET.Sdk"` parameter to `csproj()` (review 1, F7). Split the
     spec-kit and payload part of `make_solution` into `_project_base(base, runner)`; `make_solution`'s signature and
     the files it writes stay byte-identical (the existing detect and e2e tests confirm it). Add
     `make_host_solution(base, kind, framework, runner)`:
     - `src/App.Host/App.Host.csproj` with `Microsoft.NET.Sdk.Worker` and `dotnet add package
       Microsoft.Extensions.Hosting` (worker), or `Microsoft.NET.Sdk.Web` (web);
     - sources as in the probe (namespace `App.Host`);
     - `tests/App.Tests` referencing the host, with the recipe's packages added by `dotnet add package` and one unit
       test per framework that calls `Pricing.ToCents` (worker) or `Greeting.Hello` (web);
     - `App.slnx` and the git commit.
   - `test_init_e2e.py` `test_init_with_a_host_surface`, parametrized `("worker", "xunit3", "vstest")` and
     `("web", "mstest", "mtp")`:
     - `init_detect.py` gives `acSurfaceProjects == []` and `hostProjects == ["src/App.Host/App.Host.csproj"]`;
     - `init_config.py` with the host as `--surface`, then `init_scaffold.py`;
     - the web case's csproj has the AspNetCore framework reference;
     - `init_verify.py` gives every line PASS or SKIP, and `PASS [7] results: bound scenario passed`;
     - `<refsDir>/api/App.Host.cs` has `class Pricing` or `class Greeting` and no `Main(`;
     - then write `StepDefinitions/HostProbe.cs`: worker, a public static method that returns
       `new App.Host.Worker(NullLogger<App.Host.Worker>.Instance)`; web, one that takes an `IEndpointRouteBuilder`
       and returns `App.Host.Greeting.MapGreeting(routes)`;
     - `acRefBuildCommand` exits 0.
7. **Docs (S14-R09, R10).**
   - **`CHANGELOG.md` `[Unreleased]`:**
     - Changed bullet for #16;
     - Fixed bullet for the framework reference;
     - a new `### Known limits of an Exe surface` with the `WinExe` and `appsettings` lines;
     - the Upgrade section gets one line: existing AC projects are not changed, so a Web SDK surface needs
       `<FrameworkReference Include="Microsoft.AspNetCore.App" />` added to the AC project by hand.
   - **`docs/WORKFLOW.md` §0:** "AC tests target the core library API (the "AC surface", chosen at init), not hosts
     such as a CLI, web API, worker or UI. Hosts are thin wrappers and stay out of scope. The exception is a product
     that is one host project: init lists the `Exe` projects, the user may choose one by hand, and its public API is
     then the surface (not its startup)."
   - **`docs/steps/05-init.spec.md:96`:** append "(Step 14: `Exe` projects are listed as `hostProjects` and may be
     chosen by hand.)".
   - **`docs/DESIGN.md`:** a decision-log row for step 14 (decisions 1–5, D1).
   - **`docs/steps/TRACKER.md`:** row 14 (status, plan, verification) and step 14 notes.
   - **Spec status:** done.
8. **Verification.**
   - Narrow first: `test_init.py`, `test_commands.py`, `test_scripts.py -k exe`.
   - Then the full suite on 3.14, and on 3.11 (`--basetemp` on C:). Restore `.venv` with `uv sync -q --python 3.14`
     afterwards.
   - Mutations, each must fail a test (S14-A02):
     - `exe` → `library` candidates (Exe proposed);
     - `hostProjects` removed;
     - `WinExe` counted as a host;
     - a case-sensitive `== "Exe"`;
     - the AspNetCore exception removed (`IMPLICIT_KEPT` empty);
     - copying the implicit `Microsoft.NETCore.App` (add it to `IMPLICIT_KEPT`; the "implicit NETCore.App dropped"
       row must kill it; review 1, F2).
   - Opt-in: `SPECKIT_AC_DOTNET_E2E=1` on `test_init_e2e.py` (the 7-pair matrix and both host cases) and
     `test_e2e_sample.py`.
   - A05: revert R03 locally, so the web case's ref-mode step file fails to build, then restore it.
   - Path scan of the diff for drive / UNC paths.

## Review dispositions

### Round 1 (`14-exe-surface.review-1.md`, REVISE: 0 BLOCKER, 1 MAJOR, 6 MINOR)

| # | Severity | Disposition | Edit |
|---|---|---|---|
| F1 | MAJOR | ACCEPTED | Step 3: no `BASE_FRAMEWORK`; explicit references copied as today, whatever their id. Assumption 5 withdrawn; the test row "explicit NETCore.App kept". No new deviation |
| F2 | MINOR | ACCEPTED | Step 8: the mutation adds `Microsoft.NETCore.App` to `IMPLICIT_KEPT` |
| F3 | MINOR | ACCEPTED | Step 5: an own loader for `fixtures/exe`, no blank-line asserts |
| F4 | MINOR | ACCEPTED | Step 5: explicit kept / gone lists |
| F5 | MINOR | ACCEPTED | Step 4: a real `OutputType Exe` csproj at the surface path |
| F6 | MINOR | ACCEPTED | Step 2: the command also asks for the TFM when there are no unit tests and the chosen surface is not the proposal; D1 notes it; step 4's command test pins it |
| F7 | MINOR | ACCEPTED | Step 6: `sdk=` parameter on `csproj()`; `make_solution` byte-identical |

### Round 2 (`14-exe-surface.review-2.md`, APPROVE: 0 BLOCKER, 0 MAJOR, 2 MINOR)

| # | Severity | Disposition | Edit |
|---|---|---|---|
| F1 | MINOR | ACCEPTED | D1 withdrawn (no spec deviation left); step 2's TFM rule keyed on the TFM itself: ask when the chosen surface is not the proposal and the proposed TFM is lower than a chosen project's highest runnable one (null is already asked). Step 4 test unchanged for `propose()` |
| F2 | MINOR | ACCEPTED | Step 5: assert the state machine's declaration is gone (`struct <ExecuteAsync>d__`); the probe listing keeps the `[AsyncStateMachine(...)]` attribute line |
