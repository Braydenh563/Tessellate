# attach-1031 (INBOX 1460, notebook attachment cards)

Done: notebook items on a message are one card (`notebookCard`, chat-agent.js), staged with a remove x and sent above the question; a press previews it with Open (`attachmentPeek`, attachment-peek.js, lazy). The extract panel's proposal cards moved to the lazy extract-preview.js to pay for the boot bytes.

Done (fixes-1031): a map rides `board_ids` with the turn and reload draws its card; a reloaded note's name is its whole first line (the page names it, as at send); a map's preview lists its topics and a file's its opening text (attachment-peek.js).

Remaining:
- Not verified: a real chat send with a model (fake transport only); the light theme run of the sweep covered the 1 and 5 card cases and the four kinds, not a screenshot read; the map and file previews were read as text from a seeded chat on :8808, not shot.
- A map attached before this change has no `board_ids` on its stored turn, so old chats stay without the card (nothing to recover it from).
