// sheets-selects.js: resizable sidebars, sheets and their dismissal, the select
// menu recipe. Moved out of app.js on 2026-09-26 as one contiguous range (INBOX
// 426 cc, docs/roadmap/agent-remaining/appjs-split.md). A classic script
// sharing app.js's globals, loaded in app.js's old order; nothing in an earlier
// file calls into it while the page loads (scratchpad/appjs-map.js --check).

// --- resizable sidebars ----------------------------------------------------------
// Both sidebars were a fixed 230px. In the chat list that left about four
// characters of a conversation's name visible, which is no name at all, and
// how much room a sidebar deserves depends on your screen and your titles,
// not on a number picked once.
//
// Drag the edge to resize. The width is remembered per sidebar, and there's a
// keyboard path because a mouse-only control is one that some people simply
// cannot use.

const SIDEBAR_MIN = 170;
const SIDEBAR_MAX = 520;
// Per-sidebar starting widths. The chat list carries the most text per row, 
// a title, then a date/turns/tokens line, so it starts wider than a list of
// one-word category names.
const SIDEBAR_DEFAULTS = { "chat-sidebar": 300, sidebar: 260, "doc-sidebar": 260, "skills-sidebar": 300 };
const sidebarDefault = (id) => SIDEBAR_DEFAULTS[id] || 260;

function sidebarWidth(id, fallback = 260) {
  const saved = Number(prefs.get(`sidebarWidth:${id}`, null));
  return Number.isFinite(saved) && saved >= SIDEBAR_MIN ? saved : fallback;
}

// Below this the layout stacks into one column and there is no column to size.
//
// **Moved from 720 to 820** (UI_MODERNISATION_PLAN.md Phase 9, band 3: an
// iPad in portrait is 768 or 810 CSS px). The number has to move here and in
// the stylesheet together, and this is the half that is easy to forget:
// `applySidebarWidth` writes an inline `grid-template-columns` when the
// layout is *not* stacked, and an inline style beats a media query, so a CSS
// breakpoint at 820 with this constant left at 720 would have left every
// width from 721 to 819 silently two-column with a stylesheet that said
// otherwise. Verified at 721, 780 and 819 after the move.
const STACKED_LAYOUT = "(max-width: 819.98px)";

function layoutIsStacked() {
  return window.matchMedia(STACKED_LAYOUT).matches;
}

//: The most of the window a sidebar may take. Reported directly: "the ui
//: needs to seemlessly adapt and perfect itself on any resolution and not
//: just be squashed but still fit somehow."
//:
//: Measured before this existed: the sidebar was its saved pixel width at
//: *every* viewport: 260px at 1920 (14% of the window, fine) and 260px at
//: 820 (32%, leaving the notes column 459px). The sidebar never gave up a
//: pixel, so the content absorbed the entire difference. That is the
//: "squashed but still fit somehow" feeling, and its cause is a stored
//: absolute width applied to a relative space.
//:
//: A stylesheet `clamp()` cannot fix it: the width is written as an inline
//: `grid-template-columns` on the parent (below), and an inline style beats
//: every rule. So the cap belongs here, where the number is decided.
const SIDEBAR_VIEWPORT_SHARE = 0.24;

//: The iPad-landscape band (UI_MODERNISATION_PLAN.md Phase 9, 820-1100).
//:
//: The share above is a ratio, and a ratio alone gets this band wrong in
//: both directions: 24% of 1024 is 246px, which is a desktop sidebar on a
//: tablet, and 24% of 820 is 197px, which is a different sidebar again on
//: the same device held the other way. A band is supposed to look like one
//: design, so this one names an absolute ceiling instead: 12rem, the width
//: at which a category name and a conversation title still read.
//:
//: It has to live here rather than in the stylesheet. The sidebar's width is
//: written as an inline `grid-template-columns` on the parent (see
//: applySidebarWidth below), and an inline style beats every rule in every
//: file, media query or not. A `clamp()` in CSS would have looked correct,
//: passed review, and done nothing at all.
const SIDEBAR_TABLET_MAX = 192;
const SIDEBAR_TABLET_BAND = "(min-width: 820px) and (max-width: 1099.98px)";

function layoutIsTablet() {
  return window.matchMedia(SIDEBAR_TABLET_BAND).matches;
}

//: What the sidebar may actually occupy right now, the user's own width
//: where there is room for it, less where there is not, never below the
//: floor a category name needs to stay readable.
function sidebarFittedWidth(saved) {
  const cap = Math.max(SIDEBAR_MIN, Math.round(window.innerWidth * SIDEBAR_VIEWPORT_SHARE));
  const banded = layoutIsTablet() ? Math.min(cap, SIDEBAR_TABLET_MAX) : cap;
  return Math.min(saved, banded);
}

//: The skill logs sidebar sits *after* `main` in `.skills-split`
//: (INBOX 430), where every other resizable sidebar sits before it in its
//: own grid: a template written "column, then 1fr" put the width where the
//: content should stretch and the content where the sidebar should sit,
//: which is why this set exists rather than reading DOM order at call time
//: (an aside mid-resize is not necessarily still where it started).
const RIGHT_SIDE_SIDEBARS = new Set(["skills-sidebar"]);

function applySidebarWidth(aside, width, { remember = true } = {}) {
  const clamped = Math.min(Math.max(Math.round(width), SIDEBAR_MIN), SIDEBAR_MAX);
  // **The user's choice is stored, the fitted width is applied**, and the
  // split matters: storing the fitted one would mean dragging a window
  // narrow permanently shrank a preference the user set on a wide screen,
  // with no way to notice it had happened. Widening the window restores it.
  // `remember: false` is for the re-fit on resize, which is the app
  // reacting rather than the user choosing.
  if (remember) prefs.set(`sidebarWidth:${aside.id}`, String(clamped));
  aside.style.setProperty("--saved-width", `${clamped}px`);

  if (layoutIsStacked()) {
    aside.parentElement.style.removeProperty("grid-template-columns");
    return clamped;
  }

  const onRight = RIGHT_SIDE_SIDEBARS.has(aside.id);
  const rail = "48px";
  const fitted = `${sidebarFittedWidth(clamped)}px`;
  if (aside.classList.contains("sidebar-collapsed")) {
    aside.parentElement.style.gridTemplateColumns = onRight
      ? `minmax(0, 1fr) ${rail}`
      : `${rail} minmax(0, 1fr)`;
  } else {
    aside.parentElement.style.gridTemplateColumns = onRight
      ? `minmax(0, 1fr) ${fitted}`
      : `${fitted} minmax(0, 1fr)`;
  }
  return clamped;
}

//: Re-fit every sidebar as the window changes size, not only when it crosses
//: the one stacking breakpoint below. Without this the cap above would apply
//: at load and then go stale the moment anyone resized a window, which is
//: the normal way a desktop app is used, and exactly the case the report was
//: about. `remember: false`: this is not the user choosing a width.
let sidebarRefitTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(sidebarRefitTimer);
  sidebarRefitTimer = setTimeout(() => {
    for (const id of ["sidebar", "chat-sidebar", "doc-sidebar", "skills-sidebar"]) {
      const aside = document.getElementById(id);
      if (aside?.dataset.resizable) {
        applySidebarWidth(aside, sidebarWidth(id, sidebarDefault(id)), { remember: false });
      }
    }
  }, 120);
});

// Rotating a phone, or dragging a desktop window narrow, crosses the
// threshold without reloading: so re-decide then too.
// Rotating a phone, or dragging a desktop window narrow, crosses a band
// boundary without reloading, so both boundaries re-decide the width. The
// tablet band is listed with the stacking one because forgetting it is
// exactly the failure the band exists to prevent: an iPad turned from
// portrait to landscape would come back with the portrait sheet's width.
for (const query of [STACKED_LAYOUT, SIDEBAR_TABLET_BAND]) {
  window.matchMedia(query).addEventListener("change", () => {
    applySidebarSheetMode(layoutIsStacked());
    for (const id of SIDEBAR_IDS) {
      const aside = document.getElementById(id);
      if (aside?.dataset.resizable) {
        applySidebarWidth(aside, sidebarWidth(id, sidebarDefault(id)), { remember: false });
      }
    }
  });
}

// --- the sidebars, as sheets (Phase 9, bands 3 and 4) -------------------------
// Stacked, a sidebar used to sit *above* the content: at 390 the Notes
// categories card was 48px of chrome before the first note and the chat list
// was 99px before the first message, and on a tablet in portrait it is worse
// because there is more of it. A panel you are not using should not cost the
// panel you are using any height at all.
//
// So below 820 the three sidebars leave the flow and become sheets that slide
// in from the left, over the content, with a rail left showing that carries
// the collapse toggle they already have. No new control, no new gesture: the
// button that opens and closes a sidebar on a desktop opens and closes the
// sheet on a tablet.
//
// The state is a class of its own rather than a reuse of `.sidebar-collapsed`,
// and the reason is worth writing down. `.sidebar-collapsed` means something
// specific on a desktop, a 48px rail with a hover-peek, and it carries
// `width: 48px !important` plus a `:hover` rule at higher specificity that
// re-expands it. Reusing it here would mean fighting two `!important`
// declarations from a later block, and a touch-hold would have triggered the
// hover-peek. Instead the desktop classes are taken off while stacked and put
// back on the way out, so none of those rules apply and there is nothing to
// fight.
const SIDEBAR_IDS = ["sidebar", "chat-sidebar", "doc-sidebar", "skills-sidebar"];

function eachSidebar(fn) {
  for (const id of SIDEBAR_IDS) {
    const aside = document.getElementById(id);
    if (aside) fn(aside, id);
  }
}

function applySidebarSheetMode(stacked) {
  eachSidebar((aside) => {
    if (stacked) {
      // Remember the desktop state exactly once, so a second call inside the
      // band cannot record "not collapsed" over the user's real preference.
      if (aside.dataset.deskCollapsed === undefined) {
        aside.dataset.deskCollapsed = aside.classList.contains("sidebar-collapsed") ? "1" : "";
      }
      aside.classList.remove("sidebar-collapsed");
      aside.parentElement?.classList.remove("layout-sidebar-collapsed");
      // A sheet opens closed. Arriving with the content already covered is
      // the failure a sheet exists to avoid.
      aside.classList.remove("sidebar-sheet-open");
    } else {
      aside.classList.remove("sidebar-sheet-open");
      if (aside.dataset.deskCollapsed) {
        aside.classList.add("sidebar-collapsed");
        aside.parentElement?.classList.add("layout-sidebar-collapsed");
      }
      delete aside.dataset.deskCollapsed;
    }
  });
}

// --- the dismissal every sheet keeps, wherever it is built -------------------
// UI_MODERNISATION_PLAN.md Phase 11. `openSheet` builds a modal bottom sheet
// out of nothing and owns its own listeners for the life of that one overlay.
// The two sheets that predate it are a different object: an element that is
// already on the page and *becomes* a sheet inside a band (the three sidebars
// below 600, the graph's popup at the bottom of the map). Those cannot be built
// by `openSheet` without losing what each was built for, and the reason is
// written in DESIGN.md's index rather than rediscovered: the sidebar sheet
// keeps a rail on screen with its own opener on it, which is the way back, and
// the graph's is deliberately not modal, because the map it came from has to
// stay visible for the sheet to have an origin.
//
// What they must share is the *dismissal*, which is the half a hand-built sheet
// always gets wrong: Escape, a press outside, and the focus going back to the
// control that opened it. This is that half, in one place, so a third in-place
// sheet inherits all three rather than inventing them.
//
// Captured, both of them, which is the one behavioural change this extraction
// makes: the sidebar sheet's Escape was a bubbling listener, so any handler
// bound further down the page that stops an Escape took it first. `openSheet`
// has always captured for exactly that reason.
function wireInPlaceSheetDismissal({ find, close }) {
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const open = find();
    if (!open) return;
    event.stopPropagation();
    close(open);
  }, true);
  document.addEventListener("pointerdown", (event) => {
    const open = find();
    if (!open || open.contains(event.target)) return;
    close(open);
  }, true);
}

// Escape closes an open sheet, and a tap on the content behind it does too.
// Both are what a sheet means; without them the only way back is the rail,
// which is the half of the panel the sheet is covering.
function initSidebarSheetDismissal() {
  wireInPlaceSheetDismissal({
    find: () => document.querySelector(".sidebar-sheet-open"),
    close: (open) => {
      open.classList.remove("sidebar-sheet-open");
      //: The rail's own button is the opener, so focus goes back to it: the
      //: same contract `openSheet`'s `returnFocus` keeps.
      const opener = open.querySelector(".sidebar-collapse-toggle");
      opener?.setAttribute("aria-expanded", "false");
      opener?.focus();
      //: Below 600 that toggle is not on the page once the sheet is shut
      //: (the head's `.phone-sidebar-opener` stands for it), so the focus
      //: went nowhere, measured by `sheetdismiss.js` at 390: activeElement
      //: was the body. The phone's own opener takes it there.
      const phoneOpener = open.id
        ? document.querySelector(`.phone-sidebar-opener[aria-controls="${CSS.escape(open.id)}"]`)
        : null;
      if (phoneOpener) {
        phoneOpener.setAttribute("aria-expanded", "false");
        if (document.activeElement !== opener) phoneOpener.focus();
      }
    },
  });
}

//: The name a folded sidebar shows on its rail (see makeSidebarResizable).
const SIDEBAR_RAIL_NAMES = {
  sidebar: "Categories",
  "chat-sidebar": "Chats",
  "doc-sidebar": "Documents",
  "skills-sidebar": "Skill logs",
};

