# End-to-end sample (step 7)

A small spec-kit .NET project for running the whole AC flow once with a live model
(`docs/steps/07-e2e-sample.spec.md`). The live part is interactive Claude Code, driven by a person:
**[RUNBOOK.md](RUNBOOK.md)** says what to type, what to approve and what to check after each stage.

| Path | What |
|---|---|
| `sample/` | Base project copied over `specify init`: `Shop.slnx`, `src/Shop.Pricing` (`DiscountCalculator.Total`, not implemented yet), xUnit v3 / VSTest unit tests, `CLAUDE.md`, a filled constitution |
| `specs/` | The two feature specs `stage.py spec` seeds instead of `/speckit-specify`: 001 order discount (100.00 or more → 10 % off), 002 raises the threshold to 150.00 |
| `fixtures/` | Implementations `stage.py implement` copies instead of `/speckit-implement`: `001-buggy` (`>` instead of `>=`, the planted bug), `001-fixed`, `002` |
| `reference/` | Hand-written acceptance criteria, features and step definitions. Used **only** by `tests/test_e2e_sample.py` to prove the sample catches the bug; never copied into the live sample |
| `make_sample.py` | Builds the sample in a folder outside this repo and installs speckit-ac into it |
| `stage.py` | Seeds a spec, copies a fixture, commits between stages |
| `check_stage.py` | Checks a stage from the files it left; PASS / FAIL / WARN lines |
| `e2elib.py` | Shared helpers |

Tests: `tests/test_e2e_tools.py` (always run) covers the three scripts on fabricated trees;
`tests/test_e2e_sample.py` (`SPECKIT_AC_DOTNET_E2E=1`, a few minutes) builds a real sample and runs the reference
tests against every fixture.
