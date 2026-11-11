"""Run the companion catalogue block of avatars.js (between its markers) under node with stubs (atlascat-1108 A2 to A5)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AVATARS = ROOT / "frontend" / "js" / "avatars.js"
CATALOGUE = ROOT / "frontend" / "companion-catalogue.json"


def block() -> str:
    text = AVATARS.read_text(encoding="utf-8")
    a, b = text.index("//: catalogue-begin"), text.index("//: catalogue-end")
    return text[a:b]


def run(body: str, acts: dict | None = None, answer: str = "ok") -> object:
    """`body` is async JS ending in `console.log(JSON.stringify(x))`; `nmb`, `NAME_MARK_BUDDY_ACTS` and a stub `api` exist.
    `answer`: ok (the real file), http (a 404), bad (not JSON), down (the fetch rejects)."""
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    doc = CATALOGUE.read_text(encoding="utf-8")
    script = f"""
const nmb = {{}};
const NAME_MARK_BUDDY_ACTS = {json.dumps(acts or {})};
const calls = [];
const api = (path, opts) => {{
  calls.push([path, opts]);
  const mode = {json.dumps(answer)};
  if (mode === "down") return Promise.reject(new Error("offline"));
  if (mode === "http") return Promise.resolve({{ ok: false, status: 404 }});
  if (mode === "bad") return Promise.resolve({{ ok: true, json: () => Promise.reject(new Error("bad json")) }});
  return Promise.resolve({{ ok: true, json: () => Promise.resolve({doc}) }});
}};
{block()}
(async () => {{ {body} }})();
"""
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])
