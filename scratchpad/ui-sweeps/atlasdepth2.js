// Atlas (companion) sweeps: one look, one measure each, consolidated: one async function per case.
// Run one case by name, or every case in order with no argument:
//   node scratchpad/ui-sweeps/atlasdepth2.js atlasgait

// Which loops Atlas runs per look (idle, walk, float, wave): the animation
// names on the companion's char box, the body layer, the lower layer and the
// right arm in a stand-in `#nm-buddy` (the real one rides inside
// `#nm-buddy-rider`), plus how far the char box travels up in a walk cycle.
//   BASE=... node atlasdepth2.js atlasgait
async function atlasgait() {
  const {boot}=require('./lib.js');
    const {browser,page}=await boot({viewport:{width:1093,height:614}});
    const rows=await page.evaluate(async()=>{
      const out=[];
      for(const look of ['masculine','feminine']) for(const [state,cls,pose] of [['idle','','stand'],['walk','nmb-walking','stand'],['float','','float'],['wave','nmb-act-wave','stand']]){
        localStorage.setItem('atlas-look',look);
        document.getElementById('nm-buddy')?.remove();
        const h=document.createElement('div'); h.id='nm-buddy'; if(cls) h.classList.add(cls); h.dataset.pose=pose; if(cls==='nmb-walking') h.style.setProperty('--nmb-lean','1');
        h.style.position='fixed'; h.style.left='300px'; h.style.top='200px'; h.style.width='64px'; h.style.height='92px';
        const face=document.createElement('div'); face.className='nm-buddy-face'; const char=document.createElement('div'); char.className='nm-buddy-char';
        char.append(atlasFigure()); face.append(char); h.append(face); document.body.append(h);
        await new Promise(r=>setTimeout(r,120));
        const a=(el)=>el?getComputedStyle(el).animationName:'-';
        const ys=[]; for(let i=0;i<14;i++){ ys.push(char.getBoundingClientRect().top); await new Promise(r=>setTimeout(r,100)); }
        out.push(`${look.padEnd(9)} ${state.padEnd(5)} char=${a(char)} body=${a(h.querySelector('.atl-layer-body'))} lower=${a(h.querySelector('.atl-layer-lower'))} arm-r=${a(h.querySelector('.atl-layer-body .nmb-arm-r'))} rise=${(Math.max(...ys)-Math.min(...ys)).toFixed(1)}px`);
        h.remove();
      }
      localStorage.removeItem('atlas-look');
      return out;
    });
    console.log(rows.join('\n'));
    await browser.close();
}

// Every mood's three arm variants at the companion's size, per look, in one
// sheet: the check that variant 1 and 2 read as different gestures and that
// the arms read at all when small. SIZE=92 (the companion's height) by
// default; ZOOM is the device scale. Writes shots/atlas-moodgrid-<look>-<theme>.png.
//   BASE=... THEME=dark LOOK_ATLAS=feminine MOODS=happy,sleepy SCRATCH=.. node atlasdepth2.js atlasmoodgrid
async function atlasmoodgrid() {
  const {boot}=require('./lib.js');
  const THEME=process.env.THEME||'light';
    const {browser,page}=await boot({viewport:{width:1093,height:614},deviceScaleFactor:+(process.env.ZOOM||2)});
    for(const look of (process.env.LOOK_ATLAS||'masculine,feminine').split(',')){
      await page.evaluate(async({look,moods,size})=>{
        document.getElementById('atl-grid')?.remove();
        localStorage.setItem('atlas-look',look);
        clearTimeout(atlasMoodTimer); setAtlasMood=()=>{};
        const box=document.createElement('div'); box.id='atl-grid'; box.className='card';
        box.style.position='fixed'; box.style.inset='52px 8px 36px 8px'; box.style.zIndex='9999'; box.style.display='grid'; box.style.gridTemplateColumns='repeat(12, 1fr)'; box.style.gap='2px'; box.style.overflow='hidden';
        const list=moods?moods.split(','):Object.keys(ATLAS_MOODS);
        for(const mood of list) for(const v of [0,1,2]){
          const cell=document.createElement('div'); cell.style.textAlign='center'; cell.style.fontSize='9px';
          const s=atlasDraw(size,'calm','full'); atlasApply(s,mood); s.dataset.atlasMood=mood; s.dataset.atlasVariant=String(v);
          cell.append(s, document.createElement('br'), `${mood} ${v}`); box.append(cell);
        }
        document.body.append(box); localStorage.removeItem('atlas-look');
      },{look,moods:process.env.MOODS||'',size:+(process.env.SIZE||92)});
      await page.waitForTimeout(1500);
      await page.screenshot({path:`${process.env.SCRATCH||'.'}/shots/atlas-moodgrid-${look}-${THEME}.png`});
    }
    await browser.close();
}

