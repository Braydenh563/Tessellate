"""What a Settings model card says about a model (INBOX 444).

The Models screen's "Suggested downloads" was 31 rows of ``name ~size purpose``
and 29 identical Download buttons. A person choosing hardware they already own
needs four things the list never said: how much memory the model asks for,
what it is good at, whether it fits *this* computer, and which one to start
with. The catalogue (`model_manager.SUGGESTED_MODELS`) stays the hand-kept
list of names, sizes and purposes; this module derives the rest from it, in
one place with tests, so the page does not guess.

Everything here is an estimate and says so. Memory is counted in system RAM;
a GPU with enough video memory runs the same model faster, and this does not
measure one. The fit verdict is "would this plausibly run", not a benchmark.

Also here: `inspect_model_name`, the check behind "Download another model".
It is pure (no network, because the app draws its settings offline): it says
what a typed name *is* (an Ollama library model, a community model on
ollama.com, or a Hugging Face GGUF repository that Ollama pulls through
`hf.co/`) and refuses what Ollama could not pull, so the person is told before
a download starts rather than by a failed one.
"""

from __future__ import annotations

import math
import re

#: What each catalogue group is *for*. The page groups its cards by this, and
#: "Use" on a card sets the matching role (chat, images, reading text, search).
PURPOSE_OF_KIND = {
    "text": "chat",
    "moe": "chat",
    "embedding": "embeddings",
    "vision": "vision",
    "ocr": "ocr",
}

#: One starting pick per group, in the catalogue's own words: the entry whose
#: purpose line already says "the default", "start with this one" or "the one
#: to try". Not a benchmark; the page says "our starting pick".
RECOMMENDED = {
    "text": "llama3.2",
    "moe": "gemma4:e2b",
    "embedding": "nomic-embed-text",
    "vision": "moondream",
    "ocr": "hf.co/ggml-org/GLM-OCR-GGUF:Q8_0",
}

#: Fit verdicts, as the share of the computer's memory the model asks for. The
#: rest of the memory is the operating system, the app and a browser, which
#: between them want 3 to 4 GB on any machine this runs on.
FITS_BELOW = 0.60
TIGHT_BELOW = 0.85


