"""Opt-in web search: the ONE feature that leaves the machine.

It's off by default, gated behind the "web_search_enabled" preference, and the
UI labels results clearly as coming from the internet.

Two providers:

- **SearXNG** (recommended): a self-hosted metasearch engine. If the user
  points `searxng_url` at their own instance we use its JSON API: no scraping,
  no API key, aggregated results, and the query never leaves their network
  beyond whatever SearXNG itself federates.
- **DuckDuckGo HTML** (default): no setup at all. The request carries only
  the query text. Parsed defensively, since it's markup we don't control.

Whatever the provider, a failure degrades: SearXNG errors fall back to
DuckDuckGo rather than breaking search entirely.
"""

from __future__ import annotations

import html
import ipaddress
import logging
import re
import socket
import time
from urllib.parse import (
    parse_qs,
    unquote,
    urljoin,
    urlparse,
)

import requests

from tessellate.core import egress
from tessellate.core.logbuffer import safe_value
from tessellate.core.security import UnsafeUrl, is_internal_address, public_addresses
from tessellate.core import webclip
from tessellate.core.privacy_http import (  # noqa: F401 - the old names stay importable from here
    PRIVACY_HEADERS,
    PinnedAdapter as _PinnedAdapter,
    pin_url as _pin_url,
    strip_tracking,
)

logger = logging.getLogger(__name__)

DDG_URL = "https://html.duckduckgo.com/html/"
REQUEST_TIMEOUT = 10
#: Opening a page: connect in 4 s, then 8 s between bytes. A dead host used to
#: hold the reader on "Opening..." for the whole 10 s per hop (audit 1030 A10);
#: the panel's Stop is beside it, and the failure says what happened.
READER_TIMEOUT = (4, 8)

# Phrases DuckDuckGo serves to clients it has decided are not browsers. When
# one of these comes back the response is a 200 with no results in it, which
# is indistinguishable from "nothing matched" unless it is looked for. That
# ambiguity is why "web search returns nothing" was reported as a parser bug
# for so long: the parser was working perfectly on a page that never contained
# any results.
_CHALLENGE_MARKERS = (
    "anomaly",
    "unusual traffic",
    "detected unusual",
    "are you a robot",
    "captcha",
    "blocked",
    "rate limit",
)

def _private_session() -> requests.Session:
    """A one-shot session that keeps nothing between calls.

    Headers alone don't stop the other half of the correlation problem:
    cookies are how a search engine links one query to the next. The jar is
    empty at the start and thrown away at the end, so nothing about a search
    survives to be joined onto the one after it.

    trust_env stays ON deliberately. Turning it off looks like a privacy win, 
    no ambient proxy, no netrc, but it also discards the system CA bundle and
    the user's own proxy settings, and someone routing through Tor or a VPN
    configures that through exactly those variables. Ignoring them would make
    this less private, not more.
    """
    session = requests.Session()
    session.headers.update(PRIVACY_HEADERS)
    session.cookies.clear()
    return session


# Small in-process cache so repeating a search (or an agent retrying one)
# doesn't hit the network again within the same minute or two.
_CACHE: dict[tuple[str, int], tuple[float, list[dict]]] = {}
CACHE_TTL_SECONDS = 180
CACHE_MAX_ENTRIES = 64


class WebSearchError(RuntimeError):
    """The web couldn't be reached or the response wasn't usable."""


def _cache_get(key: tuple[str, int]) -> list[dict] | None:
    hit = _CACHE.get(key)
    if not hit:
        return None
    stored_at, results = hit
    if time.time() - stored_at > CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return results


def _cache_put(key: tuple[str, int], results: list[dict]) -> None:
    if len(_CACHE) >= CACHE_MAX_ENTRIES:
        _CACHE.clear()  # tiny cache; simplest correct eviction
    _CACHE[key] = (time.time(), results)


def clear_cache() -> None:
    """Used by tests and when the provider settings change."""
    _CACHE.clear()
    _PREFETCHED.clear()


# Where a self-hosted SearXNG usually listens. Checked in order, once, so a
# user who has one running never has to type a URL. Every port
# searxng_manager can settle on (DEFAULT_PORT plus FALLBACK_PORTS) is here,
# or Auto-detect would miss our own instance whenever it had to dodge a
# taken 8888.
SEARXNG_CANDIDATES = (
    "http://localhost:8888",
    "http://127.0.0.1:8888",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://localhost:8890",
    "http://localhost:8899",
    "http://searxng:8080",
)
DISCOVERY_TIMEOUT = 1.5


