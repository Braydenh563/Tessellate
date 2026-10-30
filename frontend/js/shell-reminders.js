// shell-reminders.js: the clock and welcome, the scroll edge, the phone bar's
// recede, the Reminders tab. Moved out of app.js on 2026-09-26 as one
// contiguous range (INBOX 426 cc, docs/roadmap/agent-remaining/appjs-split.md).
// A classic script sharing app.js's globals, loaded in app.js's old order;
// nothing in an earlier file calls into it while the page loads
// (scratchpad/appjs-map.js --check).

// --- live clock + dashboard welcome ------------------------------------------------
// One ticker updates every visible .live-clock (reminders tab + dashboard),
// so the current time is always on screen, the reminders tab used to give
// no sense of "now" at all (user-reported).
function tickClocks() {
  const now = new Date();
  const time = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const date = now.toLocaleDateString([], {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
  for (const el of document.querySelectorAll(".live-clock")) {
    const t = el.querySelector(".clock-time");
    const d = el.querySelector(".clock-date");
    if (t) t.textContent = time;
    if (d) d.textContent = date;
  }
}
//: **Clocks wake once a minute, aligned to the wall clock** (INBOX 266 (7);
//: WORLD_CLASS_PLAN 10, F6): stopped while the tab is hidden and repainted on
//: return; a `setTimeout` chain to :00.25 of the next minute rather than a
//: 60s interval, which would run up to a minute behind. One helper for the
//: three clocks (header, Dashboard, status bar). Measured, `idle.js`.
const MINUTE_TICK_MARGIN_MS = 250;

//: **One chain for every minute-level painter** (audit 1028 S38): the three
//: clocks and the reminder check used to chain their own timeouts, four wakes
//: a minute for one minute of work. They share this one; the stopper takes a
//: painter off, and the last one off clears the timer.
const minuteTickers = new Set();
let minuteHandle = null;

function armMinuteTick() {
  if (minuteHandle !== null) return;
  const wait = 60000 - (Date.now() % 60000) + MINUTE_TICK_MARGIN_MS;
  //: Named, not an arrow: `scratchpad/ui-sweeps/idle.js` counts wakes by
  //: `fn.name`, and a census of anonymous callbacks cannot tell anyone
  //: which one to look at.
  minuteHandle = setTimeout(function minuteTick() {
    minuteHandle = null;
    for (const paint of [...minuteTickers]) {
      try {
        paint();
      } catch (error) {
        console.error(error);
      }
    }
    if (minuteTickers.size) armMinuteTick();
  }, wait);
}

function startMinuteTicker(paint) {
  paint();
  minuteTickers.add(paint);
  armMinuteTick();
  //: The caller keeps the stopper rather than an id: the chain's timeout has
  //: a different id after every tick.
  return () => {
    minuteTickers.delete(paint);
    if (!minuteTickers.size && minuteHandle !== null) {
      clearTimeout(minuteHandle);
      minuteHandle = null;
    }
  };
}

let clockTimer = null;

function startClockTicker() {
  if (clockTimer === null) clockTimer = startMinuteTicker(tickClocks);
}

function stopClockTicker() {
  if (clockTimer !== null) {
    clockTimer();
    clockTimer = null;
  }
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopClockTicker();
  } else {
    tickClocks();
    startClockTicker();
  }
});

startClockTicker();
tickClocks();

window.addEventListener("resize", () => {
  //: `typeof`, for the reason `refreshArtForTheme` below already records:
  //: `sizeDashWidgets` lives in dashboard.js, which loads after this file,
  //: and the desktop window resizes itself while the scripts are still being
  //: fetched (pywebview shows the window, then sizes it to the saved
  //: geometry). A resize in that gap ran this handler before dashboard.js had
  //: executed, and the owner's log had it: "Uncaught ReferenceError:
  //: sizeDashWidgets is not defined (app.js:22128)". The grid is not on
  //: screen yet at that moment anyway, so skipping the call loses nothing;
  //: dashboard.js sizes its own widgets when it renders.
  if ($("dash-grid") && typeof sizeDashWidgets === "function") sizeDashWidgets();
  // A dragged composer height is only valid for the window it was dragged in.
  refitComposer();
});

// Fade a tab-strip edge only while there is something hidden beyond it.
//
// This was a media query, which is the wrong test: whether the tabs overflow
// depends on how long the AI status pill's text currently is and whether the
// wordmark is showing, not only on the window width. So a fixed breakpoint
// faded a tab bar that fitted perfectly, and left a scrolling one at other
// widths looking as though "Reminders" had been clipped: which is exactly
// the complaint the fade exists to prevent. Measuring is both simpler and
// correct at every width.
//
// Measuring *overflow* was still not enough, and it was reported: "the
// reminders tab in the top bar is partially faded out on the right." A bar
// scrolled to its end has nothing further right, but the old single class
// kept fading anyway: so the last tab was permanently dimmed, which reads as
// a disabled control. The question each edge answers is "is there more THIS
// way", so each edge gets its own class and the answer is recomputed on
// scroll as well as on resize.
// How much room the tab strip has if it stays on the header's own row.
//
// Measured from the header's other children rather than guessed from a
// breakpoint, for the same reason the fade is: whether the tabs fit depends on
// the wordmark, the status pill's current text and which header buttons are
// showing, none of which a width range knows about.
function tabRowSpace() {
  const header = $("top-bar");
  const bar = $("tab-bar");
  if (!header || !bar) return 0;
  const style = getComputedStyle(header);
  const gap = parseFloat(style.columnGap || style.gap) || 0;
  const padding =
    (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0);
  let others = 0;
  let siblings = 0;
  for (const child of header.children) {
    if (child === bar || child.classList.contains("hidden")) continue;
    others += child.getBoundingClientRect().width;
    siblings += 1;
  }
  return header.clientWidth - padding - others - gap * siblings;
}

//: **The room to centre the strip on the window** (INBOX 430, the owner: the
//: top bar "isn't centred at smaller widths", the tabs sat left beside the
//: space switcher while the buttons sat right). Twice the narrower of the two
//: halves: from the window's centre to the nearer group, less a gap. Measured
//: from the groups' own edges, which do not move whichever way the strip is
//: drawn (absolutely placed, filling the gap, or on its own row), so the
//: answer cannot feed itself.
function tabCentreSpace() {
  const header = $("top-bar");
  const bar = $("tab-bar");
  if (!header || !bar) return 0;
  const style = getComputedStyle(header);
  const gap = parseFloat(style.columnGap || style.gap) || 0;
  const box = header.getBoundingClientRect();
  const centre = box.left + box.width / 2;
  let left = box.left + (parseFloat(style.paddingLeft) || 0);
  let right = box.right - (parseFloat(style.paddingRight) || 0);
  for (const child of header.children) {
    if (child === bar || child.classList.contains("hidden")) continue;
    const r = child.getBoundingClientRect();
    if (!r.width) continue;
    if (r.left + r.width / 2 < centre) left = Math.max(left, r.right);
    else right = Math.min(right, r.left);
  }
  return 2 * (Math.min(centre - left, right - centre) - gap);
}

// What the tab strip actually needs, summed from the buttons rather than read
// off the strip's own box.
//
// **This is the fix for a reported bug, and the distinction is the whole
// bug.** The wrap test used `bar.scrollWidth`, which is `max(content,
// clientWidth)`, and the wrapped rule gives the strip `flex-basis: 100%`. So
// the moment it wrapped, its scrollWidth became the *width of the header*,
// which is by definition larger than the room beside the header's other
// children, and the test that decided wrapping was measuring its own output.
// It could not oscillate, as the old comment said. It latched, which is worse:
// one transient narrow moment, a drag of the window edge, a font arriving
// late: and the header stayed two rows tall for the rest of the session.
// Measured: at 900px it wraps and scrollWidth reads 868; widened to 2000px it
// reads 1952 and stays wrapped at 102px tall, where a fresh load at the same
// width renders one row at 60px. That is "the top bar keeps switching and
// permanently changing layout", exactly.
//
// The buttons are `flex: 0 0 auto`, so their widths are the same whichever row
// the strip is on. That is what makes this measurement independent of the
// state it is being used to decide.
function tabContentWidth() {
  const bar = $("tab-bar");
  if (!bar) return 0;
  const style = getComputedStyle(bar);
  const gap = parseFloat(style.columnGap || style.gap) || 0;
  const padding =
    (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0);
  let total = 0;
  let count = 0;
  for (const child of bar.children) {
    //: Tabs only (INBOX 539): the sliding `.tab-glide` is a child too and
    //: takes the active tab's width, so counting it made the strip's need
    //: depend on which tab was selected (485px on Timeline, 470 on Notes at
    //: 1024) and the strip jumped 29px between centred and not.
    if (child.classList.contains("hidden") || !child.matches("[data-tab]")) continue;
    total += child.getBoundingClientRect().width;
    count += 1;
  }
  return total + padding + gap * Math.max(0, count - 1);
}

