// documents-base.js: the ```base block (DOCUMENTS_PLAN gap row 6, the Obsidian "Bases" ask): a fence of lines is drawn as
// a table of the notes whose properties match. Read-only by decision: the table shows the `---` blocks the notes already
// have (`GET /property-table`, repo/properties.py `table`), and a note's block is changed in the note, so there is one
// place a value is written. The first column opens the note. Only a table: board and calendar views are LEDGER L-documents-52.
//
//   type: Book                one `type:` property
//   where: status = read      any number of these, all must hold (a list property matches any of its values)
//   columns: author, rating   the properties to show, in order
//   sort: rating desc         one property, asc or desc (numbers and dates sort as such)
//   limit: 50                 rows, at most 300
//
// Lazy: `LAZY_MODULES.docBase`, registered in lazy-entries.js; documents-math.js draws Read and Live and calls
// `docMathRender.base.fill`. Everything is a property of `docMathRender.base`, so the file adds no global name.
(() => {
  // DOC-BASE-BEGIN (tests/test_doc_base.py runs this region in node)
  const KEYS = new Set(["type", "where", "columns", "sort", "limit"]);
  const MAX_ROWS = 300;

  //: **`parse(source)`**: `{ type, where: [[key, value]], columns, sort, desc, limit, errors }`, the reasons a line was
  //: not understood being sentences for under the table.
  function parse(source) {
    const model = { type: "", where: [], columns: [], sort: "", desc: false, limit: 100, errors: [] };
    for (const raw of String(source || "").split("\n")) {
      const line = raw.trim();
      if (!line) continue;
      const at = line.indexOf(":");
      const key = at > 0 ? line.slice(0, at).trim().toLowerCase() : "";
      const value = at > 0 ? line.slice(at + 1).trim() : "";
      if (!KEYS.has(key)) {
        model.errors.push(`"${line.slice(0, 40)}" is not a line a base reads. Use type, where, columns, sort or limit.`);
      } else if (key === "type") {
        model.type = value;
      } else if (key === "where") {
        const eq = value.indexOf("=");
        if (eq > 0 && value.slice(0, eq).trim()) model.where.push([value.slice(0, eq).trim(), value.slice(eq + 1).trim()]);
        else model.errors.push(`"where: ${value.slice(0, 30)}" should read property = value.`);
      } else if (key === "columns") {
        model.columns = value.split(",").map((c) => c.trim()).filter(Boolean).slice(0, 12);
      } else if (key === "sort") {
        const m = /^(.*?)(?:\s+(asc|desc))?$/i.exec(value);
        model.sort = (m && m[1] ? m[1] : value).trim();
        model.desc = Boolean(m && m[2] && m[2].toLowerCase() === "desc");
      } else {
        const n = Number.parseInt(value, 10);
        if (n >= 1) model.limit = Math.min(n, MAX_ROWS);
        else model.errors.push(`"limit: ${value.slice(0, 20)}" should be a number of rows.`);
      }
    }
    return model;
  }

  //: The address the table is read from.
  function query(model) {
    const params = new URLSearchParams();
    if (model.type) params.set("type", model.type);
    for (const [k, v] of model.where) params.append("where", `${k}=${v}`);
    if (model.columns.length) params.set("columns", model.columns.join(","));
    if (model.sort) params.set("sort", model.sort);
    if (model.desc) params.set("desc", "true");
    params.set("limit", String(model.limit));
    return `/property-table?${params}`;
  }
  // DOC-BASE-END

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  function draw(body, model, data) {
    body.replaceChildren();
    if (!data.rows.length) {
      body.append(el("p", "db-empty", "No notes match."));
      return;
    }
    const wrap = el("div", "db-scroll");
    const table = el("table", "db-table");
    const head = el("tr");
    for (const name of ["Note", ...data.columns]) head.append(el("th", "", name));
    const thead = el("thead");
    thead.append(head);
    table.append(thead);
    const rows = el("tbody");
    for (const row of data.rows) {
      const tr = el("tr");
      const first = el("td", "db-title");
      const open = el("button", "db-open link-button", row.title);
      open.type = "button";
      open.addEventListener("click", () => flashEntry(row.id));
      first.append(open);
      tr.append(first);
      for (const column of data.columns) tr.append(el("td", "", (row.values[column] || []).join(", ")));
      rows.append(tr);
    }
    table.append(rows);
    wrap.append(table);
    body.append(wrap);
    if (data.total > data.rows.length) body.append(el("p", "db-count", `${data.rows.length} of ${nounCount(data.total, "note")}.`));
  }

  //: **`fill(figure, source)`**: reads the notes and draws the table into `figure`; false (the reasons left in the figure)
  //: when the fence names nothing to look for, so Read keeps it as code.
  function fill(figure, source) {
    const model = parse(source);
    figure.replaceChildren();
    const issues = el("ul", "db-issues");
    for (const line of model.errors) issues.append(el("li", "", line));
    if (!model.type && !model.where.length && !model.columns.length) {
      figure.append(el("p", "db-empty", "Nothing to look for yet. Write a line such as type: Book."));
      if (model.errors.length) figure.append(issues);
      return false;
    }
    const bar = el("div", "db-bar");
    const label = el("span", "db-label", model.type ? `Notes of type ${model.type}` : "Notes");
    const refresh = smallButton("ph:arrow-clockwise", "Refresh the table", () => load());
    refresh.classList.add("icon-only");
    bar.append(refresh, label);
    const body = el("div", "db-body");
    body.setAttribute("aria-live", "polite");
    figure.append(bar, body);
    if (model.errors.length) figure.append(issues);
    let token = 0;
    function load() {
      const mine = ++token;
      body.replaceChildren(el("p", "db-empty", "Reading the notes"));
      apiJson(query(model), { silent: true })
        .then((data) => {
          if (mine === token && figure.isConnected) draw(body, model, data);
        })
        .catch(() => {
          if (mine === token) body.replaceChildren(el("p", "db-empty", "The notes could not be read just now."));
        });
    }
    load();
    return true;
  }

  Object.assign(docMathRender, { base: { parse, query, fill } });
})();
