"""Nothing in Settings scrolls sideways (INBOX 622).

The owner, with a screenshot of Settings, Tools it can use: "idk if this
navigation is the right way to go about it. should it be redesigned
better??" It was a strip of the pane's group heads in the pane's dock that
scrolled sideways, with a visible scrollbar and its last label clipped. The
decision: the groups are the sidebar's second level, nested under the pane
they belong to (two levels, as VS Code and Linear draw settings), a press
scrolls to the group and the group you are reading is tracked as you scroll;
on a phone the jump list gains the same groups. And no horizontal scroll
anywhere in Settings, held here.

The stylesheet half: no rule that reaches an element of the Settings dialog
lets it scroll on the x axis (`overflow-x: auto|scroll`, or a two-value
`overflow` whose first value is). The runtime half, every pane at 1440 and
390, is `scratchpad/ui-sweeps/settingsnav.js` ("nothing in Settings scrolls
sideways").
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_DIR = ROOT / "frontend" / "css"
INDEX = ROOT / "frontend" / "index.html"
FIND = ROOT / "frontend" / "js" / "settings-find.js"


def _settings_markup() -> str:
    html = INDEX.read_text(encoding="utf-8")
    start = html.index('id="settings-modal"')
    return html[start:]


def _settings_names() -> set[str]:
    """Every class and id written inside the Settings dialog, plus the ones
    its scripts build there (the sidebar groups, the jump list)."""
    markup = _settings_markup()
    names = {"." + c for attr in re.findall(r'class="([^"]+)"', markup) for c in attr.split()}
    names |= {"#" + i for i in re.findall(r'id="([^"]+)"', markup)}
    names |= {".settings-nav-groups", ".settings-nav-group", "#settings-jump", ".settings-jump", ".settings-index"}
    #: Utility classes that also live far outside Settings say nothing about
    #: where a rule lands; a rule naming only these is not a Settings rule.
    #: `.code-block` too: outside Settings it holds a note's wide table, which
    #: must scroll; inside, `#settings-modal .code-block` wraps it (asserted
    #: below).
    return names - {".row", ".hidden", ".muted", ".small", ".ghost", ".icon-only", ".card", ".chip", ".code-block"}


def _sideways_rules() -> list[str]:
    names = _settings_names()
    hits = []
    for path in sorted(CSS_DIR.glob("*.css")):
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for m in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", text):
            body = m.group(2)
            sideways = re.search(r"overflow-x\s*:\s*(auto|scroll)", body) or re.search(
                r"overflow\s*:\s*(auto|scroll)\s+\w", body
            )
            if not sideways:
                continue
            for selector in m.group(1).split(","):
                # The subject of the selector: its last compound.
                subject = re.split(r"[\s>+~]+", selector.strip())[-1]
                if set(re.findall(r"[.#][\w-]+", subject)) & names:
                    hits.append(f"{path.name}: {' '.join(selector.split())}")
    return hits


def test_no_settings_rule_scrolls_sideways():
    hits = _sideways_rules()
    assert not hits, f"a Settings element may scroll sideways: {hits}"
    css = "\n".join(p.read_text(encoding="utf-8") for p in sorted(CSS_DIR.glob("*.css")))
    rule = re.search(r"#settings-modal \.code-block \{([^}]*)\}", css)
    assert rule and "overflow-x: visible" in rule.group(1) and "pre-wrap" in rule.group(1)


def test_the_lint_sees_a_strip():
    """The rule this file exists for, caught: the strip it replaced."""
    names = _settings_names()
    assert ".modal-nav" in names and "#settings-nav" in names


def test_the_pane_index_is_the_sidebars_second_level():
    """No strip in the pane: the groups are built into `#settings-nav`, after
    the pane's own link, and into the phone's jump list."""
    code = re.sub(r"//.*", "", FIND.read_text(encoding="utf-8"))
    assert "settings-index" not in code, "the in-pane strip is gone"
    assert '"settings-nav-groups"' in code and '"settings-nav-group"' in code
    assert 'button[data-section="${CSS.escape(name)}"]`)?.after(list)' in code
    assert ".settings-jump option[data-group]" in code and "row.dataset.group" in code
    assert "aria-current" in code and "scrollIntoView" not in code


def test_a_status_naming_an_address_wraps_inside_the_pane():
    """The Models pane at 390: "Saved, but nothing is answering at <address>"
    holds a word no line can break, and the pane grew to 581px in a 308px
    window (and a long question in a help popover's Ask Atlas chip to 327).
    Settings' status and muted lines take `overflow-wrap: anywhere`, which also
    lowers a flex item's minimum width, and the chip is capped at its parent."""
    css = re.sub(r"/\*.*?\*/", "", "\n".join(p.read_text(encoding="utf-8") for p in sorted(CSS_DIR.glob("*.css"))), flags=re.S)
    status = re.search(r"#settings-modal :is\(\.status, \.muted\) \{([^}]*)\}", css)
    assert status and "overflow-wrap: anywhere" in status.group(1)
    chip = re.search(r"\.help-atlas > \.atlas-suggest \{([^}]*)\}", css)
    assert chip and "max-width: 100%" in chip.group(1)