//: Strip modes in order of preference: "centred" on the window, "gap"
//: (centred between the two groups), "wrapped" (a row of its own). State-free.
function tabBarMode(needed, space, centreSpace) {
  const need = Math.ceil(needed);
  if (need > Math.floor(space)) return "wrapped";
  return need <= Math.floor(centreSpace) ? "centred" : "gap";
}

function syncTabOverflowFade() {
  const bar = $("tab-bar");
  if (!bar) return;
  // A tab you have to scroll to is a tab you will not find. When the strip
  // cannot fit beside the wordmark and the header buttons, it takes a row of
  // its own: where all seven fit with room to spare at any width the app is
  // usable at. Photographed on a 7-tab window: "Dashboard" clipped to "oard"
  // at the left edge, which no amount of edge-fading makes readable.
  const header = $("top-bar");
  // Below 600 the strip is not in the header at all: `dockTabBar` moves it
  // onto the body so `position: fixed` can reach the viewport past the
  // header's backdrop filter. The wrap question is then meaningless, and
  // leaving it to be asked kept `.tabs-wrapped` on a header that had nothing
  // to wrap: measured at 390 the top bar stood at 110px against 58px at 599
  // with identical contents.
  if (header && bar.parentElement !== header) {
    header.classList.remove("tabs-wrapped");
    bar.classList.remove("fade-start", "fade-end");
    return;
  }
  if (header) {
    const needed = tabContentWidth();
    const space = tabRowSpace();
    //: A pure function of the measurements: the old hysteresis read its own
    //: previous class, so 1500 wrapped where 1440 centred depending on the
    //: resize order. No feedback to damp: none of the three numbers moves
    //: with the mode (topbarmode.js sweep).
    const mode = tabBarMode(needed, space, tabCentreSpace());
    header.classList.toggle("tabs-wrapped", mode === "wrapped");
    header.classList.toggle("tabs-centred", mode === "centred");
  }
  // 1px of slack at each end: sub-pixel layout makes scrollWidth exceed
  // clientWidth by a fraction on plenty of widths where nothing is cut off,
  // and a scroll offset lands on .5 of a pixel as often as not.
  const hidden = bar.scrollWidth - bar.clientWidth;
  bar.classList.toggle("fade-start", hidden > 1 && bar.scrollLeft > 1);
  bar.classList.toggle("fade-end", hidden - bar.scrollLeft > 1);
}

