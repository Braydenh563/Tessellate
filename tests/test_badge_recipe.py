"""One drawing for a provenance word (INBOX 437).

The owner: "make sure the badges are the same style across the app". Before,
"Built-in" was a hairline box in Settings and bare text on the Library's
skill cards, and "you set this" was a third drawing. DESIGN.md's recipe
index names `chip item-label` for every one of them;
`scratchpad/ui-sweeps/badges.js` measures it in the browser.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import JS_DIR

WORDS = ("Built-in", "Edited", "Yours", "you set this")


def _js() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(JS_DIR.glob("*.js")))


def test_every_provenance_chip_is_the_label_recipe():
    js = _js()
    for word in ("Built-in", "Edited"):
        for match in re.finditer(rf'chip\([^;\n]*"{word}"[^;\n]*\)', js):
            assert "item-label" in match.group(0), match.group(0)


def test_the_retired_drawings_stay_retired():
    css = "\n".join(p.read_text(encoding="utf-8") for p in sorted((JS_DIR.parent / "css").glob("*.css")))
    js = _js()
    for name in ("sampling-source-user", "skill-badge-custom"):
        assert name not in css and name not in js, name


def test_the_library_card_and_the_sliders_use_it():
    js = _js()
    assert "`chip item-label skill-badge" in js
    assert '"chip item-label sampling-source"' in js
    assert 'classList.toggle("is-yours", overridden)' in js


def test_a_named_items_actions_are_its_own_column():
    js = _js()
    #: templates, personas and custom skills: the actions beside the row, not in it
    assert js.count("li.append(row, actions)") >= 3


#: Every status word (INBOX 461 (1), 468): the words a badge says about the
#: state of a thing (installed, ready, in use, fits) are the same recipe as
#: the provenance words above, the tone on the edge and the icon.
STATUS_WORDS = (
    "Installed", "Not ready yet", "Fits", "Tight fit", "Too big here", "In use for",
    "Download cancelled", "Our starting pick", "confirms first", "online", "in use",
    "is ready", "can't read yet", "Installing Tesseract",
)


def test_every_status_badge_is_the_label_recipe():
    js = _js()
    seen = set()
    for match in re.finditer(r"chip\((`[^`]*`|\"[^\"]*\")\s*,\s*(`[^`]*`|\"[^\"]*\")", js):
        label, cls = match.group(1), match.group(2)
        for word in STATUS_WORDS:
            if word in label:
                seen.add(word)
                assert "item-label" in cls, match.group(0)
    # The fit words live in a table, not a chip() call.
    fit = js[js.index("const FIT_WORDS = {"):][:400]
    assert fit.count('tone: "item-label') == 3, fit
    assert {"Installed", "Not ready yet", "confirms first", "online", "In use for"} <= seen


def test_status_badges_are_never_a_fill_again():
    """The fills the status words had (a green, a warn and an accent pill, and
    a grey one) and the per-surface colour rules that drew them are gone; a
    hand-built status badge cannot come back under those names."""
    css = "\n".join(p.read_text(encoding="utf-8") for p in sorted((JS_DIR.parent / "css").glob("*.css")))
    js = _js()
    assert "extras-installed" not in css and "extras-installed" not in js
    assert ".ocr-engine-chip.is-warn" not in css
    assert 'badge.className = `chip item-label${running ? " is-ok" : ""}`' in js
    index = (JS_DIR.parent / "index.html").read_text(encoding="utf-8")
    assert 'id="searxng-host-state" class="chip item-label"' in index
    # The recipe reaches every surface, not three.
    assert ":is(.entry-meta, .skill-card-header, .sampling-row, body) .chip.item-label {" in css
    assert ".chip.item-label.is-ok" in css and ".chip.item-label.is-warn" in css
    # A status word is never drawn with the filing chips' fills.
    for call in re.finditer(r"chip\(([^;\n]*?),\s*\"(confidence|review|tag)\"\)", js):
        assert not any(w in call.group(1) for w in STATUS_WORDS), call.group(0)


def test_a_model_cards_badges_are_a_row_of_their_own():
    """INBOX 468: in the foot beside the action they wrapped into a ragged
    stack. A row of their own, one line, above the actions."""
    models = (JS_DIR / "settings-models.js").read_text(encoding="utf-8")
    card = models[models.index("function buildModelCard("):models.index("function updateModelProgress(")]
    assert "if (badges.children.length) card.appendChild(badges);" in card
    assert "actions.appendChild(badgesNode)" not in card
    css = (JS_DIR.parent / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    rule = css[css.index(".model-card-badges {"):][:200]
    assert "flex-wrap: nowrap" in rule


def _css() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((JS_DIR.parent / "css").glob("*.css")))


def test_a_chips_height_floor_survives_the_untrimmed_words():
    """INBOX 503 trimmed a chip's words to the x-height band; INBOX 592 took
    the trim off (a trimmed chip beside the untrimmed date sat on another
    centre line in Segoe UI; `tests/test_icon_label_align.py` holds the
    recipe now). The floor it added stays: zero specificity, so every
    family's own floor wins."""
    css = _css()
    assert re.search(r":where\(\.chip\)\s*\{\s*min-height: 1\.125rem;", css)


def test_a_chips_icon_gap_is_a_token():
    css = _css()
    assert re.search(r"\n\.chip\s*\{\s*gap: var\(--space-1\);\s*\}", css)


