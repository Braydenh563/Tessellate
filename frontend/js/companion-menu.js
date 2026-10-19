// companion-menu.js: the companion's menu and the enlarged view of a face,
// moved out of avatars.js on 2026-10-05 for the boot-script gzip budget
// (tests/test_boot_budget.py). Both open only on a gesture (a press, a right
// click, a double-click or a long press on the companion or a face), so the
// boot carries stand-ins (`LAZY_ENTRY_POINTS.companionMenu`, app.js) that
// fetch this file on first use and then call the real function.

//: **The large view.** A click on a face that is not part of a control
//: opens it big, animated, with what it was read as, so the joke can be
//: seen at a size where it lands.
//:
//: **The companion comes into it itself** (INBOX 443, the owner: "if the
//: companion is doing a specific action and i double click it to view it in
//: the enlarged window, I want it to keep doing that action unless poked or
//: something else happens"). Opened from the companion (`visit`), the large
//: view is not a new drawing of it: the companion's own element moves into
//: the card for as long as the card is open (`nameMarkBuddyVisit`), so its
//: act, its face, its props, its sleep and its pose are the ones it had,
//: and its own timer ends the act when the act ends. A poke is its own
//: click handler; an app event its own cue. Closing sends it home to the
//: perch it left.
//:
//: **And alive while you watch** (the owner: "needs more life and not just
//: a statue"): its beat is every 2.5 to 6 seconds in here rather than 20 to
//: 60 (`nameMarkBuddySchedule`), its eyes and head follow the pointer across
//: the whole card (`nameMarkBuddyHeadAt`), a hover pets it, and it says one
//: of its lines now and then (`nameMarkViewerChatter`). Any other face gets
//: the same: the shared idle acts at the view's own quicker beat.
//: Under reduced motion it only blinks, gently (`nameMarkViewerBlinks`).
function openNameMarkViewer(seed, { visit = false } = {}) {
  //: One at a time: a double-click opens it once.
  if (document.querySelector(".nm-viewer")) return;
  const opener = document.activeElement;
  const openedAt = performance.now();
  const buddy = visit ? document.getElementById("nm-buddy") : null;
  const visiting = !!buddy && (buddy.dataset.seed || "") === (seed || "") && !buddy.classList.contains("nmb-away");
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay nm-viewer";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", `${seed || "Face"}, enlarged`);
  const card = document.createElement("div");
  card.className = "card modal-card nm-viewer-card";
  //: The dialog-head recipe (DESIGN.md, "A dialog's head"): its name, then
  //: the icon X. Close was a word button at the foot.
  const head = document.createElement("div");
  head.className = "dialog-head nm-viewer-head";
  const name = document.createElement("h2");
  name.className = "dialog-head-title nm-viewer-name";
  name.textContent = seed || "Unnamed";
  const actions = document.createElement("span");
  actions.className = "dialog-head-actions";
  //: The companion's own face is a button, so the stage around it is not
  //: one; any other face is drawn inside a button that pokes it.
  const stage = document.createElement(visiting ? "div" : "button");
  stage.className = "nm-viewer-stage";
  if (!visiting) {
    stage.type = "button";
    stage.title = "Poke it";
  }
  //: The whole character, as the companion draws it, at 2.2 times.
  const figure = document.createElement("span");
  figure.className = "nm-viewer-figure";
  if (visiting) {
    //: What it sits on, drawn only for that pose (the CSS).
    const ledge = document.createElement("span");
    ledge.className = "nm-viewer-ledge";
    ledge.setAttribute("aria-hidden", "true");
    figure.appendChild(ledge);
  } else figure.appendChild(characterFor(seed).figure());
  stage.appendChild(figure);
  //: One line of description: what it is.
  const reading = document.createElement("p");
  reading.className = "muted nm-viewer-reading";
  //: Atlas is not a face read from its name (its reading gave "Calm face
  //: with shades", which describes nothing on the screen): it says who it is.
  //: A face with nothing read from its name used to say "A face of its
  //: own", which says nothing (the owner): now what it is.
  reading.textContent = isAtlasSeed(seed) ? "The app's own guide" : nameMarkTitle(nameMood(seed)) || "Its own face, read from its name";
  let home = null;
  let chatter = 0;
  let blinks = 0;
  const shut = () => {
    clearTimeout(chatter);
    clearTimeout(blinks);
    if (home) home();
    home = null;
    overlay.remove();
    document.removeEventListener("keydown", onKey, true);
    if (opener && typeof opener.focus === "function" && opener.isConnected) opener.focus();
  };
  const close = smallButton("ph:x", "Close", shut);
  close.classList.add("icon-only", "dialog-head-btn");
  actions.appendChild(close);
  head.append(name, actions);
  card.append(head, stage, reading);
  overlay.appendChild(card);
  const onKey = (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      shut();
    }
  };
  //: Poked, its face answers too, more each poke in a row (B62).
  let pokes = 0;
  let pokedAt = 0;
  if (!visiting) {
    stage.addEventListener("click", () => {
      nameMarkReact(stage.querySelector(".name-mark"));
      nameMarkSay(stage, nameMarkLine(seed));
      pokes = performance.now() - pokedAt < 4000 ? pokes + 1 : 1;
      pokedAt = performance.now();
      nameMarkViewerFace(figure, seed, NM_VIEWER_POKED[Math.min(pokes, NM_VIEWER_POKED.length) - 1], 2400);
    });
  }
  //: Not closed by the second click of the double-click that opened it:
  //: a click on the ground within 400ms of opening is that click.
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay && performance.now() - openedAt > 400) shut();
  });
  document.addEventListener("keydown", onKey, true);
  document.body.appendChild(overlay);
  if (visiting) home = nameMarkBuddyVisit(figure);
  if (visiting && !home) figure.appendChild(characterFor(seed).figure());
  if (home) card.appendChild(nameMarkViewerActs(document.getElementById("nm-buddy")));
  nameMarkViewerFit(figure);
  requestAnimationFrame(() => nameMarkViewerFit(figure));
  close.focus();
  //: Its lines, one every 7 to 13 seconds while the view is open; not
  //: asleep, not under a line it has just been poked into saying.
  const talk = () => {
    chatter = setTimeout(() => {
      if (!overlay.isConnected) return;
      const asleep = !!home && nameMarkBuddyAsleep(document.getElementById("nm-buddy"));
      const host = home ? document.getElementById("nm-buddy") : stage;
      if (!asleep && host && !host.querySelector(":scope > .nm-say")) {
        nameMarkSay(host, nameMarkLine(seed));
        //: A line said with a face to match, a neighbouring one, and back.
        if (!home) nameMarkViewerFace(figure, seed, nameMarkViewerNear(seed), 2600);
      }
      talk();
    }, 7000 + Math.random() * 6000);
  };
  talk();
  //: Glad to be looked at: a brighter face as the view opens (B62).
  if (!home) setTimeout(() => nameMarkViewerFace(figure, seed, nameMarkViewerNear(seed, true), 2400), 350);
  if (nameMarkIdleQuiet()) {
    blinks = nameMarkViewerBlinks(figure);
    return;
  }
  //: Alive while it is open: a first small act soon, then the view's beat,
  //: and its eyes and head on the pointer (INBOX 591; its loops are the
  //: CSS's, under `.nm-viewer-figure > .nm-figure.nm-live`).
  if (!home) {
    setTimeout(() => figure.isConnected && nameMarkIdleAct(figure, nameMarkBuddyActOff("wave") ? "glance" : "wave"), 700);
    setTimeout(() => figure.isConnected && nameMarkIdleAct(figure, "glance"), 2600);
    nameMarkIdleWake();
    nameMarkViewerFollow(overlay, figure);
  }
}