// Selecting a tab brings it into view, so the fade is only over a tab you
// are not using. Its `scrollIntoView` shows in profiles as the tab switch's
// own layout flushed here; guarding or deferring it measured no faster.
function revealActiveTab() {
  const active = document.querySelector("#tab-bar button.active");
  if (active && active.scrollIntoView) {
    active.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  syncTabOverflowFade();
}

window.addEventListener("resize", syncTabOverflowFade, { passive: true });
//: Once more when the webfont lands: the boot measurement sees fallback
//: glyphs, and a strip that fit in those can wrap or collide in the real face.
document.fonts?.ready?.then(() => syncTabOverflowFade());
//: And whenever a neighbour changes size: the space switcher gets its name
//: and the notification button appears after boot, each taking room the boot
//: measurement had counted as the strip's. Measured at 1240: the boot sync
//: left the strip unwrapped and 13px under the controls, and the same call
//: a moment later wrapped it (INBOX 195).
if (window.ResizeObserver) {
  const headerWatch = new ResizeObserver(() => syncTabOverflowFade());
  for (const child of $("top-bar")?.children || []) {
    if (child.id !== "tab-bar") headerWatch.observe(child);
  }
}
$("tab-bar")?.addEventListener("scroll", syncTabOverflowFade, { passive: true });

//: **One sliding indicator for every strip** (the owner, 2026-10-04: "a
//: slight css sliding animation ... cheap but looks professional", and
//: 2026-10-05: "Also like the smooth slide across tabs"; 08-consistency.css,
//: "one sliding indicator"). The top bar, the sub-tab strips, every
//: segmented control, the Settings sections and a pane's groups: the strip's
//: `::before` takes the chosen option's place and size at once (custom
//: properties), then a `transform` animation moves it from where it was
//: drawn, so a frame of the glide lays nothing out and a click mid-glide
//: carries on from there. Its length is `--ui-slow`, which Interface
//: animations sets to 0 when off; reduced motion does not stop it. A strip
//: is wired the first time the pointer or the focus reaches it (the top bar
//: at boot); a class, `aria-selected` or `aria-current` change moves it, and
//: a resize or the webfont re-places it.
const GLIDE_STRIPS = "#tab-bar, #settings-nav, .settings-nav-groups, .tabs-line, .seg:not(.seg-multi):not(.wb-export-seg)";
const GLIDE_CHOSEN = ':scope > .active, :scope > [aria-selected="true"], :scope > [role="group"] > .active, :scope > [aria-current="location"]';
function glideStrip(strip) {
  if (!strip || strip.glide) return;
  let at = null;
  const place = (move) => {
    const tab = strip.querySelector(GLIDE_CHOSEN);
    if (!tab || !tab.offsetWidth || strip.closest("#phone-tab-dock")) {
      if (strip.classList.contains("has-glide")) strip.classList.remove("has-glide");
      at = null;
      return;
    }
    const r = tab.getBoundingClientRect();
    const o = strip.getBoundingClientRect();
    const next = {
      tab,
      x: r.left - o.left - strip.clientLeft + strip.scrollLeft,
      y: r.top - o.top - strip.clientTop + strip.scrollTop,
      w: r.width,
      h: r.height,
    };
    if (at && ["x", "y", "w", "h"].every((k) => at[k] === next[k])) return;
    //: Where the indicator is drawn this frame, mid-glide included: its
    //: resting box plus the running transform (origin top left).
    let from = null;
    if (move && at && at.tab !== tab) {
      const m = new DOMMatrix(getComputedStyle(strip, "::before").transform);
      from = { x: at.x + m.e, y: at.y + m.f, w: at.w * m.a, h: at.h * m.d };
    }
    for (const k of ["x", "y", "w", "h"]) strip.style.setProperty(`--glide-${k}`, `${next[k]}px`);
    if (!strip.classList.contains("has-glide")) strip.classList.add("has-glide");
    at = next;
    const tokens = getComputedStyle(strip);
    const ms = parseFloat(tokens.getPropertyValue("--ui-slow")) * 1000;
    if (!from || !ms || !window.KeyframeEffect || !("pseudoElement" in KeyframeEffect.prototype)) return;
    for (const running of strip.getAnimations({ subtree: true })) {
      if (running.effect?.pseudoElement === "::before") running.cancel();
    }
    strip.animate(
      [
        { transform: `translate(${from.x - next.x}px, ${from.y - next.y}px) scale(${from.w / next.w}, ${from.h / next.h})` },
        { transform: "none" },
      ],
      { duration: ms, easing: tokens.getPropertyValue("--ease-in-out").trim() || "ease-in-out", pseudoElement: "::before" }
    );
  };
  strip.glide = place;
  //: `childList` too (the owner, 2026-10-10: "There's overlap on these
  //: settings tabs in the sidebar"): a page's "On this page" list opening or
  //: closing above the chosen row moves the row and not its size, so neither
  //: observer saw it and the fill stayed where the row had been (measured: 20
  //: px under it after an 18 px insert).
  //: Placed a frame later, not in the mutation's microtask: there it read
  //: the new page's layout before the click's own work had finished, and the
  //: frame laid it out a second time (INBOX 1419: 100 to 250ms at 4x CPU).
  let queued = 0;
  new MutationObserver(() => {
    queued ||= setTimeout(() => ((queued = 0), place(true)), 16);
  }).observe(strip, {
    attributes: true,
    attributeFilter: ["class", "aria-selected", "aria-current"],
    childList: true,
    subtree: true,
  });
  if (window.ResizeObserver) {
    const sized = new ResizeObserver(() => place(false));
    sized.observe(strip);
    for (const option of strip.querySelectorAll("button")) sized.observe(option);
  }
  document.fonts?.ready?.then(() => place(false));
  place(false);
}
for (const type of ["pointerover", "focusin"]) {
  document.addEventListener(type, (event) => glideStrip(event.target.closest?.(GLIDE_STRIPS)), { passive: true, capture: true });
}
glideStrip($("tab-bar"));

// Same edge-fade, generalised for every other `.edge-fade` strip (Notes
// sub-tabs, Library sub-tabs, the document sidebar's tabs): none of them
// wrap to their own row the way #tab-bar does, so this is just the fade
// half of syncTabOverflowFade, reused rather than duplicated.
function syncEdgeFade(bar) {
  if (!bar) return;
  const hidden = bar.scrollWidth - bar.clientWidth;
  bar.classList.toggle("fade-start", hidden > 1 && bar.scrollLeft > 1);
  bar.classList.toggle("fade-end", hidden - bar.scrollLeft > 1);
}

for (const bar of document.querySelectorAll(".edge-fade")) {
  syncEdgeFade(bar);
  bar.addEventListener("scroll", () => syncEdgeFade(bar), { passive: true });
  if (typeof ResizeObserver !== "undefined") {
    // Fires when a hidden (0-width) strip becomes visible on tab switch,
    // same as content changing width, no extra wiring needed per tab.
    new ResizeObserver(() => syncEdgeFade(bar)).observe(bar);
  }
}
window.addEventListener("resize", () => {
  document.querySelectorAll(".edge-fade").forEach(syncEdgeFade);
}, { passive: true });

// --- the scroll edge effect (UI_MODERNISATION_PLAN Phase 10, INBOX 100) -----
//
// "Optimize for legibility when content scrolls beneath controls": the bar
// over a scrolling region fades a soft edge under itself while there is
// content passing behind it, and paints nothing at rest. DESIGN.md, "Taken
// from Liquid Glass and the HIG", rule 2.
//
// **One listener, and the bar is chosen by measurement rather than by name.**
// The obvious implementation is a rule per surface, and it is wrong on the
// first surface you try it on: Notes has three candidate bars stacked above
// its list (the top bar, the sub-tab strip, the dock) and only the *last* of
// them has scrolling content under it. A gradient under the other two lands
// on another bar, where it reads as a smudge rather than as depth. So this
// takes the region that actually scrolled, and marks the one bar whose bottom
// edge is sitting against that region's top.
//
// Nothing here knows which tab it is on, which is the point: a new surface
// with a dock over a scroller gets the effect with no new code, and a surface
// that puts its dock somewhere else gets nothing rather than getting it in
// the wrong place.
const SCROLL_EDGE_BARS = "header#top-bar, .dock, .notes-subtabs, .library-subtabs";

// How close a bar's bottom edge has to be to the top of the scrolling region
// to count as "the bar over it". A few pixels of margin between the two is
// normal (`.dock` carries `margin-bottom: var(--space-4)`); half a control
// height is not, and means the bar belongs to something else.
const SCROLL_EDGE_GAP = 24;

// Regions that have actually scrolled at least once. Switching tabs has to
// restore the effect on a page that was left mid-scroll, and re-scanning
// every element of a page for scrollability on each tab change is a lot of
// getComputedStyle for a cosmetic gradient. A scroll event is the cheapest
// possible way to learn which elements are worth asking about.
const scrollEdgeRegions = new Set();

//: What each region last told its bar. The bar over a region only changes
//: when the region crosses its top edge, so a scroll that stays below it
//: (nearly every frame of every scroll) has nothing to measure: without this
//: each frame read every bar's box, which traced at 34 to 87ms per scroll.
const scrollEdgeLastState = new WeakMap();

//: Which region made a bar opaque. Any scroller on the page runs
//: `markScrollEdge`, and it used to clear the flag from every bar that was not
//: its own: an inner pane (the answer, the matching records) scrolling for the
//: first time took the opaque ground off the sub-tab strip the page scroll had
//: just given it, and the strip went see-through over the Ask box (owner,
//: 2026-10-12). Only the region that set a bar may take it back.
const scrollEdgeOwner = new WeakMap();

function markScrollEdge(region, force = false) {
  if (!region || typeof region.getBoundingClientRect !== "function") return;
  const wasScrolled = scrollEdgeLastState.get(region);
  const nowScrolled = region.scrollTop > 1;
  if (!force && wasScrolled === nowScrolled) return;
  scrollEdgeLastState.set(region, nowScrolled);
  // A menu, a dialog or a popover scrolls over the page, not under a bar.
  if (
    region.closest &&
    region.closest(".action-menu, .help-popover, .modal-overlay, #settings-modal, [role='menu']")
  ) {
    return;
  }
  scrollEdgeRegions.add(region);
  const scrolled = region.scrollTop > 1;
  const top = region.getBoundingClientRect().top;
  let best = null;
  let gap = Infinity;
  for (const bar of document.querySelectorAll(SCROLL_EDGE_BARS)) {
    // A bar inside the region scrolls with the content; a bar wrapping it is
    // its container, not a lid over it.
    if (region.contains(bar) || bar.contains(region)) continue;
    const box = bar.getBoundingClientRect();
    if (!box.height) continue;
    const distance = top - box.bottom;
    if (distance < -1 || distance > SCROLL_EDGE_GAP) continue;
    if (distance < gap) {
      gap = distance;
      best = bar;
    }
  }
  for (const bar of document.querySelectorAll("[data-scrolled]")) {
    if (bar !== best && (scrollEdgeOwner.get(bar) || region) === region) bar.removeAttribute("data-scrolled");
  }
  if (best && scrolled) {
    best.setAttribute("data-scrolled", "1");
    scrollEdgeOwner.set(best, region);
  } else if (best) best.removeAttribute("data-scrolled");
  //: A sub-tab strip is sticky *inside* the region it lids (INBOX 529: "hard
  //: to see when scrolled down"), so the loop above skips it and it stayed
  //: see-through over the notes. It takes its surface the same way.
  for (const strip of region.querySelectorAll(".notes-subtabs, .library-subtabs, [data-dock-name=notes]")) {
    if (scrolled) {
      strip.setAttribute("data-scrolled", "1");
      scrollEdgeOwner.set(strip, region);
    } else strip.removeAttribute("data-scrolled");
  }
}

// --- the phone's tab bar recedes on the way down (INBOX 104) ----------------
//
// DESIGN.md's Liquid Glass rule 10: the bar over a scrolling region gives its
// space back while you are reading and takes it again the moment you turn
// round. **Never hidden**, which is the half of the rule that is easy to lose:
// a bar that disappears is a navigation people hunt for, so what recedes is the
// caption, not the bar. 57.6px of bar with words becomes 44px of icons, which
// is still a full row of 44px targets.
//
// It rides on the scroll-edge listener above rather than bringing one of its
// own, which is that block's own warning taken seriously: one capture-phase
// listener, coalesced with `requestAnimationFrame`, choosing its target by
// measuring rather than by name. A per-surface listener here would be seven
// listeners reading layout on every scroll event on a phone.
//
// The page's reservation for the bar (`#status-bar`'s bottom margin, and
// `--page-viewport`) deliberately does *not* change with it. A fixed bar that
// shrinks while the space reserved for it shrinks too moves the content under
// it, which moves the scroll position, which fires the scroll event that
// shrank it: the reservation stays at the full height and the bar is simply
// shorter inside it.
const PHONE_BAR_RECEDE_PX = 12;
//: Per region, because two lists on two tabs are two reading positions, and
//: coming back to one mid-page should not read as a scroll up.
const phoneBarLastTop = new WeakMap();

function markTabBarRecede(region) {
  const dock = $("phone-tab-dock");
  if (!dock) return;
  //: The bar only exists in the phone band; above it there is nothing to
  //: recede, and an attribute left behind would be waiting for the next
  //: resize down.
  if (!window.matchMedia(PHONE_TABS).matches) {
    dock.removeAttribute("data-receded");
    return;
  }
  const top = region.scrollTop;
  const last = phoneBarLastTop.get(region);
  phoneBarLastTop.set(region, top);
  //: At the top of anything the bar is always whole. Arriving at the top of a
  //: list with the captions still folded away is the state nobody asked for,
  //: and it is the state a threshold alone leaves you in.
  if (top <= PHONE_BAR_RECEDE_PX) {
    dock.removeAttribute("data-receded");
    return;
  }
  //: The first scroll event a region ever sends has no previous reading, and
  //: zero is the honest one to compare it with: the event only exists because
  //: something moved, and a region starts at the top. Without this the first
  //: flick of a list is swallowed and the bar recedes on the second.
  const delta = top - (last ?? 0);
  //: A dead band in both directions, so a finger resting on a list does not
  //: flicker the bar between its two heights.
  if (delta > PHONE_BAR_RECEDE_PX) dock.setAttribute("data-receded", "1");
  else if (delta < -PHONE_BAR_RECEDE_PX) dock.removeAttribute("data-receded");
}

let scrollEdgeFrame = 0;
function onScrollEdge(event) {
  const region = event.target === document ? document.scrollingElement : event.target;
  if (!region || region.nodeType !== 1) return;
  if (scrollEdgeFrame) return;
  // Coalesced to one measurement per frame: a scroll event fires far more
  // often than the screen repaints, and this one reads layout.
  scrollEdgeFrame = requestAnimationFrame(() => {
    scrollEdgeFrame = 0;
    markScrollEdge(region);
    //: The same guard the edge effect uses: a menu, a dialog or a sheet
    //: scrolls *over* the page, and the bar it is covering has no business
    //: reacting to it.
    if (
      !region.closest ||
      !region.closest(".action-menu, .help-popover, .modal-overlay, #settings-modal, [role='menu']")
    ) {
      markTabBarRecede(region);
    }
  });
}

// Capture, because scroll does not bubble: without it this would only ever
// hear about the document's own scrolling, which is the one thing this app
// does not do (the page is its own scroll container, see §36A).
document.addEventListener("scroll", onScrollEdge, { capture: true, passive: true });

//: **While a list scrolls, its rows change their hover look at once rather
//: than animating it.** Traced on Notes (a 30-step wheel scroll at
//: 1184x760): with the pointer resting over the list, every card that slid
//: under it ran its 120ms hover transition in and out, and a transition of a
//: card's border or shadow repaints and re-rasterises the whole card every
//: frame. A/B with the rows' transitions off: raster 940ms to 280ms, paint
//: 250ms to 100ms. Hover still shows (the row under the pointer still changes
//: its look); it only stops being animated during the scroll, and the
//: transitions are back 150ms after the last scroll event. One attribute on
//: <html>, set on the first event of a gesture and cleared once, so a scroll
//: costs two style invalidations, not one per frame.
let pageScrollingTimer = 0;
document.addEventListener(
  "scroll",
  () => {
    if (pageScrollingTimer) clearTimeout(pageScrollingTimer);
    else document.documentElement.setAttribute("data-scrolling", "");
    pageScrollingTimer = setTimeout(() => {
      pageScrollingTimer = 0;
      document.documentElement.removeAttribute("data-scrolling");
    }, 150);
  },
  { capture: true, passive: true }
);

function syncScrollEdges() {
  const page = document.querySelector(".tab-page:not(.hidden)");
  let handled = false;
  for (const region of scrollEdgeRegions) {
    if (!region.isConnected) {
      scrollEdgeRegions.delete(region);
      continue;
    }
    if (page && page.contains(region) && region.scrollTop > 1) {
      markScrollEdge(region, true);
      handled = true;
    }
  }
  if (handled) return;
  for (const bar of document.querySelectorAll("[data-scrolled]")) {
    bar.removeAttribute("data-scrolled");
  }
  //: And a tab you have just arrived on shows its bar whole, whatever the tab
  //: you left was scrolled to. `syncScrollEdges` already runs on a tab change
  //: and on a resize, which are the two moments this is true of.
  $("phone-tab-dock")?.removeAttribute("data-receded");
}

window.addEventListener("resize", syncScrollEdges, { passive: true });

// A tab switch is a class change on the pages, not an event this file
// publishes, and observing it here keeps the whole effect in one block
// instead of adding a line to the tab machinery for a gradient.
if (typeof MutationObserver !== "undefined") {
  const scrollEdgeObserver = new MutationObserver(() => syncScrollEdges());
  for (const page of document.querySelectorAll(".tab-page")) {
    scrollEdgeObserver.observe(page, { attributes: true, attributeFilter: ["class"] });
  }
}
// The pill's text arrives with the status polls, long after first paint, and
// changes width when it does, so remeasure whenever the header changes size
// rather than only on window resize.
if (typeof ResizeObserver !== "undefined") {
  // Measured on the next frame rather than inside the callback.
  //
  // Reported from the desktop shell's console: "ResizeObserver loop completed
  // with undelivered notifications." That warning is the browser saying an
  // observer callback changed the layout of something it observes, and this
  // one does exactly that, deciding `.tabs-wrapped` changes the header's
  // height and the strip's width, which is what it is watching. The loop
  // terminates (both measurements are independent of the class now, so the
  // second pass agrees with the first), but it costs a wasted layout every
  // resize and prints an error that looks like a fault.
  //
  // Deferring breaks the cycle: the write lands after the observation phase,
  // and the `queued` flag collapses a burst of resize notifications into one
  // measurement instead of one per element per frame.
  let queued = false;
  const headerObserver = new ResizeObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      syncTabOverflowFade();
    });
  });
  const bar = $("tab-bar");
  if (bar) {
    headerObserver.observe(bar);
    if (bar.parentElement) headerObserver.observe(bar.parentElement);
  }
}
syncTabOverflowFade();