def size_gb(text: str | None) -> float | None:
    """``"~2.7 GB"`` or ``"274 MB"`` as gigabytes; None when it cannot be read."""
    match = re.search(r"([\d.]+)\s*(GB|MB)", text or "", re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    return value if match.group(2).upper() == "GB" else value / 1000


def ram_needed_gb(entry: dict) -> float | None:
    """The memory a model asks for while it runs, in gigabytes.

    The catalogue states it where it matters (``ram_gb`` on the entries whose
    purpose line says "Needs ~16 GB"); otherwise it is the weights plus the
    working memory a conversation adds, 15% and 0.7 GB, rounded up to the next
    half gigabyte. An estimate for a Q4 model at a normal context window, which
    is what Ollama pulls by default.
    """
    stated = entry.get("ram_gb")
    if stated:
        return float(stated)
    weights = size_gb(entry.get("size"))
    if weights is None:
        return None
    return max(1.0, math.ceil((weights * 1.15 + 0.7) * 2) / 2)


def good_for(kind: str, entry: dict) -> list[str]:
    """What the model is good at, as short tokens the page words itself."""
    purpose = (entry.get("purpose") or "").lower()
    if kind == "text":
        tags = ["chat", "filing"]
    elif kind == "moe":
        tags = ["chat"]
    elif kind == "embedding":
        return ["embeddings"]
    elif kind == "vision":
        tags = ["vision"]
        if re.search(r"reading text|text reading|text in images", purpose):
            tags.append("ocr")
        return tags
    else:  # ocr
        return ["ocr"]
    if re.search(r"agent|tool", purpose):
        tags.append("agent")
    if re.search(r"writing|summaris", purpose):
        tags.append("writing")
    if re.search(r"long-document|context window", purpose):
        tags.append("long documents")
    return tags


_FIT_ORDER = ("fits", "tight", "too_big")


def _share_fit(need_gb: float, pool_gb: float) -> str:
    share = need_gb / pool_gb
    if share <= FITS_BELOW:
        return "fits"
    if share <= TIGHT_BELOW:
        return "tight"
    return "too_big"


def fit_reason(
    need_gb: float | None, total_gb: float | None, free_gb: float | None = None, vram_gb: float | None = None
) -> str | None:
    """Why the verdict is not the plain share of memory: ``gpu`` (the video
    memory holds the model more comfortably, so it runs there) or ``low_free``
    (little memory is free right now). None when the verdict is the plain one."""
    if need_gb is None or not total_gb:
        return None
    plain = _share_fit(need_gb, total_gb)
    on_card = _share_fit(need_gb, vram_gb) if vram_gb else None
    if on_card and _FIT_ORDER.index(on_card) < _FIT_ORDER.index(plain):
        return "gpu"
    if on_card == "fits":
        return None  # runs on the card: free system memory is not the limit
    if free_gb is not None and plain == "fits" and need_gb > free_gb * TIGHT_BELOW:
        return "low_free"
    return None


def fit_for(
    need_gb: float | None, total_gb: float | None, free_gb: float | None = None, vram_gb: float | None = None
) -> str:
    """``fits``, ``tight``, ``too_big``, or ``unknown`` when either number is.

    The share of the computer's memory decides. Video memory that holds the
    model more comfortably wins (it runs on the card), and memory that is free
    only right now (``free_gb``) can take a Fits down to Tight, never further:
    other programs come and go, the total does not.
    """
    if need_gb is None or not total_gb:
        return "unknown"
    reason = fit_reason(need_gb, total_gb, free_gb, vram_gb)
    if reason == "gpu":
        return _share_fit(need_gb, vram_gb)  # type: ignore[arg-type]
    return "tight" if reason == "low_free" else _share_fit(need_gb, total_gb)


def decorate(
    kind: str,
    entry: dict,
    total_gb: float | None,
    free_gb: float | None = None,
    vram_gb: float | None = None,
    loaded: bool = False,
) -> dict:
    """The catalogue entry plus what the card shows.

    ``loaded``: Ollama holds this model in memory now, so the memory it asks
    for is already taken out of ``free_gb`` and must not count against it.
    """
    need = ram_needed_gb(entry)
    free = None if loaded else free_gb
    return {
        **entry,
        "kind": kind,
        "purpose_key": PURPOSE_OF_KIND.get(kind, kind),
        "ram_gb": need,
        "good_for": good_for(kind, entry),
        "recommended": RECOMMENDED.get(kind) == entry["name"],
        "fit": fit_for(need, total_gb, free, vram_gb),
        "fit_reason": fit_reason(need, total_gb, free, vram_gb),
    }


#: What an installed model may be set to, by its kind. A vision model reads
#: pictures, reads the text in them and still chats; an OCR model only reads
#: text; an embedding model only turns text into numbers for search.
USES_OF_KIND = {
    "embedding": ["embeddings"],
    "vision": ["vision", "ocr", "chat"],
    "ocr": ["ocr"],
    "text": ["chat"],
}
_EMBED_NAME = re.compile(r"embed|minilm|\bbge-|\be5-|\bgte-", re.I)
_OCR_NAME = re.compile(r"ocr", re.I)
_VISION_NAME = re.compile(r"vision|llava|moondream|minicpm-v|[-.]vl\b|\dvl\b|-vl[-:]", re.I)
_VISION_FAMILIES = {"clip", "mllama", "siglip", "qwen2vl", "qwen25vl", "qwen3vl"}


def installed_uses(entry: dict) -> list[str]:
    """What the installed model card offers to use a model for (op4-1005's
    found-not-fixed: every installed model was offered chat, images and
    reading text, so an embedding model said "Use for chat" and never "Use
    for search"). The catalogue's own kind first, by name with or without
    `:latest`; then Ollama's `details` (a `bert` family embeds, a `clip`
    projector sees); then the name, which is all an OpenAI-dialect server
    gives; a model nothing marks is a chat model."""
    from tessellate.ai.model_manager import SUGGESTED_MODELS

    name = str(entry.get("name") or "")
    bare = name.removesuffix(":latest")
    for kind, models in SUGGESTED_MODELS.items():
        if any(m["name"] in (name, bare) for m in models):
            return list(USES_OF_KIND.get(kind, ["chat"]))
    details = entry.get("details") or {}
    families = {str(f).lower() for f in (details.get("families") or [])}
    families.add(str(details.get("family") or "").lower())
    if any("bert" in f for f in families) or _EMBED_NAME.search(name):
        return list(USES_OF_KIND["embedding"])
    if _OCR_NAME.search(name):
        return list(USES_OF_KIND["ocr"])
    if families & _VISION_FAMILIES or _VISION_NAME.search(name):
        return list(USES_OF_KIND["vision"])
    return list(USES_OF_KIND["text"])


# --- "Download another model" -----------------------------------------------------

_PART = r"[a-z0-9][a-z0-9._-]*"
_OLLAMA = re.compile(rf"^(?:(?P<ns>{_PART})/)?(?P<model>{_PART})(?::(?P<tag>[A-Za-z0-9][A-Za-z0-9._-]*))?$")
_HF_PART = r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}"
_HF = re.compile(rf"^(?:hf\.co|huggingface\.co)/(?P<owner>{_HF_PART})/(?P<repo>{_HF_PART})(?::(?P<quant>[A-Za-z0-9_.-]+))?$")
_HF_URL = re.compile(
    rf"^https?://(?:www\.)?(?:huggingface\.co|hf\.co)/(?P<owner>{_HF_PART})/(?P<repo>{_HF_PART})"
    r"(?:/(?:tree|blob|resolve)/[^/\s]+(?:/(?P<file>[^\s?#]+))?)?/?(?:[?#]\S*)?$"
)
#: A quantisation tag as it sits in a GGUF file name (``Qwen3-4B-Q4_K_M.gguf``).
#: Bounded (a quantisation suffix is a few characters, "Q4_K_M"): an open
#: `+` before the look-ahead let `search` re-scan a long run of "q0_q0_..."
#: from every start, which CodeQL flagged as polynomial on a pasted name.
_QUANT = re.compile(r"(?<![A-Za-z0-9])(IQ\d_[A-Z0-9_]{1,8}|Q\d_[A-Z0-9_]{1,8}|BF16|F16|F32)(?![A-Za-z0-9])", re.IGNORECASE)

