# Quick sketch on its own

Tessellate's Quick sketch pad running on its own page. It uses the same two
files as the app: `frontend/js/sketch-pad.js` and `frontend/css/sketch-pad.css`.
In the app, `openSketch` (media.js) hands the pad a host that saves to notes
and uses the app's menu, help popover, confirm dialog and preferences. With
no host, the pad falls back to its built-in defaults: settings kept for the
visit, the browser's confirm dialog, its own menu and help panel, and
Download PNG. This page's `boot.js` hands it a `prefs` that keeps the
settings in localStorage.

## Run it

From the repository root:

```bash
python3 -m http.server 8862
# open http://127.0.0.1:8862/tools/sketch-standalone/
```

## Files to copy

Keep the same relative layout, or change the four paths in `index.html`.

| File | What it is |
| --- | --- |
| `tools/sketch-standalone/index.html` | The page: one card, the stylesheets, two scripts |
| `tools/sketch-standalone/boot.js` | Opens the pad and follows the system's light or dark setting |
| `tools/sketch-standalone/standalone.css` | The page around the pad, plus three tokens the app sets in later sheets |
| `frontend/js/sketch-pad.js` | The pad: tools, canvases, undo, keyboard, the markup it builds |
| `frontend/css/sketch-pad.css` | The pad's styles, all from the app's tokens |
| `frontend/css/00-tokens-shell.css` | The app's design tokens (colour, space, radius, type) and its card |
| `frontend/vendor/phosphor/` (`style.css`, `Phosphor.woff2`, `Phosphor.woff`, `Phosphor.ttf`, `LICENSE`) | The icon font |
| `frontend/vendor/atkinson/` (four `.woff2` files, `LICENSE`) | The app's reading font, which `00-tokens-shell.css` references (optional: without it the system font is used) |

## Using it elsewhere

```js
SketchPad.open(element, {
  title: "Quick sketch",
  save: async (blob, caption) => { /* store the PNG; throw to show an error */ },
});
```

Every host hook is optional: `save`, `toast` (`(message, isError)`),
`confirm` (`(message, { confirmLabel, cancelLabel })`), `prefs`
(`{ get(key, fallback), set(key, value) }`), `highlighter`, `menu`, `wireHelp`,
`singleKeys` and `close`. `SKETCH_HOST_DEFAULTS` at the top of
`sketch-pad.js` lists them with their fallbacks.

## Licence

Tessellate is AGPL-3.0, so a copy of these files is under AGPL-3.0 too. The
Phosphor icons are MIT and the Atkinson Hyperlegible font is under the SIL
Open Font License; each folder keeps its own `LICENSE`.
