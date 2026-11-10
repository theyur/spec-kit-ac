# Plan — Step 9: Release v0.1.0

Spec: `docs/steps/09-release.spec.md` (approved 2026-11-10). Scratchpad: `<sp>` =
`<scratchpad>`, work folder `<sp>/s9`.

**Rule for this plan, its reviews and every file committed in step 9:** never spell the original checkout's path
or the §10 tokens. They live only in `<sp>/s9/scrub.py`, `<sp>/s9/patterns.txt` and `CLAUDE.local.md`. Hashes
cited below are **pre-rewrite** hashes unless marked otherwise.

## Facts (inspected 2026-11-10)

- **F1** Local `master`, 15 commits (pre-rewrite `fa9fb9a` … `843258f`), no remote, no tags. `git 2.56.0.windows.4`.
  Uncommitted: `TRACKER.md` (PR 16 note, row 9 status). Untracked: the 09 spec, this plan, reviews 1–3 (and any
  later review). `git filter-branch` refuses staged or unstaged changes to tracked files; untracked files may stay.
- **F2** `docs/reference/WORKFLOW-SETUP-CT.md` was added in the first commit and never changed (one blob). §10 runs from
  line 784 (its heading) to EOF; the blob is LF (the working copy has CRLF in places, `git ls-files --eol`: `i/lf w/crlf`).
  Header lines 6 and 9 refer to §10.
- **F3** The original path occurs, over all commits, only as backtick + drive path + backslash (followed by
  `.claude\…`, `tests\…` or nothing), plus one forward-slash form inside §10.
- **F4** Own hashes cited in HEAD files: `a8986a9` (08 results), `9804ab8` (08 plan, 08 results).
- **F5** Version `0.1.0.dev0` in `pyproject.toml:3` and `src/speckit_ac/payload/extension.yml:6`;
  `tests/test_commands.py:88-93` asserts they match. `uv lock --check` passes.
- **F6** Tests skip without `specify` / `dotnet`; opt-in e2e via `SPECKIT_AC_DOTNET_E2E`; every test commit passes its
  own git identity. `test_init` `needs_dotnet` tests use `.slnx` (SDK ≥ 9.0.200); local SDK 10.0.403.
- **F7** Actions (`gh api`, 2026-11-10): `actions/checkout` v7.0.1, major tag `v7` exists;
  `astral-sh/setup-uv` `v10.3.3` (no `v10` major tag); `SonarSource/sonarqube-scan-action` v8.4.1, major tag `v8`
  exists, `runs.using: node24`, win32 handling in `src/main/utils.js`.
- **F8** `coverage` 7.17.2 on PyPI, `requires_python >=3.11`.
- **F9** GitHub `theyur/spec-kit-ac`: private, empty, no secrets. HT model: CI scanner with `SONAR_TOKEN` skip,
  CodeQL default setup, ruleset `master protect` (deletion, non_fast_forward, required `SonarCloud Code Analysis`
  [integration 12526] and `CodeQL` [57789], strict off).