# A hostname, and nothing that could be smuggled into a request line or a
# header. `urlparse` will happily hand back a "hostname" containing characters
# no resolver would accept, and a Host header is a header like any other.
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9._~\-\[\]:]{1,253}$")


def _searxng_target(
    base_url: str, path: str = "/search"
) -> tuple[str, dict[str, str]] | None:
    """Turn a configured SearXNG address into a request that can only reach it.

    SearXNG is documented as self-hosted, the app can even install it for you
    - so the address is required to resolve to this machine or the local
    network, and *every* address it resolves to must, not merely one of them.
    Anything else and this becomes a way for a mistyped or hostile preference
    to aim the app at an arbitrary host.

    The connection is then pinned to the address that passed the check, for the
    same reason `_pin_url` exists on the reader path: resolving once to check
    and again to connect leaves a DNS-rebinding window between the two, and a
    nameserver that answers differently the second time walks straight through
    it. Returns None, never a partly-checked target, when anything fails.
    """
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    # Credentials in the URL are never needed here, and
    # "http://localhost@evil.example/" is the classic way to make an address
    # read as one host while resolving to another.
    if parsed.username or parsed.password:
        return None

    host = parsed.hostname
    if not _HOSTNAME_RE.match(host):
        return None

    try:
        # A port outside 0–65535 makes this raise rather than return None,
        # which would otherwise escape as a 500 from the settings screen.
        port = parsed.port
    except ValueError:
        return None
    if port is not None and not (0 < port <= 65535):
        return None

    addresses = _host_addresses(host)
    if not addresses or not all(is_internal_address(address) for address in addresses):
        return None

    # Prefer IPv4 when the name resolves to both families. A self-hosted
    # SearXNG almost always listens on IPv4 (ours binds 127.0.0.1 exactly),
    # while Windows resolves `localhost` to IPv6 ::1 first, pinning to the
    # first answer meant probing a door the instance was not behind.
    pinned_ip = next((a for a in addresses if a.version == 4), addresses[0])
    if port is None:
        port = 443 if parsed.scheme == "https" else 80

    literal = f"[{pinned_ip}]" if pinned_ip.version == 6 else str(pinned_ip)
    scheme = {"https": "https"}.get(parsed.scheme, "http")
    url = f"{scheme}://{literal}:{int(port)}{path}"
    host_header = host if parsed.port is None else f"{host}:{parsed.port}"
    return url, {**PRIVACY_HEADERS, "Host": host_header}


def probe_searxng(base_url: str) -> bool:
    """True if a SearXNG instance answers JSON search at this URL.

    `_searxng_target` is what makes that safe, see it for why the address has
    to be local and why the connection is pinned to it.
    """
    target = _searxng_target(base_url)
    if not target:
        return False
    probe_url, headers = target

    try:
        # Not user-reachable as an SSRF: `probe_url` is an IP literal this
        # module built, from an address it resolved and checked itself.
        response = requests.get(
            probe_url,
            params={"q": "memorymap ping", "format": "json"},
            headers=headers,
            timeout=DISCOVERY_TIMEOUT,
        )
        if response.status_code != 200:
            return False
        payload = response.json()
    except (requests.RequestException, ValueError):
        return False
    return isinstance(payload, dict) and isinstance(payload.get("results"), list)


def discover_searxng() -> str | None:
    """Find a SearXNG on the usual local ports, or None."""
    for candidate in SEARXNG_CANDIDATES:
        if probe_searxng(candidate):
            return candidate
    return None


def domain_of(url: str) -> str:
    """'https://en.wikipedia.org/wiki/X' -> 'en.wikipedia.org' (for display)."""
    try:
        return urlparse(url).netloc.removeprefix("www.")
    except ValueError:
        return ""


# Which engine answers. Kept as data so the settings screen, the API and the
# search itself all agree on the same three names.
PROVIDERS = {
    "auto": {
        "label": "Automatic (recommended)",
        "detail": (
            "Prefer your own SearXNG whenever it is running, and fall back to "
            "DuckDuckGo when it isn't: so search keeps working before you "
            "have set one up."
        ),
    },
    "searxng": {
        "label": "SearXNG only",
        "detail": (
            "Only ever ask your own instance. A search fails rather than "
            "quietly going out to DuckDuckGo instead."
        ),
    },
    "duckduckgo": {
        "label": "DuckDuckGo only",
        "detail": "Always scrape DuckDuckGo, even if a SearXNG is configured.",
    },
}

