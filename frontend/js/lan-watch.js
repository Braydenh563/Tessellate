// Other devices, as this computer's window hears of them (INBOX 867, 896).
//
// The owner: "Just make sure everything is handled for the user
// automatically". A phone that signs in for the first time is held until
// someone here says yes (core/lantrust.py), and a network nobody allowed
// keeps the LAN port closed; both reach this window as a toast and a row in
// the bell. Loaded by `startReminderWatch` (status.js) once per page.
//
// One request at a time, held open by the server (`GET /auth/lan-watch`)
// until something changes or 25 s pass, so a notice arrives at once and an
// idle minute costs two requests. It runs while LAN mode is off too, since
// the switch applies while the app runs (INBOX 900) and the status bar's
// icon says which it is; it stops for good only on another device (403),
// where only this computer answers and the icon never shows.

const lanWatchState = { running: false, seen: new Set(), heldKey: "", offKey: "", version: -1 };

//: Through `api()` like every request (tests/test_no_bare_fetch.py), silent
//: so a 401 here never draws the lock screen: a locked session answers
//: "locked", any other refusal (403 on another device) "stop", and a network
//: failure throws to `lanWatch`, which waits and asks again.
async function lanWatchOnce() {
  let response;
  try {
    response = await api(`/auth/lan-watch?since=${lanWatchState.version}`, {
      silent: true,
      signal: AbortSignal.timeout(40000),
    });
  } catch (error) {
    if (error?.isLockout || error?.status === 401) return "locked";
    if (error?.status === 403) return "stop";
    if (error?.status) return "wait";
    throw error;
  }
  const state = await response.json();
  const changed = state.version !== lanWatchState.version;
  lanWatchState.version = state.version;
  lanPaintIcon(lanLookFromWatch(state));
  lanNoticeSwitchedOff(state.switched_off);
  if (changed) lanRefreshOpenPanel();
  if (!state.serving) {
    lanWatchState.heldKey = "";
    return "again";
  }
  for (const device of state.pending || []) lanNoticeDevice(device);
  lanNoticeHeld(state.held);
  return "again";
}

async function lanWatch() {
  if (lanWatchState.running) return;
  lanWatchState.running = true;
  try {
    for (;;) {
      //: A hidden window asks nothing (battery): it asks again when shown.
      while (document.hidden) await new Promise((wake) => document.addEventListener("visibilitychange", wake, { once: true }));
      let next = "again";
      try {
        next = await lanWatchOnce();
      } catch {
        next = "wait"; // the server restarting, or asleep: try again shortly
      }
      if (next === "stop") return;
      //: Locked: ask again in a minute rather than drawing the lock screen
      //: from here; an unlock does not restart this loop, so it keeps going.
      if (next !== "again") await new Promise((done) => setTimeout(done, next === "locked" ? 60000 : 10000));
    }
  } finally {
    lanWatchState.running = false;
  }
}

async function lanAnswerDevice(device, verdict) {
  try {
    await apiJson(`/auth/lan-devices/${encodeURIComponent(device.id)}/${verdict}`, { method: "POST" });
    toast(verdict === "allow" ? `${device.name} can sign in now.` : `${device.name} was not let in.`);
    renderLanAccess();
  } catch (error) {
    toast(error.message || "That device is no longer waiting.", "info");
  }
}

function lanNoticeDevice(device) {
  if (lanWatchState.seen.has(device.id)) return;
  lanWatchState.seen.add(device.id);
  const title = `${device.name} at ${device.address} wants to open this notebook`;
  toastAction(title, "Allow", () => lanAnswerDevice(device, "allow"), {
    sticky: true,
    record: false,
    also: { label: "Deny", run: () => lanAnswerDevice(device, "deny") },
  });
  recordNotification({
    kind: "info",
    title,
    detail: "It gave the right password. Allow it here, or in Settings, Account & security, Other devices.",
    key: `lan-device:${device.id}:${Math.round(device.at)}`,
    action: { settings: "account", focus: "account-lan-pending", label: "Review" },
  });
}

