// L882: .docx export (read back as XML), Format on a large file, list chords
// on emulated non-US layouts (key and code disagree, as on a real layout).
// BASE=http://127.0.0.1:8856 node hw882.js
const { boot } = require("./lib.js");
const { execFileSync } = require("child_process");
const path = require("path"), fs = require("fs"), os = require("os");
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`); };
(async () => {
  const { browser, ctx, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: "block" });
  await page.waitForTimeout(1500);
  const dc = page.locator(".confirm-overlay button", { hasText: "Don't check" });
  if (await dc.count()) await dc.first().click();
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  const open = async (title, ft, content) => {
    await page.evaluate(async ([t, f, c]) => {
      const body = { title: t, content: c }; if (f) body.file_type = f;
      const d = await apiJson("/documents", { method: "POST", body: JSON.stringify(body) });
      await loadDocuments(d.id);
    }, [title, ft, content]);
    await page.waitForTimeout(1500);
  };

  // ---- A: docx export ----
  const md = ["# Quarterly report", "", "Intro with **bold**, *italic* and a [link](https://example.com).", "", "- one", "  - nested", "    - deeper", "- two", "", "1. first", "2. second", "", "| a | b |", "| - | - |", "| 1 | 2 |", "", "```js", "const x = 1;", "```", "", "> quoted", "", "Ünïcödé & <angle> \"quotes\"", ""].join("\n");
  await open("Word check", null, md);
  await page.evaluate(() => { window.__saved = null; window.__name = null; saveFile = async (name, blob) => { window.__saved = blob; window.__name = name; return true; }; });
  const exp = await page.evaluate(async () => { const r = await exportDocumentDocx(); await new Promise((r) => setTimeout(r, 500)); return { r, name: window.__name, size: window.__saved && window.__saved.size }; });
  ok("docx export saved a file", !!exp.size && /\.docx$/.test(exp.name || ""), JSON.stringify(exp));
  const b64 = await page.evaluate(async () => { const buf = new Uint8Array(await window.__saved.arrayBuffer()); let s = ""; for (const x of buf) s += String.fromCharCode(x); return btoa(s); });
  const file = path.join(os.tmpdir(), `hw882-${process.pid}.docx`);
  fs.writeFileSync(file, Buffer.from(b64, "base64"));
  const py = path.resolve(__dirname, "..", "..", ".venv", "bin", "python");
  const out = JSON.parse(execFileSync(py, ["-I", "-c", `
import json, re, sys, zipfile
from xml.dom import minidom
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
res = {"names": names, "bad_zip": z.testzip()}
parsed = {}
for n in names:
    if n.endswith(".xml") or n.endswith(".rels"):
        try: minidom.parseString(z.read(n)); parsed[n] = True
        except Exception as e: parsed[n] = str(e)[:80]
res["xml_errors"] = {k: v for k, v in parsed.items() if v is not True}
x = z.read("word/document.xml").decode()
res["ilvl"] = sorted(set(re.findall(r'<w:ilvl w:val="(\\d)"', x)))
res["tbl"] = x.count("<w:tbl>")
res["bold"] = bool(re.search(r"<w:b/>", x))
res["hyperlink"] = x.count("<w:hyperlink")
res["unicode"] = "Ünïcödé &amp; &lt;angle&gt;" in x
res["has_content_types"] = "[Content_Types].xml" in names
print(json.dumps(res))
`, file], { encoding: "utf8" }));
  // Round trip: python-docx (system python) and LibreOffice headless read the same file back.
  let rt = {};
  try {
    rt = JSON.parse(execFileSync("python3", ["-I", "-c", `
