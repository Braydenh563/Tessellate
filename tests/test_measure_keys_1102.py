"""OPEN 1662: the key-check count in `scratchpad/ui-sweeps/measure-static.py`
(`keys`) counts a check written as `key.toLowerCase() === "x"` and each
`case "x":` of a `switch (e.key)`, not only `e.key === "x"`."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location("measure_static", ROOT / "scratchpad" / "ui-sweeps" / "measure-static.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_way_of_checking_a_key_is_counted():
    text = '''
    if (e.key === "Escape") close();
    if (event.key.toLowerCase() === "k") open();
    if ((ev.key || "").toLowerCase() == 'j') next();
    const k = e.key.toLowerCase();
    if (k === "m") mute();
    switch (e.key) {
      case "ArrowUp": up(); break;
      case "ArrowDown":
      case "x": down(); break;
      default: break;
    }
    switch (event.key.toLowerCase()) {
      case "z": undo(); break;
    }
    if (name === "q") ignored();
    '''
    assert sorted(_module().key_checks(text)) == sorted(["Escape", "k", "j", "m", "ArrowUp", "ArrowDown", "x", "z"])
