# Changelog

All notable changes to spec-kit-ac are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/). After a release, `master` carries the next `.dev0`
version and an `## [Unreleased]` section until the next release.

## [0.1.4] - 2026-11-16

### Fixed

- The raw test results `specs/*/ac/runs/**/ac-results.trx` are git-ignored. A TRX file holds the user's login, the
  machine name and local paths; only the cleaned `ac-results.md` is a run record (#19).
- `ac-results.md` holds no absolute local path any more (#18):
  - paths below the project root (a worktree included) are written repo-relative, for example
    `tests/App.AcceptanceTests/StepDefinitions/…:line 42`;
  - every other Windows drive or UNC path becomes `[external path]`. That covers the user profile, the NuGet
    cache, SDK folders and a network share.
- The test writer and the judge can read and search only the API listings in `<refsDir>/api/`. They can no longer
  Grep the reference DLLs beside them, which confirmed guessed type names (#17).
- `speckit-ac doctor` advises `speckit-ac upgrade` for a missing `.gitignore` / `.gitattributes` block. Re-running
  `/speckit-ac-init` only verifies, so the old advice did not help.
- `export_refs.py` no longer fails on members that reference assemblies keep even without `InternalsVisibleTo`:
  `internal virtual` and `internal abstract` members, internal members of a public interface, and a public
  struct's `internal` and `private` fields. The listing drops them.
- `/speckit-ac-init` copies the implicit `Microsoft.AspNetCore.App` framework reference of a Web SDK surface into the
  AC project. Before, the writer's ref-mode build failed with CS0012 as soon as a step used an ASP.NET Core type.

### Changed

- `speckit-ac upgrade` refreshes the managed blocks in `.gitignore` and `.gitattributes` when
  `.workflow/config.json` exists. Only the text between the markers changes. `doctor` warns when a block is out of
  date.
- An AC surface project may use `InternalsVisibleTo` for its own unit tests (#15). `/speckit-ac-init` shows it as
  information instead of stopping. `export_refs.py`:
  - writes into the API listing only the members that code outside the assembly can use (public, protected,
    protected internal). Internal, private and private protected members and accessors go, with their
    attributes and bodies, and so do the `[assembly: InternalsVisibleTo(...)]` lines;
  - fails when a friend assembly is the AC project's own assembly (its `AssemblyName`, any case, any public key);
  - fails when anything hidden is still left after the filter, or when the friend lines can't be read;
  - removes the refs folder after any failure once it has started, so no unchecked DLL is left for the ref-mode
    build.

  The testability text that init offers for the constitution now reads "`InternalsVisibleTo` never names the AC
  assembly".
- An `Exe` project (a worker service, a web API) may be the AC surface, chosen by hand, for a product that is one
  host project (#16). `/speckit-ac-init` still proposes only libraries:
  - detection lists the `Exe` projects as `hostProjects`;
  - with no library it always asks which host to use, and with neither it stops;
  - the summary marks a chosen host as "host (`Exe`)";
  - it asks for the target framework again when the chosen projects need a higher one than proposed.

### Known limits of the path cleaning

- POSIX paths other than the project root stay as they are; most are routes (`/api/users/42`). So do MSYS forms
  such as `/c/Users/…`.
- An external path hides up to its last separator on the line. Words between two such paths can be hidden too,
  while words after the last separator stay. For example, `C:\Users\First Last` keeps `Last`, and a file name
  with a space keeps its tail. The same goes for a path with mixed separators, a path with an unclosed quote, and
  a drive path glued to a word (`dirC:\…`).
- JSON-escaped UNC paths (`\\\\server\\share`) and long-path UNC forms (`\\?\UNC\…`) are not recognised.
- A sibling folder whose name is the root plus a space (`repo 2`) gives `. 2\…`.

### Known limits of the API listing

- With `InternalsVisibleTo`, internal member names (no bodies) stay in the reference DLLs. Only the compiler
  reads those; the writer and the judge cannot. A guessed internal name gives CS0122 rather than CS0117, which
  tells the writer that the name exists. The same was already true of internal types.
- A public type that implements an internal interface still names it, in its base list and in its explicit
  implementations (`void IInner.M()`). That holds with or without `InternalsVisibleTo`.
- A DLL that mentions `InternalsVisibleToAttribute` without granting any friend fails the export with "shows no
  friend line". This happens, for example, when a public API uses the attribute type. The check is a byte
  search, not a metadata read, so it fails closed rather than trusting a listing that may have lost its friend
  lines.

### Known limits of an `Exe` surface

- `WinExe` projects (WPF, WinForms) are not offered; they need a `-windows` target framework in the AC project.
- In normal mode the AC project's output also gets the host's `appsettings*.json`, so a test that builds the host
  reads the product's configuration.

### Upgrade

- Run `speckit-ac upgrade` in existing installs. It adds the TRX line to the `.gitignore` block.
  - It stops before any change, and names the file, when `.gitignore` or `.gitattributes` is not UTF-8 or holds
    a broken block.
- Init writes the AC project once, so an existing AC project with a Web SDK surface does not get the framework
  reference: add `<FrameworkReference Include="Microsoft.AspNetCore.App" />` to it by hand if its steps need ASP.NET
  Core types.
- Untrack TRX files that are already committed with `git rm --cached -- "specs/*/ac-results.trx"`, then commit.
  Git history keeps them.
- `ac-results.md` files written before the upgrade are not rewritten.

## [0.1.3] - 2026-11-14

### Fixed

- `export_refs.py` no longer reads a multi-line string literal (verbatim `@"…"`, raw `"""…"""`) or a multi-line
  `/* … */` comment as logic. A keyword such as `return` or `if (` on a later line of one used to fail the logic
  check with "the listing contains logic, not only stubs" (#9).
- The `/speckit-ac-*` skills show their argument hint in Claude Code's autocomplete again. spec-kit drops
  `argument-hint` when it renders the skills; install and upgrade now copy it from each command (#10).
  `speckit-ac doctor` warns when a skill lacks it.

### Changed

- `/speckit-ac-critic`: the critic sub-agent replies with the full pass summary (verdict, counts, one line per
  MAJOR and MINOR note), so its own window shows the findings even when the host collapses the main agent's
  mid-turn text (#11).

### Upgrade

- Run `speckit-ac upgrade` in existing installs to get the argument hints and the new critic reply.

## [0.1.2] - 2026-11-12

### Fixed

- `export_refs.py` no longer reports return-value attributes such as `[return: NotNullIfNotNull("name")]` as
  logic in a reference-assembly listing. Any nullability contract on a return value used to fail the export.
- `export_refs.py` ignores keywords inside string and char literals and comments, for example a public
  `const string` that contains "return".

### Changed

- `export_refs.py` (the start of `/speckit-ac-translate` phase 2 and `/speckit-ac-tests-write`) first checks
  that the AC project still references every package of the AC surface projects that is not implicit or
  `PrivateAssets=all`.
  - `/speckit-ac-init` adds these packages once. A package the surface gains later was missing in ref mode,
    which compiles against the reference assemblies only, so the writer's build failed (for example
    `ServiceCollection` not found).
  - The check fails before anything is built and prints the `dotnet add` line for each missing package. It
    never edits the AC project.
- `/speckit-ac-tests-write`: when the writer reports missing packages, the command names the next step: add
  them to the AC project, then run the command again without `fresh`.

**Upgrading:** a project whose AC surface gained packages after `/speckit-ac-init` now stops at
`export_refs.py` until the listed packages are added to the AC project.

## [0.1.1] - 2026-11-11

### Changed

- `/speckit-ac-critic` shows a pass summary after every pass, before it verifies anything: the verdict,
  the counts, and one line per MAJOR and MINOR note. Its finish report lists every note with its
  outcome (fixed, partly fixed, rejected with the reason, or open). Before, the user often saw only the
  verdict and the counts.

## [0.1.0] - 2026-11-10

First release. Tested on Windows with uv, PowerShell 7, spec-kit 1.0.2 (`--script ps`) and
interactive Claude Code; first used in a real project (Habit Tracker).

### Added

- `speckit-ac` CLI: `install`, `uninstall`, `upgrade` and `doctor`. It checks the prerequisites, adds
  the spec-kit extension `ac`, and deploys the Claude-side files:
  - the three AC agents;
  - the guard registration in `.claude/settings.json`;
  - human-only `speckit-ac-*` skills;
  - a marked `CLAUDE.md` block;
  - a hashed deploy manifest.

  An install followed by an uninstall leaves the project byte for byte as it was.
- `/speckit-ac-init`: once per project, it detects the solution, the test framework and the runner,
  and asks only what it can't detect. It writes `.workflow/config.json`, scaffolds the Reqnroll
  acceptance-test project (xUnit v2/v3, NUnit, MSTest on VSTest or Microsoft.Testing.Platform), and
  verifies the setup. `smoke` runs the live guard smoke test.
- `/speckit-ac-translate`: drafts and locks `acceptance.md` per feature, then translates it into
  tagged Reqnroll `.feature` files. Every acceptance item gets a scenario or is recorded as skipped.
- `/speckit-ac-tests-write`: writes step definitions in isolation, from the spec, the acceptance
  criteria and reference assemblies only.
- `/speckit-ac-tests-analyze`: runs the AC tests of every feature and judges each failure
  (`TRANSLATION_FAULT`, `TEST_FAULT`, `IMPLEMENTATION_FAULT`, `SPEC_AMBIGUITY`, `UNEXPRESSIBLE`,
  `SUPERSEDED`).
- `/speckit-ac-critic`: independent critic review of a spec, plan, tasks, acceptance criteria or
  feature files.
- A fail-closed `PreToolUse` guard that enforces the isolation:
  - per-role read and write rules;
  - fixed subagent prompts;
  - the active-run marker;
  - content-hash locks.
- An end-to-end sample with a planted implementation bug and a contradicting second feature
  (`tests/e2e/`).

[0.1.4]: https://github.com/theyur/spec-kit-ac/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/theyur/spec-kit-ac/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/theyur/spec-kit-ac/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/theyur/spec-kit-ac/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/theyur/spec-kit-ac/releases/tag/v0.1.0