//: A resize grip says its value (WCAG 4.1.2: a focusable separator requires
//: `aria-valuenow`). Read by an observer, so every way of resizing reports it.
function trackSeparatorValue(handle, panel, min, max, axis = "width") {
  handle.setAttribute("aria-valuemin", String(min));
  handle.setAttribute("aria-valuemax", String(max));
  //: A horizontal separator (the code editor's output panel) reports its height.
  const tall = axis === "height";
  const size = () => (tall ? panel.getBoundingClientRect().height : panel.getBoundingClientRect().width);
  const write = (px) => {
    const now = Math.round(px);
    if (!now) return; // hidden or folded away: keep the last real value
    handle.setAttribute("aria-valuenow", String(Math.min(Math.max(now, min), max)));
    handle.setAttribute("aria-valuetext", `${now} pixels ${tall ? "tall" : "wide"}`);
  };
  write(size() || min);
  if (typeof ResizeObserver === "function") {
    new ResizeObserver((entries) => {
      const box = entries[entries.length - 1].borderBoxSize?.[0];
      write((tall ? box?.blockSize : box?.inlineSize) ?? size());
    }).observe(panel);
  }
}

function makeSidebarResizable(aside) {
  if (!aside || aside.dataset.resizable) return;
  aside.dataset.resizable = "1";
  applySidebarWidth(aside, sidebarWidth(aside.id, sidebarDefault(aside.id)));

  const handle = document.createElement("div");
  handle.className = "sidebar-resize";
  // A real slider: screen readers announce it, and arrows resize it.
  handle.setAttribute("role", "separator");
  handle.setAttribute("aria-orientation", "vertical");
  handle.setAttribute("tabindex", "0");
  handle.setAttribute("aria-label", "Resize the sidebar: arrow keys, or drag");
  aside.appendChild(handle);
  trackSeparatorValue(handle, aside, SIDEBAR_MIN, SIDEBAR_MAX);

  const collapseBtn = document.createElement("button");
  collapseBtn.className = "sidebar-collapse-toggle";
  // Sentence case (DESIGN.md copy rules), and a name that is not the
  // whitespace between the three icons (INBOX 424).
  collapseBtn.type = "button";
  collapseBtn.title = "Hide or show the sidebar";
  collapseBtn.setAttribute("aria-label", "Hide or show the sidebar");
  collapseBtn.innerHTML = `
    <svg class="icon-expanded" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
      <line x1="9" y1="3" x2="9" y2="21"></line>
    </svg>
    <svg class="icon-collapsed" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
      <line x1="15" y1="3" x2="15" y2="21"></line>
    </svg>
    <i class="ph ph-push-pin icon-peek" aria-hidden="true"></i>
  `;
  //: The peek's icon is a pin, "keep it open": it was drawn as a bell, the
  //: notifications glyph (INBOX 432).
  collapseBtn.addEventListener("click", () => {
    // Stacked, this same button is the sheet's opener. The desktop classes
    // are not applied in that band (applySidebarSheetMode takes them off), so
    // toggling them here would put back exactly the rules the sheet was built
    // to avoid fighting.
    if (layoutIsStacked()) {
      const open = aside.classList.toggle("sidebar-sheet-open");
      collapseBtn.setAttribute("aria-expanded", String(open));
      return;
    }
    const folded = aside.classList.toggle("sidebar-collapsed");
    aside.parentElement.classList.toggle("layout-sidebar-collapsed", folded);
    //: Remembered, like its width (INBOX 432: a reload unfolded it).
    try {
      prefs.set(`sidebarCollapsed:${aside.id}`, folded ? "1" : "0");
    } catch {
      /* storage blocked: this session only */
    }

    // The grid column, for whichever side this sidebar is on (INBOX 430):
    // routed through applySidebarWidth so the left/right branch lives in one
    // place rather than being re-decided here, which is how a right-side
    // sidebar's collapse used to put its rail column on the wrong edge.
    const saved = Number(prefs.get(`sidebarWidth:${aside.id}`, null)) || sidebarDefault(aside.id);
    applySidebarWidth(aside, saved, { remember: false });
  });
  aside.appendChild(collapseBtn);
  let foldedBefore = false;
  try {
    foldedBefore = prefs.get(`sidebarCollapsed:${aside.id}`, null) === "1";
  } catch {
    /* storage blocked */
  }
  if (foldedBefore && !layoutIsStacked() && !aside.classList.contains("sidebar-collapsed")) collapseBtn.click();

  //: What a folded sidebar shows (INBOX 425, the owner: the collapsed
  //: sidebars were "white plain"). A 48px column with one button in it read
  //: as an empty panel rather than as the sidebar, put away. Its name, set
  //: sideways under the button, says which sidebar it is and is a second way
  //: to open it; the same recipe as the skill logs' folded column.
  const railName = SIDEBAR_RAIL_NAMES[aside.id];
  if (railName) {
    const rail = document.createElement("button");
    rail.type = "button";
    rail.className = "sidebar-rail-name";
    rail.textContent = railName;
    rail.title = `Show ${railName.toLowerCase()}`;
    rail.tabIndex = -1; // the toggle above is the keyboard's way in
    rail.addEventListener("click", () => collapseBtn.click());
    aside.appendChild(rail);
  }

  //: A right-side sidebar's handle sits on its *left* edge (the one
  //: touching `main`, see the CSS override next to `.sidebar-resize`), so
  //: the same rightward drag that widens a left-side sidebar narrows one on
  //: the right: the pointer is moving away from the content either way, but
  //: which direction "away" is depends on which side the content is on.
  const onRight = RIGHT_SIDE_SIDEBARS.has(aside.id);
  const startDrag = (event) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = aside.getBoundingClientRect().width;
    document.body.classList.add("resizing-sidebar");

    const move = (e) => {
      const delta = e.clientX - startX;
      applySidebarWidth(aside, startWidth + (onRight ? -delta : delta));
    };
    const stop = () => {
      document.body.classList.remove("resizing-sidebar");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  };
  handle.addEventListener("pointerdown", startDrag);

  handle.addEventListener("keydown", (event) => {
    const step = event.shiftKey ? 40 : 12;
    const current = aside.getBoundingClientRect().width;
    // Same reasoning as the drag: Left/Right name a screen direction, and
    // which way that grows a right-side sidebar is the mirror of a left one.
    const grow = onRight ? "ArrowLeft" : "ArrowRight";
    const shrink = onRight ? "ArrowRight" : "ArrowLeft";
    if (event.key === shrink) {
      event.preventDefault();
      applySidebarWidth(aside, current - step);
    } else if (event.key === grow) {
      event.preventDefault();
      applySidebarWidth(aside, current + step);
    } else if (event.key === "Home") {
      event.preventDefault();
      applySidebarWidth(aside, sidebarDefault(aside.id)); // back to the default
    }
  });
  // Double-click the handle to reset, the convention everywhere else.
  handle.addEventListener("dblclick", () =>
    applySidebarWidth(aside, sidebarDefault(aside.id))
  );
}

function initResizableSidebars() {
  for (const id of SIDEBAR_IDS) {
    const aside = document.getElementById(id);
    if (aside) makeSidebarResizable(aside);
  }
  makeWebPanelResizable(document.getElementById("web-panel"));
  applySidebarSheetMode(layoutIsStacked());
  initSidebarSheetDismissal();
}

// The Notes sidebar used to mirror `main`'s height into its own `min-height`
// via a ResizeObserver watching `main`. That's exactly backwards for a grid
// row with `align-items: stretch`: setting the sidebar's height taller grows
// the shared row, which stretches `main` to fill it, which re-fires the
// observer with a bigger `main.offsetHeight`, an unbounded feedback loop
// (reported as the sidebar "continuously expanding"). The chat sidebar never
// needed this: it just sets `height: 100%` and lets the grid resolve it (see
// `#chat-sidebar` in style.css). Removed here too: `.layout`'s own
// `align-items: stretch` plus the `min-height: var(--page-sticky-h)` floor in
// style.css already produces the right height with no JS and nothing to loop.

// The web panel (§36G) isn't a grid column like the three sidebars above, it
// is a flex sibling of #chat-main inside <main>, sized by `flex-basis:
// clamp(19rem, 30%, 26rem)` (see style.css). That clamp is a considered
// default, not a placeholder, it keeps the column readable without a drag , 
// so unlike the sidebars, this only overrides it once the user actually asks
// to, and "reset" removes the inline style entirely rather than reapplying a
// remembered default. Below WEB_PANEL_NARROW the panel takes the whole of
// <main> (see the media query in style.css); an inline flex-basis would beat
// that stylesheet rule regardless of the media query; so it stays suppressed
// there and comes back once the window is wide enough again.
const WEB_PANEL_MIN = 280;
const WEB_PANEL_MAX = 900;
const WEB_PANEL_NARROW = "(max-width: 1100px)";

function webPanelIsNarrow() {
  return window.matchMedia(WEB_PANEL_NARROW).matches;
}

//: The widest the panel may be is also bounded by the conversation beside
//: it. `innerWidth * 0.6` alone let the panel take 864px of a 1440 window
//: whose <main> is about 1,100px, which left the chat 210px wide with its
//: composer folded into a column (measured, `scratchpad/ui-sweeps/webpanel.js`).
const WEB_PANEL_CHAT_MIN = 360;

function webPanelMaxWidth(panel) {
  const main = panel.parentElement;
  const room = main ? main.getBoundingClientRect().width - WEB_PANEL_CHAT_MIN : Infinity;
  return Math.max(WEB_PANEL_MIN, Math.min(WEB_PANEL_MAX, window.innerWidth * 0.6, room));
}

function applyWebPanelWidth(panel, width) {
  const clamped = Math.min(Math.max(Math.round(width), WEB_PANEL_MIN), webPanelMaxWidth(panel));
  try {
    prefs.set("webPanelWidth", String(clamped));
  } catch {
    /* blocked storage: the width holds for this session */
  }
  if (webPanelIsNarrow()) {
    panel.style.removeProperty("flex");
    panel.style.removeProperty("width");
  } else {
    // 0 0 prevents flex shrinkage so the drag math stays pixel-perfect
    panel.style.flex = `0 0 ${clamped}px`;
    panel.style.width = `${clamped}px`;
  }
  return clamped;
}

function resetWebPanelWidth(panel) {
  prefs.remove("webPanelWidth");
  panel.style.removeProperty("flex");
  panel.style.removeProperty("width");
}

window.matchMedia(WEB_PANEL_NARROW).addEventListener("change", () => {
  const panel = document.getElementById("web-panel");
  if (!panel?.dataset.resizable) return;
  const saved = Number(prefs.get("webPanelWidth", null));
  if (Number.isFinite(saved) && saved >= WEB_PANEL_MIN && !webPanelIsNarrow()) {
    panel.style.flex = `0 0 ${saved}px`;
    panel.style.width = `${saved}px`;
  } else {
    panel.style.removeProperty("flex");
    panel.style.removeProperty("width");
  }
});

function makeWebPanelResizable(panel) {
  if (!panel || panel.dataset.resizable) return;
  panel.dataset.resizable = "1";

  const saved = Number(prefs.get("webPanelWidth", null));
  if (Number.isFinite(saved) && saved >= WEB_PANEL_MIN) applyWebPanelWidth(panel, saved);

  const handle = document.createElement("div");
  handle.className = "sidebar-resize web-panel-resize";
  handle.setAttribute("role", "separator");
  handle.setAttribute("aria-orientation", "vertical");
  handle.setAttribute("tabindex", "0");
  handle.setAttribute("aria-label", "Resize the web panel, arrow keys, or drag");
  panel.appendChild(handle);
  trackSeparatorValue(handle, panel, WEB_PANEL_MIN, WEB_PANEL_MAX);

  const startDrag = (event) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = panel.getBoundingClientRect().width;
    document.body.classList.add("resizing-sidebar");

    // The panel sits to the *right* of the conversation, so dragging the
    // handle left (a negative clientX delta) is what widens it, the mirror
    // image of the sidebars, whose handle is on their trailing (right) edge.
    const move = (e) => applyWebPanelWidth(panel, startWidth - (e.clientX - startX));
    const stop = () => {
      document.body.classList.remove("resizing-sidebar");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  };
  handle.addEventListener("pointerdown", startDrag);

  handle.addEventListener("keydown", (event) => {
    const step = event.shiftKey ? 40 : 12;
    const current = panel.getBoundingClientRect().width;
    // Same mirrored direction as the drag: ArrowLeft widens, ArrowRight narrows.
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      applyWebPanelWidth(panel, current + step);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      applyWebPanelWidth(panel, current - step);
    } else if (event.key === "Home") {
      event.preventDefault();
      resetWebPanelWidth(panel);
    }
  });
  handle.addEventListener("dblclick", () => resetWebPanelWidth(panel));
}

// A ⋯ button that opens a small menu. Built from the same pieces as the note
// overflow menu so the two behave identically, one open at a time, click away
// or Escape to close, arrow keys to move.
function makeMenuItem(label, title, run) {
  return { label, title, run };
}