// safeMdSlice/notePreviewText are shared (note previews, the writing room,
// the board's labels, the Library), not dashboard-only (roadmap 88.3).
// A preview slice that never cuts through a markdown marker (longest first,
// `**` before `*`), prefers a sentence end inside the budget, and never
// returns nothing: a marker as the first character once made the row a bare
// "…"; the fallback is a plain slice with the markers stripped.
function safeMdSlice(text, maxChars) {
  if (text.length <= maxChars) return { text, truncated: false };

  // Look for a sentence end in the back half of the budget, so a very long
  // first sentence still gets cut at the budget rather than swallowing it.
  const window = text.slice(0, maxChars);
  const sentence = window.search(/[.!?…](?=\s|$)(?![^\s]*[.!?])/);
  let cut =
    sentence >= Math.floor(maxChars * 0.4) ? window.slice(0, sentence + 1) : window;

  for (const marker of ["**", "~~", "`", "*"]) {
    if ((cut.split(marker).length - 1) % 2 !== 1) continue;
    const balanced = cut.slice(0, cut.lastIndexOf(marker));
    // Only if it leaves something to show. Otherwise drop the markers and
    // keep the words.
    if (balanced.trim()) cut = balanced;
    else cut = cut.replace(/[*~`]/g, "");
    break;
  }
  if (!cut.trim()) cut = window.replace(/[*~`]/g, "");
  return { text: cut, truncated: cut.length < text.length };
}

// One line of a note, as plain text, used wherever a preview genuinely
// can't be rendered markup (a `title` tooltip, an SVG export label, a
// whiteboard card's own text). The dashboard's label-sized widget lists
// (dashboard.js) render real markdown instead, via `safeMdSlice` +
// `renderInlineMarkdown`'s `compact` mode, the same as every other
// label-sized surface in this app.
//: **A `[[link]]`'s visible words, without the syntax its target happens to
//: start with.** Reported: *"note links have inline md not rendered or
//: suppressed, when an ai mentions a note that starts with a note that has a
//: '# text' hashtag md heading, it will write the hashtag"*, with a screenshot
//: of `[[# Girl with bell]]` rendering as "# Girl with bell" in both the
//: editor and the preview.
//:
//: The `[[` picker inserts the target note's first line verbatim, `# ` and
//: all, and `resolveWikiTarget` deliberately keeps matching that form, because
//: every link already written in every existing note is in it. So the raw text
//: has to stay in the document and only the *label* is cleaned, which is what
//: this is: the same treatment `noteLabel` already gives a chat badge, for the
//: same reason (INBOX 35 and 40, "a badge is not a source view"), applied to
//: the other place a note's opening words are shown as a control.
//:
//: Falls back to the raw name rather than to an empty string: a link whose
//: text is nothing but markers is still a link somebody typed, and a button
//: with no words in it cannot be clicked on purpose.
function wikiLinkLabel(name) {
  //: An id-addressed board reads as its title, never as "board:12|House
  //: jobs". The raw form is an address, and an address on a chip is the
  //: same mistake as a url where a link's text should be.
  const ref = boardEmbedRef(name);
  if (ref) return ref.title || (ref.map ? "Mind map" : "Board");
  const clean = notePreviewText(wikiLinkShown(name)).replace(/\s+/g, " ").trim();
  return clean || name;
}

//: **`[[Target|Shown]]`: the part before the first bar names the note, the
//: part after it is what is drawn.** The server reads it this way everywhere
//: (`manager.wiki_link_targets`, tests/test_wiki_links_alias.py); the page drew
//: the whole `Target|Shown` as the chip's words and looked for a note that
//: opens with the whole string (found by the deepflows sweep). A board
//: reference (`board:12|House jobs`) uses the bar for the board's title and is
//: read by `boardEmbedRef`, so it comes back whole from both.
function wikiLinkTarget(name) {
  const text = String(name ?? "");
  if (boardEmbedRef(text)) return text;
  const bar = text.indexOf("|");
  return bar === -1 ? text : text.slice(0, bar).trim();
}

//: The words to draw: after the first bar, or the target when there is no
//: alias (or an empty one, `[[bread|]]`).
function wikiLinkShown(name) {
  const text = String(name ?? "");
  if (boardEmbedRef(text)) return text;
  const bar = text.indexOf("|");
  if (bar === -1) return text;
  return text.slice(bar + 1).trim() || text.slice(0, bar).trim();
}

//: Text shortened for display: cut at the last whole word inside `limit`
//: with an ellipsis, never mid-word. A bare `.slice(0, n)` left labels such
//: as "responds to the blu" all over the app, which reads as a typo rather
//: than as "there is more". A single word longer than the limit is cut hard,
//: still with the ellipsis. Text that fits comes back unchanged.
function clipText(text, limit) {
  const full = String(text ?? "").trim();
  if (full.length <= limit) return full;
  const hard = full.slice(0, Math.max(1, limit - 1));
  const soft = hard.replace(/\s+\S*$/, "");
  return `${(soft.length >= limit / 2 ? soft : hard).replace(/[\s,.;:!?-]+$/, "")}…`;
}

//: GRAPH_PLAN KG4: a note's `---` properties block is never its words (the
//: server's `entry/properties.block_end`: line one, closed within 200 lines).
function stripFrontmatter(text) {
  const source = String(text || "");
  if (!/^---[ \t]*(\n|$)/.test(source)) return source;
  const lines = source.split("\n");
  let at = lines[0].length + 1;
  for (let i = 1; i < Math.min(lines.length, 201); i++) {
    if (/^---[ \t]*$/.test(lines[i])) return source.slice(at + lines[i].length + 1);
    at += lines[i].length + 1;
  }
  return source;
}

function notePreviewText(content) {
  return stripFrontmatter(content || "")
    .replace(/[\u202a-\u202e\u2066-\u2069]/g, "") // bidi controls reorder a label (N20)
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\[\[([^[\]]{1,120})\]\]/g, "$1")
    .replace(
      new RegExp(INLINE_MD.source, "g"),
      // m[10]/m[12] are the image/link *URLs*, only checked for "which branch
      // matched", never shown; a preview shows the image's alt text (or a
      // placeholder, since alt is often empty) and a link's own text, not a
      // raw path nobody asked to read.
      //
      // **These indices were off by two and the previous comment named the
      // wrong groups.** Reported with a screenshot of the Contents page:
      // "Girl with bell undefined", "Leafeon Pokemon image test undefined", 
      // notes whose body ends in an image. The `++colour|text++` highlight
      // alternative was added to INLINE_MD after this replacer was written,
      // and it introduced two capture groups in the middle of the pattern, so
      // every index past it shifted by two. Nothing failed loudly: `??` walked
      // off the end of the branches it knew, the last one returned
      // `undefined`, and `String.replace` stringified that into the preview.
      //
      // It was wrong in three ways at once, and only one of them was visible:
      // an image previewed as "undefined", a link previewed as "undefined",
      // and `==red|highlighted==` previewed as "red", the colour name, because
      // m[4] is the optional colour group and was being read as the text.
      // Verified against the live pattern: g1 code, g2 bold, g3 strike,
      // g4 highlight colour, g5 highlight text, g6 ++colour, g7 ++text,
      // g8 italic, g9/g10 image alt+url, g11/g12 link text+url, g13/g14 run
      // attributes+words (a run previews as its words).
      (...m) =>
        m[1] ?? m[2] ?? m[3] ?? m[5] ?? m[7] ?? m[8] ??
        (m[10] !== undefined ? m[9] || "image" : m[14] !== undefined ? notePreviewText(m[14]) : m[11])
    );
}