import json, sys, docx
d = docx.Document(sys.argv[1])
ps = d.paragraphs
print(json.dumps({"paras": len(ps), "title": ps[0].text, "styles": sorted({p.style.name for p in ps})[:8], "tables": len(d.tables), "cell": d.tables[0].cell(1, 1).text if d.tables else None, "bold_runs": sum(1 for p in ps for r in p.runs if r.bold), "text": " | ".join(p.text for p in ps)[:400]}))
`, file], { encoding: "utf8" }));
  } catch (e) { rt = { err: String(e.message).slice(0, 120) }; }
  ok("python-docx opens it: title, a 2x2 table, bold runs", rt.title === "Quarterly report" && rt.tables === 1 && rt.cell === "2" && rt.bold_runs >= 1, JSON.stringify(rt).slice(0, 300));
  let lo = "";
  try {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "hw882lo-"));
    execFileSync("soffice", ["--headless", "--convert-to", "txt:Text (encoded):UTF8", "--outdir", dir, file], { encoding: "utf8", timeout: 90000, env: { ...process.env, HOME: dir } });
    lo = fs.readFileSync(path.join(dir, path.basename(file, ".docx") + ".txt"), "utf8");
  } catch (e) { lo = "ERR " + String(e.message).slice(0, 100); }
  ok("LibreOffice converts it and the text survives", /Quarterly report/.test(lo) && /Ünïcödé & <angle>/.test(lo) && /nested/.test(lo) && /deeper/.test(lo), JSON.stringify(lo.slice(0, 200)));
  fs.unlinkSync(file);
  ok("docx is a valid zip with every XML part well-formed", out.bad_zip === null && Object.keys(out.xml_errors).length === 0 && out.has_content_types, JSON.stringify({ parts: out.names.length, err: out.xml_errors }));
  ok("docx holds list levels 0-2, a table, bold, a link, escaped unicode", out.ilvl.includes("0") && out.ilvl.includes("1") && out.ilvl.includes("2") && out.tbl === 1 && out.bold && out.hyperlink >= 1 && out.unicode, JSON.stringify({ ilvl: out.ilvl, tbl: out.tbl, link: out.hyperlink, uni: out.unicode }));
  const gone = await page.evaluate(async () => { const id = currentDoc.id; const r = await fetch(`/documents/${id}/export.docx`, { credentials: "same-origin" }); return r.status; });
  ok("the old server-side export.docx route is gone (extra removed)", gone === 404 || gone === 405, "status " + gone);

  // ---- B: Format on a large file ----
  const rows = [];
  for (let i = 0; i < 4000; i++) rows.push(`function f${i}(a,b){if(a>b){return a+${i}}else{return [a,b,{k:${i},v:"x"}]}}`);
  await open("big.js", "js", rows.join("\n"));
  await page.evaluate(() => { window.__long = []; try { new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__long.push(Math.round(e.duration)))).observe({ entryTypes: ["longtask"] }); } catch (e) {} });
  const f1 = await page.evaluate(async () => { const t0 = performance.now(); const r = await docFormatCode("document"); return { r, ms: Math.round(performance.now() - t0), lines: docCmView.state.doc.lines, long: window.__long.slice() }; });
  ok("Format on 4000 one-line functions re-indents the file", f1.r === true && f1.lines > 20000, JSON.stringify({ lines: f1.lines, ms: f1.ms, longTasks: f1.long }));
  ok("Format finishes in under 8 s", f1.ms < 8000, f1.ms + " ms; longest task " + Math.max(0, ...f1.long));
  await page.evaluate(() => docCmView.focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(400);
  const lines2 = await page.evaluate(() => docCmView.state.doc.lines);
  ok("one undo restores the unformatted file", lines2 === 4000, "lines " + lines2);
  const f2 = await page.evaluate(async () => { const t0 = performance.now(); const r = await docFormatCode("document"); return { r, ms: Math.round(performance.now() - t0) }; });
  ok("Format again after undo works", f2.r === true, f2.ms + " ms");
  // big JSON
  await open("big.json", "json", JSON.stringify(Array.from({ length: 6000 }, (_, i) => ({ id: i, name: "n" + i, tags: ["a", "b"] }))));
  const f3 = await page.evaluate(async () => { const t0 = performance.now(); const r = await docFormatCode("document"); return { r, ms: Math.round(performance.now() - t0), lines: docCmView.state.doc.lines }; });
  ok("Format on a 6000-object JSON file", f3.r === true && f3.lines > 30000 && f3.ms < 8000, JSON.stringify(f3));

  // ---- C: list chords on emulated layouts ----
  await open("Chords", null, "alpha");
  const cdp = await ctx.newCDPSession(page);
  const send = async (spec) => {
    const mods = (spec.ctrl ? 2 : 0) | (spec.shift ? 8 : 0) | (spec.alt ? 1 : 0);
    const base = { modifiers: mods, key: spec.key, code: spec.code, windowsVirtualKeyCode: spec.vk, nativeVirtualKeyCode: spec.vk };
    await cdp.send("Input.dispatchKeyEvent", { type: "rawKeyDown", ...base });
    await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", ...base });
  };
  const reset = async (text) => {
    await page.evaluate((t) => { docCmView.dispatch({ changes: { from: 0, to: docCmView.state.doc.length, insert: t }, selection: { anchor: 0 } }); docCmView.focus(); }, text);
    await page.waitForTimeout(150);
  };
  const doc = () => page.evaluate(() => docCmView.state.doc.toString());
  const layouts = [
    ["US Ctrl+Shift+8", { ctrl: 1, shift: 1, key: "*", code: "Digit8", vk: 56 }, /^- alpha/],
    ["German Ctrl+Shift+8 (key is open paren)", { ctrl: 1, shift: 1, key: "(", code: "Digit8", vk: 56 }, /^- alpha/],
    ["French AZERTY Ctrl+Shift+8 (key is 8)", { ctrl: 1, shift: 1, key: "8", code: "Digit8", vk: 56 }, /^- alpha/],
    ["US Ctrl+Shift+7", { ctrl: 1, shift: 1, key: "&", code: "Digit7", vk: 55 }, /^1\. alpha/],
    ["German Ctrl+Shift+7 (key is slash)", { ctrl: 1, shift: 1, key: "/", code: "Digit7", vk: 55 }, /^1\. alpha/],
    ["US Ctrl+Shift+9", { ctrl: 1, shift: 1, key: "(", code: "Digit9", vk: 57 }, /^- \[ \] alpha/],
    ["German Ctrl+Shift+9 (key is close paren)", { ctrl: 1, shift: 1, key: ")", code: "Digit9", vk: 57 }, /^- \[ \] alpha/],
    ["Dvorak Ctrl+B (code KeyN)", { ctrl: 1, key: "b", code: "KeyN", vk: 66 }, /^\*\*bold text\*\*|\*\*alpha\*\*/],
    ["Russian Ctrl+B (key is a Cyrillic letter)", { ctrl: 1, key: "и", code: "KeyB", vk: 66 }, /^\*\*bold text\*\*|\*\*alpha\*\*/],
  ];
  for (const [name, spec, want] of layouts) {
    await reset("alpha");
    if (/Ctrl\+B/.test(name)) await page.evaluate(() => docCmView.dispatch({ selection: { anchor: 0, head: 5 } }));
    await send(spec);
    await page.waitForTimeout(150);
    const d = await doc();
    ok("chord: " + name, want.test(d), JSON.stringify(d.slice(0, 30)));
  }
  console.log(bad ? `FAILED ${bad}` : "ALL PASS");
  await browser.close();
})().catch((e) => { console.log("ERR", e.message); process.exit(1); });
