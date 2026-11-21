// Phone More sheet: tap each row at 390 (touch) and check its surface is reached and on top (L446).
//   BASE=http://127.0.0.1:8790 node scratchpad/ui-sweeps/phonemore.js
const {boot}=require('./lib.js');
(async()=>{const {browser,page}=await boot({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
await page.reload({waitUntil:"domcontentloaded"});await page.waitForTimeout(2500);await page.fill("#lock-password","testpassword123").catch(()=>{});await page.click("#lock-submit").catch(()=>{});await page.waitForTimeout(3000);
const rows=await (async()=>{await page.tap('#phone-more-btn');await page.waitForTimeout(1200);const r=await page.$$eval('.sheet-list > *',els=>els.map(e=>e.textContent.trim()).filter(Boolean));await page.keyboard.press('Escape');await page.waitForTimeout(500);return r})();
console.log('rows',JSON.stringify(rows));
const checks={"Ask the agent":()=>{const i=document.querySelector('#command-palette-input');const r=i?.getBoundingClientRect();let e=i,hid=0;while(e){if(getComputedStyle(e).display==='none'||getComputedStyle(e).visibility==='hidden'||+getComputedStyle(e).opacity===0)hid++;e=e.parentElement}return {r:r&&[r.x|0,r.y|0,r.width|0,r.height|0],hid,top:document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===i}},
"Guide":()=>{const i=document.querySelector('#help-chat-input');const r=i?.getBoundingClientRect();return {r:r&&[r.x|0,r.y|0,r.width|0,r.height|0],top:document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===i}},
"Timeline":()=>({tab:document.querySelector('#tab-bar button.active')?.dataset.tab,vis:!!document.querySelector('#timeline-tab, #tab-timeline, [data-panel=timeline]')?.getClientRects().length}),
"Reminders":()=>({tab:document.querySelector('#tab-bar button.active')?.dataset.tab}),
"Graph":()=>({tab:document.querySelector('#tab-bar button.active')?.dataset.tab}),
"Commands":()=>{const i=document.querySelector('#palette-input');const r=i?.getBoundingClientRect();return {r:r&&[r.x|0,r.y|0,r.width|0,r.height|0],top:document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===i}},
"Settings":()=>({open:!!document.querySelector('#settings-modal')?.getClientRects().length})};
for(const name of rows){await page.tap('#phone-more-btn');await page.waitForTimeout(1200);
const row=page.locator('.sheet-list > *',{hasText:name}).first();await row.tap().catch(e=>console.log('tapfail',name,e.message.slice(0,80)));await page.waitForTimeout(1800);
const fn=Object.entries(checks).find(([k])=>name.startsWith(k));
console.log(name,JSON.stringify(await page.evaluate(fn?fn[1]:()=>0)),'sw',await page.evaluate(()=>document.documentElement.scrollWidth),'focus',await page.evaluate(()=>document.activeElement?.id||document.activeElement?.className?.slice?.(0,40)));
for(let i=0;i<2;i++){await page.keyboard.press('Escape');await page.waitForTimeout(400);}
await page.evaluate(()=>switchTab("dashboard"));await page.waitForTimeout(600);}
await browser.close();})();
