# CI fixes round 2 (stopped mid-run, 2026-10-17)

Source: CI run 39047044822, job 117437803578, head 61e3ab9, 13 failed on Python 3.13.

Done in this WIP commit (uncommitted edits saved as-is, not yet re-tested):
- proofread.py, supersede.py, recognise.py: bounded runs for the source lint.
- core/hardware.py: creationflags=NO_WINDOW on the subprocess call.
- tests/test_list_endpoints_page.py, tests/test_list_limits.py: bounded list entries ("Now the list_commands bounded entries").

Still to do (from the brief): test_chat_transcript (taskLogButton shape in ai-tools.js), test_no_ui_emoji (kaomoji in icon-picker.js, keep the faces), test_undo_coverage (saveModelHardware), test_ui_1017b (CSS rule text now `#task-history .entry-meta { flex-wrap: nowrap; }`), plus six failures not yet read from the job log. Re-run all failing tests, then gate.sh --staged.