// --- reminders tab (Wave D) --------------------------------------------------------

// (The session-scoped `notifiedReminderIds` set went with the dead poller
// above. §36C keeps announced ids in localStorage instead, so a reload does
// not re-announce everything already overdue, which a Set could not survive.)

let reminderFilter = "open"; // open | all | done

// BACKLOG §77's pattern, extended to Reminders (§89 item 1): deliberately
// narrower than Notes' own version. Applies only to the Done group; see the
// note on #reminders-page-size in index.html for why Overdue/Today/Upcoming
// are never paginated in any filter.
let remindersPageSize = prefs.get("reminders-page-size", null) || "all";
let remindersDonePage = 1;

async function loadReminders() {
  //: Every reminder, not the first page. `/reminders` is ordered `due_at`
  //: ascending, so the first page is the *oldest* rows with the ticked-off
  //: ones among them: a notebook whose oldest two hundred are all done would
  //: push everything upcoming off the list, which is exactly the silent loss
  //: paging was added to prevent. Reading to the end keeps the grouping below
  //: unchanged and loses nothing; a real pager is the better answer at
  //: thousands and is written up in `archive/agent-remaining/list-paging.md`.
  //: A sentinel, not `[]`: "you have no reminders" and "the reminders could
  //: not be read" are different facts and only one of them is about the
  //: person. See `surfaceFailed`.
  //: Placeholders on the first load only (INBOX 454: flicking Open, All and
  //: Done flashed them in and out, because a filter with nothing in it is an
  //: empty list and every reload drew them into it). A reload keeps what is
  //: on screen until the answer replaces it.
  if (!loadReminders.loaded) showSkeletons($("reminder-groups"), 3);
  const all = await apiPagedList("/reminders", 200).catch(() => null);
  if (all) loadReminders.loaded = true;
  //: A reminder just made or moved is the soonest one: the due timer follows.
  if (all) armReminderTimer(all);
  clearSkeletons($("reminder-groups"));
  if (!all) {
    surfaceFailed($("reminders-empty"), "your reminders", loadReminders);
    return;
  }
  surfaceRecovered($("reminders-empty"));
  //: Anything that changes a reminder ends up here (setting, ticking off,
  //: deleting, undoing), and every one of those changes a note card's
  //: reminder chip (INBOX 309). Cleared rather than tracked per reminder:
  //: this list is the whole table, so working out *which* note moved would
  //: be a second model of the same data.
  reminderCountsCache.clear();
  const groupsBox = $("reminder-groups");
  groupsBox.replaceChildren();

  const reminders = all.filter((r) =>
    reminderFilter === "all" ? true : reminderFilter === "done" ? r.done : !r.done
  );
  $("reminders-empty").classList.toggle("hidden", all.length > 0);
  $("reminder-clear-done").classList.toggle("hidden", !all.some((r) => r.done));
  // Surface anything due on the tab itself, from wherever you are.
  updateReminderBadge(all);

  const now = new Date();
  const endOfToday = new Date(now);
  endOfToday.setHours(23, 59, 59, 999);
  const groups = { Overdue: [], Today: [], Upcoming: [], Done: [] };
  for (const reminder of reminders) {
    const due = new Date(reminder.due_at);
    if (reminder.done) groups.Done.push(reminder);
    else if (due < now) groups.Overdue.push(reminder);
    else if (due <= endOfToday) groups.Today.push(reminder);
    else groups.Upcoming.push(reminder);
  }

  // Nothing in this filter, but reminders do exist elsewhere.
  if (all.length && !reminders.length) {
    const none = document.createElement("p");
    none.className = "muted";
    none.textContent =
      reminderFilter === "done"
        ? "Nothing completed yet."
        : "All clear: nothing open.";
    groupsBox.appendChild(none);
  }

  const donePagination = $("reminders-done-pagination");
  for (const label of ["Overdue", "Today", "Upcoming", "Done"]) {
    const items = groups[label];
    if (!items.length) continue;
    const heading = document.createElement("h3");
    heading.className = `reminder-group-head group-${label.toLowerCase()}`;
    const text = document.createElement("span");
    text.textContent = label;
    const count = document.createElement("span");
    count.className = "group-count";
    count.textContent = items.length;
    heading.append(text, count);
    groupsBox.appendChild(heading);
    const ul = document.createElement("ul");
    ul.className = "entry-list";
    // Done is the one group this app ever slices, see remindersPageSize's
    // own comment. Every other group renders in full, always, regardless of
    // this control's value.
    const shown =
      label === "Done" ? paginateDoneReminders(items) : items;
    for (const reminder of shown) ul.appendChild(reminderItem(reminder, label));
    groupsBox.appendChild(ul);
  }
  // The bar only means something under a Done group that actually rendered
  // one: paginateDoneReminders already hid/showed it for that case, but a
  // filter with no Done items at all (Open) has to hide it too, since the
  // loop above never reaches the branch that would.
  if (!groups.Done.length) donePagination.classList.add("hidden");
}

function paginateDoneReminders(items) {
  const bar = $("reminders-done-pagination");
  if (remindersPageSize === "all") {
    bar.classList.add("hidden");
    return items;
  }
  const pageSize = Number(remindersPageSize);
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  remindersDonePage = Math.min(Math.max(1, remindersDonePage), totalPages);
  const start = (remindersDonePage - 1) * pageSize;
  bar.classList.remove("hidden");
  $("reminders-done-page-status").textContent = `Page ${remindersDonePage} of ${totalPages}`;
  $("reminders-done-page-prev").disabled = remindersDonePage <= 1;
  $("reminders-done-page-next").disabled = remindersDonePage >= totalPages;
  return items.slice(start, start + pageSize);
}

// A count of due-or-overdue reminders on the Reminders tab button, so you
// notice them from any tab.
function updateReminderBadge(reminders) {
  const button = $("tab-btn-reminders");
  if (!button) return;
  const now = new Date();
  const due = (reminders || []).filter(
    (r) => !r.done && new Date(r.due_at) <= now
  ).length;
  // The status bar's reminder slot is fed from here rather than from its own
  // fetch: this function is the one place both callers of /reminders land, so
  // the bar and the tab badge cannot disagree and no second timer exists to
  // drift from the first.
  reminderCounts = {
    open: (reminders || []).filter((r) => !r.done).length,
    due,
  };
  renderStatusBar();
  syncPhoneMoreRuns();

  let badge = button.querySelector(".tab-badge");
  if (!due) {
    badge?.remove();
    return;
  }
  if (!badge) {
    badge = document.createElement("span");
    badge.className = "tab-badge";
    button.appendChild(badge);
  }
  badge.textContent = ` ${due}`;
  badge.title = `${nounCount(due, "reminder")} due`;
}

