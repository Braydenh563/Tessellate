"""The notebook on a time axis (roadmap §10B).

Asked for repeatedly: "I want a note timeline where I can see notes visually
by what time they were made. Maybe I can even group them by events or related
places etc." The axis is time; the bands are what make it a map of what
happened rather than a sorted list.
"""

from __future__ import annotations

from datetime import timedelta

from tessellate.core.database import Entry, utcnow


def _save(client, content, **extra):
    response = client.post("/entries", json={"content": content, **extra})
    assert response.status_code == 201
    return response.json()


def _age(session, note_id: int, days: int) -> None:
    """Backdate a note, so a timeline has more than one column in it."""
    entry = session.get(Entry, note_id)
    entry.created_at = utcnow() - timedelta(days=days)
    session.commit()


def test_an_empty_notebook_is_an_empty_timeline_not_an_error(client):
    body = client.get("/timeline").json()
    assert body["rows"] == [] and body["buckets"] == []


def test_notes_land_in_buckets_on_the_scale_asked_for(client, session):
    old = _save(client, "an older thought")
    _age(session, old["id"], 40)
    _save(client, "a fresh thought")

    monthly = client.get("/timeline?scale=month").json()
    assert len(monthly["buckets"]) == 2, monthly["buckets"]
    assert all(bucket.endswith("-01") for bucket in monthly["buckets"])

    yearly = client.get("/timeline?scale=year").json()
    assert len(yearly["buckets"]) == 1  # 40 days apart is one year


def test_a_note_plots_at_what_it_is_about_not_when_it_was_typed(client, session):
    """The reason this is more than ORDER BY created_at: §10A resolved the
    relative time in note text, so "the deadline is next friday" knows which
    Friday and belongs there."""
    note = _save(client, "the deadline is next friday")
    body = client.get("/timeline?scale=day").json()
    placed = next(n for n in body["rows"] if n["id"] == note["id"])

    assert placed["placed_by"] == "mentioned"
    assert placed["phrase"] == "next friday"
    assert placed["at"] > placed["written_at"], placed
    # A note with no dates in it stays where it was written, and says so.
    plain = _save(client, "no dates in this one")
    again = client.get("/timeline?scale=day").json()
    written = next(n for n in again["rows"] if n["id"] == plain["id"])
    assert written["placed_by"] == "written" and written["phrase"] == ""


def test_bands_are_the_categories_you_actually_write_in(client, session):
    _save(client, "pasta recipe", category="Recipes")
    _save(client, "risotto recipe", category="Recipes")
    _save(client, "a work thing", category="Work")

    body = client.get("/timeline?group=category").json()
    names = [band["name"] for band in body["bands"]]
    assert names[0] == "Recipes", body["bands"]  # biggest first
    assert dict((b["name"], b["count"]) for b in body["bands"]) == {
        "Recipes": 2,
        "Work": 1,
    }


def test_bands_can_be_tags_instead(client):
    _save(client, "a note", tags=["garden"])
    _save(client, "another", tags=["garden", "spring"])
    _save(client, "bare one")

    bands = {b["name"]: b["count"] for b in client.get("/timeline?group=tag").json()["bands"]}
    assert bands["garden"] == 2
    assert bands["spring"] == 1
    assert bands["untagged"] == 1


def test_bands_can_be_threads_a_root_and_its_continuations(client):
    """§87.6: "a note with children sprouts a branch," using the thread
    structure `Entry.parent_id` already stores rather than category or tag."""
    root = _save(client, "trip planning")
    _save(client, "booked flights", parent_id=root["id"])
    _save(client, "booked hotel", parent_id=root["id"])
    _save(client, "a lone note with no children")

    bands = {b["name"]: b["count"] for b in client.get("/timeline?group=thread").json()["bands"]}
    assert bands["trip planning"] == 3
    # The lone note isn't a thread, so it doesn't get its own lane, it
    # folds into the shared band the same way a long tail of small
    # category/tag bands already does.
    from tessellate.api.routes_timeline import THREAD_BAND

    assert bands[THREAD_BAND] == 1


