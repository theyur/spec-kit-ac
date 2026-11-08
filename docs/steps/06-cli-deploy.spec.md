# Step 6 — `speckit-ac` CLI and deploy

**Status:** done (2026-11-08; decisions 1–8 approved as drafted; deviations D1–D3 recorded in the plan) · **Tracker row:** 6 · **Source of truth:** `docs/DESIGN.md`

## Goal

`speckit-ac install` turns a spec-kit .NET project into one that can run `/speckit-ac-init`: it
checks the prerequisites, adds the spec-kit extension from the bundled payload, and deploys the
Claude-side files spec-kit doesn't know about. These are the three agents, the guard registration,
the patched human-only skills, the `CLAUDE.md` block and a deploy manifest.

- `uninstall` undoes it.
- `upgrade` re-adds and redeploys.
- `doctor` checks the deployed state.

An install→uninstall round trip leaves a fresh project byte-identical.

Out of scope:

- running anything with a live model (step 7);
- the live guard smoke test (step 7);
- publishing the package (step 9).

## Context

- **DESIGN §9 (deploy):**
  - the three agents go into `.claude/agents/`;
  - the guard registration goes into `.claude/settings.json` (merged, added last,
    `onFailure: "block"`);
  - a marked block goes into `CLAUDE.md`;
  - a deploy manifest with hashes;
  - the skills are patched with `disable-model-invocation: true`, changing only that key and keeping
    `metadata.source`;
  - the `--dev` symlinks are replaced with real files.
- **DESIGN §9, CLI:**
  - `install` = checks → `specify extension add --dev <payload>` → deploy;
  - `uninstall` = undo the deploy (keep user-modified files, warn) → `specify extension remove ac`;
  - `upgrade` = add `--force` + redeploy;
  - `doctor` = hashes, guard registration, Python command.
- **DESIGN §9, guard command:** the committed guard command never points into the uv tool's
  environment.
- **DESIGN §9, verification:** step 6 verifies what git records, what a clone gets, and that
  `specify extension remove` still deletes the real skill files.
- **DESIGN §2:** v1.0 = Windows, uv, pwsh, spec-kit `--script ps`, Python command
  `uv run --no-project python -I`.
- **Tracker open items for step 6:**
  - `uninstall` removes the `.gitignore` / `.gitattributes` blocks that init wrote, with the same
    helper;
  - `doctor` may re-run `init_verify.py`;
  - deploy must exist before `/speckit-ac-init smoke` can pass;
  - deploy may patch `argument-hint` too (cosmetic).
- **Checked on 2026-11-08** with specify 1.0.2, by a probe in the session scratchpad:
  - **Fresh project.** `specify init --integration claude --script ps` writes
    `.specify/init-options.json` with `"script": "ps"` and `"integration": "claude"`. It writes no
    `CLAUDE.md`, no `.claude/settings.json`, no `.specify/extensions.yml` and no
    `.specify/extensions/.registry`.
  - **`extension add --dev <payload>` adds:**
    - `.specify/extensions/ac/`: every payload file, plus
      `.specify-dev/agent-commands/claude/<skill>/SKILL.md`;
    - five `.claude/skills/speckit-ac-*/SKILL.md` symlinks, which git records as mode `120000`, so a
      Windows clone with `core.symlinks=false` gets a text file holding the link path;
    - `.specify/extensions.yml`;
    - `.specify/extensions/.registry`. It records no source path.
  - **`extension remove ac --force`**, after the links were replaced by real patched files:
    - it deletes those files and their folders;
    - it leaves `.registry` = `{"schema_version": "1.0", "extensions": {}}`;
    - it leaves `extensions.yml` = `installed: []` / `settings: auto_execute_hooks: true` / `hooks: {}`;
    - it leaves an empty `.specify/extensions/.backup/ac/`.
  - **Ignore file.** spec-kit honours a `.extensionignore` (gitignore syntax) in the source folder
    when it copies an extension (`specify_cli/extensions/__init__.py`, `_load_extensionignore`).
  - **Version.** `specify --version` prints `specify 1.0.2`.
- **From the step 1 spike:**
  - hook commands run in Git Bash;
  - the form `uv run --no-project python -I "$CLAUDE_PROJECT_DIR/…"` works;
  - `onFailure: "block"` blocks both on a missing interpreter and on a timeout;
  - `extension add --force` regenerates the links and drops any patch;
  - `settings.json` is not touched by `specify extension …`.

## Requirements

### CLI

- **S06-R01 Subcommands.**
  - `speckit-ac install | uninstall | upgrade | doctor`. Each works on the current directory, which
    must be the project root (contains `.specify/`); it does not search parent folders.
  - `--version` and the help text stay as they are.
  - Exit codes: 0 success, 1 failure (or a doctor `FAIL`), 2 usage error.
  - Output is ASCII only.
  - The CLI writes nothing outside the project. It runs `specify`, `uv` and `git`.
