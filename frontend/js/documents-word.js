// -----------------------------------------------------------------------------
// Word files in the browser: Mammoth reads a .docx, docx writes one
// -----------------------------------------------------------------------------
//
// The owner, 2026-10-10 (INBOX 765, DOCUMENTS_PLAN Phase 7, superseded row):
// Word files are read and written in the browser with Mammoth and docx, both
// vendored under frontend/vendor with their notices in THIRD_PARTY.md. This
// replaces the python-docx export (an optional extra most installs lacked, so
// Download as Word answered 501) and, for a .docx brought into the Library,
// the server's text extraction, which kept the words and lost the headings,
// lists, emphasis and tables.
//
// Loaded on demand, never at boot and never with the Library: the two
// libraries are 100 KB and 140 KB gzipped, paid only by a Word import or
// export. Everything here waits on `docWordLibs` first.

const DOC_WORD_LIBS = {
  mammoth: "/vendor/mammoth/mammoth.browser.min.js",
  docx: "/vendor/docx/docx.min.js",
};

async function docWordLib(name) {
  if (window[name]) return window[name];
  const loaded = await lazyScript(DOC_WORD_LIBS[name]);
  if (!loaded || !window[name]) throw new Error(`The Word ${name === "docx" ? "writer" : "reader"} could not be loaded.`);
  return window[name];
}

//: Word's paragraph styles that mean a code block: the one this writer uses
//: (`DOC_WORD_CODE_STYLE`) and the two Word and pandoc write. Mammoth turns
//: each run of them into one `<pre>`, which the paste converter fences.
const DOC_WORD_CODE_STYLE = "Code";
//: A fenced block's language rides in its style's name, "Code js" (OPEN
//: 1097): Word shows it in the styles list, and the import maps each one to
//: `pre.language-js`, which the paste converter fences as ```js. A style map
//: cannot match a pattern, so the languages are a list; any other language
//: is written in plain "Code" and comes back as a bare fence, as before.
const DOC_WORD_CODE_LANGS = [
  "bash", "c", "cpp", "cs", "css", "diff", "go", "html", "java", "js", "json", "jsx", "kotlin", "lua",
  "md", "mermaid", "php", "py", "python", "r", "rb", "ruby", "rust", "sh", "shell", "sql", "swift",
  "text", "toml", "ts", "tsx", "xml", "yaml", "yml",
];
const DOC_WORD_STYLE_MAP = [
  ...DOC_WORD_CODE_LANGS.map((lang) => `p[style-name='${DOC_WORD_CODE_STYLE} ${lang}'] => pre.language-${lang}:separator('\\n')`),
  "p[style-name='Code'] => pre:separator('\\n')",
  "p[style-name='Source Code'] => pre:separator('\\n')",
  "p[style-name='HTML Preformatted'] => pre:separator('\\n')",
];

