// The avatar lab's script (tools/avatar-lab.html explains the bench).
//: The app's globals the renderers reach for, answered here.
//: The CSS box: a constructed stylesheet, which the app's CSP allows where
//: an inline <style> is refused.
const USER_SHEET = new CSSStyleSheet();
document.adoptedStyleSheets = [...document.adoptedStyleSheets, USER_SHEET];
let userCssText = "";
function userCss(text) {
  if (text === undefined) return userCssText;
  userCssText = String(text || "");
  try {
    USER_SHEET.replaceSync(userCssText);
  } catch (e) {
    /* a half-typed rule; the last good sheet stays */
  }
  return userCssText;
}
const LAB = { look: "masculine", style: "character", mood: "calm", seed: "Brayden", own: {}, ground: "dark", motion: false, live: false, css: "", notes: "", snaps: {} };
function userMarkSeed() { return LAB.seed; }
function aiNameNow() { return "Atlas"; }
function currentAccentHex() { return "#6d5dfc"; }
function appearancePref(key, fallback) {
  if (key === "atlas-look") return LAB.look;
  if (key === "atlas-style") return LAB.style;
  if (key === "face-look") return "mixed";
  if (key === "avatar-buddy") return "persona";
  return fallback;
}
function nameMarkBuddyCue() { }
function nameMarkBuddyAct() { }
function syncNameMarkBuddy() { }
function paintDashEmblem() { }
function repaintOwnFace() { }
//: Served by the app, the renderers are at "/"; opened as a file, they are
//: beside this folder.
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
  script("js/prefs.js").then(() => script("js/avatars.js")).then(() => {
    //: The product decomposes each SVG into raster layers for animated chat
    //: surfaces; the lab wants the geometry itself.
    window.nameMarkCompose = function (key, build, opts = {}) {
      const svg = build();
      const size = opts.size || 20;
      svg.setAttribute("width", size);
      svg.setAttribute("height", opts.height || size);
      svg.dataset.nmSize = String(size);
      svg.dataset.nmKb = "1";
      svg.classList.add("name-mark");
      return svg;
    };
    window.watchNameMark = function (svg) { if (svg) svg.dataset.nmKb = "1"; };
    //: atlas-motion.js holds the blink and arm rig and companion-settings.js the
    //: look pickers since they left atlas.js and avatars.js; the app loads them
    //: lazily, the lab needs them up front.
    return script("js/atlas.js").then(() => ensureModule("atlasMotion")).then(() => script("js/companion-settings.js"));
  }).then(() => {
    //: Atlas reads its look from the app's storage first; the lab's choice
    //: must win without touching that storage.
    window.atlasLook = () => LAB.look;
    //: **What you pick stays picked** (the owner: "on the avatar lab, it
    //: keeps reverting my selected motion and goes to sleep standing with a
    //: night cap"). atlas.js's own life (sleepy after ten idle minutes or
    //: before 5am, a start at a click while sleepy, a poke's reaction) set
    //: every Atlas on the page, the lab's specimens too. With Live behaviour
    //: off (the default) none of it reaches them.
    const liveMood = window.setAtlasMood;
    window.setAtlasMood = (...args) => (LAB.live ? liveMood(...args) : undefined);
    boot();
  }).catch((e) => { document.getElementById("status").textContent = e.message; });
})();

