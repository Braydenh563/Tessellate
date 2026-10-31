"""What the notebook gives a chat message is one card, staged and sent (INBOX 1460).

The owner: notebook attachments were "a black bar with middle sentence text
cut off on both sides" in a sent bubble (a centred `<button>` with
`white-space: nowrap` overflows both ways) and a blue chip while staged.
Both are the staged file card's recipe now: `notebookCard` in chat-agent.js
builds it from `attachmentChip`, the composer stages it with a remove button,
the bubble shows it above the question, and a press previews it (the citation
peek, with an Open button) from the lazy attachment-peek.js.

Source assertions, as test_chat_attachments.py: there is no DOM here. The
measured half is `scratchpad/ui-sweeps/notebookattach.js`.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    return text[text.index(start) :].split(end)[0]


def test_the_chip_builder_can_be_a_card_that_opens() -> None:
    attach = _read("frontend", "js", "chat-attach.js")
    builder = _between(attach, "function attachmentChip(", "\nfunction renderImageAttachments")
    for needle in ('"att-chip-open"', "onOpen", "icon", 'aria-haspopup'):
        assert needle in builder, needle
    # The open button holds the tile and the words; the remove button is its
    # sibling, never inside it (a button in a button is invalid markup).
    assert builder.index('"att-chip-open"') < builder.index('"att-chip-x"')


def test_one_card_builder_serves_the_bubble_and_the_composer() -> None:
    agent = _read("frontend", "js", "chat-agent.js")
    attach = _read("frontend", "js", "chat-attach.js")
    assert agent.count("function notebookCard(") == 1
    card = _between(agent, "function notebookCard(", "\nfunction ")
    assert "attachmentChip(" in card
    assert "attachmentPeek" in card
    strip = _between(agent, "function chatAttachmentStrip(", "\nfunction notebookCard(")
    assert "notebookCard(" in strip
    for old in ("msg-attachment-note", "msg-attachment-doc", "ph:paperclip", "mapChip("):
        assert old not in strip, old
    # Staged: notes, documents and maps all use it, with the remove button.
    for fn in ("renderAttachments", "renderBoardAttachments", "renderDocumentAttachments"):
        body = _between(attach, f"function {fn}(", "\n}\n")
        assert "notebookCard(" in body, fn
        assert "onRemove" in body, fn
    assert 'className = "chip attachment-chip"' not in _between(attach, "function renderAttachments(", "\n}\n")


def test_the_old_black_bar_and_blue_chip_rules_are_gone() -> None:
    for css in ("02-chat-graph.css", "08-consistency.css"):
        text = _read("frontend", "css", css)
        assert ".msg-attachment-note" not in text, css
        assert ".msg-attachment-doc" not in text, css
    for js in ("chat-agent.js", "chat-attach.js"):
        text = _read("frontend", "js", js)
        assert "msg-attachment-note" not in text
        assert "msg-attachment-doc" not in text


def test_the_cards_sit_above_the_bubble_on_its_side() -> None:
    """The hub's decision (INBOX 1460): above the message bubble, aligned to
    its side. The strip is the bubble's previous sibling, and is removed with
    it (the bubble holds it as `cards`; `dropChatBubble` removes both)."""
    agent = _read("frontend", "js", "chat-agent.js")
    add = _between(agent, "function addBubble(", "\nfunction dropChatBubble")
    assert 'bubble.cards = strip' in add
    assert add.index('appendChild(strip)') < add.index('appendChild(bubble)')
    assert "bubble.insertBefore(strip" not in add
    assert "node.cards?.remove()" in _between(agent, "function dropChatBubble(", "\n}\n")
    for name, needle in (("chat-attach.js", "dropChatBubble(userBubble)"), ("chat-edit.js", "dropChatBubble(later)"), ("chat-edit.js", "dropChatBubble(node)")):
        assert needle in _read("frontend", "js", name), needle
    css = app_css()
    rule = _between(css, "#chat-messages > .msg-attachments {", "}")
    assert "align-self: flex-end" in rule
    assert "max-width: min(82%, 54rem)" in rule


def test_a_card_never_ends_a_name_mid_cut_on_both_sides() -> None:
    css = _read("frontend", "css", "04-chat-dock-appearance.css")
    open_rule = _between(css, ".att-chip-open {", "}")
    for decl in ("text-align: left", "min-width: 0", "flex: 1 1 auto"):
        assert decl in open_rule, decl
    # The name's ellipsis is the stem's, at the end only (the file card's).
    assert "text-overflow: ellipsis" in _between(css, ".att-chip-stem {", "}")


def test_the_preview_is_lazy_and_reuses_the_citation_peek() -> None:
    card = _between(_read("frontend", "js", "chat-agent.js"), "function notebookCard(", "\nfunction ")
    assert '"/js/attachment-peek.js"' in card
    assert "reply-kit-lazy.css" in card, "the empty number slot is hidden by this sheet"
    peek = _read("frontend", "js", "attachment-peek.js")
    assert "openCitationPeek(" in peek
    assert "function attachmentPeek(" in peek
    # The peek's Open button is the card's own door.
    cites = _read("frontend", "js", "capture-ask.js")
    assert "source.open" in cites
    assert "source.title" in cites


def test_help_says_what_a_card_does() -> None:
    from tessellate.ai import help_chat

    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "chat-attach-cards")
    assert "preview" in topic["body"].lower()
    assert "above your message" in topic["body"]
    assert len(topic["body"]) < 1900
    index = _read("frontend", "index.html")
    assert "Press a card for a preview with Open" in index


def app_css() -> str:
    from tests._css_paths import css_text

    return css_text()


def test_the_open_button_is_named_by_its_verb_and_the_hover_keeps_the_facts_readable() -> None:
    """UX review 1031 items 7 and 18: the name was "Weekly review Note · 2 min
    ago" with "Preview" only on a tooltip; and the facts line was 4.1:1 on the
    hovered card's grey (4.65 light and 5.11 dark on the quieter tone)."""
    attach = _read("frontend", "js", "chat-attach.js")
    builder = _between(attach, "function attachmentChip(", "\nfunction renderImageAttachments")
    assert 'open.setAttribute("aria-label", `${title}, ${facts.textContent}`)' in builder
    css = _read("frontend", "css", "04-chat-dock-appearance.css")
    hover = _between(css, ".att-chip:has(> .att-chip-open:is(:hover, :focus-visible)) {", "}")
    assert "background: var(--ghost-btn-bg);" in hover
