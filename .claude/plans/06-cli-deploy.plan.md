# Plan — step 6: `speckit-ac` CLI and deploy

Spec: `docs/steps/06-cli-deploy.spec.md` (approved 2026-11-08, decisions 1–8 as drafted).

## Facts (observed in the repo or by probe, 2026-11-08)

- F1 `src/speckit_ac/cli.py` has only `--version`/help (`build_parser`, `main(argv) -> int`, `_exit_code`);
  `tests/test_cli.py` covers them. `paths.payload_dir()` returns the bundled payload folder.
- F2 `aclib.py` has `BLOCK_BEGIN`/`BLOCK_END` (`#` lines), `_block_span`, `write_block(path, lines)`,
  `remove_block(path)`, `validate_config(cfg)`, `AcError`. `init_config.PYTHON = "uv run --no-project python -I"`.
  `write_block` appends after one blank line; `remove_block` drops one blank line before the block. A file
  without a trailing line break comes back with one (known edge; see G1).
- F3 The guard (`payload/hooks/guard.py`) takes the root from `CLAUDE_PROJECT_DIR` (else its install
  location), a missing config allows the main agent except `Skill speckit-ac-*` (exit 2, `skill_rule`), and
  logs only subagent calls (`log()`), so a main-agent self-test writes no `guard.log`.
