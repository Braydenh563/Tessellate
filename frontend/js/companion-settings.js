// companion-settings.js: what a person does to the companion on purpose, moved out
// of avatars.js on 2026-11-01 (audit AI23): the Settings controls (Your look,
// Your own character, what it does and how showy), Show or hide, Call back and
// the face repaint after a Look change. None of it is needed for the companion
// to appear, so it is the `companionSettings` bundle in lazy-entries.js: that
// bundle lists the characters first (`CHARACTER_DEPENDENTS`), and boot carries
// stand-ins for the names other files call (`installStandIns`), so a call
// before the file is in waits for it and then runs, in order. Not wrapped, like
// companion-menu.js: the tests that read the companion's code read it as one.

function nameMarkBuddyKeepCustom(custom) {
  nameMarkBuddyCustomReset();
  try {
    prefs.set("avatar-buddy-custom", JSON.stringify({ name: custom.name, style: custom.style }));
  } catch (e) {
    // Kept for this visit only.
  }
  const buddy = document.getElementById("nm-buddy");
  if (buddy) {
    delete buddy.dataset.seed;
    syncNameMarkBuddy();
  }
}

//: Every generated face on the page drawn again (a change of Face looks):
//: every size read first, then every face replaced, so it costs one layout.
function nameMarkRepaintAll() {
  const faces = [...document.querySelectorAll(".name-mark[data-nm-seed]:not(.nm-atlas)")].filter((el) => !el.closest("#nm-buddy"));
  const sizes = faces.map((el) => Math.round(el.getBoundingClientRect().width) || 20);
  faces.forEach((el, i) => el.replaceWith(nameMark(el.dataset.nmSeed, sizes[i])));
  repaintOwnFace();
}

const PROFILE_LOOK_WORDS = {
  hat: "wizard hat", chefhat: "chef's hat", partyhat: "party hat", flowercrown: "flower crown", tricorn: "pirate hat",
  squareglasses: "square glasses", threed: "3D glasses", starglasses: "star shades", heartglasses: "heart shades", visor: "cyber visor",
  thumbsup: "thumbs up", mug: "hot drink", fishingrod: "fishing rod", tableflip: "table flip",
  tee: "T-shirt", scoop: "scoop neck", collar: "shirt and tie", sweater: "jumper", uwu: "uwu",
  crop: "textured crop", sweep: "side-swept fringe", quiff: "soft quiff", messy: "tousled", curls: "short curls",
  wavy: "wavy, to the chin", long: "long and straight", waves: "long waves",
};

function repaintOwnFace() {
  if (typeof paintUserMarks === "function") paintUserMarks();
  const buddy = document.getElementById("nm-buddy");
  if (buddy) {
    delete buddy.dataset.seed;
    syncNameMarkBuddy();
  }
  if (typeof paintDashEmblem === "function") paintDashEmblem();
}

//: The part pickers, one select per part, for Your look and for your own
//: companion alike: `read` gives the style as it is, `write` keeps a
//: changed one.
function nameMarkLookPickers(host, prefix, autoLabel, read, write) {
  for (const [key, label, options] of PROFILE_LOOK_PARTS) {
    const row = document.createElement("label");
    row.className = "profile-look-part";
    const text = document.createElement("span");
    text.className = "muted";
    text.textContent = label;
    const select = document.createElement("select");
    select.className = "small-select";
    select.id = `${prefix}${key}`;
    select.dataset.part = key;
    const auto = new Option(autoLabel, "");
    const none = new Option("None", "none");
    //: A face always has a skin and its hair a colour: no "None" for those.
    select.append(auto);
    if (key !== "skin" && key !== "hairtone") select.append(none);
    for (const value of options()) {
      const word = PROFILE_LOOK_WORDS[value] || value.replace(/([a-z])([A-Z])/g, "$1 $2");
      select.append(new Option(word.charAt(0).toUpperCase() + word.slice(1), value));
    }
    if (key === "mood") none.textContent = "Plain";
    select.addEventListener("change", () => {
      const style = read();
      style[key] = select.value;
      write(style);
    });
    row.append(text, select);
    host.appendChild(row);
  }
}

//: Where to make it: your face in Profile, your character here in
//: Appearance under the companion's own row.
function nameMarkBuddyMakeIt(kind) {
  if (typeof openSettingsModal !== "function") return;
  if (kind === "me") openSettingsModal("preferences", "profile-look");
  else openSettingsModal("appearance", "avatar-buddy-custom");
}

