// Text contrast, both themes (BACKLOG §116.1 item 4). For every visible text
// element on each tab (and each Settings section), the computed colour
// against the first non-transparent background up the tree, as a WCAG
// contrast ratio. Reports anything under 4.5:1 (3:1 for text ≥ 18.66px or
// bold ≥ 14px). THEME=dark for the other theme. Computed colours, not pixel
// samples, so glass and images do not confuse it — a translucent card is
// composited against whatever is behind it and reported as "translucent".
const {boot}=require('./lib.js');
// Every tab page, not only the seven with a button in the tab bar.
//
// Documents, the whiteboard and the mind map are reached from a dock or a
// Library row rather than from `[data-tab]`, so a sweep that clicked the tab
// bar never once measured them: three whole surfaces, one of them the
// documents editor, had never been contrast-checked when this was found
// (`archive/agent-remaining/image-cards.md`, 2026-09-12). `switchTab` is how the app
// itself gets there, so it is how this gets there.
// 'whiteboard' was in this list and was never once measured, at any width.
// There is no `#tab-whiteboard`: a board is a surface inside the Library's
// Boards & maps section, and `revealTab` hides every page in its own TABS
// list and finds nothing to show for a name that is not in it, so the sweep
// measured an empty window and printed "ok". That is the exact failure the
// element count added below exists to catch, and this is its first catch.
// The board is reached the way the app reaches it: the sub-tab, then a board.
const TABS=['dashboard','notes','chat','graph','library','timeline','reminders','documents'];
// The sub-tabs, which are whole screens wearing one tab's id. Notes has four
// and Library has five, and only whichever was last open had ever been
// measured.
const SUBTABS={
  notes:['browse','capture','writing-room','ask'],
  library:null,  // filled in from the strip itself: its ids move with the plan
};
const SECTIONS=['models','searchindex','appearance','account','tools','skills','memory','learned','tasks','data','logs','extras','about'];
// ONLY=settings skips the tabs and measures the Settings sections alone.
// WIDTH/HEIGHT, because this sweep took no viewport at all and had therefore
// only ever run at `boot`'s default 1440x900 (UI_MODERNISATION_PLAN Phase 11
// item 11 named it as open for exactly that reason). A phone is not the same
// page: below 600 the docks fold, the sidebars park off screen, the tab bar
// is captions under icons and the header is three controls, so a colour
// measured at 1440 says nothing about a control that only exists at 390.
// Below 600 it asks for a touch context too, since half of that band's rules
// are behind `(pointer: coarse)`.
const WIDTH=Number(process.env.WIDTH||1440);
const HEIGHT=Number(process.env.HEIGHT||(WIDTH<600?844:900));
const PHONE=WIDTH<600;
// **A surface that came back empty is a failure, not a note.** The count below
// was added after `whiteboard` sat in the tab list with no tab page to open,
// so the sweep measured an empty window at every width and reported 0
// low-contrast findings, which reads as a pass: and it reported it for a long
// time. Counting the elements caught it; printing the count did not stop the
// next one, because a line of prose in the middle of thirty-odd "ok"s is not
// something anyone reads and the gate that runs this file only ever saw exit
// 0. The surfaces that measured nothing are collected here, named at the end,
// and the process exits non-zero. A sweep that measures nothing must fail.
const empty=[];
// **A low-contrast finding fails the sweep** (readings.md: it used to print and
// exit 0, so the gate's `sweep-contrast` step stayed green over a finding).
// Measured clean at 1440, 820 and 390 in both themes before this was made a
// failure. A finding whose background had to be composited from a translucent
// layer ("~" after the ratio) is the worst-case estimate the comment above
// `over` describes, so it is reported but does not fail on its own.
const low=[];
(async()=>{const {browser,page}=await boot({viewport:{width:WIDTH,height:HEIGHT},hasTouch:PHONE,isMobile:PHONE});
const run=async(label)=>{const r=await page.evaluate(()=>{
  const cv=document.createElement('canvas');cv.width=cv.height=1;const cx=cv.getContext('2d',{willReadFrequently:true});
  const parse=(c)=>{if(!c||c==='transparent')return null;const m=c.match(/^rgba?\(([^)]+)\)$/);if(m){const p=m[1].split(/[\s,\/]+/).map(Number);return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1};}
    // `color(srgb r g b / a)`, which is how Chromium reports a colour-mix()
    // result, in 0..1 channels. The canvas below refuses it here, so it read
    // as transparent and the image captions' dark scrim was measured as white
    // text on the white card behind it: "1.00~" for a caption that is legible.
    const s=c.match(/^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)$/);
    if(s)return {r:Math.round(+s[1]*255),g:Math.round(+s[2]*255),b:Math.round(+s[3]*255),a:s[4]===undefined?1:+s[4]};
    // oklab()/color-mix() results: let the canvas resolve them to bytes.
    cx.clearRect(0,0,1,1);cx.fillStyle='#000';cx.fillStyle=c;if(cx.fillStyle==='#000000'&&!/black|#000/.test(c))return null;cx.fillRect(0,0,1,1);const d=cx.getImageData(0,0,1,1).data;return {r:d[0],g:d[1],b:d[2],a:d[3]/255};};
  const lum=({r,g,b})=>{const f=(v)=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);};return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b);};
  const ratio=(a,b)=>{const l1=lum(a),l2=lum(b);return (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);};
  //: Translucent layers are composited over the opaque one found below them,
  //: not skipped: a caption on a 75% dark scrim over a white card was measured
  //: as white on white (1.00:1) when the scrim is what it is read against.
  //: Compositing over the card is the worst case for an image underneath
  //: (a white photo), which is the case the scrim exists for.
  const over=(top,base)=>({r:top.r*top.a+base.r*(1-top.a),g:top.g*top.a+base.g*(1-top.a),b:top.b*top.a+base.b*(1-top.a),a:1});
  const bgOf=(el)=>{let translucent=false;const layers=[];let base=null;for(let e=el;e;e=e.parentElement){const cs=getComputedStyle(e);if(cs.backgroundImage&&cs.backgroundImage!=='none')return {c:null,translucent,gradient:true};const c=parse(cs.backgroundColor);if(c&&c.a>0){if(c.a<1)translucent=true;if(c.a>=0.9){base=c;break;}layers.push(c);}}if(!base){const root=parse(getComputedStyle(document.body).backgroundColor);const html=parse(getComputedStyle(document.documentElement).backgroundColor);base=(root&&root.a>0)?root:(html&&html.a>0)?html:{r:255,g:255,b:255,a:1};translucent=true;}let c=base;for(let i=layers.length-1;i>=0;i--)c=over(layers[i],c);return {c:{r:Math.round(c.r),g:Math.round(c.g),b:Math.round(c.b),a:1},translucent};};
  // `checked` so an "ok" is backed by a number. A run that reached a surface
  // and found nothing wrong and a run whose surface never rendered both
  // printed "ok" before this, and the second is the one that matters: the
  // phone band's settings sections were reached by clicking a strip that is
  // hidden below 600, so every one of them was "ok" by never being looked at.
  const out=[];const seen=new Set();let checked=0;
  for(const el of document.querySelectorAll('.tab-page:not(.hidden) *, #settings-modal:not(.hidden) *, .modal-overlay:not(.hidden) *, [data-sheet] *, .action-menu *, #editor-menu:not(.hidden) *')){
    if(!el.checkVisibility||!el.checkVisibility())continue;
    const text=[...el.childNodes].filter(n=>n.nodeType===3&&n.textContent.trim()).map(n=>n.textContent.trim()).join(' ');
    if(!text)continue;const cs=getComputedStyle(el);const fg=parse(cs.color);if(!fg||fg.a<1)continue;checked++;
    const {c:bg,translucent,gradient}=bgOf(el);if(gradient||!bg)continue;const r=ratio(fg,bg);const size=parseFloat(cs.fontSize);const bold=parseInt(cs.fontWeight)>=700;const need=(size>=18.66||(bold&&size>=14))?3:4.5;
    if(r<need){const key=(el.id||el.className.toString().slice(0,40))+'|'+text.slice(0,20);if(seen.has(key))continue;seen.add(key);
      out.push(`${r.toFixed(2)}${translucent?'~':''} <${el.tagName.toLowerCase()}${el.id?'#'+el.id:'.'+[...el.classList].slice(0,2).join('.')}> "${text.slice(0,30)}" ${cs.color} on rgb(${bg.r},${bg.g},${bg.b})`);}
  }
  return {out:out.slice(0,12),checked};});
  console.log(`== ${label}: ${r.out.length?r.out.length+' low-contrast':'ok'} (${r.checked} text elements)`);r.out.forEach(l=>console.log('  '+l));
  if(r.out.some((l)=>!/^[\d.]+~/.test(l)))low.push(label);
  if(!r.checked){console.log('  nothing was measured here, which is a finding about the sweep, not the surface');empty.push(label);}};
