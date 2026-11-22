"""`GET /utilities/work` and `/utilities/units`: the calculator's two calls
(INBOX 1300 C06: "an interactive calculator popup that is accessible and also
link it to the /calc command as well as other unit conversions").

The calculator works out through the chat's own `calculate` tool, which reads
through `ai/utilities.answer` and `ai/arithmetic`, so a sum typed in the popup
and the same sum asked in the chat cannot disagree. The units are the
recogniser's table, grouped by what they measure, and the dated currency table.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import tools
from tessellate.core import deps
from tessellate.core.deps import get_session

router = APIRouter(tags=["utilities"])


@router.get("/utilities/work")
def work(q: str = "", session: Session = Depends(get_session)) -> dict:
    got = tools.execute_tool(session, "calculate", {"question": q[:300]})
    return {key: got[key] for key in ("answer", "read_as", "error") if key in got}


@router.get("/utilities/units")
def units() -> dict:
    from tessellate.ai import recognise_units, utilities

    grouped: dict[str, list[str]] = {}
    for dimension, _size, said in recognise_units.UNITS.values():
        names = grouped.setdefault(dimension, [])
        if said not in names:
            names.append(said)
    grouped = {dimension: sorted(names, key=str.lower) for dimension, names in grouped.items()}
    grouped["currency"] = sorted(utilities.RATES)
    #: Places whose clocks the Convert widget and the Units tab read ("09:00 London to Tokyo"); the zone database is the machine's own, so it works offline.
    grouped["timezone"] = list(utilities.CONVERT_PLACES)
    return {**grouped, "rates_date": utilities.current_rates()[1].isoformat()}


# --- the currency table (decision 43, L519) -------------------------------------


class RatesBody(BaseModel):
    #: The day the rates were true, said with every currency answer.
    date: date
    #: Units of each currency to one US dollar; codes the built-in table has.
    rates: dict[str, float] = Field(max_length=200)


def _rates_out() -> dict:
    from tessellate.ai import utilities

    rates, when = utilities.current_rates()
    saved = deps.get_config().get_preference(utilities.RATES_PREFERENCE, None)
    return {"date": when.isoformat(), "rates": rates, "built_in": not isinstance(saved, dict)}


@router.get("/utilities/rates")
def get_rates() -> dict:
    return _rates_out()


@router.put("/utilities/rates")
def put_rates(body: RatesBody) -> dict:
    from tessellate.ai import utilities

    unknown = sorted(code for code in body.rates if code not in utilities.RATES)
    if unknown:
        raise HTTPException(422, f"Not a currency this table has: {', '.join(unknown)}.")
    bad = sorted(code for code, value in body.rates.items() if not 0 < value < 1e9)
    if bad:
        raise HTTPException(422, f"A rate must be a number above 0: {', '.join(bad)}.")
    rates = {code: value for code, value in body.rates.items() if code != "USD"}
    deps.get_config().set_preference(utilities.RATES_PREFERENCE, {"date": body.date.isoformat(), "rates": rates})
    return _rates_out()


@router.delete("/utilities/rates")
def reset_rates() -> dict:
    from tessellate.ai import utilities

    deps.get_config().unset_preference(utilities.RATES_PREFERENCE)
    return _rates_out()
