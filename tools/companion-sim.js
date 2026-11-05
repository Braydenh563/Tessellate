// The companion simulator's script (tools/companion-sim.html explains it).
//: The app's globals the companion reaches for, answered here.
const SIM = { seed: "Atlas", trace: true, points: [] };
function userMarkSeed() { return "You"; }
function aiNameNow() { return "Atlas"; }
function currentAccentHex() { return "#6d5dfc"; }
function appearancePref(key, fallback) {
  if (key === "avatar-buddy") return SIM.seed === "Atlas" ? "persona" : "custom";
  if (key === "avatar-motion") return "always";
  if (key === "face-look") return "mixed";
  if (key === "atlas-style") return "character";
  return fallback;
}
function paintDashEmblem() {}
function repaintOwnFace() {}
function switchTab() {}
function nameMarkBuddyCustom() { return { name: SIM.seed, style: {} }; }
//: The companion's menu is the app's (app.js, `openMenuAtPoint`), which is
//: not loaded here; this stand-in lists the same items at the same point
//: so they can be run. Where the real menu lands is app.js's business.
function openMenuAtPoint(items, x, y) {
  document.querySelector(".sim-menu")?.remove();
  const menu = document.createElement("ul");
  menu.className = "sim-menu action-menu";
  //: Kept on screen: the point may be in page coordinates.
  menu.style.left = `${Math.round(Math.min(Math.max(0, x), innerWidth - 220))}px`;
  menu.style.top = `${Math.round(Math.min(Math.max(0, y - scrollY), innerHeight - 160))}px`;
  for (const item of items || []) {
    if (!item || !item.label) continue;
    const li = document.createElement("li");
    li.textContent = String(item.label).replace(/^ph:\S+\s*/, "");
    li.onclick = () => { menu.remove(); if (typeof item.run === "function") item.run(); };
    menu.append(li);
  }
  document.body.append(menu);
  setTimeout(() => document.addEventListener("click", () => menu.remove(), { once: true }), 0);
}
function openNameMarkViewer() {}
function nameMarkBuddyKeepCustom() {}
const prefsCache = { dashboard_persona: "Atlas" };
//: The app's tab list: the companion reads the visible `#tab-<name>` page
//: for its surfaces, and without a list it sees no page at all.
const TABS = ["notes"];

const ROOT = location.protocol === "file:" ? "../frontend/" : "/";
(function load() {
  const css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = `${ROOT}css/08-consistency.css`;
  document.head.appendChild(css);
  const script = (src) => new Promise((ok, no) => {
    const el = document.createElement("script");
    el.src = ROOT + src;
    el.onload = ok;
    el.onerror = () => no(new Error(`could not load ${src}`));
    document.head.appendChild(el);
  });
  script("js/prefs.js").then(() => script("js/avatars.js")).then(() => script("js/atlas.js")).then(() => ensureModule("atlasMotion")).then(boot).catch((e) => { document.getElementById("status").textContent = e.message; });
})();

