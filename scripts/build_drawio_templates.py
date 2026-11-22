"""draw.io's templates as a board library set (WHITEBOARD_PLAN section 8).

    python scripts/build_drawio_templates.py <templates dir> [--count 40] [--out frontend/board-library/drawio-templates.json]

`<templates dir>` is `src/main/webapp/templates` of jgraph/drawio (CC BY 4.0, its `LICENSE`): folders of
`mxfile` XML, each page an `mxGraphModel` plain or deflated. Every page goes through the app's own cell
reader and planner (`wbDrawioPlan` in frontend/js/whiteboard-interchange.js, run in node) and
`wbDrawioStyle.more.payload`, so the library holds what an import of the file would put on a board.
The pick is deterministic: one from each folder in turn, in name order, skipping what has a picture, no
connector, fewer than three shapes, or more than the library holds.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend" / "js" / "whiteboard-interchange.js"
NOTE = "Template by JGraph, CC BY 4.0"
MAX_BYTES = 200_000


def model_of(path: Path) -> ET.Element | None:
    """The first page's `mxGraphModel` of a template file."""
    root = ET.parse(path).getroot()
    if root.tag == "mxGraphModel":
        return root
    diagram = root.find("diagram")
    if diagram is None:
        return None
    inner = diagram.find("mxGraphModel")
    if inner is not None:
        return inner
    packed = (diagram.text or "").strip()
    if not packed:
        return None
    raw = zlib.decompress(base64.b64decode(packed), -15).decode("utf-8")
    return ET.fromstring(urllib.parse.unquote(raw))


def cells_of(model: ET.Element) -> list[dict]:
    """The cells as the reader makes them (`wbDrawioModelCells`)."""
    cells = []
    for el in model.iter("mxCell"):
        wrap = None
        for up in model.iter():
            if up.tag in ("UserObject", "object") and el in list(up):
                wrap = up
        geo = el.find("mxGeometry")

        def point(name: str):
            if geo is None:
                return None
            for p in geo.findall("mxPoint"):
                if p.get("as") == name:
                    return {"x": float(p.get("x") or 0), "y": float(p.get("y") or 0)}
            return None

        points = []
        if geo is not None:
            for arr in geo.iter("Array"):
                if arr.get("as") == "points":
                    points += [{"x": float(q.get("x") or 0), "y": float(q.get("y") or 0)} for q in arr]
        cells.append({
            "id": (wrap if wrap is not None else el).get("id"), "parent": el.get("parent"),
            "vertex": el.get("vertex") == "1", "edge": el.get("edge") == "1",
            "source": el.get("source"), "target": el.get("target"), "style": el.get("style") or "",
            "value": (wrap.get("label") or "") if wrap is not None else el.get("value") or "",
            "geo": {k: geo.get(k) for k in ("x", "y", "width", "height")} | {"relative": geo.get("relative") == "1"} if geo is not None else {},
            "sourcePoint": point("sourcePoint"), "targetPoint": point("targetPoint"), "points": points,
        })
    return cells


def convert(cell_lists: list[list[dict]]) -> list[dict | None]:
    """Each cell list through the app's planner: `{plan, made}` or None, from one node run."""
    node = shutil.which("node")
    if not node:
        raise SystemExit("node is needed: the converter runs the app's own reader")
    source = SOURCE.read_text(encoding="utf-8")
    pure = source[: source.index("//: The rows inside an SVG")]
    script = (pure + "\nconst all = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
              "console.log(JSON.stringify(all.map((cells) => { const plan = wbDrawioPlan(cells);"
              " return { plan: { items: plan.items.length, links: plan.links.length, dropped: plan.dropped }, made: wbDrawioStyle.more.payload(plan) }; })));")
    out = subprocess.run([node, "-e", script], input=json.dumps(cell_lists), capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def words(stem: str) -> str:
    text = re.sub(r"[_-]+", " ", stem).strip()
    return text[:1].upper() + text[1:]


def build(src: Path, count: int) -> dict:
    files: dict[str, list[Path]] = {}
    for path in sorted(src.glob("*/*.xml")):
        files.setdefault(path.parent.name, []).append(path)
    candidates = []
    for folder, paths in files.items():
        for path in paths:
            try:
                model = model_of(path)
                cells = cells_of(model) if model is not None else []
            except (ET.ParseError, ValueError, zlib.error):
                continue
            candidates.append((folder, path, cells))
    results = convert([c[2] for c in candidates])
    ok: dict[str, list] = {}
    for (folder, path, cells), res in zip(candidates, results, strict=True):
        made = res["made"]
        if not made or made["skipped"] or res["plan"]["items"] < 3 or not res["plan"]["links"]:
            continue
        if len(json.dumps(made["payload"])) > MAX_BYTES or len(made["payload"]["items"]) > 120:
            continue
        ok.setdefault(folder, []).append((folder, path, cells, res))
    picked, turn = [], 0
    folders = sorted(ok)
    while len(picked) < count and any(ok.values()):
        folder = folders[turn % len(folders)]
        turn += 1
        if ok[folder]:
            picked.append(ok[folder].pop(0))
    items = []
    seen = set()
    for folder, path, cells, res in picked:
        key = f"{folder}-{path.stem}".replace("_", "-").lower()
        if key in seen:
            continue
        seen.add(key)
        name = words(path.stem)
        items.append({
            "key": key, "kind": "element", "name": name, "hint": f"{words(folder)} template from draw.io",
            "tags": ["template", "draw.io", folder, *[w for w in re.split(r"[_ -]+", path.stem) if len(w) > 2][:4]],
            "template": "board", "note": NOTE, "payload": res["made"]["payload"],
        })
    return {
        "format": "memorymap-library-set", "version": 1, "key": "drawio-templates", "name": "Templates from draw.io",
        "source": {"project": "jgraph/drawio", "library": "src/main/webapp/templates", "licence": "CC-BY-4.0", "note": NOTE},
        "items": items,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--out", type=Path, default=ROOT / "frontend" / "board-library" / "drawio-templates.json")
    args = ap.parse_args()
    data = build(args.src, args.count)
    args.out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {len(data['items'])} templates to {args.out}")


if __name__ == "__main__":
    main()
