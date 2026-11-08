# smalla-1108 remaining (Batch A of small-rows-1108.md)

Done: all three rows built, one commit each (branch `agent/smalla-1108`).

- Look export and import: `settings.js` `settingsLook.lookFile` (markers `LOOK FILE BEGIN`/`END`), buttons in "Your themes". `tests/test_look_share_1108.py`.
- Surprise mix: same object (`pick`, `surpriseNow`), button in Theme & colour. `tests/test_look_mix_1108.py`. The existing Themes "Surprise me" (random whole theme, `settings-controls.js` `theme-surprise`) is unchanged.
- Line spacing and line width: two Typography & layout lists, attribute rules. `tests/test_reading_tokens_1108.py`.

Left, one line each:

- `BACKLOG.md` Colours: per-surface accents and a custom palette builder are still open (not in this batch).
- `BACKLOG.md` More themes and palettes: "a Surprise me that generates a coherent one" (generated, not picked) is still open.
- Line height and measure are attribute rules, not tokens, because `tests/test_style_scale.py` caps custom properties at 428 and the stylesheet was at the cap; if the owner wants real `--read-leading` and `--read-measure` tokens, two other custom properties must go first.
- Live editor (CodeMirror) line height is not scaled by Line spacing; its measure is (`--doc-measure`).
- Not verified: the settings window with the new rows on a phone width; a real note and document on screen (probe elements with the real selectors were measured).
- Port 8797 was already served by another checkout, so the sweeps ran on 8796 (data dir under the session scratchpad); that server is still running and is mine to stop.
- `docs/CODEMAP.md` and `CHANGELOG.md` were not edited (instructed); `tests/test_codemap_fresh.py` fails until the orchestrator runs `python scripts/codemap.py`.
