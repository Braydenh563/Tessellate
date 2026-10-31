"""Pydantic request/response shapes shared by the API routes."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from tessellate.entry.cleantext import is_blank
from tessellate.entry.tagnames import normalise_tags


def not_blank(value: str | None, what: str = "note") -> str | None:
    """Refuse text that holds nothing a reader can see: spaces, line breaks and
    zero-width characters alone. The text itself is kept as sent."""
    if value is not None and is_blank(value):
        raise ValueError(f"That {what} is blank. Write something first.")
    return value



class SpaceCreate(BaseModel):
    # `id` is accepted for backward compatibility with older frontend
    # payloads but is always ignored, the server slugifies `name` instead
    # (routes_spaces.create_space). A client-chosen id was how "all" and
    # "default" could be created and break the reserved sentinels, so the
    # server no longer trusts it at all rather than merely validating it.
    id: str | None = None
    name: str = Field(min_length=1)
    icon: str = Field(min_length=1, default="ph-circles-four")

class SpaceUpdate(BaseModel):
    # Optional: update_space only writes fields the caller actually sent,
    # so omitting one (e.g. renaming without touching the icon) can't
    # blank out the other with None (see routes_spaces.update_space).
    name: str | None = Field(default=None, min_length=1)
    icon: str | None = Field(default=None, min_length=1)
    #: None means "leave as it is", the same convention as the two above.
    hidden_from_all: bool | None = None

class SpaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    icon: str
    #: True when this space's contents are kept out of "All spaces".
    hidden_from_all: bool = False

#: The longest a note may be, and the longest a tag may be.
#:
#: Measured 2026-09-12: a 5 MB note was accepted and took 2.26 s of blocking
#: handler time, while a 5 MB *document* was refused, because
#: `routes_documents` has had `MAX_CONTENT` since it was written and capture
#: never grew one. The same app said yes and no to the same paste depending
#: on which box it went in. This is that number, not a new opinion about how
#: long a note may be: 500,000 characters is a hundred times the longest note
#: anyone writes and a tenth of what hurt.
#:
#: The tag length cap is `entry/tagnames.MAX_TAG_LENGTH`,
#: beside the rest of the rule for what a tag may be.
MAX_NOTE_CONTENT = 500_000


#: The swatch keys a note's colour may be (INBOX 1479): the ones the category
#: picker draws (`routes_categories.CATEGORY_PALETTE_KEYS`, which a test keeps
#: equal), so one palette serves both.
NOTE_COLOURS = (
    "red", "orange", "amber", "lime", "green", "teal",
    "cyan", "blue", "indigo", "violet", "magenta", "pink",
)


def known_note_colour(value: str | None) -> str | None:
    if value is not None and value not in NOTE_COLOURS:
        raise ValueError("Pick one of the colour swatches")
    return value


class EntryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_NOTE_CONTENT, description="The thought to store")
    tags: list[str] = Field(default_factory=list, max_length=200)
    #: GRAPH_PLAN KG4: a note type's name; its fields are written at the top.
    note_type: str | None = Field(default=None, max_length=60)

    @field_validator("content")
    @classmethod
    def _content_is_not_blank(cls, content: str) -> str:
        return not_blank(content)

    @field_validator("tags")
    @classmethod
    def _tags_are_labels(cls, tags: list[str]) -> list[str]:
        """A tag is a label: clipped, blank-free, each once whatever its case.

        The whole rule is `entry/tagnames.normalise_tags`, shared with the
        manager so a tag written by the AI or a rename obeys the same one.
        Blank ones drop out, which is what a trailing comma produces.
        """
        return normalise_tags(tags)
    # Guided mode: the user picks the category up front and
    # the AI janitor is skipped entirely.
    category: str | None = None
    # Train-of-thought: continue an existing entry.
    parent_id: int | None = None
    # Documents this note belongs with, attached as it is saved. Asked for
    # directly: "a way to link documents to new notes I create in the capture
    # tab". Doing it on create rather than afterwards is the point, the
    # connection is obvious while you are writing and forgotten by the time
    # the note is in a list.
    document_ids: list[int] = Field(default_factory=list, max_length=10)
    # A note captured from the text-selection popup, not yet reviewed.
    is_draft: bool = False
    #: Made by a map gesture (`Entry.map_topic`): kept out of Notes and
    #: Recently added, found by search like any note.
    map_topic: bool = False
    # Where a web-reader clipping came from (BACKLOG §65): real metadata,
    # not parsed back out of the markdown blockquote `saveSelectionAsNote`
    # (app.js) still writes into `content` for portability. Both optional
    # and independent: a source without a title still renders (falls back
    # to the URL), the same as the frontend's own `clippingMarkdown` already
    # falls back.
    #: http(s) only (SEC-15, audit 2026-10-05): the card opens it, and a
    #: `javascript:` address would be one click from running in the app.
    source_url: str | None = Field(default=None, max_length=2000, pattern=r"^[Hh][Tt][Tt][Pp][Ss]?://")
    source_title: str | None = Field(default=None, max_length=300)
    #: Save now, decide the category later on a background thread.
    #:
    #: Filing asks a local model, which on a small machine is seconds, and
    #: it used to happen *inside* this request, so the composer stayed
    #: disabled behind "Filing…" for the whole of it. With this set the
    #: response comes back as soon as the note is on disk, carrying
    #: `filing_state: "pending"`; the caller polls `GET /entries/{id}/filing`
    #: (or just reloads the list) to find out where it landed.
    #:
    #: Ignored when `category` or `parent_id` decides the category anyway, 
    #: there is nothing to defer in either case.
    defer_filing: bool = False
    #: Read `#word` in the text as tags as well (INBOX 434). Opt-in, sent by
    #: the boxes a person writes a note in (Capture, Quick note, the graph's
    #: new note), never by an import or the AI, whose text is not a person
    #: labelling their own thought.
    inline_tags: bool = False
    #: The same note sent twice is saved once. The offline queue
    #: (quick-note.js) gives every note it holds a key and resends it until
    #: an answer arrives, so a save whose answer was lost on the way back
    #: (the server stopped after the commit) is answered with the note it
    #: already made rather than a second copy.
    client_key: str | None = Field(default=None, max_length=80)
    #: The note's colour from the capture card's dots (INBOX 1479).
    colour: str | None = None

    @field_validator("colour")
    @classmethod
    def _colour_is_a_swatch(cls, value: str | None) -> str | None:
        return known_note_colour(value)


class EntryUpdate(BaseModel):
    """Manual override: only provided fields change."""

    #: The same two limits `EntryCreate` carries, for the same reason. A cap
    #: that only guards the create path is not a cap: every note in the
    #: notebook can be edited, so the long paste and the 50,000-character tag
    #: just arrive through `PUT` instead. Found by asking where else the
    #: shape this was fixed in can enter.
    content: str | None = Field(default=None, min_length=1, max_length=MAX_NOTE_CONTENT)
    category: str | None = None
    tags: list[str] | None = Field(default=None, max_length=200)

    @field_validator("content")
    @classmethod
    def _content_is_not_blank(cls, content: str | None) -> str | None:
        return not_blank(content)

    @field_validator("tags")
    @classmethod
    def _tags_are_labels(cls, tags: list[str] | None) -> list[str] | None:
        if tags is None:
            return None
        return normalise_tags(tags)
    pinned: bool | None = None
    #: A swatch key to set the colour, null to clear it; left out, it stays.
    colour: str | None = None

    @field_validator("colour")
    @classmethod
    def _colour_is_a_swatch(cls, value: str | None) -> str | None:
        return known_note_colour(value)

    is_draft: bool | None = None
    #: The `content_hash` of the text this edit started from, so a save made
    #: over text another window has since changed is refused (409) rather
    #: than silently overwriting it (api/edit_conflicts.py). Optional: a
    #: writer that sends none is not checked.
    base_hash: str | None = Field(default=None, max_length=64)
    #: The text includes an Atlas suggestion the person applied before saving
    #: (Improve writing in the form): the edit is recorded as theirs and
    #: Atlas's together, so the history can say so (INBOX 446).
    ai_assisted: bool = False


class ContextBody(BaseModel):
    """Extra context appended to an existing note."""

    text: str = Field(min_length=1, max_length=10_000)


class LinkOut(BaseModel):
    link_id: int
    entry_id: int  # the entry on the other end
    preview: str  # first few words of that entry
    reason: str | None = None  # why these are connected, if anyone said or it was deduced
    # 0..1, set only when `reason` above came from embedding similarity
    # rather than from a person or the AI saying it, see EntryLink.reason_confidence.
    reason_confidence: float | None = None
    #: "out" when this note is the link's source, "in" when it is the target.
    #:
    #: `links_for_entry` has always returned both directions merged into one
    #: list, so a note could show what it was connected to but never which
    #: way round: and "this note points at that one" and "that one points at
    #: this" are different facts. Asked for by way of Kortex's own
    #: Connections block, which shows every link with an in/out arrow.
    #: Defaults to "out" so an older client (or a caller that doesn't care)
    #: reads exactly as it did before this field existed.
    direction: str = "out"
    #: GRAPH_PLAN KG3: the link's kind, what it is called from this end (its
    #: inverse name when this note is the target), and its properties.
    link_type: str | None = None
    link_label: str | None = None
    props: dict | None = None


class AttachmentOut(BaseModel):
    id: int
    filename: str
    size: int
    is_image: bool
    #: When it was attached, ISO-8601. The attachment card's facts line is
    #: kind, size and the day it came (INBOX 440 (2)); the row has always had
    #: the date, the note's payload never carried it. "" for a row without one.
    created_at: str = ""


class SimilarOut(BaseModel):
    """A near-duplicate spotted while saving."""

    id: int
    preview: str
    similarity: float


class DocumentRefOut(BaseModel):
    """Just enough of a document to name it and open it."""

    id: int
    title: str


class EntryDateOut(BaseModel):
    """A relative time phrase, and the date it resolved to.

    The phrase travels with the date on purpose: the resolution is a rule
    ("next Friday" = the Friday of next week), not a fact, and a reader can
    only disagree with it if both are visible.
    """

    phrase: str
    at: date
    precision: str = "day"
    #: "15:00" when the note said a time beside the day ("on Friday at 3pm",
    #: precision "minute"), the writer's own clock with no zone; None for a day.
    time: str | None = None


class EntryOut(BaseModel):
    id: int
    content: str
    #: The hash of `content` (api/edit_conflicts.py): an editor sends it back
    #: as `base_hash` so a save over a newer text is refused, not lost.
    content_hash: str = ""
    #: GRAPH_PLAN KG4: the `---` block at the top of the note, read, and the
    #: type it names (`type:`), if any.
    properties: dict[str, list[str]] = Field(default_factory=dict)
    note_type: str | None = None
    # A note's own leading `# Heading`, if it wrote one, not a stored,
    # separately-edited field. Editing the title is editing that line, the
    # same as editing any other line of the note; there's no second field to
    # go out of sync with the content it's supposedly titling.
    title: str | None = None
    category: str
    tags: list[str]
    ai_confidence: int
    #: Offered at filing, not yet taken or discarded (INBOX 440).
    suggested_tags: list[str] = []
    #: Each offered tag's why, the words in the note that back it
    #: (WORLD_CLASS 23, decision 5).
    suggested_tag_reasons: dict[str, str] = {}
    #: Suggestions turned down on this note, which `restore` offers again.
    discarded_tags: list[str] = []
    #: "Don't suggest tags for this note" is on (brief 89).
    tag_suggest_off: bool = False
    access_count: int = 0
    last_opened_at: datetime | None = None
    #: When a person last changed the text, title, tags or category; null if
    #: never since it was written. Sort "recently edited" by this falling back
    #: to `created_at`. See `Entry.edited_at` for why not `updated_at`.
    edited_at: datetime | None = None
    parent_id: int | None = None
    pinned: bool = False
    #: The note's own colour, a swatch key (INBOX 1479); null for none.
    colour: str | None = None
    user_filed: bool = False
    # Private notes are encrypted at rest and kept out of search and the AI.
    is_private: bool = False
    # Captured from the text-selection popup, not yet reviewed.
    is_draft: bool = False
    #: A whiteboard/concept map, which is an Entry like any other (see
    #: `Entry.is_board`). The frontend had no way to tell one from a note at
    #: all, so a board could not be offered as a link target, filtered out of
    #: a note list, or labelled as what it is, every surface either treated
    #: it as a note or hard-coded a second fetch of `/whiteboard/boards`.
    is_board: bool = False
    #: "board" or "map" for a board, None for a note (`Entry.board_kind`).
    board_kind: str | None = None
    #: A topic a map gesture made (`Entry.map_topic`, audit UX-06).
    map_topic: bool = False
    # Where a web-reader clipping came from, when it was one (BACKLOG §65).
    source_url: str | None = None
    source_title: str | None = None
    #: Where this note sat in an imported vault (`Projects/Roadmap.md`), or
    #: "" for one written here. The Contents index groups on it, and the
    #: wiki-link resolver matches its filename, see `Entry.source_path`.
    source_path: str = ""
    #: Which space this note is filed in. Added for INBOX 1a/38: notes
    #: carried this on the row (`Entry.workspace_id`) all along, but nothing
    #: sent it to the frontend, so a note card had no way to say which space
    #: it belonged to, and "notes from a deleted space appear in All spaces"
    #: could not be told apart from "the space's own notes were correctly
    #: kept, and these are unrelated notes that were always in Default
    #: Space." "default" is where a deleted space's notes land (see
    #: routes_spaces.py); it is a real row in `spaces`, not a sentinel, so
    #: the frontend can always resolve this against the spaces list it
    #: already loads for the switcher.
    workspace_id: str = "default"
    created_at: datetime
    deleted_at: datetime | None = None  # set only in the recycle-bin view
    archived_at: datetime | None = None  # set only when archived (BACKLOG §30b)
    links: list[LinkOut] = Field(default_factory=list)
    attachments: list[AttachmentOut] = Field(default_factory=list)
    # Documents this note is attached to: [{"id": 3, "title": "Trip plan"}].
    documents: list["DocumentRefOut"] = Field(default_factory=list)
    # What the note's relative time phrases meant when it was written (§10A):
    # [{"phrase": "next friday", "at": "2026-08-07", "precision": "day"}].
    dates: list["EntryDateOut"] = Field(default_factory=list)
    # How this entry was filed, only present on the create response:
    # 'semantic-match' | 'llm' | 'user' | 'thread' | 'none'
    filed_by: str | None = None
    # 'done' | 'pending' | 'failed', see Entry.filing_state. A note saved
    # with `defer_filing` comes back 'pending' and settles later.
    filing_state: str = "done"
    # Near-duplicate warning: only present on the create response.
    similar: SimilarOut | None = None
    # GRAPH_PLAN 518: on an edit that renamed the note while other notes
    # still write `[[old]]`: {"old", "new", "notes"}, for the offer to
    # rewrite them (`POST /entries/{id}/wiki-rename`).
    wiki_rename: dict | None = None
