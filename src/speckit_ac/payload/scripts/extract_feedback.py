"""Copy the writer-feedback section out of a judge report (docs/WORKFLOW.md §3.2, principle 5).

Usage: extract_feedback.py <judge-report.md> <out.md>
"""
import sys
from pathlib import Path

BEGIN = "<!-- WRITER-FEEDBACK:BEGIN -->"
END = "<!-- WRITER-FEEDBACK:END -->"

if len(sys.argv) != 3:
    sys.exit("Usage: extract_feedback.py <judge-report.md> <out.md>")

report = Path(sys.argv[1]).read_text(encoding="utf-8")
start, stop = report.find(BEGIN), report.find(END)
if start == -1 or stop == -1 or stop < start:
    feedback = "No feedback (the judge report has no writer-feedback markers).\n"
else:
    feedback = report[start + len(BEGIN):stop].strip() + "\n"

Path(sys.argv[2]).write_text(feedback, encoding="utf-8", newline="\n")
print(f"Wrote {sys.argv[2]}")