// The same menu as `kebabMenu`, with a worded opener instead of a "⋯".
//
// Reported: "a lot of the dropdown menus aren't the same ui style??", and
// they were not, because some of them were not this component at all. A
// native `<select>` used as an action list is drawn by the operating system:
// it cannot take the app's padding, radius, hover or icons, which is exactly
// the "tight and right up against the edge of the text" the report describes.
// A `<select>` is the right control for *choosing a value in a form*; an
// action that happens the moment you pick it is a menu, and now uses the
// app's own one.
//
// `openerClass` because the opener has to belong to the row it stands in: on
// a `.small` toolbar it is a `.small` button, and on the capture panel's
// 40px attach row it is a plain `.ghost` one beside "Attach" and "From
// library". Defaulted to what every existing caller already got, so adding
// the parameter changed nothing that was already on screen.
function labelledMenu(label, items, ariaLabel, openerClass = "ghost small") {
  const wrap = document.createElement("span");
  wrap.className = "menu-wrap";

  const menu = document.createElement("div");
  menu.className = "action-menu hidden";
  menu.setAttribute("role", "menu");

  const opener = document.createElement("button");
  opener.type = "button";
  opener.className = openerClass;
  setLabel(opener, label);
  opener.title = ariaLabel;
  opener.setAttribute("aria-label", ariaLabel);
  opener.setAttribute("aria-haspopup", "menu");
  opener.setAttribute("aria-expanded", "false");
  opener.addEventListener("click", (event) => {
    event.stopPropagation();
    const willOpen = menu.classList.contains("hidden");
    if (willOpen) openActionMenu(menu, opener);
    else closeActionMenus();
  });

  //: `group` is honoured here as `kebabMenu` honours it (a hairline where the
  //: name changes): a worded menu past five rows was drawn ungrouped
  //: (menus.js sweep, "Add this note to a document": 7 rows, no groups).
  let lastGroup = null;
  for (const item of items) {
    if (lastGroup !== null && item.group && item.group !== lastGroup) {
      const rule = document.createElement("div");
      rule.className = "menu-sep";
      rule.setAttribute("role", "separator");
      menu.appendChild(rule);
    }
    if (item.group) lastGroup = item.group;
    const button = document.createElement("button");
    button.className = "menu-item";
    button.setAttribute("role", "menuitem");
    setLabel(button, item.label);
    if (item.title) button.title = item.title;
    menuRowFits(button, item.title || "");
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      closeActionMenus();
      await item.run();
    });
    menu.appendChild(button);
  }
  wireMenuKeyboard(menu, opener);
  wrap.append(opener, menu);
  return wrap;
}

// --- every <select> in the app wears the app's own menu ---------------------
//
// **The last surface the stylesheet could not reach.** Reported repeatedly,
// and finally with a screenshot of the model picker: a native `<select>`
// popup is drawn by the operating system, not the page. It ignores the
// app's palette, radius, padding, hover and icons entirely, which is why
// dropdowns looked like a different program, why their text sat "right up
// against the edge", and why no amount of CSS on `select` ever fixed it.
// `select` itself is styled (the closed control matches); only the *popup*
// was out of reach, and there is no CSS that reaches it.
//
// So the popup is replaced rather than restyled. The real `<select>` stays
// in the DOM and stays the source of truth: every `.value` read, `.options`
// write and `change` listener in the rest of the app keeps working
// untouched, which is what makes this safe to apply everywhere at once
// instead of rewriting dozens of call sites. The visible control is a
// button plus a `role="listbox"`, using the same `openActionMenu` /
// `closeActionMenus` plumbing as every other menu here, so it inherits
// their positioning, flip-when-clipped and click-away behaviour for free.
//
// Selects are repopulated all over this app (models, categories, personas),
// often long after first render, so a MutationObserver re-reads the options
// rather than trusting a one-time build.
const SELECT_ENHANCED = "data-enhanced-select";

function enhanceSelect(select) {
  if (!select || select.hasAttribute(SELECT_ENHANCED)) return;
  // A multi-select is a different control with different semantics, and
  // nothing in this app uses one; leave it to the browser rather than
  // guessing at a listbox that supports multiple selection.
  if (select.multiple || select.size > 1) return;
  if (select.closest("[data-no-select-enhance]")) return;
  select.setAttribute(SELECT_ENHANCED, "1");

  const shell = document.createElement("span");
  shell.className = "select-shell";

  const opener = document.createElement("button");
  opener.type = "button";
  opener.className = "select-opener";
  opener.setAttribute("aria-haspopup", "listbox");
  opener.setAttribute("aria-expanded", "false");

  const valueText = document.createElement("span");
  valueText.className = "select-value";
  const caret = document.createElement("i");
  caret.className = "ph ph-caret-down select-caret";
  caret.setAttribute("aria-hidden", "true");
  opener.append(valueText, caret);
  //: **A select whose closed face is an icon and a caret** (`data-select-icon`
  //: on the select, a Phosphor class). For a picker that is an action rather
  //: than a setting, whose resting text is only ever its own name ("Text
  //: colour…"): in a toolbar that name is a word-sized box saying what the
  //: icon beside it already says. The word stays in the opener, visually
  //: hidden (`.select-opener-icon`), and the opener's name is the select's
  //: aria-label below, so nothing is lost to a screen reader.
  if (select.dataset.selectIcon) {
    const icon = document.createElement("i");
    icon.className = `ph ${select.dataset.selectIcon} select-icon`;
    icon.setAttribute("aria-hidden", "true");
    opener.prepend(icon);
    opener.classList.add("select-opener-icon");
  }

  const menu = document.createElement("div");
  menu.className = "action-menu select-menu hidden";
  menu.setAttribute("role", "listbox");

  select.parentNode.insertBefore(shell, select);
  shell.append(select, opener, menu);
  // Reported repeatedly, on different selects, as the same shape: the
  // model picker (Settings) and the note editor's category picker both
  // spilled off the edge of whatever scrolling/backdrop-filter ancestor
  // they opened inside: ".modal-content" for the first, the note card's
  // own stacking context for the second. `wireEscapedActionMenu` (this
  // file, above) already exists for exactly this, it was built for the
  // Library's Documents kebab and reparents an open menu to <body>,
  // positioning it from the opener's own rect so no ancestor's overflow or
  // stacking context can clip it, but it was only ever wired to that one
  // menu. Every one of this app's 51+ selects shares the same
  // `.select-menu`/`openActionMenu` shape, so wiring it here once covers
  // all of them instead of chasing each report to a different select.
  wireEscapedActionMenu(shell);

  // The native control keeps doing its job (form value, validation, the
  // label association) but stops being what you see or tab to, the opener
  // carries the keyboard now.
  select.classList.add("select-native-hidden");
  select.tabIndex = -1;
  select.setAttribute("aria-hidden", "true");

  //: The name the select already has, wherever it was given: its own
  //: `aria-label`, the element `aria-labelledby` points at, or the `<label
  //: for>` beside it. Only the first was read, so a select named the ordinary
  //: HTML way reached a screen reader as "Choose an option": measured on
  //: Settings, Account's idle-lock select and the Graph's colour select.
  const labelledBy = (select.getAttribute("aria-labelledby") || "")
    .split(/\s+/)
    .map((id) => id && document.getElementById(id)?.textContent.trim())
    .filter(Boolean)
    .join(" ");
  const label =
    select.getAttribute("aria-label") ||
    labelledBy ||
    select.labels?.[0]?.textContent.trim().replace(/\s+/g, " ") ||
    select.title ||
    "Choose an option";
  opener.setAttribute("aria-label", label);
  opener.title = select.title || label;

  const syncValue = () => {
    const chosen = select.options[select.selectedIndex];
    valueText.textContent = chosen ? chosen.textContent.trim() : "";
    //: **The name contains what is written on the button** (WCAG 2.5.3, Label
    //: in Name; axe `label-content-name-mismatch`, 22 findings in 2026-10-10's
    //: sweep, every sort and model picker). "Sort notes" was the whole name
    //: while the face read "Newest first", so a person saying the words they
    //: can see ("click newest first") reached nothing. Now "Sort notes: Newest
    //: first". An icon-only opener shows no text, so keeps the plain label.
    if (!opener.classList.contains("select-opener-icon")) {
      const shown = valueText.textContent;
      opener.setAttribute(
        "aria-label",
        shown && !label.toLowerCase().includes(shown.toLowerCase()) ? `${label}: ${shown}` : label
      );
    }
    opener.disabled = select.disabled;
    for (const row of menu.querySelectorAll("[role='option']")) {
      const on = row.dataset.value === select.value;
      row.setAttribute("aria-selected", String(on));
      row.classList.toggle("is-chosen", on);
    }
  };

  //: **An option the app has hidden is not offered here either.** Measured
  //: on the OCR workspace's reader picker: `#ocr-reader` carries
  //: `<option value="ocr" hidden>AI vision model</option>`, which
  //: `ocrLoadReaders` unhides only on a machine that really has two
  //: different readers, and this stand-in listed all three regardless, so
  //: the control offered a reader that does not exist here. The native
  //: `<select>` has honoured `hidden` on an option for years; the shell in
  //: front of it had never been told to. `syncHidden` below covers the same
  //: mistake one level up, for a select that is hidden as a whole.
  const buildOptionRow = (option) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "menu-item select-option";
    row.setAttribute("role", "option");
    row.dataset.value = option.value;
    row.textContent = option.textContent.trim();
    //: **An option that wants its row drawn its own way** names a class in
    //: `data-menu-class` (Settings' Font list sets each row in its own face,
    //: INBOX 670). The menu is lifted to <body>, so no selector can reach a
    //: row through its select; the class travels with the row instead.
    if (option.dataset.menuClass) row.classList.add(...option.dataset.menuClass.split(/\s+/).filter(Boolean));
    if (option.disabled) row.setAttribute("aria-disabled", "true");
    row.addEventListener("click", (event) => {
      event.stopPropagation();
      closeActionMenus();
      if (option.disabled || select.value === option.value) return;
      select.value = option.value;
      syncValue();
      // The app listens on the real control, so the real control is what
      // announces the change.
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    return row;
  };

  const rebuild = () => {
    menu.replaceChildren();
    //: **A group's own name, drawn once, not folded into each option's
    //: words.** INBOX 273: this opener built its menu by walking
    //: `select.options`, `HTMLOptionsCollection`'s flat view that drops
    //: which `<optgroup>` (if any) an option came from, so grouping the app
    //: sets on a select never reached the control the reader actually opens
    //: -- the Library's document-property filter worked around it by putting
    //: the group's name in each option's own text ("status: draft") rather
    //: than teach this shared opener about groups. Walking `select.children`
    //: instead of `select.options` keeps document order (an optgroup's
    //: options stay under it, a bare option stays where it was written) and
    //: lets a group draw its own label row, `.dock-menu-section`'s shape: a
    //: hairline above it and small text, not a `role="option"` row, so
    //: `syncValue`'s `[role='option']` walk and the click handler both skip
    //: past it without change. No observer needed for either shape: `rebuild()`
    //: runs on every open, so a picker that gains a reader, or a group, while
    //: the app is running shows it the next time it is opened.
    for (const node of select.children) {
      if (node.tagName === "OPTGROUP") {
        const visible = [...node.children].filter((option) => !option.hidden);
        if (!visible.length) continue;
        const label = document.createElement("div");
        label.className = "select-group-label";
        label.textContent = node.label || "";
        menu.appendChild(label);
        for (const option of visible) menu.appendChild(buildOptionRow(option));
      } else if (node.tagName === "OPTION") {
        if (node.hidden) continue;
        menu.appendChild(buildOptionRow(node));
      }
    }
    syncValue();
  };

  opener.addEventListener("click", (event) => {
    event.stopPropagation();
    if (select.disabled) return;
    if (menu.classList.contains("hidden")) {
      rebuild();
      openActionMenu(menu, opener);
      focusMenuItem(menu.querySelector(".is-chosen"), menu);
    } else {
      closeActionMenus();
    }
  });

  select.addEventListener("change", syncValue);
  new MutationObserver(rebuild).observe(select, { childList: true, subtree: true });

  // **A `<select>` that has been hidden must take its stand-in with it.**
  // Measured, not reasoned: on Library → Images the native
  // `#library-media-read` was 0x0 (`setLibraryMediaKind` adds `hidden`, since a
  // read filter is a Files idea) while the shell this function wraps it in
  // still rendered a 124x36 dropdown reading "Read or not", on a tab where
  // "read" means nothing. `#update-version-select` in Settings → About is
  // toggled the same way and had the same hole.
  //
  // This is the shape CLAUDE.md names: the value was set correctly on the
  // native control and did its damage on a *different element*, so the code
  // that hides it reads as right at every line. The fix belongs here rather
  // than at either call site, because every one of the app's 50-odd selects
  // inherits the same stand-in and any of them could be hidden tomorrow.
  // `hidden` is watched alongside the class for the same reason the
  // stylesheet protects both: this app hides things with either.
  const syncHidden = () => {
    shell.classList.toggle("hidden", select.classList.contains("hidden") || select.hidden);
  };
  syncHidden();
  new MutationObserver(syncHidden).observe(select, {
    attributes: true,
    attributeFilter: ["class", "hidden"],
  });

  // **Programmatic `select.value = …` fires no event at all**, and this app
  // sets one directly in dozens of places, every "load the saved settings
  // into the form" path does. A `change` listener alone therefore leaves the
  // opener showing whatever was selected when the page was built.
  //
  // Measured, not reasoned: the Timeline's own View control read "Grid" while
  // the timeline underneath it was rendering the *line* view, because the tab
  // assigned the saved value to that select directly, after this control had
  // been enhanced. (Both views and the select are gone now, the Timeline is one
  // feed: the hole this fixes was in every one of the app's 51 selects.)
  //
  // The fix is to make assignment observable: shadow `value`, `selectedIndex`
  // and `disabled` on this instance with accessors that call through to the
  // prototype's real ones and then re-sync the label. `Reflect.get/set` with
  // the element as receiver is what keeps the native accessor working on the
  // right object: reading the descriptor and calling `.get.call(select)`
  // directly would be the same thing written less safely.
  const proto = Object.getPrototypeOf(select);
  for (const prop of ["value", "selectedIndex", "disabled"]) {
    const native = Object.getOwnPropertyDescriptor(proto, prop);
    if (!native || !native.set) continue;
    Object.defineProperty(select, prop, {
      configurable: true,
      enumerable: false,
      get() {
        return native.get.call(this);
      },
      set(next) {
        native.set.call(this, next);
        syncValue();
      },
    });
  }

  wireMenuKeyboard(menu, opener);
  rebuild();
}

// **Double-click any slider to put it back to its default.** Asked for
// directly: "allow the user to double click any slider to reset it to
// default."
//
// One delegated listener rather than fourteen handlers, and no table of
// default values anywhere: every `<input type="range">` in this app already
// carries its default in its `value` attribute, and `defaultValue` reflects
// exactly that attribute rather than whatever the control currently shows.
// So the default is read from the same place the markup states it, and a
// slider added later is covered the moment it exists.
//
// Both events are dispatched, and both are needed: this app has live
// handlers on `input` (the graph's gravity/spread redraw as you drag) and
// commit handlers on `change` (the appearance settings persist there).
// Firing only one would either leave the screen stale or leave the setting
// unsaved.
document.addEventListener("dblclick", (event) => {
  const slider = event.target;
  if (!(slider instanceof HTMLInputElement) || slider.type !== "range") return;
  if (slider.disabled) return;
  //: A slider whose "default" is not its markup value (the model's sampling
  //: knobs: back to the model's own, by dropping your override) answers a
  //: cancelable `rangereset` itself (INBOX 437: the value went back, the
  //: "you set this" badge stayed, because the reset saved a new override).
  const own = new CustomEvent("rangereset", { cancelable: true });
  if (!slider.dispatchEvent(own)) return;
  if (slider.value === slider.defaultValue) return;
  slider.value = slider.defaultValue;
  slider.dispatchEvent(new Event("input", { bubbles: true }));
  slider.dispatchEvent(new Event("change", { bubbles: true }));
  toast("Reset to default");
});

// A control that does something on double-click has to say so somewhere, and
// the tooltip is where this app already explains its controls. Appended to
// whatever the slider's own title says rather than replacing it, so the
// existing explanations survive.
function annotateSliders(root) {
  for (const slider of (root || document).querySelectorAll("input[type='range']")) {
    if (slider.dataset.dblHinted) continue;
    slider.dataset.dblHinted = "1";
    const existing = (slider.title || "").trim();
    slider.title = existing
      ? `${existing}: double-click to reset`
      : "Double-click to reset to default";
  }
}

function enhanceAllSelects(root) {
  for (const select of (root || document).querySelectorAll("select")) {
    enhanceSelect(select);
  }
}

//: **A date or a time, picked** (UI_MODERNISATION_PLAN Phase 12 decision 5;
//: the owner: "the reminder dropdowns for setting datetimes and stuff, they
//: need a custom style"). The native field keeps the value, so every caller
//: that reads or writes `.value` is unchanged (a write repaints the face, a
//: `.focus()` lands on the face); what is seen and tabbed to is the select
//: recipe's opener, and what opens is the help popover shell holding the
//: Timeline month pop's grid (DESIGN.md, "A date picked from a month") or the
//: times of the day in the person's clock. A phrase typed in its field ("next
//: friday", "3pm") is read by `ai/when` on the reminders route. The fields in
//: the page at boot are enhanced; one built later stays native. The panel is a
//: lazy piece (date-field.js, the boot scripts are at their gzip cap): the
//: first press loads it, wires it and presses again.
function dateFieldFace(value, isTime) {
  if (isTime) {
    const [h, m] = value.split(":").map(Number);
    return new Date(2000, 0, 1, h, m).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  }
  const day = new Date(`${value}T00:00:00`);
  const year = day.getFullYear() === new Date().getFullYear() ? undefined : "numeric";
  return day.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year });
}

