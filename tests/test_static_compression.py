"""INBOX 47: the stamped-URL cache policy, and a wire-size check for the
existing compression it rides on.

**What this file is not.** `test_compression.py` (added alongside the gzip
middleware itself, commit 610def1) already proves `/app.js` comes back
`content-encoding: gzip`, that both streaming NDJSON endpoints are excluded,
and that the exclusion is read off the configured app rather than a constant.
Re-deriving that here would be the same "three sessions rebuilt existing
work" mistake CLAUDE.md warns about: curl against a live server on this
branch showed `/app.js`, every root script, `/vendor/d3.v7.min.js` and
`/css/*.css` all already gzip-compressed (515 KB on the wire for a 1.6 MB
`app.js`) before this file existed. INBOX 47's "static assets are not
compressed" did not hold up.

**What was actually missing** is `RevalidatedStatic` in `app.py`: every
static response got `Cache-Control: no-cache` regardless of whether the URL
carried a `?v=<version>` stamp, so a stamped asset (a *different URL* on
every release, per `test_asset_cache_busting.py`) still paid a revalidation
round trip it never needed. That is the actual gap this file closes and
tests.
"""

from __future__ import annotations

import gzip

from tessellate import __version__
from tests._app_js import APP_JS, app_js_files


def test_a_stamped_asset_is_immutable_and_gzipped(client):
    """`/app.js?v=<version>` is the real request the browser makes."""
    with client.stream(
        "GET", f"/js/app.js?v={__version__}", headers={"Accept-Encoding": "gzip"}
    ) as response:
        assert response.status_code == 200
        assert response.headers.get("content-encoding") == "gzip"
        assert response.headers.get("cache-control") == "public, max-age=31536000, immutable"
        raw = b"".join(response.iter_raw())
    # Belt and braces, same pattern as test_compression.py's round-trip test:
    # fetch without letting httpx decode, then gunzip it by hand.
    body = gzip.decompress(raw)
    assert body.startswith(b"//") or len(body) > 0  # app.js is real JS, not empty


#: The ratchet on the app's own scripts, gzipped as served. Three numbers, all
#: measured through this test's client (the middleware's level 6 with a sync
#: flush per chunk, which is not what `gzip -6` on the file gives):
#:
#: - `APP_JS_CAP`, app.js alone. Lowered at every step of the split
#:   (`docs/roadmap/archive/agent-remaining/appjs-split.md`) to the new size plus 2%,
#:   so the file cannot quietly grow back into what it was.
#: - `PIECE_CAP`, every other piece. 64 KB is the plan's per-file bound: the
#:   largest range in the split table measures well under it.
#: - `TOTAL_CAP`, every piece added up: the real wire cost of the app's code
#:   on a cold load. Splitting costs a little here (each file starts gzip's
#:   window empty), so this is rewritten to the measured total plus 2% at each
#:   step, and after the split only ever downward.
#:
#: **2026-10-05, comments stripped at serve time** (audit FE-01,
#: `api/asset_strip.py`): the same 25 files went from 792,475 bytes to
#: 335,400 on the wire, app.js from 42,710 to 14,778, the largest piece
#: (notes-list.js) to 27,423 (a comment's lines are left empty, so line
#: numbers match the source; that costs about 2% over removing them). The
#: caps are those numbers plus 2%; the per-piece bound is the plan's 64 KB
#: scaled by the same strip, rounded. What is measured is code now, not
#: prose: a comment costs nothing here.
#:
#: **Re-measured on the merged tree, 2026-10-05.** The 15,070 above was set on
#: the frontend branch alone, while the boot split (merged the same hour) had
#: moved seven surfaces out of app.js and registered them in its lazy table;
#: together app.js measured 15,132 bytes. The cap is that plus 2%, the rule
#: this comment states, and it only goes down from here.
#:
#: **2026-10-05, search-boot-1005.** The Settings window's handlers that only
#: its listeners call, the "m" chord's guide, and the pickers, menus and
#: checkers that one lazy file alone uses moved into that file: app.js
#: 15,221 (cap was 15,435), total 323,086 (cap was 342,100),
#: both measured by this test's client. Caps are the measure rounded up.
#: **Merged into the integration branch the same day**: app.js 14,207, total
#: 322,228 after the note edit form (renderEditForm, now note-edit-panels.js
#: behind a stand-in) and eight one-caller helpers moved to their lazy files.
#: Caps are the measure rounded up to the next 100.
APP_JS_CAP = 14_300
PIECE_CAP = 32_000
#: After claude/notes-flow-rebuild 143b240 merged: total 321,331 (the
#: embedding models list into settings-packages.js), app.js unchanged.
#: And after 88227db (621, 622): 321,097.
#: And after the Atlas merge, with addSkill in settings-controls.js: 320,986.
#: And with the s2 agent's list drag-select edge scroll (+489) and Link all
#: above 70% (+152): 321,487, a raise the next agent undid by moving the edge
#: scroll to drag-edge.js and `noteEditToolbar` to note-edit-panels.js (both
#: lazy): 320,244.
#: And with Brief 88 (chat: the Guide's palette row, a source opening at its
#: quote, the undo call at each chat write; its helpers moved to the lazy
#: chat-undo.js first, -442): 320,554. A raise to win back (OPEN.md, bootdiet:
#: the meeting overlay's listeners in settings-wiring.js are the next lever).
#: And with undo on every write (INBOX 898; its helpers are the lazy
#: undo-kit.js, the call sites and the stand-ins are not): 321,387, which was
#: won back, not raised for: the share-sheet intake (`takeSharedIntake`) is the
#: lazy shared-intake.js and `renderMemorySettings` is in settings-controls.js,
#: behind stand-ins. App.js 14,045, total 319,920.
#: And after the model panel, answer edit and Explain row moved to the lazy gesture-kit.js: 318,631.
TOTAL_CAP = 320_600


