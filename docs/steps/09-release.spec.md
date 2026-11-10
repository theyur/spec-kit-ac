# Step 9 — Release v0.1.0

**Status:** approved (2026-11-10) · **Tracker row:** 9 · **Source of truth:** `docs/DESIGN.md`

## Goal

Publish spec-kit-ac as `v0.1.0` in its own GitHub repository, `theyur/spec-kit-ac`, so that a project
can install it with one `uv tool install` line. Give the repository the same PR gates as Habit
Tracker:

1. clean the local history before the first push (no project-specific content from the original
   project);
2. push `master`, then bring the release changes in through a PR;
3. CI: pytest on Windows, SonarQube Cloud with coverage, and CodeQL. You request the Copilot review
   yourself;
4. the version bump, the README install line, a changelog, and a tag-driven GitHub Release with the
   wheel and the sdist.

Out of scope:

- PyPI publishing (DESIGN §9: distribution is the git URL);
- changing the commit author email (your git identity stays as recorded);
- Linux/macOS CI (v1.0 targets Windows; memory `v1-target-environment`);
- the opt-in .NET suites in CI (`SPECKIT_AC_DOTNET_E2E=1` needs NuGet, dotnet and spec-kit; they stay
  local and skipped);
- the backlog items (critic model at init, init's spec-input wording) and any new package review
  findings. Those become their own PRs after the release;
- secret scanning, Dependabot and other repository security settings, unless you ask.

## Context (inspected 2026-11-10)

- **GitHub:** `theyur/spec-kit-ac` exists, is **private** and **empty** (no default branch). You chose
  to make it public (2026-11-10).
- **Local repo:** branch `master`, 15 commits, no remote, no tags. The uncommitted change is the
  PR 16 merge note in `TRACKER.md`. `dist/` is git-ignored. `.claude/plans/` is tracked, since the
  tracker links to it.
- **Version:** `0.1.0.dev0` in `pyproject.toml` and `src/speckit_ac/payload/extension.yml`.
  `test_commands.py` asserts that the two match.
- **Install line:** README and DESIGN §9 say `git+https://github.com/<owner>/spec-kit-ac`.
- **Original-project content in the history** (every commit, checked with `git grep` across
  `git rev-list --all`):
  - `docs/reference/WORKFLOW-SETUP-CT.md` was added once (`fa9fb9a`) and never changed. Its §10
    ("This repository (CT)", lines 784–end) holds that project's specifics: project names, sample
    file names, the encoding tables, its hooks and paths. Lines 6 and 9 of its header refer to §10.
  - Absolute paths to the original checkout (its local drive path) appear in 9 files: `CLAUDE.md`,
    `docs/DESIGN.md`, step specs 00, 01, 02, 03 and 05, and plans 02 and 03. (The draft said 11, a
    miscount; corrected after the dry run, plan deviation D4.)
  - Commit hashes in this spec are **pre-rewrite** hashes (`fa9fb9a` is now `d9d9be6`, `843258f` is now
    `1162c7e`).
  - The neutral lint strings in `tests/test_agents.py` (`"CT."`, `"knowledge-base"`) and the
    name→placeholder table in plan 02 (`CT.Core` → `App.Core`) stay. They name nothing beyond what
    WORKFLOW-SETUP §0–9 already says.
- **Habit Tracker's gates** (the model, read 2026-11-10):
  - `.github/workflows/sonar.yml`: the scanner runs in CI. The job skips cleanly while `SONAR_TOKEN`
    is unset, and waits for the quality gate.
  - CodeQL runs as default setup (repository setting, no workflow file).
  - Ruleset `master protect` on the default branch blocks deletion and non-fast-forward pushes, and
    requires the checks `SonarCloud Code Analysis` and `CodeQL`.
  - The user requests Copilot reviews and merges.

## Decisions to approve

1. **History rewrite (your choice, 2026-11-10):** before the first push, rewrite all 15 commits so
   that no commit's tree contains:
   - §10 of the reference doc. It becomes one line: "§10 (choices specific to the original project)
     is not part of this copy." The header lines 6 and 9 are reworded to match;
   - the original checkout's absolute path. Each becomes `<original project>` (for example
     `<original project>\.claude\hooks\guard.py`).

   Commit messages, authors and dates stay the same. Only the commit hashes change, so the hashes
   cited in the tracker and the results files are remapped with the old→new map. `CLAUDE.md` keeps the
   rule "read only, never edit it". The local path moves to a git-ignored `CLAUDE.local.md`, which
   Claude Code loads automatically, so sessions here still find the original project. Before the
   rewrite, a `git bundle` of the old history goes to the scratchpad as a backup, until you confirm.
