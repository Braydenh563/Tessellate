"""Settings' information architecture (INBOX 444).

The owner: "the settings needs better designing, rearrangement, better
internal navigation and cleaning up." Measured first (`scratchpad/ui-sweeps/
settingsia.js`, UI_MODERNISATION_PLAN "Settings information architecture"):
twenty sections, nine concerns set from two or three of them, Models alone
4,737px with search relevance set two sections away from the engine and the
index it tunes.

This file pins the decisions, so no session after cannot quietly undo them:

* the nav is six named groups in a fixed order;
* every nav button names a section that exists and is in `SETTINGS_SECTIONS`
  (a section left out of that list is rendered and never shown);
* the controls that moved live in the section they moved to;
* a deep link that names a control lands on the section that holds it, even
  when the caller still names the old section (`openSettingsModal` resolves the
  section from the control itself, so a move can never strand a link).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from tests._app_js import INDEX_HTML, JS_DIR

HTML = INDEX_HTML.read_text(encoding="utf-8")


class _Settings(HTMLParser):
    """Collects the Settings modal: the nav's groups and each section's ids."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, dict]] = []
        self.groups: list[tuple[str, list[str]]] = []  # (label, [data-section])
        self.labels: dict[str, str] = {}
        self.section_ids: dict[str, set[str]] = {}
        self._in_nav = False
        self._current_group: list[str] | None = None
        self._group_label_id: str | None = None
        self._section: str | None = None
        self._capture: str | None = None
        self._buf = ""
        self._label_for_group: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.stack.append((tag, a))
        if tag == "nav" and a.get("id") == "settings-nav":
            self._in_nav = True
        if self._in_nav and tag == "p" and "nav-group-label" in (a.get("class") or ""):
            self._capture = a.get("id", "")
            self._buf = ""
        if self._in_nav and tag == "div" and a.get("role") == "group":
            self._current_group = []
            self.groups.append((a.get("aria-labelledby", ""), self._current_group))
        if self._in_nav and tag == "button" and "data-section" in a and self._current_group is not None:
            self._current_group.append(a["data-section"])
        if tag == "section" and (a.get("id") or "").startswith("settings-") and "settings-section" in (a.get("class") or ""):
            self._section = a["id"][len("settings-"):]
            self.section_ids[self._section] = set()
        elif self._section and a.get("id"):
            self.section_ids[self._section].add(a["id"])

    def handle_endtag(self, tag):
        if tag == "nav" and self._in_nav:
            self._in_nav = False
        if tag == "p" and self._capture is not None:
            self._label_for_group[self._capture] = self._buf.strip()
            self._capture = None
        if tag == "section":
            self._section = None
        while self.stack:
            top, _ = self.stack.pop()
            if top == tag:
                break

    def handle_data(self, data):
        if self._capture is not None:
            self._buf += data


def _parse() -> _Settings:
    parser = _Settings()
    parser.feed(HTML)
    return parser


PARSED = _parse()

#: The decision. A group is its label and its sections, in order.
EXPECTED_NAV = [
    ("AI", ["models", "searchindex", "personas", "skills", "tools", "memory", "learned", "websearch"]),
    ("Notebook", ["preferences", "general", "templates", "data"]),
    ("Look and feel", ["appearance", "shortcuts"]),
    ("Privacy and security", ["account", "privacy"]),
    ("System", ["extras", "tasks", "logs"]),
    ("Help and About", ["help", "about"]),
]


def _settings_sections() -> list[str]:
    text = (JS_DIR / "settings.js").read_text(encoding="utf-8")
    body = re.search(r"const SETTINGS_SECTIONS = \[(.*?)\];", text, re.S).group(1)
    return re.findall(r'"([a-z]+)"', body)


def test_the_nav_is_six_named_groups_in_order():
    got = [(PARSED._label_for_group[label_id], sections) for label_id, sections in PARSED.groups]
    assert got == EXPECTED_NAV


