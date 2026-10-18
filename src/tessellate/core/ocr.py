"""Local OCR text extraction for uploaded images (ROADMAP.md item 30d).

A whiteboard photo or a scanned page attached via `POST /media/upload`
attaches today as an opaque file nothing reads, "what was on that
whiteboard photo from March" is unanswerable by search. This reads the
image once, in the background, and stores what it found on
`MediaUpload.ocr_text`, so the Library's Image Gallery search (client-side,
same as the rest of the Library's own search box) can find it.

`pytesseract`/Pillow (the thin Python wrapper this module imports) are
listed as the "ocr" entry in `core/extras.py`'s installable-extras
registry: pip installable, so `_run_install` handles that half exactly
like every other extra. The `tesseract` **system binary** itself is a
different problem: no PyPI wheel ships it, so `pip install` alone can
never make it appear. `attempt_binary_install` below (asked for directly:
"automate it if possible") tries the platform's own package manager
non-interactively, winget/brew/apt/dnf/pacman, and `core/extras.py`'s
`_run_install` calls it, best-effort, right after the pip half succeeds
for this one extra specifically. When neither the automated attempt nor a
manual `apt install tesseract-ocr` (INSTALL.md) has happened yet, this
degrades to "extracts nothing," logged once per process rather than once
per upload, never a failed upload, the same "never blocks or fails the
thing it's attached to" contract `ai/embeddings.py`'s own background retry
already follows.
"""

from __future__ import annotations

import functools
import importlib
import importlib.util
import logging
import os
import re
import shutil
import subprocess  # noqa: S404  # fixed args from a hardcoded table below, no shell, no user input
import sys
import time
from pathlib import Path

from tessellate.core import jobs
from tessellate.core.subproc import NO_WINDOW

logger = logging.getLogger("tessellate.ocr")

#: Only raster formats Tesseract/Pillow can open directly, deliberately
#: excludes PDF (`MEDIA_SUFFIXES` in routes_files.py allows it too), which
#: would need page rasterisation (a poppler/pdf2image dependency this
#: feature doesn't pull in) before Tesseract could see anything at all.
OCR_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})

#: Where the Windows installers put `tesseract.exe` when they do not put
#: it on PATH. Each entry is (environment variable, the rest of the path).
#: The UB-Mannheim build, which is the one INSTALL.md points at, offers an
#: "install for me only" mode that needs no administrator and lands under
#: LOCALAPPDATA; that is the mode most people end up in, and the one whose
#: installer never touches the machine PATH.
_WINDOWS_TESSERACT_DIRS = (
    ("ProgramFiles", ("Tesseract-OCR",)),
    ("ProgramFiles(x86)", ("Tesseract-OCR",)),
    ("LOCALAPPDATA", ("Programs", "Tesseract-OCR")),
    ("LOCALAPPDATA", ("Tesseract-OCR",)),
    ("ProgramW6432", ("Tesseract-OCR",)),
)

#: The registry keys the same installers write, whatever directory was
#: chosen. Checked before the fixed directories above, since this one is
#: right even for a custom install path.
_WINDOWS_TESSERACT_KEYS = (
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Tesseract-OCR"),
    ("HKEY_CURRENT_USER", r"SOFTWARE\Tesseract-OCR"),
)


def _registry_tesseract_dir() -> Path | None:
    """The install directory Tesseract's own installer recorded, if any.

    Tried before the fixed Program Files guesses because it is the only
    source that survives someone choosing a different folder. Everything
    here is best effort: `winreg` does not exist off Windows, the key does
    not exist unless Tesseract was installed by its installer, and a value
    that is there but points nowhere is treated as absent.
    """
    try:
        import winreg  # noqa: PLC0415  # Windows-only, imported where it is used
    except ImportError:
        return None
    for root_name, subkey in _WINDOWS_TESSERACT_KEYS:
        root = getattr(winreg, root_name, None)
        if root is None:
            continue
        try:
            with winreg.OpenKey(root, subkey) as key:
                for value_name in ("Path", "InstallDir", ""):
                    try:
                        value, _kind = winreg.QueryValueEx(key, value_name)
                    except OSError:
                        continue
                    if value and Path(value).is_dir():
                        return Path(value)
        except OSError:
            continue
    return None


@functools.lru_cache(maxsize=1)
def _probe_windows_tesseract() -> Path | None:
    """Find `tesseract.exe` where the installer leaves it when PATH misses it.

    Reported directly: "Tesseract installed but not recognised". The
    Windows installers do not reliably add their own directory to PATH, and
    the per-user mode never does, so `shutil.which` says "not installed"
    about a binary sitting in a standard place. Answering "install it
    again" to someone who already has it is the worst version of this.

    Cached: an install that happens while the app is running is picked up
    by `attempt_binary_install`, which clears this, and every other caller
    is a status poll that would otherwise stat the same four directories
    forever.
    """
    candidates = []
    from_registry = _registry_tesseract_dir()
    if from_registry is not None:
        candidates.append(from_registry)
    for env_var, parts in _WINDOWS_TESSERACT_DIRS:
        root = os.environ.get(env_var, "")
        if root:
            candidates.append(Path(root).joinpath(*parts))
    for directory in candidates:
        binary = directory / "tesseract.exe"
        if binary.is_file():
            return binary
    return None