function enhanceDateField(input) {
  if (!input || input.dataset.dateField || !/^(date|time)$/.test(input.type)) return;
  input.dataset.dateField = "1";
  const isTime = input.type === "time";
  const label = input.getAttribute("aria-label") || (isTime ? "Time" : "Date");
  const shell = document.createElement("span");
  shell.className = "select-shell date-field";
  const opener = document.createElement("button");
  opener.type = "button";
  opener.className = "select-opener";
  opener.setAttribute("aria-haspopup", "dialog");
  opener.setAttribute("aria-expanded", "false");
  const icon = document.createElement("i");
  icon.className = `ph ${isTime ? "ph-clock" : "ph-calendar-blank"} select-icon`;
  icon.setAttribute("aria-hidden", "true");
  const face = document.createElement("span");
  face.className = "select-value";
  opener.append(icon, face);
  const panel = document.createElement("div");
  panel.className = "timeline-monthpop hidden";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", label);
  input.parentNode.insertBefore(shell, input);
  shell.append(input, opener, panel);
  input.classList.add("select-native-hidden");
  input.tabIndex = -1;
  input.setAttribute("aria-hidden", "true");
  const paint = () => {
    const value = input.value;
    face.textContent = value ? dateFieldFace(value, isTime) : label;
    opener.setAttribute("aria-label", `${label}: ${value ? face.textContent : "not set"}`);
  };
  const native = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
  Object.defineProperty(input, "value", {
    configurable: true,
    get() { return native.get.call(this); },
    set(value) { native.set.call(this, value); paint(); },
  });
  input.focus = (options) => opener.focus(options);
  paint();
  const first = async (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    opener.removeEventListener("click", first, true);
    if (await ensureModule("dateField")) {
      dateFieldWire(input, opener, panel, label, isTime);
      opener.click();
    }
  };
  opener.addEventListener("click", first, true);
}

// **Focus a `<select>`. Never call `.focus()` on one directly.**
// `enhanceSelect` hides the native control (`tabIndex = -1`, `aria-hidden`)
// behind a `.select-opener`, so `select.focus()` focuses nothing and keys go
// to `body`, silently (a Playwright sweep caught two in the link picker, and
// three more call sites did the same). No lint can see it: what decides is
// what a variable holds at runtime, so the guard is this helper and
// `scratchpad/ui-sweeps/selectfocus.js`. One retry on the next frame covers a
// select enhanced by the MutationObserver after it was created.
// `closest(".select-shell")`, not `parentElement`: three page-size selects
// have markup between them and the shell (measured). A select inside a shut
// `<details>` menu has nothing focusable, so the focus stays where it was.
function focusSelect(select) {
  if (!select) return;
  const land = () => {
    const opener = select.closest(".select-shell")?.querySelector(".select-opener");
    (opener || select).focus();
  };
  if (select.hasAttribute(SELECT_ENHANCED)) land();
  else requestAnimationFrame(land);
}

// New selects appear whenever a panel renders, so watch for them rather
// than asking every render path to remember to call this.
function watchForSelects() {
  enhanceAllSelects(document);
  for (const field of document.querySelectorAll('input:is([type="date"], [type="time"])')) enhanceDateField(field);
  annotateSliders(document);
  new MutationObserver((records) => {
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (node.nodeType !== 1) continue;
        if (node.tagName === "SELECT") enhanceSelect(node);
        else enhanceAllSelects(node);
        //: A date or time field drawn after boot (the document properties
        //: panel's typed rows, INBOX 904 B16) is the picker too, not the
        //: browser's grey calendar.
        if (node.tagName === "INPUT") enhanceDateField(node);
        else for (const field of node.querySelectorAll('input:is([type="date"], [type="time"])')) enhanceDateField(field);
        if (node.tagName === "INPUT") annotateSliders(node.parentNode || document);
        else annotateSliders(node);
      }
    }
  }).observe(document.body, { childList: true, subtree: true });
}

// **On a phone a ⋯ menu is an action sheet** (INBOX 392, UI_MODERNISATION_PLAN
// Phase 11 item 12: "a bottom sheet instead of a popover"). A popover hung
// from a 44px opener in a 390px window lands wherever the opener is, often
// under the thumb's far reach at the top of the screen, and is clamped and
// flipped to fit; the phone's own answer is the sheet from the bottom edge,
// every row full width at the thumb. Below 600 every `kebabMenu` opens the
// sheet recipe with the menu itself moved in, its rows, their handlers, their
// groups and its keyboard the same, and put back on close. A row press closes
// the sheet first (captured, before the row's own handler runs), so whatever
// the row opens next, a dialog or another sheet, takes the focus after it.
// Only `kebabMenu`, the recipe: a context menu at a point (`openMenuAtPoint`)
// stays where the finger held.
const PHONE_ACTION_SHEET = "(max-width: 599.98px)";

function openKebabSheet(menu, opener, label) {
  closeActionMenus();
  const home = menu.parentElement;
  let closeSheet = null;
  let sheetCard = null;
  // A group's row opens its group in place (below 720 a submenu is an
  // accordion, `buildMenuGroupButton`), so it leaves the sheet open.
  const onRow = (event) => {
    const row = event.target.closest(".menu-item");
    if (row && !row.classList.contains("has-submenu") && closeSheet) closeSheet();
  };
  closeSheet = openSheet({
    label,
    name: "action-menu",
    returnFocus: opener,
    build: (card) => {
      card.classList.add("action-menu-card");
      sheetCard = card;
      menu._inSheet = true;
      menu.style.left = "";
      menu.style.top = "";
      menu.classList.remove("hidden", "action-menu-flip", "action-menu-escaped");
      card.appendChild(menu);
      card.addEventListener("click", onRow, true);
    },
    onClose: () => {
      closeSheet = null;
      opener.setAttribute("aria-expanded", "false");
    },
    //: After the sheet's exit (`openSheet`'s `onGone`), so the card is not an
    //: empty rectangle while it leaves. Skipped when the menu has already
    //: been taken into a newer sheet (the same ⋯ pressed again inside the
    //: exit window): sending it home then would empty the sheet that is open.
    onGone: () => {
      if (menu.parentElement !== sheetCard) return;
      menu.classList.add("hidden");
      if (home) home.appendChild(menu);
      // After the observer has seen the class change above, so it does not
      // escape a menu that is on its way home.
      queueMicrotask(() => {
        menu._inSheet = false;
      });
    },
  });
  opener.setAttribute("aria-expanded", "true");
}

//: **Which overflow glyph (INBOX 706).** `⋯` (`ph:dots-three`, horizontal) for
//: an item's overflow in a row, a card or a bar of controls; `⋮`
//: (`ph:dots-three-vertical`) for the overflow at the end of a row in a
//: vertical list and in a narrow column, the platform conventions. A caller
//: passes the `vertical` option; the default stays the horizontal one, and
//: nothing else draws an overflow glyph (DESIGN.md's recipe index, pinned by
//: `tests/test_icon_conventions.py`).
//: **Row actions** (DESIGN.md, INBOX 810): an action repeated on every row of
//: a list is a quiet text button (no edge, no face at rest; the ghost tint,
//: the ring and a 24px floor under the pointer or the keyboard), a
//: destructive one waits in the muted ink until it is aimed at, and three or
//: more fold into the row's ⋯ behind the first. `actions` are kebabMenu items
//: (`label`, `title`, `run`, `danger`), so a row moves between the two shapes
//: without its caller changing.
function rowActions(actions, ariaLabel) {
  actions = actions.filter(Boolean); // an action left out on this device is null
  const wrap = document.createElement("span");
  wrap.className = "entry-actions row-actions";
  const button = (action) => {
    const b = smallButton(action.label, action.title, () => action.run());
    b.classList.add("quiet");
    if (action.danger) b.classList.add("danger");
    return b;
  };
  if (actions.length < 3) wrap.append(...actions.map(button));
  else wrap.append(button(actions[0]), kebabMenu(actions.slice(1), ariaLabel));
  return wrap;
}

//: **Type to filter a long list** (row 1643, WORLD_CLASS_PLAN 22.2: "every
//: list with more than 20 rows can be filtered by typing"; DESIGN.md's
//: recipe row). One `.search-field.list-filter` before `list`, shown only
//: while the list holds more than `threshold` rows, hiding the rows whose
//: words do not hold what is typed and saying so in one muted row when none
//: do. Escape in the field clears it before it closes anything. The list's
//: owner calls `refresh()` after each redraw, so a filter typed survives a
//: re-render; rows are `rows` (a selector run on the list), by default its
//: direct `li` children. `inside` puts the field at the head of the list
//: itself, for a popup that is its own list (the space menu).
function listFilter(list, { label, threshold = 12, rows = ":scope > li", inside = false } = {}) {
  if (!list) return null;
  if (list._listFilter) return list._listFilter;
  const field = document.createElement("div");
  field.className = "search-field list-filter hidden";
  const glyph = document.createElement("i");
  glyph.className = "ph ph-magnifying-glass search-field-icon";
  glyph.setAttribute("aria-hidden", "true");
  const input = document.createElement("input");
  input.type = "search";
  input.className = "search-field-input";
  input.placeholder = label;
  input.setAttribute("aria-label", label);
  input.autocomplete = "off";
  if (list.id) input.setAttribute("aria-controls", list.id);
  field.append(glyph, input);
  if (!inside) list.before(field);
  const empty = document.createElement(list.tagName === "UL" || list.tagName === "OL" ? "li" : "div");
  empty.className = "muted list-filter-empty hidden";
  const refresh = () => {
    if (inside && field.parentElement !== list) list.prepend(field);
    const all = [...list.querySelectorAll(rows)].filter((row) => row !== empty);
    field.classList.toggle("hidden", all.length <= threshold && !input.value);
    const needle = input.value.trim().toLowerCase();
    let shown = 0;
    for (const row of all) {
      const match = !needle || row.textContent.toLowerCase().includes(needle);
      // The `hidden` attribute, because a list's own row rule (`display:
      // flex`) outranks a class; `[hidden]` is the one rule that wins. A row
      // some other code had hidden keeps that state when the filter clears.
      if (!match && !row.classList.contains("list-filter-miss")) {
        row.classList.add("list-filter-miss");
        if (row.hidden) row.dataset.listFilterWasHidden = "1";
        row.hidden = true;
      } else if (match && row.classList.contains("list-filter-miss")) {
        row.classList.remove("list-filter-miss");
        row.hidden = row.dataset.listFilterWasHidden === "1";
        delete row.dataset.listFilterWasHidden;
      }
      if (match) shown += 1;
    }
    empty.textContent = `Nothing here matches "${input.value.trim()}".`;
    empty.classList.toggle("hidden", !needle || shown > 0);
    if (empty.parentElement !== list) list.append(empty);
    else if (empty.nextElementSibling) list.append(empty);
  };
  input.addEventListener("input", refresh);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && input.value) {
      event.preventDefault();
      event.stopPropagation();
      input.value = "";
      refresh();
    }
  });
  list._listFilter = { field, input, refresh };
  refresh();
  return list._listFilter;
}