def test_every_nav_button_has_a_section_and_a_place_in_the_list():
    listed = _settings_sections()
    nav = [name for _label, sections in EXPECTED_NAV for name in sections]
    for name in nav:
        assert name in PARSED.section_ids, f"nav names {name!r}, no #settings-{name}"
        assert name in listed, f"{name!r} is missing from SETTINGS_SECTIONS, so it would never be shown"
    assert sorted(listed) == sorted(PARSED.section_ids), "SETTINGS_SECTIONS and the sections drifted"
    assert len(nav) == len(set(nav)), "a section sits in two groups"


def test_the_controls_that_moved_live_where_they_moved_to():
    """Search belongs together: the engine, the index and the relevance floor
    that tunes what they return (it was in General, two sections away)."""
    ids = PARSED.section_ids
    for control in (
        "search-engine-config",
        "embedding-model-select",
        "reindex-box",
        "reindex-start",
        "search-relevance-group",
        "pref-search-min-sim",
        "pref-search-z-margin",
        "search-engine-health",
        "embedding-error",
    ):
        assert control in ids["searchindex"], f"#{control} should be in Search and index"
        assert control not in ids["models"], f"#{control} is still in Models"
        assert control not in ids["general"], f"#{control} is still in General"
    # The answer style is Atlas's voice, so it sits with the personas.
    assert "pref-style" in ids["personas"]
    assert "pref-style" not in ids["general"]


def test_a_control_has_one_home():
    """The same id in two sections is a control drawn twice."""
    seen: dict[str, str] = {}
    for section, ids in PARSED.section_ids.items():
        for control in ids:
            assert control not in seen, f"#{control} is in both {seen[control]} and {section}"
            seen[control] = section


def test_a_link_names_the_section_that_holds_its_target():
    """Callers that pass both a section and a control must agree with the
    markup. The runtime resolves the section from the control, so a stale
    caller would still land; this keeps the callers honest."""
    owner = {control: section for section, ids in PARSED.section_ids.items() for control in ids}
    wrong: list[str] = []
    sources = [(path.name, path.read_text(encoding="utf-8")) for path in JS_DIR.glob("*.js")]
    sources.append(("index.html", HTML))
    for name, text in sources:
        for section, control in re.findall(r'openSettingsModal\(\s*"([a-z]+)"\s*,\s*"([A-Za-z0-9_-]+)"', text):
            if control in owner and owner[control] != section:
                wrong.append(f"{name}: openSettingsModal({section!r}, {control!r}) but #{control} is in {owner[control]}")
        for section, control in re.findall(r'data-goto-section="([a-z]+)"\s+data-goto-target="([A-Za-z0-9_-]+)"', text):
            if control in owner and owner[control] != section:
                wrong.append(f"{name}: data-goto {section}/{control}, #{control} is in {owner[control]}")
        for section, control in re.findall(r'settings:\s*"([a-z]+)",\s*el:\s*"([A-Za-z0-9_-]+)"', text):
            if control in owner and owner[control] != section:
                wrong.append(f"{name}: REVEAL_TARGETS {section}/{control}, #{control} is in {owner[control]}")
    assert not wrong, "; ".join(wrong)


def test_opening_with_a_control_resolves_the_section_from_the_control():
    text = (JS_DIR / "settings.js").read_text(encoding="utf-8")
    opener = text[text.index("async function openSettingsModal") :]
    opener = opener[: opener.index("showSettingsSection(section)")]
    assert 'closest(".settings-section")' in opener, (
        "openSettingsModal must take the section from the control it was asked to scroll to"
    )


def test_every_section_that_holds_a_preference_fills_it_on_open():
    """`renderPrefs` fills `pref-search-*` and `pref-style`; it only ran for
    Profile and General, so Search and index and Personas would have shown the
    raw HTML defaults for settings that ship on."""
    text = (JS_DIR / "settings.js").read_text(encoding="utf-8")
    line = next(row for row in text.splitlines() if "renderPrefs()" in row and "includes(name)" in row)
    for name in ("preferences", "general", "searchindex", "personas"):
        assert f'"{name}"' in line, f"{name} opens without filling its preferences"
