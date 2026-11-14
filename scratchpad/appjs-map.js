// The app.js split plan's instrument (INBOX 426 cc). Parses frontend/js/app.js
// as a classic script (espree + eslint-scope, from the sandbox's eslint) and
// reports, per section (every header comment, plus the cut points in
// appjs-cuts.json for the long stretch with no headers):
//
//   - its line range and what it declares at top level;
//   - how many top-level statements run at load (not function bodies);
//   - FORWARD references at load: something a load-time statement names that
//     is declared in a LATER section, directly (a handler passed, a constant
//     read) or through the direct calls of a function it calls. In one file
//     a function declaration is hoisted, so these work today; in files
//     loaded in order they are ReferenceErrors;
//   - the top-level let/const of OTHER sections a load-time statement reads
//     or writes (a TDZ hazard only if the split reorders files).
//
// A top-level IIFE counts as load time. Calls are followed through direct
// `f(...)` calls only; a callback is not a call.
//
//   node scratchpad/appjs-map.js           JSON
//   node scratchpad/appjs-map.js --md      the table in appjs-split.md
//   node scratchpad/appjs-map.js --check FROM TO
//        the forward references a file made of lines FROM..TO would have
const fs = require('fs');
const path = require('path');
const NM = '/opt/node22/lib/node_modules/eslint/node_modules/';
const espree = require(NM + 'espree');
const scope = require(NM + 'eslint-scope');

const FILE = path.join(__dirname, '..', 'frontend', 'js', 'app.js');
const src = fs.readFileSync(FILE, 'utf8');
const lines = src.split('\n');
const ast = espree.parse(src, { ecmaVersion: 'latest', sourceType: 'script', loc: true, range: true });
const manager = scope.analyze(ast, { ecmaVersion: 2022, sourceType: 'script' });
const global = manager.globalScope;

const HEADER = /^(\/\/ (---|===)|\/\* (---|===)|\/\/ §)/;
const starts = [];
lines.forEach((l, i) => {
  if (HEADER.test(l)) {
    const title = l.replace(/^(\/\/|\/\*)\s*[-=]*\s*/, '').replace(/\s*[-=]{3,}.*$/, '').trim();
    starts.push({ line: i + 1, title });
  }
});
const CUTS = JSON.parse(fs.readFileSync(path.join(__dirname, 'appjs-cuts.json'), 'utf8'));
for (const c of CUTS) starts.push(c);
starts.sort((a, b) => a.line - b.line);
if (!starts.length || starts[0].line > 1) starts.unshift({ line: 1, title: '(file head)' });
const sections = starts.map((s, i) => ({ ...s, end: (starts[i + 1] ? starts[i + 1].line : lines.length + 1) - 1 }));
const sectionOf = (line) => sections.findIndex((s) => line >= s.line && line <= s.end);

const decl = new Map();
for (const v of global.variables) {
  const d = v.defs[0];
  if (!d) continue;
  const kind = d.type === 'FunctionName' ? 'function' : d.type === 'ClassName' ? 'class' : (d.parent && d.parent.kind) || d.type;
  decl.set(v.name, { kind, line: d.name.loc.start.line });
}

const iife = new Set();
const unwrap = (e) => (e && e.type === 'UnaryExpression' ? e.argument : e);
for (const node of ast.body) {
  const e = node.type === 'ExpressionStatement' ? unwrap(node.expression) : null;
  if (e && e.type === 'CallExpression' && /FunctionExpression|ArrowFunctionExpression/.test(e.callee.type)) iife.add(e.callee);
}
const loadTime = (s) => {
  for (let x = s; x; x = x.upper) {
    if (x.type === 'function' && !iife.has(x.block)) return false;
    if (x.type === 'class-field-initializer') return false;
    if (x === global) return true;
  }
  return true;
};
const ownerFn = (s) => {
  let f = s;
  while (f && f.type !== 'function') f = f.upper;
  if (f && f.upper === global && f.block.type === 'FunctionDeclaration') return f.block.id.name;
  return null;
};

const loadRefs = [];
const fnReads = new Map();
for (const s of manager.scopes) {
  for (const ref of s.references) {
    const name = ref.identifier.name;
    if (!decl.has(name)) continue;
    if (ref.resolved && ref.resolved.scope !== global) continue;
    const line = ref.identifier.loc.start.line;
    if (loadTime(s)) { loadRefs.push({ name, line, write: ref.isWrite() }); continue; }
    const fname = ownerFn(s);
    if (!fname) continue;
    if (!fnReads.has(fname)) fnReads.set(fname, new Set());
    fnReads.get(fname).add(name);
  }
}

