// L889: Writing room Stop mid-pass with thinking, against an OpenAI-compatible backend that
// streams reasoning_content then words slowly (scratchpad/ui-sweeps/hw889-stub.py PORT THINK GAP, or a
// real llama-server). LLM=http://127.0.0.1:8866/v1 [MODEL=stub-1] BASE=http://127.0.0.1:8856 node hw889.js
const { boot } = require("./lib.js");
const fs = require("fs");
const LLM = process.env.LLM, MODEL = process.env.MODEL || "stub-1", STUBLOG = process.env.STUBLOG || "";
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`); };
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.waitForTimeout(1500);
  const dc = page.locator(".confirm-overlay button", { hasText: "Don't check" });
  if (await dc.count()) await dc.first().click();
  const cfg = await page.evaluate(async ([u, m]) => {
    const r = await apiJson("/models/provider", { method: "POST", body: JSON.stringify({ provider: "openai", base_url: u }) });
    try { await apiJson("/preferences", { method: "PUT", body: JSON.stringify({ chat_model: m }) }); } catch (e) {}
    return { running: r.running, models: (r.models || []).map((x) => x.name || x.id).slice(0, 3) };
  }, [LLM, MODEL]);
  console.log("provider", JSON.stringify(cfg));
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(800);
  await page.evaluate(() => [...document.querySelectorAll("#tab-notes button")].find((x) => x.textContent.trim() === "Writing room" && x.offsetParent)?.click());
  await page.waitForTimeout(800);
  const fill = async (thoughts, draft) => page.evaluate(([t, d]) => {
    const a = document.getElementById("draft-thoughts"); a.value = t; a.dispatchEvent(new Event("input", { bubbles: true }));
    const b = document.getElementById("draft-text"); b.value = d; b.dispatchEvent(new Event("input", { bubbles: true }));
  }, [thoughts, draft]);
  const state = () => page.evaluate(() => ({
    text: document.getElementById("draft-text").value,
    status: document.getElementById("draft-status").textContent.trim(),
    composeHidden: document.getElementById("draft-compose").classList.contains("hidden"),
    stopHidden: document.getElementById("draft-cancel").classList.contains("hidden"),
    readOnly: document.getElementById("draft-text").readOnly,
    thinkingShown: !document.getElementById("draft-thinking").classList.contains("hidden"),
    thinkingLen: (document.querySelector("#draft-thinking .thinking") || {}).textContent?.length || 0,
    thoughts: document.getElementById("draft-thoughts").value,
  }));
  const until = async (fn, ms) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (await page.evaluate(fn)) return Date.now() - t0; await page.waitForTimeout(40); } return -1; };
  const ORIGINAL = "My settled draft stays put.";
  // 1. Stop during thinking, before any token.
  await fill("tent stove layers weekend", ORIGINAL);
  await page.click("#draft-compose");
  const tThink = await until(() => !document.getElementById("draft-thinking").classList.contains("hidden"), 20000);
  ok("thinking appears while the model is thinking", tThink >= 0, tThink + " ms");
  await page.waitForTimeout(500);
  const mid = await state();
  ok("during thinking the draft box is untouched and Stop shows", mid.text === ORIGINAL && !mid.stopHidden && mid.composeHidden && mid.thinkingLen > 0, JSON.stringify({ t: mid.text.slice(0, 30), len: mid.thinkingLen }));
  const t0 = Date.now();
  await page.click("#draft-cancel");
  const tStop = await until(() => /^Stopped/.test(document.getElementById("draft-status").textContent.trim()), 5000);
  const after = await state();
  ok("Stop during thinking says Stopped within 500 ms", tStop >= 0 && tStop < 500, tStop + " ms");
  ok("Stop during thinking keeps draft and thoughts, restores Compose", after.text === ORIGINAL && after.thoughts === "tent stove layers weekend" && !after.composeHidden && after.stopHidden && !after.readOnly, JSON.stringify(after));
  // 2. Stop after words have started over a settled draft.
  await fill("tent stove layers weekend", ORIGINAL);
  await page.click("#draft-compose");
  const tWords = await until(() => document.getElementById("draft-text").value !== "My settled draft stays put." && document.getElementById("draft-text").value.length > 20, 30000);
  ok("words stream into the box after thinking", tWords >= 0, tWords + " ms");
  await page.waitForTimeout(600);
  const partial = (await state()).text;
  await page.click("#draft-cancel");
  const tStop2 = await until(() => /^Stopped/.test(document.getElementById("draft-status").textContent.trim()), 5000);
  const after2 = await state();
  ok("Stop mid-words restores the settled draft (partial was " + partial.length + " chars)", tStop2 >= 0 && tStop2 < 500 && after2.text === ORIGINAL && partial.length > 0 && partial !== ORIGINAL, `${tStop2} ms ${JSON.stringify(after2.text.slice(0, 40))}`);
  // 3. The backend stream closed.
  if (STUBLOG && fs.existsSync(STUBLOG)) {
    await page.waitForTimeout(800);
    const log = fs.readFileSync(STUBLOG, "utf8").trim().split("\n");
    const closed = log.filter((l) => /client_closed/.test(l)).length, starts = log.filter((l) => /start/.test(l)).length;
    ok("the backend saw both streams closed by the client", closed >= 2 && starts >= 2, `starts ${starts} closed ${closed}`);
  }
  // 4. A full pass after Stops lands, collapses thinking, and can be undone.
  await fill("tent stove layers weekend", "");
  await page.click("#draft-compose");
  const tDone = await until(() => !document.getElementById("draft-compose").classList.contains("hidden"), 90000);
  const fin = await state();
  ok("a full pass after two Stops completes with text", tDone >= 0 && fin.text.length > 40 && !/^Stopped/.test(fin.status), `${tDone} ms, ${fin.text.length} chars, status ${JSON.stringify(fin.status)}`);
  const open = await page.evaluate(() => document.querySelector("#draft-thinking details, details#draft-thinking")?.open);
  ok("thinking folds shut once the draft lands", open === false || open === undefined, String(open));
  console.log(bad ? `FAILED ${bad}` : "ALL PASS");
  await browser.close();
})().catch((e) => { console.log("ERR", e.message); process.exit(1); });
