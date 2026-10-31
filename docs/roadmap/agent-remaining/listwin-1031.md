# listwin-1031 remaining list

done: S16 and S53 in one commit (shared `windowRows`, notes-list.js; Timeline feed on it, timeline.js).

Left:
- Placeholders are one element per row (5,000 notes are 5,000 `li.row-shell`); a run-length spacer would bound that too, but the keyboard walk, `entryListItems` and selection ranges count shells, so it is a rewrite of three callers for a cost measured in single milliseconds. Not started.
- The Timeline table view (`timelineTableRow`, paintTimelineTable) still builds every loaded row; only the feed is windowed. Table rows are `tr` and the selection column reads the DOM.
- Timeline shell guesses (`TIMELINE_ROW_GUESS`) were measured on title-only notes (41.6 px a row); a notebook with snippets is taller until a row has drawn once.
- Found, not mine: `tests/test_global_scope_ratchet.py::test_cross_file_guards_only_go_down` fails on the base (277 guards, cap 276).
