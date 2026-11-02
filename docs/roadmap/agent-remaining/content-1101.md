# content-1101: Content protocol (row 2a) and the reminders repository (INBOX 1499)

Branch agent/content-1101 from claude/sharp-thompson-45hngp at 239744d; port 8845.

- done: 5c86b57 row 2a design in audit-1031-ranked.md; step (1) the bin guard, `repo/content.py`, tests/test_content_protocol.py (before 404, 404, 200; after 409).
- done: 179be8e reminders repository, `repo/reminders.py`; `Reminder` in `MOVED`; ORM_CALLS_CAP 870 to 843; tests/test_repo_reminders.py.
- drive on :8845 (untracked `drive-content.js` in the session scratch): magic add rows 1 to 2, tick done true, weekly complete rolls 7 days, twin flagged, bin 200 / read 404 / restore 200 / purge live 409 / purge binned 200, ics 3 events re-imported as 0 added 3 updated; binned document, board, file writes 409 with the noun's sentence; Library bin restore of the document by its dialog then GET 200, PUT 200.

Left (owner's words from audit 1031 AR7: "one bin, one undo table and one export walker"):
- row 2a steps (2) and (3): built in content2-1101 (see docs/roadmap/agent-remaining/content2-1101.md).
- row 3a next resource: tags (src/tessellate/api/routes_tags*.py), then properties.
