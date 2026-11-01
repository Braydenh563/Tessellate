"""The product is Tessellate, formerly MemoryMap AI (INBOX 903).

The owner, 2026-10-11: "alright lets rename and retrademark to Tessellate
update absolutely everything including all the documentation and the pages
site. make sure to still note the former name though."

Branches written before the rename keep landing, so this fails on any old
name `scripts/rebrand.py` would still change; the fix is to run it. What the
script keeps (paths, files, stored values, the certificate subject, owner
quotes, history, "formerly" mentions, lines marked `brand: keep`) is its
allowlist, tested below.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("rebrand", ROOT / "scripts" / "rebrand.py")
rebrand = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rebrand)


def _run(text: str, quotes_kept: bool = False) -> str:
    return rebrand.rebrand_text(text, quotes_kept)[0]


def test_no_old_name_left_in_user_facing_files():
    left = rebrand.pending()
    assert not left, f"run `python scripts/rebrand.py`; old name left in {left}"


def test_the_name_in_copy_becomes_tessellate():
    assert _run("Welcome to MemoryMap AI. MemoryMap's tabs.") == "Welcome to Tessellate. Tessellate's tabs."
    assert _run('"Quit MemoryMap?\\n\\nThe app"') == '"Quit Tessellate?\\n\\nThe app"'
    assert _run('echo "\\nMemoryMap has stopped"') == 'echo "\\nTessellate has stopped"'
    assert _run("<h1>MemoryMap&nbsp;AI</h1>") == "<h1>Tessellate</h1>"


def test_files_paths_identifiers_and_formerly_are_kept():
    kept = [
        r"%APPDATA%\MemoryMap AI",
        "dist/MemoryMap AI/MemoryMap AI.exe",
        "MemoryMap-AI-Setup-0.4.1-windows-x86_64.exe",
        "restartMemoryMap()",
        "X-MemoryMap-Agent: atlas",
        "Tessellate (formerly MemoryMap AI)",
        "Formerly MemoryMap AI.",
        'return str(Path(base) / "MemoryMap AI")  # brand: keep',
        "# brand: keep-next\nAPP = \"MemoryMap\"",
    ]
    for text in kept:
        assert _run(text) == text, text


def test_owner_quotes_are_kept_in_the_roadmap_docs():
    quote = 'The owner: "Do it on the computer MemoryMap runs on." Then MemoryMap shipped.'
    assert _run(quote, quotes_kept=True) == (
        'The owner: "Do it on the computer MemoryMap runs on." Then Tessellate shipped.'
    )


def test_repo_url_moves_and_the_switch_can_hold_it():
    text = "https://github.com/Braydenh563/MemoryMap-AI/releases and https://braydenh563.github.io/MemoryMap-AI/"
    assert _run(text) == "https://github.com/Braydenh563/Tessellate/releases and https://braydenh563.github.io/Tessellate/"
    assert rebrand.rebrand_text(text, False, rebrand.OLD_REPO)[0] == text


def test_the_script_is_idempotent():
    text = "MemoryMap AI at https://github.com/Braydenh563/MemoryMap-AI, formerly MemoryMap AI."
    once = _run(text)
    assert _run(once) == once


def test_the_former_name_is_noted_where_people_look():
    for rel in ("README.md", "docs/index.html", "frontend/index.html", "CHANGELOG.md", "docs/CHANGELOG.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert re.search(r"formerly MemoryMap AI", text, re.I), rel
    assert "Renamed to Tessellate; formerly MemoryMap AI." in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Renamed to Tessellate; formerly MemoryMap AI." in (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8")


def test_strings_that_secure_or_find_existing_data_keep_the_old_name():
    """Changing any of these would lock a person out of their own data, or
    make a phone distrust the computer it already trusts."""
    src = ROOT / "src" / "tessellate"
    assert b'b"memorymap-bcrypt-input"' in (src / "api" / "routes_auth.py").read_bytes()
    assert '"MemoryMap AI on this computer"' in (src / "core" / "lancert.py").read_text(encoding="utf-8")
    assert 'Path(base) / "MemoryMap AI", Path(base) / "Tessellate"  # brand: keep' in (src / "core" / "config.py").read_text(encoding="utf-8")


def test_a_copy_started_before_the_rename_is_recognised():
    from tessellate.core import instance_lock

    assert instance_lock.APP_NAMES == ("Tessellate", "MemoryMap AI")
    for launcher in ("start.sh", "uninstall.sh"):
        assert '*"Tessellate"*|*"MemoryMap AI"*' in (ROOT / launcher).read_text(encoding="utf-8")
    for launcher in ("start.bat", "uninstall.bat"):
        assert 'findstr /C:"Tessellate" /C:"MemoryMap AI"' in (ROOT / launcher).read_text(encoding="utf-8")


def test_the_ocr_browser_keys_are_tessellate_and_the_old_ones_move_once():
    text = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    assert 'OCR_VIEW_KEY = "tessellate.ocr.view"' in text
    assert 'OCR_READER_KEY = "tessellate.ocr.reader"' in text
    assert "prefs.remove(`memorymap.ocr.${name}`)" in text
