# Plan review 2 — Step 14 (plan-critic on Opus, 2026-11-16)

**Verdict: APPROVE** — 0 BLOCKER · 0 MAJOR · 2 MINOR. Round-1 dispositions F1–F3, F5, F7 correct and complete; F4
and F6 raise the two MINORs.

Checked this round (round-1 "Not checked"): `test_commands.py` flattens whitespace before matching (`:263`, `:522`);
`docs/DESIGN.md:217–221` decision-log table fits the planned row and nothing in DESIGN says the surface must be a
library; `docs/CONFIG.md:16` describes `acSurfaceProjects` neutrally; `tests/test_e2e_sample.py:97–104` reads only
existing proposal keys.

## Findings

1. **[MINOR] D1 + the F6 edit.** In D1's own case (host-only, no unit tests) the F6 rule always fires and offers
   the chosen projects' TFM, so D1's value never reaches the config; D1 only matters when tests exist but share no
   runnable TFM. The F6 trigger also misses unit tests whose common TFM is lower than a chosen host's (NU1201 at
   `init_verify` [1]). Fix: drop D1, or key the command rule on the TFM itself (ask when the chosen surface is not
   the proposal and the proposed TFM is null or lower than a chosen project's highest runnable TFM).
2. **[MINOR] Step 5 worker list: "gone `d__`" may fail on a correct listing.** `public_only()` strips only type
   declarations (`export_refs.py:336–351`); an `[AsyncStateMachine(typeof(<ExecuteAsync>d__N))]` attribute above
   `ExecuteAsync` survives. Assert on the declaration form instead, unless the fixture shows no attribute line.

## Not checked

TRACKER row format; CHANGELOG wording; the probe listings themselves.
