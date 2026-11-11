"""Importing starts from one button over a hidden picker, and ends with an
undo (INBOX 464 (18)); a preview step sits between them since INBOX 1520
(`tests/test_import_preview.py`).

Settings, Data had three two-step imports: "Choose files" then "Import",
"Choose files" then "Import folder", "Choose file" then "Import". Each is now
one button that opens the picker, and choosing the files starts the import,
the shape the Library's Upload has. The picker's own Cancel is the way out
before; after, the toast's Undo moves exactly the notes that import made to
the recycle bin, which is why both endpoints now return their ids.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
#: The import buttons' listeners moved to settings-controls.js (2026-10-05,
#: the boot gzip budget), so the two files are read as one text.
WIRING = (ROOT / "frontend" / "js" / "settings-wiring.js").read_text(encoding="utf-8") + "\n" + (
    ROOT / "frontend" / "js" / "settings-controls.js"
).read_text(encoding="utf-8")
DATA = (ROOT / "frontend" / "js" / "settings-data.js").read_text(encoding="utf-8")

PAIRS = (
    ("import-md", "import-md-files"),
    ("import-md-folder-btn", "import-md-folder"),
    ("import-document", "import-document-file"),
)


def test_markdown_import_returns_the_ids_it_made(client):
    files = [("files", (f"n{i}.md", f"note number {i}".encode(), "text/markdown")) for i in range(3)]
    files.append(("files", ("empty.md", b"   ", "text/markdown")))
    body = client.post("/import/markdown", files=files).json()
    assert body["imported"] == 3 and len(body["ids"]) == 3
    for entry_id in body["ids"]:
        assert client.get(f"/entries/{entry_id}").status_code == 200


def test_document_import_returns_the_ids_it_made(client, monkeypatch):
    from tessellate.api import routes_settings_transfer

    monkeypatch.setattr(routes_settings_transfer.importer, "markitdown_available", lambda: True)
    monkeypatch.setattr(
        routes_settings_transfer.importer, "convert_to_markdown", lambda _p: "# One\n\nfirst\n\n# Two\n\nsecond"
    )
    body = client.post("/import/document", files={"file": ("deck.pptx", b"x", "application/x")}).json()
    assert body["imported"] == len(body["ids"]) >= 1


def test_each_import_is_one_button_over_a_hidden_picker():
    for button, picker in PAIRS:
        tag = re.search(rf'<input id="{picker}"[^>]*>', INDEX, re.S)
        assert tag and 'type="file"' in tag.group(0) and 'class="hidden"' in tag.group(0), picker
        assert re.search(rf'\$\("{button}"\)\.addEventListener\("click", \(\) => \$\("{picker}"\)\.click\(\)\)', WIRING), button
        assert re.search(rf'\$\("{picker}"\)\.addEventListener\("change"', WIRING), picker


def test_the_import_offers_undo_with_the_ids():
    assert DATA.count("undoImport(") >= 3, "both imports offer the undo"
    # Rule 1.8: the toast's Undo is an entry on the undo stack (offerUndo).
    assert "offerUndo(" in DATA


def test_no_native_file_input_is_drawn():
    """DESIGN.md "Choosing files to bring in": a button with the verb over a
    hidden picker, never the browser's own "Choose files" box beside a second
    button (the two-step shape all three imports had)."""
    for tag in re.findall(r"<input\b[^>]*>", INDEX, re.S):
        if 'type="file"' not in tag:
            continue
        hidden = re.search(r'class="[^"]*\b(hidden|visually-hidden)\b', tag) or re.search(r"\shidden[\s>]", tag)
        assert hidden, f"a visible file input: {' '.join(tag.split())[:120]}"
