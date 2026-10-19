"""`GET /statistics`: the Statistics page in one call (UI_MODERNISATION
statistics rows 1 and 2).

The notebook's counts, the reminders', this week against last, and the
usage ledger's rows, all counted from rows by `ai/notebook_stats.page` with
no model. The week is the person's own (`user_now`), so the week starts on
their day (Settings, or the locale). Nothing is cached: every count is one aggregate query, and a cache
would need an event from every write to stay true.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.ai import notebook_stats, stats_ask
from tessellate.core import deps, usage
from tessellate.core.config import user_now, week_first_day
from tessellate.core.deps import get_session

router = APIRouter(tags=["statistics"])


@router.get("/statistics")
def statistics(
    #: The growth chart's range (the page's 3 months, 1 year, all control).
    growth: str = Query("12", pattern="^(3|12|all)$"),
    session: Session = Depends(get_session),
) -> dict:
    config = deps.get_config()
    return notebook_stats.page(session, user_now(config), usage.summary(config.data_dir, []), week_first_day(config), growth)


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=300)


@router.post("/statistics/ask")
def ask_statistics(body: AskBody, session: Session = Depends(get_session)) -> dict:
    """"Ask about your statistics": counted sentences, no model (ai/stats_ask.py)."""
    config = deps.get_config()
    done = stats_ask.ask(body.question, session, user_now(config), usage.summary(config.data_dir, []), week_first_day(config))
    return {"kind": done.kind, "text": done.text, "facts": done.facts}
