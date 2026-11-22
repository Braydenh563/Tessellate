// L-world-class-107 (403): every reachable menu's width, padding, row height and icon and text
// columns, per tab. A menu whose rows disagree on icon or text x is misaligned. BASE=... node menu-rows.js
const {boot}=require('./lib.js');
const TABS=['dashboard','notes','library','chat','timeline','reminders','graph'];
(async()=>{const {browser,page}=await boot();const res=[];
for(const tab of TABS){
 await page.evaluate(t=>document.getElementById('tab-btn-'+t)?.click(),tab);await page.waitForTimeout(2000);
 const n=await page.evaluate(()=>{const v=[...document.querySelectorAll('.kebab-opener,[aria-haspopup="menu"]')].filter(b=>{const r=b.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(b).visibility!=='hidden'});v.forEach((b,i)=>b.dataset.sweepIdx=i);return v.length;});
 for(let i=0;i<Math.min(n,12);i++){
  const id=await page.evaluate(i=>{const b=document.querySelector(`[data-sweep-idx="${i}"]`);return b?(b.id||b.getAttribute('aria-label')||b.title||b.className).slice(0,40):null},i);
  try{await page.click(`[data-sweep-idx="${i}"]`,{timeout:1500,force:true});}catch(e){continue;}
  await page.waitForTimeout(350);
  const m=await page.evaluate(()=>{const menus=[...document.querySelectorAll('[role="menu"]')].filter(m=>{const r=m.getBoundingClientRect();return r.width>0&&r.height>0});const menu=menus.pop();if(!menu)return null;
   const mr=menu.getBoundingClientRect();const items=[...menu.querySelectorAll('[role="menuitem"],[role="menuitemcheckbox"],[role="menuitemradio"]')].filter(x=>x.getBoundingClientRect().height>0);
   const rows=items.map(it=>{const r=it.getBoundingClientRect();const cs=getComputedStyle(it);const ic=it.querySelector('.ph,svg,img');const ir=ic&&ic.getBoundingClientRect();
     const tw=document.createTreeWalker(it,NodeFilter.SHOW_TEXT,{acceptNode:n=>n.textContent.trim()&&!n.parentElement.closest('.ph')?1:3});const tn=tw.nextNode();let tx=null;if(tn){const rg=document.createRange();rg.selectNodeContents(tn);tx=rg.getBoundingClientRect().left-r.left;}
     return {h:Math.round(r.height),pl:cs.paddingLeft,pr:cs.paddingRight,icon:ir?+(ir.left-r.left).toFixed(1):null,text:tx!=null?+tx.toFixed(1):null,w:Math.round(r.width),fs:cs.fontSize};});
   const cs=getComputedStyle(menu);return {w:Math.round(mr.width),pad:cs.padding,n:rows.length,rows};});
  if(m){const uniq=k=>[...new Set(m.rows.map(r=>r[k]).filter(v=>v!=null))];
   res.push({tab,opener:id,w:m.w,pad:m.pad,n:m.n,h:uniq('h'),pl:uniq('pl'),pr:uniq('pr'),icon:uniq('icon'),text:uniq('text'),rowW:uniq('w'),fs:uniq('fs')});}
  await page.keyboard.press('Escape');await page.waitForTimeout(200);
 }
}
require('fs').writeFileSync(process.env.SCRATCH+'/menus.json',JSON.stringify(res,null,1));
console.log(res.length);await browser.close();})();