//: **A menu row's words end inside its padding** (the owner 2026-10-11, in
//: the mono font: "there's some overflowing text in some places on
//: different fonts like mono"; the dashboard ⋯'s "Continue: Here are some
//: refined, non-corny..." ran into the menu's right padding). The words are
//: always a `.ph-text` span, which 08-consistency.css lets shrink and end in
//: an ellipsis, and a row whose words are cut carries them whole in its
//: title, with the row's own hint after them.
function menuRowFits(row, hint) {
  if (!row.querySelector(".ph-text") && row.childElementCount === 0 && row.textContent) {
    const words = document.createElement("span");
    words.className = "ph-text";
    words.textContent = row.textContent;
    row.replaceChildren(words);
  }
  const check = () => {
    const words = row.querySelector(".ph-text");
    if (!words) return;
    const cut = words.scrollWidth > words.clientWidth + 1;
    const said = words.textContent;
    //: A label the caller already shortened ends in "…": no full stop after it.
    const join = /[.?!…:]$/.test(said) ? " " : ". ";
    row.title = cut ? (hint ? `${said}${join}${hint}` : said) : hint;
    if (!row.title) row.removeAttribute("title");
  };
  row.addEventListener("pointerenter", check);
  row.addEventListener("focus", check);
}

function kebabMenu(items, ariaLabel, { vertical = false } = {}) {
  const wrap = document.createElement("span");
  wrap.className = "menu-wrap";

  const menu = document.createElement("div");
  menu.className = "action-menu hidden";
  menu.setAttribute("role", "menu");

  const opener = smallButton(vertical ? "ph:dots-three-vertical" : "ph:dots-three", ariaLabel, () => {
    if (window.matchMedia(PHONE_ACTION_SHEET).matches && typeof openSheet === "function") {
      openKebabSheet(menu, opener, ariaLabel);
      return;
    }
    const willOpen = menu.classList.contains("hidden");
    if (willOpen) openActionMenu(menu, opener);
    else closeActionMenus();
  });
  //: **A kebab is one glyph, so it is square.** Reported: "all the chat header
  //: buttons [should] be square, there should be no rectangle single icon
  //: buttons as that is not consistent with the rest of the application."
  //: Measured in that header: Fork and Compress 28×28, this opener 43×28, it
  //: took `.small`'s text padding because the class that squares an icon
  //: button has to be remembered per button (see the rule's own comment in
  //: 00-tokens-shell.css) and nobody remembered it here. Set at the source, so
  //: every ⋯ in the app is square rather than one more thing to remember.
  //: **One class for every ⋯** (INBOX 722, the owner: "meatball buttons have a
  //: visible outline, is that consistent with the rest of the app??"). The
  //: Library's cards and lines drew a resting `--shadow-sm` on a button whose
  //: fill and edge another rule had already cleared, so the ⋯ read as an
  //: outlined square there and as a plain glyph everywhere else. The class is
  //: the one place a surface cannot override: the ghost recipe is written once,
  //: in 08-consistency.css, DESIGN.md's "A ⋯ or ⋮ that opens a menu" row.
  opener.classList.add("icon-only", "kebab-opener");
  opener.setAttribute("aria-haspopup", "menu");
  opener.setAttribute("aria-expanded", "false");

  //: **Groups, drawn from the items rather than from separator objects**
  //: (DOCUMENTS_PLAN section 16). The table cell's menu was the case that
  //: asked for this: ten items covering rows, columns, alignment and the
  //: whole table, read as one list of ten, and a reader scanning it had to
  //: know the order to find anything. A menu of five or fewer needs no help;
  //: past that, the thing that makes a list scannable is a break every few
  //: rows, which is what every other application's menus do.
  //:
  //: An item carries `group`, a name, and the rule is "a hairline wherever
  //: the name changes". Callers declare meaning, never pixels, and a caller
  //: that declares nothing gets exactly what it got before, so every existing
  //: menu in the app is untouched. The name is not drawn: a heading per three
  //: rows would make a ten-row menu seventeen rows tall, and the rule here is
  //: the divider, not the label. `role="separator"` so the grouping is in the
  //: accessibility tree too, and `wireMenuKeyboard` walks `.menu-item`, so a
  //: divider is never a stop on the way down.
  let lastGroup = null;
  for (const item of items) {
    if (lastGroup !== null && item.group && item.group !== lastGroup) {
      const rule = document.createElement("div");
      rule.className = "menu-sep";
      rule.setAttribute("role", "separator");
      menu.appendChild(rule);
    }
    if (item.group) lastGroup = item.group;
    //: **An item with `items` is a submenu** (the owner, of the companion's
    //: menu: "extend this menu a bit maybe with sub-sections"): the note
    //: card's flyout recipe, `buildMenuGroupButton` (menus.js), which
    //: already flies out beside the row, clamps to the window, escapes a
    //: clipping ancestor, and opens in place in the phone's sheet.
    if (Array.isArray(item.items) && typeof buildMenuGroupButton === "function") {
      menu.appendChild(buildMenuGroupButton(item.label, item.items));
      continue;
    }
    const button = document.createElement("button");
    button.className = item.disabled ? "menu-item menu-item-unavailable" : "menu-item";
    //: A destructive row says so in the app's own danger colour. Added when
    //: the Images gallery's bespoke menu was folded into this one, it had a
    //: red Delete and this did not, and losing that on the way in would have
    //: made the shared control worse than the one it replaced.
    //: `menu-danger`, the class this menu's own stylesheet already defines, 
    //: not the generic `danger`, which is written for buttons with a ground.
    if (item.danger) button.classList.add("menu-danger");
    button.setAttribute("role", "menuitem");
    setLabel(button, item.label);
    if (item.title) button.title = item.title;
    menuRowFits(button, item.title || "");
    // Muted, not `disabled`, a native disabled button also blocks its own
    // title tooltip on some platforms, which is the one piece of information
    // this state actually needs to deliver (why the button can't do its
    // normal job). `run` still fires; a disabled item's `run` says why.
    if (item.disabled) button.setAttribute("aria-disabled", "true");
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      closeActionMenus();
      await item.run();
    });
    menu.appendChild(button);
  }
  wireMenuKeyboard(menu, opener);
  wrap.append(opener, menu);
  //: What a right-click on the row this menu belongs to opens at the pointer
  //: (`openRowMenu`), and what F2 looks through for Rename: the same items,
  //: so the two ways in cannot disagree about what the row can do.
  wrap.rowMenu = { items, ariaLabel };
  //: **Every ⋯ menu escapes its container, not just the ones somebody
  //: remembered.** Reported three times across three surfaces, the documents
  //: list, the gallery, and then the lightbox, always the same shape: the
  //: menu is `position: absolute` inside an ancestor that scrolls or paints a
  //: `backdrop-filter`, and either clips it.
  //:
  //: `wireEscapedActionMenu` was written to be opted into "for any menu known
  //: to live inside a scrolling ancestor", and that is the part that keeps
  //: failing: which ancestors scroll is not knowable from where the menu is
  //: built, and a caller added next year will not know either. Opting in
  //: *here* covers every `kebabMenu` at once, which is every ⋯ in the app.
  //:
  //: It is still not folded into `openActionMenu`, deliberately: the chat
  //: dock's popovers, the selection popup and the whiteboard's context menu
  //: build `.action-menu` by other routes, none of them are clipped, and
  //: rewriting what they all share to fix this class is the bigger change
  //: that function's own comment argues against.
  wireEscapedActionMenu(wrap);
  return wrap;
}

//: **A formatting-toolbar menu has to stay inside its panel**, and until this
//: ran it did not.
//:
//: Reported twice: *"formatting can go off the edge of the pannel in the
//: capture tab and im assuming the documents tab as well"* and *"dropdown
//: menus from the formatting bar get cut off and dont stay in the panel"*.
//: Measured in the capture composer at 1440px: the **Insert** menu spanned
//: x=164–356 against a panel starting at x=287, **123px of it outside the
//: panel's left edge**. The three menus at the right end of the same strip
//: were all comfortably inside, which is why this reads as intermittent.
//:
//: The cause is one line of CSS doing the right thing in the wrong place.
//: `.doc-dock-menu-list` is `position: absolute; right: 0`, anchored to its
//: opener's *right* edge, growing leftwards. That is correct for the menu it
//: was written for (the document ⋯, which sits at the right end of the header
//: row) and wrong for an opener near the left of a toolbar, where a 192px
//: menu is pushed straight out of the panel.
//:
//: Not fixable in CSS: which edge to anchor to depends on where the opener
//: happens to sit relative to a panel whose width changes with the window,
//: the sidebar and the chat dock. So it is measured on open, the same way
//: `wireEscapedActionMenu` handles the clipping case it owns.
//:
//: `toggle` does not bubble, so this listens in the capture phase, one
//: delegated listener covers the note composer's strip and the document
//: editor's, including any `<details>` menu added to either later.
function clampToolbarMenu(details, { retry = true } = {}) {
  const list = details.querySelector(".doc-dock-menu-list");
  if (!list) return;
  const opener = details.querySelector("summary") || details;
  // **Cleared, not zeroed: and this distinction is the whole bug below.**
  //
  // The inline values have to go before measuring, or the menu's own size is
  // measured from wherever the previous open left it. This used to clear them
  // by writing `left: 0; top: 0`, and then the guard two lines down could
  // `return`, leaving those zeros in place. A `position: fixed` element at
  // 0,0 sits in the top-left corner of whatever its containing block is,
  // which for these menus is the surrounding `.card`: reported as "the
  // toolbar dropdowns are now appearing in the top left corner of the panel",
  // with a screenshot of the Block menu pinned to the corner of the capture
  // card while its button sat 1,600px away.
  //
  // Writing "" removes the declaration instead, so a failed measurement falls
  // back to the stylesheet, which now says `top: auto; left: auto`, i.e. the
  // static position, i.e. roughly under the button. A wrong-but-near answer
  // beats a corner every time.
  list.style.left = "";
  list.style.top = "";
  list.style.right = "";
  const anchor = opener.getBoundingClientRect();
  const box = list.getBoundingClientRect();
  if (!box.width || !anchor.width) {
    // Nothing to measure *yet* is a real state: a `<details>` panel is not
    // laid out until the open takes effect, and this runs from the `toggle`
    // event. One retry on the next frame, once, a loop here would spin
    // forever on a menu that is genuinely empty.
    if (retry) requestAnimationFrame(() => clampToolbarMenu(details, { retry: false }));
    // Out of retries: show it where the stylesheet put it rather than never.
    // `.doc-dock-menu-list` is invisible until this class arrives.
    else list.classList.add("is-placed");
    return;
  }
  const margin = 8;
  // **Left-aligned to the opener, growing rightwards.**
  //
  // This was `anchor.right - box.width`, right-aligned, transcribed from the
  // stylesheet's `right: 0`, which is correct for `#doc-dock-menu` (a kebab at
  // the far right of the panel, where a menu growing rightwards would leave
  // the screen) and wrong for every menu in a toolbar. Measured: a 192px menu
  // right-aligned to a 41px icon button lands **151px to the left of the
  // button that opened it**, over the sidebar, on the capture toolbar, at
  // every viewport. Reported as "dropdowns are completely broken and dont show
  // in the capture notes and documents toolbars", which is what a menu that
  // opens nowhere near its control looks like from the outside.
  //
  // `clampToolbarMenu` only ever runs for `.doc-toolbar-menu` (see the toggle
  // listener below), so the kebab keeps the stylesheet's right-alignment and
  // this is a toolbar-only rule.
  let left = anchor.left;
  if (left + box.width > window.innerWidth - margin) {
    // No room to the right: right-align to the opener, which is the shape that
    // keeps a menu attached to its button near the end of a row.
    left = Math.min(anchor.right - box.width, window.innerWidth - margin - box.width);
  }
  // `margin` wins a tie deliberately: a viewport narrower than the menu cannot
  // satisfy both edges, and losing the *start* of the list is worse than
  // losing its end.
  if (left < margin) left = margin;
  let top = anchor.bottom + 4;
  if (top + box.height > window.innerHeight - margin) {
    // Flip above the opener, and only fall back to "pinned to the bottom" when
    // there is no room either way, a menu that covers its own button is still
    // better than one whose last item is unreachable.
    const above = anchor.top - 4 - box.height;
    top = above >= margin ? above : Math.max(margin, window.innerHeight - margin - box.height);
  }
  list.style.left = `${Math.round(left)}px`;
  list.style.top = `${Math.round(top)}px`;

  // **A second pass, because `position: fixed` is not always fixed to the
  // viewport**: an ancestor with `transform`, `filter`, `backdrop-filter`,
  // `contain` or `will-change` becomes the containing block, and `.card`
  // carries `backdrop-filter` with Glass on (measured live with the
  // background art on: a fixed child at left 0 inside `.card.doc-main` lands
  // at x=293). The reported "dropdowns flicker somewhere random" was that
  // offset (a menu given left 886 rendered at 1177). Rather than walk the
  // ancestors for a growing list of properties, measure where the panel
  // landed and correct by the difference: one layout read, zero when there
  // is no containing block; dx 0 (±1) on all six menus after.
  const landed = list.getBoundingClientRect();
  const driftX = left - landed.x;
  const driftY = top - landed.y;
  if (Math.abs(driftX) > 0.5 || Math.abs(driftY) > 0.5) {
    list.style.left = `${Math.round(left + driftX)}px`;
    list.style.top = `${Math.round(top + driftY)}px`;
  }
  // Only now is it allowed to paint -- see `.doc-dock-menu-list` in
  // 04-chat-dock-appearance.css for the flicker this prevents.
  list.classList.add("is-placed");
}

