# attach-1031 (INBOX 1460, notebook attachment cards)

Done: notebook items on a message are one card (`notebookCard`, chat-agent.js), staged with a remove x and sent above the question; a press previews it with Open (`attachmentPeek`, attachment-peek.js, lazy). The extract panel's proposal cards moved to the lazy extract-preview.js to pay for the boot bytes.

Remaining:
- Maps are not stored with a turn: a reloaded chat loses an attached mind map (no `board_ids` on the conversation row, `_hydrate_attachments` in src/tessellate/api/routes_conversations.py:455). Owner words: "Restored chats (reload) render the same."
- A reloaded note card's name is the server's first line cut at 60 characters (routes_conversations.py:525); it is re-derived from the loaded note when the notebook has it, else cut without an ellipsis.
- A map or library file preview shows only its facts line (no outline or text); a document's opening words are fetched.
- Not verified: a real chat send with a model (fake transport only); the light theme run of the sweep covered the 1 and 5 card cases and the four kinds, not a screenshot read.
