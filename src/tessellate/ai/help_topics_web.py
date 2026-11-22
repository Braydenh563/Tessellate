"""The Guide's topics for the assistant's reach beyond the notebook: browsing and other apps.

Moved out of `help_topics_more.py` (at its line cap) whole; `help_topics_more` places each where it sat,
so the Guide's order is unchanged. Data only: no imports, no behaviour.
"""

from __future__ import annotations

ASSISTANT_BROWSER: dict = {
    "id": "assistant-browser",
    "keywords": (
        "browse the web",
        "browse a page",
        "open a page for me",
        "browser tools",
        "follow a link",
        "find text on a page",
        "go back a page",
        "assistant browser",
        "browser mcp",
        "read a page for me",
    ),
    "body": (
        "In Agent mode, with web search on (Settings, Web search), the assistant can "
        "browse beside searching: it opens a page in the Web panel, reads it as text, "
        "follows one of its links, finds words on it and goes back. The page it reads "
        "is the page you see in the panel. Opening and following send a request, "
        "so they use the same switch, the same address checks and the same "
        "confirm as a web search: once a page has been read in a turn, "
        "each further open or follow waits for you on a card. Reading, finding and "
        "going back use the page already held and send nothing. A page is someone "
        "else's words: Atlas reads it as data and never follows instructions in it. "
        "An MCP client you connected sees the same tools while web search is on. "
        "By hand, the reader has the page's links, Find in this page and Results."
    ),
    "badge": {"label": "Web search", "section": "websearch"},
}
ASSISTANT_BROWSER_META = {
    "title": "Browse the web with the assistant",
    "path": "Settings, Web search",
}

#: Moved out of tools-setting whole when the scope and OAuth rows came (L-world-class-560): that topic sat at the reply budget.
MCP_LINKS: dict = {
    "id": "mcp-links",
    "title": "Use your notes from another app",
    "keywords": (
        "mcp",
        "mcp link",
        "connect claude",
        "claude desktop",
        "claude.ai",
        "revoke a token",
        "oauth",
        "another app",
        "tool server",
        "docker",
    ),
    "badge": {"label": "Tools it can use", "section": "tools"},
    "body": (
        "Settings, Tools it can use, Use these tools from another app: a snippet to paste into an MCP client such as "
        "Claude Desktop, which can then read your notes (never a private one) and use your skills as prompts. It reads "
        "only until you tick Let that app add and change notes; deleting is never offered. Make a link gives an app an "
        "address and its own token, shown once, to revoke; Categories and Tags limit it to those notes only, so it cannot "
        "search, read or change any other. An app such as claude.ai can sign in with OAuth instead: its page waits, the "
        "sign-in shows under Waiting to sign in with a short code, and you press Approve on this computer. The link works "
        "only on this computer unless LAN mode is on, and nothing is sent anywhere else."
    ),
}
MCP_LINKS_META = {
    "title": "Use your notes from another app",
    "path": "Settings, Tools it can use, Use these tools from another app",
    "target": "mcp-config-group",
}