const go=async(t)=>{await page.evaluate((name)=>{try{switchTab(name);}catch(e){}},t);await page.waitForTimeout(700);};
// ONLY=document measures the documents editor with a document open (DOCUMENTS_PLAN
// 17e). The `documents` entry in TABS reaches the tab with nothing open, so
// the editor, its dock, the formatting strip, the outline and every `.cm-md-*`
// decoration had never been read for contrast. One document holding each
// construct and a few writing findings, in every view.
if(process.env.ONLY==='document'){
  const body=['# Contrast fixture','','A paragraph with **bold**, *italic*, ==highlight==, `inline code`, a [link](https://example.com) and a [[Wiki link]] and teh misspelled wrnog words.','','## A section','','> A quotation that carries on for a while.','','> [!note] A callout','> Its body text.','','- [ ] an open task','- [x] a done task','- a bullet','','| Name | Value |','| --- | --- |','| one | 1 |','','```js','const a = 1; // comment','```','','A footnote.[^1]','','[^1]: The note.',''].join('\n');
  await page.evaluate(async(content)=>{const r=await api('/documents',{method:'POST',body:JSON.stringify({title:'Contrast fixture',content})});const d=await r.json();switchTab('documents');await openDocument(d.id);},body);
  await page.waitForSelector('#doc-editor .cm-content',{state:'visible',timeout:15000}).catch(()=>{});
  await page.waitForTimeout(2500);
  for(const view of ['live','source','split','rendered']){
    await page.evaluate((v)=>setDocView(v),view);await page.waitForTimeout(900);await run('documents/'+view);
  }
  await page.evaluate(()=>setDocView('live'));await page.waitForTimeout(600);
  const tab=await page.evaluate(()=>{const b=[...document.querySelectorAll('#doc-sidebar [role="tab"], #doc-sidebar button')].find((x)=>/^Outline/.test(x.textContent.trim()));if(b){b.click();return true;}return false;});
  if(tab){await page.waitForTimeout(500);await run('documents/outline');}
  console.log(`== done at ${WIDTH}x${HEIGHT}, theme ${process.env.THEME||'light'}`);
  await browser.close();process.exit(empty.length||low.length?1:0);
}
// ONLY=pr: the surfaces the 2026-10-17 PR changed, each opened the way a
// person opens it: the new chat page, the chat "/" menu, the timeline
// calendar (month, week, day) and its add sheet, the autocorrect menu.
if(process.env.ONLY==='pr'){
  await page.evaluate(async()=>{if((await apiJson('/entries?limit=1')).length)return;for(let i=0;i<4;i++)await apiJson('/entries',{method:'POST',body:JSON.stringify({content:`Sweep note ${i}\n\nSomething written about topic ${i}.`,category:'Sweep'})});const d=new Date();d.setHours(d.getHours()+3);await apiJson('/reminders',{method:'POST',body:JSON.stringify({text:'Sweep reminder',due_at:d.toISOString()})});}).catch(()=>{});
  await go('chat');await run('pr/chat (new)');
  await page.focus('#chat-input').catch(()=>{});await page.keyboard.type('/');await page.waitForTimeout(1200);await run('pr/chat slash menu');
  await page.keyboard.press('Escape');await page.fill('#chat-input','').catch(()=>{});
  for(const span of ['month','week','day']){
    await page.evaluate((sp)=>{localStorage.setItem('timeline-view','calendar');localStorage.setItem('timeline-cal-span',sp);switchTab('timeline');if(typeof timelineCal!=='undefined'){timelineCal.url='';timelineCal.span=sp;}paintTimeline();},span);
    await page.waitForTimeout(1500);await run('pr/timeline calendar '+span);
    if(span==='month'){
      await page.focus('.timeline-cal-monthcell[tabindex="0"]').catch(()=>{});await page.keyboard.press('n');await page.waitForTimeout(900);
      await page.keyboard.type('Dentist at 3pm');await page.waitForTimeout(900);await run('pr/calendar add sheet');
      await page.keyboard.press('Escape');await page.waitForTimeout(400);
    }
  }
  await go('notes');
  await page.evaluate(()=>document.querySelector('#notes-subtabs button[data-section="capture"], #notes-subtabs button[data-subtab="capture"]')?.click());await page.waitForTimeout(900);
  await page.click('#entry-content',{force:true}).catch(()=>{});await page.keyboard.type('I ran a teh ',{delay:30});await page.waitForTimeout(600);
  const m=await page.evaluate(()=>{const k=document.querySelector('.autocorrect-mark');if(!k)return false;const r=k.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2};});
  if(m){await page.mouse.move(m.x,m.y);await page.mouse.click(m.x,m.y);await page.waitForTimeout(500);await run('pr/autocorrect menu');}
  else console.log('== pr/autocorrect menu: SKIPPED, no mark was drawn');
  console.log(`== done at ${WIDTH}x${HEIGHT}, theme ${process.env.THEME||'light'}`);
  await browser.close();process.exit(empty.length||low.length?1:0);
}
for(const t of (process.env.ONLY==='settings'?[]:TABS)){
  await go(t);
  // A tab that would not open is worth saying so about, rather than being
  // silently reported as clean.
  const open=await page.evaluate((name)=>{const el=document.getElementById('tab-'+name);return el?!el.classList.contains('hidden'):null;},t);
  if(open===false){console.log(`== ${t}: SKIPPED, the tab did not open`);continue;}
  await run(t);
  const subs=SUBTABS[t]===null
    ? await page.evaluate(()=>[...document.querySelectorAll('#library-subtabs button')].map(b=>b.dataset.subtab||b.getAttribute('aria-controls')||b.textContent.trim()))
    : SUBTABS[t];
  if(!subs)continue;
  for(const sub of subs){
    const clicked=await page.evaluate(({tab,sub})=>{
      const strip=document.getElementById(tab+'-subtabs');
      if(!strip)return false;
      const btn=[...strip.querySelectorAll('button')].find(b=>(b.dataset.section||b.dataset.subtab||b.getAttribute('aria-controls')||b.textContent.trim())===sub);
      if(!btn)return false;btn.click();return true;
    },{tab:t,sub});
    if(!clicked)continue;
    await page.waitForTimeout(600);
    await run(`${t}/${sub}`);
  }
}
// A board and a map, each opened from the Boards & maps section the way a
// person opens one (there is no tab page for either, so they cannot join TABS).
// A board is also measured with every object selected, because the drag grip
// on a sticky or text box (`.wb-object-grip`), the resize handles and the
// selection bar only exist selected: the surfaces this sweep never read, where
// the small contrast rows lived (OPEN.md: "the sticky's grip and other small
// contrast rows"). Nothing is created here: a sweep that made a board on every
// run would fill the data directory it shares with every other sweep. If the
// notebook has no board or map to open it says so rather than passing quietly.
if(process.env.ONLY!=='settings'){
  for(const kind of ['board','map']){
    await go('library');
    const opened=await page.evaluate(async(kind)=>{
      document.querySelector('#library-subtabs button[data-target="library-view-whiteboard"]')?.click();
      await new Promise(r=>setTimeout(r,900));
      const card=[...document.querySelectorAll('.library-board-card')].find(c=>c.wbBoard&&(kind==='map'?c.wbBoard.type==='map':c.wbBoard.type!=='map'));
      if(!card)return 'no '+kind+' in this notebook';
      card.click();
      await new Promise(r=>setTimeout(r,1800));
      return document.getElementById('wb-topbar')?.offsetParent?'open':'it would not open';
    },kind);
    if(opened!=='open'){console.log(`== whiteboard (${kind}): SKIPPED, ${opened}`);continue;}
    await page.waitForTimeout(600);await run(`whiteboard (${kind} open)`);
    // Everything selected: the grips and handles are drawn for a selection.
    const sel=await page.evaluate(()=>{try{wbSelectAllItems();return true;}catch(e){return false;}});
    if(sel){await page.waitForTimeout(500);await run(`whiteboard (${kind}, all selected)`);
      // How many of the small selection-only marks were on screen to be read:
      // an "ok" over a board with none of them proves nothing about them.
      const marks=await page.evaluate(()=>({grips:[...document.querySelectorAll('.wb-object-grip')].filter(g=>g.checkVisibility()).length,handles:[...document.querySelectorAll('.wb-handle, .wb-resize-handle')].filter(g=>g.checkVisibility()).length}));
      console.log(`   selection marks on screen: ${marks.grips} grips, ${marks.handles} handles`);}
    // The board's own sidebar, one tab at a time (a board has Library, Notes,
    // Layers and Pages; a map has Library, This map and Outline).
    for(const side of (kind==='map'?['library','map','outline']:['library','notes','layers','pages'])){
      const ok=await page.evaluate((s)=>{try{wbOpenSidebar(s,{focus:false});return true;}catch(e){return false;}},side);
      if(!ok)continue;await page.waitForTimeout(700);await run(`whiteboard (${kind}) sidebar/${side}`);
    }
    await page.evaluate(()=>{try{wbCloseSidebar();}catch(e){}});
    await page.keyboard.press('Escape').catch(()=>{});await page.waitForTimeout(400);
  }
}

