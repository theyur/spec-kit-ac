# Plan review 2 — step 4 (plan-critic)

**Verdict: APPROVE** (0 BLOCKER, 0 MAJOR, 5 MINOR)

## Round-1 findings

All seven Resolved (1: restructure planned, one detail below; 2: deletion after usage checks, spec R08
amended; 3: lazy `FEATURE_LIST` + stray-folder test; 4: explicit `AcError`; 5: FR never exempt, spec
R09 amended; 6: verify only existing locks; 7: WORKFLOW §6 Bash bullet).

Re-verified: guard `:157–159`, `:236–275`, `:260`, `:279–298`; `aclib.py:242–254`, `Feature.paths()`
keys cover every placeholder except `RUN_ID`, `ANALYZE_ID`, `FEATURE_LIST` (handled);
`changed_files.py:52–68` usage checks precede the comparison; `make_project` copies the whole payload
(agents present); spec-kit validator ignores unknown `extension.*` keys; `uv_build` ships
`extension.yml`, `commands/`, `templates/` without changes.

## Findings (all MINOR)

1. `test_changed_files_allowlist`: after a fresh `new_run.py write` the active run is `run-002`, so the
   "another run's report" path `run-002/writer-report.md` (`test_scripts.py:255`) becomes allowed;
   move it to `run-003`. Create the new run before the new snapshot.
2. Critic port: the source skill's `knowledge base` wording (`SKILL.md:42`, the `plan` reference row)
   trips `test_no_ct_strings` (`knowledge-base` in `CT_STRINGS`, scans every payload `.md`/`.yml`);
   reword those lines.
3. `check_acceptance.py`: "bad heading" and "unknown ref" findings need a stated form — line number
   and id/ref token, not heading text (R10 "no file contents beyond ids").
4. Docs: on tests-analyze's all-passed path no `check` runs, so the judge marker (without
   `taskMessage`) stays; a command stopped between `task_message.py` and `check` leaves a marker with
   `taskMessage` (the identical launch stays possible until the next run script). Say so in CONFIG and
   WORKFLOW principle 9.
5. WORKFLOW §6: the bullet on editing `.specify/extensions/ac/` should name the installed
   `agents/*.md`, the source of `taskMessage`.