- **F10** `gh` is preinstalled on GitHub-hosted runners.
- **F11** Dry run (`<sp>/s9/dryrun.sh` on a fresh scratch clone, round-2 scrub without a heading, 2026-11-10):
  exit 0; author/committer names, emails, dates and messages identical for all 15 commits; the union of changed
  files over the 15 old/new pairs is exactly the 10-file list (the reference doc + 9 path files; the spec's "11
  files" is a miscount of 9); the reference doc is one blob in all new commits and ends with the one line; every
  blob LF; path/token patterns: 0 hits in any commit; the reference doc has no `^## 10\.` heading in any commit
  (DESIGN's own `## 10. Known risks` heading made a repo-wide heading grep a false positive, so the heading check
  is path-limited); secret shapes: 0 hits (a positive-control pattern does hit); commit messages
  (`git log --format=%B`): 0 hits for the path/token patterns, the secret shapes and other local paths.
  Dry-run new HEAD `3ddce84`. Rerun after round 3 with `dryrun.sh` → `verify.sh` (every step 4 check scripted,
  full `%B` metadata comparison): `VERIFY: PASS`, same new HEAD `3ddce84`. Pre-commit scan of the current step 9
  files (`git ls-files -m -o --exclude-standard`, both pattern files): no hit, after the spec bullet was reworded.
- **F12** `CLAUDE.local.md` is still loaded at session start (Claude Code memory docs, checked 2026-11-10).
- **F13** Other local absolute paths (HT checkout, user-profile and scratchpad paths) appear in 13 tracked files.
  The spec does not cover them; the user decides at the step 3 gate.

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| A1 | `git filter-branch --tree-filter` keeps messages, authors, committer dates | 0.95 (F11) | Metadata drift | Compare logs (step 4) |
| A2 | Byte edits + `eol=lf` keep blobs LF | 0.95 (F11) | CRLF churn | `git ls-files --eol`, per-commit name-only diffs |
| A4 | The suite passes on `windows-latest` with uv + Python + the runner's git/pwsh/dotnet | 0.6 | CI red | First CI run; fix with tests in the PR (spec risk 1) |
| A5 | SonarCloud PR analysis gates new code = PR diff; it needs a prior `master` analysis (from the import's automatic analysis) | 0.7 | Gate red / no PR analysis | Preflight in step 10; the user waits for the first analysis before turning Automatic Analysis off |
| A6 | Required-check names will be `test (3.11)`, `test (3.14)`, `SonarCloud Code Analysis`, `CodeQL` | 0.8 | Merge blocked | Read the PR's check runs before the ruleset (step 17) |
| A7 | Subprocess-run scripts are not measured by coverage | 0.9 | Lower reported number | Accepted; noted |

## Steps

### Phase A — history (before the first push)

1. **Backup** (S09-R01): `git bundle create <sp>/s9/pre-rewrite.bundle --all`; `git bundle verify`; save
   `git log --format='%H %an <%ae> %ad | %cn <%ce> %cd | %s'` to `<sp>/s9/old-log.txt` (human-readable extra);
   from the **real** repository, write `verify.sh`'s inputs `<sp>/s9/real-old-revs.txt` (`git rev-list --reverse
   master`) and `<sp>/s9/real-old-meta.txt` (per commit `%an %ae %ad %cn %ce %cd %B`, NUL-separated, as in
   `dryrun.sh`) (round 4 #1); record `git stash list` and `git for-each-ref` (round 4 #4). Nothing in the tree
   changes in this step (round 3 #3).
2. **Scrub script** `<sp>/s9/scrub.py` (stdlib, `uv run --no-project python -I`; written with the Write tool):
   - reference doc: replace §10 (from its heading to EOF) with the single line
     `§10 (choices specific to the original project) is not part of this copy.` — **no heading** (round 1 #3);
     reword header lines 6 and 9 to point at "the original project" and say §10 is not part of this copy; each
     anchor must match exactly once, else exit 1;
   - every file: the backslash path form → `<original project>\`, the forward-slash form → `<original project>`;
     exit 1 if any form of the path is left.
   `<sp>/s9/patterns.txt` holds the repo-wide check patterns (the path in any slash form, the old §10 heading text,
   the distinctive §10 tokens), one regex per line; `<sp>/s9/secret-patterns.txt` the secret shapes. Two greps per
   commit `<c>` (round 2 #1):
   - repo-wide: `git grep -I -i -E -c -f <sp>/s9/patterns.txt <c>`;
   - heading, reference doc only: `git grep -c -E '^## 10\.' <c> -- docs/reference/WORKFLOW-SETUP-CT.md`.
3. **Dry run and gate** (round 1 #1, #5; round 2 #5, #6, #11; round 3 #4): one script,
   `<sp>/s9/verify.sh <repo> <old-meta-file> <old-revs-file>`, used for every dry run and for the real rewrite
   (step 4 passes the `real-old-*` files of step 1), so both are checked the same way. Any grep exit status above 1
   fails the script, and a positive control requires every line of `patterns.txt` to hit the old HEAD
   (round 4 #2). It prints only names, counts and hashes:
   - the old→new map;
   - full-message metadata equality (`%an %ae %ad %cn %ce %cd` + `%B` per commit, old vs new);
   - the union of changed files over the 15 pairs, and any file outside the planned list;
   - the reference-doc blob count and its last line;
   - both greps of step 2, the secret scan, and the message scan (`git log --format=%B master | grep -c -f …` with
     both pattern files);
   - the non-LF blob count;
   - the new HEAD hash.

   `<sp>/s9/dryrun.sh` clones fresh, runs the filter, then calls `verify.sh` on the clone. The F11 checks were
   partly run by hand; the gate shows `verify.sh`'s output. **Show
   the user** these results, the spec's file-count correction (11 → 9 path files), F13, and the version rule of
   step 12, and **ask**: (a) OK to rewrite the real repository; (b) do F13's paths stay; (c) accept the version rule.
   If (b) is "remove" (round 3 #2): extend `scrub.py`, the planned file list **and `patterns.txt`** with the F13
   paths; rerun the dry run; ask (a) again with the new results. The extended `patterns.txt` is then the one used
   by steps 4, 16 and 17. Nothing in the real repository changes before (a) is answered yes.
4. **Rewrite and verify** (S09-R02, A01, A02):
   - set the WIP aside (round 3 #3): copy `TRACKER.md` and the untracked step 9 files to `<sp>/s9/wip/`, compare
     each copy with the original byte for byte (`cmp`), then `git restore docs/steps/TRACKER.md` (the only tracked
     change; untracked files stay in place);
   - `FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch --tree-filter "<python> <sp>/s9/scrub.py" -- master`;
   - `verify.sh` on the real repository; every check passes (the list below);
   - the new HEAD hash equals the dry run's (deterministic rewrite);
   - logs: same 15 lines as `old-log.txt` except hashes; map saved to `<sp>/s9/hash-map.txt`;
   - for each of the 15 old/new pairs: `git diff --name-only` ⊆ {reference doc, `CLAUDE.md`, `docs/DESIGN.md`,
     `docs/steps/{00,01,02,03,05}-*.spec.md`, `.claude/plans/{02-runtime-port,03-agents}.plan.md`} (10 files; the
     spec's "11 files" counted the reference doc twice — corrected in the tracker notes);
   - the reference doc is the same blob in all 15 new commits; inspect that blob once (ends with the one line);
   - both greps of step 2 over every new commit, and the message scan: nothing;
   - secret-shape scan over every commit (`<sp>/s9/secret-patterns.txt`, `git grep -c`): file names and counts
     only, none expected; a hit is shown by file name and decided with the user;
   - copy `TRACKER.md` back from `<sp>/s9/wip/`; if (b) was "remove", run a path-only copy of the scrub (the
     reference-doc anchors removed) with `<sp>/s9/wip/` as its working directory, copy the results back over the
     tree, then grep them with the extended `patterns.txt`: nothing (round 3 #2, round 4 #3);
   - `uv run pytest -q --tb=short` on 3.14 and on 3.11 (scratchpad venv) → PASS counts;
   - keep `refs/original/` and the bundle until the user confirms in step 19.
5. **Branch and hash remap** (round 1 #15): `git switch -c release/v0.1.0`; remap `a8986a9` and `9804ab8` in the 08
   plan and results with `hash-map.txt`; mark the plan's and spec's pre-rewrite hashes as such (this plan's header
   note; one note line in the spec's Context); correct the spec's "11 files" to 9 (shown to the user in step 3).
6. **Local path note** (S09-R03, round 1 #14): `CLAUDE.local.md` (path + read-only rule), `.gitignore` entry;
   `CLAUDE.md`: "Port from the original project's `.claude\` folder (its path is in `CLAUDE.local.md`; read only,
   never edit it)" and line 10 reworded (§0–9 generic; §10 not part of this copy); `docs/DESIGN.md` lines 26–28
   likewise. `git check-ignore CLAUDE.local.md` (A03).
7. **First push** (S09-R04) — **ask first**: `git remote add origin https://github.com/theyur/spec-kit-ac.git`;
   `git push -u origin master` (the rewritten master only; the release branch stays local);
   `gh repo view --json defaultBranchRef` → `master`; `git rev-parse master origin/master` equal (A04).

### Phase B — gates before the PR (round 1 #4)

8. **User:** make the repository public. Check `gh repo view --json visibility` → `PUBLIC`.
9. **CodeQL** (S09-R11) — **ask**, then
   `gh api -X PATCH repos/theyur/spec-kit-ac/code-scanning/default-setup -f state=configured -f query_suite=default`;
   read back state and languages (expected `python` now; `actions` after the workflows reach `master` — read again
   after the merge).
10. **User:** import the repo into SonarQube Cloud (org `theyur`, key `theyur_spec-kit-ac`), wait for the first
    automatic analysis of `master`, turn Automatic Analysis off, add the `SONAR_TOKEN` secret. **Preflight:**
    visibility public, `gh secret list` shows the name `SONAR_TOKEN` (name only), default setup `configured`, and
    the user confirms that the first analysis of `master` finished and Automatic Analysis is off (round 2 #8).
    The PR is opened only when all of these hold.

### Phase C — release changes on `release/v0.1.0`

11. **Version** (S09-R05): `0.1.0` in `pyproject.toml` and `extension.yml`; `uv lock`; `uv run speckit-ac --version`
    → `speckit-ac 0.1.0`. S00-A03 (dev version) stays as history.
12. **Helper** `tools/release_check.py` (stdlib):
    - `check <tag>`: exit 1 unless the tag is `v` + the pyproject version, the `extension.yml` version is the same,
      and the version is not a pre-release (`.dev`, `a`, `b`, `rc`);
    - `notes <version> <out>`: write the `## [<version>] - <date>` section of `CHANGELOG.md`; exit 1 when missing
      or empty;
    - `latest`: print the newest dated changelog version.
    **Version rule (round 1 #10; a new decision, asked at the step 3 gate — round 2 #4):** after a release, the
    next change on `master` moves it to the next `.dev0` version and adds an `## [Unreleased]` changelog section
    (the first post-release PR, not part of step 9). The README pins the newest *released* (dated) changelog
    version, never a dev version. If accepted: recorded in DESIGN §9 and as deviation D3 (R10's checks key off
    `latest` instead of the package version). If declined: no DESIGN text, R10 as written (tests compare with the
    package version), and `latest` is dropped from the helper.
13. **Tests** `tests/test_release.py` (S09-R10), stdlib; comment lines are stripped before any match (round 1 #9):
    - helper in-process: matching tag, wrong tag, mismatched manifest (tmp copy), a dev version refused, notes
      extraction, missing or empty section, `latest`;
    - `ci.yml`: `push` to `master`, `pull_request`, `workflow_dispatch`; top-level `permissions: contents: read`;
      concurrency `ci-${{ github.ref }}`; `windows-latest`; matrix `["3.11", "3.14"]`; job name
      `test (${{ matrix.python }})`; `uv sync --locked`; `uv run pytest -q --tb=short`;
    - `sonar.yml`: same triggers as Habit Tracker's (`push` to `master`, `pull_request` opened/synchronize/reopened,
      `workflow_dispatch`); permissions exactly `contents: read` and `pull-requests: read`, no `write` anywhere
      (round 3 #6); the skip step tests `SONAR_TOKEN`; `fetch-depth: 0`; `--with coverage`; scan action `@v8`;
      `sonar-project.properties` holds org, key, `sonar.sources=src,tools`, `sonar.tests=tests`,
      `sonar.python.version=3.11`, `sonar.python.coverage.reportPaths=coverage.xml`, `sonar.qualitygate.wait=true`;
    - `release.yml`: `tags: ["v*"]`; permissions exactly `contents: write`; step order check → pytest → build →
      notes → `gh release create` (last); no `continue-on-error`, no `if:`; pinned `python-version`,
      `enable-cache: false`;
    - all workflows: every `uses:` is `owner/repo@vN` or `@vN.N.N`; top-level `permissions:` present;
    - `CHANGELOG.md`: a dated section for `latest`; when the package version is not a dev version, it equals
      `latest` and `notes` returns non-empty text for it from the real changelog (round 2 #7); README has
      `git+https://github.com/theyur/spec-kit-ac@v<latest>` and no `<owner>` (per the step 3 answer, see step 12).
14. **Workflows and config** (S09-R06–R08):
    - `ci.yml`: as tested; `fail-fast: false`; checkout@v7, `astral-sh/setup-uv@v10.3.3`
      (`python-version: ${{ matrix.python }}`, `enable-cache: true`). **No setup-dotnet** (round 1 #11): R06's
      steps only; the first run records the runner's SDK; if `.slnx` tests fail there, adding it is a deviation
      for the user.
    - `sonar.yml`: HT pattern (header comment with the one-time setup; fork PRs get no token, so the job skips);
      windows-latest, Python 3.14; `uv sync --locked`;
      `uv run --with coverage coverage run -m pytest -q --tb=short`; `uv run --with coverage coverage xml`;
      `SonarSource/sonarqube-scan-action@v8` with `SONAR_TOKEN`; org/key overrides passed in `args` only when the
      repository variables are set (round 1 #12); defaults live in `sonar-project.properties`.
      `pyproject.toml`: `[tool.coverage.run] source = ["src", "tools"]`, `relative_files = true`.
    - `release.yml`: windows-latest; checkout@v7; setup-uv (`python-version: "3.14"`, `enable-cache: false`);
      `uv sync --locked`; `release_check.py check "$GITHUB_REF_NAME"`; pytest; `uv build`; `release_check.py notes`;
      `gh release create "$GITHUB_REF_NAME" dist/*.whl dist/*.tar.gz --title … --notes-file … --verify-tag` with
      `GH_TOKEN: ${{ github.token }}`; bash steps say `shell: bash`.
    - `.gitignore`: `.coverage`, `coverage.xml`, `CLAUDE.local.md`.
15. **Docs** (S09-R09):
    - README: install section (pinned + unpinned), status "v0.1.0 released", "PR flow" (PRs against `master`;
      CI, Sonar and CodeQL must pass; Copilot review on request; fork PRs can't pass the Sonar check), `tools/`;
    - DESIGN §9: URL, version rule; decision-log row 2026-11-10;
    - `CHANGELOG.md`: Keep a Changelog header, `## [0.1.0] - <date>` (the planned tag date; corrected in the PR if the
      tag moves to a later day) summarising steps 0–8;
    - tracker row 9 → `implementing`, notes (including the file-count correction).
16. **Local verification and PR**:
    - pytest on 3.14 and 3.11 → PASS counts;
    - coverage commands locally: `coverage.xml` `<source>` entries + `filename`s resolve to existing files
      (round 1 #13);
    - `uv build` → `speckit_ac-0.1.0-py3-none-any.whl`, `speckit_ac-0.1.0.tar.gz`; `release_check.py check v0.1.0`
      exit 0, `check v0.1.1` exit 1;
    - **ask** to commit, push the branch and open the PR, and whether follow-up fix commits on this PR may be
      committed and pushed without a new ask each time (a standing OK, recorded in the tracker notes; round 2 #3);
    - **pre-commit scan** (round 3 #1): both pattern files (`grep -I -i -E -c -f`) over every file to be committed
      (`git ls-files -m -o --exclude-standard`, so `CLAUDE.local.md` and other ignored files are never read):
      nothing. A hit is fixed by rewording (no allowlist); the spec bullet that named a secret shape is already
      reworded in words;
    - after the OK: commit; **leak scan** (round 2 #2): both greps of step 2 and the secret shapes over every commit
      in `origin/master..HEAD` (`git rev-list`), plus the message scan of that range: nothing; only then
      `git push -u origin release/v0.1.0` and `gh pr create --base master` (body ends with the Claude Code line).
      No review request.
17. **Checks and ruleset** (S09-R12):
    - watch the PR's checks with `mcp__ccd_pr__get_status` (no polling loops);
    - fix CI/Sonar/CodeQL findings with tests in new commits (spec risks 1, 3–5), each reported; every push runs
      the step 16 pre-commit scan and the leak scan over `origin/release/v0.1.0..HEAD` first, and is made under the
      standing OK or after a new ask (round 2 #2, #3). Saved reviews describe secret shapes and tokens in words;
    - the user requests Copilot reviews; findings are assessed and fixed as in tracker step 8;
    - once all four checks have reported on the head, **ask**, then `gh api -X POST repos/theyur/spec-kit-ac/rulesets`
      from a JSON file mirroring HT plus the two `test (…)` contexts (the Actions integration id is read from the
      PR's check runs); read it back (A06). Before the merge, tracker row 9 says `done (pending tag)` and its
      "Verified" cell says "A01–A06 verified; A07–A08 pending the tag" (round 3 #5). The notes list one open item:
      the post-release PR (A07/A08 results, release URL, the `.dev0` bump and `[Unreleased]` if the version rule was
      accepted, a changelog date fix if the tag falls on a later day than the changelog date).
18. **Tag** (S09-R13, round 1 #7) — after the user merged:
    - `git switch master && git pull --ff-only`;
    - on the merge commit: `release_check.py check v0.1.0`, `release_check.py notes 0.1.0 <sp>/s9/notes.md`
      (non-empty) and `uv build` (both artifact names) (round 2 #7);
    - gating runs for that SHA: `test (3.11)`, `test (3.14)` and `CodeQL` green. The `master` Sonar run is reported;
      if it is red, the tag waits for the user's decision (fix first, or tag anyway);
    - read the CodeQL default-setup languages again (expect `actions` and `python`) and report them (round 2 #9);
    - **ask**, then `git tag -a v0.1.0 -m "spec-kit-ac 0.1.0"`, `git push origin v0.1.0`;
    - wait for the release run (one `gh run watch` in the background); check the Release assets and notes (A07);
    - if the release run fails after the tag is public, the tag is never moved: report it, and the user chooses a
      re-run (when the cause is outside the tree) or `v0.1.1`.
19. **Install check and cleanup** (S09-R14):
    - `uvx --isolated --from git+https://github.com/theyur/spec-kit-ac@v0.1.0 speckit-ac --version` → `0.1.0`;
    - in HT: first record its branch and `git status --porcelain` (baseline; round 2 #11); then
      `uv tool install --reinstall speckit-ac --from git+…@v0.1.0`, `speckit-ac upgrade`, `speckit-ac doctor`
      → 0 FAIL; HT's diff against the baseline left uncommitted and reported (A08);
    - **ask** the user whether the backup can go (round 4 #4): first show `git stash list` and `git for-each-ref`;
      only if the stash is empty and the refs are `master`, `release/v0.1.0`, the remote refs, the tag and
      `refs/original/refs/heads/master`: `git update-ref -d refs/original/refs/heads/master`,
      `git reflog expire --expire=now --all`, `git gc --prune=now`; otherwise report and ask. The bundle stays in
      the scratchpad until the session ends;
    - **ask** whether to make the post-release PR now (the open item from step 17): tracker row 9 → `done` with
      A07/A08 results and the release URL, plus the dev bump and the date fix when they apply. It follows the same
      scan, push and PR rules as steps 16–17.

## Requirement coverage

| Req | Steps |
|---|---|
| R01 | 1 |
| R02 | 2, 3, 4 |
| R03 | 6 |
| R04 | 7 |
| R05 | 11 |
| R06–R08 | 12, 14 |
| R09 | 15, 17 |
| R10 | 13 |
| R11 | 9 |
| R12 | 17 |
| R13 | 18 |
| R14 | 19 |
| Decision 3 (gates) | 3, 7, 9, 16, 17, 18, 19 |

## Deviations from the spec (round 2 #10; carried into the tracker notes)

- **D1** `astral-sh/setup-uv@v10.3.3`: a full version, because the action publishes no `v10` major tag (F7). R06 says
  "a released major version that has been checked to exist"; the full tag is the closest checked form. Other
  actions use major tags.
- **D2** `sonar.sources=src,tools`: decision 5 names `src/`; the release helper in `tools/` is source code, so it is
  analysed too.
- **D3** (only if the user accepts the version rule at the step 3 gate) R10's changelog/README checks key off the
  newest released changelog version, not the package version.
- **D5** (only if the user answers "remove" at gate 3(b)) R02's planned file list grows by the files holding the F13
  paths, and `patterns.txt` by their patterns.
- **D4** The spec's Context says 11 files carry the path; the dry run shows 9 (plus the reference doc). Spec text
  corrected in step 5.

## Review dispositions

### Round 1 (`09-release.review-1.md`, REVISE)

1. BLOCKER, rewrite gate — ACCEPTED: step 3 shows the dry-run results and asks; nothing changes before the OK.
2. MAJOR, the plan leaks the patterns — ACCEPTED: the patterns live in `<sp>/s9/patterns.txt`, the plan describes
   them in words, and step 16 scans the release branch and the working tree before the push.
3. MAJOR, the §10 heading — ACCEPTED: one line, no heading; `^## 10\.` is in the patterns.
4. MAJOR, the gates come after the PR — ACCEPTED: Phase B (public → CodeQL → Sonar import, analysis, token) comes
   before the PR, with a preflight in step 10.
5. MINOR, weak verification — ACCEPTED: per-pair name-only diffs against the 10-file list, a single blob check,
   new HEAD equal to the dry run's, one file list.
6. MINOR, both Pythons on the rewritten HEAD — ACCEPTED: step 4.
7. MINOR, the check before the tag — ACCEPTED: step 18 checks the merge commit and `master` CI, plus the
   failure rule.
8. MINOR, release Python and cache — ACCEPTED: `3.14`, `enable-cache: false`.
9. MINOR, weak text checks — ACCEPTED: comments are stripped, the full order is asserted, no `continue-on-error`
   or `if:`, and the triggers and concurrency are asserted.
10. MINOR, dev-version breakage — ACCEPTED: the version rule in step 12; the tests key off `latest`.
11. MINOR, setup-dotnet and init_verify — ACCEPTED: setup-dotnet dropped (R06 as written), `init_verify.py` dropped
    from step 19.
12. MINOR, Sonar org and key in two places — ACCEPTED: the defaults are in the properties file, and the overrides
    are passed only when the variables are set.
13. MINOR, coverage paths — ACCEPTED: a local check in step 16, and the `.gitignore` entries.
14. MINOR, stale §10 pointers — ACCEPTED: `CLAUDE.md` line 10 and DESIGN lines 26–28 in step 6.
15. MINOR, loose ends — ACCEPTED:
    - the backup is released in step 19;
    - the remap and the branch are in step 5;
    - "as in tracker step 8";
    - the tracker says `done` before the merge;
    - the pre-rewrite hashes are marked;
    - the fork-PR note is in the README and the `sonar.yml` header.

Not a finding (F13): put to the user at the step 3 gate.

### Round 2 (`09-release.review-2.md`, REVISE)

1. MAJOR, the heading pattern can't pass — ACCEPTED: the heading grep uses a pathspec for the reference doc only,
   and the path and tokens stay repo-wide. Both commands are in step 2, and the F11 dry run used them.
2. MAJOR, the leak scan can pass on nothing — ACCEPTED: commit first, scan every commit in
   `origin/master..HEAD` plus its messages, then push. It repeats before every later push (steps 16, 17).
   No `--no-index`.
3. MAJOR, step 17 pushes without an OK — ACCEPTED: a standing-OK question in step 16, recorded; otherwise ask
   before each push.
4. MAJOR, the version rule is a new decision — ACCEPTED: it's asked at the step 3 gate. Both branches are
   spelled out in step 12, and D3 applies only if it's accepted.
5. MAJOR, commit messages aren't scanned — ACCEPTED: the message scan is in the dry run (F11: 0 hits) and in
   steps 3, 4 and 16.
6. MINOR, the "11 files" claim — ACCEPTED: the dry run printed the union over all 15 pairs (exactly the 10-file
   list). The correction is shown at the gate and made in the spec (step 5, D4).
7. MINOR, the rehearsal covers only `check` — ACCEPTED: a real-changelog `notes` test (step 13); `notes` and
   `uv build` on the merge commit; the gating runs are named, and a red Sonar run on `master` waits for the user
   (step 18).
8. MINOR, the preflight misses A5 — ACCEPTED: the user confirms the first analysis and Automatic Analysis off
   (step 10).
9. MINOR, the `actions` language re-read — ACCEPTED: step 18 reads it before the tag ask.
10. MINOR, unrecorded deviations — ACCEPTED: D1–D4 listed.
11. MINOR, open branches — ACCEPTED: the F13 "remove" loop (step 3), and the HT baseline before the upgrade
    (step 19). The scratchpad path in this plan's header falls under F13 and goes with the user's answer.

### Round 3 (`09-release.review-3.md`, REVISE)

1. MAJOR, the secret gate trips on the spec — ACCEPTED: the spec bullet now describes the shape in words; a
   pre-commit scan over the files to be committed is in step 16 (F11: no hit now); "nothing" stays the rule, with
   no allowlist; reviews are saved without spelling shapes or tokens.
2. MAJOR, the WIP restore on the "remove" branch — ACCEPTED: on that branch `patterns.txt` gets the F13 patterns,
   the restored WIP files are scrubbed and grepped before pytest (step 4), and steps 16 and 17 use the extended
   file.
3. MINOR, the tree changes before the gate — ACCEPTED: step 1 changes nothing; step 4 sets aside, after the OK, only
   the modified tracked file, with a byte check; F1 now lists reviews 1–3.
4. MINOR, the dry-run script — ACCEPTED: `verify.sh` (full `%B` comparison, the union, every step 4 check) is used
   for every dry run and for the real rewrite; it was rerun with `VERIFY: PASS` (F11).
5. MINOR, `done` before A07/A08 — ACCEPTED: row 9 says `done (pending tag)` with A07–A08 pending; the post-release
   PR is an open item before the merge and an explicit ask in step 19.
6. MINOR, `sonar.yml` permissions — ACCEPTED: the exact set `contents: read` + `pull-requests: read`, with no
   `write`, is asserted in step 13.

### Round 4 (`09-release.review-4.md`, APPROVE)

1. MINOR, `verify.sh` inputs — ACCEPTED: step 1 writes `real-old-revs.txt` and `real-old-meta.txt` from the real
   repository, and steps 3–4 state the three-argument call.
2. MINOR, grep failures and no positive control — ACCEPTED: an exit status above 1 fails the script, and every
   line of `patterns.txt` must hit the old HEAD.
3. MINOR, the scrub on the "remove" branch — ACCEPTED: a path-only scrub runs inside `<sp>/s9/wip/`; D5 is added.
4. MINOR, the cleanup scope — ACCEPTED: the stash and refs are checked first, and the exact commands are named in
   step 19.