async function clearDoneReminders() {
  //: To the end, or this clears the first page's done rows and reports that
  //: count as if it were all of them.
  const all = await apiPagedList("/reminders", 200).catch(() => null);
  if (!all) return toast("Could not load your reminders. Try again.", true, { action: ["Try again", clearDoneReminders] });
  const done = all.filter((r) => r.done);
  if (!done.length) return;
  if (!(await confirmDialog(`Delete ${done.length} completed reminder${done.length === 1 ? "" : "s"}?`))) {
    return;
  }
  //: One Undo for the lot (INBOX 537): they go to the recycle bin and come
  //: back from it (WORLD_CLASS_PLAN 5 item 10).
  //: Every delete is tried; how many failed is said once (audit 2026-10-05,
  //: FE-12), where a silent catch let them come back unexplained, with a Try
  //: again for just those rows.
  const drop = async (rows = done) => {
    const results = await Promise.all(
      rows.map((r) => api(`/reminders/${r.id}`, { method: "DELETE" }).then(() => true, () => false))
    );
    const left = rows.filter((_, i) => !results[i]);
    if (left.length) toast(`Couldn't delete ${left.length} of the reminders.`, true, { action: ["Try again", () => drop(left)] });
    loadReminders();
  };
  const remake = async (rows = done) => {
    const results = await Promise.all(
      rows.map((r) => api(`/reminders/${r.id}/restore`, { method: "POST" }).then(() => true, () => false))
    );
    const left = rows.filter((_, i) => !results[i]);
    if (left.length) toast(`Couldn't bring back ${left.length} of the reminders.`, true, { action: ["Try again", () => remake(left)] });
    loadReminders();
  };
  await drop();
  const action = pushUndo(`Cleared ${done.length} completed reminders`, remake, drop);
  toastAction(`Cleared ${done.length} completed reminder${done.length === 1 ? "" : "s"}.`, "Undo", async () => {
    settleUndoFromToast(action);
    await remake().catch((e) => toast(e.message, true));
  });
}

let editingReminderId = null;

function reminderItem(reminder, label) {
  const li = document.createElement("li");
  li.dataset.id = reminder.id; // flashReminder's own hook, same shape as #entry-list's data-id
  li.dataset.swipeRight = reminder.done ? "Reopen" : "Done"; // the phone's swipe (initRowSwipe)
  if (label === "Overdue") li.classList.add("overdue");
  // Colour-code by priority (styled in CSS: a coloured left border).
  if (reminder.priority && reminder.priority !== "normal") {
    li.classList.add(`priority-${reminder.priority}`);
  }

  if (editingReminderId === reminder.id) {
    //: The form is its own lazy file (reminder-edit.js): only an edit needs it.
    lazyScript("/js/reminder-edit.js").then(() => li.replaceChildren(reminderEditForm(reminder)));
    return li;
  }

  const row = document.createElement("div");
  row.className = "entry-meta";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = reminder.done;
  checkbox.title = reminder.done ? "Reopen" : "Mark done";
  checkbox.setAttribute("aria-label", `${reminder.done ? "Reopen" : "Mark done"}: ${reminder.text || "this reminder"}`);
  checkbox.style.width = "auto";
  checkbox.addEventListener("change", async () => {
    const before = { due_at: reminder.due_at, done: reminder.done };
    //: Completing a repeating reminder rolls it on to its next time, read
    //: by the server from the rule (every weekday, the last Friday of the
    //: month) in this person's own days; its undo puts the due time back.
    if (checkbox.checked && reminder.recurring && reminder.recurring !== "none") {
      const rolled = await apiJson(`/reminders/${reminder.id}/complete?tz_offset_minutes=${-new Date().getTimezoneOffset()}`, { method: "POST" });
      const put = (body) => async () => {
        await apiJson(`/reminders/${reminder.id}`, { method: "PUT", body: JSON.stringify({ ...body, restore: true }) });
        loadReminders();
      };
      pushUndo("Rescheduled a reminder", put(before), put({ due_at: rolled.due_at, done: false }));
      loadReminders();
      toast(`Rescheduled to ${whenText(rolled.due_at)}.`);
      return;
    }
    await reminderPutUndoably(reminder.id, checkbox.checked ? "Completed a reminder" : "Reopened a reminder", before, { done: checkbox.checked });
    //: A reminder ticked off: Atlas looks proud (INBOX 742).
    if (checkbox.checked) atlasOn("done");
  });
  row.appendChild(checkbox);

  const text = document.createElement("span");
  text.className = "reminder-text";
  text.textContent = reminder.text;
  if (reminder.done) text.style.textDecoration = "line-through";
  row.appendChild(text);

  //: The repeat and the early alert ride on a line of their own under the
  //: row (the target's `.entry-links` line): beside the text they squeezed
  //: it to nothing at 320 ("every last Friday of the month" is 118px).
  const when = document.createElement("div");
  when.className = "entry-links";
  //: The coloured edge and the weight said "high" and nothing said it in
  //: words (uisweep-1011: a state shown only by colour), so the line does.
  if (reminder.priority === "high" || reminder.priority === "low") {
    const level = chip(`ph:flag ${reminder.priority === "high" ? "High" : "Low"} priority`, "tag");
    level.title = "Set in Edit this reminder";
    when.appendChild(level);
  }
  if (reminder.recurring && reminder.recurring !== "none") {
    const words = reminder.repeat_words || reminder.recurring;
    const repeat = chip(`ph:repeat ${words}`, "tag");
    repeat.title = `Repeats ${words}`;
    when.appendChild(repeat);
  }
  if (reminder.alert_words) {
    const early = chip(`ph:bell-ringing ${reminder.alert_words}`, "tag");
    early.title = `An alert ${reminder.alert_words} it is due`;
    when.appendChild(early);
  }

  const due = document.createElement("span");
  due.className = "entry-date";
  //: The day and clock, then how far off (dog2 item 8).
  due.textContent = `${parseServerTime(reminder.due_at)?.toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })} · ${relativeWhen(reminder.due_at)}`;
  row.appendChild(due);

  const actions = document.createElement("span");
  actions.className = "entry-actions";
  if (!reminder.done) {
    actions.appendChild(
      smallButton("+1h", "Snooze one hour", () =>
        snoozeReminderTo(reminder, new Date(Date.now() + 60 * 60 * 1000))
      )
    );
    actions.appendChild(
      smallButton("ph:arrow-right Tomorrow", "Snooze to tomorrow 9am", () =>
        snoozeReminderTo(reminder, presetDate("tomorrow"))
      )
    );
  }
  actions.appendChild(
    smallButton("ph:pencil-simple", "Edit this reminder", () => {
      editingReminderId = reminder.id;
      loadReminders();
    })
  );
  //: Delete joins the row's other connections in one menu (INBOX 393, the
  //: integration vocabulary every object already speaks: its note, Atlas,
  //: copy). The two snoozes and Edit stay on the row, being what a reminder
  //: is touched for; four same-sized icons were one more than a row reads.
  //: A deleted reminder goes to the recycle bin (WORLD_CLASS_PLAN 5 item
  //: 10); Undo restores the same reminder, its id and its target kept.
  const deleteReminder = async () => {
    await apiJson(`/reminders/${reminder.id}`, { method: "DELETE" });
    loadReminders();
    const restore = async () => {
      await apiJson(`/reminders/${reminder.id}/restore`, { method: "POST" });
      loadReminders();
    };
    const rebin = async () => {
      await apiJson(`/reminders/${reminder.id}`, { method: "DELETE" });
      loadReminders();
    };
    const action = pushUndo("Moved a reminder to the bin", restore, rebin);
    toastAction(`Moved ${toastName(reminder.text, "the reminder")} to the bin.`, "Undo", async () => {
      settleUndoFromToast(action);
      await restore().catch((e) => toast(e.message, true));
      toast(`Restored ${toastName(reminder.text, "the reminder")}.`);
    });
  };
  const menuItems = [];
  const target = reminderTarget(reminder);
  if (target) menuItems.push({ label: target.label, run: target.open, group: "go" });
  //: D8's third snooze (WORLD_CLASS_PLAN: "10m, 1h, tomorrow"): in the menu,
  //: since the row already holds the two it is touched for most.
  if (!reminder.done) {
    menuItems.push({
      label: "ph:clock-countdown Snooze 10 minutes",
      run: () => snoozeReminderTo(reminder, new Date(Date.now() + 10 * 60 * 1000)),
      group: "snooze",
    });
  }
  menuItems.push(
    { label: "ph:chat-circle Ask Atlas about this", run: () => askAtlasAboutThing("reminder", reminder.text), group: "go" },
    {
      label: "ph:copy Copy text",
      run: async () => {
        if (await copyToClipboard(reminder.text)) toast("Copied.");
      },
      group: "go",
    },
    //: One reminder as a calendar event (`GET /reminders/{id}/export.ics`,
    //: WORLD_CLASS_PLAN section 17 row 7): the way it reaches a phone's
    //: calendar without a server in the middle. Imported twice, it updates
    //: rather than duplicates, since the file's UID is the reminder's own.
    {
      label: "ph:calendar-plus Add to calendar (.ics)",
      run: () => downloadFromApi(`/reminders/${reminder.id}/export.ics`, `reminder-${reminder.id}.ics`),
      group: "go",
    },
    //: The same event on a provider's own add-event page, filled in. The
    //: server only builds the address (`GET /reminders/{id}/calendar-links`);
    //: nothing is sent anywhere until this press opens the page, and a
    //: private note's words are never in it.
    {
      label: "ph:google-logo Add to Google Calendar",
      run: () => openCalendarPage(reminder.id, "google"),
      group: "go",
    },
    {
      label: "ph:microsoft-outlook-logo Add to Outlook",
      run: () => openCalendarPage(reminder.id, "outlook"),
      group: "go",
    },
    { label: "ph:trash Delete", run: deleteReminder, group: "remove", danger: true }
  );
  actions.appendChild(kebabMenu(menuItems, `Actions for the reminder “${reminder.text}”`, { vertical: true }));
  row.appendChild(actions);
  li.appendChild(row);
  if (when.childElementCount) li.appendChild(when);

  if (target && (reminder.target_title || reminder.entry_preview)) {
    const linkRow = document.createElement("div");
    linkRow.className = "entry-links";
    const noteChip = chip(`${target.icon} ${reminder.target_title || reminder.entry_preview}`, "link", target.open);
    noteChip.title = target.label.replace(/^ph:\S+ /, "");
    linkRow.appendChild(noteChip);
    li.appendChild(linkRow);
  }
  return li;
}