def _adopt_tesseract(binary: Path) -> None:
    """Make one found-off-PATH binary usable by everything that looks later.

    Two places have to agree, and neither is reached by simply returning
    True from `tesseract_available`:

    * `pytesseract` runs `tesseract` by bare name through its own
      `subprocess`, so it needs `tesseract_cmd` pointed at the real file or
      the very next call fails with the error this function exists to
      prevent.
    * `shutil.which`, which `tesseract_available` itself asks first and
      `attempt_binary_install` asks again after an install, plus anything
      else on this process's PATH.

    Both are idempotent: the PATH entry is added once, and re-pointing
    `tesseract_cmd` at the same file costs nothing.
    """
    directory = str(binary.parent)
    path = os.environ.get("PATH", "")
    if directory not in path.split(os.pathsep):
        os.environ["PATH"] = f"{path}{os.pathsep}{directory}" if path else directory
        logger.info("found tesseract at %s, which PATH did not mention", binary)
    try:
        import pytesseract  # noqa: PLC0415  # optional extra, imported where it is used
    except ImportError:
        return  # the binary is there, the Python wrapper is the other half
    pytesseract.pytesseract.tesseract_cmd = str(binary)


def tesseract_available() -> bool:
    """Whether the `tesseract` binary is reachable from this process.

    PATH first, since that is the answer on every platform where the
    package manager installed it. Windows gets a second look in the places
    its installers actually use, and adopts what it finds so that
    `pytesseract` and every later `shutil.which` see it too.
    """
    if shutil.which("tesseract") is not None:
        return True
    if sys.platform == "win32":
        binary = _probe_windows_tesseract()
        if binary is not None:
            _adopt_tesseract(binary)
            return True
    return False


#: The preference the person's language choice is kept under. One setting for
#: every read (the workspace, the background pass after an upload, a PDF page),
#: because "remember my language" that only the button you pressed obeyed would
#: be a setting that quietly stops applying (INBOX 443 (3)).
LANGUAGE_PREFERENCE = "ocr_language"

#: A Tesseract language is a code such as `eng` or `chi_sim`, and several join
#: with a plus (`eng+deu`). Checked before it is stored or handed to the
#: program as an argument: this string ends up on a command line.
_LANGUAGE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,19}(\+[A-Za-z][A-Za-z0-9_]{1,19}){0,3}$")

#: What each common code is called, so the picker says "German" and not
#: `deu`. A code not listed is shown as itself.
LANGUAGE_NAMES = {
    "eng": "English", "deu": "German", "fra": "French", "spa": "Spanish",
    "ita": "Italian", "por": "Portuguese", "nld": "Dutch", "swe": "Swedish",
    "nor": "Norwegian", "dan": "Danish", "fin": "Finnish", "pol": "Polish",
    "ces": "Czech", "hun": "Hungarian", "ron": "Romanian", "tur": "Turkish",
    "ell": "Greek", "rus": "Russian", "ukr": "Ukrainian", "heb": "Hebrew",
    "ara": "Arabic", "hin": "Hindi", "tha": "Thai", "vie": "Vietnamese",
    "jpn": "Japanese", "kor": "Korean", "chi_sim": "Chinese (simplified)",
    "chi_tra": "Chinese (traditional)", "lat": "Latin",
}

#: The list of installed languages is asked of the program, which is a process
#: start; the workspace asks on every open, so the answer is kept briefly.
_LANGUAGES_TTL_SECONDS = 30.0
_languages_cache: dict[str, tuple[float, list[str]]] = {}


