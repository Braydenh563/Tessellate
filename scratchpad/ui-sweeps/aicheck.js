// Check with AI, in place (INBOX 410). The owner, 2026-09-24: "improve how
// the 'check with ai' feature works in the documents editor."
//
// Drives the suggestions panel in Chromium: with no model connected (the
// sandbox has none, so this is the real server's answer) the panel says so
// with a way to Settings, Models; with a canned stream (the route fulfilled
// here, the backend's own parsing is tests/test_doc_ai_check.py) the findings
// land as rows with Apply and Dismiss and as underlines in the text; Stop ends
// a check that is still running; Discuss in chat opens the chat with the
// document attached and nothing typed for the writer.
//
// Usage: BASE=http://127.0.0.1:8792 [THEME=dark] node aicheck.js
const { boot } = require("./lib.js");

let bad = 0;
let good = 0;
const ok = (n, c, d) => {
  if (c) good += 1;
  else bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`);
};

const DOC = "# Plan\n\nIts a good plan. The team have agreed to it's terms. We was going to start monday.\n";
const STREAM = [
  { type: "item", quote: "Its a good plan", reason: "missing apostrophe", fix: "It's a good plan" },
  { type: "item", quote: "it's terms", reason: "possessive, no apostrophe", fix: "its terms" },
  { type: "item", quote: "We was going", reason: "we takes were", fix: "We were going" },
  { type: "done", count: 3, message: "", ollama_running: true },
].map((e) => JSON.stringify(e)).join("\n") + "\n";

(async () => {
  const { browser, page } = await boot();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(1500);
  const J = JSON.stringify;
  await page.evaluate(async (c) => {
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Plan", content: c, file_type: "md" }) });
    await loadDocuments(d.id);
  }, DOC);
  await page.waitForTimeout(1200);
  await page.click("#doc-prose");
  await page.waitForTimeout(300);

  const panel = () =>
    page.evaluate(() => {
      const p = document.getElementById("doc-prose-panel");
      const run = p.querySelector(".doc-prose-ai-run");
      const groups = [...p.querySelectorAll(".doc-prose-group")].map((g) => g.textContent.trim());
      const ai = p.querySelector(".doc-prose-ai");
      return {
        open: !p.classList.contains("hidden"),
        run: run ? run.textContent.trim() : null,
        groups,
        status: ai ? ai.querySelector(".doc-prose-ai-line, .notice")?.textContent.trim() : null,
        notice: !!p.querySelector(".doc-prose-ai .notice.notice-warn"),
        settings: !!p.querySelector(".doc-prose-ai-settings"),
        chat: !!p.querySelector(".doc-prose-ai-chat"),
        aiRows: [...p.querySelectorAll(".doc-prose-row")].filter((r) => r.querySelector(".doc-finding-dot[data-kind=\"ai\"]")).length,
        underlines: document.querySelectorAll(".cm-content .cm-finding-ai").length,
      };
    });

  // --- no model: the real server says so ------------------------------------------
  await page.click(".doc-prose-ai-run");
  await page.waitForFunction(() => docAiCheck.state !== "running", null, { timeout: 15000 }).catch(() => {});
  let p = await panel();
  ok("with no model the panel says so, as a warn notice", p.notice && /No AI model is connected/.test(p.status || ""), J(p));
  ok("with a way to Settings, Models, and Discuss in chat beside it", p.settings && p.chat, J(p));
  await page.click(".doc-prose-ai-settings");
  await page.waitForTimeout(700);
  const models = await page.evaluate(() => {
    const s = document.getElementById("settings-models");
    return !!s && !s.classList.contains("hidden") && s.getBoundingClientRect().height > 0;
  });
  ok("the button opens Settings on Models", models);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(400);

  // --- a canned stream: findings land as rows and underlines -------------------------
  await page.route("**/ai-check", (route) => route.fulfill({ status: 200, contentType: "application/x-ndjson", body: STREAM }));
  await page.click(".doc-prose-ai-run");
  await page.waitForFunction(() => docAiCheck.state === "done", null, { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(300);
  p = await panel();
  ok("three findings land under Checked with AI", p.aiRows === 3 && p.groups.some((g) => /Checked with AI/.test(g)), J(p));
  ok("and are underlined in the text", p.underlines === 3, J(p.underlines));
  ok("the line says what it found", p.status === "Checked with AI: 3 findings.", p.status);
  const row = await page.evaluate(() => {
    const r = [...document.querySelectorAll("#doc-prose-panel .doc-prose-row")].find((x) => x.querySelector(".doc-finding-dot[data-kind=\"ai\"]"));
    return {
      words: r.querySelector(".doc-finding-words")?.textContent,
      why: r.querySelector(".doc-finding-why")?.textContent,
      apply: r.querySelector(".doc-prose-fix:not(.doc-prose-dismiss)")?.getAttribute("aria-label"),
      dismiss: r.querySelector(".doc-prose-dismiss")?.getAttribute("aria-label"),
      dot: getComputedStyle(r.querySelector(".doc-finding-dot[data-kind=\"ai\"]")).backgroundColor,
    };
  });
  ok("a row is the words, the reason, Apply and Dismiss", row.words && row.why === "missing apostrophe" && /It.s a good plan/.test(row.apply || "") && row.dismiss === "Dismiss this finding", J(row));
  // Apply the first.
  await page.evaluate(() => {
    const r = [...document.querySelectorAll("#doc-prose-panel .doc-prose-row")].find((x) => x.querySelector(".doc-finding-dot[data-kind=\"ai\"]"));
    r.querySelector(".doc-prose-fix:not(.doc-prose-dismiss)").click();
  });
  await page.waitForTimeout(400);
  let text = await page.evaluate(() => docCmView.state.doc.toString());
  p = await panel();
  ok("Apply writes the fix and the row goes", text.includes("It's a good plan.") && p.aiRows === 2, J({ rows: p.aiRows }));
  await page.evaluate(() => {
    const r = [...document.querySelectorAll("#doc-prose-panel .doc-prose-row")].find((x) => x.querySelector(".doc-finding-dot[data-kind=\"ai\"]"));
    r.querySelector(".doc-prose-dismiss").click();
  });
  await page.waitForTimeout(300);
  p = await panel();
  text = await page.evaluate(() => docCmView.state.doc.toString());
  ok("Dismiss removes a row and leaves the text", p.aiRows === 1 && text.includes("it's terms"), J(p.aiRows));

  // --- Stop ---------------------------------------------------------------------------
  await page.unroute("**/ai-check");
  await page.route("**/ai-check", () => { /* never answers */ });
  await page.click(".doc-prose-ai-run");
  await page.waitForTimeout(400);
  p = await panel();
  ok("while it runs the button is Stop and the line says so", p.run === "Stop" && /Checking with AI/.test(p.status || ""), J(p));
  await page.click(".doc-prose-ai-run");
  await page.waitForTimeout(400);
  p = await panel();
  ok("Stop ends it", p.run === "Check with AI" && /^Stopped\./.test(p.status || ""), J(p));

  // --- measure, light or dark ---------------------------------------------------------
  const m = await page.evaluate(() => {
    const p = document.getElementById("doc-prose-panel").getBoundingClientRect();
    const line = document.querySelector(".doc-prose-ai-line");
    return { panelH: Math.round(p.height), lineColor: line && getComputedStyle(line).color, bg: getComputedStyle(document.getElementById("doc-prose-panel")).backgroundColor };
  });
  console.log("measure:", J(m));
  await page.screenshot({ path: `${process.env.SCRATCH || "."}/shots/aicheck-${process.env.THEME || "light"}.png` });

  // --- Discuss in chat ----------------------------------------------------------------
  await page.click(".doc-prose-ai-chat");
  await page.waitForTimeout(800);
  const chat = await page.evaluate(() => ({
    tab: localStorage.getItem("activeTab") || document.querySelector(".tab-page:not(.hidden)")?.id,
    input: document.getElementById("chat-input")?.value || "",
    chips: (typeof attachedDocuments !== "undefined" ? attachedDocuments : []).map((d) => d.name),
    nudge: document.getElementById("chat-nudge")?.textContent.trim() || "",
  }));
  ok("Discuss in chat opens chat with the document attached and nothing typed", chat.input === "" && chat.chips.includes("Plan"), J(chat));
  ok("and no skill suggestion over it", !/skill for this/.test(chat.nudge), chat.nudge);

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${good} passed, ${bad} failed`);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
