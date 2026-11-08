# Step 7 — live end-to-end run: results

Spec: [07-e2e-sample.spec.md](07-e2e-sample.spec.md) · Runbook: [tests/e2e/RUNBOOK.md](../../tests/e2e/RUNBOOK.md) ·
Run on 2026-11-08, 17:26–18:57, driven by the user. I checked each stage with `check_stage.py`, the run folders,
`.workflow/guard.log` and the sample sessions' transcripts (`~/.claude/projects/E--Personal-speckit-ac-e2e/`).

## Environment

- Windows 11, Claude Code 2.1.318 (desktop app, auto mode), spec-kit 1.0.2, .NET SDK 10.0.403, uv 0.11.26,
  PowerShell 7.6.9; speckit-ac 0.1.0.dev0 installed as a uv tool from the checkout.
- Sample `<e2e-sample>` (own git repository): `Shop.Pricing`, xUnit v3 on VSTest, Reqnroll 3.3.4.
- **Model:** every main session and every subagent ran on `claude-fable-5-1` (the user's session model; the AC
  agents have no `model:` key and inherit it; the critic asked for `model: "fable"`, `effort: "high"`).

## Outcome per stage

| Stage | What ran | Check | Outcome |
|---|---|---|---|
| 1 | `make_sample.py` (4 s) | — | sample built, CLI from the uv tool, payload matches the checkout, `doctor` 0 FAIL (after a tooling fix, below) |
| 2 | `/speckit-ac-init` (≈ 7 min) | `init` PASS | detection as expected; config xunit3 / VSTest; AC project `tests/Shop.AcceptanceTests`; verification passed |
| 3 | `/speckit-ac-init smoke` (≈ 6 min) + 3 manual checks | `smoke` PASS | all three AC roles ran under the guard and **handed back**; guard decisions exactly as expected, each once; main-agent read blocked; `Explore` launch denied (its prompt named `StepDefinitions/`); missing interpreter blocked Bash, PowerShell and Glob (`onFailure: block`) |
| 4 | 001: translate ×2, critic `ac` ×2, critic `features`, tests-write, tests-analyze, fix, tests-analyze | `ac`, `features`, `written`, `analyze fault-001` (on `analyze-1`), `analyze pass` all PASS | 4 AC items; critic `ac` REVISE → APPROVE; translator: no issues; writer: 17 results; **only the 100.00 → 90.00 example failed, judge `IMPLEMENTATION_FAULT`, high**; the main agent's fix (`>` → `>=` + 6 lines of unit tests) → 17/17 passed |
| 5 | 002: translate ×2, tests-write, tests-analyze (all features) | `ac`, `features`, `written`, `analyze superseded-002` all PASS | 28 results; F002 11/11 passed; **7 F001 examples in [100.00, 150.00) failed, every one judged `SUPERSEDED`, high**, citing F002 FR-002 |
| 6 | `speckit-ac doctor` | `init` PASS | 13 ok, 0 warn, 0 FAIL |

Acceptance checks: S07-A03 (smoke), A04 (fault, then pass) and A05 (superseded) met; A01/A02 see the tracker.

## Open items carried into step 7

| Open item (from) | Answer | Evidence |
|---|---|---|
| TRX `className` carries `F00N` (step 2) | confirmed (also step 5) | results keyed `F001/…` and `F002/…` in both features' runs |
| `export_refs.py` against a real project (step 2) | confirmed | tests-write ran it; both writers built in ref mode first time |
| class-level `[Scope(Tag = "F00N")]` scopes step definitions (step 3) | confirmed | F001 and F002 bind **identical** step texts, each class scoped; 28 results, no ambiguous binding |
| model passes the multi-line task message unchanged (steps 3–4) | confirmed | 6 AC launches + 3 smoke launches, no launch denied, no retry |
| `tools:` keeps `SubagentHandback`; hand-back screen runs (step 3) | confirmed | every role handed back; the screen denied feature 001's writer once (`ac-test-writer SubagentHandback deny`), it retried, then allowed |
| hand-back in interactive Claude Code (step 1 risk 4, PARTIAL headless) | confirmed | all hand-backs arrived as "[Subagent hand-back]" messages |
| `Agent` `description` reaches the subagent (step 4) | not observed | the calls carry a description ("AC translator run translate-001", …); what the subagent saw is not visible |
| Fable available for `/speckit-ac-critic` (step 4) | confirmed, but not discriminating | `model: "fable"` accepted; the main agent was on Fable too |
| dotnet steps of the commands (step 4) | confirmed | build, unit tests, `export_refs.py`, `acTestCommand`, TRX, `summarize_trx.py` all ran in both features |
| hook runs in Git Bash with `$CLAUDE_PROJECT_DIR`, 30 s timeout (step 6) | confirmed; timeout not hit | the missing-interpreter error came from `/usr/bin/bash`; the guard found the project in every call (≈ 120 logged decisions); no timeout in the run |
| `/speckit-ac-init` setup, verify, smoke live (step 5) | confirmed | stages 2–3 |
| model passes the multi-line smoke prompt unchanged (step 5) | confirmed | the three smoke launches were allowed |

