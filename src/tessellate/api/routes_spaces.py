import re

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from tessellate.api.schemas import SpaceResponse, SpaceCreate, SpaceUpdate
from tessellate.core import deps, paths, spacelock, vault
from tessellate.core.database import Entry, Space
from tessellate.core.database import impersonate_workspace
from tessellate.core.deps import get_session
from tessellate.repo import spaces as space_repo
from tessellate.entry.cleantext import clean_name, is_blank, name_key
from sqlalchemy.orm import Session

router = APIRouter(tags=["Spaces"])

# "all" is the frontend's "show every space" sentinel and "default" is the
# fallback delete_space reassigns orphaned rows to, a user-created space
# with either id would break both, so neither can ever be created or deleted.
RESERVED_SPACE_IDS = {"all", "default"}

# Phosphor icon names only. The frontend does `class="ph " + icon` with no
# escaping, so an unvalidated icon is a CSS class injection into the page.
_ICON_RE = re.compile(r"^ph-[a-z0-9-]{1,40}$")

_MAX_NAME_LEN = 60

def _generate_space_id(name: str, session: Session) -> str:
    """Server-generated id: slugify(name), de-duplicated with a numeric
    suffix. Chosen over validating a client-supplied id because the
    reserved-sentinel and charset rules a client id would need are exactly
    the rules a generated-and-deduped slug satisfies for free."""
    base = paths.slug(name, 49, ascii_only=True, fallback="space")
    existing = space_repo.ids(session)
    candidate = base
    n = 2
    while candidate in RESERVED_SPACE_IDS or candidate in existing:
        suffix = f"-{n}"
        candidate = f"{base[: 49 - len(suffix)]}{suffix}"
        n += 1
    return candidate


def _validate_icon(icon: str) -> str:
    if not _ICON_RE.match(icon):
        raise HTTPException(400, "Pick an icon from the list.")
    return icon


_RESERVED_NAMES = frozenset({"all", "all spaces", "everything"})


def _validate_name(name: str, *, restoring: bool = False) -> str:
    name = clean_name(name)
    if is_blank(name):
        raise HTTPException(400, "A space needs a name.")
    if len(name) > _MAX_NAME_LEN:
        raise HTTPException(400, f"A space name can be at most {_MAX_NAME_LEN} characters.")
    #: "All" and "All spaces" are the switcher's everything-view: a space of
    #: that name sat beside it, reading the same (audit 1030 Y8).
    if not restoring and " ".join(name.casefold().split()) in _RESERVED_NAMES:
        raise HTTPException(400, f"\u201c{name}\u201d is the name of the view of every space. Pick another name.")
    return name


def _refuse_duplicate_name(session: Session, name: str, own_id: str | None = None) -> None:
    """Two spaces with the same name (case and spacing aside) cannot be told
    apart in the picker or the "In <space>" chips (sweep 1028b W12)."""
    wanted = name_key(name)
    for other in space_repo.all_spaces(session):
        if other.id != own_id and name_key(other.name) == wanted:
            raise HTTPException(409, f"A space called \u201c{other.name}\u201d already exists.")


@router.get("/spaces", response_model=list[SpaceResponse])
def get_spaces(session: Session = Depends(get_session)):
    return space_repo.all_spaces(session)


@router.get("/spaces/{space_id}/counts")
def space_counts(space_id: str, session: Session = Depends(get_session)):
    """What deleting this space would take with it, for the confirm dialog."""
    deps.get_or_404(session, Space, space_id, "That space could not be found.")
    return space_repo.counts(session, space_id)


@router.post("/spaces", response_model=SpaceResponse)
def create_space(space_in: SpaceCreate, session: Session = Depends(get_session)):
    # space_in.id is intentionally never read, see SpaceCreate.id's docstring.
    name = _validate_name(space_in.name)
    icon = _validate_icon(space_in.icon)
    _refuse_duplicate_name(session, name)
    space_id = _generate_space_id(name, session)
    if space_in.is_private and vault.key() is None:
        raise HTTPException(status_code=423, detail="Unlock your private notes first.")
    space = Space(id=space_id, name=name, icon=icon, is_private=space_in.is_private)
    session.add(space)
    session.commit()
    session.refresh(space)
    return space