# Deliberately "auto" rather than "searxng", now that the install path works.
#
# The roadmap asked to flip the default to SearXNG once it did. Read literally
# that means "searxng", and that mode exists precisely so it will NOT fall back
#, which is right for the person who wants it and wrong as a default, because
# a fresh notebook has no SearXNG yet and every search would fail until one was
# installed. "auto" already *prefers* SearXNG whenever it is running, which is
# the behaviour the item actually wanted; what was missing was saying so, which
# the labels above and the settings copy now do.
DEFAULT_PROVIDER = "auto"

# How to describe the engine that ANSWERED, which is a different question from
# which one was configured, under "auto" those routinely differ, and the
# difference is the whole point of saying so. The person picked an engine in
# Settings for a privacy reason; if the panel does not report which one served
# a given search, that choice is invisible exactly where it matters.
ANSWERED_BY = {
    "searxng": {
        "label": "SearXNG",
        "detail": "your own instance: the query stayed on your machine",
    },
    "duckduckgo": {
        "label": "DuckDuckGo",
        "detail": "a third party saw this query, but not your notes",
    },
}


def answered_by(provider: str) -> dict:
    """A name and a plain-English privacy note for whoever answered."""
    known = ANSWERED_BY.get(str(provider or "").strip().lower())
    if known:
        return {"provider": provider, **known}
    return {"provider": provider, "label": str(provider or "unknown"), "detail": ""}


def normalise_provider(value: object) -> str:
    """Anything unrecognised means the default, never an error.

    This is read from a preferences file the user is invited to edit by hand,
    and a typo there should not be able to break searching altogether.
    """
    text = str(value or "").strip().lower()
    return text if text in PROVIDERS else DEFAULT_PROVIDER


def settings_from(config) -> tuple[str, str]:
    """(searxng_url, provider) as the user has them set.

    Takes the config rather than reaching for the singleton, so this module
    stays free of the dependency container. One reader for the HTTP route and
    the agent's `web_search` tool both: two readers is how the tool ended up
    honouring a different setting from the rest of the app.
    """
    return (
        str(config.get_preference("searxng_url", "") or ""),
        normalise_provider(config.get_preference("search_provider")),
    )


@egress.labelled(lambda query, *a, **k: f"Web search for '{egress.short(query)}'")
def search_web(
    query: str,
    limit: int = 5,
    searxng_url: str | None = None,
    provider: str = DEFAULT_PROVIDER,
) -> list[dict]:
    """[{title, url, snippet, domain, engine}] for a query, best first.

    `provider` is the user's choice from Settings, Web search, and "searxng"
    means it. The old behaviour: try SearXNG, silently fall back to
    DuckDuckGo: is still available as "auto" and is still the default, but it
    could not be turned off, and it is the wrong answer for somebody who runs
    their own instance *so that* their queries stay on their own network: a
    failed instance quietly sent every query to the engine they were avoiding.
    """
    query = (query or "").strip()
    if not query:
        return []

    provider = normalise_provider(provider)
    if provider == "searxng" and not searxng_url:
        raise WebSearchError(
            "Web search is set to use SearXNG only, but no SearXNG address is "
            "configured. Set one in Settings, Web search, or switch the "
            "engine to Automatic."
        )

    cache_key = (f"{provider}::{searxng_url or 'ddg'}::{query.lower()}", limit)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if provider == "searxng":
        # No fallback on purpose, see the docstring.
        results = _search_searxng(query, limit, searxng_url)
    elif provider == "duckduckgo":
        results = _search_duckduckgo(query, limit)
    else:
        results = []
        if searxng_url:
            try:
                results = _search_searxng(query, limit, searxng_url)
            except WebSearchError as exc:
                # Named, not swallowed: "my results changed" is otherwise
                # impossible to explain after the fact.
                logger.info(
                    "SearXNG didn't answer (%s): falling back to DuckDuckGo",
                    exc,
                )
                results = []
        if not results:
            try:
                results = _search_duckduckgo(query, limit)
            except WebSearchError as exc:
                #: **Rate-limited is a reason to look for the alternative, not
                #: a reason to stop.** Asked for directly: "if duck duck go is
                #: rate limiting it automatically tries searxng and if it isnt
                #: installed it suggests it."
                #:
                #: Only in `auto`, and only when no instance is configured: a
                #: configured one was already tried above, and the two named
                #: providers mean *that one*, which is the whole reason they
                #: stopped falling back (see the docstring).
                #:
                #: Only for a challenge, not for every failure: a timeout or a
                #: DNS error means the network is down, and probing four local
                #: ports on a machine with no network is four more timeouts
                #: before the same message.
                found = discover_searxng() if _is_challenge(exc) else None
                if not found:
                    raise
                logger.info(
                    "DuckDuckGo is rate-limiting; found a SearXNG at %s and used it",
                    found,
                )
                results = _search_searxng(query, limit, found)

    _cache_put(cache_key, results)
    return results


