"""The owner's review 5899342467 on PR #233 (2026-11-13): the lazy parts and the early edit."""

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
MAP = (JS / "whiteboard-map.js").read_text(encoding="utf-8")
MORE = (JS / "whiteboard-map-more.js").read_text(encoding="utf-8")
WB = (JS / "whiteboard.js").read_text(encoding="utf-8")


def _block(text: str, start: str, end: str = "\n}\n") -> str:
    rest = text[text.index(start) :]
    return rest[: rest.index(end) + len(end)]


def test_the_grip_is_its_own_case_and_an_unknown_part_is_none():
    """An unknown part name used to fall through to `default` and come back
    as a resize grip; it is now null, and `part` adds nothing for it."""
    make = _block(MAP, "wbMapCache.make = function", "\n};\n")
    assert 'case "grip":' in make
    assert "default:\n      return null;" in make
    part = _block(MAP, "wbMapCache.part = function", "\n};\n")
    assert "if (!e) return null;" in part


def test_the_audio_mark_finds_the_link_mark_without_making_one():
    """`part(el, "link")` built a hidden link button on every audio topic."""
    assert 'wbMapCache.part(el, "link")?.after(mark)' not in MORE
    assert 'wbMapCache.part(el, "link", false)' in MORE


def test_an_early_edit_the_editor_never_took_over_is_put_back():
    """The render makes the new topic editable before `wbMapEditNode` opens
    it; if that open bails, the topic stayed contenteditable with no editor."""
    # Text editing moved to whiteboard-textedit.js, indented in its wrapper (L286 carve); same asserts.
    drop = _block((JS / "whiteboard-textedit.js").read_text(encoding="utf-8"), "wbBeginTextEdit.drop = (el) =>", "\n  };\n")
    assert "if (!el?._wbPreEdit) return;" in drop
    assert 'el.removeAttribute("contenteditable");' in drop
    assert 'classList.remove("wb-text-editing")' in drop
    # wbMapAddChild moved to whiteboard-map-record.js (L-whiteboard-49).
    add = _block((JS / "whiteboard-map-record.js").read_text(encoding="utf-8"), "async function wbMapAddChild(", "\n  });\n")
    finally_at = add.index("} finally {")
    assert "wbBeginTextEdit.drop(" in add[finally_at : finally_at + 400]