//: **Things to ask of it, in its large view** (Brief 88, the owner:
//: "improve the actions and stuff for the expanded companion panel").
//: The view only watched it; now a row of chips under its line asks for
//: an act, the ones its pose allows (a hop needs its feet under it), and
//: Atlas's own three when it is Atlas. Each plays as a poke does: a
//: sleeping companion wakes for it first. One chip row, the interactive
//: chip recipe (DESIGN.md), labelled for a screen reader as a group.
const NM_VIEWER_ACTS = [
  ["wave", "Wave"], ["cheer", "Cheer"], ["hop", "Hop"], ["stretch", "Stretch"], ["shrug", "Shrug"], ["wiggle", "Wiggle"],
  ["juggle", "Juggle stars"], ["map", "Read its map"], ["meditate", "Meditate"],
];
function nameMarkViewerActs(buddy) {
  const row = document.createElement("div");
  row.className = "nm-viewer-acts";
  row.setAttribute("role", "group");
  row.setAttribute("aria-label", "Ask it to");
  const atlas = nameMarkBuddyHasAtlas(buddy);
  for (const [act, label] of NM_VIEWER_ACTS) {
    const spec = NAME_MARK_BUDDY_ACTS[act];
    if (!spec || !spec.poses.includes(nmb.pose) || (spec.atlas && !atlas)) continue;
    row.appendChild(chip(label, "nm-viewer-act", () => {
      if (nameMarkBuddyAsleep(buddy)) nameMarkBuddyWake(true);
      nameMarkBuddyAct(act);
    }));
  }
  return row;
}

