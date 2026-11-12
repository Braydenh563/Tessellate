// draw.io interchange, the rest (WHITEBOARD_PLAN section 14): a .drawio file with a turned shape, a picture
// stored inside it and a gradient; a draw.io library (mxlibrary) into the Library; a draw.io CSV; a
// template placed on the open board. Measures what lands on the board.
//   bash scratchpad/ui-sweeps/serve.sh 8894 <scratch dir>
//   BASE=http://127.0.0.1:8894 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbdrawio3.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

const PNG = "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGP8z8Dwn4GBgYGJAQoAHxcCAr7p+4cAAAAASUVORK5CYII=";
const FILE = `<mxfile><diagram name="P"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="a" value="Turned" style="rounded=0;whiteSpace=wrap;html=1;rotation=30;fillColor=#dae8fc;gradientColor=#7ea6e0;gradientDirection=north;shadow=1;" vertex="1" parent="1"><mxGeometry x="40" y="40" width="120" height="60" as="geometry"/></mxCell>
<mxCell id="b" value="" style="shape=image;image=data:image/png,${PNG};" vertex="1" parent="1"><mxGeometry x="240" y="40" width="64" height="64" as="geometry"/></mxCell>
<mxCell id="c" value="" style="edgeStyle=orthogonalEdgeStyle;endArrow=classic;" edge="1" parent="1" source="a" target="b"><mxGeometry relative="1" as="geometry"/></mxCell>
</root></mxGraphModel></diagram></mxfile>`;
const LIB = `<mxlibrary>${JSON.stringify([
  { xml: '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="x" value="Lib box" style="rounded=1;" vertex="1" parent="1"><mxGeometry width="120" height="60" as="geometry"/></mxCell></root></mxGraphModel>', w: 120, h: 60, title: "Lib box" },
  { xml: '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="y" value="Lib oval" style="ellipse;" vertex="1" parent="1"><mxGeometry width="80" height="80" as="geometry"/></mxCell></root></mxGraphModel>', w: 80, h: 80, title: "Lib oval" },
])}</mxlibrary>`;
const CSV = "# label: %name%\n# style: rounded=1;fillColor=#fff2cc;\n# connect: {\"from\":\"boss\",\"to\":\"name\",\"invert\":true,\"style\":\"endArrow=classic;\"}\n# layout: verticaltree\nname,boss\nAda,\nBo,Ada\nCy,Ada\n";

(async () => {
  const { browser, page, errors } = await openBoard({ viewport: { width: 1440, height: 900 } });
  const counts = () => page.evaluate(() => {
    const sk = wbState.sketches.map((s) => JSON.parse(s.data));
    return {
      shapes: sk.filter((p) => p.d).length, links: sk.filter((p) => String(p.type || "").startsWith("link-")).length,
      objects: wbState.objects.length, sketches: sk,
    };
  });

  await page.evaluate((t) => wbImportText(t), FILE);
  await page.waitForTimeout(2500);
  const file = await page.evaluate(() => {
    const sk = wbState.sketches.map((s) => JSON.parse(s.data));
    const turned = sk.find((p) => p.label === "Turned");
    return {
      turned: turned && { gradient: turned.gradient || null, shadow: !!turned.shadow, box: turned.d && turned.d.length },
      images: wbState.objects.filter((o) => o.kind === "image").map((o) => (o.data && o.data.url) || ""),
    };
  });
  check("the gradient and the shadow land on the shape", file.turned && file.turned.gradient && file.turned.gradient.dir === "n" && file.turned.shadow, file);
  check("the picture stored in the file lands as an uploaded board picture", file.images.length === 1 && /^\/media\//.test(file.images[0]), file.images);
  // Review 5883430964: an SVG picture inside the file is drawn to a PNG (the upload takes no .svg), never lost.
  const SVG = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#c33"/></svg>').toString("base64");
  const svgFile = FILE.replace(`image/png,${PNG}`, `image/svg+xml,${SVG}`).replace('id="c"', 'id="c2"').replace(' source="a" target="b"', "");
  const said = await page.evaluate(async (t) => { await wbImportText(t); return document.querySelector("#wb-live, [aria-live]")?.textContent || ""; }, svgFile);
  await page.waitForTimeout(2500);
  const svgImages = await page.evaluate(() => wbState.objects.filter((o) => o.kind === "image").map((o) => (o.data && o.data.url) || ""));
  check("an SVG picture inside the file lands as an uploaded PNG", svgImages.length === 2 && svgImages.every((u) => /^\/media\//.test(u)), { svgImages, said });
  await page.evaluate(() => wbUndo && wbUndo());
  await page.waitForTimeout(1500);
  const after = await counts();
  check("the connector joins the two", after.links === 1, { links: after.links });

  // The shape is turned: measure the drawn bounding box against the unturned 120 x 60.
  const turn = await page.evaluate(() => {
    const s = wbState.sketches.map((r) => JSON.parse(r.data)).find((p) => p.label === "Turned");
    const nums = (s.d.match(/-?\d+(\.\d+)?/g) || []).map(Number);
    const xs = nums.filter((_, i) => i % 2 === 0), ys = nums.filter((_, i) => i % 2 === 1);
    return { w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
  });
  check("the drawn shape is turned: a 30 degree turn of 120 x 60 spans about 134 x 112", Math.abs(turn.w - 134) < 6 && Math.abs(turn.h - 112) < 6, turn);

  // A draw.io library into the Library.
  const lib = await page.evaluate(async (t) => {
    await wbLibImportFile(new File([t], "sweep lib.xml", { type: "text/xml" }));
    await new Promise((r) => setTimeout(r, 1500));
    const res = await api("/board-library");
    const names = (await res.json()).items.map((i) => i.name);
    return { names };
  }, LIB);
  check("both library entries are in the Library", lib.names.includes("Lib box") && lib.names.includes("Lib oval"), lib.names);

  // The CSV: three shapes, two connectors, laid out as a tree (Ada above Bo and Cy).
  await page.evaluate(() => { wbState.sketches.length = 0; });
  const before = (await counts()).sketches.length;
  await page.evaluate((t) => wbImportText(t), CSV);
  await page.waitForTimeout(2500);
  const csv = await page.evaluate(() => {
    const top = (d) => Math.min(...(d.match(/-?\d+(\.\d+)?/g) || []).filter((_, i) => i % 2 === 1).map(Number));
    const rows = wbState.sketches.map((s) => { const p = JSON.parse(s.data); return { ...p, y: p.d ? s.y + top(p.d) : 0 }; });
    const by = (n) => rows.find((r) => r.label === n);
    return { shapes: rows.filter((r) => r.d).length, links: rows.filter((r) => String(r.type || "").startsWith("link-")).length, ada: by("Ada")?.y, bo: by("Bo")?.y, cy: by("Cy")?.y };
  });
  check("the CSV makes three shapes and two connectors", csv.shapes === 3 && csv.links === 2, csv);
  check("verticaltree puts the boss above the others", csv.ada < csv.bo && csv.ada < csv.cy && Math.abs(csv.bo - csv.cy) < 2, csv);
  void before;

  // A template placed on the open board at the middle of the view.
  const placed = await page.evaluate(async () => {
    const was = wbState.sketches.length;
    await wbLibPlace({ kind: "template", ref: "builtin:drawio-templates/basic-classes", name: "Classes" }, null, { here: true });
    await new Promise((r) => setTimeout(r, 1500));
    return { was, now: wbState.sketches.length + wbState.objects.length };
  });
  check("Place on this board adds the template's items to the open board", placed.now > placed.was, placed);
  check("no console errors", errors.length === 0, errors);
  summary();
  await browser.close();
})();
