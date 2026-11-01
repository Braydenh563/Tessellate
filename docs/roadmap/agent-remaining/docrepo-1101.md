# docrepo-1101: Document and DocumentLink reads behind repo/documents.py

Branch agent/docrepo-1101 from claude/sharp-thompson-45hngp; port 8871.

- done: 4dafc27 chat (attach, pool, said); 7bed0ab conversations, whiteboard, bench, reminders, mentions; b7ef14b routes_entries; 032af9b routes_graph; 019029a routes_library; 9987da6 timeline, diag, debug, code_assist, documents, `Document` and `DocumentLink` in MOVED, ORM cap 811 to 767.
- drive: `docrepo_drive.py` in the session scratch, same sequence against the new code (:8871) and the base (:8872): identical output (graph, pins, references, backlinks, library, timeline, diagnostics, health, reminders, chat attach, extract commit).
- left: `routes_spaces.py` lines 92 and 383 to 400 still name `Document` and `DocumentLink` (CROSS_RESOURCE, until spaces move, row 3a); non-api readers (ai/, entry/, core/, search/) keep direct reads, the boundary test covers `api/` only.
