// diagram-kinds.js: the block pane for the other kinds (1546 P4, DOCUMENTS_PLAN
// "1546 design" D3). Lazy: `LAZY_MODULES.diagramKinds`, registered at the foot of
// documents-mermaid.js and fetched by diagram-builder.js the first time a mind map,
// a timeline or a sequence diagram opens, so the flowchart path does not grow.
//
// Three kinds, one engine. Each kind is a model with `parse(source)` and
// `print(model)` (D2: the source is the only state, a line the reader cannot place
// is kept verbatim and drawn as a locked row, nothing is dropped) and an adapter
// that says where a block may sit (`children`), so one set of moves (place, move,
// step, nest, lift, delete) serves all three. `DIAGRAM-KINDS-BEGIN`/`END` is the
// pure part (node-tested, tests/test_diagram_kinds.py); the rest is the DOM, made
// with createElement and textContent, on the builder's own classes and helpers.
//
// One closure, one export: `diagramModel.kinds` (no new global name).
(() => {
  // DIAGRAM-KINDS-BEGIN
  //: **Mind map**: `{root, head}`; the root and every branch are `{type: "r"|"b", uid,
  //: ident, text, shape, children, extra}`. **Timeline**: `{title, free, sections, head}`;
  //: `free` holds the periods before any section, a section `{title, periods}`, a period
  //: `{when, events}`, an event `{text}`. **Sequence**: `{title, participants, steps}`;
  //: a step is a message, a note, a block (`loop`, `alt`, `opt` and the other openers,
  //: holding steps), a divider (`else`, `and`, `option`) or a kept line. `front` holds
  //: what stood ahead of the header (frontmatter, `%%{init}%%`), `head` the kept lines
  //: that belong to no block, `extra` the kept lines that follow a block. A text a kind
  //: cannot hold (a second mind map root, `box` and `create` in a sequence) is null.
  const KX_MAX = 120;
  const KX_CODE = { "#": "#35;", ":": "#58;", ";": "#59;" };
  //: A label as source: `#` and the kind's own separator written as Mermaid's entity codes.
  const kxEsc = (t, extra = "") => String(t ?? "").replace(/\s*\n\s*/g, " ").replace(new RegExp(`[#${extra}]`, "g"), (c) => KX_CODE[c]).trim();
  const kxUid = (m) => `u${(m.seq = (m.seq || 0) + 1)}`;
  const kxKey = (n) => `${n.type}:${n.uid}`;
  const kxPad = (depth) => "  ".repeat(depth);

  //: The lines after the header, or null when the header is not this kind's.
  function kxLines(source, header) {
    const { front, rest } = diagramModel.front(String(source ?? "").replace(/\r/g, ""));
    const lines = rest.split("\n");
    let at = 0;
    while (at < lines.length && (!lines[at].trim() || lines[at].trim().startsWith("%%"))) {
      if (lines[at].trim()) front.push(lines[at].trim());
      at++;
    }
    return header.test((lines[at] || "").trim()) ? { front, body: lines.slice(at + 1) } : null;
  }

  // --- mind map ---------------------------------------------------------------------
  const KX_MM = [["))", "((", "bang"], ["((", "))", "circle"], ["{{", "}}", "hexagon"], [")", "(", "cloud"], ["[", "]", "square"], ["(", ")", "round"]];
  const KX_MM_SHAPES = ["default", ...KX_MM.map((s) => s[2])];

  //: One node line: an optional id, then a shape's marks around its words (quoted or not).
  //: A line whose marks do not close is kept whole in `raw` and printed as it stood.
  function kxMmRead(line) {
    const at = line.search(/[([{)]/);
    if (at < 0) return { ident: "", text: diagramModel.decode(line), shape: "default" };
    const raw = { raw: line, ident: "", text: line, shape: "default" };
    const tail = line.slice(at);
    const hit = KX_MM.find(([open]) => tail.startsWith(open));
    if (!hit || tail.length < hit[0].length + hit[1].length || !tail.endsWith(hit[1])) return raw;
    let body = tail.slice(hit[0].length, tail.length - hit[1].length).trim();
    //: `bare` remembers a shape the author wrote without quotes, so saving does not add them (`root((Plan))` stays).
    let bare = true;
    if (body.length >= 2 && body[0] === '"' && body.at(-1) === '"') {
      body = body.slice(1, -1);
      bare = false;
      if (body[0] === "`") return raw;
    }
    return { ident: line.slice(0, at).trim(), text: diagramModel.decode(body), shape: hit[2], ...(bare ? { bare } : {}) };
  }

  function kxMmParse(source) {
    const r = kxLines(source, /^mindmap$/i);
    if (!r) return null;
    const m = { kind: "mindmap", front: r.front, head: [], root: null };
    const stack = [];
    let last = null;
    for (const line of r.body) {
      const text = line.replace(/\t/g, "    ");
      const s = text.trim();
      if (!s) continue;
      if (/^(?:%%|::)/.test(s)) {
        (last ? (last.extra ||= []) : m.head).push(s);
        continue;
      }
      const node = { type: "b", uid: kxUid(m), ...kxMmRead(s), children: [] };
      const indent = text.length - text.trimStart().length;
      while (stack.length && stack.at(-1).indent >= indent) stack.pop();
      if (!stack.length) {
        if (m.root) return null;
        node.type = "r";
        m.root = node;
      } else stack.at(-1).node.children.push(node);
      stack.push({ indent, node });
      last = node;
    }
    return m;
  }

  //: Plain words need no marks, unless a bracket or a mark of its own would be read as a shape.
  const kxMmPlain = (t) => Boolean(t) && !/[[\](){}]/.test(t) && !/^(?:%%|::)/.test(t);

  function kxMmPrint(m) {
    const out = [...m.front, "mindmap", ...m.head.map((l) => kxPad(1) + l)];
    const used = new Set();
    const mark = (n) => {
      if (n.ident) used.add(n.ident);
      n.children.forEach(mark);
    };
    if (m.root) mark(m.root);
    let next = 0;
    const fresh = () => {
      while (used.has(`n${++next}`));
      used.add(`n${next}`);
      return `n${next}`;
    };
    const line = (n) => {
      if (n.raw != null) return n.raw;
      const text = String(n.text ?? "").replace(/\s*\n\s*/g, " ").trim();
      const shape = n.shape || "default";
      if (shape === "default" && kxMmPlain(text)) return text;
      const [open, close] = shape === "default" ? ["[", "]"] : KX_MM.find((s) => s[2] === shape);
      //: A bare shape stays bare while its words hold nothing a bracket, a quote or a leading mark would break.
      const q = n.bare && text && !/["[\](){}]/.test(text) && !/^(?:%%|::)/.test(text) ? "" : '"';
      return `${n.ident || fresh()}${open}${q}${q ? text.replace(/"/g, "'") : text}${q}${close}`;
    };
    const walk = (n, depth) => {
      out.push(kxPad(depth) + line(n));
      for (const l of n.extra || []) out.push(kxPad(depth + 1) + l);
      n.children.forEach((c) => walk(c, depth + 1));
    };
    if (m.root) walk(m.root, 1);
    return out.join("\n") + "\n";
  }

  // --- timeline ---------------------------------------------------------------------
  function kxTlParse(source) {
    const r = kxLines(source, /^timeline$/i);
    if (!r) return null;
    const dec = (t) => diagramModel.decode(t.trim());
    const m = { kind: "timeline", front: r.front, head: [], title: null, free: [], sections: [] };
    let section = null;
    let last = null;
    let last_period = null;
    const keep = (line) => (last ? (last.extra ||= []) : m.head).push(line);
    for (let i = 0; i < r.body.length; i++) {
      const s = r.body[i].trim();
      if (!s) continue;
      const title = /^title\s+(\S.*)$/i.exec(s);
      const sect = /^section\s+(\S.*)$/i.exec(s);
      if (title && m.title == null) m.title = dec(title[1]);
      else if (sect) {
        section = { type: "s", uid: kxUid(m), title: dec(sect[1]), periods: [] };
        m.sections.push(section);
        last = section;
        last_period = null;
      } else if (/^acc(?:Title|Descr)\b/.test(s)) {
        keep(s);
        //: A multi-line description keeps every line of its braces.
        if (/^accDescr\s*\{/.test(s) && !s.includes("}")) while (++i < r.body.length) {
          keep(r.body[i].trim());
          if (r.body[i].includes("}")) break;
        }
      } else if (s.startsWith("%%") || title) keep(s);
      else if (s[0] === ":") {
        const events = s.split(":").slice(1).map(dec).filter(Boolean);
        if (!last_period) keep(s);
        else last_period.events.push(...events.map((text) => ({ type: "e", uid: kxUid(m), text })));
      } else {
        const [when, ...events] = s.split(":");
        last_period = { type: "p", uid: kxUid(m), when: dec(when), events: events.map(dec).filter(Boolean).map((text) => ({ type: "e", uid: kxUid(m), text })) };
        (section ? section.periods : m.free).push(last_period);
        last = last_period;
      }
    }
    return m;
  }

  function kxTlPrint(m) {
    const out = [...m.front, "timeline", ...m.head.map((l) => kxPad(1) + l)];
    if (m.title != null) out.push(`${kxPad(1)}title ${kxEsc(m.title, ":")}`);
    const period = (p, depth) => {
      out.push(kxPad(depth) + [kxEsc(p.when, ":"), ...p.events.map((e) => kxEsc(e.text, ":"))].join(" : "));
      for (const l of p.extra || []) out.push(kxPad(depth + 1) + l);
    };
    m.free.forEach((p) => period(p, 1));
    for (const s of m.sections) {
      out.push(`${kxPad(1)}section ${kxEsc(s.title, ":")}`);
      for (const l of s.extra || []) out.push(kxPad(2) + l);
      s.periods.forEach((p) => period(p, 2));
    }
    return out.join("\n") + "\n";
  }

  // --- sequence ---------------------------------------------------------------------
  const KX_ID = "[\\p{L}\\p{N}_.]+(?:-[\\p{L}\\p{N}_.]+)*?";
  const KX_ARROWS = ["<<-->>", "<<->>", "-->>", "->>", "--x", "-x", "--)", "-)", "-->", "->"];
  const KX_MSG = new RegExp(`^(${KX_ID})\\s*(${KX_ARROWS.map((a) => a.replace(/[()]/g, "\\$&")).join("|")})\\s*([+-]?)\\s*(${KX_ID})\\s*:\\s*(.*)$`, "u");
  const KX_NOTE = new RegExp(`^note\\s+(left of|right of|over)\\s+(${KX_ID})(?:\\s*,\\s*(${KX_ID}))?\\s*:\\s*(.*)$`, "iu");
  const KX_DECL = /^(participant|actor)\s+([\p{L}\p{N}_.-]+)(?:\s+as\s+(.+))?$/iu;
  const KX_BLOCK = /^(loop|alt|opt|par|critical|break|rect)\b\s*(.*)$/i;
  const KX_DIV = /^(else|and|option)\b\s*(.*)$/i;
  const KX_WORDS = ["Alice", "Bob", "Carol", "Dave", "Erin", "Frank", "Grace", "Heidi"];

  function kxSeqParse(source) {
    const r = kxLines(source, /^sequenceDiagram$/i);
    if (!r) return null;
    const m = { kind: "sequence", front: r.front, title: null, participants: [], steps: [] };
    //: L-documents-56: `box` groups declarations (`p.box`, the words after it), `create` and `destroy` belong to the message that
    //: follows (`step.create`, `step.destroy`: a participant id), and a leading `autonumber` is `m.autonumber`.
    let boxed = null;
    const pend = {};
    const dec = (t) => diagramModel.decode(t.trim());
    const who = (id, label = null, actor = null) => {
      let p = m.participants.find((x) => x.id === id);
      if (!p) m.participants.push((p = { type: "a", uid: kxUid(m), id, label: id, actor: false, ...(boxed !== null ? { box: boxed } : {}) }));
      if (label != null) p.label = label;
      if (actor != null) p.actor = actor;
      return p;
    };
    const open = [];
    const into = () => (open.length ? open.at(-1).steps : m.steps);
    for (const s of diagramModel.statements(r.body.join("\n"))) {
      let hit;
      const lead = (pend.create || pend.destroy) && !KX_MSG.test(s) && !/^(?:create|destroy)\b/i.test(s);
      if (lead || (boxed !== null && !KX_DECL.test(s) && !/^end$/i.test(s) && !s.startsWith("%%")) || (/^box\b/i.test(s) && (boxed !== null || open.length || m.steps.length))) return null;
      if (boxed !== null && /^end$/i.test(s)) boxed = null;
      else if ((hit = /^box\b\s*(.*)$/i.exec(s))) boxed = dec(hit[1]);
      else if (/^autonumber$/i.test(s) && !m.steps.length && !open.length) m.autonumber = true;
      else if ((hit = new RegExp(`^create\\s+(participant|actor)\\s+(${KX_ID})(?:\\s+as\\s+(.+))?$`, "iu").exec(s))) pend.create = who(hit[2], hit[3] ? dec(hit[3]) : null, /^actor$/i.test(hit[1])).id;
      else if ((hit = new RegExp(`^destroy\\s+(${KX_ID})$`, "iu").exec(s))) pend.destroy = hit[1];
      else if (/^(?:create|destroy)\b/i.test(s)) return null;
      else if (s.startsWith("%%")) into().push({ type: "k", uid: kxUid(m), line: s });
      else if ((hit = KX_MSG.exec(s))) {
        who(hit[1]);
        who(hit[4]);
        const step = { type: "m", uid: kxUid(m), from: hit[1], to: hit[4], arrow: hit[2], act: hit[3], text: dec(hit[5]) };
        for (const k of ["create", "destroy"]) if (pend[k] && [step.from, step.to].includes(pend[k])) step[k] = pend[k];
        if ((pend.create && !step.create) || (pend.destroy && !step.destroy)) return null;
        pend.create = pend.destroy = null;
        into().push(step);
      } else if ((hit = KX_DECL.exec(s))) who(hit[2], hit[3] ? dec(hit[3]) : null, /^actor$/i.test(hit[1]));
      else if ((hit = KX_NOTE.exec(s))) {
        const ids = [hit[2], hit[3]].filter(Boolean);
        ids.forEach((id) => who(id));
        into().push({ type: "t", uid: kxUid(m), pos: hit[1].toLowerCase(), who: ids, text: dec(hit[4]) });
      } else if ((hit = /^title\s*:?\s*(\S.*)$/i.exec(s)) && m.title == null && !open.length) m.title = dec(hit[1]);
      else if ((hit = KX_BLOCK.exec(s))) {
        const block = { type: "b", uid: kxUid(m), kw: hit[1].toLowerCase(), text: dec(hit[2]), steps: [] };
        into().push(block);
        open.push(block);
      } else if ((hit = KX_DIV.exec(s)) && open.length) into().push({ type: "d", uid: kxUid(m), kw: hit[1].toLowerCase(), text: dec(hit[2]) });
      else if (/^end$/i.test(s) && open.length) open.pop();
      else into().push({ type: "k", uid: kxUid(m), line: s });
    }
    return pend.create || pend.destroy || boxed !== null ? null : m;
  }

  function kxSeqPrint(m) {
    const out = [...m.front, "sequenceDiagram"];
    if (m.title != null) out.push(`${kxPad(1)}title ${kxEsc(m.title, ";")}`);
    //: A participant made by a `create` line is declared there; one whose creating message is gone is declared up here.
    const ends = (s, k) => s[k] && (s.from === s[k] || s.to === s[k]);
    const made = new Set(kxSteps(m.steps).filter((s) => s.type === "m" && ends(s, "create")).map((s) => s.create));
    const decl = (p, word) => `${word} ${p.id}${p.label !== p.id ? ` as ${kxEsc(p.label, ";")}` : ""}`;
    if (m.autonumber) out.push(`${kxPad(1)}autonumber`);
    let boxed = null;
    for (const p of m.participants) {
      if (made.has(p.id)) continue;
      const b = typeof p.box === "string" ? p.box : null;
      if (b !== boxed) {
        if (boxed !== null) out.push(`${kxPad(1)}end`);
        if (b !== null) out.push(`${kxPad(1)}box${b ? ` ${kxEsc(b, ";")}` : ""}`);
        boxed = b;
      }
      out.push(kxPad(boxed === null ? 1 : 2) + decl(p, p.actor ? "actor" : "participant"));
    }
    if (boxed !== null) out.push(`${kxPad(1)}end`);
    const tail = (text) => (kxEsc(text, ";") ? ` ${kxEsc(text, ";")}` : "");
    const put = (steps, depth) => {
      for (const s of steps) {
        if (s.type === "k") out.push(kxPad(depth) + s.line);
        else if (s.type === "m") {
          const born = ends(s, "create") && m.participants.find((p) => p.id === s.create);
          if (born) out.push(kxPad(depth) + "create " + decl(born, born.actor ? "actor" : "participant"));
          if (ends(s, "destroy")) out.push(`${kxPad(depth)}destroy ${s.destroy}`);
          out.push(`${kxPad(depth)}${s.from}${s.arrow}${s.act || ""}${s.to}:${tail(s.text)}`);
        }
        else if (s.type === "t") out.push(`${kxPad(depth)}Note ${s.pos} ${s.who.join(",")}:${tail(s.text)}`);
        else if (s.type === "d") out.push(`${kxPad(depth - 1)}${s.kw}${tail(s.text)}`);
        else {
          out.push(`${kxPad(depth)}${s.kw}${tail(s.text)}`);
          put(s.steps, depth + 1);
          out.push(`${kxPad(depth)}end`);
        }
      }
    };
    put(m.steps, 1);
    return out.join("\n") + "\n";
  }

  // --- the engine -------------------------------------------------------------------
  //: An adapter says where a block may sit: `children(m, node)` answers the lists a
  //: node holds (null: the diagram itself) as `{list, types, fixed}` in the order they
  //: print. Every move below goes through it, so one engine serves the three kinds.
  const kxWalk = (A, m, fn, parent = null, depth = 0) => {
    for (const level of A.children(m, parent)) for (const n of level.list) {
      fn(n, level, parent, depth);
      kxWalk(A, m, fn, n, depth + 1);
    }
  };
  const kxCount = (A, m) => {
    let c = 0;
    kxWalk(A, m, (n) => n.type !== "k" && c++);
    return c;
  };
  const kxFind = (A, m, key) => {
    let hit = null;
    const uid = String(key).slice(2);
    kxWalk(A, m, (node, level, parent) => {
      if (!hit && node.uid === uid && node.type !== "k") hit = { node, level, list: level.list, parent };
    });
    return hit;
  };
  const kxLevel = (A, m, parent, type) => A.children(m, parent).find((level) => level.types.includes(type) && !level.fixed) || null;
  const kxWithin = (A, m, node, ancestor) => {
    let hit = node === ancestor;
    kxWalk(A, m, (n) => n === node && (hit = true), ancestor);
    return hit;
  };

  //: The blocks as nested rows `{type, uid, node, kids}` in the order they print; a
  //: kept line is a row of its own, `{type: "k", uid, line}`.
  function kxRows(A, m, parent = null) {
    const out = [];
    if (!parent) (m.head || []).forEach((line, i) => out.push({ type: "k", uid: `h${i}`, line }));
    for (const level of A.children(m, parent)) for (const n of level.list) {
      if (n.type === "k") out.push({ type: "k", uid: n.uid, line: n.line });
      else {
        const kids = [...(n.extra || []).map((line, i) => ({ type: "k", uid: `${n.uid}.${i}`, line })), ...kxRows(A, m, n)];
        out.push({ type: n.type, uid: n.uid, node: n, fixed: level.fixed, kids: A.children(m, n).length || kids.length ? kids : undefined });
      }
    }
    return out;
  }

  function kxMove(A, m, key, parentKey = null, beforeKey = null) {
    const f = kxFind(A, m, key);
    const parent = parentKey ? kxFind(A, m, parentKey)?.node : null;
    if (!f || f.level.fixed || key === beforeKey || (parentKey && !parent) || (parent && kxWithin(A, m, parent, f.node))) return false;
    const level = kxLevel(A, m, parent, f.node.type);
    if (!level) return false;
    f.list.splice(f.list.indexOf(f.node), 1);
    const before = beforeKey ? level.list.find((n) => kxKey(n) === beforeKey) : null;
    level.list.splice(before ? level.list.indexOf(before) : level.list.length, 0, f.node);
    return true;
  }

  //: A block of `type` inside `parent` (null: the top) before the node `before`; null
  //: when the kind has no place for it there or the diagram is full.
  function kxAdd(A, m, type, { parent = null, before = null, fields = {} } = {}) {
    const level = kxLevel(A, m, parent, type);
    if (!level || kxCount(A, m) >= KX_MAX) return null;
    const node = A.make(m, type, fields);
    const at = before ? level.list.indexOf(before) : -1;
    level.list.splice(at >= 0 ? at : level.list.length, 0, node);
    return node;
  }

  //: Where a block of `type` goes for a selection: into it when asked and it can hold one,
  //: else after it among its own kind, else inside it, else (the same two) beside its
  //: parents, so an event added with a section selected still lands in a period.
  function kxSpot(A, m, type, selKey, into = false) {
    let at = selKey && kxFind(A, m, selKey);
    if (!at) {
      const home = A.home(m, type);
      return home === undefined ? null : { parent: home, before: null };
    }
    for (let hops = 0; at && hops < 8; hops++) {
      if (into && kxLevel(A, m, at.node, type)) return { parent: at.node, before: null };
      if (at.level.types.includes(type) && !at.level.fixed) return { parent: at.parent, before: at.list[at.list.indexOf(at.node) + 1] || null };
      const deep = A.deep?.(at.node, type) || (kxLevel(A, m, at.node, type) && at.node);
      if (deep) return { parent: deep, before: null };
      at = at.parent && kxFind(A, m, kxKey(at.parent));
    }
    //: Nothing near it holds one: the top, when the diagram's own list takes the kind (a participant, a section).
    return kxLevel(A, m, null, type) ? { parent: null, before: null } : null;
  }

  //: Deletes a block with what it holds. Kept lines inside it stay: a kept step takes its
  //: place in the list, a block's `extra` goes to the one before it. `{count, joins}` answers
  //: what went with it (`joins`: the kind's own, a participant's messages), or null.
  function kxRemove(A, m, key) {
    const f = kxFind(A, m, key);
    if (!f || f.level.fixed) return null;
    let count = 0;
    const kept = [];
    const lines = [...(f.node.extra || [])];
    kxWalk(A, m, (n) => {
      if (n.type === "k") kept.push(n);
      else count++;
      lines.push(...(n.extra || []));
    }, f.node);
    const at = f.list.indexOf(f.node);
    f.list.splice(at, 1, ...kept);
    if (lines.length) {
      const host = f.list.slice(0, at).reverse().find((x) => x.type !== "k") || f.parent;
      (host ? (host.extra ||= []) : m.head).push(...lines);
    }
    return { count, joins: A.onRemove ? A.onRemove(m, f.node) : 0 };
  }

  function kxStep(A, m, key, dir) {
    const f = kxFind(A, m, key);
    if (!f || f.level.fixed) return false;
    const i = f.list.indexOf(f.node);
    const j = i + dir;
    if (j < 0 || j >= f.list.length) return false;
    [f.list[i], f.list[j]] = [f.list[j], f.list[i]];
    return true;
  }

  //: Alt+Right: to the end of the nearest block above it that can hold one, among its
  //: sisters first, then its parent's.
  function kxNest(A, m, key) {
    const f = kxFind(A, m, key);
    if (!f || f.level.fixed) return false;
    const above = (x) => x.list.slice(0, x.list.indexOf(x.node)).reverse();
    const pf = f.parent && kxFind(A, m, kxKey(f.parent));
    for (const c of [...above(f), ...(pf ? above(pf) : [])]) if (c.type !== "k" && kxLevel(A, m, c, f.node.type)) return kxMove(A, m, key, kxKey(c));
    return false;
  }

  //: Alt+Left: out of its parent, to just after it when the grandparent holds its kind.
  function kxLift(A, m, key) {
    const f = kxFind(A, m, key);
    const pf = f?.parent && kxFind(A, m, kxKey(f.parent));
    if (!f || !pf || f.level.fixed) return false;
    const level = kxLevel(A, m, pf.parent, f.node.type);
    if (!level) return false;
    const next = pf.list === level.list ? pf.list[pf.list.indexOf(pf.node) + 1] : null;
    return kxMove(A, m, key, pf.parent ? kxKey(pf.parent) : null, next ? kxKey(next) : null);
  }

  //: The words of a block, in place. An empty one is refused.
  function kxRelabel(A, m, key, text) {
    const f = kxFind(A, m, key);
    const clean = String(text ?? "").replace(/\s*\n\s*/g, " ").trim();
    if (!f || !clean) return false;
    A.setText(f.node, clean, m);
    return true;
  }

  //: The blocks of `inc` (a parsed model of the same kind) added to `m`, a block under the
  //: copy of its parent when that came too, else under the kind's home for it. `take` is a
  //: Set of incoming keys, or null for all. `{added, skipped, first}`: what the diagram gained
  //: (a participant a message brought along counts), and the first of it in document order.
  //: A kind with `spare` keeps that many places free for what a block brings with it.
  function kxMerge(A, m, inc, take = null) {
    const out = { added: 0, skipped: 0, first: null };
    const had = new Set();
    kxWalk(A, m, (n) => had.add(n));
    const made = new Map();
    made.inc = inc;
    kxWalk(A, inc, (n, _level, parent) => {
      if (n.type === "k" || (take && !take.has(kxKey(n)))) return;
      if (kxCount(A, m) >= KX_MAX - (A.spare || 0)) return void out.skipped++;
      const copy = A.clone(m, n, made);
      if (!copy) return;
      const under = (parent && made.get(parent)) || A.home(m, copy.type);
      const level = under === undefined ? null : kxLevel(A, m, under, copy.type) || kxLevel(A, m, null, copy.type);
      if (!level) return void out.skipped++;
      level.list.push(copy);
      made.set(n, copy);
    });
    kxWalk(A, m, (n) => {
      if (n.type === "k" || had.has(n)) return;
      out.added++;
      out.first ||= kxKey(n);
    });
    return out;
  }

  // --- the adapters -----------------------------------------------------------------
  const kxMake = (m, type, f) => ({ type, uid: kxUid(m), ...f });
  const kxLast = (list) => list[list.length - 1] || null;
  const KX_ARROW_NAMES = {
    "->>": "Message", "-->>": "Reply", "-)": "Async", "--)": "Async reply", "-x": "Lost", "--x": "Lost reply",
    "->": "Line", "-->": "Dashed line", "<<->>": "Both ways", "<<-->>": "Both ways, dashed",
  };

  const mindmap = {
    name: "mindmap", noun: "mind map", header: "mindmap", want: "mind map", parse: kxMmParse, print: kxMmPrint,
    blank: (m) => !m.root,
    children: (m, n) => (n ? [{ list: n.children, types: ["b"] }] : m.root ? [{ list: [m.root], types: ["r"], fixed: true }] : []),
    home: (m) => m.root,
    //: A blank mind map gets its central idea first.
    start: (m, text = "Central idea") => (m.root ||= kxMake(m, "r", { ident: "root", text, shape: "circle", children: [] })),
    make: (m, type, f) => kxMake(m, type, { ident: "", text: "Idea", shape: "default", children: [], ...f }),
    clone: (m, n) => kxMake(m, "b", { ident: "", text: n.text, shape: n.shape, children: [] }),
    text: (n) => n.text,
    setText: (n, text) => (delete n.raw, (n.text = text)),
    tiles: [
      { id: "branch", group: "Ideas", name: "Branch", icon: "tree-structure", key: "b", into: true, type: "b", fields: { text: "Branch" }, about: "a branch under the selected block, or beside the last branch you added" },
      { id: "leaf", group: "Ideas", name: "Leaf", icon: "leaf", key: "n", type: "b", fields: { text: "Idea" }, about: "a leaf next to the selected block" },
    ],
    primary: "leaf",
    hint: () => "Add the central idea first.",
  };

  const timeline = {
    name: "timeline", noun: "timeline", header: "timeline", want: "timeline", parse: kxTlParse, print: kxTlPrint,
    blank: (m) => m.title == null && !m.free.length && !m.sections.length && !m.head.length,
    children: (m, n) => (!n ? [{ list: m.free, types: ["p"] }, { list: m.sections, types: ["s"] }] : n.type === "s" ? [{ list: n.periods, types: ["p"] }] : n.type === "p" ? [{ list: n.events, types: ["e"] }] : []),
    //: An event with nothing chosen goes to the last period; a period or a section, to the top.
    home: (m, type) => {
      if (type !== "e") return null;
      return kxLast(m.sections.flatMap((s) => s.periods)) || kxLast(m.free) || undefined;
    },
    //: An event added with a section chosen goes to the section's last period.
    deep: (n, type) => (type === "e" && n.type === "s" ? kxLast(n.periods) : null),
    make: (m, type, f) => kxMake(m, type, type === "s" ? { title: "Section", periods: [], ...f } : type === "p" ? { when: "When", events: [], ...f } : { text: "Event", ...f }),
    clone: (m, n) => kxMake(m, n.type, n.type === "s" ? { title: n.title, periods: [] } : n.type === "p" ? { when: n.when, events: [] } : { text: n.text }),
    text: (n) => (n.type === "s" ? n.title : n.type === "p" ? n.when : n.text),
    setText: (n, text) => (n.type === "s" ? (n.title = text) : n.type === "p" ? (n.when = text) : (n.text = text)),
    tiles: [
      { id: "section", group: "Headings", name: "Section", icon: "rows", key: "s", type: "s", fields: { title: "Section" }, about: "a section, a heading over periods" },
      { id: "period", group: "Headings", name: "Period", icon: "calendar-blank", key: "p", type: "p", fields: { when: "When" }, about: "a period, a date or a time" },
      { id: "event", group: "What happened", name: "Event", icon: "flag", key: "e", type: "e", fields: { text: "Event" }, about: "an event in the selected period" },
    ],
    primary: "event",
    hint: (type) => (type === "e" ? "Add a period first, then its events." : "Nothing to add there."),
  };

  //: A letter not yet an id: A to Z, then P27 and on.
  function kxFreshId(m) {
    const used = new Set(m.participants.map((p) => p.id));
    for (let c = 65; c < 91; c++) if (!used.has(String.fromCharCode(c))) return String.fromCharCode(c);
    for (let i = 27; ; i++) if (!used.has(`P${i}`)) return `P${i}`;
  }
  function kxAddWho(m, actor = false, label = null) {
    const names = new Set(m.participants.map((p) => p.label));
    return kxMake(m, "a", { id: kxFreshId(m), label: label || KX_WORDS.find((w) => !names.has(w)) || `Participant ${m.participants.length + 1}`, actor });
  }
  const kxSteps = (steps) => steps.flatMap((s) => [s, ...(s.steps ? kxSteps(s.steps) : [])]);

  const sequence = {
    name: "sequence", noun: "sequence diagram", header: "sequenceDiagram", want: "", parse: kxSeqParse, print: kxSeqPrint,
    blank: (m) => !m.participants.length && !m.steps.length && m.title == null,
    children: (m, n) => (!n ? [{ list: m.participants, types: ["a"] }, { list: m.steps, types: ["m", "t", "b", "k"] }] : n.type === "b" ? [{ list: n.steps, types: ["m", "t", "b", "d", "k"] }] : []),
    home: () => null,
    make: (m, type, f) => {
      if (type === "a") return kxAddWho(m, f.actor, f.label);
      if (type === "m") return kxMake(m, "m", { from: "A", to: "B", arrow: "->>", act: "", text: "Message", ...f });
      if (type === "t") return kxMake(m, "t", { pos: "over", who: [], text: "Note", ...f });
      if (type === "d") return kxMake(m, "d", { kw: "else", text: "Otherwise", ...f });
      const block = kxMake(m, "b", { kw: "loop", text: "Repeat", steps: [], ...f });
      //: A group with nothing in it makes Mermaid log NaN attributes while it draws (measured, loop and alt),
      //: so a new one holds a message between the first two participants, and an alt its divider and a second.
      const [a, b] = m.participants;
      const step = () => (a && b ? [kxMake(m, "m", { from: a.id, to: b.id, arrow: "->>", act: "", text: "Message" })] : []);
      if (!block.steps.length) block.steps.push(...step());
      //: A parallel box holds two lanes, joined by `and`, as an alt holds two ways joined by `else`.
      if (block.kw === "alt" || block.kw === "par") block.steps.push(kxMake(m, "d", block.kw === "alt" ? { kw: "else", text: "Otherwise" } : { kw: "and", text: "Meanwhile" }), ...step());
      return block;
    },
    //: The fields a tile's block starts with. A message needs two participants, so a diagram with
    //: fewer gets them (Alice, Bob); after a message the new one runs between the same pair (a
    //: reply, back). `made` counts the participants added.
    defaults(m, tile, sel) {
      let made = 0;
      while (tile.type !== "a" && m.participants.length < 2) (m.participants.push(kxAddWho(m, false)), made++);
      const ps = m.participants;
      const f = { ...tile.fields };
      if (tile.type === "m") {
        const pair = sel?.type === "m" ? [sel.from, sel.to] : [ps[0].id, ps[1].id];
        [f.from, f.to] = tile.id === "reply" ? [pair[1], pair[0]] : pair;
      } else if (tile.type === "t") f.who = [sel?.type === "m" ? sel.to : ps[0].id];
      return { fields: f, made };
    },
    //: A participant with the same label is the same one; a message brings the ones it needs.
    clone(m, n, made) {
      const pid = (id) => {
        if (!made.has(`id:${id}`)) {
          const from = made.inc.participants.find((p) => p.id === id);
          const label = from?.label || id;
          const same = m.participants.find((p) => p.label.toLowerCase() === label.toLowerCase());
          const copy = same || kxAddWho(m, Boolean(from?.actor), label);
          if (!same) m.participants.push(copy);
          made.set(`id:${id}`, copy.id);
        }
        return made.get(`id:${id}`);
      };
      if (n.type === "a") return void pid(n.id);
      if (n.type === "m") return kxMake(m, "m", { from: pid(n.from), to: pid(n.to), arrow: n.arrow, act: n.act, text: n.text });
      if (n.type === "t") return kxMake(m, "t", { pos: n.pos, who: n.who.map(pid), text: n.text });
      if (n.type === "d") return kxMake(m, "d", { kw: n.kw, text: n.text });
      return kxMake(m, "b", { kw: n.kw, text: n.text, steps: [] });
    },
    text: (n) => (n.type === "a" ? n.label : n.text),
    setText: (n, text) => (n.type === "a" ? (n.label = text) : (n.text = text)),
    onRemove(m, node) {
      if (node.type !== "a") return 0;
      let gone = 0;
      const sweep = (steps) => {
        for (let i = steps.length - 1; i >= 0; i--) {
          const s = steps[i];
          if (s.type === "m" && (s.from === node.id || s.to === node.id)) (steps.splice(i, 1), gone++);
          else if (s.type === "t" && s.who.includes(node.id)) {
            s.who = s.who.filter((id) => id !== node.id);
            if (!s.who.length) (steps.splice(i, 1), gone++);
          } else if (s.steps) sweep(s.steps);
        }
      };
      sweep(m.steps);
      return gone;
    },
    tiles: [
      { id: "actor", group: "Who", name: "Actor", icon: "user", key: "a", type: "a", fields: { actor: true }, about: "an actor, a person on the left of the picture" },
      { id: "participant", group: "Who", name: "Participant", icon: "user-circle", key: "p", type: "a", fields: {}, about: "a participant, a system or a service" },
      { id: "message", group: "Messages", name: "Message", icon: "arrow-right", key: "m", type: "m", fields: { arrow: "->>", text: "Message" }, about: "a message between two participants" },
      { id: "reply", group: "Messages", name: "Reply", icon: "arrow-bend-up-left", key: "r", type: "m", fields: { arrow: "-->>", text: "Reply" }, about: "a dashed reply, back the other way" },
      { id: "async", group: "Messages", name: "Async", icon: "lightning", key: "y", type: "m", fields: { arrow: "-)", text: "Async" }, about: "an async message, sent without waiting" },
      { id: "lost", group: "Messages", name: "Lost", icon: "x-circle", key: "x", type: "m", fields: { arrow: "-x", text: "Lost" }, about: "a message that never arrives" },
      { id: "note", group: "Notes and boxes", name: "Note", icon: "note-pencil", key: "t", type: "t", fields: { text: "Note" }, about: "a note beside a participant" },
      { id: "loop", group: "Notes and boxes", name: "Loop", icon: "repeat", key: "l", type: "b", fields: { kw: "loop", text: "Repeat" }, about: "a loop around steps" },
      { id: "alt", group: "Notes and boxes", name: "Alt", icon: "shuffle", key: "g", type: "b", fields: { kw: "alt", text: "Condition" }, about: "an alt, one way or the other" },
      { id: "opt", group: "Notes and boxes", name: "Opt", icon: "question", key: "o", type: "b", fields: { kw: "opt", text: "Optional" }, about: "an optional step" },
      { id: "par", group: "Notes and boxes", name: "Parallel", icon: "arrows-split", key: "u", type: "b", fields: { kw: "par", text: "At the same time" }, about: "a parallel box, two lanes at once" },
      { id: "critical", group: "Notes and boxes", name: "Critical", icon: "warning", key: "c", type: "b", fields: { kw: "critical", text: "Must happen" }, about: "a critical step that must happen" },
      { id: "break", group: "Notes and boxes", name: "Break", icon: "hand-palm", key: "b", type: "b", fields: { kw: "break", text: "Stop here" }, about: "a break, where the flow stops" },
    ],
    primary: "message",
    spare: 2,
    hint: () => "Nothing to add there.",
  };

  const diagramKinds = { mindmap, timeline, sequence };
  for (const A of Object.values(diagramKinds)) A.empty = () => A.parse(`${A.header}\n`);
  const diagramKindOps = {
    walk: kxWalk, count: kxCount, find: kxFind, level: kxLevel, rows: kxRows, move: kxMove, add: kxAdd, spot: kxSpot, remove: kxRemove,
    step: kxStep, nest: kxNest, lift: kxLift, relabel: kxRelabel, merge: kxMerge, key: kxKey, MAX: KX_MAX, lines: kxLines, make: kxMake, pad: kxPad, esc: kxEsc, ARROWS: KX_ARROW_NAMES, SHAPES: KX_MM_SHAPES, steps: kxSteps,
  };
  // DIAGRAM-KINDS-END

  // ---------------------------------------------------------------------------
  // The pane: the builder's classes and helpers (`kit`, handed in by diagram-builder.js),
  // one tree of cards over the engine above.
  // ---------------------------------------------------------------------------
  const ops = diagramKindOps;
  const panes = new WeakMap();
  let kit = null;
  const TYPE_ICON = { s: "rows", p: "calendar-blank", e: "flag", t: "note-pencil", d: "arrow-bend-down-right" };
  //: A block and a divider in a sentence of their own, shown under the row (1702: "loop" and "else" sat at the right edge as bare words).
  const BLOCK_WORD = { loop: "Loop, repeats", alt: "Alt, one way or another", opt: "Opt, only if", par: "Par, at the same time", critical: "Critical, must succeed", break: "Break, stops here", rect: "Highlight" };
  const DIV_WORD = { else: "Else, the other way", and: "And, at the same time", option: "Option, another choice" };
  const BLOCK_ICON = { loop: "repeat", alt: "shuffle", opt: "question" };
  const MM_GLYPH = { default: "stadium", square: "rect", round: "round", circle: "circle", hexagon: "hexagon" };
  const MM_NAME = { default: "Plain", square: "Square", round: "Rounded", circle: "Circle", bang: "Bang", cloud: "Cloud", hexagon: "Hexagon" };
  const SEQ_BLOCKS = ["loop", "alt", "opt", "par", "critical", "break", "rect"];
  const PAD = { over: "Over", "left of": "Left of", "right of": "Right of" };

  const icon = (name, cls = "") => {
    const i = kit.el("i", `ph ph-${name} ${cls}`.trim());
    i.setAttribute("aria-hidden", "true");
    return i;
  };
  const find = (S, key) => ops.find(S.k, S.m, key);
  //: A pick made by hand: Branch then nests under it (`S.fresh` is the block Branch just made).
  const pick = (S, key, focus) => ((S.fresh = null), kit.select(S, key, focus));
  const nameOf = (S, key) => S.k.text(find(S, key)?.node || {}) || "block";
  const whoLabel = (S, id) => S.m.participants?.find((p) => p.id === id)?.label || id;

  //: The mark at the head of a card: a shape in miniature for a mind map's node, else a glyph.
  function glyph(S, node) {
    if (S.k.glyph) return icon(S.k.glyph(node));
    if (S.k.name === "mindmap") {
      if (node.type === "r") return icon("tree-structure");
      if (!MM_GLYPH[node.shape]) return icon(node.shape === "bang" ? "lightning" : "cloud");
      const g = kit.el("span", "dgm-shape");
      g.dataset.shape = MM_GLYPH[node.shape];
      g.setAttribute("aria-hidden", "true");
      return g;
    }
    if (node.type === "a") return icon(node.actor ? "user" : "user-circle");
    if (node.type === "m") return icon(node.arrow === "-->>" ? "arrow-bend-up-left" : /x$/.test(node.arrow) ? "x-circle" : "arrow-right");
    if (node.type === "b") return icon(BLOCK_ICON[node.kw] || "stack-simple", "dgm-group-icon");
    return icon(TYPE_ICON[node.type] || "square");
  }

  //: The small words beside a card's label, and the kind of block in the card's spoken name.
  function words(S, node) {
    if (S.k.words) return S.k.words(S.m, node);
    const label = (id) => S.m.participants?.find((p) => p.id === id)?.label || id;
    if (S.k.name === "sequence") {
      if (node.type === "m") return { meta: `${label(node.from)} to ${label(node.to)}`, show: `${label(node.from)} \u2192 ${label(node.to)}`, kind: KX_ARROW_NAMES[node.arrow]?.toLowerCase() || "message" };
      if (node.type === "t") return { meta: `${node.pos} ${node.who.map(label).join(", ")}`, kind: "note" };
      if (node.type === "b" || node.type === "d") return { meta: (node.type === "b" ? BLOCK_WORD : DIV_WORD)[node.kw] || node.kw, kind: node.type === "b" ? node.kw : `${node.kw} divider` };
      return { meta: "", kind: node.actor ? "actor" : "participant" };
    }
    if (S.k.name === "timeline") return { meta: "", kind: { s: "section", p: "period", e: "event" }[node.type] };
    return { meta: "", kind: node.type === "r" ? "central idea" : node.children.length ? "branch" : "leaf" };
  }

  //: `activate K` and `deactivate K` are kept lines (the blocks do not edit them), said in plain words: "Worker is active".
  function keptWords(S, line) {
    const hit = /^(de)?activate\s+(\S+)$/i.exec(line);
    if (S.k.keptWords) return S.k.keptWords(line, S.m);
    if (!hit || S.k.name !== "sequence") return null;
    const who = S.m.participants.find((p) => p.id === hit[2])?.label || hit[2];
    return `${who} ${hit[1] ? "is done" : "is active"}`;
  }

  // --- the tree -------------------------------------------------------------------
  const keysOf = (rows) => rows.flatMap((r) => (r.type === "k" ? [] : [ops.key(r), ...keysOf(r.kids || [])]));

  //: A row whose words, kind, glyph and menu are unchanged keeps its element (the flowchart's rule, diagram-builder.js
  //: `render`), and the tree moves only what is out of place, so a change lays out only the rows it touched.
  function render(S) {
    const had = S.tree.contains(document.activeElement);
    const rows = ops.rows(S.k, S.m);
    if (S.sel && !keysOf(rows).includes(S.sel)) S.sel = null;
    const fresh = new Map();
    S.cache ||= new Map();
    const built = rows.map((r) => buildBlock(S, r, 1, fresh));
    //: A sequence list opens with its participants, then its messages: a heading before each (1702: one undifferentiated list).
    if (S.k.name === "sequence") {
      const heads = [["a", "Participants"], ["mtbd", "Messages"]].map(([types, text]) => [rows.findIndex((r) => types.includes(r.type)), text]);
      for (const [index, text] of heads.reverse()) if (index >= 0) built.splice(index, 0, ((S.heads ||= {})[text] ||= kit.el("p", "dgm-sechead muted", text)));
      for (const text of ["Participants", "Messages"]) if (S.heads?.[text]) S.heads[text].setAttribute("aria-hidden", "true");
    }
    S.cache = fresh;
    S.tree.querySelectorAll(".dgm-target, .dgm-connecting, .dgm-lifted").forEach((b) => b.classList.remove("dgm-target", "dgm-connecting", "dgm-lifted"));
    kit.reconcile(S.tree, built);
    const blank = S.k.blank(S.m);
    S.empty.classList.toggle("hidden", !blank);
    S.pane.tabIndex = blank ? 0 : -1;
    const stop = kit.blockEl(S, S.sel) || S.tree.querySelector(".dgm-block");
    kit.stops(S, stop);
    if (had && document.activeElement !== stop) stop?.focus();
    diagramModel.library.hist(S);
  }

  //: What a row shows and what its menu offers, as one string. The node is kept beside it: the menu's actions hold that
  //: object, so a re-read source (undo, an edit in Source) makes new nodes and every row is built again.
  function fieldsOf(S, row, level, kids) {
    if (row.type === "k") return `k${level}\n${row.line}`;
    const n = row.node;
    const { meta, kind } = words(S, n);
    return [level, row.fixed, n.type, S.k.text(n), meta, kind, n.shape, n.arrow, n.act, n.pos, n.kw, n.actor, n.from, n.to, S.k.sig?.(n), Boolean(row.kids), kids.map((k) => k.sig).join("|")].join("\u0001");
  }

  function buildBlock(S, row, level, fresh) {
    const key = row.type === "k" ? `k:${row.uid}` : ops.key(row);
    const kids = (row.kids || []).map((k) => buildBlock(S, k, level + 1, fresh));
    const sig = fieldsOf(S, row, level, kids.map((k) => fresh.get(k.dataset.key)));
    const hit = S.cache.get(key);
    const made = hit && hit.sig === sig && hit.node === row.node ? hit.el : buildRow(S, row, level, kids);
    fresh.set(key, { sig, node: row.node, el: made });
    return made;
  }

  function buildRow(S, row, level, built) {
    const block = kit.el("div", "dgm-block");
    block.setAttribute("role", "treeitem");
    block.setAttribute("aria-level", String(level));
    if (row.type === "k") {
      block.classList.add("dgm-kept");
      block.dataset.key = `k:${row.uid}`;
      block.setAttribute("aria-label", `Kept line: ${row.line}`);
      block.title = "Blocks cannot edit this line. It stays in the source where it is.";
      const card = kit.el("div", "dgm-card");
      const said = keptWords(S, row.line);
      if (said) {
        block.setAttribute("aria-label", `${said}, from the line ${row.line}`);
        card.append(icon(/^de/i.test(row.line) ? "stop-circle" : "play-circle", "dgm-kept-icon"), kit.el("span", "dgm-label", said));
      } else card.append(icon("lock-simple", "dgm-kept-icon"), kit.el("code", "dgm-label", row.line));
      block.append(card);
      return block;
    }
    const node = row.node;
    const key = ops.key(row);
    const text = S.k.text(node);
    const { meta, kind, show } = words(S, node);
    block.dataset.key = key;
    block.setAttribute("aria-label", `${text || "(empty)"}, ${kind}${meta ? `, ${meta}` : ""}`);
    //: A mind map's leaf holds nothing yet and is a plain card; every other holder is a boxed one with its hole.
    const boxed = Boolean(row.kids) && (row.kids.length > 0 || S.k.name !== "mindmap");
    if (boxed) {
      block.classList.add("dgm-group");
      block.setAttribute("aria-expanded", "true");
    }
    const card = kit.el("div", "dgm-card");
    //: A sequence row is two lines: the sentence, and who it is between (or what the block is) muted under it.
    if (meta && (S.k.name === "sequence" || S.k.two)) card.classList.add("dgm-card-two");
    const grip = kit.el("span", "dgm-grip");
    grip.dataset.objGrip = "";
    grip.title = "Drag to move";
    grip.append(icon("dots-six-vertical"));
    card.append(grip, glyph(S, node), kit.el("span", "dgm-label", text));
    if (meta) card.append(kit.el("span", "dgm-meta muted", show || meta));
    card.append(diagramModel.library.lazyKebab(() => itemsFor(S, key), `Menu for ${text}`));
    block.append(card);
    if (boxed || row.kids?.length) {
      const kids = kit.el("div", "dgm-kids");
      kids.setAttribute("role", "group");
      if (row.kids.length) kids.append(...built);
      else kids.append(kit.el("p", "dgm-hole muted", "Drop blocks here"));
      block.append(kids);
    }
    return block;
  }

  // --- menus ----------------------------------------------------------------------
  //: A pick of one participant (or "no one", for a note's second), from the picker the flowchart's Join uses.
  function pickWho(S, title, allow, done, none = null) {
    const refs = S.k.refs ? S.k.refs(S.m) : S.m.participants;
    const things = S.k.refsWord || "participants";
    const shell = pickerDialog({ title, placeholder: `Search the ${things}…`, searchLabel: `Search the ${things}` });
    const box = pickerListbox(shell, things.charAt(0).toUpperCase() + things.slice(1));
    const paint = () => {
      const needle = shell.search.value.trim().toLowerCase();
      const items = [...(none ? [{ icon: "ph:minus", label: none, about: "", value: "" }] : []), ...refs.filter((p) => allow(p)).map((p) => ({ icon: "ph:user-circle", label: p.label, about: p.id, value: p.id }))]
        .filter((i) => !needle || i.label.toLowerCase().includes(needle));
      box.fill(items, needle, { icon: "ph:users", title: `No ${things.replace(/s$/, "")} matches`, text: "Try other words." });
    };
    shell.search.addEventListener("input", paint);
    paint();
    new Promise((resolve) => shell.open(resolve)).then((id) => id !== undefined && id !== null && done(id));
  }

  function itemsFor(S, key) {
    const f = find(S, key);
    const n = f.node;
    const A = S.k;
    const say = (text) => kit.commit(S, text);
    const sub = (title, list, current, set) => ({ label: `ph:caret-right ${title}`, group: "edit", items: list.map(([value, name]) => ({ label: `${value === current ? "ph:check" : "ph:square"} ${name}`, run: () => set(value) })) });
    const numbering = { label: `${S.m.autonumber ? "ph:check-square" : "ph:square"} Number the messages`, group: "edit", run: () => (S.m.autonumber ? delete S.m.autonumber : (S.m.autonumber = true), say(S.m.autonumber ? "Messages are numbered." : "Messages are not numbered.")) };
    const items = [{ label: "ph:pencil-simple Rename", run: () => relabel(S, key), group: "edit" }];
    if (A.name === "mindmap") items.push(sub("Shape", ops.SHAPES.map((s) => [s, MM_NAME[s]]), n.shape || "default", (shape) => (delete n.raw, (n.shape = shape), say(`${nameOf(S, key)} is now ${MM_NAME[shape].toLowerCase()}.`))));
    if (A.menu) items.push(...A.menu({ S, n, key, say, sub, pickWho, nameOf, prompt: promptDialog }));
    else if (n.type === "m") {
      items.push(
        { label: "ph:arrow-line-left From…", group: "edit", run: () => pickWho(S, "Message from", () => true, (id) => ((n.from = id), say(`Message now comes from ${whoLabel(S, id)}.`))) },
        { label: "ph:arrow-line-right To…", group: "edit", run: () => pickWho(S, "Message to", () => true, (id) => ((n.to = id), say(`Message now goes to ${whoLabel(S, id)}.`))) },
        sub("Arrow", Object.entries(ops.ARROWS), n.arrow, (arrow) => ((n.arrow = arrow), say(`Arrow is now ${ops.ARROWS[arrow].toLowerCase()}.`))),
        sub("Activation", [["", "None"], ["+", "Activate the receiver"], ["-", "Deactivate the sender"]], n.act, (act) => ((n.act = act), say("Activation changed."))),
        //: L-documents-56: a message can make its receiver appear (`create`) or end a participant (`destroy`); autonumber is the diagram's.
        sub("Lifetime", [["", "Neither"], ["create", "Creates the receiver"], ["destroy-to", "Destroys the receiver"], ["destroy-from", "Destroys the sender"]], n.create ? "create" : n.destroy ? `destroy-${n.destroy === n.to ? "to" : "from"}` : "", (v) => {
          delete n.create;
          delete n.destroy;
          if (v === "create") n.create = n.to;
          else if (v) n.destroy = v === "destroy-to" ? n.to : n.from;
          say(v ? `Message ${v === "create" ? "creates" : "destroys"} a participant.` : "Message ends no participant.");
        }),
        numbering,
      );
    } else if (n.type === "t") {
      items.push(
        sub("Position", Object.entries(PAD), n.pos, (pos) => ((n.pos = pos), (n.who = pos === "over" ? n.who : n.who.slice(0, 1)), say(`Note is now ${pos}.`))),
        { label: "ph:user-circle About…", group: "edit", run: () => pickWho(S, "Note about", () => true, (id) => ((n.who = [id, ...n.who.slice(1)]), say(`Note is now about ${whoLabel(S, id)}.`))) },
        ...(n.pos === "over" ? [{ label: "ph:users Also about…", group: "edit", run: () => pickWho(S, "Note also about", (p) => p.id !== n.who[0], (id) => ((n.who = id ? [n.who[0], id] : [n.who[0]]), say(id ? `Note now spans to ${whoLabel(S, id)}.` : "Note is about one participant.")), "Just one") }] : []),
      );
    } else if (n.type === "b") items.push(...(n.kw === "rect" ? [{ label: "ph:palette Colour…", group: "edit", run: () => openSheet({ label: "Colour of the highlight", sub: "Tints the steps inside. Pale blue is the default.", name: "diagram-colour", build: (card, close) => {
      card.classList.add("swatch-card");
      card.append(swatchPicker({ label: "Colour", value: null, onChange: () => {}, onChoose: (key) => {
        close();
        const [r, g, b] = key ? CATEGORY_PALETTE[key].slice(1).match(/\w\w/g).map((x) => parseInt(x, 16)) : [191, 223, 255];
        n.text = `rgba(${r}, ${g}, ${b}, ${key ? 0.3 : 1})`;
        say(`Highlight is now ${key || "pale blue"}.`);
      }, none: "Pale blue" }));
    } }) }] : []), sub("Kind", SEQ_BLOCKS.map((b) => [b, b]), n.kw, (kw) => ((n.kw = kw), say(`Block is now a ${kw}.`))));
    else if (n.type === "d") items.push(sub("Word", [["else", "else"], ["and", "and"], ["option", "option"]], n.kw, (kw) => ((n.kw = kw), say(`Divider is now ${kw}.`))));
    else if (n.type === "a") items.push({ label: "ph:selection Box…", group: "edit", run: async () => {
      const text = await promptDialog(`Box around ${n.label} (the words on its edge; blank takes it out)`, n.box || "", { confirmLabel: "Save" });
      if (text == null) return;
      if (text.trim()) n.box = text.trim();
      else delete n.box;
      say(n.box ? `${n.label} sits in the box ${n.box}.` : `${n.label} is out of its box.`);
    } }, numbering, { label: n.actor ? "ph:user-circle Make it a participant" : "ph:user Make it an actor", group: "edit", run: () => ((n.actor = !n.actor), say(`${n.label} is now ${n.actor ? "an actor" : "a participant"}.`)) });
    if (!f.level.fixed) {
      items.push(
        { label: "ph:arrow-up Move up", run: () => stepBlock(S, key, -1), group: "move" },
        { label: "ph:arrow-down Move down", run: () => stepBlock(S, key, 1), group: "move" },
        { label: "ph:arrow-line-right Nest into the block above", run: () => nestBlock(S, key, true), group: "move" },
        { label: "ph:arrow-line-left Lift out", run: () => nestBlock(S, key, false), group: "move" },
        { label: "ph:trash Delete", danger: true, run: () => removeBlock(S, key), group: "end" },
      );
    }
    return items;
  }

  // --- gestures -------------------------------------------------------------------
  function relabel(S, key) {
    const b = kit.blockEl(S, key);
    if (!b || key[0] === "k") return;
    const was = nameOf(S, key);
    kit.beginEdit(S, b.querySelector(":scope > .dgm-card > .dgm-label"), was, (text) => {
      if (!ops.relabel(S.k, S.m, key, text)) return;
      if (text === was && S.source === S.k.print(S.m)) return render(S);
      kit.commit(S, `Renamed to ${text}.`);
    }, key);
  }

  //: A tile's block, after the selection, inside it, or at a drop's `spot`. The sequence adds the
  //: participants a first message needs, a blank mind map its central idea.
  //: `fields` overrides the tile's (the picture names a message's two ends); `wrap` is a step the new box takes in (a Loop dropped on a message).
  function addTile(S, tile, { sel: asked, spot = null, edit = true, fields: given = null, wrap = null } = {}) {
    const A = S.k;
    const m = S.m;
    //: A sequence diagram names the new part on its picture (diagram-seq-canvas.js), as a mind map and a timeline do with their
    //: list folded (a field in a hidden row held the redraw, 1661 m); else in the list.
    const name = () => (edit ? (S.seq || (S.hitAt && S.pane.offsetParent === null) ? (S.seqOpen = S.sel) : relabel(S, S.sel)) : null);
    if (ops.count(A, m) >= ops.MAX - 4) return kit.say(S, `A diagram holds at most ${ops.MAX} blocks.`);
    //: A blank mind map gets its central idea and nothing else: it is named first, then Branch grows it (dgbt-1109 4).
    if (A.start && !m.root) {
      S.sel = ops.key(A.start(m));
      S.fresh = null;
      kit.commit(S, "Added the central idea. Name it, then add branches.");
      return name(), S.sel;
    }
    //: Branch twice in a row makes sisters: the block it just made is still the pick, and a child of that child was the surprise
    //: (Food under Hotels). A block picked by hand (`S.fresh` cleared) takes its own children (dgbt-1109 5).
    //: Only for a press of the Add tile or shelf: a key on a block (`sel` given) means that block.
    const picked = asked === undefined ? S.sel : asked;
    const fresh = tile.into && asked === undefined && !spot && !wrap && picked && picked === S.fresh ? find(S, picked)?.parent : null;
    const sel = fresh ? ops.key(fresh) : picked;
    const at = sel && find(S, sel)?.node;
    const under = wrap && find(S, wrap);
    const place = spot || (under && { parent: under.parent, before: under.node }) || ops.spot(A, m, tile.type, sel, Boolean(tile.into));
    if (!place) return kit.say(S, A.hint(tile.type));
    const { fields, made } = A.defaults ? A.defaults(m, tile, at) : { fields: tile.fields, made: 0 };
    const node = ops.add(A, m, tile.type, { parent: place.parent, before: place.before, fields: { ...fields, ...given } });
    if (!node) return kit.say(S, A.hint(tile.type));
    if (under && node.steps) (under.list.splice(under.list.indexOf(under.node), 1), node.steps.splice(0, 1, under.node));
    S.tile = tile;
    S.sel = ops.key(node);
    S.fresh = tile.into && !spot ? S.sel : null;
    const where = A.name === "mindmap" && place.parent ? ` ${tile.into ? "under" : "next to"} ${A.text(place.parent)}` : "";
    kit.commit(S, `Added ${tile.name.toLowerCase()}${where}${made ? ` and ${made} ${(A.made || ["participant", "participants"])[made === 1 ? 0 : 1]}` : ""}.`);
    name();
    return S.sel;
  }

  function stepBlock(S, key, dir) {
    if (key[0] === "k") return;
    if (!ops.step(S.k, S.m, key, dir)) return kit.say(S, `${nameOf(S, key)} is already ${dir < 0 ? "first" : "last"}.`);
    kit.commit(S, `Moved ${nameOf(S, key)} ${dir < 0 ? "up" : "down"}.`);
  }

  function nestBlock(S, key, into) {
    if (key[0] === "k") return;
    if (!(into ? ops.nest(S.k, S.m, key) : ops.lift(S.k, S.m, key))) return kit.say(S, into ? "There is no block above that can hold it." : `${nameOf(S, key)} cannot come out of where it is.`);
    kit.commit(S, into ? `Nested ${nameOf(S, key)}.` : `Lifted ${nameOf(S, key)} out.`);
  }

  function removeBlock(S, key) {
    if (key[0] === "k") return;
    const f = find(S, key);
    const near = f && f.list[f.list.indexOf(f.node) + 1] || f?.list[f.list.indexOf(f.node) - 1] || f?.parent;
    const name = nameOf(S, key);
    const gone = ops.remove(S.k, S.m, key);
    if (!gone) return kit.say(S, "The central idea stays. Delete its branches instead.");
    S.sel = near && near.type !== "k" ? ops.key(near) : null;
    const extra = [gone.count > 1 ? `${gone.count - 1} inside` : "", gone.joins ? `${gone.joins} ${(S.k.joinWords || ["message", "messages"])[gone.joins === 1 ? 0 : 1]}` : ""].filter(Boolean);
    kit.commit(S, `Deleted ${name}${extra.length ? ` with ${extra.join(", ")}` : ""}.`);
  }

  // --- keyboard -------------------------------------------------------------------
  function onKey(S, event) {
    const block = event.target.closest?.(".dgm-block");
    if (event.target.isContentEditable || !block || event.target.closest(".menu-wrap")) return;
    const key = block.dataset.key;
    const all = [...S.tree.querySelectorAll(".dgm-block")];
    const at = all.indexOf(block);
    const go = (target) => target && pick(S, target.dataset.key, true);
    const mod = event.ctrlKey || event.metaKey;
    if (mod && !event.altKey && /^[zy]$/i.test(event.key)) {
      event.preventDefault();
      event.stopPropagation();
      return event.shiftKey || /y/i.test(event.key) ? S.io.redo() : S.io.undo();
    }
    if (event.altKey && !mod) {
      const act = { ArrowUp: () => stepBlock(S, key, -1), ArrowDown: () => stepBlock(S, key, 1), ArrowRight: () => nestBlock(S, key, true), ArrowLeft: () => nestBlock(S, key, false) }[event.key];
      if (!act) return;
      event.preventDefault();
      event.stopPropagation();
      return act();
    }
    if (mod || event.shiftKey && event.key !== "F10") return;
    const tile = S.k.tiles.find((t) => t.key === event.key.toLowerCase());
    const primary = S.k.tiles.find((t) => t.id === (S.tile?.id || S.k.primary));
    const act = {
      ArrowDown: () => go(all[at + 1]), ArrowUp: () => go(all[at - 1]), Home: () => go(all[0]), End: () => go(all.at(-1)),
      ArrowLeft: () => go(block.parentElement.closest(".dgm-block")), ArrowRight: () => go(block.querySelector(".dgm-block")),
      Enter: () => relabel(S, key), F2: () => relabel(S, key), Insert: () => addTile(S, primary, { sel: key }),
      Delete: () => removeBlock(S, key), Backspace: () => removeBlock(S, key),
      ContextMenu: () => menuAt(S, block), F10: () => menuAt(S, block),
    }[event.key] || (tile && (() => addTile(S, tile, { sel: key })));
    if (!act || (key[0] === "k" && !/^Arrow|^Home$|^End$/.test(event.key))) return;
    event.preventDefault();
    act();
  }

  function menuAt(S, block) {
    if (block.dataset.key[0] === "k") return;
    const r = block.querySelector(".dgm-card").getBoundingClientRect();
    openMenuAtPoint(itemsFor(S, block.dataset.key), "Block menu", r.left + r.width / 2, r.bottom, block);
  }

  // --- the pointer mode: obj-drag.js's one gesture, ahead of carry ------------------
  function seedBlock(event) {
    const target = event.target;
    const tile = target.closest?.(".dgm-tile[data-tile]");
    const block = target.closest?.(".dgm-card")?.closest(".dgm-block");
    //: A press on a mind map's or a timeline's drawn part carries its row, as the row's grip does (diagram-tree-canvas.js).
    const drawn = !tile && !block && diagramModel.treeCanvas?.node(event, panes);
    if (drawn) return { card: drawn.box, ref: { kind: "block", id: drawn.key, title: nameOf(drawn.S, drawn.key) }, grip: event.pointerType !== "touch", S: drawn.S, key: drawn.key, tile: null };
    const root = (tile || block)?.closest(".dgm");
    const S = root && panes.get(root);
    if (!S || target.closest(".menu-wrap, [contenteditable]") || (block && (block.classList.contains("dgm-kept") || find(S, block.dataset.key)?.level.fixed))) return null;
    const def = tile && S.k.tiles.find((t) => t.id === tile.dataset.tile);
    const key = tile ? null : block.dataset.key;
    return { card: tile || block.querySelector(":scope > .dgm-card"), ref: { kind: "block", id: key || def.id, title: tile ? def.name : nameOf(S, key) }, grip: Boolean(target.closest("[data-obj-grip]")), S, key, tile: def };
  }

  //: A shelf tile dropped on a mind map or timeline picture (INBOX 1661 l) off its parts is added where a press on the tile adds
  //: it, after the selection; the whole picture takes the drop mark. Over a part, diagram-tree-canvas.js `over` names the place.
  function pictureDrop(S, at, tile) {
    const stage = S.fig?.parentElement;
    return stage?.contains(at) && !at.closest(".dgm-shelf") ? diagramModel.treeCanvas?.landing(S, tile) || { canvas: true, op: "into", card: S.fig, add: {}, word: S.sel ? "After the selection" : "Add it here" } : null;
  }

  //: Where a drop would land: before or after a block (its top or bottom edge), or into it.
  function dropAt(g) {
    const { S, key } = g;
    const A = S.k;
    const at = document.elementFromPoint(g.x, g.y);
    if (!at || !S.pane.contains(at)) return S.seq ? (g.tile ? diagramModel.seqCanvas.over(g) : null) : diagramModel.treeCanvas?.over(g) || (g.tile ? pictureDrop(S, at, g.tile) : null);
    if (S.seq) diagramModel.seqCanvas.clear(S);
    const dragged = key ? find(S, key) : null;
    const type = dragged ? dragged.node.type : g.tile.type;
    const block = at.closest(".dgm-block");
    if (!block) return ops.level(A, S.m, null, type) ? { op: "into", parent: null, before: null } : null;
    const over = block.dataset.key;
    const f = over[0] === "k" ? null : find(S, over);
    if (!f || (dragged && (over === key || withinNode(A, S.m, f.node, dragged.node)))) return null;
    const card = block.querySelector(":scope > .dgm-card");
    const r = card.getBoundingClientRect();
    const frac = (g.y - r.top) / r.height;
    const holds = ops.level(A, S.m, f.node, type);
    const beside = ops.level(A, S.m, f.parent, type);
    const next = f.list[f.list.indexOf(f.node) + 1] || null;
    if (beside && (frac < 0.28 || (!holds && frac < 0.5))) return { op: "before", parent: f.parent, before: f.node, card };
    if (beside && (frac > 0.72 || !holds)) return { op: "after", parent: f.parent, before: beside.list === f.list ? next : null, card, below: true };
    return holds ? { op: "into", parent: f.node, before: null, card } : null;
  }
  const withinNode = (A, m, node, ancestor) => {
    let hit = node === ancestor;
    ops.walk(A, m, (n) => n === node && (hit = true), ancestor);
    return hit;
  };

  function dropApply(g, target) {
    const { S } = g;
    const spot = target.canvas && !("parent" in target) ? null : { parent: target.parent, before: target.before };
    if (g.tile) return addTile(S, g.tile, { spot, edit: false, ...target.add });
    const to = target.parent ? ops.key(target.parent) : null;
    if (!ops.move(S.k, S.m, g.key, to, target.before ? ops.key(target.before) : null)) return;
    S.sel = g.key;
    kit.commit(S, target.op === "into" ? `Nested ${nameOf(S, g.key)} into ${S.k.text(target.parent)}.` : `Moved ${nameOf(S, g.key)}.`);
  }

  const KIND_MODE = {
    ancestors: true,
    seed: seedBlock,
    grab: () => ({}),
    begin(g) {
      g.scroller = g.S.pane;
      g.dragEl = g.tile ? null : kit.blockEl(g.S, g.key);
      g.dragEl?.classList.add("dgm-lifted");
    },
    update(g) {
      g.target = dropAt(g);
      kit.dropMark(g, g.target);
    },
    drop(g) {
      kit.dropMark(g, null);
      if (g.S.seq) diagramModel.seqCanvas.clear(g.S);
      g.dragEl?.classList.remove("dgm-lifted");
      if (g.target) dropApply(g, g.target);
    },
    cancel(g) {
      kit.dropMark(g, null);
      if (g.S.seq) diagramModel.seqCanvas.clear(g.S);
      g.dragEl?.classList.remove("dgm-lifted");
    },
  };

  // --- building the pane ----------------------------------------------------------
  const EMPTY = {
    mindmap: ["Start a mind map", "Press Add, then Branch for the central idea. Name it, then Branch and Leaf grow it. Drag blocks to move or nest them."],
    timeline: ["Start a timeline", "Press Add, then Section or Period to begin, then Event for what happened. A Section groups periods."],
    sequence: ["Start a sequence diagram", "Press Add, then Message to add two participants and the first message. A Loop or an Alt wraps steps."],
  };

  function buildPalette(S) {
    const bar = kit.el("div", "dock dgm-dock");
    bar.dataset.dockName = "diagram";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Diagram blocks");
    //: The Add library (diagram-library.js): the tiles by meaning, each with its hint.
    //: The same specs are the picture's shelf (diagram-library.js `shelf`, asked for by the builder once the picture has its stage).
    S.specs = S.k.tiles.map((t) => ({
      group: t.group, name: t.name, hint: `Adds ${t.about}.`, glyph: icon(t.icon), keys: t.key.toUpperCase(),
      label: `Add ${t.name.toLowerCase()}. Adds ${t.about}.`, data: { tile: t.id }, press: () => addTile(S, t),
    }));
    const tiles = diagramModel.library.build(S.specs);
    const actions = kit.el("div", "dock-actions");
    S.suggestBtn = smallButton("ph:sparkle Suggest", "Start from a template, your notes or a description", () => kit.suggestMenu(S, S.suggestBtn));
    S.suggestBtn.classList.add("dgm-suggest");
    S.suggestBtn.setAttribute("aria-haspopup", "menu");
    actions.append(S.suggestBtn);
    for (const [name, label, tip, run] of [["ph:arrow-counter-clockwise", "Undo", "Undo, Ctrl+Z", () => S.io.undo()], ["ph:arrow-clockwise", "Redo", "Redo, Ctrl+Y", () => S.io.redo()]]) {
      const b = smallButton(name, tip, run);
      b.classList.add("icon-only", "dgm-hist");
      if (label === "Redo") b.classList.add("dgm-redo");
      b.setAttribute("aria-label", label);
      actions.append(b);
    }
    actions.append(...[diagramModel.kindbar?.expand(S)].filter(Boolean), kit.more(S));
    bar.append(tiles, kit.el("div", "dock-group"), actions, tiles.hint);
    return bar;
  }

  function mount(host, io, text, A) {
    host.replaceChildren();
    const root = kit.el("div", "dgm");
    root.dataset.kind = A.name;
    const S = { host, root, io, source: text, k: A, m: null, sel: null, tile: null, drawn: 0, hit: null, tidy: false };
    S.live = kit.el("p", "visually-hidden dgm-live");
    S.live.setAttribute("role", "status");
    S.live.setAttribute("aria-live", "polite");
    S.tree = kit.el("div", "dgm-tree");
    S.tree.setAttribute("role", "tree");
    S.tree.setAttribute("aria-label", "Diagram blocks");
    S.empty = kit.el("div", "empty-state dgm-empty");
    const start = smallButton("ph:layout Start from a template", `Pick a starting ${A.noun}`, () => kit.suggest(S, "templates"), false);
    start.classList.add("accent");
    S.empty.append(kit.el("p", "empty-title", (EMPTY[A.name] || A.empty_text)[0]), kit.el("p", "", (EMPTY[A.name] || A.empty_text)[1]), start);
    S.ghosts = kit.el("div", "dgm-ghosts hidden");
    S.drop = kit.el("div", "dgm-drop hidden");
    S.pane = kit.el("div", "dgm-pane");
    S.pane.setAttribute("aria-label", `Diagram blocks. Press ${A.tiles.map((t) => t.key.toUpperCase()).join(", ")} to add one.`);
    S.pane.setAttribute("role", "region");
    S.pane.append(S.tree, S.empty, S.ghosts, S.drop);
    S.fig = kit.el("figure", "dgm-picture");
    const body = kit.el("div", "dgm-body");
    body.append(S.pane, S.fig);
    S.note = kit.el("p", "muted dgm-hint hidden", "");
    root.append(buildPalette(S), S.note, body, S.live);
    diagramModel.kindbar?.mount(S, kit);
    host.append(root);
    panes.set(root, S);
    root.addEventListener("keydown", (event) => diagramModel.kindbar.historyKey(S, event));
    S.tree.addEventListener("keydown", (event) => onKey(S, event));
    S.tree.addEventListener("click", (event) => {
      const block = event.target.closest(".dgm-block");
      if (block && !event.target.closest(".menu-wrap")) pick(S, block.dataset.key);
    });
    S.tree.addEventListener("dblclick", (event) => {
      const block = event.target.closest(".dgm-label")?.closest(".dgm-block");
      if (block && block.dataset.key[0] !== "k") relabel(S, block.dataset.key);
    });
    S.tree.addEventListener("contextmenu", (event) => {
      const block = event.target.closest(".dgm-block");
      if (!block || block.dataset.key[0] === "k") return;
      event.preventDefault();
      openMenuAtPoint(itemsFor(S, block.dataset.key), "Block menu", event.clientX, event.clientY, block);
    });
    wireLongPress(S.tree, (event, point) => {
      const block = event.target.closest?.(".dgm-block");
      if (block && block.dataset.key[0] !== "k") openMenuAtPoint(itemsFor(S, block.dataset.key), "Block menu", point.x, point.y, block);
    });
    S.pane.addEventListener("keydown", (event) => {
      const tile = event.target === S.pane && !event.ctrlKey && !event.metaKey && !event.altKey && A.tiles.find((t) => t.key === event.key.toLowerCase());
      if (!tile) return;
      //: Not left to the page: the new block's name is already being edited, and the letter would land in it.
      event.preventDefault();
      addTile(S, tile, { sel: null });
    });
    sync(host, text, S);
    return S;
  }

  //: Reads the source into the model. One this kind's reader cannot take (a second mind map root,
  //: `box` or `create` in a sequence) or over the limit is its picture alone with one line saying why.
  function sync(host, text, S = panes.get(host.querySelector(":scope > .dgm"))) {
    if (!S) return null;
    const A = S.k;
    S.source = text;
    const read = A.parse(text);
    const big = Boolean(read && ops.count(A, read) > ops.MAX);
    const parsed = big ? null : read;
    S.tidy = Boolean(parsed && text.trim() && A.print(parsed) !== text);
    S.plain = !parsed;
    S.root.classList.toggle("dgm-plain", !parsed);
    S.note.classList.toggle("hidden", Boolean(parsed));
    S.note.textContent = parsed ? "" : big ? `This diagram has more than ${ops.MAX} blocks, so it opens in Source with its picture.` : `Blocks cannot read this ${A.noun}, so it opens in Source with its picture.`;
    S.m = parsed || A.empty();
    //: With a block the phone's list is a sheet (diagram-touch.js) and the picture takes the page, as a flowchart's with an arrow.
    S.root.classList.toggle("dgm-listless", !A.blank(S.m));
    if (!parsed) S.ghosts.replaceChildren(), S.ghosts.classList.add("hidden");
    S.pane.classList.toggle("hidden", !parsed);
    render(S);
    kit.drawPicture(S);
    return S;
  }

  //: What the ghosts layer (diagram-suggest.js) needs of a suggestion of this kind: a row per block with
  //: its glyph and words, the keys that go with a block (everything inside it), and the merge itself.
  function ghostSpec(S, inc) {
    const A = S.k;
    const nodes = [];
    ops.walk(A, inc, (n, _level, _parent, depth) => n.type !== "k" && nodes.push({ n, depth }));
    return {
      rows: nodes.map(({ n, depth }) => {
        const { meta, kind } = words({ k: A, m: inc }, n);
        return { key: ops.key(n), level: depth, glyph: glyph(S, n), text: A.text(n), meta, aria: `${A.text(n)}, ${kind}${meta ? `, ${meta}` : ""}` };
      }),
      subtree(key) {
        const keys = [key];
        const at = nodes.find((x) => ops.key(x.n) === key)?.n;
        if (at) ops.walk(A, inc, (n) => n.type !== "k" && keys.push(ops.key(n)), at);
        return keys;
      },
      merge(take) {
        const done = ops.merge(A, S.m, inc, take);
        return { count: done.added, skipped: done.skipped, sel: done.first };
      },
    };
  }

  //: What the builder calls for a source of this kind: the pane in `host`, mounted once, then only told the source.
  function show(host, io, text, name, helpers) {
    kit = helpers;
    const A = diagramKinds[name];
    if (!A) return null;
    A.render = render;
    if (typeof OBJ_MODES === "object" && !OBJ_MODES.diagramKind) OBJ_MODES.diagramKind = KIND_MODE;
    const S = panes.get(host.querySelector(":scope > .dgm"));
    if (!S || S.k !== A) return mount(host, io, text, A);
    S.io = io;
    return text === S.source ? S : sync(host, text, S);
  }

  //: What the picture (diagram-seq-canvas.js) does to a row: the same steps the list's keys take, with the same lines said.
  const act = {
    select: (S, key) => pick(S, key),
    name: nameOf,
    rename(S, key, text) {
      if (text === nameOf(S, key) || !ops.relabel(S.k, S.m, key, text)) return;
      kit.commit(S, `Renamed to ${text}.`);
    },
    remove: removeBlock,
    step: stepBlock,
    add: addTile,
    //: A participant to just before `before` (null: last), from a drag of its head on the picture; no change, no commit.
    shift(S, key, before) {
      const was = S.k.print(S.m);
      if (!ops.move(S.k, S.m, key, null, before) || S.k.print(S.m) === was) return false;
      S.sel = key;
      kit.commit(S, `Moved ${nameOf(S, key)}.`);
      return true;
    },
  };

  //: The five kinds of diagram-kinds-more.js (L-documents-57) join `diagramKinds` when that file loads; `load` fetches it for them.
  const MORE = /^(gantt|pie|state|class|er)$/;
  const load = (name) => (MORE.test(name) && !diagramKinds[name] ? lazyScript("/js/diagram-kinds-more.js") : true);
  diagramModel.kinds = { mindmap, timeline, sequence, ops, show, load, MORE, registry: diagramKinds, ghostSpec, act };
})();
