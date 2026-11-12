"""A diagram's page menu hides the writing chrome (OPEN W18, owner answer Q26: hide the file chrome, Download stays first).

Driven in Chromium 2026-11-10 (1440 x 900, a fresh .mmd document, the head's ... menu): 13 rows on a markdown document, 7 on a
diagram (Download or print, Connections, History, Replace in every document, Copy app link, Model for this feature, Delete).
"""

from pathlib import Path

DOCS = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")


def test_the_writing_groups_and_rows_follow_the_file_type():
    assert 'syncDocFileType.groups = [foldDocMenuGroup("ph:layout Editor and layout", [' in DOCS and ']), foldDocMenuGroup("ph:pencil-simple While you write", [' in DOCS
    assert 'for (const el of [...(syncDocFileType.groups || []), $("doc-read-aloud"), $("doc-extract")]) el?.classList.toggle("hidden", type.ext === "mmd");' in DOCS


def test_download_stays_first_in_the_menu():
    assert "docDownloadGroup?.parentElement?.prepend(docDownloadGroup);" in DOCS
