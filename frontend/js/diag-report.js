// diag-report.js: the one copyable diagnostics report (INBOX 1430, the owner,
// 2026-10-28: "improve the app's ability to register and log issues and lag and
// complexity so I can just give you the logs"). Settings, Logs, Copy
// diagnostics, "Save diagnostics as file" and the palette command run
// `diagCopy` / `diagSave`; lag-watch.js (the same lazy module, `diagnostics`)
// holds what the browser saw, `GET /diagnostics` what the server did.
//
// Plain text under about 20 KB: a header, then lines grouped and counted
// ("x14 frame 220-560ms [notes] phone-shell.js tab onclick (forced layout
// 146-299ms)"), the last errors with their frames, the slow routes as a table,
// slow statements, failed jobs and a complexity snapshot. Nothing a person
// wrote is in it: causes are file and function names, triggers are element
// selectors, routes have their ids and query strings removed, statements their
// literals, and the home folder is `~`. Counts and ids stand in for titles.
//
// The functions down to `diagBuild` are pure (tests/test_diag_report.py runs
// them in node); the last three touch the page.

const DIAG_LIMIT = 20000;

//: The home folder is `~`, the server's address is gone (a LAN address names a
//: network), the version stamp on an asset URL is gone, an address is `<email>`.
function diagRedact(text) {
  return String(text ?? "")
    .replace(/\/home\/[^/\s"')]+/g, "~")
    .replace(/\/Users\/[^/\s"')]+/g, "~")
    .replace(/[A-Za-z]:\\Users\\[^\\\s"')]+/g, "~")
    .replace(/\/root\b/g, "~")
    .replace(/https?:\/\/[^/\s"')]+/g, "")
    .replace(/\?v=[\w.-]+/g, "")
    .replace(/[\w.+-]+@[\w-]+\.[\w.-]+/g, "<email>");
}

function diagRange(values, unit = "") {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  return lo === hi ? `${lo}${unit}` : `${lo}-${hi}${unit}`;
}

//: Lag reports with the same kind, view and wording apart from their numbers
//: are one line: `x14 frame 220-560ms [notes] cause after pointerdown button#x`.
//: `n` on a report is how many stalls it already stands for.
function diagGroupLag(events) {
  const groups = new Map();
  for (const e of events || []) {
    const slots = [];
    //: A frame names up to three scripts; the worst one is the group's wording and the
    //: others are listed by file, so one slow click is not a dozen kinds.
    const [head, ...rest] = String(e.cause || "no script attributed").split("; ");
    const shape = head.replace(/(\d+(?:\.\d+)?)(ms| calls\/s)/g, (_, num, unit) => {
      slots.push(Number(num));
      return `\u0001${unit}`;
    });
    const key = `${e.kind}|${e.view}|${shape}`;
    const g = groups.get(key) || { kind: e.kind, view: e.view, shape, count: 0, ms: [], slots: [], inputs: new Map(), nodes: [], last: "", others: new Set() };
    for (const other of rest) {
      const who = other.startsWith("animation loops") ? "animation loops" : other.split(" ")[0];
      if (who !== head.split(" ")[0]) g.others.add(who);
    }
    g.count += Number(e.n) || 1;
    g.ms.push(Number(e.ms) || 0);
    slots.forEach((v, i) => (g.slots[i] ||= []).push(v));
    //: A control pressed within three seconds is the likely cause of a stall; older is noise.
    if (e.input && e.input_ago_ms != null && e.input_ago_ms < 3000) g.inputs.set(e.input, (g.inputs.get(e.input) || 0) + 1);
    if (e.nodes) g.nodes.push(Number(e.nodes));
    g.last = e.at || g.last;
    groups.set(key, g);
  }
  return [...groups.values()]
    .sort((a, b) => Math.max(...b.ms) * b.count - Math.max(...a.ms) * a.count)
    .map((g) => {
      let i = 0;
      const cause = diagRedact(g.shape).replace(/\u0001( calls\/s|ms)/g, (_, unit) => diagRange(g.slots[i++] || [0], unit.trim() === "ms" ? "ms" : " calls/s"));
      const top = [...g.inputs].sort((a, b) => b[1] - a[1])[0];
      const after = top && g.kind === "frame" ? ` after ${top[0]}` : "";
      const size = g.nodes.length ? ` (${diagRange(g.nodes.map((n) => Math.round(n / 100) / 10))}k elements)` : "";
      const also = g.others.size ? ` (also ${[...g.others].join(", ")})` : "";
      return `x${g.count} ${g.kind} ${diagRange(g.ms, "ms")} [${g.view}] ${cause}${also}${after}${size}`;
    });
}

//: The last errors, each once with a count: `x3 [documents] message` and the
//: first frames of its stack, indented.
function diagErrors(list, max = 8, frames = 5) {
  return [...(list || [])]
    .sort((a, b) => b.last - a.last)
    .slice(0, max)
    .map((e) => {
      const lines = String(e.stack || "").split("\n").map((l) => diagRedact(l.trim())).filter(Boolean);
      const head = diagRedact(e.message).slice(0, 200);
      const rest = lines.filter((l) => l !== head && !head.includes(l)).slice(0, frames).map((l) => `    ${l.slice(0, 160)}`);
      return [`x${e.n} [${e.view}] ${head}`, ...rest].join("\n");
    });
}

function diagTable(rows, columns) {
  if (!rows.length) return ["none"];
  const cells = rows.map((r) => columns.map((c) => String(c.get(r))));
  const widths = columns.map((c, i) => Math.max(c.head.length, ...cells.map((r) => r[i].length)));
  const line = (r) => r.map((v, i) => v.padEnd(widths[i])).join("  ").trimEnd();
  return [line(columns.map((c) => c.head)), ...cells.map(line)];
}

//: `data`: { now, header: { version, build, device, viewport, cores, memory, counts, nodes, heap, platform, python, settings, sampler },
//: lag: [events], errors: [groups], server: { slow_routes, slow_queries, exceptions, job_failures }, snapshot }.
function diagSections(data, size) {
  const h = data.header || {};
  const s = data.server || {};
  const counts = h.counts || {};
  const num = (n) => Number(n || 0).toLocaleString("en-US");
  const out = [];
  out.push(["Tessellate diagnostics", [
    `Made ${data.now} | version ${h.version || "?"} build ${h.build || "?"}`,
    `Device: ${h.device || "?"} | viewport ${h.viewport || "?"} @${h.dpr || 1}x | ${h.cores || "?"} cores | ${h.memory ? h.memory + " GB" : "memory unknown"}`,
    `Notebook: ${num(counts.notes)} notes, ${num(counts.boards)} boards, ${num(counts.docs)} documents, ${num(counts.links)} links | ${num(h.nodes)} page elements | heap ${h.heap ?? "?"} MB`,
    `Server: ${h.platform || "?"}, Python ${h.python || "?"}`,
    `Settings: ${Object.entries(h.settings || {}).map(([k, v]) => `${k}=${v}`).join(", ") || "defaults"}; frame sampler ${h.sampler ? "on" : "off"}`,
  ]]);
  const lag = diagGroupLag(data.lag);
  out.push([`Lag (${lag.length} kinds, worst first)`, lag.slice(0, size.lag).concat(lag.length > size.lag ? [`... ${lag.length - size.lag} more kinds`] : []).concat(lag.length ? [] : ["none logged"])]);
  const errors = diagErrors(data.errors, size.errors, size.frames);
  out.push([`Errors in the browser (${(data.errors || []).reduce((n, e) => n + e.n, 0)} total, ${(data.errors || []).length} kinds)`, errors.length ? errors : ["none"]]);
  out.push(["Slow routes (a second or more)", diagTable(s.slow_routes || [], [
    { head: "route", get: (r) => `${r.method} ${r.route}` }, { head: "count", get: (r) => r.n },
    { head: "max ms", get: (r) => r.max_ms }, { head: "avg ms", get: (r) => r.avg_ms }, { head: "last status", get: (r) => r.status },
  ])]);
  out.push(["Slow database statements (250 ms or more)", diagTable(s.slow_queries || [], [
    { head: "count", get: (r) => r.n }, { head: "max ms", get: (r) => r.max_ms }, { head: "statement", get: (r) => diagRedact(r.sql) },
  ])]);
  const ex = (s.exceptions || []).slice(0, size.errors).map((x) => `x${x.n} ${x.type} on ${x.route} (ref ${String(x.ref).slice(0, 8)}): ${diagRedact(x.message)}\n${(x.frames || []).slice(-size.frames).map((f) => `    ${f}`).join("\n")}`.trimEnd());
  out.push(["Server exceptions", ex.length ? ex : ["none"]]);
  const jobs = (s.job_failures || []).map((j) => `${j.kind} at ${j.at}: ${diagRedact(j.detail)}`);
  out.push(["Failed jobs", jobs.length ? jobs : ["none"]]);
  const snap = data.snapshot;
  if (snap) {
    out.push(["Complexity snapshot", [
      `${num(snap.nodes)} elements; heap ${snap.heap_mb ?? "unavailable"} MB`,
      ...(snap.wide.length ? [`Largest child lists: ${snap.wide.join("; ")}`] : []),
      ...(snap.longest.length ? ["Longest stalls in the last 5 minutes:", ...snap.longest.map((r) => `  ${r.ms}ms ${r.kind} ${diagRedact(r.cause) || "no script attributed"}`)] : ["No stall in the last 5 minutes."]),
      ...(snap.raf.length ? ["Animation loops by cost since load:", ...diagTable(snap.raf, [
        { head: "owner", get: (r) => r.owner }, { head: "calls", get: (r) => r.calls }, { head: "total ms", get: (r) => r.ms },
        { head: "avg ms", get: (r) => r.avg }, { head: "max ms", get: (r) => r.max },
      ]).map((l) => `  ${l}`)] : [snap.sampler ? "No animation loop seen." : "Frame sampler is off."]),
    ]]);
  }
  return out;
}

//: Smaller and smaller until it fits: fewer lag kinds, fewer errors, fewer frames.
function diagBuild(data, limit = DIAG_LIMIT) {
  let text = "";
  for (const size of [{ lag: 40, errors: 8, frames: 5 }, { lag: 25, errors: 6, frames: 3 }, { lag: 15, errors: 4, frames: 2 }, { lag: 8, errors: 3, frames: 0 }]) {
    text = diagSections(data, size).map(([title, lines]) => `== ${title} ==\n${lines.join("\n")}`).join("\n\n") + "\n";
    if (text.length <= limit) return text;
  }
  return text.slice(0, limit - 40) + "\n[trimmed to fit the size limit]\n";
}

function diagDevice() {
  const brands = navigator.userAgentData?.brands?.filter((b) => !/not.?a.?brand/i.test(b.brand)).map((b) => `${b.brand} ${b.version}`).join(", ");
  const platform = navigator.userAgentData?.platform || navigator.platform || "";
  return `${brands || diagRedact(navigator.userAgent).slice(-60)} on ${platform}`;
}

async function diagCollect() {
  //: The batch waiting to be sent goes first, so the server's file has it.
  await lagFlush();
  const server = await apiJson("/diagnostics");
  const snapshot = lagSnapshot();
  return diagBuild({
    now: new Date().toISOString(),
    header: {
      version: server.version,
      build: server.lag.find((e) => e.build)?.build,
      device: diagDevice(),
      viewport: `${innerWidth}x${innerHeight}`,
      dpr: window.devicePixelRatio || 1,
      cores: navigator.hardwareConcurrency,
      memory: navigator.deviceMemory,
      counts: server.counts,
      nodes: snapshot.nodes,
      heap: snapshot.heap_mb,
      platform: server.platform,
      python: server.python,
      settings: server.settings,
      sampler: snapshot.sampler,
    },
    lag: server.lag,
    errors: [...LAG.errors.values()],
    server,
    snapshot,
  });
}

async function diagCopy() {
  try {
    const text = await diagCollect();
    if (await copyToClipboard(text)) toast(`Copied the diagnostics (${(text.length / 1024).toFixed(1)} KB). Paste it where you send your logs.`);
  } catch (error) {
    toast(error.message || "Couldn't build the diagnostics. Try again.", true);
  }
}

async function diagSave() {
  try {
    const text = await diagCollect();
    await saveFile("tessellate-diagnostics.txt", new Blob([text], { type: "text/plain" }));
    toast("Diagnostics saved. Have a look inside before you send it.");
  } catch (error) {
    toast(error.message || "Couldn't build the diagnostics. Try again.", true);
  }
}
