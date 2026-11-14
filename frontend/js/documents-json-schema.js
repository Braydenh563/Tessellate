// documents-json-schema.js: JSON Schema lint and key completion for a .json document (DOCUMENTS_PLAN, L-documents-42).
//
// A .json file whose top-level object has "$schema" is checked against that schema and completes its property keys.
// **Loaded on the first check of such a file**, by `lazyScript` in documents-code.js, which then calls
// `DOC_LINT_CONFIG.jsonSchema` (a field of an existing const, so the shared scope gains no name).
//
// **The schema comes from the library, never the network** (the app is offline): "$schema" is matched against the
// title of a .json document, with or without ".json", or against the last segment of a path or URL
// ("./person.schema.json" finds the document titled person.schema.json). A schema not found is one note on the
// "$schema" value, and the file is not checked. No schema set is bundled: none existed to reuse.
//
// **The validator is a draft-07 subset**, in-house: type, properties, required, additionalProperties (false or a
// schema), enum, items (a schema or a list), minimum, maximum, and "$ref" to "#" or "#/definitions/x" (also "#/$defs/x")
// inside the same schema. Everything else in a schema is ignored, never an error. Ranges come from CodeMirror's own JSON
// parse tree (the pointer-to-node idea of codemirror-json-schema, written here, none of its code): the tree is read once
// into a small value tree whose every node carries its source range, and a finding is a node's range.
(() => {
  const TYPES = { object: "an object", array: "an array", string: "a string", number: "a number", integer: "an integer", boolean: "true or false", null: "null" };
  const VALUES = ["Object", "Array", "String", "Number", "True", "False", "Null"];

  //: The value tree: {kind, from, to, value, props: [{key, keyFrom, keyTo, value}], items}. A tree with error nodes
  //: (a key typed with no value yet) still reads: a property with no value gets `value: null`.
  function read(CM, state) {
    const tree = CM.language.ensureSyntaxTree(state, state.doc.length, 200) || CM.language.syntaxTree(state);
    const text = (n) => state.sliceDoc(n.from, n.to);
    const parse = (n, fallback) => {
      try { return JSON.parse(text(n)); } catch { return fallback; }
    };
    const build = (n) => {
      const at = { from: n.from, to: n.to };
      if (n.name === "Object") {
        const props = [];
        for (let c = n.node.firstChild; c; c = c.nextSibling) {
          const name = c.name === "Property" ? c.node.getChild("PropertyName") : null;
          if (!name) continue;
          let value = null;
          for (let v = name.node.nextSibling; v; v = v.nextSibling) {
            if (VALUES.includes(v.name)) { value = build(v); break; }
          }
          props.push({ key: parse(name, text(name).replace(/^"|"$/g, "")), keyFrom: name.from, keyTo: name.to, value });
        }
        return { kind: "object", ...at, props };
      }
      if (n.name === "Array") {
        const items = [];
        for (let c = n.node.firstChild; c; c = c.nextSibling) if (VALUES.includes(c.name)) items.push(build(c));
        return { kind: "array", ...at, items };
      }
      if (n.name === "String") return { kind: "string", ...at, value: parse(n, text(n).slice(1, -1)) };
      if (n.name === "Number") return { kind: "number", ...at, value: Number(text(n)) };
      if (n.name === "True" || n.name === "False") return { kind: "boolean", ...at, value: n.name === "True" };
      return { kind: "null", ...at, value: null };
    };
    for (let c = tree.topNode.firstChild; c; c = c.nextSibling) if (c.name === "Object") return build(c);
    return null;
  }

  const plain = (node) => {
    if (!node) return undefined;
    if (node.kind === "object") return Object.fromEntries(node.props.map((p) => [p.key, plain(p.value)]));
    if (node.kind === "array") return node.items.map(plain);
    return node.value;
  };

  //: "#" or "#/definitions/x": a JSON pointer into the same schema, `~1` and `~0` decoded. Anything else is left alone
  //: (an empty schema accepts everything). Chains are cut at 20 hops.
  function deref(schema, root) {
    let at = schema;
    for (let i = 0; at && typeof at === "object" && typeof at.$ref === "string"; i += 1) {
      const ref = at.$ref;
      if ((ref !== "#" && !ref.startsWith("#/")) || i >= 20) return {};
      let hit = root;
      for (const part of ref === "#" ? [] : ref.slice(2).split("/")) hit = hit && typeof hit === "object" ? hit[part.replace(/~1/g, "/").replace(/~0/g, "~")] : undefined;
      if (!hit || typeof hit !== "object") return {};
      at = hit;
    }
    return at && typeof at === "object" ? at : {};
  }

  const kindOf = (node) => (node.kind === "number" && Number.isInteger(node.value) ? "integer" : node.kind);
  const typeOk = (want, node) => want === node.kind || (want === "integer" && kindOf(node) === "integer");
  const show = (v) => JSON.stringify(v);

  //: Findings for one value against one schema, pushed on `out` as {from, to, severity, message, source}. `root` is the
  //: whole schema, for "$ref" from anywhere inside it.
  function check(node, schemaIn, root, out) {
    const schema = deref(schemaIn, root);
    const hit = (from, to, message) => out.push({ from, to, severity: "warning", message, source: "Schema" });
    if (schema.type !== undefined) {
      const wants = [].concat(schema.type);
      if (!wants.some((w) => typeOk(w, node))) {
        hit(node.from, node.to, `Expected ${wants.map((w) => TYPES[w] || w).join(" or ")}, found ${TYPES[kindOf(node)] || node.kind}.`);
        return;
      }
    }
    if (Array.isArray(schema.enum)) {
      const value = show(plain(node));
      if (!schema.enum.some((e) => show(e) === value)) hit(node.from, node.to, `Not one of ${schema.enum.slice(0, 6).map(show).join(", ")}${schema.enum.length > 6 ? ", and more" : ""}.`);
    }
    if (node.kind === "number") {
      if (typeof schema.minimum === "number" && node.value < schema.minimum) hit(node.from, node.to, `Below the minimum of ${schema.minimum}.`);
      if (typeof schema.maximum === "number" && node.value > schema.maximum) hit(node.from, node.to, `Above the maximum of ${schema.maximum}.`);
    }
    if (node.kind === "object") {
      const props = schema.properties && typeof schema.properties === "object" ? schema.properties : {};
      for (const name of Array.isArray(schema.required) ? schema.required : []) {
        if (!node.props.some((p) => p.key === name)) hit(node.from, node.from + 1, `Missing required property ${show(name)}.`);
      }
      for (const prop of node.props) {
        if (Object.hasOwn(props, prop.key)) {
          if (prop.value) check(prop.value, props[prop.key], root, out);
        } else if (schema.additionalProperties === false) {
          if (prop.key !== "$schema") hit(prop.keyFrom, prop.keyTo, `${show(prop.key)} is not allowed here.`);
        } else if (schema.additionalProperties && typeof schema.additionalProperties === "object" && prop.value) {
          check(prop.value, schema.additionalProperties, root, out);
        }
      }
    }
    if (node.kind === "array" && schema.items) {
      node.items.forEach((item, i) => {
        const sub = Array.isArray(schema.items) ? schema.items[i] : schema.items;
        if (sub && typeof sub === "object") check(item, sub, root, out);
      });
    }
  }

  //: Which library document a "$schema" value names: a .json document's title, with or without ".json", or the last
  //: segment of a path or URL. A remote URL is only ever matched this way, never fetched.
  function findDoc(docs, ref) {
    const last = String(ref).split(/[/\\]/).pop().replace(/[#?].*$/, "").toLowerCase();
    const names = new Set([String(ref).toLowerCase(), last, last.replace(/\.json$/, "")]);
    return docs.find((d) => {
      const title = String(d.title || "").toLowerCase();
      return d.file_type === "json" && (names.has(title) || names.has(title.replace(/\.json$/, "")));
    }) || null;
  }

  //: The running app's own library list and API; a test passes its own.
  const live = { docs: () => docs, api: (path) => apiJson(path, { silent: true }) };

  const cache = new Map();
  async function loadSchema(doc, api) {
    const kept = cache.get(doc.id);
    if (kept && Date.now() - kept.at < 3000) return kept.schema;
    let schema = null;
    try {
      const parsed = JSON.parse((await api(`/documents/${doc.id}`)).content || "");
      if (parsed && typeof parsed === "object") schema = parsed;
    } catch { /* an unreadable schema is no schema */ }
    cache.set(doc.id, { at: Date.now(), schema });
    return schema;
  }

  //: What a state's "$schema" resolves to: null (no "$schema" key), {root, tag} (not in the library) or {root, tag, schema}.
  async function schemaFor(CM, state, env = live) {
    const root = read(CM, state);
    const tag = root && root.props.find((p) => p.key === "$schema" && p.value && p.value.kind === "string");
    if (!tag) return null;
    const doc = findDoc(env.docs(), tag.value.value);
    const schema = doc ? await loadSchema(doc, env.api) : null;
    return schema ? { root, tag, schema } : { root, tag };
  }

  async function diagnostics(CM, state, env = live) {
    const got = await schemaFor(CM, state, env);
    if (!got) return [];
    if (!got.schema) return [{ from: got.tag.value.from, to: got.tag.value.to, severity: "info", source: "Schema", message: "This schema is not in the library, so the file is not checked against it." }];
    const out = [];
    check(got.root, got.schema, got.schema, out);
    return out;
  }

  //: The schema for the value at a path of keys and indexes (a JSON pointer's segments), or null.
  function schemaAt(schema, path) {
    let at = deref(schema, schema);
    for (const seg of path) {
      if (typeof seg === "number") at = Array.isArray(at.items) ? at.items[seg] : at.items;
      else at = at.properties && Object.hasOwn(at.properties, seg) ? at.properties[seg] : at.additionalProperties;
      if (!at || typeof at !== "object") return null;
      at = deref(at, schema);
    }
    return at;
  }

  //: The object a key would go in at `pos`, with the path to it, or null when `pos` is in a value.
  function objectAt(root, pos) {
    const path = [];
    let node = root;
    while (node) {
      if (node.kind === "array") {
        const i = node.items.findIndex((it) => pos >= it.from && pos <= it.to);
        if (i < 0) return null;
        path.push(i);
        node = node.items[i];
        continue;
      }
      if (node.kind !== "object" || pos <= node.from) return null;
      const into = node.props.find((p) => p.value && pos > p.value.from && pos <= p.value.to);
      if (!into) return { node, path };
      if (into.value.kind !== "object" && into.value.kind !== "array") return null;
      path.push(into.key);
      node = into.value;
    }
    return null;
  }

  //: Property keys from the schema at the caret, with the schema's descriptions. Inside a typed `"na` the list replaces
  //: the text after the quote; at a bare position (Ctrl+Space) it inserts a whole `"key": `.
  async function complete(CM, context, env = live) {
    const state = context.state;
    const quote = context.matchBefore(/"[^"\n]*$/);
    if (!quote && !context.explicit) return null;
    const got = await schemaFor(CM, state, env);
    if (!got || !got.schema) return null;
    const start = quote ? quote.from : context.pos;
    const here = objectAt(got.root, start);
    if (!here) return null;
    //: In the value half of a `"key": ` the text since the last comma or brace holds a colon.
    if (state.sliceDoc(state.doc.lineAt(start).from, start).split(/[,{]/).pop().includes(":")) return null;
    const sub = schemaAt(got.schema, here.path);
    if (!sub || !sub.properties) return null;
    const have = new Set(here.node.props.filter((p) => p.keyFrom !== start).map((p) => p.key));
    const required = new Set(Array.isArray(sub.required) ? sub.required : []);
    const options = Object.keys(sub.properties).filter((k) => !have.has(k)).map((label) => {
      const prop = deref(sub.properties[label], got.schema);
      const done = (view, from, to, insert) => view.dispatch({ changes: { from, to, insert }, selection: { anchor: from + insert.length } });
      return {
        label,
        type: "property",
        detail: [required.has(label) ? "required" : "", [].concat(prop.type || []).join(" or ")].filter(Boolean).join(", "),
        info: prop.description ? String(prop.description) : undefined,
        boost: required.has(label) ? 1 : 0,
        apply: quote
          ? (view, c, from, to) => done(view, from, view.state.sliceDoc(to, to + 1) === '"' ? to + 1 : to, `${label}": `)
          : (view, c, from, to) => done(view, from, to, `"${label}": `),
      };
    });
    if (!options.length) return null;
    return quote ? { from: quote.from + 1, options, validFor: /^[^"\n]*$/ } : { from: context.pos, options };
  }

  DOC_LINT_CONFIG.jsonSchema = { diagnostics, complete, schemaFor, read, check, findDoc, schemaAt, objectAt };
})();
