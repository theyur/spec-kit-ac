# Step 15 — Release 0.1.4

**Status:** spec-approved (2026-11-16; the user approved it with decision 1 reworded and asked to start the release PR) · **Tracker row:** 15 · **Source of truth:** `docs/DESIGN.md` §9

## Goal

Publish spec-kit-ac **0.1.4**, made of steps 12–14 (GitHub issues #15–#19, milestone `v0.1.4`), as the 0.1.2 and
0.1.3 releases were done. Then move `master` to the next `.dev0`.

This step adds no feature and no fix. It changes only version fields, the changelog, the README and the tracker.

## Context (inspected 2026-11-16)

- **Version rule** (DESIGN §9, `docs/DESIGN.md:165–176`):
  - a `vX.Y.Z` tag on `master` runs `.github/workflows/release.yml`;
  - the workflow checks that the tagged commit is on `master`, and that the tag, `pyproject.toml` and
    `extension.yml` carry the same final version. It then runs the tests, builds, and creates the GitHub Release
    with the wheel, the sdist and the changelog section as notes;
  - a tag is never moved;
  - after a release, `master` moves to the next `.dev0` with an `## [Unreleased]` section, and the README pins the
    newest dated changelog version.
- **Today:** `pyproject.toml:3` and `src/speckit_ac/payload/extension.yml:6` say `0.1.4.dev0`.
  - `CHANGELOG.md` `## [Unreleased]` holds steps 12–14. Its sections are Fixed, Changed, three "Known limits"
    sections and Upgrade. The compare link is `v0.1.3...master`.
  - The README pins `@v0.1.3` and says "Status: v0.1.3 released".
  - `tests/test_release.py` pins two things. `test_changelog_has_the_newest_release_and_its_notes`: a final
    version must equal the newest dated changelog section. `test_readme_pins_the_newest_release`: the README
    install line names it.
- **The 0.1.3 pattern** (commits `aa16c04`, `8618e62`):
  - release PR 13 on `release/v0.1.3`, with a version bump, `uv.lock` regenerated, the changelog section dated
    with its compare link, and the README status and install pin;
  - after the merge, tag `v0.1.3` on the merge commit `9c98b28`;
  - the release run passed, and `uvx --isolated --from git+…@v0.1.3 speckit-ac --version` printed `0.1.3`;
  - post-release PR 14 on `chore/post-release-0.1.3`, with `0.1.4.dev0`, an empty `[Unreleased]` and the
    release noted in the tracker.
- **GitHub:** milestone `v0.1.4` is open with 5 closed issues and 0 open. Milestone `v0.1.3` is also still open
  (0 open, 3 closed). The latest release is `v0.1.3`. The current branch `release/v0.1.4` is cut from `master`
  `8d880e2` (the PR #22 merge).

## Decisions to approve

1. **The version is 0.1.4, a patch bump.** SemVer sets no rule for `0.y.z` (§4: initial development, anything may
   change). The usual convention (Cargo, npm caret ranges) treats `0.y` as the major version: a `y` bump for a
   breaking change, a `z` bump for compatible additions and fixes. Steps 12–14 hold no breaking change:
   - #15 relaxes a rule;
   - #16 adds a choice and a detection key;
   - #17 tightens the agents' reads;
   - #18 changes report content;
   - #19's `upgrade` can now stop before any change on a non-UTF-8 or broken managed block, a pre-check that
     names the file;
   - the config schema stays 1.

   So the version is 0.1.4, which also matches the milestone `v0.1.4`. A 0.2.0 would only mark the larger feature
   set, not a compatibility change.
2. **The changelog section is released as it stands.** `[Unreleased]` becomes `[0.1.4] - <date>`. The date is
   the day the release PR is opened. If the tag falls on a later day, a fix-up commit corrects it before the
   tag, as in step 9.
   - Section order: Fixed, Changed, three Known-limits sections, Upgrade. The release notes are this whole
     section.
   - Nothing is reworded, apart from one check (R03).
3. **Branch flow and roles**, as for 0.1.3:
   - **Me:**
     - release PR `release/v0.1.4`;
     - after the merge, the annotated tag `v0.1.4` on the merge commit, pushed only after your OK at that moment;
     - post-release PR `chore/post-release-0.1.4`.
   - **You:** request the Copilot reviews and merge both PRs.
   - The standing OK from step 9 still holds: follow-up fix commits on a release PR may be pushed without a new
     ask, and each one is reported.
4. **Close milestones `v0.1.4` and `v0.1.3`** once the release is published. Each has no open issues. I close
   them with `gh api`, after your OK at that moment.
5. **No Habit Tracker or e2e-sample upgrade** in this step, as for 0.1.2 and 0.1.3. The opt-in dotnet suite on
   the release branch stands in for it. Upgrading Habit Tracker (it gets the TRX `.gitignore` line) is your
   call afterwards.

## Requirements

### Release PR (`release/v0.1.4`)

- **S15-R01** Version `0.1.4` in `pyproject.toml` and `extension.yml`; `uv.lock` regenerated (`uv lock`), changing
  only the package's own version line.
- **S15-R02** `CHANGELOG.md`:
  - `## [Unreleased]` becomes `## [0.1.4] - <date>`;
  - the link definition `[Unreleased]: …compare/v0.1.3...master` becomes
    `[0.1.4]: https://github.com/theyur/spec-kit-ac/compare/v0.1.3...v0.1.4`.
- **S15-R03** Changelog read-through before the bump:
  - every issue of the milestone (#15–#19) is named;
  - no bullet describes behaviour that a later step changed (for example step 12 text that step 13 replaced);
  - no local absolute path.
  - Findings are fixed in the same PR and listed in the PR description.
- **S15-R04** `README.md`: the status line reads "Status: v0.1.4 released", and the install line pins `@v0.1.4`.
  Nothing else changes.
- **S15-R05** Checks on the release branch, before the PR:
  - `uv run pytest -q --tb=short` passes on CPython 3.14 and 3.11;
  - `tools/release_check.py check v0.1.4` and `notes 0.1.4 <scratch file>` succeed;
  - the opt-in dotnet tests (`SPECKIT_AC_DOTNET_E2E=1`: the init matrix, the host cases, the e2e sample) pass.
- **S15-R06** The PR passes `test (3.11)`, `test (3.14)`, `SonarCloud Code Analysis` and `CodeQL`.

### Tag and release

- **S15-R07** After the merge, and after your OK:
  - `git tag -a v0.1.4 -m "spec-kit-ac 0.1.4"` on the merge commit, then `git push origin v0.1.4`;
  - the release workflow passes every step and publishes `speckit_ac-0.1.4-py3-none-any.whl` and
    `speckit_ac-0.1.4.tar.gz`, with the changelog section as notes.
- **S15-R08** `uvx --isolated --from git+https://github.com/theyur/spec-kit-ac@v0.1.4 speckit-ac --version` prints
  `0.1.4`.
- **S15-R09** After your OK: milestones `v0.1.4` and `v0.1.3` are closed (decision 4).

### Post-release PR (`chore/post-release-0.1.4`)

- **S15-R10** Version `0.1.5.dev0` in `pyproject.toml` and `extension.yml`; `uv.lock` regenerated.
- **S15-R11** `CHANGELOG.md`: a new empty `## [Unreleased]` above `[0.1.4]`, and the link
  `[Unreleased]: https://github.com/theyur/spec-kit-ac/compare/v0.1.4...master`.
- **S15-R12** `docs/steps/TRACKER.md`:
  - row 15 marked done, with the verification;
  - step 15 notes that record the release: the PRs, the tag and its merge commit, the run result, and the `uvx`
    output.
  - The spec status becomes done.
- **S15-R13** The post-release PR passes the same four checks.

## Acceptance checks

| ID | Check | Covers |
|---|---|---|
| S15-A01 | On the release branch: pytest passes on 3.14 and 3.11; `release_check.py check v0.1.4` exits 0; the notes file equals the `[0.1.4]` section without link definitions | R01, R02, R05 |
| S15-A02 | The opt-in dotnet tests pass on the release branch | R05 |
| S15-A03 | The release PR's four checks pass; its diff touches only `pyproject.toml`, `extension.yml`, `uv.lock`, `CHANGELOG.md`, `README.md`, the tracker and this spec (plus any R03 fix, listed) | R01–R04, R06 |
| S15-A04 | Release `v0.1.4` exists with the two artifacts; its notes match the changelog section; `uvx` prints `0.1.4` | R07, R08 |
| S15-A05 | `master` after the post-release PR: `0.1.5.dev0`, an empty `[Unreleased]`, `test_release.py` passes, tracker row 15 done | R10–R13 |
| S15-A06 | Milestones `v0.1.4` and `v0.1.3` are closed | R09 |

## Out of scope

- Any code change. A defect found on the release branch stops the step: it goes into its own fix step, and this
  release waits or ships without it, as you decide.
- Upgrading Habit Tracker or the e2e sample (decision 5).
- PyPI publishing (DESIGN §9: GitHub only).
- Moving or re-creating a tag. A failed release run is re-run, or superseded by 0.1.5.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | The tag lands on a later day than the changelog date | R02: a fix-up commit before the tag; the workflow publishes the dated section as it is |
| 2 | `uv lock` changes more than the package's own version line (a newer resolver, a moved pin) | R01: the diff is checked; anything else is reverted, or reported before the PR |
| 3 | The release run fails after the tag is pushed (a flaky test, a runner change) | Re-run the workflow; the tag is never moved; a code fix becomes 0.1.5 |
| 4 | The release notes are long (three Known-limits sections) | They are the changelog as reviewed in steps 12–14; R03 checks them once more |