- **S06-R02 Prerequisites.** `install`, `upgrade` and `doctor` check:
  - the OS is Windows;
  - `uv`, `pwsh` and `specify` are on PATH;
  - `specify --version` is at least 1.0.2;
  - `uv run --no-project python -I` starts a Python of at least 3.11;
  - `.specify/init-options.json` has `"script": "ps"` and `"integration": "claude"`;
  - `CLAUDE.md` exists;
  - a `.sln` or `.slnx` is in the root;
  - the project is a git repository.

  `install` and `upgrade` stop on the first list of problems before changing anything. `doctor`
  reports each one. dotnet is not checked here (`/speckit-ac-init` checks it).
- **S06-R03 The bundled payload never carries bytecode.**
  - The payload gets a `.extensionignore` with `__pycache__/` and `*.pyc`.
  - The CLI never imports payload modules in a way that writes `__pycache__` into the payload folder.

### Install

- **S06-R04 Refusals before any change.** `install` stops when any of these holds:
  - `.workflow/deploy.json` exists;
  - `.specify/extensions/.registry` lists `ac`;
  - a file in `.claude/agents/` has an AC agent's name and different content;
  - `.claude/settings.json` exists but is not a JSON object, or its `hooks` / `hooks.PreToolUse`
    have the wrong type;
  - `.workflow/config.json` exists and is invalid, because a registered guard would then block every
    call.

  For an existing install, it points to `upgrade` or `doctor`.
- **S06-R05 Order.** The steps run in this order:
  1. checks (R02, R04);
  2. record which files existed before (R09);
  3. `specify extension add --dev <bundled payload>`;
  4. skills (R06);
  5. agents (R07);
  6. `CLAUDE.md` block (R08);
  7. guard self-test (R11);
  8. guard registration (R10), last;
  9. manifest (R09).

  If a step after 3 fails, install undoes what it did (R13 order) and exits 1 with the cause.
- **S06-R06 Skills.** For every `.claude/skills/speckit-ac-*/SKILL.md`:
  - a symlink is replaced by a real file with the link target's bytes;
  - its frontmatter gets `disable-model-invocation: true`: the key is added before `metadata:`, or
    set if present. Every other byte stays as it was, including `metadata.source`;
  - `argument-hint` is not patched (decision 7).
- **S06-R07 Agents.** The three `agents/*.md` files are copied from the installed
  `.specify/extensions/ac/agents/` to `.claude/agents/`, byte for byte. This is the same source
  `task_message.py` reads.
- **S06-R08 `CLAUDE.md` block.**
  - The block sits between `<!-- >>> speckit-ac (managed; do not edit) -->` and
    `<!-- <<< speckit-ac -->`. It is written with the same block helper as init's blocks, generalised
    to take the marker lines. The file's CRLF / LF is kept, and the rest of the file is untouched.
  - The text is generic, because the config does not exist yet. It names the folders as
    "`StepDefinitions/` and `Support/` of the AC project (`acProjectDir` in
    `.workflow/config.json`)". It holds the soft rules from WORKFLOW §6 for the main agent:
    - run the flow only through the `/speckit-ac-*` commands, which the user types; never start them
      or the AC subagents any other way;
    - report and stop after each step;
    - never read, search, diff or review step definitions and AC support code, with any tool;
    - never edit `.feature` files, locks, `runs/`, `refsDir` or the marker;
    - every domain rule the AC depend on belongs in the spec or the constitution, not only in
      `CLAUDE.md`;
    - the flow order, pointing to `docs` of the extension (`.specify/extensions/ac/README.md`).
- **S06-R09 Deploy manifest** `.workflow/deploy.json` (committed; `schemaVersion: 1`). It holds:
  - the package `version`;
  - the guard `command`;
  - `files`: the project-relative path, `sha256` and `kind` of every file the deploy wrote or patched
    (`agent`, `skill`) and of every installed extension file (`extension`, under
    `.specify/extensions/ac/`). This lets `doctor` work without the bundled payload, so a teammate
    without the uv tool can check it too;
  - `preexisting`: whether each of these existed before install: `.claude/settings.json`,
    `.claude/agents/`, `.specify/extensions.yml`, `.specify/extensions/.registry`,
    `.specify/extensions/.backup/`;
  - the date and time.
