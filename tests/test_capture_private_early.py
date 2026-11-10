"""The Capture page's Private button works before quick-note.js has loaded (s14-1110).

quick-note.js wires the button but is preloaded 3 s after boot, so an early press did nothing. The boot script
capture-ask.js carries a listener that loads the file and flips the lock itself while `createNoteSafely.lock` is absent.
Driven in Chromium: a press at t=0 with the file held back 1.5 s ended pressed with the draft key set; a second press unset it.
"""

from pathlib import Path

ASK = Path(__file__).resolve().parents[1] / "frontend" / "js" / "capture-ask.js"


def test_an_early_press_loads_the_quick_note_and_flips_the_lock() -> None:
    text = ASK.read_text(encoding="utf-8")
    at = text.index('$("entry-private")?.addEventListener("click"')
    block = text[at : at + 400]
    assert "!createNoteSafely.lock" in block
    assert 'ensureModule("quickNote")' in block
    assert 'lock.flip(' in block and '"captureDraftPrivate"' in block
