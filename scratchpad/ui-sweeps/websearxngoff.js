// The Web panel with SearXNG stopped (the owner 2026-11-22: nothing said so
// until a search failed, and the failure's Try again and Start SearXNG sat at
// different x). Stubs status (STATE=stopped|running) and a searxng_down search.
//   BASE=http://127.0.0.1:8781 THEME=dark STATE=stopped node scratchpad/ui-sweeps/websearxngoff.js
// Prints the status shown at open, the dot's state and words, and after a
// failed search the x of the field, the message and each action. Exits 1 if
// the message and actions do not share the field's left edge.
const {boot}=require('./lib.js');
let bad=0;
const STATE=process.env.STATE||'stopped';
(async()=>{
  const {browser,page}=await boot({viewport:{width:1440,height:900}});
  const running=STATE==='running';
  await page.route('**/websearch/searxng/status*',r=>r.fulfill({json:{backend:'venv',installing:false,state:running?'running':'stopped',responding:running}}));
  await page.route(/\/websearch\?q=/,r=>r.fulfill({status:503,json:{detail:'The SearXNG search failed. Check that SearXNG is running, then try again.',code:'searxng_down'}}));
  await page.evaluate((p)=>{prefsCache.web_search_enabled=true;prefsCache.search_provider=p;switchTab('chat');},process.env.P||'searxng');
  await page.waitForTimeout(600);
  await page.evaluate(()=>toggleWebPanel(true));
  await page.waitForTimeout(1200);
  const open=await page.evaluate(()=>{const d=document.getElementById('web-engine-dot');const s=document.querySelector('.web-engine-notice')||document.getElementById('web-status');const f=document.querySelector('.web-search-field').getBoundingClientRect();
    return {noticeX:Math.round(s.getBoundingClientRect().left*10)/10,fieldX:Math.round(f.left*10)/10,above:s.getBoundingClientRect().bottom<=f.top,dot:d.dataset.state,title:d.title,aria:d.getAttribute('aria-label'),bg:getComputedStyle(d).backgroundColor,status:s.innerText.replace(/\s+/g,' ').trim(),buttons:[...s.querySelectorAll('button')].map(b=>b.innerText.trim())};});
  console.log(`[${STATE}] open: dot=${open.dot} bg=${open.bg} title="${open.title}" aria="${open.aria}"`);
  console.log(`[${STATE}] open status: "${open.status}" buttons=${JSON.stringify(open.buttons)} notice.x=${open.noticeX} field.x=${open.fieldX} aboveField=${open.above}`);
  if(!running&&!open.status)bad++;if(running&&open.status)bad++;
  if(!running){
    await page.fill('#web-query','local-first');await page.press('#web-query','Enter');await page.waitForTimeout(1500);
    const m=await page.evaluate(()=>{const x=(el)=>el?Math.round(el.getBoundingClientRect().left*10)/10:null;
      const s=document.getElementById('web-status');const field=document.querySelector('.web-search-field');
      const range=document.createRange();const tn=[...s.childNodes].flatMap(e=>e.nodeType===3?[e]:[...e.childNodes]).find(n=>n.nodeType===3&&n.textContent.trim());
      let msg=null;if(tn){range.selectNodeContents(tn);msg=Math.round(range.getClientRects()[0].left*10)/10;}
      const tx=(b)=>{const t=b.querySelector('.ph-text')||b;const r=document.createRange();r.selectNodeContents(t);return Math.round(r.getClientRects()[0].left*10)/10;};
      const btns=[...s.querySelectorAll('button')].map(b=>({t:b.innerText.trim(),x:x(b),ix:x(b.querySelector('.ph')||b),tx:tx(b),y:Math.round(b.getBoundingClientRect().top)}));
      return {field:x(field),msg,btns,text:s.innerText.replace(/\s+/g,' ').trim()};});
    console.log(`[${STATE}] error: field.x=${m.field} message.x=${m.msg} ${m.btns.map(b=>`${b.t}.x=${b.x} (icon ${b.ix}, words ${b.tx}) y=${b.y}`).join(' ')}`);
    console.log(`[${STATE}] error text: "${m.text}"`);
    if(m.msg!==m.field)bad++;
    const ys=new Set(m.btns.map(b=>b.y));if(ys.size>1)bad++;
    if(m.btns.length&&new Set(m.btns.map(b=>b.x)).size!==m.btns.length)bad++;
    if(m.btns.length&&Math.abs(m.btns[0].ix-m.field)>1)bad++;
  }
  await page.screenshot({path:`${process.env.SCRATCH||'.'}/web-off-${STATE}.png`});
  await browser.close();process.exit(bad?1:0);
})();