def test_a_thread_whose_root_is_outside_the_window_still_bands(client, session):
    """A parent older than the visible range isn't fetched a second time, 
    the child just becomes a root of its own, the same honest
    simplification the `days` filter already asks the rest of the view to
    accept, rather than a crash or a silently dropped note."""
    root = _save(client, "old root")
    child = _save(client, "a recent continuation", parent_id=root["id"])
    _age(session, root["id"], days=400)

    body = client.get("/timeline?group=thread&days=30").json()
    assert [n["id"] for n in body["rows"]] == [child["id"]]
    bands = {b["name"]: b["count"] for b in body["bands"]}
    from tessellate.api.routes_timeline import THREAD_BAND

    assert bands[THREAD_BAND] == 1


def test_a_long_tail_of_bands_collapses_into_one(client):
    """A chart with forty lanes is not a chart."""
    from tessellate.api.routes_timeline import MAX_BANDS, OTHER_BAND

    for index in range(MAX_BANDS + 4):
        _save(client, f"note {index}", category=f"Cat{index}")

    bands = client.get("/timeline?group=category").json()["bands"]
    assert len(bands) == MAX_BANDS + 1
    assert bands[-1]["name"] == OTHER_BAND
    assert bands[-1]["count"] == 4


def test_grouping_can_be_turned_off(client):
    _save(client, "one", category="Work")
    bands = client.get("/timeline?group=none").json()["bands"]
    assert [band["name"] for band in bands] == ["All notes"]


def test_private_notes_stay_out_of_the_view(client, session):
    """Its text is encrypted at rest; a preview in a chart would undo that."""
    from tessellate.core import vault

    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    note = _save(client, "the appointment is tomorrow")
    client.post(f"/entries/{note['id']}/privacy", json={"private": True})

    body = client.get("/timeline").json()
    assert [n["id"] for n in body["rows"]] == []


def test_binned_notes_stay_out_too(client):
    note = _save(client, "a mistake")
    client.delete(f"/entries/{note['id']}")
    assert client.get("/timeline").json()["rows"] == []


def test_a_window_can_be_asked_for(client, session):
    old = _save(client, "ancient history")
    _age(session, old["id"], 400)
    _save(client, "recent")

    year = client.get("/timeline?days=365").json()
    assert [n["preview"] for n in year["rows"]] == ["recent"]
    everything = client.get("/timeline?days=0").json()
    assert len(everything["rows"]) == 2


def test_a_scale_or_grouping_it_does_not_know_is_refused(client):
    assert client.get("/timeline?scale=fortnight").status_code == 422
    assert client.get("/timeline?group=vibes").status_code == 422


def test_a_truncated_preview_says_so(client):
    """A bare `[:120]` slice cuts a long note off mid-word with nothing on
    screen to say there's more: reported as the grid view's cards missing
    an ellipsis. A short note is untouched; a long one ends in one."""
    from tessellate.api.routes_timeline import PREVIEW_CHARS

    short = _save(client, "a short note well under the preview limit")
    long_note = _save(client, "x" * (PREVIEW_CHARS + 50))

    body = client.get("/timeline").json()
    previews = {n["id"]: n["preview"] for n in body["rows"]}

    assert previews[short["id"]] == "a short note well under the preview limit"
    assert previews[long_note["id"]].endswith("…")
    assert len(previews[long_note["id"]]) == PREVIEW_CHARS


