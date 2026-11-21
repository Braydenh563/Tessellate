// The font matrix (the owner 2026-10-11: "there's some overflowing text in
// some places on different fonts like mono"). Runs errors.js, with its
// text-fit check, once per Appearance font and theme at 1440, 1024 and 390.
// The fonts are read from index.html's `#font-seg` options, so a font added
// there is in the matrix without anyone remembering to add it here
// (tests/test_font_matrix.py holds that). Prints errors.js's lines per run;
// exits 1 if any run has a finding.
// FONTS=mono THEMES=light WIDTHS=1440 narrow it; SLOW=1 for a loaded machine.
// A font, a theme and a width take about 90s, so the whole matrix (5 x 2 x 3)
// is 30 cells and 45 minutes in one go. SHARD=n runs the n-th pair of cells
// (CELLS_PER_SHARD); stable.txt lists every shard, so CI and `gate.sh --sweeps`
// check every cell and each run stays inside the sweep time limit. Run alone (no SHARD) it runs
// every cell. Cells run one after another: two at once slow the app's own
// probes (the search status answers 503 while it is still checking) and a first
// run's two setups race. tests/test_ci_sweeps.py holds that the shards cover
// every cell.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const html = fs.readFileSync(path.join(__dirname, '../../frontend/index.html'), 'utf8');
const select = html.split('id="font-seg"')[1].split('</select>')[0];
const all = [...select.matchAll(/<option value="([a-z0-9-]+)"/g)].map((m) => m[1]);
const fonts = process.env.FONTS ? process.env.FONTS.split(',') : all;
const themes = (process.env.THEMES || 'light,dark').split(',');
const widths = (process.env.WIDTHS || '1440,1024,390').split(',');
const CELLS_PER_SHARD = 2;
let cells = [];
for (const font of fonts) for (const theme of themes) for (const width of widths) cells.push({ font, theme, width });
if (process.env.SHARD) {
  const n = Number(process.env.SHARD);
  cells = cells.slice((n - 1) * CELLS_PER_SHARD, n * CELLS_PER_SHARD);
}
let bad = 0;
for (const { font, theme, width } of cells) {
  const run = spawnSync(process.execPath, [path.join(__dirname, 'errors.js')], {
    env: { ...process.env, FONT: font, THEME: theme, WIDTHS: width },
    encoding: 'utf8',
    timeout: 45 * 60 * 1000,
  });
  const out = (run.stdout || '') + (run.stderr || '');
  console.log(`## font ${font}, ${theme}, ${width}px`);
  console.log(out.trimEnd());
  if (run.status !== 0 || / [1-9]\d* layout findings| [1-9]\d* errors/.test(out)) bad++;
}
console.log(`fontmatrix: ${cells.length} runs, ${bad} with findings`);
process.exitCode = bad ? 1 : 0;