// Does Atlas's hand hold the bell and the lantern? In the companion's bell
// and lantern acts, the distance from the prop's top (the bell's crown, the
// lantern's string) to the nearest point of the right arm's outline, in the
// drawing's units, per look. Target: under 2.
//   BASE=... SCRATCH=.. node atlasdepth2.js atlasprop
async function atlasprop() {
  const {boot}=require('./lib.js');
    const {browser,page}=await boot({viewport:{width:1093,height:614}});
    const rows=await page.evaluate(async()=>{
      const out=[];
      for(const look of ['masculine','feminine']) for(const act of ['bell','lantern']){
        localStorage.setItem('atlas-look',look);
        document.getElementById('nm-buddy')?.remove();
        const h=document.createElement('div'); h.id='nm-buddy'; h.className=`nmb-act-${act}`; h.dataset.pose='stand';
        h.style.position='fixed'; h.style.left='300px'; h.style.top='200px'; h.style.width='64px'; h.style.height='92px';
        const fig=atlasFigure(); h.append(fig); document.body.append(h);
        fig.querySelectorAll('*').forEach(e=>{e.style.transition='none'; e.style.animation='none';});
        await new Promise(r=>setTimeout(r,200));
        const body=fig.querySelector('.atl-layer-body'); const rig=body.querySelector('.atl-rig');
        const inv=rig.getScreenCTM().inverse();
        const arm=body.querySelector('.nmb-arm-r path.atl-skin');
        const m=inv.multiply(arm.getScreenCTM()); const L=arm.getTotalLength();
        const pts=[]; for(let i=0;i<=120;i++){const q=arm.getPointAtLength(L*i/120); pts.push(new DOMPoint(q.x,q.y).matrixTransform(m));}
        const tip=pts.reduce((a,p)=>Math.hypot(p.x-37.4,p.y-41)>Math.hypot(a.x-37.4,a.y-41)?p:a,pts[0]);
        const prop=body.querySelector(act==='bell'?'.nmp-bell .atl-prop-bell':'.nmp-lantern .atl-prop-string');
        const pm=inv.multiply(prop.getScreenCTM());
        const top=act==='bell'?new DOMPoint(48.2,63.2).matrixTransform(pm):new DOMPoint(48.2,61).matrixTransform(pm);
        out.push(`${look.padEnd(9)} ${act.padEnd(7)} tip ${tip.x.toFixed(1)},${tip.y.toFixed(1)}  prop top ${top.x.toFixed(1)},${top.y.toFixed(1)}  gap to the hand's outline ${Math.min(...pts.map(p=>Math.hypot(p.x-top.x,p.y-top.y))).toFixed(1)}`);
        h.remove();
      }
      localStorage.removeItem('atlas-look');
      return out;
    });
    console.log(rows.join('\n'));
    await browser.close();
}

