# content3-1101: row 2a leftovers and INBOX 1499 (the documents repository)

Branch agent/content3-1101 from claude/sharp-thompson-45hngp; port 8861.

- done: step 1 binned documents walked and exported (decision recorded in row 2a); step 2 reminder and recording write routes through `content.writable` (a recording's 404 text is now "That recording could not be found.", read and write alike).
- done: step 3 `repo/documents.py` (document list, outline and contents reads, create, history, AI-edit log); MOVED gains DocumentRevision and DocumentAiEdit (Document and DocumentLink are still read by other routers); ORM cap 843 to 811.
- drive: `content3/drive.py` in the session scratch against :8861 (create, edit, bin, 409, restore, folder export, reminder and recording 409).
- left (not in this brief): Document and DocumentLink reads in routes_entries, routes_graph, routes_timeline, routes_mentions, chat_*, routes_diag, routes_debug, routes_bench, routes_code_assist, routes_conversations, routes_whiteboard keep `Document` out of MOVED.