//: **Its menu opens at it** (INBOX 426 p, the owner: "the right click
//: companion dropdown menu doesnt appear where the companion is"). However
//: it was opened (a right-click, a hold, the keyboard), the menu is placed
//: from the companion's own box: beside it on the side with room, its top
//: level with the companion's, kept inside the window. `openMenuAtPoint`
//: builds it (the app's one menu), and it is then shifted by a `translate`
//: to that place, which leaves how the menu was positioned alone. While it
//: is open the companion does not go anywhere on its own.
//:
//: **Opened by the pointer, it opens at the pointer** (INBOX 426 x, 84.png,
//: round 4): `at` is where a right-click or a long press was, and the menu
//: opens there, the way every other context menu does; from the keyboard
//: it opens beside the companion's box. And a move already under way stops
//: where it is drawn: measured at 1.25 and 1.5 scale, a right-click mid-walk
//: or mid-poof opened the menu at the companion and the move then carried
//: the companion 69 to 136px away from it. Its next place is chosen on its
//: own beat, once the menu has closed.
function nameMarkBuddyMenu(buddy, at = null) {
  if (typeof openMenuAtPoint !== "function") return;
  const face = buddy.querySelector(".nm-buddy-face");
  if (nmb.anim && nmb.anim.playState === "running") {
    const drawn = buddy.getBoundingClientRect();
    nmb.anim.cancel();
    nmb.hopAnim?.cancel();
    buddy.classList.remove("nmb-walking", "nmb-poofing");
    nmb.glue = null;
    nameMarkBuddyWatch();
    nameMarkBuddyRide(null, Math.round(drawn.left), Math.round(drawn.top));
    buddy.dataset.pose = nmb.pose = "float";
    buddy.dataset.legs = nmb.legs = "";
    nameMarkBuddyQueuePlace();
  }
  const tab = nameMarkBuddyTab();
  const spots = nameMarkBuddySpots();
  const items = [
    { group: "say", label: "ph:hand-waving Say hello", run: () => face.click() },
    { group: "say", label: "ph:arrows-out Enlarge", run: () => openNameMarkViewer(buddy.dataset.seed || "", { visit: true }) },
    //: **Pinned means pinned** (INBOX 426 l, the owner: "when I press the
    //: option to stay in the same spot across pages ... it still moves"):
    //: the place on screen and the pose are kept, and nothing but you moves
    //: it again (no perch, no errand, no beat) until you drag it or call it
    //: back.
    { group: "place", label: "ph:push-pin Stay here on every page", run: () => {
      //: Where it is drawn now: mid-walk, `nmb.x` is where it was going,
      //: and pinning there made it jump at the moment it was told to stay.
      const box = buddy.getBoundingClientRect();
      const x = Math.round(box.left);
      const y = Math.round(box.top);
      nmb.anim?.cancel();
      nmb.hopAnim?.cancel();
      nameMarkBuddyKeepSpots({ "*": { x, y, pose: nmb.pose, legs: nmb.legs, side: buddy.dataset.side || "", w: innerWidth, h: innerHeight, keep: 1 } });
      nameMarkBuddyMoveTo(buddy, { kind: "pinned", x, y, pose: nmb.pose, legs: nmb.legs, side: buddy.dataset.side || "" }, true);
      //: Pinned where it already is, nothing moved, so the press showed no
      //: sign of having worked (the popup-actions audit): it nods, where a
      //: nod fits its pose.
      if (NAME_MARK_BUDDY_ACTS.nod.poses.includes(nmb.pose) && !nameMarkBuddyStill()) nameMarkBuddyAct("nod");
    } },
  ];
  if (spots[tab]) {
    items.push({ group: "place", label: "ph:push-pin-slash Let it choose its spot here", run: () => {
      const next = { ...spots };
      delete next[tab];
      nameMarkBuddyKeepSpots(next);
      placeNameMarkBuddy(buddy, false, [nmb.x, nmb.y]);
    } });
  }
  //: **Tuck it away for a while** (the owner at release: "a way to tuck it
  //: away but still have it there"): it goes behind the status bar with
  //: only its head showing, the bar perch's own `legs: "peek"`, and stays
  //: there, on this page only and not saved, until it is clicked, dragged
  //: or called back.
  const { bottom } = nameMarkBuddyLedges();
  if (bottom && !nmb.tucked) {
    items.push({ group: "place", label: "ph:arrow-line-down Tuck behind the bar", run: () => {
      const x = Math.max(NMB_GUTTER, Math.min(innerWidth - NMB_GUTTER - NMB_W, Math.round(buddy.getBoundingClientRect().left)));
      nmb.tucked = true;
      nameMarkBuddyMoveTo(buddy, { kind: "pinned", pose: "sit", legs: "peek", x, y: bottom.top - NMB_SEAT, edge: { el: document.getElementById("status-bar"), type: "top", kind: "bar", y: bottom.top } });
    } });
  }
  items.push({ group: "place", label: "ph:arrow-counter-clockwise Call back and reset its place", run: nameMarkBuddyCallBack });
  //: **Who it is, how Atlas looks, its size, and the settings behind them,
  //: one flyout each** (the owner: "extend this menu a bit maybe with
  //: sub-sections if necessary, for things such as a quick link to the
  //: profile/personas/appearences tab, toggling various features such as
  //: masculine/feminine, which companion is displayed etc."). Submenus
  //: (`items`, the kebab recipe's flyout) so the menu stays eight rows; the
  //: current choice in each is ticked. Each choice goes through its own
  //: Appearance control's change, so the menu and Settings cannot disagree.
  const tick = (on, label) => `${on ? "ph:check" : "ph:dot-outline"} ${label}`;
  const choose = (id, value) => {
    const select = document.getElementById(id);
    if (!select) return;
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  };
  let who = "off";
  try {
    who = prefs.get("avatar-buddy", null) || "off";
  } catch (e) {
    who = "off";
  }
  items.push({
    group: "who",
    label: "ph:user-switch Companion",
    items: [
      ...[["atlas", "Atlas"], ["me", "You"], ["persona", "The chat's persona"], ["custom", "Your own character"]]
        .map(([value, label]) => ({
          label: tick(who === value, label),
          //: Your own character, never made: chosen, and its maker opened,
          //: rather than a face quietly made up for it.
          run: () => {
            choose("avatar-buddy", value);
            if (value === "custom" && !nameMarkBuddyMade("custom")) nameMarkBuddyMakeIt("custom");
          },
        })),
      ...(nameMarkBuddyMade("me") ? [] : [{ label: "ph:user-circle-plus Create your avatar", run: () => nameMarkBuddyMakeIt("me") }]),
    ],
  });
  const look = document.getElementById("atlas-look")?.value || "auto";
  items.push({
    group: "who",
    label: "ph:coat-hanger Atlas look",
    items: [["masculine", "Masculine"], ["feminine", "Feminine"], ["auto", "Auto: match your faces"]]
      .map(([value, label]) => ({ label: tick(look === value, label), run: () => choose("atlas-look", value) })),
  });
  const size = nmb.scale || 1;
  items.push({
    group: "who",
    label: "ph:resize Size",
    items: Object.entries(NMB_SIZES).map(([name, value]) => ({
      label: tick(size === value, `${name[0].toUpperCase()}${name.slice(1)}`),
      title: `Make it ${name}`,
      run: () => nameMarkBuddySetSize(value),
    })),
  });
  items.push({
    group: "settings",
    label: "ph:gear Settings",
    items: [
      { label: "ph:palette Appearance, the companion", run: () => openSettingsModal("appearance", "avatar-buddy-row") },
      { label: "ph:user-circle Profile, your look", run: () => openSettingsModal("preferences") },
      { label: "ph:mask-happy Personas", run: () => openSettingsModal("personas") },
    ],
  });
  items.push({ group: "hide", label: "ph:eye-slash Hide", run: () => nameMarkBuddyHide(buddy) });
  const box = face.getBoundingClientRect();
  //: In the enlarged view (`nmb.visit`) only who it is, its look and its
  //: size: a place on the page, Enlarge and Hide mean nothing inside the card.
  const shown = nmb.visit ? items.filter((item) => item.group === "who") : items;
  openMenuAtPoint(shown, "Companion", at ? at[0] : box.left, at ? at[1] : box.top);
  const menu = [...document.querySelectorAll(".pointer-menu-host .action-menu, .action-menu.action-menu-escaped")]
    .find((el) => !el.classList.contains("hidden") && el.getBoundingClientRect().width);
  nmb.menu = menu || null;
  if (!menu) return;
  //: At the pointer: only kept inside the window.
  const inside = () => {
    menu.style.translate = "";
    const now = menu.getBoundingClientRect();
    const margin = 8;
    const dx = Math.min(0, innerWidth - margin - now.right) + Math.max(0, margin - now.left);
    const dy = Math.min(0, innerHeight - margin - now.bottom) + Math.max(0, margin - now.top);
    if (dx || dy) menu.style.translate = `${Math.round(dx)}px ${Math.round(dy)}px`;
  };
  //: Placed from the companion's box as it is each time: a panel moving
  //: under it while the menu is open (a transform) carries both.
  const beside = () => {
    const box = face.getBoundingClientRect();
    menu.style.translate = "";
    const now = menu.getBoundingClientRect();
    const gap = 6;
    const margin = 8;
    let left = box.right + gap;
    if (left + now.width > innerWidth - margin) left = box.left - gap - now.width;
    left = Math.min(Math.max(margin, left), innerWidth - margin - now.width);
    const top = Math.min(Math.max(margin, box.top), innerHeight - margin - now.height);
    menu.style.translate = `${Math.round(left - now.left)}px ${Math.round(top - now.top)}px`;
  };
  //: Placed now, and once more on the next frame: the menu's own opening
  //: settles its box a frame later, which measured as the menu landing 13px
  //: above the companion's top when placed only once.
  const place = at ? inside : beside;
  place();
  nmb.menuPlace = place;
  requestAnimationFrame(() => {
    if (menu.isConnected && !menu.classList.contains("hidden")) place();
  });
}

