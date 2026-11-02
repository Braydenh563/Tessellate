"""The privacy receipt: what left this machine, read from the app's own record.

WORLD_CLASS_PLAN §2 standout 5 ("a page that proves, from the app's own
logs, that nothing left the machine; hosted competitors cannot ship this")
and §12 S6's second half ("show the configured URL in the privacy
receipt"). The record is `core/egress.py`'s audit hook, which sees every
connection and every name lookup this process makes; this route reads it,
adds the ledger kept across launches, and says in plain words the two things
the hook cannot see: the model server and a SearXNG are other programs.

Read-only apart from the ledger flush, and behind the unlock like every
data route: which hosts a notebook has talked to is itself private.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from tessellate.core import egress, netbind, qrsvg, security
from tessellate.core.config import ConfigManager
from tessellate.core.deps import DEFAULT_BASE_URLS, get_config

router = APIRouter(prefix="/privacy", tags=["privacy"])

#: The switches that let the app itself reach past this computer, in the
#: order Settings shows them. `on` is read live; `reaches` is what a person
#: would want to know before turning one on.
_SWITCHES = (
    ("web_search_enabled", "Web search", "The search engine you chose, with the words you searched for, and a page you clip, when you clip it."),
    ("update_check_enabled", "Check for updates", "GitHub's releases page, with nothing about your notebook."),
    ("auto_update_enabled", "Pull new code at start", "GitHub, to fetch the latest code when a launcher copy starts."),
    ("searxng_autostart", "Start SearXNG with the app", "Only this computer, until a search is made."),
)

_COVERS = (
    "Every connection and name lookup this app's own process made since it "
    "started, recorded by the interpreter itself, so no code path can skip it. "
    "Your model server (Ollama, LM Studio, llama.cpp) and SearXNG are separate "
    "programs with their own connections, which this receipt cannot see; their "
    "addresses are shown instead."
)

_SCOPE_WORDS = {
    "this_computer": "this computer",
    "local_network": "a device on your network",
    "internet": "the internet",
}


def _model_server(config: ConfigManager) -> dict:
    provider = str(config.get_preference("llm_provider", "ollama") or "ollama").lower()
    configured = str(config.get_preference("llm_base_url", "") or "").strip()
    default = DEFAULT_BASE_URLS["openai"] if provider == "openai" else config.ollama_url
    url = configured or default
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        port = parts.port
    except ValueError:
        host, port = "", None
    scope = egress.scope_of(host) if host else "this_computer"
    where = _SCOPE_WORDS[scope]
    if scope == "this_computer":
        note = "Your notes are read by a model on this computer."
    else:
        note = (
            f"Your notes are sent to the model server at {host}"
            f"{':' + str(port) if port else ''}, which is {where}, each time the AI reads them."
        )
    return {
        "provider": provider,
        "url": security.without_userinfo(url),  # never a typed password (SEC-12)
        "host": host,
        "port": port,
        "scope": scope,
        "local_only_ai": bool(config.get_preference("local_only_ai", True)),
        "note": note,
    }


def _label(rows: list[dict], model: dict) -> list[dict]:
    """Say which destination is the model server: expected, but named."""
    for row in rows:
        matches_host = model["host"] and model["host"] in (row["host"], row.get("name"))
        matches_port = row["kind"] == "lookup" or model["port"] in (None, row["port"])
        if matches_host and matches_port:
            row["role"] = "model server"
        else:
            row["role"] = row.get("feature") or "unattributed"
    return rows


@router.get("/verdict")
def verdict() -> dict:
    """The top bar's Local chip (row 1641): this launch's one-word answer,
    the receipt's own `verdict`, without the ledger flush and the lists the
    receipt builds, because the chip asks every few minutes."""
    return {"verdict": egress.verdict(egress.totals()), "watching": egress.installed()}


@router.get("/receipt")
def receipt(config: ConfigManager = Depends(get_config)) -> dict:
    ledger = egress.flush(config.data_dir / egress.LEDGER_NAME)
    model = _model_server(config)
    counts = egress.totals()
    ledger_totals = ledger.get("totals", {})
    return {
        "watching": egress.installed(),
        "watching_since": egress.since(),
        "verdict": egress.verdict(counts),
        "totals": counts,
        "destinations": _label(egress.destinations(), model),
        "recent": egress.recent(),
        "ledger": {
            "since": ledger.get("since"),
            "verdict": egress.verdict(ledger_totals),
            "totals": ledger_totals,
            "destinations": _label([dict(r) for r in ledger.get("destinations", [])], model),
        },
        "model_server": model,
        "listening": netbind.describe(config),
        "switches": [
            {"key": key, "label": label, "on": bool(config.get_preference(key, False)), "reaches": reaches}
            for key, label, reaches in _SWITCHES
        ],
        "covers": _COVERS,
    }


@router.get("/lan-qr.svg")
def lan_qr(
    request: Request,
    address: str = Query(min_length=1, max_length=200),
    config: ConfigManager = Depends(get_config),
) -> Response:
    """**The address as a QR code**, for the phone's camera (WORLD_CLASS_PLAN
    "Placed from Brief 40" fix 2). Only an address this notebook itself
    shows (`netbind.describe`, the same list Settings and the receipt draw),
    so the route draws nothing a caller chose. SVG, black on white."""
    shown = netbind.describe(config, request.url.port).get("addresses") or []
    if address not in shown:
        raise HTTPException(status_code=404, detail="That is not an address this notebook shows.")
    return Response(qrsvg.svg(address), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
