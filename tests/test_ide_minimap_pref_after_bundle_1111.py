"""documents-ide.js can run before documents.js declares docToolPref; the minimap checkbox is set after the bundle."""
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_the_ide_script_does_not_call_docToolPref_at_its_top_level():
    assert "docToolPref(" not in (JS / "documents-ide.js").read_text().split("docIdeToggleMinimap(event.target.checked)")[1].split("INBOX 736")[0]


def test_the_view_sets_the_minimap_box_once_the_bundle_is_in():
    text = (JS / "documents-view.js").read_text()
    # The view loads documents.js, then documents-ide.js, then sets the box (the two spokes' fixes merged).
    then = text.split('lazyScript("/js/documents.js").then(() => lazyScript("/js/documents-ide.js")).then(() => {')[1].split("});")[0]
    assert 'docToolPref("codeMinimap", false)' in then
