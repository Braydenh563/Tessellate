"""Source text: a declaration repeated later in boot CSS under the same
selector, at-rule nesting and value is dead weight: the later copy always
wins, so the earlier one costs gzip bytes against the boot budget and
nothing else. Fourteen were removed together (110 bytes)."""

import re

from tests._app_js import FRONTEND_DIR

CSS = FRONTEND_DIR / "css"


def _boot_files():
    html = (FRONTEND_DIR / "index.html").read_text()
    return [CSS / name for name in re.findall(r'href="/css/([^"?]+\.css)', html)]


def _dead_duplicates():
    last, dead = {}, []
    for path in _boot_files():
        text = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), path.read_text(), flags=re.S)
        ctx = []
        for m in re.finditer(r"([^{};]*)\{|\}|([^{};]*);", text):
            if m.group(0) == "}":
                if ctx:
                    ctx.pop()
                continue
            if m.group(1) is not None:
                ctx.append(" ".join(m.group(1).split()))
                continue
            decl = m.group(2).strip()
            if ":" not in decl or not ctx or ctx[-1].startswith("@"):
                continue
            prop, value = decl.split(":", 1)
            key = (tuple(ctx), prop.strip())
            where = f"{path.name}:{text.count(chr(10), 0, m.start()) + 1}"
            if key in last and last[key][0] == " ".join(value.split()):
                dead.append(f"{last[key][1]} {decl} (again at {where})")
            last[key] = (" ".join(value.split()), where)
    return dead


def test_no_dead_duplicate_declarations_in_boot_css():
    """Source text: the later copy always wins, so the earlier one is dead."""
    assert _dead_duplicates() == []
