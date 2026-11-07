# Plan review — 01-platform-spike — round 3

**Reviewer:** plan-critic subagent · **Verdict: APPROVE** (7 MINOR, no BLOCKER/MAJOR)

All round-1 and round-2 dispositions verified present and adequate (r2 F3 confirmed at
`common.sh:185–208`; r2 F8 confirmed at `extensions/__init__.py:2118–2130, 2966–2968`). Constraints
respected; evidence rules separate NOT RUN / PARTIAL from FAIL in steps 10, 11, 12 D3, 13. Coverage:
every R01–R13 and A01–A07 mapped.

## Findings (all MINOR; "can be applied during execution without a further round")

1. Step 14 / R07, A04 — exclusion list misses `.claude/skills/speckit-ac-invocable/` (D1 fallback),
   `.specify/feature.json`, `specs/001-stub/tasks.md`. `remove()` deletes only skill dirs in
   `registered_skills`, so the D1 copy would look like a leftover. Exclude them or delete the D1 copy
   after D2.
2. Step 12 (real-file patch) and 14 / R05a, R07, DESIGN §9 — `remove()` deletes
   `.claude/skills/<name>/` only if its `SKILL.md` frontmatter has `metadata.source: extension:ac`
   (`extensions/__init__.py:1811–1828`). The patch must flip only the one key; record "deploy patch
   must preserve `metadata.source`" as a step-6 consequence.
3. Step 16 / A07 — env.txt with `NAME=`/`NAME:` lines would hit `token"?\s*[:=]` for the messaging
   token variable name. Use bare names one per line, or pre-declare the exclusion.
4. Steps 7b, 9–13 / decision 1 — 11 runs + ≤ 2 Sonnet reruns vs "roughly 8–10". Report run count,
   worst case (≤ $13) and real `total_cost_usd` in the results doc.
5. Step 10 / R09e — no status for "control also says NONE"; pre-declare PARTIAL after one Sonnet
   rerun, consequence: agents must not rely on `omitClaudeMd`.
6. Step 17 / R12 — name the all-pass branch (propose, not apply, a §10 "verified" note).
7. Editorial — step 3 "same file as step 6" → step 7; duplicated "`git status --porcelain`" in step 16.
