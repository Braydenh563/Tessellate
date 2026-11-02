"""The Dashboard's hero at the Focused view (INBOX 675).

The owner, with a screenshot at about 2000px: "can you improve the dashboard
hero section on the focused view??" The banner was "Evening, Brayden." over
the note count at the left, the time over the date at the far right, and
nothing between: measured by `scratchpad/ui-sweeps/hero675.js`, the widest
empty strip of the hero was 60% of it at 1024, 72% at 1440 and 78% at 1920.

Now: the date and time are one small line over the greeting (information,
not a second headline), New note is the hero's one action, and a glance of
four tiles fills the other half: what is due today, today's meetings, the
filings waiting and the note you were last in. Every number comes from a
read the dashboard already makes (`dashReminders`, `fetchDashStats`,
`dashEntries`), no new endpoint and no model. These pin what a static read
can pin, and the glance's arithmetic runs in node; the layout numbers are the
sweep's.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.ai import help_chat

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
DASH = (JS / "dashboard.js").read_text(encoding="utf-8")
CSS = re.sub(
    r"/\*.*?\*/", "", "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css"))), flags=re.S
)


def _function(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 3]


def _hero() -> str:
    start = INDEX.index('<section class="dash-hero" id="dash-hero">')
    return re.sub(r"<!--.*?-->", "", INDEX[start : INDEX.index("</section>", start)], flags=re.S)


def test_the_hero_carries_an_action_and_a_glance():
    hero = _hero()
    new = re.search(r'<button type="button" id="dash-hero-new"[^>]*>(.*?)</button>', hero, re.S)
    assert new, "New note is the hero's one action"
    assert "New note" in new.group(1) and 'class="ghost' not in new.group(0)
    assert re.search(r'id="dash-glance"[^>]*role="group"[^>]*aria-label="Today at a glance"', hero)
    assert "style=" not in hero  # the CSP refuses inline styles
    # Identity, then the action, then the glance: the tab order reads the
    # hero the way it is laid out.
    assert hero.index('id="dash-greeting"') < hero.index('id="dash-hero-new"') < hero.index('id="dash-glance"')


def test_the_glance_reads_what_the_dashboard_already_fetched():
    render = _function(DASH, "renderDashGlance")
    for source in ("dashReminders()", "fetchDashStats()", "dashEntries()"):
        assert source in render, source
    # No new endpoint, no model: the glance is arithmetic over those three.
    assert "apiJson(" not in render and "/insights/" not in render
    # Tiles are the tile recipe (`.quick-link`), not a new kind of box.
    assert "quickLinkButton(" in render
    assert "renderDashGlance()" in _function(DASH, "renderDashboardGreeting")
    assert '$("dash-hero-new")' in DASH and "startNewNote()" in DASH


def test_the_glance_and_action_belong_to_the_focused_view_only():
    # Full and Compact have Quick access, whose first tile is New note: a
    # second copy in their banner would be two of the same doorway.
    assert re.search(r"\.dash-hero-new,\s*\.dash-glance\s*\{\s*display:\s*none;", CSS)
    focused = r'#tab-dashboard\[data-density="focused"\]'
    assert re.search(focused + r" \.dash-glance\s*\{[^}]*display:\s*grid", CSS)
    assert re.search(focused + r" \.dash-hero-new\s*\{[^}]*display:\s*inline-flex", CSS)
    assert re.search(focused + r" \.dash-hero\s*\{[^}]*grid-template-areas", CSS)


def test_the_time_is_not_a_second_headline_at_focused():
    focused = r'#tab-dashboard\[data-density="focused"\]'
    time = re.search(focused + r" \.dash-clock-time[^{]*\{([^}]*)\}", CSS)
    assert time and "var(--text-sm)" in time.group(1)
    greeting = re.search(focused + r" \.dash-greeting\s*\{([^}]*)\}", CSS)
    assert greeting and "var(--text-h2)" in greeting.group(1)


def test_a_tile_inside_the_hero_is_a_tone():
    # DESIGN.md, Surfaces: "a tile inside a card is `--surface-2`".
    rule = re.search(r"\.dash-glance \.quick-link\s*\{([^}]*)\}", CSS)
    assert rule and "var(--surface-2)" in rule.group(1)


def test_the_help_says_what_the_focused_hero_holds():
    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "dashboard-controls")
    body = topic["body"]
    assert "Focused" in body and "due today" in body and "to file" in body
    popover = INDEX[INDEX.index('id="dash-help"') : INDEX.index("</div>", INDEX.index('id="dash-help"'))]
    assert "Focused" in popover


DRIVER = r"""
const now = new Date(2026, 9, 6, 20, 35);
const iso = (d) => d.toISOString();
const at = (h, m, day = 6) => new Date(2026, 9, day, h, m);
const reminders = [
  { text: "Call the bank", due_at: iso(at(17, 0)), done: false },
  { text: "Send the invoice", due_at: iso(at(21, 30)), done: false },
  { text: "Old one", due_at: iso(at(9, 0)), done: true },
  { text: "Tomorrow's", due_at: iso(at(9, 0, 7)), done: false },
];
const meeting = (title, when) => ({ id: title.length, title, content: `---\ntype: Meeting\ndate: ${when}\n---\n# ${title}\n`, created_at: iso(at(8, 0)) });
const entries = [
  meeting("Standup", "2026-10-06 09:00"),
  meeting("Design review", "2026-10-06 21:00"),
  meeting("Next week", "2026-10-13 10:00"),
  { id: 9, title: "Reading", content: "# Reading", created_at: iso(at(8, 0)), last_opened_at: iso(at(19, 0)) },
];
const out = {};
out.busy = dashGlanceFacts({ reminders, stats: { to_review: 3 }, entries, now });
out.calm = dashGlanceFacts({ reminders: [reminders[3]], stats: { to_review: 0 }, entries: [], now });
out.nostats = dashGlanceFacts({ reminders: [], stats: null, entries: [], now });
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def glance(tmp_path_factory) -> dict:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    source = "\n".join(
        [
            _function((JS / "prefs.js").read_text(encoding="utf-8"), "nounCount"),
            _function(DASH, "dashContinueNote"),
            _function(DASH, "dashMeetingWhen"),
            _function(DASH, "dashGlanceFacts"),
            DRIVER,
        ]
    )
    script = tmp_path_factory.mktemp("glance") / "run.js"
    script.write_text(source, encoding="utf-8")
    run = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def _tile(facts: list[dict], tile: str) -> dict:
    return next(f for f in facts if f["id"] == tile)