const loadCalls = [];
const fnCalls = new Map();
const isFn = (n) => decl.get(n) && decl.get(n).kind === 'function';
const walk = (node, owner) => {
  if (!node || typeof node.type !== 'string') return;
  let next = owner;
  if (/Function/.test(node.type)) {
    if (node.type === 'FunctionDeclaration' && owner === 'load' && isFn(node.id.name)) next = node.id.name;
    else if (iife.has(node) && owner === 'load') next = 'load';
    else next = null;
  }
  if (node.type === 'CallExpression' && node.callee.type === 'Identifier' && isFn(node.callee.name)) {
    if (owner === 'load') loadCalls.push({ name: node.callee.name, line: node.loc.start.line });
    else if (owner) {
      if (!fnCalls.has(owner)) fnCalls.set(owner, new Set());
      fnCalls.get(owner).add(node.callee.name);
    }
  }
  for (const key of Object.keys(node)) {
    if (key === 'loc' || key === 'range') continue;
    const v = node[key];
    if (Array.isArray(v)) v.forEach((c) => walk(c, next));
    else if (v && typeof v.type === 'string') walk(v, next);
  }
};
for (const node of ast.body) walk(node, 'load');

const reach = (start) => {
  const seen = new Set([start]);
  const stack = [start];
  while (stack.length) {
    const f = stack.pop();
    for (const g of fnCalls.get(f) || []) if (!seen.has(g)) { seen.add(g); stack.push(g); }
  }
  return seen;
};

// For a span of lines [from, to] treated as one file: the load-time names it
// uses that are declared after `to` (later files).
// `after`: the line the span will sit after once moved (its own end if it
// stays); a name is forward when declared after that and outside the span.
function forwardFor(from, to, after = to) {
  const out = new Map();
  const later = (at) => at > after && (at < from || at > to);
  for (const r of loadRefs) {
    if (r.line < from || r.line > to) continue;
    const at = decl.get(r.name).line;
    if (later(at)) out.set(r.name, at);
  }
  for (const c of loadCalls) {
    if (c.line < from || c.line > to) continue;
    for (const f of reach(c.name)) {
      for (const n of fnReads.get(f) || []) {
        const at = decl.get(n).line;
        if (later(at) && !out.has(n)) out.set(`${c.name}() .. ${n}`, at);
      }
      if (later(decl.get(f).line) && !out.has(f)) out.set(`${c.name}() .. ${f}()`, decl.get(f).line);
    }
  }
  return out;
}

//   --check FROM TO [AFTER]: the forward references of lines FROM..TO as a
//   file of their own, placed after line AFTER of today's app.js (default:
//   where they are). A move earlier is checked with AFTER < FROM.
if (process.argv[2] === '--check') {
  const from = Number(process.argv[3]);
  const to = Number(process.argv[4]);
  const f = forwardFor(from, to, process.argv[5] ? Number(process.argv[5]) : to);
  console.log(`${f.size} forward reference(s) at load from lines ${from}-${to}`);
  for (const [n, at] of f) console.log(`  ${n}  (declared at ${at}, section ${sectionOf(at) + 1}: ${sections[sectionOf(at)].title})`);
  process.exit(0);
}

const stmts = sections.map(() => 0);
for (const node of ast.body) {
  if (node.type === 'FunctionDeclaration') continue;
  const i = sectionOf(node.loc.start.line);
  const inert = node.type === 'VariableDeclaration' &&
    node.declarations.every((d) => !d.init || /Literal|ArrowFunctionExpression|FunctionExpression/.test(d.init.type));
  if (!inert) stmts[i] += 1;
}

const out = sections.map((s, i) => {
  const own = [...decl].filter(([, d]) => d.line >= s.line && d.line <= s.end);
  const refs = loadRefs.filter((r) => r.line >= s.line && r.line <= s.end);
  const letConst = new Map();
  for (const r of refs) {
    const d = decl.get(r.name);
    const home = sectionOf(d.line);
    if ((d.kind === 'let' || d.kind === 'const') && home !== i) {
      const prev = letConst.get(r.name);
      letConst.set(r.name, { home: home + 1, write: (prev && prev.write) || r.write });
    }
  }
  const forward = forwardFor(s.line, s.end);
  return {
    n: i + 1, title: s.title, from: s.line, to: s.end, lines: s.end - s.line + 1,
    functions: own.filter(([, d]) => d.kind === 'function').length,
    lets: own.filter(([, d]) => d.kind === 'let').map(([n]) => n),
    consts: own.filter(([, d]) => d.kind === 'const').map(([n]) => n),
    loadStatements: stmts[i],
    loadCalls: [...new Set(loadCalls.filter((c) => c.line >= s.line && c.line <= s.end).map((c) => c.name))],
    letConstAcross: [...letConst].map(([n, v]) => `${n} ${v.write ? 'w' : 'r'}@${v.home}`),
    forwardAtLoad: [...forward].map(([n, at]) => `${n}@${sectionOf(at) + 1}`),
  };
});

if (process.argv.includes('--md')) {
  const cell = (list, k = 5) => (list.length ? list.slice(0, k).join(', ') + (list.length > k ? ` (+${list.length - k})` : '') : '');
  for (const s of out) {
    console.log(`| ${s.n} | ${s.from}-${s.to} | ${s.lines} | ${s.title.replace(/\|/g, '/').slice(0, 58)} | ${s.functions} | ${s.lets.length}/${s.consts.length} | ${s.loadStatements} | ${cell(s.loadCalls, 4)} | ${cell(s.letConstAcross, 4)} | ${cell(s.forwardAtLoad, 4)} |`);
  }
} else {
  console.log(JSON.stringify({ totalLines: lines.length, declarations: decl.size, sections: out }, null, 1));
}
