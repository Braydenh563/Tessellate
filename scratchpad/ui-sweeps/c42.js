// BASE=http://127.0.0.1:8796 node c42.js (INBOX 1300 C42): composer reply text must survive a reload.
const { boot } = require("./lib.js");
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const out = {};
  if (process.env.TRACE) page.on("request", (r) => { if (/conversations/.test(r.url()) && r.method() !== "GET") console.log(r.method(), r.url().replace(/^.*8796/, ""), (r.postData() || "").slice(0, 160)); });
  await page.evaluate(() => switchTab("chat")); await page.waitForTimeout(600);
  await page.evaluate(() => newChatConversation());
  await page.evaluate(() => { const b = [...document.querySelectorAll(".confirm-overlay button")].find((x) => /Don.t check/.test(x.innerText)); b && b.click(); });
  const qs = (process.env.QS || "yo wassup :)|what can you do|list my tags").split("|");
  for (const q of qs) {
    await page.evaluate(() => { const b = [...document.querySelectorAll(".confirm-overlay button")].find((x) => /Don.t check/.test(x.innerText)); b && b.click(); });
    const n0 = await page.evaluate(() => document.querySelectorAll("#chat-messages .msg.assistant").length);
    await page.fill("#chat-input", q); await page.click("#chat-send", {timeout: 4000}).catch(async (e) => { console.log("BLOCKED", q, await page.evaluate(() => [...document.querySelectorAll(".confirm-overlay")].map((d) => d.innerText))); process.exit(1); });
    await page.waitForFunction((n) => { const a = document.querySelectorAll("#chat-messages .msg.assistant"); return a.length > n && !a[a.length - 1].classList.contains("is-generating"); }, n0, { timeout: 20000 });
    await page.waitForTimeout(1500);
  }
  const live = await page.evaluate(() => [...document.querySelectorAll("#chat-messages .msg.assistant")].map((b) => b.innerText.slice(0, 120)));
  const id = await page.evaluate(() => chatConv.id);
  const stored = await page.evaluate((id) => apiJson(`/conversations/${id}`).then((c) => c.messages.filter((m) => m.role === "assistant").map((m) => m.content.slice(0, 60) + " | steps:" + (m.steps || []).map((x) => x.kind + (x.text ? "+" : "")).join(","))), id);
  await page.reload({ waitUntil: "domcontentloaded" }); await page.waitForTimeout(2000);
  if (await page.locator("#lock-password").isVisible()) { await page.fill("#lock-password", "testpassword123"); await page.click("#lock-submit"); await page.waitForTimeout(2500); }
  await page.evaluate(() => switchTab("chat")); await page.waitForTimeout(600);
  await page.evaluate((id) => openConversation(id), id); await page.waitForTimeout(1500);
  const after = await page.evaluate(() => [...document.querySelectorAll("#chat-messages .msg.assistant")].map((b) => b.innerText.slice(0, 120)));
  console.log(JSON.stringify({ live, stored, after }, null, 1));
  await browser.close();
})();