//: **The drawing's own box, kept clear of the words under it** (the owner,
//: 2026-09-27: "make sure the text doesnt clash with the avatar in the
//: expanded companion panel"). The figure's box is the 64 by 92 companion
//: at 2.2 times, but the drawing is not that box: Atlas's wisps and tail
//: hang below its feet, a hat stands above its head. Measured before, the
//: drawing ran 4 to 16px into the name for every face at 1440 and 1093, and
//: a beanie was cut 5px by the card's top. So the drawing is measured as it
//: is drawn (every visible part's box) and the figure is given margins to
//: take in what reaches past it, before the card is first painted (here and
//: once more a frame later, for a part that lays out late). Only ever grown,
//: so nothing under it moves once it has been seen. The card's own gap then
//: separates it from the name, which a mood's small loop stays inside.
function nameMarkViewerFit(figure) {
  if (!figure.isConnected) return;
  const box = figure.getBoundingClientRect();
  let top = box.top;
  let bottom = box.bottom;
  let left = box.left;
  let right = box.right;
  for (const el of figure.querySelectorAll("*")) {
    if (el.closest("defs, clipPath, mask, filter, linearGradient, radialGradient, symbol")) continue;
    if (el instanceof SVGGElement || el instanceof SVGSVGElement) continue;
    //: An HTML box around parts only places them; its own box is not ink.
    if (!(el instanceof SVGElement) && el.children.length) continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none" || Number(cs.opacity) < 0.05) continue;
    top = Math.min(top, r.top);
    bottom = Math.max(bottom, r.bottom);
    left = Math.min(left, r.left);
    right = Math.max(right, r.right);
  }
  const grow = (side, px) => {
    const was = parseFloat(figure.style[side]) || 0;
    if (px > was) figure.style[side] = `${Math.ceil(px)}px`;
  };
  grow("marginTop", box.top - top);
  grow("marginBottom", bottom - box.bottom);
  const side = Math.max(box.left - left, right - box.right);
  grow("marginLeft", side);
  grow("marginRight", side);
}

//: **A face in its large view watches the pointer** (INBOX 591, the owner:
//: the view "has no life to it like with atlas and the companion itself").
//: Its face is not one of the faces on screen the page's follow listener
//: nudges (that one tilts a whole face 10 degrees, which on a standing
//: figure tips the body over), so the view has its own: over the dialog,
//: at most once a frame, the pointer's offset from the head as two numbers
//: from -1 to 1 (`--nmv-x`, `--nmv-y` on the figure) that the CSS turns into
//: the companion's own attending look, eyes first and the head after.
//: Nothing with Faces follow the pointer off; never under reduced motion
//: (the caller returns before this); gone with the dialog.
function nameMarkViewerFollow(overlay, figure) {
  //: The face it has now: a reaction swaps it (`nameMarkViewerFace`).
  const face = () => figure.querySelector(":scope > .nm-figure:not(.nmv-leaving)");
  if (!face()) return;
  let frame = 0;
  let at = null;
  const set = (x, y) => {
    const drawn = face();
    drawn?.style.setProperty("--nmv-x", x.toFixed(2));
    drawn?.style.setProperty("--nmv-y", y.toFixed(2));
  };
  overlay.addEventListener("pointermove", (event) => {
    if (document.documentElement.dataset.avatarFollow === "off") return;
    at = [event.clientX, event.clientY];
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      const drawn = face();
      if (!drawn) return;
      const head = (drawn.querySelector(".nm-buddy-head") || drawn).getBoundingClientRect();
      const reach = Math.max(240, head.width * 3);
      const clamp = (v) => Math.max(-1, Math.min(1, v));
      set(clamp((at[0] - (head.left + head.width / 2)) / reach), clamp((at[1] - (head.top + head.height / 2)) / reach));
    });
  }, { passive: true });
  //: The pointer gone from the window: it looks ahead again, slowly (the
  //: CSS's transition).
  overlay.addEventListener("pointerleave", () => set(0, 0), { passive: true });
}

//: **Its face reacts** (B62, the owner: "The profile avatar in the enlarged
//: popup from double clicking the profile picture doesn't have any life to
//: it"). A face drawn from a name has one mood, and the view kept it: its
//: loops and small acts moved it, but under reduced motion (only blinks) it
//: was a still picture with a caption. Now its face changes the way the
//: companion's does (`nameMarkBuddyExpress`): brighter as the view opens,
//: glad, then excited, then laughing as it is poked in a row, a
//: neighbouring look with each line it says, and back, each a crossfade
//: (an opacity change, so also under reduced motion). Not with Avatar
//: animation off; not Atlas (its moods are its own) or a character of its own.
const NM_VIEWER_POKED = ["happy", "excited", "laughing", "laughing", "unimpressed"];
function nameMarkViewerNear(seed, bright = false) {
  const mood = nameMood(seed).mood || "";
  const near = (bright ? ["happy", "excited", "cute"] : NMB_EXPR_NEAR[mood] || NMB_EXPR_NEAR[""]).filter((e) => e !== mood);
  return near[Math.floor(Math.random() * near.length)] || "happy";
}
function nameMarkViewerFace(figure, seed, expr, ms) {
  if (!figure.isConnected || document.documentElement.dataset.avatarMotion === "off" || isAtlasSeed(seed) || characterRendererFor(seed)) return;
  const old = figure.querySelector(":scope > .nm-figure:not(.nmv-leaving)");
  if (!old || (old.dataset.expr || "") === expr) return;
  const next = nameCharacterFigure(seed, expr);
  next.dataset.expr = expr;
  for (const k of ["--nmv-x", "--nmv-y"]) next.style.setProperty(k, old.style.getPropertyValue(k) || "0");
  old.classList.add("nmv-leaving");
  old.after(next);
  const gone = () => old.remove();
  if (typeof next.animate === "function") next.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 280, easing: "ease-in-out" }).finished.then(gone, gone);
  else gone();
  clearTimeout(figure.nmvFace);
  figure.nmvFace = ms ? setTimeout(() => nameMarkViewerFace(figure, seed, "", 0), ms) : 0;
}

