"""No script writes a `style` attribute: the page's CSP refuses it.

`style-src 'self'` has no 'unsafe-inline', so `el.setAttribute("style", ...)`
and d3's `.attr("style", ...)` are refused, and each refusal is a console
error. The CSSOM (`el.style.x = ...`, `el.style.setProperty`, `cssText`) is
not an inline style to the CSP and works. Found on the graph's old SVG export
(`graphInlineComputedStyle`), which wrote one per element of the clone: 6,278
refusals for one export of the 417-note fixture, while the picture came out
right, because the attribute was kept. That export went with the SVG renderer
(audit 1029 row 60), so only the rule stays. CLAUDE.md section 6,
shape 4, is the same rule for markup.
"""

from __future__ import annotations

import re

from tests._css_paths import FRONTEND_DIR

PATTERN = re.compile(r"""(?:setAttribute|\.attr)\(\s*["']style["']""")


def test_no_script_writes_a_style_attribute():
    offenders = []
    for path in sorted((FRONTEND_DIR / "js").glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            if PATTERN.search(line):
                offenders.append(f"{path.name}:{number}: {stripped[:100]}")
    assert offenders == [], (
        "a `style` attribute written from script is refused by the CSP and "
        "logs an error; set the property through the CSSOM (`el.style.x =`) "
        "or, on an SVG export clone, as a presentation attribute:\n"
        + "\n".join(offenders)
    )
