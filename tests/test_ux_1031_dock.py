"""Audit 1031 class 26 (N27, N37, N46): a dock keeps its list controls.

N27: Sort, Cards or Rows and Select sat in the dock's ⋯ at 1440 (a count
rule: past seven items a dock folds). Every dock now folds by width alone
(INBOX 1520). N37: a suggested tag is a button (class 28 made it one), and a batch
act hands focus back to Select. N46: a note opened from the list is a step of
the one history, so Back names the view before it."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _js(name: str) -> str:
    return (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")


def test_every_dock_folds_by_width_and_never_by_count():
    """INBOX 1520 (the owner, N27): items fold into the ⋯ only when the row runs out of room."""
    text = _js("phone-shell.js")
    assert "DOCK_FOLD_PAST" not in text and "dockItemCount" not in text and "DOCK_KEEPS_ABOVE" not in text
    fit = text.split("function fitDock(dock)", 1)[1].split("\n}\n", 1)[0]
    # Everything shown first, so the answer depends on the width alone; then the arrange zone, then the actions.
    #: A dock with nothing folded is already "everything shown", so it may ask
    #: `dockTight` before the unfold and write nothing (INBOX 1534); a folded one
    #: unfolds before it asks.
    unfold = fit.index("foldDockArrange(dock, false)")
    assert unfold < fit.index("dockTight(dock)", unfold) < fit.index("foldDockArrange(dock, true)")
    assert '!dock.querySelector(".dock-arrange-slot, .dock-action-slot, [data-folded-from]") && !dockTight(dock)' in fit
    assert "if (dockTight(dock)) foldDockActions(dock, true)" in fit
    assert "new ResizeObserver" in text and "contentRect.width" in text


def test_a_dock_in_a_template_surface_is_watched_once_it_is_built():
    """C20 (W34): Notes is a `<template data-surface>` built on its first open (X15), so its dock was not
    in the page when `initDockFolding` looked: nothing watched it and, with the connections rail open, it
    wrapped to two rows (82 px against 46) at 1366 to 1500. Each surface's docks are watched as it is built."""
    text = _js("phone-shell.js")
    init = text.split("function initDockFolding()", 1)[1].split("\n}\n", 1)[0]
    assert "watchDocks" in init and "onSurface(" in init and "SURFACES" in init
    assert "WeakSet" in init, "a dock is observed once, however many surfaces build around it"


def test_a_batch_act_hands_focus_back_to_select():
    text = _js("skills.js")
    body = text.split("function exitSelectMode()", 1)[1].split("\n}\n", 1)[0]
    assert 'restoreFocusTo(() => ($("select-btn").offsetParent ? $("select-btn")' in body


def test_a_note_opened_from_the_list_is_a_step_of_the_one_history():
    text = _js("capture-ask.js")
    assert 'recordTabVisit("notes", `note:${id}`' in text
    nav = _js("navigation.js")
    assert "title: prev ? `Back to ${entryLabel(prev)}`" in nav
