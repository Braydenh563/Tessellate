"""Source text: the ui sweeps drive the companion's internals from outside
avatars.js, whose file is an IIFE now; they reach them through `nmb`, so the
handles have to exist (L-ui-modernisation-75)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_companion_tick_and_pet_are_reachable_on_nmb():
    text = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    assert "nmb.tick = nameMarkBuddyTick;" in text
    assert "nmb.pet = nameMarkBuddyPet;" in text


def test_companion_internals_the_sweeps_call_are_on_nmb_inner():
    text = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    line = next(row for row in text.splitlines() if row.startswith("  nmb.inner = {"))
    for name in (
        "nameMarkBuddyBeat",
        "nameMarkBuddyCheck",
        "nameMarkBuddyDrift",
        "nameMarkBuddySeen",
        "NMB_EXPR_EVENTS",
    ):
        assert name in line


def test_phone_sidebar_openers_mount_as_each_surface_is_built():
    text = (ROOT / "frontend" / "js" / "phone-shell.js").read_text(encoding="utf-8")
    assert (
        'for (const surface of ["notes", "chat", "documents", "library"]) onSurface(surface, mountPhoneSidebarOpeners);'
        in text
    )


def test_notes_sidebar_is_wired_when_its_surface_is_built():
    text = (ROOT / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")
    assert (
        'for (const name of ["notes", "documents", "chat", "library"]) onSurface(name, wire);'
        in text
    )


def test_floating_new_buttons_follow_their_surfaces_for_notes_and_library():
    text = (ROOT / "frontend" / "js" / "phone-shell.js").read_text(encoding="utf-8")
    assert (
        'for (const name of ["notes", "library", "reminders", "timeline", "graph"]) onSurface(name'
        in text
    )


def test_graph_hit_testing_is_reachable_for_the_sweeps():
    text = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    assert "gcRequestDraw.inspect = { gcBowPoint, gcCurvedLinks, gcEdgeAtWorld, gcNodeAtWorld, gcSelectionChanged, gcWorldPoint };" in text


def test_editor_hint_is_applied_as_each_surface_is_built():
    text = (ROOT / "frontend" / "js" / "editor.js").read_text(encoding="utf-8")
    assert 'onSurface(surface, editorHintAllPlaceholders);' in text
