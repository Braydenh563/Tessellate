"""`POST /spelling/check` (L-chat-259): a document's lang tag picks the English list server-side."""

from __future__ import annotations

from tessellate.ai import variants


def _check(client, words, lang):
    got = client.post("/spelling/check", json={"words": words, "lang": lang})
    assert got.status_code == 200, got.text
    return got.json()


def test_british_tag_reads_the_british_list(client) -> None:
    uk = _check(client, ["colour", "color"], "en-GB")
    us = _check(client, ["colour", "color"], "en-US")
    assert uk["variant"] == "uk" and us["variant"] == "us"
    assert uk["unknown"] == ["color"]
    assert us["unknown"] == ["colour"]


def test_tag_mapping() -> None:
    assert variants.variant_of_lang("en_gb") == "uk"
    assert variants.variant_of_lang("en-CA") == "ca"
    assert variants.variant_of_lang("en") == "all"
    assert variants.variant_of_lang("ja") is None


def test_cjk_and_other_languages_are_not_checked(client) -> None:
    for lang in ("ja", "zh-CN", "ko", "fr"):
        got = _check(client, ["考え", "gibberishxyz"], lang)
        assert got == {"checked": False, "variant": None, "unknown": []}


def test_repeats_collapse_and_case_is_ignored(client) -> None:
    got = _check(client, ["Zzqxv", "zzqxv", "garden"], "en-US")
    assert got["unknown"] == ["zzqxv"]
