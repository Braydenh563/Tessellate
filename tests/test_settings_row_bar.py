"""One changed-row bar x for every row recipe, and the Help "Where" line kept
inside its topic's fold (INBOX 1610, 1612). Measured in a browser by the sweep
the commit names; this keeps the rules that make the numbers from drifting."""
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css"


def _rules(name: str, scope: str) -> list[str]:
    text = (CSS / name).read_text(encoding="utf-8")
    return [
        text[i : text.index("}", i)]
        for i in range(len(text))
        if text.startswith(f"{scope} .setting-modified::before", i)
        or text.startswith(f"{scope} :is(.check-row, .setting-check, .checkbox-label).setting-modified::before", i)
    ]


def test_the_changed_bar_sits_one_gutter_from_the_text_edge_on_every_recipe():
    for name, scope in (("01-forms-settings.css", "#settings-modal"), ("appearance-panel-lazy.css", "#appearance-panel")):
        rules = _rules(name, scope)
        assert len(rules) >= 1, (name, rules)
        assert "calc(-2 * var(--space-3))" in rules[0]
        if name != "appearance-panel-lazy.css":
            continue
        assert "calc(-1 * var(--space-3))" in rules[1]
    lazy = (CSS / "settings-controls-lazy.css").read_text(encoding="utf-8")
    assert "#settings-modal :is(.check-row, .setting-check, .checkbox-label).setting-modified::before {\n  inset-inline-start: calc(-1 * var(--space-3))" in lazy


def test_the_where_line_is_the_last_line_of_its_fold():
    text = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    i = text.index(".help-accordion > details > p.help-topic-links {")
    rule = text[i : text.index("}", i)]
    assert "margin: 0 0 0 var(--space-7)" in rule
    assert "border-top: 0" in rule
    assert "p.help-topic-links" not in (CSS / "04-chat-dock-appearance.css").read_text(encoding="utf-8")