const LAN_HELD_WORDS = {
  new_network: "this network is not one you trusted",
  unknown_network: "this network could not be identified",
  public_network: "Windows calls this network public",
  untrusted_network: "you stopped trusting this network",
  no_network: "this computer is not on a network",
};
//: Said by the icon only: the person chose the first, and a dropped wifi
//: or a phone's hotspot going away is not something to answer.
const LAN_QUIET_REASONS = new Set(["untrusted_network", "no_network"]);

function lanNoticeHeld(held) {
  const key = held ? `${held.reason}:${held.network?.key || ""}` : "";
  if (key === lanWatchState.heldKey) return;
  lanWatchState.heldKey = key;
  if (!held || LAN_QUIET_REASONS.has(held.reason)) return;
  const where = held.network?.label || "this network";
  const title = `Other devices can't open this notebook on ${where}`;
  toastAction(title, "Review", () => lanOpenPanel(), { record: false, ms: 12000 });
  recordNotification({
    kind: "info",
    title,
    detail: `Kept closed because ${LAN_HELD_WORDS[held.reason] || "this network is not allowed"}. The wifi icon in the status bar, or Settings, Account & security, Other devices, can trust it.`,
    key: `lan-held:${key}`,
    action: { settings: "account", focus: "account-allow-lan", label: "Review" },
  });
}

//: **The 14-day rule, said on this computer** (secscan-1011): LAN mode left
//: on and unused switches itself off (lanlive.switch_off_if_unused), and the
//: person learns it here once, in a toast and the bell, until they say OK.
function lanNoticeSwitchedOff(date) {
  if (!date || lanWatchState.offKey === date) return;
  lanWatchState.offKey = date;
  const title = `Other devices were turned off on ${date}`;
  toastAction(title, "Review", () => lanOpenPanel(), {
    sticky: true,
    record: false,
    also: { label: "OK", run: () => lanDismissSwitchedOff() },
  });
  recordNotification({
    kind: "info",
    title,
    detail: "No other device opened the app for 14 days, so it closed itself. Turn it on again from the wifi icon in the status bar.",
    key: `lan-off:${date}`,
    action: { settings: "account", focus: "account-allow-lan", label: "Review" },
  });
}

async function lanDismissSwitchedOff() {
  try {
    return await apiJson("/auth/lan-notice/dismiss", { method: "POST" });
  } catch (error) {
    toast(error.message, true);
    return null;
  }
}

// ---- the status bar's icon and its panel (INBOX 896) ----------------------
// The owner: "a lan icon in the bottom status bar ... whether it is open or
// closed or off", with "a popup" to turn it on or off, see the address and
// manage the networks it trusts. The icon is painted from the watch above,
// so a dropped wifi or an untrusted network reaches it within the watch's
// beat; the panel is a help popover (`wireHelpPopover`), and a sheet when
// the bar has no box to anchor to (a phone, or the slot switched off).

//: One look, from either answer: the watch's or `/auth/lan-access`'s.
function lanLook({ allow, listening, held, label, error, live, switchedOff }) {
  const where = label || "this network";
  if (!allow) {
    return {
      name: "off",
      glyph: "wifi-slash",
      words: switchedOff ? `Off since ${switchedOff}: unused for 14 days.` : "Off. Only this computer can open the app.",
    };
  }
  if (!listening) {
    if (live && error === "port_taken") return { name: "closed", glyph: "wifi-x", words: "On, but another program holds its port." };
    if (live) return { name: "closed", glyph: "wifi-x", words: "On, and opening now." };
    return { name: "restart", glyph: "arrow-clockwise", words: "On after the app restarts." };
  }
  if (held) return { name: "closed", glyph: "wifi-x", words: `Closed on ${where}: ${LAN_HELD_WORDS[held] || "it is not trusted"}.` };
  return { name: "open", glyph: "wifi-high", words: `Open on ${where}. Other devices need your password.` };
}