@router.put("/spaces/{space_id}", response_model=SpaceResponse)
def update_space(space_id: str, space_in: SpaceUpdate, session: Session = Depends(get_session)):
    space = deps.get_or_404(session, Space, space_id, "That space could not be found.")
    # Only fields the caller actually sent are applied, so an omitted field
    # doesn't get overwritten with None (SpaceUpdate's fields are optional).
    provided = space_in.model_dump(exclude_unset=True)
    if "name" in provided:
        space.name = _validate_name(provided["name"])
        _refuse_duplicate_name(session, space.name, space.id)
    if "icon" in provided:
        space.icon = _validate_icon(provided["icon"])
    if "hidden_from_all" in provided:
        # "default" is where a deleted space's notes land, so hiding it would
        # quietly empty the everything-view of anything that ever fell back
        # to it: refused for the same reason it cannot be deleted.
        if space.id == "default" and provided["hidden_from_all"]:
            raise HTTPException(
                status_code=400,
                detail="The default space cannot be hidden from All spaces.",
            )
        space.hidden_from_all = bool(provided["hidden_from_all"])
    session.commit()
    session.refresh(space)
    return space


def _move_space_contents(session: Session, source: str, target: str) -> dict:
    """Every row of `source` becomes `target`'s (see `repo.spaces.move_contents`)."""
    manifest = space_repo.move_contents(session, source, target)
    # These statements move notes round the ORM, so `updated_at` stays put
    # and the filing corpus's diff would not see them (`lexical_filing`).
    from tessellate.ai import lexical_filing

    lexical_filing.forget_corpus()
    return manifest


class SpaceRestore(BaseModel):
    """What a space's delete answered with, sent back by Undo (undo-1005)."""

    space: SpaceResponse
    move_to: str | None = None
    moved: dict[str, list[int]] = Field(default_factory=dict)
    merged: list[dict] = Field(default_factory=list)
    #: Notes the space itself had sealed, so Undo marks them so again (L-world-class-842).
    sealed_notes: list[int] = Field(default_factory=list)


def _refuse_locked_private(private: bool, token: str | None) -> None:
    """INBOX 1727: a private space is deleted or brought back only while its
    session has them open, so nothing in it is moved or remade unsealed."""
    if private and not spacelock.opened(token):
        raise HTTPException(status_code=423, detail="Unlock your private spaces first.")


@router.post("/spaces/restore", response_model=SpaceResponse)
def restore_space(
    body: SpaceRestore, session: Session = Depends(get_session), x_auth_token: str | None = Header(default=None)
):
    """Undo a space's delete: the space again, with its own id, and every row
    the delete moved out of it moved back (a row moved on since stays where
    it is now). A merged category is made again with its id and its notes
    pointed back at it. A delete that took the contents with it answers with
    no restore at all, so it never reaches here."""
    sid = body.space.id
    if sid in RESERVED_SPACE_IDS:
        raise HTTPException(400, "The default spaces cannot be made again.")
    if space_repo.find(session, sid) is not None:
        raise HTTPException(409, "A space with that id already exists.")
    _refuse_locked_private(bool(body.space.is_private), x_auth_token)
    #: Checked, but stored as it was: an undo never renames the space.
    _validate_name(body.space.name, restoring=True)
    name = body.space.name
    icon = _validate_icon(body.space.icon)
    session.add(Space(id=sid, name=name, icon=icon, hidden_from_all=bool(body.space.hidden_from_all), is_private=bool(body.space.is_private)))
    session.flush()
    if body.move_to:
        _move_back(session, body, sid)
    if body.space.is_private:
        _seal_restored(session, sid, body.sealed_notes)
    session.commit()
    if body.space.is_private:
        from tessellate.entry import manager_private

        manager_private.scrub_private_leftovers(session)
    return space_repo.find(session, sid)


