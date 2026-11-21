(() => {
  // whiteboard-config.js: a board's configuration as a JSON file (L-whiteboard-44). "Plugins" here means this
  // declarative file and nothing else: draw.io's plugins are third-party script, which the CSP forbids and an
  // offline notebook should not run. The file sets default styles, the grid and paper, palettes and which shape
  // libraries are off. The server (`wb_config.py`) checks it against a schema before anything is applied.

  //: The board settings a configuration carries. The picture and the board colour are left out on purpose.
  const CFG_BOARD_FIELDS = ["defaults", "grid_size", "grid_color", "guides", "page_view", "shadow_default", "sticky_fold", "rough", "paper", "orientation", "units", "paper_w", "paper_h"];

  //: Pure: the settings, palettes and switched-off sets as the file's object.
  function cfgBuild(background, palettes, setsOff) {
    const board = {};
    for (const key of CFG_BOARD_FIELDS) if (background && background[key] != null) board[key] = background[key];
    return {
      format: "tessellate-board-config",
      version: 1,
      board,
      palettes: palettes.map((p) => ({ name: p.name, colours: (p.payload?.colours || []).slice(0, 16) })).filter((p) => p.colours.length).slice(0, 8),
      shape_libraries_off: [...setsOff],
    };
  }

  async function cfgExport() {
    let items = [];
    try {
      items = (await apiJson("/board-library"))?.items || [];
    } catch {
      toast("The library could not be read, so the palettes are left out of the file.", "info");
    }
    const palettes = items.filter((x) => x.kind === "palette");
    const config = cfgBuild(wbBoardBackground(), palettes, prefs.json("wb-lib-sets-off", []));
    await saveFile(wbExportFileName("whole", "json").replace(/\.json$/, " configuration.json"), new Blob([JSON.stringify(config, null, 2)], { type: "application/json" }));
    toast("Board configuration exported.");
  }

  //: Apply a checked configuration: the settings go to this board (one undo step), each palette is saved to the library,
  //: and the shape-library switches are merged into this device's choice.
  async function cfgApply(config) {
    if (Object.keys(config.board || {}).length) await wbSetBackground(config.board);
    for (const p of config.palettes || []) await wbLibCreate("palette", p.name, { colours: p.colours }, ["palette", "colours"]);
    if ((config.shape_libraries_off || []).length) {
      const off = new Set([...prefs.json("wb-lib-sets-off", []), ...config.shape_libraries_off]);
      prefs.set("wb-lib-sets-off", JSON.stringify([...off]));
    }
  }

  async function cfgImportText(text) {
    let checked;
    try {
      checked = await apiJson("/whiteboard/config/check", { method: "POST", body: JSON.stringify({ content: text }) });
    } catch (err) {
      toast(err?.message || "That is not a board configuration file.", "info");
      return;
    }
    await cfgApply(checked);
    toast("Board configuration applied.");
  }

  function cfgImport() {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json,application/json";
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (file) await cfgImportText(await file.text());
    });
    input.click();
  }

  wbFmtState.config = { build: cfgBuild, export: cfgExport, import: cfgImport, importText: cfgImportText };
})();