2. **Branch flow:**
   - push the rewritten `master` as the default branch;
   - make the release changes (R03–R09) on `release/v0.1.0` and open a PR against `master`;
   - you request the Copilot review and merge;
   - tag the merge commit.
3. **Who does what:**
   - **You:**
     - make the repository public;
     - import it into SonarQube Cloud (organization `theyur`) and turn Automatic Analysis off;
     - add the repository secret `SONAR_TOKEN`. I only check that the name exists
       (`gh secret list`), never the value;
     - request Copilot reviews and merge the PR.
   - **Me, each after your OK at that moment:**
     - the history rewrite and the pushes;
     - enabling CodeQL default setup through `gh api`, once the repository is public (code scanning
       on a private personal repository needs a paid plan);
     - creating the ruleset, once each required check has run once (a ruleset can only require check
       names that exist);
     - pushing the tag.
4. **CI on Windows only:** `windows-latest`, CPython 3.11 (the floor) and 3.14 (the dev version),
   through `astral-sh/setup-uv`. The command is `uv run pytest -q --tb=short`, as locally.
5. **Sonar coverage without a new dependency:** CI runs
   `uv run --with coverage coverage run -m pytest` and `coverage xml`. `pyproject.toml` keeps
   `pytest` as its only dev dependency (CLAUDE.md: "Dev-only: pytest"). Sonar analyzes `src/` as
   sources and `tests/` as tests, with Python version 3.11.
6. **The release is built by a workflow** on a `v*` tag push, not on this machine:
   - check that the tag, `pyproject.toml` and `extension.yml` carry the same version;
   - run the tests;
   - `uv build`;
   - `gh release create` with the wheel, the sdist, and the matching `CHANGELOG.md` section as notes.

   A version mismatch fails the job before anything is published.
7. **Install line:** pinned to the tag:
   `uv tool install speckit-ac --from git+https://github.com/theyur/spec-kit-ac@v0.1.0`. The README
   also shows the unpinned form for the latest `master`.

## Requirements

### History and first push

- **S09-R01 Backup:** before the rewrite, create `git bundle create <scratchpad>/s9/pre-rewrite.bundle
  --all`, and check that `git bundle verify` passes.
- **S09-R02 Rewrite** (decision 1): every commit reachable from `master` gets the edited files. Then:
  - `git grep` over every rewritten commit finds no absolute path to the original checkout (either slash) and no §10 heading;
  - `git diff <old HEAD> <new HEAD>` touches only the planned files;
  - the old→new hash map is saved next to the bundle;
  - the suite passes on the new `HEAD`;
  - a scan of every commit for secret-shaped strings (private keys, tokens, password assignments) finds
    nothing. The scan reports file names and counts only, never matches.
- **S09-R03 Local path note:** `CLAUDE.local.md` (git-ignored; a new `.gitignore` entry) holds the
  original project's path and the "read only" rule. `CLAUDE.md` refers to "the original project"
  without a path.
- **S09-R04 First push:** `git push -u origin master`. The GitHub default branch is `master`.

### Release changes (`release/v0.1.0`, PR to `master`)

- **S09-R05 Version:** `0.1.0` in `pyproject.toml` and `extension.yml`; `uv.lock` refreshed.
  `speckit-ac --version` prints `speckit-ac 0.1.0`.
- **S09-R06 CI workflow** `.github/workflows/ci.yml`:
  - triggers: push to `master`, pull requests, manual runs;
  - permissions: `contents: read`; concurrency per ref;
  - a matrix job `test (3.11)` / `test (3.14)` on `windows-latest`: checkout, setup-uv with the
    matrix Python, `uv sync --locked`, then the pytest command;
  - every third-party action is pinned to a released major version that has been checked to exist.
- **S09-R07 Sonar workflow** `.github/workflows/sonar.yml`, the same pattern as Habit Tracker's:
  - skip with a notice while `SONAR_TOKEN` is unset;
  - full-depth checkout;
  - coverage per decision 5;
  - the SonarSource scan action with organization `theyur` and project key
    `theyur_spec-kit-ac`. Both can be overridden by repository variables;
  - `sonar.qualitygate.wait=true`. The settings live in `sonar-project.properties`;
  - the header comment lists the one-time setup steps (yours, decision 3).
- **S09-R08 Release workflow** `.github/workflows/release.yml` (decision 6):
  - trigger `push` of tags `v*`;
  - permissions: `contents: write`;
  - it fails before publishing when the versions differ or the tests fail.
