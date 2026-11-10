# Changelog

All notable changes to spec-kit-ac are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/). After a release, `master` carries the next `.dev0`
version and an `## [Unreleased]` section until the next release.

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

[0.1.0]: https://github.com/theyur/spec-kit-ac/releases/tag/v0.1.0
