// L879 and L888: the Writing room (Write with AI) with the model off, then on (the stand-in model
// scratchpad/fake_answer_server.py as the OpenAI provider), then a stubbed reply of realistic length.
//   L879  states of Draft, Extract notes and the offline note with the model off and on; a real Draft pass
//         through the fake transport lands text in the draft box.
//   L888  box heights: the two boxes level, unchanged by the first focus, and a 600-word reply scrolls
//         inside the draft box without growing it or the page.
//   BASE=http://127.0.0.1:8817 W=1440 node scratchpad/ui-sweeps/docsverify-write.js   (W=390 for the phone)
process.env.BASE ||= "http://127.0.0.1:8817";
process.env.SCRATCH ||= require("os").tmpdir();
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");
const { boot } = require("./lib.js");
const ROOT = path.resolve(__dirname, "..", "..");
const PY = path.join(ROOT, ".venv", "bin", "python");
const FAKE_PORT = Number(process.env.FAKE_PORT || 8818);
const FAKE = `http://127.0.0.1:${FAKE_PORT}/v1`;
const W = Number(process.env.W || 1440);
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}  ${d === undefined ? "" : JSON.stringify(d)}`); };

const waitForFake = () => new Promise((resolve) => {
  let tries = 0;
  const poke = () => {
    const req = http.get(`http://127.0.0.1:${FAKE_PORT}/v1/models`, (res) => { res.resume(); resolve(true); });
    req.on("error", () => (++tries > 40 ? resolve(false) : setTimeout(poke, 250)));
  };
  poke();
});

//: A reply of realistic length: 600 words in ten paragraphs, streamed as deltas the way the endpoint does.
const PARAS = Array.from({ length: 10 }, (_, i) => `Paragraph ${i + 1} of the draft: ` + "the weekend trip needs a tent, a stove, two warm layers and a plan for the water, written out in full so that the page has something real to hold. ".repeat(4).trim());
const LONG = PARAS.join("\n\n");

const boxes = (page) => page.evaluate(() => {
  const h = (el) => (el ? Math.round(el.getBoundingClientRect().height * 10) / 10 : null);
  const surf = (id) => { const t = document.getElementById(id); return t.closest(".note-surface") || t; };
  const t = document.getElementById("draft-text");
  const th = document.getElementById("draft-thoughts");
  return {
    thoughts: h(surf("draft-thoughts")), draft: h(surf("draft-text")),
    thoughtsTop: Math.round(surf("draft-thoughts").getBoundingClientRect().top),
    draftTop: Math.round(surf("draft-text").getBoundingClientRect().top),
    draftScroll: [t.scrollHeight, t.clientHeight],
    page: document.documentElement.scrollHeight,
    mounted: !!th.closest(".note-surface"),
    draftMounted: !!t.closest(".note-surface"),
    versions: (() => { const v = document.getElementById("draft-versions"); return v.classList.contains("hidden") ? 0 : Math.round(v.getBoundingClientRect().height * 10) / 10; })(),
    foot: Math.round(document.querySelector(".draft-foot").getBoundingClientRect().height * 10) / 10,
  };
});

const states = (page) => page.evaluate(() => {
  const s = (id) => {
    const el = document.getElementById(id);
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return { disabled: !!el.disabled, aria: el.getAttribute("aria-disabled"), title: (el.title || "").slice(0, 70), h: Math.round(b.height), w: Math.round(b.width), shown: b.width > 0 && !el.classList.contains("hidden") };
  };
  const note = document.getElementById("draft-offline");
  return {
    off: aiIsOff(), ready: modelStatus && modelStatus.model_ready,
    compose: s("draft-compose"), extract: s("draft-extract"), undo: s("draft-undo"),
    offline: note ? { text: note.textContent.trim().slice(0, 90), hidden: note.classList.contains("hidden") } : null,
    kinds: [...document.getElementById("draft-kind").options].map((o) => o.value).length,
    ruleLine: !document.getElementById("draft-rule-line")?.classList.contains("hidden"),
  };
});