//: The line under the companion's select: shown only while the choice is a
//: face you have not made.
function nameMarkBuddyMakeHint() {
  const hint = document.getElementById("avatar-buddy-make");
  if (!hint) return;
  const kind = typeof appearancePref === "function" ? appearancePref("avatar-buddy", "off") : "off";
  const show = (kind === "me" || kind === "custom") && !nameMarkBuddyMade(kind);
  hint.classList.toggle("hidden", !show);
  if (!show) return;
  document.getElementById("avatar-buddy-make-text").textContent = kind === "me"
    ? "It wears a face read from your name until you make your own."
    : "It wears a face read from its name until you give it one below.";
  const go = document.getElementById("avatar-buddy-make-go");
  go.textContent = kind === "me" ? "Create your avatar" : "Make your character";
  go.onclick = () => nameMarkBuddyMakeIt(kind);
}

function mountBuddyCustom() {
  nameMarkBuddyMakeHint();
  const box = document.getElementById("avatar-buddy-custom");
  if (!box) return;
  const on = (typeof appearancePref === "function" ? appearancePref("avatar-buddy", "off") : "off") === "custom";
  box.classList.toggle("hidden", !on);
  const host = document.getElementById("avatar-buddy-parts");
  const input = document.getElementById("avatar-buddy-name");
  if (host && !host.childElementCount) {
    nameMarkLookPickers(host, "avatar-buddy-look-", "From its name", () => ({ ...nameMarkBuddyCustom().style }), (style) => {
      nameMarkBuddyKeepCustom({ name: nameMarkBuddyCustom().name, style });
    });
    let typing = 0;
    input?.addEventListener("input", () => {
      clearTimeout(typing);
      typing = setTimeout(() => nameMarkBuddyKeepCustom({ name: input.value, style: nameMarkBuddyCustom().style }), 300);
    });
    document.getElementById("avatar-buddy-shuffle")?.addEventListener("click", () => {
      const custom = nameMarkBuddyCustom();
      nameMarkBuddyKeepCustom({ name: custom.name, style: { ...custom.style, variant: ((Number(custom.style.variant) || 0) + 1) % 10000 } });
    });
  }
  const custom = nameMarkBuddyCustom();
  if (input && document.activeElement !== input) input.value = custom.name;
  for (const [key] of PROFILE_LOOK_PARTS) {
    const select = document.getElementById(`avatar-buddy-look-${key}`);
    if (select) select.value = custom.style[key] || "";
  }
}

function mountProfileLook() {
  const host = document.getElementById("profile-look-parts");
  if (!host) return;
  if (!host.childElementCount) {
    nameMarkLookPickers(host, "profile-look-", "From your name", ownNameMarkStyle, (style) => {
      setOwnNameMarkStyle(style);
      repaintOwnFace();
      markPrefsDirty();
    });
    document.getElementById("profile-look-shuffle")?.addEventListener("click", () => {
      const style = ownNameMarkStyle();
      style.variant = ((Number(style.variant) || 0) + 1) % 10000;
      setOwnNameMarkStyle(style);
      repaintOwnFace();
      markPrefsDirty();
    });
    document.getElementById("profile-look-reset")?.addEventListener("click", () => {
      setOwnNameMarkStyle({});
      syncProfileLook();
      repaintOwnFace();
      markPrefsDirty();
    });
  }
  syncProfileLook();
}

function syncProfileLook() {
  const style = ownNameMarkStyle();
  for (const [key] of PROFILE_LOOK_PARTS) {
    const select = document.getElementById(`profile-look-${key}`);
    if (select) select.value = style[key] || "";
  }
}

function mountBuddyActivities() {
  mountBuddyShowy();
  const host = document.getElementById("avatar-buddy-activities");
  if (!host || host.childElementCount) return;
  const off = nameMarkBuddyActivitiesOff();
  for (const [key, label] of NMB_ACTIVITIES) {
    const row = document.createElement("label");
    row.className = "setting-check";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = !off.has(key);
    input.dataset.activity = key;
    const text = document.createElement("span");
    text.textContent = label;
    row.append(input, text);
    host.appendChild(row);
    if (key === "habits") mountBuddyActivities.help(host, row);
  }
  host.addEventListener("change", (event) => {
    const input = event.target.closest?.("input[data-activity]");
    if (!input) return;
    const now = nameMarkBuddyActivitiesOff();
    if (input.checked) now.delete(input.dataset.activity);
    else now.add(input.dataset.activity);
    try {
      prefs.set("avatar-buddy-acts-off", [...now].join(","));
    } catch (e) {
      // Kept for this visit only.
    }
    //: Turned off while it is doing it: it stops, the way it always does.
    if (nmb.act && nameMarkBuddyActOff(nmb.act, now)) nameMarkBuddyAct("");
    const buddy = document.getElementById("nm-buddy");
    if (buddy) nameMarkBuddyToggles(buddy);
  });
}

