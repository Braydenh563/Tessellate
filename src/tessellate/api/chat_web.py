"""The web beside the notes: whether a turn may search it, a page read for an
answer, and the chips and offers that point to it.

Moved whole from `routes_chat.py` (audit AR3, gods-1101): the code is
unchanged, and `routes_chat` re-exports every name here that anything
reads, so `routes_chat.WEB_PAGES` still works. Imports run one way, down the
layer list in `routes_chat.py`'s docstring, never back to `routes_chat`.
"""

from __future__ import annotations

from tessellate.ai import composer, composer_money, composer_unplaced, composer_web, note_rank, personal, toolwords
from tessellate.api.chat_request import _StreamRequest, _composed
from tessellate.core import deps


#: How many web pages an answer with no model reads, and how much of each:
#: enough for a sentence that answers, never a crawl (decision 37).
WEB_PAGES = 3


WEB_PAGE_CHARS = 4000


def _unmatched_recents(req: _StreamRequest, prepared: dict) -> bool:
    """A question with subject words that matched no note, answered by the
    "never look empty" fallback of the newest notes: those are not evidence,
    and a model prompt carrying about 6 KB of them answers from the wrong
    notes (audit 1030 A12). A question with no subject ("my latest notes",
    "what is in my notebook"), or one with notes attached, keeps them."""
    if not str(prepared.get("search_mode") or "") == "recent" or req.body.note_ids or req.images_raw or req.skill:
        return False
    if not req.ollama.is_running() or _composed(req, True):
        return False
    from tessellate.ai.note_recency import is_recency_ask

    #: Two or more subject words is a topic ("mortgage rate zebra paddock");
    #: one is as often the notebook itself ("tell me about my notebook").
    return not is_recency_ask(req.question or "") and len(note_rank.subject(req.question or "")) >= 2


def _web_first(req: _StreamRequest, prepared: dict) -> bool:
    """The web before the notes: when no note matched, or when the turn asks
    for the web outright ("search the web for ...")."""
    return toolwords.asks_web(req.question) or (not prepared["notes"] and composer_unplaced.worthy(req.question or ""))


def _notes_chip(req: _StreamRequest) -> bool:
    """The "Search my notes instead" chip was pressed: this turn is the notes' alone (L217)."""
    return str(getattr(getattr(req, "body", None), "question", "") or "").strip() == composer_web.NOTES_INSTEAD


def _web_allowed(req: _StreamRequest) -> bool:
    """Web sources only when the person turned web search on in Settings and
    the turn may use tools (decision 43: never fetched without the toggle)."""
    try:
        on = bool(deps.get_config().get_preference("web_search_enabled", False)) and bool(req.use_tools)
        #: A spending total is the notes' sum: the web cannot know it.
        q = req.question or ""
        #: A first-person question is the person's own record: only an
        #: explicit "search the web for" sends it out (audit 1030 A1, A2).
        own = personal.about_own_notes(q) or composer_money.asks(q) or (personal.about_own_record(q) and not toolwords.asks_web(q))
        return on and not own and not _notes_chip(req)
    except Exception:  # noqa: BLE001  # no preference is off
        return False


def _web_pref_on() -> bool:
    """Settings, Web search is on (whatever this turn's mode can do with it)."""
    try:
        return bool(deps.get_config().get_preference("web_search_enabled", False))
    except Exception:  # noqa: BLE001  # no preference is off
        return False


def _web_page_row(i: int, hit: dict, page: dict) -> dict | None:
    text = str(page.get("text") or "")[:WEB_PAGE_CHARS]
    title = " ".join(str(page.get("title") or hit.get("title") or page.get("domain") or "A web page").split())
    if not text.strip():
        return None
    return {
        "id": -(i + 1), "kind": "web", "url": str(page.get("url") or hit.get("url")), "domain": page.get("domain", ""),
        "content": f"{title}\n\n{text}",
        #: The result's one line for the panel: the engine's snippet,
        #: else the page's opening.
        "snippet": " ".join(str(hit.get("snippet") or text[:200]).split())[:200],
    }