- **S06-R10 Guard registration.**
  - `.claude/settings.json` is created as `{}` if missing.
  - One group is appended to `hooks.PreToolUse`:
    `{"matcher": "*", "hooks": [{"type": "command", "command": "uv run --no-project python -I \"$CLAUDE_PROJECT_DIR/.specify/extensions/ac/hooks/guard.py\"", "timeout": 30, "onFailure": "block"}]}`.
  - Our group is the one whose command names `.specify/extensions/ac/hooks/guard.py`. It is replaced
    if present, never duplicated.
  - The Python part is the v1.0 constant `init_config.PYTHON` (one definition).
  - The file is written as `json.dumps(…, indent=2, ensure_ascii=False)` plus a line break, in the
    file's own line ending. Other keys, their order and their values are kept.
- **S06-R11 Guard self-test.** Before registering, the installed guard runs with the registered
  Python command, `cwd` = root and `CLAUDE_PROJECT_DIR` = root, on two inputs. It must:
  - allow a main-agent `Read` of `CLAUDE.md` (exit 0);
  - block a main-agent `Skill` call for `speckit-ac-init` (exit 2).

  Otherwise nothing is registered and install fails.
- **S06-R12 Install output.** Install lists what it wrote and ends with the next steps:
  1. start a **new** Claude Code session (agents and hooks load at session start; trust the
     folder);
  2. run `/speckit-ac-init`;
  3. run `/speckit-ac-init smoke` in another new session;
  4. commit the deployed files, including the real `SKILL.md` files and `.workflow/deploy.json`.

### Uninstall

