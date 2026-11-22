// Every `.notice` on one row: the icon, the words, the action and the close
// vertically centred (the owner 2026-11-22: "the icon and text sit at the top
// while the button and x sit in the middle"). Stubs /extras so every package
// reads missing, mounts the package notice in each real host plus the AI
// offline and web engine notices, and per notice prints the spread of its
// children's centre-y (max - min, must be under 1px while the words are one
// line), its paddings, and whether the action and close end on its right edge.
//   BASE=http://127.0.0.1:8781 THEME=dark WIDTH=1440 node scratchpad/ui-sweeps/noticealign.js
const {boot}=require('./lib.js');
const W=Number(process.env.WIDTH||1440);
(async()=>{
  const {browser,page}=await boot({viewport:{width:W,height:900}});
  const IDS=['languagetool','localllm','voice','speakers','semantic','documents','needle','rapidocr','translate','pyodide'];
  await page.route('**/extras',r=>r.fulfill({json:{running:false,extras:IDS.map(id=>({id,installed:false,label:id,enables:'',unavailable:id==='localllm'?'Install it from Settings, Packages.':''}))}}));
  await page.evaluate(()=>localStorage.removeItem('extraNoticeDismissed'));
  await page.evaluate(()=>openSettingsModal('models'));
  await page.waitForTimeout(1200);
  await page.evaluate(async(IDS)=>{
    // A host for each package inside the open Settings section, so the recipe is
    // measured where a notice really sits (a settings card's width and type).
    const sec=document.querySelector('.settings-section:not(.hidden), #settings-models');
    for(const id of IDS){const host=document.createElement('div');host.dataset.probe=id;sec.prepend(host);await extraNoticeMount(host,id,{fresh:true});}
  },IDS);
  await page.waitForTimeout(800);
  const rows=await page.evaluate(()=>{
    const out=[];
    for(const n of document.querySelectorAll('.notice')){
      const r=n.getBoundingClientRect();if(!r.width||!n.checkVisibility())continue;
      const kids=[...n.children].filter(k=>k.checkVisibility()&&k.getBoundingClientRect().width);
      const cy=kids.map(k=>{const b=k.getBoundingClientRect();return b.top+b.height/2;});
      const cs=getComputedStyle(n);
      const words=kids.find(k=>!/^(BUTTON|I)$/.test(k.tagName)&&!k.classList.contains('ph')&&!k.classList.contains('notice-end'));
      const lines=words?Math.round(words.getBoundingClientRect().height/parseFloat(getComputedStyle(words).lineHeight||20)):0;
      const btns=kids.filter(k=>k.tagName==='BUTTON'||k.classList.contains('notice-end'));
      const last=btns.length?btns[btns.length-1].getBoundingClientRect():null;
      out.push({name:(n.dataset.extra||n.className.split(' ').filter(c=>c!=='notice').join('.')||'notice'),
        spread:cy.length?Math.round((Math.max(...cy)-Math.min(...cy))*10)/10:0,
        rows:new Set(kids.map(k=>Math.round(k.getBoundingClientRect().top/4))).size,
        lines,pad:[cs.paddingTop,cs.paddingRight,cs.paddingBottom,cs.paddingLeft].join(' '),gap:cs.columnGap,
        rightGap:last?Math.round((r.right-parseFloat(cs.paddingRight)-parseFloat(cs.borderRightWidth)-last.right)*10)/10:null,
        h:Math.round(r.height),w:Math.round(r.width)});
    }
    return out;});
  let bad=0;
  for(const x of rows){const one=x.lines<=1;const fail=one&&x.spread>=1;if(fail)bad++;
    console.log(`[${W}] ${x.name.padEnd(28)} spread=${x.spread} lines=${x.lines} w=${x.w} h=${x.h} pad=${x.pad} gap=${x.gap} rows=${x.rows} rightGap=${x.rightGap}${fail?'  FAIL':''}`);}
  console.log(`[${W}] notices=${rows.length} failing=${bad}`);
  await page.screenshot({path:`${process.env.SCRATCH||'.'}/notices-${W}.png`});
  await browser.close();process.exit(bad?1:0);
})();
