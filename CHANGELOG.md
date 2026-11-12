# Changelog

All notable changes to spec-kit-ac are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/). After a release, `master` carries the next `.dev0`
version and an `## [Unreleased]` section until the next release.

## [Unreleased]

_Nothing yet._

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

[Unreleased]: https://github.com/theyur/spec-kit-ac/compare/v0.1.2...master
[0.1.2]: https://github.com/theyur/spec-kit-ac/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/theyur/spec-kit-ac/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/theyur/spec-kit-ac/releases/tag/v0.1.0