function boot() {
  const $ = (id) => document.getElementById(id);
  const K = "avatar-lab:";
  const MOODS = Object.keys(ATLAS_MOODS);
  const POSES = [
    ["stand", "stand", []], ["sit", "sit", []], ["hang", "hang", []], ["float", "float", []], ["lean", "lean", []],
    ["settling", "lie-1", []], ["half down", "lie-2", []], ["lying", "lie", ["nmb-sleep"]], ["curling", "curl-1", []], ["curled", "curl", []],
    ["sleep", "sit", ["nmb-sleep"]], ["drowsy", "stand", ["nmb-music", "nmb-drowsy"]], ["night", "sit", ["nmb-night"]], ["reading", "stand", ["nmb-reading", "nmb-think"]],
    ["cheer", "stand", ["nmb-act-cheer"]], ["startle", "stand", ["nmb-act-startle"]], ["wake", "stand", ["nmb-act-wake"]], ["lantern", "stand", ["nmb-act-lantern"]],
    ["bell", "stand", ["nmb-act-bell"]], ["wave", "stand", ["nmb-act-wave"]], ["peek", "stand", ["nmb-act-peek"]], ["offline", "stand", ["nmb-offline"]],
    ["meditate", "float", ["nmb-act-meditate"]], ["juggling", "stand", ["nmb-act-juggle"]], ["starry map", "stand", ["nmb-act-map"]], ["carry", "stand", ["nmb-act-carry"]],
  ];
  const KNOBS = [
    ["bodyWidth", "Body width", 0.7, 1.5, 0.01], ["headSize", "Head size", 0.8, 1.3, 0.01], ["tailLength", "Tail length", 0.5, 1.7, 0.01],
    ["tailCurl", "Tail curl", -70, 70, 1], ["strandOpacity", "Strand", 0, 1, 0.01], ["starSize", "Star size", 0.6, 1.8, 0.01], ["lockCount", "Hair locks", 0, 6, 1],
  ];
  const COLOURS = [["hi", "highlight"], ["lt", "light"], ["md", "mid"], ["dp", "deep"], ["navy", "navy"], ["glow", "glow"]];
  const SEEDS = ["Brayden", "Alice", "Charlie", "Luna", "Max", "Zoe", "Kai", "Nova", "Sage", "Finn", "panda", "fox", "wizardMage", "pirateKing", "A", "???", "Atlas"];
  const cards = [];
  let token = 0;
  const say = (text) => {
    const t = $("toast");
    t.textContent = text;
    t.classList.add("on");
    clearTimeout(t.timer);
    t.timer = setTimeout(() => t.classList.remove("on"), 1500);
  };
  const tuneNow = () => atlasTune();
  const store = () => {
    try {
      localStorage.setItem(`${K}state`, JSON.stringify({ ...LAB, tune: window.ATLAS_TUNE || {} }));
    } catch (e) { /* a private window keeps nothing */ }
  };
  const observer = new IntersectionObserver((entries) => {
    for (const e of entries) e.target.classList.toggle("off", !e.isIntersecting);
  }, { rootMargin: "120px" });

  //: A card: a title, a close, and a builder the tune re-runs.
  function card(title, sub, build) {
    const c = document.createElement("section");
    c.className = "card";
    const head = document.createElement("div");
    head.className = "head";
    const strong = document.createElement("strong");
    strong.textContent = title;
    const subEl = document.createElement("span");
    subEl.className = "sub";
    subEl.textContent = sub || "";
    const close = document.createElement("button");
    close.className = "close";
    close.textContent = "×";
    close.onclick = () => {
      c.remove();
      const i = cards.indexOf(entry);
      if (i >= 0) cards.splice(i, 1);
    };
    head.append(strong, subEl, close);
    const body = document.createElement("div");
    c.append(head, body);
    $("canvas").querySelector(".empty")?.remove();
    $("canvas").prepend(c);
    observer.observe(c);
    const entry = { el: c, body, build, sub: subEl };
    cards.push(entry);
    rebuild(entry);
    return entry;
  }
  function rebuild(entry) {
    entry.body.replaceChildren();
    entry.build(entry.body, entry);
  }
  function rebuildAll() {
    for (const entry of cards) rebuild(entry);
  }
  function spec(node, label, detail, figure) {
    const s = document.createElement("article");
    s.className = "spec";
    const stage = document.createElement("div");
    stage.className = `stage${figure ? " figure" : ""}`;
    stage.append(node);
    const l = document.createElement("div");
    l.className = "label";
    l.textContent = label;
    s.append(stage, l);
    if (detail) {
      const d = document.createElement("div");
      d.className = "detail";
      d.textContent = detail;
      s.append(d);
    }
    return s;
  }
  function grid(parent, wide) {
    const g = document.createElement("div");
    g.className = `grid${wide ? " wide" : ""}`;
    parent.append(g);
    return g;
  }
  //: Six specimens a frame, and a later batch cancels an earlier one.
  function batch(parent, makers) {
    let i = 0;
    const mine = ++token;
    const step = () => {
      if (mine !== token) return;
      const frag = document.createDocumentFragment();
      const end = Math.min(i + 6, makers.length);
      for (; i < end; i += 1) frag.append(makers[i]());
      parent.append(frag);
      if (i < makers.length) requestAnimationFrame(step);
    };
    step();
  }
  const draw = (size, mood, level) => atlasDraw(size, mood || LAB.mood, level);
  const withLook = (look, fn) => {
    const was = LAB.look;
    LAB.look = look;
    try { return fn(); } finally { LAB.look = was; }
  };
  //: A pose card's second line: what the card is made of beyond its name.
  //: The base pose only when it differs from the label (a plain "stand"
  //: card read "stand / stand"), then the companion classes that make it.
  function poseDetail(label, pose, classes) {
    return [...(pose === label ? [] : [pose]), ...classes].join(" · ");
  }
  //: The companion's figure in a state: the pose CSS keys on `#nm-buddy`.
  function posed(pose, classes, look) {
    const host = document.createElement("div");
    host.id = "nm-buddy";
    host.className = classes.join(" ");
    host.dataset.pose = pose;
    host.append(withLook(look || LAB.look, () => atlasFigure()));
    return host;
  }
  function refOverlay(stage) {
    if (!LAB.refSrc) return;
    const img = document.createElement("img");
    img.className = "ref";
    img.src = LAB.refSrc;
    stage.append(img);
  }
  function info(parent, rows) {
    const d = document.createElement("dl");
    d.className = "info";
    for (const [k, v] of rows) {
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v;
      d.append(dt, dd);
    }
    parent.append(d);
  }

  // --- the views ---------------------------------------------------------------
  const views = {
    hero() {
      card("Atlas", `${LAB.style} · ${LAB.look} · ${LAB.mood}`, (body, entry) => {
        entry.sub.textContent = `${LAB.style} · ${LAB.look} · ${LAB.mood}`;
        const h = document.createElement("div");
        h.className = "hero";
        const stage = document.createElement("div");
        stage.className = "stage";
        stage.append(draw(340, LAB.mood, "full"));
        refOverlay(stage);
        h.append(stage);
        const t = tuneNow();
        info(h, [["Mood", LAB.mood], ["Cue", ATLAS_MOODS[LAB.mood]?.cue || ""], ["Tune", KNOBS.map(([k]) => `${k} ${t[k]}`).join(", ")], ["Colours", Object.entries(t.colours).map(([k, v]) => `${k} ${v}`).join(", ") || "as designed"]]);
        body.append(h);
      });
    },
    compare() {
      card("Both looks", LAB.mood, (body) => {
        const p = document.createElement("div");
        p.className = "pair";
        for (const look of ["masculine", "feminine"]) {
          const stage = document.createElement("div");
          stage.className = "stage";
          stage.append(withLook(look, () => draw(340, LAB.mood, "full")));
          refOverlay(stage);
          const wrap = document.createElement("div");
          const l = document.createElement("div");
          l.className = "label";
          l.textContent = look;
          wrap.append(stage, l);
          p.append(wrap);
        }
        body.append(p);
        const g = grid(body, true);
        g.style.marginTop = "12px";
        batch(g, POSES.slice(0, 8).flatMap(([label, pose, classes]) => ["masculine", "feminine"].map((look) => () => spec(posed(pose, classes, look), `${label} · ${look}`, "", true))));
      });
    },
    //: **The morning review** (the owner, round 5: "review every expression
    //: and pose at once"): one card, both looks, every mood as the head the
    //: chat shows, every companion state as the figure, and the sizes the
    //: app uses (the figure at 1:1, the bust, the icon), so a round's
    //: changes are read against each other rather than one view at a time.
    review() {
      card("Morning review", "both looks · every expression · every pose · every size", (body) => {
        const auto = typeof atlasLookReason === "function" ? atlasLookReason() : null;
        if (auto) {
          const note = document.createElement("p");
          note.className = "hint";
          note.textContent = `Auto would draw ${auto.look} right now (${{ chosen: "Atlas look is set", "face-looks": "Face looks says so", "your-look": "Your look says so", default: "nothing says otherwise: the main look" }[auto.reason]}).`;
          body.append(note);
        }
        for (const look of ["masculine", "feminine"]) {
          const h = document.createElement("h3");
          h.className = "review-head";
          h.textContent = `${look} · expressions`;
          body.append(h);
          const g = grid(body);
          batch(g, MOODS.map((m) => () => withLook(look, () => spec(draw(88, m, "head"), m, ATLAS_MOODS[m].words || "at rest"))));
          const h2 = document.createElement("h3");
          h2.className = "review-head";
          h2.textContent = `${look} · poses`;
          body.append(h2);
          const g2 = grid(body, true);
          batch(g2, POSES.map(([label, pose, classes]) => () => spec(posed(pose, classes, look), label, classes.join(" "), true)));
          const h3 = document.createElement("h3");
          h3.className = "review-head";
          h3.textContent = `${look} · at size`;
          body.append(h3);
          const g3 = grid(body);
          batch(g3, [
            () => withLook(look, () => spec(posed("stand", [], look), "figure 1:1", "64 by 92, the companion", true)),
            () => withLook(look, () => spec(atlasAvatar(80, LAB.mood), "bust 80", "the guide")),
            () => withLook(look, () => spec(atlasAvatar(28, LAB.mood), "bust 28", "the agent's head")),
            () => withLook(look, () => spec(draw(24, LAB.mood), "24px", "the icon")),
            () => withLook(look, () => spec(draw(16, LAB.mood), "16px", "the smallest")),
          ]);
        }
      });
    },
    moods() {
      card("All moods", `${LAB.style} · ${LAB.look}`, (body) => {
        const g = grid(body);
        batch(g, MOODS.map((m) => () => {
          const s = spec(draw(88, m, "head"), m, ATLAS_MOODS[m].words || "at rest");
          s.onclick = () => setMood(m);
          return s;
        }));
      });
    },
    sizes() {
      card("Every size", `${LAB.look} · ${LAB.mood} · 16 to 200px`, (body) => {
        const g = grid(body);
        batch(g, [200, 160, 120, 96, 80, 64, 48, 40, 32, 28, 24, 20, 16].map((n) => () => spec(draw(n), `${n}px`, n < 28 ? "tiny: the face" : n < 96 ? "head" : "full")));
        g.append(spec(atlasAvatar(80, LAB.mood), "bust 80", "the guide's avatar"), spec(atlasAvatar(28, LAB.mood), "bust 28", "the agent's head"), spec(atlasAvatar(20, LAB.mood), "bust 20", "Find anything"));
      });
    },
    poses() {
      card("Every pose", `${LAB.look} · the companion's states`, (body) => {
        const g = grid(body, true);
        batch(g, POSES.map(([label, pose, classes]) => () => spec(posed(pose, classes), label, poseDetail(label, pose, classes), true)));
      });
    },
    avatar() {
      const seed = LAB.seed;
      card(`Character · ${seed}`, "the generated mark", (body) => {
        const h = document.createElement("div");
        h.className = "hero";
        const stage = document.createElement("div");
        stage.className = "stage";
        stage.append(nameMark(seed, 160));
        h.append(stage);
        let r = {};
        try { r = nameMood(seed) || {}; } catch (e) { r = {}; }
        info(h, [["Mood", r.mood || "seeded"], ["Animal", r.animal || ""], ["Look", r.look || "neutral"], ["Props", (r.props || []).join(", ")], ["Your look", Object.entries(LAB.own).filter(([, v]) => v).map(([k, v]) => `${k} ${v}`).join(", ") || "from the name"]]);
        body.append(h);
      });
    },
    "avatar-sizes"() {
      const seed = LAB.seed;
      card(`Character sizes · ${seed}`, "", (body) => {
        const g = grid(body);
        batch(g, [128, 96, 80, 64, 48, 32, 28, 24, 20, 16].map((n) => () => spec(nameMark(seed, n), `${n}px`)));
      });
    },
    figure() {
      const seed = LAB.seed;
      card(`Figure · ${seed}`, "the companion's body", (body) => {
        const g = grid(body, true);
        let f;
        try { f = drawCharacter(seed, 100, "figure"); } catch (e) { f = nameMark(seed, 128); }
        g.append(spec(f, seed, "figure", true));
      });
    },
    gallery() {
      card("Gallery", "seeds that have caught bugs before", (body) => {
        const g = grid(body);
        batch(g, SEEDS.map((s) => () => {
          const x = spec(s === "Atlas" ? draw(48) : nameMark(s, 48), s);
          x.onclick = () => { LAB.seed = s; $("seed").value = s; views.avatar(); };
          return x;
        }));
      });
    },
    "snap-a"() { snap("A"); },
    "snap-b"() { snap("B"); },
    ab() {
      if (!LAB.snaps.A && !LAB.snaps.B) return say("Keep a tune as A or B first");
      card("A and B", "two tunes, the current one restored after", (body) => {
        const p = document.createElement("div");
        p.className = "pair";
        const current = { tune: JSON.parse(JSON.stringify(window.ATLAS_TUNE || {})), css: userCss() };
        for (const name of ["A", "B"]) {
          const s = LAB.snaps[name];
          const wrap = document.createElement("div");
          const stage = document.createElement("div");
          stage.className = "stage";
          if (s) {
            window.ATLAS_TUNE = JSON.parse(JSON.stringify(s.tune));
            atlasBuild();
            userCss(s.css || "");
            stage.append(withLook(s.look, () => atlasDraw(340, s.mood, "full")));
          }
          const l = document.createElement("div");
          l.className = "label";
          l.textContent = s ? `${name}: ${s.at}` : `${name}: nothing kept`;
          wrap.append(stage, l);
          p.append(wrap);
        }
        window.ATLAS_TUNE = current.tune;
        atlasBuild();
        userCss(current.css);
        body.append(p);
      });
    },
    "reset-tune"() {
      window.ATLAS_TUNE = {};
      atlasBuild();
      syncKnobs();
      rebuildAll();
      store();
      say("Tune reset to the drawing as designed");
    },
  };
  function snap(name) {
    LAB.snaps[name] = { at: new Date().toLocaleTimeString(), tune: JSON.parse(JSON.stringify(window.ATLAS_TUNE || {})), css: userCss(), look: LAB.look, mood: LAB.mood };
    $("snaps").textContent = `A: ${LAB.snaps.A ? LAB.snaps.A.at : "none"}. B: ${LAB.snaps.B ? LAB.snaps.B.at : "none"}.`;
    store();
    say(`Kept as ${name}`);
  }
  function setMood(m) {
    LAB.mood = m;
    for (const b of $("moods").querySelectorAll("button")) b.classList.toggle("on", b.dataset.m === m);
    store();
    rebuildAll();
  }

  // --- the tune knobs -----------------------------------------------------------
  let retuneTimer = 0;
  function retune(partial) {
    clearTimeout(retuneTimer);
    retuneTimer = setTimeout(() => {
      atlasRetune(partial);
      rebuildAll();
      store();
    }, 90);
  }
  function syncKnobs() {
    const t = tuneNow();
    for (const [key] of KNOBS) {
      const input = $(`tune-${key}`);
      input.value = t[key];
      input.nextElementSibling.value = key === "tailCurl" || key === "lockCount" ? String(t[key]) : Number(t[key]).toFixed(2);
    }
    for (const [key] of COLOURS) $(`colour-${key}`).value = t.colours[key] || "";
  }
  for (const [key, label, min, max, step] of KNOBS) {
    const k = document.createElement("div");
    k.className = "knob";
    const span = document.createElement("span");
    span.textContent = label;
    const input = document.createElement("input");
    input.type = "range";
    input.id = `tune-${key}`;
    input.min = min;
    input.max = max;
    input.step = step;
    const output = document.createElement("output");
    input.addEventListener("input", () => {
      const v = Number(input.value);
      output.value = key === "tailCurl" || key === "lockCount" ? String(v) : v.toFixed(2);
      retune({ [key]: v });
    });
    k.append(span, input, output);
    $("knobs").append(k);
  }
  for (const [key, label] of COLOURS) {
    const l = document.createElement("label");
    l.textContent = label;
    const input = document.createElement("input");
    input.id = `colour-${key}`;
    input.placeholder = "as designed";
    input.addEventListener("change", () => retune({ colours: { [key]: input.value.trim() } }));
    l.append(input);
    $("colours").append(l);
  }
  $("css").addEventListener("input", () => {
    LAB.css = $("css").value;
    userCss(LAB.css);
    store();
  });

  // --- the reference overlay ------------------------------------------------------
  $("ref-file").addEventListener("change", () => {
    const file = $("ref-file").files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      LAB.refSrc = reader.result;
      rebuildAll();
      say("Reference loaded");
    };
    reader.readAsDataURL(file);
  });
  for (const [id, prop, scale, digits] of [["ref-op", "--ref-op", 0.01, 2], ["ref-scale", "--ref-scale", 0.01, 2], ["ref-x", "--ref-x", 1, 0], ["ref-y", "--ref-y", 1, 0]]) {
    const input = $(id);
    input.addEventListener("input", () => {
      const v = Number(input.value) * scale;
      input.nextElementSibling.value = v.toFixed(digits);
      document.documentElement.style.setProperty(prop, digits ? String(v) : `${v}px`);
    });
  }

  // --- the rest of the side ---------------------------------------------------------
  for (const m of MOODS) {
    const b = document.createElement("button");
    b.dataset.m = m;
    b.textContent = m;
    b.onclick = () => setMood(m);
    $("moods").append(b);
  }
  nameMarkLookPickers($("own-parts"), "lab-look-", "From the name", () => ({ ...LAB.own }), (style) => {
    LAB.own = style;
    setOwnNameMarkStyle(style);
    store();
    rebuildAll();
  });
  document.addEventListener("click", (e) => {
    const action = e.target.dataset?.do;
    if (action && views[action]) views[action]();
  });
  $("look").onchange = (e) => { LAB.look = e.target.value; store(); rebuildAll(); };
  $("style").onchange = (e) => { LAB.style = e.target.value; store(); rebuildAll(); };
  $("seed").addEventListener("input", (e) => { LAB.seed = e.target.value.trim() || "Buddy"; store(); });
  $("seed").addEventListener("keydown", (e) => { if (e.key === "Enter") views.avatar(); });
  $("ground").onclick = () => {
    LAB.ground = LAB.ground === "dark" ? "light" : "dark";
    document.documentElement.dataset.mode = LAB.ground;
    $("ground").textContent = `Ground: ${LAB.ground}`;
    store();
  };
  $("live").onclick = () => {
    LAB.live = !LAB.live;
    $("live").textContent = `Live behaviour: ${LAB.live ? "on" : "off"}`;
    say(LAB.live ? "Atlas's own moods now play (sleepy when idle, pokes)" : "Pinned to what you pick");
  };
  $("motion").onclick = () => {
    LAB.motion = !LAB.motion;
    document.documentElement.dataset.avatarMotion = LAB.motion ? "always" : "off";
    $("motion").textContent = `Motion: ${LAB.motion ? "on" : "off"}`;
    store();
  };
  $("clear").onclick = () => {
    token += 1;
    cards.length = 0;
    $("canvas").replaceChildren();
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.innerHTML = "<h2>Cleared.</h2><p>Pick a view on the left.</p>";
    $("canvas").append(empty);
  };
  $("notes").addEventListener("input", () => { LAB.notes = $("notes").value; store(); });
  $("export").onclick = () => {
    const out = {
      exportedAt: new Date().toISOString(),
      look: LAB.look, mood: LAB.mood, style: LAB.style, ground: LAB.ground,
      tune: window.ATLAS_TUNE || {}, tuneInForce: tuneNow(), css: userCss(),
      snapshots: LAB.snaps, seed: LAB.seed, own: LAB.own, notes: $("notes").value,
      howToApply: "tuneInForce holds every value; the ones that differ from atlas.js's ATLAS_TUNE_DEFAULTS are the owner's choices. Geometry keys change the constants atlasBuild reads; colours are the --atl-* custom properties in 08-consistency.css.",
    };
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 2)], { type: "application/json" }));
    a.download = `avatar-lab-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    say("Session exported");
  };
  $("import").addEventListener("change", () => {
    const file = $("import").files[0];
    if (!file) return;
    file.text().then((text) => {
      const s = JSON.parse(text);
      if (s.tune) window.ATLAS_TUNE = s.tune;
      if (s.snapshots) LAB.snaps = s.snapshots;
      if (s.css !== undefined) { LAB.css = s.css; $("css").value = s.css; userCss(s.css); }
      if (s.look) { LAB.look = s.look; $("look").value = s.look; }
      if (s.mood) LAB.mood = s.mood;
      if (s.notes !== undefined) { LAB.notes = s.notes; $("notes").value = s.notes; }
      atlasBuild();
      syncKnobs();
      setMood(LAB.mood);
      $("snaps").textContent = `A: ${LAB.snaps.A ? LAB.snaps.A.at : "none"}. B: ${LAB.snaps.B ? LAB.snaps.B.at : "none"}.`;
      say("Session loaded");
    }).catch((e) => say(`Could not read it: ${e.message}`));
  });

  // --- boot -------------------------------------------------------------------------
  try {
    const saved = JSON.parse(localStorage.getItem(`${K}state`) || "{}");
    for (const key of ["look", "style", "mood", "seed", "own", "ground", "motion", "css", "notes", "snaps"]) if (saved[key] !== undefined) LAB[key] = saved[key];
    if (saved.tune) window.ATLAS_TUNE = saved.tune;
  } catch (e) { /* nothing kept */ }
  atlasBuild();
  setOwnNameMarkStyle(LAB.own);
  $("look").value = LAB.look;
  $("style").value = LAB.style;
  $("seed").value = LAB.seed;
  $("css").value = LAB.css;
  userCss(LAB.css);
  $("notes").value = LAB.notes;
  for (const [key] of PROFILE_LOOK_PARTS) { const el = $(`lab-look-${key}`); if (el) el.value = LAB.own[key] || ""; }
  document.documentElement.dataset.mode = LAB.ground;
  $("ground").textContent = `Ground: ${LAB.ground}`;
  document.documentElement.dataset.avatarMotion = LAB.motion ? "always" : "off";
  $("motion").textContent = `Motion: ${LAB.motion ? "on" : "off"}`;
  $("snaps").textContent = `A: ${LAB.snaps.A ? LAB.snaps.A.at : "none"}. B: ${LAB.snaps.B ? LAB.snaps.B.at : "none"}.`;
  syncKnobs();
  setMood(LAB.mood);
  $("status").textContent = `ready · ${ROOT === "/" ? "served by the app" : "opened as a file"}`;
  views.hero();
}
