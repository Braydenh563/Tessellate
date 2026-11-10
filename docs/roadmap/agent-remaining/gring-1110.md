# gring-1110: INBOX 1723, the graph's hover ring

- done: e55d6b50f, a pointer hover is the node's own halo plus a 1.5px hairline (`gcHoverMark.draw`, cached sprite `gcHoverMark.cache`); keyboard, open card and search current keep a 2px accent ring 3px clear; tests/test_graph_hover_ring_1723.py; DESIGN.md recipe row.
- measured (sweep untracked, scratch `gring/ring.js`, 30px node at zoom 2): before 4px solid #78a8ff (dark) / #2f5bd3 (light) on the edge; after no accent pixel on hover, hairline peak 4.8:1 (dark) and 3.3:1 (light) against the halo beside it; focus ring 5.0:1 (dark) and 4.8:1 (light) against the ground beside it; gcDraw with a hover easing 0.20 to 0.21-0.32 ms median dark, 0.29 to 0.42 ms light (run-to-run noise about 0.1 ms).
- not verified: high-DPI (dpr 2) crops; a phone; matched and traced-path rings left as they were (accent on the edge), not in the owner's ask.
- next: none for 1723. Possible follow-up for the owner: the search-matched and path rings still straddle the dot's edge in accent; same offset treatment if wanted (graph-canvas.js, `item.onPath` / `item.matched` branches in gcDraw's ring loop).
