"""The companion moves on its own time and rides with the panel it is on.

INBOX 426, the owner: "they still telleport and move suddenly as well and it
is jarring"; "atlas needs to move and work on its own time not based off how
fast the user is switching tabs or scrolling. if it is sitting on a pannel and
I scroll or that panel moves it might fall or move with the panel"; "it keeps
disappearing and reappearing on different parts of the page as I scroll";
"when I press the option to stay in the same spot across pages ... it still
moves"; "the companion just went off the screen and I cant get it back now";
"the right click companion dropdown menu doesnt appear where the companion
is"; "I changed my name but the companion which was me didnt update".

The motion itself is measured in a browser by
`scratchpad/ui-sweeps/companionscroll.js` (a per-frame trace over a scroll:
glued within 2px, no frame jump past 45px beyond its panel's own, never
below full opacity) and `companionbeats.js` (fast tab switching, pinning,
resize, the menu's place, call back, no frame loop when idle). These tests
pin the wiring that makes those numbers true, so a later edit cannot quietly
put the old behaviour back.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

from pathlib import Path

import pytest
from tests._app_js import app_js_text, frontend_text

ROOT = Path(__file__).resolve().parents[1]
#: avatars.js and its lazy half, companion-menu.js (the menu and the enlarged
#: view), read as one.
AV = "\n".join((ROOT / "frontend" / "js" / name).read_text(encoding="utf-8") for name in ("avatars.js", "companion-menu.js"))
APP = app_js_text()
SETTINGS = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _fn(name: str, src: str = AV) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


def test_it_is_drawn_through_a_transform_not_left_and_top() -> None:
    # Following a panel every frame must never be a layout.
    assert "buddy.style.transform = `translate(${nmb.lx}px, ${nmb.ly}px)`" in _fn("nameMarkBuddyPut")
    region = AV[AV.index("function nameMarkBuddyPut(") : AV.index("// --- being found")]
    assert not re.search(r"buddy\.style\.(left|top) =", region)


def test_a_scroll_moves_it_with_its_panel_in_the_same_frame() -> None:
    listener = AV[AV.index('document.addEventListener("scroll", (event) => {\n  //: Any scroll') :]
    listener = listener[: listener.index("}, { passive: true, capture: true });")]
    assert "nameMarkBuddyFollow();" in listener
    follow = _fn("nameMarkBuddyFollow")
    assert "g.el.getBoundingClientRect()" in follow and "box.top + g.dy" in follow
    # A panel drawn again is found again by its path, not lost.
    assert "document.querySelector(g.sel)" in follow


def test_following_stops_when_the_page_is_still() -> None:
    frame = _fn("nameMarkBuddyFollowFrame")
    assert "now < nmbFollow.until" in frame
    assert "performance.now() + ms" in _fn("nameMarkBuddyKeepUp")


def test_no_move_is_a_fade_to_somewhere_else() -> None:
    move = _fn("nameMarkBuddyGo")
    assert "distance > 700" not in move
    # The two fades left: Reduce motion's, in place of the travel, and
    # being carried asleep (a sleeper is not woken to walk). Each is a
    # crossfade now (INBOX 443), never a fade to nothing and back.
    assert move.count("nameMarkBuddyCrossfade(buddy, dx, dy,") == 2 and "if (nameMarkBuddyNoTravel()) {" in move
    assert "if (nameMarkBuddyAsleep(buddy)) {" in move


def test_a_tab_switch_only_asks_for_a_look_on_its_own_beat() -> None:
    changed = _fn("nameMarkBuddyTabChanged")
    assert "placeNameMarkBuddy" not in changed and "nameMarkBuddyQueuePlace();" in changed
    queue = _fn("nameMarkBuddyQueuePlace")
    # The first ask's time stands, and never within five seconds of a move.
    assert "if (nmb.placeTimer" in queue and "5000 - since" in queue
    beat = _fn("nameMarkBuddyBeat")
    assert "nameMarkBuddyStillGood(" in beat


def test_a_scroll_or_a_moved_panel_is_not_a_reason_to_choose_again() -> None:
    check = _fn("nameMarkBuddyCheck")
    assert "anchorMoved" not in check and "panel moved" not in check
    assert "nmbFollow.scrollAt" in check
    # Resize fits it back in, it does not choose a new perch at once.
    assert "setTimeout(nameMarkBuddyRefit" in AV


def test_pinned_on_every_page_means_it_never_moves_on_its_own() -> None:
    for name in ("nameMarkBuddyCheck", "nameMarkBuddyQueuePlace", "nameMarkBuddyBeat", "nameMarkBuddyErrand", "nameMarkBuddyUnheld"):
        assert "nmb.pinned" in _fn(name), name
    menu = _fn("nameMarkBuddyMenu")
    assert '"*": {' in menu and "keep: 1" in menu and 'kind: "pinned"' in menu


def test_it_can_always_be_called_back() -> None:
    callback = _fn("nameMarkBuddyCallBack")
    assert "nameMarkBuddyKeepSpots({})" in callback and 'revealFeature("set-companion")' in callback
    assert "run: nameMarkBuddyCallBack" in _fn("nameMarkBuddyMenu")
    assert "act: () => nameMarkBuddyCallBack()" in APP
    assert 'id="avatar-buddy-recall"' in HTML
    assert '$("avatar-buddy-recall").addEventListener("click", () => nameMarkBuddyCallBack());' in SETTINGS


def test_its_menu_opens_at_it() -> None:
    menu = _fn("nameMarkBuddyMenu")
    assert 'face.getBoundingClientRect()' in menu and "menu.style.translate" in menu
    # However it is opened, the pointer's place is not used.
    assert "nameMarkBuddyMenu(buddy, x, y)" not in AV and "beside()" not in AV


def test_a_new_name_redraws_the_companion() -> None:
    paint = _fn("paintUserMarks", APP)
    assert "syncNameMarkBuddy()" in paint


def test_a_companion_of_your_own() -> None:
    # INBOX 426 e: any name, the same part pickers as Your look, kept on this
    # computer, and its parts worn only by its own name while it is the
    # companion.
    assert '<option value="custom">Your own character</option>' in HTML
    assert 'id="avatar-buddy-name"' in HTML and 'id="avatar-buddy-parts"' in HTML
    assert 'if (choice === "custom") return nameMarkBuddyCustom().name;' in AV
    own = _fn("nameMarkOwnFor")
    assert 'appearancePref("avatar-buddy", "off") === "custom"' in own
    mount = _fn("mountBuddyCustom")
    assert 'nameMarkLookPickers(host, "avatar-buddy-look-", "From its name"' in mount
    # Your look and the companion share one picker builder.
    assert 'nameMarkLookPickers(host, "profile-look-", "From your name"' in _fn("mountProfileLook")
    assert '"avatar-buddy-custom"' in _fn("nameMarkBuddyKeepCustom")
    assert "mountBuddyCustom();" in SETTINGS


def test_what_a_face_holds_shows_in_its_head_mark() -> None:
    # INBOX 426 f: the first faces drew the held thing in a raised hand at
    # the mark's lower right; the head-only mark had dropped it. Back, with
    # the figure's own drawing, and never in the small mark's one cue.
    draw = _fn("drawCharacter")
    assert "if (!full && !mini && reading.hand) {" in draw
    block = draw[draw.index("if (!full && !mini && reading.hand) {") :]
    assert "nameCharacterHeld(reading.hand, hand," in block[: block.index("\n  }\n")]


def test_a_panel_moved_by_a_transform_is_followed_every_frame() -> None:
    # Round 2: the loop runs on while the panel or an ancestor animates a
    # property that places it, not only for its fixed second and a half,
    # and the events that set a transition going and end it start it.
    frame = _fn("nameMarkBuddyFollowFrame")
    assert "nameMarkBuddyPanelMoving(nmb.glue.el)" in frame
    moving = _fn("nameMarkBuddyPanelMoving")
    assert "document.getAnimations()" in moving and "target.contains(el)" in moving
    # An endless animation elsewhere (a spinner) must not keep an idle page busy.
    assert "Number.isFinite(" in moving
    for event in ("transitionrun", "transitionend", "transitioncancel", "animationend"):
        assert f'"{event}"' in AV
    # Both motion sweeps run in the gate's sweep list.
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert "companionscroll companionbeats" in gate


CSS08 = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")


def test_the_companion_is_light_on_the_page() -> None:
    # INBOX 426 x: "the companion showing makes everything noticeably
    # slower". Measured by scratchpad/ui-sweeps/companionperf.js (in the
    # gate's sweeps): Atlas idle +190ms/s of main thread before, +63 after.
    # No filter on the moving figure (it re-layered the page every frame).
    char = CSS08[CSS08.index(".nm-buddy-char {") : CSS08.index("}", CSS08.index(".nm-buddy-char {"))]
    assert "filter" not in char
    # Its drawing's idle animations are paced by hand, reads before writes.
    tempo = _fn("nameMarkBuddyTempo")
    assert "anim.pause()" in tempo and "anim.currentTime = t" in tempo
    assert tempo.index("const states = nmbTempo.anims.map") < tempo.index("anim.currentTime = t")
    assert "SVGElement" in tempo
    # The obstacle sweep waits for any scroll to settle, glued or not.
    check = _fn("nameMarkBuddyCheck")
    assert "if (performance.now() - nmbFollow.scrollAt < 400) {" in check
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert "companionperf" in gate


def test_it_rides_its_panels_scroll_and_leaves_with_it() -> None:
    # INBOX 426 x: "if I scroll really fast the companion will just float in
    # the corner ... then it will disappear". On a panel in a scroll area it
    # rides that area's scroll through a ScrollTimeline (the compositor moves
    # it, however fast), clipped to the area's visible box. Measured in
    # composited frames by scratchpad/ui-sweeps/companionsmooth.js.
    ride = _fn("nameMarkBuddyRide")
    assert "new ScrollTimeline({ source: want" in ride
    assert 'rangeEnd: `${NMB_RIDE_PX}px`' in ride and 'rangeStart: "0px"' in ride
    # It stays in the body, in its own band: the app's scroll boxes are
    # never given a child.
    build = _fn("nameMarkBuddyBuild")
    assert 'band.id = "nm-buddy-band"' in build and "document.body.appendChild(band)" in build
    assert "#nm-buddy-band.nmb-riding {\n  overflow: clip;" in CSS08
    # A scroll of the area it rides reads no box and moves nothing.
    listener = AV[AV.index('document.addEventListener("scroll", (event) => {\n  //: Any scroll') :]
    listener = listener[: listener.index("}, { passive: true, capture: true });")]
    riding = listener[listener.index("if (nmb.ride && target === nmb.ride.el) {") :]
    riding = riding[: riding.index("return;")]
    assert "getBoundingClientRect" not in riding and "nameMarkBuddyPut" not in riding
    # Not on a bar that sticks: it ignores the scroll the rider follows.
    assert 'pos === "sticky" || pos === "fixed"' in _fn("nameMarkBuddyScrollsWith")
    # Out of sight, it waits for the page to be still and then its own beat.
    seen = _fn("nameMarkBuddySeen")
    assert "nameMarkBuddyQueuePlace()" in seen and "nmbFollow.scrollAt" in seen


def test_a_jump_it_must_make_is_a_poof_under_half_a_second() -> None:
    # INBOX 426 x: "a better teleport". Out of sight, or further than a walk
    # should go, it dissolves in stars and appears in another burst. The
    # owner, 2026-09-27: "the disappearing and reappearing animation needs to
    # be improved again": two gestures, out easing in and in easing out with
    # a small overshoot, not one blink.
    assert "const NMB_POOF_OUT_MS = 180;" in AV and "const NMB_POOF_IN_MS = 300;" in AV
    assert 'scale: "1.04"' in _fn("nameMarkBuddyPoof")
    move = _fn("nameMarkBuddyGo")
    assert "nameMarkBuddyPoof(buddy, dx, dy, seenFrom)" in move
    poof = _fn("nameMarkBuddyPoof")
    # The shrink is on the character: a `scale` on the host scaled the
    # translate that places it (measured: swept 600px across the page).
    host_frames = poof[poof.index("nmb.anim = buddy.animate(") : poof.index("const char =")]
    assert "scale" not in host_frames
    # Only its own end takes its class off (a cancelled move's late event).
    assert "if (nmb.anim === anim) buddy.classList.remove(\"nmb-poofing\")" in poof
    assert "if (nmb.anim !== walk) return;" in move


def test_choosing_a_perch_is_cheap() -> None:
    # The choice with `near` hit-tested every point of up to 120 perches
    # (176ms, a stall before every move); a perch that cannot beat the best
    # so far is no longer sampled, and each point is tested once (5.7ms).
    choose = _fn("nameMarkBuddyChoose")
    assert "if (best && ceiling <= best.score) {" in choose
    assert "nmbCoverCache = new Map();" in choose
    assert "nmbCoverCache?.get(key)" in _fn("nameMarkBuddyCovers")


def test_its_menu_holds_it_where_it_is() -> None:
    # INBOX 426 x, 84.png: the menu open in one corner, the companion in
    # another. Measured (companionmenu.js): with the menu open, its own
    # behaviours moved it 338px away before; now nothing moves it until the
    # menu closes, and a panel carrying it carries the menu.
    for name in ("nameMarkBuddyBeat", "nameMarkBuddyErrand", "nameMarkBuddyUnheld", "nameMarkBuddyCheck", "nameMarkBuddyTick"):
        assert "nameMarkBuddyMenuOpen()" in _fn(name), name
    assert "if (nmb.menuPlace && nameMarkBuddyMenuOpen()) nmb.menuPlace();" in _fn("nameMarkBuddyPut")
    menu = _fn("nameMarkBuddyMenu")
    place = menu[menu.index("const beside = () => {") :]
    assert "const box = face.getBoundingClientRect();" in place[: place.index("};")]
    # Flipped to its left at the right edge and kept inside the window.
    assert "if (left + now.width > innerWidth - margin) left = box.left - gap - now.width;" in place
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert "companionmenu" in gate


def test_its_face_changes_with_what_happens() -> None:
    # INBOX 426 x: "one expression only". Measured by companionlife.js: a
    # hello is happy, a saved note excited, an error surprised, thinking
    # serious, away sleepy and back with a wave, and each comes back.
    express = _fn("nameMarkBuddyExpress")
    assert "nameCharacterFigure(seed, want)" in express
    # The face only: the colours stay the name's.
    draw = _fn("drawCharacter")
    assert "const expr = full && nameCharacterExpression" in draw
    assert "const bias = reading.source !== \"seed\" && reading.mood ?" in draw
    # Drawn ahead in idle time, so a reaction never waits on a first drawing.
    assert "requestIdleCallback" in _fn("nameMarkBuddyPrewarm")
    assert "nameMarkBuddyPrewarm(seed);" in AV
    # Back after a long idle: a wave.
    assert 'nameMarkBuddyAct("wave")' in _fn("nameMarkBuddyAwake")


def test_light_and_dark_and_its_size() -> None:
    # INBOX 426 x: "a light or dark variant", "size options". A soft
    # shadow on a light page, a light of the accent behind it on a dark
    # one, both still gradients (no filter).
    dark = CSS08[CSS08.index(':root[data-theme="dark"] #nm-buddy::after {') :]
    dark = dark[: dark.index("}")]
    assert "radial-gradient" in dark and "filter" not in dark
    # Small, medium, large in its menu and Appearance; any size from the
    # handle; kept; scaled about the point it touches its perch, and its
    # shape and sampled points with it (companionlife.js measures it).
    assert "const NMB_SIZES = { small: 0.8, medium: 1, large: 1.3 };" in AV
    assert 'prefs.set("avatar-buddy-size"' in _fn("nameMarkBuddySetSize")
    assert "nameMarkBuddyScaled(nameMarkBuddyShapeAt1(" in _fn("nameMarkBuddyShape")
    assert "ox + (qx - ox) * size" in _fn("nameMarkBuddyCovers")
    assert 'label: "ph:resize Size",' in _fn("nameMarkBuddyMenu")  # a flyout since round 7
    assert 'id="avatar-buddy-size"' in HTML
    assert '"avatar-buddy-size"' in SETTINGS
    assert "#nm-buddy .nm-buddy-face {\n  scale: var(--nmb-scale);\n  transform-origin: 50% var(--nmb-edge);" in CSS08


def test_a_saved_face_is_read_as_it_may_be_drawn_now() -> None:
    # INBOX 426 w (73.png, 90.png): a saved hand "middlefinger" left the
    # Holding select empty. Every saved style is read through the pickers'
    # own option lists (profilelook.js: Holding reads "From your name", a
    # saved hair is kept). The server drops retired parts too
    # (tests/test_preferences_api.py).
    clean = _fn("nameMarkStyleClean")
    assert "options().includes(value)" in clean
    assert "return nameMarkStyleClean(" in _fn("ownNameMarkStyle")
    assert "style: nameMarkStyleClean(saved.style)" in _fn("nameMarkBuddyCustom")


def test_your_picture_enlarges_on_a_double_click() -> None:
    # INBOX 426 w: "the profile picture cannot be enlarged like the
    # companion". A double-click on any of your own pictures opens it large,
    # and the second click of it no longer closes what the first opened.
    listener = AV[AV.index('document.addEventListener("dblclick", (event) => {') :]
    assert 'closest?.("[data-user-mark]")' in listener[:400]
    viewer = _fn("openNameMarkViewer")
    assert "performance.now() - openedAt > 400" in viewer
    assert 'if (document.querySelector(".nm-viewer")) return;' in viewer


def test_pinned_stays_put_through_resizes_and_a_pin_mid_walk() -> None:
    # INBOX 426 (l): "when I press the option to stay in the same spot
    # across pages ... it still moves sometimes". Measured by
    # companionpin.js (six tab switches, scroll, a panel collapsing and its
    # own panel removed, three minutes of simulated idle, resize, reload):
    # before, a pin near the middle jumped 200px when the window went from
    # 900 to 700px high, and a pin made mid-walk jumped 202px to where it
    # was going. A place keeps its place; only one within NMB_EDGE_NEAR of
    # the right or bottom edge keeps its distance from that edge.
    restore = _fn("nameMarkBuddyRestore")
    assert "toRight < NMB_EDGE_NEAR && toRight < sx ? innerWidth - (w - sx) : sx" in restore
    assert "toBottom < NMB_EDGE_NEAR && toBottom < sy ? innerHeight - (h - sy) : sy" in restore
    assert "w / 2" not in restore and "h / 2" not in restore
    menu = _fn("nameMarkBuddyMenu")
    stay = menu[menu.index("Stay here on every page") :]
    stay = stay[: stay.index("} },")]
    assert "const box = buddy.getBoundingClientRect();" in stay
    assert "{ x, y, pose: nmb.pose" in stay
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert "companionpin" in gate


def test_its_menu_opens_at_the_pointer_and_stops_a_move() -> None:
    # INBOX 426 x, 84.png, round 4: at 1.25 and 1.5 scale, dark, riding a
    # scrolled dashboard panel, a right-click mid-walk or mid-poof opened
    # the menu at the companion and the move then carried it 38 to 142px
    # away. companionmenu.js (70 menus, every way in) now finds every menu
    # within 24px. A move under way stops where it is drawn; a right-click
    # or a long press opens the menu at the pointer, the keyboard beside it.
    menu = _fn("nameMarkBuddyMenu")
    assert 'if (nmb.anim && nmb.anim.playState === "running") {' in menu
    assert "nameMarkBuddyRide(null, Math.round(drawn.left), Math.round(drawn.top));" in menu
    assert "at ? at[0] : box.left, at ? at[1] : box.top" in menu
    assert "const place = at ? inside : beside;" in menu
    build = _fn("nameMarkBuddyBuild")
    assert "if (event.button === 2) rightDown = " in build
    assert "nameMarkBuddyMenu(buddy, at);" in build


def test_the_size_handle_shows_only_when_asked_for() -> None:
    # Round 4: the handle was reported visible at rest. Hidden by opacity
    # and visibility; shown on hover or the keyboard's focus, or while it
    # is sized, and not while it is carried (companionlife.js: hidden/0 at
    # rest, visible/1 on focus, 1 on hover).
    grip = CSS08[CSS08.index("#nm-buddy .nmb-size-grip {") :]
    grip = grip[: grip.index("}")]
    assert "opacity: 0;" in grip and "visibility: hidden;" in grip
    assert "#nm-buddy:not(.nm-buddy-dragging) .nm-buddy-face:is(:hover, :focus-visible) .nmb-size-grip," in CSS08
    # Atlas round 4's filter stays: its svg roots are composited, not paced.
    assert "!(a.effect.target instanceof SVGSVGElement)" in _fn("nameMarkBuddyTempo")
    # What animates inside one of Atlas's layers is stepped every other beat
    # (10Hz): measured 40 paints and 20 layouts a second at 20Hz, 20 and 10
    # at 10Hz, 119 and 60 left free (atlasmoodfx.js, INJECT=1).
    tempo = _fn("nameMarkBuddyTempo")
    assert 'a.effect.target.closest("svg.atl-layer")' in tempo
    assert "if (beat || !nmbTempo.slow.has(anim)) anim.currentTime = t;" in tempo


def test_the_benches_carry_no_inline_style() -> None:
    # Round 5: the avatar lab logged three "Refused to apply inline style"
    # warnings (the app's policy is style-src 'self'); they were three
    # style attributes in tools/avatar-lab.html, now classes in its CSS.
    for page in (ROOT / "tools").glob("*.html"):
        assert not re.search(r"\sstyle=\"", page.read_text(encoding="utf-8")), page.name


def test_it_notices_the_app_rate_limited_and_never_under_reduced_motion() -> None:
    # Round 5: reads along with a long note, peeks at the graph laid out
    # again, cheers once for a longer streak, yawns at night, covers its
    # eyes for a private note, looks at a new toast (companionreact.js, each
    # from its real event). Each has a cooldown, none within 6s of another,
    # none under Reduce motion or Avatar animation Off.
    react = _fn("nameMarkBuddyReact")
    assert "nameMarkBuddyStill()" in react and "NMB_REACT_GAP" in react
    for kind in ("read", "graph", "streak", "yawn", "private", "toast"):
        assert f"{kind}: {{ cool:" in AV, kind
    # The streak: once, and only for a count longer than the last seen.
    assert "if (seen && days > seen) nameMarkBuddyReact(\"streak\");" in _fn("nameMarkBuddyStreak")
    dashboard = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert "nameMarkBuddyStreak(streak)" in dashboard
    # Night: a tick yawns, and the yawn's early return comes after the mood
    # has moved, so a tick that yawns still tires it at night (review, round 6).
    tick = _fn("nameMarkBuddyTick")
    assert 'nameMarkBuddyReact("yawn")' in tick
    assert tick.index("nmb.mood.energy = drift(") < tick.index('nameMarkBuddyReact("yawn")')
    # A toast goes through the same limits.
    assert 'nameMarkBuddyReact("toast", added)' in AV
    # Covering its eyes: its hands over its head, not under it.
    assert '#nm-buddy.nmb-act-hide:not([data-pose="hang"]) :is(.nmb-arm-l, .nmb-arm-r) {\n  z-index: 3;' in CSS08


def test_it_can_be_petted_tossed_and_watches_a_near_pointer() -> None:
    # Round 5 (companioninteract.js): the pointer resting on it gets a happy
    # wiggle, once in 15s; let go at speed it is thrown (INBOX 882: a flight
    # with gravity and bounces, tests/test_companion_throw.py), a slow
    # let-go is a drop; its eyes stay on a near pointer, and with Faces
    # follow the pointer off a pointer passing is not followed.
    build = _fn("nameMarkBuddyBuild")
    assert "}, NMB_PET_MS);" in build and "nameMarkBuddyThrow(buddy, v[0], v[1]);" in build
    assert "Math.hypot(v[0], v[1]) > NMB_TOSS_SPEED" in build
    pet = _fn("nameMarkBuddyPet")
    assert "nameMarkBuddyStill()" in pet and "15000" in pet
    assert "spots[tab] = nameMarkBuddySpotFor(spot);" in _fn("nameMarkBuddyThrowLand")
    assert "nameMarkBuddyPerches(tab, near && per < 12 ? near[0] : null)" in _fn("nameMarkBuddyChoose")
    notice = _fn("nameMarkBuddyNotice")
    assert 'document.documentElement.dataset.avatarFollow !== "off"' in notice
    assert "const near = follows && dist < NMB_EYES_NEAR * reach;" in notice


def test_a_scroll_already_on_its_way_does_not_close_a_new_menu() -> None:
    # Round 5, the companionmenu.js flake: a scroll's event comes with the
    # next frame, so a right-click in the frame of a scroll (a trackpad's
    # momentum, a smooth scroll) opened a menu that closeActionMenusOnScroll
    # shut a moment later: 17 of 20 such right-clicks showed no menu, 0 of
    # 80 after this.
    menus = (ROOT / "frontend" / "js" / "menus.js").read_text(encoding="utf-8")
    on_scroll = menus[menus.index("function closeActionMenusOnScroll(") :]
    on_scroll = on_scroll[: on_scroll.index("\n}\n")]
    assert "performance.now() - (window._menuOpenedAt || 0) < 200" in on_scroll
    opener = menus[menus.index("function openActionMenu(") :]
    assert "window._menuOpenedAt = performance.now();" in opener[:400]


def test_a_walk_is_paced_too() -> None:
    # Round 5 review (atlaswalk.js): while it walked, Atlas's leg steps
    # (animations on groups inside its svg) laid out and repainted it every
    # frame, 60 layouts and 120 paints a second, because the pacer let a
    # walk run at full rate. Paced from its first step: 20 and 39.
    tempo = _fn("nameMarkBuddyTempo")
    assert 'const busy = (!!nmb.act && !NMB_RESTING_ACTS.has(nmb.act)) || buddy.classList.contains("nm-buddy-dragging") || !!nmb.visit;' in tempo
    assert "nmb-walking" not in tempo[tempo.index("const busy") : tempo.index("const still")]
    move = _fn("nameMarkBuddyGo")
    walk = move[move.index('nameMarkBuddyBlend(buddy, () => buddy.classList.add("nmb-walking"), NMB_BLEND_IN_MS);') :]
    assert "nmbTempo.seen = 0;" in walk[:300] and "setTimeout(nameMarkBuddyTempo, 0)" in walk[:400]


def test_every_way_to_a_note_counts_as_opening_it() -> None:
    # Round 6: search, a link, the palette, the Library, the timeline, the
    # graph and chat all go to a note through flashEntry (capture-ask.js);
    # the companion reads along from there too (companionreact.js: the
    # palette's jump to a long note reads along).
    ask = (ROOT / "frontend" / "js" / "capture-ask.js").read_text(encoding="utf-8")
    flash = ask[ask.index("function flashEntry(") :]
    flash = flash[: flash.index("\n}\n")]
    # Unguarded since Brief 86 dropped the redundant typeof guards on eager-file functions (avatars.js is eager).
    assert "nameMarkBuddyNoteOpened(id);" in flash and "typeof nameMarkBuddyNoteOpened" not in flash


def test_the_large_view_enlarges_the_figure_with_scale_not_transform() -> None:
    # The owner: "when I click on atlas in the larger view window sometimes
    # it shrinks for a sec then expands back to full height after the
    # animation is finished". The figure box is Atlas's `.atl-figure-box`,
    # and a mood whose loop moves the whole body animates its `transform`,
    # which replaced the viewer's `transform: scale(2.2)`: 233 to 245px at
    # rest, 108 to 116 at the loop's middle (viewerpoke.js). `scale`
    # composes with an animated `transform` instead of being replaced.
    css = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules = re.findall(r"\.nm-viewer-figure\s*>\s*\.nm-figure\s*\{([^}]*)\}", css)
    assert rules, "the large view's figure rule moved; point this test at it"
    for body in rules:
        assert not re.search(r"(?<![-\w])transform\s*:", body), "the large view sizes its figure by `transform` again"
    assert any(re.search(r"(?<![-\w])scale\s*:\s*2\.2", body) for body in rules)


def test_a_change_of_look_does_not_draw_the_shared_defs_as_heads() -> None:
    # The owner, with a screenshot: "a column of four small Atlas heads"
    # under the status bar at the bottom left, outside any UI. `atlasRepaint`
    # (atlas.js) redraws every `svg.nm-atlas` on the page when Atlas look,
    # Atlas style or Face looks changes, and the hidden `<svg class="nm-atlas
    # atl-defs">` each look keeps its gradients in, a child of <body> with a
    # height of 0, is one: it was replaced by a whole 20px Atlas, in the
    # page's flow under everything, and the next look's defs made the next
    # head. strayheads.js: one head per change, at x 0 and y 840, 860, 880.
    atlas = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
    start = atlas.index("function atlasRepaint(")
    body = atlas[start : atlas.index("\n}\n", start)]
    loop = body[: body.index("svg.replaceWith(")]
    assert "atl-defs" in loop, "atlasRepaint redraws the shared defs as a head"


def test_the_companion_shows_and_hides_from_anywhere() -> None:
    # INBOX 430: a hotkey, a palette action, and so a Find anything action.
    wiring = (ROOT / "frontend" / "js" / "settings-wiring.js").read_text(encoding="utf-8")
    assert 'toggleCompanion: { keys: "Ctrl+Shift+Y"' in wiring
    assert "nameMarkBuddyToggle()" in wiring
    panes = (ROOT / "frontend" / "js" / "settings-panes.js").read_text(encoding="utf-8")
    # The row names which it will do (tests/test_companion_toggle.py).
    assert "Show companion\", chord: \"toggleCompanion\", act: () => nameMarkBuddyToggle()" in panes
    toggle = _fn("nameMarkBuddyToggle")
    assert 'prefs.get("nm-buddy-last", null)' in toggle
    assert 'prefs.set("nm-buddy-last", was)' in _fn("nameMarkBuddyHide")


def test_it_gets_out_of_a_popups_way() -> None:
    # INBOX 430: "the notifications panel was blocked by it". A popup is an
    # obstacle as a whole box; over one it fades at once and steps aside.
    assert '"#notif-panel:not(.hidden)' in AV
    assert "const boxes = nameMarkBuddyPopups();" in _fn("nameMarkBuddyObstacles")
    dodge = _fn("nameMarkBuddyDodge")
    assert 'buddy.classList.toggle("nmb-dodge", over)' in dodge
    assert "queueNameMarkBuddyCheck()" in dodge
    assert "#nm-buddy.nmb-dodge { opacity: 0.12; }" in CSS08


def test_it_keeps_out_of_the_tours_ring() -> None:
    # INBOX 430: "Atlas spills out of its ring in the tour". The tour's ring
    # and card are popups it gets out of the way of, looked at again once a
    # step has settled, measured by the drawn figure's box.
    assert "#tour-spot:not(.hidden), #tour-card:not(.hidden)" in AV
    assert "nmbDodgeLate = setTimeout(nameMarkBuddyDodge, 700);" in AV
    assert 'buddy.querySelector(".nm-figure")' in _fn("nameMarkBuddyDodge")


def test_it_perches_on_the_pages_panels_first_on_every_tab():
    # INBOX 430: "perch and ride on UI elements on every tab and scroll with
    # them, as it does on the Dashboard". Every tab put it on a window bar
    # (companiontabs.js, before); now each tab's first choice is a panel.
    start = AV.index("const NAME_MARK_BUDDY_ORDER = {")
    table = AV[start : AV.index("};", start)]
    rows = dict(re.findall(r"(\w+): \[\"(\w+)\"", table))
    assert set(rows) >= {"dashboard", "notes", "chat", "graph", "library", "documents", "timeline", "reminders"}
    assert all(first in ("card", "dock", "under") for first in rows.values()), rows
    # Never a menu faded out or a field you type into, and Atlas's tail is
    # part of what must not cover a control.
    assert "child.checkVisibility({ opacityProperty: true, visibilityProperty: true })" in AV
    assert "child.matches(\"textarea, input, select, [contenteditable='true'], .cm-editor\")" in AV
    assert 'document.querySelector("#nm-buddy .atl-figure-box")) shape.push(' in AV


def test_it_follows_a_tab_change_only_once_you_stay_and_comes_in_smoothly():
    # INBOX 430: "the companion lingers on the old tab for a second, then pops
    # in elsewhere". Hidden with its tab at once, shown again if you come
    # straight back, following after 1.6 to 2.8s, entering by a walk, a
    # climb or a materialise, and leaving by a dissolve.
    changed = _fn("nameMarkBuddyTabChanged")
    assert 'buddy.classList.add("nmb-away");' in changed
    assert "NMB_DWELL_MS + Math.random() * NMB_DWELL_JITTER_MS" in changed
    assert "if (!nmb.tab || tab === nmb.tab)" in changed
    enter = _fn("nameMarkBuddyEnter")
    # The ways it can come (INBOX 501 made the choice varied; see the test
    # of not the same way twice).
    for how in ('"down"', '"up"', '"walk"', '"materialise"', 'how === "down"', 'how === "walk"'):
        assert how in enter, how
    for guard in ("nameMarkBuddyBeat", "nameMarkBuddyCheck"):
        assert "nmb.away" in _fn(guard), guard
    assert "nameMarkBuddyLeave(buddy, () => {" in _fn("nameMarkBuddyHide")
    assert "#nm-buddy.nmb-away { opacity: 0; visibility: hidden;" in CSS08


def test_reduce_actions_and_atlas_stances_at_rest():
    # INBOX 430: "a Reduce actions setting (Appearance > Companion) ... Off,
    # Fewer (the default) and Normal", and stances of each look's own.
    assert 'id="avatar-buddy-actions"' in HTML
    for value in ('value="off"', 'value="fewer"', 'value="normal"'):
        assert value in HTML[HTML.index('id="avatar-buddy-actions"') :][:400]
    decide = _fn("nameMarkBuddyDecide")
    # Fewer is a third, except in its large view, where it is watched.
    assert "if (!NMB_QUIET_ACTS.includes(act)) w *= { off: 0, fewer: nmb.visit ? 1 : 0.33, normal: 1 }[actions] ?? 0.33;" in decide
    assert "if (stance && (!nmb.atlasLook || nmb.atlasLook !== stance.look)) w = 0;" in decide
    for stance, look in (("fold", "masculine"), ("hip", "masculine"), ("clasp", "feminine"), ("sway", "feminine")):
        assert f'{stance}: {{ ms:' in AV and f'look: "{look}" }}' in AV
        assert f"#nm-buddy.nmb-act-{stance} " in CSS08


def test_its_menu_has_sections_for_who_it_is_and_the_settings_behind_it():
    # The owner: "extend this menu a bit maybe with sub-sections ... a quick
    # link to the profile/personas/appearences tab, toggling ... masculine/
    # feminine, which companion is displayed". Submenus are the kebab
    # recipe's own (`items` on a row, `buildMenuGroupButton`), and each choice
    # goes through the Appearance control it mirrors.
    kebab = (ROOT / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")
    assert "if (Array.isArray(item.items) && typeof buildMenuGroupButton === \"function\")" in kebab
    menu = _fn("nameMarkBuddyMenu")
    for row in ("ph:user-switch Companion", "ph:coat-hanger Atlas look", "ph:resize Size", "ph:gear Settings"):
        assert f'label: "{row}",\n    items:' in menu, row
    assert 'choose("avatar-buddy", value)' in menu and 'choose("atlas-look", value)' in menu
    for target in ('openSettingsModal("appearance", "avatar-buddy-row")', 'openSettingsModal("preferences")', 'openSettingsModal("personas")'):
        assert target in menu


def test_it_sets_off_and_lands_and_eases_between_poses():
    # INBOX 430: "far more lifelike, organic motion and transitions". A walk
    # is held back for a crouch and ends in a squash and a rebound, eased per
    # keyframe (an easing over the whole animation made the crouch late);
    # the limbs ease into a new pose; the pacer leaves those transitions be.
    # Held back `setOff` (the crouch), unless it takes over a move under way.
    assert "const setOff = underway ? 0 : NMB_SET_OFF_MS;" in AV
    assert "delay: setOff, fill: \"backwards\"" in AV
    assert "nameMarkBuddySquash(char, duration + setOff, underway);" in AV
    squash = _fn("nameMarkBuddySquash")
    assert '.map((frame) => ({ ...frame, easing: "ease-in-out" })), { duration: total });' in squash
    assert "a instanceof CSSTransition" in AV
    assert "#nm-buddy :is(.nmb-leg, .nmb-arm, .nmb-hold, .atl-lower) { transition: transform calc(var(--motion-slow) * 2) var(--ease-spring)" in CSS08


def test_it_is_never_drawn_before_its_place_and_never_jumps_after_it() -> None:
    # The owner, 2026-09-27: it "appeared for a split second at the top right
    # ... then ... pretty suddenly slightly adjusted its position to perch".
    # Measured (scratchpad/ui-sweeps/companionentry.js): placed while the
    # dashboard was filling in, then carried 142px and 18px in single frames.
    # Built hidden, before its style is first computed ...
    build = _fn("nameMarkBuddyBuild")
    assert build.index('buddy.classList.add("nmb-away");') < build.index("nameMarkBuddySetSize(")
    # ... and brought in the way it comes to a tab, once the page is still.
    sync = _fn("syncNameMarkBuddy")
    assert "nameMarkBuddyArrive(buddy);" in sync and "placeNameMarkBuddy(buddy, true)" not in sync
    assert "nameMarkBuddySettle(tab, (spot) => {" in _fn("nameMarkBuddyArrive")
    settle = _fn("nameMarkBuddySettle")
    assert "NMB_SETTLE_QUIET_MS" in settle and "NMB_SETTLE_MAX_MS" in settle
    assert "if (moved) choose();" in settle
    # A tab switch while it settles does not show it unplaced.
    assert "if (!Number.isFinite(nmb.x)) {" in _fn("nameMarkBuddyTabChanged")
    # A panel that jumps is glided after, added to whatever else moves it;
    # a scroll and a panel's own animation are still followed exactly.
    catch_up = _fn("nameMarkBuddyCatchUp")
    assert 'composite: "add"' in catch_up
    assert "nmbFollow.scrollAt < 200" in catch_up and "nameMarkBuddyPanelMoving(" in catch_up
    follow = _fn("nameMarkBuddyFollow")
    assert follow.count("nameMarkBuddyCatchUp(buddy,") == 2
    # A move that starts mid-glide starts from where it is drawn.
    assert "nmb.glideAnim.playState === \"running\"" in _fn("nameMarkBuddyMoveTo")
    # Leaving with its tab goes in the same frame as the tab (the owner:
    # "it stayed visible on the new tab for a split second, vanished";
    # measured at 1093x614, 11 frames shown on the new tab with the 200ms
    # fade, 0 now); coming down or up out of a bar is clipped at its own
    # edge rather than drawn over the bar.
    assert "#nm-buddy.nmb-away { opacity: 0; visibility: hidden; pointer-events: none; transition: none; }" in CSS08
    assert "clipPath: clip(t)" in _fn("nameMarkBuddyEnter")
    assert "nmb-arrive" not in AV and "nmb-arrive" not in CSS08


def test_its_enlarged_view_keeps_the_drawing_clear_of_its_name() -> None:
    # The owner, 2026-09-27: "make sure the text doesnt clash with the avatar
    # in the expanded companion panel". Measured (viewerclash.js): the
    # drawing ran 4 to 16px into the name for every face; now the figure's
    # margins take in the drawing's own reach, measured before first paint.
    viewer = _fn("openNameMarkViewer")
    assert "nameMarkViewerFit(figure);" in viewer
    assert 'isAtlasSeed(seed) ? "The app\'s own guide"' in viewer
    fit = _fn("nameMarkViewerFit")
    assert 'grow("marginBottom", bottom - box.bottom);' in fit and 'grow("marginTop", box.top - top);' in fit
    assert "if (px > was)" in fit


def test_it_peeks_down_from_under_the_top_bar() -> None:
    # The owner: "is there a peak half hidden animation for the companion
    # like with the bottom bar for the top bar as well?" Hanging, it pulls up
    # behind the edge, turns over out of sight and lets its head down under
    # it; ending it always goes through `peekback` (never a pop to hanging).
    # Measured (peekdown.js): 25px of head shown under the bar, frames within
    # 12px, back to hanging with no clip.
    assert 'peekdown: { ms: 9000, w: 1.5, cool: 60000, poses: ["hang"] },' in AV
    act = _fn("nameMarkBuddyAct")
    assert 'if (was === "peekdown" && act !== "peekback" && !nameMarkBuddyStill()) act = act || "peekback";' in act
    assert "&:is(.nmb-act-peekdown, .nmb-act-peekback) .nm-buddy-face { clip-path: inset(5px -80px -80px -80px); }" in CSS08
    for name in ("nmb-peekdown", "nmb-peekback"):
        assert f"@keyframes {name} {{" in CSS08


def test_every_change_of_place_is_travelled_by_its_body() -> None:
    # The owner, 2026-09-27: "instead the slight position displacements, the
    # companion instead walks or jumps, fly, to the new position ... if it is
    # further away then it will teleport". Measured (locomotion.js, 1440 and
    # 1093, as you and as Atlas): a 22px step is a hop, 160px a walk (Atlas
    # floats), 640px a poof, its panel jumping 40px a hop; at most 10.8px a
    # frame, speed changing at most 5.5px a frame, every move ending on its
    # place.
    go = _fn("nameMarkBuddyGo") + _fn("nameMarkBuddyRoute")
    for way in ("if (nameMarkBuddyNoTravel()) {", "nameMarkBuddyPoof(buddy, dx, dy, seenFrom)",
                "if (route === \"float\") {", "if (d < size * NMB_HOP_SIZES && !poseChanged)",
                'nameMarkBuddyBlend(buddy, () => buddy.classList.add("nmb-walking"), NMB_BLEND_IN_MS);'):
        assert way in go, way
    # Distances are in its own size, not pixels.
    assert "const size = NMB_W * Math.max(0.7, nmb.scale || 1);" in go
    assert "distance > size * NMB_POOF_SIZES" in go
    assert "NMB_POOF_PX" not in AV
    # Atlas and the winged and ghostly faces float.
    assert "isAtlasSeed(seed)" in _fn("nameMarkBuddyFlies")
    # Its panel moving under it, and a resize keeping it to its bar, go the
    # same way when it stands still.
    assert "nameMarkBuddyGo(buddy, dx, dy, nmb.spot || {}, false);" in _fn("nameMarkBuddyCatchUp")
    assert "nameMarkBuddyGo(buddy, dx, dy, nmb.spot || {}, false);" in _fn("nameMarkBuddyRefit")
    assert "nameMarkBuddyGo(buddy, dx, dy, spot, poseChanged, was, underway);" in _fn("nameMarkBuddyMoveTo")


def test_it_settles_in_with_props_and_each_doing_can_be_turned_off() -> None:
    # The owner, 2026-09-27: "new companion states with simple props ...
    # lying down and sleeping, reading, sitting on a beanbag, pulling out a
    # chair and sitting, face palming, and other gestures, each with smooth
    # transitions in and out", and "Every companion feature must be
    # togglable in Settings", and it "must stay cheap". Measured
    # (companionacts.js, as you and as Atlas): each prop shown, at most 2.8px
    # a frame going in or out, nothing left behind, 0 to 0.3 layouts a second
    # while it rests in one.
    for act in ("lie", "read", "beanbag", "chair", "facepalm", "shrug"):
        assert f"  {act}: {{ ms:" in AV, act
    for prop in ("beanbag", "chair", "pillow", "book"):
        assert f'class: "nms nms-{prop}"' in _fn("nameMarkBuddyScene"), prop
    # Out: the body gets up first, the prop goes after.
    assert 'buddy.classList.add("nmb-unwind");' in _fn("nameMarkBuddyAct")
    assert "#nm-buddy .nms {" in CSS08 and ".nmb-unwind) .nm-buddy-char {" in CSS08
    # Rest is paced as rest: a long settled act does not run the drawing at
    # full rate.
    assert "const NMB_RESTING_ACTS = new Set([" in AV
    # Every doing has a switch, and what is off is never picked.
    assert 'id="avatar-buddy-activities"' in HTML
    assert "mountBuddyActivities()" in (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    assert "if (nameMarkBuddyActOff(act, off)) continue;" in _fn("nameMarkBuddyDecide")
    table = AV[AV.index("const NMB_ACTIVITIES = [") : AV.index("];", AV.index("const NMB_ACTIVITIES = ["))]
    for act in ("wave", "peek", "peekdown", "lie", "read", "beanbag", "chair", "facepalm", "shrug"):
        assert f'"{act}"' in table, act


def test_close_by_it_keeps_its_eyes_on_you_and_wakes_gently() -> None:
    # The owner: "atlas doesnt follow my mouse pointer when it is close.
    # should it??" Measured (companiongaze.js): a slow pass past its head
    # moved its gaze 15 to 16 times, was 7 (the dead zone and a head wait
    # that restarted with every move); asleep, a pointer held 50px away for
    # 1.5s now wakes it (it stayed asleep). Faces follow the pointer (the
    # Appearance switch) still turns all of it off.
    aim = _fn("nameMarkBuddyAim")
    assert "const dead = near ? 0.05 : 0.15;" in aim
    assert 'if (near && Date.now() >= nmb.groggyUntil) {' in aim
    notice = _fn("nameMarkBuddyNotice")
    assert "nameMarkBuddyAim([x, y], near);" in notice
    assert "nameMarkBuddyWake(true);" in notice and "now - nmb.nearSince > 700" in notice
    assert 'document.documentElement.dataset.avatarFollow !== "off"' in notice
    assert "#nm-buddy:is(.nmb-attend, .nmb-watch) .nm-atlas .atl-iris { translate:" in CSS08


def test_it_leans_its_body_a_little_while_still_facing_you() -> None:
    # The owner: "tilt their body that way while still mostly facing
    # forward". One property (`--nmb-tilt`) turns the figure a few degrees
    # about its feet, eased; used glancing at a close pointer (measured 0.4,
    # 1.2 and 2 degrees at 20, 60 and 150px, companiongaze.js), before
    # setting off, and now and then at rest.
    assert "#nm-buddy .nm-buddy-char { rotate: calc(var(--nmb-tilt) * 4deg); }" in CSS08
    assert "nameMarkBuddyLean(nmb.ex, now, speed);" in _fn("nameMarkBuddyNotice")
    assert "nameMarkBuddyTilt(dx > 0 ? -0.8 : 0.8," in _fn("nameMarkBuddyGo")
    assert 'if (act === "tilt") nameMarkBuddyTilt(' in _fn("nameMarkBuddyAct")


def test_emotes_night_cap_and_faces_that_crossfade_and_come_down_gradually() -> None:
    # The owner: "should there be more emotes like zzzz coming off it for
    # sleeping, wearing a night cap etc.", and a face that "will change
    # expressions for a sec then instantly go back". Measured
    # (companionemotes.js): three z's at different points of their drift,
    # the cap on asleep (1) and off awake (0), two figures for a moment in a
    # change of face then one, the "?" and the sparkle shown, and a laugh
    # coming down through a smile.
    build = _fn("nameMarkBuddyBuild")
    assert 'emote.className = "nmb-emote";' in build and "for (let i = 0; i < 3; i += 1) {" in build
    assert ".nm-buddy-z i:nth-child(3) { animation-delay: 1.73s; }" in CSS08
    # Only lying or curled (sitting), never upright.
    assert '#nm-buddy:is(.nmb-act-lie, :is([data-pose="sit"], [data-pose^="curl"]):is(.nmb-sleep, .nmb-act-nap)):not(.nmb-cap-off) .nmp-nightcap { opacity: 1; }' in CSS08
    express = _fn("nameMarkBuddyExpress")
    assert 'old.classList.add("nmb-fig-leaving");' in express and "nameMarkBuddyExpress(softer, 2400)" in express
    assert 'nameMarkBuddyActOff("emote")' in _fn("nameMarkBuddyEmote")
    for key in ('"emotes"', '"nightcap"'):
        assert key in AV[AV.index("const NMB_ACTIVITIES = [") :][:3000]


def _run_pure(names: list[str], body: str):
    # The interaction model's choices are pure functions: run them as they
    # are written, in node, against the cases below.
    src = "\n".join(_fn(n) for n in names)
    # The poke pools are two one-line constants the reaction reads.
    pools = "\n".join(re.search(rf"^const {n} = .*;$", AV, re.M).group(0) for n in ("NMB_POKE_GENTLE", "NMB_POKE_POOL"))
    script = "const NMB_WARMTH_HALF_MS = 240000; const NMB_BORED_MS = 240000;\n" + pools + "\n" + src + "\nconsole.log(JSON.stringify(" + body + "));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_interaction_model_moves_between_states_as_the_owner_asked() -> None:
    # The owner: "if I click it, it will change expressions for a sec then
    # instantly go back to doing what it was doing like sleeping, it needs to
    # be more natural and gradual, unless it is startled".
    # Asleep, a click always wakes it slowly (never a start: the owner,
    # 2026-09-27, "it opens its eyes and mouth for a sec like it is startled
    # but then falls back asleep"); poked again while waking, a pout, then
    # grumpy.
    click = _run_pure(["nameMarkBuddyClickReaction"], "[[true,1,60000],[true,2,900],[false,1,1500,true],[false,2,1500,true],[false,3,1500,true,'',() => 0],[false,1,60000,false,'',() => 0]].map((a) => nameMarkBuddyClickReaction(...a))")
    # Asleep: wake. Groggy: a pout for the first two, then the pool.
    assert click == ["wake", "wake", "pout", "pout", "pleased", "pleased"]
    # INBOX 705: awake, a poke is one of a pool, never the same twice running,
    # and annoyed is rare (the fifth poke in twenty seconds, one draw in four,
    # never straight after itself).
    pool = _run_pure(["nameMarkBuddyClickReaction"], "(() => { const out = []; for (let pokes = 1; pokes <= 8; pokes++) for (let r = 0; r < 20; r++) { let i = 0; const rand = () => (r + 0.5 + i++ * 7) % 20 / 20; out.push([pokes, nameMarkBuddyClickReaction(false, pokes, 3000, false, '', rand), nameMarkBuddyClickReaction(false, pokes, 3000, false, 'grumpy', rand)]); } return out; })()")
    seen = {how for _, how, _ in pool}
    assert {"pleased", "playful", "curious", "wave", "spin", "laugh"} <= seen
    assert all(how != "grumpy" for pokes, how, _ in pool if pokes < 5)
    assert all(after != "grumpy" for _, _, after in pool)
    late = [how for pokes, how, _ in pool if pokes >= 5]
    assert 0 < sum(how == "grumpy" for how in late) <= len(late) * 0.3
    repeat = _run_pure(["nameMarkBuddyClickReaction"], "[...NMB_POKE_POOL].map((last) => nameMarkBuddyClickReaction(false, 3, 3000, false, last, () => 0.99) !== last)")
    assert all(repeat)
    hover = _run_pure(["nameMarkBuddyHoverReaction"], "[[true,0,0,false],[true,1800,0,false],[false,0,0,false],[false,0,-0.5,false],[false,0,0.5,true]].map((a) => nameMarkBuddyHoverReaction(...a))")
    assert hover == ["stir", "wake", "brighten", "none", "none"]
    # Warmth relaxes by half in four minutes, and not at all at once.
    warm = _run_pure(["nameMarkBuddyWarmthAt"], "[nameMarkBuddyWarmthAt({v: 0.8, at: 0}, 0), nameMarkBuddyWarmthAt({v: 0.8, at: 0}, 240000), nameMarkBuddyWarmthAt(null, 5)]")
    assert warm[0] == 0.8 and abs(warm[1] - 0.4) < 1e-9 and warm[2] == 0
    # Boredom grows with time on a perch, less for a tired, shy or sleepy one.
    bored = _run_pure(["nameMarkBuddyBoredom"], "[nameMarkBuddyBoredom(0, 0.7, 0.7, ''), nameMarkBuddyBoredom(240000, 0.7, 0.7, ''), nameMarkBuddyBoredom(240000, 0.2, 0.7, ''), nameMarkBuddyBoredom(240000, 0.7, 0.7, 'sleepy')]")
    assert bored[0] == 0 and bored[1] > 1 and bored[2] < bored[1] and bored[3] < bored[1]


def test_its_reactions_come_and_go_gradually_and_it_gets_bored() -> None:
    # Woken slowly (a yawn, a stretch, a look), awake 45s at least; hover and
    # click answered through the model; boredom drives a few steps over or a
    # wander and back, never while you type or read near it, pinned, on an
    # errand, with Reduce actions off or with it switched off.
    wake = _fn("nameMarkBuddyWake")
    assert 'nameMarkBuddyAct("yawn", 1700);' in wake and 'setTimeout(() => nameMarkBuddyAct("wake"), 1800)' in wake
    assert "nmb.awakeUntil = Date.now() + NMB_AWAKE_MS;" in wake
    tick = _fn("nameMarkBuddyTick")
    assert "if (idle > NMB_SLEEP_MS && !awake) {" in tick and "if (nameMarkBuddyWander(Date.now())) {" in tick
    build = _fn("nameMarkBuddyBuild")
    assert "const how = nameMarkBuddyClickReaction(wasAsleep, wasAsleep ? 1 : nmb.pokes.length, sinceLast, groggy, lastHow);" in build
    assert "nameMarkBuddyHover(0);" in build
    wander = _fn("nameMarkBuddyWander")
    for guard in ("nmb.pinned", 'nmb.perch === "errand"', 'nameMarkBuddyActions() === "off"', 'nameMarkBuddyActOff("wander")',
                  "now - (nmb.keyAt || 0) < 20000", "nameMarkBuddyMenuOpen()"):
        assert guard in wander, guard
    assert "now - nmb.home.at > 30000" in wander
    # Asked near where it was, its own perch won every time (wander.js): it
    # looks a few widths off, towards the middle.
    assert "const away = nameMarkBuddyChoose(tab, obstacles, [nmb.x + off, nmb.y], 4);" in wander
    assert "nameMarkBuddyWarmthAt(nmb.feel, now)" in _fn("nameMarkBuddyDecide")


def test_its_gaze_has_one_reach_for_every_kind_and_drifts_back() -> None:
    # The owner: "it doesnt follow the mouse movement if i have it turned on
    # either ... the main companions dont have the look at mouse proximity
    # limit like atlas does". Measured (companiongaze.js, the switch on, as
    # Atlas and as you): 20, 60 and 150px look that way (eyes 0.7, 2 and
    # 3.4px), 400px has let go and drifted back to 0; one code path.
    notice = _fn("nameMarkBuddyNotice")
    # Its reach is its size, read where its head is drawn (INBOX 443: in its
    # large view, 2.2 times).
    assert "const reach = size;" in notice and "if (dist > 220 * reach && !loud) {" in notice
    assert "Math.max(0.7, nmb.scale || 1)];" in _fn("nameMarkBuddyHeadAt")
    release = _fn("nameMarkBuddyRelease")
    assert 'buddy.style.setProperty("--nmb-ex", "0");' in release
    assert "#nm-buddy .name-mark .nm-eyes { transition: translate calc(var(--motion-slow) * 3) var(--ease-in-out); }" in CSS08


def test_the_larger_faces_have_a_life_of_their_own() -> None:
    # The owner: "my popup character doesnt really have much expression, same
    # with when it is a profile avatar". Measured (faceslife.js): the Profile
    # face (56px) plays small acts while the 18px one stays still, and
    # nothing plays with Avatar animation off; the large view plays one as it
    # opens (viewerclash.js), and says what the face is.
    tick = _fn("nameMarkIdleTick")
    assert "NM_IDLE_MIN" in tick and "if (!big.length) return;" in tick
    assert "nameMarkIdleQuiet()" in tick and "nameMarkIdleQuiet()" in _fn("nameMarkIdleAct")
    quiet = _fn("nameMarkIdleQuiet")
    assert 'root.dataset.avatarMotion === "off"' in quiet and 'nameMarkBuddyActions() === "off"' in quiet
    viewer = _fn("openNameMarkViewer")
    assert '"Its own face, read from its name"' in viewer and '"A face of its own"' not in viewer
    assert "nameMarkIdleWake();" in viewer


def test_its_arms_rest_in_its_mood_and_come_back_to_it_after_an_act() -> None:
    # The owner: "make sure that the positions of the limbs like the arm on
    # companions ... actually match the mood as well". Measured (armmood.js,
    # as you): each mood's arms where its rule puts them (happy -35/35,
    # surprised -155/155, nervous a hand at the mouth), a face palm at -150
    # over it, and after the act the arm back in the mood's pose.
    assert 'buddy.dataset.feel = want || nmb.reading?.mood || "";' in _fn("nameMarkBuddyExpress")
    for mood in ("happy", "surprised", "confused", "sleepy", "sad", "nervous", "serious"):
        assert f'[data-feel="{mood}"]' in CSS08, mood
    # Lighter than any act's arm, so an act plays over it and hands it back.
    assert ':where(#nm-buddy:is([data-feel="happy"], [data-feel="cute"])) .nm-figure .nmb-arm-r { transform: rotate(-35deg); }' in CSS08
    # Arms are drawn over the body, so they also turn in across it: hands
    # on hips, clasped, at the chest (the first reading, that inward arms
    # were hidden, was a 1x screenshot; at 3x they are in front).
    assert ':where(#nm-buddy:is([data-feel="nervous"])) .nm-figure .nmb-arm-r { transform: rotate(100deg); }' in CSS08
    assert ':where(#nm-buddy:is([data-feel="uwu"])) .nm-figure .nmb-arm-l { transform: rotate(-62deg); }' in CSS08


def test_it_rests_where_you_put_it_on_a_button_and_the_button_still_clicks() -> None:
    # The owner: "atlas or the companion wont let me rest it on the start
    # something buttons on the dashboard". Measured (perchbuttons.js): let go
    # above a tile it fell 172 to 238px (the find field above the tiles, and
    # Atlas's tail reaching into the tile); now it stands on each tile, and
    # the tile takes a click at its middle and at its top edge under it.
    yours = _fn("nameMarkBuddyYoursObstacles")
    assert "const wide = NMB_W * Math.max(0.7, nmb.scale || 1) * 4;" in yours
    assert 'const overFront = spot?.pose === "sit" && spot?.legs !== "tuck";' in yours
    for fn in ("nameMarkBuddyDrop", "nameMarkBuddyCheck", "nameMarkBuddyStillGood", "nameMarkBuddyNextSpot"):
        assert "nameMarkBuddyYoursObstacles(" in _fn(fn), fn
    assert "const minW = Math.round(NMB_W * Math.max(0.7, nmb.scale || 1));" in _fn("nameMarkBuddySurfaceWalk")
    # Standing or sitting, only the part above its soles or seat is the
    # handle: a 75px button it sat above (legs and nebula over it) clicks.
    assert '#nm-buddy:is([data-pose="stand"], [data-pose="sit"]) .nm-buddy-face { pointer-events: none; }' in CSS08
    assert '#nm-buddy[data-pose="sit"] .nm-buddy-face::after {\n  bottom: 20px;' in CSS08
    assert '#nm-buddy:is([data-pose="stand"], [data-pose="sit"]) .nmb-size-grip { pointer-events: auto; }' in CSS08


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_variant_is_never_the_one_it_played_last() -> None:
    # The owner: "also state variations, not the exact same animation or
    # mood animation each time". Two hundred picks in a row, each given the
    # last: never the same twice running, and every variant turns up.
    runs = _run_pure(["nameMarkBuddyPickVariant"], """(() => { const out = {}; for (const n of [2, 3, 4]) { let last = -1; const seen = new Set(); let repeats = 0;
      for (let i = 0; i < 200; i += 1) { const v = nameMarkBuddyPickVariant(n, last); if (v === last) repeats += 1; seen.add(v); last = v; }
      out[n] = [repeats, seen.size]; } out.edge = [nameMarkBuddyPickVariant(3, 2, 0.999), nameMarkBuddyPickVariant(3, 0, 0), nameMarkBuddyPickVariant(1, 0, 0.5)]; return out; })()""")
    for n in ("2", "3", "4"):
        assert runs[n][0] == 0 and runs[n][1] == int(n), (n, runs[n])
    assert runs["edge"] == [1, 1, 0]


def test_acts_have_variants_and_their_own_tempo_each_time() -> None:
    act = _fn("nameMarkBuddyAct")
    assert "const v = nameMarkBuddyPickVariant(variants, nmb.variant?.[act] ?? -1);" in act
    assert "if (!NMB_RESTING_ACTS.has(act)) nameMarkBuddyVary(buddy, act, ms || spec?.ms || 1200);" in act
    assert "anim.playbackRate = rate;" in _fn("nameMarkBuddyVary")
    for rule in ('&.nmb-act-wave[data-variant="1"]', '&.nmb-act-hop[data-variant="2"]', '&.nmb-act-nap[data-variant="2"]'):
        assert rule in CSS08, rule
    assert "nameMarkBuddyPickVariant(3, nmb.variant?.joy ?? -1)" in _fn("nameMarkBuddyJoy")


def test_it_lies_down_to_sleep_where_there_is_room_and_moves_by_its_look() -> None:
    # The owner: "when it sleeps can it lay down?? ... masculine and feminine
    # ways to stand and move the body". Measured (napgait.js): a nap on open
    # bar lies down and gets up through its way up, a nap squeezed beside a
    # button dozes where it is; a 160px walk as you takes 898ms masculine and
    # 754 feminine (a deeper and a lighter bob), Atlas's float 788 and 662.
    act = _fn("nameMarkBuddyAct")
    assert 'if (act === "nap" && !nameMarkBuddyActOff("lie") && nameMarkBuddyLieRoom()) act = "lie";' in act
    assert "nameMarkBuddyLieRoom()" in _fn("nameMarkBuddyTick")
    assert 'if (nmb.pose !== "stand" || nmb.legs' in _fn("nameMarkBuddyLieRoom")
    assert "NMB_GAIT_PACE[buddy.dataset.gait]" in _fn("nameMarkBuddyGo")
    assert '&[data-gait="masculine"].nmb-walking .nm-buddy-char { animation: nmb-bob-heavy' in CSS08
    assert '&[data-gait="feminine"].nmb-walking .nm-buddy-char { animation: nmb-bob-light' in CSS08


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_lean_has_hysteresis_and_a_dwell() -> None:
    # The owner: "leans or tilts to the left and right a bit back and forth
    # too fast because of my mouse movement". Measured (leanflick.js): a 2Hz
    # sweep across it for 5s changed its lean 21 times; now 0, and a pointer
    # held to one side still gets its lean (0.6).
    got = _run_pure(["nameMarkBuddyLeanSide"], "[[0,0.8,5000],[0,0.5,5000],[1,0.5,5000],[1,0.2,5000],[1,-0.8,500],[1,-0.8,1400],[-1,0.1,200]].map((a) => nameMarkBuddyLeanSide(...a))")
    assert got == [1, 0, 1, 0, 1, -1, -1]
    lean = _fn("nameMarkBuddyLean")
    assert "Math.exp(-dt / 250)" in lean and "if (speed > 1500) return;" in lean


def test_performance_mode_alone_no_longer_holds_the_companion_still() -> None:
    # The owner: "when the companion is appearing from off screen, it still
    # just appears there" (OS animations on). Performance mode's automatic
    # setting set data-motion=reduced and held the companion to a 300ms
    # fade. Measured (tabentry.js, 1093x614, tab bar and keyboard): with
    # Performance mode on it walks, materialises or climbs in; with Motion
    # set to Reduce or the system asking, it fades; never a pop.
    motion = _fn("nameMarkBuddyMotion")
    assert 'if (app === "reduced") return { mode: "fades", reason: "app" };' in motion
    assert '"(prefers-reduced-motion: reduce)"' in motion and '"perf-ignored"' in motion
    assert "return nameMarkBuddyMotion().mode !== \"full\";" in _fn("nameMarkBuddyNoTravel")
    assert 'root.dataset.buddyMotion = "full"' in _fn("nameMarkBuddyMotionApply")
    assert ':root:not([data-avatar-motion="off"]):is(:not([data-motion="reduced"]), [data-buddy-motion="full"]) #nm-buddy' in CSS08
    assert 'id="avatar-buddy-motion"' in HTML and 'id="about-motion"' in HTML
    # Less motion leaves by a fade, not a cut.
    assert "duration: 260" in _fn("nameMarkBuddyLeave")


def test_the_movement_hint_names_what_always_overrides() -> None:
    # Wrap-up ledger 0927: the Companion movement hint names the reason (OS,
    # setting, perf). Measured (companiontabswitch.js MOVE=always
    # MOTION=reduce): it walked in under the system's reduce and the hint
    # was empty; now it says what it is overriding. Every reason has a line.
    motion = _fn("nameMarkBuddyMotion")
    for reason in ("app-ignored", "os-ignored", "perf-ignored"):
        assert f'"{reason}"' in motion
    why = re.search(r"const NMB_MOTION_WHY = \{(.*?)\n\};", AV, re.S).group(1)
    for reason in ("avatar", "setting", "app", "os", "perf-ignored", "app-ignored", "os-ignored"):
        assert re.search(rf'(^|\s|"){re.escape(reason)}"?:\s*"[A-Z]', why, re.M), reason


def test_it_never_perches_in_a_run_of_words() -> None:
    # The owner: "atlas companion just perched in the middle of the weekly
    # digest". Measured (perchtext.js, 1093x614 and 1440x900, boot and six
    # tab arrivals): on chat at 1093 it rested with 346 square px of words
    # under it; now 0 everywhere, and no arrival is followed by a poof.
    walk = _fn("nameMarkBuddySurfaceWalk")
    assert 'child.closest("p, blockquote, pre, h1, h2, h3, h4, h5, h6")' in walk
    assert '!cs.display.startsWith("inline")' in walk
    choose = _fn("nameMarkBuddyChoose")
    assert "if (!soiled || perch.score > soiled.score) soiled = perch;" in choose and "if (soiled) return soiled;" in choose


def test_the_lab_keeps_what_you_pick_and_no_cap_is_worn_upright() -> None:
    # The owner: "on the avatar lab, it keeps reverting my selected motion
    # and goes to sleep standing with a night cap". Measured (labpin.js):
    # with Live behaviour off, a sleepy from atlas.js's idle clock and a
    # click leave the specimens as picked; on, they follow it.
    lab = (ROOT / "tools" / "avatar-lab.js").read_text(encoding="utf-8")
    assert "window.setAtlasMood = (...args) => (LAB.live ? liveMood(...args) : undefined);" in lab
    assert 'id="live"' in (ROOT / "tools" / "avatar-lab.html").read_text(encoding="utf-8")
    assert "#nm-buddy .nm-atlas { --atl-nightcap: 0; }" in CSS08
    assert '#nm-buddy[data-pose="sit"]:not(.nmb-cap-off) .nm-atlas[data-atlas-mood="sleepy"] { --atl-nightcap: 1; }' in CSS08


def test_faces_in_round_holders_stay_inside_their_circle() -> None:
    # The owner: "in Settings > Personas, the Atlas avatar spills outside its
    # black circle". Measured (personaclip.js): every persona and profile
    # face in Settings clipped to circle(50%).
    css01 = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    assert ":is(.persona-mark, .profile-mark) > :is(.name-mark, .nm-atlas, svg) {\n  clip-path: circle(50%);" in css01


def test_a_face_you_have_not_made_says_so_and_leads_to_its_maker() -> None:
    # The owner: "I havent made a custom avatar yet but it set one randomly
    # ... I as a user might not have even known how to make a custom avatar".
    # Measured (makeavatar.js): the hint under the select shows, its button
    # opens Profile's maker, and the companion's menu offers Create your avatar.
    assert 'id="avatar-buddy-make"' in HTML and 'id="avatar-buddy-make-go"' in HTML
    assert 'openSettingsModal("preferences", "profile-look")' in _fn("nameMarkBuddyMakeIt")
    menu = _fn("nameMarkBuddyMenu")
    assert '"ph:user-circle-plus Create your avatar"' in menu
    assert 'if (value === "custom" && !nameMarkBuddyMade("custom")) nameMarkBuddyMakeIt("custom");' in menu
    assert "nameMarkBuddyMakeHint();" in _fn("mountBuddyCustom")


def test_companions_can_be_saved_applied_renamed_and_deleted() -> None:
    # The owner: "I want to be able to save custom companions like with the
    # custom themes". Measured (buddypresets.js): saved as Atlas, Large, fades
    # only; applied over you at Small, it is Atlas at 1.3 with fades again;
    # renamed; deleted.
    assert 'id="avatar-buddy-presets"' in HTML and 'id="avatar-buddy-preset-save"' in HTML
    for key in ('"avatar-buddy"', '"atlas-look"', '"avatar-buddy-custom"', '"avatar-buddy-size"', '"avatar-buddy-acts-off"', '"avatar-buddy-motion"'):
        assert key in AV[AV.index("const NMB_PRESET_KEYS = [") :][:400], key
    assert "p.name !== nmbPresetRenaming" in _fn("nameMarkBuddySavePreset")
    assert "mountBuddyPresets()" in (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_calm_budget_caps_sudden_acts() -> None:
    # The owner: "make sure that random sudden movements dont happen too
    # frequently or randomly. it cant be distracting for the user". A loud
    # act at most once a gap (60 to 90s), none within 4s of typing or 2s of
    # a scroll.
    got = _run_pure(["nameMarkBuddyCalmAllows"], "[[100000,0,75000,0,Infinity],[100000,50000,75000,0,Infinity],[100000,0,75000,97000,Infinity],[100000,0,75000,0,1500],[100000,20000,75000,90000,5000]].map((a) => nameMarkBuddyCalmAllows(...a))")
    assert got == [True, False, False, False, True]
    decide = _fn("nameMarkBuddyDecide")
    assert "if (!calm && NMB_LOUD_ACTS.includes(act)) continue;" in decide
    assert "if (NMB_LOUD_ACTS.includes(act)) nameMarkBuddyLoud();" in _fn("nameMarkBuddyAct")
    assert "nmb.loudGap = 60000 + Math.random() * 30000;" in _fn("nameMarkBuddyLoud")
    # Its unprompted big moves all ask: the joy bounce, the wander off, the
    # "you are back" wave, the app's cues.
    for name in ("nameMarkBuddyJoy", "nameMarkBuddyWander", "nameMarkBuddyAwake", "nameMarkBuddyCue"):
        assert "nameMarkBuddyCalmAllows(" in _fn(name), name


def test_sleep_holds_through_input_moves_and_tab_switches() -> None:
    # The owner: a click near it "startles for about a second then goes
    # instantly back to sleep"; clicking a tab, "I saw it shoot back up look
    # alive suddenly and look surprised". Measured before and after
    # (companionsleeptab.js): 83 of 461 frames walking while asleep across
    # two tab switches, pokes gave wake, wake, wiggle; after, 0 of 463, in
    # by the sleeping fade both times, pokes give wake, pout, grumpy.
    # atlassleepinput.js COMPANION_ONLY=1: 0 awake frames for a held Ctrl,
    # a click 150px off, three at 80px and a tab click; a direct poke opens
    # its eyes over 1.25s (was 122ms) and it is awake 20s later.
    stir = _fn("nameMarkBuddyStir")
    assert "nameMarkBuddyWake" not in stir and 'buddy.classList.add("nmb-stir");' in stir
    go = _fn("nameMarkBuddyGo")
    assert go.index("if (nameMarkBuddyAsleep(buddy)) {") < go.index('nameMarkBuddyAct("");\n  const char')
    enter = _fn("nameMarkBuddyEnter")
    assert 'return "asleep";' in enter and enter.index("nameMarkBuddyAsleep(buddy)") < enter.index("nameMarkBuddyNoTravel()")
    cue = _fn("nameMarkBuddyCue")
    assert "if (nameMarkBuddyAsleep(buddy)) {" in cue and 'if (cue === "bell") nameMarkBuddyWake(true);' in cue
    assert 'buddy.classList.remove("nmb-sleep", "nmb-drowsy");\n    const face' not in cue
    wake = _fn("nameMarkBuddyWake")
    assert "if (slept) nameMarkBuddyEase(buddy, 7000);" in wake and "nmb.wokeAt = Date.now();" in wake
    assert "nameMarkBuddyEase(buddy, 3200)" in _fn("nameMarkBuddyTick")
    css = CSS08
    assert ":is(.nm-atlas.atl-easing, #nm-buddy.nmb-easing .nm-atlas) :is(.atl-eye-open," in css
    assert "#nm-buddy.nmb-pout .nm-atlas {" in css and "#nm-buddy.nmb-grumpy .nm-atlas {" in css
    # Grumpy comes down through a pout.
    assert "nameMarkBuddyPout(buddy, 5000);" in AV


def test_out_of_sight_never_cancels_the_tab_follow() -> None:
    # Found measuring the owner's perch report (probe, 1093x614): from a
    # dashboard scrolled so its panel was out of sight, a switch to Notes
    # left it away for 5s and more, because `nameMarkBuddySeen` cleared the
    # tab follow's timer. After: on Notes 3s later.
    seen = _fn("nameMarkBuddySeen")
    assert "awayTimer" not in seen and "nmb.sightTimer = setTimeout(wait, 1600);" in seen
    assert "if (nmb.away) return;" in seen
    assert "clearTimeout(nmb.sightTimer);" in _fn("nameMarkBuddyGone")


def test_perches_are_top_edges_outside_card_content_and_measured_for_words() -> None:
    # The owner, again: Atlas sat over the Weekly digest, just under its
    # title; "valid perches are top edges only, and never within a card's
    # content box below its heading", "every settle validated against text
    # rects". Measured (perchwords.js, four tabs at six scroll positions,
    # chosen and settled): 1093x614, 15 of 38 bad before (289 square px of
    # "Start something", hanging from panels, rows inside cards), 0 after;
    # 1440x900, 0 of 38.
    edges = _fn("nameMarkBuddyEdges")
    assert "if (nameMarkBuddyInsideCard(el, box)) continue;" in edges
    assert 'type: "under", kind: "under"' not in edges
    inside = _fn("nameMarkBuddyInsideCard")
    assert "cb.height > innerHeight * 0.6" in inside and "box.top > cb.top + 6" in inside
    choose = _fn("nameMarkBuddyChoose")
    assert "const words = nameMarkBuddyWordsUnder(perch.x, perch.y, perch.pose, perch.legs);" in choose
    assert choose.index('legs: "peek"') < choose.index("if (soiled) return soiled;")
    words = _fn("nameMarkBuddyWordsUnder")
    assert "seen < 400" in words and "nameMarkBuddyScroller(root)" in words


def test_a_perch_that_goes_is_replaced_at_once() -> None:
    # The owner: on Chat "it was left floating mid-panel for seconds after its
    # perch (a button on an empty chat) went away". Measured (perchgone.js,
    # 1093x614, its chat perch removed): floated 2241ms before, 257ms after.
    follow = _fn("nameMarkBuddyFollow")
    lost = follow[follow.index("if (!g.lost) {") :]
    lost = lost[: lost.index("return;")]
    assert "nmb.placeTimer = setTimeout(nameMarkBuddyBeat, 250);" in lost and "nameMarkBuddyQueuePlace()" not in lost


def test_an_act_lets_its_face_go_slowly() -> None:
    # The owner: emotes and acts on a click "must ease back to the prior
    # state, never cut back after a few seconds". Measured
    # (companionactease.js, Atlas, a cheer): its happy eyes went back in
    # 104ms when the act ended, now over 1307ms.
    act = _fn("nameMarkBuddyAct")
    assert "if (was && was !== act && !NMB_FACELESS_ACTS.includes(was)) nameMarkBuddyEase(buddy, 1800);" in act
    assert act.index("nameMarkBuddyEase(buddy, 1800)") < act.index("buddy.classList.remove(`nmb-act-${was}`)")
    # A shorter ease never cuts a longer one (a wake's 7s) short.
    assert "if (until <= (nmb.easeUntil || 0) && buddy.classList.contains(\"nmb-easing\")) return;" in _fn("nameMarkBuddyEase")
    # Declared before the first function that reads them at load.
    assert AV.index("const NMB_LOUD_ACTS") < AV.index("function nameMarkBuddyAct(")


def test_it_takes_a_smaller_size_to_fit_a_small_perch() -> None:
    # The owner: "size and proportion depend on the perch; it scales down
    # where space is small and never overlaps text". Measured (perchwords.js,
    # 1093x614, dashboard scrolled to the end): the only clean perch left was
    # on a card at 0.75 of its size; it took that rather than the bar.
    choose = _fn("nameMarkBuddyChoose")
    assert "nmb.scale = NMB_FIT_SCALE;" in choose and "return { ...small, fit: NMB_FIT_SCALE };" in choose
    assert choose.index("fit: NMB_FIT_SCALE") < choose.index('legs: "peek"')
    move = _fn("nameMarkBuddyMoveTo")
    assert "const size = spot.fit || nameMarkBuddyScaleSaved();" in move and "nameMarkBuddySetSize(size, false);" in move
    assert "#nm-buddy.nmb-fitting .nm-buddy-face { transition: scale" in CSS08


def test_the_atlas_hooks_are_wired() -> None:
    # Wrap-up ledger 0927: atlas.js's hooks for the companion: `data-lean`
    # (its own lean, not the whole figure tipped), `data-atlas-variant` (a
    # new arm variant at each new place; a lie-down's head side), and the
    # pose frames lie-1, lie-2, lie and curl-1, curl, played in order and
    # back, kept across a carry, dropped when picked up.
    assert "buddy.dataset.lean = side < 0 ? \"l\" : \"r\";" in _fn("nameMarkBuddyLean")
    assert 'nameMarkBuddyFrames(buddy, ["lie-1", "lie-2", "lie"]);' in _fn("nameMarkBuddyLieDown")
    assert 'nameMarkBuddyFrames(buddy, ["curl-1", "curl"]);' in _fn("nameMarkBuddyCurlUp")
    assert "nameMarkBuddyKeepFrame(buddy);" in _fn("nameMarkBuddyMoveTo")
    assert "buddy.dataset.atlasVariant = String(nameMarkBuddyPickVariant(3," in _fn("nameMarkBuddyMoveTo")
    assert 'if (act === "lie") nameMarkBuddyLieDown(buddy);' in _fn("nameMarkBuddyAct")
    assert "nameMarkBuddyCurlUp(buddy)" in _fn("nameMarkBuddyTick") and "nameMarkBuddyGetUp(buddy)" in _fn("nameMarkBuddyWake")
    assert "if (/^(lie|curl)/.test(buddy.dataset.pose || \"\")) buddy.dataset.pose = nmb.pose;" in _fn("nameMarkBuddyHalt")
    assert "#nm-buddy.nmb-act-lie:has(.atl-figure-box) .nm-buddy-char { transform: none; }" in CSS08


def test_a_woken_atlas_companion_wakes_atlas_too() -> None:
    # atlassleepinput.js after atlas.js's startle fix: a poke woke the
    # companion but Atlas's mood stayed "sleepy", eyes shut for 3s and
    # more (the click lands on the face's box, not `.nm-atlas`). Now its
    # eyes are open 1255ms after the poke.
    assert 'if (slept && nameMarkBuddyHasAtlas(buddy) && typeof atlasWake === "function") atlasWake();' in _fn("nameMarkBuddyWake")


def test_the_chat_tab_is_a_perch_that_keeps_its_controls_clear() -> None:
    # INBOX 443 (a), the owner: "the companion perches and action surfaces
    # and stuff needs to be properly done for the chat tab". Measured before
    # (companionchat.js, 1440): Atlas sat tucked on the chat dock with its
    # tail curled 22px below its seat, over the input by 13px, and while an
    # answer was written its reading errand put the tail 27 to 29px over
    # Stop. A tucked Atlas still has a tail, so the tail is in its shape.
    shape = _fn("nameMarkBuddyShapeAt1")
    assert 'legs !== "tuck" && document.querySelector("#nm-buddy .atl-figure-box")' not in shape
    assert 'document.querySelector("#nm-buddy .atl-figure-box")) shape.push(' in shape
    # The latest message is never covered, and the chat's dock is its first
    # perch: as a card it was past the dozen card edges looked at (the
    # sidebar's saved chats came first) and was never considered.
    obstacles = _fn("nameMarkBuddyObstacles")
    assert '#chat-messages .msg' in obstacles
    surfaces = AV[AV.index("const NAME_MARK_BUDDY_SURFACES = [") : AV.index("].join", AV.index("const NAME_MARK_BUDDY_SURFACES = ["))]
    assert '".chat-dock"' in surfaces
    assert '.dash-toolbar, .chat-dock, .wb-topbar") ? "dock" : "card"' in AV
    assert 'chat: ["dock", "card", "under", "hang", "bar"]' in AV
    # Reading along while an answer is written: a clean place on the dock's
    # top edge, searched along it, never a fixed x that lands on Stop.
    errand = _fn("nameMarkBuddyChatErrand")
    assert ".chat-dock" in errand and "nameMarkBuddyHits(" in errand
    assert "box.right - NMB_W - 72" not in errand


def test_its_enlarged_view_is_itself_alive_and_still_doing_what_it_was() -> None:
    # INBOX 443 (b), (c), the owner: "the regular companion expanded popup
    # window needs more life and not just a statue"; "if the companion is
    # doing a specific action and i double click it to view it in the
    # enlarged window, I want it to keep doing that action unless poked or
    # something else happens". Measured in a browser by
    # scratchpad/ui-sweeps/companionviewer.js.
    viewer = _fn("openNameMarkViewer")
    # The companion's own element visits the view, so its act, face, props,
    # sleep and pose carry over, and its own timer ends the act.
    assert 'openNameMarkViewer(buddy.dataset.seed || "", { visit: true })' in AV
    assert "nameMarkBuddyVisit(figure)" in viewer and "if (home) home();" in viewer
    visit = _fn("nameMarkBuddyVisit")
    assert "host.appendChild(buddy);" in visit and "anim.finish()" in visit
    assert "visit.home.insertBefore(buddy" in _fn("nameMarkBuddyHome")
    # While it visits nothing moves it, and it cannot be carried off.
    for name in ("nameMarkBuddyMoveTo", "nameMarkBuddyCheck", "nameMarkBuddyFollow", "nameMarkBuddyErrand",
                 "nameMarkBuddyWander", "nameMarkBuddyRide", "nameMarkBuddyDodge", "nameMarkBuddyBeat",
                 "nameMarkBuddyTabChanged", "nameMarkBuddyRefit", "nameMarkBuddyLieRoom"):
        assert "nmb.visit" in _fn(name), name
    assert 'if (event.button !== 0 || nmb.visit) return;' in AV
    # Watched, it plays: a quicker beat, neither Fewer nor the calm budget
    # holding it back, its eyes on the pointer from where it is drawn, and
    # its lines now and then. Reduced motion: a blink and nothing more.
    assert "nmb.visit ? 2500 + Math.random() * 3500" in _fn("nameMarkBuddySchedule")
    decide = _fn("nameMarkBuddyDecide")
    assert "const calm = !!nmb.visit ||" in decide and "fewer: nmb.visit ? 1 : 0.33" in decide
    assert "nameMarkBuddyHeadAt()" in _fn("nameMarkBuddyNotice") and "nameMarkBuddyHeadAt()" in _fn("nameMarkBuddyAim")
    assert "nameMarkSay(host, nameMarkLine(seed))" in viewer
    assert "nameMarkViewerBlinks(figure)" in viewer and "nameMarkIdleQuiet()" in viewer
    # Any other face: the view's quicker beat, and it looks about and fidgets.
    assert "viewer ? 2500 + Math.random() * 3000" in _fn("nameMarkIdleTick")
    assert 'acts.push("look", "shift")' in _fn("nameMarkIdleAct")
    # The dialog's head recipe and one line of description.
    assert 'head.className = "dialog-head nm-viewer-head"' in viewer and '"dialog-head-btn"' in viewer
    assert "Click it to say hello." not in viewer and "nm-viewer-hint" not in viewer
    css = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))
    assert ".nm-viewer-figure > #nm-buddy {" in css and "--nmb-scale: 2.2 !important;" in css


def test_a_double_click_does_not_poke_it_and_no_move_leaves_it_gone() -> None:
    # INBOX 443: the first click of the double-click that enlarges it used
    # to poke it, ending the act the large view was to carry; and the owner:
    # "I also want companion transitions to be better even with reduced
    # motion on". Without travel a move faded out, left nothing, and faded
    # in: now a copy fades out where it was while it fades in where it is.
    assert "pokeTimer = setTimeout(poke, 280);" in AV
    assert "if (!nmb.visit && event.detail >= 2) return;" in AV
    assert "clearTimeout(pokeTimer);\n    pokeTimer = 0;\n    openNameMarkViewer(" in AV
    assert "if (!nmb.act || NMB_FACELESS_ACTS.includes(nmb.act)) nameMarkBuddyAct(\"wiggle\");" in _fn("nameMarkBuddyPet")
    fade = _fn("nameMarkBuddyCrossfade")
    assert "buddy.cloneNode(true)" in fade and "ghost.inert = true;" in fade and "buddy.after(ghost);" in fade
    assert "[{ opacity: 1 }, { opacity: 0 }]" in fade and "[{ opacity: 0 }, { opacity: 1 }]" in fade
    go = _fn("nameMarkBuddyGo")
    assert go.count("nameMarkBuddyCrossfade(buddy, dx, dy,") == 2
    assert "{ opacity: 0, translate:" not in go


def test_it_does_what_the_apps_model_work_is_doing() -> None:
    # INBOX 443, the owner: "the companion doesnt change action for related
    # actions when things are happening like for the tag and file with atlas
    # note function running with atlas reading the note". One hook (fetch,
    # watched once) and a table of the model's addresses, not a call in each
    # feature. Measured by scratchpad/ui-sweeps/companionwork.js.
    table = AV[AV.index("const NMB_WORK = [") : AV.index("];", AV.index("const NMB_WORK = ["))]
    for address in ("reevaluate", "suggest-tags", "improve", "vision-ocr", "caption", "chat|help\\/ask|drafts\\/compose"):
        assert address in table, address
    assert "window.fetch = (input, init = {}) =>" in AV and AV.count("window.fetch = (") == 1
    # The filing is read from the save's answer and the filing poll's.
    assert '/^\\/entries\\/[^/]+\\/filing$/.test(path)' in AV and 'state === "pending"' in AV
    # A stream's end is seen as it is read, its cancel passed on.
    assert "return reader.cancel(reason);" in AV and 'Object.defineProperty(response, "body", { value: body });' in AV
    work = _fn("nameMarkBuddyWork")
    assert 'nameMarkBuddyAct("read", 10 * 60 * 1000);' in work and 'nameMarkBuddyCue("think")' in work
    assert 'nameMarkBuddyCue(kind === "file" ? "carry" : "nod")' in work and 'nameMarkBuddyCue("shrug")' in work
    assert 'nameMarkBuddyCue("rest");' in work
    assert "nod: { ms: 1200, w: 0" in AV and "&.nmb-act-nod .nm-buddy-head" in CSS08
    # No feature file calls it: the hook is the only way in.
    for path in (ROOT / "frontend" / "js").glob("*.js"):
        if path.name != "avatars.js":
            assert "nameMarkBuddyWork(" not in path.read_text(encoding="utf-8"), path.name


def test_its_last_resort_is_never_the_corner_over_a_control() -> None:
    # INBOX 443: on the phone's Chat, an answer down to the dock left no
    # clean edge, and the corner was taken over Send by 32px
    # (companionchat.js, 390). Tucked behind the bottom bar instead.
    choose = _fn("nameMarkBuddyChoose")
    assert "return soiled || corner;" not in choose
    assert "nameMarkBuddyHits(corner.x, corner.y, corner.pose, obstacles, corner.legs) ? tucked : corner" in choose


def test_the_size_ring_is_not_drawn_in_the_enlarged_view() -> None:
    # INBOX 466: the ring at the companion's corner still showed on the
    # visiting companion inside the large view, where the card sizes it.
    assert ".nm-viewer-figure > #nm-buddy .nmb-size-grip { display: none; }" in CSS08


def test_a_folded_sidebar_is_no_perch_and_its_rider_moves_on() -> None:
    # INBOX 462: "the companion perches dont handle collapsed sidebars at
    # least in the chat tab". Measured by companioncollapse.js: before, it
    # sat on in the air over Chat's folded "New chat" (227,726, the rail
    # 48px); after, it walks to a perch it can be seen on.
    shown = _fn("nameMarkBuddyPerchShown")
    assert 'el.closest(".sidebar-collapsed")' in shown and "opacityProperty: true" in shown
    assert 'child.classList.contains("sidebar-collapsed")' in _fn("nameMarkBuddySurfaceWalk")
    assert "nameMarkBuddyPerchShown(el)" in _fn("nameMarkBuddyRestore")
    follow = _fn("nameMarkBuddyFollow")
    assert 'g.el.closest(".sidebar-collapsed")' in follow
    assert follow.index("const folded =") < follow.index("if (!box || (!box.width && !box.height)) {")


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_way_there_is_chosen_by_the_shape_of_the_move() -> None:
    # INBOX 455 (2), the owner: "more and better transitions between
    # positions and moving across different and the same tab(s)". A small
    # step is a hop, a shuffle or a scoot; mostly up or down, a climb; a
    # change of level within three of itself, a leap; on the level, a walk;
    # further, a far way; a flyer floats, and glides when far.
    consts = "const NMB_HOP_SIZES = 0.7; const NMB_FAR_SIZES = 3; const NMB_FAR_POOF_SIZES = 5;"
    src = consts + "\n" + _fn("nameMarkBuddyRoute")
    cases = "[[20,0,0.1],[20,0,0.5],[20,0,0.9],[160,0,0.5],[60,-160,0.5],[10,120,0.5],[150,60,0.5],[400,0,0.5],[400,200,0.5]]"
    script = src + f"\nconsole.log(JSON.stringify({cases}.map(([dx, dy, r]) => nameMarkBuddyRoute(dx, dy, 64, false, false, r)).concat([nameMarkBuddyRoute(100, 0, 64, true, false, 0), nameMarkBuddyRoute(400, 0, 64, true, false, 0), nameMarkBuddyRoute(20, 0, 64, false, true, 0)])));"
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out == ["hop", "shuffle", "scoot", "walk", "climb", "climb", "leap", "far", "far", "float", "far", "walk"]
    # A flyer (Atlas) varies by distance too (the owner, 2026-10-10: "no
    # variation in how it moves around at various distances"): it used to
    # float or glide and nothing else.
    fly = src + "\nconsole.log(JSON.stringify([[20,0,0.1],[20,0,0.9],[60,-120,0.2],[60,-120,0.8],[150,0,0.2],[400,0,0.5]].map(([dx, dy, r]) => nameMarkBuddyRoute(dx, dy, 64, true, false, r))));"
    flown = json.loads(subprocess.run(["node", "-e", fly], capture_output=True, text=True, check=True).stdout)
    assert flown == ["hop", "float", "leap", "float", "float", "far"]
    go = _fn("nameMarkBuddyGo")
    # Far: the geometry says which far ways are open (a walk only on the level).
    assert 'nameMarkBuddyFarWay([...(distance > size * NMB_FAR_POOF_SIZES ? ["poof"] : []), "glide", ...(Math.abs(dy) <= 36 ? ["walk"] : [])])' in go
    # A climb is one path with a corner, its limbs switching at the corner.
    assert 'goingUp ? `0px ${dy}px` : `${dx}px 0px`' in go
    assert 'nameMarkBuddyTravel(buddy, "", at, "climb")' in go
    # Interruptible: a new place mid-move starts at speed from where it is
    # drawn, and a figure cut off in mid-air comes down rather than snapping.
    move = _fn("nameMarkBuddyMoveTo")
    assert "const underway =" in move and 'composite: "add"' in move
    assert "...(underway ? [] :" in _fn("nameMarkBuddySquash")
    # Into a tab from the side of the tab it left.
    assert "nmb.cameFrom = nameMarkBuddyTabSide(nmb.tab, tab);" in _fn("nameMarkBuddyTabChanged")
    enter = _fn("nameMarkBuddyEnter")
    # The side it glides in from is the tab's it left (INBOX 501 lets it
    # glide in from the nearer edge at a start too).
    assert "const fromLeft = side ? side < 0 : x < innerWidth / 2;" in enter
    assert 'else if (reach < innerWidth * 0.5) ways = ["glide", "materialise", "fall"];' in enter


def test_its_limbs_move_with_it() -> None:
    # INBOX 469, the owner: "have the arms and legs be used a bit for various
    # position, action etc changes and transitions". One gesture per way of
    # going, on the individual transform properties (they add to the pose),
    # and none under Reduce motion
    # (the crossfade returns before any is started).
    limbs = _fn("nameMarkBuddyLimbs")
    assert 'id: "nmb-limb"' in limbs and "rotate: `${deg * m}deg`" in limbs and "transform" not in limbs
    # Inside Atlas's drawing they are paced at 20Hz, like the walk's steps.
    assert 'a.id !== "nmb-limb" && a.effect.target.closest("svg.atl-layer")' in _fn("nameMarkBuddyTempo")
    assert "nmbTempo.timer = setTimeout(nameMarkBuddyTempo, 0);" in limbs
    for kind in ("leap", "glide", "float", "cue"):
        assert f"  {kind}: {{ arm:" in AV, kind
    go = _fn("nameMarkBuddyGo")
    assert go.index("nameMarkBuddyCrossfade(buddy, dx, dy, 420);") < go.index('nameMarkBuddyLimbs(buddy, "glide"')
    assert 'nameMarkBuddyLimbs(buddy, "cue", 420)' in _fn("nameMarkBuddyAct")
    for rule in ('.nmb-walking:not([data-travel]) .nmb-arm-l { animation: nmb-arm-swing',
                 '&[data-travel="climb"] .nmb-hold { opacity: 1; }',
                 '&[data-travel="climb"] .nmb-hold-l { animation: nmb-reach'):
        assert rule in CSS08, rule


def _css_rule(css: str, selector: str) -> str:
    start = css.index(selector + " {")
    return css[start : css.index("}", start)]


def test_a_speech_line_is_as_wide_as_its_words_wherever_it_is_said() -> None:
    """INBOX 481, the owner: "these messages on the companion dont render
    properly". In the large view the stage's rule set `right` and the
    figure's rule set `left: 100%`, so the absolute bubble was the 8px
    between them: its background behind the first letter and the rest of
    the `nowrap` line drawn white over the art (measured, 15px box under a
    132px line; `scratchpad/ui-sweeps/companionsay.js` walks every case).
    The box takes its width from its text, and the figure's rule undoes
    the inset it does not use."""
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    base = _css_rule(css, ".nm-say")
    assert "width: max-content" in base
    assert "max-width:" in base and "100vw" in base
    assert "white-space: nowrap" not in base
    viewer = _css_rule(css, ".nm-viewer-figure > #nm-buddy > .nm-say")
    assert "left: 100%" in viewer and "right: auto" in viewer


def test_atlas_pupils_stay_inside_its_eyes():
    """INBOX 497, the owner: "when I have my cursor to the top right of the
    companion or atlas, the pupils basically go off the head and you can
    only see white eyes". Four offsets added up on Atlas's iris, measured at
    up to 3.3 times the room its pupil has (`companioneyes.js`, which walks
    every pose, both looks and four moods with the gaze at the 8 compass
    points and the window's corners). The aim is held inside the unit
    circle, the generated faces' eye moves are not Atlas's, its look scales
    to the room (2 across, 1 up or down), and the mood's own pupil placement
    eases out of the way while it looks at something."""
    aim = _fn("nameMarkBuddyAim")
    assert "const len = Math.hypot(lx, ly);" in aim and "lx /= len;" in aim and "ly /= len;" in aim
    assert "Math.max(-1, Math.min(1, (dx / reach)" not in aim
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    assert "#nm-buddy .nm-atlas .nm-eyes { translate: none !important; }" in css
    assert "#nm-buddy:is(.nmb-attend, .nmb-watch) .nm-atlas .atl-pupil { --atl-px: 0px; --atl-py: 0px; --atl-lean-dir: 0; }" in css
    iris = re.search(r"#nm-buddy:is\(\.nmb-attend, \.nmb-watch\) \.nm-atlas \.atl-iris \{ translate: calc\(var\(--nmb-ex\) \* ([0-9.]+)px\) calc\(var\(--nmb-ey\) \* ([0-9.]+)px\)", css)
    assert iris, "the iris follows the aim"
    gx, gy = float(iris.group(1)), float(iris.group(2))
    # The pupil's room in the almond, less its own size at a mood's larger
    # pupil (1.1), the tightest of the two mirrored eyes, by direction
    # (measured in the eye's own units, companioneyes.js): 1.7 across, 1.26
    # up, 1.12 on the upward diagonals. The look's ellipse stays inside it,
    # and nothing else moves the pupil while it looks.
    import math
    room = {0: 1.7, 22.5: 1.68, 45: 1.44, 67.5: 1.38, 90: 1.44, 270: 1.26, 292.5: 1.12, 315: 1.14, 337.5: 1.28}
    for deg, r in room.items():
        a = math.radians(deg)
        reach = 1 / math.hypot(math.cos(a) / gx, math.sin(a) / gy)
        assert reach <= r, (deg, reach, r)
    assert "--atl-lean-dir: 0; }" in css


def test_an_act_or_a_walk_is_let_go_not_dropped():
    """INBOX 497, the owner: "make the atlas behaviour more smooth and less
    sudden beginning and stopping of actions". Taking an act's class off
    mid-way put every part back at rest in one frame (companionblend.js: 7
    to 22px in a frame against 2 to 4px while the act ran). The parts it
    moved are read first and eased back from there (an `offset: 0`
    keyframe, since a lone keyframe is the end), off the pacer, and not
    under reduced motion; the companion's expressions cross over 0.6s."""
    blend = _fn("nameMarkBuddyBlend")
    assert "nameMarkIdleQuiet()" in blend and "{ ...moved, offset: 0 }" in blend
    assert 'id: "nmb-blend"' in blend
    assert "nameMarkBuddyBlend(buddy, () => buddy.classList.remove(`nmb-act-${was}`));" in _fn("nameMarkBuddyAct")
    assert 'nameMarkBuddyBlend(buddy, () => buddy.classList.remove("nmb-walking"));' in AV
    assert 'a.id !== "nmb-blend"' in _fn("nameMarkBuddyTempo")
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    assert "transition: transform calc(var(--motion-slow) * 3) var(--ease-in-out);" in css


def test_it_comes_on_screen_a_way_that_suits_the_place_and_not_the_same_twice():
    """INBOX 501, the owner: "when atlas or the companion appears on the
    screen it just kinda appears and there is no smooth or creative
    animation for it to happen, or even differences on how it gets there".
    The same perch chose the same entrance every time (the climb down from
    the top bar five times in five on the dashboard, faded up in 136 to
    200ms; companionarrive.js). Each place has the ways that suit it, the
    last one is left out when there is another, and the climb fades up over
    its first half."""
    enter = _fn("nameMarkBuddyEnter")
    assert 'ways = ["down", "materialise"]' in enter and 'ways = ["up", "materialise", "tumble"]' in enter
    assert 'ways = ["walk", "glide", "materialise", "tumble"]' in enter
    assert "const fresh = ways.filter((w) => w !== nmb.lastEnter);" in enter and "nmb.lastEnter = how;" in enter
    assert "opacity: 1, offset: 0.5 }" in enter
    # Reduced motion still fades in where it is.
    assert "if (nameMarkBuddyNoTravel()) {" in enter


def test_it_perches_on_every_library_view_and_on_a_board_never_in_the_air() -> None:
    # INBOX 521, the owner: "the companion perching needs fixing for many of
    # the library tabs as well as for the whiteboard and mindmap". Measured
    # (perchall.js, 1536x864): 10 of 10 Library sub-tabs, board and map on a
    # window bar before; on a dock, a card or the board's toolbar after, feet
    # within 4px of a painted edge everywhere, and at 1440x900 and 390x844.
    walk = _fn("nameMarkBuddySurfaceWalk")
    # An open board's view is 0px tall round its toolbars: looked inside.
    assert "if ((!box.width || !box.height) && depth < 8" in walk
    # Only what paints is a surface; a canvas's own drawing is not walked.
    assert "nameMarkBuddyPainted(cs)" in walk and "!nameMarkBuddyOverCanvas(child, true)" in walk
    # A panel with its own dock holds cards; it is not a content card.
    assert ":scope > .dock, :scope > [role='toolbar']" in _fn("nameMarkBuddyInsideCard")
    # A toolbar over a canvas may be hung from.
    assert 'type: "under", kind: "dock", y: box.bottom' in _fn("nameMarkBuddyEdges")
    # Panels before the controls in them, and a dock looked at along its length.
    perches = _fn("nameMarkBuddyPerches")
    assert "sort((a, b) => ctl(a) - ctl(b))" in perches and 'kind === "dock" ? Math.min(30' in perches
    # Another view in the same tab asks for a new perch, by preference.
    assert "nmb.fresh = true;" in _fn("nameMarkBuddyViewChanged")
    assert "fresh ? null : [nmb.x, nmb.y]" in _fn("nameMarkBuddyBeat")
    # A panel found again by its path must be the same panel.
    assert "again.className === g.cls" in _fn("nameMarkBuddyFollow")
    # A peek ignores the bar's own buttons, not a button floating over it.
    assert "if (box.top >= bar) continue;" in _fn("nameMarkBuddyHits")
    # Reflowed over a control on resize, it moves at once.
    assert "nameMarkBuddyRefitClear(buddy)" in _fn("nameMarkBuddyRefit")
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert " perchall " in gate


def test_the_large_view_of_a_face_is_alive_like_the_companion() -> None:
    # INBOX 591 (the owner: "the regular companion enlarged panel view has no
    # life to it like with atlas and the companion itself"). Measured
    # (scratchpad/ui-sweeps/atlasmo1005-viewerlife.js, a plain face, 2s): 3
    # of 40 elements moved before (its 1.3px breath and a blink), and the
    # pointer moved nothing (its face is not one of the faces on screen the
    # follow listener nudges). Now its weight shifts, its head sways and its
    # arms drift on clocks that never line up, each starting at rest, and its
    # eyes and head turn to the pointer; under reduced motion, none of it.
    gate = ':root:not([data-avatar-motion="off"]):not([data-motion="reduced"]) .nm-viewer-figure > .nm-figure.nm-live {'
    assert gate in CSS08
    block = CSS08[CSS08.index(gate) : CSS08.index("\n  }\n", CSS08.index(gate))]
    for rule in (
        "& .nm-char { animation: nmv-shift 7.3s ease-in-out -3.65s infinite alternate; }",
        "& .nm-char .nm-buddy-head { animation: nmv-head-sway 5.9s ease-in-out -2.95s infinite alternate; }",
        "& .nmb-arm-l { animation: nmv-arm-drift 4.6s ease-in-out -2.3s infinite alternate; }",
        "& .nmb-arm-r { animation: nmv-arm-drift 4.6s ease-in-out -2.3s infinite alternate-reverse; }",
    ):
        assert rule in block, rule
    assert "translate: calc(var(--nmv-x) * 3.4px) calc(var(--nmv-y) * 2.6px);" in block
    assert "rotate: calc(var(--nmv-x) * 7deg);" in block
    reduce = CSS08[CSS08.index("/* INBOX 591: under the system's reduced-motion hint") :]
    assert ".nm-viewer-figure > .nm-figure :is(.nm-char, .nm-buddy-head, .nmb-arm-l, .nmb-arm-r) { animation: none !important; }" in reduce[:800]
    viewer = _fn("openNameMarkViewer")
    # Attached only once the quiet check has returned, so reduced motion and
    # Avatar animation off never follow; Faces follow the pointer off holds.
    assert viewer.index("if (nameMarkIdleQuiet())") < viewer.index("nameMarkViewerFollow(overlay, figure)")
    follow = _fn("nameMarkViewerFollow")
    assert 'document.documentElement.dataset.avatarFollow === "off"' in follow
    assert 'style.setProperty("--nmv-x"' in follow and "requestAnimationFrame" in follow


def test_inbox_669_an_ended_move_is_never_replayed_by_the_pacer() -> None:
    # INBOX 669 (the owner: "when I click atlas, it often starts tilting to
    # the left then just snaps back"; "atlas's arm movements are jerky").
    # The pacer's list is read once a second, so it held an act's animations
    # after the stylesheet had cancelled them, and `pause()` on a cancelled
    # animation restarts it from its first frame: every act's gesture played
    # a second time, stepped at 10Hz (atlas669-clicks.js). It skips them.
    tempo = _fn("nameMarkBuddyTempo")
    skip = tempo.index('if (states[i] === "idle" || states[i] === "finished")')
    assert skip < tempo.index("anim.pause()") and skip < tempo.index("anim.play()")
    # In the large view, drawn 2.2 times over, nothing is stepped.
    assert "|| !!nmb.visit;" in tempo


def test_inbox_669_no_rig_joint_turns_over_four_degrees_a_frame() -> None:
    motion = (ROOT / "frontend" / "js" / "atlas-motion.js").read_text(encoding="utf-8")
    spring = _fn("atlasRigSpring", motion)
    assert "const ATLAS_RIG_MAX_SPEED = 200;" in motion
    assert 200 / 60 < 4
    # Clamped inside the integration step, before the position moves.
    assert spring.index("ATLAS_RIG_MAX_SPEED") < spring.index("j.x += j.v * h;")


def test_inbox_669_arm_gestures_start_and_end_at_the_arms_rest() -> None:
    # A gesture's keyframes began and ended at rotate(0deg), the rest only
    # of a calm standing arm: floating (-28deg) or her held-out arm (-50deg)
    # swung to 0 first and swung past rest at the end (20 degrees a frame).
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    for name in ["nmb-wave", "nmb-wave-l", "nmb-scratch", "nmb-hide-l", "nmb-hide-r", "atl-wave", "atl-buddy-wave", "atl-buddy-wave-f", "atl-buddy-scratch"]:
        body = re.search(r"@keyframes " + re.escape(name) + r" \{(.*?)\n\}", css, re.S).group(1)
        assert not re.search(r"(^|\s)(0%|100%|from|to)[ ,{]", body), name


def test_inbox_669_a_turn_hands_back_about_the_point_it_turned_on() -> None:
    # Hanging by one hand turns the body about the hand; cut short, its
    # class took the point away and the eased turn swung about the new one,
    # 44px off in a frame in the large view (atlas669-clicks.js).
    blend = _fn("nameMarkBuddyBlend")
    held = blend.index("held.push({ anim, el, from });")
    assert 'from.transformOrigin = style.transformOrigin;' in blend[:held]
    assert "el.animate([{ ...moved, offset: 0 }]" in blend


def test_inbox_669_a_lean_held_by_a_rule_is_eased_back_too() -> None:
    # A facepalm leans the body by a plain rule and stops its bob; at its
    # end the bob came back over the rule's transition and the lean went in
    # a frame (the head 9px). The blend reads the body before and after.
    blend = _fn("nameMarkBuddyBlend")
    # The body and, since the jolts pass (2026-10-11), its limbs.
    before = blend.index("querySelectorAll(NMB_BLEND_PARTS)")
    assert ".nm-buddy-char" in AV[AV.index("const NMB_BLEND_PARTS") :][:200]
    after = blend.index("change();\n  for (const { anim, el, from } of held)")
    assert before < after
    tail = blend[after:]
    assert "BODY.filter((key) => style[key] !== from[key])" in tail and "el.animate([{ ...moved, offset: 0 }]" in tail
    # A part the held loop eased is read again for what else moved.
    assert "if (eased.has(el)) continue;" not in tail and "A part eased above is read again" in tail


def test_the_first_entrance_after_an_unlock_is_a_drop_once() -> None:
    # INBOX 707 (the owner: "when loading the app after login, the companion
    # just appears with no animation"). Measured: the usual entrance was a
    # 250ms fade over a 14px drift. The first one of a page load drops in over
    # 640ms and ends at rest; the flag is spent so a tab switch never replays
    # it, and Reduce motion / Avatar animation off return before it.
    enter = _fn("nameMarkBuddyEnter")
    assert "unlockDrop: true" in AV
    drop = enter.index("if (nmb.unlockDrop && !hangs) {")
    assert enter.index("if (nameMarkBuddyNoTravel()) {") < drop, "the reduced-motion fade must come first"
    assert "nmb.unlockDrop = false;" in enter[drop:]
    assert 'translate: "0px 0px", opacity: 1 }' in enter[drop:], "it ends at rest, with no jump"
    assert "{ duration: 640," in enter[drop:]
    # A hanging or bar perch uses its own way out of the bar, never the bare fade.
    assert "const how = unlockFirst ? ways[0] :" in enter


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_rub_and_a_shake_are_strokes_back_and_forth() -> None:
    # INBOX 743, the owner: "more mouse interaction with the companion like
    # rubbing its head. flipping it upside down". A rub is the pointer going
    # back and forth over its head, a flip a shake while it is carried: both
    # read from the same pure count of direction changes, so a pass across it
    # or a hand's tremor is neither.
    def strokes(samples, axis, travel, window):
        return _run_pure(["nameMarkBuddyStrokes"], f"nameMarkBuddyStrokes({json.dumps(samples)}, {axis}, {travel}, {window})")

    rub = [[x, 30, i * 150] for i, x in enumerate([0, 20, 0, 20, 0, 20])]
    assert strokes(rub, 0, 5, 1600) == 4
    # A straight pass, and a tremor of two pixels, are no strokes at all.
    assert strokes([[x, 30, i * 40] for i, x in enumerate(range(0, 60, 6))], 0, 5, 1600) == 0
    assert strokes([[x, 30, i * 60] for i, x in enumerate([0, 2, 0, 2, 0, 2, 0])], 0, 5, 1600) == 0
    # The same rub spread over four seconds is not one rub: only the last
    # 1.6s counts.
    slow = [[x, 30, i * 800] for i, x in enumerate([0, 20, 0, 20, 0, 20])]
    assert strokes(slow, 0, 5, 1600) < 4
    # A shake is the other axis, with longer strokes.
    shake = [[100, y, i * 120] for i, y in enumerate([0, 40, 0, 40, 0])]
    assert strokes(shake, 1, 14, 900) == 3
    assert strokes(shake, 0, 14, 900) == 0


def test_rubbed_and_flipped_are_wired_to_the_pointer() -> None:
    build = _fn("nameMarkBuddyBuild")
    # Rubbed: the pointer over it, not pressing; flipped: shaken while carried,
    # and set right with a dizzy face when it is let go.
    assert "nameMarkBuddyStrokes(rub, 0," in build and "nameMarkBuddyRubbed(" in build
    assert "nameMarkBuddyStrokes(drag.samples" not in build
    assert "nameMarkBuddyStrokes(drag.shake, 1," in build and "nameMarkBuddyFlip(buddy, true)" in build
    assert "nameMarkBuddyFlip(buddy, false)" in build
    rubbed = _fn("nameMarkBuddyRubbed")
    # Never under Still motion, never in a hidden window, and it soothes a sulk.
    assert "nameMarkBuddyStill()" in rubbed and "document.hidden" in rubbed
    assert "nmb.grumpyUntil = 0" in rubbed


def test_nothing_runs_behind_the_lock_and_an_idle_page_is_not_polled() -> None:
    # Brief 34 decision 7: nothing runs hidden or locked; under 1ms of main
    # thread per idle minute. Measured before (companionperf.js IDLE=1): the
    # perch check walked the tab's controls every 1.5s on a page nobody
    # touched, under the lock screen too, and Atlas's tail asked for a frame
    # sixty times a second at rest.
    poll = AV[AV.index("const NMB_CHECK_IDLE_MS") :]
    poll = poll[: poll.index("}, 1500);")]
    assert "nameMarkBuddyCurtained()" in poll and "document.hidden" in poll
    assert "!nmb.checkDue" in poll and "NMB_CHECK_IDLE_MS" in poll
    assert "nameMarkBuddyLockSync();" in _fn("nameMarkBuddyBuild")
    assert '"none"' in _fn("nameMarkBuddyLockSync")
    life = (ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8")
    frame = _fn("atlasTailFrame", life)
    assert 'data-atlas-hidden' in frame and "tail.calm" in frame and "ATLAS_TAIL_CALM_MS" in frame
    # The large view keeps the frame loop: it is the one thing on screen.
    assert '!box.closest(".nm-viewer-figure")' in _fn("atlasTailCalm", life)
    # At rest the tail is a held drawing swayed on the compositor (Brief 34
    # continues, step 2): its layer root's transform, nothing drawn per beat.
    assert "atlasTailRest(tail, p)" in frame and "tail.resting" in frame
    rest = _fn("atlasTailRest", life)
    assert "svg.animate(" in rest and "transform:" in rest and "setAttribute" not in rest
    assert "getComputedStyle(svg).transform" in _fn("atlasTailUnrest", life)
    atlas = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
    sync = _fn("atlasHiddenSync", atlas)
    assert "lock-overlay" in sync and "atlasTailWake(box)" in sync


def test_atlas_changes_face_on_its_own_and_on_more_events() -> None:
    # INBOX 742: "atlas doesnt seem to change emotions alot if at all".
    atlas = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
    drift = _fn("atlasDrift", atlas)
    assert 'atlasMoodNow !== "calm"' in drift and "data-atlas-hidden" in drift
    assert "atlasDriftState.recent" in drift and "35000 + Math.random() * 40000" in drift
    on = _fn("atlasOn", atlas)
    assert 'event === "done"' in on and 'event === "found" || event === "nothing"' in on
    js = ROOT / "frontend" / "js"
    assert 'atlasOn(hits.length ? "found" : "nothing")' in (js / "search.js").read_text(encoding="utf-8")
    assert 'atlasOn("done")' in (js / "shell-reminders.js").read_text(encoding="utf-8")


def test_the_companion_steps_off_a_dock_more_menu():
    """The owner, 2026-10-11, over Notes' Reload / Manage tags menu: "the
    companion still covers some parts of the ui and doesnt move out of the
    way". A dock's "more" menu is an open `<details>`, which the popup list
    missed (measured: the figure now ends clear of the open menu's box)."""
    js = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    popups = re.search(r"const NMB_POPUPS = \"(.*)\";", js).group(1)
    assert 'details[open][class*=\\"menu\\"] > :not(summary)' in popups
    assert '[role=\\"menu\\"]:not(.hidden)' in popups


# The companion's words check counts only drawn text (INBOX 812).


def test_the_companions_words_check_counts_only_drawn_text():
    # INBOX 812: the walk's 400-node cap was spent on text nobody can see (the
    # Ask card's closed history list sits ahead of the answer), so the words
    # under Atlas read as 0 over the "You asked:" line.
    js = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    body = js[js.index("function nameMarkBuddyWordsUnder("):].split("\nconst NMB_WORDS_PX", 1)[0]
    assert "checkVisibility()" in body and "FILTER_REJECT" in body
    assert body.index("n.textContent.trim()") < body.index("seen += 1")


# The companion's menu opens in the enlarged view (owner 2026-10-10).


def test_the_companion_menu_opens_in_the_enlarged_view():
    """"I cant right click to view the menu to change the companion in the
    expanded popup view". Measured: right-click in the enlarged view opens
    the menu on top (z 2601 over the card) with Companion, Atlas look and
    Size only; choosing a persona there switches it and the card stays open."""
    avatars = frontend_text("avatars.js")
    handler = avatars[avatars.index('face.addEventListener("contextmenu"') :][:600]
    assert "if (nmb.visit) return;" not in handler
    menu = frontend_text("companion-menu.js")
    assert 'nmb.visit ? items.filter((item) => item.group === "who") : items' in menu


# The fall is not choppy (owner 2026-10-12, "about 4 frames a second").


def test_a_flight_frame_never_restyles_the_whole_figure():
    """Measured (scratchpad sweep, Atlas, 1440x900, thrown across Notes): the
    flight loop set the inherited custom property `--nmb-sway` on #nm-buddy
    every frame, which restyles every element of the drawing under it; 29
    frames in 1.6 s (p50 50 ms, p95 117 ms, 14 long tasks) against 92 (p50
    16.7 ms) with that one call removed. The lean is written to the three
    elements that wear it (`nameMarkBuddySway`), whose `rotate` is not
    inherited, so a frame restyles only them."""
    avatars = frontend_text("avatars.js")
    assert 'setProperty("--nmb-sway"' not in avatars
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    assert "var(--nmb-sway)" not in css
    sway = _fn("nameMarkBuddySway", avatars)
    assert "style.rotate" in sway and "querySelectorAll" in sway
    # Every writer goes through it: the flight, the drag, and their stops.
    assert avatars.count("nameMarkBuddySway(buddy,") >= 5