//: **Under reduced motion, a blink now and then** and nothing else (the
//: owner asked for "gentle opacity or blink only" there): the lids close
//: and open over 0.3s, every 4 to 8 seconds, on the compositor.
function nameMarkViewerBlinks(figure) {
  const run = () => {
    if (!figure.isConnected) return;
    for (const lid of figure.querySelectorAll(".nm-blinks")) {
      lid.animate?.([{ transform: "scaleY(1)" }, { transform: "scaleY(0.1)", offset: 0.5 }, { transform: "scaleY(1)" }], { duration: 300, easing: "ease-in-out" });
    }
    timer = setTimeout(run, 4000 + Math.random() * 4000);
  };
  let timer = setTimeout(run, 1500);
  return timer;
}

// Settings, Appearance, Saved companions: opened only with that pane, so
// it lives here (boot budget, 2026-10-17) behind a stand-in for
// `mountBuddyPresets` (LAZY_ENTRY_POINTS.companionMenu).
//: **Saved companions**, the custom themes' pattern for the companion:
//: every setting that makes it who it is, kept under a name in this
//: browser, applied in one press, renamed (its name back in the field, then
//: saved) and deleted. At most twelve.
const NMB_PRESET_KEYS = ["avatar-buddy", "atlas-look", "face-look", "avatar-buddy-custom", "avatar-buddy-size", "avatar-buddy-actions", "avatar-buddy-acts-off", "avatar-buddy-motion"];
const NMB_PRESET_MAX = 12;
let nmbPresetRenaming = "";
function nameMarkBuddyPresets() {
  try {
    const list = prefs.json("avatar-buddy-presets", []);
    return Array.isArray(list) ? list : [];
  } catch (e) {
    return [];
  }
}
function nameMarkBuddyKeepPresets(list) {
  try {
    prefs.set("avatar-buddy-presets", JSON.stringify(list));
  } catch (e) {
    // Not kept this time.
  }
  mountBuddyPresets();
}
function nameMarkBuddySavePreset() {
  const input = document.getElementById("avatar-buddy-preset-name");
  const name = (input?.value || "").trim().slice(0, 30);
  if (!name) {
    toast("Give the companion a name first.", "info");
    input?.focus();
    return;
  }
  const values = {};
  for (const key of NMB_PRESET_KEYS) {
    const v = prefs.get(key, null);
    if (v !== null) values[key] = v;
  }
  const others = nameMarkBuddyPresets().filter((p) => p.name !== name && p.name !== nmbPresetRenaming);
  if (others.length >= NMB_PRESET_MAX) {
    toast(`You can keep ${NMB_PRESET_MAX} saved companions: delete one first.`, "info");
    return;
  }
  nmbPresetRenaming = "";
  input.value = "";
  nameMarkBuddyKeepPresets([...others, { name, values }]);
  toast(`Saved “${name}”.`);
}
function nameMarkBuddyApplyPreset(preset) {
  for (const key of NMB_PRESET_KEYS) {
    if (preset.values?.[key] !== undefined) prefs.set(key, preset.values[key]);
    else prefs.remove(key);
  }
  nameMarkBuddyCustomCache = null;
  const acts = document.getElementById("avatar-buddy-activities");
  if (acts) acts.replaceChildren();
  if (typeof applyAppearance === "function") applyAppearance();
  if (typeof renderAppearance === "function") renderAppearance();
  const buddy = document.getElementById("nm-buddy");
  if (buddy) {
    delete buddy.dataset.seed;
    nameMarkBuddySetSize(nameMarkBuddyScaleSaved(), false);
    nameMarkBuddyToggles(buddy);
  }
  syncNameMarkBuddy();
  mountBuddyActivities();
  toast(`Applied “${preset.name}”.`);
}
function mountBuddyPresets() {
  const box = document.getElementById("avatar-buddy-presets");
  if (!box) return;
  box.replaceChildren();
  const list = nameMarkBuddyPresets();
  if (!list.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "Nothing saved yet: set the companion up how you like it, then save it here.";
    box.appendChild(empty);
  }
  for (const preset of list) {
    const row = document.createElement("div");
    row.className = "row avatar-buddy-preset";
    const apply = document.createElement("button");
    apply.type = "button";
    apply.className = "small";
    apply.textContent = preset.name;
    apply.title = `Apply “${preset.name}”`;
    apply.addEventListener("click", () => nameMarkBuddyApplyPreset(preset));
    const rename = document.createElement("button");
    rename.type = "button";
    rename.className = "ghost small";
    rename.textContent = "Rename";
    rename.addEventListener("click", () => {
      const input = document.getElementById("avatar-buddy-preset-name");
      nmbPresetRenaming = preset.name;
      input.value = preset.name;
      input.focus();
      input.select();
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost small";
    remove.textContent = "Delete";
    remove.setAttribute("aria-label", `Delete the saved companion “${preset.name}”`);
    remove.addEventListener("click", () => {
      nameMarkBuddyKeepPresets(nameMarkBuddyPresets().filter((p) => p.name !== preset.name));
      toast(`Deleted “${preset.name}”.`);
    });
    row.append(apply, rename, remove);
    box.appendChild(row);
  }
  const save = document.getElementById("avatar-buddy-preset-save");
  if (save && !save.dataset.wired) {
    save.dataset.wired = "1";
    save.addEventListener("click", nameMarkBuddySavePreset);
    document.getElementById("avatar-buddy-preset-name")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") nameMarkBuddySavePreset();
    });
  }
}