//: The habits row's '?' (INBOX 1581, standing order 13): the button in the
//: row, its popover after it (outside the label, so a click in the text
//: never flips the switch); built here, not in index.html, which is at its
//: element cap (tests/test_boot_diet3.py).
mountBuddyActivities.help = (host, row) => {
  const make = (tag, props = {}) => Object.assign(document.createElement(tag), props);
  const id = "avatar-buddy-habits-help";
  const name = "About little habits and reactions";
  const help = make("button", { type: "button", className: "icon-only ghost small graph-help-toggle", title: name });
  help.dataset.helpFor = id;
  help.setAttribute("aria-controls", id);
  help.setAttribute("aria-expanded", "false");
  help.setAttribute("aria-label", name);
  const mark = make("i", { className: "ph ph-question" });
  mark.setAttribute("aria-hidden", "true");
  help.append(mark);
  row.append(help);
  const body = make("div", { className: "help-body hidden", id });
  body.setAttribute("role", "dialog");
  body.setAttribute("aria-label", name);
  body.append(
    make("p", { textContent: "Small things it does now and then: a puzzled tilt when a search finds nothing and a nod when the next one does, a double take when the pointer rushes past, a shake after you carry it a while, a nod on the hour, a wave when you come back after ten minutes away, a shiver when the battery is low and a glance when the window is resized or goes fullscreen, a wince when a note goes to the bin. Atlas also looks around, hums, settles with a breath and takes a second look at the pointer." }),
    make("p", { textContent: "None of it happens while you type, while Motion is reduced, or over something else it is doing. Its moods also follow the part of the day: brighter in the morning, quieter in the evening." }),
  );
  row.after(body);
  initHelpToggles(host);
};

//: Companion > Showy entrances (INBOX 1463): off unless chosen.
function mountBuddyShowy() {
  const box = document.getElementById("avatar-buddy-showy");
  if (!box) return;
  box.checked = nameMarkBuddyShowy();
  if (box.dataset.wired) return;
  box.dataset.wired = "1";
  box.addEventListener("change", () => {
    try {
      prefs.set("avatar-buddy-entrances", box.checked ? "showy" : "quiet");
    } catch (e) {
      // Kept for this visit only.
    }
  });
}

//: **Out the same way, or dissolving** (INBOX 430): hidden from its menu or
//: by Ctrl+Shift+Y it dematerialises into starlight rather than vanishing.
function nameMarkBuddyLeave(buddy, then) {
  if (!buddy || typeof buddy.animate !== "function") {
    then();
    return;
  }
  //: Less motion is a fade, never a cut.
  if (nameMarkBuddyNoTravel()) {
    buddy.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 260, easing: "ease-in", fill: "forwards" });
    setTimeout(then, 280);
    return;
  }
  const char = buddy.querySelector(".nm-buddy-char");
  nmb.anim?.cancel();
  nameMarkBuddyBurst(buddy, 0, 0, 120);
  char?.animate([{ scale: "1", opacity: 1 }, { scale: "1.05", opacity: 1, offset: 0.25 }, { scale: "0.45", opacity: 0 }], { duration: 380, easing: "ease-in", fill: "forwards" });
  setTimeout(then, 400);
}

