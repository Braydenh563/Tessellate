// Brief 42: Word files in the browser. Download as Word on a document with a
// heading, emphasis, a nested list, a table, a code block, a picture and two
// suggested changes, then the same bytes read back by Mammoth through the
// Library's import path. The .docx's own XML is read by python3's zipfile.
// Usage: BASE=http://127.0.0.1:8846 node docs42d.js
const { boot } = require("./lib.js");
const J = JSON.stringify;
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}  - ${d}`); };
const MD = "# Plan\n\nSome **bold** and *slanted* words with [a link](https://example.com).\n\n- one\n- two\n  - nested\n\n1. first\n2. second\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n```\ncode line\n  indented\n```\n\nA box: ![Red box](PICTURE)\n\nKeep {++new words++} and {--old words--} here.\n";
(async () => {
  const { browser, page } = await boot();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(1500);
  await page.evaluate(async (c) => {
    const canvas = document.createElement("canvas"); canvas.width = 40; canvas.height = 20;
    canvas.getContext("2d").fillRect(0, 0, 40, 20);
    const png = await new Promise((r) => canvas.toBlob(r, "image/png"));
    const form = new FormData(); form.append("file", new File([png], "box.png", { type: "image/png" }));
    const up = await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body: form });
    c = c.replace("PICTURE", up.url);
    const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Word trip", content: c, file_type: "md" }) }); await loadDocuments(d.id); }, MD);
  await page.waitForTimeout(2000);
  const r = await page.evaluate(async () => {
    let saved = null;
    const real = window.saveFile;
    window.saveFile = async (name, blob) => { saved = { name, blob }; };
    const t0 = performance.now();
    await exportDocumentDocx();
    const exportMs = Math.round(performance.now() - t0);
    window.saveFile = real;
    if (!saved) return { saved: false };
    const file = new File([saved.blob], saved.name);
    const t1 = performance.now();
    const back = await docWordImport(file);
    const importMs = Math.round(performance.now() - t1);
    const html = (await mammoth.convertToHtml({ arrayBuffer: await file.arrayBuffer() })).value;
    const raw = new Uint8Array(await saved.blob.arrayBuffer());
    let bin = ""; for (const b of raw) bin += String.fromCharCode(b);
    return { b64: btoa(bin), saved: true, name: saved.name, bytes: saved.blob.size, exportMs, importMs, md: back.content, title: back.title, tags: ["h1", "strong", "em", "ul", "table", "a"].filter((t) => html.includes(`<${t}`)) };
  });
  ok("Download as Word writes a .docx in the browser", r.saved && /\.docx$/.test(r.name) && r.bytes > 2000, J({ name: r.name, bytes: r.bytes, ms: r.exportMs }));
  ok("the heading, emphasis, lists, table and link survive into Word", r.tags && r.tags.length === 6, J(r.tags));
  ok("Mammoth reads it back to markdown the editor keeps", /^# Plan/m.test(r.md || "") && /\*\*bold\*\*/.test(r.md) && /\| \*\*A\*\* \| \*\*B\*\* \|/.test(r.md || "") && /^1\. first/m.test(r.md) && !/Copy/.test(r.md), J({ ms: r.importMs, title: r.title, md: (r.md || "").slice(0, 300) }));
  const tmp = require("os").tmpdir() + "/docs42d.docx";
  require("fs").writeFileSync(tmp, Buffer.from(r.b64 || "", "base64"));
  const xml = JSON.parse(require("child_process").execFileSync("python3", ["-c",
    "import json,re,sys,zipfile;x=zipfile.ZipFile(sys.argv[1]).read('word/document.xml').decode();print(json.dumps({'ins':x.count('<w:ins '),'del':x.count('<w:delText'),'drawing':x.count('<w:drawing>'),'levels':re.findall(r'w:ilvl w:val=\"(\\d)\"',x),'code':x.count('w:val=\"Code\"')}))", tmp]).toString());
  ok("a picture is a Word picture, suggestions are tracked changes, the nested item is level 1", xml.drawing === 1 && xml.ins === 1 && xml.del === 1 && xml.levels.includes("1"), J(xml));
  ok("the import keeps the nested list, the code block and the picture", /^  - nested$/m.test(r.md || "") && /```\ncode line\n  indented\n```/.test(r.md || "") && /!\[Red box\]\(\/media\//.test(r.md || ""), J((r.md || "").slice(-220)));
  // Audit 1102 DX9: structure survives. A diagram, a formula, two tasks, a footnote cited twice and a remote picture.
  const FX = "# Probe\n\nMaths $x^2 + y_1$ and a note[^1] then again[^1].\n\n```mermaid\ngraph TD; A-->B; B-->C\n```\n\n$$\\frac{a}{b} + \\sqrt{x}$$\n\n- [ ] open task\n- [x] done task\n\n![remote](https://example.com/a.png)\n\n[^1]: The footnote text.\n";
  await page.evaluate(async (c) => { const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: "Word structure", content: c, file_type: "md" }) }); await loadDocuments(d.id); }, FX);
  await page.waitForTimeout(2000);
  const b2 = await page.evaluate(async () => {
    let saved = null; const real = window.saveFile; window.saveFile = async (n, b) => { saved = b; };
    await exportDocumentDocx(); window.saveFile = real;
    let bin = ""; for (const v of new Uint8Array(await saved.arrayBuffer())) bin += String.fromCharCode(v); return btoa(bin);
  });
  const tmp2 = require("os").tmpdir() + "/docs42d-structure.docx";
  require("fs").writeFileSync(tmp2, Buffer.from(b2, "base64"));
  const s2 = JSON.parse(require("child_process").execFileSync("python3", ["-c",
    "import json,re,sys,zipfile;z=zipfile.ZipFile(sys.argv[1]);x=z.read('word/document.xml').decode();f=z.read('word/footnotes.xml').decode();print(json.dumps({'fn':x.count('<w:footnoteReference'),'fnBodies':len(re.findall(r'<w:footnote [^>]*w:id=\"[1-9]',f)),'drawing':x.count('<w:drawing'),'omath':len(re.findall(r'<m:oMath[ >]',x)),'frac':x.count('<m:f>'),'back':'Back' in x,'remote':'Remote image' in x,'boxes':[c for c in '\u2610\u2611' if c in x],'src':'A-->B' in x or 'A--&gt;B' in x}))", tmp2]).toString());
  ok("footnotes are Word footnotes (before: 0 references, 0 bodies)", s2.fn === 2 && s2.fnBodies === 2, J(s2));
  ok("the diagram is a picture, not its source (before: 0 drawings, source written)", s2.drawing === 1 && !s2.src, J(s2));
  ok("maths is Word maths (before: 0 oMath)", s2.omath === 2 && s2.frac === 1, J(s2));
  ok("tasks keep state, and no Back or remote-image text (before: no boxes, both texts present)", s2.boxes.length === 2 && !s2.back && !s2.remote, J(s2));
  console.log("errors", J(errors.slice(0, 4)), "bad", bad);
  await browser.close();
})();
