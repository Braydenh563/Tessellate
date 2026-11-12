// INBOX 443 (a), the owner: "the companion perches and action surfaces and
// stuff needs to be properly done for the chat tab". Where the companion
// sits on the Chat tab, measured against the controls it must never cover:
// the composer's input, Send, the latest message, the jump-to-latest pill;
// and which Chat surface it is on (the dock, the message pane, the
// conversation list, a bubble, or a window bar). Then one real turn against
// a model that takes SLOW seconds to answer (FAKE, a fake OpenAI server:
// `SLOW=7 PORT=8774 python3 <slowfake.py>`, which wraps
// scratchpad/fake_openai_server.py), sampled while it thinks and after it
// lands: the class it wears (`nmb-think`), where it went, and what it did.
//
// Env: W (1440; 390 boots a phone), KIND (atlas), FAKE (8774), SHOT (a tag
// for screenshots in out/buddy-chat-*.png). Exits 1 when the drawn figure
// overlaps a protected control by more than 2px at any sample where it is
// not on its way somewhere (a frame of a move is printed, marked moving).
const { boot } = require("./lib.js");
const path = require("path");

const W = Number(process.env.W || 1440);
const OUTDIR = path.join(__dirname, "out");
require("fs").mkdirSync(OUTDIR, { recursive: true });

async function sample(page, label) {
  return page.evaluate((label) => {
    const buddy = document.getElementById("nm-buddy");
    if (!buddy) return { label, missing: true };
    //: The drawn parts only: the box's empty corners are not ink.
    //: A part is ink only when it and every group around it is drawn: the
    //: props (a moon, a book, a page) are in the figure at opacity 0.
    const shown = (el) => {
      for (let n = el; n && n !== buddy; n = n.parentElement) {
        const cs = getComputedStyle(n);
        if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) < 0.05) return false;
      }
      return true;
    };
    const parts = [...buddy.querySelectorAll(".nm-buddy-char *")].filter((el) => el instanceof SVGGraphicsElement && !(el instanceof SVGGElement) && !(el instanceof SVGSVGElement) && !el.closest("defs, clipPath, mask") && shown(el));
    const ink = parts.map((el) => Object.assign(el.getBoundingClientRect().toJSON(), { cls: el.getAttribute("class") || el.tagName })).filter((r) => r.width && r.height);
    const fig = (buddy.querySelector(".nm-figure, .atl-figure") || buddy).getBoundingClientRect();
    const box = (el) => {
      if (!el || el.closest(".hidden") || !el.getClientRects().length) return null;
      const r = el.getBoundingClientRect();
      return r.width && r.height ? r : null;
    };
    const msgs = [...document.querySelectorAll("#chat-messages .msg")];
    const protect = {
      input: box(document.getElementById("chat-input")),
      send: box(document.getElementById("chat-send")),
      stop: box(document.getElementById("chat-stop")),
      latest: box(msgs[msgs.length - 1]),
      jump: box(document.getElementById("chat-jump-latest")),
    };
    const over = {};
    for (const [k, r] of Object.entries(protect)) {
      if (!r) continue;
      let worst = 0;
      let who = "";
      for (const p of ink) {
        const w = Math.min(p.right, r.right) - Math.max(p.left, r.left);
        const h = Math.min(p.bottom, r.bottom) - Math.max(p.top, r.top);
        if (w > 0 && h > 0 && Math.min(w, h) > worst) {
          worst = Math.min(w, h);
          who = p.cls;
        }
      }
      if (worst > 0) over[k] = `${Math.round(worst)} ${who}`;
    }
    const on = nmb.glue?.el || nmb.spot?.anchor || null;
    const name = (el) => (el ? `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ""}${el.classList?.length ? `.${[...el.classList].slice(0, 2).join(".")}` : ""}` : "-");
    const where = on ? (on.closest(".chat-dock") ? "dock" : on.closest("#chat-messages .msg") ? "bubble" : on.closest("#chat-messages") ? "messages" : on.closest("#chat-sidebar") ? "sidebar" : on.closest("#chat-main") ? "chat-main" : "elsewhere") : "window";
    const r = (b) => (b ? [b.left, b.top, b.right, b.bottom].map(Math.round) : null);
    return {
      label, perch: nmb.perch, pose: nmb.pose, legs: nmb.legs, act: nmb.act, think: buddy.classList.contains("nmb-think"),
      reading: buddy.classList.contains("nmb-reading"), on: name(on), where, fig: r(fig),
      dock: r(box(document.querySelector(".chat-dock"))), pane: r(box(document.getElementById("chat-messages"))),
      sidebar: r(box(document.getElementById("chat-sidebar"))), ...Object.fromEntries(Object.entries(protect).map(([k, v]) => [k, r(v)])),
      over,
      //: Whether its own placement thinks this place is clear: a cover
      //: the sweep sees and this misses is the shape being wrong.
      hits: nmb.inner.nameMarkBuddyHits(nmb.x, nmb.y, nmb.pose, nmb.inner.nameMarkBuddyObstacles("chat"), nmb.legs),
      stopBox: r(box(document.getElementById("chat-stop"))),
      at: [nmb.x, nmb.y].map(Math.round),
      //: On its way between two places (a walk, a poof, a crossfade): a
      //: frame of the way, reported but not a place it sits.
      moving: !!(nmb.anim && nmb.anim.playState === "running") || buddy.classList.contains("nmb-walking"),
    };
  }, label);
}

