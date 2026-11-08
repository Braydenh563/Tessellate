# smalld-1108 remaining

Built (one commit each, see git log): review fixes on batch C (case transforms and picks leave note questions alone, a bare day and month in a week question is this year, fractions to two decimals); stale rows verified and moved to HISTORY (T11, T5 plus "reading time of", C6, X4, X6, X12, X18); T1 round, floor, ceil, log, ln, pow, "2(3+4)" in `ai/composer_sums.py`; T6 join, split, count characters in `ai/composer_text.py`; Unix epoch both ways in `ai/composer_epoch.py`. Tests: `tests/test_composer_smalld_1108.py`.

Left:
- X5 rename a tag or category by chat: "rename the tag gym to fitness" is not read by `commands.read_typed`; the `rename_tag` and `rename_category` tools exist (`act_registry.py:309`). Needs a typed reader plus a confirm card.
- X8 restore ("restore the passport note") is not read by `commands.read_typed`; `restore` is routed as an app-only verb (`act_registry._APP_VERB`).
- X10 "add X to today's note", X11 "summarise ... into a note", X13 templates with variables, X14 bulk preview, X15 scheduled acts, X16 generic "undo that", X17 "cancel"/"never mind" for a pending act: not read as chat verbs (probed with `commands.read_typed`); each needs the confirm-first path in `routes_chat.py`, which is at its line cap.
- T6 acting on a named note ("uppercase the passport note"): needs the confirm-first draft path.
- C1 return-after-a-gap greeting and A17 "then and now": unchanged from smallc-1108 (need route data).
- Unix time shows UTC only; a local-time line would need the device zone from the client.
- Not run: the full composer suite and the full gate (targeted tests and `gate.sh --staged` only). No real-model check; by decision 75 these readers answer only with no model or From your notes.