// A sleepy Atlas and input (the "startled by Ctrl" reports): with Atlas
// sleepy, hold Ctrl for 40 frames and click the page 10 times away from any
// Atlas; count frames where any mark is surprised (target 0). Then poke an
// Atlas: it eases to calm (.atl-easing on), and stays calm through the
// resting-mood check. BASE=http://127.0.0.1:8861 node atlasdepth2.js atlaswake
async function atlaswake() {
  const {boot}=require('./lib.js');
    const {browser,page}=await boot({viewport:{width:1093,height:614}});
    const state=()=>page.evaluate(()=>({mood:atlasMoodNow,surprised:document.querySelectorAll('.nm-atlas.nm-surprised').length,marks:document.querySelectorAll('.nm-atlas').length,easing:document.querySelectorAll('.nm-atlas.atl-easing').length}));
    await page.evaluate(()=>setAtlasMood('sleepy'));
    await page.waitForTimeout(300);
    let surprised=0, frames=0;
    await page.keyboard.down('Control');
    for(let i=0;i<40;i++){ await page.keyboard.down('Control'); await page.waitForTimeout(50); const s=await state(); frames++; if(s.surprised||s.mood==='surprised') surprised++; }
    await page.keyboard.up('Control');
    for(let i=0;i<10;i++){ await page.mouse.click(600,300); await page.waitForTimeout(80); const s=await state(); frames++; if(s.surprised||s.mood==='surprised') surprised++; }
    const before=await state();
    console.log(`sleepy under input: ${surprised} of ${frames} frames surprised; mood after=${before.mood}; marks=${before.marks}`);
    await page.evaluate(()=>setAtlasMood('sleepy'));
    await page.waitForTimeout(200);
    // A poke: a click event on a visible mark.
    const poked=await page.evaluate(()=>{const m=[...document.querySelectorAll('.nm-atlas')].find(x=>x.checkVisibility()); if(!m) return false; m.dispatchEvent(new MouseEvent('click',{bubbles:true})); return true;});
    await page.waitForTimeout(100);
    const s1=await state();
    await page.waitForTimeout(2600);
    const s2=await state();
    const rest=await page.evaluate(()=>atlasRestingMood());
    console.log(`poke: poked=${poked} at+100ms mood=${s1.mood} easing=${s1.easing}; at+2.7s mood=${s2.mood} easing=${s2.easing}; resting=${rest}`);
    // A poke of an Atlas already awake: the reaction holds 3 to 5s, then eases
    // back (.atl-easing on) rather than snapping.
    await page.evaluate(()=>setAtlasMood('calm'));
    await page.evaluate(()=>{const m=[...document.querySelectorAll('.nm-atlas')].find(x=>x.checkVisibility()); m.dispatchEvent(new MouseEvent('click',{bubbles:true}));});
    const line=[];
    for(let t=0;t<=6000;t+=250){ const s=await state(); line.push(`${t}:${s.mood}${s.easing?'~':''}`); await page.waitForTimeout(250); }
    console.log('awake poke timeline (ms:mood, ~ easing): '+line.join(' '));
    await browser.close();
}