def test_a_row_carries_what_the_table_view_puts_in_its_columns(client):
    """TIMELINE_PLAN decision 6: the table's columns are date, title, kind,
    category, space, tags, words and links, and the view renders from the row
    model and from nothing else. Three of those were not in the payload, so a
    column could only ever have been blank or a second request per row.

    The word count is words, not characters: `preview` has already thrown the
    characters away, and it is the number a person thinks in.
    """
    first = _save(client, "the first note, which is six words long")
    second = _save(client, f"a second note linking to [[{first['id']}]]")

    rows = {note["id"]: note for note in client.get("/timeline").json()["rows"]}

    assert rows[first["id"]]["words"] == 8
    # The default space is named, not slugged: a column has to be readable.
    assert rows[first["id"]]["space"]
    assert rows[first["id"]]["space"] != ""
    # A link counts on both sides, which is what a "links" column means: how
    # many notes this one is joined to.
    assert rows[second["id"]]["links"] >= 0
    assert set(rows[first["id"]]) >= {"space", "words", "links", "tags", "category"}


def test_the_view_is_paged_rather_than_capped(client, session):
    """TIMELINE_PLAN decision 9: `MAX_NOTES` goes, pagination replaces it.

    The cap was 1,500 rows with nothing after it and nothing on screen to say
    so: a notebook past it lost its older notes silently. A page has a cursor,
    and the cursor is `created_at|id` rather than an offset, so a note saved
    while someone is reading cannot shift the page under them.
    """
    for i in range(5):
        note = _save(client, f"note {i}")
        _age(session, note["id"], i)

    first = client.get("/timeline?limit=2").json()
    assert len(first["rows"]) == 2
    assert first["has_more"] is True
    assert first["next_cursor"]

    second = client.get(f"/timeline?limit=2&cursor={first['next_cursor']}").json()
    assert len(second["rows"]) == 2
    seen = [note["id"] for note in first["rows"]] + [n["id"] for n in second["rows"]]
    assert len(set(seen)) == 4, "a page repeated a note"
    # Newest first, all the way through the pages: by when they were written,
    # which is what the cursor orders by (the ids run the other way here,
    # because each note is backdated one day further than the last).
    written = [n["written_at"] for n in first["rows"]] + [n["written_at"] for n in second["rows"]]
    assert written == sorted(written, reverse=True)

    last = client.get(f"/timeline?limit=2&cursor={second['next_cursor']}").json()
    assert last["has_more"] is False
    assert last["next_cursor"] is None


def test_a_page_still_carries_the_density_of_the_whole_range(client, session):
    """The scrubber is the overview someone drags to get somewhere, so it is
    the whole range or it is a map of the part already on screen."""
    for i in range(6):
        note = _save(client, f"note {i}")
        _age(session, note["id"], i * 3)

    page = client.get("/timeline?limit=2").json()
    assert len(page["rows"]) == 2
    # Six notes, six different days, all of them in the strip.
    assert sum(page["density"].values()) == 6
    assert len(page["density"]) == 6


def test_a_later_page_does_not_recompute_the_density_strip(client, session):
    """The strip is drawn from the first page and no later page's `density` is
    read (timeline.js `timelineLoadMore`, the calendar's fetch), so a page with
    a cursor skips the whole range's counts and the document and reminder scans."""
    for i in range(6):
        note = _save(client, f"note {i}")
        _age(session, note["id"], i * 3)
    first = client.get("/timeline?limit=2").json()
    assert sum(first["density"].values()) == 6
    second = client.get(f"/timeline?limit=2&cursor={first['next_cursor']}").json()
    assert len(second["rows"]) == 2
    assert second["density"] == {}


def test_a_cursor_it_cannot_read_is_refused_rather_than_ignored(client):
    """A silently ignored cursor is a view that starts again at the top on
    every page, which reads as duplicated notes rather than as an error."""
    assert client.get("/timeline?cursor=not-a-cursor").status_code == 422
    assert client.get("/timeline?limit=0").status_code == 422
    assert client.get("/timeline?limit=5000").status_code == 422


# --- kinds: the journal is not only its notes (TIMELINE_PLAN.md Phase 4) ------


def _document(client, title="Field notes", content="# Field notes\nthe first line"):
    response = client.post("/documents", json={"title": title, "content": content})
    assert response.status_code in (200, 201), response.text
    return response.json()


