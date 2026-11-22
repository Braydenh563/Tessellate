"""The boot sweep runs in CI (WORLD_CLASS_PLAN H9): `boottime.js` was the named
gate for boot cost and nothing ran it. The e2e job has the headless Chromium, so
the step lives there and must fail on a page error."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_e2e_job_runs_the_boot_sweep_and_fails_on_a_page_error() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "scratchpad/ui-sweeps/boottime.js" in ci
    assert "pageerrors +0" in ci, "a page error must fail the step"
    assert ci.index("boottime.js") > ci.index("  e2e:"), "it belongs to the Playwright job"
    assert ci.index("npx playwright install --with-deps chromium") < ci.index("boottime.js")


def test_the_sweep_library_finds_playwright_in_the_e2e_folder() -> None:
    lib = (ROOT / "scratchpad/ui-sweeps/lib.js").read_text(encoding="utf-8")
    assert "require('@playwright/test')" in lib
