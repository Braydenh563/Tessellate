// diagram-kinds-more.js: a Gantt chart, a pie chart, a state, a class and an ER diagram as block kinds (L-documents-57, INBOX 1679
// gap 3). Lazy: fetched by `diagramModel.kinds.load` (diagram-kinds.js) before the pane for one of these opens, and it joins the
// kinds' registry. The same engine as the mind map, the timeline and the sequence diagram: each kind is `parse(source)`, `print(model)`
// and an adapter saying where a block may sit (`children`). A line the reader cannot place stays where it stood as a kept line, and a
// row the person has not touched is printed as it was written (`raw`), so a source in the docs' own form comes back unchanged.
// `DIAGRAM-KINDS-MORE-BEGIN`/`END` is the pure part (node-tested, tests/test_diagram_kinds_more.py).
//
// One closure, no export: the adapters are added to `diagramModel.kinds.registry` and to `diagramModel.kinds`.
(() => {
  // DIAGRAM-KINDS-MORE-BEGIN
  const kmMake = (m, type, f) => ({ type, uid: `u${(m.seq = (m.seq || 0) + 1)}`, ...f });
  const kmKeep = (m, line) => kmMake(m, "k", { line });
  const kmClean = (t) => String(t ?? "").replace(/\s*\n\s*/g, " ").trim();
  const kmLast = (list) => list[list.length - 1] || null;

  //: The header line, the lines before it (frontmatter, comments) and the body; `unit` is the indent the source uses.
  function kmRead(source, re) {
    const { front, rest } = diagramModel.front(String(source ?? "").replace(/\r/g, ""));
    const lines = rest.split("\n");
    let at = 0;
    while (at < lines.length && (!lines[at].trim() || lines[at].trim().startsWith("%%"))) {
      if (lines[at].trim()) front.push(lines[at].trim());
      at++;
    }
    const head = (lines[at] || "").trim();
    if (!re.test(head)) return null;
    const body = lines.slice(at + 1);
    const lead = body.find((l) => /^[ \t]+\S/.test(l));
    return { front, head, body, unit: lead ? /^[ \t]*/.exec(lead)[0] : "    " };
  }
  const kmBase = (kind, r) => ({ kind, front: r.front, header: r.head, unit: r.unit });
  //: One line of a list, as printed: a kept line as it stood, a row as it was written unless it was changed (`raw` goes then).
  const kmLine = (n, canon) => (n.type === "k" ? n.line : n.raw ?? canon(n));
  //: Every block of a list and what it holds, depth first.
  const kmAll = (list, kids, fn) => list.forEach((n) => (fn(n), kids(n) && kmAll(kids(n), kids, fn)));
  const kmFresh = (used, stem) => {
    for (let i = 1; ; i++) if (!used.has(`${stem}${i}`)) return `${stem}${i}`;
  };

  // --- pie ---------------------------------------------------------------------------
  function kmPieParse(source) {
    const r = kmRead(source, /^pie(?:\s+showData)?(?:\s+title\b.*)?$/i);
    if (!r) return null;
    const m = { ...kmBase("pie", r), items: [], showData: /^pie\s+showData\b/i.test(r.head) };
    //: The title in the header is a block (`head`) that prints back there; `raw` keeps the header as written until it is edited.
    const title = /\btitle\s+(\S.*)$/i.exec(r.head);
    if (title) m.items.push(kmMake(m, "p", { key: "title", value: title[1], head: true, raw: r.head }));
    m.headTitle = Boolean(title);
    for (const raw of r.body) {
      const s = raw.trim();
      const hit = /^"([^"]*)"\s*:\s*(\d+(?:\.\d+)?)$/.exec(s);
      const prop = /^title\s+(\S.*)$/i.exec(s);
      if (!s) continue;
      m.items.push(hit ? kmMake(m, "s", { label: hit[1], value: hit[2], raw: s }) : prop ? kmMake(m, "p", { key: "title", value: prop[1], raw: s }) : kmKeep(m, s));
    }
    return m;
  }
  function kmPiePrint(m) {
    const head = m.items.find((n) => n.type === "p" && n.head);
    const header = (head ? head.raw === undefined : m.headTitle) ? `pie${m.showData ? " showData" : ""}${head ? ` title ${head.value}` : ""}` : m.header;
    return [...m.front, header, ...m.items.filter((n) => !n.head).map((n) => m.unit + kmLine(n, (x) => (x.type === "p" ? kmProp(x) : `"${x.label}" : ${x.value}`)))].join("\n") + "\n";
  }
  //: A property row (`title X`, `dateFormat X`) as the docs write it.
  const kmProp = (n) => `${n.key} ${n.value}`;
  const KM_PROPS = { title: "title", dateformat: "date format" };
  const kmPropGlyph = (n) => (n.key.toLowerCase() === "title" ? "text-t" : "calendar-blank");
  const kmPieSum = (m) => m.items.reduce((sum, n) => sum + (n.type === "s" ? Number(n.value) : 0), 0);

  // --- gantt -------------------------------------------------------------------------
  const KM_GANTT_KEEP = /^(title|dateFormat|axisFormat|tickInterval|excludes|includes|todayMarker|weekday|weekend|topAxis|inclusiveEndDates|click|accTitle|accDescr|vert)\b/i;
  const KM_GANTT_FLAGS = ["done", "active", "crit", "milestone"];
  function kmGanttParse(source) {
    const r = kmRead(source, /^gantt$/i);
    if (!r) return null;
    const m = { ...kmBase("gantt", r), free: [], sections: [] };
    let section = null;
    const into = () => (section ? section.tasks : m.free);
    for (let i = 0; i < r.body.length; i++) {
      const s = r.body[i].trim();
      let hit;
      if (!s) continue;
      if (!section && (hit = /^(title|dateFormat)\s+(\S.*)$/i.exec(s))) m.free.push(kmMake(m, "p", { key: hit[1], value: hit[2], raw: s }));
      else if (s.startsWith("%%") || KM_GANTT_KEEP.test(s)) {
        into().push(kmKeep(m, s));
        //: A multi-line description keeps every line of its braces.
        if (/^accDescr\s*\{/.test(s) && !s.includes("}")) while (++i < r.body.length) {
          into().push(kmKeep(m, r.body[i].trim()));
          if (r.body[i].includes("}")) break;
        }
      } else if ((hit = /^section\s+(\S.*)$/i.exec(s))) m.sections.push((section = kmMake(m, "s", { title: hit[1], tasks: [] })));
      else if ((hit = /^([^:#]+?)\s*:\s*(\S.*)$/.exec(s))) into().push(kmMake(m, "t", { text: hit[1].trim(), spec: hit[2].trim(), raw: s }));
      else into().push(kmKeep(m, s));
    }
    return m;
  }
  function kmGanttPrint(m) {
    const task = (n) => m.unit + kmLine(n, (x) => (x.type === "p" ? kmProp(x) : `${x.text} :${x.spec}`));
    const out = [...m.front, m.header, ...m.free.map(task)];
    for (const s of m.sections) out.push(`${m.unit}section ${s.title}`, ...s.tasks.map(task));
    return out.join("\n") + "\n";
  }
  const kmFlags = (spec) => String(spec).split(",").map((t) => t.trim()).filter(Boolean);
  //: A task's status words (done, active, crit, milestone) toggled; they lead the timing, as the docs write them.
  function kmFlag(n, flag) {
    const parts = kmFlags(n.spec);
    const on = parts.filter((p) => KM_GANTT_FLAGS.includes(p));
    const rest = parts.filter((p) => !KM_GANTT_FLAGS.includes(p));
    const next = on.includes(flag) ? on.filter((p) => p !== flag) : [...on, flag];
    delete n.raw;
    n.spec = [...KM_GANTT_FLAGS.filter((p) => next.includes(p)), ...rest].join(", ");
    return next.includes(flag);
  }

  //: Mermaid cannot place the first task by its length alone (it reads an end time from nothing), so with no task yet the new one
  //: starts today, in the default date format; a chart with its own `dateFormat` is left to the person.
  function kmGanttSpec(m, spec) {
    const some = [...m.free, ...m.sections.flatMap((s) => s.tasks)].some((n) => n.type === "t");
    const format = m.free.concat(...m.sections.map((s) => s.tasks)).find((n) => n.type === "k" && /^dateFormat\b/i.test(n.line) || n.type === "p" && /^dateFormat$/i.test(n.key));
    if (some || (format && !/^dateFormat\s+YYYY-MM-DD$/i.test(format.type === "p" ? kmProp(format) : format.line))) return spec;
    const [first, ...rest] = kmFlags(spec).reverse();
    return [...rest.reverse(), new Date().toISOString().slice(0, 10), first].join(", ");
  }

  // --- state -------------------------------------------------------------------------
  const KM_ST_ID = "[\\w.-]+";
  const KM_ST_X = new RegExp(`^(\\[\\*\\]|${KM_ST_ID})\\s*-->\\s*(\\[\\*\\]|${KM_ST_ID})(?:\\s*:\\s*(.*))?$`);
  function kmStateParse(source) {
    const r = kmRead(source, /^stateDiagram(?:-v2)?$/i);
    if (!r) return null;
    const m = { ...kmBase("state", r), items: [] };
    const open = [];
    const into = () => (open.length ? kmLast(open).items : m.items);
    for (const raw of r.body) {
      const s = raw.trim();
      let hit;
      if (!s) continue;
      if ((hit = new RegExp(`^state\\s+(${KM_ST_ID})\\s*\\{$`).exec(s))) {
        const c = kmMake(m, "c", { id: hit[1], items: [] });
        into().push(c);
        open.push(c);
      } else if (s === "}" && open.length) open.pop();
      else if ((hit = new RegExp(`^state\\s+"([^"]*)"\\s+as\\s+(${KM_ST_ID})$`).exec(s))) into().push(kmMake(m, "s", { id: hit[2], desc: hit[1], raw: s }));
      else if ((hit = new RegExp(`^state\\s+(${KM_ST_ID})$`).exec(s))) into().push(kmMake(m, "s", { id: hit[1], desc: null, raw: s }));
      else if ((hit = KM_ST_X.exec(s))) into().push(kmMake(m, "x", { from: hit[1], to: hit[2], label: hit[3] ? kmClean(hit[3]) : "", raw: s }));
      else into().push(kmKeep(m, s));
    }
    return open.length ? null : m;
  }
  function kmStatePrint(m) {
    const out = [...m.front, m.header];
    const put = (list, d) => {
      for (const n of list) {
        const pad = m.unit.repeat(d);
        if (n.type === "c") {
          out.push(`${pad}state ${n.id} {`);
          put(n.items, d + 1);
          out.push(`${pad}}`);
        } else out.push(pad + kmLine(n, (x) => (x.type === "s" ? (x.desc == null ? `state ${x.id}` : `state "${x.desc}" as ${x.id}`) : `${x.from} --> ${x.to}${x.label ? ` : ${x.label}` : ""}`)));
      }
    };
    put(m.items, 1);
    return out.join("\n") + "\n";
  }
  const kmStItems = (n) => (n.type === "c" ? n.items : null);
  //: Every state a transition or a declaration names, in the order they first appear, with the words each shows.
  function kmStateRefs(m) {
    const seen = new Map();
    const note = (id, label) => id !== "[*]" && (!seen.has(id) || (label && seen.get(id) === id)) && seen.set(id, label || id);
    kmAll(m.items, kmStItems, (n) => {
      if (n.type === "x") (note(n.from), note(n.to));
      else if (n.type === "s") note(n.id, n.desc);
      else if (n.type === "c") note(n.id);
    });
    return [...seen].map(([id, label]) => ({ id, label }));
  }
  //: A state's id said everywhere it stands: transitions, declarations and groups (a row's `raw` goes with the change).
  function kmStateRename(m, from, to) {
    kmAll(m.items, kmStItems, (n) => {
      for (const f of n.type === "x" ? ["from", "to"] : ["id"]) if (n[f] === from) (n[f] = to, delete n.raw);
    });
  }

  // --- class -------------------------------------------------------------------------
  const KM_CL_ARROWS = { "<|--": "Inheritance", "--|>": "Inheritance, arrow last", "*--": "Composition", "--*": "Composition, diamond last", "o--": "Aggregation", "--o": "Aggregation, diamond last", "-->": "Association", "<--": "Association, arrow first", "--": "Link", "..": "Dashed link", "..>": "Dependency", "<..": "Dependency, arrow first", "..|>": "Realization", "<|..": "Realization, arrow first" };
  const KM_CL_NAME = '[^\\s"{}:]+';
  const KM_CL_REL = new RegExp(`^(${KM_CL_NAME})\\s+(?:"([^"]*)"\\s+)?(${Object.keys(KM_CL_ARROWS).sort((a, b) => b.length - a.length).map((a) => a.replace(/[|*.<>-]/g, "\\$&")).join("|")})\\s+(?:"([^"]*)"\\s+)?(${KM_CL_NAME})(?:\\s*:\\s*(.*))?$`);
  function kmClassParse(source) {
    const r = kmRead(source, /^classDiagram(?:-v2)?$/i);
    if (!r) return null;
    const m = { ...kmBase("class", r), items: [] };
    let open = null;
    for (const raw of r.body) {
      const s = raw.trim();
      let hit;
      if (!s) continue;
      if (open) {
        if (s === "}") open = null;
        else open.members.push(kmMake(m, "m", { text: s }));
      } else if ((hit = /^class\s+([^\s{]+)\s*(\{)?\s*(\})?$/.exec(s))) {
        const c = kmMake(m, "c", { name: hit[1], members: [], braced: Boolean(hit[2]) });
        m.items.push(c);
        if (hit[2] && !hit[3]) open = c;
      } else if ((hit = KM_CL_REL.exec(s))) m.items.push(kmMake(m, "r", { from: hit[1], l1: hit[2] || "", arrow: hit[3], l2: hit[4] || "", to: hit[5], label: hit[6] ? kmClean(hit[6]) : "", raw: s }));
      else m.items.push(kmKeep(m, s));
    }
    return open ? null : m;
  }
  function kmClassPrint(m) {
    const out = [...m.front, m.header];
    const q = (t) => (t ? ` "${t}"` : "");
    for (const n of m.items) {
      if (n.type !== "c") out.push(m.unit + kmLine(n, (x) => `${x.from}${q(x.l1)} ${x.arrow}${q(x.l2)} ${x.to}${x.label ? ` : ${x.label}` : ""}`));
      else if (!n.members.length && !n.braced) out.push(`${m.unit}class ${n.name}`);
      else out.push(`${m.unit}class ${n.name} {`, ...n.members.map((x) => m.unit.repeat(2) + (x.type === "k" ? x.line : x.text)), `${m.unit}}`);
    }
    return out.join("\n") + "\n";
  }
  const kmClassNames = (m) => {
    const names = new Set();
    for (const n of m.items) n.type === "c" ? names.add(n.name) : n.type === "r" && (names.add(n.from), names.add(n.to));
    return [...names].map((id) => ({ id, label: id }));
  };

  // --- ER ----------------------------------------------------------------------------
  const KM_ER_ENT = '[\\w-]+|"[^"]+"';
  const KM_ER_LEFT = { "||": "Exactly one", "|o": "Zero or one", "}o": "Zero or more", "}|": "One or more" };
  const KM_ER_RIGHT = { "||": "Exactly one", "o|": "Zero or one", "o{": "Zero or more", "|{": "One or more" };
  const KM_ER_REL = new RegExp(`^(${KM_ER_ENT})\\s+(\\|\\||\\|o|\\}o|\\}\\|)(--|\\.\\.)(\\|\\||o\\||o\\{|\\|\\{)\\s+(${KM_ER_ENT})(?:\\s*:\\s*(.*))?$`);
  const kmErShow = (t) => String(t).replace(/^"|"$/g, "");
  const kmErToken = (t) => (/^[\w-]+$/.test(t) ? t : `"${t.replace(/"/g, "")}"`);
  function kmErParse(source) {
    const r = kmRead(source, /^erDiagram$/i);
    if (!r) return null;
    const m = { ...kmBase("er", r), items: [] };
    let open = null;
    for (const raw of r.body) {
      const s = raw.trim();
      let hit;
      if (!s) continue;
      if (open) {
        if (s === "}") open = null;
        else open.members.push(kmMake(m, "a", { text: s }));
      } else if ((hit = new RegExp(`^(${KM_ER_ENT})(\\s*\\[[^\\]]*\\])?\\s*\\{\\s*(\\})?$`).exec(s))) {
        const e = kmMake(m, "e", { name: hit[1], alias: hit[2] || "", members: [], braced: true });
        m.items.push(e);
        if (!hit[3]) open = e;
      } else if ((hit = KM_ER_REL.exec(s))) {
        const label = hit[6] == null ? null : kmClean(hit[6]);
        m.items.push(kmMake(m, "r", { from: hit[1], lc: hit[2], line: hit[3], rc: hit[4], to: hit[5], label: label == null ? null : kmErShow(label), raw: s }));
      } else if ((hit = new RegExp(`^(${KM_ER_ENT})(\\s*\\[[^\\]]*\\])?$`).exec(s))) m.items.push(kmMake(m, "e", { name: hit[1], alias: hit[2] || "", members: [], braced: false }));
      else m.items.push(kmKeep(m, s));
    }
    return open ? null : m;
  }
  function kmErPrint(m) {
    const out = [...m.front, m.header];
    for (const n of m.items) {
      if (n.type !== "e") out.push(m.unit + kmLine(n, (x) => `${x.from} ${x.lc}${x.line}${x.rc} ${x.to}${x.label == null ? "" : ` : ${/\s/.test(x.label) ? `"${x.label}"` : x.label || '""'}`}`));
      else if (!n.members.length && !n.braced) out.push(`${m.unit}${n.name}${n.alias}`);
      else out.push(`${m.unit}${n.name}${n.alias} {`, ...n.members.map((x) => m.unit.repeat(2) + (x.type === "k" ? x.line : x.text)), `${m.unit}}`);
    }
    return out.join("\n") + "\n";
  }
  const kmErNames = (m) => {
    const names = new Set();
    for (const n of m.items) n.type === "e" ? names.add(n.name) : n.type === "r" && (names.add(n.from), names.add(n.to));
    return [...names].map((id) => ({ id, label: kmErShow(id) }));
  };

  // --- the adapters ------------------------------------------------------------------
  //: A relation (class, ER, state) when nothing else names its words: its two ends.
  const kmEnds = (n, show = (t) => t) => `${show(n.from)} → ${show(n.to)}`;
  //: A relation between two blocks is added with the selection as its first end, the next other one as its second.
  function kmPair(names, sel, none) {
    const ids = names.map((x) => x.id);
    const from = sel && ids.includes(sel) ? sel : ids[0];
    return [from, ids.find((id) => id !== from) || none];
  }

  const pie = {
    name: "pie", noun: "pie chart", header: "pie", want: "pie chart", parse: kmPieParse, print: kmPiePrint,
    blank: (m) => !m.items.length,
    children: (m, n) => (n ? [] : [{ list: m.items, types: ["s", "p", "k"] }]),
    home: () => null,
    make: (m, type, f) => (type === "p" ? kmMake(m, "p", { key: "title", value: "Title", ...f }) : kmMake(m, "s", { label: "Slice", value: "10", ...f })),
    clone: (m, n) => (n.type === "p" ? kmMake(m, "p", { key: n.key, value: n.value }) : kmMake(m, "s", { label: n.label, value: n.value })),
    text: (n) => (n.type === "p" ? n.value : n.label),
    setText: (n, text) => (delete n.raw, n.type === "p" ? (n.value = kmClean(text)) : (n.label = kmClean(text).replace(/"/g, "'"))),
    glyph: (n) => (n.type === "p" ? kmPropGlyph(n) : "chart-pie-slice"),
    words(m, n) {
      if (n.type === "p") return { meta: "", kind: KM_PROPS[n.key.toLowerCase()] };
      const sum = kmPieSum(m);
      return { meta: `${n.value}${sum > 0 ? ` (${Math.round((Number(n.value) / sum) * 100)}%)` : ""}`, kind: "slice" };
    },
    sig: (n) => n.value,
    tiles: [
      { id: "slice", group: "Slices", name: "Slice", icon: "chart-pie-slice", key: "s", type: "s", fields: { label: "Slice" }, about: "a slice of the pie, with a number" },
      { id: "title", group: "Chart", name: "Title", icon: "text-t", key: "t", type: "p", fields: { key: "title", value: "Title" }, about: "the title over the chart" },
    ],
    primary: "slice",
    hint: () => "Nothing to add there.",
    empty_text: ["Start a pie chart", "Press Add, then Slice. Name it, then set its number from its menu. A slice's share is its number over the total."],
    menu: ({ S, n, say, prompt, nameOf, key }) => [
      { label: "ph:hash Value…", group: "edit", run: async () => {
        const text = await prompt(`Number for ${nameOf(S, key)} (above zero, as in 42 or 7.5)`, n.value, { confirmLabel: "Save" });
        if (text == null) return;
        if (!/^\d+(?:\.\d+)?$/.test(text.trim()) || !Number(text)) return say("A slice needs a number above zero.");
        delete n.raw;
        n.value = text.trim();
        say(`${nameOf(S, key)} is now ${n.value}.`);
      } },
    ],
  };

  const gantt = {
    name: "gantt", noun: "Gantt chart", header: "gantt", want: "gantt chart", parse: kmGanttParse, print: kmGanttPrint,
    blank: (m) => !m.free.length && !m.sections.length,
    children: (m, n) => (!n ? [{ list: m.free, types: ["t", "p", "k"] }, { list: m.sections, types: ["s"] }] : n.type === "s" ? [{ list: n.tasks, types: ["t", "k"] }] : []),
    //: A task with nothing chosen goes to the last section; a section, to the end.
    home: (m, type) => (type === "t" ? kmLast(m.sections) : null),
    deep: () => null,
    //: A section with nothing in it makes Mermaid log NaN attributes while it draws (measured), so a new one holds a task.
    make: (m, type, f) => (type === "p" ? kmMake(m, "p", { key: "title", value: "Title", ...f }) : type === "s" ? kmMake(m, "s", { title: "Section", tasks: [gantt.make(m, "t", {})], ...f }) : kmMake(m, "t", { text: "Task", spec: kmGanttSpec(m, f.spec || "3d"), ...f })),
    clone: (m, n) => (n.type === "p" ? kmMake(m, "p", { key: n.key, value: n.value }) : n.type === "s" ? kmMake(m, "s", { title: n.title, tasks: [] }) : kmMake(m, "t", { text: n.text, spec: n.spec })),
    text: (n) => (n.type === "p" ? n.value : n.type === "s" ? n.title : n.text),
    setText: (n, text) => (delete n.raw, n.type === "p" ? (n.value = kmClean(text)) : n.type === "s" ? (n.title = kmClean(text)) : (n.text = kmClean(text).replace(/[:#;]/g, " ").trim())),
    glyph: (n) => (n.type === "p" ? kmPropGlyph(n) : n.type === "s" ? "rows" : kmFlags(n.spec).includes("milestone") ? "diamond" : "calendar-check"),
    words(m, n) {
      if (n.type === "p") return { meta: "", kind: KM_PROPS[n.key.toLowerCase()] };
      if (n.type === "s") return { meta: "", kind: "section" };
      const on = kmFlags(n.spec).filter((p) => KM_GANTT_FLAGS.includes(p));
      return { meta: n.spec, kind: on.length ? `task, ${on.join(", ")}` : "task" };
    },
    keptWords: (line) => {
      const hit = /^(axisFormat|excludes|todayMarker|tickInterval)\s+(\S.*)$/i.exec(line);
      return hit ? `${{ axisformat: "Axis format", excludes: "Skips", todaymarker: "Today marker", tickinterval: "Ticks" }[hit[1].toLowerCase()]}: ${hit[2]}` : null;
    },
    tiles: [
      { id: "section", group: "Headings", name: "Section", icon: "rows", key: "s", type: "s", fields: { title: "Section" }, about: "a section, a heading over tasks" },
      { id: "task", group: "Tasks", name: "Task", icon: "calendar-check", key: "t", type: "t", fields: { text: "Task" }, about: "a task, after the last one unless it is given a start" },
      { id: "title", group: "Chart", name: "Title", icon: "text-t", key: "i", type: "p", fields: { key: "title", value: "Title" }, about: "the title over the chart" },
      { id: "dateformat", group: "Chart", name: "Date format", icon: "calendar-blank", key: "d", type: "p", fields: { key: "dateFormat", value: "YYYY-MM-DD" }, about: "how the dates in the timings are written" },
      { id: "milestone", group: "Tasks", name: "Milestone", icon: "diamond", key: "m", type: "t", fields: { text: "Milestone", spec: "milestone, 0d" }, about: "a milestone, a moment with no length" },
    ],
    primary: "task",
    hint: () => "Nothing to add there.",
    empty_text: ["Start a Gantt chart", "Press Add, then Section and Task. A task's timing is its menu's Set timing: an id, a start and a length, or after another task."],
    menu: ({ S, n, say, prompt, nameOf, key }) => (n.type !== "t" ? [] : [
      { label: "ph:timer Set timing…", group: "edit", run: async () => {
        const text = await prompt(`Timing of ${nameOf(S, key)}: an id, a start and a length (a1, 2026-01-05, 5d), or after another task (after a1, 3d)`, n.spec, { confirmLabel: "Save" });
        if (text == null || !text.trim()) return;
        delete n.raw;
        n.spec = kmClean(text);
        say(`Timing of ${nameOf(S, key)} is ${n.spec}.`);
      } },
      { label: "ph:caret-right Status", group: "edit", items: [["done", "Done"], ["active", "Active"], ["crit", "Critical"], ["milestone", "Milestone"]].map(([flag, name]) => ({ label: `${kmFlags(n.spec).includes(flag) ? "ph:check-square" : "ph:square"} ${name}`, run: () => say(`${nameOf(S, key)} is ${kmFlag(n, flag) ? "now" : "no longer"} ${name.toLowerCase()}.`) })) },
    ]),
  };

  const kmStMake = (m, f = {}) => {
    const used = new Set(kmStateRefs(m).map((x) => x.id));
    return kmMake(m, "s", { id: kmFresh(used, "S"), desc: "State", ...f });
  };
  const state = {
    name: "state", noun: "state diagram", header: "stateDiagram-v2", want: "state diagram", parse: kmStateParse, print: kmStatePrint,
    blank: (m) => !m.items.length,
    children: (m, n) => (!n ? [{ list: m.items, types: ["s", "c", "x", "k"] }] : n.type === "c" ? [{ list: n.items, types: ["s", "c", "x", "k"] }] : []),
    home: () => null,
    make(m, type, f) {
      if (type === "x") return kmMake(m, "x", { from: "[*]", to: "[*]", label: "", ...f });
      if (type === "c") {
        const used = new Set(kmStateRefs(m).map((x) => x.id));
        const id = kmFresh(used, "Group");
        used.add(id);
        return kmMake(m, "c", { id, items: [kmStMake(m, { id: kmFresh(used, "S") })], ...f });
      }
      return kmStMake(m, f);
    },
    //: A transition needs two ends: from the chosen state (or the one a chosen transition ends in) to the next other state, else to the end mark.
    defaults(m, tile, sel) {
      const f = { ...tile.fields };
      let made = 0;
      if (tile.type === "x") {
        if (!kmStateRefs(m).length) (m.items.push(kmStMake(m)), made++);
        const ids = kmStateRefs(m).map((x) => x.id);
        const at = sel && (sel.type === "x" ? sel.to : sel.id);
        f.from = ids.includes(at) ? at : ids[0];
        f.to = ids.find((id) => id !== f.from) || "[*]";
      }
      return { fields: f, made };
    },
    clone(m, n) {
      if (n.type === "x") return kmMake(m, "x", { from: n.from, to: n.to, label: n.label });
      const taken = new Set(kmStateRefs(m).map((x) => x.id));
      const id = taken.has(n.id) ? kmFresh(taken, "S") : n.id;
      return n.type === "c" ? kmMake(m, "c", { id, items: [] }) : kmMake(m, "s", { id, desc: n.desc });
    },
    text: (n) => (n.type === "x" ? n.label || kmEnds(n) : n.type === "c" ? n.id : n.desc ?? n.id),
    setText(n, text, m) {
      const t = kmClean(text);
      delete n.raw;
      if (n.type === "x") n.label = t;
      else if (n.type === "s") n.desc = t.replace(/"/g, "'");
      else if (m) kmStateRename(m, n.id, t.replace(/[^\w.-]+/g, "_") || n.id);
    },
    //: A state that goes takes its transitions with it, and so does one inside a group that goes.
    onRemove(m, node) {
      if (node.type === "x") return 0;
      const ids = new Set();
      kmAll([node], kmStItems, (n) => n.type !== "x" && n.type !== "k" && ids.add(n.id));
      let gone = 0;
      const sweep = (list) => {
        for (let i = list.length - 1; i >= 0; i--) {
          const n = list[i];
          if (n.type === "x" && (ids.has(n.from) || ids.has(n.to))) (list.splice(i, 1), gone++);
          else if (n.type === "c") sweep(n.items);
        }
      };
      sweep(m.items);
      return gone;
    },
    joinWords: ["transition", "transitions"],
    made: ["state", "states"],
    refs: (m) => [...kmStateRefs(m), { id: "[*]", label: "Start or end" }],
    refsWord: "states",
    glyph: (n) => (n.type === "x" ? "arrow-right" : n.type === "c" ? "squares-four" : "circle"),
    words: (m, n) => (n.type === "x" ? { meta: n.label ? kmEnds(n) : "", kind: "transition" } : { meta: n.type === "s" && n.desc != null && n.desc !== n.id ? n.id : "", kind: n.type === "c" ? "group" : "state" }),
    sig: (n) => `${n.id}|${n.desc}`,
    keptWords: (line) => (/^direction\s+/i.test(line) ? `Direction: ${line.replace(/^direction\s+/i, "")}` : null),
    tiles: [
      { id: "state", group: "States", name: "State", icon: "circle", key: "s", type: "s", fields: {}, about: "a state" },
      { id: "group", group: "States", name: "Group", icon: "squares-four", key: "g", type: "c", fields: {}, about: "a group, a state that holds states", into: true },
      { id: "transition", group: "Moves", name: "Transition", icon: "arrow-right", key: "t", type: "x", fields: {}, about: "a transition from the chosen state to another" },
    ],
    primary: "state",
    hint: () => "Nothing to add there.",
    empty_text: ["Start a state diagram", "Press Add, then State. A Transition joins two states; its menu picks where it starts and ends, and [*] is the start or the end."],
    menu: ({ S, n, say, pickWho, nameOf, key }) => (n.type !== "x" ? [] : [
      { label: "ph:arrow-line-left From…", group: "edit", run: () => pickWho(S, "Transition from", () => true, (id) => (delete n.raw, (n.from = id), say(`Transition now starts at ${id === "[*]" ? "the start" : id}.`))) },
      { label: "ph:arrow-line-right To…", group: "edit", run: () => pickWho(S, "Transition to", () => true, (id) => (delete n.raw, (n.to = id), say(`Transition now ends at ${id === "[*]" ? "the end" : id}.`))) },
      ...(n.label ? [{ label: "ph:eraser No label", group: "edit", run: () => (delete n.raw, (n.label = ""), say("The label is gone.")) }] : []),
    ]),
  };

  const classKind = {
    name: "class", noun: "class diagram", header: "classDiagram", want: "class diagram", parse: kmClassParse, print: kmClassPrint,
    blank: (m) => !m.items.length,
    children: (m, n) => (!n ? [{ list: m.items, types: ["c", "r", "k"] }] : n.type === "c" ? [{ list: n.members, types: ["m", "k"] }] : []),
    //: A member with nothing chosen goes into the last class; with none, the tile says to add a class first.
    home: (m, type) => (type === "m" ? m.items.filter((x) => x.type === "c").pop() : null),
    make(m, type, f) {
      if (type === "c") return kmMake(m, "c", { name: kmFresh(new Set(kmClassNames(m).map((x) => x.id)), "Class"), members: [], braced: false, ...f });
      if (type === "r") return kmMake(m, "r", { from: "A", l1: "", arrow: "<|--", l2: "", to: "B", label: "", ...f });
      return kmMake(m, "m", { text: "+field", ...f });
    },
    defaults(m, tile, sel) {
      const f = { ...tile.fields };
      let made = 0;
      if (tile.type === "r") {
        while (kmClassNames(m).length < 2) (m.items.push(classKind.make(m, "c", {})), made++);
        const [from, to] = kmPair(kmClassNames(m), sel && (sel.type === "c" ? sel.name : sel.type === "r" ? sel.to : null), "B");
        Object.assign(f, { from, to });
      }
      return { fields: f, made };
    },
    clone(m, n) {
      if (n.type === "c") return kmMake(m, "c", { name: n.name, members: [], braced: n.braced });
      if (n.type === "m") return kmMake(m, "m", { text: n.text });
      return kmMake(m, "r", { from: n.from, l1: n.l1, arrow: n.arrow, l2: n.l2, to: n.to, label: n.label });
    },
    text: (n) => (n.type === "c" ? n.name : n.type === "m" ? n.text : n.label || kmEnds(n)),
    setText(n, text, m) {
      const t = kmClean(text);
      delete n.raw;
      if (n.type === "m") n.text = t;
      else if (n.type === "r") n.label = t;
      else {
        const next = t.replace(/[\s{}":]/g, "") || n.name;
        for (const x of m ? m.items : []) if (x.type === "r") for (const f of ["from", "to"]) x[f] === n.name && (x[f] = next, delete x.raw);
        n.name = next;
      }
    },
    //: A class that goes takes the relations that end in it, so none is left naming what is no longer there.
    onRemove(m, node) {
      if (node.type !== "c") return 0;
      let gone = 0;
      for (let i = m.items.length - 1; i >= 0; i--) {
        const x = m.items[i];
        if (x.type === "r" && (x.from === node.name || x.to === node.name)) (m.items.splice(i, 1), gone++);
      }
      return gone;
    },
    joinWords: ["relation", "relations"],
    made: ["class", "classes"],
    refs: kmClassNames,
    refsWord: "classes",
    glyph: (n) => (n.type === "c" ? "cube" : n.type === "m" ? (/\(/.test(n.text) ? "function" : "text-aa") : "arrows-left-right"),
    words: (m, n) => (n.type === "r" ? { meta: n.label ? kmEnds(n) : "", kind: (KM_CL_ARROWS[n.arrow] || "relation").toLowerCase() } : { meta: "", kind: n.type === "c" ? "class" : /\(/.test(n.text) ? "method" : "field" }),
    sig: (n) => `${n.arrow}|${n.from}|${n.to}|${n.l1}|${n.l2}`,
    tiles: [
      { id: "class", group: "Classes", name: "Class", icon: "cube", key: "c", type: "c", fields: {}, about: "a class" },
      { id: "member", group: "Classes", name: "Member", icon: "text-aa", key: "m", type: "m", fields: {}, about: "a field or a method in the selected class (+name, +run())", into: true },
      { id: "relation", group: "Relations", name: "Relation", icon: "arrows-left-right", key: "r", type: "r", fields: {}, about: "a relation between two classes" },
    ],
    primary: "class",
    hint: (type) => (type === "m" ? "Add a class first." : "Nothing to add there."),
    empty_text: ["Start a class diagram", "Press Add, then Class. A Member goes inside the chosen class; a Relation joins two classes and its menu picks the arrow."],
    menu: ({ S, n, say, sub, prompt, pickWho, nameOf, key }) => (n.type !== "r" ? [] : [
      { label: "ph:arrow-line-left From…", group: "edit", run: () => pickWho(S, "Relation from", () => true, (id) => (delete n.raw, (n.from = id), say(`Relation now starts at ${id}.`))) },
      { label: "ph:arrow-line-right To…", group: "edit", run: () => pickWho(S, "Relation to", () => true, (id) => (delete n.raw, (n.to = id), say(`Relation now ends at ${id}.`))) },
      sub("Arrow", Object.entries(KM_CL_ARROWS), n.arrow, (arrow) => (delete n.raw, (n.arrow = arrow), say(`The relation is now ${KM_CL_ARROWS[arrow].toLowerCase()}.`))),
      { label: "ph:hash How many…", group: "edit", run: async () => {
        const text = await prompt(`How many at each end of ${nameOf(S, key)}: the first end, then the second, as in 1, * or 1, 0..*`, [n.l1, n.l2].filter(Boolean).join(", "), { confirmLabel: "Save" });
        if (text == null) return;
        const [a = "", b = ""] = text.split(",").map((t) => t.trim().replace(/"/g, ""));
        delete n.raw;
        [n.l1, n.l2] = [a, b];
        say(a || b ? "The counts are set." : "The counts are cleared.");
      } },
    ]),
  };

  const er = {
    name: "er", noun: "ER diagram", header: "erDiagram", want: "er diagram", parse: kmErParse, print: kmErPrint,
    blank: (m) => !m.items.length,
    children: (m, n) => (!n ? [{ list: m.items, types: ["e", "r", "k"] }] : n.type === "e" ? [{ list: n.members, types: ["a", "k"] }] : []),
    home: (m, type) => (type === "a" ? m.items.filter((x) => x.type === "e").pop() : null),
    make(m, type, f) {
      if (type === "e") return kmMake(m, "e", { name: kmFresh(new Set(kmErNames(m).map((x) => x.id)), "ENTITY"), alias: "", members: [], braced: false, ...f });
      if (type === "r") return kmMake(m, "r", { from: "A", lc: "||", line: "--", rc: "o{", to: "B", label: "has", ...f });
      return kmMake(m, "a", { text: "string name", ...f });
    },
    defaults(m, tile, sel) {
      const f = { ...tile.fields };
      let made = 0;
      if (tile.type === "r") {
        while (kmErNames(m).length < 2) (m.items.push(er.make(m, "e", {})), made++);
        const [from, to] = kmPair(kmErNames(m), sel && (sel.type === "e" ? sel.name : sel.type === "r" ? sel.to : null), "B");
        Object.assign(f, { from, to });
      }
      return { fields: f, made };
    },
    clone(m, n) {
      if (n.type === "e") return kmMake(m, "e", { name: n.name, alias: n.alias, members: [], braced: n.braced });
      if (n.type === "a") return kmMake(m, "a", { text: n.text });
      return kmMake(m, "r", { from: n.from, lc: n.lc, line: n.line, rc: n.rc, to: n.to, label: n.label });
    },
    text: (n) => (n.type === "e" ? kmErShow(n.name) : n.type === "a" ? n.text : n.label || kmEnds(n, kmErShow)),
    setText(n, text, m) {
      const t = kmClean(text);
      delete n.raw;
      if (n.type === "a") n.text = t;
      else if (n.type === "r") n.label = t;
      else {
        const next = kmErToken(t);
        for (const x of m ? m.items : []) if (x.type === "r") for (const f of ["from", "to"]) x[f] === n.name && (x[f] = next, delete x.raw);
        n.name = next;
      }
    },
    //: A entity that goes takes the relations that end in it, so none is left naming what is no longer there.
    onRemove(m, node) {
      if (node.type !== "e") return 0;
      let gone = 0;
      for (let i = m.items.length - 1; i >= 0; i--) {
        const x = m.items[i];
        if (x.type === "r" && (x.from === node.name || x.to === node.name)) (m.items.splice(i, 1), gone++);
      }
      return gone;
    },
    joinWords: ["relationship", "relationships"],
    made: ["entity", "entities"],
    refs: kmErNames,
    refsWord: "entities",
    glyph: (n) => (n.type === "e" ? "table" : n.type === "a" ? (/\bPK\b/.test(n.text) ? "key" : "dot-outline") : "arrows-left-right"),
    words: (m, n) => (n.type === "r" ? { meta: n.label ? kmEnds(n, kmErShow) : "", kind: `${(KM_ER_LEFT[n.lc] || "").toLowerCase()} to ${(KM_ER_RIGHT[n.rc] || "").toLowerCase()}` } : { meta: "", kind: n.type === "e" ? "entity" : "attribute" }),
    sig: (n) => `${n.lc}|${n.rc}|${n.line}|${n.from}|${n.to}`,
    tiles: [
      { id: "entity", group: "Entities", name: "Entity", icon: "table", key: "e", type: "e", fields: {}, about: "an entity, a table of things" },
      { id: "attribute", group: "Entities", name: "Attribute", icon: "dot-outline", key: "a", type: "a", fields: {}, about: "an attribute in the selected entity (type name, then PK or FK)", into: true },
      { id: "relationship", group: "Relationships", name: "Relationship", icon: "arrows-left-right", key: "r", type: "r", fields: {}, about: "a relationship between two entities" },
    ],
    primary: "entity",
    hint: (type) => (type === "a" ? "Add an entity first." : "Nothing to add there."),
    empty_text: ["Start an ER diagram", "Press Add, then Entity. An Attribute goes inside the chosen entity; a Relationship joins two entities and its menu sets how many on each side."],
    menu: ({ S, n, say, sub, pickWho }) => (n.type !== "r" ? [] : [
      { label: "ph:arrow-line-left From…", group: "edit", run: () => pickWho(S, "Relationship from", () => true, (id) => (delete n.raw, (n.from = id), say(`Relationship now starts at ${kmErShow(id)}.`))) },
      { label: "ph:arrow-line-right To…", group: "edit", run: () => pickWho(S, "Relationship to", () => true, (id) => (delete n.raw, (n.to = id), say(`Relationship now ends at ${kmErShow(id)}.`))) },
      sub("Left side", Object.entries(KM_ER_LEFT), n.lc, (lc) => (delete n.raw, (n.lc = lc), say(`Left side is now ${KM_ER_LEFT[lc].toLowerCase()}.`))),
      sub("Right side", Object.entries(KM_ER_RIGHT), n.rc, (rc) => (delete n.raw, (n.rc = rc), say(`Right side is now ${KM_ER_RIGHT[rc].toLowerCase()}.`))),
      sub("Line", [["--", "Identifying, solid"], ["..", "Not identifying, dashed"]], n.line, (line) => (delete n.raw, (n.line = line), say(`The line is now ${line === "--" ? "solid" : "dashed"}.`))),
    ]),
  };

  const diagramKindsMore = { gantt, pie, state, class: classKind, er };
  for (const A of Object.values(diagramKindsMore)) A.empty = () => A.parse(`${A.header}\n`);
  // DIAGRAM-KINDS-MORE-END

  Object.assign(diagramModel.kinds.registry, diagramKindsMore);
  Object.assign(diagramModel.kinds, diagramKindsMore);
})();
