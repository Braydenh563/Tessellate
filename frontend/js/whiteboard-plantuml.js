(() => {
  // whiteboard-plantuml.js: the board's joined shapes written as PlantUML text (L-whiteboard-41). The reading
  // of PlantUML is the server's (`wb_convert.py`); this is the other way, next to the Mermaid writer in
  // whiteboard-interchange.js and fed by the same `wbBoardToMermaid.graph`, so the two say the same things. No renderer is
  // needed: the text is for a PlantUML tool, or a person, to read. The writer is pure; `export` saves it.

  //: Words safe in a PlantUML quoted name: the quote, a line break and the backslash would end or bend it.
  const puWords = (text) => String(text || "").replace(/["\\]/g, " ").replace(/\s+/g, " ").trim().slice(0, 120) || " ";

  //: A rectangle, a diamond (a decision) or a circle, each with the board's words, then the connectors:
  //: `-->` where the board has an arrow end, `--` where it has none, a dashed line `..>` and `..`. Frames are
  //: `package`s round what they hold. Pure: `graph` is `wbBoardToMermaid.graph`'s answer.
  function puText(graph) {
    const kinds = { rect: "rectangle", diamond: "diamond", circle: "circle" };
    const declare = (n, pad) => `${pad}${kinds[n.shape] || "rectangle"} "${puWords(n.words)}" as ${n.id}`;
    const lines = ["@startuml"];
    for (const { title, nodes } of graph.frames.values()) {
      lines.push(`package "${puWords(title)}" {`, ...nodes.map((n) => declare(n, "  ")), "}");
    }
    lines.push(...graph.loose.map((n) => declare(n, "")));
    for (const e of graph.edges) {
      const bar = e.dashed ? ".." : "--";
      lines.push(`${e.from} ${bar}${e.arrow ? ">" : ""} ${e.to}${e.label ? ` : ${puWords(e.label)}` : ""}`);
    }
    lines.push("@enduml");
    return lines.join("\n") + "\n";
  }

  async function puExport() {
    const graph = wbBoardToMermaid.graph(wbState, wbCardTitleForExport, wbMermaidFrameOf);
    if (!graph.edges.length) {
      toast("Nothing on this board is joined by a connector, so there is no PlantUML to write.");
      return;
    }
    await saveFile(wbExportFileName("whole", "puml"), new Blob([puText(graph)], { type: "text/plain" }));
    toast("Board exported as PlantUML.");
  }

  wbFmtState.plantuml = { text: puText, export: puExport };
})();
