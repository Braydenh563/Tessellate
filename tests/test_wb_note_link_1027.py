"""Review finding, 2026-10-27: a text box or sticky linked to a note (Link...,
A note...) saves `data.link = "#/notes/12"`, and the object validator, which
allowed only http, https and mailto, refused it with 422. An app route hash
is now kept; a script or data address is still refused."""

from __future__ import annotations

import pytest

from tests.test_whiteboard import board_client  # noqa: F401  (fixture)


@pytest.mark.parametrize("link", ["#/notes/12", "#/documents/3", "https://example.com", "mailto:a@b.c"])
def test_a_note_or_web_link_on_a_text_box_is_saved(board_client, link):  # noqa: F811
    r = board_client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": "x", "link": link}})
    assert r.status_code == 201, r.text
    assert r.json()["data"]["link"] == link


@pytest.mark.parametrize("link", ["javascript:alert(1)", "data:text/html,x", "#javascript:x", "#/notes/1\"><b>", "//evil.example"])
def test_a_script_or_odd_address_is_still_refused(board_client, link):  # noqa: F811
    r = board_client.post("/whiteboard/objects", json={"kind": "sticky", "data": {"content": "x", "link": link}})
    assert r.status_code == 422, r.text
