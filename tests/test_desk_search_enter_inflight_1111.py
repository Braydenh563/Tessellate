"""Quick search: Enter pressed while the search request is still out opens the first match when it lands
(desk-1670.md "Enter during an in-flight search fetch does nothing"). Driven in Chromium on 2026-11-11 with `/search`
held 900 ms: after the debounce, Enter, six hits arrived and nothing opened; now the first hit opens. This pins the
shape: the run Enter was pressed in is remembered, a typed letter forgets it, and only that run opens a hit."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")


def test_enter_during_the_fetch_is_remembered_for_that_run() -> None:
    keydown = JS.split('$("desk-search-text").addEventListener("keydown"')[1].split("\n  });\n")[0]
    assert "} else if (searching) enterAt = searchSeq;" in keydown
    assert keydown.index("runSearch();") < keydown.index("enterAt = searchSeq;")


def test_the_landing_run_opens_the_first_hit_only_if_it_is_the_run_enter_was_pressed_in() -> None:
    run = JS.split("async function runSearch()")[1].split("\n  }\n")[0]
    assert "if (enterAt === mine) list.querySelector(\"button\")?.click();" in run
    assert run.index("if (mine !== searchSeq) return;") < run.index("enterAt === mine")


def test_typing_forgets_a_pending_enter_and_every_end_of_a_run_clears_the_flag() -> None:
    typing = JS.split('$("desk-search-text").addEventListener("input"')[1].split("\n  });\n")[0]
    assert "enterAt = 0;" in typing
    run = JS.split("async function runSearch()")[1].split("\n  }\n")[0]
    assert run.count("searching = false;") == 3