// `openSettingsModal`, not a click on `#settings-btn`: below 600 that button
// is hidden and Settings is a row in the header's `#header-more` menu (Phase
// 11 item 1), so a sweep that clicked it measured no Settings section at all
// at phone width and said nothing about having skipped them.
// The guide panel (INBOX 270 part 4): a sheet, so `.modal-overlay` already
// puts it in scope; it only had to be opened. Empty, then with a conversation,
// because the welcome and the bubbles are different text on different grounds.
if(process.env.ONLY!=='settings'){
  // The Guide is a lazy bundle (helpChat): awaited before its first call, or
  // on a slow machine `renderHelpChatMessage` was not there yet and the throw
  // ended the run before Settings (qa-1005, every LOOK run at 1440).
  const opened=await page.evaluate(async()=>{try{await ensureModule('helpChat');openHelpChat();return true;}catch(e){return false;}});
  if(opened){
    await page.waitForTimeout(500);await run('guide (empty)');
    await page.evaluate(()=>{renderHelpChatMessage('user','How do I add a reminder?');renderHelpChatMessage('assistant','Open the **Reminders** tab.',[{label:'Open Reminders',tab:'reminders'}],['Reminders']);});
    await page.waitForTimeout(200);await run('guide (a conversation)');
    await page.evaluate(()=>helpChatNewChat());await page.keyboard.press('Escape');await page.waitForTimeout(300);
  } else console.log('== guide: SKIPPED, openHelpChat is not reachable');
}

