"""The offline translator: which pairs are installed and which files serve them.

WORLD_CLASS_PLAN 28.5 row 10 (Brief 83). The owner, 2026-10-10: "What about
ai free translations?" A model-backed "Translate this passage" already
existed (a document hands the passage to chat); this is the one that needs
no model.

**Where the engine runs, and why.** Bergamot is marian-nmt compiled to
WebAssembly. It runs in a Web Worker in the page
(`frontend/js/translate-worker.js`), not here, measured on 2026-10-10:

- the app's policy (`core/security.build_csp`) already has
  `'wasm-unsafe-eval'` in `script-src` and `worker-src 'self'` for the
  grammar checker, and the engine's Emscripten glue has no `eval` and no
  `new Function`, so it runs under that policy unchanged;
- the server has no WebAssembly runtime and none may be installed (CLAUDE.md
  section 7), and a native build would be one more per-platform binary to
  pin and inspect.

So this module only says what is installed and resolves the file names the
worker may fetch; the text never reaches the server. The files are the
public engine and model, nothing of the notebook's.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.core import extras

#: The package in Settings, Packages that carries the engine and the pairs.
EXTRA_ID = "translate"

#: Said wherever Translate this cannot run yet: names the package as
#: Settings, Packages lists it.
INSTALL_HINT = (
    "Translate this needs the offline translator. Install “Translate "
    "offline” in Settings, Packages."
)

#: The engine's two files, loaded by the worker.
ENGINE_FILES = ("bergamot-translator-worker.js", "bergamot-translator-worker.wasm")

def _pair(source: str, target: str, label: str) -> dict:
    """One direction's row. The file names follow the Mozilla model release's
    own pattern (`model.<pair>.intgemm.alphas.bin`, `lex.50.50.<pair>.s2t.bin`,
    `vocab.<pair>.spm`), the one the English to Spanish files already carry."""
    tag = source + target
    return {
        "from": source,
        "to": target,
        "label": label,
        "model": f"model.{tag}.intgemm.alphas.bin",
        "lex": f"lex.50.50.{tag}.s2t.bin",
        "vocab": f"vocab.{tag}.spm",
    }


#: Every direction the app knows how to ask for. A row reaches the page only
#: when its three files are in the installed folder (`installed_pairs`), so a
#: pair the package does not carry never shows in the picker. Only English to
#: Spanish ships today (`core/extras.py`); the rest wait on pinned downloads
#: (a LEDGER row), and their file names are the release's pattern, not yet
#: checked against a downloaded file.
PAIRS: tuple[dict, ...] = (
    _pair("en", "es", "English to Spanish"),
    _pair("en", "fr", "English to French"),
    _pair("en", "de", "English to German"),
    _pair("en", "it", "English to Italian"),
    _pair("en", "pt", "English to Portuguese"),
    _pair("es", "en", "Spanish to English"),
    _pair("fr", "en", "French to English"),
    _pair("de", "en", "German to English"),
)

_PAIR_KEYS = ("from", "to", "label", "model", "lex", "vocab")

_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".wasm": "application/wasm",
}


def _folder() -> Path | None:
    return extras.download_ready(EXTRA_ID)


def installed_pairs() -> list[dict]:
    """The registry rows whose three files are all in the installed folder, in
    registry order (English to Spanish first, so the first is the default)."""
    folder = _folder()
    if folder is None:
        return []
    return [
        {key: pair[key] for key in _PAIR_KEYS}
        for pair in PAIRS
        if all((folder / pair[key]).is_file() for key in ("model", "lex", "vocab"))
    ]


def status() -> dict:
    """What the palette row and the sheet read: installed or not, the pairs
    there are to pick from, and the sentence to show when it is not."""
    installed = _folder() is not None
    return {
        "installed": installed,
        "pairs": installed_pairs(),
        "engine": ENGINE_FILES[0] if installed else "",
        "hint": "" if installed else INSTALL_HINT,
        "extra": EXTRA_ID,
    }


def served(name: str) -> tuple[Path, str] | None:
    """The file `name` names and its media type, or None.

    `name` only picks an entry from the extra's own list of written files
    (the engine, the licence, each pair's three), so no spelling of a path
    reaches the disk and the marker file is never served."""
    folder = _folder()
    if folder is None:
        return None
    extra = extras.EXTRAS_BY_ID[EXTRA_ID]
    allowed = {file: file for download in extra.downloads for _member, file in download.members}
    allowed.update({pair[key]: pair[key] for pair in PAIRS for key in ("model", "lex", "vocab")})
    listed = allowed.get(name)
    if listed is None or not (folder / listed).is_file():
        return None
    suffix = "." + listed.rsplit(".", 1)[-1] if "." in listed else ""
    return folder / listed, _TYPES.get(suffix, "application/octet-stream")
