# Plan review 1 — step 6 (plan-critic, 2026-11-08)

**Verdict: REVISE** (0 BLOCKER, 3 MAJOR, 9 MINOR)

Coverage: every requirement R01–R18 and acceptance check A01–A08 maps to a plan step. The facts F1–F3,
F8 and F9 were verified against the repo. Guard ordering is correct everywhere: install registers after
the self-test and before the manifest, rollback unregisters first, uninstall unregisters before
`specify extension remove`, and upgrade re-registers only after a passing self-test.

## Findings

1. **[MAJOR]** Step 4 `unregister_guard` (R10, R13.2, round trip). Dropping an empty `PreToolUse` and an
   empty `hooks` unconditionally removes keys a pre-existing `settings.json` already had (`"hooks": {}`).
   - **Fix:** record whether install created `hooks` / `hooks.PreToolUse`, and drop them only then.
2. **[MAJOR]** Step 6 `remove_leftovers` (R13.8, A02). The parent `.specify/extensions/` is never
   removed. If a fresh project has none, the round trip leaves an empty folder.
   - **Fix:** probe, then add it to `PREEXISTING`; also decide for `.claude/skills/`.
3. **[MAJOR]** Steps 3–7 (R05, R13). `aclib` block helpers raise `AcError`, which is never wrapped. In
   uninstall that can stop the run after the guard is off and the agents are deleted, and a re-run then
   fails.
   - **Fix:** wrap `AcError` as `DeployError`. Make each uninstall step tolerate "already done". Test a
     failed uninstall followed by a successful re-run.
4. **[MINOR]** `EMPTY_EXTENSIONS_YML` may be CRLF on disk.
   - **Fix:** confirm the raw bytes, or compare after folding CRLF.
5. **[MINOR]** `payload_module`: `init_config` inserts its folder into `sys.path` and imports `aclib`.
   Loading by file location can create two `aclib` modules and two `AcError` classes.
   - **Fix:** register the modules in `sys.modules` and load `aclib` first.
6. **[MINOR]** Doctor check 11 compares the config's `python` with the constant, but the spec says the
   registered command.
   - **Fix:** parse the registered command; fall back to the constant only when nothing is registered.
7. **[MINOR]** Doctor aborts on a malformed `settings.json` instead of printing a `[FAIL]` line and
   continuing.
   - **Fix:** catch the error and continue.
8. **[MINOR]** Test gaps:
   - (a) doctor writes nothing: compare snapshots;
   - (b) running from a sub-folder is refused;
   - (c) A04 needs a state check at the time of the call: settings content when `remove` runs, and no
     guard group during the self-test.
9. **[MINOR]** DESIGN §9 (line 172) says the guard command uses the config's Python. Add that sentence to
   the step 12 edit list.
10. **[MINOR]** If the rollback itself fails there is no manifest, so `uninstall` refuses.
    - **Fix:** print the manual steps on an undo failure.
11. **[MINOR]** A pre-existing identical agent file is deleted by uninstall.
    - **Fix:** record each agent's pre-existence, or refuse any same-name file.
12. **[MINOR]** Host timeouts are unspecified.
    - **Fix:** state them per call class (e.g. 300 s for `uv run`, 180 s for `specify`). A timeout is a
      reported failure, not a crash.
