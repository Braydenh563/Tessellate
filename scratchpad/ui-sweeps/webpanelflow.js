// The Web panel's behaviours, driven the way a person drives them, against the
// same stubbed /websearch routes as webpanel.js (the sandbox has no SearXNG):
// Enter searches, ArrowDown walks from the field into the results and ArrowUp
// back, Enter opens the reader, Escape goes back, Stop cancels a slow search,
// Ctrl+F in the reader counts the page rather than the tab, the head's kebab
// names the engine's command, and Cite in chat puts a chip in the composer
// whose page rides on the next message to the model.
//
//   BASE=http://127.0.0.1:8790 node scratchpad/ui-sweeps/webpanelflow.js
const {boot}=require('./lib.js');
const RESULTS=Array.from({length:10},(_,i)=>({title:`Result number ${i+1} about local-first software`,url:`https://example${i}.org/a`,domain:`example${i}.org`,snippet:'A snippet.',via:['duckduckgo'],engine:'searxng'}));
const PAGE={url:'https://example0.org/a',domain:'example0.org',title:'Local-first software',words:300,read_minutes:2,text:'x',
  blocks:[{type:'p',text:'Local-first means the local copy is primary. Local copies sync.'},{type:'heading',level:2,text:'Local ideals'},{type:'p',text:'Fast, local, private.'}]};
let failed=0;const check=(ok,what)=>{console.log(`${ok?'ok  ':'FAIL'} ${what}`);if(!ok)failed++;};
(async()=>{
  const {browser,page}=await boot({viewport:{width:1440,height:900}});
  let delay=100;let sent=null;
  await page.route('**/websearch/searxng/status*',r=>r.fulfill({json:{backend:'docker',installing:false,state:'running',responding:true}}));
  await page.route('**/websearch/read*',r=>r.fulfill({json:PAGE}));
  await page.route(/\/websearch\?q=/,async r=>{await new Promise(z=>setTimeout(z,delay));r.fulfill({json:{results:RESULTS,provider:'searxng',answered_by:{label:'SearXNG (local)',detail:''}}}).catch(()=>{});});
  await page.route(/\/chat(\/stream)?(\?|$)/,async r=>{if(r.request().method()==='POST'){sent=r.request().postData();}r.fulfill({status:503,json:{detail:'stubbed'}});});
  await page.evaluate(()=>{prefsCache.web_search_enabled=true;localStorage.removeItem('webSearchHistory');switchTab('chat');toggleWebPanel(true);});
  await page.waitForTimeout(700);
  const dot=await page.evaluate(()=>{const d=document.getElementById('web-engine-dot');return {s:d.dataset.state,t:d.title};});
  check(dot.s==='running'&&/stay on this machine/.test(dot.t),`engine dot says "${dot.t}"`);
  await page.click('#web-panel-menu button');await page.waitForTimeout(200);
  const menu=await page.evaluate(()=>[...document.querySelectorAll('.action-menu:not(.hidden) .menu-item')].map(b=>b.textContent.trim()));
  check(menu[0]==='Stop SearXNG'&&menu.includes('Web search settings'),`head kebab: ${menu.join(' | ')}`);
  await page.keyboard.press('Escape');await page.waitForTimeout(150);
  await page.fill('#web-query','local-first');await page.press('#web-query','Enter');await page.waitForTimeout(500);
  check(await page.evaluate(()=>document.querySelectorAll('#web-results .web-result').length)===8,'Enter searched: 8 rows and a Show more');
  await page.focus('#web-query');await page.keyboard.press('ArrowDown');
  check(await page.evaluate(()=>document.activeElement.textContent.startsWith('Result number 1')),'ArrowDown from the field lands on the first result');
  await page.keyboard.press('ArrowDown');
  check(await page.evaluate(()=>document.activeElement.textContent.startsWith('Result number 2')),'ArrowDown walks to the second');
  await page.keyboard.press('ArrowUp');await page.keyboard.press('ArrowUp');
  check(await page.evaluate(()=>document.activeElement.id)==='web-query','ArrowUp from the first goes back to the field');
  await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');await page.waitForTimeout(400);
  check(await page.evaluate(()=>!document.getElementById('web-reader').classList.contains('hidden')),'Enter on a result opens the reader');
  // Find in page, scoped to the reader.
  await page.focus('#web-reader-back');await page.keyboard.press('Control+f');await page.waitForTimeout(200);
  await page.keyboard.type('local');await page.waitForTimeout(300);
  const count=await page.evaluate(()=>document.getElementById('global-find-count').textContent);
  // Five in the page's text; the reader's own title and the tab around it
  // would make it six or more.
  check(/of 5$/.test(count),`Ctrl+F in the reader counts the page only: "${count}"`);
  await page.keyboard.press('Escape');await page.waitForTimeout(150);
  check(await page.evaluate(()=>document.getElementById('global-find-bar').classList.contains('hidden')&&!document.getElementById('web-reader').classList.contains('hidden')),'the first Escape closes find and keeps the page');
  await page.focus('#web-reader-back');await page.keyboard.press('Escape');await page.waitForTimeout(150);
  check(await page.evaluate(()=>document.getElementById('web-reader').classList.contains('hidden')&&document.activeElement.textContent.startsWith('Result number 1')),'Escape in the reader goes back, to the result that was open');
  // Stop.
  delay=4000;await page.fill('#web-query','slow one');await page.press('#web-query','Enter');await page.waitForTimeout(200);
  check(await page.isVisible('#web-stop'),'Stop shows while a search is on its way');
  await page.click('#web-stop');await page.waitForTimeout(200);
  const st=await page.evaluate(()=>({stop:document.getElementById('web-stop').classList.contains('hidden'),status:document.getElementById('web-status').textContent}));
  check(st.stop&&st.status==='Stopped.','Stop cancels it and hides itself');
  // Cite in chat.
  delay=50;await page.press('#web-query','Enter');await page.waitForTimeout(400);
  await page.evaluate(()=>document.querySelector('.web-result-title').click());await page.waitForTimeout(400);
  await page.click('#web-reader-cite');await page.waitForTimeout(300);
  const chip=await page.evaluate(()=>document.querySelector('#chat-web-attachment:not(.hidden) .att-chip')?.textContent||'');
  check(/Local-first software/.test(chip),`Cite in chat puts a chip in the composer: "${chip.trim()}"`);
  await page.evaluate(()=>sendChatMessage('What does it say about sync?'));await page.waitForTimeout(800);
  check(Boolean(sent)&&/citing this web page: Local-first software/.test(sent)&&/Local copies sync/.test(sent),'the page rides on the message to the model');
  check(await page.evaluate(()=>document.getElementById('chat-web-attachment').classList.contains('hidden')),'and the chip is cleared after sending');
  const bubble=await page.evaluate(()=>[...document.querySelectorAll('#chat-messages .msg.user')].pop()?.textContent||'');
  check(!/citing this web page/.test(bubble),'the bubble shows only what was typed');
  await browser.close();
  if(failed){console.log(`FAIL: ${failed}`);process.exit(1);}console.log('ok');
})();
