"""One filename helper for every download (notes audit 1031, N6/N22/N31).

A header is latin-1; a title is any script. The helper writes an ASCII
fallback plus an RFC 5987 `filename*`, so a Japanese title downloads under
its own name and never crashes the route.
"""

from urllib.parse import quote

from tessellate.api.downloads import attachment_headers, safe_filename


def test_ascii_name_stays_a_plain_quoted_filename():
    assert attachment_headers("Buy-milk.md")["Content-Disposition"] == (
        'attachment; filename="Buy-milk.md"'
    )


def test_non_latin_name_gets_an_ascii_fallback_and_filename_star():
    value = attachment_headers("日本語のメモ.md")["Content-Disposition"]
    value.encode("latin-1")
    assert 'filename="download.md"' in value
    assert "filename*=UTF-8''" + quote("日本語のメモ.md") in value


def test_mixed_name_keeps_its_ascii_part_in_the_fallback():
    value = attachment_headers("Plan-計画.md")["Content-Disposition"]
    assert 'filename="Plan-.md"' in value


def test_header_injection_characters_never_survive():
    value = attachment_headers('a"b\r\nX: y.md')["Content-Disposition"]
    assert "\r" not in value and "\n" not in value
    assert value.count('"') == 2


def test_safe_filename_keeps_unicode_letters_and_drops_paths():
    assert safe_filename("日本語 メモ", "md") == "日本語-メモ.md"
    assert safe_filename("../../etc/passwd", "md") == "etcpasswd.md"
    assert safe_filename("", "md", "note") == "note.md"


def test_export_of_a_japanese_note_downloads(client):
    created = client.post("/entries", json={"content": "# ゴルフの考え\n\nbody"}).json()
    response = client.get(f"/entries/{created['id']}/export.md")
    assert response.status_code == 200
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    assert quote("ゴルフの考え.md") in response.headers["content-disposition"]