MAX_NAME = 200


def _bad(message: str) -> dict:
    return {"valid": False, "error": message}


def inspect_model_name(raw: str) -> dict:
    """What a typed model name is, or why Ollama could not pull it.

    Returns ``{"valid": True, "name", "source", "title", "detail", "warnings"}``
    (``name`` is what to pass to Ollama, normalised) or ``{"valid": False,
    "error"}``. Never touches the network: a name that is well formed but does
    not exist is found out by Ollama when the download starts, and the card
    shows its answer.
    """
    text = (raw or "").strip()
    if not text:
        return _bad("Type a model name, for example qwen2.5:3b.")
    if len(text) > MAX_NAME:
        return _bad("That name is too long to be a model.")
    if re.search(r"\s", text):
        return _bad("A model name has no spaces. Paste just the name or the repository link.")
    if ".." in text or text.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", text):
        return _bad("That looks like a file path. Ollama downloads by name; for a Hugging Face model paste its repository link.")

    warnings: list[str] = []

    url = _HF_URL.match(text)
    if url:
        owner, repo, file = url.group("owner"), url.group("repo"), url.group("file")
        quant = None
        if file:
            if not file.lower().endswith(".gguf"):
                return _bad("That link points at a file that is not a .gguf model. Paste the repository link instead.")
            found = _QUANT.search(file)
            if found:
                quant = found.group(1).upper()
            else:
                warnings.append("The file name does not say its quantisation, so Ollama will choose one from the repository.")
        text = f"hf.co/{owner}/{repo}" + (f":{quant}" if quant else "")

    if text.lower().endswith(".gguf") and "/" not in text:
        return _bad("That is a model file. Ollama needs the repository it lives in: paste the Hugging Face link or hf.co/owner/name.")

    hf = _HF.match(text)
    if not hf and re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9_.-]+)?$", text) and "gguf" in text.lower().split(":")[0]:
        #: ``owner/repo-GGUF`` with no host: a Hugging Face repository, read as one.
        hf = _HF.match("hf.co/" + text)
        warnings.append("Read as a Hugging Face repository, because the name says GGUF.")
    if hf:
        owner, repo, quant = hf.group("owner"), hf.group("repo"), hf.group("quant")
        name = f"hf.co/{owner}/{repo}" + (f":{quant}" if quant else "")
        if "gguf" not in repo.lower():
            warnings.append("Ollama can only download repositories that hold GGUF files. If this one does not, the download will fail.")
        where = f"the {quant} file" if quant else "the repository's default file"
        return {
            "valid": True,
            "name": name,
            "source": "huggingface",
            "title": f"Hugging Face model {owner}/{repo}",
            "detail": f"Ollama downloads {where} from huggingface.co. The size is not known until the download starts.",
            "warnings": warnings,
        }

    lowered = text.lower()
    if lowered != text:
        warnings.append("Written in lower case, which is how Ollama names models.")
    if re.match(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?::\d+)?/", lowered):
        return _bad("Only models from ollama.com and Hugging Face can be downloaded here. Leave the registry address off.")
    ollama = _OLLAMA.match(lowered)
    if not ollama:
        return _bad("That is not a model name Ollama understands. Names look like qwen2.5:3b, or user/model:tag.")
    ns, model, tag = ollama.group("ns"), ollama.group("model"), ollama.group("tag")
    if ns:
        title = f"Community model {ns}/{model} on ollama.com"
        detail = "Published by a person or group rather than in Ollama's own library, so it is worth knowing who made it."
    else:
        title = f"Ollama library model {model}"
        detail = "From ollama.com's own library."
    detail += f" Tag {tag}." if tag else " No tag given, so the library's default size (latest)."
    detail += " The size is not known until the download starts."
    return {
        "valid": True,
        "name": lowered,
        "source": "ollama",
        "title": title,
        "detail": detail,
        "warnings": warnings,
    }