## Guard log

121 lines after the run. After the smoke test: translator 18, writer 36, judge 27 decisions, critics
(`general-purpose`, role main) 25. **One denial** in the whole flow after the smoke test: the hand-back screen on
feature 001's writer (retried, then allowed). No isolation breach reported by `changed_files.py`.

## Times (from the transcripts; approximate, include waiting for hand-backs)

| Command | 001 | 002 |
|---|---|---|
| `/speckit-ac-translate` phase 1 | 51 s | 50 s |
| `/speckit-ac-critic ac` | pass 1 ≈ 5 min, pass 2 ≈ 1.5 min | — |
| `/speckit-ac-translate` phase 2 | ≈ 1.5 min | ≈ 1 min |
| `/speckit-ac-critic features` | ≈ 2 min | — |
| `/speckit-ac-tests-write` | ≈ 2 min | ≈ 1.7 min |
| `/speckit-ac-tests-analyze` | ≈ 1.7 min (fault), ≈ 3.5 min (after the fix) | ≈ 5 min |

## Fixes made during the run (all in the e2e tooling; no package defect found)

1. `e2elib.cli_command("tool")` found the checkout's `.venv\Scripts\speckit-ac.EXE` first on PATH under `uv run`;
   it now uses `uv tool dir --bin` only (+ test). Stage 1 re-run with `--force`.
2. The runbook assumed terminal T's folder was the checkout; it now defines `$R`, `$S` and PowerShell functions
   `check` / `stage` that work from any folder.
3. `check_stage analyze` read only the latest analyze, so the fault could not be re-checked after the fix; new
   `--analyze analyze-K` option (+ tests).
4. `check_stage analyze` kept one verdict per AC id; outlines give one judge row per failing example, so a wrong
   verdict among them could hide. Every verdict of an id now counts (+ test).

## Findings

- **Every AC subagent and the critic ran in the background**, although the commands ask for
  `run_in_background: false` (the model passed the string `"false"`). The main agent waited for each hand-back,
  so nothing broke. Recorded in WORKFLOW §6; candidate follow-up in the tracker.
- **The hook command runs in Git Bash:** backslashes in a hand-edited interpreter path are lost. The deployed
  command uses forward slashes. Recorded in WORKFLOW §6.
- The judge writes one Summary row per failing example, with trailing text in the key cell
  (`F001/AC-001 (row 100.00 → 90.00)`). Consumers must parse tolerantly (the e2e checker does).
- Outline examples show up in TRX test names as `…(subtotal: "100.00", total: "90.00", __pickleIndex: "0", …)`;
  `summarize_trx.py` keys them correctly by `@AC-` tag.
- Backlog (user): choose the critic's model at `/speckit-ac-init` (custom model / effort, or the main agent's).

## Not covered

- `TRANSLATION_FAULT`, `TEST_FAULT`, `SPEC_AMBIGUITY`, `UNEXPRESSIBLE` and the writer's feedback loop were not
  planted (the judge's feedback sections said "No feedback.").
- Whether the `Agent` description reaches the subagent.
- A hook timeout: never hit, so the 30 s value is not measured against a cold uv start.
- Only one model (Fable 5.1) and one framework / runner pair (xUnit v3 on VSTest).