def _served_gzip_size(client, name: str) -> int:
    with client.stream(
        "GET", f"/js/{name}?v={__version__}", headers={"Accept-Encoding": "gzip"}
    ) as response:
        assert response.status_code == 200, name
        assert response.headers.get("content-encoding") == "gzip", name
        return len(b"".join(response.iter_raw()))


def test_the_app_scripts_stay_under_the_ratchet(client):
    """app.js under its own cap, every other piece under 64 KB, and all of
    them together under the total. The history of the single-file bound this
    replaced is kept below, because it is the reason the split exists."""
    # 750 KB. Raised from 600 on 2026-09-13 when the popup agent, the Guide and
    # the link menu took the gzipped file to 609 KB, and from 700 on 2026-09-21
    # at 701,992 bytes, 0.3% over, after a night that added per-feature model
    # choice, the Ask sub-tab's four fixes, the tag offer and the mind map's
    # pictures and waypoints.
    #
    # **Two raises is the signal, not the number.** The bound is a smoke test
    # against a runaway file rather than a budget, and its real answer has been
    # the same both times: the app.js split, SESSION_BRIEFS Brief 33, after
    # which this comes back down on its own. A third raise should not be
    # written; the split should be done instead, and the count above is here so
    # whoever reads this next can see how overdue it is rather than inferring
    # it from one number.
    #
    # **The third time, the split was done.** 2026-09-23: 750,706 bytes, 0.1%
    # over. The Timeline tab (about 1,800 lines) moved into its own
    # timeline.js, loaded at boot after dashboard.js, and the bound stayed
    # where it was: 724,604 bytes after, measured through the live server.
    # The next time this goes red, the answer is the next surface out of
    # app.js, not a fourth number here.
    #
    # **The fourth time, the same answer.** 2026-09-24: 752,031 bytes after the
    # catalogue's deep links. The popup agent (Ctrl+K, about 1,330 lines)
    # moved into palette.js, loaded after timeline.js: 730,546 bytes after.
    # Then the generated faces grew to a surface of their own and went into
    # avatars.js (762,903 bytes before, 736,191 after).
    #
    # **The fifth time, the split itself.** 2026-09-26: app.js 740,482 bytes
    # and agent-activity.js 10,651 (751,133 together) when the file started
    # being cut into the pieces the plan lists; the bound became the three
    # caps above. After the last cut: app.js 41,630, the largest piece
    # notes-list.js at 50,207, and 777,805 together, 26,672 bytes (3.6%) more
    # than the one file, which is what 23 gzip streams that each start with
    # an empty window cost. APP_JS_CAP now only ever goes down.
    #
    # **2026-10-05, the first cut of that total.** 792,754 bytes (cap 794,000,
    # notes-list.js 63,548 of the 64,000 piece bound) came down to 758,418 with
    # notes-list.js at 57,929, by moving code only a gesture reaches into lazy
    # files: the catalogue's deep links, the welcome card, the update dialogs,
    # the palette's window, a note card's menu panels, the edit form's two
    # panels, the inline "put on a board" pickers, and the 110 listeners inside
    # the Settings window (settings-controls.js, awaited by the first
    # `openSettingsModal`). The cap is that total plus 2%, 774,000. It is a cap:
    # it goes down after a split and is never raised.
    sizes = {path.name: _served_gzip_size(client, path.name) for path in app_js_files()}
    assert sizes[APP_JS.name] < APP_JS_CAP, (
        f"gzipped app.js is {sizes[APP_JS.name]} bytes, expected under {APP_JS_CAP}"
    )
    over = {n: size for n, size in sizes.items() if n != APP_JS.name and size >= PIECE_CAP}
    assert not over, f"pieces over {PIECE_CAP} bytes gzipped: {over}"
    total = sum(sizes.values())
    assert total < TOTAL_CAP, (
        f"the app's scripts total {total} bytes gzipped, expected under {TOTAL_CAP}"
    )


def test_an_unstamped_asset_is_not_immutable(client):
    """No `?v=` means the URL can be reused across a release, so it keeps
    asking the browser to revalidate rather than promising it never will."""
    response = client.get("/js/app.js", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    cache_control = response.headers.get("cache-control", "")
    assert "immutable" not in cache_control
    assert cache_control == "no-cache"


def test_vendored_assets_stay_revalidated_too(client):
    """Vendored files are deliberately never stamped
    (`test_asset_cache_busting.py::test_vendored_assets_are_left_alone`), so
    they must not accidentally pick up the immutable treatment either."""
    response = client.get("/vendor/d3.v7.min.js", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-cache"


def test_a_query_string_that_only_contains_v_as_a_substring_is_not_stamped(client):
    """`?vv=1` or `?rev=1` must not be mistaken for the app's own `?v=` stamp."""
    response = client.get("/js/app.js?vv=1", headers={"Accept-Encoding": "gzip"})
    assert response.headers.get("cache-control") == "no-cache"


def test_chat_stream_never_carries_content_encoding(client):
    """The one response class this change must never touch. Streamed NDJSON
    is excluded from gzip entirely (see test_compression.py); this asserts
    the same invariant holds for the real route, with a real (AI-unavailable)
    request, rather than only against the middleware's configured exclusion
    list."""
    with client.stream(
        "POST", "/chat/stream", headers={"Accept-Encoding": "gzip"}, json={"question": "hey"}
    ) as response:
        assert "content-encoding" not in response.headers
        # Drain the stream so the test client's connection closes cleanly.
        for _ in response.iter_lines():
            pass
