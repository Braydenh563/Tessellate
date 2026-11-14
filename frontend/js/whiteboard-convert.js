(() => {
  // whiteboard-convert.js: GraphML, Miro and PlantUML files, and an EMF, brought in through the Import dialog
  // (L-whiteboard-41 and 45). The reading is the server's (`wb_convert.py`, POST /whiteboard/convert: size caps and
  // hardened XML are there); this file only recognises what was pasted or chosen, asks, and hands the answer to
  // the placers the Mermaid import already has (`wbImportMermaid`, `wbImportMermaidSequence`, whiteboard-interchange.js).
  // Everything stays on this computer: the one request is to this app's own server.

  const HEAD = 4096;

  //: Pure: which reader a pasted text is for, or null. Cheap on purpose: the server decides for real.
  function cvSniff(text) {
    const head = String(text || "").slice(0, HEAD);
    if (/<graphml[\s>]/i.test(head)) return "graphml";
    if (/@startuml/i.test(head)) return "plantuml";
    //: Miro's REST items: a list, or `{"data": [...]}`, whose items name a Miro `type`.
    if (/^\s*[[{]/.test(head) && /"type"\s*:\s*"(sticky_note|shape|frame|connector|text|card|app_card)"/.test(String(text).slice(0, 20000))) return "miro";
    return null;
  }

  function cvBase64(bytes) {
    let out = "";
    for (let i = 0; i < bytes.length; i += 0x8000) out += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(out);
  }

  //: Ask the server to read `body` (`{format, content}` or `{format, data_b64}`) and draw the answer. One undo step.
  async function cvRun(body, at = wbViewCentre(), name = "") {
    let got;
    try {
      got = await apiJson("/whiteboard/convert", { method: "POST", body: JSON.stringify(body) });
    } catch (err) {
      toast(err.message || "That file could not be read.", "info");
      return 0;
    }
    if (got.kind === "sequence") return wbImportMermaidSequence(null, at, got.sequence);
    if (got.kind === "emf") return cvEmf(got, name, at);
    return wbImportMermaid(null, at, got.graph);
  }

  //: An EMF is not drawn (no browser decodes one and no MIT pure-Python renderer exists, see `inspect_emf`). The
  //: board gets a note box that says so and names the file's size, so nothing is silently dropped.
  async function cvEmf(info, name, at) {
    const words = `${name || "A file"} is an EMF picture, ${info.width} by ${info.height}. ${info.message}`;
    await wbRecordGesture(async () => {
      await wbCreateObject("text", { content: words, bg: "#fff4a3", border_color: "#e8d56a", color: "#2a2a1f" }, Math.round(at[0] - 160), Math.round(at[1] - 55), 320, 110);
    });
    renderWhiteboardNow();
    toast(info.message, "info");
    wbAnnounce(info.message);
    return 1;
  }

  async function cvImportEmf(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    return cvRun({ format: "emf", data_b64: cvBase64(bytes) }, wbViewCentre(), file.name);
  }

  wbFmtState.convert = { sniff: cvSniff, run: cvRun, importEmf: cvImportEmf, base64: cvBase64 };
})();
