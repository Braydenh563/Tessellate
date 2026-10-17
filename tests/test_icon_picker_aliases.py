"""Emoji search finds an emoji by the names people use (INBOX 904 B82).

The picker read only the Unicode name, so "pray" and "high five" found nothing
for the folded hands (🙏). `iconPickerHay` is the text a search reads for one
tile: its name, its group and its everyday aliases. Run in node, like the
other pure-function tests of vendored-free front-end code.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "icon-picker.js").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _hay(name: str, group: str = "People") -> str:
    aliases = re.search(r"^const ICON_EMOJI_ALIASES = \{.*?^\};", JS, re.S | re.M)
    fn = re.search(r"^function iconPickerHay\(.*?^\}", JS, re.S | re.M)
    assert aliases and fn, "the alias table and iconPickerHay must exist"
    script = f"{aliases.group(0)}\n{fn.group(0)}\nconsole.log(JSON.stringify(iconPickerHay({{name: {json.dumps(name)}}}, {json.dumps(group)})));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def test_the_folded_hands_are_found_by_everyday_words() -> None:
    hay = _hay("person with folded hands")
    for word in ("pray", "high five", "please", "thanks", "namaste"):
        assert word in hay, word


def test_the_name_and_group_are_still_searched() -> None:
    hay = _hay("grinning face", "Smileys")
    assert "grinning face" in hay and "smileys" in hay


def test_every_alias_names_an_emoji_in_the_picker() -> None:
    names = {m.replace("_", " ") for m in re.findall(r"([a-z_]+)=\\u\{", JS)}
    table = re.search(r"^const ICON_EMOJI_ALIASES = \{(.*?)^\};", JS, re.S | re.M).group(1)
    keys = re.findall(r'^\s*"([a-z ]+)":', table, re.M)
    assert keys and not [k for k in keys if k not in names], [k for k in keys if k not in names]
