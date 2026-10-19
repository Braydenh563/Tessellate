"""Which overflow and menu icon goes where (INBOX 706).

The owner, 2026-10-06: "we have been using majority of meatball icons but I
think meatball, kebab, bento box icons and more etc are better for use in
various situations and uses". The platform conventions, taken:

- `⋯` (`ph-dots-three`, meatball) is an item's overflow in a horizontal row, a
  card or a bar of controls;
- `⋮` (`ph-dots-three-vertical`, kebab) is the overflow at the end of a row in
  a vertical list and in a narrow column (a rail's rows, a settings list);
- `⊞` (`ph-dots-nine`, bento) only switches between apps or spaces;
- `☰` (`ph-list`, hamburger) only opens navigation.

The app has no app switcher and no hamburger (navigation is the tab bar), so
the last two are listed here with an empty allowance: the day one is built it
joins the list on purpose. Rule and rows: DESIGN.md, "Overflow and menu icons".
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._repo_files import repo_files

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "frontend"
HTML = (FRONT / "index.html").read_text(encoding="utf-8")
JS = {p.name: p.read_text(encoding="utf-8") for p in sorted((FRONT / "js").glob("*.js"))}
CSS = {p.name: p.read_text(encoding="utf-8") for p in sorted((FRONT / "css").glob("*.css"))}

#: A glyph is one of the two overflow shapes; the circled, outlined and
#: vertical-outlined variants were one-off third styles for the same job.
STRAY_OVERFLOW = ("dots-three-circle", "dots-three-outline", "dots-three-circle-vertical", "dots-three-outline-vertical")

#: Where a kebab is vertical: `kebabMenu(..., { vertical: true })` call sites by
#: file (rows of a vertical list), and the one narrow-column button in the
#: markup. A new vertical one is a decision, so it is a line here.
VERTICAL_KEBABS = {
    "categories-panel.js": 1,  # Manage categories, one row per category
    "documents.js": 2,  # the documents rail's rows; a history version's row (Brief 76)
    "documents-codekit.js": 1,  # a saved snippet's row in the code panel's narrow column (INBOX 788)
    "link-types.js": 1,  # the relation types list
    "note-cards.js": 1,  # a note's connection rows
    "note-properties.js": 1,  # the note types list
    "notes-list.js": 1,  # the Notes categories rail
    "search.js": 1,  # the saved searches under the Notes categories rail (Brief 47)
    "settings-packages.js": 2,  # a package row, a bundle row
    "sheets-selects.js": 1,  # the Chats rail
    "shell-reminders.js": 1,  # a reminder row
    "tag-manager.js": 1,  # Manage tags, one row per tag
}
VERTICAL_IN_MARKUP = {"wb-lib-more"}  # the board sidebar's narrow head


def _all_sources() -> dict[str, str]:
    return {"index.html": HTML, **JS, **CSS}


def test_no_third_style_of_overflow_glyph() -> None:
    offenders = [
        f"{name}: ph-{glyph}"
        for name, text in _all_sources().items()
        for glyph in STRAY_OVERFLOW
        if re.search(rf"\bph[-:]{glyph}\b", text)
    ]
    assert not offenders, "one overflow glyph is the meatball or the kebab, never a variant:\n  " + "\n  ".join(offenders)


def test_the_bento_grid_and_the_hamburger_are_not_drawn_for_anything_else() -> None:
    offenders = []
    for name, text in _all_sources().items():
        for glyph, meaning in (("dots-nine", "switching apps or spaces"), ("list", "opening navigation")):
            if re.search(rf"\bph[-:]{glyph}(?![-\w])", text):
                offenders.append(f"{name}: ph-{glyph} is for {meaning}, and nothing here switches or navigates with it")
    assert not offenders, "\n".join(offenders)


def test_a_meatball_or_kebab_in_the_markup_opens_a_menu() -> None:
    """The glyph means overflow and nothing else: it sits in a control whose
    name says so (More, Actions, Sort and view). A dashed line and a section
    break both borrowed the meatball once."""
    pattern = re.compile(r'(<(?:button|summary)\b[^>]*>)\s*<i class="ph ph-dots-three(?:-vertical)?\b[^"]*"')
    found = pattern.findall(HTML)
    assert len(found) >= 8, "the markup's overflow controls were not found"
    unnamed = [tag[:160] for tag in found if not re.search(r'(?:title|aria-label)="[^"]*(?:[Mm]ore|[Aa]ctions|[Ss]ort and view)', tag)]
    assert not unnamed, f"a dots glyph on a control that is not an overflow menu: {unnamed}"


def test_in_script_the_overflow_glyph_belongs_to_the_menu_builders_alone() -> None:
    allowed = {
        "sheets-selects.js",  # kebabMenu
        "menus.js",  # the note row's own builder, a card (meatball)
        "documents.js",  # the dock's More toggle label
        "whiteboard-commands.js",  # the legend naming the menu key
        "editor.js",  # (comment on the section break: not a glyph)
    }
    users = {
        name
        for name, text in JS.items()
        if re.search(r'["\']ph:dots-three(?:-vertical)?["\']', text)
    }
    assert users <= allowed, f"a new place draws the overflow glyph: {sorted(users - allowed)}"
    assert "ph:asterisk" in JS["editor.js"], "the section break is no longer a meatball"
    assert 'icon: "ph:dots-three", label: "Section break"' not in JS["editor.js"]


def test_the_vertical_kebab_is_only_at_the_end_of_a_vertical_list_row_or_in_a_narrow_column() -> None:
    counts = {name: len(re.findall(r"\{ vertical: true \}", text)) for name, text in JS.items() if "{ vertical: true }" in text}
    assert counts == VERTICAL_KEBABS, f"vertical kebabs by file {counts}; allowed {VERTICAL_KEBABS}"
    vertical_in_markup = set(re.findall(r'id="([\w-]+)"[^>]*>\s*<i class="ph ph-dots-three-vertical', HTML))
    assert vertical_in_markup == VERTICAL_IN_MARKUP, vertical_in_markup


def test_kebab_menu_draws_the_vertical_glyph_only_when_asked() -> None:
    source = JS["sheets-selects.js"]
    start = source.index("function kebabMenu(")
    body = source[start : start + 900]
    assert "{ vertical = false } = {}" in body
    assert 'vertical ? "ph:dots-three-vertical" : "ph:dots-three"' in body


def test_the_list_view_toggle_is_not_a_hamburger() -> None:
    """Cards and Rows: the toggle's second state is `ph-rows`, the counterpart
    of `ph-squares-four`; `ph-list` stays free for the navigation button."""
    assert HTML.count('data-library-view="list"') == 2
    for match in re.finditer(r'data-library-view="list"[^>]*>\s*<i class="ph (ph-[\w-]+)"', HTML):
        assert match.group(1) == "ph-rows", match.group(0)


def test_design_md_has_the_row_and_names_this_lint() -> None:
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "Overflow and menu icons" in design
    assert "tests/test_icon_conventions.py" in design


# --- The AI and the agent (INBOX 723) ----------------------------------------
#
# The owner, 2026-10-06: "make sure all the icons for the ai are consistent.
# also can you use a better icon for the agent?? i dont like the robot".
# Measured before: the AI wore five glyphs (sparkle, magic wand, brain, robot,
# four-pointed star) with no rule for which, and the same "Ask Atlas" job wore
# a sparkle in one menu and a wand in the next. One glyph per meaning now:
#
# - `ph-sparkle`: the AI does something for you (describe, read, ask, suggest,
#   draft, rewrite, file by meaning, the "AI off" mark).
# - `ph-strategy`: the agent, which plans and then acts in steps on your
#   behalf (Agent mode, the popup agent, Agent activity, its runs).
# - `ph-lightning`: Skills (left as it was).
# - `ph-magic-wand`: tidy or fix automatically, by rule, no model.
# - `ph-brain`: what it remembers about you.
# - `ph-asterisk`: a section break.
#
# Rule and rows: DESIGN.md, "AI and agent icons".

PY = {
    p.relative_to(ROOT / "src").as_posix(): p.read_text(encoding="utf-8")
    for p in repo_files(ROOT / "src" / "tessellate", suffixes=(".py",))
}

AI_ICON = "sparkle"
AGENT_ICON = "strategy"

#: Where the agent glyph is drawn, by file. Each is the agent itself or one of
#: its runs; a new place is a decision, so it is a line here.
AGENT_ICON_PLACES = {
    "index.html": 4,  # the popup agent's head and input, Agent mode (toggle, segment); Activity wears ph-activity (decision 70)
    "agent-activity.js": 1,  # the status bar's runs
    "chat-attach.js": 1,  # an agent turn's run in the activity panel
    "chat.js": 1,  # a past turn answered in Agent mode
    "editor.js": 1,  # the chat palette's Agent mode row
    "phone-more.js": 2,  # More sheet: Ask the agent, Agent activity (moved out of phone-shell.js, INBOX 1314)
    "settings-panes.js": 1,  # the command palette's Ask the agent anything
    "settings-wiring.js": 1,  # the tools popup's Popup agent
    "skills.js": 1,  # the nudge to switch to Agent mode
    "status.js": 2,  # the status bar's agent button, a run's notification
}

#: Words one of which sits on or near every line that draws the agent glyph.
AGENT_CONTEXT = re.compile(r"agent|\bruns?\b", re.IGNORECASE)

#: What the wand may mean: tidy or fix automatically, by rule.
WAND_MEANINGS = re.compile(r"\bFix\b|autocorrect|align", re.IGNORECASE)
#: What the brain may mean: what it remembers.
BRAIN_MEANINGS = re.compile(r"remember|memory", re.IGNORECASE)
#: Words that say the AI or the agent is doing the work.
AI_WORDS = re.compile(r"\bAI\b|Atlas|\bagent\b|\bmodel\b|by meaning|semantic", re.IGNORECASE)


def _glyph_lines(glyph: str, sources: dict[str, str]) -> list[tuple[str, int, list[str]]]:
    """(file, line index, lines) for each line that draws `glyph`, as
    `ph-name` in markup and CSS or `ph:name` in a label string."""
    found = []
    pattern = re.compile(rf"\bph[-:]{glyph}(?![-\w])")
    for name, text in sources.items():
        lines = text.splitlines()
        for number, line in enumerate(lines):
            if pattern.search(line):
                found.append((name, number, lines))
    return found


def _everywhere() -> dict[str, str]:
    return {**_all_sources(), **PY}


def test_the_robot_is_gone() -> None:
    users = sorted({name for name, _, _ in _glyph_lines("robot", _everywhere())})
    assert not users, f"the agent is ph-{AGENT_ICON} now; the robot is back in {users}"


def test_the_agent_glyph_is_in_the_vendored_font() -> None:
    style = (FRONT / "vendor" / "phosphor" / "style.css").read_text(encoding="utf-8")
    assert f".ph-{AGENT_ICON}:before" in style
    assert f".ph-{AI_ICON}:before" in style


def test_the_agent_glyph_is_drawn_only_for_the_agent_and_its_runs() -> None:
    hits = _glyph_lines(AGENT_ICON, _everywhere())
    counts: dict[str, int] = {}
    for name, _, _ in hits:
        counts[name] = counts.get(name, 0) + 1
    assert counts == AGENT_ICON_PLACES, f"the agent glyph by file {counts}; allowed {AGENT_ICON_PLACES}"
    stray = []
    for name, number, lines in hits:
        window = " ".join(lines[max(0, number - 4) : number + 3])
        if not AGENT_CONTEXT.search(window):
            stray.append(f"{name}:{number + 1}: {lines[number].strip()[:140]}")
    assert not stray, "the agent glyph on something that is not the agent or a run:\n  " + "\n  ".join(stray)


def test_the_ai_glyph_is_never_the_agent() -> None:
    """A line that names the agent wears the agent glyph, not the sparkle: the
    popup agent's head wore a sparkle while its button wore a wand."""
    offenders = [
        f"{name}:{number + 1}: {lines[number].strip()[:140]}"
        for name, number, lines in _glyph_lines(AI_ICON, _everywhere())
        if re.search(r"\bagent\b", lines[number], re.IGNORECASE)
    ]
    assert not offenders, "the sparkle is the AI doing a thing for you, not the agent:\n  " + "\n  ".join(offenders)


