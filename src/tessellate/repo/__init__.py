"""Repositories: one module per resource, the only place its tables are queried.

Audit 1031 AR1 counted 359 ORM queries in the routers, so no one place decided
what a request may read or write, and each guard (the bin, the shelf, the
workspace) was a route-by-route bug. The pattern (INBOX 1499, designed in
`docs/roadmap/agent-remaining/audit-1031-ranked.md` row 3a):

- `repo/<resource>.py` owns its model and that model's join tables. Nothing
  under `api/` imports those models once the resource has moved
  (`tests/test_repo_boundaries.py` holds it per resource).
- Verbs are plain functions taking the request's `Session` first: `find`
  (row or None), `get` (row or `NotFound`), `page` (rows and total), then
  writes named by what they do (`create`, `update`, `delete`, `attach_to_*`).
- A repository flushes but never commits: the route owns the transaction, so
  one request that calls two verbs commits once or not at all.
- Errors are domain names (`NotFound`, `Invalid`, `Conflict`) that are also
  `HTTPException`s, so the app's one error shape answers them unchanged and a
  caller outside HTTP (the MCP server, an AI tool) catches them by name.
- The workspace and bin floors stay in `core/database.py`'s session criteria;
  a repository adds the rules that are its resource's own (a binned note is
  restored before it is edited, a private note is not read to the AI).

Routes keep validation of the request body, the response shape and the
transaction; the same test file counts the ORM calls left under `api/`,
a ratchet that only goes down.
"""

from __future__ import annotations

from fastapi import HTTPException


class NotFound(HTTPException):
    """There is no such row, or the caller may not see it (404)."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=404, detail=detail)


class Invalid(HTTPException):
    """The value can never be stored as given (422)."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=422, detail=detail)


class Conflict(HTTPException):
    """The row exists but is in a state that refuses this (409)."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=409, detail=detail)


class ReadOnly(HTTPException):
    """The row is built in and cannot be changed (400)."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=400, detail=detail)
