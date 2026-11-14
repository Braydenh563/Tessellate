// Every way a note is made, measured end to end (INBOX 434): keystrokes or
// clicks from anywhere to saved, ms from the save to the note in the list
// (`allEntries`), ms to filed with no model (the postponed lexical filer), and
// what happens when the server is gone mid-save (the text kept? a retry?).
// Prints one line per path. Read-only apart from the notes it makes.
//
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/captureaudit.js
// PATHS=capture,quick,... runs a subset.
const {boot}=require('./lib.js');
const only=(process.env.PATHS||'').split(',').filter(Boolean);
const want=(name)=>!only.length||only.includes(name);
(async()=>{
const {browser,ctx,page}=await boot({viewport:{width:1440,height:900}});
const out=[];
const row=(path,fields)=>out.push(`${path.padEnd(22)} ${Object.entries(fields).map(([k,v])=>`${k}=${v}`).join('  ')}`);
const focused=()=>page.evaluate(()=>{const e=document.activeElement;return e?`${e.tagName.toLowerCase()}${e.id?'#'+e.id:''}${e.className&&typeof e.className==='string'?'.'+e.className.split(' ')[0]:''}`:'none';});
//: In the page: wait until a note whose text holds `marker` is in
//: `allEntries` (what the list paints from), and then until it is filed.
const timeToList=(marker,t0)=>page.evaluate(async([m,t0])=>{
  const start=t0??performance.now(); const deadline=start+15000;
  while(performance.now()<deadline){
    const hit=(typeof allEntries!=='undefined'?allEntries:[]).find(e=>(e.content||'').includes(m));
    if(hit) return {ms:Math.round(performance.now()-start), id:hit.id, cat:hit.category, state:hit.filing_state};
    await new Promise(r=>setTimeout(r,10));
  }
  return {ms:'never'};
},[marker,t0]);
const timeToFiled=(id)=>page.evaluate(async(id)=>{
  const start=performance.now();
  while(performance.now()-start<20000){
    const r=await fetch(`/entries/${id}`,{headers:{'X-Auth-Token':localStorage.getItem('token')}});
    if(r.ok){const e=await r.json(); if(e.filing_state!=='pending') return {ms:Math.round(performance.now()-start),cat:e.category,state:e.filing_state};}
    await new Promise(r=>setTimeout(r,50));
  }
  return {ms:'never'};
},id);
const stamp=()=>Math.random().toString(36).slice(2,8);
const mark=()=>page.evaluate(()=>performance.now());
const goDash=async()=>{await page.evaluate(()=>switchTab('dashboard'));await page.waitForTimeout(600);};

// 1. Capture from the dashboard: Ctrl+Shift+N, type, Ctrl+Enter.
if(want('capture')){
  await goDash();
  const m='cap'+stamp(); const text=`Garden plan for tomatoes and basil ${m}`;
  await page.keyboard.press('Control+Shift+N'); await page.waitForTimeout(700);
  const f=await focused();
  await page.keyboard.type(text);
  const t0=await mark(); await page.keyboard.press('Control+Enter');
  const l=await timeToList(m,t0); const fl=l.id?await timeToFiled(l.id):{};
  row('capture (Ctrl+Shift+N)',{keys:`1+typing+1`,focus:f,list_ms:l.ms,filed_ms:fl.ms,cat:fl.cat});
}
// 2. The global shortcut from each tab: where the caret is after it.
if(want('shortcut')){
  for(const tab of ['dashboard','notes','chat','library','graph','whiteboard','timeline','reminders']){
    await page.evaluate((t)=>switchTab(t),tab).catch(()=>{}); await page.waitForTimeout(900);
    const before=await page.evaluate(()=>localStorage.getItem('activeTab'));
    const t0=await mark(); await page.keyboard.press('Control+Shift+N');
    const r=await page.evaluate(async(t0)=>{const s=performance.now();while(performance.now()-s<3000){const a=document.activeElement;if(a&&(a.closest?.('.note-surface')||a.id==='entry-content'||a.closest?.('#quick-note'))) return {ms:Math.round(performance.now()-t0),el:a.closest('#quick-note')?'quick-note':'capture'};await new Promise(r=>setTimeout(r,10));}return {ms:'never'};},t0);
    const after=await page.evaluate(()=>localStorage.getItem('activeTab'));
    row(`shortcut from ${tab}`,{to_caret_ms:r.ms,in:r.el||'-',left_page:before!==after?`yes (${before}->${after})`:'no'});
    await page.keyboard.press('Escape'); await page.waitForTimeout(200);
  }
}
// 2b. Quick note (Alt+N) from each tab: saved without leaving it.
if(want('quick')){
  for(const tab of ['dashboard','chat','library','graph','timeline']){
    await page.evaluate((t)=>switchTab(t),tab).catch(()=>{}); await page.waitForTimeout(900);
    const t0=await mark(); await page.keyboard.press('Alt+N');
    const r=await page.evaluate(async(t0)=>{const s=performance.now();while(performance.now()-s<3000){if(document.activeElement?.id==='quick-note-text') return Math.round(performance.now()-t0);await new Promise(r=>setTimeout(r,10));}return 'never';},t0);
    const m='qn'+stamp();
    await page.keyboard.type(`Quick thought on ${tab} ${m} #quick`);
    const t1=await mark(); await page.keyboard.press('Control+Enter');
    const l=await timeToList(m,t1);
    const after=await page.evaluate(()=>localStorage.getItem('activeTab'));
    const open=await page.evaluate(()=>document.getElementById('quick-note')?.open);
    row(`quick note on ${tab}`,{to_caret_ms:r,keys:'1+typing+1',list_ms:l.ms,stayed:after===tab,closed:!open});
  }
  // Escape keeps the words; the next open brings them back.
  await page.keyboard.press('Alt+N'); await page.waitForTimeout(300);
  await page.keyboard.type('Half a thought');
  await page.keyboard.press('Escape'); await page.waitForTimeout(200);
  await page.keyboard.press('Alt+N'); await page.waitForTimeout(300);
  const kept=await page.evaluate(()=>document.getElementById('quick-note-text').value);
  row('quick note Esc+reopen',{kept:JSON.stringify(kept)});
  await page.evaluate(()=>{document.getElementById('quick-note-text').value='';localStorage.removeItem('quickNoteDraft');document.getElementById('quick-note').close();});
}
// 3. The command palette.
if(want('palette')){
  await goDash();
  await page.keyboard.press('Control+K'); await page.waitForTimeout(400);
  await page.keyboard.type('new note'); await page.waitForTimeout(300);
  await page.keyboard.press('Enter'); await page.waitForTimeout(900);
  row('palette "new note"',{keys:'1+8+1',focus:await focused()});
  await page.keyboard.press('Escape');
}
// 4. Paste of text, a URL, an image into the capture box.
if(want('paste')){
  await page.evaluate(()=>startNewNote()); await page.waitForTimeout(800);
  const m='url'+stamp();
  const r=await page.evaluate(async(m)=>{
    const target=document.activeElement;
    const dt=new DataTransfer(); dt.setData('text/plain',`https://example.com/${m}`);
    target.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));
    await new Promise(r=>setTimeout(r,400));
    return document.getElementById('entry-content').value;
  },m);
  row('paste a URL',{box:JSON.stringify(r.slice(0,80))});
  const img=await page.evaluate(async()=>{
    const c=document.createElement('canvas');c.width=4;c.height=4;const blob=await new Promise(r=>c.toBlob(r,'image/png'));
    const dt=new DataTransfer(); dt.items.add(new File([blob],'shot.png',{type:'image/png'}));
    document.activeElement.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));
    await new Promise(r=>setTimeout(r,500));
    return {box:document.getElementById('entry-content').value.slice(-60),chips:document.querySelectorAll('#entry-attachment-chips > *').length};
  });
  row('paste an image',{box:JSON.stringify(img.box),chips:img.chips});
  const file=await page.evaluate(async()=>{
    const dt=new DataTransfer(); dt.items.add(new File(['hello'],'notes.txt',{type:'text/plain'}));
    const target=document.getElementById('entry-content').parentElement.querySelector('.cm-content')||document.getElementById('entry-content');
    target.dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true}));
    await new Promise(r=>setTimeout(r,500));
    return {chips:document.querySelectorAll('#entry-attachment-chips > *').length, target:target.className};
  });
  row('drop a file on box',{chips:file.chips,target:file.target});
  // Clean up the composer so later paths start empty.
  await page.evaluate(()=>{resetCaptureForm(document.getElementById('entry-content'),document.getElementById('entry-title'));clearStagedImages?.();captureStagedFiles=[];});
}
// 5. The selection menu's Save as a note.
if(want('selection')){
  const m='sel'+stamp();
  await page.evaluate((m)=>{switchTab('notes');showNotesSection('browse');},m); await page.waitForTimeout(600);
  const t0=await mark();
  await page.evaluate((m)=>saveSelectionAsNote(`Selected words about bread ${m}`),m);
  const l=await timeToList(m,t0); const fl=l.id?await timeToFiled(l.id):{};
  row('selection save',{clicks:'select+menu+1',list_ms:l.ms,filed_ms:fl.ms,cat:fl.cat});
}
// 6. The graph's new note.
if(want('graph')){
  const m='gr'+stamp();
  await page.evaluate(()=>switchTab('graph')); await page.waitForTimeout(2500);
  await page.evaluate(()=>openGraphNewNote()); await page.waitForTimeout(500);
  const f=await focused();
  await page.keyboard.type(`Graph note on rivers ${m}`);
  const t0=await mark(); await page.keyboard.press('Control+Enter');
  const l=await timeToList(m,t0); const fl=l.id?await timeToFiled(l.id):{};
  row('graph new note',{focus:f,list_ms:l.ms,filed_ms:fl.ms,cat:fl.cat});
}
// 6b. The dashboard's Quick capture widget, when it is on the dashboard.
if(want('dash')){
  await goDash();
  const box=await page.$('textarea[aria-label="Quick capture"]');
  if(!box){row('dashboard widget',{present:'no'});}
  else{
    const m='dw'+stamp();
    await box.fill(`Dashboard thought on kites ${m} #outdoors`);
    const t0=await mark(); await box.press('Control+Enter');
    const l=await timeToList(m,t0); const fl=l.id?await timeToFiled(l.id):{};
    const tags=await page.evaluate((id)=>(typeof allEntries!=='undefined'?allEntries:[]).find(e=>e.id===id)?.tags,l.id);
    row('dashboard widget',{list_ms:l.ms,filed_ms:fl.ms,tags:JSON.stringify(tags)});
  }
}
// 7. Server down mid-save, from Capture.
if(want('offline')){
  await page.evaluate(()=>startNewNote()); await page.waitForTimeout(800);
  const m='off'+stamp();
  await page.keyboard.type(`Offline thought about trains ${m}`);
  await ctx.route('**/entries',(route)=>route.request().method()==='POST'?route.abort('connectionrefused'):route.continue());
  await page.keyboard.press('Control+Enter'); await page.waitForTimeout(1200);
  const s=await page.evaluate(()=>({box:document.getElementById('entry-content').value,status:document.getElementById('save-status').textContent.trim(),draft:localStorage.getItem('captureDraft'),outbox:localStorage.getItem('noteOutbox')}));
  row('offline save',{kept_in_box:s.box.includes(m),draft:!!(s.draft||'').includes(m),outbox:!!(s.outbox||'').includes(m),status:JSON.stringify(s.status.slice(0,70))});
  await ctx.unroute('**/entries');
  // Back up: does it go by itself?
  const t0=await mark();
  await page.evaluate(()=>window.noteServerUp?.());
  const l=await timeToList(m,t0);
  row('offline -> back up',{synced_ms:l.ms});
  // Reload: kept?
  await page.reload({waitUntil:'domcontentloaded'}); await page.waitForTimeout(500);
  if(await page.isVisible('#lock-password').catch(()=>false)){await page.fill('#lock-password','testpassword123');await page.click('#lock-submit');}
  await page.waitForTimeout(3500);
  const after=await page.evaluate((m)=>({box:document.getElementById('entry-content').value.includes(m),saved:(typeof allEntries!=='undefined'?allEntries:[]).some(e=>(e.content||'').includes(m))}),m);
  row('offline -> reload',after);
}
// 8. The title survives a reload?
if(want('draft')){
  await page.evaluate(()=>startNewNote()); await page.waitForTimeout(800);
  await page.fill('#entry-title','Draft title kept');
  await page.keyboard.press('Tab');
  await page.evaluate(()=>{document.getElementById('entry-title').focus();});
  await page.evaluate(()=>{const s=noteSurfaceFor(document.getElementById('entry-content'));s?s.focus():document.getElementById('entry-content').focus();});
  await page.keyboard.type('Body kept after a crash');
  await page.evaluate(()=>{document.getElementById('entry-tags').value='kept';document.getElementById('entry-tags').dispatchEvent(new Event('input',{bubbles:true}));});
  await page.waitForTimeout(800);
  await page.reload({waitUntil:'domcontentloaded'});
  if(await page.waitForSelector('#lock-password',{state:'visible',timeout:5000}).catch(()=>null)){await page.fill('#lock-password','testpassword123');await page.click('#lock-submit');}
  await page.waitForTimeout(3500);
  const r=await page.evaluate(()=>({title:document.getElementById('entry-title').value,body:document.getElementById('entry-content').value,tags:document.getElementById('entry-tags').value}));
  row('draft after reload',{title:JSON.stringify(r.title),body:JSON.stringify(r.body.slice(0,40)),tags:JSON.stringify(r.tags)});
  await page.evaluate(()=>resetCaptureForm(document.getElementById('entry-content'),document.getElementById('entry-title')));
}
// 9. Escape in the capture box: anything lost?
if(want('escape')){
  await page.evaluate(()=>startNewNote()); await page.waitForTimeout(800);
  await page.keyboard.type('Escape test words');
  await page.keyboard.press('Escape'); await page.waitForTimeout(300);
  const r=await page.evaluate(()=>({box:document.getElementById('entry-content').value,draft:localStorage.getItem('captureDraft')}));
  row('Esc in capture',{box:JSON.stringify(r.box),focus:await focused()});
  await page.evaluate(()=>resetCaptureForm(document.getElementById('entry-content'),document.getElementById('entry-title')));
}
// 10. Inline #tag in the body.
if(want('hashtag')){
  await page.evaluate(()=>startNewNote()); await page.waitForTimeout(800);
  const m='ht'+stamp();
  await page.keyboard.type(`Recipe for soup ${m} #cooking #soup`);
  const t0=await mark(); await page.keyboard.press('Control+Enter');
  const l=await timeToList(m,t0);
  const tags=await page.evaluate((id)=>(typeof allEntries!=='undefined'?allEntries:[]).find(e=>e.id===id)?.tags,l.id);
  row('inline #tags',{tags:JSON.stringify(tags)});
}
// 11. Phone: the floating + to the box.
if(want('phone')){
  const p=await ctx.browser().newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
  await p.close();
}
console.log(out.join('\n'));
await browser.close();})();