//: **Called back** (INBOX 426 k, the owner: "the companion just went off
//: the screen and I cant get it back now ... there needs to be some way to
//: reset the position and recall the companion"). From its menu, from
//: Appearance and from the command palette: every place you gave it is
//: forgotten and it comes to the tab's best perch, walking there when it
//: can be seen, arriving there when it could not. With no companion on, it
//: opens the setting that turns one on.
function nameMarkBuddyCallBack() {
  nmb.home = null;
  const buddy = document.getElementById("nm-buddy");
  if (!buddy) {
    if (typeof revealFeature === "function") revealFeature("set-companion");
    return;
  }
  nameMarkBuddyKeepSpots({});
  nmb.pinned = false;
  //: Hidden with its page, out for a while or on its way in: it is here now, whatever its mind had in hand (the asked-for button must always bring it).
  const wasAway = nmb.away || nmb.absent || !!nmb.afield;
  clearTimeout(nmb.appearTimer);
  nmb.appearTimer = 0;
  nmb.leaving = false;
  nmb.afield = null;
  nmb.owed = "";
  if (wasAway) {
    nmb.away = false;
    nmb.absent = false;
    buddy.classList.remove("nmb-away");
    nmb.lonely = 0;
    nmb.lonelyTouch(false);
    if (nameMarkBuddyAsleep(buddy)) nameMarkBuddyWake(true);
  }
  nmb.anim?.cancel();
  nmb.hopAnim?.cancel();
  buddy.style.translate = "";
  buddy.classList.remove("nm-buddy-dragging", "nmb-poofing", "nmb-walking");
  const box = buddy.getBoundingClientRect();
  const seen = !wasAway && !nmb.outOfSight && box.right > 0 && box.left < innerWidth && box.bottom > 0 && box.top < innerHeight;
  nameMarkBuddyIndexReset();
  placeNameMarkBuddy(buddy, !seen);
  //: Out of sight, it comes in the way it would to a tab (`nameMarkBuddyEnter`).
  if (!seen && nmb.spot) nmb.enteredBy = nameMarkBuddyEnter(buddy, nmb.spot);
  nameMarkSay(buddy, "Here I am.");
}

function nameMarkBuddyHide(buddy) {
  //: Hide removes the face, so a keyboard user's focus would fall to the page (Tab began again at "Skip to
  //: content"); it goes to the toast's way back instead. A mouse press leaves focus where it is.
  const kept = !!buddy && buddy.contains(document.activeElement);
  let was = null;
  try {
    //: Which companion it was, so the hotkey brings the same one back.
    was = prefs.get("avatar-buddy", null);
    if (was && was !== "off") prefs.set("nm-buddy-last", was);
    prefs.set("avatar-buddy", "off");
  } catch (e) {
    // Hidden for this session at least.
  }
  const select = document.getElementById("avatar-buddy");
  if (select) select.value = "off";
  nameMarkBuddyLeave(buddy, () => {
    dropAnimations(buddy);
    buddy?.remove();
    //: Every copy: a stray second mount left its glow and grip behind.
    for (const stray of document.querySelectorAll("#nm-buddy, .nmb-burst")) stray.remove();
    nameMarkBuddyGone();
  });
  //: The chord as it is bound now (it is rebindable), not as it shipped.
  const keys = typeof shortcuts === "object" ? shortcuts?.toggleCompanion?.keys : "";
  //: **The way back is a button, not a sentence** (INBOX 743, the owner:
  //: "the show companion notification button was poorly shown"). The toast
  //: named a chord and a Settings path in prose, with nothing to press; the
  //: toast-with-action recipe puts the one press beside its first line.
  const back = was && was !== "off" ? was : "me";
  toastAction(
    keys ? `Companion hidden. ${keys} brings it back too.` : "Companion hidden.",
    "Show it",
    () => {
      try {
        prefs.set("avatar-buddy", back);
      } catch (e) {
        // Back for this visit.
      }
      const choice = document.getElementById("avatar-buddy");
      if (choice) choice.value = back;
      syncNameMarkBuddy();
    },
    { record: false }
  );
  if (kept) document.querySelector("#toast-box .toast-action")?.focus();
}

//: **Show or hide it from anywhere** (INBOX 430, the owner: "a show/hide
//: companion hotkey, and palette action"): Ctrl+Shift+Y (`toggleCompanion`
//: in the shortcut registry), the command palette and Find anything, whose
//: row says which it will do (`nameMarkBuddyShowing`). Hidden, it comes back
//: as whichever companion it was (`nm-buddy-last`), or Atlas.
function nameMarkBuddyToggle() {
  if (nameMarkBuddyShowing()) {
    nameMarkBuddyHide(document.getElementById("nm-buddy"));
    return;
  }
  let back = "atlas";
  try {
    back = prefs.get("nm-buddy-last", null) || "atlas";
    prefs.set("avatar-buddy", back);
  } catch (e) {
    // Shown for this session at least.
  }
  //: The same steps as the Appearance select's change, run here: that
  //: listener is wired only when Settings first opens (settings-controls.js),
  //: and the select can exist before then (built for the palette's labels).
  const select = document.getElementById("avatar-buddy");
  if (select) select.value = back;
  mountBuddyCustom();
  syncNameMarkBuddy();
  if (select) nameMarkBuddySizeSelect();
}
