// L541: Quick access when app-features.js is slow (3 s) or fails (500). Measured 2026-11-13:
// slow paints 5 tiles at 2.3 s, no page errors; a 500 leaves the box empty with the
// lazyLoadFailed toast, and the next dashboard visit paints 5 tiles.
const {boot}=require('./lib.js');
(async()=>{
 for (const mode of ['slow','fail']) {
  const {browser,ctx,page}=await boot({serviceWorkers:'block'});
  const errs=[]; page.on('pageerror',e=>errs.push(e.message));
  await ctx.route(/\/js\/app-features\.js/, async r=>{ if(mode==='slow'){await new Promise(x=>setTimeout(x,3000)); return r.continue();} return r.fulfill({status:500,body:'x'}); });
  await page.reload({waitUntil:'domcontentloaded'}); await page.waitForTimeout(800);
  if (await page.isVisible('#lock-password')) { await page.fill('#lock-password','testpassword123'); await page.click('#lock-submit'); }
  const t0=Date.now(); let painted=null;
  for(let i=0;i<80;i++){ const n=await page.evaluate(()=>document.querySelectorAll('#dash-quicklinks .launch-row > *').length); if(n){painted=Date.now()-t0;break;} await page.waitForTimeout(100);}
  const toast=await page.evaluate(()=>[...document.querySelectorAll('.toast,.toast-msg')].map(e=>e.textContent.trim()).join(' | '));
  const box=await page.evaluate(()=>document.getElementById('dash-quicklinks')?.innerText.slice(0,120));
  console.log(JSON.stringify({mode,painted,errs,toast,box}));
  if(mode==='fail'){ await ctx.unroute(/\/js\/app-features\.js/); await page.evaluate(()=>switchTab('notes')); await page.waitForTimeout(500); await page.evaluate(()=>switchTab('dashboard')); await page.waitForTimeout(2500);
    console.log('retry', await page.evaluate(()=>document.querySelectorAll('#dash-quicklinks .launch-row > *').length)); }
  await browser.close();
 }
})();