//: Opens a reminder in Google Calendar's or Outlook's add-event page, in a new
//: tab that cannot reach back. The tab is opened on the press, before the
//: address is fetched, or a pop-up blocker refuses it; `noopener` in the
//: features would return no handle to point at the address, so the link back
//: is cut by hand.
async function openCalendarPage(id, provider) {
  const tab = window.open("about:blank", "_blank");
  if (tab) tab.opener = null;
  try {
    const links = await apiJson(`/reminders/${id}/calendar-links`);
    if (tab) tab.location.href = links[provider];
    else window.open(links[provider], "_blank", "noopener,noreferrer");
  } catch (error) {
    tab?.close();
    toast(error.message || "Couldn't open the calendar page.", true);
  }
}

//: **What a reminder is about, and the way to it** (WORLD_CLASS_PLAN 1.3,
//: row 15). A reminder used to point at a note only, so a board's said "Open
//: its note" and flashed nothing in the Notes list; a document could not have
//: one. `target_kind` comes from the server, which knows a board from a note.
function reminderTarget(reminder) {
  const kind = reminder.target_kind || (reminder.entry_id ? "note" : null);
  if (kind === "document" && reminder.document_id) {
    return { icon: "ph:file-text", label: "ph:file-text Open its document", open: () => openDocumentFromNote(reminder.document_id) };
  }
  if ((kind === "board" || kind === "map") && reminder.entry_id) {
    const icon = kind === "map" ? "ph:tree-structure" : "ph:squares-four";
    return { icon, label: `${icon} Open its ${kind}`, open: () => openWhiteboardBoard(reminder.entry_id) };
  }
  if (kind === "note" && reminder.entry_id) {
    return { icon: "ph:note-pencil", label: "ph:note-pencil Open its note", open: () => flashEntry(reminder.entry_id) };
  }
  return null;
}

// Relative time that works both ways: "in 2 hours" (future) and "3 days ago"
// (past). relativeTime() only handles the past, which is wrong for reminders.
//: Through `parseServerTime`, like every other reader of a server time
//: (audit 2026-10-05, FE-16): the server keeps a zone-less `due_at` as UTC.
function relativeWhen(iso) {
  const when = parseServerTime(iso);
  if (!when) return "";
  const diff = when.getTime() - Date.now();
  const mins = Math.abs(diff) / 60000;
  if (mins < 0.75) return diff >= 0 ? "now" : "just now";
  const [amount, unit] = mins < 60 ? [mins, "minute"] : mins < 1440 ? [mins / 60, "hour"] : mins < 10080 ? [mins / 1440, "day"] : mins < 86400 ? [mins / 10080, "week"] : [mins / 43200, "month"];
  const value = Math.round(amount);
  const label = `${value} ${unit}${value === 1 ? "" : "s"}`;
  return diff >= 0 ? `in ${label}` : `${label} ago`;
}