def test_the_wand_only_tidies_or_fixes_by_rule() -> None:
    offenders = []
    for name, number, lines in _glyph_lines("magic-wand", _everywhere()):
        line = lines[number]
        window = " ".join(lines[max(0, number - 1) : number + 2])
        if AI_WORDS.search(line) or not WAND_MEANINGS.search(window):
            offenders.append(f"{name}:{number + 1}: {line.strip()[:140]}")
    assert not offenders, "the wand means tidy or fix by rule; the AI is ph-sparkle:\n  " + "\n  ".join(offenders)


def test_the_brain_is_only_what_it_remembers() -> None:
    offenders = [
        f"{name}:{number + 1}: {lines[number].strip()[:140]}"
        for name, number, lines in _glyph_lines("brain", _everywhere())
        if not BRAIN_MEANINGS.search(lines[number])
    ]
    assert not offenders, "the brain means memory; the AI is ph-sparkle:\n  " + "\n  ".join(offenders)


def test_the_four_pointed_star_and_the_asterisk_each_have_one_job() -> None:
    """The four-pointed star sat beside the sparkle and read as a second AI
    mark; the asterisk is the section break and nothing else."""
    stars = sorted({name for name, _, _ in _glyph_lines("star-four", _everywhere())})
    assert not stars, f"ph-star-four reads as the AI's sparkle: {stars}"
    asterisks = [
        f"{name}:{number + 1}"
        for name, number, lines in _glyph_lines("asterisk", _everywhere())
        if "Section break" not in lines[number]
    ]
    assert not asterisks, f"ph-asterisk is the section break only: {asterisks}"