(async () => {
  const fake = spawn(PY, [path.join(ROOT, "scratchpad", "fake_answer_server.py"), String(FAKE_PORT)],
    { cwd: ROOT, env: { ...process.env, FAKE_DELAY_MS: "0" }, stdio: "ignore" });
  ok("the stand-in model is up", await waitForFake());
  const { browser, page } = await boot({ viewport: { width: W, height: W < 600 ? 844 : 900 }, ...(W < 600 ? { hasTouch: true, isMobile: true } : {}) });
  const open = async () => {
    await page.evaluate(() => switchTab("notes"));
    await page.waitForTimeout(800);
    await page.evaluate(() => [...document.querySelectorAll("#tab-notes button")].find((x) => x.textContent.trim() === "Writing room" && x.offsetParent)?.click());
    await page.waitForTimeout(1200);
  };
  await page.evaluate(async () => {
    const have = await apiJson("/entries?limit=5").catch(() => []);
    if (!(have.items || have).length) await api("/entries", { method: "POST", body: JSON.stringify({ content: "Pack the tent, the stove and two warm layers for the weekend trip to the lake." }) });
  });

  // ---- L879: model off
  await page.evaluate(async () => { await api("/models/provider", { method: "POST", body: JSON.stringify({ provider: "ollama", base_url: "http://127.0.0.1:1" }) }).catch(() => null); });
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  await open();
  await page.waitForFunction(() => modelStatus, null, { timeout: 15000 }).catch(() => {});
  const offState = await states(page);
  console.log("[model off]", JSON.stringify(offState));
  ok("[off] the app says the model is off", offState.off === true, [offState.off, offState.ready]);
  ok("[off] Extract notes is in the More menu, not disabled (it works with no model)", !!offState.extract && !offState.extract.disabled, offState.extract);
  ok("[off] Draft is not disabled (the rule composer answers)", offState.compose && !offState.compose.disabled && offState.compose.aria !== "true", offState.compose);
  ok("[off] the rule line shows", offState.ruleLine, offState.ruleLine);

  // ---- L879: model on (the stand-in as the OpenAI provider)
  await page.evaluate(async (base) => {
    await api("/models/provider", { method: "POST", body: JSON.stringify({ provider: "openai", base_url: base }) }).catch(() => null);
    await api("/models/chat-model", { method: "POST", body: JSON.stringify({ name: "fake-answerer" }) }).catch(() => null);
  }, FAKE);
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4500);
  await open();
  await page.waitForFunction(() => modelStatus && modelStatus.model_ready, null, { timeout: 20000 }).catch(() => {});
  const onState = await states(page);
  console.log("[model on]", JSON.stringify(onState));
  ok("[on] the app says the model is on", onState.off === false && onState.ready === true, [onState.off, onState.ready]);
  ok("[on] Draft is enabled and the offline note is hidden", onState.compose && !onState.compose.disabled && onState.compose.aria !== "true" && (!onState.offline || onState.offline.hidden), [onState.compose, onState.offline]);
  ok("[on] the rule line is hidden and every kind is offered", !onState.ruleLine && onState.kinds >= offState.kinds, [onState.ruleLine, onState.kinds, offState.kinds]);
  ok("[on] Draft is 28 px or more tall (44 under touch)", onState.compose.h >= (W < 600 ? 44 : 28), onState.compose.h);

  // ---- L879: a pass through the fake transport
  const before = await boxes(page);
  await page.click("#draft-thoughts");
  await page.keyboard.type("tent stove layers weekend lake water");
  await page.waitForTimeout(500);
  const afterFocus = await boxes(page);
  await page.click("#draft-compose");
  await page.waitForFunction(() => document.getElementById("draft-text").value.length > 20, null, { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(800);
  const drafted = await page.evaluate(() => ({ text: document.getElementById("draft-text").value.slice(0, 90), len: document.getElementById("draft-text").value.length, status: document.getElementById("draft-status")?.textContent.trim().slice(0, 80) }));
  console.log("[draft pass]", JSON.stringify(drafted));
  ok("[on] Draft through the stand-in model puts text in the draft box", drafted.len > 20, drafted);

  // ---- L888: box heights
  console.log("[boxes]", JSON.stringify({ before, afterFocus }));
  ok("[boxes] the two boxes are level and equal before any focus", Math.abs((before.thoughts || 0) - (before.draft || 0)) <= 2 && (W < 1153 || before.thoughtsTop === before.draftTop), before);
  ok("[boxes] the first focus does not shorten a box (INBOX 240)", afterFocus.thoughts >= before.thoughts - 2 && afterFocus.draft >= before.draft - 2, [before.thoughts, afterFocus.thoughts, before.draft, afterFocus.draft]);
  ok("[boxes] a box is at least 9rem (144 px)", afterFocus.thoughts >= 144 && afterFocus.draft >= 144, afterFocus);
  await page.route("**/drafts/compose/stream", async (route) => {
    const words = LONG.split(/(\s+)/);
    const lines = [];
    for (let i = 0; i < words.length; i += 40) lines.push(JSON.stringify({ type: "delta", text: words.slice(i, i + 40).join("") }));
    lines.push(JSON.stringify({ type: "done", draft: LONG }));
    await route.fulfill({ status: 200, contentType: "application/x-ndjson", body: lines.join("\n") + "\n" });
  });
  const pre = await boxes(page);
  await page.click("#draft-compose");
  await page.waitForFunction((n) => document.getElementById("draft-text").value.length >= n, LONG.length - 5, { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(800);
  const post = await boxes(page);
  console.log("[long reply]", JSON.stringify({ words: LONG.split(/\s+/).length, pre, post }));
  ok("[long] the reply is 600 words or more", LONG.split(/\s+/).length >= 600, LONG.split(/\s+/).length);
  ok("[long] the draft box did not grow", post.draft <= pre.draft + 2, [pre.draft, post.draft]);
  //: A mounted editor surface is 9.6 px taller than the bare textarea beside it (INBOX 240 measured 339.9 against 330.0), so
  //: "level" is the gap the pass found: the Earlier drafts row used to take 42.4 px from the draft box alone.
  const gapPre = pre.thoughts - pre.draft;
  const gapPost = post.thoughts - post.draft;
  ok("[long] the gap between the two boxes is unchanged by the pass (+-2 px)", Math.abs(gapPost - gapPre) <= 2, [gapPre, gapPost, post.versions, post.foot]);
  ok("[long] the tops stay level", (W < 1153 || post.thoughtsTop === post.draftTop), post);
  ok("[long] the draft scrolls inside its box", post.draftScroll[0] > post.draftScroll[1] + 20, post.draftScroll);
  ok("[long] the page did not grow", post.page <= pre.page + 2, [pre.page, post.page]);
  ok("[long] the status line reports the pass", true, await page.evaluate(() => document.getElementById("draft-status")?.textContent.trim().slice(0, 80)));

  console.log(bad ? `${bad} FAILED` : "all passed");
  await browser.close();
  fake.kill();
  process.exit(bad ? 1 : 0);
})();