//: **The companion's mind** (B87c and B88c, the owner, 2026-10-17: "the
//: companion needs a lot of improvements in behaviour, actions and lifelike
//: ncp decision making"; "more movement, more transition and actions").
//: The pick (`nameMarkBuddyDecide`) weighed mood, the hour, warmth and its
//: perch, but not what you were doing, and the wait between picks was a
//: plain 20 to 60 second roll. With this file loaded (the first tick fetches
//: it, `nameMarkBuddyTick`), `nmb.mind` adds:
//: - **what you are doing** (`drive`): typing, it keeps you company quietly
//:   (it reads along, stops to think) and saves the big gestures; scrolling,
//:   it looks about; sitting there idle, it plays (juggles, stretches,
//:   tosses a star); gone a while, it winds down; the pointer close by, it
//:   notices you; each tab leans it to its own thing (a map on the graph,
//:   a book in notes, a think in chat);
//: - **when** (`nextIn`): still the decided 20 to 60 seconds (Brief 34,
//:   "fewer, longer, calmer"), placed in it by its energy, your typing, a
//:   big act just done and you idling, not by a roll alone;
//: - **into and out of an act** (`lead`, `after`): a beat of anticipation
//:   before a big gesture (a dip at the knees, a glance your way before a
//:   wave), a breath out after one, and sometimes the act that follows from
//:   it (a pleased nod after juggling, a think after reading its map, a
//:   stretch after meditating);
//: - **three new acts** (`NMB_MIND_ACTS`): it stops to think (a tilt, its
//:   hands a little up, a thinking face), it sighs, and Atlas tosses one
//:   star from its hand (the rig, atlas-motion.js).
//: All of it on the one timer and the acts' own timers: nothing new runs
//: between acts. Reduced motion and Still have none of the beats.
const NMB_MIND_ACTS = {
  ponder: { ms: 4200, w: 1, cool: 45000, poses: ["stand", "sit", "float", "lean"] },
  sigh: { ms: 1700, w: 0.7, cool: 60000, poses: ["stand", "sit", "float", "lean"] },
  toss: { ms: 4400, w: 1, cool: 70000, poses: ["stand", "float"], atlas: true },
};
const NMB_MIND_LEAD = ["wave", "stretch", "juggle", "toss", "shrug", "scratch", "facepalm", "map", "swing", "onehand", "feet", "kick"];
//: What follows from what, and how often: [act, chance].
const NMB_MIND_NEXT = {
  juggle: [["nod", 0.5]], toss: [["nod", 0.35]], map: [["ponder", 0.45], ["look", 0.25]],
  read: [["ponder", 0.35], ["stretch", 0.3]], meditate: [["stretch", 0.5]], stretch: [["yawn", 0.25], ["look", 0.25]],
  ponder: [["nod", 0.35], ["shrug", 0.2]], scratch: [["shrug", 0.2]], wave: [["glance", 0.35]], hop: [["look", 0.3]],
  lie: [["stretch", 0.55]], nap: [["stretch", 0.4], ["yawn", 0.2]], sigh: [["look", 0.3]],
};
const NMB_MIND_TABS = {
  notes: { read: 1.4, ponder: 1.2 }, documents: { read: 1.4, ponder: 1.2 }, library: { read: 1.5 },
  graph: { map: 1.8, look: 1.3, ponder: 1.2 }, chat: { ponder: 1.6, tilt: 1.2 }, timeline: { look: 1.2, map: 1.2 },
};
const NMB_MIND = {
  //: Multipliers on the pick's weights for what you are doing right now.
  drive(now = Date.now(), idle = now - nmb.lastInput, scrollAgo = nameMarkBuddyScrollAgo(), tab = nameMarkBuddyTab()) {
    const out = {};
    const mul = (table) => {
      for (const [act, k] of Object.entries(table)) out[act] = (out[act] ?? 1) * k;
    };
    const typing = now - (nmb.keyAt || 0) < 8000;
    if (typing) mul({ read: 1.6, ponder: 1.8, tilt: 1.3, look: 0.6, glance: 0.5, wave: 0.3, hop: 0.3, stretch: 0.5, juggle: 0.4, toss: 0.5, sigh: 0.6 });
    else if (scrollAgo < 4000) mul({ look: 1.8, turn: 1.4, glance: 1.4, read: 0.6 });
    else if (idle > 3 * 60 * 1000) mul({ yawn: 1.5, meditate: 1.8, sigh: 1.5, lie: 1.3, beanbag: 1.3, juggle: 0.6, hop: 0.5, wave: 0.6 });
    else if (idle > 20000) mul({ juggle: 1.8, toss: 1.8, stretch: 1.6, map: 1.4, hop: 1.3, wave: 1.3, ponder: 1.2, swing: 1.4, kick: 1.4 });
    //: The pointer within reach a moment ago: it has noticed you.
    const p = nmb.pointer;
    if (p && idle < 5000 && !typing && Number.isFinite(nmb.x) && Math.hypot(p[0] - nmb.x - NMB_W / 2, p[1] - nmb.y - NMB_HEAD / 2) < 240) mul({ glance: 2.2, wave: 1.5, tilt: 1.3 });
    mul(NMB_MIND_TABS[tab] || {});
    return out;
  },
  //: How long until the next pick, within the decided 20 to 60 seconds.
  nextIn: (now = Date.now(), roll = Math.random()) => {
    const idle = now - nmb.lastInput;
    let f = 0.3 + 0.35 * (1 - (nmb.mood?.energy ?? 0.6)) + 0.3 * (roll - 0.5);
    if (now - (nmb.keyAt || 0) < 8000) f += 0.25;
    if (now - (nmb.loudAt || 0) < 40000) f += 0.15;
    if (idle > 20000 && idle < 3 * 60 * 1000) f -= 0.3;
    return 20000 + 40000 * Math.max(0, Math.min(1, f));
  },
  //: Into a big act on a beat: true when it has taken the act on.
  lead(buddy, act) {
    if (!NMB_MIND_LEAD.includes(act) || nameMarkBuddyStill() || nameMarkIdleQuiet()) return false;
    const char = buddy.querySelector(".nm-buddy-char");
    if (!char || typeof char.animate !== "function") return false;
    if (act === "wave" && nmb.pointer) nameMarkBuddyAim(nmb.pointer);
    char.animate([{ translate: "0 0" }, { translate: "0 1.6px", offset: 0.6 }, { translate: "0 0" }], { duration: 300, easing: "ease-in-out", composite: "add" });
    clearTimeout(nmb.timer);
    nmb.timer = setTimeout(() => {
      nmb.timer = 0;
      if (!buddy.isConnected || nmb.act || nmb.flight || buddy.classList.contains("nm-buddy-dragging") || buddy.classList.contains("nmb-walking")) nameMarkBuddySchedule();
      else nameMarkBuddyAct(act);
    }, 220);
    return true;
  },
  //: An act it starts that has no CSS of its own: its limbs, its face.
  start(buddy, act, ms) {
    if (!NMB_MIND_ACTS[act] || nameMarkBuddyStill()) return;
    if (act === "ponder") {
      nameMarkBuddyLimbs(buddy, "ponder", ms);
      nameMarkBuddyTilt(Math.random() < 0.5 ? -0.45 : 0.45, ms - 500);
      const atlas = isAtlasSeed(buddy.dataset.seed || "");
      nameMarkBuddyExpress(atlas ? "thinking" : "confused", ms - 300, { drift: atlas });
    } else if (act === "sigh") {
      nameMarkBuddyLimbs(buddy, "sigh", ms);
      buddy.querySelector(".nm-buddy-char")?.animate?.([{ translate: "0 0" }, { translate: "0 -1.4px", offset: 0.35 }, { translate: "0 0.8px", offset: 0.7 }, { translate: "0 0" }], { duration: ms, easing: "ease-in-out", composite: "add" });
    }
  },
  //: Out of an act: a breath out after a big one, and what follows, if
  //: anything does and suits the moment ("" when nothing).
  after(buddy, act, roll = Math.random(), now = Date.now()) {
    if (nameMarkBuddyStill()) return "";
    if ((NMB_MIND_LEAD.includes(act) || NMB_LOUD_ACTS.includes(act)) && !nameMarkIdleQuiet()) {
      buddy.querySelector(".nm-buddy-char")?.animate?.([{ translate: "0 0" }, { translate: "0 -1px", offset: 0.3 }, { translate: "0 0.6px", offset: 0.7 }, { translate: "0 0" }], { duration: 600, easing: "ease-in-out", composite: "add" });
    }
    if (nmb.visit || buddy.classList.contains("nmb-sleep") || nameMarkBuddyActions() === "off") return "";
    let r = roll;
    for (const [next, chance] of NMB_MIND_NEXT[act] || []) {
      r -= chance;
      if (r >= 0) continue;
      const spec = NAME_MARK_BUDDY_ACTS[next];
      if (!spec || !spec.poses.includes(nmb.pose) || (nmb.cool[next] || 0) > now || nameMarkBuddyActOff(next)) return "";
      if (NMB_LOUD_ACTS.includes(next) && !nameMarkBuddyCalmAllows(now, nmb.loudAt || 0, nmb.loudGap || NMB_LOUD_GAP_MS, nmb.keyAt || 0, nameMarkBuddyScrollAgo())) return "";
      if (spec.atlas && !nmb.atlasLook) return "";
      return next;
    }
    return "";
  },
};
Object.assign(NAME_MARK_BUDDY_ACTS, NMB_MIND_ACTS);
Object.assign(NMB_LIMB_MOVES, {
  ponder: { arm: [[0.18, 16], [0.82, 16]] },
  sigh: { arm: [[0.3, -10], [0.5, -10], [0.8, 4]] },
});
nmb.mind = NMB_MIND;

