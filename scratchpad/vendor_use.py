"""Vendored libraries: what each ships against what the app calls (Brief 75).

The owner, 2026-10-10: "make sure all the vendored repositories are made full
use of. I want maximum utility." For every library in docs/THIRD_PARTY.md this
counts the exports or capabilities the vendored copy offers and those the
app's own code reaches, and prints "available N, called M, unused: ...".

Run: python scratchpad/vendor_use.py [--full] [--groups] [--json]
`tests/test_vendor_utilisation.py` imports `collect()` and ratchets each
library's called count, so a library is never quietly used less. Needs node
for the three browser bundles whose exports can only be read by running them
(CodeMirror, D3, Emmet). p5's public API was dumped once in Chromium
(`new Set(Object.getOwnPropertyNames(p5.prototype))`, functions not starting
with an underscore) because p5 will not initialise outside a page; it is
pinned to the vendored 1.9.4, so it changes only with the file.

"Called" is a lower bound: a name built at run time (`"ph-" + name`) is not
seen. The unused lists are therefore leads to check, not verdicts.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
VENDOR = FRONTEND / "vendor"
SRC = ROOT / "src" / "tessellate"
THIRD_PARTY = ROOT / "docs" / "THIRD_PARTY.md"

#: THIRD_PARTY.md's "Library" cell -> the key `collect()` reports it under.
LIBRARY_KEYS = {
    "FlashText": "flashtext",
    "CodeMirror 6": "codemirror",
    "Emmet": "emmet",
    "js-beautify": "jsbeautify",
    "sucrase": "sucrase",
    "JS-Interpreter": "jsinterpreter",
    "sql.js": "sqljs",
    "Harper": "harper",
    "D3": "d3",
    "p5.js": "p5",
    "Phosphor Icons": "phosphor",
    "English word list": "wordlist",
    "Python standard library table": "pystdlib",
    "Atkinson Hyperlegible": "atkinson",
    "Mammoth": "mammoth",
    "Mermaid": "mermaid",
    "MathLive": "mathlive",
    "docx": "docx",
    "draw.io stencils": "stencils",
    #: A download extra (Settings, Packages), not vendored JS: the engine, its
    #: model and the parts compiled into its WASM are one capability, counted once.
    "Bergamot translator": "translate",
    "Firefox Translations model, English to Spanish": "translate",
    "marian-nmt (inside the Bergamot WASM)": "translate",
    "intgemm (inside the Bergamot WASM)": "translate",
    "SentencePiece (inside the Bergamot WASM)": "translate",
    "ruy (inside the Bergamot WASM)": "translate",
    "ssplit-cpp (inside the Bergamot WASM)": "translate",
}

P5_FUNCTIONS = [
    "abs",
    "acos",
    "alpha",
    "ambientLight",
    "ambientMaterial",
    "angleMode",
    "append",
    "applyMatrix",
    "arc",
    "arrayCopy",
    "asin",
    "atan",
    "atan2",
    "background",
    "beginClip",
    "beginContour",
    "beginGeometry",
    "beginShape",
    "bezier",
    "bezierDetail",
    "bezierPoint",
    "bezierTangent",
    "bezierVertex",
    "blend",
    "blendMode",
    "blue",
    "boolean",
    "box",
    "brightness",
    "buildGeometry",
    "byte",
    "camera",
    "ceil",
    "char",
    "circle",
    "clear",
    "clearDepth",
    "clearStorage",
    "clip",
    "color",
    "colorMode",
    "concat",
    "cone",
    "constrain",
    "copy",
    "cos",
    "createA",
    "createAudio",
    "createButton",
    "createCamera",
    "createCanvas",
    "createCapture",
    "createCheckbox",
    "createColorPicker",
    "createDiv",
    "createElement",
    "createFileInput",
    "createFilterShader",
    "createFramebuffer",
    "createGraphics",
    "createImage",
    "createImg",
    "createInput",
    "createNumberDict",
    "createP",
    "createRadio",
    "createSelect",
    "createShader",
    "createSlider",
    "createSpan",
    "createStringDict",
    "createVector",
    "createVideo",
    "createWriter",
    "cursor",
    "curve",
    "curveDetail",
    "curvePoint",
    "curveTangent",
    "curveTightness",
    "curveVertex",
    "cylinder",
    "day",
    "debugMode",
    "degrees",
    "describe",
    "describeElement",
    "directionalLight",
    "displayDensity",
    "dist",
    "downloadFile",
    "ellipse",
    "ellipseMode",
    "ellipsoid",
    "emissiveMaterial",
    "encodeAndDownloadGif",
    "endClip",
    "endContour",
    "endGeometry",
    "endShape",
    "erase",
    "exitPointerLock",
    "exp",
    "fill",
    "filter",
    "float",
    "floor",
    "fract",
    "frameRate",
    "freeGeometry",
    "frustum",
    "fullscreen",
    "get",
    "getFilterGraphicsLayer",
    "getFrameRate",
    "getItem",
    "getTargetFrameRate",
    "getURL",
    "getURLParams",
    "getURLPath",
    "green",
    "gridOutput",
    "hex",
    "hour",
    "httpDo",
    "httpGet",
    "httpPost",
    "hue",
    "image",
    "imageLight",
    "imageMode",
    "int",
    "isLooping",
    "join",
    "keyIsDown",
    "lerp",
    "lerpColor",
    "lightFalloff",
    "lightness",
    "lights",
    "line",
    "linePerspective",
    "loadBytes",
    "loadFont",
    "loadImage",
    "loadJSON",
    "loadModel",
    "loadPixels",
    "loadShader",
    "loadStrings",
    "loadTable",
    "loadXML",
    "log",
    "loop",
    "mag",
    "map",
    "match",
    "matchAll",
    "max",
    "metalness",
    "millis",
    "min",
    "minute",
    "model",
    "month",
    "nf",
    "nfc",
    "nfp",
    "nfs",
    "noCanvas",
    "noCursor",
    "noDebugMode",
    "noErase",
    "noFill",
    "noLights",
    "noLoop",
    "noSmooth",
    "noStroke",
    "noTint",
    "noise",
    "noiseDetail",
    "noiseSeed",
    "norm",
    "normal",
    "normalMaterial",
    "orbitControl",
    "ortho",
    "panorama",
    "perspective",
    "pixelDensity",
    "plane",
    "point",
    "pointLight",
    "pop",
    "popMatrix",
    "popStyle",
    "pow",
    "print",
    "push",
    "pushMatrix",
    "pushStyle",
    "quad",
    "quadraticVertex",
    "radians",
    "random",
    "randomGaussian",
    "randomSeed",
    "rect",
    "rectMode",
    "red",
    "redraw",
    "registerMethod",
    "registerPreloadMethod",
    "registerPromisePreload",
    "removeElements",
    "removeItem",
    "requestPointerLock",
    "resetMatrix",
    "resetShader",
    "resizeCanvas",
    "reverse",
    "rotate",
    "rotateX",
    "rotateY",
    "rotateZ",
    "round",
    "saturation",
    "save",
    "saveCanvas",
    "saveFrames",
    "saveGif",
    "saveJSON",
    "saveJSONArray",
    "saveJSONObject",
    "saveStrings",
    "saveTable",
    "scale",
    "second",
    "select",
    "selectAll",
    "set",
    "setAttributes",
    "setCamera",
    "setFrameRate",
    "setMoveThreshold",
    "setShakeThreshold",
    "shader",
    "shearX",
    "shearY",
    "shininess",
    "shorten",
    "shuffle",
    "sin",
    "smooth",
    "sort",
    "specularColor",
    "specularMaterial",
    "sphere",
    "splice",
    "split",
    "splitTokens",
    "spotLight",
    "sq",
    "sqrt",
    "square",
    "storeItem",
    "str",
    "stroke",
    "strokeCap",
    "strokeJoin",
    "strokeWeight",
    "subset",
    "tan",
    "text",
    "textAlign",
    "textAscent",
    "textDescent",
    "textFont",
    "textLeading",
    "textOutput",
    "textSize",
    "textStyle",
    "textWidth",
    "textWrap",
    "texture",
    "textureMode",
    "textureWrap",
    "tint",
    "torus",
    "translate",
    "triangle",
    "trim",
    "unchar",
    "unhex",
    "unregisterMethod",
    "updatePixels",
    "vertex",
    "writeFile",
    "year",
]
P5_CLASSES = [
    "Camera",
    "Color",
    "ColorConversion",
    "DataArray",
    "Element",
    "File",
    "Font",
    "Framebuffer",
    "FramebufferCamera",
    "FramebufferTexture",
    "Geometry",
    "Graphics",
    "Image",
    "Matrix",
    "MediaElement",
    "NumberDict",
    "PrintWriter",
    "RenderBuffer",
    "Renderer",
    "Renderer2D",
    "RendererGL",
    "Shader",
    "StringDict",
    "Table",
    "TableRow",
    "Texture",
    "TypedDict",
    "VERSION",
    "Vector",
    "XML",
]

#: Upstream packages the bundle does not carry, named so the ranking can cost
#: them. Not counted as available: they are not in the repository.
NOT_VENDORED = (
    "@codemirror/merge",
    "@codemirror/lang-sql",
    "@codemirror/lang-xml",
    "@codemirror/lang-cpp",
    "@codemirror/lang-rust",
    "@codemirror/lang-go",
    "@codemirror/lang-java",
    "@codemirror/lang-php",
    "@codemirror/lang-sass",
    "@codemirror/lang-less",
    "@codemirror/lang-vue",
    "@replit/codemirror-indentation-markers",
    "@codemirror/collab",
)

#: Phosphor ships one weight in the vendored web font.
PHOSPHOR_WEIGHTS = ("thin", "light", "regular", "bold", "fill", "duotone")

_NODE_EXPORTS = r"""
const vm = require("vm"), fs = require("fs");
const [file, name, depth] = process.argv.slice(1);
const w = {};
w.window = w; w.self = w;
w.document = { createElement() { return { style: {} }; }, documentElement: { style: {} }, head: {} };
w.navigator = { userAgent: "", platform: "" };
vm.createContext(w);
vm.runInContext(fs.readFileSync(file, "utf8"), w);
const root = w[name];
const out = {};
for (const key of Object.keys(root)) {
  const v = root[key];
  out[key] = depth === "2" && v && (typeof v === "object" || typeof v === "function") ? Object.keys(v) : null;
}
process.stdout.write(JSON.stringify(out));
"""


@dataclass
class Report:
    key: str
    title: str
    available: list[str]
    called: list[str]
    #: group name -> every available name in it, for the ranking
    groups: dict[str, list[str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def unused(self) -> list[str]:
        used = set(self.called)
        return [name for name in self.available if name not in used]


# ---- reading the app ---------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def frontend_scripts() -> dict[str, str]:
    """frontend/js/*.js and sw.js: everything the browser runs of ours."""
    out = {p.name: _read(p) for p in sorted((FRONTEND / "js").glob("*.js"))}
    out["sw.js"] = _read(FRONTEND / "sw.js")
    return out


def python_sources() -> dict[str, str]:
    """src/tessellate/**/*.py without the vendored copies."""
    out = {}
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel.startswith("vendor/"):
            continue
        out[rel] = _read(path)
    return out


def icon_corpus() -> str:
    """Every file that can name an icon class: scripts, the page, styles, Python."""
    parts = list(frontend_scripts().values())
    parts.append(_read(FRONTEND / "index.html"))
    parts += [_read(p) for p in sorted((FRONTEND / "css").glob("*.css"))]
    parts += list(python_sources().values())
    return "\n".join(parts)


def _live_lines(text: str) -> str:
    """The text without whole-line comments, so a comment cannot count as a call."""
    keep = []
    for line in text.splitlines():
        head = line.lstrip()
        if head.startswith(("#", "//", "*", "/*")):
            continue
        keep.append(line)
    return "\n".join(keep)


def run_node_exports(bundle: Path, global_name: str, depth: int = 1) -> dict[str, list[str] | None]:
    """The bundle's global's own keys; depth 2 adds each module's keys."""
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("node is needed to read the browser bundles' exports")
    done = subprocess.run(
        [node, "-e", _NODE_EXPORTS, str(bundle), global_name, str(depth)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(done.stdout)


# ---- following a bundle's global through aliases and destructuring -----------

_ALIAS = re.compile(r"\b(?:const|let|var)\s+(\w+)\s*=\s*(\w+)((?:\.\w+)*)\s*[;,)\n]")
_DESTRUCTURE = re.compile(r"\{([^{}]*)\}\s*=\s*(\w+)((?:\.\w+)*)\s*[;,)\n]")


def qualified_uses(text: str, roots: tuple[str, ...]) -> set[str]:
    """Dotted paths reached from `roots` in one file, e.g. "view.EditorView".

    Follows `const ac = CM.autocomplete`, `const { Decoration } = CM.view` and
    `window.CM6`. Per file, because an alias such as `E` means one thing in
    the file that assigns it.
    """
    for root in roots:
        text = text.replace(f"window.{root}", root)
    alias: dict[str, str] = {root: "" for root in roots}
    for _ in range(3):
        for match in _ALIAS.finditer(text):
            name, base, chain = match.groups()
            if base in alias and name not in alias:
                alias[name] = (alias[base] + chain).lstrip(".")
    paths: set[str] = set()
    for name, prefix in alias.items():
        for match in re.finditer(rf"(?<!\w)(?<!\w\.){re.escape(name)}((?:\.\w+)+)", text):
            paths.add((prefix + match.group(1)).lstrip("."))
    for match in _DESTRUCTURE.finditer(text):
        body, base, chain = match.groups()
        if base not in alias:
            continue
        prefix = (alias[base] + chain).lstrip(".")
        for part in body.split(","):
            item = part.strip()
            if not item or item.startswith("..."):
                continue
            item = re.split(r"[:=]", item)[0].strip()
            if re.fullmatch(r"\w+", item):
                paths.add(f"{prefix}.{item}" if prefix else item)
    return paths


def _called(known: list[str], paths: set[str]) -> list[str]:
    return [name for name in known if name in paths or any(p.startswith(name + ".") for p in paths)]


# ---- the libraries -------------------------------------------------------------


def codemirror_report(scripts: dict[str, str]) -> Report:
    entry = _read(VENDOR / "codemirror" / "entry.js")
    modules = re.findall(r"export \* as (\w+) from", entry)
    direct = []
    for block in re.findall(r"export \{([^}]*)\} from", entry):
        direct += [n.strip() for n in block.split(",") if n.strip()]
    exports = run_node_exports(VENDOR / "codemirror" / "codemirror.min.js", "CM6", depth=2)
    groups: dict[str, list[str]] = {}
    for module in modules:
        groups[module] = [f"{module}.{n}" for n in exports.get(module) or []]
    groups["legacy modes"] = [n for n in direct if n in exports]
    available = [name for names in groups.values() for name in names]
    paths: set[str] = set()
    for text in scripts.values():
        paths |= qualified_uses(text, ("CM6", "CMx", "CM"))
    called = _called(available, paths)
    pkg = json.loads(_read(VENDOR / "codemirror" / "package.json"))["dependencies"]
    bundled = set(re.findall(r'from "([^"]+)"', entry))
    unbundled = sorted(n for n in pkg if not any(b == n or b.startswith(n + "/") for b in bundled))
    notes = [
        f"{len(pkg)} packages pinned in package.json; not bundled: {', '.join(unbundled) or 'none'}",
        "not vendored at all: " + ", ".join(NOT_VENDORED),
    ]
    return Report("codemirror", "CodeMirror 6", available, called, groups, notes)


def emmet_report(scripts: dict[str, str]) -> Report:
    exports = run_node_exports(VENDOR / "emmet" / "emmet.min.js", "EMMET")
    available = sorted(exports)
    paths: set[str] = set()
    for text in scripts.values():
        paths |= qualified_uses(text, ("EMMET",))
    # Syntaxes Emmet can expand; the app passes four (DOC_EMMET_SYNTAX).
    syntaxes = ["html", "css", "xml", "jsx", "scss", "sass", "stylus", "pug", "haml", "slim"]
    mapped = set(
        re.findall(
            r'\b(\w+):\s*"(\w+)"',
            _read(FRONTEND / "js" / "documents-code.js")
            .split("DOC_EMMET_SYNTAX = ", 1)[-1]
            .split("}", 1)[0],
        )
    )
    passed = {value for _key, value in mapped}
    available += [f"syntax:{s}" for s in syntaxes]
    called = _called(available, paths) + [f"syntax:{s}" for s in syntaxes if s in passed]
    return Report(
        "emmet",
        "Emmet",
        available,
        called,
        {"functions": sorted(exports), "syntaxes": [f"syntax:{s}" for s in syntaxes]},
    )


def sucrase_report(scripts: dict[str, str]) -> Report:
    """The TypeScript pass (run-core.js). The bundle's global is reached
    through `runVendorScript(url, "SUCRASE")`, so a call is counted where a
    file names the global and calls the export on what it returned."""
    exports = sorted(run_node_exports(VENDOR / "sucrase" / "sucrase.min.js", "SUCRASE"))
    transforms = ["typescript", "jsx", "imports", "flow", "react-hot-loader", "jest"]
    available = exports + [f"transform:{t}" for t in transforms]
    called: list[str] = []
    for text in scripts.values():
        if '"SUCRASE"' not in text:
            continue
        called += [name for name in exports if re.search(rf"\.{name}\(", text)]
        called += [f"transform:{t}" for t in transforms if f'"{t}"' in text]
    return Report("sucrase", "sucrase", available, sorted(set(called)), {"functions": exports})


#: sql.js's API (Database, Statement, StatementIterator), from its README.
SQLJS_METHODS = [
    "Database", "run", "exec", "each", "prepare", "iterateStatements", "export", "close",
    "getRowsModified", "create_function", "create_aggregate", "bind", "step", "get",
    "getColumnNames", "getAsObject", "getSQL", "getNormalizedSQL", "reset", "free",
    "next", "getRemainingSQL",
]


def sqljs_report() -> Report:
    """The SQL runner. It runs inside the sandbox page, so its calls are in
    `api/run_sandbox.py`'s worker text, not in a frontend script."""
    text = _live_lines(_read(SRC / "api" / "run_sandbox.py"))
    #: The runner's own names for a database, a statement and the iterator,
    #: so a regular expression's `.exec(` is not counted as SQL.
    called = [m for m in SQLJS_METHODS if re.search(rf"(?:new SQL\.|\b(?:db|stmt|ins|it)\.){m}\(", text)]
    return Report("sqljs", "sql.js", list(SQLJS_METHODS), called, {"methods": list(SQLJS_METHODS)})


#: JS-Interpreter's public API: the names its interpreter.js keeps from a
#: compiler's renaming (`Interpreter.prototype['...']`).
JSINTERP_METHODS = [
    "step", "run", "getStatus", "appendCode", "createObject", "createObjectProto",
    "createNativeFunction", "createAsyncFunction", "getProperty", "setProperty",
    "nativeToPseudo", "pseudoToNative", "getGlobalScope", "setGlobalScope",
    "getStateStack", "setStateStack",
]


def jsinterpreter_report() -> Report:
    """The JavaScript debugger (DOCUMENTS_PLAN 23, D3). It steps inside the
    sandbox page, so its calls are in `api/run_sandbox.py`'s worker text."""
    text = _live_lines(_read(SRC / "api" / "run_sandbox.py"))
    called = [m for m in JSINTERP_METHODS if re.search(rf"\b(?:interp|it|this)\.{m}\(", text)]
    return Report("jsinterpreter", "JS-Interpreter", list(JSINTERP_METHODS), called, {"methods": list(JSINTERP_METHODS)})


def jsbeautify_report(scripts: dict[str, str]) -> Report:
    exports = sorted(run_node_exports(VENDOR / "js-beautify" / "beautify.min.js", "JSBEAUTIFY"))
    paths: set[str] = set()
    for text in scripts.values():
        paths |= qualified_uses(text, ("JSBEAUTIFY",))
    # A selection of whole lines is formatted by the library at the indent level of
    # its first line (`indent_level`, documents-code.js `docBeautifyText`; ledger 1565).
    available = exports + ["selection"]
    called = _called(available, paths)
    if any("indent_level" in text for text in scripts.values()):
        called.append("selection")
    return Report("jsbeautify", "js-beautify", available, called, {"functions": exports})


def _class_methods(source: str, class_re: str) -> list[str]:
    """Public method and accessor names of the first class whose name matches."""
    names: list[str] = []
    for match in re.finditer(
        rf"^(?:let \w+\$?\d* = )?class ({class_re})\b[^\n]*\{{\n(.*?)\n\}}", source, re.M | re.S
    ):
        for line in match.group(2).splitlines():
            m = re.match(r"  (?:static |async |get |set )*(\w+)\(", line)
            if (
                m
                and not m.group(1).startswith("_")
                and m.group(1) not in ("constructor", "free", "new")
            ):
                names.append(m.group(1))
        if names and not class_re.startswith("(?:Super)"):
            break
    return names


def harper_report(scripts: dict[str, str]) -> Report:
    source = _read(VENDOR / "harper" / "BinaryModule-BmeyZWwZ.js")
    groups: dict[str, list[str]] = {}
    for label, pattern in (
        ("Linter", r"Linter\d*"),
        ("Lint", r"Lint\d*"),
        ("Suggestion", r"Suggestion\d*"),
        ("Span", r"Span\d*"),
        ("BinaryModule", r"(?:Super)?BinaryModule(?:Impl)?"),
    ):
        groups[label] = [f"{label}.{n}" for n in dict.fromkeys(_class_methods(source, pattern))]
    for enum in ("Dialect", "Language", "SuggestionKind"):
        block = re.search(rf"const {enum}\$1 = Object\.freeze\(\{{(.*?)\n\}}\)", source, re.S)
        members = re.findall(r"^  ([A-Za-z]\w*):", block.group(1), re.M) if block else []
        groups[enum] = [f"{enum}.{m}" for m in members]
    available = [name for names in groups.values() for name in names]
    worker = scripts["harper-worker.js"]
    called = []
    for name in available:
        owner, member = name.split(".")
        if owner in ("Dialect", "Language", "SuggestionKind"):
            if re.search(rf"\b{owner}\.{member}\b", worker):
                called.append(name)
        elif owner == "BinaryModule":
            if re.search(rf"slimBinary\.{member}\b", worker):
                called.append(name)
        elif re.search(rf"\.{member}\b", worker):
            # Lint and Span share names with plain objects the worker builds;
            # a member counts only when the worker calls it on a lint or span.
            called.append(name)
    return Report("harper", "Harper", available, called, groups)


def phosphor_report() -> Report:
    css = _read(VENDOR / "phosphor" / "style.css")
    glyphs = sorted(set(re.findall(r"\.ph\.ph-([a-z0-9-]+):before", css)))
    corpus = icon_corpus()
    used = set(re.findall(r"\bph-([a-z0-9]+(?:-[a-z0-9]+)*)", corpus))
    weights = [f"weight:{w}" for w in PHOSPHOR_WEIGHTS]
    shipped = (
        ["weight:regular"] if "font-weight: normal" in css and ".ph-bold" not in css else weights
    )
    available = glyphs + weights
    called = [g for g in glyphs if g in used] + shipped
    notes = [
        "the icon picker lists every glyph (icon-picker.js iconPickerPhosphorNames), so a glyph the code never names is still reachable by the owner",
        "called counts glyph names the code spells out; names built at run time are not seen",
    ]
    return Report(
        "phosphor",
        "Phosphor Icons",
        available,
        called,
        {"glyphs": glyphs, "weights": weights},
        notes,
    )


#: Public surfaces a spelling word list could serve: (label, files, pattern).
WORDLIST_CAPABILITIES = (
    ("spell check in the documents editor", ("frontend/js/documents.js",), r"wordlist/en\.txt"),
    (
        "ranked suggestions in the documents editor",
        ("frontend/js/documents.js",),
        r"docSpellGuesses",
    ),
    (
        "spell check in the notes editor",
        ("frontend/js/editor.js", "frontend/js/notes-list.js", "frontend/js/note-cards.js"),
        r"wordlist|docSpell",
    ),
    (
        "spell check in the chat composer",
        ("frontend/js/chat.js", "frontend/js/composer.js"),
        r"wordlist|docSpell",
    ),
    (
        "spell check in board and mind map text",
        ("frontend/js/whiteboard.js", "frontend/js/whiteboard-map.js"),
        r"wordlist|docSpell",
    ),
    (
        "spell check in timeline and sheets",
        ("frontend/js/timeline.js", "frontend/js/sheets-selects.js"),
        r"wordlist|docSpell",
    ),
    ("Guide fuzzy match (help_chat.py)", ("src/tessellate/ai/help_chat.py",), r"wordlist|en\.txt"),
    (
        "question noise real-word check (question_noise.py)",
        ("src/tessellate/ai/question_noise.py",),
        r"wordlist|en\.txt",
    ),
    (
        "search typo tolerance",
        ("src/tessellate/api/routes_search.py", "src/tessellate/core/search.py"),
        r"wordlist|en\.txt",
    ),
)


def wordlist_report() -> Report:
    words = [w for w in _read(VENDOR / "wordlist" / "en.txt").splitlines() if w.strip()]
    available, called = [], []
    for label, files, pattern in WORDLIST_CAPABILITIES:
        available.append(label)
        for rel in files:
            path = ROOT / rel
            if path.exists() and re.search(pattern, _live_lines(_read(path))):
                called.append(label)
                break
    return Report(
        "wordlist", "English word list", available, called, {}, [f"{len(words)} words in en.txt"]
    )


#: What the Python standard library table (`python-stdlib/stdlib.json`: each
#: name's kind, signature and doc line) can drive in a Python document, and
#: where each use would be read.
PYSTDLIB_CAPABILITIES = (
    ("completions after module.", ("frontend/js/documents-code.js",), r"autocomplete:.*docPyStdlibSource"),
    ("hover card", ("frontend/js/documents-code.js",), r"docPyHover"),
    ("signature help inside a call", ("frontend/js/documents-code.js",), r"docPySignature"),
)


def _capability_report(key: str, title: str, capabilities: tuple, notes: list[str]) -> Report:
    available, called = [], []
    for label, files, pattern in capabilities:
        available.append(label)
        if any((ROOT / rel).exists() and re.search(pattern, _live_lines(_read(ROOT / rel))) for rel in files):
            called.append(label)
    return Report(key, title, available, called, {}, notes)


def pystdlib_report() -> Report:
    modules = json.loads(_read(VENDOR / "python-stdlib" / "stdlib.json")).get("modules", {})
    return _capability_report(
        "pystdlib", "Python standard library table", PYSTDLIB_CAPABILITIES, [f"{len(modules)} modules in stdlib.json"]
    )


def atkinson_report() -> Report:
    """Each face shipped under `atkinson/` is available; one an @font-face names is called."""
    css = "\n".join(_read(path) for path in sorted((ROOT / "frontend" / "css").glob("*.css")))
    faces = sorted(path.name for path in (VENDOR / "atkinson").glob("*.woff2"))
    called = [face for face in faces if f"vendor/atkinson/{face}" in css]
    return Report("atkinson", "Atkinson Hyperlegible", faces, called, {})


#: Mammoth's public surface (mammoth.browser), and the docx classes a writer
#: reaches for; both are read in documents-word.js (Brief 42, INBOX 736).
MAMMOTH_API = ["convertToHtml", "convertToMarkdown", "extractRawText", "embedStyleMap", "images"]
DOCX_API = [
    "Document", "Packer", "Paragraph", "TextRun", "HeadingLevel", "Table", "TableRow", "TableCell",
    "ExternalHyperlink", "InternalHyperlink", "ImageRun", "AlignmentType", "PageBreak", "Header", "Footer",
    "Bookmark", "LevelFormat", "TabStopType", "UnderlineType", "PageNumber", "FootnoteReferenceRun",
    "WidthType", "BorderStyle", "ShadingType", "SectionType",
]


def mammoth_report(scripts: dict[str, str]) -> Report:
    text = scripts.get("documents-word.js", "")
    called = [name for name in MAMMOTH_API if re.search(rf"\bmammoth\.{name}\b", text)]
    return Report("mammoth", "Mammoth", list(MAMMOTH_API), called, {}, ["read in documents-word.js, a .docx brought into the Library"])


#: Mermaid's public API (mermaid.esm default export), read in mermaid-frame.js.
MERMAID_API = [
    "initialize", "render", "parse", "run", "init", "detectType", "registerExternalDiagrams",
    "registerLayoutLoaders", "registerIconPacks", "setParseErrorHandler", "contentLoaded",
    "getRegisteredDiagramsMetadata", "mermaidAPI",
]


def mermaid_report(scripts: dict[str, str]) -> Report:
    text = scripts.get("mermaid-frame.js", "")
    called = [name for name in MERMAID_API if re.search(rf"\bmermaid\.{name}\b", text)]
    return Report("mermaid", "Mermaid", list(MERMAID_API), called, {}, ["read in mermaid-frame.js, the diagram frame"])


#: MathLive's public surface the equation field (math-field.js) can reach, each with
#: where the app calls it. The unused rows are the ranked leftovers: reading an
#: equation aloud, MathML out, and typeset-in-place for a whole element.
MATHLIVE_CAPABILITIES = (
    ("MathfieldElement, the editable field", ("frontend/js/math-field.js",), r"new MathfieldElement\("),
    ("fontsDirectory", ("frontend/js/math-field.js",), r"MathfieldElement\.fontsDirectory"),
    ("soundsDirectory", ("frontend/js/math-field.js",), r"MathfieldElement\.soundsDirectory"),
    ("keypressVibration", ("frontend/js/math-field.js",), r"MathfieldElement\.keypressVibration"),
    ("getValue (LaTeX out)", ("frontend/js/math-field.js",), r"\.getValue\("),
    ("setValue (LaTeX in)", ("frontend/js/math-field.js",), r"\.setValue\("),
    ("insert at the caret", ("frontend/js/math-field.js",), r"\.insert\("),
    ("executeCommand", ("frontend/js/math-field.js",), r"\.executeCommand\("),
    ("mathVirtualKeyboardPolicy", ("frontend/js/math-field.js",), r"mathVirtualKeyboardPolicy"),
    ("menuItems", ("frontend/js/math-field.js",), r"\.menuItems"),
    ("convertLatexToMathMl", ("frontend/js/math-field.js",), r"convertLatexToMathMl"),
    ("convertLatexToSpeakableText", ("frontend/js/math-field.js",), r"convertLatexToSpeakableText"),
    ("renderMathInElement", ("frontend/js/math-field.js",), r"renderMathInElement"),
    ("inlineShortcuts", ("frontend/js/math-field.js",), r"inlineShortcuts"),
)


def mathlive_report() -> Report:
    return _capability_report(
        "mathlive", "MathLive", MATHLIVE_CAPABILITIES, ["read in math-field.js, the equation field"]
    )


def docx_report(scripts: dict[str, str]) -> Report:
    text = scripts.get("documents-word.js", "")
    called = [name for name in DOCX_API if re.search(rf"\bD\.{name}\b", text)]
    return Report("docx", "docx", list(DOCX_API), called, {}, ["written in documents-word.js, Download as Word"])


#: Bergamot's embind surface as its bindings document it. The engine is a
#: download (`extras/translate/`), never in the repository, so this list is
#: the published API rather than a read of the file, and the counts are a floor.
BERGAMOT_API = [
    "BlockingService", "TranslationModel", "AlignedMemory", "AlignedMemoryList", "VectorString",
    "VectorResponseOptions", "translate", "translateViaPivoting", "getTranslatedText", "getOriginalText",
    "getSourceSentence", "getTargetSentence", "alignment", "html", "qualityScores",
]


def translate_report(scripts: dict[str, str]) -> Report:
    text = scripts.get("translate-worker.js", "")
    called = [name for name in BERGAMOT_API if re.search(rf"\b{name}\b", text)]
    return Report(
        "translate",
        "Bergamot translator (download extra)",
        list(BERGAMOT_API),
        called,
        {},
        ["a download extra, not vendored: marian-nmt, intgemm, SentencePiece, ruy and ssplit-cpp are inside its WASM"],
    )


def d3_module(name: str) -> str:
    """Which d3 module a top-level export belongs to (by name; d3 has no map)."""
    rules = (
        ("force", r"^force"),
        ("hierarchy", r"^(hierarchy|tree|cluster|treemap\w*|pack\w*|partition|stratify)$"),
        ("scale", r"^(scale\w*|tickFormat|ticks|tickIncrement|tickStep|nice)$"),
        ("scale-chromatic", r"^(scheme\w+|interpolate[A-Z]\w+)$"),
        (
            "shape",
            r"^(arc|area|line|pie|stack\w*|symbol\w*|link\w*|curve\w+|radial\w*|lineRadial|areaRadial|pointRadial|areaY|lineX|lineY)$",
        ),
        ("geo", r"^(geo\w+|path|\w*Projection)$"),
        (
            "selection",
            r"^(select\w*|selection|create|creator|matcher|namespace\w*|pointers?|style|window|local|sourceEvent)$",
        ),
        ("transition", r"^(transition|active|interrupt|ease\w*)$"),
        ("interaction", r"^(zoom\w*|drag\w*|brush\w*|event)$"),
        (
            "time",
            r"^(time\w*|utc\w*|unix|\w*Day|\w*Week|\w*Hour|\w*Minute|\w*Second|\w*Month|\w*Year|\w*Sunday|\w*Monday|\w*Tuesday|\w*Wednesday|\w*Thursday|\w*Friday|\w*Saturday|\w*Millisecond)$",
        ),
        ("format", r"^(format\w*|precision\w*|\w+Format\w*|\w*Parse|\w*Specifier)$"),
        ("axis", r"^axis\w+$"),
        ("delaunay", r"^(Delaunay|Voronoi)$"),
        ("contour", r"^(contour\w*|density2d)$"),
        ("polygon", r"^polygon\w+$"),
        ("quadtree", r"^quadtree$"),
        ("random", r"^random\w*$"),
        ("color", r"^(rgb|hsl|lab|hcl|lch|color|cubehelix|gray|cmyk|display)$"),
        ("interpolate", r"^(interpolate\w*|piecewise|quantize|zoomIdentity)$"),
        (
            "dsv-fetch",
            r"^(csv\w*|tsv\w*|dsv\w*|autoType|json|text|image|xml|html|svg|blob|buffer)$",
        ),
        ("chord", r"^(chord\w*|ribbon\w*)$"),
        ("timer", r"^(timer\w*|timeout|interval|now)$"),
        ("sankey-etc", r"^$"),
    )
    for group, pattern in rules:
        if re.search(pattern, name):
            return group
    return "array and statistics"


def d3_report(scripts: dict[str, str]) -> Report:
    exports = sorted(run_node_exports(VENDOR / "d3.v7.min.js", "d3"))
    used: set[str] = set()
    for text in scripts.values():
        used |= set(re.findall(r"\bd3\.(\w+)", text))
    groups: dict[str, list[str]] = {}
    for name in exports:
        groups.setdefault(d3_module(name), []).append(name)
    called = [n for n in exports if n in used]
    return Report("d3", "D3", exports, called, groups)


def p5_report(scripts: dict[str, str]) -> Report:
    used: set[str] = set()
    for text in scripts.values():
        if "new p5(" in text:
            used |= set(re.findall(r"(?<![\w.])p\.(\w+)", text))
            used |= {f"class:{n}" for n in re.findall(r"\bp5\.([A-Z]\w+)", text)}
    available = list(P5_FUNCTIONS) + [f"class:{n}" for n in P5_CLASSES]
    called = [n for n in available if n in used]
    return Report(
        "p5",
        "p5.js",
        available,
        called,
        {"functions": list(P5_FUNCTIONS), "classes": [f"class:{n}" for n in P5_CLASSES]},
    )


def flashtext_report(sources: dict[str, str]) -> Report:
    tree = ast.parse(_read(SRC / "vendor" / "flashtext.py"))
    methods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "KeywordProcessor":
            methods = [
                f.name
                for f in node.body
                if isinstance(f, ast.FunctionDef) and not f.name.startswith("_")
            ]
    options = [
        "extract_keywords(span_info)",
        "extract_keywords(max_cost)",
        "replace_keywords(max_cost)",
        "KeywordProcessor(case_sensitive=True)",
    ]
    available = methods + options
    live = "\n".join(_live_lines(text) for text in sources.values())
    called = [m for m in methods if re.search(rf"\.{m}\(", live)]
    if re.search(r"span_info\s*=\s*True", live):
        called.append("extract_keywords(span_info)")
    if re.search(r"max_cost\s*=\s*[1-9]", live):
        called += ["extract_keywords(max_cost)"]
    if re.search(r"case_sensitive\s*=\s*True", live):
        called.append("KeywordProcessor(case_sensitive=True)")
    return Report("flashtext", "FlashText", available, called, {})


def stencils_report(scripts: dict[str, str]) -> Report:
    """The draw.io stencil sets and board-library files (THIRD_PARTY.md's board-library table)."""
    library = FRONTEND / "board-library"
    index = json.loads(_read(library / "index.json"))
    served = {s["key"] for s in index["sets"]}
    available, called, groups = [], [], {}
    for s in index["sets"]:
        available.append(f"set:{s['key']}")
        called.append(f"set:{s['key']}")
    for path in sorted((library / "drawio").glob("*.json")):
        data = json.loads(_read(path))
        key = data["key"]
        names = [f"{key}:{item['key']}" for item in data["items"]]
        groups[key] = names
        available.append(f"set:{key}")
        text = "\n".join(scripts.values()) + "\n".join(
            _live_lines(t) for t in python_sources().values()
        )
        if key in served or re.search(rf"{re.escape(key)}|board-library/drawio", text):
            called.append(f"set:{key}")
    return Report("stencils", "draw.io stencils and board-library sets", available, called, groups)


def collect() -> dict[str, Report]:
    # Comments name things they do not call; only live lines count.
    scripts = {name: _live_lines(text) for name, text in frontend_scripts().items()}
    sources = python_sources()
    reports = [
        codemirror_report(scripts),
        emmet_report(scripts),
        jsbeautify_report(scripts),
        sucrase_report(scripts),
        sqljs_report(),
        jsinterpreter_report(),
        harper_report(scripts),
        phosphor_report(),
        wordlist_report(),
        pystdlib_report(),
        atkinson_report(),
        d3_report(scripts),
        p5_report(scripts),
        flashtext_report(sources),
        stencils_report(scripts),
        mammoth_report(scripts),
        mermaid_report(scripts),
        mathlive_report(),
        docx_report(scripts),
        translate_report(scripts),
    ]
    return {r.key: r for r in reports}


def third_party_libraries() -> list[str]:
    """The Library column of docs/THIRD_PARTY.md's tables."""
    names = []
    for line in _read(THIRD_PARTY).splitlines():
        if (
            line.startswith("| ")
            and not line.startswith("| ---")
            and not line.startswith("| Library")
        ):
            names.append(line.strip("|").split("|")[0].strip())
    return names


def format_report(
    report: Report, full: bool = False, show_groups: bool = False, limit: int = 24
) -> str:
    unused = report.unused
    shown = unused if full or len(unused) <= limit else unused[:limit]
    tail = "" if len(shown) == len(unused) else f" (+{len(unused) - len(shown)} more)"
    lines = [
        f"{report.title}: available {len(report.available)}, called {len(report.called)}, unused: {', '.join(shown)}{tail}"
    ]
    if show_groups:
        used = set(report.called)
        for group, names in report.groups.items():
            lines.append(
                f"  {group}: {len(names)} available, {sum(n in used for n in names)} called"
            )
    for note in report.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    reports = collect()
    if "--json" in argv:
        print(
            json.dumps(
                {
                    k: {"available": len(r.available), "called": len(r.called), "unused": r.unused}
                    for k, r in reports.items()
                },
                indent=1,
            )
        )
        return 0
    for report in reports.values():
        print(format_report(report, full="--full" in argv, show_groups="--groups" in argv))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
