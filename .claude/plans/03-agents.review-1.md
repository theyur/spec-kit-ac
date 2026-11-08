# Plan review 1 — 03-agents (plan-critic)

## Requirement coverage

| Req | Plan step(s) | Note |
|---|---|---|
| R01 | 3, 4, 5, 6 | Covered. |
| R02 | 3–5, 6, 8 | Covered; payload grep confirms it is clean today. |
| R03 | Design "Placeholders", 3–5, 6 | Covered, but the "sourced" check is weak (Finding 2). |
| R04 | Design "Templates", 3–5 | Labels match the spec for all three roles. Placeholder spellings differ from the spec (`<AC_DIR>` → `<AC_PROJECT_DIR>`, `<SAMPLES_DIR>`, …); justified, not yet reflected in the spec. |
| R05 | 2 | Covered. |
| R06 | 1, 7 | Covered. |
| R07–R09 | 3 | Covered. |
| R10–R14 | 4 | R13 only partly reachable (Finding 1). |
| R15–R18 | 5 | Covered. |
| R19 | 6 | Covered; see Findings 2 and 4 on drift detection. |
| R20 | 1, 2 | Covered. |
| R21 | 7 | Covered. |
| R22 | 8, 9 | Covered. |

Verified against the repo: plan facts F3–F7 are true. Every template path traced is allowed by the guard
for its role with the matching marker. Tag rules match `check_features.py`; `API-CHANGED:`/`UNEXPRESSIBLE:`
ride on `PendingStepException`, which `summarize_trx.outcome()` counts as pending; `F00N/AC-NNN` matches
`summarize_trx` headings. No contradiction with CLAUDE.md or DESIGN §8.

## Findings

- **F1 [MAJOR] The writer is told to read the project files but has no way to find them.** The guard
  denies Glob/Grep rooted at `<ac>` and the writer's only Bash command is the build, so it cannot list
  `<ac>/`. The template has no line naming the `.csproj`, yet R13 depends on reading it. `acProject`
  exists as a config key and the guard allows reading it. Add a `Project file: <AC_PROJECT>` line
  (flagging the R04 deviation), or limit R13.
- **F2 [MAJOR] The "placeholders come from allowed sources" test does not test the source mapping.**
  Both lists are hand-maintained, so renaming an `aclib.Feature.paths()` key would not fail
  `test_agents.py`. Fill templates mechanically (UPPER_SNAKE → camelCase → lookup in `ac_feature.py`
  output or `CONFIG`; `RUN_ID`/`ANALYZE_ID`/`FEATURE_LIST` special) and fail on a missing key.
- **F3 [MINOR]** CT's "your own earlier translation reports" must be dropped (guard allows only the
  active run's report); the plan does not say so.
- **F4 [MINOR]** R07 vs R08 tension on items without an id: state that any Gherkin-like entry is an
  item and a missing id/traceability is an issue with id `—`.
- **F5 [MINOR]** `test_no_hard_coded_paths` may trip on the placeholder table; say whether the table is
  excluded from the scan or must contain no example paths.
- **F6 [MINOR]** `ac_feature.py --all` fails the whole listing on any stray folder under `specs/`; a spec
  choice (R20), worth a tracker note for steps 4/5.
- **F7 [MINOR]** R04 placeholder spellings changed without a spec amendment.
- **F8 [MINOR]** No assumption row for the hand-back tool surviving the `tools:` whitelist; add it to the
  step 7 confirmation list.

## Verdict: REVISE
