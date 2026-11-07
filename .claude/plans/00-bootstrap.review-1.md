# Plan review — round 1 (plan-critic) — verdict: REVISE

Spec: `docs/steps/00-bootstrap.spec.md` · Plan: `.claude/plans/00-bootstrap.plan.md`

Requirement coverage: R01–R14 all mapped; no unmapped requirements.

## Findings

- [MAJOR] Step 1 + 6 + 7 (R01, R03, A01): `readme = "README.md"` is declared in step 1 but README is
  created only in step 7; `uv sync` in step 6 builds the project with uv_build, which fails on a
  missing readme. Create README before step 6 or drop `readme`.
- [MINOR] Step 2 `cli.py` (R05): state the `SystemExit.code` mapping (`None` → 0, int → int) so the
  `-> int` contract is honest.
- [MINOR] Step 4 (R08, R09): anchor `pyproject.toml` and `src/` paths on
  `Path(__file__).resolve().parents[1]`, not cwd.
- [MINOR] Step 8 (R12 access table): DESIGN does not say where reference assemblies / API listings
  live in the per-feature model; don't invent a path silently — mark "decided in step 2" or list as
  an assumption.
- [MINOR] Step 9 (assumption 3): use `uv run --isolated --python 3.11 pytest` so the optional check
  doesn't recreate `.venv` with 3.11.
- [MINOR] Step 10 (R14): also update the spec header status from `spec-draft`.

## Verdict: REVISE

One ordering defect will fail the build at step 6; the rest is consistent with DESIGN, TRACKER and
CLAUDE.md.
