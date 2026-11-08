# Plan review 1 — step 4 (plan-critic)

**Verdict: REVISE** (1 MAJOR, 6 MINOR, no BLOCKER)

## Requirement coverage

No unmapped requirement (R01–R22 mapped to steps 1–12). Verified against the repo and spec-kit
1.0.2: F1 (`guard.py:157-159`, `:236-275`, prompt through `self.strings` at `:260`), F2
(`guard.py:279-298`, `aclib.py:242-254`), F4 (`changed_files.py:52-82`), F5
(`summarize_trx.py:150-177`), F6/F7; `extension.version` via `packaging.Version`
(`extensions/__init__.py:324`), list hooks with `command`/`priority ≥ 1`/`optional`/`prompt`/
`description` (`:418-439`, `:5043-5054`), lower priority first (`:5118-5136`); the four `after_*`
events are real; `extract_feedback.py`, `record_skips.py`, `check_features.py` don't read the marker,
so deleting it at `check` breaks no later step; guard dispatch position is correct; no conflict with
`CLAUDE.md` (`tomllib` only in tests).

## Findings

- **[MAJOR]** Step 3 breaks `tests/test_scripts.py::test_changed_files_allowlist` (`:239-260`, four
  `check` calls on one marker: no snapshot, success, breach, wrong role) and
  `test_changed_files_translator` (`:278-290`, success then breach); step 10 doesn't plan their
  restructuring.
- **[MINOR]** Step 3's `finally` deletes the marker on usage errors before any check (no snapshot,
  wrong role, broken config); R08 says "after the check". A mistyped role then forces a new run
  folder.
- **[MINOR]** `FEATURE_LIST` from `all_features` must be lazy: `all_features` fails on any stray
  folder under `specs/`; only the judge uses it. Pin with a test (stray folder + translator run
  succeeds).
- **[MINOR]** A missing agent **file** must be an explicit `AcError` (a plain `read_text` raises
  `FileNotFoundError`, not `FAIL: …`).
- **[MINOR]** R09 lets FR rows say "Not testable through the API", R10 requires every FR covered;
  decide explicitly and say it in the template's instructions.
- **[MINOR]** R15 step 2: `ac_lock.py verify` exits 1 both for "not locked" and "differ"; the command
  must check which lock files exist per feature and verify only those.
- **[MINOR]** WORKFLOW §6: a Bash-forged marker now also carries `taskMessage`, so it lets the main
  agent start an AC role with any prompt; extend the existing Bash bullet.
