# perfdgm-1108 remaining

- done P2: lazy row menus (diagram-library.js lazyKebab; builder and kinds call it). Not done: delegate shape/connect/chip listeners (about 3 per row left); start mermaid fetch parallel to document fetch; idle-slice rows. Pre-existing: a real mouse press on a row opener can land on .dgm-joins (pointerdown lands there, pointerup on the glyph), seen in Playwright on baseline too.
- next: P3 relabel debounce (diagram-builder.js drawPicture, put new code outside the builder: gzip cap 11,995 of 12,000).
