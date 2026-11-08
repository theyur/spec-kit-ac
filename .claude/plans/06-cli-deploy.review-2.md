# Plan review 2 — step 6 (plan-critic, 2026-11-08)

**Verdict: REVISE** (0 BLOCKER, 2 MAJOR, 4 MINOR)

All twelve round-1 findings are resolved by concrete plan edits. The facts were re-verified, and
`GUARD_COMMAND` reproduces the R10 string exactly. The order is consistent with the guard's
fail-closed behaviour.

## Findings

1. **[MAJOR]** Steps 4 and 7 (R15, R13.3, A05). In upgrade, `build_manifest` hashes an agent the
   user changed and upgrade kept, so the new manifest records the user's hash. A later uninstall then
   deletes the user's agent.
   - **Fix:** for a kept agent, record the hash of the deployed source, or carry the old entry forward.
   - **Test:** edit an agent, upgrade, uninstall.
2. **[MAJOR]** Step 11 (A07). The real-`specify` test passes a payload without `__pycache__`, so A07 is
   proven only against the fake.
   - **Fix:** plant `__pycache__/*.pyc` and a `*.pyc` file in the payload copy. Assert that nothing
     matches under `.specify/extensions/ac/` and that no `.extensionignore` is installed.
3. **[MINOR]** Step 7. `settingsCreatedKeys` is not stated for the upgrade manifest.
   - **Fix:** carry it forward, as a union with the result of the new register.
4. **[MINOR]** Design (R01 ASCII). Child output decoded with `errors="replace"`, or a non-ASCII path in an
   error message, can break the ASCII-only rule or cp1252 stdout.
   - **Fix:** route printing through one function that uses `backslashreplace`. Set `PYTHONUTF8=1` for
     child processes.
   - **Test:** a failing fake `specify` with non-ASCII output.
5. **[MINOR]** Steps 6 and 7. `add --force` may leave backups in `.backup/ac/`.
   - **Fix:** probe it, then delete the backups or list them as kept.
6. **[MINOR]** Assumption A2 is still at 0.7 although step 2 says it is confirmed.
   - **Fix:** update the table.