// Convert an ISO timestamp to the value a <input type=datetime-local> wants.
function toLocalInputValue(iso) {
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// A named quick-due preset -> a concrete Date.
function presetDate(preset) {
  const d = new Date();
  d.setSeconds(0, 0);
  switch (preset) {
    case "30m":
      d.setMinutes(d.getMinutes() + 30);
      break;
    case "1h":
      d.setHours(d.getHours() + 1);
      break;
    case "3h":
      d.setHours(d.getHours() + 3);
      break;
    case "tonight":
      // If it's already past 7pm, "tonight" can only mean tomorrow evening.
      if (d.getHours() >= 19) d.setDate(d.getDate() + 1);
      d.setHours(19, 0, 0, 0);
      break;
    case "tomorrow":
      d.setDate(d.getDate() + 1);
      d.setHours(9, 0, 0, 0);
      break;
    case "tomorrowpm":
      d.setDate(d.getDate() + 1);
      d.setHours(14, 0, 0, 0);
      break;
    case "weekend": {
      // The coming Saturday morning; on a Saturday or Sunday, the next one.
      const daysToSaturday = (6 - d.getDay() + 7) % 7 || 7;
      d.setDate(d.getDate() + daysToSaturday);
      d.setHours(10, 0, 0, 0);
      break;
    }
    case "nextweek":
      d.setDate(d.getDate() + 7);
      d.setHours(9, 0, 0, 0);
      break;
    default:
      break;
  }
  return d;
}

// --- the due time, split across two fields ------------------------------------
// #reminder-due stays the single source of truth (every caller already writes
// it), and these two keep the visible date/time inputs in step with it. Going
// through one setter is what stops the hidden value and the fields drifting
// apart, which would show one time and save another.

function setDue(localValue) {
  $("reminder-due").value = localValue || "";
  syncPartsFromDue();
  updateDueReadout();
}

function syncPartsFromDue() {
  const raw = $("reminder-due").value;
  const [date, time] = raw.split("T");
  $("reminder-date").value = date || "";
  // datetime-local may carry seconds; the time field wants HH:MM.
  $("reminder-time").value = (time || "").slice(0, 5);
}

function syncDueFromParts() {
  const date = $("reminder-date").value;
  const time = $("reminder-time").value || "09:00";
  // A date with no time is still a usable intention; a time with no date
  // isn't, so that combination is left alone until a date is picked.
  $("reminder-due").value = date ? `${date}T${time}` : "";
  updateDueReadout();
}

// A plain-English echo of whatever is in the datetime field. The raw
// "27/07/2026 11:20 AM" is hard to sanity-check at a glance; "in about 3
// hours: Monday 27 July, 11:20" is not (user-reported).
function updateDueReadout() {
  const readout = $("reminder-due-readout");
  if (!readout) return;
  const raw = $("reminder-due").value;
  if (!raw) {
    readout.textContent = "No time set";
    readout.classList.add("muted");
    return;
  }
  const when = new Date(raw);
  if (Number.isNaN(when.getTime())) {
    readout.textContent = "That date doesn't look right";
    return;
  }
  const minutes = Math.round((when.getTime() - Date.now()) / 60000);
  const pretty = when.toLocaleString([], {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
  let relative;
  if (minutes < 0) relative = "in the past";
  else if (minutes < 1) relative = "in under a minute";
  else if (minutes < 60) relative = `in ${minutes} min`;
  else if (minutes < 60 * 24) relative = `in about ${Math.round(minutes / 60)} h`;
  else {
    const days = Math.round(minutes / (60 * 24));
    relative = `in ${nounCount(days, "day")}`;
  }
  setLabel(readout, `ph:alarm ${relative}: ${pretty}`);
  readout.classList.toggle("error", minutes < 0);
}

// Shift the due time by a number of minutes, from whatever is there now.
function nudgeDue(minutes) {
  const raw = $("reminder-due").value;
  const base = raw && !Number.isNaN(new Date(raw).getTime()) ? new Date(raw) : new Date();
  base.setMinutes(base.getMinutes() + minutes);
  setDue(toLocalInputValue(base.toISOString()));
}

// True when the compose form is untouched, nothing typed anywhere. Only then
// is it safe to move the due time out from under the user.
function reminderComposeIsPristine() {
  return (
    !$("reminder-text").value.trim() &&
    !$("reminder-magic").value.trim() &&
    $("reminder-priority").value === "normal" &&
    $("reminder-recurring").value === "none"
  );
}

// Re-seed the due time whenever the tab is opened on an untouched form, so it
// is always relative to now rather than to whenever the app happened to start
// (user request). A half-written reminder is never disturbed.
function refreshReminderDefaults() {
  if (!$("reminder-due").value || reminderComposeIsPristine()) {
    setDue(defaultDueValue());
  } else {
    syncPartsFromDue();
    updateDueReadout();
  }
}

async function snoozeReminderTo(reminder, when) {
  const before = { due_at: reminder.due_at, done: Boolean(reminder.done) };
  const put = (body) =>
    apiJson(`/reminders/${reminder.id}`, { method: "PUT", body: JSON.stringify({ ...body, restore: true }) });
  await put({ due_at: when.toISOString(), done: false });
  loadReminders();
  //: Undo puts the old time and state back (WORLD_CLASS_PLAN row 32, from
  //: the world-class branch's 2d867a1); `restore` lets a time already past
  //: through (an overdue reminder is the one that gets snoozed).
  const back = async () => {
    await put(before);
    loadReminders();
  };
  const action = pushUndo("Snoozed a reminder", back, async () => {
    await put({ due_at: when.toISOString(), done: false });
    loadReminders();
  });
  toastAction(`Snoozed to ${whenText(when)}.`, "Undo", async () => {
    settleUndoFromToast(action);
    await back();
  });
}

//: **Every reminder act undoes** (TIMELINE_PLAN 11 row 1): create, complete
//: and edit join delete, snooze and clear on the app's one stack. A PUT's
//: inverse is the PUT of the fields it changed, as they were.
async function reminderPutUndoably(id, label, before, after) {
  const put = (body) => async () => {
    await apiJson(`/reminders/${id}`, { method: "PUT", body: JSON.stringify(body) });
    loadReminders();
  };
  await put(after)();
  //: `restore`: the time it goes back to may be past (an overdue one edited).
  pushUndo(label, put({ ...before, restore: true }), put({ ...after, restore: true }));
}

//: Create's inverse is the bin, and its redo the bin's restore, so the
//: reminder that comes back is the same one, its id and target kept.
function reminderMadeUndo(reminder) {
  if (!reminder?.id) return;
  const call = (path, method) => async () => {
    await apiJson(path, { method });
    loadReminders();
  };
  pushUndo("Added a reminder", call(`/reminders/${reminder.id}`, "DELETE"), call(`/reminders/${reminder.id}/restore`, "POST"));
}

async function addReminder(text, dueValue, entryId = null, opts = {}) {
  if (!text || !dueValue) {
    //: Names the one that is missing (not an error: an expected condition).
    toast(!text && !dueValue ? "A reminder needs text and a due time." : !text ? "Write what to be reminded of." : "Pick a due time for this reminder.");
    return false;
  }
  const made = await apiJson("/reminders", {
    method: "POST",
    body: JSON.stringify({
      text,
      due_at: new Date(dueValue).toISOString(),
      entry_id: entryId,
      document_id: opts.documentId ?? null,
      priority: opts.priority || "normal",
      recurring: opts.recurring || "none",
    }),
  });
  // Asked here, when a reminder actually lands, and not on first load, a
  // permission prompt with no context is refused by default, and a refusal is
  // close to permanent (§36C).
  askNotificationPermission();
  reminderMadeUndo(made);
  toast("Reminder set.");
  //: The card's reminder chip (INBOX 309) reads a cached count, and this is
  //: the moment that count became wrong. Dropped rather than adjusted: the
  //: next render asks, and a number kept in step by hand is a number that
  //: eventually is not.
  if (entryId != null) reminderCountsCache.delete(Number(entryId));
  loadReminders();
  return true;
}

// Magic Add (`magicAddReminder`) is quickadd.js's, with the chips.

// The old Wave O poller is gone: a stray setInterval beside the rewritten
// checkDueReminders ran it twice (double requests, a race on the announced
// ids). One poller now; it guards on authToken() (see checkDueReminders).

// Default due time for new reminders: tomorrow morning, 9am.
// The field starts at today's date and the current time, so the common case
// is a small nudge rather than re-typing the whole thing. It used to jump to
// 9am tomorrow, which was wrong far more often than it was right. Rounded up
// to the next five minutes so the default isn't already in the past by the
// time you press Add.
function defaultDueValue() {
  const due = new Date();
  due.setSeconds(0, 0);
  due.setMinutes(Math.ceil((due.getMinutes() + 1) / 5) * 5);
  return toLocalInputValue(due.toISOString());
}

//: "Add all to calendar (.ics)" in the Reminders dock's More menu: every open
//: reminder in this space, one file. The menu closes first so the save
//: dialog (or the desktop's saved-to toast) is not drawn under it.
$("reminders-export-ics")?.addEventListener("click", () => {
  $("reminders-more-menu")?.removeAttribute("open");
  downloadFromApi("/reminders/export.ics", "tessellate-reminders.ics");
});

//: "Import a calendar (.ics)" (TIMELINE_PLAN decision 17): every event a
//: reminder can hold comes in, a bad one is named by its line and the rest
//: kept, and Undo bins exactly the reminders it added.
$("reminders-import-ics").addEventListener("click", () => {
  $("reminders-more-menu").removeAttribute("open");
  $("reminders-import-ics-file").click();
});
$("reminders-import-ics-file").addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  form.append("tz_offset_minutes", String(-new Date().getTimezoneOffset()));
  let result;
  try {
    result = await (await api.upload("/reminders/import.ics", form)).json();
  } catch (error) {
    toast(error.message, true);
    return;
  }
  loadReminders();
  const skipped = result.skipped.length ? ` Skipped ${result.skipped.length}: ${result.skipped[0].reason}${result.skipped.length > 1 ? " and more" : ""}.` : "";
  const message = `Imported ${result.added.length}, updated ${result.updated.length}.${skipped}`;
  const each = (path, method) => async () => {
    for (const id of result.added) await apiJson(path(id), { method });
    loadReminders();
  };
  if (!result.added.length) return void toast(message, "info");
  offerUndo("Imported reminders", message, each((id) => `/reminders/${id}`, "DELETE"), each((id) => `/reminders/${id}/restore`, "POST"));
});

//: In this boot file rather than app.js, whose gzipped size is a ratchet;
//: `initAuth` (spaces-find.js's last line) calls it after this file loads.
//: Answers whether the token is still live (false on a 401), so the boot
//: path can go to the lock screen before drawing a page whose every widget
//: would fail (the owner, INBOX 597: "after the loading screen, it goes to
//: this blank dashboard for a couple seconds then goes to the lock screen").
async function refreshMediaSession() {
  if (!authToken()) return false;
  try {
    //: Through `api` (tests/test_no_bare_fetch.py), silent so a 401 does
    //: not raise the lock screen itself: the boot path does that.
    await api("/auth/media-session", { method: "POST", silent: true });
    return true;
  } catch (error) {
    // Offline or the server is gone: the boot path says so on its own.
    return !error?.isLockout;
  }
}

// --- the opening curtain ---------------------------------------------------------
//: Here rather than in app.js, whose gzipped size is a ratchet
//: (tests/test_static_compression.py); `initAuth` (called at the end of
//: spaces-find.js) and the unlock are its only callers, both after this file.
//: **One curtain, lifted once** (INBOX 577, the owner: "loading up the app is
//: very laggy or visually slow. it is visually not clean and glitchy even
//: though it may not be"). Measured before (`scratchpad/ui-sweeps/
//: smooth1005-boot.js`, 1440x900): the splash cut to the shell the moment
//: `/auth/status` answered, and the shell then built itself in view: the
//: dashboard's greeting, clock and widgets arrived over the next 600ms and
//: pushed the page down twice (layout shift 0.025 after the unlock, 0.073
//: with sign-in off), while the companion played its entrance under the
//: lock screen and was simply there when it lifted.
//:
//: Now whatever covers the window when the app starts (the splash, or the
//: lock screen once the password is in) stays up while the first tab draws,
//: then fades once, over a finished page: the lock card says "Opening…" on
//: its button meanwhile. It waits for `ready` (startApp's preferences and
//: first tab) and never longer than `SHELL_CURTAIN_MAX_MS`, so a slow
//: server shows a page filling in rather than a curtain that never lifts.
//: Two frames after `ready`, so the tab's own render has been laid out and
//: painted under it. The companion waits for the lift (`nameMarkBuddyCurtained`).
const SHELL_CURTAIN_MAX_MS = 1500;
function curtainShell(ready) {
  const root = document.documentElement;
  root.classList.add("shell-curtain");
  let lifted = false;
  const lift = () => {
    if (lifted) return;
    lifted = true;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      root.classList.remove("shell-curtain");
      hideBootSplash();
      liftLockScreen();
    }));
  };
  //: And the dashboard's widgets, when it is the first tab (`dashSettled`).
  Promise.resolve(ready).then(() => window.dashSettled).then(lift, lift);
  setTimeout(lift, SHELL_CURTAIN_MAX_MS);
}

//: The lock screen after a password: it fades rather than vanishing, and
//: takes its `hidden` (which everything else reads as "unlocked") once the
//: fade is done. A prompt borrowing the overlay is not this.
function liftLockScreen() {
  const overlay = $("lock-overlay");
  setBusy($("lock-submit"), false);
  if (overlay.classList.contains("hidden") || overlay.dataset.mode === "prompt") return;
  overlay.classList.add("lock-leaving");
  const gone = () => {
    overlay.classList.remove("lock-leaving");
    // Not when it was asked for again meanwhile (a lock pressed during the fade).
    if (overlay.dataset.mode !== "prompt" && prefs.get("token", null)) overlay.classList.add("hidden");
  };
  setTimeout(gone, reducedMotionWanted() ? 0 : 220);
}

// ---- from app.js (search-boot-1005): buildSelect ----
// Moved whole. Every use is in this file, so it is not needed before this file loads.

// A <select> from [value, label] pairs, with one option preselected.
function buildSelect(options, selected) {
  const select = document.createElement("select");
  select.className = "small-select";
  for (const [value, label] of options) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (value === selected) option.selected = true;
    select.appendChild(option);
  }
  return select;
}
