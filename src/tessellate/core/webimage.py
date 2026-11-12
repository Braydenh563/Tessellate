"""One picture from a link, for a map topic (MINDMAP gap 8).

The clipper's rules, unchanged (`core/webclip.py`): every hop, redirects
included, goes through `public_addresses` and is pinned to the address that
passed, so a private, loopback or metadata address is never requested. What is
new is only what is kept: a raster picture (PNG, JPEG, GIF, WebP, AVIF, BMP)
under `IMAGE_MAX_BYTES`. SVG is refused on purpose: `/media/` serves from the
app's own origin and an SVG is markup that can run script.
"""

from __future__ import annotations

import time

from tessellate.core import egress, webclip

#: A picture, not a video or a poster scan: past this the link is refused.
IMAGE_MAX_BYTES = 10_000_000

_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
    "image/bmp": ".bmp",
}


def _check(response, url: str) -> str:  # noqa: ANN001
    """The suffix the answer's type earns, or a refusal with a sentence."""
    webclip.check_status(response, url)
    kind = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if kind not in _SUFFIX:
        response.close()
        raise webclip.ClipRefused("That link isn't a picture the map can keep (PNG, JPEG, GIF, WebP, AVIF or BMP).")
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > IMAGE_MAX_BYTES:
        response.close()
        raise webclip.ClipRefused("That picture is too large to keep.")
    return _SUFFIX[kind]


def _read(response, deadline: float) -> bytes:  # noqa: ANN001
    body = bytearray()
    for chunk in response.iter_content(65536):
        body.extend(chunk)
        if len(body) > IMAGE_MAX_BYTES:
            response.close()
            raise webclip.ClipRefused("That picture is too large to keep.")
        if time.monotonic() > deadline:
            response.close()
            raise webclip.ClipRefused("That picture took too long to arrive.", 502)
    return bytes(body)


@egress.labelled(lambda url, *a, **k: f"Fetching a topic's picture: {egress.short(url, 80)}")
def fetch_image(url: str) -> dict:
    """GET one public picture, checking every hop. Returns
    `{"url", "body", "suffix"}` or raises `ClipRefused`."""
    url = webclip.clean_url(url)
    deadline = time.monotonic() + webclip.CLIP_DEADLINE_SECONDS
    session = webclip._new_session()
    try:
        for _ in range(webclip.CLIP_MAX_REDIRECTS + 1):
            response = webclip._clip_hop(session, url)
            if response.is_redirect or getattr(response, "is_permanent_redirect", False):
                url = webclip._redirect_url(response, url, deadline)
                continue
            suffix = _check(response, url)
            return {"url": url, "body": _read(response, deadline), "suffix": suffix}
        raise webclip.ClipRefused("That link redirected too many times.", 502)
    finally:
        session.close()
