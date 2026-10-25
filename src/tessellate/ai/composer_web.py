"""What the app says about a pasted link, and about the web being unavailable.

The 22-10 bug doc, three rows:

- "Read <url> and tell me about it" searched the notes for "read", "www" and
  "thesaurus" and answered with unrelated notes. A link is a page to read: with
  web access on it is fetched and summarised (`page_analysis`); with it off the
  reply says what is needed and where the switch is.
- A failing web search (SearXNG not running) was a dead end. The reply names the
  service, says what it could not do, and links the setting that fixes it.
- Reading a page that refuses the reader says so, with the reason it gave.

Every sentence about a page is the page's own; the rest is wording about what
the app can do.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from tessellate.ai import page_analysis

_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"“”]+", re.I)
_TRAIL = ".,;:!?)]}>'\"”’"
_KEEP = re.compile(r"\b(?:save|add|bookmark|clip|remember|store|file|append|link|attach|tag|put|pin)\b", re.I)
_READ = re.compile(
    r"\b(?:read|summari[sz]e|summary|tl;?dr|tell me|what(?:'s| is| does)|explain|analy[sz]e|check|look at|open|about|says?|gist|key points|overview|review|digest)\b", re.I
)

SETTINGS_LABEL = "Open web search settings"


def url_in(question: str) -> str | None:
    """The first web address in `question`, with its scheme, or None."""
    m = _URL.search(question or "")
    if not m:
        return None
    url = m.group(0).rstrip(_TRAIL)
    if url.lower().startswith("www."):
        url = "https://" + url
    return url if urlparse(url).hostname else None


def reads_link(question: str) -> bool:
    """Whether the link in `question` is to be read: asked about, or alone.
    "Save <url> to my notes" is not (that is a note to write)."""
    url_match = _URL.search(question or "")
    if not url_match:
        return False
    rest = (question[: url_match.start()] + " " + question[url_match.end():]).strip(" .,;:!?()")
    if not rest:
        return True
    if _KEEP.search(rest):
        return False
    return bool(_READ.search(rest))


def _host(url: str) -> str:
    return (urlparse(url).hostname or url).removeprefix("www.")


def web_off(url: str) -> dict:
    """The reply to a link while web access is off: what is needed, where it is."""
    return {
        "text": (
            f"I can read {_host(url)} and tell you what it says, but web access is off, and with it off I only read what is on this computer. "
            "Turn on web search in Settings, then send the link again.\n\n" + SETTINGS_LABEL
        ),
        "offer": {"kind": "open", "surface": "settings:websearch", "label": SETTINGS_LABEL},
    }


def unreadable(url: str, reason: str) -> dict:
    return {
        "text": f"I could not read {_host(url)}: {reason.rstrip('.')}. You can open it yourself from the link, or try another page.\n\n{url}",
        "offer": None,
    }


#: The one line that starts the search service. Settings, Web search shows the
#: same command, and the Guide's web search topic repeats it.
DOCKER_ONE_LINER = "docker run -d --name searxng -p 8888:8080 -v searxng:/etc/searxng searxng/searxng"
START_STEPS = (
    "To start one with Docker, run:\n\n```\n" + DOCKER_ONE_LINER + "\n```\n\n"
    "then press Auto-detect in Settings, Web search."
)


def search_down(reason: str, searxng_url: str, provider: str) -> dict:
    """A web search that could not run, in plain words with the switch.

    With SearXNG chosen and no address saved it is not "down": it was never set
    up, and the reply says so rather than naming a service that does not exist."""
    offer = {"kind": "open", "surface": "settings:websearch", "label": SETTINGS_LABEL}
    if provider == "searxng" and not searxng_url:
        return {
            "text": (
                "Web search is not set up yet: SearXNG is chosen as the provider, but no search service address is saved. "
                "Your notes did not hold an answer either.\n\n" + START_STEPS + "\n\n" + SETTINGS_LABEL
            ),
            "offer": offer,
        }
    where = f" at {searxng_url}" if searxng_url else ""
    return {
        "text": (
            f"I tried to search the web, but the search service{where} is not answering ({reason.rstrip('.')}). "
            "Your notes did not hold an answer either. Start it or pick another provider in Settings, Web search, then ask again.\n\n"
            + START_STEPS + "\n\n" + SETTINGS_LABEL
        ),
        "offer": offer,
    }


def page_summary(page: dict, url: str) -> dict:
    """A fetched page told back: its name and size, its key points, key terms
    and sections, every point a sentence of the page."""
    found = page_analysis.analyse(page.get("blocks") or [])
    title = page_analysis._plain(str(page.get("title") or _host(url)))
    size = []
    if page.get("words"):
        size.append(f"{int(page['words']):,} words")
    if page.get("read_minutes"):
        size.append(f"{page['read_minutes']} min read")
    lines = [f"**{title}** ({', '.join([_host(url)] + size)})"]
    if found["key_points"]:
        lines += ["", "The main points:"] + [f"- {p}" for p in found["key_points"]]
    else:
        text = page_analysis._plain(str(page.get("text") or ""))[:400]
        lines += ["", text or "I could not find readable text on that page."]
    if found["terms"]:
        lines += ["", "Key terms: " + ", ".join(found["terms"]) + "."]
    heads = [s["title"] for s in found["sections"] if s["level"] > 1][:8] or [s["title"] for s in found["sections"]][:8]
    if len(heads) > 1:
        lines += ["", "Sections: " + "; ".join(heads) + "."]
    return {"text": "\n".join(lines), "offer": None}