//: A fixed-position menu does not travel with the strip it belongs to, so any
//: scroll or resize while it is open would leave it stranded beside a button
//: that has moved. Re-placing on both is cheaper than the alternative (an
//: anchor-positioning polyfill) and covers the two ways it can happen: the
//: page scrolls under a sticky toolbar, or the toolbar itself is scrolled
//: sideways in row mode.
//: A live collection for the same reason as `ACTION_MENUS`: a capturing
//: scroll listener on every tab, with nothing open nearly always (18ms of
//: selector matching over a 30-step scroll, traced).
const TOOLBAR_MENUS = document.getElementsByClassName("doc-toolbar-menu");

function replaceOpenToolbarMenus() {
  const open = [];
  for (const details of TOOLBAR_MENUS) if (details.open) open.push(details);
  for (const details of open) clampToolbarMenu(details);
}
window.addEventListener("resize", replaceOpenToolbarMenus);
window.addEventListener("scroll", replaceOpenToolbarMenus, true);

document.addEventListener(
  "toggle",
  (event) => {
    const details = event.target;
    if (!(details instanceof HTMLElement) || details.tagName !== "DETAILS") return;
    if (!details.classList.contains("doc-toolbar-menu")) return;
    if (!details.open) {
      // Back to invisible for the next open, so it never paints unplaced.
      details.querySelector(".doc-dock-menu-list")?.classList.remove("is-placed");
      return;
    }
    //: One toolbar menu open at a time: a `<details>` never closes its
    //: neighbours, so two lists stood over each other (owner, 2026-10-12).
    for (const other of TOOLBAR_MENUS) if (other !== details && other.open) other.open = false;
    clampToolbarMenu(details);
  },
  true
);

