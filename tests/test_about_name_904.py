"""INBOX 904 B15: the owner wants the app marketed as "Tessellate Notes",
"Tessellate for short". About carries the long name as its heading and the
short name in the line under it; the window title and the rest stay Tessellate."""

from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")


def test_about_names_the_app_tessellate_notes_and_tessellate_for_short():
    about = HTML[HTML.index('id="settings-about"'):].split("</section>", 1)[0]
    assert "<h3>Tessellate Notes</h3>" in about
    assert "Tessellate for short. Formerly MemoryMap AI." in about
