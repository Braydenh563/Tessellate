"""L-chat-236 (D30): a document's language is a field the writer sets, the editor says it in a
`lang` attribute, English comes in British and American, and Japanese and Chinese are never
split into words on spaces.

The field is the `lang` key of the document's leading properties block (the key `docProse.langOf`
already read, and what an export, a sync and a version carry with no migration): one source of
truth, not a column beside it. The tests run the pure methods in node, as test_doc_spell_lang_1104."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.ai import spelling, variants

ROOT = Path(__file__).resolve().parent.parent
DOCS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
VIEW = (ROOT / "frontend" / "js" / "documents-view.js").read_text(encoding="utf-8")
SPELL = (ROOT / "frontend" / "js" / "documents-spell.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _method(name: str) -> str:
    start = DOCS.index(f"  {name}(")
    return DOCS[start : DOCS.index("\n  },", start) + 5]


def _run(call: str, *names: str):
    script = "const docProse = { " + "\n".join(_method(n) for n in names) + " };\nconsole.log(JSON.stringify(" + call + "));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
@pytest.mark.parametrize(
    ("text", "tag", "variant"),
    [
        ("plain", "", None),
        ("---\nlang: en-GB\n---\nx", "en-GB", "uk"),
        ("---\nlanguage: \"en-us\"\n---\nx", "en-US", "us"),
        ("---\nlang: en_AU\n---\nx", "en-AU", "au"),
        ("---\nlang: en-CA\n---\nx", "en-CA", "ca"),
        ("---\nlang: en-IN\n---\nx", "en-IN", "in"),
        ("---\nlang: fr\n---\nx", "fr", None),
        ("---\nlang: zh-Hans\n---\nx", "zh-Hans", None),
        ("body\n---\nlang: en-GB\n---", "", None),
    ],
)
def test_the_full_tag_and_the_english_variant_it_names(text, tag, variant):
    assert _run(f"docProse.tagOf({json.dumps(text)})", "tagOf") == tag
    assert _run(f"docProse.variantOf({json.dumps(text)})", "tagOf", "variantOf") == variant


@needs_node
@pytest.mark.parametrize(
    ("text", "tag", "want"),
    [
        ("hello", "fr", "---\nlang: fr\n---\nhello"),
        ("---\ntitle: T\n---\nhello", "en-GB", "---\ntitle: T\nlang: en-GB\n---\nhello"),
        ("---\nlang: fr\ntitle: T\n---\nhello", "de", "---\nlang: de\ntitle: T\n---\nhello"),
        ("---\nlang: fr\n---\nhello", "", "hello"),
        ("---\nlang: fr\ntitle: T\n---\nhello", "", "---\ntitle: T\n---\nhello"),
        ("hello", "", "hello"),
        ("---\r\nlang: fr\r\n---\r\nhello", "ja", "---\r\nlang: ja\r\n---\r\nhello"),
    ],
)
def test_setting_the_language_edits_only_the_properties_block(text, tag, want):
    edit = _run(f"docProse.withLang({json.dumps(text)}, {json.dumps(tag)})", "withLang")
    assert text[: edit["start"]] + edit["insert"] + text[edit["end"] :] == want


@needs_node
def test_setting_the_language_to_what_it_is_changes_nothing():
    edit = _run('docProse.withLang("---\\nlang: fr\\n---\\nx", "fr")', "withLang")
    assert edit["start"] == edit["end"] and edit["insert"] == ""


def test_the_editor_says_its_language_and_the_picker_writes_the_field():
    assert 'dom.setAttribute("lang", tag)' in DOCS.split("  paintLang() {", 1)[1].split("\n  },", 1)[0]
    assert VIEW.count("docProse.paintLang()") == 2  #: on every change to the text, and when the view mounts
    assert 'id="doc-language"' in HTML
    for tag in ("en-GB", "en-US", "fr", "de", "es", "ja", "zh"):
        assert f'value="{tag}"' in HTML.split('id="doc-language"', 1)[1].split("</select>", 1)[0]
    assert "docProse.withLang(" in DOCS and "$(\"doc-language\")" in DOCS


def test_a_document_in_british_english_is_checked_as_british():
    """The grammar ask reads the variant from the text it is asked about, so a note box or a
    document carries its own; a text with none falls back to the Settings choice."""
    ask = (ROOT / "frontend" / "js" / "documents-prose.js").read_text(encoding="utf-8").split("function docGrammarAsk(", 1)[1].split("\n}\n", 1)[0]
    assert "docSpellingVariant(text)" in ask
    fn = DOCS.split("function docSpellingVariant(", 1)[1].split("\n}\n", 1)[0]
    assert "docProse.variantOf(text)" in fn


def test_japanese_and_chinese_are_never_split_into_words_on_spaces():
    assert "docProse.cjk(lang) || packState(lang) !== \"ready\") return [];" in SPELL.split("function packFindings(", 1)[1]
    note = DOCS.split("  langNote(text) {", 1)[1].split("\n  },", 1)[0]
    assert "cjk" in note and "not written in words split by spaces" in note


@needs_node
@pytest.mark.parametrize(("lang", "yes"), [("ja", True), ("zh", True), ("ko", True), ("en", False), ("fr", False)])
def test_cjk_languages_are_named(lang, yes):
    assert _run(f"docProse.cjk({json.dumps(lang)})", "cjk") is yes


def test_british_and_american_english_are_two_lists_of_one_stock():
    us, uk, every = variants.english("us"), variants.english("uk"), variants.english()
    assert "color" in us and "colour" not in us
    assert "colour" in uk and "color" not in uk
    assert "organise" in uk and "organize" not in uk and "organize" in us and "organise" not in us
    assert "travelled" in uk and "traveled" not in uk
    #: Not a spelling pair: both countries use these.
    for word in ("practice", "program", "knife", "knives", "centre" if False else "house"):
        assert word in us and word in uk, word
    assert us < every and uk < every
    assert variants.english("off") == every and variants.english("all") == every


def test_the_others_follow_their_family_and_the_speller_hands_the_choice_on():
    assert variants.english("au") == variants.english("uk") and variants.english("in") == variants.english("uk")
    assert variants.english("ca") == every_ca()
    assert spelling.english("uk") == variants.english("uk") and spelling.english() == variants.english()


def every_ca():
    """Canada keeps -our and the doubled l with Britain, -ize and -re/-er with America."""
    ca = variants.english("ca")
    assert "colour" in ca and "color" not in ca and "organize" in ca and "organise" not in ca
    return ca