def _move_back(session: Session, body: SpaceRestore, sid: str) -> None:
    """Every row the delete moved out, moved back, and each merged category made again."""
    space_repo.move_back(session, body.merged, body.moved, body.move_to, sid)
    from tessellate.ai import lexical_filing
    from tessellate.search import index as search_index

    search_index.rebuild(session)
    # Moved back by statement, so the filing corpus must forget too.
    lexical_filing.forget_corpus()


def _seal_restored(session: Session, sid: str, sealed_notes: list[int] | None = None) -> None:
    """Whatever came back into a private space is sealed again, a note made
    ordinary since the delete included: a restore never lands one in the clear."""
    from tessellate.entry import private_space

    session.expire_all()  # moved back by statement: read them as they are now
    private_space.seal_space_members(session, sid)
    private_space.mark_sealed_by_space(session, sid, sealed_notes or [])


class SpaceDeleted(SpaceResponse):
    #: What Undo sends back to `POST /spaces/restore`; null when the delete
    #: took the space's contents with it, which has no way back.
    restore: dict | None = None


def _delete_space_moving(session: Session, space: Space, move_to: str) -> SpaceDeleted:
    """Delete a space after moving everything in it to another one."""
    space_id = space.id
    if move_to == space_id:
        raise HTTPException(400, "Pick a different space to move its contents to.")
    target = deps.get_or_404(session, Space, move_to, "The space to move to could not be found.")
    response = SpaceResponse.model_validate(space)
    forgotten: list[int] = []
    if space.is_private and not target.is_private:
        from tessellate.entry import private_space

        private_space.unseal_space_files(session, space_id)
        forgotten = private_space.forget_sealed_by_space(session, space_id)
    manifest = _move_space_contents(session, space_id, move_to)
    session.delete(space)
    session.commit()
    from tessellate.search import index as search_index

    # Every moved row's index entry still names the old space.
    search_index.rebuild(session)
    session.commit()
    return SpaceDeleted(
        **response.model_dump(),
        restore={"space": response.model_dump(), "move_to": move_to, **manifest, "sealed_notes": forgotten},
    )


def _purge_collect(session: Session, space_id: str) -> tuple[dict[str, list], list]:
    """The ids of what a purge takes, and the files on disk it unlinks after
    the commit. Read with the space's bin included: a binned document or
    reminder is hidden from every ordinary read."""
    config = deps.get_config()
    attachments, uploads, ids = space_repo.purge_sources(session, space_id)
    files = [config.uploads_dir / a.stored_name for a in attachments]
    files += [config.data_dir / "media" / u.filename for u in uploads]
    return ids, files


def _purge_forget_index(session: Session, ids: dict[str, list]) -> None:
    """Every delete below is a query-level statement, which the search index's
    flush hook never sees; without this the space's notes, documents and
    reminders stayed findable from All spaces after the space itself was gone
    (measured, tests/test_search_engine.py)."""
    from tessellate.core.database import (
        Attachment, Bookmark, Document, MediaUpload, Reminder,
    )
    from tessellate.search import index as search_index

    for model, key in (
        (Attachment, "attachment"), (MediaUpload, "upload"), (Document, "document"),
        (Entry, "entry"), (Bookmark, "bookmark"), (Reminder, "reminder"),
    ):
        search_index.forget(session, model, ids[key])