function lanLookFromWatch(state) {
  return lanLook({
    allow: state.allow_lan,
    listening: state.serving,
    held: state.held?.reason || "",
    label: state.network,
    error: state.error,
    live: state.live,
    switchedOff: state.switched_off,
  });
}

function lanLookFromState(state) {
  return lanLook({
    allow: state.allow_lan,
    listening: Boolean(state.network),
    held: state.held || "",
    label: state.network?.network?.label,
    live: state.live,
    switchedOff: state.switched_off,
  });
}

function lanPaintIcon(look) {
  const button = $("status-lan");
  if (!button) return;
  lazyScript("/css/lan-lazy.css");
  button.dataset.lanState = look.name;
  const glyph = button.querySelector(".ph");
  if (glyph) glyph.className = `ph ph-${look.glyph}`;
  button.setAttribute("aria-label", `Other devices: ${look.name === "restart" ? "restart needed" : look.name}`);
  button.title = shortcutTitle(`Other devices. ${look.words}`, "lanPanel");
  if (button.classList.contains("hidden")) {
    button.classList.remove("hidden");
    lanWirePanel();
  }
}

function lanWirePanel() {
  const button = $("status-lan");
  const panel = $("lan-popover");
  if (!button || !panel || button.dataset.lanWired) return;
  button.dataset.lanWired = "1";
  //: Captured, so it runs before the popover's own listener: a button with
  //: no box (below 600 the bar is not on screen and `PHONE_STATUS_ROWS`
  //: presses it; or its slot is switched off) opens the sheet instead.
  button.addEventListener(
    "click",
    (event) => {
      if (button.getBoundingClientRect().width) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      lanOpenSheet();
    },
    true
  );
  wireHelpPopover(button, panel);
  button.addEventListener("click", () => {
    if (button.getAttribute("aria-expanded") === "true") lanFillPanel(panel, () => placeHelpPopover(panel, button));
  });
}

function lanOpenSheet() {
  openSheet({
    label: "Other devices",
    name: "lan",
    build: (card) => {
      const body = document.createElement("div");
      body.className = "lan-panel";
      card.appendChild(body);
      lanFillPanel(body);
    },
  });
}

//: The shortcut (`lanPanel`, Alt+L) and the notices' Review: the bar's own
//: button, so the popover, the sheet and the refusal stay in one place.
function lanOpenPanel() {
  if (typeof onOtherDevice === "function" && onOtherDevice()) {
    toast(THIS_COMPUTER_ONLY, "info");
    return;
  }
  const button = $("status-lan");
  if (!button) return;
  lanWirePanel();
  button.click();
}

function lanRefreshOpenPanel() {
  const panel = $("lan-popover");
  const button = $("status-lan");
  if (panel && button && !panel.classList.contains("hidden")) lanFillPanel(panel, () => placeHelpPopover(panel, button));
  const sheet = document.querySelector('[data-sheet="lan"] .lan-panel');
  if (sheet) lanFillPanel(sheet);
}

async function lanFillPanel(holder, after) {
  if (!holder.childElementCount) {
    holder.replaceChildren(lanPanelLine("ph:spin Checking", "muted"));
    after?.();
  }
  //: The address block, the network rows and the switch are Settings' own
  //: (settings-controls.js), so the two surfaces cannot say it two ways.
  const ready = await ensureModule("settingsControls");
  let state = null;
  try {
    state = ready ? await apiJson("/auth/lan-access", { silent: true }) : null;
  } catch (error) {
    holder.replaceChildren(lanPanelLine(`ph:warning ${error.message || "Could not read the network settings."}`, "muted"));
    after?.();
    return;
  }
  if (!state) return;
  const paint = (next) => {
    lanDrawPanel(holder, next, paint);
    lanPaintIcon(lanLookFromState(next));
    if (typeof renderLanState === "function") renderLanState(next);
    after?.();
  };
  paint(state);
}

