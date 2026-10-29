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
