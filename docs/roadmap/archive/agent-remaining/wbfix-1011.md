# wbfix-1011: Undo of a deleted shape adds `"layer":""` to its data

Brief for an Opus agent. Begin with `docs/roadmap/agent-remaining/agent_common.md` and the `orient` skill.
Branch `agent/wbfix-1011`, worktree `scratchpad/wt-wbfix`, port 8797.

## The failing check

`scratchpad/ui-sweeps/wbtrash660.js`, desktop 1440 (`ONLY=board`, default):
`shape: Undo restores the board identically` FAILS. Result: 38/39 passed. Every other check passes, including the note card, the text boxes, the multi-selection, the map topic and the Escape case.

## The exact diff

The sweep compares the board as text (`boardState()`, ids left out). Before the delete and after Undo, only one line differs. It is the rect shape, the `S` row:

```
before: S {"type":"rect","d":"M360 200 L460 200 L460 280 L360 280 Z","color":"#3b82f6","width":3}
after:  S {"type":"rect","d":"M360 200 L460 200 L460 280 L360 280 Z","color":"#3b82f6","width":3,"layer":""}
```

The only change is one extra key, `"layer":""`, appended to the sketch's `data` JSON string. Its `d`, `color` and `width` are unchanged. The `N` row (note card) and both `O text` rows are identical.

## Where it comes from

1. `frontend/js/whiteboard.js:8685`: Undo of a delete re-creates the item with `POST` and a payload passed through `wbKeepOwnLayer`.
2. `frontend/js/whiteboard-library.js:1653-1662`, `wbKeepOwnLayer`: for a sketch it parses `data` and, when there is no truthy `layer`, writes `layer: ""`. For an object (line 1654) it does the same to `payload.data`. Its comment says the restore sends `""` so the item "comes back where it was rather than onto whichever layer is current now".
3. `src/memorymap/api/routes_whiteboard.py:1328`, `_on_current_layer`: on every create, if `"layer"` is absent it stamps the current layer. If the key is present (even `""`) it stores the data as sent. So `""` is stored verbatim. That is the source of the extra key: the original sketch was created without a `layer` key, the stamp found no current layer, and nothing was added. The restore sends `""` to block the stamp, and the server keeps it.

Both sketch create paths call it (`routes_whiteboard.py:2930` and `:3011`), and `routes_board_library.py:56` imports it.

## What to decide and fix

- Recommended: make `""` mean "no layer" on the server. In `_on_current_layer`, when `data.get("layer") == ""`, return the data with the `layer` key removed and do not stamp. Then Undo sends `""` as now, the stored JSON matches the original, and the comment's intent still holds. Check that the readers treat an absent key and `""` alike: `wbSketchData(item)?.layer || null` (whiteboard-library.js:1564) and `wbNamedLayerFlag(data.layer, ...)` (whiteboard.js:5692, 8976) both do on a falsy value. Confirm the sketch and object paths both go through this one function.
- Do not fix it by changing the sweep's comparator to ignore `layer`. That hides a real change to stored data.
- Objects: the same `layer:""` is written for text boxes (`wbKeepOwnLayer` line 1654). `wbtrash660.js` does not show it, because `boardState()` prints only `o.data?.content` for objects. Add `data.layer` to the object row of the comparator, measure before and after, then fix both kinds together. Not measured yet.

## Tests and gate

- Add a targeted test first, in the file that covers `_on_current_layer` (grep `_on_current_layer` under `tests/`): create with `layer: ""`, assert the stored data has no `layer` key; create with no key on a board with a current layer, assert the stamp still happens.
- Restart the server after the Python change (uvicorn does not reload).
- Rerun `ONLY=board node scratchpad/ui-sweeps/wbtrash660.js` (expect 39/39) and `scripts/gate.sh --changed`. Never the full suite.

## Found, not fixed

- `scratchpad/ui-sweeps/wbphone.js` (fixed by the sweep commit, not an app issue): intermittent. Across about 12 runs it failed 2 times. One failure was `page.click` blocked by the first-run "Check for updates" confirm, now dismissed. The other was the template dialog not opening in 5 click attempts over 20s; the cause is not known. Retries added to the sweep; a stack trace from that failure was not captured. The sweep waits for `#wb-template-dialog[open]` now.
