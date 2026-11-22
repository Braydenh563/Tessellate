"""The OCR workspace's markup is a fetched surface (`frontend/surfaces/ocr.html`), as Settings' body is.

index.html had passed its 900 KB cap (tests/test_settings_surface_760.py) with the board panels; the
workspace opens rarely, so its 27 KB is read on its first open instead of shipped with every boot.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._surface_assets import surface_text

RAW = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_bytes().decode("utf-8")
STUB = re.search(r'<script type="text/x-surface" data-surface="ocr"([^>]*)></script>', RAW)


def test_the_page_holds_a_stub_that_names_the_file():
    assert STUB and 'data-src="/surfaces/ocr.html?v=' in STUB.group(1)
    assert 'class="card modal-card ocr-card"' not in RAW
    assert 'class="card modal-card ocr-card"' in surface_text("ocr")


def test_the_listed_ids_are_the_ids_of_the_file():
    listed = re.search(r'data-ids="([^"]*)"', STUB.group(1)).group(1).split(" ")
    assert listed == list(dict.fromkeys(re.findall(r'\sid="([^"]+)"', surface_text("ocr"))))


def test_the_file_is_served_stamped(client):
    url = re.search(r'data-surface="ocr"[^>]*data-src="([^"]+)"', client.get("/").text).group(1)
    assert re.fullmatch(r"/surfaces/ocr\.html\?v=[\w.]+-[0-9a-f]+", url)
    response = client.get(url)
    assert response.status_code == 200 and "<!--" not in response.text