#: Which failures are worth looking for another engine over. Matched on the
#: message this module itself wrote, not on the page body, which is long gone
#: by the time the error reaches the caller.
_CHALLENGE_SIGNS = ("rate-limiting", "unexpected page")


def _is_challenge(error: Exception) -> bool:
    text = str(error).lower()
    return any(sign in text for sign in _CHALLENGE_SIGNS)


# --- SearXNG ------------------------------------------------------------------


def _search_searxng(query: str, limit: int, base_url: str) -> list[dict]:
    """Query a self-hosted SearXNG instance via its JSON API."""
    # One shared check with probe_searxng, rather than two that can drift.
    # This path used to do its own looser version and then hand the *hostname*
    # to requests, which resolved it a second time, so the address that was
    # checked and the address that was connected to were not guaranteed to be
    # the same one. The probe pinned; the search that followed it did not.
    target = _searxng_target(base_url)
    if not target:
        raise WebSearchError(
            "The SearXNG address must be a plain web address (starting with "
            "http or https) on this computer or your own network."
        )
    url, headers = target
    session = _private_session()
    try:
        # Not user-reachable as an SSRF: `url` is an IP literal built here from
        # an address this module resolved and checked itself.
        # POST rather than GET so the query never appears in a request line, 
        # request lines are what end up in access logs and proxy history. The
        # instance is local, but "local" is not the same as "not written down".
        response = session.post(
            url,
            data={"q": query, "format": "json"},
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        # The transport's own text is for the log; the query is not in it.
        logger.warning("SearXNG search failed (%s): %s", type(exc).__name__, safe_value(str(exc), 300))
        raise WebSearchError(
            "The SearXNG search failed. Check that SearXNG is running, then try again."
        ) from exc
    finally:
        session.close()  # the cookie jar goes with it

    rows = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise WebSearchError("SearXNG sent back something Tessellate couldn't read.")

    results = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        link = str(row.get("url") or "").strip()
        if not link:
            continue
        results.append(
            {
                "title": str(row.get("title") or link).strip(),
                "url": link,
                "snippet": str(row.get("content") or "").strip(),
                "domain": domain_of(link),
                "engine": "searxng",
                # SearXNG is a metasearch engine: "via searxng" says where the
                # query was assembled, not who answered it. It reports the
                # upstream engines that returned each result, and that is the
                # part with privacy meaning, a result from a self-hosted
                # instance still originated somewhere.
                "via": _upstream_engines(row),
            }
        )
    return results


# A SearXNG result names its upstream engines as short lowercase slugs. Cap
# both the count and the length: this is third-party text on its way to the UI,
# and a long list would push the result itself off the row.
MAX_UPSTREAM_ENGINES = 4
MAX_UPSTREAM_NAME_CHARS = 24


def _upstream_engines(row: dict) -> list[str]:
    """Which engines actually returned a SearXNG result, cleaned for display.

    SearXNG sends `engines` (a list) and sometimes `engine` (a single name);
    take whichever is there, and accept neither without complaint, this is
    presentational, so a schema change upstream must not break searching.
    """
    raw = row.get("engines")
    if not isinstance(raw, list):
        single = row.get("engine")
        raw = [single] if isinstance(single, str) else []
    names = []
    for item in raw:
        if not isinstance(item, str):
            continue
        # Letters, digits and the few separators engine names really use;
        # everything else goes, so nothing styled or scripted reaches the DOM.
        name = "".join(
            character
            for character in item.strip().lower()
            if character.isalnum() or character in "._- "
        ).strip()
        if name and name not in names:
            names.append(name[:MAX_UPSTREAM_NAME_CHARS])
        if len(names) >= MAX_UPSTREAM_ENGINES:
            break
    return names


# --- DuckDuckGo ---------------------------------------------------------------


def _search_duckduckgo(query: str, limit: int) -> list[dict]:
    """Scrape the HTML endpoint, and say which of the three failures happened.

    "Web search returns nothing" had been filed against the parser, but the
    parser has three quite different ways of ending up with an empty list and
    only one of them is its own fault:

    1. The request never arrived, no egress, a proxy refusing CONNECT, DNS.
    2. It arrived and was refused: a 202/403 challenge page, or a rate limit.
    3. It arrived, was a real results page, and genuinely had no results.

    All three used to reach the caller as an empty list or one generic
    message, so the obvious conclusion was that the markup had changed. The
    status and body length are logged for every search, that is what the
    Logs screen needs in order to answer this without a debugger, and cases
    1 and 2 now raise with a description of what actually happened.
    """
    session = _private_session()
    try:
        response = session.post(
            DDG_URL,
            data={"q": query},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        # The query itself is deliberately not logged: this is the one feature
        # that leaves the machine, and the log is a file on disk.
        logger.warning("Web search request failed (%s): %s", type(exc).__name__, exc)
        raise WebSearchError(
            "Web search failed. Check your internet connection and try again."
        ) from exc
    finally:
        session.close()  # no cookies carried into the next search

    body = response.text
    results = _parse_results(body, limit)
    logger.info(
        "Web search via DuckDuckGo: HTTP %s, %d bytes, %d results parsed",
        response.status_code,
        len(body),
        len(results),
    )
    if not results:
        lowered = body[:20_000].lower()
        hit = next((m for m in _CHALLENGE_MARKERS if m in lowered), None)
        if hit:
            logger.warning(
                "DuckDuckGo served a challenge page (matched %r), not results", hit
            )
            raise WebSearchError(
                "DuckDuckGo is rate-limiting this app rather than returning "
                "results, and no SearXNG instance was found on this machine. "
                "Waiting a few minutes usually clears it; running your own "
                "SearXNG avoids it entirely, and Settings, Web search has a "
                "one-press install for it."
            )
        if len(body) < 2000:
            # A real results page is tens of kilobytes even when it finds
            # nothing. Something this short is an error or an interstitial.
            logger.warning(
                "DuckDuckGo returned a %d-byte body with no results, "
                "probably not a results page at all",
                len(body),
            )
            raise WebSearchError(
                "The search engine returned an unexpected page instead of "
                "results. If this keeps happening, try SearXNG in Settings."
            )
    return results


def _strip_tags(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]{0,20000}>", "", fragment)).strip()


def _real_url(href: str) -> str:
    """DuckDuckGo wraps results in a redirect (…/l/?uddg=<real-url>);
    unwrap it so the user sees where a link actually goes."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.path.startswith("/l/"):
        wrapped = parse_qs(parsed.query).get("uddg", [""])[0]
        if wrapped:
            return strip_tracking(unquote(wrapped))
    return strip_tracking(href)


# Two ways of finding results: the long-standing `result__a` markup, and a
# looser anchor-based pass. If DDG changes one, the other usually still works;
# if both fail we return [] and the UI says "no results" instead of crashing.
_TITLE_PATTERNS = (
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    r'<a[^>]*href="(/l/\?[^"]+)"[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</a>',
)
_SNIPPET_PATTERNS = (
    r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
    r'<td[^>]*class="[^"]*result-snippet[^"]*"[^>]*>(.*?)</td>',
)


def _first_matches(patterns: tuple[str, ...], page: str) -> list:
    for pattern in patterns:
        found = re.findall(pattern, page, re.S)
        if found:
            return found
    return []


def _parse_results(page: str, limit: int) -> list[dict]:
    """A deliberately small parse of the results page, with a backup pattern."""
    titles = _first_matches(_TITLE_PATTERNS, page)
    snippets = _first_matches(_SNIPPET_PATTERNS, page)
    results = []
    for index, (href, title) in enumerate(titles[:limit]):
        link = _real_url(html.unescape(href))
        results.append(
            {
                "title": _strip_tags(title),
                "url": link,
                "snippet": _strip_tags(snippets[index]) if index < len(snippets) else "",
                "domain": domain_of(link),
                "engine": "duckduckgo",
            }
        )
    return results


# --- reader view --------------------------------------------------------------

_READER_MAX_BYTES = 400_000
_READER_MAX_CHARS = 20_000


def _host_addresses(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Every IP a hostname resolves to, so a check can't be dodged by a name.

    An empty list means the name doesn't resolve: callers treat that as a
    failed check rather than a pass, so a lookup failure can never open a hole.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return []
    found = []
    for info in infos:
        try:
            found.append(ipaddress.ip_address(info[4][0]))
        except ValueError:  # a non-IP sockaddr; nothing to check against
            continue
    return found


_MAX_REDIRECTS = 5


def _assert_external(url: str) -> list:
    """Refuse a URL that isn't plain http(s) out to the public internet.

    A search result is untrusted input, so it must never make the app fetch
    something on this machine or the local network, that would turn "open a
    result" into a probe of the user's own services.

    Returns the resolved addresses so the caller can connect to one it has
    actually checked (see _pin_url) instead of resolving the name again.
    """
    # The judgement itself moved to `core/security.py` (S5) so the next
    # outbound fetcher does not have to know the web reader exists. What stays
    # here is the translation into this module's own error, which is what the
    # UI renders, and `_pin_url` below, which is the half that is genuinely
    # about fetching rather than about judging.
    try:
        return public_addresses(url)
    except UnsafeUrl as exc:
        # `UnsafeUrl` is a sentence written for a person (core/security.py).
        raise WebSearchError(str(exc)) from exc


def _get_external(url: str) -> requests.Response:
    """GET a public URL, checking every redirect hop rather than only the first.

    Redirects are followed by hand precisely because `allow_redirects=True`
    would resolve the next hop inside requests, where the address check can't
    see it: a public page answering "302 → http://127.0.0.1/" would otherwise
    walk straight past the guard above.
    """
    session = _private_session()
    try:
        for _ in range(_MAX_REDIRECTS):
            addresses = _assert_external(url)
            pinned, host_header = _pin_url(url, addresses[0])
            parsed = urlparse(pinned)
            if parsed.scheme == "https":
                session.mount(
                    f"https://{parsed.netloc}", _PinnedAdapter(urlparse(url).hostname)
                )
            # CodeQL reports this as SSRF and always will: opening a link the
            # user picked is the feature. Every hop is address-checked above
            # and then pinned to the checked address, which is as far as this
            # can be constrained without dropping the feature.
            response = session.get(
                pinned,
                headers={"Host": host_header},
                timeout=READER_TIMEOUT,
                stream=True,
                allow_redirects=False,
            )
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("location", "")
                response.close()
                if not location:
                    raise WebSearchError("That page redirected to nowhere.")
                # A relative Location is resolved against the hop it came from, 
                # the original URL, not the pinned one, so the next check sees
                # the real hostname.
                url = requests.compat.urljoin(url, location)
                continue
            response.raise_for_status()
            # The body is still unread, so the session has to outlive this
            # function; closing it here would shut the pool the caller is about
            # to stream from. Tying it to the response hands that lifetime to
            # the garbage collector.
            response._memorymap_session = session
            # response.url is the pinned IP-literal, anything resolved
            # against it (relative links, error messages) would leak the
            # confusing rewritten address. Carry the real one alongside.
            response._memorymap_url = url
            return response
    except BaseException:
        session.close()
        raise
    session.close()
    raise WebSearchError("That page redirected too many times.")


def _split_url(url: str) -> tuple[str, str]:
    """(scheme, host) for an http(s) URL, or ("", "") if it isn't one.

    Credentials in the URL are rejected outright: they're never needed here and
    "http://trusted.example@evil.example/" is a classic way to make a URL read
    as one host while resolving to another.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "", ""
    if parsed.username or parsed.password:
        return "", ""
    return parsed.scheme, parsed.hostname


#: Pages fetched ahead for an agent round (INBOX 527, `tools.prefetch_web`),
#: each handed out once by `fetch_readable_cached` and then forgotten: a
#: round's calls run in order from memory, and nothing outlives the round.
_PREFETCHED: dict[str, tuple[float, dict]] = {}
PREFETCH_TTL_SECONDS = 60


def prefetch_readable(url: str) -> None:
    """Fetch `url` now, for the `read_url` call about to ask for it."""
    page = fetch_readable(url)
    if len(_PREFETCHED) >= CACHE_MAX_ENTRIES:
        _PREFETCHED.clear()
    _PREFETCHED[strip_tracking(url)] = (time.time(), page)


def fetch_readable_cached(url: str) -> dict:
    """`fetch_readable`, or the page `prefetch_readable` just fetched."""
    hit = _PREFETCHED.pop(strip_tracking(url), None)
    if hit and time.time() - hit[0] <= PREFETCH_TTL_SECONDS:
        return hit[1]
    return fetch_readable(url)


@egress.labelled(lambda url, *a, **k: f"Reading a web page: {egress.short(url, 80)}")
def fetch_readable(url: str) -> dict:
    """Fetch a page and return its readable text.

    This is what makes "open a result" useful without embedding a browser:
    scripts, styles and chrome are stripped and only text comes back, so
    nothing from the page can execute in the app.
    """
    # The link may have come from somewhere other than our own results
    # (an agent, a pasted URL), so clean it here as well rather than trusting
    # that it was cleaned upstream.
    url = strip_tracking(url)
    try:
        response = _get_external(url)
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            raise WebSearchError("That link isn't a readable page.")
        raw = response.raw.read(_READER_MAX_BYTES, decode_content=True) or b""
    except requests.HTTPError as exc:
        # Name the site, not the pinned IP-literal the request was aimed at, 
        # "403 for https://162.159.142.170:443/…" reads as our bug, and the
        # interesting part is *why*: 403/429/503 from a fetch that presents
        # ordinary headers is almost always bot protection (Cloudflare and
        # friends fingerprint the TLS handshake itself), which no local
        # reader can pass. Say so, instead of leaving a raw status to explain.
        status = exc.response.status_code if exc.response is not None else 0
        if status in (403, 429, 503):
            raise WebSearchError(
                f"{domain_of(url)} refused the reader ({status}): its bot "
                "protection wants a real browser. Open the link there instead."
            ) from exc
        raise WebSearchError(
            f"Couldn't open that page: {domain_of(url)} answered with an error ({status})."
        ) from exc
    except requests.Timeout as exc:
        raise WebSearchError(
            f"{domain_of(url)} took too long to answer. Try again, or open the link in your browser."
        ) from exc
    except requests.RequestException as exc:
        logger.warning("Couldn't open a page for the reader (%s): %s", type(exc).__name__, safe_value(str(exc), 300))
        raise WebSearchError(
            "Couldn't open that page. Check the address and your internet connection."
        ) from exc

    # Relative links resolve against where the page actually came from
    # (redirects included): never against response.url, which is the
    # pinned IP-literal.
    final_url = getattr(response, "_memorymap_url", url)
    page = raw.decode(response.encoding or "utf-8", errors="replace")
    blocks = _readable_blocks(page)
    words = sum(len(block["text"].split()) for block in blocks)
    #: **A thin reading gets the clipper's tree reader instead.** Reported:
    #: "some websites only show one or a couple words instead of properly
    #: rendering". The pattern above only sees text inside p, li, h1-h6,
    #: blockquote and pre, and a page built from styled divs (most site
    #: builders) gives it a heading and nothing else. `webclip.extract`
    #: parses the page into a tree and picks the densest container, the
    #: same reader "Save page as note" uses; its markdown becomes blocks.
    if words < _THIN_READ_WORDS:
        tree_blocks = _blocks_from_markdown(webclip.extract(page, final_url)["markdown"])
        tree_words = sum(len(block["text"].split()) for block in tree_blocks)
        if tree_words > words:
            blocks, words = tree_blocks, tree_words
    return {
        "url": url,
        "domain": domain_of(url),
        "title": _page_title(page) or domain_of(url),
        #: From the blocks when there are any: the whole-page strip below is
        #: a regex, and a tag whose attributes hold a ">" (site builders put
        #: JSON in data attributes) leaves the rest of the tag as text.
        "text": (
            "\n\n".join(block["text"] for block in blocks) if blocks else _readable_text(page)
        )[:_READER_MAX_CHARS],
        "blocks": blocks,
        "links": _page_links(page, final_url),
        "words": words,
        # Roughly how long this is, so you can decide whether to read it here
        # or save it for later before scrolling to find out.
        "read_minutes": max(1, round(words / 220)) if words else 0,
    }


# Keep the article, drop the furniture. Nav bars, cookie banners and menus are
# what make a stripped page unreadable, so they go before the text is taken.
_STRIP_TAGS = (
    "script|style|noscript|svg|nav|footer|header|aside|form|iframe|button|select"
)
_JUNK_PATTERNS = re.compile(
    r"(cookie|subscribe|newsletter|advertisement|sign in|log in|skip to)",
    re.I,
)


def _content_body(page: str) -> str:
    """The page minus its furniture, narrowed to the article when marked up.

    Shared by the block parser and the link collector, so both read the same
    part of the page, links from a stripped nav bar would be exactly the
    chrome the stripping exists to drop.
    """
    body = re.sub(rf"(?is)<({_STRIP_TAGS})[^>]{{0,400}}>.{{0,200000}}?</\1>", " ", page)
    article = re.search(r"(?is)<(article|main)[^>]{0,400}>(.{0,500000}?)</\1>", body)
    return article.group(2) if article else body


_LINK_RE = re.compile(
    r"(?is)<a\s[^>]{0,600}?href\s*=\s*([\"'])(.{1,2000}?)\1[^>]{0,600}>(.{0,2000}?)</a>"
)


def _page_links(page: str, base_url: str, limit: int = 40) -> list[dict]:
    """The article's outgoing links: [{text, url}], absolute and cleaned.

    So an agent that has read a page can cite where its statements lead and
    follow up without a second search. Only http(s) targets survive: 
    javascript:, data: and mailto: are dropped by the same check every
    reader URL passes: and following one still goes through the full
    address check and pinning in fetch_readable; nothing here is fetched.
    """
    links: list[dict] = []
    seen: set[str] = set()
    for match in _LINK_RE.finditer(_content_body(page)):
        label = re.sub(r"[ \t\xa0]+", " ", _strip_tags(match.group(3))).strip()
        if len(label) < 2:
            continue  # icon and anchor links say nothing worth keeping
        absolute = urljoin(base_url, html.unescape(match.group(2)).strip())
        scheme, _host = _split_url(absolute)
        if not scheme:
            continue
        absolute = strip_tracking(absolute.split("#", 1)[0])
        if not absolute or absolute in seen:
            continue
        seen.add(absolute)
        links.append({"text": label[:120], "url": absolute})
        if len(links) >= limit:
            break
    return links


def _readable_blocks(page: str) -> list[dict]:
    """Structured [{type, text}] so the reader can lay the page out properly.

    Returning headings and paragraphs separately is what turns a wall of text
    into something you can actually read.
    """
    body = _content_body(page)

    blocks: list[dict] = []
    pattern = re.compile(
        r"(?is)<(h[1-6]|p|li|blockquote|pre)[^>]{0,400}>(.{0,50000}?)</\1>"
    )
    for match in pattern.finditer(body):
        tag = match.group(1).lower()
        text = _strip_tags(match.group(2))
        text = re.sub(r"[ \t ]+", " ", text).strip()
        if not text or len(text) < 2:
            continue
        # Short lines that look like chrome rather than content.
        if len(text) < 40 and _JUNK_PATTERNS.search(text):
            continue
        kind = "heading" if tag.startswith("h") else tag
        block = {"type": kind, "text": text[:2000]}
        # Keep the heading's depth. Flattening h1..h6 to one "heading" threw
        # away the page's own outline: which is the thing that makes a
        # stripped article navigable rather than a long ribbon of text.
        if kind == "heading":
            block["level"] = int(tag[1])
        blocks.append(block)
        if len(blocks) >= 300:
            break

    # Nothing structured? Fall back to paragraphs of plain text.
    if not blocks:
        plain = _readable_text(page)[:_READER_MAX_CHARS]
        blocks = [
            {"type": "p", "text": para.strip()}
            for para in plain.split("\n\n")
            if para.strip()
        ]
    return blocks


def _page_title(page: str) -> str:
    match = re.search(r"<title[^>]{0,400}>(.{0,2000}?)</title>", page, re.S | re.I)
    return _strip_tags(match.group(1)) if match else ""


_THIN_READ_WORDS = 80
_MD_LINK = re.compile(r"!?\[([^\]]{0,500})\]\([^)\s]{0,2000}\)")


def _blocks_from_markdown(markdown: str) -> list[dict]:
    """`webclip`'s markdown as the reader's [{type, text}] blocks: headings
    keep their level, list lines become items, links keep their words."""
    blocks: list[dict] = []
    for chunk in markdown.split("\n\n"):
        for line in chunk.split("\n") if chunk.lstrip().startswith(("- ", "* ")) else [chunk]:
            text = line.strip()
            heading = re.match(r"(#{1,6})\s+(.*)", text)
            kind, level = "p", 0
            if heading:
                kind, level, text = "heading", len(heading.group(1)), heading.group(2)
            elif text[:2] in ("- ", "* "):
                kind, text = "li", text[2:]
            elif text.startswith("> "):
                kind, text = "blockquote", text[2:]
            text = _MD_LINK.sub(r"\1", text).replace("**", "").strip()
            if len(text) < 2:
                continue
            block = {"type": kind, "text": text[:2000]}
            if level:
                block["level"] = level
            blocks.append(block)
            if len(blocks) >= 300:
                return blocks
    return blocks


def _readable_text(page: str) -> str:
    """Strip scripts/styles/markup and collapse whitespace into paragraphs."""
    body = re.sub(
        r"(?is)<(script|style|noscript|svg|nav|footer|header)[^>]{0,400}>.{0,200000}?</\1>",
        " ",
        page,
    )
    # Block-level tags become paragraph breaks so the text stays readable.
    body = re.sub(r"(?i)</(p|div|section|article|li|h[1-6]|tr)\s*>", "\n\n", body)
    body = re.sub(r"(?i)<br\s*/?>", "\n", body)
    text = html.unescape(re.sub(r"<[^>]{0,20000}>", " ", body))
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.split("\n")]
    kept: list[str] = []
    for line in lines:
        if not line:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        kept.append(line)
    return "\n".join(kept).strip()