// Brief 34 continues, step 5 (INBOX 752, the owner: "so incredibly smoothe
// between everything and every event"). The corner Atlas on the dashboard:
// 1. Reaction latency, from the end of the 1.5s debounce (the moment
//    `setAtlasMood` is called, INBOX 773) to the first frame that has the
//    new mood on the companion's drawing. TRIALS (5).
// 2. Snaps: every frame for MS (60000), the hands' and the head's centres
//    relative to the figure; a snap is a jump over 4px in one frame out of
//    under 1px a frame for the three frames before (a start with no ease).
// 3. Idle variety: the distinct things it does in that time (its act, its
//    pose, its tail's act, its arm variant), as `kind:value`.
//   BASE=... MS=60000 node atlasdepth2.js atlassmooth
async function atlassmooth() {
  const {boot}=require('./lib.js');
    const {browser,page}=await boot({viewport:{width:1440,height:900}});
    await page.evaluate(()=>{ localStorage.removeItem('nm-buddy-spots'); const b=$('avatar-buddy'); b.value='atlas'; b.dispatchEvent(new Event('change',{bubbles:true})); revealTab('dashboard'); });
    await page.waitForTimeout(6000);
    const lat=await page.evaluate(async(n)=>{
      const out=[]; const moods=['proud','worried','happy','confused','delighted','thinking','shy'];
      for(let i=0;i<n;i++){
        const mood=moods[i%moods.length];
        const t0=performance.now(); setAtlasMood(mood,2000,{quiet:true});
        const t=await new Promise(res=>{const f=()=>{const s=document.querySelector('#nm-buddy .atl-layer-body'); if(s&&s.dataset.atlasMood===mood) res(performance.now()-t0); else requestAnimationFrame(f);}; requestAnimationFrame(f);});
        out.push(Math.round(t)); await new Promise(r=>setTimeout(r,3000));
      }
      return out;
    }, +(process.env.TRIALS||5));
    const res=await page.evaluate(async(ms)=>{
      const buddy=document.getElementById('nm-buddy');
      const c=(el)=>{if(!el)return null; const r=el.getBoundingClientRect(); return r.width?[r.left+r.width/2,r.top+r.height/2]:null;};
      const parts=()=>{const box=buddy.querySelector('.atl-figure-box'); const b=c(box); return {b, h:[...buddy.querySelectorAll('.atl-layer-body .atl-hand')].slice(0,2).map(c), head:c(buddy.querySelector('.atl-layer-body .atl-head'))};};
      const hist={}; let snaps=0; const seen=new Set(); const where=[];
      const t0=performance.now();
      await new Promise(done=>{const f=()=>{
        const p=parts(); if(p.b){
          const pts={head:p.head, hl:p.h[0], hr:p.h[1]};
          for(const [k,v] of Object.entries(pts)){ if(!v) continue; const rel=[v[0]-p.b[0], v[1]-p.b[1]]; const H=hist[k]||(hist[k]=[]); H.push(rel); if(H.length>5) H.shift();
            if(H.length===5){ const d=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]); const jump=d(H[4],H[3]); const before=Math.max(d(H[3],H[2]),d(H[2],H[1]),d(H[1],H[0])); if(jump>4&&before<1){snaps++; where.push(`${k}@${Math.round(performance.now()-t0)}:${buddy.className.match(/nmb-act-\w+/)?.[0]||buddy.dataset.pose}`);} } }
        }
        const tail=buddy.querySelector('.atl-figure-box')?.atlasTail;
        seen.add('act:'+((buddy.className.match(/nmb-act-[\w-]+/)||[''])[0])); seen.add('pose:'+buddy.dataset.pose); if(tail) seen.add('tail:'+tail.act); seen.add('arms:'+buddy.dataset.atlasVariant); seen.add('mood:'+atlasMoodNow);
        if(performance.now()-t0<ms) requestAnimationFrame(f); else done(); }; requestAnimationFrame(f);});
      return {snaps, where:where.slice(0,10), distinct:[...seen].filter(x=>!/:(undefined)?$/.test(x))};
    }, +(process.env.MS||60000));
    console.log(JSON.stringify({latencyMs:lat, snapsPerRun:res.snaps, snapAt:res.where, distinct:res.distinct.length, list:res.distinct}));
    await browser.close();
}

// Brief 34 continues, step 1: are Atlas's fifteen moods fifteen faces at the
// sizes people see them? Draws every mood at SIZES (104 full, 28 head, 20
// tiny) per look, freezes every loop at t=0, and writes one PNG per cell to
// shots/facediff/<theme>-<look>-<size>-<mood>.png at device scale 1 (the real
// pixels). atlasfacediff.py then counts the distinct faces by pixel diff.
//   BASE=... THEME=dark SIZES=28,20 node atlasdepth2.js atlasfacediff
async function atlasfacediff() {
  const {boot}=require('./lib.js');
  const fs=require('fs');
  const THEME=process.env.THEME||'light';
  const OUT=(process.env.SCRATCH||'.')+'/shots/facediff';
  fs.mkdirSync(OUT,{recursive:true});
    const {browser,page}=await boot({viewport:{width:1200,height:900},deviceScaleFactor:+(process.env.ZOOM||1)});
    for(const look of (process.env.LOOK_ATLAS||'masculine,feminine').split(',')){
      for(const size of (process.env.SIZES||'104,28,20').split(',').map(Number)){
        await page.evaluate(({look,size,dark,zoom,before})=>{
          document.getElementById('atl-diff')?.remove();
          localStorage.setItem('atlas-look',look);
          clearTimeout(atlasMoodTimer); setAtlasMood=()=>{};
          const box=document.createElement('div'); box.id='atl-diff';
          // One flat colour under every cell: a card's gradient differs by position and reads as a face change.
          box.style.background=dark?'#1c1d22':'#ffffff';
          box.style.position='fixed'; box.style.inset=zoom?'60px auto auto 8px':'60px 8px 8px 8px'; box.style.width=zoom?'560px':''; box.style.zIndex='9999';
          box.style.display='flex'; box.style.flexWrap='wrap'; box.style.gap='6px'; box.style.alignContent='flex-start';
          for(const mood of Object.keys(ATLAS_MOODS)){
            const cell=document.createElement('span'); cell.dataset.mood=mood; cell.style.display='inline-block'; cell.style.lineHeight='0';
            cell.append(atlasDraw(size,mood)); box.append(cell);
          }
          document.body.append(box); localStorage.removeItem('atlas-look');
          // BEFORE=1 rebuilds the faces as they were before the cue (Brief 34
          // continues, step 1): no lazy sheet, no cue, no brows on the tiny bust.
          if(before){document.querySelector('link[href*="atlas-lazy"]')?.remove(); box.querySelectorAll('.atl-cue, .atl-tiny .atl-brow').forEach(n=>n.remove());}
        },{look,size,dark:THEME==='dark',zoom:!!process.env.ZOOM,before:!!process.env.BEFORE});
        await page.waitForTimeout(1800);
        await page.evaluate(()=>document.getAnimations().forEach(a=>{try{if(a instanceof CSSTransition)a.finish();else{a.currentTime=0;a.pause();}}catch(e){}}));
        await page.waitForTimeout(100);
        // ZOOM=4 writes one sheet per size to look at instead of the cells.
        if(process.env.ZOOM){await (await page.$('#atl-diff')).screenshot({path:`${OUT}/../facesheet-${THEME}-${look}-${size}.png`,clip:undefined});continue;}
        for(const cell of await page.$$('#atl-diff > span')){
          const mood=await cell.getAttribute('data-mood');
          await (await cell.$('svg')).screenshot({path:`${OUT}/${THEME}-${look}-${size}-${mood}.png`});
        }
      }
    }
    await browser.close();
}