- F4 Probe (specify 1.0.2): fresh `specify init --integration claude --script ps` has no `CLAUDE.md`,
  `.claude/settings.json`, `.specify/extensions.yml`, `.registry`; `extension add --dev` creates the
  extension folder (incl. `.specify-dev/agent-commands/claude/speckit-ac-*/SKILL.md`), five skill symlinks
  `..\..\..\.specify\extensions\ac\.specify-dev\…` (git mode 120000), `extensions.yml`, `.registry` (no
  source path). `remove ac --force` deletes real patched skills and leaves `.registry` =
  `{"schema_version": "1.0", "extensions": {}}` (CRLF, no trailing newline), `extensions.yml` =
  `installed: []\r\nsettings:\r\n  auto_execute_hooks: true\r\nhooks: {}\r\n` (raw bytes, **CRLF**; review-1 #4),
  empty `.backup/ac/`.
- F4c `extension add --dev --force` over an installed `ac` leaves only an **empty** `.specify/extensions/.backup/`
  (probe p2, review-2 #5); a later `remove` leaves an empty `.backup/ac/`. The leftover rule (empty folders
  only) covers both.
- F4b A fresh `specify init` has **no `.specify/extensions/` folder** (probe p2, review-1 #2); `.claude/skills/`
  exists from init (spec-kit's own skills), so it is never ours to remove.
- F5 spec-kit's copy honours `.extensionignore` (`specify_cli/extensions/__init__.py:1206`, gitignore
  syntax, file itself excluded). `specify --version` prints `specify 1.0.2`.
- F6 Generated SKILL.md frontmatter: `name`, `description`, `compatibility`, `metadata:` (nested `author`,
  `source`); no `disable-model-invocation`, no `argument-hint`.
- F7 **This machine has `core.autocrlf=true` (system gitconfig) and `core.symlinks=false`.** A clone checks
  out the committed LF files as CRLF, so raw-byte hashes of the deployed files differ in a clone.
- F8 `tests/test_stdlib_only.py` scans every `.py` under `src/speckit_ac/`; `speckit_ac` and payload script
  stems are allowed. `tests/acproject.py:95 run_guard` runs the real guard in tests.
- F9 `test_commands.py::test_real_spec_kit_install` already runs the real `specify` (skipped without it).

## Assumptions

| # | Assumption | Confidence | Consequence if wrong | Validation |
|---|---|---|---|---|
| A1 | Claude Code runs the hook command in Git Bash, so `$CLAUDE_PROJECT_DIR` in double quotes expands | 0.9 | guard never runs → every call blocked (fail closed, visible) | step 1 spike 4.4/4.6; live in step 7 smoke |
| A2 | `uv_build` puts `payload/.extensionignore` (a dotfile) into the wheel | confirmed (probe: built wheel lists `speckit_ac/payload/.extensionignore`) | bytecode could reach installs from a compiled wheel | wheel test in step 11 keeps it pinned |
| A3 | Creating symlinks works in the test environment (spec-kit created them here) | 0.8 | the fake `specify` falls back to a plain file; the symlink branch would be untested by unit tests | fake falls back and a test is skipped only for that branch; real-specify test covers links |
| A4 | Hashing deployed text with CRLF folded to LF is acceptable for "with its hash" (R09/R16) | 0.85 | doctor FAILs every file in an `autocrlf=true` clone (F7) | spec intent is "unchanged content"; deviation D1, critic review |
| A5 | spec-kit does not reformat `.claude/settings.json` during add/remove | 0.9 | round trip (b) fails | spike 3.5; real-specify round-trip test |
| A6 | Importing payload modules with `sys.dont_write_bytecode = True` writes no `__pycache__` | 0.95 | bytecode in the bundled payload; `.extensionignore` still keeps it out of installs | test A07 |

No blocking assumption (none < 0.7 with high consequence).

## Design

- `src/speckit_ac/paths.py`: `payload_module(name)` — imports a payload script module (`aclib`,
  `init_config`) from `payload/scripts/` with `sys.dont_write_bytecode` set for the import (R03).
- `src/speckit_ac/deploy.py` (new, stdlib only): all logic, no argparse.
  - `Host` dataclass: `run(cmd, cwd, stdin=None, env=None, timeout=…) -> (code, out)`, `which`, `system`.
    `REAL_HOST` uses `subprocess` (UTF-8, errors="replace"). Timeouts: `uv run` 300 s (a cold uv may fetch
    an interpreter), `specify` 300 s, `git` 60 s, guard self-test 60 s. A timeout or a missing executable
    returns code `None` with the reason; callers turn it into a prerequisite problem or `DeployError`, never
    a traceback (review-1 #12). Child processes get `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8`. Every line
    the CLI prints goes through one `say()` that encodes to ASCII with `errors="backslashreplace"` (R01;
    review-2 #4). Tests inject fakes.
  - Constants: `GUARD_REL = ".specify/extensions/ac/hooks/guard.py"`,
    `GUARD_COMMAND = f'{PYTHON} "$CLAUDE_PROJECT_DIR/{GUARD_REL}"'`, `TIMEOUT = 30`, `MANIFEST =
    ".workflow/deploy.json"`, `ROLES`, `MD_BEGIN/MD_END` (`<!-- … -->`), `EMPTY_EXTENSIONS_YML` (compared
    after folding CRLF to LF), `PREEXISTING = (".claude/settings.json", ".claude/agents",
    ".claude/agents/<role>.md" ×3, ".specify/extensions", ".specify/extensions.yml",
    ".specify/extensions/.registry", ".specify/extensions/.backup")` (review-1 #2, #11).
  - `DeployError` (user-facing, exit 1); every call into `aclib` that can raise `AcError` is wrapped
    (`aclib_call`) so it surfaces as `DeployError` (review-1 #3). `Report` collects `ok/warn/fail/info`
    lines (ASCII).
  - Pieces: `prerequisites`, `refusals`, `specify_add/remove`, `patch_skills`, `deploy_agents`,
    `write_claude_block`, `register_guard`/`unregister_guard`, `guard_self_test`, `content_hash`,
    `build_manifest`, `remove_leftovers`, `install`, `uninstall`, `upgrade`, `doctor`.
- `cli.py`: subparsers `install`, `uninstall`, `upgrade`, `doctor`; each calls `deploy.<cmd>(Path.cwd())`;
  `DeployError` → `FAIL: …` on stderr, exit 1; doctor returns 1 on any FAIL. No subcommand → help, 0.
- `aclib.py`: `_block_span`, `write_block`, `remove_block` gain keyword args `begin=BLOCK_BEGIN,
  end=BLOCK_END` (defaults keep init's behaviour). One helper for both block styles (R08).

## Steps

0. **Status.** Tracker row 6 → `implementing` once the critic loop ends. (—)
1. **Block helper generalised** (`aclib.py`): `begin`/`end` keyword args on the three functions; existing
   init tests unchanged. (R08, R13.5)
2. **Payload hygiene** (R03): add `payload/.extensionignore` (`__pycache__/`, `*.pyc`);
   `paths.payload_module(name)`: with `sys.dont_write_bytecode = True` for the duration, loads `aclib` first
   and registers it in `sys.modules["aclib"]`, then `init_config` (whose `import aclib` reuses it), so there
   is one `AcError` class (review-1 #5). The CLI uses `aclib` (blocks, `validate_config`, `AcError`) and
   only `init_config.PYTHON`. Payload README row. (A2 confirmed: a built wheel contains
   `speckit_ac/payload/.extensionignore`.)
3. **`deploy.py` — checks** (R01, R02, R04):
   - `require_root(root)`: `.specify/` exists, else `DeployError`.
   - `prerequisites(root, host) -> list[str]`: OS Windows; `uv`, `pwsh`, `specify` on PATH; `specify
     --version` parsed `specify X.Y.Z` ≥ 1.0.2; `uv run --no-project python -I -c …` prints ≥ 3.11;
     init-options `script == "ps"` and `integration == "claude"`; `CLAUDE.md`; a root `.sln`/`.slnx`;
     `git rev-parse --is-inside-work-tree` = `true`.
   - `read_settings(root)`: missing → `None`; not an object, `hooks` not an object, `PreToolUse` not a list
     → `DeployError`. Invalid JSON → `DeployError`.
   - `config_problem(root)`: config exists and `aclib.validate_config` (after JSON parse) fails → message.
   - `install_refusals`: manifest exists; `.registry` lists `ac`; an AC agent file in `.claude/agents/`
     with other content than the payload's; settings/config problems.
4. **`deploy.py` — deploy pieces** (R06–R11):
   - `patch_skill_text(text)`: split frontmatter by lines (keep the file's line ending); if a top-level
     `disable-model-invocation:` line exists set it to `true`, else insert `disable-model-invocation: true`
     before the top-level `metadata:` line, else before the closing `---`. No frontmatter → `DeployError`.
   - `patch_skills(root)`: for each `.claude/skills/speckit-ac-*/SKILL.md`: read bytes (through a link),
     unlink a link, write patched bytes; none found → `DeployError` (spec-kit did not render them).
   - `deploy_agents(root, keep_changed: dict|None)`: copy the three `.specify/extensions/ac/agents/*.md`;
     in upgrade, a target whose hash ≠ manifest is kept and reported.
   - `claude_block_lines()`: the generic rules of R08 (flow order, stop after each step, commands typed by
     the user only, never read/search/diff/review `StepDefinitions/` and `Support/` of the AC project,
     never edit `.feature` files, locks, `runs/`, `refsDir`, the marker, domain rules in the spec or
     constitution, pointer to `.specify/extensions/ac/README.md`). Written with `write_block(…, begin=MD_BEGIN,
     end=MD_END)`.
   - `register_guard(root) -> created_keys` / `unregister_guard(root, file_created, created_keys)`: our
     group = any `PreToolUse` group whose `hooks[*].command` contains `GUARD_REL`; removed, then (register)
     appended. `register` returns which of `hooks` / `hooks.PreToolUse` it had to create; `unregister`
     drops an empty `PreToolUse` / `hooks` **only if install created it** (review-1 #1). Write
     `json.dumps(obj, indent=2, ensure_ascii=False) + "\n"` with the file's newline (CRLF if the old
     text's first break is CRLF). On register of a pre-existing file, `reformatted` = the original text
     differs from that serialisation of its own parsed object; install reports it and the manifest keeps
     `settingsReformatted` (decision 3; no content is stored). On unregister: if install created the file
     and the object is `{}` → delete. No group present → no-op (re-runnable).
   - `guard_self_test(root, host) -> str|None`: run `PYTHON.split() + [root/GUARD_REL]` with
     `cwd=root`, `env = os.environ + CLAUDE_PROJECT_DIR=root`, stdin JSON
     `{"hook_event_name": "PreToolUse", "cwd": root, "tool_name": "Read", "tool_input": {"file_path":
     root/CLAUDE.md}}` → exit 0, and `tool_name: Skill, tool_input: {"skill": "speckit-ac-init"}` → exit 2.
     Returns the problem or `None`.
   - `content_hash(path)`: sha256 of the bytes with `\r\n` folded to `\n` (D1).
   - `build_manifest(root, preexisting, settings_created_keys, settings_reformatted, kept_agents={})`:
     a kept (user-changed) agent is recorded with the hash of the **deployed source**
     (`.specify/extensions/ac/agents/<role>.md`), never the user's file, so a later uninstall still sees it
     as changed and keeps it (review-2 #1). `schemaVersion 1`,
     `version`, `command`, `installedAt` (UTC ISO), `preexisting` (path → bool), `settingsCreatedKeys`,
     `settingsReformatted`, `files` = agents (`agent`), skills (`skill`), every file under
     `.specify/extensions/ac/` except `__pycache__` (`extension`), sorted by path. Written LF, indent 2.
     `read_manifest` validates the shape (else `DeployError`).
5. **`install(root, host)`** (R04, R05, R12): steps in R05 order; a list `done` of undo actions; on any
   failure after `specify extension add`, run `undo(done)` (reverse: unregister, remove block, delete
   written agents, `specify extension remove ac --force`, leftovers per the recorded `preexisting`) and
   raise `DeployError` naming the failed step. If an undo action itself fails, the error also prints the
   same manual-steps text uninstall prints without a manifest (review-1 #10). Prints what it wrote and the
   four next steps of R12.
6. **`uninstall(root, host)`** (R13, R14): no manifest → `DeployError` with the manual steps (decision 6).
   Order exactly R13.2–9: unregister → agents (missing → skip silently; preexisting → keep silently; hash
   match → delete; else keep + warn) → `CLAUDE.md` block → `.gitignore`/`.gitattributes` blocks
   (`remove_block`; delete the file when empty) → warn for changed skills → `specify extension remove ac
   --force` (only while `.registry` lists `ac`) → `remove_leftovers(root, preexisting)` (`.registry` when
   not preexisting and `extensions == {}`; `extensions.yml` when not preexisting and its CRLF-folded text ==
   `EMPTY_EXTENSIONS_YML`; `.backup/ac/` when empty, then `.backup/` when empty and not preexisting, then
   `.specify/extensions/` when empty and not preexisting; `.claude/agents/` when empty and not preexisting)
   → delete manifest, then `.workflow/` if empty. Lists the kept user data that exists (R14). Every step is
   a no-op when already done, and the manifest is deleted last, so after a failure (`AcError` from a
   malformed block, a failing `specify remove`) a second `uninstall` finishes the job (review-1 #3).
7. **`upgrade(root, host)`** (R15): needs manifest + `.registry` lists `ac`; prerequisites; settings/config
   checks. Unregister → `specify extension add --dev <payload> --force` → patch skills → agents (keep
   changed; their manifest hash = deployed source) → block → self-test → register → manifest (keep
   `preexisting` and `settingsReformatted`; `settingsCreatedKeys` = old ∪ this register's result,
   review-2 #3). On
   failure after unregistering: if `GUARD_REL` exists and the self-test passes, register again; raise
   `DeployError` naming the step.
8. **`doctor(root, host) -> int`** (R16): never writes. Checks 1–11 of R16 in order with `[ok]`, `[warn]`,
   `[FAIL]` lines and a total; every check catches its own `DeployError`/`AcError`/`OSError`/`ValueError`
   and reports `[FAIL]`, then the next check runs (a malformed `settings.json` is a `[FAIL]` on check 8,
   review-1 #7). Hashes via `content_hash`. Check 11 uses `aclib.validate_config` and compares
   `cfg["python"]` with the Python part of the **registered** command (falling back to the constant only
   when no group is registered, review-1 #6), then `.gitignore`/`.gitattributes` contain the `#` block.
   Last line points to `/speckit-ac-init` for the .NET checks. Returns 1 when any FAIL. Requires the root
   like every command (R01).
9. **`cli.py`** (R01): subparsers, ASCII output, exit codes; help text lists the four commands.
10. **Tests** (R18), new `tests/test_deploy.py` + `tests/fakespecify.py`:
    - `fakespecify.FakeHost(root)`: `specify --version` → `specify 1.0.2`; `extension add --dev P [--force]`
      → copy P honouring `.extensionignore` patterns, write the `.specify-dev` skills from the commands
      (spec-kit frontmatter shape of F6), symlink each skill (plain file if symlinks fail), registry +
      `extensions.yml` as probed; `remove ac --force` → delete folder and skill dirs, write F4 leftovers; `uv
      run --no-project python -I …` → `sys.executable -I …`; `git rev-parse` → `true`; records every call.
      `which`/`system` configurable.
    - Unit tests: each prerequisite problem; each refusal (R04); skill patch (link and file, LF and CRLF,
      key present `false` → `true`, no `metadata:`), byte-exact apart from the line; settings merge
      (missing, other hooks kept in order, existing entry replaced not duplicated, invalid types, CRLF);
      `CLAUDE.md` block LF/CRLF and round trip; manifest content; install happy path (call order:
      `specify add` before patch, self-test before register, register last before manifest); rollback when
      the self-test fails and when patching fails (tree back to the snapshot); uninstall order (guard off
      before `specify remove`), kept changed agent with warning, leftover rules both ways, kept user data
      listed, no manifest → exit 1 with manual steps; upgrade keeps a changed agent and re-patches skills,
      re-registers after a failing `specify add --force`; every doctor check ok and FAIL (A06's four
      named FAILs), CRLF-folded hashes pass; CLI exit codes and help.
    - Review-1 #8: doctor leaves the tree unchanged (snapshot before/after, incl. `.workflow/`); a command
      run from a sub-folder of the project fails (`.specify/` missing) without searching upwards; A04 by
      state, not only call order: the fake's `extension remove` handler records whether `settings.json`
      still holds our group at that moment (must be no), and its `uv run` handler records whether our group
      is registered when the self-test runs (must be no).
    - Review-1 #3: uninstall with a malformed `.gitignore` block fails with `FAIL:` (guard already off);
      after fixing the block, a second uninstall completes and the tree equals the pre-install snapshot.
    - Review-1 #1/#11: a pre-existing `settings.json` with `"hooks": {}` and a pre-existing identical agent
      file both survive the round trip byte for byte.
    - Review-2 #1: install → edit an agent → upgrade → uninstall: the agent is still there with the user's
      bytes, and both upgrade and uninstall name it in a warning.
    - Review-2 #3: install (creates `hooks`) → user adds another `PreToolUse` hook → upgrade → user removes
      it → uninstall: `settings.json` deleted (created by install, `{}` again).
    - Review-2 #4: a fake `specify` that fails with non-ASCII output → `FAIL:` line is pure ASCII.
    - Self-test against the real guard (copied payload).
    - Round trip with the fake host: snapshot equality (`.git` excluded) for a fresh project and one with an
      indent-2 `settings.json` holding another hook plus another `.claude/agents/` file.
    - `__pycache__` planted in a payload copy does not reach the install (A07); `payload_module` leaves no
      `__pycache__` in the payload.
11. **Real `specify` tests** (`tests/test_deploy_real.py`, skipped without `specify`/Windows): (a)/(b)
    byte-identical round trips; (c) install → commit → `git clone -c core.symlinks=false` → skills mode
    `100644` and patched, `doctor` exits 0 with only the config warning; (d) after `upgrade`, skills
    patched again; (e) after uninstall no `speckit-ac-*` skill. The payload is passed as a copy (deploy takes
    `payload` as a parameter defaulting to `payload_dir()`) **with planted `scripts/__pycache__/x.cpython-311.pyc`
    and `scripts/stray.pyc`**: nothing named `__pycache__` or `*.pyc` and no `.extensionignore` appears under
    `.specify/extensions/ac/`, and the manifest lists none (A07 against the real `specify`, review-2 #2).
    After (d) upgrade, uninstall still round-trips (F4c). Wheel check: `uv build --wheel` into a tmp dir and assert
    `speckit_ac/payload/.extensionignore` is in the zip (marked slow but run). (R18, A2)
12. **Docs** (R17): README (usable commands, install flow, new session, commit); CONFIG.md (rows for
    `deploy.json`, the `CLAUDE.md` block); WORKFLOW §6 (what doctor covers; settings reformat note); payload
    README (`.extensionignore`); DESIGN §9 text (manifest location, timeout 30, leftovers rule, doctor scope,
    and line 172: the committed guard command uses the v1.0 Python constant at deploy time and `doctor`
    checks it against the config's `python` — review-1 #9) and a decision-log row for decisions 1–8 + D1.
13. **Verify**: `uv run pytest -q --tb=short` on 3.14 and 3.11 (scratchpad venv); mutation spot-check ≥ 5
    (guard registered before self-test; unregister after `specify remove`; skill patch drops `metadata`;
    leftovers deleted although preexisting; doctor ignores a missing flag; CRLF folding removed); tracker
    row 6 and notes.

## Deviations from the spec

- D1 Hashes in the manifest and in `doctor` are taken over the content with CRLF folded to LF (F7: an
  `autocrlf=true` clone otherwise FAILs every file). Raw-byte equality is still what the round-trip tests
  check.
- D2 The manifest's `preexisting` covers more than the five paths of R09: also `.specify/extensions/` and
  each of the three agent files, plus `settingsCreatedKeys` / `settingsReformatted` (review-1 #1, #2, #11),
  so the round trip stays byte-identical in those cases.

- D3 (found in the real-spec-kit run) spec-kit rewrites an existing `.claude/settings.json` on every
  `extension add` / `remove` (`specify_cli/events.py` `_safe_write_json`, text mode → CRLF, non-ASCII
  escaped); the step 1 spike (3.5) had a file already in that form. `settings_style()` records the line ending
  and the reformat flag **before** `specify extension add`; `register_guard` writes in that ending; uninstall
  (and an install rollback) re-serialise the file in it after `specify extension remove`
  (`restore_settings_style`); the manifest gains `settingsNewline`. Without it, round trip (b) failed.

## Implementation notes

- All steps 1–13 done. Tests: `tests/fakespecify.py` (fake host + project + snapshot helpers),
  `tests/test_deploy.py` (92), `tests/test_deploy_real.py` (4, real specify / uv / git / uv build).
- Mutation spot-check (scratchpad `s6/mutate6.py`, `mutate6b.py`): 9 of 9 caught — register before the
  self-test, guard taken off after `specify remove`, skill patch replacing `metadata:`, leftovers ignoring
  `preexisting`, doctor ignoring a missing flag, no CRLF folding, settings style not restored, kept agent hashed
  as the user's file, created keys always dropped. (A first version of the guard-order mutation left the
  early unregister in place, so it was not a mutation; rewritten.)

## Gaps known up front

- G1 A `CLAUDE.md` / `.gitignore` without a trailing line break comes back from uninstall with one (F2).
  Reported in docs as a known limit; the round-trip fixtures end with a line break.
- G2 A user's `specify integration upgrade` reverts the skill patch; only `doctor` notices (DESIGN §9).

## Review dispositions

### Round 1 (`06-cli-deploy.review-1.md`, REVISE: 0 BLOCKER, 3 MAJOR, 9 MINOR)

1. ACCEPTED — `settingsCreatedKeys` in the manifest; empty `hooks`/`PreToolUse` dropped only when created
   (step 4, manifest, tests).
2. ACCEPTED — probe p2: a fresh project has no `.specify/extensions/` → added to `PREEXISTING` and removed
   when empty (F4b, step 6); `.claude/skills/` comes from `specify init`, never removed.
3. ACCEPTED — `aclib_call` wraps `AcError`; every uninstall step re-runnable, manifest deleted last; test.
4. ACCEPTED — raw bytes are CRLF (probe); compare after folding (F4, Design).
5. ACCEPTED — `payload_module` loads `aclib` first and registers it in `sys.modules` (step 2).
6. ACCEPTED — check 11 compares with the registered command (step 8).
7. ACCEPTED — every doctor check catches its own errors (step 8).
8. ACCEPTED — tests (a) doctor writes nothing, (b) sub-folder refused, (c) A04 by state (step 10).
9. ACCEPTED — DESIGN line 172 added to step 12.
10. ACCEPTED — undo failure prints the manual steps (step 5).
11. ACCEPTED — agent pre-existence recorded; a pre-existing agent is never deleted (Design, step 6).
12. ACCEPTED — per-call timeouts; timeout = reported failure (Design).

### Round 2 (`06-cli-deploy.review-2.md`, REVISE: 0 BLOCKER, 2 MAJOR, 4 MINOR)

1. ACCEPTED — a kept agent's manifest hash is the deployed source's (step 4, step 7); test added.
2. ACCEPTED — the real-`specify` test plants `__pycache__`/`*.pyc` and checks the install (step 11).
3. ACCEPTED — `settingsCreatedKeys` carried forward as a union in upgrade (step 7); test added.
4. ACCEPTED — `say()` with `backslashreplace`, `PYTHONUTF8=1` for children; test added (Design).
5. ACCEPTED — probed: `add --force` leaves only an empty `.backup/` (F4c); the empty-folder rule covers it;
   upgrade-then-uninstall round trip in step 11.
6. ACCEPTED — A2 marked confirmed.

### Round 3 (`06-cli-deploy.review-3.md`, APPROVE: 1 MINOR)

1. ACCEPTED — `read_settings` refuses a `PreToolUse` item that is not an object; the group matcher treats
   anything not shaped `{"hooks": [{"command": str}, …]}` as not ours and leaves it; unit test with a
   string item. Folded into steps 3–4 during implementation.
