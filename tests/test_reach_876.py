"""L-world-class-876 and 780: Chat destinations the reach crawl found no palette command for, or found four presses deep
(scratchpad/ui-sweeps/reach.js, 2 of 148 on 2026-11-22)."""

from __future__ import annotations

from tests._app_js import with_pieces


def test_rename_this_chat_is_a_palette_command_on_the_chat_tab() -> None:
    palette = with_pieces("app-palette.js")
    row = palette[palette.index("function chatPaletteRows()") :][:500]
    assert 'prefs.get("activeTab", null) !== "chat" || !chatConv' in row
    assert "...chatPaletteRows(), ...notesPaletteCommands(lowered)]" in palette
    assert "run: paletteLater(() => renameCurrentConversation())" in row


def test_the_atlas_suggestion_is_named_by_the_words_its_command_uses() -> None:
    # The crawl matches a tooltip's head (before the colon) against palette commands: "Ask Atlas"
    # is the palette's "Ask Atlas about this note"; "Opens Atlas with this question" named nothing.
    assert 'ask.title = "Ask Atlas: opens Chat with this question";' in with_pieces("chat.js")


def test_activity_tabs_have_palette_commands() -> None:
    # L-world-class-780: Agent runs and History were four presses deep (Chat, More actions, Activity, the tab).
    features = with_pieces("app-features.js")
    assert 'act: () => openActivity("runs") }' in features and 'act: () => openActivity("history") }' in features
