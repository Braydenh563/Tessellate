# dgpic-1109: INBOX 1661 (l), mind map and timeline edited on their picture (agent dgpic, branch agent/dgpic-1109)

## Design

- Mermaid 12.2 numbers mind map boxes (`<g class="node mindmap-node" id="…-node_N">`) and timeline boxes (`<path id="…-node-N">`) in source order; box N is row N of the same walk (diagram-tree-canvas.js `order`), its words checked so a stale drawing drops a box rather than mis-assign it. A timeline with sections does not draw its free periods; `order` skips them.
- Shared editing (`edit` in diagram-seq-canvas.js): pick, double press or Enter or F2 rename, Delete, Alt+arrows. The builder loads seq-canvas for every kind; it loads the tree file for a mind map or a timeline. Overlay keys on `S.hitAt`.
- Drags use the list's own engine (diagram-kinds.js `seedBlock` asks `treeCanvas.node`, `dropAt` asks `treeCanvas.over`); `spot` uses the list's thresholds (0.28/0.72), an event down its period, the rest across.

## Done (1440 px, sweeps untracked in the session scratch dgp/: pic.js, shelf.js)

- Mind map: 6 of 6 boxes picked by a press at their centre (two "Same" leaves, two keys); double press on Beta, typed Bravo: source and picture renamed; Gamma dragged to Alpha's left edge, caption "Before Alpha": source Gamma, Alpha, Bravo. Leaf tile dropped on Alpha's middle, caption "Into Alpha": Idea under Alpha. No page errors.
- Timeline: 8 of 8 boxes picked (two "one" events); event two renamed deux in place; 2021 dragged to 2020's left edge, caption "Before 2020": source 2021 : deux before 2020 : one. No page errors.
- Sequence after the refactor: 6 of 6 parts picked, req renamed ask, App head dragged past Server: User, Server, App. No page errors.

## Left

- A new part added with the list folded is named on a mind map or timeline picture (`S.seqOpen`), not measured.
- Not verified: 390 px, real touch (the engine's hold should carry a drawn part, unmeasured), real inference.

- done: f467cc3 (picture map, pick, rename, drag, shelf drop on a part, Guide).
- next: the Left lines above; nothing in progress.
