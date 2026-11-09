# chatfoot-1109 (INBOX 1706): remaining

- done: 1 foot buttons are `ghost quiet` text buttons (answer-kit.js `answerFootGather`, answer-foot-lazy.css); 2 caret in the flow at the label end (static, contrast 8.79, rotates open); 4 and the live/reload split (composed support saved with the turn: routes_conversations.py `TurnBody.support`, grounding.py `composed_support`; sources counted by `composed` in `chatSourcesFrom`).
- not reproduced: 3 "buttons disappeared" after opening Why (live and reloaded, real clicks, 4 of 4 chips kept; digest answer too). Likely the digest or reload split above (a reloaded digest answer drew Cites and the evidence count, which the live one never does), not a removal. If it returns, log `.answer-foot-bar` mutations as in the sweep (answer-kit.js:2911 `bar.remove()` is the only removal).
- not verified: touch size of the quiet chips on a phone (28.6 px tall at 1920; the `.chip-interactive` overhang is gone); light theme.
- next: an Ask tab stored turn (routes_ask_history.py:133) still recounts support with the model counter; Ask history has no `by.composed` to branch on.