- **S09-R09 Docs:**
  - **README:** the install section uses the decision 7 lines (no `<owner>`). The status line says
    v0.1.0 is released. A "Contributing / PR flow" note: PRs against `master`, CI + Sonar + CodeQL
    must pass, Copilot review on request.
  - **DESIGN §9:** the real URL, plus a decision-log row for this step (rewrite, gates,
    release-by-workflow).
  - **`CHANGELOG.md`** (new): a `## [0.1.0] - <date>` section summarising the features. The release
    workflow uses it.
  - **Tracker:** row 9 and its notes (including the PR 16 note that is uncommitted now).
- **S09-R10 Tests for the release files** (`tests/test_release.py`):
  - the three workflows parse as expected: required keys, triggers, the matrix, no `@main` or
    unpinned actions, and least-privilege permissions;
  - the release workflow's version check compares `pyproject.toml`, `extension.yml` and the tag
    name;
  - `CHANGELOG.md` has a section for the package version;
  - the README install line names the package version's tag;
  - stdlib only: no YAML library, the checks read the text. A version-check helper script is
    tested directly.

### Gates and release

- **S09-R11 CodeQL:** default setup enabled (decision 3), with the languages GitHub detects (expected:
  `actions`, `python`). It runs on the PR.
- **S09-R12 Ruleset** `master protect`, as in Habit Tracker:
  - deletion and non-fast-forward blocked on the default branch;
  - required checks: `SonarCloud Code Analysis`, `CodeQL`, `test (3.11)`, `test (3.14)`.

  It is created after the PR has run each check once and before you merge.
- **S09-R13 Tag and release:** after the merge, an annotated tag `v0.1.0` on the merge commit
  (`git tag -a v0.1.0 -m "spec-kit-ac 0.1.0"`), then push it. The release workflow publishes the
  GitHub Release with `speckit_ac-0.1.0-py3-none-any.whl` and `speckit_ac-0.1.0.tar.gz`.
- **S09-R14 Install from GitHub:**
  - `uvx --isolated --from git+https://github.com/theyur/spec-kit-ac@v0.1.0 speckit-ac --version`
    prints `speckit-ac 0.1.0`;
  - in Habit Tracker, after `uv tool install --reinstall` from the same URL and `speckit-ac upgrade`,
    `speckit-ac doctor` reports 0 FAIL;
  - the Habit Tracker change (only the deploy manifest's version and the extension files) is left
    uncommitted there for you to decide.

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S09-A01 | Bundle verifies. The new history has 15 commits with the same messages and authors. `git grep` over all commits finds no absolute path to the original checkout and no §10 heading. The secret-shape scan finds nothing | R01, R02 |
| S09-A02 | `uv run pytest -q --tb=short` passes on the rewritten `HEAD` and on the release branch, on CPython 3.14 and 3.11 | R02, R05, R10 |
| S09-A03 | `CLAUDE.local.md` is ignored (`git check-ignore`), and `CLAUDE.md` has no absolute path to the original project | R03 |
| S09-A04 | `origin/master` equals the rewritten local `master`; the default branch is `master` | R04 |
| S09-A05 | On the PR, `test (3.11)`, `test (3.14)`, `SonarCloud Code Analysis` and `CodeQL` all pass on the head SHA | R06, R07, R11 |
| S09-A06 | The ruleset exists with the four required checks; a direct push to `master` would be refused (read from the ruleset, not tried) | R12 |
| S09-A07 | The Release `v0.1.0` exists with the two artifacts, and its notes match the changelog section | R08, R13 |
| S09-A08 | The install from the tag prints `0.1.0`; Habit Tracker's `doctor` reports 0 FAIL after the upgrade | R14 |

## Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Tests that pass here fail on the GitHub runner (paths, a different PowerShell, git config, no `specify`) | The first CI run shows it. Fix in the PR with a regression test; never skip a test only for CI without your OK |
| 2 | The rewrite edits a file in a way that breaks an old commit's tests | Only `HEAD`'s suite is required. Old commits are history, not releases. The bundle keeps the original |
| 3 | The Sonar quality gate fails on existing code (new-code period = whole project on the first analysis) | Report the findings; fix what's real in the PR; any gate or rule change is yours |
| 4 | CodeQL flags existing Python (for example path handling in the scripts) | Same: fix what's real, with a test; dismissals are yours |
| 5 | The SonarSource scan action on Windows behaves differently from Linux | If it fails, run the Sonar job on `ubuntu-latest`, with coverage produced there (the tests that need Windows are then listed and decided with you) |
