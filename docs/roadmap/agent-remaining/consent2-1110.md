# consent2-1110: fixes from the review of the consent change (380e39fe1 / a425acfd1)

Done (this branch, see `git log`): items 1 to 8 of the review brief.

1. Stale card: `chatHistoryToSend` (answer-kit.js) names only the last waiting card and marks every card not pending on each send; `consent.read` honours `pending_*` only on a last turn that has an answer.
2. Server binding: `ai/consent_store.py` (single-use id, 1800 s, 64 cards), `consent.attach` in `_event` parks every waiting act or confirm card and strips `_say`; `ChatTurn.pending_steps/pending_skipped/pending_tool` are gone (so no size to bound), `pending_id` replaces them; Confirm sends `consent_id` and spends it.
3. Typed yes on a tool: Undo row from the tool's undo and `refreshAfterToolChanges` on every settle (`chat_agent.consent_events`, `ask-compose.js`).
4. `_YES_WORDS` lost fine, why not, alright, all right; `wait` is no longer filler.
5. Bare yes to an offer: `req.offer_yes` in `_follow_up`; `_act_planned_events` runs it with Undo unless the plan is the "already have" duplicate ask.
6. Composed wording on Confirm and typed yes: `acts.run_said` (restored `ticked_line`), the mood parked with the card; exact asserts restored in test_acts, test_engine_acts, test_composer_r9_acts_1109, test_composer_audit_1030, test_composer_todo_line_1109, test_follow_items_1110, test_slot_reply_1570; `tests/_consent.py` presses Confirm with the card's id.
7. `MAX_PARKED_CONFIRMS` 2 to 12.
8. `"run": True` keys removed; `commands.plan` words a plan whose line is only its card label as the confirm line.

Left (found, not fixed):
- ~~Cards from `starter_acts` and the model's `act_registry.propose` carry no `_say`~~ Built (compleft-1110.md, `acts.plain_say`).
- Not driven in a browser: the open-card JS (`consentId`, `waitingCard`, the send-time clearing) is node-checked and read, not watched. A 30 minute old card still runs from its Confirm button (client steps, plain words) but not from a typed yes.
- A tool undo whose tool is not in `commands.RUNNABLE` draws no Undo row after a typed yes (the Confirm button path draws none either).
