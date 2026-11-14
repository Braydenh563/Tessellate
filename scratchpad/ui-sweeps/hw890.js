// L890: a synthetic paste of Word-shaped clipboard HTML (CF_HTML header, mso classes, o:p,
// conditional comments, mso-list), and emulated touch (WIDTH=390). BASE=http://127.0.0.1:8856 node hw890.js
const { boot } = require("./lib.js");
const WIDTH = Number(process.env.WIDTH || 1440);
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`); };
// The Windows CF_HTML header (Version:, StartHTML:) is stripped by the browser before a page sees the clipboard, so none is sent.
const doc = (frag) => '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta http-equiv=Content-Type content="text/html; charset=utf-8"><meta name=ProgId content=Word.Document><meta name=Generator content="Microsoft Word 15"><!--[if gte mso 9]><xml><w:WordDocument><w:View>Normal</w:View></w:WordDocument></xml><![endif]--><style><!-- p.MsoNormal, li.MsoNormal, div.MsoNormal {margin:0in; font-size:11.0pt; font-family:"Calibri",sans-serif;} h1 {mso-style-priority:9; margin-top:12pt; font-size:16.0pt;} @list l0:level1 {mso-level-number-format:bullet;} --></style></head><body lang=EN-US style=\'tab-interval:.5in\'><!--StartFragment-->' + frag + '<!--EndFragment--></body></html>';
const CASES = [
  { name: "heading, bold, italic, link, o:p noise", html: doc('<h1><span style=\'mso-ansi-language:EN-US\'>Trip plan</span><o:p></o:p></h1><p class=MsoNormal><span style=\'font-family:"Calibri",sans-serif\'>Pack the <b>tent</b> and <i>stove</i>, see <a href="https://example.com/map">the map</a>.<o:p></o:p></span></p><p class=MsoNormal><o:p>&nbsp;</o:p></p><p class=MsoNormal>It’s “quoted” – done.<o:p></o:p></p>'), plain: "Trip plan\nPack the tent and stove, see the map.\n\nIt’s “quoted” – done.", must: [/^# Trip plan/m, /\*\*tent\*\*/, /\*stove\*|_stove_/, /\[the map\]\(https:\/\/example\.com\/map\)/, /It’s “quoted” – done\./], mustNot: [/o:p/, /mso-/, /MsoNormal/, /<[a-z]/i, /StartFragment/, /Version:0\.9/, /gte mso/, /@list/] },
  { name: "mso-list bullets with a nested level", html: doc('<p class=MsoListParagraphCxSpFirst style=\'text-indent:-.25in;mso-list:l0 level1 lfo1\'><![if !supportLists]><span style=\'font-family:Symbol;mso-fareast-font-family:Symbol\'><span style=\'mso-list:Ignore\'>·<span style=\'font:7.0pt "Times New Roman"\'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span></span></span><![endif]>Tent<o:p></o:p></p><p class=MsoListParagraphCxSpMiddle style=\'margin-left:1.0in;text-indent:-.25in;mso-list:l0 level2 lfo1\'><![if !supportLists]><span style=\'font-family:"Courier New"\'><span style=\'mso-list:Ignore\'>o<span style=\'font:7.0pt "Times New Roman"\'>&nbsp;&nbsp;&nbsp;</span></span></span><![endif]>Poles<o:p></o:p></p><p class=MsoListParagraphCxSpLast style=\'text-indent:-.25in;mso-list:l0 level1 lfo1\'><![if !supportLists]><span style=\'mso-list:Ignore\'>·<span style=\'font:7.0pt "Times New Roman"\'>&nbsp;&nbsp;&nbsp;</span></span><![endif]>Stove<o:p></o:p></p>'), plain: "· Tent\no Poles\n· Stove", must: [/^- Tent$/m, /^ {2,4}- Poles$/m, /^- Stove$/m], mustNot: [/·/, /^o Poles/m, /mso-/, /<[a-z]/i, /supportLists/] },
  { name: "numbered list", html: doc('<p class=MsoListParagraphCxSpFirst style=\'text-indent:-.25in;mso-list:l1 level1 lfo2\'><![if !supportLists]><span style=\'mso-list:Ignore\'>1.<span style=\'font:7.0pt "Times New Roman"\'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span></span><![endif]>First<o:p></o:p></p><p class=MsoListParagraphCxSpLast style=\'text-indent:-.25in;mso-list:l1 level1 lfo2\'><![if !supportLists]><span style=\'mso-list:Ignore\'>2.<span style=\'font:7.0pt "Times New Roman"\'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span></span><![endif]>Second<o:p></o:p></p>'), plain: "1. First\n2. Second", must: [/^1\. First$/m, /^2\. Second$/m], mustNot: [/mso-/, /<[a-z]/i, /^1\. 1\./m] },
  { name: "table with MsoTableGrid", html: doc('<table class=MsoTableGrid border=1 cellspacing=0 cellpadding=0 style=\'border-collapse:collapse;border:none\'><tr><td width=156 valign=top style=\'width:117.0pt;border:solid windowtext 1.0pt\'><p class=MsoNormal><b>Item</b><o:p></o:p></p></td><td width=156 valign=top><p class=MsoNormal><b>Qty</b><o:p></o:p></p></td></tr><tr><td width=156 valign=top><p class=MsoNormal>Tent<o:p></o:p></p></td><td width=156 valign=top><p class=MsoNormal>1<o:p></o:p></p></td></tr></table><p class=MsoNormal><o:p>&nbsp;</o:p></p>'), plain: "Item\tQty\nTent\t1", must: [/\|\s*Item\s*\|\s*Qty\s*\|/, /\|\s*-+\s*\|\s*-+\s*\|/, /\|\s*Tent\s*\|\s*1\s*\|/], mustNot: [/MsoTableGrid/, /width=/, /<[a-z]/i, /mso-/] },
  { name: "script and event handler in Word-shaped html", html: doc('<p class=MsoNormal onclick="alert(1)">Safe <a href="javascript:alert(2)">text</a><script>alert(3)</script><o:p></o:p></p>'), plain: "Safe text", must: [/Safe text/], mustNot: [/alert/, /javascript:/, /onclick/, /<script/i] },
];
(async () => {
  const phone = WIDTH < 600;
  const { browser, page } = await boot(phone ? { viewport: { width: WIDTH, height: 844 }, hasTouch: true, isMobile: true } : { viewport: { width: WIDTH, height: 900 } });
  await page.waitForTimeout(1500);
  const dc = page.locator(".confirm-overlay button", { hasText: "Don't check" });
  if (await dc.count()) await dc.first().click();
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(1500);
  await page.evaluate(async () => { const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Word paste", content: "" }) }); await loadDocuments(d.id); });
  await page.waitForTimeout(1500);
  await page.evaluate(() => { if (typeof setDocView === "function") setDocView("live"); });
  await page.waitForTimeout(500);
  const focus = async () => {
    if (phone) { const r = await page.evaluate(() => { const b = document.querySelector(".cm-content").getBoundingClientRect(); return { x: b.x + 20, y: b.y + 10 }; }); await page.touchscreen.tap(r.x, r.y); }
    else await page.click(".cm-content");
  };
  for (const c of CASES) {
    await page.evaluate(() => docCmView.dispatch({ changes: { from: 0, to: docCmView.state.doc.length, insert: "" } }));
    await focus();
    await page.evaluate(({ html, plain }) => {
      const dt = new DataTransfer(); dt.setData("text/html", html); dt.setData("text/plain", plain);
      document.querySelector(".cm-content").dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
    }, c);
    await page.waitForTimeout(250);
    const text = await page.evaluate(() => docCmView.state.doc.toString());
    const missing = c.must.filter((r) => !r.test(text)).map(String), extra = c.mustNot.filter((r) => r.test(text)).map(String);
    ok(`word paste: ${c.name}`, !missing.length && !extra.length, JSON.stringify({ text: text.slice(0, 160), missing, extra }));
  }
  // The paste is one undo step.
  await page.evaluate(() => docCmView.dispatch({ changes: { from: 0, to: docCmView.state.doc.length, insert: "" } }));
  await focus();
  await page.evaluate(({ html, plain }) => { const dt = new DataTransfer(); dt.setData("text/html", html); dt.setData("text/plain", plain); document.querySelector(".cm-content").dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true })); }, CASES[0]);
  await page.waitForTimeout(200);
  await page.evaluate(() => docUndo());
  await page.waitForTimeout(200);
  const afterUndo = await page.evaluate(() => docCmView.state.doc.toString());
  ok("one undo removes the whole Word paste", afterUndo === "", JSON.stringify(afterUndo.slice(0, 60)));
  if (phone) {
    // Touch: tapping the editor focuses it and the toolbar controls are finger-sized.
    const m = await page.evaluate(() => {
      const bars = [...document.querySelectorAll("#tab-documents button")].filter((b) => b.offsetParent && b.getBoundingClientRect().width > 0);
      const small = bars.filter((b) => { const r = b.getBoundingClientRect(); return Math.min(r.width, r.height) < 32; }).map((b) => (b.id || b.title || b.textContent.trim()).slice(0, 30) + ":" + Math.round(b.getBoundingClientRect().width) + "x" + Math.round(b.getBoundingClientRect().height));
      return { buttons: bars.length, small, focused: document.activeElement && document.activeElement.className, sx: document.documentElement.scrollWidth - innerWidth };
    });
    ok("tap focuses the editor", /cm-content/.test(m.focused || ""), m.focused);
    ok("no sideways scroll at 390", m.sx <= 0, String(m.sx));
    ok("visible document buttons are at least 32px on touch", m.small.length === 0, JSON.stringify(m.small.slice(0, 6)) + " of " + m.buttons);
  }
  console.log(bad ? `FAILED ${bad}` : "ALL PASS");
  await browser.close();
})().catch((e) => { console.log("ERR", e.message); process.exit(1); });
