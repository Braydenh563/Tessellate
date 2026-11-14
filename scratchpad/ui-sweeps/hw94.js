// L-documents-94: writing room Stop mid-pass against a real llama-server (scratchpad/llama-dev.sh serve).
// The fetch is aborted mid-stream as the browser's Stop does; llama-server's /slots must show the slot
// idle soon after, and stay busy without the abort (the control run).
// LLM=http://127.0.0.1:8080 MODEL=<name from /v1/models> BASE=http://127.0.0.1:8781 node hw94.js
const { boot } = require("./lib.js");
const LLM = process.env.LLM || "http://127.0.0.1:8080", MODEL = process.env.MODEL || "";
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`); };
const busy = async () => (await (await fetch(`${LLM}/slots`)).json()).some((s) => s.is_processing);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1280, height: 800 } });
  await page.waitForTimeout(1200);
  const cfg = await page.evaluate(async ([u, m]) => {
    const r = await apiJson("/models/provider", { method: "POST", body: JSON.stringify({ provider: "openai", base_url: u + "/v1" }) });
    try { await apiJson("/preferences", { method: "PUT", body: JSON.stringify({ chat_model: m }) }); } catch (e) {}
    return { running: r.running };
  }, [LLM, MODEL]);
  ok("the app reaches the real model", cfg.running === true, JSON.stringify(cfg));
  const pass = (abortAfter) => page.evaluate(async (after) => {
    const ctl = new AbortController();
    const t0 = performance.now();
    const res = await api.stream("/drafts/compose/stream", {
      method: "POST", signal: ctl.signal,
      body: JSON.stringify({ thoughts: "a long walk along the coast, the weather turning, what to pack for three days and why each thing matters", length: "long" }),
    });
    const reader = res.body.getReader();
    let bytes = 0;
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        bytes += value.length;
        if (after && bytes > after) { ctl.abort(); break; }
      }
    } catch (e) { /* the abort */ }
    return { status: res.status, bytes, ms: Math.round(performance.now() - t0) };
  }, abortAfter);
  // The aborted pass: Stop once the words are flowing.
  const stopped = await pass(400);
  ok("the pass streamed before Stop", stopped.status === 200 && stopped.bytes > 400, JSON.stringify(stopped));
  const t0 = Date.now();
  let idleAt = -1;
  for (let i = 0; i < 60; i++) { if (!(await busy())) { idleAt = Date.now() - t0; break; } await sleep(100); }
  ok("llama-server's slot is idle within 2 s of Stop", idleAt >= 0 && idleAt < 2000, idleAt + " ms");
  // Control: without Stop the same pass keeps the slot busy well past that point.
  const control = pass(0);
  await sleep(2500);
  const stillBusy = await busy();
  ok("control: without Stop the model is still writing 2.5 s in", stillBusy, String(stillBusy));
  const fin = await control;
  ok("control pass completes", fin.status === 200 && fin.bytes > 400, JSON.stringify(fin));
  await browser.close();
  console.log(bad ? `${bad} FAIL` : "ALL PASS");
  process.exit(bad ? 1 : 0);
})();
