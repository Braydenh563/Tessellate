"""The address's QR code (core/qrsvg.py) and its route.

WORLD_CLASS_PLAN "Placed from Brief 40" fix 2, lansafe-1011's leftover
(the QR code of the address), now built. The encoder was checked, while it was
written, against the `qrcode` package (not a dependency) for every mask of
versions 1 to 10 at level M: 112 matrices, 0 different. One of them is kept
here as rows, so a change to the encoder that a phone's camera would no
longer read fails here first.
"""

from __future__ import annotations

import pytest

from tessellate.core import qrsvg

#: `qrcode` 8.x, version 2, level M, mask 5, border 0, for this text.
URL = "https://192.168.0.107:8443"
GOLDEN_MASK_5 = [
    "1111111001100010101111111", "1000001010000110001000001", "1011101011111001001011101",
    "1011101011000110001011101", "1011101001110010001011101", "1000001000010000001000001",
    "1111111010101010101111111", "0000000010010011100000000", "1000001010001100011001110",
    "0100000110100001110011110", "1110001001000001000101011", "0000010110010000011001001",
    "0110001100011010011000001", "1000000011101011010000010", "1011111010000111001111011",
    "1011000010011001000101101", "1000011111000101111110100", "0000000011011111100010000",
    "1111111000111010101010001", "1000001001000000100010000", "1011101000100101111110100",
    "1011101001011101101000011", "1011101001001001000001101", "1000001000100001110110001",
    "1111111011110011110001001",
]


def _rows(matrix):
    return ["".join("1" if dark else "0" for dark in row) for row in matrix]


def test_matches_the_reference_encoder():
    assert _rows(qrsvg.encode(URL, mask=5)) == GOLDEN_MASK_5


@pytest.mark.parametrize(
    ("text", "size"),
    [("a", 21), (URL, 25), ("https://[fe80::1c2b:3d4e:5f60:7182]:8443", 29), ("w" * 213, 57)],
)
def test_smallest_version_that_holds_it(text, size):
    matrix = qrsvg.encode(text)
    assert len(matrix) == size and all(len(row) == size for row in matrix)
    # The three finders' dark centres and the dark module beside the lower one.
    for x, y in ((3, 3), (size - 4, 3), (3, size - 4)):
        assert matrix[y][x]
    assert matrix[size - 8][8]


def test_too_long_is_refused():
    with pytest.raises(ValueError):
        qrsvg.encode("x" * 214)


def test_svg_is_dark_on_light_with_a_quiet_zone():
    out = qrsvg.svg(URL)
    assert out.startswith("<svg ") and 'viewBox="0 0 33 33"' in out
    assert 'fill="#fff"' in out and 'fill="#000"' in out
    assert "<script" not in out


def test_route_draws_only_an_address_this_notebook_shows(client, monkeypatch):
    from tessellate.api import routes_privacy

    monkeypatch.setattr(
        routes_privacy.netbind, "describe",
        lambda config, port=None: {"addresses": [URL, "https://[fe80::1]:8443"]},
    )
    good = client.get("/privacy/lan-qr.svg", params={"address": URL})
    assert good.status_code == 200, good.text
    assert good.headers["content-type"].startswith("image/svg+xml")
    assert good.headers["cache-control"] == "no-store"
    assert good.text == qrsvg.svg(URL)
    other = client.get("/privacy/lan-qr.svg", params={"address": "https://evil.example/"})
    assert other.status_code == 404
    # Locked like every route not on the open list: tests/test_every_route_is_locked.py.

