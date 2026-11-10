// Graph grouping (INBOX 431 (6)): category cohesion and the loose notes' ring.
// GROUP=0 or 1 (the View menu's Group by category). Lower cohesion is tighter.
// Seed with a few categories and links first (150 notes, 8 categories).
const {boot}=require('./lib.js');
(async()=>{
 const {browser,page}=await boot();
 await page.evaluate((g)=>localStorage.setItem('graph-group', g), process.env.GROUP||'1');
 await page.click('#tab-btn-graph'); await page.waitForTimeout(10000);
 const m=await page.evaluate(()=>{
  const ns=(graphNodesRef||[]).filter(n=>Number.isFinite(n.x)); const links=new Map(); 
  const deg=new Map(ns.map(n=>[n.id,0])); for (const e of (gcTab.edges||[])) { const a=e.source.id??e.source, b=e.target.id??e.target; deg.set(a,(deg.get(a)||0)+1); deg.set(b,(deg.get(b)||0)+1); }
  const cx=ns.reduce((a,n)=>a+n.x,0)/ns.length, cy=ns.reduce((a,n)=>a+n.y,0)/ns.length;
  const d=(n,x,y)=>Math.hypot(n.x-x,n.y-y);
  const byCat=new Map(); for(const n of ns){ if(!byCat.has(n.category)) byCat.set(n.category,[]); byCat.get(n.category).push(n);}
  let intra=0; for(const [c,arr] of byCat){ const x=arr.reduce((a,n)=>a+n.x,0)/arr.length, y=arr.reduce((a,n)=>a+n.y,0)/arr.length; for(const n of arr) intra+=d(n,x,y);} intra/=ns.length;
  const overall=ns.reduce((a,n)=>a+d(n,cx,cy),0)/ns.length;
  const orph=ns.filter(n=>!deg.get(n.id)), linked=ns.filter(n=>deg.get(n.id));
  const mean=(a)=>a.reduce((s,n)=>s+d(n,cx,cy),0)/Math.max(1,a.length);
  return {n:ns.length, cohesion:(intra/overall).toFixed(2), orphanDist:Math.round(mean(orph)), linkedDist:Math.round(mean(linked)), orphanRatio:(mean(orph)/mean(linked)).toFixed(2), orphans:orph.length};
 });
 console.log(process.env.GROUP, JSON.stringify(m)); await browser.close();
})();