def _reminder(client, text="ring the landlord back", days=1):
    due = (utcnow() + timedelta(days=days)).isoformat()
    response = client.post("/reminders", json={"text": text, "due_at": due})
    assert response.status_code in (200, 201), response.text
    return response.json()


def _kinds(body) -> list[str]:
    return [row["kind"] for row in body["rows"]]


def test_a_document_and_a_reminder_are_rows_in_the_feed(client):
    _save(client, "a note about the roof")
    _document(client)
    _reminder(client)

    body = client.get("/timeline").json()
    assert sorted(set(_kinds(body))) == ["document", "note", "reminder"]
    #: Every row says what it is and carries an identity that is unique across
    #: kinds: note 1 and document 1 are two different things.
    assert len({row["key"] for row in body["rows"]}) == len(body["rows"])
    assert all(row["key"].startswith(row["kind"] + ":") for row in body["rows"])


def test_a_reminder_sits_on_the_day_it_is_due_and_says_so(client):
    _reminder(client, days=3)
    row = client.get("/timeline").json()["rows"][0]
    assert row["kind"] == "reminder"
    #: The same claim a note makes when it only mentions a date, and the row
    #: says it the same way, so the view can be honest in one place.
    assert row["placed_by"] == "due"
    assert row["at"][:10] == (utcnow() + timedelta(days=3)).date().isoformat()


def test_a_document_sits_where_it_was_started_not_where_it_was_last_saved(client):
    """A document that plotted at `updated_at` would walk forwards through the
    feed every time it was opened, which is the one thing a journal must not
    do."""
    document = _document(client)
    client.put(f"/documents/{document['id']}", json={"content": "# Field notes\nmore"})
    row = [r for r in client.get("/timeline").json()["rows"] if r["kind"] == "document"][0]
    assert row["at"] == row["written_at"]
    assert "updated_at" in row


def test_kind_narrows_the_feed_and_a_board_is_not_a_note(client, session):
    note = _save(client, "an ordinary note")
    board = _save(client, "# My map")
    session.get(Entry, board["id"]).is_board = True
    session.commit()
    _document(client)
    _reminder(client)

    assert _kinds(client.get("/timeline?kind=note").json()) == ["note"]
    assert _kinds(client.get("/timeline?kind=board").json()) == ["board"]
    assert _kinds(client.get("/timeline?kind=document").json()) == ["document"]
    assert sorted(_kinds(client.get("/timeline?kind=note,document").json())) == [
        "document",
        "note",
    ]
    assert client.get("/timeline?kind=note").json()["rows"][0]["id"] == note["id"]


def test_an_unknown_kind_is_refused_rather_than_silently_empty(client):
    """The failure that reads as "the timeline is broken"."""
    assert client.get("/timeline?kind=notes").status_code == 422
    assert client.get("/timeline?kind=").status_code == 200  # empty means all


def test_paging_across_three_tables_loses_nothing_and_repeats_nothing(client):
    _save(client, "a note about the roof")
    _document(client)
    _reminder(client)

    seen = []
    cursor = None
    for _ in range(5):
        url = "/timeline?limit=1" + (f"&cursor={cursor}" if cursor else "")
        body = client.get(url).json()
        seen += [row["key"] for row in body["rows"]]
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert len(seen) == 3, seen
    assert len(set(seen)) == 3, seen


def test_a_cursor_from_before_the_other_kinds_existed_still_works(client, session):
    """A reader half way down the feed when the app updates keeps their place
    rather than getting a 422 on the next scroll."""
    import base64

    first = _save(client, "the older note")
    _age(session, first["id"], 5)
    _save(client, "the newer note")
    entry = session.get(Entry, first["id"])
    old_style = base64.urlsafe_b64encode(
        f"{(entry.created_at + timedelta(days=1)).isoformat()}|{entry.id + 1}".encode()
    ).decode()

    body = client.get(f"/timeline?cursor={old_style}").json()
    assert [row["id"] for row in body["rows"] if row["kind"] == "note"] == [first["id"]]