// "12.4k" beats "12417" when the number is a rough sense of scale, which is
// all a token count ever is.
//: **A model's name as a badge should say, at a glance, which model.**
//: Reported: "can you truncate hugging face model names in visual badges
//: except for in the model settings page to remove the hf.co/ part??"
//:
//: A HuggingFace id arrives as `hf.co/LiquidAI/LFM2.5-VL-1.6B` (Ollama's own
//: form): three segments of which only the last identifies the model, and
//: the first two eat the width a badge has. The org is kept off too: two
//: models from the same org differ in their last segment, never their first.
//: Settings → Models is deliberately *not* a caller: choosing a model to pull
//: needs the id you would actually type.
//:
//: Only prefixes that are registry addresses are stripped. `llama3.2:3b` and
//: `gemma3:latest` are already short and are returned untouched, tag and all.
function shortModelName(name) {
  const raw = String(name || "").trim();
  if (!raw) return "";
  const withoutHost = raw.replace(/^(https?:\/\/)?(hf\.co|huggingface\.co)\//i, "");
  //: Only when a registry host was actually stripped is the remaining
  //: `org/model` split safe: a bare `library/llama3` from a private registry
  //: keeps its shape, because there the org may be the only thing telling two
  //: models apart.
  if (withoutHost === raw) return raw;
  const parts = withoutHost.split("/").filter(Boolean);
  return parts.at(-1) || withoutHost;
}
window.shortModelName = shortModelName;

//: **A picture can carry two readings, and the lightbox showed one of them.**
//: Reported, and reproduced before it was touched: a `MediaUpload` or an
//: `Attachment` holds `ocr_text` (Tesseract's own pass, written automatically
//: the moment the file is saved into a note) and `vision_ocr_text` (a vision
//: model's transcription, always asked for by hand). With both stored, the
//: lightbox drew `vision_ocr_text || ocr_text` and the Tesseract reading was
//: nowhere on the surface built for reading: measured at 1440 with both seeded
//: through `POST /media/{id}/ocr` and `/vision-ocr`, `.lightbox-text` held the
//: vision reading and the whole `.lightbox-info` panel never contained a
//: character of the other one.
//:
//: What it shows now is not a new decision. The Library card's own reading
//: fold settled this exact question already (`renderLibraryImagesGallery`,
//: library.js): "Tesseract's reading goes inside the same disclosure, under
//: the vision one: it is the same question ('what does this say'), answered by
//: the other reader", labelled "Also read with Tesseract OCR" and left out
//: entirely when it is empty, which on a machine with no Tesseract is always.
//: This applies that decision to the one surface that missed it, in the
//: elements already there (`.lightbox-text`, `.lightbox-byline`), so there is
//: no second recipe and no new rule to lint.
//:
//: Stacked rather than behind a two-state control, on purpose: the lightbox is
//: the picture "at a size the text can be checked against", and two
//: transcriptions of one image are worth having open precisely so they can be
//: read against each other and against the page. A toggle answers "which one
//: is current", which is a question the badge on the card already answers,
//: and it makes the comparison impossible.
//:
//: One reader of the row, so the four surfaces that build a lightbox item
//: cannot drift apart again (`hydrate` here, the two menu rows that re-read a
//: picture, and `libraryLightboxItems` in library.js).
function lightboxReadingsFor(row) {
  const vision = (row?.vision_ocr_text || "").trim();
  const tesseract = (row?.ocr_text || "").trim();
  if (vision) {
    return {
      text: vision,
      byline: `Text read by ${shortModelName(row?.vision_ocr_model) || "a model"}`,
      //: Only a *second* reading is an alternate. With no vision reading the
      //: Tesseract one is the reading, and it is returned as `text` below
      //: rather than as a footnote to an empty panel.
      altText: tesseract,
      altByline: tesseract ? "Also read with Tesseract OCR" : "",
      //: Which stored field each one is, so the lightbox can delete the
      //: reading it shows (INBOX 421 e) rather than guess at the reader.
      textSource: "vision",
      altSource: tesseract ? "tesseract" : "",
    };
  }
  return {
    text: tesseract,
    byline: tesseract ? "Text read with Tesseract OCR" : "",
    altText: "",
    altByline: "",
    textSource: tesseract ? "tesseract" : "",
    altSource: "",
  };
}
window.lightboxReadingsFor = lightboxReadingsFor;

function formatTokens(n) {
  const count = Number(n) || 0;
  if (count < 1000) return String(count);
  return `${(count / 1000).toFixed(count < 10000 ? 1 : 0)}k`;
}

// Server timestamps are UTC. Most now carry an explicit offset or Z; older
// stored values may carry neither, and a naive string is parsed as LOCAL by
// JavaScript. One parser, so the assumption lives in exactly one place.
function parseServerTime(iso) {
  if (!iso) return null;
  const text = String(iso);
  const hasZone = /[Zz]$|[+-]\d{2}:?\d{2}$/.test(text);
  const date = new Date(hasZone ? text : `${text}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

// How long ago, in words. A wall of identical timestamps tells you nothing;
// "yesterday" and "3 weeks ago" are what you actually navigate by.
function relativeTime(iso) {
  // Timestamps now come back explicitly UTC ("...+00:00"), so the old
  // unconditional `iso + "Z"` produced "…+00:00Z", an unparseable string that
  // rendered literally as "Invalid Date" in the documents sidebar. Only assume
  // UTC when the value doesn't already say what it is.
  const then = parseServerTime(iso);
  if (!then) return "";
  const seconds = Math.max(0, (Date.now() - then.getTime()) / 1000);
  if (seconds < 90) return "just now";
  const minutes = seconds / 60;
  if (minutes < 60) return `${Math.round(minutes)} min ago`;
  const hours = minutes / 60;
  if (hours < 24) return `${Math.round(hours)}h ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  // Screenshotted as "1 weeks ago". Rounding 8 days gives 1, and the plural
  // was hard-coded: the only branch here that forgot to agree with its own
  // number.
  const weeks = Math.round(days / 7);
  if (days < 30) return `${weeks} week${weeks === 1 ? "" : "s"} ago`;
  return then.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

//: How many chats the switcher shows. Searching and sorting all of them is
//: the Library's job now (§36F); this list exists so the chat you were in ten
//: minutes ago is one click away without leaving the tab you are typing in,
//: and eight is comfortably more than "the one before this one" while still
//: fitting beside a conversation.
const RECENT_CHATS_SHOWN = 8;

const CHAT_SIDEBAR_SORT_KEY = "chatSidebarSort";

// Pinned notes stay first regardless of sort, that promise (a divider marks
// the boundary, just below) predates this control and a sort choice
// shouldn't silently break it. Only the order *within* each of the two
// groups changes.
function sortConversations(conversations, mode) {
  const pinned = conversations.filter((c) => c.pinned);
  const rest = conversations.filter((c) => !c.pinned);
  const byMode = {
    recent: (a, b) => new Date(b.updated_at) - new Date(a.updated_at),
    turns: (a, b) => (b.turns || 0) - (a.turns || 0),
    tokens: (a, b) => (b.tokens || 0) - (a.tokens || 0),
    alpha: (a, b) => a.title.localeCompare(b.title),
  }[mode] || null;
  if (!byMode) return conversations; // "recent" is already the server's own order
  return [...pinned.sort(byMode), ...rest.sort(byMode)];
}

async function loadConversationList() {
  //: Placeholders while the list is on its way, and no "no saved chats"
  //: until the answer says so (INBOX 435 (6), skeletons.js).
  const list = $("conversation-list");
  showSkeletons(list, 4, "li");
  if (!list.children.length || list.querySelector(".skeleton")) $("conv-empty")?.classList.add("hidden");
  const conversations = sortConversations(
    await apiJson("/conversations").catch(() => []),
    $("chat-sidebar-sort")?.value || "recent"
  ).slice(0, RECENT_CHATS_SHOWN);
  clearSkeletons(list);
  list.replaceChildren();
  const empty = $("conv-empty");
  empty.classList.toggle("hidden", conversations.length > 0);
  empty.textContent = "No saved chats yet. Ask something to start one.";

  let sawUnpinned = false;
  for (const conversation of conversations) {
    // One divider between the pinned block and the rest, so "pinned" reads as
    // a section rather than as an unexplained reordering.
    if (!conversation.pinned && !sawUnpinned && list.children.length) {
      const rule = document.createElement("li");
      rule.className = "conv-divider";
      rule.setAttribute("aria-hidden", "true");
      list.appendChild(rule);
    }
    if (!conversation.pinned) sawUnpinned = true;

    const li = document.createElement("li");
    if (conversation.id === chatConv.id) li.classList.add("active-conv");
    if (conversation.pinned) li.classList.add("pinned-conv");

    //: **The whole row opens the chat, not just the words in it.** Reported:
    //: "I clicked on other chat conversations in the chat sidebar but the
    //: conversations didnt visibly select in the sidebar." Measured: the
    //: `<li>` is 268x48 and `.conv-title`, which carried the only click
    //: handler: is 211x35. The 6.4px/9.6px padding ring and the gutter kept
    //: clear for the ⋯ are dead: `elementFromPoint` returns the `<li>` at the
    //: row's top edge, bottom edge, left edge and right-hand side alike. So
    //: roughly a third of every row did nothing when clicked, which reads
    //: exactly like a selection that failed rather than a click that missed.
    //:
    //: On the `<li>`, with the actions cluster excluded: a click on the ⋯ (or
    //: on anything inside the menu it opens) is not a request to switch
    //: conversations. `aria-current` says which row is the open one to a
    //: screen reader, which the accent fill says to everyone else.
    li.addEventListener("click", (event) => {
      if (event.target instanceof Element && event.target.closest(".entry-actions")) return;
      openConversation(conversation.id);
    });
    li.setAttribute("aria-current", conversation.id === chatConv.id ? "true" : "false");

    const title = document.createElement("span");
    title.className = "conv-title";
    title.title = "Open this chat";

    const name = document.createElement("span");
    name.className = "conv-name";
    setLabel(name, `${conversation.pinned ? "ph:push-pin " : ""}${conversation.title}`);
    const meta = document.createElement("span");
    meta.className = "conv-meta muted";
    const bits = [relativeTime(conversation.last_at)];
    if (conversation.turns) {
      bits.push(`${conversation.turns} ${conversation.turns === 1 ? "turn" : "turns"}`);
    }
    // "tok" rather than "tokens": the row is one line by design, and the
    // number is the useful part, spelling out the unit is what pushed it
    // into an ellipsis at the default sidebar width.
    if (conversation.tokens) bits.push(`${formatTokens(conversation.tokens)} tok`);
    meta.textContent = bits.join(" · ");
    meta.title = bits.join(" · "); // in full, if the row still has to clip
    title.append(name, meta);
    // The title often isn't the subject: show what was actually asked.
    if (conversation.preview && conversation.preview !== conversation.title) {
      title.title = conversation.preview;
    }
    // One ⋯ instead of three buttons. In a sidebar this narrow they were
    // taking most of the row, leaving a few characters of the chat's name.
    const actions = document.createElement("span");
    actions.className = "entry-actions";
    const items = [];
    items.push(
      makeMenuItem(
        conversation.pinned ? "ph:push-pin-slash Unpin" : "ph:push-pin Pin",
        conversation.pinned ? "Let this chat sort by date again" : "Keep this chat at the top",
        async () => {
          await apiJson(`/conversations/${conversation.id}/pin`, {
            method: "PUT",
            body: JSON.stringify({ pinned: !conversation.pinned }),
          });
          chatWriteRecord("chatPinUndo", conversation.id, !conversation.pinned);
          loadConversationList();
        }
      )
    );
    items.push(
      makeMenuItem("ph:pencil-simple Rename", "Rename this chat", async () => {
        const next = await promptDialog("Rename this chat:", conversation.title);
        if (!next || !next.trim()) return;
        await apiJson(`/conversations/${conversation.id}`, {
          method: "PUT",
          body: JSON.stringify({ title: next.trim() }),
        });
        chatWriteRecord("chatTitleUndo", conversation.id, conversation.title, next.trim());
        if (chatConv.id === conversation.id) $("chat-title").textContent = next.trim();
        loadConversationList();
      })
    );
    items.push(
      makeMenuItem("ph:sparkle Name with Atlas", "Let Atlas name this chat", async () => {
        //: Asked for, so answered directly: the activity notice below obeys
        //: "AI activity: panel only", and with that set the click showed
        //: nothing at all, start or finish (the owner at release).
        toast("Atlas is naming this chat…");
        const named = await apiJson(`/conversations/${conversation.id}/retitle`, {
          method: "POST",
        }).catch((e) => {
          toast(e.message, true);
          return null;
        });
        if (!named) return;
        if (named.title !== conversation.title) chatWriteRecord("chatTitleUndo", conversation.id, conversation.title, named.title);
        if (chatConv.id === conversation.id) $("chat-title").textContent = named.title;
        toast(named.ai_named ? `Named “${named.title}”.` : "Kept the first question as the title.");
        //: The AI naming a conversation is activity, not something the user
        //: did: so it obeys the same "pop up, or only in the centre" choice
        //: as every other thing the AI does on its own.
        agentActivityNotice(
          named.ai_named ? `Renamed to “${named.title}”.` : "Used the first question as the title.",
          { kind: "run" }
        );
        loadConversationList();
      })
    );
    items.push(appLinkMenuItem("chat", conversation.id));
    items.push(
      // Not destructive, so not grouped with Delete below, same "keep it,
      // but out of the way" action Notes already has for entries (BACKLOG
      // §30b's named remaining scope: chats and documents). Reachable
      // again from the Library's Shelved filter.
      makeMenuItem("ph:archive Archive", "Keep it, but out of the way, not deleted", async () => {
        await apiJson(`/conversations/${conversation.id}/archive`, { method: "PUT" });
        chatWriteRecord("chatArchiveUndo", conversation.id, conversation.title);
        if (chatConv.id === conversation.id) newChatConversation();
        toast("Archived.");
        loadConversationList();
      })
    );
    items.push(
      makeMenuItem("ph:trash Delete", "Delete this chat", async () => {
        if (!(await confirmDialog("Delete this saved chat?"))) return;
        const gone = await apiJson(`/conversations/${conversation.id}`, { method: "DELETE" });
        if (chatConv.id === conversation.id) newChatConversation();
        loadConversationList();
        chatDeleteUndo(gone);
      })
    );
    //: Six rows is past the ceiling (DESIGN.md): what you do to it, its address, and the two that put it away.
    const group = (item) => (/Copy app link/.test(item.label) ? "copy" : /Archive|Delete/.test(item.label) ? "end" : "act");
    actions.appendChild(kebabMenu(items.map((item) => ({ ...item, group: group(item) })), `Actions for ${conversation.title}`, { vertical: true }));
    li.append(title, actions);
    list.appendChild(li);
  }
}

// An edited answer is labelled, always. A transcript that silently presents
// your words as the model's is worse than no transcript.
function editedMarker() {
  const tag = document.createElement("span");
  tag.className = "edited-marker muted";
  tag.textContent = "edited by you";
  tag.title = "You changed this answer after the model wrote it";
  return tag;
}

// Editing questions has worked for a while; answers were fixed forever, so a
// model that got one detail wrong left you regenerating the whole thing and
// hoping. Editing in place keeps the rest of the thread intact.
function editChatAnswer(handles, turnIndex, current) {
  if (handles.bubble.querySelector(".answer-editor")) return; // already open
  const editor = document.createElement("div");
  editor.className = "answer-editor";
  const box = document.createElement("textarea");
  box.value = current;
  box.rows = Math.min(20, Math.max(4, current.split("\n").length + 1));
  box.setAttribute("aria-label", "Edit this answer");

  const target = handles.timeline.answerElement();
  const finish = (markdown) => {
    editor.remove();
    target.classList.remove("hidden");
    if (markdown !== null) handles.timeline.replaceAnswer(markdown);
  };

  const save = document.createElement("button");
  save.className = "small";
  save.type = "button";
  save.textContent = "Save";
  save.addEventListener("click", async () => {
    const next = box.value.trim();
    if (!next) {
      toast("An empty answer isn't a correction: delete the message instead.", "info");
      return;
    }
    if (chatConv.id) {
      const priorAnswer = chatConv.turns[turnIndex]?.answer;
      const chatId = chatConv.id;
      try {
        await apiJson(`/conversations/${chatConv.id}/turns/${turnIndex}/answer`, {
          method: "PUT",
          body: JSON.stringify({ content: next }),
        });
      } catch (error) {
        toast(error.message, true);
        return; // leave the editor open rather than losing the edit
      }
      if (priorAnswer != null) {
        pushRequestUndo(
          "Edited an answer",
          `/conversations/${chatId}/turns/${turnIndex}/answer`,
          "PUT",
          { content: priorAnswer },
          { content: next },
          () => (chatConv?.id === chatId ? openConversation(chatId) : null)
        );
      }
    }
    if (chatConv.turns[turnIndex]) chatConv.turns[turnIndex].answer = next;
    finish(next);
    if (!handles.bubble.querySelector(".edited-marker")) {
      handles.bubble.insertBefore(
        editedMarker(),
        handles.bubble.querySelector(".msg-actions")
      );
    }
    toast("Answer updated.");
  });

  const cancel = document.createElement("button");
  cancel.className = "ghost small";
  cancel.type = "button";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => finish(null));

  const row = document.createElement("div");
  row.className = "row";
  row.append(save, cancel);
  editor.append(box, row);
  target.classList.add("hidden");
  target.after(editor);
  box.focus();
}

async function openConversation(id) {
  const full = await apiJson(`/conversations/${id}`).catch(() => null);
  if (!full) return;
  // Before the pane is rebuilt, not after: this reads the composer state that
  // belongs to the conversation being left.
  releaseChatComposer();
  // ROADMAP.md item 13: switching between saved chats was invisible to
  // back/forward. Recorded here rather than at each of this function's
  // call sites (the sidebar, the Library) so neither has to remember to.
  recordTabVisit("chat", `conv:${full.id}`, full.title || "");
  chatConv = { id: full.id, turns: [] };
  chatAwaitingAgentAnswer = false; // a saved thread's own pending ask, if any, isn't answerable live
  // Not carried across conversations, and not persisted: re-deriving it is one
  // click, and a summary restored against the wrong thread would be worse than
  // no summary at all.
  chatSummary = null;
  renderCompressionState();
  $("chat-title").textContent = full.title;
  renderChatUsage(full.tokens);
  //: **Give the starter chips back before clearing the pane, not after.**
  //:
  //: Reported with a screenshot: *"I cant view older chat sessions, the
  //: panel/page just appears blank."* The title, model and token count in the
  //: header were all correct, only the transcript was empty, which is what
  //: made it look like a rendering problem with the messages rather than a
  //: crash.
  //:
  //: `#chat-suggest` is **on loan**. `chatEmptyState` *moves* that element out
  //: of the dock and into `.chat-empty` inside `#chat-messages` (see its own
  //: comment on why the starters belong with the welcome). So on any chat that
  //: was showing the empty state, every fresh load of the tab, the element
  //: is a child of the very thing being wiped here: `replaceChildren()`
  //: destroyed it, and the next line dereferenced `null` and threw.
  //:
  //: The throw landed exactly between "clear the transcript" and "render the
  //: messages", so the pane was emptied and then nothing was drawn. Every
  //: saved conversation opened blank, and the console error was the only
  //: sign.
  //:
  //: `clearChatEmptyState` already knows how to return the chips to the dock, 
  //: it exists for this, so the fix is to let it run first rather than to
  //: null-guard the symptom.
  clearChatEmptyState();
  $("chat-messages").replaceChildren();
  //: Optional-chained regardless: this element is moved between two parents at
  //: runtime, and a second caller that clears the pane should degrade to a
  //: stale chip strip rather than to a blank conversation.
  $("chat-suggest")?.classList.add("hidden");
  let lastQuestionText = null;
  for (const message of full.messages) {
    if (message.role === "user") {
      lastQuestionText = message.content;
      const asked = addBubble("user", message.content, message.attachments);
      if (message.followup_of) markFollowup(asked, message.followup_of);
    } else {
      const handles = addAssistantBubble(message.persona || null);
      // Replay the run in the order it happened when the turn recorded one.
      // Older turns (saved before steps existed) only have the flattened
      // thinking/tools/answer, so they're rebuilt in that fixed order, 
      // everything is still shown, just without the interleaving.
      if (message.steps && message.steps.length) {
        handles.timeline.replay(message.steps);
      } else {
        if (message.thinking) {
          handles.timeline.thinking(message.thinking);
        }
        // Re-draw the tool-activity chips (Wave G) so they don't vanish on
        // reload the way they used to (user-reported).
        for (const t of message.tools || []) {
          handles.timeline.tool(toolChip(t.label, t.ok !== false, t));
        }
        if (message.content) {
          handles.timeline.answer(message.content);
        }
      }
      handles.timeline.finalise();
      //: …and the step group, so a replayed turn does not reopen with
      //: "Working: 3 steps" over a conversation that finished yesterday.
      handles.timeline.finish?.();
      // Rebuild the metadata line. Reported in IDEAS.md as "chat message
      // metadata disappears on reload": it was only ever built from the live
      // stream, so reopening a chat showed answers with nothing to say which
      // model wrote them or what they cost. Turns saved before this stored no
      // stats and correctly get no line, rather than a row of "?"s.
      if (message.stats) {
        //: A reopened conversation gets its meter back from the last turn that
        //: recorded one: without this the header says nothing about a thread
        //: that is already 80% through its window, which is precisely the
        //: thread you want warned about.
        renderChatContextMeter(message.stats);
        handles.bubble.appendChild(
          messageMetaLine({
            model: message.stats.model,
            elapsedMs: message.elapsed_ms,
            stats: message.stats,
            toolCount: (message.tools || []).length,
            rounds: message.stats.round || 0,
            usedTools: message.used_tools ?? null,
          })
        );
      }
      //: **The Sources panel is rebuilt, not the thing it replaced.**
      //:
      //: Reported: *"a lot of the steps and agent process disappears when I
      //: leave the chat session and come back to it."* A live turn ends with
      //: the Sources panel: notes, files and web pages, with previews and
      //: links: and this path rebuilt the old "N matching notes" disclosure
      //: instead, which knows nothing about files or the web. So reopening a
      //: conversation genuinely lost most of what the turn had consulted, and
      //: what survived was drawn as a different control.
      //:
      //: `touched` comes back off the saved tool events, which have carried it
      //: since the live action line was built, the same rows, from the same
      //: place, so a reopened panel is the panel and not an approximation.
      const savedInput = {
        meta: {
          raw_results: message.raw_results || [],
          search_mode: message.search_mode,
        },
        toolEvents: message.tools || [],
        touched: (message.tools || []).flatMap((t) => t.touched || []),
      };
      //: The panel's order, built once and handed to the citation pass below
      //: as the live path does (chat-attach.js, `turnSources`). Reopening
      //: passed `null` there, so the marks fell back to "order first cited"
      //: and a note that was 8 in the panel read 1 in the prose while its
      //: peek showed source 8 (the owner, INBOX 430).
      const savedOrder = chatSourcesFrom(savedInput);
      const savedSources = chatSourcesPanel({ ...savedInput, sources: savedOrder });
      if (savedSources) {
        handles.recordsHolder.appendChild(savedSources);
      } else if (message.raw_results) {
        renderRecordsDetails(handles.recordsHolder, {
          raw_results: message.raw_results,
          search_mode: message.search_mode,
          match_info: message.match_info || {},
          connected_ids: message.connected_ids || [],
        });
      }
      // Same reload-reconstruction fix as raw_results just above, for the
      // "Grounded in" chips: reported directly as disappearing once the chat
      // tab was left or the session ended, since nothing rebuilt this on
      // reopen either.
      if (message.sentence_grounding) {
        renderAnswerGrounding(
          handles.groundingHolder,
          message.sentence_grounding,
          message.raw_results || [],
          handles.bubble?.querySelectorAll(".bubble-answer") || null,
          "",
          savedOrder,
          //: Saved on the turn by the server from the same counter the live
          //: stream used, so the notice survives reopening the chat.
          message.support || null,
          message.picture_alts || null
        );
      }
      placeAnswerFigures(handles.bubble?.querySelectorAll(".bubble-answer"), message, lastQuestionText);
      // And the same shape again for the "what to ask next" chips, reported
      // separately: "suggested repsponse continuation prompts in chat doesnt
      // persist and disappears once I switch chat sessions or quit the app".
      // Rendered through the same function the live path uses, so a restored
      // chip is not a slightly different chip.
      if (message.followups) {
        renderFollowups(handles.bubble, message.followups);
      }
      //: And the Resume and Edit-step buttons, which disappeared on reopen for
      //: the same reason and are rebuilt through the same function the live
      //: path uses, from the state saved with the turn.
      if (message.resume) {
        appendRunResumeControls(handles.bubble, {
          ...message.resume,
          timeline: handles.timeline,
        });
      }
      const turnIndex = chatConv.turns.length; // index this pair will occupy
      if (message.edited) handles.bubble.appendChild(editedMarker());
      //: The same list the live stream builds, see `assistantMessageActions`.
      //: These two paths had already drifted (this one had Edit and no fork or
      //: rewrite; the live one the reverse), which is how a fix lands on half
      //: the app's messages.
      handles.bubble.appendChild(
        assistantMessageActions({
          bubble: handles.bubble,
          text: message.content,
          question: lastQuestionText,
          onEdit: () => editChatAnswer(handles, turnIndex, message.content),
        })
      );
      if (lastQuestionText !== null) {
        chatConv.turns.push({ question: lastQuestionText, answer: message.content });
      }
    }
  }
  // A conversation that is still being answered has not saved that turn yet, 
  // the save happens when the stream ends, so what came back from the server
  // above is the thread *without* the message in flight. Left alone, coming
  // back to it shows either an empty pane or a thread missing its newest
  // question: exactly the "my message disappeared" this whole change is about.
  // Saying so is the honest render, and the note is replaced by the real turn
  // the moment the stream finishes and the list refreshes.
  if (isStreamingConversation(full.id)) {
    // Coming back to the thread that is still being answered. The saved
    // messages above are the thread *without* this turn, it has not been
    // written yet, or exists only as a half-finished checkpoint row, which is
    // the reported "empty message bubble". Drop that partial and put the live
    // nodes back instead.
    const bubbles = $("chat-messages").querySelectorAll(".msg");
    const lastAssistant = [...bubbles].reverse().find((b) => b.classList.contains("assistant"));
    if (lastAssistant && !lastAssistant.textContent.trim()) {
      lastAssistant.previousElementSibling?.classList.contains("msg")
        && lastAssistant.previousElementSibling.remove();
      lastAssistant.remove();
    }
    reattachStreamingTurn();
  } else if (!full.messages.length) {
    renderChatEmptyState();
  }
  if (lastQuestionText) lastChatQuestion = lastQuestionText;
  lazyScript("/js/chat-time.js").then(() => stampChatTimes(full.messages));
  loadConversationList();
  //: Where it was left, not always its end (Placed 2026-09-09 item 99 (b)).
  if (isStreamingConversation(full.id)) chatScrollToEnd();
  else restoreChatPosition(full.id);
}

async function loadChatSuggestions() {
  // Only the welcome placeholder may be present, real messages hide the chips.
  if ($("chat-messages").querySelector(".msg")) return;
  loadChatSuggestions.pending = true;
  const picks = await apiJson("/chat/suggestions").catch(() => []);
  loadChatSuggestions.pending = false;

  // Re-check after the await in case a message was sent while we waited
  if ($("chat-messages").querySelector(".msg")) return;

  // batch-a.md's "left open" item: `#chat-suggest` is on loan to `.chat-empty`
  // (see the long comment on `openConversation` below) and `newChatConversation`
  // used to wipe `#chat-messages` with a bare `replaceChildren()` without
  // sending it home first, so a "+ New" click while this call was still
  // awaiting the network took the element it was about to write to with it.
  // `newChatConversation` returns it home first now (below), so this should
  // not fire in practice any more; kept as the same defensive `?.`
  // `openConversation` already uses at its own call site, since a null box
  // here would otherwise throw past the point where anything could tell.
  const box = $("chat-suggest");
  if (!box) return;
  clearSkeletons(box);
  box.replaceChildren();
  box.classList.toggle("hidden", picks.length === 0);
  //: The empty card shows skeletons for these (`renderChatEmptyState`); the
  //: chips go in below in this same task, so no frame shows neither.
  $("chat-messages").querySelector(".chat-empty")?.classList.remove("chat-empty-waiting");
  if (!picks.length) return;
  const label = document.createElement("span");
  label.className = "muted";
  //: UX-07: with no model a chip goes to Notes, Ask, and says so.
  label.textContent = aiIsOff() ? "Try in Notes, Ask:" : "Try asking:";
  box.appendChild(label);
  for (const question of picks) {
    //: No model: the chips go to Notes, Ask, like the dashboard's Ask tile
    //: (INBOX 472: they answered "no saved notes" over two notes).
    const chipEl = chip(question, "", async () => {
      if (aiIsOff()) {
        await switchTab("notes");
        showNotesSection("ask");
        $("question").value = question;
        askQuestion(question);
        return;
      }
      sendChatMessage(question);
    });
    box.appendChild(chipEl);
  }
  //: They arrive after the welcome was drawn, so the welcome takes them now.
  const empty = $("chat-messages").querySelector(".chat-empty");
  if (empty && !empty.contains(box)) empty.appendChild(box);
  // These chips arrive after the tab is drawn and are a row or two of height
  // the composer's fit was measured without.
  refitComposer();
}

// Personas section in Settings (Wave C, editing + reset in Wave D).
// Mirrors the backend's built-ins: editing one saves an override with the
// same name (the saved list wins), and Reset deletes the override.
//: The name, and the function that reads it. The function is kept even now
//: that the constant is declared above it, because `GUIDE_NAME` is still
//: settings.js's and the two are read the same way; the `typeof` guard is
//: what stopped the first version of this throwing at boot, when the
//: constant lived in the last script on the page and `renderPlanToggle()`
//: read it at load.
//: One name for the notebook's AI, spelt once (INBOX 225). It lives here
//: rather than in settings.js because index.html loads app.js first and
//: settings.js last: a module-level string anywhere else in the app can read
//: this one at load time, and could not read a constant declared in the last
//: script on the page. The backend's `AI_NAME` in ai/__init__.py is the same
//: word.
const AI_NAME = "Atlas";

function aiNameNow() {
  return typeof AI_NAME === "string" ? AI_NAME : "Atlas";
}

//: The built-in librarian is Atlas; a preference saved as "Librarian" from
//: before the rename reads as Atlas everywhere (INBOX 237).
function personaDisplayName(name) {
  return !name || name === "Librarian" ? aiNameNow() : name;
}

// --- thinking words (rotating words beside the thinking dots) --------------
//
// Asked for directly: rotating "thinking words" next to the three-dot
// indicator, like Claude Code's ("Pondering…", "Spelunking…"), customisable
// per persona. The app's own default, and Atlas's (the built-in persona
// most worth a voice of its own); Coach's and Analyst's are the other two
// built-ins. `PersonaItem.thinking_words` (routes_settings.py) is where a
// custom override for any of these, or for a person's own persona, lives:
// this file only supplies what a persona gets when it has never set one.
const DEFAULT_THINKING_WORDS = [
  "Thinking", "Pondering", "Leafing through your notes", "Connecting the dots",
  "Following a thread", "Mulling it over", "Cross-referencing", "Gathering thoughts",
  "Tracing the links", "Sifting", "Weighing it up", "Piecing it together",
  "Reading between the lines", "Consulting the margins", "Untangling", "Distilling",
];
const ATLAS_THINKING_WORDS = [
  "Stargazing", "Charting constellations", "Consulting the stars", "Drifting through the nebula",
  "Orbiting the question", "Tracing starlight", "Aligning the planets", "Catching a comet",
  "Listening between the stars", "Counting moons", "Weaving stardust", "Following a meteor",
  "Spinning up a galaxy", "Reading the night sky", "Gathering starlight", "Mapping your cosmos",
];
const COACH_THINKING_WORDS = [
  "Cheering you on", "Spotting your wins", "Tracking your progress", "Finding your next step",
  "Celebrating the small stuff", "Looking for momentum", "Noticing what is working", "Building on your streak",
  "Coaching it through", "Setting the pace", "Looking for a breakthrough", "Weighing your options",
  "Finding the encouraging angle", "Charting your growth", "Rooting for you", "Keeping score of progress",
];
const ANALYST_THINKING_WORDS = [
  "Crunching the numbers", "Extracting the facts", "Spotting the pattern", "Cross-checking the data",
  "Organising the findings", "Running the figures", "Verifying the details", "Mapping the variables",
  "Isolating the signal", "Tabulating the results", "Auditing the notes", "Correlating the evidence",
  "Drawing the trend line", "Parsing the record", "Weighing the evidence", "Compiling the summary",
];

//: Which built-in list belongs to which built-in name. A function, like
//: `builtinPersonas()` beside it, since the app's own persona's key is
//: `aiNameNow()`, not a literal "Atlas": Atlas's own words apply only while
//: the AI is still actually named that, the same test `chatHeadIsAtlas`
//: (chat-agent.js) already makes for the avatar.
function builtinThinkingWords() {
  const name = aiNameNow();
  return {
    [name]: name === "Atlas" ? ATLAS_THINKING_WORDS : DEFAULT_THINKING_WORDS,
    Coach: COACH_THINKING_WORDS,
    Analyst: ANALYST_THINKING_WORDS,
  };
}

//: **What rotates beside the thinking dots for a given persona.** A custom
//: override (`PersonaItem.thinking_words`, saved through the persona editor
//: or "Suggest with AI") wins; a built-in persona's own list is next; the
//: app's default list is what everyone else, including a person's own
//: from-scratch persona, gets. `personaName` is whatever `typingDots`/
//: `progressLine` were handed, the same value `personaDisplayName` already
//: normalises everywhere else (`null`, `"Librarian"`, a real name).
function thinkingWordsFor(personaName) {
  const writer = personaDisplayName(personaName);
  const overrides = (prefsCache && prefsCache.personas) || [];
  const custom = overrides.find((p) => p.name === writer || p.name === personaName);
  if (custom && Array.isArray(custom.thinking_words) && custom.thinking_words.length) {
    return custom.thinking_words;
  }
  const builtin = builtinThinkingWords();
  return builtin[writer] || DEFAULT_THINKING_WORDS;
}

//: **The feature's own switch, stored the way its nearest sibling control
//: is.** `progress-motion` (chat.js's `progressMotionWanted`, settings.js's
//: Appearance section) governs the same indicator and is a per-browser
//: `localStorage` setting, never sent to the server: this matches it rather
//: than round-tripping `/preferences` for a display toggle, and reads
//: `localStorage` directly rather than through `appearancePref` (settings.js,
//: a lazily-fetched-feeling name but actually boot-loaded; direct is simpler
//: and asks nothing of load order either way). Missing (never set) or "on"
//: means shown, matching this app's other on-by-default switches
//: ("avatar-follow", "grammar_check").
function wantsThinkingWords() {
  try {
    return prefs.get("show-thinking-words", null) !== "off";
  } catch {
    return true; // no localStorage (private mode, a blocked origin): default on
  }
}

//: A function, not a table: the librarian is named after the app's AI
//: (`AI_NAME`, settings.js), so its key and its prompt are built from that
//: name when asked for, the same way `librarian.DEFAULT_PERSONA` is built
//: from the backend's `AI_NAME` (the owner, 2026-09-14: "since you were
//: using {ai name} as the ai name variable, should that be used instead??").
function builtinPersonas() {
  const name = aiNameNow();
  return {
    [name]: `You are ${name}, the librarian of this notebook: warm, curious and a little witty. You know these notes well, love spotting how they connect, speak plainly, and say so when the notes don't know.`,
    Coach:
      "You are an encouraging personal coach reviewing the user's notes. " +
      "Spot patterns, celebrate progress, and suggest one concrete next step.",
    Analyst:
      "You are a precise analyst. Extract the facts, numbers, and patterns " +
      "from the notes and organise your answer clearly.",
  };
}

let personaEditing = null; // name currently in inline-edit mode


//: The names the pickers offer, from what is already in memory.
function personaNamesNow() {
  const custom = ((prefsCache && prefsCache.personas) || []).map((p) => p.name);
  return [...new Set([...Object.keys(builtinPersonas()), ...custom])];
}


// A second, independent picker (asked for directly): the dashboard greeting
// otherwise always spoke in whichever persona Chat had active, with no way
// to give the notebook's own front page a different voice. "" means "no
// override" and falls back to active_persona server-side, same clear-with-
// empty-string convention display_name/dashboard_persona already share.
function renderDashboardPersonaSelect(names) {
  const select = $("dashboard-persona-select");
  const current = (prefsCache && prefsCache.dashboard_persona) || "";
  select.replaceChildren();
  const sameAsChat = document.createElement("option");
  sameAsChat.value = "";
  sameAsChat.textContent = "Same as Chat";
  select.appendChild(sameAsChat);
  for (const name of names) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  }
  //: A saved name that is no longer in the list (the built-in was
  //: "Librarian" before it became Atlas; a custom persona can be deleted)
  //: left the select with no selected option, which the enhanced opener
  //: drew as an empty box with a chevron (the owner, 2026-09-14: "this
  //: dashboard welcome message persona dropdown box is broken visually").
  //: The old built-in reads as the new one; anything else unknown reads as
  //: "Same as Chat", which is what the server falls back to as well.
  const wanted = personaDisplayName(current) === current || current === "Librarian" ? personaDisplayName(current) : current;
  select.value = names.includes(wanted) ? wanted : "";
  paintDashboardPersonaMark();
}

//: "Same as Chat" follows Chat's picker, so its face does too.
document.addEventListener("change", (event) => {
  if (event.target?.id === "persona-select") paintDashboardPersonaMark();
});