//: Moved from avatars.js on 2026-10-18 for the boot budget: only the large
//: view above calls it.
//: **The companion, visiting its large view.** Its element moves from its
//: perch into `host` and back on `home()`; nothing about it is copied, so
//: nothing about it is lost. While it visits (`nmb.visit`) nothing moves it
//: (`nameMarkBuddyMoveTo`, the checks, its rides, errands and wanders all
//: stand down), it cannot be carried off or have its menu opened, and its
//: beat is the view's. A walk under way is finished first: the view shows
//: where it was going, not the path.
function nameMarkBuddyVisit(host) {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy || nmb.visit || buddy.classList.contains("nm-buddy-dragging")) return null;
  for (const anim of [nmb.anim, nmb.glideAnim]) if (anim && anim.playState === "running") anim.finish();
  clearTimeout(nmb.placeTimer);
  nmb.placeTimer = 0;
  //: The ledge under it shows for a sit; the CSS reads the host's
  //: own `data-pose`, a copy kept here (a `:has()` on the companion's made
  //: every pose change restyle 968 elements of the page).
  const mirror = () => { host.dataset.pose = buddy.dataset.pose || ""; };
  //: **A face visiting its large view keeps moving between its beats**
  //: (INBOX 600, the owner: "it might sway or do something for a couple
  //: seconds but will then snap still"). Its acts come every 2.5 to 6
  //: seconds and its breath is under a pixel, so between them it stood still
  //: for over a second (atlas600-still.js: 1,083ms with no part moving
  //: 0.75px). Its weight now shifts about its feet and it bobs, on two clocks
  //: that never line up (6.7s, 4.3s), so one is under way while the other
  //: turns; `rotate` and `translate` on the face's own box, which nothing
  //: else moves, so an act plays over them. Each starts half a swing in, at
  //: rest. Atlas too (INBOX 619): its layers' own loops are under a pixel
  //: for over a second at a time (atlas619-viewer.js: still 1,051 to
  //: 1,787ms in the view), so it floats on the same two clocks. Script, not
  //: the stylesheet (the boot CSS is at its budget); gone with the visit,
  //: and never under reduced motion or with the companion's actions off.
  const face = buddy.querySelector(":scope > .nm-buddy-face");
  const sway = [];
  if (face && typeof face.animate === "function" && !nameMarkIdleQuiet()) {
    const loop = (frames, ms) => face.animate(frames, { duration: ms, delay: -ms / 2, iterations: Infinity, direction: "alternate", easing: "ease-in-out" });
    sway.push(loop([{ rotate: "-2deg" }, { rotate: "2deg" }], 6700), loop([{ translate: "0 1.2px" }, { translate: "0 -1.4px" }], 4300));
  }
  const watch = new MutationObserver(mirror);
  nmb.visit = { home: buddy.parentNode, next: buddy.nextSibling, watch, sway, pose: nmb.pose, legs: nmb.legs, at: Date.now() };
  buddy.classList.remove("nmb-dodge");
  //: **Free of its perch in there** (INBOX 619, the owner: "in the enlarged
  //: preview atlas is still hanging, it should be slightly separate from the
  //: companion but still have the same life"). It came in holding the pose
  //: of its perch: hanging by its hands from the card's top edge, sitting on
  //: a drawn ledge, leaning on nothing. In the view it floats, clear of the
  //: card's edges, with its float's own loops and the view's beat; the
  //: perch's pose and legs go back with it (`nameMarkBuddyHome`). Asleep
  //: lying or curled, it stays so, and gets up into the float.
  if (nmb.pose !== "stand") {
    nmb.pose = "float";
    buddy.dataset.legs = nmb.legs = "";
    if (!/^(lie|curl)/.test(buddy.dataset.pose || "")) buddy.dataset.pose = "float";
  }
  host.appendChild(buddy);
  mirror();
  //: **In the view at rest** (the owner, 2026-10-11: "if it is hanging,
  //: the expanded companion kinda looks awkward with both it's arms up").
  //: The view is a cut, not a move: its limbs take the float's resting
  //: places at once (their transitions finished, Atlas's rig set in one
  //: frame) rather than lowering from the hang's raised arms while you look.
  if (nmb.visit.pose !== nmb.pose) {
    for (const el of buddy.querySelectorAll(".nmb-arm, .nmb-hold, .nmb-leg")) {
      getComputedStyle(el).transform;
      for (const anim of el.getAnimations?.() || []) if (anim instanceof CSSTransition) anim.finish();
    }
    const box = buddy.querySelector(".atl-figure-box");
    if (box?.atlasRig) {
      box.atlasRig.fresh = true;
      atlasRigWake(box);
    }
  }
  watch.observe(buddy, { attributes: true, attributeFilter: ["data-pose"] });
  //: Its own act keeps its own end; with none under way, the view's beat.
  if (!nmb.act) nameMarkBuddySchedule();
  return nameMarkBuddyHome;
}
function nameMarkBuddyHome() {
  const visit = nmb.visit;
  if (!visit) return;
  nmb.visit = null;
  visit.watch?.disconnect();
  for (const anim of visit.sway || []) anim.cancel();
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) return;
  //: Back to its perch's pose (the view floated it, `nameMarkBuddyVisit`).
  if (visit.pose && nmb.pose !== visit.pose) {
    nmb.pose = visit.pose;
    buddy.dataset.legs = nmb.legs = visit.legs || "";
    if (!/^(lie|curl)/.test(buddy.dataset.pose || "")) buddy.dataset.pose = visit.pose;
  }
  buddy.querySelector(":scope > .nm-say")?.remove();
  if (visit.home?.isConnected) visit.home.insertBefore(buddy, visit.next?.parentNode === visit.home ? visit.next : null);
  nameMarkBuddyRelease();
  if (!nmb.act) nameMarkBuddySchedule();
  queueNameMarkBuddyCheck();
}

