"""Nothing new reaches the network without somebody deciding it may.

WORLD_CLASS_PLAN section 12, S5: "move the private-IP guard into
`core/security.py` as `assert_public_url()` and call it from every outbound
fetch (bookmarks, clipper, update downloader, provider base URL)". The move is
done; this is the half that keeps it done, and it is the shape
`test_every_route_is_locked.py` already uses for the same reason: a new
outbound fetch added tomorrow reads exactly like one that was reviewed.

The rule is not "every fetch calls the guard". Most of the modules below are
*supposed* to reach an address the person set or the app installed, a local
model or a local SearXNG among them, and asserting the guard there would be
asserting the wrong thing. The rule is
that the list of modules that reach the network at all is short, written down,
and carries a sentence per line saying which kind each is. A module that turns
up here without a line is the finding.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from tests._repo_files import repo_files

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "tessellate"

#: The calls that leave this machine. `session.get`/`session.post` are not
#: here: SQLAlchemy sessions use the same two names, and the modules that
#: build a `requests.Session` are already in the list below through their
#: `requests.` calls.
OUTBOUND = {
    "requests.get", "requests.post", "requests.put", "requests.head", "requests.request",
    "requests.Session",
    # **Not only `requests`** (the rest of S5, 2026-09-24). This set used to
    # stop at the five `requests.` calls, so `core/extra_downloads.py`
    # (`urllib.request.urlopen`) and `core/embedmodels.py` (Hugging Face's
    # `snapshot_download`) fetched from the network without a line here, the
    # exact "arrives unreviewed" shape the test exists to stop. The standard
    # library's two ways out, httpx's, and Hugging Face's are named now, with
    # the call matched by its dotted name however it was imported.
    "urllib.request.urlopen", "urlopen", "urllib.request.urlretrieve", "urlretrieve",
    "http.client.HTTPConnection", "http.client.HTTPSConnection",
    "httpx.get", "httpx.post", "httpx.put", "httpx.request", "httpx.stream",
    "httpx.Client", "httpx.AsyncClient",
    "snapshot_download", "hf_hub_download",
}

#: Every module allowed to reach the network, and what it is. Two kinds:
#: "untrusted" means the URL came from somewhere the person did not type and
#: the app does not control, so it must go through
#: `core.security.public_addresses`; "configured" means the address is one the
#: person set or the app installed, where a private address is the point.
REACHES_THE_NETWORK = {
    # Untrusted: a search result, a page the person asked to open. Guarded by
    # `core.security.public_addresses`, every redirect hop re-checked, and the
    # connection pinned to the address that passed.
    "search/websearch.py": "untrusted",
    # Configured: the launcher asks its own server's /health over `localhost`
    # once a launch, to fall back to 127.0.0.1 when that name does not work.
    "__main__.py": "configured",
    # Untrusted: a page the person asked to clip (WORLD_CLASS_PLAN D9), only
    # while the web opt-in is on. The same guard on every hop, the same
    # pinning, and a cap on the whole fetch's size and time.
    "core/webclip.py": "untrusted",
    # Configured: the local model, at the address the person set. Private is
    # the normal case here and refusing it would break the product; what is
    # refused is the cloud metadata address, by `security.check_backend_url`.
    "ai/ollama_client.py": "configured",
    "ai/openai_client.py": "configured",
    # Configured: the two clients above go through this, which is `requests`
    # with a redirect off the configured host and port refused (S6).
    "ai/provider_http.py": "configured",
    "ai/captions.py": "configured",
    "api/routes_bench.py": "configured",  # this server over 127.0.0.1 only (the live budgets)  # TESSELLATE_CAPTIONS_URL, refused unless loopback
    # Configured: the captions helper the app starts itself (INBOX 1777): a
    # health check over 127.0.0.1 at the port its own child process printed.
    "ai/captions_process.py": "configured",
    # The other computer the person paired: the address they typed in Settings, on their own network, and from
    # the second press on only to the certificate they checked (sync_link.pair).
    "entry/sync_link.py": "configured",
    # Configured: the app's own SearXNG, which it downloads and starts itself.
    "search/searxng_install.py": "configured",
    # Configured: the update feed and the installer download, both pinned to an
    # https allowlist of GitHub hosts before a byte is written (S11).
    "api/routes_update.py": "configured",
    # Configured: the optional extras (OCR models and the like), each a URL
    # the app ships with a pinned SHA-256, fetched over https or from this
    # machine (`url_allowed`), and refused unless the bytes match the hash.
    "core/extra_downloads.py": "configured",
    # Configured: an embedding model from the list the app offers, by its
    # Hugging Face repo id, through `huggingface_hub`.
    "core/embedmodels.py": "configured",
}


def _dotted(node: ast.AST) -> str | None:
    """`a.b.c` for a chain of names, None for anything else (a call, a subscript)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head else None
    return None


