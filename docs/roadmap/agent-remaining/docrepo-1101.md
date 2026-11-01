# docrepo-1101: Document and DocumentLink reads behind repo/documents.py

Branch agent/docrepo-1101; port 8871.

- done: chat group (chat_attach, chat_pool, chat_said)
- next: routes_conversations, routes_whiteboard, routes_bench, routes_reminders, routes_mentions
- done: 4dafc27 chat group; second group (routes_conversations, whiteboard, bench, reminders, mentions) in the commit after
- next: routes_entries (find x2, mention_rows, attached_to), then routes_graph, routes_library, timeline/diag/debug/code_assist/documents
- done: 7bed0ab second group; routes_entries in the commit after
- next: routes_graph (link_pairs, unshelved, held, pinned), routes_library, timeline/diag/debug/code_assist/documents (python3 scratchpad/groups.py graph|library|rest)
- done: b7ef14b routes_entries; routes_graph in the commit after
- next: routes_library, timeline/diag/debug/code_assist/documents, then MOVED gains Document and DocumentLink (python3 scratchpad/groups.py library|rest)
- done: 032af9b routes_graph; routes_library in the commit after
- next: timeline/diag/debug/code_assist/documents, then MOVED gains Document and DocumentLink (python3 scratchpad/groups.py rest)
- done: 019029a routes_library; last group (timeline, diag, debug, code_assist, documents) plus MOVED in the commit after
- next: nothing in the brief; routes_spaces.py:92 and :383 name Document and DocumentLink (CROSS_RESOURCE) when spaces move