def test_the_density_strip_counts_every_kind_the_feed_shows(client):
    """A week spent writing one long document would otherwise read as empty."""
    _document(client)
    body = client.get("/timeline?kind=document").json()
    assert sum(body["density"].values()) == 1
    assert sum(client.get("/timeline?kind=note").json()["density"].values()) == 0


def test_the_row_list_is_called_rows_and_sent_once(client):
    """`notes` held documents, boards and reminders, which is a name that lies.

    Both keys carried the same list for the releases a cached frontend could
    still read `notes`; at 5,000 notes the copy was half of a 350 KB page
    (audit 2026-10-05, ARCH-11), so it is gone and the list is sent once.
    """
    _save(client, "a note about the roof")
    _document(client)
    _reminder(client)

    body = client.get("/timeline").json()
    assert "notes" not in body
    assert {row["kind"] for row in body["rows"]} == {"note", "document", "reminder"}


def test_starting_todays_note_opens_the_composer_rather_than_writing_it():
    """Asked for directly: the timeline's "Start today's note" button "shouldnt
    make the note yet, it should open the capture tab and put in the date text
    in the title and focus on the main text area".

    It used to POST the day's note on the press, so a press you thought better
    of left an empty dated note in the notebook, and the button beside it
    (which only appears when the day has no note) disappeared with it. The
    suite cannot open a browser, so what is held here is that the handler
    shows the capture section and fills the title rather than calling the
    endpoint.
    """
    from pathlib import Path

    #: timeline.js since the Timeline tab was split out of app.js.
    app = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "timeline.js").read_text(
        encoding="utf-8"
    )
    body = app[app.index("function startDayNote(") :]
    body = body[: body.index("\n}\n")]
    assert '/entries/daily/' not in body, "the press must not write a note"
    assert 'showNotesSection("capture")' in body
    assert '$("entry-title")' in body and '$("entry-content")' in body


# --- a mentioned day is a day, not a UTC midnight (audit 2026-10-05, UX-02) --
#
# A day mention was served as "2026-10-09T00:00:00+00:00", which a browser west
# of UTC draws on Thursday evening: the dentist on Friday showed under "Thu,
# Oct 8, 8:00 PM" in New York. A day row now carries the day as a date and no
# instant, and a row whose note said a time carries that time, floating.


def test_a_day_mention_is_served_as_a_date_not_an_instant(client):
    note = _save(client, "the deadline is next friday")
    row = next(r for r in client.get("/timeline?scale=day").json()["rows"] if r["id"] == note["id"])
    assert row["all_day"] is True
    assert len(row["date"]) == 10 and row["date"].count("-") == 2
    assert row["at"] == row["date"], "a day row must not carry a clock or an offset"
    assert row["time"] is None


def test_a_time_said_with_the_day_is_kept_and_floats(client):
    note = _save(client, "Dentist appointment on Friday at 3pm")
    row = next(r for r in client.get("/timeline?scale=day").json()["rows"] if r["id"] == note["id"])
    assert row["all_day"] is False
    assert row["time"] == "15:00"
    assert row["at"] == f"{row['date']}T15:00:00", "the note's own clock, with no offset to shift it"
    assert row["phrase"] == "on Friday at 3pm"


def test_a_written_row_keeps_its_instant(client):
    note = _save(client, "no dates in this one")
    row = next(r for r in client.get("/timeline?scale=day").json()["rows"] if r["id"] == note["id"])
    assert not row.get("all_day")
    assert "T" in row["at"]


def test_the_timeline_names_maps_with_boards():
    """OPEN row 850: a map's row sits under the board kind; the kind says so."""
    from pathlib import Path

    timeline = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "timeline.js").read_text(encoding="utf-8")
    assert '{ key: "board", label: "Boards and maps"' in timeline