// One look, every pose, animations and transitions off, at 6x: still frames
// for a pixel comparison between two builds ("the masculine look is
// pixel-identical"). Compare with scratchpad/pngpixel.py's read_png.
//   LOOK=masculine TAG=before BASE=... SCRATCH=... node atlasdepth2.js atlasstill
async function atlasstill() {
  const { boot } = require('./lib.js');
  const LOOK = process.env.LOOK || 'masculine';
  const TAG = process.env.TAG || 'after';
  const THEME = process.env.THEME || 'light';
  const POSES = (process.env.POSES || 'stand,sit,float,lie-2,lie,curl').split(',');
    const { browser, page } = await boot({ viewport: { width: 600, height: 700 } });
    for (const pose of POSES) {
      await page.evaluate(({ look, pose }) => {
        document.getElementById('atl-still')?.remove();
        localStorage.setItem('atlas-look', look);
        const box = document.createElement('div'); box.id = 'atl-still';
        Object.assign(box.style, { position: 'fixed', left: '0', top: '0', width: '600px', height: '700px', zIndex: '9999', overflow: 'hidden', background: '#808080' });
        document.getElementById('nm-buddy')?.remove();
        const holder = document.createElement('div'); holder.id = 'nm-buddy';
        Object.assign(holder.style, { position: 'absolute', left: '110px', top: '70px', width: '64px', height: '92px', transform: 'scale(6)', transformOrigin: '0 0' });
        const fig = atlasFigure(); Object.assign(fig.style, { position: 'relative', display: 'block', width: '64px', height: '92px' });
        if (pose !== 'stand') holder.dataset.pose = pose;
        for (const el of [holder, ...fig.querySelectorAll('*'), fig]) { el.style.animation = 'none'; el.style.transition = 'none'; }
        holder.append(fig); box.append(holder); document.body.append(box);
      }, { look: LOOK, pose });
      await page.waitForTimeout(700);
      const el = await page.$('#atl-still');
      await el.screenshot({ path: `${process.env.SCRATCH || '.'}/shots/still-${TAG}-${THEME}-${LOOK}-${pose}.png` });
    }
    await page.evaluate(() => localStorage.removeItem('atlas-look'));
    await browser.close();
}

const CASES = {
  atlasgait,
  atlasmoodgrid,
  atlasprop,
  atlaswake,
  atlassmooth,
  atlasfacediff,
  atlasstill,
};
const names = process.argv.slice(2);
const unknown = names.filter((n) => !Object.prototype.hasOwnProperty.call(CASES, n));
if (unknown.length) {
  console.error(`unknown case: ${unknown.join(", ")}`);
  console.error(`cases: ${Object.keys(CASES).join(", ")}`);
  process.exit(2);
}
(async () => {
  for (const name of names.length ? names : Object.keys(CASES)) await CASES[name]();
})();
