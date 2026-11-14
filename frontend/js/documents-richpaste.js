// documents-richpaste.js: rich paste: HTML from a page, Word or Google Docs as Markdown.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  const DOC_RICH_TAGS = /<(h[1-6]|strong|b|em|i|a\s[^>]*href|ul|ol|blockquote|pre|code|img|table|del|s)[\s>]|<p[^>]*>(?:\s|&nbsp;)*[·•▪§Ø](?:\s|&nbsp;)|MsoList|mso-list/i;
  const DOC_RICH_STYLE = /font-weight\s*:\s*(bold|bolder|[6-9]00)\b|font-style\s*:\s*italic/i;
  const DOC_CODE_HTML = /white-space\s*:\s*pre|font-family\s*:[^;"]*(mono|consolas|courier|menlo)/i;
  function docHtmlIsRich(html) {
    return DOC_RICH_TAGS.test(html) || (DOC_RICH_STYLE.test(html) && !DOC_CODE_HTML.test(html));
  }
  function docWordListLine(el, styleOf, inline) {
    const style = styleOf(el, "mso-list");
    //: **A list paragraph with its `mso-list` style stripped is still a list**
    //: (DX32, audit 1102): Word for the web, Outlook and a copy through another
    //: editor keep the `MsoListParagraph` class or only the bullet glyph, and
    //: "· item" arrived as a paragraph starting with a middle dot. One rule for
    //: both: the style, the class, or a leading glyph (`·`, `•`, `▪`, `§`, or
    //: Word's "o" set apart by two spaces) makes the paragraph an item.
    const glyph = /^[\s\u00a0]*(?:[·•▪◦‣§Ø]|o(?=[\s\u00a0]{2}))[\s\u00a0]+\S/.test(el.textContent);
    const styled = Boolean(style) && style !== "none";
    if (!styled && !glyph && !/MsoList/i.test(el.getAttribute("class") || "")) return "";
    const list = styled ? style : "";
    //: Without the style the depth is the indent: Word steps a level by half an inch.
    const inches = Number(/(\d*\.?\d+)in/.exec(styleOf(el, "margin-left"))?.[1] || 0);
    const level = Number(/level(\d+)/.exec(list)?.[1] || (inches ? Math.round(inches / 0.5) : 1));
    //: The marker span is nested (`<span Symbol><span mso-list:Ignore>`), so it
    //: is found by its style wherever it sits, read, and taken out.
    const marks = [...el.querySelectorAll("[data-mm-style]")].filter((c) => styleOf(c, "mso-list") === "ignore");
    const mark = marks.map((c) => c.textContent).join("");
    marks.forEach((c) => c.remove());
    const number = /^\s*(\d+)[.)]/.exec(mark)?.[1] || (/^\s*[a-z]{1,4}[.)]/i.test(mark) ? "1" : "");
    let text = [...el.childNodes].map(inline).join("").replace(/\s+/g, " ").trim();
    //: The glyph itself, when it was text rather than a marker span.
    if (glyph && !marks.length) text = text.replace(/^(?:[·•▪◦‣§Ø]|o)\s+/, "");
    return text ? `${"  ".repeat(Math.max(0, level - 1))}${number ? `${number}.` : "-"} ${text}` : "";
  }
  function docHtmlToMarkdown(html) {
    //: `style` renamed before parsing: the page's CSP refuses an inline style
    //: even in a parsed, inert document (a console error per attribute, and
    //: the value never reaches `el.style`), and the two it matters for are
    //: read from the text below.
    //: A `<style>` block goes too (Word opens every copy with one): an inline style element is refused
    //: by the CSP the same way, and its rules would style nothing in an inert document anyway (L890).
    const source = String(html || "").replace(/<style[\s\S]*?<\/style\s*>/gi, "").replace(/(<[^>]*?\s)style\s*=/gi, "$1data-mm-style=");
    const doc = new DOMParser().parseFromString(source, "text/html");
    const safeUrl = (url) => {
      const value = String(url || "").trim();
      const ok = /^(https?:|mailto:)/i.test(value) || (value.startsWith("/") && !value.startsWith("//"));
      //: Encoded: a ")" ended the Markdown link early (audit 1028 D16).
      return ok ? value.replace(/[\s()<>]/g, (c) => encodeURIComponent(c)) : "";
    };
    //: Google Docs wraps a whole copy in `<b style="font-weight:normal">`, and
    //: marks real bold and italic on spans by style rather than by tag.
    const styleOf = (el, prop) => {
      const m = new RegExp(`(?:^|;)\\s*${prop}\\s*:\\s*([^;]+)`, "i").exec(el.getAttribute("data-mm-style") || "");
      return m ? m[1].trim().toLowerCase() : "";
    };
    const isBold = (el) => {
      const tag = el.nodeName;
      const weight = styleOf(el, "font-weight");
      if (tag === "STRONG" || tag === "B") return !/^(normal|[1-5]00)$/.test(weight);
      return /^(bold|bolder|[6-9]00)$/.test(weight);
    };
    const isItalic = (el) => el.nodeName === "EM" || el.nodeName === "I" || styleOf(el, "font-style") === "italic";
    const inline = (node) => {
      if (node.nodeType === 3) return node.nodeValue.replace(/\s+/g, " ");
      if (node.nodeType !== 1) return "";
      const tag = node.nodeName;
      if (/^(SCRIPT|STYLE|META|TITLE|HEAD|TEMPLATE)$/.test(tag)) return "";
      if (tag === "BR") return "\n";
      if (tag === "IMG") {
        const src = safeUrl(node.getAttribute("src"));
        return src ? `![${(node.getAttribute("alt") || "").replace(/[[\]|]/g, "")}](${src})` : "";
      }
      let text = [...node.childNodes].map(inline).join("");
      if (tag === "CODE") return text.trim() ? `\`${text.replace(/`/g, "")}\`` : "";
      const wrap = (mark) => {
        const lead = text.match(/^\s*/)[0];
        const tail = text.match(/\s*$/)[0];
        const core = text.trim();
        return core ? `${lead}${mark}${core}${mark}${tail}` : text;
      };
      if (isBold(node)) text = wrap("**");
      if (isItalic(node)) text = wrap("*");
      if (tag === "DEL" || tag === "S" || tag === "STRIKE") text = wrap("~~");
      if (tag === "A") {
        const href = safeUrl(node.getAttribute("href"));
        const label = text.trim();
        if (href && label) return `[${label.replace(/[[\]]/g, "")}](${href})`;
      }
      return text;
    };
    const out = [];
    const para = (text) => {
      const clean = text.replace(/[ \t]+\n/g, "\n").replace(/\n[ \t]+/g, "\n").trim();
      if (clean) out.push(clean);
    };
    const BLOCK = /^(P|DIV|H[1-6]|UL|OL|LI|BLOCKQUOTE|PRE|TABLE|SECTION|ARTICLE|HEADER|FOOTER|MAIN|ASIDE|FIGURE|FIGCAPTION|HR|DL|DT|DD|BODY|HTML)$/;
    const list = (el, depth) => {
      let n = 0;
      for (const li of el.children) {
        if (li.nodeName !== "LI") continue;
        n += 1;
        const marker = el.nodeName === "OL" ? `${n}.` : "-";
        const own = [...li.childNodes].filter((c) => !(c.nodeType === 1 && /^(UL|OL)$/.test(c.nodeName)));
        const text = own.map(inline).join("").replace(/\s+/g, " ").trim();
        out.push(`${"  ".repeat(depth)}${marker} ${text}`);
        for (const sub of li.children) if (/^(UL|OL)$/.test(sub.nodeName)) list(sub, depth + 1);
      }
    };
    let wordRun = -1;
    const block = (el) => {
      let run = "";
      const flush = () => {
        para(run);
        run = "";
      };
      for (const child of el.childNodes) {
        const tag = child.nodeType === 1 ? child.nodeName : "";
        //: An inline wrapper round whole blocks (Google Docs' outer `<b>`) is
        //: walked as a container, or its paragraphs and lists would run together.
        if (tag && !BLOCK.test(tag) && child.querySelector("p, div, h1, h2, h3, h4, h5, h6, ul, ol, blockquote, pre, table")) {
          flush();
          block(child);
          continue;
        }
        if (!tag || !BLOCK.test(tag)) {
          run += inline(child);
          continue;
        }
        flush();
        const wordItem = tag === "P" ? docWordListLine(child, styleOf, inline) : "";
        const heading = /^H([1-6])$/.exec(tag);
        if (wordItem) {
          //: Word's list paragraphs run together as one tight list.
          //: `wordRun >= 0`: with nothing before it both sides were -1, and a list at the very start of a paste was appended to `out[-1]`, a property, and lost (DX32).
          if (wordRun >= 0 && wordRun === out.length - 1) out[wordRun] += `\n${wordItem}`;
          else {
            out.push(wordItem);
            wordRun = out.length - 1;
          }
        } else if (heading) {
          const text = inline(child).replace(/\s+/g, " ").trim();
          if (text) out.push(`${"#".repeat(Number(heading[1]))} ${text}`);
        } else if (tag === "UL" || tag === "OL") {
          const start = out.length;
          list(child, 0);
          //: A list is one block: its items are joined without blank lines.
          out.splice(start, out.length - start, out.slice(start).join("\n"));
        } else if (tag === "BLOCKQUOTE") {
          const inner = docHtmlToMarkdown(child.innerHTML);
          if (inner) out.push(inner.split("\n").map((line) => `> ${line}`.trimEnd()).join("\n"));
        } else if (tag === "PRE") {
          const code = child.textContent.replace(/\n$/, "");
          //: A block's language, when the page names it (`language-js` on the
          //: pre or its code, as GitHub and a Word import write it).
          const inner = child.querySelector("code");
          const lang = (/(?:^|\s)language-([\w+#-]+)/.exec(`${child.className} ${inner?.className || ""}`) || [])[1] || "";
          out.push("```" + lang + "\n" + code + "\n```");
        } else if (tag === "TABLE") {
          const grid = [...child.querySelectorAll("tr")].map((tr) =>
            [...tr.children].map((cell) => inline(cell).replace(/\s+/g, " ").replace(/\|/g, "\\|").trim())
          ).filter((row) => row.length);
          if (grid.length) out.push(docTableFromGrid(grid));
        } else if (tag === "HR") {
          out.push("---");
        } else {
          block(child);
        }
      }
      flush();
    };
    block(doc.body);
    return out.join("\n\n").replace(/\n{3,}/g, "\n\n").trim();
  }
  function docRichPasteEvent(event, view) {
    const plain = docPastePlain;
    docPastePlain = false;
    if (plain || view.dom.classList.contains("doc-content-code")) return false;
    const html = event.clipboardData?.getData("text/html") || "";
    if (!html || !docHtmlIsRich(html)) return false;
    const markdown = docHtmlToMarkdown(html);
    if (!markdown) return false;
    event.preventDefault();
    const sel = view.state.selection.main;
    const doc = view.state.doc;
    //: Padded to start (and end) its own line when it is a block (DX3).
    const insert = docRichPasteEvent.fit(markdown, doc.lineAt(sel.from).text.slice(0, sel.from - doc.lineAt(sel.from).from), doc.lineAt(sel.to).text.slice(sel.to - doc.lineAt(sel.to).from));
    docUndoBreak();
    view.dispatch({
      changes: { from: sel.from, to: sel.to, insert },
      selection: { anchor: sel.from + insert.length },
      userEvent: "input.paste",
      scrollIntoView: true,
    });
    docPasteOfferRich(view, sel.from, insert, event.clipboardData.getData("text/plain"));
    return true;
  }

  //: The file's surface: what other files call (L335).
  Object.assign(window, { docHtmlIsRich, docHtmlToMarkdown, docRichPasteEvent });
})();