await page.evaluate(()=>{try{openSettingsModal('models');}catch(e){document.getElementById('settings-btn')?.click();}});await page.waitForTimeout(600);
// The section strip is hidden below 600 (the phone puts every section in one
// scroll with a jump select beside the search), so the sections are reached
// the way the app reaches them rather than by clicking a strip that is not
// there: another whole band this sweep would otherwise report as clean by
// never having looked at it.
for(const s of SECTIONS){
  const ok=PHONE
    ? await page.evaluate((name)=>{try{openSettingsModal(name);return true;}catch(e){return false;}},s)
    : await page.click(`#settings-modal [data-section="${s}"]`,{timeout:1500}).then(()=>true).catch(()=>false);
  if(!ok)continue;await page.waitForTimeout(400);await run('settings/'+s);
}
console.log(`== done at ${WIDTH}x${HEIGHT}, theme ${process.env.THEME||'light'}`);
if(empty.length){
  console.log(`FAIL: ${empty.length} surface${empty.length===1?'':'s'} measured 0 text elements at ${WIDTH}x${HEIGHT}, theme ${process.env.THEME||'light'}: ${empty.join(', ')}`);
  console.log('A surface with no text on it is either a surface this sweep could not open or one the app did not draw. Either way its "ok" above is about nothing.');
}
if(low.length)console.log(`FAIL: low contrast on ${low.length} surface${low.length===1?'':'s'}: ${low.join(', ')}`);
await browser.close();
process.exitCode=empty.length||low.length?1:0;})();
