"""L709, the owner 2026-11-12: on card view the open note is the last card
clicked or focused, until another is clicked or Notes is left; search ranks
its linked notes higher.

Driven in the app (2,000 notes, card view, Playwright): clicking card 1998
then typing "graph" sent `/search?q=graph&kind=note,board,map&limit=50&entry_id=1998`;
after switching to Graph the remembered card was gone."""

from __future__ import annotations

from tests._app_js import app_js_text

JS = app_js_text()


def test_a_click_or_focus_on_a_card_remembers_it() -> None:
    assert 'list?.addEventListener("pointerdown", remember);' in JS
    assert 'list?.addEventListener("focusin", remember);' in JS
    assert "if (li && list?.contains(li)) list.dataset.lastCard = li.dataset.id;" in JS


def test_search_falls_back_to_it_and_leaving_notes_forgets_it() -> None:
    assert '|| Number($("entry-list")?.dataset.lastCard) || null;' in JS
    assert '(open ? `&entry_id=${open}` : "")' in JS
    assert 'if (name !== "notes") delete $("entry-list")?.dataset.lastCard;' in JS