def test_four_tiles_always_in_one_order(glance):
    for case in ("busy", "calm", "nostats"):
        assert [f["id"] for f in glance[case]] == ["due", "meetings", "review", "continue"]


def test_due_today_counts_the_overdue_and_the_rest_of_today(glance):
    due = _tile(glance["busy"], "due")
    assert due["count"] == 2 and due["overdue"] == 1
    assert due["label"] == "2 due today"
    assert due["hint"].startswith("Call the bank")
    assert due["go"] == "reminders"
    calm = _tile(glance["calm"], "due")
    assert calm["count"] == 0 and calm["label"] == "Nothing due today"
    assert calm["hint"].startswith("Next: Tomorrow's")


def test_meetings_today_name_the_next_one(glance):
    meetings = _tile(glance["busy"], "meetings")
    assert meetings["count"] == 2 and meetings["label"] == "2 meetings today"
    assert meetings["hint"].startswith("Design review at ")
    assert meetings["go"] == {"entry": len("Design review")}
    none = _tile(glance["calm"], "meetings")
    assert none["label"] == "No meetings today" and none["go"] == "meetings"


def test_filings_and_the_last_note(glance):
    review = _tile(glance["busy"], "review")
    assert review["label"] == "3 to file" and review["go"] == "review"
    assert _tile(glance["calm"], "review")["label"] == "Nothing to file"
    # A failed stats read says nothing rather than a wrong zero.
    assert _tile(glance["nostats"], "review")["count"] is None
    last = _tile(glance["busy"], "continue")
    assert last["go"] == {"entry": 9}
    assert _tile(glance["calm"], "continue")["go"] == "capture"


def test_no_exclamation_marks_or_em_dashes_in_the_glance_copy():
    body = _function(DASH, "dashGlanceFacts")
    strings = re.findall(r'"([^"\n]*)"|`([^`\n]*)`', body)
    for pair in strings:
        text = pair[0] or pair[1]
        assert "!" not in text and chr(0x2014) not in text, text