//: The language a rendered block was fenced with, when the list has it.
function docWordCodeLang(pre) {
  const code = pre.querySelector("code");
  const named = code?.getAttribute("data-lang") || (/(?:^|\s)language-([\w+#-]+)/.exec(`${pre.className} ${code?.className || ""}`) || [])[1] || "";
  const lang = named.toLowerCase();
  return DOC_WORD_CODE_LANGS.includes(lang) ? lang : "";
}

//: A picture inside the .docx goes to the media store, as a pasted one
//: does, so the imported document links it rather than losing it (the
//: paste converter keeps only same-origin addresses, never `data:`).
async function docWordUploadPicture(image) {
  try {
    const bytes = image.readAsArrayBuffer ? await image.readAsArrayBuffer() : await image.read();
    const type = image.contentType || "image/png";
    const ext = (type.split("/")[1] || "png").replace("jpeg", "jpg").replace(/[^a-z0-9]/g, "") || "png";
    const form = new FormData();
    form.append("file", new File([bytes], `word-picture.${ext}`, { type }));
    const uploaded = await apiJson("/media/upload", { method: "POST", headers: authHeaders(), body: form });
    return uploaded && uploaded.url ? { src: uploaded.url } : { src: "" };
  } catch {
    return { src: "" };
  }
}

//: **A .docx with tracked changes goes to the server's reader** (OPEN 1096).
//: Mammoth takes an insertion as written and drops a deletion, accepting a
//: reviewer's changes on the reader's behalf; `docview.docx_to_markdown`
//: keeps them as suggestion mode's marks to accept or reject. So the import
//: looks first: the zip's central directory, then `word/document.xml`
//: inflated by the browser's own `DecompressionStream`, for a `w:ins` or a
//: `w:del` (the server's `docx_has_revisions` asks the same). Anything it
//: cannot read is "no revisions", which is the old path.
async function docWordHasRevisions(file) {
  try {
    const buf = new Uint8Array(await file.arrayBuffer());
    const view = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
    let end = -1;
    for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i -= 1) {
      if (view.getUint32(i, true) === 0x06054b50) {
        end = i;
        break;
      }
    }
    if (end < 0) return false;
    const names = new TextDecoder();
    let at = view.getUint32(end + 16, true);
    for (let n = view.getUint16(end + 10, true); n > 0; n -= 1) {
      if (view.getUint32(at, true) !== 0x02014b50) return false;
      const method = view.getUint16(at + 10, true);
      const size = view.getUint32(at + 20, true);
      const nameLength = view.getUint16(at + 28, true);
      const name = names.decode(buf.subarray(at + 46, at + 46 + nameLength));
      if (name === "word/document.xml") {
        const local = view.getUint32(at + 42, true);
        const start = local + 30 + view.getUint16(local + 26, true) + view.getUint16(local + 28, true);
        const data = buf.subarray(start, start + size);
        const xml = method === 0
          ? names.decode(data)
          : await new Response(new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"))).text();
        return /<w:(?:ins|del)[\s>]/.test(xml);
      }
      at += 46 + nameLength + view.getUint16(at + 30, true) + view.getUint16(at + 32, true);
    }
  } catch {
    return false;
  }
  return false;
}

//: A .docx to a title and markdown: Mammoth's HTML (headings, nested lists,
//: emphasis, tables, links, code blocks, pictures) through the editor's own
//: paste converter, so an import reads as a paste of the same page does.
async function docWordImport(file) {
  const mammoth = await docWordLib("mammoth");
  const result = await mammoth.convertToHtml(
    { arrayBuffer: await file.arrayBuffer() },
    { styleMap: DOC_WORD_STYLE_MAP, convertImage: mammoth.images.imgElement(docWordUploadPicture) },
  );
  const content = docHtmlToMarkdown(result.value || "");
  const title = String(file.name || "Imported document").replace(/\.docx$/i, "").trim() || "Imported document";
  return { title, content, warnings: (result.messages || []).length };
}

//: Suggestion mode's marks (`{++…++}`, `{--…--}`) as private-use characters
//: the renderer passes through untouched, so the walk below can write them
//: as Word's own tracked changes rather than as braces. A mark may span
//: blocks, which is why the walk carries its state in `ctx`, not per node.
const DOC_WORD_INS_OPEN = "";
const DOC_WORD_INS_CLOSE = "";
const DOC_WORD_DEL_OPEN = "";
const DOC_WORD_DEL_CLOSE = "";

function docWordMarkSuggestions(text) {
  if (typeof docSuggestParse !== "function") return text;
  let out = text;
  const marks = docSuggestParse(text);
  for (let i = marks.length - 1; i >= 0; i -= 1) {
    const mark = marks[i];
    const [open, close] = mark.kind === "ins" ? [DOC_WORD_INS_OPEN, DOC_WORD_INS_CLOSE] : [DOC_WORD_DEL_OPEN, DOC_WORD_DEL_CLOSE];
    out = out.slice(0, mark.start) + open + mark.body + close + out.slice(mark.end);
  }
  return out;
}

//: The width a picture asked for (`![alt|300](src)`, the editor's own
//: option), else its own, never wider than the page's text (6.27 in).
const DOC_WORD_PAGE_PX = 600;

async function docWordPicture(img) {
  const src = img.getAttribute("src") || "";
  //: Only this notebook's own pictures: the app is offline, and the page's
  //: CSP would refuse anything else anyway.
  if (!/^(\/(media|files)\/|blob:|data:image\/)/.test(src)) return null;
  try {
    //: The notebook's own pictures go through the one door; a `blob:` or
    //: `data:` address is this tab's, not a request.
    const response = src.startsWith("/") ? await api(src) : await fetch(src);
    if (!response.ok) return null;
    let blob = await response.blob();
    const bitmap = await createImageBitmap(blob);
    let type = { "image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/bmp": "bmp" }[blob.type];
    if (!type) {
      //: Word reads PNG, JPEG, GIF and BMP; anything else (WebP) is redrawn.
      const canvas = document.createElement("canvas");
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      canvas.getContext("2d").drawImage(bitmap, 0, 0);
      blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
      if (!blob) return null;
      type = "png";
    }
    const asked = Number((/\|(\d{1,4})\s*$/.exec(img.getAttribute("alt") || "") || [])[1]) || 0;
    const width = Math.max(1, Math.min(DOC_WORD_PAGE_PX, asked || bitmap.width));
    const height = Math.max(1, Math.round((bitmap.height * width) / Math.max(1, bitmap.width)));
    return { type, data: await blob.arrayBuffer(), width, height };
  } catch {
    return null;
  }
}

//: The open document to a .docx: the markdown rendered by the app's own
//: renderer, then walked into docx's paragraphs, so a heading, a list or a
//: table means in Word what it means on screen.
async function docWordBlob(D, title, text) {
  const marked = docWordMarkSuggestions(text);
  const holder = document.createElement("div");
  renderMarkdown(holder, marked);
  //: The renderer's own chrome is not the document: a code block's and a
  //: table's bar (its label, Copy, Save) would be written as text.
  for (const chrome of holder.querySelectorAll(".code-bar, button")) chrome.remove();
  const pictures = new Map();
  for (const img of holder.querySelectorAll("img")) {
    const picture = await docWordPicture(img);
    if (picture) pictures.set(img, picture);
  }
  const ctx = { mode: "", revision: 1, date: new Date().toISOString(), pictures, lists: 0, lines: marked.split("\n"), langs: new Set() };
  const children = docWordBlocks(D, holder, 0, ctx);
  const levels = Array.from({ length: 9 }, (_, level) => ({
    level,
    format: D.LevelFormat.DECIMAL,
    text: `%${level + 1}.`,
    alignment: D.AlignmentType.START,
    style: { paragraph: { indent: { left: 720 * (level + 1), hanging: 360 } } },
  }));
  const doc = new D.Document({
    creator: "Tessellate",
    title: title || "Document",
    styles: {
      paragraphStyles: [
        { id: DOC_WORD_CODE_STYLE, name: DOC_WORD_CODE_STYLE, basedOn: "Normal", run: { font: "Consolas" }, paragraph: { spacing: { before: 0, after: 0 } } },
        ...[...ctx.langs].map((lang) => ({ id: `${DOC_WORD_CODE_STYLE}-${lang}`, name: `${DOC_WORD_CODE_STYLE} ${lang}`, basedOn: DOC_WORD_CODE_STYLE })),
      ],
    },
    numbering: { config: [{ reference: "mm-numbered", levels }] },
    sections: [{ children: children.length ? children : [new D.Paragraph("")] }],
  });
  return D.Packer.toBlob(doc);
}

async function docWordExport() {
  if (!currentDoc) return false;
  try {
    const D = await docWordLib("docx");
    const blob = await docWordBlob(D, currentDoc.title, docCmView ? docStr(docCmView.state.doc) : currentDoc.content || "");
    await saveFile(docExportName(currentDoc.title, "docx"), blob);
    return true;
  } catch (error) {
    toast(`Could not write the Word file: ${error.message}`, true);
    return false;
  }
}

//: A text node's words, split where a suggestion opens or closes.
function docWordText(D, text, style, ctx) {
  const runs = [];
  for (const piece of text.split(/([-])/)) {
    if (piece === DOC_WORD_INS_OPEN) ctx.mode = "ins";
    else if (piece === DOC_WORD_DEL_OPEN) ctx.mode = "del";
    else if (piece === DOC_WORD_INS_CLOSE || piece === DOC_WORD_DEL_CLOSE) ctx.mode = "";
    else if (piece && !ctx.mode) runs.push(new D.TextRun({ text: piece, ...style }));
    else if (piece) {
      const Run = ctx.mode === "ins" ? D.InsertedTextRun : D.DeletedTextRun;
      runs.push(new Run({ text: piece, id: ctx.revision, author: "Tessellate", date: ctx.date, ...style }));
      ctx.revision += 1;
    }
  }
  return runs;
}

function docWordRuns(D, node, style = {}, ctx = { mode: "", revision: 1, date: new Date().toISOString(), pictures: new Map() }) {
  const runs = [];
  for (const child of node.childNodes) {
    if (child.nodeType === 3) {
      if (child.nodeValue) runs.push(...docWordText(D, child.nodeValue, style, ctx));
      continue;
    }
    if (child.nodeType !== 1) continue;
    const tag = child.tagName.toLowerCase();
    if (tag === "br") runs.push(new D.TextRun({ text: "", break: 1 }));
    else if (tag === "strong" || tag === "b") runs.push(...docWordRuns(D, child, { ...style, bold: true }, ctx));
    else if (tag === "em" || tag === "i") runs.push(...docWordRuns(D, child, { ...style, italics: true }, ctx));
    else if (tag === "del" || tag === "s") runs.push(...docWordRuns(D, child, { ...style, strike: true }, ctx));
    else if (tag === "code") runs.push(...docWordRuns(D, child, { ...style, font: "Consolas" }, ctx));
    else if (tag === "img") {
      const alt = (child.getAttribute("alt") || "").replace(/\|.*$/, "").trim();
      const picture = ctx.pictures.get(child);
      runs.push(picture
        ? new D.ImageRun({ type: picture.type, data: picture.data, transformation: { width: picture.width, height: picture.height }, altText: { name: alt || "picture", title: alt, description: alt } })
        : new D.TextRun({ text: `[${alt || "picture"}]`, ...style }));
    } else if (tag === "a" && /^(https?:|mailto:)/i.test(child.getAttribute("href") || "")) {
      runs.push(new D.ExternalHyperlink({ link: child.getAttribute("href"), children: docWordRuns(D, child, { ...style, style: "Hyperlink" }, ctx) }));
    } else runs.push(...docWordRuns(D, child, style, ctx));
  }
  return runs;
}

//: Each item's level and kind, from the list's source lines: an item is a
//: line with a marker, its level the depth of its indent among the indents
//: above it. Null when the lines do not account for every item (a list
//: inside a callout, whose lines are numbered from the callout).
function docWordListShape(lines, start, count) {
  if (!Array.isArray(lines) || !Number.isInteger(start) || start < 0) return null;
  const shape = [];
  const indents = [];
  for (let i = start; i < lines.length && shape.length < count; i += 1) {
    const match = /^(\s*)([-*+]|\d+[.)])\s/.exec(lines[i]);
    if (!match) continue;
    const indent = match[1].replace(/\t/g, "    ").length;
    while (indents.length && indent < indents[indents.length - 1]) indents.pop();
    if (!indents.length || indent > indents[indents.length - 1]) indents.push(indent);
    shape.push({ level: indents.length - 1, ordered: /\d/.test(match[2]) });
  }
  return shape.length === count ? shape : null;
}

const DOC_WORD_HEADINGS = { h1: "HEADING_1", h2: "HEADING_2", h3: "HEADING_3", h4: "HEADING_4", h5: "HEADING_5", h6: "HEADING_6" };

function docWordBlocks(D, root, depth, ctx, instance = 0) {
  const out = [];
  for (const el of root.children) {
    //: The renderer draws `#` as an h3 for the page's scale and says the
    //: level the text wrote in its class (`md-h1`); Word wants that level.
    const level = /(?:^|\s)md-h([1-6])(?:\s|$)/.exec(el.className || "");
    const tag = level ? `h${level[1]}` : el.tagName.toLowerCase();
    if (DOC_WORD_HEADINGS[tag]) out.push(new D.Paragraph({ heading: D.HeadingLevel[DOC_WORD_HEADINGS[tag]], children: docWordRuns(D, el, {}, ctx) }));
    else if (tag === "p") out.push(new D.Paragraph({ children: docWordRuns(D, el, {}, ctx) }));
    else if (tag === "hr") out.push(new D.Paragraph({ thematicBreak: true, children: [] }));
    else if (tag === "pre") {
      //: One paragraph per line in the code style, so Word keeps the lines
      //: and the import (`DOC_WORD_STYLE_MAP`) reads them back as one block.
      const lang = docWordCodeLang(el);
      if (lang) ctx.langs.add(lang);
      const style = lang ? `${DOC_WORD_CODE_STYLE}-${lang}` : DOC_WORD_CODE_STYLE;
      for (const line of el.textContent.replace(/\n$/, "").split("\n")) {
        out.push(new D.Paragraph({ style, children: [new D.TextRun({ text: line })] }));
      }
    } else if (tag === "blockquote") {
      for (const p of docWordBlocks(D, el, depth, ctx, instance)) out.push(p);
    } else if (tag === "ul" || tag === "ol") {
      //: Word's own lists (bullets, and numbering that restarts per list),
      //: so a nested item is a level in Word and comes back nested. The
      //: renderer draws a nested list flat, so each item's level and kind
      //: are read from its own source line (`docWordListShape`).
      const items = [...el.children].filter((li) => li.tagName.toLowerCase() === "li");
      const shape = docWordListShape(ctx.lines, Number(el.getAttribute("data-src-line")), items.length);
      const own = tag === "ol" || (shape && shape.some((item) => item.ordered)) ? instance || (ctx.lists += 1) : instance;
      items.forEach((li, index) => {
        const holder = document.createElement("div");
        const nested = [];
        for (const part of li.childNodes) {
          if (part.nodeType === 1 && /^(ul|ol)$/i.test(part.tagName)) nested.push(part);
          else holder.append(part.cloneNode(true));
        }
        const runs = docWordRuns(D, holder, {}, ctx);
        const item = shape ? shape[index] : { level: 0, ordered: tag === "ol" };
        const lvl = Math.min(depth + item.level, 8);
        out.push(item.ordered
          ? new D.Paragraph({ numbering: { reference: "mm-numbered", level: lvl, instance: own }, children: runs })
          : new D.Paragraph({ bullet: { level: lvl }, children: runs }));
        for (const list of nested) {
          const wrap = document.createElement("div");
          wrap.append(list.cloneNode(true));
          out.push(...docWordBlocks(D, wrap, lvl + 1, ctx, own));
        }
      });
    } else if (tag === "table") {
      const rows = [...el.querySelectorAll("tr")].map((tr) => new D.TableRow({
        children: [...tr.children].map((cell) => new D.TableCell({ children: [new D.Paragraph({ children: docWordRuns(D, cell, cell.tagName === "TH" ? { bold: true } : {}, ctx) })] })),
      }));
      if (rows.length) out.push(new D.Table({ rows }));
    } else if (el.querySelector("p, h1, h2, h3, h4, ul, ol, table, pre")) {
      //: A wrapper the renderer adds (a callout, a column): its blocks.
      out.push(...docWordBlocks(D, el, depth, ctx, instance));
    } else if (el.textContent.trim() || el.querySelector("img")) {
      out.push(new D.Paragraph({ children: docWordRuns(D, el, {}, ctx) }));
    }
  }
  return out;
}
