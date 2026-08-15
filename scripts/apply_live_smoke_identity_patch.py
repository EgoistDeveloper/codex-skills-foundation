#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().with_name("run_codex_live_smoke.py")
text = path.read_text(encoding="utf-8")
replacements = {
    '    subject_commit = git(["rev-parse", "v0.2.1^{commit}"], cwd=ROOT)\n': (
        "    # The installed candidate is materialized from this exact repository revision.\n"
        "    subject_commit = harness_commit\n"
    ),
    "    initial_candidate = run_tests(candidate_workspace)\n    if initial_baseline.returncode == 0": (
        "    initial_candidate = run_tests(candidate_workspace)\n"
        "    write_process_output(baseline_dir / \"tests-before.txt\", initial_baseline)\n"
        "    write_process_output(candidate_dir / \"tests-before.txt\", initial_candidate)\n"
        "    if initial_baseline.returncode == 0"
    ),
}
for old, new in replacements.items():
    if text.count(old) != 1:
        raise SystemExit(f"patch marker count is {text.count(old)}, expected 1: {old!r}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("live smoke identity patch: PASS")
