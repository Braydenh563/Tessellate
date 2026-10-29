# INBOX 1436: sketch and noise art, the paused picture, the cheaper pass

Plan block: "Placed from INBOX, 2026-10-29" at the end of `docs/roadmap/UI_MODERNISATION_PLAN.md`.
Steps: A baseline, B long pause becomes a picture, C Wander and Drift, D cheaper-equivalent pass.

## A. Baseline (before any change)

`scratchpad/ui-sweeps/bgartcost.js`, dark theme, 1440x900, `CPU=1` (CPU-backed canvas), this four-core
sandbox (so the art holds to 20 fps; mesh asks for 15 and dusk for 10). Server on :8806, a fresh data dir.
Paint is the draw plus the raster it causes, per frame. Allocation is the art-attributed sampled heap over 10 s
(it includes the page code running under the art's frames, so read it against the other rows, not against zero).

| style | script ms | paint median ms | fps | main thread ms/s | browser CPU ms/s | alloc KB / 10 s |
| --- | --- | --- | --- | --- | --- | --- |
| aurora | 0.87 | 0.88 | 20 | 76.7 | 418 | 2029 |
| constellation | 0.49 | 1.80 | 20 | 117.1 | 662 | 3327 |
| waves | 0.08 | 0.87 | 20 | 73.4 | 380 | 1583 |
| bubbles | 0.11 | 1.18 | 20 | 109.7 | 356 | 2160 |
| mesh | 0.09 | 0.91 | 15 | 58.8 | 300 | 1679 |
| microbes | 0.38 | 2.15 | 20 | 151.0 | 340 | 2871 |
| mycelium | 0.15 | 0.51 | 20 | 135.4 | 372 | 1698 |
| dusk | 0.08 | 0.21 | 10 | 37.0 | 280 | 1626 |
| ripples | 0.05 | 0.45 | 20 | 57.2 | 374 | 1810 |
| fireflies | 0.17 | 0.66 | 20 | 62.3 | 376 | 2384 |
| rain | 0.06 | 0.44 | 20 | 61.1 | 396 | 1646 |

The most expensive existing style is microbes (2.15 ms median paint; constellation has the larger p95, 5.79 ms).
Neither new style may pass microbes' 2.15 ms.

### Paused cost, before (`PAUSE=1 PAUSE_WAIT=22 CPU=1`, a hidden tab)

| style | moving | paused 3 s | paused 24 s | resumed |
| --- | --- | --- | --- | --- |
| aurora | canvas 1, rAF 120 / 2 s, heap 20.1 MB, RSS 726 MB | canvas 1, rAF 0, heap 19.4, RSS 715 | canvas 1, rAF 0, heap 14.8, RSS 693 | canvas 1, rAF 120 |
| constellation | canvas 1, rAF 120, heap 16.4, RSS 860 | canvas 1, rAF 0, heap 17.0, RSS 842 | canvas 1, rAF 0, heap 14.6, RSS 760 | canvas 1, rAF 120 |
| mycelium (twin) | canvas 2, rAF 121, heap 16.2, RSS 913 | canvas 2, rAF 0, heap 17.5, RSS 904 | canvas 2, rAF 0, heap 14.5, RSS 774 | canvas 2, rAF 120 |

The rAF figure counts every callback with p5 or bg-art.js on the stack, and the header emblem is a p5 sketch, so
the moving figure (120 in 2 s) is the emblem's 60 a second plus the art's; the 0 while paused is the art
having stopped (the emblem stops with a hidden tab). A pause already costs no frames, so what a long pause can
still save is the mounted canvas (1 or 2 canvases kept in the DOM and composited) and, if it were freed, its bitmap.
Browser RSS moves by tens of MB between samples from the garbage collector alone and is not a clean signal.
Only three styles were measured for the paused baseline: the other styles take the same path (one canvas, no rAF).

## B. A pause of 20 s or more becomes a picture (built)

`bgArtApplyPause` starts a 20 s timer (`BG_ART_FREEZE_MS`) when the first pause cause appears and clears it on
resume. At 20 s `bgArtFreeze` captures the canvas through `bgArtMountStill` (the still path's own `toBlob`,
now shared; a canvas element's CSS background, the constellation's nebula, is laid under the image; the
mycelium's two canvases are flattened first at their fade opacity), waits for the image to decode, then takes
the canvas out of the page. A resume (`bgArtThaw`) puts the canvas back, removes the picture, and the loop goes on.
Hidden tab included (the same pause flag). A timer that fires early waits out the rest; a resume while the
picture is encoding discards it.

Which: **kept state**. The style's closure (typed arrays, seed, clock) and the canvas bitmap stay in memory, so
the art continues exactly where it was. A restart with the same seed would free the bitmap but lose the picture
the person was looking at, so it was not chosen. What a long pause now frees is the live layer: the canvas
element(s) leave the DOM and the compositor, and one image layer stands in.

Measured (`PAUSE=1 PAUSE_WAIT=22 CPU=1`, dark, a hidden tab; canvases and pictures in the DOM, art rAF in 2 s):

| style | paused 3 s, before | paused 24 s, before | paused 24 s, after | resumed, after |
| --- | --- | --- | --- | --- |
| aurora | canvas 1, still 0, rAF 0 | canvas 1, still 0 | canvas 0, still 1, rAF 0 | canvas 1, still 0, rAF 120 |
| constellation | canvas 1, rAF 0 | canvas 1 | canvas 0, still 1, rAF 0 | canvas 1, still 0, rAF 120 |
| mycelium (twin) | canvas 2, rAF 0 | canvas 2 | canvas 0, still 1, rAF 0 | canvas 2, still 0, rAF 120 |

JS heap and browser RSS did not move beyond the run-to-run noise (aurora 693 to 705 MB, constellation 760 to 758,
mycelium 774 to 797), as expected: the bitmap is kept. Not verified: GPU memory of the freed layer, or a real
window minimised on Windows.

## C. Wander and Drift (built)

Both follow the file's header rules (typed arrays, nothing allocated per frame, pixel density at most 1, colours from
`ctx.baseHue`, dark adds light and light lays ink, still by capture through `settle` plus one frame).
Registered in `BG_ART_BUILDERS`, `BG_ART_STYLES`, `BG_ART_INFO` (the Appearance grid) and `BG_ART_COST`; the Guide
topic `background-art` (`ai/help_topics_more.py`) names both and the 20 s picture.

- **Wander**: 3 to 6 pens (accent hue and two 40 degree offsets), 7 steps a frame each as one path onto a
  persistent canvas at pixel density 0.5, 20 fps, a heading that keeps 82 percent of itself, `bgTurnBack` at the
  edges, `destination-out` 10 percent every 4 s, a stroke restarts after 2,600 frames. Still: `settle` walks 70 frames ahead.
- **Drift**: `bgHash2` lattice table, three octaves, smoothstep, 180x113 buffer at pixel density 0.125 into one
  reused `ImageData` (`putImageData`, scaled by CSS), 12 fps with a third of the rows recomputed per frame, a colour
  table between two tones 40 degrees apart. The first version called a per-pixel noise function and allocated 58 MB
  in 10 s (V8 boxed the fractional arguments, as the file's header warned); `bgFbmRow` does a whole row in one
  function over a prebuilt lattice: 1.6 MB.

Measured (`bgartcost.js`, `CPU=1`, same sandbox, still check on):

| style | theme | script ms | paint median ms | fps | alloc KB / 10 s | still |
| --- | --- | --- | --- | --- | --- | --- |
| wander | dark | 0.04 | 0.11 | 20 | 2,439 | 0 rAF, no canvas, image set |
| wander | light | 0.04 | 0.12 | 20 | 2,472 | same |
| drift | dark | 0.37 | 0.41 | 12 | 1,609 | 0 rAF, no canvas, image set |
| drift | light | 0.36 | 0.40 | 12 | 1,629 | same |

Both are under microbes' 2.15 ms (the most expensive style) and under the cheapest tier boundary (Light is under
0.5 ms). `BG_ART_COST` holds 0.12 and 0.41. Art-only pixels (`pngpixel.py`): drift dark (43,26,90) at the centre
against a page of about (31,31,31); drift light (204,204,238). Not verified: contrast of the muted dashboard
text over each (bgartcontrast.js was not run for the new styles), a real-model or Windows machine.
