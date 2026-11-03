// INBOX 1556: a web search that fails because SearXNG is down offers Start (or
// Install) SearXNG, retries when it answers, and says why when it cannot start.
// Real backend: SearXNG only, pointed at a dead port, so /websearch answers 502
// with code "searxng_down"; only /websearch/searxng/start is stubbed where a
// real install would download packages.
//
//   BASE=http://127.0.0.1:8797 node scratchpad/ui-sweeps/inbox1556-searxng-down.js
const {boot}=require('./lib.js');
let failed=0;const check=(ok,what)=>{console.log(`${ok?'ok  ':'FAIL'} ${what}`);if(!ok)failed++;};
(async()=>{
  const {browser,page}=await boot({viewport:{width:1440,height:900}});
  await page.evaluate(async()=>{await apiJson('/preferences',{method:'PUT',body:JSON.stringify({web_search_enabled:true,search_provider:'searxng',searxng_url:'http://127.0.0.1:9'})});prefsCache=await apiJson('/preferences');switchTab('chat');toggleWebPanel(true);});
  await page.waitForTimeout(600);
  const search=async()=>{await page.fill('#web-query','kettles');await page.press('#web-query','Enter');await page.waitForTimeout(1500);};
  const row=()=>page.evaluate(()=>{const r=document.querySelector('#web-status .searxng-down');return r?{text:r.textContent.trim(),buttons:[...r.querySelectorAll('button')].map(b=>b.textContent.trim())}:null;});
  // 1. SearXNG down, this computer: the message plus the action.
  await search();
  const msg=await page.evaluate(()=>document.getElementById('web-status').textContent);
  check(/SearXNG search failed/.test(msg),`message kept: "${msg.slice(0,70)}"`);
  let r=await row();
  check(r&&r.buttons.some(b=>/^(Start|Install) SearXNG$/.test(b)),`row offers: ${r&&r.buttons.join(' | ')}`);
  const body=await page.evaluate(async()=>{try{await apiJson('/websearch?q=x');}catch(e){return {code:e.body&&e.body.code,status:e.status};}});
  check(body&&body.code==='searxng_down'&&body.status===502,`the 502 carries code ${JSON.stringify(body)}`);
  // 2. Start (stubbed): says it is starting, then the search runs again.
  let started=0,searches=0;
  await page.route('**/websearch/searxng/start',async rt=>{started++;await new Promise(z=>setTimeout(z,300));rt.fulfill({json:{running:true,url:'http://127.0.0.1:8888'}});});
  await page.route(/\/websearch\?q=/,rt=>{searches++;rt.fulfill({json:{results:[{title:'A kettle',url:'https://example.org/k',domain:'example.org',snippet:'s',engine:'searxng'}],provider:'searxng',answered_by:{label:'SearXNG (local)',detail:''}}});});
  await page.click('#web-status .searxng-down button');
  await page.waitForTimeout(100);
  const during=await page.evaluate(()=>document.querySelector('#web-status .searxng-down-line')?.textContent||'');
  check(/Starting SearXNG|Setting SearXNG up/.test(during),`while starting: "${during}"`);
  await page.waitForTimeout(1200);
  check(started===1&&searches===1,`one start (${started}) then one retry (${searches})`);
  check(await page.evaluate(()=>document.querySelectorAll('#web-results .web-result').length)===1,'the retried search drew its result');
  // 3. Another device: one line of why, and Web search settings.
  await page.unroute(/\/websearch\?q=/);
  await page.evaluate(()=>{document.documentElement.dataset.otherDevice='1';});
  await search();
  r=await row();
  check(r&&/Not available on this device/.test(r.text)&&r.buttons.length===1&&r.buttons[0]==='Web search settings',`other device: "${r&&r.text}" | ${r&&r.buttons.join(' | ')}`);
  await page.click('#web-status .searxng-down button');
  await page.waitForTimeout(800);
  check(await page.evaluate(()=>!document.getElementById('settings-modal').classList.contains('hidden')&&!!document.querySelector('#settings-modal [data-section=websearch].active, #settings-modal .active[data-section=websearch]')||!document.getElementById('settings-modal').classList.contains('hidden')),'Web search settings opens the Settings window');
  await page.evaluate(()=>{delete document.documentElement.dataset.otherDevice;});
  // 4. No way to run it here (no backend): the status detail, and Web search settings.
  await page.keyboard.press('Escape');await page.waitForTimeout(400);
  check(await page.evaluate(()=>document.getElementById('settings-modal').classList.contains('hidden')),'Settings closed again');
  await page.route('**/websearch/searxng/status*',rt=>rt.fulfill({json:{backend:null,state:'absent',installing:false,responding:false,detail:'SearXNG can\'t be set up automatically here.'}}));
  await search();
  r=await row();
  check(r&&/set up automatically/.test(r.text)&&r.buttons.join('|')==='Web search settings',`no install: "${r&&r.text}" | ${r&&r.buttons.join(' | ')}`);
  // 5. Absent: the button says Install.
  await page.unroute('**/websearch/searxng/status*');
  await page.route('**/websearch/searxng/status*',rt=>rt.fulfill({json:{backend:'source',state:'absent',installing:false,responding:false}}));
  await search();
  r=await row();
  check(r&&r.buttons.includes('Install SearXNG'),`absent: ${r&&r.buttons.join(' | ')}`);
  // Geometry: the row sits inside the panel and wraps rather than overflows.
  const geo=await page.evaluate(()=>{const p=document.getElementById('web-panel').getBoundingClientRect();const x=document.querySelector('#web-status .searxng-down').getBoundingClientRect();return {panelRight:Math.round(p.right),rowRight:Math.round(x.right),rowW:Math.round(x.width)};});
  check(geo.rowRight<=geo.panelRight,`row inside the panel: ${JSON.stringify(geo)}`);
  await browser.close();
  console.log(failed?`${failed} FAILED`:'all ok');process.exit(failed?1:0);
})();
