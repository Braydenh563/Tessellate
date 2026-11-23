"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

Compare a code file with another document (L-documents-3): the compare menu's
first row, `Another document…`, lists the other documents and puts the chosen
one's text where a saved version's goes (`docIde.compare`), so the same inline
hunks, Reject and Stop comparing apply. Driven in the app by
`scratchpad/ui-sweeps/doccompare3.js`; the Guide says so."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDE = (ROOT / "frontend" / "js" / "documents-ide.js").read_text(encoding="utf-8")


def test_the_compare_menu_offers_another_document_and_loads_its_text():
    menu = IDE[IDE.index("async function docIdeCompareMenu()"): IDE.index("function formatDocHistoryWhen")]
    assert "Another document" in menu
    other = IDE[IDE.index("async function docIdeCompareOther("): IDE.index("function docIdeStopCompare")]
    assert "/documents?limit=" in other and "docIde.compare = " in other
    assert "currentDoc.id" in other  # the other document is never offered against itself


def test_the_guide_names_it():
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "code-files")
    assert "Compare with a saved version or another document" in body
