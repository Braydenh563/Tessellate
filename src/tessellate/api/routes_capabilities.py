"""`GET /capabilities`: what this install can do, asked once (WORLD_CLASS_PLAN B7).

The question every optional feature asks before it draws itself is "is the
thing behind me here": a transcriber for the microphone button, Tesseract for
"read the text in this image", markitdown for the Office importer, a local
embedding model for "find by meaning". Each used to be answered by its own
status route, or by trying and showing the error, so a button could appear
and then fail on its first press. This is the one answer, cheap enough for the
page to read once at unlock: every field is a look at the disk or at a saved
preference, never a request to a model server and never an import of the
package it asks about (`importlib.util.find_spec` finds without loading, which
matters for a 700 MB ML stack).

*Installed*, not *running*. Whether the model server answers right now is
`/models/status`'s question, polled because it changes; what is installed
changes when the person installs something, which restarts nothing but is
rare enough that a reload is the right way to see it.
"""

from __future__ import annotations

import importlib.util

from fastapi import APIRouter

from tessellate import __version__
from tessellate.api import paging
from tessellate.core import deps

router = APIRouter(tags=["system"])

#: The versioned contract's prefix (H4); `api/versioning.py` serves it.
API_PREFIX = "/api/v1"
API_VERSION = 1


def _mcp() -> dict:
    """The stdio MCP server, as far as this install can run it.

    A source checkout runs `python -m tessellate.mcp_server`. The packaged app
    cannot (its exe is the interpreter and takes only its own flags), so it
    answers with its own `--mcp` flag instead of a Python command it does not
    have; the earlier answer, "installed" with the Python command, made an
    outside client set up from it fail to start."""
    import sys

    from tessellate.core.config import resolved_data_dir

    #: The snippet an outside client's config takes (Settings, Tools it can
    #: use): this interpreter, because the client's own `python` rarely has the
    #: app's packages, and this notebook's folder, so it opens the same notes.
    env = {"TESSELLATE_DATA_DIR": str(resolved_data_dir())}
    if getattr(sys, "frozen", False):
        return {
            "installed": True,
            "command": "Tessellate --mcp",
            "config": {"command": sys.executable, "args": ["--mcp"], "env": env},
        }
    return {
        "installed": True,
        "command": "python -m tessellate.mcp_server",
        "config": {
            "command": sys.executable,
            "args": ["-m", "tessellate.mcp_server"],
            "env": env,
        },
    }


def _installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


@router.get("/capabilities")
def capabilities() -> dict:
    from tessellate.ai import voice
    from tessellate.core import netbind, ocr
    from tessellate.entry import importer

    config = deps.get_config()
    from tessellate.core import embedmodels

    backend = embedmodels.backend_name(config.get_preference("embedding_backend", embedmodels.BUILTIN_BACKEND))
    return {
        "version": __version__,
        "api": {
            "version": API_VERSION,
            "prefix": API_PREFIX,
            # How a client walks a list and guards a write, said rather than
            # left for it to discover from one route's headers.
            "next_cursor_header": paging.NEXT_CURSOR,
            "etag_on": ["/entries/{id}"],
            "if_match_on": ["PUT /entries/{id}", "DELETE /entries/{id}"],
            # The header an outside agent names itself in, so the change it
            # makes is filed under its name in the activity panel (H4).
            "agent_header": "X-MemoryMap-Agent",
        },
        "features": {
            # A local model for meaning (the fastembed backend) is an
            # optional install; the Ollama backend needs only the server.
            "embeddings": {
                "backend": backend,
                "installed": backend == "ollama" or _installed("fastembed"),
            },
            "voice": {"installed": voice.whisper_available()},
            "ocr": {
                # A local engine on the server (Tesseract, or RapidOCR where
                # Tesseract is not ready; the key keeps its old name, which is
                # the local reader's id). The browser's own reader and a
                # vision model are the fallbacks, which is why `ocr` alone is
                # never a reason to hide "read the text".
                "tesseract": ocr.local_available(),
                "engine": ocr.engine(),
            },
            "office_import": {"installed": importer.markitdown_available()},
            # Read aloud is the browser's speech synthesis: nothing to install
            # on this side, said so the page does not go looking for it.
            "tts": {"engine": "browser"},
            "mcp": _mcp(),
            "lan": {"enabled": bool(netbind.lan_enabled(config))},
            "user_skills_folder": {"installed": True},
        },
    }