def test_every_chip_builder_puts_its_words_in_a_span():
    """`chip()` wraps bare words in `.ph-text`, so every chip's words are one
    element a rule can reach (the ellipsis, the facts line's shrink)."""
    js = (JS_DIR / "app.js").read_text(encoding="utf-8")
    words = js[js.index("function chipWords("):]
    assert 'className: "ph-text"' in words[: words.index("\n}\n")]
    body = js[js.index("function chip(text"):]
    assert "chipWords(span, text)" in body[: body.index("\n}\n")]



def test_the_timeline_marks_are_even_pixels():
    """INBOX 503: the rail's glyphs sat 0.5 to 1px off their circles because a
    18.4px circle and a 12.88px glyph box leave a fractional gap that the two
    round differently. An even circle and glyph box leave whole pixels."""
    css = (JS_DIR.parent / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")
    assert "--timeline-mark: round(1.15rem, 2px);" in css
    assert ".timeline-row-mark > .ph" in css and "round(calc(var(--text-xs) * 1.15), 2px)" in css


def test_no_hand_built_chip_takes_bare_text():
    """A chip made by hand (`el.className = "chip ..."`) gives its words to
    `chipWords`, never `el.textContent =`, which leaves them outside the
    `.ph-text` span the recipe trims (the contents jump chip, "On this day",
    chat's "+N", and the rest were found this way)."""
    found = []
    for path in sorted(JS_DIR.glob("*.js")):
        lines = path.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            m = re.search(r'(\w+)\.className = [`"\'](?:[^`"\']*\s)?chip[\s`"\']', line)
            if not m:
                continue
            for nxt in lines[i + 1 : i + 8]:
                if re.match(rf"\s*{m.group(1)}\.textContent =", nxt):
                    found.append(f"{path.name}:{i + 1}")
                    break
    assert not found, found


def test_a_status_label_is_a_tinted_pill_without_an_edge():
    """INBOX 553 (c), the owner's decision of 2026-10-05: status labels app-wide
    are a tinted pill with no edge, matching the meta chips. The ratchet: the
    label's own rule is the `--chip-bg` tint at the pill radius with `border:
    0`; its tones are tints, never an edge; and no other rule anywhere gives a
    `.chip.item-label`, or a status badge drawn as one, a border colour back."""
    css = "\n".join(p.read_text(encoding="utf-8") for p in sorted((JS_DIR.parent / "css").glob("*.css")))
    base = css[css.index(":is(.entry-meta, .skill-card-header, .sampling-row, body) .chip.item-label {") :]
    base = base[: base.index("}")]
    assert "background: var(--chip-bg)" in base and "border: 0" in base, base
    pill = css[css.index("body .chip.item-label,\n.entry-meta .chip.item-label {") :]
    assert "border-radius: var(--radius-pill)" in pill[: pill.index("}")]
    for tone in ("is-yours", "is-ok", "is-warn"):
        rule = css[css.index(".chip.item-label." + tone + " {") :]
        rule = rule[: rule.index("}")]
        assert "background:" in rule and "border" not in rule, (tone, rule)
    bare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for selector, body in re.findall(r"([^{}]*item-label[^{}]*)\{([^}]*)\}", bare):
        assert not re.search(r"border(?:-color)?\s*:(?!\s*(?:0|none|transparent)\b)", body), selector.strip()
    # The status badges that were drawn on their own now are the label, or its tint.
    js = _js()
    assert '"chip item-label library-read-badge is-read is-ok"' in js
    read = css[css.index(".msg-attachment-read-badge {") :]
    read = read[: read.index("}")]
    assert "border: 0" in read and "radius-pill" in read



def test_the_badge_sweep_measures_against_the_recipes_target():
    """One target (DESIGN.md, the label row): an icon beside words lands on
    the words' cap-height centre (INBOX 592). badgealign.js measured against
    the x-height band (INBOX 503) and read a cap-aligned skill fact 1.5px
    high; it reads the font's cap height now, as iconalign.js does."""
    sweeps = Path(__file__).resolve().parents[1] / "scratchpad" / "ui-sweeps"
    js = (sweeps / "badgealign.js").read_text(encoding="utf-8")
    py = (sweeps / "badgealign.py").read_text(encoding="utf-8")
    assert "measureText('H')" in js and "measureText('x')" not in js
    assert 'capcentre(tr, it["cap"])' in py and "xcentre" not in py
    design = (Path(__file__).resolve().parents[1] / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "the x-height band INBOX 503 measured against is retired" in design


# An empty chip is hidden, so a badge filled later leaves no stub (INBOX 803).

ROOT = Path(__file__).resolve().parents[1]


def _front_css(name: str) -> str:
    return (ROOT / "frontend" / "css" / name).read_text(encoding="utf-8")


def test_a_badge_with_no_text_is_hidden():
    css = _front_css("01-forms-settings.css")
    block = css[css.index(".chip:empty {"):].split("}", 1)[0]
    assert "display: none" in block
    # The two Ask badges are empty in the markup and filled by renderChatMeta,
    # so they are what the rule is for; a space inside would defeat :empty.
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<span id="answered-by" class="chip item-label answer-model"></span>' in html
    assert '<span id="search-mode" class="chip"></span>' in html