function boot() {
  const $ = (id) => document.getElementById(id);
  const words = ["Notes", "Timeline", "Reminders", "Documents", "Graph", "Board", "Library", "Chat", "Search", "Settings", "Insights", "Review"];
  //: The mock page: a dozen cards of uneven heights, a couple wide.
  function panels(seed) {
    const host = $("panels");
    host.replaceChildren();
    let r = seed;
    const rand = () => { r = (r * 1103515245 + 12345) % 2147483648; return r / 2147483648; };
    for (let i = 0; i < 14; i += 1) {
      const c = document.createElement("section");
      c.className = `card${rand() < 0.2 ? " wide" : ""}`;
      c.style.setProperty("--h", `${100 + Math.round(rand() * 220)}px`);
      const h = document.createElement("h3");
      h.textContent = `${words[i % words.length]} ${i + 1}`;
      const p = document.createElement("p");
      p.textContent = "A panel the companion can perch on, hang from or peek past. Move the panels to see it keep its place on the surface it chose.";
      c.append(h, p);
      host.append(c);
    }
  }
  panels(7);
  //: The trace: the companion's centre each frame, a fading line.
  const canvas = $("trace-canvas");
  const ctx = canvas.getContext("2d");
  const fit = () => { canvas.width = innerWidth * devicePixelRatio; canvas.height = innerHeight * devicePixelRatio; };
  fit();
  addEventListener("resize", fit);
  let last = null;
  function tick() {
    const buddy = document.getElementById("nm-buddy");
    if (buddy) {
      const box = buddy.getBoundingClientRect();
      const p = { x: box.left + box.width / 2, y: box.top + box.height / 2, t: performance.now() };
      if (!last || Math.hypot(p.x - last.x, p.y - last.y) > 0.5) {
        if (SIM.trace) SIM.points.push(p);
        last = p;
      }
      $("where").textContent = `${Math.round(box.left)},${Math.round(box.top)} · ${buddy.dataset.pose || ""}${buddy.dataset.legs ? " " + buddy.dataset.legs : ""} · ${[...buddy.classList].filter((c) => c.startsWith("nmb-")).join(" ")}`;
    }
    const cut = performance.now() - 12000;
    SIM.points = SIM.points.filter((q) => q.t > cut);
    ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    ctx.lineWidth = 2;
    for (let i = 1; i < SIM.points.length; i += 1) {
      const a = SIM.points[i - 1];
      const b = SIM.points[i];
      ctx.strokeStyle = `rgba(109, 93, 252, ${0.15 + 0.85 * ((b.t - cut) / 12000)})`;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
  //: The controls.
  $("scroll").onclick = () => {
    const target = scrollY < document.body.scrollHeight / 2 ? document.body.scrollHeight : 0;
    const start = scrollY;
    const t0 = performance.now();
    const go = () => {
      const k = Math.min(1, (performance.now() - t0) / 700);
      scrollTo(0, start + (target - start) * k);
      if (k < 1) requestAnimationFrame(go);
    };
    go();
  };
  $("shuffle").onclick = () => { panels(Math.floor(Math.random() * 1000)); travel(); };
  //: A trip: the companion's own placement, as a page change would ask.
  function travel() {
    try {
      if (typeof placeNameMarkBuddy === "function") placeNameMarkBuddy(undefined, false);
    } catch (e) {
      $("status").textContent = `travel failed: ${e.message}`;
    }
  }
  $("travel").onclick = travel;
  //: A beat: the companion's own behaviour runner, which decides a trip, a
  //: stretch, a glance or nothing, as its timer would every 20 to 60
  //: seconds; "Auto beats" calls it every 5 seconds so a trip comes soon.
  function beat() {
    try {
      nmb.lastInput = Date.now();
      if (typeof nameMarkBuddyTick === "function") nameMarkBuddyTick();
    } catch (e) {
      $("status").textContent = `beat failed: ${e.message}`;
    }
  }
  $("beat").onclick = beat;
  //: A trip: the companion's own placement, asked to look near a panel
  //: chosen at random, as a page change would ask it to look near where
  //: it was; it walks there on the compositor, legs stepping.
  function trip() {
    const cards = [...document.querySelectorAll(".sim-grid .card")].filter((c) => { const r = c.getBoundingClientRect(); return r.bottom > 60 && r.top < innerHeight - 60; });
    const card = cards[Math.floor(Math.random() * cards.length)];
    if (!card || typeof placeNameMarkBuddy !== "function") return;
    const r = card.getBoundingClientRect();
    try {
      nmb.spot = null;
      placeNameMarkBuddy(undefined, false, [r.left + r.width / 2, r.top + r.height / 2]);
    } catch (e) {
      $("status").textContent = `trip failed: ${e.message}`;
    }
  }
  $("trip").onclick = trip;
  let auto = 0;
  let beats = 0;
  $("auto").onclick = () => {
    if (auto) {
      clearInterval(auto);
      auto = 0;
    } else {
      trip();
      auto = setInterval(() => { beats += 1; if (beats % 2) beat(); else trip(); }, 5000);
    }
    $("auto").textContent = `Auto beats: ${auto ? "on" : "off"}`;
    $("auto").classList.toggle("on", !!auto);
  };
  $("menu").onclick = () => {
    const buddy = document.getElementById("nm-buddy");
    if (!buddy) return;
    const box = buddy.getBoundingClientRect();
    const face = buddy.querySelector(".nm-buddy-face") || buddy;
    face.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: box.left + box.width / 2, clientY: box.top + box.height / 2, button: 2 }));
  };
  $("trace").onclick = () => {
    SIM.trace = !SIM.trace;
    $("trace").textContent = `Trace: ${SIM.trace ? "on" : "off"}`;
    $("trace").classList.toggle("on", SIM.trace);
  };
  $("wipe").onclick = () => { SIM.points = []; };
  $("seed").addEventListener("change", () => {
    SIM.seed = $("seed").value.trim() || "Atlas";
    const old = document.getElementById("nm-buddy");
    if (old) old.remove();
    start();
  });
  //: The real companion, on this page.
  function start() {
    try {
      syncNameMarkBuddy();
      $("status").textContent = document.getElementById("nm-buddy") ? "companion live" : "companion did not appear";
    } catch (e) {
      $("status").textContent = `companion failed: ${e.message}`;
      console.error(e);
    }
  }
  start();
}
