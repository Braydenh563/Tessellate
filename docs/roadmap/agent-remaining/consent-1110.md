# consent-1110: consent for every act (owner 2026-11-10, HANDOVER "Consent for every act")

Inventory (every act path; "waits" means a card with Confirm and Cancel, or a typed yes):

| path | before | now |
| --- | --- | --- |
| `commands.plan` intents reminder, complete, uncomplete, cancel, snooze, new_note, meeting, pin, unpin | ran at once with Undo (`"run": True`, `routes_chat._act_planned_events`) | waits (`plan` drops `run` and words the line as a confirm) |
| `task_acts` list-line remove, tick, snooze, add to list | ran at once | waits (same wrapper) |
| `follow_items` (remove milk, make it 6, add butter, rename it) | rewritten to a sentence, then ran at once | waits (goes through the same plan) |
| delete, rename, move, tag, untag, link, unlink, append, rename_tag, rename_category, restore | waited | waits |
| `composer_talk.accepted_offer` ("yes" to "Shall I remind you ...") | rewrote to "remind me to ...", ran at once | the reminder card waits, one more Confirm or typed yes (F12 owns the offer wording) |
| starter acts (`starter_acts`) | cards that waited | waits |
| agent tool calls: destructive and CHANGE_TOOLS | parked | parks |
| agent tool calls: ADD_TOOLS (create_note, tag_note add, pin_note, set_reminder ...) | ran | parks (`tool_focus.needs_confirm`: every WRITE_TOOL; a plan or skill run the person started stays approved for adds) |
| `/chat/command/run`, `/chat/tools/execute` | Confirm and Undo buttons | unchanged |
| the Guide, Ask | describe acts, never run them | unchanged |

Done: typed yes or no (`ai/consent.py`, `api/chat_agent.consent_events`, `ChatTurn.pending_steps/pending_skipped/pending_tool`, `ask-compose.js`, `answer-kit.js`), G2 (note about X, make a note private, snooze TypeError, chat_turn exception text).

Left (found, not fixed):
- `task_acts.py` still builds some plans with a `"run": True` key that `commands.plan` now drops; remove the key from the five sites (task_acts.py:200, 631, 685, 770; commands.py:1546, 1633, 1643, 1893) in one sweep when F12 lands, to keep the conflict small.
- The Undo row after a typed yes on a parked tool call is not drawn (the tool result's undo is in the batch format; `consent_events` says "Done" only). The Confirm button path still gives the toast.
- "write a packing list for japan" still offers an empty checklist note (`task_acts.py:142`, by design from composer-r7); the card shows "- [ ]" in its label.
- The agent's `MAX_PARKED_CONFIRMS = 2` now also limits a model that wants to add three notes in one turn; it is told to wait for approval.
- Not driven in a browser: the open-card JS (`pendingRun`, `settle`) is node-checked and read, not watched.
