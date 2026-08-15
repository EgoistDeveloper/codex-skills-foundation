#!/usr/bin/env python3
"""One-shot patch for the systematic-debugging live behavior gate."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def patch_live_harness() -> None:
    path = ROOT / "scripts/run_codex_live_smoke.py"
    replace_once(
        path,
        '''- Runtime aramak, kurmak veya indirmek için sistem klasörlerini tarama.
- Tamamlandı demeden önce node smoke-test.mjs komutunu çalıştır.
''',
        '''- İlk üretim kodu değişikliğinden önce node smoke-test.mjs komutunu çalıştır ve başarısızlığı gözlemle.
- Kaynak veya test dosyasını okumayı yeniden üretim kanıtı sayma.
- Runtime aramak, kurmak veya indirmek için sistem klasörlerini tarama.
- Tamamlandı demeden önce aynı node smoke-test.mjs komutunu yeniden çalıştır.
''',
        "live prompt reproduction order",
    )
    replace_once(
        path,
        '''} catch (error) {
  console.error("EF_SMOKE_TESTS_FAIL");
  throw error;
}
''',
        '''} catch (error) {
  // Keep the machine-readable failure marker on stdout because Codex command
  // aggregation may omit stderr for failed commands on some clients.
  console.log("EF_SMOKE_TESTS_FAIL");
  console.error(error);
  process.exitCode = 1;
}
''',
        "fixture failure marker transport",
    )


def write_skill() -> None:
    path = (
        ROOT
        / "plugins/engineering-foundation-core/skills/systematic-debugging/SKILL.md"
    )
    path.write_text(
        '''---
name: systematic-debugging
description: Diagnose a reproducible defect through evidence, ranked hypotheses, isolation, a minimal fix, and a regression guard. Use for failures, flaky tests, performance regressions, unexpected behavior, or unclear root causes. Do not use random patches as experiments or for ordinary feature implementation.
---

# Systematic Debugging

## Reproduction gate

- When a reproduction command is supplied and runnable, execute it before editing production code and record the observed failure.
- Reading source code, tests, logs, or an obvious-looking defect is not reproduction.
- Do not edit under an assumed failure. If the command cannot run, make at most one direct attempt and one bounded repository-local fallback, then report `BLOCKED` or `NOT_REPRODUCED`.
- Do not scan system directories, install or download runtimes, or borrow an unrelated environment merely to force a reproduction.
- After the fix, rerun the same reproduction command and report only the result actually observed.

## Procedure

1. Capture the exact symptom, expected behavior, input, environment, and reproduction command.
2. Classify the failure as deterministic, intermittent, blocked, or not reproduced.
3. Localize the earliest incorrect state with logs, traces, focused tests, query inspection, or binary search.
4. Reduce to the smallest reliable reproducer.
5. Rank a small set of falsifiable hypotheses.
6. Run the cheapest experiment that distinguishes the leading hypothesis.
7. Change the root cause, not the final visible symptom.
8. Add a regression guard that fails before the fix and passes after it when practical.
9. Remove temporary instrumentation and run targeted plus risk-proportional broader verification.

Change one causal variable at a time. Do not accumulate speculative edits and call the eventual green test a diagnosis. Performance claims require comparable before/after measurement. Never add a fallback that silently masks authorization failure, data corruption, or invariant violations.

If reproduction is unavailable, preserve observations, state the missing evidence, and give the safest next diagnostic action. Do not manufacture certainty merely because completion statuses look lonely.
''',
        encoding="utf-8",
        newline="\n",
    )


def patch_eval_case() -> None:
    path = ROOT / "evals/cases/debug-before-fix.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["revision"] = 2
    payload["behavior_assertions"] = [
        "Runs an available reproduction command before editing production code.",
        "Captures observed reproduction status instead of inferring it from source or tests.",
        "Runs hypothesis-discriminating experiments.",
        "Adds a regression guard for the supported cause.",
    ]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def patch_live_tests() -> None:
    path = ROOT / "tests/test_codex_live_smoke.py"
    replace_once(
        path,
        '''    def test_fixture_starts_failing_and_passes_after_supported_fix(self) -> None:
''',
        '''    def test_live_prompt_requires_pre_edit_reproduction(self) -> None:
        self.assertIn("İlk üretim kodu değişikliğinden önce", module.LIVE_PROMPT)
        self.assertIn(module.TEST_COMMAND, module.LIVE_PROMPT)
        self.assertIn("yeniden üretim kanıtı sayma", module.LIVE_PROMPT)

    def test_fixture_starts_failing_and_passes_after_supported_fix(self) -> None:
''',
        "live prompt regression test",
    )
    replace_once(
        path,
        '''            self.assertIn(module.TEST_START_MARKER, before_text)
            self.assertIn(module.TEST_FAIL_MARKER, before_text)
''',
        '''            self.assertIn(module.TEST_START_MARKER, before_text)
            self.assertIn(module.TEST_FAIL_MARKER, before_text)
            self.assertIn(module.TEST_FAIL_MARKER, before.stdout)
''',
        "failure marker stdout assertion",
    )


def patch_skill_tests() -> None:
    path = ROOT / "tests/test_skills.py"
    replace_once(
        path,
        '''    def test_no_portable_allowed_tools(self) -> None:
''',
        '''    def test_systematic_debugging_has_a_pre_edit_reproduction_gate(self) -> None:
        path = (
            ROOT
            / "plugins/engineering-foundation-core/skills/systematic-debugging/SKILL.md"
        )
        text = path.read_text(encoding="utf-8")
        self.assertIn("before editing production code", text)
        self.assertIn("is not reproduction", text)
        self.assertIn("Do not scan system directories", text)
        self.assertIn("rerun the same reproduction command", text)

    def test_no_portable_allowed_tools(self) -> None:
''',
        "systematic debugging contract test",
    )


def bump_core_version() -> None:
    path = ROOT / "catalog/plugins.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    matches = [plugin for plugin in payload["plugins"] if plugin["name"] == "engineering-foundation-core"]
    if len(matches) != 1:
        raise SystemExit("expected one engineering-foundation-core catalog entry")
    if matches[0]["version"] != "0.2.1":
        raise SystemExit(f"unexpected current core version: {matches[0]['version']}")
    matches[0]["version"] = "0.2.2"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def patch_docs() -> None:
    changelog = ROOT / "CHANGELOG.md"
    replace_once(
        changelog,
        '''- Added cached, uncached, output, reasoning, duration, and environment-validity metrics.
''',
        '''- Added cached, uncached, output, reasoning, duration, and environment-validity metrics.
- Require the core debugging skill to observe a runnable reproduction before production edits and to stop boundedly when reproduction is blocked.
- Emit fixture failure markers on stdout so failed Codex commands remain machine-detectable across clients.
''',
        "changelog debugging gate",
    )

    live_smoke = ROOT / "docs/live-smoke.md"
    replace_once(
        live_smoke,
        '''- the test runner prints explicit started, pass, and fail markers;
- a shell command returning zero after a failed test cannot become false positive evidence;
''',
        '''- the prompt requires the exact reproduction command before the first production edit and again after the fix;
- the test runner prints explicit started, pass, and fail markers, with the failure marker on stdout for stable Codex transport;
- a shell command returning zero after a failed test cannot become false positive evidence;
''',
        "live smoke validity documentation",
    )


def main() -> None:
    patch_live_harness()
    write_skill()
    patch_eval_case()
    patch_live_tests()
    patch_skill_tests()
    bump_core_version()
    patch_docs()
    print("systematic-debugging reproduction gate patch: PASS")


if __name__ == "__main__":
    main()
