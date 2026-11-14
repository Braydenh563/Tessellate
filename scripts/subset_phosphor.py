"""Rebuild the boot icon font: `Phosphor.woff2` as a subset of the full font.

    python scripts/subset_phosphor.py

L-world-class-70 (INBOX 1780). `Phosphor-full.woff2` is the whole vendored
font (1,530 icons); `Phosphor.woff2` holds only the icons the code names, so
the first paint fetches the small file. `style.css` lists the subset first and
the full font second in the `.ph` font stack, so a glyph the subset lacks (an
icon picked from the picker, or a stored `ph:name` outside the code's own
names) falls back to the full file, which the browser fetches only then.

Run it again when icon names are added: `tests/test_icon_names.py` keeps the
names valid against the full font, `tests/test_phosphor_subset.py` keeps the
subset current. Needs fonttools and brotli (`pip install fonttools brotli`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "frontend" / "vendor" / "phosphor"
#: Where an icon name can be written: the app's files and the server's (file
#: type and space icons are stored by name and sent down as `ph:name`).
SCAN = ((ROOT / "frontend", ("vendor",)), (ROOT / "src" / "tessellate", ()))
SUFFIXES = {".js", ".html", ".css", ".py"}
NAME = re.compile(r"""(?<![A-Za-z0-9_-])ph[:-]([a-z][a-z0-9]*(?:-[a-z0-9]+)*)""")
#: A bare quoted icon name (`icon: "file-pdf"`, a name table): the helper adds the `ph-` itself.
QUOTED = re.compile(r"""["'`]([a-z][a-z0-9]*(?:-[a-z0-9]+)*)["'`]""")


def codepoints() -> dict[str, int]:
    css = (DIR / "style.css").read_text(encoding="utf-8")
    return {
        name: int(code, 16)
        for name, code in re.findall(r'\.ph\.ph-([a-z0-9-]+):before\s*\{\s*content:\s*"\\([0-9a-f]+)"', css)
    }


def used_names(available: set[str]) -> set[str]:
    found: set[str] = set()
    for base, skip in SCAN:
        for path in base.rglob("*"):
            if path.suffix not in SUFFIXES or any(part in skip for part in path.relative_to(base).parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            found.update(NAME.findall(text))
            found.update(n for n in QUOTED.findall(text) if n in available)
    return found & available


def main() -> int:
    from fontTools import subset

    points = codepoints()
    names = used_names(set(points))
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = []
    options.glyph_names = False
    options.notdef_outline = False
    font = subset.load_font(str(DIR / "Phosphor-full.woff2"), options)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=sorted(points[n] for n in names))
    subsetter.subset(font)
    subset.save_font(font, str(DIR / "Phosphor.woff2"), options)
    print(
        f"{len(names)} icon names, {(DIR / 'Phosphor.woff2').stat().st_size:,} bytes "
        f"(full {(DIR / 'Phosphor-full.woff2').stat().st_size:,})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
