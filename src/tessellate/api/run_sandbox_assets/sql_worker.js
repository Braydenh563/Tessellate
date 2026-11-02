
function cell(v) {
  if (v === null || v === undefined) return null;
  if (v instanceof Uint8Array) return "[blob, " + v.length + " bytes]";
  return v;
}
function lineAt(text, pos) {
  var n = 1;
  for (var i = 0; i < pos && i < text.length; i++) if (text.charCodeAt(i) === 10) n++;
  return n;
}
//: Whitespace and comments before a statement's first word, so its line is
//: the line its first word is on.
var LEAD = /^(?:\s+|--[^\n]*(?:\n|$)|\/\*[\s\S]*?\*\/)*/;
self.onmessage = function (e) {
  var d = e.data || {};
  var text = String(d.source || ""), offset = Number(d.lineOffset) || 0;
  initSqlJs({ wasmBinary: d.wasm }).then(function (SQL) {
    var db = new SQL.Database();
    var line = null;
    try {
      (d.tables || []).forEach(function (t) {
        var cols = t.columns.map(function (c) { return '"' + String(c).replace(/"/g, '""') + '"'; });
        db.run("CREATE TABLE \"" + String(t.name).replace(/"/g, '""') + "\" (" + cols.join(", ") + ")");
        var ins = db.prepare("INSERT INTO \"" + String(t.name).replace(/"/g, '""') + "\" VALUES (" + cols.map(function () { return "?"; }).join(", ") + ")");
        t.rows.forEach(function (r) { ins.run(r); });
        ins.free();
        postMessage({ t: "log", level: "info", text: "Loaded " + t.rows.length + " rows into " + t.name + ".", line: null });
      });
      var it = db.iterateStatements(text);
      for (;;) {
        var rest = it.getRemainingSQL();
        var start = text.length - rest.length;
        start += LEAD.exec(rest)[0].length;
        line = start < text.length ? lineAt(text, start) + offset : null;
        var step = it.next();
        if (step.done) break;
        var stmt = step.value, rows = [], more = 0;
        var columns = stmt.getColumnNames();
        while (stmt.step()) {
          if (rows.length < ROW_CAP) rows.push(stmt.get().map(cell));
          else more++;
        }
        stmt.free();
        if (columns.length) postMessage({ t: "table", columns: columns, rows: rows, more: more, line: line });
        else {
          var changed = db.getRowsModified();
          postMessage({ t: "log", level: "info", text: changed === 0 ? "Done." : changed === 1 ? "1 row changed." : changed + " rows changed.", line: line });
        }
      }
      postMessage({ t: "done", pending: 0 });
    } catch (err) {
      postMessage({ t: "log", level: "error", text: String(err && err.message || err), line: line, uncaught: true });
    } finally {
      db.close();
    }
  }, function (err) {
    postMessage({ t: "log", level: "error", text: "SQLite could not start: " + String(err && err.message || err), line: null, uncaught: true });
  });
};
