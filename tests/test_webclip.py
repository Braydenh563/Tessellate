"""The web clipper (WORLD_CLASS_PLAN D9): `POST /links/clip`.

A page the person chose to clip is fetched once, reduced to its title, its
source address and its main text as markdown, and saved as a note. It is
the second thing in the app that goes online, so it is held to the rules the
first one (the web reader) set, and these tests are those rules:

* **Only when asked, and only when allowed.** The clip is refused, before any
  network call, while the web opt-in (`web_search_enabled`, Settings, Web
  search) is off, with a sentence that says where to turn it on.
* **Never a probe of this machine or its network** (S5,
  `core.security.public_addresses`): a non-http scheme, credentials in the
  URL, a name that resolves to a private, loopback, link-local or metadata
  address, and a redirect to any of those are all refused. Every hop is
  checked, not only the first.
* **Bounded.** A page past the size cap or slower than the time cap is
  refused rather than half-kept, and says which.
* **Nothing executable survives.** Scripts, styles, frames and handlers are
  gone from the note; links keep only http(s) targets, made absolute.

The network is never touched: `webclip._new_session` is replaced by a fake
that answers per host, and name lookups by a table.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.core import security, webclip

FIXTURES = Path(__file__).parent / "fixtures" / "clip"


# --- the fake network ------------------------------------------------------------

class FakeRaw:
    def __init__(self, body: bytes, chunk: int = 4096):
        self.body = body
        self.chunk = chunk


class FakeResponse:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code = status
        self.headers = {"content-type": "text/html; charset=utf-8", **(headers or {})}
        self._body = body
        self.encoding = "utf-8"
        self.closed = False

    @property
    def is_redirect(self):
        return self.status_code in (301, 302, 303, 307, 308) and "location" in self.headers

    is_permanent_redirect = False

    def iter_content(self, chunk_size=4096):
        # A slow network hands over a little at a time, whatever was asked.
        step = min(chunk_size, 4096)
        for i in range(0, len(self._body), step):
            yield self._body[i : i + step]

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(response=self)

    def close(self):
        self.closed = True


class FakeSession:
    """Answers by the Host header the clipper sends, so a test can script a
    redirect chain across hosts."""

    def __init__(self, pages: dict[str, FakeResponse], log: list):
        self.pages = pages
        self.log = log
        self.headers = {}

    def mount(self, *args, **kwargs):
        pass

    def get(self, url, headers=None, **kwargs):
        host = (headers or {}).get("Host", "")
        self.log.append((url, host))
        return self.pages[host]

    def close(self):
        pass


@pytest.fixture
def net(monkeypatch):
    """A table of name → addresses and host → response."""
    names: dict[str, list[str]] = {}
    pages: dict[str, FakeResponse] = {}
    log: list = []
    monkeypatch.setattr(security, "_resolve", lambda host: names.get(host, []))
    monkeypatch.setattr(webclip, "_new_session", lambda: FakeSession(pages, log))
    return names, pages, log


def page(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# --- SSRF --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "javascript:alert(1)",
        "data:text/html,<p>hi</p>",
        "http://user:pass@example.com/",
        "gopher://example.com/",
    ],
)
def test_only_plain_http_is_fetched(net, url):
    with pytest.raises(webclip.ClipRefused):
        webclip.fetch_page(url)
    assert net[2] == [], "nothing was requested"


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.5", "192.168.1.20", "172.16.3.4", "169.254.169.254", "::1", "fc00::1", "0.0.0.0"],
)
def test_a_name_that_resolves_inside_is_refused(net, address):
    names, _pages, log = net
    names["sneaky.example"] = [address]
    with pytest.raises(webclip.ClipRefused) as refused:
        webclip.fetch_page("http://sneaky.example/")
    assert "local address" in str(refused.value)
    assert log == []


def test_one_private_answer_among_public_ones_is_refused(net):
    names, _pages, log = net
    names["mixed.example"] = ["93.184.216.34", "127.0.0.1"]
    with pytest.raises(webclip.ClipRefused):
        webclip.fetch_page("https://mixed.example/")
    assert log == []


def test_a_redirect_to_a_private_address_is_refused_at_that_hop(net):
    names, pages, log = net
    names["public.example"] = ["93.184.216.34"]
    names["internal.example"] = ["10.1.2.3"]
    pages["public.example"] = FakeResponse(302, headers={"location": "http://internal.example/admin"})
    with pytest.raises(webclip.ClipRefused) as refused:
        webclip.fetch_page("http://public.example/start")
    assert "local address" in str(refused.value)
    assert [host for _url, host in log] == ["public.example"], "the private hop was never requested"


def test_a_redirect_to_a_literal_private_ip_is_refused(net):
    names, pages, log = net
    names["public.example"] = ["93.184.216.34"]
    pages["public.example"] = FakeResponse(301, headers={"location": "http://127.0.0.1:8080/"})
    with pytest.raises(webclip.ClipRefused):
        webclip.fetch_page("http://public.example/")


def test_a_redirect_to_another_scheme_is_refused(net):
    names, pages, _log = net
    names["public.example"] = ["93.184.216.34"]
    pages["public.example"] = FakeResponse(302, headers={"location": "file:///etc/passwd"})
    with pytest.raises(webclip.ClipRefused):
        webclip.fetch_page("http://public.example/")


def test_too_many_redirects_are_refused(net):
    names, pages, _log = net
    names["loop.example"] = ["93.184.216.34"]
    pages["loop.example"] = FakeResponse(302, headers={"location": "http://loop.example/again"})
    with pytest.raises(webclip.ClipRefused) as refused:
        webclip.fetch_page("http://loop.example/")
    assert "redirect" in str(refused.value)


def test_the_connection_is_pinned_to_the_checked_address(net):
    names, pages, log = net
    names["pinned.example"] = ["93.184.216.34"]
    pages["pinned.example"] = FakeResponse(200, page("docs_page.html"))
    webclip.fetch_page("http://pinned.example/docs")
    url, host = log[0]
    assert "93.184.216.34" in url and host == "pinned.example"


# --- caps --------------------------------------------------------------------------

def test_a_page_over_the_size_cap_is_refused(net, monkeypatch):
    names, pages, _log = net
    names["big.example"] = ["93.184.216.34"]
    monkeypatch.setattr(webclip, "CLIP_MAX_BYTES", 10_000)
    pages["big.example"] = FakeResponse(200, b"<p>" + b"x" * 20_000 + b"</p>")
    with pytest.raises(webclip.ClipRefused) as refused:
        webclip.fetch_page("http://big.example/")
    assert "too large" in str(refused.value)


def test_a_declared_length_over_the_cap_is_refused_before_reading(net, monkeypatch):
    names, pages, _log = net
    names["big.example"] = ["93.184.216.34"]
    monkeypatch.setattr(webclip, "CLIP_MAX_BYTES", 10_000)
    response = FakeResponse(200, b"<p>small</p>", headers={"content-length": "50000000"})
    pages["big.example"] = response
    with pytest.raises(webclip.ClipRefused):
        webclip.fetch_page("http://big.example/")


def test_a_page_slower_than_the_time_cap_is_refused(net, monkeypatch):
    names, pages, _log = net
    names["slow.example"] = ["93.184.216.34"]
    pages["slow.example"] = FakeResponse(200, b"<p>" + b"y" * 50_000 + b"</p>")
    clock = iter(range(0, 10_000, 7))
    monkeypatch.setattr(webclip.time, "monotonic", lambda: next(clock))
    with pytest.raises(webclip.ClipRefused) as refused:
        webclip.fetch_page("http://slow.example/")
    assert "too long" in str(refused.value)


def test_something_that_is_not_a_page_is_refused(net):
    names, pages, _log = net
    names["pdf.example"] = ["93.184.216.34"]
    pages["pdf.example"] = FakeResponse(200, b"%PDF-1.7", headers={"content-type": "application/pdf"})
    with pytest.raises(webclip.ClipRefused) as refused:
        webclip.fetch_page("http://pdf.example/file.pdf")
    assert "web page" in str(refused.value)


# --- extraction --------------------------------------------------------------------

def test_a_news_article_keeps_its_story_and_loses_its_furniture():
    out = webclip.extract(page("news_article.html").decode(), "https://bread.example/2026/sourdough")
    md = out["markdown"]
    assert out["title"] == "Why sourdough needs time"
    assert "slow fermentation" in md and "**slow fermentation**" in md
    assert "## The overnight rule" in md
    assert "- Feed the starter twelve hours before." in md
    # The link is absolute and the tracking parameter is gone.
    assert "[our cold proof guide](https://bread.example/guides/cold-proof)" in md
    for furniture in ("Sign in", "cookies", "premium flour", "Ten cakes", "Copyright", "dataLayer", "track()", "font-family"):
        assert furniture not in md, furniture


def test_a_page_with_no_article_tag_finds_its_body_by_its_prose():
    out = webclip.extract(page("blog_div_soup.html").decode(), "https://blog.example/local-first")
    md = out["markdown"]
    assert out["title"] == "Notes on local-first software"
    assert "primary copy of your data" in md and "outlives the company" in md
    assert "> The cloud is just someone else's computer." in md
    for furniture in ("Archive", "newsletter", "Comment by", "secret json", "enable JavaScript", "alert(1)", "onerror"):
        assert furniture not in md, furniture


def test_a_docs_page_keeps_its_code_lists_and_only_safe_links():
    out = webclip.extract(page("docs_page.html").decode(), "https://docs.example/guide/scheduler.html")
    md = out["markdown"]
    assert out["title"] == "Configuring the scheduler - Docs"
    assert "`jobs.toml`" in md
    assert '```\n[job.backup]\ncron = "0 3 * * *"\ncommand = "backup --all"\n```' in md
    assert "1. Write the file." in md and "2. Restart with *sched reload*." in md
    assert "[cron reference](https://docs.example/reference/cron.html)" in md
    assert "javascript:" not in md and "this bad link" in md
    assert "Docs built with" not in md


def test_the_note_is_title_source_and_text():
    out = webclip.extract(page("news_article.html").decode(), "https://bread.example/2026/sourdough")
    note = webclip.note_content(out, "https://bread.example/2026/sourdough")
    lines = note.split("\n")
    assert lines[0] == "# Why sourdough needs time"
    assert "Source: <https://bread.example/2026/sourdough>" in note
    assert "<script" not in note and "<style" not in note


# --- the route ---------------------------------------------------------------------

def test_the_clip_is_refused_while_the_web_is_off(client, net, monkeypatch):
    names, pages, log = net
    names["bread.example"] = ["93.184.216.34"]
    pages["bread.example"] = FakeResponse(200, page("news_article.html"))
    response = client.post("/links/clip", json={"url": "https://bread.example/2026/sourdough"})
    assert response.status_code == 403
    assert "Settings" in response.json()["detail"] and "Web search" in response.json()["detail"]
    assert log == [], "nothing was fetched while the web was off"


def test_a_clip_becomes_a_note_with_its_source(client, app_state, net):
    names, pages, _log = net
    app_state.set_preference("web_search_enabled", True)
    names["bread.example"] = ["93.184.216.34"]
    pages["bread.example"] = FakeResponse(200, page("news_article.html"))
    response = client.post("/links/clip", json={"url": "https://bread.example/2026/sourdough?utm_source=x"})
    assert response.status_code == 201, response.text
    note = response.json()
    assert note["content"].startswith("# Why sourdough needs time")
    assert note["source_url"] == "https://bread.example/2026/sourdough"
    stored = client.get(f"/entries/{note['id']}").json()
    assert "slow fermentation" in stored["content"]
    # Findable by the words on the page, which is the gate D9 names.
    hits = client.get("/search", params={"q": "fermentation"}).json()["hits"]
    assert any(hit["kind"] == "note" and hit["id"] == note["id"] for hit in hits), hits


def test_the_route_refuses_a_private_address_with_a_sentence(client, app_state, net):
    names, _pages, log = net
    app_state.set_preference("web_search_enabled", True)
    names["router.lan"] = ["192.168.1.1"]
    response = client.post("/links/clip", json={"url": "http://router.lan/"})
    assert response.status_code == 400
    assert "local address" in response.json()["detail"]
    assert log == []


def test_the_route_refuses_a_non_http_scheme(client, app_state, net):
    app_state.set_preference("web_search_enabled", True)
    response = client.post("/links/clip", json={"url": "file:///etc/passwd"})
    assert response.status_code == 400