//: ---- The way a far move is travelled (INBOX 1305, the owner: "companion
//: movement for both small and large distances needs a lot of improvement,
//: and reworking") ----
//:
//: Fetched with the companion's mind at its first tick. Until it is here a far move walks. `nameMarkBuddyGo` (avatars.js) asks
//: `companionPathPlan` for a move past `NMB_FAR_SIZES` of itself and plays
//: the frames it gets back, so the plan is pure: a distance in, a path out.
//:
//: **Never a teleport, never a diagonal glide through the page.** The old far
//: ways were a glide (a straight slide at up to 43px a frame), a walk, or past
//: 480px a poof, one frame of 1,000px. Now:
//:   run    on the level: a walk quickened to a run, its pace set by distance
//:   arc    to a higher place, or a short way down: a jump over a parabola
//:   drop   a long way down, not far across: it runs to the edge above the
//:          place, then falls
//: Every plan is sampled into straight pieces and its time is stretched until
//: the fastest piece is at most `COMPANION_PATH_PEAK` px a 60 Hz frame (the
//: teleport line is 40), so the longest move across a 1440px window takes
//: about 1.3s, and a 1000px one about a second.

const COMPANION_PATH_PEAK = 30;
const COMPANION_PATH_SAMPLES = 32;
const COMPANION_PATH_LEVEL = 36;
const COMPANION_PATH_DROP = 120;

//: Sine in and out: it sets off from rest, and its fastest moment is 1.57
//: times its mean (a cubic's is three).
function companionPathEase(t) {
  return (1 - Math.cos(Math.PI * t)) / 2;
}

//: Where on the way it is at `s` in [0, 1] of the time. `dx`, `dy` run from
//: where it goes back to where it was (the `translate` it starts at and
//: animates to 0); `kind` is run, arc or drop; `h` the arc's rise; `split` the
//: share of a drop's time spent running to the edge.
function companionPathAt(kind, dx, dy, h, split, s) {
  if (kind === "arc") {
    const e = companionPathEase(s);
    return [dx * (1 - e), dy * (1 - e) - h * 4 * s * (1 - s)];
  }
  if (kind === "drop") {
    if (s <= split) return [dx * (1 - companionPathEase(s / split)), dy];
    const f = (s - split) / (1 - split);
    return [0, dy * (1 - f * f)];
  }
  const e = companionPathEase(s);
  return [dx * (1 - e), dy * (1 - e)];
}

//: The kind of way for a move of `dx`, `dy` (back to where it was; dy > 0 is
//: a rise). A flyer never drops: it floats down.
function companionPathKind(dx, dy, flies) {
  if (Math.abs(dy) <= COMPANION_PATH_LEVEL) return "run";
  if (dy > 0 || flies || -dy < COMPANION_PATH_DROP || Math.abs(dx) > -dy * 1.2) return "arc";
  return "drop";
}

//: Longest piece of a sampled path, in px, over its pieces' share of the time.
function companionPathPeak(points, ms) {
  let worst = 0;
  for (let i = 1; i < points.length; i += 1) worst = Math.max(worst, Math.hypot(points[i][1] - points[i - 1][1], points[i][2] - points[i - 1][2]));
  return (worst * 1000) / 60 / (ms / (points.length - 1));
}

//: The plan: `{ kind, ms, frames, peak, beat, points }`. `frames` are the
//: keyframes for the host's `translate` (linear between samples), `beat` how
//: much quicker its legs go than a walk's, `peak` the fastest frame in px at
//: 60 Hz. Pure.
function companionPathPlan(dx, dy, size, flies = false) {
  const d = Math.hypot(dx, dy);
  const kind = companionPathKind(dx, dy, flies);
  const h = kind === "arc" ? Math.min(150, 24 + d * 0.1 + Math.max(0, dy) * 0.25) : 0;
  const fall = kind === "drop" ? 200 + Math.sqrt(-dy) * 34 : 0;
  const along = kind === "drop" ? 260 + Math.abs(dx) * 0.7 : 0;
  const base = kind === "drop" ? along + fall : 380 + d * 0.55;
  const split = kind === "drop" ? along / base : 0;
  const n = COMPANION_PATH_SAMPLES;
  const points = [];
  for (let i = 0; i <= n; i += 1) {
    const [x, y] = companionPathAt(kind, dx, dy, h, split, i / n);
    points.push([i / n, x, y]);
  }
  //: Stretched only as far as the fastest piece needs; never shortened.
  const ms = Math.round(Math.max(base, companionPathPeak(points, 1) / COMPANION_PATH_PEAK));
  return {
    kind,
    ms,
    peak: +companionPathPeak(points, ms).toFixed(1),
    beat: +Math.min(1.8, Math.max(1.1, 0.9 + d / ms)).toFixed(2),
    frames: points.map(([offset, x, y]) => ({ offset, translate: `${x.toFixed(1)}px ${y.toFixed(1)}px` })),
    points,
  };
}