(async () => {
  const phone = W < 700;
  const { browser, page } = await boot({ viewport: { width: W, height: phone ? 844 : 900 }, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
  const fake = process.env.FAKE || "8774";
  await page.evaluate(async (port) => apiJson("/models/provider", { method: "POST", body: JSON.stringify({ provider: "openai", base_url: `http://127.0.0.1:${port}/v1` }) }).catch((e) => ({ error: String(e) })), fake);
  await page.evaluate(async (k) => {
    localStorage.removeItem("nm-buddy-spots");
    prefs.set("avatar-buddy", k); await ensureModule("characters"); syncNameMarkBuddy();
  }, process.env.KIND || "atlas");
  await page.evaluate(() => switchTab("chat"));
  await page.waitForTimeout(3000);
  const rows = [await sample(page, "empty chat")];
  if (process.env.SHOT) await page.screenshot({ path: `${OUTDIR}/buddy-chat-${W}-empty-${process.env.SHOT}.png` });
  // One quick turn so there is a transcript, then the slow one sampled.
  await page.fill("#chat-input", "What tags do I have?");
  await page.click("#chat-send");
  for (let i = 0; i < 6; i += 1) {
    await page.waitForTimeout(2000);
    rows.push(await sample(page, `turn +${(i + 1) * 2}s`));
  }
  if (process.env.SHOT) await page.screenshot({ path: `${OUTDIR}/buddy-chat-${W}-thinking-${process.env.SHOT}.png` });
  await page.waitForSelector("#chat-send:not(.hidden)", { timeout: 30000 }).catch(() => {});
  for (let i = 0; i < 4; i += 1) {
    await page.waitForTimeout(1000);
    rows.push(await sample(page, `landed +${i + 1}s`));
  }
  await page.waitForTimeout(5000);
  rows.push(await sample(page, "settled"));
  if (process.env.SHOT) await page.screenshot({ path: `${OUTDIR}/buddy-chat-${W}-settled-${process.env.SHOT}.png` });
  let bad = false;
  for (const row of rows) {
    const o = Object.entries(row.over || {}).filter(([, v]) => parseFloat(v) > 2);
    if (o.length && !row.moving) bad = true;
    console.log(`${row.label}: ${row.perch}/${row.pose}${row.legs ? `/${row.legs}` : ""} act=${row.act || "-"}${row.think ? " think" : ""}${row.reading ? " reading" : ""} on ${row.on} (${row.where}) fig ${row.fig}${o.length ? `  OVER ${JSON.stringify(Object.fromEntries(o))} hits=${row.hits}${row.moving ? " (moving)" : ""} at ${row.at} stop ${row.stopBox}` : ""}`);
  }
  const last = rows[rows.length - 1];
  console.log(`dock ${last.dock} pane ${last.pane} sidebar ${last.sidebar} input ${last.input} send ${last.send} latest ${last.latest} jump ${last.jump}`);
  console.log(bad ? "FAIL" : "PASS");
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
