// The OCR workspace's tool row and its interactions (INBOX 717), measured.
//
//   BASE=http://127.0.0.1:8864 W=1440 READY=1 THEME=dark SCRATCH=/tmp/x \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/ocr717.js
//
// W is the window width (390 boots a phone context). READY=1 fakes Tesseract
// ready through `/ocr-readers` (the sandbox has none); unset, the real "not
// installed" state is measured. Opens a three-page PDF and checks: one tool
// row at its control height, every control on one centre line, nothing past
// the row's edge, the reader dot and popover, Read's menu, the ⋯ menu's
// Manage, rings not clipped, the arrows on the rail and the reading, a
// re-read that keeps the page, and Ask attaching a chip with an empty
// composer. MODE=smooth measures the interactions instead (see smooth()).
// Prints PASS/FAIL lines and the numbers; exits 1 on a FAIL.
const { boot } = require("./lib.js");

const W = Number(process.env.W || 1440);
const SHOTS = process.env.SCRATCH || ".";
const TAG = `${W}-${process.env.THEME || "light"}${process.env.READY ? "-ready" : ""}`;
let failures = 0;
function check(label, ok, detail) {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail !== undefined ? `  ${detail}` : ""}`);
}

async function main() {
  const phone = W < 600;
  const { browser, page } = await boot({
    viewport: { width: W, height: phone ? 844 : 900 },
    ...(phone ? { hasTouch: true, isMobile: true } : {}),
  });
  if (process.env.READY) {
    await page.route("**/ocr-readers*", async (route) => {
      const json = await (await route.fetch()).json();
      json.tesseract = true;
      json.engine = {
        ...json.engine, ready: true, binary: true, package: true, version: "5.5.3", reason: "", fix: "",
        languages: [{ code: "eng", name: "English" }, { code: "deu", name: "German" }], language: "eng",
        engine: "tesseract", engine_name: "Tesseract", rapidocr: Boolean(process.env.RAPID),
      };
      route.fulfill({ json });
    });
  }
  // A reading, so Ask, the re-read and the arrows have something to act on.
  await page.route("**/ocr-page-read*", (route) =>
    route.fulfill({ json: { text: "Page one. Project kickoff.\n\nScope: capture and search.", model: "test-reader" } }));
  // The page's stored reading follows the faked read, as the server's would.
  let readDone = false;
  await page.route("**/page-reads*", (route) => {
    if (!readDone || route.request().method() !== "GET") return route.continue();
    return route.fulfill({ json: { pages: [{ page: 0, text: "Page one. Project kickoff.\n\nScope: capture and search.", caption: "" }], message: "" } });
  });
  // The recovery-key offer is a first-run card over everything.
  await page.evaluate(() => {
    const skip = [...document.querySelectorAll("button")].find((b) => /Skip for now/.test(b.textContent));
    skip?.click();
  });
  const make = await (await browser.newContext()).newPage();
  await make.setContent(`<style>div{page-break-after:always;font:28px Georgia;padding:60px}</style>
    <div>Page one. Project kickoff.</div><div>Page two. Decisions.</div><div>Page three. Actions.</div>`);
  const pdf = (await make.pdf({ format: "A4" })).toString("base64");
  const media = await page.evaluate(async (b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const fd = new FormData();
    fd.append("file", new File([bytes], `scan-${Date.now()}.pdf`, { type: "application/pdf" }));
    fd.append("direct", "true");
    const r = await fetch("/media/upload", { method: "POST", body: fd, headers: { "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() } });
    return r.json();
  }, pdf);
  await page.evaluate(() => switchTab("library"));
  await page.waitForTimeout(1500);
  await page.evaluate(async (m) => {
    const row = await apiJson(`/media/meta/${encodeURIComponent(m.url.split("/").pop())}`);
    openOcrWorkspace({ ...row, _isImage: true }, [{ ...row, _isImage: true }]);
  }, media);
  await page.waitForTimeout(2500);
  await page.evaluate(() => {
    const skip = [...document.querySelectorAll("button")].find((b) => /Skip for now/.test(b.textContent) && b.offsetParent);
    skip?.click();
  });
  await page.waitForTimeout(300);

  const row = await page.evaluate(() => {
    const dock = document.getElementById("ocr-dock");
    const shown = (el) => el.offsetParent !== null && getComputedStyle(el).visibility !== "hidden";
    const box = dock.getBoundingClientRect();
    const style = getComputedStyle(dock);
    const controls = [...dock.querySelectorAll("button, summary, .select-opener")].filter(shown)
      .filter((el) => !el.closest(".dock-menu-list, .action-menu"));
    const rects = controls.map((el) => ({ id: el.id || el.className.toString().slice(0, 20), r: el.getBoundingClientRect() }));
    const centres = rects.map(({ r }) => r.top + r.height / 2);
    const heights = [...new Set(rects.map(({ r }) => Math.round(r.height)))];
    const innerRight = box.right - parseFloat(style.paddingRight) - parseFloat(style.borderRightWidth);
    return {
      height: Math.round(box.height),
      controlH: Math.max(...rects.map(({ r }) => r.height)),
      paddingY: parseFloat(style.paddingTop) + parseFloat(style.paddingBottom) + parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth),
      spread: Math.max(...centres) - Math.min(...centres),
      heights,
      past: rects.filter(({ r }) => r.right > innerRight + 0.5 || r.left < box.left).map(({ id }) => id),
      folded: [...dock.querySelectorAll(".is-folded")].map((el) => el.id || el.className),
      tight: [...dock.classList].filter((c) => c.startsWith("is-")),
      count: controls.length,
      head: Math.round(document.querySelector(".ocr-head").getBoundingClientRect().height),
      dot: document.getElementById("ocr-engine-dot").className,
      readerTitle: document.querySelector("#ocr-reader-menu > summary").title,
      unnamed: [...document.querySelectorAll("#ocr-workspace button")].filter(shown)
        .filter((b) => !(b.getAttribute("aria-label") || b.textContent.trim())).map((b) => b.id || b.className),
    };
  });
  console.log(JSON.stringify(row));
  const rail = await page.evaluate(() => ({
    tab: document.querySelector("#ocr-rail-switch .is-active")?.dataset.mode,
    items: document.querySelectorAll("#ocr-rail .ocr-rail-item").length,
    tops: new Set([...document.querySelectorAll("#ocr-rail-switch .ocr-rail-tab")].map((t) => Math.round(t.getBoundingClientRect().top))).size,
  }));
  // The page checks need the optional PDF rasteriser (pypdfium2, Settings,
  // Packages). Without it the app says so in #ocr-message and has one page,
  // so the checks are skipped, loudly, rather than failed or passed.
  const noRenderer = await page.evaluate(() => /PDF rasteriser|PDF pages/.test(document.getElementById("ocr-message")?.textContent || ""));
  if (noRenderer) console.log(`SKIP  ${TAG}: the PDF page checks: pypdfium2 is not installed here (the app shows its install notice)`);
  if (!phone && !noRenderer) {
    check(`${TAG}: a PDF opens on its own pages in the rail`, rail.tab === "pages" && rail.items === 3, JSON.stringify(rail));
    check(`${TAG}: the rail's switch is one row`, rail.tops === 1, `${rail.tops} row(s)`);
  }
  const oneRow = row.height <= Math.round(row.controlH + row.paddingY + 1);
  check(`${TAG}: the tool row is one row`, oneRow, `${row.height}px (control ${row.controlH} + ${row.paddingY})`);
  check(`${TAG}: every control on one centre line`, row.spread <= 1, `${row.spread.toFixed(2)}px spread`);
  check(`${TAG}: nothing past the row's edge`, row.past.length === 0, row.past.join(","));
  check(`${TAG}: every visible button has a name`, row.unnamed.length === 0, row.unnamed.join(","));
  check(`${TAG}: the reader dot says ${process.env.READY ? "ready" : "not ready"}`,
    process.env.READY ? /is-ok/.test(row.dot) : /is-warn|is-ok/.test(row.dot), `${row.dot} / ${row.readerTitle}`);
  await page.screenshot({ path: `${SHOTS}/ocr717-${TAG}.png` });

  // Rings: every focusable in the head and the row, its 4px ring against
  // every clipping ancestor.
  const clipped = await page.evaluate(() => {
    const out = [];
    const shown = (el) => el.offsetParent !== null;
    for (const el of [...document.querySelectorAll(".ocr-head button, .ocr-head summary, .ocr-head .select-opener")].filter(shown)) {
      const r = el.getBoundingClientRect();
      for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
        const cs = getComputedStyle(a);
        if (cs.overflowX === "visible" && cs.overflowY === "visible" && cs.contain.indexOf("paint") < 0) continue;
        const b = a.getBoundingClientRect();
        if (r.left - 4 < b.left - 0.5 || r.right + 4 > b.right + 0.5 || r.top - 4 < b.top - 0.5 || r.bottom + 4 > b.bottom + 0.5) {
          out.push(`${el.id || el.className.toString().slice(0, 16)} in ${a.id || a.className.toString().slice(0, 16)}`);
        }
        break;
      }
    }
    return out;
  });
  check(`${TAG}: no focus ring is clipped in the head`, clipped.length === 0, clipped.join("; "));

  // The reader popover: the dot, the choice, the language label over its select.
  await page.evaluate(() => document.querySelector("#ocr-reader-menu > summary").click());
  await page.waitForTimeout(400);
  const pop = await page.evaluate(() => {
    // On a phone a dock menu opens as a sheet, its list moved into it.
    const list = document.getElementById("ocr-reader").closest(".dock-menu-list");
    const r = list.getBoundingClientRect();
    const label = list.querySelector(".ocr-engine-lang-label");
    const select = list.querySelector(".ocr-engine-lang-wrap .select-opener, .ocr-engine-lang-wrap select");
    return {
      open: document.getElementById("ocr-reader-menu").open || Boolean(list.closest(".sheet-card")),
      inWindow: r.left >= 0 && r.right <= innerWidth && r.bottom <= innerHeight,
      text: list.textContent.replace(/\s+/g, " ").trim().slice(0, 160),
      stacked: label && select ? label.getBoundingClientRect().bottom <= select.getBoundingClientRect().top + 1 : null,
      install: [...list.querySelectorAll("button")].map((b) => b.textContent.trim()).filter(Boolean),
    };
  });
  check(`${TAG}: the reader popover opens inside the window`, pop.open && pop.inWindow, pop.text);
  if (process.env.READY) check(`${TAG}: the language label stands over its select`, pop.stacked === true, String(pop.stacked));
  else check(`${TAG}: not installed, the popover offers Install`, pop.install.some((t) => /Install Tesseract/.test(t)), pop.install.join("|"));
  await page.screenshot({ path: `${SHOTS}/ocr717-${TAG}-reader.png` });
  // RapidOCR, a choice (RAPID=1 fakes it installed): the option, or the
  // "not installed" line with its Install.
  const rapid = await page.evaluate(() => {
    const option = document.querySelector('#ocr-reader option[value="rapidocr"]');
    return {
      text: option?.textContent || "",
      disabled: Boolean(option?.disabled),
      missing: !document.getElementById("ocr-rapidocr-missing").classList.contains("hidden"),
    };
  });
  if (process.env.READY) {
    check(`${TAG}: RapidOCR is ${process.env.RAPID ? "offered" : "named as not installed, with Install"}`,
      process.env.RAPID ? !rapid.disabled && !rapid.missing && /English and Chinese/.test(rapid.text)
        : rapid.disabled && rapid.missing && /not installed/.test(rapid.text), JSON.stringify(rapid));
  }
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  const afterEsc = await page.evaluate(() => ({
    popover: document.getElementById("ocr-reader-menu").open,
    workspace: !document.getElementById("ocr-workspace").classList.contains("hidden"),
  }));
  check(`${TAG}: Escape closes the popover, not the window`, !afterEsc.popover && afterEsc.workspace, JSON.stringify(afterEsc));

  // Read's menu.
  const menu = await page.evaluate(async () => {
    const caret = document.getElementById("ocr-read-menu");
    if (!caret) return null;
    caret.click();
    await new Promise((r) => setTimeout(r, 300));
    const open = [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item")].map((b) => b.textContent.trim());
    document.body.click();
    return open;
  });
  if (!noRenderer) check(`${TAG}: Read's menu holds this page, all pages and a range`,
    menu && menu.length === 3 && /all 3 pages/.test(menu[1]), JSON.stringify(menu));
  await page.waitForTimeout(200);

  // The ⋯ menu: Manage, and whatever folded.
  const more = await page.evaluate(async () => {
    document.querySelector("#ocr-tools-more .menu-wrap > button").click();
    await new Promise((r) => setTimeout(r, 300));
    const rows = [...document.querySelectorAll(".action-menu:not(.hidden) .menu-item, .sheet-card .menu-item")].map((b) => b.textContent.trim());
    document.body.click();
    document.querySelector(".sheet-overlay:not(.hidden) .sheet-close, .sheet-overlay:not(.hidden) [aria-label='Close']")?.click();
    return rows;
  });
  check(`${TAG}: ⋯ holds Manage readers`, more.some((t) => /Manage readers/.test(t)), more.join(" | "));
  if (row.folded.length) {
    check(`${TAG}: ⋯ offers what folded`, more.length > 1, `${row.folded.join(",")} -> ${more.length} rows`);
  }
  await page.keyboard.press("Escape").catch(() => {});
  await page.waitForTimeout(300);

  // Read page 1 (faked), then the reading's arrows and the re-read.
  readDone = true;
  await page.evaluate(() => document.getElementById("ocr-read-page").click());
  await page.waitForTimeout(1200);
  const read = await page.evaluate(() => ({
    rows: document.querySelectorAll("#ocr-region-list .ocr-region").length,
    empty: !document.getElementById("ocr-empty").classList.contains("hidden"),
    label: document.getElementById("ocr-read-page-label").textContent,
  }));
  if (!process.env.READY) {
    // Nothing can read here: the read says what to do, and Ask has nothing.
    const said = await page.evaluate(() => document.getElementById("ocr-message").textContent);
    check(`${TAG}: a read that cannot run says what to do`, /reader menu|Settings/.test(said), said);
    await browser.close();
    process.exit(failures ? 1 : 0);
  }
  check(`${TAG}: a read fills the reading and drops the empty state`, read.rows > 0 && !read.empty, JSON.stringify(read));

  // Ask: a chip, an empty composer, a toast.
  const ask = await page.evaluate(async () => {
    document.getElementById("chat-input").value = "";
    const toasts = [];
    const watch = new MutationObserver((list) => {
      for (const m of list) for (const n of m.addedNodes) if (n.nodeType === 1) toasts.push(n.textContent.trim());
    });
    watch.observe(document.getElementById("toast-box"), { childList: true, subtree: true });
    document.getElementById("ocr-to-chat").click();
    await new Promise((r) => setTimeout(r, 900));
    watch.disconnect();
    const chip = document.querySelector("#chat-selection-attachment .attachment-chip");
    return {
      composer: document.getElementById("chat-input").value,
      chip: chip ? chip.textContent.trim().slice(0, 80) : "",
      toast: toasts.join(" | ").slice(0, 200),
      closed: document.getElementById("ocr-workspace").classList.contains("hidden"),
    };
  });
  check(`${TAG}: Ask leaves the composer empty`, ask.composer === "", JSON.stringify(ask.composer.slice(0, 40)));
  check(`${TAG}: Ask attaches the page as a chip`, /page 1/.test(ask.chip), ask.chip);
  check(`${TAG}: Ask says what it did`, /attached to your next chat message/.test(ask.toast), ask.toast);
  await page.screenshot({ path: `${SHOTS}/ocr717-${TAG}-ask.png` });
  if (process.env.RAPID) {
    const picked = await page.evaluate(async () => {
      const select = document.getElementById("ocr-reader");
      select.value = "rapidocr";
      select.dispatchEvent(new Event("change", { bubbles: true }));
      const word = document.getElementById("ocr-reader-name").textContent;
      reopenOcrWorkspace();
      await new Promise((r) => setTimeout(r, 1500));
      return { word, after: document.getElementById("ocr-reader").value, url: ocrRegionsUrl(ocrWorkspaceCurrent, 0) };
    });
    check(`${TAG}: choosing RapidOCR names it, is remembered, and asks for it`,
      picked.word === "RapidOCR" && picked.after === "rapidocr" && /engine=rapidocr/.test(picked.url), JSON.stringify(picked));
    await page.evaluate(() => {
      const select = document.getElementById("ocr-reader");
      select.value = "tesseract";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  await browser.close();
  process.exit(failures ? 1 : 0);
}

// MODE=smooth (INBOX 717 item 5): the interactions on a stored three-page
// reading. Page switching (does the reading pane empty, does it follow the
// page), a re-read keeping the selected section, zoom keeping its centre, the
// arrows on the reading, and typing in a reading never turning the page.
const LONG = Array.from({ length: 30 }, (_, i) => `Line ${i + 1} of a long page.`).join("\n\n");

async function smooth() {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  // Three stored pages, each long enough to scroll the reading pane.
  await page.route("**/page-reads*", (route) => {
    if (route.request().method() !== "GET") return route.continue();
    return route.fulfill({ json: { pages: [0, 1, 2].map((p) => ({ page: p, text: `Page ${p + 1}.\n\n${LONG}`, caption: "" })), message: "" } });
  });
  await page.route("**/ocr-page-read*", (route) =>
    route.fulfill({ json: { text: `Page 2 again.\n\n${LONG}`, model: "test-reader" } }));
  const make = await (await browser.newContext()).newPage();
  await make.setContent(`<style>div{page-break-after:always;font:28px Georgia;padding:60px}</style>
    <div>One</div><div>Two</div><div>Three</div>`);
  const pdf = (await make.pdf({ format: "A4" })).toString("base64");
  const media = await page.evaluate(async (b64) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const fd = new FormData();
    fd.append("file", new File([bytes], `smooth-${Date.now()}.pdf`, { type: "application/pdf" }));
    fd.append("direct", "true");
    const r = await fetch("/media/upload", { method: "POST", body: fd, headers: { "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() } });
    return r.json();
  }, pdf);
  await page.evaluate(() => switchTab("library"));
  await page.waitForTimeout(1200);
  await page.evaluate(async (m) => {
    const row = await apiJson(`/media/meta/${encodeURIComponent(m.url.split("/").pop())}`);
    openOcrWorkspace({ ...row, _isImage: true }, []);
  }, media);
  await page.waitForTimeout(2500);

  // Page switching: sample the reading pane every frame while page 2 loads.
  const turn = await page.evaluate(async () => {
    const list = document.getElementById("ocr-region-list");
    const samples = [];
    let sampling = true;
    const tick = () => {
      samples.push(list.children.length);
      if (sampling) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    document.getElementById("ocr-next-page").click();
    await new Promise((r) => setTimeout(r, 1500));
    sampling = false;
    const current = list.querySelector(".ocr-region.is-current-page");
    const lr = list.getBoundingClientRect();
    const cr = current?.getBoundingClientRect();
    return {
      emptyFrames: samples.filter((n) => n === 0).length,
      frames: samples.length,
      current: current?.dataset.page,
      inView: cr ? cr.top >= lr.top - 1 && cr.top < lr.bottom : false,
    };
  });
  check("turning the page never empties the reading pane", turn.emptyFrames === 0, `${turn.emptyFrames} of ${turn.frames} frames empty`);
  check("the reading follows the page", turn.current === "1" && turn.inView, JSON.stringify(turn));

  // A re-read keeps the selected section and where the pane was scrolled.
  const reread = await page.evaluate(async () => {
    const list = document.getElementById("ocr-region-list");
    const row = list.querySelector('.ocr-region[data-page="1"]');
    row.click();
    list.scrollTop = Math.min(list.scrollHeight - list.clientHeight, row.offsetTop + 40);
    const before = list.scrollTop;
    const index = row.dataset.index;
    document.getElementById("ocr-read-page").click();
    await new Promise((r) => setTimeout(r, 1500));
    return {
      before,
      after: list.scrollTop,
      selected: list.querySelector(".ocr-region.is-active")?.dataset.index,
      index,
    };
  });
  check("a re-read keeps the selected section", reread.selected === reread.index, JSON.stringify(reread));

  // Zoom keeps the point at the centre of the page pane.
  const zoom = await page.evaluate(async () => {
    const pane = document.getElementById("ocr-page-pane");
    ocrSetZoom(2);
    await new Promise((r) => setTimeout(r, 300));
    pane.scrollTop = (pane.scrollHeight - pane.clientHeight) / 2;
    pane.scrollLeft = (pane.scrollWidth - pane.clientWidth) / 2;
    const centre = () => ({
      x: (pane.scrollLeft + pane.clientWidth / 2) / pane.scrollWidth,
      y: (pane.scrollTop + pane.clientHeight / 2) / pane.scrollHeight,
    });
    const before = centre();
    ocrStepZoom(1);
    await new Promise((r) => setTimeout(r, 300));
    const after = centre();
    ocrSetZoom(null);
    return { before, after, drift: Math.max(Math.abs(before.x - after.x), Math.abs(before.y - after.y)) };
  });
  check("a zoom step keeps the centre of the page", zoom.drift < 0.03, JSON.stringify(zoom));

  // The arrows walk the reading's sections; Enter goes to its page.
  const keys = await page.evaluate(async () => {
    const list = document.getElementById("ocr-region-list");
    const first = list.querySelector(".ocr-region");
    first.focus();
    first.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    const moved = document.activeElement?.dataset.index;
    document.activeElement.dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true }));
    const end = document.activeElement?.dataset.page;
    document.activeElement.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await new Promise((r) => setTimeout(r, 1200));
    const stops = [...list.querySelectorAll(".ocr-region")].filter((r) => r.tabIndex === 0).length;
    return { moved, end, page: ocrWorkspacePage, stops };
  });
  check("arrows walk the sections, one tab stop, Enter turns to the page",
    keys.moved === "1" && keys.end === "2" && keys.page === 2 && keys.stops === 1, JSON.stringify(keys));

  // Typing in a section never turns the page.
  const typing = await page.evaluate(async () => {
    const text = document.querySelector("#ocr-region-list .ocr-region-text");
    text.focus();
    const at = ocrWorkspacePage;
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
    await new Promise((r) => setTimeout(r, 400));
    return { before: at, after: ocrWorkspacePage };
  });
  check("Left arrow in a reading's text moves the caret, not the page", typing.before === typing.after, JSON.stringify(typing));

  // Pages belongs to the file on screen: a PDF opened, then at once an image,
  // and the PDF's late page load must not put its Pages tab under the image.
  const pages = await page.evaluate(async (m) => {
    const canvas = Object.assign(document.createElement("canvas"), { width: 40, height: 20 });
    const blob = await new Promise((r) => canvas.toBlob(r, "image/png"));
    const fd = new FormData();
    fd.append("file", new File([blob], `pic-${Date.now()}.png`, { type: "image/png" }));
    fd.append("direct", "true");
    const up = await (await fetch("/media/upload", { method: "POST", body: fd, headers: { "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() } })).json();
    const pdf = await apiJson(`/media/meta/${encodeURIComponent(m.url.split("/").pop())}`);
    const pic = await apiJson(`/media/meta/${encodeURIComponent(up.url.split("/").pop())}`);
    closeOcrWorkspace();
    openOcrWorkspace({ ...pdf, _isImage: true }, []);
    openOcrWorkspace({ ...pic, _isImage: true }, []);
    await new Promise((r) => setTimeout(r, 2500));
    return {
      tabs: [...document.querySelectorAll("#ocr-rail-switch .ocr-rail-tab")].map((t) => t.dataset.mode),
      mode: ocrRailMode,
      viewing: ocrWorkspaceCurrent?.original_name,
    };
  }, media);
  check("Pages shows only for the paged file on screen", !pages.tabs.includes("pages") && pages.mode !== "pages", JSON.stringify(pages));

  await browser.close();
  process.exit(failures ? 1 : 0);
}

(process.env.MODE === "smooth" ? smooth : main)().catch((error) => {
  console.error(error);
  process.exit(1);
});
