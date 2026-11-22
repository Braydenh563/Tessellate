"""Resolve a merge's CHANGELOG conflicts by keeping both sides (ours first),
Every agent merge conflicts here, since every commit adds a line at the same place."""

import re

pattern = re.compile(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", re.S)
with open("CHANGELOG.md") as fh:
    text = fh.read()
text = pattern.sub(lambda m: m.group(1) + m.group(2), text)
assert "<<<<<<<" not in text and ">>>>>>>" not in text
with open("CHANGELOG.md", "w") as fh:
    fh.write(text)
print("changelog: both sides kept")
