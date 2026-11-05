# diagram R1 (INBOX 1613), 1104

- done: shape menu rows draw their glyph with a trailing check; row swatch is a `button.dgm-swatch` named "Shape: <label>" that opens the same menu (diagram-builder.js `shapeItems`, `shapeRow`, `shapeButton`; diagram-lazy.css end).
- not verified: touch (long press and a phone width), dark theme, screen reader announcement of `aria-current` on the chosen row.
- left: the swatch menu opens right-aligned to the swatch (the kebab recipe's own placement), so it sits left of the swatch; left as the recipe.