def _home_place(config) -> str:  # noqa: ANN001
    """The person's city, read off their reported timezone ("Australia/Brisbane"
    is Brisbane), for a local web search; "" for none or a bare zone (UTC)."""
    name = str(config.get_preference("timezone", "") or "").strip()
    return name.rsplit("/", 1)[-1].replace("_", " ") if "/" in name and not name.startswith("Etc/") else ""


def _offer_events(found: dict) -> list[dict]:
    """A reply with the one button it offers (an `open` offer: the setting)."""
    events: list[dict] = [{"type": "answer", "delta": found["text"]}]
    if found.get("offer"):
        events.append({"type": "offer", "offer": found["offer"]})
    return events


#: A web reply, answered or not, is not from the notes: this second meta
#: replaces the first, so the badge is not "From your notes" and Sources does
#: not list the ten notes searched first (INBOX 1550: "Sources: 10 notes"
#: under "the search service ... is not answering").
NOT_NOTES = {
    "type": "meta", "web": True, "raw_results": [], "picture_alts": {}, "picture_sizes": {}, "search_mode": "web",
    "connected_ids": [], "match_info": {}, "when_phrase": None, "as_of": None, "as_of_revisions": {},
    "answered_by": None, "ollama_running": False, "composed": False,
}


def nothing_found_meta(prepared: dict, missed: bool = True) -> list[dict]:
    """The second meta of an answer that found nothing: no rows, so no sources under it (W8 B13); [] when found."""
    return [{**NOT_NOTES, "web": False, "search_mode": prepared["search_mode"], "composed": True, "answered_by": None}] if missed else []


def _search_service() -> tuple[str, str]:
    """(SearXNG address, provider) as Settings has them, for a failure's wording."""
    from tessellate.search import websearch

    try:
        return websearch.settings_from(deps.get_config())
    except Exception:  # noqa: BLE001  # an unreadable setting is no address
        return "", ""


def _can_start_searxng() -> bool:
    """Whether the app can launch the search service itself (`composer_web.can_start`)."""
    return composer_web.can_start(*_search_service())


def _link_events(req: _StreamRequest, url: str) -> list[dict]:
    """A pasted link to be read (`composer_web`): fetched and told back when
    web access is on, else the setting that allows it. Never a notes search."""
    from tessellate.search import websearch

    if not _web_allowed(req):
        return _offer_events(composer_web.web_off(url))
    try:
        page = websearch.fetch_readable_cached(url)
    except websearch.WebSearchError as exc:
        return _offer_events(composer_web.unreadable(url, str(exc)))
    return _offer_events(composer_web.page_summary(page, url))


def _web_chip(req: _StreamRequest) -> list[dict]:
    """A miss on an ask that names the person's notes: the web is a chip to
    press, never the first stop (INBOX 1490), and only with web search on."""
    asked = req.question or ""
    if not (_web_pref_on() and composer_unplaced.says_notes(asked)) or toolwords.asks_web(asked):
        return []
    terms = composer.plan(asked).terms
    if not terms:
        return []
    return [{"type": "offer", "offer": {"kind": "ask", "label": "", "asks": [f"Search the web for {' '.join(terms[:3])}"]}}]


def _torn_events(req: _StreamRequest, prepared: dict) -> list | None:
    """Notes or the web (INBOX 1696 s): a message both sides read about equally
    gets one line and the two chips, no model, no search; the composer stays
    editable. Web off or not allowed: None, the notes answer."""
    if not prepared["notes"] or req.images_raw or req.body.answer_from or not _web_allowed(req):
        return None
    if not composer_unplaced.torn(req.question or "", prepared["notes"], web_on=True):
        return None
    asks = composer_unplaced.torn_chips(req.question or "")
    return [{"type": "answer", "delta": "Did you mean your notes or the web?"}, {"type": "offer", "offer": {"kind": "ask", "label": "", "asks": asks}}]