def installed_languages() -> list[str]:
    """The language packs the `tesseract` program has, as it reports them.

    Empty when the program is missing or does not answer. `osd` is dropped: it
    is the orientation detector, not a language anyone reads.
    """
    binary = shutil.which("tesseract")
    if not binary:
        return []
    now = time.monotonic()
    cached = _languages_cache.get(binary)
    if cached and now - cached[0] < _LANGUAGES_TTL_SECONDS:
        return list(cached[1])
    languages: list[str] = []
    try:
        result = subprocess.run(  # noqa: S603  # fixed args, the binary found on PATH, no shell
            [binary, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=NO_WINDOW,
        )
        # Some builds print the list on stderr; read both.
        for line in (result.stdout + "\n" + result.stderr).splitlines():
            line = line.strip()
            if line.lower().startswith("list of"):
                continue
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", line) and line != "osd":
                languages.append(line)
    except (OSError, subprocess.SubprocessError):
        logger.info("could not list tesseract languages", exc_info=True)
    _languages_cache[binary] = (now, languages)
    return list(languages)


_version_cache: dict[str, str] = {}


def clear_language_cache() -> None:
    """Forget what the program said about itself (after an install)."""
    _languages_cache.clear()
    _version_cache.clear()


def tesseract_version() -> str:
    """`5.3.4` from `tesseract --version`, or "" when it cannot be asked."""
    binary = shutil.which("tesseract")
    if not binary:
        return ""
    if binary in _version_cache:
        return _version_cache[binary]
    try:
        result = subprocess.run(  # noqa: S603  # fixed args, the binary found on PATH, no shell
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    first = ((result.stdout or result.stderr).strip().splitlines() or [""])[0]
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", first)
    _version_cache[binary] = match.group(1) if match else ""
    return _version_cache[binary]


def saved_language() -> str:
    """The language the person chose, or "" for Tesseract's own default."""
    deps = importlib.import_module("tessellate.core.deps")
    config = deps.peek_config()  # never starts the app (and its data folder) to ask
    if config is None:
        return ""
    try:
        value = str(config.get_preference(LANGUAGE_PREFERENCE, "") or "")
    except Exception:  # noqa: BLE001  # settings not readable: the default
        return ""
    return value if _LANGUAGE_PATTERN.match(value) else ""


def set_language(code: str) -> str:
    """Remember a language. "" goes back to the default. Raises `ValueError`
    for a code that is malformed or whose pack is not installed, with a
    message that says what to do."""
    code = (code or "").strip()
    if code:
        if not _LANGUAGE_PATTERN.match(code):
            raise ValueError("That is not a language code. Pick one from the list.")
        have = installed_languages()
        missing = [part for part in code.split("+") if part not in have]
        if missing:
            raise ValueError(
                f"The {', '.join(missing)} language pack isn't installed for Tesseract. "
                "Install it with your package manager (for example tesseract-ocr-deu), "
                "then reopen this list."
            )
    deps = importlib.import_module("tessellate.core.deps")
    deps.get_config().set_preference(LANGUAGE_PREFERENCE, code)
    return code


def effective_language() -> str:
    """The saved language when its packs are all still installed, else "".

    A pack removed since it was chosen must not turn every read into a
    failure: the default language reads, and the status says it fell back.
    """
    code = saved_language()
    if not code:
        return ""
    have = installed_languages()
    return code if have and all(part in have for part in code.split("+")) else ""


def _language_kwargs() -> dict:
    """`{"lang": code}` only when a language is chosen, so the default call is
    exactly the call it always was."""
    code = effective_language()
    return {"lang": code} if code else {}


def packages_available() -> bool:
    """Whether `pytesseract` and Pillow can be imported (a look, not an import)."""
    try:
        return (
            importlib.util.find_spec("pytesseract") is not None
            and importlib.util.find_spec("PIL") is not None
        )
    except (ImportError, ValueError):
        return False


#: **RapidOCR, the second local reader** (WORLD_CLASS_PLAN row 31 item 97, the
#: owner asking for an OCR alternative to pytesseract). PaddleOCR's models on
#: onnxruntime: pip-installable whole, no system program, better than
#: Tesseract on photographs and mixed layouts, Apache-2.0. **An optional extra,
#: never a dependency**: `core/extras.py`'s "rapidocr" row installs it on the
#: person's own press, like faster-whisper, and nothing here imports it at
#: module level. Two package names have shipped the same `RapidOCR` class:
#: `rapidocr_onnxruntime` (1.x, the one the extra installs) and `rapidocr`
#: (2.x and later); either is read.
RAPIDOCR_MODULES = ("rapidocr_onnxruntime", "rapidocr")

#: The readers' names as a person reads them. `"tesseract"` stays the *id* of
#: the local reader in stored readings, page reads and the API (`source`,
#: the reader picker's value), whichever engine did the reading: rows written
#: before RapidOCR existed say it, and renaming a stored id to say which
#: program ran would split one reader in two everywhere it is read back.
ENGINE_NAMES = {"tesseract": "Tesseract", "rapidocr": "RapidOCR"}


def rapidocr_available() -> bool:
    """Whether a RapidOCR package can be imported (a look, not an import)."""
    for name in RAPIDOCR_MODULES:
        try:
            if importlib.util.find_spec(name) is not None:
                return True
        except (ImportError, ValueError):
            continue
    return False


#: The local engines a reader may name outright (INBOX 717, the owner: "does
#: the ocr worspace give rapidocr as an alternative??"). `""` is the automatic
#: pick below, and stays what every caller that names nothing gets.
LOCAL_ENGINES = ("tesseract", "rapidocr")


def engine(choice: str = "") -> str:
    """Which local reader reads: `"tesseract"` when both of its halves are
    here (the default whenever it is present, as it always was),
    `"rapidocr"` when Tesseract is not ready and RapidOCR is installed, and
    `""` when neither can read.

    `choice="rapidocr"` is the workspace's explicit pick: RapidOCR reads even
    when Tesseract is ready, and `""` comes back when it is not installed (the
    caller says so; nothing is substituted for an engine somebody named)."""
    if choice == "rapidocr":
        return "rapidocr" if rapidocr_available() else ""
    if tesseract_available() and packages_available():
        return "tesseract"
    if rapidocr_available():
        return "rapidocr"
    return ""


def engine_name(choice: str = "") -> str:
    """The reading engine's name for a sentence, "Tesseract" when none is
    installed (it is the one an install suggestion names first)."""
    if choice == "rapidocr":
        return "RapidOCR"
    return ENGINE_NAMES.get(engine(), "Tesseract")


def local_available() -> bool:
    """Whether some local OCR engine can read here (the question every caller
    that used to ask `tesseract_available()` about *reading* meant)."""
    return bool(engine())


@functools.lru_cache(maxsize=1)
def _rapidocr_reader():
    """One RapidOCR instance per process: building it loads three ONNX models
    (about a second), which a reader built per page would pay every time.
    `lru_cache` rather than a module global, the same shape as
    `_log_binary_missing` (CodeQL's unused-global note)."""
    for name in RAPIDOCR_MODULES:
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        return module.RapidOCR()
    raise ImportError("no RapidOCR package is installed")


def _rapidocr_lines(image_path: Path) -> list[tuple[list, str, float]] | None:
    """`(box, text, score)` per line RapidOCR found, in its reading order, or
    None when it cannot run. A box is four `[x, y]` corners; a score 0 to 1.

    The 1.x call returns `(result, elapse)` with `result` a list of
    `[box, text, score]` or None for a page with no text; 2.x returns an
    object with `boxes`, `txts` and `scores`. Both are read."""
    try:
        reader = _rapidocr_reader()
        out = reader(str(image_path))
    except Exception:
        logger.warning("RapidOCR failed for %s", image_path.name, exc_info=True)
        return None
    if isinstance(out, tuple):
        out = out[0]
    if out is None:
        return []
    if hasattr(out, "txts"):
        boxes = list(getattr(out, "boxes", None) if getattr(out, "boxes", None) is not None else [])
        texts = list(out.txts or [])
        scores = list(getattr(out, "scores", None) or [1.0] * len(texts))
        rows = zip(boxes, texts, scores)
    else:
        rows = ((row[0], row[1], row[2]) for row in out if len(row) >= 3)
    lines = []
    for box, text, score in rows:
        text = str(text).strip()
        if not text:
            continue
        try:
            corners = [[float(x), float(y)] for x, y in box]
        except (TypeError, ValueError):
            continue
        lines.append((corners, text, float(score)))
    return lines


def _rapidocr_text(image_path: Path) -> str:
    lines = _rapidocr_lines(image_path)
    return "\n".join(text for _, text, _ in lines or []).strip()


def _image_size(image_path: Path, lines: list[tuple[list, str, float]]) -> tuple[float, float]:
    """The page's pixel size, from Pillow (RapidOCR's own dependency), or
    failing that the furthest corner any line reached."""
    try:
        from PIL import Image

        with Image.open(image_path) as img:
            return float(img.size[0]), float(img.size[1])
    except Exception:  # noqa: BLE001  # Pillow missing or the file unreadable: the boxes still say something
        # A PNG says its size in its first 24 bytes, so a RapidOCR install
        # without Pillow still gets the true page size for the commonest
        # screenshot format; anything else falls back to the boxes.
        try:
            head = image_path.read_bytes()[:24]
            if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
                return float(int.from_bytes(head[16:20], "big")), float(int.from_bytes(head[20:24], "big"))
        except OSError:
            pass  # unreadable here too: the boxes below are what is left
        xs = [x for corners, _, _ in lines for x, _ in corners] or [0.0]
        ys = [y for corners, _, _ in lines for _, y in corners] or [0.0]
        return max(xs), max(ys)


def _rapidocr_regions(image_path: Path) -> dict | None:
    """`extract_regions`' shape from RapidOCR's lines. RapidOCR finds lines,
    not blocks, so lines are joined into a block while each starts within
    about half a line's height of the last one's foot and overlaps it
    sideways: a paragraph comes back as one region, a new column or a gap as
    another, which is what Tesseract's block numbering gives."""
    lines = _rapidocr_lines(image_path)
    if lines is None:
        return None
    width, height = _image_size(image_path, lines)
    if not width or not height:
        return None
    boxes = []
    for corners, text, score in lines:
        xs = [x for x, _ in corners]
        ys = [y for _, y in corners]
        boxes.append({"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys), "text": text, "score": score})
    heights = sorted(b["y1"] - b["y0"] for b in boxes)
    median_height = heights[len(heights) // 2] if heights else 0.0
    blocks: list[dict] = []
    for b in boxes:
        last = blocks[-1] if blocks else None
        line_h = b["y1"] - b["y0"]
        joins = (
            last is not None
            and 0 <= b["y0"] - last["y1"] <= max(line_h, last["line_h"]) * 0.6
            and b["x0"] < last["x1"]
            and b["x1"] > last["x0"]
        )
        if joins:
            last["lines"].append(b["text"])
            last["words"] += _line_words(b["text"], b["x0"], b["y0"], b["x1"], b["y1"], width, height)
            last["scores"].append(b["score"])
            last["heights"].append(line_h)
            last["x0"], last["y0"] = min(last["x0"], b["x0"]), min(last["y0"], b["y0"])
            last["x1"], last["y1"] = max(last["x1"], b["x1"]), max(last["y1"], b["y1"])
            last["line_h"] = line_h
        else:
            blocks.append({
                **b, "lines": [b["text"]], "scores": [b["score"]], "heights": [line_h], "line_h": line_h,
                "words": _line_words(b["text"], b["x0"], b["y0"], b["x1"], b["y1"], width, height),
            })
    regions = []
    for block in blocks:
        block_heights = sorted(block["heights"])
        block_median = block_heights[len(block_heights) // 2]
        kind = "heading" if median_height and block_median >= median_height * REGION_HEADING_RATIO else "text"
        regions.append(
            {
                "index": len(regions),
                "kind": kind,
                "text": "\n".join(block["lines"]),
                "confidence": round(100 * sum(block["scores"]) / len(block["scores"]), 1),
                "box": {
                    "x": round(block["x0"] / width, 5),
                    "y": round(block["y0"] / height, 5),
                    "w": round((block["x1"] - block["x0"]) / width, 5),
                    "h": round((block["y1"] - block["y0"]) / height, 5),
                },
                "words": block["words"],
            }
        )
    return {
        "width": int(width),
        "height": int(height),
        "regions": regions,
        "source": "tesseract",
        "engine": "rapidocr",
    }


def engine_status() -> dict:
    """One honest answer to "can a local reader read here, and how".

    `binary` and `package` are Tesseract's two halves, reported separately
    because they are fixed by different things (`attempt_binary_install` for
    one, pip for the other) and "not installed" names neither. `engine` is
    the one that reads (`engine()`), `rapidocr` whether RapidOCR is
    installed; Tesseract's languages apply to Tesseract only. `fix` is the
    one action that mends it, which the workspace and Settings both offer.
    """
    binary = tesseract_available()
    package = packages_available()
    reader = engine()
    ready = bool(reader)
    if ready:
        reason = ""
    elif not binary and not package:
        reason = "Tesseract isn't installed."
    elif not binary:
        reason = "The Tesseract program isn't installed, though the part that connects it to Tessellate is."
    else:
        reason = "The part that connects Tesseract to Tessellate isn't installed."
    languages = installed_languages() if binary else []
    saved = saved_language()
    chosen = effective_language()
    note = ""
    if saved and not chosen and binary:
        note = f"The saved language ({saved}) is no longer installed, so the default is used."
    return {
        "ready": ready,
        "binary": binary,
        "package": package,
        "version": tesseract_version() if binary else "",
        "languages": [
            {"code": code, "name": LANGUAGE_NAMES.get(code, code)} for code in languages
        ],
        "language": chosen,
        "language_note": note,
        "reason": reason,
        "fix": "" if ready else "install",
        "engine": reader,
        "engine_name": ENGINE_NAMES.get(reader, ""),
        "rapidocr": rapidocr_available(),
        #: The download each install costs, from the one list that installs
        #: them (`core/extras.py`), so the workspace's offer says it without
        #: a second copy of the number (WORLD_CLASS_PLAN 28.4 row 5).
        "rapidocr_size": _extra_size("rapidocr"),
        "tesseract_size": _extra_size("ocr"),
    }


def extra_size(extra_id: str) -> str:
    """The download an extra costs, as `core/extras.py`'s table says it.
    extras.py imports this module, so it sets this name when its table is
    built rather than being imported here (tests/test_no_import_cycles.py
    holds the direction); until then no size is known."""
    return ""


def _extra_size(extra_id: str) -> str:
    return extra_size(extra_id)


def unavailable_reason(choice: str = "") -> str:
    """Why no local reader can read right now, in a sentence that says what
    to do, or "" when one can. Used where a route used to return nothing and
    let a missing engine look like a page with no text on it."""
    if choice == "rapidocr":
        if rapidocr_available():
            return ""
        return "RapidOCR isn't installed. Install it in Settings, Packages, or pick another reader."
    status = engine_status()
    if status["ready"]:
        return ""
    return (
        f"{status['reason']} Install it in Settings, Packages (Search inside images), "
        "or RapidOCR beside it, or read this with the AI vision model instead."
    )


def _one_thread_for_tesseract() -> None:
    """Pin Tesseract's OpenMP to one thread unless the person set it.

    Measured 2026-09-14 in a four-core container: a 600x160 line of text took
    42 s with the default (every OpenMP thread spinning on the LSTM's tiny
    matrices), and 0.28 s with `OMP_THREAD_LIMIT=1`. The same oversubscription
    hits any laptop running the app beside a model that already owns the
    cores, and the Tesseract project's own advice for that case is this
    variable. `setdefault`, so a person who tuned it keeps their value; the
    child process inherits the environment through pytesseract's subprocess.
    """
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")


@functools.lru_cache(maxsize=1)
def _log_binary_missing() -> None:
    """Called on every missing-binary path but only ever logs once per
    process: `lru_cache` runs the body on the first call and returns the
    cached `None` on every later one, which needs no mutable module-level
    flag at all (CodeQL flagged the plain-bool version of this as an
    unused-global-variable note: `py/unused-global-variable`)."""
    logger.info(
        "the 'tesseract' binary isn't on PATH: uploaded images won't "
        "get searchable OCR text until Tesseract OCR is installed "
        "separately (see INSTALL.md); this is not an error"
    )


@functools.lru_cache(maxsize=1)
def _log_package_missing() -> None:
    """Same once-per-process shape as `_log_binary_missing` above, for the
    other gap: the binary is there but `pytesseract`/Pillow aren't."""
    logger.info(
        "tesseract is installed but the pytesseract/Pillow Python "
        "packages aren't: run: pip install pytesseract Pillow"
    )


def extract_text(image_path: Path, choice: str = "") -> str:
    """Best-effort OCR text for one image file. Never raises: a missing
    binary, a corrupt image, or an unsupported format all just mean no text
    was found, exactly as if the image genuinely had none. RapidOCR reads
    when Tesseract is not ready and it is installed (`engine()`), or when it
    was chosen (`choice`)."""
    picked = engine(choice)
    if picked == "rapidocr":
        return _rapidocr_text(image_path)
    if choice == "rapidocr":
        return ""
    if not tesseract_available():
        _log_binary_missing()
        return ""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        # The tesseract *binary* is on PATH (checked above) but the
        # `pytesseract`/`Pillow` Python packages aren't installed: a
        # different gap than the binary-missing one, worth its own message.
        _log_package_missing()
        return ""
    _one_thread_for_tesseract()
    try:
        with Image.open(image_path) as img:
            text = pytesseract.image_to_string(img, **_language_kwargs())
        return text.strip()
    except Exception:
        # A single unreadable image (corrupt file, an animated GIF Tesseract
        # chokes on, a format Pillow can't decode) must never take down the
        # background thread it runs on or be mistaken for the binary being
        # missing: logged with the traceback so a real recurring failure is
        # still diagnosable, just not surfaced to the person who uploaded it.
        logger.warning("OCR failed for %s", image_path.name, exc_info=True)
        return ""


#: A word Tesseract is less than this sure of is dropped from a region's
#: text. Its own confidence is 0–100 and it reports -1 for the structural
#: rows (page/block/paragraph) that carry no word at all. 30 is low enough to
#: keep a smudged scan readable and high enough to drop the punctuation-noise
#: it invents at the edges of a photograph.
REGION_MIN_CONFIDENCE = 30

#: A word taller than this multiple of the page's median word height is read
#: as a heading rather than body text. Purely a *presentation* hint for the
#: region list: nothing downstream depends on it being right, which is why a
#: ratio is honest here and a "table"/"formula" classifier would not be:
#: Tesseract reports boxes and confidences, not semantic structure, and
#: labelling a region "table" from box geometry alone would be a guess
#: presented as a fact.
REGION_HEADING_RATIO = 1.45


def extract_regions(image_path: Path, choice: str = "") -> dict | None:
    """Text laid out as Tesseract found it: one entry per block, with the
    box it occupies on the page.

    Asked for directly, with three screenshots of Baidu's Unlimited-OCR:
    *"for the document ocr I want smth like this"*, a page beside its
    regions, each region typed and its text separately readable, rather than
    one wall of text under the picture with no way to tell which part of the
    page a line came from.

    Returns `None`, not an empty result, when the OCR stack is missing or
    the image cannot be read, so a caller can tell "nothing is installed"
    apart from "this page has no text on it" and say so. Boxes are
    **normalised to 0–1** against the image's own pixel size, because the
    thing that draws them is an `<img>` scaled to whatever width the panel
    happens to be; sending pixels would make every overlay wrong at every
    size but one. RapidOCR's lines are grouped into the same blocks when it
    is the engine (`_rapidocr_regions`).
    """
    picked = engine(choice)
    if picked == "rapidocr":
        return _rapidocr_regions(image_path)
    if choice == "rapidocr":
        return None
    if not tesseract_available():
        _log_binary_missing()
        return None
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        _log_package_missing()
        return None
    _one_thread_for_tesseract()
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            data = pytesseract.image_to_data(
                img, output_type=pytesseract.Output.DICT, **_language_kwargs()
            )
    except Exception:
        logger.warning("OCR regions failed for %s", image_path.name, exc_info=True)
        return None
    if not width or not height:
        return None

    #: Grouped by Tesseract's own block numbering rather than by clustering
    #: boxes ourselves: it has already done the page analysis, and a second
    #: opinion computed from the boxes it returned would only ever be worse.
    blocks: dict[tuple[int, int], dict] = {}
    heights: list[float] = []
    for i in range(len(data.get("text", []))):
        word = str(data["text"][i]).strip()
        if not word:
            continue
        try:
            confidence = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if confidence < REGION_MIN_CONFIDENCE:
            continue
        key = (int(data["page_num"][i]), int(data["block_num"][i]))
        left, top = float(data["left"][i]), float(data["top"][i])
        word_w, word_h = float(data["width"][i]), float(data["height"][i])
        heights.append(word_h)
        block = blocks.setdefault(
            key,
            {"words": [], "confidences": [], "x0": left, "y0": top, "x1": left, "y1": top,
             "line": int(data["line_num"][i]), "heights": [], "boxes": []},
        )
        #: A newline where Tesseract says the line changed, so a paragraph
        #: comes back as a paragraph. Joining every word with a space turned
        #: an address block into one run-on line.
        if int(data["line_num"][i]) != block["line"]:
            block["words"].append("\n")
            block["line"] = int(data["line_num"][i])
        block["words"].append(word)
        block["boxes"].append(_word_box(word, left, top, word_w, word_h, width, height))
        block["confidences"].append(confidence)
        block["heights"].append(word_h)
        block["x0"] = min(block["x0"], left)
        block["y0"] = min(block["y0"], top)
        block["x1"] = max(block["x1"], left + word_w)
        block["y1"] = max(block["y1"], top + word_h)

    median_height = sorted(heights)[len(heights) // 2] if heights else 0.0
    regions = []
    for key in sorted(blocks):
        block = blocks[key]
        text = " ".join(block["words"]).replace(" \n ", "\n").replace("\n ", "\n").strip()
        if not text:
            continue
        block_heights = block["heights"]
        block_median = sorted(block_heights)[len(block_heights) // 2] if block_heights else 0.0
        kind = (
            "heading"
            if median_height and block_median >= median_height * REGION_HEADING_RATIO
            else "text"
        )
        regions.append(
            {
                "index": len(regions),
                "kind": kind,
                "text": text,
                "confidence": round(sum(block["confidences"]) / len(block["confidences"]), 1),
                #: x/y/w/h as fractions of the image, top-left origin.
                "box": {
                    "x": round(block["x0"] / width, 5),
                    "y": round(block["y0"] / height, 5),
                    "w": round((block["x1"] - block["x0"]) / width, 5),
                    "h": round((block["y1"] - block["y0"]) / height, 5),
                },
                "words": block["boxes"],
            }
        )
    return {"width": width, "height": height, "regions": regions, "source": "tesseract"}


def _word_box(text: str, left: float, top: float, w: float, h: float, width: float, height: float) -> dict:
    """One word where it sits, normalised like a region's box: what the
    workspace's Live Text layer positions over the page (WORLD_CLASS_PLAN 28.4
    row 7), so a drag across the picture selects the words themselves."""
    return {
        "text": text,
        "x": round(left / width, 5),
        "y": round(top / height, 5),
        "w": round(w / width, 5),
        "h": round(h / height, 5),
    }


def _line_words(text: str, x0: float, y0: float, x1: float, y1: float, width: float, height: float) -> list[dict]:
    """RapidOCR boxes lines, not words: each word gets the slice of its line
    its characters take, which is close for the proportional text of a page
    and keeps a selection in reading order."""
    words = str(text or "").split()
    chars = sum(len(word) for word in words) + max(0, len(words) - 1)
    if not words or not chars:
        return []
    out, at = [], x0
    per = (x1 - x0) / chars
    for word in words:
        out.append(_word_box(word, at, y0, per * len(word), y1 - y0, width, height))
        at += per * (len(word) + 1)
    return out


#: A line this many characters or fewer, with no closing punctuation, is a
#: heading rather than a one-line paragraph. Twelve words at a generous average
#:, long enough for a real section title, short enough that a sentence which
#: happens to end without a full stop is not mistaken for one.
READING_HEADING_CHARS = 72


def regions_from_reading(text: str) -> list[dict]:
    """Split a page's *reading* into typed blocks, with no image involved.

    **Why this exists: "the regions dont work without tesseract but surely
    there's a better way."** They did not, and the fallback said so honestly, 
    one region covering the whole page and a message telling you to go install
    a binary. That is a correct answer to the wrong question. This app's
    primary reader is a vision model, not Tesseract (see `read_page`), so on
    the path most people actually use, the page *was* read, in order, with its
    structure intact in the text, and the workspace threw all of that away
    because it could not draw a rectangle around it.

    Regions are two different things wearing one name: **where a block sits on
    the page**, which genuinely needs pixel analysis, and **what the blocks
    are, in order**, which does not. This computes the second from the reading
    itself, so every page gets regions whatever is installed: a heading is
    still a heading, a table is still a table, and "this sentence came from
    block 4 of page 2" is answerable: which is what "make it so extracted
    text is visually linked to the page or section it was extracted from"
    actually asks for. Where Tesseract *is* installed, `extract_regions` above
    still supplies real boxes and this is not used.

    Blocks are separated by blank lines, which is what every reader, vision
    model, Tesseract's own `--psm 1`, a PDF text layer, already emits between
    paragraphs. `box` is None rather than a full-page rectangle: a box that
    claims to be the whole page is a *wrong* answer, and the UI can draw a
    list without one but cannot un-draw a lie.
    """
    blocks: list[dict] = []
    for chunk in re.split(r"\n\s*\n", str(text or "")):
        body = chunk.strip("\n").rstrip()
        if not body.strip():
            continue
        blocks.append(
            {
                "index": len(blocks),
                "kind": _reading_block_kind(body),
                "text": body,
                #: Nothing measured it, so nothing pretends to have. The
                #: workspace reads 0.0 as "no confidence to show" and omits the
                #: badge rather than displaying a confident-looking zero.
                "confidence": 0.0,
                "box": None,
            }
        )
    return blocks


def _reading_block_kind(body: str) -> str:
    """What a block of a reading is, from its shape alone.

    Deliberately shape, not content: a model asked to label its own output
    costs a second round trip per page and disagrees with itself between runs,
    and every one of these is a rule a person could check by looking.
    """
    lines = [line for line in body.splitlines() if line.strip()]
    first = lines[0].strip() if lines else ""

    #: A fenced block, or a run of lines that are all indented four spaces, 
    #: the two ways every markdown reader writes code.
    if first.startswith("```") or all(line.startswith("    ") for line in lines):
        return "code"
    #: Two or more pipes on most lines is a table however it was drawn; a
    #: single stray pipe in prose is not.
    if len(lines) >= 2 and sum(line.count("|") >= 2 for line in lines) >= len(lines) - 1:
        return "table"
    #: Bullets, numbers, or checkboxes on the majority of lines.
    bulleted = sum(
        bool(re.match(r"^\s*(?:[-*+\u2022]|\d+[.)])\s+", line)) for line in lines
    )
    if lines and bulleted >= max(2, len(lines) - 1):
        return "list"
    #: A markdown heading says so outright. Otherwise: one short line with no
    #: sentence-ending punctuation is a title, which is how a heading reads on
    #: a scanned page where nothing carries markup at all.
    if first.startswith("#"):
        return "heading"
    if (
        len(lines) == 1
        and len(first) <= READING_HEADING_CHARS
        and not first.endswith((".", "!", "?", ":", ";", ","))
    ):
        return "heading"
    return "text"


def extract_and_store(upload_id: int, image_path: Path) -> None:
    """Runs OCR synchronously and writes the result onto the `MediaUpload`
    row if any text was found. Split out from `extract_in_background` below
    so tests can call this directly without waiting on a real thread.

    **Once per picture, by one engine** (owner: "the vision captioning and
    ocr should only happen each once, not multiple times each"). It had no
    stored-result guard, so every save of a note holding the picture read it
    again; and it ran beside the vision model's own read of the same text.
    Now it stands down when the text is already stored, and when a vision
    model is there to read it (`vision_ocr_and_store`, queued by the same
    commit), so the picture is read once, by the better reader available.
    """
    deps = importlib.import_module("tessellate.core.deps")
    from tessellate.core.database import MediaUpload

    with deps.get_db().session() as session:
        upload = session.get(MediaUpload, upload_id)
        if upload is None or upload.ocr_text:
            return
    try:
        if deps.get_model_manager().resolve_vision_model(deps.get_ollama()):
            return
    except Exception:  # noqa: BLE001  # no backend reachable: Tesseract is the reader
        pass
    text = extract_text(image_path)
    if not text:
        return
    # Imported here, not at module level: this file has to stay importable
    # (for `tesseract_available()`/`extract_text()` alone) without pulling
    # in the whole app's dependency graph just to check whether a binary
    # exists on PATH.
    #
    # `deps` specifically goes through `importlib` rather than an `import`
    # statement, because a statement is what CodeQL py/cyclic-import counts, 
    # deferring it into the function body does not clear the finding, only
    # dropping the statement does (`entry/manager.py` records the same). The
    # cycle here is `ai.embeddings -> core.extras -> core.ocr -> core.deps ->
    # ai.embeddings`, and this is its wrong-direction edge: `deps` is the
    # container that builds the embedding service, so nothing it builds
    # should name it back. Runtime behaviour is identical.
    with deps.get_db().session() as session:
        upload = session.get(MediaUpload, upload_id)
        if upload is None:
            return  # deleted (or its upload never committed) before OCR finished
        upload.ocr_text = text
        session.commit()


def extract_in_background(upload_id: int, image_path: Path) -> None:
    """Fire-and-forget: never blocks the `POST /media/upload` response.
    Tesseract can take a second or two per image, and the upload itself is
    already done by the time this runs, the same "don't make the caller
    wait for something that isn't the point of the request" reasoning as
    `ai/embeddings.py`'s background reinstall-and-retry."""
    jobs.enqueue("ocr", extract_and_store, upload_id, image_path, name=image_path.name, dedupe_key=("ocr", upload_id))


#: Per platform, the first package manager found on PATH gets tried. Every
#: command is fixed and non-interactive, no shell, no string built from
#: user input, and every flag exists specifically to prevent a prompt this
#: process has no way to answer (a password, a EULA dialog, an "are you
#: sure?"). Linux tries three, in order, since which one exists varies by
#: distro; Windows and macOS have one first-party option each.
_BINARY_INSTALL_COMMANDS: dict[str, list[tuple[str, list[str]]]] = {
    "win32": [
        (
            "winget",
            [
                "winget",
                "install",
                "--id",
                "UB-Mannheim.Tesseract-OCR",
                "-e",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
        )
    ],
    "darwin": [("brew", ["brew", "install", "tesseract"])],
    "linux": [
        ("apt-get", ["apt-get", "install", "-y", "tesseract-ocr"]),
        ("dnf", ["dnf", "install", "-y", "tesseract"]),
        ("pacman", ["pacman", "-S", "--noconfirm", "tesseract"]),
    ],
}

BINARY_INSTALL_TIMEOUT = 90


def attempt_binary_install(timeout: int = BINARY_INSTALL_TIMEOUT) -> tuple[bool, str]:
    """Best-effort, non-interactive install of the `tesseract` system binary
    itself: the one part `pip install pytesseract` can never do, since it
    isn't a Python package. Asked for directly: "add the option for install
    assistance for the tesseract program installation, automate it if
    possible."

    Tries the platform's own package manager with fully non-interactive
    flags. Never prompts, never hangs waiting on a password or a UAC dialog
    it has no way to answer, every attempt is wall-clock bounded, and
    never raises; any failure is reported back as an honest, actionable
    message rather than a crash. `installed` is only ever `True` once
    `tesseract_available()` is confirmed **after** the attempt, the
    installer's own exit code is not trusted alone, the same "a POST
    response can lie about stored state" caution this app applies
    everywhere else that reports success.
    """
    if tesseract_available():
        return True, "Tesseract is already installed."

    platform_key = "linux" if sys.platform.startswith("linux") else sys.platform
    candidates = _BINARY_INSTALL_COMMANDS.get(platform_key, [])
    available = [(name, cmd) for name, cmd in candidates if shutil.which(name)]
    if not available:
        return False, (
            "Couldn't find a package manager to install Tesseract "
            "automatically on this system, install it by hand (see "
            "INSTALL.md)."
        )

    # Linux package managers need root. Tried as-is first (already root: 
    # common inside a container) and, only if that's not the case, once
    # more through `sudo -n`, which fails immediately rather than prompting
    # for a password this non-interactive process has no way to answer,
    # instead of silently hanging until the timeout above kills it.
    manager_name, base_command = available[0]
    attempts = [base_command]
    if platform_key == "linux" and hasattr(os, "geteuid") and os.geteuid() != 0:
        attempts = [["sudo", "-n", *base_command], base_command]

    last_error = ""
    for attempt in attempts:
        try:
            result = subprocess.run(  # noqa: S603  # fixed args from the table above, no shell
                attempt,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=NO_WINDOW,
            )
        except FileNotFoundError:
            continue  # `sudo` itself isn't installed: fall through to the bare command
        except subprocess.TimeoutExpired:
            last_error = f"{attempt[0]} timed out after {timeout}s"
            continue
        # The install just changed the filesystem the probe cached an answer
        # about, and on Windows the installer it ran is exactly the one that
        # may not touch PATH, so the confirmation below has to be allowed to
        # look again rather than repeat a stale "not there".
        _probe_windows_tesseract.cache_clear()
        if result.returncode == 0 and tesseract_available():
            return True, "Tesseract installed."
        tail = (result.stderr or result.stdout or "").strip().splitlines()
        last_error = tail[-1] if tail else f"{manager_name} exited with code {result.returncode}"

    return False, (
        f"Couldn't install Tesseract automatically ({last_error or 'unknown error'}) "
        ", install it by hand (see INSTALL.md)."
    )