- **S06-R13 Order, guard first.** A registered guard whose file is gone would block every tool call
  of a running session, so the guard registration comes off first. The steps:
  1. needs `.workflow/deploy.json`; without it, stop and print the manual steps (decision 6);
  2. remove our guard group from `.claude/settings.json`. Delete the file if install created it and
     it is now `{}`;
  3. agents: delete each one whose hash matches the manifest; keep a changed one and warn;
  4. remove the `CLAUDE.md` block;
  5. remove the `.gitignore` / `.gitattributes` blocks (init's), with `aclib.remove_block`. Delete
     the file if it is empty afterwards;
  6. warn about each skill whose hash differs from the manifest, because spec-kit deletes it;
  7. `specify extension remove ac --force`;
  8. spec-kit's leftovers, only for what did not exist before install:
     - `.registry` if its `extensions` is empty;
     - `extensions.yml` if its text is exactly the empty state seen in the probe;
     - empty `.backup/ac/` and an empty `.backup/`;
     - `.claude/agents/` if it is empty;
  9. delete the manifest; delete `.workflow/` if it is empty.
- **S06-R14 User data stays.** Uninstall never deletes any of these, and lists the ones present as
  kept:
  - `.workflow/config.json`;
  - the AC project;
  - `refsDir`;
  - `specs/*/acceptance.md`;
  - `specs/*/ac/`;
  - `.workflow/guard.log`.

### Upgrade

- **S06-R15 Upgrade.**
  - It needs the manifest and an installed `ac`.
  - Order:
    1. checks;
    2. remove the guard registration;
    3. `specify extension add --dev <payload> --force`;
    4. skills (R06);
    5. agents: replace each unchanged one (hash = manifest); keep a changed one and warn;
    6. `CLAUDE.md` block, rewritten;
    7. guard self-test;
    8. guard registration;
    9. manifest, rewritten, keeping `preexisting`.
  - If a step after the unregistering fails and the installed guard is still there and passes the
    self-test, upgrade registers it again. Either way it exits 1 and names the failed step.
  - The same version may be re-applied, as a repair.

### Doctor

- **S06-R16 Doctor never writes.** It prints one line per check, `[ok]`, `[warn]` or `[FAIL]`, then
  a total. Exit 1 if any check is `FAIL`. The checks:
  1. prerequisites (R02);
  2. the manifest is present and valid;
  3. `.registry` lists `ac` at the manifest's version;
  4. the installed CLI version equals the manifest's (`warn`: run `upgrade`);
  5. every manifest file exists with its hash. `FAIL` for extension files and skills; `warn` for a
     changed agent;
  6. extra files in `.specify/extensions/ac/` are a `warn`, except `__pycache__`;
  7. each skill is a real file with `disable-model-invocation: true` (`FAIL`; fix: `upgrade`);
  8. exactly one guard group, with the command, `timeout`, `onFailure` and matcher of R10;
  9. the guard self-test (R11);
  10. `CLAUDE.md` has the block;
  11. config:
      - missing: `warn` (run `/speckit-ac-init`);
      - invalid: `FAIL`;
      - valid: `python` equals the Python part of the registered command, and the `.gitignore` /
        `.gitattributes` blocks are present.

  It does not run dotnet. It ends by pointing to `/speckit-ac-init` (verify mode) for the
  .NET-side checks (decision 5).

### Docs and tests

- **S06-R17 Docs.**
  - README: the commands are usable, with the install flow and the new-session note.
  - CONFIG.md: rows for `deploy.json` and the `CLAUDE.md` block.
  - WORKFLOW §6: doctor and what it covers.
  - Payload README: `.extensionignore`.
  - DESIGN §9 and a decision-log row for decisions 1–8, after approval.
- **S06-R18 Tests** (pytest; runtime stays stdlib only):
  - **Unit tests with a fake `specify`** (no real `specify` needed):
    - every refusal (R04);
    - skill patching, symlink and real file, byte-exact apart from the key;
    - settings merge: missing file, other hooks, an existing entry replaced, invalid types;
    - block markers in `CLAUDE.md`, CRLF and LF;
    - the manifest;
    - the uninstall order (guard first), kept user-modified agents, the leftover rules;
    - an upgrade that keeps a changed agent;
    - every doctor check, both the ok and the FAIL case;
    - rollback after a failing step;
    - the self-test against the real guard.
  - **Real `specify` tests** (skipped when `specify` is missing):
    - (a) a fresh `specify init --script ps` project plus `CLAUDE.md`, `.sln` and a git commit:
      install → uninstall gives a byte-identical tree, `.git` excluded;
    - (b) the same with an existing indent-2 `settings.json` holding another hook, and another file
      in `.claude/agents/`: byte-identical;
    - (c) after install, commit, then `git clone` with `core.symlinks=false`: the skills are mode
      `100644` with patched content; `doctor` in the clone passes, apart from the config `warn`;
    - (d) after `upgrade`, the skills are patched again;
    - (e) after uninstall, no `speckit-ac-*` skill is left.
  - The wheel ships `payload/.extensionignore`.

## Acceptance checks

- **S06-A01** The full suite passes on CPython 3.14 and 3.11, with the real-`specify` tests running
  (specify 1.0.2 is installed here).
- **S06-A02** Round trip (a) and (b) are byte-identical.
- **S06-A03** The clone check (c): real files, flag present, `doctor` exits 0.
- **S06-A04** The guard is registered only after a passing self-test. Uninstall removes it before
  `specify extension remove` (tested by the call order).
- **S06-A05** A user-modified agent survives uninstall and upgrade, and a warning names it.
- **S06-A06** `doctor` `FAIL`s on each of these, one test each:
  - a skill without the flag;
  - a changed `guard.py`;
  - a missing guard registration;
  - a config `python` that differs from the registered command.
- **S06-A07** No `__pycache__` in the installed extension, even when the payload folder has one.
- **S06-A08** A mutation spot-check: at least 5 deliberate breaks, each caught by a test.

## Out of scope

- Running `init_verify.py` from `doctor` (decision 5).
- Other OSes and PATH-Python detection (DESIGN §2).
- Restoring a reformatted `settings.json` byte for byte (decision 3).
- Patching `argument-hint` (decision 7).
- Installing from a URL or the spec-kit catalogue.
- A live model run and the live smoke test (step 7).

## Decisions taken in this spec (confirm on approval)

1. **The manifest is `.workflow/deploy.json`, committed.** It is not inside
   `.specify/extensions/ac/`, because `upgrade`'s `add --force` and `uninstall`'s `remove` delete
   that folder. It hashes the installed extension files too, so `doctor` works without the bundled
   payload.
2. **Guard hook: `timeout: 30`.** The spike used 15, but a cold `uv` start is slower, and a timeout
   blocks the call. The Python command at deploy time is the v1.0 constant, because the config does
   not exist yet. `doctor` checks later that the config's `python` matches.
3. **`settings.json` is re-serialised with `indent=2`** (spec-kit's own style). A file in that style
   round-trips byte for byte. Any other style comes back with the same JSON but new formatting, and
   uninstall says so. The CLI never copies `settings.json` content into the manifest, because it may
   hold secrets in `env`.
4. **Uninstall cleans spec-kit's empty leftovers only when they did not exist before install**
   (`.registry` with no extensions, `extensions.yml` in its exact empty state, empty `.backup/`). That
   is what makes a fresh project round-trip byte-identical. A project that had other extensions keeps
   its files.
5. **`doctor` does not run dotnet.** The .NET-side checks stay in `/speckit-ac-init` (verify mode),
   which doctor names. That keeps doctor fast, and runnable by a teammate without the SDK restore.
6. **Uninstall needs the manifest.** Without it, it stops and prints the manual steps rather than
   guessing which files are ours.
7. **No `argument-hint` patch.** DESIGN §9 says the patch changes only `disable-model-invocation`.
8. **A `.extensionignore` in the payload** keeps `__pycache__` / `*.pyc` out of every installed
   copy, whatever the installer compiled.
