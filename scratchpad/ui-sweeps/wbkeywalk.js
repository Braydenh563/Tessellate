// INBOX 445 (2): a board's items reached from the keyboard alone.
//
// Tab from the board's chrome until the canvas has focus (it is a Tab stop
// now), then Tab walks the items in reading order, each announced in
// `#wb-announcer`; past the last one Tab leaves the canvas (no trap), and
// Shift+Tab walks back. Ctrl+A selects pictures too. On a map the arrows
// announce the topic they land on.
//
//   BASE=http://127.0.0.1:8798 SCRATCH=/tmp/mm-wb-a08 \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbkeywalk.js
const { boot, newBoard: libNewBoard } = require("./lib.js");

let pass = 0;
let fail = 0;
function ok(label, good, detail) {
  if (good) pass += 1;
  else fail += 1;
  console.log(`${good ? "OK  " : "FAIL"} ${label}${detail ? "  " + detail : ""}`);
}

async function newBoard(page, name, type) {
  await libNewBoard(page, name, type);
  await page.keyboard.press("Escape");
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await newBoard(page, "Key walk", "board");
  await page.evaluate(async () => {
    const board = window.currentBoardId;
    const post = async (path, body) => apiJson(path, { method: "POST", body: JSON.stringify(body) });
    await post("/whiteboard/sketches", { board_id: board, x: 0, y: 0, data: JSON.stringify({ d: "M 100 100 h 160 v 100 h -160 Z", color: "#335577", width: 3, shape: "rect" }) });
    await post("/whiteboard/objects", { kind: "text", board_id: board, x: 400, y: 100, width: 200, height: 100, data: { content: "Second, a sticky", bg: "#fff3a8" } });
    await post("/whiteboard/objects", { kind: "text", board_id: board, x: 100, y: 400, width: 200, height: 100, data: { content: "Third, a text box" } });
    await post("/whiteboard/objects", { kind: "image", board_id: board, x: 3000, y: 2400, width: 160, height: 120, data: { url: "/media/none.png" } });
    await fetchWhiteboardState();
    renderWhiteboardNow();
    clearWbSelection();
  });
  await page.waitForTimeout(500);

  // Tab from the board's first control until the canvas has focus.
  await page.evaluate(() => document.querySelector("#library-view-whiteboard button:not([disabled])").focus());
  let reached = false;
  for (let i = 0; i < 60 && !reached; i++) {
    await page.keyboard.press("Tab");
    reached = await page.evaluate(() => document.activeElement && document.activeElement.id === "whiteboard-container");
  }
  ok("the canvas is reachable with Tab", reached);
  const ring = await page.evaluate(() => {
    const cs = getComputedStyle(document.getElementById("whiteboard-container"));
    return `${cs.outlineStyle} ${cs.outlineWidth}`;
  });
  ok("and shows a focus ring when it arrives", ring.startsWith("solid") && parseFloat(ring.split(" ")[1]) >= 2, ring);

  const said = [];
  for (let i = 0; i < 4; i++) {
    await page.keyboard.press("Tab");
    await page.waitForTimeout(120);
    said.push(await page.evaluate(() => document.getElementById("wb-announcer").textContent));
  }
  ok("Tab walks the four items in reading order, each announced", said[0].startsWith("Rectangle, 1 of 4") && said[1].startsWith("Sticky note: Second") && said[2].startsWith("Text box: Third") && said[3].startsWith("Picture, 4 of 4"), said.join(" | "));
  await page.waitForTimeout(500);
  const onScreen = await page.evaluate(() => {
    const el = document.querySelector(".wb-object.wb-selected");
    const r = el && el.getBoundingClientRect();
    const v = document.getElementById("whiteboard-container").getBoundingClientRect();
    return Boolean(r && r.left >= v.left && r.right <= v.right && r.top >= v.top && r.bottom <= v.bottom);
  });
  ok("an off-screen item is brought on screen", onScreen);
  await page.keyboard.press("Tab");
  const left = await page.evaluate(() => document.activeElement && document.activeElement.id);
  ok("past the last item Tab leaves the canvas", left !== "whiteboard-container", left);
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Shift+Tab");
  await page.waitForTimeout(120);
  const back = await page.evaluate(() => document.getElementById("wb-announcer").textContent);
  ok("Shift+Tab walks back", back.startsWith("Text box: Third"), back);
  await page.keyboard.press("Control+a");
  const all = await page.evaluate(() => wbMultiSelection.size);
  ok("Ctrl+A selects the picture too", all === 4, String(all));
  await page.keyboard.press("Escape");

  await newBoard(page, "Key walk map", "map");
  // newBoard's Escape dropped the root's selection; take it again.
  await page.evaluate(() => {
    selectWbItem("object", wbMapIndex().roots[0].id);
    document.getElementById("whiteboard-container").focus();
  });
  await page.keyboard.press("Tab");
  await page.keyboard.type("First branch");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(400);
  await page.keyboard.press("ArrowLeft");
  await page.waitForTimeout(200);
  const label = await page.evaluate(() => document.getElementById("whiteboard-container").getAttribute("aria-label"));
  ok("a map's canvas names its own keys", label.startsWith("Mind map."), label);
  await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(200);
  const topic = await page.evaluate(() => document.getElementById("wb-announcer").textContent);
  ok("an arrow on a map announces the topic", topic.startsWith("Topic: First branch"), topic);
  // Typed straight after Enter, before the editor can have opened: the M
  // and D must not arm the quick-nav chord, F must not focus the branch.
  await page.keyboard.press("Enter");
  await page.keyboard.type("Mind df", { delay: 5 });
  await page.waitForTimeout(700);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(500);
  const fast = await page.evaluate(() => ({
    texts: wbState.objects.map((o) => o.data.content),
    tab: document.querySelector("#tab-library") && !document.querySelector("#tab-library").classList.contains("hidden"),
    guide: Boolean(document.getElementById("chord-guide") && !document.getElementById("chord-guide").classList.contains("hidden")),
  }));
  ok("keys typed before the new topic's editor opens are its text", fast.texts.includes("Mind df") && fast.tab && !fast.guide, JSON.stringify(fast));
  console.log(`${pass} ok, ${fail} failed`);
  await browser.close();
})();