def _calls(tree: ast.AST) -> set[str]:
    """Every call's dotted name: `requests.get`, `urllib.request.urlopen`,
    and a bare `snapshot_download` imported by name."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name:
                names.add(name)
    return names


def _fetchers() -> set[str]:
    found = set()
    for path in repo_files(SRC, suffixes=(".py",)):
        if _calls(ast.parse(path.read_text())) & OUTBOUND:
            found.add(str(path.relative_to(SRC)))
    return found


def test_every_module_that_reaches_the_network_is_written_down():
    new = _fetchers() - set(REACHES_THE_NETWORK)
    assert not new, (
        "these modules make outbound HTTP calls and are not in REACHES_THE_NETWORK: "
        + ", ".join(sorted(new))
        + ". Add a line saying whether the URL is untrusted (it must go through "
        "core.security.public_addresses) or configured (the person set it)."
    )


def test_the_list_names_modules_that_still_fetch():
    """An entry for a module that stopped fetching is an exemption nobody
    granted, waiting for the next thing to be put in that file."""
    gone = set(REACHES_THE_NETWORK) - _fetchers()
    assert not gone, f"REACHES_THE_NETWORK names modules that no longer fetch: {sorted(gone)}"


def test_the_untrusted_fetcher_goes_through_the_shared_guard():
    untrusted = [name for name, kind in REACHES_THE_NETWORK.items() if kind == "untrusted"]
    for name in untrusted:
        source = (SRC / name).read_text()
        assert "public_addresses" in source, (
            f"{name} fetches untrusted URLs but does not call core.security.public_addresses"
        )


def test_the_guard_refuses_every_way_in(monkeypatch):
    import ipaddress

    from tessellate.core import security

    def resolves_to(*addresses: str) -> None:
        monkeypatch.setattr(security, "_resolve", lambda host: list(addresses))

    resolves_to("93.184.216.34")
    assert security.public_addresses("https://example.com/") == [
        ipaddress.ip_address("93.184.216.34")
    ]

    # A scheme that is not http(s), including the ones a link in a note can
    # carry.
    for url in ("file:///etc/passwd", "ftp://example.com/x", "javascript:alert(1)"):
        with pytest.raises(security.UnsafeUrl):
            security.public_addresses(url)

    # Credentials in the URL: "http://trusted.example@evil.example/" reads as
    # one host and resolves to another.
    with pytest.raises(security.UnsafeUrl):
        security.public_addresses("http://example.com@127.0.0.1/")

    # Every address is checked, not the first: a name answering with one
    # public and one loopback address is refused.
    resolves_to("93.184.216.34", "127.0.0.1")
    with pytest.raises(security.UnsafeUrl, match="local address"):
        security.public_addresses("https://example.com/")

    # A lookup that fails is a failed check, never a pass.
    resolves_to()
    with pytest.raises(security.UnsafeUrl, match="look up"):
        security.public_addresses("https://example.com/")

    # The families of address that are local without being 127.0.0.1: the
    # LAN, link-local, and the cloud metadata service.
    # And the shared address space (100.64.0.0/10: carrier-grade NAT, Tailscale
    # nodes, Alibaba Cloud's metadata service at 100.100.100.200), which Python
    # does not call private, and the IPv4-mapped form of a private address.
    for address in (
        "10.0.0.5", "192.168.1.7", "169.254.169.254", "::1",
        "100.64.0.1", "100.100.100.200", "198.18.0.1", "::ffff:10.0.0.5",
        # NAT64 (64:ff9b::/96) wraps an IPv4 address; Python 3.13 calls the
        # wrapped metadata, loopback and LAN addresses global.
        "64:ff9b::a9fe:a9fe", "64:ff9b::7f00:1", "64:ff9b::a00:5",
    ):
        resolves_to(address)
        with pytest.raises(security.UnsafeUrl, match="local address"):
            security.public_addresses("https://example.com/")


def test_the_scan_sees_fetchers_that_do_not_use_requests():
    """The widening, pinned: each shape of call is found wherever it sits."""
    sample = ast.parse(
        "import urllib.request\n"
        "from huggingface_hub import snapshot_download\n"
        "def f():\n"
        "    urllib.request.urlopen('https://x')\n"
        "    snapshot_download(repo_id='r')\n"
    )
    assert {"urllib.request.urlopen", "snapshot_download"} <= _calls(sample) & OUTBOUND


def test_nat64_wrapping_a_public_address_stays_public(monkeypatch):
    from tessellate.core import security

    monkeypatch.setattr(security, "_resolve", lambda host: ["64:ff9b::808:808"])
    assert security.public_addresses("https://example.com/")