def _purge_space(session: Session, space: Space) -> SpaceDeleted:
    """**Deleting a space deletes what was in it** (owner: "make sure that if
    a specific space is deleted too, that all the content including notes
    files and images etc originating in that specific space get deleted with
    it as well"). Only on request (`purge=1`, audit 1031 Z20).

    impersonate_workspace(..., "all") disables the session's ambient workspace
    filter for this block: a request carrying X-Workspace-ID for some *other*
    space would otherwise AND that id into every DELETE, so deleting
    "personal" while browsing "work" would remove nothing. Files on disk are
    unlinked after the commit: a row that is gone and a file that is still
    there is recoverable; the reverse is not."""
    from tessellate.entry import bin as other_bin

    space_id = space.id
    # Capture the response body before deleting: reading attributes off an
    # instance after session.delete()+commit() raises ObjectDeletedError.
    body = SpaceResponse.model_validate(space).model_dump()
    # An empty space has nothing to lose, so its delete can be undone; one
    # with contents deletes them for good (files on disk included).
    restorable = not space_repo.has_rows(session, space_id)
    response = SpaceDeleted(**body, restore={"space": body} if restorable else None)
    with impersonate_workspace(session, "all"), other_bin.including_binned(session):
        ids, to_unlink = _purge_collect(session, space_id)
        _purge_forget_index(session, ids)
        space_repo.purge_side_tables(session, ids)
        space_repo.purge_rows(session, space_id, ids["category"])
    session.delete(space)
    session.commit()
    for path in to_unlink:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass  # the row is gone; a stray file is the recoverable failure
    return response


@router.delete("/spaces/{space_id}", response_model=SpaceDeleted)
def delete_space(
    space_id: str,
    move_to: str | None = None,
    purge: bool = False,
    session: Session = Depends(get_session),
    x_auth_token: str | None = Header(default=None),
):
    """Delete a space and move everything in it to `move_to` (the default
    space when it is not given), or, with `purge=1`, delete everything in it
    for good (owner, 0.3.31: "the option to delete all its contents, and the
    other to move its contents to a different space"). The purge is explicit
    (audit 1031 Z20): a client that forgets the parameter cannot destroy."""
    if space_id in RESERVED_SPACE_IDS:
        raise HTTPException(400, "The default spaces cannot be deleted.")
    space = deps.get_or_404(session, Space, space_id, "That space could not be found.")
    _refuse_locked_private(bool(space.is_private), x_auth_token)
    if purge and move_to:
        raise HTTPException(400, "Choose either moving the contents or deleting them, not both.")
    if purge:
        return _purge_space(session, space)
    return _delete_space_moving(session, space, move_to or "default")


class MoveNotesBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    #: Out of a private space (INBOX 1727): "Keep it private" (the default)
    #: or "Make it ordinary".
    keep_private: bool = True


@router.post("/spaces/{space_id}/move-notes")
def move_notes_to_space(space_id: str, body: MoveNotesBody, session: Session = Depends(get_session)) -> dict:
    """Move these notes into one space (WORLD_CLASS_PLAN 5 item 5, section 8
    row 30; INBOX 1's "a Move to space bulk action").

    Only notes the request can see move: the ambient space filter reads them,
    so a selection made in one space cannot reach into another. A note keeps
    its category's *name*: categories are per space, so the target's category
    of that name is used, made when it has none. What hangs off the note in
    its old space comes with it (its files, its reminders, its fade score),
    and so do links whose both ends moved; a link to a note left behind stays
    where it was, as a space's delete leaves one. `from` is each note's old
    space, which is what an Undo sends back.
    """
    from tessellate.entry import moving

    if space_id == "all":
        raise HTTPException(400, "Pick one space to move them to.")
    from tessellate.entry import private_space
    from tessellate.entry import manager_private

    target = deps.get_or_404(session, Space, space_id, "That space could not be found.")
    # A locked private space's notes are out of this read, so only the target can be locked here.
    if target.is_private and session.info.get("sealed_workspaces"):
        raise HTTPException(status_code=423, detail="Unlock your private spaces first.")
    leaving = private_space.leaving_ids(session, space_id, body.ids)
    moved = moving.to_space(session, space_id, body.ids)
    if leaving:
        private_space.after_leaving(session, leaving, keep_private=body.keep_private)
        session.commit()
    if target.is_private and moved.get("moved"):
        manager_private.scrub_private_leftovers(session)
    return moved
