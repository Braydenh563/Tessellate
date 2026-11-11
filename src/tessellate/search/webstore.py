"""Pages fetched in a chat, kept on this computer for a week (CHAT_PLAN, the
web-search store). Nothing here touches the network or leaves the machine: it
is a table of what the reader already returned, with the time it was fetched,
so a source can say "fetched 2 days ago" and offer to fetch it again. The
switch is `web_store_enabled` (default on); Clear empties it."""

from __future__ import annotations

import logging
from datetime import timedelta

from tessellate.core import deps
from tessellate.core.database import WebPage, utcnow

logger = logging.getLogger(__name__)

KEEP_DAYS = 7
MAX_PAGES = 200


def _key(url: str) -> str:
    from tessellate.search.websearch import strip_tracking

    return strip_tracking(url)[:2000]


def enabled() -> bool:
    config = deps.peek_config()
    return bool(config and config.get_preference("web_store_enabled", True))


def remember(url: str, page: dict) -> None:
    """Keep (or refresh) a page; drop what is a week old or past the cap. Never raises."""
    db = deps.peek_db()
    if db is None or not enabled():
        return
    try:
        with db.session() as session:
            now = utcnow()
            session.query(WebPage).filter(WebPage.fetched_at < now - timedelta(days=KEEP_DAYS)).delete()
            key = _key(url)
            row = session.query(WebPage).filter(WebPage.url_key == key).first()
            if row is None:
                row = WebPage(url_key=key)
                session.add(row)
            row.url = str(page.get("url") or url)[:2000]
            row.title = str(page.get("title") or "")[:500]
            row.domain = str(page.get("domain") or "")[:255]
            row.text = str(page.get("text") or "")
            row.links = list(page.get("links") or [])
            row.fetched_at = now
            session.flush()
            extra = session.query(WebPage).count() - MAX_PAGES
            if extra > 0:
                oldest = session.query(WebPage.id).order_by(WebPage.fetched_at).limit(extra).all()
                session.query(WebPage).filter(WebPage.id.in_([r[0] for r in oldest])).delete(synchronize_session=False)
            session.commit()
    except Exception as exc:  # noqa: BLE001  # keeping a page must never fail a read
        logger.info("Web page not kept: %s", exc)


def ages(urls: list[str]) -> dict[str, str]:
    """{url: ISO fetch time} for the kept pages among `urls` that are under a week old."""
    db = deps.peek_db()
    if db is None or not urls:
        return {}
    keys = {_key(u): u for u in urls[:50]}
    cutoff = utcnow() - timedelta(days=KEEP_DAYS)
    with db.session() as session:
        rows = session.query(WebPage).filter(WebPage.url_key.in_(list(keys)), WebPage.fetched_at >= cutoff).all()
        return {keys[r.url_key]: r.fetched_at.isoformat() for r in rows}


def clear() -> int:
    with deps.get_db().session() as session:
        n = session.query(WebPage).delete()
        session.commit()
        return n
