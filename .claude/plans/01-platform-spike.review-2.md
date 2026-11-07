# Plan review — 01-platform-spike — round 2

**Reviewer:** plan-critic subagent · **Verdict: REVISE** (2 MAJOR, 7 MINOR, no BLOCKER)

All twelve round-1 dispositions verified present and adequate. Constraints respected (scratchpad
only, no global installs, explicit `--allowedTools`, no bypassPermissions, `--max-budget-usd 1`, 10 runs
+ ≤ 2 Sonnet reruns). Coverage: every R01–R13 and A01–A07 mapped (notes per finding below).

## Findings

- **[MAJOR] F1** — Facts bullet 3, step 9 / R08, R09. Stripping *every* `CLAUDE*` variable may strip
  `CLAUDE_CODE_GIT_BASH_PATH`, which Claude Code on Windows uses to find the hook/Bash shell; hooks
  would fail to launch, `onFailure: block` would block every call, and steps 9–13 would stall. The
  "OK" probe used no tools/hooks. Fix: strip by explicit name list minus a keep-list
  (`CLAUDE_CODE_GIT_BASH_PATH` and other `CLAUDE_CODE_*` configuration knobs), record names stripped
  and kept (never values) in `logs/env.txt`.
- **[MAJOR] F2** — step 12 D3 / R09h, R05c, A05. "No Skill call" is not proof the model *cannot*
  invoke the skill; `system/init` slash-command list does not discriminate either. Force an attempt
  ("call the Skill tool with skill `speckit-ac-probe` even if you believe it is unavailable; report the
  exact error verbatim"); PASS only on an observed `Skill` attempt in the hook log plus an error in the
  tool_result, else PARTIAL.
- **[MINOR] F3** — step 13 / R06. `common.sh:180–208` resolves the feature only from
  `SPECIFY_FEATURE_DIRECTORY` or `.specify/feature.json` (`feature_directory`); no git. Write
  `.specify/feature.json` = `{"feature_directory": "specs/001-stub"}` before run E.
- **[MINOR] F4** — steps 12 → 13 / R06, R08. `specify extension` commands in step 12 re-serialize
  `settings.json`; if the probe entry is dropped, run E has no hook and risk 2 is NOT RUN for the wrong
  reason. Before run E (and run A if `specify` ran after step 7), re-parse and assert the probe entry;
  if removed, record as a deploy fact and re-add.
- **[MINOR] F5** — step 16 / R01, R10. `~/.claude.json` is written every run and holds account
  details. Record only file names and changed/unchanged (hash/mtime), never contents/diffs.
  Pre-declare `~/.claude.json`, `~/.claude/stats-cache.json`, `history.jsonl` as expected writes.
- **[MINOR] F6** — steps 7, 10 / R09e, A05. Results row must say R09e was measured on `spike-omit`
  (Glob-only), not `spike-agent`, and why. Ask the main agent's canary sanity question **last**, so it
  doesn't leak into subagent prompts.
- **[MINOR] F7** — step 16 / A06. `.claude/plans/*.md` are untracked planning artefacts; pre-declare
  them in the A06 check.
- **[MINOR] F8** — step 12 / R05a. Rewrite sequence listed once for two patch variants. State which
  variant it tests or run per variant. `--force` calls `remove()` → `rmtree` (`extensions/__init__.py:
  2118–2130, 2966–2968`), deterministic for both; `add zz` / `remove zz` legs may differ.
- **[MINOR] F9** — step 12 D1 fallback / R09h. Fallback copy dir `spike-invocable` vs
  `name: speckit-ac-invocable`; if skills are keyed by directory, the D2 deny rule would not match.
  Make the directory equal to `name` (dead branch anyway).

## Source verification (reviewer)

`extensions/__init__.py` 1620–1731, 1384–1389, 2086–2130, 2895–2977, 5043–5054;
`integrations/claude/__init__.py:218–228`; `extensions/_commands.py:986–992, 1168–1172`;
`core_pack/commands/tasks.md:95–127`; `core_pack/scripts/bash/common.sh:77–85, 180–208`;
`commands/init.py:280–282, 367–368`; `docs/DESIGN.md:143–151`.