function lanPanelLine(label, className = "") {
  const line = document.createElement("p");
  line.className = `lan-panel-line ${className}`.trim();
  setLabel(line, label);
  return line;
}

function lanPanelHeading(words) {
  const heading = document.createElement("h4");
  heading.className = "setting-subhead";
  heading.textContent = words;
  return heading;
}

function lanDrawPanel(holder, state, paint) {
  const look = lanLookFromState(state);
  const head = document.createElement("div");
  head.className = "lan-panel-head";
  head.dataset.lanState = look.name;
  //: A sheet's own head already says it (`openSheet`'s title).
  if (!holder.closest(".sheet-card")) {
    const title = document.createElement("strong");
    title.textContent = "Other devices";
    head.appendChild(title);
  }
  head.appendChild(lanPanelLine(`ph:${look.glyph} ${look.words}`));
  const parts = [head];

  if (!state.allow_lan && state.switched_off) {
    const dismiss = smallButton("OK", "OK, put this notice away", async () => {
      const next = await lanDismissSwitchedOff();
      if (next) paint(next);
    });
    const notice = document.createElement("div");
    notice.className = "notice lan-panel-notice";
    notice.append(lanPanelLine(`ph:clock-countdown No other device opened the app for ${state.unused_days || 14} days, so it turned itself off.`), dismiss);
    parts.push(notice);
  }

  const addresses = document.createElement("div");
  addresses.className = "lan-addresses hidden";
  addresses.id = holder.id ? `${holder.id}-addresses` : "lan-sheet-addresses";
  renderLanAddresses(addresses, state.other_devices ? state : { addresses: [] });
  parts.push(addresses);

  const actions = document.createElement("div");
  actions.className = "row button-row lan-panel-actions";
  const toggle = smallButton(
    state.allow_lan ? "ph:wifi-slash Turn off" : "ph:wifi-high Turn on",
    state.allow_lan ? "Turn off: close the app to other devices now and sign them out" : "Turn on: let devices on this network open the app; asks for your password",
    async () => {
      const next = await lanSwitch(!state.allow_lan);
      if (next) paint(next);
    },
    false
  );
  actions.appendChild(toggle);
  const here = state.current_network || "";
  const trusted = (state.networks || []).some((network) => network.key === here);
  if (state.allow_lan && state.held && !trusted && state.held !== "no_network") {
    const listed = (state.untrusted || []).find((network) => network.key === here);
    actions.appendChild(
      smallButton("ph:shield-check Trust this network", "Trust this network: let other devices in here; asks for your password", () =>
        listed ? lanTrustNetwork(listed, paint) : lanAllowHere(paint)
      )
    );
  }
  actions.appendChild(
    smallButton("ph:gear Settings", "Settings: devices, the certificate and the rest", () => {
      closeHelpPopovers();
      document.querySelector('[data-sheet="lan"] .sheet-close')?.click();
      openSettingsModal("account", "account-allow-lan");
    })
  );
  parts.push(actions);

  const rows = lanNetworkRows(state, paint);
  const trustedList = document.createElement("ul");
  trustedList.className = "entry-list";
  trustedList.append(...(rows.trusted.length ? rows.trusted : [lanEmptyRow(state.allow_lan ? "None. Trust this network to let other devices in here." : "None yet. Turning this on trusts the network you are on.")]));
  parts.push(lanPanelHeading("Trusted networks"), trustedList);
  if (rows.untrusted.length) {
    const untrustedList = document.createElement("ul");
    untrustedList.className = "entry-list";
    untrustedList.append(...rows.untrusted);
    parts.push(lanPanelHeading("Untrusted networks"), untrustedList);
  }
  holder.replaceChildren(...parts);
}

lanWatch();
