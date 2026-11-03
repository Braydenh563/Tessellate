"""An icon beside words sits on the words' cap-height centre (INBOX 592).

The owner, with three screenshots from Windows: "these badges and metadata
dont have their icons vertically aligned with their text, probably the case
elsewhere as well". Two rounds before this (INBOX 494, 503) measured clean in
the sandbox, whose UI font is DejaVu Sans, and wrong on the owner's Segoe UI:
a flex row centres the words' box, whose middle is the font's ascent and
descent, and Segoe's tall ascent puts that middle 0.064em above its
capitals. The corrections were per family (a chip's words trimmed to the
x-height band, fixed drops on chip and status bar icons), calibrated in the
one font nobody on Windows sees, and a trimmed chip beside an untrimmed date
put the facts line on two centres.

The recipe (DESIGN.md, "An icon beside words"): the gap is read from the live
font (`measureLabelOptics`, settings.js) into `--ph-cap-dy`; `.ph-lead` and
`.ph-trail` move by it; nobody trims a label's words or hand-sets a
`translate` on a label's icon. `scratchpad/ui-sweeps/iconalign.js` measures
it (`FONT=segoe` for the owner's metrics).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "frontend" / "css"


def _css() -> str:
    text = "\n".join(p.read_text(encoding="utf-8") for p in sorted(CSS_DIR.glob("*.css")))
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _rules(css: str):
    for match in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", css):
        yield match.group(1).strip(), match.group(2)


def test_the_gap_is_measured_from_the_live_font_and_remeasured_on_a_font_change():
    js = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    body = js[js.index("function measureLabelOptics("):]
    body = body[: body.index("\n}\n")]
    assert '"1cap"' in body, "the cap height comes from the font, not a constant"
    assert '"--ph-cap-dy"' in body
    assert "document.fonts?.ready?.then(measureLabelOptics)" in js
    apply = js[js.index("function applyAppearance("):]
    apply = apply[: apply.index("\n}\n")]
    assert apply.index("root.dataset.font =") < apply.index("measureLabelOptics();")


def test_a_label_icon_moves_by_the_measured_gap():
    css = _css()
    found = [
        body for selector, body in _rules(css)
        if {s.strip() for s in selector.split(",")} == {".ph-lead", ".ph-trail"} and "translate" in body
    ]
    assert found, "`.ph-lead, .ph-trail` carry the shared translate"
    assert re.search(r"translate:\s*0 calc\(var\(--ph-cap-dy\) \* 1em / 1\.15 - var\(--ph-ink-dy\)\)", found[0])


def test_no_label_words_are_trimmed():
    """A trimmed label beside an untrimmed one is two centre lines in one row."""
    css = _css()
    assert "text-box" not in css and "text-box-trim" not in css


def test_no_hand_set_translate_on_a_label_icon():
    """One mechanism. A per-family drop is calibrated in one font."""
    css = _css()
    offenders = []
    for selector, body in _rules(css):
        if "@" in selector or not re.search(r"(?:^|\s)translate:\s*(?!none\b)[^\s;]", body):
            continue
        for part in selector.split(","):
            part = part.strip()
            if part in {".ph-lead", ".ph-trail"}:
                continue
            last = re.split(r"\s+|>|\+|~", part)[-1]
            if re.search(r"\.ph-(?:lead|trail)\b", last) or (
                "#status-bar" in part and re.search(r"i\.ph\b", last)
            ):
                offenders.append(part)
    assert not offenders, f"a label icon nudged by hand: {offenders}"


def test_an_inline_icon_rides_the_baseline_with_its_ink_correction():
    css = _css()
    body = next(b for s, b in _rules(css) if s == ".ph" and "vertical-align" in b)
    assert "vertical-align: calc(-0.12em + var(--ph-ink-dy));" in body


def test_the_more_links_button_is_the_link_pill():
    """Screenshot 3: "+3 more links" was a ghost button (32px, 600, a square
    radius) at the end of a row of 26px outlined pills."""
    css = _css()
    body = next(b for s, b in _rules(css) if ".entry-links-more" in s and "border-radius" in b)
    assert "border-radius: var(--radius-pill);" in body
    assert "align-self: stretch;" in body
    assert "min-height: calc(1.5rem + 2px);" in body


def test_a_timeline_row_keeps_its_mark_and_its_title_on_one_line():
    """INBOX 542: the note mark sat 1.2px above its title (2.2px in Segoe UI).

    The mark and the time are start-aligned and offset to the title line's
    centre, which holds only while the title sits at the top of its track. A
    row on `--row-h` has a track taller than the title, and the title (the one
    item left centred) dropped by half the difference. The track is
    centred in the row (`align-content`) and the title starts at its top, so
    all three share the title's line in a one-line row and nothing changes in
    a row with a snippet."""
    css = _css()
    body = next(
        b for s, b in _rules(css)
        if s == ".timeline-feed .timeline-row" and "--timeline-title-line" in b
    )
    assert "align-content: center;" in body
    main = next(b for s, b in _rules(css) if s == ".timeline-feed .timeline-row > .timeline-row-main")
    assert "align-self: start;" in main
