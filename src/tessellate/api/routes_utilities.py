"""`GET /utilities/work` and `/utilities/units`: the calculator's two calls
(INBOX 1300 C06: "an interactive calculator popup that is accessible and also
link it to the /calc command as well as other unit conversions").

The calculator works out through the chat's own `calculate` tool, which reads
through `ai/utilities.answer` and `ai/arithmetic`, so a sum typed in the popup
and the same sum asked in the chat cannot disagree. The units are the
recogniser's table, grouped by what they measure, and the dated currency table.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from tessellate.ai import tools
from tessellate.core.deps import get_session

router = APIRouter(tags=["utilities"])


@router.get("/utilities/work")
def work(q: str = "", session: Session = Depends(get_session)) -> dict:
    got = tools.execute_tool(session, "calculate", {"question": q[:300]})
    return {key: got[key] for key in ("answer", "read_as", "error") if key in got}


@router.get("/utilities/units")
def units() -> dict:
    from tessellate.ai import recognise, utilities

    grouped: dict[str, list[str]] = {}
    for dimension, _size, said in recognise.UNITS.values():
        names = grouped.setdefault(dimension, [])
        if said not in names:
            names.append(said)
    grouped = {dimension: sorted(names, key=str.lower) for dimension, names in grouped.items()}
    grouped["currency"] = sorted(utilities.RATES)
    return {**grouped, "rates_date": utilities.RATES_DATE.isoformat()}