def test_a_label_that_says_with_ai_wears_the_sparkle() -> None:
    """Measured in the lightbox's More menu: "Describe with AI" wore the
    sparkle and "Read text with AI", one row under it, wore `ph-text-aa`."""
    offenders = [
        f"{name}: {match.group(0)}"
        for name, text in JS.items()
        for match in re.finditer(r'["`]ph:([\w-]+) [^"`\n]*\bwith AI\b', text)
        if match.group(1) != AI_ICON
    ]
    assert not offenders, "a control that names the AI wears ph-sparkle:\n  " + "\n  ".join(offenders)


def test_ask_and_agent_wear_the_two_glyphs_in_the_chat_dock() -> None:
    ask = re.search(r'<button data-chat-mode="chat"[^>]*>\s*<i class="ph (ph-[\w-]+)', HTML)
    agent = re.search(r'<button data-chat-mode="agent"[^>]*>\s*<i class="ph (ph-[\w-]+)', HTML)
    assert ask and ask.group(1) == f"ph-{AI_ICON}", ask and ask.group(1)
    assert agent and agent.group(1) == f"ph-{AGENT_ICON}", agent and agent.group(1)
    #: The panel is Activity now, every job and the agent's runs (decision 70).
    assert 'ph-activity ph-lead" aria-hidden="true"></i> Activity' in HTML


def test_design_md_has_the_ai_and_agent_row() -> None:
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    at = design.index("| AI and agent icons")
    row = design[at : design.index("\n", at)]
    assert f"ph-{AGENT_ICON}" in row and f"ph-{AI_ICON}" in row
    assert "tests/test_icon_conventions.py" in row
